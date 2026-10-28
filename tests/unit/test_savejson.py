"""wcmods/formats/savejson.py: edits to the save's JSON text that change only what they're told to, the game's
own layout (tabs, CRLF, number style) kept everywhere else."""
import pytest

from wcmods.formats.savejson import SaveDoc

TEXT = ('{\r\n\t"acct": {\r\n\t\t"0": {\r\n\t\t\t"Level": 5,\r\n\t\t\t"Timer": 0.250000,\r\n\t\t\t"Name": "Fawn",\r\n'
        '\t\t\t"On": true,\r\n\t\t\t"Inv": {\r\n\t\t\t\t"Moss": 4,\r\n\t\t\t\t"Herb": 2\r\n\t\t\t},\r\n'
        '\t\t\t"Empty": {},\r\n\t\t\t"Seen": ["A", "B", "C"]\r\n\t\t}\r\n\t}\r\n}')


def changed_lines(a, b):
    return [(x, y) for x, y in zip(a.split("\r\n"), b.split("\r\n")) if x != y]


def test_set_changes_only_its_span_on_every_value_type():
    for path, value, want in (("0/Level", 6, '\t\t\t"Level": 6,'), ("0/Timer", 0.5, '\t\t\t"Timer": 0.5,'),
                              ("0/Name", "Moth", '\t\t\t"Name": "Moth",'), ("0/On", False, '\t\t\t"On": false,')):
        d = SaveDoc(TEXT)
        d.set(path, value)
        assert changed_lines(TEXT, d.text) == [(next(x for x in TEXT.split("\r\n") if x.startswith(want.split(":")[0])), want)]
    d = SaveDoc(TEXT)
    with pytest.raises(KeyError, match="no value at 0/Nope"):
        d.set("0/Nope", 1)


def test_set_many_in_one_parse_and_nested_paths_refused():
    d = SaveDoc(TEXT)
    d.set_many([("0/Level", 7), ("0/Inv/Moss", 9), ("0/Level", 8)])   # later wins
    assert d.get("0/Level") == 8 and d.get("0/Inv/Moss") == 9 and len(changed_lines(TEXT, d.text)) == 2
    with pytest.raises(ValueError, match="one contains the other"):
        SaveDoc(TEXT).set_many([("0/Inv", {}), ("0/Inv/Moss", 1)])


def test_insert_into_empty_and_non_empty_objects_keeps_crlf_and_indent():
    d = SaveDoc(TEXT)
    d.insert("0/Inv", "Catnip", 5)
    assert '\r\n\t\t\t\t"Catnip": 5,\r\n\t\t\t\t"Moss": 4,' in d.text and d.get("0/Inv/Catnip") == 5
    d.insert("0/Empty", "First", 1)
    assert d.get("0/Empty") == {"First": 1} and '"Empty": {\r\n\t\t\t\t"First": 1\r\n\t\t\t}' in d.text
    d.insert("0/Inv", "Moss", 10)   # a key it has: set
    assert d.get("0/Inv/Moss") == 10
    with pytest.raises(KeyError, match="is not an object"):
        d.insert("0/Level", "x", 1)


def test_delete_removes_the_entry_and_its_comma():
    d = SaveDoc(TEXT)
    d.delete("0/Inv/Moss")   # the first of two
    assert d.get("0/Inv") == {"Herb": 2} and '"Inv": {\r\n\t\t\t\t"Herb": 2\r\n\t\t\t},' in d.text
    d = SaveDoc(TEXT)
    d.delete("0/Inv/Herb")   # the last
    assert '"Inv": {\r\n\t\t\t\t"Moss": 4\r\n\t\t\t},' in d.text
    d.delete("0/Inv/Moss")   # the only one left
    assert d.get("0/Inv") == {} and '"Inv": {},' in d.text
    d = SaveDoc(TEXT)
    d.delete("0/Timer")      # one in the middle: the lines around it as they were
    assert d.text == TEXT.replace('\t\t\t"Timer": 0.250000,\r\n', "")
    with pytest.raises(KeyError):
        d.delete("0/Nope")
    with pytest.raises(KeyError):
        d.delete("")


def test_delete_list_elements_from_the_end():
    d = SaveDoc(TEXT)
    d.delete("0/Seen/2")
    d.delete("0/Seen/0")
    assert d.get("0/Seen") == ["B"] and '"Seen": ["B"]' in d.text
    d.delete("0/Seen/0")
    assert d.get("0/Seen") == [] and '"Seen": []' in d.text


def test_exists_and_get_with_array_indexes():
    d = SaveDoc(TEXT)
    assert d.get("0/Seen/1") == "B" and d.exists("0/Seen/2") and not d.exists("0/Seen/3")
    assert not d.exists("0/Level/x") and not d.exists("9") and d.account == "acct"


def test_a_key_with_a_slash_is_unreachable():
    d = SaveDoc('{"acct": {"a/b": 1, "a": {"b": 2}}}')
    assert d.get("a/b") == 2   # '/' always separates: the key "a/b" itself can't be named
    assert not SaveDoc('{"acct": {"a/b": 1}}').exists("a/b")


def test_two_top_level_keys_is_an_error():
    with pytest.raises(ValueError, match="unexpected save layout"):
        SaveDoc('{"a": {}, "b": {}}')
