"""After a game update (wcmods/exe/gamebuild.py): the builds a mod.json lists, and the re-check that builds
the held-back data mods on the new game instead of holding them back on trust. The game is the made-up one
(fake_game), on a build set by WCMODS_GAME_BUILD; whether its files can be read is stood in for where a test
needs them readable."""
import json
import os

import pytest

from wcmods import gamefiles, pipeline
from wcmods.exe import gamebuild
from wcmods.mods import Mod, discover

from unit_helpers import make_mod

NEW = 99999999   # the build the game "updated" to
OLD = gamebuild.VERIFIED_BUILD


def call(st, method, path, body=None, query=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, query, None)


@pytest.fixture
def updated(monkeypatch, fake_game):
    """The made-up game on a newer build than every mod here was made for."""
    monkeypatch.setenv("WCMODS_GAME_BUILD", str(NEW))
    return fake_game


@pytest.fixture
def readable(monkeypatch):
    """The game's files count as readable (the made-up game has none): what the build reads of them is its own
    business, and the palette mods here read nothing."""
    monkeypatch.setattr(gamefiles, "unreadable", lambda cfg: None)


def builds_of(studio, mod_id):
    with open(os.path.join(studio.ctx.mods_root, mod_id, "mod.json"), encoding="utf-8") as f:
        return json.load(f).get("game_builds")


def test_builds_accepts_strings_and_whole_floats_and_warns_on_an_empty_list(tmp_path):
    def mod(meta):
        folder = tmp_path / str(len(os.listdir(tmp_path)))
        folder.mkdir()
        (folder / "mod.json").write_text(json.dumps({"name": "M", **meta}), encoding="utf-8")
        return Mod(str(folder))
    assert gamebuild.made_for(mod({"game_builds": ["26184573", 24847281.0, 26184574]})) == [26184573, 24847281, 26184574]
    assert gamebuild.made_for(mod({"game_builds": "26184573"})) == [26184573]
    assert gamebuild.made_for(mod({"game_build": 26184573})) == [26184573]
    for empty in ([], ["soon"], [1.5], True, None, "x"):
        m = mod({"game_builds": empty})
        assert gamebuild.made_for(m) == list(gamebuild.ASSUMED_BUILDS)
        assert gamebuild.builds_problem(m) == "mod.json's game_builds should be a list of build numbers like [26184573]"
    assert gamebuild.builds_problem(mod({})) is None and gamebuild.builds_problem(mod({"game_builds": [1]})) is None


def test_a_bad_game_builds_is_a_warning_on_the_card(studio):
    make_mod(studio, "typo", {"game_builds": ["soon"]})
    (card,) = call(studio, "GET", "mods")
    assert card["warnings"] == [gamebuild.BUILDS_PROBLEM] and card["problems"] == []


def test_a_data_mod_that_still_builds_is_stamped_with_the_new_build(studio, updated, readable):
    make_mod(studio, "dark-forest", {"name": "Dark Forest", "game_builds": [OLD]}, {"palette.json": {"fur": {"3": "#112233"}}})
    cfg = studio.ctx.cfg
    found = discover(studio.ctx.mods_root)
    assert gamebuild.held_back(cfg, found) == {"dark-forest": "made for an older version of the game"}
    assert gamebuild.candidates(cfg, found) == ["dark-forest"] and gamebuild.recheck_due(cfg, found)
    said = []
    results = gamebuild.recheck(cfg, found, studio.ctx.build_dir, said.append)
    assert results == {"dark-forest": "ok"} and builds_of(studio, "dark-forest") == [OLD, NEW]
    assert "Dark Forest: checked on build 99999999: fine" in said
    assert not os.path.exists(studio.ctx.build_dir + "-check")
    found = discover(studio.ctx.mods_root)
    assert gamebuild.held_back(cfg, found) == {} and not gamebuild.recheck_due(cfg, found)
    with open(cfg.path, encoding="utf-8") as f:
        rec = json.load(f)["rechecked"]
    assert rec["build"] == NEW and rec["results"] == {"dark-forest": "ok"} and rec["when"]
    card = call(studio, "GET", "mods")[0]
    assert card["rechecked"] == "ok" and card["rechecked_since_apply"] is True and card["outdated"] is None


