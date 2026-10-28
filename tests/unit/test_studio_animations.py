"""The Animations page's routes (wcmods/studio.py), on a studio over temporary folders with the game's skeleton
stubbed to test_animations.py's small one: uploads that never land on another animation's file, the files the
page can't take said in its words, the game's sequences listed by their plain names even when one can't be
read, and Try it on my cat through the game bridge (stubbed)."""
import json
import os

import pytest

from wcmods import animations as A
from wcmods import studio as studio_mod
from wcmods.formats import anim

from unit_helpers import make_mod
from test_animations import Mesh, Skel, column, gltf_file, motion


def call(st, method, path, body=None, query=None, upload=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, query, upload)


@pytest.fixture
def toy(studio, monkeypatch):
    """The studio, with every kind's skeleton the toy one."""
    monkeypatch.setattr(studio, "_skeleton", lambda kind: Skel())
    return studio


def kit_file(path, seconds=None):
    """A .glb as the start kit makes it, with one animation; or a .gltf `seconds` long."""
    skel = Skel()
    if seconds is None:
        bones = A.track_bones(skel)
        path.write_bytes(A.write_rig(skel, Mesh(), [("Wag", bones, motion(skel, bones, 7), 30.0)], "test"))
    else:
        path.write_bytes(gltf_file([{"name": "spine"}], [(0, "rotation", [(0, 0, 0, 1), (0, 0, 0, 1)])],
                                   {0: column(A.IDENTITY)}, [0.0, seconds]))
    return str(path)


def test_uploads_never_overwrite_another_animations_file(toy, tmp_path):
    folder = make_mod(toy, "mine")
    q = {"name": "Wave", "file": "wave.glb", "for": "cat"}
    first = call(toy, "POST", "mods/mine/animation", query=q, upload=kit_file(tmp_path / "a.glb"))
    second = call(toy, "POST", "mods/mine/animation", query=q, upload=kit_file(tmp_path / "b.glb"))
    assert (first["path"], second["path"]) == ("animations/Wave.glb", "animations/Wave-2.glb")
    assert [c["name"] for c in first["clips"]] == ["Wag"] and first["max_seconds"] == A.MAX_SECONDS
    # Ids that differ only in case are one file on Windows: a free name all the same.
    third = call(toy, "POST", "mods/mine/animation", query=dict(q, name="wave"), upload=kit_file(tmp_path / "c.glb"))
    assert third["path"] == "animations/wave-3.glb"
    # Choosing again for the same animation keeps its file's name.
    again = call(toy, "POST", "mods/mine/animation", query=dict(q, current="animations/Wave-2.glb"), upload=kit_file(tmp_path / "d.glb"))
    assert again["path"] == "animations/Wave-2.glb"
    assert sorted(os.listdir(os.path.join(folder, "animations"))) == ["Wave-2.glb", "Wave.glb", "wave-3.glb"]


def test_a_separate_gltf_is_refused_with_the_blender_step(toy, tmp_path):
    make_mod(toy, "mine")
    apart = tmp_path / "wave.gltf"
    apart.write_text(json.dumps({"asset": {"version": "2.0"}, "nodes": [{"name": "spine"}],
                                 "buffers": [{"byteLength": 8, "uri": "wave.bin"}]}))
    with pytest.raises(ValueError) as e:
        call(toy, "POST", "mods/mine/animation", query={"name": "Wave", "file": "wave.gltf"}, upload=str(apart))
    assert str(e.value) == "that .gltf keeps its animation in wave.bin: in Blender, export it again as glTF Binary (.glb); the page takes one file"
    assert not os.path.isdir(os.path.join(toy.ctx.mods_root, "mine", "animations"))
    # One with its data inside is taken.
    inside = tmp_path / "inside.gltf"
    kit_file(inside, seconds=2.0)
    assert call(toy, "POST", "mods/mine/animation", query={"name": "Nod", "file": "inside.gltf"}, upload=str(inside))["path"] == "animations/Nod.gltf"


def test_a_file_too_long_is_refused_at_upload(toy, tmp_path):
    make_mod(toy, "mine")
    long = tmp_path / "long.gltf"
    kit_file(long, seconds=70.0)
    with pytest.raises(ValueError) as e:
        call(toy, "POST", "mods/mine/animation", query={"name": "Long", "file": "long.gltf"}, upload=str(long))
    assert str(e.value) == "Wave is 70.0 s long; an animation can be up to 60 s: shorten it in Blender"
    # The page learns which are too long when one file has both.
    info = A.describe("x.gltf", long.read_bytes(), "cat", Skel())
    assert info["clips"] == [{"name": "Wave", "seconds": 70.0, "too_long": True}] and info["max_seconds"] == 60


