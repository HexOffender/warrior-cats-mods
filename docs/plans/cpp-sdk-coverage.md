# The C++ SDK, for all of the game

A plan to make wcmods' C++ SDK (`wcmods/cpp_sdk/include/WCMods/`) reach every part of the game a mod could want to
read or change, and to close the reverse-engineering gaps that stand in the way. The Lua side is out of scope here:
the owner will have it caught up later, from what these steps find. Written 2026-11-04 on build 26337109, after
[HexOffender/warrior-cats-mods#111](https://github.com/HexOffender/warrior-cats-mods/pull/111) (native functions, the
live inventory, commands, the sky, sounds, montages, the save's hash) and #112 and #113 (the Menu pages fixes).

The steps are done one at a time, in one session, so no two pieces of work overlap. Each one is its own pull
request, reviewed and merged before the next starts.

## What it is for

A C++ mod should be able to do with the game what the game itself does:
- read and change any of its tables and words while it runs;
- play, swap and silence its sounds and music;
- change its sky;
- make cats of its own that walk, talk and are talked to, and change the looks of any cat;
- read and change bonds, quests, story scenes, fights, dens and the clan;
- put things on the ground, play animations, show effects;
- move the player around the map, and show things on the HUD and the map.

Where the game can't do something (a new area, a new trait, weather), the plan says so once, with the reason, so
nobody plans it again.

## Where it stands

What the C++ SDK reaches today (SDK.md, "C++ mods"), all seen working in game:

| Part of the game | C++ today |
|---|---|
| Objects, reflection, hooks | any property by path, any reflected function, hooks before and after, spawning plain actors |
| Your cat | health, stamina, fight stamina, level, XP, stats, status conditions, size, place, time dilation |
| Animals | senses, what their AI knows, the blackboard |
| The clock, the fresh-kill pile | read and set |
| Inventory | live counts, adding and removing through the game's own `AddItem` |
| The save | the slot's live state, saving, the hash, the file as JSON |
| Quests | the list, statuses, objectives, the tracked one, the chapter (starting one is written but untried) |
| Fights | fighters, moves, teams, turn order (the fight events are hooked but never seen firing) |
| Commands | the game's own commands (opening the inventory, the pause screen) |
| The sky | its presets, held |
| Sounds and animations | playing the game's sounds by id, and its own montages by tag |
| UI | tabs in the game's screens, the HUD's parts, overlays, every UMG control; the mod menu's pages |

What the Lua module has and C++ hasn't: cats of a mod's own (`Game.npcs`), pickups on the ground
(`Game.items.drop`), a mod's own animations (`Game.anims`), the talk box (`Game.dialogue`), the HUD's banner and
objective lines (`Game.hud`), map markers (`Game.mapMarker`), the clock hold (`Game.time.hold`), a cat's
customization data as a table.

What nobody's code reaches yet: the game's tables and words while it runs, the music, the sky's values, bonds,
playing a conversation by tag, the clan roster, den decorations, minigames, dilemmas, story scenes by tag, starting
and ending fights cleanly, fast travel, photo mode, the camera, visual effects.

The reverse-engineering roadmap's open steps ([re-roadmap.md](re-roadmap.md)) fold into this plan:

| Roadmap step | State on 2026-11-04 | Closed by |
|---|---|---|
| 1. Which tuning values the game reads | table edits reach play (run speed, seen); which of the 441 keys the code reads is unknown | step 2 |
| 2. A line edited in `Strings_EN` shows in a talk | done: a key's words changed show in a talk's line (step 7) | steps 3, 7 |
| 3. Is `AudioEvents.csv` read at runtime | not checked | step 4 |
| 7. The sky table, and the day cycle | presets and the fade back known; the table not looked at | step 5 |
| 8. Where a bond is stored | done: the cat's slot's `GameplayProgression/Bonding`, through the game's bond functions (reverse-engineering.md, "Bonds") | step 8 |
| 9. The dialogue graphs | done: read in game by reflection and played in the talk box; the game's own player by tag tried and set aside (it crashes when ended early) | step 7 |
| The rest, 1: `quests.start` on the game's quests | untried | step 11 |
| The rest, 3: the talk box's answer buttons | done: they show answers' words; clicking them runs the box's own graph code, so a mod takes answers by number | step 7 |
| The rest, 4: `NPCData` beyond looks | not started | step 9 |
| The rest, 6: the mood and progression keys | not started | step 11 |
| The rest, 7: the five events never seen firing | not seen | step 12 |
| The rest, 9 and 10: den decorations, build times | not started | step 13 |

Steps 4, 5, 6 and 10 of the roadmap are done (level signatures, the RE tools, enums from the game, the save hash).

Two things found on 2026-11-03 are open too: the pause screen's tabs moved to the arrow keys and a mod's tab page
keeps them (three UI tests fail), and UE4SS crashed in its own code at least three times (step 1).

## How every step runs

1. **A branch** from `origin/main`, in the worktree `.claude/worktrees/cpp-sdk-native` (`claude/cpp-<topic>`).
2. **Find out first.** Static work on the class dump (`vanilla/sdk/api-index.txt`), the extracted tables and the exe
   (`tools/re/`); then in-game reads through the bridge, one object at a time: no `FindAllOf` or `find` scans, a
   backup first, and nobody else's game (check `agent status` and the UE4SS log's start time before installing).
   What's found goes into `docs/reverse-engineering.md`, with how it was found.
