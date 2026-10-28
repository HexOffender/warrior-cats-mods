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


def build(tmp_path, found, code=False, data=None, said=None):
    sec = TweaksSection()
    cfg = SimpleNamespace(data={"allow_code_mods": code, **(data or {})}, ue4ss_mods_dir=str(tmp_path / "Mods"))
    ctx = BuildContext(cfg, None, str(tmp_path / "out"), log=(said.append if said is not None else lambda m: None))
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
        ({"skip_scenes": True}, "tweaks.json: 'skip_scenes' is not available yet: it hasn't been checked that skipping "
                                "keeps the story's steps"),
        ([1], 'tweaks.json should be an object, like {"keep_stamina_full": true}'),
    ]
    for raw, said in cases:
        with pytest.raises(ValueError) as e:
            tweaks.validate(raw)
        assert str(e.value) == said


def test_skipping_the_story_waits_for_its_check_in_the_game(monkeypatch, studio):
    # Off is fine; on is refused (so no mod, downloaded or not, turns it on), the Tweaks pages hide it, and the
    # install made for the hand check (WCMODS_UNCHECKED_TWEAKS=1) lets it through.
    assert tweaks.validate({"skip_scenes": False}) == {"skip_scenes": False}
    assert studio.api("GET", ["tweaks"], {})["unchecked"] == {"skip_scenes": "it hasn't been checked that skipping keeps the story's steps"}
    monkeypatch.setenv("WCMODS_UNCHECKED_TWEAKS", "1")
    assert tweaks.validate({"skip_scenes": True}) == {"skip_scenes": True}
    assert studio.api("GET", ["tweaks"], {})["unchecked"] == {}
    # The code stays, for that check: it leaves a cat Sandbox mode has to Sandbox mode, and the mod menu's page shows
    # its switch only when the install turned it on.
    lua = tweaks.script(tweaks.merge([{"skip_scenes": True}]))
    assert 'ModRef:GetSharedVariable("Sandbox.active")' in lua
    assert "if not holding and (not S.skip_scenes or sandboxCat()) then return end" in lua
    assert 'if installed.skip_scenes then S.skip_scenes = ui.switch("Skip the story\'s scenes", S.skip_scenes) end' in lua


def test_heal_key_must_be_one_of_the_offered_keys():
    # Not F10 or F11 (the game's own), nor F12 (Steam's screenshot key).
    assert tweaks.HEAL_KEYS == ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9")
    assert tweaks.validate({"heal_key": "F5"}) == {"heal_key": "F5"} and tweaks.validate({"heal_key": ""}) == {"heal_key": ""}
    for bad in ("F10", "F11", "F12", "f5", "G", 5):
        with pytest.raises(ValueError, match="'heal_key' should be one of F1, F2.*F12 Steam's for a screenshot"):
            tweaks.validate({"heal_key": bad})
    # The mod menu's Tweaks page doesn't offer a key something else has taken, unless it's the one installed.
    lua = tweaks.script(tweaks.merge([]), None, taken=("F5", "F6"))
    assert 'local HEAL_KEYS = { "F1", "F2", "F3", "F4", "F7", "F8", "F9" }' in lua
    lua = tweaks.script(tweaks.merge([{"heal_key": "F6"}]), None, taken=("F5", "F6"))
    assert 'local HEAL_KEYS = { "F1", "F2", "F3", "F4", "F6", "F7", "F8", "F9" }' in lua


