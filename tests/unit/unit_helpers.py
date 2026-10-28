"""What the unit tests share besides fixtures: the repository's folder, a small save, a made-up eye atlas, and
the helpers that write a save or a mod into a test's folders. Imported by name (`from unit_helpers import make_mod`), which
works in any of pytest's import modes, as pyproject.toml puts tests/unit on the path; conftest.py is never
imported that way, as importing it a second time would make a second stand-in for the player's folder.
Nothing here runs anything as it's imported."""
import json
import os

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


def write_save(folder, data=SAVE):
    """WrcGame.sav holding `data` in folder, laid out as the game lays out its saves."""
    from wcmods.selftest import _small_save
    from wcmods.formats.save import SAV_NAME
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, SAV_NAME)
    with open(path, "wb") as f:
        f.write(_small_save(json.dumps(data)))
    return path


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
