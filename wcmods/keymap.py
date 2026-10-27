"""Unreal key names to Windows key codes, and the remap plans: the in-game remap script's (gameremap.py)
and the key remapper's (remapper.py).

The game ignores edited bindings (see README, "Remapping keys"), so it always listens for its own
keys. Inside the game, a remap works on the game's actions: the in-game script sends an action's
command when its new key is pressed, and drops the game's own command when it comes from the old key
(native_plan). Movement and the camera are axes, which it can't move; those and the "menus" section
are left to the key remapper outside the game, where a remap is "when I press F, send the game E":
it holds back F and sends E in its place. Actions in controls.json are turned into such key pairs
using the game's bindings below; the "keys" section maps keys directly (e.g. W, which no action
lists). Both apply while you play. The "menus" section is a separate set of key pairs used only
while a menu is open.
"""
from .controls import KNOWN_KEYS, normalise_key

# What the game listens for on the keyboard (from the save; edits to it are ignored). Axis actions
# list their negative key; the positive ones (W, D, Up, Right) are built in.
GAME_KEYBOARD = {
    "Player_Movement_Up": "S", "Player_Movement_Right": "A", "Player_Camera_Up": "Down",
    "Player_Camera_Right": "Left", "Player_Pounce": "SpaceBar", "Player_Drop": "C",
    "Player_Den_Place": "X", "Player_Interact": "E", "Player_ReturnToCamp": "X",
    "Player_Friend_Talk": "C", "Player_Crouch": "LeftControl", "Player_Scent_Tracking": "Q",
    "Player_Camera_Reset": "R", "Player_Run": "LeftShift", "Player_Pause": "Enter",
}
BUILT_IN_KEYS = ("W", "D", "Up", "Right")
# Actions on keys the save doesn't list, from the game's Controls screen (seen in game sending these
# actions). Only the in-game script moves them; the key remapper doesn't know them.
SCREEN_KEYBOARD = {"Player_Show_Inventory": "I", "Player_Show_Quest": "K", "Player_Show_Map": "M",
                   "Player_Growl": "L"}
# The controller's, from the save in the same way.
GAME_GAMEPAD = {
    "Player_Movement_Up": "Gamepad_LeftY", "Player_Movement_Right": "Gamepad_LeftX",
    "Player_Camera_Up": "Gamepad_RightY", "Player_Camera_Right": "Gamepad_RightX",
    "Player_Pounce": "Gamepad_FaceButton_Top", "Player_Drop": "Gamepad_FaceButton_Right",
    "Player_Den_Place": "Gamepad_FaceButton_Top", "Player_Interact": "Gamepad_FaceButton_Bottom",
    "Player_ReturnToCamp": "Gamepad_FaceButton_Top", "Player_Friend_Talk": "Gamepad_FaceButton_Right",
    "Player_Crouch": "Gamepad_LeftTrigger", "Player_Scent_Tracking": "Gamepad_FaceButton_Left",
    "Player_Camera_Reset": "Gamepad_LeftShoulder", "Player_Run": "Gamepad_RightShoulder",
    "Player_Pause": "Gamepad_Special_Right",
}
# Actions the game reads as axes every frame instead of sending as commands, so only the key remapper
# outside the game can move them; and the keyboard keys they're on.
AXES = ("Player_Movement_Up", "Player_Movement_Right", "Player_Camera_Up", "Player_Camera_Right")
AXIS_KEYS = ("W", "S", "A", "D", "Up", "Down", "Left", "Right")
# Keys and buttons the in-game script can put an action on: any the game sees as a button.
BUTTONS = KNOWN_KEYS - {"Gamepad_LeftX", "Gamepad_LeftY", "Gamepad_RightX", "Gamepad_RightY",
                        "Gamepad_LeftTriggerAxis", "Gamepad_RightTriggerAxis"}

# Unreal key name -> Windows virtual-key code.
VK = {chr(c): c for c in range(ord("A"), ord("Z") + 1)}
VK.update({name: 0x30 + i for i, name in enumerate(
    "Zero One Two Three Four Five Six Seven Eight Nine".split())})
VK.update({f"F{i}": 0x6F + i for i in range(1, 13)})
VK.update({f"NumPad{name}": 0x60 + i for i, name in enumerate(
    "Zero One Two Three Four Five Six Seven Eight Nine".split())})
