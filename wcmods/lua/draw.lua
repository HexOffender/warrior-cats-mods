-- WCModsDraw: text and 2D shapes on screen, for custom menus, debug text and world markers.
-- Installed by wcmods; any UE4SS script can use it:
--
--   local Draw = require("WCModsDraw")
--   Draw.onFrame(function(d)
--       d.text(20, 20, "Hello", { size = 18 })
--       d.rect(10, 50, 200, 40, { color = "#00000080" })
--       d.marker(location, "Herbs", { sub = "Collect three", edge = true })
--       if d.button(20, 100, 140, 30, "Click me") then print("clicked\n") end
--   end)
--
-- Everything is in pixels from the viewport's top left, like WCModsView. Painters run every frame on
-- the game thread, and whatever a frame doesn't draw is hidden. Colours are "#rrggbb", "#rrggbbaa" or
-- {r, g, b, a} from 0 to 1, in sRGB like an image editor's. Every call is listed in docs/SDK.md.
--
-- It draws with the game's own UI system: one widget on the viewport (above the game's UI) holding a
-- canvas, with text blocks and images kept in pools. An element only gets a call into the game when
-- something about it changed. The overlay never takes clicks, so the game's UI and controls behave
-- as before; buttons notice clicks through the player's input instead.
local View = require("WCModsView")
local Draw = {}

local COLLAPSED, HIT_TEST_INVISIBLE = 1, 3               -- ESlateVisibility: Collapsed, HitTestInvisible
local J_LEFT, J_CENTER, J_RIGHT = 0, 1, 2                 -- ETextJustify: Left, Center, Right
local JUSTIFY = { left = J_LEFT, center = J_CENTER, right = J_RIGHT }
local ALIGN_X = { left = 0, center = 0.5, right = 1 }
local ALIGN_Y = { top = 0, middle = 0.5, bottom = 1 }

local function valid(o) return o ~= nil and o:IsValid() end
-- Lines go to UE4SS.log under the name of the mod whose script draws (WCModsGame's, set by the script bootstrap,
-- in this Lua state), so a painter's error says whose it is; "[WCModsDraw]" when there's none.
local function log(fmt, ...)
    local G = package.loaded.WCModsGame
    local who = type(G) == "table" and type(G.modName) == "string" and G.modName ~= "" and G.modName
    print((who and ("[" .. who .. "] drawing: ") or "[WCModsDraw] ") .. string.format(fmt, ...) .. "\n")
end

local reported, nreported = {}, 0
local function report(where, err)
    local key = where .. tostring(err)
    if reported[key] or nreported >= 20 then return end
    reported[key], nreported = true, nreported + 1
    log("error in %s: %s", where, tostring(err))
end

-- ---------- colours ----------
local function linear(c)
    if c <= 0.04045 then return c / 12.92 end
    return ((c + 0.055) / 1.055) ^ 2.4
end
local colours = {}
-- {R, G, B, A} in linear space, as the game's UI wants it, and a key to tell colours apart.
local function colour(c)
    local key = type(c) == "table" and table.concat({ c[1] or c.r or 0, c[2] or c.g or 0, c[3] or c.b or 0,
                                                       c[4] or c.a or 1 }, ",") or tostring(c)
    local hit = colours[key]
    if hit then return hit, key end
    local r, g, b, a
    if type(c) == "string" then
        local hex = c:gsub("^#", "")
        if #hex ~= 6 and #hex ~= 8 then error("colour should be #rrggbb or #rrggbbaa: " .. c) end
        r, g, b = tonumber(hex:sub(1, 2), 16), tonumber(hex:sub(3, 4), 16), tonumber(hex:sub(5, 6), 16)
        a = #hex == 8 and tonumber(hex:sub(7, 8), 16) or 255
        if not (r and g and b and a) then error("colour should be #rrggbb or #rrggbbaa: " .. c) end
        r, g, b, a = r / 255, g / 255, b / 255, a / 255
    elseif type(c) == "table" then
        r, g, b, a = c[1] or c.r or 0, c[2] or c.g or 0, c[3] or c.b or 0, c[4] or c.a or 1
    else
        error("colour should be \"#rrggbb\" or {r, g, b, a}")
    end
    hit = { R = linear(r), G = linear(g), B = linear(b), A = a }
    colours[key] = hit
    return hit, key
end

