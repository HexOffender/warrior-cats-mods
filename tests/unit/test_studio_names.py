"""The Names page's routes (Studio.names_preview, GET /names/losing, POST /uninstall's "losing") on the tiny game
of tiny_names.py: the cats come from every enabled mod with the page's file in its own mod's place, a cat a
mod named is listed by its name and can be renamed again, a broken names.json elsewhere or a save that can't
be read doesn't stop the page, and taking every mod out says which cats lose their names first. And the page's
guide."""
import json
import os
import re

import pytest

from wcmods import guide, names, pipeline
from wcmods.formats.save import SAV_NAME

from unit_helpers import REPO, make_mod, write_save
from tiny_names import PLACES, cat, reader, save, strings, tiny_game

SPARKLE = cat("Warrior", "STR_CAT_NAME_WCM_FIXED_SPARKLE", "_HEART")   # named Sparkle by a mod
WOOD = cat("Warrior", "STR_CAT_NAME1", "_HEART")                       # Woodheart, the game's own name
PLAYER = cat("Leader", "STR_CAT_NAME53", "_STAR")                      # your cat, Otterstar
NAMED = {"cats": {"Woodheart": {"fixed": "Sparkle"}}}                  # the mod's entry that named it


def call(st, method, path, body=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, None, None)


@pytest.fixture
def names_studio(studio):
    """The studio with the tiny game's name tables, as if read from the game, and a save: your cat, Sparkle and
    Woodheart."""
    studio._names = tiny_game()
    write_save(studio.ctx.cfg.save_dir, {"acct": save(player=PLAYER, warriors=[SPARKLE, WOOD])})
    return studio


def listed(answer):
    return {c["target"]: c for c in answer["cats"]}


def test_get_names_lists_a_mod_named_cat_by_its_name(names_studio):
    make_mod(names_studio, "sparkle", files={"names.json": NAMED})
    r = call(names_studio, "GET", "names")
    one = listed(r)["RiverClan/Warrior/0"]
    assert (one["name"], one["mod_named"], one["name_known"], one["with_mods"]) == ("Sparkle", True, True, "Sparkle")
    assert r["losing_text"] == [] and r["save_problem"] is None and r["current_slot"] == "0"
    assert r["renames"] == [] and r["warnings"] == []   # the page's own file is empty: nothing of its own to do


def test_get_names_with_its_mod_off_names_the_cat_from_its_ids_and_says_it_would_lose_its_name(names_studio):
    make_mod(names_studio, "sparkle", {"enabled": False}, files={"names.json": NAMED})
    r = call(names_studio, "GET", "names")
    one = listed(r)["RiverClan/Warrior/0"]
    assert (one["name"], one["name_known"], one["was"]) == ("Sparkle", False, "STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART")
    assert r["losing_text"] == [{"target": "RiverClan/Warrior/0", "name": "Sparkle",
                                 "key": "STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART"}]


def test_preview_uses_the_pages_spec_for_its_own_mod(names_studio):
    make_mod(names_studio, "mine", files={"names.json": NAMED})
    # The page has taken the entry out, not saved yet: the cat would lose its name at the next Apply.
    r = call(names_studio, "POST", "names/preview", {"spec": {}, "mod": "mine"})
    assert [c["target"] for c in r["losing_text"]] == ["RiverClan/Warrior/0"]
    # Without the mod named, the saved file counts, as on GET.
    assert call(names_studio, "POST", "names/preview", {"spec": {}})["losing_text"] == []


def test_preview_counts_the_pages_mod_while_it_is_off(names_studio):
    make_mod(names_studio, "mine", {"enabled": False}, files={"names.json": NAMED})
    r = call(names_studio, "POST", "names/preview", {"spec": NAMED, "mod": "mine"})
    assert r["losing_text"] == [] and listed(r)["RiverClan/Warrior/0"]["name_known"] is True
    # But the cat it named shows as <MISSING STRING TABLE ENTRY> now, while it's off (the commonest Cat 1): said.
    assert r["mod_off"] is True and r["off_named"] == [
        {"target": "RiverClan/Warrior/0", "name": "Sparkle", "key": "STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART"}]
    assert listed(r)["RiverClan/Warrior/0"]["named_by_off_mod"] is True
    assert listed(r)["RiverClan/Warrior/1"]["named_by_off_mod"] is False
    # A mod not made yet (My mods before its first save) counts too, and isn't off.
    r = call(names_studio, "POST", "names/preview", {"spec": NAMED, "mod": "my-mods"})
    assert r["losing_text"] == [] and r["mod_off"] is False and r["off_named"] == []


