"""items.json as the items section reads it (wcmods/sections/items.py), without the game: what a half-made item
does to the rest (it's left out, with a warning, and the others go in), what's refused, and the words the Items
page names each herb's effect by. What the game's tables say about an item is checked by `python wcmods.py
selftest`."""
import json
import os
import re

import pytest

from wcmods.sdk import BuildContext
from wcmods.sections import items as items_mod
from wcmods.sections.items import EFFECT_WORDS, NOTHING_OWN, Game, ItemsSection

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERB = {"id": "MoonHerb", "like": "MediumHealingHerb", "name": "Moon Herb", "description": "Heals under the full moon."}


class Ctx:
    def __init__(self):
        self.warnings, self.left_out, self.current = [], [], None

    warn = BuildContext.warn
    leave_out = BuildContext.leave_out


def collect(tmp_path, data, ctx=None):
    mod = type("Mod", (), {"id": "mine", "folder": str(tmp_path)})()
    (tmp_path / "items.json").write_text(json.dumps(data), encoding="utf-8")
    return ItemsSection().collect(mod, ctx if ctx is not None else Ctx())


@pytest.mark.parametrize("key, value", [("name", ""), ("name", "   "), ("name", None), ("description", ""),
                                        ("description", " \n"), ("description", None)])
def test_an_item_without_a_name_or_description_is_left_out_with_a_warning(tmp_path, key, value):
    half = dict(HERB, id="NewHerb", **{key: value})
    if value is None:
        del half[key]
    ctx = Ctx()
    got = collect(tmp_path, {"items": [half, HERB]}, ctx)
    assert got == {"items": [HERB], "recipes": {}}, "the other item still goes in"
    assert ctx.warnings == [f"mine: NewHerb: it has no {key}, so it's left out of the game"]
    # Listed for the studio's save too, by name (its id when it has none), with why in a few words.
    name = "NewHerb" if key == "name" else "Moon Herb"
    assert ctx.left_out == [{"section": None, "mod": "mine", "id": "NewHerb", "name": name, "why": f"no {key}"}]
    # Alone, it leaves nothing to build.
    assert collect(tmp_path, {"items": [half]}) is None
    # A name or description that isn't text is a mistake in the file, not a half-made item.
    with pytest.raises(ValueError, match=f'"{key}" should be text'):
        collect(tmp_path, {"items": [dict(HERB, **{key: 5})]})


def test_an_accessory_with_nothing_of_its_own_is_warned(tmp_path):
    bare = {"id": "Collar", "like": "Neck.DogCollar.1", "name": "Collar", "description": "Blue."}
    ctx = Ctx()
    assert collect(tmp_path, {"items": [bare, HERB]}, ctx) == {"items": [HERB], "recipes": {}}
    assert ctx.warnings == [f"mine: Collar: {NOTHING_OWN}, so it's left out of the game"]
    assert [(x["name"], x["why"]) for x in ctx.left_out] == [("Collar", "nothing of its own yet")]
    for own in ({"texture": {"tint": "#a8c4ff"}}, {"model": "models/c.glb"}, {"place": {"up": 1}}, {"opacity": 0.5}):
        assert collect(tmp_path, {"items": [dict(bare, **own)]})["items"][0]["id"] == "Collar", own
    # One the build gets anyway (its kind given, with a look the game has) is refused there in the same words.
    game = object.__new__(Game)
    game._looks, game._meshes, game.added = {"DogCollar": ["/Game/T_DogCollar_BC.T_DogCollar_BC"]}, {}, {}
    tag = "Gameplay.Inventory.Cosmetic.Neck.DogCollar.1"
    with pytest.raises(ValueError, match=re.escape(NOTHING_OWN)):
        game.look({"id": "Collar"}, tag)
    with pytest.raises(ValueError, match="a colour, or a PNG picture"):
        game.look({"id": "Collar", "texture": "pictures/collar.jpg"}, tag)
    assert game.look({"id": "Collar", "texture": {"tint": "#ffffff"}}, tag)["var"] == 2
    # Without a "like", the build says it needs one (the selftest counts that warning).
    assert collect(tmp_path, {"items": [{"id": "Crown", "kind": "accessory", "name": "Crown", "description": "x"}]})


@pytest.mark.parametrize("item_id", ["Moon Herb", "1Herb", "M" * 49, "", 5, None])
def test_ids_that_arent_letters_and_digits_are_refused(tmp_path, item_id):
    with pytest.raises(ValueError, match="letters and digits"):
        collect(tmp_path, {"items": [dict(HERB, id=item_id)]})


