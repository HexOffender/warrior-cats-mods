"""The Game data page's routes, through Studio.api over the made-up game (tests/studio/fixtures/game.py): its
tables and their kinds, a table with the English for its text keys, the index the page searches, and what
saving a data.json says about it."""
import json
import os

import pytest

from wcmods import studio as studio_mod
from unit_helpers import make_mod


def get(st, path):
    return st.api("GET", [p for p in path.split("/") if p], {}, None)


def put(st, path, body):
    return st.api("PUT", [p for p in path.split("/") if p], body, None)


def test_game_data_lists_tables_and_kinds(studio, data_game):
    r = get(studio, "game/data")
    assert "TuningData.csv" in r["tables"] and "NPC/Scars.csv" in r["tables"]
    assert r["kinds"]["OnlineGifts.csv"] == "online" and r["kinds"]["TuningData.csv"] == "gameplay"
    assert r["hidden"] == ["HeightMap/L_Test_Height_0.csv"]   # map data: the page doesn't list it


def test_a_table_comes_with_its_english_texts(studio, data_game):
    r = get(studio, "game/data/AttackMove.csv")
    assert r["name"] == "AttackMove.csv" and r["header"] == ["#", "Name", "Power", "Stance"]
    assert r["rows"][0] == ["1", "STR_ATTACK_QUICK_CLAW", "10", "Offensive"]
    assert r["texts"] == {"STR_ATTACK_QUICK_CLAW": "Quick Claw", "STR_ATTACK_POUNCE": "Pounce", "STR_ATTACK_DODGE": "Dodge"}
    assert get(studio, "game/data/NPC/Scars.csv")["header"][0] == ""   # a header the page shows as "Row"
    assert get(studio, "game/data/TuningData.csv")["texts"] == {}


def test_a_missing_table_is_a_400_in_page_words(studio, data_game):
    with pytest.raises(ValueError) as e:
        get(studio, "game/data/Nope.csv")
    assert str(e.value) == "the game has no table 'Nope.csv'; the Game data page lists the ones it has"


def test_the_index_names_every_table_and_its_rows(studio, data_game):
    index = get(studio, "game/data/index")["tables"]
    assert set(index) == set(data_game.TABLES) - {"HeightMap/L_Test_Height_0.csv"}
    run = "Gameplay.Exploration.Player.MoveAndRun.Run.Speed"
    assert run in index["TuningData.csv"]["rows"]
    assert index["TuningData.csv"]["descriptions"][run] == "The target maximum speed of the cat while running."
    assert "Gameplay.Combat.Rest.Stamina" not in index["TuningData.csv"]["descriptions"]   # no description: none
    assert index["CombatBaseExperience.csv"] == {"rows": ["Fish", "WeakMice", "Mice", "Squirrel", "Rabbit", "Bird",
                                                          "Rat", "Badger"], "descriptions": {}}
    assert get(studio, "game/data/index") is not None and studio._data_index is index   # read once


def test_put_data_json_refuses_broken_json_and_adds_a_newline(studio, data_game):
    folder = make_mod(studio, "mine")
    with pytest.raises(ValueError):
        put(studio, "mods/mine/file/data.json", {"text": "{broken"})
    r = put(studio, "mods/mine/file/data.json", {"text": json.dumps({"TuningData.csv": {"x": 1}})})
    assert r["problems"] == [] and r["notes"] == []
    with open(f"{folder}/data.json", encoding="utf-8") as f:
        assert f.read().endswith("}\n")


def test_check_file_shows_an_unknown_table_as_a_note(studio, data_game):
    make_mod(studio, "mine")
    r = put(studio, "mods/mine/file/data.json", {"text": json.dumps({"Nope.csv": {"A": 1}, "TuningData.csv": {"x": 1}})})
    assert r["problems"] == []
    assert r["notes"] == ["the game has no table 'Nope.csv', so its edits are left out (the Game data page lists "
                          "the tables the game has)"]
    # A file that isn't data.json's shape at all is still a problem.
    r = put(studio, "mods/mine/file/data.json", {"text": json.dumps({"TuningData.csv": None})})
    assert r["problems"] and "should be a table name ending in .csv" in r["problems"][0] and r["notes"] == []