def test_preview_with_the_pages_mod_on_says_nothing_is_off(names_studio):
    make_mod(names_studio, "mine", files={"names.json": NAMED})
    r = call(names_studio, "POST", "names/preview", {"spec": NAMED, "mod": "mine"})
    assert r["mod_off"] is False and r["off_named"] == [] and not listed(r)["RiverClan/Warrior/0"]["named_by_off_mod"]


def test_preview_with_the_pages_mod_off_leaves_a_cat_another_mod_names(names_studio):
    make_mod(names_studio, "mine", {"enabled": False})
    make_mod(names_studio, "sparkle", files={"names.json": NAMED})
    r = call(names_studio, "POST", "names/preview", {"spec": {}, "mod": "mine"})
    assert r["mod_off"] is True and r["off_named"] == [] and r["losing_text"] == []


def test_second_rename_of_a_mod_named_cat_reaches_the_save(names_studio):
    make_mod(names_studio, "sparkle", files={"names.json": NAMED})
    r = call(names_studio, "POST", "names/preview", {"spec": {"cats": {"Sparkle": "Otterheart"}}, "mod": "mine"})
    assert r["renames"] == [{"target": "Sparkle", "from": "Sparkle", "to": "Otterheart"}]
    one = listed(r)["RiverClan/Warrior/0"]
    assert one["with_mods"] == "Otterheart" and one["how"] == "parts"
    assert r["changed_names"] == 1 and r["changed_texts"] == 0


def test_a_cat_whose_mod_is_gone_is_renamed_by_its_place_and_ids(names_studio):
    entry = {"name": "Otterheart", "was": "STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART"}
    r = call(names_studio, "POST", "names/preview", {"spec": {"cats": {"RiverClan/Warrior/0": entry}}, "mod": "mine"})
    assert [x["to"] for x in r["renames"]] == ["Otterheart"] and r["losing_text"] == []


def test_preview_keeps_the_pages_warnings_to_its_own_file(names_studio):
    make_mod(names_studio, "other", files={"names.json": {"cats": {"Nobody": "Otterheart"}}})
    r = call(names_studio, "POST", "names/preview",
             {"spec": {"prefixes": {"rename": {"Ottr": "Moth"}}, "cats": {"Ghost": "Wrenheart"}}, "mod": "mine"})
    assert r["notes"] == [
        {"where": "prefixes.rename.Ottr", "text": "There's no prefix called 'Ottr' in the game, so nothing is renamed"},
        {"where": "cats.Ghost", "text": "No cat in your save is called 'Ghost'"}]
    assert r["warnings"] == [n["text"] for n in r["notes"]]


def test_a_broken_names_json_in_another_mod_is_left_out_with_a_warning(names_studio):
    make_mod(names_studio, "broken", files={"names.json": {"prefixes": {"weights": {"Otter": "lots"}}}})
    make_mod(names_studio, "sparkle", files={"names.json": NAMED})
    r = call(names_studio, "GET", "names")
    assert listed(r)["RiverClan/Warrior/0"]["name"] == "Sparkle"
    assert r["warnings"] == ["Broken's names.json is left out here, because it can't be used: broken/names.json: "
                             'prefixes.weights.Otter should be an object like {"ThunderClan": 0.07}']


def test_preview_refuses_a_names_json_mistake_in_a_sentence(names_studio):
    with pytest.raises(ValueError, match=r"^names\.json: prefixes\.rename\.Otter should be the new text, not empty$"):
        call(names_studio, "POST", "names/preview", {"spec": {"prefixes": {"rename": {"Otter": ""}}}})


