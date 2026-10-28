"""Models of a mod's own for accessories (models.py, formats/skelmesh.py's morph data, the items section's
"model"), without the game: reading OBJ and glTF into the game's space, writing OBJ, tangents, the morph
codec, and tying a model to a body. The game's own meshes are checked by `python wcmods.py selftest`."""
import base64
import json
import math
import random
import struct

import pytest

from wcmods import luacheck, models
from wcmods.formats import skelmesh
from wcmods.sections.items import PICKUPS, Game, ItemsSection, ModelFile, Plain, items_lua


def close(a, b, eps=1e-4):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


# ------------------------------------------------------------------------------------------------- OBJ
def test_obj_reads_into_the_games_space():
    # A square in metres, Y up, facing +Z (the cat's front), as Blender writes it: a quad with relative
    # indices and no normals, UVs with V up the picture.
    text = """# a square
v 0 0 0
v 0.1 0 0
v 0.1 0.1 0
v 0 0.1 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
f -4/-4 -3/-3 -2/-2 -1/-1
"""
    m = models.read("square.obj", text.encode())
    assert len(m.triangles) == 2 and len(m.positions) == 4
    # (x, y, z) metres -> (100 x, 100 z, 100 y) cm: up is the game's Z, the file's +Z its +Y.
    assert close(m.positions[2], (10.0, 0.0, 10.0))
    assert close(m.uvs[0], (0.0, 1.0)) and close(m.uvs[2], (1.0, 0.0))          # V flipped for the game
    # Counter-clockwise in the file, so the face's normal is the file's +Z: the game's +Y.
    assert all(close(n, (0.0, 1.0, 0.0)) for n in m.normals)
    # ...and the game's clockwise rule agrees: v x u along the normal.
    a, b, c = (m.positions[i] for i in m.triangles[0])
    u, v = [b[k] - a[k] for k in range(3)], [c[k] - a[k] for k in range(3)]
    outside = (v[1] * u[2] - v[2] * u[1], v[2] * u[0] - v[0] * u[2], v[0] * u[1] - v[1] * u[0])
    assert outside[1] > 0


def test_obj_written_reads_back():
    geo = {"positions": [(1.0, 2.0, 3.0), (4.0, 2.0, 3.0), (1.0, 6.0, 3.0)], "normals": [(0.0, 0.0, 1.0)] * 3,
           "uvs": [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], "triangles": [(0, 1, 2)]}
    m = models.read("t.obj", models.write_obj("t", geo, material="t").encode())
    assert m.triangles == [(0, 1, 2)]
    assert all(close(a, b) for a, b in zip(m.positions, geo["positions"]))
    assert all(close(a, b) for a, b in zip(m.uvs, geo["uvs"]))
    assert all(close(a, b) for a, b in zip(m.normals, geo["normals"]))


def test_models_that_cant_be_used_are_refused():
    with pytest.raises(ValueError, match="no triangles"):
        models.read("empty.obj", b"v 0 0 0\nv 1 0 0\n")
    with pytest.raises(ValueError, match="hasn't got"):
        models.read("bad.obj", b"v 0 0 0\nf 1 2 3\n")
    with pytest.raises(ValueError, match=".obj"):
        models.read("model.fbx", b"x")
    with pytest.raises(ValueError, match="glb"):
        models.read("outside.gltf", json.dumps({"asset": {"version": "2.0"}, "buffers": [{"uri": "data.bin", "byteLength": 4}],
                                                "meshes": []}).encode())
    with pytest.raises(ValueError, match="compression"):
        models.read("draco.gltf", json.dumps({"asset": {"version": "2.0"},
                                              "extensionsRequired": ["KHR_draco_mesh_compression"]}).encode())
    many = "".join(f"v {i} 0 0\nv {i} 1 0\nv {i} 0 1\nf {3 * i + 1} {3 * i + 2} {3 * i + 3}\n" for i in range(22000))
    with pytest.raises(ValueError, match="Decimate"):
        models.read("big.obj", many.encode())


