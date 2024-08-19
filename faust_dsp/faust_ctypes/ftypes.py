import ctypes as c
import numpy as np


def get_faustfloat(dll):
    """returns the type of floating-point number used
    by analyzing the content of FAUSTFLOAT macro

    :param dll: DLL loaded by ctypes
    :type dll: ctypes.CDLL

    :return: (ctypes data type, numpy data type)
    :rtype: tuple[ctypes.CDLL, numpy.dtype]"""

    fname = c.c_char_p.in_dll(dll, "dllarch_faustfloat_name").value
    fsize = c.c_size_t.in_dll(dll, "dllarch_faustfloat_size").value
    if fname in (b"float", b"double", b"long double"):
        return (getattr(c, "c_" + fname.decode().replace(" ", "")),
                np.dtype("float%d" % (fsize * 8)))
    # might be in the future a FixPoint arithmetic implementation
    raise TypeError("Unknown FAUSTFLOAT type")


# translation of architecture/faust/gui/CInterface.h
class Soundfile(c.Structure):
    """
    .. note::
        Not implemented yet, but one can still pass soundfiles as dsp inputs by
        converting them as numpy arrays
    """
    pass


sound_pp = c.POINTER(c.POINTER(Soundfile))

# declare types related to metadata
metaDeclareFun = c.CFUNCTYPE(None, c.c_voidp, c.c_char_p, c.c_char_p)


class MetaGlue(c.Structure):
    _fields_ = [
        ("metaInterface", c.c_void_p),
        ("declare", metaDeclareFun)
    ]


MetaGlue_p = c.POINTER(MetaGlue)


# declare types related to UI
# harder than MetaData because types are generics, depending on FAUSTFLOAT

class UiFunTypes(object):
    """container for types of UI functions parameterized by FAUSTFLOAT"""
    def __init__(self, FAUSTFLOAT):
        """
        :param FAUSTFLOAT: float type
        :type FAUSTFLOAT: ctypes.CDLL"""
        FAUSTFLOATP = c.POINTER(FAUSTFLOAT)
        # layout

        self.openTabBoxFun = c.CFUNCTYPE(None, c.c_voidp, c.c_char_p)
        self.openHorizontalBoxFun = self.openTabBoxFun
        self.openVerticalBoxFun = self.openTabBoxFun
        self.closeBoxFun = c.CFUNCTYPE(None, c.c_voidp)

        # active widgets
        self.addButtonFun = c.CFUNCTYPE(
            None, c.c_voidp, c.c_char_p, FAUSTFLOATP)
        self.addCheckButtonFun = self.addButtonFun
        self.addVerticalSliderFun = c.CFUNCTYPE(
            None, c.c_voidp, c.c_char_p, FAUSTFLOATP,
            FAUSTFLOAT, FAUSTFLOAT, FAUSTFLOAT, FAUSTFLOAT)
        self.addHorizontalSliderFun = self.addVerticalSliderFun
        self.addNumEntryFun = self.addVerticalSliderFun

        # passive widgets
        self.addHorizontalBargraphFun = c.CFUNCTYPE(
            None, c.c_voidp, c.c_char_p, FAUSTFLOATP, FAUSTFLOAT, FAUSTFLOAT)
        self.addVerticalBargraphFun = self.addHorizontalBargraphFun

        # soundfiles
        self.addSoundfileFun = c.CFUNCTYPE(
            None, c.c_voidp, c.c_char_p, c.c_char_p, sound_pp)
        self.declareFun = c.CFUNCTYPE(
            None, c.c_voidp, FAUSTFLOATP, c.c_char_p, c.c_char_p)

        self.FAUSTFLOAT = FAUSTFLOAT
        # we need to ensure this type is not garbage-collected
        self.FAUSTFLOATP = FAUSTFLOATP


