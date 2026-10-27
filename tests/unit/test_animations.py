"""Animations of a mod's own (animations.py, formats/anim.py, the animations section), without the game: the two
spaces, glTF clips onto the game's bones (a start kit's, and one with Blender's bone frames and an armature node
over them), the per-track codec, a sequence's properties, animations.json and the Lua the install writes. The
game's own sequences and skeletons are checked by `python wcmods.py selftest`."""
import base64
import json
import math
import random
import struct

import pytest

from wcmods import animations as A
from wcmods import luacheck
from wcmods.formats import anim
from wcmods.formats.cooked import NAME_HASH_VERSION, write_header
from wcmods.formats.cityhash import name_hash
from wcmods.lua import source
from wcmods.sections.animations import AnimationsSection, check


def close(a, b, eps=1e-6):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


def same_rotation(a, b, eps=1e-6):
    return abs(abs(sum(x * y for x, y in zip(a, b))) - 1) <= eps


def unit(q):
    n = math.sqrt(sum(x * x for x in q))
    return tuple(x / n for x in q)


def turn(axis, degrees):
    h = math.radians(degrees) / 2
    return (axis[0] * math.sin(h), axis[1] * math.sin(h), axis[2] * math.sin(h), math.cos(h))


class Skel:
    """A small skeleton: root, a spine bone up and forward, a tail bone off its back, Camera_ref (left out)."""

    def __init__(self):
        self.bones = [("root", -1), ("spine", 0), ("tail", 1), ("Camera_ref", 0)]
        self.poses = [((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)),
                      ((0.0, -10.0, 15.0), unit((0.7, 0.0, 0.0, -0.7)), (1.0, 1.0, 1.0)),
                      ((0.0, -4.0, 0.0), unit((0.1, 0.2, 0.0, -0.97)), (1.0, 1.0, 1.0)),
                      ((0.0, 14.0, 20.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0))]

    def index(self, name):
        return next((i for i, (n, _) in enumerate(self.bones) if n.lower() == name.lower()), None)


class Mesh:
    """A triangle skinned to the spine and the tail, as skelmesh's geometry() gives one (its own bone order),
    resting with its tail turned round from the skeleton's (as the rabbit's right ear is), in skelmesh's
    poses (rotation, translation, scale: 10 numbers)."""
    bones = [("tail", 1), ("spine", -1)]

    def __init__(self):
        skel = Skel()
        tail = A._decompose(A._mul(A._trs(*skel.poses[2]), A._trs((0, 0, 0), turn((0, 1, 0), 180), (1, 1, 1))))
        self.poses = [tuple(tail[1]) + tuple(tail[0]) + (1.0, 1.0, 1.0),
                      tuple(skel.poses[1][1]) + tuple(skel.poses[1][0]) + (1.0, 1.0, 1.0)]

    def geometry(self, lod=0):
        return {"positions": [(0.0, -10.0, 15.0), (0.0, -14.0, 15.0), (1.0, -12.0, 16.0)],
                "normals": [(1.0, 0.0, 0.0)] * 3, "uvs": [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
                "triangles": [(0, 1, 2)], "weights": [[(1, 1.0)], [(0, 1.0)], [(0, 0.5), (1, 0.5)]]}


def motion(skel, bones, n, seed=1):
    """Keys for the bones: their reference pose, turned and moved a little more each key."""
    rnd = random.Random(seed)
    out = []
    for b in bones:
        t0, q0, s0 = skel.poses[b]
        axis = unit((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)) + (0.0,))[:3]
        T, Q, S = [], [], []
        for k in range(n):
            T.append(tuple(v + 0.5 * k * (c + 1) for c, v in enumerate(t0)))
            Q.append(A._decompose(A._mul(A._trs((0, 0, 0), q0, (1, 1, 1)), A._trs((0, 0, 0), turn(axis, 9 * k), (1, 1, 1))))[1])
            S.append(s0)
        out.append((T, Q, S))
    return out


