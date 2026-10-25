# WC Mods — mod manager for *Warrior Cats: Clans of the Forest*

A mod manager and shared modding library for the Steam version (Unreal Engine 5.7, app 3960600).

## Getting started

1. **Download** this folder (on GitHub: the green **Code** button, then **Download ZIP**) and unzip
   it anywhere, such as your Documents.
2. **Double-click `Clan Mod Studio`** in it. It opens in your web browser. The first time, if your
   computer doesn't have Python (what Clan Mod Studio runs on), it says so and offers to install it;
   say yes, then double-click it again.
3. **Follow "Get set up"** at the top of the page. It finds the game, makes a safety copy of your
   save, and installs the script loader most mods need (UE4SS) with one click. If you've never played,
   start the game once first so it makes a save.
4. **Add a mod:** drop the mod's .zip on the page, or onto `Clan Mod Studio` itself, and press **Add
   to my mods**. To try some, [wcmods-examples](https://github.com/HexOffender/wcmods-examples) has palettes, mouse look and more:
   download it (**Code**, then **Download ZIP**) and drop that .zip on the page.
5. **Press Play** (top right). It puts your mods in the game and starts it. Close the game before you
   change mods; press Play again after.

To open it from your desktop, right-click `Clan Mod Studio` and choose *Send to > Desktop (create
shortcut)*. Close its black window to stop it. If it's already open, double-clicking it again
brings it back.

**Updating:** unzip a new download over the old folder; your mods and settings stay. With git, note
that wcmods used to come with palettes, mouse look and other mods in `mods/`. They're now in
[wcmods-examples](https://github.com/HexOffender/wcmods-examples), so pulling takes them out of
`mods/` (copy any you changed somewhere first); add back the ones you use. Everything else in `mods/`
is yours and git leaves it alone, except the mod menu's own folder.

## Clan Mod Studio

```
python wcmods.py studio      # what double-clicking Clan Mod Studio does
```

Also in this folder: **`Play with key remaps.bat`** starts the game with your key remaps active (see
[Remapping keys](#remapping-keys)), which the studio's Play button does too when your mods remap
keys. It stops by itself when the game closes.

**Clan Mod Studio** puts your mods in the game. Its **Mods** page is where you start:
- **Add a mod:** drop a downloaded mod's .zip on the page. It shows what's in it (what the mod
  changes, whether it runs code, what else it needs) before you add it.
- **Example mods:** wcmods comes with one mod, the mod menu. Example mods are in their own
  repository, [wcmods-examples](https://github.com/HexOffender/wcmods-examples): themed palettes, eye and coat colours, mouse look,
  controls, game tweaks and more. Drop its .zip on the page and tick the ones you want.
- **Switch mods on and off:** a mod that needs another turns that one on too, and turning off a mod
  that others need asks first.
- **Play** (top right): puts what's changed in the game, then starts it. Apply to game does just the
  first part. Both need the game closed, and a banner lists what isn't in the game yet.
- **The rest:** each mod's More has its priority, its folder, Save as .zip (to share it) and Remove.
  A removed or replaced mod is kept in `backups/mods/`, and Backups and repair puts it back. That
  section also has your save backups and "Take all mods out of the game".

The pages under **Make mods** are for making your own; each edits a file in a mod folder:

| Page | What you change | Stored as | Reaches the game through |
|---|---|---|---|
| **Palettes** | eye, coat, pattern and marking colours on a live cat; new pattern and marking colours | `palette.json` | eye atlas patch (eyes); UE4SS script (the rest) |
| **Your cat** | colours only your cat wears (coat, paws, ears, nose, whiskers); which colour slots it wears | `cats.json` | UE4SS script (colours); your save, on install (slots) |
| **Controls** | keyboard, mouse and controller bindings; press-to-bind, conflicts, controller presets | `controls.json` | the key remapper while you play (`wcmods play`); see [Remapping keys](#remapping-keys) |
| | mouse look: sensitivity, invert, smoothing | `mouselook.json` | UE4SS script |
| **Names** | rename, add and remove name prefixes, suffixes and rogue names; the ban list; cameo cats and any shown name; the cats in your save | `names.json` | edited tables and text in the mod pak; cat renames in your save, on install |
| **Game data** | XP, costs, rewards, speeds and ~440 tuning values, in any runtime table | `data.json` | edited tables in the mod pak |
| **Save** | level, XP, health, stamina, fresh-kill pile, stats, inventory, settings, anything else | `save.json` | your save, on install |

**Scripting the game:** a mod's `scripts/main.lua` runs in the game with no Python, and its
`settings.json` gets a page in the mod menu. The shared `WCModsGame` module covers a lot of the game:
- your cat's health, stamina, level, stats, traits, looks, size and position;
- items, the fresh-kill pile, the time of day, quests and fights;
- the save, the game's managers and its developer switches;
- timers, keys, events and hooks;
- an inspector for any of the game's objects.

With code mods allowed, `python wcmods.py lua "Game.cat():name()"`, the studio's **Console** page and
the mod menu's Console run Lua in the game while it's open. See [docs/scripting.md](docs/scripting.md);
the example is [game-tweaks](https://github.com/HexOffender/wcmods-examples/tree/main/game-tweaks) in wcmods-examples.

Mods can also ship whole replacement files (`files/Wrc/...`), and their own pages and build
steps written with the shared library (see [docs/SDK.md](docs/SDK.md)). UE4SS scripts can draw
on screen (menus, debug text, markers on places in the world) and find nearby pickups, cats and
quest objectives with the shared Lua modules wcmods installs (docs/SDK.md, "Overlays"; example:
[quest-markers](https://github.com/HexOffender/wcmods-examples/tree/main/quest-markers) in wcmods-examples, a custom quest with on-screen markers).
Mods can run C++ in the game too, as UE4SS C++ mods: `python wcmods.py new my-mod --kind cpp`, then
`python wcmods.py cpp setup` and `cpp build my-mod` build its `cpp/` against the game's UE4SS (docs/SDK.md,
"C++ mods", lists what that needs).

**In game, Insert opens the mod menu** (with UE4SS). A status line under its title shows how your
cat is doing, and the side bar groups the pages:
- **Home:** an Overview of your cat and the world with quick buttons and the keys mods use, and
  the installed mods.
- **Your cat:** stats, colours and mouse look.
- **World:** the clock and the fresh-kill pile, Travel (saved spots, checkpoints, areas, Back),
  what's nearby, and your items.
- **Story:** quests and their objectives.
- **Fight:** both sides of a fight.
- **Cheats:** the engine's cheats and the game's developer switches.
- **Mods:** pages for mods with live settings.
- **Tools:** the log, the menu's own settings, and with code mods allowed the Inspector and Console.

Everything there changes live. Mouse look and your cat's colours change as you move their sliders,
and Save writes the change back to the mod, so the next install keeps it.

**The mod menu is a mod of its own**, **Mod menu** (`mods/mod-menu`), on to begin with:
- **Turning it off:** the game has no menu, and mods that add a page to it still work; they just
  have no page.
- **Mods that can't do without it:** they say so in their `mod.json` (`"requires"`), and turning
  one on turns the menu on too.
- **Its settings:** its card's Settings (its `menu.json`) set the key that opens it, the controller
  button that does too (View, to begin with), its size and whether cheats start on. A- and A+ in the
  menu's top bar resize it while you play.
- **With a controller:** View opens it, the d-pad moves between its controls and A presses them, and
  View or B closes it. Opened from a controller, the game pauses while it's open.
- **The game's console:** it's under Options on the Mods page.
- **Your own page:** docs/SDK.md, "`WCModsMenu`", shows how a script adds one.

**Cheats** are the engine's cheat manager, which the release build leaves off. The menu's Cheats
page switches them on and off while you play, and has god mode, fly and ghost (W A S D or the left
stick move the way the camera faces; Space and Left Ctrl, or the triggers, go up and down; ghost goes
through walls), cat size, game speed, teleport to where the
camera looks, and a box for any console command. With cheats on, the console's cheat commands work
too (`god`, `slomo 0.5`, `teleport`). The console's own `fly`, `ghost` and `changesize` don't stick:
the game puts its cat back to its own movement each frame and resets its mesh's scale, so the page
does those itself (it scales the whole cat, and moves it while flying). `python wcmods.py cheats on` makes them start on (install
again to apply), and `python wcmods.py console on|off` switches the game's console (`~` or F10).
Some cheats can break a quest or a save, so back up first if you're unsure (Mods page).

The original game files are never modified. Everything goes into
`<game>\Wrc\Content\Paks\~mods\zzz_WCMods_*`, `<game>\Wrc\Binaries\Win64\ue4ss\Mods\WCMods*` and
`ue4ss\Mods\shared\WCMods*`. Uninstall removes those. Save edits are written into your save only after a backup.

## Remapping keys

The game doesn't take remaps from mods. It keeps a copy of your bindings in the save
(`Shared/InputKeyboard`, `Shared/InputGamepad`) but ignores edits to it. That was tested twice:
once with the mouse in the camera slots, and once with keyboard keys only and the game's
custom-controls switch (`SettingsData/CustomControls`) on. The game also has its own rebinding
screen (`WBP_GuiPopupControlConfig`), but on PC it's hidden and not wired up: forcing its Settings
button visible gives a button that does nothing.

There are three ways around that:

1. **Controller buttons: Steam Input.** In Steam, right-click the game, then Properties, Controller.
2. **Keyboard keys: Microsoft PowerToys Keyboard Manager.** Open Keyboard Manager, choose
   *Remap a key*, map your new key to the game's key (for example F to E for Interact), and set
   the target app to `Wrc-Win64-ShippingDRM.exe` so the remap only applies in the game.
3. **Keyboard keys: the wcmods key remapper.** `python wcmods.py play` starts the game, and while
   you play, the keys in your mods' `controls.json` (the Controls page) stand in for the game's.
   "Play" means the game window is in front and you're exploring, not in a menu. A small UE4SS
   script (`WCModsPlayState`, installed with your mods when you have remaps) tells the remapper
   which it is. Windows can't, because the game draws its own cursor. Without that script, remaps
   apply whenever the game is in front. The remapper holds back the key you press and sends the
   game's key in its place, and it stops when the game closes.
   Menus, the name screen and other programs keep your normal keys, except for the menu remaps you
   set (the Controls page's "In menus" list). A key whose action moved stops doing it, unless another
   action still uses it. Mouse buttons and the wheel can stand in for keys.
   Tested in game (2026-10-23) with movement on T/F/G/H. The new keys moved the cat, WASD did
   nothing while playing, and remapping switched off when another window was in front and on the
   title screen. The pause menu hasn't been checked yet.

**The current method is method 3** for keyboard and mouse, with method 1 for controllers.
Method 2 does the same job without wcmods, if you'd rather not run the remapper. Don't run both
at once for the same keys.

To use method 3, set your keys on the Controls page (or in `controls.json`), save them to a mod,
and install mods once (game closed), which adds the play-state script. Then start the game with
`python wcmods.py play` instead of from Steam:

```
python wcmods.py play              # start the game through Steam and remap until it closes
python wcmods.py remap             # the same, when the game is already running (or about to be)
python wcmods.py play --dry-run    # report which remaps would happen, without changing any keys
python wcmods.py play --in-menus   # remap in menus too
python wcmods.py play --debug      # log the window in front, the play state, and remapped key presses
```

It runs as a normal program using Windows' low-level keyboard hook. Ctrl+C stops it, and anything
it was holding down is let go. Details:

- **A press finishes as it started.** A key you were already holding when you went from a menu into
  play keeps going to the game unchanged until you let go, so nothing gets stuck. A remapped key
  stops repeating when a menu opens.
- **Some keys keep their old job.** Enter, Space, Escape, Backspace and Tab are never held back when
  their action moves, because prompts and dialogue shown while you play may need them; the build
  and `play` say so.
- **Other programs' keys pass through.** Keys sent by other programs (Steam Input's keyboard buttons,
  macro tools) aren't remapped or held back. A controller button that Steam Input turns into W still
  walks forward.
- **Mouse remaps cost a little.** Remapping a mouse button or the wheel adds a mouse hook, which
  Windows calls for every mouse movement. Remap keyboard keys only if you notice any lag.

## Command line

Everything the studio does is also available as a command:

```
python wcmods.py status      # game, save, Oodle, UE4SS, and your mods
python wcmods.py selftest    # checks every file format against your install (writes nothing)
python wcmods.py install     # builds the enabled mods and installs them (game closed)
python wcmods.py play        # starts the game with your key remaps (see Remapping keys)
python wcmods.py uninstall   # removes them again
```

Install stops if any mod failed to build, because installing would remove that mod's earlier
changes. Fix or turn off the mod, or use `install --force` (the studio offers "Install the rest
anyway") to install everything else.

Adding and sharing mods:

```
python wcmods.py add "Cool Mod v1.2.zip"   # add a downloaded mod (a .zip of one or more mods, or a folder)
python wcmods.py remove cool-mod           # take it out of mods/ (kept in backups/mods)
python wcmods.py pack my-mod               # my-mod-1.0.zip, to share
```

`enable <mod>` (and `add`, unless `--off`) also turns on the mods it requires, and `disable <mod>`
and `remove <mod>` refuse while mods that are on need it (`--with-dependents` turns those off too).

After a game update, `game build` says which build is installed, what wcmods followed and what it
couldn't, and which mods were made for an older version. `allow-outdated <mod>` uses one anyway on
this build. See [docs/updating.md](docs/updating.md).

Also: `new <name> --kind palette|controls|files|data|items|names|save|script`, `eyes`,
`tables`, `names [--cats] [--json]`, `controls [--json]`, `files <pattern>`, `extract <pattern>`,
`texture <item|accessory|/Game/...>` (one of the game's textures as a PNG),
`build`, `backup`, `restore [name|latest]`, `cheats [on|off]` (whether the mod menu's cheats start
on), `console [on|off]` (the game's `~` console). With code mods allowed and the game running:
`lua <code>` or `lua -f file.lua` (run Lua in the game), `inspect <expr>` (an object's properties and
functions), `find <class>`, `game` (is the bridge up?) and `game types` (Lua type files for your
editor).

`agent ...` drives the game for testing, by hand or by an AI agent:

- **Game:** `agent launch --world` starts it and plays into the forest, and `agent quit` closes it.
- **Mod menu:** `agent menu read Stats` and `agent menu set Health 150` read and use its pages.
- **Input:** `agent key W --hold 2` walks.
- **Pictures:** `agent shot --menu` saves a picture.
- **Tests:** `agent test` runs the in-game tests in `tests/game` and writes a report with pictures.

`agent install` puts in a test build with the bridge. It allows code mods for that build, so the
code of every mod that's on runs, downloaded ones included; turn off any you don't trust first. Your
settings in `wcmods.json` stay as they are; like any install, it updates the record there of what's
installed. See [docs/agent.md](docs/agent.md).

## How it's built

`wcmods` is a shared library plus a set of independent **sections**. `files`, `data`, `names`,
`palettes`, `cats`, `controls`, `mouselook` and `save` are built in, and mods can add more. Each
section reads its own files from every enabled mod and contributes outputs through one build
context: pak files, CSV edits (merged across mods), patched assets, UE4SS scripts and save edits.
If a section fails, its outputs are rolled back, it's marked FAILED in the build report, and the
rest still build. The studio works the same way: each page is a separate module, loaded when
opened, built on `studio/lib/wc.js`.

An install writes, into the game:
- **`Paks\~mods\zzz_WCMods_P.pak`:** every replacement file and edited table.
- **`zzz_WCMods_P.utoc` / `.ucas`:** patched cooked assets (the eye atlas).
- **Mods' own cooked paks:** as `zzz_WCMods_<mod>_<name>_P.*`.
- **UE4SS scripts:** in `ue4ss\Mods\WCMods*`, among them the mod menu's window (`WCModsMenuHost`)
  while the Mod menu mod is on.
- **The shared Lua modules** in `ue4ss\Mods\shared\`: `WCModsDraw`, `WCModsView`, `WCModsWorld`,
  `WCModsGame`, `WCModsMenu` (with the mod menu), and `WCModsNames`, which is written from your name
  mods.

[docs/SDK.md](docs/SDK.md), "Game files, repacking and new content", explains how the game's
files are packed, how wcmods repacks them, and how to add new models and other cooked content.
[docs/reverse-engineering.md](docs/reverse-engineering.md) collects what we've worked out about the
game's insides (the camera, traits, colours, names, the save, cheats, its classes and managers), with
the tools in `tools/re/`. [docs/mechanics/](docs/mechanics/README.md) explains the game's rules,
with the numbers to change for each: the combat damage formula, every move, stat growth, traits,
stamina and stealth, fresh-kill, dens, items, bonding and how NPCs are made.

Mods are applied in `priority` order, then by folder name. When two mods set the same thing,
the higher priority wins.

## File formats

### `mod.json`

Every mod has one. Only `name` is needed; Clan Mod Studio shows the rest:

```json
{
  "name": "Cool Tweaks",
  "description": "What it changes, in a line.",
  "version": "1.2",
  "author": "Ash",
  "enabled": true,
  "priority": 0,
  "requires": ["mod-menu"],
  "uses": []
}
```

- **`requires`:** the mods it can't work without, by folder name. Turning it on turns them on.
  While one is missing or off, building leaves this mod out and says why (installing stops, as for
  any mod that didn't build, unless `--force`).
- **`uses`:** mods it works with when they're on, such as `mod-menu` for a page in the mod menu.
  Nothing is turned on for them; the studio just shows it.
- **`game_builds`:** the builds of the game it was made for (a mod without it was made for
  24847281). After a game update, a mod that doesn't list the new build is left out until it's
  updated, or you choose "Use it anyway" for that build. See [docs/updating.md](docs/updating.md).
- **`priority`:** mods are applied in priority order, then by folder name, and the higher one wins
  when two set the same thing.

**Sharing a mod:** Save as .zip (a mod's More, in the studio) or `wcmods pack <mod>` writes a .zip
with the mod's folder in it, and that's what the studio's Add a mod takes. A .zip can hold several
mod folders, or one mod's files at the top (it's then named after the .zip). Adding a mod never
runs anything in it. Mods with code (a `section.py`, `scripts/`, a `studio/` page) stay out of the
game until "Allow mods that run code" is on (the studio's Options, or `"allow_code_mods": true` in
`wcmods.json`), which is only for mods from people you trust.

Besides the JSON files below, a mod can hold:
- **`files/Wrc/...`:** whole replacement files at their game path. `extract` copies one out to
  start from.
- **`paks/`:** cooked content made with Unreal Engine 5.7, as a `.pak` with its `.utoc` and
  `.ucas`, for new models, textures and sounds. It's installed as it is, under a `zzz_WCMods_`
  name, so it loads after the game's files and comes off on uninstall. See docs/SDK.md, "New
  content", for making it and getting the game to use it. Not yet tried with this game.

### `palette.json`
```json
{ "eyes": { "Amber": "#FFB300", "Sky": ["#001B2E", "#00E5FF"] },
  "fur": { "3": "#D9380B" }, "pattern": { "0": "#3B2A6B" }, "marking": { "0": "#FFF4E0" } }
```
Eye keys are the game's slot names (`python wcmods.py eyes`). Some names don't match the colour
(`Yellow` is green). One colour keeps the game's shading; a list is spread from pupil to rim. The
cat creator's eye buttons are recoloured to match. Coat, pattern and marking keys are slots 0–24
(0–14 natural, 15–24 bright extras); `python wcmods.py tables` lists the game's originals.

A recoloured slot changes every cat with that slot. To add colours instead, give **pattern** and
**marking** colours slot numbers from 25 up:
```json
{ "pattern": { "25": "#ff00cc" }, "marking": { "25": "#00e5ff", "26": "#7cfc00" } }
```
The game's colours stay as they are, and only cats set to a new slot wear it (the Your cat page or
`cats.json` picks it for your cat). Slot numbers are fixed, so several palettes can each add colours,
and your cat keeps its colour whatever else you turn on. Quick palettes leave alone a palette that
only adds slots. The game checks these indexes against the colour list's real size, so a new slot
nobody adds just shows no colour, never a crash.

Coat colours can't take new slots. The game pairs each of its coat colours with paw, ear, nose and
whisker colours it keeps in its code, and a coat slot past 24 has none, which crashes it. To give
just your cat a coat colour of its own, use `cats.json`'s `colours`.

#### Ready-made palettes

Ten themed palettes are in [wcmods-examples](https://github.com/HexOffender/wcmods-examples): ThunderClan Forest, RiverClan
Waters, ShadowClan Night, WindClan Moor, SkyClan Sunset, StarClan Silverpelt, Dark Forest, Leaf-bare
Frost, Pastel Kits and Vivid Clans (`palette-*`). Add the ones you want from its .zip on the Mods page,
or with `python wcmods.py add ../wcmods-examples/palette-dark-forest`. Each one recolours coats,
patterns, markings and eyes. The
natural coats are a colour grade of the game's own, so every slot keeps its place from light to dark;
the bright extras and the eyes get the theme's own colours.

To switch quickly, tick palettes under **Quick palettes** on the Palettes page and press **Apply**,
with the game closed. That turns the ticked palettes on, turns the other palette-only mods off, and
installs. If the install fails, the previous choice is put back. Mods that hold anything besides a
palette are never touched.

Pick one theme at a time; two themes together show only one of them. Eyes-only and coats-only
palettes (Gemstone Eyes, Richer Coats, StarClan Glow Eyes) go on top of a theme, because the themes
are priority -10. From the command line:

```
python wcmods.py palette                                     # list the palette mods and which are on
python wcmods.py palette palette-starclan-silverpelt         # use just that one, and install
python wcmods.py palette palette-dark-forest gemstone-eyes   # Dark Forest coats with gemstone eyes
python wcmods.py palette --none                              # back to the game's colours
```

`tools/make_palettes.py --out ../wcmods-examples` generates them from the game's colours
(`colour_tables.json` and the eye atlas), into a checkout of wcmods-examples. Edit its themes and run it
again to change them. It keeps each one's priority and anything else you added to its `mod.json`. A
palette you've added is your own copy, so add it again to get the new one.

### `cats.json`
```json
{ "player": { "colours": { "fur": "#9fb6e0", "paws": "#ffb6c1", "ears": "#ff9aa6", "nose": "#ff7b9a", "whiskers": "#ffffff" },
              "slots": { "fur": 11, "pattern": 25, "marking": 26 } } }
```
- **`colours`** go onto your cat's own materials while you play. That covers menus and portraits,
  and every part is optional. No other cat changes, and any colour works, including paws, ears,
  nose and whiskers, which have no slots at all. The game sets your cat's colours again whenever it
  sets your cat up, so the UE4SS script (`WCModsCatLook`) puts yours back twice a second.
  Uninstalling brings your saved colours back.
- **`slots`** picks which colour slot your cat wears, written into your save on install, after a
  backup: `fur` 0–24 (20–24 are the Feral Edition's, which the game swaps without it), `pattern`
  and `marking` any slot, including new ones a palette adds. Leave a part out to keep your save's.

### `controls.json`
```json
{ "keyboard": { "Player_Interact": "F", "Player_Movement_Up": "K" },
  "keys": { "I": "W", "Escape": "P" },
  "menus": { "keys": { "Escape": "BackSpace" } },
  "gamepad": { "Player_Run": "LT" } }
```

- **`keyboard`** moves an action to a new key: here Interact goes from E to F. Actions are the game's;
  `python wcmods.py controls` lists them with their keys. The game's axis actions list only one
  direction, so `Player_Movement_Up` is the back key (S) and `Player_Camera_Right` is the left key.
- **`keys`** maps a key you press straight to a game key while you play. Use it for keys no action
  lists: the built-in W, D, Up and Right, or any other key the game uses. `"T": "W"` makes T go
  forward and W stop. The game key stops working on its own once something stands in for it, unless
  an action still uses it (then it's a second key for that job). Enter, Space, Escape, Backspace
  and Tab always keep working.
- **`menus`** is a separate set of key pairs used only while the game shows a menu with its cursor
  (the title screen is confirmed; check the pause menu and others with `play --debug`). Here `Escape`
  opens the pause menu while playing (it sends P) and closes menus (it sends Backspace). In menus the
  game's own keys keep working too. A letter, digit or Space used here also changes what you type on
  the name screen, and the build warns about it. A press finishes as it started: the Escape that opens
  the menu is released as P. Remapping Escape (or Enter, Space, Backspace, Tab) while playing means
  prompts and dialogue shown during play don't get it; the build warns about that too.
- **`gamepad`** is kept for planning. The remapper doesn't handle controllers; use Steam Input.

Keys are Unreal key names. Controller buttons also take short names (A/B/X/Y, LB/RB, LT/RT,
Start). The build checks the names, and `python wcmods.py play` applies keyboard and mouse remaps
(see [Remapping keys](#remapping-keys)).

### `mouselook.json`
```json
{ "sensitivity": 1.0, "invert": false, "smoothing": 0, "toggle_key": "F6" }
```
The game switches Unreal's mouse capture off (`DefaultViewportMouseCaptureMode=NoCapture`), so
the mouse never reaches its camera and no binding can change that. Mouse look is a UE4SS script
instead. While you explore with the cursor hidden, it captures the mouse and moves the camera
(`BP_AdventureCamera`) itself. It lets go whenever the game shows its cursor. The arrow keys
and right stick still work. `toggle_key` switches it off and on in game. R (or LB) levels the
tilt. `pitch_min`/`pitch_max` limit the tilt (default -20/23, the game's own). `smoothing` is how
long the camera takes to catch up with the mouse, in milliseconds: 0 (the default) follows it at
once, and the game eases the arrow keys and stick over about 200. `"debug": true` logs what it
does to `ue4ss\UE4SS.log`, including whether each turn stayed and how even the frames were. The
`mouse-look` mod and the Mouse look card on the Controls page both edit this file.

How it moves the camera, for anyone extending it: turning rotates the camera actor's root. The
game resets the spring arm's and the camera's pitch every frame, so tilting goes through a scene
component the script adds between the root and the arm. Rotators are built with
`KismetMathLibrary:MakeRotator`, because UE4SS drops the pitch of a rotator passed as a Lua table.

How the game's camera works (read from its code, `SwtAdventureCameraActor`):
- It's an actor of its own that follows the cat: a root that turns, the game's spring arm on it,
  and the camera on the end. Its numbers are `Gameplay.Exploration.Camera.*` in `TuningData.csv`,
  read once when the camera starts.
- Each frame it adds that frame's arrow-key and stick turn to the root's current rotation, so a
  turn the mouse made earlier in the frame stays.
- On a camera spline (`SplineActor`), while it looks at something, and for 0.8 s after joining or
  leaving a spline, it sets the rotation itself and ignores the arrow keys. The mouse can't turn
  it then either.
- The spring arm eases after the root (`CameraRotationLagSpeed`, from `Lag.Rotation` 5). Mouse look
  sets that from `smoothing` while it has the mouse and gives the game's back when it lets go.
- While the cat moves, the camera itself leans up to 15° toward where it's heading
  (`Ahead.Rotation`). Set that to 0 with `data.json` for a camera that only turns when you turn it:
  `{ "TuningData.csv": { "Gameplay.Exploration.Camera.Ahead.Rotation": 0 } }`.

Known issues:
- With `smoothing` above 0, fast diagonal moves roll the camera slightly, because the spring arm
  eases turn and tilt together.
- Mouse look stops when the engine's look input is switched off (`IsLookInputIgnored`), but the
  game's own camera locks (`EInputRestriction::CameraRotationDisabled`) aren't visible to scripts,
  so the mouse may still turn the camera where the arrow keys can't.

### `data.json`
```json
{ "CombatBaseExperience.csv": { "*": { "BaseExperience": "x2" } },
  "TuningData.csv": { "Gameplay.Exploration.Player.MoveAndRun.Run.Speed": 450 } }
```
Rows are matched by their first column. `"-": ["53"]` removes rows and `"+": [{ "#": "91", ... }]`
adds them (missing columns stay empty).

### `items.json`
```json
{ "items": [ { "id": "MoonHerb", "like": "MediumHealingHerb", "name": "Moon Herb",
               "description": "Health Recovery (medium). Picked under a full moon.",
               "recipe": { "Dandelion": 2, "Cotton": 1 }, "give": 3 } ] }
```
New herbs, materials and accessory looks: a name, a description and an icon in the inventory, what
the herb does (one of the game's herb effects), a recipe at the medicine cat's bartering, and some
to start with. `like` borrows the rest from a game item, and `"recipes"` changes what the game's own
herbs and accessories cost. An icon or a look can be a PNG of the mod's own or one of the game's
recoloured (`{"tint": "#a8c4ff"}`, made from your game files at install); `python wcmods.py texture
<item or accessory>` saves the game's as a PNG to paint over. New looks work for neck, body and paw
accessories, not head ones. Every key is in [SDK.md](docs/SDK.md) ("New items"). New items need the
Oodle DLL.

### `names.json`
```json
{ "prefixes": { "rename": { "Otter": "Moth" }, "add": { "Sparrow": { "like": "Wren" } }, "remove": ["Pigeon"] },
  "suffixes": { "rename": { "pelt": "coat" }, "add": { "whisper": {} }, "remove": ["face"] },
  "rogues":   { "rename": { "Chesnut": "Chestnut" }, "add": ["Moss"], "remove": ["Fury"] },
  "banned":   { "add": ["Lionheart"], "remove": ["Tigerstar"] },
  "names":    { "Brightheart": "Brightfur" },
  "cats":     { "player": "Mothheart", "Blaze": { "fixed": "Sparkle" }, "Cedarkit": { "prefix": "Glimmer" } } }
```
A clan cat's name is a prefix and a suffix (Otter + paw). The suffix changes with rank: kits are
-kit, apprentices -paw, leaders -star. `python wcmods.py names` lists every part with your mods'
changes, and `names --cats` lists the cats in your save. The **Names** page in the studio edits all
of this. Names are matched by their English text (any case) or ID.

- **`prefixes` / `suffixes`:**
  - `rename` changes every name with that part: Otterpaw, Otterheart and the rest become Mothpaw,
    Mothheart.
  - `add` makes a new part that every combination exists for. `like` copies how often another part
    is used (each clan for prefixes, each rank for suffixes) and how it's suggested on the name
    screen. Without it, the new part gets the average.
  - `remove` stops the game handing a part out; cats that already have it keep their names. The
    kit, paw and star suffixes are kept, because kits, apprentices and leaders need them.
  - `weights` sets how often one is used, e.g. `{ "Fern": { "ThunderClan": 0.07 } }`.
- **`rogues`:** the whole names cats outside the clans get.
- **`banned`:** names the game never hands out (mostly canon characters). `add` takes any prefix +
  suffix the game can make, and `"clear": true` empties the list.
- **`names`:** changes every text that's exactly this name, including the nine canon cameo cats.
  Some cameo names are also clan names (Brightheart is Bright + heart), so both change. `text`
  sets any of the game's text by key: `{ "STR_BOT_NAME_1": "..." }`.
- **`cats`:** renames cats in your save on install, after a backup. Each key picks a cat: `player`,
  its current name, or its place from `names --cats` (`RiverClan/Warrior/3`).
  - A plain name must be a prefix + suffix the game can make, new ones included. Otherwise it's
    used as a fixed name.
  - `{ "prefix": "Glimmer" }` gives the cat its own prefix that grows with rank: Glimmerkit, then
    Glimmerpaw.
  - `{ "fixed": "Sparkle" }` never changes.

  Story roles (`{THE AGING LEADER}` in dialogue) show the cat cast in them, so renaming that cat
  renames the role. A cat is skipped if its name changed between building and installing.

Renames change the English text only. The other languages translate names, and those translations
stay. Added names and parts appear in every language with their English text. Added parts get IDs
made from their name (`STR_CAT_NAME_WCM_SPARROW`), so saved cats keep their names whatever else
your mods add.

### `save.json`
```json
{ "set": { "0/GameplayProgression/Level": 5 },
  "add": { "0/GameplayProgression/State/Inventory": { "Gameplay.Inventory.Consumable.SmallCatnip": 5 } } }
```

## Appearance vs gameplay

The game rolls traits (Ambitious, Brave, Wise, Energetic, Curious, Patient) from body, ear and
face shape. Stats come from your Clan. Your save stores which *slot* each option uses, not the
colour.

- **Palettes are appearance-only.** They redraw a slot; your cat keeps the same slot, so traits
  and stats don't change. Suggested names follow the slot.
- **Game data and save edits are gameplay changes.** That's their purpose. The tool warns when
  an edit touches the online den-visit tables (`OnlineGifts.csv`, `VisitRewards.csv`), the
  trait-driving body, ear or face odds, or replacement files not known to be appearance-only.

## What's verified

`selftest` checks, against your install:
- **Game files:** reading the paks, container and save; Oodle decompression; the eye atlas layout.
- **Writers:** paks and IoStore containers read back identically, with correct BLAKE3 chunk hashes.
  The pak's directory index stores file names the way the game's own pak does (see below).
- **CSV editor:** reproduces all 67 runtime tables byte-for-byte.
- **Cooked assets:** the item table's 412 rows read and write back byte-for-byte; texture copies get
  the IDs the game's own packages have; the accessory look lists read back with new looks added.
- **Save editor:** changes only the values it's told to.
- **UE4SS scripts:** the generated Lua has balanced blocks and brackets (a light structure check;
  there's no Lua interpreter to fully parse it). Builds also warn if any UE4SS script fails it.

Confirmed in game (2026-10-23):
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
  Save edits are applied after a backup: restore one from the Mods page (or
  `python wcmods.py restore latest`) if anything goes wrong.
- Edited key bindings in the save are ignored, and the game's rebinding screen doesn't work on PC
  (see [Remapping keys](#remapping-keys)).
- The key remapper (`wcmods play`) moves keys while you play and leaves other windows and the title
  screen alone. The pause menu hasn't been checked yet.

Confirmed in game (2026-10-24):
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

Confirmed in game, items (2026-10-24):
- New herbs and materials show in the inventory with their names, descriptions and icons. Their
  recipes show at the medicine cat's bartering, and trading works.
- New textures load: icons from a PNG and recoloured ones, and a new collar look, worn in its new
  colour and made at bartering. Accessories you already have show as an empty slot there, the
  game's own too.

Confirmed in game, scripting (2026-10-24):
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
- **The new mod menu pages** (Game, Game switches, Inspector, Console) run against the live game
  without errors. They were checked with a recording stand-in for the menu, not opened on screen.

Not yet confirmed in game:
- **Scripting:**
  - the mod menu's new pages on screen;
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
- **Parts of the mod menu.** Not yet checked: Save on the Mouse look and Your cat pages, cats'
  own names in Nearby labels, and god mode, game speed and teleport on the Cheats page.
- **Mods' own cooked paks (`paks/`).** They're installed as the game's own patch paks are named,
  but no cooked content has been tried in game yet.
- **Names beyond the text.** Renamed and added names reach the game's text table (Mothpaw,
  Sparrowheart, Mothwhisper and the rogue Moss were read back in game). Still unchecked: new cats
  getting added parts, removed parts and ban list changes; the name screen's suggestions; and cat
  renames in a save (they're applied after a backup, so `restore latest` undoes them).

After a game update, run `selftest` before installing again.

## Requirements

Clan Mod Studio's "Get set up" sees to these:

- **Python 3.10 or newer.** The launchers offer to install it with winget (Windows' own installer)
  or send you to python.org. The Microsoft Store's Python works too.
- **UE4SS**, the script loader, for coat, pattern, marking and eye-button colours, your cat's own
  colours, mouse look, the mod menu (with its cheats), overlays and scripts from mods.
  - **Install it:** "Install it" downloads the `UE4SS_v*.zip` from its `experimental-latest` GitHub
    release (tried with `UE4SS_v3.0.1-1181-g83330635.zip`) and puts it in the game. Or give the
    studio that .zip yourself.
  - **How it's set up:** its debug console windows are off. Its cheat-manager enabler is off too,
    because the mod menu's Cheats page does that job and can switch cheats off again.
  - **The game's console:** UE4SS's console enabler (`ConsoleEnablerMod`) is on, so `~` or F10 opens
    it (`python wcmods.py console off` turns it off).
  - **Removing it:** delete `dwmapi.dll` and the `ue4ss` folder from `<game>\Wrc\Binaries\Win64`.
- **Optional:** an `oo2core_*_win64.dll` from another installed game, found automatically on your
  Steam libraries (here: Planet Zoo), or picked in "Get set up". It's only used to read the game's
  compressed files, which mods that change names, game data or eye colours need. Without it,
  palettes still change coats, patterns and markings, and say that eye colours were left out.
