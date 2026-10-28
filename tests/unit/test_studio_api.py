"""Clan Mod Studio's API (wcmods/studio.py, Studio.api), called straight, without sockets: every route that
never reads the game's paks, on the happy path and at its edges (a key left out, the wrong type, an unknown
id, a mod.json or palette.json that can't be read, no save, no game, a game whose paks are missing, the game
"running"). The routes that read the game's files stay in `python wcmods.py selftest`."""
import io
import json
import os
import time
import zipfile

import pytest

from wcmods import gamefiles, onboarding, palettes, studio as studio_mod
from wcmods.config import EXE_NAME, game_running as REAL_GAME_RUNNING   # taken before the sandbox patches it
from wcmods.formats import png
from wcmods.formats.save import SAV_NAME
from wcmods.studio import BUILTIN_SECTIONS, NO_GAME, Download

from unit_helpers import make_mod, write_save


def call(st, method, path, body=None, query=None, upload=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, query, upload)


def get(st, path, query=None):
    return call(st, "GET", path, query=query)


def post(st, path, body=None, query=None, upload=None):
    return call(st, "POST", path, body, query, upload)


def zip_of(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data if isinstance(data, (str, bytes)) else json.dumps(data))
    return str(path)


# ---------- info, changes, settings ----------
def test_info_says_what_the_studio_has_without_a_game(studio):
    r = get(studio, "info")
    assert r["game_dir"] is None and r["save_found"] is False and r["ue4ss"] is False
    assert r["game_running"] is False and r["installed"] is None and r["install_outdated"] is False
    assert r["code_changed"] is False and r["allow_code_mods"] is False
    assert r["game_build"] == {"build": None, "verified": False, "label": None}
    assert [s["id"] for s in r["sections"]] == [s["id"] for s in BUILTIN_SECTIONS]


def test_info_with_the_fake_game_a_save_and_the_game_running(studio, fake_game, save, sandbox):
    sandbox.running = True
    r = get(studio, "info")
    assert r["game_dir"] == fake_game and r["save_found"] and r["ue4ss"] and r["game_running"]


def test_fake_running_is_exactly_0_or_1_and_only_with_wcmods_data(monkeypatch):
    # The real config.game_running (the sandbox stands in for it everywhere else), with tasklist saying the
    # game runs: WCMODS_FAKE_RUNNING decides only as "0" or "1", and only with WCMODS_DATA set.
    from types import SimpleNamespace
    from wcmods import config
    monkeypatch.setattr(config.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=f"{EXE_NAME}  1234 Console"))
    for value, running in (("0", False), ("1", True), ("true", True), (" 0", True), ("00", True), ("", True)):
        monkeypatch.setenv("WCMODS_FAKE_RUNNING", value)
        assert REAL_GAME_RUNNING() is running, value
    monkeypatch.setenv("WCMODS_FAKE_RUNNING", "0")
    monkeypatch.delenv("WCMODS_DATA")
    assert REAL_GAME_RUNNING() is True


def test_info_adds_the_console_and_mods_own_pages_only_with_code_mods_allowed(studio):
    make_mod(studio, "paged", {"studio_title": "Paged"}, {"studio/section.js": "export default {}"})
    make_mod(studio, "off-page", {"enabled": False}, {"studio/section.js": "export default {}"})
    assert not any(s["id"] in ("console", "mod-paged") for s in get(studio, "info")["sections"])
    call(studio, "PATCH", "settings", {"allow_code_mods": True})
    ids = [s["id"] for s in get(studio, "info")["sections"]]
    assert "console" in ids and "mod-paged" in ids and "mod-off-page" not in ids
    page = next(s for s in get(studio, "info")["sections"] if s["id"] == "mod-paged")
    assert page == {"id": "mod-paged", "title": "Paged", "module": "/mods/paged/studio/section.js", "from_mod": "paged", "group": "play"}


def test_settings_change_code_mods_and_refuse_anything_but_true_or_false(studio):
    assert get(studio, "settings") == {"allow_code_mods": False, "data_dir": studio.ctx.cfg.data_dir}
    assert call(studio, "PATCH", "settings", {"allow_code_mods": True})["allow_code_mods"] is True
    with open(studio.ctx.cfg.path, encoding="utf-8") as f:
        assert json.load(f)["allow_code_mods"] is True
    assert call(studio, "PATCH", "settings", {})["allow_code_mods"] is True
    with pytest.raises(ValueError, match="true or false"):
        call(studio, "PATCH", "settings", {"allow_code_mods": "yes"})


def test_changes_name_the_mods_waiting_to_go_in(studio, sandbox):
    assert get(studio, "changes") == {"installed": False, "on": [], "off": [], "changed": [], "redo": [], "any": False,
                                      "names": {}, "game_running": False}
    make_mod(studio, "tweaks", {"name": "Tweaks"})
    sandbox.running = True
    r = get(studio, "changes")
    assert r["on"] == ["tweaks"] and r["any"] and r["names"] == {"tweaks": "Tweaks"} and r["game_running"]


def test_an_unknown_route_is_a_lookup_error(studio):
    with pytest.raises(LookupError, match="unknown API route"):
        get(studio, "nothing/here")


# ---------- getting set up ----------
def test_setup_lists_every_step_undone_without_a_game(studio):
    s = get(studio, "setup")
    assert s["game"] == {"ok": False, "dir": None, "steam": None, "steam_text": None}
    assert s["save"] == {"ok": False} and s["backup"] == {"ok": False, "latest": None}
    assert s["loader"]["ok"] is False and s["pages"]["ok"] is False and s["pages"]["installed"] is False
    assert s["running"] is False and s["done"] is False and s["inbox"] is None


def test_setup_with_the_fake_game_and_a_save(studio, fake_game, save):
    s = get(studio, "setup")
    assert s["game"]["ok"] and s["game"]["dir"] == fake_game and s["game"]["steam"] is None
    assert s["save"]["ok"] and not s["backup"]["ok"] and not s["loader"]["ok"] and not s["done"]


