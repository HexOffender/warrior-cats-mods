"""The reverse-engineering scripts under tools/re/: memscan's search on a fake process (a list of regions and
a read function, no real process opened) and xrefs on a tiny exe built here."""
import importlib.util
import os
import pathlib
import random
import struct
import sys

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
    empty, as ReadProcessMemory's does for a read whose readable part is under 56 KB; with `partial`, it
    comes back with the readable part, as for a longer one (in whole 56 KB blocks there)."""

    def __init__(self, regions, short=(), partial=False):
        self.data = sorted(regions.items())
        self.short = dict(short)   # {address: n}: a read starting there gets only n bytes (memory freed meanwhile)
        self.partial = partial
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
        if not self.readable(addr, n) and not self.partial:
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
    """A chunk that comes back short is searched as far as it goes, and nothing is joined across the gap:
    the half of a pattern the short read ended with isn't joined to the half the next chunk starts with."""
    data = bytearray(3 * 4096)
    data[10:14] = b"KEEP"
    data[1998:2000] = b"SP"           # the last bytes the short read got
    data[4096:4098] = b"LT"           # the next chunk's first bytes
    data[4096 + 50:4096 + 54] = b"KEEP"
    mem = Memory({0x40000: bytes(data)}, short={0x40000: 2000})
    hits = mem.scan({"k": b"KEEP", "s": b"SPLT"}, chunk=4096)
    assert addresses(hits["k"]) == [0x4000a, 0x41032] and hits["s"] == []


def test_memscan_doesnt_join_a_short_read_to_the_next_region():
    first, second = bytearray(4096), bytearray(4096)
    first[1998:2000] = b"SP"
    second[:2] = b"LT"
    mem = Memory({0x50000: bytes(first), 0x51000: bytes(second)}, short={0x50000: 2000})
    assert mem.scan({"s": b"SPLT"})["s"] == []


@pytest.mark.parametrize("partial", [False, True])
def test_memscan_with_the_old_scan_beside_it(partial):
    """scan_with_old() reads each chunk the old way too (64 bytes past its end, all or nothing): the old scan
    finds what is followed by readable memory, even across regions that touch, each once, and misses the
    last chunk of a region followed by unreadable memory, which it reads as empty (also when Windows
    reports part of that read as copied: the old read() threw the failed read away)."""
    first, second = bytearray(3 * 4096), bytearray(4096)
    first[100:104] = b"\xde\xad\xbe\xef"
    first[4096 + 10:4096 + 14] = b"\xde\xad\xbe\xef"    # in the 64 bytes the old scan read past the first chunk
    first[-2:], second[:2] = b"\xde\xad", b"\xbe\xef"   # across the regions' seam
    second[-4:] = b"\xde\xad\xbe\xef"                   # unreadable memory after it
    mem = Memory({0x60000: bytes(first), 0x63000: bytes(second)}, partial=partial)
    hits, old, empty = memscan.scan_with_old(mem.regions(), mem.read, {"m": b"\xde\xad\xbe\xef"}, chunk=4096)
    assert addresses(hits["m"]) == [0x60064, 0x6100a, 0x62ffe, 0x63ffc]
    assert old == {"m": [0x60064, 0x6100a, 0x62ffe]}
    assert empty == [(0x63000, 4096)]


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


def without_short_reads(regions, chunk, short):
    """The pieces of `regions` a scan in `chunk`s gets when the reads in `short` ({address: n}) come back
    with only n bytes: the bytes a short read didn't get are a gap, as between regions that don't touch."""
    pieces = {}
    for base, data in regions.items():
        start = 0
        for off in range(0, len(data), chunk):
            got = short.get(base + off)
            if got is not None:
                if off + got > start:
                    pieces[base + start] = data[start:off + got]
                start = off + min(chunk, len(data) - off)
        if len(data) > start:
            pieces[base + start] = data[start:]
    return pieces


