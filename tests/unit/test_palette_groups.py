"""The new colour slots and coat presets each palette adds, for scripts (palettes.slot_groups and the WCModsPalettes
module), and palette.json's coat presets."""
import json
import re

import pytest

from wcmods import luacheck
from wcmods import palettes as P

from unit_helpers import eye_atlas


class Mod:
    def __init__(self, mod_id, name):
        self.id, self.name = mod_id, name


def test_each_palette_lists_the_new_slots_it_wins():
    items = [(Mod("dark", "Dark Forest"), {"pattern": {"100": (1, 0, 0), "101": (0, 1, 0), "3": (0, 0, 1)},
                                            "marking": {"100": (1, 1, 1)}}),
             (Mod("moor", "WindClan Moor"), {"pattern": {"101": (0, 0, 0), "125": (1, 1, 0)}, "fur": {"3": (0, 0, 0)}}),
             (Mod("restyle", "Restyle"), {"pattern": {"4": (0, 0, 0)}, "eyes": {"Amber": (1, 0, 0)}})]
    groups = P.slot_groups(items)
    # Slot 101 is the later palette's, as merge() keeps its colour; a palette that adds none is left out.
    assert groups == [{"id": "dark", "name": "Dark Forest", "pattern": [100], "marking": [100], "coats": []},
                      {"id": "moor", "name": "WindClan Moor", "pattern": [101, 125], "marking": [], "coats": []}]
    lua = P.groups_module(groups)
    assert not luacheck.check(lua)
    assert ('{ ["id"] = "dark", ["name"] = "Dark Forest", ["pattern"] = { 100 }, ["marking"] = { 100 }, '
            '["coats"] = {  } }') in lua
    assert P.groups_module([]).rstrip().endswith("return {  }")


def load(tmp_path, doc):
    path = tmp_path / "palette.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return P.load(str(path))


def test_coat_presets_load_with_the_game_coat_they_save_as(tmp_path):
    pal = load(tmp_path, {"coats": {"Ash": {"fur": "#9a9590", "nose": "#3a3330", "like": 12, "_note": "grey"},
                                    "Snow": {"fur": "white", "paws": [255, 0, 0], "like": 0},
                                    "_help": "presets"}})
    assert sorted(pal["coats"]) == ["Ash", "Snow"]
    assert pal["coats"]["Ash"]["like"] == 12
    assert P.colors.hex_from_srgb(pal["coats"]["Ash"]["nose"]) == "#3a3330"
    assert P.colors.hex_from_srgb(pal["coats"]["Snow"]["paws"]) == "#ff0000"
    assert "ears" not in pal["coats"]["Ash"]
    # Only coat presets: it changes none of the game's colours.
    assert P.adds_only(pal)
    assert not P.adds_only({**pal, "fur": {"3": (0, 0, 0)}})


def test_coat_colours_past_the_games_are_presets_saved_as_the_nearest_game_coat(tmp_path):
    """A fur colour numbered 25 and up is written as a pattern one is, and becomes a coat preset: the game's coat
    table never gets it (a cat on a coat past 24 crashes the game), and the save holds the game coat it's most like."""
    pal = load(tmp_path, {"fur": {"3": "#112233", "100": "#9fb6e0", "101": "white", "102": "#f00cf0"},
                          "coats": {"Ash": {"fur": "#9a9590", "like": 12}}})
    assert P.fur_presets(pal) == {100: {"fur": P.colors.parse("#9fb6e0"), "like": 15},
                                  101: {"fur": (1.0, 1.0, 1.0), "like": 10},
                                  102: {"fur": P.colors.parse("#f00cf0"), "like": 18}}
    # Never the Feral Edition's coats (20-24), which a game without it swaps: #F28EF3 is coat 21.
    assert P.nearest_coat(P.colors.parse("#F28EF3")) < P.LIKE_SLOTS
    assert P.merge([pal])["fur"] == {"3": P.colors.parse("#112233")}
    assert "[100]" not in P.ue4ss_script(P.merge([pal]))
    assert P.adds_only({"fur": {"100": (1, 1, 1)}}) and not P.adds_only(pal)
    # Listed after the palette's named presets; a slot two palettes set is the later one's, as for patterns.
    groups = P.slot_groups([(Mod("old", "Old"), {"fur": {"100": (0, 0, 0), "105": (0, 0, 0)}}), (Mod("mine", "Mine"), pal)])
    assert groups[0]["coats"] == [{"id": "old/fur/105", "name": "Coat colour 105", "slot": 105, "like": 14, "fur": "#000000"}]
    assert [c["id"] for c in groups[1]["coats"]] == ["mine/Ash", "mine/fur/100", "mine/fur/101", "mine/fur/102"]
    assert groups[1]["coats"][1] == {"id": "mine/fur/100", "name": "Coat colour 100", "slot": 100, "like": 15, "fur": "#9fb6e0"}
    assert not luacheck.check(P.groups_module(groups))


