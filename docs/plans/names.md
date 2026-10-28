# Words: the Names page

Plan written 2026-10-28 from the audit of the Names page (`studio/sections/names.js`, `wcmods/names.py`, `wcmods/sections/names.py`, `wcmods/studio.py` names routes, `wcmods/world.py` and `wcmods/lua/world_names.lua`) and the skeptics' verdicts, and reviewed the same day against the maps, the verdicts, the code and the three branches under way (the review's corrections are listed at the end). It is scoped to the Names page and `names.json`. Work already under way elsewhere is referred to, not planned again:

- the test harness branch: `tests/unit/conftest.py`'s `studio`, `save` and `fake_game` fixtures and its `write_save` / `make_mod` helpers, which call `Studio.api` over temp folders; the DOM shim `tests/studio/lib/dom.mjs`, whose `routes` answer a page's API calls (the fake-API pattern for page tests); the Chromium driver `tests/studio/lib/browser.mjs` for e2e runs against a real studio; CI running `node --test "tests/studio/**/*.test.mjs"`;
- the Leaf and Bark look: per-page `studio/sections/<page>.css`, linked when the page's id is in app.js's `PAGE_STYLES`; `wc.pageHead({title, lede, help})`, where `help: "help:<page>"` opens the guide page in the help panel;
- the shell: save-time validation through each section's `collect()`, shown under the Editing-mod bar by `Studio.check_file`; the dirty guard; the `installed` bus event, which carries the build's manifest, and `wc.installedEvent`, which skips while the page has unsaved changes; the plain-words summary with a warnings count in the log drawer; `/uninstall` run as a logged task; help panels from `docs/guide/<page>.md`, listed in `docs/guide/README.md`.

## What it is for

