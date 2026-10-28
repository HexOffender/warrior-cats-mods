"""Reading a Windows executable (PE32+): its sections, functions (.pdata) and relocations (.reloc).

The game's exe is relocated by ASLR on every launch (DYNAMIC_BASE), so everything here works in
RVAs, addresses relative to the image's start, which are the same on disk and in memory. Its code
isn't encrypted on disk (Steam's wrapper only adds a .bind section at the entry point), so the
file can be read directly. Used by signatures.py and tools/re/.
"""
import hashlib
import os
import struct

IMAGE_REL_BASED_DIR64 = 10
UNW_FLAG_CHAININFO = 4


class Section:
    def __init__(self, name, rva, vsize, raw, rawsize, flags, data):
        self.name, self.rva, self.vsize, self.raw, self.rawsize, self.flags = name, rva, vsize, raw, rawsize, flags
        self.data = data

    def __repr__(self):
        return f"<Section {self.name} rva=0x{self.rva:X} size=0x{self.vsize:X}>"


class Image:
    """An exe on disk. `text` is its code section; addresses are RVAs."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.raw = f.read()
        d = self.raw
        if d[:2] != b"MZ":
            raise ValueError(f"{path} isn't an exe")
        pe = struct.unpack_from("<I", d, 0x3C)[0]
        if d[pe:pe + 4] != b"PE\0\0":
            raise ValueError(f"{path} isn't a PE file")
        self.machine, nsec, self.timestamp = struct.unpack_from("<HHI", d, pe + 4)
        optsize, self.characteristics = struct.unpack_from("<HH", d, pe + 20)
        opt = pe + 24
        if struct.unpack_from("<H", d, opt)[0] != 0x20B:
            raise ValueError(f"{path} isn't a 64-bit exe")
        self.entry = struct.unpack_from("<I", d, opt + 16)[0]
        self.image_base = struct.unpack_from("<Q", d, opt + 24)[0]
        self.size_of_image = struct.unpack_from("<I", d, opt + 56)[0]
        self.checksum = struct.unpack_from("<I", d, opt + 64)[0]
        self.dll_characteristics = struct.unpack_from("<H", d, opt + 70)[0]
        ndirs = struct.unpack_from("<I", d, opt + 108)[0]
        self.dirs = [struct.unpack_from("<II", d, opt + 112 + 8 * i) for i in range(ndirs)]
        self.sections = []
        for i in range(nsec):
            o = opt + optsize + 40 * i
            name = d[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, rva, rawsize, raw = struct.unpack_from("<IIII", d, o + 8)
            flags = struct.unpack_from("<I", d, o + 36)[0]
            self.sections.append(Section(name, rva, vsize, raw, rawsize, flags, memoryview(d)[raw:raw + min(rawsize, vsize)]))
        self.text = self.section(".text")
        self._functions = self._relocs = self._entries = self._whole = None

    def section(self, name):
        return next((s for s in self.sections if s.name == name), None)

    def section_at(self, rva):
        return next((s for s in self.sections if s.rva <= rva < s.rva + max(s.vsize, s.rawsize)), None)

    def read(self, rva, n):
        s = self.section_at(rva)
        if not s:
            raise ValueError(f"RVA 0x{rva:X} is outside the image's sections")
        off = rva - s.rva
        return bytes(s.data[off:off + n])

    @property
    def is_dll(self):
        return bool(self.characteristics & 0x2000)

    def _string(self, rva, limit=512):
        data = self.read(rva, limit)
        return data.split(b"\0", 1)[0].decode("ascii", "replace")

    def exports(self):
        """The names of the functions it exports (a DLL's), as a set."""
        rva, size = self.dirs[0] if self.dirs else (0, 0)
        if not size:
            return set()
        count = struct.unpack_from("<I", self.read(rva + 24, 4))[0]    # NumberOfNames
        table = struct.unpack_from("<I", self.read(rva + 32, 4))[0]    # AddressOfNames
        return {self._string(r) for r in struct.unpack_from(f"<{count}I", self.read(table, 4 * count))} if count else set()

    def imports(self):
        """The names of the DLLs it imports from, as written ("UE4SS.dll")."""
        rva, size = self.dirs[1] if len(self.dirs) > 1 else (0, 0)
        out = []
        for i in range(size // 20):
            name = struct.unpack_from("<I", self.read(rva + 20 * i + 12, 4))[0]
            if not name:
                break
            out.append(self._string(name))
        return out

    @property
    def aslr(self):
        """Whether Windows moves it at every launch (DYNAMIC_BASE, and its relocations kept)."""
        return bool(self.dll_characteristics & 0x40) and self.dirs[5][1] > 0

    def fingerprint(self):
        """What tells one build of the exe from another: its link time, size and a hash of its code."""
        return {"size": len(self.raw), "timestamp": self.timestamp, "size_of_image": self.size_of_image,
                "text_sha1": hashlib.sha1(self.text.data).hexdigest()}

    def _pdata(self):
        """[(begin, end, unwind info RVA)] of .pdata's entries, sorted."""
        if self._entries is None:
            rva, size = self.dirs[3] if len(self.dirs) > 3 else (0, 0)
            data = self.read(rva, size) if size else b""
            out = []
            for i in range(0, size - 11, 12):
                b, e, u = struct.unpack_from("<III", data, i)
                if b and e > b:
                    out.append((b, e, u))
            out.sort()
            self._entries = out
        return self._entries

    def functions(self):
        """[(begin RVA, end RVA)] of .pdata's entries (every function with unwind data: nearly all of them).
        One function can have several: see whole_functions()."""
        if self._functions is None:
            self._functions = [(b, e) for b, e, _ in self._pdata()]
        return self._functions

    def _continues(self, unwind):
        """The begin of the entry an entry continues, from its unwind info (UNW_FLAG_CHAININFO, or an
        unwind RVA with its low bit set, which points at that entry itself), or None for a first part."""
        if unwind & 1:
            return struct.unpack("<I", self.read(unwind & ~1, 4))[0]
        head = self.read(unwind, 4)
        if len(head) < 4:   # in a section's zero-filled tail, which the file doesn't hold: no unwind info
            return None
        if not (head[0] >> 3) & UNW_FLAG_CHAININFO:
            return None
        codes = head[2] + (head[2] & 1)                 # unwind codes are 2 bytes, padded to an even count
        return struct.unpack("<I", self.read(unwind + 4 + 2 * codes, 4))[0]

    def whole_functions(self):
        """[(begin, end)] of whole functions. MSVC gives a function that saves registers in stages
        (shrink-wrapping) several .pdata entries: the first with the prologue, then chained ones
        (UNW_FLAG_CHAININFO), each saying which entry it continues. They come right after it (all 69,628
        such functions in build 26184573's exe do), so a whole function is its first part's begin to its
        last part's end (a part can continue one placed after it, as long as they're all together). A part
        that isn't next to the rest stays a function of its own."""
        if self._whole is None:
            continues = {}   # an entry's begin -> the begin of the entry it continues
            for b, _, u in self._pdata():
                try:
                    cont = self._continues(u)
                except (ValueError, struct.error):   # unwind info outside the image: taken as a first part
                    cont = None
                if cont is not None and cont != b:
                    continues[b] = cont

            def first(b):
                for _ in range(64):   # chains are short; a loop in broken data stops here
                    if b not in continues:
                        break
                    b = continues[b]
                return b
            out, last = [], None
            for b, e, _ in self._pdata():
                root = first(b)
                if out and out[-1][1] == b and root == last:
                    out[-1] = (out[-1][0], e)
                else:
                    out.append((b, e))
                    last = root
            self._whole = out
        return self._whole

    def function_at(self, rva):
        """The (begin, end) of the whole function holding rva (whole_functions()), or None."""
        import bisect
        funcs = self.whole_functions()
        i = bisect.bisect_right(funcs, (rva, 1 << 40)) - 1
        if i >= 0 and funcs[i][0] <= rva < funcs[i][1]:
            return funcs[i]
        return None

    def relocations(self):
        """The RVAs that hold absolute 64-bit addresses (patched when ASLR moves the image), as a set."""
        if self._relocs is None:
            rva, size = self.dirs[5]
            data = self.read(rva, size) if size else b""
            out, p = set(), 0
            while p + 8 <= len(data):
                page, block = struct.unpack_from("<II", data, p)
                if block < 8:
                    break
                for i in range(p + 8, p + block, 2):
                    entry = struct.unpack_from("<H", data, i)[0]
                    if entry >> 12 == IMAGE_REL_BASED_DIR64:
                        out.add(page + (entry & 0xFFF))
                p += block
            self._relocs = out
        return self._relocs


def game_exe(cfg):
    """The game's exe, from wcmods' config; None when the game isn't found."""
    from ..config import EXE_NAME
    if not cfg.game_dir:
        return None
    path = os.path.join(cfg.win64_dir, EXE_NAME)
    return path if os.path.isfile(path) else None
