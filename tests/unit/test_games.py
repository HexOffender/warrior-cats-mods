"""The games in a save (wcmods/games.py) and the pages that choose one: the games list on a save with several games
(two cats with one name, a sandbox game, a slot with no cat of yours, sandbox.json missing or broken), GET /save's
and GET /cat's "games", a Save page change for a chosen game made in that game only, and cats.json's "4/player",
which changes that game's cat only (sections/cats.py over a temp save). No game: the cats' names come from a
stand-in for the studio's cat namer."""
import json
import os

import pytest

from wcmods import catcolours, games, luacheck, names, pipeline
from wcmods.formats.save import SAV_NAME, SaveGame
from wcmods.formats.savejson import SaveDoc
from wcmods.names import Plan as RealPlan
from wcmods.sections import cats as cats_section
from wcmods.sections import savedit

from unit_helpers import GAMES_NAMES, games_save, write_save


def call(st, method, path, body=None):
    return st.api(method, [p for p in path.split("/") if p], dict(body or {}), None)


def shown(cat):
    """The studio's cat namer, standing in: the name a cat shows, by its prefix ID."""
    return GAMES_NAMES.get(cat["ids"].get("PrefixNameId"), "")


def doc(folder):
    return SaveDoc(SaveGame.load(os.path.join(folder, SAV_NAME)).json_text)


def sandbox_json(studio, content):
    """sandbox.json where Sandbox mode keeps it: the scripts' folder beside the saves (pipeline.saved_folder)."""
    folder = pipeline.saved_folder(studio.ctx.cfg)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, games.SANDBOX_FILE), "w", encoding="utf-8") as f:
        f.write(content if isinstance(content, str) else json.dumps(content))


SANDBOX = {"_help": "The sandbox cats, by save slot (0 is the first).",
           "cats": [{"slot": 4, "clan": "ThunderClan", "prefix": "STR_CAT_NAME6", "made": "2026-10-27T10:00:00Z"}]}


# ---------- the list ----------
def test_each_game_with_a_cat_of_yours_in_the_games_order_numbered_as_the_cat_choice_numbers_them():
    data = games_save()["acct"]
    got = games.in_save(data, shown, SANDBOX["cats"])
    assert got == [
        {"slot": "0", "n": 1, "name": "Sharppaw", "clan": "ThunderClan", "rank": "Apprentice", "level": 3,
         "sandbox": False, "current": False},
        {"slot": "2", "n": 3, "name": "Mothwing", "clan": "RiverClan", "rank": "MedicineCat", "level": 7,
         "sandbox": False, "current": False},
        {"slot": "4", "n": 5, "name": "Sharppaw", "clan": "ThunderClan", "rank": "Apprentice", "level": 1,
         "sandbox": True, "current": True}]
    # Slot 1 has clan cats but no cat of yours, and slot 3 nothing: neither is a game to pick.
    assert "1" not in {g["slot"] for g in got} and "3" not in {g["slot"] for g in got}
    # Without a namer (no game folder) the names are None, never a place or an ID.
    assert [g["name"] for g in games.in_save(data)] == [None, None, None]
    # The game played last follows the save.
    assert [g["slot"] for g in games.in_save(games_save(current=2)["acct"]) if g["current"]] == ["2"]
    assert games.words("4") == names.game_words("4") == "your 5th game"


def test_a_sandbox_game_is_one_whose_cat_is_still_the_one_sandbox_mode_made_there():
    data = games_save()["acct"]

    def sandbox(entries):
        return [g["slot"] for g in games.in_save(data, None, entries) if g["sandbox"]]
    assert sandbox([{"slot": 4, "clan": "ThunderClan", "prefix": "STR_CAT_NAME6"}]) == ["4"]
    assert sandbox([{"slot": "2"}]) == ["2"], "an entry that says neither clan nor prefix"
    assert sandbox([{"slot": 4, "clan": "ThunderClan", "prefix": "STR_CAT_NAME1"}]) == [], "the slot was started again"
    assert sandbox([{"slot": 4, "clan": "WindClan"}]) == []
    assert sandbox([{"slot": True}, {"slot": -1}, {"slot": "four"}, {"slot": None}]) == []
    assert sandbox([]) == []


