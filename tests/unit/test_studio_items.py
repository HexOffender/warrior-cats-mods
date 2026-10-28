"""The Items page's routes (wcmods/studio.py), on a studio over temporary folders: what a save says about a
half-made item, uploads that never land on another item's file, pictures anywhere in the mod, a model's drawing
kept until the model changes, and the game's items with what each herb does, who for and when (the game's
tables stubbed: the real ones are read by `python wcmods.py selftest`)."""
import json
import os

import pytest

from wcmods import accessories
from wcmods import studio as studio_mod
from wcmods.formats import png

from unit_helpers import make_mod

HERB = {"id": "MoonHerb", "like": "MediumHealingHerb", "name": "Moon Herb", "description": "Heals under the full moon."}
TRIANGLE = "v 0 0 0\nv 0.1 0 0\nv 0 0.1 0\nf 1 2 3\n"


def call(st, method, path, body=None, query=None, upload=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, query, upload)


def picture(path, rgb=(200, 100, 50)):
    with open(path, "wb") as f:
        f.write(png.write(16, 16, bytes(rgb + (255,)) * 256))
    return str(path)


def test_the_save_check_says_an_item_without_a_description_is_left_out(studio):
    folder = make_mod(studio, "mine")
    half = dict(HERB, id="NewHerb", name="New herb", description="")
    r = call(studio, "PUT", "mods/mine/file/items.json", {"text": json.dumps({"items": [half, HERB]})})
    assert r["problems"] == ["NewHerb: it has no description, so it's left out of the game"]
    assert json.loads(open(os.path.join(folder, "items.json"), encoding="utf-8").read())["items"][0] == half, "saved all the same"
    # Once it has one, the line goes.
    r = call(studio, "PUT", "mods/mine/file/items.json", {"text": json.dumps({"items": [dict(half, description="x"), HERB]})})
    assert r["problems"] == []
    # The check is the build's: a mistake in the file is said the same way it always was.
    r = call(studio, "PUT", "mods/mine/file/items.json", {"text": json.dumps({"items": [dict(HERB, id="Moon Herb")]})})
    assert len(r["problems"]) == 1 and "letters and digits" in r["problems"][0]


def test_uploads_never_overwrite_another_items_picture(studio, tmp_path):
    folder = make_mod(studio, "mine")
    first = call(studio, "POST", "mods/mine/picture", query={"name": "NewHerb-icon"}, upload=picture(tmp_path / "a.png", (255, 0, 0)))
    # Another new item named the same way (its id follows its name until it's saved) gets a name of its own.
    second = call(studio, "POST", "mods/mine/picture", query={"name": "NewHerb-icon"}, upload=picture(tmp_path / "b.png", (0, 0, 255)))
    assert (first["path"], second["path"]) == ("pictures/NewHerb-icon.png", "pictures/NewHerb-icon-2.png")
    w, h, rgba = png.read(open(os.path.join(folder, "pictures", "NewHerb-icon.png"), "rb").read())
    assert rgba[:3] == bytes((255, 0, 0)), "the first item's picture is as it was"
    # Names that differ only in case are one file on Windows: told apart all the same.
    third = call(studio, "POST", "mods/mine/picture", query={"name": "newherb-icon"}, upload=picture(tmp_path / "c.png"))
    assert third["path"] == "pictures/newherb-icon-3.png"


def test_choosing_again_keeps_the_items_own_file_name(studio, tmp_path):
    folder = make_mod(studio, "mine")
    call(studio, "POST", "mods/mine/picture", query={"name": "MoonHerb-icon"}, upload=picture(tmp_path / "a.png", (255, 0, 0)))
    again = call(studio, "POST", "mods/mine/picture", query={"name": "MoonHerb-icon", "current": "pictures/MoonHerb-icon.png"},
                 upload=picture(tmp_path / "b.png", (0, 255, 0)))
    assert again["path"] == "pictures/MoonHerb-icon.png"
    assert png.read(open(os.path.join(folder, "pictures", "MoonHerb-icon.png"), "rb").read())[2][:3] == bytes((0, 255, 0))
    assert os.listdir(os.path.join(folder, "pictures")) == ["MoonHerb-icon.png"]
    # Its own file in another folder isn't this one: a free name, as for anyone else's.
    other = call(studio, "POST", "mods/mine/picture", query={"name": "MoonHerb-icon", "current": "icons/MoonHerb-icon.png"},
                 upload=picture(tmp_path / "c.png"))
    assert other["path"] == "pictures/MoonHerb-icon-2.png"


