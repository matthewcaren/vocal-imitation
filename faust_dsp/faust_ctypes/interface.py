import string
import ctypes as c

# a string consisting of characters that are valid identifiers in both
# Python 2 and Python 3
valid_ident = string.ascii_letters + string.digits + "_"


def str_to_identifier(s):
    """Convert a "bytes" to a valid (in Python 2 and 3) identifier.

    :param s: the bytes string
    :type s: bytes

    :return: a string which is a valid identifier
    :rtype: string"""
    # convert str/bytes to unicode string
    s = s.decode()

    def filter_chars(s):
        for c in s:
            # periods are used for abbreviations and look ugly when converted
            # to underscore, so filter them out completely
            if c == ".":
                yield ""
            elif c in valid_ident or c == "_":
                yield c
            else:
                yield "_"

    if s[0] in string.digits:
        s = "_"+s

    return ''.join(filter_chars(s))


class Param(object):
    """A UI parameter object (from FAUSTPy)

    This objects represents a FAUST UI input.  It makes sure to enforce the
    constraints specified by the minimum, maximum and step size.

    This object implements the descriptor protocol: reading it works just like
    normal objects, but assignment is redirects to its "zone" attribute.
    """

    def __init__(self, label, zone, init, min, max, step, param_type):
        """
        :param label: The full label as specified in the FAUST DSP file.
        :param zone: Points to the FAUSTFLOAT object inside the DSP C object.
        :param init: The initialisation value.
        :param min:  The minimum allowed value.
        :param max:  The maximum allowed value.
        :param step: The step size of the parameter.
        :param paramtype: The parameter type (e.g., HorizontalSlider)
        """

        self.label = label
        self._zone = zone
        self._zone[0] = init
        self.min = min
        self.max = max
        self.step = step
        self.type = param_type

        # extra attributes
        self.default = init
        self.metadata = {}
        self.__doc__ = "min={0}, max={1}, step={2}".format(min, max, step)

    def __zone_getter(self):
        return self._zone[0]

    def __zone_setter(self, x):
        if x >= self.max:
            self._zone[0] = self.max
        elif x <= self.min:
            self._zone[0] = self.min
        else:
            self._zone[0] = self.min + round((x-self.min)/self.step)*self.step

    zone = property(fget=__zone_getter, fset=__zone_setter,
                    doc="Pointer to the value of the parameter.")

    def __set__(self, obj, value):

        self.zone = value


class Box(object):
    """Box containing widgets (from FAUSTPy)"""
    def __init__(self, label, layout):
        """
        
        :param label: the label of the box
        :type label: bytes
        :param layout: the layout of the box, "horizontal", "vertical" or "tab"
        :type layout: str
        """
        self.label = label
        self.layout = layout
        self.metadata = {}

    def __setattr__(self, name, value):
        if name in self.__dict__ and hasattr(self.__dict__[name], "__set__"):
            self.__dict__[name].__set__(self, value)
        else:
            object.__setattr__(self, name, value)


