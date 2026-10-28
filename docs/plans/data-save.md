# Numbers: the Game data and Save pages

A plan for the two pages that change numbers: Game data (the tables the game plays by, through a
mod's `data.json`) and Save (the player's own save, through `save.json` or straight into the
save). It comes out of the 2026-10 audit of both pages (`audit/data.json`, `audit/save.json`) and
the skeptics' checks of every high and medium finding. Low findings were not checked; they are
listed as likely, not confirmed.

Work already under way elsewhere is referred to, not planned again: the test harness branch
(`claude/studio-tests`: `tests/unit/conftest.py` fixtures that call `Studio.api` over temp folders,
`tests/studio/lib/dom.mjs` and a dependency-free Chromium driver in `tests/studio/lib/browser.mjs`,
`node:test` units for `studio/lib`, end-to-end tests in `tests/studio/e2e/`, CI with Node), the Leaf
and Bark look (`claude/studio-look`: `styles.css`, a theme toggle, `studio/sections/<page>.css`,
`wc.pageHead({eyebrow, title, lede, help})`), and the shell (`claude/studio-shell`:
`Studio.check_file` running a section's `collect()` at save and showing what it raises under the
Editing-mod bar, a dirty guard with a Save/Discard/Stay choice, `wc.installedEvent`, progress polling
and a plain-words summary in the log drawer, `InstallBlocked` and the per-mod `failed` list in the
build report, the manifest's `names`, `cfg.peek()` in `pending()`, help panels from
`docs/guide/<page>.md`).

Other plans touch the same code, and this one is written to fit them:
- `docs/plans/palettes-cat.md` step 15 makes `apply_save_ops` record a cat's original look in
  `cat-originals.json` beside `wcmods.json` for "Put my cat back", through its own
  `wcmods/catorig.py` and `tests/unit/test_save_ops.py`. This plan's record of save edits is a
  second file beside it, `save-changes.json`, kept by `wcmods/saverecord.py` (step 6). The two stay
  separate (different keys, different undo); whichever plan lands second moves the shared
  read-and-write into `saverecord.py`. Its step 13 also links "the Save page's Injury system switch"
  from the Scars card, which this plan's default drops (Open question 5).
- `docs/plans/mods-setup.md` step 7 makes `/restore` ask for an Apply that "puts your mods' save
  changes back". Step 6 here makes that true under once-per-save edits. Neither plan prunes save
  backups, which "Change my save now" makes more of (see Likely but unchecked).
- `docs/plans/docs-guide.md` writes `docs/guide/data.md` and `docs/guide/save.md` and rewrites
  `docs/formats.md`'s `save.json` section. This plan updates those pages for what it changes. It
  does not write them a second time.

## What it is for

A creator wants to make the game play differently: run faster, level quicker, have prey worth
more, give the clans bigger cats or fewer scars. Now and then they also want to fix up their own
cat's save (top level, a full fresh-kill pile, a pawful of herbs) without losing anything they
have played for. Both pages exist for that. Today both are spreadsheets of the game's internal
names that only a programmer can read. The plan turns them into plain-word cards and keeps the raw
tables and the raw save behind a fold.

## Where it stands

### What works, and how we know

The table pipeline is sound underneath:
- `wcmods/formats/csvdata.py` edits a CSV in place and keeps every other byte. The selftest
  round-trips all 67 NonAsset tables byte for byte and applies a multiply-plus-one-cell edit to
  `CombatBaseExperience.csv` (`selftest.py:193-203`, needs the installed game).
- `tests/unit/test_formats.py::test_csv_rows_added_and_removed_in_the_files_style` covers row
  removal and addition on inline text.
- The page's cell editor, the "Multiply every column by N" control and the kind badges all reach
  the right Python. `wcmods/sections/data.py` collects, `BuildContext.resolve_csv_edits` in
  `wcmods/sdk.py:404-428` merges every mod's edits in priority order, and the edited text goes
  into the mod pak.

What has not been seen is the effect. `docs/verified.md:237` still lists "Game data tables in
play" as unconfirmed. The tables load from the same pak as the text, which is confirmed, but no
gameplay change has been checked on screen.

The save side works end to end:
- `wcmods/formats/save.py` decodes and re-encodes `WrcGame.sav`: one zlib archive per 128 KiB,
  the original Hash kept, a re-encode check before writing, and a backup of the whole save folder
  first.
- `tests/unit/test_formats.py::test_saves_over_128k_read_and_written` covers the long-save layout.
- The selftest checks that `SaveDoc.set` changes one line and that `set_many` and `insert` behave
  on a real save (`selftest.py:212-258`).
- `docs/verified.md:44` records that an edited save loads and that the game accepted a Level
  change.
- The audit ran the page's route, the section, `apply_save_ops` and the codec against temp saves.
  176 unit tests passed.

### Half-finished

- **Cell changes recorded but never shown.** Every build records each changed cell as
  `{row, column, from, to, by}` in the manifest's `csv_changes` (`wcmods/pipeline.py:194`), and
  nothing reads it: not the Apply drawer (`studio/app.js` `summarize` prints sections and warnings
  only), not the page, not the in-game Overview.
- **Row removal and addition.** `"-"` and `"+"` are documented (`docs/formats.md:214`) and tested
  in `csvdata`, but the page cannot make them and corrupts them when it finds them (bug 1).
- **Mechanics notes unused.** `docs/mechanics/*.md` explains most of what the page shows, row by
  row, and the page never links or quotes it. 361 of TuningData's 441 rows have an empty
  Description.
- **Kind badges.** `wcmods/sections/files.py` `classify` covers online, traits and appearance only.
  The dialogue, quest, HeightMap and UniqueIds tables count as "gameplay" with no note, and the page
  offers StoryDialogues' 2937 rows for editing like any other table.
- **No "give once" and no remove in `save.json`.** The SDK's `only_new` ("give once", used by the
  items section for starting items) has no place in `save.json` or on the Save page. There is no
  way to remove a key from the save at all.
- **A shared `save.json` lands on a fixed slot.** The Save page hides the Share card
  (`share: false`), but a `save.json` still ships in a mod's `.zip`. It applies to whoever installs
  it, on the slot number it was made on.
- **The Stats card may do nothing.** It says "the game may recalculate these". The code that builds
  a fighter's stats works them out from Level (`docs/mechanics/progression.md:62-65`), and nobody
  has checked whether the game ever reads the saved Stats.

### Confirmed bugs

Game data. A skeptic checked each one. Where the skeptic corrected a finding, the correction is
what is written here.

1. [high] `studio/sections/data.js:59`: the page corrupts row removals and additions.
   - `clean()` spreads any non-null object, so the documented `"-": ["53"]` and `"+": [{...}]`
     arrays become `{"0": ...}` objects.
   - The first Save to mod writes that shape. Save is always enabled, so no cell change is needed.
   - At build the removal is lost ("no row '0' to remove"), and `"+"` raises `AttributeError` in
     `csvdata.apply_edits` (`csvdata.py:205`).
   - That drops every edit the mod had on the table and marks the section partial, which blocks
     Apply until "Apply the rest anyway".
   - Precondition: a hand-written or imported file. The page never makes these entries itself.
2. [medium] `studio/sections/data.js:122`: the page and the build disagree when a row edit and a
   `"*"` multiplier share a column.
   - `valueFor()` shows the row edit winning over the `"*"`.
   - `apply_edits` runs edits in JSON key order (`csvdata.py:177-203`), and a multiplier
     multiplies the current text.
   - So the game gets the row's value doubled whenever the row key comes before `"*"` in the file.
   - That is always the case for integer-keyed tables (AttackMove, CombatDilemmas, NPC/Scars,
     NPC/PreffixName and more), since JavaScript puts integer-like keys first. For other tables it
     happens whenever the cell was edited before the multiplier was added.
3. [medium] `studio/sections/data.js:155`: every edit throws away the table view.
   - Every commit (Enter, blur or Escape), "Apply to all rows" and the Remove chip rebuild the
     table card.
   - The row filter is emptied and all rows come back. The multiply column and factor reset to the
     first column and 2.
   - The new `.table-wrap` starts scrolled to the top, so the focused cell can be out of view. Past
     the 600-row cap it may not be drawn at all.
4. [medium] `studio/sections/data.js:114`: a slow table load can take over the page.
   - `openTable()` sets `tableData` after its own fetch without checking that `current` is still
     that table.
   - Click a large table, then a small one before the large one answers: `tableData` stays on the
     large table while the small one is shown.
   - From then on `renderTable()`'s guard returns early. A cell edit leaves its text box in place
     with no "edited" mark, until the creator clicks that table in the list again.
5. [medium] `studio/sections/data.js:204`: Escape saves the typed value in Chromium.
   - The skeptic refuted the "second copy of the table" half: Chromium's `clear()` removes the
     nested redraw before appending its own.
   - The real defect is Escape. It calls `renderTable()` to cancel, the redraw's `clear()` fires
     `blur` into `commit()`, and the typed value is saved as "set".
   - The page becomes dirty and the next Save to mod writes the value.
6. [medium] `studio/sections/data.js:201`: one row can't be kept out of a multiplier.
   - With a `"*"` multiplier on a column, the editor opens with the game's original number, not the
     multiplied value the cell shows.
   - Typing the original, or the shown value, leaves the multiplier in force.
   - A row set to another number is exempt on the page, but in the build only when `"*"` comes
     before it in the file (bug 2).
7. [medium] `studio/sections/data.js:136`: text goes into number columns unchecked.
   - A non-number typed into a numeric column (`1,5`, `abc`, `x2`) is saved as text and written into
     the game's CSV unchanged, quoted when it holds a comma.
   - Nothing reports it: no toast, no build warning, no log line. `csvdata.format_value` returns any
     non-multiplier string as it is.
   - The page already computes `numericCols` and does not use them.
   - A numeric value with stray spaces is trimmed, so only text keeps its spaces.
   - A multiplier on an empty or text cell shows `x2` as the cell's value, while the build leaves the
     cell alone and only warns.
