"""The Lua wcmods writes for the game: every shared module and script compiles (luacheck, brackets and
tokens) with its settings filled in. Nothing here runs it; `agent test` does that in the game."""
import re

import pytest

from wcmods import catcolours, draw, game, gameremap, keymap, luacheck, menu, mouselook, palettes, view, world

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


def test_names_module_with_areas_and_quests():
    lua = world.names_lua(places=({"R-05": "Willow-Weep"}, {"Gameplay.Quest.Moss": {"Apprentice": "Moss for the dens"}}))
    assert not problems(lua)
    assert '["R-05"] = "Willow-Weep"' in lua and '["Apprentice"] = "Moss for the dens"' in lua
    assert "function N.area(" in lua and "function N.quest(" in lua


def test_game_module_names_the_saved_folder_the_install_makes():
    lua = game.lua(None, r"D:\Saves\WCMods")
    assert not problems(lua)
    assert 'local saved = "D:\\\\Saves\\\\WCMods"' in lua and "local saved = nil" in game.lua()


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
    lua = menu.host_script(MANIFEST, [], dev=True, log=r"C:\Game\ue4ss\UE4SS.log", pages_note="Get set up adds it.")
    assert not problems(lua)
    assert 'Menu.page("Inspector"' in lua and 'Menu.page("Lua console"' in lua
    assert 'Menu.page("Overview"' in lua and 'Menu.page("Installed mods"' in lua and 'Menu.page("Log"' in lua
    assert '"Get set up adds it."' in lua and r'"C:\\Game\\ue4ss\\UE4SS.log"' in lua
    # The pages about the game are the Menu pages mod's (github.com/HexOffender/wcmods-menu-pages).
    assert 'Menu.page("Cheats"' not in lua and 'Menu.page("Nearby"' not in lua and '"Materials.Moss"' not in lua


def test_mod_menu_shows_a_scripts_status_line():
    assert "function Menu.status(" in menu.lua()
    assert 'Menu.shared("status")' in menu.host_script(MANIFEST, [])


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


def test_in_game_remap_plan():
    # The same moves inside the game: each action is sent on its new key and dropped from its old one,
    # in play and in menus. Den_Place leaves X, but Return to camp keeps it; the controller's Run takes LT,
    # so Crouch leaves LT. J stands for C while you play (Drop and Talk to friend) and stops sending its own
    # Play. Escape closes menus as Backspace does, and stops pausing there. Forward on I and moving back on
    # K are axes, left for the key remapper.
    plan, rest, warns = keymap.native_plan({
        "keyboard": {"Player_Interact": "F", "Player_Scent_Tracking": "E", "Player_Den_Place": "Z",
                     "Player_Movement_Up": "K"},
        "keys": {"I": "W", "J": "C"}, "gamepad": {"Player_Run": "LT"}, "menus": {"Escape": "BackSpace"}})
    moves = {"F": ["Player_Interact"], "E": ["Player_Scent_Tracking"], "Z": ["Player_Den_Place"],
             "Gamepad_LeftTrigger": ["Player_Run"]}
    moved = {"Player_Interact": ["E"], "Player_Scent_Tracking": ["Q"], "Player_Den_Place": ["X"],
             "Player_Run": ["Gamepad_RightShoulder"], "Player_Crouch": ["Gamepad_LeftTrigger"]}
    assert plan["play"]["send"] == {**moves, "J": ["Player_Friend_Talk", "Player_Drop"]}
    assert plan["play"]["drop"] == {**moved, "Player_Play": ["J"], "Minigame_Button_X": ["J"]}
    assert plan["menu"]["send"] == {**moves, "Escape": ["Button_B", "Button_Back"]}
    assert plan["menu"]["drop"] == {**moved, "Player_Pause": ["Escape"]}
    assert plan["keys"]["Player_Interact"] == ["F", "LeftMouseButton", "Gamepad_FaceButton_Bottom"]
    assert plan["keys"]["Player_Crouch"] == ["LeftControl", "RightControl", "RightMouseButton"]
    assert rest == {"keyboard": {"Player_Movement_Up": "K"}, "keys": {"I": "W"}}
    assert len(warns) == 2 and "Player_Crouch is on Gamepad_LeftTrigger" in warns[0] and "Player_Play is on J" in warns[1]
    # The game's key pictures show the new keys: a command can have one for each device, and the menu
    # pair's commands show Escape in menus only.
    icons = plan["icons"]
    assert icons["play"]["Player_Interact"] == ["F"] and icons["play"]["Player_Run"] == ["Gamepad_LeftTrigger"]
    assert icons["play"]["Player_Drop"] == ["J"] and "Button_Back" not in icons["play"]
    assert icons["menu"]["Button_Back"] == ["Escape"] and "Player_Drop" not in icons["menu"]
    assert keymap.native_plan({"keyboard": {"Player_Interact": "F"}, "gamepad": {"Player_Interact": "Y"},
                               "keys": {"H": "E"}})[0]["icons"]["play"]["Player_Interact"] == [
        "F", "Gamepad_FaceButton_Top", "H"]   # moves first, then keys standing for others


