"""The in-game mod menu: a shared UE4SS Lua module (WCModsMenu) and the script that hosts the window.

Insert (wcmods.json "menu_key") opens a window with a tab per page. Any UE4SS script adds a page with
WCModsMenu.page(title, fn); wcmods' own scripts add pages for their live settings, and the host's
first page lists the installed mods and what they set, from the build. See docs/SDK.md, "Mod menu".

How the pieces fit: each UE4SS mod runs in a Lua state of its own, so the host and the pages talk
through UE4SS's shared variables (strings, numbers, booleans and UObjects). The host makes the
window and shares its content panel; while a page is showing, the script that owns it builds its
controls straight into that panel. The controls are the game's own UI widgets (buttons, check boxes,
sliders, drop-downs, text boxes), so they take clicks and typing properly, and the page reads back
what the player changed each frame.
"""
from .sdk import lua_value

SHARED_NAME = "WCModsMenu"
HOST_NAME = "WCModsMenuHost"
DEFAULT_KEY = "INS"
# UE4SS Key names a player might want for the menu (F11 is the game's fullscreen key).
KEYS = ("INS", "HOME", "END", "DEL", "PAGE_UP", "PAGE_DOWN") + tuple(f"F{n}" for n in range(1, 13) if n != 11)

LUA = r'''-- WCModsMenu: pages in the in-game mod menu (Insert). Installed by wcmods; any UE4SS script can add one:
--
--   local Menu = require("WCModsMenu")
--   Menu.page("My mod", function(ui)
--       ui.heading("My mod")
--       settings.on = ui.switch("Enabled", settings.on)
--       settings.speed = ui.slider("Speed", settings.speed, 0.5, 3, { step = 0.1 })
--       if ui.button("Reset") then settings.speed = 1 end
--   end)
--
-- While the menu shows the page, its function runs every frame. Each ui call is one row, and returns
-- what the player set it to (or the value passed in, when they didn't touch it), so a page can keep
-- the script's own settings in step with one line per setting. Every call is in docs/SDK.md.
--
-- The controls work from the keyboard and a controller too: Tab, the arrow keys or the d-pad move
-- between them, Enter, Space or A presses one, and the one with focus has a ring round it.
--
-- The window belongs to WCModsMenuHost; pages are built straight into its content panel with the
-- game's own UI widgets, found through UE4SS's shared variables (each mod has a Lua state of its own).
local Menu = {}

local function valid(o) return o ~= nil and o:IsValid() end
local function log(fmt, ...) print(string.format("[WCModsMenu] " .. fmt .. "\n", ...)) end

local reported, nreported = {}, 0
local function report(where, err)
    local key = where .. tostring(err)
    if reported[key] or nreported >= 20 then return end
    reported[key], nreported = true, nreported + 1
    log("error in %s: %s", where, tostring(err))
end

-- ---------- shared with the host ----------
local PREFIX = "WCModsMenu."
function Menu.shared(name)
    local ok, v = pcall(function() return ModRef:GetSharedVariable(PREFIX .. name) end)
    if ok then return v end
    return nil
end
function Menu.share(name, value)
    pcall(function() ModRef:SetSharedVariable(PREFIX .. name, value) end)
end

-- ---------- colours ----------
local function linear(c)
    if c <= 0.04045 then return c / 12.92 end
    return ((c + 0.055) / 1.055) ^ 2.4
end
-- "#rrggbb" or "#rrggbbaa" (sRGB) as the {R, G, B, A} the game's UI wants, which is linear.
function Menu.color(hex)
    local h = tostring(hex):gsub("^#", "")
    local r, g, b = tonumber(h:sub(1, 2), 16), tonumber(h:sub(3, 4), 16), tonumber(h:sub(5, 6), 16)
    local a = #h == 8 and tonumber(h:sub(7, 8), 16) or 255
    if not (r and g and b and a) then return { R = 1, G = 0, B = 1, A = 1 } end
    return { R = linear(r / 255), G = linear(g / 255), B = linear(b / 255), A = a / 255 }
end
local C = Menu.color
-- Text is at least 4.5:1 against what it's on. A button's colour is a tint of the engine's button
-- image, which draws it at about half the brightness (in linear light): text on a "good" button is
-- 4.8:1 as drawn. A chosen tab or option is light with dark text, and focus is a gold ring.
local THEME = {
    text = "#e8ecf2", muted = "#9aa6b5", heading = "#ffd98a", accent = "#5b8def",
    danger = "#f08080", danger_fill = "#d65a5a", good = "#43a063", off = "#4a5260", line = "#ffffff26",
    selected = "#e6eeff", selected_text = "#10141a", focus = "#ffd98a",
}
Menu.theme = THEME

-- ---------- the game's UI classes ----------
local NONE = FName("None")   -- lets the engine name each new object
local lib
function Menu.classes()
    if lib then return lib end
    local paths = {
        TextBlock = "/Script/UMG.TextBlock", Button = "/Script/UMG.Button", CheckBox = "/Script/UMG.CheckBox",
        Slider = "/Script/UMG.Slider", SpinBox = "/Script/UMG.SpinBox", ComboBox = "/Script/UMG.ComboBoxString",
        EditableTextBox = "/Script/UMG.EditableTextBox", ProgressBar = "/Script/UMG.ProgressBar",
        Image = "/Script/UMG.Image", HorizontalBox = "/Script/UMG.HorizontalBox", VerticalBox = "/Script/UMG.VerticalBox",
        ScrollBox = "/Script/UMG.ScrollBox", Border = "/Script/UMG.Border", SizeBox = "/Script/UMG.SizeBox",
        Spacer = "/Script/UMG.Spacer", CanvasPanel = "/Script/UMG.CanvasPanel", WidgetTree = "/Script/UMG.WidgetTree",
        ScaleBox = "/Script/UMG.ScaleBox",
        UserWidget = "/Script/UMG.UserWidget",
    }
    local l = {}
    for k, p in pairs(paths) do
        l[k] = StaticFindObject(p)
        if not valid(l[k]) then return nil end
    end
    l.CommonUserWidget = StaticFindObject("/Script/CommonUI.CommonUserWidget")
    l.widgets = StaticFindObject("/Script/UMG.Default__WidgetBlueprintLibrary")
    l.statics = StaticFindObject("/Script/Engine.Default__GameplayStatics")
    lib = l
    return l
end

-- ---------- building widgets ----------
local outer   -- the host's widget tree: what new widgets belong to
function Menu.setOuter(o) outer = o end
function Menu.new(kind, owner)
    return StaticConstructObject(lib[kind], owner or outer, NONE)
end
local new = Menu.new

local AUTO, FILL = 0, 1                  -- ESlateSizeRule
local H_FILL, H_LEFT, H_CENTER, H_RIGHT = 0, 1, 2, 3
local V_FILL, V_TOP, V_CENTER = 0, 1, 2

-- Text at `pt` points (the UI scales it with the screen like the game's own text).
function Menu.text(str, pt, colour, wrap)
    local t = new("TextBlock")
    local f = t.Font
    pcall(function()
        t:SetFont({ FontObject = f.FontObject, TypefaceFontName = f.TypefaceFontName, Size = pt or 13,
                    LetterSpacing = 0, SkewAmount = 0, bForceMonospaced = false, MonospacedWidth = 1 })
    end)
    t:SetText(FText(tostring(str)))
    t:SetColorAndOpacity({ SpecifiedColor = C(colour or THEME.text), ColorUseRule = 0 })
    if wrap then t:SetAutoWrapText(true) end
    return t
end
local text = Menu.text

-- Put `child` in a horizontal box: size "auto" or a fill weight, padding left/right, vertical centring
-- (or valign), filling its space across (or halign).
function Menu.add(box, child, fill, padLeft, padRight, valign, halign)
    local slot = box:AddChildToHorizontalBox(child)
    slot:SetSize({ SizeRule = fill and FILL or AUTO, Value = fill or 1 })
    slot:SetPadding({ Left = padLeft or 0, Top = 0, Right = padRight or 0, Bottom = 0 })
    slot:SetVerticalAlignment(valign or V_CENTER)
    if halign then slot:SetHorizontalAlignment(halign) end
    return slot
end
local add = Menu.add

function Menu.button(label, colour, pt)
    local b = new("Button")
    b:SetContent(text(label, pt or 12.5))
    b:SetBackgroundColor(C(colour or "#3a4250"))
    return b
end

-- A box of a fixed size around a widget.
function Menu.sized(child, w, h)
    local s = new("SizeBox")
    if w then s:SetWidthOverride(w) end
    if h then s:SetHeightOverride(h) end
    s:SetContent(child)
    return s
end

local function setText(t, str) t:SetText(FText(tostring(str))) end
local function getText(w)
    local t = w:GetText()
    if type(t) == "string" then return t end
    return t:ToString()
end
local function getString(s)
    if type(s) == "string" then return s end
    if s == nil then return "" end
    return s:ToString()
end

-- ---------- keyboard and controller ----------
-- The game's UI moves focus between the controls (Tab, the arrow keys, the d-pad) and presses the one
-- with focus (Enter, Space, A); the window keeps focus inside itself. A ring (Menu.ring) shows where it is.
local CLEAR = "#00000000"
function Menu.ring(child)
    local r = new("Border")
    r:SetPadding({ Left = 2, Top = 2, Right = 2, Bottom = 2 })
    r:SetBrushColor(C(CLEAR))
    r:SetContent(child)
    return r
end

-- Whether a widget, or one inside it, has the keyboard's (and a controller's) focus.
function Menu.focused(w)
    local ok, yes = pcall(function() return w:HasKeyboardFocus() or w:HasFocusedDescendants() end)
    return ok and yes == true
end
local focused = Menu.focused

-- A click: the button went from pressed to released, with the mouse still on it when the mouse pressed
-- it, or with focus when a key or a controller's button did. The game's UI gives a button focus when it's
-- clicked; after a mouse click focus goes back to the window, so the button has no ring and Enter or
-- Space doesn't press it again.
local function clicked(state, key, b)
    local pressed = b:IsPressed()
    local was = state[key]
    if pressed and not was then state[key .. ":mouse"] = b:IsHovered() end
    state[key] = pressed
    if not was or pressed then return false end
    if state[key .. ":mouse"] then
        local hit = b:IsHovered()
        local w = Menu.shared("window")
        if hit and valid(w) then pcall(function() w:SetKeyboardFocus() end) end
        return hit
    end
    return focused(b)
end
Menu.clicked = clicked

local function put(e, key, value, apply)
    if e.last[key] ~= value then
        e.last[key] = value
        apply(value)
    end
end

local function near(a, b) return math.abs((a or 0) - (b or 0)) < 1e-6 end

-- Light a row's ring while `w` has focus; true when it does. render() asks once a frame whether
-- focus is anywhere on the page, so the rows only ask the engine when it is.
local pageFocus = false
local function showFocus(e, key, ring, w)
    local f = pageFocus and focused(w)
    put(e, key, f, function(v) ring:SetBrushColor(C(v and THEME.focus or CLEAR)) end)
    return f
end

-- The engine's text and number boxes are white with the menu's light text on them; make them dark.
local FIELD, FIELD_FILL = "#14171c", "#2a3a55"
local function tint(brush, hex)
    local c, want = brush.TintColor.SpecifiedColor, C(hex)
    c.R, c.G, c.B, c.A = want.R, want.G, want.B, want.A
end
local function setForeground(slateColor, hex)
    local want = C(hex)
    slateColor.ColorUseRule = 0
    local c = slateColor.SpecifiedColor
    c.R, c.G, c.B, c.A = want.R, want.G, want.B, want.A
end
local function styleTextBox(t)
    pcall(function()
        local ws = t.WidgetStyle
        for _, k in ipairs({ "BackgroundImageNormal", "BackgroundImageHovered", "BackgroundImageFocused", "BackgroundImageReadOnly" }) do
            tint(ws[k], FIELD)
        end
        setForeground(ws.ForegroundColor, THEME.text)
        ws.TextStyle.Font.Size = 12.5
    end)
end
local function styleSpinBox(s)
    pcall(function()
        local ws = s.WidgetStyle
        for _, k in ipairs({ "BackgroundBrush", "HoveredBackgroundBrush", "ActiveBackgroundBrush" }) do tint(ws[k], FIELD) end
        for _, k in ipairs({ "ActiveFillBrush", "HoveredFillBrush", "InactiveFillBrush" }) do tint(ws[k], FIELD_FILL) end
        setForeground(s.ForegroundColor, THEME.text)
        s.Font.Size = 12
    end)
end

-- A drop-down's list: the engine draws the chosen and hovered rows with dark text, which the game's
-- dark highlight made black on black. Light text on the menu's field colour, and its accent for the
-- row under the cursor or chosen.
local function styleComboBox(c)
    pcall(function()
        local s = c.ItemStyle
        for _, k in ipairs({ "InactiveBrush", "EvenRowBackgroundBrush", "OddRowBackgroundBrush" }) do tint(s[k], FIELD) end
        for _, k in ipairs({ "ActiveBrush", "ActiveHoveredBrush", "InactiveHoveredBrush", "EvenRowBackgroundHoveredBrush",
                             "OddRowBackgroundHoveredBrush", "ActiveHighlightedBrush", "InactiveHighlightedBrush",
                             "SelectorFocusedBrush" }) do
            tint(s[k], THEME.accent)
        end
        setForeground(s.TextColor, THEME.text)
        setForeground(s.SelectedTextColor, "#ffffff")
        setForeground(c.ForegroundColor, THEME.text)
    end)
    pcall(function()   -- the box itself, showing the choice: the engine's is white, under the menu's light text
        local b = c.WidgetStyle.ComboButtonStyle
        for _, k in ipairs({ "Normal", "Hovered", "Pressed", "Disabled" }) do tint(b.ButtonStyle[k], FIELD) end
        setForeground(b.ButtonStyle.NormalForeground, THEME.text)
        setForeground(b.ButtonStyle.HoveredForeground, THEME.text)
        setForeground(b.ButtonStyle.PressedForeground, THEME.text)
        tint(b.MenuBorderBrush, FIELD)
    end)
end

-- ---------- pages ----------
local pages, started = {}, false
local open_sections = {}
local content, gen, rows, cursor = nil, nil, {}, 0

local function trim(from)
    for i = #rows, from, -1 do
        local e = rows[i]
        if e and valid(e.root) then pcall(function() e.root:RemoveFromParent() end) end
        rows[i] = nil
    end
end

-- One row of the page: reuse last frame's row at this place when it's the same kind, otherwise
-- make it (and drop the rows after it, which a different layout won't match either).
local function row(kind, make)
    cursor = cursor + 1
    local e = rows[cursor]
    if e and e.kind ~= kind then
        trim(cursor)
        e = nil
    end
    if not e then
        e = make()
        e.kind, e.last, e.state = kind, e.last or {}, {}
        local slot = content:AddChild(e.root)
        slot:SetPadding({ Left = 8, Top = e.top or 4, Right = 14, Bottom = e.bottom or 4 })
        rows[cursor] = e
    end
    return e
end

-- ---------- being driven from outside (wcmods agent menu ...; docs/agent.md) ----------
-- A tool reads the page that's showing, and uses its controls, through shared variables: "agent.read"
-- set to a token asks for the page's rows, answered in "agent.page" (JSON); "agent.act" set to
-- "token\tlabel\tvalue" uses one control (by its label, or "@n" for the n-th row), answered in
-- "agent.done" ("token\tok\tkind\tlabel" or "token\tmissing"). The mod whose page is showing draws it,
-- so that one answers, and clears the request so no other page acts on it.
-- "agent.scroll" scrolls the page: "top", "end", a number, or "row\t<label>" to bring that row into view.
local agent = { i = 0 }
local function agentBegin()
    agent.i, agent.rec, agent.act, agent.hit, agent.scroll, agent.rowAt = 0, nil, nil, nil, nil, nil
    local token = Menu.shared("agent.read")
    if token and token ~= "" then agent.rec, agent.token = {}, token end
    local a = Menu.shared("agent.act")
    if a and a ~= "" then
        local t, label, value = tostring(a):match("^([^\t]*)\t([^\t]*)\t?(.*)$")
        if t then agent.act = { token = t, label = label, value = value } end
    end
    local s = Menu.shared("agent.scroll")
    if s and s ~= "" then agent.scroll = tostring(s) end
end
local function agentScroll()
    local s = agent.scroll
    Menu.share("agent.scroll", "")
    local want = s:match("^row\t(.*)$")
    if want then
        local e = agent.rowAt and rows[agent.rowAt]
        if e and valid(e.root) then content:ScrollWidgetIntoView(e.root, false, 1, 0) end   -- 1: to the top
    elseif s == "top" then content:ScrollToStart()
    elseif s == "end" then content:ScrollToEnd()
    elseif tonumber(s) then content:SetScrollOffset(tonumber(s)) end
end
local function agentEnd(page)
    if agent.scroll then pcall(agentScroll) end
    if agent.rec then
        Menu.share("agent.read", "")
        Menu.share("agent.page", Menu.json({ token = agent.token, page = page.id, title = page.title,
                                             rows = Menu.list(agent.rec) }))
    end
    if agent.act then
        Menu.share("agent.act", "")
        local h = agent.hit
        Menu.share("agent.done", agent.act.token .. "\t" .. (h and ("ok\t" .. h.kind .. "\t" .. h.label) or "missing"))
    end
end
-- Each row says what it shows; a control (`acts`) gets back the action meant for it: its new value as
-- text, "" for a plain press.
local function seen(kind, label, value, options, acts, focus)
    agent.i = agent.i + 1
    if agent.scroll and not agent.rowAt then
        local want = agent.scroll:match("^row\t(.*)$")
        local shown = tostring(label or value or "")
        if want and (shown == want or shown:lower() == want:lower() or "@" .. agent.i == want) then agent.rowAt = cursor end
    end
    if agent.rec then
        agent.rec[#agent.rec + 1] = { n = agent.i, kind = kind, label = label ~= nil and tostring(label) or nil,
                                      value = value, options = options, focus = focus or nil }
    end
    local a = agent.act
    if acts and a and not agent.hit and label ~= nil then
        local l = tostring(label)
        if a.label == l or a.label == "@" .. agent.i or a.label:lower() == l:lower() then
            agent.hit = { kind = kind, label = l }
            return a.value
        end
    end
    return nil
end
local function truthy(s, now)
    s = tostring(s):lower()
    if s == "" or s == "toggle" then return not now end
    return s == "on" or s == "true" or s == "1" or s == "yes" or s == "open"
end

-- A label and its control, which has a focus ring (the third value).
local function labelled(label, control, controlFill, extra, halign)
    local box = new("HorizontalBox")
    local l = text(label, 13)
    local r = Menu.ring(control)
    add(box, l, 0.42, 0, 12)
    add(box, r, controlFill or 0.58, 0, 0, nil, halign)
    if extra then add(box, extra, nil, 8) end
    return box, l, r
end

local ui = {}

function ui.heading(str)
    local e = row("heading", function()
        local t = text(str, 18, THEME.heading)
        return { root = t, t = t, top = 8, bottom = 4 }
    end)
    put(e, "text", str, function(v) setText(e.t, v) end)
    seen("heading", nil, tostring(str))
end

function ui.text(str, opts)
    opts = opts or {}
    local e = row("text", function()
        local t = text(str, opts.size or 13, opts.color or THEME.text, true)
        return { root = t, t = t }
    end)
    put(e, "text", tostring(str), function(v) setText(e.t, v) end)
    put(e, "color", opts.color or THEME.text, function(v) e.t:SetColorAndOpacity({ SpecifiedColor = C(v), ColorUseRule = 0 }) end)
    seen(opts.note and "note" or "text", nil, tostring(str))
end

function ui.note(str)
    ui.text(str, { size = 12, color = THEME.muted, note = true })
end

function ui.separator()
    row("separator", function()
        local b = new("Border")
        b:SetBrushColor(C(THEME.line))
        return { root = Menu.sized(b, nil, 1), top = 6, bottom = 6 }
    end)
end

function ui.space(h)
    local e = row("space", function()
        local s = new("Spacer")
        return { root = s, s = s }
    end)
    put(e, "h", h or 8, function(v) e.s:SetSize({ X = 1, Y = v }) end)
end

-- Two columns: a name and its value, for showing settings. opts.color colours the value.
function ui.field(label, value, opts)
    opts = opts or {}
    local e = row("field", function()
        local v = text("", 13, THEME.text, true)
        local box, l = labelled(label, v)
        l:SetColorAndOpacity({ SpecifiedColor = C(THEME.muted), ColorUseRule = 0 })
        return { root = box, l = l, v = v }
    end)
    put(e, "label", label, function(s) setText(e.l, s) end)
    put(e, "value", tostring(value), function(s) setText(e.v, s) end)
    put(e, "vcolor", opts.color or THEME.text, function(c) e.v:SetColorAndOpacity({ SpecifiedColor = C(c), ColorUseRule = 0 }) end)
    seen("field", label, tostring(value))
end

-- Several values side by side: ui.columns({ {"Level", 20}, {"Health", "233 / 233", "#ff8080"}, ... }). Each item is
-- { label, value, colour }; the label sits small above its value.
function ui.columns(items)
    local n = #items
    local e = row("columns" .. n, function()
        local box = new("HorizontalBox")
        local cells = {}
        for i = 1, n do
            local col = new("VerticalBox")
            local l = text("", 12, THEME.muted)
            local v = text("", 14, THEME.text, true)
            col:AddChildToVerticalBox(l)
            col:AddChildToVerticalBox(v)
            add(box, col, 1, 0, 12, 0)
            cells[i] = { l = l, v = v }
        end
        return { root = box, cells = cells, top = 6, bottom = 6 }
    end)
    for i, it in ipairs(items) do
        local c = e.cells[i]
        if c then
            put(e, "l" .. i, tostring(it[1]), function(v) setText(c.l, v) end)
            put(e, "v" .. i, tostring(it[2] == nil and "-" or it[2]), function(v) setText(c.v, v) end)
            put(e, "c" .. i, it[3] or THEME.text, function(v) c.v:SetColorAndOpacity({ SpecifiedColor = C(v), ColorUseRule = 0 }) end)
        end
        seen("field", it[1], tostring(it[2] == nil and "-" or it[2]))
    end
end

local KIND_COLOURS = { primary = THEME.accent, danger = THEME.danger_fill, good = THEME.good }
-- A button; true the frame it's clicked. opts.kind: "primary", "danger", "good" or nil.
function ui.button(label, opts)
    opts = opts or {}
    local e = row("button", function()
        local box = new("HorizontalBox")
        local b = Menu.button(label)
        local r = Menu.ring(b)
        add(box, r)
        return { root = box, b = b, r = r }
    end)
    put(e, "label", label, function(v) e.b:SetContent(text(v, 12.5)) end)
    put(e, "color", opts.kind or "", function(v) e.b:SetBackgroundColor(C(KIND_COLOURS[v] or "#3a4250")) end)
    local f = showFocus(e, "focus", e.r, e.b)
    local pressed = seen("button", label, nil, nil, true, f) ~= nil
    return clicked(e.state, "b", e.b) or pressed
end

-- A row of buttons; the index of the one clicked this frame, or nil.
function ui.buttons(labels, opts)
    opts = opts or {}
    local e = row("buttons" .. #labels, function()
        local box = new("HorizontalBox")
        local bs, rs = {}, {}
        for i, l in ipairs(labels) do
            bs[i] = Menu.button(l)
            rs[i] = Menu.ring(bs[i])
            add(box, rs[i], nil, 0, 4)
        end
        return { root = box, bs = bs, rs = rs }
    end)
    local hit
    for i, b in ipairs(e.bs) do
        put(e, "label" .. i, labels[i], function(v) b:SetContent(text(v, 12.5)) end)
        local kind = opts.kinds and opts.kinds[i] or ""
        put(e, "color" .. i, kind, function(v) b:SetBackgroundColor(C(KIND_COLOURS[v] or "#3a4250")) end)
        local f = showFocus(e, "focus" .. i, e.rs[i], b)
        if clicked(e.state, i, b) then hit = i end
        if seen("button", labels[i], nil, nil, true, f) ~= nil then hit = i end
    end
    return hit
end

-- A check box with its label; returns whether it's ticked. opts.swatch: a colour shown by the label.
function ui.toggle(label, value, opts)
    opts = opts or {}
    local e = row(opts.swatch and "toggle+swatch" or "toggle", function()
        local box = new("HorizontalBox")
        local c = new("CheckBox")
        local r = Menu.ring(c)
        local l = text(label, 13)
        add(box, r, nil, 0, 8)
        local sw
        if opts.swatch then
            sw = new("Image")
            add(box, Menu.sized(sw, 16, 16), nil, 0, 10)
        end
        add(box, l, 1)
        return { root = box, c = c, r = r, l = l, sw = sw }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    if e.sw then put(e, "swatch", opts.swatch, function(v) e.sw:SetColorAndOpacity(C(v)) end) end
    local now = e.c:IsChecked()
    if e.v ~= nil and now ~= e.v then
        e.v = now                                   -- the player clicked it
    elseif e.v ~= (value and true or false) then
        e.v = value and true or false               -- the script changed it
        e.c:SetIsChecked(e.v)
    end
    local act = seen("toggle", label, e.v, nil, true, showFocus(e, "focus", e.r, e.c))
    if act ~= nil then
        e.v = truthy(act, e.v)
        e.c:SetIsChecked(e.v)
    end
    return e.v
end

-- An on/off switch: a button that shows On or Off; returns the new state.
function ui.switch(label, value)
    local e = row("switch", function()
        local b = Menu.button("Off")
        local box, l, r = labelled(label, Menu.sized(b, 80), nil, nil, H_LEFT)
        return { root = box, b = b, l = l, r = r }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    local on = value and true or false
    if clicked(e.state, "b", e.b) then on = not on end
    local act = seen("switch", label, on, nil, true, showFocus(e, "focus", e.r, e.b))
    if act ~= nil then on = truthy(act, on) end
    put(e, "on", on, function(v)
        e.b:SetContent(text(v and "On" or "Off", 12.5))
        e.b:SetBackgroundColor(C(v and THEME.good or THEME.off))
    end)
    return on
end

-- One of several options as a row of buttons; returns the chosen one.
function ui.radio(label, value, options)
    local e = row("radio" .. #options, function()
        local inner = new("HorizontalBox")
        local bs, rs = {}, {}
        for i, o in ipairs(options) do
            bs[i] = Menu.button(tostring(o), nil, 12)
            rs[i] = Menu.ring(bs[i])
            add(inner, rs[i], nil, 0, 2)
        end
        local box, l = labelled(label, inner)
        return { root = box, bs = bs, rs = rs, l = l }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    local chosen = value
    local f = false
    for i, b in ipairs(e.bs) do
        if clicked(e.state, i, b) then chosen = options[i] end
        if showFocus(e, "focus" .. i, e.rs[i], b) then f = true end
    end
    local strs = {}
    for i, o in ipairs(options) do strs[i] = tostring(o) end
    local act = seen("radio", label, tostring(chosen), strs, true, f)
    if act ~= nil then
        for i, s in ipairs(strs) do
            if s == act or s:lower() == act:lower() then chosen = options[i] break end
        end
    end
    for i, b in ipairs(e.bs) do
        local sel = options[i] == chosen
        put(e, "opt" .. i, strs[i] .. (sel and "\t*" or ""), function()
            b:SetContent(text(strs[i], 12, sel and THEME.selected_text or THEME.text))
            b:SetBackgroundColor(C(sel and THEME.selected or "#3a4250"))
        end)
    end
    return chosen
end

-- A drop-down list; returns the chosen option.
function ui.choice(label, value, options)
    local e = row("choice", function()
        local c = new("ComboBox")
        styleComboBox(c)
        local box, l, r = labelled(label, c)
        return { root = box, c = c, l = l, r = r }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    local strs = {}
    for i, o in ipairs(options) do strs[i] = tostring(o) end
    put(e, "options", table.concat(strs, "\n"), function()
        e.c:ClearOptions()
        for _, s in ipairs(strs) do e.c:AddOption(s) end
        e.v = nil
    end)
    local now = getString(e.c:GetSelectedOption())
    if e.v ~= nil and now ~= e.v then
        e.v = now
    elseif e.v ~= tostring(value) then
        e.v = tostring(value)
        e.c:SetSelectedOption(e.v)
    end
    local act = seen("choice", label, e.v, strs, true, showFocus(e, "focus", e.r, e.c))
    if act ~= nil then
        for _, s in ipairs(strs) do
            if s == act or s:lower() == act:lower() then
                e.v = s
                e.c:SetSelectedOption(s)
                break
            end
        end
    end
    for i, s in ipairs(strs) do
        if s == e.v then return options[i] end
    end
    return value
end

-- A slider from lo to hi; returns its value. opts: step, format ("%.2f"), color.
function ui.slider(label, value, lo, hi, opts)
    opts = opts or {}
    local e = row("slider", function()
        local s = new("Slider")
        local v = text("", 12, THEME.muted)
        local box, l, r = labelled(label, s, nil, Menu.sized(v, 84))
        return { root = box, s = s, l = l, vt = v, r = r }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    -- The range stretches to take a value outside it, which the slider would otherwise clamp (and
    -- that would look like the player moving it).
    lo, hi = math.min(lo, value), math.max(hi, value)
    put(e, "range", lo .. "," .. hi .. "," .. (opts.step or 0), function()
        e.s:SetMinValue(lo)
        e.s:SetMaxValue(hi)
        e.s:SetStepSize(opts.step or (hi - lo) / 100)
        e.v = nil
    end)
    if opts.color then put(e, "color", opts.color, function(c) e.s:SetSliderBarColor(C(c)) e.s:SetSliderHandleColor(C(c)) end) end
    local now = e.s:GetValue()
    if e.v ~= nil and not near(now, e.v) then
        e.v = now
    elseif e.v == nil or not near(e.v, value) then
        e.v = value
        e.s:SetValue(value)
    end
    local act = tonumber(seen("slider", label, e.v, { lo, hi }, true, showFocus(e, "focus", e.r, e.s)) or "")
    if act then
        e.v = act
        e.s:SetValue(act)
    end
    put(e, "shown", string.format(opts.format or "%.2f", e.v), function(s) setText(e.vt, s) end)
    return e.v
end

-- A number box (drag it or type); returns its value. opts: min, max, step, whole (whole numbers only).
function ui.number(label, value, opts)
    opts = opts or {}
    local e = row("number", function()
        local s = new("SpinBox")
        styleSpinBox(s)
        local box, l, r = labelled(label, s)
        return { root = box, s = s, l = l, r = r }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    put(e, "whole", opts.whole and true or false, function(whole)
        pcall(function()
            e.s:SetMinFractionalDigits(whole and 0 or 1)
            e.s:SetMaxFractionalDigits(whole and 0 or 3)
            e.s:SetAlwaysUsesDeltaSnap(whole)
        end)
        e.v = nil
    end)
    put(e, "range", tostring(opts.min) .. "," .. tostring(opts.max) .. "," .. tostring(opts.step), function()
        if opts.min then e.s:SetMinValue(opts.min) e.s:SetMinSliderValue(opts.min) end
        if opts.max then e.s:SetMaxValue(opts.max) e.s:SetMaxSliderValue(opts.max) end
        if opts.step then e.s:SetDelta(opts.step) end
        e.v = nil
    end)
    local now = e.s:GetValue()
    if opts.whole then now = math.floor(now + 0.5) end
    if e.v ~= nil and not near(now, e.v) then
        e.v = now
    elseif e.v == nil or not near(e.v, value) then
        e.v = value
        e.s:SetValue(value)
    end
    local act = tonumber(seen("number", label, e.v, { opts.min, opts.max }, true, showFocus(e, "focus", e.r, e.s)) or "")
    if act then
        e.v = opts.whole and math.floor(act + 0.5) or act
        e.s:SetValue(e.v)
    end
    return e.v
end

-- A text box; returns its text. opts.hint shows when it's empty.
function ui.input(label, value, opts)
    opts = opts or {}
    local e = row("input", function()
        local t = new("EditableTextBox")
        styleTextBox(t)
        local box, l, r = labelled(label, t)
        return { root = box, t = t, l = l, r = r }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    put(e, "hint", opts.hint or "", function(v) e.t:SetHintText(FText(v)) end)
    local now = getText(e.t)
    if e.v ~= nil and now ~= e.v then
        e.v = now
    elseif e.v ~= tostring(value or "") then
        e.v = tostring(value or "")
        setText(e.t, e.v)
    end
    local act = seen("input", label, e.v, nil, true, showFocus(e, "focus", e.r, e.t))
    if act ~= nil then
        e.v = act
        setText(e.t, act)
    end
    return e.v
end

local function hexOf(r, g, b)
    return string.format("#%02x%02x%02x", math.floor(r + 0.5), math.floor(g + 0.5), math.floor(b + 0.5))
end
-- A colour: a swatch, red, green and blue sliders, and its hex code; returns "#rrggbb".
function ui.color(label, hex)
    local e = row("color", function()
        local inner = new("HorizontalBox")
        local sw = new("Image")
        add(inner, Menu.sized(sw, 34, 18), nil, 0, 8)
        local ss = {}
        for i, c in ipairs({ "#e05555", "#55c070", "#5b8def" }) do
            ss[i] = new("Slider")
            ss[i]:SetMinValue(0)
            ss[i]:SetMaxValue(255)
            ss[i]:SetStepSize(1)
            ss[i]:SetSliderBarColor(C(c))
            ss[i]:SetSliderHandleColor(C(c))
            add(inner, ss[i], 1, 0, 6)
        end
        local v = text("", 12, THEME.muted)
        add(inner, Menu.sized(v, 84))
        local box, l, r = labelled(label, inner, 0.58)
        return { root = box, sw = sw, ss = ss, vt = v, l = l, r = r, inner = inner }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    local h = tostring(hex or "#808080"):gsub("^#", "")
    local want = { tonumber(h:sub(1, 2), 16) or 128, tonumber(h:sub(3, 4), 16) or 128, tonumber(h:sub(5, 6), 16) or 128 }
    e.rgb = e.rgb or {}
    local moved = false
    for i, s in ipairs(e.ss) do
        local now = s:GetValue()
        if e.rgb[i] ~= nil and not near(now, e.rgb[i]) then
            e.rgb[i], moved = now, true
        end
    end
    if not moved then
        for i, s in ipairs(e.ss) do
            if e.rgb[i] == nil or math.abs(e.rgb[i] - want[i]) >= 0.5 then
                e.rgb[i] = want[i]
                s:SetValue(want[i])
            end
        end
    end
    local out = hexOf(e.rgb[1], e.rgb[2], e.rgb[3])
    local act = seen("color", label, out, nil, true, showFocus(e, "focus", e.r, e.inner))
    local ah = act and act:match("^#?(%x%x%x%x%x%x)$")
    if ah then
        for i, s in ipairs(e.ss) do
            e.rgb[i] = tonumber(ah:sub(i * 2 - 1, i * 2), 16)
            s:SetValue(e.rgb[i])
        end
        out = hexOf(e.rgb[1], e.rgb[2], e.rgb[3])
    end
    put(e, "hex", out, function(v)
        e.sw:SetColorAndOpacity(C(v))
        setText(e.vt, v)
    end)
    return out
end

-- A bar filled to `fraction` (0-1). opts.color, opts.format ("%d%%").
function ui.progress(label, fraction, opts)
    opts = opts or {}
    local e = row("progress", function()
        local p = new("ProgressBar")
        local v = text("", 12, THEME.muted)
        local box, l = labelled(label, Menu.sized(p, nil, 14), nil, Menu.sized(v, 84))
        return { root = box, p = p, vt = v, l = l }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    local f = math.max(0, math.min(1, fraction or 0))
    put(e, "f", math.floor(f * 1000), function() e.p:SetPercent(f) end)
    put(e, "color", opts.color or THEME.accent, function(v) e.p:SetFillColorAndOpacity(C(v)) end)
    put(e, "shown", string.format(opts.format or "%d%%", math.floor(f * 100 + 0.5)), function(s) setText(e.vt, s) end)
    seen("progress", label, string.format(opts.format or "%d%%", math.floor(f * 100 + 0.5)))
end

local textures = {}
-- A picture: a texture object or its path, w by h (opts.color tints it).
function ui.image(texture, w, h, opts)
    opts = opts or {}
    local e = row("image", function()
        local i = new("Image")
        local s = Menu.sized(i, w or 64, h or 64)
        local box = new("HorizontalBox")
        add(box, s)
        return { root = box, i = i, s = s }
    end)
    put(e, "size", (w or 64) .. "x" .. (h or 64), function()
        e.s:SetWidthOverride(w or 64)
        e.s:SetHeightOverride(h or 64)
    end)
    local tex = texture
    if type(texture) == "string" then
        tex = textures[texture]
        if not valid(tex) then
            tex = StaticFindObject(texture)
            if not valid(tex) and LoadAsset then pcall(function() tex = LoadAsset(texture) end) end
            textures[texture] = tex
        end
    end
    put(e, "tex", valid(tex) and tex:GetFullName() or "", function()
        if valid(tex) then e.i:SetBrushFromTexture(tex, false) end
    end)
    put(e, "color", opts.color or "#ffffff", function(v) e.i:SetColorAndOpacity(C(v)) end)
end

-- A part of the page that opens and closes with a click on its title. opts.open: open at first.
function ui.section(title, fn, opts)
    opts = opts or {}
    local key = opts.id or title
    if open_sections[key] == nil then open_sections[key] = opts.open ~= false end
    local e = row("section", function()
        local b = Menu.button("")
        local r = Menu.ring(b)
        return { root = r, b = b, r = r, top = 4 }
    end)
    if clicked(e.state, "b", e.b) then open_sections[key] = not open_sections[key] end
    local act = seen("section", title, open_sections[key], nil, true, showFocus(e, "focus", e.r, e.b))
    if act ~= nil then open_sections[key] = truthy(act, open_sections[key]) end
    local isOpen = open_sections[key]
    put(e, "title", (isOpen and "-  " or "+  ") .. title, function(v) e.b:SetContent(text(v, 14, THEME.heading)) end)
    put(e, "bg", isOpen, function() e.b:SetBackgroundColor(C("#2c3440")) end)
    if isOpen then fn(ui) end
    return isOpen
end

Menu.ui = ui

-- ---------- running pages ----------
local function render(page)
    content, outer = Menu.shared("content"), Menu.shared("tree")
    if not (valid(content) and valid(outer)) then return end
    local g = Menu.shared("generation")
    if g ~= gen then
        rows, gen = {}, g
    end
    cursor = 0
    pageFocus = focused(content)
    agentBegin()
    local ok, err = pcall(page.fn, ui)
    if not ok then
        report("page " .. page.title, err)
        ui.text("This page hit an error: " .. tostring(err), { color = THEME.danger })
    end
    agentEnd(page)
    trim(cursor + 1)
end

local function tick()
    if not Menu.shared("open") or not Menu.classes() then return end
    local id = Menu.shared("page")
    for _, p in ipairs(pages) do
        if p.id == id then
            local ok, err = pcall(render, p)
            if not ok then report("drawing " .. p.title, err) end
            return
        end
    end
end

-- The shared list of pages: one line each, id, title, order, group and the mod it came from, tab-separated.
-- Whose a page with this id is: "" when the line doesn't say (a C++ mod's, or an older script's), nil
-- when there's none. Whole ids only: a plain find would match "Travel" inside "Fast Travel".
local function ownerOf(list, id)
    for line in list:gmatch("[^\n]+") do
        local lid, rest = line:match("^([^\t]*)\t(.*)$")
        if lid == id then return rest:match("^[^\t]*\t[^\t]*\t[^\t]*\t([^\t]*)") or "" end
    end
    return nil
end

local function register(p)
    local list = Menu.shared("pages") or ""
    local have = ownerOf(list, p.id)
    if have ~= nil and have ~= p.owner then
        -- Another mod has a page with this id already: this one gets its own, so the two don't both draw
        -- into one tab (each script's tick draws its page with the shown id).
        p.id = p.id .. " (" .. p.owner .. ")"
        have = ownerOf(list, p.id)
    end
    if have == nil then
        Menu.share("pages", list .. p.id .. "\t" .. p.title .. "\t" .. tostring(p.order) .. "\t" .. p.group .. "\t" .. p.owner .. "\n")
    end
end

-- The mod a page comes from: the folder under Mods/ its script runs from (UE4SS names a chunk by its
-- path), else the chunk's name; "" when Lua can't say.
local SLASH = string.char(92)
local function caller(level)
    local info = debug and debug.getinfo and debug.getinfo(level + 1, "S")
    local src = info and tostring(info.source or "") or ""
    src = src:gsub(SLASH, "/")
    return src:match("/Mods/([^/]+)/") or src
end

-- The groups the menu's side bar shows, in order (menu.GROUPS in wcmods/menu.py, written in here): id,
-- label, and what the Overview says is there. A page names one of these ids (or a group of its own,
-- which comes after "mods").
Menu.groups = @GROUPS@

-- Add a page to the mod menu. fn(ui) runs every frame while it shows. opts.group puts it in a group of
-- the side bar ("mods" by default; Menu.groups lists them), opts.order sorts it within the group (lower
-- first), and opts.id tells pages with the same title apart (without it, the title; a second mod's page
-- with a title another mod has gets the title plus its mod's name, so the two don't share a tab).
function Menu.page(title, fn, opts)
    opts = opts or {}
    local p = { id = opts.id or title, title = title, fn = fn, order = opts.order or 50,
                group = (tostring(opts.group or "mods"):gsub("[\t\n]", " ")), owner = caller(2) }
    pages[#pages + 1] = p
    ExecuteInGameThread(function() register(p) end)
    if not started then
        started = true
        if LoopInGameThreadAfterFrames == nil or not pcall(LoopInGameThreadAfterFrames, 1, tick) then
            LoopAsync(16, function()
                ExecuteInGameThread(tick)
                return false
            end)
        end
    end
    return p.id
end

function Menu.isOpen() return Menu.shared("open") and true or false end

-- Open the menu (on a page, by its id or title), or close it; e.g. from a script's own key. The host does
-- it on its next frame.
function Menu.open(page) Menu.share("request", "open\t" .. tostring(page or "")) end
function Menu.close() Menu.share("request", "close\t") end

-- Tell the menu about a key a script uses, so its Overview page lists it: Menu.key("F6", "Mouse look on and off").
function Menu.key(key, what)
    if not key or key == "" then return end
    local line = tostring(key) .. "\t" .. (tostring(what or ""):gsub("[\t\n]", " ")) .. "\n"
    ExecuteInGameThread(function()
        local list = Menu.shared("keys") or ""
        if not list:find(line, 1, true) then Menu.share("keys", list .. line) end
    end)
end

-- ---------- saving settings ----------
local LIST = {}
-- Mark a table as a JSON list, so it's written [] even when empty (Lua can't tell {} from []).
function Menu.list(t)
    return setmetatable(t or {}, LIST)
end

local function encode(v, indent)
    local t = type(v)
    if t == "nil" then return "null" end
    if t == "boolean" then return v and "true" or "false" end
    if t == "number" then
        if v ~= v or v == math.huge or v == -math.huge then return "null" end
        if math.type(v) == "integer" then return tostring(v) end
        -- %g writes 12.0 as "12", which comes back as a whole number (and a setting then only takes whole
        -- numbers); keep it a float.
        local s = string.format("%.6g", v)
        if not s:find("[%.eE]") then s = s .. ".0" end
        return s
    end
    if t == "string" then
        return '"' .. v:gsub('[%c"\\]', function(c)
            local named = { ['"'] = '\\"', ["\\"] = "\\\\", ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }
            return named[c] or string.format("\\u%04x", c:byte())
        end) .. '"'
    end
    if t ~= "table" then error("can't save a " .. t .. " as JSON") end
    local pad, inner = string.rep("  ", indent), string.rep("  ", indent + 1)
    if getmetatable(v) == LIST and #v == 0 then return "[]" end
    if #v > 0 or next(v) == nil then
        local parts = {}
        for i, x in ipairs(v) do parts[i] = encode(x, indent + 1) end
        if #parts == 0 then return next(v) == nil and "{}" or "[]" end
        return "[" .. table.concat(parts, ", ") .. "]"
    end
    local keys = {}
    for k in pairs(v) do keys[#keys + 1] = tostring(k) end
    table.sort(keys, function(a, b)   -- "_help" and other notes first, then the settings
        local ua, ub = a:sub(1, 1) == "_", b:sub(1, 1) == "_"
        if ua ~= ub then return ua end
        return a < b
    end)
    local parts = {}
    for _, k in ipairs(keys) do parts[#parts + 1] = inner .. encode(k) .. ": " .. encode(v[k], indent + 1) end
    return "{\n" .. table.concat(parts, ",\n") .. "\n" .. pad .. "}"
end

-- A Lua value as JSON text (objects get their keys sorted, notes like "_help" first).
function Menu.json(value) return encode(value, 0) end

-- Write a Lua value to a JSON file; true, or false and why not.
function Menu.saveJson(path, value)
    local ok, err = pcall(function()
        local f = assert(io.open(path, "wb"))   -- binary, so the file keeps \n line ends on Windows
        f:write(encode(value, 0), "\n")
        f:close()
    end)
    if not ok then return false, tostring(err) end
    return true
end

return Menu
'''

