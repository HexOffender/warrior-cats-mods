"""Find code that references strings: RIP-relative LEA and MOV whose target is a string's address.

usage: xrefs.py <exe> [--prefix] "<text>" ...
Each text is looked for as ASCII and as UTF-16 in the exe's data sections. Prints each place it is a
whole string, and the code that points at it:
  lea  `lea r64,[rip+disp32]`: the string's address, passed on (nearly every reference);
  mov  `mov r64,[rip+disp32]`: its first eight bytes, copied inline (rare: see below).
With --prefix, each place a string starts with the text instead ("Gameplay.Exploration.Level." finds
L"Gameplay.Exploration.Level.%d", a pattern a key is built from), with the whole string shown.

A whole string ends with its terminator (\\0, or \\0\\0 in UTF-16, which also has to start at an even
address), so "Turn" doesn't report the code that uses "TurnBasedCombatComponent". What is in front of
it isn't required to be a terminator. A place that follows a character of its kind (the "Turn" of
"EndTurn") is listed only when code points at it, since code pointing there uses it as a string of its
own. Counted on the game's exe (build 26184573, 2026-10-28), over every lea and mov this script finds
whose target starts a whole string of 4 or more characters (TEXT below) in a data section: 230,329 lea
and 105 mov (125 mov counting shorter strings); 104,041 distinct strings, 1,485 of them with no
terminator in front (they follow other data, or are UTF-16 right after a narrow string's last
character), and none of the 76,858 UTF-16 ones at an odd address.
Not found: a pointer to the string kept in a table (uht.py finds those), 32-bit `mov r32,[rip+disp32]`
(its first four bytes) and copies through SSE registers (movups), strings built at runtime. Of those
two forms, 1,496 and 301 point into .rdata at 4 or more printable characters and a terminator, but the
32-bit ones look noisy (many are likely by chance). It is a byte search, not a disassembly: a hit could
in principle sit inside another instruction, but it has to land exactly on the string.

Other scripts import find(image, texts, prefix=False).
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # the repository, for wcmods
from wcmods.exe import pe  # noqa: E402

ENCODINGS = (("ascii", "ascii", 1), ("utf16", "utf-16-le", 2))   # (name, codec, bytes per character)
TEXT = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}   # characters a string holds, for "follows a character of its kind"
IMAGE_SCN_CNT_CODE = 0x20
# REX.W (48, or 4C for r8 to r15), 8D lea or 8B mov, ModRM with mod 00 and rm 101 ([rip+disp32]), disp32.
CODE = re.compile(rb"[\x48\x4c]([\x8b\x8d])[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]")
FORMS = {0x8D: "lea", 0x8B: "mov"}


def places(image, text, prefix=False):
    """[(va, encoding, inside)]: each place `text` is a whole string in the image's data sections (with
    `prefix`, each place a string starts with it: the terminator after it isn't required), `inside` being
    True when it follows a character of its kind (it may be inside a longer string)."""
    out = []
    raw = image.raw
    for name, codec, unit in ENCODINGS:
        try:
            pat = text.encode(codec)
        except UnicodeEncodeError:
            continue
        if not pat:
            continue
        zero = b"\0" * unit
        for s in image.sections:
            if s.flags & IMAGE_SCN_CNT_CODE:
                continue
            lo, hi = s.raw, s.raw + min(s.rawsize, s.vsize)
            i = raw.find(pat, lo, hi)
            while i >= 0:
                va = image.image_base + s.rva + i - s.raw
                end = i + len(pat)
                after = raw[end:end + unit] if end + unit <= hi else (zero if s.vsize > s.rawsize else b"")
                if (prefix or after == zero) and va % unit == 0:
                    if unit == 1:
                        inside = i > lo and raw[i - 1] in TEXT
                    else:
                        inside = i - 2 >= lo and raw[i - 1] == 0 and raw[i - 2] in TEXT
                    out.append((va, name, inside))
                i = raw.find(pat, i + 1, hi)
    return sorted(out)


def references(image, targets):
    """{target va: [(instruction va, "lea" or "mov")]} for the code section's RIP-relative lea and mov
    that point at one of `targets` (virtual addresses)."""
    out = {va: [] for va in targets}
    if not out:
        return out
    code = image.text
    data, start = code.data, image.image_base + code.rva
    for m in CODE.finditer(data):
        i = m.start()
        if i + 7 > len(data):
            break
        target = start + i + 7 + struct.unpack_from("<i", data, i + 3)[0]
        if target in out:
            out[target].append((start + i, FORMS[data[i + 1]]))
    return out


def find(image, texts, prefix=False):
    """{text: [(va, encoding, [(instruction va, form), ...])]}: each place each text is a whole string
    (see the module's notes; with `prefix`, each place a string starts with it), in address order, with
    the code that points at it. A place that may be inside a longer string is left out when nothing
    points at it. `image` is a wcmods.exe.pe.Image or the exe's path."""
    if not isinstance(image, pe.Image):
        image = pe.Image(image)
    found = {text: places(image, text, prefix) for text in texts}
    refs = references(image, {va for spots in found.values() for va, _, _ in spots})
    return {text: [(va, enc, refs[va]) for va, enc, inside in spots if refs[va] or not inside]
            for text, spots in found.items()}


def string_at(image, va, encoding, limit=256):
    """The string at `va` ("ascii" or "utf16"), up to its terminator or `limit` characters."""
    codec, unit = next((codec, unit) for name, codec, unit in ENCODINGS if name == encoding)
    data = image.read(va - image.image_base, limit * unit)
    for k in range(0, len(data) - unit + 1, unit):
        if data[k:k + unit] == b"\0" * unit:
            data = data[:k]
            break
    return data[:len(data) - len(data) % unit].decode(codec, "replace")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    prefix = "--prefix" in argv
    args = [a for a in argv if a != "--prefix"]
    if len(args) < 2:
        sys.exit(__doc__)
    image = pe.Image(args[0])
    result = find(image, args[1:], prefix)

    def shown(text, va, enc):   # with --prefix, the whole string that starts with the text
        return string_at(image, va, enc) if prefix else text

    print("strings:")
    for text, spots in result.items():
        for va, enc, _ in spots:
            print(f"  {va:#x} {enc} {shown(text, va, enc)!r}")
        if not spots:
            print(f"  {text!r}: " + ("no string in the exe starts with it (or only inside longer ones)" if prefix
                                     else "not in the exe as a whole string (or only inside longer ones)"))
    print("references:")
    for text, spots in result.items():
        for va, enc, refs in spots:
            listed = ", ".join(f"{form} {at:#x}" for at, form in refs[:12])
            more = f" ({len(refs)} in all)" if len(refs) > 12 else ""
            print(f"  {shown(text, va, enc)!r} ({enc} @{va:#x}): {listed or 'none'}{more}")


if __name__ == "__main__":
    main()