def test_setup_game_takes_the_games_folder_or_its_exes_and_refuses_others(studio, tmp_path):
    game = tmp_path / "Elsewhere"
    win64 = game / "Wrc" / "Binaries" / "Win64"
    win64.mkdir(parents=True)
    (win64 / EXE_NAME).write_bytes(b"")
    assert post(studio, "setup/game", {"dir": str(win64)}) == {"dir": str(game)}
    with open(studio.ctx.cfg.path, encoding="utf-8") as f:
        assert json.load(f)["game_dir"] == str(game)
    assert get(studio, "info")["game_dir"] == str(game)
    for bad in ({"dir": str(tmp_path)}, {}, {"dir": None}, {"dir": ["x"]}, {"dir": 7}):
        with pytest.raises(ValueError, match="the game isn't in"):
            post(studio, "setup/game", bad)


def test_setup_backup_makes_the_first_safety_copy_once_there_is_a_save(studio):
    assert post(studio, "setup/backup") == {"name": None}
    write_save(studio.ctx.cfg.save_dir)
    first = post(studio, "setup/backup")["name"]
    assert first.endswith("-first-run") and post(studio, "setup/backup") == {"name": None}
    assert get(studio, "backups") == [first] and get(studio, "setup")["backup"] == {"ok": True, "latest": first}


# ---------- mods: list, make, change, switch, remove, restore, pack as .zip ----------
def test_a_mod_is_made_listed_changed_switched_removed_and_put_back(studio):
    made = post(studio, "mods", {"id": "my-mods", "name": "My mods", "description": "Mine"})
    assert made["id"] == "my-mods" and made["name"] == "My mods" and made["enabled"] is False and made["kinds"] == []
    (m,) = get(studio, "mods")
    assert m["id"] == "my-mods" and m["problems"] == [] and m["needed_by"] == [] and m["preset"] is False
    assert m["outdated"] is None and m["game_builds"] and m["menu_pages"] is False and m["pack"] is False
    changed = call(studio, "PATCH", "mods/my-mods", {"enabled": True, "priority": 2, "author": "me", "version": "1.1"})
    assert changed["enabled"] and changed["priority"] == 2 and changed["author"] == "me" and changed["version"] == "1.1"
    assert post(studio, "mods/my-mods/switch", {"on": False}) == {"changed": [{"id": "my-mods", "name": "My mods", "on": False}], "blocked_by": []}
    assert get(studio, "mods")[0]["enabled"] is False
    gone = post(studio, "mods/my-mods/remove")
    assert gone["blocked_by"] == [] and gone["turned_off"] == [] and gone["moved_to"].endswith("-removed-my-mods")
    assert get(studio, "mods") == []
    (r,) = get(studio, "mods/removed")
    assert r["id"] == "my-mods" and r["why"] == "removed" and r["title"] == "My mods" and r["name"] == gone["moved_to"]
    assert post(studio, "mods/restore", {"name": gone["moved_to"]}) == {"restored": "my-mods"}
    assert [(m["id"], m["enabled"]) for m in get(studio, "mods")] == [("my-mods", False)]
    assert get(studio, "mods/removed") == []


def test_making_a_mod_refuses_bad_ids_missing_keys_and_wrong_types(studio):
    with pytest.raises(ValueError, match='needs "id"'):
        post(studio, "mods", {"name": "No id"})
    with pytest.raises(ValueError, match='"id" should be text'):
        post(studio, "mods", {"id": ["list"]})
    with pytest.raises(ValueError, match="lowercase"):
        post(studio, "mods", {"id": "Bad Id"})
    with pytest.raises(ValueError, match='"priority" should be a whole number'):
        post(studio, "mods", {"id": "fine", "priority": "high"})
    with pytest.raises(ValueError, match='"enabled" should be true or false'):
        post(studio, "mods", {"id": "fine", "enabled": 1})
    with pytest.raises(ValueError, match='"name" should be text'):
        post(studio, "mods", {"id": "fine", "name": {"en": "x"}})
    post(studio, "mods", {"id": "fine"})
    with pytest.raises(ValueError, match="already exists"):
        post(studio, "mods", {"id": "fine"})
    assert get(studio, "mods") and len(get(studio, "mods")) == 1   # the refused ones made no folder


def test_changing_a_mod_refuses_unknown_mods_and_wrong_types(studio):
    with pytest.raises(LookupError, match="no mod named nope"):
        call(studio, "PATCH", "mods/nope", {"enabled": True})
    folder = make_mod(studio, "tweaks", {"priority": 1})
    with pytest.raises(ValueError, match='"priority" should be a whole number'):
        call(studio, "PATCH", "mods/tweaks", {"priority": [1]})
    with pytest.raises(ValueError, match='"enabled" should be true or false'):
        call(studio, "PATCH", "mods/tweaks", {"enabled": "on"})
    with open(os.path.join(folder, "mod.json"), encoding="utf-8") as f:
        assert json.load(f)["priority"] == 1   # untouched
    assert call(studio, "PATCH", "mods/tweaks", {"priority": None, "name": "Tweaks!"})["name"] == "Tweaks!"


