"""The mods that go with Clan Mod Studio (its "add-ons"): four mods of their own, each in its own repository
and fetched from its GitHub releases, which the studio's pages need for what they make to reach the game,
or which are the player's own tools:

- Menu pages: the mod menu's pages about the game (menupages.py keeps what is its own: the Overview's
  note, its cheats setting);
- Sandbox mode: brings the Characters and Questlines pages' cats and quests into the game;
- Creator palettes: your new colours and coat presets in the cat maker (its .zip carries ten themed
  palettes, which ship off, and Coat presets, which ships on);
- Emote wheel: a wheel of your emotes and the game's poses.

ADDONS is the one list of them. It says nothing about which wcmods each one needs or whether it runs code:
each one's own mod.json says that ("wcmods", mods.Mod.has_code), so there's one place for it.

Adding one (add) downloads its latest release's .zip into the cache folder in your files' folder
(cache/downloads, kept so that a preview and the add after it read one file; an older download of the same
add-on is removed once the new one is there) and adds the mods in it through modzip.add_zip, each on or off
as it ships. A mod you have already keeps whether it's on, and the files in its `keep` keep your values
over the new copy's (settings.json: the Emote wheel's key, Menu pages' cheats), whether it's added here or
from its .zip on the Mods page (remember, put_back). The other mods in its .zip go in beside it, but never
over a mod of yours with the same id that an earlier add of it didn't bring in (ADDED_WITH). A release of
the version you have changes nothing. With no release on GitHub yet, it says so in words (NO_RELEASE)
rather than failing.

WCMODS_RELEASES, set to a folder, stands in for GitHub: each add-on's newest .zip in it (by the version in
its file name) is its latest release, and none is "no release yet". It's for the tests.
"""
import json
import os
import pathlib
import re
import shutil
import tempfile
from typing import NamedTuple

from . import modzip
from . import mods as modlib
from .mods import Mod

MAX_ZIP = 50 * 1024 * 1024
DOWNLOADS = os.path.join("cache", "downloads")   # in your files' folder (config.data_dir())
NO_RELEASE = "no release yet; the owner of that mod has to publish one"


class Addon(NamedTuple):
    id: str            # its folder in mods/, and its mod.json's mod
    name: str
    repo: str          # its GitHub repository
    asset: str         # its release's .zip, as a pattern (Sandbox mode's release carries example mods too)
    about: str         # what it does, in one sentence, for the Add-ons card
    pages: tuple = ()  # the studio pages whose work it brings into the game
    tool: bool = False  # the player's own tool rather than part of a story
    keep: tuple = ()   # files whose values an update keeps over the new copy's

    @property
    def api(self):
        return f"https://api.github.com/repos/{self.repo}/releases/latest"

    @property
    def page(self):
        return f"https://github.com/{self.repo}/releases"


ADDONS = (
    Addon("menu-pages", "Menu pages", "HexOffender/wcmods-menu-pages", r"^menu-pages[^/\\]*\.zip$",
          "Your cat, the world, quests, fights and cheats in the in-game menu", tool=True, keep=("settings.json",)),
    Addon("sandbox", "Sandbox mode", "HexOffender/wcmods-sandbox", r"^sandbox-\d[^/\\]*\.zip$",
          "Shows the cats and questlines you make", pages=("npcs", "quests"), keep=("settings.json",)),
    Addon("creator-palettes", "Creator palettes", "HexOffender/wcmods-creator-palettes",
          r"^creator-palettes-\d[^/\\]*\.zip$", "Your new colours and coat presets in the cat maker",
          pages=("palettes",), tool=True),
    Addon("emote-wheel", "Emote wheel", "HexOffender/wcmods-emote-wheel", r"^emote-wheel-\d[^/\\]*\.zip$",
          "A wheel of your emotes and the game's poses", pages=("animations",), tool=True, keep=("settings.json",)),
)


def find(addon_id):
    """The add-on with this id, or None."""
    return next((a for a in ADDONS if a.id == addon_id), None)


def get(addon_id):
    """The add-on with this id; LookupError when there's none."""
    addon = find(addon_id)
    if not addon:
        raise LookupError(f"there's no mod called {addon_id} among the mods that go with Clan Mod Studio")
    return addon


def installed(mods_root, addon):
    """The add-on in your mods, or None (a mod.json that can't be read is as good as none)."""
    folder = os.path.join(mods_root, addon.id)
    if not os.path.isfile(os.path.join(folder, "mod.json")):
        return None
    try:
        m = Mod(folder)
    except (OSError, ValueError):
        return None
    return None if m.problem else m