@pytest.mark.parametrize("content", [None, "", "{not json", "[]", '{"cats": {"slot": 4}}', '{"cats": [4, "x", null]}',
                                     "﻿" + json.dumps(SANDBOX)])
def test_a_missing_or_broken_sandbox_json_is_no_sandbox_games(tmp_path, content):
    if content is not None:
        (tmp_path / games.SANDBOX_FILE).write_text(content, encoding="utf-8")
    entries = games.sandbox_entries(str(tmp_path))
    if content and content.startswith("﻿"):
        assert entries == SANDBOX["cats"], "a byte-order mark is read past"
    else:
        assert entries == []
    assert games.sandbox_entries(None) == [] and games.sandbox_entries(str(tmp_path / "nowhere")) == []


# ---------- the routes ----------
@pytest.fixture
def several(studio, monkeypatch):
    """The studio over games_save, with the names its cats show, and Sandbox mode's sandbox.json beside the saves."""
    write_save(studio.ctx.cfg.save_dir, games_save())
    sandbox_json(studio, SANDBOX)
    monkeypatch.setattr(studio, "cat_namers", lambda: (shown, lambda c: [shown(c).lower()] if shown(c) else []))
    return studio


def test_get_save_lists_the_games_and_the_game_played_last(several):
    r = call(several, "GET", "save")
    assert [(g["slot"], g["n"], g["name"], g["level"], g["sandbox"], g["current"]) for g in r["games"]] == [
        ("0", 1, "Sharppaw", 3, False, False), ("2", 3, "Mothwing", 7, False, False), ("4", 5, "Sharppaw", 1, True, True)]
    assert r["current_cat"] == {"slot": "4", "name": "Sharppaw"}
    assert r["cats"] == {"0": "Sharppaw", "2": "Mothwing", "4": "Sharppaw"}


def test_get_save_with_sandbox_json_broken_still_lists_the_games(several):
    sandbox_json(several, "{ half written")
    assert [g["sandbox"] for g in call(several, "GET", "save")["games"]] == [False, False, False]


def test_get_cat_lists_the_games_with_what_each_cat_of_yours_has_now_and_every_games_cats(several):
    r = call(several, "GET", "cat")
    assert [(g["slot"], g["name"], g["current"]) for g in r["games"]] == [
        ("0", "Sharppaw", False), ("2", "Mothwing", False), ("4", "Sharppaw", True)]
    by_slot = {g["slot"]: g["look_now"] for g in r["games"]}
    assert by_slot["0"]["slots"]["fur"] == 3 and by_slot["0"]["look"]["tail"] == 1
    assert by_slot["4"]["slots"]["fur"] == 8 and by_slot["4"]["look"]["tail"] == 2
    assert by_slot["2"]["slots"]["fur"] == 5
    assert r["current"]["fur"] == 8, "your cat (\"player\") is the game played last's"
    # The other cats of every game, the game being played first, each by a key the build finds it by.
    assert [(c["slot"], c["target"], c["playing"]) for c in r["cats"]] == [
        ("4", "Dustfur", True), ("0", "0/Lionheart", False), ("1", "1/Gorseleaf", False)]


def test_the_names_page_heads_its_games_in_the_same_words():
    assert names.describe_target("4/player") == "your cat in your 5th game"
    assert savedit.label("0/GameplayProgression/Level", None, None, "4") == "your 1st game's cat's level"
    assert savedit.label("0/GameplayProgression/Level", {"0": "Sharppaw"}.get, None, "4") == "Sharppaw's level"


# ---------- the Save page: a change for the game chosen ----------
def test_change_my_save_now_for_a_chosen_game_changes_that_game_only(several):
    before = doc(several.ctx.cfg.save_dir)
    r = call(several, "POST", "save/apply", {"changes": [{"path": "0/GameplayProgression/Level", "value": 12}]})
    after = doc(several.ctx.cfg.save_dir)
    assert after.get("0/GameplayProgression/Level") == 12
    assert after.get("4/GameplayProgression/Level") == before.get("4/GameplayProgression/Level") == 1, \
        "the game played last, with a cat of the same name, is as it was"
    assert after.get("2/GameplayProgression/Level") == 7
    assert [(a["path"], a["was"], a["now"]) for a in r["applied"]] == [("0/GameplayProgression/Level", 3, 12)]
    # Done so far has it by its path: the page puts it under its game.
    (done,) = call(several, "GET", "save/applied")["changes"]
    assert done["path"] == "0/GameplayProgression/Level" and done["current"] == 12


