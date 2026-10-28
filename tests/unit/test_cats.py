"""cats.json (catcolours.py and the cats section), without the game: a cat's look, other cats by name or place,
the save fields they set, and other cats' colours in the script."""
import pytest

from wcmods import catcolours as C
from wcmods import luacheck
from wcmods.sections import cats as section


def test_a_look_and_eye_slots_become_the_saves_fields():
    one = C.validate({"player": {"look": {"body": 6, "tail": 0, "pattern": 20, "size": 0.9}, "slots": {"eyes": 3}}})["player"]
    assert one["look"] == {"BodyValue": 6, "FurIdx": 6, "TailIdx": 0, "PatternIdx": 20, "CatSize": 0.9}
    assert one["slots"] == {"eye_left": 3, "eye_right": 3}
    assert C.fields_of(one) == {"EyeLeftColorIdx": 3, "EyeRightColorIdx": 3, "BodyValue": 6, "FurIdx": 6, "TailIdx": 0,
                                "PatternIdx": 20, "CatSize": 0.9}


@pytest.mark.parametrize("raw, message", [
    ({"player": {"look": {"body": 10}}}, "0 to 9"),
    ({"player": {"look": {"pattern": 21}}}, "0 to 20"),
    ({"player": {"look": {"tails": 1}}}, "takes body, fur, tail"),
    ({"player": {"look": {"size": 3}}}, "a scale from 0.05 to 1.5"),
    ({"player": {"look": {"ears": True}}}, "0 to 9"),
    ({"player": {"slots": {"eyes": 25}}}, "0-24"),
    ({"cats": {"player": {}}}, 'your own cat is "player"'),
    ({"cats": ["Bluestar"]}, "cats by name or place"),
    ({"cats": {"Bluestar": {"tail": 3}}}, '"look"'),
    ({"Bluestar": {}}, '"cats" for others'),
])
def test_looks_that_cant_be_used_are_refused(raw, message):
    with pytest.raises(ValueError, match=message):
        C.validate(raw)


def test_later_mods_win_part_by_part_and_cat_by_cat():
    a = C.validate({"player": {"look": {"body": 3, "tail": 4}}, "cats": {"Duskfang": {"look": {"fur": 1}, "slots": {"fur": 2}}}})
    b = C.validate({"player": {"look": {"body": 8}}, "cats": {"Duskfang": {"look": {"fur": 9}}, "Gustpaw": {"scars": "none"}}})
    merged = C.merge([a, b])
    assert merged["player"]["look"] == {"BodyValue": 8, "FurIdx": 8, "TailIdx": 4}
    assert merged["cats"]["Duskfang"]["look"] == {"FurValue": 9} and merged["cats"]["Duskfang"]["slots"] == {"fur": 2}
    assert merged["cats"]["Gustpaw"]["scars"] == {part: 0 for part in C.SCARS}


def test_fields_are_set_in_the_save_text_whole_numbers_and_sizes_alike():
    text = '(ClanType=WindClan,BodyValue=4,TailIdx=3,PrefixNameId="STR_CAT_NAME11",CatSize=0.450000)'
    out = C.set_fields(text, {"BodyValue": 9, "CatSize": 1.0, "MarkingIdx": 5})
    assert out == '(ClanType=WindClan,BodyValue=9,TailIdx=3,PrefixNameId="STR_CAT_NAME11",CatSize=1.000000,MarkingIdx=5)'
    assert C.set_fields(out, {"CatSize": 0.5}).count("CatSize=0.500000") == 1


def test_other_cats_colours_go_in_the_script_by_their_name_ids():
    lua = C.script({}, others={"STR_CAT_NAME11|_FANG": {"nose": (0.0, 1.0, 0.0)}})
    assert not luacheck.check(lua) and "@OTHERS@" not in lua
    assert '["STR_CAT_NAME11|_FANG"] = {\n        ["Nose Color"] = { 0.00000, 1.00000, 0.00000 },\n    },' in lua
    mine = C.script({"fur": (1.0, 0.0, 0.0)}, "A|B")
    assert not luacheck.check(mine) and "local OTHERS = {\n\n}" in mine