HOST_LUA = r'''-- The in-game mod menu: the window, its tabs, and the first pages. Written by wcmods on every install;
-- change wcmods.json ("menu_key") and install again rather than editing this.
--
-- @KEY@ opens and closes it, and Escape closes it; so does a controller's button (SETTINGS.pad), with B
-- closing it too. While it's open the game's controls are paused (the UI takes the keyboard and mouse,
-- or the game itself pauses when the controller opened it) and the cursor shows; closing gives them
-- back. Pages come from any UE4SS script through WCModsMenu.page (docs/SDK.md, "Mod menu"); the window
-- shares its content panel with them and they build their rows into it.
local Menu = require("WCModsMenu")
local SETTINGS = @SETTINGS@

-- Only an engine object has IsValid (the pages also hand this strings, numbers and tables).
local function valid(o)
    if type(o) ~= "userdata" then return false end
    local ok, yes = pcall(function() return o:IsValid() end)
    return ok and yes == true
end
local function log(fmt, ...) print(string.format("[WCModsMenu] " .. fmt .. "\n", ...)) end
local C, THEME, new, add, text = Menu.color, Menu.theme, Menu.new, Menu.add, Menu.text

local VISIBLE, COLLAPSED = 0, 1   -- ESlateVisibility
local FILL = 1
local USER_SPECIFIED = 7          -- EStretch::UserSpecified: scale by SetUserSpecifiedScale
local NAV_WRAP = 2                -- EUINavigationRule::Wrap, for EUINavigation Left..Previous (0-5)
local SCROLL_INSTANT = 1          -- EScrollWhenFocusChanges::InstantScroll

local pc, nextSearch = nil, 0
local function controller()
    -- A destroyed controller's slot can be taken by another object, so even reading it is guarded.
    local ok, still = pcall(function() return valid(pc) and valid(pc.Player) end)
    if ok and still then return pc end
    pc = nil
    if os.clock() < nextSearch then return nil end
    nextSearch = os.clock() + 0.5
    for _, c in ipairs(FindAllOf("PlayerController") or {}) do
        if valid(c) and valid(c.Player) then
            pc = c
            break
        end
    end
    return pc
end

-- ---------- the window ----------
local win   -- { widget, tree, tabs, content, close, pause }

local function build(c, lib)
    -- A plain UserWidget class is abstract; CommonUI's is concrete when the game has it.
    local widget
    if valid(lib.CommonUserWidget) then
        local ok, w = pcall(function() return lib.widgets:Create(c, lib.CommonUserWidget, c) end)
        if ok and valid(w) then widget = w end
    end
    if not widget then widget = StaticConstructObject(lib.UserWidget, c, FName("None")) end
    if not valid(widget.WidgetTree) then widget.WidgetTree = StaticConstructObject(lib.WidgetTree, widget, FName("None")) end
    local tree = widget.WidgetTree
    Menu.setOuter(tree)
    local function make(kind) return new(kind, tree) end

    local canvas = make("CanvasPanel")
    tree.RootWidget = canvas
    local dim = make("Border")
    dim:SetBrushColor({ R = 0, G = 0, B = 0, A = 0.35 })
    local ds = canvas:AddChildToCanvas(dim)
    ds:SetAnchors({ Minimum = { X = 0, Y = 0 }, Maximum = { X = 1, Y = 1 } })
    ds:SetOffsets({ Left = 0, Top = 0, Right = 0, Bottom = 0 })

    -- The game shrinks its UI to fit a 3840x2160 design (DefaultEngine.ini: ScaleToFit), so at 1080p
    -- everything is drawn at half size. The window sits in a scale box that undoes that (see fit()),
    -- which scales layout and drawing together: text stays sharp, and the engine's check boxes,
    -- sliders and drop-downs grow with it.
    local scaler = make("ScaleBox")
    local ss = canvas:AddChildToCanvas(scaler)
    ss:SetAnchors({ Minimum = { X = 0.5, Y = 0.5 }, Maximum = { X = 0.5, Y = 0.5 } })
    ss:SetAlignment({ X = 0.5, Y = 0.5 })
    ss:SetPosition({ X = 0, Y = 0 })
    ss:SetAutoSize(true)
    scaler:SetStretch(USER_SPECIFIED)
    local sizer = make("SizeBox")
    scaler:SetContent(sizer)
    local frame = make("Border")
    frame:SetBrushColor(C("#161b22f8"))
    frame:SetPadding({ Left = 18, Top = 14, Right = 18, Bottom = 14 })
    sizer:SetContent(frame)

    local column = make("VerticalBox")
    frame:SetContent(column)
    local header = make("HorizontalBox")
    add(header, text("Mod menu", 20, THEME.heading), 1)
    local rings = {}
    local function ringed(name, w, padRight)
        local r = Menu.ring(w)
        add(header, r, nil, 0, padRight)
        rings[#rings + 1] = { name = name, w = w, r = r }
        return w
    end
    local smaller = ringed("A-", Menu.button("A-", nil, 12), 2)
    local bigger = ringed("A+", Menu.button("A+", nil, 12), 16)
    local pause = ringed("Pause the game", make("CheckBox"), 4)
    add(header, text("Pause the game", 12, THEME.muted), nil, 0, 16)
    local close = ringed("Close", Menu.button("Close", nil, 13))
    column:AddChildToVerticalBox(header)

    -- Under the header: how your cat is doing (HOST.status, from the Game pages), or how to use the menu.
    local status = text(SETTINGS.opens .. " opens and closes this menu. Changes apply at once; a page's Save keeps them.",
                        12, THEME.muted, true)
    local hs = column:AddChildToVerticalBox(status)
    hs:SetPadding({ Left = 0, Top = 6, Right = 0, Bottom = 12 })

    local body = make("HorizontalBox")
    local bs = column:AddChildToVerticalBox(body)
    bs:SetSize({ SizeRule = FILL, Value = 1 })
    local tabs = make("ScrollBox")
    add(body, Menu.sized(tabs, 230), nil, 0, 14, 0)
    local pane = make("Border")
    pane:SetBrushColor(C("#1f2630"))
    pane:SetPadding({ Left = 10, Top = 10, Right = 6, Bottom = 10 })
    local content = make("ScrollBox")
    pane:SetContent(content)
    add(body, pane, 1, 0, 0, 0)

    widget:AddToViewport(2000)
    -- Keyboard and controller: focus moving off an edge of the window comes back in at the other side
    -- (it would otherwise go to the game's own screens underneath), and a list scrolls to what has focus.
    for dir = 0, 5 do pcall(function() frame:SetNavigationRuleBase(dir, NAV_WRAP) end) end
    for _, list in ipairs({ tabs, content }) do pcall(function() list:SetScrollWhenFocusChanges(SCROLL_INSTANT) end) end
    return { widget = widget, tree = tree, tabs = tabs, content = content, close = close, pause = pause, frame = frame,
             scaler = scaler, sizer = sizer, smaller = smaller, bigger = bigger, status = status, rings = rings,
             tabButtons = {}, tabList = nil, state = {} }
end

-- Size the window for this screen: undo the game's UI shrink, times the player's own size (A-/A+,
-- and wcmods.json "menu_scale"), and keep it within the screen.
local size = SETTINGS.scale
local BASE_W, BASE_H = 1080, 700
local function fit()
    local c, lib = controller(), Menu.classes()
    if not (win and c and lib) then return end
    local layout = StaticFindObject("/Script/UMG.Default__WidgetLayoutLibrary")
    local vw, vh, dpi = 1920, 1080, 1
    pcall(function()
        local v = layout:GetViewportSize(c)
        vw, vh = v.X, v.Y
        dpi = layout:GetViewportScale(c)
    end)
    if not (vw > 0 and vh > 0 and dpi > 0) then vw, vh, dpi = 1920, 1080, 1 end
    -- As if the screen were 1080 pixels tall with no shrink: the sizes above are made for that.
    local s = math.max(0.7, vh / 1080) / dpi * size
    local slateW, slateH = vw / dpi, vh / dpi   -- the screen in the UI's own units
    win.scaler:SetUserSpecifiedScale(s)
    win.sizer:SetWidthOverride(math.min(BASE_W, slateW * 0.94 / s))
    win.sizer:SetHeightOverride(math.min(BASE_H, slateH * 0.92 / s))
end

-- Whether a kept object is still the one it was: a destroyed object's slot can be taken by another
-- object, which then looks valid but is of another class.
local function alive(o, cls)
    local ok, yes = pcall(function() return o:IsValid() and o:GetClass():GetFName():ToString() == cls end)
    return ok and yes
end

-- The window is the player controller's: a new level brings a new controller and clears the viewport,
-- so the window is made again then (the old one is never touched again).
local function windowOk()
    local c = controller()
    return win and c and win.owner == c:GetAddress() and alive(win.widget, win.cls)
end

local function ensureWindow()
    if windowOk() then return true end
    local c, lib = controller(), Menu.classes()
    if not (c and lib) then return false end
    local ok, made = pcall(build, c, lib)
    if not ok then
        log("couldn't make the menu window: %s", tostring(made))
        return false
    end
    win = made
    win.owner, win.cls = c:GetAddress(), win.widget:GetClass():GetFName():ToString()
    Menu.share("content", win.content)
    Menu.share("tree", win.tree)
    Menu.share("frame", win.frame)   -- where the window is on screen, for `wcmods agent shot --menu`
    Menu.share("window", win.widget)   -- focus goes back to it after a mouse click (Menu.clicked)
    return true
end

-- ---------- tabs ----------
-- The side bar lists the pages under their groups (Menu.groups), in order; a group of a script's own
-- comes after Mods, and a page without a group is under Mods.
local GROUP_RANK, GROUP_LABEL = {}, {}
for i, g in ipairs(Menu.groups) do GROUP_RANK[g.id], GROUP_LABEL[g.id] = i, g.label end
local function groupRank(g) return GROUP_RANK[g] or (GROUP_RANK.mods + 0.5) end

local function pageList()
    local out = {}
    for line in (Menu.shared("pages") or ""):gmatch("([^\n]+)") do
        local id, title, order, group = line:match("^([^\t]*)\t([^\t]*)\t([^\t]*)\t?([^\t]*)")   -- then the mod's name, which the tabs don't need
        if id then out[#out + 1] = { id = id, title = title, order = tonumber(order) or 50, group = group ~= "" and group or "mods" } end
    end
    table.sort(out, function(a, b)
        local ra, rb = groupRank(a.group), groupRank(b.group)
        if ra ~= rb then return ra < rb end
        if a.group ~= b.group then return a.group < b.group end
        if a.order ~= b.order then return a.order < b.order end
        return a.title < b.title
    end)
    return out
end

-- ---------- C++ mods ----------
-- WCMods.hpp puts WCModsCpp.mods[<id>] into this state as it starts: each C++ mod's pages (its settings page
-- among them), its keys for the Overview, and the values it shares. Pages are picked up when the menu opens,
-- since a C++ mod may add one after this script started.
local cppPages = {}
local function cppShare(name, value)
    if type(WCModsCpp) == "table" and WCModsCpp.share then pcall(WCModsCpp.share, name, value) end
end
local function syncCpp()
    if type(WCModsCpp) ~= "table" or type(WCModsCpp.mods) ~= "table" then return end
    for _, m in pairs(WCModsCpp.mods) do
        local ok, list = pcall(m.pages)
        for _, p in ipairs(ok and type(list) == "table" and list or {}) do
            if p.id and not cppPages[p.id] then
                cppPages[p.id] = true
                Menu.page(p.title or p.id, function(ui) m.draw(p.id, ui) end, { id = p.id, order = p.order, group = p.group })
            end
        end
        local okK, keys = pcall(m.keys)
        for line in (okK and tostring(keys or "") or ""):gmatch("([^\n]+)") do
            local key, what = line:match("^([^\t]*)\t(.*)$")
            if key then Menu.key(key, what) end
        end
    end
end

-- Quests of C++ mods' own, on the Quests page (WCModsCpp.mods[id].quests(): "id\ttitle\tstatus\tobjective\tprogress"
-- lines; an empty title takes one off), passed on through WCModsGame's Game.quests.report once a second.
local cppQuests = {}
local okCppGame, CppGame = pcall(require, "WCModsGame")
local function syncCppQuests()
    if type(WCModsCpp) ~= "table" or type(WCModsCpp.mods) ~= "table" or not okCppGame then return end
    for _, m in pairs(WCModsCpp.mods) do
        local ok, lines = pcall(m.quests)
        for line in (ok and tostring(lines or "") or ""):gmatch("([^\n]+)") do
            local id, title, status, objective, progress = line:match("^([^\t]*)\t([^\t]*)\t([^\t]*)\t([^\t]*)\t(.*)$")
            if id and id ~= "" and cppQuests[id] ~= line then
                cppQuests[id] = line
                if title == "" then
                    CppGame.quests.report(id, nil)
                else
                    CppGame.quests.report(id, { title = title, status = status, objective = objective, progress = progress, by = "C++" })
                end
            end
        end
    end
end
if okCppGame and CppGame.every then CppGame.every(1, syncCppQuests) end

local generation = 0
local function show(id)
    if win then
        win.pointAt = 0   -- the new page's first control, as soon as it has one
        -- Focus on the old page would go with it (a script opening another page): put it on the tab.
        if Menu.focused(win.content) then win.focusTab = true end
    end
    Menu.share("page", id)
    cppShare("menu.page", id)
    pcall(function() win.content:ClearChildren() end)
    generation = generation + 1
    Menu.share("generation", generation)
end

local function updateTabs()
    local list = pageList()
    local key = {}
    for i, p in ipairs(list) do key[i] = p.id end
    key = table.concat(key, "\n")
    if key ~= win.tabList then
        win.tabList = key
        win.tabs:ClearChildren()
        win.tabButtons = {}
        local group
        for _, p in ipairs(list) do
            if p.group ~= group then
                group = p.group
                local h = text((GROUP_LABEL[group] or group):upper(), 12, THEME.muted)
                local hslot = win.tabs:AddChild(h)
                hslot:SetPadding({ Left = 4, Top = #win.tabButtons > 0 and 10 or 0, Right = 0, Bottom = 4 })
            end
            local b = Menu.button(p.title, nil, 13)
            local r = Menu.ring(b)
            local slot = win.tabs:AddChild(r)
            slot:SetPadding({ Left = 0, Top = 0, Right = 0, Bottom = 1 })
            win.tabButtons[#win.tabButtons + 1] = { id = p.id, title = p.title, b = b, r = r, state = {} }
        end
    end
    local current = Menu.shared("page")
    local known = false
    for _, t in ipairs(win.tabButtons) do
        if t.id == current then known = true end
    end
    if not known and win.tabButtons[1] then
        current = win.tabButtons[1].id
        show(current)
    end
    for _, t in ipairs(win.tabButtons) do
        if Menu.clicked(t.state, "b", t.b) and t.id ~= current then
            current = t.id
            show(current)
        end
    end
    for _, t in ipairs(win.tabButtons) do
        local sel = t.id == current
        if t.sel ~= sel then
            t.sel = sel
            t.b:SetContent(text(t.title, 13, sel and THEME.selected_text or THEME.text))
            t.b:SetBackgroundColor(C(sel and THEME.selected or "#2a313c"))
        end
    end
    -- Opening the menu puts focus on its page's tab, so the keyboard and a controller start there.
    if win.focusTab then
        win.focusTab = false
        for _, t in ipairs(win.tabButtons) do
            if t.id == current then pcall(function() t.b:SetKeyboardFocus() end) end
        end
    end
end

-- Right from the side bar goes to the page's first control. The engine only looks straight across,
-- where a page often has text, so each tab is told where to go; it's looked for again twice a second,
-- as pages make and drop their rows.
local CONTROLS = { Button = true, CheckBox = true, Slider = true, SpinBox = true, EditableTextBox = true,
                   ComboBoxString = true }
local function firstControl(w, depth)
    if not valid(w) or depth > 12 then return nil end
    if CONTROLS[w:GetClass():GetFName():ToString()] then return w end
    local ok, n = pcall(function() return w:GetChildrenCount() end)
    if ok and type(n) == "number" then
        for i = 0, n - 1 do
            local found = firstControl(w:GetChildAt(i), depth + 1)
            if found then return found end
        end
        return nil
    end
    local okc, c = pcall(function() return w:GetContent() end)
    return okc and firstControl(c, depth + 1) or nil
end
local NAV_RIGHT = 1
local function pointTabs()
    if os.clock() < (win.pointAt or 0) then return end
    win.pointAt = os.clock() + 0.5
    local first = firstControl(win.content, 0)
    local key = (first and tostring(first:GetAddress()) or "") .. "|" .. tostring(win.tabList) .. "|" .. generation
    if key == win.pointed then return end
    win.pointed = key
    for _, t in ipairs(win.tabButtons) do
        if first then pcall(function() t.b:SetNavigationRuleExplicit(NAV_RIGHT, first) end)
        else pcall(function() t.b:SetNavigationRuleBase(NAV_RIGHT, 0) end) end   -- 0: Escape, the engine's own
    end
end

-- The rings round the window's own controls, and which of them has focus (WCModsMenu.focus, for the
-- agent; a page's own rows say so in their reads).
local function showFocus()
    local where = ""
    local function light(x, w, name)
        local f = Menu.focused(w)
        if f then where = name end
        if x.lit ~= f then
            x.lit = f
            x.r:SetBrushColor(C(f and THEME.focus or "#00000000"))
        end
    end
    for _, x in ipairs(win.rings) do light(x, x.w, x.name) end
    local inTabs = Menu.focused(win.tabs)   -- once, rather than asking every tab
    for _, t in ipairs(win.tabButtons) do
        if inTabs or t.lit then light(t, t.b, "tab\t" .. t.title) end
    end
    if where ~= win.focusShared then
        win.focusShared = where
        Menu.share("focus", where)
    end
end

-- ---------- opening and closing ----------
local isOpen, before, paused = false, nil, false

local function setPaused(on)
    local c = controller()
    if c and Menu.classes() then pcall(function() Menu.classes().statics:SetGamePaused(c, on) end) end
    paused = on
end

-- byPad: opened with the controller's button (SETTINGS.pad). The game only hears a controller while it
-- has input, and a menu that takes all input (as with the keyboard) couldn't be closed from one. So this
-- menu leaves the game its input, with the game paused, so the stick doesn't walk your cat, and the
-- button or B closes it.
local byPad = false
local function openMenu(fromPad)
    if isOpen or not ensureWindow() then return end
    local c, lib = controller(), Menu.classes()
    before = { cursor = c.bShowMouseCursor, pause = win.pause:IsChecked() }
    win.widget:SetVisibility(VISIBLE)
    fit()
    c.bShowMouseCursor = true
    pcall(function() win.widget:SetIsFocusable(true) end)
    byPad = fromPad and true or false
    if byPad then
        pcall(function() win.pause:SetIsChecked(true) end)
        pcall(function() lib.widgets:SetInputMode_GameAndUIEx(c, win.widget, 0, false, true) end)
    else
        pcall(function() lib.widgets:SetInputMode_UIOnlyEx(c, win.widget, 0, false) end)
    end
    win.focusTab = true
    isOpen = true
    Menu.share("open", true)
    cppShare("menu.open", true)
    syncCpp()
    show(Menu.shared("page") or "")
    if win.pause:IsChecked() then setPaused(true) end
end

local function closeMenu()
    if not isOpen then return end
    isOpen = false
    Menu.share("open", false)
    cppShare("menu.open", false)
    if paused then setPaused(false) end
    local wasPad = byPad
    byPad = false
    if windowOk() then
        win.widget:SetVisibility(COLLAPSED)
        pcall(function() win.content:ClearChildren() end)
        -- Opened from the controller, it ticked "Pause the game": put that back as it was.
        if wasPad and before then pcall(function() win.pause:SetIsChecked(before.pause) end) end
    end
    local c, lib = controller(), Menu.classes()
    if c and lib then
        c.bShowMouseCursor = before and before.cursor or false
        -- As the game's own menus leave it; mouse look takes the mouse back by itself when it's on.
        -- Flushing input: a key let go while the menu had the keyboard would otherwise stay down.
        if not pcall(function() lib.widgets:SetInputMode_GameAndUIEx(c, nil, 0, false, true) end) then
            pcall(function() lib.widgets:SetInputMode_GameAndUIEx(c, CreateInvalidObject(), 0, false, true) end)
        end
    end
end

-- What the status line under the header says: the Game pages fill this in (HOST.status).
local HOST = { status = nil, statusOn = true }
local statusAt, statusShown = -1, nil

local function tick()
    if not isOpen then return end
    if not windowOk() then
        -- The level changed under the open menu: the game cleared the viewport.
        isOpen, byPad = false, false
        Menu.share("open", false)
        return
    end
    updateTabs()
    pointTabs()
    showFocus()
    if HOST.status and os.clock() - statusAt >= 0.5 then
        statusAt = os.clock()
        local ok, line = pcall(HOST.status)
        line = (HOST.statusOn and ok and line) or (SETTINGS.opens .. " opens and closes this menu. Changes apply at once; " ..
                                                   "a page's Save keeps them.")
        if line ~= statusShown then
            statusShown = line
            pcall(function() win.status:SetText(FText(line)) end)
        end
    end
    for _, key in ipairs({ "smaller", "bigger" }) do
        if Menu.clicked(win.state, key, win[key]) then
            size = math.max(SETTINGS.size_min, math.min(SETTINGS.size_max, size * (key == "bigger" and 1.12 or 1 / 1.12)))
            fit()
        end
    end
    if Menu.clicked(win.state, "close", win.close) then closeMenu() end
    if isOpen and win.pause:IsChecked() ~= paused then setPaused(win.pause:IsChecked()) end
end

-- Work that needs doing once a second (cheats on a new level's cat). It runs here, on the game thread
-- with everything else: a LoopAsync would run it on another thread in this same Lua state, and two
-- threads in one Lua state at once crash the game.
local everySecond, nextSecond = {}, 0

-- A script asked for the menu (Menu.open / Menu.close).
local function requests()
    local req = Menu.shared("request")
    if not req or req == "" then return end
    Menu.share("request", "")
    local what, page = tostring(req):match("^(%a+)\t(.*)$")
    if what == "close" then
        closeMenu()
    elseif what == "open" then
        if page ~= "" then
            for _, p in ipairs(pageList()) do
                if p.id == page or p.title == page then
                    Menu.share("page", p.id)
                    break
                end
            end
        end
        if isOpen then show(Menu.shared("page") or "") else openMenu() end
    end
end

-- The controller's button (and, while the menu is open from it, B): read from the game's own input.
local PAD = SETTINGS.pad ~= "" and { KeyName = FName(SETTINGS.pad) } or nil
local PAD_BACK = { KeyName = FName("Gamepad_FaceButton_Right") }
local function pressed(k)
    local c = controller()
    if not c then return false end
    local ok, yes = pcall(function() return c:WasInputKeyJustPressed(k) end)
    return ok and yes == true
end
local function gamePaused()
    local c = controller()
    local ok, yes = pcall(function() return Menu.classes().statics:IsGamePaused(c) end)
    return ok and yes == true
end
local function padButton()
    if not isOpen then
        -- Not while something else has paused the game (its own pause menu, on Start): the menu would
        -- unpause it on closing, under that menu.
        if pressed(PAD) and not gamePaused() then openMenu(true) end
    elseif byPad and (pressed(PAD) or pressed(PAD_BACK)) then
        closeMenu()
    end
end

local function frame()
    local ok, err = pcall(tick)
    if not ok then log("error: %s", tostring(err)) end
    if PAD then
        local okP, errP = pcall(padButton)
        if not okP then log("error: %s", tostring(errP)) end
    end
    local okR, errR = pcall(requests)
    if not okR then log("error: %s", tostring(errR)) end
    local now = os.clock()
    if now >= nextSecond then
        nextSecond = now + 1
        for _, fn in ipairs(everySecond) do
            local ok2, err2 = pcall(fn)
            if not ok2 then log("error: %s", tostring(err2)) end
        end
    end
end

if LoopInGameThreadAfterFrames == nil or not pcall(LoopInGameThreadAfterFrames, 1, frame) then
    LoopAsync(16, function()
        ExecuteInGameThread(frame)
        return false
    end)
end

local key = Key[SETTINGS.key] or Key.INS
RegisterKeyBind(key, function()
    ExecuteInGameThread(function()
        local ok, err = pcall(function() if isOpen then closeMenu() else openMenu() end end)
        if not ok then log("error: %s", tostring(err)) end
    end)
end)
RegisterKeyBind(Key.ESCAPE, function()
    ExecuteInGameThread(function() if isOpen then pcall(closeMenu) end end)
end)

-- ---------- the host's own pages ----------
local function show_value(ui, label, v, depth)
    depth = depth or 0
    if type(v) ~= "table" then
        ui.field(string.rep("   ", depth) .. label, tostring(v))
        return
    end
    local keys = {}
    for k in pairs(v) do keys[#keys + 1] = k end
    table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
    if #keys == 0 then
        ui.field(string.rep("   ", depth) .. label, "(none)")
        return
    end
    local simple = #v > 0
    for _, x in ipairs(v) do if type(x) == "table" then simple = false end end
    if simple then
        local parts = {}
        for i, x in ipairs(v) do parts[i] = tostring(x) end
        ui.field(string.rep("   ", depth) .. label, table.concat(parts, ", "))
        return
    end
    if label ~= "" then ui.field(string.rep("   ", depth) .. label, "") end
    for i, k in ipairs(keys) do
        if i > 40 then
            ui.note(string.format("... and %d more", #keys - 40))
            break
        end
        show_value(ui, tostring(k), v[k], depth + 1)
    end
end

Menu.page("Installed mods", function(ui)
    ui.heading("Installed mods")
    ui.note("Built " .. SETTINGS.built .. ". Turn mods on and off and change what they do in Clan Mod Studio, " ..
            "then install again. Mods with live settings have pages of their own below this one.")
    if #SETTINGS.mods == 0 then ui.text("No mods are on.") end
    for _, m in ipairs(SETTINGS.mods) do
        ui.section(m.name, function()
            if m.description ~= "" then ui.text(m.description) end
            ui.field("Folder", "mods/" .. m.id)
            ui.field("Contains", #m.kinds > 0 and table.concat(m.kinds, ", ") or "nothing yet")
            ui.field("Priority", m.priority)
        end, { id = "mod:" .. m.id, open = false })
    end
    ui.separator()
    ui.heading("What the build set up")
    for _, s in ipairs(SETTINGS.sections) do
        ui.section(s.title, function()
            ui.field("From", table.concat(s.mods, ", "))
            if s.status ~= "ok" then ui.text("Status: " .. s.status, { color = THEME.danger }) end
            for _, err in ipairs(s.errors) do ui.text(err, { color = THEME.danger }) end
            if s.notes then show_value(ui, "", s.notes) end
        end, { id = "section:" .. s.id, open = false })
    end
    if #SETTINGS.warnings > 0 then
        ui.section("Build warnings", function()
            for _, w in ipairs(SETTINGS.warnings) do ui.note(w) end
        end, { open = false })
    end
end, { order = 1, group = "home" })

-- Nearby things, through WCModsWorld: any kinds at once, each in its own colour, in the list and (with
-- "Mark them on screen") as markers drawn with WCModsDraw.
local okWorld, World = pcall(require, "WCModsWorld")
local okDraw, Draw = pcall(require, "WCModsDraw")
if okWorld then
    local look = { radius = 3000, mark = false, on = { pickups = true }, colors = {} }
    local function colorOf(kind) return look.colors[kind] or World.kindColor(kind) end
    local found, foundAt, foundKey = {}, nil, ""
    local function refresh()
        local kinds = {}
        for _, k in ipairs(World.kindOrder()) do
            if look.on[k] then kinds[#kinds + 1] = k end
        end
        local key = table.concat(kinds, ",") .. "@" .. look.radius
        if foundAt == nil or key ~= foundKey or os.clock() - foundAt >= 0.5 then
            foundAt, foundKey = os.clock(), key
            local all = {}
            for _, k in ipairs(kinds) do
                for _, it in ipairs(World.nearby(k, look.radius)) do
                    it.kind = k
                    all[#all + 1] = it
                end
            end
            table.sort(all, function(a, b) return a.distance < b.distance end)
            found = all
        end
        return found
    end
    Menu.page("Nearby", function(ui)
        ui.heading("Nearby")
        ui.note("What's around your cat, from the game's own objects (WCModsWorld). Tick the kinds to show; " ..
                "each has its own colour, here and on screen.")
        local r = ui.slider("Within", look.radius, 500, 20000, { step = 500, format = "%.0f cm" })
        if math.abs(r - look.radius) >= 1 then look.radius, foundAt = r, nil end
        if okDraw then look.mark = ui.switch("Mark them on screen", look.mark) end
        for _, k in ipairs(World.kindOrder()) do
            look.on[k] = ui.toggle(World.kindLabel(k), look.on[k] or false, { swatch = colorOf(k) })
        end
        ui.section("Colours", function()
            for _, k in ipairs(World.kindOrder()) do look.colors[k] = ui.color(World.kindLabel(k), colorOf(k)) end
        end, { open = false })
        ui.separator()
        if not World.player() then
            ui.text("Not in the world yet.")
            return
        end
        local list = refresh()
        ui.field("Found", #list)
        for i, it in ipairs(list) do
            if i > 40 then
                ui.note(string.format("... and %d more", #list - 40))
                break
            end
            ui.field(string.format("%.0f m", it.distance / 100), it.label .. "   (" .. World.kindLabel(it.kind) .. ")",
                     { color = colorOf(it.kind) })
        end
    end, { order = 22, group = "world" })
    if okDraw then
        Draw.onFrame(function(d)
            if not look.mark then return end
            local shown, per = 0, {}
            for _, it in ipairs(refresh()) do
                if shown >= 80 then break end
                per[it.kind] = (per[it.kind] or 0) + 1
                if per[it.kind] <= 20 and it.actor:IsValid() then
                    shown = shown + 1
                    d.marker(it.location, it.label, { color = colorOf(it.kind), size = 9, textSize = 13 })
                end
            end
        end)
    end
end

-- ---------- cheats ----------
-- Cheats are the engine's cheat manager on the player controller, as in the game's own debug builds
-- (the release build leaves it out). With it, the console's cheat commands work (god, slomo,
-- teleport ...), and the page below has the handy ones. Flying and size are done here instead of with
-- the engine's fly, ghost and changesize, which the game undoes (see below).
-- SETTINGS.cheats (wcmods.json "cheats") says whether they start on; the page switches them live.
-- god: whether this page turned god mode on (the game makes the cat safe by itself at times too).
local cheats = { on = SETTINGS.cheats, movement = "Walk", speed = 1, size = 1, god = false, flySpeed = 900, command = "" }

local function cheatManager(c)
    local ok, cm = pcall(function() return c.CheatManager end)
    if ok and valid(cm) then return cm end
    return nil
end

local function makeCheatManager(c)
    if cheatManager(c) then return cheatManager(c) end
    local cls = c.CheatClass   -- the game's own cheat class when it has one
    if not valid(cls) then cls = StaticFindObject("/Script/Engine.CheatManager") end
    if not valid(cls) then return nil end
    local cm = StaticConstructObject(cls, c, FName("None"))
    if not valid(cm) then return nil end
    c.CheatManager = cm
    pcall(function() cm:ReceiveInitCheatManager() end)
    log("cheats on (%s)", cls:GetFName():ToString())
    return cm
end

local function setSpeed(c, v)
    pcall(function() Menu.classes().statics:SetGlobalTimeDilation(c, v) end)
end

local function pawnOf(c)
    local ok, p = pcall(function() return c.Pawn end)
    if ok and valid(p) then return p end
    return nil
end

-- ---- flying, done here ----
-- The engine's Fly and Ghost switch the cat's movement mode, and the game sets it straight back each
-- frame. So while Fly or Ghost is on, the cat has no gravity and its movement component stands still
-- (MOVE_None), and this moves it each frame where the game's own controls point it (the way it would
-- W A S D and the left stick, by the camera), with Space and Left Ctrl (or the triggers) for up and
-- down. Fly stops at walls; Ghost turns collision off.
local MOVE_NONE, MOVE_FALLING = 0, 3
local function key(name) return { KeyName = FName(name) } end
local keys = {
    up = key("SpaceBar"), down = key("LeftControl"), w = key("W"), a = key("A"), s = key("S"), d = key("D"),
    stickX = key("Gamepad_LeftX"), stickY = key("Gamepad_LeftY"),
    rise = key("Gamepad_RightTriggerAxis"), sink = key("Gamepad_LeftTriggerAxis"),
}
local held   -- { pawn = its address, gravity = the game's GravityScale } while flying

local function land(pawn)
    if held and pawn and pawn:GetAddress() == held.pawn then
        pcall(function()
            local m = pawn.CharacterMovement
            m.GravityScale = held.gravity
            m:SetMovementMode(MOVE_FALLING, 0)
        end)
        pcall(function() pawn:SetActorEnableCollision(true) end)
    end
    held = nil
end

local function setMovement(c, move)
    local pawn = pawnOf(c)
    if move == "Walk" then land(pawn) end
    if pawn and move ~= "Walk" then pcall(function() pawn:SetActorEnableCollision(move ~= "Ghost") end) end
    cheats.movement = move
end

local function down(c, key)
    local ok, yes = pcall(function() return c:IsInputKeyDown(key) end)
    return ok and yes
end

local function flyTick()
    if not cheats.on or cheats.movement == "Walk" then return end
    local c = controller()
    local pawn = c and pawnOf(c)
    if not pawn then return end
    local m = pawn.CharacterMovement
    if not valid(m) then return end
    if not held or held.pawn ~= pawn:GetAddress() then   -- a new cat (a new area): start it flying
        held = { pawn = pawn:GetAddress(), gravity = m.GravityScale }
        pawn:SetActorEnableCollision(cheats.movement ~= "Ghost")
    end
    m.GravityScale = 0
    if m.MovementMode ~= MOVE_NONE then m:SetMovementMode(MOVE_NONE, 0) end
    m.Velocity = { X = 0, Y = 0, Z = 0 }
    if isOpen then return end   -- the menu has the controls
    -- The game stops updating its own movement direction while the cat floats (it would keep the
    -- last one), so this reads the controls itself: W A S D (the game's own keys, which the key
    -- remapper sends too) and the left stick, by the camera's direction.
    pcall(function() pawn:ConsumeMovementInputVector() end)   -- don't let the game's input pile up
    local function axis(k)
        local ok, v = pcall(function() return c:GetInputAnalogKeyState(k) end)
        if ok and math.abs(v or 0) > 0.2 then return v end
        return 0
    end
    local f = (down(c, keys.w) and 1 or 0) - (down(c, keys.s) and 1 or 0) + axis(keys.stickY)
    local r = (down(c, keys.d) and 1 or 0) - (down(c, keys.a) and 1 or 0) + axis(keys.stickX)
    local dx, dy = 0, 0
    if f ~= 0 or r ~= 0 then
        local yaw = math.rad(c.PlayerCameraManager:GetCameraRotation().Yaw)
        dx = f * math.cos(yaw) - r * math.sin(yaw)
        dy = f * math.sin(yaw) + r * math.cos(yaw)
        local n = math.sqrt(dx * dx + dy * dy)
        if n > 1 then dx, dy = dx / n, dy / n end
    end
    local dz = (down(c, keys.up) and 1 or 0) - (down(c, keys.down) and 1 or 0) + axis(keys.rise) - axis(keys.sink)
    if dx == 0 and dy == 0 and dz == 0 then return end
    local step = cheats.flySpeed * Menu.classes().statics:GetWorldDeltaSeconds(c)
    local l = pawn:K2_GetActorLocation()
    pawn:K2_SetActorLocation({ X = l.X + dx * step, Y = l.Y + dy * step, Z = l.Z + dz * step },
                             cheats.movement == "Fly", {}, false)
    if dx ~= 0 or dy ~= 0 then
        pawn:K2_SetActorRotation({ Pitch = 0, Yaw = math.deg(math.atan(dy, dx)), Roll = 0 }, false)
    end
end
if LoopInGameThreadAfterFrames == nil or not pcall(LoopInGameThreadAfterFrames, 1, function() pcall(flyTick) end) then
    LoopAsync(16, function()
        ExecuteInGameThread(function() pcall(flyTick) end)
        return false
    end)
end

-- ---- size, done here ----
-- The engine's ChangeSize resizes the cat's collision capsule and sets its mesh's scale, but leaves
-- the mesh where it was in the capsule (so a bigger cat floats), and the game sets the mesh's scale
-- back. Scaling the whole cat (the actor) grows the capsule and everything on it together; growing
-- lifts it by the capsule's extra height so it doesn't start inside the ground.
local scaled   -- { pawn = its address, base = the game's actor scale } while the size isn't 1

local function setSize(c, f)
    local pawn = pawnOf(c)
    if not pawn then return end
    if not scaled or scaled.pawn ~= pawn:GetAddress() then
        local now = pawn:GetActorScale3D()
        scaled = { pawn = pawn:GetAddress(), base = { X = now.X, Y = now.Y, Z = now.Z } }
    end
    local cap = pawn.CapsuleComponent
    local before = cap:GetScaledCapsuleHalfHeight()
    local b = scaled.base
    pawn:SetActorScale3D({ X = b.X * f, Y = b.Y * f, Z = b.Z * f })
    local after = cap:GetScaledCapsuleHalfHeight()
    if after > before then
        local l = pawn:K2_GetActorLocation()
        pawn:K2_SetActorLocation({ X = l.X, Y = l.Y, Z = l.Z + (after - before) + 1 }, false, {}, true)
    end
    cheats.size = f
    if f == 1 then scaled = nil end
end

local function cheatsOff(c)
    local cm, pawn = cheatManager(c), pawnOf(c)
    if cheats.movement ~= "Walk" then setMovement(c, "Walk") end
    if cheats.size ~= 1 then pcall(setSize, c, 1) end
    if cm then
        if cheats.god and pawn and not pawn.bCanBeDamaged then pcall(function() cm:God() end) end
        if not pcall(function() c.CheatManager = nil end) then c.CheatManager = CreateInvalidObject() end
        log("cheats off")
    end
    if cheats.speed ~= 1 then setSpeed(c, 1) end
    cheats.movement, cheats.speed, cheats.size, cheats.god = "Walk", 1, 1, false
end

-- A new level brings a new player controller without a cheat manager, and a new cat: give them the
-- cheats that are on. The game may set the cat's scale again too, so the size is checked each second.
everySecond[#everySecond + 1] = function()
    if not cheats.on then return end
    local c = controller()
    local pawn = c and pawnOf(c)
    if not pawn then return end
    if not cheatManager(c) then
        makeCheatManager(c)
        cheats.god = false
    end
    if cheats.size ~= 1 then
        local now = pawn:GetActorScale3D()
        local want = scaled and scaled.pawn == pawn:GetAddress() and scaled.base.X * cheats.size or nil
        if not want or math.abs(now.X - want) > 0.01 * want then setSize(c, cheats.size) end
    end
end

-- Run a console command as if typed in the game's console.
local function console(c, cmd)
    local lib = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
    if valid(lib) then lib:ExecuteConsoleCommand(c, cmd, c) end
end

Menu.page("Cheats", function(ui)
    ui.heading("Cheats")
    ui.note("The engine's cheat commands, as in the game's debug builds. They start " ..
            (SETTINGS.cheats and "on" or "off") .. " each time (Clan Mod Studio, Mods page, In game). " ..
            "Some can break a quest or a save: back up first (Mods page) if you're unsure.")
    local c = controller()
    if not c then
        ui.text("No player yet.")
        return
    end
    local on = ui.switch("Cheats", cheats.on)
    if on ~= cheats.on then
        cheats.on = on
        if on then
            if not makeCheatManager(c) then ui.text("Couldn't make a cheat manager.", { color = THEME.danger }) end
        else
            cheatsOff(c)
        end
    end
    if not cheats.on then return end
    local cm = cheatManager(c)
    if not cm then
        cm = makeCheatManager(c)
        if not cm then
            ui.text("Couldn't make a cheat manager.", { color = THEME.danger })
            return
        end
    end
    local pawn = c.Pawn

    ui.separator()
    if valid(pawn) then
        local god = ui.toggle("God mode (nothing hurts you)", not pawn.bCanBeDamaged)
        if god == pawn.bCanBeDamaged then
            cm:God()
            cheats.god = god
        end
        local move = ui.radio("Moving", cheats.movement, { "Walk", "Fly", "Ghost" })
        if move ~= cheats.movement then setMovement(c, move) end
        if cheats.movement ~= "Walk" then
            ui.note("W A S D or the left stick move you the way the camera faces; Space and Left Ctrl (or the triggers) " ..
                    "go up and down. Fly stops at walls; Ghost goes through them.")
            cheats.flySpeed = ui.slider("Flying speed", cheats.flySpeed, 200, 4000, { step = 100, format = "%.0f cm/s" })
        end
        local size = ui.slider("Cat size", cheats.size, 0.25, 4, { step = 0.05, format = "x%.2f" })
        if math.abs(size - cheats.size) > 0.001 then setSize(c, size) end
        if ui.button("Teleport to where the camera looks") then cm:Teleport() end
    else
        ui.note("Movement cheats show once you're in the world.")
    end
    local speed = ui.slider("Game speed", cheats.speed, 0.1, 4, { step = 0.05, format = "x%.2f" })
    if math.abs(speed - cheats.speed) > 0.001 then
        cheats.speed = speed
        setSpeed(c, speed)
    end

    ui.separator()
    cheats.command = ui.input("Engine command", cheats.command, { hint = "e.g. stat fps" })
    local hit = ui.buttons({ "Run", "stat fps", "stat unit" })
    if hit == 1 and cheats.command ~= "" then console(c, cheats.command)
    elseif hit == 2 then console(c, "stat fps")
    elseif hit == 3 then console(c, "stat unit") end

    ui.separator()
    ui.note("The game's own developer switches (always full health or stamina, attacks that always land, " ..
            "fast den building ...) are on the Game switches page.")
end, { order = 50, group = "cheats" })
@PAGES@
log("ready: %s opens the mod menu", SETTINGS.key_name)
syncCpp()

'''