-- ---------- the overlay ----------
local NONE = FName("None")   -- lets the engine name each new object
local lib, pc, nextSearch = nil, nil, 0

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

local function setup()
    if lib then return true end
    local l = {
        userWidget = StaticFindObject("/Script/UMG.UserWidget"),
        commonWidget = StaticFindObject("/Script/CommonUI.CommonUserWidget"),
        tree = StaticFindObject("/Script/UMG.WidgetTree"),
        canvas = StaticFindObject("/Script/UMG.CanvasPanel"),
        text = StaticFindObject("/Script/UMG.TextBlock"),
        image = StaticFindObject("/Script/UMG.Image"),
        widgets = StaticFindObject("/Script/UMG.Default__WidgetBlueprintLibrary"),
        layout = StaticFindObject("/Script/UMG.Default__WidgetLayoutLibrary"),
    }
    for _, k in ipairs({ "userWidget", "tree", "canvas", "text", "image", "widgets", "layout" }) do
        if not valid(l[k]) then return false end
    end
    l.leftMouse = { KeyName = FName("LeftMouseButton") }
    lib = l
    return true
end

local zorder, shown = 1000, true
local overlay, retryAt = nil, 0     -- { widget, tree, canvas }
local pools = { text = {}, image = {} }

local function createOverlay(c)
    -- A plain UserWidget class is abstract, so the engine won't create one the usual way. CommonUI's
    -- is concrete when the game has it; otherwise the widget and its tree are made directly.
    local widget
    if valid(lib.commonWidget) then
        local ok, w = pcall(function() return lib.widgets:Create(c, lib.commonWidget, c) end)
        if ok and valid(w) then widget = w end
    end
    if not widget then widget = StaticConstructObject(lib.userWidget, c, NONE) end
    if not valid(widget) then error("couldn't create the overlay widget") end
    if not valid(widget.WidgetTree) then widget.WidgetTree = StaticConstructObject(lib.tree, widget, NONE) end
    local canvas = StaticConstructObject(lib.canvas, widget.WidgetTree, NONE)
    widget.WidgetTree.RootWidget = canvas
    widget:SetVisibility(HIT_TEST_INVISIBLE)
    widget:AddToViewport(zorder)
    return { widget = widget, tree = widget.WidgetTree, canvas = canvas }
end

-- Whether a kept object is still the one it was: a destroyed object's slot can be taken by another
-- object, which then looks valid but is of another class.
local function alive(o, cls)
    local ok, yes = pcall(function() return o:IsValid() and o:GetClass():GetFName():ToString() == cls end)
    return ok and yes
end

-- The overlay goes when the level changes (the game clears the viewport and a new player controller
-- comes), so it's made again then; the old one is never touched again.
local function ensureOverlay()
    local c = controller()
    if not c then return false end
    local owner = c:GetAddress()
    if overlay and overlay.owner == owner and alive(overlay.widget, overlay.cls) then return true end
    if not setup() or os.clock() < retryAt then return false end
    retryAt = os.clock() + 1
    if overlay and overlay.owner == owner and alive(overlay.widget, overlay.cls) then
        pcall(function() overlay.widget:RemoveFromParent() end)
    end
    overlay, pools = nil, { text = {}, image = {} }
    local ok, made = pcall(createOverlay, c)
    if not ok then
        report("creating the overlay", made)
        return false
    end
    overlay = made
    overlay.owner, overlay.cls = owner, made.widget:GetClass():GetFName():ToString()
    overlay.widget:SetVisibility(shown and HIT_TEST_INVISIBLE or COLLAPSED)
    return true
end

-- ---------- elements ----------
local frame = { used = { text = 0, image = 0 }, order = 0, scale = 1 }

local function put(e, key, value, apply)
    if e.last[key] ~= value then
        e.last[key] = value
        apply(value)
    end
end

local function round(v) return math.floor(v * 10 + 0.5) / 10 end

local function element(kind)
    local n = frame.used[kind] + 1
    frame.used[kind] = n
    local e = pools[kind][n]
    if not e then
        local w = StaticConstructObject(lib[kind], overlay.tree, NONE)
        local slot = overlay.canvas:AddChildToCanvas(w)
        e = { w = w, slot = slot, last = {} }
        if kind == "text" then
            slot:SetAutoSize(true)
            local f = w.Font
            e.font = { object = f.FontObject, typeface = f.TypefaceFontName, size = f.Size > 0 and f.Size or 24 }
        else
            slot:SetAutoSize(false)
        end
        pools[kind][n] = e
    end
    frame.order = frame.order + 1
    put(e, "z", frame.order, function(v) e.slot:SetZOrder(v) end)
    put(e, "vis", HIT_TEST_INVISIBLE, function(v) e.w:SetVisibility(v) end)
    return e
