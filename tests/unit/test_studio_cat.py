"""The Your cat page's side of the studio: GET /cat over saves that read, saves that don't and no save at all, and
what Save to mod says about a cats.json (Studio.check_file and Studio.file_notes), over temporary folders."""
import json
import os
import re

import pytest

from wcmods import studio as studio_mod
from wcmods.formats.save import SAV_NAME
from wcmods.names import Plan as RealPlan

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
    assert r["current"] == {} and r["cats"] == [] and r["scars"]["current"] == {} and r["current_slot"] is None
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
    assert r["save_problem"] is None and r["current_slot"] == "5"
    assert r["current"]["fur"] == 11 and r["scars"]["current"]["ear"] == 4
    assert r["look"]["current"]["body"] == 6 and r["look"]["current"]["size"] == 0.45
    # Every game's cats, the game being played first; another game's by a key with its slot first.
    assert [(c["slot"], c["where"], c["target"], c["playing"]) for c in r["cats"]] == [
        ("5", "WindClan/Warrior/0", "WindClan/Warrior/0", True), ("2", "WindClan/Warrior/0", "2/WindClan/Warrior/0", False)]
    other, elsewhere = r["cats"]
    assert other["current"]["slots"]["fur"] == 7 and other["current"]["look"]["tail"] == 3
    assert other["current"]["look"]["size"] is None, "a cat without CatSize has no size, not 0"
    assert elsewhere["current"]["slots"]["fur"] == 1
    # The games with a cat of yours: slot 2 has none, so it isn't one; game 5's cat has what it has now.
    (game,) = r["games"]
    assert game["slot"] == "5" and game["n"] == 6 and game["current"] and game["clan"] == "WindClan"
    assert game["look_now"]["slots"]["fur"] == 11 and game["look_now"]["scars"]["ear"] == 4


# ---------- the keys a file may name a cat by ----------
class NamesPlan:
    """names.Plan's display, without the game's name tables: the name a cat shows now (final=False) and after the
    names mods that are on (final), from the dicts below by its prefix."""
    NOW = {"STR_CAT_NAME2": "Hawkleaf", "STR_CAT_NAME3": "Hawkleaf", "STR_CAT_NAME4": "Duskfang"}
    AFTER = {**NOW, "STR_CAT_NAME4": "Mothfang"}   # a names mod renames Duskfang

    def __init__(self, game, spec):
        pass

    def display(self, ids, final=True):
        return (self.AFTER if final else self.NOW).get(ids.get("PrefixNameId"), "")


def npc(prefix, role="Warrior"):
    return f'(ClanType=WindClan,Role={role},PrefixNameId="{prefix}",SuffixNameId="_LEAF",FurColorIdx=1)'


CLANS = {"acct": {
    "0": {"GameplayProgression": {"Gameplay.Combat.Character.Cat.Player": {"Customization": cat("STR_CAT_NAME1", "FurColorIdx=1")}},
          "NPCData": {"Clans": {"WindClan": {"Warrior": [npc("STR_CAT_NAME2"), npc("STR_CAT_NAME3")],
                                             "Deputy": [npc("STR_CAT_NAME4", "Deputy")]}},
                      "NarrativeRoles": {"TheDeputy": npc("STR_CAT_NAME4", "Deputy")}}},
    "Shared": {"General": {"CurrentCatSlot": 0}}}}


@pytest.fixture
def clans(studio, fake_game, monkeypatch):
    write_save(studio.ctx.cfg.save_dir, CLANS)
    monkeypatch.setattr(studio_mod.names, "Plan", NamesPlan)
    studio._names = object()   # the game's names, as if read: NamesPlan doesn't look at them
    return {c["where"]: c for c in call(studio, "GET", "cat")["cats"]}


def test_two_cats_with_one_name_are_picked_by_place_and_both_answer_to_the_name(clans):
    first, second = clans["Clans/WindClan/Warrior/0"], clans["Clans/WindClan/Warrior/1"]
    assert first["target"] == "Clans/WindClan/Warrior/0" and second["target"] == "Clans/WindClan/Warrior/1"
    assert first["aliases"]["names"] == second["aliases"]["names"] == ["hawkleaf"]
    assert first["clan"] == "WindClan" and first["role"] == "Warrior"


