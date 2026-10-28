"""How wcmods stands on a game build it wasn't checked on (wcmods/exe/gamebuild.py), without the game:
- what a game update switched off, in a player's words: the Apply warning, `wcmods game build` and the
  Mods page's banner name values by what they are, not by the game's C++ classes;
- layout(): a verified build needs no check; another build's check is worked out once and cached, a
  cache cut short is worked out again, and a check that fails leaves every value off (and is tried
  again next time) instead of stopping the build."""
import json
import os
from types import SimpleNamespace

import pytest

from wcmods import game
from wcmods.exe import gamebuild, signatures

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEVEL = "/Script/SwtAdventure.SwtAdventureLevelComponent"
STATE = "/Script/SwtAdventure.SwtAdventureGameplayGameState"


def test_describe_says_it_in_plain_words():
    lost = [f"{LEVEL}:WCM_Level", f"{LEVEL}:WCM_LevelShown", f"{LEVEL}:WCM_Prowess", f"{LEVEL}:WCM_Stamina"]
    assert gamebuild.describe(lost) == "your cat's level and stats"
    assert gamebuild.describe(lost + [f"{STATE}:WCM_DayTime"]) == "your cat's level and stats; the time of day"
    assert gamebuild.describe(f"{STATE}:WCM_DayTime") == "the time of day"
    assert gamebuild.phrases(lost + [f"{STATE}:WCM_DayTime"] + lost) == ["your cat's level and stats",
                                                                          "the time of day"]
    assert gamebuild.describe([]) == ""


def test_every_value_wcmods_reads_has_plain_words():
    words = gamebuild.phrases(f"{cls}:{name}" for cls, fields in game.HIDDEN for name, _, _ in fields)
    assert len(words) == len(game.HIDDEN)
    assert not [w for w in words if "Component" in w or "GameState" in w or "WCM_" in w]


def test_a_class_without_words_is_named_as_it_is():
    assert gamebuild.describe("/Script/Wrc.WrcSomethingNew:WCM_Value") == "WrcSomethingNew.Value"
    assert gamebuild.name(f"{LEVEL}:WCM_Level") == "SwtAdventureLevelComponent.Level"


def test_the_mods_page_keeps_the_phrases_apart():
    """GET /api/game/update gives one phrase per class (phrases()), some with commas of their own ("your
    cat's health, stamina and experience, and the fresh-kill pile"): the Mods page's banner separates them
    with semicolons, as describe() does."""
    with open(os.path.join(ROOT, "studio", "sections", "mods.js"), encoding="utf-8") as f:
        js = f.read()
    assert 'update.moved.join("; ")' in js and 'update.lost.join("; ")' in js
    assert "," in gamebuild.PLAIN["SwtQuestResourceComponent"]


# ---------- layout() ----------
def members():
    return [f"{cls}:{name}" for cls, fields in game.HIDDEN for name, _, _ in fields]


def quiet(message):
    pass


@pytest.fixture
def updated(monkeypatch, tmp_path):
    """The game updated to a build wcmods wasn't checked on, its exe a file in tmp_path, and a check() that
    counts its calls and finds the level component moved 4 bytes on, everything else where it was."""
    exe = tmp_path / "game.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setenv("WCMODS_GAME_BUILD", "99999998")
    monkeypatch.setattr(gamebuild.pe, "game_exe", lambda cfg: str(exe))
    calls = []

    def check(path, sigs=None, log=print):
        calls.append(path)
        classes, offsets = {}, {}
        for cls, fields in game.HIDDEN:
            classes[cls] = {"fields": {}}
            for name, offset, _ in fields:
                moved = cls == LEVEL
                classes[cls]["fields"][name] = {"status": "moved" if moved else "same"}
                offsets[f"{cls}:{name}"] = offset + 4 if moved else offset
        return {"classes": classes, "offsets": offsets, "same": False}

    monkeypatch.setattr(signatures, "check", check)
    return SimpleNamespace(cfg=SimpleNamespace(root=str(tmp_path), game_dir=None), calls=calls)


def cache_of(cfg):
    return gamebuild._cache_path(cfg, gamebuild.layout_key(cfg))


def test_a_verified_build_needs_no_check(updated, monkeypatch):
    monkeypatch.setenv("WCMODS_GAME_BUILD", str(gamebuild.VERIFIED_BUILD))
    assert gamebuild.layout(updated.cfg, log=quiet) == {
        "build": gamebuild.VERIFIED_BUILD, "status": "verified", "offsets": None, "moved": [], "lost": []}
    assert updated.calls == []
    assert not os.path.exists(os.path.join(updated.cfg.root, gamebuild.CACHE_DIR))


def test_layout_caches_a_check(updated):
    fit = gamebuild.layout(updated.cfg, log=quiet)
    assert fit["status"] == "adapted" and fit["lost"] == []
    assert fit["moved"] == [k for k in members() if k.startswith(LEVEL + ":")]
    assert fit["offsets"][f"{LEVEL}:WCM_Level"] == 0x124
    assert gamebuild.layout(updated.cfg, log=quiet) == fit   # read back, not worked out again
    assert len(updated.calls) == 1
    with open(cache_of(updated.cfg), encoding="utf-8") as f:
        assert json.load(f) == fit
    assert not os.path.exists(cache_of(updated.cfg) + ".part")
    gamebuild.layout(updated.cfg, log=quiet, refresh=True)
    assert len(updated.calls) == 2


def test_a_half_written_cache_is_ignored(updated):
    path = cache_of(updated.cfg)
    os.makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"build": 99999998, "offs')   # cut short while it was written
    fit = gamebuild.layout(updated.cfg, log=quiet)
    assert fit["status"] == "adapted" and len(updated.calls) == 1
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == fit


def test_a_failing_check_leaves_everything_off(updated, monkeypatch):
    def broken(*a, **k):
        raise ValueError("an exe unlike any wcmods knows")
    monkeypatch.setattr(signatures, "check", broken)
    fit = gamebuild.layout(updated.cfg, log=quiet)
    assert fit["status"] == "partial" and fit["moved"] == [] and fit["lost"] == members()
    assert set(fit["offsets"]) == set(members()) and set(fit["offsets"].values()) == {None}
    assert "an exe unlike any wcmods knows" in fit["why"]
    assert not os.path.exists(cache_of(updated.cfg))   # nothing kept: it's tried again next time
