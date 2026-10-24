"""Driving the in-game mod menu from outside: open a page, read what it shows, use its controls.

Each page is drawn by its own script every frame (WCModsMenu); the module answers requests the agent
leaves in shared variables (see "being driven from outside" in menu.py's Lua). A read gives the page's
rows in order, each with its kind (heading, text, note, field, button, switch, toggle, slider, number,
input, choice, radio, color, progress, section), label and value; an action names a row by its label
(any case) or as "@n", its place on the page.
"""
import json
import time
import uuid

from ..sdk import lua_value

PREFIX = "WCModsMenu."
# The side bar's groups in order (Menu.groups in menu.py).
GROUPS = ("home", "cat", "world", "story", "fight", "cheats", "mods", "tools")
CONTROLS = ("button", "switch", "toggle", "slider", "number", "input", "choice", "radio", "color", "section")


class Row:
    def __init__(self, d):
        self.n, self.kind = d.get("n"), d.get("kind")
        self.label, self.value, self.options = d.get("label"), d.get("value"), d.get("options")

    def __repr__(self):
        return f"<Row {self.n} {self.kind} {self.label!r}={self.value!r}>"

    def line(self):
        """How `wcmods agent menu read` prints it."""
        if self.kind == "heading":
            return f"# {self.value}"
        if self.kind in ("text", "note"):
            return ("  " if self.kind == "note" else "") + str(self.value)
        if self.kind == "section":
            return f"[{'-' if self.value else '+'}] {self.label}"
        if self.kind == "button":
            return f"[ {self.label} ]"
        shown = self.value
        if isinstance(shown, bool):
            shown = "on" if shown else "off"
        extra = ""
        if self.kind in ("radio", "choice") and self.options:
            extra = "   (" + " | ".join(self.options) + ")"
        elif self.kind in ("slider", "number") and self.options:
            lo, hi = (self.options + [None, None])[:2]
            if lo is not None or hi is not None:
                extra = f"   ({lo if lo is not None else ''}..{hi if hi is not None else ''})"
        return f"{self.label}: {shown}{extra}" + ("" if self.kind == "field" else f"   <{self.kind}>")


class Page:
    def __init__(self, d):
        self.id, self.title = d.get("page"), d.get("title")
        self.rows = [Row(r) for r in (d.get("rows") or [])]

    def __repr__(self):
        return f"<Page {self.id!r}, {len(self.rows)} rows>"

    def find(self, label, kind=None):
        """The first row with this label (any case), or None."""
        want = str(label).lower()
        for r in self.rows:
            if r.label is not None and r.label.lower() == want and (kind is None or r.kind == kind):
                return r
        return None

    def get(self, label, default=None):
        """A row's value by its label."""
        r = self.find(label)
        return r.value if r else default

    def has(self, text):
        """Whether any label or value on the page contains `text` (any case)."""
        want = str(text).lower()
        return any(want in str(r.label or "").lower() or want in str(r.value or "").lower() for r in self.rows)

    def errors(self):
        """Rows saying the page hit an error (WCModsMenu shows them in red in place of the rest)."""
        return [r.value for r in self.rows if r.kind == "text" and str(r.value).startswith("This page hit an error")]

    def controls(self):
        return [r for r in self.rows if r.kind in CONTROLS]

    def text(self):
        return "\n".join(r.line() for r in self.rows)


