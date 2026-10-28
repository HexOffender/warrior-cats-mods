# The documentation

One page per audience to start from, then the rest by topic.

**If you make mods without code:** the [README](../README.md) gets you set up and through a first mod,
and the [guide](guide/README.md) is the rest: the pages behind Clan Mod Studio's **Help** button and each
page's **How this works**.

**If you play with mods:** the [README](../README.md): getting set up, adding mods, the mod menu in the
game, and remapping keys. Then:
- [setup.md](setup.md): what Clan Mod Studio needs, where your files are, updating it, what it puts in
  the game, and setting it up by hand.
- [mod-menu.md](mod-menu.md): the mod menu in the game, its pages and its cheats.
- [updating.md](updating.md), after a game update: what wcmods does by itself, and what a "made for an
  older version" mod means.

**If you write mods by hand or with code:**
1. [formats.md](formats.md): the files a mod is made of (palettes, your cat, controls, mouse look,
   tweaks, game data, items, animations, characters and questlines, mod packs, names, save edits, a
   script's settings) and `wcmods.json`. No code needed; Clan Mod Studio's Make pages write them.
2. [scripting.md](scripting.md): Lua in the game with `WCModsGame`: your cat, items, quests, fights,
   events, hooks, the mod menu's pages and the live console. Read this before SDK.md.
3. [SDK.md](SDK.md): the mod folder and `mod.json`, Python build steps, studio pages, repacking and
   new content, the shared Lua modules (`WCModsDraw`, `WCModsMenu`, `WCModsView`, `WCModsWorld`),
   and C++ mods.
4. [cli.md](cli.md): every command, with examples.
5. [mechanics/](mechanics/README.md): how the game's rules work and which numbers to change.
6. [reverse-engineering.md](reverse-engineering.md): the game's insides, for finding something new.

**If you work on wcmods itself:** [CONTRIBUTING.md](../CONTRIBUTING.md) (how to run the checks and
where things go), then [ARCHITECTURE.md](ARCHITECTURE.md) (how the code is laid out),
[agent.md](agent.md) (driving the game for tests) and [verified.md](verified.md) (what has been
confirmed in game, and what hasn't).

| Page | What it covers | For |
|---|---|---|
| [README](../README.md) | Getting set up, a first mod, Clan Mod Studio's pages, adding mods, the mod menu, remapping keys, and where to go next | creators, players |
| [guide/](guide/README.md) | The guide inside Clan Mod Studio (its Help button): how the studio works, a page at a time, for people who make mods without code | creators, players |
| [setup.md](setup.md) | What Clan Mod Studio needs, your files, updating it, setting up by hand, what an install puts in the game, looks and gameplay | players, mod makers |
| [mod-menu.md](mod-menu.md) | The mod menu in the game: opening it, its pages, Menu pages, cheats, what hasn't been checked | players |
| [updating.md](updating.md) | Game updates: what wcmods follows by itself, mods made for older builds, the signatures | players, mod makers, wcmods |
| [cli.md](cli.md) | Every command, with examples: playing, mods, making mods, the game, game updates, C++, testing | players who like a terminal, mod makers |
| [formats.md](formats.md) | Every JSON file a mod can hold, with examples | mod makers |
| [remapping.md](remapping.md) | How key remaps reach the game: the in-game script, the old key remapper and its command line, what hasn't been checked | mod makers, wcmods |
| [scripting.md](scripting.md) | `WCModsGame`, script mods, the bridge and console, the mod menu's pages, the game's own UI from Lua | mod makers (Lua) |
| [SDK.md](SDK.md) | The mod folder, `wcmods.sdk` build steps, studio pages, repacking, new items, animations and content, the shared Lua modules, C++ mods | mod makers (code) |
| [mechanics/](mechanics/README.md) | Combat, progression, exploration, clan life, items, quests, NPCs: the rules and the tables behind them | mod makers |
| [reverse-engineering.md](reverse-engineering.md) | Files and formats, the save, game objects, the camera, cheats, UE4SS, names, colours, the game's UI; the method and tools | mod makers, wcmods |
| [agent.md](agent.md) | The agent controller: launching the game, menus, keys, pictures, the in-game tests | wcmods |
| [verified.md](verified.md) | What the self-test checks and what has been confirmed in game, by date | wcmods |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The packages, the build pipeline, where the Lua and the studio live, the tests | wcmods |

**Conventions in these pages:** a finding says how it was confirmed ("seen in game", "matches the
save", "read from the code"); guesses are marked as guesses; code addresses are the build's they were
found on (reverse-engineering.md says which), while offsets inside objects usually survive updates.
