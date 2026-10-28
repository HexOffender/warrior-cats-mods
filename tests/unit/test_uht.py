"""tools/re/uht.py's enum reading, without the game's exe: a small stand-in image holding enum tables laid out as
UHT writes them ({const char* name, int64 value} pairs, the names "<Enum>::<Name>"), and the check of wcmods' Lua
against an exe (`uht.py <exe> lua`): every Game.enums list and every enum number the Lua keeps in a constant. The
game's own exe was checked with it by hand (docs/reverse-engineering.md, "The game's enums")."""
import importlib.util
import os
import struct
from types import SimpleNamespace

from unit_helpers import REPO

_spec = importlib.util.spec_from_file_location("uht", os.path.join(REPO, "tools", "re", "uht.py"))
uht = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uht)

BASE, RVA = 0x140000000, 0x1000


def image(enums, extra_strings=(), params=(), plain=(), decoys=()):
    """An exe-like image: each enum {name: [(member, value), ...]} as its strings and then its table, with a
    zero entry before and after each table as the exe has between its tables. The members of an enum in `plain`
    are written without "<name>::" in front, as a plain enum's are; an enum in `params` also gets UHT's
    parameters for it (FEnumParams: OuterFunc, DisplayNameFunc, NameUTF8, CppTypeUTF8, the table, then the
    flags, the count and the C++ form, 0 for a plain enum and 2 for an enum class). A name in `decoys` is also
    pointed at from somewhere that isn't an enum's parameters."""
    data = bytearray(16)

    def string(text):
        at = len(data)
        data.extend(text.encode() + b"\0")
        return BASE + RVA + at

    for text in extra_strings:
        string(text)
    tables = {}
    for name, members in enums.items():
        pointers = [(string(m if name in plain else f"{name}::{m}"), v) for m, v in members]
        data.extend(bytes(-len(data) % 8) + bytes(16))
        tables[name] = BASE + RVA + len(data)
        for p, v in pointers:
            data.extend(struct.pack("<Qq", p, v))
        data.extend(bytes(16))
    names = {}
    for name in list(params) + list(decoys):
        if name not in names:
            names[name] = string(name)
    data.extend(bytes(-len(data) % 8))
    for name in decoys:
        data.extend(struct.pack("<QQQQQQ", 0, 0, names[name], 0x7, 0, 0))
    for name in params:
        data.extend(struct.pack("<QQQQQIhBB", BASE + RVA, 0, names[name], names[name], tables[name], 0x45,
                                len(enums[name]), 0, 0 if name in plain else 2))
    raw = bytes(data)
    return uht.Exe(image=SimpleNamespace(raw=raw, image_base=BASE,
                                         sections=[SimpleNamespace(rva=RVA, vsize=len(raw), raw=0, rawsize=len(raw))])), tables


def test_enum_table_gives_the_names_values_and_where_the_table_is():
    exe, tables = image({"ECommands": [("NoCommand", 0), ("Player_Mouse_Camera_Up", 64), ("Player_Interact", 67)],
                         "EOther": [("A", 0)]})
    first, table = uht.enum_table(exe, "ECommands")
    assert first == tables["ECommands"]
    assert table == [("ECommands::NoCommand", 0), ("ECommands::Player_Mouse_Camera_Up", 64), ("ECommands::Player_Interact", 67)]
    assert uht.enum_values(exe, "ECommands") == {"NoCommand": 0, "Player_Mouse_Camera_Up": 64, "Player_Interact": 67}
    assert list(uht.enum_values(exe, "ECommands")) == ["NoCommand", "Player_Mouse_Camera_Up", "Player_Interact"]
    assert uht.enum_table(exe, "EMissing") == (None, []) and uht.enum_values(exe, "EMissing") == {}


def test_enum_table_passes_over_a_longer_name_ending_the_same():
    # "XEFoo::A" holds "EFoo::A" but isn't it: only a pointer to the whole string counts.
    exe, tables = image({"EFoo": [("A", 0), ("B", 1)]}, extra_strings=["XEFoo::A"])
    assert uht.enum_table(exe, "EFoo") == (tables["EFoo"], [("EFoo::A", 0), ("EFoo::B", 1)])


