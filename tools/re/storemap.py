"""Map tuning keys to the members a loader stores them in, for loaders that store straight to `this`.

usage: storemap.py <exe> <dumpbin listing>

tunemap.py handles loaders that pass `lea rdx,[reg+offset]` as the out parameter. Others read a
key and then `movss dword ptr [rbx+offset],xmm0`. This pairs each `lea rdx,[<string>]` with the next
store to `[reg+offset]`, e.g. for the combat loader at 0x1417D7940:
  417D7A6F rbx+0x38C movss Gameplay.Combat.Damage.Formula.Universal.Factor
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uht import Exe  # noqa: E402

if len(sys.argv) < 3:
    sys.exit(__doc__)
exe = Exe(sys.argv[1])
key = at = None
for line in open(sys.argv[2]):
    m = re.search(r"([0-9A-F]{16}): lea\s+rdx,\[([0-9A-F]{16})h\]", line)
    if m:
        key, at = exe.cstr(int(m.group(2), 16)), m.group(1)
        continue
    m = re.search(r"[0-9A-F]{16}: (movss|movsd|mov)\s+(?:dword|qword|byte) ptr \[(r\w+)\+([0-9A-F]+)h\],\w+", line)
    if m and key:
        print(at[-8:], f"{m.group(2)}+0x{int(m.group(3), 16):X}", m.group(1), key)
        key = None
