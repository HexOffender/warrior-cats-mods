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
local THEME = {
    text = "#e8ecf2", muted = "#9aa6b5", heading = "#ffd98a", accent = "#5b8def", danger = "#d65a5a",
    good = "#4caf6e", off = "#4a5260", line = "#ffffff26",
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

-- A click: the button went from pressed to released with the mouse still on it.
local function clicked(state, key, b)
    local pressed = b:IsPressed()
    local was = state[key]
    state[key] = pressed
    return was and not pressed and b:IsHovered()
end

local function put(e, key, value, apply)
    if e.last[key] ~= value then
        e.last[key] = value
        apply(value)
    end
end

local function near(a, b) return math.abs((a or 0) - (b or 0)) < 1e-6 end

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

local function labelled(label, control, controlFill, extra, halign)
    local box = new("HorizontalBox")
    local l = text(label, 13)
    add(box, l, 0.42, 0, 12)
    add(box, control, controlFill or 0.58, 0, 0, nil, halign)
    if extra then add(box, extra, nil, 8) end
    return box, l
end

local ui = {}

function ui.heading(str)
    local e = row("heading", function()
        local t = text(str, 18, THEME.heading)
        return { root = t, t = t, top = 8, bottom = 4 }
    end)
    put(e, "text", str, function(v) setText(e.t, v) end)
end

function ui.text(str, opts)
    opts = opts or {}
    local e = row("text", function()
        local t = text(str, opts.size or 13, opts.color or THEME.text, true)
        return { root = t, t = t }
    end)
    put(e, "text", tostring(str), function(v) setText(e.t, v) end)
    put(e, "color", opts.color or THEME.text, function(v) e.t:SetColorAndOpacity({ SpecifiedColor = C(v), ColorUseRule = 0 }) end)
end

function ui.note(str)
    ui.text(str, { size = 11.5, color = THEME.muted })
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
end

local KIND_COLOURS = { primary = THEME.accent, danger = THEME.danger, good = THEME.good }
-- A button; true the frame it's clicked. opts.kind: "primary", "danger", "good" or nil.
function ui.button(label, opts)
    opts = opts or {}
    local e = row("button", function()
        local box = new("HorizontalBox")
        local b = Menu.button(label)
        add(box, b)
        return { root = box, b = b }
    end)
    put(e, "label", label, function(v) e.b:SetContent(text(v, 12.5)) end)
    put(e, "color", opts.kind or "", function(v) e.b:SetBackgroundColor(C(KIND_COLOURS[v] or "#3a4250")) end)
    return clicked(e.state, "b", e.b)
end

-- A row of buttons; the index of the one clicked this frame, or nil.
function ui.buttons(labels, opts)
    opts = opts or {}
    local e = row("buttons" .. #labels, function()
        local box = new("HorizontalBox")
        local bs = {}
        for i, l in ipairs(labels) do
            bs[i] = Menu.button(l)
            add(box, bs[i], nil, 0, 6)
        end
        return { root = box, bs = bs }
    end)
    local hit
    for i, b in ipairs(e.bs) do
        put(e, "label" .. i, labels[i], function(v) b:SetContent(text(v, 12.5)) end)
        local kind = opts.kinds and opts.kinds[i] or ""
        put(e, "color" .. i, kind, function(v) b:SetBackgroundColor(C(KIND_COLOURS[v] or "#3a4250")) end)
        if clicked(e.state, i, b) then hit = i end
    end
    return hit
end

-- A check box with its label; returns whether it's ticked. opts.swatch: a colour shown by the label.
function ui.toggle(label, value, opts)
    opts = opts or {}
    local e = row(opts.swatch and "toggle+swatch" or "toggle", function()
        local box = new("HorizontalBox")
        local c = new("CheckBox")
        local l = text(label, 13)
        add(box, c, nil, 0, 10)
        local sw
        if opts.swatch then
            sw = new("Image")
            add(box, Menu.sized(sw, 16, 16), nil, 0, 10)
        end
        add(box, l, 1)
        return { root = box, c = c, l = l, sw = sw }
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
    return e.v
end

-- An on/off switch: a button that shows On or Off; returns the new state.
function ui.switch(label, value)
    local e = row("switch", function()
        local b = Menu.button("Off")
        local box, l = labelled(label, Menu.sized(b, 80), nil, nil, H_LEFT)
        return { root = box, b = b, l = l }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    local on = value and true or false
    if clicked(e.state, "b", e.b) then on = not on end
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
        local bs = {}
        for i, o in ipairs(options) do
            bs[i] = Menu.button(tostring(o), nil, 12)
            add(inner, bs[i], nil, 0, 4)
        end
        local box, l = labelled(label, inner)
        return { root = box, bs = bs, l = l }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    local chosen = value
    for i, b in ipairs(e.bs) do
        put(e, "opt" .. i, tostring(options[i]), function(v) b:SetContent(text(v, 12)) end)
        if clicked(e.state, i, b) then chosen = options[i] end
    end
    for i, b in ipairs(e.bs) do
        put(e, "sel" .. i, options[i] == chosen, function(v) b:SetBackgroundColor(C(v and THEME.accent or "#3a4250")) end)
    end
    return chosen
end

-- A drop-down list; returns the chosen option.
function ui.choice(label, value, options)
    local e = row("choice", function()
        local c = new("ComboBox")
        local box, l = labelled(label, c)
        return { root = box, c = c, l = l }
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
        local box, l = labelled(label, s, nil, Menu.sized(v, 84))
        return { root = box, s = s, l = l, vt = v }
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
    put(e, "shown", string.format(opts.format or "%.2f", e.v), function(s) setText(e.vt, s) end)
    return e.v
end

-- A number box (drag it or type); returns its value. opts: min, max, step.
function ui.number(label, value, opts)
    opts = opts or {}
    local e = row("number", function()
        local s = new("SpinBox")
        local box, l = labelled(label, s)
        return { root = box, s = s, l = l }
    end)
    put(e, "label", label, function(v) setText(e.l, v) end)
    put(e, "range", tostring(opts.min) .. "," .. tostring(opts.max) .. "," .. tostring(opts.step), function()
        if opts.min then e.s:SetMinValue(opts.min) e.s:SetMinSliderValue(opts.min) end
        if opts.max then e.s:SetMaxValue(opts.max) e.s:SetMaxSliderValue(opts.max) end
        if opts.step then e.s:SetDelta(opts.step) end
        e.v = nil
    end)
    local now = e.s:GetValue()
    if e.v ~= nil and not near(now, e.v) then
        e.v = now
    elseif e.v == nil or not near(e.v, value) then
        e.v = value
        e.s:SetValue(value)
    end
    return e.v
end

-- A text box; returns its text. opts.hint shows when it's empty.
function ui.input(label, value, opts)
    opts = opts or {}
    local e = row("input", function()
        local t = new("EditableTextBox")
        local box, l = labelled(label, t)
        return { root = box, t = t, l = l }
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
        local box, l = labelled(label, inner, 0.58)
        return { root = box, sw = sw, ss = ss, vt = v, l = l }
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
        return { root = b, b = b, top = 6 }
    end)
    if clicked(e.state, "b", e.b) then open_sections[key] = not open_sections[key] end
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
    local ok, err = pcall(page.fn, ui)
    if not ok then
        report("page " .. page.title, err)
        ui.text("This page hit an error: " .. tostring(err), { color = THEME.danger })
    end
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

local function register(p)
    local list = Menu.shared("pages") or ""
    local line = p.id .. "\t" .. p.title .. "\t" .. tostring(p.order) .. "\n"
    if not list:find(p.id .. "\t", 1, true) then Menu.share("pages", list .. line) end
end

-- Add a page to the mod menu. fn(ui) runs every frame while it shows. opts.order sorts the tabs
-- (lower first; the host's own pages are 0-9), opts.id tells pages with the same title apart.
function Menu.page(title, fn, opts)
    opts = opts or {}
    local p = { id = opts.id or title, title = title, fn = fn, order = opts.order or 50 }
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
        return string.format("%.6g", v)
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
        local f = assert(io.open(path, "w"))
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
-- @KEY@ opens and closes it, and Escape closes it. While it's open the game's controls are paused (the
-- UI takes the keyboard and mouse) and the cursor shows; closing gives them back. Pages come from any
-- UE4SS script through WCModsMenu.page (docs/SDK.md, "Mod menu"); the window shares its content panel
-- with them and they build their rows into it.
local Menu = require("WCModsMenu")
local SETTINGS = @SETTINGS@

local function valid(o) return o ~= nil and o:IsValid() end
local function log(fmt, ...) print(string.format("[WCModsMenu] " .. fmt .. "\n", ...)) end
local C, THEME, new, add, text = Menu.color, Menu.theme, Menu.new, Menu.add, Menu.text

local VISIBLE, COLLAPSED = 0, 1   -- ESlateVisibility
local FILL = 1
local USER_SPECIFIED = 7          -- EStretch::UserSpecified: scale by SetUserSpecifiedScale

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
    add(header, text("Mods", 20, THEME.heading), 1)
    local smaller = Menu.button("A-", nil, 12)
    add(header, smaller, nil, 0, 4)
    local bigger = Menu.button("A+", nil, 12)
    add(header, bigger, nil, 0, 18)
    local pause = make("CheckBox")
    add(header, pause, nil, 0, 6)
    add(header, text("Pause the game", 12, THEME.muted), nil, 0, 18)
    local close = Menu.button("Close", nil, 13)
    add(header, close)
    column:AddChildToVerticalBox(header)

    local hint = text(SETTINGS.key_name .. " opens and closes this menu. Changes apply at once; a page's Save keeps them. " ..
                      "A- and A+ change the menu's size.", 11.5, THEME.muted, true)
    local hs = column:AddChildToVerticalBox(hint)
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
    return { widget = widget, tree = tree, tabs = tabs, content = content, close = close, pause = pause,
             scaler = scaler, sizer = sizer, smaller = smaller, bigger = bigger,
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
    return true
end

-- ---------- tabs ----------
local function pageList()
    local out = {}
    for line in (Menu.shared("pages") or ""):gmatch("([^\n]+)") do
        local id, title, order = line:match("^(.-)\t(.-)\t(.-)$")
        if id then out[#out + 1] = { id = id, title = title, order = tonumber(order) or 50 } end
    end
    table.sort(out, function(a, b)
        if a.order ~= b.order then return a.order < b.order end
        return a.title < b.title
    end)
    return out
end

local generation = 0
local function show(id)
    Menu.share("page", id)
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
        for _, p in ipairs(list) do
            local b = Menu.button(p.title, nil, 13)
            local slot = win.tabs:AddChild(b)
            slot:SetPadding({ Left = 0, Top = 0, Right = 0, Bottom = 4 })
            win.tabButtons[#win.tabButtons + 1] = { id = p.id, b = b }
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
        local pressed = t.b:IsPressed()
        if t.was and not pressed and t.b:IsHovered() and t.id ~= current then
            current = t.id
            show(current)
        end
        t.was = pressed
        local sel = t.id == current
        if t.sel ~= sel then
            t.sel = sel
            t.b:SetBackgroundColor(C(sel and THEME.accent or "#2a313c"))
        end
    end
end

-- ---------- opening and closing ----------
local isOpen, before, paused = false, nil, false

local function setPaused(on)
    local c = controller()
    if c and Menu.classes() then pcall(function() Menu.classes().statics:SetGamePaused(c, on) end) end
    paused = on
end

local function openMenu()
    if isOpen or not ensureWindow() then return end
    local c, lib = controller(), Menu.classes()
    before = { cursor = c.bShowMouseCursor }
    win.widget:SetVisibility(VISIBLE)
    fit()
    c.bShowMouseCursor = true
    pcall(function() win.widget:SetIsFocusable(true) end)
    pcall(function() lib.widgets:SetInputMode_UIOnlyEx(c, win.widget, 0, false) end)
    isOpen = true
    Menu.share("open", true)
    show(Menu.shared("page") or "")
    if win.pause:IsChecked() then setPaused(true) end
end

local function closeMenu()
    if not isOpen then return end
    isOpen = false
    Menu.share("open", false)
    if paused then setPaused(false) end
    if windowOk() then
        win.widget:SetVisibility(COLLAPSED)
        pcall(function() win.content:ClearChildren() end)
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

local function tick()
    if not isOpen then return end
    if not windowOk() then
        -- The level changed under the open menu: the game cleared the viewport.
        isOpen = false
        Menu.share("open", false)
        return
    end
    updateTabs()
    for _, key in ipairs({ "smaller", "bigger" }) do
        local b = win[key]
        local down = b:IsPressed()
        if win.state[key] and not down and b:IsHovered() then
            size = math.max(0.6, math.min(2.2, size * (key == "bigger" and 1.12 or 1 / 1.12)))
            fit()
        end
        win.state[key] = down
    end
    local pressed = win.close:IsPressed()
    if win.state.close and not pressed and win.close:IsHovered() then closeMenu() end
    win.state.close = pressed
    if isOpen and win.pause:IsChecked() ~= paused then setPaused(win.pause:IsChecked()) end
end

-- Work that needs doing once a second (cheats on a new level's cat). It runs here, on the game thread
-- with everything else: a LoopAsync would run it on another thread in this same Lua state, and two
-- threads in one Lua state at once crash the game.
local everySecond, nextSecond = {}, 0

local function frame()
    local ok, err = pcall(tick)
    if not ok then log("error: %s", tostring(err)) end
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
end, { order = 0 })

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
    end, { order = 5 })
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
    cheats.command = ui.input("Console command", cheats.command, { hint = "e.g. stat fps" })
    local hit = ui.buttons({ "Run", "stat fps", "stat unit" })
    if hit == 1 and cheats.command ~= "" then console(c, cheats.command)
    elseif hit == 2 then console(c, "stat fps")
    elseif hit == 3 then console(c, "stat unit") end

    ui.separator()
    ui.note("The game also has its own developer cheats (rank up, currency, complete the current quest, " ..
            "teleport to camp ...) in its cheats manager; they aren't wired up here yet.")
end, { order = 8 })

log("ready: %s opens the mod menu", SETTINGS.key_name)
'''

KEY_NAMES = {"INS": "Insert", "HOME": "Home", "END": "End", "DEL": "Delete", "PAGE_UP": "Page Up",
             "PAGE_DOWN": "Page Down"}


def lua():
    return LUA


def host_script(manifest, mods, key=DEFAULT_KEY, cheats=False, scale=1.0):
    """The host's script, with the overview of this build: the enabled mods and what each section set.
    cheats: whether the Cheats page starts with cheats on (wcmods.json "cheats"); scale: the menu's size,
    1 for the usual (wcmods.json "menu_scale")."""
    if key not in KEYS:
        raise ValueError(f"menu_key should be one of {', '.join(KEYS)}")
    enabled = [m for m in mods if m.enabled]
    sections = []
    for sid, rep in manifest["sections"].items():
        if not rep.get("mods"):
            continue
        sections.append({"id": sid, "title": rep["title"], "status": rep["status"], "errors": rep.get("errors", []),
                         "mods": rep["mods"], "notes": manifest["notes"].get(sid)})
    settings = {
        "key": key, "key_name": KEY_NAMES.get(key, key), "built": manifest["built"].replace("T", " "),
        "cheats": bool(cheats), "scale": float(scale),
        "mods": [{"id": m.id, "name": m.name, "description": m.description, "kinds": m.kinds(),
                  "priority": m.priority} for m in enabled],
        "sections": sections, "warnings": manifest["warnings"],
    }
    return HOST_LUA.replace("@SETTINGS@", lua_value(settings)).replace("@KEY@", KEY_NAMES.get(key, key))