def test_switching_on_brings_what_a_mod_needs_and_off_asks_about_the_mods_needing_it(studio):
    make_mod(studio, "base", {"enabled": False})
    make_mod(studio, "dep", {"enabled": False, "requires": ["base"]})
    on = post(studio, "mods/dep/switch", {"on": True})
    assert [(c["id"], c["on"]) for c in on["changed"]] == [("dep", True), ("base", True)]
    assert post(studio, "mods/base/switch", {"on": False}) == {"changed": [], "blocked_by": [{"id": "dep", "name": "Dep"}]}
    assert {m["id"]: m["enabled"] for m in get(studio, "mods")} == {"base": True, "dep": True}
    off = post(studio, "mods/base/switch", {"on": False, "cascade": True})
    assert sorted(c["id"] for c in off["changed"]) == ["base", "dep"] and off["blocked_by"] == []
    with pytest.raises(LookupError, match="no mod named nope"):
        post(studio, "mods/nope/switch", {"on": True})
    make_mod(studio, "lonely", {"enabled": False, "requires": ["missing"]})
    with pytest.raises(ValueError, match="add it first"):
        post(studio, "mods/lonely/switch", {"on": True})
    assert get(studio, "mods")[2]["problems"] == []   # off, so what it needs isn't a problem yet


def test_removing_a_mod_that_others_need_is_blocked_unless_they_go_off_too(studio):
    make_mod(studio, "base")
    make_mod(studio, "dep", {"requires": ["base"]})
    assert post(studio, "mods/base/remove") == {"blocked_by": [{"id": "dep", "name": "Dep"}]}
    assert len(get(studio, "mods")) == 2
    r = post(studio, "mods/base/remove", {"cascade": True})
    assert r["turned_off"] == ["Dep"] and r["blocked_by"] == [] and r["moved_to"].endswith("-removed-base")
    (dep,) = get(studio, "mods")
    assert dep["id"] == "dep" and dep["enabled"] is False
    with pytest.raises(LookupError):
        post(studio, "mods/base/remove")


def test_putting_a_mod_back_needs_its_backups_name(studio):
    with pytest.raises(ValueError, match='needs "name"'):
        post(studio, "mods/restore", {})
    with pytest.raises(ValueError, match='"name" should be text'):
        post(studio, "mods/restore", {"name": 3})
    with pytest.raises(LookupError, match="no removed mod"):
        post(studio, "mods/restore", {"name": "20260101-000000-removed-x"})


def test_a_mod_whose_mod_json_cant_be_read_is_listed_off_with_the_problem_on_its_card(studio):
    make_mod(studio, "fine")
    broken = make_mod(studio, "broken", files={"mod.json": "{not json"})
    make_mod(studio, "listed", files={"mod.json": "[1, 2]"})
    found = {m["id"]: m for m in get(studio, "mods")}
    assert set(found) == {"fine", "broken", "listed"} and found["fine"]["problems"] == []
    assert found["broken"]["enabled"] is False and found["broken"]["name"] == "broken"
    assert found["broken"]["problems"][0].startswith("mod.json isn't valid: ") and "line 1" in found["broken"]["problems"][0]
    assert "fix it in a text editor" in found["broken"]["problems"][0]
    assert found["broken"]["problem"] == found["broken"]["problems"][0]   # the card's switch stays off for it
    assert found["listed"]["enabled"] is False and "should hold an object" in found["listed"]["problems"][0]
    assert get(studio, "changes")["on"] == ["fine"]
    with pytest.raises(ValueError, match="can't be read"):
        call(studio, "PATCH", "mods/broken", {"enabled": True})
    with pytest.raises(ValueError, match="should hold an object"):
        post(studio, "mods/listed/switch", {"on": True})
    with open(os.path.join(broken, "mod.json"), encoding="utf-8") as f:
        assert f.read() == "{not json"   # never written over


def test_status_and_the_build_say_why_a_mod_whose_mod_json_cant_be_read_is_left_out(studio, fake_game, capsys):
    from types import SimpleNamespace
    from wcmods import cli
    make_mod(studio, "fine")
    make_mod(studio, "broken", files={"mod.json": "{not json"})
    cli.cmd_status(studio.ctx, SimpleNamespace())
    lines = capsys.readouterr().out.splitlines()
    i = next(n for n, line in enumerate(lines) if line.lstrip().startswith("[ ] broken"))
    assert lines[i + 1].strip().startswith("left out: mod.json isn't valid: ") and "fix it in a text editor" in lines[i + 1]
    assert not any(line.strip().startswith("left out:") for line in lines[:i] + lines[i + 2:])   # fine says nothing
    # The build (`wcmods build`, install, the studio's Apply) says it among its warnings, which Apply's log lists.
    r = post(studio, "build")
    assert r["result"]["mods"] == ["fine"]
    (said,) = [w for w in r["result"]["warnings"] if w.startswith("broken ")]
    assert said.startswith("broken is left out: mod.json isn't valid: ") and "fix it in a text editor" in said
    assert not any(w.startswith("fine ") for w in r["result"]["warnings"])
    cli.cmd_build(studio.ctx, SimpleNamespace())
    assert f"  warning: {said}" in capsys.readouterr().out.splitlines()


def test_a_mod_made_for_an_older_game_is_used_anyway_on_this_build_only(studio, monkeypatch):
    make_mod(studio, "old")   # no "game_builds": made for the build every mod before them was made on
    with pytest.raises(RuntimeError, match="couldn't tell which build"):   # no game, no build to allow it on
        post(studio, "mods/old/allow-outdated")
    monkeypatch.setenv("WCMODS_GAME_BUILD", "99999999")   # as if Steam had installed a newer build
    (m,) = get(studio, "mods")
    assert m["outdated"] == {"made_for": [24847281], "allowed": False} and m["game_builds"] == [24847281]
    assert post(studio, "mods/old/allow-outdated") == {"build": 99999999, "allowed": True}
    with open(studio.ctx.cfg.path, encoding="utf-8") as f:
        assert json.load(f)["allow_outdated"] == {"old": [99999999]}
    assert get(studio, "mods")[0]["outdated"] == {"made_for": [24847281], "allowed": True}
    monkeypatch.setenv("WCMODS_GAME_BUILD", "99999998")   # another update: the choice was for that build only
    assert get(studio, "mods")[0]["outdated"]["allowed"] is False
    monkeypatch.setenv("WCMODS_GAME_BUILD", "99999999")
    assert post(studio, "mods/old/allow-outdated", {"on": False}) == {"build": 99999999, "allowed": False}
    assert get(studio, "mods")[0]["outdated"]["allowed"] is False
    with open(studio.ctx.cfg.path, encoding="utf-8") as f:
        assert json.load(f)["allow_outdated"] == {}
    with pytest.raises(LookupError, match="no mod named nope"):
        post(studio, "mods/nope/allow-outdated")


