-- WCModsMenu: pages in the in-game mod menu (Insert). Installed by wcmods with UE4SS, the window too;
-- any UE4SS script can add one:
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
-- Lines go to UE4SS.log under the name of the mod whose page it is (WCModsGame's, set by the script bootstrap, in
-- this Lua state), so a page's error says whose it is; "[WCModsMenu]" for the window's own.
local function log(fmt, ...)
    local G = package.loaded.WCModsGame
    local who = type(G) == "table" and type(G.modName) == "string" and G.modName ~= "" and G.modName
    print((who and ("[" .. who .. "] mod menu: ") or "[WCModsMenu] ") .. string.format(fmt, ...) .. "\n")
end

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

local AUTO, FILL = 0, 1                  -- ESlateSizeRule: Automatic, Fill
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

-- A page made again by its script: its line in the shared list says its title, order and group now.
local function relist(p)
    local out = {}
    for line in (Menu.shared("pages") or ""):gmatch("[^\n]+") do
        if line:match("^([^\t]*)\t") == p.id and ownerOf(line, p.id) == p.owner then
            line = p.id .. "\t" .. p.title .. "\t" .. tostring(p.order) .. "\t" .. p.group .. "\t" .. p.owner
        end
        out[#out + 1] = line .. "\n"
    end
    Menu.share("pages", table.concat(out))
end

-- The mod a page comes from: the folder under Mods/ its script runs from (UE4SS names a chunk by its
-- path), else the chunk's name; "" when Lua can't say. A script mod's own files are loaded by the script
-- bootstrap under their names in the mod ("@scripts/main.lua"), and the bootstrap says its folder (MOD.ue4ss).
local SLASH = string.char(92)
local function caller(level)
    local info = debug and debug.getinfo and debug.getinfo(level + 1, "S")
    local src = info and tostring(info.source or "") or ""
    src = src:gsub(SLASH, "/")
    local folder = src:match("/Mods/([^/]+)/")
    if folder then return folder end
    if src:match("^@scripts/") and type(MOD) == "table" and type(MOD.ue4ss) == "string" and MOD.ue4ss ~= "" then
        return MOD.ue4ss
    end
    -- A chunk loaded from a string has the string itself as its source: one line of it, no tabs (the
    -- page list is tab-separated lines), and not too long.
    return (src:gsub("[\t\r\n].*", ""):sub(1, 60))
end

-- The groups the menu's side bar shows, in order (menu.GROUPS in wcmods/menu.py, written in here): id and
-- label. A page names one of these ids (or a group of its own, which comes after "mods"); a group shows
-- once a page is in it.
Menu.groups = @GROUPS@

-- Add a page to the mod menu. fn(ui) runs every frame while it shows. opts.group puts it in a group of
-- the side bar ("mods" by default; Menu.groups lists them), opts.order sorts it within the group (lower
-- first), and opts.id tells pages with the same title apart (without it, the title; a second mod's page
-- with a title another mod has gets the title plus its mod's name, so the two don't share a tab). Gives
-- back the id as asked for: a page that shares its title with another mod's is best given opts.id, since
-- the renamed one isn't known until the next frame, and Menu.open(title) opens the first of them.
function Menu.page(title, fn, opts)
    opts = opts or {}
    local p = { id = opts.id or title, asked = opts.id or title, title = title, fn = fn, order = opts.order or 50,
                group = (tostring(opts.group or "mods"):gsub("[\t\n]", " ")), owner = caller(2) }
    -- The same page made again by the same script takes the first one's place (its tab, with the title, order
    -- and group it has now): a script's own page made later, from a timer, in the place of the one wcmods made
    -- for its settings ("script:<id>").
    for _, q in ipairs(pages) do
        if q.asked == p.asked and q.owner == p.owner then
            q.title, q.fn, q.order, q.group = p.title, p.fn, p.order, p.group
            ExecuteInGameThread(function() relist(q) end)
            return q.id
        end
    end
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

-- The line under the window's title, while the menu is open: one line of how things stand, e.g. your
-- cat's health and where it is. nil or "" puts back the menu's own line (how to open and close it). One
-- script's line at a time: the last one set shows. The player can hide it (Tools, Menu).
function Menu.status(text)
    Menu.share("status", (tostring(text or ""):gsub("[\r\n]+", " ")))
end

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

-- Whether a table is a list to write as [...] even when it's empty: one of Menu.list's, or WCModsGame's (what
-- Game.json.decode makes of a list in a file, as a script's settings.json is read when the game starts).
local function listy(v)
    local mt = getmetatable(v)
    if mt == nil then return false end
    if mt == LIST then return true end
    local G = package.loaded.WCModsGame
    return type(G) == "table" and type(G.json) == "table" and mt == G.json.listMeta
end

local function encode(v, indent)
    local t = type(v)
    if t == "nil" then return "null" end
    if t == "boolean" then return v and "true" or "false" end
    if t == "number" then
        if v ~= v or v == math.huge or v == -math.huge then return "null" end
        if math.type(v) == "integer" then return tostring(v) end
        -- The shortest form that reads back as the same number, so a Save never changes a value it didn't
        -- touch. %g writes 12.0 as "12", which comes back as a whole number (and a setting then only takes
        -- whole numbers); keep it a float.
        local s = string.format("%.15g", v)
        if tonumber(s) ~= v then s = string.format("%.17g", v) end
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
    if listy(v) and #v == 0 then return "[]" end
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
