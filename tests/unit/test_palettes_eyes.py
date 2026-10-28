"""Eye colours in palette.json: how a key names one of the eye atlas's rows (eyeatlas.resolve), and what
palettes.apply_eyes paints into a row, on a made-up atlas (conftest.eye_atlas) instead of the game's."""
import struct

import pytest

from wcmods import colors, eyeatlas, palettes

from unit_helpers import EYE_LABELS, eye_atlas

CLOSE = 2e-3   # half floats keep about three decimal places


def rgb(atlas, row, x):
    return atlas.row(row)[x][:3]


def near(a, b):
    return all(abs(p - q) < CLOSE for p, q in zip(a, b))


def lum(p):
    return colors.luminance(p)


def test_resolve_takes_labels_in_any_case_and_numbers_in_range():
    assert eyeatlas.resolve(EYE_LABELS, "Amber") == 2
    assert eyeatlas.resolve(EYE_LABELS, "  amber ") == 2
    assert eyeatlas.resolve(EYE_LABELS, "SCLERA") == 0
    assert eyeatlas.resolve(EYE_LABELS, "dlc3") == 23
    for key, row in [("iris2", 2), ("row2", 2), ("2", 2), ("iris03", 3), ("Row25", 25), ("0", 0)]:
        assert eyeatlas.resolve(EYE_LABELS, key) == row, key
    # The atlas's own height, when it's given, is the limit (EyeAtlas.slot passes it).
    assert eyeatlas.resolve(EYE_LABELS[:3], "2", 3) == 2


@pytest.mark.parametrize("key", ["row26", "iris99", "30", "26"])
def test_a_row_past_the_atlas_is_a_key_error_naming_the_row(key):
    with pytest.raises(KeyError) as e:
        eyeatlas.resolve(EYE_LABELS, key)
    said = e.value.args[0]
    assert f"'{key}'" in said and "26 eye colours" in said and "0-25" in said
    with pytest.raises(KeyError):
        eye_atlas().slot(key)


@pytest.mark.parametrize("key", ["Ambre", " 3x", "iris", "row-1", "", "²"])
def test_a_key_that_isnt_a_label_or_a_number_names_the_labels(key):
    with pytest.raises(KeyError) as e:
        eyeatlas.resolve(EYE_LABELS, key)
    assert "isn't one of the game's eye colours" in e.value.args[0] and "Amber, Hazel" in e.value.args[0]


def test_reading_or_writing_a_row_past_the_atlas_is_refused():
    atlas = eye_atlas()
    for bad in (-1, 26):
        with pytest.raises(ValueError, match="bad row"):
            atlas.row(bad)
        with pytest.raises(ValueError, match="bad row"):
            atlas.set_row(bad, [(0, 0, 0, 1)] * 64)


def test_one_colour_keeps_the_rows_black_to_rim_ramp():
    atlas = eye_atlas()
    alpha = [p[3] for p in atlas.row(2)]
    target = colors.parse("#ffb300")
    palettes.apply_eyes(atlas, {"Amber": target})
    row = [rgb(atlas, 2, x) for x in range(64)]
    assert near(row[0], (0, 0, 0)), "the pupil end stays black"
    assert near(row[63], colors.to_linear(target)), "the rim is the colour, in linear light"
    lums = [lum(p) for p in row]
    assert all(b >= a - 1e-6 for a, b in zip(lums, lums[1:])), "brighter from pupil to rim"
    assert [p[3] for p in atlas.row(2)] == alpha
    assert near(rgb(atlas, 3, 63), (0.06, 0.5, 0.91)), "the other rows are left as they were"


def test_one_colour_on_a_flat_sclera_row_is_flat():
    atlas = eye_atlas()
    palettes.apply_eyes(atlas, {"Sclera": colors.parse("#f7f3e8")})
    want = colors.to_linear(colors.parse("#f7f3e8"))
    assert all(near(rgb(atlas, 0, x), want) for x in range(64))


def test_a_gradient_puts_its_stops_at_the_ends_and_thirds():
    a, b, c, d = (colors.parse(h) for h in ("#001018", "#00e5ff", "#ff0000", "#ffffff"))
    la, lb, lc, ld = (colors.to_linear(x) for x in (a, b, c, d))
    atlas = eye_atlas()
    palettes.apply_eyes(atlas, {"Sky": [a, b]})
    assert near(rgb(atlas, 9, 0), la) and near(rgb(atlas, 9, 63), lb)
    palettes.apply_eyes(atlas, {"Sky": [a, b, c]})
    assert near(rgb(atlas, 9, 0), la) and near(rgb(atlas, 9, 63), lc)
    for x in (31, 32):   # the middle stop is halfway along, between these two pixels
        assert all(abs(p - q) < 0.03 for p, q in zip(rgb(atlas, 9, x), lb)), x
    palettes.apply_eyes(atlas, {"Sky": [a, b, c, d]})
    assert [near(rgb(atlas, 9, x), want) for x, want in ((0, la), (21, lb), (42, lc), (63, ld))] == [True] * 4
    # A list of one colour is that colour flat, pupil to rim (unlike one colour on its own, which keeps the ramp).
    palettes.apply_eyes(atlas, {"Sky": [b]})
    assert all(near(rgb(atlas, 9, x), lb) for x in range(64))
    assert all(p[3] == 1.0 for p in atlas.row(9))


def test_changes_report_row_label_and_old_and_new_rims():
    atlas = eye_atlas()
    old = colors.hex_from_linear(rgb(atlas, 2, 63))
    changes = palettes.apply_eyes(atlas, {"amber": colors.parse("#ff0000"), "row0": colors.parse("#ffffff")})
    assert changes == [(2, "Amber", old, "#ff0000"), (0, "Sclera", colors.hex_from_linear(rgb(eye_atlas(), 0, 63)), "#ffffff")]


def test_a_row_that_peaks_mid_ramp_keeps_its_shape():
    """Whether every one of the game's rows is brightest at its rim isn't known (reverse-engineering.md):
    a row that peaks before it keeps that shape, its rim the share of the peak it had."""
    atlas = eye_atlas()
    peak = (0.2, 0.6, 0.9)
    pixels = []
    for x in range(64):
        s = x / 40 if x <= 40 else 1.0 - 0.5 * (x - 40) / 23   # up to the peak at x 40, then down to half
        pixels.append((peak[0] * s, peak[1] * s, peak[2] * s, 1.0))
    atlas.set_row(5, pixels)
    target = colors.to_linear(colors.parse("#40c060"))
    palettes.apply_eyes(atlas, {"Green": colors.parse("#40c060")})
    assert near(rgb(atlas, 5, 40), target), "the brightest pixel takes the colour"
    assert near(rgb(atlas, 5, 63), [0.5 * c for c in target]), "the rim keeps half of it, as it had half the peak"
    assert near(rgb(atlas, 5, 0), (0, 0, 0))


def test_the_atlas_round_trips_its_bytes_and_clamps_what_half_floats_cant_hold():
    atlas = eye_atlas()
    before = atlas.bytes()
    atlas.set_row(1, atlas.row(1))
    assert atlas.bytes() == before
    atlas.set_row(1, [(-1.0, 1e9, 0.5, 1.0)] * 64)
    assert struct.unpack_from("<4e", atlas.data, 64 * 8)[:2] == (0.0, 64992.0)
