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


# ---------- what the check's build has to say before a mod passes ----------
def palette(studio, mod_id, meta=None):
    make_mod(studio, mod_id, {"game_builds": [OLD], **(meta or {})}, {"palette.json": {"fur": {"3": "#112233"}}})


def test_a_section_that_fails_as_a_whole_fails_its_mods(studio, updated, readable, monkeypatch):
    from wcmods.sections.palettes import PaletteSection
    palette(studio, "dark-forest")

    def broken(self, ctx, items):
        raise RuntimeError("the eye atlas moved")
    monkeypatch.setattr(PaletteSection, "build", broken)
    results = gamebuild.recheck(studio.ctx.cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None)
    assert results == {"dark-forest": "the eye atlas moved"} and builds_of(studio, "dark-forest") == [OLD]
    # The game's files going unreadable midway is no verdict: tried again.
    palette(studio, "pastel")

    def unreadable(self, ctx, items):
        raise gamefiles.Unreadable("the game's files can't be read: there's no pakchunk0 (is Steam updating?)")
    monkeypatch.setattr(PaletteSection, "build", unreadable)
    results = gamebuild.recheck(studio.ctx.cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None)
    assert results["pastel"] == gamebuild.COULDNT_READ and builds_of(studio, "pastel") == [OLD]
    assert gamebuild.recheck_due(studio.ctx.cfg, discover(studio.ctx.mods_root))


def test_a_mod_needing_a_held_back_mod_or_a_newer_studio_is_never_stamped(studio, updated, readable):
    make_mod(studio, "sandbox", {"name": "Sandbox mode", "game_builds": [OLD]}, {"scripts/main.lua": "-- sandbox"})
    make_mod(studio, "story", {"name": "Moonlit story", "game_builds": [OLD], "requires": ["sandbox"]},
             {"npcs.json": {"npcs": []}})
    palette(studio, "future", {"wcmods": "9.0"})
    palette(studio, "needs-ghost", {"requires": ["ghost"]})
    cfg = studio.ctx.cfg
    found = discover(studio.ctx.mods_root)
    assert gamebuild.candidates(cfg, found) == [] and not gamebuild.recheck_due(cfg, found)
    assert gamebuild.recheck(cfg, found, studio.ctx.build_dir, lambda m: None) == {}
    assert builds_of(studio, "story") == builds_of(studio, "future") == builds_of(studio, "needs-ghost") == [OLD]
    # Even if one slips into a check and the build leaves it out, it gets no answer and no stamp.
    manifest = {"mods": ["a"], "left_out": {"a": "needs Sandbox mode"}, "sections": {}}
    assert gamebuild._verdict("a", {**manifest, "left_out": {}}) == "ok"


def test_only_the_mods_whose_edits_failed_are_held_back(studio, updated, readable, monkeypatch):
    from wcmods.gamefiles import GameFiles
    make_mod(studio, "bad-table", {"game_builds": [OLD]}, {"data.json": {"Gone.csv": {"row": {"Value": 2}}}})
    make_mod(studio, "good-table", {"game_builds": [OLD]}, {"data.json": {"Kept.csv": {"row": {"Value": 3}}}})
    monkeypatch.setattr(GameFiles, "exists", lambda self, path: True)

    def read_text(self, path):
        if path.endswith("Gone.csv"):
            raise ValueError("the update removed Gone.csv")
        return "Name,Value\nrow,1\n"
    monkeypatch.setattr(GameFiles, "read_text", read_text)
    results = gamebuild.recheck(studio.ctx.cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None)
    assert results["good-table"] == "ok" and "Gone.csv: edits not applied" in results["bad-table"]
    assert builds_of(studio, "good-table") == [OLD, NEW] and builds_of(studio, "bad-table") == [OLD]


