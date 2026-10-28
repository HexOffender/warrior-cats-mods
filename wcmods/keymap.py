"""Unreal key names to Windows key codes, and the remap plans: the in-game remap script's (gameremap.py)
and the key remapper's (remapper.py).

The game ignores edited bindings (see docs/remapping.md), so it always listens for its own
keys. Each key it hears is sent on to its listeners as the game's commands (KEY_COMMANDS: Interact,
Pounce, and the menus' Up, Confirm, Back...). Inside the game, a remap works on those commands: the
in-game script sends a command when its new key is pressed, and drops the game's own when it comes
from the old key (native_plan), in play and in menus. Movement and the camera are axes, which it
can't move; those are left to the key remapper outside the game, where a remap is "when I press F,
send the game E": it holds back F and sends E in its place. Actions in controls.json are turned into
such key pairs using the game's bindings below; the "keys" section maps keys directly (e.g. W, which
no action lists). Both apply while you play. The "menus" section is a separate set of key pairs used
only while a menu is open.

Every warning is a sentence for the person who made the remap (the Apply drawer shows them, and describe()
puts them on the Controls page's rows): commands by their names in NAMES, keys by label().
"""
from .controls import GAMEPAD_ALIASES, KNOWN_KEYS, normalise_key

# What the game listens for on the keyboard (from the save; edits to it are ignored). Axis actions
# list their negative key; the positive ones (W, D, Up, Right) are built in. The save puts Pause on
# Enter, but the game pauses on Escape (Enter confirms), so that one is the game's.
GAME_KEYBOARD = {
    "Player_Movement_Up": "S", "Player_Movement_Right": "A", "Player_Camera_Up": "Down",
    "Player_Camera_Right": "Left", "Player_Pounce": "SpaceBar", "Player_Drop": "C",
    "Player_Den_Place": "X", "Player_Interact": "E", "Player_ReturnToCamp": "X",
    "Player_Friend_Talk": "C", "Player_Crouch": "LeftControl", "Player_Scent_Tracking": "Q",
    "Player_Camera_Reset": "R", "Player_Run": "LeftShift", "Player_Pause": "Escape",
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
# Every command each key and mouse button sends to the game's listeners, seen in game with each one
# pressed on its own (2026-10-27, build 26184573; the same in play, the pause menu and a fight). Keys not
# listed send none. In menus, mouse presses go to the button under the cursor instead.
KEY_COMMANDS = {
    "W": ["Button_Up"], "S": ["Button_Down"], "A": ["Button_Left", "AnimTool_PreviousAnim"],
    "D": ["Button_Right", "AnimTool_NextAnim"],
    "Up": ["Button_Up"], "Down": ["Button_Down"], "Left": ["Button_Left"], "Right": ["Button_Right"],
    "Enter": ["Button_A", "Button_Confirm", "Button_Skip"], "BackSpace": ["Button_B", "Button_Back"],
    "Escape": ["Player_Pause"],
    "SpaceBar": ["Button_Y", "Player_Pounce", "Player_PhotoMode_Shoot", "AnimTool_PlayLoopAnim"],
    "E": ["Button_X", "Player_Interact"], "C": ["Player_Friend_Talk", "Player_Drop"],
    "X": ["Player_ReturnToCamp", "Player_Den_Place", "Player_PhotoMode_Exit", "AnimTool_StopAnim"],
    "Q": ["Player_Scent_Tracking", "Player_PhotoMode_HideUI"], "R": ["Button_Randomize", "Player_Camera_Reset"],
    "I": ["Player_Show_Inventory", "Minigame_Button_A"], "J": ["Player_Play", "Minigame_Button_X"],
    "K": ["Player_Show_Quest", "Minigame_Button_B"], "L": ["Player_Growl", "Minigame_Button_Y"],
    "M": ["Player_Show_Map"], "P": ["Button_Start"], "T": ["Button_StickR"], "V": ["Button_Select"],
    "One": ["Button_ShoulderL"], "Two": ["Button_ShoulderR"], "Three": ["Button_TriggerL"],
    "Four": ["Button_TriggerR"],
    "LeftShift": ["Player_Run", "AnimTool_PlayAnim"], "RightShift": ["Player_Run"],
    "LeftControl": ["Player_Crouch"], "RightControl": ["Player_Crouch"],
    "LeftMouseButton": ["Button_Confirm", "Player_Interact"], "RightMouseButton": ["Player_Crouch"],
}
# The game's commands (its ECommands enum), less the axes and its developer tools: the ones controls.json
# can put on a key.
COMMANDS = tuple("""
Button_Up Button_Down Button_Right Button_Left Button_A Button_B Button_X Button_Y Button_ShoulderL
Button_ShoulderR Button_TriggerL Button_TriggerR Button_StickL Button_StickR Button_StickL_Up
Button_StickL_Down Button_StickL_Right Button_StickL_Left Button_StickR_Up Button_StickR_Down
Button_StickR_Right Button_StickR_Left Button_Select Button_Start Button_Back Button_Confirm
Button_Randomize Button_Skip Player_Interact Player_ReturnToCamp Player_Friend_Talk Player_Den_Place
Player_Play Player_Run Player_Crouch Player_Pounce Player_Drop Player_Show_Map Player_Show_Inventory
Player_Show_Quest Player_Scent_Tracking Player_Camera_Reset Player_Growl Player_PhotoMode_Camera_Crane_Up
Player_PhotoMode_Camera_Crane_Down Player_PhotoMode_Shoot Player_PhotoMode_Exit Player_PhotoMode_HideUI
Player_Pause Minigame_Button_X Minigame_Button_Y Minigame_Button_A Minigame_Button_B Player_Cinematic_Skip
Player_ShowHideControls
""".split())
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

# The game's commands and jobs in plain words: [its name, what a key that does it does]. The name is the
# Controls page's row label; the second is for sentences ("F does Interact", "Enter opens the pause menu").
# "key:W" and the axis actions are the moving jobs, which only the key remapper outside the game can move.
# None: a developer's tool of the game's, never said.
NAMES = {
    "Player_Interact": ["Interact", "does Interact"], "Player_Pounce": ["Pounce", "pounces"],
    "Player_Run": ["Run", "runs"], "Player_Crouch": ["Crouch", "crouches"],
    "Player_Scent_Tracking": ["Scent tracking", "tracks scents"], "Player_Drop": ["Drop", "drops what you carry"],
    "Player_Friend_Talk": ["Talk to a friend", "talks to a friend"],
    "Player_Den_Place": ["Place a den decoration", "places a den decoration"],
    "Player_ReturnToCamp": ["Return to camp", "takes you back to camp"],
    "Player_Camera_Reset": ["Reset the camera", "resets the camera"],
    "Player_Pause": ["Pause menu", "opens the pause menu"],
    "Player_Show_Inventory": ["Inventory", "opens the inventory"], "Player_Show_Quest": ["Quest log", "opens the quest log"],
    "Player_Show_Map": ["Map", "opens the map"], "Player_Growl": ["Meow", "meows"],
    "Player_Play": ["Play", "does the game's Play action"],
    "Player_PhotoMode_Shoot": ["Take a photo", "takes a photo in photo mode"],
    "Player_PhotoMode_Exit": ["Leave photo mode", "leaves photo mode"],
    "Player_PhotoMode_HideUI": ["Hide photo mode's buttons", "hides photo mode's buttons"],
    "Player_PhotoMode_Camera_Crane_Up": ["Photo mode's camera up", "raises photo mode's camera"],
    "Player_PhotoMode_Camera_Crane_Down": ["Photo mode's camera down", "lowers photo mode's camera"],
    "Player_Cinematic_Skip": ["Skip a cutscene", "skips cutscenes"],
    "Player_ShowHideControls": ["Show or hide the controls", "shows or hides the controls"],
    "Button_Up": ["Up", "moves up in menus"], "Button_Down": ["Down", "moves down in menus"],
    "Button_Left": ["Left", "moves left in menus"], "Button_Right": ["Right", "moves right in menus"],
    "Button_A": ["Confirm", "confirms in menus"], "Button_Confirm": ["Confirm", "confirms in menus"],
    "Button_Skip": ["Skip", "skips dialogue"], "Button_B": ["Back", "goes back in menus"],
    "Button_Back": ["Back", "goes back in menus"], "Button_X": ["the map's legend", "shows the map's legend"],
    "Button_Y": ["the menus' Y button", "does the menus' Y button"],
    "Button_Randomize": ["Randomize", "randomizes in the cat maker"],
    "Button_Start": ["the game's Start button", "does the game's Start button"],
    "Button_Select": ["the game's Select button", "does the game's Select button"],
    "Button_StickL": ["the left stick's click", "does the left stick's click"],
    "Button_StickR": ["the right stick's click", "does the right stick's click"],
    "Button_ShoulderL": ["Previous tab", "goes to the previous tab"], "Button_ShoulderR": ["Next tab", "goes to the next tab"],
    "Button_TriggerL": ["Previous page", "goes to the previous page of a tab"],
    "Button_TriggerR": ["Next page", "goes to the next page of a tab"],
    "Minigame_Button_A": ["a minigame's button", "presses a minigame's button"],
    "Minigame_Button_B": ["a minigame's button", "presses a minigame's button"],
    "Minigame_Button_X": ["a minigame's button", "presses a minigame's button"],
    "Minigame_Button_Y": ["a minigame's button", "presses a minigame's button"],
    "Player_Movement_Up": ["Move back", "moves you back"], "Player_Movement_Right": ["Move left", "moves you left"],
    "Player_Camera_Up": ["Camera down", "moves the camera down"], "Player_Camera_Right": ["Camera left", "moves the camera left"],
    "key:W": ["Move forward", "moves you forward"], "key:D": ["Move right", "moves you right"],
    "key:Up": ["Camera up", "moves the camera up"], "key:Right": ["Camera right", "moves the camera right"],
    "AnimTool_PreviousAnim": None, "AnimTool_NextAnim": None, "AnimTool_PlayLoopAnim": None, "AnimTool_StopAnim": None,
    "AnimTool_PlayAnim": None,
}
for _d in ("L", "R"):
    for _way in ("Up", "Down", "Left", "Right"):
        NAMES[f"Button_Stick{_d}_{_way}"] = [f"the {'left' if _d == 'L' else 'right'} stick {_way.lower()}",
                                             f"pushes the {'left' if _d == 'L' else 'right'} stick {_way.lower()} in menus"]
# The job each movement key does (the game reads them itself, every frame).
AXIS_JOB = {"W": "key:W", "S": "Player_Movement_Up", "A": "Player_Movement_Right", "D": "key:D",
            "Up": "key:Up", "Down": "Player_Camera_Up", "Left": "Player_Camera_Right", "Right": "key:Right"}

# Keys by the names a player knows them by, for sentences: Space, Left Shift, 1, Mouse 4, the controller's A.
# Controller buttons are named as on an Xbox pad (the page shows PlayStation and Switch names too).
_LABELS = {
    "SpaceBar": "Space", "LeftShift": "Left Shift", "RightShift": "Right Shift", "LeftControl": "Left Ctrl",
    "RightControl": "Right Ctrl", "LeftAlt": "Left Alt", "RightAlt": "Right Alt", "BackSpace": "Backspace",
    "CapsLock": "Caps Lock", "PageUp": "Page Up", "PageDown": "Page Down", "Up": "the up arrow",
    "Down": "the down arrow", "Left": "the left arrow", "Right": "the right arrow", "Tilde": "`", "Hyphen": "-",
    "Equals": "=", "LeftBracket": "[", "RightBracket": "]", "Backslash": "\\", "Semicolon": ";", "Apostrophe": "'",
    "Comma": ",", "Period": ".", "Slash": "/", "Multiply": "Num *", "Add": "Num +", "Subtract": "Num -",
    "Decimal": "Num .", "Divide": "Num /",
    "LeftMouseButton": "the left mouse button", "RightMouseButton": "the right mouse button",
    "MiddleMouseButton": "the middle mouse button", "ThumbMouseButton": "Mouse 4", "ThumbMouseButton2": "Mouse 5",
    "MouseScrollUp": "the wheel up", "MouseScrollDown": "the wheel down",
    "Gamepad_FaceButton_Bottom": "the controller's A", "Gamepad_FaceButton_Right": "the controller's B",
    "Gamepad_FaceButton_Left": "the controller's X", "Gamepad_FaceButton_Top": "the controller's Y",
    "Gamepad_LeftShoulder": "the controller's LB", "Gamepad_RightShoulder": "the controller's RB",
    "Gamepad_LeftTrigger": "the controller's LT", "Gamepad_RightTrigger": "the controller's RT",
    "Gamepad_Special_Left": "the controller's View button", "Gamepad_Special_Right": "the controller's Menu button",
    "Gamepad_LeftThumbstick": "the left stick's click", "Gamepad_RightThumbstick": "the right stick's click",
    "Gamepad_DPad_Up": "the D-pad's up", "Gamepad_DPad_Down": "the D-pad's down",
    "Gamepad_DPad_Left": "the D-pad's left", "Gamepad_DPad_Right": "the D-pad's right",
    "Gamepad_LeftX": "the left stick", "Gamepad_LeftY": "the left stick", "Gamepad_RightX": "the right stick",
    "Gamepad_RightY": "the right stick", "Gamepad_LeftTriggerAxis": "the controller's LT",
    "Gamepad_RightTriggerAxis": "the controller's RT",
}


def label(key):
    """A key as a player knows it: "Space", "1", "Num 5", "Mouse 4", "the controller's A"."""
    if key in _LABELS:
        return _LABELS[key]
    if key in DIGITS:
        return str(DIGITS.index(key))
    if key.startswith("NumPad") and key[6:] in DIGITS:
        return f"Num {DIGITS.index(key[6:])}"
    return key


def say(command):
    """A command or job by its name ("Interact", "Inventory"); one NAMES doesn't know, by its words."""
    return (NAMES.get(command) or [command.replace("_", " ")])[0]


def does(command):
    """What a key doing the command does, for a sentence: "opens the inventory"."""
    found = NAMES.get(command)
    return found[1] if found else f"does {command.replace('_', ' ')}"


def _and(words):
    words = list(dict.fromkeys(w for w in words if w))   # in order, each once
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1] if words else ""


