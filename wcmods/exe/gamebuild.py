"""Which build of the game is installed, and how wcmods and the mods stand on it.

Steam keeps the game up to date by itself, so a player can have a newer build than wcmods, or a mod,
was made for. This module tells which build is installed (Steam's appmanifest) and what follows:

- wcmods' own parts: on VERIFIED_BUILD, the one game.HIDDEN's offsets were confirmed on, nothing
  changes. On another, signatures.check() looks for what the update moved and the in-game module gets
  the offsets it found; members it can't find again, or can't vouch for, are left out rather than
  guessed. The answer is kept in cache/layout-<key>.json, so it's worked out once per game update.
- mods: each says in mod.json which builds it was made for ("game_builds"). One that doesn't list the
  installed build is "made for an older version" and stays out of the game until it's updated, or the
  player chooses to use it anyway on this build (wcmods.json "allow_outdated"), with a warning that it
  may not work or may behave unpredictably. So do the mods that need it. A mod that says nothing was
  made for build 24847281, as every mod before this was.
- the re-check (recheck): a held-back mod that is only data (no code, no paks/ or files/, not a pack) is
  built on the new game instead of being held back on trust. One that builds is stamped with the new build
  in its mod.json and goes in; one that fails stays held back with the reason. What came of it is kept in
  wcmods.json "rechecked", so each mod is checked once per build; while the game's files can't be read,
  nothing is checked and it's tried again next time.
"""
import hashlib
import json
import os
import re

from . import pe

# The build game.HIDDEN's offsets were confirmed on. HIDDEN holds one layout, so this is one build: after
# checking a new one, update HIDDEN to it and put its number here.
VERIFIED_BUILD = 26184573
VERIFIED_LABEL = "patch 1.1, October 2026"
# What a mod.json without "game_builds" was made for: the build every mod before them was made on.
ASSUMED_BUILDS = (24847281,)
CACHE_DIR = "cache"


def steam_build(cfg):
    """The build Steam has installed (its appmanifest's "buildid"), or None. WCMODS_GAME_BUILD, when set,
    stands in for it: for trying what a game update does without one."""
    if os.environ.get("WCMODS_GAME_BUILD", "").isdigit():
        return int(os.environ["WCMODS_GAME_BUILD"])
    if not cfg.game_dir:
        return None
    from ..config import STEAM_APP_ID
    steamapps = os.path.dirname(os.path.dirname(os.path.normpath(cfg.game_dir)))   # <lib>\steamapps
    path = os.path.join(steamapps, f"appmanifest_{STEAM_APP_ID}.acf")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            m = re.search(r'"buildid"\s+"(\d+)"', f.read())
    except OSError:
        return None
    return int(m.group(1)) if m else None


def current(cfg):
    """{"build" (None when unknown), "verified", "label"}: the installed build."""
    build = steam_build(cfg)
    verified = build == VERIFIED_BUILD
    return {"build": build, "verified": verified, "label": VERIFIED_LABEL if verified else None}


def _build(v):
    """One build number: a whole number, a whole float (26184573.0) or digits as text ("26184573"); else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def _builds(v):
    """A list of build numbers from mod.json or wcmods.json: a number, or a list of them (as _build reads each)."""
    v = v if isinstance(v, list) else [v]
    return [b for b in (_build(x) for x in v) if b is not None]


BUILDS_PROBLEM = "mod.json's game_builds should be a list of build numbers like [26184573]"


def builds_problem(mod):
    """What's wrong with a mod's "game_builds" when it's there but holds no build number, or None."""
    for key in ("game_builds", "game_build"):
        if key in mod.meta:
            return None if _builds(mod.meta[key]) else BUILDS_PROBLEM
    return None


def made_for(mod):
    """The builds a mod says it was made for (mod.json "game_builds"), or the assumed ones."""
    return _builds(mod.meta.get("game_builds", mod.meta.get("game_build"))) or list(ASSUMED_BUILDS)


def _allowed_table(cfg):
    table = cfg.data.get("allow_outdated")
    return table if isinstance(table, dict) else {}


def allowed(cfg, mod_id, build):
    """Whether the player chose to use a mod made for an older version on this build."""
    return build in _builds(_allowed_table(cfg).get(mod_id))


def allow(cfg, mod_id, build, on=True):
    """Use (or stop using) a mod made for an older version, on this build only."""
    cfg.reload()
    table = dict(_allowed_table(cfg))
    builds = [b for b in _builds(table.get(mod_id)) if b != build]
    if on:
        builds.append(build)
    if builds:
        table[mod_id] = builds
    else:
        table.pop(mod_id, None)
    cfg.data["allow_outdated"] = table
    cfg.save()


