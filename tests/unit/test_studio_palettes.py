"""The Palettes page's side of the studio: what Save to mod says about a palette.json (Studio.check_file and
Studio.file_notes), the game's colour tables the page shows, and Quick palettes' switch, over temporary folders."""
import json
import os

import pytest

from wcmods import mods as modlib

from unit_helpers import EYE_LABELS, make_mod


def call(st, method, path, body=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, None, None)


def put(st, mod_id, doc):
    return call(st, "PUT", f"mods/{mod_id}/file/palette.json", {"text": json.dumps(doc)})


def test_a_coat_colour_past_the_games_and_an_unknown_part_are_problems(studio):
    make_mod(studio, "mine")
    r = put(studio, "mine", {"fur": {"30": "#fff"}})
    assert r["problems"] == ["palette.json: fur has the game's coat colours 0-24 only; only pattern and marking colours "
                             "take new ones, 25 and up (to colour just your cat's coat, use cats.json)"]
    r = put(studio, "mine", {"pattern": {"25": "#fff"}, "hats": {}})
    assert len(r["problems"]) == 1 and "unknown part 'hats'" in r["problems"][0]
    assert r["notes"] == []


def test_an_eye_the_game_hasnt_got_is_a_note_once_the_game_is_found(studio, fake_game, monkeypatch):
    monkeypatch.setattr(studio, "eyes", lambda: {"labels": EYE_LABELS, "rows": []})
    make_mod(studio, "mine")
    r = put(studio, "mine", {"eyes": {"Ambre": "#fff", "Amber": "#ffb300", "row26": "#000"}})
    assert r["problems"] == []
    assert r["notes"] == [
        "Eyes: 'Ambre' isn't one of the game's eye colours (" + ", ".join(EYE_LABELS) + "), so Apply leaves it out",
        "Eyes: 'row26' is past the game's 26 eye colours (they're 0-25), so Apply leaves it out"]


def test_one_colour_named_twice_says_which_one_apply_uses(studio, fake_game, monkeypatch):
    # The Palettes page reads "3" before "03" whatever the file's order, so it lists the two as a conflict: the note
    # says which one the build takes, from the file's own order.
    make_mod(studio, "mine")
    r = put(studio, "mine", {"pattern": {"03": "#111111", "3": "#222222"}, "fur": {"1": "#000", "01": "#fff", "001": "#888"}})
    assert r["problems"] == []
    assert r["notes"] == [
        'Fur: "1", "01" and "001" all name coat colour 1, and Apply uses "001", the last in the file: remove the others',
        'Pattern: "03" and "3" both name pattern colour 3, and Apply uses "3", the later in the file: remove the other']
    # Eyes, once the game's names can be read: an eye named two ways.
    monkeypatch.setattr(studio, "eyes", lambda: {"labels": EYE_LABELS, "rows": []})
    r = put(studio, "mine", {"eyes": {"iris09": "#ff0000", "9": "#00ff00", "Sclera": "#fff", "row0": "#eee", "Amber": "#ffb300"}})
    assert r["notes"] == [
        'Eyes: "iris09" and "9" both name the Sky eye, and Apply uses "9", the later in the file: remove the other',
        'Eyes: "Sclera" and "row0" both name the eye white, and Apply uses "row0", the later in the file: remove the other']


def test_without_the_game_or_its_files_the_eye_names_wait_for_apply(studio, fake_game):
    make_mod(studio, "mine")
    # A game folder whose files can't be read (fake_game has no paks): no note, and nothing in studio.log.
    assert put(studio, "mine", {"eyes": {"Ambre": "#fff"}}) == {"saved": "palette.json", "requires": [], "problems": [],
                                                              "notes": []}
    assert not os.path.isfile(os.path.join(studio.ctx.cfg.data_dir, "studio.log"))
    studio.ctx.cfg.data["game_dir"] = None
    assert put(studio, "mine", {"eyes": {"Ambre": "#fff"}})["notes"] == []


