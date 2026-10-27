"""ACL (the Animation Compression Library, github.com/nfrechette/acl, MIT) streams as the game's sequences keep
them: a pure-Python decoder for ACL 2.1's uniformly sampled transform tracks, the only kind the game has.

Most of the game's sequences (519 of 757) are compressed with Unreal's ACL plugin. Decoding them lets wcmods
read every one of the game's animations (AnimSequence.tracks, formats/anim.py): the start kits carry them as
examples, and the selftest decodes them all. Only reading: a mod's own sequences are written with Unreal's
per-track codec. The layout follows ACL 2.1.0's sources (core/impl/compressed_headers.h,
compression/impl/write_*.h, decompression/impl/*); docs/reverse-engineering.md, "ACL streams", has it in
prose, with what was checked in game.

A stream (offsets from its start; little-endian):
  * raw_buffer_header: u32 size, u32 hash; tracks_header (24): u32 tag 0xAC11AC11, u16 version (10 = 2.1.0),
    u8 algorithm (0, uniformly sampled), u8 track type (12, qvvf), u32 tracks, u32 samples, f32 sample rate,
    u32 packed flags: bit 0 has scale, bit 1 the default scale (0 for an additive sequence, or 1), bit 2
    scale format, bit 3 translation format (1 = variable), bits 4-7 rotation format (3 = drop w, variable),
    bit 8 database, bit 9 trivial defaults (the identity was what the compressor left out), bit 10 stripped
    keyframes, bit 30 wrap-optimized (the repeated last sample is left out);
  * transform_tracks_header (52, at 32): segments, animated sub tracks (all, rotations, translations, scales),
    constant samples (rotations, translations, scales), then offsets from this header: database, segment
    headers, sub track types, constant data, clip range data. With several segments, their first samples
    (u32 each, then 0xFFFFFFFF) follow it;
  * sub track types: 2 bits a track from the most significant, 16 to a u32 (0 default, 1 constant, 2 animated),
    rotations' words, then translations', then scales';
  * constant data: rotations (drop-w formats as x of up to 4, then their y, then z), translations, scales
    (3 floats each);
  * clip range data, for the animated sub tracks in groups of up to 4 of one kind: a rotation group's minimums'
    x, y, z and extents' x, y, z (floats, n of each); a translation's or scale's min xyz and extent xyz;
  * per segment a header (16 bytes; 20 with stripped keyframes, the last a mask of the samples kept, sample k
    at bit 31 - k): bits a sample takes (all, rotations, translations) and the offset of its data: a byte
    per animated sub track (bits per component: 0 = constant in the segment, 31 = raw floats; rotations padded
    to a multiple of 4), with several segments the segment ranges (2-aligned: rotation groups of 4 as min x[4],
    y[4], z[4], extent x[4], y[4], z[4] in bytes, or a constant sample's 16 bits split high/low; 6 bytes a
    translation or scale), then (4-aligned) the samples: big-endian bit fields, a sample's rotations, then
    translations, then scales.
A value is clip_min + clip_extent * (segment_min + segment_extent * q / (2^bits - 1)), segment values in 255ths;
a sub track constant in its segment is clip_min + clip_extent * its 16-bit sample / 65535, and a raw one its
floats as they are. A rotation's w is sqrt(|1 - x^2 - y^2 - z^2|), and the quaternion normalized (as ACL's
interpolation leaves it).

What a stream leaves at its default is what Unreal's ACL plugin gives it: for a sequence that isn't additive
(default scale 1), a rotation's and translation's are the bone's bind pose, the skeleton's reference pose;
for an additive one, the identity. A scale's is the default scale, whatever the bind pose's (the prop
A_GPE_TiedBranch_Falling's root rests at scale 100 and plays at 1).
"""
import math
import struct

TAG, VERSION = 0xAC11AC11, 10
UNIFORM, QVVF = 0, 12
QUAT_FULL, QUAT_DROP_W_FULL, QUAT_DROP_W_VARIABLE = 0, 2, 3
VECTOR_VARIABLE = 1
RAW = 31                       # a sub track's bits per component when it keeps raw floats (2.1)
HEADER = 32                    # where the transform tracks header starts