def test_preview_survives_an_unreadable_save(names_studio):
    path = os.path.join(names_studio.ctx.cfg.save_dir, SAV_NAME)
    with open(path, "rb") as f:
        whole = f.read()
    with open(path, "wb") as f:
        f.write(whole[:len(whole) // 2])   # cut short, as while the game writes it
    r = call(names_studio, "GET", "names")
    assert r["cats"] == [] and r["save_problem"] == (
        "Couldn't read your save: it's cut short, or not laid out the way wcmods expects (the game may be writing it "
        "just now). The cats list is empty until it can be read")


def test_get_names_without_a_save(studio):
    studio._names = tiny_game()
    r = call(studio, "GET", "names")
    assert r["cats"] == [] and r["save_problem"] is None and r["current_slot"] is None
    assert [p["text"] for p in r["prefixes"]] == ["Wood", "Ember", "Otter", "Wren", "Pigeon"]


def test_preview_says_what_a_names_entry_also_renames(names_studio):
    r = call(names_studio, "POST", "names/preview", {"spec": {"names": {"Rock": "Pebble"}}})
    assert r["names_hits"] == {"Rock": {"cats": ["the cameo cat Rock"], "elsewhere": ["the material Rock", "a line in a quest"]}}


def test_check_file_says_the_names_mistake(studio):
    make_mod(studio, "mine")
    r = call(studio, "PUT", "mods/mine/file/names.json", {"text": json.dumps({"prefixes": {"weights": {"Otter": "lots"}}})})
    assert r["problems"] == ['names.json: prefixes.weights.Otter should be an object like {"ThunderClan": 0.07}']


# ---------- taking every mod out ----------
def test_cats_losing_text_lists_mod_named_cats_your_cat_first(studio):
    write_save(studio.ctx.cfg.save_dir, {"acct": save(player=cat("Leader", "STR_CAT_NAME_WCM_FAWN", "_STAR"),
                                                      warriors=[WOOD, SPARKLE])})
    losing = pipeline.cats_losing_text(studio.ctx.cfg)
    assert [(c["target"], c["name"], c["player"]) for c in losing] == [
        ("player", "Fawnstar", True), ("RiverClan/Warrior/1", "Sparkle", False)]
    assert pipeline.say_cats(losing) == "your cat (Fawnstar) and Sparkle"


def test_a_rogue_given_a_game_prefix_is_said_to_lose_its_name(studio):
    """A rogue renamed Otter has the game's prefix ID alone, whose text only the mod gives: taking the mods out
    (or a build with that mod off) says so, as for a cat with a _WCM_ name."""
    rogue = cat("RogueCat", "STR_CAT_NAME53")
    write_save(studio.ctx.cfg.save_dir, {"acct": save(warriors=[WOOD], outsiders=[rogue])})
    assert [c["target"] for c in pipeline.cats_losing_text(studio.ctx.cfg)] == ["Outsiders/0"]
    studio._names = tiny_game()
    plan = names.Plan(studio._names, names.merge([]))
    assert [(c["target"], c["name"]) for c in pipeline.cats_losing_text(studio.ctx.cfg, plan)] == [("Outsiders/0", "Otter")]

    class Build:   # what the build's warning reads of a build: the files made so far and the save edits
        files, save_ops = {}, []

    class Game:
        def read_text(self, path):
            return strings("EN")

    warned = pipeline.names_without_text(studio.ctx.cfg, Build(), Game())
    assert len(warned) == 1 and warned[0].startswith("a cat in your save has a name a mod made") and \
        "the cat at Outsiders · 0" in warned[0]
    r = call(studio, "POST", "names/preview", {"spec": {}})
    assert [x["target"] for x in r["losing_text"]] == ["Outsiders/0"] and listed(r)["Outsiders/0"]["mod_named"] is True
    r = call(studio, "POST", "names/preview", {"spec": {"cats": {"Nobody": {"prefix": "Otter"}}}, "mod": "mine"})
    assert r["losing_text"] == []


def test_cats_losing_text_without_a_save(studio):
    assert pipeline.cats_losing_text(studio.ctx.cfg) == []
    assert call(studio, "GET", "names/losing") == {"losing": []}


def test_uninstall_answers_losing_and_says_it_first(studio, fake_game):
    write_save(studio.ctx.cfg.save_dir, {"acct": save(player=PLAYER, warriors=[SPARKLE])})
    assert [c["name"] for c in call(studio, "GET", "names/losing")["losing"]] == ["Sparkle"]
    r = call(studio, "POST", "uninstall")
    assert [c["name"] for c in r["result"]["losing"]] == ["Sparkle"] and r["result"]["removed"] == []
    # "warning: " at the start of the line, as the page's drawer and Play count warnings
    assert r["log"][0].startswith("warning: a cat in your save has a name only your mods give: Sparkle. With the mods "
                                  "out, it shows as <MISSING STRING TABLE ENTRY>")
    assert r["summary"] == ("Took every mod out of the game. Your mods are still here. A cat's name shows as "
                            "<MISSING STRING TABLE ENTRY> until they're back (the log says which).")


def test_a_mod_named_cat_says_the_name_it_had_as_its_mods_file_says(names_studio):
    make_mod(names_studio, "sparkle", {"enabled": False}, files={"names.json": NAMED})
    r = call(names_studio, "GET", "names")
    assert listed(r)["RiverClan/Warrior/0"]["before"] == "Woodheart"
    assert listed(r)["RiverClan/Warrior/1"]["before"] == ""   # not named by a mod
    by_place = {"cats": {"RiverClan/Warrior/0": {"fixed": "Sparkle", "was": "Wrenheart"}}}
    r = call(names_studio, "POST", "names/preview", {"spec": by_place, "mod": "mine"})
    assert listed(r)["RiverClan/Warrior/0"]["before"] == "Wrenheart"   # the page's file counts too, and says last


# ---------- places, quests and items ----------
class Reader:
    """The studio's reader of the game's tables (Studio._reader), with a small item table."""
    TEXT = {"STR_ITEM_CONSUMABLE_NAME_7": "Marigold", "STR_CRAFT_MATERIAL_NAME_20": "Rock", "STR_CAT_ACCESSORY_HEAD_12": "Big Leaf"}

    def cooked_table(self, name):
        rows = [("1", {"itemTag": "Gameplay.Inventory.Consumable.MediumHealingHerb", "Name": {"key": "STR_ITEM_CONSUMABLE_NAME_7"}}),
                ("2", {"itemTag": "Gameplay.Inventory.Materials.Rock", "Name": {"key": "STR_CRAFT_MATERIAL_NAME_20"}}),
                ("3", {"itemTag": "Gameplay.Inventory.Materials.Rock2", "Name": {"key": "STR_CRAFT_MATERIAL_NAME_20"}}),   # one name, two items
                ("4", {"itemTag": "Gameplay.Inventory.Cosmetic.Head.BigLeaf.1", "Name": {"key": "STR_CAT_ACCESSORY_HEAD_12"}}),
                ("5", {"itemTag": "Gameplay.Inventory.Cosmetic.Head.Odd.1", "Name": {"text": "Odd Hat"}}),
                ("6", {"itemTag": "Gameplay.Inventory.Cosmetic.Head.None.1", "Name": {"key": "STR_NO_TEXT"}}),
                ("7", {"itemTag": "Gameplay.Quest.NPC.Giver.Kit", "Name": {"key": "STR_GIVER_ROLE_KIT"}})]
        assert name == "DT_QuestObjectsInfo"
        return rows

    def text(self, key):
        return self.TEXT.get(key, key)


def test_texts_lists_areas_quests_and_items(studio, fake_game):
    class Game:
        def read_text(self, path):
            return reader(PLACES)(path)
    studio.ctx._game = Game()
    studio._reader = lambda: Reader()
    r = call(studio, "GET", "names/texts")
    assert r["areas"] == [{"key": "STR_RIVERCLAN_ZONE_5", "code": "R-05", "text": "Willow-Weep"}]
    # One row per text: a title several quests share lists them all.
    assert [([q["quest"] for q in t["quests"]], [q["rank"] for q in t["quests"]], t["text"]) for t in r["quests"]] == [
        (["Gather"], ["Apprentice"], "Feathering the Nests"), (["Gather"], ["Warrior"], "Preparation is Readiness!"),
        (["RankUp"], [""], "The Proving Grounds"), (["Rest1", "Rest2", "Rest3"], ["", "", ""], "A Time to Rest")]
    # And a name two items share (Rock and Rock2) is one row with both, not the second dropped.
    assert [(i["kind"], i["text"], i["key"], i["tags"]) for i in r["items"]] == [
        ("accessory", "Big Leaf", "STR_CAT_ACCESSORY_HEAD_12", ["Gameplay.Inventory.Cosmetic.Head.BigLeaf.1"]),
        ("accessory", "Odd Hat", None, ["Gameplay.Inventory.Cosmetic.Head.Odd.1"]),
        ("consumable", "Marigold", "STR_ITEM_CONSUMABLE_NAME_7", ["Gameplay.Inventory.Consumable.MediumHealingHerb"]),
        ("material", "Rock", "STR_CRAFT_MATERIAL_NAME_20", ["Gameplay.Inventory.Materials.Rock", "Gameplay.Inventory.Materials.Rock2"])]


def test_items_with_inline_text_have_no_key_to_rename_them_by(studio, fake_game):
    studio.ctx._game = type("Game", (), {"read_text": lambda self, path: (_ for _ in ()).throw(KeyError(path))})()
    studio._reader = lambda: Reader()
    items = call(studio, "GET", "names/texts")["items"]
    assert [i for i in items if i["key"] is None] == [{"key": None, "tags": ["Gameplay.Inventory.Cosmetic.Head.Odd.1"],
                                                        "kind": "accessory", "text": "Odd Hat"}]


def test_preview_gives_the_games_text_for_other_text_entries(names_studio):
    r = call(names_studio, "POST", "names/preview", {"spec": {"text": {"STR_BOT_NAME_1": "Hi", "STR_NEW_ONE": "New"}}})
    assert r["text_now"] == {"STR_BOT_NAME_1": "Someone", "STR_NEW_ONE": ""}


def test_texts_without_a_game_ends_as_names_does(studio):
    with pytest.raises(SystemExit):
        call(studio, "GET", "names/texts")


# ---------- the page's guide ----------
def test_the_names_guide_has_its_six_parts_in_plain_words():
    text = guide.read(REPO, "names")
    assert re.findall(r"^## (.+)$", text, re.M) == ["What it changes in the game", "A five-minute first try",
                                                    "What you can and can't do", "Did it reach the game?",
                                                    "Common mistakes", "Undo"]
    assert "names" in guide.pages(REPO)
    assert not re.search(r"—|STR_|python wcmods|--\w", text)
    assert "**" not in guide.render(text)   # every bold closes where it should
