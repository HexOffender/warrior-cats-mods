"""Models of a mod's own for accessories: an OBJ or glTF file (.obj, .gltf, .glb) made in Blender or any
3D program, put on a cat as a new look of one of the game's accessories.

The game's accessories are skinned meshes on the cat's skeleton, with body-shape morphs (SHP_Slim,
SHP_Brawny, SHP_Chubby...) so they follow the cat's build. A model has neither, so wcmods gives it the
cat's own: every vertex takes the bone weights and morph deltas of the nearest points of the cat's body
(SK_CatMaster, the skin under the fur), as if it were painted on. Then it goes into a copy of the
accessory's mesh (formats/skelmesh.py) with the accessory's material, so its look (texture) shows on it
through the model's UVs.

Space: a model is in metres with Y up and the cat facing +Z, which is what Blender's OBJ and glTF
exporters write by default (Blender's front view looks at the cat's face). The game's meshes are in
centimetres with Z up and the cat facing +Y, so (x, y, z) in a file is (100 x, 100 z, 100 y) in the
game. Swapping two axes mirrors the space, which also turns the files' counter-clockwise triangles into
the game's clockwise ones, so the vertex order of a triangle stays as it is. OBJ's texture V runs up
the picture and the game's down (glTF's too), so an OBJ's V is flipped.

`start_kit` writes the accessory and the cat as OBJ files to model on, with the look as a PNG.
"""
import base64
import io
import json
import math
import os
import struct
import zipfile

SCALE = 100.0                   # centimetres in a metre
FORMATS = (".obj", ".gltf", ".glb")
MAX_VERTICES = 65535            # 16-bit indices, as the game's accessories use
MAX_TRIANGLES = 120000
MAX_FILE = 64 * 1024 * 1024
NEAREST = 4                     # body vertices a model's vertex takes its weights from
BODY = "/Game/Art/Characters/CatMaster/Skel/SK_CatMaster"
FAR = 25.0                      # cm: a model this far from the cat is probably in the wrong place or units


def to_game(x, y, z):
    return (x * SCALE, z * SCALE, y * SCALE)


def from_game(x, y, z):
    return (x / SCALE, z / SCALE, y / SCALE)


class Model:
    """A model in the game's space: positions (cm), normals, UVs (V down), triangles (index triples)."""

    def __init__(self, positions, normals, uvs, triangles):
        self.positions, self.normals, self.uvs, self.triangles = positions, normals, uvs, triangles

    def bounds(self):
        lo = [min(p[c] for p in self.positions) for c in range(3)]
        hi = [max(p[c] for p in self.positions) for c in range(3)]
        return lo, hi

    def summary(self):
        lo, hi = self.bounds()
        return {"vertices": len(self.positions), "triangles": len(self.triangles),
                "size_cm": [round(hi[c] - lo[c], 2) for c in range(3)],
                "centre_cm": [round((hi[c] + lo[c]) / 2, 2) for c in range(3)]}


# ---------------------------------------------------------------------------------------------- reading
def read(name, data, sibling=None):
    """A Model from a file's bytes; `name` gives the format by its extension. `sibling(name)` returns the
    bytes of a file a .gltf refers to (its .bin), or None. ValueError says what's wrong with it."""
    if len(data) > MAX_FILE:
        raise ValueError(f"the model is over {MAX_FILE // 1024 ** 2} MB")
    ext = os.path.splitext(name)[1].lower()
    try:
        if ext == ".obj":
            parts = _read_obj(data.decode("utf-8", "replace"))
        elif ext == ".glb":
            parts = _read_glb(data)
        elif ext == ".gltf":
            parts = _read_gltf(json.loads(data.decode("utf-8")), None, sibling)
        else:
            raise ValueError(f"models are {', '.join(FORMATS)} files")
    except (struct.error, KeyError, IndexError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"{os.path.basename(name)} isn't a model wcmods can read ({type(e).__name__}: {e})") from None
    return _finish(parts, name)