# TODO: implement the *Display() and *Bargraph() methods
class UserInterface(object):
    """(from FAUSTPy)
    Maps the UI elements of a FAUST DSP to attributes of another object,
    specifically a FAUST wrapper object.

    In FAUST, UI's are specified by the DSP object, which calls methods of a UI
    object to create them.  The PythonUI class implements such a UI object.  It
    creates C callbacks to its methods and stores then in a UI struct, which
    can then be passed to the buildUserInterface() function of a FAUST DSP
    object.

    The DSP object basically calls the methods of the PythonUI class from C via
    the callbacks in the UI struct and thus creates a hierarchical namespace of
    attributes which map back to the DSP's UI elements.

    .. note::

        Box and Param attributes are prefixed with `b_` and `p_`, respectively,
        in order to differentiate them from each other and from regular
        attributes.

    Boxes and parameters without a label are given a default name of `anon<N>`,
    where N is an integer (e.g., `p_anon1` for a label-less parameter).

    """

    def __init__(self, GlueClass, obj=None):
        """
        :param GlueClass: class declaring UI Glue structure
        :type GlueClass: class
        :param obj: The Python object to which the UI elements are to be added.
            If None (the default) the PythonUI instance manipulates itself.
        :type obj: object
        """

        if obj is not None:
            self._boxes = [obj]
        else:
            self._boxes = [self]

        self._num_anon_boxes = [0]
        self._num_anon_params = [0]
        self._metadata = [{}]
        self._group_metadata = {}

        # create a UI object and store callbacks as it's function
        # pointers; also store the above functions in self so that they don't
        # get garbage collected

        self.ui_glue = GlueClass(
            None, self._openTabBox,
            self._openHorizontalBox, self._openVerticalBox, self._closeBox,
            self._addButton, self._addCheckButton, self._addVerticalSlider,
            self._addHorizontalSlider, self._addNumEntry,
            self._addHorizontalBargraph, self._addVerticalBargraph,
            self._addSoundfile, self._declare)

    ##########################
    # stuff to do with boxes
    ##########################

    def _openBox(self, label, layout):
        # If the label is an empty string, don't do anything, just stay in the
        # current Box
        if label:
            # special case the first box, which is always "0x00" (the ASCII
            # Null character), so that it has a consistent name
            if label.decode() == '0x00':
                sane_label = "ui"
            else:
                sane_label = "b_"+str_to_identifier(label)
        else:
            # if the label is empty, create a default label
            self._num_anon_boxes[-1] += 1
            sane_label = "b_anon" + str(self._num_anon_boxes[-1])

        # create a new sub-Box and make it a child of the current Box
        box = Box(label, layout)
        setattr(self._boxes[-1], sane_label, box)
        self._boxes.append(box)

        # store the group meta-data in the newly opened box and reset
        # self._group_metadata
        self._boxes[-1].metadata.update(self._group_metadata)
        self._group_metadata = {}

        self._num_anon_boxes.append(0)
        self._num_anon_params.append(0)
        self._metadata.append({})

    # callback functions for uiInterface struct

    def _openTabBox(self, ui_interface, label):
        self._openBox(label, "tab")

    def _openHorizontalBox(self, ui_interface, label):
        self._openBox(label, "horizontal")

    def _openVerticalBox(self, ui_interface, label):
        self._openBox(label, "vertical")

    def _closeBox(self, ui_interface):
        cur_metadata = self._metadata.pop()
        # iterate over the objects in the current box and assign the meta-data
        # to the correct parameters
        for p in self._boxes[-1].__dict__.values():

            # TODO: add the Display class (or whatever it will be called) to
            # this list once *Display and *Bargraph are implemented
            if not isinstance(p, (Param, )):
                continue

            # iterate over the meta-data that has accumulated in the current
            # box and assign it to its corresponding Param objects
            for zone_addr, mdata in cur_metadata.items():
                if c.addressof(p._zone) == zone_addr:
                    p.metadata.update(mdata)

        self._num_anon_boxes.pop()
        self._num_anon_params.pop()

        # now pop the box off the stack
        self._boxes.pop()

    ##########################
    # stuff to do with inputs
    ##########################

    def _add_input(self, label, zone, init, min, max, step, param_type):
        if label:
            sane_label = str_to_identifier(label)
        else:
            # if the label is empty, create a default label
            self._num_anon_params[-1] += 1
            sane_label = "anon" + str(self._num_anon_params[-1])

        setattr(self._boxes[-1], "p_"+sane_label,
                Param(label, zone, init, min, max, step, param_type))

    def _addButton(self, ui_interface, label, zone):
        self._add_input(label, zone, 0, 0, 1, 1, "Button")

    def _addCheckButton(self, ui_interface, label, zone):
        self._add_input(label, zone, 0, 0, 1, 1, "CheckButton")

    def _addVerticalSlider(self, ui_interface, label, zone,
                           init, min, max, step):
        self._add_input(label, zone, init, min, max, step, "VerticalSlider")

    def _addHorizontalSlider(self, ui_interface, label, zone,
                             init, min, max, step):
        self._add_input(label, zone, init, min, max, step, "HorizontalSlider")

    def _addNumEntry(self, ui_interface, label, zone, init, min, max, step):
        self._add_input(label, zone, init, min, max, step, "NumEntry")

    def _addHorizontalBargraph(self, ui_interface, label, zone, min, max):
        pass

    def _addVerticalBargraph(self, ui_interface, label, zone, min, max):
        pass

    def _addSoundfile(self, ui_interface, label, filename, sf_zone):
        pass

    def _declare(self, ui_interface, zone, key, value):
        if not zone:
            # set group meta-data
            #
            # the group meta-data is stored temporarily here and is set during
            # the next openBox()
            self._group_metadata[key] = value
        else:
            # store parameter meta-data
            #
            # since the only identifier we get is the zone (pointer to the
            # control value), we have to store this for now and assign it to
            # the corresponding parameter later in closeBox()
            if c.addressof(zone) not in self._metadata[-1]:
                self._metadata[-1][c.addressof(zone)] = {}
            self._metadata[-1][c.addressof(zone)][key] = value
