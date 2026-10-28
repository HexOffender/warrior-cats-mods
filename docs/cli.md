# The command line

Everything Clan Mod Studio does is also a command, for anyone who likes a terminal and for mod makers.
Nobody needs it to make or play with mods: the studio does all of this with buttons.

Open a terminal in the Clan Mod Studio folder (the one with `wcmods.py` in it) and type
`python wcmods.py` and a command (`py -3 wcmods.py` works too). `python wcmods.py --help` lists every
command in groups, and `python wcmods.py <command> -h` says more about one. The commands and the studio
share your files ([setup.md](setup.md#your-files)), so a change made with one shows in the other.

## Playing

```
python wcmods.py status      # the game, your save, your files' folder, the script loader, and your mods
python wcmods.py studio      # what double-clicking Clan Mod Studio does
python wcmods.py backup      # back up your save now
python wcmods.py restore     # list your save backups
```

- `studio --port <n>` opens on another port (8765 to begin with), `--no-browser` doesn't open your
  browser, and `--add <zip or folder>` opens with that mod ready to add, as dropping it on
  `Clan Mod Studio` does.
- `restore <name>`, or `restore latest`, puts a backup back, with the game closed.
- `cheats [on|off]` shows, or sets, whether the Menu pages mod's Cheats page starts with cheats on, from
  the next time the game starts.
- `console [on|off]` shows, or switches, the game's own command window (`~` or F10; it needs the
  [script loader](guide/README.md#script-loader)), from the next time the game starts.
- `play` starts the game through Steam with the old key remapper, and `remap` runs the remapper while the
  game runs. Both are deprecated: key changes work inside the game now, and the old remapper is only for
  what a script can't reach, such as moving the cat and the camera on other keys.
  [remapping.md](remapping.md#the-old-key-remapper-outside-the-game-deprecated) has their options.

## Mods

```
python wcmods.py add "Cool Mod v1.2.zip"   # add a downloaded mod: a .zip of one or more mods, or a folder
python wcmods.py remove cool-mod           # take it out of your mods folder (kept in backups\mods)
python wcmods.py install                   # build the mods that are on and put them in the game (game closed)
python wcmods.py uninstall                 # take everything wcmods put in the game out again
python wcmods.py pack my-mod               # my-mod-1.0.zip, to share
```

- `enable <mod>...` and `disable <mod>...` switch mods on and off by folder name. `enable` (and `add`,
  unless `--off`) also turns on the mods it requires; `disable` and `remove` refuse while mods that are on
  need it, and `--with-dependents` turns those off too.
- `add` puts a .zip that holds several mods in switched off, unless you say `--on`; `--only a,b` adds
  just those.
- `install` stops if any mod failed to build, because installing would remove what that mod put in the
  game before. Fix the mod or turn it off, or use `install --force` (the studio's **Apply the rest
  anyway**) to install everything else.
- `uninstall` leaves your save as it is: changes your mods made to it stay. `restore` puts a backup back.
- `build` builds the mods that are on into `build\`, in the Clan Mod Studio folder, without putting them
  in the game (the studio's **Check my mods**).
- `pack <mod> [file]` writes the mod's .zip, named after its folder and version unless you name it.
- `palette` lists your palette mods. `palette <id>...` switches to those (the other palette-only mods go
  off) and installs; `--none` switches every palette-only mod off, for the game's colours;
  `--no-install` only switches them; `--force` installs even if some other mods failed to build.
- `addons` lists the mods that go with Clan Mod Studio, with GitHub's latest of each. `addons add <id>`
  adds or updates one (`menu-pages`, `sandbox`, `creator-palettes` or `emote-wheel`), and `--zip <file>`
  takes a .zip you downloaded instead. `menu-pages [--zip <file>]` does the same for Menu pages.

## Making mods

```
python wcmods.py new my-mod --kind palette      # start a mod from a template
python wcmods.py files "*NPC/*.csv"             # list the game's files that match
python wcmods.py extract "*NPC/CatSize.csv"     # copy them into vanilla\ to start a files mod
```

- `new <name> --kind palette|controls|files|data|items|save|names|script|cpp` (palette when you leave it
  out). [formats.md](formats.md) describes each file, and [SDK.md](SDK.md) the folder.
- `texture <what>` saves one of the game's textures as a PNG to paint over: an accessory's look
  (`Neck.DogCollar.1`), an item's icon (`SmallHealingHerb`) or a `/Game/...` path. It goes in
  `vanilla\textures\`, or where `--out` says.
- `model <accessory>` saves an accessory and the cat as OBJ files, with the look as a PNG, to make a model
  of your own on (`--out` for the folder).
- `animation [cat|mouse|bird|...]` saves the cat, or an animal, rigged to the game's skeleton as a .glb
  to animate in Blender; `animation --check <file>` says which animations a .glb or .gltf holds, and
  which of the game's bones they move.
- `eyes` lists the eye colour slots and their colours now.
- `tables` reads the coat, pattern, marking and eye-button colour tables from the game's log (after the
  game has started once with the script loader) and saves them as `colour_tables.json` in the Clan Mod
  Studio folder. The studio's colour pages read the log themselves, and that file when the log has none.
- `names [--cats] [--json]` lists the game's name parts, rogue names and ban list with your mods' changes,
  or with `--cats` the cats in your save.
- `controls [--json]` shows the key bindings stored in your save, which the game ignores
  ([remapping.md](remapping.md#why-remaps-happen-while-the-game-runs)).

## In the game

These need [mods that run code](guide/README.md#code-mods) allowed, an install since you allowed them,
and the game running (`game` on its own just says whether it is).

```
python wcmods.py lua "Game.cat():name()"    # run Lua in the game; an expression shows its value
python wcmods.py lua -f my-test.lua         # run a .lua file
python wcmods.py inspect "Game.player()"    # an object's properties and functions
python wcmods.py find WrcRoamingEnemy       # the game's objects of a class
python wcmods.py game                       # is the game running with the bridge?
python wcmods.py game types                 # Lua type files for your editor
```

- `inspect --all` adds the engine's own Actor and Object members.
- `find --limit <n>` lists at most that many (50 to begin with). Reading many objects at once has crashed
  the game just after a level loads, so use it once your cat is in the world.
- `--timeout <seconds>` waits longer for an answer, and `--json` prints the whole reply.
- The studio's **Try Lua in the game** page (under Advanced) does what `lua` and `inspect` do.
  [scripting.md, The game bridge](scripting.md#the-game-bridge) says how it works.

## After a game update

```
python wcmods.py game build              # the installed build, what wcmods followed, and mods made for older ones
python wcmods.py allow-outdated my-mod   # use a mod made for an older version anyway, on this build
```

- `game build --refresh` looks for what moved again.
- `allow-outdated <mod> --off` leaves it out again.
- `game signatures check` checks the installed exe against wcmods' signatures.

[updating.md](updating.md) says what all of it means.

## C++ mods

```
python wcmods.py new my-mod --kind cpp
python wcmods.py cpp setup              # UE4SS's source, at the commit of the game's UE4SS
python wcmods.py cpp build my-mod       # builds its cpp\ into dlls\main.dll
```

- `cpp` alone says what's ready.
- `cpp setup --commit <commit>` names UE4SS's commit, when the game hasn't run with UE4SS yet.
- `cpp build --watch` builds again whenever a file in `cpp\` changes; `--keep` also keeps the DLL as
  `dlls\<UE4SS commit>\`, for a mod that carries builds for several UE4SS versions.
- `cpp ide [--open]` makes a Visual Studio solution (and opens it).
- `cpp crash` says which mod the game's last crash was in.
- The Mods page's **Build C++**, under a C++ mod's **More**, builds that mod.

[SDK.md, C++ mods](SDK.md#c-mods) lists what building needs.

## Testing and checking

```
python wcmods.py selftest     # checks every file format against your install
python wcmods.py agent test   # runs the in-game tests in tests\game and writes a report with pictures
```

`selftest` reads the game and your save and writes only to a temporary folder. After a game update, run
it before installing again. The tests that run without the game are in
[CONTRIBUTING.md](../CONTRIBUTING.md#checks-to-run).

`agent ...` drives the game for testing, by hand or by an AI agent:
- **The game:** `agent launch --world` starts it and plays into the forest, and `agent quit` closes it.
- **The mod menu:** `agent menu read Stats` and `agent menu set Health 150` read and use its pages.
- **Keys:** `agent key W --hold 2` walks.
- **Pictures:** `agent shot --menu` saves a picture of the mod menu.
- **Tests:** `agent test` runs the in-game tests.

`agent install` puts in a test build with the bridge. It allows code mods for that build, so the code of
every mod that's on runs, downloaded ones included: turn off any you don't trust first. Your settings in
`wcmods.json` stay as they are; like any install, it updates the record there of what's installed.
[agent.md](agent.md) has every agent command.

[verified.md](verified.md) lists what has been confirmed in the game, by date, and what hasn't been yet.
