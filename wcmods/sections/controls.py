"""Button remapping (controls.json). The game ignores edited bindings in its save, so remaps are carried
out at runtime. Inside the game, a UE4SS script (gameremap.py) moves the game's actions and menu keys to
other keys, mouse buttons and controller buttons: that's the way remaps work. What it can't move
(movement and the camera, the map's zoom and move, and mouse buttons in menus) is left to the old key
remapper outside the game (`wcmods play` / `wcmods remap`, deprecated), for which this section installs
the small UE4SS script that tells it when you're playing (playstate.py). See docs/remapping.md.

keys_in_use lists what every key does before any remap (the game's keys, wcmods' own and the keys mods
declare); the Controls page shows it, and the build and the page warn when a remap lands on one that
wcmods or a mod listens on itself."""
import json
import os

from .. import controls, gameremap, keymap, menusettings, mods as modlib, mouselook, playstate
from ..sdk import Section

DEVICES = controls.DEVICES
LAUNCHER = keymap.LAUNCHER
# The mod menu's key as wcmods.json spells it (menu.KEYS) -> Unreal's name for it.
MENU_KEY_NAMES = {"INS": "Insert", "HOME": "Home", "END": "End", "DEL": "Delete", "PAGE_UP": "PageUp",
                  "PAGE_DOWN": "PageDown"}
EMOTE_WHEEL = "emote-wheel"   # the Emote wheel mod (wcmods-emote-wheel), whose settings.json names its keys
GET_SET_UP = "Get set up, on the Mods page, installs the loader"


class ControlsSection(Section):
    id = "controls"
    title = "Controls"
    files = ("controls.json",)

    def collect(self, mod, ctx):
        return controls.parse(self.read_json(mod, "controls.json")) or None

    def build(self, ctx, items):
        merged = merge(data for _, data in items)
        if not merged:
            return
        ue4ss = bool(ctx.cfg.ue4ss_mods_dir)
        in_game, outside, _ = split(merged, ue4ss)
        if gameremap.has_work(in_game):
            ctx.add_ue4ss_mod(gameremap.UE4SS_MOD_NAME, {"Scripts/main.lua": gameremap.script(in_game),
                                                         "enabled.txt": ""})
        send, block, _ = keymap.plan(outside)
        menu_send, _ = keymap.menu_plan(outside)
        # The same sentences the Controls page shows before Apply, the keys wcmods and mods listen on included.
        said = keymap.describe(merged, ue4ss, reserved(keys_in_use(ctx.cfg, ctx.mods)))
        for w in said["warnings"]:
            ctx.warn(w)
        if send or block or menu_send:
            # Lets the remapper tell play from menus (see playstate.py).
            path = playstate.state_path(ctx.cfg)
            if path:
                # Each change only the old key remapper makes (moving you or the camera, mouse buttons in menus).
                for found in said["rows"].values():
                    for row in found.values():
                        if row["status"] == "launcher":
                            ctx.warn(f"{row['line'].rstrip('.')}, which is deprecated")
                ctx.add_ue4ss_mod(playstate.UE4SS_MOD_NAME, {"Scripts/main.lua": playstate.script(path), "enabled.txt": ""})
            else:
                ctx.warn(f"Without the script loader, key changes work only when you start the game with {LAUNCHER} "
                         "(keyboard and mouse only, and it changes keys whenever the game is in front, menus "
                         f"included). {GET_SET_UP}")
        ctx.note("controls", merged)
        ctx.note("remaps", {"in_game": in_game, "send": send, "block": sorted(block), "menus": menu_send})


def merge(datas):
    """controls.json contents from several mods, later ones winning per action or key."""
    merged = {}
    for data in datas:
        for device, mapping in data.items():
            merged.setdefault(device, {}).update(mapping)
    return {d: m for d, m in merged.items() if m}


