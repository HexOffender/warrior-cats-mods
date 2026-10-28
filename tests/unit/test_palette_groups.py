"""The new colour slots each palette adds, for scripts (palettes.slot_groups and the WCModsPalettes module)."""
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
    assert groups == [{"id": "dark", "name": "Dark Forest", "pattern": [100], "marking": [100]},
                      {"id": "moor", "name": "WindClan Moor", "pattern": [101, 125], "marking": []}]
    lua = P.groups_module(groups)
    assert not luacheck.check(lua)
    assert '{ ["id"] = "dark", ["name"] = "Dark Forest", ["pattern"] = { 100 }, ["marking"] = { 100 } }' in lua
    assert P.groups_module([]).rstrip().endswith("return {  }")
