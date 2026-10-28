"""Game update signatures (wcmods/exe/pe.py, signatures.py), without the game:
- a PE built by hand whose functions have chained unwind entries, as MSVC gives a function that saves
  registers in stages: pe.Image.function_at answers the whole function, not its first 10 bytes;
- which accesses can be a member's: none through a stack address or a global's pointer, none wider than
  the member (a vtable slot at the same offset);
- the level component's signatures as committed: code laid out the way their patterns say finds all eight
  members where they were on an exe they weren't made on, and follows them when the update moves them;
- make() refuses a class it found no signature for, instead of shipping one a game update switches off.
The same on the installed game's exe is `python wcmods.py selftest` (docs/reverse-engineering.md, "Game
updates", has what was run on build 26184573)."""
import copy
import struct
from types import SimpleNamespace

import pytest

from wcmods.exe import pe, signatures, x64

LEVEL = "/Script/SwtAdventure.SwtAdventureLevelComponent"
TEXT = 0x1000


# ---------- a PE built by hand ----------
def build_pe(sections, dirs):
    """A PE32+ file: sections [(name, rva, data)], data directories {index: (rva, size)}."""
    nsec, optsize = len(sections), 240
    raw = 0x400
    headers, body = [], b""
    for name, rva, data in sections:
        size = -(-len(data) // 0x200) * 0x200
        headers.append(struct.pack("<8sIIII12xI", name.encode(), len(data), rva, size, raw, 0x60000020))
        body += data + b"\0" * (size - len(data))
        raw += size
    opt = bytearray(optsize)
    struct.pack_into("<H", opt, 0, 0x20B)
    struct.pack_into("<Q", opt, 24, 0x140000000)
    struct.pack_into("<II", opt, 32, 0x1000, 0x200)
    struct.pack_into("<I", opt, 56, max(rva for _, rva, _ in sections) + 0x1000)
    struct.pack_into("<I", opt, 108, 16)
    for i, (rva, size) in dirs.items():
        struct.pack_into("<II", opt, 112 + 8 * i, rva, size)
    head = bytearray(0x40)
    head[:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, 0x40)
    head += b"PE\0\0" + struct.pack("<HHIIIHH", 0x8664, nsec, 0, 0, 0, optsize, 0x22) + opt + b"".join(headers)
    return bytes(head) + b"\0" * (0x400 - len(head)) + body


def unwind(codes=0, chained=None):
    """UNWIND_INFO: version 1, `codes` unwind codes (padded to an even count), then the RUNTIME_FUNCTION it
    continues when chained (UNW_FLAG_CHAININFO)."""
    head = bytes([1 | (pe.UNW_FLAG_CHAININFO << 3 if chained else 0), 0, codes, 0])
    out = head + b"\0\0" * (codes + (codes & 1))
    return out + (struct.pack("<III", *chained) if chained else b"")


def test_chained_unwind_entries_make_one_function(tmp_path):
    rdata, pdata = 0x2000, 0x3000
    infos = bytearray()

    def info(codes=0, chained=None):
        at = rdata + len(infos)
        infos.extend(unwind(codes, chained))
        infos.extend(b"\0" * (-len(infos) % 4))
        return at

    # A function in three parts (the last with an odd number of unwind codes), one on its own after a gap,
    # one whose middle part continues a part placed after it (as 0x1412602D0 does in the game's exe), and
    # one continued through an unwind RVA with its low bit set (pointing at the entry it continues).
    a = (0x1000, 0x1010, info())
    b = (0x1010, 0x1020, info(2, a))
    c = (0x1020, 0x1030, info(1, b))
    d = (0x1040, 0x1050, info())
    r = (0x1050, 0x1058, info())
    y = (0x1060, 0x1068, info(0, r))
    x = (0x1058, 0x1060, info(0, y))
    g = (0x1070, 0x1078, info())
    entries = [a, b, c, d, r, x, y, g]
    h = (0x1078, 0x1080, (pdata + 12 * entries.index(g)) | 1)
    entries.append(h)
    table = b"".join(struct.pack("<III", *e) for e in entries)
    path = tmp_path / "game.exe"
    path.write_bytes(build_pe([(".text", 0x1000, b"\xCC" * 0x100), (".rdata", rdata, bytes(infos)),
                               (".pdata", pdata, table)], {3: (pdata, len(table))}))
    img = pe.Image(str(path))
    assert len(img.functions()) == 9      # .pdata's entries, as they are
    assert img.whole_functions() == [(0x1000, 0x1030), (0x1040, 0x1050), (0x1050, 0x1068), (0x1070, 0x1080)]
    assert img.function_at(0x1025) == (0x1000, 0x1030)
    assert img.function_at(0x105A) == (0x1050, 0x1068)
    assert img.function_at(0x107C) == (0x1070, 0x1080)
    assert img.function_at(0x1035) is None


# ---------- which accesses can be a member's ----------
def finder_for(code):
    """What _foreign and _access read of a Finder, over `code` at RVA TEXT, and its instructions."""
    finder = SimpleNamespace(tdata=code, text=SimpleNamespace(rva=TEXT))
    return finder, [(TEXT + p, ins) for p, ins in x64.instructions(code, 0, len(code))]


def test_accesses_through_the_stack_or_a_global_are_not_members():
    code = bytes.fromhex(
        "48 8B D9"                  # mov rbx, rcx           (this)
        "48 8B 3D 00 10 00 00"      # mov rdi, [rip+...]     a global's pointer
        "8B 97 54 01 00 00"         # mov edx, [rdi+0x154]   not this one's (a singleton's +0x154)
        "8B 8B 54 01 00 00"         # mov ecx, [rbx+0x154]   this one's
        "48 8D AC 24 00 FF FF FF"   # lea rbp, [rsp-0x100]   a frame pointer
        "8B 85 68 01 00 00"         # mov eax, [rbp+0x168]   a stack slot
        "48 8B C5"                  # mov rax, rbp           still the stack
        "8B 80 68 01 00 00"         # mov eax, [rax+0x168]   a stack slot
        "E8 00 00 00 00"            # call                   rax is what it returned now
        "8B 80 68 01 00 00"         # mov eax, [rax+0x168]   could be
        "48 8B 3F"                  # mov rdi, [rdi]         loaded through the global: anything
        "8B 87 54 01 00 00"         # mov eax, [rdi+0x154]   could be
        "C3")
    finder, insns = finder_for(code)
    foreign = signatures._foreign(finder, insns)
    at_members = [i for i, (_, ins) in enumerate(insns) if ins.memory() and ins.disp in (0x154, 0x168)]
    assert at_members == [2, 3, 5, 7, 9, 11]
    assert [i for i in at_members if i in foreign] == [2, 5, 7]


def test_an_access_wider_than_the_member_is_not_it():
    code = bytes.fromhex(
        "FF 90 C8 01 00 00"         # call [rax+0x1C8]        a vtable slot, not a float at +0x1C8
        "48 8B 90 08 01 00 00"      # mov rdx, [rax+0x108]    a pointer, not a byte at +0x108
        "0F B6 83 08 01 00 00"      # movzx eax, byte [rbx+0x108]
        "F3 0F 10 83 C8 01 00 00"   # movss xmm0, [rbx+0x1C8]
        "48 8D 93 20 01 00 00"      # lea rdx, [rbx+0x120]    its address, passed on
        "8B 83 20 01 00 00"         # mov eax, [rbx+0x120]
        "F2 0F 10 83 20 01 00 00")  # movsd xmm0, [rbx+0x120] 8 bytes: two members at once, or another field
    finder, insns = finder_for(code)
    offsets = {0x1C8: 4, 0x108: 1, 0x120: 4}
    assert [signatures._access(finder, r, ins, offsets) for r, ins in insns] == \
        [False, False, True, True, True, True, False]


# ---------- the level component's signatures, as committed ----------
def code_for(entry, shift=0):
    """Code laid out as a class's site patterns say, one after another between int3s: wildcards zero, and
    each capture holding the member's offset (moved by `shift`)."""
    out = bytearray(b"\xCC" * 16)
    for site in entry["sites"]:
        part = bytearray(0 if b is None else b for b in signatures._unhex(site["pattern"]))
        for at, was in site["captures"].items():
            struct.pack_into("<i", part, int(at), was + shift)
        out += part + b"\xCC" * 16
    return bytes(out)


def check_on(monkeypatch, code, sigs, size):
    """signatures.check() over `code`, as the code of every class in `sigs` (each `size` bytes), on an exe
    that isn't the one the signatures were made on."""
    text = SimpleNamespace(rva=TEXT, data=memoryview(code))

    class Image:
        def __init__(self, path):
            self.text, self.image_base = text, 0x140000000

        def relocations(self):
            return set()

        def fingerprint(self):
            return {"size": 1, "timestamp": 0, "size_of_image": 0, "text_sha1": "another build"}

        def function_at(self, rva):
            return (TEXT, TEXT + len(code)) if TEXT <= rva < TEXT + len(code) else None

    class Finder(signatures.Finder):
        def find_class(self, name):
            info = signatures.ClassInfo(name)
            info.size, info.functions = size, [(TEXT, TEXT + len(code))]
            info.super_class = info.static_class = info.class_pointer = None
            return info

        def class_code(self, infos):
            return [i for i in infos if i]

    monkeypatch.setattr(signatures.pe, "Image", Image)
    monkeypatch.setattr(signatures, "Finder", Finder)
    return signatures.check("game.exe", sigs, log=lambda m: None)


def level_only():
    sigs = signatures.load()
    return {"made_on": sigs["made_on"], "classes": {LEVEL: copy.deepcopy(sigs["classes"][LEVEL])}}


def test_the_level_component_has_signatures_for_every_member():
    entry = signatures.load()["classes"][LEVEL]
    votes = {}
    for site in entry["sites"]:
        for was in site["captures"].values():
            votes[was] = votes.get(was, 0) + 1
    # Every member, and twice at least: a move is followed on the word of two sites.
    assert {n: votes.get(o, 0) >= signatures.MIN_MOVE_VOTES for n, o in entry["fields"].items()} == \
        {n: True for n in entry["fields"]}
    assert entry["anchors"] and all(a["pattern"] for a in entry["anchors"])


def test_the_level_component_is_found_on_another_build(monkeypatch):
    sigs = level_only()
    entry = sigs["classes"][LEVEL]
    res = check_on(monkeypatch, code_for(entry), sigs, entry["size"])
    fields = res["classes"][LEVEL]["fields"]
    assert not res["same_exe"]
    assert {n: f["status"] for n, f in fields.items()} == {n: "same" for n in entry["fields"]}
    assert all(res["offsets"][f"{LEVEL}:{n}"] == o for n, o in entry["fields"].items())
    assert res["same"]


def test_the_level_component_is_followed_when_it_moves(monkeypatch):
    sigs = level_only()
    entry = sigs["classes"][LEVEL]
    res = check_on(monkeypatch, code_for(entry, shift=4), sigs, entry["size"])
    fields = res["classes"][LEVEL]["fields"]
    assert {n: (f["status"], f["now"]) for n, f in fields.items()} == \
        {n: ("moved", o + 4) for n, o in entry["fields"].items()}


def test_before_the_level_component_had_signatures_it_was_lost(monkeypatch):
    """What every game update did before: no sites, so nothing to find it by on another exe."""
    sigs = level_only()
    sigs["classes"][LEVEL]["sites"] = []
    res = check_on(monkeypatch, b"\xCC" * 64, sigs, sigs["classes"][LEVEL]["size"])
    assert {f["status"] for f in res["classes"][LEVEL]["fields"].values()} == {"lost"}


def test_every_class_has_signatures_and_the_build_they_were_made_on():
    from wcmods.exe import gamebuild
    sigs = signatures.load()
    assert sigs["made_on"]["build"] == gamebuild.VERIFIED_BUILD
    assert [c for c, e in sigs["classes"].items() if not e["sites"]] == []


# ---------- make() ----------
def fake_maker(monkeypatch, unsigned=()):
    """make() over a fake exe whose every class is found, and gets a site unless its short name is in
    `unsigned`."""
    class Image:
        def __init__(self, path):
            pass

        def fingerprint(self):
            return {"text_sha1": "x"}

        def function_at(self, rva):
            return (rva, rva + 16)

    class Finder:
        def __init__(self, img):
            self.img = img

        def find_class(self, short):
            info = signatures.ClassInfo(short)
            info.size, info.functions, info.super_class, info.static_class = 0x400, [(TEXT, TEXT + 16)], None, None
            return info

        def class_code(self, infos):
            return list(infos)

        def function_signature(self, begin):
            return [0x90] * 20

    def sites(finder, search, offsets):
        short = next(c for c, fields in signatures.game.HIDDEN
                     if {o for _, o, _ in fields} == set(offsets)).rsplit(".", 1)[-1]
        return [] if short in unsigned else [{"from": "0x1000", "pattern": "90", "captures": {"0": min(offsets)}}]

    monkeypatch.setattr(signatures.pe, "Image", Image)
    monkeypatch.setattr(signatures, "Finder", Finder)
    monkeypatch.setattr(signatures, "_sites", sites)


def test_make_fails_a_class_with_no_sites(monkeypatch):
    fake_maker(monkeypatch, unsigned=("SwtAdventureLevelComponent",))
    with pytest.raises(signatures.Unsigned) as e:
        signatures.make("game.exe", log=lambda m: None)
    assert e.value.classes == ["SwtAdventureLevelComponent"]
    assert "SwtAdventureLevelComponent" in str(e.value) and "ANCHORS" in str(e.value)


def test_make_with_every_class_signed(monkeypatch):
    fake_maker(monkeypatch)
    res = signatures.make("game.exe", log=lambda m: None)
    assert all(e["sites"] for e in res["classes"].values())
    assert len(res["classes"][LEVEL]["anchors"]) == len(signatures.ANCHORS[LEVEL])
