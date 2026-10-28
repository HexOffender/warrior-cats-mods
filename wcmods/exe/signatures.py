"""Signatures for the classes wcmods reads directly: telling when a game update moves their data, and
where to.

game.HIDDEN lists members the game doesn't reflect (health at +0x10C in a resource component, the
clock at +0x438 in the game state, ...). They're offsets inside objects, so ASLR doesn't move them, but
a rebuild that adds a member to a class does. For each class this keeps:
- its size, from the class's registration call (GetPrivateStaticClassBody(..., sizeof(T), alignof(T)...));
- signatures: short byte patterns of the class's own code where it reads or writes those members,
  with every displacement, branch target and relocated address left out (wildcards) and the members'
  offsets marked as captures.

"The class's own code" is what's certainly its: the virtual functions it overrides (its vtable, found
through the constructor its registration passes), its native UFunctions (its StaticRegisterNatives
table), the functions those call directly (a parent's code among them: the level component's start-up
calls its parent's level setter), and the functions that ask for the class (Finder.class_code), each
read whole (pe.Image.function_at). A pattern only has to be unique among those, so it stays short and
survives the code around it changing. On another build, check() finds the class again the same way,
compares its size, and reads each member's offset out of the matching code; to follow a move, two
separate instructions must agree (overlapping sites that capture the same instruction are one vote).

    python wcmods.py game signatures make     # on the build wcmods was verified on: wcmods/exe/signatures.json
    python wcmods.py game signatures check    # on the installed game: what moved, and where to

Works on the exe on disk (pe.Image); nothing runs the game.
"""
import json
import os
import re
import struct

from .. import game
from . import pe, x64

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signatures.json")
RSP = 4
WINDOW = 40          # bytes of code either side of an access, at most
MIN_PATTERN = 12     # bytes; shorter patterns match too easily
MIN_FUNCTION_PATTERN = 20
WIDTH = {"ByteProperty": 1, "IntProperty": 4, "FloatProperty": 4}   # a member's size in bytes, by its kind

# Functions the reverse-engineering notes tie to a class whose members its own code hardly touches
# (docs/mechanics/combat.md, progression.md, docs/reverse-engineering.md): the starts of whole functions
# (pe.Image.function_at), as RVAs on build 26184573 (the combat, status and detection ones each 0x260 past
# where they were on 24847281). Each is found again in another build by a pattern of its first
# instructions that's unique in the whole exe, then read like the class's own code.
ANCHORS = {
    "/Script/SwtAdventure.TurnBasedCombatComponent": [
        (0x17D8270, "builds a fighter's stats from its level"),
        (0x17D8A00, "a fighter's Prowess with its buffs"),
        (0x17D9A60, "a fighter's speed, from Agility and stamina"),
        (0x17D70C0, "setting up a fighter: health and fight stamina from its stats"),
        (0x17D6A30, "dynamic difficulty: an enemy's level, its AI tier and its moves"),
        (0x17DB3E0, "hitting and missing: the defender's team looked up for a forced miss"),
    ],
    "/Script/SwtAdventure.SwtAdventureStatusComponent": [
        (0x17CE150, "the end of a round: the self-cure roll, and poison queued on the director"),
        (0x17CDB40, "loads the status tuning"),
    ],
    "/Script/SwtAdventure.SwtAdventureDetectionComponent": [
        (0x17B8DB0, "loads the senses from the tuning for the size class"),
        (0x17B80C0, "reads the senses"),
    ],
    # Its own code already reaches the level and the cap, which are its parent's (USwtQuestLevelComponent's)
    # members: its start-up override (0x17C6210) stores the cap and calls the parent's level setter, which
    # class_code() takes in as a direct callee. make() without these anchors signs all eight members too
    # (on 26184573). They're kept for redundancy: the XP setter adds a fourth separate instruction on the
    # level and a third on the cap, and the level setter is still searched if a rebuild stops 0x17C6210
    # calling it. The parent's start-up (0x1658C00) isn't one: its only access, the cap's store, is the
    # same bytes as 0x17C6210's as far as a signature reaches, so with both searched neither is unique,
    # and make() loses the cap's signature in 0x17C6210 (the cap in 2 instructions instead of 3).
    "/Script/SwtAdventure.SwtAdventureLevelComponent": [
        (0x1658A90, "setting the XP: levels up while it reaches the next level's, below the cap"),
        (0x1658870, "setting the level: the XP bar's size from the XP table, full at the cap"),
    ],
}


class ClassInfo:
    """Where a class's registration, size, vtable and own functions are in one exe."""

    def __init__(self, name):
        self.name = name
        self.size = self.align = None
        self.vtable = self.parent_vtable = None
        self.register_natives = None
        self.overrides = []      # function RVAs the class's vtable has and its parent's doesn't
        self.natives = []        # (UFunction name, exec function RVA)
        self.functions = []      # [(begin, end)] of all of the above

    def summary(self):
        return {"size": self.size, "align": self.align, "vtable": self.vtable, "overrides": len(self.overrides),
                "natives": len(self.natives)}


