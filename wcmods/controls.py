"""Key and button names, and the bindings the game keeps in its save.

The game stores each binding as "<kind>,<Action>,<Key>,<Scale>.1" under Shared.InputKeyboard
or Shared.InputGamepad, e.g. "0,Player_Interact,E,1.000000.1" (kind 0 = button, 1 = axis; the game
writes them with the format "%d,%s,%s,%f.1"). It doesn't apply edited ones, though: remaps
written here had no effect in game, so the controls section no longer writes them (see
docs/remapping.md). read_bindings and apply stay for inspecting and testing the save format.
Key names are Unreal FKey names (SpaceBar, LeftShift, F, ThumbMouseButton, Gamepad_FaceButton_Left...).
"""
import json
import re

SECTIONS = {"keyboard": "InputKeyboard", "gamepad": "InputGamepad"}

KNOWN_KEYS = set("""
A B C D E F G H I J K L M N O P Q R S T U V W X Y Z Zero One Two Three Four Five Six Seven Eight Nine
F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 Escape Tab CapsLock SpaceBar Enter BackSpace Delete Insert
Home End PageUp PageDown Up Down Left Right LeftShift RightShift LeftControl RightControl LeftAlt RightAlt
Tilde Hyphen Equals LeftBracket RightBracket Backslash Semicolon Apostrophe Comma Period Slash
NumPadZero NumPadOne NumPadTwo NumPadThree NumPadFour NumPadFive NumPadSix NumPadSeven NumPadEight NumPadNine
Multiply Add Subtract Decimal Divide
LeftMouseButton RightMouseButton MiddleMouseButton ThumbMouseButton ThumbMouseButton2
MouseScrollUp MouseScrollDown
Gamepad_LeftX Gamepad_LeftY Gamepad_RightX Gamepad_RightY Gamepad_LeftTriggerAxis Gamepad_RightTriggerAxis
Gamepad_FaceButton_Bottom Gamepad_FaceButton_Right Gamepad_FaceButton_Left Gamepad_FaceButton_Top
Gamepad_LeftShoulder Gamepad_RightShoulder Gamepad_LeftTrigger Gamepad_RightTrigger
Gamepad_LeftThumbstick Gamepad_RightThumbstick Gamepad_Special_Left Gamepad_Special_Right
Gamepad_DPad_Up Gamepad_DPad_Down Gamepad_DPad_Left Gamepad_DPad_Right
""".split())

GAMEPAD_ALIASES = {
    "a": "Gamepad_FaceButton_Bottom", "cross": "Gamepad_FaceButton_Bottom",
    "b": "Gamepad_FaceButton_Right", "circle": "Gamepad_FaceButton_Right",
    "x": "Gamepad_FaceButton_Left", "square": "Gamepad_FaceButton_Left",
    "y": "Gamepad_FaceButton_Top", "triangle": "Gamepad_FaceButton_Top",
    "lb": "Gamepad_LeftShoulder", "l1": "Gamepad_LeftShoulder",
    "rb": "Gamepad_RightShoulder", "r1": "Gamepad_RightShoulder",
    "lt": "Gamepad_LeftTrigger", "l2": "Gamepad_LeftTrigger",
    "rt": "Gamepad_RightTrigger", "r2": "Gamepad_RightTrigger",
    "ls": "Gamepad_LeftThumbstick", "l3": "Gamepad_LeftThumbstick",
    "rs": "Gamepad_RightThumbstick", "r3": "Gamepad_RightThumbstick",
    "start": "Gamepad_Special_Right", "options": "Gamepad_Special_Right", "menu": "Gamepad_Special_Right",
    "back": "Gamepad_Special_Left", "select": "Gamepad_Special_Left", "view": "Gamepad_Special_Left",
    "dpad_up": "Gamepad_DPad_Up", "dpad_down": "Gamepad_DPad_Down",
    "dpad_left": "Gamepad_DPad_Left", "dpad_right": "Gamepad_DPad_Right",
}


