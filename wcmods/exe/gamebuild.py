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
  built on the new game, with the mods it needs and no others, instead of being held back on trust. One
  that builds without a failure of its own or of a section it's in is stamped with the new build in its
  mod.json and goes in; one that fails stays held back with the reason. What came of it is kept in
  wcmods.json "rechecked", with each mod's signature, so a mod is checked once per build and again when it
  changes; while the game's files can't be read, nothing is checked and it's tried again next time.
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
UNREADABLE = "the game's files can't be read"   # how gamefiles.Unreadable starts


def checkable(mod):
    """Whether building a mod on the new game says whether it still works: it's only data (palettes, controls,
    mouse look, game data, items, animations, names, your cat's colours, save edits, characters, questlines).
    Code (scripts, C++, build steps) can't be judged by a build; neither can cooked content (paks/) or
    replaced game files (files/), which the build copies as they are; a pack has nothing of its own. Items
    with accessories or models, and animations, patch the game's cooked assets: that they build is as far as
    a check goes."""
    kinds = set(mod.kinds())
    return not (mod.problem or mod.has_code() or mod.meta.get("pack") or kinds & {"files", "cooked content"})


def _record(cfg, build):
    rec = cfg.data.get("rechecked")
    if isinstance(rec, dict) and rec.get("build") == build and isinstance(rec.get("results"), dict):
        return rec
    return {}


def checked(cfg, build):
    """What the re-check found on `build` (wcmods.json "rechecked"): {mod id: "ok", or why it didn't build},
    {} when it hasn't run on that build."""
    return _record(cfg, build).get("results", {})


def check_warnings(cfg, build):
    """What the re-check's build warned about each mod it checked on `build`: {mod id: [warnings]}."""
    w = _record(cfg, build).get("warnings")
    return w if isinstance(w, dict) else {}


def signature(mod):
    """What tells a mod changed since it was checked: its version, and how many files it has, their total
    size and the newest one's time (mod.json aside: the check's own stamp and switching it on or off write
    that)."""
    count = size = newest = 0
    for folder, dirs, files in os.walk(mod.folder):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for name in files:
            if folder == mod.folder and name == "mod.json":
                continue
            try:
                st = os.stat(os.path.join(folder, name))
            except OSError:
                continue
            count, size, newest = count + 1, size + st.st_size, max(newest, st.st_mtime_ns)
    return f"{mod.version}|{count}|{size}|{newest}"


def candidates(cfg, mods, build=None):
    """The held-back mods a re-check can judge (checkable), on `build` (the installed one unless given), that a
    build could put in: none that needs a newer Clan Mod Studio, or a mod that's missing, off, or held back
    without being a candidate itself (a story needing Sandbox mode, made for the older version: the story
    waits for it)."""
    from .. import mods as modlib
    build = build if build is not None else steam_build(cfg)
    by_id = {m.id: m for m in mods}
    old = outdated(cfg, mods, build)
    too_new = modlib.too_new(mods)
    keep = {i for i, o in old.items() if not o["allowed"] and checkable(by_id[i]) and i not in too_new}
    while True:
        def buildable(i):
            for r in modlib.needed(mods, i):
                m = by_id.get(r)
                if m is None or not m.enabled or r in too_new or (r in old and not old[r]["allowed"] and r not in keep):
                    return False
            return True
        fewer = {i for i in keep if buildable(i)}
        if fewer == keep:
            break
        keep = fewer
    return [i for i in old if i in keep]


def _due(cfg, mods, build):
    """The candidates to check now: never checked on this build, checked while the game's files couldn't be
    read, or changed since (signature)."""
    rec = _record(cfg, build)
    found, sigs = rec.get("results", {}), rec.get("signatures") if isinstance(rec.get("signatures"), dict) else {}
    by_id = {m.id: m for m in mods}
    return [i for i in candidates(cfg, mods, build)
            if i not in found or str(found[i]).startswith(COULDNT_READ) or sigs.get(i) != signature(by_id[i])]


def recheck_due(cfg, mods, build=None):
    """Whether a re-check has something to do (_due)."""
    build = build if build is not None else steam_build(cfg)
    return build is not None and bool(_due(cfg, mods, build))


def _verdict(mod_id, manifest):
    """What a check build's manifest says of one candidate it built: "ok", or why not. Its own failure in any
    section; else a failure of a section it's in that isn't another mod's (the section failing as a whole,
    or a file whose edits were its own, the section's "blame"); a file whose editors can't be told is
    "couldn't check"; the game's files unreadable midway is COULDNT_READ, tried again. A save edit its save
    has no place for ("skipped") fails it too."""
    sections = list(manifest.get("sections", {}).values())
    for rep in sections:
        for mod, text in rep.get("failed") or []:
            if mod == mod_id:
                return COULDNT_READ if UNREADABLE in str(text) else text
    for rep in sections:
        if mod_id not in rep.get("mods", []):
            continue
        blame = rep.get("blame") or {}
        for mod, text in rep.get("failed") or []:
            if mod is not None:
                continue
            if UNREADABLE in str(text):
                return COULDNT_READ
            if text in blame:
                if mod_id in blame[text]:
                    return text
                if not blame[text]:
                    return f"{COULDNT}: {text}"
                continue   # another mod's edit to a file this one doesn't touch
            return text   # the section failed as a whole
        if rep.get("status") == "failed":
            return f"{rep.get('title', 'a part of the build')} didn't build"
    for w in manifest.get("warnings", []):
        if str(w).startswith(f"{mod_id}: ") and str(w).endswith("; skipped"):
            return str(w)[len(mod_id) + 2:]
    return "ok"


