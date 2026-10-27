"""The game's cooked skeletal meshes (accessories, the cat's body), read and copied with new geometry.

A mod's own model for an accessory becomes a copy of one of the game's accessory meshes under a new
name: the same skeleton, materials, LOD settings and body-shape morphs, with the model's vertices and
triangles in every LOD. As with textures (texture.py), cooking one from scratch would mean writing every
part of a cooked USkeletalMesh; a copy keeps the game's layout and changes only what the geometry decides.

The package (UE 5.7, unversioned): an AnimCurveMetaData, one UMorphTarget export per morph, then the
mesh. The mesh export is its properties (copied as they are, but for a copy of the imported bounds),
a u32 HasGuid, then:
  * FStripDataFlags, ImportedBounds (FBoxSphereBounds, 7 doubles), the materials (FSkeletalMaterial:
    material, slot name, a u32 "imported name follows" flag, FMeshUVChannelInfo, a u32 0), the
    reference skeleton (bones: FName and parent; bind poses: FTransform, 10 doubles; the name map);
  * a u32 bCooked, then each LOD's render data, and a fixed tail (in-lined LOD counts and such).
A LOD is: strip flags, bIsLODCookedOut, bInlined, RequiredBones (u16), the render sections, the
ActiveBoneIndices, BuffersSize (the streamed data's length), then that streamed data: strip flags,
the index buffer (u8 type size, then u16 or u32 indices), positions (FVector3f), tangents (two
FPackedNormals a vertex) and UVs (half floats), skin weights (MaxBoneInfluences bone indices into the
section's BoneMap, then as many u8 weights, a vertex), an empty lookup buffer, vertex colours, an
empty skin weight profile map, 36 bytes the game's meshes all have alike, the morph targets' GPU
data, and 14 more fixed bytes.

The morph data (FMorphTargetVertexInfoBuffers) is a u32 stream: a 40-byte header for every batch of up
to 64 moved vertices (data offset in bytes, packed bit widths and count, the first vertex index, the
position minimums, tangent bit widths and minimums), then the batches' bit-packed elements: index
offset, position delta and, when the batch has them, normal (TangentZ) deltas, each a quantized
integer above the batch minimum. Then per morph its smallest and largest delta (FVector4f: xyz the
position, w the normal's), its first batch, how many, the total, and the two precisions.

Each UMorphTarget export says, per LOD, how many vertices it moves; those counts are rewritten too.
"""
import math
import struct

from .cityhash import name_hash
from .cooked import ZenPackage
from .texture import export_hash

EXPORT_ENTRY = 72
BATCH = 64                   # vertices in a morph batch
HEADER_WORDS = 10            # a batch header's u32s
PAD_WORDS = 3                # zero u32s after the morph data, so the GPU can read past its last element
DEFAULT_PRECISION = (0.004, 1 / 2048)   # the game's morph position and normal steps (cm, unit normal)
MAX_BONES_PER_SECTION = 255  # bone indices in the skin buffer are bytes


class FormatError(ValueError):
    """The mesh isn't laid out as wcmods expects (a game update may have changed it)."""


class _R:
    def __init__(self, data, pos=0):
        self.d, self.p = data, pos

    def t(self, fmt):
        v = struct.unpack_from("<" + fmt, self.d, self.p)
        self.p += struct.calcsize("<" + fmt)
        return v if len(v) > 1 else v[0]

    def raw(self, n):
        if self.p + n > len(self.d):
            raise FormatError("the mesh ends early")
        b = self.d[self.p:self.p + n]
        self.p += n
        return bytes(b)

    def arr(self, fmt):
        n = self.t("i")
        if not 0 <= n < 1 << 24:
            raise FormatError("an array's size is out of range")
        return [self.t(fmt) for _ in range(n)]

    def bulk(self, elem=None):
        size, n = self.t("ii")
        if elem is not None and n and size != elem:
            raise FormatError(f"a buffer has {size}-byte elements, not {elem}")
        if not 0 <= n < 1 << 26 or not 0 <= size < 64:
            raise FormatError("a buffer's size is out of range")
        return size, self.raw(size * n)


