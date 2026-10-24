"""Mouse look (mouselook.json): a UE4SS script that lets the mouse turn the exploration camera.

The game switches Unreal's mouse capture off (DefaultViewportMouseCaptureMode=NoCapture in its
DefaultInput.ini), so mouse movement never reaches it, and the bindings kept in the save don't
change its controls. The script works at runtime instead: while you explore with the cursor hidden
it captures the mouse like most PC games and moves the camera actor (BP_AdventureCamera) directly.
It releases the mouse whenever the game shows its cursor.
"""
import json

UE4SS_MOD_NAME = "WCModsMouseLook"
DEFAULTS = {
    "sensitivity": 1.0,
    "invert": False,
    "toggle_key": "F6",     # turns mouse look off and on in game; "" for none
    # Tilt limits, from Gameplay.Exploration.Camera.Pitch.Min/Max in TuningData.csv.
    "pitch_min": -20.0,
    "pitch_max": 23.0,
    # How long the camera takes to catch up with the mouse, in milliseconds; 0 for not at all. The game
    # eases the camera after the arrow keys and stick over about 200 ms (Lag.Rotation 5 in TuningData.csv).
    "smoothing": 0.0,
    "debug": False,         # log what the script sees to ue4ss/UE4SS.log as [MouseLook]
}
TOGGLE_KEYS = tuple(f"F{n}" for n in range(1, 13) if n != 11)   # F11 is the game's fullscreen key


def validate(raw):
    """Check a mouselook.json and return just the settings it sets."""
    if not isinstance(raw, dict):
        raise ValueError("mouselook.json should be an object like {\"sensitivity\": 1.0}")
    out = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if key not in DEFAULTS:
            raise ValueError(f"mouselook.json: unknown setting '{key}' (known: {', '.join(DEFAULTS)})")
        default = DEFAULTS[key]
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError(f"mouselook.json: '{key}' should be true or false")
        elif isinstance(default, float):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"mouselook.json: '{key}' should be a number")
            value = float(value)
            if key == "sensitivity" and not 0.05 <= value <= 10:
                raise ValueError("mouselook.json: 'sensitivity' should be between 0.05 and 10")
            if key.startswith("pitch_") and not -89 <= value <= 89:
                raise ValueError(f"mouselook.json: '{key}' should be between -89 and 89 degrees")
            if key == "smoothing" and not 0 <= value <= 1000:
                raise ValueError("mouselook.json: 'smoothing' should be between 0 and 1000 milliseconds")
        elif key == "toggle_key":
            if value not in TOGGLE_KEYS + ("",):
                raise ValueError(f"mouselook.json: 'toggle_key' should be one of {', '.join(TOGGLE_KEYS)} or \"\"")
        out[key] = value
    return out


def merge(items, sources=None):
    """Settings from several mods, later ones winning. sources names each item for error messages."""
    settings, setter = dict(DEFAULTS), {}
    for i, data in enumerate(items):
        settings.update(data)
        for key in data:
            setter[key] = sources[i] if sources else None
    if settings["pitch_min"] >= settings["pitch_max"]:
        def said(key):
            who = setter.get(key)
            return f"{settings[key]:g} ({'from ' + who if who else 'default'})"
        raise ValueError(f"mouse look: pitch_min {said('pitch_min')} must be below pitch_max {said('pitch_max')}")
    return settings


