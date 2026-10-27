# How wcmods is built

A map of the code for anyone changing it. What each part does for a player is in the
[README](../README.md); what it offers a mod maker is in [SDK.md](SDK.md).

## The repository

| Where | What |
|---|---|
| `wcmods.py`, `Clan Mod Studio.bat`, `Play with key remaps.bat` | The entry points: the command line, and the launchers a player double-clicks (the second, for the deprecated key remapper) (`wcmods/findpython.bat` finds or offers to install Python) |
| `wcmods/` | The Python package (below) |
| `wcmods/lua/` | wcmods' in-game Lua, as `.lua` files: the shared modules, the mod menu's host and pages, and the scripts the sections write for mods. The Python module beside each one reads it and fills its `@TOKENS@` in |
| `wcmods/sections/` | The eleven built-in build sections, one per kind of mod content |
| `wcmods/agent/` | The agent controller that drives the running game ([agent.md](agent.md)) |
| `wcmods/cpp_sdk/` | `WCMods.hpp` and its headers for C++ mods, and the build files `cpp ide` makes |
| `wcmods/templates/` | What `wcmods new --kind ...` copies |
| `studio/` | Clan Mod Studio's front end: `index.html`, `app.js` (the shell: side bar, Apply and Play, the log drawer), `lib/wc.js` (the helpers every page uses), `sections/*.js` (one module per page) |
| *(not in the repository)* | The player's own files: `mods/`, `wcmods.json` and `backups/`, in `%LOCALAPPDATA%\WCMods` (`config.data_dir()`, `WCMODS_DATA` to move it), so `git pull` or a new download never touches them. Older versions kept them here; `userdata.migrate` moves them out on the first start |
| `tests/` | `unit/` (pytest, no game), `game/` (in-game, run by `agent test`), `cpp-sdk/` (a C++ test mod), `kraken/` (fixtures for the decoder) |
| `tools/` | Generators (`make_palettes.py` for wcmods-examples, `make_kraken_fixtures.py`) and `re/`, the reverse-engineering scripts behind [reverse-engineering.md](reverse-engineering.md) |
| `docs/` | The documentation ([docs/README.md](README.md) lists it) |

wcmods needs nothing installed beyond Python 3.10+: no packages, no DLLs, no compiled code in the
repository. The game's Kraken compression is decoded in pure Python (`formats/kraken.py`); an Oodle
DLL from another game is an optional speed-up a player points `wcmods.json` at.

## The package

`wcmods/` by responsibility:

