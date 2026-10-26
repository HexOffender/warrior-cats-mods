-- The in-game mod menu: the window, its tabs, and the first pages. Written by wcmods on every install;
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