8. [medium] `wcmods/sections/data.py:29`: one unknown table name drops all of a mod's data edits.
   - A table name the game doesn't have (a typo in a hand-written or imported file, or a table a
     game update renamed) makes `collect()` raise.
   - Every table edit in that mod is left out and the section is partial.
   - The whole Apply is refused, with a message quoting a command-line hint.
   - The only way on is "Apply the rest anyway", which installs without any of that mod's data
     edits. The page cannot show or remove the table.
9. [low, corrected from medium] `wcmods/sdk.py:416`: nothing shows when two sources change the same
   cell.
   - Two enabled mods, or the Names page and a `data.json`, are resolved by priority order exactly
     as documented. So this is a missing visibility feature, not a defect.
   - Nothing on the page, in the Apply log or in game says that two sources touched the cell,
     although `csv_changes` records each change's source.

Save.

10. [high] `wcmods/pipeline.py:518`: a `save.json` edit is made again at every install.
    - At every later install (Apply, or Play while anything is pending, for instance after turning
      any mod on), `apply_save_ops` re-sets each "set" path whose save value differs from the mod's.
    - It also re-inserts each inventory add at the mod's quantity: `savedit.py:46` and `:53` queue
      them without `only_new`.
    - Example: a creator sets Level 10, plays to 14, then presses Apply for an unrelated change, and
      is back at Level 10.
    - The only evidence is the drawer line and the automatic backup. The page never says the edit
      stays in force.
11. [medium] `wcmods/sections/savedit.py:39`: an unreadable save blocks every install.
    - `build()` decodes `WrcGame.sav` before checking whether any mod has a `save.json`.
    - The skeptic added that `wcmods/sections/cats.py:27` does the same for `cats.json`.
    - A save wcmods can't decode (truncated, mid-write, or laid out differently after a game update)
      raises `ValueError` and the section is marked failed.
    - `pipeline.install` then refuses with "not installing because some mods didn't build: Save
      edits: ValueError: ...", even for a player with only a palette mod.
12. [medium] `studio/sections/save.js:149`: every change folds the tree back up.
    - Any value change calls `render()`, which rebuilds the whole "Everything else" tree with every
      group closed except the root.
    - A creator editing a nested value must reopen every group to change the next one.
    - Tree inputs lose keyboard focus to the document, because the rebuilt tree has no element with
      the old id.
    - Quick-card inputs keep focus through `wc.keepFocus`; only the Tab's intended move is
      swallowed.
13. [medium] `studio/sections/save.js:140`: the tree rounds decimals away.
    - A number whose current value is whole (volumes at 1, the fresh-kill Timer at 0, any float
      field at a round value) is treated as an integer field.
    - A typed decimal is `Math.round()`ed. When the rounded value equals the original, the edit is
      dropped and the box snaps back with no message.
    - The quick-card volume fields pass `int: false` and are unaffected.
14. [low, corrected from medium] `studio/sections/save.js:45`: number ranges aren't enforced.
    - The number fields show a min (Level 1, counts 0, volumes 0 to 1), but nothing enforces it.
    - A typed -5, 0, 999999 or 1e301 passes the `Number.isFinite` check and reaches the save.
    - What the game does with such values is unknown, so this is a missing guard rail, not a defect
      that acts on its own.
15. [low, corrected from medium] `wcmods/pipeline.py:503`: save edits waiting for a save aren't
    flagged.
    - An install made before the game had a save logs "no save yet; launch the game once, then
      install again" and records nothing.
    - `pending()` ignores save ops, so the status chip says "Game up to date" and Play starts the
      game without installing.
    - The audit's "Apply shows nothing to do" was wrong: Apply is always enabled and does apply the
      edits. The creator just isn't told to press it.
