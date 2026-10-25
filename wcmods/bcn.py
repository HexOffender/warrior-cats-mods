"""DXT1 and DXT5 (BC1 and BC3) texture blocks, encoded and decoded in plain Python.

The game's textures are DXT-compressed: 4 x 4 pixel blocks, 8 bytes each in DXT1 (two 5:6:5
colours and a 2-bit index per pixel), 16 in DXT5 (an alpha block of two 8-bit values and 3-bit
indices, then a DXT1 colour block). The encoder picks each block's two colours along the block's
main colour axis and each pixel's nearest of the four colours: not the best compressor there is, but
a fair one, and quick enough for a mod's textures.

Images are RGBA bytes, row by row (see png.py); widths and heights are multiples of 4, or 1 or 2 for
the smallest mips.
"""
import struct

FORMATS = {"PF_DXT1": 8, "PF_DXT5": 16}     # bytes per block


def size(fmt, width, height):
    """Bytes of a mip of that size."""
    return max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * FORMATS[fmt]


def _565(r, g, b):
    return ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255)


def _rgb(c):
    r, g, b = c >> 11, (c >> 5) & 63, c & 31
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)


def _block(rgba, width, height, bx, by):
    """The 16 pixels of a block, (r, g, b, a) each, repeating edge pixels past the image."""
    px = []
    for y in range(4):
        yy = min(by * 4 + y, height - 1)
        for x in range(4):
            i = (yy * width + min(bx * 4 + x, width - 1)) * 4
            px.append((rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]))
    return px


def _colour_block(px):
    n = len(px)
    mr = sum(p[0] for p in px) / n
    mg = sum(p[1] for p in px) / n
    mb = sum(p[2] for p in px) / n
    # The main axis of the colours: a few power iterations on their covariance.
    cxx = cxy = cxz = cyy = cyz = czz = 0.0
    for r, g, b, _ in px:
        dr, dg, db = r - mr, g - mg, b - mb
        cxx += dr * dr
        cxy += dr * dg
        cxz += dr * db
        cyy += dg * dg
        cyz += dg * db
        czz += db * db
    ax, ay, az = 1.0, 1.0, 1.0
    for _ in range(4):
        ax, ay, az = (cxx * ax + cxy * ay + cxz * az, cxy * ax + cyy * ay + cyz * az, cxz * ax + cyz * ay + czz * az)
        m = max(abs(ax), abs(ay), abs(az))
        if m < 1e-9:
            ax, ay, az = 1.0, 1.0, 1.0
            break
        ax, ay, az = ax / m, ay / m, az / m
    lo = hi = None
    lo_d = hi_d = 0.0
    for p in px:
        d = p[0] * ax + p[1] * ay + p[2] * az
        if lo is None or d < lo_d:
            lo, lo_d = p, d
        if hi is None or d > hi_d:
            hi, hi_d = p, d
    c0, c1 = _565(*hi[:3]), _565(*lo[:3])
    if c0 < c1:
        c0, c1 = c1, c0
    if c0 == c1:
        return struct.pack("<HHI", c0, c1, 0)
    p0, p1 = _rgb(c0), _rgb(c1)
    pal = (p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)), tuple((a + 2 * b) // 3 for a, b in zip(p0, p1)))
    bits = 0
    for i, (r, g, b, _) in enumerate(px):
        best, best_d = 0, None
        for k, (pr, pg, pb) in enumerate(pal):
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if best_d is None or d < best_d:
                best, best_d = k, d
        bits |= best << (2 * i)
    return struct.pack("<HHI", c0, c1, bits)


def _alpha_block(px):
    alphas = [p[3] for p in px]
    a0, a1 = max(alphas), min(alphas)
    if a0 == a1:
        return bytes((a0, a1)) + b"\0" * 6
    pal = [a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)]
    bits = 0
    for i, a in enumerate(alphas):
        best = min(range(8), key=lambda k: abs(a - pal[k]))
        bits |= best << (3 * i)
    return bytes((a0, a1)) + bits.to_bytes(6, "little")


def encode(fmt, width, height, rgba):
    """The DXT blocks of an RGBA image."""
    out = bytearray()
    for by in range((height + 3) // 4):
        for bx in range((width + 3) // 4):
            px = _block(rgba, width, height, bx, by)
            if fmt == "PF_DXT5":
                out += _alpha_block(px)
            out += _colour_block(px)
    return bytes(out)


def decode(fmt, width, height, data):
    """RGBA bytes of DXT blocks."""
    out = bytearray(width * height * 4)
    step = FORMATS[fmt]
    p = 0
    for by in range((height + 3) // 4):
        for bx in range((width + 3) // 4):
            alpha = [255] * 16
            if fmt == "PF_DXT5":
                a0, a1 = data[p], data[p + 1]
                bits = int.from_bytes(data[p + 2:p + 8], "little")
                if a0 > a1:
                    pal = [a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)]
                else:
                    pal = [a0, a1] + [((5 - k) * a0 + k * a1) // 5 for k in range(1, 5)] + [0, 255]
                alpha = [pal[(bits >> (3 * i)) & 7] for i in range(16)]
            c0, c1, bits = struct.unpack_from("<HHI", data, p + step - 8)
            p0, p1 = _rgb(c0), _rgb(c1)
            if c0 > c1 or fmt == "PF_DXT5":
                pal = [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)),
                       tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
                trans = None
            else:
                pal = [p0, p1, tuple((a + b) // 2 for a, b in zip(p0, p1)), (0, 0, 0)]
                trans = 3
            for i in range(16):
                x, y = bx * 4 + i % 4, by * 4 + i // 4
                if x < width and y < height:
                    k = (bits >> (2 * i)) & 3
                    o = (y * width + x) * 4
                    out[o:o + 3] = bytes(pal[k])
                    out[o + 3] = 0 if k == trans else alpha[i]
            p += step
    return bytes(out)
