"""Check wcmods' Kraken decoder against an oo2core DLL on the game's own files.

    python tools/verify_kraken.py [--ucas N] [--pak N] [--seed S] [--files]

Takes N random compressed blocks from the IoStore container and N compressed pak entries (every
block of each), decodes each with wcmods.kraken and with the DLL named by "oodle_dll" in
wcmods.json, and compares. --files adds every block of the item table, the GUI manager Blueprint
and the eye atlas, the cooked assets wcmods patches. The self-test does a small version of this;
run this after a game update, or after touching kraken.py, with a few thousand blocks.
"""
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from wcmods.formats import kraken  # noqa: E402
from wcmods.config import Config  # noqa: E402
from wcmods.formats.iostore import IoStoreReader  # noqa: E402
from wcmods.formats.oodle import Oodle  # noqa: E402
from wcmods.formats.pak import PakReader, _entry_header_size  # noqa: E402


def main(args):
    def opt(name, default):
        return int(args[args.index(name) + 1]) if name in args else default
    n_ucas, n_pak, seed = opt("--ucas", 200), opt("--pak", 50), opt("--seed", 1)
    cfg = Config(ROOT)
    if not cfg.oodle_dll:
        sys.exit('set "oodle_dll" in wcmods.json to an oo2core_*_win64.dll to compare against')
    dll = Oodle(cfg.oodle_dll)
    rng = random.Random(seed)
    stats = {"ok": 0, "bad": 0, "in": 0, "out": 0, "t_py": 0.0, "t_dll": 0.0}

    def check(label, raw, usize):
        t0 = time.perf_counter()
        want = dll.decompress(raw, usize)
        stats["t_dll"] += time.perf_counter() - t0
        t0 = time.perf_counter()
        try:
            got = kraken.decompress(raw, usize)
            problem = None
        except kraken.KrakenError as e:
            got, problem = None, str(e)
        stats["t_py"] += time.perf_counter() - t0
        stats["in"] += len(raw)
        stats["out"] += usize
        if got == want:
            stats["ok"] += 1
            return
        stats["bad"] += 1
        if problem is None:
            first = next((i for i in range(usize) if got[i] != want[i]), usize)
            problem = f"differs at byte {first} of {usize}"
        print(f"FAIL {label}: {problem}")

    io = IoStoreReader(os.path.join(cfg.paks_dir, "pakchunk0-Windows.utoc"))
    compressed = [i for i, (_, _, _, m) in enumerate(io.blocks) if m]
    with open(io.ucas_path, "rb") as f:
        for bi in rng.sample(compressed, min(n_ucas, len(compressed))):
            boff, csize, usize, _ = io.blocks[bi]
            f.seek(boff)
            check(f"ucas block {bi} ({csize} -> {usize})", f.read(csize), usize)
        if "--files" in args:
            from wcmods import accessories, eyeatlas
            from wcmods.formats import cooked
            for path in (cooked.TABLES["DT_QuestObjectsInfo"][0], accessories.GUI_MANAGER, eyeatlas.PATH):
                offset, length = io.chunk_ranges[io.chunk_index(path)]
                for bi in range(offset // io.block_size, (offset + length - 1) // io.block_size + 1):
                    boff, csize, usize, method = io.blocks[bi]
                    if method:
                        f.seek(boff)
                        check(f"{path} block {bi}", f.read(csize), usize)

    pak = PakReader(os.path.join(cfg.paks_dir, "pakchunk0-Windows.pak"))
    entries = [(p, e) for p, e in pak.entries.items() if e.method and e.block_sizes]
    with open(pak.path, "rb") as f:
        for p, e in rng.sample(entries, min(n_pak, len(entries))):
            pos = e.offset + _entry_header_size(e)
            for k, csize in enumerate(e.block_sizes):
                f.seek(pos)
                want = min(e.block_size, e.raw_size - k * e.block_size)
                check(f"pak {p} block {k} ({csize} -> {want})", f.read(csize), want)
                pos += csize

    print(f"{stats['ok']} ok, {stats['bad']} bad; {stats['in'] / 1e6:.1f} MB in -> {stats['out'] / 1e6:.1f} MB out; "
          f"python {stats['t_py']:.1f}s ({stats['out'] / 1e6 / max(stats['t_py'], 1e-9):.2f} MB/s), "
          f"dll {stats['t_dll']:.2f}s")
    return 1 if stats["bad"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