def _bulk(size, data):
    return struct.pack("<ii", size, len(data) // size if size else 0) + data


def _arr(fmt, values):
    return struct.pack("<i", len(values)) + b"".join(struct.pack("<" + fmt, *(v if isinstance(v, tuple) else (v,)))
                                                       for v in values)


# ---------------------------------------------------------------------------------------------- morphs
def _bits(v):
    return v.bit_length() if v > 0 else 0


def decode_morphs(words, starts, counts, pos_prec, tan_prec):
    """[[(vertex, (dx, dy, dz) quantized, (nx, ny, nz) quantized or None), ...] per morph]."""
    blob = struct.pack(f"<{len(words)}I", *words)
    out = []
    for first, n in zip(starts, counts):
        elems = []
        for b in range(first, first + n):
            h = words[b * HEADER_WORDS:(b + 1) * HEADER_WORDS]
            if len(h) < HEADER_WORDS:
                raise FormatError("a morph batch header runs past the data")
            off, packed, imin = h[0], h[1], h[2]
            pmin = struct.unpack("<3i", struct.pack("<3I", *h[3:6]))
            tmin = struct.unpack("<3i", struct.pack("<3I", *h[7:10]))
            ib, pb = packed & 31, ((packed >> 5) & 31, (packed >> 10) & 31, (packed >> 15) & 31)
            tan, ne = (packed >> 20) & 1, packed >> 21
            tb = (h[6] & 31, (h[6] >> 5) & 31, (h[6] >> 10) & 31)
            per = ib + sum(pb) + (sum(tb) if tan else 0)
            size = (ne * per + 7) // 8
            if off + size > len(blob):
                raise FormatError("a morph batch runs past the data")
            bits = int.from_bytes(blob[off:off + size], "little")
            q = 0
            for e in range(ne):
                v = bits >> q
                q += per
                idx = (v & ((1 << ib) - 1)) + imin + e
                v >>= ib
                d = []
                for c in range(3):
                    d.append((v & ((1 << pb[c]) - 1)) + pmin[c])
                    v >>= pb[c]
                t = None
                if tan:
                    t = []
                    for c in range(3):
                        t.append((v & ((1 << tb[c]) - 1)) + tmin[c])
                        v >>= tb[c]
                    t = tuple(t)
                elems.append((idx, tuple(d), t))
        out.append(elems)
    return out


def encode_morphs(morphs):
    """(words, batch starts, batch counts, total batches) for morphs as decode_morphs gives them."""
    headers, datas, starts, counts = [], [], [], []
    for elems in morphs:
        starts.append(len(headers))
        n = 0
        for b in range(0, len(elems), BATCH):
            batch = elems[b:b + BATCH]
            imin = batch[0][0]
            ib = _bits(max(e[0] - imin - k for k, e in enumerate(batch)))
            pmin = [min(e[1][c] for e in batch) for c in range(3)]
            pb = [_bits(max(e[1][c] for e in batch) - pmin[c]) for c in range(3)]
            tan = any(e[2] is not None for e in batch)
            ts = [e[2] or (0, 0, 0) for e in batch]
            tmin = [min(t[c] for t in ts) for c in range(3)] if tan else [0, 0, 0]
            tb = [_bits(max(t[c] for t in ts) - tmin[c]) for c in range(3)] if tan else [0, 0, 0]
            per = ib + sum(pb) + sum(tb)
            value, q = 0, 0
            for k, (e, t) in enumerate(zip(batch, ts)):
                fields = [(e[0] - imin - k, ib)] + [(e[1][c] - pmin[c], pb[c]) for c in range(3)]
                if tan:
                    fields += [(t[c] - tmin[c], tb[c]) for c in range(3)]
                for v, w in fields:
                    value |= v << q
                    q += w
            nbytes = (len(batch) * per + 31) // 32 * 4
            datas.append(value.to_bytes(nbytes, "little"))
            headers.append((imin, pb, tan, len(batch), ib, pmin, tb, tmin))
            n += 1
        counts.append(n)
    words, offset = [], len(headers) * HEADER_WORDS * 4
    for (imin, pb, tan, ne, ib, pmin, tb, tmin), data in zip(headers, datas):
        words += [offset, ib | pb[0] << 5 | pb[1] << 10 | pb[2] << 15 | (1 << 20 if tan else 0) | ne << 21, imin]
        words += [v & 0xFFFFFFFF for v in pmin]
        words += [tb[0] | tb[1] << 5 | tb[2] << 10] + [v & 0xFFFFFFFF for v in tmin]
        offset += len(data)
    data = b"".join(datas)
    words += list(struct.unpack(f"<{len(data) // 4}I", data)) + [0] * PAD_WORDS
    return words, starts, counts, len(headers)


def quantize_morph(deltas, pos_prec, tan_prec):
    """[(vertex, (dx, dy, dz), (nx, ny, nz) or None)] in floats -> the quantized elements a morph keeps:
    those that still move after rounding, in vertex order."""
    out = []
    for v, d, n in sorted(deltas, key=lambda e: e[0]):
        qd = tuple(int(math.floor(x / pos_prec + 0.5)) for x in d)
        qn = tuple(int(math.floor(x / tan_prec + 0.5)) for x in n) if n is not None else None
        if qn is not None and not any(qn):
            qn = None
        if any(qd) or qn is not None:
            out.append((v, qd, qn))
    return out


def morph_extents(elems, pos_prec, tan_prec):
    """(minimum, maximum) FVector4f of a morph's deltas: xyz the position's, w the normal's."""
    if not elems:
        return (0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0)
    lo = [min(e[1][c] for e in elems) * pos_prec for c in range(3)]
    hi = [max(e[1][c] for e in elems) * pos_prec for c in range(3)]
    ns = [x for e in elems if e[2] for x in e[2]]
    return (*lo, min(ns) * tan_prec if ns else 0.0), (*hi, max(ns) * tan_prec if ns else 0.0)


# ------------------------------------------------------------------------------------------------ LODs
class Section:
    FIELDS = "HIIIBIII"

    def __init__(self, r):
        self.strip = r.raw(2)
        (self.material, self.base_index, self.triangles, self.recompute_tangent, self.mask_channel,
         self.cast_shadow, self.ray_tracing, self.base_vertex) = r.t(self.FIELDS)
        if r.t("i"):
            raise FormatError("meshes with cloth can't be copied")
        self.bone_map = r.arr("H")
        self.vertices, self.max_influences, self.cloth_asset = r.t("Iih")
        self.clothing = r.raw(20)
        if not self.strip[1] & 1:
            raise FormatError("a section keeps its duplicated vertices, which wcmods doesn't read")
        self.disabled = r.t("I")

    def bytes(self):
        return (self.strip + struct.pack("<" + self.FIELDS, self.material, self.base_index, self.triangles,
                                         self.recompute_tangent, self.mask_channel, self.cast_shadow,
                                         self.ray_tracing, self.base_vertex)
                + struct.pack("<i", 0) + _arr("H", self.bone_map)
                + struct.pack("<Iih", self.vertices, self.max_influences, self.cloth_asset)
                + self.clothing + struct.pack("<I", self.disabled))


class Lod:
    def __init__(self, r, has_colours):
        self.strip = r.raw(2)
        cooked_out, self.inlined = r.t("II")
        if cooked_out or not self.inlined:
            raise FormatError("a LOD isn't in the package itself (streamed LODs can't be copied)")
        self.required = r.arr("H")
        self.sections = [Section(r) for _ in range(r.t("i"))]
        self.active = r.arr("H")
        size = r.t("I")
        start = r.p
        self.stream_strip = r.raw(2)
        self.index_size = r.t("B")
        if self.index_size not in (2, 4):
            raise FormatError(f"{self.index_size}-byte indices")
        _, raw = r.bulk(self.index_size)
        self.indices = list(struct.unpack(f"<{len(raw) // self.index_size}{'H' if self.index_size == 2 else 'I'}", raw))
        stride, n = r.t("II")
        _, raw = r.bulk(12)
        if stride != 12 or len(raw) != 12 * n:
            raise FormatError("unexpected position buffer")
        self.positions = [struct.unpack_from("<3f", raw, 12 * i) for i in range(n)]
        self.smvb_strip = r.raw(2)
        self.uv_channels, nv, full_uv, high_tan = r.t("IIII")
        if nv != n or full_uv or high_tan:
            raise FormatError("only half-precision UVs and packed tangents are supported")
        _, self.tangents = r.bulk(8)
        _, raw = r.bulk(4)
        if len(raw) != 4 * n * self.uv_channels or len(self.tangents) != 8 * n:
            raise FormatError("the vertex buffers disagree on the vertex count")
        self.uvs = [struct.unpack_from(f"<{2 * self.uv_channels}e", raw, 4 * self.uv_channels * i) for i in range(n)]
        self.skin_strip = r.raw(2)
        variable, self.influences, total, nvs, b16, w16 = r.t("IIIIII")
        if variable or b16 or w16 or nvs != n or total != n * self.influences:
            raise FormatError("only fixed 8-bit skin weights are supported")
        _, self.skin = r.bulk(1)
        if len(self.skin) != 2 * self.influences * n:
            raise FormatError("unexpected skin weight buffer size")
        self.lookup = r.raw(2 + 4 + 8)
        if self.lookup[2:] != struct.pack("<Iii", 0, 4, 0):
            raise FormatError("a skin weight lookup buffer, which wcmods doesn't write")
        self.has_colours = has_colours
        if has_colours:
            self.colour_strip = r.raw(2)
            stride, ncol = r.t("II")
            _, self.colours = r.bulk(4)
            if stride != 4 or ncol != n or len(self.colours) != 4 * n:
                raise FormatError("unexpected vertex colour buffer")
        if r.t("i"):
            raise FormatError("skin weight profiles, which wcmods doesn't write")
        self.middle = r.raw(32)
        self.morphs, self.morph_min, self.morph_max = [], [], []
        self.pos_prec, self.tan_prec = DEFAULT_PRECISION
        self.has_morphs = r.t("I")              # a mesh without morph targets has no morph data
        if self.has_morphs not in (0, 1):
            raise FormatError("unexpected morph data flag")
        if self.has_morphs:
            words = r.arr("I")
            nm = r.t("i")
            self.morph_min = [r.t("4f") for _ in range(nm)]
            if r.t("i") != nm:
                raise FormatError("morph extents disagree")
            self.morph_max = [r.t("4f") for _ in range(nm)]
            starts, counts = r.arr("I"), r.arr("I")
            total, self.pos_prec, self.tan_prec = r.t("Iff")
            if len(starts) != nm or len(counts) != nm or total != sum(counts):
                raise FormatError("the morph batches don't add up")
            self.morphs = decode_morphs(words, starts, counts, self.pos_prec, self.tan_prec)
        self.end = r.raw(14)
        if r.p - start != size:
            raise FormatError("a LOD's buffers aren't the size it says")

    @property
    def vertex_count(self):
        return len(self.positions)

    def stream_bytes(self):
        n = len(self.positions)
        fmt = "H" if self.index_size == 2 else "I"
        out = [self.stream_strip, struct.pack("<B", self.index_size),
               _bulk(self.index_size, struct.pack(f"<{len(self.indices)}{fmt}", *self.indices)),
               struct.pack("<II", 12, n), _bulk(12, b"".join(struct.pack("<3f", *p) for p in self.positions)),
               self.smvb_strip, struct.pack("<IIII", self.uv_channels, n, 0, 0), _bulk(8, self.tangents),
               _bulk(4, b"".join(struct.pack(f"<{2 * self.uv_channels}e", *uv) for uv in self.uvs)),
               self.skin_strip, struct.pack("<IIIIII", 0, self.influences, n * self.influences, n, 0, 0),
               _bulk(1, self.skin), self.lookup]
        if self.has_colours:
            out += [self.colour_strip, struct.pack("<II", 4, n), _bulk(4, self.colours)]
        out += [struct.pack("<i", 0), self.middle, struct.pack("<I", self.has_morphs)]
        if self.has_morphs:
            words, starts, counts, total = encode_morphs(self.morphs)
            out += [_arr("I", words), _arr("4f", self.morph_min), _arr("4f", self.morph_max), _arr("I", starts),
                    _arr("I", counts), struct.pack("<Iff", total, self.pos_prec, self.tan_prec)]
        out.append(self.end)
        return b"".join(out)

    def bytes(self):
        stream = self.stream_bytes()
        return (self.strip + struct.pack("<II", 0, 1) + _arr("H", self.required)
                + struct.pack("<i", len(self.sections)) + b"".join(s.bytes() for s in self.sections)
                + _arr("H", self.active) + struct.pack("<I", len(stream)) + stream)


# ------------------------------------------------------------------------------------------------ mesh
def _find_start(ex, names):
    """Where the mesh's own data starts after its properties: strip flags, then bounds, materials and a
    reference skeleton whose first bone has no parent."""
    for p in range(2, len(ex) - 200):
        if not ex[p] & 1:                 # cooked: editor data stripped
            continue
        r = _R(ex, p + 2)
        b = r.t("7d")
        if not all(math.isfinite(x) and abs(x) < 1e7 for x in b) or min(b[3:]) < 0:
            continue
        nm = r.t("i")
        if not 0 < nm < 64:
            continue
        try:
            for _ in range(nm):
                r.t("i")
                i, _n = r.t("II")
                flag = r.t("I")
                if i >= len(names) or flag > 1:
                    raise FormatError("")
                if flag:
                    r.t("II")
                r.t("II4f")
                r.t("i")
            nb = r.t("i")
            if not 0 < nb < 2048:
                continue
            i, _n, parent = r.t("IIi")
            if i < len(names) and parent == -1:
                return p
        except (FormatError, struct.error):
            continue
    raise FormatError("couldn't find where the mesh's data starts (the game may have updated)")


class SkeletalMesh:
    """One of the game's cooked skeletal meshes, to read or to copy with new geometry. With morphs=False,
    which morph is which isn't worked out: the mesh's geometry can be read (without morphs), not copied
    (the animals' meshes that keep their morph list elsewhere read that way)."""

    def __init__(self, data, morphs=True):
        self.pkg = pkg = ZenPackage(data)
        em = pkg.summary[8]
        self.export_names = [pkg.names[struct.unpack_from("<I", pkg.data, em + EXPORT_ENTRY * i + 16)[0]]
                             for i in range(pkg.export_count)]
        package = pkg.names[pkg.summary[2]]
        short = package.rsplit("/", 1)[-1]
        if short not in self.export_names:
            raise FormatError(f"{package} has no export named {short}")
        self.main = self.export_names.index(short)
        exports = [pkg.export(i) for i in range(pkg.export_count)]
        if any(exports[i][0] != sum(s for _, s in exports[:i]) for i in range(len(exports))):
            raise FormatError("the mesh's exports aren't laid out as expected")
        self.exports = [bytearray(pkg.export_data[o:o + s]) for o, s in exports]
        self.trailer = pkg.export_data[sum(s for _, s in exports):]
        ex = bytes(self.exports[self.main])
        start = _find_start(ex, pkg.names)
        self.props = ex[:start]
        r = _R(ex, start)
        self.strip = r.raw(2)
        self.bounds_raw = r.raw(56)
        self.bounds = struct.unpack("<7d", self.bounds_raw)
        self.materials = []
        for _ in range(r.t("i")):
            at = r.p
            r.t("i")
            name = r.t("II")
            if r.t("I"):
                r.t("II")
            r.t("II4fi")
            self.materials.append((pkg.names[name[0]], ex[at:r.p]))
        at = r.p
        self.bones = []
        for _ in range(r.t("i")):
            name, number = r.t("II")
            self.bones.append((pkg.names[name] + (f"_{number - 1}" if number else ""), r.t("i")))
        self.poses = [r.t("10d") for _ in range(r.t("i"))]
        if len(self.poses) != len(self.bones):
            raise FormatError("bones and bind poses disagree")
        for _ in range(r.t("i")):
            r.t("IIi")
        self.skeleton = ex[at:r.p]             # the reference skeleton, which a copy keeps as it is
        if r.t("I") != 1:
            raise FormatError("the mesh isn't cooked")
        nlods = r.t("i")
        if not 0 < nlods <= 8:
            raise FormatError(f"{nlods} LODs")
        has_colours = None
        self.lods = []
        for _ in range(nlods):
            if has_colours is None:
                has_colours = _has_colours(ex, r.p)
            self.lods.append(Lod(r, has_colours))
        self.tail = ex[r.p:]
        # The morph targets, in the order the LOD buffers keep them: the MorphTargets property, the
        # array of their exports in the mesh's properties.
        morph_exports = [i for i, n in enumerate(self.export_names) if i != self.main and n.startswith("SHP_")]
        nm = len(self.lods[0].morphs) if morphs else 0
        self.morph_order = None
        for p in range(0, len(self.props) - 4 * (nm + 1)):
            if struct.unpack_from("<i", self.props, p)[0] != nm:
                continue
            vals = struct.unpack_from(f"<{nm}i", self.props, p + 4)
            if sorted(vals) == [i + 1 for i in morph_exports] and nm:
                self.morph_order = [v - 1 for v in vals]
                break
        if nm and self.morph_order is None:
            raise FormatError("couldn't tell which morph target is which")
        self.morph_order = self.morph_order or []
        self.morph_names = [self.export_names[i] for i in self.morph_order]
        for i in self.morph_order:
            self._morph_lods(i)                 # checks each can be rewritten

    # ---------------------------------------------------------------------------- the morph exports
    def _morph_lods(self, i):
        """(offset of the per-LOD list, [(moved, deltas, sections)] per LOD) in morph export i: after its
        properties and HasGuid, strip flags, a u32 1, the LOD count, then per LOD a u32 1, the vertices
        it moves, how many deltas it had before rounding, its section indices, bGeneratedByEngine and a
        u32 0."""
        b = bytes(self.exports[i])
        n = len(self.lods)
        for p in range(len(b) - 8, 1, -1):
            if b[p:p + 2] != self.strip or struct.unpack_from("<Ii", b, p + 2) != (1, n):
                continue
            r, lods = _R(b, p + 10), []
            try:
                for _ in range(n):
                    if r.t("I") != 1:
                        raise FormatError("")
                    moved, before = r.t("II")
                    sections = r.arr("i")
                    r.t("II")
                    lods.append((moved, before, sections))
            except (FormatError, struct.error):
                continue
            if r.p == len(b) - 4 and b[-4:] == b"\0\0\0\0":
                return p, lods
        raise FormatError(f"morph target {self.export_names[i]} isn't laid out as expected")

    def _write_morph_lods(self, i, counts):
        p, _ = self._morph_lods(i)
        b = bytes(self.exports[i])
        out = b[:p + 10]
        for moved in counts:
            out += struct.pack("<III", 1, moved, moved) + (_arr("i", [0]) if moved else _arr("i", []))
            out += struct.pack("<II", 0, 0)
        self.exports[i] = bytearray(out + b"\0\0\0\0")

    # ------------------------------------------------------------------------------------- reading
    def geometry(self, lod=0):
        """LOD `lod` as plain lists: {"positions", "normals", "tangents" ((x, y, z, binormal sign)), "uvs"
        (channel 0), "triangles" (vertex index triples), "weights" ([(bone, weight 0..1), ...] a vertex),
        "morphs" ({name: {vertex: ((dx, dy, dz), (nx, ny, nz) or None)}})} in the mesh's own space
        (centimetres, Z up)."""
        L = self.lods[lod]
        n = L.vertex_count
        normals, tangents = [], []
        for i in range(n):
            tx, ty, tz, _, x, y, z, s = struct.unpack_from("<8b", L.tangents, 8 * i)
            normals.append((x / 127.0, y / 127.0, z / 127.0))
            tangents.append((tx / 127.0, ty / 127.0, tz / 127.0, 1.0 if s >= 0 else -1.0))
        weights = [None] * n
        k = L.influences
        for s in L.sections:
            for v in range(s.base_vertex, s.base_vertex + s.vertices):
                row = L.skin[2 * k * v:2 * k * (v + 1)]
                weights[v] = [(s.bone_map[row[j]], row[k + j] / 255.0) for j in range(k) if row[k + j]]
        tris = [tuple(L.indices[i:i + 3]) for i in range(0, len(L.indices) - 2, 3)]
        morphs = {}
        for name, elems in zip(self.morph_names, L.morphs):
            morphs[name] = {v: (tuple(c * L.pos_prec for c in d), tuple(c * L.tan_prec for c in t) if t else None)
                            for v, d, t in elems}
        return {"positions": list(L.positions), "normals": normals, "tangents": tangents,
                "uvs": [uv[:2] for uv in L.uvs], "triangles": tris, "weights": weights, "morphs": morphs}

    def bone_index(self, name):
        for i, (n, _) in enumerate(self.bones):
            if n == name:
                return i
        return None

    # ------------------------------------------------------------------------------------- writing
    def set_geometry(self, model):
        """Put a model in every LOD: model is {"positions", "normals", "tangents" ((x, y, z, sign) a vertex),
        "uvs", "triangles", "weights" ([(bone index, weight), ...] a vertex, weights summing to 1),
        "morphs" ({morph name: [(vertex, (dx, dy, dz), (nx, ny, nz) or None)]})}. The mesh keeps one
        section, with the first LOD section's material."""
        n = len(model["positions"])
        if not 3 <= n < 1 << 20:
            raise ValueError(f"a model of {n} vertices")
        used = sorted({b for w in model["weights"] for b, _ in w})
        if not used:
            raise ValueError("the model's vertices aren't tied to any bone")
        if len(used) > MAX_BONES_PER_SECTION:
            raise ValueError(f"the model uses {len(used)} bones; a section takes up to {MAX_BONES_PER_SECTION}")
        if any(b >= len(self.bones) for b in used):
            raise ValueError("a weight names a bone the skeleton hasn't got")
        active = set()
        for b in used:
            while b >= 0 and b not in active:
                active.add(b)
                b = self.bones[b][1]
        slot = {b: i for i, b in enumerate(used)}
        indices = [i for t in model["triangles"] for i in t]
        if any(not 0 <= i < n for i in indices):
            raise ValueError("a triangle names a vertex the model hasn't got")
        tangents = b"".join(_packed(t[:3]) + bytes([127]) + _packed(nrm) + _sign(t[3])
                            for t, nrm in zip(model["tangents"], model["normals"]))
        bounds = _bounds(model["positions"])
        bounds_raw = struct.pack("<7d", *bounds)
        for L in self.lods:
            k = L.influences
            skin = bytearray()
            for w in model["weights"]:
                top = sorted(w, key=lambda bw: -bw[1])[:k]
                q = _byte_weights([x for _, x in top])
                row_i = [slot[b] for b, _ in top] + [0] * (k - len(top))
                row_w = q + [0] * (k - len(top))
                skin += bytes(row_i) + bytes(row_w)
            L.skin = bytes(skin)
            L.index_size = 2 if n <= 0xFFFF else 4
            L.indices = indices
            L.positions = [tuple(p) for p in model["positions"]]
            L.tangents = tangents
            L.uvs = [tuple(uv) * L.uv_channels for uv in model["uvs"]]
            if L.has_colours:
                L.colours = b"\xff" * (4 * n)
            sec = L.sections[0]
            sec.base_index, sec.triangles, sec.base_vertex, sec.vertices = 0, len(indices) // 3, 0, n
            sec.bone_map = used
            sec.max_influences = max(1, min(k, max(len(w) for w in model["weights"])))
            L.sections = [sec]
            L.active = sorted(active)
            L.morphs, L.morph_min, L.morph_max = [], [], []
            for name in self.morph_names:
                elems = quantize_morph(model["morphs"].get(name, []), L.pos_prec, L.tan_prec)
                lo, hi = morph_extents(elems, L.pos_prec, L.tan_prec)
                L.morphs.append(elems)
                L.morph_min.append(lo)
                L.morph_max.append(hi)
        for i, name in zip(self.morph_order, self.morph_names):
            self._write_morph_lods(i, [len(L.morphs[self.morph_names.index(name)]) for L in self.lods])
        # The imported bounds, here and wherever the properties keep a copy of them.
        self.props = self.props.replace(self.bounds_raw, bounds_raw)
        self.bounds_raw, self.bounds = bounds_raw, bounds

    def rename(self, package_name, object_name):
        """Name it /Game/...: the package's and the mesh's names, and the export's public hash."""
        pkg = self.pkg
        em = pkg.summary[8] - pkg._after_names
        rest = bytearray(pkg._rest)
        name_index = struct.unpack_from("<I", rest, em + EXPORT_ENTRY * self.main + 16)[0]
        for i, new in ((name_index, object_name), (pkg.summary[2], package_name)):
            if not new.isascii():
                raise ValueError(f"{new!r}: mesh names must be ASCII")
            del pkg._index[pkg.names[i]]
            pkg.names[i] = new
            pkg._index[new] = i
            pkg.hashes[i] = name_hash(new)
        struct.pack_into("<Q", rest, em + EXPORT_ENTRY * self.main + 56, export_hash(object_name))
        pkg._rest = bytes(rest)
        self.export_names[self.main] = object_name

    def main_export(self):
        return (self.props + self.strip + self.bounds_raw + struct.pack("<i", len(self.materials))
                + b"".join(m for _, m in self.materials) + self.skeleton
                + struct.pack("<Ii", 1, len(self.lods)) + b"".join(L.bytes() for L in self.lods) + self.tail)

    def bytes(self):
        """The package."""
        parts = [bytes(e) for e in self.exports]
        parts[self.main] = self.main_export()
        return self.pkg.rebuild(b"".join(parts) + self.trailer, [len(p) for p in parts])


def _has_colours(ex, lod_at):
    """Whether the LODs have a vertex colour buffer (the mesh's bHasVertexColors): read the first LOD
    as far as its skin weights and look at what follows."""
    r = _R(ex, lod_at)
    r.raw(2)
    r.t("II")
    r.arr("H")
    for _ in range(r.t("i")):
        r.raw(2)
        r.t(Section.FIELDS)
        r.t("i")
        r.arr("H")
        r.t("Iih")
        r.raw(20)
        r.t("I")
    r.arr("H")
    r.t("I")
    r.raw(2)
    size = r.t("B")
    r.bulk(size)
    r.t("II")
    r.bulk(12)
    r.raw(2)
    r.t("IIII")
    r.bulk(8)
    r.bulk(4)
    r.raw(2)
    r.t("IIIIII")
    r.bulk(1)
    r.raw(14)
    head = ex[r.p:r.p + 10]
    return len(head) == 10 and struct.unpack_from("<I", head, 2)[0] == 4 and struct.unpack_from("<I", head, 6)[0] > 0


def _packed(v):
    return bytes((max(-127, min(127, int(round(c * 127.0)))) & 0xFF) for c in v)


def _sign(s):
    return bytes([127 if s >= 0 else 0x81])


def _byte_weights(ws):
    """Weights (summing to about 1) as bytes summing to exactly 255."""
    total = sum(ws) or 1.0
    q = [int(math.floor(w / total * 255 + 0.5)) for w in ws]
    order = sorted(range(len(ws)), key=lambda i: -ws[i])
    diff = 255 - sum(q)
    i = 0
    while diff and q:
        j = order[i % len(order)]
        step = 1 if diff > 0 else -1
        if 0 <= q[j] + step <= 255:
            q[j] += step
            diff -= step
        i += 1
    return q


def _bounds(points):
    lo = [min(p[c] for p in points) for c in range(3)]
    hi = [max(p[c] for p in points) for c in range(3)]
    origin = [(a + b) / 2 for a, b in zip(lo, hi)]
    extent = [(b - a) / 2 for a, b in zip(lo, hi)]
    radius = max(math.dist(origin, p) for p in points)
    return (*origin, *extent, radius)