def test_a_cats_places_are_every_key_the_build_takes_and_case_counts(clans):
    places = clans["Clans/WindClan/Warrior/1"]["aliases"]["places"]
    for key in ("Clans/WindClan/Warrior/1", "WindClan/Warrior/1", "Warrior/1", "NPCData/Clans/WindClan/Warrior/1",
                "0/NPCData/Clans/WindClan/Warrior/1"):
        assert key in places, key
    assert "windclan/warrior/1" not in places, "the build matches places as written"
    assert "1" not in places, "a key without a / is a name"


def test_a_renamed_cat_answers_to_both_names_and_a_unique_name_is_its_key(clans, studio):
    deputy = clans["Clans/WindClan/Deputy/0"]
    assert deputy["target"] == "Mothfang" and deputy["name"] == "Mothfang"
    assert deputy["aliases"]["names"] == ["duskfang", "mothfang"]
    # A cat in a story role too is one cat, found by either place.
    assert "NarrativeRoles/TheDeputy" in deputy["aliases"]["places"]
    assert call(studio, "GET", "cat")["your_clan"] == "WindClan"


class MatchPlan(NamesPlan):
    """NamesPlan's names with the build's own matcher (names.Plan's _targets), as sections/cats.py's _others uses it."""
    NOW = {**NamesPlan.NOW, "STR_CAT_NAME5": "Brackenfur", "STR_CAT_NAME6": "Hawkleaf"}
    AFTER = {**NOW, "STR_CAT_NAME4": "Mothfang"}
    _targets, cats_called, _called, id_name = RealPlan._targets, RealPlan.cats_called, RealPlan._called, RealPlan.id_name
    prefixes, suffixes = [], []   # the game's name parts, for names.guess_name: none here


# Two Hawkleafs and a deputy in a story role too, a Warrior/0 in two clans, and game 2 with a Hawkleaf at the same
# place as one of game 0's.
MANY = {"acct": {
    "0": {"GameplayProgression": {"Gameplay.Combat.Character.Cat.Player": {"Customization": cat("STR_CAT_NAME1", "FurColorIdx=1")}},
          "NPCData": {"Clans": {"WindClan": {"Warrior": [npc("STR_CAT_NAME2"), npc("STR_CAT_NAME3")],
                                             "Deputy": [npc("STR_CAT_NAME4", "Deputy")]},
                                "ThunderClan": {"Warrior": [npc("STR_CAT_NAME5")]}},
                      "NarrativeRoles": {"TheDeputy": npc("STR_CAT_NAME4", "Deputy")}}},
    "2": {"NPCData": {"Clans": {"WindClan": {"Warrior": [npc("STR_CAT_NAME7"), npc("STR_CAT_NAME6")]}}}},
    "Shared": {"General": {"CurrentCatSlot": 0}}}}


def page_finds(key, cats, slot):
    """lib/catlook.js's catsFor, written out: a key with a slot first means that game's cats, one without the game
    being played's, "player" is no other cat, a place matches the cat's places as written, a name its names in any
    case."""
    k, game = key.strip(), slot
    m = re.match(r"^(\d+)/(.*)$", k)
    if m:
        game, k = m.group(1), m.group(2)
    if k.lower() == "player":
        return []
    return [c for c in cats if c["slot"] == game
            and (k in c["aliases"]["places"] if "/" in k else k.lower() in c["aliases"]["names"])]