# ------------------------------------------------------------------------------------------- the two spaces
def test_a_transform_and_its_parts_go_to_the_games_space_alike():
    rnd = random.Random(3)
    for _ in range(50):
        t = tuple(rnd.uniform(-1, 1) for _ in range(3))
        q = unit(tuple(rnd.uniform(-1, 1) for _ in range(4)))
        s = tuple(rnd.uniform(0.5, 2) for _ in range(3))
        whole = A.m_to_game(A._trs(t, q, s))
        parts = A._trs(A.t_to_game(t), A.q_swap(q), A.s_swap(s))
        assert close(whole[0] + whole[1], parts[0] + parts[1], 1e-9)
        assert close(A.m_from_game(whole)[1], t, 1e-12)
    # A metre up in a file (+Y) is 100 cm up in the game (+Z); the file's front (+Z) the game's (+Y).
    assert A.t_to_game((0, 1, 0)) == (0, 0, 100) and A.t_to_game((0, 0, 1)) == (0, 100, 0)


def test_transforms_decompose_into_what_made_them():
    t, q, s = (1.0, -2.0, 3.0), unit((0.3, -0.1, 0.5, 0.8)), (1.0, 2.0, 0.5)
    t2, q2, s2 = A._decompose(A._trs(t, q, s))
    assert close(t, t2) and same_rotation(q, q2) and close(s, s2)
    a = A._trs(t, q, s)
    ident = A._mul(a, A._inv(a))
    assert close(ident[0] + ident[1], A.IDENTITY[0] + A.IDENTITY[1], 1e-9)


# --------------------------------------------------------------------------------------------- retargeting
def test_a_start_kits_animation_comes_back_as_the_same_keys():
    skel = Skel()
    bones = A.track_bones(skel)
    assert bones == [0, 1, 2]                                    # Camera_ref is left out, as the game's are
    keys = motion(skel, bones, 7)
    glb = A.write_rig(skel, Mesh(), [("Wag", bones, keys, 30.0)], "test")
    gltf = A.Gltf("kit.glb", glb)
    assert [c["name"] for c in gltf.clips] == ["Wag"] and abs(gltf.clips[0]["seconds"] - 0.2) < 1e-6
    back = A.retarget(gltf, gltf.clip("Wag"), skel, bones, 30.0, A.rest_pose(skel, Mesh()))
    for (T, Q, S), (T2, Q2, S2) in zip(keys, back):
        assert len(T2) == 7
        assert all(close(a, b, 1e-4) for a, b in zip(T, T2))
        assert all(same_rotation(a, b, 1e-6) for a, b in zip(Q, Q2))
    # The kit rests as the game skins the mesh, so moving from the skeleton's pose would turn the tail round.
    off = A.retarget(gltf, gltf.clip("Wag"), skel, bones, 30.0)
    assert not same_rotation(off[2][1][0], keys[2][1][0], 1e-3)
    # The mesh is skinned to the skeleton's bones by name, whatever order the mesh keeps them in.
    doc = json.loads(glb[20:20 + struct.unpack_from("<I", glb, 12)[0]])
    assert doc["skins"][0]["joints"] == [0, 1, 2, 3] and [n["name"] for n in doc["nodes"][:4]] == ["root", "spine", "tail", "Camera_ref"]


def gltf_file(nodes, channels, ibms, times):
    """A .gltf with its data inline: `nodes` as glTF nodes, `channels` [(node, path, values)] sampled at
    `times`, and a skin of the joints in `ibms` {node: column-major matrix}."""
    buf, views, accessors = bytearray(), [], []

    def add(values, fmt, kind):
        start = len(buf)
        for v in values:
            buf.extend(struct.pack("<" + fmt, *(v if isinstance(v, (tuple, list)) else (v,))))
        views.append({"buffer": 0, "byteOffset": start, "byteLength": len(buf) - start})
        accessors.append({"bufferView": len(views) - 1, "componentType": 5126, "count": len(values), "type": kind})
        return len(accessors) - 1
    t = add(times, "f", "SCALAR")
    samplers, chans = [], []
    for node, path, values in channels:
        samplers.append({"input": t, "output": add(values, f"{len(values[0])}f", "VEC4" if path == "rotation" else "VEC3")})
        chans.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path}})
    joints = sorted(ibms)
    skin = {"joints": joints, "inverseBindMatrices": add([ibms[j] for j in joints], "16f", "MAT4")}
    doc = {"asset": {"version": "2.0"}, "nodes": nodes, "skins": [skin], "scenes": [{"nodes": [0]}],
           "animations": [{"name": "Wave", "samplers": samplers, "channels": chans}],
           "accessors": accessors, "bufferViews": views,
           "buffers": [{"byteLength": len(buf), "uri": "data:application/octet-stream;base64," + base64.b64encode(bytes(buf)).decode()}]}
    return json.dumps(doc).encode()


