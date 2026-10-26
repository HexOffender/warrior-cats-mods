# The documentation

One page per audience to start from, then the rest by topic.

**If you play with mods:** the [README](../README.md) is all you need: getting set up, Clan Mod
Studio, the mod menu in game, remapping keys, and the command line. After a game update,
[updating.md](updating.md) says what wcmods does and what a "made for an older version" mod means.

**If you make mods:**
1. [formats.md](formats.md): the JSON files a mod is made of (palettes, your cat, controls, mouse
   look, game data, items, names, save edits). No code needed; Clan Mod Studio's Make pages write them.
2. [scripting.md](scripting.md): Lua in the game with `WCModsGame`: your cat, items, quests, fights,
   events, hooks, the mod menu's pages and the live console. Read this before SDK.md.
3. [SDK.md](SDK.md): the mod folder and `mod.json`, Python build steps, studio pages, repacking and
   new content, the shared Lua modules (`WCModsDraw`, `WCModsMenu`, `WCModsView`, `WCModsWorld`),
   and C++ mods.
4. [mechanics/](mechanics/README.md): how the game's rules work and which numbers to change.
5. [reverse-engineering.md](reverse-engineering.md): the game's insides, for finding something new.

**If you work on wcmods itself:** [CONTRIBUTING.md](../CONTRIBUTING.md) (how to run the checks and
where things go), then [ARCHITECTURE.md](ARCHITECTURE.md) (how the code is laid out),
[agent.md](agent.md) (driving the game for tests) and [verified.md](verified.md) (what has been
confirmed in game, and what hasn't).

| Page | What it covers | For |
|---|---|---|
| [README](../README.md) | Getting started, Clan Mod Studio, the mod menu, remapping keys, the command line | players |
| [updating.md](updating.md) | Game updates: what wcmods follows by itself, mods made for older builds, the signatures | players, mod makers, wcmods |
| [formats.md](formats.md) | Every JSON file a mod can hold, with examples | mod makers |
| [scripting.md](scripting.md) | `WCModsGame`, script mods, the bridge and console, the mod menu's pages, the game's own UI from Lua | mod makers (Lua) |
| [SDK.md](SDK.md) | The mod folder, `wcmods.sdk` build steps, studio pages, repacking, new items and content, the shared Lua modules, C++ mods | mod makers (code) |
| [mechanics/](mechanics/README.md) | Combat, progression, exploration, clan life, items, quests, NPCs: the rules and the tables behind them | mod makers |
| [reverse-engineering.md](reverse-engineering.md) | Files and formats, the save, game objects, the camera, cheats, UE4SS, names, colours, the game's UI; the method and tools | mod makers, wcmods |
| [agent.md](agent.md) | The agent controller: launching the game, menus, keys, pictures, the in-game tests | wcmods |
| [verified.md](verified.md) | What the self-test checks and what has been confirmed in game, by date | wcmods |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The packages, the build pipeline, where the Lua and the studio live, the tests | wcmods |

**Conventions in these pages:** a finding says how it was confirmed ("seen in game", "matches the
save", "read from the code"); guesses are marked as guesses; code addresses are the build's they were
found on (reverse-engineering.md says which), while offsets inside objects usually survive updates.
