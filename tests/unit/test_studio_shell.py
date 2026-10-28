"""Clan Mod Studio's shell, through Studio.api over temporary folders (no game): what a save says about its
file, a damaged mod.json or palette.json listed rather than fatal, the log's progress and last-apply.log, the
restart route, a damaged wcmods.json set aside, the guide's renderer, and the handler's sentences."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from wcmods import config as config_mod, guide, mods as modlib, palettes, pipeline
from wcmods import studio as studio_mod
from wcmods.config import Config

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(os.path.abspath(os.sep), "Game")   # a game folder's path, in this system's own way
NPCS = {"npcs": [{"id": "mossfoot", "name": "Mossfoot", "title": "Elder"}]}
QUEST = {"quests": [{"id": "first", "title": "First", "giver": "mossfoot",
                     "steps": [{"do": "talk", "lines": ["Hello."]}]}]}


@pytest.fixture
def studio(studio):
    """The harness's studio (conftest.py: its root, data folder and saves all in the test's own folder, no game
    found), with `data` its data folder. Never Ctx(ROOT, ...): that would move a mods/, wcmods.json or backups/
    kept in the repository's folder into the test's, which is then deleted. The guide's tests point `root` at the
    repository for its docs/guide, which is only read."""
    studio.data = Path(studio.ctx.cfg.data_dir)
    (studio.data / "mods").mkdir(exist_ok=True)
    return studio


def call(st, method, path, body=None, query=None):
    return st.api(method, [p for p in path.split("/") if p], dict(body or {}), query)


def make_mod(st, mod_id, meta=None, files=None):
    folder = st.data / "mods" / mod_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "mod.json").write_text(json.dumps({"name": mod_id.title(), "enabled": True, **(meta or {})}) if meta != "broken"
                                     else "{not json", encoding="utf-8")
    for name, content in (files or {}).items():
        (folder / name).write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return folder


# ---------- A: what a save says about its file ----------
@pytest.mark.parametrize("name, good, bad, said", [
    ("palette.json", {"fur": {"0": "#f2e6d0"}}, {"fur": {"x": "#f2e6d0"}}, "slot numbers"),
    ("palette.json", {"eyes": {"Amber": ["#001018", "#00e5ff"]}}, {"fur": {"0": "not a colour"}}, "not a colour"),
    ("controls.json", {"keyboard": {"Player_Interact": "F"}}, {"nope": {}}, "should be one of"),
    ("mouselook.json", {"sensitivity": 1.0}, {"sensitivity": "high"}, "sensitivity"),
    ("names.json", {"prefixes": {"remove": ["Moon"]}}, {"hats": {}}, "should be one of"),
    ("cats.json", {"player": {"colours": {"fur": "#7a6a58"}}}, {"dog": {}}, "isn't something it knows"),
    ("save.json", {"set": {"0/GameplayProgression/Level": 5}}, {"set": "x"}, "must be objects"),
    ("items.json", {"items": [{"id": "MoonHerb", "name": "Moon herb", "description": "Glows."}]}, {"items": "x"}, "list of items"),
    ("animations.json", {"animations": []}, {"animations": "x"}, "should be an object"),
    ("quests.json", QUEST, {"quests": [{"id": "q", "title": "Q", "giver": "nobody", "steps": []}]}, "isn't one of this mod's cats"),
])
def test_saving_a_file_says_what_would_keep_it_out_of_the_game(studio, name, good, bad, said):
    make_mod(studio, "mine", files={"npcs.json": NPCS})
    ok = call(studio, "PUT", f"mods/mine/file/{name}", {"text": json.dumps(good)})
    assert ok["saved"] == name and ok["problems"] == []
    r = call(studio, "PUT", f"mods/mine/file/{name}", {"text": json.dumps(bad)})
    assert len(r["problems"]) == 1 and said in r["problems"][0]
    for word in ("Error", "section", "--force", "Traceback"):
        assert word not in r["problems"][0]
    # The file is saved either way: the mistake is the player's to fix when they like.
    assert json.loads((studio.data / "mods" / "mine" / name).read_text(encoding="utf-8")) == bad


def test_a_file_checked_against_the_game_waits_for_apply_while_the_game_cant_be_read(studio):
    make_mod(studio, "mine")
    r = call(studio, "PUT", "mods/mine/file/data.json", {"text": json.dumps({"TuningData.csv": {"x": 1}})})
    assert r["problems"] == [studio_mod.CHECK_LATER]
    # With a game folder whose paks aren't there (Steam updating it, say): the same, not an error.
    game = studio.data / "Game"
    (game / "Wrc" / "Binaries" / "Win64").mkdir(parents=True)
    (game / "Wrc" / "Binaries" / "Win64" / config_mod.EXE_NAME).write_bytes(b"")
    studio.ctx.cfg.data["game_dir"] = str(game)
    r = call(studio, "PUT", "mods/mine/file/data.json", {"text": json.dumps({"TuningData.csv": {"x": 1}})})
    assert r["problems"] == [studio_mod.CHECK_LATER]


def test_cats_and_quests_are_checked_together_and_need_the_sandbox_mod(studio):
    make_mod(studio, "story")
    r = call(studio, "PUT", "mods/story/file/npcs.json", {"text": json.dumps(NPCS)})
    assert r["problems"] == [] and r["requires"] == ["sandbox"]
    r = call(studio, "PUT", "mods/story/file/quests.json", {"text": json.dumps(QUEST)})
    assert r["problems"] == []
    # The cat the quest's giver names goes: the quest's file is what's wrong now.
    r = call(studio, "PUT", "mods/story/file/npcs.json", {"text": json.dumps({"npcs": []})})
    assert r["problems"] and "mossfoot" in r["problems"][0]


def test_a_file_shaped_wrong_is_said_without_python_names(studio, monkeypatch):
    make_mod(studio, "mine")

    class Reader:   # a section that trips over a list where it wants an object, as a file edited by hand can make it
        def claims(self, mod):
            return True

        def collect(self, mod, ctx):
            return [].get("x")
    monkeypatch.setattr(studio_mod, "owner", lambda file: Reader())
    r = call(studio, "PUT", "mods/mine/file/names.json", {"text": json.dumps({"prefixes": []})})
    assert r["problems"] == ["names.json isn't shaped the way the page writes it (docs/formats.md shows how it's laid out)"]


def test_cats_saved_into_a_mod_whose_mod_json_is_broken_are_saved_and_the_problem_said(studio):
    make_mod(studio, "story", meta="broken")
    r = call(studio, "PUT", "mods/story/file/npcs.json", {"text": json.dumps(NPCS)})
    assert r["saved"] == "npcs.json" and r["requires"] == []
    assert r["problems"][0].startswith("The mod can't note that it needs the Sandbox mode mod, and stays off, until its "
                                       "mod.json is fixed: mod.json isn't valid")
    assert json.loads((studio.data / "mods" / "story" / "npcs.json").read_text(encoding="utf-8")) == NPCS


def test_studio_log_starts_again_past_its_size(studio, monkeypatch):
    monkeypatch.setattr(studio_mod, "STUDIO_LOG_MAX", 200)
    for i in range(3):
        studio.log_error(f"GET /api/x{i}", ValueError("x" * 300))
    log, old = studio.data / studio_mod.STUDIO_LOG, studio.data / (studio_mod.STUDIO_LOG + ".1")
    assert old.exists() and "GET /api/x2" in log.read_text(encoding="utf-8")
    assert "GET /api/x0" not in log.read_text(encoding="utf-8") + old.read_text(encoding="utf-8")   # two at most


@pytest.fixture
def planted():
    """A mod in a mods/ folder in the repository's folder, as a player who keeps theirs there has (WCMODS_DATA
    pointing at it, or from before they moved out of it); taken away again afterwards."""
    folder = Path(ROOT) / "mods" / f"zz-wcmods-test-planted-{os.getpid()}"
    made_mods = not folder.parent.exists()
    folder.mkdir(parents=True)
    (folder / "mod.json").write_text(json.dumps({"name": "Planted", "enabled": True}), encoding="utf-8")
    try:
        yield folder
    finally:
        for f in (folder.iterdir() if folder.exists() else []):
            f.unlink()
        if folder.exists():
            folder.rmdir()
        if made_mods and folder.parent.exists() and not any(folder.parent.iterdir()):
            folder.parent.rmdir()


def test_a_planted_mods_folder_in_the_repositorys_folder_is_left_where_it_is(planted, studio, tmp_path, monkeypatch):
    """This module's `studio` (made after the folder was planted) and the command line start from a folder of
    their own, so nothing moves the player's mods into a test's folder, which is deleted. (conftest.py checks
    the same of the whole run.)"""
    assert [m["id"] for m in call(studio, "GET", "mods")] == []
    from wcmods.cli import main
    monkeypatch.setenv(config_mod.DATA_ENV, str(tmp_path / "cli-data"))
    (tmp_path / "cli-root").mkdir()
    try:
        main(str(tmp_path / "cli-root"), ["status"])
    except SystemExit:
        pass
    assert (planted / "mod.json").is_file()
    assert not (studio.data / "mods" / planted.name).exists() and not (tmp_path / "cli-data" / "mods" / planted.name).exists()


def test_broken_json_isnt_written_and_is_said_in_words(studio):
    make_mod(studio, "mine")
    with pytest.raises(ValueError, match=r"names\.json isn't valid: .* at line 1"):
        call(studio, "PUT", "mods/mine/file/names.json", {"text": "{bad"})
    assert not (studio.data / "mods" / "mine" / "names.json").exists()
    with pytest.raises(ValueError, match='needs "text"'):
        call(studio, "PUT", "mods/mine/file/names.json", {})


def test_deleting_a_pages_file(studio):
    make_mod(studio, "mine", files={"save.json": {"set": {}}})
    assert call(studio, "DELETE", "mods/mine/file/save.json") == {"deleted": "save.json"}
    assert not (studio.data / "mods" / "mine" / "save.json").exists()
    assert call(studio, "DELETE", "mods/mine/file/save.json") == {"deleted": "save.json"}   # gone already: fine
    assert call(studio, "GET", "mods/mine/file/save.json") == {"exists": False, "text": None}


# ---------- A: one bad mod doesn't take the list down ----------
def test_a_mod_whose_mod_json_cant_be_read_is_listed_with_its_problem(studio):
    make_mod(studio, "fine", files={"palette.json": {"fur": {"0": "#fff"}}})
    make_mod(studio, "broken", meta="broken")
    (studio.data / "mods" / "list").mkdir()
    (studio.data / "mods" / "list" / "mod.json").write_text("[1, 2]", encoding="utf-8")
    found = {m["id"]: m for m in call(studio, "GET", "mods")}
    assert set(found) == {"fine", "broken", "list"}
    assert found["fine"]["problem"] is None and found["fine"]["enabled"] and found["fine"]["kinds"] == ["palette"]
    assert found["broken"]["name"] == "broken" and not found["broken"]["enabled"] and found["broken"]["kinds"] == []
    assert found["broken"]["problem"].startswith("mod.json isn't valid: ") and "line 1" in found["broken"]["problem"]
    assert "should hold an object" in found["list"]["problem"]
    assert found["broken"]["problems"] == [found["broken"]["problem"]]   # on the card, with the switch off
    # It can't be changed until it's fixed, and that's said in words.
    with pytest.raises(ValueError, match="can't be changed"):
        call(studio, "PATCH", "mods/broken", {"enabled": True})
    # The rest of the studio takes it in its stride.
    assert call(studio, "GET", "changes")["on"] == ["fine"]
    info = call(studio, "GET", "info")
    assert info["warning"] is None and info["restartable"] is False and info["data_dir"] == str(studio.data)


@pytest.mark.parametrize("text, said", [
    ("[1]", "should be an object"),
    ("{bad", "isn't valid"),
    ('{"fur": "red"}', "fur should be an object of colours by slot"),
    ('{"fur": {"0": "nope"}}', "not a colour"),
    ('{"fur": {"0": 12}}', "not a colour"),
    ('{"eyes": {"Amber": [1, "x"]}}', "eyes.Amber"),
    ('{"hats": {}}', "unknown part"),
    ('{"coats": {"Ash": {"fur": 3, "like": 1}}}', "coats.Ash.fur"),
])
def test_a_bad_palette_is_a_sentence_and_doesnt_break_the_list(studio, text, said):
    make_mod(studio, "pal", files={"palette.json": text})
    path = str(studio.data / "mods" / "pal" / "palette.json")
    with pytest.raises(ValueError) as e:
        palettes.load(path)
    assert said in str(e.value) and str(e.value).startswith("palette.json") and "Error" not in str(e.value)
    mod = modlib.Mod(str(studio.data / "mods" / "pal"))
    assert modlib.palette_only(mod) is True   # unreadable: left for the build to say
    listed = call(studio, "GET", "mods")
    assert [m["id"] for m in listed] == ["pal"] and listed[0]["preset"] is True
    assert call(studio, "GET", "cat/options")["palette"]["fur"] == {}   # the bad one is left out, not fatal


def test_a_missing_palette_file_is_a_sentence_too(tmp_path):
    with pytest.raises(ValueError, match=r"palette\.json can't be read"):
        palettes.load(str(tmp_path / "palette.json"))


# ---------- C: progress and the last apply ----------
def test_progress_shows_a_tasks_lines_while_it_runs_and_the_last_apply_keeps_them(studio):
    assert call(studio, "GET", "progress") == {"id": None, "title": None, "lines": [], "running": False}
    with pytest.raises(LookupError, match="Nothing has been applied"):
        call(studio, "GET", "last-apply")
    started, go = threading.Event(), threading.Event()

    def task(log):   # a fake build: logs, waits to be looked at, logs again
        log("reading your mods")
        started.set()
        go.wait(5)
        log("made the pak")
        return {"sections": {"palettes": {"title": "Colour palettes", "status": "ok", "mods": ["pal"], "errors": [], "failed": []}},
                "mods": ["pal"], "names": {"pal": "Pretty palette"}, "warnings": ["a thing to know"]}
    out = {}
    t = threading.Thread(target=lambda: out.update(studio.run(task, "Apply to game", keep=True, task="t1")))
    t.start()
    assert started.wait(5)
    mid = call(studio, "GET", "progress")
    assert mid == {"id": "t1", "title": "Apply to game", "lines": ["reading your mods"], "running": True}
    go.set()
    t.join(5)
    done = call(studio, "GET", "progress")
    assert done["running"] is False and done["lines"] == ["reading your mods", "made the pak"]
    assert out["log"] == ["reading your mods", "made the pak"] and out["result"]["mods"] == ["pal"]
    assert out["summary"] == "Put 1 mod in the game: Pretty palette. 1 warning."
    last = call(studio, "GET", "last-apply")
    assert last["title"] == "Apply to game" and last["when"]
    assert last["summary"] == ["Put 1 mod in the game: Pretty palette. 1 warning.", "warning: a thing to know"]
    assert last["log"] == "reading your mods\nmade the pak"
    assert (studio.data / studio_mod.LAST_APPLY).read_text(encoding="utf-8").startswith("Apply to game · ")


def test_a_task_waiting_for_the_lock_never_shows_another_tasks_log_as_its_own(studio):
    # The last task's log is still there when the next is asked for, while the lock is held by something else
    # (a save, say): /progress shows the new task, with no lines yet, not the old log.
    studio.run(lambda log: log("the last check's line"), "Check mods", task="old")
    out = {}
    with studio.lock:
        t = threading.Thread(target=lambda: out.update(studio.run(lambda log: log("mine"), "Apply to game", task="new")))
        t.start()
        for _ in range(100):
            if call(studio, "GET", "progress")["id"] == "new":
                break
            time.sleep(0.02)
        assert call(studio, "GET", "progress") == {"id": "new", "title": "Apply to game", "lines": [], "running": True}
    t.join(5)
    assert out["log"] == ["mine"]
    # While another task runs, a waiting one leaves its progress alone: the page sees whose log it is by the id.
    started, go = threading.Event(), threading.Event()

    def first(log):
        log("first's line")
        started.set()
        go.wait(5)
    a = threading.Thread(target=lambda: studio.run(first, "Apply to game", task="a"))
    a.start()
    assert started.wait(5)
    b = threading.Thread(target=lambda: studio.run(lambda log: log("second's line"), "Check mods", task="b"))
    b.start()
    time.sleep(0.2)
    assert call(studio, "GET", "progress") == {"id": "a", "title": "Apply to game", "lines": ["first's line"], "running": True}
    go.set()
    a.join(5)
    b.join(5)
    assert call(studio, "GET", "progress")["id"] == "b"


def test_a_task_that_fails_is_kept_in_the_last_apply_with_what_blocked_it(studio):
    blocked = pipeline.InstallBlocked([("Colour palettes", "pal", "palette.json: fur keys are slot numbers")])

    def task(log):
        log("reading your mods")
        raise blocked
    with pytest.raises(pipeline.InstallBlocked):
        studio.run(task, "Play", keep=True)
    last = call(studio, "GET", "last-apply")
    assert last["title"] == "Play" and "Apply the rest anyway" in last["summary"][0] and "--force" not in last["summary"][0]
    assert last["log"] == "reading your mods"
    assert call(studio, "GET", "progress")["running"] is False


def test_plain_summary_names_mods_and_the_first_problem():
    names = {"pal": "Pretty palette", "cats": "My cats"}
    assert studio_mod.plain_summary({"mods": ["pal", "cats"], "names": names, "sections": {}, "warnings": []}) \
        == "Put 2 mods in the game: Pretty palette, My cats."
    assert studio_mod.plain_summary({"mods": [], "names": names, "sections": {}, "warnings": ["w"]}) \
        == "Put the mod menu in the game, with no mods on. 1 warning."
    bad = {"mods": ["pal"], "names": names, "warnings": [],
           "sections": {"palettes": {"title": "Colour palettes", "status": "partial", "mods": [],
                                     "errors": ["cats: oh no", "pal: bad slot"],
                                     "failed": [["cats", "oh no"], ["pal", "bad slot"]]}}}
    assert studio_mod.plain_summary(bad) == "Couldn't put My cats in: oh no (1 more problem in the log)"
    # A manifest an older wcmods wrote, without "failed".
    old = {"mods": [], "sections": {"save": {"title": "Save edits", "status": "failed", "mods": [], "errors": ["boom"]}}}
    assert studio_mod.plain_summary(old) == "Couldn't put Save edits in: boom"
    # Check my mods puts nothing in the game, and says so.
    assert studio_mod.plain_summary({"mods": ["pal", "cats"], "names": names, "sections": {}, "warnings": ["w"]}, checked=True) \
        == "Checked 2 mods: Pretty palette, My cats. Apply to game puts them in. 1 warning."
    assert studio_mod.plain_summary({"mods": [], "sections": {}, "warnings": []}, checked=True) == "Checked: no mods are on."
    assert studio_mod.plain_summary(bad, checked=True) == "My cats can't go in the game yet: oh no (1 more problem in the log)"


# A build whose sections all ran, but whose table edits then failed: the section's errors have it, and "failed"
# (as a wcmods before the fix wrote it) is empty.
PARTIAL = {"mods": ["tables"], "names": {"tables": "Tougher foxes"}, "warnings": [], "outputs": [], "ue4ss_mods": [], "save_ops": [],
           "sections": {"data": {"title": "Game data", "status": "partial", "mods": ["tables"], "failed": [],
                                 "errors": ["TuningData.csv: edits not applied (no row 'Fox')"]}}}


def test_a_section_whose_failures_are_only_in_its_errors_still_stops_the_install(tmp_path, monkeypatch):
    build = tmp_path / "build"
    build.mkdir()
    (build / "manifest.json").write_text(json.dumps(PARTIAL), encoding="utf-8")
    monkeypatch.setattr(pipeline, "game_running", lambda: False)
    cfg = Config(str(tmp_path), str(tmp_path))
    with pytest.raises(pipeline.InstallBlocked) as got:
        pipeline.install(cfg, str(build), str(tmp_path / "backups"), log=lambda m: None)
    assert got.value.problems == [("Game data", None, "TuningData.csv: edits not applied (no row 'Fox')")]
    assert studio_mod.plain_summary(PARTIAL) == "Couldn't put Game data in: TuningData.csv: edits not applied (no row 'Fox')"
    # A section that isn't ok with nothing said at all is still a problem, never an install that goes ahead.
    assert pipeline.section_problems({"title": "Names", "status": "failed", "errors": [], "failed": []}) == [(None, "it didn't build fully")]
    assert pipeline.section_problems({"status": "ok", "errors": ["x"], "failed": []}) == []


def test_a_builds_late_failures_go_in_failed_too(tmp_path, monkeypatch):
    """pipeline.build itself: a CSV edit that can't be made after the sections ran is in the section's "failed",
    and so are its save edits being left out, so the install stops."""
    from wcmods.cli import Ctx
    ctx = Ctx(str(tmp_path / "root"), str(tmp_path / "data"))

    class Section:   # a section that edits a table and the save
        id, title, owner = "data", "Game data", None

        def claims(self, mod):
            return True

        def collect(self, mod, c):
            return {}

        def build(self, c, items):
            c.save_ops.append({"op": "set", "path": "x", "value": 1, "section": "data"})
    monkeypatch.setattr(pipeline, "load_sections", lambda cfg, mods, log: ([Section()], []))
    monkeypatch.setattr(pipeline.BuildContext, "resolve_csv_edits",
                        lambda self: ({}, [("Wrc/Content/Data/TuningData.csv", ["data"], "no row 'Fox'")]))
    monkeypatch.setattr(pipeline.BuildContext, "resolve_table_rows", lambda self: ({}, []))
    monkeypatch.setattr(pipeline, "names_without_text", lambda cfg, c, game: [])
    monkeypatch.setattr(pipeline.gamebuild, "current", lambda cfg: {"build": None})
    monkeypatch.setattr(pipeline.gamebuild, "layout", lambda cfg, log=None: {"status": "verified", "moved": [], "lost": [], "offsets": {}})
    mod = studio_mod.mods.create(ctx.mods_root, "tables", "Tougher foxes", "", enabled=True)
    try:
        manifest = pipeline.build(ctx.cfg, [mod], str(tmp_path / "build"), log=lambda m: None)
    except Exception as e:   # noqa: BLE001 - past the report, the build reads the game's files, which aren't here
        pytest.skip(f"the build needs the game's files past its report here ({type(e).__name__}: {e})")
    rep = manifest["sections"]["data"]
    assert rep["status"] == "partial" and len(rep["failed"]) == len(rep["errors"]) == 2
    assert [text for _, text in rep["failed"]] == rep["errors"]


def test_install_blocked_has_the_facts_and_each_surface_words_them(tmp_path, monkeypatch):
    e = pipeline.InstallBlocked([("Colour palettes", "pal", "bad slot"), ("Save edits", None, "boom"), ("Names", "pal", "x")])
    assert "install anyway with --force" in str(e) and "Colour palettes: pal: bad slot" in str(e) and "Save edits: boom" in str(e)
    page = e.describe("press Apply the rest anyway", "what they put in the game before is removed")
    assert "--force" not in page and "Apply the rest anyway" in page
    assert e.mods() == ["pal"]
    # pipeline.install raises it from a build with a section that didn't go right.
    build = tmp_path / "build"
    build.mkdir()
    manifest = {"sections": {"palettes": {"title": "Colour palettes", "status": "partial", "mods": [], "errors": ["pal: bad slot"],
                                          "failed": [["pal", "bad slot"]]}}, "outputs": [], "ue4ss_mods": [], "save_ops": []}
    (build / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(pipeline, "game_running", lambda: False)
    cfg = Config(str(tmp_path), str(tmp_path))
    with pytest.raises(pipeline.InstallBlocked) as got:
        pipeline.install(cfg, str(build), str(tmp_path / "backups"), log=lambda m: None)
    assert got.value.problems == [("Colour palettes", "pal", "bad slot")]


# ---------- E: restart ----------
def test_restart_refuses_without_a_window_of_its_own_and_answers_its_shape_otherwise(studio, monkeypatch):
    with pytest.raises(RuntimeError, match="can't restart itself"):
        call(studio, "POST", "restart")
    assert call(studio, "GET", "info")["restartable"] is False
    studio.server, studio.port, studio.dry_restart = object(), 8792, True   # a server, but never really restarted here
    assert call(studio, "GET", "info")["restartable"] is True
    assert call(studio, "POST", "restart") == {"restarting": True, "how": "python", "port": 8792}
    assert call(studio, "POST", "restart")["restarting"] is True   # asked twice: still one restart
    studio.port = studio_mod.DEFAULT_PORT
    assert call(studio, "POST", "restart")["how"] == "python"   # no launcher in its folder
    (Path(studio.root) / studio_mod.LAUNCHER).write_text("@echo off\n", encoding="utf-8")
    assert call(studio, "POST", "restart")["how"] == ("launcher" if os.name == "nt" else "python")


def test_the_restarted_studio_starts_from_a_path_with_spaces_and_an_ampersand(tmp_path):
    folder = tmp_path / "Mods & more" / "wc mods"
    folder.mkdir(parents=True)
    how, command = studio_mod.restart_command(str(folder), 8792)
    assert how == "python" and command[:3] == [sys.executable, "-I", "-c"] and command[4:] == [
        str(folder / "wcmods.py"), "studio", "--port", "8792"]   # a list: no shell between it and Python
    if os.name != "nt":
        return
    # The launcher, run by cmd /C (its window closes when it ends), its path quoted inside quotes cmd takes off.
    marker = tmp_path / "ran.txt"
    (folder / studio_mod.LAUNCHER).write_text(f'@echo off\r\n> "{marker}" echo "%~dp0"\r\n', encoding="utf-8")
    how, command = studio_mod.restart_command(str(folder), studio_mod.DEFAULT_PORT)
    assert how == "launcher" and command == f'cmd.exe /C ""{folder / studio_mod.LAUNCHER}""'
    r = subprocess.run(command, cwd=str(folder), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert r.returncode == 0, r.stdout + r.stderr
    assert marker.read_text().strip() == f'"{folder}{os.sep}"'


def test_a_restarted_studio_that_fails_keeps_its_window_open_with_the_message(tmp_path):
    def wrapped(code):
        script = tmp_path / f"exits{code}.py"
        script.write_text(f"print('the studio says hello')\nraise SystemExit({code})\n", encoding="utf-8")
        return subprocess.run([sys.executable, "-I", "-c", studio_mod.RESTART_WRAPPER, str(script)], input="\n",
                              capture_output=True, text=True, timeout=30)
    ok = wrapped(0)
    assert ok.returncode == 0 and "the studio says hello" in ok.stdout and "Press Enter" not in ok.stdout
    bad = wrapped(3)
    assert bad.returncode == 3 and "Something went wrong; the message above says what." in bad.stdout
    assert "Press Enter to close this window." in bad.stdout


def test_settings_are_saved_while_something_reads_the_file(tmp_path):
    """On Windows a file another program has open can't be replaced: wcmods.json is tried again a moment later,
    then written in place, so an install's last save never fails because the studio was looking at it."""
    cfg = Config(str(tmp_path), str(tmp_path))
    cfg.data["game_dir"] = "first"
    cfg.save()
    with open(tmp_path / "wcmods.json", encoding="utf-8") as reader:   # the studio peeking at it, say
        cfg.data["game_dir"] = "second"
        cfg.save()
        assert json.loads((tmp_path / "wcmods.json").read_text(encoding="utf-8"))["game_dir"] == "second"
        assert reader.read()   # the reader is undisturbed
    assert not any(n.endswith(".part") for n in os.listdir(tmp_path))
    assert cfg.peek()["game_dir"] == "second"