def gen_Glue(ft):
    """Class Factory generating an UIGlue class compatible with CDLL structures

    :param ft: the fun type
    :type ft: UiFunTypes

    :return: a class generating UIGlue Ctype consistent with ft"""

    class FloatUIGlue(c.Structure):
        _fields_ = [
            ("uiInterface", c.c_void_p),
            ("openTabBox", ft.openTabBoxFun),
            ("openHorizontalBox", ft.openHorizontalBoxFun),
            ("openVerticalBox", ft.openVerticalBoxFun),
            ("closeBox", ft.closeBoxFun),
            ("addButton", ft.addButtonFun),
            ("addCheckButton", ft.addCheckButtonFun),
            ("addVerticalSlider", ft.addVerticalSliderFun),
            ("addHorizontalSlider", ft.addHorizontalSliderFun),
            ("addNumEntry", ft.addNumEntryFun),
            ("addHorizontalBargraph", ft.addHorizontalBargraphFun),
            ("addVerticalBargraph", ft.addVerticalBargraphFun),
            ("addSoundfile", ft.addSoundfileFun),
            ("declare", ft.declareFun)
        ]

        _ft = ft

        def __init__(self, *args):
            # no automatic conversion from callback to function pointers
            # ensure it automatically when creating an instance
            t_args = [ftype(fun)
                      for (_, ftype), fun in zip(self._fields_, args)]
            super().__init__(*t_args)

    return FloatUIGlue


def type_dsplib(dll, uiglue_t):
    """declare the types of the functions of the dsp library

    This is very important to avoid SegFaults. C pointers are stored as python
    ints. By declaring a type, translation from int to C pointer is automatic
    when calling a function

    :param dll: DLL loaded by ctypes
    :type dll: ctypes.CDLL

    :param uiglue_t: UIGlue CType
    :type uiglue_t: class

    .. note::
        as we cannot know the structure of mydsp whithout reading the
        code, mydsp* type is c_void_p
    """
    type_generic_dsplib(dll)
    type_uiglue_dsplib(dll, uiglue_t)


def type_generic_dsplib(dll):
    FAUSTFLOAT = get_faustfloat(dll)[0]
    FAUSTFLOATPP = c.POINTER(c.POINTER(FAUSTFLOAT))

    dll.newmydsp.restype = c.c_void_p
    dll.newmydsp.argtypes = []

    dll.deletemydsp.restype = None
    dll.deletemydsp.argtypes = [c.c_void_p]

    dll.metadatamydsp.restype = None
    dll.metadatamydsp.argtypes = [MetaGlue_p]

    dll.getSampleRatemydsp.restype = c.c_int
    dll.getSampleRatemydsp.argtypes = [c.c_void_p]

    dll.getNumInputsmydsp.restype = c.c_int
    dll.getNumInputsmydsp.argtypes = [c.c_void_p]

    dll.getNumOutputsmydsp.restype = c.c_int
    dll.getNumOutputsmydsp.argtypes = [c.c_void_p]

    dll.classInitmydsp.restype = None
    dll.classInitmydsp.argtypes = [c.c_int]

    dll.instanceResetUserInterfacemydsp.restype = None
    dll.instanceResetUserInterfacemydsp.argtypes = [c.c_void_p]

    dll.instanceClearmydsp.restype = None
    dll.instanceClearmydsp.argtypes = [c.c_void_p]

    dll.instanceConstantsmydsp.restype = None
    dll.instanceConstantsmydsp.argtypes = [c.c_void_p, c.c_int]

    dll.instanceInitmydsp.restype = None
    dll.instanceInitmydsp.argtypes = [c.c_void_p, c.c_int]

    dll.initmydsp.restype = None
    dll.initmydsp.argtypes = [c.c_void_p, c.c_int]

    dll.computemydsp.restype = None
    dll.computemydsp.argtypes = [c.c_void_p, c.c_int,
                                 FAUSTFLOATPP, FAUSTFLOATPP]

    dll._is_cpython_typed = True


def type_uiglue_dsplib(dll, uiglue_t):
    dll.buildUserInterfacemydsp.restype = None
    dll.buildUserInterfacemydsp.argtypes = [c.c_void_p, c.POINTER(uiglue_t)]