def test_a_plain_enum_is_found_through_its_uht_parameters():
    # A plain enum's names have no "<Enum>::" (EInputEvent's IE_Pressed), so only its parameters name it.
    exe, tables = image({"EInputEvent": [("IE_Pressed", 0), ("IE_Released", 1), ("IE_MAX", 5)],
                         "ECommands": [("NoCommand", 0), ("Player_Interact", 67)]},
                        params=["EInputEvent", "ECommands"], plain=["EInputEvent"])
    (at, table, count, form), = uht.enum_params(exe, "EInputEvent")
    assert table == tables["EInputEvent"] and count == 3 and uht.CPP_FORMS[form] == "a plain enum"
    assert uht.enum_table(exe, "EInputEvent") == (tables["EInputEvent"],
                                                  [("IE_Pressed", 0), ("IE_Released", 1), ("IE_MAX", 5)])
    assert uht.enum_values(exe, "EInputEvent") == {"IE_Pressed": 0, "IE_Released": 1, "IE_MAX": 5}
    # An enum class found this way gives the same as its names' prefix.
    assert uht.CPP_FORMS[uht.enum_params(exe, "ECommands")[0][3]] == "an enum class"
    assert uht.enum_values(exe, "ECommands") == {"NoCommand": 0, "Player_Interact": 67}
    # Without parameters, a plain enum isn't found (nothing names it).
    bare, _ = image({"EInputEvent": [("IE_Pressed", 0)]}, plain=["EInputEvent"])
    assert uht.enum_table(bare, "EInputEvent") == (None, [])


def test_a_pointer_to_the_name_that_isnt_its_parameters_is_passed_over():
    # The name is pointed at from elsewhere too (a property's type, say): only a pointer followed by the C++ type's
    # name, a table, a count and a form counts.
    exe, tables = image({"EFoo": [("A", 0), ("B", 1)]}, params=["EFoo"], decoys=["EFoo"])
    params = uht.enum_params(exe, "EFoo")
    assert [(t, c) for _, t, c, _ in params] == [(tables["EFoo"], 2)]
    assert uht.enum_params(exe, "EMissing") == []


def test_lua_constants_reads_both_comment_forms():
    text = ("local INTERACT_COMMAND = 67   -- ECommands::Player_Interact in build 26184573, when it can't be read\n"
            "local SHOWN, COLLAPSED = 4, 1   -- ESlateVisibility: SelfHitTestInvisible, Collapsed\n"
            "local GARBAGE = 0x00200000   -- EInternalObjectFlags::Garbage\n"
            "local A, B = 0, 1   -- ESlateVisibility\n"            # no names: nothing to check it by
            "local C = 2\n-- ESlateVisibility::Hidden\n")      # a comment on its own line isn't the number's
    assert uht.lua_constants(text) == [
        ("ECommands", "Player_Interact", 67, 1), ("EInternalObjectFlags", "Garbage", 0x200000, 3),
        ("ESlateVisibility", "SelfHitTestInvisible", 4, 2), ("ESlateVisibility", "Collapsed", 1, 2)]


def test_lua_constants_takes_hex_and_reports_a_line_that_doesnt_pair_up():
    text = ("local A, B = 0x1, 0x10   -- EFoo: One, Sixteen\n"
            "local C = 2   -- EFoo: Two\n"                               # one constant, written the second way
            "local D, E, F = 0, 1, 2   -- EFoo: Zero, One\n"             # three numbers, two names
            "local G, H = 0, 1   -- EFoo: Zero, One, Two\n")
    assert uht.lua_constants(text) == [("EFoo", "One", 1, 1), ("EFoo", "Sixteen", 16, 1), ("EFoo", "Two", 2, 2),
                                       ("EFoo", "Zero, One", None, 3), ("EFoo", "Zero, One, Two", None, 4)]
    exe, _ = image({"EFoo": [("Zero", 0), ("One", 1), ("Two", 2), ("Sixteen", 16)]})
    results = uht.check_lua(exe, [], {"x.lua": text})
    got = {what: (ok, note) for what, ok, note in results}
    assert got["x.lua:1 EFoo::Sixteen = 16"] == (True, "the exe has 16") and got["x.lua:2 EFoo::Two = 2"][0] is True
    # Counted as a failure, not left out of the "N of N match".
    assert got["x.lua:3 EFoo: Zero, One"] == (
        False, "the comment's names and the line's numbers don't pair up, so none of them is checked")
    assert got["x.lua:4 EFoo: Zero, One, Two"][0] is False and len(results) == 5


