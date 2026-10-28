"""wcmods/sections/savedit.py: save.json read, checked against the save and the ranges the game takes, and turned
into save edits that say what they change in words."""
import json
import os

import pytest

from wcmods.formats.save import SAV_NAME
from wcmods.sdk import BuildContext
from wcmods.sections import savedit
from wcmods.sections.savedit import SaveSection

from unit_helpers import write_save

SAVE = {"acct": {"1": {"GameplayProgression": {"Level": 5, "Experience": 120, "FreshKill": {"Value": 62},
                                               "State": {"Inventory": {"Gameplay.Inventory.Materials.Moss": 4}}}},
                 "Shared": {"General": {"CurrentCatSlot": 1}, "SettingsData": {"MasterVolume": 1}}}}


class NoGame:
    def __getattr__(self, name):
        raise OSError("the game's files can't be read")


class Mod:
    def __init__(self, tmp_path, mod_id, data):
        self.id = mod_id
        self.folder = str(tmp_path / "mods" / mod_id)
        os.makedirs(self.folder, exist_ok=True)
        with open(os.path.join(self.folder, "save.json"), "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))


def build(studio, tmp_path, *mods):
    ctx = BuildContext(studio.ctx.cfg, NoGame(), str(tmp_path / "out"), log=lambda m: None)
    sec = SaveSection()
    ctx.begin("save")
    sec.build(ctx, [(m, d) for m in mods for d in [sec.collect(m, ctx)] if d is not None])
    ctx.end()
    return ctx


def test_collect_shapes_and_help_key(tmp_path):
    sec = SaveSection()
    got = sec.collect(Mod(tmp_path, "a", {"_help": "x", "set": {"_help": "y", "1/GameplayProgression/Level": 9},
                                          "add": {}, "remove": ["1/X"]}), None)
    assert got == {"set": {"1/GameplayProgression/Level": 9}, "add": {}, "remove": ["1/X"], "always": False}
    assert sec.collect(Mod(tmp_path, "b", {"set": {}, "add": {}}), None) is None
    assert sec.collect(Mod(tmp_path, "c", {"remove": ["1/X"], "always": True}), None)["always"] is True
    for i, bad in enumerate(({"set": "x"}, {"add": {"1/State": 5}}, {"remove": "1/X"}, {"remove": [1]},
                             {"always": "yes"}, [1])):
        with pytest.raises(ValueError):
            sec.collect(Mod(tmp_path, f"bad{i}", bad), None)


def test_build_with_no_items_and_an_unreadable_save_does_not_raise(studio, tmp_path):
    saves = studio.ctx.cfg.save_dir
    with open(os.path.join(saves, SAV_NAME), "wb") as f:
        f.write(b"GVAS not really a save")
    ctx = build(studio, tmp_path)   # no save.json at all: the save isn't even read
    assert ctx.warnings == [] and ctx.save_ops == []
    ctx = build(studio, tmp_path, Mod(tmp_path, "mine", {"set": {"1/GameplayProgression/Level": 9}}))
    assert ctx.save_ops == [] and ctx.warnings == ["save: your save couldn't be read, so save edits were skipped this time"]


def test_build_warns_and_skips_missing_paths_and_out_of_range_values(studio, tmp_path):
    write_save(studio.ctx.cfg.save_dir, SAVE)
    ctx = build(studio, tmp_path, Mod(tmp_path, "mine", {
        "set": {"1/GameplayProgression/Level": 25, "1/GameplayProgression/Experience": 500, "1/Nope": 1,
                "1/GameplayProgression/FreshKill/Value": 101, "Shared/SettingsData/MasterVolume": 0.5},
        "add": {"1/GameplayProgression/State/Inventory": {"Gameplay.Inventory.Consumable.SmallCatnip": -1,
                                                          "Gameplay.Inventory.Materials.Moss": 2.5,
                                                          "Gameplay.Inventory.Materials.Stick": 3},
                "1/GameplayProgression/Level": {"x": 1}}}))
    assert [(o["op"], o.get("path"), o.get("key"), o["value"]) for o in ctx.save_ops] == [
        ("set", "1/GameplayProgression/Experience", None, 500), ("set", "Shared/SettingsData/MasterVolume", None, 0.5),
        ("insert", "1/GameplayProgression/State/Inventory", "Gameplay.Inventory.Materials.Stick", 3)]
    w = "\n".join(ctx.warnings)
    assert "your cat's level: Level goes from 1 to 20, not 25; skipped" in w
    assert "your save has no value at 1/Nope" in w and "The fresh-kill pile goes from 0 to 100, not 101" in w
    assert "your cat's Small Catnip: A count of things carried goes from 0 or more, not -1" in w
    assert "has to be a whole number" in w and "1/GameplayProgression/Level isn't an object" in w


def test_remove_queues_a_delete_op(studio, tmp_path):
    write_save(studio.ctx.cfg.save_dir, SAVE)
    ctx = build(studio, tmp_path, Mod(tmp_path, "mine", {"remove": ["1/GameplayProgression/State/Inventory/Gameplay.Inventory.Materials.Moss"]}))
    (op,) = ctx.save_ops
    assert op["op"] == "remove" and op["once"] is True and op["source"] == "mine" and op["section"] == "save"
    # "always": made at every install, as before: not once.
    ctx = build(studio, tmp_path, Mod(tmp_path, "every", {"set": {"1/GameplayProgression/Level": 9}, "always": True}))
    assert "once" not in ctx.save_ops[0]


def test_ops_carry_a_label_in_words(studio, tmp_path):
    write_save(studio.ctx.cfg.save_dir, SAVE)
    ctx = build(studio, tmp_path, Mod(tmp_path, "mine", {
        "set": {"1/GameplayProgression/Level": 9, "Shared/SettingsData/MasterVolume": 0.5},
        "add": {"1/GameplayProgression/State/Inventory": {"Gameplay.Inventory.Consumable.SmallHealingHerb": 5}}}))
    assert [o["label"] for o in ctx.save_ops] == ["your cat's level", "the game's setting master volume",
                                                  "your cat's Small Healing Herb"]
    # With the cats' names: the cat by name; another slot by its number.
    assert savedit.label("1/GameplayProgression/Level", {"1": "Fawnstar"}.get) == "Fawnstar's level"
    assert savedit.label("0/GameplayProgression/FreshKill/Value", {}.get, None, "1") == "cat slot 0's fresh-kill pile"
    assert savedit.label("Shared/General/CurrentCatSlot") == "Current Cat Slot"
    assert savedit.item_words("Gameplay.Inventory.Cosmetic.Neck.DogCollar.1") == "Neck Dog Collar 1"