def no_release(addon):
    """What to say when an add-on has no release on GitHub: whose move it is, and where to look."""
    return f"{addon.name} has {NO_RELEASE} ({addon.page})"


def _same(a, b):
    ka, kb = modlib.version_key(a), modlib.version_key(b)
    return ka == kb if ka is not None and kb is not None else str(a) == str(b)


def _newer(latest, have):
    """Whether `latest` is a newer version than `have` (one that isn't a version: whether they differ)."""
    ka, kb = modlib.version_key(latest), modlib.version_key(have)
    if ka is not None and kb is not None:
        return ka > kb
    return bool(latest) and str(latest) != str(have)


def _version_in(name):
    m = re.search(r"-v?(\d+(?:\.\d+)*)\.zip$", name, re.I)
    return m.group(1) if m else ""


def _local_release(addon, folder):
    """WCMODS_RELEASES' stand-in for GitHub: the newest .zip of the add-on in `folder` (by the version in its
    name; one without a version only when none has one)."""
    from .ue4ss import NoRelease
    pattern = re.compile(addon.asset)
    names = [n for n in os.listdir(folder) if pattern.match(n)] if os.path.isdir(folder) else []
    if not names:
        raise NoRelease(f"{addon.name} has no release on GitHub yet ({addon.page})")
    versioned = [n for n in names if modlib.version_key(_version_in(n)) is not None]
    name = max(versioned, key=lambda n: modlib.version_key(_version_in(n))) if versioned else max(names)
    path = os.path.abspath(os.path.join(folder, name))
    return {"name": name, "url": pathlib.Path(path).as_uri(), "size": os.path.getsize(path),
            "version": _version_in(name), "page": addon.page, "id": None,
            "updated_at": str(os.stat(path).st_mtime_ns)}


def find_release(addon, timeout=20):
    """The add-on's latest release's .zip: {"name", "url", "size", "version" (its tag, without a "v"),
    "page", "id" and "updated_at" (GitHub's for the .zip, which tell a new upload under the same name)}. No
    release at all is ue4ss.NoRelease; any other trouble with GitHub a RuntimeError saying so (ue4ss.Offline
    when it couldn't be reached)."""
    local = os.environ.get("WCMODS_RELEASES")
    if local:
        return _local_release(addon, local)
    from .ue4ss import github_release
    data = github_release(addon.api, addon.name, addon.page, timeout)
    pattern = re.compile(addon.asset)
    for a in data.get("assets", []):
        if pattern.match(a.get("name", "")):
            return {"name": a["name"], "url": a["browser_download_url"], "size": a.get("size"),
                    "version": str(data.get("tag_name") or "").strip().lstrip("vV"), "page": addon.page,
                    "id": a.get("id"), "updated_at": a.get("updated_at")}
    raise RuntimeError(f"the latest {addon.name} release has no .zip of the mod in it; download it from "
                       f"{addon.page} and add it on the Mods page")


def latest(addon, timeout=20):
    """What GitHub has of the add-on: {"version", "name"}; {"no_release": True, "error"} when there's no
    release; {"error", "offline"} when GitHub couldn't be asked (offline: it couldn't be reached at all)."""
    from .ue4ss import NoRelease, Offline
    try:
        r = find_release(addon, timeout)
    except NoRelease:
        return {"no_release": True, "error": no_release(addon)}
    except RuntimeError as e:
        return {"error": str(e), "offline": isinstance(e, Offline)}
    return {"version": r["version"], "name": r["name"]}


def answered(found):
    """Whether latest()'s `found` is GitHub's answer (a version, or no release at all), which can be kept for
    a while, rather than GitHub not answering (no connection, too many questions), which can't."""
    return bool(found) and (not found.get("error") or bool(found.get("no_release")))


def status(cfg, releases=None):
    """Each add-on as the Add-ons card shows it: [{id, name, about, page, pages, tool, installed, enabled,
    version, code (it runs code), needs_code (and mods that run code aren't allowed), too_new (why this
    wcmods leaves it out, or None), latest (GitHub's version, once asked: `releases`, {id: latest()}), newer,
    no_release, error (why GitHub had no answer, or that there's no release), offline (GitHub couldn't be
    reached)}]."""
    releases = releases or {}
    code_ok = bool(cfg.data.get("allow_code_mods"))
    out = []
    for a in ADDONS:
        m = installed(cfg.mods_root, a)
        rel = releases.get(a.id) or {}
        out.append({"id": a.id, "name": a.name, "about": a.about, "page": a.page, "pages": list(a.pages),
                    "tool": a.tool, "installed": bool(m), "enabled": bool(m and m.enabled),
                    "version": m.version if m else None, "code": bool(m and m.has_code()),
                    "needs_code": bool(m and m.has_code() and not code_ok),
                    "too_new": modlib.needs_newer(m.wcmods_min) if m else None,
                    "latest": rel.get("version"), "newer": bool(m and rel.get("version") and _newer(rel["version"], m.version)),
                    "no_release": bool(rel.get("no_release")), "error": rel.get("error"),
                    "offline": bool(rel.get("offline"))})
    return out