class Finder:
    """Finds classes in an exe. Builds an index of RIP-relative references once (a pass over the code)."""

    def __init__(self, image):
        self.img = image
        self.text = image.text
        self.tdata = bytes(image.text.data)
        self.relocs = image.relocations()
        self._refs = None

    # ---- references ----
    def refs_to(self, targets):
        """{target RVA: [instruction RVAs]} for lea/mov reg,[rip+...] instructions pointing at targets."""
        want, out = set(targets), {t: [] for t in targets}
        base = self.text.rva
        for m in re.finditer(rb"[\x48\x4C][\x8D\x8B][\x05\x0D\x15\x1D\x25\x2D\x35\x3D]", self.tdata):
            i = m.start()
            tgt = base + i + 7 + struct.unpack_from("<i", self.tdata, i + 3)[0]
            if tgt in want:
                out[tgt].append(base + i)
        return out

    def utf16(self, s):
        """RVAs of a whole UTF-16 string (as UE's TEXT() literals are) in the read-only data."""
        enc = s.encode("utf-16-le") + b"\0\0"
        out = []
        for sec in self.img.sections:
            if sec.name not in (".rdata", ".data"):
                continue
            d = bytes(sec.data)
            # Not checked for a terminator before it: UTF-16 literals sit right after ASCII ones too
            # ("...Turn\0" then "TurnBased..."), and only a registration call's reference counts anyway.
            for m in re.finditer(re.escape(enc), d):
                if m.start() % 2 == 0:
                    out.append(sec.rva + m.start())
        return out

    def ascii(self, s):
        enc = s.encode() + b"\0"
        out = []
        for sec in self.img.sections:
            if sec.name != ".rdata":
                continue
            d = bytes(sec.data)
            for m in re.finditer(re.escape(enc), d):
                if m.start() == 0 or d[m.start() - 1] == 0:
                    out.append(sec.rva + m.start())
        return out

    # ---- decoding helpers ----
    def insns(self, begin, end=None, limit=4000):
        """[(RVA, Insn)] from begin to the function's end (or `end`), stopping at undecodable bytes."""
        if end is None:
            fn = self.img.function_at(begin)
            end = fn[1] if fn else begin + 256
        out, p, stop = [], begin - self.text.rva, end - self.text.rva
        try:
            while p < stop and len(out) < limit:
                ins = x64.decode(self.text.data, p)
                out.append((self.text.rva + p, ins))
                p += ins.length
        except x64.DecodeError:
            pass
        return out

    def target(self, rva, ins):
        """Where a RIP-relative operand or a rel8/rel32 branch points."""
        p = rva - self.text.rva
        if ins.rel_size:
            return rva + ins.length + int.from_bytes(self.tdata[p + ins.rel_at:p + ins.rel_at + ins.rel_size], "little", signed=True)
        if ins.rip:
            return rva + ins.length + ins.disp
        return None

    def pointer(self, rva):
        """The RVA an absolute pointer at `rva` holds (a relocated slot), or None."""
        if rva not in self.relocs:
            return None
        return struct.unpack("<Q", self.img.read(rva, 8))[0] - self.img.image_base

    # ---- vtables ----
    def vtable(self, rva, limit=600):
        out = []
        while len(out) < limit:
            v = self.pointer(rva)
            if v is None or not (self.text.rva <= v < self.text.rva + len(self.tdata)):
                break
            out.append(v)
            rva += 8
        return out

    def _vtable_stores(self, rva, depth=0, seen=None):
        """Vtables a constructor installs (lea reg,[rip+.rdata] then mov [obj],reg), following its calls."""
        seen = seen if seen is not None else set()
        if rva in seen or depth > 2:
            return []
        seen.add(rva)
        out, lea = [], {}
        for r, ins in self.insns(rva, rva + 2048, limit=300):
            p = r - self.text.rva
            op = self.tdata[p + 1] if self.tdata[p] in (0x48, 0x4C) else None
            rex_r = 8 if self.tdata[p] in (0x4C, 0x4D, 0x4E, 0x4F) else 0
            if ins.rip and op == 0x8D:
                t = self.target(r, ins)
                sec = self.img.section_at(t)
                if sec and sec.name == ".rdata":
                    lea[ins.reg + rex_r] = t
            elif op == 0x89 and ins.mod is not None and ins.mod != 3 and not ins.rip and (ins.disp or 0) == 0:
                src = ins.reg + rex_r
                if src in lea and self.vtable(lea[src], limit=8):
                    out.append(lea[src])
            if self.tdata[p] == 0xE8:
                out += self._vtable_stores(self.target(r, ins), depth + 1, seen)
            elif ins.rel_size == 4 and (self.tdata[p] == 0xE9 or self.tdata[p] == 0x0F):
                # A tail call, conditional ones too: InternalConstructor<T> is `if (obj) jmp T::T`.
                t = self.target(r, ins)
                if not (rva <= t < rva + 2048):
                    out += self._vtable_stores(t, depth + 1, seen)
                if self.tdata[p] == 0xE9:
                    break
            if self.tdata[p] == 0xC3 and not out and r - rva < 16:
                continue   # `ret` right after a conditional tail call: nothing more in this one
            if self.tdata[p] == 0xC3:
                break
        return out

    # ---- a class ----
    def find_class(self, name):
        """Find a class by its short name ("SwtQuestResourceComponent"); a ClassInfo, or None."""
        names = self.utf16(name)
        refs = self.refs_to(names)
        for target in names:
            for ref in refs[target]:
                info = self._from_registration(name, ref)
                if info:
                    return info
        return None

    def _from_registration(self, name, ref):
        """Read the GetPrivateStaticClassBody call that `ref` (the class's name) feeds:
        (Package, Name, ReturnClass, RegisterNativeFunc /* r9 */, InSize /* [rsp+20h] */,
        InAlignment /* 28h */, ClassFlags, CastFlags, ConfigName, ClassConstructor /* 48h */, ...).
        Stack arguments are stored through rsp, or through r11 (rsp before the frame was made)."""
        fn = self.img.function_at(ref)
        if not fn:
            return None
        info = ClassInfo(name)
        regs, stack = {}, {}       # register -> .text pointer it holds; final rsp offset -> value
        frame, r11_is_rsp = 0, False
        call_at = None
        for r, ins in self.insns(fn[0], fn[1]):
            p = r - self.text.rva
            rex = self.tdata[p] if 0x40 <= self.tdata[p] <= 0x4F else 0
            op = self.tdata[p + (1 if rex else 0)]
            if self.tdata[p:p + 3] == bytes((0x4C, 0x8B, 0xDC)):            # mov r11, rsp
                r11_is_rsp = True
            elif self.tdata[p:p + 3] in (bytes((0x48, 0x83, 0xEC)), bytes((0x48, 0x81, 0xEC))):   # sub rsp, imm
                frame = int.from_bytes(self.tdata[p + ins.imm_at:p + ins.imm_at + ins.imm_size], "little")
            elif ins.rip and op == 0x8D:
                regs[ins.reg + (8 if rex & 4 else 0)] = self.target(r, ins)
            elif op in (0x89, 0xC7) and ins.memory() and ins.base in (RSP, 11) and (ins.base == RSP or r11_is_rsp):
                at = ins.disp + (frame if ins.base == 11 else 0)
                if op == 0xC7:
                    stack[at] = int.from_bytes(self.tdata[p + ins.imm_at:p + ins.imm_at + ins.imm_size], "little")
                elif ins.reg + (8 if rex & 4 else 0) in regs:
                    stack[at] = regs[ins.reg + (8 if rex & 4 else 0)]
            if op == 0xE8 and r > ref:
                call_at = r
                break
        if call_at is None or 0x20 not in stack:
            return None
        info.size, info.align = stack.get(0x20), stack.get(0x28)
        info.register_natives = regs.get(9)
        ctor = stack.get(0x48)
        stores = self._vtable_stores(ctor) if ctor else []
        if not stores:
            return None
        info.vtable = stores[-1]
        mine = self.vtable(info.vtable)

        # The parent's vtable is the other one the constructors install that shares the most entries
        # with the class's (member objects' vtables share none).
        def shared(v):
            return sum(1 for a, b in zip(mine, self.vtable(v)) if a == b)
        others = [v for v in dict.fromkeys(stores[:-1]) if v != info.vtable]
        info.parent_vtable = max(others, key=shared) if others else None
        parent = self.vtable(info.parent_vtable) if info.parent_vtable else []
        info.overrides = sorted({f for i, f in enumerate(mine) if i >= len(parent) or parent[i] != f})
        info.natives = self._natives(info.register_natives)
        info.static_class = fn[0]          # GetPrivateStaticClass: what T::StaticClass() calls
        info.class_pointer = regs.get(8)   # where it keeps the UClass* (ReturnClass)
        info.super_class = self._through_jumps(stack.get(0x60))   # the parent's StaticClass
        return info

    def _through_jumps(self, rva):
        """A function, following it when it's only a jump to another (thunks, folded functions)."""
        for _ in range(4):
            if rva is None:
                return None
            p = rva - self.text.rva
            if not (0 <= p < len(self.tdata)) or self.tdata[p] != 0xE9:
                return rva
            rva = rva + 5 + struct.unpack_from("<i", self.tdata, p + 1)[0]
        return rva

    def function_signature(self, begin):
        """A pattern of a function's first instructions that matches only it in the whole exe, or None."""
        span = self.img.function_at(begin)
        if not span:
            return None
        insns = self.insns(span[0], span[1], limit=120)
        whole = None
        for count in range(3, len(insns)):
            pat, _ = _bytes(self, insns, 0, count, {})
            if sum(b is not None for b in pat) < MIN_FUNCTION_PATTERN:
                continue
            whole = whole or self.tdata
            hits = []
            for m in _regex(pat).finditer(whole):
                hits.append(self.text.rva + m.start())
                if len(hits) > 1:
                    break
            if hits == [span[0]]:
                return pat
        return None

    def find_function(self, pattern):
        """The function a function_signature() pattern matches (its begin RVA), or None when it doesn't
        match exactly once."""
        hits = []
        for m in _regex(pattern).finditer(self.tdata):
            hits.append(self.text.rva + m.start())
            if len(hits) > 1:
                return None
        return hits[0] if hits else None

    def callers(self, targets):
        """{target: [function begins]} of the functions with a direct call (E8) to each target."""
        want, out = set(targets), {t: set() for t in targets}
        base, d = self.text.rva, self.tdata
        for m in re.finditer(rb"\xE8", d):
            i = m.start()
            if i + 5 > len(d):
                break
            t = base + i + 5 + struct.unpack_from("<i", d, i + 1)[0]
            if t in want:
                fn = self.img.function_at(base + i)
                if fn:
                    out[t].add(fn[0])
        return out

    def class_code(self, infos):
        """Each class's own code, as [(begin, end)] in info.functions: the virtuals it overrides and its
        native UFunctions, the functions those call directly, and the functions that ask for the class
        (call its StaticClass, or read its UClass pointer: a Cast<T> or a GetComponentByClass<T>)."""
        infos = [i for i in infos if i]
        calls = self.callers([i.static_class for i in infos])
        reads = self.refs_to([i.class_pointer for i in infos if i.class_pointer])
        for info in infos:
            own = info.overrides + [f for _, f in info.natives]
            begins = set(own)
            for f in own:
                for r, ins in self.insns(f, limit=2000):
                    if self.tdata[r - self.text.rva] == 0xE8:
                        begins.add(self.target(r, ins))
            begins |= calls.get(info.static_class, set())
            for ref in reads.get(info.class_pointer, []):
                fn = self.img.function_at(ref)
                if fn:
                    begins.add(fn[0])
            begins.discard(info.static_class)
            spans = set()
            for b in begins:
                span = self.img.function_at(b)
                if span and span[1] - span[0] < 20000:   # not the engine's giant dispatchers
                    spans.add(span)
            info.functions = sorted(spans)
        return infos

    def _natives(self, register):
        """(UFunction name, exec RVA) pairs from a StaticRegisterNatives function's table."""
        if not register:
            return []
        out = []
        for r, ins in self.insns(register, register + 256, limit=40):
            p = r - self.text.rva
            if ins.rip and self.tdata[p + 1] == 0x8D:
                arr = self.target(r, ins)
                i = arr
                while True:
                    name_at, func = self.pointer(i), self.pointer(i + 8)
                    if name_at is None or func is None or not (self.text.rva <= func < self.text.rva + len(self.tdata)):
                        break
                    raw = self.img.read(name_at, 128)
                    nm = raw.split(b"\0", 1)[0]
                    if not nm or not nm.isascii():
                        break
                    out.append((nm.decode(), func))
                    i += 16
                if out:
                    return out
            if self.tdata[p] == 0xC3:
                break
        return out