def test_a_ground_model_upload_never_overwrites(studio, tmp_path):
    folder = make_mod(studio, "mine")
    obj = tmp_path / "pebble.obj"
    obj.write_text(TRIANGLE)
    q = {"name": "Pebble-ground", "file": "pebble.obj", "ground": "1"}
    first = call(studio, "POST", "mods/mine/model", query=q, upload=str(obj))
    second = call(studio, "POST", "mods/mine/model", query=q, upload=str(obj))
    assert (first["path"], second["path"]) == ("models/Pebble-ground.obj", "models/Pebble-ground-2.obj")
    mine = call(studio, "POST", "mods/mine/model", query=dict(q, current="models/Pebble-ground-2.obj"), upload=str(obj))
    assert mine["path"] == "models/Pebble-ground-2.obj"
    assert sorted(os.listdir(os.path.join(folder, "models"))) == ["Pebble-ground-2.obj", "Pebble-ground.obj"]
    # A .gltf that keeps its data in another file: the page takes one file, so the Blender step is said.
    gltf = tmp_path / "rock.gltf"
    gltf.write_text(json.dumps({"asset": {"version": "2.0"}, "buffers": [{"byteLength": 12, "uri": "rock.bin"}]}))
    with pytest.raises(ValueError, match=r"keeps its model in rock\.bin: in Blender, export it again as glTF Binary \(\.glb\)"):
        call(studio, "POST", "mods/mine/model", query={"name": "Rock", "file": "rock.gltf", "ground": "1"}, upload=str(gltf))


def test_a_picture_anywhere_in_the_mod_is_served_by_its_path(studio, tmp_path):
    folder = make_mod(studio, "mine", files={"icons/moon.png": open(picture(tmp_path / "m.png"), "rb").read(), "notes.txt": "hi"})
    got = call(studio, "GET", "mods/mine/picture", query={"path": "icons/moon.png"})
    assert got.filename == "moon.png" and png.read(got.data)[0] == 16
    for bad in ("notes.txt", "icons/none.png", "../../data/wcmods.json", os.path.join(folder, "..", "other.png")):
        with pytest.raises(LookupError, match="has no picture"):
            call(studio, "GET", "mods/mine/picture", query={"path": bad})


def test_a_models_drawing_is_kept_until_the_model_changes(studio, tmp_path):
    folder = make_mod(studio, "mine", files={"models/pebble.obj": TRIANGLE})
    first = studio.model_view(studio.mod("mine"), "models/pebble.obj", on_cat=False)
    assert studio.model_view(studio.mod("mine"), "models/pebble.obj", on_cat=False) is first
    path = os.path.join(folder, "models", "pebble.obj")
    with open(path, "w") as f:
        f.write(TRIANGLE + "v 0 0 0.2\nf 1 2 4\n")
    os.utime(path, (os.path.getmtime(path) + 5,) * 2)
    again = studio.model_view(studio.mod("mine"), "models/pebble.obj", on_cat=False)
    assert again is not first and again["triangles"] == 2