def column(a):
    m, t = A.m_from_game(a)
    return (m[0], m[3], m[6], 0.0, m[1], m[4], m[7], 0.0, m[2], m[5], m[8], 0.0, t[0], t[1], t[2], 1.0)


def test_blenders_own_bone_frames_and_an_armature_node_dont_change_the_keys():
    # Blender turns each bone its own way when it imports a rig, and keeps an armature object above the
    # bones. A file whose joints have other frames (each turned by a frame of its own) under a turned and
    # scaled armature node, moving the same way in model space, gives the game's bones the same keys.
    skel = Skel()
    bones = A.track_bones(skel)
    n = 5
    keys = motion(skel, bones, n, seed=7)
    rnd = random.Random(11)
    frames = {b: A._trs((0, 0, 0), unit(tuple(rnd.uniform(-1, 1) for _ in range(4))), (1, 1, 1)) for b in bones}
    armature = A._trs((5.0, 1.0, -2.0), turn((1, 0, 0), -90), (0.5, 0.5, 0.5))   # game space

    def globals(k):
        g = []
        for b, (name, parent) in enumerate(skel.bones):
            local = A._trs(*(skel.poses[b] if k is None else (keys[b][0][k], keys[b][1][k], keys[b][2][k]))) \
                if b in bones else A._trs(*skel.poses[b])
            g.append(local if parent < 0 else A._mul(g[parent], local))
        return [A._mul(armature, A._mul(x, frames[b])) if b in frames else x for b, x in enumerate(g)]

    def locals_of(g):
        out = []
        for b in bones:
            parent = skel.bones[b][1]
            above = armature if parent < 0 else g[parent]
            t, q, s = A._decompose(A.m_from_game(A._mul(A._inv(above), g[b])))
            out.append((t, q, s))
        return out
    rest = locals_of(globals(None))
    arm_t, arm_q, arm_s = A._decompose(A.m_from_game(armature))
    nodes = [{"name": "Armature", "translation": list(arm_t), "rotation": list(arm_q), "scale": list(arm_s), "children": [1]}]
    for b in bones:
        t, q, s = rest[b]
        node = {"name": skel.bones[b][0], "translation": list(t), "rotation": list(q), "scale": list(s)}
        kids = [c + 1 for c, (_, p) in enumerate(skel.bones) if p == b and c in bones]
        if kids:
            node["children"] = kids
        nodes.append(node)
    per_key = [locals_of(globals(k)) for k in range(n)]
    channels = []
    for b in bones:
        channels.append((b + 1, "translation", [per_key[k][b][0] for k in range(n)]))
        channels.append((b + 1, "rotation", [per_key[k][b][1] for k in range(n)]))
    ibms = {b + 1: column(A._inv(globals(None)[b])) for b in bones}
    gltf = A.Gltf("blender.gltf", gltf_file(nodes, channels, ibms, [k / 30 for k in range(n)]))
    back = A.retarget(gltf, gltf.clip(), skel, bones, 30.0)
    for (T, Q, S), (T2, Q2, S2) in zip(keys, back):
        assert all(close(a, b, 1e-4) for a, b in zip(T, T2))
        assert all(same_rotation(a, b, 1e-6) for a, b in zip(Q, Q2))
        assert all(close(s, (1.0, 1.0, 1.0), 1e-6) for s in S2)


