# Things: the Items and Animations pages

Written to `D:/projects/warrior-cats-mods/.claude/worktrees/clan-mod-studio-overhaul-27fa18/docs/plans/items-animations.md`. This plan covers the two "make a thing" pages of Clan Mod Studio. It comes from the 2026-10 audit (`items.json` and `animations.json`), the skeptics' verdicts, the code on `main` at 3af2898, and the other plans in `docs/plans/` that touch the same code:

- `controls.md`: the key dialog and the keys already in use.
- `story.md`: `listEditor`.
- `docs-guide.md`: the guide pages.
- `mods-setup.md`: the Emote wheel note on the Animations page.

The shell, the look and the test harness have their own branches. This plan refers to them where it needs them.

## What it is for

A creator with no code, and usually no Blender, wants to put something of their own into the game: a herb that heals, a material for a questline, a collar in a new colour, a cat that yawns at a key press, a trot that looks different. For each of those they should be able to:

- make it in a few minutes on one page;
- see on that page whether it went into the game;
- never be stopped by a message they can't act on.

## Where it stands

**What works, and how we know.**

- **Items.** A new herb or material shows in the inventory with its name, description and icon. Its recipe shows at the medicine cat's, and trading works. Icons from a PNG load, and so do recoloured ones. A new collar look is worn and can be made at bartering (docs/verified.md, 2026-10-24).
- **Accessory models.** OBJ and GLB models, `place`, `opacity` and `glass` showed on the cat in three places: the inventory's picture, the forest and the main menu's cat. Models on the ground lay where `Game.items.drop` left them and were collected as usual (verified.md, 2026-10-27).
- **Animations.** Animations made in Blender from the start kit played as emotes from the mod menu and from F6 and F7. That included claws out, 1.5 times the speed, and animations on mice and birds. The cats' trot was replaced by the sleep loop through the kit's own `.glb` and `"clip"` (verified.md, 2026-10-27).
- **Python tests.** The parts that don't need the game are well tested: `tests/unit/test_models.py`, `tests/unit/test_animations.py` and `tests/unit/test_acl.py`. 176 unit tests pass on `main`.
- **Selftest.** `wcmods selftest` covers the parts that need the game's files: `_items_section`, `_textures`, `_accessory_looks` and `_animations`.
- **No page tests on `main`.** The studio's JavaScript has no tests, and neither do the routes behind these pages. The tests branch (PR #75) adds route tests for pictures and models on the ground. `add_animation`, `animation_info` and `anim_sequences` stay untested, because they read the game's skeletons.

**What is half finished.**

- **Items:**
  - A recipe can't ask for a material that the same mod adds (`items.js:574-578`), although `Game.cost` accepts one (`items.py:536-553`).
  - The game's own recipes (`"recipes"`) have no page.
  - `rarity`, `color`, `target`, `combat`, `exploring` and `fight_only` are checked in Python but have no controls.
  - Only look 1 of each accessory can be a base on the page (`items.js:51`), though `items.json` takes any look (`items.py:385-397`).
  - The items template's `_help` was written before accessories and models existed.
- **Animations:**
  - `check` accepts controller buttons for emotes, but the page can't pick one.
  - The build's notes (`animations`, `emotes`, `replaced`) never reach the studio.
  - The route that needs no Blender exists in the backend: the kit's own clips, or any game sequence by its path through `Game.anims.play`. Neither the page nor the docs mention it.

**Confirmed bugs.** A skeptic checked each one. Refuted claims are left out, and the skeptics' corrections are noted.

1. [medium] `studio/sections/items.js:114`: an item saved with a blank Name or Description saves without complaint, then blocks Apply for every mod. The message names `items.json`, the item number and `--force`. The skeptic lowered this from high, because nothing is lost and the item is named. The real defects:
   - the page never checks the two fields;
   - nothing marks them as needed;
   - the Description placeholder reads like real content;
   - one bad item blocks the whole install.
