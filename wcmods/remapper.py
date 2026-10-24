"""The key remapper: while the game is in front and you're playing (exploring, not in a menu), keys you
press stand in for the game's own keys. Menus, the cat-naming screen and every other program are left alone.
The game says which it is through a small UE4SS script (playstate.py) that writes "play" or "menu" to a
file; without it, the remapper remaps whenever the game is in front.

Windows only. It uses a low-level keyboard hook (and a mouse hook when a mouse button or the wheel
stands in for a key): a remapped key is held back and the game's key is sent in its place with
SendInput. Keys that other programs inject (and the remapper's own) pass straight through. Nothing in
the game changes; it receives its usual keys. Run by `wcmods remap` and `wcmods play`.
"""
import ctypes
import os
import threading
import time
from ctypes import wintypes

from . import keymap

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL, WH_MOUSE_LL, HC_ACTION = 13, 14, 0
WM_QUIT, WM_KEYDOWN, WM_SYSKEYDOWN = 0x12, 0x100, 0x104
WM_XBUTTONDOWN, WM_XBUTTONUP, WM_MOUSEWHEEL = 0x20B, 0x20C, 0x20A
MOUSE_BUTTONS = {0x201: ("LeftMouseButton", True), 0x202: ("LeftMouseButton", False),
                 0x204: ("RightMouseButton", True), 0x205: ("RightMouseButton", False),
                 0x207: ("MiddleMouseButton", True), 0x208: ("MiddleMouseButton", False)}
LLKHF_INJECTED, LLMHF_INJECTED = 0x10, 0x01
INPUT_KEYBOARD, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 1, 0x1, 0x2
MAGIC = 0x57434D52   # "WCMR" in dwExtraInfo marks the remapper's own key presses
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


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


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD))
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def _exe_name(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _window_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, len(buf))
    return buf.value