def test_a_palette_json_that_isnt_a_palette_is_a_problem_on_the_card_not_a_blank_page(studio):
    make_mod(studio, "a-list", files={"palette.json": []})
    make_mod(studio, "a-string", files={"palette.json": {"fur": "#ff0000"}})
    make_mod(studio, "not-json", files={"palette.json": "{"})
    make_mod(studio, "fine", files={"palette.json": {"fur": {"3": "#ff0000"}, "eyes": {"Amber": "#ffb300"}}})
    found = {m["id"]: m for m in get(studio, "mods")}
    assert found["fine"]["problems"] == [] and found["fine"]["preset"] is True
    for i in ("a-list", "a-string", "not-json"):
        (problem,) = found[i]["problems"]
        assert problem.startswith("palette.json") and "Error" not in problem and studio.ctx.mods_root not in problem
    assert "should be an object with its parts in it" in found["a-list"]["problems"][0]
    assert "fur should be an object of colours by slot" in found["a-string"]["problems"][0]
    assert "isn't valid" in found["not-json"]["problems"][0] and "line 1" in found["not-json"]["problems"][0]
    for i in ("a-list", "a-string"):
        with pytest.raises(ValueError):
            palettes.load(os.path.join(studio.ctx.mods_root, i, "palette.json"))
    options = get(studio, "cat/options")   # the bad ones are left out, the good one is in
    assert options["palette"]["fur"] == {"3": "#ff0000"} and options["palette"]["pattern"] == {}
    assert options["game_slots"] == 25 and options["feral_slots"] == [20, 21, 22, 23, 24]
    assert options["parts"]["pattern"] == 20 and options["parts"]["body"] == 9


def test_a_mod_downloads_as_a_zip_of_its_folder(studio):
    make_mod(studio, "share-me", {"version": "1.2"}, {"palette.json": {"fur": {"1": "#123456"}}})
    d = get(studio, "mods/share-me/zip")
    assert isinstance(d, Download) and d.filename == "share-me-1.2.zip" and d.ctype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(d.data)) as z:
        assert sorted(z.namelist()) == ["share-me/mod.json", "share-me/palette.json"]
    with pytest.raises(LookupError):
        get(studio, "mods/nope/zip")


def test_a_downloaded_zip_is_previewed_then_added(studio, tmp_path):
    z = zip_of(tmp_path / "cool.zip", {"Cool Tweaks/mod.json": {"name": "Cool Tweaks", "version": "2"},
                                        "Cool Tweaks/palette.json": {"fur": {"1": "#123456"}}})
    seen = post(studio, "mods/add", query={"step": "preview", "name": "cool.zip"}, upload=z)
    assert seen["code_allowed"] is False and len(seen["mods"]) == 1
    (m,) = seen["mods"]
    assert m["id"] == "cool-tweaks" and m["kinds"] == ["palette"] and m["code"] is False and m["existing"] is None
    assert get(studio, "mods") == []   # a preview adds nothing
    added = post(studio, "mods/add", query={"step": "add", "name": "cool.zip", "enable": "0"}, upload=z)
    assert added["added"][0]["id"] == "cool-tweaks" and added["added"][0]["replaced"] is None
    (now,) = get(studio, "mods")
    assert now["enabled"] is False and now["version"] == "2"
    again = post(studio, "mods/add", query={"step": "add", "name": "cool.zip", "ids": "cool-tweaks"}, upload=z)
    assert again["added"][0]["replaced"] and get(studio, "mods")[0]["enabled"] is True
    assert get(studio, "mods/removed")[0]["why"] == "replaced"
    with pytest.raises(ValueError, match="none of the mods asked for"):
        post(studio, "mods/add", query={"step": "add", "ids": "other"}, upload=z)


def test_adding_refuses_no_body_a_file_that_isnt_a_zip_and_a_zip_with_no_mod(studio, tmp_path):
    with pytest.raises(ValueError, match="send the .zip"):
        post(studio, "mods/add", query={"step": "preview"})
    plain = tmp_path / "plain.zip"
    plain.write_bytes(b"this is not a zip")
    with pytest.raises(zipfile.BadZipFile):
        post(studio, "mods/add", query={"step": "preview"}, upload=str(plain))
    with pytest.raises(ValueError, match="has no mod in it"):
        post(studio, "mods/add", query={"step": "preview"}, upload=zip_of(tmp_path / "empty.zip", {"readme.txt": "hi"}))


# ---------- a mod's files ----------
def test_a_mods_file_is_written_read_back_and_deleted(studio):
    make_mod(studio, "mine")
    assert get(studio, "mods/mine/file/palette.json") == {"exists": False, "text": None}
    text = json.dumps({"fur": {"3": "#ff0000"}})
    assert call(studio, "PUT", "mods/mine/file/palette.json", {"text": text}) == {"saved": "palette.json", "requires": [], "problems": [], "left_out": []}
    with open(os.path.join(studio.ctx.mods_root, "mine", "palette.json"), encoding="utf-8") as f:
        assert f.read() == text + "\n"
    assert get(studio, "mods/mine/file/palette.json") == {"exists": True, "text": text + "\n"}
    assert get(studio, "mods")[0]["kinds"] == ["palette"]
    assert call(studio, "DELETE", "mods/mine/file/palette.json") == {"deleted": "palette.json"}
    assert call(studio, "DELETE", "mods/mine/file/palette.json") == {"deleted": "palette.json"}   # already gone: fine
    assert get(studio, "mods/mine/file/palette.json")["exists"] is False


