"""WCModsView: a shared UE4SS Lua module with what the player's camera sees, for overlays.

Installed as ue4ss/Mods/shared/WCModsView/WCModsView.lua whenever wcmods installs into UE4SS, so any
UE4SS script (wcmods' own, a mod's section.py, or one written by hand) can `require("WCModsView")` and
turn world positions into screen positions. See docs/SDK.md, "Overlays".
"""

SHARED_NAME = "WCModsView"
NEAR_PLANE = 10.0   # Unreal's near clipping plane (r.SetNearClipPlane), in centimetres

LUA = r'''-- WCModsView: what the player's camera sees, for overlays. Installed by wcmods; any UE4SS script can use it:
--
--   local View = require("WCModsView")
--   local view = View.current()                        -- nil until there's a camera and a viewport
--   local x, y, depth = View.worldToScreen(location, view)  -- pixels from the top left; nil behind the camera
--
-- view.location {X, Y, Z} and view.rotation {Pitch, Yaw, Roll} are the camera's; view.fov is its horizontal
-- field of view in degrees; view.width and view.height are the viewport in pixels; view.rect is the part
-- the picture fills ({x, y, width, height}; smaller than the viewport only when the camera keeps its own
-- aspect ratio). view.viewMatrix, view.projectionMatrix and view.viewProjection are Unreal's matrices
-- (4 rows of 4, for row vectors: clip = {X, Y, Z, 1} * viewProjection), as the renderer builds them.
--
-- Everything comes from the camera manager's last view, which is the picture on screen now. Get a view
-- once per update and pass it to worldToScreen for every point; worldToScreen gets one itself if not.
-- View.cameraSpace(location, view) gives right, up and forward in centimetres, for points off screen.
-- View.engineWorldToScreen(location) asks the engine (GameplayStatics.ProjectWorldToScreen) instead,
-- which is slower but handy to check against.
local View = {}

local NEAR_PLANE = @NEAR_PLANE@

local function valid(o) return o ~= nil and o:IsValid() end

local pc, nextSearch = nil, 0
local function controller()
    -- A destroyed controller's slot can be taken by another object, so even reading it is guarded.
    local ok, still = pcall(function() return valid(pc) and valid(pc.Player) end)
    if ok and still then return pc end
    pc = nil
    if os.clock() < nextSearch then return nil end
    nextSearch = os.clock() + 0.5   -- FindAllOf is slow: look again at most twice a second
    for _, c in ipairs(FindAllOf("PlayerController") or {}) do
        if valid(c) and valid(c.Player) then
            pc = c
            break
        end
    end
    return pc
end

local layout, statics
local function libs()
    if not valid(layout) then layout = StaticFindObject("/Script/UMG.Default__WidgetLayoutLibrary") end
    if not valid(statics) then statics = StaticFindObject("/Script/Engine.Default__GameplayStatics") end
    return valid(layout) and valid(statics)
end

-- Unreal's rotation matrix rows: the camera's forward (X), right (Y) and up (Z) directions.
local function axes(r)
    local p, y, ro = math.rad(r.Pitch), math.rad(r.Yaw), math.rad(r.Roll)
    local sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(ro), math.cos(ro)
    return { cp * cy, cp * sy, sp },
           { sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp },
           { -(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp }
end

local function dot(a, b) return a[1] * b[1] + a[2] * b[2] + a[3] * b[3] end

local function multiply(a, b)
    local out = {}
    for i = 1, 4 do
        out[i] = {}
        for j = 1, 4 do
            out[i][j] = a[i][1] * b[1][j] + a[i][2] * b[2][j] + a[i][3] * b[3][j] + a[i][4] * b[4][j]
        end
    end
    return out
end

function View.current()
    local c = controller()
    if not c or not libs() then return nil end
    local ok, view = pcall(function()
        local pov = c.PlayerCameraManager.CameraCachePrivate.POV
        local size = layout:GetViewportSize(c)
        local width, height = size.X, size.Y
        if not (width > 0 and height > 0) then return nil end
        local loc = { X = pov.Location.X, Y = pov.Location.Y, Z = pov.Location.Z }
        local rot = { Pitch = pov.Rotation.Pitch, Yaw = pov.Rotation.Yaw, Roll = pov.Rotation.Roll }
        -- A camera that keeps its own aspect ratio is letterboxed or pillarboxed in the middle.
        local rect = { x = 0, y = 0, width = width, height = height }
        if pov.bConstrainAspectRatio and pov.AspectRatio > 0 then
            if width / height > pov.AspectRatio then
                rect.width = height * pov.AspectRatio
                rect.x = (width - rect.width) / 2
            else
                rect.height = width / pov.AspectRatio
                rect.y = (height - rect.height) / 2
            end
        end
        local forward, right, up = axes(rot)
        local l = { loc.X, loc.Y, loc.Z }
        -- Unreal's view space: X right, Y up, Z forward (the distance in front of the camera).
        local viewMatrix = {
            { right[1], up[1], forward[1], 0 },
            { right[2], up[2], forward[2], 0 },
            { right[3], up[3], forward[3], 0 },
            { -dot(l, right), -dot(l, up), -dot(l, forward), 1 },
        }
        -- Reversed-Z perspective with the horizontal field of view kept, as the renderer does.
        local t = math.tan(math.rad(math.max(0.001, pov.FOV)) / 2)
        local projectionMatrix = {
            { 1 / t, 0, 0, 0 },
            { 0, (rect.width / rect.height) / t, 0, 0 },
            { 0, 0, 0, 1 },
            { 0, 0, NEAR_PLANE, 0 },
        }
        return { location = loc, rotation = rot, fov = pov.FOV, width = width, height = height, rect = rect,
                 forward = forward, right = right, up = up, viewMatrix = viewMatrix,
                 projectionMatrix = projectionMatrix, viewProjection = multiply(viewMatrix, projectionMatrix) }
    end)
    if ok then return view end
    return nil
end

-- Screen position of a world location ({X, Y, Z} or an FVector): x and y in pixels from the viewport's
-- top left, and how far in front of the camera it is. Nil when it's behind the camera.
function View.worldToScreen(location, view)
    view = view or View.current()
    if not view then return nil end
    local m = view.viewProjection
    local px, py, pz = location.X, location.Y, location.Z
    local cx = px * m[1][1] + py * m[2][1] + pz * m[3][1] + m[4][1]
    local cy = px * m[1][2] + py * m[2][2] + pz * m[3][2] + m[4][2]
    local cw = px * m[1][4] + py * m[2][4] + pz * m[3][4] + m[4][4]
    if cw <= 0 then return nil end
    local r = view.rect
    return r.x + (cx / cw * 0.5 + 0.5) * r.width, r.y + (0.5 - cy / cw * 0.5) * r.height, cw
end

-- Where a world location is relative to the camera, in centimetres: right, up and forward (negative
-- forward is behind it). Works for points off screen too, e.g. to point at them from the screen's edge.
function View.cameraSpace(location, view)
    view = view or View.current()
    if not view then return nil end
    local d = { location.X - view.location.X, location.Y - view.location.Y, location.Z - view.location.Z }
    return dot(d, view.right), dot(d, view.up), dot(d, view.forward)
end

-- The same through the engine: x and y in pixels, or nil when it can't be projected.
function View.engineWorldToScreen(location)
    local c = controller()
    if not c or not libs() then return nil end
    local out = {}
    local ok, hit = pcall(function()
        return statics:ProjectWorldToScreen(c, { X = location.X, Y = location.Y, Z = location.Z }, out, false)
    end)
    if not ok or not hit or out.X == nil then return nil end
    return out.X, out.Y
end

return View
'''


def lua():
    return LUA.replace("@NEAR_PLANE@", repr(NEAR_PLANE))
