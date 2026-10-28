"""Read Unreal reflection data (UHT tables) out of the game's exe: property offsets and enum values.

usage:
  uht.py <exe> props <PropertyName> [more names...]   the property tables around each name: every
                                                        property's name, generator flags and offset
  uht.py <exe> enum <EnumName>                          an enum's names and values, e.g. ECharacterTrait,
                                                        and where its table is
  uht.py <exe> lua                                      wcmods' Lua against the exe: every Game.enums list
                                                        and every enum number the Lua keeps as a fallback

UHT's property tables (FPropertyParamsBase) survive in the exe: name pointer at +0, RepNotify
pointer at +8, flags (u64) at +16, generator flags (u8) at +24, array dimension (u16) at +48 and
offset (u16) at +50. A property's table sits next to its struct's other properties, so finding a
pointer to one name finds them all. Enum tables are {const char* name, int64 value} pairs.
See docs/reverse-engineering.md.
"""
import glob
import os
import re
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)   # the repository, for wcmods
from wcmods.exe import pe  # noqa: E402


class Exe:
    """The exe's bytes and addresses, on wcmods.pe.Image: `data` is the whole file, `base` the image base,
    va(offset) and off(va) turn file offsets into virtual addresses and back. `image` stands in for the
    file (anything with raw, image_base and sections, as the tests' small fixtures have)."""

    def __init__(self, path=None, image=None):
        self.image = image if image is not None else pe.Image(path)
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


def enum_table(exe, name):
    """An enum's table in the exe: (the address of its first entry, [(name, value), ...] with the names as
    the table has them, "ECommands::NoCommand"), or (None, []) when no table has it. Found by its names'
    "<EnumName>::" prefix, which every enum class and namespaced enum has (all of the game's own); a plain
    enum's names (EInputEvent's IE_Pressed) have none, so it isn't found this way."""
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
        first, out = exe.va(q), []
        while (exe.cstr(struct.unpack_from("<Q", exe.data, q)[0]) or "").startswith(prefix):
            out.append((exe.cstr(struct.unpack_from("<Q", exe.data, q)[0]),
                        struct.unpack_from("<q", exe.data, q + 8)[0]))
            q += 16
        return first, out
    return None, []


def enum_values(exe, name):
    """An enum's values by name, without the "<EnumName>::" in front ({"NoCommand": 0, ...}), in the table's
    order; empty when the exe has no table for it."""
    _, table = enum_table(exe, name)
    return {full.split("::", 1)[1]: value for full, value in table}


def enum(exe, name):
    first, table = enum_table(exe, name)
    if first is None:
        print(f"no enum table found for {name}")
        return
    print(f"{name}: {len(table)} names, table at {first:#x} (RVA {first - exe.base:#x})")
    for full, value in table:
        print(full, value)


# A number the Lua keeps for an enum value, with the value named in its comment:
#   local INTERACT_COMMAND = 67   -- ECommands::Player_Interact in build 26184573, ...
#   local SHOWN, COLLAPSED = 4, 1   -- ESlateVisibility: SelfHitTestInvisible, Collapsed
_ONE = re.compile(r"^[ \t]*local[ \t]+\w+[ \t]*=[ \t]*(0[xX][0-9A-Fa-f]+|\d+)[ \t]*--[ \t]*(E\w+)::(\w+)", re.M)
_SEVERAL = re.compile(r"^[ \t]*local[ \t]+\w+(?:[ \t]*,[ \t]*\w+)+[ \t]*=[ \t]*(\d+(?:[ \t]*,[ \t]*\d+)+)[ \t]*--[ \t]*"
                      r"(E\w+):[ \t]*(\w+(?:[ \t]*,[ \t]*\w+)*)", re.M)


def lua_constants(text):
    """The enum numbers a Lua file keeps, as [(enum, name, number, line)], from the two comment forms above."""
    out = []
    for m in _ONE.finditer(text):
        out.append((m.group(2), m.group(3), int(m.group(1), 0), text.count("\n", 0, m.start()) + 1))
    for m in _SEVERAL.finditer(text):
        numbers = [int(n) for n in m.group(1).split(",") if n.strip()]
        names = [n.strip() for n in m.group(3).split(",")]
        if len(numbers) == len(names):
            line = text.count("\n", 0, m.start()) + 1
            out += [(m.group(2), name, n, line) for name, n in zip(names, numbers)]
    return out


def check_lua(exe, enums=None, sources=None):
    """wcmods' Lua against the exe. Every Game.enums list (wcmods/game.py ENUMS, the fallback when the game's
    own enum can't be read in game) must be its enum's names in the exe's order, numbered from 0; every enum
    number a Lua file keeps (lua_constants) must be that name's value. `sources` maps a file name to its text
    (wcmods/lua/*.lua by default). Returns [(what, ok, note)]: ok is None for a number whose enum has no table
    to check it against (an engine flag set such as EInternalObjectFlags, which isn't reflected)."""
    if enums is None:
        from wcmods import game
        enums = game.ENUMS
    if sources is None:
        sources = {}
        for path in sorted(glob.glob(os.path.join(REPO, "wcmods", "lua", "*.lua"))):
            with open(path, encoding="utf-8") as f:
                sources[os.path.basename(path)] = f.read()
    out, cache = [], {}

    def values(name):
        if name not in cache:
            cache[name] = enum_values(exe, name)
        return cache[name]

    for key, path, names in enums:
        name = path.rsplit(".", 1)[-1]
        got = values(name)
        want = {n: i for i, n in enumerate(names)}
        if not got:
            out.append((f"Game.enums.{key} ({name})", False, "no enum table in the exe"))
        elif got == want and list(got) == names:
            out.append((f"Game.enums.{key} ({name})", True, f"{len(names)} names"))
        else:   # as WCModsGame says it in the game's log when the game's enum isn't build 26184573's
            diff = []
            for n in dict.fromkeys(names + list(got)):
                if n not in got:
                    diff.append(f"{n} gone")
                elif n not in want:
                    diff.append(f"{n} {got[n]} new")
                elif got[n] != want[n]:
                    diff.append(f"{n} {want[n]} -> {got[n]}")
            out.append((f"Game.enums.{key} ({name})", False, ", ".join(diff) or "the same names in another order"))
    for file, text in sources.items():
        for name, member, number, line in lua_constants(text):
            got = values(name)
            what = f"{file}:{line} {name}::{member} = {number}"
            if not got:
                out.append((what, None, "not checked: no enum table in the exe (not reflected, or a plain enum)"))
            elif member not in got:
                out.append((what, False, f"the exe's {name} has no {member}"))
            else:
                out.append((what, got[member] == number, f"the exe has {got[member]}"))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[2] not in ("props", "enum", "lua") or (sys.argv[2] != "lua" and len(sys.argv) < 4):
        sys.exit(__doc__)
    e = Exe(sys.argv[1])
    if sys.argv[2] == "props":
        props(e, sys.argv[3:])
    elif sys.argv[2] == "enum":
        enum(e, sys.argv[3])
    else:
        results = check_lua(e)
        for what, ok, note in results:
            print(f"{'ok  ' if ok else '--  ' if ok is None else 'DIFF'} {what}: {note}")
        checked = [ok for _, ok, _ in results if ok is not None]
        print(f"{sum(checked)} of {len(checked)} match the exe ({len(results) - len(checked)} not checked)")
        sys.exit(0 if all(checked) else 1)