def test_a_failed_mod_is_checked_again_once_it_changes_and_can_be_used_anyway(studio, updated, readable):
    make_mod(studio, "old-tweaks", {"name": "Old tweaks", "game_builds": [OLD]}, {"palette.json": {"fur": {"3": "not a colour"}}})
    cfg = studio.ctx.cfg
    assert gamebuild.recheck(cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None)["old-tweaks"] != "ok"
    assert not gamebuild.recheck_due(cfg, discover(studio.ctx.mods_root))
    # Its maker fixes it: due again, and it passes.
    with open(os.path.join(studio.ctx.mods_root, "old-tweaks", "palette.json"), "w", encoding="utf-8") as f:
        json.dump({"fur": {"3": "#123456"}}, f)
    assert gamebuild.recheck_due(cfg, discover(studio.ctx.mods_root))
    assert gamebuild.recheck(cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None) == {"old-tweaks": "ok"}
    assert builds_of(studio, "old-tweaks") == [OLD, NEW]


def test_the_check_builds_only_the_candidates_and_what_they_need(studio, updated, readable, monkeypatch):
    built = []
    real = pipeline.build
    monkeypatch.setattr(pipeline, "build", lambda cfg, mods, *a, **k: built.append(sorted(m.id for m in mods)) or real(cfg, mods, *a, **k))
    palette(studio, "dark-forest", {"requires": ["helper"]})
    make_mod(studio, "helper", {"name": "Helper"}, {"names.json": {}})
    make_mod(studio, "other-script", {"name": "Other"}, {"section.py": "raise SystemExit('ran')"})
    gamebuild.recheck(studio.ctx.cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, lambda m: None)
    assert built == [["dark-forest", "helper"]]


def test_one_mod_json_that_cant_be_written_doesnt_stop_the_others(studio, updated, readable, monkeypatch):
    palette(studio, "a")
    palette(studio, "b")
    real = gamebuild._stamp

    def stamp(mod, build):
        if mod.id == "a":
            raise PermissionError("mod.json is in use")
        real(mod, build)
    monkeypatch.setattr(gamebuild, "_stamp", stamp)
    said = []
    results = gamebuild.recheck(studio.ctx.cfg, discover(studio.ctx.mods_root), studio.ctx.build_dir, said.append)
    assert results == {"b": "ok"} and builds_of(studio, "b") == [OLD, NEW] and builds_of(studio, "a") == [OLD]
    assert any(s.startswith("A: built") and "couldn't be noted" in s for s in said)
    assert gamebuild.recheck_due(studio.ctx.cfg, discover(studio.ctx.mods_root))   # a: tried again
    assert not [f for f in os.listdir(os.path.join(studio.ctx.mods_root, "b")) if f.endswith(".part")]


def test_the_verdict_reads_skipped_save_edits_and_blame():
    def manifest(sections, warnings=()):
        return {"mods": ["a", "b"], "left_out": {}, "sections": sections, "warnings": list(warnings)}
    section = {"title": "Game data", "status": "partial", "mods": ["a", "b"],
               "failed": [(None, "X.csv: edits not applied (gone)")], "blame": {"X.csv: edits not applied (gone)": ["a"]}}
    m = manifest({"data": section})
    assert gamebuild._verdict("a", m) == "X.csv: edits not applied (gone)" and gamebuild._verdict("b", m) == "ok"
    unknown = {**section, "blame": {"X.csv: edits not applied (gone)": []}}
    assert gamebuild._verdict("b", manifest({"data": unknown})) == "couldn't check: X.csv: edits not applied (gone)"
    whole = {"title": "Palettes", "status": "failed", "mods": ["a"], "failed": [(None, "the eye atlas moved")]}
    assert gamebuild._verdict("a", manifest({"palettes": whole})) == "the eye atlas moved"
    skipped = manifest({}, ["a: your save has no value at Player.Stats.Old; skipped", "b: fine but noisy"])
    assert gamebuild._verdict("a", skipped) == "your save has no value at Player.Stats.Old; skipped"
    assert gamebuild._verdict("b", skipped) == "ok"


def test_the_checks_warnings_show_on_the_card(studio, updated):
    palette(studio, "dark-forest")
    cfg = studio.ctx.cfg
    cfg.data["rechecked"] = {"build": NEW, "when": "2026-10-28T10:00:00", "results": {"dark-forest": "boom"},
                             "signatures": {}, "warnings": {"dark-forest": ["dark-forest: colour 3 is close to black"]}}
    cfg.save()
    (card,) = call(studio, "GET", "mods")
    assert card["warnings"] == ["dark-forest: colour 3 is close to black"]