def test_the_mesh_rest_pose_is_the_meshs_own_and_the_skeletons_for_bones_it_hasnt_got():
    skel = Skel()
    pose = A.rest_pose(skel, Mesh())
    assert pose[0] == skel.poses[0] and pose[3] == skel.poses[3] and pose[1] == skel.poses[1]
    assert same_rotation(pose[2][1], A._decompose(A._mul(A._trs(*skel.poses[2]),
                                                         A._trs((0, 0, 0), turn((0, 1, 0), 180), (1, 1, 1))))[1])
    # A file that only turns the spine leaves the tail where the mesh rests it.
    at = A.reference_globals(skel, pose)[1][1]
    gltf = A.Gltf("one.gltf", gltf_file([{"name": "spine", "translation": list(A.t_from_game(at))}],
                                        [(0, "rotation", [(0, 0, 0, 1), turn((0, 1, 0), 30)])],
                                        {0: column(A._inv((A.IDENTITY[0], at)))}, [0.0, 0.5]))
    back = A.retarget(gltf, gltf.clip(), skel, [0, 1, 2], 30.0, pose)
    assert all(same_rotation(q, pose[2][1]) for q in back[2][1])


def test_a_bone_of_the_files_own_between_the_games_doesnt_move_the_rig():
    # Blender writes children before parents; a bone the game hasn't got sits between the root and the spine.
    # The rig's space is the armature's, above the root, so the root turning gives the same keys either way.
    skel = Skel()
    ref = A.reference_globals(skel)
    g_root, g_spine, g_tail = ref[0], ref[1], ref[2]
    g_extra = A._mul(g_root, A._trs((0, 0, 0), turn((1, 0, 0), 90), (1, 1, 1)))

    def local(parent_g, g):
        t, q, s = A._decompose(A.m_from_game(A._mul(A._inv(parent_g), g)))
        return {"translation": list(t), "rotation": list(q), "scale": list(s)}

    def keys(extra):
        if extra:
            nodes = [dict(name="tail", **local(g_spine, g_tail)), dict(name="spine", children=[0], **local(g_extra, g_spine)),
                     dict(name="extra", children=[1], **local(g_root, g_extra)),
                     dict(name="root", children=[2], **local(A.IDENTITY, g_root)), {"name": "Armature", "children": [3]}]
            ibms = {0: column(A._inv(g_tail)), 1: column(A._inv(g_spine)), 2: column(A._inv(g_extra)),
                    3: column(A._inv(g_root))}
        else:
            nodes = [dict(name="tail", **local(g_spine, g_tail)), dict(name="spine", children=[0], **local(g_root, g_spine)),
                     dict(name="root", children=[1], **local(A.IDENTITY, g_root)), {"name": "Armature", "children": [2]}]
            ibms = {0: column(A._inv(g_tail)), 1: column(A._inv(g_spine)), 2: column(A._inv(g_root))}
        root = 3 if extra else 2
        data = gltf_file(nodes, [(root, "rotation", [(0, 0, 0, 1), turn((0, 1, 0), 90)])], ibms, [0.0, 1.0])
        data = json.loads(data)
        data["scenes"] = [{"nodes": [len(nodes) - 1]}]
        gltf = A.Gltf("x.gltf", json.dumps(data).encode())
        return A.retarget(gltf, gltf.clip(), skel, [0, 1, 2], 30.0)
    plain, extra = keys(False), keys(True)
    for (T, Q, _), (T2, Q2, _) in zip(plain, extra):
        assert all(close(a, b, 1e-4) for a, b in zip(T, T2)) and all(same_rotation(a, b, 1e-6) for a, b in zip(Q, Q2))
    assert same_rotation(plain[0][1][-1], A.q_swap(turn((0, 1, 0), 90)), 1e-6)    # the root turns about the game's up


