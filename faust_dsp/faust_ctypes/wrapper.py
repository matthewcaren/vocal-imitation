import ctypes as c
import faust_ctypes.ftypes as f

from os import path, PathLike

from faust_ctypes.processor import Processor
from faust_ctypes.interface import UserInterface
from faust_ctypes.metadata import MetaData


class Faust(object):
    """a python object wrapping a whole DSP DLL

    groups processor, interface and metadata, and ensure that they are
    consistently initialized together
    """
    def __init__(self, dll, sr=44100):
        """initialize the wrapper

        :param dll: the dynamically linked library
        :type dll: string or file-like or ctypes.CDLL
        :param sr: the sampling rate (unused as of now)
        :type sr: int

        """
        if isinstance(dll, (str, bytes, PathLike, int)) and path.exists(dll):
            self.dll = c.CDLL(path.abspath(dll))
        elif isinstance(dll, c.CDLL):
            self.dll = dll
        else:
            raise TypeError("unknown DLL: neither CDLL object nor valid path")

        self.sr = sr

        # we first need to narrow the CTypes headers to the actual value of
        # FAUSTFLOAT
        self.c_type, self.dtype = f.get_faustfloat(self.dll)

        self._ft = f.UiFunTypes(self.c_type)
        self._GlueClass = f.gen_Glue(self._ft)

        f.type_dsplib(self.dll, self._GlueClass)

        self.dsp_p = self.dll.newmydsp()
        self.dll.initmydsp(self.dsp_p, c.c_int(sr))

        self.proc = Processor(self.dll, self.dsp_p)
        self.ui = UserInterface(self._GlueClass)
        self.meta = MetaData()

        # we can now use callbacks to build the structure of the Python Objects
        # from the DLL
        self.dll.buildUserInterfacemydsp(self.dsp_p,
                                         c.byref(self.ui.ui_glue))
        self.dll.metadatamydsp(self.meta.glue)

    def __del__(self):
        self.dll.deletemydsp(self.dsp_p)
