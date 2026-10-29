"""The studio's API for the Characters and Questlines pages (Studio.api over temporary folders, no game): a
save of cats or quests makes the mod use Sandbox mode (never need it), turns an installed Sandbox mode on,
what the pages are told about Sandbox mode, starting every questline over, "Use where my cat is standing"
when the game can't be asked, and the guide's pages for the two pages."""
import json
import os
import re

import pytest

from wcmods import bridge, guide, mods as modlib, pipeline, story
from wcmods import studio as studio_mod

from unit_helpers import REPO, make_mod

CAT = {"npcs": [{"id": "mossfoot", "name": "Mossfoot", "lines": ["Hello."]}]}
QUEST = {"quests": [{"id": "moss", "title": "Moss for Mossfoot", "giver": "mossfoot",
                     "steps": [{"do": "talk", "lines": ["Bring me moss?"]}]}]}


def call(st, method, path, body=None, query=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, query)


def save_file(st, mod_id, name, value):
    return call(st, "PUT", f"mods/{mod_id}/file/{name}", {"text": json.dumps(value) if not isinstance(value, str) else value})


def meta(st, mod_id):
    with open(os.path.join(st.ctx.mods_root, mod_id, "mod.json"), encoding="utf-8") as f:
        return json.load(f)


# ---------- Sandbox mode as a soft need ----------
def test_saving_a_cat_marks_the_mod_as_using_sandbox(studio):
    make_mod(studio, "mine")
    r = save_file(studio, "mine", "npcs.json", CAT)
    assert r["uses"] == ["sandbox"] and r["requires"] == [] and r["turned_on"] == []
    assert meta(studio, "mine")["uses"] == ["sandbox"] and "requires" not in meta(studio, "mine")


def test_saving_twice_doesnt_duplicate_uses(studio):
    make_mod(studio, "mine", {"uses": ["mod-menu"]})
    save_file(studio, "mine", "npcs.json", CAT)
    save_file(studio, "mine", "quests.json", QUEST)
    save_file(studio, "mine", "npcs.json", CAT)
    assert meta(studio, "mine")["uses"] == ["mod-menu", "sandbox"]


def test_an_empty_npcs_file_adds_nothing(studio):
    make_mod(studio, "mine")
    r = save_file(studio, "mine", "npcs.json", {"npcs": []})
    assert r["uses"] == [] and r["turned_on"] == []
    assert "uses" not in meta(studio, "mine")
    # And emptied later: what it says it uses stays, since it blocks nothing.
    save_file(studio, "mine", "npcs.json", CAT)
    save_file(studio, "mine", "npcs.json", {"npcs": []})
    assert meta(studio, "mine")["uses"] == ["sandbox"]


def test_a_studio_added_requires_moves_to_uses(studio):
    make_mod(studio, "old-story", {"requires": ["sandbox", "menu-pages"]}, files={"npcs.json": CAT})
    r = save_file(studio, "old-story", "npcs.json", CAT)
    assert r["requires"] == ["menu-pages"] and r["uses"] == ["sandbox"]
    assert meta(studio, "old-story")["requires"] == ["menu-pages"]


def test_a_mod_with_scripts_keeps_its_requires(studio):
    make_mod(studio, "scripted", {"requires": ["sandbox"]}, files={"scripts/main.lua": "print('hi')\n"})
    r = save_file(studio, "scripted", "npcs.json", CAT)
    assert r["requires"] == ["sandbox"] and r["uses"] == []


def test_saving_turns_an_installed_sandbox_on_and_says_so(studio):
    make_mod(studio, "sandbox", {"name": "Sandbox mode", "enabled": False, "version": "0.5"})
    make_mod(studio, "mine")
    r = save_file(studio, "mine", "npcs.json", CAT)
    assert r["turned_on"] == ["Sandbox mode"]
    assert meta(studio, "sandbox")["enabled"] is True
    # Once it's on, a save says nothing more.
    assert save_file(studio, "mine", "npcs.json", CAT)["turned_on"] == []


