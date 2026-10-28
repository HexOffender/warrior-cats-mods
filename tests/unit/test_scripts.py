"""Script mods (wcmods/sections/scripts.py): what a mod's scripts/ and settings.json become in the game, and what's
wrong with them said in a creator's words, on the mod's card before any Apply and in the build. Over the harness's
temp folders; the Lua is checked by its shape (there's no Lua here) and run in the game by tests/game/test_scripts.py."""
import json
import os
import re
from types import SimpleNamespace

import pytest

from wcmods import luacheck, mods as modlib
from wcmods.sdk import BuildContext
from wcmods.sections import cpp, scripts
from wcmods.sections.scripts import ScriptsSection

from unit_helpers import make_mod

MAIN = 'MOD.log("hello")\n'


def ctx_for(tmp_path, found=(), code=True):
    """A BuildContext as the build makes one, over tmp_path, with code mods allowed (or not) and `found` on."""
    ctx = BuildContext(SimpleNamespace(data={"allow_code_mods": code}, ue4ss_mods_dir=str(tmp_path / "Mods")), None,
                       str(tmp_path / "out"), log=lambda m: None)
    ctx.mods = [m for m in found if m.enabled]
    return ctx


def build(tmp_path, found, code=True):
    """The scripts section over the mods `found`, as pipeline.build runs it: (ctx, {mod id: why it was left out})."""
    sec, ctx = ScriptsSection(), ctx_for(tmp_path, found, code)
    ctx.begin(sec.id)
    items, failed = [], {}
    for m in ctx.mods:
        if not sec.claims(m):
            continue
        try:
            items.append((m, sec.collect(m, ctx)))
        except ValueError as e:
            failed[m.id] = str(e)
    sec.build(ctx, items)
    ctx.end()
    return ctx, failed


def main_lua(ctx, mod_id):
    return ctx.ue4ss_mods[scripts.ue4ss_name(mod_id)][0]["Scripts/main.lua"].decode()


def test_needs_main_lua(studio, tmp_path):
    make_mod(studio, "empty", files={"scripts/helper.lua": "return {}"})
    m = studio.mod("empty")
    with pytest.raises(ValueError, match=r"scripts/ needs a main\.lua"):
        ScriptsSection().collect(m, ctx_for(tmp_path))
    assert scripts.problems(m) == ["scripts/ needs a main.lua (it runs when the game starts), so the script won't run"]


def test_settings_must_be_an_object(studio, tmp_path):
    make_mod(studio, "listy", files={"scripts/main.lua": MAIN, "settings.json": [1, 2]})
    with pytest.raises(ValueError, match=r'^settings\.json should hold an object: \{"name": value, \.\.\.\}$'):
        ScriptsSection().collect(studio.mod("listy"), ctx_for(tmp_path))


def test_settings_with_a_trailing_comma_name_the_line(studio, tmp_path):
    make_mod(studio, "comma", files={"scripts/main.lua": MAIN, "settings.json": '{\n  "on": true,\n}\n'})
    # Python's own words for the mistake differ between its versions (the comma's line, or the brace's after it).
    with pytest.raises(ValueError, match=r"^settings\.json isn't valid: .+ at line [23]$"):
        ScriptsSection().collect(studio.mod("comma"), ctx_for(tmp_path))
    # Said the same way on the card, and when the studio saves the file (check_file runs collect).
    assert [p for p in scripts.problems(studio.mod("comma")) if p.startswith("settings.json isn't valid")]
    assert studio.check_file(studio.mod("comma"), "settings.json")[0].startswith("settings.json isn't valid: ")


def test_bootstrap_fills_every_token_and_compiles(studio, tmp_path):
    settings = {"_help": "notes", "on": True, "speed": 1.0, "n": 3, "keys": [], "spots": [[1, 2], [3, 4]], "who": "Fawn"}
    make_mod(studio, "my-script", {"name": "My Script"}, {"scripts/main.lua": MAIN, "settings.json": settings})
    ctx, failed = build(tmp_path, studio.mods())
    main = main_lua(ctx, "my-script")
    assert not failed and not luacheck.check(main) and not re.findall(r"@[A-Z_]+@", main)
    assert '["speed"] = 1.0' in main and '["n"] = 3' in main and '["keys"] = {  }' in main
    assert '["spots"] = { { 1, 2 }, { 3, 4 } }' in main and '["who"] = "Fawn"' in main
    assert 'id = "my-script"' in main and 'name = "My Script"' in main
    assert 'settingsFile = "' + os.path.abspath(os.path.join(studio.ctx.mods_root, "my-script", "settings.json")).replace(
        "\\", "\\\\") + '"' in main
    assert "if not pageMade and true and next(MOD.settings) ~= nil then" in main
    assert not ctx.warnings
    note = ctx.notes["scripts"]["my-script"]
    assert note == {"installed as": "WCModsScript_my_script", "files": ["main.lua"], "settings": ["keys", "n", "on", "speed",
                                                                                               "spots", "who"]}


