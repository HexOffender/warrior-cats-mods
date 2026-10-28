"""The Controls page's Python side: the game's keys as the build knows them (/game/keys), controls.json read in
words (controls.parse), what the build will do said entry by entry before Apply (keymap.describe and
/controls/check), the keys wcmods and mods listen on (keys_in_use), the plain-words warnings of the remap plans,
and what the build adds to the game with and without the script loader."""
import json
from types import SimpleNamespace

import pytest

from wcmods import controls, gameremap, keymap, mods as modlib, playstate
from wcmods.sdk import BuildContext
from wcmods.sections import controls as section

from unit_helpers import REPO, make_mod


def call(st, method, path, body=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, None)


def rows(said, section_name):
    return said["rows"][section_name]


# ---------- the game's keys ----------
def test_game_keys_route_serves_the_build_tables(studio):
    # No save, no game: the page still knows the game's keys, and Pause is on Escape (the save's Enter is wrong).
    r = call(studio, "GET", "game/keys")
    assert r["keyboard"]["Player_Pause"] == "Escape" and r["keyboard"]["Player_Show_Inventory"] == "I"
    assert r["gamepad"]["Player_Interact"] == "Gamepad_FaceButton_Bottom"
    assert r["ue4ss"] is False
    assert r["names"]["Player_Friend_Talk"] == ["Talk to a friend", "talks to a friend"]
    assert r["aliases"]["l2"] == "Gamepad_LeftTrigger" and "AnimTool_StopAnim" not in r["names"]


def test_game_keys_route_says_the_loader_is_there_with_the_fake_game(studio, fake_game):
    assert call(studio, "GET", "game/keys")["ue4ss"] is True


# ---------- reading controls.json ----------
@pytest.mark.parametrize("raw, said", [
    (["F"], "should be an object like"),
    ({"keyboard": {"Player_Interact": None}}, "keyboard: Player_Interact should be a key's name"),
    ({"keyboard": {"Player_Interact": ["F"]}}, "keyboard: Player_Interact should be a key's name"),
    ({"keyboard": {"Player_Interact": {"button": "F"}}}, "needs a \"key\""),
    ({"keybaord": {}}, "should be one of keyboard, gamepad, keys, menus"),
    ({"keys": ["T", "W"]}, "'keys' should be an object"),
    ({"menus": {"Escape": "BackSpace"}}, '"menus" should look like {"keys"'),
])
def test_parse_rejects_a_list_a_null_and_a_wrong_section_name(raw, said):
    with pytest.raises(ValueError) as e:
        controls.parse(raw)
    assert said in str(e.value)


def test_parse_accepts_menus_keys_and_flattens_them():
    raw = {"_help": "a note", "keyboard": {"Player_Interact": {"key": "F"}, "_why": "x"},
           "menus": {"keys": {"U": "Enter"}, "_note": "y"}, "keys": {"T": "W"}}
    assert controls.parse(raw) == {"keyboard": {"Player_Interact": "F"}, "menus": {"U": "Enter"}, "keys": {"T": "W"}}
    assert controls.parse({}) == {}


def test_merge_later_mods_win_per_key_and_empty_sections_drop():
    merged = section.merge([{"keyboard": {"Player_Interact": "F", "Player_Run": "G"}, "keys": {}},
                            {"keyboard": {"Player_Interact": "H"}, "menus": {"U": "Enter"}}])
    assert merged == {"keyboard": {"Player_Interact": "H", "Player_Run": "G"}, "menus": {"U": "Enter"}}


def test_saving_a_controls_json_with_a_null_says_which_entry(studio):
    make_mod(studio, "keys")
    r = call(studio, "PUT", "mods/keys/file/controls.json", {"text": json.dumps({"keyboard": {"Player_Run": None}})})
    assert r["problems"] == ["controls.json: keyboard: Player_Run should be a key's name in quotes, like \"F\""]


# ---------- the plans, in plain words ----------
def test_the_games_own_keys_are_a_no_op():
    # Every action on the game's own key and button (what the old Keyboard and Controller defaults buttons wrote,
    # Pause on Escape): nothing to do, nothing for the key remapper, nothing said.
    game = keymap.game_keys()
    plan, rest, warns = keymap.native_plan({"keyboard": game["keyboard"], "gamepad": game["gamepad"]})
    assert not gameremap.has_work(plan) and warns == []
    send, block, warns = keymap.plan(rest)
    assert send == {} and block == set() and warns == []