# ------------------------------------------------------------------------------------------------ glTF
def gltf(primitive_mode=4, matrix=None, translation=None, scale=None, binary=False, normalized_uv=False):
    """A one-triangle glTF (a strip or fan of the same corners for other modes)."""
    pos = [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.0, 0.1, 0.0)]
    blob = b"".join(struct.pack("<3f", *p) for p in pos)
    if normalized_uv:
        uvs = b"".join(struct.pack("<2H", u, v) for u, v in ((0, 0), (65535, 0), (0, 65535))) + b"\0\0"
        uv_acc = {"bufferView": 1, "componentType": 5123, "normalized": True, "count": 3, "type": "VEC2"}
    else:
        uvs = b"".join(struct.pack("<2f", u, v) for u, v in ((0, 0), (1, 0), (0, 1)))
        uv_acc = {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC2"}
    idx = struct.pack("<3H", 0, 1, 2) + b"\0\0"
    data = blob + uvs + idx
    node = {"mesh": 0}
    if matrix:
        node["matrix"] = matrix
    if translation:
        node["translation"] = translation
    if scale:
        node["scale"] = scale
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [node],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "TEXCOORD_0": 1}, "indices": 2, "mode": primitive_mode}]}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(blob)},
                           {"buffer": 0, "byteOffset": len(blob), "byteLength": len(uvs)},
                           {"buffer": 0, "byteOffset": len(blob) + len(uvs), "byteLength": 6}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}, uv_acc,
                         {"bufferView": 2, "componentType": 5123, "count": 3, "type": "SCALAR"}]}
    if binary:
        doc["buffers"] = [{"byteLength": len(data)}]
        js = json.dumps(doc).encode()
        js += b" " * (-len(js) % 4)
        return "m.glb", (struct.pack("<4sII", b"glTF", 2, 28 + len(js) + len(data)) + struct.pack("<II", len(js), 0x4E4F534A)
                         + js + struct.pack("<II", len(data), 0x004E4942) + data)
    doc["buffers"] = [{"byteLength": len(data), "uri": "data:application/octet-stream;base64," + base64.b64encode(data).decode()}]
    return "m.gltf", json.dumps(doc).encode()


@pytest.mark.parametrize("binary", [False, True])
def test_gltf_reads_like_obj(binary):
    name, data = gltf(binary=binary)
    m = models.read(name, data)
    assert m.triangles == [(0, 1, 2)]
    assert close(m.positions[1], (10.0, 0.0, 0.0)) and close(m.positions[2], (0.0, 0.0, 10.0))
    assert close(m.uvs[1], (1.0, 0.0)) and close(m.uvs[2], (0.0, 1.0))     # glTF's V runs down already
    assert close(m.normals[0], (0.0, 1.0, 0.0))


def test_gltf_node_transforms_and_normalized_uvs():
    m = models.read(*gltf(translation=[0.0, 0.2, 0.0], scale=[2.0, 2.0, 2.0], normalized_uv=True))
    assert close(m.positions[0], (0.0, 0.0, 20.0)) and close(m.positions[1], (20.0, 0.0, 20.0))
    assert close(m.uvs[1], (1.0, 0.0), 1e-3)
    # A mirrored node: its faces turn inside out, and the reader turns them back.
    mirrored = models.read(*gltf(matrix=[-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]))
    assert close(mirrored.normals[0], (0.0, 1.0, 0.0))


# -------------------------------------------------------------------------------------------- tangents
def test_tangents_follow_u_and_say_which_way_v_goes():
    m = models.Model([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 0.0, 10.0)], [(0.0, 1.0, 0.0)] * 3,
                     [(0.0, 1.0), (1.0, 1.0), (0.0, 0.0)], [(0, 1, 2)])
    t = models.tangents(m)
    assert close(t[0][:3], (1.0, 0.0, 0.0))
    flipped = models.Model(m.positions, m.normals, [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], m.triangles)
    assert models.tangents(flipped)[0][3] == -t[0][3]


# --------------------------------------------------------------------------------------------- morphs
def random_morphs(rng, n_vertices, n_morphs):
    morphs = []
    for k in range(n_morphs):
        verts = sorted(rng.sample(range(n_vertices), rng.randint(0, n_vertices)))
        tan = k % 2 == 0
        morphs.append([(v, tuple(rng.randint(-400, 400) for _ in range(3)),
                        tuple(rng.randint(-900, 900) for _ in range(3)) if tan else None) for v in verts])
    return morphs