def _cap(text):
    return text[:1].upper() + text[1:]


def jobs(commands):
    """The commands a key sends, each said once ("confirms in menus and skips dialogue"); the game's
    developer tools left out."""
    return _and(does(c) for c in commands if NAMES.get(c, True) is not None)


class Note(str):
    """A warning, in plain words, that knows which controls.json entries it's about: rows, a list of
    (section, name), section "keyboard", "gamepad", "keys" or "menus" and name an action or a pressed key.
    line_says: the rows' own line (describe) already says it, so Apply says it and the rows don't, twice."""

    def __new__(cls, text, rows=(), line_says=False):
        note = super().__new__(cls, text)
        note.rows = [tuple(r) for r in rows if r]
        note.line_says = line_says
        return note


def game_keys():
    """The game's own keys as the build knows them (one home for the studio's Controls page, which shows them
    as each action's key, and for sentences about them): its keyboard actions with the Controls screen's
    (Pause on Escape, whatever the save says), its controller buttons, the moving keys, what each key sends,
    the controller's short names, and the names of the game's commands."""
    return {"keyboard": {**GAME_KEYBOARD, **SCREEN_KEYBOARD}, "gamepad": dict(GAME_GAMEPAD),
            "built_in": list(BUILT_IN_KEYS), "axes": list(AXES), "axis_keys": list(AXIS_KEYS),
            "commands": {k: list(v) for k, v in KEY_COMMANDS.items()}, "aliases": dict(GAMEPAD_ALIASES),
            "names": {c: list(n) for c, n in NAMES.items() if n}}