def test_native_plan_warns_when_pause_leaves_escape_or_an_action_lands_on_enter():
    # The file the studio's old "Keyboard defaults" button wrote: the game's keys, but Pause on Enter (the save's).
    old_defaults = {"keyboard": {**keymap.GAME_KEYBOARD, "Player_Pause": "Enter"}}
    plan, _, warns = keymap.native_plan(old_defaults)
    assert plan["play"]["send"] == {"Enter": ["Player_Pause"]} and plan["play"]["drop"] == {"Player_Pause": ["Escape"]}
    assert warns == ["Enter now opens the pause menu, in menus as well, and still confirms in menus and skips "
                     "dialogue; Escape will no longer open the pause menu"]
    _, _, warns = keymap.native_plan({"keyboard": {"Player_Interact": "BackSpace"}})
    assert warns == ["Backspace now does Interact, in menus as well, and still goes back in menus"]
    # A menus pair for Escape isn't a move of Pause: it leaves play alone.
    assert keymap.native_plan({"menus": {"Escape": "BackSpace"}})[2] == []


def test_native_plan_warns_when_a_pressed_key_still_moves_you():
    plan, _, warns = keymap.native_plan({"keys": {"W": "E"}})
    assert plan["play"]["send"]["W"] == ["Button_X", "Player_Interact"]
    assert warns == ["W now does what E does while you explore, and still moves you forward too: the game reads that "
                     "key itself"]


def test_native_plan_pairs():
    # E for E is nothing; a D-pad button can stand for a key, and sends that key's commands on the pad.
    plan, rest, warns = keymap.native_plan({"keys": {"E": "E", "Gamepad_DPad_Up": "M"}})
    assert plan["play"]["send"] == {"Gamepad_DPad_Up": ["Player_Show_Map"]} and not rest and not warns
    # Escape for P while you explore: Escape stops pausing, which is said.
    _, _, warns = keymap.native_plan({"keys": {"Escape": "P"}})
    assert warns == ["Escape now does what P does while you explore, so it no longer opens the pause menu"]


def test_native_plan_and_plan_edges():
    # Drop on X: X stops placing decorations and taking you back to camp (one sentence for both).
    _, _, warns = keymap.native_plan({"keyboard": {"Player_Drop": "X"}})
    assert warns == ["X now drops what you carry, so it no longer places a den decoration and takes you back to camp; "
                     "give Place a den decoration and Return to camp another key"]
    # Interact on F and F standing for W: F is set both ways.
    _, _, warns = keymap.native_plan({"keyboard": {"Player_Interact": "F"}, "keys": {"F": "W"}})
    assert any(w.startswith("F is set both for Interact and for a change only Play with key remaps.bat makes")
               for w in warns)
    # Without the loader, controller buttons can't change; the game's own stick says nothing.
    _, _, warns = keymap.plan({"gamepad": {"Player_Run": "LT", "Player_Movement_Up": "Gamepad_LeftY"}})
    assert warns == ["Without the script loader, controller buttons can't change: Play with key remaps.bat is keyboard "
                     "and mouse only (Get set up, on the Mods page, installs the loader)"]
    assert warns[0].rows == [("gamepad", "Player_Run")]
    # In menus a mouse button can't stand for a controller button.
    send, warns = keymap.menu_plan({"menus": {"ThumbMouseButton": "Gamepad_FaceButton_Bottom"}})
    assert send == {} and warns == ["In menus, Mouse 4 can only stand for a keyboard key, not the controller's A"]


def test_native_plan_menu_row_pairs_keep_the_games_key():
    # Confirm also on U: U sends Enter's commands in menus, and Enter keeps them (nothing is dropped).
    plan, _, _ = keymap.native_plan({"menus": {"U": "Enter", "PageDown": "Two"}})
    assert plan["menu"]["send"] == {"U": ["Button_A", "Button_Confirm", "Button_Skip"], "PageDown": ["Button_ShoulderR"]}
    assert plan["menu"]["drop"] == {} and plan["play"]["send"] == {}


def test_native_plan_second_key_after_a_move_lists_both_keys():
    # Interact moved to F and a second key H standing for E (the game's key): both do Interact while you explore.
    plan, _, warns = keymap.native_plan({"keyboard": {"Player_Interact": "F"}, "keys": {"H": "E"}})
    assert plan["play"]["send"]["F"] == ["Player_Interact"] and "Player_Interact" in plan["play"]["send"]["H"]
    assert plan["keys"]["Player_Interact"][:2] == ["F", "H"] and not warns


