"""Animations of a mod's own (animations.json): glTF files made in Blender, for cats or one kind of animal,
played as emotes on your cat (a key, and the mod menu's Emotes page) or by scripts (Game.anims).

    {
      "animations": [
        {
          "id": "Wave",
          "name": "Wave",
          "file": "animations/wave.glb",
          "for": "cat",
          "emote": true,
          "key": "F6"
        }
      ]
    }

Each becomes a sequence, /Game/WCMods/<mod>/A_<id>: a copy of one of the game's on that kind's skeleton
with the file's animation in it (ctx.add_animation, animations.py, formats/anim.py). The install lists them
in the shared Lua module WCModsAnims, from which WCModsGame's Game.anims plays them by their id,
"<mod>/<id>"; with emotes, the WCModsEmotes script puts those on their keys and on a mod menu page. They
play over what the cat or animal is doing, in the slot its AnimBlueprint plays the game's own montages in.
See docs/SDK.md for every key.
"""
import re

from .. import animations
from ..sdk import Section
from .items import ModelFile

ID = re.compile(r"[A-Za-z][A-Za-z0-9]{0,47}$")
KEY = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}$")      # one of Unreal's key names: "F6", "T", "Gamepad_DPad_Up"
KEYS = {"id", "name", "file", "for", "clip", "loop", "speed", "blend", "emote", "key", "claws"}
ANIMS_LUA = "WCModsAnims"       # the shared Lua module that lists the install's animations
EMOTES_SCRIPT = "WCModsEmotes"  # the script that puts the emotes on keys and a menu page
SPEEDS = (0.1, 10.0)
BLENDS = (0.0, 2.0)
BLEND = 0.25                    # seconds an animation blends in and out, unless it says


class AnimationFile(ModelFile):
    """A glTF file in the mod's folder, read once the animation is known to be good."""
    what = "animation"

    def parts(self, mod):
        """(file name, bytes, sibling) for animations.build."""
        def sibling(name):
            try:
                return self._bytes(mod, name)
            except ValueError:
                return None
        return self.rel, self._bytes(mod), sibling


class AnimationsSection(Section):
    id = "animations"
    title = "Animations"
    files = ("animations.json",)

    def collect(self, mod, ctx):
        raw = self.read_json(mod, "animations.json")
        if not isinstance(raw, dict) or not isinstance(raw.get("animations", []), list):
            raise ValueError('animations.json should be an object: {"animations": [...]}')
        found = raw.get("animations", [])
        seen = set()
        for i, a in enumerate(found):
            what = f"animations.json: animation {i + 1}"
            if not isinstance(a, dict):
                raise ValueError(f"{what} should be an object")
            check(a, what)
            if a["id"] in seen:
                raise ValueError(f"{what}: another animation is called {a['id']} too")
            seen.add(a["id"])
        return found or None

    def build(self, ctx, items):
        made, emotes, keys = {}, [], {}
        for mod, found in items:
            for a in found:
                full = f"{mod.id}/{a['id']}"
                kind = a.get("for", "cat")
                file = AnimationFile(a["file"])
                try:
                    path, seconds = ctx.add_animation(
                        f"{mod.id}/A_{a['id']}", lambda file=file, mod=mod: file.parts(mod), kind=kind, clip=a.get("clip"),
                        claws=bool(a.get("claws")), source=f"{mod.id}: {a['id']}", key=file.key(mod))
                except ValueError as e:
                    ctx.warn(f"{mod.id}: {a['id']}: {e}")
                    continue
                entry = {"name": a["name"], "kind": kind, "path": path, "loop": bool(a.get("loop")),
                         "speed": float(a.get("speed", 1.0)), "blend": float(a.get("blend", BLEND)), "seconds": seconds}
                if a.get("emote"):
                    entry["emote"] = True
                    emote = {"id": full, "name": a["name"]}
                    if a.get("key"):
                        entry["key"] = emote["key"] = a["key"]
                        if a["key"] in keys:
                            ctx.warn(f"{mod.id}: {a['id']}: the key {a['key']} is {keys[a['key']]}'s emote too; it plays both")
                        keys[a["key"]] = full
                    emotes.append(emote)
                made[full] = entry
        if not made:
            return
        if not ctx.cfg.ue4ss_mods_dir:
            ctx.warn("animations play through the script loader (UE4SS), which isn't installed: Get set up on the Mods "
                     "page adds it")
        ctx.add_ue4ss_shared(ANIMS_LUA, animations.module(made))
        ctx.note("animations", sorted(made))
        if emotes:
            ctx.add_ue4ss_mod(EMOTES_SCRIPT, {"Scripts/main.lua": animations.emotes_script(emotes), "enabled.txt": ""})
            ctx.note("emotes", [e["id"] for e in emotes])


def check(a, what):
    """ValueError for an animation that isn't written right (what each key takes: docs/SDK.md)."""
    unknown = sorted(k for k in a if k not in KEYS and not k.startswith("_"))
    if unknown:
        raise ValueError(f"{what}: unknown key(s) {', '.join(unknown)} (docs/SDK.md lists them)")
    if not isinstance(a.get("id"), str) or not ID.match(a["id"]):
        raise ValueError(f"{what}: \"id\" should be letters and digits, starting with a letter (e.g. \"Wave\")")
    what = f"{what} ({a['id']})"
    if not isinstance(a.get("name"), str) or not a["name"].strip():
        raise ValueError(f"{what}: \"name\" is missing")
    if not isinstance(a.get("file"), str) or not a["file"].lower().endswith(animations.FORMATS):
        raise ValueError(f"{what}: \"file\" should be a glTF file in the mod's folder (.glb or .gltf), e.g. "
                         "\"animations/wave.glb\"")
    kind = a.get("for", "cat")
    if kind not in animations.KINDS:
        raise ValueError(f"{what}: \"for\" should be one of {', '.join(animations.KINDS)}")
    if a.get("clip") is not None and (not isinstance(a["clip"], str) or not a["clip"]):
        raise ValueError(f"{what}: \"clip\" should be the name of an animation in the file")
    for key in ("loop", "emote", "claws"):
        if a.get(key) is not None and not isinstance(a[key], bool):
            raise ValueError(f"{what}: \"{key}\" should be true or false")
    for key, (lo, hi) in (("speed", SPEEDS), ("blend", BLENDS)):
        v = a.get(key)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi):
            raise ValueError(f"{what}: \"{key}\" should be a number from {lo:g} to {hi:g}")
    if kind != "cat":
        for key in ("emote", "claws", "key"):
            if a.get(key):
                raise ValueError(f"{what}: only cats' animations take \"{key}\" (emotes are your cat's)")
    if a.get("key") is not None:
        if not isinstance(a["key"], str) or not KEY.match(a["key"]):
            raise ValueError(f"{what}: \"key\" should be one of the game's key names, e.g. \"F6\" or \"Gamepad_DPad_Up\"")
        if not a.get("emote"):
            raise ValueError(f"{what}: \"key\" plays an emote: give \"emote\": true too")