def test_morph_data_round_trips():
    rng = random.Random(7)
    morphs = random_morphs(rng, 300, 5) + [[]]
    words, starts, counts, total = skelmesh.encode_morphs(morphs)
    assert total == sum(counts) and counts[-1] == 0
    assert words[-skelmesh.PAD_WORDS:] == [0] * skelmesh.PAD_WORDS
    assert skelmesh.decode_morphs(words, starts, counts, 0.004, 1 / 2048) == morphs
    # Batches of 64 moved vertices, the first one's data right after every header.
    assert counts[0] == math.ceil(len(morphs[0]) / skelmesh.BATCH)
    assert words[0] == total * skelmesh.HEADER_WORDS * 4


def test_morphs_keep_only_what_still_moves():
    elems = skelmesh.quantize_morph([(3, (0.0, 0.001, 0.0), None), (1, (0.01, 0.0, 0.0), (0.0, 0.0, 0.0)),
                                     (2, (0.0, 0.0, 0.0), (0.0, 0.01, 0.0))], 0.004, 1 / 2048)
    assert elems == [(1, (3, 0, 0), None), (2, (0, 0, 0), (0, 20, 0))]
    lo, hi = skelmesh.morph_extents(elems, 0.004, 1 / 2048)
    assert close(lo, (0.0, 0.0, 0.0, 0.0), 1e-6) and close(hi, (0.012, 0.0, 0.0, 20 / 2048), 1e-6)


def test_bone_weights_add_up_to_255():
    for ws in ([0.5, 0.5], [0.333, 0.333, 0.334], [0.9, 0.05, 0.03, 0.02], [1.0]):
        q = skelmesh._byte_weights(ws)
        assert sum(q) == 255 and all(0 <= x <= 255 for x in q)


# ---------------------------------------------------------------------------------------- the cat's skin
class FakeBody:
    """A body for Skin: points on a line, each tied to its own bone, and one morph that lifts them."""

    def __init__(self, n=40):
        positions = [(float(i), 0.0, 0.0) for i in range(n)]
        self.lods = [type("Lod", (), {"sections": [type("Section", (), {"base_vertex": 0, "vertices": n})()]})()]
        self.geo = {"positions": positions, "weights": [[(i, 1.0)] for i in range(n)],
                    "morphs": {"SHP_Up": {i: ((0.0, 0.0, 1.0), None) for i in range(n)}}}

    def geometry(self, lod=0):
        return self.geo


def test_skin_finds_the_nearest_points():
    skin = models.Skin(FakeBody(), ["SHP_Up"])
    rng = random.Random(3)
    for _ in range(50):
        p = (rng.uniform(-5, 45), rng.uniform(-8, 8), rng.uniform(-8, 8))
        want = sorted((math.dist(p, q), i) for i, q in enumerate(skin.positions))[:models.NEAREST]
        got = skin.nearest(p)
        assert [i for _, i in got] == [i for _, i in want]


def test_a_model_takes_the_weights_and_morphs_of_the_skin_under_it():
    skin = models.Skin(FakeBody(), ["SHP_Up", "SHP_None"])
    m = models.Model([(10.0, 0.0, 0.5), (10.5, 0.0, 0.5), (30.0, 0.0, 2.0)], [(0.0, 0.0, 1.0)] * 3,
                     [(0.0, 0.0)] * 3, [(0, 1, 2)])
    weights, morphs, farthest = skin.bind(m)
    assert all(abs(sum(w for _, w in ws) - 1.0) < 1e-9 for ws in weights)
    assert weights[0][0][0] == 10 and weights[2][0][0] == 30          # mostly the bone right under it
    assert [v for v, _, _ in morphs["SHP_Up"]] == [0, 1, 2] and close(morphs["SHP_Up"][0][1], (0.0, 0.0, 1.0))
    assert morphs["SHP_None"] == [] and 1.9 < farthest < 2.1


