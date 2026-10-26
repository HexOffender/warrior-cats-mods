"""Read any game file by path, from the legacy pak or the IoStore container."""
import fnmatch
import os

from .iostore import IoStoreReader
from .oodle import Oodle
from .pak import PakReader

BASE_PAK = "pakchunk0-Windows.pak"
BASE_UTOC = "pakchunk0-Windows.utoc"
NONASSET = "Wrc/Content/Gameplay/DataTables/NonAsset/"


class GameFiles:
    def __init__(self, cfg):
        self.cfg = cfg
        self._oodle = self._pak = self._io = None

    @property
    def oodle(self):
        """The decompressor: wcmods' own, or the oo2core DLL wcmods.json names."""
        if self._oodle is None:
            self._oodle = Oodle(self.cfg.oodle_dll)
        return self._oodle

    @property
    def pak(self):
        if self._pak is None:
            self._pak = PakReader(os.path.join(self.cfg.paks_dir, BASE_PAK), self.oodle)
        return self._pak

    @property
    def io(self):
        if self._io is None:
            self._io = IoStoreReader(os.path.join(self.cfg.paks_dir, BASE_UTOC), self.oodle)
        return self._io

    def exists(self, path):
        return path in self.pak.entries or path in self.io.files

    def read(self, path):
        if path in self.pak.entries:
            return self.pak.read(path)
        if path in self.io.files:
            return self.io.read_file(path)
        raise KeyError(f"game file not found: {path}")

    def read_text(self, path):
        return self.read(path).decode("utf-8")

    def find(self, pattern):
        pat = pattern.lower()
        return sorted([p for p in self.pak.entries if fnmatch.fnmatch(p.lower(), pat)] +
                      [p for p in self.io.files if fnmatch.fnmatch(p.lower(), pat)])

    def data_tables(self):
        """Every runtime CSV the game loads from NonAsset/, relative to that folder."""
        return sorted(p[len(NONASSET):] for p in self.pak.entries
                      if p.startswith(NONASSET) and p.endswith(".csv"))
