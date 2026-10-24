"""The game's process and window on Windows: finding them, pictures of the window, and keys.

Pictures (PrintWindow) and posted keys work on the game's own window, whatever is in front of it,
without moving the mouse or changing the focus. UE4SS's key binds (the mod menu's Insert, a script's
Game.onKey) read the keyboard itself, so they only see `hotkey`, which presses keys for real and so
needs the game in front.
"""
import ctypes
import ctypes.wintypes as wt
import time

from .. import keymap
from ..config import EXE_NAME
from ..remapper import INPUT, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, MAGIC
from .image import Image

CRASH_REPORTER = "CrashReportClient.exe"

# Own copies of the DLLs, so these argtypes don't clash with the ones other modules set.
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

TH32CS_SNAPPROCESS = 0x2
PROCESS_TERMINATE, SYNCHRONIZE = 0x1, 0x100000
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
PW_CLIENTONLY, PW_RENDERFULLCONTENT = 0x1, 0x2
SW_RESTORE = 9


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = (wt.DWORD, wt.DWORD)
kernel32.Process32FirstW.argtypes = (wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
kernel32.Process32NextW.argtypes = (wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
kernel32.TerminateProcess.argtypes = (wt.HANDLE, wt.UINT)
kernel32.CloseHandle.argtypes = (wt.HANDLE,)
user32.EnumWindows.argtypes = (WNDENUMPROC, wt.LPARAM)
user32.GetWindowThreadProcessId.argtypes = (wt.HWND, ctypes.POINTER(wt.DWORD))
user32.IsWindowVisible.argtypes = (wt.HWND,)
user32.IsIconic.argtypes = (wt.HWND,)
user32.GetClientRect.argtypes = (wt.HWND, ctypes.POINTER(wt.RECT))
user32.GetForegroundWindow.restype = wt.HWND
user32.SetForegroundWindow.argtypes = (wt.HWND,)
user32.ShowWindow.argtypes = (wt.HWND, ctypes.c_int)
user32.GetDC.restype = wt.HDC
user32.GetDC.argtypes = (wt.HWND,)
user32.ReleaseDC.argtypes = (wt.HWND, wt.HDC)
user32.PrintWindow.argtypes = (wt.HWND, wt.HDC, wt.UINT)
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.MapVirtualKeyW.argtypes = (wt.UINT, wt.UINT)
user32.SendInput.argtypes = (wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.GetWindowTextW.argtypes = (wt.HWND, wt.LPWSTR, ctypes.c_int)
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = (wt.HDC,)
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = (wt.HDC, ctypes.c_int, ctypes.c_int)
gdi32.SelectObject.argtypes = (wt.HDC, wt.HGDIOBJ)
gdi32.GetDIBits.argtypes = (wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.POINTER(BITMAPINFOHEADER), wt.UINT)
gdi32.DeleteObject.argtypes = (wt.HGDIOBJ,)
gdi32.DeleteDC.argtypes = (wt.HDC,)


def processes(exe=None):
    """[(pid, exe name)] of running processes, or only those named `exe` (any case)."""
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wt.HANDLE(-1).value:
        return []
    out = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if exe is None or entry.szExeFile.lower() == exe.lower():
                out.append((entry.th32ProcessID, entry.szExeFile))
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return out


def game_pid():
    found = processes(EXE_NAME)
    return found[0][0] if found else None


def crash_reporters():
    """Pids of crash reporter windows (Unreal's CrashReportClient) that are open."""
    return [pid for pid, _ in processes(CRASH_REPORTER)]


def kill(pid):
    """End a process at once (no saving): for a hung game, or a crash reporter (closing it sends nothing)."""
    h = kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
    if not h:
        return False
    try:
        return bool(kernel32.TerminateProcess(h, 1))
    finally:
        kernel32.CloseHandle(h)


def game_window(pid=None):
    """The game's main window (its biggest visible one), or None."""
    pid = pid or game_pid()
    if not pid:
        return None
    found = []

    def each(hwnd, _):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            r = wt.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            found.append((r.right * r.bottom, hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(each), 0)
    return max(found)[1] if found else None


def title(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value


def client_size(hwnd):
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    return r.right, r.bottom


def is_foreground(hwnd):
    return bool(hwnd) and user32.GetForegroundWindow() == hwnd


def is_minimized(hwnd):
    return bool(user32.IsIconic(hwnd))


def bring_to_front(hwnd):
    """Put the game in front (restoring it if minimised). Windows may refuse; True when it's in front."""
    if is_minimized(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    # Windows only lets the program the user last used change the focus; a tap of Alt counts as using it.
    _send_vk(keymap.VK["LeftAlt"], True)
    _send_vk(keymap.VK["LeftAlt"], False)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    return is_foreground(hwnd)


def capture(hwnd):
    """A picture of the window's drawing area as it is now (also when other windows cover it)."""
    w, h = client_size(hwnd)
    if w <= 0 or h <= 0:
        raise RuntimeError("the game's window has no size (minimised?)")
    hdc = user32.GetDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    try:
        gdi32.SelectObject(mem, bmp)
        if not user32.PrintWindow(hwnd, mem, PW_CLIENTONLY | PW_RENDERFULLCONTENT):
            raise RuntimeError("Windows couldn't capture the game's window")
        bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    finally:
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, hdc)
    return Image.from_bgra(buf.raw, w, h)


def vk_of(name):
    """A key's Windows code from its Unreal name ("W", "SpaceBar", "F6", "Insert"; any case)."""
    for k, vk in keymap.VK.items():
        if k.lower() == str(name).lower():
            return vk
    aliases = {"space": "SpaceBar", "esc": "Escape", "return": "Enter", "shift": "LeftShift",
               "ctrl": "LeftControl", "control": "LeftControl", "alt": "LeftAlt", "ins": "Insert", "del": "Delete"}
    if str(name).lower() in aliases:
        return keymap.VK[aliases[str(name).lower()]]
    raise ValueError(f"unknown key {name!r}; use an Unreal key name such as W, SpaceBar, Enter, F6")


def _lparam(vk, up):
    scan = user32.MapVirtualKeyW(vk, 0)
    lp = 1 | (scan << 16) | ((1 << 24) if vk in keymap.EXTENDED else 0)
    if up:
        lp |= (1 << 30) | (1 << 31)
    return lp


def post_key(hwnd, vk, down):
    """A key press or release posted to the window: the game's own controls see it, focus or not."""
    return bool(user32.PostMessageW(hwnd, WM_KEYDOWN if down else WM_KEYUP, vk, _lparam(vk, not down)))


def _send_vk(vk, down):
    flags = (0 if down else KEYEVENTF_KEYUP) | (KEYEVENTF_EXTENDEDKEY if vk in keymap.EXTENDED else 0)
    event = INPUT(type=INPUT_KEYBOARD)
    # MAGIC marks it as injected by wcmods, so a running key remapper leaves it alone.
    event.u.ki = KEYBDINPUT(wVk=vk, wScan=user32.MapVirtualKeyW(vk, 0), dwFlags=flags, time=0, dwExtraInfo=MAGIC)
    return user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) == 1


def send_key(vk, down):
    """A real key press or release (SendInput): it goes to whatever window is in front."""
    return _send_vk(vk, down)
