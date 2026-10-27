"""Animations of a mod's own: glTF files (.glb, .gltf) made in Blender, played on cats and the roaming animals.

An animation is keys for the bones of one of the game's skeletons: the cats' (every cat in the forest,
yours and the clans', shares SK_CatMaster's) or one kind of animal's. A file's joints are matched to the
game's bones by name, and each bone moves as the file's joint of that name moves from its rest pose:
its model-space motion is put on the game's own bone, so the game's bone lengths and directions don't
have to be the file's (Blender turns bones its own way when it imports them). Bones the file leaves out
hold the game's reference pose. The keys go into a copy of one of the game's sequences on that skeleton
(formats/anim.py), at that sequence's frame rate.

Space: a file is in metres with Y up and the animal facing +Z (Blender's glTF settings); the game is in
centimetres with Z up, facing +Y. (x, y, z) in a file is (100 x, 100 z, 100 y) in the game, so a
rotation's quaternion (x, y, z, w) is (-x, -z, -y, w) there (swapping two axes mirrors the space, which
turns rotations the other way), and a scale's (x, y, z) is (x, z, y).

`start_kit` writes a .glb to animate: the animal rigged to the game's skeleton, with some of the game's
own animations on it as examples.
"""
import hashlib
import io
import json
import math
import os
import struct
import zipfile

from . import models

FORMATS = (".glb", ".gltf")
MAX_FILE = 64 * 1024 * 1024
MAX_SECONDS = 60
CACHE_VERSION = 2   # change when the writer or the retargeting changes, so cached sequences are made again
# What a broken file can make the reading or the retargeting raise besides ValueError: each is the file's fault,
# so it's a ValueError too, and only that animation is left out.
BROKEN = (KeyError, IndexError, TypeError, AttributeError, ArithmeticError, RecursionError, struct.error)

_ART = "/Game/Art/Characters/"
# The skeletons an animation can be for: its label, the skeleton, the mesh the start kit shows, the sequence a
# new one is a copy of (a plain one: no notifies, no curves but the cats' constant ones), the meshes that run
# it in the game (to tell which actors can play it), and the game's sequences the start kit carries as
# examples (the ones in Unreal's own codecs, which wcmods decodes).
KINDS = {
    "cat": {"label": "Cats", "skeleton": "CatMaster/Skel/SK_CatMaster_Skeleton", "mesh": "CatMaster/Skel/SK_CatMaster",
            "template": "CatMaster/Animations/A_CatMaster_Meow", "meshes": ["SK_CatMaster"],
            "examples": ["CatMaster/Animations/A_CatMaster_Stretch_1", "CatMaster/Animations/A_CatMaster_Meow",
                         "CatMaster/Animations/A_CatMaster_Shake_1", "CatMaster/Animations/A_CatMaster_Stand_1_c"]},
    "mouse": {"label": "Mice", "skeleton": "Enemy/Mice/Skel/SK_Mice_Skeleton", "mesh": "Enemy/Mice/Skel/SK_Mice",
              "template": "Enemy/Mice/Animations/Combat/A_Mice_Hit_Out_T", "meshes": ["SK_Mice"],
              "examples": ["Enemy/Mice/Animations/A_Mice_Idle_1", "Enemy/Mice/Animations/A_Mice_Walk_1"]},
    "rat": {"label": "Rats", "skeleton": "Enemy/Rats/Skel/SK_Rats_Skeleton", "mesh": "Enemy/Rats/Skel/SK_Rats",
            "template": "Enemy/Rats/Animations/Combat/A_Rats_Hit_Out_T", "meshes": ["SK_Rats"],
            "examples": ["Enemy/Rats/Animations/A_Rats_Idle_1", "Enemy/Rats/Animations/A_Rats_Walk_1"]},
    "rabbit": {"label": "Rabbits", "skeleton": "Enemy/Rabbit/Skel/SK_Rabbit_Skeleton", "mesh": "Enemy/Rabbit/Skel/SK_Rabbit",
               "template": "Enemy/Rabbit/Animations/Combat/A_Rabbit_Hit_Out_N", "meshes": ["SK_Rabbit"],
               "examples": ["Enemy/Rabbit/Animations/Combat/A_Rabbit_Hit_1"]},
    "squirrel": {"label": "Squirrels", "skeleton": "Enemy/Squirrel/Skel/SK_Squirrel_Skeleton",
                 "mesh": "Enemy/Squirrel/Skel/SK_Squirrel",
                 "template": "Enemy/Squirrel/Animations/Combat/SneakyStance/A_Squirrel_Sneaky_Stance_Stand_1",
                 "meshes": ["SK_Squirrel"], "examples": []},
    "bird": {"label": "Birds", "skeleton": "Enemy/Bird/Skel/SK_Bird_Skeleton", "mesh": "Enemy/Bird/Skel/SK_Bird",
             "template": "Enemy/Bird/Animations/Combat/A_Bird_Lose_2", "meshes": ["SK_Bird"], "examples": []},
    "fox": {"label": "Foxes", "skeleton": "Enemy/Fox/Skel/Sk_Fox_Skeleton", "mesh": "Enemy/Fox/Skel/Sk_Fox",
            "template": "Enemy/Fox/Animations/Combat/A_Fox_Hit_Out_N", "meshes": ["Sk_Fox"], "examples": []},
    "badger": {"label": "Badgers", "skeleton": "Enemy/Badger/Skel/Sk_Badger_Skeleton", "mesh": "Enemy/Badger/Skel/Sk_Badger",
               "template": "Enemy/Badger/Animations/Combat/OffensiveStance/A_Badger_Offensive_Stance_Stand_1",
               "meshes": ["Sk_Badger"], "examples": []},
    "dog": {"label": "Dogs", "skeleton": "Enemy/Dog/Skel/SK_Dog_Skeleton", "mesh": "Enemy/Dog/Skel/SK_Dog",
            "template": "Enemy/Dog/Animations/Combat/SneakyStance/A_Dog_Sneaky_Stance_Stand_1", "meshes": ["SK_Dog"],
            "examples": []},
    "snake": {"label": "Snakes", "skeleton": "Enemy/Snake/Skel/SK_Snake_Skeleton", "mesh": "Enemy/Snake/Skel/SK_Snake",
              "template": "Enemy/Snake/Animations/Combat/A_Snake_Hit_Out_T", "meshes": ["SK_Snake"], "examples": []},
}
# The cats' claws: the sequences hold these curves at 1 (claws in); "claws" out puts them at 0.
CLAWS = ("shp_claw_hiden_l", "shp_claw_hiden_r", "shp_claw_b_hiden_l", "shp_claw_b_hiden_r")


