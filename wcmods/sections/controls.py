"""Button remapping (controls.json). The game ignores edited bindings in its save, so for now this only
checks the file; see README, "Remapping keys"."""
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
            out[device] = {}
            for action, change in mapping.items():
                if not action.startswith("_"):
                    out[device][action] = controls.key_of(change)   # raises ValueError for {} without "key"
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
        ctx.warn("the game ignores edited key bindings, so controls.json isn't applied yet; remap keys with "
                 "PowerToys Keyboard Manager for now (README, \"Remapping keys\")")
        ctx.note("controls", merged)
