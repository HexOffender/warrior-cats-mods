"""The game's cooked animations (AnimSequence) and skeletons: read, decoded, and copied with new keys.

A mod's own animation becomes a copy of one of the game's sequences on the same skeleton, with new keys,
a new length and a new name, as textures (texture.py) and meshes (skelmesh.py) are copies: the copy keeps
the game's layout, its skeleton and compression settings, and changes only what the keys decide.

The package (UE 5.7, unversioned): the AnimSequence export, plus one export per notify object for the
sequences with notifies (footsteps). The sequence export is its properties (the class's own first: the
bone, curve and frame-stripping settings, then SequenceLength, the Skeleton, AssetUserData...), a u32
HasGuid, the SkeletonGuid, FStripDataFlags, a u32 bSerializeCompressedData, then the compressed data:
  * i32 CompressedRawDataSize (for statistics), the track table (i32 per track: its bone in the
    skeleton), the curve names (FNames), i32 byte count and a u32 "in bulk data" (0), the bone data,
    the bone codec's name in its settings (FString), the curve codec's path (FString), i32 count and
    the curve bytes;
  * then the bone codec's own fields. ACL (AnimBoneCompressionCodec_ACL_*): i32 keys and a u32 0; the
    bone data is an ACL stream (formats/acl.py). Unreal's (AnimCompress_*): i32 keys, u8 key encoding
    (2 = per track, 0 = constant key lerp), u8 translation, rotation and scale formats, then i32 sizes: the byte
    stream, the track offsets, the scale offsets and the scale offsets' stride. The bone data is the
    track offsets, the scale offsets, then the byte stream.

A per-track track, at its offset in the byte stream (-1: none, the identity): a u32 header (keys in bits
0-23, flags in 24-27, format in 28-31), then for format 3 a (min, range) pair of floats per component,
the keys, and with flag 8 a frame table (4-aligned, u8 frame numbers, u16 from 256 frames). Flags 1, 2,
4 say which of x, y, z are stored (none: all three; the rest are 0). Format 1 is a float per component,
format 2 a u16 ((v - 32767) / 32767 for rotations, (v - 255) for translations and scales: Unreal's
offset (1 << (15 - s)) - 1 and integer factor offset >> s, s = 0 or 7), format 3 a u32 per key, x in
bits 21-31, y in 10-20, z in 0-9, min + range * q / (2^bits - 1). Rotations keep x, y, z of a quaternion
whose w is positive. Keys without a frame table are spread evenly over the sequence; one key holds all
through. docs/reverse-engineering.md, "Animations", has the rest.

Keys are what tracks() gives and set_tracks() takes: per track, a list of (translation, rotation, scale)
per key: centimetres, a quaternion (x, y, z, w) and a factor, relative to the bone's parent, at RATE
keys a second.
"""
import math
import struct

from .cityhash import name_hash
from .cooked import NAME_HASH_VERSION, ZenPackage, _Reader, read_header
from .texture import export_hash, package_id

EXPORT_ENTRY = 72
RATE = 30                          # keys a second, unless a sequence says (most of the game's; the birds' 24)
PER_TRACK, CONSTANT_KEY = 2, 0     # Unreal's key encodings
FLOAT96, FIXED48, INTERVAL, IDENTITY = 1, 2, 3, 6
# What a copy's keys are written with: Unreal's per-track codec, from the engine's own settings (the
# codec only has to be found: the data says how it's laid out). A sequence copied from one of the
# game's in ACL is moved to these settings.
UE_SETTINGS = "/Engine/Animation/DefaultAnimBoneCompressionSettings"
UE_CODEC = "AnimCompress_PerTrackCompression_5"
# AnimSequence's properties wcmods reads, by their unversioned index, and the size of their values: the
# bone, curve and frame-stripping settings (object references), PlatformTargetFrameRate (a cooked
# FPerPlatformFrameRate: a u32 1, then numerator and denominator; 30 a second when left out) and
# SequenceLength (a float).
OBJECT_PROPERTIES = (0, 1, 2)
FRAME_RATE, SEQUENCE_LENGTH = 17, 20
MAX_KEYS = 1 << 16


