"""Button remapping (controls.json). The game ignores edited bindings in its save, so keyboard and mouse
remaps are carried out by the key remapper (`wcmods play` / `wcmods remap`) while the game runs. This
section checks them at build time and installs the small UE4SS script that tells the remapper when
you're playing (playstate.py). See README, "Remapping keys"."""
from .. import controls, keymap, playstate
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
        send, block, warnings = keymap.plan(merged)
        menu_send, menu_warnings = keymap.menu_plan(merged)
        for w in warnings + menu_warnings:
            ctx.warn(w)
        if send or block or menu_send:
            # Lets the remapper tell play from menus (see playstate.py).
            path = playstate.state_path(ctx.cfg)
            if path:
                ctx.add_ue4ss_mod(playstate.UE4SS_MOD_NAME, {"Scripts/main.lua": playstate.script(path), "enabled.txt": ""})
            else:
                ctx.warn("without UE4SS the key remapper can't tell menus from play, so it remaps whenever "
                         "the game is in front")
        ctx.note("controls", merged)
        ctx.note("remaps", {"send": send, "block": sorted(block), "menus": menu_send})


def merge(datas):
    """controls.json contents from several mods, later ones winning per action or key."""
    merged = {}
    for data in datas:
        for device, mapping in data.items():
            merged.setdefault(device, {}).update(mapping)
    return {d: m for d, m in merged.items() if m}