def read_bindings(json_text):
    """Return {'keyboard': {action: key}, 'gamepad': {action: key}}; entries it can't read are left out.
    Raises LookupError when the save has no settings yet (an empty save, before the game has written any)."""
    doc = json.loads(json_text)
    account = next(iter(doc.values()), None)
    if not isinstance(account, dict) or not isinstance(account.get("Shared"), dict):
        raise LookupError("the save has no key bindings yet; start the game and reach the main menu once")
    shared = account["Shared"]
    out = {}
    for device, section in SECTIONS.items():
        out[device] = {}
        for action, value in shared.get(section, {}).items():
            parts = str(value).split(",")
            if len(parts) >= 3:
                out[device][action] = parts[2]
    return out


def key_of(change, name=None):
    """A controls.json entry is a key name; {"key": ...} objects from older studio versions also work.
    Anything else (null, a list, a number) is a ValueError that names the entry."""
    what = f"controls.json: {name}" if name else "controls.json"
    if isinstance(change, dict):
        if "key" not in change:
            raise ValueError(f"{what} needs a \"key\", like {{\"key\": \"F\"}}")
        change = change["key"]
    if not isinstance(change, str) or not change.strip():
        raise ValueError(f"{what} should be a key's name in quotes, like \"F\"")
    return change


DEVICES = ("keyboard", "gamepad", "keys", "menus")


def parse(raw):
    """controls.json as the build reads it: {"keyboard": {action: key}, "gamepad": {...}, "keys": {key: key},
    "menus": {key: key}}, with "menus"' {"keys": {...}} flattened so mods merge key by key, and every "_" key
    (a note) left out. What can't be read is a ValueError that says where, in words."""
    if not isinstance(raw, dict):
        raise ValueError('controls.json should be an object like {"keyboard": {"Player_Interact": "F"}}')
    out = {}
    for device, mapping in raw.items():
        if device.startswith("_"):
            continue
        if device not in DEVICES:
            raise ValueError(f"controls.json: '{device}' should be one of {', '.join(DEVICES)}")
        if not isinstance(mapping, dict):
            raise ValueError(f"controls.json: '{device}' should be an object like {{\"Player_Interact\": \"F\"}}"
                             if device != "menus" else 'controls.json: "menus" should look like {"keys": {"Escape": "BackSpace"}}')
        if device == "menus":
            extra = [k for k in mapping if k != "keys" and not k.startswith("_")]
            if extra or not isinstance(mapping.get("keys", {}), dict):
                raise ValueError('controls.json: "menus" should look like {"keys": {"Escape": "BackSpace"}}')
            mapping = mapping.get("keys", {})
        out[device] = {name: key_of(change, f"{device}: {name}") for name, change in mapping.items()
                       if not name.startswith("_")}
    return out


def normalise_key(device, key):
    k = str(key).strip()
    if device == "gamepad":
        k = GAMEPAD_ALIASES.get(k.lower(), k)
    if len(k) == 1 and k.isalpha():
        k = k.upper()
    return k


def apply(json_text, changes):
    """changes: {'keyboard': {action: key}, 'gamepad': {...}}. Returns (new_text, applied, warnings)."""
    current = read_bindings(json_text)
    applied, warnings = [], []
    text = json_text
    for device, mapping in changes.items():
        if device not in SECTIONS:
            warnings.append(f"unknown device '{device}' (use 'keyboard' or 'gamepad')")
            continue
        block = re.search(r'"%s":\s*\{[^{}]*\}' % SECTIONS[device], text)
        if not block:
            warnings.append(f"save has no {SECTIONS[device]} section")
            continue
        body = block.group()
        for action, change in mapping.items():
            if action not in current[device]:
                warnings.append(f"{device}: no action named {action} (known: {', '.join(current[device])})")
                continue
            new_key = normalise_key(device, key_of(change))
            if new_key not in KNOWN_KEYS:
                warnings.append(f"{device}: '{new_key}' is not a key name I recognise; using it anyway")
            pat = re.compile(r'("%s":\s*"\d+,%s,)([^,"]+)(,[^"]*")' % (re.escape(action), re.escape(action)))
            body, n = pat.subn(lambda m: m.group(1) + new_key + m.group(3), body)
            if n:
                applied.append((device, action, current[device][action], new_key))
        text = text[:block.start()] + body + text[block.end():]
    return text, applied, warnings