class FormatError(ValueError):
    """The stream isn't one wcmods decodes (another ACL version or kind of track)."""


def _float(u):
    return struct.unpack("<f", struct.pack("<I", u))[0]


def _quat(x, y, z):
    # A quantized x, y, z can come out a little over a length of 1 near a half turn: ACL takes the absolute
    # value there (quat_from_positive_w), so w isn't 0, and normalizes when it interpolates.
    w = math.sqrt(abs(1.0 - x * x - y * y - z * z))
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    return (x / n, y / n, z / n, w / n)


def _lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def _nlerp(a, b, u):
    if sum(x * y for x, y in zip(a, b)) < 0:
        b = tuple(-x for x in b)
    q = _lerp(a, b, u)
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    return tuple(x / n for x in q)


class _Bits:
    """A big-endian bit stream."""

    def __init__(self, data, start):
        self.d, self.start = data, start

    def take(self, bit, n):
        at = self.start + bit // 8
        chunk = int.from_bytes(self.d[at:at + 8].ljust(8, b"\0"), "big")
        return chunk >> (64 - bit % 8 - n) & ((1 << n) - 1)


def info(blob):
    """The stream's header: {"tracks", "samples", "keys" (with a wrap-optimized one's last), "rate", "trivial",
    "has_scale", ...}."""
    if len(blob) < HEADER + 52:
        raise FormatError("an ACL stream is longer than that")
    size, _, tag, version, algorithm, kind, tracks, samples, rate, flags = struct.unpack_from("<IIIHBBIIfI", blob, 0)
    if tag != TAG or size != len(blob):
        raise FormatError("not an ACL stream")
    if version != VERSION or algorithm != UNIFORM or kind != QVVF:
        raise FormatError(f"an ACL stream of version {version}, algorithm {algorithm}, tracks of type {kind}: "
                          "wcmods decodes ACL 2.1's uniformly sampled transforms")
    out = {"tracks": tracks, "samples": samples, "rate": rate, "has_scale": bool(flags & 1),
           "default_scale": float(flags >> 1 & 1), "scale_format": flags >> 2 & 1, "translation_format": flags >> 3 & 1,
           "rotation_format": flags >> 4 & 15, "database": bool(flags >> 8 & 1), "trivial": bool(flags >> 9 & 1),
           "stripped": bool(flags >> 10 & 1), "wrap": bool(flags >> 30 & 1)}
    out["keys"] = samples + (1 if out["wrap"] else 0)
    if out["database"]:
        raise FormatError("an ACL stream with its keys in a database")
    return out


def decode(blob, bind=None):
    """Every track's keys, as formats/anim.py's tracks() gives them: [(translations, rotations, scales)], one value
    a key. `bind` is the bind pose for each track [(translation, rotation, scale)], which a rotation or
    translation the stream leaves at its default takes (needed unless the sequence is additive, or its
    defaults the identity)."""
    try:
        return _decode(blob, bind)
    except (struct.error, IndexError, KeyError) as e:
        raise FormatError(f"the ACL stream isn't laid out as wcmods expects ({type(e).__name__}: {e})") from None


