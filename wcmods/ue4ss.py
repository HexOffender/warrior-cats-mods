"""UE4SS, the script loader: install it in the game, and install and register Lua mods in it (mods.txt and
mods.json both list enabled mods)."""
import json
import os
import re
import shutil
import tempfile
import zipfile

# Where UE4SS comes from: its project's GitHub releases. wcmods is tried with the experimental build
# (UE4SS_v3.0.1-1181-g83330635.zip, the release's UE4SS_v*.zip; the zDEV one is for UE4SS's own
# developers).
RELEASE_API = "https://api.github.com/repos/UE4SS-RE/RE-UE4SS/releases/tags/experimental-latest"
RELEASE_PAGE = "https://github.com/UE4SS-RE/RE-UE4SS/releases/tag/experimental-latest"
ASSET = re.compile(r"^UE4SS_v[0-9][^/\\]*\.zip$")
MAX_ZIP = 200 * 1024 * 1024
# Its settings for players: no debug console windows over the game.
SETTINGS = {"ConsoleEnabled": "0", "GuiConsoleEnabled": "0", "GuiConsoleVisible": "0"}


def loader_installed(win64_dir):
    """Whether UE4SS is in the game (its dwmapi.dll, which the game loads, and its ue4ss folder)."""
    return bool(win64_dir) and os.path.isfile(os.path.join(win64_dir, "dwmapi.dll")) \
        and os.path.isfile(os.path.join(win64_dir, "ue4ss", "UE4SS.dll"))


_DLL_HASHES = {}   # (path, size, mtime) -> SHA-1, for loader_identity


def loader_identity(win64_dir):
    """Which UE4SS the game has, for C++ mods (built against one UE4SS): {"commit": its git commit from the
    first lines of UE4SS.log ("Git SHA #83330635"; None when the game hasn't run since this UE4SS.dll was
    put in), "dll": UE4SS.dll's SHA-1}, or None without UE4SS."""
    import hashlib
    if not loader_installed(win64_dir):
        return None
    dll = os.path.join(win64_dir, "ue4ss", "UE4SS.dll")
    st = os.stat(dll)
    key = (os.path.abspath(dll), st.st_size, st.st_mtime_ns)
    if key not in _DLL_HASHES:   # 20 MB, read once per UE4SS.dll rather than on every build
        with open(dll, "rb") as f:
            _DLL_HASHES[key] = hashlib.sha1(f.read()).hexdigest()
    digest = _DLL_HASHES[key]
    commit, path = None, log_path(win64_dir)
    if path and os.path.getmtime(path) >= os.path.getmtime(dll):
        with open(path, encoding="utf-8", errors="replace") as f:
            for _, line in zip(range(20), f):
                m = re.search(r"Git SHA #([0-9a-fA-F]{7,40})", line)
                if m:
                    commit = m.group(1).lower()
                    break
    return {"commit": commit, "dll": digest}


