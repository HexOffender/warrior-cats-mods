"""Read the game's IoStore container (.utoc/.ucas) and write small mod containers.

Format notes (verified against pakchunk0-Windows.utoc, UE 5.7):
  * TOC version 8, 144-byte header, 12-byte chunk ids, 10-byte big-endian offset/length pairs,
    12-byte compression blocks, directory index, then 24-byte chunk metas (BLAKE3-160 + flags).
  * Container header chunk (type 6): 'IoCn' version 5, package ids, 16-byte store entries whose
    array views hold offsets relative to the field itself, then a soft-package-reference blob
    addressed by an absolute (offset, size) pair.
"""
import struct

from .binio import read_fstring, write_fstring
from .oodle import Oodle
from .blake3 import blake3

TOC_MAGIC = b"-==--==--==--==-"
TOC_VERSION = 8
TOC_HEADER_SIZE = 144
BLOCK_SIZE = 0x10000
CHUNK_EXPORT_BUNDLE = 1
CHUNK_CONTAINER_HEADER = 6
FLAG_COMPRESSED, FLAG_ENCRYPTED, FLAG_SIGNED, FLAG_INDEXED = 1, 2, 4, 8
HEADER_SIGNATURE = 0x496F436E
NONE = 0xFFFFFFFF


class IoStoreReader:
    def __init__(self, utoc_path, oodle=None):
        self.utoc_path = utoc_path
        self.ucas_path = utoc_path[:-5] + ".ucas"
        self.oodle = oodle or Oodle()   # wcmods' own Kraken decoder unless a DLL-backed one is given
        buf = open(utoc_path, "rb").read()
        if buf[:16] != TOC_MAGIC:
            raise ValueError(f"{utoc_path}: not a utoc file")
        self.version = buf[16]
        (hdr_size, entries, nblocks, block_entry, nmethods, method_len, self.block_size,
         dir_size, _partitions) = struct.unpack_from("<9I", buf, 20)
        self.container_id = buf[56:64]
        self.flags = buf[80]
        if self.flags & FLAG_ENCRYPTED:
            raise ValueError(f"{utoc_path}: encrypted containers are not supported")
        (seeds,) = struct.unpack_from("<I", buf, 84)
        (no_hash,) = struct.unpack_from("<I", buf, 96)
        p = hdr_size
        self.chunk_ids = [buf[p + i * 12:p + i * 12 + 12] for i in range(entries)]
        p += entries * 12
        self.chunk_ranges = []
        for i in range(entries):
            b = buf[p + i * 10:p + i * 10 + 10]
            self.chunk_ranges.append((int.from_bytes(b[:5], "big"), int.from_bytes(b[5:], "big")))
        p += entries * 10 + seeds * 4 + no_hash * 4
        self.blocks = []
        for i in range(nblocks):
            b = buf[p + i * block_entry:p + i * block_entry + 12]
            self.blocks.append((int.from_bytes(b[0:5], "little"), int.from_bytes(b[5:8], "little"),
                                int.from_bytes(b[8:11], "little"), b[11]))
        p += nblocks * block_entry
        self.methods = [buf[p + i * method_len:p + (i + 1) * method_len].rstrip(b"\0").decode()
                        for i in range(nmethods)]
        p += nmethods * method_len
        self.files = _read_directory_index(buf[p:p + dir_size]) if self.flags & FLAG_INDEXED else {}

    def chunk_index(self, path):
        return self.files[path]

    def read_chunk(self, index):
        offset, length = self.chunk_ranges[index]
        first, last = offset // self.block_size, (offset + length - 1) // self.block_size
        parts = []
        with open(self.ucas_path, "rb") as f:
            for bi in range(first, last + 1):
                boff, csize, usize, method = self.blocks[bi]
                f.seek(boff)
                raw = f.read(csize)
                if method == 0:
                    parts.append(raw[:usize])
                elif self.methods[method - 1] == "Oodle":
                    parts.append(self.oodle.decompress(raw, usize))
                else:
                    raise RuntimeError(f"chunk is compressed with {self.methods[method - 1]}, which wcmods can't read")
        data = b"".join(parts)
        start = offset - first * self.block_size
        return data[start:start + length]

    def read_file(self, path):
        return self.read_chunk(self.files[path])

    def container_header(self):
        for i, cid in enumerate(self.chunk_ids):
            if cid[11] & 0x3F == CHUNK_CONTAINER_HEADER:
                return ContainerHeader.parse(self.read_chunk(i))
        raise ValueError("container has no header chunk")