def _key(name):
    return normalise_key("keyboard", name)


def _old_keys(device, action):
    """The keys an action is on in the game: the Controls screen's one, or every key that sends it.
    Second keys the game has for an action (Right Shift for Run) keep working when it moves."""
    if device == "gamepad":
        return [GAME_GAMEPAD[action]] if action in GAME_GAMEPAD else []
    primary = {**GAME_KEYBOARD, **SCREEN_KEYBOARD}
    if action in primary:
        return [primary[action]]
    return [k for k, commands in KEY_COMMANDS.items() if action in commands]


DIGITS = ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine")
LAUNCHER = "Play with key remaps.bat"
STEAM = "change it in Steam's controller settings (right-click the game in Steam, then Properties, Controller)"


def _stick(action):
    return "the left stick" if action.startswith("Player_Movement") else "the right stick"


def _native(device, key):
    """What a key does in the game on its own: the commands it sends (a controller button, its actions)."""
    if device == "gamepad":
        return [a for a, k in GAME_GAMEPAD.items() if k == key and a not in AXES]
    return [c for c in KEY_COMMANDS.get(key, []) if not c.startswith(("AnimTool_", "Minigame_"))]


def native_plan(merged):
    """What the in-game remap script (gameremap.py) does with controls.json merged across mods, and what's
    left for the key remapper outside the game.

    Returns (plan, rest, warnings). plan is {"play": {"send": ..., "drop": ...}, "menu": {...},
    "keys": {action: [key, ...]}, "icons": {"play": ..., "menu": ...}}. In each, send is {key: [command,
    ...]}: pressing the key sends those commands; drop is {command: [key, ...]}: the game's own command is
    dropped when it comes from one of those keys. "play" applies while you explore (the controller and the
    HUD), "menu" in the game's menus (any other screen). keys says where each changed action is now; icons
    is {command: [key, ...]}, the keys the game's pictures of that command's key show instead of its own.
    rest is controls.json with only what the
    script can't do (movement and the camera, keys standing for them or for keys that send nothing, mouse
    buttons in menus, and menu pairs standing for the arrows or WASD, which the map reads itself), for
    plan and menu_plan. warnings are Notes: sentences that know the entries they're about.
    """
    plans = {"play": ({}, {}), "menu": ({}, {})}
    rest, warnings, setters, moved = {}, [], {}, set()

    def warn(text, *rows, line_says=False):
        warnings.append(Note(text, rows, line_says))

    def send(where, key, command, setter):
        out = plans[where][0].setdefault(key, [])
        if command not in out:
            out.append(command)
        setters.setdefault((where, key), set()).add(setter)

    def drop(where, command, key):
        out = plans[where][1].setdefault(command, [])
        if key not in out:
            out.append(key)

    # Moving an action, or any of the game's commands: everywhere, in play and in menus.
    landed = []   # actions moved onto Enter or BackSpace, which still confirm or go back in menus
    for device in ("keyboard", "gamepad"):
        for action, key in merged.get(device, {}).items():
            row = (device, action)
            known = COMMANDS if device == "keyboard" else GAME_GAMEPAD
            if action in AXES or action not in known:
                if device == "keyboard":
                    rest.setdefault("keyboard", {})[action] = key   # plan() moves it, or says it doesn't know it
                elif action in AXES:
                    if normalise_key(device, key) != GAME_GAMEPAD[action]:   # the game's own stick: nothing to do
                        warn(f"{_cap(_stick(action))} can't be moved by a mod; {STEAM}", row)
                elif action in COMMANDS:
                    warn(f"{say(action)} has no controller button in the game, so a mod can't put it on one", row)
                else:
                    warn(f"The controller has no action called \"{action}\"; it has "
                         f"{_and(say(a) for a in GAME_GAMEPAD if a not in AXES)}", row)
                continue
            new = normalise_key(device, key)
            if new not in BUTTONS:
                warn(f"{say(action)}: the game has no key or button called \"{new}\"", row)
                continue
            old = _old_keys(device, action)
            if old == [new]:
                continue
            if not old:
                warn(f"No key does {say(action)} in the game; {label(new)} will", row)
            moved.add(row)
            for where in plans:
                send(where, new, action, row)
                for k in old:
                    if k != new:
                        drop(where, action, k)
            if new in AXIS_KEYS:
                warn(f"{_cap(label(new))} now {does(action)}, and still {does(AXIS_JOB[new])} too: the game reads "
                     f"that key itself", row)
            if device == "keyboard" and new in ("Enter", "BackSpace"):
                landed.append((row, new, action))
    # Moves that change what a menu key or the pause key does, which nothing else on screen would say: a mod
    # made with the studio's old "Keyboard defaults" button put Pause on Enter. The row's own line says the
    # same (_move_line), so these are for Apply.
    for row, new, action in landed:
        text = f"{_cap(label(new))} now {does(action)}, in menus as well, and still {jobs(_native('keyboard', new))}"
        if action == "Player_Pause":
            text += "; Escape will no longer open the pause menu"
        warn(text, row, line_says=True)
    if ("keyboard", "Player_Pause") in moved and not any(a == "Player_Pause" for _, _, a in landed):
        warn("Escape will no longer open the pause menu", ("keyboard", "Player_Pause"), line_says=True)
    # The key that takes an action stops doing the actions the game has on it, unless they move too.
    own = {"keyboard": {**GAME_KEYBOARD, **SCREEN_KEYBOARD}, "gamepad": GAME_GAMEPAD}
    for key, commands in list(plans["play"][0].items()):
        lost = []
        for device, table in own.items():
            for action, k in table.items():
                if k == key and action not in commands and action not in AXES and (device, action) not in moved:
                    for where in plans:
                        drop(where, action, key)
                    lost.append(action)
        if lost:
            what = "button" if key.startswith("Gamepad_") else "key"
            warn(f"{_cap(label(key))} now {jobs(commands)}, so it no longer {_and(does(a) for a in lost)}; give "
                 f"{_and(say(a) for a in lost)} another {what}", *sorted(setters[("play", key)]))
    # A key that stands for another: while you play ("keys") or in menus ("menus"). It sends that key's
    # commands and stops sending its own, as with the key remapper outside the game.
    for section, where in (("keys", "play"), ("menus", "menu")):
        for src, dst in merged.get(section, {}).items():
            row = (section, src)
            s, d = _key(src), _key(dst)
            commands = KEY_COMMANDS.get(d, [])
            if (s not in BUTTONS or not commands or (where == "play" and d in AXIS_KEYS)
                    or (where == "menu" and s in MOUSE)):
                rest.setdefault(section, {})[src] = dst   # for the key remapper outside the game
                continue
            if s == d:
                continue
            for command in commands:
                send(where, s, command, row)
            for command in KEY_COMMANDS.get(s, []):
                if command not in commands:
                    drop(where, command, s)
            # What the pressed key stops doing there: its actions while you explore, its menu jobs in menus
            # (Backspace standing for Enter no longer goes back). The row's line says it too (_pair_line). A
            # menus pair for an arrow or WASD key goes to the key remapper as well, whose plan says it.
            lost = _pair_lost(s, d, where)
            if lost and where == "play":
                warn(f"{_cap(label(s))} now does what {label(d)} does while you explore, so it no longer "
                     f"{_and(does(c) for c in lost)}", row, line_says=True)
            elif lost and d not in AXIS_KEYS:
                warn(f"In menus, {label(s)} now does what {label(d)} does, so it no longer {jobs(lost)}", row,
                     line_says=True)
            if where == "play" and s in AXIS_KEYS:
                warn(f"{_cap(label(s))} now does what {label(d)} does while you explore, and still "
                     f"{does(AXIS_JOB[s])} too: the game reads that key itself", row)
            if where == "menu" and d in AXIS_KEYS:
                # The map zooms and moves on those keys by reading them itself: only the key remapper can
                # do that part. With it running it holds the key back, so the game sees d.
                rest.setdefault("menus", {})[src] = dst
                warn(f"In menus, {label(s)} moves as {label(d)} does, but zooming and moving the map with it works "
                     f"only when the game is started with {LAUNCHER}", row)
            elif where == "menu" and (len(s) == 1 or s in DIGITS or s == "SpaceBar"):
                warn(f"In menus, {label(s)} still types on the name screen, and does {label(d)}'s job there too", row)
    for (where, key), who in sorted(setters.items()):
        # A move shows in both play and menus; say so once.
        if len(who) > 1 and (where == "play" or any(w[0] == "menus" for w in who)):
            warn(f"{_cap(label(key))} is set for {_and(say(c) for c in plans[where][0][key])}; it does all of them",
                 *sorted(who))
    outside = {}
    for src in rest.get("keys", {}):
        outside.setdefault(_key(src), []).append(("keys", src))
    for action, key in rest.get("keyboard", {}).items():
        outside.setdefault(_key(key), []).append(("keyboard", action))
    for key in sorted(set(outside) & set(plans["play"][0])):
        warn(f"{_cap(label(key))} is set both for {_and(say(c) for c in plans['play'][0][key])} and for a change "
             f"only {LAUNCHER} makes (moving you or the camera); use another key for one of them",
             *(sorted(setters[("play", key)]) + outside[key]))
    # Where each of the game's actions that changed is now, for scripts that listen for it themselves.
    play_send, play_drop = plans["play"]
    keys = {}
    for action in sorted({c for cs in play_send.values() for c in cs} | set(play_drop)):
        if not action.startswith("Player_"):
            continue
        found = (_old_keys("keyboard", action) + [k for k, cs in play_send.items() if action in cs]
                 + [k for k, cs in KEY_COMMANDS.items() if action in cs] + _old_keys("gamepad", action))
        dropped = play_drop.get(action, [])
        keys[action] = [k for i, k in enumerate(found) if k not in dropped and k not in found[:i]]
    plan = {where: {"send": sends, "drop": drops} for where, (sends, drops) in plans.items()}
    plan["keys"] = keys
    # The keys the game's key pictures (prompts, footers, the Controls tab) show for each command that has a
    # new one: moved actions first, then keys standing for others. The script shows the first with a
    # picture in the same set as the game's (the keyboard's, or the controller's).
    plan["icons"] = {}
    for where, (sends, _) in plans.items():
        icons = plan["icons"][where] = {}
        for key, commands in sends.items():
            for command in commands:
                icons.setdefault(command, []).append(key)
    return plan, rest, warnings