def test_the_code_changed_message_points_at_the_restart_button(studio):
    game = studio.data / "Game"
    (game / "Wrc" / "Binaries" / "Win64").mkdir(parents=True)
    (game / "Wrc" / "Binaries" / "Win64" / config_mod.EXE_NAME).write_bytes(b"")
    studio.ctx.cfg.data["game_dir"] = str(game)
    studio.code_stamp = 0
    with pytest.raises(RuntimeError, match="Restart the studio"):
        call(studio, "POST", "play")
    for word in ("stdout", "traceback", "wcmods was updated"):
        assert word not in str(pytest.raises(RuntimeError, call, studio, "POST", "install").value)


# ---------- F: a damaged wcmods.json ----------
def test_a_damaged_settings_file_is_set_aside_and_said(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(config_mod, "_find_game_dir", lambda: None)
    (tmp_path / "wcmods.json").write_text("{broken", encoding="utf-8")
    cfg = Config(str(tmp_path), str(tmp_path))
    assert cfg.data == {} and cfg.warning.startswith("Your settings file was damaged; it was set aside as wcmods.json.broken-")
    aside = [n for n in os.listdir(tmp_path) if n.startswith("wcmods.json.broken-")]
    assert len(aside) == 1 and not (tmp_path / "wcmods.json").exists()
    assert (tmp_path / aside[0]).read_text(encoding="utf-8") == "{broken"
    # Saving starts afresh, whole and in place; reading it back is fine and the warning stays until it's been shown.
    cfg.data["game_dir"] = "x"
    cfg.save()
    assert not any(n.endswith(".part") for n in os.listdir(tmp_path))
    assert cfg.peek()["game_dir"] == "x"
    cfg.reload()
    assert cfg.data["game_dir"] == "x" and cfg.warning
    # A settings file that isn't an object counts as damaged too; a good one gives no warning.
    (tmp_path / "list").mkdir()
    (tmp_path / "list" / "wcmods.json").write_text("[]", encoding="utf-8")
    assert Config(str(tmp_path), str(tmp_path / "list")).warning
    (tmp_path / "good").mkdir()
    (tmp_path / "good" / "wcmods.json").write_text("{}", encoding="utf-8")
    assert Config(str(tmp_path), str(tmp_path / "good")).warning is None
    # The studio shows it as a chip; the command line prints it (though the Config that set the file aside was
    # userdata.prepare's, made before the command's own).
    from wcmods.cli import main
    (tmp_path / "wcmods.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setenv(config_mod.DATA_ENV, str(tmp_path))
    (tmp_path / "root").mkdir()   # wcmods' folder, as the command sees it: never the repository's (see `studio`)
    try:
        main(str(tmp_path / "root"), ["status"])
    except SystemExit:
        pass
    out = capsys.readouterr()
    assert "warning: Your settings file was damaged" in out.err and "game folder : NOT FOUND" in out.out


def test_pending_reads_the_settings_afresh_without_setting_them_aside(tmp_path):
    (tmp_path / "wcmods.json").write_text(json.dumps({"installed": {"mods": [], "built": "2026-10-27T12:00:00"}}), encoding="utf-8")
    cfg = Config(str(tmp_path), str(tmp_path))
    (tmp_path / "wcmods.json").write_text("{half writ", encoding="utf-8")   # being written this moment
    assert pipeline.pending(cfg, [])["installed"] is True   # falls back to what's loaded
    assert (tmp_path / "wcmods.json").read_text(encoding="utf-8") == "{half writ"   # and leaves the file be


# ---------- H: the guide ----------
SAMPLE = """# A title

Some *words* with **weight**, `code <b>` and a [page](studio.md#the-log), a [doc](../formats.md),
a [site](https://example.org/?a=1&b=2) and a [bad](javascript:alert) one.

## Lists
- one
- two
  goes on
1. first
2. second

```
raw <code>
```
> a quote
---
![a picture](images/p.png) ![not ours](http://x/y.png)
"""


def test_the_guide_renders_its_markdown_and_nothing_else():
    html = guide.render(SAMPLE)
    assert '<h1 id="a-title">A title</h1>' in html and '<h2 id="lists">Lists</h2>' in html
    assert "<em>words</em>" in html and "<strong>weight</strong>" in html and "<code>code &lt;b&gt;</code>" in html
    assert '<a href="/help/studio#the-log">page</a>' in html
    assert 'href="https://github.com/HexOffender/warrior-cats-mods/blob/main/docs/formats.md" target="_blank"' in html
    assert 'href="https://example.org/?a=1&amp;b=2" target="_blank" rel="noopener">site</a>' in html
    assert "javascript:" not in html and ">bad<" not in html and "bad one" in html
    assert "<ul><li>one</li><li>two goes on</li></ul>" in html and "<ol><li>first</li><li>second</li></ol>" in html
    assert "<pre><code>raw &lt;code&gt;</code></pre>" in html and "<blockquote><p>a quote</p></blockquote>" in html
    assert "<hr>" in html and '<img src="/help/images/p.png" alt="a picture">' in html and "x/y.png" not in html
    assert guide.title(SAMPLE) == "A title"
    import re
    tags = set(re.findall(r"<([a-z0-9]+)", html))
    assert tags <= set(guide.TAGS)


def test_the_guides_pages_are_served_to_the_panel(studio):
    studio.root = ROOT   # the repository's docs/guide, only read
    assert guide.pages(ROOT)[0] == "README" and "studio" in guide.pages(ROOT)
    r = call(studio, "GET", "help/studio")
    assert r["title"] == "How Clan Mod Studio works" and "<h2" in r["html"] and r["pages"] == guide.pages(ROOT)
    assert call(studio, "GET", "help/index")["page"] == "README"
    for bad in ("../README", "nope", "studio.md"):
        with pytest.raises(LookupError):
            call(studio, "GET", f"help/{bad}")


# ---------- D and the rest, through the server ----------
@pytest.fixture
def served(studio):
    server = studio_mod._Server(("127.0.0.1", 0), None)
    port = server.server_address[1]
    server.RequestHandlerClass = studio_mod.make_handler(studio, port)
    studio.server, studio.port, studio.dry_restart = server, port, True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield studio, port
    finally:
        server.shutdown()
        server.server_close()


def ask(studio, port, path, method="GET", body=None, token=True, raw=False):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-WC-Token"] = studio.token
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
            return r.status, (data.decode("utf-8") if raw else json.loads(data))
    except urllib.error.HTTPError as e:
        data = e.read()
        return e.code, (data.decode("utf-8") if raw else json.loads(data))


def test_the_page_and_the_guide_are_served_with_the_token_in_place(served):
    studio, port = served
    studio.root = ROOT   # the repository's docs/guide, only read
    for path in ("/", "/index.html", "/studio/index.html"):
        code, html = ask(studio, port, path, raw=True)
        assert code == 200 and studio.token in html and "{{WC_TOKEN}}" not in html
    code, html = ask(studio, port, "/help/studio", raw=True)
    assert code == 200 and "<!doctype html>" in html and "/studio/styles.css" in html and "How Clan Mod Studio works" in html
    assert ask(studio, port, "/help/", raw=True)[1].count("<h1") == 1
    assert ask(studio, port, "/help/nope")[0] == 404
    assert ask(studio, port, "/help/images/nope.png")[0] == 404
    assert ask(studio, port, "/help/../wcmods/studio.py")[0] in (404, 400)


def test_errors_reach_the_page_as_sentences_and_the_details_go_to_the_log(served, monkeypatch):
    studio, port = served
    make_mod(studio, "mine")
    code, a = ask(studio, port, "/api/mods/mine/file/names.json", "PUT", {"text": "{bad"})
    assert code == 400 and a["error"].startswith("names.json isn't valid: ")
    code, a = ask(studio, port, "/api/mods/mine/file/names.json", "PUT", {})
    assert code == 400 and a["error"] == 'the request needs "text"'
    code, a = ask(studio, port, "/api/mods/nope/file/names.json")
    assert code == 404 and a["error"] == "no mod named nope"
    code, a = ask(studio, port, "/api/info", token=False)
    assert code == 403 and "studio token" in a["error"]
    assert studio_mod.other_studio(port) is True
    # Something unexpected: a sentence, with the traceback in studio.log and on the console.
    real = studio.api

    def broken(method, parts, body, query=None, upload=None):
        if parts == ["info"]:
            raise TypeError("boom")
        if parts == ["changes"]:
            raise FileNotFoundError(2, "No such file", os.path.join(GAME, "Wrc", "Content", "Paks", "pakchunk0-Windows.pak"))
        if parts == ["setup"]:
            raise PermissionError(13, "Permission denied", os.path.join(GAME, "zzz_WCMods_P.ucas"))
        if parts == ["backups"]:
            raise json.JSONDecodeError("Expecting value", "{", 1)
        if parts == ["mods", "removed"]:   # json.load of a file: the file is named
            path = studio.data / "removed.json"
            path.write_text("{oops", encoding="utf-8")
            with open(path, encoding="utf-8") as fp:
                json.load(fp)
        if parts == ["last-apply"]:   # with words of its own
            raise FileNotFoundError("no backup named 2026-10-27-1200-studio")
        if parts == ["ingame"]:   # with none at all
            raise RuntimeError() from KeyError()
        if parts == ["cpp"]:
            raise OSError()
        return real(method, parts, body, query, upload)
    monkeypatch.setattr(studio, "api", broken)
    code, a = ask(studio, port, "/api/info")
    assert code == 500 and a["error"] == "Something went wrong: boom, with the details in studio.log"
    log = (studio.data / studio_mod.STUDIO_LOG).read_text(encoding="utf-8")
    assert "GET /api/info" in log and "TypeError: boom" in log
    code, a = ask(studio, port, "/api/changes")
    assert code == 400 and a["error"] == "A file the studio needs is missing: pakchunk0-Windows.pak (is Steam updating the game?)"
    code, a = ask(studio, port, "/api/setup")
    assert code == 400 and a["error"] == "zzz_WCMods_P.ucas is in use (is the game running?)"
    code, a = ask(studio, port, "/api/backups")
    assert code == 400 and a["error"] == "A file the studio reads isn't valid: Expecting value at line 1"
    code, a = ask(studio, port, "/api/mods/removed")
    assert code == 400 and a["error"].startswith("removed.json isn't valid: Expecting property name")
    code, a = ask(studio, port, "/api/last-apply")
    assert code == 400 and a["error"] == "no backup named 2026-10-27-1200-studio"
    code, a = ask(studio, port, "/api/cpp")
    assert code == 500 and a["error"] == "Something went wrong, with the details in studio.log"
    code, a = ask(studio, port, "/api/ingame")
    assert code == 400 and a["error"] == "Something went wrong, with the details in studio.log"
    for word in ("Error", "Traceback", "Game"):
        assert word not in json.dumps([a])


def test_a_blocked_install_answers_with_the_facts_for_apply_the_rest_anyway(served, monkeypatch):
    studio, port = served
    monkeypatch.setattr(studio, "api", lambda *a, **k: (_ for _ in ()).throw(
        pipeline.InstallBlocked([("Colour palettes", "pal", "bad slot")])))
    code, a = ask(studio, port, "/api/install", "POST", {})
    assert code == 409 and a["blocked"] == [{"title": "Colour palettes", "mod": "pal", "text": "bad slot"}] and a["mods"] == ["pal"]
    assert "press Apply the rest anyway" in a["error"] and "--force" not in a["error"]


def test_the_restart_route_through_the_server(served):
    studio, port = served
    code, a = ask(studio, port, "/api/restart", "POST", {})
    assert code == 200 and a == {"restarting": True, "how": "python", "port": port}
    assert ask(studio, port, "/api/info")[0] == 200   # dry: still here


def test_a_port_held_by_another_program_moves_the_studio_along(served, monkeypatch):
    studio, port = served
    monkeypatch.setattr(studio_mod, "PROBE_TIMEOUT", 0.5)   # the held port never answers: don't wait long for it
    held = socket.socket()
    held.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", socket.SO_REUSEADDR), 1)
    held.bind(("127.0.0.1", 0))
    held.listen(1)
    busy = held.getsockname()[1]
    try:
        assert studio_mod.other_studio(busy) is False
        server, tried, other = studio_mod.find_port(busy)
        assert server is not None and tried == [busy] and other is None and server.server_address[1] != busy
        server.server_close()
    finally:
        held.close()
    # The port of a studio already open is told apart, and not moved past.
    server, tried, other = studio_mod.find_port(port)
    assert server is None and tried == [port] and other == port
