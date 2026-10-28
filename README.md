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
   (UE4SS) with one click. If you've never played, start the game once first so it makes a save.
   - **"Let mods run their own scripts":** press **Allow**. The mods that come with Clan Mod Studio, and
     many others, are small programs that run inside the game; only allow it for mods from people you
     trust (the warning names the ones you have). **Not now** leaves it for later (Options, on the
     Settings and repair page).
   - **"Get the mods that go with Clan Mod Studio":** press **Add all four**. Menu pages (the mod menu's
     pages about your cat and the game), Sandbox mode (where the cats and questlines you make turn up),
     Creator palettes (your new colours and coat presets in the cat maker) and the Emote wheel come from
     their GitHub pages; one with no release yet says so on its row. Once everything is done, the card
     folds to one line.
4. **Add a mod:** drop the mod's .zip on the page, or onto `Clan Mod Studio` itself, and press **Add
   to my mods**. To try some, [wcmods-examples](https://github.com/HexOffender/wcmods-examples) has palettes, mouse look and more:
   download it (**Code**, then **Download ZIP**) and drop that .zip on the page. Most of them were made
   for an older version of the game: the Mods page checks the ones that are only data (palettes, names,
   tweaks) on yours by itself and puts in the ones that build; a script waits for its maker, or **Use it
   anyway…**.
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
  offers it with the other mods that go with Clan Mod Studio; until it's in, the menu has the Overview,
  your mods' pages and the Tools.

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
is deprecated (see [Remapping keys](#remapping-keys)). Remaps work inside the game however you start
it; the old remapper is only for remapping movement or the camera. It stops by itself when the game
closes.

**Clan Mod Studio** puts your mods in the game. Its **Mods** page is where you start:
- **Add a mod:** drop a downloaded mod's .zip on the page. It shows what's in it (what the mod
  changes, whether it runs code, what else it needs, by name) before you add it, and whether each one goes
  in switched on, as it ships unless you change it. A mod whose requirement you don't have is added
  switched off, and says what it needs; for one of the mods that go with Clan Mod Studio, the preview has
  its Add button. A .zip with `mod.json` at its top and no `"id"` is named after its file name with a
  version at the end dropped ("Cool Mod v1.3.zip" goes in as cool-mod), so the next version replaces it
  rather than going in beside it; one an older Clan Mod Studio named with the version in it is found by
  its name and replaced. A mod made for a newer Clan Mod Studio (its mod.json's `"wcmods"`) is left out,
  and says to update.
- **The mods that go with Clan Mod Studio:** their card lists Menu pages, Sandbox mode, Creator palettes
  and the Emote wheel, each with a sentence, a state (Not added, In, Off, Needs scripts allowed, Newer one
  out, Needs a newer Clan Mod Studio, No release yet) and one button: Add, Switch on or Get the latest.
  Check for newer versions asks GitHub (nothing else does). `python wcmods.py addons` lists them, and
  `addons add <id>` adds one.
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
  Save as .zip carries every mod in it (a pack made from My mods carries it as "<pack>: its own content",
  so whoever adds it keeps their own My mods). **Play only this pack** turns its mods on and the rest off,
  but your own tools (Menu pages, Creator palettes, the Emote wheel, and any mod whose mod.json says
  `"tool": true`) and the mods its mods work with stay as they were; **Back to my mods** puts yours back,
  and removing the pack while it plays does the same. A pack's card says what would keep one of its mods out
  of the game (a story pack's cats need Sandbox mode, which runs code, so mods that run code allowed). A
  pack someone sent you is added like any mod, on the Mods page: a mod you already have is ticked only when
  the pack's copy is different and newer, and a pack never puts in an older copy of one of the mods that go
  with Clan Mod Studio than yours.
- **Settings and repair**, the other page under Your mods: the game's console, allowing mods that run
  code, your save backups, removed mods (a removed or replaced mod is kept in `backups/mods/`, and
  Put it back does that), "Take all mods out of the game", and starting an empty mod of your own from a
  name. Backups are listed in words ("Today 15:30, backed up by you"); restoring one keeps the save you had
  as another backup, and the next Apply puts your mods' save changes back (turn those mods off first to keep
  them out). Take all mods out leaves your mods on here, so Play puts them back: to play without mods, start
  the game from Steam. When the game crashed since the last Apply, the page says so at the top of Backups and
  repair (and the Mods page once), with the C++ mod it was in when one was on its stack, Copy the report and
  Turn it off.

The pages under **Make mods** are for making your own; each edits a file in a mod folder. **Save to
mod** checks the file the way Apply would and says under the Editing mod bar what would keep it out of
the game; the page asks before you switch mods or close it with unsaved changes.

| Page | What you change | Stored as | Reaches the game through |
|---|---|---|---|
| **Palettes** | eye, coat, pattern and marking colours on a live cat; new pattern and marking colours | `palette.json` | eye atlas patch (eyes); UE4SS script (the rest) |
| **Your cat** | colours only your cat wears (coat, paws, ears, nose, whiskers); which colour slots it wears; its scars | `cats.json` | UE4SS script (colours); your save, on install (slots, scars) |
| **Controls** | keyboard, mouse and controller bindings; press-to-bind, conflicts, controller presets | `controls.json` | the game itself (`WCModsRemap`); movement and the camera only with the old key remapper (deprecated); see [Remapping keys](#remapping-keys) |
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
**Import** for just that page's file. The .zip is named after the mod's folder and version
(`moonlit-cats-1.2.zip`); the mod goes in under its folder name on the other side, whatever the file is
called, so a newer version replaces the older one there.

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
- **Getting it:** it's one of the mods that go with Clan Mod Studio: Add all four in Get set up, or Add
  on its row of their card, downloads its latest release and adds it to your mods; Get the latest updates
  it, keeping its settings. `python wcmods.py addons add menu-pages` (or `menu-pages`) does the same, and
  its `.zip` can be added like any mod.
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

The game doesn't take remaps from mods. It keeps a copy of your bindings in the save
(`Shared/InputKeyboard`, `Shared/InputGamepad`) but ignores edits to it, its own rebinding
screen (`WBP_GuiPopupControlConfig`) is hidden and not wired up on PC, and the bindings themselves
live in native code no script can reach ([docs/reverse-engineering.md, Input](docs/reverse-engineering.md#input)
has what was found). So wcmods remaps while the game runs. Set your keys on the Controls page (or in
`controls.json`), save them to a mod, and install mods (game closed). Then:

| What you remap | Done by |
|---|---|
| The game's actions that are buttons: Interact, Pounce, Run, Crouch, Scent tracking, Drop, Talk to friend, Place den decoration, Return to camp, Reset camera, Pause, and the Controls screen's Inventory (I), Quest (K), Map (M) and Meow (L), onto keyboard keys, mouse buttons or controller buttons | **the game**, through wcmods' `WCModsRemap` script: start the game any way you like, from Steam too |
| Any other of the game's commands, everywhere: the menus' Confirm, Back, Skip, tab buttons and the rest (`"keyboard": {"Button_Skip": "G"}`) | **the game** |
| A key that stands for another while you play (`"keys": {"H": "E"}`) | **the game** |
| A key that stands for another in menus, the "In menus" list (`"menus"`): I and K for Up and Down, F for Enter | **the game** (mouse buttons there: the old key remapper) |
| Movement and the camera (Move back, Move left, Camera down, Camera left, and keys standing for W, D, Up or Right) | only **the old key remapper** outside the game (deprecated, below) |
| The controller's sticks | **Steam Input** (in Steam, right-click the game, then Properties, Controller) |
| Anything, without UE4SS | **the old key remapper**, for keyboard and mouse |

**Inside the game.** The `WCModsRemap` script is installed with your mods whenever they remap anything it
can do, with "Allow mods that run code" on or off (it's wcmods' own script, like mouse look's). Every key
the game hears becomes one or more of its commands (Interact, Pounce, and in menus Up, Confirm, Back...),
and the script works on those:
- **Moving an action or command** (`keyboard`, `gamepad`): the new key does it, in play and in the game's
  menus, and the old key stops doing it but keeps its other jobs. With Interact on F, E still shows info on
  the map; with Pounce moved off Space, Space still confirms dialogue. A key that takes an action stops doing
  its own (with Interact on Q, Q no longer tracks scents; the build says so).
- **A key standing for another** while you play (`keys`) or in menus (`menus`): it does all of that key's
  jobs there, and none of its own. Menus are every screen but the HUD: the title and cat maker, the
  pause menu and its pages, the inventory, the map, photo mode, a fight's menu, and talking to a cat.
  Letters still type on the name screen, and do the other key's job there too (the build says so).
  A few screens read some keys directly, like movement: the map's zoom and move (arrows, WASD), photo
  mode's camera (Shift+WASD, Z/C) and turning the cat in the cat maker (Q/E). A menu pair standing for
  an arrow key or WASD therefore also goes to the old key remapper, which can do those (the build says so).

The game's pictures of keys follow too: prompts such as Travel and Talk, the menus' footers (Back,
Confirm) and the pause screen's Controls tab show the new key, from the game's own pictures. A command
that didn't move keeps the game's picture (with Escape standing for Backspace in menus, the footers' Back
shows Escape while Confirm keeps Enter).
The keyboard's pictures follow keyboard moves and a controller's follow controller moves. A key the game
has no picture for (the middle mouse button, the wheel) leaves the game's picture as it was. Movement and
the camera, which only the old key remapper can move, keep theirs. Seen working in game: Interact on F, Run on G,
Scent tracking on the middle mouse button, Map on N (in the map screen too), H as a second Interact, the
pause menu moved with I and K and confirmed with U, O closing menus, the next tab on PageDown instead of
2, and a fight's menu and moves picked with I, K and U; the old keys did nothing. The Travel and Talk
prompts and the Controls tab showed F for Interact, and the pause screen's Back showed Escape for a
menu pair. Controller buttons and the wheel are done the same way but haven't been tried yet. Scripts that listen for Interact themselves (`Game.npcs`, for a mod's own cats) follow it to its
new key.

**The old key remapper outside the game (deprecated).** Remapping is done inside the game now, and the
old key remapper is kept only for what a script can't reach: what the game reads as axes every frame
(movement and the camera, the map's zoom and move) and mouse buttons in the "In menus" list (in menus, a
click goes to the button under the cursor, not to the game's keys). The studio's Play doesn't start it
any more; when your mods have remaps only it can do, the build and Play say so. While you play, the keys in your mods' `controls.json` stand in for the game's. "Play"
means the game window is in front and you're exploring, not in a menu. A small UE4SS script
(`WCModsPlayState`, installed with your mods when the remapper has work to do) tells the remapper
which it is. Windows can't, because the game draws its own cursor. Without that script, remaps
apply whenever the game is in front. The remapper holds back the key you press and sends the
game's key in its place, and it stops when the game closes. Menus, the name screen and other
programs keep your normal keys, except for the menu remaps you set (the Controls page's "In menus"
list). A key whose action moved stops doing it, unless another action still uses it. Mouse buttons
and the wheel can stand in for keys. The pause menu hasn't been checked yet.

To use it, start the game with `Play with key remaps.bat` or `python wcmods.py play` instead of from
Steam or the studio's Play. Its "play" means no game screen is showing: exploring, photo mode, or
talking to a cat. When everything you remap is done inside the game, `play` just starts the game:

```
python wcmods.py play              # start the game through Steam and remap until it closes
python wcmods.py remap             # the same, when the game is already running (or about to be)
python wcmods.py play --dry-run    # report which remaps would happen, without changing any keys
python wcmods.py play --in-menus   # remap in menus too
python wcmods.py play --debug      # log the window in front, the play state, and remapped key presses
```

Microsoft PowerToys Keyboard Manager can stand in for the key remapper, if you'd rather not run it:
choose *Remap a key*, map your new key to the game's key (for example T to W for forward), and set
the target app to `Wrc-Win64-ShippingDRM.exe` so the remap only applies in the game. Don't remap the
same keys with it and wcmods at once.

The key remapper runs as a normal program using Windows' low-level keyboard hook. Ctrl+C stops it,
and anything it was holding down is let go. Details:

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
`build`, `backup`, `restore [name|latest]`, `addons` (the mods that go with Clan Mod Studio, and GitHub's
latest of each) and `addons add <id> [--zip file]` (add or update one), `menu-pages [--zip file]` (the
same for the Menu pages mod), `cheats [on|off]` (whether Menu pages' cheats start on), `console [on|off]` (the game's `~`
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