class FormatError(ValueError):
    """The sequence isn't laid out as wcmods expects (a game update may have changed it)."""


def script_index(path):
    """The FPackageObjectIndex a package imports a script object by ("/Script/Engine.AnimSequence")."""
    from .cityhash import cityhash64
    h = cityhash64(path.lower().replace(".", "/").replace(":", "/").encode("utf-16-le"))
    return h & ~(3 << 62) | 1 << 62


SEQUENCE_CLASS = script_index("/Script/Engine.AnimSequence")


def is_sequence(data):
    """Whether a package holds an AnimSequence (not a montage, a composite or a pose asset); its notify objects
    may come first."""
    try:
        pkg = ZenPackage(data)
        return any(struct.unpack_from("<Q", pkg.data, pkg.summary[8] + EXPORT_ENTRY * i + 32)[0] == SEQUENCE_CLASS
                   for i in range(pkg.export_count))
    except (ValueError, struct.error):
        return False


class _R:
    def __init__(self, data, pos=0):
        self.d, self.p = data, pos

    def t(self, fmt):
        v = struct.unpack_from("<" + fmt, self.d, self.p)
        self.p += struct.calcsize("<" + fmt)
        return v if len(v) > 1 else v[0]

    def raw(self, n):
        if n < 0 or self.p + n > len(self.d):
            raise FormatError("the sequence ends early")
        b = self.d[self.p:self.p + n]
        self.p += n
        return bytes(b)

    def fstring(self):
        n = self.t("i")
        if not 0 < n < 4096:
            raise FormatError("a name is out of range")
        s = self.raw(n)
        if s[-1:] != b"\0":
            raise FormatError("a name isn't terminated")
        return s[:-1].decode("ascii")


def _fstring(s):
    b = s.encode("ascii") + b"\0"
    return struct.pack("<i", len(b)) + b


def _exports(pkg):
    """[(name, offset, size)] of a package's exports, which must lie end to end."""
    em = pkg.summary[8]
    out = []
    for i in range(pkg.export_count):
        off, size, ni, number = struct.unpack_from("<QQII", pkg.data, em + EXPORT_ENTRY * i)
        out.append((pkg.names[ni] + (f"_{number - 1}" if number else ""), off, size))
    if any(out[i][1] != sum(s for _, _, s in out[:i]) for i in range(len(out))):
        raise FormatError("the exports aren't laid out as expected")
    return out


def _package_name(pkg):
    """The package's name, with its FName number ("/Game/.../A_CatMaster_Walk" number 2: "..._Walk_1")."""
    number = pkg.summary[3]
    return pkg.names[pkg.summary[2]] + (f"_{number - 1}" if number else "")


def _main(pkg, exports):
    short = _package_name(pkg).rsplit("/", 1)[-1].lower()
    for i, (name, _, _) in enumerate(exports):
        if name.lower() == short:           # FNames match in any case
            return i
    raise FormatError(f"{_package_name(pkg)} has no export named {short}")


# ----------------------------------------------------------------------------------------------- skeleton
class Skeleton:
    """A cooked USkeleton's reference skeleton: bones [(name, parent index)] and their reference pose
    [(translation, rotation, scale)], each relative to its parent (cm; quaternion x, y, z, w)."""

    def __init__(self, data):
        pkg = ZenPackage(data)
        exports = _exports(pkg)
        _, off, size = exports[_main(pkg, exports)]
        ex = pkg.export_data[off:off + size]
        for p in range(0, len(ex) - 16):
            found = self._read_at(ex, p, pkg.names)
            if found:
                self.bones, self.poses = found
                break
        else:
            raise FormatError("couldn't find the skeleton's bones (the game may have updated)")
        self._index = {n.lower(): i for i, (n, _) in enumerate(self.bones)}

    @staticmethod
    def _read_at(ex, p, names):
        """The bones and poses if a reference skeleton starts at p: the bone count, each bone's FName and
        parent (the first without one, the others after theirs), the same count of poses (10 doubles)."""
        n = struct.unpack_from("<i", ex, p)[0]
        if not 0 < n < 1024 or p + 4 + 12 * n + 4 + 80 * n > len(ex):
            return None
        bones = []
        for k in range(n):
            ni, number, parent = struct.unpack_from("<IIi", ex, p + 4 + 12 * k)
            if ni >= len(names) or not -1 <= parent < k or (k == 0) != (parent == -1):
                return None
            bones.append((names[ni] + (f"_{number - 1}" if number else ""), parent))
        q = p + 4 + 12 * n
        if struct.unpack_from("<i", ex, q)[0] != n:
            return None
        poses = []
        for k in range(n):
            v = struct.unpack_from("<10d", ex, q + 4 + 80 * k)
            if not all(math.isfinite(x) for x in v):
                return None
            poses.append((v[4:7], v[0:4], v[7:10]))
        return bones, poses

    def index(self, name):
        """A bone's index by name (any case), or None."""
        return self._index.get(name.lower())


