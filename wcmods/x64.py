"""A small x86-64 instruction decoder: how long each instruction is and where its operands sit.

Enough to cut code into instructions and find the parts a game update changes: memory operands
([reg+disp], where struct member offsets live), RIP-relative addresses, branch targets and
immediates. It doesn't name instructions. signatures.py uses it to build patterns that survive a
rebuild; checked against every function in the game's .pdata (see check_functions).
"""

LEGACY_PREFIXES = {0xF0, 0xF2, 0xF3, 0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65, 0x66, 0x67}


def _set(*ranges):
    out = set()
    for r in ranges:
        if isinstance(r, int):
            out.add(r)
        else:
            out.update(range(r[0], r[1] + 1))
    return out


# One-byte opcodes with a ModRM byte.
MODRM_1 = _set((0x00, 0x03), (0x08, 0x0B), (0x10, 0x13), (0x18, 0x1B), (0x20, 0x23), (0x28, 0x2B), (0x30, 0x33),
               (0x38, 0x3B), 0x63, 0x69, 0x6B, (0x80, 0x8F), 0xC0, 0xC1, 0xC6, 0xC7, (0xD0, 0xD3), (0xD8, 0xDF),
               0xF6, 0xF7, 0xFE, 0xFF)
IMM8_1 = _set(0x04, 0x0C, 0x14, 0x1C, 0x24, 0x2C, 0x34, 0x3C, 0x6A, 0x6B, 0x80, 0x82, 0x83, 0xA8, (0xB0, 0xB7),
              0xC0, 0xC1, 0xC6, 0xCD, (0xE4, 0xE7))
IMMZ_1 = _set(0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D, 0x68, 0x69, 0x81, 0xA9, 0xC7)
REL8_1 = _set((0x70, 0x7F), (0xE0, 0xE3), 0xEB)
REL32_1 = _set(0xE8, 0xE9)
INVALID_1 = _set(0x06, 0x07, 0x0E, 0x16, 0x17, 0x1E, 0x1F, 0x27, 0x2F, 0x37, 0x3F, 0x60, 0x61, 0x82, 0x9A,
                 0xC4, 0xC5, 0xD4, 0xD5, 0xD6, 0xEA)

# Two-byte (0F xx) opcodes without a ModRM byte; everything else in the map has one.
NO_MODRM_2 = _set(0x05, 0x06, 0x07, 0x08, 0x09, 0x0B, 0x0E, (0x30, 0x37), 0x77, (0x80, 0x8F), 0xA0, 0xA1, 0xA2,
                  0xA8, 0xA9, 0xAA, (0xC8, 0xCF))
IMM8_2 = _set((0x70, 0x73), 0xA4, 0xAC, 0xBA, 0xC2, 0xC4, 0xC5, 0xC6)


class Insn:
    """One decoded instruction. Offsets are from the instruction's start; None when absent."""
    __slots__ = ("length", "opmap", "opcode", "modrm", "mod", "reg", "rm", "base", "index", "rip",
                 "disp", "disp_at", "disp_size", "imm_at", "imm_size", "rel_at", "rel_size", "vex", "evex", "rex_w")

    def __init__(self):
        self.length, self.opmap, self.opcode, self.modrm = 0, 1, None, None
        self.mod = self.reg = self.rm = self.base = self.index = None
        self.rip, self.disp, self.disp_at, self.disp_size = False, None, None, 0
        self.imm_at, self.imm_size, self.rel_at, self.rel_size = None, 0, None, 0
        self.vex = self.evex = self.rex_w = False

    def memory(self):
        """Whether it has a [base+disp] memory operand (not RIP-relative, not a register)."""
        return self.mod is not None and self.mod != 3 and not self.rip

    def __repr__(self):
        bits = [f"len={self.length}", f"map={self.opmap}", f"op={self.opcode:02X}"]
        if self.memory():
            bits.append(f"[r{self.base}+0x{self.disp or 0:X}]")
        if self.rip:
            bits.append("rip")
        return "<Insn " + " ".join(bits) + ">"


class DecodeError(ValueError):
    pass