def test_a_mods_save_json_for_a_game_goes_into_the_game_with_that_number(several, tmp_path):
    """A save.json made for sharing keeps its paths: a change to the 3rd game goes into the 3rd game of whoever adds it."""
    folder = tmp_path / "share"
    folder.mkdir()
    (folder / "save.json").write_text(json.dumps({"set": {"2/GameplayProgression/Level": 9}}))
    mod = type("Mod", (), {"id": "share", "folder": str(folder)})()
    section, ctx = savedit.SaveSection(), Ctx(several.ctx.cfg.save_dir, tmp_path)
    section.build(ctx, [(mod, section.collect(mod, ctx))])
    assert [(op["path"], op["value"]) for op in ctx.ops] == [("2/GameplayProgression/Level", 9)]
    pipeline.apply_save_ops(several.ctx.cfg, ctx.ops, several.ctx.backups, lambda line: None)
    d = doc(several.ctx.cfg.save_dir)
    assert d.get("2/GameplayProgression/Level") == 9
    assert d.get("0/GameplayProgression/Level") == 3 and d.get("4/GameplayProgression/Level") == 1


# ---------- cats.json: your cat in one game ----------
class SlotPlan:
    """names.Plan's own matcher (_targets) over the stand-in names: no game's name tables needed."""
    renames = []
    _targets, cats_called = RealPlan._targets, RealPlan.cats_called

    def __init__(self, game, spec):
        pass

    def _called(self, cat, name):
        return shown(cat).lower() == name.lower()


class Ctx:
    """What the cats section uses of a build: the save's folder, a scripts folder, and what it adds and says."""

    def __init__(self, save_dir, tmp):
        self.cfg = type("Cfg", (), {"save_dir": save_dir, "ue4ss_mods_dir": str(tmp), "data": {}})()
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


def build_cats(studio, tmp_path, monkeypatch, raw):
    monkeypatch.setattr(cats_section.names, "Plan", SlotPlan)
    monkeypatch.setattr(cats_section.names, "GameNames", lambda read: None)
    folder = tmp_path / "mod"
    folder.mkdir(exist_ok=True)
    (folder / "cats.json").write_text(json.dumps(raw))
    ctx = Ctx(studio.ctx.cfg.save_dir, tmp_path)
    mod = type("Mod", (), {"id": "looks", "folder": str(folder)})()
    cats_section.CatsSection().build(ctx, [(mod, catcolours.validate(raw))])
    return ctx


def test_cats_json_4_player_changes_that_games_cat_only(studio, tmp_path, monkeypatch):
    write_save(studio.ctx.cfg.save_dir, games_save(current=2))   # another game is being played
    ctx = build_cats(studio, tmp_path, monkeypatch, {"cats": {"4/player": {"look": {"tail": 5}, "slots": {"fur": 11}}}})
    assert [op["path"] for op in ctx.ops] == [f"4/{names.PLAYER_TAIL}"]
    assert ctx.ops[0]["who"] == "your cat in your 5th game" and ctx.ops[0]["set"] == {"TailIdx": 5, "FurColorIdx": 11}
    assert not ctx.warnings
    pipeline.apply_save_ops(studio.ctx.cfg, ctx.ops, studio.ctx.backups, lambda line: None)
    d = doc(studio.ctx.cfg.save_dir)
    assert "TailIdx=5" in d.get(f"4/{names.PLAYER_TAIL}") and "FurColorIdx=11" in d.get(f"4/{names.PLAYER_TAIL}")
    for other in ("0", "2"):   # your 1st game's Sharppaw too, though it has the same name
        assert "TailIdx=5" not in d.get(f"{other}/{names.PLAYER_TAIL}") and "FurColorIdx=11" not in d.get(f"{other}/{names.PLAYER_TAIL}")


def test_player_and_its_game_by_number_make_one_change_the_games_own_choices_winning(studio, tmp_path, monkeypatch):
    write_save(studio.ctx.cfg.save_dir, games_save(current=4))
    ctx = build_cats(studio, tmp_path, monkeypatch, {"player": {"look": {"tail": 3, "ears": 4}},
                                                    "cats": {"4/player": {"look": {"tail": 6}}}})
    assert [(op["path"], op["set"]) for op in ctx.ops] == [(f"4/{names.PLAYER_TAIL}", {"TailIdx": 6, "EarIdx": 4})]


