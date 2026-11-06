# The Lua SDK, brought up to the C++ SDK

The C++ SDK grew through three programs ([cpp-sdk-coverage.md](cpp-sdk-coverage.md), [cpp-sdk-gaps.md](cpp-sdk-gaps.md),
[cpp-sdk-ai.md](cpp-sdk-ai.md), #116 to #151). The Lua side (`wcmods/lua/game.lua`'s `Game.*`, documented in
[scripting.md](../scripting.md)) wasn't changed alongside. This plan brings `Game.*` up to the C++ calls wherever
UE4SS's Lua can do it, and fixes the bugs the C++ side found and fixed that the Lua side still has.

As before, the steps are done one at a time in one session, each its own pull request, reviewed and merged before the
next starts.

## What Lua can and can't reach

UE4SS's Lua calls reflected functions and reads and writes reflected properties. It reaches unreflected members
through `Game.hidden` (custom properties: the Int, Float and Byte members of `game.HIDDEN`), and it has UE4SS's own
`UDataTable` (`FindRow`, `GetRowNames`, `ForEachRow`) and `TMap` wrappers.

What it can't do:
- call the game's native functions (`game.NATIVE`: adding items, the bonds, a cat's look, story scenes, unlocking a
  place, the tuning lookup);
- read the C++-only hidden members (`game.CPP_ONLY`: a map, an array or a double: the inventory's items, the tuning
  table, the AI's running tree, the talk tables, the sky's presets, the world map's translation);
- read raw memory (the fight AI's chances map, a fighter's moves array, a talk's words written in place).

Most of what the C++ SDK does is reflected calls and properties, with state and timers of its own, so Lua can do it
the same way. Steps 1 to 7 are that. Step 8 is the rest, which only a C++ helper could give Lua.

## The gaps

| Area | In C++, not in Lua (`Game.*`) | Step |
|---|---|---|
| Bugs fixed in C++ only | the talk box leaves your cat "in a talk" (animals stop noticing it, pounces start nothing); `say` while the box fades out leaves it faded; asking a quest's status writes the quest into the save; a quest under way reads no status; `Game.items.drop` takes any tag (a bad one gets into the save and crashes the game at quit) and drops where Interact can't reach; the save cache misses a same-size rewrite; the clock hold drifts | 1 |
| The game's AI | an AI's controller, tree running or asleep, stopped and restarted, its blackboard's keys read and written, another tree run, its trees set, the trees as data; moving an AI, facing, the nav mesh; noticing, ignoring, calming, fleeing, following | 2 |
| Animals and walking cats | the kinds, an animal put in the world (a borrowed generator), the animals near, removing one; the walking cats and their paths, a path given, a cat stopped and walked on | 3 |
| Fights | your cat's fighter, a fight started the player's way, the fight menu (attack, rest, flee), a fight ended, its dilemma answered, your cat's turns taken for it (`auto_fight`); a hit changed in the damage event | 4 |
| Story | the current objective, collecting it, finishing one; the scenes listed, playing, seen, skipped; the progression flags; your cat's mood | 5 |
| Tables and words | the DataTables listed, read, changed, a row removed; the game's words read by key | 6 |
| The rest of the world | console commands; the save's hash; item names, icons and kinds; the sky's presets; sounds, music and volumes; pausing; a montage; effects and movement; your cat's speeds; the camera; dens; places and travel; photo mode; looks read, accessories, the clan's cats | 7 |
| Only through C++ | items added and taken away (and the live inventory), the bonds, a cat's look set, story scenes played, a place unlocked, travel through the map, the AI's running tree and task, the fight AI's chances and an enemy's moves, the tuning, words changed, story talks filled from their tables, a talk's bond answers, a herb's use, a den decoration's cost | 8 |

## 1. The bugs C++ found

**Known** (each seen in game on the C++ side, cited where it was fixed):
- **The talk box.** `Game.dialogue.hide` takes the box down (`RemoveFromParent`) but leaves the player controller's
  talk flags on (`WCM_TalkFlags`, 0x1 and 0x20: Talk.hpp's `end_box_talk`). `WCM_TalkFlags` is an IntProperty, so
  Lua has it in `Game.hidden`.
- **`say` during the fade-out.** The C++ box plays its fade-in again when a line comes in while it's fading
  (Talk.hpp). Lua cancels the removal but plays no fade-in, so `showing()` is true while the box can't be seen.
- **Quest status.** The game's status calls add any id they're asked about to the save's `QuestProgression`, so C++
  only asks about aliases the manager holds (Story.hpp); Lua's `status`, `result`, `successes` and `objectives` ask
  about anything. And `describe` reads the quest object's own status, None until it ends: the game keeps progress
  by its `QuestAlias`, which Lua doesn't know.
- **Dropping an item.** C++ refuses a tag that isn't under `Gameplay.Inventory` (a reflected `MatchesTag`), and
  drops 50 cm in front of your cat, where Interact reaches (Items.hpp).
- **The save cache** checks the file's size; C++ also checks its write time, since a same-size rewrite left a read
  a save behind. Lua's `io` has no file time: a compare of the file's head instead.
- **The clock hold** sets the clock twice a second; C++ every frame.
- **Docs:** scripting.md says the `damage`, `turnEnded`, `status` and `questStatus` events haven't been seen firing
  (C++ has seen them, on the same hooks) and that a fight can't be ended (`end_fight` does it). A hook on a function a
  Blueprint calls natively hands the caller's variables as parameters (C++'s `has_params`); UE4SS's Lua hook can't
  tell, so scripting.md warns of it.

**Proof.** In game: animals notice your cat after `Game.dialogue` (as `test_ai_notice` after `test_talks`); the
flags back at 0; a quest's status read leaves the save as it was; a bad tag refused and a good one picked up by
Interact; the clock held to the minute.

## 2. The game's AI

**The calls.** `Game.ai`: `controller`, `brain`, `running`, `asleep`, `stop`, `restart`, `keys`, `get`/`set` (a
blackboard key by its type), `runTree`, `trees`/`setTrees`, `treeNodes`; `moveTo` (a place or another actor, done
with how it ended), `stopMoving`, `moving`, `face`, `navPoint`; `detectionFlags`, `ignorePlayer` (one, or every
animal near), `noticePlayer`, `calm`, `trackingPlayer`, `flee`, `follow`/`stopFollowing`.

All of it is reflected (Ai.hpp): the controller's `MoveToLocation`, `RunBehaviorTree`, the brain's `StopLogic` and
`RestartLogic`, the blackboard's `SetValueAs*`, the detection sphere's collision response, the animal's own
`OnCharacterDetected`/`OnCharacterLost`. The walk engine (arrival, stalls) is `Npc:walkTo`'s, shared. The running
tree and its task need the brain's `InstanceStack`, an array: step 8.

**Proof.** In game, as `test_ai`, `test_ai_move`, `test_ai_notice` and `test_ai_trees` do from C++, and the same
values from both (the C++ test mod records them in the same game).

**Done.** All of it but the running tree and its task (step 8), with `Game.animals.near` from step 3 (the stealth mode
needs it). The trees as data match C++'s node for node. A byte member's enum can't be asked for from Lua, so the
settings in the game's eight trees are named from a table of their enums.

## 3. Animals and walking cats

**The calls.** `Game.animals`: `kinds()` (DT_Combat_Generator's parties, through UE4SS's `UDataTable`), `spawn(kind,
place, {respawn})` (a placed generator borrowed, as Ai.hpp's `spawn_animal`: its tags set to the kind, moved, given
back after), `near(radius)`, `remove`. `Game.walkers`: `near(radius)` with their paths, `walkPath(cat, points, {loop,
speed})`, `ownPath`, `stop`, `walkAgain`, `walking`.

**Proof.** In game, as `test_ai_spawn` and `test_ai_walk`: a rabbit spawned and fought for its rewards, the generator
given back; a mod's cat walking a loop, stopping for a talk.

**Done.** All of it, but the fight with the spawned rabbit (step 4: fights from Lua). `Game.walkers.walking` can't check
the running tree is `BT_WalkingNPC` (step 8). The code is a do-block of its own after `Game.ai`'s: each block's locals
count toward the main chunk's 200 while it's open, and `Game.ai`'s had two to spare.

## 4. Fights

**The calls.** `Game.combat` (`Game.fight` is already the fight-now function): `cat()`, `start(animal)` (behind it
and pounce), `menu()`, `attack(n)`, `rest()`, `flee()`, `moves()`, `finish(won)`, `dilemma()` and `answerDilemma(n)`,
`autoFight(on)`; `onDamage(fn)` able to change the hit (`hookRaw`, as the C++ handler does); `Game.command(name)` for
the game's controls (C++'s `command`; its `console` is step 7's). `Fighter:setAITier` is there already.

**Proof.** In game, as `test_fights` and the fight half of `test_ai_fight`: fights won, fled and lost from Lua.

**Done.** Moves are numbered 1 to 4. `autoFight` picks the move that costs the most stamina, not the most damaging:
the moves' damage is in an array Lua can't read (step 8). A fight with a spawned rabbit (step 3's open check) was the
rabbit's party, where the world let a fight start.

## 5. Story

**The calls.** `Game.quests`: `current()`, `collect(target)`, `finishObjective`, `alias`, and `objectives` with
their targets; `Game.scenes`: `list()`, `playing()`, `seen(tag)`, `skip()`; `Game.progression(path)`;
`Game.mood`/`setMood` (the save manager's, not a cat's).

**Proof.** In game, against `test_story_matches_lua`'s C++ values.

**Done.** Played as C++'s `test_quests` does, on a backed-up save put back after. Playing a scene is a native call
(step 8).

## 6. Tables and words

**The calls.** `Game.tables`: `list()`, `rows(name)`, `row(name, key)`, `set(name, key, path, value)`,
`removeRow`. Adding a row stays C++'s: UE4SS's `AddRow` throws on this engine (Tables.hpp). `Game.words(key)`,
`wordKeys(table)`.

**Proof.** In game: a row read and changed from Lua, read back from C++.

**Done.** `Game.tables` (`list`, `get`, `rowNames`, `rows`, `row`, `set`, `removeRow`), `Game.words` and
`Game.wordKeys`. A row changed from Lua is read back by a fresh lookup (C++'s reading goes through the same memory).
`wordKeys` takes a prefix, as C++'s `word_keys` does. Changing words, and the tuning, are step 8's.

## 7. The rest of the world

**The calls.** `Game.command`, `Game.save.hash`; `Game.items.info` (name, icon, kind, from the item table) and
`isItem`; `Game.sky.presets`, `hold`; `Game.sounds` (play, swap, mute), `Game.music`, `Game.volumes`; `Game.pause`;
`Cat:playMontage`; `Game.effects` (Niagara, the game's effects), movement, jump and gravity; `Cat:speeds`/`setSpeeds`
and `Game.camera`/`setCamera` (their floats are in `Game.hidden` already); `Game.dens` (list, enter, hotspots,
remove a decoration); `Game.places` (list, the travel map opened), `Game.photo`; `Cat:look()` in full,
`Game.accessories`, `Game.clanCats`, `Game.roleOf`.

**Proof.** In game, each against its C++ test's values.

## 8. Only through C++

What needs a native function, a C++-only member or raw memory: the live inventory and adding or taking items, the
bonds, setting a cat's look, playing a story scene, unlocking a place, travel through the map, the AI's running tree
and task, the fight AI's chances and an enemy's moves, the tuning, changing words, story talks, a talk's bond
answers, a herb's use, a den decoration's cost.

The way exists: a C++ mod puts `WCModsCpp` into every Lua mod's state (Mod.hpp), and `WCModsCpp.ui` already gives
Lua about 75 C++ functions (UiLua.hpp). A small C++ helper built with the SDK could add `WCModsCpp.native` the same
way, and `Game.*` would use it when it's there and say so when it isn't.

**To decide first:** how such a helper reaches players. The repo keeps no compiled code, and building it needs Visual
Studio and UE4SS's source. It could be an addon built from its own repository and downloaded from its release, as
the other addons are, opt in. Or these calls stay C++'s only.

## Status

| Step | State | Pull request |
|---|---|---|
| 1. The bugs C++ found | done | #153 |
| 2. The game's AI | done | #154 |
| 3. Animals and walking cats | done | #155 |
| 4. Fights | done | #156 |
| 5. Story | done | #157 |
| 6. Tables and words | done | #158 |
| 7. The rest of the world | part one done (sky, sounds, effects, movement, speeds, console) | this branch, `claude/lua-world` |
| 8. Only through C++ | to decide | |
