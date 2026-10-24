"""Find the direct calls and jumps (E8/E9 rel32) to functions in the exe.

usage: callers.py <exe> <function address> [more addresses...]
e.g.   callers.py Wrc-Win64-ShippingDRM.exe 1417D87A0

One pass over the code section; prints how many places call each address and the first 24.
Calls through vtables or pointers aren't found.
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
targets = {int(a, 16): [] for a in sys.argv[2:]}
vsize, va, rsize, raw = exe.sections[0]    # .text comes first
base = exe.base + va - raw
for m in re.finditer(rb"[\xE8\xE9]", exe.data[raw:raw + rsize]):
    at = raw + m.start()
    if base + at + 5 + struct.unpack_from("<i", exe.data, at + 1)[0] in targets:
        targets[base + at + 5 + struct.unpack_from("<i", exe.data, at + 1)[0]].append(hex(base + at))
for target, found in targets.items():
    print(hex(target), len(found), " ".join(found[:24]))