def asset(kind, what):
    """A kind's skeleton, mesh or template as an asset path (/Game/Art/Characters/...)."""
    return _ART + KINDS[kind][what]


def track_bones(skeleton):
    """The bones an animation keys: all of them but the ones the game aims things with (Camera_ref,
    Target_ref), as the game's own sequences leave them out."""
    return [i for i, (name, _) in enumerate(skeleton.bones) if not name.lower().endswith("_ref")]


# ---------------------------------------------------------------------------------------------------- math
# A transform is (m, t): a 3x3 matrix (row-major, rotation and scale) and a translation; it maps p to m p + t.
def _quat_matrix(q):
    x, y, z, w = q
    n = x * x + y * y + z * z + w * w
    s = 2.0 / n if n else 0.0
    return (1 - s * (y * y + z * z), s * (x * y - z * w), s * (x * z + y * w),
            s * (x * y + z * w), 1 - s * (x * x + z * z), s * (y * z - x * w),
            s * (x * z - y * w), s * (y * z + x * w), 1 - s * (x * x + y * y))


def _matrix_quat(m):
    a, b, c, d, e, f, g, h, i = m
    tr = a + e + i
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = ((h - f) / s, (c - g) / s, (d - b) / s, 0.25 * s)
    elif a > e and a > i:
        s = math.sqrt(1.0 + a - e - i) * 2
        q = (0.25 * s, (b + d) / s, (c + g) / s, (h - f) / s)
    elif e > i:
        s = math.sqrt(1.0 + e - a - i) * 2
        q = ((b + d) / s, 0.25 * s, (f + h) / s, (c - g) / s)
    else:
        s = math.sqrt(1.0 + i - a - e) * 2
        q = ((c + g) / s, (f + h) / s, 0.25 * s, (d - b) / s)
    n = math.sqrt(sum(v * v for v in q)) or 1.0
    return tuple(v / n for v in q)


def _trs(t, q, s):
    r = _quat_matrix(q)
    return (tuple(r[3 * row + col] * s[col] for row in range(3) for col in range(3)), tuple(t))


def _mul(a, b):
    """a after b."""
    (m, t), (n, u) = a, b
    mn = tuple(sum(m[3 * r + k] * n[3 * k + c] for k in range(3)) for r in range(3) for c in range(3))
    return mn, tuple(sum(m[3 * r + k] * u[k] for k in range(3)) + t[r] for r in range(3))