# ------------------------------------------------------------------------------------------------ decoding
def _comps(flags):
    m = flags & 7
    return [c for c in range(3) if m == 0 or m >> c & 1]


def _lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _nlerp(a, b, t):
    """Unreal's blend of two key rotations: the shorter way, lerped and normalised."""
    if sum(x * y for x, y in zip(a, b)) < 0:
        b = tuple(-x for x in b)
    q = _lerp(a, b, t)
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    return tuple(x / n for x in q)


def _spread(keys, frames, nframes, blend):
    """Keys at `frames` (or evenly over the sequence when None) as one value per frame."""
    n = len(keys)
    if n == 1:
        return [keys[0]] * nframes
    if frames is None:
        if n == nframes:
            return list(keys)
        out = []
        for f in range(nframes):
            pos = f / (nframes - 1) * (n - 1) if nframes > 1 else 0.0
            j = min(int(pos), n - 2)
            out.append(blend(keys[j], keys[j + 1], pos - j))
        return out
    out, j = [], 0
    for f in range(nframes):
        while j + 1 < n and frames[j + 1] <= f:
            j += 1
        if f <= frames[0]:
            out.append(keys[0])
        elif j + 1 >= n:
            out.append(keys[-1])
        else:
            out.append(blend(keys[j], keys[j + 1], (f - frames[j]) / (frames[j + 1] - frames[j])))
    return out


def _vec(fmt, flags, bs, p, kind, mins=None, ranges=None):
    """One key's x, y, z (a rotation's without w) at p, and where the next starts."""
    v = [0.0, 0.0, 0.0]
    cs = _comps(flags)
    if fmt == FLOAT96 or fmt == 0 and kind != "R":
        for c in (cs if fmt == FLOAT96 else range(3)):
            v[c] = struct.unpack_from("<f", bs, p)[0]
            p += 4
    elif fmt == FIXED48:
        for c in cs:
            u = struct.unpack_from("<H", bs, p)[0]
            p += 2
            v[c] = (u - 32767) / 32767.0 if kind == "R" else float(u - 255)
    elif fmt == INTERVAL:
        u = struct.unpack_from("<I", bs, p)[0]
        p += 4
        q = (u >> 21 & 0x7FF, u >> 10 & 0x7FF, u & 0x3FF)
        for c, bits in zip(range(3), (11, 11, 10)):
            if c in cs:
                v[c] = q[c] / ((1 << bits) - 1) * ranges[c] + mins[c]
    elif fmt == 0 and kind == "R":                # a whole quaternion
        x, y, z, w = struct.unpack_from("<4f", bs, p)
        return (x, y, z, w), p + 16
    else:
        raise FormatError(f"key format {fmt} isn't one wcmods reads")
    if kind == "R":
        x, y, z = v
        return (x, y, z, math.sqrt(max(0.0, 1.0 - x * x - y * y - z * z))), p
    return tuple(v), p


