-- The in-game mod menu: the window, its tabs, and its own pages (the Overview, the installed mods and the
-- Tools). Written by wcmods on every install with UE4SS; change its key in Clan Mod Studio (Settings and
-- repair, Options) and install again rather than editing this.
--
-- @KEY@ opens and closes it, and Escape closes it; so does a controller's button (SETTINGS.pad), with B
-- closing it too. While it's open the game's controls are paused (the UI takes the keyboard and mouse,
-- or the game itself pauses when the controller opened it) and the cursor shows; closing gives them
-- back. Pages come from any UE4SS script through WCModsMenu.page (docs/SDK.md, "WCModsMenu"), the pages
-- about the game from the Menu pages mod; the window shares its content panel with them and they build
-- their rows into it.
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

local VISIBLE, COLLAPSED = 0, 1   -- ESlateVisibility: Visible, Collapsed
local FILL = 1                    -- ESlateSizeRule::Fill
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

    -- Under the header: how your cat is doing (a script's Menu.status, the Menu pages mod's), or how to use
    -- the menu.
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

-- What the status line under the header says: a script's Menu.status (the Menu pages mod's: how your cat
-- is doing), or how to use the menu. The Menu page can hide a script's line (HOST.statusOn).
local HOST = { statusOn = true }
local statusAt, statusShown = -1, nil
local USAGE = SETTINGS.opens .. " opens and closes this menu. Changes apply at once; a page's Save keeps them."

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
    if os.clock() - statusAt >= 0.25 then
        statusAt = os.clock()
        local line = HOST.statusOn and Menu.shared("status") or nil
        if type(line) ~= "string" or line == "" then line = USAGE end
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

-- The window's own pages are in menu_host_pages.lua, pasted in here by menu.host_script:
@PAGES@
-- The menu's key, for scripts that point at the menu ("<name> didn't start: ... The mod menu (Insert), Tools, Log
-- says more", the script bootstrap's).
Menu.share("key_name", SETTINGS.key_name)
log("ready: %s opens the mod menu", SETTINGS.key_name)
syncCpp()