@pytest.mark.parametrize("coats, why", [
    ({"Ash": {"like": 12}}, '"fur"'),
    ({"Ash": {"fur": "#9a9590"}}, '"like"'),
    ({"Ash": {"fur": "#9a9590", "like": 25}}, '"like"'),
    ({"Ash": {"fur": "#9a9590", "like": True}}, '"like"'),
    ({"Ash": {"fur": "#9a9590", "like": "12"}}, '"like"'),
    ({"Ash": {"fur": "#9a9590", "tail": "#000000", "like": 1}}, "unknown key"),
    ({"Ash": {"fur": "not a colour", "like": 1}}, "coats.Ash.fur"),
    ({"A/B": {"fur": "#9a9590", "like": 1}}, "without /"),
    ({"Ash ": {"fur": "#9a9590", "like": 1}}, "spaces at its ends"),
    ({"Ash": "#9a9590"}, "should be an object"),
    (["Ash"], "object of presets"),
])
def test_bad_coat_presets_are_refused(tmp_path, coats, why):
    with pytest.raises(ValueError, match=re.escape(why)):
        load(tmp_path, {"coats": coats})


def test_coat_presets_are_listed_by_palette_with_their_ids(tmp_path):
    pal = load(tmp_path, {"coats": {"Blue fox": {"fur": "#3050ff", "nose": "#00ff00", "like": 3}}})
    groups = P.slot_groups([(Mod("coats", "Coat test"), pal), (Mod("none", "Nothing"), {"pattern": {"3": (0, 0, 0)}})])
    assert groups == [{"id": "coats", "name": "Coat test", "pattern": [], "marking": [],
                       "coats": [{"id": "coats/Blue fox", "name": "Blue fox", "like": 3, "fur": "#3050ff",
                                  "nose": "#00ff00"}]}]
    assert not luacheck.check(P.groups_module(groups))


class Ctx:
    """Just enough of the build context for the palettes section: what it adds, patches, notes and warns, with the
    script loader installed unless `loader` says otherwise."""
    def __init__(self, loader=True):
        self.shared, self.notes, self.mods, self.patched, self.warnings, self.read = {}, {}, {}, {}, [], []
        self.cfg = type("Cfg", (), {"ue4ss_mods_dir": "ue4ss/Mods" if loader else None})()

    def add_ue4ss_mod(self, name, files): self.mods[name] = files
    def add_ue4ss_shared(self, name, text): self.shared[name] = text
    def note(self, key, value): self.notes[key] = value
    def log(self, *a): pass
    def warn(self, msg): self.warnings.append(msg)
    def patch_package(self, path, data, source=None): self.patched[path] = data

    def read_game_file(self, path):
        self.read.append(path)
        return b"the game's eye atlas"


def test_a_coats_only_palette_installs(tmp_path):
    from wcmods.sections.palettes import PaletteSection
    pal = load(tmp_path, {"coats": {"Ash": {"fur": "#8f8a85", "like": 11}}})
    other = {"pattern": {"100": (1, 0, 0)}, "fur": {"3": (0, 0, 0)}}
    assert "coats" not in P.merge([pal, other])
    ctx = Ctx()
    PaletteSection().build(ctx, [(Mod("coats", "Coat presets"), pal), (Mod("dark", "Dark Forest"), other)])
    assert ctx.notes["new_colours"] == {"coats": {"coats": 1}, "dark": {"pattern": 1}}
    lua = ctx.shared[P.GROUPS_LUA]
    assert '["id"] = "coats/Ash"' in lua and not luacheck.check(lua)
    assert not luacheck.check(ctx.mods[next(iter(ctx.mods))]["Scripts/main.lua"])


