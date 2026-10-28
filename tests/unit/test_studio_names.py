"""The Names page's routes (Studio.names_preview, GET /names/losing, POST /uninstall's "losing") on the tiny game
of tiny_names.py: the cats come from every enabled mod with the page's file in its own mod's place, a cat a
mod named is listed by its name and can be renamed again, a broken names.json elsewhere or a save that can't
be read doesn't stop the page, and taking every mod out says which cats lose their names first."""
import json
import os

import pytest

from wcmods import pipeline
from wcmods.formats.save import SAV_NAME

from unit_helpers import make_mod, write_save
from tiny_names import cat, save, tiny_game

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
    # A mod not made yet (My mods before its first save) counts too.
    r = call(names_studio, "POST", "names/preview", {"spec": NAMED, "mod": "my-mods"})
    assert r["losing_text"] == []


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


def test_cats_losing_text_without_a_save(studio):
    assert pipeline.cats_losing_text(studio.ctx.cfg) == []
    assert call(studio, "GET", "names/losing") == {"losing": []}


def test_uninstall_answers_losing_and_says_it_first(studio, fake_game):
    write_save(studio.ctx.cfg.save_dir, {"acct": save(player=PLAYER, warriors=[SPARKLE])})
    assert [c["name"] for c in call(studio, "GET", "names/losing")["losing"]] == ["Sparkle"]
    r = call(studio, "POST", "uninstall")
    assert [c["name"] for c in r["result"]["losing"]] == ["Sparkle"] and r["result"]["removed"] == []
    assert r["log"][0].startswith("  warning: a cat in your save has a name only your mods give: Sparkle. With the mods "
                                  "out, it shows as <MISSING STRING TABLE ENTRY>")