def plan(merged):
    """merged: controls.json merged across mods: {"keyboard": {action: key}, "keys": {key: key}}.

    Returns (send, block, warnings). send maps a key you press to the game key it stands for. block
    holds game keys that no longer do anything, because their action moved and nothing else uses them.
    warnings are Notes, said for the key remapper outside the game (Play with key remaps.bat).
    """
    send, moved_from, warnings, by, left = {}, {}, [], {}, {}
    # What you press for each of the game's jobs: its actions, plus the built-in keys, which count as
    # jobs of their own (moving W to T should stop W moving you, the same as moving an action).
    game_key = dict(GAME_KEYBOARD, **{f"key:{k}": k for k in BUILT_IN_KEYS})
    pressed = dict(game_key)

    def warn(text, *rows):
        warnings.append(Note(text, rows))

    def move(new, old, row):
        if new == old:
            return
        if new in send and send[new] != old:
            warn(f"With {LAUNCHER}, {label(new)} is set for more than one key; it stands for {label(old)}",
                 by[new], row)
        send[new] = old
        by[new] = row
        moved_from.setdefault(old, []).append(row)

    for action, key in merged.get("keyboard", {}).items():
        row = ("keyboard", action)
        if action not in GAME_KEYBOARD:
            if action in COMMANDS:
                warn(f"{say(action)} moves only with the script loader (Get set up, on the Mods page, installs it)", row)
            else:
                warn(f"There's no action called \"{action}\"", row)
            continue
        new = _key(key)
        if new not in VK and new not in MOUSE:
            warn(f"{say(action)}: {LAUNCHER} can't use {label(new)}", row)
            continue
        pressed[action] = new
        move(new, GAME_KEYBOARD[action], row)
    for src, dst in merged.get("keys", {}).items():
        row = ("keys", src)
        s, d = _key(src), _key(dst)
        if s not in VK and s not in MOUSE:
            warn(f"{LAUNCHER} can't use {label(s)}", row)
            continue
        if d not in VK:
            warn(f"{_cap(label(s))} can only stand for a keyboard key, not {label(d)}", row)
            continue
        if d in BUILT_IN_KEYS:
            pressed[f"key:{d}"] = s
        # Any other game key keeps working on its own key too, unless its action moves.
        move(s, d, row)
    pads = [("gamepad", a) for a, k in merged.get("gamepad", {}).items()
            if normalise_key("gamepad", k) != GAME_GAMEPAD.get(a)]
    if pads:
        warn(f"Without the script loader, controller buttons can't change: {LAUNCHER} is keyboard and mouse only "
             "(Get set up, on the Mods page, installs the loader)", *pads)
    # What a key you press stops doing when it stands for another: the jobs on it (its actions, the moving
    # keys), and the game's other commands it sends, such as Inventory on I.
    for job, key in pressed.items():
        if key in send and send[key] != game_key[job]:
            left.setdefault(key, []).append(job)
    for key in send:
        for command in KEY_COMMANDS.get(key, []):
            if (command.startswith("Player_") and command not in pressed
                    and command not in KEY_COMMANDS.get(send[key], [])):
                left.setdefault(key, []).append(command)
    for key, lost in left.items():
        warn(f"With {LAUNCHER}, {label(key)} stands for {label(send[key])}, so it no longer "
             f"{_and(does(j) for j in lost)}", by[key])
    in_use = set(pressed.values()) | set(send)
    block = {k for k in moved_from if k not in in_use}
    for key in sorted(block & set(NEVER_HELD_BACK)):
        warn(f"With {LAUNCHER}, {label(key)} keeps its old job too: prompts and dialogue shown while you play may "
             "need it", *moved_from[key])
    for key in sorted(set(send) & set(NEVER_HELD_BACK)):
        warn(f"With {LAUNCHER}, {label(key)} stands for {label(send[key])} while you play, so prompts and dialogue "
             f"shown then won't get {label(key)}", by[key])
    return send, block - set(NEVER_HELD_BACK), warnings