class Remapper:
    """send: {key you press: game key}; block: game keys to hold back. Key names are Unreal names."""

    def __init__(self, send, block, exe_names, log=print, dry_run=False, in_menus=False, debug=False,
                 state_file=None):
        self.send, self.block = dict(send), set(block)
        self.exe = {n.lower() for n in exe_names}
        self.log, self.dry_run, self.in_menus, self.debug = log, dry_run, in_menus, debug
        self.state_file = state_file
        self.playing = None     # from the play-state file: True, False, or None when there's no file
        self._last_state, self._debug_keys = None, 0
        self.held = {}          # key you're holding -> game key the remapper is holding for it
        self.swallowed = set()  # blocked keys held down, so their release is held back too
        self.used = set()       # remaps already reported once
        self._front = (None, False)
        self._hooks, self._procs, self._thread_id = [], [], None
        self._failed = False

    # ---- when to remap ----
    def _front_window(self):
        """(hwnd, exe name, window class, is the game) for the window in front; cached per window."""
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return (None, "", "", False)
        if hwnd != self._front[0]:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            exe, cls = _exe_name(pid.value), _window_class(hwnd)
            # Unreal's game window class, in case the game's process can't be opened to read its name.
            self._front = (hwnd, exe, cls, exe in self.exe or (not exe and cls == "UnrealWindow"))
        return self._front

    def read_state(self):
        """Read the play-state file (main loop). A half-written file keeps the last state."""
        if not self.state_file:
            return
        try:
            with open(self.state_file, encoding="ascii", errors="replace") as f:
                text = f.read().strip()
        except OSError:
            self.playing = False   # the script is installed but hasn't written yet (the game is starting)
            return
        if text in ("play", "menu"):
            self.playing = text == "play"

    def active(self):
        """The game is in front and, unless in_menus, you're playing rather than in a menu."""
        if not self._front_window()[3]:
            return False
        return self.in_menus or self.playing is not False

    def report_state(self):
        """Debug: log the window in front and the play state whenever they change. Called from the main loop."""
        _, exe, cls, is_game = self._front_window()
        state = (exe, cls, is_game, self.playing)
        if state != self._last_state:
            self._last_state = state
            said = {True: "play", False: "menu", None: "no play-state file"}[self.playing]
            self.log(f"  [debug] front: {exe or '?'} ({cls}) game={is_game}; game says: {said}; "
                     f"remapping {'ON' if self.active() else 'off'}")

    # ---- sending ----
    def _press(self, name, down):
        vk = keymap.VK[name]
        flags = (0 if down else KEYEVENTF_KEYUP) | (KEYEVENTF_EXTENDEDKEY if vk in keymap.EXTENDED else 0)
        event = INPUT(type=INPUT_KEYBOARD)
        event.u.ki = KEYBDINPUT(wVk=vk, wScan=user32.MapVirtualKeyW(vk, 0), dwFlags=flags, time=0,
                                dwExtraInfo=MAGIC)
        user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))

    def _report(self, source, target):
        if source not in self.used:
            self.used.add(source)
            self.log(f"  {source} -> {target}" + (" (dry run: not sent)" if self.dry_run else ""))

    def handle(self, name, down):
        """One key or button event; returns True to hold it back from the game."""
        if not down:
            target = self.held.pop(name, None)
            if target is not None:
                self._press(target, False)   # always, even if the game lost focus meanwhile
                return True
            if name in self.swallowed:
                self.swallowed.discard(name)
                return True
            return False
        if name in self.held:                # the key repeating while held
            self._press(self.held[name], True)
            return True
        if name in self.swallowed:
            return True
        on = self.active()
        if self.debug and self._debug_keys < 40 and (name in self.send or name in self.block):
            self._debug_keys += 1   # only the remapped keys are ever logged
            self.log(f"  [debug] {name} pressed; remapping {'ON' if on else 'off'}")
        if not on:
            return False
        target = self.send.get(name)
        if target is not None:
            self._report(name, target)
            if self.dry_run:
                return False
            self.held[name] = target
            self._press(target, True)
            return True
        if name in self.block:
            self._report(name, "nothing")
            if self.dry_run:
                return False
            self.swallowed.add(name)
            return True
        return False

    def tap(self, name):
        """A wheel notch: press and release the game key it stands for."""
        target = self.send.get(name)
        if target is None or not self.active():
            return False
        self._report(name, target)
        if self.dry_run:
            return False
        self._press(target, True)
        self._press(target, False)
        return True

    def release_all(self):
        for target in self.held.values():
            self._press(target, False)
        self.held.clear()
        self.swallowed.clear()

    # ---- hooks ----
    def _guard(self, fn, n_code, w_param, l_param):
        if n_code == HC_ACTION and not self._failed:
            try:
                if fn(w_param, l_param):
                    return 1
            except Exception as e:   # never let an error eat keys: report once and stop remapping
                self._failed = True
                self.log(f"  remapper error, remapping stopped: {type(e).__name__}: {e}")
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _on_key(self, w_param, l_param):
        k = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if k.flags & LLKHF_INJECTED or k.dwExtraInfo == MAGIC:
            return False
        name = keymap.NAME_OF_VK.get(k.vkCode)
        return name is not None and self.handle(name, w_param in (WM_KEYDOWN, WM_SYSKEYDOWN))

    def _on_mouse(self, w_param, l_param):
        m = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        if m.flags & LLMHF_INJECTED:
            return False
        if w_param in MOUSE_BUTTONS:
            name, down = MOUSE_BUTTONS[w_param]
            return self.handle(name, down)
        if w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP):
            name = "ThumbMouseButton" if (m.mouseData >> 16) == 1 else "ThumbMouseButton2"
            return self.handle(name, w_param == WM_XBUTTONDOWN)
        if w_param == WM_MOUSEWHEEL:
            delta = ctypes.c_short((m.mouseData >> 16) & 0xFFFF).value
            return self.tap("MouseScrollUp" if delta > 0 else "MouseScrollDown")
        return False

    def _install(self):
        hmod = kernel32.GetModuleHandleW(None)
        wanted = [(WH_KEYBOARD_LL, self._on_key)]
        if any(s in keymap.MOUSE for s in self.send):   # a mouse hook sees every movement; only when needed
            wanted.append((WH_MOUSE_LL, self._on_mouse))
        for kind, fn in wanted:
            proc = HOOKPROC(lambda n, w, l, fn=fn: self._guard(fn, n, w, l))
            hook = user32.SetWindowsHookExW(kind, proc, hmod, 0)
            if not hook:
                raise ctypes.WinError(ctypes.get_last_error())
            self._procs.append(proc)   # the callback must outlive the hook
            self._hooks.append(hook)

    def _uninstall(self):
        for hook in self._hooks:
            user32.UnhookWindowsHookEx(hook)
        self._hooks.clear()
        self._procs.clear()

    def run(self, should_stop, poll=0.1):
        """Remap until should_stop() returns True (checked every `poll` seconds) or Ctrl+C."""
        ready, errors = threading.Event(), []

        def loop():
            self._thread_id = kernel32.GetCurrentThreadId()
            try:
                self._install()
            except OSError as e:
                errors.append(e)
                ready.set()
                return
            ready.set()
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass   # the hooks run inside GetMessageW; there's nothing to dispatch
            self._uninstall()

        thread = threading.Thread(target=loop, name="wcmods-remapper", daemon=True)
        thread.start()
        ready.wait(5)
        if errors:
            raise errors[0]
        try:
            while not should_stop():
                self.read_state()
                if self.debug:
                    self.report_state()
                time.sleep(poll)
        finally:
            if self._thread_id:
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            thread.join(5)
            self.release_all()
