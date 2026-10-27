"""Locate the game, its saves and UE4SS (and an optional Oodle DLL); persist overrides in wcmods.json.
Locate your own files too: your mods, wcmods.json and backups are in a folder outside wcmods' (data_dir)."""
import json
import os
import re
import subprocess

DATA_ENV = "WCMODS_DATA"
STEAM_APP_ID = "3960600"
GAME_FOLDER = "Warrior Cats Clans of the Forest"
EXE_NAME = "Wrc-Win64-ShippingDRM.exe"
MOD_BASENAME = "zzz_WCMods_P"   # sorts last and carries the _P (patch) priority suffix
# wcmods' own UE4SS mod: the colour tables from your palettes, and the reports `tables` reads. It was
# WCModsPalettes; an install removes that folder (ue4ss.ours takes every WCMods* folder as wcmods').
UE4SS_MOD_NAME = "WCModsCore"


HELP = ("wcmods' own settings. game_dir and save_dir: where the game and its saves are, when wcmods can't find "
        "them. allow_code_mods: whether mods may run code. allow_outdated: mods used on a game build they weren't "
        "made for. console: the game's ~ console on or off. oodle_dll: an oo2core DLL for faster decoding. "
        "installed, installed_ue4ss, installed_ue4ss_shared: what the last install put in the game; leave them. "
        "docs/formats.md says more.")


def data_dir():
    """Where your mods, wcmods.json and backups are: %LOCALAPPDATA%\\WCMods, outside the wcmods folder, so
    updating wcmods (git pull, or a new download unzipped over it) never touches them. WCMODS_DATA puts
    them somewhere else (wcmods' own folder, say, to keep everything in one place as older versions did)."""
    return os.path.abspath(os.environ.get(DATA_ENV) or os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "WCMods"))


def same_folder(a, b):
    """Whether two paths are one folder, however each is spelled (a junction, a subst drive, a short name)."""
    try:
        return os.path.samefile(a, b)
    except OSError:   # one of them isn't there
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


class Config:
    """wcmods' settings. `root` is wcmods' own folder (its code and caches); `data` is the folder with your
    mods, wcmods.json and backups (data_dir() unless given: the tests give a folder of their own)."""

    def __init__(self, root, data=None):
        self.root = root
        self.data_dir = data or data_dir()
        self.path = os.path.join(self.data_dir, "wcmods.json")
        self.data = {}
        self.reload()

    def reload(self):
        """Read wcmods.json again. The studio keeps one Config for its whole run, so anything that
        reads a value, changes it and saves (install, uninstall) reloads first; otherwise it would
        write back what it read at startup over what the command line wrote since."""
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8-sig") as f:
                self.data = json.load(f)

    def save(self):
        """Write wcmods.json, with a _help line first saying what it is (docs/formats.md lists every key)."""
        ordered = {"_help": HELP, **{k: v for k, v in self.data.items() if k != "_help"}}
        self.data.clear()   # in place: whoever holds this dict keeps it
        self.data.update(ordered)
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
            f.write("\n")

    # ---- locations ----
    @property
    def mods_root(self):
        return os.path.join(self.data_dir, "mods")

    @property
    def backups_dir(self):
        """Save backups (<date>-<time>-<reason>) and removed or replaced mods (mods/)."""
        return os.path.join(self.data_dir, "backups")

    @property
    def game_dir(self):
        d = self.data.get("game_dir")
        if d and os.path.isdir(d):
            return d
        d = _find_game_dir()
        if d:
            self.data["game_dir"] = d
        return d

    @property
    def paks_dir(self):
        return os.path.join(self.game_dir, "Wrc", "Content", "Paks")

    @property
    def mods_install_dir(self):
        return os.path.join(self.paks_dir, "~mods")

    @property
    def win64_dir(self):
        return os.path.join(self.game_dir, "Wrc", "Binaries", "Win64")

    @property
    def save_dir(self):
        return self.data.get("save_dir") or os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "Wrc", "Saved", "SaveGames")

    @property
    def oodle_dll(self):
        """An oo2core DLL named by "oodle_dll" in wcmods.json, or None: wcmods decodes the game's files
        itself (kraken.py); the DLL is only a speed-up for extracting many of them."""
        d = self.data.get("oodle_dll")
        return d if d and os.path.isfile(d) else None

    @property
    def ue4ss_mods_dir(self):
        """UE4SS 3.x keeps mods in Win64/ue4ss/Mods; older builds use Win64/Mods."""
        if not self.game_dir:   # the studio still opens, to ask where the game is
            return None
        for sub in (("ue4ss", "Mods"), ("Mods",)):
            d = os.path.join(self.win64_dir, *sub)
            if os.path.isdir(d):
                return d
        return None


def _steam_library_dirs():
    roots = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            roots.append(winreg.QueryValueEx(k, "SteamPath")[0].replace("/", "\\"))
    except (OSError, ImportError):   # ImportError: not Windows
        pass
    roots += [r"C:\Program Files (x86)\Steam"]
    libs = []
    for r in roots:
        vdf = os.path.join(r, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            with open(vdf, encoding="utf-8", errors="replace") as f:
                libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', f.read())]
        libs.append(r)
    seen, out = set(), []
    for lib in libs:
        key = os.path.normcase(lib)
        if key not in seen and os.path.isdir(lib):
            seen.add(key)
            out.append(lib)
    return out


def _steam_common_dirs():
    return [os.path.join(lib, "steamapps", "common") for lib in _steam_library_dirs()]


def _find_game_dir():
    try:
        import winreg
        for hive, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")):
            try:
                with winreg.OpenKey(hive, sub + "\\Steam App " + STEAM_APP_ID) as k:
                    d = winreg.QueryValueEx(k, "InstallLocation")[0]
                    if os.path.isdir(d):
                        return d
            except OSError:
                pass
    except ImportError:
        pass
    for common in _steam_common_dirs():
        d = os.path.join(common, GAME_FOLDER)
        if os.path.isdir(d):
            return d
    return None


def steam_game_dir():
    """The copy of the game Steam starts (Play, steam://rungameid): the folder under steamapps/common that its
    appmanifest names, in the Steam library that has one; None when Steam hasn't got the game, or not whole
    (no exe there: being installed or moved)."""
    for lib in _steam_library_dirs():
        try:
            with open(os.path.join(lib, "steamapps", f"appmanifest_{STEAM_APP_ID}.acf"), encoding="utf-8",
                      errors="replace") as f:
                m = re.search(r'"installdir"\s+"([^"]+)"', f.read())
        except OSError:
            continue
        d = os.path.join(lib, "steamapps", "common", m.group(1) if m else GAME_FOLDER)
        if os.path.isfile(os.path.join(d, "Wrc", "Binaries", "Win64", EXE_NAME)):
            return d
    return None


def steam_elsewhere(cfg):
    """Steam's copy of the game when it isn't the one wcmods installs into (game_dir), else None. Mods then go
    into a game nobody starts, while the save both use still gets their edits."""
    steam = steam_game_dir()
    return steam if steam and cfg.game_dir and not same_folder(steam, cfg.game_dir) else None


def steam_elsewhere_text(steam, game_dir):
    """What that means, for every place that says so (the build, `status`, Play, the studio's Mods page)."""
    return (f"Steam starts the game from {steam}, but wcmods puts your mods into {game_dir}, so the game you play "
            "has none of them, and a cat renamed to a mod's own name shows as <MISSING STRING TABLE ENTRY>")


def game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/NH"],
                             capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return EXE_NAME.lower() in out.lower()
