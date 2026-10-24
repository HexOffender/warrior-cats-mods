"""Map tuning keys to the member offsets a loader stores them in.

usage: tunemap.py <exe> <dumpbin listing> [more listings...]
A listing is `dumpbin /disasm:nobytes /range:<start>,<end> <exe>` output for a function that reads
tuning keys (find one with xrefs.py on a key such as Gameplay.Exploration.Camera.TurnRate.Yaw).
Each key the code loads and the `lea rdx,[reg+offset]` it stores into are printed as one line.
"""
import re, struct, sys
exe = open(sys.argv[1], "rb").read()
pe = struct.unpack_from("<I", exe, 0x3C)[0]
nsec = struct.unpack_from("<H", exe, pe + 6)[0]
opt = pe + 24
base = struct.unpack_from("<Q", exe, opt + 24)[0]
so = opt + struct.unpack_from("<H", exe, pe + 20)[0]
secs = []
for i in range(nsec):
    s = so + 40 * i
    vsize, va, rsize, raw = struct.unpack_from("<IIII", exe, s + 8)
    secs.append((va, vsize, raw, rsize))
def text_at(addr):
    rva = addr - base
    for va, vsize, raw, rsize in secs:
        if va <= rva < va + vsize:
            off = raw + rva - va
            end = exe.index(b"\0", off)
            t = exe[off:end]
            if len(t) > 3 and all(32 <= c < 127 for c in t):
                return t.decode()
            # maybe utf-16
            end = off
            while exe[end:end+2] != b"\0\0": end += 2
            try:
                u = exe[off:end].decode("utf-16-le")
                if u.isprintable() and len(u) > 3: return u
            except Exception: pass
    return None
pending = None
for path in sys.argv[2:]:
    for line in open(path, encoding="ascii", errors="replace"):
        m = re.search(r"([0-9A-F]{16}): lea\s+r\w+,\[0000000(14[0-9A-F]+)h\]", line)
        if m:
            t = text_at(int(m.group(2), 16))
            if t and ("." in t or t.startswith("Gameplay")):
                pending = (m.group(1), t)
            continue
        m = re.search(r"([0-9A-F]{16}): lea\s+rdx,\[(r\w+)\+([0-9A-F]+)h\]", line)
        if m and pending:
            print(f"{pending[0][-8:]} +0x{int(m.group(3),16):X} ({m.group(2)})  {pending[1]}")
            pending = None