def test_in_game_menu_keys_and_any_command():
    # Menu navigation on I/K and Confirm on F; the game's Skip moved to F everywhere, Pause to P (the game
    # pauses on Escape, whatever its save says). A mouse button can't stand in for a key in menus.
    plan, rest, warns = keymap.native_plan({"menus": {"I": "Up", "K": "Down", "F": "Enter", "ThumbMouseButton": "BackSpace"},
                                            "keyboard": {"Button_Skip": "G", "Player_Pause": "P"}})
    menu = plan["menu"]
    assert menu["send"]["I"] == ["Button_Up"] and menu["send"]["K"] == ["Button_Down"]
    assert menu["send"]["F"] == ["Button_A", "Button_Confirm", "Button_Skip"]
    assert menu["drop"]["Player_Show_Inventory"] == ["I"] and menu["drop"]["Player_Pause"] == ["Escape"]
    assert plan["play"]["send"] == {"G": ["Button_Skip"], "P": ["Player_Pause"]}
    assert plan["play"]["drop"] == {"Button_Skip": ["Enter"], "Player_Pause": ["Escape"]}
    # I and K also go to the key remapper, which alone can zoom and move the map (it reads those keys).
    assert rest == {"menus": {"I": "Up", "K": "Down", "ThumbMouseButton": "BackSpace"}}
    assert sum("zooming and moving the map" in w for w in warns) == 2
    assert sum("types on the name screen" in w for w in warns) == 1
    _, _, warns = keymap.native_plan({"keyboard": {"Player_ShowHideControls": "H"}})
    assert warns == ["keyboard: no key sends Player_ShowHideControls in the game; H will"]


def test_in_game_remap_warnings():
    _, _, warns = keymap.native_plan({"keyboard": {"Player_Interact": "Q", "Player_Pounce": "W"},
                                      "gamepad": {"Player_Camera_Up": "RB"}})
    assert any("Player_Scent_Tracking is on Q" in w for w in warns)       # Q's own job stops
    assert any(w.startswith("W now does Player_Pounce") for w in warns)   # W still walks too
    assert any("is a stick" in w for w in warns)
    # The Controls screen's keys the save doesn't list move too, and a mouse button can take an action.
    plan, rest, warns = keymap.native_plan({"keyboard": {"Player_Show_Map": "N", "Player_Run": "ThumbMouseButton"}})
    assert plan["play"]["send"] == {"N": ["Player_Show_Map"], "ThumbMouseButton": ["Player_Run"]}
    assert not rest and not warns


def test_in_game_remap_script():
    plan, _, _ = keymap.native_plan({"keyboard": {"Player_Interact": "F"}, "menus": {"I": "Up"}})
    lua = gameremap.script(plan)
    assert not problems(lua)
    assert '["play"] = { ["send"] = { ["F"] = { "Player_Interact" } }, ["drop"] = { ["Player_Interact"] = { "E" } } }' in lua
    assert '["I"] = { "Button_Up" }' in lua
    assert '["icons"] = { ["play"] = { ["Player_Interact"] = { "F" } }' in lua
    assert "NotifyOnNewObject" in lua and "mcGuiButtonImage" in lua