3. **The calls**, in the SDK's headers, in its style: game thread only, `nullptr`/`nullopt`/`false` when something
   isn't there, a line in the log for a misuse, nothing that can crash on a missing object. A native function the
   SDK calls is signed per build (`game.NATIVE`) and checked against its pattern before every first call.
4. **Proof for every call.** Game-free unit tests in `tests/cpp-sdk/cpp/src/` (fakes of the game's memory layouts,
   as `test_native.cpp` does for the inventory's map), Python unit tests for anything under `wcmods/`, and an
   in-game test per feature in `tests/game/test_cpp_sdk.py` through the C++ test mod's phases, run on a fresh game.
   What the game did goes into `docs/verified.md`; what wasn't seen stays in its unchecked list.
5. **Docs:** `docs/SDK.md` for every call, `docs/reverse-engineering.md` for the findings, and this plan's status
   table below.
6. **Review and merge:** the pull request gets a code review (correctness first), the findings are fixed and the
   affected in-game tests run again, and it's merged once CI is green. Then the next step starts from the new main.

## The steps

Ordered so that what later steps stand on comes first: the test suite green, then tables and text (which sounds,
the sky, items and dens use), then the parts with the most for a mod.

### 1. Clean ground: the tab keys and UE4SS's crashes

**The gap.** Since build 26337109 the pause screen moves between its tabs with the arrow keys. A tab of a mod's own
gives its page the keyboard (`focus`, on by default), and its controls take the arrows, so the player can't get
back to the game's tabs. `test_ui_tab`, `test_ui_inventory_tab` and `test_ui_lua` fail. Separately, UE4SS crashed in
its own code at least three times on 2026-11-03, with no mod's code on the stack (verified.md). The test mod hooks
and unhooks `ClientRestart`, the first suspect.

**Find out.**
- How the game's own panels share the arrows with the tab row: `inspect` the pause screen's `NavControls` and a
  panel's controls while the Controls tab shows, and watch the screen's `OnListenCommand` with a hook while the
  arrows are pressed on the game's own panels.
- The crashes: the game's crash records (`python wcmods.py cpp crash`), UE4SS's source for unhooking
  (`UnregisterHook` while hooks are being called), and a loop that hooks and unhooks `ClientRestart` 50 times.

**The calls.** `ui::tab` keeps the tab row working: Left and Right on a control that doesn't use them (a button, a
check box, the page itself) go to the game's tab row, and `focus` gives the page the keyboard only on Down or Enter,
as the game's panels take it. If the crash is the SDK's unhook, `unhook` from inside a callback is deferred to the
end of the frame.

**Proof.** The three tab tests pass; a new test walks to the mod's tab and back with the arrows. The unhook loop
runs without a crash (or the crash is pinned to UE4SS and written up, with the SDK avoiding it).

### 2. The game's tables, live

**The gap.** The game keeps most of what it is in DataTables (items, characters, attacks, tuning, the sky, sounds).
A data mod changes them in a pak at install; a C++ mod can't read a row or change one while the game runs.