def _inv(a):
    m, t = a
    a0, a1, a2, b0, b1, b2, c0, c1, c2 = m
    det = a0 * (b1 * c2 - b2 * c1) - a1 * (b0 * c2 - b2 * c0) + a2 * (b0 * c1 - b1 * c0)
    if abs(det) < 1e-12:
        raise ValueError("a bone is scaled to nothing")
    k = 1.0 / det
    inv = ((b1 * c2 - b2 * c1) * k, (a2 * c1 - a1 * c2) * k, (a1 * b2 - a2 * b1) * k,
           (b2 * c0 - b0 * c2) * k, (a0 * c2 - a2 * c0) * k, (a2 * b0 - a0 * b2) * k,
           (b0 * c1 - b1 * c0) * k, (a1 * c0 - a0 * c1) * k, (a0 * b1 - a1 * b0) * k)
    return inv, tuple(-sum(inv[3 * r + c] * t[c] for c in range(3)) for r in range(3))


def _decompose(a):
    """(translation, rotation, scale) of a transform (no shear)."""
    m, t = a
    cols = [(m[c], m[3 + c], m[6 + c]) for c in range(3)]
    s = [math.sqrt(sum(v * v for v in col)) or 1.0 for col in cols]
    det = (m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) + m[2] * (m[3] * m[7] - m[4] * m[6]))
    if det < 0:
        s[0] = -s[0]
    r = tuple(m[3 * row + col] / s[col] for row in range(3) for col in range(3))
    return t, _matrix_quat(r), tuple(s)


IDENTITY = ((1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0))


# ------------------------------------------------------------------------------------------ the two spaces
def t_to_game(t):
    return (t[0] * models.SCALE, t[2] * models.SCALE, t[1] * models.SCALE)


def t_from_game(t):
    return (t[0] / models.SCALE, t[2] / models.SCALE, t[1] / models.SCALE)


def q_swap(q):
    """A rotation in the other space (the same both ways)."""
    return (-q[0], -q[2], -q[1], q[3])


def s_swap(s):
    return (s[0], s[2], s[1])


def m_to_game(a):
    """A glTF-space transform in the game's space: P a P^-1, P swapping y and z and scaling by 100."""
    m, t = a
    p = (0, 2, 1)
    return tuple(m[3 * p[r] + p[c]] for r in range(3) for c in range(3)), t_to_game(t)


def m_from_game(a):
    m, t = a
    p = (0, 2, 1)
    return tuple(m[3 * p[r] + p[c]] for r in range(3) for c in range(3)), t_from_game(t)


