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
- **Other people's mods are theirs.** `mods/` is the player's folder; only `mods/mod-menu/` is wcmods'.

## Checks to run

```bash
python -m pytest
```

```bash
python wcmods.py selftest
```

```bash
python wcmods.py agent test
```

`pytest` (install it with `python -m pip install pytest`) runs `tests/unit/`, which needs no game;
it's what CI runs. `selftest` checks every file format against the installed game and writes only to
a temp folder. `agent test` drives the running game through the in-game tests in `tests/game/`
([docs/agent.md](docs/agent.md)); it needs the game and UE4SS, and backs up the save first. A change
to the Lua, the mod menu or a section wants all three; a change to a format, the first two.

## Writing it down

Findings about the game go in [docs/reverse-engineering.md](docs/reverse-engineering.md) or
[docs/mechanics/](docs/mechanics/README.md), with how they were confirmed. What has been seen working
in game goes in [docs/verified.md](docs/verified.md), by date; what hasn't is listed there too, so
nobody assumes it. User-facing text (the studio, the mod menu, the CLI) says the same thing in the
same words on every surface; when a page or a button moves, search the docs and the copy for its
old name.
