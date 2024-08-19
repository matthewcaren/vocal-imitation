import faust_ctypes.ftypes as f


class MetaData(object):
    """object used to retrieve DSP metadata with callbacks"""
    def __init__(self):
        self.data = dict()
        self.glue = f.MetaGlue(None, f.metaDeclareFun(self.declare))

    def declare(self, metaInterface, key, val):
        """callback for declaring python dict with C"""
        self.data[key] = val
