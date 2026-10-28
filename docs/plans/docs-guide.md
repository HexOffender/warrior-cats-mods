# The creator guide and the docs

A plan for the help a creator reads: the guide inside Clan Mod Studio (`docs/guide/`, shown by the
studio's Help panel), the README, `docs/README.md`, `docs/formats.md` and the smaller docs, and the
tests that keep them true. It comes from the 2026-10 audit maps for the docs, the shell and the
separate mods, the skeptics' verdicts on every high and medium claim in those areas (26, none
refuted), and a re-read of the code on `3af2898`. Low claims were not checked by a skeptic; the ones
this plan acts on were re-read in the code and say so.

## Work already under way, and who writes what

Three branches are not planned again here:

- **Tests** (`claude/studio-tests`): `tests/unit/conftest.py` with the `studio`, `fake_game` and
  `save` fixtures and `make_mod`, the HTTP handler test, `tests/studio/lib/browser.mjs`, node:test
  units for `studio/lib`, CI with Node.
- **Look** (`claude/studio-look`, 4a597a8): Leaf and Bark, per-page `studio/sections/<page>.css`, and
  `wc.pageHead({eyebrow, title, lede, help})`.
- **Shell** (`claude/studio-shell`, read at c97edf4). For the docs it already has:
  - `wcmods/guide.py`, the guide's renderer: headings (h1-h4), paragraphs, bullet and numbered lists
    one level deep, fenced code, bold, italic, inline code, links, pictures from
    `docs/guide/images/`; **no tables**. `other.md#slug` opens in the panel; `../formats.md#x` and
    `../../README.md` open on GitHub (`blob/main`); anything else is left as text.
  - `GET /api/help/<page>` (`index` is `README`) and `/help/<page>` on its own; the top bar's Help
    button opens the panel on the index; `pageHead`'s `help: "help:<page>"` puts a "How this works"
    button in a page's head that opens `docs/guide/<page>.md`. A `help` without the `help:` prefix is
    still a doc path opened on GitHub. No section uses `pageHead` yet on either branch.
  - `docs/guide/README.md` (the index: one entry, How Clan Mod Studio works) and
    `docs/guide/studio.md` (your mods folder, the Editing mod bar and My mods, Save to mod, Apply to
    game and Play, the log, What Undo means here, where your files are).
  - README bullets for Help, the log and Last apply, Restart the studio; the `docs/README.md` row for
    `guide/`; SDK.md's `wc.js` table and route list; ARCHITECTURE.md rows for `studio/` and
    `docs/guide/`.
  - Fixes for docs-area bugs: the Settings page builds its list of Make pages from `/info`; the
    "not installing" message words the way past it per surface (`InstallBlocked`: `--force` on the
    command line, Apply the rest anyway in the studio); a damaged `wcmods.json` is set aside and the
    studio says so; a mod whose `palette.json` has the wrong shape is listed with its problem
    (`mods.palette_problem`, `palettes.load` raising only `ValueError`) instead of failing `GET /mods`.

The other feature plans of this overhaul each write or extend the guide page of the studio page they
change. This plan sets the rules every page follows, writes the pages no other plan writes, and
tests all of them. One writer per page:

| Studio page (section id) | Guide page | Written by | Extended by |
|---|---|---|---|
| the index | `README.md` | shell | this plan (step 2: the list, the words) |
| how the studio works | `studio.md` | shell | this plan (step 2: Undo) |
| Mods (`mods`) | `mods.md` | mods-setup step 3 | console-lua (one paragraph) |
| Mod packs (`packs`) | `packs.md` | this plan (step 6) | mods-setup step 6 |
| Settings and repair (`settings`) | `settings.md` | mods-setup step 7 | |
| Palettes (`palettes`) | `palettes.md` | this plan (step 3) | palettes-cat |
| Your cat (`cat`) | `cat.md` | this plan (step 3) | palettes-cat |
| Controls (`controls`) | `controls.md` | controls step 10 | |
| Names (`names`) | `names.md` | names plan | |
| Items (`items`) | `items.md` | this plan (step 4) | items-animations |
| Animations (`animations`) | `animations.md` | this plan (step 4) | items-animations |
| Characters (`npcs`) | `characters.md` | story steps 3 and 9 | |
| Questlines (`quests`) | `questlines.md` | story steps 4 and 9 | |
| Game data (`data`) | `data.md` | this plan (step 5) | data-save steps 3-4 |
| Save (`save`) | `save.md` | this plan (step 5) | data-save steps 6-8 |
| Console (`console`) | `console.md` | console-lua | |
| Tweaks (`tweaks`, planned) | `tweaks.md` | console-lua step 7 | |
| sharing | `sharing.md` | this plan (step 6) | |
| when something doesn't work | `trouble.md` | this plan (step 6) | |

Whichever lands first writes the page in this plan's form (the rules in step 2); a later plan adds to
it. Page names are what the creator reads in the panel's "Open in a tab" address, so Characters and
Questlines keep `characters` and `questlines` (as the story plan names them) although their section
ids are `npcs` and `quests`. No runtime map is needed: each page names its guide page in its own
`pageHead` call. The table above goes into `docs/ARCHITECTURE.md`'s "Where things are named" as a
fourth column (step 2), and `test_guide.py` checks the two agree.

## What it is for

A creative person who has never modded anything opens a page in Clan Mod Studio, wonders what it
will do to their game, and presses "How this works" beside the title. The panel opens on that page's
guide, in the studio, without the internet: what the page changes in the game, a first try that
takes five minutes and ends with where to look in the game, what can and can't be done (the limits
the game really has, so nobody spends an evening on something that can't work), how to tell the
change arrived, the mistakes people make, and how to undo it. Every page has the same six parts in
the same order, names the buttons exactly as the page shows them, and explains each word they may
not know (slot, script loader) by a link to one short list. Nothing in it asks for a command line.

The README stays the page for playing with mods and points creators at the guide in its first
lines; `docs/README.md` puts the guide first for makers and keeps `formats.md`, `scripting.md` and
`SDK.md` for people who write files or code. The reference docs stop contradicting the code, and a
test fails the next time they do.

## Where it stands

**What works, and how we know.** The reference docs are accurate where the audit spot-checked them
(23 claims against the code). `python -m pytest tests/unit` passes (176 on `3af2898`); no test reads a
doc except `test_mods.py:53` (C++ headers against SDK.md). For this plan, three probes ran read-only
on `3af2898`: all 167 relative links and anchors in README.md and `docs/**/*.md` resolve; every key
the code reads from `wcmods.json` (12) has a row in formats.md's table; and formats.md's JSON
examples for `palette.json` (three blocks), `cats.json`, `mouselook.json`, `npcs.json`,
`quests.json` and `names.json` pass `palettes.load`, `catcolours.validate`, `mouselook.validate`,
`story.read` and `names.validate`.