def test_a_heal_key_something_else_uses_is_warned_about_by_name(studio, tmp_path):
    # Mouse look's on and off key (F6 by default, with a mouselook.json) and a controls.json remap onto F3: warned
    # about by what uses them, and kept (pressing them does both); left out of what the Tweaks page offers.
    make_mod(studio, "look", files={"mouselook.json": {"sensitivity": 1.5}})
    make_mod(studio, "keys", {"name": "Key mod"}, files={"controls.json": {"keyboard": {"Player_Interact": "F3"}, "keys": {"F4": "W"}}})
    make_mod(studio, "my-mods", {"priority": 5}, files={"tweaks.json": {"heal_key": "F6"}})
    ctx = build(tmp_path, studio.mods())
    assert ctx.warnings == ["tweaks: my-mods: its heal key, F6, is also mouse look's on and off key (mouselook.json), "
                            "so pressing it does both: pick another key on the Tweaks page"]
    assert '["heal_key"] = "F6"' in ctx.ue4ss_mods[tweaks.UE4SS_MOD_NAME][0]["Scripts/main.lua"].decode()
    r = studio.api("GET", ["tweaks"], {})
    assert r["heal_keys"] == ["F1", "F2", "F5", "F7", "F8", "F9"]
    assert r["taken"] == {"F3": "the key for Player_Interact (the controls.json of Key mod)",
                          "F4": "a remap to W (the controls.json of Key mod)",
                          "F6": "mouse look's on and off key (mouselook.json)"}
    # A mouselook.json that moves its key elsewhere frees F6; one switched off counts for nothing.
    make_mod(studio, "look-2", {"priority": 9}, files={"mouselook.json": {"toggle_key": "F8"}})
    make_mod(studio, "off", {"enabled": False}, files={"controls.json": {"keyboard": {"Player_Run": "F1"}}})
    r = studio.api("GET", ["tweaks"], {})
    assert "F6" in r["heal_keys"] and "F8" not in r["heal_keys"] and "F1" in r["heal_keys"]


def test_the_mod_menus_key_moved_onto_the_heal_key_drops_the_heal_not_the_mod(studio, tmp_path):
    # Saved with F5 free, then the mod menu's key moved to F5: Apply keeps the mod's other tweaks and leaves the heal
    # out, with a warning, instead of refusing the mod.
    make_mod(studio, "my-mods", files={"tweaks.json": {"heal_key": "F5", "keep_stamina_full": True}})
    ctx = build(tmp_path, studio.mods(), data={"menu_key": "F5"})
    assert ctx.warnings == ["tweaks: my-mods: its heal key, F5, is the mod menu's key too, so the heal is left out: "
                            "pick another key on the Tweaks page"]
    lua = ctx.ue4ss_mods[tweaks.UE4SS_MOD_NAME][0]["Scripts/main.lua"].decode()
    assert '["heal_key"] = ""' in lua and '["keep_stamina_full"] = true' in lua
    assert ctx.notes["tweaks"]["on"] == {"keep_stamina_full": True}


def test_no_tweak_on_puts_nothing_in_the_game(studio, tmp_path):
    # A tweaks.json of {} (Save to mod with nothing ticked), or an hour with the clock not held: no WCModsTweaks,
    # so no timers, frame function or mod menu page for nothing.
    make_mod(studio, "my-mods", files={"tweaks.json": {"_help": "Mine.", "time_of_day": 9}})
    said = []
    ctx = build(tmp_path, studio.mods(), said=said)
    assert tweaks.UE4SS_MOD_NAME not in ctx.ue4ss_mods and not ctx.warnings and "tweaks" not in ctx.notes
    assert "  tweaks: no tweak is on, so WCModsTweaks stays out" in said
    # Its heal key on the mod menu's own key, dropped, leaves nothing on too.
    make_mod(studio, "more", {"priority": 3}, files={"tweaks.json": {"heal_key": "F5"}})
    assert tweaks.UE4SS_MOD_NAME not in build(tmp_path, studio.mods(), data={"menu_key": "F5"}).ue4ss_mods


def test_higher_priority_mod_wins_each_key(studio, tmp_path):
    make_mod(studio, "low", {"priority": 0}, {"tweaks.json": {"keep_stamina_full": True, "heal_key": "F5"}})
    make_mod(studio, "high", {"priority": 5}, {"tweaks.json": {"heal_key": "F7", "hold_time": True, "time_of_day": 21}})
    ctx = build(tmp_path, studio.mods())
    lua = ctx.ue4ss_mods[tweaks.UE4SS_MOD_NAME][0]["Scripts/main.lua"].decode()
    assert '["keep_stamina_full"] = true' in lua and '["heal_key"] = "F7"' in lua and '["time_of_day"] = 21.0' in lua
    assert ctx.notes["tweaks"]["on"] == {"keep_stamina_full": True, "heal_key": "F7", "hold_time": True, "time_of_day": 21.0}


def test_the_in_game_save_goes_to_the_top_mod_keeping_its_notes(studio, tmp_path):
    make_mod(studio, "low", {"priority": 0}, {"tweaks.json": {"keep_stamina_full": True}})
    folder = make_mod(studio, "high", {"priority": 5}, {"tweaks.json": {"_help": "My tweaks.", "hold_time": True}})
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