# ---------- making patterns ----------
VOLATILE = (0, 1, 2, 8, 9, 10, 11)   # rax, rcx, rdx, r8-r11: a call leaves anything in them
# Opcodes whose ModRM reg field is a general register they write (mov/lea are followed more closely).
WRITES_REG = {0x03, 0x0B, 0x13, 0x1B, 0x23, 0x2B, 0x33, 0x63, 0x69, 0x6B, 0x8A}
WRITES_REG_0F = {0xAF, 0xB6, 0xB7, 0xBE, 0xBF, 0x2C, 0x2D} | set(range(0x40, 0x50))   # imul, movzx/sx, cvt*2si, cmov
# Opcodes that write their ModRM r/m operand, when it's a register.
WRITES_RM = {0x01, 0x09, 0x11, 0x19, 0x21, 0x29, 0x31, 0x88, 0xC1, 0xC7, 0xD1, 0xD3}


def _foreign(finder, insns):
    """The indices of the instructions in `insns` (one function, in order) whose memory operand can't be a
    member of the class: its base register holds a stack address (rbp as a frame pointer, lea reg,[rsp+...])
    or a pointer read from a global (mov reg,[rip+...], lea reg,[rip+...]). A class's code reads other
    objects too, its locals and a singleton behind a global among them, at offsets that can equal a
    member's (the level component's code reads +0x154 of the object at 0x14A8A6E08, not its Prowess).
    It's a straight read of the function, branches ignored: a register's kind is set by the last
    instruction before that writes it, and one it can't follow is taken as anything (as before)."""
    tdata, base = finder.tdata, finder.text.rva
    kind = {RSP: "stack"}   # register -> "stack" or "global"; anything else isn't in it
    out = set()
    for i, (r, ins) in enumerate(insns):
        if ins.memory() and ins.base is not None and ins.base in kind:
            out.add(i)
        if ins.vex or ins.evex or ins.opmap != 1:
            continue
        p = r - base
        while tdata[p] in x64.LEGACY_PREFIXES:
            p += 1
        rex = tdata[p] if 0x40 <= tdata[p] <= 0x4F else 0
        op = tdata[p + (1 if rex else 0)]
        wide = bool(rex & 8)
        reg = ins.reg + (8 if rex & 4 else 0) if ins.reg is not None else None
        if op == 0x0F:
            if ins.opcode in WRITES_REG_0F:
                kind.pop(reg, None)
            continue
        if op in (0x8B, 0x8D):                    # mov reg, r/m and lea reg, [m]
            if ins.mod == 3:
                was = kind.get(ins.base) if wide and op == 0x8B else None
            elif ins.rip:
                was = "global" if wide else None
            else:
                was = "stack" if op == 0x8D and kind.get(ins.base) == "stack" else None
            kind.pop(reg, None)
            if was:
                kind[reg] = was
        elif op == 0x89 and ins.mod == 3:          # mov r/m, reg between registers
            was = kind.get(reg) if wide else None
            kind.pop(ins.base, None)
            if was:
                kind[ins.base] = was
        elif op in WRITES_REG:
            kind.pop(reg, None)
        elif ins.mod == 3 and _writes_rm(op, ins.reg):
            # Adding to or subtracting from a stack address leaves one (add rsp/sub rbp, imm).
            if not (op in (0x81, 0x83) and ins.reg in (0, 5) and kind.get(ins.base) == "stack"):
                kind.pop(ins.base, None)
        elif 0xB8 <= op <= 0xBF or 0x58 <= op <= 0x5F:   # mov reg, imm and pop reg
            kind.pop((op & 7) + (8 if rex & 1 else 0), None)
        if op == 0xE8 or (op == 0xFF and ins.reg in (2, 3)) or (op == 0xF7 and ins.reg >= 4) or op == 0x99:
            for v in (VOLATILE if op in (0xE8, 0xFF) else (0, 2)):   # a call; mul/div and cdq write rax, rdx
                kind.pop(v, None)
    return out