class MenuDriver:
    def __init__(self, agent):
        self.agent = agent

    def _shared(self, name):
        v = self.agent.lua(f"return ModRef:GetSharedVariable({lua_value(PREFIX + name)})")
        return None if v == "nil" else v

    def _share(self, name, value):
        self.agent.lua(f"ModRef:SetSharedVariable({lua_value(PREFIX + name)}, {lua_value(value)}) return true")

    def is_open(self):
        return self._shared("open") is True

    def current(self):
        """The id of the page the menu shows (or last showed)."""
        return self._shared("page") or None

    def pages(self):
        """Every page: [{"id", "title", "order", "group"}], in the side bar's groups."""
        out = []
        for line in str(self._shared("pages") or "").splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                out.append({"id": parts[0], "title": parts[1], "order": float(parts[2] or 50),
                            "group": parts[3] if len(parts) > 3 and parts[3] else "mods"})
        rank = {g: i for i, g in enumerate(GROUPS)}
        out.sort(key=lambda p: (rank.get(p["group"], rank["mods"] + 0.5), p["order"], p["title"]))
        return out

    def page_id(self, page):
        """A page's id from its id or title (any case); raises when there's none."""
        pages = self.pages()
        for p in pages:
            if page in (p["id"], p["title"]):
                return p["id"]
        for p in pages:
            if str(page).lower() in (p["id"].lower(), p["title"].lower()):
                return p["id"]
        raise self.agent.error(f"no menu page {page!r}; there are: " + ", ".join(p["title"] for p in pages))

    def open(self, page=None, timeout=10):
        """Open the menu, on a page (id or title) when given; returns the page that shows, read."""
        want = self.page_id(page) if page else None
        self._share("request", "open\t" + (want or ""))
        self.agent.wait(lambda: self.is_open() and (want is None or self.current() == want),
                        timeout, f"the menu to open{' on ' + repr(page) if page else ''}")
        return self.read(timeout=timeout)

    def close(self, timeout=10):
        if not self.is_open():
            return
        self._share("request", "close\t")
        self.agent.wait(lambda: not self.is_open(), timeout, "the menu to close")

    def read(self, timeout=10):
        """What the page shows now, as a Page."""
        if not self.is_open():
            raise self.agent.error("the menu isn't open (agent.menu.open(page) first)")
        token = uuid.uuid4().hex[:12]
        self._share("agent.read", token)

        def answer():
            raw = self._shared("agent.page")
            if not raw:
                return None
            data = json.loads(raw)
            return data if data.get("token") == token else None

        return Page(self.agent.wait(answer, timeout, "the menu page to answer"))

    def act(self, label, value="", timeout=10):
        """Use a control: press a button or section, or give a switch, slider, box or list a value.
        Returns (kind, label) of the row it used; raises when the page has no such control."""
        if not self.is_open():
            raise self.agent.error("the menu isn't open (agent.menu.open(page) first)")
        if isinstance(value, bool):
            value = "on" if value else "off"
        token = uuid.uuid4().hex[:12]
        clean = lambda s: str(s).replace("\t", " ").replace("\n", " ")
        self._share("agent.act", f"{token}\t{clean(label)}\t{clean(value)}")

        def answer():
            raw = self._shared("agent.done") or ""
            parts = str(raw).split("\t")
            return parts if parts[0] == token else None

        parts = self.agent.wait(answer, timeout, f"the menu to use {label!r}")
        if parts[1] != "ok":
            page = self.read(timeout=timeout)
            names = ", ".join(repr(r.label) for r in page.controls())
            raise self.agent.error(f"page {page.title!r} has no control {label!r}; it has: {names}")
        # The page has run with the change; give the next frame a moment so what it changed shows.
        time.sleep(0.1)
        return parts[2], parts[3]

    def press(self, label, timeout=10):
        return self.act(label, "", timeout)

    def set(self, label, value, timeout=10):
        return self.act(label, value, timeout)

    def section(self, title, open=True, timeout=10):
        return self.act(title, "open" if open else "close", timeout)

    def scroll(self, to="top", timeout=10):
        """Scroll the page: "top", "end", a number of pixels, or a row's label to bring it into view."""
        value = str(to) if to in ("top", "end") or isinstance(to, (int, float)) else "row\t" + str(to)
        self._share("agent.scroll", value)
        self.agent.wait(lambda: (self._shared("agent.scroll") or "") == "", timeout, "the page to scroll")
        time.sleep(0.15)

    def region(self):
        """Where the menu's window is in the game's window: (x, y, w, h) in pixels, or None."""
        r = self.agent.lua(MENU_REGION_LUA)
        if not isinstance(r, list) or len(r) != 4:
            return None
        x, y, w, h = (int(round(v)) for v in r)
        return x - 2, y - 2, w + 4, h + 4

    def shot(self, name=None, scale=1.0):
        """A picture of just the menu's window."""
        return self.agent.shot(name or ("menu-" + (self.current() or "closed")), scale=scale, menu=True)


# The window sits in the middle of the screen, in a scale box (the frame's grandparent): its size on
# screen is the box's size times the UI's scale. (UE4SS hands back cached geometry as zeros, so the
# engine can't be asked where the widget was drawn.)
MENU_REGION_LUA = """
local f = ModRef:GetSharedVariable("WCModsMenu.frame")
if not (f and f:IsValid()) or not ModRef:GetSharedVariable("WCModsMenu.open") then return nil end
local box = f:GetParent():GetParent()
local layout = StaticFindObject("/Script/UMG.Default__WidgetLayoutLibrary")
local pc = Game.controller()
local d, scale, view = box:GetDesiredSize(), layout:GetViewportScale(pc), layout:GetViewportSize(pc)
local w, h = d.X * scale, d.Y * scale
return { (view.X - w) / 2, (view.Y - h) / 2, w, h }
"""