def _read_directory_index(d):
    p = 0
    mount, p = read_fstring(d, p)
    (nd,) = struct.unpack_from("<i", d, p); p += 4
    dirs = [struct.unpack_from("<4I", d, p + i * 16) for i in range(nd)]; p += nd * 16
    (nf,) = struct.unpack_from("<i", d, p); p += 4
    files = [struct.unpack_from("<3I", d, p + i * 12) for i in range(nf)]; p += nf * 12
    (ns,) = struct.unpack_from("<i", d, p); p += 4
    strings = []
    for _ in range(ns):
        s, p = read_fstring(d, p)
        strings.append(s)
    out = {}
    stack = [(0, "")]
    while stack:
        di, prefix = stack.pop()
        name, child, sibling, first_file = dirs[di]
        here = prefix + (strings[name] + "/" if name != NONE else "")
        fi = first_file
        while fi != NONE:
            fname, nxt, chunk = files[fi]
            out[here + strings[fname]] = chunk
            fi = nxt
        c = child
        while c != NONE:
            stack.append((c, here))
            c = dirs[c][2]
    return out


class ContainerHeader:
    """Parsed container header; store entries are kept as (imported package ids, shader map hashes)."""

    def __init__(self, version, container_id, package_ids, entries, tail_fields, soft_refs):
        self.version = version
        self.container_id = container_id
        self.package_ids = package_ids
        self.entries = entries
        self.tail_fields = tail_fields   # raw bytes between store entries and the soft-ref pair
        self.soft_refs = soft_refs

    @classmethod
    def parse(cls, h):
        sig, version = struct.unpack_from("<II", h, 0)
        if sig != HEADER_SIGNATURE or version != 5:
            raise ValueError(f"unsupported container header (sig={sig:#x} version={version})")
        container_id = h[8:16]
        (n,) = struct.unpack_from("<i", h, 16)
        package_ids = list(struct.unpack_from(f"<{n}Q", h, 20))
        p = 20 + n * 8
        (store_len,) = struct.unpack_from("<i", h, p); p += 4
        store = h[p:p + store_len]
        entries = []
        for k in range(n):
            e = k * 16
            n_imp, o_imp, n_sh, o_sh = struct.unpack_from("<IIII", store, e)
            imports = list(struct.unpack_from(f"<{n_imp}Q", store, e + o_imp)) if n_imp else []
            shaders = [store[e + 8 + o_sh + j * 20:e + 8 + o_sh + (j + 1) * 20] for j in range(n_sh)]
            entries.append((imports, shaders))
        p += store_len
        soft_pos = len(h) - 16 - _soft_blob_len(h)
        tail_fields = h[p:soft_pos]
        soft_off, soft_size = struct.unpack_from("<qq", h, soft_pos)
        soft_refs = h[soft_off:soft_off + soft_size]
        return cls(version, container_id, package_ids, entries, tail_fields, soft_refs)

    def entry_for(self, package_id):
        return self.entries[self.package_ids.index(package_id)]

    def serialize(self):
        n = len(self.package_ids)
        fixed = bytearray()
        data = bytearray()
        for k, (imports, shaders) in enumerate(self.entries):
            field = k * 16
            if imports:
                o_imp = n * 16 + len(data) - field
                data += struct.pack(f"<{len(imports)}Q", *imports)
            else:
                o_imp = 0
            if shaders:
                o_sh = n * 16 + len(data) - (field + 8)
                data += b"".join(shaders)
            else:
                o_sh = 0
            fixed += struct.pack("<IIII", len(imports), o_imp, len(shaders), o_sh)
        store = bytes(fixed) + bytes(data)
        out = bytearray(struct.pack("<II", HEADER_SIGNATURE, self.version))
        out += self.container_id
        out += struct.pack("<i", n) + struct.pack(f"<{n}Q", *self.package_ids)
        out += struct.pack("<i", len(store)) + store
        out += self.tail_fields
        soft_off = len(out) + 16
        out += struct.pack("<qq", soft_off, len(self.soft_refs)) + self.soft_refs
        return bytes(out)


def _soft_blob_len(h):
    # The soft-reference pair (offset, size) sits right before its blob at the end of the header.
    for size in range(0, 64):
        pos = len(h) - 16 - size
        if pos < 0:
            break
        off, sz = struct.unpack_from("<qq", h, pos)
        if sz == size and off == pos + 16:
            return size
    raise ValueError("could not locate soft package references in container header")


# Fields between the store entries and the soft-ref pair for an empty container:
# optional segment package ids, optional segment store entries, redirect name map,
# localized packages, package redirects -- all empty.
EMPTY_TAIL_FIELDS = struct.pack("<iiiii", 0, 0, 0, 0, 0)