def _finish(parts, name):
    """Source-space triangles [(positions, normals or None, uvs or None) per corner] -> a welded Model."""
    positions, normals, uvs, triangles, index = [], [], [], [], {}
    need_normals = False
    for corners in parts:
        tri = []
        for p, n, t in corners:
            key = (p, n, t)
            i = index.get(key)
            if i is None:
                i = index[key] = len(positions)
                positions.append(p)
                normals.append(n)
                uvs.append(t if t is not None else (0.0, 0.0))
                need_normals |= n is None
            tri.append(i)
        if tri[0] != tri[1] and tri[1] != tri[2] and tri[0] != tri[2]:
            triangles.append(tuple(tri))
    if not triangles:
        raise ValueError(f"{os.path.basename(name)} has no triangles (export the mesh with its faces)")
    if len(positions) > MAX_VERTICES:
        raise ValueError(f"the model has {len(positions)} vertices; an accessory takes up to {MAX_VERTICES} "
                         "(Blender's Decimate modifier makes fewer)")
    if len(triangles) > MAX_TRIANGLES:
        raise ValueError(f"the model has {len(triangles)} triangles; an accessory takes up to {MAX_TRIANGLES}")
    if need_normals:
        normals = _smooth_normals(positions, normals, triangles)
    game_p = [to_game(*p) for p in positions]
    game_n = [_unit(to_game(*n)) for n in normals]
    return Model(game_p, game_n, uvs, triangles)


def _smooth_normals(positions, normals, triangles):
    """Normals for the vertices that have none: the area-weighted normals of the faces at that point
    (counter-clockwise faces, as the files keep them)."""
    acc = {}
    for a, b, c in triangles:
        n = _cross(_sub(positions[b], positions[a]), _sub(positions[c], positions[a]))
        for i in (a, b, c):
            s = acc.setdefault(positions[i], [0.0, 0.0, 0.0])
            for k in range(3):
                s[k] += n[k]
    return [n if n is not None else _unit(acc.get(p, (0.0, 1.0, 0.0))) for p, n in zip(positions, normals)]


def _read_obj(text):
    vs, vts, vns, out = [], [], [], []

    def ref(token, items, what):
        i = int(token)
        i = i - 1 if i > 0 else len(items) + i
        if not 0 <= i < len(items):
            raise ValueError(f"a face names {what} {token}, which the file hasn't got")
        return items[i]

    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0].startswith("#"):
            continue
        tag = parts[0]
        if tag == "v":
            vs.append(tuple(float(x) for x in parts[1:4]))
        elif tag == "vt":
            u = float(parts[1])
            v = float(parts[2]) if len(parts) > 2 else 0.0
            vts.append((u, 1.0 - v))                 # OBJ's V runs up the picture, the game's down
        elif tag == "vn":
            vns.append(tuple(float(x) for x in parts[1:4]))
        elif tag == "f":
            corners = []
            for tok in parts[1:]:
                bits = tok.split("/")
                p = ref(bits[0], vs, "vertex")
                t = ref(bits[1], vts, "texture coordinate") if len(bits) > 1 and bits[1] else None
                n = ref(bits[2], vns, "normal") if len(bits) > 2 and bits[2] else None
                corners.append((p, n, t))
            for k in range(1, len(corners) - 1):     # a polygon as a fan of triangles
                out.append((corners[0], corners[k], corners[k + 1]))
    return out


GLTF_TYPES = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
GLTF_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _read_glb(data):
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError("not a glTF 2 binary (.glb) file")
    p, doc, binary = 12, None, None
    while p + 8 <= min(length, len(data)):
        size, kind = struct.unpack_from("<II", data, p)
        chunk = data[p + 8:p + 8 + size]
        if kind == 0x4E4F534A:
            doc = json.loads(chunk.decode("utf-8"))
        elif kind == 0x004E4942 and binary is None:
            binary = chunk
        p += 8 + size + (-size % 4)
    if doc is None:
        raise ValueError("the .glb has no JSON part")
    return _read_gltf(doc, binary, None)