def test_check_lua_compares_the_lists_and_the_constants():
    exe, _ = image({"EFoo": [("A", 0), ("B", 1), ("C", 5)], "EBar": [("X", 0), ("Y", 1)]})
    enums = [("foo", "/Script/M.EFoo", ["A", "B", "C"]), ("bar", "/Script/M.EBar", ["X", "Y"]),
             ("gone", "/Script/M.EGone", ["Q"])]
    sources = {"x.lua": "local C_ = 5   -- EFoo::C\nlocal P, Q = 0, 1   -- EBar: X, Y\nlocal Z = 3   -- EFoo::Z\n"
                        "local B_ = 2   -- EFoo::B\nlocal G = 0x10   -- ENope::G\n"}
    got = {what: (ok, note) for what, ok, note in uht.check_lua(exe, enums, sources)}
    assert got["Game.enums.foo (EFoo)"] == (False, "C 2 -> 5")
    assert got["Game.enums.bar (EBar)"] == (True, "2 names")
    assert got["Game.enums.gone (EGone)"] == (False, "no enum table in the exe")
    assert got["x.lua:1 EFoo::C = 5"] == (True, "the exe has 5")
    assert got["x.lua:2 EBar::X = 0"][0] is True and got["x.lua:2 EBar::Y = 1"][0] is True
    assert got["x.lua:3 EFoo::Z = 3"] == (False, "the exe's EFoo has no Z")
    assert got["x.lua:4 EFoo::B = 2"] == (False, "the exe has 1")
    assert got["x.lua:5 ENope::G = 16"][0] is None   # not reflected: not checked, not a failure


def test_check_lua_finds_a_name_the_game_added_or_dropped():
    exe, _ = image({"EFoo": [("A", 0), ("New", 1), ("B", 2)]})
    (what, ok, note), = uht.check_lua(exe, [("foo", "/Script/M.EFoo", ["A", "B", "Old"])], {})
    assert what == "Game.enums.foo (EFoo)" and not ok and note == "B 1 -> 2, Old gone, New 1 new"


def test_the_lua_keeps_its_game_enum_numbers_where_the_check_reads_them():
    # The fallbacks for the game's own enums are written so `uht.py <exe> lua` checks them after a game update,
    # the agent's Lua (in a Python string) too.
    sources = uht.lua_sources()
    game = uht.lua_constants(sources["wcmods/lua/game.lua"])
    remap = uht.lua_constants(sources["wcmods/lua/remap.lua"])
    agent = uht.lua_constants(sources["wcmods/agent/controller.py"])
    assert ("ECommands", "Player_Interact", 67) in [c[:3] for c in game]
    assert {("ECommands", "NoCommand", 0), ("EGuiConsolesTypes", "UI_PC", 1)} <= {c[:3] for c in remap}
    assert ("ECommands", "Button_Confirm", 26) in [c[:3] for c in agent]
    # Unreal's own numbers are named the same way, so the check covers them too.
    assert {("ECollisionEnabled", "NoCollision", 0), ("ESpawnActorCollisionHandlingMethod", "AlwaysSpawn", 1),
            ("ESpawnActorScaleMethod", "OverrideRootScale", 0), ("EUMGSequencePlayMode", "Forward", 0),
            ("ETextJustify", "Center", 1), ("ESlateVisibility", "Hidden", 2)} <= {c[:3] for c in game}
    assert ("EInputEvent", "IE_Pressed", 0) in [c[:3] for c in remap]
    # No line anywhere names its values in a way the check can't pair up.
    assert not [(f, c) for f, text in sources.items() for c in uht.lua_constants(text) if c[2] is None]