def _writes_rm(op, sub):
    """Whether an instruction with this opcode (and ModRM reg field, for the groups) writes its r/m operand."""
    if op in WRITES_RM:
        return True
    if op in (0x81, 0x83):
        return sub != 7   # cmp writes nothing
    if op == 0xF7:
        return sub in (2, 3)   # not, neg
    if op == 0xFF:
        return sub in (0, 1)   # inc, dec
    return False


# Opcodes (one-byte map) whose memory operand is a byte, and the general-purpose ones that are 4 bytes
# (8 with REX.W, 2 with 0x66).
BYTE_OPS = {0x00, 0x02, 0x08, 0x0A, 0x10, 0x12, 0x18, 0x1A, 0x20, 0x22, 0x28, 0x2A, 0x30, 0x32, 0x38, 0x3A,
            0x80, 0x84, 0x86, 0x88, 0x8A, 0xC0, 0xC6, 0xD0, 0xD2, 0xF6, 0xFE}
INT_OPS = {0x01, 0x03, 0x09, 0x0B, 0x11, 0x13, 0x19, 0x1B, 0x21, 0x23, 0x29, 0x2B, 0x31, 0x33, 0x39, 0x3B, 0x63,
           0x69, 0x6B, 0x81, 0x83, 0x85, 0x87, 0x89, 0x8B, 0xC1, 0xC7, 0xD1, 0xD3, 0xF7, 0xFF}
