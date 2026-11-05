"""Sort TuningData's keys by what the game's code says of them.

usage: tuning_read.py <exe> <TuningData.csv> [--build N] [--out wcmods/exe/tuning_read.json]

Each key goes into one of three groups (docs/plans/re-roadmap.md, the tuning plan's static part):
- read: a lea or mov in the code points at the key as a whole string;
- pattern: for the rest, the code points at a format string that starts with one of the key's dotted prefixes
  ("Gameplay.Exploration.Level.%d"), or at the prefix itself, with its dot, as a whole string (three parts or more;
  without the dot it may be a tag of the same name), so the code may build the key at runtime;
- not_named: everything else, which nothing in the code names.

It writes {"made_on": <build>, "read": [...], "pattern": {"<key>": "<the format string or prefix>"}, "not_named": [...]}. A key that's
"not named" may still be read (through a table the game builds from another), but nothing names it directly.
"""
import argparse
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)

import xrefs  # noqa: E402
from wcmods.exe import pe  # noqa: E402

MIN_PARTS = 3   # "Gameplay.Exploration" alone is named everywhere: a prefix says something from three parts on


def keys_of(csv_path):
    """TuningData's keys, in the file's order (its first column; the header row skipped)."""
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return [r[0] for r in rows[1:] if r and r[0]]


def prefixes(key):
    """The key's dotted prefixes from the longest down to MIN_PARTS parts, each with its dot and without:
    "A.B.C.D" -> ["A.B.C.", "A.B.C"]."""
    parts = key.split(".")
    out = []
    for n in range(len(parts) - 1, MIN_PARTS - 1, -1):
        head = ".".join(parts[:n])
        out += [head + ".", head]
    return out


def makes(fmt, key):
    """Whether a format string can make the key: %d and %i a number, %s and {n} any text without a dot. A format
    that ends with its placeholder only has to start the key: the code adds the rest ("...Detection.%s", then
    ".PlayerZone.EntryDistance"); one with text after it has to make all of it ("...Player.%s.Scale")."""
    ends_open = bool(re.search(r"(%[-+ #0]*\d*(?:\.\d+)?[a-zA-Z]|\{[^}]*\})$", fmt))
    rx = ""
    i = 0
    while i < len(fmt):
        spec = re.match(r"%[-+ #0]*\d*(?:\.\d+)?([a-zA-Z])", fmt[i:]) if fmt[i] == "%" else None
        if fmt.startswith("%%", i):
            rx += "%"
            i += 2
        elif spec:
            rx += r"\d+" if spec.group(1) in "diu" else r"[^.]+"
            i += spec.end()
        elif fmt[i] == "{":
            j = fmt.find("}", i)
            rx += r"[^.]+"
            i = j + 1 if j > 0 else len(fmt)
        else:
            rx += re.escape(fmt[i])
            i += 1
    return (re.match(rx, key) if ends_open else re.fullmatch(rx, key)) is not None


def sort(image, keys):
    """The three groups for these keys, from the image's code (see the module's notes)."""
    if not isinstance(image, pe.Image):
        image = pe.Image(image)
    named = xrefs.find(image, keys)
    read = [k for k in keys if any(refs for _, _, refs in named.get(k, []))]
    rest = [k for k in keys if k not in set(read)]
    wanted = sorted({p for k in rest for p in prefixes(k)})
    found = xrefs.find(image, wanted)
    whole = {p for p, spots in found.items() if any(refs for _, _, refs in spots)}
    # Format strings the code points at, starting with a dotted prefix: "Gameplay.Exploration.Level.%d".
    formats = {}
    dotted = [p for p in wanted if p.endswith(".")]
    for p, spots in xrefs.find(image, dotted, prefix=True).items():
        for va, enc, refs in spots:
            text = xrefs.string_at(image, va, enc) if refs else ""
            if text.startswith(p) and ("%" in text[len(p):] or "{" in text[len(p):]):
                formats.setdefault(p, []).append(text)
    pattern, not_named = {}, []
    for k in rest:
        hit = None
        for p in prefixes(k):
            # A format string only when it can make the key ("...Player.%s.Scale" isn't "...Player.Run.Speed").
            hit = next((f for f in formats.get(p, []) if makes(f, k)), None) or (p if p in whole and p.endswith(".") else None)
            if hit:
                break
        if hit:
            pattern[k] = hit
        else:
            not_named.append(k)
    return {"read": read, "pattern": pattern, "not_named": not_named}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("exe")
    ap.add_argument("tuning_csv")
    ap.add_argument("--build", type=int, default=None, help="the game build the exe is (written as made_on)")
    ap.add_argument("--out", default=None, help="where to write the JSON (default: print it)")
    a = ap.parse_args(argv)
    result = {"made_on": a.build, **sort(a.exe, keys_of(a.tuning_csv))}
    text = json.dumps(result, indent=1, ensure_ascii=False) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"{a.out}: {len(result['read'])} read, {len(result['pattern'])} built from a pattern, "
              f"{len(result['not_named'])} not named")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
