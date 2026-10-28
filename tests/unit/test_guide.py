"""The creator guide (docs/guide/, the studio's Help panel) and the docs around it hold together: every link
and #anchor in README.md, docs/*.md and docs/guide/*.md leads somewhere; the guide's pages use only what the
panel draws (no tables, no lists in lists), no command lines and no em dashes; each Make page has its six
parts in order; the glossary links name a word the glossary has; the index lists every page once; and each
page renders through wcmods/guide.py with no Markdown left showing."""
import glob
import os
import re

import pytest

from unit_helpers import REPO
from wcmods import guide

GUIDE = os.path.join(REPO, "docs", "guide")
INDEX = os.path.join(GUIDE, "README.md")
GLOSSARY = "Words you'll meet"   # the index's part with the words other pages link (### headings)
# The studio's Make pages, each with a guide page of the same name, and the six parts each of those has.
MAKE_PAGES = ("palettes", "cat", "controls", "names", "items", "animations", "characters", "questlines", "data",
              "save", "tweaks", "console")
SIX_PARTS = ("What it changes in the game", "A five-minute first try", "What you can and can't do",
             "Did it reach the game?", "Common mistakes", "Undo")

LINK = re.compile(r"!?\[((?:[^\[\]]|\[[^\]]*\])*)\]\(([^)\s]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def rel(path):
    return os.path.relpath(path, REPO).replace(os.sep, "/")


def guide_pages():
    return sorted(glob.glob(os.path.join(GUIDE, "*.md")))


def checked_docs():
    """README.md, docs/*.md and docs/guide/*.md: the docs whose links are checked."""
    return [os.path.join(REPO, "README.md")] + sorted(glob.glob(os.path.join(REPO, "docs", "*.md"))) + guide_pages()


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def unfenced(text):
    """(line number, line) for every line outside fenced code."""
    fenced = False
    for n, line in enumerate(text.split("\n"), 1):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            yield n, line


def prose_lines(text):
    """unfenced(), with inline code spans blanked out (a link or a mark inside backticks is code, not
    Markdown)."""
    for n, line in unfenced(text):
        yield n, re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line)


def code_spans(text):
    """(line number, text) of every inline code span and every line of fenced code."""
    fenced = False
    for n, line in enumerate(text.split("\n"), 1):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            yield n, line
        else:
            for m in re.finditer(r"`([^`]*)`", line):
                yield n, m.group(1)


def headings(text):
    """[(level, text)] of the Markdown headings outside fenced code."""
    out = []
    for _, line in unfenced(text):
        m = HEADING.match(line)
        if m:
            out.append((len(m.group(1)), m.group(2)))
    return out


def github_slug(text):
    """A heading's anchor on GitHub: its text without marks, lower case, everything but letters, digits, spaces,
    hyphens and underscores dropped, then each space a hyphen."""
    return re.sub(r"[^\w\- ]", "", guide._plain(text).strip().lower()).replace(" ", "-")


def anchors(path, slug):
    """The anchors of a doc's headings by `slug`, with GitHub's -1, -2... on headings that repeat."""
    found, seen = set(), {}
    for _, text in headings(read(path)):
        s = slug(text)
        if s in seen:
            seen[s] += 1
            found.add(f"{s}-{seen[s]}")
        else:
            seen[s] = 0
            found.add(s)
    return found


def links(path):
    """(line number, link text, href) for every relative link and picture in a doc (web addresses left out)."""
    raw = dict(unfenced(read(path)))
    for n, line in prose_lines(read(path)):
        for m in LINK.finditer(line):
            href = raw[n][m.start(2):m.end(2)]
            if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):   # https:, mailto:
                continue
            yield n, raw[n][m.start(1):m.end(1)], href


def in_guide(path):
    return os.path.dirname(os.path.abspath(path)) == os.path.abspath(GUIDE)


def glossary():
    """The anchors of the glossary's words: the ### headings under the index's Words you'll meet."""
    words, inside = set(), False
    for level, text in headings(read(INDEX)):
        if level == 2:
            inside = text == GLOSSARY
        elif level == 3 and inside:
            words.add(guide.slug(text))
    return words


def test_the_guide_has_its_pages():
    names = {os.path.basename(p)[:-3] for p in guide_pages()}
    assert {"README", "studio", "mods", "companion-mods", "packs", "settings"} | set(MAKE_PAGES) <= names
    assert glossary() >= {"slot", "script-loader", "code-mods", "sandbox-mode", "menu-pages", "mod-menu",
                          "build-log", "game-build"}


