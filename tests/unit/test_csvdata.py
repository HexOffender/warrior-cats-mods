"""wcmods/formats/csvdata.py: data.json's edits on the game's tables. One fixed order inside a file ("-", then
"*", then the named rows, then "+"), whatever order its keys are in; values in the cell's own style; and a
mistake in one edit said as a problem, never an exception and never the others' loss."""
from wcmods.formats import csvdata
from wcmods.formats.csvdata import Table, apply_edits, format_value

XP = "Enemy,BaseExperience,DifficultyOffset\r\nFish,10,0\r\nMice,25,0\r\nRat,60,0\r\n"
TUNING = "---,MaxValue,Description\r\nRun.Speed,390,How fast\r\nHetero.Chance,0.15,\r\nTag,Gameplay.X,\r\n"


def cell(text, row, col):
    t = Table(text)
    r = next(r for r in t.rows if r.fields[0] == row)
    return r.fields[t.column(col)]


def test_one_cell_set():
    out, applied, problems = apply_edits(XP, {"Mice": {"BaseExperience": 50}})
    assert out == XP.replace("Mice,25", "Mice,50") and applied == [("Mice", "BaseExperience", "25", "50")]
    assert problems == []


def test_multiply_every_row_keeps_integers():
    out, applied, problems = apply_edits(XP, {"*": {"BaseExperience": "x2"}})
    assert out == "Enemy,BaseExperience,DifficultyOffset\r\nFish,20,0\r\nMice,50,0\r\nRat,120,0\r\n"
    assert len(applied) == 3 and problems == []
    out, _, _ = apply_edits(XP, {"*": {"BaseExperience": "x1.5"}})
    assert cell(out, "Mice", "BaseExperience") == "37.5"


def test_multiplier_then_named_row_in_either_key_order():
    for edits in ({"*": {"BaseExperience": "x2"}, "Mice": {"BaseExperience": 25}},
                  {"Mice": {"BaseExperience": 25}, "*": {"BaseExperience": "x2"}}):
        out, applied, _ = apply_edits(XP, edits)
        assert [cell(out, r, "BaseExperience") for r in ("Fish", "Mice", "Rat")] == ["20", "25", "120"]
        # Mice set back to its own number is no change at all: one line per cell, its first and last value.
        assert ("Mice", "BaseExperience", "25", "50") not in applied and len(applied) == 2


def test_a_rows_own_multiplier_uses_the_value_before_star():
    for edits in ({"*": {"BaseExperience": "x2"}, "Mice": {"BaseExperience": "x0.5"}},
                  {"Mice": {"BaseExperience": "x0.5"}, "*": {"BaseExperience": "x2"}}):
        out, applied, _ = apply_edits(XP, edits)
        assert cell(out, "Mice", "BaseExperience") == "12.5" and cell(out, "Fish", "BaseExperience") == "20"
        assert ("Mice", "BaseExperience", "25", "12.5") in applied
    # Without "*", a row's own multiplier multiplies the game's number.
    out, _, _ = apply_edits(XP, {"Rat": {"BaseExperience": "x0.5"}})
    assert cell(out, "Rat", "BaseExperience") == "30"


def test_a_row_before_star_in_the_file_warns_once():
    _, _, problems = apply_edits(XP, {"Mice": {"BaseExperience": 25}, "*": {"BaseExperience": "x2"}})
    assert problems == ['Mice.BaseExperience: this file\'s own value now wins over its "*" (25, not 50); the Game '
                        'data page always showed 25']
    # After "*" a plain value always won: nothing to say.
    assert apply_edits(XP, {"*": {"BaseExperience": "x2"}, "Mice": {"BaseExperience": 25}})[2] == []
    # A row's own "xN" after "*" used to multiply its result: said too, once.
    _, _, problems = apply_edits(XP, {"*": {"BaseExperience": "x2"}, "Mice": {"BaseExperience": "x0.5"}})
    assert len(problems) == 1 and "(12.5, not 25)" in problems[0]
    # Another column of the same row isn't touched by "*": nothing changed for it, nothing said.
    assert apply_edits(XP, {"Mice": {"DifficultyOffset": 1}, "*": {"BaseExperience": "x2"}})[2] == []


def test_shorthand_sets_the_second_column_and_a_one_column_table_reports():
    out, applied, problems = apply_edits(TUNING, {"Run.Speed": 450})
    assert cell(out, "Run.Speed", "MaxValue") == "450" and problems == []
    out, applied, problems = apply_edits("Name\nMoth\n", {"Moth": "x"})
    assert out == "Name\nMoth\n" and applied == [] and "only its key column" in problems[0]


def test_column_names_match_without_case_and_the_key_column_is_refused():
    out, _, problems = apply_edits(XP, {"Mice": {"baseexperience": 30}})
    assert cell(out, "Mice", "BaseExperience") == "30" and problems == []
    out, applied, problems = apply_edits(XP, {"Mice": {"Enemy": "Mouse", "Nope": 1}})
    assert out == XP and applied == []
    assert "'Enemy' is the row key and can't be changed" in problems
    assert any(p.startswith("no column 'Nope'") for p in problems)