# The menu's size, as a factor on the usual: what menu.json "size", the studio and A-/A+ in game stay within.
SCALES = (0.6, 2.2)
KEY_NAMES = {"INS": "Insert", "HOME": "Home", "END": "End", "DEL": "Delete", "PAGE_UP": "Page Up",
             "PAGE_DOWN": "Page Down"}
# Controller buttons the game leaves free while you play (its own: the face buttons, bumpers, the left
# trigger, moving the sticks and Start; the right trigger is fly and ghost's up, on the Cheats page), as
# Unreal key names; "" for none. View is Back on older Xbox pads, Create or Share on PlayStation and -
# on Switch.
DEFAULT_PAD = "Gamepad_Special_Left"
PAD_NAMES = {"Gamepad_Special_Left": "View", "Gamepad_LeftThumbstick": "Left stick click",
             "Gamepad_RightThumbstick": "Right stick click", "Gamepad_DPad_Up": "D-pad up",
             "Gamepad_DPad_Down": "D-pad down", "Gamepad_DPad_Left": "D-pad left", "Gamepad_DPad_Right": "D-pad right",
             "": "None"}
PADS = tuple(PAD_NAMES)


# The side bar's groups, in order: id, label, and what the Overview page says is there (Home holds the
# Overview itself; Tools gains the Inspector and the Lua console with code mods allowed, said in the Lua).
# Written into the Lua as Menu.groups; the agent's menu driver (agent/menu.py) and the C++ SDK's
# PageOptions (cpp_sdk/include/WCMods/Menu.hpp) follow it.
GROUPS = (
    {"id": "home", "label": "Home"},
    {"id": "cat", "label": "Your cat",
     "where": "Stats: health, stamina, level and stats. Colours and Mouse look, when those mods are on."},
    {"id": "world", "label": "World", "where": "The time of day and the fresh-kill pile; Travel; what's Nearby; your Items."},
    {"id": "story", "label": "Story", "where": "Quests: the one you follow, its objectives, and every quest's state."},
    {"id": "fight", "label": "Fight", "where": "Both sides of a fight while you're in one."},
    {"id": "cheats", "label": "Cheats", "where": "The engine's cheats, and the game's own developer switches."},
    {"id": "mods", "label": "Mods", "where": "Pages from the mods you have on."},
    {"id": "tools", "label": "Tools", "where": "The log, this menu's settings"},
)