def test_every_link_and_anchor_leads_somewhere():
    """Each relative link names a file or folder that's there and, with #, one of its headings: by the guide's
    own rule (wcmods/guide.py) for a guide page, and by GitHub's too when the link is read on GitHub (from
    outside the guide); by GitHub's for every other doc."""
    broken, count = [], 0
    for path in checked_docs():
        for n, text, href in links(path):
            count += 1
            target, _, anchor = href.partition("#")
            dest = os.path.normpath(os.path.join(os.path.dirname(path), target)) if target else path
            where = f"{rel(path)}:{n}: [{text}]({href})"
            if not os.path.exists(dest):
                broken.append(f"{where}: there's no {rel(dest)}")
                continue
            if not anchor:
                continue
            if not dest.endswith(".md") or os.path.isdir(dest):
                broken.append(f"{where}: an anchor on something that isn't a doc")
                continue
            if in_guide(dest):
                ok = anchor in anchors(dest, guide.slug) and (in_guide(path) or anchor in anchors(dest, github_slug))
            else:
                ok = anchor in anchors(dest, github_slug)
            if not ok:
                broken.append(f"{where}: {rel(dest)} has no heading #{anchor}")
    assert count > 300, count
    assert not broken, "\n".join(broken)


def test_glossary_links_name_a_word_the_glossary_has():
    """A link to the index with an anchor (from a guide page, the README or a doc) names one of the words under
    Words you'll meet, so it lands on the word, not on another part of the index."""
    words, wrong, count = glossary(), [], 0
    for path in checked_docs():
        for n, text, href in links(path):
            target, _, anchor = href.partition("#")
            dest = os.path.normpath(os.path.join(os.path.dirname(path), target)) if target else path
            if not anchor or os.path.normcase(dest) != os.path.normcase(INDEX):
                continue
            count += 1
            if anchor not in words:
                wrong.append(f"{rel(path)}:{n}: [{text}]({href}) isn't one of the words: {sorted(words)}")
    assert count > 50, count
    assert not wrong, "\n".join(wrong)


@pytest.mark.parametrize("page", [os.path.basename(p) for p in guide_pages()])
def test_guide_pages_use_only_what_the_panel_draws(page):
    """No tables (the panel has none), no list inside a list item (it draws lists one level deep), no em dash,
    no HTML, and one # title."""
    text, problems = read(os.path.join(GUIDE, page)), []
    for n, line in prose_lines(text):
        if line.lstrip().startswith("|"):
            problems.append(f"{n}: a table: {line.strip()}")
        if re.match(r"^\s+([-*+]|\d+[.)])\s", line):
            problems.append(f"{n}: a list inside a list: {line.strip()}")
        if "—" in line:
            problems.append(f"{n}: an em dash: {line.strip()}")
        if re.search(r"</?[a-zA-Z][^>]*>", line):
            problems.append(f"{n}: HTML: {line.strip()}")
    titles = [h for h in headings(text) if h[0] == 1]
    if len(titles) != 1:
        problems.append(f"{len(titles)} # titles, not one")
    assert not problems, page + "\n" + "\n".join(problems)


@pytest.mark.parametrize("page", [os.path.basename(p) for p in guide_pages()])
def test_guide_pages_have_no_command_lines(page):
    """A creator never types a command: no `python ...`, no ` --flag`, and no .bat to run from code (a file
    the studio names, such as Play with key remaps.bat, is double-clicked, so it's plain words)."""
    text, problems = read(os.path.join(GUIDE, page)), []
    for n, line in prose_lines(text):
        if re.search(r"\bpython ", line, re.I) or re.search(r"(^|\s)--[a-z]", line):
            problems.append(f"{n}: {line.strip()}")
    for n, code in code_spans(text):
        if re.search(r"\bpython\b|\.bat\b|(^|\s)--[a-z]|wcmods\.py", code, re.I):
            problems.append(f"{n}: `{code}`")
    assert not problems, page + "\n" + "\n".join(problems)


@pytest.mark.parametrize("page", MAKE_PAGES)
def test_make_pages_have_the_six_parts_in_order(page):
    text = read(os.path.join(GUIDE, page + ".md"))
    assert tuple(t for level, t in headings(text) if level == 2) == SIX_PARTS


def test_the_index_lists_every_page_once():
    """The index's lists, above Words you'll meet, link each guide page once and nothing that isn't one."""
    text = read(INDEX)
    lists = text.split(f"## {GLOSSARY}")[0]
    listed = []
    for n, line in prose_lines(lists):
        if re.match(r"^[-*]\s", line):
            m = LINK.search(line)
            assert m, f"docs/guide/README.md:{n}: a list line with no page: {line.strip()}"
            listed.append(m.group(2).partition("#")[0])
    pages = sorted(os.path.basename(p) for p in guide_pages() if os.path.basename(p) != "README.md")
    assert sorted(listed) == pages, (sorted(listed), pages)


@pytest.mark.parametrize("page", [os.path.basename(p)[:-3] for p in guide_pages()])
def test_guide_pages_render_with_no_markdown_left(page):
    """Through wcmods/guide.py, as the Help panel shows them: no ** or ]( left in the words (a bold label split
    badly, or a link the renderer doesn't take), and only the panel's tags."""
    html = guide.render(guide.read(REPO, page))
    words = re.sub(r"<(pre|code)>.*?</\1>", "", html, flags=re.S)
    for left in ("**", "]("):
        assert left not in words, f"{page}: {left!r} near: {words[max(0, words.find(left) - 80):words.find(left) + 80]}"
    tags = set(re.findall(r"</?([a-z0-9]+)", html))
    assert tags <= set(guide.TAGS), tags - set(guide.TAGS)
    assert guide.title(guide.read(REPO, page))