# ---------- the colours a palette.json can say, and what it can't ----------
def test_palette_colours_load_in_every_form_the_docs_allow(tmp_path):
    pal = load(tmp_path, {"fur": {"0": "orange", "1": [255, 0, 0], "2": "#11223344", "3": "abc", "4": [0, 0, 255, 128],
                                  "5": "  #A1B2C3 ", "6": [300, -5, 127.6]},
                          "eyes": {"Amber": "teal", "Sky": ["#001018", [0, 229, 255]], "Sclera": "#f7f3e8ff"}})
    assert {k: P.colors.hex_from_srgb(v) for k, v in pal["fur"].items()} == {
        "0": "#ff8c00", "1": "#ff0000", "2": "#112233", "3": "#aabbcc", "4": "#0000ff", "5": "#a1b2c3", "6": "#ff0080"}
    assert P.colors.hex_from_srgb(pal["eyes"]["Amber"]) == "#008080"
    assert [P.colors.hex_from_srgb(c) for c in pal["eyes"]["Sky"]] == ["#001018", "#00e5ff"]
    assert P.colors.hex_from_srgb(pal["eyes"]["Sclera"]) == "#f7f3e8"


@pytest.mark.parametrize("doc, why", [
    ({"fur": {" 3": "#ffffff"}}, "fur keys are coat colour numbers, counted from 0; got ' 3'"),
    ({"fur": {"3x": "#ffffff"}}, "coat colour numbers, counted from 0"),
    ({"fur": {"²": "#ffffff"}}, "coat colour numbers, counted from 0"),
    ({"iris_ui": {"30": "#ffffff"}}, "iris_ui has the game's cat maker eye button colours 0-24 only; only coat, pattern and "
                                      "marking colours take new ones"),
    ({"fur": {"3": ["#000000", "#ffffff"]}}, "gradients are eyes-only"),
    ({"eyes": {"Amber": []}}, "eyes.Amber"),
    ({"eyes": {"Amber": "#GGGGGG"}}, "not a colour"),
    ({"hats": {"0": "#ffffff"}}, "unknown part 'hats'"),
    ({"pattern": ["#ffffff"]}, "pattern should be an object of pattern colours by colour number"),
    ({"eyes": "Amber"}, "eyes should be an object of colours by the game's eye colour names"),
])
def test_load_refuses_what_the_build_cant_use_with_a_sentence(tmp_path, doc, why):
    with pytest.raises(ValueError, match=re.escape(why)):
        load(tmp_path, doc)


def test_load_ignores_notes_and_counts_leading_zeros_as_the_game_does(tmp_path):
    pal = load(tmp_path, {"_help": "x", "name": "Dawn", "description": "Pinks", "fur": {"_note": "warm", "03": "#ffffff"},
                          "pattern": {"025": "#ff00cc"}})
    assert pal == {"fur": {"3": (1.0, 1.0, 1.0)}, "pattern": {"25": (1.0, 0.0, 0.8)}}
    assert P.new_slots(pal) == {"pattern": [25]}


# ---------- the palettes section's eyes, on a made-up atlas ----------
RED, GREEN, BLUE = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


@pytest.fixture
def atlases(monkeypatch):
    """The eye atlases the section reads, made up (conftest.eye_atlas): the list of those it made."""
    import copy
    from wcmods import eyeatlas
    made, template = [], eye_atlas()

    def fake(data):
        made.append(copy.deepcopy(template))
        return made[-1]
    monkeypatch.setattr(eyeatlas, "EyeAtlas", fake)
    return made


def build(*items, loader=True):
    from wcmods.sections.palettes import PaletteSection
    ctx = Ctx(loader)
    PaletteSection().build(ctx, [(Mod(i, i.title()), pal) for i, pal in items])
    return ctx