def _per_track(bs, off, kind, nframes):
    """A per-track track's value at every frame."""
    h = struct.unpack_from("<I", bs, off)[0]
    n, flags, fmt = h & 0xFFFFFF, h >> 24 & 0xF, h >> 28
    if not 0 < n <= nframes:
        raise FormatError(f"a track has {n} keys in {nframes} frames")
    p = off + 4
    mins, ranges = [0.0] * 3, [0.0] * 3
    if fmt == INTERVAL:
        for c in _comps(flags):
            mins[c], ranges[c] = struct.unpack_from("<2f", bs, p)
            p += 8
    keys = []
    for _ in range(n):
        k, p = _vec(fmt, flags, bs, p, kind, mins, ranges)
        keys.append(k)
    frames = None
    if flags & 8 and n > 1:
        p = (p + 3) & ~3
        frames = struct.unpack_from(f"<{n}{'B' if nframes < 256 else 'H'}", bs, p)
    return _spread(keys, frames, nframes, _nlerp if kind == "R" else _lerp)


def _constant_key(bs, off, n, fmt, kind, nframes):
    """A constant-key track (keys spread evenly; one key is a float vector, or for a rotation, float96)."""
    if off == -1 or n <= 0:
        return None
    if n == 1:
        fmt = FLOAT96 if kind == "R" else 0
    p = off
    mins, ranges = [0.0] * 3, [0.0] * 3
    if fmt == INTERVAL:
        for c in range(3):
            mins[c] = struct.unpack_from("<f", bs, p)[0]
            p += 4
        for c in range(3):
            ranges[c] = struct.unpack_from("<f", bs, p)[0]
            p += 4
    keys = []
    for _ in range(n):
        k, p = _vec(fmt, 7, bs, p, kind, mins, ranges)
        keys.append(k)
    return _spread(keys, None, nframes, _nlerp if kind == "R" else _lerp)


# ------------------------------------------------------------------------------------------------ writing
SAME = {"T": 1e-4, "R": 1e-6, "S": 1e-5}  # keys this close to the first are the same (cm, quaternion, factor)


def _float_track(kind, keys):
    """A per-track track in full floats (format 1, all three components): one key when they're all alike."""
    if kind == "R":
        fixed = []
        for q in keys:
            n = math.sqrt(sum(x * x for x in q)) or 1.0
            if q[3] < 0:
                n = -n
            fixed.append((q[0] / n, q[1] / n, q[2] / n))
        keys = fixed
    else:
        keys = [tuple(float(x) for x in k) for k in keys]
    first = keys[0]
    if all(max(abs(a - b) for a, b in zip(k, first)) < SAME[kind] for k in keys):
        keys = [first]
    return struct.pack("<I", len(keys) | 7 << 24 | FLOAT96 << 28) + b"".join(struct.pack("<3f", *k) for k in keys)


