"""Read any game file by path, from the legacy pak or the IoStore container."""
import fnmatch
import os
import sys

from .formats.iostore import IoStoreReader
from .formats.oodle import Oodle
from .formats.pak import PakReader

BASE_PAK = "pakchunk0-Windows.pak"
BASE_UTOC = "pakchunk0-Windows.utoc"
NONASSET = "Wrc/Content/Gameplay/DataTables/NonAsset/"


class Unreadable(RuntimeError):
    """The game's files can't be opened: its pak isn't where the game folder should have it (Steam updating
    or verifying the game, or game_dir pointing at the wrong folder), or can't be read."""


def unreadable(cfg):
    """Why the game's files can't be read right now (no game folder; its pak or container missing, being
    updated, or locked), or None when both open."""
    if not cfg.game_dir:
        return "the game hasn't been found"
    try:
        game = GameFiles(cfg)
        game.pak, game.io
    except Unreadable as e:
        return str(e)
    except (OSError, ValueError) as e:   # there, but not a pak or container wcmods can read
        return f"the game's files can't be read: {e}"
    return None


class GameFiles:
    def __init__(self, cfg):
        self.cfg = cfg
        self._oodle = self._pak = self._io = None

    def _open(self, reader, name):
        path = os.path.join(self.cfg.paks_dir, name)
        try:
            return reader(path, self.oodle)
        except FileNotFoundError:
            raise Unreadable(f"the game's files can't be read: there's no {name} in {self.cfg.paks_dir} (is Steam "
                             "updating or verifying the game? If the game is somewhere else, Get set up asks where)") from None
        except OSError as e:
            raise Unreadable(f"the game's files can't be read: {path} ({e.strerror or e}); is Steam updating or "
                             "verifying the game?") from None

    @property
    def oodle(self):
        """The decompressor: wcmods' own, or the oo2core DLL wcmods.json names (wcmods' own when that
        DLL can't be loaded, with a line on stderr)."""
        if self._oodle is None:
            dll = self.cfg.oodle_dll
            try:
                self._oodle = Oodle(dll)
            except (OSError, AttributeError) as e:   # can't be loaded, or isn't an oo2core DLL
                print(f"wcmods: couldn't load the Oodle DLL {dll} ({e}); decoding in Python instead", file=sys.stderr)
                self._oodle = Oodle()
        return self._oodle

    @property
    def pak(self):
        if self._pak is None:
            self._pak = self._open(PakReader, BASE_PAK)
        return self._pak

    @property
    def io(self):
        if self._io is None:
            self._io = self._open(IoStoreReader, BASE_UTOC)
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
