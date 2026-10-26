"""The Lua wcmods writes for the game: every shared module and script compiles (luacheck, brackets and
tokens) with its settings filled in. Nothing here runs it; `agent test` does that in the game."""
import re

import pytest

from wcmods import catcolours, draw, game, keymap, luacheck, menu, mouselook, palettes, view, world

MANIFEST = {"sections": {}, "notes": {}, "warnings": ["w"], "built": "2026-10-24T01:00:00"}


def problems(lua):
    return luacheck.check(lua) + re.findall(r"@[A-Z_]+@", lua)   # bracket problems, and tokens left unfilled


@pytest.mark.parametrize("module", [view, draw, world, menu, game], ids=lambda m: m.SHARED_NAME)
def test_shared_module_compiles(module):
    assert not problems(module.lua())


def test_names_module_with_the_games_own_text():
    lua = world.names_lua()
    assert not problems(lua)
    assert "function N.name(" in lua and lua.rstrip().endswith("return N")


def test_mouse_look_script():
    lua = mouselook.script(mouselook.merge([mouselook.validate({"sensitivity": 1.5, "invert": True, "smoothing": 50})]))
    assert not problems(lua)
    assert "sensitivity = 1.5" in lua and "invert = true" in lua and "smoothing = 50.0" in lua


def test_mouse_look_script_with_its_menu_page():
    lua = mouselook.script(mouselook.merge([{}]), {"path": r"C:\mods\m\mouselook.json", "file": "mods/m/mouselook.json",
                                                  "keep": {"_help": 'say "hi"'}})
    assert not problems(lua)
    assert r'"C:\\mods\\m\\mouselook.json"' in lua


def test_your_cats_colours_script_with_its_menu_page():
    lua = catcolours.script({"fur": (1.0, 0.5, 0.0)}, save={"path": "x", "file": "y", "doc": {"player": {"colours": {}}}})
    assert not problems(lua)
    assert '"#ff8000"' in lua


def test_mod_menu_window_script_with_the_dev_pages():
    lua = menu.host_script(MANIFEST, [], dev=True)
    assert not problems(lua)
    assert 'Menu.page("Inspector"' in lua and 'Menu.page("Lua console"' in lua and '"Materials.Moss"' in lua
    assert 'ui.heading("Nearby")' in lua and 'group = "cheats"' in lua   # the host's own pages are in too


def test_mod_menu_opens_from_a_controller_too():
    lua = menu.host_script(MANIFEST, [])
    assert '"Gamepad_Special_Left"' in lua and "(or View on a controller)" in lua
    assert '["pad"] = ""' in menu.host_script({"sections": {}, "notes": {}, "warnings": [], "built": ""}, [], pad="")


def test_mod_menus_groups_come_from_one_table():
    ids = [g["id"] for g in menu.GROUPS]
    lua = menu.lua()
    assert all(f'["id"] = "{i}"' in lua for i in ids)
    from wcmods.agent import menu as agent_menu
    assert agent_menu.GROUPS == tuple(ids)


def test_mod_menu_answers_the_agent_controller():
    assert all(s in menu.lua() for s in ('"agent.read"', '"agent.act"', '"agent.scroll"'))
    assert 'Menu.share("frame"' in menu.host_script({"sections": {}, "notes": {}, "warnings": [], "built": ""}, [])


def test_palette_script():
    assert not luacheck.check(palettes.ue4ss_script({}))


def test_key_remap_plan():
    # Interact and Scent tracking move along F/E/Q, so Q goes quiet; X stays because Return to camp still
    # uses it; forward moves to I, so W goes quiet.
    send, block, warns = keymap.plan({"keyboard": {"Player_Interact": "F", "Player_Scent_Tracking": "E",
                                                   "Player_Den_Place": "Z"}, "keys": {"I": "W"}})
    assert send == {"F": "E", "E": "Q", "Z": "X", "I": "W"} and block == {"Q", "W"} and not warns
