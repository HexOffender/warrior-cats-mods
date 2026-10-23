# WC Mods — mod manager for *Warrior Cats: Clans of the Forest*

A mod manager and shared modding library for the Steam version (Unreal Engine 5.7, app 3960600).

```
python wcmods.py studio      # opens Clan Mod Studio in your browser: the all-in-one manager
```

**Clan Mod Studio** has one page per kind of mod. Each page edits a file in a mod folder.
Install mods (top right) builds everything and puts it in the game:

| Page | What you change | Stored as | Reaches the game through |
|---|---|---|---|
| **Mods** | turn mods on/off, priority, new mods, uninstall, save backups | `mod.json` | — |
| **Palettes** | eye, coat, pattern and marking colours on a live cat | `palette.json` | eye atlas patch (eyes); UE4SS script (the rest) |
| **Controls** | keyboard, mouse and controller bindings; press-to-bind, conflicts, controller presets | `controls.json` | bindings in your save (not yet seen working, see below) |
| | mouse look: sensitivity, invert | `mouselook.json` | UE4SS script |
| **Game data** | XP, costs, rewards, speeds and ~440 tuning values, in any runtime table | `data.json` | edited tables in the mod pak |
| **Save** | level, XP, health, stamina, fresh-kill pile, stats, inventory, settings, anything else | `save.json` | your save, on install |

Mods can also ship whole replacement files (`files/Wrc/...`), and their own pages and build
steps written with the shared library (see [docs/SDK.md](docs/SDK.md)).

The original game files are never modified. Everything goes into
`<game>\Wrc\Content\Paks\~mods\zzz_WCMods_P.*` and `<game>\Wrc\Binaries\Win64\ue4ss\Mods\WCMods*`.
Uninstall removes those. Save edits and remaps are written into your save only after a backup.

## Command line

Everything the studio does is also available as a command:

```
python wcmods.py status      # game, save, Oodle, UE4SS, and your mods
python wcmods.py selftest    # checks every file format against your install (writes nothing)
python wcmods.py install     # builds the enabled mods and installs them (game closed)
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

### `controls.json`
```json
{ "keyboard": { "Player_Interact": "F" }, "gamepad": { "Player_Run": "LT" } }
```

Camera and movement are axis bindings, so they also take a scale (direction and sensitivity),
e.g. `{ "key": "Left", "scale": -1 }`. The keyboard entries hold the *negative* direction (← at -1).

These go into the bindings the game keeps in your save, but the game hasn't been seen using an
edited one: a test that moved Reset camera from R to T had no effect. Treat remaps as untested.

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
- The tilt levels on R and LB even if Reset camera is remapped.

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
- **CSV editor:** reproduces all 67 runtime tables byte-for-byte.
- **Save editor:** changes only the values it's told to.

Confirmed in game (2026-10-23):
- The mod pak and container load, and eye palettes change the cats' eyes.
- UE4SS runs, finds the colour tables on `BP_WrcGuiManager_C`, and its writes take effect.
- Mouse look turns and tilts the camera, gives the cursor back in menus, and toggles with F6
  (see its known issues above).
- Edited saves load, and the game keeps the edits when it saves again. The save carries a 64-bit
  checksum whose formula isn't known; the tool keeps the original value and the game accepts it.
  Save edits are applied after a backup: restore one from the Mods page (or
  `python wcmods.py restore latest`) if anything goes wrong.

Not yet confirmed in game:
- **Remaps.** A remapped key (Reset camera on T) had no effect, so the game may not read the
  bindings from the save. That test also bound the mouse to the camera keys, which the game may
  have rejected as a whole; a keyboard-only retest is pending. This game doesn't expose its live
  key bindings to mods.
- **Coat colours on screen.** The UE4SS script rewrites the fur table about two seconds after launch.

After a game update, run `selftest` before installing again.

## Requirements

- Python 3.10+ (the Microsoft Store Python works).
- An `oo2core_*_win64.dll` from another installed game, found automatically on your Steam
  libraries (here: Planet Zoo). It's only used to read the game's compressed files.
- UE4SS for coat, pattern, marking and eye-button colours. Installed from the `experimental-latest`
  GitHub release (`UE4SS_v3.0.1-1181-g83330635.zip`), with its cheat-manager and dev-console
  enablers off. To remove it, delete `dwmapi.dll` and the `ue4ss` folder from `<game>\Wrc\Binaries\Win64`.