# ------------------------------------------------------------------------------------------------ reading
class Gltf:
    """A glTF file's nodes (their names, parents and rest transforms, in the game's space), skins and
    animations."""

    def __init__(self, name, data, sibling=None):
        if len(data) > MAX_FILE:
            raise ValueError(f"the file is over {MAX_FILE // 1024 ** 2} MB")
        if os.path.splitext(name)[1].lower() not in FORMATS:
            raise ValueError("animations are glTF files (.glb, or .gltf): Blender's File > Export > glTF 2.0")
        try:
            self.doc, accessor = models.gltf_document(name, data, sibling)
            self._read(accessor)
        except BROKEN + (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"{os.path.basename(name)} isn't a glTF file wcmods can read ({type(e).__name__}: {e})") from None

    def _read(self, accessor):
        doc = self.doc
        nodes = doc.get("nodes", [])
        self.names = [str(n.get("name") or f"node {i}") for i, n in enumerate(nodes)]
        self.parent = [None] * len(nodes)
        for i, n in enumerate(nodes):
            for c in n.get("children", []):
                self.parent[c] = i
        self.rest = []                    # each node's own transform, in the game's space
        for n in nodes:
            if "matrix" in n:
                m = [float(v) for v in n["matrix"]]            # column-major
                self.rest.append(m_to_game((tuple(m[4 * c + r] for r in range(3) for c in range(3)), tuple(m[12:15]))))
            else:
                self.rest.append(m_to_game(_trs(n.get("translation", (0, 0, 0)), n.get("rotation", (0, 0, 0, 1)),
                                                n.get("scale", (1, 1, 1)))))
        self.order = []                   # parents before children
        seen = set()
        for i in range(len(nodes)):
            stack = [i] if self.parent[i] is None else []
            while stack:
                j = stack.pop()
                if j in seen:
                    raise ValueError("the file's nodes loop")
                seen.add(j)
                self.order.append(j)
                stack.extend(reversed(nodes[j].get("children", [])))
        if len(seen) != len(nodes):
            raise ValueError("the file's nodes loop")       # some are only under each other
        # Where each joint was when the mesh was bound to it (the skin's inverse bind matrices), when there's
        # a skin: that's the pose the animation moves from, whatever its nodes' own transforms say.
        self.bind = {}
        for skin in doc.get("skins", []):
            ibms = accessor(skin["inverseBindMatrices"]) if "inverseBindMatrices" in skin else None
            for k, j in enumerate(skin.get("joints", [])):
                if ibms is not None and j not in self.bind:
                    m = ibms[k]
                    ibm = m_to_game((tuple(m[4 * c + r] for r in range(3) for c in range(3)), tuple(m[12:15])))
                    self.bind[j] = _inv(ibm)
        self.clips = []
        for a, anim in enumerate(doc.get("animations", [])):
            channels = []
            for ch in anim.get("channels", []):
                target = ch.get("target", {})
                path, node = target.get("path"), target.get("node")
                if path not in ("translation", "rotation", "scale") or node is None:
                    continue                                   # morph weights aren't read
                sampler = anim["samplers"][ch["sampler"]]
                times = [float(t) for t in accessor(sampler["input"])]
                values = accessor(sampler["output"])
                mode = sampler.get("interpolation", "LINEAR")
                if mode == "CUBICSPLINE":
                    if len(values) != 3 * len(times):
                        raise ValueError("a cubic spline's values don't match its times")
                elif len(values) != len(times):
                    raise ValueError("an animation's values don't match its times")
                if times:
                    channels.append((node, path, times, values, mode))
            if channels:
                start = min(c[2][0] for c in channels)
                end = max(c[2][-1] for c in channels)
                self.clips.append({"name": anim.get("name") or f"Animation {a + 1}", "channels": channels,
                                   "start": start, "seconds": end - start})

    def clip(self, name=None):
        """An animation by name, or the first when there's no name; ValueError when there's none."""
        if not self.clips:
            raise ValueError("the file has no animation (in Blender, export with Animation on, and the action "
                             "on the armature)")
        if name is None:
            return self.clips[0]
        for c in self.clips:
            if c["name"] == name:
                return c
        raise ValueError(f"the file has no animation {name!r} (it has {', '.join(repr(c['name']) for c in self.clips)})")

    def joints(self, skeleton):
        """{skeleton bone index: node} for the file's nodes named as the game's bones (in any case)."""
        out = {}
        for i, name in enumerate(self.names):
            b = skeleton.index(name)
            if b is not None and b not in out:
                out[b] = i
        return out

    def _rest_globals(self):
        g = {}
        for i in self.order:
            p = self.parent[i]
            g[i] = self.rest[i] if p is None else _mul(g[p], self.rest[i])
        return {i: self.bind.get(i, g[i]) for i in g}

    def _locals_at(self, clip, t):
        """Each node's own transform at time t (from its start), animated or at rest."""
        parts = {}
        for node, path, times, values, mode in clip["channels"]:
            parts.setdefault(node, {})[path] = _sample(times, values, mode, clip["start"] + t, path)
        out = list(self.rest)
        for node, p in parts.items():
            n = self.doc["nodes"][node]
            if "matrix" in n:
                m = [float(v) for v in n["matrix"]]
                base = (tuple(m[4 * c + r] for r in range(3) for c in range(3)), tuple(m[12:15]))
                bt, bq, bs = _decompose(base)
            else:
                bt, bq, bs = n.get("translation", (0, 0, 0)), n.get("rotation", (0, 0, 0, 1)), n.get("scale", (1, 1, 1))
            out[node] = m_to_game(_trs(p.get("translation", bt), p.get("rotation", bq), p.get("scale", bs)))
        return out


def _sample(times, values, mode, t, path):
    """A channel's value at time t."""
    n = len(times)
    if mode == "CUBICSPLINE":
        key = lambda k: values[3 * k + 1]                      # noqa: E731 - in-tangent, value, out-tangent
    else:
        key = lambda k: values[k]                              # noqa: E731
    if t <= times[0] or n == 1:
        return tuple(key(0))
    if t >= times[-1]:
        return tuple(key(n - 1))
    lo, hi = 0, n - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if times[mid] <= t:
            lo = mid
        else:
            hi = mid
    t0, t1 = times[lo], times[hi]
    u = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    if mode == "STEP":
        return tuple(key(lo))
    if mode == "CUBICSPLINE":
        dt = t1 - t0
        p0, m0 = values[3 * lo + 1], values[3 * lo + 2]
        p1, m1 = values[3 * hi + 1], values[3 * hi]
        u2, u3 = u * u, u * u * u
        v = tuple((2 * u3 - 3 * u2 + 1) * a + (u3 - 2 * u2 + u) * dt * b + (-2 * u3 + 3 * u2) * c + (u3 - u2) * dt * d
                  for a, b, c, d in zip(p0, m0, p1, m1))
        if path == "rotation":
            nrm = math.sqrt(sum(x * x for x in v)) or 1.0
            v = tuple(x / nrm for x in v)
        return v
    a, b = key(lo), key(hi)
    if path == "rotation":
        return _slerp(a, b, u)
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def _slerp(a, b, u):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b, d = tuple(-x for x in b), -d
    if d > 0.9995:
        q = tuple(x + (y - x) * u for x, y in zip(a, b))
    else:
        th = math.acos(min(1.0, d))
        s = math.sin(th)
        wa, wb = math.sin((1 - u) * th) / s, math.sin(u * th) / s
        q = tuple(wa * x + wb * y for x, y in zip(a, b))
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    return tuple(x / n for x in q)