def test_settings_page_off(studio, tmp_path):
    make_mod(studio, "quiet", {"settings_page": False}, {"scripts/main.lua": MAIN, "settings.json": {"on": True}})
    ctx, _ = build(tmp_path, studio.mods())
    assert "if not pageMade and false and next(MOD.settings) ~= nil then" in main_lua(ctx, "quiet")


def test_mod_name_with_quotes_and_newline(studio, tmp_path):
    make_mod(studio, "odd", {"name": 'Say "hi"\nthere'}, {"scripts/main.lua": MAIN})
    ctx, _ = build(tmp_path, studio.mods())
    main = main_lua(ctx, "odd")
    assert not luacheck.check(main)
    assert main.startswith("-- Written by wcmods: starts Say \"hi\" there's in-game script (mods/odd/scripts/main.lua)")
    assert 'name = "Say \\"hi\\"\\nthere"' in main
    assert "settings = {  }" in main and "settingsFile = nil" in main


def test_code_mods_off_warns_notes_and_adds_nothing(studio, tmp_path):
    make_mod(studio, "tweaks", {"name": "Tweaks"}, {"scripts/main.lua": MAIN})
    ctx, failed = build(tmp_path, studio.mods(), code=False)
    assert not failed and not ctx.ue4ss_mods
    assert ctx.warnings == ["scripts: Tweaks has an in-game script (scripts/), which only runs with mods that run code "
                            "allowed (Options, on the Settings and repair page; \"allow_code_mods\" in wcmods.json); left out"]
    assert ctx.notes["scripts"]["tweaks"] == {"left out": "mods that run code are off"}


def test_ids_differing_in_punctuation_or_case_are_refused_naming_both(studio, tmp_path):
    # my-mod, my_mod and My.Mod would all go in as WCModsScript_my_mod (one folder, on Windows, whatever the case):
    # all three are kept out, each saying so, and the other script mods still build.
    for mod_id in ("my-mod", "my_mod", "My.Mod", "other"):
        make_mod(studio, mod_id, files={"scripts/main.lua": f"-- {mod_id}\n"})
    ctx, failed = build(tmp_path, studio.mods())
    said = "My.Mod, my-mod and my_mod would both go in as WCModsScript_My_Mod: rename one of them"
    assert sorted(failed) == ["My.Mod", "my-mod", "my_mod"]
    assert all(why.startswith(said) for why in failed.values()), failed
    assert list(ctx.ue4ss_mods) == ["WCModsScript_other"]
    # The card says it before any Apply; and with one of them off, the other two still clash.
    cards = {m["id"]: m for m in studio.api("GET", ["mods"], {})}
    assert any(p.startswith(said) for p in cards["my-mod"]["problems"]) and not cards["other"]["problems"]
    studio.mod("My.Mod").set_enabled(False)
    assert sorted(scripts.clashes(studio.mods())) == ["my-mod", "my_mod"]


def test_a_second_ue4ss_mod_by_the_same_name_is_refused(tmp_path):
    # The backstop for a section that doesn't check first: the later mod would silently replace the earlier one.
    ctx = ctx_for(tmp_path)
    ctx.begin("scripts")
    ctx.add_ue4ss_mod("WCModsScript_a", {"Scripts/main.lua": "--"})
    with pytest.raises(ValueError, match="two mods would go in as the UE4SS mod WCModsScript_A"):
        ctx.add_ue4ss_mod("WCModsScript_A", {"Scripts/main.lua": "--"})


def test_cpp_mods_differing_in_punctuation_are_refused_naming_both(studio, tmp_path):
    make_mod(studio, "fast-run", files={"dlls/main.dll": b"MZ"})
    make_mod(studio, "fast_run", files={"dlls/main.dll": b"MZ"})
    sec, ctx = cpp.CppSection(), ctx_for(tmp_path, studio.mods())
    for m in ctx.mods:
        with pytest.raises(ValueError, match="fast-run and fast_run would both go in as WCModsCpp_fast_run"):
            sec.collect(m, ctx)


