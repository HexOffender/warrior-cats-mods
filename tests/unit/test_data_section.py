"""wcmods/sections/data.py and the merge of every mod's table edits (BuildContext.resolve_csv_edits): a table the
game hasn't got is left out with a warning in page words, not the whole mod; the warnings name the mod; and a
cell two sources change is said."""
import json
import os

import pytest

from wcmods.sdk import BuildContext
from wcmods.sections.data import DataSection

XP = "Enemy,BaseExperience,DifficultyOffset\r\nFish,10,0\r\nMice,25,0\r\n"
TABLES = {"Wrc/Content/Gameplay/DataTables/NonAsset/CombatBaseExperience.csv": XP,
          "Wrc/Content/Gameplay/DataTables/NonAsset/TuningData.csv": "---,MaxValue\r\nRun.Speed,390\r\n",
          "Wrc/Content/Gameplay/DataTables/NonAsset/OnlineGifts.csv": "---,Amount\nMoss,2\n",
          "Wrc/Content/Gameplay/DataTables/NonAsset/TraitsFilters.csv": "---,Weight\nBrave,1\n"}


class Game:
    exists = staticmethod(lambda path: path in TABLES)
    read_text = staticmethod(lambda path: TABLES[path])


class Mod:
    def __init__(self, tmp_path, mod_id, data):
        self.id, self.name = mod_id, mod_id.title()
        self.folder = str(tmp_path / mod_id)
        os.makedirs(self.folder)
        with open(os.path.join(self.folder, "data.json"), "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))


def ctx(tmp_path):
    return BuildContext(None, Game(), str(tmp_path / "out"), log=lambda m: None)


def test_help_key_ignored_and_two_tables_collected(tmp_path):
    mod = Mod(tmp_path, "mine", {"_help": "text", "TuningData.csv": {"Run.Speed": 450},
                                 "CombatBaseExperience.csv": {"*": {"BaseExperience": "x2"}}})
    c = ctx(tmp_path)
    assert DataSection().collect(mod, c) == {"TuningData.csv": {"Run.Speed": 450},
                                             "CombatBaseExperience.csv": {"*": {"BaseExperience": "x2"}}}
    assert c.warnings == []


def test_unknown_table_warns_and_keeps_the_rest(tmp_path):
    mod = Mod(tmp_path, "mine", {"Nope.csv": {"A": 1}, "TuningData.csv": {"Run.Speed": 450}})
    c = ctx(tmp_path)
    assert DataSection().collect(mod, c) == {"TuningData.csv": {"Run.Speed": 450}}
    (w,) = c.warnings
    assert w.startswith("mine: the game has no table 'Nope.csv'") and "Game data page" in w
    assert "wcmods files" not in w and "`" not in w   # no command line for the player
    # Only tables the game hasn't got: nothing left to put in is no data at all, not an error.
    assert DataSection().collect(Mod(tmp_path, "only", {"Nope.csv": {"A": 1}}), ctx(tmp_path)) is None


def test_non_csv_key_or_non_dict_edits_is_an_error(tmp_path):
    for i, data in enumerate(({"Tuning": {"A": 1}}, {"TuningData.csv": None}, {"TuningData.csv": [1]}, [1, 2])):
        with pytest.raises(ValueError):
            DataSection().collect(Mod(tmp_path, f"m{i}", data), ctx(tmp_path))
    with pytest.raises(ValueError, match="line 1"):
        DataSection().collect(Mod(tmp_path, "broken", "{nope"), ctx(tmp_path))


def test_online_and_traits_tables_warn(tmp_path):
    mod = Mod(tmp_path, "mine", {"OnlineGifts.csv": {"Moss": 3}, "TraitsFilters.csv": {"Brave": 2}})
    c = ctx(tmp_path)
    sec = DataSection()
    c.begin("data")
    sec.build(c, [(mod, sec.collect(mod, c))])
    c.end()
    assert any("OnlineGifts.csv feeds the online den-visit features" in w for w in c.warnings)
    assert any("TraitsFilters.csv changes which traits cats get" in w for w in c.warnings)
    assert c.notes["data"]["tables"] == ["OnlineGifts.csv", "TraitsFilters.csv"]


def built(tmp_path, *mods):
    """Every mod's data.json through the section and the merge, as a build does: (table text, changes, warnings)."""
    c = ctx(tmp_path)
    sec = DataSection()
    c.begin("data")
    sec.build(c, [(m, sec.collect(m, c)) for m in mods])
    c.end()
    changes, failures = c.resolve_csv_edits()
    assert failures == []
    path = "Wrc/Content/Gameplay/DataTables/NonAsset/CombatBaseExperience.csv"
    return c.files[path][0].decode(), changes.get(path, []), c.warnings


def test_two_mods_same_table_queue_in_priority_order(tmp_path):
    low = Mod(tmp_path, "double-xp", {"CombatBaseExperience.csv": {"*": {"BaseExperience": "x2"}}})
    high = Mod(tmp_path, "more-xp", {"CombatBaseExperience.csv": {"*": {"BaseExperience": "x2"}}})
    text, changes, _ = built(tmp_path, low, high)
    assert "Fish,40,0" in text and "Mice,100,0" in text   # x2 then x2: x4, as documented
    assert [c["by"] for c in changes] == ["double-xp", "double-xp", "more-xp", "more-xp"]


def test_same_cell_from_two_sources_warns(tmp_path):
    a = Mod(tmp_path, "double-xp", {"CombatBaseExperience.csv": {"*": {"BaseExperience": "x2"}}})
    b = Mod(tmp_path, "my-tweaks", {"CombatBaseExperience.csv": {"Mice": {"BaseExperience": 30}, "Nope": 1}})
    text, _, warnings = built(tmp_path, a, b)
    assert "Mice,30,0" in text and "Fish,20,0" in text
    assert "my-tweaks changed Mice.BaseExperience in CombatBaseExperience.csv after double-xp; the game gets my-tweaks's" in warnings
    # A problem names the mod it's in, not the section.
    assert "my-tweaks: CombatBaseExperience.csv: no row 'Nope'" in warnings


def test_one_files_star_then_its_row_is_not_a_conflict(tmp_path):
    a = Mod(tmp_path, "mine", {"CombatBaseExperience.csv": {"*": {"BaseExperience": "x2"}, "Mice": {"BaseExperience": 25}}})
    text, changes, warnings = built(tmp_path, a)
    assert "Mice,25,0" in text and "Fish,20,0" in text and warnings == []
    assert changes == [{"row": "Fish", "column": "BaseExperience", "from": "10", "to": "20", "by": "mine"}]