def _lua(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(float(value))
    return json.dumps(value)   # ASCII-only strings here; JSON escapes are valid Lua


def script(settings, save=None):
    """save: where the in-game menu's Save writes the settings: {"path": the mod's mouselook.json,
    "file": how to name it to the player, "keep": the file's own notes such as "_help"}."""
    from .sdk import lua_value
    table = "{ " + ", ".join(f"{k} = {_lua(settings[k])}" for k in DEFAULTS) + " }"
    return LUA_TEMPLATE.replace("@SETTINGS@", table).replace("@SAVE@", lua_value(save))


LUA_TEMPLATE = r'''-- Mouse look for Warrior Cats: Clans of the Forest. Written by wcmods from mouselook.json: change that
-- (or the Mouse look card on the studio's Controls page) and install again rather than editing this.
--
-- The game switches the engine's mouse capture off, so mouse movement never reaches it. While you explore
-- with the cursor hidden, this captures the mouse the way most PC games do and moves the exploration camera
-- (BP_AdventureCamera) itself. Whenever the game shows its cursor, the mouse is released again. The arrow
-- keys and the right stick keep working.
--
-- Turning rotates the camera actor's root, which the game turns too and leaves alone otherwise. Tilting
-- can't use the spring arm or the camera: the game sets their rotation every frame. So the script slips
-- a component of its own (a pivot) in between the root and the spring arm and tilts that. The arm keeps
-- doing everything else, including its collision test, so the camera orbits up and down around the cat.
--
-- How the game turns its camera (SwtAdventureCameraActor, read from its code): each frame it adds that
-- frame's arrow-key and stick turn to the root's current rotation, so a turn the script made earlier in
-- the frame stays. On a camera spline, while it looks at something, and for 0.8 s after joining or
-- leaving a spline, it sets the rotation itself and ignores the arrow keys too; the mouse can't turn it
-- then either. The spring arm then eases after the root (rotation lag, about 200 ms). That suits a stick
-- but makes the mouse feel floaty, so while the mouse is captured the arm uses `smoothing` instead, and
-- gets the game's own back when the mouse is released.
local SETTINGS = @SETTINGS@

-- The game's mouse axes give 0.07 per count (AxisConfig in DefaultInput.ini); Unreal turns 2.5 degrees per unit.
local DEGREES_PER_UNIT = 2.5
local KEEP_RELATIVE = 0   -- EAttachmentRule::KeepRelative

local function log(fmt, ...) print(string.format("[MouseLook] " .. fmt .. "\n", ...)) end
local function debug(fmt, ...) if SETTINGS.debug then log(fmt, ...) end end

local reported, nreported = {}, 0
local function report(where, err)
    local key = where .. tostring(err)
    if reported[key] or nreported >= 20 then return end
    reported[key], nreported = true, nreported + 1
    log("error in %s: %s", where, tostring(err))
end

local function valid(o) return o ~= nil and o:IsValid() end
local function className(o) return o:GetClass():GetFName():ToString() end
local function same(a, b) return valid(a) and valid(b) and a:GetAddress() == b:GetAddress() end

local lib, keys
local function setup()
    if lib then return true end
    local widgets = StaticFindObject("/Script/UMG.Default__WidgetBlueprintLibrary")
    local statics = StaticFindObject("/Script/Engine.Default__GameplayStatics")
    local kmath = StaticFindObject("/Script/Engine.Default__KismetMathLibrary")
    local sceneComponent = StaticFindObject("/Script/Engine.SceneComponent")
    local input = StaticFindObject("/Script/Engine.Default__InputSettings")
    if not (valid(widgets) and valid(statics) and valid(kmath) and valid(sceneComponent)) then return false end
    lib = { widgets = widgets, statics = statics, math = kmath, sceneComponent = sceneComponent, input = input }
    local function key(name) return { KeyName = FName(name) } end
    keys = {
        mouseX = key("MouseX"), mouseY = key("MouseY"),
        -- The game's Reset camera keys also level the tilt. The game ignores remapped bindings, so these
        -- are always its own; a key remapper outside the game sends them too.
        reset = { key("R"), key("Gamepad_LeftShoulder") },
        none = FName("None"),
    }
    return true
end

local pc, search = nil, 0
local function findController()
    for _, c in ipairs(FindAllOf("PlayerController") or {}) do
        if valid(c) and valid(c.Player) then return c end
    end
    return nil
end

local enabled, captured = true, false
local function menuOpen()
    local ok, open = pcall(function() return ModRef:GetSharedVariable("WCModsMenu.open") end)
    return ok and open == true
end
local function capture(on)
    captured = on
    if on then
        -- The game turns on Unreal's mouse smoothing (bEnableMouseSmoothing), which makes quick movements
        -- uneven. Nothing else in the game reads the mouse axes, so it's simply switched off.
        if valid(lib.input) and lib.input.bEnableMouseSmoothing then
            lib.input.bEnableMouseSmoothing = false
            debug("mouse smoothing off")
        end
        -- Game-only input: the viewport captures and hides the mouse, so its movement reaches the game.
        if not pcall(function() lib.widgets:SetInputMode_GameOnly(pc, false) end) then
            lib.widgets:SetInputMode_GameOnly(pc)
        end
    else
        -- Game-and-UI input, as in the game's menus: the cursor moves freely and clicks reach the UI.
        if not pcall(function() lib.widgets:SetInputMode_GameAndUIEx(pc, nil, 0, false, false) end) then
            lib.widgets:SetInputMode_GameAndUIEx(pc, CreateInvalidObject(), 0, false, false)
        end
    end
    debug("mouse %s", on and "captured" or "released")
end

local function exploring()
    local pawn = pc.Pawn
    return valid(pawn) and className(pawn):find("Exploration_Character_Player", 1, true) ~= nil
end

local lastView
local function explorationCamera()
    local view = pc:GetViewTarget()
    local name = valid(view) and className(view) or "none"
    if name ~= lastView then
        lastView = name
        debug("camera: %s", name)
    end
    if name == "BP_AdventureCamera_C" then return view end
    return nil
end

local function fmtRot(r) return string.format("p=%.1f y=%.1f", r.Pitch, r.Yaw) end
-- The rotator comes from MakeRotator: passing a Lua table as the rotator keeps its yaw but drops its
-- pitch (tested in game: asked for 7, read back 0).
local function setRotation(comp, pitch, yaw, roll)
    comp:K2_SetRelativeRotation(lib.math:MakeRotator(roll, pitch, yaw), false, {}, false)
end

-- tilt: degrees the pivot adds to the game's arm pitch, as the player set it. written: what the pivot
-- holds now (nil before the first tilt).
local tilt, written = 0, nil

-- The pivot: an empty scene component the script adds to the camera actor, attached where the arm was,
-- with the arm moved onto it. Its rotation is the script's alone. It's looked up through the arm rather
-- than by remembering the camera, because a camera made after a reload can land at the old one's address.
local pivot, retryAt = nil, 0
local function ensurePivot(cam, arm, now)
    if valid(pivot) and same(arm:GetAttachParent(), pivot) then return pivot end
    if now < retryAt then return nil end
    retryAt = now + 5   -- if building it fails, try again in a few seconds rather than every frame
    if pivot ~= nil then tilt = 0 end   -- a new camera (another area or a reload) starts level
    pivot, written = nil, nil
    local parent = arm:GetAttachParent()
    if not valid(parent) then error("the camera's arm isn't attached to anything") end
    local identity = { Rotation = { X = 0, Y = 0, Z = 0, W = 1 }, Translation = { X = 0, Y = 0, Z = 0 },
                       Scale3D = { X = 1, Y = 1, Z = 1 } }
    local comp = cam:AddComponentByClass(lib.sceneComponent, true, identity, false)
    if not valid(comp) then error("couldn't add a pivot to the camera") end
    comp:K2_AttachToComponent(parent, keys.none, KEEP_RELATIVE, KEEP_RELATIVE, KEEP_RELATIVE, false)
    arm:K2_AttachToComponent(comp, keys.none, KEEP_RELATIVE, KEEP_RELATIVE, KEEP_RELATIVE, false)
    if not same(arm:GetAttachParent(), comp) then error("couldn't move the camera's arm onto the pivot") end
    debug("pivot added between %s and the camera arm", className(parent))
    pivot, retryAt = comp, 0
    return pivot
end

local function setTilt(cam, arm, amount, now)
    local p = ensurePivot(cam, arm, now)
    if not p then return end
    if written == nil or math.abs(amount - written) > 0.0001 then setRotation(p, amount, 0, 0) end
    written = amount
end

-- The arm's rotation lag is its CameraRotationLagSpeed, which the game sets once when the camera starts
-- (Lag.Rotation in TuningData.csv: 5). The time it takes to catch up is about 1/speed; 0 means at once.
local function mouseLag() return SETTINGS.smoothing > 0 and 1000 / SETTINGS.smoothing or 0 end
local lagged   -- { arm = the arm the script changed, speed = the game's own value }

local function restoreLag()
    if not lagged then return end
    if valid(lagged.arm) then lagged.arm.CameraRotationLagSpeed = lagged.speed end
    debug("camera smoothing back to the game's (lag speed %.2f)", lagged.speed)
    lagged = nil
end

local function useMouseLag(arm)
    if lagged and not same(lagged.arm, arm) then restoreLag() end   -- a new camera keeps its own value
    local speed, want = arm.CameraRotationLagSpeed, mouseLag()
    if not lagged then
        lagged = { arm = arm, speed = speed }
        debug("camera lag speed %.2f while the mouse is captured (the game's %.2f)", want, speed)
    end
    if math.abs(speed - want) > 0.0001 then arm.CameraRotationLagSpeed = want end
end

local sawMouse
local acc = { dx = 0, dy = 0, since = nil }
-- Debug only: whether each turn was still there the next frame, and how even the frames were.
local stats = { frames = 0, slowest = 0, kept = 0, undone = 0 }
local pendingYaw   -- { was, want }: the turn written last frame
local function wrap(a) return (a + 180) % 360 - 180 end

local function steer(cam, now, dt)
    local root, arm = cam.RootComponent, cam.AdventureArmComponent
    if not (valid(root) and valid(arm)) then return end
    useMouseLag(arm)

    local dx = pc:GetInputAnalogKeyState(keys.mouseX)
    local dy = pc:GetInputAnalogKeyState(keys.mouseY)
    local k = DEGREES_PER_UNIT * SETTINGS.sensitivity
    if (dx ~= 0 or dy ~= 0) and not sawMouse then
        sawMouse = true
        log("mouse movement is reaching the game")
    end
    local r = root.RelativeRotation
    if pendingYaw then
        local t = math.abs(wrap(r.Yaw - pendingYaw.want)) <= math.abs(wrap(r.Yaw - pendingYaw.was)) and "kept" or "undone"
        stats[t] = stats[t] + 1
        pendingYaw = nil
    end
    if dx ~= 0 then
        local was = r.Yaw
        setRotation(root, r.Pitch, was + dx * k, r.Roll)
        if SETTINGS.debug then pendingYaw = { was = was, want = was + dx * k } end
    end

    -- The limits are for the total pitch (the game's arm pitch plus the tilt), and the allowed range always
    -- includes level. So a camera the game puts past a limit (some areas look steeply down) is never pushed
    -- back, and a tilt the current posture can't fit (crouching lowers the arm) is held back, not lost.
    local base = arm.RelativeRotation.Pitch
    local lo, hi = math.min(0, SETTINGS.pitch_min - base), math.max(0, SETTINGS.pitch_max - base)
    local d = dy * k * (SETTINGS.invert and -1 or 1)
    if d ~= 0 then tilt = math.max(math.min(lo, tilt), math.min(math.max(hi, tilt), tilt + d)) end
    for _, key in ipairs(keys.reset) do
        if pc:WasInputKeyJustPressed(key) then tilt = 0 end
    end
    local shown = math.max(lo, math.min(hi, tilt))
    if shown ~= 0 or written ~= nil then setTilt(cam, arm, shown, now) end

    if SETTINGS.debug then
        if dx ~= 0 or dy ~= 0 then acc.dx, acc.dy, acc.since = acc.dx + dx, acc.dy + dy, acc.since or now end
        if acc.since then
            stats.frames, stats.slowest = stats.frames + 1, math.max(stats.slowest, dt)
            if now - acc.since >= 2 then
                -- "view" is what the player sees: the camera manager's last result.
                local seen = "?"
                pcall(function() seen = fmtRot(pc.PlayerCameraManager.CameraCachePrivate.POV.Rotation) end)
                log("mouse %.1f, %.1f; tilt %.1f (shown %.1f); turns kept %d, undone %d; %d frames, slowest %.0f ms; " ..
                    "lag speed %.2f; root %s arm %s view %s", acc.dx, acc.dy, tilt, shown, stats.kept, stats.undone,
                    stats.frames, stats.slowest * 1000, arm.CameraRotationLagSpeed, fmtRot(root.RelativeRotation),
                    fmtRot(arm.RelativeRotation), seen)
                acc.dx, acc.dy, acc.since = 0, 0, nil
                stats.frames, stats.slowest, stats.kept, stats.undone = 0, 0, 0, 0
            end
        end
    end
end

local lastTime, lookBaseline
local function step()
    if not setup() then return end
    if not valid(pc) then
        pc, search = nil, search - 1
        if search > 0 then return end
        search = 30   -- looking for the controller is slow; try twice a second until it exists
        pc = findController()
        if not pc then return end
    end
    -- The mod menu (Insert) has the keyboard and mouse while it's open, and gives them back when it
    -- closes; changing the input mode under it would hand the game its controls again.
    if menuOpen() then
        captured = false
        restoreLag()
        lastTime = nil
        return
    end
    local want = enabled and not pc.bShowMouseCursor and exploring()
    if want ~= captured then capture(want) end
    if not enabled and tilt ~= 0 then
        tilt = 0   -- switched off: level the camera again
        if valid(pivot) then setRotation(pivot, 0, 0, 0) end
        written = 0
    end
    if not captured then   -- a menu is open, or mouse look is off
        restoreLag()
        lastTime = nil
        return
    end
    -- The engine's look lock, for moments that disable looking around. Only a lock that comes on during
    -- play counts: a game that never uses controller look may keep it on all the time.
    local locked = pc:IsLookInputIgnored()
    if lookBaseline == nil then
        lookBaseline = locked
        debug("look input ignored at start: %s", tostring(locked))
    end
    if locked and not lookBaseline then return end
    local cam = explorationCamera()
    if not cam then return end   -- another camera (a cutscene, combat) is showing: leave it alone
    local now = lib.statics:GetTimeSeconds(pc)
    if now == lastTime then return end   -- once per game frame, and not while paused
    local dt = lastTime and now - lastTime or 0
    lastTime = now
    steer(cam, now, dt)
end

local function frame()
    local ok, err = pcall(step)
    if not ok then report("update", err) end
end

if SETTINGS.toggle_key ~= "" and Key ~= nil and Key[SETTINGS.toggle_key] ~= nil then
    RegisterKeyBind(Key[SETTINGS.toggle_key], function()
        enabled = not enabled
        log("mouse look %s", enabled and "on" or "off")
    end)
end

if LoopInGameThreadAfterFrames == nil or not pcall(LoopInGameThreadAfterFrames, 1, frame) then
    LoopAsync(5, function()
        ExecuteInGameThread(frame)
        return false
    end)
end
log("loaded (sensitivity %.2f, invert %s, toggle key %s)", SETTINGS.sensitivity, tostring(SETTINGS.invert),
    SETTINGS.toggle_key ~= "" and SETTINGS.toggle_key or "none")

-- A page in the mod menu (Insert) to change the settings while you play. Save writes them to the mod's
-- mouselook.json, so installing again keeps them.
local SAVE = @SAVE@
-- The page is extra: if the menu can't load or add it, the script works as before.
local okMenu, Menu = pcall(require, "WCModsMenu")
if okMenu then pcall(function()
    if SETTINGS.toggle_key ~= "" then Menu.key(SETTINGS.toggle_key, "Mouse look on and off") end
    local installed, status = {}, nil
    for k, v in pairs(SETTINGS) do installed[k] = v end
    Menu.page("Mouse look", function(ui)
        ui.heading("Mouse look")
        ui.note("Changes apply as you make them." .. (SAVE and (" Save writes them to " .. SAVE.file ..
                ", so installing again keeps them.") or ""))
        enabled = ui.switch("Mouse look", enabled)
        SETTINGS.sensitivity = ui.slider("Sensitivity", SETTINGS.sensitivity, 0.05, 3, { step = 0.05, format = "x%.2f" })
        SETTINGS.invert = ui.toggle("Invert up/down", SETTINGS.invert)
        SETTINGS.smoothing = ui.slider("Smoothing", SETTINGS.smoothing, 0, 500, { step = 10, format = "%.0f ms" })
        ui.note("How long the camera takes to catch up with the mouse; the game eases the arrow keys over about 200 ms.")
        -- Both stay within -89..89 with the lowest at least a degree under the highest, as mouselook.json needs.
        SETTINGS.pitch_min = ui.slider("Lowest tilt", SETTINGS.pitch_min, -89, 88, { step = 1, format = "%.0f deg" })
        SETTINGS.pitch_max = ui.slider("Highest tilt", SETTINGS.pitch_max, -88, 89, { step = 1, format = "%.0f deg" })
        if SETTINGS.pitch_min > SETTINGS.pitch_max - 1 then SETTINGS.pitch_min = math.max(-89, SETTINGS.pitch_max - 1) end
        SETTINGS.debug = ui.toggle("Log what it does to UE4SS.log", SETTINGS.debug)
        ui.field("Switches on and off with", SETTINGS.toggle_key ~= "" and SETTINGS.toggle_key or "no key")
        ui.space(6)
        local hit = ui.buttons(SAVE and { "Save", "Back to installed" } or { "Back to installed" }, { kinds = { "primary" } })
        if hit and SAVE and hit == 1 then
            local out = {}
            for k, v in pairs(SAVE.keep or {}) do out[k] = v end
            for k, v in pairs(SETTINGS) do out[k] = v end
            local ok, err = Menu.saveJson(SAVE.path, out)
            status = ok and ("Saved to " .. SAVE.file .. ".") or ("Couldn't save: " .. tostring(err))
        elseif hit then
            for k, v in pairs(installed) do SETTINGS[k] = v end
            status = "Back to the installed settings."
        end
        if status then ui.note(status) end
    end, { order = 12, group = "cat" })
end) end
'''