def menu_plan(merged):
    """The "menus" section, {key you press: game key}, used only while a menu is open.

    Returns (send, warnings). Only the key you press is held back in menus (it does the game key's job
    instead of its own, which is said): the game's key keeps working too, and no key is blocked.
    """
    send, warnings = {}, []
    for src, dst in merged.get("menus", {}).items():
        row = [("menus", src)]
        s, d = _key(src), _key(dst)
        if s not in VK and s not in MOUSE:
            warnings.append(Note(f"In menus, {LAUNCHER} can't use {label(s)}", row))
        elif d not in VK:
            warnings.append(Note(f"In menus, {label(s)} can only stand for a keyboard key, not {label(d)}", row))
        elif s != d:
            send[s] = d
            lost = [] if s in MOUSE else _pair_lost(s, d, "menu")   # it holds s back, so s's own jobs go
            if lost:
                warnings.append(Note(f"In menus, with {LAUNCHER}, {label(s)} stands for {label(d)}, so it no longer "
                                     f"{jobs(lost)}", row))
            if len(s) == 1 or s in DIGITS or s == "SpaceBar":
                warnings.append(Note(f"In menus, with {LAUNCHER}, typing {label(s)} on the name screen sends "
                                     f"{label(d)} instead", row))
    return send, warnings