# ------------------------------------------------------------------------------------------- retargeting
def rest_pose(skeleton, mesh):
    """Each of the skeleton's bones' pose [(translation, rotation, scale)] as the game skins the kind's mesh
    (formats/skelmesh.py) in: the mesh's own reference pose, which isn't always its skeleton's (the rabbit's
    differs on most of its bones, with its right ear, eyelid and cheek turned round; the cats' front paws by
    a centimetre), and the skeleton's for bones the mesh hasn't got."""
    own = {name.lower(): (v[4:7], v[0:4], v[7:10]) for (name, _), v in zip(mesh.bones, mesh.poses)}
    return [own.get(name.lower(), pose) for (name, _), pose in zip(skeleton.bones, skeleton.poses)]


def reference_globals(skeleton, pose=None):
    """Each game bone's reference pose (`pose`, or the skeleton's own) in model space."""
    g = []
    for (name, parent), (t, q, s) in zip(skeleton.bones, pose or skeleton.poses):
        local = _trs(t, q, s)
        g.append(local if parent < 0 else _mul(g[parent], local))
    return g


def _depth(gltf, i):
    d, p = 0, gltf.parent[i]
    while p is not None:
        d, p = d + 1, gltf.parent[p]
    return d


def retarget(gltf, clip, skeleton, bones, rate, pose=None):
    """The clip's keys for the skeleton's `bones` (indexes), at `rate` keys a second: [(translations,
    rotations, scales)] a bone, relative to its parent in the game's space. `pose` is the pose the game's
    bones move from (rest_pose; the skeleton's own by default)."""
    if clip["seconds"] > MAX_SECONDS:
        raise ValueError(f"the animation is {clip['seconds']:.1f} s long; an animation can be up to {MAX_SECONDS} s")
    n = max(2, int(round(clip["seconds"] * rate)) + 1)
    joints = gltf.joints(skeleton)
    if not joints:
        raise ValueError("none of the file's bones has the name of one of the game's (export the start kit's "
                         "armature, keeping its bones' names)")
    pose = pose or skeleton.poses
    rest = gltf._rest_globals()
    ref = reference_globals(skeleton, pose)
    ref_local = [_trs(*p) for p in pose]
    # The rig's own space: the node above the game's root bone, or above the file's topmost bone with a
    # game bone's name (Blender's armature object), at rest. A joint's motion from its rest pose, in that
    # space, is put on the game's bone at its reference pose: G'(t) = R^-1 G(t) G(rest)^-1 R G'(ref). So
    # where the armature object stands, and how it's turned and sized, doesn't matter; moving it in the
    # animation moves the whole animal.
    root = next((b for b, (_, parent) in enumerate(skeleton.bones) if parent < 0), 0)
    top = joints.get(root)
    if top is None:
        top = min(joints.values(), key=lambda i: (_depth(gltf, i), i))
    above = gltf.parent[top]
    rig = IDENTITY if above is None else rest[above]
    unrig = _inv(rig)
    moved = {b: _mul(_inv(rest[j]), _mul(rig, ref[b])) for b, j in joints.items()}
    out = {b: ([], [], []) for b in bones}
    for k in range(n):
        t = min(clip["seconds"], k / rate)
        local = gltf._locals_at(clip, t)
        g = {}
        for i in gltf.order:
            p = gltf.parent[i]
            g[i] = local[i] if p is None else _mul(g[p], local[i])
        game = []
        for b, (name, parent) in enumerate(skeleton.bones):
            if b in joints:
                game.append(_mul(unrig, _mul(g[joints[b]], moved[b])))
            else:
                game.append(ref_local[b] if parent < 0 else _mul(game[parent], ref_local[b]))
        for b in bones:
            parent = skeleton.bones[b][1]
            own = game[b] if parent < 0 else _mul(_inv(game[parent]), game[b])
            tr, q, s = _decompose(own)
            out[b][0].append(tr)
            out[b][1].append(q)
            out[b][2].append(s)
    return [out[b] for b in bones]


