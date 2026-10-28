"""Write studio/sections/data-notes.json, the Game data page's notes beside the game's rows, from docs/mechanics/.

usage: mechanics_notes.py [<out file>]   (default studio/sections/data-notes.json)

For every backticked token in docs/mechanics/*.md that names a table (`CatSize.csv`) or a key (a dotted name
with a capital in it: `Stamina.RegenRate`, `Gameplay.Exploration.Level.<n>`), it keeps the line the token is
on, with the markdown taken out, and the heading above it:

    { "Stamina.RegenRate": [{ "doc": "exploration.md", "heading": "Stamina", "anchor": "#stamina",
                              "text": "Back when not running: 20 per second (Stamina.RegenRate)" }] }

Tokens are kept as the docs write them; the page matches them to rows (a row whose key is the token or ends
with "." and the token, <x> standing for one part of a key; a table by its file's name). Run it again after
changing the notes, as mechanics_tables.py is after a game update. It reads only the docs: no game needed.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DOCS = os.path.join(REPO, "docs", "mechanics")
OUT = os.path.join(REPO, "studio", "sections", "data-notes.json")
PER_TOKEN = 3   # notes kept for one token: the first lines that mention it

TICKED = re.compile(r"`([^`]+)`")
TABLE = re.compile(r"^[A-Za-z0-9_]+(/[A-Za-z0-9_]+)*\.csv$")
KEY = re.compile(r"^[A-Za-z0-9_<>]+(\.[A-Za-z0-9_<>]+)+$")


def is_token(text):
    """A table's file name, or a key: dotted, with a capital letter, no spaces."""
    if TABLE.match(text):
        return True
    return bool(KEY.match(text)) and any(c.isupper() for c in text) and not text.endswith(".md")


def anchor(heading):
    """The heading's anchor as GitHub makes it: "Jumping, climbing and falling" -> "#jumping-climbing-and-falling"."""
    return "#" + re.sub(r"[^\w\- ]", "", heading.lower()).strip().replace(" ", "-")


def plain(line):
    """A line of markdown as words: no ticks, links, emphasis or list markers; a table row as "first: the rest"."""
    text = line.strip()
    if text.startswith("|"):
        cells = [c.strip() for c in text.strip("|").split("|")]
        cells = [c for c in cells if c]
        text = f"{cells[0]}: {', '.join(cells[1:])}" if len(cells) > 1 else (cells[0] if cells else "")
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "")
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<!\w)[*_](.+?)[*_](?!\w)", r"\1", text)
    text = re.sub(r"^(#+|[-*+]|\d+\.)\s+", "", text)
    return re.sub(r"\s+", " ", text).strip()


LONGEST = 240   # a note longer than this is cut at a word, with "..."


def blocks(markdown):
    """(heading, block) for each paragraph, list item and table row, a paragraph's wrapped lines joined; code,
    comments and table rules left out."""
    heading, current, fenced = "", [], False
    out = []

    def flush():
        if current:
            out.append((heading, " ".join(current)))
            current.clear()
    for line in markdown.splitlines():
        if line.startswith("```"):
            flush()
            fenced = not fenced
            continue
        stripped = line.strip()
        if fenced or stripped.startswith("<!--") or re.match(r"^\|[\s|:-]+\|?$", stripped):
            continue
        m = re.match(r"^#{1,4}\s+(.*)$", line)
        if m:
            flush()
            heading = plain(m.group(1))
            continue
        if not stripped:
            flush()
            continue
        # A new list item or table row starts a block; an indented line goes on with the one before.
        if re.match(r"^\s*([-*+]|\d+\.)\s+", line) or stripped.startswith("|"):
            flush()
        current.append(stripped)
        if stripped.startswith("|"):
            flush()
    flush()
    return out


def sentence(text, token):
    """The sentence of a block that names the token, cut to LONGEST."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text)
    said = next((p for p in parts if token in p), text)
    if len(said) > LONGEST:
        said = said[:LONGEST].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    return said


def notes_from(docs):
    """{token: [{doc, heading, anchor, text}]} from {doc name: its markdown}, the docs in name order. The lines
    listing a page's sources (every table it read) say nothing about one, so they're left out."""
    notes = {}
    for name in sorted(docs):
        for heading, block in blocks(docs[name]):
            text = plain(block)
            if not text or text.startswith("Sources:"):
                continue
            for token in dict.fromkeys(TICKED.findall(block)):
                if not is_token(token):
                    continue
                found = notes.setdefault(token, [])
                note = {"doc": name, "heading": heading, "anchor": anchor(heading) if heading else "",
                        "text": sentence(text, token)}
                if len(found) < PER_TOKEN and note not in found:
                    found.append(note)
    return notes


def read_docs(folder=DOCS):
    docs = {}
    for name in sorted(os.listdir(folder)):
        if name.endswith(".md") and name != "README.md":
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                docs[name] = f.read()
    return docs


def write(out=OUT, folder=DOCS):
    notes = notes_from(read_docs(folder))
    data = {"_help": "Made by tools/re/mechanics_notes.py from docs/mechanics/*.md: run it again after changing them. "
                     "The Game data page shows these lines beside the rows they name."}
    data.update(sorted(notes.items()))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return notes


if __name__ == "__main__":
    found = write(sys.argv[1] if len(sys.argv) > 1 else OUT)
    print(f"{len(found)} tokens, {sum(len(v) for v in found.values())} notes")
