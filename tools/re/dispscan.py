"""Find code that uses several members of one struct: SSE float instructions with those displacements.

usage: dispscan.py <exe> <hex offsets, comma-separated> [how many must appear]
e.g.   dispscan.py Wrc-Win64-ShippingDRM.exe 38C,390,394,398,39C 4

Once a loader shows which members hold some tuning values (tunemap.py, storemap.py), this finds
the code that reads them back. It prints each 1 KB block of the exe where at least that many of
the offsets appear as disp32 operands of movss/addss/mulss/subss/divss/comiss and similar. That
is how the damage formula was found (docs/mechanics/combat.md).
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uht import Exe  # noqa: E402

if len(sys.argv) < 3:
    sys.exit(__doc__)
exe = Exe(sys.argv[1])
offsets = [int(x, 16) for x in sys.argv[2].split(",")]
need = int(sys.argv[3]) if len(sys.argv) > 3 else len(offsets)

blocks = {}
for d in offsets:
    disp = re.escape(struct.pack("<I", d))
    # F3 [REX] 0F op modrm(mod=10) disp32: movss/addss/mulss/subss/minss/divss/maxss and the store.
    sse = re.compile(rb"\xF3[\x40-\x4F]?\x0F[\x10\x11\x58\x59\x5C\x5D\x5E\x5F][\x80-\xBF]" + disp)
    # [REX] 0F 2E/2F modrm disp32: ucomiss/comiss.
    cmp = re.compile(rb"[\x40-\x4F]?\x0F[\x2E\x2F][\x80-\xBF]" + disp)
    for pattern in (sse, cmp):
        for m in pattern.finditer(exe.data):
            blocks.setdefault(m.start() // 0x400, set()).add(d)
for block, found in sorted(blocks.items()):
    if len(found) >= need:
        print(hex(exe.va(block * 0x400)), " ".join(hex(x) for x in sorted(found)))
