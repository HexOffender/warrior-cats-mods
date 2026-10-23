"""Unreal key names to Windows key codes, and the remap plan the key remapper (remapper.py) runs.

The game ignores edited bindings (see README, "Remapping keys"), so it always listens for its own
keys. A remap is therefore "when I press F, send the game E": the remapper holds back F and sends
E in its place. Actions in controls.json are turned into such key pairs using the game's bindings
below; the "keys" section maps keys directly (e.g. W, which no action lists).
"""
from .controls import normalise_key

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
# Mouse buttons and the wheel can stand in for a key, but the game's keys are all keyboard keys.
MOUSE = ("LeftMouseButton", "RightMouseButton", "MiddleMouseButton", "ThumbMouseButton", "ThumbMouseButton2",
         "MouseScrollUp", "MouseScrollDown")


def _key(name):
    return normalise_key("keyboard", name)


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
    return send, {k for k in moved_from if k not in in_use}, warnings
