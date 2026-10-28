"""Save edits (save.json), made in WrcGame.sav on install after a backup, once per save.

    {
      "set": { "0/GameplayProgression/Experience": 500, "Shared/SettingsData/Minimap": false },
      "add": { "0/GameplayProgression/State/Inventory": { "Gameplay.Inventory.Consumable.SmallCatnip": 5 } },
      "remove": [ "0/GameplayProgression/State/Inventory/Gameplay.Inventory.Materials.Cobweb" ],
      "always": false
    }

Paths start inside the save's account object; see savejson.py. Each change is made once per save and recorded
(saverecord.py), so playing on past it isn't undone by the next install; a mod whose value changes makes it
again, and "always": true makes every change at every install, as before. A value outside what the game
takes (RANGES) is left out with a warning.
"""
import os
import re

from ..formats.save import SAV_NAME, SaveGame
from ..formats.savejson import SaveDoc
from ..sdk import Section

# What a value in the save may be, by its path (the patterns read the same in Python and in the Save page's
# JavaScript, which gets them from GET /api/save): the lowest, the highest (None: no top) and whether it's whole.
RANGES = [
    {"match": r"^\d+/GameplayProgression/Level$", "min": 1, "max": 20, "whole": True, "what": "Level"},
    {"match": r"^\d+/GameplayProgression/Experience$", "min": 0, "max": None, "whole": True, "what": "Experience"},
    {"match": r"^\d+/GameplayProgression/FreshKill/Value$", "min": 0, "max": 100, "whole": False,
     "what": "The fresh-kill pile"},
    {"match": r"/State/(Health|Stamina)$", "min": 0, "max": None, "whole": False, "what": "Health and stamina"},
    {"match": r"^\d+/GameplayProgression/State/Inventory/[^/]+$", "min": 0, "max": None, "whole": True,
     "what": "A count of things carried"},
    {"match": r"^Shared/SettingsData/\w*Volume$", "min": 0, "max": 1, "whole": False, "what": "A volume"},
]

# A change's path in words, for the log, the record and the Save page (which gets these too): {cat} is the
# cat in the path's slot ("Fawnstar", "your cat", "cat slot 0"), {item} an item's name, {name} the last part
# of the path in words.
WORDS = [
    {"match": r"^(\d+)/GameplayProgression/Level$", "say": "{cat}'s level"},
    {"match": r"^(\d+)/GameplayProgression/Experience$", "say": "{cat}'s experience"},
    {"match": r"^(\d+)/GameplayProgression/FreshKill/Value$", "say": "{cat}'s fresh-kill pile"},
    {"match": r"^(\d+)/GameplayProgression/Gameplay\.Combat\.Character\.Cat\.Player/State/Health$", "say": "{cat}'s health"},
    {"match": r"^(\d+)/GameplayProgression/Gameplay\.Combat\.Character\.Cat\.Player/State/Stamina$", "say": "{cat}'s stamina"},
    {"match": r"^(\d+)/GameplayProgression/Stats$", "say": "{cat}'s combat stats"},
    {"match": r"^(\d+)/GameplayProgression/State/Inventory/(.+)$", "say": "{cat}'s {item}"},
    {"match": r"^Shared/SettingsData/(.+)$", "say": "the game's setting {name}"},
    {"match": r"^(\d+)/", "say": "{cat}'s {name}"},
]
ITEM_ROOT = "Gameplay.Inventory."


def range_problem(path, value):
    """Why a value can't go at a path (out of range, or not whole), in words; None when it's fine."""
    for r in RANGES:
        if not re.search(r["match"], path):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"{r['what']} has to be a number"
        if r["whole"] and float(value) != int(value):
            return f"{r['what']} has to be a whole number"
        if value < r["min"] or (r["max"] is not None and value > r["max"]):
            top = f" to {r['max']}" if r["max"] is not None else " or more"
            return f"{r['what']} goes from {r['min']}{top}, not {value}"
        return None
    return None


def words(name):
    """A key in words: "MasterVolume" -> "Master volume", "SmallHealingHerb" -> "Small Healing Herb"."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name.replace(".", " ").replace("_", " ")).strip()
    return spaced[:1].upper() + spaced[1:]


def item_words(tag):
    """An item's name from its tag alone, when the game's names can't be read."""
    rest = tag[len(ITEM_ROOT):] if tag.startswith(ITEM_ROOT) else tag
    parts = rest.split(".")
    return words(" ".join(parts[1:] if len(parts) > 1 else parts))


def label(path, cat_name=None, item_name=None, current_slot=None):
    """A save path in words: "Fawnstar's level". cat_name(slot) and item_name(tag) give names when known."""
    last = words(path.rstrip("/").rsplit("/", 1)[-1])
    for w in WORDS:
        m = re.search(w["match"], path)
        if not m:
            continue
        said = {"name": last.lower()}
        if "{cat}" in w["say"]:
            slot = m.group(1)
            said["cat"] = (cat_name(slot) if cat_name else None) or \
                ("your cat" if slot == current_slot else f"cat slot {slot}")
        if "{item}" in w["say"]:
            said["item"] = (item_name(m.group(2)) if item_name else None) or item_words(m.group(2))
        return w["say"].format(**said)
    return last