def _warned(manifest, mod):
    """The check build's warnings about one mod: those that start with its id or name."""
    return [w for w in manifest.get("warnings", [])
            if str(w).startswith((f"{mod.id}:", f"{mod.name}:", f"{mod.id} ", f"{mod.name} "))]


def _stamp(mod, build):
    """Add `build` to the mod's mod.json "game_builds", written whole (a temp file, then a replace), so a
    studio and `wcmods game build` at the same time can't leave half a file."""
    path = os.path.join(mod.folder, "mod.json")
    with open(path, encoding="utf-8-sig") as f:
        meta = json.load(f)
    if not isinstance(meta, dict):
        raise ValueError("mod.json should hold an object")
    meta["game_builds"] = made_for(mod) + [build]
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    mod.__init__(mod.folder)


def recheck(cfg, mods, build_dir, log=print):
    """Build the held-back data mods that are due (_due) on the installed game, with the mods they need and
    nothing else, in a folder beside the real build (`build_dir`-check, removed after), counting them as
    allowed for that build alone. One that builds (_verdict) gets the build added to its mod.json
    "game_builds" and goes in from now on; one that doesn't stays held back, with what went wrong, until it
    changes. While the game's files can't be read, nothing is built: each gets COULDNT_READ and is tried again
    next time. The answers are kept in wcmods.json "rechecked" ({"build", "when", "results", "signatures",
    "warnings"}). Returns the results."""
    import datetime
    import shutil
    from .. import gamefiles, pipeline
    from .. import mods as modlib
    build = steam_build(cfg)
    if build is None:
        return {}
    cfg.reload()
    rec = _record(cfg, build)
    found = dict(rec.get("results", {}))
    sigs = dict(rec.get("signatures") or {})
    warned = dict(rec.get("warnings") or {})
    todo = _due(cfg, mods, build)
    if not todo:
        return found
    by_id = {m.id: m for m in mods}
    names = {m.id: m.name for m in mods}
    why = gamefiles.unreadable(cfg)
    if why:
        log(f"couldn't check {', '.join(names[i] for i in todo)} on build {build}: {why}")
        found.update({i: COULDNT_READ for i in todo})
    else:
        log(f"checking {', '.join(names[i] for i in todo)} on build {build}")
        # Only the mods being checked and what they need: nobody else's section.py runs for it.
        wanted = set(todo) | {r for i in todo for r in modlib.needed(mods, i)}
        out = os.path.normpath(build_dir) + "-check"
        try:
            manifest = pipeline.build(cfg, [m for m in mods if m.id in wanted], out, log=lambda m: log("  " + m),
                                      trusted=todo)
        finally:
            shutil.rmtree(out, ignore_errors=True)
        built = set(manifest.get("mods", [])) - set(manifest.get("left_out") or {})
        for i in todo:
            if i not in built:   # left out for a reason of its own: no answer, and no stamp
                found.pop(i, None)
                sigs.pop(i, None)
                log(f"{names[i]}: not checked: the check's build left it out")
                continue
            verdict = _verdict(i, manifest)
            warned[i] = _warned(manifest, by_id[i])
            if verdict == "ok":
                try:
                    _stamp(by_id[i], build)
                except (OSError, ValueError) as e:   # the others go on; this one is tried again next time
                    found.pop(i, None)
                    sigs.pop(i, None)
                    log(f"{names[i]}: built on build {build}, but its mod.json couldn't be noted ({e})")
                    continue
                log(f"{names[i]}: checked on build {build}: fine")
            else:
                log(f"{names[i]}: didn't build on build {build}: {verdict}")
            found[i] = verdict
            sigs[i] = signature(by_id[i])
    cfg.reload()
    cfg.data["rechecked"] = {"build": build, "when": datetime.datetime.now().isoformat(timespec="seconds"),
                             "results": found, "signatures": sigs, "warnings": warned}
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


# What the members of each class in game.HIDDEN are, in a player's words: what the Apply warning, `wcmods
# game build` and the Mods page's banner say a game update moved or switched off.
PLAIN = {
    "SwtQuestResourceComponent": "your cat's health, stamina and experience, and the fresh-kill pile",
    "SwtQuestStaminaComponent": "how fast your cat's stamina comes back",
    "SwtAdventureLevelComponent": "your cat's level and stats",
    "SwtAdventureFreshKillPileComponent": "the fresh-kill pile's timer",
    "SwtAdventureGameplayGameState": "the time of day",
    "TurnBasedCombatComponent": "the fighters' stats, moves and sides in a fight",
    "SwtAdventureStatusComponent": "poison and the other status conditions",
    "SwtAdventureDetectionComponent": "how far animals see and hear your cat",
}


def name(key):
    """"/Script/SwtQuest.SwtQuestResourceComponent:WCM_Value" as "SwtQuestResourceComponent.Value", for
    maintainers (the selftest)."""
    cls, _, member = key.partition(":")
    return f"{cls.rsplit('.', 1)[-1]}.{member.replace('WCM_', '')}"


def phrases(keys):
    """The plain words for members ("class:property" keys): one phrase per class (PLAIN), each once, in
    the order the keys come; a class PLAIN doesn't know is named as name() does."""
    out = []
    for key in keys:
        cls = key.partition(":")[0].rsplit(".", 1)[-1]
        words = PLAIN.get(cls) or name(key)
        if words not in out:
            out.append(words)
    return out


def describe(keys):
    """Members in a player's words, as one phrase: ["...SwtAdventureLevelComponent:WCM_Level",
    "...SwtAdventureLevelComponent:WCM_Prowess"] is "your cat's level and stats"; several classes' phrases
    are separated by semicolons (they have commas of their own). One key (a str) works too."""
    return "; ".join(phrases([keys] if isinstance(keys, str) else keys))