def test_colours_for_your_cat_in_one_game_go_on_by_its_name_and_a_game_sharing_it_is_said(studio, tmp_path, monkeypatch):
    write_save(studio.ctx.cfg.save_dir, games_save(current=2))
    ctx = build_cats(studio, tmp_path, monkeypatch, {"player": {"colours": {"ears": "#0000ff"}},
                                                    "cats": {"4/player": {"colours": {"nose": "#ff0000"}}}})
    script = ctx.scripts[catcolours.UE4SS_MOD_NAME]["Scripts/main.lua"]
    assert not luacheck.check(script) and "@YOURS@" not in script
    yours = script.split("local YOURS = {", 1)[1].split("\n}", 1)[0]
    # Game 4's Sharppaw, by its name IDs, with that game's own colours only: the player's stay in COLOURS, which
    # the script lays them over as it paints (so the in-game Colours page, which changes COLOURS, still works).
    assert '["STR_CAT_NAME6|_PAW"] = {' in yours and '["Nose Color"]' in yours and '["Ears Color"]' not in yours
    assert '["Ears Color"]' in script.split("local COLOURS = {", 1)[1].split("\n}", 1)[0]
    assert any("its colours go on your cat in your 1st game too, which has the very same name" in w for w in ctx.warnings)
    assert not ctx.ops, "colours only: nothing goes into the save"


def test_colours_for_one_game_name_every_game_sharing_its_cats_name_in_one_sentence(studio, tmp_path, monkeypatch):
    save = games_save(current=2)
    save["acct"]["3"] = json.loads(json.dumps(save["acct"]["0"]))   # a third Sharppaw, in your 4th game
    write_save(studio.ctx.cfg.save_dir, save)
    ctx = build_cats(studio, tmp_path, monkeypatch, {"cats": {"4/player": {"colours": {"nose": "#ff0000"}}}})
    assert ctx.warnings == ["your cat in your 5th game: its colours go on your cats in your 1st game and your 4th game "
                            "too, which have the very same name: the game tells cats apart only by their names"]


def test_a_game_with_no_cat_of_yours_is_said_and_nothing_changes(studio, tmp_path, monkeypatch):
    write_save(studio.ctx.cfg.save_dir, games_save())
    ctx = build_cats(studio, tmp_path, monkeypatch, {"cats": {"1/player": {"look": {"tail": 5}}}})
    assert not ctx.ops
    assert ctx.warnings == ["your cat in your 2nd game ('1/player'): your save has no cat of yours in that game"]


def test_a_games_own_colours_go_over_the_live_player_colours_so_the_colours_page_still_works():
    # The mod menu's Colours page changes COLOURS while you play: your cat in a game with colours of its own
    # wears COLOURS with that game's over them, made as it's painted, never a table fixed at install.
    lua = catcolours.script({"fur": (1.0, 0.0, 0.0)}, "A|B", yours={"C|D": {"nose": (0.0, 1.0, 0.0)}})
    over = lua.split("local function over(own)", 1)[1].split("\nend", 1)[0]
    assert over.index("pairs(COLOURS)") < over.index("pairs(own)"), "the game's own colours win where both set a part"
    tick = lua.split("local function tick()", 1)[1].split("\nend\n", 1)[0]
    assert "cols, who = over(YOURS[key])" in tick and "YOURS[key], " not in tick
    page = lua.split('Menu.page("Colours"', 1)[1]
    assert "if YOURS[known] then" in page and "colours of its own in cats.json too, and those win where both" in page


def test_the_script_takes_your_cat_by_game_beside_the_others():
    lua = catcolours.script({"fur": (1.0, 0.0, 0.0)}, "A|B", yours={"C|D": {"nose": (0.0, 1.0, 0.0), "fur": (1.0, 0.0, 0.0)}})
    assert not luacheck.check(lua)
    assert 'local YOURS = {\n    ["C|D"] = {\n        ["Fur Color"]' in lua
    assert "local YOURS = {\n\n}" in catcolours.script({}, "A|B")
