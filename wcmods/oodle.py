"""Oodle decompression: wcmods' own Kraken decoder (kraken.py), or an oo2core DLL when one is set.

The game's files are Kraken-compressed (Oodle's codec), and the game links Oodle statically, so it
has no DLL to borrow. wcmods decodes them itself, in Python. An `oo2core_*_win64.dll` from another
game, named by "oodle_dll" in wcmods.json, is used instead when it's there: about a hundred times
faster, which only shows when extracting many files. Nothing needs it. Either is only used to
*read* the game's files; what wcmods writes is uncompressed.
"""
import ctypes

from . import kraken


class Oodle:
    """Decompresses Kraken data. `path` is the DLL in use, or None for the Python decoder."""

    def __init__(self, dll_path=None):
        self.path = dll_path or None
        self._dll = None
        if dll_path:
            dll = ctypes.WinDLL(dll_path)
            fn = dll.OodleLZ_Decompress
            fn.restype = ctypes.c_ssize_t
            fn.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_ssize_t,
                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t,
                           ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_int]
            self._dll = fn

    @property
    def name(self):
        return self.path or "wcmods' Kraken decoder"

    def decompress(self, src, raw_size):
        """`raw_size` bytes from the compressed `src`."""
        if self._dll is None:
            return kraken.decompress(src, raw_size)
        out = ctypes.create_string_buffer(raw_size)
        n = self._dll(src, len(src), out, raw_size, 1, 0, 0, None, 0, None, None, None, 0, 3)
        if n != raw_size:
            raise RuntimeError(f"Oodle decompression failed ({n} of {raw_size} bytes)")
        return out.raw