SSE_SCALAR = {0x10, 0x11, 0x2A, 0x2C, 0x2D, 0x51, 0x58, 0x59, 0x5A, 0x5C, 0x5D, 0x5E, 0x5F}


def _width(finder, rva, ins):
    """How many bytes the instruction at rva reads or writes through its memory operand: 0 for lea (it only
    takes the address), None when this doesn't know the instruction."""
    tdata = finder.tdata
    p = rva - finder.text.rva
    prefixes = set()
    while tdata[p] in x64.LEGACY_PREFIXES:
        prefixes.add(tdata[p])
        p += 1
    rex = tdata[p] if 0x40 <= tdata[p] <= 0x4F else 0
    op = tdata[p + (1 if rex else 0)]
    if ins.vex or ins.evex:
        return None
    if op != 0x0F:
        if op == 0x8D:
            return 0
        if op in BYTE_OPS:
            return 1
        if op == 0xFF and ins.reg in (2, 3, 4, 5, 6):   # call/jmp through memory (a vtable slot), push
            return 8
        if op in INT_OPS:
            return 8 if rex & 8 else 2 if 0x66 in prefixes else 4
        return None
    op2 = ins.opcode
    if ins.opmap != 1:
        return None
    if op2 in (0xB6, 0xBE) or 0x90 <= op2 <= 0x9F:
        return 1
    if op2 in (0xB7, 0xBF):
        return 2
    if op2 == 0xAF or 0x40 <= op2 <= 0x4F:
        return 8 if rex & 8 else 2 if 0x66 in prefixes else 4
    if op2 in SSE_SCALAR:
        return 4 if 0xF3 in prefixes else 8 if 0xF2 in prefixes else 16
    if op2 in (0x2E, 0x2F):
        return 8 if 0x66 in prefixes else 4
    if op2 in (0x6E, 0x7E):
        return 8 if rex & 8 or 0xF3 in prefixes else 4
    if op2 == 0xD6:
        return 8
    if op2 in (0x28, 0x29, 0x6F, 0x7F, 0x54, 0x55, 0x56, 0x57, 0x14, 0x15, 0xC6):
        return 16
    return None


