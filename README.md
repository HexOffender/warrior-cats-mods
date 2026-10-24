# WC Mods — mod manager for *Warrior Cats: Clans of the Forest*

A mod manager and shared modding library for the Steam version (Unreal Engine 5.7, app 3960600).

```
python wcmods.py studio      # opens Clan Mod Studio in your browser: the all-in-one manager
```

Or double-click, in this folder:
- **`Clan Mod Studio.bat`** opens the studio in your browser; close its window to stop it. If a
  studio is already running, it opens that one.
- **`Play with key remaps.bat`** starts the game through Steam with your key remaps active (see
  [Remapping keys](#remapping-keys)). It stops by itself when the game closes.

Right-click either one and choose *Send to > Desktop (create shortcut)* to launch it from the desktop.

**Clan Mod Studio** has one page per kind of mod. Each page edits a file in a mod folder.
Install mods (top right) builds everything and puts it in the game:

| Page | What you change | Stored as | Reaches the game through |
|---|---|---|---|
| **Mods** | turn mods on/off, priority, new mods, uninstall, save backups | `mod.json` | — |
| **Palettes** | eye, coat, pattern and marking colours on a live cat | `palette.json` | eye atlas patch (eyes); UE4SS script (the rest) |
| **Controls** | keyboard, mouse and controller bindings; press-to-bind, conflicts, controller presets | `controls.json` | the key remapper while you play (`wcmods play`); see [Remapping keys](#remapping-keys) |
| | mouse look: sensitivity, invert | `mouselook.json` | UE4SS script |
| **Game data** | XP, costs, rewards, speeds and ~440 tuning values, in any runtime table | `data.json` | edited tables in the mod pak |
| **Save** | level, XP, health, stamina, fresh-kill pile, stats, inventory, settings, anything else | `save.json` | your save, on install |

Mods can also ship whole replacement files (`files/Wrc/...`), and their own pages and build
steps written with the shared library (see [docs/SDK.md](docs/SDK.md)).

The original game files are never modified. Everything goes into
`<game>\Wrc\Content\Paks\~mods\zzz_WCMods_P.*` and `<game>\Wrc\Binaries\Win64\ue4ss\Mods\WCMods*`.
Uninstall removes those. Save edits are written into your save only after a backup.

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

Also: `enable/disable <mod>`, `new <name> --kind palette|controls|files|data|save`, `eyes`,
`tables`, `controls [--json]`, `files <pattern>`, `extract <pattern>`, `build`, `backup`,
`restore [name|latest]`.

## How it's built

`wcmods` is a shared library plus a set of independent **sections**. `files`, `data`,
`palettes`, `controls`, `mouselook` and `save` are built in, and mods can add more. Each section reads its
own files from every enabled mod and contributes outputs through one build context: pak files,
CSV edits (merged across mods), patched assets, UE4SS scripts and save edits. If a section fails,
its outputs are rolled back, it's marked FAILED in the build report, and the rest still build.
The studio works the same way: each page is a separate module, loaded when opened, built on
`studio/lib/wc.js`.

Mods are applied in `priority` order, then by folder name. When two mods set the same thing,
the higher priority wins.

## File formats

### `palette.json`
```json
{ "eyes": { "Amber": "#FFB300", "Sky": ["#001B2E", "#00E5FF"] },
  "fur": { "3": "#D9380B" }, "pattern": { "0": "#3B2A6B" }, "marking": { "0": "#FFF4E0" } }
```
Eye keys are the game's slot names (`python wcmods.py eyes`). Some names don't match the colour
(`Yellow` is green). One colour keeps the game's shading; a list is spread from pupil to rim. The
cat creator's eye buttons are recoloured to match. Coat, pattern and marking keys are slots 0–24
(0–14 natural, 15–24 bright extras); `python wcmods.py tables` lists the game's originals.

#### Ready-made palettes

Ten themed palettes come as mods, all off to start: ThunderClan Forest, RiverClan Waters, ShadowClan
Night, WindClan Moor, SkyClan Sunset, StarClan Silverpelt, Dark Forest, Leaf-bare Frost, Pastel Kits
and Vivid Clans (`mods/palette-*`). Each one recolours coats, patterns, markings and eyes. The
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

`tools/make_palettes.py` generates them from the game's colours (`colour_tables.json` and the eye
atlas). Edit its themes and run it again to change them. It keeps whether each one is on, its
priority, and anything else you added to its `mod.json`.

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
{ "sensitivity": 1.0, "invert": false, "toggle_key": "F6" }
```
The game switches Unreal's mouse capture off (`DefaultViewportMouseCaptureMode=NoCapture`), so
the mouse never reaches its camera and no binding can change that. Mouse look is a UE4SS script
instead. While you explore with the cursor hidden, it captures the mouse and moves the camera
(`BP_AdventureCamera`) itself. It lets go whenever the game shows its cursor. The arrow keys
and right stick still work. `toggle_key` switches it off and on in game. R (or LB) levels the
tilt. `pitch_min`/`pitch_max` limit the tilt (default -20/23, the game's own). `"debug": true`
logs what it does to `ue4ss\UE4SS.log`. The `mouse-look` mod and the Mouse look card on the
Controls page both edit this file.

How it moves the camera, for anyone extending it: turning rotates the camera actor's root, which
the game only nudges. The game resets the spring arm's and the camera's pitch every frame, so
tilting goes through a scene component the script adds between the root and the arm. Rotators
are built with `KismetMathLibrary:MakeRotator`, because UE4SS drops the pitch of a rotator passed
as a Lua table.

Known issues:
- **The camera rolls a little during fast moves.** The spring arm's rotation lag
  (`CameraRotationLagSpeed` 5, the game's `Gameplay.Exploration.Camera.Lag.Rotation`) blends turn
  and tilt together. It's also aim smoothing, which mouse look shouldn't have.
- About one frame in five, the game sets the camera's turn itself, and that frame's mouse movement
  is lost.
- Mouse look stops when the engine's look input is switched off (`IsLookInputIgnored`), but the
  game's own camera locks (`EInputRestriction::CameraRotationDisabled`) aren't visible to scripts,
  so the mouse may still turn the camera where the arrow keys can't.

### `data.json`
```json
{ "CombatBaseExperience.csv": { "*": { "BaseExperience": "x2" } },
  "TuningData.csv": { "Gameplay.Exploration.Player.MoveAndRun.Run.Speed": 450 } }
```

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
- **Save editor:** changes only the values it's told to.
- **UE4SS scripts:** the generated Lua has balanced blocks and brackets (a light structure check;
  there's no Lua interpreter to fully parse it). Builds also warn if any UE4SS script fails it.

Confirmed in game (2026-10-23):
- The mod container loads, and eye palettes change the cats' eyes.
- The mod pak's files replace the game's: an edit to the game's English text
  (`Strings_EN.csv`) renamed the player's Otterpaw to Mothpaw on screen. Paks built by earlier versions of wcmods loaded,
  but the engine found none of their files, so game data, replacement files and text edits had no
  effect; install again to rebuild them. Pak version 12 stores file names in the directory index as
  UTF-8 with no terminator (folder names keep theirs). Names written the older way read back with a
  trailing NUL, so the engine never matched them.
- UE4SS runs, finds the colour tables on `BP_WrcGuiManager_C`, and its writes take effect.
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

Not yet confirmed in game:
- **Coat colours on screen.** The UE4SS script rewrites the fur table about two seconds after launch.
- **Game data tables in play.** They load from the same pak as the text, but no gameplay change has
  been checked on screen yet.

After a game update, run `selftest` before installing again.

## Requirements

- Python 3.10+ (the Microsoft Store Python works).
- An `oo2core_*_win64.dll` from another installed game, found automatically on your Steam
  libraries (here: Planet Zoo). It's only used to read the game's compressed files.
- UE4SS for coat, pattern, marking and eye-button colours. Installed from the `experimental-latest`
  GitHub release (`UE4SS_v3.0.1-1181-g83330635.zip`), with its cheat-manager and dev-console
  enablers off. To remove it, delete `dwmapi.dll` and the `ue4ss` folder from `<game>\Wrc\Binaries\Win64`.
