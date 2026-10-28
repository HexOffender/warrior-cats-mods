"""What the game's last run said about each script mod, read from UE4SS's log (UE4SS.log, beside its Mods folder):
whether its script started and loaded, its errors, and what it printed. The studio shows it on the mod's card
("Loaded when the game last started", or why it didn't), with the lines under More.

    report = scriptlog.report(cfg, mods)
    report["mods"]["game-tweaks"]   # {"started", "loaded", "errors", "lines", "state", "said", ...}

UE4SS starts a new log each time the game starts, so the file is one session. Its lines look like this (UE4SS
3.0.1, the one Get set up installs; a line it doesn't recognise is left out, not misread):

    [2026-10-27 23:46:34.1656879] Starting Lua mod 'WCModsScript_game_tweaks'
    [2026-10-27 23:46:34.2100175] [Lua] [Game Tweaks] loaded

A script's own lines carry its mod's name (MOD.log, and WCModsGame's messages once the script bootstrap names
the mod); a plain print() while the script starts belongs to the mod UE4SS is starting then. A message of
several lines (an error with its stack traceback) goes on without the time on its next lines.
"""
import datetime
import os
import re

HEAD = 512 * 1024        # UE4SS's own lines about starting the mods are near the top
TAIL = 2 * 1024 ** 2     # a mod's own lines, read from the end
SHOWN = 30               # the lines kept for each mod, newest first

# A line in UE4SS.log that says a script went wrong. The agent's in-game tests look for these too; here they're
# looked for only in a mod's own lines, so UE4SS's start-up dump ("FArchiveState::ArIsError = 0x29") never counts.
ERROR_LINE = re.compile(r"\berror\b|stack traceback|attempt to (call|index|perform|compare|concatenate)", re.I)
STAMP = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)(?:\.\d+)?\] ?(.*)$")
STARTING = re.compile(r"^Starting Lua mod '([^']+)'")
STARTS_END = ("Starting mods", "Event loop start")    # UE4SS done starting one mod's script, and on to others
LUA = re.compile(r"^\[Lua\] ?(.*)$", re.S)              # (a message may go on over several lines)
NAMED = re.compile(r"^\[([^\]\n]+)\] (.*)$", re.S)       # "[Mod name] text"
# How the script bootstrap (lua/script_bootstrap.lua) says a script didn't load: "can't load: <error>" (and
# "can't load scripts/main.lua: <error>" before wcmods named the files itself), or "error: <error>" when its
# main.lua stopped with an error.
LOAD_FAILED = re.compile(r"^(?:can't load(?: scripts/main\.lua)?|error): (.*)$", re.S)
MORE = re.compile(r" \(\d+ more\)$")   # "... (1812 more)": an error said again (game.lua's failed())
RUNTIME = re.compile(r"^error in ")    # how WCModsGame starts a timer's, key's or hook's error (failed())

# What the card says, by state.
SAID = {
    "loaded": "Loaded when the game last started",
    "errors": "Loaded when the game last started, then hit an error: {error}",
    "failed": "Didn't load when the game last started: {error}",
    "not-started": "Didn't start when the game last started (the script loader didn't run it)",
    "waiting": "Hasn't run since you applied",
}

_cache = {}   # (path, size, mtime) -> what read() found


def log_path(cfg):
    """Where UE4SS.log is (or will be, once the game has run with UE4SS), or None without a game folder."""
    from . import ue4ss
    try:
        win64 = cfg.win64_dir
    except Exception:   # no game found
        return None
    if not win64:
        return None
    return ue4ss.log_path(win64) or os.path.join(win64, "ue4ss", "UE4SS.log")


def _text(path):
    """The log's head and tail as text (the whole file when it's small): (head, tail), tail None when it's all
    in head. A tail's first line, cut in half, is left out."""
    with open(path, "rb") as f:
        size = f.seek(0, 2)
        f.seek(0)
        if size <= HEAD + TAIL:
            return f.read().decode("utf-8", "replace").lstrip("\ufeff"), None
        head = f.read(HEAD)
        f.seek(size - TAIL)
        tail = f.read()
    head = head.decode("utf-8", "replace").lstrip("\ufeff")
    tail = tail.decode("utf-8", "replace")
    return head[:head.rfind("\n") + 1], tail[tail.find("\n") + 1:]


def _entries(text):
    """The log's entries in order: (time, text), a message of several lines joined with "\n"."""
    out = []
    for line in text.splitlines():
        m = STAMP.match(line)
        if m:
            out.append([m.group(1), m.group(2)])
        elif out and line.strip():
            out[-1][1] += "\n" + line
    return [tuple(e) for e in out]