def _access(finder, rva, ins, offsets):
    """Whether the instruction at rva reads or writes one of `offsets` ({offset: the member's size}) the way
    a member is: [reg+disp32] (not through rsp), at most as wide as the member, or a lea of it. A wider
    access at the same offset is another object's field (a pointer, or a vtable slot: call [rax+0x1C8])."""
    if not (ins.memory() and ins.base not in (RSP, None) and ins.disp in offsets and ins.disp_size == 4):
        return False
    width = _width(finder, rva, ins)
    return width is None or width <= offsets[ins.disp]


def _bytes(finder, insns, lo, hi, offsets, foreign=()):
    """A pattern of insns[lo..hi] with what a rebuild changes left out, and its captures: {position:
    offset} of the accesses to `offsets` ({offset: size}; _access) but the `foreign` indices' (_foreign)."""
    tdata, base = finder.tdata, finder.text.rva
    out, captures = [], {}
    for n, (r, ins) in enumerate(insns[lo:hi + 1], lo):
        p = r - base
        raw = list(tdata[p:p + ins.length])
        wild = set()
        if ins.disp_at is not None and ins.disp_size:
            wild.update(range(ins.disp_at, ins.disp_at + ins.disp_size))
            if offsets and n not in foreign and _access(finder, r, ins, offsets):
                captures[len(out) + ins.disp_at] = ins.disp
        if ins.rel_at is not None:
            wild.update(range(ins.rel_at, ins.rel_at + ins.rel_size))
        for k in range(ins.length):
            if r + k in finder.relocs or any(r + k - j in finder.relocs for j in range(1, 8)):
                wild.add(k)
        out += [None if k in wild else b for k, b in enumerate(raw)]
    return out, captures


def _regex(pattern):
    return re.compile(b"".join(b"." if b is None else re.escape(bytes([b])) for b in pattern), re.DOTALL)


def _hex(pattern):
    return " ".join("??" if b is None else f"{b:02X}" for b in pattern)


def _unhex(text):
    return [None if t == "??" else int(t, 16) for t in text.split()]


def _matches(finder, functions, rx):
    """[(function begin, RVA of the match)] of a pattern inside the given functions."""
    out = []
    base = finder.text.rva
    for begin, end in functions:
        chunk = finder.tdata[begin - base:end - base]
        for m in rx.finditer(chunk):
            out.append((begin, begin + m.start()))
            if len(out) > 1:
                return out
    return out


def _parent(found, info):
    """The monitored class `info` derives from (its registration's super class), or None."""
    if not (info and info.super_class):
        return None
    return next((i for i in found.values() if i and i is not info and i.static_class == info.super_class), None)


def _search(finder, found, cls, anchors):
    """The code a class's members are looked for in: its own, its monitored ancestors' (a member it
    inherits is read there too), and its anchors."""
    info = found[cls]
    spans = set(info.functions)
    seen, parent = set(), _parent(found, info)
    while parent and id(parent) not in seen:
        seen.add(id(parent))
        spans |= set(parent.functions)
        parent = _parent(found, parent)
    for rva in anchors:
        span = finder.img.function_at(rva)
        if span:
            spans.add(span)
    return sorted(spans)


