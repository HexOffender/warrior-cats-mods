"""What the game left behind when it crashed, and which C++ mod it was in.

Unreal writes each crash to %LOCALAPPDATA%\\Wrc\\Saved\\Crashes\\<id>\\CrashContext.runtime-xml: what went
wrong and the call stack, with the module, function, source file and line of every frame it can name. A C++
mod's DLL is called main.dll (its symbols say `main!`), and its frames name the source file the mod was built
from, which says which mod it is. `python wcmods.py cpp crash` reads the latest.
"""
import os
import re
import xml.etree.ElementTree as ET

FRAME = re.compile(r"^(?P<module>[^!\s]+)!(?P<function>.*?)(?: \[(?P<file>[^\]]+?):(?P<line>\d+)\])?\s*$")


def crashes_dir():
    """Where the game leaves its crash reports; WCMODS_CRASHES stands in for it (the tests' own folder)."""
    if os.environ.get("WCMODS_CRASHES"):
        return os.environ["WCMODS_CRASHES"]
    base = os.environ.get("LOCALAPPDATA") or ""
    return os.path.join(base, "Wrc", "Saved", "Crashes")


def latest(after=None):
    """The newest crash folder (its CrashContext.runtime-xml), or None; with `after` (a time), only one newer."""
    folder = crashes_dir()
    try:
        names = os.listdir(folder)
    except OSError:   # not there (no crash yet), or not readable this moment
        return None
    best, best_time = None, after or 0
    for name in names:
        path = os.path.join(folder, name, "CrashContext.runtime-xml")
        try:
            when = os.path.getmtime(path)
        except OSError:   # no report in it, or one removed as it's read
            continue
        if when > best_time:
            best, best_time = path, when
    return best


def parse(text):
    """A crash context's contents: {"type", "error", "frames": [{module, function, file, line, text}]}."""
    root = ET.fromstring(text)
    out = {"type": "", "error": "", "frames": []}
    for tag, key in (("CrashType", "type"), ("ErrorMessage", "error")):
        node = root.find(f".//RuntimeProperties/{tag}")
        if node is not None and node.text:
            out[key] = node.text.strip()
    stack = root.find(".//RuntimeProperties/CallStack")
    for line in (stack.text or "").splitlines() if stack is not None else []:
        line = line.strip()
        if not line:
            continue
        m = FRAME.match(line)
        frame = {"module": "", "function": line, "file": None, "line": None, "text": line}
        if m:
            frame.update(module=m.group("module"), function=m.group("function").strip(), file=m.group("file"),
                         line=int(m.group("line")) if m.group("line") else None)
        out["frames"].append(frame)
    return out


def _under(path, folder):
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(folder)]) == os.path.abspath(folder)
    except ValueError:   # different drives
        return False


def blame(crash, mods, sdk_dir):
    """Which C++ mod a crash was in: the first frame whose source file is in a mod's folder, as
    {"mod": id, "file", "line", "function", "sdk": whether the frame is in wcmods' SDK headers}; the first
    frame in the SDK's headers when no mod's own code is on the stack; None when no C++ mod is on it."""
    first_sdk = None
    for f in crash["frames"]:
        if not f["file"]:
            continue
        for mod in mods:
            if _under(f["file"], mod.folder):
                return {"mod": mod.id, "file": os.path.relpath(f["file"], mod.folder).replace(os.sep, "/"), "line": f["line"],
                        "function": f["function"], "sdk": False}
        if first_sdk is None and sdk_dir and _under(f["file"], sdk_dir):
            first_sdk = {"mod": None, "file": os.path.relpath(f["file"], sdk_dir).replace(os.sep, "/"), "line": f["line"],
                         "function": f["function"], "sdk": True}
    if first_sdk:
        # The SDK's code ran for some mod: the nearest frame in a main.dll says which, when the DLL is named.
        return first_sdk
    return None


UNREADABLE = "the crash report couldn't be read"


def read(path):
    """A crash file's crash (parse), its text decoded by its byte-order mark: UTF-16 (as Unreal often writes
    it), UTF-8, else the Windows code page. ValueError (UNREADABLE) when it isn't a crash context at all."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16", errors="replace")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
    try:
        return parse(text)
    except ET.ParseError:
        raise ValueError(UNREADABLE) from None


def summary(path, mods, sdk_dir):
    """A crash for the studio's card: {"when" (ISO time), "message", "mod" (the C++ mod it was in, or None),
    "mod_name", "where" (a sentence on where in it, or None), "readout" (readout()'s lines, to copy), "path"}."""
    import datetime
    when = datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="minutes")
    try:
        crash = read(path)
    except ValueError as e:
        return {"when": when, "message": str(e), "mod": None, "mod_name": None, "where": None, "readout": f"{e}\n  {path}",
                "path": path}
    who = blame(crash, mods, sdk_dir)
    names = {m.id: m.name for m in mods}
    mod = who["mod"] if who and who["mod"] else None
    where = (f"{who['file']}:{who['line']}, {who['function']}" if who and who["mod"]
             else "wcmods' C++ SDK, called by a C++ mod" if who else None)
    return {"when": when, "message": crash["error"] or crash["type"] or "no message", "mod": mod,
            "mod_name": names.get(mod, mod) if mod else None, "where": where, "readout": readout(path, mods, sdk_dir),
            "path": path}


def readout(path, mods, sdk_dir):
    """A few lines about a crash file: when, what, and which C++ mod, for people."""
    import datetime
    try:
        crash = read(path)
    except ValueError as e:
        return f"{e}\n  {path}"
    when = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"the game crashed at {when}: {crash['error'] or crash['type'] or 'no message'}"]
    who = blame(crash, mods, sdk_dir)
    if who and who["mod"]:
        lines.append(f"  in the C++ mod {who['mod']}: {who['file']}:{who['line']}, {who['function']}")
    elif who:
        lines.append(f"  in wcmods' C++ SDK ({who['file']}:{who['line']}, {who['function']}), called by a C++ mod")
    main_frames = [f for f in crash["frames"] if f["module"] == "main"]
    if not who and main_frames and main_frames[0]["file"]:
        # Symbols name the source, but it's no mod of this folder's (another checkout, say).
        lines.append(f"  in a C++ mod built from {main_frames[0]['file']}:{main_frames[0]['line']} ({main_frames[0]['function']}), "
                     f"not one of the mods here")
    elif not who and main_frames:
        lines.append(f"  in a C++ mod's main.dll ({main_frames[0]['function']}); built without symbols, so no file")
    elif not who:
        lines.append("  no C++ mod on the stack (the game's own code, or a Lua script's)")
    for f in crash["frames"][:8]:
        lines.append("    " + f["text"][:160])
    lines.append(f"  {path}")
    return "\n".join(lines)