def describe(merged, in_game=True, reserved=None):
    """What the build will do with controls.json merged across mods, said entry by entry: for the Controls
    page, before Apply, in the same words Apply uses. in_game: whether the script loader is there (without
    it, everything goes to the key remapper outside the game, as sections.controls.split does). reserved:
    {key: {"does", "from"}}, keys that wcmods or a mod listens on itself (sections.controls.keys_in_use).

    Returns {"rows": {section: {name: row}}, "lost": {device: {action: sentence}}, "lines": [...],
    "warnings": [...], "launcher": bool}. section is "keyboard" or "gamepad" (name an action) or "keys" or
    "menus" (name the key you press). Each row is {"key", "status", "line", "notes"}: status "game" (Apply
    puts it in the game), "launcher" (it works only when the game is started with Play with key remaps.bat),
    "cannot" (nothing will do it; notes say why) or "same" (the game's own key: nothing changes); line says
    what happens, notes are the warnings about it (not those the line already says). lost: the game's actions
    that stay on their key in the file but stop working there because another change took it (Crouch, when
    Run moves onto the controller's LT), and under "menus", {key: sentence} for each key a menus pair takes
    from its own jobs in menus (Backspace standing for Enter no longer goes back). lines are the warnings
    about no entry; warnings all of them, as Apply says them; launcher whether anything needs Play with key
    remaps.bat.
    """
    if in_game:
        native, rest, notes = native_plan(merged)
    else:
        native, rest, notes = None, merged, []
    send, block, plan_notes = plan(rest)
    menu_send, menu_notes = menu_plan(rest)
    notes = list(notes) + plan_notes + menu_notes
    play = native["play"] if native else {"send": {}, "drop": {}}
    menu = native["menu"] if native else {"send": {}, "drop": {}}
    rows = {"keyboard": {}, "gamepad": {}, "keys": {}, "menus": {}}

    def put(section, name, key, status, line=""):
        rows[section][name] = {"key": key, "status": status, "line": line, "notes": []}

    for device in ("keyboard", "gamepad"):
        for action, key in merged.get(device, {}).items():
            new = normalise_key(device, key)
            if device == "gamepad" and action in AXES:
                if new == GAME_GAMEPAD[action]:
                    put(device, action, new, "same")
                else:
                    put(device, action, new, "cannot", f"{_cap(_stick(action))} can't be moved by a mod; {STEAM}.")
            elif _old_keys(device, action) == [new]:
                put(device, action, new, "same")
            elif action in play["send"].get(new, []):
                put(device, action, new, "game", _move_line(device, action, new, play))
            elif device == "keyboard" and action in GAME_KEYBOARD and send.get(new) == GAME_KEYBOARD[action]:
                put(device, action, new, "launcher",
                    f"{_cap(label(new))} {does(action)} when the game is started with {LAUNCHER}.")
            else:
                put(device, action, new, "cannot")
    for src, dst in merged.get("keys", {}).items():
        s, d = _key(src), _key(dst)
        if s == d:
            put("keys", src, s, "same")
        elif src not in rest.get("keys", {}) and s in play["send"]:
            put("keys", src, s, "game", _pair_line(s, d, while_you="explore"))
        elif send.get(s) == d:
            what = does(AXIS_JOB[d]) if d in AXIS_JOB else f"does what {label(d)} does"
            put("keys", src, s, "launcher", f"{_cap(label(s))} {what} while you explore, when the game is started "
                                            f"with {LAUNCHER}.")
        else:
            put("keys", src, s, "cannot")
    for src, dst in merged.get("menus", {}).items():
        s, d = _key(src), _key(dst)
        if s == d:
            put("menus", src, s, "same")
        elif s in menu["send"] and (src not in rest.get("menus", {}) or d in AXIS_KEYS):
            put("menus", src, s, "game", _pair_line(s, d))
        elif menu_send.get(s) == d:
            put("menus", src, s, "launcher", f"In menus, {label(s)} does what {label(d)} does when the game is "
                                             f"started with {LAUNCHER}.")
        else:
            put("menus", src, s, "cannot")
    # The game's actions that keep their key, but lose it to another change: said on their own rows.
    lost = {"keyboard": {}, "gamepad": {}}
    for device, table in (("keyboard", {**GAME_KEYBOARD, **SCREEN_KEYBOARD}), ("gamepad", GAME_GAMEPAD)):
        what = "button" if device == "gamepad" else "key"
        for action, k in table.items():
            mine = merged.get(device, {}).get(action)
            if action in AXES or (mine is not None and normalise_key(device, mine) != k):
                continue   # a stick, or moved elsewhere: its own row says where
            if k in play["drop"].get(action, []):
                now = play["send"].get(k, [])
                lost[device][action] = (f"{_cap(label(k))} no longer {does(action)}" + (f": it {jobs(now)} now" if now else "")
                                        + f". Give {say(action)} another {what}.")
            elif device == "keyboard" and k in send and send[k] != k:
                lost[device][action] = (f"With {LAUNCHER}, {label(k)} stands for {label(send[k])}, so it no longer "
                                        f"{does(action)}. Give {say(action)} another key.")
    # The keys a menus pair takes from their own jobs in menus (Backspace standing for Enter no longer goes
    # back): said on the In menus card, by the key.
    lost["menus"] = {}
    working = {src: _key(merged["menus"][src]) for src, row in rows["menus"].items() if row["status"] in ("game", "launcher")}
    for src, d in working.items():
        s = _key(src)
        gone = [] if s in MOUSE else _pair_lost(s, d, "menu")
        if gone:
            how = (f"in menus it does what {label(d)} does now" if rows["menus"][src]["status"] == "game"
                   else f"with {LAUNCHER} it stands for {label(d)} there")
            # Another key standing for one that does them (U for Enter) already does: no advice for those.
            done = {c for other, k in working.items() if other != src for c in KEY_COMMANDS.get(k, [])}
            missing = [c for c in gone if c not in done]
            lost["menus"][s] = (f"{_cap(label(s))} no longer {jobs(gone)}: {how}."
                                + (f" Give {_and(say(c) for c in missing)} another key." if missing else ""))
    # Keys that wcmods or a mod listens on itself do their own job too, whatever the game does.
    for section, found in rows.items():
        for name, row in found.items():
            taken = (reserved or {}).get(row["key"])
            if taken and row["status"] in ("game", "launcher"):
                notes.append(Note(f"{_cap(label(row['key']))} also {taken['does']} ({taken['from']}), and will do "
                                  "both; pick another key", [(section, name)]))
    lines = []
    for note in notes:
        placed = [r for r in note.rows if r[1] in rows.get(r[0], {})]
        if placed and getattr(note, "line_says", False):
            continue   # the rows' own line says it; Apply says it from "warnings"
        for section, name in placed:
            row = rows[section][name]
            if row["line"].rstrip(".") != note and str(note) not in row["notes"]:
                row["notes"].append(str(note))
        if not placed:
            lines.append(str(note))
    return {"rows": rows, "lost": lost, "lines": lines, "warnings": [str(n) for n in notes],
            "launcher": bool(send or block or menu_send)}