def rim(atlas, row):
    return P.colors.hex_from_linear(atlas.row(row)[-1][:3])


def test_the_highest_palette_wins_an_eye_named_two_ways(atlases):
    from wcmods import eyeatlas
    ctx = build(("low", {"eyes": {"iris2": RED}}), ("mid", {"eyes": {"Amber": GREEN}}), ("high", {"eyes": {"iris2": BLUE}}))
    assert rim(atlases[0], 2) == "#0000ff"
    assert [(n["row"], n["slot"], n["to"]) for n in ctx.notes["eyes"]] == [(2, "Amber", "#0000ff")]
    assert eyeatlas.PATH in ctx.patched and ctx.warnings == []
    build(("low", {"eyes": {"iris2": RED}}), ("high", {"eyes": {"amber": GREEN}}))
    assert rim(atlases[1], 2) == "#00ff00"


def test_a_misspelt_eye_in_one_mod_skips_only_that_entry(atlases):
    ctx = build(("typo", {"eyes": {"Ambre": RED, "Hazel": GREEN}}), ("fine", {"eyes": {"Sky": BLUE}}))
    assert len(ctx.warnings) == 1
    assert ctx.warnings[0].startswith("typo: 'Ambre' isn't one of the game's eye colours (Sclera, Yellow, Amber")
    assert ctx.warnings[0].endswith("; skipped it")
    assert rim(atlases[0], 3) == "#00ff00" and rim(atlases[0], 9) == "#0000ff"


def test_a_row_past_the_atlas_in_one_mod_skips_only_that_entry(atlases):
    ctx = build(("far", {"eyes": {"row26": RED, "iris3": GREEN}}), ("fine", {"eyes": {"30": BLUE, "Sky": BLUE}}))
    assert ctx.warnings == ["far: 'row26' is past the game's 26 eye colours (they're 0-25); skipped it",
                            "fine: '30' is past the game's 26 eye colours (they're 0-25); skipped it"]
    assert rim(atlases[0], 3) == "#00ff00" and rim(atlases[0], 9) == "#0000ff"


def test_iris_ui_is_derived_from_the_new_rims_unless_the_file_sets_it(atlases):
    from wcmods.config import UE4SS_MOD_NAME
    ctx = build(("eyes", {"eyes": {"Amber": RED, "Hazel": GREEN}, "iris_ui": {"2": BLUE}}))
    lua = ctx.mods[UE4SS_MOD_NAME]["Scripts/main.lua"]
    # The cat maker's eye buttons are rows 1-25 in order: Amber (row 2) is button 1; button 2 is the file's own.
    assert "IrisColors = { [1] = {1.0000, 0.0000, 0.0000}, [2] = {0.0000, 0.0000, 1.0000} }" in lua
    assert ctx.notes["runtime_palette"]["iris_ui"] == ["1", "2"]
    assert not luacheck.check(lua)


def test_runtime_colours_without_the_script_loader_warn(atlases):
    said = ("coat, pattern and marking colours go in through the script loader (UE4SS), which isn't installed: "
            "Get set up on the Mods page adds it")
    for part in ("fur", "pattern", "marking"):
        assert build(("theme", {part: {"3": RED}}), loader=False).warnings == [said], part
    assert build(("theme", {"pattern": {"30": RED}}), loader=False).warnings == [said], "a new colour too"
    # Eyes go in through the game's files; the cat maker's eye buttons they bring along aren't worth a warning.
    assert build(("eyes", {"eyes": {"Amber": RED}}), loader=False).warnings == []
    assert build(("theme", {"fur": {"3": RED}})).warnings == [], "with the script loader in"


def test_no_eyes_in_any_mod_patches_nothing(atlases):
    ctx = build(("coats", {"fur": {"3": RED}}))
    assert atlases == [] and ctx.read == [] and ctx.patched == {} and "eyes" not in ctx.notes
    # Eyes that all miss: the atlas is read, and nothing is patched.
    ctx = build(("typo", {"eyes": {"Ambre": RED}}))
    assert len(atlases) == 1 and ctx.patched == {} and len(ctx.warnings) == 1
