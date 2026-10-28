"""The game's file formats, without the game: the hashes, the save codec, pictures, the Kraken decoder and
the CSV editor. These are the checks `python wcmods.py selftest` runs before it touches the game's files."""
import pytest

from wcmods import controls, selftest
from wcmods.formats.blake3 import blake3


def test_blake3_vector():
    assert blake3(b"").hex().startswith("af1349b9f5f9a1a6")


def test_name_hashes_as_in_the_games_name_maps():
    assert selftest._name_hashes()


def test_unversioned_property_headers_round_trip():
    assert selftest._unversioned_headers()


def test_saves_over_128k_read_and_written():
    ok, detail = selftest._long_save()
    assert ok, detail


def test_save_hash_is_read_from_the_gvas_header():
    ok, detail = selftest._save_hash()
    assert ok, detail


def test_save_hash_and_version_of_a_save_without_them_or_laid_out_otherwise():
    from wcmods.formats.save import _header_value
    head = selftest._save_header(0x1122334455667788, 20)
    assert _header_value(head, "Hash", "UInt64Property", 8) == bytes.fromhex("8877665544332211")
    assert _header_value(head, "Version", "ByteProperty", 1) == b"\x14"
    assert _header_value(head, "Hash", "UInt64Property", 4) is None          # another size: not read
    assert _header_value(head[:-1], "Version", "ByteProperty", 1) is None    # cut short
    flagged = head.replace(b"\x08\x00\x00\x00\x00\x88", b"\x08\x00\x00\x00\x01\x88")   # a flag set: more fields
    assert _header_value(flagged, "Hash", "UInt64Property", 8) is None


def test_pictures_pngs_dxt_blocks_and_recolours():
    assert selftest._pictures()


def test_kraken_decoder_against_oodles_own_output():
    ok, detail = selftest._kraken_fixtures()
    assert ok, detail


def test_csv_rows_added_and_removed_in_the_files_style():
    assert selftest._csv_rows()


def test_cat_rename_inside_save_text():
    assert selftest._rename_struct()


def test_cats_named_with_a_mods_text_the_build_leaves_out_are_warned_about():
    assert selftest._names_without_text()


def test_colour_slots_and_your_cats_colours_and_scars():
    assert selftest._colour_slots()


def test_palette_switching():
    assert selftest._palette_switching()


def test_bindings_read_and_a_save_without_any():
    text = '{"acct": {"Shared": {"InputKeyboard": {"Player_Interact": "0,Player_Interact,E,1.000000.1"}}}}'
    assert controls.read_bindings(text) == {"keyboard": {"Player_Interact": "E"}, "gamepad": {}}
    for empty in ("{}", '{"acct": {}}'):   # a save the game hasn't written settings to yet
        with pytest.raises(LookupError):
            controls.read_bindings(empty)
