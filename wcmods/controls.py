"""Button remapping through the bindings the game keeps in its save.

Each binding is stored as "<kind>,<Action>,<Key>,<Scale>.<flag>" under Shared.InputKeyboard
or Shared.InputGamepad, e.g. "0,Player_Interact,E,1.000000.1". Only the key part is changed.
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
MouseScrollUp MouseScrollDown MouseX MouseY
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
    """Return {'keyboard': {action: key}, 'gamepad': {action: key}}."""
    doc = json.loads(json_text)
    shared = next(iter(doc.values()))["Shared"]
    out = {}
    for device, section in SECTIONS.items():
        out[device] = {a: v.split(",")[2] for a, v in shared.get(section, {}).items()}
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
        for action, key in mapping.items():
            if action not in current[device]:
                warnings.append(f"{device}: no action named {action} (known: {', '.join(current[device])})")
                continue
            new_key = normalise_key(device, key)
            if new_key not in KNOWN_KEYS:
                warnings.append(f"{device}: '{new_key}' is not a key name I recognise; using it anyway")
            pat = re.compile(r'("%s":\s*"\d+,%s,)([^,"]+)(,[^"]*")' % (re.escape(action), re.escape(action)))
            body, n = pat.subn(lambda m: m.group(1) + new_key + m.group(3), body)
            if n:
                applied.append((device, action, current[device][action], new_key))
        text = text[:block.start()] + body + text[block.end():]
    return text, applied, warnings
