"""Button remapping (controls.json), written into the bindings the game keeps in its save."""
from .. import controls
from ..sdk import Section


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
            if device not in controls.SECTIONS:
                raise ValueError(f"controls.json: '{device}' should be 'keyboard' or 'gamepad'")
            out[device] = {a: k for a, k in mapping.items() if not a.startswith("_")}
        return out or None

    def build(self, ctx, items):
        merged = {}
        for _, data in items:
            for device, mapping in data.items():
                merged.setdefault(device, {}).update(mapping)
        merged = {d: m for d, m in merged.items() if m}
        if not merged:
            return
        for device, mapping in merged.items():
            for action, key in mapping.items():
                k = controls.normalise_key(device, key)
                if k not in controls.KNOWN_KEYS:
                    ctx.warn(f"{device}: '{k}' for {action} is not a key name I recognise")
        ctx.save_op({"op": "controls", "changes": merged})
        ctx.note("controls", merged)
