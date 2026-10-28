# Reverse-engineering roadmap for creator features

A ranked research plan, not a code plan: which gaps in what we know about the game are worth closing next, how to close each one (on the exe, on the extracted tables and the class dump, or in the running game through the bridge), what each answer unlocks in Clan Mod Studio, and how we would know it worked. Nothing in this plan was run against the game or the exe while writing it. Every "known" below says where it comes from: the notes, the tables under `vanilla/`, the class dump `vanilla/sdk/api-index.txt`, or an in-game check recorded in `docs/verified.md`. The review of this plan read the extracted tables and the dump again, read-only, and corrected the facts that did not match them (see "Changes from the review").

Three branches already under way are referred to, not planned again: the test harness (`claude/studio-tests`: `tests/unit/conftest.py` fixtures that call `Studio.api` over temp folders, an HTTP handler test, the Chromium driver `tests/studio/lib/browser.mjs`, `node:test` units for `studio/lib`, CI with Node), the look (`claude/studio-look`: Leaf and Bark, `studio/sections/<page>.css`, `wc.pageHead`), and the shell (`claude/studio-shell`: save-time checks through `collect()`, the dirty guard, the plain-words Apply summary, errors reworded for creators, help panels from `docs/guide/<page>.md`). Five sibling plans own pieces this roadmap touches, and each step names the one it builds on:
- data-save: the Game data page and the table check in game;
- names: `place_names` and the Lines card;
- console-lua: the runtime fixes in `game.lua`;
- story: the `gives` rewards and the dialogue answer buttons;
- docs-guide: the creator guide pages.

## What it is for