def test_bones_a_file_leaves_out_hold_their_reference_pose():
    skel = Skel()
    at = A.reference_globals(skel)[1][1]                         # where the game's spine is, as a kit has it
    nodes = [{"name": "Spine", "translation": list(A.t_from_game(at))}]     # any case matches
    gltf = A.Gltf("one.gltf", gltf_file(nodes, [(0, "rotation", [(0, 0, 0, 1), turn((0, 1, 0), 30)])],
                                       {0: column(A._inv((A.IDENTITY[0], at)))}, [0.0, 0.5]))
    back = A.retarget(gltf, gltf.clip("Wave"), skel, [0, 1, 2], 30.0)
    assert len(back[0][0]) == 16                                 # half a second, both ends
    assert all(same_rotation(q, skel.poses[2][1]) for q in back[2][1])   # the tail, relative to the spine
    assert all(close(t, skel.poses[1][0], 1e-6) for t in back[1][0])     # the spine turns where it stands
    assert not same_rotation(back[1][1][-1], skel.poses[1][1], 1e-3)


def test_clips_and_files_that_cant_be_used_are_refused():
    skel = Skel()
    nodes = [{"name": "spine"}]
    gltf = A.Gltf("a.gltf", gltf_file(nodes, [(0, "rotation", [(0, 0, 0, 1), (0, 0, 0, 1)])], {0: column(A.IDENTITY)}, [0.0, 1.0]))
    with pytest.raises(ValueError, match="no animation 'Run'.*'Wave'"):
        gltf.clip("Run")
    other = A.Gltf("b.gltf", gltf_file([{"name": "wing"}], [(0, "rotation", [(0, 0, 0, 1), (0, 0, 0, 1)])],
                                       {0: column(A.IDENTITY)}, [0.0, 1.0]))
    with pytest.raises(ValueError, match="name of one of the game's"):
        A.retarget(other, other.clip(), skel, [0, 1, 2], 30.0)
    long = A.Gltf("c.gltf", gltf_file(nodes, [(0, "rotation", [(0, 0, 0, 1), (0, 0, 0, 1)])], {0: column(A.IDENTITY)},
                                      [0.0, A.MAX_SECONDS + 1.0]))
    with pytest.raises(ValueError, match="up to 60 s"):
        A.retarget(long, long.clip(), skel, [0, 1, 2], 30.0)
    still = A.Gltf("d.gltf", json.dumps({"asset": {"version": "2.0"}, "nodes": [{"name": "spine"}]}).encode())
    with pytest.raises(ValueError, match="no animation"):
        still.clip()
    with pytest.raises(ValueError, match="glTF files"):
        A.Gltf("e.fbx", b"")
    info = A.describe("b.gltf", gltf_file([{"name": "wing"}, {"name": "tail"}], [(0, "rotation", [(0, 0, 0, 1)])],
                                          {0: column(A.IDENTITY), 1: column(A.IDENTITY)}, [0.0]), "cat", skel)
    assert info["matched"] == ["tail"] and info["extra"] == ["wing"] and info["missing"] == ["root", "spine"]
    # Files broken in ways glTF doesn't allow are refused as files wcmods can't read, not as wcmods' own errors.
    for broken in ({"asset": {}, "nodes": [{"name": "spine", "children": [7]}]},
                   {"asset": {}, "nodes": ["spine"]},
                   {"asset": {}, "nodes": [{"name": 5}], "skins": [{"joints": [3]}]},
                   {"asset": {}, "nodes": [{"name": "spine", "children": [0]}]}):
        with pytest.raises(ValueError, match="wcmods can read|loop"):
            A.describe("x.gltf", json.dumps(broken).encode(), "cat", skel)


