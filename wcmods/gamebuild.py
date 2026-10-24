"""Which build of the game is installed, and how wcmods and the mods stand on it.

Steam keeps the game up to date by itself, so a player can have a newer build than wcmods, or a mod,
was made for. This module tells which build is installed (Steam's appmanifest, or failing that the exe
itself) and what follows:

- wcmods' own parts: on a build in VERIFIED nothing changes. On another one, signatures.check() looks
  for what the game update moved (game.HIDDEN's members) and the in-game module gets the offsets it
  found; members it can't find again are left out rather than guessed. The answer is kept in
  cache/layout-<build>.json, so it's worked out once per game update.
- mods: each says in mod.json which builds it was made for ("game_builds"). One that doesn't list the
  installed build is "made for an older version" and stays out of the game until it's updated, or the
  player chooses to use it anyway on this build (wcmods.json "allow_outdated"), with a warning that it
  may not work or may behave unpredictably. A mod that says nothing was made for build 24847281, as
  every mod before this was.
"""
import json
import os
import re

from . import pe

# Builds wcmods' own parts (the in-game module's members, the mod menu, the agent's tests) were checked on.
VERIFIED = {24847281: "the first release (October 2026)"}
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
    from .config import STEAM_APP_ID
    steamapps = os.path.dirname(os.path.dirname(os.path.normpath(cfg.game_dir)))   # <lib>\steamapps
    path = os.path.join(steamapps, f"appmanifest_{STEAM_APP_ID}.acf")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            m = re.search(r'"buildid"\s+"(\d+)"', f.read())
    except OSError:
        return None
    return int(m.group(1)) if m else None


def current(cfg):
    """{"build" (None when unknown), "verified"}: the installed build."""
    build = steam_build(cfg)
    return {"build": build, "verified": build in VERIFIED, "label": VERIFIED.get(build)}


def made_for(mod):
    """The builds a mod says it was made for (mod.json "game_builds"), or the assumed ones."""
    v = mod.meta.get("game_builds", mod.meta.get("game_build"))
    if isinstance(v, int) and not isinstance(v, bool):
        v = [v]
    builds = [b for b in v if isinstance(b, int) and not isinstance(b, bool)] if isinstance(v, list) else []
    return builds or list(ASSUMED_BUILDS)


def allowed(cfg, mod_id, build):
    """Whether the player chose to use a mod made for an older version on this build."""
    return build in (cfg.data.get("allow_outdated") or {}).get(mod_id, [])


def allow(cfg, mod_id, build, on=True):
    """Use (or stop using) a mod made for an older version, on this build only."""
    cfg.reload()
    table = dict(cfg.data.get("allow_outdated") or {})
    builds = [b for b in table.get(mod_id, []) if b != build]
    if on:
        builds.append(build)
    if builds:
        table[mod_id] = builds
    else:
        table.pop(mod_id, None)
    cfg.data["allow_outdated"] = table
    cfg.save()


def outdated(cfg, mods, build=None):
    """{mod id: {"made_for", "allowed"}} for the mods that are on and weren't made for the installed build.
    Built-in mods are wcmods' own and follow its signatures instead."""
    build = build if build is not None else steam_build(cfg)
    if build is None:
        return {}
    out = {}
    for m in mods:
        if not m.enabled or m.builtin:
            continue
        builds = made_for(m)
        if build not in builds:
            out[m.id] = {"made_for": builds, "allowed": allowed(cfg, m.id, build)}
    return out


# ---------- wcmods' own parts on a new build ----------
def _cache_path(cfg, key):
    return os.path.join(cfg.root, CACHE_DIR, f"layout-{key}.json")


def layout(cfg, log=print, refresh=False):
    """How wcmods' in-game members stand on the installed game: {"build", "status", "offsets", "moved",
    "lost"}. status: "verified" (a build wcmods was checked on; offsets None, so game.HIDDEN as it is),
    "adapted" (another build, every member found again), "partial" (some couldn't be: they're None in
    offsets and left out), or "unknown" (no game, or no exe to read)."""
    info = current(cfg)
    if info["verified"]:
        return {"build": info["build"], "status": "verified", "offsets": None, "moved": [], "lost": []}
    exe = pe.game_exe(cfg)
    if not exe:
        return {"build": info["build"], "status": "unknown", "offsets": None, "moved": [], "lost": []}
    st = os.stat(exe)
    key = f"{info['build'] or 'unknown'}-{st.st_size:x}-{int(st.st_mtime):x}"
    path = _cache_path(cfg, key)
    if not refresh and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    from . import signatures
    log(f"  the game updated (build {info['build'] or 'unknown'}): looking for what moved, once (about a minute)")
    res = signatures.check(exe, log=lambda m: log("  " + m))
    moved = [k for c, rep in res["classes"].items() for n, f in rep["fields"].items() if f["status"] == "moved"
             for k in [f"{c}:{n}"]]
    lost = [k for c, rep in res["classes"].items() for n, f in rep["fields"].items()
            if f["status"] in ("lost", "conflict") for k in [f"{c}:{n}"]]
    out = {"build": info["build"], "status": "partial" if lost else "adapted", "offsets": res["offsets"],
           "moved": moved, "lost": lost}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    return out


def describe(key):
    """"/Script/SwtQuest.SwtQuestResourceComponent:WCM_Value" as "SwtQuestResourceComponent.Value"."""
    cls, _, name = key.partition(":")
    return f"{cls.rsplit('.', 1)[-1]}.{name.replace('WCM_', '')}"
