"""The build section for cats and questlines (sections/story.py) over a build context with no game: the one
script it writes, what it warns about (items nobody has, colour slots no palette adds, a Sandbox mode that's
missing, off, kept out or too old for a fixed look), the objectives it fills in at Apply, and its notes."""
import json
import os
from types import SimpleNamespace

import pytest

from wcmods import luacheck, story
from wcmods import mods as modlib
from wcmods.sdk import BuildContext
from wcmods.sections.story import StorySection, UE4SS_NAME

MOSS = "Gameplay.Inventory.Materials.Moss"
HERB = "Gameplay.Inventory.Consumable.SmallHealingHerb"
# The game's own rows, as the cooked table gives them: a tag, its name (a key in the game's strings) and icon.
GAME_ROWS = [("Moss", {"itemTag": MOSS, "Name": {"ns": "", "key": "STR_ITEM_MOSS", "text": "moss"},
                       "Icon": {"package": "/Game/UI/T_Moss", "asset": "T_Moss"}}),
             ("Herb", {"itemTag": HERB, "Name": {"ns": "", "key": "STR_ITEM_HERB"}, "Icon": None})]
TEXTS = {"STR_ITEM_MOSS": "Moss", "STR_ITEM_HERB": "Small Healing Herb"}


class Ctx(BuildContext):
    """A build context whose game is a few rows and strings: nothing is read from disk but the mods."""

    def __init__(self, tmp_path, found, allow_code=True, rows=GAME_ROWS, texts=TEXTS, held_back=None):
        super().__init__(SimpleNamespace(data={"allow_code_mods": allow_code}), None, str(tmp_path / "out"), log=lambda m: None)
        self.found, self.mods = list(found), [m for m in found if m.enabled and m.id not in (held_back or {})]
        self.held_back = dict(held_back or {})
        self.rows, self.texts = list(rows), dict(texts)
        self.begin("story")

    def cooked_table(self, name):
        assert name == "DT_QuestObjectsInfo"
        return self.rows

    def text(self, key, language="EN"):
        return self.texts.get(key, key)


def mod(tmp_path, mod_id, files=None, **meta):
    folder = tmp_path / "mods" / mod_id
    folder.mkdir(parents=True)
    (folder / "mod.json").write_text(json.dumps({"name": mod_id.replace("-", " ").title(), "enabled": True, **meta}),
                                     encoding="utf-8")
    for name, value in (files or {}).items():
        (folder / name).write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
    return modlib.Mod(str(folder))


CATS = {"npcs": [{"id": "mossfoot", "name": "Mossfoot", "lines": ["Hello."]}]}
QUESTS = {"quests": [{"id": "moss", "title": "Moss for Mossfoot", "giver": "mossfoot", "steps": [
    {"do": "talk", "lines": ["Bring me moss?"]},
    {"do": "collect", "item": MOSS, "count": 2},
    {"do": "visit", "place": "medicine-cat"},
    {"do": "visit", "at": [1, 2, 3]},
    {"do": "talk", "lines": ["Thank you!"], "objective": "Take the moss back"}],
    "reward": {HERB: 1}}]}


def build(tmp_path, mods, **kw):
    """Collect every mod as the pipeline does, then build: the context, after."""
    ctx = Ctx(tmp_path, mods, **kw)
    sec = StorySection()
    items = [(m, data) for m in ctx.mods if sec.claims(m) for data in [sec.collect(m, ctx)] if data is not None]
    sec.build(ctx, items)
    return ctx


def shared(ctx):
    """The cats and questlines the game gets, out of the WCModsStory script."""
    lua = ctx.ue4ss_mods[UE4SS_NAME][0]["Scripts/main.lua"]
    lua = lua.decode("utf-8") if isinstance(lua, bytes) else lua
    assert not luacheck.check(lua)
    # lua_value escapes a string as JSON does (\" \\ \n), and the JSON text has no other control characters.
    return json.loads(json.loads(lua.split("local STORY = ", 1)[1].split("\nlocal ok", 1)[0]))


def sandbox(tmp_path, version="0.5", enabled=True):
    return mod(tmp_path, "sandbox", name="Sandbox mode", version=version, enabled=enabled)