end

local function place(e, x, y, ax, ay)
    local s = frame.scale
    local px, py = round(x / s), round(y / s)
    put(e, "pos", px .. "," .. py, function() e.slot:SetPosition({ X = px, Y = py }) end)
    put(e, "align", ax .. "," .. ay, function() e.slot:SetAlignment({ X = ax, Y = ay }) end)
end

local function size(e, w, h)
    local s = frame.scale
    local sw, sh = round(math.max(0, w) / s), round(math.max(0, h) / s)
    put(e, "size", sw .. "," .. sh, function() e.slot:SetSize({ X = sw, Y = sh }) end)
end

local textures = {}
local function texture(t)
    if type(t) ~= "string" then return t end
    local hit = textures[t]
    if valid(hit) then return hit end
    hit = StaticFindObject(t)
    if not valid(hit) and LoadAsset then pcall(function() hit = LoadAsset(t) end) end
    if not valid(hit) then error("no texture at " .. t) end
    textures[t] = hit
    return hit
end

-- One image: a rectangle w by h at x, y, turned `angle` degrees around (pivotX, pivotY) of itself.
local function image(x, y, w, h, opts, angle, pivotX, pivotY)
    local e = element("image")
    place(e, x, y, 0, 0)
    size(e, w, h)
    local lin, key = colour(opts.color or "#ffffff")
    put(e, "color", key, function() e.w:SetColorAndOpacity(lin) end)
    local tex = opts.texture and texture(opts.texture) or nil
    put(e, "texture", tex and tex:GetFullName() or "", function()
        if tex then
            e.w:SetBrushFromTexture(tex, false)
        elseif not pcall(function() e.w:SetBrushResourceObject(nil) end) then
            e.w:SetBrushResourceObject(CreateInvalidObject())
        end
    end)
    put(e, "pivot", pivotX .. "," .. pivotY, function() e.w:SetRenderTransformPivot({ X = pivotX, Y = pivotY }) end)
    put(e, "angle", round(angle), function(v) e.w:SetRenderTransformAngle(v) end)
end

-- ---------- what painters get ----------
local d = {}