class SaveSection(Section):
    id = "save"
    title = "Save edits"
    files = ("save.json",)

    def collect(self, mod, ctx):
        raw = self.read_json(mod, "save.json")
        if not isinstance(raw, dict):
            raise ValueError("save.json should be an object with 'set', 'add' and 'remove'")
        sets = raw.get("set", {}) or {}
        adds = raw.get("add", {}) or {}
        removes = raw.get("remove", []) or []
        if not isinstance(sets, dict) or not isinstance(adds, dict):
            raise ValueError("save.json: 'set' and 'add' must be objects")
        if not isinstance(removes, list) or not all(isinstance(p, str) for p in removes):
            raise ValueError("save.json: 'remove' must be a list of paths")
        if not isinstance(raw.get("always", False), bool):
            raise ValueError("save.json: 'always' must be true or false")
        for obj, entries in adds.items():
            if not isinstance(entries, dict) and not obj.startswith("_"):
                raise ValueError(f"save.json: add.{obj} must map keys to values")
        sets = {k: v for k, v in sets.items() if not k.startswith("_")}
        adds = {k: v for k, v in adds.items() if not k.startswith("_")}
        if not sets and not adds and not removes:
            return None
        return {"set": sets, "add": adds, "remove": removes, "always": bool(raw.get("always"))}

    def build(self, ctx, items):
        if not items:   # nothing to do, so the save isn't read (one wcmods can't read mustn't stop other mods)
            return
        doc = None
        sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
        if os.path.isfile(sav):
            try:
                doc = SaveDoc(SaveGame.load(sav).json_text)
            except (ValueError, OSError):
                ctx.warn("your save couldn't be read, so save edits were skipped this time")
                return
        say = _Words(ctx, doc)
        count = 0
        for mod, data in items:
            # Made once per save, and recorded; "always" makes them at every install, as before.
            flags = {} if data["always"] else {"once": True}
            for path, value in data["set"].items():
                if doc is not None and not doc.exists(path):
                    ctx.warn(f"{mod.id}: your save has no value at {path}; skipped")
                    continue
                problem = range_problem(path, value)
                if problem:
                    ctx.warn(f"{mod.id}: {say(path)}: {problem}; skipped")
                    continue
                ctx.save_op({"op": "set", "path": path, "value": value, "source": mod.id, "label": say(path), **flags})
                count += 1
            for obj, entries in data["add"].items():
                if doc is not None and not isinstance(_get(doc, obj), dict):
                    ctx.warn(f"{mod.id}: {obj} isn't an object in your save; skipped")
                    continue
                for key, value in entries.items():
                    full = f"{obj}/{key}"
                    problem = range_problem(full, value)
                    if problem:
                        ctx.warn(f"{mod.id}: {say(full)}: {problem}; skipped")
                        continue
                    ctx.save_op({"op": "insert", "path": obj, "key": key, "value": value, "source": mod.id,
                                 "label": say(full), **flags})
                    count += 1
            for path in data["remove"]:
                ctx.save_op({"op": "remove", "path": path, "source": mod.id, "label": say(path), **flags})
                count += 1
        if count:
            ctx.note("edits", count)


class _Words:
    """label() with the names this build can read: the cats' (the game's name tables and the names mods on)
    and the items' (the game's item table); without the game's files, places and tags in words."""

    def __init__(self, ctx, doc):
        self.ctx, self.doc = ctx, doc
        self._cats = self._items = None

    def cat(self, slot):
        if self._cats is None:
            self._cats = {}
            try:
                from .. import names
                cats = names.cats_in_save(self.doc.data) if self.doc is not None else []
                if cats:
                    game = names.GameNames(lambda p: self.ctx.game.read_text(self.ctx.data_path(p)))
                    plan = names.Plan(game, names.merge(names.mod_specs(self.ctx.mods)))
                    for c in cats:
                        if c["player"]:
                            self._cats[c["slot"]] = plan.current_name(c["ids"])
            except Exception:   # noqa: BLE001 - no game files (or a broken names.json): slots in words instead
                pass
        return self._cats.get(slot)

    def item(self, tag):
        if self._items is None:
            self._items = {}
            try:
                for _, v in self.ctx.cooked_table("DT_QuestObjectsInfo"):
                    name = v.get("Name")
                    if isinstance(name, dict) and name.get("key") and v.get("itemTag"):
                        self._items[v["itemTag"]] = self.ctx.text(name["key"])
            except Exception:   # noqa: BLE001 - no game files: the tag in words instead
                pass
        return self._items.get(tag)

    def __call__(self, path):
        current = None
        if self.doc is not None:
            try:
                current = str(self.doc.get("Shared/General/CurrentCatSlot"))
            except (KeyError, IndexError, ValueError, TypeError):
                current = None
        return label(path, self.cat, self.item, current)


def _get(doc, path):
    try:
        return doc.get(path)
    except (KeyError, IndexError, ValueError, TypeError):
        return None
