"""The Your cat page's side of the studio: GET /cat over saves that read, saves that don't and no save at all, and
what Save to mod says about a cats.json (Studio.check_file and Studio.file_notes), over temporary folders."""
import json
import os

import pytest

from wcmods import studio as studio_mod
from wcmods.formats.save import SAV_NAME

from unit_helpers import make_mod, write_save


def call(st, method, path, body=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, None, None)


def put(st, mod_id, name, doc):
    return call(st, "PUT", f"mods/{mod_id}/file/{name}", {"text": json.dumps(doc)})


def cat(prefix, fields):
    return f'(ClanType=WindClan,Role=Warrior,PrefixNameId="{prefix}",SuffixNameId="_LEAF",{fields})'


# A save whose game being played is slot 5, with a cat of slot 2's beside it.
SAVE5 = {"acct": {
    "5": {"GameplayProgression": {"Gameplay.Combat.Character.Cat.Player": {
              "Customization": cat("STR_CAT_NAME1", "FurColorIdx=11,ScarEarId=4,BodyValue=6,CatSize=0.45")}},
          "NPCData": {"WindClan": {"Warrior": [cat("STR_CAT_NAME2", "FurColorIdx=7,TailIdx=3")]}}},
    "2": {"NPCData": {"WindClan": {"Warrior": [cat("STR_CAT_NAME3", "FurColorIdx=1")]}}},
    "Shared": {"General": {"CurrentCatSlot": 5}}}}


# ---------- GET /cat ----------
def test_no_save_gives_empty_cats_and_says_to_start_the_game(studio):
    r = call(studio, "GET", "cat")
    assert r["current"] == {} and r["cats"] == [] and r["scars"]["current"] == {}
    assert r["save_problem"] == studio_mod.SAVE_MISSING
    assert "start the game once" in r["save_problem"]


@pytest.mark.parametrize("cut", [0, 12, 70])
def test_a_save_that_cant_be_read_still_opens_the_page_and_says_why(studio, save, cut):
    path = os.path.join(studio.ctx.cfg.save_dir, SAV_NAME)
    with open(path, "rb") as f:
        whole = f.read()
    with open(path, "wb") as f:
        f.write(whole[:cut])                       # nothing, or half written while the game saves
    r = call(studio, "GET", "cat")
    assert r["save_problem"] == studio_mod.SAVE_UNREADABLE
    assert r["current"] == {} and r["cats"] == [] and r["look"]["current"] == {}
    assert r["parts"]["fur"] == "Fur Color", "the colours card still has what it needs"
    for word in ("Error", "struct", "unpack", "Traceback"):
        assert word not in r["save_problem"]


def test_a_save_that_reads_has_no_problem_and_your_cats_slots_scars_and_shape(studio):
    write_save(studio.ctx.cfg.save_dir, SAVE5)
    r = call(studio, "GET", "cat")
    assert r["save_problem"] is None
    assert r["current"]["fur"] == 11 and r["scars"]["current"]["ear"] == 4
    assert r["look"]["current"]["body"] == 6 and r["look"]["current"]["size"] == 0.45
    # Only the game being played: slot 2's cat is left out.
    assert [c["where"] for c in r["cats"]] == ["WindClan/Warrior/0"]
    (other,) = r["cats"]
    assert other["current"]["slots"]["fur"] == 7 and other["current"]["look"]["tail"] == 3
    assert other["current"]["look"]["size"] is None, "a cat without CatSize has no size, not 0"


# ---------- Save to mod: what it says about a cats.json ----------
def test_a_slot_part_the_build_doesnt_know_is_a_problem_in_words(studio):
    make_mod(studio, "mine")
    r = put(studio, "mine", "cats.json", {"player": {"slots": {"coat": 3}}})
    assert r["problems"] == ["cats.json: player.slots.coat should be one of fur, pattern, marking, eye_left, eye_right, eyes"]
    assert r["notes"] == []


def test_a_new_colour_no_palette_adds_and_a_feral_coat_are_notes(studio):
    make_mod(studio, "mine")
    r = put(studio, "mine", "cats.json", {"player": {"slots": {"pattern": 30, "fur": 21}},
                                         "cats": {"Hawkleaf": {"slots": {"marking": 26}}}})
    assert r["problems"] == []
    assert r["notes"] == [
        "Your cat: coat colour 21 is one of the Feral Edition's; without it the game gives another",
        "Your cat: pattern colour 30 is a new colour no palette that's on adds, so it shows none",
        "Hawkleaf: marking colour 26 is a new colour no palette that's on adds, so it shows none",
        "Cats: no save yet, so Hawkleaf can't be found; start the game once, then install again"]
    # A palette that's on (or this mod's own) adding them: nothing to say about those colours.
    make_mod(studio, "dark", files={"palette.json": {"pattern": {"30": "#ff00cc"}}})
    make_mod(studio, "mine2", files={"palette.json": {"marking": {"26": "#00e5ff"}}})
    r = put(studio, "mine2", "cats.json", {"player": {"slots": {"pattern": 30}}, "cats": {"Hawkleaf": {"slots": {"marking": 26}}}})
    assert [n for n in r["notes"] if "colour" in n] == []


class FakePlan:
    """names.Plan's cats_called, without the game's name tables: places by their end, names from NAMES."""
    NAMES = {"STR_CAT_NAME2": "Hawkleaf"}

    def __init__(self, game, spec):
        pass

    def cats_called(self, target, cats):
        if "/" in target:
            return [c for c in cats if any(p.endswith("/" + target) or p.endswith(target) for p in c["paths"])]
        return [c for c in cats if self.NAMES.get(c["ids"].get("PrefixNameId"), "").lower() == target.lower()]


def test_a_cat_no_key_finds_is_a_note_found_the_way_the_build_finds_cats(studio, fake_game, monkeypatch):
    write_save(studio.ctx.cfg.save_dir, SAVE5)
    monkeypatch.setattr(studio_mod.names, "Plan", FakePlan)
    studio._names = object()   # the game's names, as if read: FakePlan doesn't look at them
    make_mod(studio, "mine")
    r = put(studio, "mine", "cats.json", {"cats": {"hawkleaf": {"look": {"tail": 1}}, "Nobody": {"look": {"tail": 1}}}})
    assert r["problems"] == []
    assert r["notes"] == ["Cats: no cat in your save is called 'Nobody' (the Your cat page lists them, with their places)"]


def test_without_the_games_names_the_cats_arent_looked_for(studio, fake_game):
    write_save(studio.ctx.cfg.save_dir, SAVE5)
    make_mod(studio, "mine")
    r = put(studio, "mine", "cats.json", {"cats": {"Nobody": {"look": {"tail": 1}}}})
    assert r["problems"] == [] and r["notes"] == []
    assert not os.path.isfile(os.path.join(studio.ctx.cfg.data_dir, studio_mod.STUDIO_LOG)), "nothing went wrong"
