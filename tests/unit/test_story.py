"""Cats and questlines as data (story.py, sections/story.py), mod packs (packs.py) and mods made in the
studio noting the game's build. No game needed."""
import json
import os
import zipfile

import pytest

from wcmods import luacheck, modzip, packs, story
from wcmods import mods as modlib
from wcmods.config import Config
from wcmods.exe import gamebuild
from wcmods.sections.story import script

NPCS = {"npcs": [
    {"id": "mossfoot", "name": "Mossfoot", "title": "Elder", "colours": {"fur": "#7A6A58"}, "eyes": 6, "size": 0.8,
     "lines": ["Hello."]},
    {"id": "sparrowpaw", "name": "Sparrowpaw", "at": [-60040.4, -200, 813], "yaw": 90, "level": "L_WorldMap_01_P"},
]}
QUESTS = {"quests": [
    {"id": "first", "title": "First", "giver": "mossfoot", "steps": [
        {"do": "talk", "lines": ["Bring me moss?"]},
        {"do": "collect", "item": "Gameplay.Inventory.Materials.Moss", "count": 2},
        {"do": "visit", "place": "medicine-cat"},
        {"do": "visit", "at": [1, 2, 3], "radius": 250, "objective": "Go to the oak"}],
     "reward": {"Gameplay.Inventory.Consumable.SmallHealingHerb": 2}},
    {"id": "second", "title": "Second", "after": ["first"], "steps": [{"do": "talk", "npc": "sparrowpaw", "lines": ["Hi"]}]},
]}


def test_cats_and_quests_read_as_the_game_gets_them():
    data = story.read(NPCS, QUESTS)
    moss, sparrow = data["npcs"]
    assert moss["colours"] == {"fur": "#7a6a58"} and "yaw" not in moss and moss["lines"] == ["Hello."]
    assert sparrow["at"] == [-60040, -200, 813] and sparrow["yaw"] == 90 and sparrow["lines"] == []
    first, second = data["quests"]
    assert first["steps"][0]["npc"] == "mossfoot"                       # the giver, when the step names nobody
    assert first["steps"][2] == {"do": "visit", "place": "medicine-cat", "class": "BP_Quest_Giver_Bartering_C", "radius": 400}
    assert first["steps"][3]["radius"] == 250 and first["steps"][3]["objective"] == "Go to the oak"
    assert second["after"] == ["first"]
    assert story.items_used(data) == {"Gameplay.Inventory.Materials.Moss", "Gameplay.Inventory.Consumable.SmallHealingHerb"}
    assert story.read(None, None) == {"npcs": [], "quests": []}


@pytest.mark.parametrize("change, said", [
    (lambda n, q: n["npcs"][0].update(colours={"fur": "brown"}), "should be like"),
    (lambda n, q: n["npcs"][0].update(eyes=30), "\"eyes\""),
    (lambda n, q: n["npcs"].append(dict(n["npcs"][0])), "two cats have this id"),
    (lambda n, q: n["npcs"][0].update(hat="yes"), "unknown key"),
    (lambda n, q: q["quests"][0].update(giver="nobody"), "isn't one of this mod's cats"),
    (lambda n, q: q["quests"][0].update(after=["second"]), "each wait for the other"),
    (lambda n, q: q["quests"][1].update(after=["third"]), "isn't one of this mod's quests"),
    (lambda n, q: q["quests"][0]["steps"].append({"do": "collect", "item": "Moss"}), "whole tag"),
    (lambda n, q: q["quests"][0]["steps"].append({"do": "talk"}), "\"lines\""),
    (lambda n, q: q["quests"][0]["steps"].append({"do": "visit", "place": "the moon"}), "\"place\""),
    (lambda n, q: q["quests"][0]["steps"].append({"do": "dance"}), "\"do\""),
    (lambda n, q: q["quests"][0].update(steps=[]), "at least one step"),
    (lambda n, q: q["quests"][0].update(reward={"Gameplay.Inventory.Materials.Moss": 0}), "whole number"),
])
def test_mistakes_say_what_to_fix(change, said):
    n, q = json.loads(json.dumps(NPCS)), json.loads(json.dumps(QUESTS))
    change(n, q)
    with pytest.raises(ValueError, match=said.replace("\"", ".").replace("(", ".").replace(")", ".")):
        story.read(n, q)