def _read_gltf(doc, binary, sibling):
    unsupported = [e for e in doc.get("extensionsRequired", []) if e not in ("KHR_materials_unlit", "KHR_texture_transform")]
    if unsupported:
        raise ValueError(f"the file needs {', '.join(unsupported)}, which wcmods can't read "
                         "(export it again with compression off)")
    buffers = []
    for b in doc.get("buffers", []):
        uri = b.get("uri")
        if uri is None:
            buffers.append(binary or b"")
        elif uri.startswith("data:"):
            buffers.append(base64.b64decode(uri.split(",", 1)[1]))
        else:
            data = sibling(uri) if sibling else None
            if data is None:
                raise ValueError(f"the .gltf keeps its data in {uri}; use a .glb (glTF Binary) instead, or keep "
                                 f"{uri} beside it")
            buffers.append(data)

    def accessor(i):
        a = doc["accessors"][i]
        if "sparse" in a:
            raise ValueError("sparse accessors aren't supported")
        view = doc["bufferViews"][a["bufferView"]]
        buf = buffers[view["buffer"]]
        fmt = GLTF_TYPES[a["componentType"]]
        width = GLTF_WIDTH[a["type"]]
        size = struct.calcsize("<" + fmt)
        stride = view.get("byteStride") or size * width
        start = view.get("byteOffset", 0) + a.get("byteOffset", 0)
        norm = a.get("normalized", False)
        scale = {"b": 127.0, "B": 255.0, "h": 32767.0, "H": 65535.0}.get(fmt) if norm else None
        out = []
        for k in range(a["count"]):
            v = struct.unpack_from(f"<{width}{fmt}", buf, start + k * stride)
            if scale:
                v = tuple(max(-1.0, x / scale) for x in v)
            out.append(v if width > 1 else v[0])
        return out

    out = []
    scene = doc.get("scenes", [{}])[doc.get("scene", 0)] if doc.get("scenes") else None
    roots = scene.get("nodes", []) if scene else range(len(doc.get("nodes", [])))
    nodes = doc.get("nodes", [])

    def visit(i, parent):
        node = nodes[i]
        m = _matmul(parent, _node_matrix(node))
        if "mesh" in node:
            _mesh(doc["meshes"][node["mesh"]], m, accessor, out)
        for c in node.get("children", []):
            visit(c, m)

    if nodes:
        for r in roots:
            visit(r, _IDENTITY)
    else:
        for mesh in doc.get("meshes", []):
            _mesh(mesh, _IDENTITY, accessor, out)
    return out


def _mesh(mesh, m, accessor, out):
    normal_m = _normal_matrix(m)
    for prim in mesh.get("primitives", []):
        mode = prim.get("mode", 4)
        attrs = prim["attributes"]
        if mode not in (4, 5, 6) or "POSITION" not in attrs:
            continue
        pos = [_apply(m, p, 1.0) for p in accessor(attrs["POSITION"])]
        nrm = [_unit(_apply(normal_m, n, 0.0)) for n in accessor(attrs["NORMAL"])] if "NORMAL" in attrs else None
        uv = [(float(t[0]), float(t[1])) for t in accessor(attrs["TEXCOORD_0"])] if "TEXCOORD_0" in attrs else None
        idx = accessor(prim["indices"]) if "indices" in prim else list(range(len(pos)))
        if mode == 4:
            tris = [idx[k:k + 3] for k in range(0, len(idx) - 2, 3)]
        elif mode == 5:
            tris = [(idx[k], idx[k + 1], idx[k + 2]) if k % 2 == 0 else (idx[k + 1], idx[k], idx[k + 2])
                    for k in range(len(idx) - 2)]
        else:
            tris = [(idx[0], idx[k], idx[k + 1]) for k in range(1, len(idx) - 1)]
        if _det3(m) < 0:                    # a mirrored node turns its faces inside out; turn them back
            tris = [(a, c, b) for a, b, c in tris]
        for t in tris:
            out.append(tuple((tuple(pos[i]), tuple(nrm[i]) if nrm else None, uv[i] if uv else None) for i in t))


_IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]   # column-major, as glTF keeps them


def _node_matrix(node):
    if "matrix" in node:
        return [float(x) for x in node["matrix"]]
    tx, ty, tz = node.get("translation", (0, 0, 0))
    qx, qy, qz, qw = node.get("rotation", (0, 0, 0, 1))
    sx, sy, sz = node.get("scale", (1, 1, 1))
    r = [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy + qz * qw), 2 * (qx * qz - qy * qw),
         2 * (qx * qy - qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz + qx * qw),
         2 * (qx * qz + qy * qw), 2 * (qy * qz - qx * qw), 1 - 2 * (qx * qx + qy * qy)]
    return [r[0] * sx, r[1] * sx, r[2] * sx, 0, r[3] * sy, r[4] * sy, r[5] * sy, 0,
            r[6] * sz, r[7] * sz, r[8] * sz, 0, tx, ty, tz, 1]


def _matmul(a, b):
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def _apply(m, v, w):
    return tuple(m[r] * v[0] + m[4 + r] * v[1] + m[8 + r] * v[2] + m[12 + r] * w for r in range(3))


def _det3(m):
    a, b, c, d, e, f, g, h, i = m[0], m[4], m[8], m[1], m[5], m[9], m[2], m[6], m[10]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _normal_matrix(m):
    """The inverse transpose of m's 3 x 3 part (as a 4 x 4, column-major), which keeps normals at right
    angles to their faces under any scale."""
    a, b, c, d, e, f, g, h, i = m[0], m[4], m[8], m[1], m[5], m[9], m[2], m[6], m[10]
    det = _det3(m) or 1.0
    inv = [(e * i - f * h), -(b * i - c * h), (b * f - c * e),
           -(d * i - f * g), (a * i - c * g), -(a * f - c * d),
           (d * h - e * g), -(a * h - b * g), (a * e - b * d)]      # rows of the inverse, times det
    # transpose of the inverse, column-major: column j is row j of the inverse
    return [inv[0] / det, inv[1] / det, inv[2] / det, 0, inv[3] / det, inv[4] / det, inv[5] / det, 0,
            inv[6] / det, inv[7] / det, inv[8] / det, 0, 0, 0, 0, 1]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(v):
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (0.0, 0.0, 1.0)


# ------------------------------------------------------------------------------------------- placing
# Where a model sits on the cat, tweaked: moved (cm), turned (degrees) and scaled, in the cat's own terms.
# The game's X is the cat's left, Y its front, Z up. Scaling and turning are about the model's centre
# (the middle of its bounds); then it moves. Yaw turns its front toward the cat's left, pitch raises its
# front, roll lowers its left side.
MOVES = ("forward", "up", "left")
TURNS = ("yaw", "pitch", "roll")
PLACE_KEYS = set(MOVES) | set(TURNS) | {"scale"}
MAX_MOVE, MAX_SCALE = 100.0, 20.0


def check_place(spec, where):
    """Raise ValueError for a "place" that can't be used."""
    if not isinstance(spec, dict):
        raise ValueError(f'{where}: "place" should be an object, e.g. {{"up": 1.5, "scale": 1.2}}')
    unknown = sorted(k for k in spec if k not in PLACE_KEYS and not k.startswith("_"))
    if unknown:
        raise ValueError(f'{where}: "place" has unknown key(s) {", ".join(unknown)} (it takes '
                         f'{", ".join(MOVES + TURNS)} and scale)')

    def number(key, v, lo, hi):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise ValueError(f'{where}: "place" {key} should be a number from {lo:g} to {hi:g}')

    for k in MOVES:
        if k in spec:
            number(k, spec[k], -MAX_MOVE, MAX_MOVE)
    for k in TURNS:
        if k in spec:
            number(k, spec[k], -360, 360)
    s = spec.get("scale")
    if isinstance(s, dict):
        bad = sorted(set(s) - set(MOVES))
        if bad:
            raise ValueError(f'{where}: "place" scale takes forward, up and left, not {", ".join(bad)}')
        for k, v in s.items():
            number(f"scale {k}", v, 0.01, MAX_SCALE)
    elif s is not None:
        number("scale", s, 0.01, MAX_SCALE)


