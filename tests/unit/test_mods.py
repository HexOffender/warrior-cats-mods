"""Mods and setup without the game: downloaded .zips and what's refused, the key remapper's presses, menu
remaps, the agent controller's parts, getting set up in temporary folders, and what mods need ("requires")
and only use ("uses")."""
import json
import sys

import pytest

from wcmods import mods as modlib, selftest


def test_adding_a_downloaded_mod_from_a_zip_and_refusing_unsafe_ones():
    assert selftest._mod_zips()


def test_a_zip_cant_hide_code_and_needing_the_mod_menu_needs_nothing_more():
    assert selftest._mod_zip_guards()


def test_menu_pages_mod_added_and_updated_keeping_your_settings():
    ok, detail = selftest._menu_pages()
    assert ok, detail


def test_key_remapper_presses():
    assert selftest._remapper_presses()


def test_menu_remaps():
    assert selftest._menu_remaps()


@pytest.mark.skipif(sys.platform != "win32", reason="the agent's runner drives the game's window through user32")
def test_agent_controller_parts():
    assert selftest._agent_parts()


@pytest.mark.skipif(sys.platform != "win32", reason="the agent's controller loads user32 as it's imported")
def test_agent_install_builds_the_with_mods_whatever_game_they_name(studio, monkeypatch, tmp_path):
    """`agent install --with` a test's own mod, whose mod.json names no version of the game (as tests/game/mods'
    don't): it's built as chosen, not left out as made for an older version of the game."""
    from wcmods.agent import controller
    monkeypatch.setenv("WCMODS_DATA", studio.ctx.cfg.data_dir)
    mod = tmp_path / "extra-mod"
    mod.mkdir()
    (mod / "mod.json").write_text(json.dumps({"name": "Extra", "enabled": True}), encoding="utf-8")
    seen = {}

    def build(cfg, mods, out_dir, log=print, trusted=()):
        seen.update(mods=[m.id for m in mods], trusted=list(trusted))
        return {}

    monkeypatch.setattr(controller.window, "game_pid", lambda: None)
    monkeypatch.setattr(controller.pipeline, "build", build)
    monkeypatch.setattr(controller.pipeline, "install", lambda *a, **k: None)
    controller.Agent(studio.ctx.root).install(extra=[str(mod)])
    assert "extra-mod" in seen["mods"] and seen["trusted"] == ["extra-mod"], seen


def test_getting_set_up_finds_the_game_from_any_of_its_folders():
    assert selftest._onboarding()


def test_getting_set_up_rough_edges():
    assert selftest._onboarding_edges()


def test_steams_copy_of_the_game_told_apart_from_the_one_mods_go_into():
    assert selftest._steam_copy()


def test_your_files_move_out_of_wcmods_folder_and_the_old_mod_menus_settings_into_wcmods_json():
    ok, detail = selftest._user_data()
    assert ok, detail


def test_cpp_mod_dll_goes_in_with_its_settings_and_bad_dlls_are_refused():
    ok, detail = selftest._cpp_mod()
    assert ok, detail


def test_cpp_sdk_headers_documented_and_tested():
    ok, detail = selftest._cpp_sdk()
    assert ok, detail


# ---------- what mods need, and what they only use ----------
def _mods(tmp_path, specs):
    """Mod folders from {id: mod.json}, found as the studio finds them."""
    for mod_id, meta in specs.items():
        (tmp_path / mod_id).mkdir()
        (tmp_path / mod_id / "mod.json").write_text(json.dumps({"enabled": False, **meta}), encoding="utf-8")
    return modlib.discover(str(tmp_path))


def test_version_key_orders_versions():
    key = modlib.version_key
    assert key("0.5") == key("0.5.0") == key("v0.5")
    assert key("0.4") < key("0.5") < key("0.10") < key("1.0")
    assert key("0.5.1") > key("0.5")
    assert key("V1.2") == (1, 2, 0) and key(" 0.4 ") == (0, 4, 0)
    # Anything that isn't a plain dotted number is no version at all: callers leave it out before comparing.
    for junk in ("", None, "beta", "0.5-beta", "one.two", "v", "0..5", "1.2."):
        assert key(junk) is None, junk


def test_switching_on_turns_on_used_mods_that_are_there(tmp_path):
    _mods(tmp_path, {"story": {"uses": ["sandbox", "mod-menu", "not-here", "broken"], "requires": ["herbs"]},
                     "herbs": {"uses": ["palette"]}, "sandbox": {}, "palette": {}, "broken": {}})
    (tmp_path / "broken" / "mod.json").write_text("{not json", encoding="utf-8")   # can't be read: stays off
    found = modlib.discover(str(tmp_path))
    # Never the menu (wcmods' own), never one that isn't there.
    assert modlib.used(found, "story") == ["sandbox", "broken", "palette"]
    changed, blocked = modlib.switch(found, "story", True)
    assert blocked == [] and [i for i, _ in changed] == ["story", "herbs", "sandbox", "palette"]
    assert {m.id for m in modlib.discover(str(tmp_path)) if m.enabled} == {"story", "herbs", "sandbox", "palette"}


def test_a_used_mod_never_blocks_switching_off(tmp_path):
    found = _mods(tmp_path, {"story": {"enabled": True, "uses": ["sandbox"]}, "sandbox": {"enabled": True}})
    changed, blocked = modlib.switch(found, "sandbox", False)
    assert blocked == [] and changed == [("sandbox", False)]
    assert modlib.needing(found, "sandbox") == [] and modlib.unmet(modlib.discover(str(tmp_path))) == {}


def test_an_older_studios_sandbox_requirement_is_a_use_for_a_mod_without_code(tmp_path):
    # A story mod an older Clan Mod Studio saved, downloaded and never saved here: Sandbox mode missing never
    # keeps it (or its items) out of Apply, and turning it on turns Sandbox mode on once it's there.
    _mods(tmp_path, {"story": {"enabled": True, "requires": ["sandbox", "herbs"]}, "herbs": {"enabled": True},
                     "scripted": {"enabled": True, "requires": ["sandbox"]},
                     "pack": {"enabled": True, "pack": True, "requires": ["sandbox"]}})
    (tmp_path / "story" / "npcs.json").write_text('{"npcs": []}', encoding="utf-8")
    (tmp_path / "scripted" / "scripts").mkdir()
    (tmp_path / "scripted" / "scripts" / "main.lua").write_text("print('hi')\n", encoding="utf-8")
    found = modlib.discover(str(tmp_path))
    story = next(m for m in found if m.id == "story")
    assert story.requires == ["herbs"] and story.uses == ["sandbox"]
    assert story.written("requires") == ["sandbox", "herbs"]   # the file itself is left as it is
    unmet = modlib.unmet(found)
    assert "story" not in unmet
    # A mod with code of its own may call Sandbox mode's API, and a pack's "requires" are its mods: both still need it.
    assert unmet["scripted"] == ["needs Sandbox mode, which isn't in your mods"] and "pack" in unmet
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "sandbox" / "mod.json").write_text('{"enabled": false}', encoding="utf-8")
    found = modlib.discover(str(tmp_path))
    assert sorted(modlib.needing(found, "sandbox")) == ["pack", "scripted"]
    modlib.switch(found, "story", False)
    changed, _ = modlib.switch(modlib.discover(str(tmp_path)), "story", True)
    assert ("sandbox", True) in changed
