"""Save edits (save.json), applied to WrcGame.sav on install after a backup.

    {
      "set": { "0/GameplayProgression/Experience": 500, "Shared/SettingsData/Minimap": false },
      "add": { "0/GameplayProgression/State/Inventory": { "Gameplay.Inventory.Consumable.SmallCatnip": 5 } }
    }

Paths start inside the save's account object; see savejson.py.
"""
import os

from ..formats.save import SAV_NAME, SaveGame
from ..formats.savejson import SaveDoc
from ..sdk import Section


class SaveSection(Section):
    id = "save"
    title = "Save edits"
    files = ("save.json",)

    def collect(self, mod, ctx):
        raw = self.read_json(mod, "save.json")
        sets = raw.get("set", {}) or {}
        adds = raw.get("add", {}) or {}
        if not isinstance(sets, dict) or not isinstance(adds, dict):
            raise ValueError("save.json: 'set' and 'add' must be objects")
        for obj, entries in adds.items():
            if not isinstance(entries, dict):
                raise ValueError(f"save.json: add.{obj} must map keys to values")
        if not sets and not adds:
            return None
        return {"set": {k: v for k, v in sets.items() if not k.startswith("_")}, "add": adds}

    def build(self, ctx, items):
        doc = None
        sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
        if os.path.isfile(sav):
            doc = SaveDoc(SaveGame.load(sav).json_text)
        count = 0
        for mod, data in items:
            for path, value in data["set"].items():
                if doc is not None and not doc.exists(path):
                    ctx.warn(f"{mod.id}: your save has no value at {path}; skipped")
                    continue
                ctx.edit_save(path, value, source=mod.id)
                count += 1
            for obj, entries in data["add"].items():
                if doc is not None and not isinstance(_get(doc, obj), dict):
                    ctx.warn(f"{mod.id}: {obj} isn't an object in your save; skipped")
                    continue
                for key, value in entries.items():
                    ctx.add_save_key(obj, key, value, source=mod.id)
                    count += 1
        if count:
            ctx.note("edits", count)


def _get(doc, path):
    try:
        return doc.get(path)
    except (KeyError, IndexError, ValueError, TypeError):
        return None