function d.measure(text, px)
    -- A guess from the font size; the game's font is a little narrower than half an em on average.
    px = px or 16
    local lines, widest = 0, 0
    for line in (tostring(text) .. "\n"):gmatch("(.-)\n") do
        lines = lines + 1
        widest = math.max(widest, #line)
    end
    return widest * px * 0.52, lines * px * 1.25
end

function d.text(x, y, text, opts)
    opts = opts or {}
    local e = element("text")
    local px = opts.size or 16
    place(e, x, y, ALIGN_X[opts.align or "left"] or 0, ALIGN_Y[opts.valign or "top"] or 0)
    text = tostring(text)
    put(e, "text", text, function(v) e.w:SetText(FText(v)) end)
    put(e, "font", round(px / frame.scale), function()
        -- Font sizes are points at 96 DPI: 0.75 pt per pixel, before the UI's own scaling.
        local pt = px * 0.75 / frame.scale
        local ok, err = pcall(function()
            e.w:SetFont({ FontObject = e.font.object, TypefaceFontName = e.font.typeface, Size = pt,
                          LetterSpacing = 0, SkewAmount = 0, bForceMonospaced = false, MonospacedWidth = 1 })
        end)
        if not ok then   -- scale the text block's own font instead
            report("setting a font size", err)
            local s = pt / e.font.size
            e.w:SetRenderScale({ X = s, Y = s })
        end
    end)
    local lin, key = colour(opts.color or "#ffffff")
    put(e, "color", key, function() e.w:SetColorAndOpacity({ SpecifiedColor = lin, ColorUseRule = 0 }) end)
    put(e, "justify", opts.align or "left", function(v) e.w:SetJustification(JUSTIFY[v] or J_LEFT) end)
    local shadow = opts.shadow ~= false
    put(e, "shadow", shadow, function(v)
        e.w:SetShadowOffset(v and { X = 1, Y = 1 } or { X = 0, Y = 0 })
        e.w:SetShadowColorAndOpacity({ R = 0, G = 0, B = 0, A = v and 0.8 or 0 })
    end)
end

function d.rect(x, y, w, h, opts)
    opts = opts or {}
    local t = opts.outline
    if t and t > 0 then
        image(x, y, w, t, opts, 0, 0, 0)
        image(x, y + h - t, w, t, opts, 0, 0, 0)
        image(x, y + t, t, h - 2 * t, opts, 0, 0, 0)
        image(x + w - t, y + t, t, h - 2 * t, opts, 0, 0, 0)
    else
        image(x, y, w, h, opts, opts.angle or 0, 0.5, 0.5)
    end
end

function d.line(x1, y1, x2, y2, opts)
    opts = opts or {}
    local t = opts.thickness or 2
    local dx, dy = x2 - x1, y2 - y1
    local length = math.sqrt(dx * dx + dy * dy)
    if length < 0.01 then return end
    -- An image as long as the line, turned around the middle of its left edge, which sits at x1, y1.
    image(x1, y1 - t / 2, length, t, opts, math.deg(math.atan(dy, dx)), 0, 0.5)
end

function d.polyline(points, opts)
    opts = opts or {}
    for i = 1, #points - 1 do
        d.line(points[i][1], points[i][2], points[i + 1][1], points[i + 1][2], opts)
    end
    if opts.closed and #points > 2 then
        d.line(points[#points][1], points[#points][2], points[1][1], points[1][2], opts)
    end
end

function d.circle(x, y, radius, opts)
    opts = opts or {}
    local n = opts.segments or math.max(12, math.min(64, math.floor(radius / 3)))
    local points = {}
    for i = 0, n - 1 do
        local a = 2 * math.pi * i / n
        points[#points + 1] = { x + radius * math.cos(a), y + radius * math.sin(a) }
    end
    d.polyline(points, { color = opts.color, thickness = opts.thickness or 2, closed = true })
end

function d.mouse()
    return frame.mouseX, frame.mouseY, frame.cursor
end

function d.hover(x, y, w, h)
    local mx, my = frame.mouseX, frame.mouseY
    return frame.cursor and mx ~= nil and mx >= x and mx < x + w and my >= y and my < y + h
end

function d.clicked()
    return frame.clicked
end

function d.panel(x, y, w, h, title, opts)
    opts = opts or {}
    d.rect(x, y, w, h, { color = opts.color or "#14181ee0" })
    d.rect(x, y, w, h, { color = opts.border or "#ffffff40", outline = 1 })
    if title then
        d.rect(x + 1, y + 1, w - 2, 26, { color = opts.titleColor or "#ffffff18" })
        d.text(x + 10, y + 14, title, { size = 15, valign = "middle", color = opts.textColor or "#ffffff" })
        return y + 34   -- where the panel's content starts
    end
    return y + 8
end

function d.button(x, y, w, h, label, opts)
    opts = opts or {}
    local over = d.hover(x, y, w, h)
    d.rect(x, y, w, h, { color = over and (opts.hoverColor or "#3d4a5cf0") or (opts.color or "#252b34e8") })
    d.rect(x, y, w, h, { color = opts.border or "#ffffff50", outline = 1 })
    d.text(x + w / 2, y + h / 2, label, { size = opts.size or 15, align = "center", valign = "middle",
                                          color = opts.textColor or "#ffffff" })
    return over and frame.clicked
end

-- A marker on a place in the world: a diamond, its label above and how far it is below. With
-- opts.edge, one off screen or behind the camera sits on the screen's edge, pointing the way.
-- Returns the screen position it was drawn at, or nil when it wasn't drawn.
function d.marker(location, label, opts)
    opts = opts or {}
    local view = frame.view
    if not view then return nil end
    local from = opts.from or frame.player or view.location
    local dx, dy, dz = location.X - from.X, location.Y - from.Y, location.Z - from.Z
    local distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    if opts.maxDistance and distance > opts.maxDistance then return nil end
    local r = view.rect
    local margin = opts.margin or 40
    local x, y = View.worldToScreen(location, view)
    local inside = x and x >= r.x + margin and x <= r.x + r.width - margin and y >= r.y + margin
                   and y <= r.y + r.height - margin
    local edge = false
    if not inside then
        if not opts.edge then return nil end
        -- Point from the middle of the screen toward it, by where it is from the camera (right and up),
        -- which stays the right way round for places behind it too. Straight behind goes to the bottom.
        local right, up = View.cameraSpace(location, view)
        local cx, cy = r.x + r.width / 2, r.y + r.height / 2
        local vx, vy = right, -up
        if math.abs(vx) < 0.001 and math.abs(vy) < 0.001 then vy = 1 end
        local sx = (r.width / 2 - margin) / math.max(math.abs(vx), 0.001)
        local sy = (r.height / 2 - margin) / math.max(math.abs(vy), 0.001)
        local s = math.min(sx, sy)
        x, y, edge = cx + vx * s, cy + vy * s, true
    end
    local colour_ = opts.color or "#ffd166"
    local size_ = opts.size or 12
    d.rect(x - size_ / 2, y - size_ / 2, size_, size_, { color = "#000000a0", angle = 45 })
    d.rect(x - size_ / 2 + 2, y - size_ / 2 + 2, size_ - 4, size_ - 4, { color = colour_, angle = 45 })
    if label then
        d.text(x, y - size_, label, { size = opts.textSize or 15, align = "center", valign = "bottom", color = colour_ })
    end
    local below = opts.sub
    if opts.distance ~= false then
        local m = string.format("%d m", math.floor(distance / 100 + 0.5))
        below = below and (below .. "  " .. m) or m
    end
    if below then
        d.text(x, y + size_, below, { size = opts.subSize or 13, align = "center", valign = "top", color = "#ffffffd0" })
    end
    return x, y, edge
end

-- ---------- running painters ----------
local painters, nextId = {}, 0
local function paint()
    if not ensureOverlay() then return end
    local c = pc
    frame.used.text, frame.used.image, frame.order = 0, 0, 0
    frame.scale = lib.layout:GetViewportScale(c)
    if not (frame.scale and frame.scale > 0) then frame.scale = 1 end
    frame.view = View.current()
    frame.cursor = c.bShowMouseCursor
    local m = lib.layout:GetMousePositionOnViewport(c)
    frame.mouseX, frame.mouseY = m.X * frame.scale, m.Y * frame.scale
    frame.clicked = frame.cursor and c:WasInputKeyJustPressed(lib.leftMouse)
    frame.player = nil
    if valid(c.Pawn) then
        local l = c.Pawn:K2_GetActorLocation()
        frame.player = { X = l.X, Y = l.Y, Z = l.Z }
    end
    d.width, d.height, d.scale, d.view, d.player = 0, 0, frame.scale, frame.view, frame.player
    if frame.view then d.width, d.height = frame.view.width, frame.view.height end
    if shown then
        for _, p in ipairs(painters) do
            local ok, err = pcall(p.fn, d)
            if not ok then report("painter " .. p.id, err) end
        end
    end
    -- Hide what this frame didn't draw.
    for kind, pool in pairs(pools) do
        for i = frame.used[kind] + 1, #pool do
            local e = pool[i]
            put(e, "vis", COLLAPSED, function(v) e.w:SetVisibility(v) end)
        end
    end
end

local function tick()
    local ok, err = pcall(paint)
    if not ok then report("frame", err) end
end

local looping = false
local function start()
    if looping then return end
    looping = true
    if LoopInGameThreadAfterFrames == nil or not pcall(LoopInGameThreadAfterFrames, 1, tick) then
        LoopAsync(16, function()
            ExecuteInGameThread(tick)
            return false
        end)
    end
end

-- Draw with fn(d) every frame. Returns an id for Draw.remove.
function Draw.onFrame(fn)
    nextId = nextId + 1
    painters[#painters + 1] = { id = nextId, fn = fn }
    start()
    return nextId
end

function Draw.remove(id)
    for i, p in ipairs(painters) do
        if p.id == id then
            table.remove(painters, i)
            return true
        end
    end
    return false
end

-- Show or hide everything this script draws (e.g. on a key press).
function Draw.setVisible(on)
    shown = on and true or false
    if overlay and valid(overlay.widget) then overlay.widget:SetVisibility(shown and HIT_TEST_INVISIBLE or COLLAPSED) end
end

function Draw.isVisible() return shown end

-- Where the overlay sits among the game's UI (higher is on top); 1000 by default, above the game's.
function Draw.setZOrder(z)
    zorder = z
    if overlay and valid(overlay.widget) then
        overlay.widget:RemoveFromParent()
        overlay = nil
        retryAt = 0
    end
end

return Draw
