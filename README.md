# vocal-imitation
A method for generating human-like vocal imitations of sounds.

## Setting up the vocal synthesizer pipeline

The vocal tract model used to generate synthetic utterances runs in [Faust](https://github.com/grame-cncm/faust), using [faust-ctypes](https://adud2.gitlab.io/faust-ctypes/) to import the compiled DLL into Python. First, [get the latest Faust distribution](https://github.com/grame-cncm/faust/releases) (this project has been tested up to Faust 2.74.6).

Then, to set up the synth pipeline, first navigate to ***faust_dsp***: `cd faust_dsp`. The `SF_voc_synth_m.dsp` file is the masculine speaker, and the `SF_voc_synth_f.dsp` file is the feminine speaker.

Compile the FAUST file to base C: `faust -lang c -A faust_ctypes -a faust_ctypes/dllarch.c <DSP file> > <C file destination>`.

Then, compile the to DLL: `gcc -fPIC -shared <C file> -o SF_voc_synth_f.so`.


## Getting referent data

The [FSD50k](https://zenodo.org/records/4060432) dataset is used as the set of referents. It's labeled using the [AudioSet Ontology](https://research.google.com/audioset/ontology/index.html).
