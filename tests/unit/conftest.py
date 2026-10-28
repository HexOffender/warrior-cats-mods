"""The sandbox every unit test runs in, and the fixtures the studio's tests build on.

Nothing here reaches the real machine: the game isn't looked for (Steam, the registry), the game is never
"running", nothing is opened in Explorer or the browser, the studio's inbox and caches are in the test's own
folder, and config.data_dir() (the player's own folder, %LOCALAPPDATA%\\WCMods) points at a folder of this
run's own, which has to be empty when the run ends.
"""
import json
import os
import sys
import tempfile

# Set before anything imports wcmods: whatever a test forgets, the player's own folder is never touched.
SANDBOX = tempfile.mkdtemp(prefix="wcmods-tests-data-")
os.environ["WCMODS_DATA"] = SANDBOX
os.environ.pop("WCMODS_GAME_BUILD", None)      # a build number a developer set to try an update
os.environ.pop("WCMODS_FAKE_RUNNING", None)    # the e2e tests' stand-in for the game running: not here

import pytest  # noqa: E402

from unit_helpers import REPO, SAVE, write_save  # noqa: E402 - plain helpers; tests import them from there too


def pytest_sessionfinish(session, exitstatus):
    """The run fails when anything was written to the player's folder stand-in."""
    left = sorted(os.listdir(SANDBOX)) if os.path.isdir(SANDBOX) else []
    if left:
        print(f"\nERROR: the tests wrote into the player's own folder (its stand-in {SANDBOX}): {left}", file=sys.stderr)
        session.exitstatus = 1
    else:
        os.rmdir(SANDBOX)


@pytest.fixture
def players_folder():
    """The stand-in for the player's own folder (WCMODS_DATA) this run made, which has to stay empty."""
    return SANDBOX


class Sandbox:
    """What the tests may change about the pretend machine: whether the game "runs", and what was opened."""

    def __init__(self):
        self.running = False
        self.opened = []   # folders and URLs the studio asked the machine to open


@pytest.fixture(autouse=True)
def sandbox(monkeypatch, tmp_path):
    import webbrowser
    from wcmods import cli, config, onboarding, pipeline, studio   # noqa: F401 - each binds game_running by name
    from wcmods.exe import gamebuild
    box = Sandbox()
    monkeypatch.setattr(config, "_find_game_dir", lambda: None)        # as on a computer without the game in Steam
    monkeypatch.setattr(config, "_steam_library_dirs", lambda: [])    # so steam_game_dir() is None too (a test
    # that makes up a Steam library of its own, selftest._steam_copy, puts its own list here)
    real = config.game_running
    for module in [m for n, m in list(sys.modules.items()) if n.startswith("wcmods")]:
        if getattr(module, "game_running", None) is real:
            monkeypatch.setattr(module, "game_running", lambda: box.running)
    monkeypatch.setattr(onboarding, "INBOX", str(tmp_path / "inbox.json"))
    monkeypatch.setattr(gamebuild, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(webbrowser, "open", lambda url, *a, **k: box.opened.append(url) or True)
    monkeypatch.setattr(os, "startfile", lambda path, *a, **k: box.opened.append(path), raising=False)
    return box


@pytest.fixture
def studio(tmp_path, sandbox):
    """A Studio over a Ctx whose root, data folder and saves are all under tmp_path (as cli.main builds one,
    from Ctx(root, data)); its static folder is the real studio/, for the handler's pages."""
    from wcmods.cli import Ctx
    from wcmods.studio import Studio
    root, data, saves = tmp_path / "root", tmp_path / "data", tmp_path / "Saves"
    for d in (root, data, saves):
        d.mkdir()
    with open(data / "wcmods.json", "w", encoding="utf-8") as f:
        json.dump({"save_dir": str(saves)}, f)
    st = Studio(Ctx(str(root), str(data)))
    st.static = os.path.join(REPO, "studio")
    return st


@pytest.fixture
def fake_game(tmp_path, studio):
    """A game folder with the exe, UE4SS's mods folder and the paks folder (no paks), named in wcmods.json:
    config.is_game_dir says yes, and anything reading the game's files finds nothing to read."""
    from wcmods.config import EXE_NAME
    game = tmp_path / "Game"
    win64 = game / "Wrc" / "Binaries" / "Win64"
    (win64 / "ue4ss" / "Mods").mkdir(parents=True)
    (game / "Wrc" / "Content" / "Paks").mkdir(parents=True)
    (win64 / EXE_NAME).write_bytes(b"")
    cfg = studio.ctx.cfg
    cfg.data["game_dir"] = str(game)
    cfg.save()
    return str(game)


@pytest.fixture
def save(studio):
    """A small save in the studio's saves folder: your cat and one warrior, with keyboard and gamepad
    bindings. Returns the JSON it holds."""
    write_save(studio.ctx.cfg.save_dir)
    return SAVE