# --------------------------------------------------------------------------------------------- the sequence
class AnimSequence:
    """One of the game's cooked sequences, to read, or to copy with keys of a mod's own."""

    def __init__(self, data):
        self.pkg = pkg = ZenPackage(data)
        self._entries = _exports(pkg)
        self.main = _main(pkg, self._entries)
        self.exports = [bytes(pkg.export_data[o:o + s]) for _, o, s in self._entries]
        self.trailer = pkg.export_data[sum(s for _, _, s in self._entries):]
        ex = self.exports[self.main]
        for start in self._starts(ex):
            try:
                self._parse(ex, start)
            except (FormatError, struct.error, UnicodeDecodeError):
                continue
            if not self.tail:
                break
        else:
            raise FormatError("couldn't find where the sequence's data starts (the game may have updated)")
        self.length = None                 # a new SequenceLength, for set_tracks

    @staticmethod
    def _starts(ex):
        """Where the data after the properties may start: HasGuid 0, a 16-byte GUID, cooked strip flags,
        bSerializeCompressedData 1, the raw size, then a track table of bone indexes."""
        for p in range(8, len(ex) - 40):
            if ex[p:p + 4] != b"\0\0\0\0" or not ex[p + 20] & 1 or struct.unpack_from("<I", ex, p + 22)[0] != 1:
                continue
            n = struct.unpack_from("<i", ex, p + 30)[0]
            if 0 < n < 1024 and p + 34 + 4 * n <= len(ex) and all(
                    0 <= i < 1024 for i in struct.unpack_from(f"<{n}i", ex, p + 34)):
                yield p

    def _parse(self, ex, start):
        self.props = ex[:start]
        r = _R(ex, start)
        self.head = r.raw(26)              # HasGuid, SkeletonGuid, strip flags, bSerializeCompressedData
        self.raw_size = r.t("i")
        n = r.t("i")
        self.track_map = list(struct.unpack_from(f"<{n}i", ex, r.p))
        r.p += 4 * n
        n = r.t("i")
        if not 0 <= n < 4096:
            raise FormatError("curve count out of range")
        self.curve_names = [r.t("II") for _ in range(n)]
        nbytes = r.t("i")
        self.bulk = r.t("I")
        self.blob = r.raw(nbytes)
        self.handle = r.fstring()
        self.curve_codec = r.fstring()
        self.curve_blob = r.raw(r.t("i"))
        self.nkeys = r.t("i")
        if "_ACL" in self.handle:
            self.codec = "acl"
            self.acl_tail = r.t("I")
        else:
            self.encoding, *self.formats = r.t("4B")
            self.nbs, self.nto, self.nso, self.stride = r.t("4i")
            if 4 * (self.nto + self.nso) + self.nbs != nbytes:
                raise FormatError("the bone data's parts don't add up")
            self.codec = {PER_TRACK: "per-track", CONSTANT_KEY: "constant"}.get(self.encoding, f"encoding {self.encoding}")
        self.tail = ex[r.p:]

    # ------------------------------------------------------------------------------------------ reading
    @property
    def curves(self):
        """The curves' names, in the sequence's order."""
        return [self.pkg.names[i] for i, _ in self.curve_names]

    def sequence_length(self):
        """SequenceLength, the seconds the sequence plays (from its properties)."""
        return struct.unpack_from("<f", self.props, self._value_at(SEQUENCE_LENGTH))[0]

    def frame_rate(self):
        """Keys a second: PlatformTargetFrameRate, or RATE when the sequence leaves it out."""
        try:
            at = self._value_at(FRAME_RATE)
        except LookupError:
            return float(RATE)
        cooked, num, den = struct.unpack_from("<Iii", self.props, at)
        if cooked != 1 or num <= 0 or den <= 0:
            raise FormatError("the sequence's frame rate isn't laid out as expected")
        return num / den

    def _value_at(self, index):
        """Where a property's value is in the properties (LookupError when it's left out). Only the
        properties wcmods knows may come before SequenceLength, as in the game's plain sequences."""
        r = _Reader(self.props)
        present, zero = read_header(r)
        if SEQUENCE_LENGTH not in present or zero:
            raise FormatError("the sequence's properties aren't laid out as expected")
        at = r.pos
        for i in present:
            if i == index:
                return at
            if i in OBJECT_PROPERTIES:
                at += 4
            elif i == FRAME_RATE:
                at += 12
            else:
                break
        if index in present:
            raise FormatError("the sequence has properties wcmods doesn't know before its length")
        raise LookupError(index)

    def tracks(self, bind=None):
        """Every track's keys: [(translations, rotations, scales)], each a list of one value per key. An ACL
        stream leaves what didn't move from the bind pose out: `bind` gives that, a (translation, rotation,
        scale) a track, the skeleton's reference pose for the track's bone (bind_pose)."""
        if self.codec == "acl":
            from . import acl
            out = acl.decode(self.blob, bind)
            if len(out) != len(self.track_map) or any(len(t) != self.nkeys for track in out for t in track):
                raise FormatError("the ACL stream's tracks or keys aren't the sequence's")
            return out
        n = self.nkeys
        if not 0 < n <= MAX_KEYS:
            raise FormatError(f"{n} keys")
        stride = 4 if self.codec == "constant" else 2
        offsets = struct.unpack_from(f"<{self.nto}i", self.blob, 0)
        scales = struct.unpack_from(f"<{self.nso}i", self.blob, 4 * self.nto)
        bs = self.blob[4 * (self.nto + self.nso):]
        none_t, none_r, none_s = [(0.0, 0.0, 0.0)] * n, [(0.0, 0.0, 0.0, 1.0)] * n, [(1.0, 1.0, 1.0)] * n
        out = []
        for t in range(len(self.track_map)):
            if self.codec == "per-track":
                ot, orot = offsets[2 * t], offsets[2 * t + 1]
                osc = scales[t] if self.nso else -1
                T = none_t if ot == -1 else _per_track(bs, ot, "T", n)
                Q = none_r if orot == -1 else _per_track(bs, orot, "R", n)
                S = none_s if osc == -1 else _per_track(bs, osc, "S", n)
            elif self.codec == "constant":
                ft, fr, fs = self.formats
                ot, nt, orot, nr = offsets[stride * t:stride * t + 4]
                T = _constant_key(bs, ot, nt, ft, "T", n) or none_t
                Q = _constant_key(bs, orot, nr, fr, "R", n) or none_r
                S = none_s
                if self.nso:
                    osc, ns = scales[self.stride * t:self.stride * t + 2]
                    S = _constant_key(bs, osc, ns, fs, "S", n) or none_s
            else:
                raise FormatError(f"key {self.codec} isn't one wcmods reads")
            out.append((T, Q, S))
        return out

    def bind_pose(self, skeleton):
        """The skeleton's (formats/anim.Skeleton) reference pose for each of the sequence's tracks, for tracks()."""
        if any(not 0 <= b < len(skeleton.poses) for b in self.track_map):
            raise FormatError("the sequence's tracks aren't all bones of that skeleton")
        return [skeleton.poses[b] for b in self.track_map]

    def skeleton_name(self):
        """The package of the skeleton the sequence is on ("/Game/Art/Characters/.../SK_Mice_Skeleton"), from the
        package names it imports."""
        found = [n for n in self._package_names() if n.lower().endswith("skeleton")]
        if len(found) != 1:
            raise FormatError("couldn't tell which skeleton the sequence is on")
        return found[0]

    def constant_curves(self):
        """{curve name: value} for the curves that hold one value all through (all of them in the copies)."""
        out = {}
        if "_ACL" in self.curve_codec:          # ACL's curves aren't read
            return out
        for k, (i, _) in enumerate(self.curve_names):
            if 12 * k + 12 <= len(self.curve_blob):
                fmt, _, _, _, value, _ = struct.unpack_from("<4BfI", self.curve_blob, 12 * k)
                if fmt == 1:
                    out[self.pkg.names[i]] = value
        return out

    # ------------------------------------------------------------------------------------------ writing
    def set_tracks(self, tracks, length=None, bones=None, keep_length=False):
        """New keys (as tracks() gives them, every list as long), written with Unreal's per-track codec in
        full floats, and `length` seconds (by default the keys at the sequence's frame rate). A track per
        entry of the track table, or of `bones` (skeleton bone indexes), which becomes the track table;
        bones without a track hold their reference pose. With `keep_length`, as many keys as the sequence
        has, and its own length stays: the one way to put new keys in a sequence whose properties wcmods
        can't get through to SequenceLength (the game's with notifies, its footsteps among them)."""
        if "_ACL" in self.handle:
            raise ValueError("an ACL sequence takes Unreal's keys only once use_unreal_codec() moved it to its settings")
        if bones is not None:
            if len(set(bones)) != len(bones) or not all(isinstance(b, int) and 0 <= b < 1024 for b in bones):
                raise ValueError("the bones should be distinct skeleton bone indexes")
            self.track_map = list(bones)
        if len(tracks) != len(self.track_map):
            raise ValueError(f"{len(tracks)} tracks for a track table of {len(self.track_map)}")
        n = len(tracks[0][0])
        if not 1 < n <= MAX_KEYS or any(len(part) != n for track in tracks for part in track):
            raise ValueError("every track needs the same number of keys, at least two")
        if keep_length:
            if n != self.nkeys:
                raise ValueError(f"{n} keys for a sequence of {self.nkeys}: keeping its length takes as many")
        else:
            self._value_at(SEQUENCE_LENGTH)   # the copy's length can be written
        offsets, scales, stream = [], [], bytearray()
        for T, Q, S in tracks:            # as the game writes them: scale, translation, rotation
            scales.append(len(stream))
            stream += _float_track("S", S)
            offsets.append(len(stream))
            stream += _float_track("T", T)
            offsets.append(len(stream))
            stream += _float_track("R", Q)
        self.blob = struct.pack(f"<{len(offsets)}i", *offsets) + struct.pack(f"<{len(scales)}i", *scales) + bytes(stream)
        self.nkeys, self.nbs, self.nto, self.nso, self.stride = n, len(stream), len(offsets), len(scales), 1
        self.codec, self.encoding, self.formats = "per-track", PER_TRACK, [IDENTITY, IDENTITY, IDENTITY]
        self.raw_size = len(tracks) * (48 + 40 * n)     # Unreal's estimate of the raw keys, for statistics
        if not keep_length:
            self.length = float(length) if length is not None else (n - 1) / self.frame_rate()

    def clear_curves(self):
        """No curves (the morphs keep what the AnimBlueprint gives them)."""
        self.curve_names, self.curve_blob = [], b""

    def set_constant_curves(self, values):
        """Hold the named curves at these values (only curves the sequence has; the others stay)."""
        if "_ACL" in self.curve_codec:
            raise ValueError("the sequence's curves are compressed with ACL")
        known = set(self.curves)
        unknown = sorted(set(values) - known)
        if unknown:
            raise ValueError(f"the sequence has no curve {', '.join(unknown)}")
        rows = []
        for k, name in enumerate(self.curves):
            fmt, ktf, pre, post, value, _ = struct.unpack_from("<4BfI", self.curve_blob, 12 * k)
            if name in values:
                fmt, value = 1, float(values[name])
            elif fmt != 1:
                raise ValueError(f"the curve {name} isn't constant")
            rows.append(struct.pack("<4Bf", fmt, ktf, pre, post, value))
        size = 12 * len(rows)
        self.curve_blob = b"".join(r + struct.pack("<I", size) for r in rows)

    def use_unreal_codec(self, imports):
        """For a copy of one of the game's ACL sequences: import the engine's own bone compression settings
        in place of ACL's, so Unreal's keys can go in. `imports` is the template's container header
        imports (package IDs); returns them as the copy needs them."""
        if self.codec != "acl":
            return list(imports)
        pkg = self.pkg
        s = pkg.summary
        names = self._package_names()
        if len(names) != len(imports):
            raise FormatError("the package's imports and the container's disagree")
        acl = [i for i, n in enumerate(names) if n.startswith("/ACLPlugin/") and n.endswith("BoneCompressionSettings")]
        if len(acl) != 1:
            raise FormatError("couldn't find the ACL settings the sequence imports")
        index = acl[0]
        rest = bytearray(pkg._rest)
        base = pkg._after_names
        hashes_at, imports_at = s[6] - base, s[7] - base
        n_hashes = (s[7] - s[6]) // 8
        n_imports = (s[8] - s[7]) // 8
        changed = 0
        for k in range(n_imports):
            (v,) = struct.unpack_from("<Q", rest, imports_at + 8 * k)
            if v >> 62 == 2 and (v >> 32 & 0x3FFFFFFF) == index:
                h = v & 0xFFFFFFFF
                if h >= n_hashes:
                    raise FormatError("an import's hash is out of range")
                struct.pack_into("<Q", rest, hashes_at + 8 * h, export_hash(UE_SETTINGS.rsplit("/", 1)[-1]))
                changed += 1
        if changed != 1:
            raise FormatError("the ACL settings aren't imported once")
        names[index] = UE_SETTINGS
        rest = rest[:s[12] - base] + _name_section(names)
        s[1] = base + len(rest)                          # the header ends where the names now end
        pkg._rest = bytes(rest)
        self.handle = UE_CODEC
        out = list(imports)
        out[index] = package_id(UE_SETTINGS)
        return out

    def _package_names(self):
        """The package names the package imports (its ImportedPackageNames, in the container's order)."""
        s = self.pkg.summary
        if s[12] != max(s[6:15]) or s[12] > s[1]:
            raise FormatError("the imported package names aren't where wcmods expects")
        raw = self.pkg.data[s[12]:s[1]]
        count = struct.unpack_from("<I", raw, 0)[0]
        if count == 0:
            return []
        p = 16 + 8 * count
        lengths = struct.unpack_from(f">{count}H", raw, p)
        p += 2 * count
        names = []
        for n in lengths:
            names.append(raw[p:p + n].decode("ascii"))
            p += n
        numbers = struct.unpack_from(f"<{count}i", raw, p)
        return [n + (f"_{k - 1}" if k else "") for n, k in zip(names, numbers)]

    def rename(self, package_name, object_name):
        """Name it /Game/...: the package's and the sequence's names, and the export's public hash."""
        pkg = self.pkg
        em = pkg.summary[8] - pkg._after_names
        rest = bytearray(pkg._rest)
        name_index = struct.unpack_from("<I", rest, em + EXPORT_ENTRY * self.main + 16)[0]
        for i, new in ((name_index, object_name), (pkg.summary[2], package_name)):
            if not new.isascii():
                raise ValueError(f"{new!r}: animation names must be ASCII")
            del pkg._index[pkg.names[i]]
            pkg.names[i] = new
            pkg._index[new] = i
            pkg.hashes[i] = name_hash(new)
        struct.pack_into("<I", rest, em + EXPORT_ENTRY * self.main + 20, 0)    # no FName numbers: the names as given
        pkg.summary[3] = 0
        struct.pack_into("<Q", rest, em + EXPORT_ENTRY * self.main + 56, export_hash(object_name))
        pkg._rest = bytes(rest)

    def main_export(self):
        props = self.props
        if self.length is not None:
            at = self._value_at(SEQUENCE_LENGTH)
            props = props[:at] + struct.pack("<f", self.length) + props[at + 4:]
        out = (props + self.head + struct.pack("<i", self.raw_size)
               + struct.pack(f"<i{len(self.track_map)}i", len(self.track_map), *self.track_map)
               + struct.pack("<i", len(self.curve_names)) + b"".join(struct.pack("<II", *c) for c in self.curve_names)
               + struct.pack("<iI", len(self.blob), self.bulk) + self.blob
               + _fstring(self.handle) + _fstring(self.curve_codec)
               + struct.pack("<i", len(self.curve_blob)) + self.curve_blob)
        if self.codec == "acl":
            out += struct.pack("<iI", self.nkeys, self.acl_tail)
        else:
            out += struct.pack("<i4B4i", self.nkeys, self.encoding, *self.formats, self.nbs, self.nto, self.nso, self.stride)
        return out + self.tail

    def bytes(self):
        """The package."""
        parts = list(self.exports)
        parts[self.main] = self.main_export()
        return self.pkg.rebuild(b"".join(parts) + self.trailer, [len(p) for p in parts])


def _name_section(names):
    """An ImportedPackageNames section: a name batch (count, string bytes, hash version, the names' hashes,
    big-endian lengths, the strings), then each name's i32 number."""
    if not names:
        return struct.pack("<I", 0)
    split = [_split_number(n) for n in names]
    strings = b"".join(n.encode("ascii") for n, _ in split)
    return (struct.pack("<IIQ", len(names), len(strings), NAME_HASH_VERSION)
            + struct.pack(f"<{len(names)}Q", *(name_hash(n) for n, _ in split))
            + struct.pack(f">{len(names)}H", *(len(n) for n, _ in split)) + strings
            + struct.pack(f"<{len(names)}i", *(k for _, k in split)))


def _split_number(name):
    """An FName's text and number as Unreal splits them: "A_2" is ("A", 3); "A_02" and "A" are themselves, 0."""
    base, _, digits = name.rpartition("_")
    if base and digits.isascii() and digits.isdigit() and (digits == "0" or digits[0] != "0") \
            and int(digits) < 2 ** 31 - 1:
        return base, int(digits) + 1
    return name, 0