def _move_line(device, action, new, play):
    """A moved action, said: what the new key does now, and what the old key still does."""
    sends, drops = play["send"], play["drop"]
    native = _native(device, new)
    lost = [c for c in native if new in drops.get(c, [])]
    keeps = [c for c in native if c not in lost and c not in sends.get(new, [])]
    menu_key = device == "keyboard" and new in ("Enter", "BackSpace")   # a move works in menus too: said for these
    line = f"{_cap(label(new))} {does(action)}" + (", in menus as well" if menu_key else "")
    if lost:
        line += f"{',' if menu_key else ''} and no longer {jobs(lost)}"
    if keeps:
        line += f", and still {jobs(keeps)}"
    said = [line + "."]
    for old in _old_keys(device, action):
        if old == new:
            continue
        left = [c for c in _native(device, old) if old not in drops.get(c, [])]
        said.append(f"{_cap(label(old))} still {jobs(left)}." if left else f"{_cap(label(old))} no longer {does(action)}.")
    return " ".join(said)


def _pair_lost(s, d, where):
    """What a key standing for another stops doing: its actions while you explore (where "play"), or its jobs
    in menus (where "menu": Backspace standing for Enter no longer goes back). The game's developer tools are
    left out."""
    prefix = "Player_" if where == "play" else "Button_"
    return [c for c in KEY_COMMANDS.get(s, []) if c.startswith(prefix) and c not in KEY_COMMANDS.get(d, [])
            and NAMES.get(c, True) is not None]


def _pair_line(s, d, while_you=None):
    """A key standing for another, said: "H does what E does while you explore (Interact).", and what it stops
    doing: "In menus, Backspace does what Enter does (Confirm and Skip), and no longer goes back in menus."."""
    commands = [c for c in KEY_COMMANDS.get(d, []) if NAMES.get(c, True) is not None]
    if while_you:
        names = _and(say(c) for c in commands if c.startswith("Player_"))
        line = f"{_cap(label(s))} does what {label(d)} does while you {while_you}" + (f" ({names})" if names else "")
        lost = _pair_lost(s, d, "play")
    else:
        names = _and(say(c) for c in commands)
        line = f"In menus, {label(s)} does what {label(d)} does" + (f" ({names})" if names else "")
        lost = _pair_lost(s, d, "menu")
    if lost:
        line += f", and no longer {jobs(lost)}"
    return line + "."