def test_a_story_mod_without_sandbox_has_nothing_unmet(studio):
    make_mod(studio, "mine", files={"items.json": {"items": []}})
    save_file(studio, "mine", "npcs.json", CAT)
    found = modlib.discover(studio.ctx.mods_root)
    assert modlib.unmet(found) == {}
    listed = {m["id"]: m for m in call(studio, "GET", "mods")}
    assert listed["mine"]["problems"] == []
    assert listed["mine"]["works_with"] == [{"id": "sandbox", "name": "Sandbox mode", "state": "missing"}]
    # With Sandbox mode there but off, the card says so; switching it off is never refused for this mod.
    make_mod(studio, "sandbox", {"name": "Sandbox mode", "enabled": False})
    listed = {m["id"]: m for m in call(studio, "GET", "mods")}
    assert listed["mine"]["works_with"] == [{"id": "sandbox", "name": "Sandbox mode", "state": "off"}]
    call(studio, "POST", "mods/sandbox/switch", {"on": True})
    r = call(studio, "POST", "mods/sandbox/switch", {"on": False})
    assert r["blocked_by"] == [] and r["changed"] == [{"id": "sandbox", "name": "Sandbox mode", "on": False}]


def test_a_file_that_isnt_json_is_refused_and_untouched(studio):
    make_mod(studio, "mine", files={"npcs.json": CAT})
    with pytest.raises(ValueError, match=r"npcs\.json isn't valid: .* at line 1"):
        save_file(studio, "mine", "npcs.json", "{not json")
    with open(os.path.join(studio.ctx.mods_root, "mine", "npcs.json"), encoding="utf-8") as f:
        assert json.load(f) == CAT
    assert "uses" not in meta(studio, "mine")


def test_a_quest_naming_a_missing_cat_still_saves_with_the_problem(studio):
    make_mod(studio, "mine")
    save_file(studio, "mine", "npcs.json", CAT)
    bad = {"quests": [{"id": "moss", "title": "Moss", "giver": "sparrowpaw", "steps": [{"do": "talk", "lines": ["Hi"]}]}]}
    r = save_file(studio, "mine", "quests.json", bad)
    assert r["saved"] == "quests.json" and "sparrowpaw isn't one of this mod's cats" in r["problems"][0]
    assert call(studio, "GET", "mods/mine/file/quests.json")["exists"]