def _modrm(buf, p, start, ins, rex_b, rex_x, addr32):
    if p >= len(buf):
        raise DecodeError("cut off")
    m = buf[p]
    ins.modrm = m
    ins.mod, ins.reg, ins.rm = m >> 6, (m >> 3) & 7, m & 7
    p += 1
    if ins.mod == 3:
        ins.base = ins.rm + 8 * rex_b
        return p
    base = ins.rm
    if ins.rm == 4:   # SIB
        if p >= len(buf):
            raise DecodeError("cut off")
        sib = buf[p]
        p += 1
        base = sib & 7
        idx = ((sib >> 3) & 7) + 8 * rex_x
        ins.index = None if idx == 4 else idx
        if base == 5 and ins.mod == 0:
            ins.base = None
            ins.disp_at, ins.disp_size = p - start, 4
            ins.disp = int.from_bytes(buf[p:p + 4], "little", signed=True)
            return p + 4
        ins.base = base + 8 * rex_b
    elif ins.rm == 5 and ins.mod == 0:
        ins.rip = True   # RIP-relative (or a 32-bit absolute with 0x67)
        ins.disp_at, ins.disp_size = p - start, 4
        ins.disp = int.from_bytes(buf[p:p + 4], "little", signed=True)
        return p + 4
    else:
        ins.base = base + 8 * rex_b
    if ins.mod == 1:
        ins.disp_at, ins.disp_size = p - start, 1
        ins.disp = int.from_bytes(buf[p:p + 1], "little", signed=True)
        return p + 1
    if ins.mod == 2:
        ins.disp_at, ins.disp_size = p - start, 4
        ins.disp = int.from_bytes(buf[p:p + 4], "little", signed=True)
        return p + 4
    ins.disp = 0
    return p


