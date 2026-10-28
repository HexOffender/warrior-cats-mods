"""Tweaks (wcmods/tweaks.py, sections/tweaks.py and lua/tweaks.lua): what tweaks.json takes and refuses in words, how
several mods' tweaks merge, the in-game script they make, and the studio's side of the Tweaks page. Over the
harness's temp folders; the script is checked by its shape and luacheck, and run in the game by
tests/game/test_tweaks.py."""
import itertools
import json
import os
import re
from types import SimpleNamespace

import pytest

from wcmods import luacheck, tweaks
from wcmods.sdk import BuildContext
from wcmods.sections.tweaks import TweaksSection

from unit_helpers import make_mod


def build(tmp_path, found, code=False, data=None):
    sec = TweaksSection()
    cfg = SimpleNamespace(data={"allow_code_mods": code, **(data or {})}, ue4ss_mods_dir=str(tmp_path / "Mods"))
    ctx = BuildContext(cfg, None, str(tmp_path / "out"), log=lambda m: None)
    ctx.mods = [m for m in found if m.enabled]
    ctx.begin(sec.id)
    items = [(m, sec.collect(m, ctx)) for m in ctx.mods if sec.claims(m)]
    sec.build(ctx, items)
    ctx.end()
    return ctx


def test_every_combination_builds_a_script_that_compiles():
    for on in itertools.product([False, True], repeat=4):
        settings = tweaks.merge([{"keep_stamina_full": on[0], "heal_key": "F5" if on[1] else "", "hold_time": on[2],
                                  "time_of_day": 6.5, "min_fresh_kill": 30 if on[3] else 0, "skip_scenes": on[3]}])
        for save in (None, {"path": "C:/mods/m/tweaks.json", "file": "mods/m/tweaks.json", "keep": {"_help": 'say "hi"'}}):
            lua = tweaks.script(settings, save)
            assert not luacheck.check(lua) and not re.findall(r"@[A-Z_]+@", lua), on
    lua = tweaks.script(tweaks.merge([tweaks.validate({"hold_time": True, "time_of_day": 18})]))
    assert '["time_of_day"] = 18.0' in lua and '["hold_time"] = true' in lua and "local SAVE = nil" in lua


def test_unknown_keys_and_bad_values_are_refused_in_words():
    assert tweaks.validate({"_help": "notes stay out", "hold_time": True, "time_of_day": 6}) == {"hold_time": True, "time_of_day": 6.0}
    cases = [
        ({"stamina": True}, "tweaks.json: there's no tweak called 'stamina' (there are keep_stamina_full, heal_key, hold_time, "
                            "time_of_day, min_fresh_kill, skip_scenes)"),
        ({"hold_time": "yes"}, "tweaks.json: 'hold_time' should be true or false"),
        ({"time_of_day": "noon"}, "tweaks.json: 'time_of_day' should be a number"),
        ({"time_of_day": 25}, "tweaks.json: 'time_of_day' should be from 0 to 24 (hours)"),
        ({"min_fresh_kill": 101}, "tweaks.json: 'min_fresh_kill' should be from 0 to 100 (the pile's own range)"),
        ({"min_fresh_kill": True}, "tweaks.json: 'min_fresh_kill' should be a number"),
        ([1], 'tweaks.json should be an object, like {"keep_stamina_full": true}'),
    ]
    for raw, said in cases:
        with pytest.raises(ValueError) as e:
            tweaks.validate(raw)
        assert str(e.value) == said


def test_heal_key_must_be_one_of_the_offered_keys():
    assert tweaks.HEAL_KEYS == ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F12")   # not F10 or F11
    assert tweaks.validate({"heal_key": "F5"}) == {"heal_key": "F5"} and tweaks.validate({"heal_key": ""}) == {"heal_key": ""}
    for bad in ("F10", "F11", "f5", "G", 5):
        with pytest.raises(ValueError, match="'heal_key' should be one of F1, F2"):
            tweaks.validate({"heal_key": bad})
    with pytest.raises(ValueError, match="'heal_key' is F5, the mod menu's own key: pick another"):
        tweaks.validate({"heal_key": "F5"}, menu_key="F5")