def test_a_mods_file_is_only_one_the_studio_edits_and_only_valid_json(studio):
    make_mod(studio, "mine", {"studio_files": ["own.json", "../up.json", "sub/deep.json", ".hidden.json", "notes.txt", 5]})
    with pytest.raises(LookupError):
        get(studio, "mods/nope/file/palette.json")
    for name in ("mod.json", "up.json", "deep.json", ".hidden.json", "notes.txt", "section.py"):   # the slashed ones don't count
        with pytest.raises(PermissionError, match="the studio only edits"):
            call(studio, "PUT", f"mods/mine/file/{name}", {"text": "{}"})
    assert call(studio, "PUT", "mods/mine/file/own.json", {"text": "{}"})["saved"] == "own.json"
    with pytest.raises(ValueError, match='needs "text"'):
        call(studio, "PUT", "mods/mine/file/data.json", {})
    with pytest.raises(ValueError, match='"text" should be text'):
        call(studio, "PUT", "mods/mine/file/data.json", {"text": {"a": 1}})
    with pytest.raises(ValueError):
        call(studio, "PUT", "mods/mine/file/data.json", {"text": "{broken"})
    assert get(studio, "mods/mine/file/data.json")["exists"] is False


def test_saving_cats_or_quests_needs_the_sandbox_mod_and_says_what_keeps_a_quest_out(studio):
    make_mod(studio, "story")
    r = call(studio, "PUT", "mods/story/file/npcs.json", {"text": json.dumps({"npcs": [{"id": "moss", "name": "Mossfoot"}]})})
    assert r["requires"] == ["sandbox"] and r["problems"] == []
    quests = {"quests": [{"id": "q", "title": "Q", "giver": "nobody", "steps": [{"do": "talk", "lines": ["Hi"]}]}]}
    r = call(studio, "PUT", "mods/story/file/quests.json", {"text": json.dumps(quests)})
    assert r["requires"] == ["sandbox"] and "isn't one of this mod's cats" in r["problems"][0]
    assert get(studio, "mods/story/file/quests.json")["exists"]   # saved all the same, to be fixed on the page


# ---------- the inbox: a mod dropped on the launcher ----------
def test_a_dropped_zip_waits_in_the_inbox_until_added_or_cleared(studio, tmp_path):
    assert get(studio, "mods/inbox") == {"mods": [], "name": None}
    with pytest.raises(LookupError, match="isn't waiting any more"):
        post(studio, "mods/inbox/add")
    z = zip_of(tmp_path / "dropped.zip", {"dropped/mod.json": {"name": "Dropped"}})
    onboarding.put_inbox(z)
    waiting = get(studio, "mods/inbox")
    assert waiting["name"] == "dropped.zip" and waiting["mods"][0]["id"] == "dropped" and waiting["code_allowed"] is False
    assert get(studio, "setup")["inbox"] == "dropped.zip"
    added = post(studio, "mods/inbox/add", {"ids": ["dropped"], "enable": False})
    assert added["added"][0]["id"] == "dropped" and get(studio, "mods")[0]["enabled"] is False
    assert get(studio, "mods/inbox") == {"mods": [], "name": None}
    onboarding.put_inbox(z)
    assert post(studio, "mods/inbox/clear") == {"cleared": True} and get(studio, "mods/inbox")["name"] is None
    folder = tmp_path / "two"
    for i in ("one", "two"):
        (folder / i).mkdir(parents=True)
        (folder / i / "mod.json").write_text(json.dumps({"name": i}), encoding="utf-8")
    onboarding.put_inbox(str(folder))
    assert [m["id"] for m in get(studio, "mods/inbox")["mods"]] == ["one", "two"]
    assert [a["id"] for a in post(studio, "mods/inbox/add", {"ids": ["two"]})["added"]] == ["two"]


def test_a_dropped_file_that_isnt_a_zip_is_said_once_and_forgotten(studio, tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"nope")
    onboarding.put_inbox(str(bad))
    with pytest.raises(zipfile.BadZipFile):
        get(studio, "mods/inbox")
    assert get(studio, "mods/inbox") == {"mods": [], "name": None}


# ---------- mod packs ----------
def test_a_pack_is_made_played_on_its_own_and_stopped(studio):
    make_mod(studio, "a")
    make_mod(studio, "b", {"enabled": False})
    make_mod(studio, "c")
    p = post(studio, "packs", {"name": "Moon", "mods": ["b"], "author": "me", "version": "1", "description": "d"})
    assert p["id"] == "moon" and p["pack"] is True and p["requires"] == ["b"] and p["enabled"] is False
    assert p["kinds"] == ["mod pack"]
    desc = get(studio, "packs")
    assert desc["playing"] is None and [m["id"] for m in desc["packs"][0]["mods"]] == ["b"]
    assert desc["packs"][0]["mods"][0]["direct"] and desc["packs"][0]["mods"][0]["present"]
    assert post(studio, "packs/moon/play") == {"on": ["b", "moon"], "off": ["a", "c"]}
    assert get(studio, "packs")["playing"] == "moon"
    assert {m["id"]: m["enabled"] for m in get(studio, "mods")} == {"a": False, "b": True, "c": False, "moon": True}
    assert post(studio, "packs/stop") == {"on": ["a", "c"], "off": ["b", "moon"]}
    assert get(studio, "packs")["playing"] is None
    assert post(studio, "packs/stop") == {"on": [], "off": []}
    # Changing it keeps its id; a second new pack with the same name gets a number.
    assert post(studio, "packs", {"id": "moon", "name": "Moon 2", "mods": ["a"]})["name"] == "Moon 2"
    assert post(studio, "packs", {"name": "Moon", "mods": ["c"]})["id"] == "moon-2"