def test_build_writes_one_script_for_every_mod(tmp_path):
    a = mod(tmp_path, "a-story", {"npcs.json": CATS, "quests.json": QUESTS})
    b = mod(tmp_path, "b-story", {"npcs.json": {"npcs": [{"id": "sparrowpaw", "name": "Sparrowpaw"}]}})
    ctx = build(tmp_path, [a, b, sandbox(tmp_path)])
    assert list(ctx.ue4ss_mods) == [UE4SS_NAME]
    data = shared(ctx)
    assert data["format"] == story.FORMAT and [m["id"] for m in data["mods"]] == ["a-story", "b-story"]
    assert ctx.notes["story"]["story"] == {"a-story": {"npcs": ["mossfoot"], "quests": ["moss"]},
                                           "b-story": {"npcs": ["sparrowpaw"], "quests": []}}
    assert ctx.warnings == []


def test_an_empty_file_collects_nothing(tmp_path):
    m = mod(tmp_path, "empty", {"npcs.json": {"npcs": []}, "quests.json": {"quests": []}})
    assert StorySection().collect(m, Ctx(tmp_path, [m])) is None
    ctx = build(tmp_path, [m])
    assert ctx.ue4ss_mods == {} and ctx.warnings == []


def test_an_unknown_item_warns_once_per_tag(tmp_path):
    quests = json.loads(json.dumps(QUESTS))
    gone = "Gameplay.Inventory.Materials.Moonpetal"
    quests["quests"][0]["steps"][1]["item"] = gone
    quests["quests"][0]["reward"] = {gone: 1}
    ctx = build(tmp_path, [mod(tmp_path, "mine", {"npcs.json": CATS, "quests.json": quests}), sandbox(tmp_path)])
    assert ctx.warnings == [f"story: mine: quests.json names the item {gone}, which the game hasn't got (and no mod adds)"]


def test_a_mods_own_item_doesnt_warn(tmp_path):
    own = "Gameplay.Inventory.Materials.moonpetal"
    quests = json.loads(json.dumps(QUESTS))
    quests["quests"][0]["steps"][1]["item"] = own
    m = mod(tmp_path, "mine", {"npcs.json": CATS, "quests.json": quests})
    ctx = Ctx(tmp_path, [m, sandbox(tmp_path)])
    ctx.notes["items"] = {"items": [own]}   # the items section, which comes first, made it
    ctx.table_rows["DT_QuestObjectsInfo"] = [("mine_moonpetal", {"itemTag": own, "Name": {"ns": "WCMods", "key": "x", "text": "Moonpetal"}},
                                              "items", "mine")]
    sec = StorySection()
    sec.build(ctx, [(m, sec.collect(m, ctx))])
    assert ctx.warnings == []
    assert shared(ctx)["mods"][0]["quests"][0]["steps"][1]["objective"] == "Find 2 Moonpetal"


def test_icons_come_from_the_cooked_table_and_mod_rows(tmp_path):
    own = "Gameplay.Inventory.Consumable.mint"
    quests = json.loads(json.dumps(QUESTS))
    quests["quests"][0]["reward"] = {own: 1}
    m = mod(tmp_path, "mine", {"npcs.json": CATS, "quests.json": quests})
    ctx = Ctx(tmp_path, [m, sandbox(tmp_path)])
    ctx.table_rows["DT_QuestObjectsInfo"] = [("mine_mint", {"itemTag": own, "Icon": {"package": "/Game/WCMods/T_Mint", "asset": "T_Mint"}},
                                              "items", "mine")]
    sec = StorySection()
    sec.build(ctx, [(m, sec.collect(m, ctx))])
    assert shared(ctx)["icons"] == {MOSS: "/Game/UI/T_Moss.T_Moss", own: "/Game/WCMods/T_Mint.T_Mint"}


def test_a_palette_slot_nobody_adds_warns(tmp_path):
    cats = {"npcs": [{"id": "mossfoot", "name": "Mossfoot", "slots": {"fur": 3, "pattern": 27, "marking": 30}}]}
    off = mod(tmp_path, "colours", {"palette.json": {"pattern": {"27": "#ff0000"}, "marking": {"30": "#00ff00"}}}, enabled=False)
    ctx = build(tmp_path, [mod(tmp_path, "mine", {"npcs.json": cats}), off, sandbox(tmp_path)])
    assert ctx.warnings == [
        "story: mine: Mossfoot wears pattern colour 27, which no palette that's on adds, so it shows no colour there",
        "story: mine: Mossfoot wears markings colour 30, which no palette that's on adds, so it shows no colour there"]