def split(merged, in_game):
    """(what the in-game script does, controls.json with what's left for the key remapper, warnings).
    in_game: whether the script is there to do its part (UE4SS installed); without it, the key remapper
    does everything it can."""
    if not in_game:
        return ({"play": {"send": {}, "drop": {}}, "menu": {"send": {}, "drop": {}}, "keys": {},
                 "icons": {"play": {}, "menu": {}}}, merged, [])
    return keymap.native_plan(merged)


def remap_plan(mods_root, cfg=None):
    """What the enabled mods' controls.json ask the key remapper for: (send, block, menu_send, warnings),
    keymap.plan and keymap.menu_plan on the part the in-game script doesn't do (all of it when the script
    isn't installed in cfg's game). The CLI's remap and play, and the studio's Play, start the remapper on it."""
    sec, datas = ControlsSection(), []
    for m in modlib.discover(mods_root):   # priority order, so later mods win
        if m.enabled and sec.claims(m):
            data = sec.collect(m, None)
            if data:
                datas.append(data)
    _, outside, warnings = split(merge(datas), cfg is not None and gameremap.installed(cfg))
    send, block, plan_warnings = keymap.plan(outside)
    menu_send, menu_warnings = keymap.menu_plan(outside)
    return send, block, menu_send, warnings + plan_warnings + menu_warnings


def _read(mod, name):
    """A mod's JSON file, or None when it's not there or can't be read (the build says what's wrong with it)."""
    path = os.path.join(mod.folder, name)
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def keys_in_use(cfg, mods):
    """What each key does before any remap, for the Controls page's "Which keys are free?" and for warnings:
    [{"key", "does", "from", "taken"}], key an Unreal key name. The game's keys and controller buttons (what
    each sends, in plain words), F11 (the game's fullscreen key), the mod menu's key and controller button,
    mouse look's key while a mouse look mod is on, and the keys mods declare: emotes' keys in animations.json
    and the Emote wheel's. taken is "refuse" for a key the Controls page won't put an action on (wcmods' own,
    and F11), "warn" for a mod's (which can be switched off) and None for the game's own (the plan says what a
    remap does to those). mods: the mods to read, in priority order; only the enabled ones count."""
    found = []

    def add(key, does, source, taken=None):
        if key:
            found.append({"key": key, "does": does, "from": source, "taken": taken})

    for key, commands in keymap.KEY_COMMANDS.items():
        play = [keymap.say(keymap.AXIS_JOB[key])] if key in keymap.AXIS_JOB else []
        play += [keymap.say(c) for c in commands if c.startswith("Player_")]
        in_menus = [keymap.say(c) for c in commands if c.startswith("Button_")]
        said = keymap._and(play)
        if in_menus:
            said += ("; in menus: " if said else "in menus: ") + keymap._and(in_menus)
        add(key, said, "the game")
    pads = {}
    for action, key in keymap.GAME_GAMEPAD.items():
        if action in keymap.AXES:   # a stick, for both of its ways
            pads[key] = ["moves you" if action.startswith("Player_Movement") else "moves the camera"]
        else:
            pads.setdefault(key, []).append(keymap.say(action))
    for key, names in pads.items():
        add(key, keymap._and(names), "the game")
    add("F11", "switches between a window and full screen", "the game", "refuse")
    settings = menusettings.menu_settings(cfg)
    add(MENU_KEY_NAMES.get(settings["key"], settings["key"]), "opens the mod menu", "wcmods", "refuse")
    add(settings["pad"], "opens the mod menu", "wcmods", "refuse")
    enabled = [m for m in mods if m.enabled]
    looks = [(m, mouselook_settings(m)) for m in enabled if os.path.isfile(os.path.join(m.folder, "mouselook.json"))]
    looks = [(m, s) for m, s in looks if s is not None]
    if looks:
        try:
            toggles = {mouselook.merge([s for _, s in looks])["toggle_key"]}
        except ValueError:   # crossed tilt limits: the build refuses; each mod's own key, as it would be alone
            toggles = {s.get("toggle_key", mouselook.DEFAULTS["toggle_key"]) for _, s in looks}
        for key in sorted(k for k in toggles if k):
            add(key, "switches mouse look off and on", "Mouse look", "refuse")
    for m in enabled:
        anims = _read(m, "animations.json")
        for a in (anims or {}).get("animations", []) if isinstance(anims, dict) else []:
            if isinstance(a, dict) and a.get("emote") and isinstance(a.get("key"), str):
                add(a["key"], f"plays the emote {a.get('name') or a.get('id')}", m.name, "warn")
        if m.id == EMOTE_WHEEL:
            wheel = _read(m, "settings.json")
            wheel = wheel if isinstance(wheel, dict) else {}
            for name, default in (("key", "T"), ("pad", "Gamepad_DPad_Down")):
                value = wheel.get(name, default)
                if isinstance(value, str):
                    add(value, "opens the emote wheel", m.name, "warn")
    return found


