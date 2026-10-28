# Looks: the Palettes and Your cat pages

A plan for the two pages that change how cats look: Palettes (`studio/sections/palettes.js`, `palette.json`) and Your cat (`studio/sections/cat.js`, `cats.json`). It comes from the 2026-10 audit of both pages (the maps `palettes.json` and `cat.json`, checked by a skeptic) and from reading the code behind them. Some work is already under way and is taken as given here, not planned again:

- **The shell** (branch `claude/studio-shell`, no PR yet):
  - `Studio.check_file` runs the owning section's `collect()` at Save and answers `problems` (sentences) that show under the Editing-mod bar.
  - The dirty guard: the browser asks before the page closes; a mod switch offers Save and switch, Switch without saving, or Stay; `modTarget` exposes `dirty`, and `save()` answers true once saved.
  - `wc.installedEvent(target, fn)` skips `fn` while the page is dirty.
  - Help panels at `/help/<page>` open from `wc.pageHead({eyebrow, title, lede, help: "help:<page>"})`.
  - Errors are reworded for creators.
  - It does **not** ask before the top bar's Apply or Play when a page has unsaved changes, and it emits no status event. Pages read `/info` themselves.
- **The new look:** "Leaf and Bark", PR 74. It adds per-page stylesheets that `app.js` links from its `PAGE_STYLES` list, keeps rules shared by two or more pages in `styles.css`, and adds `wc.pageHead`.
- **The test harness** (PR 75):
  - `tests/unit/conftest.py` has the `studio`, `fake_game`, `save`/`write_save` and `make_mod` fixtures, and `sandbox.running` to make the game "run".
  - `tests/studio/lib/dom.mjs` is a DOM shim, so node can import `wc.js`. `tests/studio/lib/browser.mjs` is the Chromium driver.
  - Node units live in `tests/studio/<module>.test.mjs`.
  - Browser tests live in `tests/studio/e2e/<page>.test.mjs`. They run a real studio over a temp data folder and a made-up game folder.

Other plans touch the same code, and this one fits them:

- **docs-guide** (`docs/plans/docs-guide.md`, section 4) writes `docs/guide/palettes.md` and `docs/guide/cat.md`. The steps here add to those pages and do not create them. The guide pages use the pages' words ("colour 3"). The glossary's "slot" entry is for people reading the files.
- **data-save**:
  - Its step 3 makes `check_file` pass on `collect()`'s warnings and show them under their own heading. Step 4's notes use that.
  - Its step 6 adds `wcmods/saverecord.py` (records of save edits beside `wcmods.json`, keyed by the save's account). It also guards `cats.build`'s save decode and reworks `apply_save_ops`. Step 15 builds on it.
  - Its step 7 names cats the way `Studio.cat_info` does. The changes to `cat_info` here only add keys.
- **mods-setup**:
  - Its step 1 adds mod.json's `"wcmods"` minimum and makes `__version__` 0.4.0.
  - Its step 3 adds `GET /addons`, the Add-ons card and a Creator palettes note on the Palettes page. Step 8's Creator palettes line is that note: one note, not two.
  - Its step 8 releases Creator palettes 1.2.0.
- **console-lua** fixes two things in the in-game Lua: `menu.lua`'s encoder (an empty list stays `[]`, and floats keep their digits), and `Game.json.decode` skipping a UTF-8 BOM. Step 14 is safer with both but doesn't wait for them.

Two open PRs cover the cat choice's picture bugs, so this plan leaves them out:

- **PR 70** (`catcolours.lua`): the crash on a part with no mesh yet, and your colours on other saves' pictures.
- **PR 72** (`models.lua`).

## What it is for

A creator wants to make the game's cats look the way they imagine. That means recolouring the eyes, coats, patterns and markings every cat can wear, adding colours of their own, and giving their own cat (or a named clan cat) a look nobody else has, all without opening a file. They should be able to see what they will get before they press Apply, and to put things back when they change their mind.

## Where it stands

**What works, and how it was verified.**

- **Eyes:** eye recolouring works offline through the patched eye atlas (`wcmods/eyeatlas.py`, `palettes.apply_eyes`). It was seen in game on 2026-10-23 (docs/verified.md).
- **The runtime tables:** the WCModsCore script (`wcmods/lua/palettes.lua`) rewrites them about two seconds after launch, and the game takes the writes. The pattern and marking tables grow past 25, and slot 25 reads back with its new colour (reverse-engineering.md, Colours). The script logs the game's own tables before it patches them.
- **Your cat's own colours:** `cats.json` `colours` show on your cat, the main menu and thumbnails (verified 2026-10-23).
- **The Your cat page and its build:**
  - The page round-trips a file it made carefully (`parseOne`/`oneJson`/`toJson`).
  - The build validates thoroughly: `catcolours.validate`, 18 collected unit tests in `tests/unit/test_cats.py`, plus `selftest._colour_slots` and `_scars_build`.
  - Slots, scars and shape go into the save through `fields` ops (`pipeline.apply_save_ops`, after a backup).
- **The Palettes page and its backend:**
  - The page's tab list works fully from the keyboard.
  - The backend validates and lists coat presets: `palettes._coats` and `slot_groups`, with 15 collected tests in `tests/unit/test_palette_groups.py`.
  - The Creator palettes mod reads the shared Lua module `WCModsPalettes`.

**What is half-finished.**

- **Coat presets have no page.** They have a format, docs and an in-game reader (Creator palettes 1.2). A file's `coats` ride along unseen in the page's `kept` bucket. "Start from" another palette says "Copied" without copying its presets.
- **The page never names the Creator palettes mod**, which is the only way new colours reach the cat maker.
- **wcmods 0.3.0 refuses a palette with `coats`.** The released version says "unknown palette section", and that stops the whole install until the mod is turned off. The page doesn't say so.
- **The Coat, Pattern and Markings tabs are empty until the game has been played once with the script loader.**
  - Nothing ships `colour_tables.json`. Only `python wcmods.py tables` writes it, into the repository folder, and the .gitignore keeps it out as game data that is "not ours to redistribute".
  - In the same state, the Your cat page's slot swatches are grey numbered squares.
  - Without a game folder, the Palettes page doesn't open at all (`/game/eyes` fails).
- **`iris_ui` is a backend-only section** that nobody documents.
- **The Restyle moods** touch only the 20 standard eye rows.
- **The "DLC eyes"** come with no word on which add-on they belong to. The docs name the Feral Edition only for coats 20-24.
- **Two runtime claims are unconfirmed:** coat colours on screen, and a cat wearing a new slot, are still under "Not yet confirmed in game" in verified.md. Neither page says so.
- **On the Your cat side:**
  - Nobody has seen the in-game Colours page's Save round-trip.
  - The cat list's `role` is sent and never shown.
  - `appearance_only` is declared and never read.
  - Other save slots' cats are documented but can't be reached from the page.
  - `debug_cat_look` is a hand edit to wcmods.json.
  - The scar labels past the first eye scar and the claw marks were read off a texture, not seen in game.

**Confirmed bugs.** Each has the skeptic's severity, and the correction where the audit's claim was narrowed. The steps below refer to them by number.

1. [high] `studio/sections/palettes.js:224`: the "installed" listener calls `target.refresh()`, which reloads `palette.json` and replaces `state`. Any Apply to game, Play or Quick palettes Apply throws away unsaved colour edits without a word, and the game gets the old file.
2. [medium, was high] `studio/sections/palettes.js:109`: `fromPalette` parses colours with `color.normHex` (3- or 6-digit hex only). A hand-written palette can use names ("orange"), `[r, g, b]` lists or 8-digit hex, all of which `wcmods/colors.py:parse` accepts. The page loses those entries on load and on the next Save. The "iris03" part of the claim was refuted (`eyeRow` resolves it to row 3).
3. [medium, was high] `wcmods/eyeatlas.py:66`: `EyeAtlas.slot` returns the number in "row26", "iris99" or "30" without a range check, and the section guards only `KeyError`. `apply_eyes` then raises `ValueError("bad row")` or `struct.error`. That fails the whole palettes section for every mod, with a message that names neither the mod nor the key.
4. [low, was medium] `wcmods/palettes.py:156`: `merge` keys eye entries by their raw string. With three or more palettes naming the same row two ways ("Amber" and "iris2"), a middle mod's spelling can be applied last and win over the highest priority. Two palettes always resolve correctly, and palettes made on the page and the examples use labels.
5. [medium] `wcmods/studio.py:384`: the PUT file route only checks that the text is JSON.
   - A palette imported or copied with a fur slot of 25 or more saves with a success toast. The fur slot is kept unseen in `state`, because the Coat tab draws slots 0-24 only.
   - So does one with an unknown top-level section, which is kept as written.
   - Both fail only at Apply, and the page offers nothing to remove.
6. [low, was medium] `studio/sections/palettes.js:211`: the Quick palettes "Apply N and install" button stays enabled while the game runs or no game folder is set, unlike the shell's buttons. Pressing it shows the server's clear error, so this is polish.
7. [medium] `studio/sections/palettes.js:237` (Game colours at `:228`): Reset tab (the only undo for the Restyle moods) and Game colours also clear the tab's new slots (25 and up), with no confirmation.
   - After Save and Apply, a cat set to one of those slots shows no colour.
   - Re-adding gives the lowest free number. That is a different slot when another palette holds higher ones.
8. [medium, was high] `wcmods/studio.py:618`: `cat_info` catches `LookupError` only. A `WrcGame.sav` that exists but can't be decoded (zero bytes, half-copied, read while the game writes it) raises `ValueError`. GET /cat then answers 400, and the whole Your cat page becomes "Your cat couldn't load" with wcmods' internal message. The colours card goes with it.
9. [high] `wcmods/sections/cats.py:37`: the build embeds the top mod's `cats.json` as it was at build time.
   - The in-game Colours Save (`catcolours.lua:225-233`) writes that whole copy back with only `player.colours` replaced.
   - The Your cat page never re-reads the file: it has no focus or installed listener, and there is no mtime check on PUT.
   - So edits saved in the studio after an Apply are lost by the game's Save, and the game's Save is lost by the page's next Save to mod.
10. [medium] `studio/sections/cat.js:143`: some file keys the build resolves don't match on the page: a place without "Clans/", a name in another case, a name from before a Names-page rename, a name that stopped being unique. The page lists such a key as "(not in the game you're playing)" with no "now" values, and the cat it changes shows as unchanged.
11. [medium] `wcmods/studio.py:386`: `cats.json` is never validated at Save or Import.
    - An unknown slot, look or part name saves with a green toast.
    - It then fails at Apply: "not installing because some mods didn't build: ... player.slots.coat should be one of ...".
    - The page keeps writing the key back and offers no way to see or remove it.