def _decode(blob, bind):
    head = info(blob)
    ntracks, nsamples = head["tracks"], head["samples"]
    additive = head["default_scale"] == 0.0
    if bind is None and not head["trivial"] and not additive:
        raise FormatError("the stream leaves sub tracks at the bind pose, which isn't given")
    if bind is not None and len(bind) != ntracks:
        raise FormatError(f"{len(bind)} bind poses for {ntracks} tracks")
    rot_format = head["rotation_format"]
    if rot_format not in (QUAT_FULL, QUAT_DROP_W_FULL, QUAT_DROP_W_VARIABLE):
        raise FormatError(f"rotation format {rot_format}")
    H = HEADER
    (nseg, n_variable, n_rot, n_trans, n_scale, c_rot, c_trans, c_scale,
     _, seg_off, types_off, const_off, range_off) = struct.unpack_from("<13I", blob, H)
    if not 0 < nseg <= nsamples + 1:
        raise FormatError(f"{nseg} segments")
    starts = [0]
    if nseg > 1:
        starts = list(struct.unpack_from(f"<{nseg}I", blob, H + 52))
    ends = starts[1:] + [nsamples]
    has_scale = head["has_scale"]
    nent = (ntracks + 15) // 16
    words = struct.unpack_from(f"<{(3 if has_scale else 2) * nent}I", blob, H + types_off)

    def kinds(part):
        if part == 2 and not has_scale:
            return [0] * ntracks
        return [words[part * nent + t // 16] >> (30 - 2 * (t % 16)) & 3 for t in range(ntracks)]
    rk, tk, sk = kinds(0), kinds(1), kinds(2)
    animated = [[t for t in range(ntracks) if k[t] == 2] for k in (rk, tk, sk)]
    constant = [[t for t in range(ntracks) if k[t] == 1] for k in (rk, tk, sk)]
    if [len(a) for a in animated] != [n_rot, n_trans, n_scale] or [len(c) for c in constant] != [c_rot, c_trans, c_scale]:
        raise FormatError("the stream's sub track counts don't add up")
    # Defaults (the bind pose's rotation and translation, unless additive; the default scale), then the
    # constant sub tracks.
    use_bind = bind is not None and not additive
    fixed_t = [tuple(bind[t][0]) if use_bind else (0.0, 0.0, 0.0) for t in range(ntracks)]
    fixed_r = [tuple(bind[t][1]) if use_bind else (0.0, 0.0, 0.0, 1.0) for t in range(ntracks)]
    fixed_s = [(head["default_scale"],) * 3] * ntracks
    p = H + const_off
    if rot_format == QUAT_FULL:
        for t in constant[0]:
            fixed_r[t] = struct.unpack_from("<4f", blob, p)
            p += 16
    else:
        for g in range(0, len(constant[0]), 4):
            group = constant[0][g:g + 4]
            n = len(group)
            v = struct.unpack_from(f"<{3 * n}f", blob, p)
            p += 12 * n
            for k, t in enumerate(group):
                fixed_r[t] = _quat(v[k], v[n + k], v[2 * n + k])
    for out, tracks in ((fixed_t, constant[1]), (fixed_s, constant[2])):
        for t in tracks:
            out[t] = struct.unpack_from("<3f", blob, p)
            p += 12
    # The clip's ranges for the animated sub tracks of a variable format.
    rot_var = rot_format == QUAT_DROP_W_VARIABLE
    vec_var = (head["translation_format"] == VECTOR_VARIABLE, head["scale_format"] == VECTOR_VARIABLE)
    clip = [{}, {}, {}]
    p = H + range_off
    if rot_var:
        for g in range(0, len(animated[0]), 4):
            group = animated[0][g:g + 4]
            n = len(group)
            v = struct.unpack_from(f"<{6 * n}f", blob, p)
            p += 24 * n
            for k, t in enumerate(group):
                clip[0][t] = ((v[k], v[n + k], v[2 * n + k]), (v[3 * n + k], v[4 * n + k], v[5 * n + k]))
    for part in (1, 2):
        if vec_var[part - 1]:
            for t in animated[part]:
                v = struct.unpack_from("<6f", blob, p)
                p += 24
                clip[part][t] = (v[:3], v[3:])
    # The segments' samples.
    keys = [{t: [] for t in tracks} for tracks in animated]
    seg_header = 20 if head["stripped"] else 16
    multi = nseg > 1
    for si in range(nseg):
        at = H + seg_off + seg_header * si
        pose_bits, rot_bits, trans_bits, data = struct.unpack_from("<4I", blob, at)
        count = ends[si] - starts[si]
        stored = list(range(count))
        if head["stripped"]:
            mask = struct.unpack_from("<I", blob, at + 16)[0]
            stored = [k for k in range(count) if mask >> (31 - k) & 1]
        seg = H + data
        formats = blob[seg:seg + n_variable]
        q = seg + n_variable
        q += q & 1
        ranges = q
        q = (q + (6 * n_variable if multi else 0) + 3) & ~3
        bits = _Bits(blob, q)
        # Each animated sub track's bits per component, and its segment range.
        width, seg_range = [{}, {}, {}], [{}, {}, {}]
        fi = 0
        if rot_var:
            for t in animated[0]:
                width[0][t] = formats[fi]
                fi += 1
            fi = (len(animated[0]) + 3) // 4 * 4
        for part in (1, 2):
            if vec_var[part - 1]:
                for t in animated[part]:
                    width[part][t] = formats[fi]
                    fi += 1
        r = ranges
        if multi:
            if rot_var:
                for g in range(0, len(animated[0]), 4):
                    block = blob[r:r + 24]
                    r += 24
                    for k, t in enumerate(animated[0][g:g + 4]):
                        seg_range[0][t] = tuple(block[k + 4 * j] for j in range(6))
            for part in (1, 2):
                if vec_var[part - 1]:
                    for t in animated[part]:
                        seg_range[part][t] = blob[r:r + 6]
                        r += 6

        def size(part, t):
            if part == 0 and not rot_var:
                return 128 if rot_format == QUAT_FULL else 96
            if part > 0 and not vec_var[part - 1]:
                return 96
            n = width[part][t]
            return 96 if n == RAW else 3 * n
        sizes = [sum(size(part, t) for t in animated[part]) for part in range(3)]
        if (sizes[0], sizes[1], sum(sizes)) != (rot_bits, trans_bits, pose_bits):
            raise FormatError("a segment's sample size doesn't add up")
        got = [{t: [] for t in tracks} for tracks in animated]
        for index in range(len(stored)):
            b = index * pose_bits
            for part in range(3):
                for t in animated[part]:
                    value, b = _sample(part, t, b, bits, width, seg_range, clip, rot_format, rot_var, vec_var, multi)
                    got[part][t].append(value)
        for part in range(3):
            blend = _nlerp if part == 0 else _lerp
            for t in animated[part]:
                keys[part][t].extend(_fill(got[part][t], stored, count, blend))
    out = []
    for t in range(ntracks):
        parts = []
        for part, fixed in enumerate((fixed_r, fixed_t, fixed_s)):
            seq = keys[part][t] if t in keys[part] else [tuple(fixed[t])] * nsamples
            parts.append(seq + seq[:1] if head["wrap"] else seq)
        out.append((parts[1], parts[0], parts[2]))
    return out


def _sample(part, t, b, bits, width, seg_range, clip, rot_format, rot_var, vec_var, multi):
    """One animated sub track's value at bit b, and where the next starts."""
    variable = rot_var if part == 0 else vec_var[part - 1]
    if not variable:
        n = 4 if part == 0 and rot_format == QUAT_FULL else 3
        v = tuple(_float(bits.take(b + 32 * c, 32)) for c in range(n))
        return (v if n == 4 else _quat(*v)) if part == 0 else v, b + 32 * n
    n = width[part][t]
    lo, ext = clip[part][t]
    if n == 0:                                  # constant in this segment: its 16-bit sample is in the range data
        r = seg_range[part][t]
        if part == 0:
            v = [(r[2 * c] << 8 | r[2 * c + 1]) / 65535.0 for c in range(3)]
        else:
            v = [x / 65535.0 for x in struct.unpack("<3H", bytes(r))]
        v = [lo[c] + ext[c] * v[c] for c in range(3)]
    elif n == RAW:
        v = [_float(bits.take(b + 32 * c, 32)) for c in range(3)]
        b += 96
    else:
        m = (1 << n) - 1
        v = [bits.take(b + n * c, n) / m for c in range(3)]
        b += 3 * n
        if multi:
            r = seg_range[part][t]
            v = [r[c] / 255.0 + r[3 + c] / 255.0 * v[c] for c in range(3)]
        v = [lo[c] + ext[c] * v[c] for c in range(3)]
    return (_quat(*v) if part == 0 else tuple(v)), b


def _fill(values, stored, count, blend):
    """A segment's samples from the ones kept (stripped keyframes lie between them)."""
    if len(stored) == count:
        return values
    out = []
    for k in range(count):
        if k in stored:
            out.append(values[stored.index(k)])
            continue
        before = [j for j in stored if j < k]
        after = [j for j in stored if j > k]
        if not before or not after:
            out.append(values[stored.index(before[-1] if before else after[0])])
        else:
            lo, hi = before[-1], after[0]
            out.append(blend(values[stored.index(lo)], values[stored.index(hi)], (k - lo) / (hi - lo)))
    return out
