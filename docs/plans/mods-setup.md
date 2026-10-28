# Getting set up, the Mods page and the companion mods

A plan for the first-run path, the Mods page, the four mods that ship beside Clan Mod Studio (Menu pages, Sandbox mode, Creator palettes, Emote wheel), what Apply says reached the game, the game-build policy, Mod packs, and Settings and repair. It comes from the 2026-10-28 audit (the mods, separate-mods, packs-settings and pipeline maps) and the skeptics' verdicts on every high and medium claim. Low claims were not checked and are marked as such.

Three pieces of work are already under way on other branches and are not planned again here:

- The test harness (`claude/studio-tests`): tests/unit/conftest.py with the `studio`, `fake_game`, `save` fixtures and `make_mod`, tests/unit/test_studio_api.py and test_studio_http.py, `WCMODS_FAKE_RUNNING` for "the game is running", node:test units in tests/studio/*.test.mjs and browser tests in tests/studio/e2e/*.test.mjs through tests/studio/lib/browser.mjs, CI with Node. It already makes `POST /backup` refuse when there is no save, leaving no empty backup (`test_backing_up_without_a_save_is_refused_and_leaves_no_empty_backup`).
- The Leaf and Bark look: styles.css, the theme toggle, studio/sections/mods.css and the other per-page files, `wc.pageHead`.
- The shell (`claude/studio-shell`). It adds:
  - save-time validation through each section's collect() and `Studio.check_file`;
  - the dirty guard and `wc.installedEvent`;
  - progress polling (`GET /progress`) and the plain-words summary in the log drawer;
  - the Last apply button, and Play's drawer staying open when there is trouble;
  - errors reworded for creators, with details in studio.log, and a Restart button after an update;
  - `Mod.broken`, so `discover()` lists a mod with a damaged mod.json instead of failing;
  - a tolerant `Config` that sets a damaged wcmods.json aside and writes it atomically, and `cfg.peek()`;
  - `InstallBlocked`, with a per-mod `failed` list of (mod id or None, text) in each section's report;
  - Play returning its manifest;
  - the Settings page's Allow without `location.reload()`;
  - help panels from docs/guide/<page>.md.

Other plans touch the same code. This one is written to fit them:

- docs/plans/story.md:
  - Step 1 releases Sandbox mode 0.5 and fixes the sandbox's per-slot progress.
  - Step 2 does the following:
    - story files `use` Sandbox mode instead of requiring it (bug 25);
    - `mods.version_key`, which this plan's version checks share;
    - `sandboxStrip` on Characters and Questlines, with the "you have 0.4, Fixed looks need 0.5" words;
    - `uses_notes` in the add preview;
    - `packs.play()` keeping the mods a pack's mods `use`.
  - It also fixes the talk key G on the Characters page and formats.md.
- docs/plans/console-lua.md:
  - Step 2: `pending()` asks for an Apply when code mods are allowed and the game bridge isn't in (bug 11).
  - Step 4: `installed.problems` per mod, shown on its card.
  - Step 5: `scriptlog.report`, which reads UE4SS.log per script mod.
  - Step 6: a script mod's settings.json no longer counts as a change.
- docs/plans/palettes-cat.md: the Palettes page's "What reaches the game" strip, with its Creator palettes line.
- docs/plans/data-save.md, step 6: a restore forgets the save-change records made after the backup. That plan also owns a failure inside `apply_save_ops`.
- docs/plans/names.md: Take all mods out names the cats that will show as missing text.
- docs/plans/docs-guide.md:
  - It writes docs/guide/mods.md, packs.md, settings.md and companion-mods.md.
  - It moves README's Requirements to docs/setup.md.
  - This plan's PRs update those pages for what they change; they do not write them a second time.

Where a step leans on one of these, it says so.

## What it is for

A creative person who has never modded anything downloads Clan Mod Studio and opens it. Within five minutes the game is running with a mod in it. They never have to read GitHub, a command line or a settings file.

From then on, the Mods page is where they:
- add what friends send them;
- get the mods the studio's own pages need, with one click;
- are told in plain words when something didn't reach the game, why, and what to press to fix it, including after Steam updates the game.

## Where it stands

### What works, and how it was verified

- **The zip path is careful.** Path escapes, Windows name clashes, links, oversize files and wrong mod.json types are refused before anything is written. tests/unit/test_mods.py covers it, with 12 tests passing on 2026-10-28.
- **Switching on and off.** Turning a mod on cascades through `requires`. Removal is blocked while mods that are on need the mod.
- **Removed and replaced mods.** They go to backups/mods, and Settings and repair brings them back.
- **Get set up:**
  - It finds the game through Steam or a typed folder.
  - It makes the first save backup once.
  - It downloads UE4SS from the experimental-latest release and sets it up for players.
  - It fetches Menu pages from its GitHub release, keeping settings.json.
  - This is covered by the selftests `_onboarding`, `_onboarding_edges` and `_menu_pages`, all wrapped by tests/unit/test_mods.py.
- **Mod packs** save, describe, play on their own with a remembered snapshot, stop, and zip with every mod inside (tests/unit/test_story.py).
- **Settings and repair:** Options, backups, restore and Take all mods out do what they say. Their tests pass.
- **Game updates:** the update path holds back mods that don't list the installed build, and lets the player use one anyway, per build. This is the selftest `_outdated_mods`, which needs the game.

### What is half finished

- **Getting the companion mods.**
  - Only Menu pages has a fetch path: wcmods/menupages.py is hard-wired to one repository.
  - Sandbox mode, Creator palettes and Emote wheel can only arrive as a .zip the creator finds on GitHub.
  - Two of them, Emote wheel and Creator palettes, have no release to find: `gh release list` is empty for both (verified).
  - The Creator palettes .zip holds twelve mods: the mod, ten themed palettes that ship off, and Coat presets, which ships on.
- **Versions.**
  - Nothing lets a mod say which wcmods it needs.
  - wcmods/__init__.py still says 0.3.0, although coats support, WCModsPalettes and the npcs `look`/`slots` spawn (PR #71) all landed after the v0.3.0 tag.
  - Sandbox mode 0.5, which passes the Characters page's Fixed look on to the game, is merged on that repository's main but unreleased (the story plan's step 1).
  - The studio never looks at the installed sandbox's version.
- **After a game update.** Every mod the studio makes is pinned to the build it was made on. Nothing in the studio can un-pin it.
- **Setup steps.**
  - "Allow mods that run code" is not a setup step.
  - After Not now on Menu pages, the one-click add is gone for good.
- **Crash reports** exist only on the command line (`python wcmods.py cpp crash`).
- **Adding a folder** from the launcher is a thinner copy of the zip path: no `_check_meta`, no `id`, no dedupe.
- **After Apply.** Nothing in the studio says whether a mod actually reached the game. A forced Apply records a failed mod as installed.

### The confirmed bugs

Each entry gives the skeptic's correction where there was one. A tag after the severity says where a bug is already dealt with:

- "shell": the shell branch.
- "tests branch": the harness branch.
- "story plan" or "console-lua plan": that plan.

Tagged bugs are listed so nobody looks for them again. Every other bug has a step below.

1. wcmods/mods.py:226 [high; shell: `Mod.broken` and the guarded `discover()`]: one damaged mod.json makes `discover()` raise. That can be a trailing comma, or a file cut short by a crash during a switch, since `Mod.update` writes in place. Then:
   - GET /mods fails;
   - every page's mod list is empty;
   - the message doesn't name the mod.
2. wcmods/exe/gamebuild.py:66 and studio/sections/mods.js:45 [medium, lowered from high: not silent, a confusing dead end]:
   - On the verified build, every mod without `game_builds` counts as made for 24847281 and is left out. That includes all 25 in wcmods-examples, which README step 4 sends new players to.
   - The left-out summary banner only draws when the build is not verified.
   - So the only signs are a red line and a "Use it anyway…" behind a crash warning on each card.
3. wcmods/modzip.py:296 [medium, lowered from high]:
   - Adding a mod switched on, when its `requires` names a mod not in mods/, leaves it on with an unmet requirement. Switching it on by hand is refused in the same situation.
   - So the next Play or Apply stops until it is turned off or forced.
   - The page names the missing mod by its raw id.
4. studio/sections/mods.js:476 [medium]: each keystroke in Find a mod replaces the box with the trimmed, lower-cased text. "Dark Forest" becomes "darkforest" and finds nothing.
5. wcmods/modzip.py:330 [medium]: `inspect_folder` names a dropped folder after its folder name, while `add_folder` uses mod.json's `id`. A folder dropped on the launcher whose id differs can't be added ("none of the mods picked are in it").
6. wcmods/modzip.py:203 [medium]: a .zip with mod.json at its top and no `id` is named after the download's file name, version included. An update zipped the same way becomes a second mod, with both on.
7. studio/sections/mods.js:294 [low, lowered from medium]: a pack .zip's preview warns "Needs moonlit-cats, sandbox, which you don't have" about mods that are ticked right under it, because `needs` is computed against installed mods only.
8. studio/sections/mods.js:161 [medium; the separate-mods skeptic rated the same finding low at :158] — after Not now:
   - The Menu pages step shows a GitHub link and a command line, with no Add it button.
   - `skip_menu_pages` is never cleared.
   - Once the other steps are done, the whole card hides, while Settings and the in-game Overview still point at it.
9. wcmods/onboarding.py:29 [low, lowered from medium]: `status()` does `cfg.reload()`. That is GET /setup, called on every focus without the lock. The reload swaps the shared dict under an install that has noted `installed_ue4ss` but not saved yet. `set_game_dir()` reloads and saves outside the lock the same way.
10. studio/app.js:177 [low, lowered from medium; shell: the drawer stays open when there is trouble, and Last apply]: Play's drawer hides itself after 4 s and nothing reopens it.
11. wcmods/pipeline.py:404 [high; console-lua plan step 2]:
    - Problem: the install record has no code flag, so turning on "Allow mods that run code" after an install changes nothing `pending()` looks at.
    - What the player sees: the top bar keeps "Game up to date", Play just starts the game, and Menu pages, Sandbox mode and every script stay out until the player presses Apply by hand.
    - The fix: that plan adds a `pending()` redo when code is allowed and the bridge isn't in `installed_ue4ss`.
    - What this plan adds: only the words the Settings page and the setup step say around it.
12. wcmods/packs.py:39 [medium, lowered from high]: removing the pack named in `pack_before` leaves the player's own mods off, with no banner and no Back to my mods. `describe()` reports a playing pack only while its folder exists, and the remove route never calls `packs.stop()`.
13. studio/sections/packs.js:75 [medium]: Change it pre-selects a required mod that was removed, and the checklist can't untick it. So Save the pack always fails with "there's no mod X in your mods folder".
14. wcmods/modzip.py:441 [medium] — a pack whose content lives in the default My mods (id my-mods) requires that id. For a recipient with their own My mods:
    - the pack's copy is unticked;
    - the pack is added, and `_needs_on` turns on the recipient's own my-mods;
    - Play only this pack plays the recipient's content, not the creator's.
15. studio/sections/settings.js:34 [medium; shell: Allow and un-allow now emit `sections-changed` and `mods-changed` instead of `location.reload()`]: Allow and un-allow end in `location.reload()`, throwing away unsaved edits on other pages and the toast that says to Apply.
16. studio/sections/settings.js:106 [low, lowered from medium: a missing sentence] — after restoring a backup from before an install's save edits:
    - those edits are gone while the top bar says "Game up to date";
    - the toast never says that Apply puts them back.
    - Restoring is the documented way to undo those edits, so the fix is words, not a pending redo.
17. wcmods/formats/save.py:134 [low, lowered from medium; tests branch: the `/backup` route refuses without a save and leaves no folder] — Back up now before the game has made its save folder:
    - toasts the raw WinError;
    - leaves an empty backup folder, which the page lists with a Restore button.
    - The page still shows the button.
18. wcmods/pipeline.py:619 [low, lowered from medium: consistent, but nothing explains it]: after Take all mods out the mods stay on, so the bar at once says "Not applied yet" and Play reads "Apply and play".
19. wcmods/config.py:56 [medium; shell: tolerant Config]: a wcmods.json that isn't valid JSON stops every command at start with "error: Expecting …", naming no file.
20. wcmods/packs.py:25 [low, lowered from medium]: the Mod packs page never says that one of a pack's mods won't reach the game, for example a script with code mods off, or a mod held back for the build. The Mods page cards do say it.
21. wcmods/mods.py:246 [medium, by design but a dead end] — every mod made in the studio lists only the build it was made on:
    - after an update, each of the player's own mods is held back behind a crash warning, per build;
    - no studio action adds the new build.
22. wcmods/exe/gamebuild.py:61 [low, lowered from medium] — `_builds()` keeps only ints:
    - a digit string, a list of strings, a list of floats or an empty list all count as made for 24847281;
    - the card then gives the wrong reason.
23. wcmods/pipeline.py:406 [low, lowered from medium]: a held-back mod is listed in the changes banner as "<name> off" while its switch is on.
24. wcmods/__init__.py:3 [medium, lowered from high; reachable only once that mod is released]: no mod.json field can state a wcmods minimum, and `__version__` is still 0.3.0. So Creator palettes 1.2.0's Coat presets, which ships on, stops every Apply on the released wcmods with "unknown palette section coats".
25. wcmods/studio.py:391 [medium, lowered from high: signposted, not silent; story plan step 2] — saving one character adds sandbox to the mod's `requires` for good:
    - the studio never takes it off;
    - without the sandbox mod, that whole mod is refused at Apply, its items too.
26. D:/projects/wcmods-sandbox/sandbox/scripts/story.lua:167 [high; the release and the version words are story plan steps 1 and 2; getting it from inside the studio is step 2 here]:
    - The released Sandbox mode 0.4 spawns studio cats without `look` and `slots`, so Fixed look does nothing.
    - The fix is merged but unreleased, and its mod.json still says 0.4.
    - The studio checks no version.
27. D:/projects/wcmods-emote-wheel/README.md:24 [medium, lowered from high]: neither Emote wheel nor Creator palettes has a GitHub release, while both READMEs and docs/formats.md send creators to Releases.
28. wcmods/modzip.py:237 [low, lowered from medium]: the preview's one "Switch it on" box applies to every ticked mod, overriding each mod's shipped `enabled`. Ticking Creator palettes' ten themed palettes turns all ten on.
29. wcmods/packs.py:13 [low, lowered from medium]: Play only this pack keeps only Menu pages on. Creator palettes (with its coat presets) and the Emote wheel go off, and a cat wearing a preset shows its saved coat.
30. wcmods/modzip.py:45 [low, unchecked]: `safe_id` drops accented letters ("Étoile" becomes "toile").
31. wcmods/onboarding.py:153 [low, unchecked]: a mod dropped on the launcher expires after ten minutes, even while its preview is on screen.
32. studio/sections/mods.js:346 [low, unchecked]: problem lines from `unmet()` start lowercase and name raw ids.
33. studio/sections/mods.js:361 [low, unchecked]: the mod's name is inside the switch's label, so clicking the name toggles the mod.
34. studio/sections/mods.js:448 [low, unchecked]: Get the latest says "Apply to game to use it" even when Menu pages is off.
35. studio/sections/packs.js:117 [low, unchecked]: every mods-changed event rebuilds the pack form and loses what was typed.
36. wcmods/formats/save.py:153 and wcmods/studio.py:423 [low, unchecked]: `restore()` accepts a backup name that climbs out of the backups folder, and /backup and /restore run outside the studio lock.
37. wcmods/crashes.py:86 [low, unchecked]: a CrashContext.runtime-xml written as UTF-16 raises ParseError.
38. wcmods/config.py:83 [low, unchecked]: `Config.game_dir` returns any existing folder without checking `is_game_dir`. With a moved game, Play and Apply stay enabled while Get set up asks where the game is, and Play fails inside the build with a paks path.
39. studio/sections/packs.js:55 [low, unchecked]: a pack being played on its own is labelled "On with my mods".
40. studio/sections/settings.js:29 [low, unchecked]: Game console says "Needs UE4SS." when UE4SS is there but its console mod isn't.
41. wcmods/menusettings.py:89 [low, unchecked]: a controller button set by hand in wcmods.json shows as a raw Unreal name and can't be chosen again.
42. studio/sections/settings.js:140 [low, unchecked]: Make your own mod answers an empty or capitalised folder name with a rule about characters, where `safe_id` could make the name.
43. wcmods/pipeline.py:494 [medium, lowered from high] — after "Apply the rest anyway", a mod that failed to build is recorded as installed:
    - the page says "The game has your mods as they are here";
    - its card shows nothing wrong;
    - the in-game Installed mods page lists it.
44. wcmods/pipeline.py:442 [medium] — a section that fails with no mod involved makes install say "some mods didn't build". That happens when items and animations read the game's tables while Steam updates the game, or after a table format change.
    - The shell drops the exception's type name from the text.
    - The blame, and an "Apply the rest anyway" that installs without wcmods' own shared module, remain.
45. wcmods/pipeline.py:450 [low, lowered from medium] — install removes the old paks before copying the new ones:
    - a failed copy leaves ~mods half written;
    - `install_outdated()` (pipeline.py:611, low, unchecked) only checks the .utoc, so it doesn't notice.
    - The `apply_save_ops` half is the data-save plan's.
46. wcmods/cli.py:501 [low, lowered from medium]: `wcmods build`, `install` and `status` save the wcmods.json they loaded at start over whatever the studio wrote meanwhile.
47. wcmods/pipeline.py:102 [low, lowered from medium]: no cross-process lock. A command-line install beside the studio's Apply can delete build/ under it.
48. wcmods/pipeline.py:45 [low, lowered from medium]: two mods' own paks can land on one installed name and overwrite each other silently.
49. Pipeline lows, unchecked:
    - wcmods/exe/gamebuild.py:194: a failed signature check isn't cached, so every Apply re-runs the minute-long check.
    - wcmods/pipeline.py:379: `built` is stamped at the end of the build, so a file saved during a build is never seen as changed.
    - wcmods/sdk.py:395: rollback drops the failing section's own warnings, and a section.py that won't load is only logged.
    - wcmods/studio.py:412: Apply builds for minutes before noticing the game is running.
    - wcmods/cli.py:66: "Game updated" is also said for an older build.
    - wcmods/pipeline.py:386: with every mod held back, a game update doesn't ask for the install again.
    - wcmods/pipeline.py:154, sections/scripts.py:53 and sections/cpp.py:136: the code-off warnings say to edit wcmods.json. The shell rewords the section.py one; the other two remain.
    - wcmods/studio.py:1072: OSErrors reach the page as a 500 with the exception's name. Shell: `sentence()` and studio.log.
    - Cheats on at start counts as a change: console-lua plan step 6.

### Refuted, and what is out of scope

Refuted and left out: "Play with Apply the rest anyway never shows which mod failed or why". The failure is in the drawer on the attempt before; only the retry's drawer omits it, and the shell's drawer summary now covers that.

Confirmed in the companion repositories, to be done there (step 9 lists them):

- The Emote wheel's default key T is the game's map key.
- The committed wcmods-examples palettes add no new slots.
- wcmods-examples has no `game_builds` (D:/projects/wcmods-examples/README.md:94, medium).
- Low and unchecked: `sandbox_api.lua` assumes `Game` exists, and the Emote wheel's keys never show in the Overview.

Confirmed but owned by the story plan:

- Sandbox story progress kept by slot alone (story.lua:232).
- The Characters page and formats.md naming the wrong talk key (npcs.js:70).
- The sandbox ignoring the story format number, and the dead "Show the quest panel" switch (low).
- The Characters banner naming the wrong file (story.js:128, low).

## What a creator should be able to do

The Mods page has five cards, top to bottom.

1. **Get set up** lists the once-only steps, with a tick each. When they are all done, it folds into one line ("Set up ✓ show") instead of vanishing. The steps:
   - **"Found the game"** (or "Where's the game?" with the folder box).
   - **"Your save is backed up"** (or "Start the game once").
   - **"The script loader is installed"** (Install it / Use a .zip I downloaded…).
   - **"Let mods run their own scripts"**: one Allow button and a Not now, under this sentence: "Menu pages, Sandbox mode, Creator palettes and the Emote wheel are small programs that run inside the game. Only add mods like these from people you trust; the four that come with Clan Mod Studio are fine."
   - **"Get the mods that go with Clan Mod Studio"**: one "Add all four" button and Not now. The four are listed by name in the card below, not a second time here.
2. **"Mods that go with Clan Mod Studio"** (the Add-ons card) is the one place the four are listed. It stays on the page after setup, folded to one line when every add-on is in and current.
   - Each row has a name, one sentence in plain words, a state chip and one button.
   - The sentences: "Shows the cats and questlines you make", "Your new colours and coat presets in the cat maker", "A wheel of your emotes and the game's poses", "Your cat, the world, quests, fights and cheats in the in-game menu".
   - The state chips:
     - "Not added";
     - "In, 0.4";
     - "Newer one out: 0.5";
     - "Off";
     - "Needs scripts allowed";
     - "Needs a newer Clan Mod Studio";
     - "No release yet".
   - The buttons: Add, Get the latest, or Switch on.
   - The same Add button appears wherever a page says one of them is needed:
     - the story plan's Sandbox mode strip on Characters and Questlines;
     - the palettes-cat plan's Creator palettes line on the Palettes page;
     - a note on the Animations page;
     - the add preview's "works with Sandbox mode, which you don't have" line.
3. **"Add a mod"** is the drop zone, unchanged in shape. Its preview:
   - names mods, never ids;
   - says "in this .zip" for a pack's own mods;
   - shows each mod's shipped on/off state when a .zip holds several;
   - when a requirement is missing, offers Add if it is a known add-on, or adds the mod switched off and says why.
4. **"The game updated"** appears only after a Steam update.
   - It says "Checking your mods on the new version…" while the check runs.
   - Then it says, for example, "3 of your mods were checked on the new version and are fine. 1 couldn't go in: Old tweaks: data.json names a value the game no longer has (Run speed)", with "Turn it off" beside that one.
   - Mods that run code say "made for the older version; its maker has to update it", with "Use it anyway…" and its warning.
5. **"Your mods"** is the list, with a search box that keeps what you type. Each card says "Not in the game: <why>" when the last Apply left it out.

The five-minute first try:
1. Double-click Clan Mod Studio, and say yes to Python if asked.
2. Watch Get set up tick off the game and the save.
3. Press Install it for the script loader.
4. Press Allow on the scripts step.
5. Press Add all four.
6. Press Play. The game starts with the mod menu and its pages in it.
7. Back in the studio, open Characters, make a cat, save, press Play. The cat is there, because Sandbox mode came with the add-ons.
8. Send a friend the .zip from Save as .zip. On their Mods page, the preview says the mod works with Sandbox mode and offers to add it.

## The plan

Each step leaves the page working on its own. "Needs the game" says how a step is checked beyond the unit tests. Python tests go into tests/unit and use the harness's `studio`, `fake_game` and `save` fixtures and `make_mod`. Browser tests go into tests/studio/e2e/<page>.test.mjs, through lib/browser.mjs with a stubbed or temp-folder studio. Unit tests of studio/lib go into tests/studio/<name>.test.mjs.

### 1. Version and the "wcmods" minimum

**Files:**
- wcmods/__init__.py (`__version__ = "0.4.0"`)
- wcmods/mods.py
- wcmods/exe/gamebuild.py
- wcmods/modzip.py
- wcmods/pipeline.py
- wcmods/studio.py

**Format.** mod.json gains an optional `"wcmods": "0.4.0"`: the lowest Clan Mod Studio that can build the mod.
- It is a plain dotted number, compared with `mods.version_key` (the helper the story plan's step 2 also uses; whichever lands first adds it). `"0.4"` means `0.4.0`.
- `Mod` reads it into `self.wcmods_min`. A malformed value in a hand-edited file falls back to none, as `Mod` does for every other key.
- `modzip._check_meta` refuses a .zip whose value isn't digits and dots, with 'mod.json's "wcmods" should be a version like "0.4.0"'.

**Leaving a mod out.**
- A new `mods.too_new(mods)` returns `{id: "needs Clan Mod Studio 0.4.0 or newer; you have 0.3.0: update it"}` for enabled mods whose minimum is above `__version__`.
- The loop in `gamebuild.held_back` that adds the mods needing a held-back mod becomes `mods.with_dependents(mods, base)`, used by both `held_back` and `too_new`. So a mod that needs a too-new mod is left out with "needs Creator palettes, which needs a newer Clan Mod Studio". It doesn't fail the "requirements" check, which `unmet()` would turn into an `InstallBlocked`.
- `pipeline.build` folds both into `left_out`, so these mods are left out with a warning and nothing is refused.

**`pending()` (fixing bug 23).**
- `pending()` returns a new `left_out: {id: why}`, with `gamebuild.held_back` and `too_new` together.
- `off` becomes the mods that were installed and are now switched off; it no longer includes held-back mods.
- A left-out mod that is still in the game (in `installed.mods`) keeps `any` true, since the next install takes it out. The changes banner prints "<name> left out: <why>".

**Where the creator sees it.** GET /mods puts the sentence in `problems`. The add preview shows the line in warning colour before adding (`_found` returns the mod's `wcmods`). UI: the card line and the banner wording only.

**Tests:**
- `test_a_mod_can_say_the_wcmods_it_needs`:
  - a minimum above `__version__` is left out with the sentence, and the build still installs;
  - equal or below passes;
  - `"banana"` is refused by `_check_meta`;
  - a mod requiring a too-new mod is left out, not reported as unmet, and `install()` doesn't raise.
- `test_pending_lists_held_back_mods_as_left_out_not_off`: with `WCMODS_GAME_BUILD=99999999` and an installed record naming an unpinned mod, `left_out` has it with its reason, `off` is empty and `any` is true.

**Docs:**
- docs/SDK.md: the mod folder key list and the paragraph under it.
- docs/formats.md: the mod.json mention.
- docs/updating.md, "For mod makers": the key beside `game_builds`.

**Needs no game.**

### 2. The add-on registry

**Files:**
- wcmods/addons.py (new)
- wcmods/menupages.py, kept as a thin module: `ID`, `NAME`, `note()`, `cheats()`, `cheats_or_none()`, and `add()`, `status()` and `find_release()` delegating to addons
- wcmods/modzip.py (per-mod on/off)
- wcmods/onboarding.py
- wcmods/studio.py
- wcmods/cli.py

**Format.** A table in addons.py, one entry per companion mod:

```python
Addon(id="sandbox", name="Sandbox mode", repo="HexOffender/wcmods-sandbox",
      asset=r"^sandbox-\d[^/\\]*\.zip$",      # not sandbox-story-0.3.zip or sandbox-welcome-0.2.zip
      about="Shows the cats and questlines you make",
      pages=("npcs", "quests"), tool=False, keep=("settings.json",))
```

The other three sit alongside:

| id | asset | pages | tool | keep |
|---|---|---|---|---|
| menu-pages | `^menu-pages[^/\\]*\.zip$`, as today | `()` | True | settings.json |
| creator-palettes | `^creator-palettes-\d[^/\\]*\.zip$` | `("palettes",)` | True | — |
| emote-wheel | `^emote-wheel-\d[^/\\]*\.zip$` | `("animations",)` | True | settings.json, where its key lives |

- The registry carries no version minimum and no "code" flag. Both come from the add-on's own mod.json (step 1's `"wcmods"`, `Mod.has_code()`), so there is one source of truth.

**Reading the add-ons.**
- `addons.status(cfg)` returns, per add-on, `{id, name, about, installed, enabled, version, latest (None until asked), too_new (from step 1), page (the releases URL)}`.
- `addons.find_release(addon)` is `menupages.find_release` generalised: the first asset matching the regex, with the version from the tag. A 404 is already worded by `ue4ss.github_release` ("has no release on GitHub yet").

**`addons.add(cfg, addon_id, zip_path=None, on=None, log)`** adds the add-on:
- **Where the .zip comes from.** It downloads to `<data_dir>/cache/downloads/<asset name>`. The file is kept, so a preview and the add that follows read one file, and older files of that add-on are removed. `ue4ss.download` already takes any asset.
- **What goes in.** It adds through `modzip.add_zip`:
  - every mod in the .zip, each switched on or off as it ships;
  - so Creator palettes comes with Coat presets on and the ten themed palettes off, as its README says.
- **Updates:**
  - a mod already there keeps its own on/off;
  - the files named in `keep` are merged as menupages.add does today (your values over the shipped ones, new keys added).
- **What it returns** is the same dict as menupages.add, with `unchanged` when the release's version equals the installed one.
- **Clearing Not now.** It clears `skip_menu_pages` when it adds Menu pages.

**Per-mod on/off in modzip.** For the shipped states, `modzip.add_zip` and `add_folder` take `enable` as a bool, as today, or as a per-id dict `{id: bool}`, where a missing id keeps the mod's shipped `enabled`. `_needs_on` runs for the ids that go in switched on. Step 4 uses the same dict for the preview.

**Routes:**
- `GET /addons`: the status. `?latest=1` also asks GitHub about each, cached for an hour in memory, so the 60-an-hour unauthenticated limit isn't hit on every focus.
- `POST /addons/<id>/preview`: downloads through `self.run`, so the shell's progress shows it, then runs `modzip.inspect`. It returns exactly what `/mods/add?step=preview` returns, plus `version`, so the page reuses `renderPreview`.
- `POST /addons/<id>`, with `{on?}` or a .zip body: add or update.
- `POST /setup/pages` stays as an alias of `POST /addons/menu-pages`, so nothing else breaks.

**CLI.** `python wcmods.py addons` lists them, and `addons add <id> [--zip file]` adds one. `menu-pages` stays as an alias.

**Tests** in tests/unit/test_addons.py, with `find_release` stubbed as the selftest `_menu_pages` stubs it:
- `test_the_sandbox_release_picks_the_mod_not_the_examples`: three assets; `sandbox-0.4.zip` is chosen.
- `test_creator_palettes_comes_with_coat_presets_on_and_the_themes_off`: a .zip like its pack.py makes.
- `test_an_addon_equal_to_the_installed_version_is_unchanged`: nothing downloaded, no backup made.
- `test_github_trouble_names_the_addon_and_its_page_and_leaves_no_folder`: a 404 from the stubbed `github_release`; no `_adding-*` folder is left.
- `test_a_zip_without_the_addon_is_refused_and_the_old_copy_kept`.
- `test_updating_keeps_off_and_settings`: the Emote wheel's `key` survives an update, and so does `enabled: false`.
- `test_adding_clears_not_now`.
- `test_menu_pages_command_still_works`: the alias.
- `test_add_zip_takes_a_per_mod_on_off`.
- The existing `_menu_pages` selftest keeps passing.

**Docs:**
- docs/formats.md: the wcmods.json table (the cache folder).
- docs/SDK.md: the route list (`/addons`).
- The docs-guide plan's docs/guide/companion-mods.md gets the Add-ons card and what each add-on shows.

**Needs no game.** The real download is a manual check once per repository, once the releases exist (step 9).

### 3. Get set up and the Add-ons card

**Files:**
- studio/sections/mods.js (renderSetup, and a new renderAddons)
- studio/lib/wc.js (`wc.codeWarning()` and an `addonButton(id)` helper)
- studio/lib/story.js (the Add button inside the story plan's `sandboxStrip`)
- studio/sections/palettes.js (the Add button on the palettes-cat plan's Creator palettes line)
- studio/sections/animations.js (one note with the button)
- studio/sections/settings.js (the Options note points at the Add-ons card, not "Get set up")
- wcmods/menupages.py `note()`: the in-game Overview says "the Mods page's add-ons card adds it"
- wcmods/onboarding.py
- wcmods/studio.py

**Format.**
- **The shared config (bug 9).** `onboarding.status()` reads a Config of its own, `Config(cfg.root, cfg.data_dir)`, instead of `cfg.reload()`. Its `game_dir`, `win64_dir` and `save_dir` properties are what status needs, so the studio's shared Config is never swapped. `POST /setup/game` takes the studio lock, as `/setup/pages` skip already does.
- **New fields in `status()`:**
  - `"code": {"ok": allow_code_mods or skip_code}`, with a new wcmods.json key `skip_code: true` for Not now on that step;
  - `"addons": {"ok": setup_addons is set, "missing": [ids]}`, with a new wcmods.json key `setup_addons`: `"added"` once Add all four has run, whatever each one's outcome, or `"not now"`. So an add-on with no release yet can't keep the step open; the Add-ons card shows what didn't arrive.
- **`done`** counts the five steps.
- **A moved game (bug 38).** `/info` reports `game_dir: null` when `is_game_dir` says the folder isn't the game. That disables Play and Apply exactly when Get set up asks where the game is.

**UI** — the steps are the ones "What a creator should be able to do" lists:

- **The scripts step's Allow:**
  - It posts `PATCH /settings {allow_code_mods: true}`, after the same one-time confirmation the Settings page uses.
  - The warning text moves into `wc.codeWarning(mods)`, so the two places say the same thing. It names the mods in the player's folder that run code, with their authors ("Menu pages, by wcmods: the mod menu's pages"). That answers the packs-settings map's high UX issue.
  - If an install already exists, the console-lua plan's step 2 redo makes the top bar ask for an Apply. Until that lands, the toast says "Press Apply to game to put them in".
- **Add all four:**
  - It posts `POST /addons/<id>` for each add-on in turn, showing "Adding Sandbox mode…" per row in the Add-ons card.
  - It then toasts what went in. When code mods are still off, it says the scripts step is next.
- **The Add-ons card** (`renderAddons()`, drawn from `GET /addons`) sits below Add a mod, with a row per add-on and the state chips.
  - Get the latest asks `?latest=1` only when the player presses "Check for newer versions", so a focus never calls GitHub.
  - The Menu pages card's existing Get the latest button becomes the add-on row's.
- **The pages' Add buttons.** The same `addonButton(id)` goes into:
  - the story plan's `sandboxStrip`, wherever it says Sandbox mode is missing or too old;
  - the palettes-cat plan's "needs the Creator palettes mod" line;
  - an Animations page note: "The Emote wheel shows your emotes on a wheel in the game". This one is new.
- **Version words** on Characters and Questlines are the story plan's. This step only puts the button in.

**Tests:**
- tests/studio/e2e/mods.test.mjs, against a studio over a temp data folder with the add-on routes stubbed:
  - `the setup card lists five steps and folds when done`;
  - `Not now on the add-ons step leaves an Add button on each row of the Add-ons card`;
  - `Allow on the scripts step asks once, names the code mods and patches settings`;
  - `a focus doesn't call GitHub; Check for newer versions does`.
- tests/unit:
  - `test_setup_status_counts_the_new_steps`: the code and add-ons steps, the skip keys, `done`;
  - `test_setup_status_does_not_reload_the_shared_config`: set a key on `cfg.data`, call `status()`, and the key is still there;
  - `test_info_says_no_game_for_a_moved_game_folder`.

**Docs:**
- README Getting started, steps 3 and 4: the scripts step and the add-ons step, in the creator's words. Or docs/setup.md, once the docs-guide plan moves them.
- The docs-guide plan's docs/guide/mods.md: what each card is for.
- docs/formats.md: `skip_code`, `setup_addons`.

**Needs the game:**
- Once, by hand: a fresh data folder (`WCMODS_DATA` pointing at an empty folder) walked through all five steps on the dev machine.
- Then `python wcmods.py agent test tests/game/test_menu.py`, to see Menu pages in the game.
- First check who launched the running game, as the shared-game note says.

### 4. Mods page fixes

**Files:**
- studio/sections/mods.js
- wcmods/modzip.py
- wcmods/mods.py
- wcmods/onboarding.py
- wcmods/studio.py

**Search (bug 4).** The search box keeps the raw text in `search` and matches on `search.trim().toLowerCase()`. `renderList` keeps the one input element and redraws only the cards, so the caret stays where it was.

**One way to name a mod (bugs 5 and 6).** One helper, `modzip._identify(meta, base, label, taken)`, is used by `_inspect`, `inspect_folder` and `add_folder`. It:
- validates with `_check_meta`;
- derives the id:
  - mod.json's `id` if it has one;
  - else `base`;
  - when mod.json sits at the zip's top, `base` has a trailing version stripped by `re.sub(r"[\s_-]*v?\d+(\.\d+)*$", "", base)`, kept as it was if that leaves nothing ("2048.zip" stays "2048");
- then applies the `-2` dedupe.

**Mods added before this fix.** When there is no `id` and no folder of the derived id exists, `_found` looks for an installed mod with the same mod.json `name`. If it finds one, it uses that mod's id. So "Cool Mod v1.3.zip" replaces the "cool-mod-v1.2" an older studio made, and the preview says "Replaces the Cool Mod 1.2 you have". This is the migration for mods added before the fix.

**Missing requirements (bugs 3 and 7).**
- When `switch` raises, `_needs_on` turns the new mod off and records `"off_because": "needs Sandbox mode, which you don't have"` on its entry.
- The preview computes `needs` against `r.mods` and installed mods. It names mods from `r.mods` first and says "(in this .zip)" for a pack's own mods.
- It shows step 3's Add button for a missing requirement that is a known add-on. The story plan's `uses_notes` line sits beside it and gets the same button.
- The toast after adding says "Added Moonlit cats, switched off: it needs Sandbox mode. Add it from the add-ons card, then switch it on."

**Shipped on/off (bug 28).** For a .zip holding several mods, the preview shows each mod's shipped state as the default of its own "on" box. The add sends `/mods/add?step=add&ids=a,b&on=a`, where `on` lists the ticked mods that go in switched on, using step 2's per-id `enable`. The single-mod case keeps the one "Switch it on" box.

**Small fixes:**
- **Accents (bug 30).** `safe_id` folds accents through `unicodedata.normalize("NFKD")` first, matching what the harness branch does for `story.js` `slug()`.
- **Problem lines (bug 32).** `unmet()` names mods by their mod.json name, and missing known add-ons by their registry name, without the raw id in brackets. The card capitalises every problem line.
- **Clicking a name (bug 33).** The mod's name becomes plain text, with the switch's `aria-label` carrying the name.
- **Get the latest (bug 34).** Its toast says "It's still off: switch it on, then Apply" when the mod is off.
- **The inbox (bug 31).** `GET /mods/inbox` writes `"shown": true` into the inbox record, and `onboarding.inbox()` doesn't expire a record that has been shown.

**Tests:**
- `test_a_folder_and_a_zip_agree_on_a_mods_id`: a folder "My Story Folder" with `"id": "my-story"`; `inspect_folder` and `add_folder` both say my-story.
- `test_a_version_in_the_zips_name_does_not_become_part_of_the_id`: "Cool Mod v1.2.zip" then "Cool Mod v1.3.zip" give cool-mod twice, the second previewed as replacing the first.
- `test_a_mod_added_by_an_older_studio_is_replaced_by_name`: an installed cool-mod-v1.2 is replaced by "Cool Mod v1.3.zip".
- `test_adding_a_mod_whose_requirement_is_missing_leaves_it_off_and_says_why`.
- `test_a_multi_mod_zip_keeps_each_mods_shipped_state`: creator-palettes stays on and palette-dark-forest off; `on=` overrides.
- `test_safe_id_keeps_accented_letters`.
- `test_a_shown_inbox_entry_does_not_expire`.
- In tests/studio/e2e/mods.test.mjs:
  - `typing Dark Forest keeps the space and the capitals and matches`;
  - `a pack preview does not warn about mods inside the zip`;
  - `the preview's Add sends only ticked ids and each one's on state`;
  - `clicking a mod's name does not toggle it`.

**Docs:**
- README, "Sharing a mod": how a .zip is named, and that a version in the file name is dropped.
- README, "Add a mod": a mod whose requirement is missing is added switched off.

**Needs no game.**

### 5. What reached the game

The pipeline map's confirmed bugs, which no other plan takes.

**Files:**
- wcmods/pipeline.py
- wcmods/gamefiles.py
- wcmods/exe/gamebuild.py
- wcmods/sdk.py
- wcmods/sections/scripts.py
- wcmods/sections/cpp.py
- wcmods/menu.py
- wcmods/studio.py
- wcmods/cli.py
- studio/sections/mods.js

**A forced install (bug 43).**
- A forced `install()` writes the mods named in any section's `failed` entries, and every mod a failed section claimed, into the `installed` record. They go under the `problems` key the console-lua plan's step 4 adds (`{id: [text]}`, here with "Not in the game: <why>"), whichever PR lands second reusing the other's key.
- They stay in `installed.mods`, so `pending()` doesn't nag. A failed mod is seen as `changed` as soon as its files are edited, which is the fix the creator makes.
- GET /mods shows the line on the card in red. The changes banner lists "<name> isn't in the game: <why>".
- `menu.host_script` passes it to the in-game Installed mods page.
- The record is cleared for a mod by the next install that builds it, or when it is turned off.

**The game's files can't be read (bug 44).**
- `build()` opens the game's pakchunk0 .pak and .utoc through `GameFiles` before any section. When they can't be read, it stops with "the game's files can't be read right now (is Steam updating or checking the game?); try again when it's done".
- In `install()`, a section that failed with no mod (a `(None, text)` entry from the shell) is said as "<Section title> couldn't be built: <text>". It gives no "Apply the rest anyway", because forcing would install without wcmods' own shared module.

**A copy that fails (bug 45).**
- Before `remove_paks(dest)`, `install()` checks that every manifest output exists in build/.
- If a copy then fails, it writes `installed["broken"] = str(e)`, and `pending()` says "the last apply didn't finish: apply again".
- `install_outdated()` requires a .utoc and a .ucas beside every `zzz_WCMods_*.pak`.

**Loose ends:**
- **The CLI (bug 46).** `cmd_build` and `cmd_status` drop their trailing `cfg.save()`, or reload and re-apply only `game_dir`.
- **A lock (bug 47).** build, install and uninstall take a lock file `build/.lock`, created with `O_CREAT|O_EXCL` with the pid inside and removed in `finally`. A lock whose pid is gone is taken over. When it is held, the message is "another apply is running (Clan Mod Studio or the command line); wait for it".
- **Pak names (bug 48).** `build()` tracks installed pak names. On a clash it warns "<mod>: paks/<stem> would go in under the same name as <other>'s; left out" and skips it.
- **The other lows (bug 49):**
  - `gamebuild.layout()` caches a failed check with its reason and the wcmods version;
  - `manifest["built"]` is taken at the start of `build()`;
  - `sdk.rollback()` keeps the failing section's warnings, and a section.py that won't load goes into the warnings;
  - `/install` and `cmd_install` check `game_running()` before building;
  - `current()` gains `older` for a build below `VERIFIED_BUILD`, and the chip and status say "an older version of the game" for it;
  - the `now and` guard on the update redo is dropped whenever an install exists;
  - scripts.py and cpp.py say the shell's one sentence: "runs code, so it stays out until you allow mods that run code (Options, on the Settings and repair page)".

**Tests** in tests/unit/test_pipeline.py, with a fake game folder and `WCMODS_FAKE_RUNNING`:
- `test_a_forced_install_marks_the_failed_mod_not_in_the_game`: the card's line, and `pending()` `any` false until the mod is edited.
- `test_an_unreadable_game_stops_the_build_with_one_sentence`.
- `test_a_section_failing_with_no_mod_offers_no_force`.
- `test_a_missing_output_stops_before_anything_is_removed`.
- `test_install_outdated_wants_the_ucas`.
- `test_a_second_apply_waits_for_the_lock`.
- `test_two_paks_with_one_name_warn_and_one_goes_in`.
- `test_built_is_the_time_the_build_started`.
- In tests/unit/test_cli.py: `test_build_and_status_keep_what_the_studio_wrote`.

**Docs:**
- docs/ARCHITECTURE.md, "The build pipeline": install refuses after a failed section, and what forcing leaves out.
- docs/updating.md: when the game's files can't be read, and an older build.
- docs/SDK.md, "New content": pak names fold punctuation.
- README: "Apply the rest anyway", the button's real name, in place of "Install the rest anyway".

**Needs no game.** The manual check: rename the fake game's pakchunk0 in a `WCMODS_DATA` folder and press Apply.

### 6. After a game update: the automatic re-check

**Files:**
- wcmods/exe/gamebuild.py
- wcmods/pipeline.py
- wcmods/studio.py
- wcmods/cli.py
- studio/sections/mods.js
- wcmods/mods.py: `create` is unchanged, so a new mod still lists the build it was made on.

**The policy.** A held-back mod is a candidate for a check against the new game, instead of being held back on trust, when it:
- has no code (`Mod.has_code()` false);
- has no `paks/` or `files/` (cooked content and replaced game files can't be judged by a build);
- is not a pack.

Every other held-back mod is still held back until its maker lists the build, or the player uses it anyway.

**The check** is `gamebuild.recheck(cfg, mods, build_dir, log)`:
- It runs `pipeline.build` into `<build_dir>-check`, never the real build folder.
- The candidates are passed as `trusted=ids` and count as allowed for that run.
- It then reads the manifest:
  - **Passes:** a candidate named in no section's `failed` entry and in no `csv_failures`. Its build is appended to its mod.json `game_builds` through `Mod.update`, with a log line "checked on build N: fine". Its warnings ride along to the card.
  - **Fails:** a candidate that is named stays held back, with the failing sentence.
- When step 5's game-files check stops the build, every candidate gets "couldn't check: the game's files can't be read right now". It stays held back and is tried again next time.

**The record.** The result is written to wcmods.json:

```json
"rechecked": {"build": 26200000, "when": "...",
              "results": {"old-tweaks": "data.json names a value the game no longer has: Run speed",
                          "dark-forest": "ok"}}
```

**When it runs:**
- Not inside GET /mods, which four pages call on every focus and which must not wait minutes on the lock.
- GET /mods returns `"recheck_due": true` when a candidate isn't in `rechecked.results` for the installed build. The Mods page then posts `POST /mods/recheck`, which runs through `self.run` like Apply, with the shell's progress, and shows "Checking your mods on the new version…".
- `python wcmods.py game build` runs it too.

**Bad `game_builds` values (bug 22).** `_builds()` accepts digit strings and whole floats. A `game_builds` that is present but yields nothing becomes a build warning, shown on the card instead of the fallback reason: "mod.json's game_builds should be a list of build numbers like [26184573]".

**UI.**
- **The banner (bug 2).** The update banner draws whenever `left_out` (step 1) is non-empty, on a verified build or not. It reads "N of your mods were checked on the new version and are fine. M couldn't go in: <name>: <reason>".
- **A mod that failed** gets "Turn it off" beside it. It doesn't get a "Works on this version" button: the build has just shown that it fails.
- **Mods with code** keep "Use it anyway…" and its warning, with "its maker has to update it".
- **A checked mod's card** shows a muted "Checked after the game update" line until the next Apply.

**Tests** in tests/unit/test_gamebuild.py:
- `test_builds_accepts_strings_and_whole_floats_and_warns_on_an_empty_list`.
- `test_a_data_mod_that_still_builds_is_stamped_with_the_new_build`: a palette mod, a newer `WCMODS_GAME_BUILD`, and `fake_game` with the small palette fixtures the palettes tests use. After `recheck`, its mod.json lists both builds and it is no longer held back.
- `test_a_data_mod_whose_file_fails_stays_held_back_with_the_reason`: a data.json naming a missing table.
- `test_a_code_mod_and_a_paks_mod_are_never_checked`.
- `test_no_readable_game_means_couldnt_check_and_a_retry_next_time`.
- `test_recheck_runs_once_per_build_and_again_for_a_new_candidate`.
- `test_get_mods_never_builds` (it only says `recheck_due`).

In tests/studio/e2e/mods.test.mjs:
- `the update banner shows on the verified build when a mod is left out`;
- `a recheck_due page starts the check once and shows its progress`.

**Docs:**
- docs/updating.md, "For players": what is checked automatically, and that code mods wait for their maker.
- docs/updating.md, "For mod makers": strings are accepted; a data mod is re-checked, so listing builds is a courtesy.
- docs/formats.md: `rechecked`.
- README step 4: the examples will be checked, not refused.

**Needs the game:**
- On the dev machine, `WCMODS_GAME_BUILD=99999999 python wcmods.py studio` with the real mods folder. Watch the Mods page run the check and stamp the palettes, then press Play.
- On the next real Steam update, `python wcmods.py agent test tests/game/test_menu.py` after the check, reading the Overview page's list of installed mods.

### 7. Mod packs

**Files:**
- wcmods/packs.py
- wcmods/modzip.py
- wcmods/studio.py
- studio/sections/packs.js

**A removed pack (bug 12).**
- `describe()` reports `playing` from `pack_before` even when the pack's folder is gone. The banner then reads "Playing The Moonlit Path, which was removed", with Back to my mods.
- `stop()` works with the pack missing.
- The `/mods/<id>/remove` route calls `packs.stop(cfg, found)` first when the id is `pack_before["pack"]`.

**What stays on (bug 29).** `KEPT` becomes the registry's add-ons with `tool=True`, plus any mod whose mod.json says `"tool": true`. That is a new optional key, for mods that are the player's own tools rather than a pack's choice. `play()` also keeps the mods a pack's mods `use`, the story plan's step 2 change, so the two land together.

**Problems per pack (bug 20).** `describe()` adds per-pack `problems`: mods that run code while code mods are off, and mods left out (step 1's `left_out`), each with the sentence to show. The card lists them under the chips, and the Play only this pack toast says them.

**The pack form:**
- **Missing mods (bug 13).** Change it seeds `chosen` from present direct mods only. It lists the missing ones as "not in your mods: dropped from the pack when you save".
- **Typed text (bug 35).** The form keeps its typed values across `mods-changed` by reading the inputs before redrawing.
- **The label (bug 39).** The "On with my mods" button is hidden while the pack plays on its own.
- **Pre-ticking.** The form pre-ticks no `tool` add-on, since tools stay on anyway.

**Packs made from My mods (bug 14).** `modzip.pack()` renames the content mods that use the studio's default id, inside the .zip only:
- `my-mods` becomes `<pack-id>-mods`, with the name "<Pack name>: its own content";
- every zipped mod.json's `requires` and `uses` naming it are rewritten;
- the creator's own folders are untouched.

**The recipient's side.**
- `_found` compares a hash of the file names and sizes of an existing mod with the zip's, and marks `"different": true`.
- The preview says "You have a different mod with this name; tick to use the pack's copy (yours is kept in backups)".
- It ticks the copy by default only when the zip's version is newer, or neither copy has a version.
- A registry add-on is never ticked when the recipient's copy is the same or newer. The preview says "You have Sandbox mode 0.5; the pack carries 0.4: keeping yours", so a pack never downgrades an add-on.

**Tests** in a new tests/unit/test_packs.py:
- `test_removing_the_playing_pack_restores_the_players_mods`.
- `test_back_to_my_mods_works_when_the_pack_is_gone`.
- `test_tools_stay_on_when_a_pack_plays`: creator-palettes, and a mod with `"tool": true`, stay on.
- `test_a_pack_with_a_missing_mod_can_be_saved_from_the_page`: POST /packs with the present mods only.
- `test_a_packs_zip_renames_my_mods_and_rewrites_requires`: the zip holds `<pack>-mods/`, the pack's mod.json requires it, and add_zip on a fresh folder adds both.
- `test_the_preview_marks_a_different_mod_with_the_same_id`.
- `test_a_pack_never_downgrades_an_addon`.
- `test_describe_lists_a_packs_problems`.
- In tests/studio/e2e/packs.test.mjs:
  - `the pack form keeps typed text across a redraw`;
  - `Change it with a missing mod lists it as dropped`.

**Docs:**
- README, "Mod packs": what Play only this pack keeps on, that removing the played pack goes back to your mods, and that a story pack needs code mods allowed.
- docs/formats.md, "Mod packs": `tool`, and the zip's renaming.
- docs/SDK.md: `tool` in the key list.

**Needs no game.**

### 8. Settings and repair, and crashes

**Files:**
- wcmods/studio.py
- wcmods/formats/save.py
- wcmods/crashes.py
- wcmods/menusettings.py
- studio/sections/settings.js
- studio/sections/mods.js

**Allowing code (bug 11).**
- The Apply prompt is the console-lua plan's step 2. The no-reload is the shell's (bug 15).
- This step changes the Settings toast to "Allowed. Press Apply to game (top right) to put them in". It shows the same `wc.codeWarning(mods)` as step 3.

**Restoring a backup (bug 16).**
- The restore toast says "Put your save back as it was. The one you had is in <before-restore name>. The next Apply puts your mods' save changes back; to keep them out, turn those mods off first."
- There is no pending redo. Restoring is how a player undoes save edits, and a redo would make Play put them straight back.
- The data-save plan's step 6 makes "the next Apply" true under once-per-save edits.
- The backups list shows each name in words, for example "Today 15:30, before Apply (save edits)" or "First safety copy", from the stamp and the reason.

**Backups (bugs 17 and 36).**
- The tests branch already refuses a backup without a save in the route. `save.backup()` makes the same check, so `apply_save_ops` and the CLI can't leave an empty folder either.
- The page disables Back up now while `/info` says there is no save, with the reason.
- `restore()` refuses a name not in `list_backups()`.
- `/backup` and `/restore` run under the studio lock.

**Take all mods out (bug 18).** A sentence goes beside the button: "To play without mods, start the game from Steam; Play here puts your mods back in." The names plan adds which cats will show as missing text.

**The Options (bugs 40 to 42):**
- `/ingame` returns why the console is unavailable ("no script loader" or "no console mod in it"), and the page says it.
- `set_options` accepts any pad that `menu_settings`' `pad_ok` accepts, and the page labels an unknown one with `wc.input.keyLabel`.
- Make your own mod asks only for a Name. The id comes from `modzip.safe_id` and is shown under the box.

**Crash reports (bug 37).**
- `crashes.readout` decodes by BOM (utf-16, utf-8-sig, else cp1252), and catches ParseError with "the crash report couldn't be read".
- A new `GET /crash` returns the newest crash newer than `installed.built`, from `crashes.latest(after=...)`, with `readout`'s blame for a C++ mod. When the console-lua plan's step 5 has landed, it adds the script errors `scriptlog.report` found in that session, rather than reading UE4SS.log a second way.
- The Settings page draws "The game crashed last time" at the top of Backups and repair. It shows:
  - when;
  - the message;
  - "it was in <mod>", when a C++ frame or a script error says so;
  - "Copy the report" (the readout text to the clipboard);
  - "Turn <mod> off".
- The Mods page shows the same card once, until dismissed. The dismissal is kept in `localStorage`, as a per-viewer convenience.

**Tests** in tests/unit/test_settings.py:
- `test_a_restore_says_where_the_old_save_went_and_asks_for_nothing`: `pending()` is unchanged.
- `test_backup_without_a_save_leaves_no_folder_from_any_caller`.
- `test_restore_refuses_a_name_outside_the_backups`.
- `test_console_unavailable_says_why`.
- `test_a_hand_set_pad_can_be_chosen_again`.
- `test_make_your_own_mod_takes_a_name`.

In tests/unit/test_crashes.py, with `crashes.crashes_dir` pointed at a fixture folder:
- `test_a_utf16_crash_report_is_read`;
- `test_latest_after_a_time`;
- `test_crash_route_is_empty_without_a_crash`;
- `test_a_cpp_frame_names_the_mod`.

In tests/studio/e2e/settings.test.mjs:
- `Back up now is disabled without a save`;
- `the crash card offers Turn it off and Copy the report`.

**Docs:**
- README, Settings and repair bullet: restore and Apply, what Take all mods out leaves, where a crash shows.
- The docs-guide plan's docs/guide/settings.md: the help panel.
- docs/SDK.md, route list: `/crash`.

**Needs the game for the crash card.**
- A real CrashContext.runtime-xml from %LOCALAPPDATA%\Wrc\Saved\Crashes (the 2026-10-24 null-object crashes left some, if they are still there) is copied into the test fixtures.
- On the dev machine, one deliberate crash, after checking who launched the running game: a nil-object call from the Console page on the test cat, which reverse-engineering.md says crashes the game. Then open Settings and repair.
- Whether the `debug_crash` cheat can be fired, and what a Lua-side crash leaves, stays the packs-settings map's RE gap. It is not used here.

### 9. Companion repositories, outside this repository

These are done beside this plan.

**Sandbox mode.** The 0.5 release, the progress fix and the format check are the story plan's step 1. Its PR also adds the low `sandbox_api.lua` guard ("if not Game then print(...) return end").

**Release order.** Release wcmods 0.4.0 first: bump `__version__` in a PR, then publish on its merge, as the release notes say. Then release Creator palettes 1.2.0 and Emote wheel 1.0, following their READMEs' Releasing steps. On wcmods 0.3.0 the Coat presets palette stops every Apply, and 0.3.0 ignores the `"wcmods"` key, so Creator palettes must not reach players first.

**Add `"wcmods"` to each mod.json:**

| mod | "wcmods" | why |
|---|---|---|
| menu-pages | "0.2.0" | works from 0.2.0 |
| sandbox | "0.3.0" | Fixed looks also need wcmods 0.4.0, since `Game.npcs.spawn` took `look` and `slots` after v0.3.0; the story plan's strip says so |
| emote-wheel | "0.3.0" | its description says 0.3.0 or newer |
| creator-palettes | "0.2.0" | its own script needs no more |
| palette-coat-presets | "0.4.0" | the one that fails on 0.3.0 |

**wcmods-examples:**
- add `game_builds` to every one of the 25 mod.json files;
- regenerate the palettes with this repository's tools/make_palettes.py (on the claude/palette-builds branch, which already writes `game_builds`), so they carry the new slots;
- fix the stale README lines.

**Emote wheel:**
- Change its default key to one the game sends no command for, from reverse-engineering.md's key table, for example B. The owner picks it.
- Fix its README and description.
- List its keys through `Game.onKey`, so the Overview shows them (low).

Until those releases exist, the Add-ons rows for Emote wheel and Creator palettes say "No release yet". That comes from the 404, which `ue4ss.github_release` already words.

## Old mods and old files

Every format change here is optional to read and safe for what exists.

- **New mod.json keys.** `"wcmods"` and `"tool"` are optional. Older wcmods ignore them: the minimum only protects from 0.4.0 on, which is why step 9 orders the releases.
- **`game_builds`.** It is more lenient: strings and whole floats now count. A stamp from the re-check only appends a build, which every version reads.
- **Ids from .zip names.** A .zip with mod.json at its top now drops the version from its id. A mod added that way by an older studio is matched by name and replaced, not doubled.
- **Pack .zips.** Only new ones are renamed inside. An old pack .zip adds as before, and the "different mod" mark covers its my-mods.
- **wcmods.json.** The new keys (`skip_code`, `setup_addons`, `rechecked`, `installed.problems` entries, `installed.broken`) are absent in old files and read as "not set". `skip_menu_pages` is still read, and adding Menu pages clears it.
- **Routes.** `/setup/pages` and `wcmods menu-pages` keep working as aliases. The single `enable` of `/mods/add` still works beside the new `on=`.

## Not in this plan

- **Mods switched on and off from inside the game's own menus:** known-impossible. A pak can't be swapped while the game runs, and the game has no mod support of its own.
- **Steam Workshop sharing:** known-impossible. The game exposes no Workshop.
- **New coat or eye colour slots as real slots:** known-impossible. A coat slot past 24 crashes the game, and the eye atlas has fixed rows; presets are the way.
- **Mods that stay in the game across Steam updates without re-applying:** known-impossible. wcmods' in-game module must be rebuilt for the new build.
- **Applying mods while the game runs:** needs-re. The paks are locked, and hot-reloading wcmods' scripts hasn't been tried.
- **Refusing to apply while Steam is updating the game:** needs-re. The appmanifest's StateFlags during an update haven't been observed. Step 5's check of the game's files is the stand-in.
- **A direct "the game mounted wcmods' pak" signal for a "did it work" line:** needs-re. The only tell today is the names table. The console-lua plan's per-script "Loaded last time" and step 5's "Not in the game" cover what can be known now.
- **Pinning a known-good UE4SS:** needs-re. Whether the DRM'd exe runs every UE4SS experimental build is unknown, and each new experimental tag has to be tried in a scratch copy of the game.
- **Save-file features:** needs-re, because the save's checksum and the ForcedRank switch are unconfirmed:
  - a starting rank for sandbox cats;
  - a fresh save slot for a story pack;
  - restoring one cat's slot;
  - Steam Cloud's handling of edited or restored saves.
- **A mouse in the cat maker's colour picker for Creator palettes:** needs-re. How WBP_GuiColorGridItem takes hover and clicks is unknown.
- **A per-mod "allow this mod's code" instead of the one switch:** known-possible but deferred. It touches the three gates and the console, and deserves its own design once the setup step exists.
- **"Get the example mods" with one click:** a download of wcmods-examples' main .zip into the same preview. Known-possible, but deferred until step 9 gives the examples `game_builds` and the new slots; today it would add 25 left-out mods.
- **A "kept out" state after Take all mods out**, where the chip says "Mods taken out" and Play just starts the game: known-possible, but it changes what Play means. The plan does the sentence only; see Open questions.

## Open questions

1. Should the re-check stamp a downloaded data mod's mod.json with the new build, or keep the result only in wcmods.json? Stamping is simpler and survives a reinstall of the studio, but it edits a file the mod's author wrote.
2. Should "Add all four" add all four, or only Menu pages and Sandbox mode (the two that pages depend on), leaving Creator palettes and the Emote wheel to their rows on the Add-ons card?
3. Is "Let mods run their own scripts" the right name for the allow-code step? Should Not now on it be offered at all, given every add-on needs it?
4. Does the owner want a "Mods taken out" state (a chip, and Play that just starts the game), or only the sentence beside Take all mods out, which is what the plan does?
5. The companion releases: who runs tools/pack.py and tags v1.0 and v1.2.0, and when, given that Creator palettes 1.2.0 has to wait for wcmods 0.4.0? The Add-ons card says "No release yet" for those two until then.
6. The `tool` key: a mod.json flag, or a list in the registry only? The flag lets other authors mark their tools. The registry needs no release and no new format.
7. Should `GET /addons?latest=1` call GitHub unauthenticated only on a button press, or also once a day on open? Sixty calls an hour is the limit for everyone behind one address.
