"""Windows' SendInput structures and flags (ctypes), for pressing keys: the key remapper (remapper.py) and
the agent's window driver (agent/window.py) both send keys with them."""
import ctypes
from ctypes import wintypes

INPUT_KEYBOARD, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 1, 0x1, 0x2
MAGIC = 0x57434D52   # "WCMR" in dwExtraInfo marks wcmods' own key presses, so the remapper's hook lets them through
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]   # MOUSEINPUT is the largest member


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]