def test_the_games_script_shares_them_as_json_text():
    class M:
        id, name = "my-mod", 'My "quoted" mod'
    text = story.bundle([(M, story.read(NPCS, QUESTS))])
    lua = script(text)
    assert not luacheck.check(lua)
    assert story.SHARED_VARIABLE in lua and "SetSharedVariable" in lua
    data = json.loads(text)
    assert data["format"] == story.FORMAT and data["mods"][0]["name"] == 'My "quoted" mod'
    assert data["mods"][0]["quests"][1]["id"] == "second"


def _mod(root, mod_id, **meta):
    folder = os.path.join(root, mod_id)
    os.makedirs(folder)
    with open(os.path.join(folder, "mod.json"), "w", encoding="utf-8") as f:
        json.dump({"name": mod_id.title(), "enabled": True, **meta}, f)
    return folder


def test_a_mod_pack_carries_its_mods_and_plays_on_its_own(tmp_path):
    data = str(tmp_path / "data")
    cfg = Config(str(tmp_path), data)
    root = cfg.mods_root
    _mod(root, "sandbox")
    story_folder = _mod(root, "story", requires=["sandbox"])
    with open(os.path.join(story_folder, "npcs.json"), "w", encoding="utf-8") as f:
        json.dump(NPCS, f)
    _mod(root, "mine")
    _mod(root, "menu-pages")
    _mod(root, "off", enabled=False)
    found = modlib.discover(root)
    p = packs.save(root, found, "moonlit", "Moonlit", ["story"], description="A story", author="Me", version="1.0",
                   game_build=123)
    assert p.meta["pack"] is True and p.requires == ["story"] and p.meta["game_builds"] == [123]
    assert "mod pack" in p.kinds() and p.to_dict()["pack"]
    found = modlib.discover(root)
    desc = packs.describe(cfg, found)["packs"][0]
    assert [(m["id"], m["direct"]) for m in desc["mods"]] == [("story", True), ("sandbox", False)]
    with pytest.raises(ValueError, match="mod pack itself"):
        packs.save(root, found, "bigger", "Bigger", ["moonlit"])
    # A pack has nothing of the game's in it, so it never counts as made for an older build.
    assert "moonlit" not in gamebuild.outdated(cfg, [m for m in found if m.id == "moonlit"], build=999)

    # Played on its own: its mods on, the rest off, but the in-game menu's pages that were on stay.
    changed = packs.play(cfg, found, "moonlit")
    on = {m.id for m in modlib.discover(root) if m.enabled}
    assert on == {"moonlit", "story", "sandbox", "menu-pages"} and changed["off"] == ["mine"]
    assert packs.describe(cfg, modlib.discover(root))["playing"] == "moonlit"
    packs.play(cfg, modlib.discover(root), "moonlit")   # again: what was on before the first time is kept
    packs.stop(cfg, modlib.discover(root))
    assert {m.id for m in modlib.discover(root) if m.enabled} == {"sandbox", "story", "mine", "menu-pages"}
    assert "pack_before" not in Config(str(tmp_path), data).data

    # Its .zip has every mod in it, and adding it somewhere else adds them all, on.
    found = modlib.discover(root)
    blob = modzip.pack(next(m for m in found if m.id == "moonlit"), found)
    with zipfile.ZipFile(__import__("io").BytesIO(blob)) as z:
        assert {n.split("/")[0] for n in z.namelist()} == {"moonlit", "story", "sandbox"}
    zpath = tmp_path / "moonlit.zip"
    zpath.write_bytes(blob)
    other = tmp_path / "other"
    seen = modzip.inspect(str(zpath), str(other))
    assert "mod pack" in next(s for s in seen if s["id"] == "moonlit")["kinds"]
    modzip.add_zip(str(zpath), str(other), str(tmp_path / "backups"))
    assert {m.id for m in modlib.discover(str(other)) if m.enabled} == {"moonlit", "story", "sandbox"}


def test_mods_made_in_the_studio_note_the_games_build(tmp_path):
    m = modlib.create(str(tmp_path), "fresh", game_build=26184573)
    assert gamebuild.made_for(m) == [26184573]
    old = modlib.create(str(tmp_path), "old")
    assert gamebuild.made_for(old) == list(gamebuild.ASSUMED_BUILDS)