def outdated(cfg, mods, build=None):
    """{mod id: {"made_for", "allowed"}} for the mods that are on and weren't made for the installed build."""
    build = build if build is not None else steam_build(cfg)
    if build is None:
        return {}
    out = {}
    for m in mods:
        if not m.enabled or m.meta.get("pack"):   # a mod pack has nothing of the game's in it to go out of date
            continue
        builds = made_for(m)
        if build not in builds:
            out[m.id] = {"made_for": builds, "allowed": allowed(cfg, m.id, build)}
    return out


def held_back(cfg, mods, build=None, trusted=()):
    """{mod id: why} for the mods a build leaves out on this version of the game: the ones made for an
    older version (unless used anyway, or `trusted`: the re-check's own build), and the ones that need them,
    which can't work without them. One the re-check built and saw fail says why."""
    from .. import mods as modlib
    build = build if build is not None else steam_build(cfg)
    found = checked(cfg, build) if build is not None else {}
    base = {}
    for i, o in outdated(cfg, mods, build).items():
        if o["allowed"] or i in trusted:
            continue
        why = found.get(i)
        base[i] = (f"made for an older version of the game, and checked on this one: {why}"
                   if why and why != "ok" and not str(why).startswith(COULDNT) else "made for an older version of the game")
    return modlib.with_dependents(mods, base, "made for an older version of the game")


# ---------- the re-check: data mods built on the new game instead of held back on trust ----------
COULDNT = "couldn't check"
COULDNT_READ = f"{COULDNT}: the game's files can't be read right now"


def checkable(mod):
    """Whether building a mod on the new game says whether it still works: it's only data. Code (scripts,
    C++, build steps) can't be judged by a build; neither can cooked content (paks/) or replaced game
    files (files/), which the build copies as they are; a pack has nothing of its own."""
    kinds = set(mod.kinds())
    return not (mod.problem or mod.has_code() or mod.meta.get("pack") or kinds & {"files", "cooked content"})


def checked(cfg, build):
    """What the re-check found on `build` (wcmods.json "rechecked"): {mod id: "ok", or why it didn't build},
    {} when it hasn't run on that build."""
    rec = cfg.data.get("rechecked")
    if isinstance(rec, dict) and rec.get("build") == build and isinstance(rec.get("results"), dict):
        return rec["results"]
    return {}


def candidates(cfg, mods, build=None):
    """The held-back mods a re-check can judge (checkable), on `build` (the installed one unless given)."""
    build = build if build is not None else steam_build(cfg)
    by_id = {m.id: m for m in mods}
    return [i for i, o in outdated(cfg, mods, build).items() if not o["allowed"] and checkable(by_id[i])]


def recheck_due(cfg, mods, build=None):
    """Whether a re-check has something to do: a candidate it hasn't checked on this build, or one it
    couldn't (the game's files couldn't be read)."""
    build = build if build is not None else steam_build(cfg)
    if build is None:
        return False
    found = checked(cfg, build)
    return any(i not in found or str(found[i]).startswith(COULDNT) for i in candidates(cfg, mods, build))


def _failures(manifest, ids):
    """{mod id: what went wrong} for the mods in `ids` that a build's manifest says didn't make it: named in
    a section's failures, or in a section whose table edits or rows couldn't go in."""
    out = {}
    for rep in manifest.get("sections", {}).values():
        for mod, text in rep.get("failed") or []:
            if mod in ids:
                out.setdefault(mod, text)
        lost = [e for e in rep.get("errors", []) if "edits not applied" in e or "rows not added" in e]
        for mod in rep.get("mods", []) if lost else []:
            if mod in ids:
                out.setdefault(mod, lost[0])
    return out


def recheck(cfg, mods, build_dir, log=print):
    """Build the held-back data mods (candidates) on the installed game, in a folder beside the real build
    (`build_dir`-check, removed after), counting them as allowed for that build alone. One that builds gets
    the build added to its mod.json "game_builds" and goes in from now on; one that doesn't stays held back,
    with what went wrong. While the game's files can't be read, nothing is built: each gets COULDNT_READ and
    is tried again next time. Each mod is checked once per build; the answers are kept in wcmods.json
    "rechecked" ({"build", "when", "results"}). Returns the results."""
    import datetime
    import shutil
    from .. import gamefiles, pipeline
    build = steam_build(cfg)
    if build is None:
        return {}
    cfg.reload()
    found = dict(checked(cfg, build))
    todo = [i for i in candidates(cfg, mods, build) if i not in found or str(found[i]).startswith(COULDNT)]
    if not todo:
        return found
    names = {m.id: m.name for m in mods}
    why = gamefiles.unreadable(cfg)
    if why:
        log(f"couldn't check {', '.join(names[i] for i in todo)} on build {build}: {why}")
        found.update({i: COULDNT_READ for i in todo})
    else:
        log(f"checking {', '.join(names[i] for i in todo)} on build {build}")
        out = os.path.normpath(build_dir) + "-check"
        try:
            manifest = pipeline.build(cfg, mods, out, log=lambda m: log("  " + m), trusted=todo)
        finally:
            shutil.rmtree(out, ignore_errors=True)
        failed = _failures(manifest, todo)
        by_id = {m.id: m for m in mods}
        for i in todo:
            if i in failed:
                found[i] = failed[i]
                log(f"{names[i]}: didn't build on build {build}: {failed[i]}")
            else:
                by_id[i].update(game_builds=made_for(by_id[i]) + [build])
                found[i] = "ok"
                log(f"{names[i]}: checked on build {build}: fine")
    cfg.reload()
    cfg.data["rechecked"] = {"build": build, "when": datetime.datetime.now().isoformat(timespec="seconds"),
                             "results": found}
    cfg.save()
    return found