# ---------- describe: what Apply will do, before Apply ----------
def test_describe_says_each_move_and_its_drop():
    said = keymap.describe({"keyboard": {"Player_Interact": "F"}})
    assert rows(said, "keyboard")["Player_Interact"] == {
        "key": "F", "status": "game", "line": "F does Interact. E still shows the map's legend.", "notes": []}
    said = keymap.describe({"keyboard": {"Player_Interact": "I"}})
    row = rows(said, "keyboard")["Player_Interact"]
    assert row["line"].startswith("I does Interact and no longer opens the inventory.")
    assert row["notes"] == ["I now does Interact, so it no longer opens the inventory; give Inventory another key"]
    row = rows(keymap.describe({"keyboard": {"Player_Pause": "Enter"}}), "keyboard")["Player_Pause"]
    assert row["line"].endswith("Escape no longer opens the pause menu.")
    # The game's own key, kept in a file: nothing changes, nothing said.
    assert rows(keymap.describe({"keyboard": {"Player_Pause": "Escape"}}), "keyboard")["Player_Pause"]["status"] == "same"


def test_describe_sorts_what_needs_the_launcher_and_what_cant():
    said = keymap.describe({"keys": {"T": "W"}, "keyboard": {"Player_Movement_Up": "K"},
                            "gamepad": {"Player_Movement_Up": "Gamepad_RightY", "Player_Camera_Up": "Gamepad_RightY"}})
    assert rows(said, "keys")["T"]["status"] == "launcher"
    assert rows(said, "keys")["T"]["line"] == ("T moves you forward while you explore, when the game is started with "
                                               "Play with key remaps.bat.")
    assert rows(said, "keyboard")["Player_Movement_Up"]["status"] == "launcher"
    stick = rows(said, "gamepad")["Player_Movement_Up"]
    assert stick["status"] == "cannot" and stick["line"].startswith("The left stick can't be moved by a mod")
    assert stick["notes"] == []   # the line says it; not twice
    assert rows(said, "gamepad")["Player_Camera_Up"]["status"] == "same" and said["launcher"] is True


def test_describe_without_ue4ss():
    # The old key remapper does what it can: keyboard moves; the controller and the Controls screen's actions it can't.
    said = keymap.describe({"keyboard": {"Player_Interact": "F", "Player_Show_Map": "N"},
                            "gamepad": {"Player_Run": "LT"}}, in_game=False)
    assert rows(said, "keyboard")["Player_Interact"]["status"] == "launcher"
    for sec, name in (("keyboard", "Player_Show_Map"), ("gamepad", "Player_Run")):
        assert rows(said, sec)[name]["status"] == "cannot" and rows(said, sec)[name]["notes"], name
    assert "script loader" in rows(said, "keyboard")["Player_Show_Map"]["notes"][0]


def test_describe_says_pairs_in_play_and_in_menus():
    said = keymap.describe({"keys": {"H": "E"}, "menus": {"U": "Enter", "ThumbMouseButton": "BackSpace"}})
    assert rows(said, "keys")["H"]["line"] == "H does what E does while you explore (Interact)."
    assert rows(said, "menus")["U"]["line"] == "In menus, U does what Enter does (Confirm and Skip)."
    assert rows(said, "menus")["U"]["notes"] == ["In menus, U still types on the name screen, and does Enter's job there too"]
    assert rows(said, "menus")["ThumbMouseButton"]["status"] == "launcher"


def test_describe_says_which_unchanged_actions_lose_their_key():
    # Run onto the controller's LT: Crouch, still on LT in the file's eyes, stops working there.
    said = keymap.describe({"gamepad": {"Player_Run": "LT"}})
    assert said["lost"] == {"keyboard": {}, "gamepad": {
        "Player_Crouch": "The controller's LT no longer crouches: it runs now. Give Crouch another button."}}
    # Moved elsewhere too, it has its own row: nothing lost.
    assert keymap.describe({"gamepad": {"Player_Run": "LT", "Player_Crouch": "RB"}})["lost"]["gamepad"] == {}
    # I standing for E while you explore: the inventory loses I. With the old key remapper, I standing for W.
    assert "I no longer opens the inventory" in keymap.describe({"keys": {"I": "E"}})["lost"]["keyboard"]["Player_Show_Inventory"]
    assert keymap.describe({"keys": {"I": "W"}}, in_game=False)["lost"]["keyboard"] == {
        "Player_Show_Inventory": "With Play with key remaps.bat, I stands for W, so it no longer opens the inventory. "
                                 "Give Inventory another key."}