VK.update({
    "Escape": 0x1B, "Tab": 0x09, "CapsLock": 0x14, "SpaceBar": 0x20, "Enter": 0x0D, "BackSpace": 0x08,
    "Delete": 0x2E, "Insert": 0x2D, "Home": 0x24, "End": 0x23, "PageUp": 0x21, "PageDown": 0x22,
    "Up": 0x26, "Down": 0x28, "Left": 0x25, "Right": 0x27,
    "LeftShift": 0xA0, "RightShift": 0xA1, "LeftControl": 0xA2, "RightControl": 0xA3,
    "LeftAlt": 0xA4, "RightAlt": 0xA5,
    "Tilde": 0xC0, "Hyphen": 0xBD, "Equals": 0xBB, "LeftBracket": 0xDB, "RightBracket": 0xDD,
    "Backslash": 0xDC, "Semicolon": 0xBA, "Apostrophe": 0xDE, "Comma": 0xBC, "Period": 0xBE, "Slash": 0xBF,
    "Multiply": 0x6A, "Add": 0x6B, "Subtract": 0x6D, "Decimal": 0x6E, "Divide": 0x6F,
})
NAME_OF_VK = {vk: name for name, vk in VK.items()}
# Keys Windows sends with the "extended" flag; injected copies need it too or the game sees the wrong key.
EXTENDED = {VK[k] for k in ("Delete", "Insert", "Home", "End", "PageUp", "PageDown", "Up", "Down", "Left",
                            "Right", "RightControl", "RightAlt", "Divide")}
# Keys that are never held back when their action moves: the "play" state also covers prompts and
# dialogue shown while you explore, which may confirm or skip with them.
NEVER_HELD_BACK = ("Enter", "SpaceBar", "Escape", "BackSpace", "Tab")
# Mouse buttons and the wheel can stand in for a key, but the game's keys are all keyboard keys.
MOUSE = ("LeftMouseButton", "RightMouseButton", "MiddleMouseButton", "ThumbMouseButton", "ThumbMouseButton2",
         "MouseScrollUp", "MouseScrollDown")


def _key(name):
    return normalise_key("keyboard", name)


def native_plan(merged):
    """What the in-game remap script (gameremap.py) does with controls.json merged across mods, and what's
    left for the key remapper outside the game.

    Returns (plan, rest, warnings). plan is {"send": {key: [action, ...]}, "drop": {action: [key, ...]},
    "keys": {action: [key, ...]}}: pressing a send key sends those actions to the game; the game's own
    command for a drop action is dropped when it comes from one of the keys listed; keys says where each
    changed action is now. rest is controls.json with only what the script can't do (movement and the
    camera, keys standing for them or for keys no action lists, and the menus), for plan and menu_plan.
    """
    send, drop, extra, rest, warnings = {}, {}, {}, {}, []
    tables = (("keyboard", {**GAME_KEYBOARD, **SCREEN_KEYBOARD}), ("gamepad", GAME_GAMEPAD))
    now = {device: dict(game) for device, game in tables}   # the key each action is on
    setters = {}   # key -> the controls.json entries that put actions on it

    def add(key, action, setter):
        if action not in send.setdefault(key, []):
            send[key].append(action)
        setters.setdefault(key, set()).add(setter)

    for device, game in tables:
        for action, key in merged.get(device, {}).items():
            if action in AXES or action not in game:
                if device == "keyboard":
                    rest.setdefault("keyboard", {})[action] = key   # plan() moves it, or says it doesn't know it
                elif action in AXES:
                    warnings.append(f"gamepad: {action} is a stick, which only Steam Input can move")
                else:
                    warnings.append(f"gamepad: no action named {action} (known: {', '.join(GAME_GAMEPAD)})")
                continue
            new = normalise_key(device, key)
            if new not in BUTTONS:
                warnings.append(f"{device}: {action}: the game has no button named '{new}'")
                continue
            if new != game[action]:
                now[device][action] = new
                add(new, action, action)
                drop.setdefault(action, []).append(game[action])
    for src, dst in merged.get("keys", {}).items():
        s, d = _key(src), _key(dst)
        actions = [a for a, k in tables[0][1].items() if k == d and a not in AXES]
        if not actions or s not in BUTTONS:
            rest.setdefault("keys", {})[src] = dst   # movement, the camera, or a key no action lists
            continue
        for action in actions:
            if s != d:
                add(s, action, f"keys: {s}")
                extra.setdefault(action, []).append(s)
    # A key that now stands for an action stops doing its own, as with the key remapper outside the game.
    for key, actions in send.items():
        if len(setters[key]) > 1:
            warnings.append(f"{key} is set for {' and '.join(actions)}; it does all of them")
        if key in AXIS_KEYS:
            warnings.append(f"{key} now does {', '.join(actions)}, and still moves you or the camera too: the "
                            f"game reads those keys itself; move that job to another key under \"keys\"")
        for device, game in tables:
            for action, own in game.items():
                if own == key and action not in actions and action not in AXES and now[device][action] == key:
                    drop.setdefault(action, []).append(key)
                    now[device][action] = None
                    warnings.append(f"{action} is on {key}, but {key} now does {', '.join(actions)}; move {action} too")
    outside = {_key(k) for k in rest.get("keys", {})} | {_key(k) for k in rest.get("keyboard", {}).values()}
    for key in sorted(outside & set(send)):
        warnings.append(f"{key} is set both for {', '.join(send[key])} and for moving you or the camera; "
                        f"use another key for one of them")
    keys = {}
    for action in sorted(set(drop) | set(extra)):
        found = [now["keyboard"].get(action), *extra.get(action, []), now["gamepad"].get(action)]
        keys[action] = [k for i, k in enumerate(found) if k and k not in found[:i]]
    if merged.get("menus"):
        rest["menus"] = merged["menus"]
    return {"send": send, "drop": drop, "keys": keys}, rest, warnings


