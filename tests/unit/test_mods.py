"""Mods and setup without the game: downloaded .zips and what's refused, the key remapper's presses, menu
remaps, the agent controller's parts, getting set up in temporary folders, and what mods need ("requires")
and only use ("uses")."""
import json
import os
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


def _hpp(name):
    """A C++ SDK header's text (wcmods/cpp_sdk/include/WCMods/<name>); it's compiled only by `cpp build`."""
    path = os.path.join(os.path.dirname(os.path.abspath(selftest.__file__)), "cpp_sdk", "include", "WCMods", name)
    with open(path, encoding="utf-8") as f:
        return f.read()


def _between(text, start, end):
    """The text from `start` up to `end` (both found in order)."""
    i = text.index(start)
    return text[i:text.index(end, i + len(start))]


def test_cpp_save_file_is_parsed_again_only_when_it_changed():
    """The C++ half of W6: save_file() parsed WrcGame.json (about 40 ms) on every call. As the Lua's fileCache, the parsed
    save is kept while the file's size is the same (looked at 4 times a second, parsed again every 30 s at least), a
    half-written file gives the last good one, save_game() drops it (as Game.save.write), and slot_data() and items()
    read it without copying the whole save."""
    hpp = _hpp("World.hpp")
    read = _between(hpp, "inline auto read_save() -> SaveRead", "\n        }\n")
    assert read.index("std::lock_guard lock(c.lock);") < read.index("read_file(save_path())")
    assert "if (c.data && now - c.checked < 250ms) return {c.data, c.size, c.at};" in read
    assert "if (c.data && size == c.size && now - c.at < 30s) return {c.data, c.size, c.at};" in read
    assert "if (!parsed) return {c.data, c.size, c.at};" in read
    assert "c.at = now;" in read and "c.size = size;" in read
    assert "detail::read_save()" in _between(hpp, "inline auto save_file() -> Json", "\n    }\n")
    assert "save_file()" not in _between(hpp, "inline auto slot_data() -> Json", "\n    }\n")
    assert "slot_data()" not in _between(hpp, "inline auto items() -> Json", "\n    }\n")
    write = _between(hpp, "inline auto save_game(", "\n    }\n")
    assert write.index("c.data.reset();") < write.index('STR("Save")')
    # The cat's slot is still the one the file names (#111), not the save game's slot index.
    assert '["Shared"]["General"]["CurrentCatSlot"]' in _between(hpp, "inline auto slot_of(const Json& file)", "\n        }\n")


def test_cpp_items_drop_the_pickups_of_another_save():
    """The C++ half of W7: items() laid the HUD's pickup totals over the save and never let go of them. As the Lua's
    pickups, they're stamped with the HUD that sent them (call.self(): its address and its name, which has the instance
    number, so a recycled address is another stamp) and the save file's size at the last one. Another HUD drops them,
    and so does a save the game wrote after them at another size, looked at once for each parse of the save. No HUD to
    go by (a level loading) keeps them, and a save written just before a pickup but not read yet doesn't drop it. No slot
    in the stamp (save_slot() stays 0 whatever the cat), no poller, and the mutex stays."""
    hpp = _hpp("World.hpp")
    hook = _between(hpp, 'on_function(STR("/Script/Wrc.GuiHudWrc:OnItemPickedUp")', "\n            });")
    assert "UObject* hud = call.self();" in hook and "std::wstring hud_name = name(hud);" in hook
    assert "auto size = save_size();" in hook and "std::lock_guard lock(p.lock);" in hook
    assert "if (hud && (hud != p.hud || hud_name != p.hud_name))" in hook and "save_slot" not in hook
    assert hook.index("drop_pickups(p);") < hook.index("p.live[tag] = total;") < hook.index("p.size = size;")
    assert "p.seen.reset();" in hook
    listing = _between(hpp, "inline auto items() -> Json", "\n    }\n")
    assert listing.index("detail::read_save()") < listing.index("std::lock_guard lock(p.lock);")
    assert "if (!p.live.empty())" in listing and "save_slot" not in listing
    assert "bool other = hud && p.hud && (hud != p.hud || name(hud) != p.hud_name);" in listing
    saved = _between(listing, "if (p.seen != save.at)", "\n            }")
    assert "p.seen = save.at;" in saved
    assert "saved = p.size && save.size && *save.size != *p.size && save.size == detail::save_size();" in saved
    assert "if (other || saved) detail::drop_pickups(p);" in listing
    assert listing.index("drop_pickups(p)") < listing.index("for (auto& [tag, total] : p.live)")
    finder = _between(hpp, "inline auto pickups_hud(const Pickups& p) -> UObject*", "\n        }\n")
    assert "if (object_staying(p.hud, p.hud_class)) return p.hud;" in finder
    assert 'find_first(STR("WBP_GuiHudGameWrc_C"))' in finder and "object_staying(h, nullptr) ? h : nullptr" in finder
    for poller in ("on_level", "every_frame", "every("):
        assert poller not in listing + hook
    # Staying: alive and not marked with UE 5's Garbage flag, which UE4SS's IsValid doesn't look at (the Lua's Game.alive).
    staying = _between(_hpp("Game.hpp"), "inline auto object_staying(", "\n        }\n")
    assert "0x00200000" in staying and "object_alive(o, was)" in staying
    assert "inline auto object_alive(" not in _hpp("Ui.hpp")   # one copy, in Game.hpp


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
