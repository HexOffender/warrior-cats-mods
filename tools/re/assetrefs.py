"""Find the game's packages by what their headers name: words in their name maps, or another package they
import objects from. Reads only the start of each package (its header), so a scan of every package takes
about a minute and a half with wcmods' own Kraken decoder.

usage: assetrefs.py <game folder> names <word> [more words...]    packages whose name map has a name
                                                                    containing a word ("QuestDialogue")
       assetrefs.py <game folder> imports <package path start>    packages importing objects of packages whose
                                                                    path starts so ("/Game/Quests/NpcDialogues/")

Both look at the .uasset and .umap packages of pakchunk0's container. How the dialogue graphs were found
(docs/reverse-engineering.md, "Dialogue graphs"); the header layout is in its "Cooked packages" part.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # the repository
from wcmods.formats.cooked import FormatError, ZenPackage  # noqa: E402
from wcmods.formats.iostore import IoStoreReader  # noqa: E402
from wcmods.formats.oodle import Oodle  # noqa: E402


def header(io, ucas, path, size=0x8000):
    """The first bytes of a package: enough for its header (read again with more if the header is longer)."""
    offset, length = io.chunk_ranges[io.files[path]]
    while True:
        want = min(size, length)
        first, last = offset // io.block_size, (offset + want - 1) // io.block_size
        parts = []
        for b in range(first, last + 1):
            boff, csize, usize, method = io.blocks[b]
            ucas.seek(boff)
            raw = ucas.read(csize)
            parts.append(raw[:usize] if method == 0 else io.oodle.decompress(raw, usize))
        data = b"".join(parts)[offset - first * io.block_size:][:want]
        need = struct.unpack_from("<I", data, 4)[0]          # HeaderSize
        if need <= len(data) or want == length:
            return data
        size = need


def imported(pkg):
    """[(package name, public export hash)] of the objects a package imports from other packages."""
    s = pkg.summary
    hashes = struct.unpack_from(f"<{(s[7] - s[6]) // 8}Q", pkg.data, s[6])
    names = pkg.imported_packages()
    return [(names[v >> 32 & 0x3FFFFFFF], hashes[v & 0xFFFFFFFF]) for v in pkg.imports() if v >> 62 == 2]


def main(argv):
    if len(argv) < 4 or argv[2] not in ("names", "imports"):
        sys.exit(__doc__)
    utoc = os.path.join(argv[1], "Wrc", "Content", "Paks", "pakchunk0-Windows.utoc")
    io = IoStoreReader(utoc, Oodle())
    words = argv[3:]
    found = 0
    with open(io.ucas_path, "rb") as ucas:
        for path in sorted(p for p in io.files if p.endswith((".uasset", ".umap"))):
            try:
                pkg = ZenPackage(header(io, ucas, path))
            except (FormatError, struct.error, UnicodeDecodeError) as e:
                print(f"{path}: not read ({e})", file=sys.stderr)
                continue
            if argv[2] == "names":
                hits = sorted({n for n in pkg.names if any(w in n for w in words)})
            else:
                hits = sorted({name for name, _ in imported(pkg) if any(name.startswith(w) for w in words)})
            if hits:
                found += 1
                print(f"{path}: {' '.join(hits)}")
    print(f"{found} packages", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv)
