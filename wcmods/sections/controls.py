"""Button remapping (controls.json). The game ignores edited bindings in its save, so keyboard and mouse
remaps are carried out by the key remapper (`wcmods play` / `wcmods remap`) while the game runs; this
section checks them at build time. See README, "Remapping keys"."""
from .. import controls, keymap
from ..sdk import Section

DEVICES = ("keyboard", "gamepad", "keys")


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
        for w in warnings:
            ctx.warn(w)
        ctx.note("controls", merged)
        ctx.note("remaps", {"send": send, "block": sorted(block)})


def merge(datas):
    """controls.json contents from several mods, later ones winning per action or key."""
    merged = {}
    for data in datas:
        for device, mapping in data.items():
            merged.setdefault(device, {}).update(mapping)
    return {d: m for d, m in merged.items() if m}