12. [low, was medium] `studio/sections/cat.js:69`: a colour written as a name, a list or 8-digit hex is dropped on load and gone after the next Save. The other values the claim said were dropped are ones the build rejects anyway.
13. [medium] `studio/sections/cat.js:39`: `/cat` is fetched once in `mount`. After Apply, the "now: slot 11 (kept)" labels and the "now" ring keep the pre-install values until the browser page is reloaded.
14. [low, was medium] `studio/sections/cat.js:213`: every slot swatch is a grey square with a number until the game has run once after an Apply with the script loader, and the page doesn't say why. The eye rows use the cat maker's `IrisColors` button colours rather than the atlas rows `/game/eyes` serves.
15. [low, was medium] `wcmods/sections/cats.py:36`: the in-game Save target is the last enabled mod with a `cats.json`, whether or not it sets player colours. With a downloaded cats mod above My mods, the colours land in the downloaded mod's file.
16. [low, was medium] `wcmods/lua/catcolours.lua:139`: player colours go on whichever save slot's cat is played, while slots, scars and shape go only to the slot that was current at install. formats.md says "player" is "your cat, in the game you're playing" for both.

Two more confirmed bugs belong to PR 70 and are not planned here:

- [high] `catcolours.lua:77`: painting a part before it has a SkinnedAsset can crash the game while the cat choice loads.
- [medium] `catcolours.lua:161`: retaking every painted menu actor writes your colours into another save's thumbnail.

**Likely but unchecked.** These are the audit's low bugs, which the skeptic did not verify:

- **Palettes:**
  - The word "null" shows between the Quick palettes note and its tiles (`palettes.js:220`, `clear(quick).append(null)`).
  - "Add a new colour" can pick a slot another palette already uses when clicked before `loadOtherSlots()` finishes (`palettes.js:139`).
  - The preview's Coat/Pattern/Markings dropdowns go blank after "Show slot 25 on the cat" (`palettes.js:278`).
  - The eye groups are hard-coded to 26 rows (`palettes.js:64`).
  - Re-renders throw keyboard focus to the top of the page on Add, Remove, the gradient's stop buttons and the mode chips (`palettes.js:330`).
  - The preview colours whiskers with the marking colour, and ears and nose with fixed CSS colours (`palettes.js:266`).
- **Your cat and the build:**
  - The Scars card's two buttons throw keyboard focus the same way (`cat.js:267`).
  - `set_fields` mangles an exponent-form value, and silently does nothing when the struct text does not end in ")" (`catcolours.py:221`).
  - The build accepts back scars 5 and 6, but the page calls them "not a scar the game has" (`catcolours.py:82`).
  - A cat renamed and reshaped in one install logs only one of the two (`pipeline.py:571`).
  - A dotted look key gets a garbled message (`catcolours.py:158`).

## What a creator should be able to do

**Palettes.**

- **Every tab works from the first open.** The game's 25 colours per table come from the game's own files where they can be read. Otherwise they show as numbered cards that still take a colour, until the first Play fills them in. Without a game folder, only the Eyes tab waits ("Find the game first").
- **A "What reaches the game" note** sits under the page head. It shows only what needs something, each with its one action:
  - coats, patterns and markings: "need the script loader: Get set up, on the Mods page, installs it";
  - new colours and coat presets in the cat maker: "need the Creator palettes mod", with the Add-ons card's Add button; or "Creator palettes is off"; or "mods that run code aren't allowed (Settings and repair)".

  When everything is ready, it is one quiet line: "Everything here reaches the game. Last applied <time>."