def test_multiplier_on_an_empty_or_text_cell_is_a_problem():
    _, applied, problems = apply_edits(TUNING, {"Tag": {"MaxValue": "x2"}})
    assert applied == [] and problems == ["Tag.MaxValue: can't multiply 'Gameplay.X' (not a number)"]
    _, applied, problems = apply_edits(TUNING, {"Run.Speed": {"Description": "x2"}})
    assert applied == [] and "can't multiply" in problems[0]
    # Over every row, the cells with no number are left alone and said once for the column.
    out, applied, problems = apply_edits(TUNING, {"*": {"MaxValue": "x2"}})
    assert cell(out, "Run.Speed", "MaxValue") == "780" and cell(out, "Tag", "MaxValue") == "Gameplay.X"
    assert problems == ["*.MaxValue: 1 row with no number there, left as they are"]


def test_text_into_a_numeric_cell_is_kept_and_reported():
    for bad in ("abc", "1,5", "x"):
        out, applied, problems = apply_edits(XP, {"Mice": {"BaseExperience": bad}})
        assert out == XP and applied == [] and problems == [f"Mice.BaseExperience: '{bad}' isn't a number; kept 25"]
    # A cell that isn't a number takes any text.
    out, _, problems = apply_edits(TUNING, {"Tag": "Gameplay.Y, with a comma"})
    assert '"Gameplay.Y, with a comma"' in out and problems == []


def test_a_numeric_string_value_is_a_number():
    out, _, problems = apply_edits(TUNING, {"Hetero.Chance": "0.08"})   # as wcmods-examples' npc-size-variety writes
    assert cell(out, "Hetero.Chance", "MaxValue") == "0.08" and problems == []
    out, _, problems = apply_edits(XP, {"Mice": {"BaseExperience": " 30 "}})
    assert cell(out, "Mice", "BaseExperience") == "30" and problems == []


def test_six_decimals_booleans_and_bad_values():
    assert format_value("0.15", 1 / 3) == "0.333333"
    assert format_value("25", 25.0) == "25" and format_value("2.5", 3.0) == "3"
    assert format_value("25", -0.0000001) == "0"
    assert format_value("FALSE", True) == "TRUE" and format_value("TRUE", False) == "FALSE"
    for bad in (None, [1], {"a": 1}, float("nan"), float("inf")):
        try:
            format_value("25", bad)
        except ValueError as e:
            assert "Error" not in str(e)
        else:
            raise AssertionError(f"{bad!r} was taken")
    _, applied, problems = apply_edits(XP, {"Mice": {"BaseExperience": None}})
    assert applied == [] and "isn't a value a table can hold" in problems[0]
    assert csvdata.multiplier("x2") == 2 and csvdata.multiplier("*0.5") == 0.5 and csvdata.multiplier("2") is None


def test_row_ops_with_the_wrong_shape_report_and_do_not_raise():
    # The shapes the Game data page used to write for "-" and "+": an object of index -> entry.
    out, applied, problems = apply_edits(XP, {"-": {"0": "Mice"}, "+": {"0": {"Enemy": "Owl"}},
                                              "Rat": {"BaseExperience": 61}})
    assert cell(out, "Rat", "BaseExperience") == "61", "the other edits still go in"
    assert '"-" should be a list of the row names to remove' in problems
    assert '"+" should be a list of rows to add, each an object of column: value' in problems
    _, _, problems = apply_edits(XP, {"+": ["Owl"]})
    assert problems == ['"+" should be a list of rows to add, each an object of column: value']
    assert apply_edits(XP, ["not", "edits"])[2] == ["the edits for a table should be an object of rows"]


def test_a_single_string_minus_is_one_row():
    out, applied, problems = apply_edits(XP, {"-": "Mice"})
    assert "Mice" not in out and applied == [("Mice", "(row)", "present", "removed")] and problems == []
    out, _, problems = apply_edits("#,Name\r\n53,A\r\n5,B\r\n3,C\r\n", {"-": "53"})
    assert out == "#,Name\r\n5,B\r\n3,C\r\n" and problems == []   # not "5" and "3", one character at a time
    out, _, problems = apply_edits(XP, {"-": ["Nope"], "+": [{"enemy": "Owl", "BaseExperience": 15}]})
    assert out.endswith("Owl,15,\r\n") and problems == ["no row 'Nope' to remove"]


def test_duplicate_row_keys_both_change():
    text = "Key,Value\nA,1\nB,2\nA,3\n"
    out, applied, _ = apply_edits(text, {"A": {"Value": "x10"}})
    assert out == "Key,Value\nA,10\nB,2\nA,30\n" and len(applied) == 2


def test_bom_and_crlf_survive():
    text = "﻿Key,Value\r\nA,1\r\nB,2"
    out, _, _ = apply_edits(text, {"B": {"Value": 5}, "+": [{"Key": "C", "Value": 7}]})
    assert out == "﻿Key,Value\r\nA,1\r\nB,5\r\nC,7"