def read(path):
    """What a log says: {"session" (its first time), "started" (the UE4SS mods it started, in order), "lines"
    ({name: [(time, text)]}: each name's own lines, by the name they carry, or by the UE4SS mod being started
    for a plain print as it starts)}. None when there's no log."""
    try:
        st = os.stat(path)
    except (OSError, TypeError):
        return None
    key = (path, st.st_size, st.st_mtime_ns)
    hit = _cache.get(key)   # (the studio answers on several threads: one may be clearing it)
    if hit is not None:
        return hit
    try:
        head, tail = _text(path)
    except OSError:
        return None
    found = {"session": None, "started": [], "lines": {}, "by_mod": {}}

    def take(entries):
        starting = None
        for when, text in entries:
            if found["session"] is None:
                found["session"] = when
            m = STARTING.match(text)
            if m:
                starting = m.group(1)
                if starting not in found["started"]:
                    found["started"].append(starting)
                continue
            if text.startswith(STARTS_END):
                starting = None
                continue
            m = LUA.match(text)
            if not m:
                continue
            said = m.group(1)
            named = NAMED.match(said)
            if named:
                found["lines"].setdefault(named.group(1), []).append((when, named.group(2)))
            elif starting:
                found["by_mod"].setdefault(starting, []).append((when, said))

    take(_entries(head))
    if tail is not None:
        take(_entries(tail))
    _cache.clear()   # one log at a time
    _cache[key] = found
    return found


def _installed(cfg):
    try:
        data = cfg.peek()
    except (OSError, ValueError, AttributeError):
        data = cfg.data
    return data.get("installed") or {}, set(data.get("installed_ue4ss") or [])


def _when(text):
    try:
        return datetime.datetime.fromisoformat(str(text).replace("T", " "))
    except ValueError:
        return None


def mod_report(found, mod, ue4ss_name, installed, run_since_apply):
    """One script mod's part of the report (see report)."""
    own = list(found["lines"].get(mod.name, [])) if found else []
    if found:   # a plain print while its script started counts as its own
        own = sorted(own + found["by_mod"].get(ue4ss_name, []), key=lambda e: e[0])
    started = bool(found) and ue4ss_name in found["started"]
    errors, failed = [], []
    for _, text in own:
        # The first line of each; the count WCModsGame adds when it says an error again a minute later is left
        # off, so it's one error.
        first = MORE.sub("", text.split("\n", 1)[0].strip())
        m = LOAD_FAILED.match(first)
        if m:
            failed.append(m.group(1).strip())
        elif ERROR_LINE.search(first):
            errors.append(RUNTIME.sub("", first))
    errors = failed + [e for e in errors if e not in failed]
    out = {"installed": installed, "started": started, "loaded": started and not failed,
           "errors": list(dict.fromkeys(errors))[:10],
           "lines": [f"{when[11:]}  {text}" for when, text in reversed(own[-SHOWN:])]}
    if not installed:
        out["state"] = None
    elif not run_since_apply:
        out["state"] = "waiting"
    elif not started:
        out["state"] = "not-started"
    elif failed:
        out["state"] = "failed"
    elif errors:
        out["state"] = "errors"
    else:
        out["state"] = "loaded"
    out["said"] = SAID[out["state"]].format(error=out["errors"][0] if out["errors"] else "") if out["state"] else None
    return out


def report(cfg, mods):
    """What the game's last run said about each script mod in `mods` (those with scripts/):
    {"log": UE4SS.log's path or None, "session": when the game last started (local time, as the log says) or
    None, "run_since_apply": whether that was after the last install, "mods": {id: {"installed" (its script went
    in with the last install), "started", "loaded", "errors" (first lines, load failures first), "lines" (its
    own, newest first, with their times), "state" (None when it wasn't installed, else "loaded", "errors",
    "failed", "not-started" or "waiting"), "said" (the state in a sentence)}}}."""
    from .sections import scripts
    path = log_path(cfg)
    found = read(path) if path else None
    inst, ue4ss_mods = _installed(cfg)
    built, session = _when(inst.get("built", "")), _when(found["session"]) if found and found["session"] else None
    since = bool(found and session and built and session >= built)
    out = {"log": path if found else None, "session": found["session"] if found else None, "run_since_apply": since,
           "mods": {}}
    for m in mods:
        if not scripts.has_scripts(m):
            continue
        name = scripts.ue4ss_name(m.id)
        out["mods"][m.id] = mod_report(found, m, name, name in ue4ss_mods, since)
    return out
