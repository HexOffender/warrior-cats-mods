"""Read and write legacy Unreal .pak files (version 12, as shipped by this game).

The writer only produces uncompressed, unencrypted paks, which the engine accepts for mods.
Layout matches UnrealPak: [entries][primary index][path-hash index][full directory index][footer].
"""
import hashlib
import struct
import zlib

from .binio import fnv64, read_fstring, write_fstring, write_utf8_string

PAK_MAGIC = 0x5A6F12E1
PAK_VERSION = 12
FOOTER_SIZE = 16 + 1 + 4 + 4 + 8 + 8 + 20 + 5 * 32


class PakEntry:
    __slots__ = ("path", "offset", "size", "raw_size", "method", "block_size", "block_sizes", "encrypted")


class PakReader:
    def __init__(self, path, oodle=None):
        self.path = path
        self.oodle = oodle
        self.entries = {}
        with open(path, "rb") as f:
            f.seek(0, 2)
            total = f.tell()
            f.seek(total - 512)
            tail = f.read(512)
            i = tail.rfind(struct.pack("<I", PAK_MAGIC))
            if i < 0:
                raise ValueError(f"{path}: not a pak file")
            self.version, index_off, index_size = struct.unpack_from("<iqq", tail, i + 4)
            if tail[i - 1]:
                raise ValueError(f"{path}: encrypted index is not supported")
            self.methods = [tail[i + 44 + k * 32:i + 44 + (k + 1) * 32].rstrip(b"\0").decode() for k in range(5)]
            f.seek(index_off)
            idx = f.read(index_size)
            p = 0
            self.mount, p = read_fstring(idx, p)
            p += 12  # entry count + path hash seed
            (has_phi,) = struct.unpack_from("<i", idx, p); p += 4
            if has_phi:
                p += 36
            (has_fdi,) = struct.unpack_from("<i", idx, p); p += 4
            if not has_fdi:
                raise ValueError(f"{path}: pak has no full directory index")
            fdi_off, fdi_size = struct.unpack_from("<qq", idx, p); p += 36
            (enc_size,) = struct.unpack_from("<i", idx, p); p += 4
            enc = idx[p:p + enc_size]
            f.seek(fdi_off)
            fdi = f.read(fdi_size)
        self.directory_index = fdi
        q = 0
        (ndirs,) = struct.unpack_from("<i", fdi, q); q += 4
        for _ in range(ndirs):
            d, q = read_fstring(fdi, q)
            (nf,) = struct.unpack_from("<i", fdi, q); q += 4
            for _ in range(nf):
                fn, q = read_fstring(fdi, q)
                (eoff,) = struct.unpack_from("<i", fdi, q); q += 4
                if eoff >= 0:
                    e = _decode_entry(enc, eoff)
                    e.path = (d if d != "/" else "") + fn
                    self.entries[e.path] = e

    def read(self, path):
        e = self.entries[path]
        if e.encrypted:
            raise ValueError(f"{path} is encrypted")
        header = _entry_header_size(e)
        with open(self.path, "rb") as f:
            if not e.method:
                f.seek(e.offset + header)
                return f.read(e.raw_size)
            if self.oodle is None or self.methods[e.method - 1] != "Oodle":
                raise RuntimeError(f"{path} is compressed ({self.methods[e.method - 1]}); Oodle DLL needed")
            out, pos = [], e.offset + header
            for k, csize in enumerate(e.block_sizes):
                f.seek(pos)
                want = min(e.block_size, e.raw_size - k * e.block_size)
                out.append(self.oodle.decompress(f.read(csize), want))
                pos += csize
            return b"".join(out)


def _decode_entry(enc, p):
    e = PakEntry()
    (bits,) = struct.unpack_from("<I", enc, p); p += 4
    bs = bits & 0x3F
    if bs == 0x3F:
        (bs,) = struct.unpack_from("<I", enc, p); p += 4
    else:
        bs <<= 11
    e.method = (bits >> 23) & 0x3F
    e.encrypted = bool(bits & (1 << 22))
    nblocks = (bits >> 6) & 0xFFFF
    if bits & (1 << 31):
        (e.offset,) = struct.unpack_from("<I", enc, p); p += 4
    else:
        (e.offset,) = struct.unpack_from("<Q", enc, p); p += 8
    if bits & (1 << 30):
        (e.raw_size,) = struct.unpack_from("<I", enc, p); p += 4
    else:
        (e.raw_size,) = struct.unpack_from("<Q", enc, p); p += 8
    e.size = e.raw_size
    if e.method:
        if bits & (1 << 29):
            (e.size,) = struct.unpack_from("<I", enc, p); p += 4
        else:
            (e.size,) = struct.unpack_from("<Q", enc, p); p += 8
    if bs == 0 or bs > e.raw_size:
        bs = e.raw_size
    e.block_size = bs
    if nblocks == 1 and not e.encrypted:
        e.block_sizes = [e.size]
    elif nblocks:
        e.block_sizes = list(struct.unpack_from(f"<{nblocks}I", enc, p))
    else:
        e.block_sizes = []
    return e


