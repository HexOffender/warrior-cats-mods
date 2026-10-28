# WC Mods — mod manager for *Warrior Cats: Clans of the Forest*

A mod manager and shared modding library for the Steam version (Unreal Engine 5.7, app 3960600).
This page is for playing with mods. To make them, start at [docs/README.md](docs/README.md); to work
on wcmods itself, at [CONTRIBUTING.md](CONTRIBUTING.md).

## Getting started

1. **Download** this folder (on GitHub: the green **Code** button, then **Download ZIP**) and unzip
   it anywhere, such as your Documents.
2. **Double-click `Clan Mod Studio`** in it. It opens in your web browser. The first time, if your
   computer doesn't have Python (what Clan Mod Studio runs on), it says so and offers to install it;
   say yes, then double-click it again.
3. **Follow "Get set up"**, the card at the top of the Mods page while anything is left to do. It
   finds the game, makes a safety copy of your save, and installs the script loader most mods need
   (UE4SS) with one click. If you've never played,
   start the game once first so it makes a save.
4. **Add a mod:** drop the mod's .zip on the page, or onto `Clan Mod Studio` itself, and press **Add
   to my mods**. To try some, [wcmods-examples](https://github.com/HexOffender/wcmods-examples) has palettes, mouse look and more:
   download it (**Code**, then **Download ZIP**) and drop that .zip on the page.
5. **Press Play** (top right). It puts your mods in the game and starts it. Close the game before you
   change mods; press Play again after.

To open it from your desktop, right-click `Clan Mod Studio` and choose *Send to > Desktop (create
shortcut)*. Close its black window to stop it. If it's already open, double-clicking it again
brings it back.

**Your files** (your mods, wcmods' settings and your backups) are in a folder of your own,
`%LOCALAPPDATA%\WCMods`, not in this one. Settings and repair shows it and opens it.
- **What's in it:** `mods\`, `wcmods.json` and `backups\`. Setting the `WCMODS_DATA` environment
  variable to a folder keeps them there instead.
- **Moving in:** older versions kept them in this folder. The first start after updating moves them
  across, and Apply to game puts them in the game again from there.

**Updating:** unzip a new download over the old folder, or `git pull`. Either way only wcmods
changes; your files stay as they are. The mod menu's settings (its key, controller button and size)
are in your `wcmods.json`, so they stay as well.
- **If `git pull` won't start:** it may say your changes to `mods/mod-menu` would be overwritten.
  That's because older versions saved the menu's settings there. Move the `mod-menu` folder out of
  `mods` (to your desktop, say), pull again, then move it back into `mods`. The next start takes its
  settings into `wcmods.json`.
- **The menu's pages about the game** are a mod of their own now, Menu pages (below). Get set up
  offers it after an update; until it's in, the menu has the Overview, your mods' pages and the Tools.

## Requirements

Clan Mod Studio's "Get set up" sees to these:

- **Python 3.10 or newer.** The launchers offer to install it with winget (Windows' own installer)
  or send you to python.org. The Microsoft Store's Python works too.
- **UE4SS**, the script loader, for coat, pattern, marking and eye-button colours, your cat's own
  colours, mouse look, the mod menu, overlays and scripts from mods.
  - **Install it:** "Install it" downloads the `UE4SS_v*.zip` from its `experimental-latest` GitHub
    release (tried with `UE4SS_v3.0.1-1181-g83330635.zip`) and puts it in the game. Or give the
    studio that .zip yourself.
  - **How it's set up:** its debug console windows are off. Its cheat-manager enabler is off too,
    because the Menu pages mod's Cheats page does that job and can switch cheats off again.
  - **The game's console:** UE4SS's console enabler (`ConsoleEnablerMod`) is on, so `~` or F10 opens
    it (`python wcmods.py console off` turns it off).
  - **Removing it:** delete `dwmapi.dll` and the `ue4ss` folder from `<game>\Wrc\Binaries\Win64`.
- **`wcmods.json`**, wcmods' own settings file, is made in your files' folder on the first run: where the game
  is, whether mods may run code, and what's installed ([docs/formats.md](docs/formats.md#wcmodsjson)
  lists every key). Get set up and the Settings and repair page edit it for you.
- **Nothing else.** The game's files are compressed with Oodle's Kraken, and wcmods decodes them
  itself (`wcmods/formats/kraken.py`, a Python port of the open-source [ooz](https://github.com/powzix/ooz)
  decoder, GPL-3.0). It's pure Python, so it takes a few seconds for a big texture or the item
  table; `"oodle_dll"` in `wcmods.json`, set to an `oo2core_*_win64.dll` another installed game
  ships, makes that a hundred times faster, which only shows when extracting many files.

## Clan Mod Studio

```
python wcmods.py studio      # what double-clicking Clan Mod Studio does
```

Also in this folder: **`Play with key remaps.bat`** starts the game with the old key remapper, which
is deprecated (see [Remapping keys](#remapping-keys)). Key changes work inside the game however you start
it; the old remapper is only for moving the cat and the camera on other keys. It stops by itself when the
game closes.

**Clan Mod Studio** puts your mods in the game. Its **Mods** page is where you start:
- **Add a mod:** drop a downloaded mod's .zip on the page. It shows what's in it (what the mod
  changes, whether it runs code, what else it needs) before you add it.
- **The menu's pages:** "Add the menu's pages" puts in Menu pages, the mod with the mod menu's
  pages about your cat and the game (below).
- **Example mods:** wcmods comes with no mods of its own. Example mods are in their own
  repository, [wcmods-examples](https://github.com/HexOffender/wcmods-examples): themed palettes, eye and coat colours, mouse look,
  controls, game tweaks and more. Drop its .zip on the page and tick the ones you want.
- **Switch mods on and off:** a mod that needs another turns that one on too, and turning off a mod
  that others need asks first.
- **Play** (top right): puts what's changed in the game, then starts it. Apply to game does just the
  first part. Both need the game closed, and a banner lists what isn't in the game yet. While they
  work, the panel at the bottom right shows the log as it comes, and ends with a line saying what
  happened in plain words (which mods went in, or what kept one out); after Play it closes by itself
  unless there's a warning. **Last apply** opens the last one again (it's `last-apply.log` in your
  files' folder). If some mods can't be made ready, nothing goes in until you fix or switch them off,
  or press **Apply the rest anyway**.
- **Help** (top right) opens the guide in a panel: how the studio works, your mods folder, saving,
  applying, the log, and where your files are ([docs/guide/](docs/guide/README.md)).
- **If Clan Mod Studio is updated while it's open**, "Restart the studio" appears at the top: press it,
  and a fresh studio opens in a new window while the page comes back by itself. If the studio's black
  window is closed, the page says so and comes back when you open Clan Mod Studio again.
- **The rest:** each mod's More has its priority, its folder, Save as .zip (to share it) and Remove.
- **Mod packs**, the next page: a set of mods shared and played together as one experience (a story
  with its cats, quests and items, the colours and names that suit it). Make one from your mods; its
  Save as .zip carries every mod in it. **Play only this pack** turns its mods on and the rest off, and
  **Back to my mods** puts yours back. A pack someone sent you is added like any mod, on the Mods page.
- **Settings and repair**, the other page under Your mods: the game's console, allowing mods that run
  code, your save backups, removed mods (a removed or replaced mod is kept in `backups/mods/`, and
  Put it back does that), "Take all mods out of the game", and starting an empty mod of your own.

The pages under **Make mods** are for making your own; each edits a file in a mod folder. **Save to
mod** checks the file the way Apply would and says under the Editing mod bar what would keep it out of
the game; the page asks before you switch mods or close it with unsaved changes.

| Page | What you change | Stored as | Reaches the game through |
|---|---|---|---|
| **Palettes** | eye, coat, pattern and marking colours on a live cat; new pattern and marking colours | `palette.json` | eye atlas patch (eyes); UE4SS script (the rest) |
| **Your cat** | colours only your cat wears (coat, paws, ears, nose, whiskers); which colour slots it wears; its scars | `cats.json` | UE4SS script (colours); your save, on install (slots, scars) |
| **Controls** | which key, mouse button or controller button does each action, second keys, keys in menus, controller presets; says what each change will do before you apply | `controls.json` | the game itself, through a small helper installed with your mods; moving and the camera only with `Play with key remaps.bat` (deprecated); see [Remapping keys](#remapping-keys) |
| | mouse look: sensitivity, invert, smoothing | `mouselook.json` | UE4SS script |
| **Names** | rename, add and remove name prefixes, suffixes and rogue names; the ban list; cameo cats and any shown name; the cats in your save | `names.json` | edited tables and text in the mod pak; cat renames in your save, on install |
| **Items** | herbs, materials and accessories of your own: name, description, icon (the game's, recoloured, or your own picture), what a herb does, an accessory's look (recoloured or your own picture), shape (your own model, OBJ or glTF from Blender), where it sits (moved, turned, sized) and opacity (see-through glass), how a herb or material lies on the ground to be picked up (your own model and picture), the medicine cat's recipe, some to start with | `items.json`, with the pictures and models it names | new rows, textures and meshes in the mod pak; a UE4SS script that puts models on the cats wearing them, and a list of models on the ground for `Game.items.drop`; starting ones in your save |
| **Animations** | animations of your own, made in Blender from a start kit (the cat, or an animal, rigged to the game's own skeleton) and saved as glTF: emotes your cat plays from a key or the mod menu's Emotes page, or anything a script plays on a cat or an animal; loop, speed, claws out | `animations.json`, with the .glb files it names | new animation sequences in the mod pak; a list of them for `Game.anims`, and a UE4SS script that puts the emotes on keys and a menu page |
| **Characters** | cats of your own: name, title, a random or fixed look, colours, eyes, size, where they stand, what they say | `npcs.json` | the [Sandbox mode](https://github.com/HexOffender/wcmods-sandbox) mod, in its sandbox games |
| **Questlines** | quests with those cats, step by step (talk, pick things up, go somewhere), one after another, with rewards | `quests.json` | the Sandbox mode mod |
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
the mod menu's Lua console run Lua in the game while it's open. See [docs/scripting.md](docs/scripting.md);
the example is [game-tweaks](https://github.com/HexOffender/wcmods-examples/tree/main/game-tweaks) in wcmods-examples.

**Stories without code:** Items, Characters and Questlines make a whole story with no code. The
cats and quests come into the game with the [Sandbox mode](https://github.com/HexOffender/wcmods-sandbox)
mod (a mod that saves cats or quests needs it, so turning it on turns that on too); items are real items,
in story games as well. "Use where my cat is standing" fills in a place from the game while it runs (it
goes through the game bridge, so it needs mods that run code allowed).

**Sharing what you make:** every page under Make mods has a **Share** part: the mod's name, author,
version and description, **Save as .zip** for others to add on their Mods page, and **Export** and
**Import** for just that page's file.

Mods can also ship whole replacement files (`files/Wrc/...`), and their own pages and build
steps written with the shared library (see [docs/SDK.md](docs/SDK.md)). UE4SS scripts can draw
on screen (menus, debug text, markers on places in the world) with [`WCModsDraw`](docs/SDK.md#wcmodsdraw)
and find nearby pickups, cats and quest objectives with [`WCModsWorld`](docs/SDK.md#wcmodsworld); the
example is [quest-markers](https://github.com/HexOffender/wcmods-examples/tree/main/quest-markers) in wcmods-examples, a custom quest with on-screen markers.
Mods can run C++ in the game too, as UE4SS C++ mods: `python wcmods.py new my-mod --kind cpp`, then
`python wcmods.py cpp setup` and `cpp build my-mod` build its `cpp/` against the game's UE4SS
([C++ mods](docs/SDK.md#c-mods) lists what that needs). A C++ mod can put a tab of its own in the game's
pause screen, inventory and settings, change the HUD and draw over it, with the game's own controls
([the game's own UI, `Ui.hpp`](docs/SDK.md#wcmodshpp)); Lua scripts get the same through it
([the game's own menus and HUD](docs/scripting.md#the-games-own-menus-and-hud)).

**In game, Insert opens the mod menu** (with UE4SS). It comes with wcmods and goes in with every
install. The side bar groups its pages: Home (an Overview of the keys and what's where, and the
installed mods), the groups the pages from mods go in (Your cat, World, Story, Fight, Cheats, Mods) and
Tools (the log, the menu's own settings, and with code mods allowed the Inspector and the Lua console).
[docs/SDK.md](docs/SDK.md#wcmodsmenu) lists every page.

Everything there changes live. Mouse look and your cat's colours change as you move their sliders,
and Save writes the change back to the mod, so the next install keeps it.
- **Its settings:** Options, on the Settings and repair page, set the key that opens it, the
  controller button that does too (View, to begin with) and its size. A- and A+ in the menu's top bar
  resize it while you play.
- **With a controller:** View opens it, the d-pad moves between its controls and A presses them, and
  View or B closes it. Opened from a controller, the game pauses while it's open.
- **The game's console:** it's under Options on the Settings and repair page too.
- **Your own page:** [docs/SDK.md, `WCModsMenu`](docs/SDK.md#wcmodsmenu) shows how a script adds one.

**The pages about the game are a mod of their own, Menu pages**
([HexOffender/wcmods-menu-pages](https://github.com/HexOffender/wcmods-menu-pages)): At a glance,
your cat's Stats, World, Travel, Nearby, Items, Quests, Fight, Cheats and Game switches, and the line
under the menu's title saying how your cat is doing.
- **Getting it:** Get set up, on the Mods page, has "Add the menu's pages", which downloads its latest
  release and adds it to your mods; "Get the latest" on its card updates it, keeping its settings.
  `python wcmods.py menu-pages` does the same, and its `.zip` can be added like any mod.
- **It's an in-game script,** so like any script it runs only with mods that run code allowed
  (Options, on the Settings and repair page). Without it, or with it off, the menu's Overview says
  what's missing.

**Cheats** are the engine's cheat manager, which the release build leaves off. Menu pages' Cheats
page switches them on and off while you play, and has god mode, fly and ghost (W A S D or the left
stick move the way the camera faces; Space and Left Ctrl, or the triggers, go up and down; ghost goes
through walls), cat size, game speed, teleport to where the
camera looks, and a box for any engine command. With cheats on, the console's cheat commands work
too (`god`, `slomo 0.5`, `teleport`). The console's own `fly`, `ghost` and `changesize` don't stick:
the game puts its cat back to its own movement each frame and resets its mesh's scale, so the page
does those itself (it scales the whole cat, and moves it while flying). Its "Start with cheats on"
switch, or `python wcmods.py cheats on`, makes them start on from the next time the game starts, and
`python wcmods.py console on|off` switches the game's console (`~` or F10).
Some cheats can break a quest or a save, so back up first if you're unsure (Settings and repair).

The original game files are never modified (uninstall takes everything out again), and save edits are
written into your save only after a backup.

## Remapping keys

1. Change keys on the **Controls** page in Clan Mod Studio (or in a mod's `controls.json`), Save to mod,
   Apply to game, then start the game any way you like.
2. The new key does the action; the old key stops doing it but keeps its other jobs, and the game's prompts
   and its Controls tab show the new key.
3. Moving the cat and the camera can't be changed this way, because the game reads those keys itself: for
   the keyboard, start the game with `Play with key remaps.bat`; for the sticks, use Steam's controller
   settings.
4. If a key already does something else, the page says what it will stop doing before you save, and so does
   Apply; the mod menu's key and button (Insert and View unless you changed them), mouse look's key (F6) and
   F11 are taken, and the page's "Which keys are free?" lists the rest.
5. Controller buttons, the side mouse buttons and the wheel haven't been tried in the game yet.

| What you change | After Apply | Note |
|---|---|---|
| An action (Interact, Pounce, Run, Crouch, Scent tracking, Drop, Talk to a friend, Place a den decoration, Return to camp, Reset the camera, Pause menu, Inventory, Quest log, Map, Meow) on a key, mouse button or controller button | works in the game | the old key keeps its other jobs; Inventory, Quest log, Map and Meow have no controller button |
| A second key for an action | works in the game while you explore | it does what the game's key does there |
| A second key for Confirm, Back or the tabs in menus | works in the game | letters still type on the name screen |
| Moving and the camera, on the keyboard | only with `Play with key remaps.bat` | deprecated, keyboard and mouse only |
| The sticks | no | Steam's controller settings |
| Mouse look | works in the game | its own card on the Controls page; needs the script loader |
| Anything, without the script loader | keyboard and mouse only, with `Play with key remaps.bat` | Get set up installs the loader |

How it works inside the game, the old key remapper and its command line, and what hasn't been checked yet:
[docs/remapping.md](docs/remapping.md). The file itself: [formats.md, controls.json](docs/formats.md#controlsjson).

## Command line

Everything the studio does is also available as a command (`python wcmods.py --help` lists them all,
in groups):

```
python wcmods.py status      # game, save, UE4SS, and your mods
python wcmods.py selftest    # checks every file format against your install (writes nothing)
python wcmods.py install     # builds the enabled mods and installs them (game closed)
python wcmods.py play        # starts the game with the old key remapper (deprecated; see Remapping keys)
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
`texture <item|accessory|/Game/...>` (one of the game's textures as a PNG), `model <accessory>` (an
accessory and the cat as OBJ files, to make a model of your own on), `animation <cat|mouse|...>` (the cat or
an animal rigged to the game's skeleton as a .glb to animate in Blender; `--check FILE` says what a file holds),
`build`, `backup`, `restore [name|latest]`, `menu-pages [--zip file]` (add or update the Menu pages
mod), `cheats [on|off]` (whether Menu pages' cheats start on), `console [on|off]` (the game's `~`
console). With code mods allowed and the game running:
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

## Making mods

A mod is a folder under `mods/` in your files' folder (`%LOCALAPPDATA%\WCMods\mods`) with a `mod.json`
and some of these files, which the pages under Make mods write for you:

| File | What it changes |
|---|---|
| `palette.json` | eye, coat, pattern and marking colours; new pattern and marking slots |
| `cats.json` | colours only your cat wears, which slots it wears, its scars |
| `controls.json`, `mouselook.json` | key and button remaps; mouse look |
| `data.json` | the game's tables: XP, costs, speeds, tuning values |
| `items.json` | new herbs, materials and accessory looks, with pictures and models of the mod's own |
| `animations.json` | animations of the mod's own for cats and animals: emotes, and ones scripts play |
| `npcs.json`, `quests.json` | cats of the mod's own, and questlines with them (for Sandbox mode) |
| `names.json` | cat name parts, rogue names, the ban list, the cats in your save |
| `save.json` | edits to your save |

[docs/formats.md](docs/formats.md) describes each one with examples; `python wcmods.py new <name>
--kind <palette|controls|data|items|names|save|files|script|cpp>` starts a mod from a template. Mods
can also replace whole game files (`files/Wrc/...`), ship cooked content (`paks/`), run Lua in the
game ([docs/scripting.md](docs/scripting.md)) and bring build steps, studio pages and C++
([docs/SDK.md](docs/SDK.md)). [docs/README.md](docs/README.md) says what to read first.

**Sharing a mod:** Save as .zip (a mod's More, in the studio) or `wcmods pack <mod>` writes a .zip
with the mod's folder in it, and that's what the studio's Add a mod takes. A .zip can hold several
mod folders, or one mod's files at the top (it's then named after the .zip). Adding a mod never
runs anything in it. A mod pack (`"pack": true` in its mod.json, its mods in `"requires"`) packs
every mod in it into its .zip. Mods with code (a `section.py`, `scripts/`, a `studio/` page) stay out of the
game until "Allow mods that run code" is on (Options on the Settings and repair page, or
`"allow_code_mods": true` in `wcmods.json`), which is only for mods from people you trust.

## Appearance vs gameplay

The game rolls traits (Ambitious, Brave, Wise, Energetic, Curious, Patient) from body, ear and
face shape. Stats come from your Clan. Your save stores which *slot* each option uses, not the
colour.

- **Palettes are appearance-only.** They redraw a slot; your cat keeps the same slot, so traits
  and stats don't change. Suggested names follow the slot.
- **Game data and save edits are gameplay changes.** That's their purpose. The tool warns when
  an edit touches the online den-visit tables (`OnlineGifts.csv`, `VisitRewards.csv`), the
  trait-driving body, ear or face odds, or replacement files not known to be appearance-only.

## What's checked

`python wcmods.py selftest` checks every file format against your install, and `python wcmods.py agent
test` runs the in-game tests. [docs/verified.md](docs/verified.md) lists what has been confirmed in
game, by date, and what hasn't been yet.

## For contributors

[CONTRIBUTING.md](CONTRIBUTING.md) says how to run the checks and where things go, and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) is the map of the code: the sections a build is made of,
the file formats under `wcmods/formats/`, the exe analysis under `wcmods/exe/`, the in-game Lua under
`wcmods/lua/`, and Clan Mod Studio's pages. The original game files are never modified: everything an
install writes goes into `<game>\Wrc\Content\Paks\~mods\zzz_WCMods_*`,
`<game>\Wrc\Binaries\Win64\ue4ss\Mods\WCMods*` and `ue4ss\Mods\shared\WCMods*`, and uninstall
removes those. [docs/reverse-engineering.md](docs/reverse-engineering.md) collects what we've worked
out about the game's insides, with the tools in `tools/re/`, and [docs/mechanics/](docs/mechanics/README.md)
explains the game's rules with the numbers to change for each.
