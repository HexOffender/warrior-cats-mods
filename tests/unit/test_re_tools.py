"""The reverse-engineering scripts under tools/re/: memscan's search on a fake process (a list of regions and
a read function, no real process opened) and xrefs on a tiny exe built here."""
import importlib.util
import pathlib
import random
import struct

import pytest

RE = pathlib.Path(__file__).resolve().parents[2] / "tools" / "re"


def load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", RE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


memscan = load("memscan")
xrefs = load("xrefs")


# --- memscan ---------------------------------------------------------------------------------------------

class Memory:
    """A fake process: {base: bytes} readable regions. A read that runs into unreadable memory comes back
    empty, as ReadProcessMemory's does for a read whose readable part is under 56 KB."""

    def __init__(self, regions, short=()):
        self.data = sorted(regions.items())
        self.short = dict(short)   # {address: n}: a read starting there gets only n bytes (memory freed meanwhile)
        self.reads = []

    def regions(self):
        return [(base, len(data), 0x20000, 0x04) for base, data in self.data]

    def readable(self, addr, n):
        pos = addr
        for base, data in self.data:
            if base <= pos < base + len(data):
                pos = min(addr + n, base + len(data))
        return pos >= addr + n

    def read(self, addr, n):
        self.reads.append((addr, n))
        if not self.readable(addr, n):
            return b""
        out, pos = b"", addr
        for base, data in self.data:   # across regions that touch, as a real read would go
            if base <= pos < base + len(data):
                take = min(addr + n, base + len(data)) - pos
                out += data[pos - base:pos - base + take]
                pos += take
        return out[:self.short.get(addr, n)]

    def scan(self, patterns, chunk=16 << 20):
        return memscan.scan(self.regions(), self.read, patterns, chunk)


def addresses(hits):
    return [h[0] for h in hits]


def test_memscan_finds_a_pattern_in_a_lonely_region():
    """A region with unreadable memory after it: the old scan read 64 bytes past its end, got nothing
    back, and never searched it."""
    page = bytearray(4096)
    page[100:104] = page[4092:4096] = b"\xde\xad\xbe\xef"
    mem = Memory({0x10000: bytes(page)})
    hits = mem.scan({"m": b"\xde\xad\xbe\xef"})["m"]
    assert hits == [(0x10064, 0x10000, 4096, 0x20000, 0x04), (0x10ffc, 0x10000, 4096, 0x20000, 0x04)]
    assert all(mem.readable(addr, n) for addr, n in mem.reads)   # no read ran past the region


def test_memscan_finds_a_pattern_across_two_chunks():
    data = bytearray(3 * 4096)
    data[4096 - 3:4096 + 5] = b"ACROSS!!"
    data[2 * 4096 - 8:2 * 4096] = b"ACROSS!!"   # the end of the second chunk: found once, not again with the third
    mem = Memory({0x20000: bytes(data)})
    assert addresses(mem.scan({"m": b"ACROSS!!"}, chunk=4096)["m"]) == [0x20000 + 4093, 0x20000 + 2 * 4096 - 8]
    assert all(n == 4096 for _, n in mem.reads)


def test_memscan_finds_a_pattern_across_two_regions_that_touch():
    """Reported once, with the region it starts in."""
    first, second = bytearray(4096), bytearray(4096)
    first[-3:] = b"SEA"
    second[:3] = b"MS!"
    mem = Memory({0x30000: bytes(first), 0x31000: bytes(second)})
    hits = mem.scan({"m": b"SEAMS!"})["m"]
    assert hits == [(0x30ffd, 0x30000, 4096, 0x20000, 0x04)]


def test_memscan_doesnt_join_regions_across_a_gap():
    first, second = bytearray(4096), bytearray(4096)
    first[-3:] = b"SEA"
    second[:3] = b"MS!"
    mem = Memory({0x30000: bytes(first), 0x32000: bytes(second)})
    assert mem.scan({"m": b"SEAMS!"})["m"] == []


def test_memscan_starts_afresh_after_a_short_read():
    """A chunk that comes back short is searched as far as it goes, and nothing is joined across the gap."""
    data = bytearray(3 * 4096)
    data[10:14] = b"KEEP"
    data[4096 - 2:4096 + 2] = b"SPLT"           # across the seam, but the first chunk came back short
    data[4096 + 50:4096 + 54] = b"KEEP"
    mem = Memory({0x40000: bytes(data)}, short={0x40000: 2000})
    hits = mem.scan({"k": b"KEEP", "s": b"SPLT"}, chunk=4096)
    assert addresses(hits["k"]) == [0x4000a, 0x41032] and hits["s"] == []