def test_channels_sample_linear_step_and_cubic():
    times = [0.0, 1.0]
    assert close(A._sample(times, [(0, 0, 0), (2, 4, 6)], "LINEAR", 0.5, "translation"), (1, 2, 3))
    assert close(A._sample(times, [(0, 0, 0), (2, 4, 6)], "STEP", 0.9, "translation"), (0, 0, 0))
    # A cubic spline with flat tangents eases: half way it's half way, a quarter of the way less than a quarter.
    cubic = [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (4, 4, 4), (0, 0, 0)]
    assert close(A._sample(times, cubic, "CUBICSPLINE", 0.5, "translation"), (2, 2, 2))
    assert A._sample(times, cubic, "CUBICSPLINE", 0.25, "translation")[0] < 1.0
    half = A._sample(times, [(0, 0, 0, 1), turn((0, 0, 1), 90)], "LINEAR", 0.5, "rotation")
    assert same_rotation(half, turn((0, 0, 1), 45))
    assert close(A._sample(times, [(1, 1, 1), (2, 2, 2)], "LINEAR", 7.0, "scale"), (2, 2, 2))   # held after the end


# ------------------------------------------------------------------------------------------------- the codec
def test_full_float_tracks_decode_to_their_keys():
    rnd = random.Random(5)
    keys = [unit(tuple(rnd.uniform(-1, 1) for _ in range(4))) for _ in range(6)]
    data = anim._float_track("R", keys)
    header = struct.unpack_from("<I", data)[0]
    assert header & 0xFFFFFF == 6 and header >> 24 & 0xF == 7 and header >> 28 == anim.FLOAT96
    back = anim._per_track(data, 0, "R", 6)
    assert all(same_rotation(a, b, 1e-6) for a, b in zip(keys, back))
    still = anim._float_track("T", [(1.0, 2.0, 3.0)] * 5)
    assert struct.unpack_from("<I", still)[0] & 0xFFFFFF == 1 and len(still) == 16     # one key holds all through
    assert anim._per_track(still, 0, "T", 5) == [(1.0, 2.0, 3.0)] * 5


def test_the_games_packed_keys_decode():
    # 16-bit rotations: (v - 32767) / 32767, only the stored components (flags 1 and 4: x and z).
    data = struct.pack("<I", 1 | 5 << 24 | anim.FIXED48 << 28) + struct.pack("<HH", 32767 + 16383, 32767)
    (q,) = anim._per_track(data, 0, "R", 1)[:1]
    assert close(q[:3], (16383 / 32767, 0.0, 0.0), 1e-6) and abs(q[3] - math.sqrt(1 - (16383 / 32767) ** 2)) < 1e-6
    # A 16-bit scale of 1.0 is 256, as the game's are.
    data = struct.pack("<I", 1 | 7 << 24 | anim.FIXED48 << 28) + struct.pack("<3H", 256, 256, 256)
    assert anim._per_track(data, 0, "S", 1) == [(1.0, 1.0, 1.0)]
    # 32-bit interval keys: a (min, range) per component, then x in bits 21-31, y in 10-20, z in 0-9.
    data = (struct.pack("<I", 2 | 7 << 24 | anim.INTERVAL << 28) + struct.pack("<6f", -1.0, 2.0, 0.0, 4.0, 5.0, 1.0)
            + struct.pack("<II", 0, 2047 << 21 | 2047 << 10 | 1023))
    first, last = anim._per_track(data, 0, "T", 2)
    assert close(first, (-1.0, 0.0, 5.0)) and close(last, (1.0, 4.0, 6.0))


def test_keys_spread_over_the_sequence_or_on_their_frames():
    lerp = anim._lerp
    assert anim._spread([(0.0,), (4.0,)], None, 5, lerp) == [(0.0,), (1.0,), (2.0,), (3.0,), (4.0,)]
    assert anim._spread([(0.0,), (4.0,)], (1, 3), 5, lerp) == [(0.0,), (0.0,), (2.0,), (4.0,), (4.0,)]


def test_imported_package_names_are_written_as_the_game_writes_them():
    names = ["/Engine/Animation/DefaultAnimBoneCompressionSettings", "/Game/X/SK_Y_Skeleton"]
    data = anim._name_section(names)
    count, size, version = struct.unpack_from("<IIQ", data)
    assert (count, size, version) == (2, sum(len(n) for n in names), NAME_HASH_VERSION)
    assert struct.unpack_from("<2Q", data, 16) == tuple(name_hash(n) for n in names)
    assert struct.unpack_from(">2H", data, 32) == tuple(len(n) for n in names)
    assert data.endswith(b"".join(n.encode() for n in names) + b"\0" * 8)
    # A name ending in _ and a number keeps the number apart, as Unreal's FNames do ("_02" isn't one).
    assert [anim._split_number(n) for n in ("/Game/A_2", "/Game/A_02", "/Game/A_0", "A")] == \
        [("/Game/A", 3), ("/Game/A_02", 0), ("/Game/A", 1), ("A", 0)]
    assert anim._name_section(["/Game/A_2"]).endswith(b"/Game/A" + struct.pack("<i", 3))