def test_story_sandbox_says_each_state(studio):
    def state():
        return call(studio, "GET", "story/sandbox")
    s = state()
    assert s["state"] == "missing" and s["version"] is None and s["older"] == [] and s["name"] == "Sandbox mode"
    assert s["needs"] == {"look": "0.5", "slots": "0.5", "patrol": "0.6"} and s["releases"].startswith("https://github.com/")
    make_mod(studio, "sandbox", {"name": "Sandbox mode", "enabled": False, "version": "0.4"})
    s = state()
    assert s["state"] == "off" and s["version"] == "0.4" and s["older"] == ["look", "patrol", "slots"]
    call(studio, "POST", "mods/sandbox/switch", {"on": True})
    assert state()["state"] == "no-code"   # a script, kept out while mods that run code aren't allowed
    studio.ctx.cfg.data["allow_code_mods"] = True
    assert state()["state"] == "on"
    with open(os.path.join(studio.ctx.mods_root, "sandbox", "mod.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "Sandbox mode", "enabled": True, "version": "0.5.0"}, f)
    assert state()["older"] == ["patrol"]
    with open(os.path.join(studio.ctx.mods_root, "sandbox", "mod.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "Sandbox mode", "enabled": True, "version": "0.6"}, f)
    assert state()["older"] == []
    # A version that isn't a plain number is older than any.
    with open(os.path.join(studio.ctx.mods_root, "sandbox", "mod.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "Sandbox mode", "enabled": True, "version": "0.5-beta"}, f)
    assert state()["older"] == ["look", "patrol", "slots"]


def test_story_sandbox_names_the_newest_release_only_once_github_has_said_it(studio):
    # GitHub isn't asked for the strip: until Check for newer versions (or an add) has asked it, no release is
    # known, so the strip names no .zip (the 0.5 fixed looks need may not be out).
    assert call(studio, "GET", "story/sandbox")["released"] is None
    studio.releases["sandbox"] = {"no_release": True, "error": "Sandbox mode has no release yet"}
    assert call(studio, "GET", "story/sandbox")["released"] is None
    studio.releases["sandbox"] = {"version": "0.4", "name": "sandbox-0.4.zip"}
    s = call(studio, "GET", "story/sandbox")
    assert s["released"] == "0.4" and s["newest"] == "0.6"   # what the fields need (patrols), which isn't out


def test_story_sandbox_says_a_sandbox_held_back_after_a_game_update(studio, monkeypatch):
    studio.ctx.cfg.data["allow_code_mods"] = True
    studio.ctx.cfg.save()   # kept through "Use it anyway", which reads wcmods.json again
    make_mod(studio, "sandbox", {"name": "Sandbox mode", "version": "0.5"})
    assert call(studio, "GET", "story/sandbox")["state"] == "on"
    # The game updated, and Sandbox mode was made for the build before: on, but every Apply leaves it out.
    monkeypatch.setenv("WCMODS_GAME_BUILD", "99999999")
    s = call(studio, "GET", "story/sandbox")
    assert s["state"] == "held-back" and s["held"] == "made for an older version of the game" and s["version"] == "0.5"
    # Until it's used anyway, on the Mods page.
    call(studio, "POST", "mods/sandbox/allow-outdated", {"on": True})
    s = call(studio, "GET", "story/sandbox")
    assert s["state"] == "on" and s["held"] is None


def test_a_story_mod_an_older_studio_saved_never_keeps_apply_out(studio):
    # Downloaded, never saved here: "requires": ["sandbox"] and no code of its own reads as a use.
    make_mod(studio, "old-story", {"requires": ["sandbox"]}, files={"npcs.json": CAT, "items.json": {"items": []}})
    listed = {m["id"]: m for m in call(studio, "GET", "mods")}
    assert listed["old-story"]["problems"] == [] and listed["old-story"]["requires"] == []
    assert listed["old-story"]["works_with"] == [{"id": "sandbox", "name": "Sandbox mode", "state": "missing"}]
    assert modlib.unmet(modlib.discover(studio.ctx.mods_root)) == {}
    # Saved here, the file says so itself.
    save_file(studio, "old-story", "npcs.json", CAT)
    assert meta(studio, "old-story")["requires"] == [] and meta(studio, "old-story")["uses"] == ["sandbox"]


# ---------- starting every questline over ----------
def progress_path(studio):
    return os.path.join(pipeline.saved_folder(studio.ctx.cfg), story.PROGRESS_FILE)


def write_progress(studio, data):
    os.makedirs(os.path.dirname(progress_path(studio)), exist_ok=True)
    with open(progress_path(studio), "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))


def test_start_over_clears_quests_and_keeps_spots(studio):
    write_progress(studio, {"_help": "...", "3": {"made": "2026-10-28T01:02:03Z", "quests": {"mine/moss": {"step": 2, "got": 1}},
                                                   "cats": {"mine/mossfoot": {"at": [1, 2, 3], "yaw": 90}}},
                            "5": {"quests": {"mine/moss": {"step": 1, "got": 0, "done": True}}, "cats": {}}})
    assert call(studio, "DELETE", "story/progress") == {"cats": 2}
    with open(progress_path(studio), encoding="utf-8") as f:
        after = json.load(f)
    assert after["3"] == {"made": "2026-10-28T01:02:03Z", "quests": {}, "cats": {"mine/mossfoot": {"at": [1, 2, 3], "yaw": 90}}}
    assert after["5"]["quests"] == {} and after["_help"] == "..."


def test_start_over_refuses_while_the_game_runs(studio, sandbox):
    write_progress(studio, {"3": {"quests": {"mine/moss": {"step": 2}}, "cats": {}}})
    sandbox.running = True
    with pytest.raises(RuntimeError, match="Close the game first"):
        call(studio, "DELETE", "story/progress")
    with open(progress_path(studio), encoding="utf-8") as f:
        assert json.load(f)["3"]["quests"] == {"mine/moss": {"step": 2}}


def test_start_over_with_no_file_says_so(studio):
    assert call(studio, "DELETE", "story/progress") == {"cats": 0}
    write_progress(studio, "{not json")   # a file that can't be read goes, as the in-game button would leave it
    assert call(studio, "DELETE", "story/progress") == {"cats": 0, "removed": True}
    assert not os.path.exists(progress_path(studio))


# ---------- "Use where my cat is standing" ----------
def test_where_says_what_to_press_when_the_game_is_closed(studio, monkeypatch, sandbox):
    studio.ctx.cfg.data["allow_code_mods"] = True

    def closed(self, code, timeout=15):
        raise bridge.BridgeError("the game isn't running with the bridge (start it after `wcmods install` with "
                                 "\"allow_code_mods\": true)")
    monkeypatch.setattr(studio_mod.Bridge, "run", closed)
    with pytest.raises(RuntimeError) as e:
        call(studio, "POST", "game/where")
    said = str(e.value)
    assert said == "The game is closed: press Play, stand where you want the cat and press this again"
    assert "wcmods install" not in said and "allow_code_mods" not in said
    # Running, but started before the mods went in: close it, Apply, Play.
    sandbox.running = True
    with pytest.raises(RuntimeError, match=r"^The game is running without the studio's connection to it: close the game, "
                                           r"press Apply to game, then Play, stand where"):
        call(studio, "POST", "game/where")

    # No answer in time (the bridge's "withdrawn"), or another command talking to it: in the words the studio
    # uses wherever it asks the game something (studio.BRIDGE_FAILED), then press again.
    def busy(self, code, timeout=15):
        raise bridge.BridgeError("no reply within 10 s (the game may be loading, or held still)", "withdrawn")
    monkeypatch.setattr(studio_mod.Bridge, "run", busy)
    with pytest.raises(RuntimeError, match=r"^The game didn't answer within 10 seconds \(it may be loading.*; press this "
                                           r"again in a moment$"):
        call(studio, "POST", "game/where")


def test_where_says_what_to_press_with_code_mods_off(studio):
    with pytest.raises(PermissionError) as e:
        call(studio, "POST", "game/where")
    assert str(e.value) == studio_mod.WHERE_NO_CODE and "Settings and repair" in str(e.value)


def test_where_gives_the_spot_and_says_when_the_cat_isnt_in_the_forest(studio, monkeypatch):
    studio.ctx.cfg.data["allow_code_mods"] = True
    replies = iter([{"ok": True, "result": [{"at": [1, 2, 3], "yaw": 90, "level": "L_WorldMap_01_P"}]},
                    {"ok": True, "result": []}])
    monkeypatch.setattr(studio_mod.Bridge, "run", lambda self, code, timeout=15: next(replies))
    assert call(studio, "POST", "game/where") == {"at": [1, 2, 3], "yaw": 90, "level": "L_WorldMap_01_P"}
    with pytest.raises(RuntimeError, match="isn't in the forest yet"):
        call(studio, "POST", "game/where")


# ---------- the guide's pages for the two story pages ----------
SIX = ["What it changes in the game", "A five-minute first try", "What you can and can't do", "Did it reach the game?",
       "Common mistakes", "Undo"]


@pytest.mark.parametrize("page, module", [("characters", "npcs.js"), ("questlines", "quests.js")])
def test_the_story_guides_have_the_six_parts_and_the_pages_link_them(page, module):
    text = guide.read(REPO, page)
    assert [line[3:] for line in text.splitlines() if line.startswith("## ")] == SIX
    steps = re.search(r"## A five-minute first try\n\n(.*?)\n\n(?!\d)", text, re.S).group(1)
    assert len(re.findall(r"^\d+\. ", steps, re.M)) <= 8
    for word in ("python", "wcmods.py", "--", "UE4SS", ".pak", "slot ", "G (", "| "):
        assert word not in text, word
    with open(os.path.join(REPO, "studio", "sections", module), encoding="utf-8") as f:
        assert f'help: "help:{page}"' in f.read()


# ---------- the Apply summary ----------
def test_the_apply_summary_says_the_cats_and_questlines_and_whether_sandbox_mode_shows_them():
    manifest = {"mods": ["my-mods", "pal"], "names": {"my-mods": "My mods", "pal": "Palette"}, "sections": {}, "warnings": [],
                "notes": {"story": {"story": {"my-mods": {"npcs": ["mossfoot", "sparrowpaw"], "quests": ["moss"]}},
                                    "sandbox": {"state": "on", "version": "0.5", "older": []}}}}
    assert studio_mod.plain_summary(manifest) == ("Put 2 mods in the game: My mods, Palette. 2 cats and 1 questline from "
                                                  "My mods; Sandbox mode 0.5 will show them.")
    manifest["notes"]["story"]["sandbox"] = {"state": "missing", "version": None, "older": []}
    manifest["warnings"] = ["story: cats and questlines go in, but nothing shows them"]
    assert studio_mod.plain_summary(manifest).endswith(
        "2 cats and 1 questline from My mods; they're waiting for Sandbox mode. 1 warning.")
    # On, but left out after a game update: nothing shows them, and the summary says what to press.
    manifest["notes"]["story"]["sandbox"] = {"state": "held-back", "version": "0.5", "older": []}
    assert studio_mod.plain_summary(manifest).endswith(
        "2 cats and 1 questline from My mods; they're waiting for Sandbox mode, left out since the game's update "
        "(Use it anyway, on the Mods page). 1 warning.")
    manifest["notes"] = {}
    assert studio_mod.plain_summary(manifest) == "Put 2 mods in the game: My mods, Palette. 1 warning."
