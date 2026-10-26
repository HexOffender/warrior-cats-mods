"""Read Unreal reflection data (UHT tables) out of the game's exe: property offsets and enum values.

usage:
  uht.py <exe> props <PropertyName> [more names...]   the property tables around each name: every
                                                        property's name, generator flags and offset
  uht.py <exe> enum <EnumName>                          an enum's names and values, e.g. ECharacterTrait

UHT's property tables (FPropertyParamsBase) survive in the exe: name pointer at +0, RepNotify
pointer at +8, flags (u64) at +16, generator flags (u8) at +24, array dimension (u16) at +48 and
offset (u16) at +50. A property's table sits next to its struct's other properties, so finding a
pointer to one name finds them all. Enum tables are {const char* name, int64 value} pairs.
See docs/reverse-engineering.md.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # the repository, for wcmods
from wcmods.exe import pe  # noqa: E402


class Exe:
    """The exe's bytes and addresses, on wcmods.pe.Image: `data` is the whole file, `base` the image base,
    va(offset) and off(va) turn file offsets into virtual addresses and back."""

    def __init__(self, path):
        self.image = pe.Image(path)
        self.data = self.image.raw
        self.base = self.image.image_base
        self.sections = [(s.vsize, s.rva, s.rawsize, s.raw) for s in self.image.sections]

    def va(self, off):
        for s in self.image.sections:
            if s.raw <= off < s.raw + s.rawsize:
                return self.base + s.rva + off - s.raw
        return None

    def off(self, va):
        r = va - self.base
        for s in self.image.sections:
            if s.rva <= r < s.rva + s.rawsize:
                return s.raw + r - s.rva
        return None

    def cstr(self, va):
        o = self.off(va)
        if o is None:
            return None
        end = self.data.find(b"\0", o, o + 96)
        text = self.data[o:end]
        return text.decode() if text and all(32 <= c < 127 for c in text) else None

    def pointers_to(self, text):
        """Addresses holding a pointer to the string `text` (whole strings only)."""
        out = []
        for m in re.finditer(re.escape(text.encode()) + b"\0", self.data):
            if m.start() and self.data[m.start() - 1] != 0:
                continue
            target = self.va(m.start())
            out += [p.start() for p in re.finditer(re.escape(struct.pack("<Q", target)), self.data)]
        return out


def props(exe, names, window=0x800):
    for name in names:
        for p in exe.pointers_to(name):
            print(f"== {name}: property table entry at {exe.va(p):#x}")
            for q in range(p - window, p + window, 8):
                t = exe.cstr(struct.unpack_from("<Q", exe.data, q)[0])
                if t and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", t) and len(t) > 1:
                    gen = exe.data[q + 24]
                    dim, offset = struct.unpack_from("<HH", exe.data, q + 48)
                    print(f"  {exe.va(q):#x} {t:40s} gen={gen:#04x} dim={dim} offset={offset:#x}")


def enum(exe, name):
    prefix = name + "::"
    for m in re.finditer(re.escape(prefix.encode()), exe.data):
        end = exe.data.find(b"\0", m.start())
        full = exe.data[m.start():end].decode(errors="replace")
        hits = exe.pointers_to(full)
        if not hits:
            continue
        q = hits[0]
        while (exe.cstr(struct.unpack_from("<Q", exe.data, q - 16)[0]) or "").startswith(prefix):
            q -= 16
        while (exe.cstr(struct.unpack_from("<Q", exe.data, q)[0]) or "").startswith(prefix):
            print(exe.cstr(struct.unpack_from("<Q", exe.data, q)[0]), struct.unpack_from("<q", exe.data, q + 8)[0])
            q += 16
        return
    print(f"no enum table found for {name}")


if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[2] not in ("props", "enum"):
        sys.exit(__doc__)
    e = Exe(sys.argv[1])
    if sys.argv[2] == "props":
        props(e, sys.argv[3:])
    else:
        enum(e, sys.argv[3])
