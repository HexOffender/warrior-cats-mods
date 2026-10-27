"""Unreal key names to Windows key codes, and the remap plans: the in-game remap script's (gameremap.py)
and the key remapper's (remapper.py).

The game ignores edited bindings (see README, "Remapping keys"), so it always listens for its own
keys. Each key it hears is sent on to its listeners as the game's commands (KEY_COMMANDS: Interact,
Pounce, and the menus' Up, Confirm, Back...). Inside the game, a remap works on those commands: the
in-game script sends a command when its new key is pressed, and drops the game's own when it comes
from the old key (native_plan), in play and in menus. Movement and the camera are axes, which it
can't move; those are left to the key remapper outside the game, where a remap is "when I press F,
send the game E": it holds back F and sends E in its place. Actions in controls.json are turned into
such key pairs using the game's bindings below; the "keys" section maps keys directly (e.g. W, which
no action lists). Both apply while you play. The "menus" section is a separate set of key pairs used
only while a menu is open.
"""
from .controls import KNOWN_KEYS, normalise_key

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


def native_plan(merged):
    """What the in-game remap script (gameremap.py) does with controls.json merged across mods, and what's
    left for the key remapper outside the game.

    Returns (plan, rest, warnings). plan is {"play": {"send": ..., "drop": ...}, "menu": {...},
    "keys": {action: [key, ...]}}. In each, send is {key: [command, ...]}: pressing the key sends those
    commands; drop is {command: [key, ...]}: the game's own command is dropped when it comes from one of
    those keys. "play" applies while you explore (the controller and the HUD), "menu" in the game's menus
    (any other screen). keys says where each changed action is now. rest is controls.json with only what the
    script can't do (movement and the camera, keys standing for them or for keys that send nothing, mouse
    buttons in menus), for plan and menu_plan.
    """
    plans = {"play": ({}, {}), "menu": ({}, {})}
    rest, warnings, setters, moved = {}, [], {}, set()

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
    for device in ("keyboard", "gamepad"):
        for action, key in merged.get(device, {}).items():
            known = COMMANDS if device == "keyboard" else GAME_GAMEPAD
            if action in AXES or action not in known:
                if device == "keyboard":
                    rest.setdefault("keyboard", {})[action] = key   # plan() moves it, or says it doesn't know it
                elif action in AXES:
                    warnings.append(f"gamepad: {action} is a stick, which only Steam Input can move")
                else:
                    warnings.append(f"gamepad: {action}: only the game's own actions can move to a controller "
                                    f"button (known: {', '.join(a for a in GAME_GAMEPAD if a not in AXES)})")
                continue
            new = normalise_key(device, key)
            if new not in BUTTONS:
                warnings.append(f"{device}: {action}: the game has no button named '{new}'")
                continue
            old = _old_keys(device, action)
            if old == [new]:
                continue
            if not old:
                warnings.append(f"{device}: no key sends {action} in the game; {new} will")
            moved.add((device, action))
            for where in plans:
                send(where, new, action, action)
                for k in old:
                    if k != new:
                        drop(where, action, k)
            if new in AXIS_KEYS:
                warnings.append(f"{new} now does {action}, and still moves you or the camera too: the game reads "
                                f"those keys itself; move that job to another key under \"keys\"")
    # The key that takes an action stops doing the actions the game has on it, unless they move too.
    own = {"keyboard": {**GAME_KEYBOARD, **SCREEN_KEYBOARD}, "gamepad": GAME_GAMEPAD}
    for key, commands in list(plans["play"][0].items()):
        for device, table in own.items():
            for action, k in table.items():
                if k == key and action not in commands and action not in AXES and (device, action) not in moved:
                    for where in plans:
                        drop(where, action, key)
                    warnings.append(f"{action} is on {key}, but {key} now does {', '.join(commands)}; move {action} too")
    # A key that stands for another: while you play ("keys") or in menus ("menus"). It sends that key's
    # commands and stops sending its own, as with the key remapper outside the game.
    for section, where in (("keys", "play"), ("menus", "menu")):
        for src, dst in merged.get(section, {}).items():
            s, d = _key(src), _key(dst)
            commands = KEY_COMMANDS.get(d, [])
            if (s not in BUTTONS or not commands or (where == "play" and d in AXIS_KEYS)
                    or (where == "menu" and s in MOUSE)):
                rest.setdefault(section, {})[src] = dst   # for the key remapper outside the game
                continue
            if s == d:
                continue
            for command in commands:
                send(where, s, command, f"{section}: {s}")
            for command in KEY_COMMANDS.get(s, []):
                if command not in commands:
                    drop(where, command, s)
                    if where == "play" and command.startswith("Player_"):
                        warnings.append(f"{command} is on {s}, but {s} now stands for {d}; move {command} too")
            if where == "menu" and (len(s) == 1 or s in DIGITS or s == "SpaceBar"):
                warnings.append(f"menus: {s} still types on the name screen, and does {d}'s job there too")
    for (where, key), who in sorted(setters.items()):
        # A move shows in both play and menus; say so once.
        if len(who) > 1 and (where == "play" or any(w.startswith("menus") for w in who)):
            warnings.append(f"{key} is set for {' and '.join(plans[where][0][key])}; it does all of them")
    outside = {_key(k) for k in rest.get("keys", {})} | {_key(k) for k in rest.get("keyboard", {}).values()}
    for key in sorted(outside & set(plans["play"][0])):
        warnings.append(f"{key} is set both for {', '.join(plans['play'][0][key])} and for moving you or the "
                        f"camera; use another key for one of them")
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
    return plan, rest, warnings


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