# ------------------------------------------------------------------------------- the items section
def test_the_models_script_knows_each_look():
    lua = models.script({"Neck": {"DogCollar": {3: {"mesh": "/Game/WCMods/m/SK_A.SK_A"},
                                                4: {"opacity": 0.5, "glass": [1.0, 0.5, 0.25]}}}})
    assert not luacheck.check(lua) and "@MODELS@" not in lua
    assert '["3"] = { ["mesh"] = "/Game/WCMods/m/SK_A.SK_A" }' in lua
    assert '["4"] = { ["opacity"] = 0.5, ["glass"] = { 1.0, 0.5, 0.25 } }' in lua
    # Only the HUD's picture is taken again, and a slot with no model is never asked for a material.
    assert '"RT_UI_Portrait_Exploration"' in lua and "CaptureComponentInventory" not in lua
    assert "c.SkinnedAsset" in lua


# ------------------------------------------------------------------------------------------------ placing
def square():
    """A 2 x 2 cm square around (0, 10, 20), facing the cat's front."""
    return models.Model([(-1.0, 10.0, 19.0), (1.0, 10.0, 19.0), (1.0, 10.0, 21.0), (-1.0, 10.0, 21.0)],
                        [(0.0, 1.0, 0.0)] * 4, [(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 1, 2), (0, 2, 3)])


def test_placing_moves_turns_and_scales_about_the_middle():
    m = square()
    moved = models.place(m, {"forward": 2, "up": -1, "left": 0.5})
    assert close(moved.positions[0], (-0.5, 12.0, 18.0)) and moved.triangles == m.triangles
    bigger = models.place(m, {"scale": 2})
    assert close(bigger.positions[0], (-2.0, 10.0, 18.0)) and close(bigger.normals[0], (0.0, 1.0, 0.0))
    # Yaw turns its front toward the cat's left (+X), pitch raises it, roll lowers the left side.
    assert close(models.place(m, {"yaw": 90}).normals[0], (1.0, 0.0, 0.0))
    assert close(models.place(m, {"pitch": 90}).normals[0], (0.0, 0.0, 1.0))
    rolled = models.place(m, {"roll": 90})
    assert close(rolled.positions[2], (1.0, 10.0, 19.0))           # its top corner on the left goes down
    # Stretched one way, its normals stay square to the face.
    tall = models.place(models.Model([(0, 0, 0), (1, 0, 1), (0, 1, 0)], [models._unit((-1.0, 0.0, 1.0))] * 3,
                                     [(0, 0)] * 3, [(0, 1, 2)]), {"scale": {"up": 2}})
    a, b, c = tall.positions
    edge = [b[k] - a[k] for k in range(3)]
    assert abs(sum(edge[k] * tall.normals[0][k] for k in range(3))) < 1e-9
    assert models.place(m, None) is m and models.place(m, {}) is m


@pytest.mark.parametrize("place, message", [
    ({"up": "a lot"}, "up should be a number"), ({"forward": 500}, "-100 to 100"), ({"spin": 3}, "unknown"),
    ({"scale": 0}, "scale should be"), ({"scale": {"tall": 2}}, "forward, up and left"), ([1, 2], "an object")])
def test_places_that_cant_be_used_are_refused(place, message):
    with pytest.raises(ValueError, match=message):
        models.check_place(place, "items.json: item 1")


def test_items_json_model_must_be_a_model_file(tmp_path):
    mod = type("Mod", (), {"id": "m", "folder": str(tmp_path)})()
    (tmp_path / "items.json").write_text(json.dumps({"items": [{"id": "A", "like": "Neck.DogCollar.1", "name": "a",
                                                                "description": "a", "model": "models/a.fbx"}]}))
    with pytest.raises(ValueError, match="model file"):
        ItemsSection().collect(mod, None)
    for extra, message in (({"opacity": 1.5}, "from 0"), ({"opacity": 0.5, "glass": "glassy"}, "colour like"),
                           ({"place": {"up": True}}, "up should be a number")):
        (tmp_path / "items.json").write_text(json.dumps({"items": [dict(
            {"id": "A", "like": "Neck.DogCollar.1", "name": "a", "description": "a"}, **extra)]}))
        with pytest.raises(ValueError, match=message):
            ItemsSection().collect(mod, None)
    outside = ModelFile("../elsewhere/a.obj")
    with pytest.raises(ValueError, match="own folder"):
        outside.read(mod)
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "a.obj").write_text("v 0 0 0\nv 0.1 0 0\nv 0 0.1 0\nf 1 2 3\n")
    inside = ModelFile("models/a.obj")
    assert inside.read(mod).summary()["triangles"] == 1
    key = inside.key(mod)
    (tmp_path / "models" / "a.obj").write_text("v 0 0 0\nv 0.2 0 0\nv 0 0.1 0\nf 1 2 3\n")
    assert inside.key(mod) != key                         # a changed model is made into a mesh again


