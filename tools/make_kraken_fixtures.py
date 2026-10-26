"""Make the Kraken fixtures in tests/kraken with an oo2core DLL's own compressor.

    python tools/make_kraken_fixtures.py "C:\\...\\oo2core_8_win64.dll"

The inputs are wcmods.selftest.kraken_samples(), generated the same every time, so only the
compressed bytes are kept; the self-test decodes each fixture with wcmods.kraken and compares.
Levels 1, 5 and 8 take different paths through Oodle's encoder (and so the decoder).
"""
import ctypes
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wcmods.selftest import kraken_samples  # noqa: E402

KRAKEN = 8   # OodleLZ_Compressor_Kraken
LEVELS = (1, 5, 8)


def main(dll_path):
    dll = ctypes.WinDLL(dll_path)
    compress = dll.OodleLZ_Compress
    compress.restype = ctypes.c_int
    compress.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int,
                         ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
    folder = os.path.join(os.path.dirname(HERE), "tests", "kraken")
    os.makedirs(folder, exist_ok=True)
    manifest = []
    for name, raw in kraken_samples().items():
        for level in LEVELS if name != "noise" else (5,):
            out = ctypes.create_string_buffer(len(raw) + 0x40000)
            n = compress(KRAKEN, raw, len(raw), out, level, None, 0, 0, None, 0)
            if n <= 0:
                sys.exit(f"{name} level {level}: OodleLZ_Compress failed ({n})")
            file = f"{name}-L{level}.kraken"
            with open(os.path.join(folder, file), "wb") as f:
                f.write(out.raw[:n])
            manifest.append({"file": file, "sample": name, "level": level, "size": len(raw),
                             "sha1": hashlib.sha1(raw).hexdigest()})
            print(f"{file}: {len(raw)} -> {n}")
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
