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
          "key": "F7"
        },
        { "id": "Yawn", "name": "Yawn", "game": "A_CatMaster_Yawn_1", "emote": true, "key": "F8" }
      ]
    }

Each becomes a sequence, /Game/WCMods/<mod>/A_<id>: a copy of one of the game's on that kind's skeleton
with the file's animation in it (ctx.add_animation, animations.py, formats/anim.py). The install lists them
in the shared Lua module WCModsAnims, from which WCModsGame's Game.anims plays them by their id,
"<mod>/<id>"; with emotes, the WCModsEmotes script puts those on their keys and on a mod menu page. They
play over what the cat or animal is doing, in the slot its AnimBlueprint plays the game's own montages in.

One with "game" (one of the game's sequences, "A_CatMaster_Yawn_1") in place of "file" needs no Blender:
that sequence plays as it is (by its own path), or, with "claws", as a copy with the claws out
(ctx.add_animation_from_game).

One with "replaces" (a game sequence: "A_CatMaster_Trot_1") goes in that sequence's place instead
(ctx.replace_animation): every cat, or every animal of that kind, plays it wherever the game played its
own, fitted to that one's length; its keys come from its file, or from the "game" sequence. It isn't one
of Game.anims' then.
See docs/SDK.md for every key.
"""
import re

from .. import animations
from ..sdk import Section
from .items import ModelFile

ID = re.compile(r"[A-Za-z][A-Za-z0-9]{0,47}$")
KEY = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}$")      # one of Unreal's key names: "F7", "T", "Gamepad_DPad_Up"
REPLACES = re.compile(r"(/Game/[A-Za-z0-9_/]+/)?A_[A-Za-z0-9_]{1,120}$")   # a game sequence's name or path
KEYS = {"id", "name", "file", "game", "for", "clip", "loop", "speed", "blend", "emote", "key", "claws", "replaces"}
# What a replacement can't have: the game plays it where it played its own, as it played that.
NOT_WITH_REPLACES = ("loop", "speed", "blend", "emote", "key", "claws")
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
        found, seen = [], set()
        files = _game_files(ctx)
        for i, a in enumerate(raw.get("animations", [])):
            what = f"animations.json: animation {i + 1}"
            if not isinstance(a, dict):
                raise ValueError(f"{what} should be an object")
            name = a.get("name").strip() if isinstance(a.get("name"), str) else ""
            # One the Animations page saved half made: the others still install, and the save says so.
            if isinstance(a.get("id"), str) and not a.get("file") and not a.get("game"):
                if ctx is not None:
                    ctx.leave_out(mod.id, a["id"], name, "nothing chosen to play yet",
                                  "nothing chosen for it to play yet")
                continue
            if isinstance(a.get("id"), str) and not name and (a.get("name") is None or isinstance(a["name"], str)):
                if ctx is not None:
                    ctx.leave_out(mod.id, a["id"], name, "no name", "it has no name")
                continue
            check(a, what)
            if a["id"].lower() in seen:     # the game's package names are any case
                raise ValueError(f"{what}: another animation is called {a['id']} too (ids differ in more than case)")
            seen.add(a["id"].lower())
            # A game sequence it names that isn't there (misspelled, or a game update moved it): left out now, so
            # the save says so, when the game's files can be read; else the build says it.
            missing = _missing_sequence(files, a)
            if missing:
                ctx.leave_out(mod.id, a["id"], name, missing)
                continue
            found.append(a)
        return found or None

    def build(self, ctx, items):
        made, emotes, keys, replaced = {}, [], {}, {}
        for mod, found in items:
            for a in found:
                full = f"{mod.id}/{a['id']}"
                kind = a.get("for", "cat")
                said = f"{mod.id}: {a['id']}"
                file = AnimationFile(a["file"]) if a.get("file") else None
                if a.get("replaces"):
                    try:
                        if file is not None:
                            path, _ = ctx.replace_animation(
                                a["replaces"], lambda file=file, mod=mod: file.parts(mod), kind=kind, clip=a.get("clip"),
                                source=said, key=file.key(mod))
                        else:
                            path, _ = ctx.replace_animation(a["replaces"], None, kind=kind, source=said,
                                                            from_game=a["game"])
                    except ValueError as e:
                        ctx.warn(f"{said}: {e}")
                        continue
                    target = path.split(".", 1)[0]     # by its path: two folders can have one name
                    if target in replaced:      # mods come lowest priority first: the later one goes in
                        ctx.warn(f"{said}: {replaced[target]} replaces {target.rsplit('/', 1)[-1]} too; this one goes "
                                 "in (its mod comes later: a higher priority, or the same and a later name)")
                    replaced[target] = full
                    continue
                try:
                    if file is not None:
                        path, seconds = ctx.add_animation(
                            f"{mod.id}/A_{a['id']}", lambda file=file, mod=mod: file.parts(mod), kind=kind,
                            clip=a.get("clip"), claws=bool(a.get("claws")), source=said, key=file.key(mod))
                    elif a.get("claws"):         # the cats' claws can only be set on a copy
                        path, seconds = ctx.add_animation_from_game(f"{mod.id}/A_{a['id']}", a["game"], kind=kind,
                                                                    claws=True, source=said)
                    else:                        # the game's own sequence, played by its path
                        seq = ctx.game_sequence(a["game"], kind)
                        short = seq["path"].rsplit("/", 1)[-1]
                        if seq["additive"]:
                            raise ValueError(f"{short} is an additive animation (its keys are added to another pose, "
                                             "not a pose of their own), so it can't play on its own")
                        path, seconds = f"{seq['path']}.{short}", seq["seconds"]
                except ValueError as e:
                    ctx.warn(f"{said}: {e}")
                    continue
                entry = {"name": a["name"], "kind": kind, "path": path, "loop": bool(a.get("loop")),
                         "speed": float(a.get("speed", 1.0)), "blend": float(a.get("blend", BLEND)), "seconds": seconds}
                if a.get("emote"):
                    entry["emote"] = True
                    emote = {"id": full, "name": a["name"]}
                    if a.get("key"):
                        entry["key"] = emote["key"] = a["key"]
                        if a["key"] in keys:   # both start, and the later one takes the cat over
                            ctx.warn(f"{mod.id}: {a['id']}: the key {a['key']} is {keys[a['key']]}'s emote too; only the "
                                     "later one plays")
                        keys[a["key"]] = full
                    emotes.append(emote)
                made[full] = entry
        if replaced:
            ctx.note("replaced", replaced)
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


def _game_files(ctx):
    """The game's file list, or None while it can't be read (no ctx, the studio's save check with no game
    folder, a pak Steam is updating): then the sequences an animation names are checked by the build."""
    from ..gamefiles import Unreadable
    try:
        return ctx.game.io.files if ctx is not None else None
    except (AttributeError, OSError, Unreadable):
        return None


def _missing_sequence(files, a):
    """Why the game's sequence an animation names ("game", "replaces") can't be found in `files` (find_sequence's
    sentence, "the game has no sequence A_CatMaster_Yawm_1 for cats ..."), or None when they're there or the
    game's files can't be read."""
    if files is None:
        return None
    for key in ("game", "replaces"):
        if a.get(key):
            try:
                animations.find_sequence(files, a.get("for", "cat"), a[key])
            except ValueError as e:
                return str(e)
    return None


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
    if a.get("file") is not None and a.get("game") is not None:
        raise ValueError(f"{what}: it plays a \"file\" or one of the game's animations (\"game\"), not both")
    if a.get("game") is not None:
        if not isinstance(a["game"], str) or not REPLACES.match(a["game"]):
            raise ValueError(f"{what}: \"game\" should be one of the game's sequences, by its name "
                             "(\"A_CatMaster_Yawn_1\") or its path")
        if a.get("clip") is not None:
            raise ValueError(f"{what}: \"clip\" picks an animation in a file; one of the game's takes none")
    elif not isinstance(a.get("file"), str) or not a["file"].lower().endswith(animations.FORMATS):
        raise ValueError(f"{what}: \"file\" should be a glTF file in the mod's folder (.glb or .gltf), e.g. "
                         "\"animations/wave.glb\" (or \"game\": one of the game's own animations)")
    kind = a.get("for", "cat")
    if kind not in animations.KINDS:
        raise ValueError(f"{what}: \"for\" should be one of {', '.join(animations.KINDS)}")
    if a.get("clip") is not None and (not isinstance(a["clip"], str) or not a["clip"]):
        raise ValueError(f"{what}: \"clip\" should be the name of an animation in the file")
    if isinstance(a.get("game"), str) and isinstance(a.get("replaces"), str) and a["game"].lower() == a["replaces"].lower():
        raise ValueError(f"{what}: a sequence can't take its own place: \"game\" and \"replaces\" are the same")
    if a.get("replaces") is not None:
        if not isinstance(a["replaces"], str) or not REPLACES.match(a["replaces"]):
            raise ValueError(f"{what}: \"replaces\" should be one of the game's sequences, by its name "
                             "(\"A_CatMaster_Trot_1\") or its path")
        given = [f'"{k}"' for k in NOT_WITH_REPLACES if a.get(k) not in (None, False)]
        if given:
            raise ValueError(f"{what}: one that replaces a game sequence plays where the game played that, as it "
                             f"played it, so it takes no {', '.join(given)}")
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
