# vocal-imitation
A method for generating human-like vocal imitations of sounds.

## Setting up the vocal synthesizer pipeline

The vocal tract model used to generate synthetic utterances is written in [Faust](https://github.com/grame-cncm/faust), using [faust-ctypes](https://adud2.gitlab.io/faust-ctypes/) to import the compiled DLL into Python. First, [get the latest Faust distribution](https://github.com/grame-cncm/faust/releases) (this project has been tested up to Faust 2.74.6).

The `SF_voc_synth_m.dsp` synth is the masculine speaker, and the `SF_voc_synth_f.dsp` synth is the feminine speaker.

Navigate to **faust_dsp** (`cd faust_dsp`), then compile the FAUST file to base C: `faust -lang c -A faust_ctypes -a faust_ctypes/dllarch.c <DSP file> > <C file destination>`.

Then, compile the to DLL using any C compiler: `gcc -fPIC -shared <C file> -o SF_voc_synth_m.so`.


## Referent data

The [FSD50k](https://zenodo.org/records/4060432) dataset is used as the set of referents. It's labeled using the [AudioSet Ontology](https://research.google.com/audioset/ontology/index.html). Be sure to download all parts, then add the entire dataset to the **data** directory under **data/FSD50/**.
