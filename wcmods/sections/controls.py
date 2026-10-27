"""Button remapping (controls.json). The game ignores edited bindings in its save, so remaps are carried
out at runtime. Inside the game, a UE4SS script (gameremap.py) moves the game's actions and menu keys to
other keys, mouse buttons and controller buttons. What it can't move (movement and the camera, and mouse
buttons in menus) is left to the key remapper outside the game (`wcmods play` / `wcmods remap`), for
which this section installs the small UE4SS script that tells it when you're playing (playstate.py).
See README, "Remapping keys"."""
from .. import controls, gameremap, keymap, mods as modlib, playstate
from ..sdk import Section

DEVICES = ("keyboard", "gamepad", "keys", "menus")


class ControlsSection(Section):
    id = "controls"
    title = "Controls"
    files = ("controls.json",)

    def collect(self, mod, ctx):
        raw = self.read_json(mod, "controls.json")
        out = {}
        for device, mapping in raw.items():
            if device.startswith("_"):
                continue
            if device not in DEVICES:
                raise ValueError(f"controls.json: '{device}' should be one of {', '.join(DEVICES)}")
            if not isinstance(mapping, dict):
                raise ValueError(f"controls.json: '{device}' should be an object")
            if device == "menus":
                # {"keys": {key you press: game key}}; kept flat here so mods merge key by key.
                extra = [k for k in mapping if k != "keys" and not k.startswith("_")]
                if extra or not isinstance(mapping.get("keys", {}), dict):
                    raise ValueError('controls.json: "menus" should look like {"keys": {"Escape": "BackSpace"}}')
                mapping = mapping.get("keys", {})
            out[device] = {}
            for name, change in mapping.items():
                if not name.startswith("_"):
                    out[device][name] = controls.key_of(change)   # raises ValueError for {} without "key"
        return out or None

    def build(self, ctx, items):
        merged = merge(data for _, data in items)
        if not merged:
            return
        in_game, outside, warnings = split(merged, bool(ctx.cfg.ue4ss_mods_dir))
        if gameremap.has_work(in_game):
            ctx.add_ue4ss_mod(gameremap.UE4SS_MOD_NAME, {"Scripts/main.lua": gameremap.script(in_game),
                                                         "enabled.txt": ""})
        send, block, outside_warnings = keymap.plan(outside)
        menu_send, menu_warnings = keymap.menu_plan(outside)
        for w in warnings + outside_warnings + menu_warnings:
            ctx.warn(w)
        if send or block or menu_send:
            # Lets the remapper tell play from menus (see playstate.py).
            path = playstate.state_path(ctx.cfg)
            if path:
                ctx.add_ue4ss_mod(playstate.UE4SS_MOD_NAME, {"Scripts/main.lua": playstate.script(path), "enabled.txt": ""})
            else:
                ctx.warn("without UE4SS, every remap goes through the key remapper (`wcmods play`), which can't "
                         "tell menus from play, so it remaps whenever the game is in front")
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
        return {"play": {"send": {}, "drop": {}}, "menu": {"send": {}, "drop": {}}, "keys": {}}, merged, []
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