@pytest.mark.parametrize("seed", range(40))
def test_memscan_matches_a_plain_search(seed):
    """Random regions (some touching, some not) of a two-letter alphabet, so patterns overlap and cross every
    seam; any chunk size finds each occurrence once, with the region it starts in. Then again with a few
    reads coming back short, against a plain search that splits the memory where those reads stopped."""
    rng = random.Random(seed)
    regions, addr = {}, 0x1000
    for _ in range(rng.randint(1, 6)):
        size = rng.randint(1, 40)
        regions[addr] = bytes(rng.choice(b"ab") for _ in range(size))
        addr += size + rng.choice((0, 0, 1, 7))
    patterns = {f"p{i}": bytes(rng.choice(b"ab") for _ in range(rng.randint(1, 6))) for i in range(3)}
    want = naive(regions, patterns)
    for chunk in (1, 2, 3, 5, 16, 1 << 20):
        starts = {base + off: min(chunk, len(data) - off) for base, data in regions.items()
                  for off in range(0, len(data), chunk)}   # each read's address and size
        cut_at = rng.sample(sorted(starts), min(len(starts), rng.randint(1, 3)))
        short = {at: rng.randrange(starts[at]) for at in cut_at}   # 0 to one byte short of the whole read
        for cut, expect in (({}, want), (short, naive(without_short_reads(regions, chunk, short), patterns))):
            mem = Memory(regions, short=cut)
            got = mem.scan(patterns, chunk=chunk)
            assert {label: addresses(h) for label, h in got.items()} == expect, (chunk, cut)
            for found in got.values():
                for at, base, size, _, _ in found:
                    assert base <= at < base + size and len(regions[base]) == size   # the region it starts in
            assert sorted(a for a, _ in mem.reads) == sorted(starts)
            assert all(mem.readable(a, n) for a, n in mem.reads)


