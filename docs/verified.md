# What's verified

What wcmods checks by itself, and what has been seen working in the game, by date. The unchecked list
at the end is as much the point as the rest: a thing listed there may work, but nobody has watched it.
[agent.md](agent.md) says how the in-game checks are run.

## The checks

`python -m pytest` runs the game-free checks (`tests/unit/`): the formats, every Lua module and script
compiling with its settings in, mod .zips and what's refused, the key remapper, setup in temporary
folders. `python wcmods.py selftest` checks, against your install:
- **Game files:** reading the paks, container and save; the eye atlas layout. wcmods' own Kraken
  decoder (the compression the game's files use) decodes samples Oodle itself compressed, and the
  game's own blocks the same as an oo2core DLL when one is set.
- **Writers:** paks and IoStore containers read back identically, with correct BLAKE3 chunk hashes.
  The pak's directory index stores file names the way the game's own pak does (see below).
- **CSV editor:** reproduces all 67 runtime tables byte-for-byte.
- **Cooked assets:** the item table's 412 rows read and write back byte-for-byte; texture copies get
  the IDs the game's own packages have; the accessory look lists read back with new looks added; every
  node and edge of the game's 91 dialogue graph packages (27,900 objects) decodes by its class and writes
  back byte-for-byte, and each package rebuilt from them is the game's byte-for-byte.
- **Animations:** all 757 of the game's animation sequences read and write back byte-for-byte (519 in ACL,
  229 in Unreal's per-track codec, 9 in its constant-key one) and decode, the ACL ones with their own
  skeleton's pose; each animal's template takes new keys and reads them back (the ACL ones moved to the
  engine's own settings); every kind's start kit carries all its examples (49), and the game's Stretch
  and Idle (ACL), put in the cats' start kit and read back from it, give the same keys.
- **Save editor:** changes only the values it's told to, and writes the header (`Hash`, `Version`)
  back as it read it.
- **Game update signatures:** on a build wcmods was checked on, every class and value it reads is where
  `game.HIDDEN` says; and with the exe's fingerprint changed, as on another build, a class whose
  signatures are taken away keeps nothing, and the level component's eight values are found by their
  own signatures, where they were or where an update moved them (since 2026-10-28; before, it had
  none).
- **UE4SS scripts:** the generated Lua has balanced blocks and brackets (a light structure check;
  there's no Lua interpreter to fully parse it). Builds also warn if any UE4SS script fails it.

## Confirmed in game

**2026-10-23:**
- The mod container loads, and eye palettes change the cats' eyes.
- The mod pak's files replace the game's: an edit to the game's English text (`Strings_EN.csv`)
  renamed the player's Otterpaw to Mothpaw on screen. Paks built by earlier versions of wcmods
  loaded, but the engine found none of their files, so game data, replacement files and text edits
  had no effect; install again to rebuild them (`status` and the studio say so). Pak version 12
  stores file names in the directory index as UTF-8 with no terminator (folder names keep theirs).
  Names written the older way read back with a trailing NUL, so the engine never matched them.
- UE4SS runs, finds the colour tables on `BP_WrcGuiManager_C`, and its writes take effect.
- Your cat's own colours (`cats.json`) show on your cat in the world, on the main menu, and in
  thumbnails, which are taken again once your colours are on. Other cats keep theirs.
- Mouse look turns and tilts the camera, gives the cursor back in menus, and toggles with F6
  (see its known issues above).
- Edited saves load, and the game keeps the edits when it saves again; a Level change made with the
  save editor was accepted. The save's 64-bit `Hash` isn't a checksum: the game makes a new one
  from the clock and an address at every write and doesn't check it (read from the code, see
  [reverse-engineering.md](reverse-engineering.md#the-save)). The tool keeps the original value, and
  the game accepts it.
  Save edits are applied after a backup: restore one from Settings and repair (or
  `python wcmods.py restore latest`) if anything goes wrong.
- Edited key bindings in the save are ignored, and the game's rebinding screen doesn't work on PC
  (see the README, [Remapping keys](../README.md#remapping-keys)).
- The key remapper (`wcmods play`) moves keys while you play and leaves other windows and the title
  screen alone (movement on T/F/G/H: the new keys moved the cat, WASD did nothing while playing, and
  remapping switched off with another window in front and on the title screen). The game ignores
  edited bindings in the save: tested with the mouse in the camera slots, and with keyboard keys only
  and the custom-controls switch (`SettingsData/CustomControls`) on.

**2026-10-24:**
- Mouse look's smoothing: with the mouse captured, the camera's lag is 0 and the picture follows
  the mouse exactly (`root y=-23.2`, `view y=-23.2` in the debug log), with even 17 ms frames. The
  game's own lag comes back in menus.
- `WCModsView` projects your cat's position to the same pixel as the engine's
  `ProjectWorldToScreen`.
- The mod menu opens with Insert and is readable at 1920x1080. The game draws its UI for
  3840x2160 and halves it, and the menu undoes that. Its live settings work.
- `WCModsWorld`'s kinds, from a survey of the classes around your cat. The Nearby page lists them,
  any kinds at once, and marks them on screen in their colours.
- The Cheats page: cheats switch on, and fly, ghost and cat size work. These are done by the menu
  itself, because the game undoes the engine's own.
- The studio refuses to install once wcmods has been updated under it. An old studio had put old
  scripts back.

**2026-10-24, items:**
- New herbs and materials show in the inventory with their names, descriptions and icons. Their
  recipes show at the medicine cat's bartering, and trading works.
- New textures load: icons from a PNG and recoloured ones, and a new collar look, worn in its new
  colour and made at bartering. Accessories you already have show as an empty slot there, the
  game's own too.

**2026-10-27, accessories' models** (build 26184573, a test mod's two looks for DogCollar, one from an
OBJ file and one from a GLB, each a ring with a bell: `WCModsModels` installed):
- A copy of DogCollar's mesh, 1.5 times as big, loaded from wcmods' container and showed on the cat's
  neck in the collar's look, bending with the neck as the cat groomed.
- In the inventory, each look worn showed on the picture of the cat in its own shape and colour;
  switching between the two and back to none left no shape behind.
- In the forest, the cat wore the ring and bell in its look while walking; the neck's mesh was the
  mod's (`SK_BellCollar`) and `CustomData` said DogCollar look 3.
- A mod made on the Items page (a GLB model and a JPEG picture, saved there as a PNG) showed the same
  way in the forest, the ring in the picture's stripes.
- Where it sits and see-through (`place`, `opacity`, `glass`): a ring made at the model's origin, put on
  the neck with the Items page's sliders (forward 11.7, up 16.4, tip 15, size 1.2) and set to 40% in a
  gold glass, sat on the neck in the inventory's picture and in the forest, the cat's fur showing
  through it. Switching from it to the game's own Dog Collar look showed the game's collar as it is.
- The other slots and the rest: a ring modelled at the origin, placed on a front paw as a new Oak
  Wrap look; the Dog Collar's own shape placed lower and a quarter bigger (`place` with no model); and
  Mud Marks as green glass on the hip. All three showed in the inventory's picture, in the forest and
  on the main menu's cat. With `SHP_Chubby` set to full on the body, fur and accessory slots by hand,
  the collar and the ring stayed on the cat as it filled out.

**2026-10-27, models on the ground** (build 26184573, a test mod's herb with a striped gem model and
picture, a material with a plain block model turned 30 degrees, and a herb `like` Comfrey Poultice
without a model; `Game.items.drop` for each):
- The gem and the block lay on the ground where they were dropped, the gem in its picture's stripes and
  the block plain grey; the pickup's own herb (Marigold, Horsetail) was hidden. The third lay as the
  game's Comfrey pickup.
- The cat collected the gem with Interact as usual: "Test Gem obtained", one in the inventory, and the
  pickup and its model were gone from the ground.
- A picture added to the block on the Items page (saved there as a PNG) showed on it in the forest.

**2026-10-27, a game animation replaced** (build 26184573, a test mod's `animations.json` with the cats'
start kit and `"clip": "A_CatMaster_Sleep_Loop_2", "replaces": "A_CatMaster_Trot_1"`):
- The install wrote the trot again (its keys from the sleep loop, fitted to the trot's 15 keys, its
  footsteps and curves kept, ACL moved to the engine's settings) and the game loaded it.
- Moving at the game's walking speed (174 cm/s, W held), the cat's head was 1.8 to 3.5 cm above its root
  bone and its spine 2.9 to 5.0: curled up as the sleep loop has it. The same moves without the mod: the
  head 14.1 to 15.6, the spine 11.7 to 13.1, the game's trot. Standing still before it moved, the head
  was at 14.2, the game's idle.
- `selftest`: the trot replaced by the kit's own trot gives back the game's keys within 4e-6 cm.

**2026-10-27, animations** (build 26184573, a test mod's `animations.json`: a wave made in Blender 5.2.3
from the cats' start kit, the same with claws out at 1.5 times the speed, a looping paddle as an emote
on F7 and as a script's swim, and a spin for mice and for birds; `WCModsEmotes` and `WCModsAnims`
installed):
- A sequence wcmods wrote first (the game's Stretch with a wagging tail, in a new package) loaded by
  its path and played on the cat through `PlaySlotAnimationAsDynamicMontage`, with its fur, tail, ears
  and build following.
- The mod menu showed an Emotes page under Your cat with both waves and the wave's key. Its button
  played the Blender wave: the cat lifted and waved its front left paw, then went back to its idle.
- F6 played the wave. F7 started the paddle, which was still playing two seconds later (its clip is
  one), F7 again stopped it, and walking off after F7 stopped it too.
- With claws out a claw showed on the raised paw; the plain wave kept the paw round.
- From a script: the swim looped on the cat (legs paddling, head up) until `Game.anims.stop`;
  `Game.anims.play` with a mouse's animation on the cat said "Mouse spin is for mouse, not cat".
- A roaming mouse (a copy of one of its per-track sequences) spun in place, a quarter turn every
  shot; a bird (a copy of one of its ACL sequences, moved to the engine's settings) turned its root a
  full circle a second (read from the bone, after making its mesh tick out of view).
- In Blender (not in game): a new action keyed on the imported start kit and exported as a .glb put
  every bone within 0.2 cm of where Blender showed it, with the armature object left alone or moved,
  turned and sized; the game's Meow through Blender came back within 0.6 degrees.

**2026-10-27, ACL** (build 26184573; the game's own ACL sequences on the cat, paused at a key and read
bone by bone):
- `A_CatMaster_Get_Up_1` at keys 30, 27 and 8, `A_CatMaster_NPC_Sniffing_1` at 47 and
  `A_CatMaster_Powerfull_Loop_1` at 30 (stripped keyframes, between the kept ones, at all but 30 of
  Get_Up), and `A_CatMaster_Run_1` (a loop, with scale) at 10 and its last key, 19: the head, neck, mouth,
  ears, `Spine_base`, `spine_01`, `tail_01` and `tail_05` turned exactly as `formats/acl.py` decodes them.
  The bones the AnimBlueprint layers over (the other spine and tail bones, `belly`, `butt`, the legs) were
  off by the same angles as with a per-track sequence.

**2026-10-24, scripting:**
- **The bridge and the commands:** they run Lua in the game; `lua`, `inspect`, `find`, `game` and
  `game types` all work. A script mod loads with its settings, and its events fire.
- **`WCModsGame`:**
  - It reads your cat's name, clan, traits, looks, health, stamina, level, experience and stats, all
    matching the save.
  - It changes health, stamina, stats, the fresh-kill pile and the clock, and the game's own clock
    function reads the new time back.
  - It reads the quest list, quest statuses and the chapter.
  - In a fight, it reads both sides' stats, levels, health and turn order, and it changed an enemy's
    stats and health.
  - Timers, hooks (including changing a call's parameters) and the level event work.
- **The mod menu's pages** (Overview, Stats, World, Travel, Items, Quests, Fight, Game switches,
  Log, Inspector, Lua console) run against the live game without errors. `agent test`'s `test_menu.py`
  opens every page on screen and photographs it; the first check, on 2026-10-24, used a recording
  stand-in for the menu instead.

**2026-10-25, names:**
- **Cat renames in a save** show on screen: a fixed name (Callie), a new prefix (Fawnpaw) and a whole
  name made with it (Fawnstar), on the HUD and the Select Your Cat screen. The game shows the saved
  suffix as it is (`_STAR` on an apprentice-rank cat reads -star). A name ID whose text the game
  hasn't got shows as `<MISSING STRING TABLE ENTRY>`.

**2026-10-27, names on build 26184573** (a test mod adding the prefix Fawn and renaming the cat
Fawnstar, as a player reported it showing "Cat 1"):
- **The pak needs a container beside it.** With the names mod's text edits alone, the game ignored
  `zzz_WCMods_P.pak`: the HUD said "Cat 1" and the game's string table had no Fawnstar. With a
  container beside it, from an eye colour or an empty one as every build now writes, the HUD said
  Fawnstar and `WCModsNames` found the added names.
- **A renamed cat whose mod is off** (the pak read, the names mod left out): the HUD said "Cat 1",
  and the build warned about that cat and its name ID. The mod menu's Overview can't tell then,
  as no mod adds names.

**2026-10-27, key remaps inside the game** (build 26184573, `WCModsRemap` installed from a test mod's
`controls.json`, started without the key remapper):
- Interact on F opened the travel map at a tunnel, and E did nothing there.
- Run on G: S+G for 2 s went 361 units, walking 256; LeftShift no longer ran.
- Scent tracking on the middle mouse button (posted to the window) turned it on; Q did nothing.
- In the map, E still toggled the legend.
- Map on N: N opened the map and closed it again from inside it; M did neither.
- `Game.npcs.interactKeys()` gave F, the pad's A and the left mouse button.
- With the script installed, the key remapper was left only the movement remap (T for W).
- With "allow_code_mods" off (no bridge, no script mods), the build still put `WCModsRemap` in, and the
  game started from Steam had Interact on F, Map on N and Scent tracking on the middle button.
- Menus and other commands: in the pause menu, K and I moved the selection down and up (the arrows still
  did too), U confirmed Resume, and O closed the map, the inventory and the quest page. `Button_ShoulderR`
  on PageDown went to the next tab, and 2 no longer did. While playing, K still opened the quest page and
  I the inventory (the menu pairs left play alone), and H, standing for E, opened the travel map.
- The game's other screens, with the same menu keys:
  - **Before play:** the title, Select your cat, the clan selection and the cat maker. Holding O asked
    to go back there, as holding Backspace does.
  - **Pause and its pages:** the pause tabs, Help, Settings, the yes/no popup and photo mode.
  - **While playing:** the inventory, the map, and a talk with a clan cat (F started it, U moved it on).
  - **Map, photo mode, cat maker:** the map's zoom and move, photo mode's camera and the cat maker's
    turning read their keys directly, so they follow only the key remapper (reverse-engineering.md,
    Input).
  - **Play state:** `WCModsPlayState` said "menu" in the pause menu, the map and the inventory, and "play"
    while exploring and talking.
- In a fight (pounced on a rogue cat): the same menu keys moved through Attack, Rest, Herbs and Flee, U
  opened the moves and used Provoking Stare (it hit), and O went back. Every key sent the same commands
  as while exploring.
- **Key pictures** (a test mod with Interact on F, G standing for C while you play, and Escape for
  Backspace in menus):
  - the Travel prompt at a tunnel showed F in keyboard mode, and the pad's X in the game's gamepad mode
    (Interact moved only on the keyboard); after teleporting away and back it still showed F;
  - the Talk prompt for the sandbox's studio cat showed F (before this, wcmods' own prompt showed a
    blank circle, as nothing set its picture up);
  - the pause screen's footer showed Escape for Back and Enter for Confirm; the tab keys kept 1 and 2;
  - the Controls tab showed F for Interact and G for Drop; Pause and the rest kept the game's keys;
  - the script set each picture once (its debug log), so nothing fought over them.

**2026-10-28, the overhaul's integration build** (build 26184573; `claude/studio-integration` with the in-game
check's fixes and PRs #97 and #99 merged, put in with `agent install` and the tests' own mods; Sandbox mode 0.5 from
wcmods-sandbox#4; the test save's sandbox cat Sharppaw, a level 1 ThunderClan apprentice; `agent test`: 57 passed,
24 skipped):
- **The runtime fixes** (`tests/game/test_scripts.py`, all ten passed): a frame function failing every frame was
  said once with its mod's name (`[Noisy script] error in onFrame: scripts/main.lua:6: ...`), then once a minute
  with a count (`(1918 more)`, the lines 60 s apart); a misspelt key (`f6`) was said with "did you mean F6?" and
  the script went on; a task that cancels itself and adds another ran with no "invalid key to 'next'";
  `Game.onKey` gave false for a wrong name and an id that cancels the key; a mod's cat's `level()` was nil; a
  script that didn't start (an `end` missing) was named at the top of the screen ("Broken script didn't start:
  scripts/main.lua, line 5. The mod menu (Insert), Tools, Log says more.") and in red on the Overview with Lua's
  own message; a script's settings page saved, said "Saved to settings.json." and kept an empty list a list and
  0.1234567 as it was; a page made from a timer was the script's only page; `_help_speed` showed under its row,
  and `_min_`/`_max_` made no rows.
- **The mod menu** by its real key: Insert opened and closed it, and the Overview listed a moved key ("F:
  Interact (was E)", from a test `controls.json`) and the emotes' and the heal key's keys (F7, F8, F4).
- **Interact on F** (`controls.json`, `WCModsRemap`): the Travel prompt at a tunnel showed F; at a studio cat's
  Talk prompt (F), E did nothing and F started the talk with its line.
- **A Character with a fixed look** (`npcs.json` `look` and `slots`, Sandbox mode 0.5): the log said "1 cats and 0
  quests from Clan Mod Studio, for the sandbox cat in slot 4", the cat stood beside the sandbox cat with its name
  and title over its head, red with dark markings, and its customisation data was the file's: `BodyValue` and
  `FurIdx` 6, `FurValue` 2, `TailIdx` 7 (`SK_Tail_Tapered`), `EarIdx` 3 (`SK_Mid_Pointy`), `EyeValue` 4,
  `WhiskerValue` 5, `FaceValue` 1, `PatternIdx` 12, `MarkingIdx` 3, `FurColorIdx` 9, `Pattern01ColorIdx` 4,
  `Pattern02ColorIdx` 0, eye colour slot 6, size 0.85 (read through a small sphere at its spot, no scan). The
  same numbers in a second game session.
- **Tweaks** (`tests/game/test_tweaks.py` passed: stamina topped up, the clock held at 09:00, the fresh-kill pile
  kept at 40, the heal key F4 posted to the window healing through the game's own input, the Tweaks page's Save
  writing `tweaks.json`). By hand: running 3 s left the stamina at 99.4 of 100 with "Keep my cat's stamina full"
  on; switched off on the Tweaks page, the same run left 86.3; on again, full.
- **The game's own animations** (`"game"`, `tests/game/test_animations.py` passed): F7 played the game's Yawn by
  its own path (`A_CatMaster_Yawn_1`, no package made) and F7 again stopped it; F8 played the claws-out copy of
  the Stretch (`/Game/WCMods/animations_mod/A_Stretch`) with the claws' curve under 0.5; the sleep loop in the
  trot's place kept the head 2.8 to 4.5 cm above the root bone while the cat moved at 174 cm/s.
- **Game data in play** (`data.json`: `TuningData.csv`'s `Gameplay.Exploration.Player.MoveAndRun.Run.Speed`, 390
  made 780): running at Bright-Water Flats (a key and LeftShift held 4.5 s from the same spot), the game's own
  speed stopped at 389 to 390 cm/s without the change; with it, it went on rising at the same acceleration, to
  594 and 613 cm/s. From `Game.cat()`'s position, 517 cm/s between two readings, against at most 395 without.
- **The studio's Try Lua in the game routes** against the game (`tests/game/test_studio_console.py`): the strip's
  "The game is running and listening (in the forest)", a line run (42), and your cat's properties and functions.
- **The level component** (PR #99): on the level 1 cat, the player state's component gave level 1 and Prowess 90
  (its health), and +0x124 (`WCM_LevelShown`) gave 20: it's the level cap, not a second copy of the level.
  `Game.cat():level()` gave 1 and `stats()` numbers (Prowess 90, Strength 95, Resilience 85, Instinct 85,
  Agility 80, Stamina 100), as the Stats page showed.
- **The game's enums read by name** (PR #97): `tests/game/test_cat.py::test_enums_are_read_from_the_game` passed;
  UE4SS.log had no "can't read the game's enum", "isn't build 26184573's", "can't read Player_Interact", "can't
  read UI_PC" or "NoCommand" line; a script reading `Game.enums.clan.Total` as it loaded logged "clan Total 5 at
  load, 5 now; the game's own: true"; with Interact on F, the Travel and Talk prompts showed F; with no remap, the
  studio cat's Talk prompt showed the game's own picture for Interact (the mouse button, as the game's Travel
  prompt does) and E started the talk.

## Not yet confirmed in game

- **Choosing a game (2026-10-28):** the Save page's changes to a game other than the one played last, made
  with Change my save now, then that game loaded from the cat choice; cats.json's `"<slot>/player"` (the Your
  cat page's Which game) writing that game's slots, scars and shape while another game is played; and its
  colours of its own going on in game through `WCModsCatLook`'s `YOURS` table, by the cat's name IDs, in
  place of `player`'s. Checked only by the unit and end-to-end tests over temp saves.
- **Animations:** on the clans' cats in the forest and on quest givers (they run the same AnimBlueprint
  and mesh, but only your cat was watched); the rats', rabbits', squirrels', foxes', badgers', dogs' and
  snakes' (made the same way as the mice's and birds'); an emote's key on a controller button.
- **The game's own animations (`"game"`):** the run as the trot (the sleep loop in the trot's place was watched
  on 2026-10-28, above), and the Animations page's Try it on my cat.
- **One playing state for every script (2026-10-28):** an emote's key stopping what the Emote wheel
  started, through the shared `WCModsAnims.playing.<actor>` and the anim instance's current montage
  (`GetCurrentActiveMontage`, `Montage_Stop`): not tried in game. Nor is the check that keeps a finished
  emote's id from stopping the game's own montage: the shared state holds the montage's address and its
  sequence, and the current montage must be that object, playing that sequence (read from its
  `SlotAnimTracks[1].AnimTrack.AnimSegments[1].AnimReference`; when that can't be read, the address
  alone decides).
- **Items:** a new look made from an accessory's second look (`"like": "Neck.DogCollar.2"`; the build
  takes it, as it takes the first).

- **Accessories' models:** on other cats (a mod's cats, NPCs) and in the save slots' pictures; and on
  a cat whose build the game set up as brawny or chubby (`RefreshShape` doesn't apply a build, so only
  the morph set by hand was seen).
- **Models on the ground:** dropped by a questline's reward or by Sandbox mode's stories (the same
  `Game.items.drop`, but not watched).

- **Scripting:**
  - the studio's Try Lua in the game page itself against the game (its routes ran against the game on
    2026-10-28, above; the strip's four states and the request withdrawn after a timeout are tested without it,
    over a made-up bridge folder);
  - the damage, quest-status and status events;
  - whether the game obeys each of its developer switches.
- **Tweaks' skip in a story game** (`skip_scenes`): seen skipping the opening scenes of a sandbox game as Sandbox
  mode's skip, but not on a fresh story cat, so it's refused, and its rows hidden, until that check shows a skipped
  scene still gives its quest step or rank (`tests/game/test_tweaks.py` says how to run it). The other tweaks ran
  in the game on 2026-10-28 (above).
- **The rest of the runtime fixes of 2026-10-28** (written and checked by their shape and by luacheck; the ones
  `tests/game/test_scripts.py` covers ran in the game on 2026-10-28, above): `Game.find` not handing back the last
  level's HUD (nil until the new one comes first); the dialogue claim renewed while the box is up; the bridge
  stopping a runaway line and running only a request it took; the script bootstrap loading the mod's files by
  their names (and `require` through them); the Log page's Mods and Errors filters; the Inspector's Find refusing
  the widest classes; a number written `12.0` read back by `Game.json.decode` as `12.0`.
- **The game's enums after a game update** (`Game.enums`, the Talk prompt's Interact, the in-game remap's
  `NoCommand` and `UI_PC`, the agent's `Button_Confirm`; seen read from the game on 2026-10-28, above): after the
  next update, UE4SS.log's "the game's enum ... isn't build 26184573's" lines should say what moved, and
  `python tools/re/uht.py <exe> lua` which fallbacks to update. A script that reads an enum before the game is up
  wasn't seen either: the one that read `Game.enums.clan` as it loaded had the game's numbers already (no "can't
  read the game's enum ..." then "... after all" lines).
- **UE4SS's log format** that `scriptlog.py` (a script's card) and the Log page read: `Starting Lua mod '<name>'`
  and `[Lua] [<mod name>] ...`, as UE4SS 3.0.1 (Git SHA 83330635) writes them, read from the installed game's
  log on 2026-10-28. Other UE4SS versions are unchecked; a line the reader doesn't recognise is left out.
- **The save's `Hash` and `Version`** (read from the code: [reverse-engineering.md](reverse-engineering.md#the-save)).
  Two checks would confirm it, both on a test cat and after a backup:
  - **Any `Hash` loads.** Turn Steam Cloud off for the game first (its Properties, General): the
    save folder has `steam_autocloud.vdf`, and the game has a cloud path of its own that writes the
    cloud copy over the slot and loads it, so the patched file might not be the one that loads. With
    the game closed, change the save's `Hash` with a hex editor: the 8 bytes that start 9 bytes after
    `UInt64Property` and its NUL. Write `EF CD AB 89 67 45 23 01` (0x0123456789ABCDEF, little-endian).
    Start the game and enter the cat, and before anything saves, run `python wcmods.py lua -f
    hash-read.lua` with:
    ```lua
    local m = Game.save.manager()
    if not m then return 'no save manager' end
    local sg = Game.get(m, 'SaveGame')
    if not Game.valid(sg) then return 'no save game' end
    local h = Game.get(sg, 'Hash')
    local ok, text = pcall(string.format, '%016X', h)
    return ok and text or tostring(h)
    ```
    It should print `0123456789ABCDEF`, which shows that the patched file is the one that loaded, and
    the cat should have its progress. Another value means the game saved first (try sooner) or
    another copy loaded.
  - **The formula.** In the forest, run `python wcmods.py lua -f hash-write.lua` with:
    ```lua
    local m, st = Game.save.manager(), Game.manager('storage')
    if not (m and st) then return 'no managers' end
    local function hash()
        local sg = Game.get(m, 'SaveGame')
        if not Game.valid(sg) then return nil end
        return Game.get(sg, 'Hash')
    end
    local function hex(v)
        local ok, text = pcall(string.format, '%016X', v)
        return ok and text or tostring(v)
    end
    local old = hash()
    if old == nil then return 'no save game' end
    local t0 = os.date('!%Y.%m.%d-%H.%M.%S')
    Game.save.write()
    local new = hash()
    if new == nil then return 'no save game after the write' end
    return table.concat({ hex(old), hex(new), hex(st:GetAddress()), hex(m:GetAddress()), t0,
        os.date('!%Y.%m.%d-%H.%M.%S') }, ' ')
    ```
    It prints the old Hash, the new Hash, the storage manager's address, the save manager's address
    and the UTC time before and after the write. If the two hashes are the same, the game skipped the
    write (the code skips it while a byte that an earlier write set is still set): run it again a
    little later. Then check in Python that `next_hash(old, when, address)` (`wcmods/formats/save.py`)
    gives the new Hash, with the storage manager's address and `when` at each second from the first
    printed time to the second. If no second matches, first doubt which
    object's address it is: the writer is the storage manager's and formats its own `this` (read
    from the code), so try the save manager's address next. The `%p` text (16 upper-case digits) was
    checked against the UCRT's `__stdio_common_vswprintf` on this machine, not in the game.
  - **Not to try on a real save:** a `Version` other than 20. The code says the game starts a new
    save instead of loading it.
- **Coat colours on screen.** The UE4SS script rewrites the fur table about two seconds after launch.
- **Game data tables in play** beyond the running speed (seen on 2026-10-28, above): the other tables and
  rows load from the same pak, but none has been watched in play (the Game data page's Quick changes say so).
- **The Save page's Change my save now and Put it back** (2026-10-28). They write through the same codec
  as save edits on install, which the game accepts (above), but a save changed from the page and then
  loaded hasn't been checked in game; nor has a `save.json` made once per save, then played on past and
  applied again.
- **New pattern and marking slots on a cat.** The lists grow in game (slot 25 read back with its new
  colour), and the game's code checks those indexes against the real list size, but no cat has been
  seen wearing a new slot yet.
- **Key remaps inside the game** on controller buttons and the mouse wheel, a remapped key held
  while a screen opens, and in den decorating, the name screen, cutscenes and minigames.
- **The key remapper outside the game** with the new play state (only the state file was read; the
  agent's keys don't pass through Windows' keyboard hook).
- **Parts of the mod menu.** Not yet checked: Save on the Mouse look and Your cat pages, and on the
  Colours page (your cat's own colours, written into the cats.json of the last Apply), cats'
  own names in Nearby labels, god mode, game speed and teleport on the Cheats page, and the pause
  menu under the key remapper.
- **Mods' own cooked paks (`paks/`).** They're installed as the game's own patch paks are named,
  but no cooked content has been tried in game yet.
- **memscan on the game itself** since the 2026-10-28 fix. On a test Python process it found 4 of 4
  markers planted next to unreadable pages, where the old scan found none, and the unit tests check
  one such marker on their own process. To check on the game:
  - Install the names test mod (the prefix Fawn, the cat renamed Fawnstar). Without it the game has
    no "Fawnstar" text, and the check finds nothing and proves nothing.
  - With the test cat in the world and the game paused (P), run `python tools/re/memscan.py
    Wrc-Win64 name=4600610077006e007300740061007200 --old --max 1000 --context 0` ("Fawnstar" in
    UTF-16). One scan reads each chunk the old way and the new way back to back.
  - It needs at least one hit. Every hit should say `old: found` or `old: missed, in a chunk it read
    as empty`; the summary's "missed otherwise" and "only it found" should be 0.
  - Record how many chunks the old scan read as empty, and the hits found only in those. Those hits
    are the fix shown on the game; with none, the check shows only that nothing the old scan found
    is lost.
- **Names beyond the text.** Renamed and added names reach the game's text table (Mothpaw,
  Sparrowheart, Mothwhisper and the rogue Moss were read back in game). Still unchecked: new cats
  getting added parts, removed parts and ban list changes, and the name screen's suggestions. Also
  unchecked (2026-10-28, the planner's fixes, tested without the game): a rogue name given to a clan
  cat showing as that fixed name (Storm), one of the game's prefixes given to a rogue or loner showing
  alone (Otter, from a text under the prefix's ID), and the mod menu's pages titling rank-less quests
  (Rank Up, the Sleep quests) by their own titles. And names.json's `text` for an area, a quest's title
  or an item: the build writes the renamed text and the mod menu's pages read it, but whether the
  game's own screens follow (the area's name as you walk in, the quest log, the inventory) hasn't been
  looked at.
- **Your cat's level and stats after a real game update.** The level component's signatures find it on
  build 26184573 as if it were another build, and follow it when its code is moved in memory
  (docs/reverse-engineering.md, "Game updates"), but no real update has come since. After the next
  one: `python wcmods.py game signatures check` should list `SwtAdventureLevelComponent` with all
  eight values `same` (or `moved`), none `lost`; then, with the new install and your cat in the world,
  `python wcmods.py lua "local ps = Game.get(Game.controller(), 'PlayerState') local cls =
  Game.object('/Script/SwtAdventure.SwtAdventureLevelComponent') local ok, c = pcall(function() return
  Game.valid(ps) and cls and ps:GetComponentByClass(cls) end) if not (ok and Game.valid(c)) then return
  'no level component' end return Game.get(c, 'WCM_Level'), Game.get(c, 'WCM_Prowess')"` should print
  the cat's level and Prowess (the mod menu's Cat page shows them too; on build 26184573 it gave 1 and 90
  for a level 1 cat, 2026-10-28). It reads the player state's component itself, calling nothing on an
  object that isn't there, and doesn't scan for it: `Cat:level()` and `stats()` go through
  `Cat:component`, which falls back to scanning every level component when the player state's
  `GetComponentByClass` finds none.
- **What the conversations show** (`wcmods/dialogue.py`, read from the graphs and the code only;
  reverse-engineering.md, *Dialogue graphs*). Each check is on the test cat, with a backup, in nobody
  else's game:
  - **Story lines come from `Strings_EN` through the row's `StringKey`, not `DebugText`.** When the aging
    leader offers his first talk (`Gameplay.Dialogue.Story.Short.TheAgingLeader.Main.1`, quest states
    `Quest.Main.1.0`, `.1` or `.Complete`), read his first three answer buttons, in any order (a
    `BondDialogue` may shuffle them). They should be "Of course it will!", "I doubt it." and "How can you
    be sure?" (`Strings_EN`), not "I agree.", "Maybe." and "I don't know." (the table's `DebugText`). Then give `names.json` `text` a new
    `QST_Story.Short.TheAgingLeader.Main.1.Right.1.Short`, install, and the first button should show it.
  - **Quest lines come from QuestDialogues.csv's row, not the key a graph copy holds.** An apprentice's
    gather quest (`Quest.Procedural.Survival.Gather.Apprentice`): answer Brave. The reply should be the
    words of `QST_Gather.Apprentice.Context.Response.Brave`. The saved graph copy names
    `QST_Gather.Apprentice.Response.Brave`, which `Strings_EN` hasn't got.
  - **A missing key shows the row's `DebugText`, which for a quest is the raw key.** The Escort and
    Recruit quests' 84 keys (14 per quest: 11 lines and 3 answers) and their titles' aren't in `Strings_EN`, and
    QuestDialogues.csv's `DebugText` is the key itself. So an Escort or Recruit quest, if the game ever
    offers one, should show raw keys on screen (`QST_Escort.Apprentice.Context.1`), not words.
  - **A missing story key shows English `DebugText`.** The resentful elder's StarClan talk
    (`Gameplay.Dialogue.Story.Monologue.Interaction.TheResentfulElder.StarClan`, which
    `NpcDialogue_TheResentfulElder` plays) has rows only for its `.Friend` and `.CloseBond` variants, and their
    six keys aren't in `Strings_EN`. Talking with him in StarClan at Friend or CloseBond should show the row's
    `DebugText` ("It is one thing to regale others with dark tales of the past…" first). At another bond
    rank, what shows is unknown (it has no row).
  - **A cat's own talk and a cinematic show the key named in their graph.** The rank-up to WindClan leader
    (`Gameplay.Narrative.RankUp.WindClan.Leader`) shows the words of
    `STR_Script.WindClan.Deputy.Leader.Promotion.Narrator.1` first. Its one button is ThunderClan's key,
    `STR_Script.ThunderClan.Deputy.Leader.Promotion.Player.1`.
  - **The variant follows your bond.** A Filler talk with a clan cat (for example
    `…Filler.ThunderClanDeputy.Main.1`) shows its `.Positive`, `.Neutral` or `.Negative` row by your bond
    with that cat. Check with two cats of different bonds.
  - **The gatekeeper's angle-bracket lines** (`NpcDialogue_DefenderGatekeeper`, `<A 1 vs 1 duel>`): are
    they what the game shows, if that giver is ever met? They're inline, so a text edit can't change them.
  - **Playing a conversation by tag** (the RE roadmap's step 9, untried). On the Sandbox mode cat (save slot
    4) with a backup, near a studio cat, run each call once from the Console page:

    ```lua
    local seq, me = Game.manager("sequencer"), Game.player()
    local npc = Game.npcs.all()[1]
    local cat = npc and npc:actorOrNil()
    if seq and me and cat then
        seq:PlaySequenceDialogue(Game.tag("Gameplay.Dialogue.Story.Short.TheAgingLeader.Main.1"), cat, me, false, false)
    end
    ```

    and the same with the stem `Gameplay.Narrative.RankUp` and both flags `true` (they add your clan's and
    your rank's leaf tags). By its name and rows, `DT_QuestSequenceDialogues` is the table
    `PlaySequenceDialogue` looks the tag up in (a guess: the call's code wasn't read). Its 30 rows are the
    cinematics' tags (`Gameplay.Narrative.RankUp.WindClan.Leader`, `…Prophecy.Intro.ThunderClan`…) and no
    story tag. So the first call is expected to play nothing, and the second the rank-up cinematic for your
    clan and rank. If either opens the game's dialogue box with the cat and its answers work, a Questlines
    step "Play the conversation" exists without writing graphs.

After a game update, run `selftest` before installing again ([updating.md](updating.md)).
