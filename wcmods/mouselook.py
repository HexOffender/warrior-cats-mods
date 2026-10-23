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
        elif key == "toggle_key":
            if value not in TOGGLE_KEYS + ("",):
                raise ValueError(f"mouselook.json: 'toggle_key' should be one of {', '.join(TOGGLE_KEYS)} or \"\"")
        out[key] = value
    return out


def merge(items):
    settings = dict(DEFAULTS)
    for data in items:
        settings.update(data)
    if settings["pitch_min"] >= settings["pitch_max"]:
        raise ValueError("mouse look: 'pitch_min' must be below 'pitch_max'")
    return settings


def _lua(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(float(value))
    return json.dumps(value)   # ASCII-only strings here; JSON escapes are valid Lua


def script(settings):
    table = "{ " + ", ".join(f"{k} = {_lua(settings[k])}" for k in DEFAULTS) + " }"
    return LUA_TEMPLATE.replace("@SETTINGS@", table)


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
local function wrap(a) return (a + 180) % 360 - 180 end
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
        mouseX = key("MouseX"), mouseY = key("MouseY"), lmb = key("LeftMouseButton"), rmb = key("RightMouseButton"),
        -- The game's Reset camera keys (Player_Camera_Reset) also level the tilt.
        reset = { key("R"), key("Gamepad_LeftShoulder") },
        tilt = FName("Player_Camera_Up"), none = FName("None"),
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

-- The pivot: an empty scene component the script adds to the camera actor, attached where the arm was,
-- with the arm moved onto it. Its rotation is the script's alone. Made once per camera actor; if that
-- fails, tilting stays off for that camera rather than trying again every frame.
local pivot, pivotFor, pivotFailed
local function ensurePivot(cam, arm)
    if pivotFor ~= nil and same(pivotFor, cam) then
        return (not pivotFailed) and valid(pivot) and pivot or nil
    end
    pivotFor, pivot, pivotFailed = cam, nil, true
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
    pivot, pivotFailed = comp, false
    return pivot
end

local tilt, written = 0, nil   -- tilt: degrees the pivot adds to the game's arm pitch
local dumped, sawMouse, pendingYaw
local tally = { yaw = { kept = 0, undone = 0 }, tilt = { kept = 0, undone = 0 } }
local acc = { dx = 0, dy = 0, since = nil, ticked = 0 }
local undoneLogged = 0

local mismatches = 0
local function setTilt(cam, arm, amount)
    local p = ensurePivot(cam, arm)
    if not p then return end
    if written ~= nil then
        local t, now = tally.tilt, p.RelativeRotation
        if math.abs(now.Pitch - written) < 0.001 then
            t.kept = t.kept + 1
        else
            t.undone = t.undone + 1
            if mismatches < 3 then
                mismatches = mismatches + 1
                log("the pivot's pitch changed between frames: wrote %.2f, now %s", written, fmtRot(now))
            end
        end
    end
    if written == nil or math.abs(amount - written) > 0.0001 then
        setRotation(p, amount, 0, 0)
    end
    written = amount
end

-- Diagnostics (debug only): the game's axis bindings, and how its own camera keys tilt the camera.
local function dumpBindings()
    local settings = StaticFindObject("/Script/Engine.Default__InputSettings")
    if not valid(settings) then return end
    local out = {}
    settings.AxisMappings:ForEach(function(_, elem)
        local m = elem:get()
        out[#out + 1] = string.format("%s=%s*%.2f", m.AxisName:ToString(), m.Key.KeyName:ToString(), m.Scale)
    end)
    log("input settings axis mappings (%d): %s", #out, table.concat(out, " "))
end
local arrows = { since = nil }
local function watchArrows(cam, arm, now)
    local v = pc:GetInputAxisValue(keys.tilt)
    if math.abs(v) <= 0.2 then return end
    arrows.since = arrows.since or now
    if now - arrows.since < 0.5 then return end
    arrows.since = nil
    local seen = "?"
    pcall(function() seen = fmtRot(pc.PlayerCameraManager.CameraCachePrivate.POV.Rotation) end)
    log("camera keys tilt %.2f: root %s, arm %s, camera %s, view %s", v, fmtRot(cam.RootComponent.RelativeRotation),
        fmtRot(arm.RelativeRotation), fmtRot(cam.CameraComponent.RelativeRotation), seen)
end

local function steer(cam, now)
    local root, arm, view = cam.RootComponent, cam.AdventureArmComponent, cam.CameraComponent
    if not (valid(root) and valid(arm) and valid(view)) then return end
    if not dumped then
        dumped = true
        debug("start: root %s, arm %s, arm length %.0f, camera %s", fmtRot(root.RelativeRotation),
            fmtRot(arm.RelativeRotation), arm.TargetArmLength, fmtRot(view.RelativeRotation))
        if SETTINGS.debug then
            local ok, err = pcall(dumpBindings)
            if not ok then report("bindings", err) end
        end
    end
    if SETTINGS.debug then watchArrows(cam, arm, now) end

    local r = root.RelativeRotation
    if pendingYaw then
        local t = tally.yaw
        if math.abs(wrap(r.Yaw - pendingYaw.want)) <= math.abs(wrap(r.Yaw - pendingYaw.was)) then
            t.kept = t.kept + 1
        else
            t.undone = t.undone + 1
            if SETTINGS.debug and undoneLogged < 8 then
                undoneLogged = undoneLogged + 1
                log("a turn was undone: yaw was %.2f, wrote %.2f, next frame %.2f", pendingYaw.was, pendingYaw.want, r.Yaw)
            end
        end
        pendingYaw = nil
    end

    local dx = pc:GetInputAnalogKeyState(keys.mouseX)
    local dy = pc:GetInputAnalogKeyState(keys.mouseY)
    local k = DEGREES_PER_UNIT * SETTINGS.sensitivity
    if dx ~= 0 or dy ~= 0 then
        if not sawMouse then
            sawMouse = true
            log("mouse movement is reaching the game")
        end
        acc.dx, acc.dy = acc.dx + dx, acc.dy + dy
    end
    if dx ~= 0 then
        local want = r.Yaw + dx * k
        setRotation(root, r.Pitch, want, r.Roll)
        pendingYaw = { was = r.Yaw, want = want }
    end

    -- Keep the total pitch within the limits, whatever the game gives the arm (crouching, climbing).
    local base = arm.RelativeRotation.Pitch
    tilt = tilt + dy * k * (SETTINGS.invert and -1 or 1)
    tilt = math.max(SETTINGS.pitch_min - base, math.min(SETTINGS.pitch_max - base, tilt))
    for _, key in ipairs(keys.reset) do
        if pc:WasInputKeyJustPressed(key) then tilt = 0 end
    end
    if tilt ~= 0 or written ~= nil then setTilt(cam, arm, tilt) end

    if SETTINGS.debug and (acc.dx ~= 0 or acc.dy ~= 0) then
        if not acc.since then acc.since, acc.ticked = now, 0 end
        -- Game time this script saw frames for, against game time that passed: below 100% means frames
        -- were skipped, and their mouse movement lost.
        acc.ticked = acc.ticked + lib.statics:GetWorldDeltaSeconds(pc)
        if now - acc.since >= 2 then
            -- "view" is what the player sees: the camera manager's last result.
            local seen = "?"
            pcall(function() seen = fmtRot(pc.PlayerCameraManager.CameraCachePrivate.POV.Rotation) end)
            log("mouse %.1f, %.1f; tilt %.1f deg (turns kept %d undone %d; tilt kept %d undone %d; frames seen %.0f%%) root %s arm %s view %s",
                acc.dx, acc.dy, tilt, tally.yaw.kept, tally.yaw.undone, tally.tilt.kept, tally.tilt.undone,
                100 * acc.ticked / (now - acc.since), fmtRot(r), fmtRot(arm.RelativeRotation), seen)
            acc.dx, acc.dy, acc.since = 0, 0, nil
        end
    end
end

local lastTime, lastCam
local function step()
    if not setup() then return end
    if not valid(pc) then
        pc, search = nil, search - 1
        if search > 0 then return end
        search = 30   -- looking for the controller is slow; try twice a second until it exists
        pc = findController()
        if not pc then return end
    end
    local want = enabled and not pc.bShowMouseCursor and exploring()
    if want ~= captured then
        capture(want)
    elseif captured and (pc:WasInputKeyJustPressed(keys.lmb) or pc:WasInputKeyJustPressed(keys.rmb)) then
        capture(true)   -- a click means the game has focus; take the mouse back if a menu let it go
    end
    if not enabled and tilt ~= 0 then
        tilt = 0   -- switched off: level the camera again
        if valid(pivot) then setRotation(pivot, 0, 0, 0) end
        written = 0
    end
    local cam = explorationCamera()
    if not cam then
        pendingYaw = nil
        return
    end
    if not same(lastCam, cam) then
        tilt, written = 0, nil   -- a new camera (another area or a reload) starts level
    end
    lastCam = cam
    if not captured then
        pendingYaw = nil   -- a menu is open over the camera: keep the view as it is
        return
    end
    local now = lib.statics:GetTimeSeconds(pc)
    if now == lastTime then return end   -- once per game frame, and not while paused
    lastTime = now
    steer(cam, now)
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
'''
