"""wcmods' bracket check for Lua (wcmods/luacheck.py), which says before Apply what would stop a script from loading
in the game, and the creator's words it says it in. The cases are the audit's table: blocks, strings, comments and
numbers that a tokeniser can get wrong."""
import pytest

from wcmods import luacheck

CASES = [
    # (what, source, the problems)
    ("an if closed, its function not", "function f() if x then end", ["line 1: 'function' is never closed"]),
    ("a lone end", "x = 1\nend", ["line 2: 'end' with nothing open"]),
    ("repeat closed with end", "repeat\n  x = x + 1\nend", ["line 3: 'end' closes 'repeat' from line 1"]),
    ("repeat ... until", "repeat x = x + 1 until x > 3", []),
    ("an unclosed string", 'print("hello)\n', ["line 1: string never closed"]),
    ("an unclosed long comment", "x = 1\n--[[ a note\nthat never ends", ["line 2: long comment never closed"]),
    ("an unclosed long string", "s = [==[ text ]=]", ["line 1: long string never closed"]),
    ("keywords inside strings, long strings and comments",
     's = "function if do end"\nt = [[ end end ]]\n-- function\n--[==[ if\nrepeat ]==]\nu = \'(\'', []),
    ("goto and a label", "for i = 1, 3 do\n  if i == 2 then goto next end\n  ::next::\nend", []),
    ("numbers: hex with an exponent, a leading dot, an exponent", "a, b, c = 0x1p4, .5, 1e5", []),
    ("1..2 (not checked: expressions aren't)", "x = 1..2", []),
    ("CRLF line ends count once", "local a = 1\r\nlocal b = 2\r\nfunction f()\r\n", ["line 3: 'function' is never closed"]),
    ("an if ... elseif left open", "if a then\n  x()\nelseif b then\n  y()\n", ["line 1: 'if' is never closed"]),
    ("a string going on past a line end with a backslash", 's = "one \\\ntwo"\nfunction f() end', []),
    ("the same with a CRLF line end", 's = "one \\\r\ntwo"\r\nfunction f() end', []),
    ("a table left open", "local t = {\n  a = 1,\n", ["line 1: '{' is never closed"]),
    ("a closing bracket of the wrong kind", "f(a]", ["line 1: ']' closes '(' from line 1"]),
]


@pytest.mark.parametrize("what,source,expected", CASES, ids=[c[0] for c in CASES])
def test_luacheck_cases(what, source, expected):
    assert luacheck.check(source) == expected


def test_explain_says_each_problem_in_a_creators_words():
    said = {p: luacheck.explain(p) for p in (
        "line 1: 'function' is never closed", "line 3: 'repeat' is never closed", "line 2: '{' is never closed",
        "line 3: 'end' closes 'repeat' from line 1", "line 2: 'end' with nothing open", "line 1: string never closed",
        "line 2: long comment never closed", "line 1: long string never closed", "line 4: unexpected character '“'",
        "line 5: 'if' is never closed", "line 6: ')' with nothing open")}
    assert said == {
        "line 1: 'function' is never closed": 'line 1: a "function" is never closed with "end"',
        "line 5: 'if' is never closed": 'line 5: an "if" is never closed with "end"',
        "line 6: ')' with nothing open": 'line 6: a ")" with nothing before it to close (one too many, or its start is missing)',
        "line 3: 'repeat' is never closed": 'line 3: a "repeat" is never closed with "until"',
        "line 2: '{' is never closed": 'line 2: a "{" is never closed with "}"',
        "line 3: 'end' closes 'repeat' from line 1":
            'line 3: this "end" is where the "repeat" from line 1 should be closed with "until"',
        "line 2: 'end' with nothing open":
            'line 2: an "end" with nothing before it to close (one too many, or its start is missing)',
        "line 1: string never closed": "line 1: a piece of text in quotes is never closed (its closing quote is missing)",
        "line 2: long comment never closed": "line 2: a --[[ comment ]] is never closed with ]]",
        "line 1: long string never closed": "line 1: a [[ long text ]] is never closed with ]]",
        "line 4: unexpected character '“'":
            "line 4: a character Lua doesn't use, '“' (copied from a word processor?)",
    }
    assert luacheck.explain("something new") == "something new"   # one it doesn't know stays as it is