def describe(name, data, kind, skeleton, sibling=None):
    """What a file holds for a kind's skeleton: {"clips": [{"name", "seconds"}], "matched": the game's bones it
    has, "missing": the game's bones it hasn't got, "extra": its bones the game hasn't got}."""
    gltf = Gltf(name, data, sibling)
    try:
        joints = gltf.joints(skeleton)
        keyed = set(track_bones(skeleton))
        animated = {c[0] for clip in gltf.clips for c in clip["channels"]}
        names = {skeleton.bones[b][0].lower() for b in joints}
        skin_joints = {j for skin in gltf.doc.get("skins", []) for j in skin.get("joints", [])}
        candidates = skin_joints or animated
        return {"kind": kind,
                "clips": [{"name": c["name"], "seconds": round(c["seconds"], 3)} for c in gltf.clips],
                "matched": sorted(skeleton.bones[b][0] for b in joints if b in keyed),
                "missing": sorted(skeleton.bones[b][0] for b in keyed if b not in joints),
                "extra": sorted(gltf.names[i] for i in candidates if gltf.names[i].lower() not in names)}
    except BROKEN as e:
        raise ValueError(f"{os.path.basename(name)} isn't a glTF file wcmods can read ({type(e).__name__}: {e})") from None


# ----------------------------------------------------------------------------------------------- building
class Game:
    """The game's skeletons and templates, read once an install and only when an animation needs them."""

    def __init__(self, read):
        self.read, self._skeletons, self._rests = read, {}, {}

    def skeleton(self, kind):
        from .formats import anim, texture
        if kind not in self._skeletons:
            self._skeletons[kind] = anim.Skeleton(self.read(texture.content_path(asset(kind, "skeleton"))))
        return self._skeletons[kind]

    def rest(self, kind):
        """The pose the game skins `kind`'s mesh in (rest_pose)."""
        from .formats import skelmesh, texture
        if kind not in self._rests:
            mesh = skelmesh.SkeletalMesh(self.read(texture.content_path(asset(kind, "mesh"))), morphs=False)
            self._rests[kind] = rest_pose(self.skeleton(kind), mesh)
        return self._rests[kind]


def build(ctx, package, kind, read_file, clip, key, claws=False, game=None):
    """{"data", "chunk_id", "imports", "shaders", "seconds"} for a new sequence `package`: the clip `clip`
    (a name, or None for the first) of the glTF file read_file() gives as (name, data, sibling), for a kind
    of animal, in a copy of the kind's template. With `key` (text that changes whenever the file would) it's
    kept in cache/animations under that and the template's bytes, so an install doesn't make it twice;
    without, it's made each time."""
    from .formats import anim, texture
    template_path = texture.content_path(asset(kind, "template"))
    template = ctx.read_game_file(template_path)
    digest = hashlib.sha1(f"{CACHE_VERSION}|{package}|{kind}|{clip}|{bool(claws)}|{key}|".encode()
                          + hashlib.sha1(template).digest()).hexdigest()
    cache = os.path.join(ctx.cache_dir, "animations")
    found, meta = os.path.join(cache, digest + ".uasset"), os.path.join(cache, digest + ".json")
    imports, shaders = ctx.game.io.container_header().entry_for(texture.package_id(asset(kind, "template")))
    if key is not None and os.path.isfile(found) and os.path.isfile(meta):
        with open(found, "rb") as f:
            data = f.read()
        with open(meta, encoding="utf-8") as f:
            info = json.load(f)
        os.utime(found)                         # used: kept by the clear-out
    else:
        texture._clear_out(cache)
        game = game or Game(ctx.read_game_file)
        skeleton = game.skeleton(kind)
        seq = anim.AnimSequence(template)
        name, file_data, sibling = read_file()
        bones, pose = track_bones(skeleton), game.rest(kind)
        try:
            gltf = Gltf(name, file_data, sibling)
            keys = retarget(gltf, gltf.clip(clip), skeleton, bones, seq.frame_rate(), pose)
        except BROKEN as e:
            raise ValueError(f"{os.path.basename(name)} has something in it wcmods can't read ({type(e).__name__}: {e})") from None
        new_imports = seq.use_unreal_codec(imports)
        if seq.codec == "acl" or kind != "cat":
            seq.clear_curves()                  # an ACL template's curves are in ACL; the animals' are faces
        seq.set_tracks(keys, bones=bones)
        if kind == "cat":
            present = [c for c in CLAWS if c in seq.curves]
            seq.set_constant_curves({c: 0.0 if claws else 1.0 for c in present})
        seq.rename(package, package.rsplit("/", 1)[-1])
        data = seq.bytes()
        info = {"seconds": round(seq.length, 4), "imports": [f"{i:016x}" for i in new_imports]}
        if key is not None:
            os.makedirs(cache, exist_ok=True)
            for path, content in ((meta, json.dumps(info).encode()), (found, data)):
                with open(path + ".tmp", "wb") as f:
                    f.write(content)
                os.replace(path + ".tmp", path)
    return {"data": data, "chunk_id": texture.chunk_id(texture.package_id(package), texture.CHUNK_EXPORT_BUNDLE),
            "imports": [int(i, 16) for i in info["imports"]], "shaders": shaders, "seconds": info["seconds"]}