def _read_json(folder, name):
    try:
        with open(os.path.join(folder, name), encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(folder, name, data):
    with open(os.path.join(folder, name), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


NOTE = ".release"   # beside a cached .zip: which upload of it that is (_upload)


def _upload(release):
    """What tells one upload of a release's .zip from another with the same name and size: GitHub's id and
    updated_at for it ("" when the release doesn't say)."""
    if release.get("id") is None and not release.get("updated_at"):
        return ""
    return f"{release.get('id')} {release.get('updated_at')}"


def _cached(path, release):
    """Whether the .zip at `path` is the release's: whole (its size), and the same upload when GitHub says
    which (the note beside it)."""
    if not os.path.isfile(path) or (release.get("size") and os.path.getsize(path) != release["size"]):
        return False
    upload = _upload(release)
    if not upload:
        return True
    try:
        with open(path + NOTE, encoding="utf-8") as f:
            return f.read().strip() == upload
    except OSError:
        return False


def download(cfg, addon, release, log=print):
    """The release's .zip in the cache folder, downloaded unless it's there already (_cached). Older downloads
    of the same add-on are removed once this one is there, so a download that fails leaves the last one.
    Returns its path."""
    from . import ue4ss
    folder = os.path.join(cfg.data_dir, DOWNLOADS)
    os.makedirs(folder, exist_ok=True)
    name = os.path.basename(release["name"])
    path = os.path.join(folder, name)
    if not _cached(path, release):
        log(f"downloading {name} ({(release.get('size') or 0) / 1024:.0f} KB) from GitHub...")
        part = tempfile.mkdtemp(prefix="_downloading-", dir=folder)
        try:
            os.replace(ue4ss.download(release, part, limit=MAX_ZIP, what=addon.name), path)
        finally:
            shutil.rmtree(part, ignore_errors=True)
        upload = _upload(release)
        try:
            if upload:
                with open(path + NOTE, "w", encoding="utf-8") as f:
                    f.write(upload + "\n")
            elif os.path.isfile(path + NOTE):
                os.remove(path + NOTE)
        except OSError:   # without its note it's downloaded again next time: no harm
            pass
    pattern = re.compile(addon.asset)
    for other in os.listdir(folder):
        zip_name = other[:-len(NOTE)] if other.endswith(NOTE) else other
        if zip_name != name and pattern.match(zip_name):
            try:
                os.remove(os.path.join(folder, other))
            except OSError:   # in use: it goes next time
                pass
    return path


ADDED_WITH = "added_with"   # mod.json: the add-on whose .zip brought this mod in (one of its extra mods)


def _came_with(mods_root, mod_id, addon):
    """Whether the mod in mods/<mod_id> came in with `addon` (an earlier add of it), so an update may replace
    it; a mod of yours with the same id (wcmods-examples' palettes share Creator palettes' ids) didn't."""
    meta = _read_json(os.path.join(mods_root, mod_id), "mod.json")
    return bool(meta) and meta.get(ADDED_WITH) == addon.id


def _mark(mods_root, mod_id, addon):
    """Note in a mod's mod.json that `addon` brought it in (_came_with)."""
    folder = os.path.join(mods_root, mod_id)
    meta = _read_json(folder, "mod.json")
    if meta is not None and meta.get(ADDED_WITH) != addon.id:
        meta[ADDED_WITH] = addon.id
        _write_json(folder, "mod.json", meta)


def remember(mods_root, ids=None):
    """Your values in the add-ons' `keep` files, read before an add or update replaces them: {add-on id:
    {file: values or None}} for each add-on you have (of `ids`, when given)."""
    out = {}
    for a in ADDONS:
        if not a.keep or (ids is not None and a.id not in ids):
            continue
        m = installed(mods_root, a)
        if m:
            out[a.id] = {f: _read_json(m.folder, f) for f in a.keep}
    return out


def put_back(mods_root, remembered, added=None):
    """Your values from remember() over the new copy's files: its new keys and its own notes ("_" keys) stay,
    yours win. `added` (modzip.add_zip's entries): only the add-ons that replaced the copy you had."""
    if added is not None:
        replaced = {d["id"] for d in added if d.get("replaced")}
        remembered = {i: v for i, v in remembered.items() if i in replaced}
    for addon_id, files in remembered.items():
        new = installed(mods_root, get(addon_id))
        if not new:
            continue
        for name, values in files.items():
            if isinstance(values, dict):
                shipped = _read_json(new.folder, name) or {}
                want = {**shipped, **{k: v for k, v in values.items() if not str(k).startswith("_")}}
                if want != shipped:
                    _write_json(new.folder, name, want)


def _release(addon, release=None):
    """`release`, or the add-on's latest one, with "no release yet" said in words."""
    from .ue4ss import NoRelease
    if release:
        return release
    try:
        return find_release(addon)
    except NoRelease:
        raise NoRelease(no_release(addon)) from None


def preview(cfg, addon_id, log=print):
    """What adding an add-on would add, as the Mods page's preview of a .zip shows it: {"mods" (modzip.inspect),
    "name" (the release's .zip), "version", "code_allowed"}. The .zip is downloaded into the cache, so the
    add after it reads the same file."""
    addon = get(addon_id)
    release = _release(addon)
    path = download(cfg, addon, release, log)
    return {"mods": modzip.inspect(path, cfg.mods_root, release["name"]), "name": release["name"],
            "version": release["version"], "code_allowed": bool(cfg.data.get("allow_code_mods"))}


def add(cfg, addon_id, zip_path=None, on=None, log=print, release=None, seed=None):
    """Add an add-on to your mods, or update it: from `zip_path` (a .zip of it someone downloaded), else its
    latest release (`release`, or asked of GitHub). Every mod in the .zip goes in, each on or off as it ships;
    a mod you have already keeps its own on or off, and `on` (True or False) says it for the add-on itself.
    The other mods in its .zip (Creator palettes' themes) never replace a mod of yours with the same id that
    an earlier add of this add-on didn't bring in (ADDED_WITH, in each one's mod.json): those are left as
    they are ("kept"). The files in its `keep` keep your values (`seed`: {file: values} to use when the copy
    you have has none). From GitHub, a release of the version you have changes nothing ("unchanged"). Adding
    Menu pages clears Get set up's old "Not now" for it.

    Returns {"id", "name", "version", "from" (the .zip), "replaced" (the older copy's backup, or None),
    "unchanged", "on", "added" (modzip.add_zip's entries for every mod that went in), "kept" ([{id, name}]
    of yours left as they were)}."""
    addon = get(addon_id)
    cfg.reload()   # it saves below: whatever another command wrote since is kept
    old = installed(cfg.mods_root, addon)
    mine = remember(cfg.mods_root, [addon.id]).get(addon.id, {})
    for f, values in (seed or {}).items():
        if mine.get(f) is None:
            mine[f] = values
    if zip_path:
        path, source = zip_path, os.path.basename(zip_path)
    else:
        release = _release(addon, release)
        if old and release["version"] and _same(release["version"], old.version):
            return {"id": addon.id, "name": addon.name, "version": old.version, "from": release["name"],
                    "replaced": None, "unchanged": True, "on": old.enabled, "added": [], "kept": []}
        path, source = download(cfg, addon, release, log), release["name"]
    found = modzip.inspect(path, cfg.mods_root, source)
    if not any(f["id"] == addon.id for f in found):
        raise ValueError(f"{source} doesn't have the {addon.name} mod in it; get its .zip from {addon.page}")
    kept = [f for f in found if f["id"] != addon.id and f["existing"] and not _came_with(cfg.mods_root, f["id"], addon)]
    ids = [f["id"] for f in found if f not in kept]
    have = {m.id: m.enabled for m in modlib.discover(cfg.mods_root) if not m.problem}
    enable = {f["id"]: have.get(f["id"], f["enabled"]) for f in found}
    if on is not None:
        enable[addon.id] = bool(on)
    log(f"adding {addon.name} from {source}")
    for f in kept:
        log(f"  {f['id']}: you have a mod of your own with that id, so it's left as it is")
    done = modzip.add_zip(path, cfg.mods_root, cfg.backups_dir, ids=ids, enable=enable, name=source)
    for d in done:
        if d["id"] != addon.id:
            _mark(cfg.mods_root, d["id"], addon)
    new = installed(cfg.mods_root, addon)
    put_back(cfg.mods_root, {addon.id: mine})
    if addon.id == "menu-pages" and cfg.data.get("skip_menu_pages"):
        cfg.data.pop("skip_menu_pages")
        cfg.save()
    me = next(d for d in done if d["id"] == addon.id)
    return {"id": addon.id, "name": addon.name, "version": new.version if new else None, "from": source,
            "replaced": me.get("replaced"), "unchanged": False, "on": me["on"], "added": done,
            "kept": [{"id": f["id"], "name": f["name"]} for f in kept]}
