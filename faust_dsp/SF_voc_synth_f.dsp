import("stdfaust.lib");

vsource(freq) = os.sawtooth(freq * (1+0.03*no.lfnoise(6)) * (1+0.03*no.lfnoise(2))) *(1+0.1*no.lfnoise(3)) : fi.lowpass(2, 4000) : _+no.noise*0.03 : fi.peak_eq_cq(-10, 2500, 0.5) : fi.peak_eq_cq(-4, freq, 1);

process = pm.SFFormantModel(3,vowel,fricative,freq,0.1*gain,vsource(freq), pm.formantFilterbankBP,0) : _*en.adsr(0.001,0.15,0.5,0.01,plosive) + no.noise*en.ar(0.001,0.04,plosive)*0.01 : *(1 - 0.7*fricative)
with{
	freq = hslider("v:vocal/[0]freq",0.5,0,1,0.01)*600 + 180 : si.smooth(0.9996);
	gain = hslider("v:vocal/[1]gain",0.5,0,1,0.01) : si.smooth(0.998);
	vowel = hslider("v:vocal/[3]vowel",0,0,1,0.01)*4 : si.smooth(0.9995);
	fricative = hslider("v:vocal/[4]fricative",0,0,1,0) : si.smooth(0.99);
	plosive = hslider("v:vocal/[5]plosive",1,0,1,1);
};