def _scales(spec):
    s = spec.get("scale", 1.0)
    if isinstance(s, dict):
        return (float(s.get("left", 1.0)), float(s.get("forward", 1.0)), float(s.get("up", 1.0)))
    return (float(s),) * 3


def _turn(v, roll, pitch, yaw):
    """Roll, then pitch, then yaw (radians) of a vector in the game's space."""
    x, y, z = v
    c, s = math.cos(roll), math.sin(roll)
    x, z = x * c + z * s, -x * s + z * c
    c, s = math.cos(pitch), math.sin(pitch)
    y, z = y * c - z * s, y * s + z * c
    c, s = math.cos(yaw), math.sin(yaw)
    x, y = x * c + y * s, -x * s + y * c
    return (x, y, z)


def place(model, spec):
    """The model moved, turned and scaled as `spec` says ("place" in items.json, check_place first)."""
    if not spec:
        return model
    sx, sy, sz = _scales(spec)
    roll, pitch, yaw = (math.radians(float(spec.get(k, 0.0))) for k in ("roll", "pitch", "yaw"))
    move = (float(spec.get("left", 0.0)), float(spec.get("forward", 0.0)), float(spec.get("up", 0.0)))
    lo, hi = model.bounds()
    c = [(a + b) / 2 for a, b in zip(lo, hi)]
    positions = []
    for p in model.positions:
        v = _turn(((p[0] - c[0]) * sx, (p[1] - c[1]) * sy, (p[2] - c[2]) * sz), roll, pitch, yaw)
        positions.append((v[0] + c[0] + move[0], v[1] + c[1] + move[1], v[2] + c[2] + move[2]))
    # A normal scales by the inverse of the scale, so it stays square to its stretched face.
    normals = [_unit(_turn((n[0] / sx, n[1] / sy, n[2] / sz), roll, pitch, yaw)) for n in model.normals]
    return Model(positions, normals, list(model.uvs), list(model.triangles))


def from_mesh(mesh, lod=0):
    """One of the game's meshes (skelmesh.SkeletalMesh) as a Model, to place the game's own shape."""
    geo = mesh.geometry(lod)
    return Model(geo["positions"], geo["normals"], geo["uvs"], geo["triangles"])


# --------------------------------------------------------------------------------------------- tangents
def tangents(model):
    """(x, y, z, sign) a vertex: the direction U grows along the surface, square to the normal, and
    whether V grows along the normal x tangent (sign 1) or against it (-1). Accumulated per triangle
    from its UVs; a vertex whose UVs say nothing gets any direction square to its normal."""
    n = len(model.positions)
    tan = [[0.0, 0.0, 0.0] for _ in range(n)]
    bit = [[0.0, 0.0, 0.0] for _ in range(n)]
    P, T = model.positions, model.uvs
    for a, b, c in model.triangles:
        e1, e2 = _sub(P[b], P[a]), _sub(P[c], P[a])
        du1, dv1 = T[b][0] - T[a][0], T[b][1] - T[a][1]
        du2, dv2 = T[c][0] - T[a][0], T[c][1] - T[a][1]
        det = du1 * dv2 - du2 * dv1
        if abs(det) < 1e-12:
            continue
        r = 1.0 / det
        t = [(e1[k] * dv2 - e2[k] * dv1) * r for k in range(3)]
        s = [(e2[k] * du1 - e1[k] * du2) * r for k in range(3)]
        for i in (a, b, c):
            for k in range(3):
                tan[i][k] += t[k]
                bit[i][k] += s[k]
    out = []
    for i in range(n):
        nrm = model.normals[i]
        t = tan[i]
        d = _dot(nrm, t)
        t = (t[0] - nrm[0] * d, t[1] - nrm[1] * d, t[2] - nrm[2] * d)
        if _dot(t, t) < 1e-12:                   # no UV direction here: any tangent square to the normal
            other = (1.0, 0.0, 0.0) if abs(nrm[0]) < 0.9 else (0.0, 1.0, 0.0)
            t = _cross(nrm, other)
        t = _unit(t)
        sign = -1.0 if _dot(_cross(nrm, t), bit[i]) < 0 else 1.0
        out.append((t[0], t[1], t[2], sign))
    return out