def test_animation_info_never_reads_outside_the_mod(toy, tmp_path):
    folder = make_mod(toy, "mine")
    os.makedirs(os.path.join(folder, "animations"))
    with open(os.path.join(folder, "animations", "wag.glb"), "wb") as f:
        f.write(open(kit_file(tmp_path / "w.glb"), "rb").read())
    got = call(toy, "GET", "mods/mine/animation-info", query={"path": "animations/wag.glb", "for": "cat"})
    assert [c["name"] for c in got["clips"]] == ["Wag"]
    for bad in ("../../data/wcmods.json", "animations/none.glb", os.path.join(folder, "..", "x.glb")):
        with pytest.raises(LookupError, match="has no animation"):
            call(toy, "GET", "mods/mine/animation-info", query={"path": bad, "for": "cat"})


class Game:
    """The game's files for anim_sequences: four of the cats' sequences, one of which can't be read at all."""
    files = ["Wrc/Content/Art/Characters/CatMaster/Animations/A_CatMaster_Yawn_1.uasset",
             "Wrc/Content/Art/Characters/CatMaster/Animations/A_CatMaster_Broken_1.uasset",
             "Wrc/Content/Art/Characters/CatMaster/Animations/PhotoMode/A_CatMaster_Pose_Photo_Mode_9.uasset",
             "Wrc/Content/Art/Characters/CatMaster/Animations/A_CatMaster_Stand_1_c.uasset"]

    def __init__(self):
        self.io = type("IO", (), {"files": self.files})()

    def read(self, path):
        if "Broken" in path:
            raise RuntimeError("a container block that won't decompress")   # not one of the errors a reader expects
        raise anim.FormatError("not a sequence")


def test_anim_sequences_skips_an_asset_it_cant_read(studio, fake_game, monkeypatch):
    studio.ctx._game = Game()
    monkeypatch.setattr(studio, "_reader", lambda: type("Reader", (), {"text": lambda self, key: {"STR_PHOTOMODE_POSE_9": "Floof Nap"}.get(key, key)})())
    got = {s["name"]: s for s in call(studio, "GET", "game/anim-sequences", query={"for": "cat"})["sequences"]}
    assert sorted(got) == ["A_CatMaster_Broken_1", "A_CatMaster_Pose_Photo_Mode_9", "A_CatMaster_Stand_1_c", "A_CatMaster_Yawn_1"]
    assert got["A_CatMaster_Broken_1"]["additive"] is False, "listed all the same: the install says so if it's chosen"
    assert (got["A_CatMaster_Yawn_1"]["label"], got["A_CatMaster_Yawn_1"]["group"]) == ("Yawn", "everyday")
    assert (got["A_CatMaster_Pose_Photo_Mode_9"]["label"], got["A_CatMaster_Pose_Photo_Mode_9"]["group"]) == ("Floof Nap", "poses")
    assert (got["A_CatMaster_Stand_1_c"]["label"], got["A_CatMaster_Stand_1_c"]["group"]) == (None, None), "not watched yet"


class Bridge:
    """The game bridge: alive or not, and what it answers."""
    alive, reply, ran = True, {"ok": True, "result": [True]}, []

    def __init__(self, cfg):
        pass

    def status(self):
        return {"alive": Bridge.alive}

    def run(self, code, timeout=15):
        Bridge.ran.append(code)
        return Bridge.reply


def test_try_anim_plays_a_game_path_through_the_bridge(studio, monkeypatch):
    monkeypatch.setattr(studio_mod, "Bridge", Bridge)
    yawn = "/Game/Art/Characters/CatMaster/Animations/A_CatMaster_Yawn_1"
    with pytest.raises(PermissionError, match="allow mods that run code first"):
        call(studio, "POST", "game/try-anim", {"path": yawn})
    studio.ctx.cfg.data["allow_code_mods"] = True
    for bad in ("A_CatMaster_Yawn_1", "/Game/WCMods/x/../A_Y", "my-mod/Wave", '/Game/A_X"); os.exit() --'):
        with pytest.raises(ValueError, match="only one of the game's own animations"):
            call(studio, "POST", "game/try-anim", {"path": bad})
    assert call(studio, "POST", "game/try-anim", {"path": yawn}) == {"played": yawn + ".A_CatMaster_Yawn_1"}
    assert f'Game.anims.play(nil, "{yawn}.A_CatMaster_Yawn_1")' in Bridge.ran[-1]
    Bridge.reply = {"ok": True, "result": ["there's no one to play it on"]}
    with pytest.raises(RuntimeError, match="it didn't play: there's no one to play it on"):
        call(studio, "POST", "game/try-anim", {"path": yawn})
    Bridge.alive = False
    with pytest.raises(RuntimeError) as e:
        call(studio, "POST", "game/try-anim", {"path": yawn})
    assert "press Play" in str(e.value) and "wcmods" not in str(e.value), "no command line"