def module(animations):
    """The WCModsAnims shared module: {id: {"name", "kind", "path", "loop", "speed", "blend", "emote", "key"}}
    for every animation the install has, and the meshes of each kind."""
    from .sdk import lua_value
    kinds = {k: v["meshes"] for k, v in KINDS.items()}
    return ("-- Written by wcmods from your mods' animations.json: their animations, and which meshes play each kind.\n"
            "-- Do not edit; edit animations.json (or the Animations page in Clan Mod Studio) and install again.\n"
            "-- WCModsGame's Game.anims plays them; the WCModsEmotes script puts the emotes on keys and a menu page.\n"
            f"return {{ animations = {lua_value(animations)}, kinds = {lua_value(kinds)} }}\n")


def emotes_script(emotes):
    """The WCModsEmotes script (lua/emotes.lua): [{"id", "name", "key"}] in the order the menu lists them."""
    from .lua import source
    from .sdk import lua_value
    return source("emotes.lua").replace("@EMOTES@", lua_value(emotes))


# ----------------------------------------------------------------------------------------------- start kit
README = """Animating {label}
{rule}

{kind}.glb is one of the game's {label_lower}, rigged to the game's own skeleton: {bones} bones with the
game's names, in the pose they rest in. Open it in Blender (File > Import > glTF 2.0) and animate the
armature: pose it, key it, make an action. {examples}

- Keep the bones' names: wcmods moves each of the game's bones as the bone of that name moves. Bones you
  don't move hold their place. You can add bones of your own (they're left out) but not rename the game's.
- Units are metres, Y up, the animal facing +Z: Blender's glTF settings, so import and export as they are.
- The game plays it where the animal stands: moving the root moves its body, not the animal itself.
- Up to {max_seconds} seconds. The game shows {rate} keys a second; wcmods samples your animation at that rate.
- Export with File > Export > glTF 2.0, "glTF Binary (.glb)", with Animation on. One file can hold several
  actions; you choose which one an animation plays.

Then in Clan Mod Studio's Animations page, add an animation for {label_lower} and choose your file.
In animations.json it's "file": "animations/my-emote.glb" (docs/SDK.md, Animations).
"""


def start_kit(game, kind):
    """A .zip to animate in: `kind`'s mesh rigged to its skeleton as a .glb (with some of the game's own
    animations as examples) and a README. Returns (zip bytes, file name)."""
    from .formats import anim, skelmesh, texture
    if kind not in KINDS:
        raise ValueError(f"there's no animal {kind!r} (there are {', '.join(KINDS)})")
    skeleton = anim.Skeleton(game.read(texture.content_path(asset(kind, "skeleton"))))
    mesh = skelmesh.SkeletalMesh(game.read(texture.content_path(asset(kind, "mesh"))), morphs=False)
    examples = []
    for path in KINDS[kind]["examples"]:
        try:
            seq = anim.AnimSequence(game.read(texture.content_path(_ART + path)))
            examples.append((path.rsplit("/", 1)[-1], seq.track_map, seq.tracks(), seq.frame_rate()))
        except (KeyError, ValueError):
            continue                              # one the game no longer has, or in ACL
    rate = anim.AnimSequence(game.read(texture.content_path(asset(kind, "template")))).frame_rate()
    data = write_rig(skeleton, mesh, examples, kind)
    label = KINDS[kind]["label"]
    what = ("It carries some of the game's own animations as actions to start from: "
            + ", ".join(e[0] for e in examples) + ".") if examples else ""
    readme = README.format(label=label, label_lower=label.lower(), rule="=" * (len(label) + 10), kind=kind,
                           bones=len(skeleton.bones), examples=what, max_seconds=MAX_SECONDS, rate=int(rate))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{kind}.glb", data)
        z.writestr("README.txt", readme)
    return out.getvalue(), f"{kind}-animation-kit.zip"