def sequence_with(props):
    seq = object.__new__(anim.AnimSequence)
    seq.props = props
    return seq


def test_a_sequences_length_and_frame_rate_come_from_its_properties():
    # The bone, curve and frame-stripping settings (object references), then SequenceLength.
    plain = write_header([0, 1, 2, 20, 24, 26], set()) + struct.pack("<3if", -1, -2, -11, 2.5) + b"\0" * 12
    seq = sequence_with(plain)
    assert seq.sequence_length() == 2.5 and seq.frame_rate() == 30.0
    # A bird's: PlatformTargetFrameRate (cooked, 24 / 1) before it.
    bird = write_header([0, 1, 2, 17, 20, 24, 26], set()) + struct.pack("<3iIiif", -1, -2, -11, 1, 24, 1, 5.0) + b"\0" * 12
    seq = sequence_with(bird)
    assert seq.sequence_length() == 5.0 and seq.frame_rate() == 24.0
    other = write_header([0, 1, 2, 19, 20, 24, 26], set()) + b"\0" * 40
    with pytest.raises(anim.FormatError, match="doesn't know"):
        sequence_with(other).sequence_length()


# ------------------------------------------------------------------------------------------ animations.json
@pytest.mark.parametrize("entry, message", [
    ({"id": "Wave", "name": "Wave", "file": "a.fbx"}, "glTF file"),
    ({"id": "2Wave", "name": "Wave", "file": "a.glb"}, "letters and digits"),
    ({"id": "Wave", "file": "a.glb"}, '"name" is missing'),
    ({"id": "Wave", "name": "Wave", "file": "a.glb", "for": "horse"}, '"for" should be one of cat'),
    ({"id": "Wave", "name": "Wave", "file": "a.glb", "speed": 0}, "from 0.1 to 10"),
    ({"id": "Wave", "name": "Wave", "file": "a.glb", "loop": "yes"}, "true or false"),
    ({"id": "Wave", "name": "Wave", "file": "a.glb", "for": "mouse", "emote": True}, "only cats'"),
    ({"id": "Wave", "name": "Wave", "file": "a.glb", "key": "F6"}, '"emote": true too'),
    ({"id": "Wave", "name": "Wave", "file": "a.glb", "emote": True, "key": "F 6"}, "key names"),
    ({"id": "Wave", "name": "Wave", "file": "a.glb", "colour": "red"}, "unknown key"),
])
def test_animations_that_cant_be_used_are_refused(entry, message):
    with pytest.raises(ValueError, match=message):
        check(entry, "animations.json: animation 1")


def test_animations_json_is_read_and_checked(tmp_path):
    mod = type("Mod", (), {"id": "m", "folder": str(tmp_path)})()
    wave = {"id": "Wave", "name": "Wave", "file": "animations/wave.glb", "emote": True, "key": "F6"}
    (tmp_path / "animations.json").write_text(json.dumps({"animations": [wave]}))
    assert AnimationsSection().collect(mod, None) == [wave]
    (tmp_path / "animations.json").write_text(json.dumps({"animations": [wave, dict(wave, id="wave")]}))
    with pytest.raises(ValueError, match="called wave too"):
        AnimationsSection().collect(mod, None)
    (tmp_path / "animations.json").write_text(json.dumps({"animations": []}))
    assert AnimationsSection().collect(mod, None) is None
    # One the Animations page saved before its file was chosen is left out, and the others install.
    ctx = FakeCtx()
    (tmp_path / "animations.json").write_text(json.dumps({"animations": [{"id": "New", "name": "New"}, wave]}))
    assert AnimationsSection().collect(mod, ctx) == [wave]
    assert ctx.warnings == ["m: New: no file chosen yet, so it's left out"]