def test_memscan_rejects_an_empty_pattern():
    with pytest.raises(ValueError):
        memscan.scan([], lambda a, n: b"", {"m": b""})


def naive(regions, patterns):
    """Every occurrence, overlapping ones too, in each run of regions that touch."""
    hits = {label: [] for label in patterns}
    runs = []
    for base, data in sorted(regions.items()):
        if runs and runs[-1][0] + len(runs[-1][1]) == base:
            runs[-1][1] += data
        else:
            runs.append([base, bytearray(data)])
    for base, data in runs:
        for label, pat in patterns.items():
            i = data.find(pat)
            while i >= 0:
                hits[label].append(base + i)
                i = data.find(pat, i + 1)
    return {label: sorted(found) for label, found in hits.items()}


@pytest.mark.parametrize("seed", range(40))
def test_memscan_matches_a_plain_search(seed):
    """Random regions (some touching, some not) of a two-letter alphabet, so patterns overlap and cross every
    seam; any chunk size finds each occurrence once, with the region it starts in."""
    rng = random.Random(seed)
    regions, addr = {}, 0x1000
    for _ in range(rng.randint(1, 6)):
        size = rng.randint(1, 40)
        regions[addr] = bytes(rng.choice(b"ab") for _ in range(size))
        addr += size + rng.choice((0, 0, 1, 7))
    patterns = {f"p{i}": bytes(rng.choice(b"ab") for _ in range(rng.randint(1, 6))) for i in range(3)}
    want = naive(regions, patterns)
    for chunk in (1, 2, 3, 5, 16, 1 << 20):
        mem = Memory(regions)
        got = mem.scan(patterns, chunk=chunk)
        assert {label: addresses(h) for label, h in got.items()} == want, chunk
        for found in got.values():
            for at, base, size, _, _ in found:
                assert base <= at < base + size and len(regions[base]) == size   # the region it starts in
        assert all(mem.readable(a, n) for a, n in mem.reads)


# --- xrefs -----------------------------------------------------------------------------------------------

BASE = 0x140000000
TEXT_VA, RDATA_VA = BASE + 0x1000, BASE + 0x2000


def tiny_exe(path, code, rdata):
    """A minimal 64-bit PE (what wcmods.exe.pe.Image reads): .text at RVA 0x1000, .rdata at RVA 0x2000."""
    head = bytearray(0x200)
    head[:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, 0x40)
    head[0x40:0x44] = b"PE\0\0"
    optsize = 112 + 16 * 8
    struct.pack_into("<HHIIIHH", head, 0x44, 0x8664, 2, 0, 0, 0, optsize, 0x22)
    opt = 0x58
    struct.pack_into("<HBBIII", head, opt, 0x20B, 14, 0, 0x200, 0x200, 0)   # magic, linker, code/data sizes
    struct.pack_into("<IIQII", head, opt + 16, 0x1000, 0x1000, BASE, 0x1000, 0x200)   # entry, code base, image base, alignments
    struct.pack_into("<II", head, opt + 56, 0x3000, 0x200)   # size of image, of headers
    struct.pack_into("<I", head, opt + 108, 16)   # data directories (all empty)
    sections = [(b".text", 0x1000, 0x200, code, 0x60000020), (b".rdata", 0x2000, 0x400, rdata, 0x40000040)]
    for i, (name, rva, raw, data, flags) in enumerate(sections):
        struct.pack_into("<8sIIIIIIHHI", head, opt + optsize + 40 * i, name, 0x200, rva, 0x200, raw, 0, 0, 0, 0, flags)
    image = bytearray(0x600)
    image[:0x200] = head
    image[0x200:0x200 + len(code)] = code
    image[0x400:0x400 + len(rdata)] = rdata
    path.write_bytes(bytes(image))
    return path


def rip(prefix, opcode, modrm, at, target):
    """A RIP-relative instruction at `at` (an offset in .text) whose operand is `target` (an offset in .rdata)."""
    return bytes([prefix, opcode, modrm]) + struct.pack("<i", RDATA_VA + target - (TEXT_VA + at + 7))