def mouselook_settings(mod):
    """A mod's mouselook.json as the build reads it, or None when it can't be read."""
    raw = _read(mod, "mouselook.json")
    try:
        return mouselook.validate(raw)
    except ValueError:
        return None


def reserved(in_use):
    """keys_in_use's keys that wcmods or a mod listens on itself: {key: {"does", "from"}}, for keymap.describe.
    A key both refuse and warn is said as the one that refuses."""
    out = {}
    for entry in sorted((e for e in in_use if e["taken"]), key=lambda e: e["taken"] != "refuse"):
        out.setdefault(entry["key"], {"does": entry["does"], "from": entry["from"]})
    return out


def check(text_or_data, mod_id, mods, cfg):
    """The Controls page's check before Apply (POST /controls/check): the page's controls.json for mod_id,
    merged with the other enabled mods' at their priorities (mod_id counts as on, since saving turns it on),
    said by keymap.describe. Returns describe's answer plus "in_use" (keys_in_use), "ue4ss", and "others":
    sentences about entries another mod also sets, and "lower": the entries a lower-priority enabled mod sets
    ([section, name] pairs), for which the page writes the game's key explicitly when it puts it back."""
    data = controls.parse(text_or_data if not isinstance(text_or_data, str) else json.loads(text_or_data))
    sec, datas, lower, others = ControlsSection(), [], set(), []
    names = {m.id: m.name for m in mods}
    above = False
    by_mod = []
    for m in mods:   # priority order
        if m.id == mod_id:
            datas.append(data)
            above = True
            continue
        if not (m.enabled and sec.claims(m)):
            continue
        try:
            theirs = sec.collect(m, None) or {}
        except ValueError:
            continue   # its own page says what's wrong with it
        datas.append(theirs)
        by_mod.append((m, theirs, above))
        if not above:
            lower |= {(section, name) for section, entries in theirs.items() for name in entries}
    if not any(m.id == mod_id for m in mods):   # a mod not made yet: the page's Save makes it, last
        datas.append(data)
    for m, theirs, later in by_mod:
        for section, entries in theirs.items():
            for name, key in entries.items():
                if name in data.get(section, {}):
                    what = keymap.say(name) if section in ("keyboard", "gamepad") else keymap.label(controls.normalise_key("keyboard", name))
                    others.append(f"{names[m.id]} also changes {what}, and "
                                  f"{'wins: it comes after this mod' if later else 'this mod wins: it comes later'}.")
    ue4ss = bool(cfg.ue4ss_mods_dir)
    in_use = keys_in_use(cfg, mods)
    merged = merge(datas)
    said = keymap.describe(merged, ue4ss, reserved(in_use))
    # An entry a later mod sets too doesn't reach the game while that mod is on: its row says so.
    for section, entries in data.items():
        for name, key in entries.items():
            if merged.get(section, {}).get(name) != key:
                winner = next(names[m.id] for m, theirs, later in reversed(by_mod)
                              if later and name in theirs.get(section, {}))
                said["rows"][section][name] = {
                    "key": key, "status": "overridden", "line": "",
                    "notes": [f"{winner} changes this too and wins (it comes after this mod), so this change doesn't "
                              "reach the game while it's on"]}
    return {**said, "in_use": in_use, "ue4ss": ue4ss, "others": others, "lower": sorted([list(x) for x in lower])}