@pytest.mark.skipif(sys.platform != "win32", reason="reads this process's memory through kernel32")
def test_memscan_on_this_process(capsys):
    """The Windows side, on this test's own process (never the game): kernel32's signatures, Proc.regions()
    and Proc.read(). A marker in the last bytes of a page whose next page is PAGE_NOACCESS is found; the
    old scan's read 64 bytes past the page fails, so it read the page as empty."""
    import ctypes
    import ctypes.wintypes as wt
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)   # its own handle: memscan's signatures stay as they are
    k32.VirtualAlloc.restype = ctypes.c_void_p
    k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]
    k32.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, ctypes.POINTER(wt.DWORD)]
    k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wt.DWORD]
    MEM_RESERVE, MEM_RELEASE, MEM_PRIVATE, PAGE_READWRITE, page = 0x2000, 0x8000, 0x20000, 0x04, 4096
    base = k32.VirtualAlloc(None, 2 * page, memscan.MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    assert base, ctypes.get_last_error()
    try:
        assert k32.VirtualProtect(base + page, page, memscan.PAGE_NOACCESS, ctypes.byref(wt.DWORD()))
        marker = os.urandom(16)
        at = base + page - len(marker)
        ctypes.memmove(at, marker, len(marker))
        proc = memscan.Proc(os.getpid())
        lonely = (base, page, MEM_PRIVATE, PAGE_READWRITE)
        assert [r for r in proc.regions() if base <= r[0] < base + 2 * page] == [lonely]
        assert (at,) + lonely in proc.scan({"m": marker})["m"]
        assert proc.read(base, page)[-len(marker):] == marker
        partial = proc.read(base, 2 * page)   # runs into the unreadable page: what was copied, if anything
        assert len(partial) <= page and proc.read(base, page).startswith(partial)

        hits, old, empty = memscan.scan_with_old([lonely], proc.read, {"m": marker})
        assert hits["m"] == [(at,) + lonely] and old["m"] == [] and empty == [(base, page)]
        memscan.main([str(os.getpid()), f"m={marker.hex()}", "--old", "--context", "0", "--max", "1000000"])
        out = capsys.readouterr().out
        assert f"@{at:#x} region {base:#x}+{page:#x} type {MEM_PRIVATE:#x} prot {PAGE_READWRITE:#x}  " \
               f"(old: missed, in a chunk it read as empty)" in out
    finally:
        k32.VirtualFree(base, 0, MEM_RELEASE)


# --- xrefs -----------------------------------------------------------------------------------------------

BASE = 0x140000000
TEXT_VA, RDATA_VA = BASE + 0x1000, BASE + 0x2000


def tiny_exe(path, code, rdata, rdata_vsize=0x200):
    """A minimal 64-bit PE (what wcmods.exe.pe.Image reads): .text at RVA 0x1000, .rdata at RVA 0x2000,
    0x200 bytes of each in the file (.rdata `rdata_vsize` bytes in memory, the rest zero-filled)."""
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
    sections = [(b".text", 0x1000, 0x200, 0x200, code, 0x60000020),
                (b".rdata", 0x2000, rdata_vsize, 0x400, rdata, 0x40000040)]
    for i, (name, rva, vsize, raw, data, flags) in enumerate(sections):
        struct.pack_into("<8sIIIIIIHHI", head, opt + optsize + 40 * i, name, vsize, rva, 0x200, raw, 0, 0, 0, 0, flags)
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
    code += b"\0Turn\0"               # in the code section: not searched
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
    """In the game's exe 1,485 of the 104,041 strings (of 4 or more characters) code points at follow other
    data, or a narrow string's last character, directly; dropping `or True` alone would have lost them."""
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


def test_xrefs_skips_the_code_section(exe):
    """Only the data sections are searched: the "Turn" after the fixture's code isn't a place."""
    image = xrefs.pe.Image(str(exe))
    assert image.text.data.tobytes().find(b"\0Turn\0") > 0
    assert all(va >= RDATA_VA for va, _, _ in xrefs.places(image, "Turn"))
    assert all(va >= RDATA_VA for va, _, _ in xrefs.places(image, "Turn", prefix=True))


@pytest.mark.parametrize("vsize, whole", [(0x400, True), (0x200, False)])
def test_xrefs_at_the_end_of_a_section(tmp_path, vsize, whole):
    """A string whose last character is a section's last byte in the file ends with the section's zero fill
    when the section is bigger in memory than in the file, and isn't a whole string otherwise."""
    rdata = bytearray(0x200)
    rdata[-4:] = b"Tail"
    image = xrefs.pe.Image(str(tiny_exe(tmp_path / "end.exe", b"\xc3", bytes(rdata), rdata_vsize=vsize)))
    assert [va for va, _, _ in xrefs.places(image, "Tail")] == ([RDATA_VA + 0x1FC] if whole else [])


def test_xrefs_prefix_finds_strings_that_start_with_the_text(exe):
    """For keys built from a pattern (`Gameplay.Exploration.Level.` starts L"Gameplay.Exploration.Level.%d"):
    "Turn" as a prefix also finds "TurnBasedCombatComponent", but still not the odd-address UTF-16, or the
    "Turn" inside "EndTurn" that nothing points at."""
    found = {va - RDATA_VA: (enc, refs) for va, enc, refs in xrefs.find(str(exe), ["Turn"], prefix=True)["Turn"]}
    assert found[0x18] == ("ascii", [(TEXT_VA + 14, "lea")])
    assert sorted(found) == [0x10, 0x18, 0x4A, 0x64, 0x81]
    assert xrefs.find(str(exe), ["TurnBased"])["TurnBased"] == []
    assert [va - RDATA_VA for va, _, _ in xrefs.find(str(exe), ["TurnBased"], prefix=True)["TurnBased"]] == [0x18]


def test_xrefs_main(exe, capsys):
    xrefs.main([str(exe), "Turn", "Nowhere", "TurnBased"])
    out = capsys.readouterr().out
    assert f"'Turn' (ascii @{RDATA_VA + 0x10:#x}): lea {TEXT_VA:#x}, mov {TEXT_VA + 7:#x}" in out
    assert f"'Turn' (ascii @{RDATA_VA + 0x81:#x}): none" in out
    assert "'Nowhere': not in the exe as a whole string (or only inside longer ones)" in out
    assert "'TurnBased': not in the exe as a whole string (or only inside longer ones)" in out


def test_xrefs_main_with_prefix(exe, capsys):
    xrefs.main([str(exe), "--prefix", "TurnBased", "Nowhere"])
    out = capsys.readouterr().out
    assert f"  {RDATA_VA + 0x18:#x} ascii 'TurnBasedCombatComponent'\n" in out
    assert f"'TurnBasedCombatComponent' (ascii @{RDATA_VA + 0x18:#x}): lea {TEXT_VA + 14:#x}\n" in out
    assert "'Nowhere': no string in the exe starts with it (or only inside longer ones)" in out


def test_xrefs_string_at(exe):
    image = xrefs.pe.Image(str(exe))
    assert xrefs.string_at(image, RDATA_VA + 0x18, "ascii") == "TurnBasedCombatComponent"
    assert xrefs.string_at(image, RDATA_VA + 0x64, "utf16") == "Turn"
    assert xrefs.string_at(image, RDATA_VA + 0x18, "ascii", limit=4) == "Turn"