def _sites(finder, search, offsets, per_field=3):
    """Patterns for the accesses to `offsets` ({offset: the member's size in bytes}) in the `search`
    functions, each the shortest around its access that matches once in them: [{"from": its function,
    "at": where it starts, "pattern", "captures"}]. Only accesses a member could be count (_access), and
    none through a stack address or a global's pointer (_foreign). A member gets sites until `per_field`
    separate instructions are captured: sites around neighbouring instructions overlap and capture the
    same one, which is one piece of evidence however many patterns hold it, so an instruction a site
    already captures gets none of its own."""
    sites, seen = [], {}   # offset -> the RVAs of the displacements captured for it
    for begin, end in search:
        insns = finder.insns(begin, end)
        foreign = _foreign(finder, insns)
        for i, (r, ins) in enumerate(insns):
            if i in foreign or not _access(finder, r, ins, offsets):
                continue
            held = seen.get(ins.disp, set())
            if len(held) >= per_field or r + ins.disp_at in held:   # enough, or a site has it already
                continue
            for width in range(1, 12):
                a, b = max(0, i - width), min(len(insns) - 1, i + width)
                if insns[i][0] - insns[a][0] > WINDOW or insns[b][0] - insns[i][0] > WINDOW:
                    break
                pat, caps = _bytes(finder, insns, a, b, offsets, foreign)
                if sum(x is not None for x in pat) < MIN_PATTERN:
                    continue
                if len(_matches(finder, search, _regex(pat))) == 1:
                    at = insns[a][0]
                    sites.append({"from": f"0x{begin:X}", "at": f"0x{at:X}", "pattern": _hex(pat),
                                  "captures": {str(k): v for k, v in caps.items()}})
                    for k, v in caps.items():
                        seen.setdefault(v, set()).add(at + k)
                    break
    return sites


def instructions(entry):
    """{offset: how many separate instructions a class's sites capture it in}, on the build they were made
    on (each site's "at" plus the capture's position: overlapping sites count an instruction once)."""
    out = {}
    for site in entry["sites"]:
        for k, was in site["captures"].items():
            out.setdefault(was, set()).add(int(site["at"], 16) + int(k))
    return {o: len(v) for o, v in out.items()}


class Unsigned(ValueError):
    """make() found no signature at all for some classes: on any other build check() could find none of
    their members, so a game update would switch every one of them off even when nothing moved."""

    def __init__(self, classes, result):
        super().__init__(f"no signatures for {', '.join(classes)}: give each anchors in signatures.ANCHORS, "
                         "functions that read its members (docs/reverse-engineering.md, \"Game updates\")")
        self.classes, self.result = classes, result


def make(image_path, log=print):
    """Signatures for every class in game.HIDDEN, from this exe (the build HIDDEN was found on):
    {"made_on": the exe's fingerprint, "classes": {class: {"fields", "size", "parent", "anchors", "sites"}}}.
    Raises Unsigned when a class isn't found or gets no signature at all (a member with none of its own is
    fine: check() keeps it while its classmates are found where they were)."""
    img = pe.Image(image_path)
    finder = Finder(img)
    result = {"made_on": img.fingerprint(), "classes": {}}
    found = {cls: finder.find_class(cls.rsplit(".", 1)[-1]) for cls, _ in game.HIDDEN}
    finder.class_code(found.values())
    unsigned = []
    for cls, fields in game.HIDDEN:
        short = cls.rsplit(".", 1)[-1]
        info = found[cls]
        entry = {"fields": {n: o for n, o, _ in fields}, "found": bool(info), "anchors": [], "sites": []}
        result["classes"][cls] = entry
        if not info:
            log(f"  {short}: not found")
            unsigned.append(short)
            continue
        entry.update(info.summary())
        parent = _parent(found, info)
        entry["parent"] = parent.name if parent else None
        anchors = []
        for rva, note in ANCHORS.get(cls, []):
            span = img.function_at(rva)
            pat = finder.function_signature(span[0]) if span else None
            entry["anchors"].append({"note": note, "was": f"0x{span[0]:X}" if span else None,
                                     "pattern": _hex(pat) if pat else None})
            if pat:
                anchors.append(span[0])
        search = _search(finder, found, cls, anchors)
        entry["sites"] = _sites(finder, search, {o: WIDTH.get(kind, 4) for _, o, kind in fields})
        got = instructions(entry)
        missing = [n for n, o, _ in fields if o not in got]
        # A move is followed on the word of MIN_MOVE_VOTES separate instructions: with fewer, check() can
        # tell the member is where it was, but not where it went.
        alone = [n for n, o, _ in fields if 0 < got.get(o, 0) < MIN_MOVE_VOTES]
        log(f"  {short}: size 0x{info.size:X}{f' (a {parent.name})' if parent else ''}, {len(search)} functions "
            f"({len(anchors)} anchors), {len(entry['sites'])} signatures"
            + (f"; none for {', '.join(missing)}" if missing else "")
            + (f"; one instruction only for {', '.join(alone)}" if alone else ""))
        if not entry["sites"]:
            unsigned.append(short)
    if unsigned:
        raise Unsigned(unsigned, result)
    return result


def save(result, path=DATA):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=1)
        f.write("\n")


def load(path=DATA):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------- checking another build ----------
MIN_MOVE_VOTES = 2   # a member is followed to a new offset on the word of two separate instructions or more