def test_a_palette_slot_a_palette_adds_is_quiet(tmp_path):
    cats = {"npcs": [{"id": "mossfoot", "name": "Mossfoot", "slots": {"pattern": 27, "marking": 4}}]}
    on = mod(tmp_path, "colours", {"palette.json": {"pattern": {"27": "#ff0000"}}})
    ctx = build(tmp_path, [mod(tmp_path, "mine", {"npcs.json": cats}), on, sandbox(tmp_path)])
    assert ctx.warnings == []


def test_broken_json_names_the_line_and_column(tmp_path):
    m = mod(tmp_path, "mine", {"npcs.json": '{"npcs": [\n  {"id": "a",}\n]}'})
    with pytest.raises(ValueError, match=r"npcs\.json: .* at line 2 column \d+"):
        StorySection().collect(m, Ctx(tmp_path, [m]))


@pytest.mark.parametrize("found, allow, state", [
    (lambda t: [sandbox(t)], True, {"state": "on", "version": "0.5", "older": []}),
    (lambda t: [sandbox(t, enabled=False)], True, {"state": "off", "version": "0.5", "older": []}),
    (lambda t: [sandbox(t)], False, {"state": "no-code", "version": "0.5", "older": []}),
    (lambda t: [], True, {"state": "missing", "version": None, "older": []}),
    (lambda t: [sandbox(t, version="0.4")], True, {"state": "on", "version": "0.4", "older": ["look", "slots"]}),
    (lambda t: [sandbox(t, version="beta")], True, {"state": "on", "version": "beta", "older": ["look", "slots"]}),
])
def test_the_note_says_the_sandbox_state(tmp_path, found, allow, state):
    ctx = build(tmp_path, [mod(tmp_path, "mine", {"npcs.json": CATS})] + found(tmp_path), allow_code=allow)
    assert ctx.notes["story"]["sandbox"] == state


def test_build_warns_when_the_sandbox_is_too_old_for_fixed_looks(tmp_path):
    cats = {"npcs": [{"id": "mossfoot", "name": "Mossfoot", "look": {"body": 3}},
                     {"id": "sparrowpaw", "name": "Sparrowpaw"}]}
    ctx = build(tmp_path, [mod(tmp_path, "mine", {"npcs.json": cats}), sandbox(tmp_path, version="0.4")])
    assert ctx.warnings == ["story: mine: Mossfoot has a fixed look, which needs Sandbox mode 0.5 or newer; you have 0.4, "
                            "so the game makes the look up each time"]
    assert build(tmp_path / "new", [mod(tmp_path / "new", "mine", {"npcs.json": cats}), sandbox(tmp_path / "new")]).warnings == []


def test_build_warns_when_the_sandbox_is_missing(tmp_path):
    ctx = build(tmp_path, [mod(tmp_path, "mine", {"npcs.json": CATS})])
    assert len(ctx.warnings) == 1
    assert ctx.warnings[0].startswith("story: cats and questlines go in, but nothing shows them until Sandbox mode is "
                                      "added and on")
    off = build(tmp_path / "off", [mod(tmp_path / "off", "mine", {"npcs.json": CATS}), sandbox(tmp_path / "off", enabled=False)])
    assert "until Sandbox mode is on" in off.warnings[0]
    kept = build(tmp_path / "kept", [mod(tmp_path / "kept", "mine", {"npcs.json": CATS}), sandbox(tmp_path / "kept")], allow_code=False)
    assert "mods that run code aren't allowed" in kept.warnings[0]
    # The cats go in all the same.
    assert UE4SS_NAME in ctx.ue4ss_mods