def find_release(timeout=20):
    """The UE4SS download wcmods uses: {"name", "url", "size", "page"} from GitHub."""
    import urllib.request
    req = urllib.request.Request(RELEASE_API, headers={"User-Agent": "wcmods", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    for a in data.get("assets", []):
        if ASSET.match(a.get("name", "")):
            return {"name": a["name"], "url": a["browser_download_url"], "size": a.get("size"), "page": RELEASE_PAGE}
    raise RuntimeError(f"UE4SS's release page has no UE4SS_v*.zip any more; download it from {RELEASE_PAGE} "
                       "and give the .zip to Clan Mod Studio")


def download(asset, folder, timeout=60, limit=MAX_ZIP, what="UE4SS"):
    """Download a release asset (UE4SS's, or `what` else's, at most `limit` bytes) into folder; returns
    the file's path."""
    import urllib.request
    path = os.path.join(folder, os.path.basename(asset["name"]))
    req = urllib.request.Request(asset["url"], headers={"User-Agent": "wcmods"})
    got = 0
    with urllib.request.urlopen(req, timeout=timeout) as r, open(path, "wb") as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            got += len(chunk)
            if got > limit:
                raise RuntimeError(f"the {what} download is far bigger than it should be; stopped")
            f.write(chunk)
    if asset.get("size") and got != asset["size"]:
        raise RuntimeError(f"the {what} download stopped early ({got} of {asset['size']} bytes); try again")
    return path


def install_loader(zip_path, win64_dir, console=True, log=print):
    """Put UE4SS in the game from its release .zip (dwmapi.dll and the ue4ss folder at its top), set up
    for players (configure_loader). The game must be closed. Returns the files written."""
    with zipfile.ZipFile(zip_path) as z:
        members = []
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if name.startswith("/") or ".." in parts or any(":" in p for p in parts):
                raise ValueError(f"{info.filename}: not a safe path; this isn't UE4SS's .zip")
            if info.is_dir() or not parts or (parts[0] != "dwmapi.dll" and parts[0] != "ue4ss"):
                continue
            members.append((parts, info))
        names = {"/".join(p) for p, _ in members}
        if "dwmapi.dll" not in names or "ue4ss/UE4SS.dll" not in names:
            raise ValueError("this isn't UE4SS's .zip (it has no dwmapi.dll and ue4ss/UE4SS.dll at its top); "
                             f"get UE4SS_v*.zip from {RELEASE_PAGE}")
        if sum(i.file_size for _, i in members) > MAX_ZIP:
            raise ValueError("this .zip unpacks to far more than UE4SS does")
        written = []
        top = os.path.realpath(win64_dir) + os.sep
        for parts, info in members:
            dest = os.path.join(win64_dir, *parts)
            if not os.path.realpath(dest).startswith(top):
                raise ValueError(f"{info.filename}: not a safe path; this isn't UE4SS's .zip")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out, 1024 * 1024)
            written.append(dest)
    log(f"  UE4SS: {len(written)} files in {win64_dir}")
    configure_loader(win64_dir, console=console)
    return written


def configure_loader(win64_dir, console=True):
    """UE4SS set up for players: its debug console windows off, its cheat-manager enabler off (the Menu
    pages mod's Cheats page does that, and can switch cheats off again), and its console enabler (~ or F10
    opens the game's console) on or off."""
    ini = os.path.join(win64_dir, "ue4ss", "UE4SS-settings.ini")
    if os.path.isfile(ini):
        with open(ini, encoding="utf-8-sig") as f:
            text = f.read()
        for key, value in SETTINGS.items():
            text = re.sub(rf"(?m)^({key}\s*=\s*).*$", lambda m: m.group(1) + value, text)
        with open(ini, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    mods_dir = os.path.join(win64_dir, "ue4ss", "Mods")
    if os.path.isdir(mods_dir):
        set_registered(mods_dir, "CheatManagerEnablerMod", False)
        if os.path.isdir(os.path.join(mods_dir, "ConsoleEnablerMod")):
            set_registered(mods_dir, "ConsoleEnablerMod", console)


def download_and_install(win64_dir, console=True, log=print):
    """find_release, download and install_loader in one go; returns the release it installed."""
    asset = find_release()
    log(f"downloading {asset['name']} ({(asset['size'] or 0) / 1024 / 1024:.1f} MB) from GitHub...")
    with tempfile.TemporaryDirectory() as tmp:
        install_loader(download(asset, tmp), win64_dir, console=console, log=log)
    return asset


def _register(mods_dir, name, enabled):
    txt = os.path.join(mods_dir, "mods.txt")
    if os.path.isfile(txt):
        with open(txt, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
        lines = [l for l in lines if l.split(":")[0].strip() != name]
        if enabled:
            at = next((i for i, l in enumerate(lines) if l.strip().startswith("; Built-in keybinds")), len(lines))
            lines.insert(at, f"{name} : 1")
        with open(txt, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")
    js = os.path.join(mods_dir, "mods.json")
    if os.path.isfile(js):
        with open(js, encoding="utf-8-sig") as f:
            entries = json.load(f)
        entries = [e for e in entries if e.get("mod_name") != name]
        if enabled:
            at = next((i for i, e in enumerate(entries) if e.get("mod_name") == "Keybinds"), len(entries))
            entries.insert(at, {"mod_name": name, "mod_enabled": True})
        with open(js, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=4)


def set_registered(mods_dir, name, enabled):
    """Turn an installed UE4SS mod on or off in place in mods.txt and mods.json, keeping its entry (for the
    mods that ship with UE4SS, listed as "Name : 0" when off)."""
    txt = os.path.join(mods_dir, "mods.txt")
    if os.path.isfile(txt):
        with open(txt, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
        hits = [i for i, l in enumerate(lines) if l.split(":")[0].strip() == name]
        if hits:
            lines[hits[0]] = f"{name} : {1 if enabled else 0}"
            with open(txt, "w", encoding="utf-8", newline="\r\n") as f:
                f.write("\n".join(lines) + "\n")
        else:
            _register(mods_dir, name, enabled)
            return
    js = os.path.join(mods_dir, "mods.json")
    if os.path.isfile(js):
        with open(js, encoding="utf-8-sig") as f:
            entries = json.load(f)
        for e in entries:
            if e.get("mod_name") == name:
                e["mod_enabled"] = bool(enabled)
        with open(js, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=4)


OUR_PREFIX = "WCMods"   # every UE4SS mod wcmods builds itself is named WCMods...


def ours(mods_dir):
    """The WCMods... mod folders installed now, whether or not wcmods.json still lists them."""
    if not os.path.isdir(mods_dir):
        return set()
    return {n for n in os.listdir(mods_dir)
            if n.startswith(OUR_PREFIX) and os.path.isdir(os.path.join(mods_dir, n))}


def install_mod(mods_dir, name, source_dir):
    target = os.path.join(mods_dir, name)
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(source_dir, target)
    _register(mods_dir, name, True)
    return target


def remove_mod(mods_dir, name):
    target = os.path.join(mods_dir, name)
    if os.path.isdir(target):
        shutil.rmtree(target)
    _register(mods_dir, name, False)


def install_shared(mods_dir, name, source_dir):
    """Install a shared Lua module as Mods/shared/<name>/, which any UE4SS script can require(name).
    Shared modules aren't mods: UE4SS doesn't run them on their own, so they aren't registered."""
    target = os.path.join(mods_dir, "shared", name)
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(source_dir, target)
    return target


def remove_shared(mods_dir, name):
    target = os.path.join(mods_dir, "shared", name)
    if os.path.isdir(target):
        shutil.rmtree(target)
        return target
    return None


def log_path(win64_dir):
    for sub in (("ue4ss", "UE4SS.log"), ("UE4SS.log",)):
        p = os.path.join(win64_dir, *sub)
        if os.path.isfile(p):
            return p
    return None


def read_reports(win64_dir, tags=("[WCModsCore]", "[WCModsPalettes]")):
    """Parse the TABLE lines (the game's original colour tables) and notes our script logs. The second
    tag is the script's name before wcmods 0.2: a log from the previous install still counts."""
    path = log_path(win64_dir)
    tables, notes = {}, []
    if not path:
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            tag = next((t for t in tags if t in line), None)
            if not tag:
                continue
            msg = line.split(tag, 1)[1].strip()
            if msg.startswith("TABLE "):
                _, prop, _n, *hexes = msg.split()
                tables[prop] = hexes
            else:
                notes.append(msg)
    return {"tables": tables, "notes": notes[-20:], "log_time": os.path.getmtime(path)}