def test_a_pack_needs_mods_that_are_there_and_not_packs(studio):
    make_mod(studio, "a")
    with pytest.raises(ValueError, match="at least one mod"):
        post(studio, "packs", {"name": "Empty", "mods": []})
    with pytest.raises(ValueError, match="no mod nope"):
        post(studio, "packs", {"name": "Lost", "mods": ["nope"]})
    with pytest.raises(ValueError, match="should be a list"):
        post(studio, "packs", {"name": "Text", "mods": "a"})
    post(studio, "packs", {"name": "Moon", "mods": ["a"]})
    with pytest.raises(ValueError, match="mod pack itself"):
        post(studio, "packs", {"name": "Bigger", "mods": ["moon"]})
    with pytest.raises(LookupError, match="no mod pack named"):
        post(studio, "packs/a/play")
    with pytest.raises(LookupError, match="no mod pack named"):
        post(studio, "packs/nope/play")
    assert get(studio, "mods")[0]["id"] == "a" and len(get(studio, "mods")) == 2


# ---------- in-game options ----------
def test_ingame_options_are_read_and_changed_and_mistakes_refused(studio):
    o = get(studio, "ingame")
    assert o["console"] is False and o["console_available"] is False and o["cheats"] is None
    assert o["key"] == "INS" and o["size"] == 1.0 and o["pad"] == "Gamepad_Special_Left"
    assert ["INS", "Name"] not in o["keys"] and o["keys"][0] == ["INS", "Insert"] and o["sizes"][1] == [1, "Normal"]
    assert o["pads"] and all(len(p) == 2 for p in o["pads"])
    changed = call(studio, "PATCH", "ingame", {"key": "F5", "size": 1.25, "console": True})
    assert changed["key"] == "F5" and changed["size"] == 1.25 and changed["console"] is True
    with open(studio.ctx.cfg.path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["menu_key"] == "F5" and data["menu_scale"] == 1.25 and data["console"] is True
    for bad, said in (({"size": "big"}, "size should be a number"), ({"size": 9}, "size should be a number"),
                      ({"key": "Q"}, "key should be one of"), ({"pad": "nope"}, "pad should be one of"),
                      ({"size": True}, "size should be a number")):
        with pytest.raises(ValueError, match=said):
            call(studio, "PATCH", "ingame", bad)
    assert get(studio, "ingame")["key"] == "F5"   # a refused change changed nothing


# ---------- save backups ----------
def test_the_save_is_backed_up_and_restored(studio, save, sandbox):
    saves = studio.ctx.cfg.save_dir
    b = post(studio, "backup")
    assert b["name"].endswith("-studio") and b["files"] == [SAV_NAME]
    assert get(studio, "backups") == [b["name"]]
    time.sleep(1.1)   # a backup's name is to the second
    before = os.path.getsize(os.path.join(saves, SAV_NAME))
    with open(os.path.join(saves, SAV_NAME), "ab") as f:
        f.write(b"spoiled")
    assert post(studio, "restore", {"name": b["name"]}) == {"restored": [SAV_NAME]}
    assert os.path.getsize(os.path.join(saves, SAV_NAME)) == before
    names = get(studio, "backups")
    assert len(names) == 2 and names[0].endswith("-before-restore") and names[1] == b["name"]   # newest first
    with pytest.raises(ValueError, match='needs "name"'):
        post(studio, "restore", {})
    with pytest.raises(FileNotFoundError, match="no backup named"):
        post(studio, "restore", {"name": "20260101-000000-manual"})
    sandbox.running = True
    with pytest.raises(RuntimeError, match="close the game"):
        post(studio, "restore", {"name": b["name"]})


def test_backing_up_without_a_save_is_refused_and_leaves_no_empty_backup(studio):
    with pytest.raises(ValueError, match="no save to back up yet"):
        post(studio, "backup")
    assert get(studio, "backups") == [] and get(studio, "setup")["backup"]["ok"] is False
    assert not os.path.isdir(studio.ctx.backups) or os.listdir(studio.ctx.backups) == []
    write_save(studio.ctx.cfg.save_dir)   # the first safety copy still happens, as nothing counted as one
    assert post(studio, "setup/backup")["name"].endswith("-first-run")


# ---------- your cat, the save, its bindings ----------
def test_cat_without_a_save_has_the_options_and_no_cats(studio):
    r = get(studio, "cat")
    assert r["current"] == {} and r["cats"] == [] and r["scars"]["current"] == {} and r["look"]["current"] == {}
    assert r["palette"] == {"fur": {}, "pattern": {}, "marking": {}} and r["game_slots"] == 25
    assert r["parts"]["fur"] == "Fur Color" and "ear" in r["scars"]["types"] and r["look"]["size"] == [0.05, 1.5]


def test_cat_with_a_save_but_no_game_names_the_cats_by_their_places(studio, save):
    r = get(studio, "cat")
    assert r["current"] == {"fur": 3, "pattern": 5, "marking": 7, "eye_left": 2, "eye_right": 4}
    assert r["scars"]["current"] == {"eye": 0, "ear": 1, "back": 0, "chest": 0}
    look = r["look"]["current"]
    assert look["body"] == 2 and look["tail"] == 1 and look["eyes"] == 3 and look["pattern"] == 4 and look["size"] == 1.1
    (warrior,) = r["cats"]
    assert warrior["target"] == warrior["name"] == warrior["where"] == "RiverClan/Warrior/0"
    assert warrior["role"] == "Warrior" and warrior["current"]["slots"]["fur"] == 3 and warrior["current"]["look"]["size"] == 1.1


def test_cat_with_a_game_whose_files_cant_be_read_still_opens(studio, fake_game, save):
    r = get(studio, "cat")
    assert r["current"]["fur"] == 3 and r["cats"][0]["name"] == "RiverClan/Warrior/0"


def test_cat_options_merge_the_enabled_palettes_only(studio):
    make_mod(studio, "warm", {"priority": 1}, {"palette.json": {"fur": {"3": "#ff0000"}, "pattern": {"30": "#00ff00"}}})
    make_mod(studio, "cool", {"priority": 2}, {"palette.json": {"fur": {"3": "#0000ff", "4": "#111111"}}})
    make_mod(studio, "off", {"enabled": False}, {"palette.json": {"fur": {"9": "#999999"}}})
    o = get(studio, "cat/options")
    assert o["palette"]["fur"] == {"3": "#0000ff", "4": "#111111"} and o["palette"]["pattern"] == {"30": "#00ff00"}


def test_the_save_is_read_as_its_account_and_data(studio, save):
    r = get(studio, "save")
    assert r["account"] == "acct" and r["data"]["Shared"]["General"] == {"CurrentCatSlot": 0}
    assert "NPCData" in r["data"]["0"] and isinstance(r["save_time"], float)


def test_the_saves_bindings_are_read_per_device(studio, save):
    r = get(studio, "game/bindings")
    assert r["bindings"] == {"keyboard": {"Player_Interact": "E", "Player_Jump": "SpaceBar"},
                             "gamepad": {"Player_Jump": "Gamepad_FaceButton_Bottom"}}
    assert isinstance(r["save_time"], float)


def test_without_a_save_the_save_routes_say_to_start_the_game(studio):
    for path in ("save", "game/bindings"):
        with pytest.raises(LookupError, match="no save yet"):
            get(studio, path)
    write_save(studio.ctx.cfg.save_dir, {"acct": {"0": {}}})   # a save the game hasn't finished writing
    with pytest.raises(LookupError, match="no key bindings yet"):
        get(studio, "game/bindings")
    assert get(studio, "cat")["cats"] == []


# ---------- the game without its files ----------
def test_game_routes_without_a_game_end_as_the_command_line_would(studio):
    for path in ("game/data", "game/eyes", "game/items", "names", "game/anim-sequences", "game/cat-shape"):
        with pytest.raises(SystemExit):
            get(studio, path)
    for path in ("build", "install", "uninstall", "play", "palettes/apply"):
        with pytest.raises(ValueError, match="hasn't found the game yet"):
            post(studio, path)
    assert NO_GAME.startswith("Clan Mod Studio hasn't found the game yet")


def test_a_game_folder_without_its_paks_says_its_files_cant_be_read(studio, fake_game):
    for path in ("game/data", "game/eyes", "game/items", "names"):
        with pytest.raises(gamefiles.Unreadable) as e:
            get(studio, path)
        assert "the game's files can't be read" in str(e.value) and "pakchunk0" in str(e.value)
        assert "Errno" not in str(e.value) and "Steam updating or verifying" in str(e.value)
    assert isinstance(e.value, RuntimeError)   # answered 400 by the handler, like any other sentence


def test_game_tables_come_from_the_games_log_or_the_tables_file_or_neither(studio, fake_game):
    assert get(studio, "game/tables") == {"tables": None, "source": None}
    with open(os.path.join(studio.root, "colour_tables.json"), "w", encoding="utf-8") as f:
        json.dump({"FurColors": ["#111111"]}, f)
    assert get(studio, "game/tables") == {"tables": {"FurColors": ["#111111"]}, "source": "colour_tables.json"}


def test_anim_kinds_list_the_animals_an_animation_can_be_for(studio):
    kinds = get(studio, "game/anim-kinds")["kinds"]
    assert kinds[0]["id"] == "cat" and kinds[0]["label"] == "Cats" and kinds[0]["examples"] > 0
    assert all(set(k) == {"id", "label", "examples"} for k in kinds)


def test_the_bridge_is_never_or_alive_or_stale(studio):
    from wcmods import bridge
    assert get(studio, "game/bridge") == {"alive": False, "never": True}
    folder = bridge.folder(studio.ctx.cfg)
    os.makedirs(folder)
    with open(os.path.join(folder, "status.json"), "w", encoding="utf-8") as f:
        json.dump({"level": "L_Forest"}, f)
    r = get(studio, "game/bridge")
    assert r["alive"] is True and r["level"] == "L_Forest" and r["age"] < bridge.ALIVE
    old = time.time() - bridge.ALIVE - 5
    os.utime(os.path.join(folder, "status.json"), (old, old))
    assert get(studio, "game/bridge")["alive"] is False


def test_the_game_is_started_only_with_a_game_and_while_it_isnt_running(studio, fake_game, sandbox):
    sandbox.running = True
    with pytest.raises(RuntimeError, match="already running"):
        post(studio, "play")
    assert sandbox.opened == []


def test_installing_with_stale_code_is_refused(studio, fake_game, monkeypatch):
    studio.code_stamp = 0.0   # as if wcmods' files were newer than the studio's start
    for path in ("build", "install", "play"):
        with pytest.raises(RuntimeError, match="Press Restart the studio"):
            post(studio, path)


def test_uninstalling_from_a_game_with_nothing_in_it_removes_nothing(studio, fake_game, sandbox):
    assert post(studio, "uninstall") == {"log": [], "result": {"removed": []}, "summary": None}
    sandbox.running = True
    with pytest.raises(RuntimeError, match="running"):
        post(studio, "uninstall")


def test_palettes_are_switched_as_presets_without_installing(studio, fake_game):
    make_mod(studio, "warm", files={"palette.json": {"fur": {"3": "#ff0000"}}})
    make_mod(studio, "cool", files={"palette.json": {"fur": {"3": "#0000ff"}}})
    make_mod(studio, "adds", files={"palette.json": {"pattern": {"30": "#00ff00"}}})
    make_mod(studio, "more", files={"palette.json": {"fur": {"3": "#0000ff"}}, "data.json": {}})
    with pytest.raises(ValueError, match="list of palette mod names"):
        post(studio, "palettes/apply", {"ids": "warm"})
    with pytest.raises(ValueError, match="not a palette mod: more"):
        post(studio, "palettes/apply", {"ids": ["more"]})
    with pytest.raises(ValueError, match="only add new colours"):
        post(studio, "palettes/apply", {"ids": ["adds"]})
    assert post(studio, "palettes/apply", {"ids": ["warm"]}) == {"log": [], "result": {"on": ["warm"], "off": ["cool"]},
                                                               "summary": None}
    assert {m["id"]: m["enabled"] for m in get(studio, "mods")} == {"adds": True, "cool": False, "more": True, "warm": True}


def test_opening_a_folder_asks_the_machine_for_the_right_one(studio, sandbox):
    make_mod(studio, "mine")
    assert post(studio, "open", {"what": "mods"}) == {"opened": studio.ctx.mods_root}
    assert post(studio, "open", {"what": "data"}) == {"opened": studio.ctx.cfg.data_dir}
    assert post(studio, "open", {"id": "mine"}) == {"opened": os.path.join(studio.ctx.mods_root, "mine")}
    assert sandbox.opened == [studio.ctx.mods_root, studio.ctx.cfg.data_dir, os.path.join(studio.ctx.mods_root, "mine")]
    with pytest.raises(LookupError):
        post(studio, "open", {"id": "nope"})
    with pytest.raises(LookupError):
        post(studio, "open", {})


# ---------- pictures and models of the mod's own ----------
def picture_file(path, w=16, h=16):
    with open(path, "wb") as f:
        f.write(png.write(w, h, bytes([200, 100, 50, 255]) * (w * h)))
    return str(path)


def test_a_picture_is_kept_in_the_mod_and_served_back(studio, tmp_path):
    make_mod(studio, "mine")
    pic = picture_file(tmp_path / "icon.png")
    r = post(studio, "mods/mine/picture", query={"name": "My Icon! (v2).png"}, upload=pic)
    assert r == {"path": "pictures/My-Icon-v2.png", "width": 16, "height": 16}
    back = get(studio, "mods/mine/picture/My-Icon-v2.png")
    assert isinstance(back, Download) and back.ctype == "image/png" and back.filename == "My-Icon-v2.png"
    with open(pic, "rb") as f:
        assert back.data == f.read()
    assert post(studio, "mods/mine/picture", query={"name": ""}, upload=pic)["path"] == "pictures/picture.png"
    with pytest.raises(LookupError, match="has no picture"):
        get(studio, "mods/mine/picture/other.png")
    with pytest.raises(LookupError):
        get(studio, "mods/mine/picture/../mod.json")


def test_a_picture_has_to_be_a_png_of_a_sensible_size(studio, tmp_path, monkeypatch):
    make_mod(studio, "mine")
    with pytest.raises(ValueError, match="send the picture"):
        post(studio, "mods/mine/picture", query={"name": "x.png"})
    plain = tmp_path / "x.png"
    plain.write_bytes(b"JPEG?")
    with pytest.raises(ValueError, match="isn't a PNG"):
        post(studio, "mods/mine/picture", query={"name": "x.png"}, upload=str(plain))
    with pytest.raises(ValueError, match="16 to 4096"):
        post(studio, "mods/mine/picture", query={"name": "x.png"}, upload=picture_file(tmp_path / "tiny.png", 8, 8))
    monkeypatch.setattr(studio_mod, "MAX_PICTURE", 100)
    with pytest.raises(ValueError, match="over 0 MB"):
        post(studio, "mods/mine/picture", query={"name": "x.png"}, upload=picture_file(tmp_path / "big.png", 64, 64))
    assert not os.path.isdir(os.path.join(studio.ctx.mods_root, "mine", "pictures"))


OBJ = "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 2\nf 1 2 3\nf 1 3 4\n"   # two triangles, in Blender's space (metres, Y up)


def test_a_model_on_the_ground_is_kept_in_the_mod_and_drawn(studio, tmp_path):
    make_mod(studio, "mine")
    obj = tmp_path / "herb.obj"
    obj.write_text(OBJ, encoding="utf-8")
    r = post(studio, "mods/mine/model", query={"name": "Herb Bush", "file": "herb.obj", "ground": "1"}, upload=str(obj))
    assert r["path"] == "models/Herb-Bush.obj" and r["vertices"] == 4 and r["triangles"] == 2 and "farthest_cm" not in r
    assert r["size_cm"] == [100.0, 200.0, 100.0]   # metres to cm; the file's Y up is the game's Z up
    view = get(studio, "mods/mine/model-view", query={"path": "models/Herb-Bush.obj", "ground": "1"})
    assert len(view["p"]) == 12 and view["t"] == [0, 1, 2, 0, 2, 3] and view["vertices"] == 4 and "farthest_cm" not in view
    with pytest.raises(LookupError, match="has no model"):
        get(studio, "mods/mine/model-view", query={"path": "models/other.obj", "ground": "1"})
    with pytest.raises(LookupError, match="has no model"):
        get(studio, "mods/mine/model-view", query={"path": "../../wcmods.json", "ground": "1"})   # outside the mod


def test_a_model_has_to_be_a_model_file_with_faces(studio, tmp_path):
    make_mod(studio, "mine")
    obj = tmp_path / "herb.obj"
    obj.write_text(OBJ, encoding="utf-8")
    with pytest.raises(ValueError, match="send the model"):
        post(studio, "mods/mine/model", query={"name": "x", "file": "herb.obj", "ground": "1"})
    with pytest.raises(ValueError, match="models are"):
        post(studio, "mods/mine/model", query={"name": "x", "file": "herb.fbx", "ground": "1"}, upload=str(obj))
    points = tmp_path / "points.obj"
    points.write_text("v 0 0 0\nv 1 0 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no triangles"):
        post(studio, "mods/mine/model", query={"name": "x", "file": "points.obj", "ground": "1"}, upload=str(points))
    assert not os.path.isdir(os.path.join(studio.ctx.mods_root, "mine", "models"))