A creator opens the Names page to make the forest sound like their own story. Their cat and the cats around them get the names they choose, the names the game hands out to new cats change, and the words on screen (a cat's line, a place, a quest, an item) can be rewritten without hunting for a key in a 9,000-row table. Everything they type should reach the game exactly as the page showed it. When it can't, the page should say why before Save.

## Where it stands

**What works, and how we know.** One planner (`names.Plan`) handles renaming, adding and removing prefixes, suffixes and rogue names, the ban list, cameo and any-name renames, and cat renames. It turns them into CSV edits in the mod pak and `name` ops in the save. In game:
- On 2026-10-25, cat renames showed on the HUD and the Select Your Cat screen: a fixed name (Callie), a new prefix (Fawnpaw) and a whole name made with it (Fawnstar).
- Renamed and added texts were read back from the game's string table: Mothpaw, Sparrowheart, Mothwhisper and the rogue Moss.
- On 2026-10-27, a cat renamed Fawnstar with an added prefix showed on the HUD once the pak had a container beside it (`docs/verified.md`).

The planner's full check, `selftest._names_plan`, covers a lot: renames reaching every combination, added texts in every language, kept suffixes, the ban list following renames, cats picked by name, place and `player` in one- and two-slot saves, story-role copies and old key forms. But it runs only against the installed game. Under pytest only `_rename_struct`, `_names_without_text` and `_csv_rows` run (`tests/unit/test_formats.py`). The page has a live preview with a debounce and a sequence guard, a cat search that unfolds the right game, and a JSON panel. The page's JavaScript has no tests.

**What is half-finished.**
- `weights`, `banned.clear`, `text` and `add.looks/clans/ranks` work in `names.py`, and the page keeps them as written (`names.js` `load()`, the `extra` object), but no control edits them.
- Areas, quest titles and item names are read for the mod menu (`world.place_names`, `world.item_names`) and can already be renamed through `text`, but nothing lists them. `place_names` also reads the game's own tables rather than the build's edited `Strings_EN`. So a renamed area may reach the HUD (unverified) but never reaches the menu pages.
- The preview never runs the "cats with no text" check that the build runs (`pipeline.names_without_text`). Forgetting an earlier rename (the × on a chip) is only warned about at Apply.
- These have never been checked in game (`docs/verified.md`, "Names beyond the text"): removed parts, added parts reaching new cats, ban-list edits, and the name screen's suggestions.
- The cats list is read once per mount and never refreshed after Apply.

**The audit's one high UX issue.** Apply's name warnings are easy to miss. The toast says "done", and "this cat will show as <MISSING STRING TABLE ENTRY>" is one line in the log. The shell's summary now counts warnings. The Names-page half is in steps 4 and 7: after Apply the page re-reads the cats and shows the ones that lost their text as a banner.

**Confirmed bugs.** Severity is as the skeptics set it. None of the checked claims was refuted.

1. [high] `wcmods/names.py:595`: a clan cat (or the player) given a whole name equal to a rogue name (Storm, Blaze, Fox, Ember, Thorn...) gets `STR_CAT_NAME_WCM_FIXED_<SLUG>` from `_new_ids`. `_custom_texts` returns early on the rogue match and adds no text. The save op is written to an empty name, the After cell is blank, and nothing warns. At build, `names_without_text` blames a mod being off, which is the wrong cause.
2. [high] `studio/sections/names.js:229`: a cat already renamed to a mod-made name is listed by its raw `STR_CAT_NAME_WCM_...` key. The rows come from `GET /names`, which is computed with an empty spec (`studio.py:561`), and are never re-rendered from a preview. `catKey` then uses that ID as the `names.json` key, which `_targets`/`_called` (`names.py:551, 562`) never match. Every later rename of that NPC through the page produces no save op, only a "no cat in your save is called ..." line in the Apply log.
3. [high] `wcmods/names.py:600`: a cat with no `SuffixNameId` (role RogueCat) given one of the game's prefixes gets `PrefixNameId=STR_CAT_NAME53` with no suffix. Strings_EN has no text under the bare key (only the 27 `STR_CAT_NAME53_<SUFFIX>` keys), so the game shows `<MISSING STRING TABLE ENTRY>`. The preview is blank, nothing warns, and `without_text` skips it because the key has no `_WCM_`.
4. [medium, lowered from high] `wcmods/pipeline.py:619`: "Take all mods out of the game" removes the pak without reading the save. Cats with `_WCM_` IDs show as `<MISSING STRING TABLE ENTRY>` (your cat as Cat 1), and nothing at that moment says which cats are affected. It can be undone from a backup, or by turning the mod back on, which the Settings row says only in general terms.
5. [low, lowered from medium] `wcmods/names.py:304`: `names` sets every English text equal to the name anywhere in `Strings_EN`. Renaming the cameo cat Rock also renames the crafting material Rock, and Fox the animal follows the rogue Fox. The card's note says so; only the changed-texts count hints at what else changed.
6. [low, lowered from medium] `wcmods/names.py:596`: a whole name that no prefix + suffix makes (Mothhart, Luna) becomes a fixed name with no warning and no mark on the row. It's documented, but the row doesn't say which rule applied.
7. [low, lowered from medium] `studio/sections/names.js:109`: rename, remove and ban keys written by hand in another case, or by ID, show empty boxes on the page. Typing adds a second key, which wins because it comes later, but the stale key stays and applies again when the box is cleared.
8. [medium] `wcmods/names.py:139`: `validate` checks only the container types. `weights: {"Otter": "lots"}`, `weights: {"Otter": {"ThunderClan": "lots"}}` and `add: {"Sparrow": {"clans": [1, 2]}}` pass and then crash `merge` or `_plan_affixes` with raw Python text; `rename: {"Otter": ""}` passes and makes names like "paw". At Apply the whole names section fails for every mod (one Plan for all). Only hand-edited or imported files carry these.
9. [medium] `studio/sections/names.js:39`: when `GET /names` fails once, the page shows "Couldn't read the game's names" over empty cards. Because `mount` returns normally, `app.js` never offers Try again. `names_preview` (`studio.py:650-656`) catches only `LookupError` around the save read, so a save the game is writing surfaces with the wrong cause.
10. [low, lowered from medium; the Lua path confirmed, the live suffix inferred] `wcmods/lua/world_names.lua:36`: `N.name` ignores the cat's role. A kit or apprentice whose IDs carry no `SuffixNameId` is labelled by its bare prefix in mod overlays and menu pages, while `names.display()` and the game use the rank's suffix.
11. [low, lowered from medium] `wcmods/names.py:506`: when the new IDs have no text, `plan_cats` still records the rename with an empty "to". The After cell is blank (the same as "no change") and "What this does" reads "Otterheart → ". This follows from 1 and 3.
12. [low, lowered from medium; from the RE map] `wcmods/world.py:59`: `place_names` assumes `<quest>.<Rank>.Title`. The 25 title rows with no rank segment (Progression.RankUp/RankUp2/RankUp3, Sleep.Rest1-13, SideQuest.Collect/Race/Trading/WinFights and the five Milestone ones) are filed under a cut-short quest key. The Menu pages' Quests and Cat pages then label those quests from their graph id ("Rank Up", "Rest1").

**Likely but unchecked** (low; no skeptic verified these):
- A prefix renamed to another prefix's text gets no clash warning (`names.py:318`).
- The "new prefix" row says "every clan, average" even when it copies another prefix (`names.js:124`).
- The template's `_help` points at a README section that doesn't exist (`wcmods/templates/names/names.json:2`).
- Preview warnings use command-line words such as `names --cats` (`names.py:498`).
- A fixed name on a cat whose suffix came from a part no longer in the tables previews as working but has no text (`names.py:611`).
- Two clan cats with byte-identical save text are merged into one (`names.py:656`).

## What a creator should be able to do

The page keeps its cards, but each one says what will happen in the creator's words, and nothing can be saved that leaves a cat without a name.

**The head.** It reads "Names" with a one-line lede ("Rename your cats, the names new cats get, and the words the game shows.") and the help panel from `docs/guide/names.md`. Under it, three short lines replace the 150-word banner:
- "Renames change the English text."
- "New names (a new prefix, a name of your own) are text this mod adds, so keep the mod on."
- "Cat renames go into your save when you Apply, after a backup."

A fold titled "If a cat shows as Cat 1 or <MISSING STRING TABLE ENTRY>" holds the recovery text. While the game's tables are being read, the cats card says "Reading the game's names…".

**Cats in your save** comes first.
- Each row has one box, "New name", with a line under it that the preview fills in:
  - "Moth + heart: grows with rank" for a prefix + suffix;
  - "Sparkle at every rank" for anything else;
  - "a rogue name" for an outsider given one.
- For a clan cat whose name isn't a prefix + suffix, a tick "grows with rank (Sparklekit, Sparklepaw...)" turns the name into the cat's own prefix. Outsiders (role RogueCat or RogueCatLeader) get no tick.
- The After install column never shows a blank for a changed cat. It shows the name, or a "no text" chip with a sentence saying why.
- A cat whose current name comes from a mod is listed by that name, whichever enabled mod gave it, and this mod's names count even while it's off. Its row says "name from a mod" and has a "Give it a game name" link. The link fills the box with the name the cat had, when the mod's entry knows it, or else with a prefix + suffix the game has for the cat's rank.
- A banner shows only when some cat would show as <MISSING STRING TABLE ENTRY> after the next Apply (its mod is off, or its rename was forgotten), with the same link per cat.
- The Earlier renames × asks first before forgetting a rename whose cat would lose its name.
- After Apply, the list shows the new names straight away.

**Prefixes, Suffixes, Rogue and loner names, and the Ban list** stay as they are, with these changes:
- the string-table IDs under each prefix go;
- a Reset appears on rows that have a change;
- the search box keeps its text through Add and Remove;
- the ban chips show the names after your renames (Lionstar, not Tigerstar, once Tiger is renamed Lion).

**Cameo cats and any cat name.** The cameo table stays. The Any name box gets type-ahead over the game's cat names. Once a name is typed, a line such as "also changes: the material Rock" appears, with a tick "everywhere", whenever the text also appears outside cat names.

**Places, quests and items** (new, folded at first). Three folds list the 50 areas, the quest titles grouped by quest with their rank, and the items' names, each with a Rename box.

**Lines the cats say** (new, folded at first; only once the in-game check in step 9 shows that a rewritten line reaches the dialogue box). A search box over the game's dialogue lines. Each hit shows who says it ("the aging leader", "you, the Brave answer", "a quest giver, Gather quest, Apprentice") and has a Rewrite box. Placeholders like `{THE AGING LEADER}` and `{PLAYER}`, and markup like `<B>...</>`, stay in the box, and a check line says when a rewrite dropped one.

**What this does** stays at the top as the summary, and every warning the planner raises for a row also appears beside that row.

**The five-minute first try:**
1. Open Names and type Sparkle for your cat. The line reads "Sparkle at every rank".
2. Tick "grows with rank". The line now reads "Sparklepaw now, Sparkle-something as a warrior".
3. Save to mod, then Apply to game, then play. The HUD says Sparklepaw.
4. Once Lines is there: back in the studio, find your clan deputy's line under Lines (search "borders"), rewrite it, Apply, and talk to the deputy.

## The plan

The steps are grouped by pull request. Each one leaves the page working. The planner comes first, because the page's new labels need the preview's new fields.

### PR 1: the planner (no dependencies)

**1. Every rename keeps its text (bugs 1, 3 and 11, and the unchecked fixed-name suffix case).** In `wcmods/names.py`:

- **Rogue names on clan cats (bug 1).** In `_custom_texts`, keep only `if self.split(name): return` for a whole name. A whole name that isn't a prefix + suffix then always gets its fixed texts (the bare key and every suffix combination), rogue match or not. The extra keys are harmless when an outsider takes the rogue ID: `_new_ids` already gives the rogue ID only to a cat whose `PrefixNameId` is a `STR_ROGUE_CAT_NAME`.
- **Game prefixes on outsiders (bug 3).** For `{"prefix": X}` where X is one of the game's prefixes, `_custom_texts` also sets the prefix's text under its bare ID (`_set_text(p["id"], p["final"])`). An outsider with no suffix then shows "Otter", the same way the game shows a rogue's own ID with no suffix. A clan cat never looks that key up.
- **Deciding whether a rename has text.** `plan_cats` checks the key the game looks up: `PrefixNameId` + (`SuffixNameId`, else the rank's `_KIT`/`_PAW`, else nothing), in `self.final`. It doesn't use `display()`'s fallback to the bare prefix, which would call a cat fine while the game shows it as `<MISSING STRING TABLE ENTRY>`. `display()` keeps its fallback only for naming a cat's current name.
- **Fixed names on a cat with an unknown suffix.** For a fixed name, or a cat's own prefix, on a cat that keeps a suffix the tables don't have (a part from a mod that's off), the planner first adds the text under that exact key and re-runs `_finish_strings()`. That function is made to run again, and the build hands `plan.edits` to the pak after `plan_cats`.
- **No text at all (bug 11).** If there is still no text, the op is skipped with a warning: `cats.<target>: the game would have no text for 'Otter' on this cat; pick a name the game has, or a name of your own`.
- **Outcomes.** Each cat's outcome is kept in `self.cat_how[<its first path>]`, keyed per cat because one key can pick several cats. It is one of `parts`, `fixed`, `rogue`, `prefix`, `own-prefix` or `none`. `cat_list` returns it as `how`, along with `mod_named` (the cat's current IDs carry `_WCM_`), which steps 4 and 7 use.
- **Clash warning.** Warn when a prefix or suffix is renamed to a text another part already has: "'Otter' renamed to 'Wren' would give two prefixes called Wren".

Format: no change to `names.json`.

Tests go in a new `tests/unit/test_names.py`. They use a tiny synthetic game built from CSV strings in a `tiny_game()` helper: the six name tables with three prefixes including Otter, the suffixes kit, paw, heart and star, the rogues Storm and Fury, and one banned row; the two filters tables (whose first header is `---`); and `Strings_EN` and `Strings_DE` with every combination.
- `test_rogue_name_on_a_clan_cat_gets_fixed_texts`: cats `{player: "Storm"}` adds `STR_CAT_NAME_WCM_FIXED_STORM` and `_HEART`, `with_mods == "Storm"` and `how == "fixed"`.
- `test_rogue_name_on_a_rogue_takes_the_rogue_id`.
- `test_game_prefix_on_a_rogue_has_a_bare_text`: `added_keys["STR_CAT_NAME53"] == "Otter"` and `with_mods == "Otter"`.
- `test_a_rogue_given_a_whole_name_gets_a_suffix_field`: `rename_struct` inserts `SuffixNameId`.
- `test_no_text_rename_is_skipped_with_a_warning`: a cat whose `SuffixNameId` is `_WCM_GONE` is given a prefix the tables have. There is no op, `how == "none"`, and the warning is raised.
- `test_fixed_name_keeps_a_suffix_the_tables_lack`: adds `FIXED_GLOW_WCM_GONE`.
- `test_prefix_rename_clash_warns`.
- `test_typo_whole_name_reports_fixed`: `how == "fixed"` for Mothhart.

Docs: the `docs/formats.md` `cats` bullets say three things: a rogue name on a clan cat is a fixed name; an outsider's new name is a whole name or a fixed one; and a rename the game would have no text for is refused with a sentence.

Game check, only when no other session has the game open (check `agent status`, and the UE4SS log's start time and loaded mods, first):
- Use the dev machine's test save, never a player's; its cat is an apprentice. Back the save up first.
- Make a scratch names mod with `cats: {"player": "Storm"}`, install it with `agent install --with`, launch to the world and take `agent shot` at once, while the HUD shows. The HUD should read Storm.
- Run the agent test `tests/game/test_names.py::test_added_texts_are_in_the_string_table`. It reads `STR_CAT_NAME_WCM_FIXED_STORM` with the test cat's suffix through `KismetStringTableLibrary`, the way `world_names.lua`'s `gameText` does: one object, no scans.
- Put the save back if nobody has played since.

**2. The names check says what is wrong (bug 8, and plain words).** Extend `names.validate` to the leaves, but refuse only what would crash `merge` or the planner (or, for an empty or null rename, what makes broken names), so no file that applies today is refused:
- rename values that aren't non-empty strings: `names.json: prefixes.rename.Otter should be the new text, not empty`;
- `weights` entries that aren't an object of numbers per column (a number in quotes still counts, as `float()` reads it today): `prefixes.weights.Otter should be an object like {"ThunderClan": 0.07}` and `prefixes.weights.Otter.ThunderClan should be a number`;
- inside an `add` entry that is an object: `like` that isn't a string, `clans`/`ranks` that aren't objects of numbers, and `looks` that isn't an object (`prefixes.add.Sparrow.clans should be an object like {"RiverClan": 0.05}`). An `add` value that isn't an object is still read as `{}`, as it is today;
- `remove`, `banned.add` and `banned.remove` items that aren't strings;
- a `cats` entry's `was` that isn't a string;
- `names` and `text` values that are lists, or objects other than step 5's `{"to": string, "everywhere": bool}`.

Shapes that do nothing today stay warnings from the planner rather than refusals, because a refusal would block the whole Apply. That covers a `cats` value that's neither a string nor an object, and an object with two of `name`, `prefix` and `fixed`.

The planner's own warnings lose their command-line and JSON words. For example, `use a cat's place from names --cats` becomes `pick the one you mean from the list; it's renamed by its place`, and `give a name, {"prefix": ...}` becomes `give it a new name`. Each warning is also kept with the row it belongs to, in `plan.notes`, a list of `(where, text)` pairs such as `("cats.player", ...)` or `("prefixes.rename.Otter", ...)`, so the page never has to parse sentences.

`merge` and `_plan_affixes` then never see a bad leaf. The same `validate` already runs on `POST /names/preview`, so "What this does" shows the sentence instead of a Python error. The shell's `Studio.check_file` runs it through `NamesSection.collect` and shows it under the Editing-mod bar as it is.

The template's `_help` points at `docs/formats.md`, "names.json" (unchecked low bug).

Tests:
- `test_validate_reports_leaf_mistakes`, parametrized over each shape above, asserting the sentence and that no `AttributeError` or float error escapes `Plan`;
- `test_validate_accepts_every_documented_shape`, using the template's `_example` block and `formats.md`'s example;
- `test_validate_keeps_todays_tolerant_shapes`: `add: {"Sparrow": true}` and a `cats` entry with both `name` and `fixed` still pass;
- `test_warnings_have_rows`.

The selftest's expected warning texts follow the rewording.

Docs: `docs/formats.md` adds the `clans`/`ranks`/`looks` options of `add`, which are implemented but undocumented. No game.

**3. The planner check runs in CI.** Port `selftest._names_plan` to `tests/unit/test_names.py` on the tiny game. The selftest keeps running against the installed game. The port adds:
- the merge cases: mod A removes Pigeon and mod B adds it (kept); A adds Sparrow and B removes it (not added); a later `cats` entry wins;
- two adds numbering rows 91 and 92 in both the part table and its filters table (keyed by the filters table's `---` column);
- a slug clash ("Sun light" against "Sun-light"), warned about and skipped;
- `banned.clear` plus an add;
- removing `kit`: it's kept, with a warning;
- `without_text` after a build with empty ops.

Bug 16 (unchecked): `cats_in_save` keeps two `Clans` paths with identical text as two cats, and merges a `NarrativeRoles` copy only into the first of them (`test_identical_clan_cats_stay_two_cats`). Docs counts in `docs/reverse-engineering.md` and `docs/mechanics/npcs.md` become 90 prefixes, 27 suffixes, 23 rogues and 31 banned, on the current tables. No game.

### PR 2: the routes (after PR 1; uses the harness and shell branches)

**4. Renamed cats are listed by their names and can be renamed again (bug 2, the save half of bug 9, and the preview's missing no-text check).** In `wcmods/studio.py`, `names_preview(spec, mod_id=None)` builds two plans:
- **The page's own plan**, from the page's spec alone. It gives "What this does": `changed_texts`, the cards' `final` texts, and the warnings that aren't about cats.
- **The "all" plan**, from `names.mod_specs` of the enabled mods with the page's spec standing in for its own mod's file at that mod's place in the priority order. The page's mod is included even while it's off, because Save to mod turns it on. This is the same merge `cat_info` does. A mod whose `names.json` fails `validate` is left out of this plan with one warning naming it; today one bad file fails the whole preview.

The all plan gives the cats list, `renames` (the page's own entries only), the `cats` warnings, the per-row `notes`, and a new `losing_text`. `losing_text` is `names.without_text(cats, ops, all.final.__contains__)` returned as `[{"target", "name", "key"}]`: the cats that would show as <MISSING STRING TABLE ENTRY> if Apply ran now.

Route changes:
- `GET /names` does the same with an empty spec and no mod, so it shows the enabled mods alone.
- `POST /names/preview` takes `{"spec": ..., "mod": "<id>"}`.
- Around the save read, catch `ValueError` and `OSError` as well as `LookupError` (`SaveGame` turns a cut-short file into `ValueError`). Answer `cats: []` with `save_problem: "Couldn't read your save (<reason>); the cats list is empty until it can be"`.
- `_changed_texts` returns both a count of names (renamed or added parts and cats) and a count of texts (keys).

In `names.py`, `_called` also matches the cat's `PrefixNameId + SuffixNameId` or its bare `PrefixNameId`. A cats key or `was` written as an ID by an older page or by hand keeps working, and `cats_called` (cats.json's other cats) gets the same.

Tests go in `tests/unit/test_studio_names.py`. They use the harness's `studio` fixture with `studio._names` set to a `GameNames` over the tiny game (`names_preview` reads the tables once and keeps them), saves written with `write_save`, and mods made with `make_mod`.
- `test_get_names_lists_a_mod_named_cat_by_its_name`: a save with `STR_CAT_NAME_WCM_FIXED_SPARKLE`/`_HEART` and an enabled mod naming it gives `name == "Sparkle"` and `mod_named`.
- `test_preview_uses_the_pages_spec_for_its_own_mod`: the page's spec without the Sparkle entry lists that cat in `losing_text`.
- `test_second_rename_of_a_mod_named_cat_reaches_the_save`: `{"Sparkle": "Dawnfur"}` gives one op.
- `test_id_key_still_finds_the_cat`.
- `test_a_broken_names_json_in_another_mod_is_left_out_with_a_warning`.
- `test_preview_survives_an_unreadable_save`: a cut-short `.sav` gives 200 with `save_problem`, not 500.
- `test_get_names_without_a_save`.
- `test_check_file_says_the_names_mistake`: the shell's `check_file` on a names.json with `weights: {"Otter": "lots"}` returns step 2's sentence.

Docs: `docs/formats.md` says a cats key may also be the cat's current IDs. No game.

**5. "Any name" renames cat names unless told everywhere (bug 5).** `names` values stay strings for the common case, but the planner limits them to name keys (`STR_CAT_NAME*`, which covers the cameo `_ICONIC_` and `_WCM` keys, and `STR_ROGUE_CAT_NAME*`). An object form opts into every key:

```json
"names": { "Rock": "Pebblepaw", "Fox": { "to": "Russet", "everywhere": true } }
```

The preview returns `names_hits`: for each entry, the keys it matches, split into `cats` and `elsewhere`, each with a plain label from the key's family (`STR_CRAFT_MATERIAL_NAME_20`: "the material Rock"; `STR_CHAR_NAME_FOX`: "the animal Fox"; `QST_*`: a quest line; anything else: "other text").

This is a behaviour change, and it gets a migration notice. A plain-string entry that also matched text outside cat names gets a planner warning, shown in the preview and at Apply: `names.Rock: the material Rock keeps its name now; tick "everywhere" to rename it too`. The docs say it too. Old wcmods can't read the object form, so the page writes it only when "everywhere" is ticked.

Tests:
- `test_names_rename_touches_cat_keys_only`;
- `test_names_everywhere_touches_every_key`;
- `test_old_names_entry_warns_what_it_no_longer_renames`;
- `test_preview_lists_what_else_a_name_hits`.

Docs: the `docs/formats.md` `names` bullet. No game. PRs 2 and 3 are released together, because PR 3 holds the "everywhere" tick.

**6. Taking mods out says which cats lose their names (bug 4).**
- Add `pipeline.cats_losing_text(cfg)`: every cat in the save whose name IDs carry `_WCM_`, with your cat first. The game's own text never has such a key, so it needs no game tables and works without a game folder. It returns `[]` with no save or an unreadable one.
- `pipeline.uninstall` logs one warning naming them (your cat first, five shown, then "n more") before removing anything. It still returns the list of removed paths, which `cli.cmd_uninstall` and the route use.
- The `/uninstall` route works out `losing` before uninstalling and answers `{"removed": [...], "losing": [...]}`. The harness's `test_uninstalling_from_a_game_with_nothing_in_it_removes_nothing` is updated to expect `"losing": []`.
- `GET /names/losing` answers the same list for the Settings page.

Tests:
- `test_cats_losing_text_lists_mod_named_cats`;
- `test_cats_losing_text_without_a_save` (gives `[]`);
- `test_uninstall_answers_losing`.

Docs: a `docs/formats.md` paragraph on uninstall. No game.

### PR 3: the page (after PR 2; uses the shell, look and harness branches)

**7. The page tells the truth about each row (bugs 6, 7, 9 and 11, and the UX notes).** In `studio/sections/names.js`:

**Loading and failure.**
- The cats card says "Reading the game's names…" until `GET /names` answers.
- When that fails, `mount` throws without drawing a card of its own, so `app.js` shows its message and Try again.
- A `save_problem` shows in the cats card, with a Try again that re-fetches `/names`.

**The head.**
- `wc.pageHead({ title: "Names", lede, help: "help:names" })`, then the three lines, then the "If a cat shows as Cat 1…" fold. The fold explains three ways back: turn the mod that named the cat back on, put a backup back, or use Give it a game name.
- `app.js` gets "names" in `PAGE_STYLES`, so `studio/sections/names.css` is linked.

**Cat rows.**
- One "New name" box. What it stores:
  - a plain string, and the planner picks parts, rogue or fixed and reports which in `how`;
  - or `{"prefix": X}` when "grows with rank" is ticked;
  - a place key adds `was`, as it does today (`{"name": X, "was": ...}`).
- Where the tick shows: for a clan cat whose name isn't a prefix + suffix, never for role RogueCat or RogueCatLeader.
- Old entries load unchanged. An entry written by the old three-way select or by hand (`{"fixed": X}`, `{"name": X}`) fills the box and stays exactly as written until the box is edited, so every older file loads and applies the same.
- The outcome line under the box is filled from `how` and `with_mods`.
- The After cell shows a "no text" chip with the planner's sentence when `how == "none"`.
- A row with `mod_named` has a small "name from a mod" note and a "Give it a game name" link. The link fills the box with the first of these that works:
  1. the entry's key or `was`, when that's a name the game can make (so `Wrenheart: {"fixed": "Sparkle"}` offers Wrenheart back);
  2. a game prefix with a suffix the tables give that rank (`_KIT`, `_PAW`, `_STAR`, or a warrior suffix for the other ranks);
  3. a rogue name, for an outsider.
- `catKey` keys a cat by its place, with `was`, when `mod_named` is true and the listed name is still its raw IDs (the mod that named it is off). Step 4's `_called` makes that key work.

**Updating without losing focus.**
- After each preview, rows update in place: the name, the outcome line, the After cell and the row notes. No card is rebuilt while the creator types, so focus stays put.
- A card is rebuilt only when its own list changes (Add, Remove, a ban, a re-fetch after Apply), and it keeps its search box's text.

**After Apply.**
- The page listens with `wc.bus.on("installed")` rather than `wc.installedEvent`: re-reading `/names` doesn't touch the file, so it should also happen while the page has unsaved changes.
- It re-fetches `/names`, so the cats list and Earlier renames show the new names at once.
- A banner lists the cats in `losing_text`, which is the Names-page half of the high UX issue.

**Loading old files.** `load()` normalises rename, remove and ban keys to the game's text (case-insensitive, or by ID, through `game.prefixes`, `suffixes`, `rogues` and `banned`). It merges duplicates and shows one toast about keys it couldn't place.

**Warnings beside rows.** They come from the preview's `notes` (step 2). They are drawn beside their row or chip, as well as in "What this does".

**Forgetting an earlier rename.** The Earlier renames × first previews the spec without that entry. When that preview's `losing_text` names a cat, it asks: "Forget this rename? Wrenheart would show as <MISSING STRING TABLE ENTRY> until you give it another name".

**Small changes.**
- The string-table ID under each prefix goes.
- A Reset appears only on rows that have a change.
- The "new prefix" row shows the copied part's clans when `like` is set (unchecked low bug).
- Ban-list chips show names after this mod's renames.
- Slot headings read "Your 2nd game (Duskfang's)", and story roles are split into words.
- "What this does" says "N names" and "N texts" separately.
- The Places and Lines cards (steps 8 and 9) start folded, so the first view is the cats, the parts and the ban list.

**The Settings page.** "Take all mods out of the game" first asks `GET /names/losing`. When the list isn't empty, it shows "3 cats in your save have names only your mods give (your cat Sparkle, Wrenheart, ...). After this they'll show as <MISSING STRING TABLE ENTRY> until you put a backup back, or give them game names on the Names page and Apply first." with two buttons, "Take them out anyway" and "Open Names". Otherwise it confirms with two presses, as today.

Tests run under node:test with the harness's DOM shim, using `dom.routes` as the fake API for `/names`, `/names/preview`, `/names/losing`, `/mods` and the mod's file, in `tests/studio/names.test.mjs`. The shim grows what `names.js` needs (`dataset`, `details` `open`/`toggle`) if it lacks it.
- `names_page_recovers_from_a_failed_get`: the first GET answers 500; after Try again the page renders.
- `save_problem_has_try_again`.
- `typo_name_shows_fixed_outcome`.
- `rank_tick_writes_a_prefix_entry`.
- `outsider_has_no_rank_tick`.
- `old_fixed_entry_loads_and_stays`.
- `no_text_chip_shows`.
- `case_insensitive_key_fills_the_box`: `{"prefixes": {"rename": {"otter": "Moth"}}}` fills the Otter box, and `toJson` keeps one key.
- `search_text_survives_an_add`.
- `rows_update_without_losing_focus`.
- `earlier_rename_asks_before_forgetting`.
- `give_it_a_game_name_offers_the_old_name`.
- `apply_refetches_the_cats_while_dirty`.
- `out_of_order_previews_the_later_wins`.
- `settings_take_out_asks_when_cats_would_lose_names`.

Docs:
- `docs/guide/names.md`, written for the help panel (what each card does, and the Cat 1 fold's text), listed in `docs/guide/README.md`;
- the `README.md` Names row;
- a "Why does my cat say Cat 1" entry under a README troubleshooting heading, which also points at Settings and repair.

No game.

### PR 4: places, quests and items; WCModsNames fixes (after PR 3; a game session for its checks)

**8. Places, quests and items from a list, and WCModsNames' own fixes.**

**Quest titles (bug 12).**
- `world.place_names` splits off the last tag segment only when it is Apprentice, Warrior, Deputy or Leader. Otherwise it keys the title by the whole tag before `.Title`, with rank `""`; `N.quest` already falls back to any rank.
- Tests in a new `tests/unit/test_world.py`: `test_place_names_rankup_titles` (a `Quest.Procedural.Progression.RankUp.Title` row lands under its own tag), plus the RE map's cases: `.Title2` rows are ignored, a short `LocationsData` row is skipped, and an unreadable `Strings_EN` gives `({}, {})`.

**The list route.** Add `GET /names/texts`. It answers:
```json
{"areas": [{"key": "STR_RIVERCLAN_ZONE_5", "code": "R-05", "text": "Willow-Weep"}],
 "quests": [{"key": "QST_Gather.Apprentice.Title", "tag": "Quest.Procedural.Survival.Gather", "quest": "Gather", "rank": "Apprentice", "text": "Feathering the Nests"}],
 "items": [{"key": "...", "tag": "Gameplay.Inventory.Consumable.MediumHealingHerb", "text": "Marigold"}]}
```
- Areas and quests come from a new `world.place_texts(read_text)`, which keeps each one's string key (`LocationsData.csv` `IdStrName`, `QuestDialogues.csv` `StringKey`). `place_names` keeps returning the shapes WCModsNames uses.
- Items come from `DT_QuestObjectsInfo` through the studio's table reader. Rows whose `Name` is inline text rather than a key can't be renamed through `text`, so the page lists them as "fixed by the game".

**The card.** "Places, quests and items" lists them in three folds, with Rename boxes that write `text` by key:

```json
"text": { "STR_RIVERCLAN_ZONE_5": "Willow Hollow", "QST_Gather.Apprentice.Title": "Gather for the elders" }
```

- `load()` moves `text` out of `extra` into `spec.text`, so the boxes show it and the JSON panel keeps it.
- Keys the lists don't know stay as rows under "Other text", with the key shown.

**The menu pages.** In `pipeline.build`, `place_names` and `item_names` read the build's edited `Strings_EN` (from `ctx.files` when the names section edited it, as `names_without_text` already does), so WCModsNames' `N.area`, `N.quest` and `N.item` follow a rename in the menu pages.

**Bug 10, gated on what the game does.**
1. First check whether the case happens at all. `python wcmods.py names --cats` on the test save lists apprentices and kits whose saved IDs have no suffix. If there are none, the Lua change waits and `docs/SDK.md` says why.
2. If there are some, read one such cat's `CustomData` (`SuffixNameId`, `Role`) in game while standing next to it, with a small `SphereOverlapActors` around the player rather than a scan. Do it in the same session as the checks below.
3. If the suffix is empty at runtime, `N.name(prefix, suffix, role)` defaults an empty suffix from a `rankSuffix` table that `world.names_data` writes. The callers pass the role:
   - `Cat:name` (`game.lua:1232`), which also needs `Role` read, since `Cat.lookFields` doesn't read it yet;
   - WCModsWorld's labels (`world.lua:212`, `d.Role`);
   - the C++ `cat_name` (`wcmods/cpp_sdk/include/WCMods/World.hpp:347`, one more `get`).
4. The role comes from Unreal as an enum. Its names are read from the game by name, the way `remap.lua` reads `ECommands`, not from a hard-coded list (`Game.enums.rank` is the player-rank enum, not the role).
5. If the game fills the suffix, only `docs/SDK.md`'s `N.name` note changes.
6. Test: `test_names_lua_has_rank_suffixes` (`tests/unit/test_lua.py`).

**Other tests:**
- `test_texts_lists_areas_quests_and_items` (route, with tiny tables holding one of each);
- `test_items_with_inline_text_are_marked_fixed`;
- `test_build_names_lua_uses_the_edited_strings` (a `text` rename of an area appears in `names_lua`'s `areas`);
- the page test `renaming_an_area_writes_text_by_key`.

Docs: a `docs/formats.md` `text` bullet with the three examples; `docs/guide/names.md`.

**Game check.** It's needed: the RE notes rate the string-table path likely but unverified for these screens. Use the same rules as step 1 (test save, no other session, backup first). Install a mod that renames one area, one quest title and one item, then look by hand at the area popup when crossing into that area, at the quest log and at the inventory. Record the result in `docs/verified.md`. If a screen doesn't follow, the fold says so ("the quest log shows the game's title; the mod menu shows yours").

### PR 5: Lines the cats say (only after the dialogue check passes)

**9. Lines the cats say.** This is gated, because the RE map lists it as an open question (RE gap 3): whether the dialogue box reads its line from the string table or from text cooked into the dialogue graph. Two checks come first, before any page work:
- **(a) Static, no game.** Extract one `NpcDialogue` package with `python wcmods.py extract` and read a `QuestDialogueTalkingNode.Paragraph` with `formats/cooked.py`. FText history type 11, with the table `SwtStrings` and a `QST_` key, means the box reads `Strings_EN`.
- **(b) In game, under step 1's rules.** Make a scratch mod whose `text` rewrites every `QST_Story.Monologue.Filler.*` line of the test cat's clan to one marker. Install it with `agent install --with` and talk to the clan deputy or another camp cat. Use lines the test cat can reach now, not the aging leader's opening line, which needs the story at that point. Also run the agent string-table read from step 1 for one of those keys.

`docs/verified.md` records the result either way. If the box shows the old line, the Lines card isn't built, and "Not in this plan" says why.

Once (b) shows the marker:

**The route.** Add `GET /names/lines?q=<text>&limit=60`. It returns hits over the dialogue lines from a small `wcmods/lines.py`, joined once per studio run from `Strings_EN` and the two dialogue tables:
```json
[{"key": "QST_Story.Short.TheAgingLeader.Main.1.Context.1", "text": "I'm troubled by this new prophecy...", "who": "the aging leader", "you": false, "trait": "", "where": "story", "quest": "", "rank": ""}]
```

**The join.**
- `StoryDialogues.csv` and `QuestDialogues.csv` (columns `---` (the tag), `Score`, `ClanBonding`, `Talker`, `Trait`, `VoiceOver`, `StringKey`, `DebugText`) map each `StringKey` to a tag, a `Talker` (NPC or Player) and a `Trait`. The join is by `StringKey`, because the tag doesn't always equal the key (some tags end in a stray `.` or a rank).
- The story tag's role segment becomes words: `TheAgingLeader` is "the aging leader", `Monologue.Filler.ThunderClanDeputy` is "a ThunderClan deputy".
- The quest tag's fourth segment names the quest (`Gather`), with its rank segment. Step 8's quest titles give the quest's name when it has one.

**Search.** It runs on the server, case-insensitive, over the text and the "who". The 4,131 `QST_` lines are never sent to the page all at once.

**The card.** "Lines the cats say" has a search box, a result list (the text, who says it, and a Rewrite box) and, below, the lines this mod already rewrites.
- A Rewrite writes `text` by key.
- The box keeps `{THE AGING LEADER}` and `{PLAYER}` placeholders and `<B>...</>` markup as they are.
- When a rewrite drops a placeholder, the card's check line says so: "the line had {THE AGING LEADER}, the cat's name; keep it so the name still shows".
- It's English only, like names; the other languages keep the game's line, and the card says so.

**Tests:**
- `test_lines_join_story_and_quest_tables`: one story row and one quest row, with the right who and where;
- `test_lines_search_is_case_insensitive`;
- `test_lines_limit`;
- `test_lines_without_dialogue_tables`: with the tables missing, lines come from `Strings_EN` with `who == ""`;
- the page tests `rewriting_a_line_writes_text_by_key` and `dropped_placeholder_warns`.

Docs:
- the `docs/formats.md` `text` bullet gains a dialogue example;
- `docs/guide/names.md`;
- `docs/mechanics/quests-and-bonding.md` gets the two tables' columns in one paragraph;
- `docs/reverse-engineering.md` gets what (a) found about `Paragraph`.

## Not in this plan

**Brand-new whole names that the game hands out to new clan cats** (Luna for a kit). This is known impossible: the game builds NPC names from the prefix and suffix tables, and only rogues take whole names (`docs/reverse-engineering.md`, Names). As a fixed name for an existing cat it works, and that's step 1.

**Renaming a cat without leaving the game.** Needs RE. The save is written by the game's own save manager, and it's unknown whether the HUD re-reads the name without a reload.

**Cameo cats' looks together with their names.** Needs RE. The cameo cats have their own skeletal meshes and materials, not colour slots.

**Adding a dialogue line, a choice or a branch, or changing which answer is right.** Needs RE. The dialogue graphs are cooked packages whose format isn't read. `text` only rewrites lines the game already shows, and what an answer's Score and ClanBonding do is inferred.

**Lines in other languages.** Not impossible, but per-language `text` needs a format and a page of its own. This plan rewrites English, as renames do.

**Name rules and extras.** Weights and per-clan name rules, name presets, a random-name button, a "Clear the whole ban list" tick (`banned.clear`) and translations for added names are all known possible but not planned here. New parts reaching new cats, ban-list edits and the game re-reading the weights have never been seen in game (`docs/verified.md`; RE gap "newly added prefixes"), so these come after that check. The check needs a new game started in the shared install, with a mod that leaves two prefixes and adds one, and every NPC's `PrefixNameId` then read one object at a time.

## Open questions

- Should `names` stop touching non-cat texts by default (step 5)? It changes what an existing mod's `"names": {"Rock": "Pebble"}` does. The plan says yes, with the "everywhere" tick, a warning on the old entry, and a line in the docs. The alternative is to keep renaming everything and only show what else changes.
- Should "Take all mods out" refuse while cats would lose their names, or warn and give a choice? Step 6 warns.
- Does the Lines card belong on the Names page, or does the page become "Words" with Names, Places and Lines as its three parts? The audit asked about the Names page; the nav label is the owner's call.
- Should a rewritten line that drops a `{ROLE}` placeholder be refused at save, or only warned about? Step 9 warns.
- Should the Lines search cover every `Strings_EN` text (settings, tutorials, achievements) under an "all words" tick, or only dialogue? Step 9 does dialogue only; the route could take `all=1` cheaply.

## Review corrections (2026-10-28)

**Facts**
- Bug 3 was high in the audit and stayed high; the skeptic didn't raise it. Bug 10 was lowered from medium. The RE map's confirmed `place_names` bug is added as bug 12.
- Bug 9's line is `studio.py:650-656`.
- The test cat on the dev save is an apprentice, not Fawnstar. Fawnstar and Cat 1 were a player's report, reproduced here.
- Game checks now follow the shared-game rules: check who launched the game, back the save up, take the HUD shot right after launch, and run no scans.

**Planner**
- Step 1 checks text on the key the game looks up, not `display()`'s bare-prefix fallback. Otherwise its own no-text test would pass a cat the game shows as missing once bare prefix texts exist.
- Step 1 adds the fixed-name suffix fix that its test already expected.
- Outcomes are kept per cat, not per key.
- Step 2 refuses only shapes that crash or break today, so no mod that applies now is refused. Shapes that do nothing today stay warnings.

**Routes**
- `uninstall` keeps its return value, because `cli.cmd_uninstall` uses it. The route adds `losing`, and the harness's exact-match uninstall test is updated.
- `losing` is simply "has `_WCM_`" and needs no game tables.
- The preview keeps "What this does" to the page's own mod, while the cats come from all enabled mods. A broken names.json in another mod no longer fails the preview.
- `losing_text` is now defined (it was used but never specified). Earlier renames' × previews the spec without that entry, because the current preview can't list a cat that the entry still keeps named.
- `names`'s new default gets a migration warning, and the object form is written only when "everywhere" is ticked.

**Page**
- It re-fetches on `bus.on("installed")`, since `installedEvent` skips while the page has unsaved changes.
- Rows update in place, so typing never loses focus.
- `PAGE_STYLES` in app.js needs "names". The guide index lists names.md.
- Page tests use the DOM shim's `routes`, not the Chromium driver, which runs a real studio that has no game tables.
- The banner shows only cats that would show as missing; other mod-named rows get a quiet note.
- One stored form per cat row, and old forms load unchanged, so the select-or-box question is settled.
- Added the loading line and ban chips that show renamed names (both in the audit's UX notes).

**Gating**
- Lines are gated on a static check and an in-game check, using lines the test cat can reach.
- The bug 10 Lua change is gated on whether the case exists. "Pass the role they already read" was wrong: none of the callers read `Role`. The role is an enum to read by name, and the files involved (`game.lua`, `world.lua`, `World.hpp`) are added.

**Structure**
- Split into 5 PRs, so the planner fixes merge with no dependencies, and the gated Lines work can't hold back the places card.