def check(image_path, sigs=None, log=print):
    """What the signatures find in this exe: {"same", "classes": {class: {"found", "size", "size_was",
    "anchors", "fields": {name: {"was", "now", "votes", "status"}}}}, "offsets": {"class:name": offset or
    None}}. Each instruction the matching sites capture a member in is one vote ("votes"), however many
    overlapping sites hold it. A member's status:
    - "same": its votes agree it's where it was;
    - "moved": two or more agree on a new offset, which fits in the class;
    - "kept": none matched, but the exe is the one the signatures were made on, or its class is the same
      size, another member of it was found where it was, and none moved or disagreed: taken as where it
      was. A class with no member found gets none kept;
    - "unsure": a single instruction says it moved; "conflict": they disagree, or two members land on the
      same offset, or the offset can't be one (outside the class, misaligned); "lost": none matched and it
      can't be kept. These mean its offset is None, so it's left out.
    """
    from ..game import HIDDEN
    widths = {f"{c}:{n}": WIDTH.get(kind, 4) for c, fields in HIDDEN for n, _, kind in fields}
    sigs = sigs or load()
    img = pe.Image(image_path)
    finder = Finder(img)
    out = {"made_on": sigs.get("made_on"), "exe": img.fingerprint(), "classes": {}, "offsets": {}}
    made_on = out["made_on"] or {}
    out["same_exe"] = all(made_on.get(k) == v for k, v in out["exe"].items())   # made_on also holds the build
    found = {cls: finder.find_class(cls.rsplit(".", 1)[-1]) for cls in sigs["classes"]}
    finder.class_code(found.values())
    for cls, entry in sigs["classes"].items():
        short = cls.rsplit(".", 1)[-1]
        info = found[cls]
        rep = {"found": bool(info), "size": info.size if info else None, "size_was": entry.get("size"),
               "anchors": 0, "fields": {}}
        out["classes"][cls] = rep
        votes = {}   # offset it was -> {where in .text the displacement is: what it says now}
        if info:
            anchors = [finder.find_function(_unhex(a["pattern"])) for a in entry.get("anchors", []) if a.get("pattern")]
            rep["anchors"] = sum(1 for a in anchors if a)
            search = _search(finder, found, cls, [a for a in anchors if a])
            for site in entry["sites"]:
                hits = _matches(finder, search, _regex(_unhex(site["pattern"])))
                if len(hits) != 1:
                    continue
                at = hits[0][1] - finder.text.rva
                for k, was in site["captures"].items():
                    # Overlapping sites capture the same instruction: it's one vote, not one per site.
                    p = at + int(k)
                    votes.setdefault(was, {})[p] = struct.unpack_from("<i", finder.tdata, p)[0]
        same_size = info is not None and info.size == entry.get("size")
        size = info.size if info else entry.get("size") or 0
        for name, was in entry["fields"].items():
            got = list(votes.get(was, {}).values())
            width = widths.get(f"{cls}:{name}", 4)
            if got and all(v == got[0] for v in got):
                now = got[0]
                if now == was:
                    status = "same"
                elif not (0 < now and now + width <= size and now % width == 0):
                    now, status = None, "conflict"   # not an offset in this class
                elif len(got) < MIN_MOVE_VOTES:
                    now, status = None, "unsure"
                else:
                    status = "moved"
            elif got:
                now, status = None, "conflict"
            else:
                now, status = None, "lost"
            rep["fields"][name] = {"was": was, "now": now, "votes": len(got), "status": status}
        statuses = [f["status"] for f in rep["fields"].values()]
        evidence = "same" in statuses
        disturbed = any(s in ("moved", "unsure", "conflict") for s in statuses)
        for name, f in rep["fields"].items():
            if f["status"] == "lost" and (out["same_exe"] or (same_size and evidence and not disturbed)):
                f["now"], f["status"] = f["was"], "kept"
        log(f"  {short}: " + ("not found" if not info else
            f"size 0x{info.size:X}" + ("" if same_size else f" (was 0x{entry.get('size') or 0:X})") + "; " +
            ", ".join(f"{n} {f['status']}" + (f" 0x{f['was']:X}->0x{f['now']:X}" if f["status"] == "moved" else "")
                      for n, f in rep["fields"].items())))
    # A class shares its object with the monitored classes it derives from: no two members on one offset.
    def line(cls):
        while cls:
            yield cls
            parent = sigs["classes"][cls].get("parent")
            cls = next((c for c in sigs["classes"] if c.rsplit(".", 1)[-1] == parent), None) if parent else None
    for cls in sigs["classes"]:
        seen = {}
        for c in line(cls):
            for name, f in out["classes"][c]["fields"].items():
                if f["now"] is not None:
                    seen.setdefault(f["now"], []).append(f)
        for clash in (fs for fs in seen.values() if len(fs) > 1):
            for f in clash:
                f["now"], f["status"] = None, "conflict"
    for cls, rep in out["classes"].items():
        for name, f in rep["fields"].items():
            out["offsets"][f"{cls}:{name}"] = f["now"]
    out["same"] = all(f["status"] in ("same", "kept") for c in out["classes"].values() for f in c["fields"].values())
    return out