2. [medium] `studio/sections/items.js:279`: the first picture or model uploaded into a mod with no folder yet lands on a stale item object, because `modReady()` saves and reloads the page. The editor shows the icon, but the file and `getValue()` don't have it, and later typing in that editor is lost too. The skeptic's corrections: the editor stays attached and shows the stale object, and all five pickers do this. `animations.js:172-182` already has the fix.
3. [medium] `studio/sections/items.js:151`: the Name box's `onchange` redraws the whole editor, so focus falls to the top of the page. A click from Name into Description doesn't land (reproduced in Chromium).
4. [medium] `studio/sections/items.js:349`: with Look set to "as it is", moving Opacity back to 100% leaves an accessory with nothing of its own. The build drops it with one warning. "Put it back where it was made" (556) and moving the place sliders back to neutral (517) do the same.
5. [medium] `studio/sections/items.js:158`: changing Kind drops `like`, the effect, recipe, look, model, place, opacity, glass and icon, with no confirmation and no way back.
6. [medium] `studio/app.js:176` (the skeptic moved it from `items.py:200`): a problem with one item at build time is one `warning:` line in the drawer, under a toast that says "done". The Items page shows nothing. Naming a herb "Medium Healing Herb" is enough to cause it.
7. [high] `wcmods/lua/models.lua:66`: `GetMaterial(0)` is called on slots with no `SkinnedAsset`. PR #72 handles it; it is not part of this plan.
8. [medium] `wcmods/lua/models.lua:174`: `retake()` writes the cat choice's big cat into save slot 0's picture (PR #72). The worry about the main menu's cat was refuted.
9. [medium] `studio/sections/animations.js:96`: a cleared Name saves. If the animation has a file, `collect()` raises and the whole mod's animations leave the game. An animation with no file is skipped on its own instead. Lowered from high.
10. [medium; one of the two skeptic passes said high] `wcmods/studio.py:806-809`: `add_animation` writes `animations/<id>.<ext>` without checking what is already there.
    - While an animation is unsaved, its id follows its name, but its file keeps the old name.
    - So "Add, choose a file, rename, Add, choose a file" overwrites the first `.glb`.
    - Ids that differ only in case share one file on NTFS.
11. [medium] `studio/sections/animations.js:224`: "Press a key…" adds a capture listener to the whole window, and only the next keydown removes it. That keystroke is swallowed anywhere, even on another page, because pages are hidden, not unmounted. Listeners stack, and there is no cancel.
12. [medium] `wcmods/animations.py:486`: `describe()` never compares a clip with `MAX_SECONDS`. A 70 s clip is accepted and saved, then dropped at build with a warning the page never sees.
13. [low] `wcmods/studio.py:801`: a "glTF Separate" `.gltf` is refused with "keep X.bin beside it", which the page can't do. Lowered because the first half of the message, export as `.glb`, can be followed.
14. [low] `studio/sections/animations.js:221`: the emote checkbox and the buttons have no `aria-label`, and the editor pane has no `data-key`, so keyboard focus drops to the top after each.
15. [likely; found while reviewing this plan, not checked by a skeptic] `studio/sections/items.js:148` with `wcmods/studio.py:755` and `:777`: the overwrite in bug 10 also happens on Items.
    - While an item is `_new`, its id follows its name.
    - Its pictures and models are named after that id (`${it.id}-icon`, `-look`, `-ground`, and `it.id` for a model).
    - `add_picture` and `add_model` write over any file already there.
    - Repro, in a mod that already exists: Add, choose an icon, rename, Add, choose an icon. The first item now shows the second item's picture.

**Unchecked lows, treated as likely:**

- **Items:**
  - `items.js:219`: `icon` set to `""`.
  - `items.js:190`: no preview for a picture outside `pictures/`.
  - `items.py:165`: a herb and a material with the same id share an icon texture name.
  - `items.py:504`: a `.jpg` icon gets a misleading message.
  - `items.js:264`: removed items leave their files behind.
  - `studio.py:874`: `model-view` isn't cached.
  - `items.js:10`: `rarity` is in `EDITED` with no control.
  - `items.js:161`: a Kind change starts from `pool[0]`.
- **Animations:**
  - `animations.js:105`: changing For drops the file.
  - `animations.js:245`: the "kept as it is" note is wrong for unknown keys. The claim's second half, that `_` keys are dropped, doesn't hold: `toJson` drops only `_new` and `_info`.
  - `animations.py:452`: a sequence with one key gives a ZeroDivisionError.
  - `animations.js:240`: the menu key is hard-coded as Insert.
  - `sections/animations.py:121`: two emotes on one key.
  - `animations.js:168`: two uploads can race.
  - `game.lua:1495`: the Emote wheel and the emotes script keep separate playing states.
  - `emotes.lua:47`: no nil guard.
  - `sections/animations.py:101`: two sequences with the same short name.
  - `studio.py:841`: one unreadable asset turns the route into a 500.

**Refuted, not a bug.** The Replaces scan is memoised, takes about 3 s, and blocks nothing. All it lacks is a "reading…" line.

## What a creator should be able to do

### Items

The cards, top to bottom:

1. **"What it is":**
   - icon preview;
   - Name and Description, both marked as needed, with "For example:" placeholders;
   - Kind;
   - "Starts from", with a read-only line under it such as "Used anywhere, for you" or "Used in fights only, for your whole team";
   - a folded "Technical name".
   For an accessory, "A new look of" lists every look by its own name (Dog Collar, Red Dog Collar), not only the first.
2. **"Icon"**, with the paint-over steps as three numbered lines.
3. **"Using it"** (for a herb). Plain words come first, with the herb in brackets: "Heals 50 health (Medium Healing Herb)", "Whole team +50% Strength for the fight (Thistle Pouch)", "Cures Poisoned (Antidote Herb Pouch)". Each badge is explained in words.
4. **"The medicine cat's recipe"**, with "Your materials" listed under the game's.
5. **"Starting with some"**, with a note that it is given once and needs a save.
6. **"Look"** (for an accessory): a colour, a picture of your own, or the look as it is; and Opacity.
7. **"Advanced: a 3D model of your own (needs Blender)"**, last, as a closed fold. It holds "Shape and place" or "On the ground". It opens by itself when the item has a model or a place.

There is no Rarity control. What rarity changes in the game hasn't been seen, so a hand-set `rarity` is listed as "kept as it is".

**After Apply:**

- Each item gets a chip, "In the game" or "Left out".
- A line at the top says, for example: "Last apply: 3 of 4 items went in. Moon Herb was left out: the game already has MediumHealingHerb; give it another name."
- After a restart, the chips come from the last build's record, marked "as of the last Apply".

**Blank fields:**

- A Name left blank goes back to the item's id when the box loses focus.
- A blank Description shows a red note and still saves. The shell shows "Moon Herb has no description, so it's left out of the game" under the Editing-mod bar, and the other items still install.

**Five minutes on Items:**

1. Add an item and name it "Moon Herb", with the description "Heals a cat under the full moon".
2. Leave Starts from on Medium Healing Herb. What it does then reads "Heals 50 health (Medium Healing Herb)".
3. Add 2 Dandelion to the recipe, and Start with 3.
4. Save to mod, Apply, Play.
5. Three Moon Herbs are in the inventory, with the Medium Healing Herb's icon, and the medicine cat makes one for two Dandelion.

### Animations

The page leads with the route that needs no Blender.

1. **"What it is"**: Name, For.
2. **"The animation"** asks "Where it comes from":
   - **"One of the game's animations"**: a list with plain names first and the technical name greyed beside each:
     - "Everyday": Yawn, Stretch, Shake, Sniff, Play, Sleep, Meow, Get up, Walk, Trot, Run, Idle;
     - the photo poses, by the game's own names;
     - "All of them".
     Under the list: the animation's length, and "has root motion" where the game marks it. Beside it, "Try it on my cat" plays it in the running game.
   - **"A file I made in Blender"**: today's row, with the clip list, the facts and the kit button, and the 60 s limit stated.
3. **"What it does"**:
   - "An emote on my cat": a key or controller button from a dialog that can be cancelled, and claws out;
   - "Plays where the game plays one of its own": the same list, to choose the target;
   - "Only for scripts and stories".
4. **"How it plays"**, unless it replaces one.

After Apply, each animation shows "In the game (F7)" or "Left out: the animation is 70 s long; up to 60 s".

**Five minutes on Animations:**

1. Add, and name it "Yawn".
2. Choose One of the game's, then Yawn, then An emote on my cat. Press F7 in the dialog. F6 is mouse look's key by default, and the dialog says so.
3. Save, Apply, Play. F7 makes the cat yawn, and the mod menu's Emotes page has a Yawn button.

Second try: Add "Run", choose "Plays where the game plays one of its own", pick Trot, Save, Apply. Every cat now trots with the run.

## The plan

Each step leaves both pages working and shippable on its own.

### What this builds on

"Shell", "look" and "tests" mean the three branches already under way:

- **Shell** (`claude/studio-shell`):
  - `Studio.check_file` (`wcmods/studio.py:197` there), and problems found at save, shown under the Editing-mod bar;
  - `wc.installedEvent`;
  - `runTask`, which already keeps the drawer open and counts warnings in its plain summary;
  - help panels at `/help/<page>`;
  - the DOM shim `tests/studio/lib/dom.mjs`, with `tests/studio/unit/*.test.mjs`.
- **Look** (`claude/studio-look`): `wc.pageHead`, `studio/sections/items.css`, and the `.fold` and `.chip.good|warn|bad` classes.
- **Tests** (PR #75):
  - `tests/unit/conftest.py`, with the fixtures `studio`, `fake_game` and `save`, and the helper `make_mod(studio, id, meta, files)`;
  - the Chromium driver `tests/studio/lib/browser.mjs`;
  - CI with Node, running `tests/studio/**/*.test.mjs`. This plan's browser tests go in `tests/studio/e2e/` and its unit tests in `tests/studio/unit/`, as the shell and story plans name them.

Other plans touch the same code. This plan uses their pieces rather than making its own, and whichever lands second builds on the first:

- **story.md step 3:** `listEditor.relabel(i)`.
- **controls.md step 1:** `GET /game/keys`.
- **controls.md step 4:** `keys_in_use(cfg, mods)`, which lists the game's keys, the menu key, mouse look's key, F11, emote keys and the Emote wheel's T. It is served today as `in_use` by `/controls/check`; the Animations page needs it as `in_use` on `GET /game/keys`.
- **controls.md step 6:** the capture dialog, and `studio/lib/keys.js`.
- **docs-guide.md step 6:** writes `docs/guide/items.md` and `animations.md` with its six fixed headings, no tables and no command lines. This plan supplies their facts.
- **mods-setup.md step 3:** the Emote wheel's Add note on the Animations page.

### Page tests without the game

The pages' browser tests run the real studio with no game (the tests branch's e2e setup), so the game routes have to be served from fixtures.

- **Driver.** This plan adds `route(urlPart, json)` to `browser.mjs`, through the DevTools `Fetch.enable`, `Fetch.requestPaused` and `Fetch.fulfillRequest` calls.
- **Fixtures**, written by hand from docs/mechanics/items.md, with names and tags only and no game bytes:
  - `tests/studio/fixtures/game-items.json`: a few herbs, materials and two accessory looks;
  - `tests/studio/fixtures/anim-sequences-cat.json`.
- **Routes without a fixture.** `/game/icon` and `/game/accessory` simply fail; the pages already tolerate that.
- **Pure parts.** The pages' pure functions move into `studio/lib/items-model.js` and `studio/lib/animations-model.js`, with node:test units.

### 1. Items: the things that lose work or block the install

**Files.** `studio/sections/items.js`, `studio/lib/story.js`, `studio/lib/items-model.js` (new), `wcmods/sections/items.py`, `wcmods/studio.py`.

**Required fields.**

- `field()` takes `required`, which sets `aria-required` and adds a "needed" hint. Placeholders start with "For example:".
- A blank Description gives a red note on the card and "needs a description" in the list label.
- A blank Name goes back to the id on blur.

**Skip, don't block.**

- Python `collect` (`items.py:110-112`) warns and skips an item with a blank name or description, as `animations.py:75-77` skips one with no file. It no longer raises for the whole file. The warning reads: `<mod>: <id>: it has no description, so it's left out of the game`.
- The shell's `check_file` also returns `ctx.warnings` from `collect`. That is a one-line change, made here once the shell has merged.
- `collect` also warns and skips an accessory with nothing of its own: no texture, model, place or opacity.
- These skips don't change what selftest's `_items_section` expects (`len(warned) == 13`); re-run it to check.

**Uploads.**

- **Stale object (bug 2).** `live(it)` finds the item again by id after `await modReady()`, as `animations.js:179` does. Every picker sets its fields on that item and calls `changed(true)`.
- **Overwrite (bug 15).** Every picker sends `&current=<the file this item already has for that slot>`. `add_picture` and `add_model` keep that name when it is given. Otherwise they take the first name no file in the folder has, such as `MoonHerb-icon-2.png`. The id may keep following the name, since no upload can land on another item's file.

**Focus.** `onchange: () => draw()` goes, and `oninput` calls `listEditor.relabel(i)` (story.md step 3; whichever lands first adds it).

**Nothing of its own.** `needsOwn(it)` puts `{ tint: "#a8c4ff" }` back after the deletes at 349, 517 and 556, as the Shape select already does at 393.

**Kind.**

- The fields a Kind change drops are kept in a page-side `WeakMap`, item to `{kind: fields}`, and come back when the creator switches back.
- The stash is never put on the item, so `toJson` stays as it is, and hand-written `_` keys inside an item still save.
- A herb starts from `MediumHealingHerb`.

**Small.** A `.jpg` icon gets "icons are PNG pictures" (`items.py:504`).

**Tests.** No game needed.

- New `tests/unit/test_items.py`:
  - `test_an_item_without_a_name_or_description_is_left_out_with_a_warning`
  - `test_an_accessory_with_nothing_of_its_own_is_warned`
  - `test_ids_that_arent_letters_and_digits_are_refused`
  - `test_unknown_keys_are_refused_and_underscore_keys_ignored`
  - `test_pictures_recipes_flags_and_opacity_are_checked`
  - `test_items_json_shape`
- New `tests/unit/test_studio_items.py`, on the `studio` fixture and `make_mod`:
  - `test_the_save_check_says_an_item_without_a_description_is_left_out` (`check_file`)
  - `test_uploads_never_overwrite_another_items_picture`
  - `test_choosing_again_keeps_the_items_own_file_name`
  - `test_a_ground_model_upload_never_overwrites` (`on_cat=False`, so no skin is read)
- `tests/studio/unit/items-model.test.mjs`: `itemId`, `toJson` (keeps `_note`, drops `_new`), `fullTag`, `needsOwn`, and the Kind stash round trip.
- `tests/studio/e2e/items.test.mjs`:
  - `first upload into a new mod is kept`
  - `tab from Name lands on Description`
  - `kind round trip keeps the model`

**Docs.** In the SDK.md key table: name and description are needed, and a blank one leaves that item out with a warning. The items template's `_help` covers accessories, pictures and models.

### 2. Items: the page in the creator's order and words

**Files.** `items.js`, `items-model.js`, `wcmods/studio.py` (`game_items`, `model_view`, the picture route), `wcmods/sections/items.py` (`EFFECT_WORDS`), `studio/sections/items.css` (look), `docs/guide/items.md`.

**Card order and folds.**

- The cards come in the order above.
- The 3D cards go in a `<details class="fold">` (`data-key: items:advanced`), open when `model` or `place` is set. The script loader (UE4SS) is mentioned once, in the fold's summary, for Opacity too.
- The tag goes behind a "Technical name" fold.
- The give note and the three paint-over lines are added.

**Effects in plain words.**

- `EFFECT_WORDS` in `items.py` is keyed by herb short id, one entry for each of the 25 consumables in docs/mechanics/items.md's table. Super Healing Herb's entry says "Full health, and maybe cures (not checked)".
- `game_items` serves it as `words` for each herb, and `effectName` becomes "<words> (<herb>)", with today's wording as the fallback.
- `game_items` also returns each herb's `target`, `combat`, `exploring` and `fight_only` (from Consumables.csv), and each item's `group` (ItemGroupIcon). These feed the read-only "Used ..., for ..." line and the badge words ("a heart, like the healing herbs").

**Choices.**

- **Your materials.** A "Your materials" optgroup lists the mod's own materials by id. `Game.cost` resolves them through `made` (`items.py:542-543`), and the build already makes materials first.
- **Every look.** "A new look of" lists every look of a neck, body or paw accessory, not only `look_number === 1`. Python already takes any look; a manual check in step 3 tints a look 2 once.
- **Rarity.** `rarity` leaves `EDITED` (low bug `items.js:10`), so a hand-set one shows as kept.

**Small.**

- "Choose an item…" deletes `it.icon` (`items.js:219`).
- `/Game/` recolours get a preview, and so do own pictures outside `pictures/` (the picture route takes the mod-relative path, checked to stay inside the mod).
- `model_view` is cached by (mod, path, mtime, on_cat).

**Tests.** No game needed.

- `test_effect_words_cover_every_game_herb_in_the_docs`
- `tests/unit/test_studio_items.py::test_game_items_says_who_and_when_for_each_herb` (with `_reader` and `ctx.game` stubbed: `game_items` also reads the GUI manager and the pickups)
- node:test `effectName`
- e2e `card order: everyday cards first, the 3D fold closed`

**Docs.**

- `docs/guide/items.md`: the facts, written with docs-guide.md's six headings.
- formats.md's `items.json` paragraph names the page's buttons, not command lines.
- README's Items row.

### 3. Items: knowing whether it reached the game

**Files.** `items.py`, `items.js`, `items-model.js`, `wcmods/studio.py` (one route).

**The build's record.**

- `ctx.note("items", ...)` becomes `{"<mod>/<id>": tag}`. Today it is the sorted tag list.
- The per-item key matters for accessories: their tag is a look number given at build, which the page can't guess.
- The in-game Overview shows notes generically (`menu_host_pages.lua:94`), and nothing else reads this note. The page also reads the old list form, and shows no chips for it.

**On the page.**

- The page listens with `wc.installedEvent`. For each item it works out the state from three things:
  - `notes.items.items`;
  - the warnings starting `items: <mod>: <id>:` (`sdk.py:139-140`, `items.py:201`);
  - the `looks`, `models` and `ground` notes.
- Each item gets a chip in the list (`.chip.good` or `.chip.bad`), with the reason in plain words.
- A line at the top counts what went in.
- Two warnings keep the item in the game, and their chip says so: "In the game; on the ground it's the game's pickup", and "In the game; no save to give it in yet".
- A new `GET /build/last` returns `{built, notes, warnings}` from the build folder's `manifest.json` (written at `pipeline.py:332`). After a restart, the page shows the chips "as of the last Apply, <time>".

**Not app.js.** The shell's plain summary already counts warnings and keeps the drawer open, so this plan leaves `app.js` alone.

**Avoiding collisions.**

- `itemId()` avoids the game's own short ids, so a new "Medium Healing Herb" becomes `MediumHealingHerb2`.
- A hand-typed collision turns the Technical name line red.
- `items.py:165` names the icon texture by kind (`T_<Kind>_<id>_Icon`), so a herb and a material with the same id stop sharing it. Only built packages change.

**Tests.**

- `test_the_install_notes_each_item_with_its_mod_and_warns_the_rest`: a fake context recording `add_table_row`, `edit_csv`, `add_save_key`, `warn` and `note`, and a faked `Game` as `test_models.py` fakes `pickup`.
- `test_materials_are_built_before_herbs_across_mods`
- `test_the_tags_ini_lists_every_made_tag`
- `test_a_herb_and_a_material_with_one_id_have_their_own_icons`
- `tests/unit/test_studio_items.py::test_build_last_reads_the_last_manifest`
- node:test `itemStatus`, including the old list form.
- e2e `status after apply`, with a canned `installed` event.

**Game.** One check by hand: the chips match the inventory, and a look-2 tint is worn. Check who launched the game first.

### 4. Animations: names, uploads, the key dialog, clip limits

**Files.** `animations.js`, `animations-model.js` (new), `wcmods/studio.py` (`add_animation`, `anim_sequences`), `animations.py` (`describe`, `retarget`), `sections/animations.py` (`collect`), `studio/lib/wc.js`, `studio/sections/controls.js`.

**Name.**

- `collect` warns and skips an animation with a blank name: "<mod>: <id>: it has no name, so it's left out".
- The page puts the id back on blur.
- The Name box loses `onchange: () => draw()` and calls `relabel(i)`, the same focus fix as Items.

**Upload.**

- The page sends `&current=<a.file>`. `add_animation` keeps that name, and otherwise takes the first free one (`Wave-2.glb`). This is the same rule as step 1, and needs no freezing of the id.
- `animId` ignores case, as `collect`'s `seen` already does.
- The upload button is disabled while an upload runs (the low bug at `animations.js:168`).

**The key dialog.**

- The Controls page's `capture()` (`controls.js:311-392`) moves to `wc.captureKey({ title, pad, reserved })`. It is built on `studio/lib/keys.js`'s pure input names (controls.md step 6; whichever lands first creates `keys.js` and moves the dialog).
- The emote row offers "Press a key…", "Press a controller button…" and "No key". Escape, Cancel, a click outside and leaving the page all cancel. One dialog is open at a time.
- Keys already in use come from `keys_in_use` (controls.md step 4) through `GET /game/keys` (`in_use`). The dialog warns but doesn't refuse: "F6 also turns mouse look on and off".
- Until controls.md step 4 lands, the dialog warns only about this mod's other emotes.
- The hint shows the real menu key in place of the hard-coded "(Insert)".

**Clip limits.**

- `describe()` returns `too_long` per clip and `max_seconds`.
- `add_animation` refuses a file with no clip within the limit.
- The page greys out over-long clips and states the limit.
- A `clip` the new file doesn't have is dropped with a toast that names it.
- `retarget` refuses one key plainly: "<sequence> has one key, so it can't be replaced".

**Small.**

- `.gltf` wording in `add_animation`: "export as glTF Binary (.glb); the page takes one file".
- `aria-label`s on the checkboxes and buttons, and `data-key: editor:<noun>` on the editor pane. That is story.js's `listEditor`, so it is done once, for every page.
- For stashes the file in a page-side `WeakMap`, the same as Kind, and gives it back when switched back.
- The "kept as it is" note becomes "The game won't take these: <keys>", with a Remove button.
- `anim_sequences` catches any exception for each asset, so one unreadable asset no longer breaks the list.

**Tests.**

- `tests/unit/test_animations.py`:
  - `test_an_animation_without_a_name_is_left_out_with_a_warning`
  - `test_describe_marks_clips_over_the_limit`
  - `test_retarget_with_one_key_is_refused_plainly`
- New `tests/unit/test_studio_animations.py`, on the `studio` fixture with `_skeleton` stubbed:
  - `test_uploads_never_overwrite_another_animations_file`
  - `test_a_separate_gltf_is_refused_with_the_blender_step`
  - `test_a_file_too_long_is_refused_at_upload`
  - `test_animation_info_never_reads_outside_the_mod`
  - `test_anim_sequences_skips_an_asset_it_cant_read`
- `tests/studio/unit/animations-model.test.mjs`: `animId` (case), `toJson` (keeps `_note`), and the For stash.
- `tests/studio/e2e/animations.test.mjs`:
  - `the key dialog cancels on Escape and on a click outside`
  - `a keystroke on another page is never taken`
  - `a blank name goes back to the id`

**Game.** One check by hand of a controller button (not confirmed in verified.md).

**Docs.** SDK.md:

- the `file` row: the page takes `.glb` or a self-contained `.gltf`; "beside it" works only for a file placed by hand;
- the `key` row: keys in use, and a controller button;
- the limits: 60 s and 64 MB, and that anything over them is left out.

### 5. Animations without Blender: a game animation as an emote or for scripts

**Files.** `sections/animations.py`, `animations.py`, `sdk.py`, `studio.py`, `animations.js`, `animations-model.js`.

**Format.** A new key, `"game"`, used in place of `"file"`. It takes what `"replaces"` takes, a name or a path:

```json
{"id": "Yawn", "name": "Yawn", "game": "A_CatMaster_Yawn_1", "emote": true, "key": "F7"}
{"id": "Flap", "name": "Flap", "for": "bird", "game": "A_Bird_Flying_Loop_1", "loop": true}
```

**Checks.**

- `check()` adds `game` to `KEYS`, requires exactly one of `file` or `game`, and refuses `clip` with `game`.
- `collect()`'s skip at line 75 becomes "neither `file` nor `game`".

**Build without claws.** No package is made.

- A new `ctx.game_sequence(name, kind)` returns `{"path", "seconds", "additive", "root_motion"}`. It uses `find_sequence`, reads the sequence once, and gives `seconds` as `(nkeys - 1) / frame_rate`, as `studio.anim_sequence` does.
- An additive sequence is refused.
- The `WCModsAnims` entry's `path` is `path + "." + short`. `Game.anims.play` loads it by path as it does today (`game.lua:1567-1595`), the same form the Emote wheel uses for the photo poses.

**Build with claws.** A new `ctx.add_animation_from_game(name, sequence, kind, claws, source)` makes a copy of the kind's template, as the glTF path does:

- keys from `src.tracks(src.bind_pose(skeleton))`;
- `set_tracks(keys, bones=src.track_map, length=(src.nkeys - 1) / src.frame_rate())`;
- the claws constants;
- `rename`;
- cached under the source's path and bytes hash.

The source's face curves are dropped, and SDK.md says so.

**The page.**

- The "Where it comes from" choice.
- `/game/anim-sequences` gains a `label` from a `FRIENDLY` table in `animations.py`, for the names the repo knows:
  - `Idle_1`, `Walk_1`, `Trot_1`, `Run_1`, `Meow`, `Stretch_1`, `Shake_1`, `Yawn_1`, `Sniffing_1`, `Play_1`, `Sleep_Loop_2`, `Get_Up_1`;
  - `Pose_Photo_Mode_1` to `_14`, by the game's pose names read through `ctx.text("STR_PHOTOMODE_POSE_n")`.
- `Stand_1_c`, `Powerfull_Loop_1` and the rest get labels once someone has watched them. Sit, groom and pounce aren't known by name in the repo yet.
- The list loads only when the picker is shown, with "Reading the game's animations…" while it reads (about 3 s for cats, then memoised for the studio run as today; no disk cache).
- **"Try it on my cat"** is a new `POST /game/try-anim`, built like `/game/where` (code mods needed; `Bridge(cfg).run`). It runs `Game.anims.play(nil, "<path>")` on a `/Game/` path only, so a game animation can be seen before it is chosen. Without the game, or with code mods off, the button says what to do in one sentence.

**Tests.**

- `test_a_game_animation_needs_no_file`
- `test_a_game_animation_goes_in_the_list_by_its_path` (`FakeCtx` gains `game_sequence` and `add_animation_from_game`)
- `test_claws_out_on_a_game_animation_makes_a_copy`
- `test_an_additive_game_animation_is_refused`
- `test_friendly_names_are_real_sequence_names` (each is a kit example name or a documented one)
- `test_build_from_a_game_sequence_keeps_its_keys` (toy skeleton)
- `tests/unit/test_studio_animations.py::test_try_anim_plays_a_game_path_through_the_bridge` (Bridge stubbed; a non-`/Game/` path and code mods off are refused)
- e2e `game emote flow`

**Game.** A new `tests/game/test_animations.py`, run with `python wcmods.py agent test -k animations --launch`:

- `test_a_game_animation_plays_as_an_emote`:
  1. Install a test mod with `agent install --with`. Its Yawn emote is set to loop, on F7.
  2. Press F7, then read one object: `Game.player().Mesh:GetAnimInstance():IsAnyMontagePlaying()`.
  3. Press F7 again; after the blend, it reads false.
- `test_claws_out_on_a_game_animation`
- "Try it on my cat" is checked once by hand.

**Docs.** SDK.md gets a `game` row ("needs wcmods 0.4.0 or newer; an older one refuses the key and leaves that mod's animations out") and a "Without Blender" paragraph. Also:

- formats.md: an example;
- README: the Animations row;
- scripting.md: the `list()` row;
- verified.md;
- `docs/guide/animations.md`: the facts, written with docs-guide.md's headings.

### 6. Animations without Blender: one game animation in another's place

**Files.** `animations.py`, `sdk.py`, `sections/animations.py`, `animations.js`.

**Format.**

```json
{"id": "Trot", "name": "Run as the trot", "game": "A_CatMaster_Run_1", "replaces": "A_CatMaster_Trot_1"}
```

**Build.**

- `ctx.replace_animation` gains a new keyword, `from_game="A_CatMaster_Run_1"`, as an alternative to `read`, which may then be `None`. The existing `source=` is the provenance text, so the new keyword has to have another name.
- `animations.build(..., replace=True, from_game=...)` reads the source's keys and fits them to the target's `nkeys` with `fit_keys(tracks, n)`, linear for positions and `_nlerp` for rotations over normalised time.
- Then `set_tracks(keys, bones=src.track_map, keep_length=True)`. That combination is untested, so it gets the first test. After that, the ACL move and the notifies work as they do today.
- Refused, each with a sentence:
  - an additive source;
  - a source for another kind;
  - a target with fewer than two keys;
  - a source the same as the target.
- `replaced` is keyed by full path, so the false "replaces it too" goes (`sections/animations.py:101`).

**The page.** The same picker chooses the target. The facts read: "Every cat plays Run where the game played Trot (0.47 s; fitted to its 15 keys)".

**Tests.**

- `test_fit_keys_keeps_the_ends_and_interpolates`
- `test_a_game_sequence_replaces_another_fitted_to_its_keys`
- `test_a_source_with_one_key_or_additive_is_refused`
- `test_the_section_passes_from_game_for_a_game_replacement`
- `test_two_sequences_with_one_short_name_both_go_in`

**Game.** `test_the_trot_can_be_another_game_animation` puts `A_CatMaster_Sleep_Loop_2` in `A_CatMaster_Trot_1`'s place by `game` rather than through the kit, so verified.md's measurement carries over. With W held, the head bone's height above the root over one second is under 3.5 cm, against about 14 cm without the mod. The result goes in verified.md.

**Docs.** SDK.md's replacing paragraph, including the `from_game` keyword, which is backward compatible. The guide's second try.

### 7. Animations: status, the kits, one playing state with the Emote wheel

**Files.** `animations.js`, `animations-model.js`, `sections/animations.py`, `wcmods/studio.py` (`/game/anim-kinds`), `wcmods/lua/game.lua`, `wcmods/lua/emotes.lua`.

**Status.** Built as in step 3, from `notes.animations.animations`, `emotes` and `replaced`, and the warnings starting `animations: <mod>: <id>:`.

**Start kits.**

- A "Start kits (for Blender)" card at the top, with one button per animal.
- A "Making…" state that stays until the download arrives.
- The example count from `/game/anim-kinds`.
- "Unzip it first; then import the .glb into Blender."
- "Add" and the default name agree: "Add an animation" makes "New animation".

**One playing state.**

- `Game.anims` publishes the current id for each actor through `ModRef:SetSharedVariable("WCModsAnims.playing.<address>", id)`. Strings are carried, per reverse-engineering.md.
- `playing()` and `stop()` read it, so a key stops what the wheel started.
- `emotes.lua` guards `v.X`.
- The two-emotes warning says what happens: "only the later one plays".
- The Emote wheel needs a matching change in its own repo.

**Tests.**

- node:test `animationStatus`
- `test_two_emotes_on_one_key_say_only_the_later_plays`
- `tests/unit/test_lua.py`: a string check that `game.lua` shares the playing id and that `emotes.lua` guards velocity.

**Game.** A check by hand that the wheel and the key agree.

**Docs.**

- README and SDK.md mention the Emote wheel. Its Add note on the page is mods-setup.md step 3's.
- SDK.md says `-` becomes `_` in `/Game/WCMods/<mod>/A_<id>`.
- SDK.md says what verified.md hasn't confirmed: animations on the clans' cats and quest givers, seven of the nine animals, and a controller button.

### Formats and compatibility

**`items.json`.** Its keys are unchanged, and a mod made before keeps working.

- The page no longer writes anything new, and keeps hand-written `_` keys.
- `collect` only gets more lenient: a blank name or description, or an accessory with nothing of its own, now leaves out one item with a warning, where before it raised for the whole file.

**`animations.json`.**

- `"game"` is new. Old files don't change.
- A mod that uses `"game"` needs wcmods 0.4.0. An older wcmods refuses the key and leaves that mod's animations out, and SDK.md says so.
- Bump `__version__` in its own PR before the release that ships it.

**`sdk.py`.** `replace_animation` gains an optional keyword, and `game_sequence` and `add_animation_from_game` are new. Nothing existing changes.

**The manifest.** The `items` note changes from a list to a map. The in-game Overview shows either; the page reads both.

**Built packages.** Icon texture names change, so the next Apply rebuilds them. Nothing is kept from one build to the next.

### Needs the game

- Step 3: once, by hand.
- Step 4: once, by hand (a controller button).
- Step 5: `python wcmods.py agent test -k animations --launch`, plus "Try it on my cat" once by hand.
- Step 6: the same agent run.
- Step 7: once, by hand.

Each time, check first that no other session launched the game. Everything else is unit, node or browser tests.

## Not in this plan

**Known to be impossible:**

- a new effect strength or a combined effect (effects are Blueprint containers);
- new looks for head accessories (the game shows look 1);
- a new walk or idle for your cat only (every cat shares one AnimBlueprint);
- swimming, flying or climbing as movement (there is no state or water movement for them).

**Needs reverse engineering first:**

- herbs with the unused parameter rows (the effect manager's map is unknown);
- herbs that grow in the forest (the spawn tables haven't been read);
- see-through accessories with a picture (no translucent skinned material takes a texture);
- den decorations, and materials from interactables (the Blueprints haven't been read);
- mirroring an animation (the bone pairs aren't named);
- emotes with sound, face emotes, and footsteps that move (no sound API, and keyed curves and notifies can't be written);
- animations on the named story cats (their skeletons haven't been compared);
- which game sequences are which, beyond the 15 the repo knows.

**Possible, but deferred:**

- a canvas preview on the page ("Try it on my cat" covers the game's own animations);
- "Try it in the game now" for your own files;
- trimming or reversing an animation;
- a dropped accessory shown as its own model;
- "give every time";
- an editor for the game's recipes;
- a Rarity control, until someone has seen what rarity changes in the game.

**Bugs 7 and 8 in `models.lua`:** PR #72. It needs one pass in the game first, with two saves and a look at the main menu's cat.

## Open questions

1. Should a half-made item or animation be skipped with a warning so the rest installs (planned; needs `check_file` to return warnings), or should it keep blocking the mod?
2. Which of the 247 cat sequences are "everyday", and what should they be called? The repo knows about 15. The rest need watching, either through "Try it on my cat" or through the ABP/montage usage index named in the audit's reverse-engineering gaps.
3. Does Opacity belong under the Advanced fold (it needs UE4SS too), or should it stay in Look?
4. What does rarity show in the game? Should category colour, "who it's for" and "when it can be used" become controls? Mixing a combat-only effect with a herb used while exploring is untested.
5. Should the studio delete files no item names, on save or zip (after a confirm), or only say that they stay?
6. Keys the game uses: warn only (planned), or refuse?
7. The claws-out copy of a game animation drops its face curves. Is that acceptable, or should claws be refused for game animations until keyed curves can be written?
8. "Try it on my cat" needs code mods allowed. Is that acceptable, or should the button stay hidden until they are?

## What this review changed

- **Bugs.** Bug 15 is new (the Items upload overwrite), with its fix.
- **Uploads.** Both pages use the same rule (`current`, then a free name). Animations no longer freezes the id.
- **Kind stash.** It moved off the item into a `WeakMap`, so hand-written `_` keys survive.
- **Rarity.** The control was dropped, since nobody has seen what rarity changes. "Every look" was added.
- **The items note.** It is keyed by `<mod>/<id>`, since accessories' tags are only known at build. `GET /build/last` was added.
- **Shell overlap.** The `app.js` toast change was dropped; the shell's summary already does it.
- **Other plans.** The key dialog, `/game/keys` and `relabel` now come from controls.md and story.md instead of being made twice. The guide pages follow docs-guide.md.
- **`from_game`.** `source=` was renamed to `from_game=`, because `replace_animation` already has a `source`.
- **`game_sequence`.** One `ctx.game_sequence` replaces `find_sequence` plus `sequence_seconds`.
- **Disk cache.** The anim-sequences disk cache was dropped.
- **Try it on my cat.** Added for the audit's high "no preview" issue.
- **Examples.** They use F7, because F6 is mouse look's key.
- **Game test.** The step 6 test uses the sleep loop, so verified.md's thresholds apply.
- **Test files.** Renamed to `tests/studio/unit|e2e/*.test.mjs` and `test_studio_items.py`. `browser.mjs` gains `route()`, and the fixtures are written by hand.
- **PRs.** Steps 5 and 6 are now separate PRs. `cli.py` was dropped from step 7.
