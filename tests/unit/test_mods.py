"""Mods and setup without the game: downloaded .zips and what's refused, the key remapper's presses, menu
remaps, the agent controller's parts, and getting set up in temporary folders."""
from wcmods import selftest


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


def test_agent_controller_parts():
    assert selftest._agent_parts()


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
