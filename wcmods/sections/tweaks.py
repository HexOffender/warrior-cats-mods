"""Tweaks (tweaks.json), shipped as wcmods' own UE4SS script (lua/tweaks.lua): no code of the mod's own runs."""
import os
import re

from .. import menusettings, mouselook, tweaks
from ..sdk import Section
from .controls import ControlsSection
from .mouselook import MouseLookSection

FKEY = re.compile(r"^[Ff](\d{1,2})$")


def taken_keys(cfg, mods):
    """{key: what has you press it} for the F keys a heal key would share in a build of `mods` (in priority order;
    the ones switched off are left out): the mod menu's key, mouse look's on and off key (when a mod has a
    mouselook.json), and a key a controls.json remap has you press. A file that can't be read is its own
    section's to say."""
    taken = {}
    menu = menusettings.menu_settings(cfg)["key"]
    if menu:
        taken[str(menu)] = "the mod menu's key"
    look, controls = MouseLookSection(), ControlsSection()
    toggle, pressed = None, {}
    for m in mods:
        if not m.enabled:
            continue
        if look.claims(m):
            try:
                data = look.collect(m, None)
            except (OSError, ValueError):
                data = None
            if data is not None:
                toggle = data.get("toggle_key", mouselook.DEFAULTS["toggle_key"] if toggle is None else toggle)
        if controls.claims(m):
            try:
                data = controls.collect(m, None)
            except (OSError, ValueError):
                data = None
            for device, mapping in (data or {}).items():   # later mods win, action by action and key by key
                for name, key in mapping.items():
                    pressed[(device, name)] = (key, m)
    if toggle:
        taken.setdefault(toggle, "mouse look's on and off key (mouselook.json)")
    for (device, name), (key, m) in pressed.items():
        if device == "keyboard":   # an action moved onto a key
            press, what = key, f"the key for {name} (the controls.json of {m.name})"
        elif device in ("keys", "menus"):   # a key that stands for another
            press, what = name, f"a remap to {key} (the controls.json of {m.name})"
        else:
            continue
        f = FKEY.match(str(press).strip())
        if f:
            taken.setdefault(f"F{int(f.group(1))}", what)
    return taken


class TweaksSection(Section):
    id = "tweaks"
    title = "Tweaks"
    files = (tweaks.FILE,)

    def collect(self, mod, ctx):
        return tweaks.validate(self.read_json(mod, tweaks.FILE))

    def build(self, ctx, items):
        if not items:
            return
        settings = tweaks.merge([data for _, data in items])
        taken = taken_keys(ctx.cfg, ctx.mods or [m for m, _ in items])
        key = settings["heal_key"]
        if key and key in taken:
            who = next(m for m, data in reversed(items) if "heal_key" in data)
            if key == menusettings.menu_settings(ctx.cfg)["key"]:
                # Moved onto the heal key after the tweaks were saved: the menu keeps its key, the heal goes.
                ctx.warn(f"{who.id}: its heal key, {key}, is the mod menu's key too, so the heal is left "
                         "out: pick another key on the Tweaks page")
                settings["heal_key"] = ""
            else:
                ctx.warn(f"{who.id}: its heal key, {key}, is also {taken[key]}, so pressing it does both: "
                         "pick another key on the Tweaks page")
        on = tweaks.active(settings)
        if not on:   # nothing ticked (a tweaks.json of {}): no script, timers or page for nothing
            ctx.log("  tweaks: no tweak is on, so WCModsTweaks stays out")
            return
        # The page in the mod menu saves into the mod whose tweaks win: the one with the highest priority.
        top = items[-1][0]
        save = {"path": os.path.abspath(os.path.join(top.folder, tweaks.FILE)), "file": f"mods/{top.id}/{tweaks.FILE}",
                "keep": {k: v for k, v in self.read_json(top, tweaks.FILE).items() if k.startswith("_")}}
        ctx.add_ue4ss_mod(tweaks.UE4SS_MOD_NAME, {"Scripts/main.lua": tweaks.script(settings, save, taken),
                                                  "enabled.txt": ""})
        ctx.note("on", on)   # the Installed mods page's