**Known.** `UDataTable` reflects its `RowStruct`; the rows are in its native `RowMap` (`TMap<FName, uint8*>`). The
tuning manager reflects nothing (re-roadmap, "Tuning"), so where `TuningData` sits at runtime is unknown. 221 of its
441 keys are whole strings in the exe.

**Find out.**
- `RowMap`'s offset in a `UDataTable` on this build (read `DT_QuestObjectsInfo` in game, one object by path, and
  compare its row count with the cooked file's 412).
- Where the tuning manager keeps `TuningData`: its memory read once for pointers to objects of class `DataTable`,
  and the code of one tuning read (`Gameplay.Exploration.MaxLevel`, known from the level component) to see what it
  looks the key up in.
- Which keys the code reads (the roadmap's step 1 static part): `tools/re/tuning_read.py` sorts the 441 keys into
  read, built from a pattern, and not named, into `wcmods/exe/tuning_read.json`.
- Which reads are live and which are taken once (the run speed is read into the movement component at start: a
  live change needs the component changed too, or a new level).

**The calls.** `wcmods::table(L"DT_QuestObjectsInfo")` (by name or path) gives a `Table`: `row_names()`, `row(name)`
as a struct `Value` that `get`/`set` work on, `rows()`, `add_row(name, from)` (a copy of a row), `remove_row(name)`.
`wcmods::tuning(L"Gameplay.Exploration.MaxLevel")` and `set_tuning(key, value)`, and `tuning_named(key)` (whether
the game's code names the key, from `tuning_read.json`).

**Proof.** Unit tests on a fake `RowMap` and a fake tuning store. In game: the item table's row count and one row's
fields; `set_tuning` on the run speed and the cat's speed measured as the data-save test does; a row added and read
back.

### 3. The game's words, live

**The gap.** Every line the game shows (dialogue, names, item names, the HUD) is a key of the string table
`SwtStrings`, loaded from `Strings_<language>.csv`. A C++ mod can't read a line by its key or change one while the
game runs, and the roadmap's step 2 (does an edited line show in a talk) was never checked.

**Known.** `KismetStringTableLibrary` reflects reading: `GetTableEntrySourceString`, `GetKeysFromStringTable`,
`GetRegisteredStringTables`. Nothing reflected writes one. An FText made from a string table key shows its entry's
display string, a shared string that every text bound to the key reads when it's drawn.

**Find out.**
- Whether `SwtStrings` is a `UStringTable` asset or a table registered from the CSV by native code (a find by path,
  then `xrefs.py` on `SwtStrings` in the exe).
- Where an entry's display string is, and whether writing it shows on screen at the next draw (the area name or a
  quest title on the HUD).
- If the registry is native only: a signed global (a new kind beside `NATIVE`: an address read from an instruction
  of a signed function), so the SDK can reach `FStringTableRegistry`.
- The roadmap's step 2, in game: a line given a new value in a mod's `names.json` shows in a talk (a camp cat's
  filler talk, read from `mcGuiTextParagraph`), and the same with `set_text`.

**The calls.** `wcmods::text(L"STR_CAT_NAME_12")`, `set_text(key, words)`, `restore_text(key)`, `text_keys(prefix)`.

**Proof.** Unit tests for the string layout and any new signing kind (`tests/unit/test_signatures.py`). In game:
`set_text` on a key the HUD shows, read back from the widget; a talk's line before and after.

### 4. Sounds and music

**The gap.** C++ plays a game sound by id. It can't swap or silence one, play a sound asset by path, stop what
plays, choose the music, or set the volumes, and nobody knows whether `AudioEvents.csv` in a mod's pak is read.

**Known.** `BP_WrcAudioManager_C`: `AudioEventsInfo` (id to soft path, 390), `AudioEventsMap` (id to loaded sound,
389). `USwtNativeAudioManager` reflects `K2_PlayEventOf`, `K2_PlayAudioOf`, `PlayEventAsset`,
`K2_PlayEventOfAttached`, `PauseAllEvents`, `SetMusicVolume`, `SetEffectsVolume`, `SetVoiceOverVolume`,
`SetMasterVolume`, `SetParameterValue`, `SetMixModifierState`, `GetAudioAssetDuration`. Music changes with places
(`AWrcMusicSourceTrigger`, `AWrcMusicParamTrigger`).

**Find out.**
- Whether changing `AudioEventsMap[id]` changes what the game itself plays for that id (a menu sound played by a
  Blueprint, whose `K2_PlayEventOf` an after-hook sees with the component it returns).
- The roadmap's step 3: a temp mod's `data.json` changing row 78 (`cat_step`), installed, and
  `AudioEventsInfo["cat_step"]` read in game.
- How music plays: what the music triggers call, which audio component holds the music now, and how a change of
  place switches it.

**The calls.** `replace_sound(id, other)`, `mute_sound(id)`, `restore_sound(id)`, `play_sound_asset(path, at)`,
`stop_sound(component)`, `sound_duration(id)`, `music()`, `play_music(id)`, `stop_music()`,
`set_volume(wcmods::Volume::Music, 0.5)`, `pause_sounds(on)`, `sound_parameter(id, name, value)`.

**Proof.** Unit tests for the id map edits on a fake map. In game: a swapped menu sound comes back from the game's
own play as the other cue; muted, no component; the music's cue before and after `play_music`; the volume read back.

### 5. The sky's values

**The gap.** The sky's presets switch, but their values (sun, skylight, fog, clouds, horizon, stars) can't be
changed, so a mod can have "night" but not "foggy dusk".

**Known.** `AWrcSkyboxActor.SkyParamsDB`, a DataTable, presumably of `FWrcSkyBoxStruct` rows; presets by
`ESkyboxPostProcessEnum`; the actor fades back to the area's preset in about 5 s, and `set_sky` holds one.

**Find out.** The table's asset and row keys (per preset?), with step 2's `table()`; whether a row changed before
`ApplyStraight` changes the look; which component each field ends in (the height fog's density, the sun's
intensity); whether a preset's row can be added for a look of the mod's own.

**The calls.** `sky_values(preset)` (the row, to `get`/`set`), `set_sky_value(preset, field, value)`,
`sky_look(values)` (a held look of the mod's own, from a preset's row with changes), `restore_sky_values()`.

**Proof.** Unit tests on the hold with a look. In game: Night's fog changed and applied, the fog component's
density read back; restored afterwards.

### 6. Cats of a mod's own

**The gap.** Lua's `Game.npcs` makes cats that stand, walk paths, wear a look, carry a label and a Talk prompt, and
answer the Interact key; C++ has `spawn` for plain actors only.

**Known.** All of it, from the Lua module (`wcmods/lua/game.lua`, `Game.npcs`, about 600 lines), the walking-pawn
rework and the 50-cat stress test ([npc-walking-stress.md](npc-walking-stress.md)): the walking pawn
(`BP_WalkingNPC_Character_Base_C`), its `walkTo` with avoidance, the label range, the prompt's key from the game's
`ECommands`, the fixed look.

**The calls.** `wcmods::npcs::spawn({look, at, label, prompt})` gives an `Npc`: `location`, `distance`, `near`,
`face`, `move_to`, `walk_to(points, on_done)`, `walking`, `stop`, `remove`, `set_label`, `set_prompt`,
`on_interact(fn)`; `npcs::all()`.

**Proof.** Unit tests for what isn't the game (path bookkeeping, the prompt's key). In game: one spawned beside the
cat with a look, walked 5 m, `Player_Interact` given near it fires `on_interact`, removed and gone.