# --------------------------------------------------------------------------------------- on the ground
def test_a_model_on_the_ground_stays_as_it_is_on_the_root_bone():
    m = square()
    geo = models.rigid_model(m)
    assert geo["positions"] == m.positions and geo["triangles"] == m.triangles and geo["morphs"] == {}
    assert geo["weights"] == [[(0, 1.0)]] * 4 and len(geo["tangents"]) == 4


class FakeGameFiles:
    def find(self, pattern):
        return [PICKUPS + "MediumHealingHerb.uasset", PICKUPS + "SmallHealingHerb.uasset"]


def test_herbs_lie_on_the_ground_as_their_model_or_as_the_game_pickup_of_what_theyre_like():
    game = object.__new__(Game)
    game.ctx, game._pickups = type("Ctx", (), {"game": FakeGameFiles()})(), None
    own = game.pickup({"model": "models/moon.obj", "texture": "pictures/moon.png"},
                      "Gameplay.Inventory.Consumable.MediumHealingHerb")
    assert own["model"].rel == "models/moon.obj" and own["picture"].rel == "pictures/moon.png"
    assert own["class"] == "MediumHealingHerb"
    assert game.pickup({}, "Gameplay.Inventory.Materials.Moss") == {"model": None, "picture": None, "class": None}
    for item, message in (({"texture": "a.png"}, 'goes with a "model"'), ({"place": {"up": 1}}, 'goes with a "model"'),
                          ({"model": "a.obj", "texture": {"tint": "#ffffff"}}, r"a picture \(a PNG\)")):
        with pytest.raises(ValueError, match=message):
            game.pickup(item, None)


def test_the_items_module_says_how_each_item_lies_on_the_ground():
    lua = items_lua({"Gameplay.Inventory.Consumable.Moon": {"mesh": "/Game/WCMods/m/A.A", "texture": "/Game/WCMods/m/B.B",
                                                            "class": "MediumHealingHerb"},
                     "Gameplay.Inventory.Consumable.Sun": {"class": "BigHealingHerb"}})
    assert not luacheck.check(lua) and lua.startswith("-- Written by wcmods")
    assert '["Gameplay.Inventory.Consumable.Moon"] = { ["mesh"] = "/Game/WCMods/m/A.A"' in lua
    assert 'return { pickups = {' in lua and '["Gameplay.Inventory.Consumable.Sun"] = { ["class"] = "BigHealingHerb" }' in lua


def test_a_plain_picture_is_as_big_as_its_texture():
    w, h, rgba = Plain((1, 2, 3), size=8).read()
    assert (w, h) == (8, 8) and len(rgba) == 8 * 8 * 4 and rgba[:8] == bytes((1, 2, 3, 255)) * 2
    assert Plain((1, 2, 3)).key() == "plain|1,2,3"


def test_a_model_on_the_ground_grows_and_turns_about_its_base():
    block = models.Model([(-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (1.0, 1.0, 2.0), (-1.0, 1.0, 2.0)],
                         [(0.0, 0.0, 1.0)] * 4, [(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 1, 2), (0, 2, 3)])
    bigger = models.place(block, {"scale": 2}, base=True)
    assert min(p[2] for p in bigger.positions) == 0.0 and max(p[2] for p in bigger.positions) == 4.0
    assert min(p[2] for p in models.place(block, {"scale": 2}).positions) == -1.0     # about its middle, it sinks
    geo = models.rigid_model(block)
    geo["weights"][0].append((1, 0.0))
    assert geo["weights"][1] == [(0, 1.0)]                 # each vertex has its own list