# ------------------------------------------------------------------------------------------ the cat's skin
class Skin:
    """The cat's body (its skin, without the eyes) as a source of bone weights and body-shape morphs."""

    def __init__(self, mesh, morph_names):
        geo = mesh.geometry(0)
        sec = mesh.lods[0].sections[0]
        keep = range(sec.base_vertex, sec.base_vertex + sec.vertices)
        self.positions = [geo["positions"][i] for i in keep]
        self.weights = [geo["weights"][i] for i in keep]
        self.morphs = {}
        for name in morph_names:
            deltas = geo["morphs"].get(name, {})
            self.morphs[name] = [deltas.get(i) for i in keep]
        self.cell = 1.5
        self.grid = {}
        for k, p in enumerate(self.positions):
            self.grid.setdefault(self._key(p), []).append(k)

    def _key(self, p):
        return (math.floor(p[0] / self.cell), math.floor(p[1] / self.cell), math.floor(p[2] / self.cell))

    def nearest(self, p, k=NEAREST):
        """[(distance, body vertex)] for the k body vertices nearest p, searching outward ring by ring."""
        cx, cy, cz = self._key(p)
        found, r = [], 0
        while True:
            for x in range(cx - r, cx + r + 1):
                for y in range(cy - r, cy + r + 1):
                    for z in range(cz - r, cz + r + 1):
                        if max(abs(x - cx), abs(y - cy), abs(z - cz)) != r:
                            continue
                        for i in self.grid.get((x, y, z), ()):
                            found.append((math.dist(p, self.positions[i]), i))
            # Everything within r cells is in; anything else is at least r * cell away.
            found.sort()
            if len(found) >= k and found[k - 1][0] <= r * self.cell or r > 200:
                return found[:k]
            r += 1

    def bind(self, model):
        """(weights, morphs, farthest): per model vertex [(bone, weight)], {morph: [(vertex, (dx, dy, dz),
        (nx, ny, nz) or None)]}, and how far its farthest vertex is from the cat (cm)."""
        weights, morphs, farthest = [], {name: [] for name in self.morphs}, 0.0
        for v, p in enumerate(model.positions):
            near = self.nearest(p)
            farthest = max(farthest, near[0][0])
            ws = [1.0 / (d * d + 0.01) for d, _ in near]
            total = sum(ws)
            ws = [w / total for w in ws]
            bones = {}
            for w, (_, i) in zip(ws, near):
                for b, x in self.weights[i]:
                    bones[b] = bones.get(b, 0.0) + w * x
            weights.append(sorted(bones.items(), key=lambda bw: -bw[1]))
            for name, deltas in self.morphs.items():
                d, n, any_n, moved = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], False, False
                for w, (_, i) in zip(ws, near):
                    e = deltas[i]
                    if e is None:
                        continue
                    moved = True
                    for c in range(3):
                        d[c] += w * e[0][c]
                    if e[1] is not None:
                        any_n = True
                        for c in range(3):
                            n[c] += w * e[1][c]
                if moved:
                    morphs[name].append((v, tuple(d), tuple(n) if any_n else None))
        return weights, morphs, farthest


