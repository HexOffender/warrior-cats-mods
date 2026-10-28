"""tools/re/mechanics_notes.py: the Game data page's lines beside the game's rows, from docs/mechanics/. Tokens kept
as the docs write them, the line in words under its heading, and the committed data-notes.json made from the
docs as they are now."""
import importlib.util
import json
import os

from unit_helpers import REPO

spec = importlib.util.spec_from_file_location("mechanics_notes", os.path.join(REPO, "tools", "re", "mechanics_notes.py"))
notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes)

DOC = """# Exploration

**Sources:** `TuningData.csv` (`Stamina.RegenRate`), `LocationsData.csv`.

## Stamina

| | Value |
|---|---|
| Back when not running | 20 per second (`Stamina.RegenRate`) |

## Levels and experience

The level cap is 20 (`Gameplay.Exploration.MaxLevel`). `Gameplay.Exploration.Level.<n>` gives the
experience for each level: see **[progression](progression.md)**.

## Size

`CatSize.csv` gives each role a *scale* range:

```
`NotThis.Key` in code
```
- A list item with `Game.items.drop` and `x2` and `docs/x.md`.
"""


def test_a_short_key_is_kept_as_written_with_its_heading():
    found = notes.notes_from({"exploration.md": DOC})
    assert found["Stamina.RegenRate"] == [{"doc": "exploration.md", "heading": "Stamina", "anchor": "#stamina",
                                           "text": "Back when not running: 20 per second (Stamina.RegenRate)"}]
    assert "NotThis.Key" not in found and "x2" not in found and "docs/x.md" not in found


def test_a_pattern_key_keeps_its_placeholder():
    found = notes.notes_from({"progression.md": DOC})
    (note,) = found["Gameplay.Exploration.Level.<n>"]
    assert note["text"] == "Gameplay.Exploration.Level.<n> gives the experience for each level: see progression."
    assert note["heading"] == "Levels and experience" and note["anchor"] == "#levels-and-experience"
    assert found["Gameplay.Exploration.MaxLevel"][0]["text"] == "The level cap is 20 (Gameplay.Exploration.MaxLevel)."


def test_a_table_name_maps_to_its_heading():
    found = notes.notes_from({"npcs.md": DOC})
    assert found["CatSize.csv"] == [{"doc": "npcs.md", "heading": "Size", "anchor": "#size",
                                     "text": "CatSize.csv gives each role a scale range:"}]
    # A page's sources list every table it read: no line about any one of them.
    assert "LocationsData.csv" not in found and "TuningData.csv" not in found


def test_markdown_is_stripped_from_the_line():
    assert notes.plain("- **Fights:** each enemy's `BaseExperience` (see [combat.md](combat.md#after-the-fight)).") == \
        "Fights: each enemy's BaseExperience (see combat.md)."
    assert notes.plain("| Run | 390 (`Player.MoveAndRun.Run.Speed`), acceleration 175 |") == \
        "Run: 390 (Player.MoveAndRun.Run.Speed), acceleration 175"
    assert notes.plain("1. *Then* the __next__ one") == "Then the next one"
    assert notes.anchor("Jumping, climbing and falling") == "#jumping-climbing-and-falling"
    assert notes.sentence("One thing here. The `Key.Name` is 5. Another.", "Key.Name") == "The `Key.Name` is 5."
    long = "word " * 80 + "Key.Name"
    assert notes.sentence(long, "Key.Name").endswith("...") and len(notes.sentence(long, "Key.Name")) <= notes.LONGEST + 3


def test_every_titles_entry_names_a_table_the_notes_mention():
    # Anywhere in docs/mechanics, its index and the pages' sources included: the titles' links lead there.
    tables = []
    for name in os.listdir(notes.DOCS):
        if name.endswith(".md"):
            with open(os.path.join(notes.DOCS, name), encoding="utf-8") as f:
                tables += [t for line in f for t in notes.TICKED.findall(line) if t.endswith(".csv")]
    with open(os.path.join(REPO, "studio", "sections", "data-titles.json"), encoding="utf-8") as f:
        titles = json.load(f)
    for table in (t for t in titles if not t.startswith("_")):
        name = table.rsplit("/", 1)[-1]
        assert table in tables or name in tables, f"{table}: no mechanics note names it"


def test_run_speed_has_a_line_once_the_docs_name_its_key():
    found = notes.notes_from(notes.read_docs())
    (run,) = found["Player.MoveAndRun.Run.Speed"]
    assert run["doc"] == "exploration.md" and run["anchor"] == "#moving" and run["text"].startswith("Run: 390")
    assert found["Player.MoveAndRun.Stamina.DrainRate"][0]["text"] == "Running: -10 per second (Player.MoveAndRun.Stamina.DrainRate)"


def test_the_committed_notes_are_made_from_the_docs_as_they_are(tmp_path):
    out = tmp_path / "data-notes.json"
    notes.write(str(out))
    with open(os.path.join(REPO, "studio", "sections", "data-notes.json"), encoding="utf-8") as f:
        assert f.read() == out.read_text(encoding="utf-8"), "run tools/re/mechanics_notes.py after changing docs/mechanics"