def test_describe_flags_a_reserved_key_once():
    reserved = {"F6": {"does": "switches mouse look off and on", "from": "Mouse look"}}
    said = keymap.describe({"keyboard": {"Player_Interact": "F6"}}, reserved=reserved)
    assert rows(said, "keyboard")["Player_Interact"]["notes"] == [
        "F6 also switches mouse look off and on (Mouse look), and will do both; pick another key"]
    assert sum("F6 also" in w for w in said["warnings"]) == 1
    assert keymap.describe({"keyboard": {"Player_Interact": "F7"}}, reserved=reserved)["warnings"] == []


# ---------- keys in use ----------
def test_keys_in_use_lists_the_games_wcmods_and_mods_keys(studio):
    cfg = studio.ctx.cfg
    cfg.data.update({"menu_key": "PAGE_UP", "menu_pad": ""})
    make_mod(studio, "look", files={"mouselook.json": {"toggle_key": "F7"}})
    make_mod(studio, "waves", files={"animations.json": {"animations": [
        {"id": "Wave", "name": "Wave", "file": "a.glb", "emote": True, "key": "G"}]}})
    make_mod(studio, "emote-wheel", {"name": "Emote wheel"}, files={"settings.json": {"key": "B"}})
    make_mod(studio, "off", {"enabled": False}, files={"mouselook.json": {"toggle_key": "F9"}})
    found = {e["key"]: e for e in section.keys_in_use(cfg, modlib.discover(studio.ctx.mods_root))}
    assert found["PageUp"] == {"key": "PageUp", "does": "opens the mod menu", "from": "wcmods", "taken": "refuse"}
    assert found["F7"]["does"] == "switches mouse look off and on" and found["F7"]["taken"] == "refuse"
    assert found["G"]["from"] == "Waves" and found["G"]["taken"] == "warn"
    assert found["B"]["does"] == "opens the emote wheel" and found["Gamepad_DPad_Down"]["from"] == "Emote wheel"
    assert found["F11"]["taken"] == "refuse"
    assert found["E"] == {"key": "E", "does": "Interact; in menus: the map's legend", "from": "the game", "taken": None}
    assert found["W"]["does"] == "Move forward; in menus: Up"
    assert found["Gamepad_LeftY"]["does"] == "moves you" and found["Gamepad_RightX"]["does"] == "moves the camera"
    assert "Insert" not in found and "Gamepad_Special_Left" not in found and "F9" not in found and "F6" not in found


def test_keys_in_use_falls_back_to_each_mods_key_when_mouse_look_wont_merge(studio):
    make_mod(studio, "a-look", {"priority": 1}, files={"mouselook.json": {"pitch_min": 10, "toggle_key": "F7"}})
    make_mod(studio, "b-look", {"priority": 2}, files={"mouselook.json": {"pitch_max": 5}})
    found = [e["key"] for e in section.keys_in_use(studio.ctx.cfg, modlib.discover(studio.ctx.mods_root))
             if e["from"] == "Mouse look"]
    assert found == ["F6", "F7"]


# ---------- /controls/check ----------
def test_controls_check_route_merges_with_other_mods_and_says_who_wins(studio):
    make_mod(studio, "low", {"priority": 1}, files={"controls.json": {"keyboard": {"Player_Interact": "G", "Player_Run": "V"}}})
    make_mod(studio, "high", {"priority": 9, "name": "High keys"}, files={"controls.json": {"keyboard": {"Player_Run": "B"}}})
    make_mod(studio, "mine", {"priority": 5, "enabled": False})
    r = call(studio, "POST", "controls/check", {"mod": "mine", "controls": {
        "keyboard": {"Player_Interact": "F", "Player_Run": "N", "Player_Drop": "Z"}}})
    assert r["rows"]["keyboard"]["Player_Interact"]["line"].startswith("F does Interact")   # this mod, over low
    assert r["rows"]["keyboard"]["Player_Run"]["status"] == "overridden"
    assert "High keys changes this too and wins" in r["rows"]["keyboard"]["Player_Run"]["notes"][0]
    assert "High keys also changes Run, and wins: it comes after this mod." in r["others"]
    assert "Low also changes Interact, and this mod wins: it comes later." in r["others"]
    assert r["lower"] == [["keyboard", "Player_Interact"], ["keyboard", "Player_Run"]]
    assert r["ue4ss"] is False and r["launcher"] is True


