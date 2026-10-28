# Contributing

wcmods is plain Python 3.10+ with no packages to install, and it stays that way: no dependencies,
no DLLs, wheels or other compiled code in the repository. Ports (the Kraken decoder) are pure Python,
and anything heavier is downloaded at setup (UE4SS) or optional (`"oodle_dll"` in `wcmods.json`).

## Getting around

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) is the map: the packages, the build pipeline, where the
in-game Lua and the studio's pages live, and the ids that have to match between a build section, a
studio page and a mod file. [docs/README.md](docs/README.md) lists every document and who it's for.

A few rules the layout follows:
- **A section owns its file.** New mod content is a section in `wcmods/sections/` that reads one
  file from a mod, a page in `studio/sections/` that writes it, and a heading in
  [docs/formats.md](docs/formats.md) that documents it.
- **Lua is in `.lua` files.** The scripts and modules that run in the game are under `wcmods/lua/`;
  the Python module beside each fills the `@TOKENS@` in. New Lua goes there too, not into Python
  strings (one short snippet, the inspector's in `bridge.py`, is the exception that remains).
- **One home per fact.** A setting, a list or a layout is defined once (the mod menu's groups in
  `menu.GROUPS`, its size limits in `menu.SCALES`) and rendered everywhere else from there.
- **Other people's mods are theirs.** A player's mods, `wcmods.json` and backups live outside the
  repository (`config.data_dir()`), so nothing a player makes is in a file git tracks. wcmods ships no
  mods: the mod menu's window is wcmods' own code, and its pages about the game are a mod in their own
  repository ([wcmods-menu-pages](https://github.com/HexOffender/wcmods-menu-pages)), which adds them
  through the same `WCModsMenu` any mod uses.

## Checks to run

```bash
python -m pytest
```

```bash
node --test "tests/studio/**/*.test.mjs"
```

```bash
python wcmods.py selftest
```

```bash
python wcmods.py agent test
```

`pytest` (install it with `python -m pip install pytest`) runs `tests/unit/`, which needs no game: the
formats, the Lua the sections write, mods and packs, and Clan Mod Studio's API and HTTP handler, called
on a studio over temporary folders (`tests/unit/conftest.py` sets that up, and keeps every test away
from the game, Steam and your own `%LOCALAPPDATA%\WCMods`). `node --test` (Node 24, nothing to install)
runs `tests/studio/`: the studio's JavaScript helpers under a small DOM shim, and the end-to-end tests
in `tests/studio/e2e/`, which start the studio on a free port and drive it in a headless Chromium over
the DevTools protocol. Those need a Chromium: Edge or Chrome where they're usually installed, or any
one named in `WC_BROWSER` (the path of `msedge.exe`, `chrome.exe` or `chromium`); without one they
skip, saying so. `selftest` checks every file format against the installed game and writes only to a
temp folder. `agent test` drives the running game through the in-game tests in `tests/game/`
([docs/agent.md](docs/agent.md)); it needs the game and UE4SS, and backs up the save first. CI runs the
first two. A change to the Lua, the mod menu or a section wants all four; a change to a format, pytest
and selftest; a change to a studio page, pytest and the node tests.

## Writing it down

Findings about the game go in [docs/reverse-engineering.md](docs/reverse-engineering.md) or
[docs/mechanics/](docs/mechanics/README.md), with how they were confirmed. What has been seen working
in game goes in [docs/verified.md](docs/verified.md), by date; what hasn't is listed there too, so
nobody assumes it. User-facing text (the studio, the mod menu, the CLI) says the same thing in the
same words on every surface; when a page or a button moves, search the docs and the copy for its
old name.
