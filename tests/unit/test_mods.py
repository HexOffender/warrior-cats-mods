"""Mods and setup without the game: downloaded .zips and what's refused, the key remapper's presses, menu
remaps, the agent controller's parts, and getting set up in temporary folders."""
from wcmods import selftest


def test_adding_a_downloaded_mod_from_a_zip_and_refusing_unsafe_ones():
    assert selftest._mod_zips()


def test_a_zip_cant_hide_code_or_claim_to_come_with_wcmods():
    assert selftest._mod_zip_guards()


def test_key_remapper_presses():
    assert selftest._remapper_presses()


def test_menu_remaps():
    assert selftest._menu_remaps()


def test_agent_controller_parts():
    assert selftest._agent_parts()


def test_getting_set_up_finds_the_game_from_any_of_its_folders():
    assert selftest._onboarding()


def test_getting_set_up_rough_edges():
    assert selftest._onboarding_edges()


def test_cpp_mod_dll_goes_in_with_its_settings_and_bad_dlls_are_refused():
    ok, detail = selftest._cpp_mod()
    assert ok, detail


def test_cpp_sdk_headers_documented_and_tested():
    ok, detail = selftest._cpp_sdk()
    assert ok, detail