def test_a_new_colour_another_palette_adds_says_which_one_shows(studio):
    make_mod(studio, "a-early", {"name": "Early", "priority": -5}, {"palette.json": {"pattern": {"25": "#111111"}}})
    make_mod(studio, "z-late", {"name": "Dark Forest", "priority": 5},
             {"palette.json": {"pattern": {"25": "#222222", "26": "#333333", "27": "#444444", "28": "#555555"},
                               "marking": {"30": "#666666"}}})
    make_mod(studio, "off", {"enabled": False}, {"palette.json": {"pattern": {"25": "#777777"}}})
    make_mod(studio, "mine")
    r = put(studio, "mine", {"pattern": {"25": "#ff00cc", "26": "#ff00cd", "27": "#ff00ce", "28": "#ff00cf"},
                             "marking": {"30": "#00e5ff", "31": "#00e5fe"}})
    assert r["problems"] == []
    assert r["notes"] == [
        "Pattern colour 25 is also added by Early, which is earlier in the Mods list, so this one shows",
        "Pattern colours 25-28 are also added by Dark Forest, which is later in the Mods list, so its colour shows",
        "Marking colour 30 is also added by Dark Forest, which is later in the Mods list, so its colour shows"]
    # Changing the game's own colours isn't adding: nothing to say.
    assert put(studio, "mine", {"pattern": {"3": "#ff00cc"}})["notes"] == []


def test_numbers_in_a_note_read_as_runs():
    from wcmods.studio import _numbers
    assert _numbers("colour", [25]) == "colour 25"
    assert _numbers("colour", [25, 26]) == "colours 25 and 26"
    assert _numbers("colour", [25, 26, 27, 30]) == "colours 25-27 and 30"
    assert _numbers("colour", [25, 27, 29]) == "colours 25, 27 and 29"
    assert _numbers("colour", [100, 101, 102, 103]) == "colours 100-103"


def test_the_games_tables_say_how_many_colours_the_game_has_even_before_they_load(studio, fake_game):
    assert call(studio, "GET", "game/tables") == {"tables": None, "source": None, "game_slots": 25}
    log = os.path.join(fake_game, "Wrc", "Binaries", "Win64", "ue4ss", "UE4SS.log")
    with open(log, "w", encoding="utf-8") as f:
        f.write("[12:00:00] [WCModsCore] TABLE FurColors 2 #F2E6D0 #3B2A6B\n[12:00:00] [WCModsCore] note\n")
    r = call(studio, "GET", "game/tables")
    assert r == {"tables": {"FurColors": ["#F2E6D0", "#3B2A6B"]}, "source": "game log", "game_slots": 25}


def test_quick_palettes_switch_only_palette_only_mods(studio):
    make_mod(studio, "warm", files={"palette.json": {"fur": {"3": "#ff0000"}}})
    make_mod(studio, "cool", files={"palette.json": {"eyes": {"Amber": "#0000ff"}}})
    make_mod(studio, "adds", files={"palette.json": {"pattern": {"30": "#00ff00"}}})
    make_mod(studio, "cat-too", files={"palette.json": {"fur": {"3": "#0000ff"}}, "cats.json": {"player": {}}})
    found = modlib.discover(studio.ctx.mods_root)
    assert {m.id: modlib.palette_only(m) for m in found} == {"adds": False, "cat-too": False, "cool": True, "warm": True}
    assert modlib.choose_palettes(found, ["cool"]) == (["cool"], ["warm"])
    assert {m.id: m.enabled for m in modlib.discover(studio.ctx.mods_root)} == {
        "adds": True, "cat-too": True, "cool": True, "warm": False}
    with pytest.raises(ValueError) as e:
        modlib.choose_palettes(found, ["adds"])   # a palette that only adds colours isn't a preset
    assert str(e.value) == ("adds only add new colours, so they aren't switched with the presets; turn them on or off "
                            "by themselves, on the Mods page")
