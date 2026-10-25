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
through the constructor its registration passes), and its native UFunctions (its StaticRegisterNatives
table). A pattern only has to be unique among those, so it stays short and survives the code around it
changing. On another build, check() finds the class again the same way, compares its size, and reads
each member's offset out of the matching code; several sites must agree.

    python wcmods.py game signatures make     # on the build wcmods was verified on: wcmods/signatures.json
    python wcmods.py game signatures check    # on the installed game: what moved, and where to

Works on the exe on disk (pe.Image); nothing runs the game.
"""
import json
import os
import re
import struct

from . import game, pe, x64

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signatures.json")
RSP = 4
WINDOW = 40          # bytes of code either side of an access, at most
MIN_PATTERN = 12     # bytes; shorter patterns match too easily
MIN_FUNCTION_PATTERN = 20

# Functions the reverse-engineering notes tie to a class whose members its own code hardly touches
# (docs/mechanics/combat.md, progression.md): RVAs on build 24847281. Each is found again in another
# build by a pattern of its first instructions that's unique in the whole exe, then read like the
# class's own code.
ANCHORS = {
    "/Script/SwtAdventure.TurnBasedCombatComponent": [
        (0x17D8010, "builds a fighter's stats from its level"),
        (0x17D87A0, "a fighter's Prowess with its buffs"),
        (0x17D9800, "a fighter's speed, from Agility and stamina"),
        (0x17D6F0A, "setting up a fighter: health and fight stamina from its stats"),
        (0x17D67D0, "dynamic difficulty: an enemy's level, its AI tier and its moves"),
        (0x17DB37E, "hitting and missing: the defender's slot looked up for a forced miss"),
    ],
    "/Script/SwtAdventure.SwtAdventureStatusComponent": [
        (0x17CDEF0, "the end of a round: the self-cure roll, and poison queued on the director"),
        (0x17CDA26, "loads the status tuning"),
    ],
    "/Script/SwtAdventure.SwtAdventureDetectionComponent": [
        (0x17B8B50, "loads the senses from the tuning for the size class"),
        (0x17B7E60, "reads the senses"),
    ],
    "/Script/SwtAdventure.SwtAdventureLevelComponent": [
        (0x17D8010, "builds a fighter's stats from its level"),
        (0x17D6F0A, "setting up a fighter: health and fight stamina from its stats"),
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
def _bytes(finder, insns, lo, hi, offsets):
    tdata, base = finder.tdata, finder.text.rva
    out, captures = [], {}
    for r, ins in insns[lo:hi + 1]:
        p = r - base
        raw = list(tdata[p:p + ins.length])
        wild = set()
        if ins.disp_at is not None and ins.disp_size:
            wild.update(range(ins.disp_at, ins.disp_at + ins.disp_size))
            if ins.memory() and ins.base not in (RSP, None) and ins.disp in offsets and ins.disp_size == 4:
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
    """Patterns for the accesses to `offsets` in the `search` functions, each the shortest around its
    access that matches once in them: [{"from", "pattern", "captures"}]."""
    sites, count = [], {}
    for begin, end in search:
        insns = finder.insns(begin, end)
        for i, (r, ins) in enumerate(insns):
            if not (ins.memory() and ins.base not in (RSP, None) and ins.disp in offsets and ins.disp_size == 4):
                continue
            if count.get(ins.disp, 0) >= per_field:
                continue
            for width in range(1, 12):
                a, b = max(0, i - width), min(len(insns) - 1, i + width)
                if insns[i][0] - insns[a][0] > WINDOW or insns[b][0] - insns[i][0] > WINDOW:
                    break
                pat, caps = _bytes(finder, insns, a, b, offsets)
                if sum(x is not None for x in pat) < MIN_PATTERN:
                    continue
                if len(_matches(finder, search, _regex(pat))) == 1:
                    sites.append({"from": f"0x{begin:X}", "pattern": _hex(pat),
                                  "captures": {str(k): v for k, v in caps.items()}})
                    for v in caps.values():
                        count[v] = count.get(v, 0) + 1
                    break
    return sites


def make(image_path, log=print):
    """Signatures for every class in game.HIDDEN, from this exe (the build HIDDEN was found on):
    {"made_on": the exe's fingerprint, "classes": {class: {"fields", "size", "parent", "anchors", "sites"}}}."""
    img = pe.Image(image_path)
    finder = Finder(img)
    result = {"made_on": img.fingerprint(), "classes": {}}
    found = {cls: finder.find_class(cls.rsplit(".", 1)[-1]) for cls, _ in game.HIDDEN}
    finder.class_code(found.values())
    for cls, fields in game.HIDDEN:
        short = cls.rsplit(".", 1)[-1]
        info = found[cls]
        entry = {"fields": {n: o for n, o, _ in fields}, "found": bool(info), "anchors": [], "sites": []}
        result["classes"][cls] = entry
        if not info:
            log(f"  {short}: not found")
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
        entry["sites"] = _sites(finder, search, {o for _, o, _ in fields})
        got = {v for site in entry["sites"] for v in site["captures"].values()}
        missing = [n for n, o, _ in fields if o not in got]
        log(f"  {short}: size 0x{info.size:X}{f' (a {parent.name})' if parent else ''}, {len(search)} functions "
            f"({len(anchors)} anchors), {len(entry['sites'])} signatures"
            + (f"; none for {', '.join(missing)}" if missing else ""))
    return result


def save(result, path=DATA):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=1)
        f.write("\n")


def load(path=DATA):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------- checking another build ----------
MIN_MOVE_VOTES = 2   # a member is followed to a new offset on the word of two sites or more
WIDTH = {"ByteProperty": 1, "IntProperty": 4, "FloatProperty": 4}


def check(image_path, sigs=None, log=print):
    """What the signatures find in this exe: {"same", "classes": {class: {"found", "size", "size_was",
    "anchors", "fields": {name: {"was", "now", "votes", "status"}}}}, "offsets": {"class:name": offset or
    None}}. A member's status:
    - "same": its signatures agree it's where it was;
    - "moved": two or more agree on a new offset, which fits in the class;
    - "kept": none matched, but the exe is the one the signatures were made on, or its class is the same
      size, another member of it was found where it was, and none moved or disagreed: taken as where it
      was. A class with no member found gets none kept;
    - "unsure": a single site says it moved; "conflict": they disagree, or two members land on the same
      offset, or the offset can't be one (outside the class, misaligned); "lost": none matched and it
      can't be kept. These mean its offset is None, so it's left out.
    """
    from .game import HIDDEN
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
        votes = {}
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
                    votes.setdefault(was, []).append(struct.unpack_from("<i", finder.tdata, at + int(k))[0])
        same_size = info is not None and info.size == entry.get("size")
        size = info.size if info else entry.get("size") or 0
        for name, was in entry["fields"].items():
            got = votes.get(was, [])
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