| Group | Modules | Notes |
|---|---|---|
| **The mod manager** | `cli` (the commands), `config` (`wcmods.json`, finding the game and the player's own folder), `userdata` (that folder: moving an old install's files into it, and an old `mods/mod-menu`'s settings into `wcmods.json`), `mods` (mod folders and `mod.json`), `modzip` (adding and packing .zips, what's refused), `pipeline` (build and install), `sdk` (`Section`, `BuildContext`, `lua_value`), `onboarding` (Get set up, Play), `studio` (the local web server behind Clan Mod Studio), `ue4ss` (the script loader), `menusettings` (the mod menu's key, button and size in `wcmods.json`, and the game's console), `menupages` (the Menu pages mod: adding and updating it from its GitHub releases), `cppmods` (building C++ mods), `crashes` (reading the game's crash reports), `luacheck` (a bracket check on generated Lua) | `cli` imports the heavy parts lazily so `status` starts fast |
| **`formats/`** | `pak`, `iostore` (the `.utoc`/`.ucas` containers), `kraken` and `oodle` (decompression), `cooked` (cooked packages and DataTables), `csvdata` (format-preserving CSV), `texture`, `skelmesh` (skeletal meshes: accessories and the cat), `png`, `bcn` (DXT), `save` and `savejson` (the save file and its JSON), `blake3`, `cityhash`, `binio` | Layered: `gamefiles → iostore/pak → oodle → kraken`, `texture → bcn/png/cooked`, `skelmesh → cooked`. Shims at the old top-level names keep `wcmods.csvdata`, `savejson`, `cooked`, `texture`, `png` and `bcn` importable, as SDK.md documents them for mods' `section.py` |
| **`exe/`** | `pe` (reading the exe), `x64` (decoding its code), `signatures` (finding the hidden members again after a game update; `signatures.json`), `gamebuild` (which build Steam installed, mods made for older ones) | Nothing here runs the game ([updating.md](updating.md)) |
| **Game content helpers** | `gamefiles` (the reader every section uses), `names`, `palettes`, `eyeatlas`, `colors`, `recolor`, `accessories`, `models` (a mod's own models for accessories: OBJ and glTF, tied to the cat's body), `catcolours` (your cat's colours and scars), `controls`, `keymap` (both remap plans), `mouselook`, `playstate` | Each knows one of the game's tables or files and the mod file that edits it |
| **In-game Lua generators** | `game` (`WCModsGame`), `menu` and `menupages` (the mod menu's module, host and pages), `draw`, `view`, `world` (the other shared modules), `bridge` (the Lua bridge the console and agent use), `mouselook`, `catcolours`, `palettes`, `playstate`, `gameremap` (the in-game key remap), `models` (`WCModsModels`, which puts mods' models on the cats wearing them) (scripts written per install) | Each reads its Lua from `wcmods/lua/` and fills the settings in with `str.replace` on `@TOKENS@`; they import nothing but `lua_value` |
| **Windows** | `remapper` (the old key remapper outside the game, deprecated, for what `gameremap` can't do: low-level hooks), `wininput` (the SendInput structs it and the agent share) | |
| **Checks** | `selftest` (`python wcmods.py selftest`, against the installed game), `agent/` (in-game tests) | `tests/unit/` runs the game-free parts of the self-test under pytest |

## The build pipeline

`pipeline.build(cfg, mods, out)` runs every section over every enabled mod (`sections/__init__.py`
loads the built-in ones and any `section.py` a mod brings, when code mods are allowed). A section's
`collect(mod, ctx)` reads and validates its file; `apply(items, ctx)` adds outputs through one
`BuildContext`: files for the mod pak, CSV edits merged across mods, patched cooked assets, UE4SS
scripts and shared modules, save edits. A section that fails is rolled back and reported; the others
still build. `pipeline.install` then writes the build into the game (`Paks\~mods\zzz_WCMods_*`,
`ue4ss\Mods\WCMods*`, `ue4ss\Mods\shared\WCMods*`) and records what it installed in `wcmods.json`.

The mod menu is wcmods' own and goes in with every build: `menu.host_script` writes the window's
script with the build's manifest, its key, button and size (`wcmods.json`, `menusettings`) and its own
pages (`lua/menu_host_pages.lua`: Overview, Installed mods, Log, Menu, Inspector, Lua console) in; the
shared `WCModsMenu` module is what other scripts add pages through. The pages about the game are a mod
of their own, Menu pages, in its own repository
([HexOffender/wcmods-menu-pages](https://github.com/HexOffender/wcmods-menu-pages)); `menupages`
fetches it into the player's mods and tells the Overview what to say while a build hasn't got it. It
uses nothing a mod can't: `WCModsMenu`, `WCModsGame` and `WCModsNames` (whose area names and quest
titles `world.place_names` reads from the game's tables at install).

## Where things are named

The same thing has an id in three places; keep them matching when adding one:

| | Build section (`sections/`) | Studio page (`studio/sections/`, `studio.BUILTIN_SECTIONS`) | Mod file |
|---|---|---|---|
| Palettes | `palettes` | `palettes` | `palette.json` |
| Your cat | `cats` | `cat` | `cats.json` |
| Controls (and mouse look) | `controls`, `mouselook` | `controls` | `controls.json`, `mouselook.json` |
| Names | `names` | `names` | `names.json` |
| Game data | `data` | `data` | `data.json` |
| Items | `items` | `items` | `items.json`, `pictures/`, `models/` |
| Save | `save` (`savedit.py`) | `save` | `save.json` |
| Replacement files | `files` | (no page) | `files/` |
| Scripts | `scripts` | `console` (the Lua console, with code mods) | `scripts/`, `settings.json` |
| C++ mods | `cpp` | (the mod's card) | `cpp/`, `dlls/` |
| Mods, Settings and repair | | `mods`, `settings` | |

The mod menu's groups are `menu.GROUPS` in `wcmods/menu.py`; the Lua, the agent's menu driver and the
C++ SDK's comments follow it, and the Menu pages mod puts its pages in them by id.

## Checks

- `python -m pytest`: `tests/unit/`, no game needed (CI runs this).
- `python wcmods.py selftest`: every format against the installed game, writes only to a temp folder.
- `python wcmods.py agent test`: the in-game tests, with pictures ([agent.md](agent.md)).

[verified.md](verified.md) keeps what has been confirmed in game and what hasn't.