def lua():
    """The shared WCModsMenu module, with the side bar's groups in."""
    return LUA.replace("@GROUPS@", lua_value([dict(g) for g in GROUPS]))


def host_script(manifest, mods, key=DEFAULT_KEY, cheats=False, scale=1.0, dev=False, pages=None, pad=DEFAULT_PAD):
    """The host's script, with the overview of this build: the enabled mods and what each section set.
    cheats: whether the Cheats page starts with cheats on (wcmods.json "cheats"); scale: the menu's size,
    1 for the usual (wcmods.json "menu_scale"); dev: whether the Inspector and Console pages are in
    (they're for code mods, so wcmods.json "allow_code_mods"); pages: menupages.data(), the area names and
    quest titles the pages show; pad: the controller button that opens it too (an Unreal key name, "" for
    none)."""
    if key not in KEYS:
        raise ValueError(f"the menu's key should be one of {', '.join(KEYS)}")
    enabled = [m for m in mods if m.enabled]
    sections = []
    for sid, rep in manifest["sections"].items():
        if not rep.get("mods"):
            continue
        sections.append({"id": sid, "title": rep["title"], "status": rep["status"], "errors": rep.get("errors", []),
                         "mods": rep["mods"], "notes": manifest["notes"].get(sid)})
    key_name, pad_name = KEY_NAMES.get(key, key), PAD_NAMES.get(pad, pad) if pad else ""
    settings = {
        "key": key, "key_name": key_name, "built": manifest["built"].replace("T", " "),
        "pad": pad or "", "pad_name": pad_name, "opens": key_name + (f" (or {pad_name} on a controller)" if pad else ""),
        "cheats": bool(cheats), "scale": float(scale), "size_min": SCALES[0], "size_max": SCALES[1], "dev": bool(dev),
        "mods": [{"id": m.id, "name": m.name, "description": m.description, "kinds": m.kinds(),
                  "priority": m.priority} for m in enabled],
        "sections": sections, "warnings": manifest["warnings"],
    }
    from . import menupages
    return (HOST_LUA.replace("@SETTINGS@", lua_value(settings)).replace("@KEY@", KEY_NAMES.get(key, key))
            .replace("@PAGES@", menupages.lua(pages)))