**What is half finished.**
- No creator guide exists beyond the shell's two pages; the creator's path is README.md:4 ("To make
  them, start at docs/README.md") to `docs/README.md:9-11` to `formats.md`, a reference organised by
  file name. Steps 2-6.
- `wc.docLink` is used by two pages (`console.js:30`, `controls.js:90`); the other pages link no doc.
  Step 7 (each page's plan, through `pageHead`).
- Replacement files (`files/`) are documented for creators (`wcmods/templates/files/HOW-TO.md`) but
  every step is a command; the same tables (CatSize, Scars, NpcGenerator) are on the Game data page,
  and nothing says so. Step 5 (`data.md` names them); `files/` stays a modder's feature in SDK.md.
- `colour_tables.json` is read by `GET /game/tables` (`studio.py:434-437`) and named in
  `formats.md:85`, but only `python wcmods.py tables` writes it (`cli.py:543-558`), and no doc says
  so. Step 1 says so; the palettes-cat plan, step 6, decides the file's future.
- The mechanics pages name tables and rows but never say they are on the Game data page's
  **Find a table** box (`data.js:36`). Step 1.

**Confirmed bugs in or about the docs.** Severity after the skeptic's correction; "re-read" marks a
low claim checked in the code for this plan; the owner is this plan or the named one.

1. `studio/index.html:24` The one Help control is a fixed link to `docs/README.md` on GitHub, online
   only and the same on every page [low, lowered from medium: players install from main's ZIP, so
   the docs they have are main's]. Shell: the Help panel. Per-page help: each page's plan, through
   `pageHead` (step 7). This plan: the pages, and the test that every `help:` names one.
2. `docs/formats.md:401` `save.json` is a four-line example: nothing on what `set` and `add` do, the
   slot at the front of a path, where paths come from, the two skips (`savedit.py:43-44`, `:49-50`)
   or the backup [low, lowered from medium: the Save page covers the practical parts]. This plan,
   step 1.
3. `studio/sections/palettes.js:160` Until the game has started once after an install, the Coat,
   Pattern and Markings tabs show no colours; the banner's second half explains the log, and
   neither README.md:106 nor formats.md's palette section mentions it [low, lowered from medium;
   corrected: one start after an install is enough, no forest visit]. Banner, README row and
   formats.md:23-24: palettes-cat step 6 (it also makes the tabs work before the first play). This
   plan: the Palettes guide page says it (step 3).
4. `studio/sections/settings.js:136` lists six of the ten Make pages [low]. Shell (built from `/info`).
5. `README.md:107` and `README.md:354` The Your cat rows say nothing of the cat's shape and size or
   of other cats in the save [low, re-read: `cat.js:60`, `:147` Whose look, `:177` Shape; formats.md
   97-119]. This plan, step 1.
6. `docs/README.md:10-11` The list of what formats.md covers leaves out characters, questlines and
   mod packs [low, re-read: formats.md 252, 282, 309]. This plan, step 1.
7. `docs/ARCHITECTURE.md:65-78` The naming table has no row for the story section (`npcs`,
   `quests`, `npcs.json`, `quests.json`) or Mod packs [low, re-read: `sections/story.py:32`,
   `studio.py:45, 53-54`]. This plan, step 1 (rows) and step 2 (guide column).
8. `README.md:321` (the map said 322) The command list's `new --kind` leaves out `cpp`, which
   `cli.py:919` and README.md:364 accept [low, re-read]. This plan, step 1.
9. `studio/sections/controls.js:402` "Add --dry-run" on a page for people with no terminal [low].
   Controls plan (the card's command lines move to `docs/remapping.md`).
10. `studio/sections/save.js:28-30` "Editing cat slot 0" unexplained, and the checksum banner in
    engineering words [low]. Data-save step 8 rewrites the head ("Your cat: <name>"); the checksum
    sentence moves into this plan's `save.md` (step 5).
11. `docs/formats.md:399` (the map said 396) "The file starts with a `_help` line saying the same":
    `config.py:18-22` names 9 of the 16 keys the table lists (not `pack_before`, `debug_cat_look`,
    the three `menu_*`, `skip_menu_pages` or `cheats`) [low, re-read]. This plan, step 1 (the
    sentence changes; `HELP` doesn't, so `config.py`, which the shell branch rewrites, is untouched).
12. `README.md:365` (the map said 366) "ship cooked content (`paks/`)" with no caveat, while
    formats.md:9-13 says it hasn't been tried with this game [low, re-read]. This plan, step 1.
13. `studio/sections/npcs.js:70` and `docs/formats.md:280` say G (or the d-pad's up) talks to a
    studio cat; Sandbox mode 0.4 uses the game's Talk prompt on Interact (E, or A on a controller)
    whenever `Game.npcs.onInteract` exists, and G does nothing [medium; re-read: the hook is in
    v0.2.0's `game.lua` too (line 1778), so this holds for every released wcmods]. Story plan steps
    1, 3 and 9. This plan's pages say Interact.
14. `docs/formats.md:38-39` "The themed palettes in wcmods-examples add theirs in a range each": the
    committed examples add no slots; only Creator palettes' copies (same mod ids) do, so adding the
    examples' copy after them takes the new colours away [medium]. This plan, step 1 (the sentence);
    mods-setup step 8 (regenerate the examples).
15. `D:/projects/wcmods-emote-wheel/README.md:24` and the Creator palettes README send creators to
    Releases pages that are empty; formats.md:36 and :55 link those repositories [medium]. Mods-setup
    step 8 (the releases). Formats.md's links go to the repository pages, which is right once there
    is a release.
16. `studio/lib/story.js:128` "download sandbox.zip": the release offers sandbox-0.4.zip and two
    example zips [low]. Mods-setup step 3 (the banner gets an Add button).
17. `D:/projects/wcmods-sandbox/sandbox/scripts/story.lua:167` Sandbox mode 0.4 (the latest
    release) spawns studio cats without `look` and `slots`, so Fixed look does nothing, and the
    studio never checks the sandbox's version [high]. Story step 1 (release 0.5), mods-setup step 3
    (the version line). No guide page promises Fixed look without saying it needs Sandbox mode 0.5.
18. `wcmods/studio.py:391` Saving a cat or questline adds `sandbox` to the mod's `requires` for good;
    without the sandbox mod the whole mod, items included, is refused at Apply [medium]. Story step 2
    (a soft need through `uses`). No guide page documents the hard requirement as lasting.
19. `D:/projects/wcmods-emote-wheel/emote-wheel/settings.json:3` The Emote wheel's default key T is
    the game's map key in keyboard mode, and its README says the game doesn't use T [medium].
    Mods-setup step 8. This plan's Animations page names no key for the wheel.
20. `D:/projects/wcmods-examples/README.md:94` None of the 25 examples lists `game_builds`, so each is
    left out on build 26184573 the moment it's added [medium]. Mods-setup steps 5 and 8.
21. `wcmods/__init__.py:3` `__version__` is still 0.3.0 and no `mod.json` key can state the wcmods a
    mod needs [medium]. Mods-setup step 1.
22. `studio/app.js:51` "Close this window and open Clan Mod Studio again" after an update loops on
    the stale server [medium]. Shell (the Restart button).
23. `wcmods/pipeline.py:445` "install anyway with --force" shown in the studio [low]. Shell.
24. `studio/app.js:205` "Start it with: python wcmods.py studio" on the boot card [low]. Still there on
    the shell branch (its `app.js:434`), so this plan's step 2 rewords it, beside its other `app.js`
    change.

Found while re-reading for this plan (not seen by a skeptic):

25. `studio/sections/settings.js:127` Beside Take all mods out: "Control remaps and save edits stay in
    your save". Remaps are never written to the save (`wcmods/sections/controls.py`'s docstring: they
    run in the game through the remap script, which Take all mods out removes with the rest); what
    stays in the save is what an Apply wrote there (Your cat's slots, shape and scars, renamed cats,
    an item's "Starting with some", `save.json`) [low]. Mods-setup step 7 rewrites that line; the
    wording is in the hand-offs below.
26. `docs/guide/studio.md` (shell branch), What Undo means here: "After an apply: switch the mod off
    (or fix it) and apply again, and the game is back to how it was without it." Not for what an
    Apply wrote into the save (formats.md 105-131 for cats.json; `items.js:260` "put in the cat you
    play now, once, when you Apply"; names.json's cat renames; save.json): switching the mod off
    leaves those as they are [medium: the one page every creator reads promises an undo that doesn't
    happen]. This plan, step 2.
27. `studio/app.js` (shell branch, the help panel's click handler): a link to a heading on another
    guide page (`README.md#slot`) calls `openHelp(href.slice(6).split("#")[0])`, so the page opens at
    its top, not at the heading [low]. This plan, step 2 (or the shell branch, if it is still open);
    the glossary links rely on it.
28. The items-animations plan writes `help: "items"` for the Items page's head; `pageHead` treats a
    string without `help:` as a doc path and links `blob/main/items` on GitHub, a 404. It must be
    `help: "help:items"`. `test_guide.py` (step 2) fails on it.

**The high items in the three maps, and where they are.** Docs: the creator's entry path (UX, high)
is this plan. Shell: the wrong-shaped `palette.json` that blanked `GET /mods` (bug, high) and the
update loop (high in the map, medium after the skeptic) are fixed on the shell branch. Separate mods:
the Fixed look (bug 17, high) is the story and mods-setup plans'; "four core features live in mods
the studio never offers", "no version words anywhere" and "'left out' mods after adding
wcmods-examples" (UX, high) are mods-setup steps 1-3, 5 and 8.

## What a creator should be able to do

On any page, "How this works" (or Help in the top bar, then the page's name in the list) opens the
page's guide in the panel. A Make page's guide reads, under these six headings, in this order:

1. **What it changes in the game**: what you'll see, and where (the forest, the cat maker, menus,
   your save), in two to four sentences, then one line on how it gets there in plain words ("a small
   helper that runs with the game", "written into your save when you Apply, after a backup").
2. **A five-minute first try**: at most eight numbered steps, starting from the page, ending with
   Save to mod, Play, and where to look in the game.
3. **What you can and can't do**: two short lists. Every "can't" is one the game proves (a crash, a
   fixed table, an untried path), said in a sentence without engine words.
4. **Did it reach the game?**: where to look, and what it looks like when it didn't (the log's line,
   a message on the page).
5. **Common mistakes**: the three or four that happen, each with what to do.
6. **Undo**: before saving, after saving, after Apply; for a page that writes the save, what stays
   and how to put it back.

The other pages (the index, How the studio works, Mods, Mod packs, Settings and repair, Sharing,
When something doesn't work) are free in shape.

The five-minute first tries for the pages this plan writes:

- **Palettes**: open Palettes; on **Eyes** pick a slot and a colour; **Save to mod**; **Play**; open
  the cat maker and look at that eye button, or at any cat with that eye colour.
- **Your cat**: open Your cat; under **Colours** tick the coat and choose a colour; **Save to mod**;
  **Play**; your cat in the forest wears it (and only your cat).
- **Items**: open Items; add a herb that starts from Medium Healing Herb, name it Moon Herb, give it a
  recipe and 3 under **Starting with some**; **Save to mod**; **Play**; it's in your cat's inventory,
  and at the medicine cat's bartering.
- **Animations**: open Animations; **Save a start kit to animate** for the cat; in Blender move the
  tail and export a .glb; choose it on the page, make it an emote and set a **Key** like F7; **Save to
  mod**; **Play**; press F7, or open the mod menu (Insert) and its Emotes page.
- **Game data**: open Game data; type `TuningData` in **Find a table**; type `Run.Speed` in **Filter
  rows**; change 390 to 520; **Save to mod**; **Play**; run.
- **Save**: open Save; under **Inventory** press **Add item**, choose Small Catnip, 5; **Save to mod**;
  close the game if it's open and press **Play** (your save is backed up and the change written
  first); open the inventory.
- **Mod packs**: make two things on the Make pages; open Mod packs; name the pack, tick the mods;
  save it; **Play only this pack**; **Back to my mods** when done.

(Labels are checked against the pages by `test_guide.py`; a feature plan that renames one updates the
page in the same change.)

## The guide's rules

These go into `CONTRIBUTING.md` as a short "Writing the guide" part (step 2), and `test_guide.py`
holds every page to them:

- **One page per studio page**, named as the table above says, plus `README.md` (the index),
  `studio.md`, `sharing.md` and `trouble.md`. A new studio page brings its guide page.
- **Make pages have the six headings** above, as `##` headings, word for word, in that order.
- **Labels in bold, exactly as the page shows them** (`**Save to mod**`, `**Find a table**`). Bold is
  for studio labels only; the game's own words are in italics (*Sandbox Mode* on the main menu, the
  *Talk* prompt).
- **Words you'll meet**: the index has this list as `###` headings: Slot, Script loader, Mods that run
  code, Sandbox mode, Menu pages, Mod menu, The log, Game version. A page links a word to it the first
  time it uses it (`[slot](README.md#slot)`).
- **What the panel draws**: no tables (the renderer has none; write a list), lists one level deep, no
  HTML, headings no deeper than `###` below the title.
- **No command lines and no engine words**: no `python`, `wcmods.py` or `--flag`; "script loader",
  not UE4SS (the word appears once, in its glossary entry); no `.pak`; "Lua" only on `console.md` and
  `tweaks.md`. File names (`palette.json`) are fine where the studio shows them (toasts, the Editing
  mod bar).
- **Links**: another guide page as `page.md#heading`; a reference doc as `../formats.md#heading`
  (opens on GitHub, for the reader who wants the file format); never a code file.
- **Short**: a Make page under 150 lines; the first try at most eight steps.
- **No pictures in this pass**: the look and the feature plans change every page this month; pictures
  can follow once they settle (`docs/guide/images/` is served already).
- **Every fact from the code**: the PR description lists the source (`file:function`) for each
  "can't" and each "did it reach the game" line; the page itself doesn't cite code.

## The plan

Each step leaves the docs and the studio working. Tests go in `tests/unit` and use the tests
branch's fixtures where they need a studio. No step changes a file format, a route or a mod file
(`_help` lines included: they keep pointing at `formats.md`, which is right for the people who open
the file), so nothing needs migrating. Only the one check in step 3 needs the game.

### 1. The docs that contradict the code, and `tests/unit/test_docs.py`

Files: `README.md`, `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/formats.md`, `docs/updating.md`,
`docs/mechanics/README.md`, `tests/unit/test_docs.py` (new). Lands on its own, first; it needs
nothing from the other branches. (Palettes-cat edits the Your cat row again later, and data-save adds
to the `save.json` section; both build on these edits.)

The edits, with the wording:

- `README.md:107` (Your cat row): "colours only that cat wears (coat, paws, ears, nose, whiskers);
  which colour slots it wears; its shape and size; its scars: your cat, or any cat in your save" and
  "UE4SS script (colours); your save, on install (slots, shape, size, scars)". `README.md:354`:
  "colours only one cat wears, which slots it wears, its shape and size, its scars".
- `README.md:321`: `new <name> --kind palette|controls|files|data|items|names|save|script|cpp`.
- `README.md:365`: "ship cooked content (`paks/`, not yet tried with this game)".
- `docs/README.md:10-11`: "the JSON files a mod is made of (palettes, your cat, controls, mouse look,
  game data, items, animations, characters and questlines, names, save edits, mod packs)".
- `docs/ARCHITECTURE.md:65-78`: two rows, "Characters and questlines | `story` | `npcs`, `quests` |
  `npcs.json`, `quests.json`" and "Mod packs | (none: `packs.py`) | `packs` | `mod.json`'s `pack`".
- `docs/formats.md:38-39`: "The ten themed palettes that come with Creator palettes add theirs in a
  range each (100-124, 125-149...), so they can all be on together." (wcmods-examples' copies get
  their slots when mods-setup step 8 regenerates them; this sentence stays true either way.)
- `docs/formats.md:85`: after "(`colour_tables.json` and the eye atlas)", "; `python wcmods.py tables`
  writes `colour_tables.json` from the game's log after the game has started once with the script
  loader". (If palettes-cat step 6 lands first and ships the tables, take its wording.)
- `docs/formats.md:224`: "what the herb does (one of the game's herb effects, listed in
  [mechanics/items.md](mechanics/items.md))".
- `docs/formats.md:399`: "The file starts with a `_help` line pointing here."
- `docs/formats.md:401-405`: the `save.json` section moves above `wcmods.json` (the heading text and
  so its anchor stay), with this prose under the example: what `set` does (sets a value the save
  already has; a path it hasn't got is skipped with "your save has no value at ...; skipped"); what
  `add` does (adds keys to an object, such as items to the inventory; an `add` into something that
  isn't an object is skipped with "... isn't an object in your save; skipped"); a path starts inside
  the save's account object, and its first part is a cat slot (`0/GameplayProgression/Level` is slot
  0's level; `Shared/...` is for every slot), the slot of the game you're playing being
  `Shared/General/CurrentCatSlot`; the Save page's **Browse the whole save** shows every path; edits
  are written when you Apply, with the game closed, after a backup of the save; the save's checksum
  is kept as it is, which the game has accepted so far (`docs/verified.md`). Data-save step 6 then
  adds its "made once" rules to the same section.
- `docs/updating.md:29-39` (For mod makers): add "A mod made in Clan Mod Studio lists the build it was
  made on when it's created (`mods.create`); saving it again later doesn't add a newer build (the
  PUT file route in `studio.py` doesn't touch `game_builds`), so after an update add the new number
  to its `mod.json`." Mods-setup step 5 replaces this with its automatic re-check.
- `docs/mechanics/README.md:3-4`: one sentence: "Every table named on these pages is on Clan Mod
  Studio's Game data page: type its name in **Find a table**, then a row's name in **Filter rows**."
  (Data-save step 3's "By goal" list goes further down the same page.)

`tests/unit/test_docs.py`:

- `test_every_mod_file_has_a_formats_heading`: every `.json` in the built-in sections' `files`
  (`wcmods/sections/*.py`; the `files`, `scripts` and `cpp` sections hold folders, not JSON) has a
  `` ### `<name>.json` `` heading in formats.md, and every such heading is a section's file or
  `wcmods.json`. Passes today; a new section's file (console-lua's `tweaks.json`) fails it until it
  has a heading.
- `test_readme_page_table_names_the_studio_pages`: the bold first cells of README's Make pages table
  equal the titles of `BUILTIN_SECTIONS` in the make group, and each "Stored as" file has a formats
  heading. Passes today.
- `test_help_lines_in_saved_files_point_at_real_headings`: every `See docs/<file>, <heading>.` in a
  `_help` string under `studio/sections/*.js` names a file that exists and a heading that contains
  the text (formats.md cats.json, names.json, npcs.json, quests.json; SDK.md New items, Animations).
  Passes today.
- `test_doc_links_point_at_files_and_headings_that_exist`: every relative link in README.md and
  `docs/**/*.md` (not `docs/plans/`) names a file that exists and, with `#`, a heading with that slug
  (GitHub's rules, `guide.slug` once the shell lands); every `docLink("...")` in `studio/` too. A
  renamed heading fails naming the doc, the line and the anchor. Passes today (167 links).
- `test_new_kind_choices_have_templates_and_match_the_readme`: every `--kind` choice of `new` has a
  folder under `wcmods/templates/`, and every `--kind a|b|...` list in README.md names exactly the
  choices. Fails today at README.md:321; passes with the edit above. (Not "templates equal choices":
  console-lua adds `templates/tweaks/`, which isn't a kind.)
- `test_wcmods_json_keys_are_documented`: every key the code reads as `cfg.data.get("x")` or
  `cfg.data["x"]` has a row in formats.md's `wcmods.json` table. Passes today (12 keys); mods-setup's
  `skip_addons`, `skip_code`, `rechecked` and `taken_out` must bring their rows.
- `test_command_examples_name_real_commands_and_flags`: in code spans and fenced blocks of README.md
  and `docs/**/*.md`, every `python wcmods.py <command> ...` names a subcommand the parser has and
  only flags that subcommand takes. The parser is captured by patching
  `argparse.ArgumentParser.parse_args` to raise with `self` while `cli.main(root, [])` runs, so
  `cli.py` doesn't change. Examples with `<placeholders>` are checked for the command and flags only.
- `test_formats_examples_pass_their_checks`: each `json` block under a heading goes through the
  matching check: `palettes.load` (a temp file), `catcolours.validate`, `mouselook.validate`,
  `story.read` (the npcs and quests blocks together), `names.validate`,
  `sections.savedit.SaveSection().collect` (through a temp mod), and `controls.json` through
  `ControlsSection().collect`. The ones the probe ran pass today; `save.json` and `controls.json` are
  first run by this test. (`data.json`, `items.json` and `animations.json` need the game's tables to
  check; step 2 adds them once the shell's `Studio.check_file` and the `fake_game` fixture are in.)
- `test_page_text_has_no_command_lines`: no string literal (comments don't count: `mods.js:407`
  names a command in one) in `studio/sections/*.js`, `studio/lib/*.js` or `studio/app.js` contains
  `python wcmods.py` or a `--flag`, except a `KNOWN` list that may only shrink: `controls.js` (the
  "Using your remaps" card: the controls plan), `mods.js:163` (Menu pages' skipped step: mods-setup
  step 3), `app.js` (the boot card: step 2). The test fails on a new one, and on a `KNOWN` entry whose
  text is gone (so the list is kept honest).

Needs no game.

### 2. The guide's rules, its index and words, and `tests/unit/test_guide.py`

Files: `CONTRIBUTING.md` (Writing the guide), `docs/guide/README.md`, `docs/guide/studio.md`,
`docs/ARCHITECTURE.md` (the guide column), `README.md` (lines 3-5), `docs/README.md` (lines 9-11),
`studio/app.js` (bugs 24 and 27), `tests/studio/e2e/shell.test.mjs` (one case), `tests/unit/test_guide.py`
(new), `tests/unit/test_docs.py` (one test). After step 1, the shell branch (it adds `docs/guide/`,
`wcmods/guide.py`, the routes and the panel) and the tests branch (the `studio` and `fake_game`
fixtures). Small, so every feature plan that lands a guide page after it is held to the rules.

- `docs/guide/README.md`, under the shell's paragraph: the pages in two lists, "Your mods" (Mods, Mod
  packs, Settings and repair, Sharing what you make, When something doesn't work) and "Make mods"
  (the ten Make pages in the side bar's order, then Console), each one line, linking only pages that
  exist (the test keeps it in step with the folder); then "## Words you'll meet", one `###` heading
  and two or three sentences each:
  - **Slot**: the game keeps colours in numbered slots; every cat set to slot 3 wears whatever colour
    slot 3 holds, so changing a slot changes every cat with it.
  - **Script loader**: a free add-on (its name is UE4SS) that lets the studio's helpers run inside the
    game; Get set up, on the Mods page, installs it. Colours of coats and patterns, your cat's own
    colours, the mod menu and most add-ons need it.
  - **Mods that run code**: mods that run inside the game rather than only changing its files; they
    stay out until you allow them on Settings and repair, which you should do only for mods from
    people you trust. Menu pages, Sandbox mode, Creator palettes and the Emote wheel are such mods.
  - **Sandbox mode**: a mod that adds a Sandbox Mode button to the game's main menu: a cat with no
    story, where the cats and questlines you make appear.
  - **Menu pages**: the mod with the in-game mod menu's pages about your cat and the world. (Both
    entries gain a link to `mods.md#mods-that-go-with-clan-mod-studio` when mods-setup step 3 writes
    that page; a link to a page that isn't there yet would fail the link test.)
  - **Mod menu**: the menu Insert opens in the game (View on a controller); its Overview lists the mods
    that went in.
  - **The log**: what Apply and Play write as they work, in the panel at the bottom right; Last apply
    opens it again. Links to `studio.md#the-log`.
  - **Game version**: Steam updates the game now and then; a mod says which versions it was made for,
    and one made for an older version is left out until it's updated or you use it anyway.
- `docs/guide/studio.md`, What Undo means here: the "After an apply" bullet becomes two: "After an
  apply, for colours, names shown in the game, key changes, game data and anything else in the game's
  files: switch the mod off and apply again, and the game is back to how it was without it." and
  "What an apply wrote into your save stays when the mod is switched off: your cat's slots, shape and
  scars from Your cat, renamed cats from Names, items from Starting with some, and changes from Save.
  To undo those, put back a save backup made before that apply (Settings and repair); you lose what
  you played since." (Palettes-cat's Put my cat back and data-save's Put it back change the second
  bullet when they land.)
- `README.md:3-5`: "This page is for playing with mods. To make your own without code, open Clan Mod
  Studio and press Help (the same pages are in [docs/guide/](docs/guide/README.md)). To write mod
  files or code, start at [docs/README.md](docs/README.md); to work on wcmods itself, at
  [CONTRIBUTING.md](CONTRIBUTING.md)."
- `docs/README.md:9`: "**If you make mods:** without code, the [guide](guide/README.md), the pages
  behind Clan Mod Studio's Help. To write the files by hand or with code:" and the numbered list after
  it as it is.
- `docs/ARCHITECTURE.md`'s naming table gains "Guide page (`docs/guide/`)" as its last column, from the
  ownership table at the top of this plan.
- `CONTRIBUTING.md`: "Writing the guide", the rules above in ten lines, "a page's head names its
  guide page as `help: "help:<page>"`", and "a new page adds its line to the index".
- `studio/app.js`, the boot card (bug 24): "Clan Mod Studio isn't running (its black window was
  closed). Double-click Clan Mod Studio, then reload this page." in place of the command, and its
  entry leaves `KNOWN` in `test_docs.py`.
- `studio/app.js`, the panel's link handler: `openHelp(page, anchor)`; after the page renders it
  scrolls `[id=anchor]` into view and focuses it, so a glossary link lands on the word (bug 27). A case
  in `tests/studio/e2e/shell.test.mjs`: a `studio.md#the-log` link from the index opens How Clan Mod
  Studio works scrolled to The log. (If the shell branch is still open when this step starts, the
  change goes there instead.)
- `tests/unit/test_docs.py` gains `test_formats_examples_that_need_the_game_tables`: the `data.json`,
  `items.json` and `animations.json` blocks through `Studio.check_file` with the `fake_game` fixture;
  a block whose check needs a table the fixture hasn't got is skipped naming it.

`tests/unit/test_guide.py` (every test runs over the pages that exist, so it passes on the shell's two
pages and grows with them):

- `test_guide_pages_use_only_what_the_panel_draws`: no line starting with `|`, no indented list item
  under a list item, no `<tag>`, no heading deeper than `###` below the `#` title, exactly one `#`.
- `test_make_pages_have_the_six_parts_in_order`: for the guide page of every make-group section
  (`BUILTIN_SECTIONS` and `CODE_SECTIONS`, page names from ARCHITECTURE.md's new column), the `##`
  headings are the six, in order, if the page exists.
- `test_make_pages_are_short`: under 150 lines; at most eight numbered steps under A five-minute
  first try.
- `test_bold_labels_are_on_the_studio_pages`: every `**label**` in a guide page occurs in a file under
  `studio/` (sections, lib, `app.js`, `index.html`); a trailing "…" is ignored. A plan that renames a
  button fails here until the page follows. (The shell's two pages pass: all eleven of their bold
  labels were found under `studio/` on the shell branch.)
- `test_guide_links_resolve`: `page.md` and `page.md#x` name a guide page and a heading whose
  `guide.slug` is `x`; `../x.md#y` and `../../README.md#y` name a repository doc and heading; no link
  to a `.py`, `.js` or `.lua` file.
- `test_no_command_lines_or_engine_words`: no `python`, `wcmods.py`, ` --x`, `.pak`; `UE4SS` only in
  README.md's Script loader entry; `Lua` only in `console.md` and `tweaks.md`.
- `test_words_youll_meet`: README.md has the eight `###` words under Words you'll meet, and every
  link to `README.md#x` from another page names one of them.
- `test_the_index_lists_every_page`: README.md links every `docs/guide/*.md`, and nothing that isn't
  there.
- `test_every_page_help_opens_a_guide_page`: each `help: "help:<page>"` and `openHelp("<page>")` in
  `studio/**/*.js` names an existing guide page; a `help:` string without the prefix that doesn't end
  in `.md` (or `.md#...`) fails (the items-animations `help: "items"` case). A `NOT_WIRED` set lists the
  section ids whose head doesn't name its page yet (today all of them); the test fails when a listed
  page gains its help (take it off the list) or an unlisted one lacks it, so the list only shrinks.
- `test_help_route_serves_every_guide_page`: with the `studio` fixture, `GET help/<page>` for each page
  answers its title and HTML with no `|` table text left in it; `GET help/index` answers README.
- `test_architecture_names_the_guide_pages`: the new column agrees with the files that exist (a named
  page may be missing until its plan lands; an existing page must be named).

Needs no game.

### 3. Palettes and Your cat

Files: `docs/guide/palettes.md`, `docs/guide/cat.md`. The palettes-cat plan extends both.

`palettes.md`, from `palettes.js`, `wcmods/palettes.py`, `wcmods/sections/palettes.py`, formats.md
16-80 and reverse-engineering.md Colours:
- What it changes: every cat's eye colours (the cat maker's eye buttons follow), and the coat, pattern
  and marking colours of the game's 25 slots of each; every cat with a slot changes. New pattern and
  marking colours (from slot 25) change no cat until one is set to them. Appearance only: traits and
  stats stay.
- First try: as above; and the quicker one, **Quick palettes**: tick a themed palette you added from
  wcmods-examples and apply it.
- Can: recolour the 25 eye slots (their names don't match their colours: *Yellow* is green); recolour
  coat, pattern and marking slots 0-24 (0-14 natural, 15-24 bright); **One colour** or **Gradient** for
  eyes; add pattern and marking colours, which keep their numbers. Can't: new coat colours as slots
  (the game crashes on a coat slot past 24; Your cat gives one cat any coat colour); more than 25 eye
  colours (the game's eye colours are a fixed grid of 25); two themes at once (only one shows;
  **Quick palettes** switches between them); choosing a new colour in the game's cat maker without
  the Creator palettes add-on.
- Did it reach the game: eyes show in the cat maker and on any cat with that eye; coat, pattern and
  marking colours need the [script loader](README.md#script-loader) and appear a moment after the
  game starts. If the page says "Coat colours not loaded yet", press **Play** once (the game needs to
  start once after an install; the forest isn't needed), close it and come back. The log names the
  palette among the mods that went in.
- Mistakes: not pressing Save to mod before Play; expecting a slot's name to be its colour; slots
  20-24 of the coat are the Feral Edition's and look different without it; a new colour nobody wears
  shows nothing (set one cat to it on Your cat).
- Undo: **Reset tab** or **Game colours** before saving; after Apply, switch the mod off on the Mods
  page and Play: the colours come back (nothing of a palette is in the save). A cat set to a new slot
  keeps that number in the save, and with no palette adding it, that colour shows as none; pick a
  game slot on Your cat.

`cat.md`, from `cat.js`, `wcmods/catcolours.py`, `wcmods/sections/cats.py`, formats.md 89-131:
- What it changes: one cat's look, your cat or any cat in your save (**Whose look**): colours only that
  cat wears (coat, paws, ears, nose, whiskers) while you play, which slots it wears, its **Shape** and
  **Size**, its **Scars**. Colours go on through the script loader while you play; slots, shape, size
  and scars are written into your save when you Apply, after a backup.
- First try: as above.
- Can: any colour on paws, ears, nose and whiskers (they have no slots); slots, including new ones a
  palette adds; body, fur, tail, ears, eyes, whiskers and face from the game's ten of each (the cat
  maker shows a clan's seven), pattern and marking from its 21; size from a kit's to a leader's; scars
  on the ears, an eye, the back and the chest, or none. Can't: change traits (they were chosen by
  body, ears and face when the cat was made, and stay); keep a size through a rank-up (the game sets
  it again); colour another cat outside the game you're playing.
- Did it reach the game: colours on your cat in the forest, menus and portraits; slots, shape and scars
  after Apply, in the forest. Scars show only with the game's own *Injury* switch on (its Gameplay
  settings).
- Mistakes: no save yet (start the game once); a rank-up renames another cat (Gustpaw to Gust-), so its
  colours stop until you pick it again and Apply; two cats with one name both change.
- Undo: colours: switch the mod off and Play. Slots, shape, size and scars stay in your save when the
  mod is off: **Keep the save's scars** before saving leaves them alone; after Apply, put back a save
  backup made before it (Settings and repair). Palettes-cat's Put my cat back replaces this line.

Needs the game once, for the "press Play once" sentence (read from the code, not tried: `palettes.lua`
logs the tables from a two-second loop that needs only the game's GUI manager, `palettes.lua:79-88`,
and every build ships it, `sections/palettes.py:41-42`). On the dev machine, from a worktree's studio,
after checking that no other session launched the running game (the game is shared between
sessions): Apply, start the game to its main menu with `python wcmods.py agent launch` without
entering a cat, close it, and open Palettes: the Coat tab shows the game's 25 colours and
`GET /api/game/tables` answers from the log. If palettes-cat step 6 lands first, its
"works before the first play" replaces the sentence and the check is that plan's.

### 4. Items and Animations

Files: `docs/guide/items.md`, `docs/guide/animations.md`. The items-animations plan extends both and
wires their heads (`help: "help:items"`, `help: "help:animations"`).

`items.md`, from `items.js`, `wcmods/sections/items.py`, formats.md 217-237, SDK.md New items,
mechanics/items.md:
- What it changes: new herbs, materials and accessories of the mod's own, in the inventory with their
  name, description and icon; a herb does one of the game's herb effects; the medicine cat can make one
  from a recipe; a cat can start with some; an accessory wears a recoloured look, a picture of your
  own, or a model of your own from Blender.
- First try: as above.
- Can: the game's herb effects (the list in [the items mechanics](../mechanics/items.md)), a recipe at
  the medicine cat's bartering, an icon from the game's (recoloured) or a picture of your own, a
  recoloured or painted accessory look, a model made on the start kit (**Save a start kit to model
  on**), **Opacity** as one-colour glass. Can't: new effect strengths (each effect is built into the
  game; "+75 health" would need a new one); a head accessory's look; an item put in the inventory at
  any moment (they arrive through **Starting with some** on Apply, a recipe, or a questline's reward
  on the ground); a see-through picture (a picture is solid; only **Opacity** makes glass).
- Did it reach the game: the inventory, the medicine cat's bartering, the accessory on your cat.
- Mistakes: expecting **Starting with some** to give more every Apply (it's once); a picture that
  isn't PNG, JPEG or WebP; a model not made on the start kit sits in the wrong place (use
  **Shape and place**).
- Undo: switch the mod off and Play: the items leave the game. Ones your cat already carries are in
  your save; what the game shows for an item whose mod is off hasn't been tried in game, so the page
  says to put back a save backup made before the Apply to be sure.

`animations.md`, from `animations.js`, `wcmods/animations.py`, SDK.md Animations:
- What it changes: animations of the mod's own for your cat (emotes) and for animals, made in Blender
  on a start kit rigged to the game's own skeleton; an emote plays from a key or the mod menu's Emotes
  page; **Replaces one of the game's** swaps one of the game's own animations.
- First try: as above.
- Can: emotes on a key or the Emotes page, **Loop**, **Speed**, **Blend**, claws out while it plays,
  animals' animations for scripts. Can't (SDK.md, "What it can't do (yet)"): make a cat or an animal
  swim, fly or move a new way (the animation plays, the body doesn't travel with it); play on part of
  the body; play on the named cats with models of their own (Brightheart, Tallstar); replace one of the
  game's animations for one cat only; keys the game already uses (pick F5 to F8, as the page says). The
  Emote wheel add-on also shows your emotes; its own key is on its settings page.
- Did it reach the game: press the key in the forest, or the mod menu's Emotes page (Insert).
- Mistakes: a file exported from another rig; a key the game uses; expecting it on other cats (scripts
  only).
- Undo: switch the mod off and Play; nothing is in the save.

Needs no game (each line is in the page's own text or the SDK's).

### 5. Game data and Save

Files: `docs/guide/data.md`, `docs/guide/save.md`, `docs/mechanics/exploration.md` (the Moving
table's Walk and Run rows gain their keys, `Gameplay.Exploration.Player.MoveAndRun.Walk.Speed` and
`Gameplay.Exploration.Player.MoveAndRun.Run.Speed`, as wcmods-examples' `faster-run/section.py:8-9`
uses them), `tests/unit/test_guide.py` (one test). Data-save steps 3, 4 and 6-8 extend both pages
(Quick changes, plain words per row, made-once save edits, Put it back) and wire their heads; its
step 3 finds the two keys already there.

Test: `test_data_page_names_rows_the_mechanics_docs_know`: every backticked table or row in `data.md`
occurs in `docs/mechanics/*.md` (with `<n>`, `<Rank>` and `<Clan>` as written there), so the guide
and data-save's "By goal" list can't drift apart.

`data.md`, from `data.js`, `wcmods/sections/data.py`, formats.md 209-216, README.md 377-387,
docs/mechanics/:
- What it changes: the numbers the game plays by, from its own tables: XP, costs, rewards, speeds,
  how many cats each clan has and how they look, and about 440 tuning values. A gameplay change by
  purpose.
- First try: as above (running speed).
- "Where to find it", one line each, with the table and row as the mechanics pages name them: XP for
  each level (`TuningData.csv`, `Gameplay.Exploration.Level.<n>`); XP from fights
  (`CombatBaseExperience.csv`, `BaseExperience`); running and walking speed (`TuningData.csv`,
  `Gameplay.Exploration.Player.MoveAndRun.Run.Speed`, the game's 390, and the same with `Walk`); inventory
  space by rank (`Gameplay.Inventory.Capacity.<Rank>`); what a herb costs at the medicine cat
  (`BarteringCost.csv`); how many cats of each role a clan has (`<Clan>NpcGenerator.csv`); clan cats'
  sizes (`CatSize.csv`) and scar chances (`Scars.csv`); the fresh-kill pile going down (`Decay.Value`,
  `Decay.Time`). **Multiply every** with **Apply to all rows** for "double all XP".
- Can and can't: any number in any table the game reads while it runs; rows added and removed. Can't:
  change cats already in your save through the clan tables (they're for cats the game makes from then
  on); be sure every tuning value is read by the game (about half aren't confirmed); change the online
  gifts and visits tables or the body, ear and face odds without a warning (they're online rewards,
  and the odds choose new cats' traits).
- Did it reach the game: play and see; the log names the mod among those that went in.
- Mistakes: a table you can't find (type part of its name); a change to a value the game doesn't read
  (nothing happens; the mechanics pages say which are confirmed); a clan table changed and expecting
  the cats you know to change.
- Undo: **Remove** on a row before saving; after Apply, switch the mod off and Play (nothing is in the
  save).

`save.md`, from `save.js`, `wcmods/sections/savedit.py`, formats.md's new save.json prose,
docs/verified.md:
- What it changes: your save itself: level, XP, health, the fresh-kill pile, the inventory, settings,
  and anything else in it (**Browse the whole save**), written when you Apply, with the game closed,
  after a backup.
- First try: as above.
- Can: values your save already has; items into the inventory. Can't: values the game works out again
  (combat stats when you level up: the page says which); your keys (the game ignores bindings edited
  in the save: use Controls); your cat's look (use Your cat). Is it safe: edited saves load and the
  game keeps the edits when it saves again (verified.md); the save's checksum is kept as it was, which
  the game has accepted so far; the studio backs up the save before every edit.
- Did it reach the game: the level and inventory in the game; with Menu pages, the mod menu's Stats.
- Mistakes: the game open (Apply and Play wait until it's closed); expecting another cat's game to
  change (the page edits the game you're playing); looking for XP rates here (they're on Game data).
- Undo: before Apply, change the value back; after, a save backup (Settings and repair).

Needs no game: the Save facts are in verified.md and the code.

### 6. Mod packs, Sharing, and When something doesn't work

Files: `docs/guide/packs.md`, `docs/guide/sharing.md`, `docs/guide/trouble.md`, the index's lines
for every page of steps 3-6 (`docs/guide/README.md`), and one line at the end of `studio.md`'s The
log: "When something didn't arrive, see [When something doesn't work](trouble.md)." Mods-setup step 6
extends `packs.md` (tools stay on; a removed pack); the shell's chips are the source for
`trouble.md`.

- `packs.md`, from `packs.js`, `wcmods/packs.py`, formats.md 309-318: what a pack is (mods shared and
  played together as one experience); making one (**Mods in it**, the needed mods go in with them);
  **Play only this pack** turns its mods on and every other mod off but Menu pages, and **Back to my
  mods** puts yours back; today the Creator palettes and Emote wheel add-ons go off too, and a cat
  wearing a coat preset shows its saved coat until Back to my mods (mods-setup step 6 keeps them on);
  **Save as .zip** carries every mod in it; a pack someone sent is added on the Mods page.
- `sharing.md`, from `wc.js` (the Share part of every Make page), `modzip.py`, updating.md: the Share
  part's name, author, version and description; **Save as .zip**; what the friend does (drop it on
  their Mods page, which shows what's in it before adding); a mod that runs code needs them to allow
  such mods; characters and questlines need Sandbox mode on their side; after a game update, a mod is
  marked with the version it was made on, and what to do (updating.md's wording, then mods-setup step
  5's); Export and Import move one page's file.
- `trouble.md`, by what the creator sees: nothing changed in the game (was it saved, applied, is the
  mod on, is the script loader in: the top bar's chips, from the shell's `app.js`); a mod is left out
  (made for an older game version; needs another mod; runs code and isn't allowed: each with its
  button, linking `mods.md`); Apply says some mods can't be made ready (the log, Apply the rest
  anyway); "Your mods go into another copy of the game" (**Use Steam's copy**); the game crashed or a
  save looks wrong (Settings and repair: **Put it back**, a save backup, **Take all mods out of the
  game**); the studio says something went wrong (`studio.log` for whoever helps).

Needs no game.

### 7. Help in every page's head (hand-off, with the test)

No files of its own. Each page's plan puts `help: "help:<page>"` in that page's `pageHead` and takes
the page off `NOT_WIRED` in `test_guide.py` in the same change: mods, packs, settings (mods-setup),
palettes and cat (palettes-cat), controls (controls), names (names), items and animations
(items-animations, with the `help:` prefix), npcs and quests (story, naming `characters` and
`questlines`), data and save (data-save), console and tweaks (console-lua). The story plan's sandbox
banner links `characters.md#getting-sandbox-mode` through `wc.openHelp`. Until a page is wired, its
guide is one click away in the Help panel's index.

### 8. The README's command line moves to `docs/cli.md`

Files: `README.md` (Command line, 289-345), `docs/cli.md` (new), `docs/README.md` (a row). After
step 1.

The section moves to `docs/cli.md` as it is (its fenced examples stay under step 1's command test).
README keeps the heading, so `#command-line` still resolves, with two sentences: "Everything the
studio does is also a command: `python wcmods.py --help` lists them, and
[docs/cli.md](docs/cli.md) explains each." `docs/README.md`'s table gains "cli.md | Every command,
with examples | players who like a terminal, mod makers". Remapping keys is the controls plan's
(its step 10 shortens it and starts `docs/remapping.md`); Requirements stays, since mods-setup step 2
adds the add-ons to it.

Needs no game.

## Hand-offs to other work

- **Shell branch**, if it is still open when step 2 starts: take the `studio.md` Undo bullets (bug 26)
  and the panel's anchor fix with its test (bug 27) there, as step 2 words them; otherwise step 2
  makes both.
- **Mods-setup step 7**: `settings.js:127` becomes "Your mods stay here, and everything they put in the
  game comes out. What an apply wrote into your save stays (your cat's slots, shape and scars, renamed
  cats, starting items, Save page changes): put back a save backup to undo those." (bug 25).
- **Mods-setup step 3**: `mods.md` in the guide's rules, with a `## Mods that go with Clan Mod Studio`
  heading and a sentence per add-on, as the Add-ons card says them, and the glossary's Sandbox mode
  and Menu pages entries gain their link to it.
- **Controls step 10**: `controls.md`'s table is written as a list (the panel draws no tables, and
  `test_guide.py` fails on a `|` line).
- **Story steps 3, 4 and 9**: `characters.md` and `questlines.md` in the six parts; Interact (E, or A)
  to talk; a `### Getting Sandbox mode` under A five-minute first try (the six `##` headings stay
  six) for the banner's link; no lasting hard requirement once story step 2 has landed; Fixed look
  says it needs Sandbox mode 0.5.
- **Items-animations**: `help: "help:items"` (bug 28); `animations.md` names no key for the Emote wheel.
- **Data-save step 3**: its "By goal" list in `docs/mechanics/README.md` and `data.md`'s "Where to find
  it" name the same rows; `test_guide.py` gains `test_data_page_names_rows_the_mechanics_docs_know`
  (each backticked table or row in `data.md` occurs in `docs/mechanics/*.md`) in this plan's step 5.
- **Palettes-cat step 6**: when its tables-before-the-first-play lands, the "press Play once" sentence
  in `palettes.md` goes with it.

## Not in this plan

Codeless ideas the maps rate needs-re or known-impossible, which the guide's "can't" lines describe
without promising: new coat colour slots (known-impossible: a coat slot past 24 has no paw, ear, nose
or whisker entry in the native map at manager+0x800 and crashes the game; coat presets are the way);
more than 25 eye colours (known-impossible: a fixed 64×26 atlas); new herb effect strengths
(needs-re: each effect tag runs a Blueprint container); lines for the game's own clan cats (needs-re:
dialogue graphs; the re-roadmap plan); fight or hunt questline steps (needs-re: ending a fight cleanly);
accessories on a mod's own cats (needs-re); choosing traits (needs-re: their storage in the save);
new sounds or music (needs-re: cooked paks untried); applying while the game runs (needs-re: script
hot reload untried, paks can't be swapped); a starting rank for sandbox cats (needs-re: ForcedRank);
more step kinds (needs-re); sandbox cats with Steam Cloud (needs-re: a per-slot mark in the save);
the mouse in Creator palettes' picker (needs-re); head accessory looks and more accessory variations
(needs-re); items given without a pickup (needs-re).

Known-possible ideas from the docs map that are other plans' work: in-studio help (shell, done); a
drawn preview of Your cat (palettes-cat); clan sizes and scar chances as plain rows (data-save
Quick changes); Save presets such as "level 10" or "5 of every herb" (data-save step 8); herb effects
in words (items-animations); any text the game shows on Names (names plan); a cat from another save
slot as a Character, and quest places by name (not planned anywhere yet; the story plan rates more
named places needs-re).

## Open questions

1. Should Mod packs, Settings and repair and the Mods page also take the six headings, or stay free in
   shape as proposed?
2. Pictures: after the look and the feature plans settle, one or two per Make page in
   `docs/guide/images/` (the shell serves them)? They'd need refreshing whenever a page changes.
3. Step 8: is the owner happy for README's command list to move to `docs/cli.md`, leaving two
   sentences?
4. The glossary sits on the index (`README.md#slot`) so one link target serves every page; would the
   owner rather have it on `studio.md`, which the index calls "Start here"?
5. `test_bold_labels_are_on_the_studio_pages` checks a label occurs anywhere under `studio/`, not on
   that page's own module; enough, or should it look only in the page's section file and `wc.js`?

## Review notes (what changed from the reviewed draft)

- The draft's on-disk copy (`docs/plans/docs-guide.md`) holds only a summary; this is the full text,
  rebuilt from the maps, the verdicts, the code on `3af2898` and the three branches as read on
  2026-10-28.
- Bugs: line numbers corrected (formats.md:399, README.md:321, :365, mods.js:163, settings.js:127, not
  :108); bugs the shell branch already fixes, and those other plans own (talk key, palettes banner,
  `controls.js` dry-run, `save.js` cat slot, `story.js` file name, the companion releases), are marked
  with their owner instead of being edited here again; the boot card's command is still on the shell
  branch, so step 2 rewords it; three new ones (Undo in `studio.md`, the panel's dropped anchor,
  `help: "items"`); the draft's own remaps line is confirmed (no remap is ever written to the save)
  and handed to mods-setup step 7, which rewrites that line.
- The draft's "docs/guide/ exists in no worktree" is out of date: the shell branch has `README.md` and
  `studio.md`.
- Dropped as duplicates: the companion-repositories PR (mods-setup steps 1 and 8, story step 1); the
  `companion-mods.md` page (mods-setup's Add-ons card and its `mods.md`); writing `controls.md`,
  `names.md`, `characters.md`, `questlines.md`, `console.md`, `mods.md`, `settings.md` (their plans
  write them); moving Remapping keys (controls step 10) and Requirements (mods-setup step 2 edits it);
  edits to `npcs.js`, `palettes.js`, `controls.js`, `save.js`, `story.js`, `settings.js` and
  `config.py`.
- Corrected facts: the characters page no longer warns that one saved cat makes the whole mod need
  Sandbox mode (story step 2 removes that); a later Save to mod does not record a new game build (the
  PUT route never touches `game_builds`); talking is Interact with every released wcmods, not only
  0.3.0.
- Open questions answered: page names (each page names its own in `pageHead`; ARCHITECTURE.md records
  them); one Help mechanism (the shell's panel through `help:`); `_help` lines stay; where "When things
  go wrong" lives (`trouble.md`); the companion releases (mods-setup step 8).
- Added: the label, link-anchor, `help:`-prefix and short-page tests; the `KNOWN`/`NOT_WIRED` lists
  that only shrink, so tests can land before the pages they guard; the formats examples that need the
  game's tables moved to step 2, so step 1 depends on nothing; the `new --kind` test no longer equates
  choices with template folders (console-lua's `templates/tweaks/` would break it); the CLI example
  test captures the parser without changing `cli.py`; guide links to pages that don't exist yet
  (`mods.md`, `trouble.md`) are added by the step that writes the page.
- Split into four PRs: the contradictions (no dependencies), the guide's rules (after the shell and
  tests branches), the pages, and the command line move.