def test_higher_priority_mod_wins_each_key(studio, tmp_path):
    make_mod(studio, "low", {"priority": 0}, {"tweaks.json": {"keep_stamina_full": True, "heal_key": "F5"}})
    make_mod(studio, "high", {"priority": 5}, {"tweaks.json": {"heal_key": "F7", "hold_time": True, "time_of_day": 21}})
    ctx = build(tmp_path, studio.mods())
    lua = ctx.ue4ss_mods[tweaks.UE4SS_MOD_NAME][0]["Scripts/main.lua"].decode()
    assert '["keep_stamina_full"] = true' in lua and '["heal_key"] = "F7"' in lua and '["time_of_day"] = 21.0' in lua
    assert ctx.notes["tweaks"]["on"] == {"keep_stamina_full": True, "heal_key": "F7", "hold_time": True, "time_of_day": 21.0}


def test_the_in_game_save_goes_to_the_top_mod_keeping_its_notes(studio, tmp_path):
    make_mod(studio, "low", {"priority": 0}, {"tweaks.json": {"keep_stamina_full": True}})
    folder = make_mod(studio, "high", {"priority": 5}, {"tweaks.json": {"_help": "My tweaks.", "skip_scenes": True}})
    lua = build(tmp_path, studio.mods()).ue4ss_mods[tweaks.UE4SS_MOD_NAME][0]["Scripts/main.lua"].decode()
    from wcmods.sdk import lua_value
    assert f'["path"] = {lua_value(os.path.abspath(os.path.join(folder, "tweaks.json")))}' in lua
    assert '["file"] = "mods/high/tweaks.json"' in lua and '["keep"] = { ["_help"] = "My tweaks." }' in lua
    assert "Menu.saveJson(SAVE.path, out)" in lua and 'status = ok and ("Saved to " .. SAVE.file .. ".")' in lua


def test_tweaks_need_no_code_mods(studio, tmp_path):
    # wcmods' own script, the mod only data: with "allow_code_mods" off it's in the build and nothing warns, and the
    # mod's card doesn't say it runs code.
    make_mod(studio, "my-mods", files={"tweaks.json": {"keep_stamina_full": True}})
    ctx = build(tmp_path, studio.mods(), code=False)
    assert tweaks.UE4SS_MOD_NAME in ctx.ue4ss_mods and not ctx.warnings
    card = next(m for m in studio.api("GET", ["mods"], {}) if m["id"] == "my-mods")
    assert card["kinds"] == ["tweaks"] and card["code"] is False and card["menu_page"] is True


def test_a_tweaks_json_saved_from_the_page_is_checked_at_once(studio):
    make_mod(studio, "my-mods")
    r = studio.api("PUT", ["mods", "my-mods", "file", "tweaks.json"], {"text": json.dumps({"stamina": True})})
    assert r["problems"] == ["tweaks.json: there's no tweak called 'stamina' (there are keep_stamina_full, heal_key, "
                             "hold_time, time_of_day, min_fresh_kill, skip_scenes)"]
    r = studio.api("PUT", ["mods", "my-mods", "file", "tweaks.json"], {"text": json.dumps({"heal_key": "F5"})})
    assert r["problems"] == []


def test_the_page_is_offered_the_keys_the_mod_menu_leaves_free(studio, fake_game):
    r = studio.api("GET", ["tweaks"], {})
    assert r["defaults"] == tweaks.DEFAULTS and r["heal_keys"] == list(tweaks.HEAL_KEYS) and r["ue4ss"] is True
    studio.api("PATCH", ["ingame"], {"key": "F5"})
    assert "F5" not in studio.api("GET", ["tweaks"], {})["heal_keys"]
    assert any(s["id"] == "tweaks" and s["group"] == "make" for s in studio.api("GET", ["info"], {})["sections"])