class ModContainerWriter:
    """Writes an uncompressed IoStore container holding replacement and new packages."""

    def __init__(self, container_id):
        self.container_id = container_id
        self.packages = []   # (path, chunk_id, data, imports, shaders)
        self.chunks = []     # (path, chunk_id, data): a package's other chunks, such as its .ubulk

    def add_package(self, path, chunk_id, data, imports, shaders):
        self.packages.append((path, chunk_id, bytes(data), imports, shaders))

    def add_chunk(self, path, chunk_id, data):
        """A chunk that isn't a package (no container header entry), e.g. a texture's bulk data."""
        self.chunks.append((path, chunk_id, bytes(data)))

    def write(self, utoc_path, ucas_path):
        header = ContainerHeader(
            5, self.container_id,
            [struct.unpack("<Q", cid[:8])[0] for _, cid, _, _, _ in self.packages],
            [(imp, sh) for _, _, _, imp, sh in self.packages],
            EMPTY_TAIL_FIELDS, b"\0\0\0\0").serialize()
        header_id = self.container_id + b"\0\0\0" + bytes([CHUNK_CONTAINER_HEADER])
        chunks = [(path, cid, data) for path, cid, data, _, _ in self.packages] + list(self.chunks)
        chunks.append((None, header_id, header))

        ucas = bytearray()
        ids, ranges, blocks, metas = [], [], [], []
        virtual = 0
        for _, cid, data in chunks:
            ids.append(cid)
            ranges.append((virtual, len(data)))
            for k in range(0, max(len(data), 1), BLOCK_SIZE):
                piece = data[k:k + BLOCK_SIZE]
                blocks.append((len(ucas), len(piece), len(piece), 0))
                ucas += piece
                ucas += b"\0" * (-len(ucas) % 16)
            virtual += -(-len(data) // BLOCK_SIZE) * BLOCK_SIZE or BLOCK_SIZE
            metas.append(blake3(data, 20) + b"\0\0\0\0")

        dir_index = _write_directory_index(
            {path: i for i, (path, _, _) in enumerate(chunks) if path is not None})

        hdr = bytearray(TOC_MAGIC)
        hdr += struct.pack("<BBH", TOC_VERSION, 0, 0)
        hdr += struct.pack("<9I", TOC_HEADER_SIZE, len(ids), len(blocks), 12, 0, 32, BLOCK_SIZE,
                           len(dir_index), 1)
        hdr += self.container_id
        hdr += b"\0" * 16                      # encryption key guid
        hdr += struct.pack("<BBH", FLAG_INDEXED, 0, 0)
        hdr += struct.pack("<I", 0)            # perfect hash seeds: none, reader falls back to a map
        hdr += struct.pack("<Q", 0xFFFFFFFFFFFFFFFF)
        hdr += struct.pack("<II", 0, 0)
        hdr += b"\0" * 40
        assert len(hdr) == TOC_HEADER_SIZE

        toc = bytearray(hdr)
        for cid in ids:
            toc += cid
        for off, length in ranges:
            toc += off.to_bytes(5, "big") + length.to_bytes(5, "big")
        for off, csize, usize, method in blocks:
            toc += off.to_bytes(5, "little") + csize.to_bytes(3, "little") + usize.to_bytes(3, "little") + bytes([method])
        toc += dir_index
        for m in metas:
            toc += m
        with open(utoc_path, "wb") as f:
            f.write(toc)
        with open(ucas_path, "wb") as f:
            f.write(ucas)


def _write_directory_index(files, mount="../../../"):
    """files: {'Wrc/Content/x.uasset': chunk_index}. Returns FIoDirectoryIndexResource bytes."""
    strings, string_ids = [], {}

    def sid(s):
        if s not in string_ids:
            string_ids[s] = len(strings)
            strings.append(s)
        return string_ids[s]

    dirs = [[NONE, NONE, NONE, NONE]]       # name, first child, next sibling, first file
    file_entries = []                      # name, next file, user data
    children = {0: {}}
    for path in sorted(files):
        parts = path.split("/")
        cur = 0
        for part in parts[:-1]:
            nxt = children[cur].get(part)
            if nxt is None:
                nxt = len(dirs)
                dirs.append([sid(part), NONE, dirs[cur][1], NONE])
                dirs[cur][1] = nxt
                children[cur][part] = nxt
                children[nxt] = {}
            cur = nxt
        fe = len(file_entries)
        file_entries.append([sid(parts[-1]), dirs[cur][3], files[path]])
        dirs[cur][3] = fe
    out = bytearray(write_fstring(mount))
    out += struct.pack("<i", len(dirs)) + b"".join(struct.pack("<4I", *d) for d in dirs)
    out += struct.pack("<i", len(file_entries)) + b"".join(struct.pack("<3I", *f) for f in file_entries)
    out += struct.pack("<i", len(strings)) + b"".join(write_fstring(s) for s in strings)
    return bytes(out)