def mesh_model(model, skin):
    """The model in skelmesh.SkeletalMesh.set_geometry's terms, tied to the cat by `skin`, and how far
    it reaches from the cat."""
    weights, morphs, farthest = skin.bind(model)
    return ({"positions": model.positions, "normals": model.normals, "tangents": tangents(model), "uvs": model.uvs,
             "triangles": model.triangles, "weights": weights, "morphs": morphs}, farthest)


class Body:
    """The cat's body, read once an install and only when a model needs it."""

    def __init__(self, game):
        self.game, self._data, self._mesh, self._skins = game, None, None, {}

    def data(self):
        if self._data is None:
            from .formats import texture
            self._data = self.game.read(texture.content_path(BODY))
        return self._data

    def skin(self, morph_names):
        from .formats import skelmesh
        key = tuple(morph_names)
        if key not in self._skins:
            if self._mesh is None:
                self._mesh = skelmesh.SkeletalMesh(self.data())
            self._skins[key] = Skin(self._mesh, morph_names)
        return self._skins[key]


CACHE_VERSION = 1   # change when the mesh copy, the transfer or the readers change, so cached meshes are made again


def build(ctx, package, like, model, key, body):
    """{"data", "chunk_id", "imports", "shaders", "farthest"} for a new mesh `package`: a copy of the game's
    mesh `like` (an asset path) with `model` (a Model, or a function that reads one) tied to the cat's
    `body` (a Body). Kept in cache/meshes under the template's and the body's bytes and `key`, text that
    changes whenever the model would, so an install doesn't make the same mesh twice."""
    import hashlib
    from .formats import skelmesh, texture
    template = ctx.read_game_file(texture.content_path(like.split(".", 1)[0]))
    digest = hashlib.sha1(f"{CACHE_VERSION}|{package}|{like}|{key}|".encode() + hashlib.sha1(template).digest()
                          + hashlib.sha1(body.data()).digest()).hexdigest()
    cache = os.path.join(ctx.cache_dir, "meshes")
    found, meta = os.path.join(cache, digest + ".uasset"), os.path.join(cache, digest + ".json")
    imports, shaders = ctx.game.io.container_header().entry_for(texture.package_id(like.split(".", 1)[0]))
    if os.path.isfile(found) and os.path.isfile(meta):
        with open(found, "rb") as f:
            data = f.read()
        with open(meta, encoding="utf-8") as f:
            farthest = json.load(f).get("farthest", 0.0)
        os.utime(found)                         # used: kept by the clear-out
    else:
        texture._clear_out(cache)
        mesh = skelmesh.SkeletalMesh(template)
        geo, farthest = mesh_model(model() if callable(model) else model, body.skin(mesh.morph_names))
        mesh.set_geometry(geo)
        mesh.rename(package, package.rsplit("/", 1)[-1])
        data = mesh.bytes()
        os.makedirs(cache, exist_ok=True)
        for path, content in ((meta, json.dumps({"farthest": farthest}).encode()), (found, data)):
            with open(path + ".tmp", "wb") as f:
                f.write(content)
            os.replace(path + ".tmp", path)
    return {"data": data, "chunk_id": texture.chunk_id(texture.package_id(package), texture.CHUNK_EXPORT_BUNDLE),
            "imports": imports, "shaders": shaders, "farthest": farthest}


def script(worn):
    """The WCModsModels script (lua/models.lua) for {slot: {accessory: {look number: {"mesh": asset path,
    "opacity": 0..1, "glass": linear [r, g, b]}}}} (each key there only when the look has it), the slot as
    the cat's CustomData names it (Neck, Paw, Body, Head)."""
    from .lua import source
    from .sdk import lua_value
    return source("models.lua").replace("@MODELS@", lua_value(worn))


