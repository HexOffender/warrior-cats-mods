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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# A cat as the save keeps it, with its colour slots, scars and look: your cat (a leader) and one warrior.
CAT = ('(ClanType=RiverClan,Role={role},PrefixNameId="{prefix}",SuffixNameId="{suffix}",FurColorIdx=3,'
       'Pattern01ColorIdx=5,Pattern02ColorIdx=7,EyeLeftColorIdx=2,EyeRightColorIdx=4,ScarEarId=1,BodyValue=2,'
       'FurIdx=2,TailIdx=1,EarIdx=0,EyeValue=3,PatternIdx=4,CatSize=1.1)')
SAVE = {"acct": {
    "0": {"GameplayProgression": {"Gameplay.Combat.Character.Cat.Player": {
              "Customization": CAT.format(role="Leader", prefix="STR_CAT_NAME1", suffix="_STAR")}},
          "NPCData": {"RiverClan": {"Warrior": [CAT.format(role="Warrior", prefix="STR_CAT_NAME2", suffix="_HEART")]}}},
    "Shared": {"General": {"CurrentCatSlot": 0},
               "InputKeyboard": {"Player_Interact": "0,Player_Interact,E,1.000000.1",
                                 "Player_Jump": "0,Player_Jump,SpaceBar,1.000000.1"},
               "InputGamepad": {"Player_Jump": "0,Player_Jump,Gamepad_FaceButton_Bottom,1.000000.1"}}}}


def pytest_sessionfinish(session, exitstatus):
    """The run fails when anything was written to the player's folder stand-in."""
    left = sorted(os.listdir(SANDBOX)) if os.path.isdir(SANDBOX) else []
    if left:
        print(f"\nERROR: the tests wrote into the player's own folder (its stand-in {SANDBOX}): {left}", file=sys.stderr)
        session.exitstatus = 1
    else:
        os.rmdir(SANDBOX)


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


def write_save(folder, data=SAVE):
    """WrcGame.sav holding `data` in folder, laid out as the game lays out its saves."""
    from wcmods.selftest import _small_save
    from wcmods.formats.save import SAV_NAME
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, SAV_NAME)
    with open(path, "wb") as f:
        f.write(_small_save(json.dumps(data)))
    return path


@pytest.fixture
def save(studio):
    """A small save in the studio's saves folder: your cat and one warrior, with keyboard and gamepad
    bindings. Returns the JSON it holds."""
    write_save(studio.ctx.cfg.save_dir)
    return SAVE


EYE_LABELS = ["Sclera", "Yellow", "Amber", "Hazel", "Copper", "Green", "Olive", "Mint", "Teal", "Sky", "Blue", "Ice",
              "Grey", "Silver", "Violet", "Lilac", "Rose", "Red", "Brown", "Black", "White",
              "Dlc1", "Dlc2", "Dlc3", "Dlc4", "Dlc5"]


def eye_atlas(width=64, labels=EYE_LABELS):
    """An eye atlas as wcmods.eyeatlas.EyeAtlas reads one, made up: a row per label, 64 half-float RGBA pixels
    each. Row 0 (the eye white) is flat; the others ramp up from black at the pupil (x 0) to a colour of their
    own at the rim, alpha 1 throughout. The pixels are its whole data, so pixel_offset is 0."""
    import struct
    from wcmods import eyeatlas
    atlas = eyeatlas.EyeAtlas.__new__(eyeatlas.EyeAtlas)
    atlas.labels, atlas.width, atlas.height, atlas.pixel_offset = list(labels), width, len(labels), 0
    atlas.data = bytearray(width * len(labels) * 8)
    for r in range(len(labels)):
        rim = (0.8, 0.8, 0.75) if r == 0 else (0.02 * r, 0.5, 1.0 - 0.03 * r)
        for x in range(width):
            s = 1.0 if r == 0 else x / (width - 1)
            struct.pack_into("<4e", atlas.data, (r * width + x) * 8, rim[0] * s, rim[1] * s, rim[2] * s, 1.0)
    return atlas


def make_mod(studio, mod_id, meta=None, files=None):
    """A mod folder in the studio's mods: mod.json from `meta` (on, unless it says), and `files`
    ({name: text, bytes or JSON-able value}) beside it. Returns the folder."""
    folder = os.path.join(studio.ctx.mods_root, mod_id)
    os.makedirs(folder)
    with open(os.path.join(folder, "mod.json"), "w", encoding="utf-8") as f:
        json.dump({"name": mod_id.replace("-", " ").title(), "enabled": True, **(meta or {})}, f)
    for name, content in (files or {}).items():
        path = os.path.join(folder, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if isinstance(content, bytes):
            with open(path, "wb") as f:
                f.write(content)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content if isinstance(content, str) else json.dumps(content))
    return folder
