"""The guide inside Clan Mod Studio: docs/guide/<page>.md rendered to HTML for the studio's help panel.

A small Markdown renderer, enough for the guide's pages: headings, paragraphs, bullet and numbered lists
(one level), fenced code, bold, italic, inline code, links and pictures. It emits only the tags in TAGS,
which the studio's panel allows and nothing else; a link to another page of the guide (`studio.md`,
`studio.md#the-log`) opens in the panel, and a picture comes from docs/guide/images/.
"""
import html
import os
import re

TAGS = ("h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "strong", "em", "code", "pre", "a", "img", "hr", "blockquote")
PAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")   # a page's name: docs/guide/<name>.md
IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.(png|jpg|jpeg|gif|webp|svg)$", re.I)
INDEX = "README"                                   # the guide's first page, docs/guide/README.md


def folder(root):
    return os.path.join(root, "docs", "guide")


def pages(root):
    """The names of the guide's pages (README first)."""
    where = folder(root)
    names = sorted(n[:-3] for n in os.listdir(where) if n.endswith(".md") and PAGE.match(n[:-3])) \
        if os.path.isdir(where) else []
    return [INDEX] + [n for n in names if n != INDEX] if INDEX in names else names


def read(root, page):
    """A page's Markdown, by name; LookupError when there's no such page."""
    if not PAGE.match(page or ""):
        raise LookupError(f"there's no help page {page!r}")
    path = os.path.join(folder(root), page + ".md")
    if not os.path.isfile(path):
        raise LookupError(f"there's no help page {page!r}")
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def title(markdown):
    """The page's first heading, or ''."""
    for line in markdown.splitlines():
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            return _plain(m.group(1))
    return ""


def render(markdown):
    """Markdown -> HTML, the guide's subset."""
    out, lines, i = [], markdown.replace("\r\n", "\n").split("\n"), 0
    para = []

    def flush():
        if para:
            out.append(f"<p>{_inline(' '.join(s.strip() for s in para))}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush()
            i += 1
            continue
        if stripped.startswith("```"):
            flush()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", stripped)
        if m:
            flush()
            level = min(len(m.group(1)), 4)
            text = m.group(2)
            out.append(f'<h{level} id="{slug(text)}">{_inline(text)}</h{level}>')
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush()
            out.append("<hr>")
            i += 1
            continue
        m = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", stripped)
        if m:
            flush()
            tag = "ol" if m.group(1)[0].isdigit() else "ul"
            items = []
            while i < len(lines):
                m = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", lines[i].strip())
                if not m or (("ol" if m.group(1)[0].isdigit() else "ul") != tag):
                    break
                item = [m.group(2)]
                i += 1
                # An item goes on over indented lines that aren't items themselves.
                while i < len(lines) and lines[i].strip() and lines[i].startswith(("  ", "\t")) \
                        and not re.match(r"^([-*+]|\d+[.)])\s+", lines[i].strip()):
                    item.append(lines[i].strip())
                    i += 1
                items.append(f"<li>{_inline(' '.join(item))}</li>")
            out.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue
        if stripped.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f"<blockquote><p>{_inline(' '.join(q for q in quote if q))}</p></blockquote>")
            continue
        para.append(line)
        i += 1
    flush()
    return "\n".join(out)


def slug(text):
    """A heading's id, as GitHub makes them: lower case, spaces as hyphens, punctuation gone."""
    s = re.sub(r"[^\w\s-]", "", _plain(text).lower()).strip()
    return re.sub(r"[\s]+", "-", s)


def _plain(text):
    """Inline Markdown with its marks taken off (for a title or a slug)."""
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[*_`]", "", text)


def _inline(text):
    """Inline marks -> HTML: code first (nothing inside it is a mark), then pictures, links, bold, italic."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append(f"<code>{html.escape(p[1:-1])}</code>")
        else:
            out.append(_marks(p))
    return "".join(out)


def _marks(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: _image(m.group(1), m.group(2)), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: _link(m.group(1), m.group(2)), text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<em>\1</em>", text)
    return text


def _quote(s):
    """For an attribute: the text is escaped already (_marks), so only the quotes are left to do."""
    return s.replace('"', "&quot;")


def _image(alt, src):
    name = src.split("/")[-1]
    if not src.startswith(("images/", "./images/")) or not IMAGE.match(name):
        return alt
    return f'<img src="/help/images/{_quote(name)}" alt="{_quote(alt)}">'


def _link(text, href):
    """Another page of the guide opens in the panel; a page of the repository's docs, on GitHub; a web
    address, in a new tab. Anything else (javascript:, a file) is left as text."""
    m = re.match(r"^(?:\./)?([A-Za-z0-9][A-Za-z0-9_-]*)\.md(#[\w-]*)?$", href)
    if m:
        return f'<a href="/help/{m.group(1)}{m.group(2) or ""}">{text}</a>'
    if href.startswith("#"):
        return f'<a href="{_quote(href)}">{text}</a>'
    # The guide is in docs/guide/: one ../ is docs/, two is the repository's root.
    m = re.match(r"^((?:\.\./)+)([\w-][\w./-]*\.md(?:#[\w-]*)?)$", href)
    if m and ".." not in m.group(2):
        up = m.group(1).count("../")
        where = ("docs/" if up == 1 else "") + m.group(2)
        return f'<a href="{DOCS}{_quote(where)}" target="_blank" rel="noopener">{text}</a>'
    if re.match(r"^https?://", href):
        return f'<a href="{_quote(href)}" target="_blank" rel="noopener">{text}</a>'
    return text


DOCS = "https://github.com/HexOffender/warrior-cats-mods/blob/main/"


def page_html(page_title, body):
    """A whole page, in the studio's look, for /help/<page> opened on its own."""
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<meta name=\"color-scheme\" content=\"light dark\">\n"
        f"<title>{html.escape(page_title or 'Help')} · Clan Mod Studio</title>\n"
        "<link rel=\"stylesheet\" href=\"/studio/styles.css\">\n</head>\n"
        f"<body class=\"help-page\">\n<article class=\"help-body\">\n{body}\n</article>\n</body>\n</html>\n")