# ------------------------------------------------------------------------------------------- the section
CATS = [{"paths": ["5/GameplayProgression/Gameplay.Combat.Character.Cat.Player/Customization"], "player": True,
         "current": True, "slot": "5", "ids": {"PrefixNameId": "STR_CAT_NAME38", "SuffixNameId": "_PAW"}},
        {"paths": ["5/NPCData/Clans/WindClan/Deputy/0", "5/NPCData/NarrativeRoles/TheDeputy"], "player": False,
         "current": True, "slot": "5", "ids": {"PrefixNameId": "STR_CAT_NAME11", "SuffixNameId": "_FANG", "Role": "Deputy"}},
        {"paths": ["5/NPCData/Clans/WindClan/Warrior/1"], "player": False, "current": True, "slot": "5",
         "ids": {"PrefixNameId": "STR_CAT_NAME12", "SuffixNameId": "_LEAF"}},
        {"paths": ["5/NPCData/Clans/WindClan/Warrior/2"], "player": False, "current": True, "slot": "5",
         "ids": {"PrefixNameId": "STR_CAT_NAME12", "SuffixNameId": "_LEAF"}},
        {"paths": ["2/NPCData/Clans/WindClan/Apprentice/0"], "player": False, "current": False, "slot": "2",
         "ids": {"PrefixNameId": "STR_CAT_NAME13", "SuffixNameId": "_PAW"}}]
NAMES = {"STR_CAT_NAME38_PAW": "Fennelpaw", "STR_CAT_NAME11_FANG": "Duskfang", "STR_CAT_NAME12_LEAF": "Hawkleaf",
         "STR_CAT_NAME13_PAW": "Gustpaw"}


class FakePlan:
    renames = []

    def __init__(self, game, spec):
        pass

    def cats_called(self, target, cats):
        slot, want = (target.split("/", 1) if target.split("/", 1)[0].isdigit() else (None, target))
        if "/" in want:
            hits = [c for c in cats if any(p.endswith("/" + want) for p in c["paths"])]
        else:
            hits = [c for c in cats if NAMES.get(c["ids"]["PrefixNameId"] + c["ids"]["SuffixNameId"], "").lower() == want.lower()]
        return [c for c in hits if slot is None or c["slot"] == slot]


class Ctx:
    def __init__(self, tmp):
        self.cfg = type("Cfg", (), {"save_dir": str(tmp), "ue4ss_mods_dir": str(tmp), "data": {}})()
        self.mods, self.ops, self.warnings, self.notes, self.scripts = [], [], [], {}, {}
        self.game = type("Game", (), {"read_text": staticmethod(lambda path: "")})()

    def data_path(self, name):
        return name

    def save_op(self, op):
        self.ops.append(op)

    def warn(self, text):
        self.warnings.append(text)

    def note(self, key, value):
        self.notes[key] = value

    def add_ue4ss_mod(self, name, files):
        self.scripts[name] = files