def test_a_data_mod_whose_file_fails_stays_held_back_with_the_reason(studio, updated, readable):
    make_mod(studio, "old-tweaks", {"name": "Old tweaks", "game_builds": [OLD]}, {"palette.json": {"fur": {"3": "not a colour"}}})
    cfg = studio.ctx.cfg
    results = gamebuild.recheck(cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None)
    why = results["old-tweaks"]
    assert why != "ok" and "not a colour" in why
    assert builds_of(studio, "old-tweaks") == [OLD]   # not stamped
    held = gamebuild.held_back(cfg, discover(studio.ctx.mods_root))
    assert held == {"old-tweaks": f"made for an older version of the game, and checked on this one: {why}"}
    assert not gamebuild.recheck_due(cfg, discover(studio.ctx.mods_root))   # once per build


def test_a_code_mod_and_a_paks_mod_are_never_checked(studio, updated, readable):
    make_mod(studio, "script", {"game_builds": [OLD]}, {"scripts/main.lua": "print(1)"})
    make_mod(studio, "cooked", {"game_builds": [OLD]}, {"paks/thing.pak": b"x"})
    make_mod(studio, "replaced", {"game_builds": [OLD]}, {"files/Wrc/Config/x.ini": "a"})
    make_mod(studio, "pack", {"pack": True, "requires": ["script"]})
    found = discover(studio.ctx.mods_root)
    assert set(gamebuild.held_back(studio.ctx.cfg, found)) == {"script", "cooked", "replaced", "pack"}   # the pack needs one
    assert gamebuild.candidates(studio.ctx.cfg, found) == [] and not gamebuild.recheck_due(studio.ctx.cfg, found)
    assert gamebuild.recheck(studio.ctx.cfg, found, studio.ctx.build_dir, lambda m: None) == {}
    assert builds_of(studio, "script") == [OLD]


def test_no_readable_game_means_couldnt_check_and_a_retry_next_time(studio, updated, monkeypatch):
    make_mod(studio, "dark-forest", {"game_builds": [OLD]}, {"palette.json": {"fur": {"3": "#112233"}}})
    cfg = studio.ctx.cfg
    said = []
    results = gamebuild.recheck(cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, said.append)
    assert results == {"dark-forest": gamebuild.COULDNT_READ} and builds_of(studio, "dark-forest") == [OLD]
    assert any("the game's files can't be read" in s for s in said)
    found = discover(studio.ctx.mods_root)
    assert gamebuild.held_back(cfg, found) == {"dark-forest": "made for an older version of the game"}
    assert gamebuild.recheck_due(cfg, found)   # tried again next time
    monkeypatch.setattr(gamefiles, "unreadable", lambda cfg: None)
    assert gamebuild.recheck(cfg, found, studio.ctx.build_dir, lambda m: None) == {"dark-forest": "ok"}


def test_recheck_runs_once_per_build_and_again_for_a_new_candidate(studio, updated, readable, monkeypatch):
    builds = []
    real = pipeline.build
    monkeypatch.setattr(pipeline, "build", lambda *a, **k: builds.append(sorted(k.get("trusted", ()))) or real(*a, **k))
    make_mod(studio, "a", {"game_builds": [OLD]}, {"palette.json": {"fur": {"3": "#112233"}}})
    cfg = studio.ctx.cfg
    gamebuild.recheck(cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None)
    gamebuild.recheck(cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None)
    assert builds == [["a"]]
    make_mod(studio, "b", {"game_builds": [OLD]}, {"palette.json": {"fur": {"4": "#445566"}}})
    assert gamebuild.recheck(cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None) == {"a": "ok", "b": "ok"}
    assert builds == [["a"], ["b"]]
    # A newer build still: every mod's checked again (a and b list the last one, so only a new mod would be).
    monkeypatch.setenv("WCMODS_GAME_BUILD", str(NEW + 1))
    assert gamebuild.recheck_due(cfg, discover(studio.ctx.mods_root))
    gamebuild.recheck(cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None)
    assert builds[-1] == ["a", "b"] and builds_of(studio, "a") == [OLD, NEW, NEW + 1]


def test_get_mods_never_builds(studio, updated, monkeypatch):
    make_mod(studio, "dark-forest", {"game_builds": [OLD]}, {"palette.json": {"fur": {"3": "#112233"}}})

    def no(*a, **k):
        raise AssertionError("built")
    real = pipeline.build
    monkeypatch.setattr(pipeline, "build", no)
    assert call(studio, "GET", "mods")[0]["outdated"]["allowed"] is False
    assert call(studio, "GET", "changes")["recheck_due"] is True
    monkeypatch.setattr(pipeline, "build", real)
    r = call(studio, "POST", "mods/recheck")   # the page's way to start it, through the studio's progress
    assert r["result"] == {"dark-forest": gamebuild.COULDNT_READ} and any("couldn't check" in line for line in r["log"])