def plan(merged):
    """merged: controls.json merged across mods: {"keyboard": {action: key}, "keys": {key: key}}.

    Returns (send, block, warnings). send maps a key you press to the game key it stands for. block
    holds game keys that no longer do anything, because their action moved and nothing else uses them.
    """
    send, moved_from, warnings = {}, set(), []
    # What you press for each of the game's jobs: its actions, plus the built-in keys, which count as
    # jobs of their own (moving W to T should stop W moving you, the same as moving an action).
    game_key = dict(GAME_KEYBOARD, **{f"key:{k}": k for k in BUILT_IN_KEYS})
    pressed = dict(game_key)

    def move(job, new, old):
        if new == old:
            return
        if new in send and send[new] != old:
            warnings.append(f"{new} is set for more than one game key; {job} wins")
        send[new] = old
        moved_from.add(old)

    for action, key in merged.get("keyboard", {}).items():
        if action not in GAME_KEYBOARD:
            warnings.append(f"keyboard: no action named {action} (known: {', '.join(GAME_KEYBOARD)})")
            continue
        new = _key(key)
        if new not in VK and new not in MOUSE:
            warnings.append(f"keyboard: {action}: the remapper can't use '{new}'")
            continue
        pressed[action] = new
        move(action, new, GAME_KEYBOARD[action])
    for src, dst in merged.get("keys", {}).items():
        s, d = _key(src), _key(dst)
        if s not in VK and s not in MOUSE:
            warnings.append(f"keys: the remapper can't use '{s}'")
            continue
        if d not in VK:
            warnings.append(f"keys: '{s}' can only stand for a keyboard key, not '{d}'")
            continue
        if d in BUILT_IN_KEYS:
            pressed[f"key:{d}"] = s
        # Any other game key keeps working on its own key too, unless its action moves.
        move(f"keys: {s}", s, d)
    if merged.get("gamepad"):
        warnings.append("gamepad: the remapper is keyboard and mouse only; remap controller buttons with Steam Input")
    for job, key in pressed.items():
        if key in send and send[key] != game_key[job]:
            warnings.append(f"{job} is on {key}, but {key} now stands for {send[key]}; move {job} too")
    in_use = set(pressed.values()) | set(send)
    block = {k for k in moved_from if k not in in_use}
    for key in sorted(block & set(NEVER_HELD_BACK)):
        warnings.append(f"{key} still does its old job too: prompts and dialogue shown while you play may need it")
    for key in sorted(set(send) & set(NEVER_HELD_BACK)):
        warnings.append(f"{key} now sends {send[key]} while playing, so prompts and dialogue shown during play "
                        f"won't get {key}")
    return send, block - set(NEVER_HELD_BACK), warnings


def menu_plan(merged):
    """The "menus" section, {key you press: game key}, used only while a menu is open.

    Returns (send, warnings). Nothing is held back in menus: the game's own key keeps working too, so
    typing on the name screen and the game's own menu keys are never lost.
    """
    send, warnings = {}, []
    for src, dst in merged.get("menus", {}).items():
        s, d = _key(src), _key(dst)
        if s not in VK and s not in MOUSE:
            warnings.append(f"menus: the remapper can't use '{s}'")
        elif d not in VK:
            warnings.append(f"menus: '{s}' can only stand for a keyboard key, not '{d}'")
        elif s != d:
            send[s] = d
            if len(s) == 1 or s in ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                                    "SpaceBar"):
                warnings.append(f"menus: typing {s} on the name screen sends {d} instead")
    return send, warnings
