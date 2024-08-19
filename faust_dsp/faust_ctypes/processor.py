import faust_ctypes.ftypes as f

import ctypes as c
import numpy as np


class Processor(object):
    """Python object wrapping the processing part of a dll
    """
    def __init__(self, dll, dsp_p):
        """initialize the processor

        :param dll: the dynamically linked library
        :type dll: ctypes.CDLL

        :param dsp_p: a pointer to the C dsp object
        :type dsp_p: ctypes.c_void_p
        """
        if not (hasattr(dll, "_is_cpython_typed") and dll._is_cpython_typed):
            raise TypeError("dynamic library not typed yet")
        # meta data about general signal processing
        self.dll = dll
        self.dsp_p = dsp_p
        self.FAUSTFLOAT, self.dtype = f.get_faustfloat(dll)
        self.FAUSTFLOATP = c.POINTER(self.FAUSTFLOAT)

        # dsp data
        self.num_in = dll.getNumInputsmydsp(self.dsp_p)
        self.num_out = dll.getNumOutputsmydsp(self.dsp_p)
        self.is_synth = (self.num_in == 0)

        # internal structures for indirect memory layout
        self._in_type = self.FAUSTFLOATP * self.num_in
        self._out_type = self.FAUSTFLOATP * self.num_out
        self._ins = self._in_type()
        self._outs = self._out_type()

    def process(self, nsamples):
        """small wrapper around C function ``computemydsp``

        can be useful if last input array has been modified
        avoid re-check and re-generation of indirect memory layout

        :param nsamples: number of samples
        :type nsamples: int"""
        self.dll.computemydsp(self.dsp_p, c.c_int(nsamples),
                              self._ins, self._outs)

    def prepare(self, audio_in, audio_out):
        """make an inner representation of i/o arrays to compute them
        handles indirect memory layout (unsupported by NumPy
        https://stackoverflow.com/questions/64815148/)

        In the special case of synthesizer, ``audio_in`` can be anything

        :param audio_in: the array to be processed
        :type audio_in: numpy.ndarray
        :param audio_out: the target array
        :type audio_out: numpy.ndarray
        """
        if not self.is_synth:
            for i, li in enumerate(audio_in):
                self._ins[i] = li.ctypes.data_as(self.FAUSTFLOATP)
        for i, li in enumerate(audio_out):
            self._outs[i] = li.ctypes.data_as(self.FAUSTFLOATP)

    def compute(self, audio_in, audio_out=None):
        """process an array with the dsp

        :param audio_in: the array to be processed
                         or the number of samples if dsp is a synthesizer
        :type audio_in: int or numpy.ndarray
        :param audio_out: (optional) the target array
        :type audio_out: numpy.ndarray or None
        :return: the array containing the processed signal
                 (``audio_out`` if given)
        """
        self.check_match(audio_in)
        if self.is_synth:
            nsamples = audio_in
        else:
            nsamples = audio_in.shape[1]

        # build output
        if audio_out is None:
            audio_out = self.gen_io(nsamples, 1)

        self.check_match(audio_out, nsamples)
        self.prepare(audio_in, audio_out)

        self.process(nsamples)

        return audio_out

    def check_match(self, iodat, nsamples=-1):
        """checks if an input/output matches the dsp

        :param iodat: the input/output data structure to test
        :param nsamples: strictly negative if input,
                         number of desired samples if output
        :raise TypeError: if the array type doesn't match DSP's FAUSTFLOAT type
        :raise ValueError: if the shape of the array doesn't match DSP's i/o
        """
        isout = nsamples >= 0
        smode = "output" if isout else "input"
        num = self.num_out if isout else self.num_in

        # eliminate synth very special case
        if self.is_synth and not isout:
            if isinstance(iodat, int):
                if iodat < 0:
                    raise ValueError("shape mismatch in Synth:"
                                     "synth input should be positive")
                return
            else:
                raise TypeError("type mismatch in DSP: "
                                "synth input should be int")

        # iodat should now be an array
        if self.dtype != iodat.dtype:
            raise TypeError("type mismatch in DSP with %s" % smode)
        if iodat.ndim != 2:
            raise ValueError("shape mismatch in DSP with %s, "
                             "not a 2D array" % smode)
        if num != iodat.shape[0]:
            raise ValueError("shape mismatch in DSP with %s, (%d vs %d)"
                             % (smode, num, iodat.shape[0]))

        # output special case
        if isout and nsamples > iodat.shape[1]:
            raise ValueError("shape mismatch in DSP with audio_out"
                             "output array too small to contain result")

    def gen_io(self, nsamples, isout=False, init=True):
        """generate a correct input/output 2D array

        :param nsamples: number of samples to generate
        :type nsamples: int
        :param isout: (optional) False if input True if output
        :type isout: bool
        :param init: wether to initialize or not the array
        :type init: bool

        :return: an input/output structure that is certified to be
                 DSP-compatible
        :rtype: :ref:`DSP-compatible io <dspcio>`)

        """
        if self.is_synth and not isout:
            return nsamples
        num = self.num_out if isout else self.num_in
        gen = np.zeros if init else np.empty
        return gen((num, nsamples), dtype=self.dtype)

    def from_obj(self, obj):
        """generate a numpy array from an object

        :param obj: the object
        :type obj: numpy-compatible object

        :return: a numpy array that can be an input (provided correct row
                 number)
        :rtype: numpy.ndarray
        """
        return np.atleast_2d(np.array(obj, dtype=self.dtype))