def test_controls_check_route_refuses_broken_text_with_a_sentence(studio):
    with pytest.raises(ValueError) as e:
        call(studio, "POST", "controls/check", {"mod": "mine", "controls": {"keyboard": {"Player_Interact": None}}})
    assert "Player_Interact should be a key's name" in str(e.value)
    with pytest.raises(ValueError) as e:
        call(studio, "POST", "controls/check", {"mod": "mine"})
    assert "didn't send its controls.json" in str(e.value)


def test_controls_check_route_lists_the_keys_in_use(studio, fake_game):
    r = call(studio, "POST", "controls/check", {"mod": "my-mods", "controls": {"keyboard": {"Player_Interact": "Insert"}}})
    assert r["ue4ss"] is True
    assert {"key": "Insert", "does": "opens the mod menu", "from": "wcmods", "taken": "refuse"} in r["in_use"]
    assert r["rows"]["keyboard"]["Player_Interact"]["notes"] == [
        "Insert also opens the mod menu (wcmods), and will do both; pick another key"]


# ---------- the build ----------
def build(tmp_path, data, ue4ss):
    mods_dir = tmp_path / "Mods"
    if ue4ss:
        mods_dir.mkdir(exist_ok=True)
    cfg = SimpleNamespace(ue4ss_mods_dir=str(mods_dir) if ue4ss else None, data={})
    ctx = BuildContext(cfg, None, str(tmp_path / "out"), lambda m: None)
    ctx.current = "controls"
    section.ControlsSection().build(ctx, [(None, data)])
    return ctx


def test_build_without_ue4ss_requests_no_script_and_names_the_launcher(tmp_path):
    ctx = build(tmp_path, {"keyboard": {"Player_Interact": "F"}}, ue4ss=False)
    assert ctx.ue4ss_mods == {}
    said = " ".join(ctx.warnings)
    assert "Play with key remaps.bat" in said and "Get set up" in said and "wcmods play" not in said


def test_build_with_ue4ss_adds_remap_only_with_work_and_playstate_only_for_the_rest(tmp_path):
    ctx = build(tmp_path, {"gamepad": {"Player_Movement_Up": "Gamepad_RightY"}}, ue4ss=True)
    assert ctx.ue4ss_mods == {} and len(ctx.warnings) == 1 and "can't be moved by a mod" in ctx.warnings[0]
    ctx = build(tmp_path, {"keyboard": {"Player_Interact": "F"}}, ue4ss=True)
    assert set(ctx.ue4ss_mods) == {gameremap.UE4SS_MOD_NAME} and ctx.warnings == []
    ctx = build(tmp_path, {"keys": {"T": "W"}}, ue4ss=True)
    assert set(ctx.ue4ss_mods) == {playstate.UE4SS_MOD_NAME}
    assert ctx.warnings == ["controls: T moves you forward while you explore, when the game is started with Play with "
                            "key remaps.bat, which is deprecated"]


def test_the_controls_guide_has_its_six_parts_and_no_command_line(studio):
    # The help panel shows docs/guide/controls.md (the page's "How this works"), rendered by wcmods/guide.py.
    from wcmods import guide
    text = guide.read(REPO, "controls")
    html = guide.render(text)
    assert guide.title(text) == "Controls" and "controls" in guide.pages(REPO)
    heads = [h.split(">", 1)[1].split("<", 1)[0] for h in html.split("<h2")[1:]]
    assert heads == ["What it changes in the game", "A five-minute first try", "What you can and can't do",
                     "Did it reach the game?", "Common mistakes", "Undo"]
    for word in ("python", "wcmods.py", "Player_", "Gamepad_", "<table"):
        assert word not in html, word


def test_the_cli_says_the_game_pauses_on_escape(studio, save, capsys):
    from wcmods import cli
    cli.cmd_controls(studio.ctx, SimpleNamespace(json=False))
    out = capsys.readouterr().out
    assert "Player_Interact" in out and "The game pauses on Escape, whatever the save says" in out
    cli.cmd_controls(studio.ctx, SimpleNamespace(json=True))
    assert "pauses on Escape" not in capsys.readouterr().out