16. [low, corrected from medium] `studio/sections/save.js:13`: the page is tied to one slot by
    number.
    - The cards show and edit only the cat slot that was current when the page opened, by number
      and with no cat name.
    - Edits under another slot (a file made earlier, or a friend's mod) appear only in the raw
      `save.json` panel, so they are not invisible as the audit said. They still apply to that cat
      at install.
    - Edits made before switching cats in the game still go to the earlier slot.
17. [medium] `studio/sections/save.js:141`: every string in the tree is editable.
    - A change to `Shared/InputKeyboard` or `InputGamepad` is written to the save and ignored by the
      game. The Controls page is the working path.
    - A cat's `Customization` struct string can be edited as raw text, and one wrong character is
      written straight into the cat's record.

Likely but unchecked (low, from the audit):
- **Game data page:**
  - `data.js:147`: leaving a cell unchanged marks the page dirty.
  - `data.js:163`: kind chips explain themselves only on hover.
  - `data.js:176`: a first header of `" "` or `"_"` (GenericEffect, QuestCineCameraSettings) is not
    shown as "Row".
  - `data.js:55`: a `null` table entry breaks the page load, and a bad Import's rejection is never
    handled.
  - `data.js:7`: the seven HeightMap and UniqueIds tables are hidden while a file can edit them.
- **Table build:**
  - `sdk.py:418`: warnings name the section rather than the mod, and the mod stays "ok".
  - `csvdata.py:161`: values are rounded to six decimals while the page shows what was typed.
  - `csvdata.py:170`: a `"-"` given as a string is taken one character at a time.
- **Save page:**
  - `save.js:85`: an add for an item the save already has shows the save's count, but Apply sets
    the mod's.
  - `save.js:17`: applied fields show "changed" and "was <same>" for ever.
  - `save.js:9`: every read failure says "No save to edit yet".
  - `save.js:63`: the stats regex drops anything that is not `name=number`, and a cleared box
    becomes 0.
  - `save.js:132`: element ids made from paths can collide.
- **Save build and backups:**
  - `pipeline.py:489`: a failure inside `apply_save_ops` leaves the paks installed and the install
    unrecorded.
  - `savejson.py:14`: keys containing `/` can never be addressed.
  - `wcmods/templates/save/save.json:4`: the template turns the minimap on.
  - `settings.js:103`: only the last ten backups are listed, and nothing prunes them. This is the
    Settings and repair page's, not planned here; it matters more once every "Change my save now"
    and "Put it back" makes a backup, so it is handed to whoever next changes that page
    (mods-setup step 7 is the nearest).

## What a creator should be able to do

### Game data

The page keeps its name in the sidebar and opens with a plain-words lede: "Change the numbers the
game plays by: how fast you run, how much a fight is worth, what prey is worth, how big the clan
cats are. Your changes go in a mod; the game's own files stay as they are." Three parts come below
the Editing-mod bar.

**Quick changes.** A card of the dozen things everyone asks for. Each is a labelled row with:
- the game's normal value, a slider and a number box;
- one line saying what it does;
- a muted "Where: TuningData, Run.Speed" line and a link to the mechanics page;
- a "Normal" button that puts the game's value back.

The rows are grouped:

| Group | Rows |
|---|---|
| Moving | Running speed 390 cm/s, Jump height 85, Stamina used while running (10 a second; the table keeps it as -10), Stamina back when resting (20 a second) |
| Levelling | XP from fights (a factor on every animal's `BaseExperience`), Levels come faster or slower (a factor on `Gameplay.Exploration.Level.2` to `.20`), Inventory space per rank (100/120/140/160) |
| Food | What each prey is worth (Mouse 1 to Rabbit 5), How fast the pile goes down (`FreshKillPile.Decay.Time`, 90 s) |
| Dens | Build time (a factor on `HousingCost` `BuildTime`) |
| Clan cats | Sizes per role (`NPC/CatSize.csv`), Scar odds per role (`NPC/Scars.csv`), Two different eyes (`NPC.Heterochromia.Chance`, 0.15). Each row says "for cats the game makes from now on: a new game's clans, new kits; cats already in your save keep theirs" |
| Day and night | `DayNight.ClockSpeed` 72, labelled as the clock's speed until someone measures what a day lasts |

Every quick change is an ordinary cell edit underneath. It shows in All tables and in `data.json`
exactly like a hand edit.

**Find a number.** One search box across every table. Words like "run", "xp", "mouse", "scar" and
"cost" find:
- the quick rows, by their labels and synonyms;
- the mechanics notes' lines;
- the table titles and purposes;
- the row keys, and the Description column of every table.

A hit reads "Running speed, 390 (TuningData)" or "Mice, BaseExperience 25 (XP from fights)".
Clicking it opens the table with that row in view.

**All tables.** Today's list and grid, behind a fold:
- **Plain words:**
  - Tables get a title and a one-line purpose where the mechanics notes have one ("XP from fights:
    how much experience each animal gives when you beat it").
  - Rows show the mechanics line beside the key ("the XP needed to reach level 5").
  - `STR_` keys show the English text, with the key on hover.
  - TuningData's value column is headed "Value", and headers carry a unit where the notes give one
    (cm/s, seconds).
  - Chips say what they mean ("Online: the den-visit server may ignore this", "Story: quests and
    talk; a wrong value can stop a quest").
- **The editor:**
  - Escape cancels and Enter commits once. The filter and scroll stay put after an edit.
  - Text typed into a number column is refused with "Use a number like 1.5".
  - TRUE/FALSE columns are checkboxes, and columns with a handful of fixed words (Stance, Rank,
    Target) are dropdowns.
  - A row is kept out of a multiplier by typing its value.
- **Multiplying:** "Multiply every …" is gone from TuningData, whose single value column holds 441
  unrelated numbers.
- **The file's own entries:** row removals and additions show as chips with Remove instead of
  being rewritten.

The raw `data.json` panel sits under "For mod makers".

**The first five minutes.**
1. Open Game data. Quick changes is at the top, with Running speed at 390.
2. Drag it to 600. The row says "390 -> 600" and the Editing-mod bar says "Unsaved changes".
3. Press Save to mod (My mods is picked by default).
4. Press Apply to game. The drawer says "TuningData: Running speed 390 -> 600 (My mods)".
5. Press Play. In the forest the cat runs faster.

That is the whole loop. The in-game check at the end of step 4 of the plan confirms that table
edits reach the game.

### Save

The page opens as "Save: changes to your cat's save", with the lede "Change what your cat has:
its level, the fresh-kill pile, what it carries. Each change is made once, with a copy of your save
kept first, and you can put any of them back." While the game runs, a status line says "The game is
running: close it before changing your save".

**Your cat: Fawnstar.** The cat's name, from the save's current slot. Level (1 to 20), Experience
and Fresh-kill pile (0 to 100) are number boxes that enforce their ranges. Health and stamina are
not on this card, because they refill in play: stamina comes back at 20 a second and a fight starts
at full health (Prowess). They stay in the tree under Advanced. Preset buttons:
- **Max level:** Level 20, Experience 0. "Your rank stays as it is: promotions come from the
  rank-up quests."
- **Fill the fresh-kill pile:** to 100.
- **Give herbs:** five each of the healing herbs and small catnip, by name.

A preset only adds to the list below. Nothing is written until the creator says so.

**What it carries.** The inventory, by item name with the game's own icons (the Items page's
lookup), with counts and a Remove on every row. An Add picker is grouped Herbs and catnip,
Materials, Accessories (an accessory is added once).

**Changes to make.** The pending changes in words ("Fresh-kill pile: 62 -> 100", "Small Healing
Herb: none -> 5"), each with a remove. Two ways to use them:
- **Change my save now:** the main path. It refuses while the game runs; otherwise it backs up,
  writes and records.
- **Keep it as a mod to share:** today's Save to mod, under its own fold, for a `save.json` that
  applies once to whoever installs it.

**Done so far.** Every change made from this page or by a mod, with when it was made and the old
and new value. Each line has "Put it back", which writes the old value back after another backup
(or takes out an item that wasn't there). If the save has moved on since, it asks first: "Your cat
is level 14 now; putting it back makes it level 5."

**Advanced.** The whole save as a tree:
- a search box that opens matching groups, and open groups that stay open after a change;
- a change in the tree joins Changes to make like any other;
- read-only rows for key bindings ("Use the Controls page") and cat records ("Use Your cat or
  Names");
- the Combat stats card with its note;
- the raw `save.json` panel.

The game settings card is dropped by default (Open question 5): the game's own menu sets those, and
the tree still reaches them.

**The first five minutes.**
1. Open Save. It shows "Your cat: Fawnstar, level 5".
2. Press Fill the fresh-kill pile. Changes to make shows "Fresh-kill pile: 62 -> 100".
3. Press Change my save now. The page says "Done at 15:30; a copy of your save from before is in
   Settings and repair".
4. Done so far shows the change, with Put it back.
5. Press Play.

## The plan

The steps are ordered so that each one leaves both pages working, with the Python underneath fixed
before the pages lean on it. Test names follow the test harness branch's layout (its
`CONTRIBUTING.md` and `docs/ARCHITECTURE.md`):
- `tests/unit/test_*.py` for Python, with its `tests/unit/conftest.py` fixtures (`studio`,
  `fake_game`, `save`, `write_save`, `make_mod`) where a test needs a Studio, a save or a mod;
- `tests/studio/<name>.test.mjs` for `node:test` units over the pure modules in `studio/lib`, as
  `tests/studio/story.test.mjs` does for `studio/lib/story.js` (`tests/studio/lib/dom.mjs` is there
  when one needs a DOM);
- `tests/studio/e2e/<name>.test.mjs` for pages driven in a headless Chromium through
  `tests/studio/lib/browser.mjs`, which skip without one.

`tests/studio/lib/` holds the helpers only. The shell branch keeps its own units in
`tests/studio/unit/`; whichever layout the two branches settle on, these files follow it. All of
them run with `node --test "tests/studio/**/*.test.mjs"`.

Browser cases go in the pull request that depends on the tests branch. They are never left in an
earlier PR that can't run them.

### 1. The table format says one thing and the build does that

Files: `wcmods/formats/csvdata.py`, `wcmods/sections/data.py`, `wcmods/sections/files.py`,
`wcmods/sdk.py`, `wcmods/templates/data/data.json`, `docs/formats.md`, `docs/SDK.md`, `README.md`,
new `tests/unit/test_csvdata.py` and `tests/unit/test_data_section.py`.

**The order.** `data.json` keeps its shape and gains one fixed order inside a table, whatever order
the keys are in: removals (`"-"`), then `"*"` on every row, then named rows, then additions (`"+"`).
- A named row's plain value replaces whatever `"*"` made of that cell.
- A named row's own `"xN"` multiplies the cell as it was before this file's `"*"`: the game's
  value, or what an earlier mod made it. So inside one file, `"*"` and a row's `xN` never compound.
  `apply_edits` keeps the cells' text from before its `"*"` pass for this.
- Between mods nothing changes. Each mod's edits apply in priority order on the text the previous
  mod left, so two mods' `"*"` x2 make x4, as documented.

So this file doubles every animal's XP except mice:

```json
{ "CombatBaseExperience.csv": { "*": { "BaseExperience": "x2" }, "Mice": { "BaseExperience": 25 } } }
```

The page's preview (which already assumes this rule) is then what the game gets.

**A one-release warning.** A file with a named row before `"*"` on the same column now builds to
the row's value rather than that value times N. That is what the page wrote for integer-keyed
tables, and what it always showed. For one release the build warns once per such cell:
"Mice.BaseExperience: this file's own value now wins over its "*" (25, not 50); the Game data page
always showed 25". A hand-written file that meant the old result is then noticed (Open question 1).

**Shapes and values.**
- `apply_edits` checks `"-"` (a list of row names; a single string is one row name, not its
  characters) and `"+"` (a list of objects). Another shape is one problem, never an exception.
- `format_value` gets a new problem. When a numeric original is replaced by a value that doesn't
  read as a number, the original is kept and the problem reported ("Mice.BaseExperience: 'abc'
  isn't a number; kept 25"). That also catches `1,5`.
- A string that reads as a number is still fine (`"0.08"`, as wcmods-examples' `npc-size-variety`
  writes), and a non-numeric original (a tag, a `STR_` key) still takes any text.
- `"*"` over a column with empty or text cells leaves those cells as they are with one problem per
  column ("BaseExperience: 2 cells aren't numbers and stay as they are"), not one per cell. A named
  row's `xN` on such a cell is still its own problem.

**Unknown tables.** `DataSection.collect` no longer raises for a table the game lacks. It warns in
page words ("the game has no table 'Nope.csv'; the Game data page lists the ones it has") and keeps
the other tables. Showing that warning at save time needs a change to the shell's
`Studio.check_file`, which only reports what `collect()` raises today, so it is done in step 3. Until
then the page itself shows the table (step 2) and the Apply drawer shows the warning.

**Kinds.** `files.classify` gains `story` for the dialogue and quest tables (QuestDialogues,
StoryDialogues, QuestObjectives, NarrativeRole). `DataSection.build` warns "<mod>:
StoryDialogues.csv is quests and talk; a wrong value can stop a quest", and `FilesSection.build`
treats `story` files as it treats `gameplay` ones, so a replacement file keeps its warning. The page
gets the kind through `/api/game/data` as before.

**Naming mods and conflicts.**
- `resolve_csv_edits` names the mod in its warnings (`source or section`).
- It adds a warning when a different source changes a cell an earlier source already changed:
  "my-tweaks changed Mice.BaseExperience after double-xp". The Apply drawer then names both.
- One file's own `"*"` followed by its own row is not a conflict.

**The template.** `wcmods/templates/data/data.json`'s `_help` points at "the Game data page in
Clan Mod Studio" and no longer claims that the page browses every table.

Tests:
- `tests/unit/test_csvdata.py`:
  - `test_one_cell_set`, `test_multiply_every_row_keeps_integers`;
  - `test_multiplier_then_named_row_in_either_key_order` (both orders give 25 for mice, 50 for the
    rest), `test_a_rows_own_multiplier_uses_the_value_before_star`,
    `test_a_row_before_star_in_the_file_warns_once`;
  - `test_shorthand_sets_the_second_column_and_a_one_column_table_reports`,
    `test_column_names_match_without_case_and_the_key_column_is_refused`;
  - `test_multiplier_on_an_empty_or_text_cell_is_a_problem`,
    `test_star_over_non_numbers_is_one_problem_per_column`,
    `test_text_into_a_numeric_cell_is_kept_and_reported`, `test_a_numeric_string_value_is_a_number`,
    `test_six_decimals_booleans_and_bad_values`;
  - `test_row_ops_with_the_wrong_shape_report_and_do_not_raise`,
    `test_a_single_string_minus_is_one_row`, `test_duplicate_row_keys_both_change`,
    `test_bom_and_crlf_survive`.
- `tests/unit/test_data_section.py`, with a fake `ctx` (`game.exists` a lambda, `warn` a list):
  - `test_help_key_ignored_and_two_tables_collected`, `test_unknown_table_warns_and_keeps_the_rest`,
    `test_non_csv_key_or_non_dict_edits_is_an_error`, `test_online_traits_and_story_tables_warn`,
    `test_classify_names_every_kind`;
  - `test_two_mods_same_table_queue_in_priority_order`, `test_same_cell_from_two_sources_warns`,
    `test_one_files_star_then_its_row_is_not_a_conflict`.

Docs: `docs/formats.md`'s `data.json` section grows from five lines to the rules above:
- values may be numbers, text, TRUE/FALSE or `"xN"`;
- columns match without regard to case;
- numbers are written with at most six decimals;
- the fixed order inside a file, and the priority order between mods;
- a row or table the game lacks is a warning, and so is text in a number cell;
- a key may be a full `Wrc/...` path.

`docs/SDK.md`'s `ctx.edit_csv` row describes the same order. README's command list says the
`tables` command is the colour tables, not these. No game needed.

### 2. The Game data page edits what it shows

Files: `studio/sections/data.js`; new `studio/lib/data.js` (the pure parts: `clean`, `toJson`,
`valueFor`, the number check, `countEdits`, the header-to-"Row" rule, the column-kind rule); new
`tests/studio/data.test.mjs`. This step leaves `studio/app.js` and `studio/lib/wc.js` alone,
because the shell and look branches rewrite both.

The page keeps today's layout.

**The file's own entries.**
- `clean()` keeps any array-valued spec (`"-"`, `"+"`) aside in a `rowOps[table]` map, and
  `toJson()` writes it back untouched.
- They show as chips above the grid ("1 row removed, 1 row added by hand") with Remove.
- A `null` or non-object table entry is skipped with a toast naming it, and the page's `onLoad`
  catches its own errors, so a bad Import says so instead of failing silently.
- A table in the file that the game lacks shows as a line under the list ("This mod also edits a
  table the game doesn't have: Nope.csv") with Remove.
- The seven HeightMap and UniqueIds tables stay out of the list (Open question 7). A file that
  edits them shows the same "also edits" line, so nothing in the file is invisible.

**Loading.** `openTable()` returns after its fetch when `current` has moved on, `renderTable()`
reads `cache[current]`, and a failed load clears `tableData`.

**The cell editor.**
- It gets a `done` flag. Enter commits once. Escape sets `done` and redraws the cell without
  committing, and the blur listener is removed before any redraw.
- A commit updates only its own cell (a fresh `valueFor` through `show()`), the list counts and the
  `"*"` chips.
- Where a rebuild is still needed (Apply to all rows, Remove chip), the filter text, the multiply
  choices and the `.table-wrap` scroll position are kept and put back.
- `unsetCell` marks the page dirty only when it removed something.

**Values.**
- `valueFor` shows a row's own `xN` as the number it makes, by step 1's rule.
- Under a `"*"` multiplier the editor opens with the shown value. Any typed value, the game's
  original included, is an explicit set for that row, which step 1's order makes hold in the build.
- In a column whose filled cells are all numbers, a non-number is refused with "Use a number like
  1.5". Values are trimmed and rounded to six decimals, as the file will write them.
- A multiplier over an empty or text cell shows "unchanged (not a number)".

**Column kinds.** These choose words the creator doesn't have to spell:
- TRUE/FALSE columns are a checkbox.
- A column with at most eight distinct words, no numbers, and each word used at least twice
  (Stance, Rank, Target, Rarity, Size) is a dropdown of those words. `STR_` and Description columns
  never are, so a small table's name column stays free text.
- A first header that is empty or punctuation after trimming shows as "Row".

**Multiplying.**
- "Multiply every …" is hidden on TuningData.
- Elsewhere its button says what it does: "Every BaseExperience × 2".
- When every filled value in the column is from 0 to 1 and the factor takes one above 1, the page
  says so before applying ("3 values go above 1; if these are chances, above 1 means always"). It
  doesn't refuse, because sizes such as CatSize's 0.1 to 1.0 live in that range too; the quick rows
  that are chances refuse (step 4).
- A "Put this table back" confirm button removes every edit on the open table.

**Keyboard and chips.**
- The grid is one tab stop with arrow-key movement (a roving `tabIndex`), and the note says "Press
  Enter to change a value".
- Kind chips spell out their meaning in visible text, so nothing depends on hover: "Online: the
  den-visit server may ignore this", "Traits: changes which personality new cats get", "Story:
  quests and talk; a wrong value can stop a quest", "Appearance only".

Tests, `tests/studio/data.test.mjs` (units over `studio/lib/data.js`, no DOM needed):
- `clean and toJson keep "-" and "+" arrays untouched`, `clean skips a null table with its name`;
- `shorthand expands to the second column once the table is cached`;
- `valueFor agrees with apply_edits for a row edit under a multiplier`,
  `valueFor shows a row's own x0.5 as its number`, `valueFor on an empty cell under x2 says unchanged`;
- `a number check accepts 25, " 25 " and 1.50 and refuses 1,5 and abc`;
- `countEdits counts a "*" entry once per column`;
- `a punctuation-only header is Row`;
- `a column of TRUE/FALSE is a checkbox, a repeated five-word column a dropdown, and five words used
  once each stay free text`.

They run with plain `node --test`; CI runs them once the tests branch's Node job is in. The browser
cases for this step are in step 3's PR, which depends on the tests branch. For this PR, Enter,
Escape, the slow-table race and the refused text are also checked by hand in the studio, and the PR
description says so. No game needed.

### 3. Plain words beside every row: notes, titles, English text and search

Files:
- new `tools/re/mechanics_notes.py` and the file it generates, `studio/sections/data-notes.json`
  (checked in; data, not code);
- new `studio/sections/data-titles.json` (hand-written);
- `wcmods/studio.py`: two route changes, and `check_file` passing `collect()`'s warnings on;
- `studio/lib/wc.js`: the shell's problems box shows those warnings under their own heading;
- `studio/sections/data.js`, `studio/sections/data.css` (the look branch's per-page file);
- `docs/mechanics/README.md`, and `docs/mechanics/exploration.md`, `clan-life.md`, `progression.md`
  and `npcs.md` where a value has no key yet;
- `docs/guide/data.md` (written by the docs-guide plan);
- new `tests/unit/test_mechanics_notes.py` and `tests/unit/test_studio_data.py`;
- `tests/studio/data.test.mjs` (more units), new `tests/studio/e2e/data.test.mjs`.

**The generator.** `mechanics_notes.py` reads `docs/mechanics/*.md`. For every backticked token that
is a table name (`X.csv`) or a dotted key with a capital in it, it records the line the token appears
in, with the markdown stripped, and the nearest heading. Tokens are kept as the docs write them:
short keys (`Stamina.RegenRate`, `DayNight.ClockSpeed`), patterns (`Gameplay.Exploration.Level.<n>`,
`Gameplay.Inventory.Capacity.<Rank>`) and bare table names (`CatSize.csv`):

```json
{ "Stamina.RegenRate": [{ "doc": "exploration.md", "heading": "Stamina",
    "anchor": "#stamina", "text": "Back when not running: 20 per second" }],
  "CombatBaseExperience.csv": [{ "doc": "combat.md", "heading": "After the fight", "anchor": "#after-the-fight",
    "text": "each enemy type has a BaseExperience in CombatBaseExperience.csv" }] }
```

**Matching notes to rows.** The page matches a token to rows when the row key equals the token or
ends with "." plus the token. `<x>` stands for one key part, and a table token matches the table with
that file name. A token that matches more than one row shows on none.

**Missing keys.** Some values in the docs have no key at all. Exploration's Moving table gives Walk
175 and Run 390 with no key, so this step adds the full keys
(`Gameplay.Exploration.Player.MoveAndRun.Run.Speed` and its siblings, taken from the table) to the
docs. Running speed then has its line.

**What stays bare.** The docs mention a few hundred keys, so most rows of most tables still show only
their key, and in TuningData the 80 rows that have a Description. The page says so.

`mechanics_notes.py` is run like `mechanics_tables.py`, after a docs change, but it reads only the
docs and needs no game.

**Titles.** `data-titles.json` is a hand-written map for the tables the notes cover. `value` renames
a value column's header (`MaxValue` to `Value`), and `units` adds a unit to a header where the notes
give one:

```json
{ "CombatBaseExperience.csv": { "title": "XP from fights",
    "what": "How much experience each animal gives when you beat it",
    "doc": "docs/mechanics/combat.md#after-the-fight", "value": "Value" },
  "HousingCost.csv": { "title": "Den decorations", "units": { "BuildTime": "seconds" } } }
```

**Routes.**
- `GET /api/game/data/<name>` adds `texts`, `{STR_KEY: English}`, for every cell in the table that
  starts with `STR_`. The Studio's `_reader()` `BuildContext` already has `text()`.
- A new `GET /api/game/data/index` returns `{table: {rows: [keys], descriptions: {key: text}}}` for
  every table, read once and cached on the Studio (a few hundred kilobytes). It is matched before the
  per-table route.

**Warnings at save.** `Studio.check_file` returns the `ctx.warnings` that `collect()` left as
`notes`, beside the `problems` it already returns, and the file PUT route passes them on. The
shell's box under the Editing-mod bar shows notes under "Saved; this part will be left out:" rather
than "Saved, but it can't go in the game yet". This is how step 1's unknown-table warning reaches the
page.

**UI.**
- The search box at the top ("Find a number by what it does") searches the quick rows' labels and
  synonyms (step 4), the notes' text, the titles, and the index's row keys and descriptions. A hit
  opens the table filtered to that row.
- Each grid row shows its note beside the key, with the doc link on the title's eyebrow.
- `STR_` cells show the English, with the key on hover.
- The page header uses `wc.pageHead({eyebrow: "Gameplay", title: "Game data", lede, help:
  "help:data"})`. The `help:` prefix opens the guide panel; a bare string would be taken for a doc
  path.

Tests:
- `tests/unit/test_mechanics_notes.py`: `test_a_short_key_is_kept_as_written_with_its_heading`,
  `test_a_pattern_key_keeps_its_placeholder`, `test_a_table_name_maps_to_its_heading`,
  `test_markdown_is_stripped_from_the_line`, `test_every_titles_entry_names_a_table_the_notes_mention`,
  `test_run_speed_has_a_line_once_the_docs_name_its_key`.
- `tests/unit/test_studio_data.py`, with the harness's `studio` fixture and a stub game set on it
  (`data_tables`, `exists` and `read_text` over three inline tables and a small `Strings_EN.csv`):
  `test_game_data_lists_tables_and_kinds`, `test_a_table_comes_with_its_english_texts`,
  `test_a_missing_table_is_an_error_in_page_words`, `test_the_index_names_every_table_and_its_rows`,
  `test_put_data_json_refuses_broken_json_and_adds_a_newline`,
  `test_check_file_shows_an_unknown_table_as_a_note`.
- `tests/studio/data.test.mjs` adds `a short key matches the one row ending with it and an
  ambiguous one matches none`.
- `tests/studio/e2e/data.test.mjs`, through the browser driver against a Studio over a fixture game:
  a game folder (as the tests branch's e2e `makeGame` makes one) whose `pakchunk0-Windows.pak`,
  written with wcmods' own `PakWriter`, holds three small NonAsset tables and `Strings_EN.csv`.
  `GameFiles` finds a file in the pak before it opens the `.utoc`, so no IoStore container is
  needed. It takes step 2's cases: `Enter commits once and keeps the filter and scroll`, `Escape
  leaves the cell as it was and the page clean`, `a slow table answering after a fast one does not
  take over`, `typing text into a number column is refused`, `a row typed under a multiplier shows
  set and writes that number`.

Docs:
- `docs/mechanics/README.md` gets a short "By goal" index naming the table and row for each goal:
  running speed, XP, prey value, day length, inventory space, den build times, cat sizes, scars.
- `docs/guide/data.md` is the docs-guide plan's page. This step adds Quick changes, search and "Is
  it in the game?" to it, and writes the page in that plan's outline if it hasn't landed yet.
- No game needed.

### 4. The Quick changes card

Files: new `studio/sections/data-quick.json`, `studio/sections/data.js`, `studio/lib/data.js` (the
mapping logic), `wcmods/selftest.py`, `README.md`, new `tests/studio/data-quick.test.mjs` and
`tests/studio/e2e/data-quick.test.mjs`.

The format has one entry per row of the card:

```json
{ "id": "run-speed", "group": "Moving", "label": "Running speed",
  "table": "TuningData.csv", "row": "Gameplay.Exploration.Player.MoveAndRun.Run.Speed", "column": "MaxValue",
  "kind": "value", "unit": "cm/s", "min": 100, "max": 1200, "step": 10,
  "what": "How fast your cat runs. Walking is 175.", "doc": "docs/mechanics/exploration.md#moving",
  "synonyms": ["run", "speed", "fast", "sprint"] }
```

**Entry kinds.**
- `kind` is `value` (writes the number into that cell) or `factor` (writes `"xN"`).
- A factor entry may give `"row": "*"` (`CombatBaseExperience` `BaseExperience`, `HousingCost`
  `BuildTime`) or `"rows": [...]`. The nineteen `Gameplay.Exploration.Level.<n>` keys are written as
  the shorthand `{row: "x0.5"}` that `apply_edits` already takes, and step 1's rule makes each
  multiply the game's value.
- `negate: true` shows a value the table keeps negative as a positive number:
  `MoveAndRun.Stamina.DrainRate` is -10 and shows as "10 a second".
- A `chance` flag clamps values to 0 to 1, and refuses a factor that would push a cell over 1 (the
  Scars columns, the two-eyes row).

**Where values come from.** The game's normal value comes from the loaded table. The card loads
TuningData, CombatBaseExperience, HousingCost, NPC/CatSize and NPC/Scars on mount, through the same
cache the grid uses.

**The first rows:**
- Moving: Running speed, Jump height, Stamina used while running, Stamina back when resting.
- Levelling: XP from fights, Levels come faster or slower, Inventory space (four rows).
- Food: What prey is worth (six rows), How fast the pile goes down.
- Dens: Den build time. Its `what` says uncommon decorations take about 4 hours, and that whether
  that is real time isn't checked.
- Clan cats: sizes (one row per role, the two range columns together), scars (one row per role, the
  three chance columns together), two different eyes. Each says it applies to cats the game makes
  from now on.
- Day and night clock.

Exact row keys are taken from the table when an entry is written, not from memory, and the selftest
(which has the installed game) gains "quick changes, titles and notes name real rows": every
`data-quick.json` entry's table, row and column, every `data-titles.json` table and every
`data-notes.json` table name exist in the game. Each `what` ends with how sure it is, in plain words:
- "Checked in game" once the in-game check below passes (the speeds);
- "The game's code uses this" for the rows the mechanics notes say are loaded by code (movement,
  jump and stamina, at `0x14179F650`);
- "Not checked in game yet" for the rest.

**UI.**
- Each row has the label, the normal value, a range slider and a number box in step, a Normal
  button, the `what` line, the muted Where line and the doc link.
- A factor row previews the first three cells: "Mice 25 -> 50, Fish 10 -> 20, ...".
- Writing goes through the same `setCell`/`unsetCell` as the grid, so the counts, the JSON panel and
  the dirty state all follow.

Tests:
- `tests/studio/data-quick.test.mjs`: `every entry names a column its table has` (against fixture
  headers), `a value entry writes the cell and Normal removes it`, `a negated entry shows 10 and
  writes -10`, `a factor entry writes xN on "*" or on each row`, `a chance factor over 1 is
  refused`, `search finds a row by a synonym`.
- `tests/studio/e2e/data-quick.test.mjs`: `dragging Running speed shows the edit in All tables and
  in data.json`, `Normal puts the row back and the page is clean`.

Docs: README's Game data row names Quick changes and the search.

Until the in-game check below passes, the card carries one line listing what has been seen working
in game. After it passes, the line reads "Checked in game: walking and running speed".

**Game verification** (its own small PR, independent of the pages). This settles
`docs/verified.md:237`. In-game tests run against a game that was installed and launched before
the run (`tests/game/test_cpp_sdk.py` works the same way): an install can't happen while the game
runs. So the mod is a folder in the repository, not a temp folder.
1. New `tests/data-speed/` holds `mod.json` and a `data.json` that sets
   `Gameplay.Exploration.Player.MoveAndRun.Walk.Speed` to 700 and `...Run.Speed` to 800 (keys as in
   wcmods-examples' `faster-run`), and raises the walk and run acceleration rows (175 cm/s² in the
   game; their keys read from the table when the file is written) to 5000. Without that, a run at
   175 cm/s² takes 4.6 s to reach 800, and a 3 s run covers about what the game's own does.
2. The run is `python wcmods.py agent install --with tests/data-speed` with the game closed, then
   `python wcmods.py agent test tests/game/test_data.py --launch`. The test's `setup(agent)` skips,
   naming those commands, unless `wcmods.json`'s `installed.mods` lists `data-speed`. Afterwards
   `agent install --normal` puts the player's own mods back.
3. `test_walk_speed_from_the_table`: `agent.move(forward=1, seconds=4)` (walking input) must go past
   1400 cm. The game's own walk covers about 610 cm in that time.
4. `test_run_speed_from_the_table`: `agent.keys("S", "LeftShift", hold=3)` (the agent's own way to
   run, away from the camera as `test_cat.py`'s key test walks, the way that's usually open) must
   go past 1500 cm. The game's own run covers about 735 cm in 3 s, and 3 s of running uses 30 of
   the 100 stamina.
5. Each test teleports back to where it started. The cat's `CharacterMovement.MaxWalkSpeed` is read
   once through `Game.get` and written to the report, not asserted, since whether the game copies
   the table's speed there isn't documented.

The test follows the in-game-probe rule (one object read, no FindAllOf scans). It runs only when no
other session has the game open (check who launched it first), on the test cat. A fight-XP check
(double-xp's `"*"` x2, one fight, Experience before and after on the Menu pages' Stats page) is
manual: finding a roaming animal to pounce on needs a world scan, which the probe rule forbids. On a
pass, verified.md moves the line to Confirmed, `docs/agent.md` counts and lists the new tests, and
the page's lede may say tables change the game without hedging.

### 5. The Apply drawer says which cells changed, and the page says what is in the game

Files: `studio/app.js` (the shell branch's `summarize`), `studio/sections/data.js`,
`wcmods/studio.py`.

**The drawer.**
- It prints `csv_changes` per table as one net line per cell: the first `from`, the last `to`,
  skipped when they are equal. For example "TuningData: Running speed 390 -> 450 (My mods)".
- Rows and columns use the quick labels and titles where it has them, and raw names otherwise. Mod
  names come from the manifest's `names`, which the shell adds.
- It shows at most twenty lines, then "and N more".
- Step 1's conflict warning appears there too.

**The page.**
- A "Your changes" card at the top of All tables lists every edit in the open mod in words (table,
  row, column, game's value -> yours), each with Normal. This is the undo and diff view the audit
  asked for.
- A new `GET /api/game/data/applied` returns the installed build's `csv_changes`: the build
  folder's `manifest.json` when its `built` equals `wcmods.json`'s `installed.built`, else nothing.
  The page reads it on open and marks those lines and cells "in the game since 15:30", which tells
  an applied edit from one not yet applied.
- On `wc.bus.on("installed", ...)` it takes the new manifest's `csv_changes` the same way. It uses
  the bus rather than `wc.installedEvent`, which skips while the page has unsaved changes, and it
  reloads nothing.

This lands after the shell branch so the summary is one piece of code, not two. Tests: a case in
`tests/studio/e2e/data.test.mjs`, `after an install the changed cells say they are in the game`,
feeds a manifest through the bus; `tests/unit/test_studio_data.py::test_applied_changes_come_from_the_installed_build`.
No game needed.

### 6. Save edits are made once, recorded, and can be undone

Files:
- `wcmods/pipeline.py`, built on the shell branch's `install()` and `pending()`;
- new `wcmods/saverecord.py`;
- `wcmods/sections/savedit.py`, `wcmods/sections/cats.py`, `wcmods/formats/savejson.py`;
- `wcmods/studio.py` (`/restore`), `wcmods/cli.py` (`restore`);
- `wcmods/templates/save/save.json`;
- `docs/formats.md`, `docs/SDK.md`, `README.md`;
- new `tests/unit/test_savejson.py`, `tests/unit/test_save_format.py`, `tests/unit/test_savedit.py`,
  `tests/unit/test_save_apply.py`, on the tests branch's `tests/unit/conftest.py` (its sandboxed
  data folder keeps every `save-changes.json` a test writes out of the player's own folder).

**Format.** `save.json` keeps `set` and `add`, and gains two keys:
- `remove`: a list of paths to take out, such as an inventory entry or a seen scene.
- `always`: default false.

```json
{ "set": { "1/GameplayProgression/Level": 20 },
  "add": { "1/GameplayProgression/State/Inventory": { "Gameplay.Inventory.Consumable.SmallCatnip": 5 } },
  "remove": [ "1/GameplayProgression/State/Inventory/Gameplay.Inventory.Materials.Cobweb" ] }
```

An older wcmods ignores `remove` and `always` (`savedit.collect` reads only `set` and `add`).

**Once per save.** Each `set`, `add` and `remove` from a `save.json` (ops whose section is `save`),
and each change the Save page makes (step 7, source `studio`), is made once per save.
- `apply_save_ops` records what it did and skips an op it has already recorded with the same value.
- An op whose value the save already holds is recorded too (`was` equal to `value`), with no backup
  and no write, so a pile that is full now isn't refilled later.
- The rename, cat-look and controls ops other sections queue are left as they are, because each has
  its own guard. A rename checks the name it expects. Starting items use `only_new`.
- A mod's own `section.py` that calls `ctx.edit_save` or `ctx.add_save_key` keeps today's
  every-install behaviour; only `save.json`'s ops and the studio's are recorded.
- The record lives in `save-changes.json` in your files' folder, beside `wcmods.json` and
  palettes-cat's `cat-originals.json`: it is about this save, not a setting. It is written whole,
  then put in place, as the shell branch's `Config.save` does.
- `wcmods/saverecord.py` reads and writes it.

```json
{ "<account>": { "my-mod": {
    "1/GameplayProgression/Level": { "value": 20, "was": 5, "when": "2026-10-28T15:30:12",
                                     "backup": "20261028-153012-before-save-edits" } } } }
```

The record is keyed by:
- `SaveDoc.account`, the one top-level key in the save's JSON. It is one per player account, so
  another account's save starts clean. A cat started again in the same slot of the same save does
  not (Open question 3).
- Then by source (a mod id, or `studio`), then by path.

**When an edit is made again.**
- A mod whose value changes (Level 20 becomes 18) applies again, because the recorded value
  differs.
- `"always": true` in the file asks for today's behaviour (re-forced at every install), for a mod
  that means it.
- The record's `was` is what Put it back writes; for a key an add or set made new (`was` null), Put
  it back removes the key. Put it back marks the record `"undone"` instead of dropping it, so a mod
  that is still on doesn't make the change again at the next Apply.

**Restoring a backup.** `/restore` and `wcmods restore` call `saverecord.forget_since(<backup
name>)`, which drops every record made at or after the restored backup's time (a backup's name
starts with it: `20261028-153012-...`). The restored save doesn't have those changes, so the next
Apply makes the mods' ones again. That is what mods-setup step 7's "Apply puts your mods' save
changes back" promises. The studio's own changes go with the restore, as the player asked.

**Upgrading (no progress lost).** The first time this version installs, there is no
`save-changes.json`. Each mod that was in the last install (`installed.mods`) and whose files
haven't changed since (`pending()`'s rule: nothing in its folder newer than `installed.built`) has
its `save.json` ops recorded as already made: `value` is the mod's value, `was` is `null`, and
nothing is written for them. A player whose Level 10 mod was overridden by play to 14 therefore
isn't put back to 10 one last time. A mod turned on or changed since the last install applies as
usual, so an edit made on the old Save page just before upgrading still goes in. Done so far lists
the recorded ones as "made before this version", without Put it back.

**Reading the save safely.**
- `savedit.build` and `cats.build` return early when they have no items.
- They wrap the save decode in `try/except (ValueError, OSError)`, which warns "your save couldn't
  be read, so save edits were skipped" and carries on.
- `apply_save_ops` tells `install()` when there was no save, and `install()` records
  `installed.save_pending`.
- Once a save exists, `pending()` adds "save edits are waiting for a save" to `redo`, so the chip
  and Play say so.
- `install()` catches exceptions from `apply_save_ops`, logs them as a warning in the manifest, and
  still records the install.

**Removing.** `SaveDoc.delete(path)` removes a key and its comma (`_spans` learns where the entry
starts: the key's opening quote) or a list element. Removals run after the sets and inserts, and
list elements go from the highest index down so earlier indexes stay valid.

**Ranges.** A small range table in `savedit.py` makes `build()` warn and skip an out-of-range value
rather than write it:
- `Level`: 1 to 20;
- `Experience`, `Health`, `Stamina` and inventory counts: at least 0;
- `FreshKill/Value`: 0 to 100;
- volumes: 0 to 1.

**Words in the log.** `savedit.build` gives each op a `label` while the build can still read the
game, the way the name and look ops carry theirs:
- cats are named through `names.cats_in_save` and `names.Plan(GameNames(...), <the build's names
  spec>).current_name(ids)` (as `CatsSection._plan` builds it);
- items are named from `DT_QuestObjectsInfo` through `ctx.cooked_table` and `ctx.text`;
- when the game's tables can't be read, the label is the path, as today.

`apply_save_ops` then logs "Fawnstar's level: 5 -> 20", not a path.

**The template.** It ships empty `set` and `add`, with a `_help` that points at the studio's Save
page instead of turning the minimap on.

Tests:
- `tests/unit/test_savejson.py`: `test_set_changes_only_its_span_on_every_value_type`,
  `test_set_many_in_one_parse_and_nested_paths_refused`,
  `test_insert_into_empty_and_non_empty_objects_keeps_crlf_and_indent`,
  `test_delete_removes_the_entry_and_its_comma`, `test_delete_list_elements_from_the_end`,
  `test_exists_and_get_with_array_indexes`, `test_a_key_with_a_slash_is_unreachable`,
  `test_two_top_level_keys_is_an_error`.
- `tests/unit/test_save_format.py`, with fixtures from `selftest._small_save`:
  `test_not_a_save_and_no_compressed_data_raise_value_error`,
  `test_a_truncated_archive_raises_value_error`, `test_to_bytes_keeps_everything_around_the_payload`,
  `test_write_save_replaces_the_sav_whole_and_mirrors_json`,
  `test_backup_names_never_merge_and_restore_copies_every_file`.
- `tests/unit/test_savedit.py`: `test_collect_shapes_and_help_key`,
  `test_build_with_no_items_and_an_unreadable_save_does_not_raise`,
  `test_build_warns_and_skips_missing_paths_and_out_of_range_values`,
  `test_remove_queues_a_delete_op`, `test_ops_carry_a_label_in_words_or_their_path`.
- `tests/unit/test_save_apply.py`, over a temp save folder:
  - `test_a_matching_set_is_recorded_without_a_backup`, `test_a_changed_set_backs_up_writes_and_records`;
  - `test_applying_again_after_the_save_moved_on_leaves_it` (Level 14 stays 14),
    `test_a_changed_mod_value_applies_again`, `test_always_re_forces`;
  - `test_insert_only_new_and_remove`;
  - `test_names_look_ops_and_a_sections_own_edit_save_are_not_recorded`;
  - `test_the_first_install_after_upgrading_records_unchanged_mods_and_applies_changed_ones`;
  - `test_restoring_a_backup_forgets_the_records_made_after_it`,
    `test_an_undone_record_is_not_made_again`;
  - `test_no_save_marks_save_pending_and_pending_says_so`,
    `test_a_failing_apply_still_records_the_install`.

Docs:
- `docs/formats.md`'s `save.json` section says:
  - paths start inside the account object;
  - `0` is a cat slot, and `Shared/General/CurrentCatSlot` says which slot is being played;
  - `set` needs an existing value; `add` adds or sets; `remove`;
  - edits are made once per save, and `always` overrides that;
  - restoring a backup lets the edits made after it apply again.

  The docs-guide plan's rewrite of that section takes this text. A new short section describes
  `save-changes.json`.
- README's Save row and the cheats paragraph say that edits are made once, and that turning the mod
  off leaves the save as it is.
- `docs/SDK.md`'s `edit_save` and `add_save_key` rows say a section's own ops are still made at
  every install (only `save.json`'s are once per save), and that a section's save ops are dropped
  when its table edits fail.

No game needed. The codec is untouched.

### 7. Change my save now, Put it back, and Done so far

Files: `wcmods/studio.py` (routes), `studio/sections/save.js`, new `studio/lib/save.js` (pure
helpers), new `tests/unit/test_studio_save.py` and `tests/studio/e2e/save.test.mjs`.

**`POST /api/save/apply`.** It takes:

```json
{ "changes": [ { "path": "1/GameplayProgression/Level", "value": 20 },
               { "add": "1/GameplayProgression/State/Inventory", "key": "Gameplay.Inventory.Consumable.SmallCatnip", "value": 5 },
               { "remove": "1/GameplayProgression/State/Inventory/Gameplay.Inventory.Materials.Cobweb" } ] }
```

- It refuses while the game runs, as `/restore` does, and says "No save yet: start the game once"
  when there is none.
- It builds ops with source `studio` and labels from the Studio's readers.
- It runs `pipeline.apply_save_ops` through `Studio.run`, under the lock installs take, so the
  backup comes first.
- It answers, through `Studio.run`, `{"log": [...], "result": {"applied": [{"path", "label", "was",
  "now"}], "backup": "<name>"}}`.

**The other routes.**
- `POST /api/save/undo {"source", "path"}` refuses while the game runs. It writes the recorded
  `was` back (or removes a key that was new) after a backup and marks the record undone. It answers
  what the save held just before, so the page can say what changed.
- `GET /api/save/applied` lists the records for the save's account, newest first, with their labels
  and whether each can be put back.
- `GET /api/save` adds `current_cat` (`{slot, name}`). The name comes from the same names lookup
  `Studio.cat_info` uses (`names.Plan(...).display`, `studio.py:593-602`), and from the slot number
  when the game's names can't be read. It also adds `game_running`.

**UI.**
- The modTarget stays, but moves into the "Keep it as a mod to share" fold, so the main flow needs
  no mod.
- The pending list lives in `studio/lib/save.js`, which also turns it into the route's `changes`
  and into a `save.json` for the fold. It is kept across page switches in `sessionStorage` (a
  per-viewer convenience). The page asks before the window closes while the list has entries. The
  mod bar is not marked dirty, since nothing in the list goes to a mod until the fold's Save to mod.
- "Change my save now" is the primary button.
- The Done so far card has Put it back. When the save's current value differs from the recorded
  `value`, Put it back confirms with both numbers first.
- A status line shows while the game runs.
- After a change, the page fetches the save again and re-renders in place. On
  `wc.bus.on("installed", ...)` (an Apply from the top bar may have made mods' save changes) it reads
  `/api/save` and `/api/save/applied` again; the Changes to make list stays.

Tests:
- `tests/unit/test_studio_save.py`, with the harness's `studio` and `save` fixtures:
  `test_apply_refuses_while_the_game_runs` (the sandbox's `running`),
  `test_apply_backs_up_writes_and_records`,
  `test_undo_writes_the_old_value_and_marks_the_record`, `test_undo_of_an_add_removes_the_key`,
  `test_applied_lists_newest_first`, `test_save_without_a_file_is_a_404_in_page_words`,
  `test_save_names_the_current_cat`.
- `tests/studio/e2e/save.test.mjs`, over a temp save: `a preset adds to the list in words`, `Change
  my save now writes and shows the change under Done so far`, `Put it back restores the old value`,
  `Put it back asks first when the save moved on`.

Game: one manual check that a save changed this way loads and keeps the change, and that an item
taken out with `remove` is gone from the inventory screen. It uses the same codec path that
`docs/verified.md:44` already records.

### 8. The Save page in plain words

Files: `studio/sections/save.js`, `studio/lib/save.js`, `studio/sections/save.css`,
`studio/sections/mods.js`, `docs/guide/save.md` (written by the docs-guide plan), `README.md`,
`tests/studio/save.test.mjs`, `tests/studio/e2e/save.test.mjs`.

**The head.** `wc.pageHead({title: "Save", lede, help: "help:save"})`.

**Your cat.**
- "Your cat: Fawnstar" with Level, Experience and Fresh-kill pile. Each enforces its range, with a
  toast when a typed value is outside it.
- Experience says what the next level needs ("of 230 for level 6"), from TuningData's
  `Gameplay.Exploration.Level.<n>` rows.
- The quick fields update in place, without a rebuild, so Tab moves on.
- The presets: Max level, with the rank line; Fill the fresh-kill pile, to 100, the cap; Give herbs.
- When the slot has no `GameplayProgression` yet: "This cat hasn't started yet: play once, then
  come back."

**What it carries.**
- The inventory by name and icon, from `/api/game/items` and `/api/game/icon?of=`, grouped Herbs
  and catnip, Materials, Accessories (the items' `kind`).
- Remove on existing rows (the `remove` op).
- An Add picker that says "can't list items: the game folder isn't set" when the items can't be
  read. An accessory is added once.
- An add for an item the save already has becomes a set of its count.
- "Also in this file: cat slot 1 (Mothpaw): Level 10" lines for edits under other slots.

**Advanced.**
- **The tree:**
  - a search box that opens matching paths;
  - "Show more" instead of the 400-key cap;
  - open groups and the focused id remembered across a rebuild (or the changed row's chip updated
    in place);
  - no rounding (the quick fields keep theirs);
  - element ids from a counter, not the path.
- **Read-only rows:**
  - everything under `Shared/InputKeyboard`, `Shared/InputGamepad` and any `*/Customization`, with
    a pointer to the right page;
  - strings that look like struct text `(A=1,B=2)`;
  - keys with a `/` in them, which a path can't reach;
  - Health and Stamina, with the line about refilling in play.
- **The Combat stats card**, with its note reworded: "When a fight starts the game works out stats
  from Level, so a change here may not last." Fields it can't read as `name=number` are kept as
  they are, and a cleared box is refused rather than written as 0.
- **The `save.json` panel.**

The Settings card is dropped (Open question 5), and the dead `delete edits.set._help` goes.

**The error card.** Its title says the cause:
- "No save yet: start the game once and come back" for a missing file;
- "Couldn't read your save" for anything else, with a Try again button and a pointer to backups.

**The Mods page.** Turning off a mod with a `save.json` (its `kinds` has `save`) adds to the toast:
"Its changes to your save stay; the Save page's Done so far puts them back." That is where a
creator looks first when undoing.

Tests:
- `tests/studio/save.test.mjs` (units over `studio/lib/save.js`): `a range clamp refuses -5 and
  999999 for Level`, `a preset expands to the right paths and values`, `describe turns a path into
  words`, `the read-only rule covers bindings, cat records, struct text and slash keys`, `an add for
  an item the save has becomes a set`, `the stats card keeps fields it can't read`.
- `tests/studio/e2e/save.test.mjs`: `a typed 0.5 in a tree box at 1 is kept`, `open groups stay
  open after a change and focus stays in the page`, `Tab from Level moves to Experience`, `a binding
  row is read-only with its note`.

Docs:
- `docs/guide/save.md` (the docs-guide plan's page) gets a new "made once" and "Put it back" part.
  Its "undo" part changes from restoring a backup to Put it back.
- README's Save row.

No game needed.

### 9. Closing the loop

Each item lands with the PR named:
- `docs/verified.md`:
  - "Game data tables in play" moves to Confirmed, with the agent tests' names, in the in-game
    verification PR;
  - the Save paragraph says edits are made once and can be put back (step 7's PR).
- `docs/mechanics/README.md` says the Game data page quotes these notes (step 3's PR).
- README's command list says the `tables` command is the colour tables, not these (step 1's PR,
  alongside the template text).

## Backward compatibility

- **`data.json`:** the shape is unchanged.
  - One change in result is a named row before `"*"` on the same column, which now gives the
    row's value, as the page always showed. The build warns about it for one release (step 1).
  - The other is text in a cell that held a number: the game's number is kept and the build warns,
    where before the text went into the table.
  - The examples (`double-xp`: `"*"` only; `npc-size-variety`: named rows with numbers as strings)
    and `ctx.tune` users (`faster-run`) build exactly as before.
- **`save.json`:** `set` and `add` are unchanged, and `remove` and `always` are optional.
  - The behaviour changes from "every install" to "once per save".
  - The first install of this version records the edits of unchanged, already-installed mods
    without writing, so no player loses progress to the change.
  - A mod that needs the old behaviour adds `"always": true`.
  - An older wcmods ignores the new keys.
  - A mod's own `section.py` save ops keep the old behaviour.
- **New files and routes** are additive. A missing `save-changes.json` is an empty record.
- **Shared code:** `wcmods.json` is unchanged apart from `installed.save_pending`.

## Not in this plan

Judged known-impossible, with the reason:

- **Damage and trait fixes as data** (making Resilience reduce damage, giving Patient a real bonus,
  adding a new tuning key): the damage code reads the Attack column for the defender, Patient
  appears in no key the exe uses, and the game reads only the keys it asks for
  (`sdk.py:208-210`). These need Lua or code mods.
- **Key bindings through the save:** the game keeps a copy of the bindings in the save and ignores
  edits to it (`README.md`, Remapping keys). The Controls page is the way.
- **Giving items while the game runs:** nothing reflected reads or writes the inventory TMap
  (`reverse-engineering.md:544-549`), so items stay a save edit made with the game closed.

Judged needs-re, with what is missing:

- **One-click fixes for the game's own data bugs** (the `...Bonus.Abundantv` row, the Cobweb gift,
  the missing Curious fresh-kill rows): `csvdata` refuses row renames, and the Abundant row's reader
  has not been traced.
- **Dialogue answer scores** (QuestDialogues and StoryDialogues `Score`): the quest code has not
  been read, so what the number feeds is inferred.
- **A traits editor in the save:** it is unknown whether the game re-derives traits from body, ears
  and face on load.
- **Promoting the cat's rank, or setting its size by rank, in the save:** where rank is stored is
  not documented, and whether the RankUp quests check it is unknown.
- **Re-watching story scenes or resetting a quest:** `QuestProgression`'s layout is unknown. Removing
  a `Sequences` entry becomes possible with step 6's `remove`, but its effect is unchecked.
- **Copying a cat to another slot:** what the GVAS `saveSlots` property holds is unknown.
- **Time of day, or where the cat stands:** both are runtime state, not save values. The Travel page
  and scripts change them live.
- **A "read by the game" column on TuningData:** about half of the 441 keys are not in the exe as
  whole strings. Finding which ones Blueprints read needs the tuning-manager probe described in the
  audit's RE gaps.
- **Whether the game reads the saved Stats or rebuilds them from Level** (and whether Health and
  Stamina are restored or reset): it decides whether the Combat stats card does anything. It stays
  under Advanced with its note until a save edited three ways is checked through the bridge.
- **When each table is read** (at start, per fight, or copied into the save as NPC looks and moves
  on the AttackBelt are): it decides which quick rows need "from now on" or "a new cat". The NPC rows
  say it already.
- **What the den-visit server does with a changed `VisitRewards` or `OnlineGifts`:** the online
  chip says only "may ignore this" until the endpoints are traced.
- **What some quick-row numbers mean:** whether `Gameplay.Exploration.Level.<n>` is per level or a
  running total, whether `BuildTime` is real hours, and what `DayNight.ClockSpeed` means in minutes.
  Each needs the save diff or in-game check the audit names. Until then the quick rows for those say
  what is known and no more.
- **What the game does with out-of-range save values:** step 6's range table guards against them
  until someone checks.

Known-possible, but larger than this plan; for later cards on the Game data page:
- a move editor with English names (AttackMove, 185 rows);
- enemy difficulty and rewards per animal;
- herb strengths (GenericEffect params);
- the stance grid and status numbers;
- den decoration material costs (the `Cost` column is a text list, so it needs its own editor);
- per-level XP as a draggable curve;
- clan looks as per-option weight editors (the NPC tables keep their weights as tuples in one cell);
- a "Game data" page in the in-game mod menu that shows the values the game loaded (a Menu pages
  mod page, once the in-game check says which tables reach the game).

Live changes to level, health and stats while playing belong to the Menu pages mod, not here.
Pruning save backups, and a Restore that says how much play it goes back over, belong to the
Settings and repair page.

## Open questions

1. **The fixed order.** Step 1 (`"*"` first, named rows override, a one-release warning) changes
   the result for a hand-written file where a row edit came before `"*"` and was meant to be
   multiplied. Accept that as the one rule, or keep key order and make the page write `"*"` first?
2. **Who gets once-per-save.** Should it be the default for every `save.json`, downloaded mods
   included, with `"always": true` the opt-out, or apply only to files the studio writes?
3. **A new cat in an old slot.** Records are keyed by the save's account, so a cat started again in
   the same slot keeps the earlier record and doesn't get the edit again. Accept, add a "Make it
   again" on Done so far, or tie the record to the slot's cat (its name IDs, which a rename
   changes)?
4. **Mods and packs.** The plan's main path writes no mod (Change my save now), with `save.json`
   only under the sharing fold. Should `save.json` also stay out of `.zip` packs unless the creator
   opts in?
5. **The settings card.** The plan drops it from the Save page (the game's own Gameplay settings do
   it in seconds, and the tree still reaches the keys). palettes-cat step 13 links "the Save page's
   Injury system switch" from the Scars card: with the card dropped, that line points at the game's
   own Gameplay settings (as `cat.js:272` already says) or opens the Advanced tree's search at
   `Shared/SettingsData/InjurySystem`. Keep the card (or that one switch) under Advanced instead?
6. **The day-and-night clock.** Show it as a quick row with "higher is faster" before anyone has
   measured a day, or leave it in All tables until then?
7. **Map data tables.** The plan keeps the HeightMap and UniqueIds tables hidden and shows only the
   "this mod also edits" line. List them under "Map data" with a warning instead?
8. **Levels.** One "faster or slower" factor over the nineteen rows, or a per-level editor from the
   start?
9. **Rounding.** A multiplier on a whole-number cell can give a decimal (the template's x1.5 makes
   Mice 37.5). Whether the game reads a decimal in a whole-number column is unchecked. Should
   `format_value` round results for whole-number originals, or leave them?

## Changes from the review

- **Step 1:**
  - A named row's own `xN` now multiplies the value before `"*"`, so the Levels quick row and a
    `"*"` can't compound. `valueFor` follows.
  - A one-release warning flags files whose result changes.
  - Numbers written as strings stay valid, and a `"-"` string is one row.
  - The `check_file` wiring moved to step 3, because the shell's `check_file` reports only what
    `collect()` raises.
- **Step 2:**
  - It no longer moves `chip()` into `wc.js`. The shell and look branches rewrite `app.js` and
    `wc.js`, and visible chip text removes the need.
  - Its browser tests moved to step 3's PR, which depends on the tests branch.
  - It covers the audit's medium UX issues the plan had left out: the TuningData multiplier
    footgun, chance columns, booleans and fixed-word columns, grid keyboard use, and Put this table
    back.
  - Map data stays hidden, the simpler default.
- **Step 3:**
  - The docs write short keys and patterns, and give no key for walk or run speed. So notes are
    matched by suffix and pattern, and the docs gain the missing keys.
  - `pageHead` help is `"help:data"`.
  - The index route is matched before the table route.
- **Step 4 and the in-game check:**
  - `negate` for the drain rows, and the NPC rows say "from now on".
  - `agent.move` walks, so the agent test measures the walk row by distance.
  - Fight XP is a manual check, because finding an animal needs a forbidden world scan.
- **Step 5:**
  - `wc.bus.on("installed")`, not `installedEvent`, which skips while dirty.
  - Net change per cell.
  - A "Your changes" card.
- **Step 6:**
  - The record moves to `save-changes.json` beside palettes-cat's `cat-originals.json`, through
    `saverecord.py`. It covers only `save.json` and the studio's ops.
  - The first install after upgrading records without writing.
  - Restore forgets later records, which matches mods-setup step 7.
  - Put it back marks a record undone instead of dropping it, so a mod that is still on doesn't
    re-apply it.
  - Labels are computed at build.
  - The account key is described accurately: one per account, not one per save.
  - `current_name` lives on `names.Plan`, not `GameNames`.
- **Step 7:**
  - Undo takes the source.
  - The name lookup is `Studio.cat_info`'s.
  - The pending list doesn't mark the mod bar dirty.
  - Put it back confirms when the save moved on.
- **Step 8:**
  - Health and Stamina left the main card and the Full health preset was dropped, since both refill
    in play.
  - Max level says the rank stays.
  - The Settings card is dropped by default.
  - The guide pages belong to the docs-guide plan.
- **Other:**
  - "My mods" is the default mod, not "My tweaks".
  - The step-6 PR now builds on the shell branch, which rewrote `install()` and `pending()`.

## Changes from the second review

Checked against `audit/data.json`, `audit/save.json`, the 17 verdicts, the code on 3af2898, and the
`claude/studio-tests`, `claude/studio-look` and `claude/studio-shell` branches. Every listed bug is
confirmed and at the file:line the verdicts give; no high bug or high UX issue was missing.

- **Test layout:** the tests branch puts `node:test` units at `tests/studio/<name>.test.mjs` and
  browser tests in `tests/studio/e2e/`, with `tests/studio/lib/` for its helpers. Every test path
  here follows it. The Game data e2e fixture game is a `PakWriter` pak holding three tables and
  `Strings_EN.csv`; the pytest ones use a stub game on the harness's `studio` fixture.
- **Step 1:** a `story` kind for the dialogue and quest tables (the audit's half-finished item, in
  `files.py`, with both build warnings and a page chip); `"*"` over non-numbers is one problem per
  column; README's `tables` line and the template are in its file list; Backward compatibility names
  the text-in-a-number-cell change.
- **Step 2:** a dropdown needs repeated words, so a small table's name column stays free text. The
  grid warns, not refuses, when a factor takes a 0-to-1 column past 1, since CatSize's 0.1-1.0
  scales would be refused as "chances"; the quick rows marked `chance` still refuse.
- **Step 3:** `units` in the titles file, for the audit's "headers carry no units".
- **Step 4:** the selftest checks the quick rows, titles and notes against the installed game; the
  "how sure" words are plain ("Checked in game", "Not checked in game yet").
- **In-game check:** in-game tests can't install while the game runs, so the mod is a repository
  folder, `tests/data-speed/`, installed before `agent test --launch`, with a `setup()` that skips
  otherwise (as `test_cpp_sdk.py` does). The acceleration rows go up for walk and run, since at
  175 cm/s² a 3 s run to 800 covers about what the game's own run does. The run row is measured
  with `agent.keys(..., "LeftShift")`, and `MaxWalkSpeed` is reported, not asserted. `docs/agent.md`
  is in the PR.
- **Step 5:** `GET /api/game/data/applied`, so the "in the game" marks show on a page opened after
  the Apply, not only during it.
- **Step 6:**
  - The upgrade records only mods that were installed and haven't changed since; a mod changed on
    the old Save page just before upgrading still applies.
  - An op the save already matches is recorded, so a full pile isn't refilled later.
  - `forget_since` compares times.
  - Put it back of a new key removes it.
  - Labels fall back to the path.
  - A section's own `ctx.edit_save` is unchanged.
  - palettes-cat plans `catorig.py`, not a shared helper, so the two files are kept apart until
    one plan lands second.
  - The PR depends on the tests branch's sandboxed fixtures as well, and is large.
- **Step 7:** the answer comes through `Studio.run`'s `{log, result}`; the page re-reads after an
  Apply; tree edits join Changes to make; the manual game check covers `remove`.
- **Step 8:** the next level's XP beside Experience, a stats card that keeps fields it can't read,
  read-only `/` keys, and a Mods page toast for a save mod turned off (the audit's high "no undo"
  issue asked for it).
- **Cross-plan:** palettes-cat's Injury system link (Open question 5), and backups that pile up
  faster, handed to the Settings and repair page.
- **PRs:** the first no longer lists `app.js`, `wc.js` or a browser test, and adds `files.py`, the
  template and README. The in-game PR adds the test mod and `docs/agent.md`. The page PR adds
  `wc.js`, the selftest, the mechanics pages and its e2e files. The save pipeline PR adds
  `saverecord.py`, `studio.py` and `cli.py`, and depends on the shell and tests branches. The Save
  page PR adds `mods.js` and its e2e file, and drops `formats.md`.
