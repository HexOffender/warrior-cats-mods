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
  the IDs the game's own packages have; the accessory look lists read back with new looks added.
- **Save editor:** changes only the values it's told to.
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
  save editor was accepted. The save carries a 64-bit checksum whose formula isn't known; the tool
  keeps the original value and the game accepts it.
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

**2026-10-27, key remaps inside the game** (build 26184573, `WCModsRemap` installed from a test mod's
`controls.json`, started without the key remapper):
- Interact on F opened the travel map at a tunnel, and E did nothing there.
- Run on G: S+G for 2 s went 361 units, walking 256; LeftShift no longer ran.
- Scent tracking on the middle mouse button (posted to the window) turned it on; Q did nothing.
- The pause screen's Controls tab opened as before, showing the game's own keys.
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

## Not yet confirmed in game

- **Accessories' models:** on other cats (a mod's cats, NPCs), in the main menu's and the save
  slots' pictures, on body and paw accessories, and on a brawny or chubby cat (the body-shape morphs
  are taken from the cat's body, close to the game's own for the Dog Collar, but not seen in game).

- **Scripting:**
  - the studio's Console page;
  - items dropped with `Game.items.drop` being picked up;
  - the damage, quest-status and status events;
  - whether the game obeys each of its developer switches.
- **Coat colours on screen.** The UE4SS script rewrites the fur table about two seconds after launch.
- **Game data tables in play.** They load from the same pak as the text, but no gameplay change has
  been checked on screen yet.
- **New pattern and marking slots on a cat.** The lists grow in game (slot 25 read back with its new
  colour), and the game's code checks those indexes against the real list size, but no cat has been
  seen wearing a new slot yet.
- **Key remaps inside the game** on controller buttons and the mouse wheel, a remapped key held
  while a screen opens, and in den decorating, the name screen, cutscenes and minigames.
- **The key remapper outside the game** with the new play state (only the state file was read; the
  agent's keys don't pass through Windows' keyboard hook).
- **Parts of the mod menu.** Not yet checked: Save on the Mouse look and Your cat pages, cats'
  own names in Nearby labels, god mode, game speed and teleport on the Cheats page, and the pause
  menu under the key remapper.
- **Mods' own cooked paks (`paks/`).** They're installed as the game's own patch paks are named,
  but no cooked content has been tried in game yet.
- **Names beyond the text.** Renamed and added names reach the game's text table (Mothpaw,
  Sparrowheart, Mothwhisper and the rogue Moss were read back in game). Still unchecked: new cats
  getting added parts, removed parts and ban list changes, and the name screen's suggestions.

After a game update, run `selftest` before installing again ([updating.md](updating.md)).