class FakeCtx:
    def __init__(self):
        self.cfg = type("Cfg", (), {"ue4ss_mods_dir": "x"})()
        self.made, self.shared, self.scripts, self.warnings, self.notes = [], {}, {}, [], {}

    def add_animation(self, name, read, kind="cat", clip=None, claws=False, source="", key=None):
        if "Broken" in name:
            raise ValueError("the file has no animation")
        self.made.append((name, kind, clip, claws))
        return "/Game/WCMods/" + name + "." + name.rsplit("/", 1)[-1], 2.0

    def add_ue4ss_shared(self, name, text):
        self.shared[name] = text

    def add_ue4ss_mod(self, name, files):
        self.scripts[name] = files

    def warn(self, text):
        self.warnings.append(text)

    def note(self, key, value):
        self.notes[key] = value


def test_the_install_lists_the_animations_and_puts_the_emotes_on_keys(tmp_path):
    mod = type("Mod", (), {"id": "m", "folder": str(tmp_path)})()
    (tmp_path / "w.glb").write_bytes(b"glTF")
    found = [{"id": "Wave", "name": "Wave", "file": "w.glb", "emote": True, "key": "F6", "claws": True},
             {"id": "Swim", "name": "Swim", "file": "w.glb", "loop": True, "speed": 1.5},
             {"id": "Spin", "name": "Spin", "file": "w.glb", "for": "mouse", "clip": "Spin"},
             {"id": "Broken", "name": "Broken", "file": "w.glb"}]
    ctx = FakeCtx()
    AnimationsSection().build(ctx, [(mod, found)])
    assert ctx.made == [("m/A_Wave", "cat", None, True), ("m/A_Swim", "cat", None, False), ("m/A_Spin", "mouse", "Spin", False)]
    assert ctx.warnings == ["m: Broken: the file has no animation"]
    lua = ctx.shared["WCModsAnims"]
    assert not luacheck.check(lua)
    assert '["m/Swim"] = { ["name"] = "Swim", ["kind"] = "cat", ["path"] = "/Game/WCMods/m/A_Swim.A_Swim", ["loop"] = true, ["speed"] = 1.5' in lua
    assert '["mouse"] = { "SK_Mice" }' in lua
    script = ctx.scripts["WCModsEmotes"]["Scripts/main.lua"]
    assert not luacheck.check(script) and "@EMOTES@" not in script
    assert '{ ["id"] = "m/Wave", ["name"] = "Wave", ["key"] = "F6" }' in script
    assert ctx.notes["emotes"] == ["m/Wave"]


def test_an_install_without_emotes_has_no_emotes_script(tmp_path):
    mod = type("Mod", (), {"id": "m", "folder": str(tmp_path)})()
    ctx = FakeCtx()
    AnimationsSection().build(ctx, [(mod, [{"id": "Swim", "name": "Swim", "file": "w.glb", "loop": True}])])
    assert ctx.warnings == ["m: Swim: there's no animation w.glb in the mod's folder"] and not ctx.shared
    (tmp_path / "w.glb").write_bytes(b"glTF")
    AnimationsSection().build(ctx, [(mod, [{"id": "Swim", "name": "Swim", "file": "w.glb", "loop": True}])])
    assert "WCModsAnims" in ctx.shared and not ctx.scripts


def test_the_game_module_plays_animations():
    lua = source("game.lua")
    for call in ("function Game.anims.play(who, id, opts)", "function Game.anims.stop(who, blend)",
                 "function Game.anims.playing(who)", "function Game.anims.kind(who)", "function Cat:animate(id, opts)",
                 "PlaySlotAnimationAsDynamicMontage", 'require, "WCModsAnims"'):
        assert call in lua
    assert not luacheck.check(source("emotes.lua").replace("@EMOTES@", "{}"))