def test_the_page_finds_every_key_shape_on_the_cats_the_build_changes(studio, fake_game, monkeypatch):
    from wcmods.formats.savejson import SaveDoc
    write_save(studio.ctx.cfg.save_dir, MANY)
    monkeypatch.setattr(studio_mod.names, "Plan", MatchPlan)
    studio._names = object()
    r = call(studio, "GET", "cat")
    assert r["current_slot"] == "0"
    every = studio_mod.names.cats_in_save(SaveDoc(studio.save_text()[0]).data)
    plan = MatchPlan(None, None)
    keys = ["Clans/WindClan/Warrior/1", "WindClan/Warrior/1", "Warrior/1", "NPCData/Clans/WindClan/Warrior/1",
            "0/NPCData/Clans/WindClan/Warrior/1", "0/Clans/WindClan/Warrior/1", "0/Warrior/1", " Warrior/1 ",
            "Warrior/0", "Clans/ThunderClan/Warrior/0", "windclan/warrior/1", "Warrior/5", "NarrativeRoles/TheDeputy",
            "0/NarrativeRoles/TheDeputy", "Deputy/0", "WindClan/Deputy/0", "2/Warrior/1", "2/Clans/WindClan/Warrior/0",
            "hawkleaf", "HAWKLEAF", "0/Hawkleaf", "2/Hawkleaf", "duskfang", "Mothfang", "Brackenfur", "Nobody",
            "player", "0/player"]
    for key in keys:
        # What the build changes (sections/cats.py's _others), in every game: the page lists every game's cats.
        target = key.strip()
        hits = [c for c in plan.cats_called(target, every) if not c["player"]]
        if studio_mod.names.slot_of(target) is None:
            hits = [c for c in hits if c["current"]]
        build = sorted((c["slot"], studio_mod.names.place(c["paths"][0])) for c in hits)
        assert sorted((c["slot"], c["where"]) for c in page_finds(key, r["cats"], r["current_slot"])) == build, key
    # And the shapes do find what they should: a place without its clan in every clan, a shared name on both.
    assert len(page_finds("Warrior/0", r["cats"], "0")) == 2 and len(page_finds("hawkleaf", r["cats"], "0")) == 2
    assert [c["where"] for c in page_finds("0/Warrior/1", r["cats"], "0")] == ["Clans/WindClan/Warrior/1"]
    # Game 2's Hawkleaf is its own there, by its name with the slot first; a name without one never reaches it.
    assert [c["target"] for c in page_finds("2/Hawkleaf", r["cats"], "0")] == ["2/Hawkleaf"]


def test_the_eye_colours_palettes_give_are_served_by_row_the_later_palette_winning(studio, fake_game, monkeypatch):
    from unit_helpers import EYE_LABELS
    monkeypatch.setattr(studio, "eyes", lambda: {"labels": EYE_LABELS, "rows": []})
    make_mod(studio, "low", {"priority": 1}, {"palette.json": {"eyes": {"iris2": "#ff0000", "Sky": ["#000000", "#00e5ff"],
                                                                         "Mint": ["#abcdef"]}}})
    make_mod(studio, "high", {"priority": 2}, {"palette.json": {"eyes": {"amber": "#00ff00", "Ambre": "#123456"}}})
    make_mod(studio, "off", {"enabled": False}, {"palette.json": {"eyes": {"Hazel": "#0000ff"}}})
    eyes = call(studio, "GET", "cat")["eyes"]
    # A list of one colour is that colour flat (apply_eyes), so it's sent as a gradient of two the same, as the
    # Palettes page reads it: one colour alone would be drawn with the game's shading.
    assert eyes == {"2": {"mode": "single", "colors": ["#00ff00"]}, "9": {"mode": "grad", "colors": ["#000000", "#00e5ff"]},
                    "7": {"mode": "grad", "colors": ["#abcdef", "#abcdef"]}}
    # Without the game's eye names there's nothing to put them on: the page shows the game's own eyes.
    studio.ctx.cfg.data["game_dir"] = None
    assert call(studio, "GET", "cat")["eyes"] == {}


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
        "No save yet, so Hawkleaf can't be found; start the game once, then install again"]
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
    assert r["notes"] == ["No cat in your save is called 'Nobody' (the Your cat page lists them, with their places)"]


def test_without_the_games_names_the_cats_arent_looked_for(studio, fake_game):
    write_save(studio.ctx.cfg.save_dir, SAVE5)
    make_mod(studio, "mine")
    r = put(studio, "mine", "cats.json", {"cats": {"Nobody": {"look": {"tail": 1}}}})
    assert r["problems"] == [] and r["notes"] == []
    assert not os.path.isfile(os.path.join(studio.ctx.cfg.data_dir, studio_mod.STUDIO_LOG)), "nothing went wrong"
