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
            out[device] = {}
            for action, change in mapping.items():
                if action.startswith("_"):
                    continue
                controls.split_change(change)   # raises ValueError for a malformed {key, scale}
                out[device][action] = change
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
            for action, change in mapping.items():
                k = controls.normalise_key(device, controls.split_change(change)[0])
                if k not in controls.KNOWN_KEYS:
                    ctx.warn(f"{device}: '{k}' for {action} is not a key name I recognise")
        ctx.save_op({"op": "controls", "changes": merged})
        # The game's own switch for custom bindings (GlobalConfig.bCustomControls, saved as
        # Shared/SettingsData/CustomControls). It's off in a fresh save.
        ctx.add_save_key("Shared/SettingsData", "CustomControls", True, source="controls")
        ctx.warn("the game keeps these bindings in the save but hasn't been seen using edited ones yet "
                 "(a test remap of Reset camera had no effect); check in game")
        ctx.note("controls", merged)
