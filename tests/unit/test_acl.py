"""ACL 2.1 streams (formats/acl.py), without the game: a stream built by hand from the layout the decoder reads,
in two segments of three samples, with an animated rotation at 8 bits, a raw translation, a constant translation,
a rotation constant in one segment, scales at the default and the bind pose for a default sub track; with a
sample stripped between two kept ones, and as an additive sequence; and a sequence's ACL tracks
(formats/anim.py). The layout follows ACL 2.1.0's sources, so these guard the decoder against itself; the game's
own 519 ACL sequences are checked by `python wcmods.py selftest`, and some against the game's own poses
(docs/verified.md)."""
import math
import struct

import pytest

from wcmods.formats import acl, anim


class BitWriter:
    def __init__(self):
        self.bits = []

    def put(self, value, n):
        self.bits += [(value >> (n - 1 - i)) & 1 for i in range(n)]

    def float(self, f):
        self.put(struct.unpack("<I", struct.pack("<f", f))[0], 32)

    def bytes(self):
        bits = self.bits + [0] * (-len(self.bits) % 8)
        return bytes(sum(b << (7 - i) for i, b in enumerate(bits[k:k + 8])) for k in range(0, len(bits), 8))


SEGMENT = 3          # samples a segment


def build(stripped=False, additive=False):
    """Two tracks, six samples in two segments of three (wrap-optimized: the game's key count is seven).
    Track 0: rotation animated at 8 bits in segment 0 (y 0, 1/2, 1 of its range) and constant in segment 1,
    translation constant, scale default. Track 1: rotation default (the bind pose), translation animated as
    raw floats (x 10 + the sample), scale default. Stripped: segment 0 keeps samples 0 and 2."""
    ntracks, nsamples = 2, 2 * SEGMENT
    flags = (1 | (0 if additive else 1 << 1) | 1 << 2 | 1 << 3 | acl.QUAT_DROP_W_VARIABLE << 4 | 1 << 30
             | (1 << 10 if stripped else 0))
    types = [(2 << 30) | (0 << 28), (1 << 30) | (2 << 28), 0]        # rotations, translations, scales
    const = struct.pack("<3f", 1.0, 2.0, 3.0)                          # track 0's translation
    clip = struct.pack("<6f", 0.0, -0.5, 0.0, 0.5, 1.0, 0.0)          # track 0's rotation: min xyz, extent xyz
    segments = []
    for si in range(2):
        formats = bytes([8 if si == 0 else 0, 0, 0, 0, acl.RAW])      # rotation (padded to 4), translation
        # rotation group of 4: min x[4], y[4], z[4], extent x[4], y[4], z[4] (u8), or the constant 16-bit sample
        rng = bytearray(24)
        if si == 0:
            rng[0], rng[4], rng[8], rng[12], rng[16], rng[20] = 0, 0, 0, 255, 255, 255
        else:
            for j, v in enumerate((0x80, 0x00, 0x80, 0x00, 0xFF, 0xFF)):  # x 0x8000, y 0x8000, z 0xFFFF
                rng[4 * j] = v
        rng += bytes(6)                                                # translation (raw: unused)
        w = BitWriter()
        kept = [0, 2] if stripped and si == 0 else list(range(SEGMENT))
        for k in kept:
            if si == 0:
                w.put(0, 8), w.put((0, 127, 255)[k], 8), w.put(0, 8)    # x 0, y 0, 127 or 255, z 0
            w.float(10.0 + SEGMENT * si + k), w.float(-1.0), w.float(0.5)
        bits_r = 24 if si == 0 else 0
        segments.append((formats, bytes(rng), w.bytes(), bits_r + 96, bits_r, 96, kept))
    nseg = 2
    head = 52
    starts = struct.pack("<3I", 0, SEGMENT, 0xFFFFFFFF)
    seg_header_size = 20 if stripped else 16
    seg_off = head + len(starts)
    types_off = seg_off + seg_header_size * nseg
    const_off = types_off + 12
    range_off = const_off + len(const)
    data = bytearray()
    data_offs = []
    at = range_off + len(clip)
    for formats, rng, samples, *_ in segments:
        data_offs.append(at)
        blob = formats + bytes((at + len(formats)) % 2)
        blob += rng
        blob += bytes(-(at + len(blob)) % 4)
        blob += samples
        data += blob
        at += len(blob)
    th = struct.pack("<13I", nseg, 5, 1, 1, 0, 0, 1, 0, 0xFFFFFFFF, seg_off, types_off, const_off, range_off)
    seg_headers = b""
    for (formats, rng, samples, pose, rb, tb, kept), off in zip(segments, data_offs):
        seg_headers += struct.pack("<4I", pose, rb, tb, off)
        if stripped:
            seg_headers += struct.pack("<I", sum(1 << (31 - k) for k in kept))
    body = th + starts + seg_headers + struct.pack("<3I", *types) + const + clip + bytes(data)
    tracks_header = struct.pack("<IHBBIIfI", acl.TAG, acl.VERSION, acl.UNIFORM, acl.QVVF, ntracks, nsamples, 30.0, flags)
    total = 8 + len(tracks_header) + len(body)
    return struct.pack("<II", total, 0) + tracks_header + body


