"""Locate the game, its saves, Oodle and UE4SS; persist overrides in wcmods.json."""
import json
import os
import re
import subprocess

STEAM_APP_ID = "3960600"
GAME_FOLDER = "Warrior Cats Clans of the Forest"
EXE_NAME = "Wrc-Win64-ShippingDRM.exe"
MOD_BASENAME = "zzz_WCMods_P"   # sorts last and carries the _P (patch) priority suffix
UE4SS_MOD_NAME = "WCModsPalettes"


class Config:
    def __init__(self, root):
        self.root = root
        self.path = os.path.join(root, "wcmods.json")
        self.data = {}
        self._oodle_searched, self._oodle_found = False, None
        self.reload()

    def reload(self):
        """Read wcmods.json again. The studio keeps one Config for its whole run, so anything that
        reads a value, changes it and saves (install, uninstall) reloads first; otherwise it would
        write back what it read at startup over what the command line wrote since."""
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8-sig") as f:
                self.data = json.load(f)

    def save(self):
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
        d = self.data.get("oodle_dll")
        if d and os.path.isfile(d):
            return d
        if not self._oodle_searched:   # walking every Steam library is slow; do it once per run
            from .oodle import find_oodle_dll
            self._oodle_searched = True
            self._oodle_found = find_oodle_dll(_steam_common_dirs())
        # Kept apart from data, so a reload() before wcmods.json is saved doesn't lose what was found.
        if self._oodle_found:
            self.data["oodle_dll"] = self._oodle_found
        return self._oodle_found

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