def test_making_a_mod_too_like_another_is_refused(studio):
    modlib.create(studio.ctx.mods_root, "my-mod")
    for too_like in ("my_mod", "my.mod", "my--mod"):
        with pytest.raises(ValueError, match=f"^{re.escape(too_like)} is too like my-mod: pick another name$"):
            modlib.create(studio.ctx.mods_root, too_like)
    modlib.create(studio.ctx.mods_root, "mymod")   # letters run together are another name
    with pytest.raises(ValueError, match="my_mod is too like my-mod"):
        studio.api("POST", ["mods"], {"id": "my_mod"})


def test_subfolders_land_under_mod(studio, tmp_path):
    make_mod(studio, "deep", files={"scripts/main.lua": 'local util = require("lib.util")\n',
                                    "scripts/lib/util.lua": "return {}\n", "scripts/data/words.txt": "fern"})
    ctx, _ = build(tmp_path, studio.mods())
    files = ctx.ue4ss_mods["WCModsScript_deep"][0]
    assert sorted(files) == ["Scripts/main.lua", "Scripts/mod/data/words.txt", "Scripts/mod/lib/util.lua",
                             "Scripts/mod/main.lua", "enabled.txt"]
    assert ctx.notes["scripts"]["deep"]["files"] == ["data/words.txt", "lib/util.lua", "main.lua"]


def test_problems_name_the_file_and_line_in_words(studio, tmp_path):
    make_mod(studio, "broken", {"name": "Broken"}, {"scripts/main.lua": "Game.every(1, function()\n  x()\n",
                                                    "scripts/helper.lua": 'return "unclosed\n'})
    said = ['scripts/helper.lua, line 1: a piece of text in quotes is never closed (its closing quote is missing), so '
            "the script won't run",
            'scripts/main.lua, line 1: a "function" is never closed with "end", so the script won\'t run',
            'scripts/main.lua, line 1: a "(" is never closed with ")", so the script won\'t run']
    m = studio.mod("broken")
    assert scripts.problems(m) == said
    # The build still puts it in (only that script fails in the game; the rest of the install is fine), and says the
    # same, by the mod's name, in its warnings and in its note (the Apply summary's).
    ctx, failed = build(tmp_path, studio.mods())
    assert not failed and "WCModsScript_broken" in ctx.ue4ss_mods
    assert ctx.warnings == [f"scripts: Broken: {p}" for p in said]
    assert ctx.notes["scripts"]["broken"]["problems"] == said
    # Fixed, the card's lines go before any Apply.
    with open(os.path.join(m.folder, "scripts", "main.lua"), "w", encoding="utf-8") as f:
        f.write("Game.every(1, function()\n  x()\nend)\n")
    with open(os.path.join(m.folder, "scripts", "helper.lua"), "w", encoding="utf-8") as f:
        f.write('return "closed"\n')
    assert scripts.problems(m) == []


def test_the_mods_page_has_a_scripts_problems_and_they_clear_when_fixed(studio):
    folder = make_mod(studio, "game-tweaks", {"name": "Game Tweaks"},
                      {"scripts/main.lua": "function heal(\n", "settings.json": {"heal_key": "F5"}})
    make_mod(studio, "palette-only", files={"palette.json": {"fur": {"3": "#ff0000"}}})
    cards = {m["id"]: m for m in studio.api("GET", ["mods"], {})}
    assert cards["game-tweaks"]["script_problems"] == [   # the innermost first
        'scripts/main.lua, line 1: a "(" is never closed with ")", so the script won\'t run',
        'scripts/main.lua, line 1: a "function" is never closed with "end", so the script won\'t run']
    assert cards["palette-only"]["script_problems"] == [] and cards["palette-only"]["script_run"] is None
    with open(os.path.join(folder, "scripts", "main.lua"), "w", encoding="utf-8") as f:
        f.write("function heal() end\n")
    assert studio.api("GET", ["mods"], {})[0]["script_problems"] == []


def test_a_settings_json_saved_from_the_studio_is_checked_at_once(studio):
    # The studio's PUT refuses text that isn't JSON; JSON that isn't an object saves, and says why it can't go in.
    make_mod(studio, "tweaks", files={"scripts/main.lua": MAIN})
    r = studio.api("PUT", ["mods", "tweaks", "file", "settings.json"], {"text": "[1, 2]"})
    assert r["problems"] == ['settings.json should hold an object: {"name": value, ...}']
    r = studio.api("PUT", ["mods", "tweaks", "file", "settings.json"], {"text": json.dumps({"on": True})})
    assert r["problems"] == []
    # A mod without scripts/ isn't the scripts section's: its settings.json (a C++ mod's) isn't checked here.
    make_mod(studio, "plain")
    assert studio.api("PUT", ["mods", "plain", "file", "settings.json"], {"text": "[1]"})["problems"] == []