def _entry_header_size(e):
    n = len(e.block_sizes) if e.method else 0
    return 8 + 8 + 8 + 4 + 20 + ((4 + 16 * n) if e.method else 0) + 1 + 4


class PakWriter:
    """Collects files (paths relative to the mount point, e.g. 'Wrc/Content/...') and writes a v12 pak."""

    def __init__(self, mount="../../../"):
        self.mount = mount
        self.files = {}

    def add(self, path, data):
        self.files[path.replace("\\", "/").lstrip("/")] = bytes(data)

    def write(self, out_path, pak_name):
        seed = zlib.crc32(pak_name.lower().encode("utf-16-le"))
        body = bytearray()
        encoded = bytearray()
        locations = {}
        for path in sorted(self.files):
            data = self.files[path]
            offset = len(body)
            sha = hashlib.sha1(data).digest()
            # In-data copy of FPakEntry: Offset is written as 0 by UnrealPak.
            body += struct.pack("<qqqI", 0, len(data), len(data), 0) + sha + b"\0" + struct.pack("<I", 0)
            body += data
            locations[path] = len(encoded)
            bits = 0
            if offset <= 0xFFFFFFFF:
                bits |= 1 << 31
            if len(data) <= 0xFFFFFFFF:
                bits |= (1 << 30) | (1 << 29)
            encoded += struct.pack("<I", bits)
            encoded += struct.pack("<I", offset) if offset <= 0xFFFFFFFF else struct.pack("<Q", offset)
            encoded += struct.pack("<I", len(data)) if len(data) <= 0xFFFFFFFF else struct.pack("<Q", len(data))

        dirs = {"/": {}}
        for path, loc in locations.items():
            parent, _, name = path.rpartition("/")
            parts = parent.split("/") if parent else []
            for k in range(1, len(parts) + 1):
                dirs.setdefault("/".join(parts[:k]) + "/", {})
            dirs[(parent + "/") if parent else "/"][name] = loc
        # Folder names are FStrings; file names are UTF-8 without a terminator (version 12). A file
        # name written as an FString reads back with a trailing NUL, so the engine never finds it.
        fdi = bytearray(struct.pack("<i", len(dirs)))
        for d in sorted(dirs):
            fdi += write_fstring(d) + struct.pack("<i", len(dirs[d]))
            for name in sorted(dirs[d]):
                fdi += write_utf8_string(name) + struct.pack("<i", dirs[d][name])

        phi = bytearray(struct.pack("<i", len(locations)))
        for path, loc in sorted(locations.items()):
            phi += struct.pack("<Qi", fnv64(path.lower().encode("utf-16-le"), seed), loc)
        phi += fdi  # pruned directory index (we keep it complete)

        def primary(phi_off, fdi_off):
            out = bytearray(write_fstring(self.mount))
            out += struct.pack("<iQ", len(locations), seed)
            out += struct.pack("<iqq", 1, phi_off, len(phi)) + hashlib.sha1(phi).digest()
            out += struct.pack("<iqq", 1, fdi_off, len(fdi)) + hashlib.sha1(fdi).digest()
            out += struct.pack("<i", len(encoded)) + encoded
            out += struct.pack("<i", 0)
            return bytes(out)

        index_off = len(body)
        index_len = len(primary(0, 0))
        phi_off = index_off + index_len
        fdi_off = phi_off + len(phi)
        index = primary(phi_off, fdi_off)
        footer = (b"\0" * 16 + b"\0" + struct.pack("<Iiqq", PAK_MAGIC, PAK_VERSION, index_off, len(index))
                  + hashlib.sha1(index).digest() + b"\0" * (5 * 32))
        assert len(footer) == FOOTER_SIZE
        with open(out_path, "wb") as f:
            f.write(body)
            f.write(index)
            f.write(phi)
            f.write(fdi)
            f.write(footer)