def test_other_cats_are_found_by_name_or_place_and_get_their_own_fields_and_colours(tmp_path, monkeypatch):
    (tmp_path / "WrcGame.sav").write_bytes(b"")
    monkeypatch.setattr(section, "SAV_NAME", "WrcGame.sav")
    monkeypatch.setattr(section.SaveGame, "load", staticmethod(lambda path: type("S", (), {"json_text": "{}"})()))
    monkeypatch.setattr(section, "SaveDoc", lambda text: type("D", (), {"data": {}})())
    monkeypatch.setattr(section.names, "cats_in_save", lambda data: CATS)
    monkeypatch.setattr(section.names, "Plan", FakePlan)
    monkeypatch.setattr(section.names, "GameNames", lambda read: None)
    mod = type("Mod", (), {"id": "m", "folder": str(tmp_path)})()
    raw = {"player": {"look": {"ears": 9}},
           "cats": {"Duskfang": {"look": {"tail": 9}, "colours": {"nose": "#00ff00"}},
                    "Hawkleaf": {"scars": "none"}, "WindClan/Warrior/2": {"slots": {"fur": 0}}, "Nobody": {"look": {"fur": 1}}}}
    (tmp_path / "cats.json").write_text("{}")
    ctx = Ctx(tmp_path)
    section.CatsSection().build(ctx, [(mod, C.validate(raw))])
    by_path = {op["path"]: op for op in ctx.ops}
    assert by_path[CATS[0]["paths"][0]]["set"] == {"EarIdx": 9} and by_path[CATS[0]["paths"][0]]["who"] == "your cat"
    for path in CATS[1]["paths"]:                         # every copy of Duskfang
        assert by_path[path]["set"] == {"TailIdx": 9}
    assert by_path["5/NPCData/Clans/WindClan/Warrior/1"]["set"] == {f: 0 for f in C.SCARS.values()}
    # Found by its name and by its place: one edit with both.
    assert by_path["5/NPCData/Clans/WindClan/Warrior/2"]["set"] == {f: 0 for f in C.SCARS.values()} | {"FurColorIdx": 0}
    assert sum(op["path"] == "5/NPCData/Clans/WindClan/Warrior/2" for op in ctx.ops) == 1
    assert any("2 cats are called 'Hawkleaf'" in w for w in ctx.warnings)
    assert any("no cat in your save is called 'Nobody'" in w for w in ctx.warnings)
    script = ctx.scripts[C.UE4SS_MOD_NAME]["Scripts/main.lua"]
    assert '["STR_CAT_NAME11|_FANG"]' in script and not luacheck.check(script)


def build(tmp_path, monkeypatch, *mods):
    (tmp_path / "WrcGame.sav").write_bytes(b"")
    (tmp_path / "cats.json").write_text("{}")
    monkeypatch.setattr(section, "SAV_NAME", "WrcGame.sav")
    monkeypatch.setattr(section.SaveGame, "load", staticmethod(lambda path: type("S", (), {"json_text": "{}"})()))
    monkeypatch.setattr(section, "SaveDoc", lambda text: type("D", (), {"data": {}})())
    monkeypatch.setattr(section.names, "cats_in_save", lambda data: CATS)
    monkeypatch.setattr(section.names, "Plan", FakePlan)
    monkeypatch.setattr(section.names, "GameNames", lambda read: None)
    ctx = Ctx(tmp_path)
    section.CatsSection().build(ctx, [(type("Mod", (), {"id": f"m{i}", "folder": str(tmp_path)})(), C.validate(raw))
                                      for i, raw in enumerate(mods)])
    return ctx


def test_a_name_means_the_game_being_played_and_a_slot_first_another(tmp_path, monkeypatch):
    ctx = build(tmp_path, monkeypatch, {"cats": {"Gustpaw": {"look": {"tail": 1}}}})
    assert not ctx.ops and ctx.warnings == ["cats: 'Gustpaw' isn't in the game you're playing; for game 2's, put its "
                                            "slot first ('2/Gustpaw')"]
    ctx = build(tmp_path, monkeypatch, {"cats": {"2/Gustpaw": {"look": {"tail": 1}, "colours": {"nose": "#000000"}}}})
    assert [op["path"] for op in ctx.ops] == ["2/NPCData/Clans/WindClan/Apprentice/0"]
    # Colours go on only in the game being played: the script can't tell games apart.
    assert any("colours go on only in the game being played" in w for w in ctx.warnings)
    assert C.UE4SS_MOD_NAME not in ctx.scripts


def test_two_cats_with_one_name_share_its_colours_with_a_warning(tmp_path, monkeypatch):
    ctx = build(tmp_path, monkeypatch, {"cats": {"WindClan/Warrior/1": {"colours": {"nose": "#000000"}}}})
    assert any("its colours go on every cat with its name (2 in this game)" in w for w in ctx.warnings)


def test_a_later_mod_wins_whichever_way_it_names_the_cat(tmp_path, monkeypatch):
    ctx = build(tmp_path, monkeypatch, {"cats": {"Duskfang": {"look": {"tail": 1}}, "WindClan/Deputy/0": {"look": {"tail": 2}}}},
                {"cats": {"Duskfang": {"look": {"tail": 3}}}})
    sets = {op["path"]: op["set"] for op in ctx.ops}
    assert sets["5/NPCData/Clans/WindClan/Deputy/0"] == {"TailIdx": 3}