# ---------- wcmods' own parts on a new build ----------
def _members():
    """Every member game.HIDDEN reads, as "class:name"."""
    from .. import game
    return [f"{cls}:{name}" for cls, fields in game.HIDDEN for name, _, _ in fields]


def _version():
    """What wcmods knows of the game's layout: game.HIDDEN and signatures.json. A layout worked out with
    other ones is worked out again."""
    from .. import game
    from . import signatures
    h = hashlib.sha1(repr(game.HIDDEN).encode())
    try:
        with open(signatures.DATA, "rb") as f:
            h.update(f.read())
    except OSError:
        pass
    return h.hexdigest()[:12]


def layout_key(cfg):
    """What a layout is worked out for: the build, the exe (size and time), and _version(); None with no
    exe. The install records it, so a change asks for another install."""
    exe = pe.game_exe(cfg)
    if not exe:
        return None
    st = os.stat(exe)
    return f"{steam_build(cfg) or 'unknown'}-{st.st_size:x}-{int(st.st_mtime):x}-{_version()}"


def _cache_path(cfg, key):
    return os.path.join(cfg.root, CACHE_DIR, f"layout-{key}.json")


def _all_off(build, status, why=None):
    off = _members()
    return {"build": build, "status": status, "offsets": {k: None for k in off}, "moved": [], "lost": off,
            "why": why}


def layout(cfg, log=print, refresh=False):
    """How wcmods' in-game members stand on the installed game: {"build", "status", "offsets", "moved",
    "lost"}. status:
    - "verified": VERIFIED_BUILD; offsets None, so game.HIDDEN as it is;
    - "adapted": another build, every member found again (moved or not);
    - "partial": some couldn't be, or couldn't be vouched for: they're None in offsets and left out;
    - "unknown": no exe to read, so every member is left out.
    A member the signatures don't cover is left out too. Nothing here stops a build: a check that fails
    leaves everything out (and is tried again next time)."""
    info = current(cfg)
    if info["verified"]:
        return {"build": info["build"], "status": "verified", "offsets": None, "moved": [], "lost": []}
    key = layout_key(cfg)
    if not key:
        return _all_off(info["build"], "unknown", "no game exe to read")
    path = _cache_path(cfg, key)
    if not refresh:
        try:
            with open(path, encoding="utf-8") as f:
                cached = json.load(f)
            if isinstance(cached, dict) and isinstance(cached.get("offsets"), dict):
                return cached
        except (OSError, ValueError):   # not worked out yet, or cut short while it was written
            pass
    from . import signatures
    log(f"  the game updated (build {info['build'] or 'unknown'}): looking for what moved, once (under a minute)")
    try:
        res = signatures.check(pe.game_exe(cfg), log=lambda m: log("  " + m))
    except Exception as e:   # an exe laid out unlike any wcmods knows, or no signatures.json
        log(f"  couldn't read the new exe ({type(e).__name__}: {e}); wcmods' own values stay off")
        return _all_off(info["build"], "partial", f"{type(e).__name__}: {e}")
    status = {f"{c}:{n}": f["status"] for c, rep in res["classes"].items() for n, f in rep["fields"].items()}
    offsets = {k: res["offsets"].get(k) for k in _members()}
    moved = [k for k in offsets if status.get(k) == "moved"]
    lost = [k for k, v in offsets.items() if v is None]
    out = {"build": info["build"], "status": "partial" if lost else "adapted", "offsets": offsets,
           "moved": moved, "lost": lost}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    os.replace(tmp, path)   # whole or not at all: a half-written cache is never read
    return out


def describe(key):
    """"/Script/SwtQuest.SwtQuestResourceComponent:WCM_Value" as "SwtQuestResourceComponent.Value"."""
    cls, _, name = key.partition(":")
    return f"{cls.rsplit('.', 1)[-1]}.{name.replace('WCM_', '')}"