def test_key_remapper_gets_only_what_the_game_cant_do(tmp_path):
    from wcmods import mods as modlib
    from wcmods.sections.controls import remap_plan
    modlib.create(str(tmp_path / "mods"), "keys", enabled=True)
    (tmp_path / "mods" / "keys" / "controls.json").write_text(
        '{"keyboard": {"Player_Interact": "F"}, "keys": {"T": "W"}}', encoding="utf-8")

    class Cfg:   # a game whose last install put the in-game script in
        ue4ss_mods_dir = str(tmp_path / "Mods")
    script = tmp_path / "Mods" / gameremap.UE4SS_MOD_NAME / "Scripts" / "main.lua"
    assert remap_plan(str(tmp_path / "mods"), Cfg())[:2] == ({"F": "E", "T": "W"}, {"E", "W"})
    script.parent.mkdir(parents=True)
    script.write_text("--", encoding="utf-8")
    assert remap_plan(str(tmp_path / "mods"), Cfg())[:2] == ({"T": "W"}, {"W"})
    assert remap_plan(str(tmp_path / "mods"))[:2] == ({"F": "E", "T": "W"}, {"E", "W"})


def test_play_starts_the_game_without_the_old_key_remapper(tmp_path, monkeypatch):
    # The key remapper outside the game is deprecated: Play always starts the game through Steam, and only
    # says when some remaps need the old remapper, and when Steam's copy of the game isn't the one mods go into.
    from types import SimpleNamespace
    from wcmods import onboarding
    started, said = [], []
    monkeypatch.setattr(onboarding, "game_running", lambda: False)
    monkeypatch.setattr(onboarding.pipeline, "pending", lambda cfg, found: {"any": False})
    monkeypatch.setattr(onboarding.pipeline, "install_outdated", lambda cfg: False)
    monkeypatch.setattr(onboarding.os, "startfile", started.append, raising=False)
    ctx = SimpleNamespace(cfg=SimpleNamespace(game_dir=str(tmp_path / "Copy")), mods_root=str(tmp_path), root=str(tmp_path))
    for needed, steam in ((False, None), (True, None), (False, str(tmp_path / "Steam"))):
        monkeypatch.setattr(onboarding, "remaps", lambda c, needed=needed: needed)
        monkeypatch.setattr(onboarding, "steam_elsewhere", lambda c, steam=steam: steam)
        started.clear()
        said.clear()
        assert onboarding.play(ctx, log=said.append)["remaps"] is needed
        assert started == [f"steam://rungameid/{onboarding.STEAM_APP_ID}"]
        assert any("deprecated" in s for s in said) is needed
        assert any(s.startswith(f"warning: Steam starts the game from {steam}") for s in said) is bool(steam)


def test_play_says_the_warnings_of_the_build_it_applies(tmp_path, monkeypatch):
    # Play applies waiting changes itself; its log is all the studio shows of it, so the build's warnings go there
    # (the Steam copy's once, from the build).
    from types import SimpleNamespace
    from wcmods import onboarding
    said = []
    monkeypatch.setattr(onboarding, "game_running", lambda: False)
    monkeypatch.setattr(onboarding.pipeline, "pending", lambda cfg, found: {"any": True})
    monkeypatch.setattr(onboarding.pipeline, "build", lambda *a, **k: {"warnings": ["a cat in your save has a name"]})
    monkeypatch.setattr(onboarding.pipeline, "install", lambda *a, **k: None)
    monkeypatch.setattr(onboarding.os, "startfile", lambda url: None, raising=False)
    monkeypatch.setattr(onboarding, "remaps", lambda c: False)
    monkeypatch.setattr(onboarding, "steam_elsewhere", lambda c: str(tmp_path / "Steam"))
    ctx = SimpleNamespace(cfg=SimpleNamespace(game_dir=str(tmp_path / "Copy")), mods_root=str(tmp_path),
                          root=str(tmp_path), build_dir=str(tmp_path / "build"), backups=str(tmp_path / "backups"))
    assert onboarding.play(ctx, log=said.append)["applied"]
    assert "warning: a cat in your save has a name" in said
    assert not any("Steam starts the game" in s for s in said)