# .rdata: (offset, bytes)
RDATA = [
    (0x10, b"Turn\0"),                         # "Turn" itself
    (0x18, b"TurnBasedCombatComponent\0"),     # starts with "Turn"
    (0x38, b"EndTurn\0"),                      # ends with it; nothing points at its "Turn"
    (0x48, b"\xff\xfeTurn\0"),                 # right after other data, no terminator in front
    (0x60, b"abc\0" + "Turn".encode("utf-16-le") + b"\0\0"),   # UTF-16 right after a narrow string's last character
    (0x70, b"\0" + "Turn".encode("utf-16-le") + b"\0\0"),      # UTF-16 at an odd address: not a string
    (0x80, b"\0Turn\0"),                       # nothing points at it
]
CODE = [   # (prefix, opcode, ModRM, target offset in .rdata)
    (0x48, 0x8D, 0x0D, 0x10),   # lea rcx, "Turn"
    (0x48, 0x8B, 0x05, 0x10),   # mov rax, the first eight bytes of "Turn"
    (0x4C, 0x8D, 0x05, 0x18),   # lea r8, "TurnBasedCombatComponent"
    (0x48, 0x8D, 0x15, 0x38),   # lea rdx, "EndTurn"
    (0x48, 0x8D, 0x0D, 0x4A),   # lea rcx, the "Turn" after other data
    (0x48, 0x8D, 0x0D, 0x64),   # lea rcx, L"Turn"
    (0x48, 0x8D, 0x0D, 0x71),   # lea rcx, the odd address
]


@pytest.fixture
def exe(tmp_path):
    rdata = bytearray(0x200)
    for off, data in RDATA:
        rdata[off:off + len(data)] = data
    code = b"".join(rip(p, o, m, 7 * i, t) for i, (p, o, m, t) in enumerate(CODE))
    code += b"\x48\x8d\x04\x24\xc3"   # lea rax,[rsp]; ret: not RIP-relative
    return tiny_exe(tmp_path / "tiny.exe", code, bytes(rdata))


def test_tiny_exe_is_an_image(exe):
    image = xrefs.pe.Image(str(exe))
    assert image.image_base == BASE and image.text.rva == 0x1000 and image.read(0x2010, 4) == b"Turn"


def test_xrefs_reports_a_lea_and_a_mov(exe):
    found = xrefs.find(str(exe), ["Turn"])["Turn"]
    assert found[0] == (RDATA_VA + 0x10, "ascii", [(TEXT_VA, "lea"), (TEXT_VA + 7, "mov")])


def test_xrefs_skips_the_head_of_a_longer_string(exe):
    """The bug `or True` left in: code that uses "TurnBasedCombatComponent" was reported for "Turn"."""
    found = xrefs.find(str(exe), ["Turn", "TurnBasedCombatComponent"])
    assert RDATA_VA + 0x18 not in [va for va, _, _ in found["Turn"]]
    assert found["TurnBasedCombatComponent"] == [(RDATA_VA + 0x18, "ascii", [(TEXT_VA + 14, "lea")])]


def test_xrefs_skips_the_tail_of_a_longer_string(exe):
    found = xrefs.find(str(exe), ["Turn", "EndTurn"])
    assert RDATA_VA + 0x3B not in [va for va, _, _ in found["Turn"]]
    assert found["EndTurn"] == [(RDATA_VA + 0x38, "ascii", [(TEXT_VA + 21, "lea")])]


def test_xrefs_keeps_strings_with_no_terminator_in_front(exe):
    """In the game's exe 1,485 of the 104,035 strings code points at follow other data, or a narrow string's
    last character, directly; dropping `or True` alone would have lost them."""
    found = {va: (enc, refs) for va, enc, refs in xrefs.find(str(exe), ["Turn"])["Turn"]}
    assert found[RDATA_VA + 0x4A] == ("ascii", [(TEXT_VA + 28, "lea")])
    assert found[RDATA_VA + 0x64] == ("utf16", [(TEXT_VA + 35, "lea")])


def test_xrefs_lists_every_whole_string(exe):
    """Also one nothing points at; not the odd-address UTF-16 or the tail of "EndTurn"."""
    found = xrefs.find(str(exe), ["Turn"])["Turn"]
    assert [(va - RDATA_VA, enc) for va, enc, _ in found] == [(0x10, "ascii"), (0x4A, "ascii"), (0x64, "utf16"),
                                                              (0x81, "ascii")]
    assert found[-1][2] == []


def test_xrefs_places_flags_a_possible_tail(exe):
    image = xrefs.pe.Image(str(exe))
    places = {va - RDATA_VA: inside for va, _, inside in xrefs.places(image, "Turn")}
    assert places == {0x10: False, 0x3B: True, 0x4A: False, 0x64: True, 0x81: False}


def test_xrefs_main(exe, capsys):
    xrefs.main([str(exe), "Turn", "Nowhere"])
    out = capsys.readouterr().out
    assert f"'Turn' (ascii @{RDATA_VA + 0x10:#x}): lea {TEXT_VA:#x}, mov {TEXT_VA + 7:#x}" in out
    assert f"'Turn' (ascii @{RDATA_VA + 0x81:#x}): none" in out
    assert "'Nowhere': not in the exe as a whole string" in out