- **"Switch between ready-made palettes"** is its own folded card (today's Quick palettes). One sentence says that its Apply turns the ticked palettes on, turns the other palette-only mods off, and installs.
- **Then come:**
  - the Editing mod bar;
  - a "Start from" row (Game colours, and each other palette);
  - a "Restyle this tab" row (the four moods and Reset tab);
  - one Undo for the last of those whole-tab changes ("Undo Vivid").
- **The preview card** shows the drawn cat with a two-option switch, "Cat shows: my colours / the game's". A caption says that paws, ears, nose and whiskers follow the coat in the game.
- **The tabs** are Eyes, Coats, Patterns, Markings and Coat presets.
- **Each colour card** has the before/after swatch pair, the picker, and a text box with the colour's code. You can paste a code someone shared, or type a name like "orange". Clicking the box selects it, ready to copy.
- **Patterns and Markings end with "New colours".** Each new colour keeps its number for good. The note says to pick it for your cat on the Your cat page, or in the cat maker with Creator palettes.
- **The Coat presets tab** lists the file's presets as cards: a name, the coat colour, optional nose, paws, whiskers and ears, and "Saved as" one of the game's first 20 coats. "Add a preset" makes a new one.
- **Words:** "colour 3", "the game's 25 colours", "eye white", "extra eyes (from a game add-on)", "the script loader". Never slot, UE4SS, DLC, sclera or priority.

**The five-minute first try:**

1. Open Palettes on a fresh install and press Patterns.
2. Press "Add a new pattern colour" and pick pink.
3. Press Save to mod. My mods is made for you and turned on.
4. Go to Your cat. It has already picked up the new colour, because it re-reads after each Save. Press the dashed pink square under "Pattern colour", then Save to mod.
5. Press Apply to game, then Play.

The note told you beforehand whether the script loader is there. If it was not, Apply's summary says the pattern colour needs it (step 8 adds that warning), and the Mods page installs it.

**Your cat.**

- **A preview cat at the top**, drawn with:
  - the slots the cat wears in the save, or the ones chosen on the page;
  - its own colours over them;
  - the real eye rows from the game's atlas, with any enabled palette's eye colours;
  - its ear and eye scars.

  The caption says what the drawing can't show: the body shape, back and chest scars, and paws.
- **"Cat shows: as it is now / with my changes".** "As it is now" is what the save holds after the last Apply. It is refreshed after each Save and Apply, and shown with the time of that Apply and whether its colours went in. "Put my cat back" sits under it.
- **"Whose look":** your cat, then the clans with each cat's role, your clan first, with a filter box.
- **"Colours of its own":** tick a part and pick a colour. The card says "they show while you play; Insert opens the mod menu, whose Colours page changes them live and Save keeps them".
- **"Colours from the game's picker":** the slot swatches, with names for the eyes, and coloured from the first open.
- **"Shape":** the cat maker's options by number, with "Keep what my cat has now" showing the current one.
- **"Scars":** a line links the Save page's Injury system switch, because scars show only with it on.
- **The raw `cats.json` panel** is folded under "For people who edit the file by hand".
- **When the save can't be read**, the page still opens and says so in one sentence, and the colours card keeps working.

## The plan

The steps are ordered so that each one leaves both pages working. The first Palettes steps are bug fixes that need nothing new; the later ones build on the shared drawing. "Needs the game" says how a step is checked in game.

Tests, and running them:

- **Python:** `tests/unit`, on the harness's fixtures. `studio` is a Studio over temp folders. `fake_game` is a made-up game folder with no paks. `save`/`write_save` write a small `WrcGame.sav` through `selftest._small_save`. `make_mod` makes a mod. `sandbox.running` makes the game "run".
- **Node units:** `tests/studio/<module>.test.mjs`, for the pure modules this plan extracts. `wc.js` imports under the DOM shim (`tests/studio/wc.test.mjs` already does), so its tests extend that file.
- **Browser:** `tests/studio/e2e/<page>.test.mjs`, a real studio over a temp data folder and a made-up game folder, as `e2e/shell.test.mjs` does.
  - That folder has no eye atlas. So the Eyes tab's logic (eye rows, moods on eyes) is tested as node units on `studio/lib/palette.js`, and the browser tests see the Eyes tab's "can't read the game's eyes" state.
  - The coat, pattern and marking tables come from a `Wrc/Binaries/Win64/ue4ss/UE4SS.log` written into that folder with `[WCModsCore] TABLE` lines, which `ue4ss.read_reports` reads.
  - A test emits a bus event in the page by importing `/studio/lib/wc.js` through the driver's `evaluate`.
- **Game tests:**
  - **Installing the fixtures:** the game tests below use fixture mods under `tests/game/mods/`, installed before the run with `python wcmods.py agent install --with tests/game/mods/<name>`. Each test skips when its fixture isn't in `wcmods.json`'s `installed` record, as `test_cpp_sdk.py` does for its mod.
  - **The save:** the runner backs the save up first, and `wcmods restore <backup>` puts the test cat back afterwards.
  - **The shared game:** the game is shared between sessions. Run these tests only after checking that no other session is using it.

### 1. Keep what the creator typed (Palettes)

Files: `studio/sections/palettes.js`, `studio/lib/palette.js` (from step 2: `applyBlocked`), `wcmods/mods.py` (one message).

**The "installed" listener.** Split the `bus.on("installed", ...)` at `palettes.js:224` (bug 1) in two:

- The Quick palettes list (`quickPick = null; renderQuick()`) re-renders on every "installed".
- The file reloads through the shell's `wc.installedEvent(target, () => target.refresh())`, which skips while the page is dirty.

When an install happens while the page is dirty, the status beside Save reads "Not in the game yet: Save to mod, then Apply" until the next Save, so nobody thinks the game has the edits. The shell doesn't ask before the top bar's Apply or Play, so this line is what tells the creator. If the shell later asks first, the line stays as the fallback.

**The Quick palettes Apply.**

- When the page is dirty, it saves the page first (`if (!await target.save()) return;`), then posts `/palettes/apply`.
- It is greyed for the same reasons the shell greys Apply (bug 6). The page reads `/info` on mount, on "installed" and on "focus" (the shell emits no status event). A pure `applyBlocked(info)` in `studio/lib/palette.js` gives the shell's own words: "Close the game first", or "Find the game first: Get set up, on the Mods page". The page sets `disabled` and the button's `title` from it.
- `mods.choose_palettes`' refusal of a palette that only adds colours ends "turn them on or off on the Mods page", not "with `wcmods enable/disable`".

**The stray "null" in `drawQuick`.** `clear(quick)` returns the bare element, whose own `append` writes `null` as text. Build the card with `el("div", {}, ...)`, which skips nulls, or filter them out.

Tests:

- Browser (`tests/studio/e2e/palettes.test.mjs`):
  - "edits survive an install while dirty": change pattern 3, emit "installed" through the driver, and the card still shows the new colour while the status says Not in the game yet;
  - "quick apply saves first": on a dirty page with a palette-only mod present, press Apply. The mod's `palette.json` on disk then has the new colour, whatever the apply says on the made-up game;
  - "quick apply is greyed without a game folder": a studio whose `wcmods.json` names no game;
  - "no null text under the quick palettes note".
- Node (`tests/studio/palette.test.mjs`): `applyBlocked({game_running: true})` and `applyBlocked({game_dir: null})` give the shell's words.
- Python, because no test covers `mods.choose_palettes` today: `tests/unit/test_mods.py::test_quick_palettes_switch_only_palette_only_mods`.
  - The ticked mods go on, and the other palette-only mods go off.
  - A mod that only adds colours is refused, and the message points at the Mods page.
  - A mod that also holds a `cats.json` is left alone.

Docs: none.

### 2. Read every colour form the build accepts, and never drop an entry silently (both pages)

Files: `studio/lib/wc.js`, a new `studio/lib/palette.js` (the Palettes page's pure functions), `studio/sections/palettes.js`. The `studio/sections/cat.js` half lands with PR 3.

**`color.parse`.** Add `color.parse(value)` to `wc.js`, mirroring `wcmods/colors.py:parse`:

- the same `NAMED` table: black, white, red, green, blue, gold, silver, pink, purple, teal, orange, cyan, magenta, lime, navy;
- `[r, g, b]` lists, 0-255 and clamped, with a fourth value ignored;
- 3-, 6- and 8-digit hex, with or without "#", with the alpha dropped;
- the result is "#RRGGBB", or null.

`normHex` stays as the hex-only check the pickers use. `wc.js` imports under the harness's DOM shim, so the colour functions stay in it and are tested in `tests/studio/wc.test.mjs`.

**The page's pure functions.** Move `eyeRow`, `fromPalette`, `toPalette`, the next-slot choice, `eyeRamp`, `applyMood` and `applyBlocked` into `studio/lib/palette.js`. Each takes the eye labels and tables as arguments, so node can test them.

**`fromPalette`** (bug 2):

- It uses `parse`.
- An eye value is read the way `palettes.load` reads it:
  - a list whose first item is a number (`[255, 140, 0]`) is one colour;
  - a list of colours is a gradient.
- A one-colour gradient list (`["#ffb300"]`) loads as a two-stop gradient of that colour. The build paints such a list flat from pupil to rim, and a two-stop gradient of one colour draws and builds the same while staying editable. It does not become "One colour", which keeps the game's shading, a different look.
- What it still can't read goes into `state.unread`, a list of `{section, key, value}`:
  - an eye name the game hasn't got;
  - a gradient under fur;
  - a non-digit key;
  - a fur slot of 25 or more;
  - an unknown section;
  - a colour `parse` refuses.
- `toPalette` writes the unread entries back untouched. The page shows them as one line under the tabs, "3 entries this page can't show", each with its own Remove button.
- The file's other known sections stay in `kept`, as today: `iris_ui`, `coats` until step 7, `name`, `description`, and `_` notes.

**`cat.js:parseOne`** uses `parse` for colours too (bug 12). This lands with PR 3, beside step 12's extraction. "red" loads as its hex and is written back as hex on the next Save. The file's meaning doesn't change, so the page is not marked dirty.

Tests:

- Node:
  - `tests/studio/wc.test.mjs`, `parse` on:
    - "orange", "#11223344", "ABC" and `[255, 0, 0]`;
    - "#GGGGGG" and `[1, 2]`, which give null.
  - `tests/studio/palette.test.mjs`:
    - a `fromPalette` to `toPalette` round trip that keeps eye labels, sorts numeric keys, leaves `coats` and `iris_ui` unchanged, writes unread entries back as they were, and keeps a one-colour eye list a list;
    - `{"eyes": {"Amber": [255, 140, 0]}}` loads as one colour, not three stops;
    - `eyeRow` on "Amber", "amber ", "iris2", "row2", "2" and "iris03", and on "30" (null).
- Python (`tests/unit/test_palette_groups.py`). The messages are asserted as the shell branch words them, since it rewrites `palettes.load`'s messages.
  - `test_palette_colours_load_in_every_form_the_docs_allow`: names, lists and 8-digit hex, for fur and eyes;
  - `test_load_ignores_notes_and_refuses_the_rest`:
    - "_help", "name" and "description" are ignored;
    - " 3" is refused, and "03" is accepted as 3;
    - a fur gradient is refused with "gradients are eyes-only";
    - `{"eyes": {"Amber": []}}` is refused.

Docs: `docs/formats.md`, palette.json:

- the colour forms: `#RGB`, `#RRGGBB`, `#RRGGBBAA`, a name from the list, `[r, g, b]`;
- the eye key forms: "Amber", "iris3", "row3", "3";
- the labels "Dlc1" to "Dlc5" and "Sclera";
- that `_`-prefixed keys and `name`/`description` are ignored;
- that a one-colour list is painted flat, pupil to rim.

### 3. An eye key past the atlas fails one entry, and the later palette wins per eye row (backend)

Files: `wcmods/eyeatlas.py`, `wcmods/sections/palettes.py`, `wcmods/palettes.py` (docstring only).

**`eyeatlas.py`** (bug 3). Factor the key rules out of `EyeAtlas.slot` into a pure `resolve(labels, key, height)`:

1. a label in any case;
2. then "irisN", "rowN" or digits;
3. then a range check that raises `KeyError(f"'{name}' is past the game's eye colours (it has rows 0-{height - 1})")`. The message reaches creators, so it doesn't say "atlas".

`slot` calls it, and step 4's check calls it too. Make `row()` check the range the way `set_row` does.

**`PaletteSection.build`** (bug 4):

1. Resolve each mod's eye keys to rows before merging. Build `{atlas.labels[row]: spec}` per mod, warning and skipping on `KeyError` and naming the mod and the key, as today.
2. Let `palettes.merge` merge by label. The later palette then wins whatever spelling each used, and `apply_eyes` runs once per row.

Tests:

- `tests/unit/test_palettes_eyes.py` (new). It uses a synthetic atlas made through `EyeAtlas.__new__`, with `labels`, `width`, `height`, `pixel_offset` and `data` set by hand, 64 by 26 half-floats.
  - `test_one_colour_keeps_the_rows_black_to_rim_ramp`: pixel 0 stays black, pixel 63 is the target in linear light, the values are monotone, and alpha is unchanged.
  - `test_one_colour_on_a_flat_sclera_row_is_flat`.
  - `test_a_gradient_puts_its_stops_at_the_ends_and_thirds`: 2 and 3 stops, and a 1-element list is flat.
  - `test_a_row_past_the_atlas_is_a_key_error_naming_the_row`: "row26", "iris99", "30".
  - `test_resolve_takes_labels_in_any_case_and_numbers_in_range`.
  - `test_changes_report_row_label_and_old_and_new_rims`.
  - `test_a_row_that_peaks_mid_ramp_keeps_its_shape`. It uses a synthetic row brightest at x=40. The rim gets that pixel's share of the peak times the target, written as the expected value so a change is noticed (RE gap: whether every game row peaks at the rim).
- `tests/unit/test_palette_groups.py`. It uses a stub ctx (the file already has a `Ctx`) that records `patch_package`, `add_ue4ss_mod`, `add_ue4ss_shared`, `note`, `warn` and `log`, and a monkeypatched `eyeatlas.EyeAtlas` that returns the synthetic atlas.
  - `test_the_highest_palette_wins_an_eye_named_two_ways`: iris2 low, Amber mid, iris2 high; the rim is the high colour.
  - `test_a_misspelt_eye_in_one_mod_skips_only_that_entry`.
  - `test_a_row_past_the_atlas_in_one_mod_skips_only_that_entry`, which fails today.
  - `test_iris_ui_is_derived_from_the_new_rims_unless_the_file_sets_it`.
  - `test_no_eyes_in_any_mod_patches_nothing`.
- `tests/unit/test_lua.py::test_palette_script_lists_its_slots`, the audit's missing test of `palettes.ue4ss_script`:
  - `{"fur": {"3": ...}}` gives the `FurColors = { [3] = {...} }` line;
  - keys "9" and "10" sort numerically;
  - `GAME_SLOTS` is substituted;
  - the script passes luacheck with entries.

Docs: `docs/formats.md`, the "which palette wins" paragraph. The later mod in the Mods list wins per colour, eyes included, whatever they are called; the order is set on the Mods page.

### 4. Checks at Save, through the shell's `Studio.check_file`

Files: `wcmods/studio.py` (beside `check_file`), `studio/sections/palettes.js`, `studio/sections/cat.js`. The palettes half lands with PR 1, the cats half with PR 3.

**How it works.** The shell's `check_file` runs the owning section's `collect()` and answers what it raises as `problems`, shown under the Editing-mod bar (bugs 5 and 11).

- The notes this step adds are things the build warns about but still installs. They use data-save step 3's channel: `check_file` passes warnings on, and the shell's box shows them under their own heading. If this lands first, it adds that channel as data-save step 3 describes.
- The extra checks are a small table in `studio.py`, keyed by file name, that `check_file` runs after `collect()`. They are not a second `collect()`.

**The palettes check.** For `palette.json`, `collect()` is `palettes.load`. It already reports fur slots past 24, non-digit keys, gradients outside eyes, unknown sections and bad coat presets, with messages a creator can read. The check adds two notes that `load` can't know. They are notes because the build skips just that entry:

- **Eye keys the game hasn't got.** That is a name that isn't one of the labels, or a number past the rows. When the game's files can be read, `eyeatlas.resolve` runs over the labels cached in `self.eyes()`, without reading the asset again. The note reads "'Ambre' isn't one of the game's eye colours, so it's left out (Amber, Olive, ...)". Without a game folder, or while its files can't be read, this check is skipped.
- **A new slot another enabled palette also adds:** "pattern colour 25 is also added by Dark Forest; the one later in the Mods list shows".

**The cats check.** For `cats.json`, `collect()` is `CatsSection.collect`, which is `catcolours.validate`. Its messages already name the key and what it takes. The check adds notes for things the build would warn about:

- a key naming no cat in the save. This uses step 11's matcher, the build's own `names.Plan.cats_called` over the save's current-slot cats, exactly as `CatsSection._others` uses it;
- a key that names two or more cats ("changes 2 cats called Hawkleaf");
- a pattern or marking slot no enabled palette adds;
- a Feral coat slot.

Without a save, or without the game's name tables, the notes that need them are skipped.

**Where the results show.** On both pages, the entries a check names can be removed where they appear: in the Palettes page's unread list (step 2) and the Your cat page's "Things this page can't change" list (step 12).

Tests (`tests/unit/test_studio_palettes.py` and `test_studio_cat.py`, new, on the `studio`, `fake_game`, `save` and `make_mod` fixtures):

- a PUT of `palette.json`:
  - with `{"fur": {"30": "#fff"}}` answers the problem;
  - with `{"eyes": {"Ambre": "#fff"}}` answers the eye-name note, with a stubbed `eyes()`;
  - with two palettes adding pattern 25 answers the note;
- a PUT of `cats.json`:
  - with `{"player": {"slots": {"coat": 3}}}` answers "cats.json: player.slots.coat should be one of fur, pattern, marking, eye_left, eye_right, eyes";
  - with a key naming no cat answers the note.

Docs: the README's Clan Mod Studio section gets one sentence: Save says what would keep a file out of the game.

### 5. Reset, Game colours, one Undo, and the small page faults (Palettes)

Files: `studio/sections/palettes.js`, `studio/lib/palette.js`.

**What the whole-tab buttons change** (bug 7):

- **Reset tab** clears only the game's slots (`i < TABLE(sec).length`) and the eye rows. The new colours keep their cards and their own Remove buttons.
- **Game colours** keeps the new slots and the coat presets.

Neither button needs a confirmation. The moods, Start from, Game colours and Reset tab each push a snapshot of `state` first. An "Undo <what was pressed>" button beside the Restyle row puts the last one back, and it goes away on Save or on a mod switch. One button replaces the confirmations and covers the moods too, the page's biggest single change.

**The row and the moods.**

- "Start from" and "Restyle this tab" are two rows, not one row of a dozen chips.
- The moods apply to every iris row from 1 to 25, and the eye white stays. The chip's title says so.

**The small faults:**

- **The preview's dropdowns** list the page's new slots and the other palettes' new slots, with their colours.
- **The eye groups** come from the labels: row 0 is the eye white, "Dlc" labels are the extra eyes, and the rest are standard.
- **The Add button** waits for `loadOtherSlots()`. It is disabled with "checking the other palettes..." until that resolves. `nextSlot` is checked again at Save time.
- **Focus after a redraw:** the cards, the stop buttons and the mode chips get `data-focus` keys (e.g. "pal:pattern:25"), so the shell's `keepFocus` puts focus back on the redrawn element. After Add, focus moves to the new colour's picker; after Remove, to the Add button.

Tests:

- Node (`tests/studio/palette.test.mjs`):
  - `nextSlot` is the max of the game's size, own slots plus one, and other mods' slots plus one;
  - removing the slot on show resets the view;
  - `applyMood("vivid")` on the eyes changes Dlc1 and leaves the eye white;
  - the undo stack puts back the state from before.
- Browser (`tests/studio/e2e/palettes.test.mjs`, tables from the log fixture):
  - Reset tab keeps pattern 25 and its card;
  - Undo after Vivid puts the Patterns tab back;
  - Game colours keeps the new colours and presets;
  - the dropdown shows "25 (new)";
  - focus lands on the new picker after Add.

Docs: `docs/formats.md`, and the Palettes guide page: what Start from copies, what Reset tab and Game colours change, what Undo undoes, and that new colours keep their numbers.

### 6. The game's colours from the first open

Files:

- `studio/sections/palettes.js`, `studio/sections/cat.js`, and `studio/sections/npcs.js` (it reads the same route);
- `wcmods/studio.py` (`/game/tables`), `wcmods/cli.py` (`cmd_tables`), `tools/make_palettes.py` (`game_colours`);
- for route 1 below: an `accessories.py`-style reader of the GuiManager asset;
- for route 2: a shipped `wcmods/data/colour_tables.json`, `.gitignore`, and `wcmods/selftest.py`.

**The page must not need the tables to work.**

- When `/game/tables` has none, the Coat, Pattern and Markings tabs still show the game's 25 colours as numbered cards ("colour 3", with the before half striped and "shows after one Play"). They take a new colour.
- The New colours block works without the tables too. New colours start at 25, which `palettes.GAME_SLOTS` already says and `/cat` serves as `game_slots`.
- Without a game folder, `/game/eyes` fails today and takes the whole page with it (`palettes.js:60`). Catch it and show the Eyes tab as "Find the game first: Get set up, on the Mods page", while the rest works. A game folder whose files can't be read shows "The game's eye colours can't be read right now".
- The banner becomes one line under the tabs, shown only while the tables are missing: "Press Play once, then come back: the game's colours appear here". The docs-guide plan rewords the same banner at `palettes.js:160`. Whichever lands second keeps this version.

**Where `python wcmods.py tables` writes.** `cmd_tables` writes `colour_tables.json` into the data folder beside `wcmods.json`, where player files live since the move out of the repository. `/game/tables` and `make_palettes` still read a copy in the repository folder, so a file made before keeps working.

**Where the real colours come from before the first play**, in order of preference:

1. **The player's own game files.** `wcmods/accessories.py:read_variations` already parses `BP_WrcGuiManager.uasset`'s package.
   - The tables are only there if the blueprint overrides the native defaults. The audit's RE gap places their initialiser in the exe, so expect this to come back empty. An afternoon's scan of the class defaults export for the table the log gives settles it.
   - If they are there, `/game/tables` reads them after the log and before anything else, cached like `self.eyes()`, with `"source": "game files"`. Nothing is redistributed, and `make_palettes.game_colours` can use the same reader.
2. **A shipped file.** The colours may be only in the native constructor. reverse-engineering.md gives the offsets 0x288-0x2B8 but not the initialiser, an RE gap that stays out of this plan. Then shipping `wcmods/data/colour_tables.json` needs the owner's yes, because the .gitignore keeps the generated copy out as game data that is "not ours to redistribute". If the owner says yes:
   - **The file:** `{"build": 26184573, "tables": {"FurColors": [25 hex], "PatternMaskColors": [...], "MarkingMaskColors": [...], "IrisColors": [...]}}`, taken from `python wcmods.py tables` on the current build.
   - **The .gitignore:** its `colour_tables.json` line matches at any depth, so it becomes `/colour_tables.json`, or the shipped file would be ignored.
   - **The generated file** that `cmd_tables` writes keeps its plain `{table: [hex]}` shape.
   - **`/game/tables`** answers, in order: the log, the generated file, the shipped file (`"source": "built in"`, with its build), else none.
   - **A one-line note** shows when the colours are the built-in ones and `/info`'s `game_build` is newer: "the game's colours from build N; Play once with the script loader to refresh them".
   - **`make_palettes.game_colours`** falls back to the shipped file, and drops its unused `EYES` list (`make_palettes.py:26-27`).
   - **A selftest step, `_tables_match_log`,** compares the log's TABLE lines with the shipped file.
3. **Neither.** The numbered cards above are the answer until the first play.

The Your cat and Characters pages get coloured swatches from the same route, with the same one-line note (bug 14).

Tests:

- `tests/unit/test_studio_palettes.py`:
  - the route's order with a fake log (a `UE4SS.log` in `fake_game`), a generated file in the data folder, one in the studio's root folder, and none;
  - the game-files or shipped source, when that route is taken.
- `tests/unit/test_ue4ss.py` (new), for `ue4ss.read_reports`, which no test reads today:
  - a `[WCModsCore] TABLE FurColors 25 ...` line gives 25 colours, and the last TABLE line per table wins;
  - the old `[WCModsPalettes]` tag still counts;
  - no log gives None.
- Browser (`tests/studio/e2e/palettes.test.mjs`):
  - with no log, the Pattern tab shows 25 numbered cards, and "Add a new pattern colour" makes 25;
  - with no eye atlas (the made-up game), the page opens with the Eyes tab's message.
- With the shipped file: `tests/unit/test_formats.py` checks that it has four tables of 25 six-digit hex colours.

Needs the game: `python wcmods.py selftest` with the game installed runs `_tables_match_log` (shipped file only). A manual check confirms that the three tabs show colours on a fresh data folder.

Docs: the README's Palettes row and `docs/formats.md:23-24` (where the colours come from, and that the page works before the first play), and the Palettes guide page.

### 7. The Coat presets tab (Palettes)

Files: `studio/sections/palettes.js`, `studio/lib/palette.js`, `wcmods/studio.py` (the PUT route), `wcmods/templates/palette/palette.json` (an example preset), `docs/formats.md`.

**The tab.** A fifth tab, "Coat presets". `state.coats` replaces `kept.coats`, so `EDITED` grows by "coats". Each preset is `{name, like, fur, nose?, paws?, whiskers?, ears?}`, as hex.

**A card per preset:**

- the name box: up to 40 characters, no "/", trimmed (the page refuses a duplicate);
- the coat colour picker (required);
- four tick-and-pick rows for nose, paws, whiskers and ears;
- "Saved as": a row of the game's coat swatches 0 to 19 with the chosen one ringed. Coats 20 to 24 show greyed with "Feral Edition: a game without it swaps this coat"; `load` accepts them.

**Using it:**

- Clicking a card's swatch shows the preset on the preview cat: coat, nose, ears and whiskers. The caption says paws aren't in the drawing.
- "Add a preset" makes "New preset" with the current coat pick's colour, and `like` set to that coat.
- Remove is a `confirmButton`.

**The format.** It is already in `docs/formats.md`:

```json
"coats": {"Ash": {"fur": "#9a9590", "nose": "#3a3330", "paws": "#4a4442", "ears": "#b8a0a0", "like": 12}}
```

The page writes exactly that. "Start from" another palette copies its presets too: today `fromPalette(..., state.kept)` skips every kept section. "Game colours" keeps them.

**Compatibility.**

- The page writes `coats` only when the file has presets, so palettes made before don't change.
- The released wcmods 0.3.0 refuses a palette with `coats` and stops the whole install. So:
  - The PUT route marks the mod when its saved `palette.json` has presets, as it already adds Sandbox mode to `requires` for story files. It sets mods-setup step 1's `"wcmods": "0.4.0"` in its `mod.json` through `Mod.update`, and never lowers a higher one. A newer Clan Mod Studio then says plainly what's needed.
  - 0.3.0 ignores the key and still refuses. So when the file has presets, the Share card says "needs Clan Mod Studio 0.4 or newer to install".

**The tab's note:** "They show in the cat maker's Fur picker with the Creator palettes mod, which needs the script loader and mods that run code allowed; the cat is saved with the game's coat it's saved as, so turning the mod off leaves it on that coat." When Creator palettes is missing, the note carries step 8's Add button.

Tests:

- Node (`tests/studio/palette.test.mjs`): coats round trip through `fromPalette`/`toPalette`, and a duplicate or slashed name is refused on the page.
- Python:
  - `test_the_pages_coat_preset_shape_passes_load`, which runs the literal the page writes through `palettes.load`;
  - `test_saving_a_palette_with_presets_marks_the_mod_for_0_4`, which also checks that a higher `"wcmods"` is kept.

Needs the game: a manual check with Creator palettes 1.2 on a wcmods newer than 0.3.0 (its `mod.json` description says so). The preset shows in the Fur picker and paints the cat. The agent controller doesn't drive the cat maker's picker, so this needs a person at the keyboard on the game's own screens.

Docs:

- `docs/formats.md`, the coat presets paragraph: the page makes them now, `like` 0-19, what a Feral `like` does without the edition, and the `"wcmods"` key the page sets.
- The Creator palettes README's limits line should say that an install with a coats palette on wcmods 0.3.0 is refused until the mod is turned off, not skipped. That repo is a sibling, so this is noted for the owner (mods-setup step 8 releases it).

### 8. "What reaches the game" and plainer words (Palettes)

Files:

- `studio/sections/palettes.js`;
- `studio/sections/palettes.css` (PR 74's per-page file), and `studio/app.js` to add "palettes" to `PAGE_STYLES`;
- `wcmods/sections/palettes.py` (one warning);
- the Palettes guide page (`docs/guide/palettes.md`, from the docs-guide plan);
- the README.

**The page head.** `wc.pageHead({eyebrow: "Appearance only", title: "Palettes", lede, help: "help:palettes"})`, so the shell's help panel opens the guide page.

**The note.** It sits under the page head and reads `/info` (`ue4ss`, `installed`, `game_build`, `allow_code_mods`). For Creator palettes it reads mods-setup's `GET /addons` (`installed`, `enabled`, `code`, `needs_newer_wcmods`), or `/mods` and a link to the mod's page until that lands. It shows only what needs something, each with one action:

- **Coats, patterns and markings:** "need the script loader: Get set up, on the Mods page, installs it".
- **New colours and coat presets in the cat maker**, one of:
  - "need the Creator palettes mod", with the Add-ons card's Add button;
  - "Creator palettes is in your mods but off";
  - "Creator palettes needs mods that run code allowed (Settings and repair)".

With nothing missing it is one quiet line, "Everything here reaches the game. Last applied <time>." It refreshes on "installed", "mods-changed" and "focus". This is the Creator palettes note mods-setup step 3 adds to `palettes.js`. Whichever lands second merges the two into this one.

**The build says it too.** `PaletteSection.build` warns, as the items and animations sections do, when the merged palette has coat, pattern or marking entries and the script loader isn't installed: "coat, pattern and marking colours go in through the script loader (UE4SS), which isn't installed: Get set up on the Mods page adds it". Today only a log NOTE says so, which the drawer's summary doesn't count. The five-minute try relies on this warning.

**The Quick palettes card** becomes the folded "Switch between ready-made palettes":

- a sentence on what Apply changes;
- the example mods named only when they are present;
- captions "coats" and "eyes" on the swatch rows;
- a warning when two ticked tiles both have coats or eyes: "Two full themes are ticked: the one later in the Mods list shows; untick one".

**Words.** A pass over every string on the page:

- "colour 3" for slot, and "the game's 25 colours";
- "eye white";
- "extra eyes (from a game add-on)" for the DLC rows. Which edition shows them isn't confirmed, so the page doesn't name one.
- "the script loader" for UE4SS;
- "the one later in the Mods list wins" for priority.

The modTarget toasts ("palette.json in my-mods isn't valid JSON") are shared, and the shell's error rewording covers them, so they aren't reworded here.

**Eye card titles.** Cards keep the game's name as the title, and add "(the game calls it Yellow)" where the hue and the name disagree, decided from the rim's hue.

**CSS.** Rules only this page uses go in `palettes.css`. The shared cat drawing's rules (step 9) go in `styles.css`, which PR 74 keeps for rules used by two or more pages.

Tests:

- Browser: the note's states. The data folder holds no Creator palettes mod, and then one that is turned off; the made-up game has and lacks `ue4ss/Mods`. Also the two-themes warning.
- Python (`tests/unit/test_palette_groups.py`): `test_runtime_colours_without_the_script_loader_warn`.

Docs:

- Add to the Palettes guide page: what needs the script loader and Creator palettes, and that coat colours on screen and a cat wearing a new colour haven't been watched in game yet. Step 16 removes that last sentence.
- README rows 106 and 383.

### 9. A colour code box, and an honest preview, with the cat drawing shared

Files: a new `studio/lib/cat.js`, `studio/sections/palettes.js`, `studio/styles.css` (the drawing's stage rules, shared), `docs/ARCHITECTURE.md`. `studio/lib/story.js` is unchanged; it is only noted.

**Which file draws which cat.** The task brief says `studio/lib/shape.js` draws the Palettes cat. It doesn't:

- `shape.js` draws accessory models for the Items page;
- the Palettes cat is the inline `CAT_SVG` in `palettes.js`;
- the Characters page has a smaller face in `story.js:catFace`.

**The shared drawing.** Move `CAT_SVG`, `drawCat` and `setIris` into `studio/lib/cat.js` as `catSvg()` and `paintCat(svg, {coat, pattern, marking, eyeWhite, irisL, irisR, nose, ears, whiskers, scars})`:

- `irisL`/`irisR` are ramps: the Palettes page passes `eyeRamp` output, the Your cat page the atlas rows;
- `scars` is optional (step 13);
- whiskers take a neutral tone from the coat's outline, not the marking colour;
- nose and ears take the preset's colours when given, else the CSS defaults.

The caption under the stage says "In the game, paws, ears, nose and whiskers follow the coat; this drawing can't show them." The "Show the game's original colours" box becomes the two-option "Cat shows: my colours / the game's".

**The colour code box.** On each colour card, the existing hex text becomes a text box that shows the code. It accepts anything `color.parse` reads (on Enter or blur), and it selects its whole text on focus, so Ctrl+C copies it. That replaces the hex text rather than adding a separate Copy button, so each card has no more controls than before. Gradients show one box per stop.

Tests (browser, since the DOM shim doesn't parse SVG; tables from the log fixture):

- `paintCat` sets the expected `fill`/`stroke` attributes;
- typing "orange" in coat 3's box sets the card to #FF8C00;
- focusing the box selects its text.

Docs: `docs/ARCHITECTURE.md:17`. `lib/cat.js` is the cat drawing both pages use, and `shape.js` is the Items page's model view.

### 10. Your cat opens whatever the save is in

Files: `wcmods/studio.py` (`cat_info`), `studio/sections/cat.js`.

**The backend** (bug 8). `cat_info` catches `(LookupError, ValueError, OSError)`. `OSError` covers a save the game holds open while it writes. It returns `"save_problem"`:

- `None`, when the save reads;
- "no save yet", for the `LookupError` case;
- for the rest, one sentence: "Your save couldn't be read (it may be half written; try again in a moment), so the page can't show what your cat wears now".

**The page:**

- renders a banner with that sentence;
- greys the Shape, slots and Scars cards, whose "now" labels read "unknown";
- keeps the colours card working;
- with no save at all, says "Start the game once, so there's a save, then come back" instead of showing question marks.

Tests:

- `tests/unit/test_studio_cat.py`, with saves from the harness's `write_save`:
  - no `WrcGame.sav` gives empty `current`, empty `cats`, `save_problem` "no save yet", and no exception;
  - a zero-byte file and a file cut short give a `save_problem` and no exception (today, a `ValueError`);
  - a save with `CurrentCatSlot` 5 and a player cat with `FurColorIdx=11`, `ScarEarId=4`, `BodyValue=6` and `CatSize=0.45` gives `current.fur` 11, `scars.current.ear` 4, `look.current.body` 6 and `size` 0.45;
  - a cat without `CatSize` gives `size` `None`;
  - a cat in slot 2, while 5 is current, is left out.
- Browser (`tests/studio/e2e/cat.test.mjs`): the page opens with no save and with a zero-byte save.

Docs: none.

### 11. Whose look: keys matched by the build's own matcher

Files: `wcmods/studio.py` (`cat_info` and a new route), `wcmods/names.py` (the place part of `_targets` as a function), `studio/sections/cat.js`.

**Matching on the server** (bug 10). The page doesn't get a second matcher. `POST /cat/match {"keys": [...]}` answers, per key, `{"cats": [<target>, ...], "why": null | "not in your save" | "in game 2: put its slot first" | "the game's names can't be read, so only places match"}`.

- It uses `names.Plan.cats_called` over the save's current-slot cats without player cats, exactly as `CatsSection._others` finds them.
- Places therefore match as the build matches them, case kept: "Clans/WindClan/Warrior/1", "WindClan/Warrior/1" and "Warrior/1".
- Names match ignoring case, including a name from before a Names-page rename.
- Without the game's name tables, places still match through the place part of `_targets`, factored into a function both use.
- The page calls it after loading the file, after an Import, and on step 13's refresh events. Step 4's cats check calls the same function.

**On the page:**

- A file key goes onto every cat it matches, labelled "changed, as "WindClan/Warrior/1"", with its "now" values shown.
- A name that matches two or more cats says "changes 2 cats called Hawkleaf", as the build's warning does.
- A key matching no cat stays listed, with the route's `why`.

**The dropdown:**

- It groups the cats by clan (`optgroup`), with the role in the label ("Hawkleaf, warrior").
- Your cat's clan comes first; it is read from the player cat's `ClanType`.
- A filter box sits above it.
- The raw place sits in the option's `title`.

Cats in other save slots stay out of the list. The docs say the `"2/Duskfang"` form is for files written by hand.

Tests:

- `test_studio_cat.py`, with a `FakePlan` as `test_cats.py` has:
  - "WindClan/Warrior/1", "Warrior/1" and "Clans/WindClan/Warrior/1" find the warrior, and "windclan/warrior/1" finds nothing, as in the build;
  - "hawkleaf" finds Hawkleaf;
  - a names mod renaming Duskfang to Mothfang: both names find the cat;
  - two NPCs with one display name: the name finds both, and `cat_info` gives each its place as `target`;
  - a key for a cat only in slot 2 answers the slot-2 `why`;
  - without the game's names, a place still matches.
- Node (`tests/studio/catlook.test.mjs`, after step 12's extraction): `placeKeys(looks, matches)` puts "WindClan/Warrior/1" on Hawkleaf, and a doubled name on both cats.

Docs: `docs/formats.md`, cats.json. Both place forms work: "Clans/WindClan/Warrior/1" as the page writes it, and "WindClan/Warrior/1" as the Names page shows it. Places match exactly, and names ignore case.

### 12. Keep what the page can't show (Your cat)

Files: a new `studio/lib/catlook.js` (`parseOne`, `oneJson`, `toJson`, `placeKeys`), `studio/sections/cat.js`, `wcmods/studio.py` (step 4's cats check).

**The extraction.** Extract the file functions into `studio/lib/catlook.js` for node tests. Step 2's `parse` goes in here (bug 12).

**"Things this page can't change"** (bug 11). Keys the page can't edit are listed under this line on the card they belong to, each with its value and a Remove button:

- `extra` per cat;
- `fileExtra`;
- `scarsRaw`;
- an unknown slot or look part, which `parseOne` keeps today and `validate` would refuse;
- a colour part the build doesn't know, or a colour `parse` refuses.

They are written back as they were until removed. The Save-time check (step 4) names the same keys. `parseOne` stops putting a slot, look or colour key that `catcolours.SLOTS`/`LOOK`/`PARTS` doesn't know into `slots`/`look`/`colours`. It goes to the list instead, and the rest is kept as before. `_`-prefixed notes are kept and not listed, since the build ignores them.

Tests (node, `tests/studio/catlook.test.mjs`):

- `parseOne({scars: "none"})` to `oneJson` gives "none";
- one part "none" and the rest absent gives `{back: "none"}`;
- `{eyes: 3}` becomes `eye_left`/`eye_right` 3 and is written back as `{eyes: 3}`, while 3 and 5 stay separate;
- `{ear: "notch-left"}` is ear 5, and is written back by name;
- `{ear: 9}` goes to the raw list and is written back unchanged;
- `_note` on a cat survives a round trip unlisted, and `notes` (no underscore) survives and is listed;
- a cat with every part cleared is dropped from the file;
- `{slots: {coat: 3}}` lands in the can't-change list (not in slots), is written back, and goes after Remove;
- `{colours: {fur: "red"}}` loads as #FF0000, and `{colours: {tail: "#fff"}}` is listed;
- a size of 3 clamps to 1.5, and unticking removes it.

Docs: none beyond step 4.

### 13. "Now" after Save and Apply, the drawn cat and plainer words (Your cat)

Files:

- `studio/sections/cat.js`;
- `studio/sections/cat.css` (PR 74's per-page file), and `studio/app.js` to add "cat" to `PAGE_STYLES`;
- `studio/lib/cat.js` (step 9);
- `wcmods/studio.py` (`look_options` gains eye colours);
- the Your cat guide page (`docs/guide/cat.md`, from the docs-guide plan).

**Keeping "now" fresh** (bug 13). Re-fetch `/cat` (and `/cat/match` for the file's keys) and `render()` on "installed", "mods-changed" and "focus", with a plain `bus.on`.

- The page's own choices stay.
- This is not `installedEvent`: `/cat` doesn't touch the file, so it must refresh even while the page is dirty.
- "mods-changed" brings in a new colour a palette has just saved, which the five-minute try needs.
- Return the unsubscribes from `mount` for `unmount`.

**The preview.**

- `catSvg()` sits at the top of the page, painted with `slotHex` for the chosen or current slots. Step 6 makes the colours real before the first play.
- The cat's own colours go over them.
- The eye rows come from `/game/eyes` for `eye_left` and `eye_right`. The row is the slot + 1, as `tests/game/test_npcs.py` and reverse-engineering.md confirm.
  - Any enabled palette's eye colour comes from `look_options`, which now returns `eyes` resolved to rows with step 3's `resolve`.
  - The eye swatches therefore get the game's names and the atlas rims, and the `IrisColors` row goes (bug 14).
  - When the game's files can't be read, `look_options` returns `eyes: {}` and the swatches fall back to `IrisColors`. The Characters page reads the same route and only gains a key.
- An ear scar is drawn as a notch or a torn edge on the matching ear, and an eye scar as a shut eye.
- The caption reads "The drawing shows colours and head scars; the body shape, the back and chest scars and the paws aren't in it."
- **"Cat shows: as it is now / with my changes"**, the same two-option switch as the Palettes page. It replaces a separate "In your save now" card.
  - "As it is now" draws what the save holds for the chosen cat, the same values as the per-card "now" labels.
  - Under it go the time of the last Apply (`/info`'s `installed.built`) and whether its colours went in. They did if `installed.ue4ss` was true and the mod is in `installed.mods`; otherwise "your colours aren't in the game yet: Apply with the script loader".
  - Step 15's "Put my cat back" sits under it too.

**Words and small changes:**

- `wc.pageHead({eyebrow: "Your cat", title: "Your cat", lede, help: "help:cat"})`;
- "Colours of its own", "Colours from the game's picker", "Fur shape" for the look row, and "Keep what my cat has now (6)";
- a sentence under each card on when to use it;
- "the script loader", with a yellow line on the colours card when `/info` says it's missing;
- the Insert-key sentence on the colours card;
- the Feral note only on coats 20 to 24;
- the raw panel folded;
- on the Scars card, a line "Scars show only with the game's Injury system on" linking the Save page's switch, and `data-focus` keys on its two buttons;
- the size box becomes a slider from 0.05 to 1.5, with kit, apprentice, warrior and leader marks and the rank-up note.

Tests (browser, `tests/studio/e2e/cat.test.mjs`):

- after "installed" is emitted, the "now" label follows a save rewritten in the temp folder, while the page is dirty too;
- after a palette adding pattern 25 is saved on the Palettes page, the dashed swatch appears;
- the preview's coat fill follows the chosen slot, and "as it is now" follows the save's;
- an ear scar adds the notch;
- the script-loader line shows when the made-up game has no `ue4ss/Mods`.

Docs:

- Add to the Your cat guide page: the preview and its switch, and the Injury system link.
- README row 107: shape and other cats are missing from it.
- `docs/formats.md`:
  - slots, scars and shape stay in the save when the mod is turned off, and are written again at every Apply;
  - colours go on the cat you play, in any save slot (bug 16);
  - how to tell it worked: the HUD picture, and the "[WCModsCatLook] cats' own colours are on" log line.

### 14. The in-game Colours Save and the studio stop overwriting each other

Files:

- `wcmods/lua/catcolours.lua`, `wcmods/sections/cats.py`, `wcmods/catcolours.py` (`script`);
- `wcmods/studio.py` (the file routes) and `studio/lib/wc.js` (`modTarget`);
- `tests/unit/test_cats.py`, `tests/unit/test_lua.py`, `tests/unit/test_studio_cat.py`, `tests/game/test_menu.py`;
- `tests/game/mods/cat-colours-save/` (`mod.json` and `cats.json`, a fixture), `docs/agent.md`.

**The rule** (bug 9), kept simple: the game's Save changes only `player.colours` in the file as it is now, and it goes to the mod whose player colours win.

**In the Lua:**

1. Save first re-reads the file with `io.open` and `Game.json.decode`. WCModsGame goes in with every install and ends with `return Game`, so `pcall(require, "WCModsGame")` gives it, as `bridge.lua` and the bootstrap already do.
2. It replaces `player.colours` in what it read and writes that back with `Menu.saveJson`.
   - Non-empty lists stay lists.
   - An empty list or a `null` comes back as `{}` from Menu's encoder, until console-lua's fix. In a `cats.json` those appear only under `_` notes, which the build ignores.
   - Floats keep six digits, enough for a size.
3. A file that is gone: Save writes a new one holding only `player.colours`, and says so.
4. A file that is there but can't be read (broken, or saved with a BOM before console-lua's fix): Save refuses with "cats.json couldn't be read; fix it in the studio, then Save here". It never writes the build's copy over it.
5. Without WCModsGame (an install from before this), Save refuses with "Apply again in the studio, then Save here".

**In `cats.py`** (bug 15): the save target is the highest-priority enabled mod that sets `player.colours`. Otherwise it is the last one with a `cats.json`, as now. The Lua page keeps saying which file. data-save step 6 also edits `cats.build` (its save decode); whichever lands second keeps both.

**On the studio side:**

- **The file routes.**
  - GET of a mod file returns its `mtime`, the file's `st_mtime_ns` as a string.
  - `modTarget` sends it back on PUT as `expect`.
  - When the file's mtime has moved, the route answers 409 with `{"error": "cats.json changed since you opened it (the game's Colours page saved, or another studio window); Reload to see it, or Save again to overwrite", "stale": true}`.
  - The PUT's answer carries the new `mtime`, which `modTarget` keeps, so the page's next Save isn't refused.
- **The answer on the page.** `modTarget` turns that answer into a two-button line under the bar, Reload and Overwrite. Overwrite sends the PUT without `expect`. A PUT without `expect` (mods' own pages, older callers) saves as today.
- **Mouse look.** The Controls page's Mouse look card writes `mouselook.json` with its own PUT, without `expect`, so this doesn't protect it. The controls page can send `expect` the same way. That is noted for the controls plan, not done here.
- **Re-reading.** `modTarget` also re-reads the file on bus "focus" when the page isn't dirty. The shell's `installedEvent` already covers "installed".

This is next to the shell's work (`modTarget` is shared), so it should land after the shell's dirty guard and reuse its Save/Discard/Stay pieces where they fit.

Tests:

- `test_cats.py::test_the_in_game_save_goes_to_the_mod_whose_player_colours_win`: two mods, the higher one setting only other cats; the lower one's path is in `SAVE`.
- `test_lua.py::test_your_cats_colours_script_with_its_menu_page`, extended to luacheck the new Save branch.
- `test_studio_cat.py`:
  - `test_a_put_with_a_stale_mtime_is_refused_with_409`;
  - `test_a_put_with_the_current_mtime_saves_and_answers_the_new_one`;
  - `test_a_put_without_expect_saves`.
- Browser: a file changed on disk reloads on focus when the page is clean, and shows the Reload/Overwrite line when it's dirty.

Needs the game: `tests/game/test_menu.py::test_colours_save_keeps_the_files_other_edits`.

1. Install the fixture `tests/game/mods/cat-colours-save`, whose `cats.json` holds `player.colours` and `look.tail`, with `agent install --with`. The test skips without it.
2. The test writes `look.body` into the fixture's `cats.json` by hand.
3. It opens the mod menu's Colours page (`agent.menu.open("Colours")`), switches on Coat (`agent.menu.set`), and presses Save (`agent.menu.press("Save")`).
4. It reads the file back: the colours, `look.tail` and `look.body` are all there.
5. Teardown writes the fixture's original text back, because the in-game Save writes into the `--with` folder.

That also closes verified.md's "Save on the Your cat page not yet checked".

Docs:

- `docs/formats.md`, cats.json: what the in-game Save writes, and where.
- README lines 157-159.
- `docs/agent.md`: the fixture, and the test count.
- `docs/verified.md`, once the game test passes.

### 15. "Put my cat back"

Files: `wcmods/pipeline.py` (`apply_save_ops`), `wcmods/saverecord.py` (data-save step 6's helper; whichever plan lands first creates it), `wcmods/studio.py` (`/cat/restore`), `studio/sections/cat.js`, `tests/unit/test_save_ops.py` (new). data-save step 6 reworks `apply_save_ops` too, so this lands on top of it, or it rebases.

**Recording the originals.** When `apply_save_ops` applies a `fields` op, it records the value the save had for each field it's about to change. It does this only the first time that field is recorded for that cat.

- The record goes in `<data folder>/cat-originals.json` through `saverecord.py`, beside `wcmods.json` and data-save's `save-changes.json`. Like that file, it is keyed first by the save's account (`SaveDoc.account`), then by the cat's save path: `{"<account>": {"5/Clans/.../Player": {"prefix": "STR_CAT_NAME53", "when": "2026-10-28T15:30:12", "backup": "20261028-153012-before-save-edits", "fields": {"FurColorIdx": 11, "BodyValue": 6}}}}`.
- The file lives outside the mods, because it is about this save, not a mod. data-save's own record leaves look ops out, so the two don't overlap.
- A cat is the same cat while its `PrefixNameId` is the same, since a rank-up changes only the suffix. When a path's cat has another prefix (a game started again in that slot), its old record is dropped and a new one starts.
- For a cat already changed by an Apply before this lands, the first record holds what the save had at the first Apply after it. The card says "what it had before <date of the first record>".
- Restoring a backup leaves the record alone. It holds what the cat had before any mod changed it, which a restore can only bring back.

**Restoring.**

- `GET /cat` returns, per cat, whether originals exist and their date.
- Under the preview's "as it is now" (step 13): `wc.confirmButton("Put my cat back", "Press again: <name> goes back to what it had before <date>, and this page's choices for it are cleared")`. The page saves first when it has unsaved changes, then posts `/cat/restore {who, mod}`.
- The route:
  1. refuses while the game runs;
  2. refuses when another enabled mod's `cats.json` still sets those fields for that cat, because the next Apply would put them on again: "Dark Forest Cats still sets its coat: turn it off on the Mods page first";
  3. clears this page's slots, scars and look for that cat from the edited mod's `cats.json`, keeping its colours;
  4. makes the usual backup;
  5. applies one `fields` op with the recorded originals through `apply_save_ops`, finding the cat by its path, or by its prefix when the path moved;
  6. drops the record;
  7. answers the log lines. The page then reloads the file and `/cat`.
- The card says plainly: "Turning the mod off doesn't undo these; Put my cat back does."

Tests (`tests/unit/test_save_ops.py`, with the harness's `write_save` holding a player cat's Customization text):

- `test_a_fields_op_writes_the_save_and_backs_it_up_first`;
- `test_originals_are_recorded_once_and_never_overwritten`: two installs, the second changing more fields, keep the first install's values for the fields it had;
- `test_put_my_cat_back_restores_the_recorded_fields_and_forgets_them`, which also checks that the page's choices for that cat are gone from the file;
- `test_put_my_cat_back_refuses_while_another_mod_sets_the_fields`;
- `test_a_cat_whose_path_moved_is_found_by_its_prefix`;
- `test_a_new_cat_in_the_same_slot_starts_a_new_record`;
- `test_records_are_kept_per_account`;
- `test_a_fields_op_equal_to_the_save_changes_nothing_and_records_nothing`;
- `test_a_rename_and_a_reshape_on_one_cat_both_land_and_both_are_logged`. It fixes the one-label-per-path log on the way: labels become a list joined with "; ". If data-save step 6 has already changed the labels, this test follows its form.
- `test_set_fields_handles_exponent_values_and_text_without_a_closing_bracket`: the regex takes `[eE][-+]?\d+`, the text is right-stripped, and a missing field is reported, not dropped.

Needs the game: no automated test. The route refuses while the game runs, and the restore is the same `fields` op Apply writes, which step 16's test sees in game. A manual check: press Put my cat back with the game closed, then Play, and the HUD picture shows the old coat.

Docs: `docs/formats.md` (cats.json, and a short paragraph on `cat-originals.json` beside data-save's `save-changes.json`), the README's Your cat row, the Your cat guide page.

### 16. Seen in game: a new colour on a cat, and coats on screen

Files: `tests/game/test_cat.py`; the fixture `tests/game/mods/looks/`, which has:

- a `mod.json`;
- a `palette.json` with `fur` "3" #00FF66 and `pattern` "25" #FF00CC;
- a `cats.json` with `player.slots` `fur` 3 and `pattern` 25.

Also `docs/verified.md`, `docs/agent.md`, and the guide pages' "not yet seen" sentence from step 8.

**The run.** The fixture is installed with `agent install --with tests/game/mods/looks`, which writes the test cat's slots into the save after a backup. The tests skip without it. Then the player enters the forest.

**The tests.**

- **`test_a_new_pattern_colour_shows_on_your_cat`:**
  - `Game.cat():customization()` reports `Pattern01ColorIdx` 25, which also confirms the `fields` op in game;
  - "Pattern Mask Color", read from the player cat's body material the way `tests/game/test_npcs.py`'s LOOK snippet reads its parameters (one object, no world scan), matches #FF00CC in linear light within 1/255.
- **`test_a_recoloured_coat_shows_on_your_cat`:** the same, with `FurColorIdx` 3 and "Fur Color" against #00FF66.

Both pass only with the script loader, which the agent's test install has. Afterwards, `wcmods restore <backup>` puts the test cat back.

**On a pass,** move "Coat colours on screen" and "New pattern and marking slots on a cat" from verified.md's "Not yet confirmed" to the dated list, and drop the guide pages' sentence.

**On a fail,** the RE gap "what makes an already set-up cat re-read its colour slots" is the next thing to look at, and the sentence stays. The script's `refreshCats` calls `RefreshShape`, which reverse-engineering.md says kept the colours.

Docs: `docs/verified.md`, `docs/agent.md` (the fixture, and the test count), the Palettes and Your cat guide pages.

## Not in this plan

**Impossible:**

- **New coat colours everyone can pick** (coat slots past 24). The game pairs each coat with paw, ear, nose and whisker colours from a native map, and crashes on a coat without them. Coat presets are the workaround.

**Needs reverse engineering first:**

- **New eye colours** (atlas rows past 26). This is likely impossible: the eye material indexes a fixed 64 by 26 atlas, and nobody has read how it turns the index into a row.
- **The game's colour tables from the exe** (the initialiser of the 25 entries per table). With it, the Palettes page would have the real colours on first open without shipping them. Step 6 works without it.
- **A preview with the game's real pattern and marking shapes.** The mask textures, and the table from a pattern index to its texture, are not traced.
- **Names or pictures for the shape options** (the cat maker's labels or thumbnails for each body, tail, ear and face). Until they are found, Shape stays numbers.
- **Paw, ear, nose and whisker colours shown per coat.** The map from coat to four colours at manager+0x800 hasn't been extracted. Until it is, the drawing says it can't show them.
- **Naming which add-on the extra eye rows belong to,** and what the cat maker shows for them without it. Until then, the page says "from a game add-on".
- **Season or night palettes, and glowing eyes.** Cats re-read the tables only when they are set up again, and the eye material's only known inputs are the atlas row scalars.
- **Colours that follow the save slot rather than the pawn (bug 16).** Comparing the pawn's name prefix with the save's is possible, but wrong when two slots' cats share a prefix. Doing it right needs to know which save slot a pawn or menu copy belongs to, which Lua can't read yet. The docs get the honest sentence in step 13.
- **Five Your cat ideas, each waiting on its own finding in game:**
  - a random look within the clan's cat-maker windows (the per-clan offsets);
  - keeping my size after rank-up (whether the size override persists);
  - live shape and scars from the mod menu (whether `RefreshShape` redraws changed CustomData);
  - accessories as part of a look (where equipped accessories live in the save);
  - changing a cat's clan or gender (what a changed ClanType does).

**Possible, left for later so they aren't lost:**

- a palette from a picture;
- a palette card picture in the shared .zip;
- "recolour my cat's own colours", opening the Palettes page on the slots the cat wears;
- "look like Hawkleaf", copying a save cat's look;
- a traits picker;
- turning the Injury system on when a scar is chosen (step 13 only links the switch);
- bulk looks by clan or role;
- coat presets offered on the Your cat page's coat row;
- a "Save and apply" button on these pages;
- a "Log every cat the colours script sees" switch on Settings and repair, for `debug_cat_look`;
- a "just switch, don't install" use of `/palettes/apply` with `install: false`, which has no caller;
- the Mouse look card sending `expect` (step 14's route takes it), for the controls plan.

**Left as is:**

- `Section.appearance_only` (`sdk.py:69`) is declared and never read. It is part of the SDK a mod's `section.py` can set, so it stays until the pipeline decides to use it in the build report.

**Owned by other plans and PRs:**

- the cat choice's picture bugs (the SkinnedAsset crash, your colours on other saves' thumbnails, hard-coded actor names) are PR 70's;
- `models.lua` is PR 72's;
- an unreadable save blocking every install (`cats.py:27`'s decode) is data-save step 6's;
- the `"wcmods"` minimum and the 0.4.0 version are mods-setup step 1's;
- the Creator palettes release and the examples' regenerated palettes are mods-setup step 8's;
- `menu.lua`'s encoder and the BOM are console-lua's.

## Open questions

1. **Can the game's colour tables be read from the player's own files** (`BP_WrcGuiManager.uasset`'s defaults), and if not, may `wcmods/data/colour_tables.json` be shipped? The .gitignore calls the generated copy game data that is "not ours to redistribute". If neither, step 6's numbered cards and the "Press Play once" line are the answer until the first play.
2. **When is wcmods 0.4 released?** Creator palettes 1.2 ships a coats palette that 0.3.0 refuses. mods-setup step 1 adds the `"wcmods"` key and the version, and step 7 sets it on a palette with presets. What's left is timing: should the Palettes page point creators at Creator palettes (step 8), and make coat presets (step 7), only once the release with `coats` support is out?
3. **The in-game Save target** (step 14): the mod whose player colours win, falling back to the last mod with a `cats.json`. Is that the rule the owner wants, or should it always be My mods (made if missing), which is what the page edits?
4. **Should turning the cats mod off, or uninstalling, put the cat back automatically** (step 15), or stay a button? Automatic is tidier, but surprises anyone who wanted to keep the look.
5. **`iris_ui`:** keep it in files as an advanced section (documented), or always derive it from the eye rims and ignore a file's own? Step 2's docs assume "documented, advanced".
6. **Shape numbers on the Your cat page:** the file counts from 0 (0-9). Show them as written, or as the cat maker counts? Step 13 keeps them as written, with a note.
7. **Back scars 5 and 6:** refuse them in `validate` (one rule for page and build), or offer them as "Spot 3 (shows nothing, as far as we know)"? The in-game pass over every scar number (an RE gap) would settle the labels too.
8. **Should a Vivid or Ember restyle touch the extra eye rows?** Step 5 says yes, with the eye white left alone.
9. **Eye card titles:** the game's names with "(the game calls it Yellow)" where they disagree, or the hue's own name first? Step 8 keeps the game's name as the title, so the cat maker and the page say the same word.

## Review corrections (2026-10-28)

Checked against the audit maps, the skeptic's verdicts and the code. All 16 listed bugs are confirmed (none refuted) at the file:line given; the lows stay "likely but unchecked".

**Counts:**

- test_cats.py collects 18 tests, not 7.
- test_palette_groups.py collects 15, not 16.

**Coordination with the work under way:**

- PR 74 links per-page CSS from a list in `app.js`, so PRs 2 and 3 touch `app.js`. The shared drawing's rules go in `styles.css`.
- The guide pages come from the docs-guide plan.
- The modTarget toast rewording is the shell's.

**Accuracy:**

- Step 11 lowercased places, but the build matches places with their case kept.
- Step 4's cats check now uses the build's own `cats_called` instead of a second matcher.
- Step 13 re-fetched `/cat` through `installedEvent`, which skips while the page is dirty, and missed "mods-changed", which the five-minute try depends on.
- The DLC eye rows were called the Feral Edition's, which nothing confirms.
- The shipped tables are explicitly "not ours to redistribute", so step 6 now prefers reading the player's game files and makes every tab work with no tables at all.
- The Palettes page failing without a game folder was missing; step 6 now covers it.

**Game tests:**

- Step 15's game test could not run: the restore route refuses while the game runs. It is now a manual check.
- The game tests use fixture mods installed with `agent install --with`, and skip without them, as test_cpp_sdk does.

**A simpler creator experience:**

- One Undo replaces the confirmations on Reset tab and Game colours.
- The "Remove every new colour" button is gone.
- The colour code box replaces the hex text instead of adding a Copy button.

**Formats stay compatible:**

- The page writes `coats` only when the file has presets, and the Share card warns that such a file needs wcmods 0.4 or newer.
- A one-colour eye list keeps its flat meaning.
- A PUT without `expect` saves as before.

## Second review (2026-10-28)

Checked again against the maps, the verdicts, the code, the branches now on disk (`claude/studio-shell`, PR 74, PR 75) and the other plans. The 16 bugs stand as listed.

**The work under way, as it now is:**

- Test paths follow PR 75:
  - node units are `tests/studio/<module>.test.mjs`, and `wc.js` imports under `lib/dom.mjs`, so `color.parse` stays in `wc.js` (no `colour.js` split);
  - browser tests are `tests/studio/e2e/<page>.test.mjs`;
  - `tests/studio/lib/` holds only the shim and the driver.
- The browser tests' made-up game has no eye atlas, so the eye-row tests moved to node units on `lib/palette.js`. The colour tables come from a `UE4SS.log` fixture.
- The shell doesn't ask before Apply or Play and emits no status event. Step 1 no longer says it does: it reads `/info` itself, through a pure `applyBlocked`.
- The shell's `check_file` is generic and answers only what `collect()` raises. Step 4's extra checks are a per-file table beside it, and its notes use data-save step 3's warnings channel.
- The page heads adopt `wc.pageHead` with `help: "help:palettes"` / `"help:cat"`.

**Other plans:**

- data-save: `saverecord.py` and the account key (step 15), `cats.py` and `apply_save_ops` edited by both, `cat_info` only gaining keys.
- mods-setup: the `"wcmods"` key (step 7 sets it), `/addons` and its Creator palettes note (step 8 is that note), the releases.
- console-lua: the encoder and the BOM (step 14).
- docs-guide: the glossary's "slot".

**Accuracy:**

- Step 2: an `[r, g, b]` eye value is one colour, and an eye name the game hasn't got joins the unread list.
- Step 3: the message doesn't say "atlas".
- Step 4: an unknown eye name is a note, not a problem, because the build skips just that entry. The check is also skipped while the game's files can't be read.
- Step 6:
  - the `.gitignore` line is anchored, or the shipped file would be ignored;
  - route 1 is flagged as likely empty;
  - `cmd_tables` writes into the data folder;
  - `test_ue4ss.py` is added.
- Step 8: the build now warns when palettes need the missing script loader. The five-minute try promised that warning, and only a log NOTE said it.
- Step 10: `OSError` is caught too.
- Step 13: `look_options` returns no eyes when the game's files can't be read.
- Step 14:
  - an unreadable file is never overwritten with the build's copy;
  - a missing one gets only the colours;
  - the Lua JSON round trip's limits are stated;
  - mtimes are `st_mtime_ns`, and the PUT answers the new one;
  - the Mouse look card doesn't send `expect`, so it isn't protected.
- Step 15: a cat is matched by its prefix, a new cat in the same slot starts a new record, and Put my cat back no longer undoes itself at the next Apply.
- Step 16: the fixture gets its `mod.json`.

**Simpler:**

- Step 8's note shows only what needs something, with one action each, and is the one Creator palettes note.
- Step 11 matches keys on the server with the build's own function (`POST /cat/match`) instead of alias lists ported to JavaScript.
- Step 13's "In your save now" card became the preview's "Cat shows: as it is now / with my changes" switch, the same switch as on Palettes: one card fewer.
- Step 1's Quick palettes refusal points at the Mods page, not the command line.

**Compatible:**

- Step 7's `"wcmods": "0.4.0"` is a key 0.3.0 ignores; the Share card line still covers 0.3.0.
- `cat-originals.json` is a new file. A cat changed before it existed records at its next Apply.
- `/cat/match` and the new `cat_info` and `look_options` keys only add.
