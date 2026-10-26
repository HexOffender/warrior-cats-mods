"""Locate the game, its saves and UE4SS (and an optional Oodle DLL); persist overrides in wcmods.json."""
import json
import os
import re
import subprocess

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


class Config:
    def __init__(self, root):
        self.root = root
        self.path = os.path.join(root, "wcmods.json")
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
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
            f.write("\n")

    # ---- locations ----
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
    except OSError:
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


def game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/NH"],
                             capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return EXE_NAME.lower() in out.lower()
