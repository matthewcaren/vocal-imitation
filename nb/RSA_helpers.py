import torch
import json
import os
import random
import torchaudio.transforms as T
import torch.nn.functional as F



### GLOBALS ###
AUDIO_SR = 44100
CONTROL_SR = 25
SAMPLE_LEN = 50
FEAT_NFFT = 4096
VOCAL_DATA_DIR = '../data/vocal_synth_f/'
# REFERENT_DATA_DIR = '../data/ESC-50/audio/'
# REFERENT_METADATA_PATH = '../data/ESC-50/meta/esc50.csv'
REFERENT_DATA_DIR = '../data/FSD50/eval_audio/'
REFERENT_METADATA_PATH = '../data/FSD50/ground_truth/eval.csv'
ONTOLOGY_PATH = '../data/audioset/ontology.json'
N_AUDIO_FEATURES = 19
N_VOCAL_TRACT_CONTROLS = 5
N_GRID_SEQ_TYPE = 11


### HELPER FUNCS ###

# ontology stuff

def get_ontology_dist(ontology_tree, a, b):
    breadcrumbs_a = find_key(ontology_tree, a)
    breadcrumbs_b = find_key(ontology_tree, b)
    a_to_shared_ancestor = [x for x in breadcrumbs_a if x not in breadcrumbs_b]
    b_to_shared_ancestor = [x for x in breadcrumbs_b if x not in breadcrumbs_a]
    return len(a_to_shared_ancestor) + len(b_to_shared_ancestor)


def build_ontology_tree():
    with open(ONTOLOGY_PATH) as data_file:    
        audioset_data = json.load(data_file)

    ontology = {}
    for category in audioset_data:
        tmp = {}
        tmp["name"] = category["name"]	
        tmp["id"] = category["id"]
        tmp["restrictions"] = category["restrictions"]
        tmp["child_ids"] = category["child_ids"]
        tmp["parents_ids"] = []
        ontology[category["id"]] = tmp

    # find parents
    for cat in ontology: 
        for c in ontology[cat]["child_ids"]:
            ontology[c]["parents_ids"].append(cat)

    # ancestors = categories without parents
    ancestors = [] 
    for cat in ontology:
        if ontology[cat]["parents_ids"] == []:
            ancestors.append(cat)

    # build entire tree
    tree = {}
    tree["name"] = "Ontology"
    tree["id"] = "ROOT"
    tree["children"] = []
    for category in ancestors:
        top_ancestors = {}
        top_ancestors["name"] = ontology[category]["name"]
        top_ancestors["id"] = ontology[category]["id"]
        top_ancestors["mark"] = ontology[category]["restrictions"]
        top_ancestors["children"] = get_all_children(category,ontology)
        tree["children"].append(top_ancestors)
    
    return tree


def get_all_children(category, ontology):
    childs = ontology[category]["child_ids"]
    childs_names = []
    for child in childs:
        child_name = {}
        child_name["name"] = ontology[child]["name"]
        child_name["id"] = ontology[child]["id"]
        child_name["mark"] = ontology[child]["restrictions"]
        if "child_ids" in ontology[child]:
            child_name["children"] = get_all_children(child,ontology)
        childs_names.append(child_name)
    if childs_names:
        return childs_names


def find_key(tree, target, path = []):
    '''
    Get breadcrumbs (of category IDs) given a target
    category (can be either ID or name)
    '''
    path.append(tree["id"])

    possible_hits = [tree["id"], clean_name(tree["name"])]
    if ", " in tree["name"]:
        possible_hits += [n.lower() for n in clean_name(tree["name"]).split(", ")]

    target = clean_name(target)

    if target in possible_hits:
        cleaned_path = []
        for x in path:
            if x not in cleaned_path:
                cleaned_path.append(x)
        return cleaned_path
    elif isinstance(tree["children"], list):
        for child in tree["children"]:
            result = find_key(child, target, path + [child["id"]])
            if result:
                return result
    path.pop()


def clean_name(s):
    '''
    Make lowercase, replace underscores with spaces, turn lists with "and" into commas
    '''
    return s.lower().replace('_', ' ').replace(', and ', ', ').replace(' and ', ', ')



# feature extraction

def spec_flatness_from_spectrogram(input_x, dim):
    log_x = torch.log(input_x)
    gmean = torch.exp(torch.mean(log_x, dim=dim))
    return torch.nan_to_num(gmean / torch.mean(input_x, dim=dim), nan=0.0)   # geo mean / arith mean

def trap_win_1D(x, amt = 10):
    '''
    Apply trapezoidal window with transition length amt (on each end)
    '''
    window = torch.ones_like(x)
    window[1:amt+1] = torch.linspace(0, 1, steps=amt)
    window[-amt-2:-2] = torch.linspace(1, 0, steps=amt)
    window[0] = 0
    window[-1] = 0
    return x*window

def centered_deriv(x):
    '''
    Take discrete (centered) derivative of a 1D Tensor
    '''
    return (F.pad(x,(1,0))[:-1] - F.pad(x,(0,1))[1:])/2

def compute_dist_features(seq, include_mean=True):
    deriv = centered_deriv(seq)
    ones = torch.ones_like(seq)
    
    mean = ones*torch.mean(seq, dtype=float)
    std = ones*torch.std(seq)
    deriv_mean = ones*abs(torch.mean(deriv, dtype=float)) * 10**9   # scaling on vibes
    deriv_std = ones*torch.std(deriv)
    
    if include_mean:
        return torch.cat((seq, mean, std, deriv_mean, deriv_std))
    else:
        return torch.cat((seq, std, deriv_mean, deriv_std))


class SimpleAudioFeatures(torch.nn.Module):
    '''
    Feature extractor class
    '''
    def __init__(self):
        super().__init__()
        self.spectrogram = T.Spectrogram(n_fft=FEAT_NFFT)
        self.centroid = T.SpectralCentroid(AUDIO_SR, n_fft=FEAT_NFFT)

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        # create spectrogram, add mild trapezoidal window
        specgram = self.spectrogram(waveform)
        
        loudness = trap_win_1D(F.normalize(torch.sum(specgram, 0), dim=0)) * 600
        loudness_f = compute_dist_features(loudness, include_mean=False)
        
        flatness = trap_win_1D(spec_flatness_from_spectrogram(specgram, dim=0)) * 2 * 10**5   # scaling factor on vibes
        flatness_f = compute_dist_features(flatness)
        
        centroid = trap_win_1D(self.centroid(waveform)) / AUDIO_SR * 3000   # scaling factor on vibes
        centroid_f = compute_dist_features(centroid)
        
        peak = trap_win_1D(torch.argmax(specgram, dim=0).float()) * 3   # scaling factor on vibes
        peak_f = compute_dist_features(peak)

        all_features = (loudness_f, flatness_f, centroid_f, peak_f)        
        return torch.cat(all_features)