### 7. Conversations

**The gap.** A C++ mod can't start one of the game's conversations, show a line of its own in the talk box, give
the player answers, or hear which answer was picked.

**Known.** Conversations are graphs (`UQuestDialogue`, `UNpcDialogue`, `UBondDialogue`), decoded in Python
(`wcmods/dialogue.py`, all 91 packages). `USwtQuestSequencerManager.PlaySequenceDialogue(tag, npc, player, clanLeaf,
rankLeaf)` plays one by tag (untried). Lua's `Game.dialogue` shows lines in the talk box (`WBP_QuestGiver_Dialogue_C`)
with a claim so two scripts don't fight over it. The box has four answer buttons (`mcButton1..4`), collapsed when
Lua uses it.

**Find out.**
- `PlaySequenceDialogue` with a camp cat and a filler tag (the roadmap's step 9, in game): the box shows the line.
- How the box reports an answer: a hook on its buttons or the graph's resolve action while a game talk with
  choices runs.
- Whether the answer buttons can be shown and labelled for a talk of the mod's own (the rest, 3).
- The loaded graph objects are reflected: read one's nodes in game and compare with `dialogue.py`.

**The calls.** `play_conversation(tag, npc)`, `say(speaker, words, {answers}, on_answer)`, `hide_talk()`,
`talk_showing()`, `conversation(tag)` (the loaded graph's lines and answers), `on(Event::Answer, fn)`.

**Proof.** In game: a game conversation started by tag shows its first line; a mod's line with two answers, the
second picked by command, reaches `on_answer` with 2.

### 8. Bonds

**The gap.** Bonding is the game's relationship system, and nobody knows where a bond is kept or what an answer's
`Score` adds.

**Known.** The save has a `Bonding` map (empty in the one save looked at). `EBondingRanks` and `EBondingTypes` name
the ranks and kinds. The pause screen's Bonds panel (`UGuiPausePanelBonds.mcGuiBondsList`) lists cats with a bar
each. Dialogue answers carry `Score` and `ClanBonding`.

**Find out** (a story-mode cat, with a backup): the slot's JSON before and after a talk whose answer has a score;
one of the Bonds panel's items read for where its bar's value comes from; `xrefs.py` on `Bonding` for the native
store; whether the store is the live save state (`save_state(L"Bonding")`) or a component's member.

**The calls.** `bonds()` (each cat's id, name, value, rank, kind), `bond(cat)`, `set_bond(cat, value)`,
`on(Event::Bond, fn)`.

**Proof.** In game: a bond set, the Bonds panel's bar for that cat read back, and the save after `save_game`.

### 9. Looks and the clan

**The gap.** A cat's looks are a struct C++ can read by path but can't change in a way the mesh shows. The clan's
cats (who they are, their roles, their looks) aren't reachable as a list.

**Known.** The cat's `MeshCustomizationComponent` (`WrcCustomizableMeshComponent`) reflects `CustomData` (`FCatCustomData`: clan, body, ears, fur colour, name ids,
size...). `UWrcNPCGenerationManager` reflects `NPCClansData` (role to looks), `NarrativeCustomDataMap`,
`NarrativeRoleMap`, `FriendsDenCharacters`, `RemainingRogueNames`. The save's `NPCData` holds each cat. Accessories
work through Lua's `models.lua` (#58).

**Find out.** Which call applies changed `CustomData` to the mesh (the component reflects `RefreshShape`, a native
event, and the `Validate*Index` checks; tried on your cat); what `NPCData` holds beyond looks (the rest, 4: a save diff across a role change); whether the
generation manager's maps change the camp cats when they're made.

**The calls.** `looks(cat)` (to `get`/`set`), `set_looks(cat, changes)` (applied), `wear(cat, accessory)`,
`clan_cats()` (each with name, role, looks, actor when it's out), `role(cat)`.

**Proof.** In game: your cat's fur colour changed and the mesh's material parameter read back; the roster's count
and names compared with the save's `NPCData`.

### 10. Things on the ground, and a mod's own animations

**The gap.** Lua drops pickups with a mod's model and plays a mod's own animations; C++ can only play the game's
montages by tag.

**Known.** Lua's `Game.items.drop` (#59) and `Game.anims` (#60), seen working; the item table (`DT_QuestObjectsInfo`)
through step 2.

**The calls.** `drop_item(tag, count, at)` (a pickup to collect), `item_info(tag)` (name, icon, kind, effect, from
the table), `animations()`, `play_animation(cat, id)`, `stop_animation(cat)`, `animation_playing(cat)`.

**Proof.** In game: a pickup dropped beside the cat, collected with `Player_Interact`, the inventory up by one; a
mod's animation from the test kit played and stopped.

### 11. Quests and the story

**The gap.** `start_quest` and `give_quest` were never tried; objectives can't be completed from code; story scenes
can't be played or skipped by tag; dilemmas can't be shown or answered; the progression and mood keys are unknown.

**Known.** The quest manager's `Quests`; the sequencer manager's `ActiveSequences`; skipping through the skip popup;
`USwtAdventureDilemmaComponent.ShowDilemmaPopUp(sequenceId)` and the dilemma table; the save manager's
`Get/SetMoodData`, `Get/SetGameProgressionData`.

**Find out.** `start_quest(L"Quest.Procedural.Survival.Gather")` in the forest (the HUD's objective line); the quest's
reflected functions for objective progress; how a story scene starts (the sequencer manager's functions, tried with
a scene the cat has seen); a dilemma shown and its choice read; the mood and progression keys from the save.

**The calls.** `start_quest` and `give_quest` proven; `advance_objective(quest, id, n)`, `complete_quest(quest,
result)`, `play_scene(tag)`, `skip_scene()`, `scenes_seen()`, `show_dilemma(id)`, `on(Event::Dilemma, fn)`,
`mood()`, `progression(key)`.

**Proof.** In game: a gather quest started, its objective on the HUD, advanced to done, and `QuestStatus` seen
firing.

### 12. Fights

**The gap.** Fights are read only: a mod can't start one with a chosen animal, end one cleanly (`EndCombat` leaves
the cat without a body), pick a move, or rely on the five fight events, never seen firing.

**Known.** A fight starts by pouncing on a roaming animal from behind (the project's notes); the director's parties,
turn order and moves are reflected; the combat manager reflects `EndCombat`.

**Find out.** What the pounce calls to start a fight (hooks on the combat manager and the director while pouncing);
the game's own ending (a fight won normally, hooked) and whether calling it ends one cleanly; how a turn's move is
chosen (the combat control component's functions); the five events, seen in one fight.

**The calls.** `start_fight(animal)`, `end_fight(won)`, `flee()`, `choose_move(index)`, the events proven, and
`on(Event::Damage)` able to change the damage.

**Proof.** In game: a fight started from code, `CombatStart`, `Damage`, `TurnEnded`, `Status` and `CombatEnd` seen,
the fight ended, and the cat walking afterwards.

### 13. Dens and clan life

**The gap.** Dens (decorations on hotspots), building, and the minigames are out of reach.

**Known.** `ASwtAdventureHousingHotspot`: `DecorationsDB`, `RequiredRank`, `HotspotSize`,
`OnOptionPicked(DecorationTag, Cost, bReadyToGo)`, `OnDelete`; den doors; `USwtAdventureMinigameComponent` with
`ActiveMinigame` and `OnEndMinigame(bSuccess, Factor)`.

**Find out.** In a den: a hotspot's `OnOptionPicked` called with a decoration's tag and nothing to pay, and whether
it builds and saves; the build time in real hours (the rest, 10); what starts a minigame and how its end is
reported.

**The calls.** `dens()`, `hotspots()`, `decorations()` (the table's rows), `place_decoration(hotspot, tag)`,
`remove_decoration(hotspot)`, `minigame()`, `end_minigame(success)`, `on(Event::Minigame, fn)`.

**Proof.** In game: a decoration placed on a hotspot, its mesh read back, and the save after `save_game`.

### 14. The map, travel, the HUD and the camera

**The gap.** Lua's HUD banner and objective line, map markers and the clock hold have no C++ calls; nothing reaches
fast travel, photo mode or the camera.

**Known.** Lua's `Game.hud`, `Game.mapMarker`, `Game.time.hold` (seen working); travel spots by den entrances (the
Travel prompt); `UQuestDialogueActionFastTravel`; `APhotoModeCameraActor`; the exploration camera (re doc, "The
exploration camera").

**Find out.** What a Travel prompt calls, and whether a place can be travelled to from code; the photo mode's
popup opened by its command; the camera's distance and field of view while exploring.

**The calls.** `hud_banner(text, seconds)`, `hud_objective(text)`, `map_marker(at, icon)`, `hold_time(h, m)`,
`travel(place)`, `places()`, `photo_mode(on)`, `camera()` with `distance`, `fov`, `set_distance`.

**Proof.** In game: the banner's text read back from the HUD; a marker on the map; a travel to camp and the cat's
place after it.

### 15. Effects, movement and senses

**The gap.** No visual effects from C++; movement values only through raw properties; the player's scent sense
can't be driven.

**Known.** `NiagaraFunctionLibrary` (engine, reflected); the game's effect managers; the character movement
component (engine, reflected); the movement loader's tuning keys; `USwtAdventureExplorationSenseComponent`.

**The calls.** `spawn_effect(path, at)`, `game_effect(tag, at)`, `movement(cat)` with walk, run, sprint, jump and
climb speeds, `set_sense(on)`.

**Proof.** In game: an effect spawned and its component alive; the run speed changed and measured; the sense on.

### 16. Every part accounted for

A last pass over the class dump: every manager and component class the game has gets a line in SDK.md's coverage
table (the C++ call that reaches it, or why none does), the doc check (`selftest._cpp_sdk`, run by
`tests/unit/test_mods.py::test_cpp_sdk_headers_documented_and_tested`) covers the new headers, the roadmap's statuses are brought up to date, and the remaining native functions any step needed are
signed. It also takes step 2's static half: `tools/re/tuning_read.py` sorts TuningData's keys into those
the code names, those built from a pattern, and those it doesn't name (`wcmods/exe/tuning_read.json`), for a
call that says whether changing a key can do anything. Its proof is the whole in-game suite, run once on a fresh game.

## Not in this plan

- **The Lua side.** Each finding is written up so Lua can follow later; no Lua calls are added here.
- **New kinds of content:** a new area, prey kind, trait, coat or eye slot, or weather. The game has no class,
  enum or table for them (re-roadmap, "Not in this plan").
- **Den visits online.** They go through the game's server and an account.
- **Making cooked content** (a mod's own sounds, models, scenes). The SDK plays and places whatever is loaded by
  path; making the packages is the content pipeline's work (re-roadmap, the rest, 11 and 12).

## Status

Each step's pull request updates its line.

| Step | State | Pull request |
|---|---|---|
| 1. Clean ground | done: the arrows on a tab's page; the crashes read (UE4SS's Lua runtime, not C++) and unhooking proved under load | #116 |
| 2. Tables, live | done: every DataTable's rows read, changed, added and taken out; TuningData read and changed, the game's own lookup signed. Which keys the code names (`tuning_read.json`) moved to step 16 | #117 |
| 3. Words, live | done: any key's words read, changed (every text made from it shows them) and put back; the key a text came from. No signed global was needed (the engine's reflected string-table calls and UE4SS's text data reach it). The roadmap's step 2 in a talk moves to step 7, which plays talks | #118 |
| 4. Sounds and music | done: an id's sound replaced, muted and put back (the game's own plays follow); the music read, played, stopped; volumes; the pause. The roadmap's step 3 answered: a data mod's `AudioEvents.csv` reaches the game. A sound by its asset path waits for a loader (step 10) | #119 |
| 5. The sky's values | done: every preset's values read and changed live in the sky's own copy (a new hidden member), put back; the table they come from. The roadmap's step 7 answered: the day cycle doesn't rewrite them, the sky fades back to the area's preset (step 1 of #111) | #120 |
| 6. Cats of a mod's own | done: spawned with a look, kept, moved, walked (stall detours), labelled, prompted, Interact heard from the controller; an asset loader and an enum lookup with them. Map markers move to step 14 with the map | #121 |
| 7. Conversations | done: the box with a mod's lines and answers' words; any of the game's talks read from its graph (lines, speakers, bonding variants, answers, actions) and played in that box, answers chosen, a mod's own talks too; an edited line shows in a talk. The game's own player (`PlaySequenceDialogue`) crashes the game when its box is closed any way but by its scene, so it isn't used (reverse-engineering.md, "Talks in game"). Answers come by number from the mod's keys, not the box's buttons | #122 |
| 8. Bonds | done: every clan's and story cat's bond read, added to and set through the game's own bond code (four native functions signed), the ranks from the tuning, your clan's story roles; the Bonds panel and the save show a change. The save manager's reflected progression calls turned out to be account-wide (and a read adds a key): documented and the test's stray key fixed. What a talk's answer adds is left open | this branch, `claude/cpp-bonds` |
| 9. Looks and the clan | not started | |
| 10. Ground items, a mod's animations | not started | |
| 11. Quests and the story | not started | |
| 12. Fights | not started | |
| 13. Dens and clan life | not started | |
| 14. The map, travel, the HUD, the camera | not started | |
| 15. Effects, movement, senses | not started | |
| 16. Every part accounted for | not started | |
