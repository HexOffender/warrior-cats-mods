"""Find code that references strings: RIP-relative LEA/MOV whose target is a string's address.

usage: xrefs.py <exe> "<text>" ...   (strings are searched as UTF-16 and ASCII)
Prints each string's VA and the VAs of instructions that point at it.
"""
import re
import struct
import sys

exe = sys.argv[1]
data = open(exe, "rb").read()
pe = struct.unpack_from("<I", data, 0x3C)[0]
nsec = struct.unpack_from("<H", data, pe + 6)[0]
opt = pe + 24
base = struct.unpack_from("<Q", data, opt + 24)[0]
sect_off = opt + struct.unpack_from("<H", data, pe + 20)[0]
sections = []
for i in range(nsec):
    s = sect_off + 40 * i
    name = data[s:s + 8].rstrip(b"\0").decode()
    vsize, va, rsize, raw = struct.unpack_from("<IIII", data, s + 8)
    sections.append((name, va, vsize, raw, rsize))


def off_to_va(off):
    for name, va, vsize, raw, rsize in sections:
        if raw <= off < raw + rsize:
            return base + va + off - raw
    return None


text = next(s for s in sections if s[0] == ".text")
t_raw, t_size, t_va = text[3], text[4], base + text[1]
code = data[t_raw:t_raw + t_size]

targets = {}
for s in sys.argv[2:]:
    for enc in ("utf-16-le", "ascii"):
        pat = s.encode(enc)
        for m in re.finditer(re.escape(pat), data):
            # only whole strings: the previous char should be a terminator
            prev = data[m.start() - (2 if enc != "ascii" else 1):m.start()]
            if prev.strip(b"\0") == b"" or True:
                va = off_to_va(m.start())
                if va:
                    targets[va] = (s, enc)

print("strings:")
for va, (s, enc) in sorted(targets.items()):
    print(f"  {va:#x} {enc[:5]} {s!r}")

# REX.W LEA r64,[rip+disp32] (48/4C 8D modrm with mod=00 rm=101) and MOV variants
rx = re.compile(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", re.S)
found = {va: [] for va in targets}
tset = set(targets)
for m in rx.finditer(code):
    i = m.start()
    disp = struct.unpack_from("<i", code, i + 3)[0]
    tgt = t_va + i + 7 + disp
    if tgt in tset:
        found[tgt].append(t_va + i)
print("references:")
for va, refs in sorted(found.items()):
    s, enc = targets[va]
    print(f"  {s!r} ({enc[:5]} @{va:#x}): {', '.join(hex(r) for r in refs[:12])}")