# --------------------------------------------------------------------------------------------- writing
def write_obj(name, geo, material=None, triangles=None):
    """OBJ text for a mesh's geometry (skelmesh's geometry() or a Model's lists): metres, Y up."""
    lines = [f"# {name}, written by wcmods: metres, Y up, the cat facing +Z (Blender's OBJ defaults)"]
    if material:
        lines.append(f"mtllib {material}.mtl")
    lines.append(f"o {name}")
    for p in geo["positions"]:
        x, y, z = from_game(*p)
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
    for u, v in geo["uvs"]:
        lines.append(f"vt {u:.6f} {1.0 - v:.6f}")
    for n in geo["normals"]:
        x, y, z = _unit(from_game(*n))
        lines.append(f"vn {x:.5f} {y:.5f} {z:.5f}")
    if material:
        lines.append(f"usemtl {material}")
    lines.append("s 1")
    for a, b, c in triangles or geo["triangles"]:
        lines.append(f"f {a + 1}/{a + 1}/{a + 1} {b + 1}/{b + 1}/{b + 1} {c + 1}/{c + 1}/{c + 1}")
    return "\n".join(lines) + "\n"


README = """Making a model for {name}
{rule}

{accessory}.obj is the game's {name}, where it sits on the cat; cat.obj is the cat it sits on (its skin,
under the fur, in the build every cat starts from). Open both in Blender (File > Import > Wavefront .obj,
with its default settings), then make your own shape in the same place: change this one, or model a new
one around the cat.

- Units are metres, Y up, the cat facing +Z: Blender's OBJ and glTF defaults, so import and export
  as they are. The cat is about 0.3 m long.
- Keep it close to the cat: every point of your model follows the nearest part of the cat's body as it
  moves and changes shape. Leave a little room for the fur (half a centimetre or so).
- Give it UVs: its look (a picture, {accessory}.png here) is painted on through them.
- Export only your model (select it, then File > Export, "Selected Only"): Wavefront .obj, or glTF
  Binary (.glb). Leave the cat out.

Then in Clan Mod Studio's Items page, choose your accessory and "Shape: a model of my own...".
In items.json it's "model": "models/my-collar.obj" (docs/SDK.md, New items).
"""


def start_kit(game, accessory, look=1, texture_mip=1):
    """A .zip to model on: the accessory (`accessory` its name, e.g. "DogCollar") and the cat as OBJ, the
    accessory's look `look` as a PNG, and a README. Returns (zip bytes, file name)."""
    from . import accessories
    from .formats import png, skelmesh, texture
    gui = game.read(accessories.GUI_MANAGER)
    lists, meshes = accessories.read_variations(gui), accessories.read_meshes(gui)
    if accessory not in meshes:
        raise ValueError(f"the game has no accessory {accessory}")
    mesh = skelmesh.SkeletalMesh(game.read(texture.content_path(meshes[accessory].split(".", 1)[0])))
    body = skelmesh.SkeletalMesh(game.read(texture.content_path(BODY)))
    files = {}
    files[f"{accessory}.obj"] = write_obj(accessory, mesh.geometry(0), material=accessory)
    files[f"{accessory}.mtl"] = f"newmtl {accessory}\nKd 1 1 1\nmap_Kd {accessory}.png\n"
    geo = body.geometry(0)
    sec = body.lods[0].sections[0]
    first = sec.base_index // 3
    files["cat.obj"] = write_obj("cat", geo, triangles=geo["triangles"][first:first + sec.triangles])
    textures = lists.get(accessory) or []
    try:                                  # some head accessories' looks are effects, not pictures
        tex = texture.load(game, textures[min(max(look, 1), len(textures)) - 1])
        w, h, rgba = tex.image(min(texture_mip, len(tex.mips) - 1))
        files[f"{accessory}.png"] = png.write(w, h, rgba)
    except (IndexError, ValueError):
        pass
    files["README.txt"] = README.format(name=accessory, rule="=" * (len(accessory) + 20), accessory=accessory)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for fname, data in files.items():
            z.writestr(fname, data)
    return out.getvalue(), f"{accessory}-model.zip"
