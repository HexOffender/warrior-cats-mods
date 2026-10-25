"""PNG images, read and written in plain Python: enough for a mod's textures and for saving the
game's own textures as pictures to paint over.

Images are (width, height, pixels), the pixels RGBA, 4 bytes each, row by row from the top.
Reads 8- and 16-bit greyscale, grey + alpha, RGB, RGBA and palette images (1/2/4/8-bit), not
interlaced ones.
"""
import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read(data):
    """(width, height, RGBA bytes) of a PNG file's bytes."""
    if not data.startswith(SIGNATURE):
        raise ValueError("not a PNG file")
    p, idat, palette, trns = 8, [], None, None
    width = height = depth = ctype = None
    while p < len(data):
        n, kind = struct.unpack_from(">I4s", data, p)
        body = data[p + 8:p + 8 + n]
        p += 12 + n
        if kind == b"IHDR":
            width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if interlace:
                raise ValueError("interlaced PNGs aren't supported; save it without interlacing")
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if width is None:
        raise ValueError("PNG without a header")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if channels is None or depth not in (1, 2, 4, 8, 16) or (depth < 8 and ctype not in (0, 3)):
        raise ValueError(f"unsupported PNG kind (colour type {ctype}, {depth}-bit)")
    raw = zlib.decompress(b"".join(idat))
    bpp = max(1, channels * depth // 8)           # bytes per pixel, for the filters
    stride = (width * channels * depth + 7) // 8
    rows = _unfilter(raw, height, stride, bpp)
    out = bytearray(width * height * 4)
    for y, row in enumerate(rows):
        _to_rgba(row, width, ctype, depth, palette, trns, out, y * width * 4)
    return width, height, bytes(out)


def _unfilter(raw, height, stride, bpp):
    rows, prev, p = [], bytearray(stride), 0
    for _ in range(height):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        if f == 1:                                         # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif f == 2:                                       # Up
            line = bytearray((a + b) & 0xFF for a, b in zip(line, prev))
        elif f == 3:                                       # Average
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif f == 4:                                       # Paeth
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        elif f != 0:
            raise ValueError(f"bad PNG filter {f}")
        rows.append(line)
        prev = line
    return rows


def _to_rgba(row, width, ctype, depth, palette, trns, out, o):
    if depth == 16:
        row = row[0::2]                                    # the high bytes
        depth = 8
    if depth < 8:                                          # greyscale or palette, packed
        per = 8 // depth
        mask = (1 << depth) - 1
        vals = [(row[i // per] >> (8 - depth * (i % per + 1))) & mask for i in range(width)]
        if ctype == 0:
            scale = 255 // mask
            vals = [v * scale for v in vals]
        row = bytes(vals)
    if ctype == 6:
        out[o:o + width * 4] = row[:width * 4]
    elif ctype == 2:
        key = struct.unpack(">HHH", trns) if trns and len(trns) == 6 else None
        for x in range(width):
            r, g, b = row[3 * x:3 * x + 3]
            a = 0 if key and (r, g, b) == tuple(k & 0xFF for k in key) else 255
            out[o + 4 * x:o + 4 * x + 4] = bytes((r, g, b, a))
    elif ctype == 0:
        for x in range(width):
            v = row[x]
            out[o + 4 * x:o + 4 * x + 4] = bytes((v, v, v, 255))
    elif ctype == 4:
        for x in range(width):
            v, a = row[2 * x], row[2 * x + 1]
            out[o + 4 * x:o + 4 * x + 4] = bytes((v, v, v, a))
    else:                                                  # palette
        if palette is None:
            raise ValueError("palette PNG without a palette")
        for x in range(width):
            i = row[x]
            r, g, b = palette[3 * i:3 * i + 3]
            a = trns[i] if trns and i < len(trns) else 255
            out[o + 4 * x:o + 4 * x + 4] = bytes((r, g, b, a))


def write(width, height, rgba):
    """PNG file bytes of an RGBA image."""
    stride = width * 4
    raw = b"".join(b"\0" + rgba[y * stride:(y + 1) * stride] for y in range(height))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def resize(width, height, rgba, new_w, new_h):
    """The image scaled to new_w x new_h: an average of the pixels each new one covers when it shrinks,
    bilinear when it grows."""
    if (width, height) == (new_w, new_h):
        return rgba
    out = bytearray(new_w * new_h * 4)
    if new_w <= width and new_h <= height:
        for y in range(new_h):
            y0, y1 = y * height // new_h, max(y * height // new_h + 1, (y + 1) * height // new_h)
            for x in range(new_w):
                x0, x1 = x * width // new_w, max(x * width // new_w + 1, (x + 1) * width // new_w)
                acc = [0, 0, 0, 0]
                for yy in range(y0, y1):
                    base = (yy * width + x0) * 4
                    for xx in range(x1 - x0):
                        i = base + 4 * xx
                        acc[0] += rgba[i]
                        acc[1] += rgba[i + 1]
                        acc[2] += rgba[i + 2]
                        acc[3] += rgba[i + 3]
                n = (y1 - y0) * (x1 - x0)
                o = (y * new_w + x) * 4
                out[o:o + 4] = bytes((acc[0] // n, acc[1] // n, acc[2] // n, acc[3] // n))
        return bytes(out)
    for y in range(new_h):
        fy = max(0.0, (y + 0.5) * height / new_h - 0.5)
        y0 = min(int(fy), height - 1)
        y1 = min(y0 + 1, height - 1)
        ty = fy - y0
        for x in range(new_w):
            fx = max(0.0, (x + 0.5) * width / new_w - 0.5)
            x0 = min(int(fx), width - 1)
            x1 = min(x0 + 1, width - 1)
            tx = fx - x0
            o = (y * new_w + x) * 4
            for c in range(4):
                a = rgba[(y0 * width + x0) * 4 + c] * (1 - tx) + rgba[(y0 * width + x1) * 4 + c] * tx
                b = rgba[(y1 * width + x0) * 4 + c] * (1 - tx) + rgba[(y1 * width + x1) * 4 + c] * tx
                out[o + c] = int(a * (1 - ty) + b * ty + 0.5)
    return bytes(out)


def half(width, height, rgba):
    """The next mip down: each pixel the average of a 2 x 2 square (a 1-pixel side stays 1)."""
    nw, nh = max(1, width // 2), max(1, height // 2)
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        r0 = min(2 * y, height - 1) * width * 4
        r1 = min(2 * y + 1, height - 1) * width * 4
        for x in range(nw):
            c0 = min(2 * x, width - 1) * 4
            c1 = min(2 * x + 1, width - 1) * 4
            o = (y * nw + x) * 4
            for c in range(4):
                out[o + c] = (rgba[r0 + c0 + c] + rgba[r0 + c1 + c] + rgba[r1 + c0 + c] + rgba[r1 + c1 + c] + 2) >> 2
    return nw, nh, bytes(out)