def test_unknown_keys_are_refused_and_underscore_keys_ignored(tmp_path):
    with pytest.raises(ValueError, match="unknown key.*colour"):
        collect(tmp_path, {"items": [dict(HERB, colour="red")]})
    noted = dict(HERB, _note="mine, from a hand edit")
    assert collect(tmp_path, {"items": [noted], "_help": "x"})["items"] == [noted]


@pytest.mark.parametrize("extra, message", [
    ({"icon": 5}, '"icon" should be text or a recolour'),
    ({"icon": {"from": 3, "tint": "#ffffff"}}, '"icon".from should be text'),
    ({"icon": {"from": "Rock"}}, "say how to recolour it"),
    ({"icon": {"tint": "blue"}}, "colour like"),
    ({"recipe": [1]}, '"recipe" should map materials'),
    ({"combat": "yes"}, '"combat" should be true or false'),
    ({"opacity": True}, '"opacity" should be a number'),
    ({"opacity": 2}, '"opacity" should be a number'),
    ({"like": 7}, '"like" should be text'),
])
def test_pictures_recipes_flags_and_opacity_are_checked(tmp_path, extra, message):
    with pytest.raises(ValueError, match=message):
        collect(tmp_path, {"items": [dict(HERB, **extra)]})


def test_items_json_shape(tmp_path):
    with pytest.raises(ValueError, match='"items" should be a list'):
        collect(tmp_path, {"items": {}})
    with pytest.raises(ValueError, match='"recipes" should map'):
        collect(tmp_path, {"recipes": []})
    with pytest.raises(ValueError, match="should be an object"):
        collect(tmp_path, [])
    assert collect(tmp_path, {}) is None
    recipes = {"Cosmetic.Head.MossPatch.1": {"Moss": 3}}
    assert collect(tmp_path, {"recipes": recipes}) == {"items": [], "recipes": recipes}


def test_an_icon_that_isnt_a_png_is_said_to_be_one(tmp_path):
    game = object.__new__(Game)
    game.info = {}
    for icon in ("icons/moon.jpg", "pictures/moon.webp", "moon.JPEG", "icons/moon"):
        with pytest.raises(ValueError, match="icons are PNG pictures"):
            game.icon(icon, {"Icon": {}})
    with pytest.raises(ValueError, match="no item Moonstone to borrow"):
        game.icon("Moonstone", {"Icon": {}})


def test_effect_words_cover_every_game_herb_in_the_docs():
    # docs/mechanics/items.md's "What consumables do": a herb a row, or several sharing their last word
    # ("Small / Medium / Big Catnip"); the ids are the names without spaces.
    with open(os.path.join(REPO, "docs", "mechanics", "items.md"), encoding="utf-8") as f:
        text = f.read()
    table = text.split("## What consumables do", 1)[1].split("\n\n", 2)[2].split("\n\n", 1)[0]
    ids = []
    for row in table.splitlines()[2:]:
        cell = row.split("|")[1].strip()
        names = [n.strip() for n in cell.split(" / ")]
        last = names[-1].split()[-1]
        ids += [(n if n == names[-1] else f"{n} {last}").replace(" ", "") for n in names]
    assert len(ids) == 25
    assert sorted(ids) == sorted(EFFECT_WORDS)
    assert all(w and w[0].isupper() or w[0] in "+" for w in EFFECT_WORDS.values())
    assert EFFECT_WORDS["MediumHealingHerb"] == "Heals 50 health"
    assert "not checked" in EFFECT_WORDS["SuperHealingHerb"], "what it does isn't known for sure"
    assert items_mod.KEYS >= {"name", "description", "texture", "model", "place", "opacity"}


def test_a_recipe_asking_for_a_material_of_the_mods_that_was_left_out_says_so():
    """The herb's recipe names its mod's own material by id; when that material was left out (no description
    yet, or refused by the build), the recipe says that rather than that there's no such material."""
    game = object.__new__(Game)
    game.info, game.materials = {}, {"Gameplay.Inventory.Materials.Dandelion"}
    game.left = {("mine", "Moonstone"): ("Moonstone", "no description")}
    with pytest.raises(ValueError, match="Moonstone is one of this mod's, left out: no description"):
        game.cost({"Moonstone": 1}, {}, "mine")
    with pytest.raises(ValueError, match="there's no material Moonstone"):
        game.cost({"Moonstone": 1}, {}, "other")
    assert game.cost({"Moonstone": 2}, {"Gameplay.Inventory.Materials.Moonstone": "mine"}, "mine") == \
        "Gameplay.Inventory.Materials.Moonstone,2"
