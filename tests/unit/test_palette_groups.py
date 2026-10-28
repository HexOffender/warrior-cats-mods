"""The new colour slots and coat presets each palette adds, for scripts (palettes.slot_groups and the WCModsPalettes
module), and palette.json's coat presets."""
import json
import re

import pytest

from wcmods import luacheck
from wcmods import palettes as P


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


@pytest.mark.parametrize("coats, why", [
    ({"Ash": {"like": 12}}, '"fur"'),
    ({"Ash": {"fur": "#9a9590"}}, '"like"'),
    ({"Ash": {"fur": "#9a9590", "like": 25}}, '"like"'),
    ({"Ash": {"fur": "#9a9590", "like": True}}, '"like"'),
    ({"Ash": {"fur": "#9a9590", "like": "12"}}, '"like"'),
    ({"Ash": {"fur": "#9a9590", "tail": "#000000", "like": 1}}, "unknown key"),
    ({"Ash": {"fur": "not a colour", "like": 1}}, "coats.Ash.fur"),
    ({"A/B": {"fur": "#9a9590", "like": 1}}, "without /"),
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