NONASSET = "Wrc/Content/Gameplay/DataTables/NonAsset/"


def test_table_lines_say_each_cell_once_in_words(studio):
    manifest = {"names": {"my-mods": "My mods", "double-xp": "Double XP"}, "csv_changes": {
        NONASSET + "TuningData.csv": [
            {"row": "Gameplay.Exploration.Player.MoveAndRun.Run.Speed", "column": "MaxValue", "from": "390", "to": "450", "by": "my-mods"},
            {"row": "Gameplay.Exploration.MaxLevel", "column": "MaxValue", "from": "20", "to": "25", "by": "my-mods"}],
        NONASSET + "CombatBaseExperience.csv": [
            {"row": "Mice", "column": "BaseExperience", "from": "25", "to": "50", "by": "double-xp"},
            {"row": "Mice", "column": "BaseExperience", "from": "50", "to": "25", "by": "my-mods"},   # back where it began
            {"row": "Fish", "column": "BaseExperience", "from": "10", "to": "20", "by": "double-xp"},
            {"row": "Fish", "column": "BaseExperience", "from": "20", "to": "30", "by": "my-mods"},
            {"row": "Owl", "column": "(row)", "from": "", "to": "added", "by": "my-mods"}],
        NONASSET + "QuestObjectives.csv": [{"row": "Q1", "column": "Count", "from": "1", "to": "2", "by": "my-mods"}],
        "Wrc/Content/Gameplay/Strings/NonAsset/Strings_EN.csv": [{"row": "STR_X", "column": "Text", "from": "A", "to": "B", "by": "n"}]}}
    assert studio_mod.table_lines(manifest, studio._data_words()) == [
        "Tuning: Running speed 390 -> 450 (My mods)",
        "Tuning: Gameplay.Exploration.MaxLevel 20 -> 25 (My mods)",
        "XP from fights: Fish, BaseExperience 10 -> 30 (My mods)",
        "Quest objectives: Q1, Count 1 -> 2 (My mods)"]
    # Without the page's words, the rows and columns as they are; and never more than 20 lines.
    many = {"csv_changes": {NONASSET + "T.csv": [{"row": f"R{i}", "column": "V", "from": "1", "to": "2", "by": "m"} for i in range(25)]}}
    lines = studio_mod.table_lines(many)
    assert len(lines) == 21 and lines[0] == "T: R0, V 1 -> 2 (m)" and lines[-1] == "and 5 more numbers"
    assert studio_mod.table_words("NPC/FurPattern1Color.csv") == "NPC fur pattern 1 color"


def test_an_install_and_last_apply_say_its_cells_in_words(studio):
    manifest = {"mods": ["my-mods"], "names": {"my-mods": "My mods"}, "sections": {}, "warnings": [], "csv_changes": {
        NONASSET + "TuningData.csv": [
            {"row": "Gameplay.Exploration.Player.MoveAndRun.Run.Speed", "column": "MaxValue", "from": "390", "to": "600", "by": "my-mods"}]}}
    r = studio.run(lambda log: manifest, "Apply to game", keep=True)
    assert r["result"]["cells_in_words"] == ["Tuning: Running speed 390 -> 600 (My mods)"]
    with open(os.path.join(studio.ctx.cfg.data_dir, studio_mod.LAST_APPLY), encoding="utf-8") as f:
        assert "Tuning: Running speed 390 -> 600 (My mods)" in f.read().split("\n\n")[0]
    # Play hands its manifest back inside its result: the same there.
    r = studio.run(lambda log: {"started": True, "manifest": dict(manifest)}, "Play", keep=True)
    assert r["result"]["manifest"]["cells_in_words"] == ["Tuning: Running speed 390 -> 600 (My mods)"]
    assert "cells_in_words" not in studio.run(lambda log: {"restored": []}, "Something")["result"]