def write_rig(skeleton, mesh, examples, name):
    """A .glb: the skeleton's bones as nodes (named as the game names them, in the pose the game skins the
    mesh in: rest_pose), the mesh's first LOD skinned to them, and each example [(name, track table, tracks,
    rate)] as an animation."""
    buf = bytearray()
    views, accessors = [], []

    def add(values, fmt, ctype, kind, target=None, minmax=False):
        while len(buf) % 4:
            buf.append(0)
        start = len(buf)
        for v in values:
            buf.extend(struct.pack("<" + fmt, *(v if isinstance(v, (tuple, list)) else (v,))))
        view = {"buffer": 0, "byteOffset": start, "byteLength": len(buf) - start}
        if target:
            view["target"] = target
        views.append(view)
        acc = {"bufferView": len(views) - 1, "componentType": ctype, "count": len(values), "type": kind}
        if minmax:
            acc["min"] = [min(v[c] for v in values) for c in range(len(values[0]))] if kind != "SCALAR" else [min(values)]
            acc["max"] = [max(v[c] for v in values) for c in range(len(values[0]))] if kind != "SCALAR" else [max(values)]
        accessors.append(acc)
        return len(accessors) - 1

    pose = rest_pose(skeleton, mesh)
    nodes = []
    for (bone, parent), (t, q, s) in zip(skeleton.bones, pose):
        nodes.append({"name": bone, "translation": list(t_from_game(t)), "rotation": list(q_swap(q)),
                      "scale": list(s_swap(s))})
    for b, (_, parent) in enumerate(skeleton.bones):
        if parent >= 0:
            nodes[parent].setdefault("children", []).append(b)
    roots = [b for b, (_, parent) in enumerate(skeleton.bones) if parent < 0]
    ref = reference_globals(skeleton, pose)
    ibms = []
    for g in ref:
        m, t = m_from_game(_inv(g))           # column-major, as glTF keeps matrices
        ibms.append((m[0], m[3], m[6], 0.0, m[1], m[4], m[7], 0.0, m[2], m[5], m[8], 0.0, t[0], t[1], t[2], 1.0))
    geo = mesh.geometry(0)
    by_name = {}
    for i, (bone, _) in enumerate(mesh.bones):
        b = skeleton.index(bone)
        if b is not None:
            by_name[i] = b
    positions = [t_from_game(p) for p in geo["positions"]]
    normals = []
    for n in geo["normals"]:
        x, y, z = t_from_game(n)
        length = math.sqrt(x * x + y * y + z * z) or 1.0
        normals.append((x / length, y / length, z / length))
    joints, weights = [], []
    for w in geo["weights"]:
        top = sorted(((by_name.get(b, 0), v) for b, v in (w or [])), key=lambda bw: -bw[1])[:4]
        total = sum(v for _, v in top) or 1.0
        top += [(0, 0.0)] * (4 - len(top))
        joints.append(tuple(b for b, _ in top))
        weights.append(tuple(v / total for _, v in top))
    indices = [i for tri in geo["triangles"] for i in tri]
    prim = {"attributes": {"POSITION": add(positions, "3f", 5126, "VEC3", 34962, minmax=True),
                           "NORMAL": add(normals, "3f", 5126, "VEC3", 34962),
                           "TEXCOORD_0": add(geo["uvs"], "2f", 5126, "VEC2", 34962),
                           "JOINTS_0": add(joints, "4H", 5123, "VEC4", 34962),
                           "WEIGHTS_0": add(weights, "4f", 5126, "VEC4", 34962)},
            "indices": add(indices, "I", 5125, "SCALAR", 34963)}
    mesh_node = len(nodes)
    nodes.append({"name": name, "mesh": 0, "skin": 0})
    skin = {"joints": list(range(len(skeleton.bones))), "skeleton": roots[0],
            "inverseBindMatrices": add(ibms, "16f", 5126, "MAT4")}
    animations = []
    for title, track_map, tracks, rate in examples:
        n = len(tracks[0][0])
        times = add([k / rate for k in range(n)], "f", 5126, "SCALAR", minmax=True)
        samplers, channels = [], []
        for b, (T, Q, S) in zip(track_map, tracks):
            if not 0 <= b < len(skeleton.bones):
                continue
            for path, values in (("translation", [t_from_game(v) for v in T]), ("rotation", [q_swap(v) for v in Q]),
                                 ("scale", [s_swap(v) for v in S])):
                samplers.append({"input": times, "output": add(values, f"{len(values[0])}f", 5126,
                                                                 "VEC4" if path == "rotation" else "VEC3"),
                                 "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1, "target": {"node": b, "path": path}})
        animations.append({"name": title, "samplers": samplers, "channels": channels})
    doc = {"asset": {"version": "2.0", "generator": "wcmods"}, "scene": 0,
           "scenes": [{"name": name, "nodes": roots + [mesh_node]}], "nodes": nodes,
           "meshes": [{"name": name, "primitives": [prim]}], "skins": [skin],
           "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(buf)}]}
    if animations:
        doc["animations"] = animations
    text = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    text += b" " * (-len(text) % 4)
    while len(buf) % 4:
        buf.append(0)
    total = 12 + 8 + len(text) + 8 + len(buf)
    return (struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<II", len(text), 0x4E4F534A) + text
            + struct.pack("<II", len(buf), 0x004E4942) + bytes(buf))