A creator wants to change three kinds of thing without code:
- what the game says (a cat's line);
- what it plays (the camp music);
- what it does (how fast they run, how a cat feels about them).

They also want to be sure the change reached the game. This plan picks the ten questions about the game whose answers let the studio offer those changes as cards with plain labels, or tell the creator honestly that a number does nothing. It ranks them by how much they give a creator for the work they take, and says how to answer each one.

## Where it stands

**What works, and how it was verified.**
- **Text edits reach the game.** The names rename writes new `STR_CAT_NAME_*` rows into `Strings_EN.csv` in the mod pak, and the cat's new name shows on the HUD (`docs/verified.md`, 2026-10-25). A pak alone is ignored: it needs a container beside it (`.utoc`/`.ucas`), fixed in #65. `names.json` `text` sets any key the same way (`docs/formats.md`, "names"), so a dialogue line is a key away.
- **wcmods' hidden members survived patch 1.1.** These are the native members listed in `wcmods/game.py` `HIDDEN`: health, stamina, level, stats, fresh-kill, the clock, fight stats, statuses and senses.
  - `python wcmods.py game signatures check` found every signed class again.
  - The level component was read by hand in game at its old offsets (`docs/reverse-engineering.md`, "Game updates").
- **Cooked DataTables round-trip.** `wcmods/formats/cooked.py` reads and rewrites them byte for byte (`DT_QuestObjectsInfo`, 412 rows, in the selftest).
- **New texture packages load from a soft path.** An item's icon and a worn collar were seen in game.
- **The game's own place names reach the mod menu.** Area names and quest titles come out of `LocationsData.csv` and `QuestDialogues.csv` through `world.place_names` into `WCModsNames`.
- **Tools for running Lua in the game.** The bridge (`wcmods lua`, `inspect`, `find`) and the agent controller (`docs/agent.md`) run Lua in the game and drive it for the tests under `tests/game/`.
- **"Is X reflected" without the game.** The class dump under `vanilla/sdk/` answers it.

**New facts from this audit** (from the tables and the dump, not run).

*Sounds.* `AudioEvents.csv` has 390 rows:
- 38 music (`Music`, `MS_mus_*`);
- 90 effects (`SoundFx`);
- 20 menu sounds (`SoundUI`);
- 242 `VoiceOver`: 41 cat voices (`vo_cat1_angry1`, `vo_dialog_sad`, and so on, the mood sounds a talking cat makes) and 201 narrator lines of the cutscenes (`STR_Script_*_Narrator_*`).

The table and the code around it:
- **Columns.** `---, IdName, AudioEvent, GroupId, AudioType`. The first column, the row key that `data.json` edits match, is a number from 1 to 390 (`cat_step` is row 78, `mus_camp` row 16). The other four are exactly the fields of `FSwtAudioDataStruct`, a table row struct in the `SwtNativeAudio` module.
- **The manager.** The game instance's `NativeAudioManager` is typed `USwtAudioManager`. `UWrcAudioManager` (a `USwtNativeAudioManager`) adds `AudioEventsInfo`, a map from id to soft sound path. `USwtNativeAudioManager` also keeps `AudioEventsMap` (id to loaded sound) and `PathToSoundCues`, a folder.
- **Playing by id.** `K2_PlayEventOf("cat_step", ...)` plays by id. Animations carry an `AnimNotify_PlayNativeAudioEvent.AudioEventId`. The dialogue tables' `VoiceOver` column names the `vo_dialog_*` ids.

*Sky.* `AWrcSkyboxActor` (the world's `BP_DayNightSky_C`) holds `SkyParamsDB`, a DataTable, presumably of `FWrcSkyBoxStruct` rows: sun, skylight, fog, clouds, horizon and stars, as floats and `FLinearColor`s.
- It switches presets named by `ESkyboxPostProcessEnum` (None 0, NeutralDay 1, CinematicNight 2, CinematicNightMoonPool 3, Night 4, ThunderClan, RiverClan, ShadowClan, WindClan, MoonPool, ...) with `StartTransition(pp)` and `ApplyStraight(pp)`.
- It switches by zone (`DoZoneDetectionFunction`) and on `OnCombat`, `OnEnterInventory` and `OnHousing`.
- There is no weather or season class anywhere.

*Dialogue.* Conversations are `UQuestDialogue` graphs of two kinds of node:
- `UQuestDialogueTalkingNode`: a `Paragraph` FText, a `TalkingSource` and a `VOEvent` id;
- bonding nodes.

They are reached by tag through `USwtQuestSequencerManager.PlaySequenceDialogue(tag, npc, player, bAddPlayerClanTypeLeafTag, bAddPlayerCharacterRankLeafTag)` and the table `DialoguesToUse`. Its rows are `FQuestDialoguesDatatable`: a quest tag and, per clan and rank, a graph. The two dialogue tables carry, per node tag: `Score`, `ClanBonding`, `Talker`, `Trait`, `VoiceOver`, `StringKey` and a `DebugText` copy of the English words.

*Bonds.* The bonds list is `mcGuiBondsList` (a `UGuiListCatsBonds`) on `UGuiPausePanelBonds`, the pause menu's Bonds panel.

*Save.* `USwtSaveGame.Hash` is a reflected `uint64`. The save manager reflects `Get/SetMoodData`, `Get/SetGameProgressionData`, `SetStateJsonDataFromString`, `SaveCurrency` and `TemporaryDisableSave`.

*Tuning.* `USwtTuningManager` and its subclasses reflect no functions at all, so Blueprints most likely can't read `TuningData` by key, and the reads are in the exe.

**Half-finished.**
- **Level component signatures.** Its eight members have no signature sites (`signatures.json` line 109, `"sites": []`), and `make()` only logs "none for ..." when that happens (lines 517 to 518).
- **Dialogue lines.** `names.json` `text` can rewrite any line, but no page shows or edits it. The keys are only found by reading `QuestDialogues.csv` and `StoryDialogues.csv` by hand. The names plan's step 8 builds that card.
- **Sounds** have no page, no doc and no in-game check.
- **Events and calls nobody has tried.**
  - Five script events (`questStatus`, `genericEvent`, `damage`, `turnEnded`, `status`) are hooked but have never been seen firing.
  - `Game.quests.start/give` has never been tried.
  - `Game.save.progression` exists, but its keys aren't known.
- **The dialogue box's other parts.** Its own answer buttons, badge and reward parts are collapsed and untried.
- **Stale open questions in the RE doc.** The list still carries questions that later sections answer (accessory variations, filler name IDs), and misses the ones found here.
- **No cooked content from an Unreal project has been loaded yet.** Every "needs Unreal" idea rests on that untried path.
- **No unit tests.** Nothing under `tools/re/`, `wcmods/exe/signatures.py`, `gamebuild.layout()` or `world.place_names()` has one.

**Confirmed bugs.** These are the skeptic's verdicts in `_verdicts_all.json`. Refuted claims are left out, the skeptic's correction is used where there was one, and each bug says which plan fixes it.

1. **The level component has no sites** (`wcmods/exe/signatures.json:109`, medium).
   - On any exe other than build 26184573, `signatures.check()` marks all eight members lost and `gamebuild.layout()` reports partial.
   - `game.hidden()` then drops the class, and `Cat:level()`, `xp()`, `xpNeeded()`, `stats()`, `setLevel()` and `setStat()` return nil in game, even when nothing moved.
   - The Mods page and the Apply log name the lost values by their C++ class.
   - Fixed by step 4.
2. **Quest titles with no rank are filed under the wrong quest** (`wcmods/world.py:59`, low; the audit said medium).
   - `place_names()` splits every `.Title` tag on its last dot as `<quest>.<Rank>.Title`.
   - The 25 of 72 title rows with no rank segment (Progression RankUp/RankUp2/RankUp3, Sleep Rest1 to Rest13, the SideQuest ones) end up under a truncated quest.
   - So the mod menu's Quests and Cat pages label those quests from their graph id ("Rank Up", "Rest1") instead of the game's titles. Nothing is overwritten, as the audit had claimed.
   - Fixed by the names plan's step 7, not here.
3. **The Interact command is a hard-coded number** (`wcmods/lua/game.lua:1811`, low; the audit said medium).
   - `INTERACT_COMMAND = 67` is a constant, where `remap.lua` reads `/Script/SwtEngine.ECommands`.
   - A future change to that enum would draw the wrong key picture on every studio cat's Talk prompt. The prompt itself keeps working, because its key comes from WCModsRemap or the save.
   - `Game.enums` (lines 1044 to 1064) carries the same risk.
   - Fixed by step 6.
4. **Another cat's level reads and writes yours** (`wcmods/lua/game.lua:1132`; medium in the runtime verdict, low in the RE verdict).
   - `Cat:component("Level")` falls back to the player's PlayerState for any cat without one, which is every clan cat and animal.
   - So `Game.cat(npcActor):level()`, `xp()` and `stats()` answer with your cat's numbers, and `setLevel()` and `setStat()` change your cat, silently.
   - Only scripts that call these on another cat are affected.
   - Fixed by the console-lua plan's step 1. The story plan's step 7 lists the same fix; one PR should carry it, and this plan adds nothing.
5. **memscan misses patterns next to unreadable memory** (`tools/re/memscan.py:69`, low; the audit said medium).
   - `scan()` reads each chunk as `n + 64` bytes. When that crosses unmapped memory, `ReadProcessMemory` reports a partial copy that `read()` throws away.
   - So 79 of 81 such regions in a test process were searched against an empty buffer.
   - Maintainer-only, but it makes the notes' "no more hits" conclusions untrustworthy. Fixed by step 5.
6. **The Nearby page can show the wrong name** (`wcmods/lua/world.lua:258`, low, unchecked). `World.label` caches a label per actor address (the cache is at line 250) and never clears it, so a pickup slot reused by another item keeps the previous name. Fixed by step 5.
7. **xrefs' whole-string filter is off** (`tools/re/xrefs.py:43`, low, unchecked).
   - The filter is disabled by `or True`, so a search for "Turn" also reports the tail of `TurnBasedCombatComponent`.
   - The regex matches only `lea`, never the `mov` its docstring promises.
   - Fixed by step 5.

The Game data page's own defects are in the data-save plan: the `"-"`/`"+"` corruption, the multiplier order, the Escape commit and the unknown-table drop. The runtime's are in the console-lua plan: the per-frame error log, `onKey` and the dialogue claim. This plan touches the Game data page only to add what steps 1 and 3 find, after the data-save plan's page work.

## What a creator should be able to do

The findings land as cards on pages that exist, in the creator's words, and as fewer hedges on the cards other plans build.

**On Names**, the names plan's step 8 builds "Lines the cats say": search a line by its words, see who says it, rewrite it. This plan's step 2 says whether the talk shows the rewrite, so the card can say "seen in a talk" instead of "may".

**On Game data**, a card **Sounds and music**, in three folds:
- **Music:** 38 tunes by plain name ("Camp music", "ThunderClan territory", "Fight music", "Quest done").
- **Sounds:** 90 effects and 20 menu sounds ("Paw steps", "Cat hiss", "Menu select").
- **Cat voices:** 41 mood sounds a talking cat makes ("A cat talking, sad").

Each row has three controls:
- "Plays: [the same]", a list of the game's sounds of the same kind;
- **Mute**;
- **Put it back**.

The page can't play the game's sounds, so the card says "you'll hear it in the game". Behind it is a `data.json` edit of `AudioEvents.csv`, nothing new in the format.

On TuningData's rows in All tables (the data-save plan's grid), a row whose key the game's code never names gets one muted line: "The game's code doesn't name this one (checked on build 26184573), so changing it may do nothing."

Later, if step 7 says yes, a card **Sky** offers a handful of looks: "Always night", "Dusk", "Foggy", "Clear".

**On Mods**, after a game update, a sentence a creator can act on: "The game updated. Your cat's level and stats in the mod menu are off until wcmods updates; everything else works." With the level component signed, there is usually no sentence at all. In the mod menu, the Overview shows the same one line while values are off, and the Quests page shows "The Proving Grounds" where it shows "Rank Up" today (the names plan's step 7).

**On Questlines** (the story plan's page), once steps 8 and 9 answer: a reward "Bond with Brightheart +10", which extends the story plan's `gives`, and a step "Play the story conversation ...".

**What you can and can't do.** The docs-guide plan's guide pages have a "What you can and can't do" section. They quote this plan's "Not in this plan" list, so a creator who asks for weather, a new kind of prey or their own voice gets a plain no with the reason. When a step here changes an answer (sounds, lines, sky), its PR changes that guide line.

**The five-minute first try** (after step 3):
1. Open Game data and go to Sounds and music.
2. Under Music, set Camp music to play Fight music.
3. Save to mod, then Apply to game.
4. Play and walk into camp.
5. Back in the studio, set Paw steps to play Cat hiss, Apply, and walk.

## The plan

**How the procedures run.**

*Static work* uses:
- the installed exe (`<game>\Wrc\Binaries\Win64\Wrc-Win64-ShippingDRM.exe`, which `wcmods.exe.pe.game_exe(cfg)` finds);
- the tables extracted under `vanilla/Wrc/Content/Gameplay/` (`python wcmods.py extract "<pattern>"` for more);
- the class dump `vanilla/sdk/api-index.txt`: one line per class, property and function, with each module's `enum E...` lines at the end of its block;
- the scripts under `tools/re/`, as their docstrings say.

*In-game work* follows these rules:
- **Code mods must be allowed.** `agent install --with <mod folder>` makes a test build with the bridge.
- **One read at a time.** One Lua read through `python wcmods.py lua "<code>"` or `inspect`. Read one object by class or path (`Game.find`, `StaticFindObject`), or a small `KismetSystemLibrary:SphereOverlapActors` at a known spot.
- **No scans.** No `FindAllOf`, `Game.findAll` or `wcmods find` scans. `find` is a `Game.findAll`, and such scans crashed the game three times on 2026-10-25.
- **Back up first.** `python wcmods.py backup` (the test runner does it).
- **Check who owns the game.** No other session may own the running game: check `agent status` and the UE4SS log's start time first.
- **Pick the cat by hand.** `agent launch --world --cat N` presses the slot's button but plays the last-played cat (the project's notes, 2026-10-27). So a test picks its cat on the choice screen with `OnListenCommand` (4 Left, 26 Confirm) and reads `mcGuiNameCat` before confirming.
- **Keep the game in front.** It barely ticks behind other windows, so bring it to the front (`agent hotkey --focus`, or the agent's `bring_to_front`) before waiting on anything in the world.
- **The save is a test save.** The dev machine's save is not the user's. The test cat is Fawnstar ("Cat 1" in the dev save), and slot 4 is a Sandbox mode cat with no HUD.

Agent tests are run as `python wcmods.py agent test tests/game/<file>.py -k <name>`.

**The ranking** is creator value over effort:
- **Steps 1 to 3** each take an evening and decide whether a page tells the truth: the Game data page's numbers (with the data-save plan's check), the names plan's Lines card, and a new Sounds card.
- **Steps 4 to 6** are robustness for everything the mod menu shows, and for the tools the rest relies on. Step 1's static part needs step 5's xrefs fix, so in practice 5 goes first.
- **Steps 7 to 9** are the bigger unknowns, whose answers decide whether a feature exists at all.
- **Step 10** is cheap insurance.

### 1. Table edits in play, and which tuning values the game reads

**Owned by the data-save plan.** Whether a table edit changes gameplay at all (`docs/verified.md:237`, "Game data tables in play") is settled by that plan's game-verification PR, `tests/game/test_data.py::test_walk_and_run_speed_from_the_table`:
- It installs a temp mod (walk 700, run 800, as wcmods-examples' `faster-run`).
- It reads `MaxWalkSpeed` on the cat's movement component in one object read.
- It moves verified.md's line to Confirmed and gives the Quick changes card its "Checked in game" line.

Fight XP is a manual check there, because finding an animal needs a scan. This plan doesn't repeat any of that. Step 3 adds its check to the file and temp-mod pattern that PR creates.

**The gap this plan takes.** Which of TuningData's 441 keys the game's code reads. The data-save plan lists a "read by the game" column as needing RE. About half the keys aren't in the exe as whole strings:
- some are built at runtime (`Gameplay.Exploration.Level.<n>`);
- some may be read by nothing.

The dump reflects no tuning getter, so the exe is where the reads are.

**Static** (no game; after step 5's xrefs fix, which makes whole-string matches honest). `tools/re/tuning_read.py <exe> <TuningData.csv>` runs the xrefs search (made importable by step 5) for every key and sorts each into one of three groups:
- **read:** a `lea`/`mov` points at the key;
- **built from a pattern:** for the rest, one of the key's dotted prefixes is referenced from code as a string (`Gameplay.Exploration.Level.`, `Gameplay.Combat.MaxBaseGrowth.`);
- **not named in the code:** everything else.

It writes `wcmods/exe/tuning_read.json`: `{"made_on": 26184573, "read": [...], "pattern": {"<key>": "<prefix>"}, "not_named": [...]}`. Spot check: every key `docs/mechanics/` says the code loads comes out "read" or "pattern". That covers the movement loader at `0x14179F650` on the first release, and `MaxBaseGrowth.*` in the stat builder.

**In game** (optional, one read). Run `wcmods inspect "Game.manager('tuning')"` once to record whether the loaded values are reflected at all. The dump says no.

**What it unlocks.** The muted "doesn't name this one" line on TuningData rows in All tables. The data-save plan's Quick changes then keep to "read" rows. No new format.

**Verified by:**
- `tests/unit/test_re_tools.py`, on the tiny synthetic PE from step 5: `test_tuning_read_marks_a_key_the_code_names`, `test_tuning_read_marks_a_key_built_from_a_prefix`, `test_tuning_read_leaves_an_unnamed_key`;
- `tests/unit/test_mods.py::test_tuning_route_says_which_keys_the_code_never_names`: the route over a fake game with a three-row TuningData.

**Then, in the code.**
- `GET /api/game/data/TuningData.csv` (`studio.py` lines 445 to 448, which the data-save plan's step 3 extends) adds `not_named` from the JSON.
- `studio/sections/data.js` draws the line beside the row, next to the data-save plan's per-row notes.
- Docs: `docs/reverse-engineering.md` "How we find things" (the script), and the Game data guide page's "Did it reach the game?" (`docs/guide/data.md`, the docs-guide plan's page).

### 2. A dialogue line edited in Strings_EN shows in a talk

**The gap.** Names are verified, dialogue is not. A talking node's `Paragraph` is an FText. One cooked as a string-table entry (history type 11, a table name plus a key) resolves through the same table the names use. One cooked as base text (type 0, the words inline) would ignore the CSV. The names plan's step 8 builds the Lines card (`GET /names/lines`, the search, the placeholder check) and lists a manual game check. This step is the research under it: the static answer and an automated agent test.

**Static.**
1. Find the dialogue table and one graph: `python wcmods.py files "*Dialogue*"`. The sequencer manager's `DialoguesToUse` is a DataTable of `FQuestDialoguesDatatable` rows; `python wcmods.py extract` that table and the first graph package it names.
2. Cheap check first: search the graph's bytes for one of its lines' English words (UTF-8 and UTF-16), and for that line's `QST_` key.
   - Words inline mean base text.
   - A key next to a table name means a string-table reference.
   - Neither means the graph names a dialogue row by tag, and the text comes from that row's `StringKey` through `Strings_EN`, like the names. Both dialogue tables carry `StringKey` per node tag.
3. To be sure, decode one export whose class in the name map is `QuestDialogueTalkingNode`:
   - open it with `cooked.ZenPackage(data)`;
   - read its unversioned properties in the order the dump gives (`UGenericGraphNode`'s, then `UQuestDialogueNode`'s, then `Paragraph`);
   - decode `Paragraph` with `cooked._Values.read(r, "text")`, which knows types 11, 0 and -1.

**In game** (the test cat, a backup, nobody else's game).
1. The test builds a temp mod whose `names.json` `text` appends " [wcmods]" to all 826 `QST_Story.Monologue.Filler.*` lines, read from the game's `Strings_EN.csv`.
2. It installs the mod with `agent install --with` and enters the world in camp.
3. It finds the nearest clan cat with one `SphereOverlapActors` of radius 3,000 on `BP_Quest_Filler_C` at the cat's spot (no scan), teleports beside it, faces it and presses Interact (`agent key E`).
4. It reads the open box with `Game.find("WBP_QuestGiver_Dialogue_C")`, checked with `IsInViewport()` because a find can hand back a dead screen. `mcGuiTextParagraph:GetText():ToString()` should end with " [wcmods]".

388 of the 824 filler rows in `StoryDialogues.csv` carry ClanBonding 1, harmless on the test cat. The manual version (the names plan's game check) rewrites only `QST_Story.Short.TheAgingLeader.Main.1.Context.1` ("I'm troubled by this new prophecy...") and talks to the leader when the story offers that conversation.

**What it unlocks.** The Lines card states the result instead of a hedge. If the talk ignores the CSV, the card is held back and step 9 becomes the route.

**Verified by** `tests/game/test_dialogue.py::test_an_edited_line_shows_in_a_talk`. It is a new file, so this check doesn't wait on the names plan's `test_names.py`.

**Docs:**
- `docs/verified.md`: the result, either way.
- `docs/reverse-engineering.md` "Dialogues": the graph classes and the FText form found. The tables' columns are the names plan's paragraph.

The card, its route, its tests and `docs/formats.md`'s dialogue example are the names plan's step 8.

### 3. Sounds and music: is AudioEvents.csv read at runtime

**The gap.** The columns of `AudioEvents.csv` are the fields of `FSwtAudioDataStruct`, so the CSV is the source of the audio manager's table. What is not known is where the manager builds `AudioEventsInfo` from:
- the CSV in the pak at runtime, as the game reads `Strings_EN.csv`;
- a DataTable cooked from it at build time;
- the folder `PathToSoundCues` names, with cues found by their names (`S_Cue_<id>`).

It is also not known whether area music is chosen by these ids. `ESwtAudioEvent` is a native enum of 20 ids (`cat_step`, `mus_camp`, `ui_select`, ...), which hints that some code plays by enum, and that may or may not go through the map.

**Static.**
- `python wcmods.py files "*AudioEvents*"`: a cooked `DT_AudioEvents.uasset` beside the CSV would say the CSV is a leftover. The quest tables have both forms.
- `python tools/re/xrefs.py <exe> "AudioEvents" "AudioEventsInfo" "PathToSoundCues"`: a reference to the CSV's path near the manager's loader says it is read at runtime.
- Compare with the TuningData loader, which step 1's script prints.

**In game** (the test cat, a backup). The test adds a temp mod in `tests/game/test_data.py`, the data-save plan's file and pattern. Rows are keyed by the table's first column, a number, so `cat_step` is row `78` and `mus_camp` row `16`:

```json
{"AudioEvents.csv": {
  "78": {"AudioEvent": "/Game/Audio/Cues/sfx/S_Cue_cat_hiss_1.S_Cue_cat_hiss_1"},
  "16": {"AudioEvent": "/Game/Audio/Cues/music/MS_mus_empty.MS_mus_empty"}}}
```

- **Without ears:** `Game.manager("audio")` is the game instance's `NativeAudioManager`; the test logs its class. On that one object, read `AudioEventsInfo` (soft paths, with `ForEach`) and `AudioEventsMap` (loaded sounds), and expect `cat_step` to hold the hiss.
- **With ears** (manual): walk, then walk into camp.
- **A third row** mutes one effect with `MS_mus_empty`. It tells whether Mute can use the music's silent cue for every kind.

**What it unlocks.** The Sounds and music card: swaps and mutes of the game's own sounds by a `data.json` edit, no new format. A creator's own `.wav` is a later, separate finding: the cooked `USoundWave` layout, in "The rest of the ranking".

**Verified by** `tests/game/test_data.py::test_a_swapped_sound_is_what_the_audio_manager_holds`.

**Then, in the code.** This is its own PR, made only if the check says the CSV is read. If it isn't, the check's PR records the answer and the Audio section says sounds need cooked paks.
- **`wcmods/sounds.py`:**
  - `NAMES` gives the 148 music, effect and UI ids in words (`mus_camp`: "Camp music", `mus_combat`: "Fight music", `cat_step`: "Paw steps", `ui_select`: "Menu select").
  - A rule names the 41 cat voices (`vo_dialog_sad`: "A cat talking, sad"; `vo_cat2_purr`: "Cat voice 2, purr").
  - The 201 narrator lines stay out of the card (open question).
- **`GET /api/game/sounds`** in `studio.py` lists row number, id, plain name, kind and path from the game's CSV.
- **The page.** `studio/lib/sounds.js` holds the pure part: rows to groups, a swap to the `data.json` cell, Put it back. `studio/sections/data.js` draws the card, with its styles in the look's `studio/sections/data.css`.
- **The id guard.** The card also writes `"_ids": {"78": "cat_step"}` inside the table's entry. `apply_edits` already skips keys starting with `_`, and older wcmods ignore it. `wcmods/sections/data.py` `build()` uses it to warn when the game's row 78 is no longer `cat_step` ("the game renumbered its sounds: open Sounds and music to pick it again"). It also warns, without refusing, when an `AudioEvent` value isn't one of the game's own cue paths.

Tests:
- `tests/unit/test_sounds.py`:
  - `test_every_music_effect_and_ui_id_has_a_plain_name`, against the list of ids kept in `sounds.py`, not the game file;
  - `test_a_voice_id_gets_a_generated_name`;
  - `test_a_sound_swap_edits_the_audio_event_column`, through `csvdata.apply_edits` on a three-row CSV keyed by number;
  - `test_a_renumbered_row_warns`;
  - `test_an_unknown_cue_path_warns_and_keeps_the_rest`.
- `tests/studio/lib/sounds.test.mjs`: `'a swap writes the AudioEvent cell of the chosen row number'`, `'Put it back removes the edit and its id'`, `'only sounds of the same kind are offered'`.
- `tests/studio/data-sounds.test.mjs`, with the Chromium driver: `'Camp music plays Fight music lands in data.json'`.
- The selftest checks that every id `sounds.py` names is still in the game's table.

Docs:
- `docs/reverse-engineering.md` gets a new "Audio" section: the table and its row numbers, the manager and its two maps, the anim notify, the enum, and the voice ids the dialogue tables name.
- `docs/formats.md` `data.json`: a sound swap as the second example, with the row-number key and `_ids`.
- The Game data guide page.
- The README page table.

### 4. Signatures for the level component

**The gap.** Bug 1. `signatures.make()` searches a class's own functions plus the anchors in `signatures.py` `ANCHORS` for instructions that touch each member. The level component's two anchors are fighter-stat functions that never read it, so no site was found and the result shipped.

**Static.**
1. **The six stats.** `python tools/re/dispscan.py <exe> 154,158,15C,160,164,168 3` prints the 1 KB blocks where three of the six stat offsets appear. dispscan only sees SSE float operands, so it finds the stats (floats, in the stats struct at +0x138), not the level.
2. **The level and the shown level.** Level (+0x120) and LevelShown (+0x124) are ints. Reach them through the code that fills them: `python tools/re/xrefs.py <exe> "Gameplay.Exploration.MaxLevel" "Gameplay.Exploration.Level.2"` finds the XP table's loader and the level-up check, which read the level beside the XP. Other candidates are what writes the save's `Level` and `Experience` back.
3. **Keep the right functions.** Run `dumpbin /disasm:nobytes /range:<start>,<end> <exe>` on the candidates. Keep the ones whose `this` is the component and that touch +0x120/+0x124 or the stats: the level-up and stat-growth code `docs/mechanics/progression.md` describes.
4. **Make the signatures.** Add their RVAs to `ANCHORS["/Script/SwtAdventure.SwtAdventureLevelComponent"]` with a note each, run `python wcmods.py game signatures make` on build 26184573, and confirm the log line no longer ends "none for Level, LevelShown, ...".

Two code changes go beside it:
- **`make()` fails a class with no sites at all.** Today it only logs. A member with no site of its own stays allowed, because `check()` keeps it while its classmates are found where they were.
- **`check()` keeps a site-less class** whose anchors all match and whose size is unchanged: the skeptic's interim, for any class that ends up with no sites.

Optionally, prove the check without a patch: copy the exe to the scratchpad, flip one byte in `.text` away from any pattern, and `signatures.check(copy)` must answer "same" for the eight (open question: the copy is 183 MB).

**What it unlocks.** Level, XP and stats stay on after the next patch, and the Mods page's update banner usually has nothing to say about wcmods' own values.

**Verified by** unit tests with a fake `Finder` (monkeypatch `pe.Image` and `signatures.Finder`):
- `tests/unit/test_signatures.py`:
  - `test_two_sites_agreeing_move_a_member`;
  - `test_one_site_alone_is_unsure`;
  - `test_sites_disagreeing_conflict`;
  - `test_an_offset_outside_the_class_conflicts`;
  - `test_two_members_on_one_offset_conflict`;
  - `test_a_class_with_no_sites_is_kept_when_its_anchors_match`;
  - `test_make_fails_a_class_with_no_sites`.
- `tests/unit/test_gamebuild.py`, with the harness's temp folders:
  - `test_a_verified_build_needs_no_check`;
  - `test_layout_caches_a_check`;
  - `test_a_half_written_cache_is_ignored`;
  - `test_a_failing_check_leaves_everything_off`.

In game only after a real patch: `python wcmods.py game signatures check`, then `agent menu read Stats` shows numbers.

**Then, in the code.**
- **`gamebuild.describe()` says it in plain words.** It maps each class to words, one phrase per class (deduplicated), e.g. `PLAIN = {"SwtAdventureLevelComponent": "your cat's level, experience and stats (the mod menu's Cat page and scripts)", "SwtAdventureFreshKillPileComponent": "the fresh-kill pile's timer", ...}`. Two places use it:
  - the Apply warning in `pipeline.py` lines 212 to 215;
  - the `GET /api/game/update` route (`studio.py` lines 195 to 200), whose `lost` and `moved` lists the Mods page banner joins (`studio/sections/mods.js` line 61).

  So the banner needs no change of its own, whatever the shell does to that page.
- **The game module carries the status.** `game.py`'s `lua()` gets the layout status and the lost classes in words, as a `@LAYOUT@` beside `@SAVED@`, passed by `pipeline.py` line 299.
- **The Overview says it in game.** The mod menu's Overview (`wcmods/lua/menu_host.lua`) shows one line while values are off: "The game updated: level and stats are off until wcmods updates".

Tests: `tests/unit/test_gamebuild.py::test_describe_says_it_in_plain_words` and `tests/unit/test_lua.py::test_game_module_carries_the_layout_status`.

Docs:
- `docs/updating.md`: the level component is now signed, and what "partial" means in words.
- `docs/reverse-engineering.md` "Game updates".

### 5. The RE tools and the Nearby label cache

**The gap.** Bugs 5, 6 and 7. Bug 2's fix (`world.place_names`) is the names plan's step 7, with its test, because its quest list needs it first. Two pieces of this audit go into that PR:
- the audit's other `place_names` cases: a ranked title, `Title2` rows ignored, a short LocationsData row, a missing table;
- the in-game check: extend `tests/game/test_menu.py::test_quests_page` so the test cat's rank-up quest reads "The Proving Grounds".

**Static only.**
- **world.lua:** `scan()` resets `actorLabels`.
- **memscan.py:** `read()` returns `buf.raw[:got.value]` on a partial copy. `scan()` reads exactly `n` bytes, with the previous chunk's last `len(pattern) - 1` bytes prefixed, so matches across chunk edges are still found.
- **xrefs.py:**
  - drop `or True`;
  - add `\x8b` to the opcode class, so `mov` is found as the docstring promises;
  - skip odd offsets for UTF-16;
  - move the work into a `find(data, strings)` function with a `main()`, so step 1's script and the tests can import it.

**Verified by:**
- `tests/unit/test_re_tools.py`, memscan (Windows only, skipped elsewhere):
  - `test_memscan_finds_a_pattern_in_a_lonely_region`: a page from `VirtualAlloc` whose next page is set `PAGE_NOACCESS`, scanned through `Proc(os.getpid())`;
  - `test_memscan_finds_a_pattern_across_two_chunks`, with `chunk=4096`.
- `tests/unit/test_re_tools.py`, xrefs on a tiny synthetic PE written to the temp folder:
  - `test_xrefs_reports_a_lea_and_a_mov`;
  - `test_xrefs_skips_the_tail_of_a_longer_string`.
- `tests/unit/test_lua.py::test_world_scan_clears_the_label_cache`: it reads the source, as the other Lua tests do.

**Docs:** `docs/reverse-engineering.md` "How we find things" says four things:
- xrefs reports both forms, and only whole strings;
- `api-index.txt` is the first place to look;
- `tuning_read.py` exists;
- "no more hits" notes made with memscan before the fix are worth repeating.

### 6. The Interact command and the enums, read from the game

**The gap.** Bug 3. Bug 4 is the console-lua plan's step 1.

**Static only.**
- **A reader in `game.lua`.** `Game.enumNames(path)` does what `remap.lua`'s `commands()` does (`StaticFindObject(path):ForEachName`), returning nil when the enum isn't found.
- **The Interact command.** It is read once, at the first prompt (`Player_Interact` in `/Script/SwtEngine.ECommands`), falling back to 67.
- **The enums.** At load, each `Game.enums` list is rebuilt from its enum's path, keeping the shipped list when the read fails. The paths come from `api-index.txt`:
  - `EClanType`, `ECharacterRank`, `ECharacterTrait` and the other quest enums are in `SwtQuest`;
  - `ESwtAdventureCombatStance`, `ESwtAdventureStatusType`, `ESwtAdventureCombatAttribute` and the rest are in `SwtAdventure`.

  Each Game.enums list matches one native enum.
- **Logging.** One log line when the game's names differ from the shipped list.
- **`remap.lua` keeps its own copy,** since it runs without `WCModsGame`.

**Verified by:**
- `tests/unit/test_lua.py`:
  - `test_interact_command_is_read_from_the_games_enum`: the `StaticFindObject("/Script/SwtEngine.ECommands")` call sits in `game.lua`, as the remap test asserts for `remap.lua`;
  - `test_every_game_enum_names_its_path`.
- In game, `tests/game/test_cat.py::test_enum_values_match_the_game`: `Game.enums.status.Poisoned` equals the value `uht.py <exe> enum ESwtAdventureStatusType` gives.

**Docs:** `docs/scripting.md` "JSON and enums": the values come from the game, and a name the game dropped reads nil after one log line.

This PR and the console-lua plan's step 1 both edit `game.lua`, `tests/unit/test_lua.py` and `docs/scripting.md`; the second to land rebases.

### 7. The sky table, and whether the day cycle overwrites it

**The gap.** The only "weather" the game has is the sky and the clock. `SkyParamsDB` and the presets are known from the dump. Four things are not:
- which asset the table is;
- how its rows are keyed (per preset or otherwise);
- whether `cooked.py` can decode `FWrcSkyBoxStruct` (floats and `FLinearColor`, which the schema kinds don't cover yet);
- whether the day cycle, the zone switch or a fight rewrites the live light and fog.

**Static.** `python wcmods.py files "*Sky*"` gives the table's path. Then:
1. `extract` it.
2. Add to `cooked.SCHEMAS` a row schema with a new `"colour"` kind: four `f32`, written as the native struct.
3. Decode it with `cooked.DataTable`. The selftest's byte-for-byte rebuild says whether the schema is right.

**In game.** `Game.find("BP_DayNightSky_C")` is one object, not `wcmods find`, which scans; `inspect` it.
1. Read `SkyParamsDB` (its path), `TransitionTimes` and `PresetForInventory`.
2. Call `sky:ApplyStraight(4)` (Night) by day and take `agent shot`.
3. Set `sky:GetExponentialHeightFog().FogDensity` and read it a second later, to see whether something writes it back.
4. Walk across a territory border, and check whether the preset follows the zone and undoes a script's choice.

`Game.time.set(21, 0)` is already verified for the clock.

**What it unlocks.** A Sky card of a few looks, by one of two routes:
- a cooked-table edit built into the mod pak, if the rows are per preset. This is the `DT_QuestObjectsInfo` route: adding rows is verified, editing a row through the same encoder is new;
- a shipped script that calls `ApplyStraight` after each zone switch, if the live values are what count.

If the table is the route, the file stores the look's name, a new optional `world.json` holding `{"sky": "foggy"}`. A new `world` section turns the name into row edits through a new `cooked.DataTable.set_row` (only `BuildContext.add_table_row` exists today). Then a later change to what "foggy" means reaches every mod, and creators never see the 40 fields.

**Verified by:**
- `tests/unit/test_formats.py::test_sky_rows_round_trip`: a synthetic table built by the encoder, in CI;
- the selftest check `_sky_table`, against the installed game;
- in game, `tests/game/test_world.py::test_a_sky_preset_changes_the_fog`.

**Docs:**
- `docs/mechanics/exploration.md` "Time of day": the sky, its presets and their zone switching, and a line that there is no weather or season system;
- `docs/reverse-engineering.md` "The game's live state".

### 8. Where a bond is stored, and what an answer's Score does

**The gap.** Bonding is the game's relationship system. `docs/mechanics/quests-and-bonding.md` marks "what the scores feed" as inferred. The one save looked at had an empty `Bonding` map, and `Game.save.progression` has no known keys.

**In game** (a story-mode cat, with a backup).
1. **Before a talk:**
   - Keep `Game.save.file()`'s slot `Bonding` and the `Shared` section.
   - Hook three save-manager calls, logging their arguments: `Game.hook("/Script/SwtEngine.SwtSaveManager:SetGameProgressionData", function(self, a, b, v) print(a, b, v) end)`, and the same on `SetMoodData` and `SetStateJsonDataFromString`.

   Hooks see only calls made through Unreal. A native-to-native write will not show, which is itself an answer.
2. **The talk.** Talk to a clan cat (388 of the 824 filler rows give ClanBonding 1 by the table), finish, call `Game.save.write()`, and diff `WrcGame.json` before and after in Python.
3. **The bonds screen.** Open the pause menu (P) on its Bonds panel (`UGuiPausePanelBonds.mcGuiBondsList`, a `UGuiListCatsBonds`), and `inspect` one of its items to see what field it reads.

**Static.**
- `python tools/re/xrefs.py <exe> "Gameplay.Progression.Bonding.Personal.Friendly" "Bonding.TraitModifier"` finds the loader; `storemap.py` gives the members and `dispscan.py` the comparison code.
- `xrefs.py <exe> "Bonding"` finds the save writer's key names.

**What it unlocks.** Two features, if the store is one a script can write (a slot JSON key through `Game.save.setState`, or a progression key):
- **A Questlines reward.** It goes into the story plan's `gives`: `"gives": {"bond": {"cat": "Brightheart", "by": 10}}`. That is an optional key, so no existing quest changes meaning.
- **A Bonds line on the mod menu's Cat page,** in the Menu pages mod's repository.

Either way, the Game data page can explain `Score` and `ClanBonding` with confidence. That makes "make the Wise answer the right one" a plain `data.json` edit of the dialogue tables.

**Verified by** the save diff and the hook log, recorded in the docs. The reward's tests go with its feature PR: `tests/unit/test_story.py::test_gives_a_bond_names_a_cat_and_an_amount`, and in game `tests/game/test_world.py::test_a_bond_reward_shows_on_the_bonds_panel`.

**Docs:**
- `docs/mechanics/quests-and-bonding.md`: from inferred to seen, adding `EBondingRanks`' Unfriendly rank and `bCheckBonding` on prey generators;
- `docs/scripting.md`: the save section's keys.

### 9. The dialogue graph format, and playing a conversation by tag

**The gap.** Everything about a conversation beyond its words: the nodes, the branches, which answer is right, and whether a mod can add an answer. High value, high effort. Step 2 decides whether the Lines card needs it at all.

**In game first, because it is cheap.** On the Sandbox mode cat (slot 4, picked on the choice screen as above) with a backup, with a studio cat `npc` from `Game.npcs`, call:

```lua
Game.manager("sequencer"):PlaySequenceDialogue(Game.tag("Gameplay.Dialogue.Story.Short.TheAgingLeader.Main.1"), npc:actorOrNil(), Game.player(), false, false)
```

It is reflected and untried. Then try the tag's stem with both flags true, which append the player's clan and rank. If the game's own box opens with the cat and the answers work, a Questlines step "Play the story conversation" exists without the format.

**Static.** With the graph package from step 2:
1. Walk its export map (72-byte entries) and name the class of each export from the name map.
2. Decode:
   - `UQuestDialogueTalkingNode`: `Paragraph`, `TalkingSource`, `VOEvent`, and the `ChildrenNodes`/`ParentNodes` arrays every `UGenericGraphNode` has;
   - `UQuestDialogueBondingTypeNode`: `BondingTypesTexts`;
   - the root.
3. Add `"array"` and `"object"` kinds to `cooked.SCHEMAS` and re-encode byte for byte.

Adding a node is the hard half: new exports need public hashes, export bundle entries and dependency bundles, which the one-export texture packages never touched.

Do the same for one `QuestDynamicGraph` and the `QuestGraphDB` rows (`FQuestGraphDatatable`: clans, ranks, giver roles, weight, a map of banned ranks). That decides whether "which procedural quests a clan offers" is an edit.

**What it unlocks.**
- **Reading:** the Lines card shows a conversation's shape and which answer is right.
- **Writing:** a new answer or branch in the game's own dialogue, and quest tuning in the game's own log.
- **The call:** the step "Play the story conversation", if it works.

**Verified by:**
- the selftest check `_dialogue_graph`: every talking node of one graph decodes and the package rebuilds byte for byte, against the installed game, like the item table;
- `tests/unit/test_formats.py::test_a_graph_with_two_nodes_round_trips`, on a synthetic package in CI;
- in game, `tests/game/test_npcs.py::test_a_story_conversation_plays_by_tag`, kept only if the call works.

**Docs:**
- `docs/reverse-engineering.md` "Dialogue graphs" and "The quest system's tables": the row struct and the objective classes;
- `docs/mechanics/quests-and-bonding.md`.

### 10. The save checksum

**The gap.** `USwtSaveGame.Hash` is a 64-bit value with an unknown formula. Creators lose nothing today: edited saves are accepted with the old value. The question is whether a patch could start checking it, which would break the Save page and the cat renames at once.

**In game, first.** Run `wcmods lua "return tostring(Game.save.manager().SaveGame.Hash)"` right after `Game.save.write()`. A zero ends the question.

**Static.**
- `python tools/re/uht.py <exe> props Hash` gives its offset in the object. The table around it lists `GamerId`, `Version`, `ExportsName`, `jsonString`, `saveSlots` and `CompressedData`.
- `xrefs.py <exe> "jsonString" "CompressedData"` finds the save writer; dumpbin it and look for the hash call.
- In Python, `formats/save.py` gains `SaveGame.hash` (the `UInt64Property` in the GVAS header). A scratch script tests CityHash64 (`formats/cityhash.py` `cityhash64`), CRC64 and xxHash against a real save's value, each over three inputs: `jsonString`, the JSON with each byte minus one (the payload's own form), and `CompressedData`.

**What it unlocks.** Nothing visible. It protects the Save page, `cats.json` and `names.json` cats from a future check, and the formula goes into `save.py` so a written save is always right.

**Verified by:**
- `tests/unit/test_formats.py::test_save_hash_is_read_from_the_gvas_header`;
- the selftest check `_save_hash` on the machine's save, once the formula is known.

**Docs:** `docs/reverse-engineering.md` "The save".

### The rest of the ranking

Below the ten, in order, each with its one-line route so it is not planned twice:
1. **Whether `Game.quests.start("Quest.Procedural.Survival.Gather")` starts one of the game's quests for a mod.** One call in the forest with a backup, then read the quest HUD; it shares step 9's evening. It would allow a Questlines step "Start one of the game's quests".
2. **Whether a studio cat can walk.** `inspect` a filler's controller and movement component, and try `SimpleMoveToLocation`.
3. **The dialogue box's own answer buttons**, for a talk with choices: `mcButton1..4` with `SetVisibility(4)`, and `Game.pressed` polling. The story plan lists this probe too.
4. **The save's `NPCData` fields beyond looks**, for changing a cat's role: a save diff across the deputy dilemma.
5. **`UniqueIds` `SoftData` at runtime:** edit one pickup's `Rewards` and collect it.
6. **The `GetMoodData` keys:** folded into step 8's hooks.
7. **The five events never seen firing:** one scripted fight with all five handlers logging, using the narrow `FindAllOf("BP_Exploration_Character_Base_C")` the project's notes found safe, or by hand.
8. **The native inventory add path:** `xrefs.py` on `OnItemPickedUp`, `callers.py` upward, then a C++ SDK call.
9. **Den decoration packs:** `DecorationsDB` and a static-mesh package writer.
10. **Two mechanics guesses:**
    - XP per level versus a running total (a save diff across a level-up);
    - den build times in real hours (a build with the clock advanced).
11. **The cooked `USoundWave` layout,** for a creator's own `.wav`: the texture-package method on one of the game's cues.
12. **Loading a mod's own cooked pak** from a `Wrc` project.
13. **`ClanSpecificBase.csv`, `HeightMap/` and `GameSharedForceFeedback.csv`:** `xrefs.py` on a row name each. Rumble strength would be a one-row option.
14. **What the den-visit server checks in `VisitRewards.csv`:** strings for the endpoints, and a throwaway account.

## Backward compatibility

- **`data.json`:** the shape is unchanged. A sound swap is an ordinary row edit keyed by the AudioEvents row number. The `_ids` note beside it is skipped by `apply_edits` and by older wcmods; it only lets a build warn when a game update renumbers the table. The page keeps `_` keys as they are.
- **`names.json`:** unchanged. Lines are `text` keys, as today.
- **`signatures.json`:** same shape, more sites. The layout cache key includes the file's hash (`gamebuild._version()`), so a layout worked out with the old file is worked out again, and the status bar asks for one Apply.
- **`wcmods/exe/tuning_read.json`:** new data shipped with wcmods. When it is missing, no line is shown.
- **`Game.enums`:** the same names, with values from the game. A script using a name the game dropped reads nil after one log line, where today it would silently use a wrong number.
- **Sky and bonds:** additive. `world.json` is a new optional file. `gives.bond` is an optional key in the story plan's `gives`, which older Sandbox mode ignores; that plan's version check says so.
- **`save.py`:** reading the hash changes nothing written.

## Not in this plan

These are known impossible, each with the reason, so nobody plans them again. The docs-guide plan's "What you can and can't do" sections quote this list.
- **A weather or season system.** The game has no class, enum or tuning key for one. Rain would need new effects cooked in Unreal plus a script. Sky looks are step 7.
- **A new kind of prey or predator.** `ESwtQuestCharacterType` is a native enum with per-kind Blueprint, animation Blueprint, mesh and animation tables. A re-skinned, renamed, re-statted kind is data and is possible.
- **A new area or camp.** That is cooked world partition data, and no tool reads it.
- **A new trait.** A native enum, with trait-keyed tables and no reflected trait function.
- **A mod's own quest in the game's K list.** `UGuiHudQuest` works from native `UQuestBase` objects. Mod quests stay in the objective panel and the mod menu's Quests page. Only a new quest graph cooked into the pak could change that, and step 9's write half would have to reach it first.
- **A new effect strength kind for herbs.** It needs a Blueprint container; the existing rows' numbers are editable.
- **Ending a fight from a script.** `EndCombat` leaves the cat without a body.
- **Opening one of the game's screens from Lua.** `USwtGuiManager` reflects no open function. A C++ mod calling the native code is a needs-RE route, after the inventory-add style of search.
- **Making Resilience reduce damage, giving Patient a real bonus, or adding a tuning key.** The code reads what it reads. These are Lua or code mods, not data.
- **New coat or eye colour slots.** Coats are a native map on the manager, and eyes a 26-row atlas in the shader, per the project's notes.
- **Items straight into the bag from Lua.** Nothing reflected adds to the inventory. That stays on the remainder list as a C++ route only.

Owned by other plans: the in-game table check and the Game data page (data-save); `place_names` and the Lines card (names); bug 4 and the runtime fixes (console-lua); the `gives` rewards and the answer-button probe (story); the guide pages (docs-guide).

Needs reverse engineering but deliberately not in the ten: everything in "The rest of the ranking" above. Each has lower creator value per evening, or waits on a step above.

## Open questions

- **Where the Sounds card goes.** On Game data (the plan) or a page of its own?
- **Which sounds are offered.** Should the 41 cat voices be swappable (the plan says yes)? Should the 201 narrator lines be left out (the plan) or offered as mute only?
- **The id guard.** Is `_ids` enough against a renumbered AudioEvents table, or should `data.json` learn to key a row by another column?
- **The modified-exe check in step 4.** Is a 183 MB copy of the exe in the scratchpad acceptable, or are the unit tests with a fake finder enough?
- **Which evenings may use the game,** given that it is shared between sessions, and in which order? Steps 2 and 3 each want it for an hour, 8 wants a story-mode cat and a talk, and 9 the sandbox cat. Step 3's check also waits on the data-save plan's verification PR, whose test file it extends.
- **The "doesn't name this one" line.** Should TuningData rows carry it at all, given that a key built at runtime from a pattern the script missed would be mislabelled? The plan shows it only when none of the key's dotted prefixes is referenced from code.
- **The sky.** Named looks only (the plan), or raw values per preset as well for hand-written files?
- **The save checksum.** Is it worth the evening at all, given edits are accepted today?
- **The dialogue graph write path.** Does step 9's hard half go ahead only if step 2 finds the CSV ignored, or regardless, for new branches?
- **Tests for maintainer-only scripts.** Steps 1 and 5 give `tools/re/` synthetic-PE tests. Is that worth it?
- **The plain names for sounds.** When the game adds a sound, who owns its name: the list in `wcmods/sounds.py`, which the selftest checks against the game's CSV (the plan), or the ids shown raw with the names as an overlay?

## Changes from the review

- **Step 1** duplicated the data-save plan's in-game table check (same test file, same run-speed row, same "seen working" line on the page). It now refers to it, and takes the question that plan hands to RE: which TuningData keys the code reads. That was the first item of "the rest", and it needs step 5's xrefs fix. The `SEEN_IN_GAME` chips are dropped, because the data-save plan's card line covers them.
- **Step 2** duplicated the names plan's step 8: the card, `GET /names/lines`, the placeholder warning and their tests. It is now the research and an agent test in a new `tests/game/test_dialogue.py`. A cheap byte search comes before the decode, and the read checks `IsInViewport()`. The filler count is 826, not about 1,000.
- **Step 3:**
  - AudioEvents rows are keyed by their first column, a number. `{"cat_step": ...}` would have failed with "no row 'cat_step'"; the examples now use rows 78 and 16.
  - The manager has two maps plus `PathToSoundCues` (a third hypothesis).
  - The 242 voice rows are 41 cat voices and 201 narrator lines.
  - Swaps are kept to one kind, and a hidden `_ids` guard was added.
  - The check and the card are two PRs, the card made only if the check passes.
  - JS tests moved to the harness's `tests/studio/` paths.
- **Step 4:**
  - dispscan sees only SSE float operands, so it can't find Level and LevelShown (ints); a route to them was added.
  - `make()` fails a class with no sites, not any member without one.
  - The plain words also reach the `/api/game/update` route that the Mods page banner (`mods.js` line 61) shows.
  - The Overview line is in `menu_host.lua`. `remap.lua` is not touched.
- **Step 5:** bug 2's fix is the names plan's step 7; the extra `place_names` cases and the Quests-page check go there. xrefs becomes importable.
- **Step 6:** bug 4 is the console-lua plan's step 1 (the story plan lists it too), so its fix and tests were dropped here.
- **Step 7:**
  - `wcmods find` is a `Game.findAll` scan, against the probe rule; it is replaced by `Game.find`.
  - The zone switching was added to the check.
  - The file stores a look's name, not 40 raw fields.
- **Step 8:**
  - The bonds list is the pause menu's Bonds panel (`UGuiPausePanelBonds`).
  - The reward extends the story plan's `gives`.
  - The reward's tests moved to its feature PR.
- **Step 9:** the call is tried with the flags off first.
- **The procedures:**
  - `--cat N` doesn't pick the cat.
  - The game stalls behind other windows.
  - The dev save's test cat is Fawnstar ("Cat 1").
- **Moved or added:**
  - `Game.quests.start` was added to the rest, from the audit's half-finished list.
  - "Opening a screen" moved from impossible to Lua-impossible.
  - A Backward compatibility section was added.
  - The docs-guide plan's "What you can and can't do" now carries the impossible list, which answers the audit's medium UX issue.
- **The PRs:** the one large findings PR is split into sky, bonds with dialogue graphs, and the checksum.
