"""The mod menu's pages built on WCModsGame: the overview, your cat, the world, travel, items, quests, the
fight, the game's developer switches, the log and the menu's own settings, and (with code mods allowed)
an inspector and a Lua console.

They're part of the menu host's script (menu.host_script puts them in), so they use its locals: Menu,
SETTINGS, THEME, valid, log, HOST (the status line), everySecond (work done once a second), size, fit,
win and setPaused. Each page is in a function of its own, which keeps the host's main chunk under Lua's
200-local limit. data() is what the build hands them from the game's tables: area names and quest titles.
"""
import os
from .lua import source as lua_source

# Items the Items page can drop by your cat: every consumable and material in the game's tables.
ITEMS = (
    "Consumable.SmallHealingHerb", "Consumable.MediumHealingHerb", "Consumable.BigHealingHerb",
    "Consumable.FullHealingHerb", "Consumable.SuperHealingHerb", "Consumable.HealingHerbPouch",
    "Consumable.SmallCatnip", "Consumable.MediumCatnip", "Consumable.BigCatnip", "Consumable.CatnipPouch",
    "Consumable.ThistlePouch", "Consumable.FishScalePouch", "Consumable.CatThymePouch", "Consumable.FeatherPouch",
    "Consumable.HerbSpicesPouch", "Consumable.EyewortPouch", "Consumable.ChamomilePouch",
    "Consumable.AntidoteHerbPouch", "Consumable.ValerianRootPouch", "Consumable.PeppermintPouch",
    "Consumable.GingerRootPouch", "Consumable.ChestnutPouch", "Consumable.LavenderPouch", "Consumable.TurmericPouch",
    "Consumable.SagePouch",
    "Materials.BerryFern", "Materials.Birdnest", "Materials.Bone", "Materials.Borage", "Materials.Broom",
    "Materials.Burdock", "Materials.CattailReed", "Materials.Cobwebs", "Materials.Comfrey", "Materials.Cotton",
    "Materials.Dandelion", "Materials.DirtMound", "Materials.Fur", "Materials.Goldenrod", "Materials.Heather",
    "Materials.Ivy", "Materials.Juniper", "Materials.Leaves", "Materials.Moss", "Materials.Oakgall", "Materials.Pine",
    "Materials.Poppy", "Materials.Rock", "Materials.Rope", "Materials.SharpeningTreeBark", "Materials.Thyme",
    "Materials.Willow",
)


def data(read_text=None, cfg=None):
    """What the pages need from the game and the install: area names by code ("R-05" -> "Willow-Weep"),
    quest titles by tag and rank, and where the UE4SS log and the saved travel spots are. Without the
    game's files the names are left out, and the pages show codes and tags instead."""
    from .formats import csvdata
    out = {"areas": {}, "quests": {}, "items": list(ITEMS), "log": "", "places": ""}
    if cfg is not None:
        try:
            out["log"] = os.path.join(cfg.win64_dir, "ue4ss", "UE4SS.log")
        except Exception:   # no game found
            pass
        out["places"] = os.path.join(os.path.dirname(os.path.normpath(cfg.save_dir)), "WCMods", "places.json")
    if read_text is None:
        return out
    try:
        strings = csvdata.Table(read_text("Wrc/Content/Gameplay/Strings/NonAsset/Strings_EN.csv"))
        en = {r.fields[0]: r.fields[1] for r in strings.rows if len(r.fields) > 1}
        base = "Wrc/Content/Gameplay/DataTables/NonAsset/"
        locations = csvdata.Table(read_text(base + "LocationsData.csv"))
        code, name = locations.column("Code"), locations.column("IdStrName")
        for r in locations.rows:
            if len(r.fields) > max(code, name):
                out["areas"][r.fields[code]] = en.get(r.fields[name], r.fields[code])
        dialogues = csvdata.Table(read_text(base + "QuestDialogues.csv"))
        key = dialogues.column("StringKey")
        for r in dialogues.rows:
            tag = r.fields[0] if r.fields else ""
            if tag.endswith(".Title") and len(r.fields) > key:
                quest, _, rank = tag[:-len(".Title")].rpartition(".")
                out["quests"].setdefault(quest, {})[rank] = en.get(r.fields[key], r.fields[key])
    except Exception:   # a table that can't be read leaves those names out
        pass
    return out


LUA = lua_source("menupages.lua")


def lua(info=None):
    """The pages' Lua, with what data() found (or nothing: codes and tags show instead of names)."""
    from .sdk import lua_value
    return LUA.replace("@DATA@", lua_value(info if info is not None else data()))