def test_a_sandbox_held_back_after_a_game_update_shows_nothing_and_says_use_it_anyway(tmp_path):
    # On, but made for the game's build before the update: the build leaves it out until "Use it anyway".
    held = {"sandbox": "made for an older version of the game"}
    ctx = build(tmp_path, [mod(tmp_path, "mine", {"npcs.json": CATS}), sandbox(tmp_path)], held_back=held)
    assert ctx.notes["story"]["sandbox"] == {"state": "held-back", "version": "0.5", "older": []}
    assert ctx.warnings == ["story: cats and questlines go in, but nothing shows them: Sandbox mode is left out since "
                            "the game's update, as it was made for an older version of the game (on the Mods page, its "
                            "card has Use it anyway…)"]
    # Left out with a mod it needs: that mod's card has the button.
    need = {"sandbox": "needs Mod menu pages, made for an older version of the game"}
    other = build(tmp_path / "b", [mod(tmp_path / "b", "mine", {"npcs.json": CATS}), sandbox(tmp_path / "b")], held_back=need)
    assert other.warnings[0].endswith("Sandbox mode is left out since the game's update: it needs Mod menu pages, made for "
                                      "an older version of the game (on the Mods page, that mod's card has Use it anyway…)")
    # Off wins: turning it on comes first.
    off = build(tmp_path / "c", [mod(tmp_path / "c", "mine", {"npcs.json": CATS}), sandbox(tmp_path / "c", enabled=False)],
                held_back=held)
    assert off.notes["story"]["sandbox"]["state"] == "off"


def test_the_pipeline_tells_the_sections_what_a_game_update_holds_back(tmp_path, monkeypatch):
    from wcmods import pipeline
    from wcmods.cli import Ctx as CliCtx
    cli = CliCtx(str(tmp_path / "root"), str(tmp_path / "data"))
    seen = {}

    class Spy:   # stands in for the story section: what the build context says is held back
        id, title, owner = "story", "Characters and questlines", None

        def claims(self, mod):
            return True

        def collect(self, mod, c):
            return {}

        def build(self, c, items):
            seen.update(c.held_back)
    held = {"sandbox": "made for an older version of the game"}
    monkeypatch.setattr(pipeline, "load_sections", lambda cfg, mods, log: ([Spy()], []))
    monkeypatch.setattr(pipeline.gamebuild, "current", lambda cfg: {"build": None})
    monkeypatch.setattr(pipeline.gamebuild, "held_back", lambda cfg, mods, build=None, trusted=(): dict(held))
    monkeypatch.setattr(pipeline.gamebuild, "layout", lambda cfg, log=None: {"status": "verified", "moved": [], "lost": [], "offsets": {}})
    found = [mod(tmp_path, "mine", {"npcs.json": CATS}), sandbox(tmp_path)]
    try:
        pipeline.build(cli.cfg, found, str(tmp_path / "build"), log=lambda m: None)
    except Exception:   # noqa: BLE001 - past the sections, the build reads the game's files, which aren't here
        pass
    assert seen == held


def test_build_fills_in_objectives_from_todays_names(tmp_path):
    cats = {"npcs": [{"id": "mossfoot", "name": "Mossfoot the Elder"}]}   # renamed since the quest was made
    ctx = build(tmp_path, [mod(tmp_path, "mine", {"npcs.json": cats, "quests.json": QUESTS}), sandbox(tmp_path)])
    steps = shared(ctx)["mods"][0]["quests"][0]["steps"]
    assert [s["objective"] for s in steps] == ["Talk to Mossfoot the Elder", "Find 2 Moss", "Visit the nearest medicine cat",
                                               "Go to the marked place", "Take the moss back"]
    # One of the game's items no strings name: the tag's own words; one of one: no count.
    quests = json.loads(json.dumps(QUESTS))
    quests["quests"][0]["steps"][1].update(item="Gameplay.Inventory.Materials.OldTwig", count=1)
    ctx = build(tmp_path / "b", [mod(tmp_path / "b", "mine", {"npcs.json": cats, "quests.json": quests}), sandbox(tmp_path / "b")],
                rows=GAME_ROWS + [("Twig", {"itemTag": "Gameplay.Inventory.Materials.OldTwig", "Name": {"key": "STR_NOPE"}})])
    assert shared(ctx)["mods"][0]["quests"][0]["steps"][1]["objective"] == "Find Old Twig"
