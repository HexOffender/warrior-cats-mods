"""Oodle decompression through an oo2core DLL that another installed game already ships.

The game links Oodle statically, so we borrow the DLL from elsewhere on the machine
(Planet Zoo, many Frontier/Epic titles, etc.). It is only loaded to *read* game data.
"""
import ctypes
import os


class Oodle:
    def __init__(self, dll_path):
        self.path = dll_path
        dll = ctypes.WinDLL(dll_path)
        fn = dll.OodleLZ_Decompress
        fn.restype = ctypes.c_ssize_t
        fn.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_ssize_t,
                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t,
                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_int]
        self._decompress = fn

    def decompress(self, src, raw_size):
        out = ctypes.create_string_buffer(raw_size)
        n = self._decompress(src, len(src), out, raw_size, 1, 0, 0, None, 0, None, None, None, 0, 3)
        if n != raw_size:
            raise RuntimeError(f"Oodle decompression failed ({n} of {raw_size} bytes)")
        return out.raw


def find_oodle_dll(search_roots):
    """Look a few folders deep under each root for an oo2core_*_win64.dll."""
    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        base_depth = root.rstrip("\\/").count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            if dirpath.count(os.sep) - base_depth >= 3:
                dirnames[:] = []
            for fn in filenames:
                low = fn.lower()
                if low.startswith("oo2core_") and low.endswith("_win64.dll"):
                    return os.path.join(dirpath, fn)
    return None