BIND = [((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)),
        ((0.0, 0.0, 0.0), (0.0, 0.0, math.sin(0.25), math.cos(0.25)), (1.0, 1.0, 1.0))]


def close(a, b, eps=1e-6):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


def test_a_hand_built_stream_decodes():
    head = acl.info(build())
    assert (head["tracks"], head["samples"], head["keys"], head["wrap"], head["trivial"]) == (2, 6, 7, True, False)
    (t0, r0, s0), (t1, r1, s1) = acl.decode(build(), BIND)
    assert len(r0) == len(t1) == 7 and r0[6] == r0[0] and t1[6] == t1[0]     # the last key is the first again
    # Track 0's rotation: y from min -0.5 by extent 1 * (0, 127 or 255) / 255; in segment 1 the 16-bit sample.
    assert close(r0[0], acl._quat(0.0, -0.5, 0.0)) and close(r0[2], acl._quat(0.0, 0.5, 0.0))
    assert close(r0[1], acl._quat(0.0, -0.5 + 127 / 255, 0.0))
    assert close(r0[3], acl._quat(0x8000 / 65535 * 0.5, -0.5 + 0x8000 / 65535, 0.0), 1e-6) and r0[4] == r0[3]
    assert t0 == [(1.0, 2.0, 3.0)] * 7 and s0 == [(1.0, 1.0, 1.0)] * 7
    assert t1[:6] == [(10.0 + k, -1.0, 0.5) for k in range(6)]
    assert r1 == [BIND[1][1]] * 7                                   # a default sub track is the bind pose


def test_a_stripped_sample_lies_between_the_kept_ones():
    # ACL keeps a segment's first and last sample; one between them is lerped (nlerped) where it lies.
    (t0, r0, _), (t1, _, _) = acl.decode(build(stripped=True), BIND)
    assert t1[:3] == [(10.0, -1.0, 0.5), (11.0, -1.0, 0.5), (12.0, -1.0, 0.5)]
    assert close(r0[1], acl._nlerp(r0[0], r0[2], 0.5)) and not close(r0[1], r0[0], 1e-3)


def test_defaults_are_the_identity_in_an_additive_sequence_and_scales_the_default_scale():
    (t0, r0, s0), (t1, r1, s1) = acl.decode(build(additive=True))        # no bind pose needed
    assert r1 == [(0.0, 0.0, 0.0, 1.0)] * 7 and s0 == s1 == [(0.0, 0.0, 0.0)] * 7
    assert acl.decode(build(additive=True), BIND) == acl.decode(build(additive=True))
    # A scale left at its default is the default scale, whatever the bind pose's (a prop's root at 100).
    big = [(t, q, (100.0, 100.0, 100.0)) for t, q, _ in BIND]
    assert [s for _, _, s in acl.decode(build(), big)] == [[(1.0, 1.0, 1.0)] * 7] * 2


def test_w_comes_back_past_a_length_of_one():
    # Near a half turn the quantized x, y, z can come out over a length of 1: ACL takes |1 - x² - y² - z²|.
    q = acl._quat(0.8, 0.6, 0.1)                                        # 1.01 long
    assert q[3] > 0.09 and abs(sum(v * v for v in q) - 1.0) < 1e-12


def test_streams_wcmods_doesnt_decode_are_refused():
    data = bytearray(build())
    with pytest.raises(acl.FormatError, match="bind pose"):
        acl.decode(bytes(data))
    data[12:14] = struct.pack("<H", 7)                                # ACL 2.0
    with pytest.raises(acl.FormatError, match="version 7"):
        acl.decode(bytes(data), BIND)
    with pytest.raises(acl.FormatError, match="not an ACL stream"):
        acl.info(b"\0" * 100)


def test_a_sequence_in_acl_decodes_with_its_skeletons_pose():
    seq = object.__new__(anim.AnimSequence)
    seq.codec, seq.blob, seq.track_map, seq.nkeys = "acl", build(), [3, 1], 7
    skel = type("Skel", (), {"poses": [None, BIND[1], None, BIND[0]]})()
    assert seq.bind_pose(skel) == [BIND[0], BIND[1]]                     # each track's bone's reference pose
    assert seq.tracks(seq.bind_pose(skel)) == acl.decode(build(), BIND)
    seq.nkeys = 6
    with pytest.raises(anim.FormatError, match="aren't the sequence's"):
        seq.tracks(BIND)
    seq.track_map = [7, 1]
    with pytest.raises(anim.FormatError, match="aren't all bones"):
        seq.bind_pose(skel)
    seq._package_names = lambda: ["/ACLPlugin/ACLAnimBoneCompressionSettings", "/Game/Art/X/SK_X_Skeleton"]
    assert seq.skeleton_name() == "/Game/Art/X/SK_X_Skeleton"