def test_build_last_reads_the_last_manifest(studio):
    assert call(studio, "GET", "build/last") == {"manifest": None, "installed": False}, "no build yet"
    manifest = {"built": "2026-10-28T10:00:00", "mods": ["mine"], "names": {"mine": "Mine"}, "outputs": ["x.pak"],
                "notes": {"items": {"items": {"mine/MoonHerb": "Gameplay.Inventory.Consumable.MoonHerb"}}},
                "warnings": ["items: mine: Lost: it has no description, so it's left out of the game"],
                "sections": {"items": {"status": "ok", "mods": ["mine"], "errors": [], "failed": []}}}
    os.makedirs(studio.ctx.build_dir, exist_ok=True)
    with open(os.path.join(studio.ctx.build_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    got = call(studio, "GET", "build/last")
    assert got["installed"] is False, "built (a check of the mods), but not what's in the game"
    assert got["manifest"] == {k: manifest[k] for k in ("built", "mods", "names", "notes", "warnings", "sections")}
    studio.ctx.cfg.data["installed"] = {"built": "2026-10-28T10:00:00", "mods": ["mine"]}
    assert call(studio, "GET", "build/last")["installed"] is True
    studio.ctx.cfg.data["installed"]["built"] = "2026-10-27T09:00:00"
    assert call(studio, "GET", "build/last")["installed"] is False, "an older install"
    with open(os.path.join(studio.ctx.build_dir, "manifest.json"), "w", encoding="utf-8") as f:
        f.write("{not json")
    assert call(studio, "GET", "build/last") == {"manifest": None, "installed": False}


@pytest.mark.parametrize("page", ["items", "animations"])
def test_the_pages_guide_has_its_six_parts_and_no_command_line(studio, page):
    import re
    from wcmods import guide
    root = os.path.dirname(studio.static)
    text = guide.read(root, page)
    assert [line[3:] for line in text.splitlines() if line.startswith("## ")] == [
        "What it changes in the game", "A five-minute first try", "What you can and can't do", "Did it reach the game?",
        "Common mistakes", "Undo"]
    assert not re.search(r"python |wcmods\.py|^\|", text, re.M), "no command lines, no tables"
    assert not re.search(r"A_[A-Z][A-Za-z]+_", text), "the game's animations by their plain names"
    assert set(re.findall(r"<([a-z0-9]+)", guide.render(text))) <= set(guide.TAGS)
    assert page in guide.pages(root) and f"({page}.md)" in guide.read(root, "README")


class Reader:
    """The game's tables for game_items: two herbs, a material, and the badge each shows."""
    use = [{"key": "Gameplay.Inventory.Consumable.MediumHealingHerb", "EffectOnUse": "Gameplay.Effect.Consumable.Health.2",
            "Type": "Health", "Target": "Owner", "bCombat": "TRUE", "bExploration": "TRUE", "bRemoveAfterCombat": "FALSE"},
           {"key": "Gameplay.Inventory.Consumable.ThistlePouch", "EffectOnUse": "Gameplay.Effect.Consumable.Buff.Strength.1",
            "Type": "BuffStrength", "Target": "OwnerTeam", "bCombat": "TRUE", "bExploration": "FALSE", "bRemoveAfterCombat": "TRUE"}]
    info = [("NewRow_1", {"itemTag": "Gameplay.Inventory.Consumable.MediumHealingHerb", "Name": {"text": "Marigold Petal"}, "ItemGroupIcon": 1}),
            ("NewRow_2", {"itemTag": "Gameplay.Inventory.Consumable.ThistlePouch", "Name": {"text": "Juniper Poultice"}, "ItemGroupIcon": 3}),
            ("NewRow_3", {"itemTag": "Gameplay.Inventory.Materials.Dandelion", "Name": {"text": "Dandelion"}, "ItemGroupIcon": 0})]

    def table(self, name):
        return self.use if name == "Consumables.csv" else []

    def cooked_table(self, name):
        return self.info

    def text(self, key):
        return key


class Files:
    def read(self, path):
        return b""

    def find(self, pattern):
        return []


def test_game_items_says_who_and_when_for_each_herb(studio, fake_game, monkeypatch):
    monkeypatch.setattr(studio, "_reader", lambda: Reader())
    monkeypatch.setattr(accessories, "read_variations", lambda data: {})
    studio.ctx._game = Files()
    got = {i["short"]: i for i in call(studio, "GET", "game/items")["items"]}
    assert got["MediumHealingHerb"]["words"] == "Heals 50 health"
    assert (got["MediumHealingHerb"]["target"], got["MediumHealingHerb"]["combat"], got["MediumHealingHerb"]["exploring"],
            got["MediumHealingHerb"]["fight_only"]) == ("Owner", True, True, False)
    assert (got["ThistlePouch"]["target"], got["ThistlePouch"]["combat"], got["ThistlePouch"]["exploring"],
            got["ThistlePouch"]["fight_only"]) == ("OwnerTeam", True, False, True)
    assert got["ThistlePouch"]["words"] == "Whole team +50% Strength for the fight"
    assert (got["MediumHealingHerb"]["group"], got["ThistlePouch"]["group"], got["Dandelion"]["group"]) == ("Health", "Stats", "None")
    assert "words" not in got["Dandelion"] and "target" not in got["Dandelion"], "a material can't be used"
