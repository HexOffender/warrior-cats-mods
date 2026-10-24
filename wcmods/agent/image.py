"""Pictures of the game window: an RGB image with PNG in and out, cropping, scaling and comparing.

Plain Python (no imaging library on the machine); the slow parts work a row or a channel at a time
with byte slices, so a 1920x1080 capture converts and saves in well under a second.
"""
import struct
import zlib


class Image:
    """width x height pixels, `rgb` holding 3 bytes per pixel, rows top to bottom."""

    def __init__(self, width, height, rgb):
        if len(rgb) != width * height * 3:
            raise ValueError(f"{width}x{height} needs {width * height * 3} bytes, not {len(rgb)}")
        self.width, self.height, self.rgb = width, height, bytes(rgb)

    def __repr__(self):
        return f"<Image {self.width}x{self.height}>"

    @classmethod
    def from_bgra(cls, data, width, height):
        """From a Windows bitmap's 32-bit BGRA pixels (top-down rows)."""
        out = bytearray(width * height * 3)
        out[0::3], out[1::3], out[2::3] = data[2::4], data[1::4], data[0::4]
        return cls(width, height, out)

    # ---------- files ----------
    def png(self):
        stride = self.width * 3
        raw = b"".join(b"\0" + self.rgb[y * stride:(y + 1) * stride] for y in range(self.height))

        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.png())
        return path

    @classmethod
    def load(cls, path):
        """An 8-bit RGB or RGBA PNG (what save() and most tools write)."""
        with open(path, "rb") as f:
            data = f.read()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"{path} isn't a PNG")
        pos, idat, header = 8, [], None
        while pos < len(data):
            n, kind = struct.unpack_from(">I4s", data, pos)
            body = data[pos + 8:pos + 8 + n]
            if kind == b"IHDR":
                header = struct.unpack(">IIBBBBB", body)
            elif kind == b"IDAT":
                idat.append(body)
            elif kind == b"IEND":
                break
            pos += 12 + n
        w, h, depth, colour, _, _, interlace = header
        if depth != 8 or colour not in (2, 6) or interlace:
            raise ValueError(f"{path}: only 8-bit RGB/RGBA PNGs without interlacing are read")
        bpp = 3 if colour == 2 else 4
        raw, stride = zlib.decompress(b"".join(idat)), w * bpp
        rows, prev = [], bytearray(stride)
        for y in range(h):
            f = raw[y * (stride + 1)]
            line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
            if f == 1:
                for i in range(bpp, stride):
                    line[i] = (line[i] + line[i - bpp]) & 255
            elif f == 2:
                for i in range(stride):
                    line[i] = (line[i] + prev[i]) & 255
            elif f == 3:
                for i in range(stride):
                    left = line[i - bpp] if i >= bpp else 0
                    line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
            elif f == 4:
                for i in range(stride):
                    a = line[i - bpp] if i >= bpp else 0
                    b, c = prev[i], prev[i - bpp] if i >= bpp else 0
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
            rows.append(bytes(line))
            prev = line
        joined = b"".join(rows)
        if bpp == 4:
            rgb = bytearray(w * h * 3)
            rgb[0::3], rgb[1::3], rgb[2::3] = joined[0::4], joined[1::4], joined[2::4]
            joined = bytes(rgb)
        return cls(w, h, joined)

    # ---------- changing it ----------
    def crop(self, x, y, w, h):
        """The part from (x, y), w by h; clipped to the picture."""
        x, y = max(0, int(x)), max(0, int(y))
        w, h = min(int(w), self.width - x), min(int(h), self.height - y)
        if w <= 0 or h <= 0:
            raise ValueError(f"crop ({x}, {y}, {w}, {h}) is outside the {self.width}x{self.height} picture")
        stride = self.width * 3
        rows = (self.rgb[(y + r) * stride + x * 3:(y + r) * stride + (x + w) * 3] for r in range(h))
        return Image(w, h, b"".join(rows))

    def scaled(self, factor):
        """Shrunk by a factor below 1 (every n-th pixel; fine for looking at, quick)."""
        if factor >= 1:
            return self
        step = max(1, round(1 / factor))
        w, h = self.width // step, self.height // step
        stride, rows = self.width * 3, []
        for y in range(h):
            line = self.rgb[y * step * stride:y * step * stride + w * step * 3]
            out = bytearray(w * 3)
            out[0::3], out[1::3], out[2::3] = line[0::3 * step][:w], line[1::3 * step][:w], line[2::3 * step][:w]
            rows.append(bytes(out))
        return Image(w, h, b"".join(rows))

    # ---------- looking at it ----------
    def pixel(self, x, y):
        i = (int(y) * self.width + int(x)) * 3
        return tuple(self.rgb[i:i + 3])

    def mean(self, step=4):
        """The average colour, from every `step`-th pixel each way."""
        stride, n, total = self.width * 3, 0, [0, 0, 0]
        for y in range(0, self.height, step):
            line = self.rgb[y * stride:(y + 1) * stride]
            for c in range(3):
                total[c] += sum(line[c::3 * step])
            n += len(line[0::3 * step])
        return tuple(t / max(1, n) for t in total)

    def blank(self, tolerance=3):
        """True when it's all one colour (a capture of a minimised or not-yet-drawn window is black)."""
        first = self.rgb[:3]
        step = max(1, self.width * self.height // 5000)
        return all(abs(self.rgb[i * 3 + c] - first[c]) <= tolerance
                   for i in range(0, self.width * self.height, step) for c in range(3))

    def diff(self, other, step=2):
        """How different two pictures of the same size are: 0 (the same) to 1, the mean of |a - b|."""
        if (self.width, self.height) != (other.width, other.height):
            raise ValueError(f"can't compare {self.width}x{self.height} with {other.width}x{other.height}")
        stride, total, n = self.width * 3, 0, 0
        for y in range(0, self.height, step):
            a = self.rgb[y * stride:(y + 1) * stride:step]
            b = other.rgb[y * stride:(y + 1) * stride:step]
            total += sum(abs(p - q) for p, q in zip(a, b))
            n += len(a)
        return total / (255 * max(1, n))