def decode(buf, pos):
    """Decode the instruction at buf[pos]; returns an Insn, or raises DecodeError."""
    ins = Insn()
    p = pos
    opsize16 = addr32 = False
    while p < len(buf) and buf[p] in LEGACY_PREFIXES:
        if buf[p] == 0x66:
            opsize16 = True
        elif buf[p] == 0x67:
            addr32 = True
        p += 1
        if p - pos > 14:
            raise DecodeError("too many prefixes")
    rex = 0
    if p < len(buf) and 0x40 <= buf[p] <= 0x4F:
        rex = buf[p]
        p += 1
    if p >= len(buf):
        raise DecodeError("cut off")
    rex_w, rex_r, rex_x, rex_b = (rex >> 3) & 1, (rex >> 2) & 1, (rex >> 1) & 1, rex & 1
    ins.rex_w = bool(rex_w)
    b = buf[p]

    # VEX (C5 two-byte, C4 three-byte) and EVEX (62) prefixes: always these in 64-bit mode.
    if b in (0xC4, 0xC5, 0x62):
        if b == 0xC5:
            r1 = buf[p + 1]
            rex_b = rex_x = 0
            omap = 1
            p += 2
            ins.vex = True
        elif b == 0xC4:
            r1, r2 = buf[p + 1], buf[p + 2]
            rex_x, rex_b = (~r1 >> 6) & 1, (~r1 >> 5) & 1
            omap = r1 & 0x1F
            ins.rex_w = bool(r2 >> 7)
            p += 3
            ins.vex = True
        else:
            p0, p1 = buf[p + 1], buf[p + 2]
            rex_x, rex_b = (~p0 >> 6) & 1, (~p0 >> 5) & 1
            omap = p0 & 0x07
            ins.rex_w = bool(p1 >> 7)
            p += 4
            ins.evex = True
        if omap not in (1, 2, 3, 5, 6):
            raise DecodeError(f"VEX map {omap}")
        ins.opmap, ins.opcode = omap, buf[p]
        p += 1
        if omap == 1 and ins.opcode == 0x77 and ins.vex:   # vzeroupper / vzeroall
            ins.length = p - pos
            return ins
        p = _modrm(buf, p, pos, ins, rex_b, rex_x, addr32)
        if omap == 3 or (omap == 1 and ins.opcode in IMM8_2):
            ins.imm_at, ins.imm_size = p - pos, 1
            p += 1
        ins.length = p - pos
        return ins

    # AMD XOP (8F with a map of 8 or more; 8F with a smaller one is pop r/m): like a three-byte VEX.
    if b == 0x8F and p + 1 < len(buf) and buf[p + 1] & 0x1F >= 8:
        r1 = buf[p + 1]
        rex_x, rex_b = (~r1 >> 6) & 1, (~r1 >> 5) & 1
        omap = r1 & 0x1F
        if omap not in (8, 9, 10):
            raise DecodeError(f"XOP map {omap}")
        ins.vex, ins.opmap, ins.opcode = True, omap, buf[p + 3]
        p = _modrm(buf, p + 4, pos, ins, rex_b, rex_x, addr32)
        if omap != 9:
            ins.imm_at, ins.imm_size = p - pos, 1 if omap == 8 else 4
            p += ins.imm_size
        ins.length = p - pos
        return ins

    p += 1
    if b != 0x0F:
        ins.opmap, ins.opcode = 1, b
        if b in INVALID_1:
            raise DecodeError(f"opcode {b:02X} isn't valid in 64-bit code")
        if b in MODRM_1:
            p = _modrm(buf, p, pos, ins, rex_b, rex_x, addr32)
        if b in IMM8_1 or (b == 0xF6 and ins.reg in (0, 1)):
            ins.imm_at, ins.imm_size = p - pos, 1
        elif b in IMMZ_1 or (b == 0xF7 and ins.reg in (0, 1)):
            ins.imm_at, ins.imm_size = p - pos, 2 if opsize16 else 4
        elif 0xB8 <= b <= 0xBF:
            ins.imm_at, ins.imm_size = p - pos, 8 if rex_w else (2 if opsize16 else 4)
        elif 0xA0 <= b <= 0xA3:   # mov with a 64-bit absolute address
            ins.imm_at, ins.imm_size = p - pos, 4 if addr32 else 8
        elif b in (0xC2, 0xCA):
            ins.imm_at, ins.imm_size = p - pos, 2
        elif b == 0xC8:
            ins.imm_at, ins.imm_size = p - pos, 3
        elif b in REL8_1:
            ins.rel_at, ins.rel_size = p - pos, 1
        elif b in REL32_1:
            ins.rel_at, ins.rel_size = p - pos, 4
        p += ins.imm_size + ins.rel_size
        ins.length = p - pos
        if ins.length > 15:
            raise DecodeError("longer than 15 bytes")
        return ins

    # 0F xx, 0F 38 xx, 0F 3A xx
    if p >= len(buf):
        raise DecodeError("cut off")
    b2 = buf[p]
    p += 1
    if b2 in (0x38, 0x3A):
        ins.opmap, ins.opcode = 2 if b2 == 0x38 else 3, buf[p]
        p += 1
        p = _modrm(buf, p, pos, ins, rex_b, rex_x, addr32)
        if b2 == 0x3A:
            ins.imm_at, ins.imm_size = p - pos, 1
            p += 1
        ins.length = p - pos
        return ins
    ins.opmap, ins.opcode = 1, b2
    if b2 == 0x0F:   # 3DNow!: ModRM, then the opcode as an imm8
        p = _modrm(buf, p, pos, ins, rex_b, rex_x, addr32)
        ins.imm_at, ins.imm_size = p - pos, 1
        p += 1
    elif 0x80 <= b2 <= 0x8F:
        ins.rel_at, ins.rel_size = p - pos, 4
        p += 4
    elif b2 not in NO_MODRM_2:
        p = _modrm(buf, p, pos, ins, rex_b, rex_x, addr32)
        if b2 in IMM8_2:
            ins.imm_at, ins.imm_size = p - pos, 1
            p += 1
    ins.length = p - pos
    if ins.length > 15:
        raise DecodeError("longer than 15 bytes")
    return ins


def instructions(buf, start, end):
    """Decode buf[start:end] in order: yields (position, Insn). Stops at the first byte it can't decode."""
    p = start
    while p < end:
        ins = decode(buf, p)
        yield p, ins
        p += ins.length


def check_functions(image, limit=None):
    """Decode every function .pdata lists, from its start to its end: (functions, ones that decode to
    exactly their end). A decoder bug shows up as a mismatch."""
    text = image.text
    total = exact = 0
    for begin, end in image.functions()[:limit]:
        if not (text.rva <= begin < end <= text.rva + len(text.data)):
            continue
        total += 1
        p = begin - text.rva
        stop = end - text.rva
        try:
            while p < stop:
                p += decode(text.data, p).length
        except DecodeError:
            continue
        exact += p == stop
    return total, exact
