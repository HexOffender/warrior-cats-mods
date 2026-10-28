"""The Save page's routes, through Studio.api over a temp save: the save with the cat being played and the words
and ranges the page uses, Change my save now (refused while the game runs; backed up, written and recorded), Put
it back, and the list of what's been done."""
import os
import time

import pytest

from wcmods import saverecord
from wcmods.formats.save import SAV_NAME, SaveGame, list_backups
from wcmods.formats.savejson import SaveDoc
from wcmods.sections import savedit

from unit_helpers import write_save

LEVEL = "1/GameplayProgression/Level"
INV = "1/GameplayProgression/State/Inventory"
SAVE = {"acct": {"0": {"GameplayProgression": {"Level": 2}},
                 "1": {"GameplayProgression": {"Level": 5, "FreshKill": {"Value": 62},
                                               "State": {"Inventory": {"Gameplay.Inventory.Materials.Moss": 4}}}},
                 "Shared": {"General": {"CurrentCatSlot": 1}}}}


def call(st, method, path, body=None):
    return st.api(method, [p for p in path.split("/") if p], dict(body or {}), None)


def doc(studio):
    return SaveDoc(SaveGame.load(os.path.join(studio.ctx.cfg.save_dir, SAV_NAME)).json_text)


@pytest.fixture
def saved(studio):
    write_save(studio.ctx.cfg.save_dir, SAVE)
    return studio


def test_apply_refuses_while_the_game_runs(saved, sandbox):
    sandbox.running = True
    with pytest.raises(RuntimeError, match="close the game before changing your save"):
        call(saved, "POST", "save/apply", {"changes": [{"path": LEVEL, "value": 20}]})
    with pytest.raises(RuntimeError, match="close the game"):
        call(saved, "POST", "save/undo", {"source": "studio", "path": LEVEL})
    assert doc(saved).get(LEVEL) == 5


def test_apply_backs_up_writes_and_records(saved):
    r = call(saved, "POST", "save/apply", {"changes": [
        {"path": LEVEL, "value": 20}, {"path": "1/GameplayProgression/FreshKill/Value", "value": 100},
        {"add": INV, "key": "Gameplay.Inventory.Consumable.SmallCatnip", "value": 5},
        {"remove": f"{INV}/Gameplay.Inventory.Materials.Moss"}]})
    d = doc(saved)
    assert d.get(LEVEL) == 20 and d.get("1/GameplayProgression/FreshKill/Value") == 100
    assert d.get(f"{INV}/Gameplay.Inventory.Consumable.SmallCatnip") == 5 and not d.exists(f"{INV}/Gameplay.Inventory.Materials.Moss")
    assert r["backup"] == list_backups(saved.ctx.backups)[-1]
    assert {a["label"]: (a["was"], a["now"]) for a in r["applied"]} == {
        "your cat's level": (5, 20), "your cat's fresh-kill pile": (62, 100),
        "your cat's Small Catnip": (None, 5), "your cat's Moss": (4, None)}
    assert any("your cat's level: 5 -> 20" in line for line in r["log"])
    assert saverecord.entry(saverecord.load(saved.ctx.cfg), "acct", "studio", LEVEL)["was"] == 5
    # Out of range, or a path the save hasn't got: refused in words, nothing written.
    for change, said in (({"path": LEVEL, "value": 25}, "Level goes from 1 to 20, not 25"),
                         ({"path": LEVEL, "value": 2.5}, "has to be a whole number"),
                         ({"path": "1/Nope", "value": 1}, "your save has no value there"),
                         ({"add": "1/Nope", "key": "x", "value": 1}, "nowhere to add it"),
                         ({"nothing": 1}, "a change needs a path and a value")):
        with pytest.raises(ValueError, match=said):
            call(saved, "POST", "save/apply", {"changes": [change]})
    with pytest.raises(ValueError, match="no changes"):
        call(saved, "POST", "save/apply", {"changes": []})
    # The page's own change is made even when the record has it: it's asked for now.
    call(saved, "POST", "save/apply", {"changes": [{"path": LEVEL, "value": 12}]})
    call(saved, "POST", "save/apply", {"changes": [{"path": LEVEL, "value": 20}]})
    assert doc(saved).get(LEVEL) == 20


def test_undo_writes_the_old_value_and_marks_the_record(saved):
    call(saved, "POST", "save/apply", {"changes": [{"path": LEVEL, "value": 20},
                                                   {"add": INV, "key": "Gameplay.Inventory.Consumable.SmallCatnip", "value": 5}]})
    time.sleep(1.1)
    r = call(saved, "POST", "save/undo", {"source": "studio", "path": LEVEL})
    assert r["before"] == 20 and r["now"] == 5 and r["label"] == "your cat's level" and doc(saved).get(LEVEL) == 5
    herb = f"{INV}/Gameplay.Inventory.Consumable.SmallCatnip"
    call(saved, "POST", "save/undo", {"source": "studio", "path": herb})
    assert not doc(saved).exists(herb), "an item that wasn't there goes again"
    applied = call(saved, "GET", "save/applied")["changes"]
    assert all(c["undone"] and not c["can_undo"] for c in applied)
    with pytest.raises(ValueError, match="needs \"source\""):
        call(saved, "POST", "save/undo", {"path": LEVEL})


def test_applied_lists_newest_first(saved):
    call(saved, "POST", "save/apply", {"changes": [{"path": LEVEL, "value": 20}]})
    time.sleep(1.1)
    call(saved, "POST", "save/apply", {"changes": [{"path": "1/GameplayProgression/FreshKill/Value", "value": 100}]})
    changes = call(saved, "GET", "save/applied")["changes"]
    assert [c["label"] for c in changes] == ["your cat's fresh-kill pile", "your cat's level"]
    assert changes[1]["current"] == 20 and changes[1]["was"] == 5 and changes[1]["can_undo"] is True
    assert changes[1]["source"] == "studio" and changes[1]["path"] == LEVEL


def test_save_without_a_file_is_a_404_in_page_words(studio):
    with pytest.raises(LookupError, match="no save yet; start the game once"):
        call(studio, "GET", "save")
    assert call(studio, "GET", "save/applied") == {"changes": []}
    with pytest.raises(LookupError):
        call(studio, "POST", "save/apply", {"changes": [{"path": LEVEL, "value": 2}]})


def test_save_names_the_current_cat(saved, sandbox):
    r = call(saved, "GET", "save")
    assert r["current_cat"] == {"slot": "1", "name": None}   # no game: the page says "your cat"
    assert r["account"] == "acct" and r["data"]["1"]["GameplayProgression"]["Level"] == 5
    assert r["words"] == savedit.WORDS and r["ranges"] == savedit.RANGES and r["game_running"] is False
    sandbox.running = True
    assert call(saved, "GET", "save")["game_running"] is True
