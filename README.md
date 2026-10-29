# Clan Mod Studio for *Warrior Cats: Clans of the Forest*

Clan Mod Studio makes mods for the Steam game *Warrior Cats: Clans of the Forest*, with no code. Recolour
the cats, rename them, make herbs and accessories of your own, write quests for cats you made, or change
how the game plays. It also adds mods other people made, and shares yours with them.

It runs on Windows and opens in your web browser. It never changes the game's own files: everything your
mods put in the game's folder comes out again with one button. The script loader, a free add-on it
installs, stays until you remove it.

This page has four parts:
- [Make your own mods](#start-here): start here if you've never modded anything.
- [Play with mods](#play-with-mods) other people made.
- [Write mods with code](#write-mods-with-code), in Lua, Python or C++.
- [Work on Clan Mod Studio](#work-on-clan-mod-studio) itself.

## Start here

1. **Download it.** On this page on GitHub, press the green **Code** button, then **Download ZIP**.
   Unzip it anywhere, such as your Documents.
2. **Double-click `Clan Mod Studio`** in that folder. A black window opens, then the studio opens in
   your web browser. The black window is the studio itself: keep it open while you use it, and close it
   to stop the studio. Closed by mistake? The page says so, and carries on when you double-click
   `Clan Mod Studio` again, with anything you hadn't saved still on it.
   - The first time, if your computer doesn't have Python (the free program Clan Mod Studio runs on),
     the black window says so and offers to install it. Say yes. If it then says to, close it and
     double-click `Clan Mod Studio` again.
3. **Follow Get set up.** It's the card at the top of the **Mods** page, and it stays until everything
   is done. It finds the game, keeps a safety copy of your save, and installs the
   [script loader](docs/guide/README.md#script-loader) most mods need when you press **Install it**.
   If you've never played the game, it asks you to start it once first, so there's a save.
   - **Let mods run their own scripts:** press **Allow**, read the warning, then press **Allow mods
     that run code**. The mods that go with Clan Mod Studio are small programs that run inside the
     game. Only allow [mods that run code](docs/guide/README.md#code-mods) from people you trust: the
     warning names the ones you have. **Not now** leaves it for later (**Options**, on the **Settings
     and repair** page).
   - **Get the mods that go with Clan Mod Studio:** press **Add all four**. They bring what you make
     into the game: [Menu pages](docs/guide/README.md#menu-pages) (the mod menu's pages about your cat
     and the game), [Sandbox mode](docs/guide/README.md#sandbox-mode) (where the cats and questlines you
     make turn up), Creator palettes (your new colours and coat presets in the cat maker) and the Emote
     wheel (a wheel of your emotes and the game's poses).
     [Mods that go with Clan Mod Studio](docs/guide/companion-mods.md) says more. One that has no release
     yet says **No release yet** on its row: nothing is wrong on your side.

   When everything is done, the card folds to one line.
4. **Press Help** (top right) whenever you wonder what something does. Every page also has **How this
   works** under its title, which opens that page's guide.

To start it from your desktop, right-click `Clan Mod Studio` and choose *Send to > Desktop (create
shortcut)*. Double-clicking it while it's open brings back the one that's open.

## Make your first mod

Five minutes: give your cat a pink nose. It needs the script loader from **Get set up**.

1. Open **Your cat**, in the side bar under Make mods.
2. Under **Colours of its own**, tick **Nose** and pick a bright pink.
3. Press **Save to mod**. The first time, the studio makes a mod called **My mods** for you and switches
   it on.
4. Close the game if it's open, then press **Play** (top right; it reads **Apply and play** while changes
   wait). It puts your mods in, then starts the game.
5. In the forest your cat has a pink nose, and on the main menu and in its picture too. No other cat
   has.

That's how every page works: change something, **Save to mod**, **Play**.
[How Clan Mod Studio works](docs/guide/studio.md) explains the Editing mod bar, **Save to mod**, **Apply
to game**, the [build log](docs/guide/README.md#build-log), what undo means here, and where your files
are.

## Clan Mod Studio

**Help**, at the top, opens [the guide](docs/guide/README.md), and each page's **How this works** opens
its own part of it. The side bar has three groups of pages. **Your mods** is for the mods you have:
- [The Mods page](docs/guide/mods.md): **Get set up**, adding mods, switching them on and off, and telling
  whether they reached the game.
- [Mods that go with Clan Mod Studio](docs/guide/companion-mods.md) (a card on the Mods page): Menu
  pages, Sandbox mode, Creator palettes and the Emote wheel, and how to get them.
- [Mod packs](docs/guide/packs.md): mods shared and played together as one experience.
- [Settings and repair](docs/guide/settings.md): the options, your save backups, mods you removed, and
  taking every mod out of the game.

**Make mods** is for making your own. Each page saves one file into a mod; its name below opens its
guide. How a change reaches the game:
- **the mod pak**: a file of game data that Apply adds beside the game's own files, and that wins over
  them;
- **the script loader**: small helpers that run inside the game while you play;
- **your save**: Apply writes the change into your save, once, after a backup.

| Page | What you change | Saved as | How it reaches the game |
|---|---|---|---|
| [**Palettes**](docs/guide/palettes.md) | the game's eye, coat, pattern and marking colours, which every cat picks from by number (its [slot](docs/guide/README.md#slot)); new coat, pattern and marking colours | `palette.json` | the mod pak (eye colours); the script loader (the rest) |
| [**Your cat**](docs/guide/cat.md) | your cat (in the game you're playing, or in one game you choose), or any cat in your save: colours of its own (coat, paw pads, inner ears, nose, whiskers); which of the game's colours it wears; its shape and size; its scars | `cats.json` | the script loader (colours of its own); your save (the game's colours, shape, size, scars) |
| [**Controls**](docs/guide/controls.md) | which key, mouse button or controller button does each action; second keys; keys in menus; controller presets. The page says what each change will do before you apply | `controls.json` | a small helper that comes with your mods, through the script loader; moving and the camera only with `Play with key remaps.bat`, the old key remapper, which is on its way out (deprecated): see [Remapping keys](#remapping-keys) |
| | mouse look: sensitivity, invert, smoothing, tilt limits and its on and off key | `mouselook.json` | the script loader |
| [**Names**](docs/guide/names.md) | the cats in your save (a name of your own, or one that grows with rank); the parts of clan names and rogue names (renamed, added, removed); the ban list; cameo cats and any other name the game shows; areas, quest titles and item names | `names.json` | the mod pak (the game's names and text); your save (renamed cats) |
| [**Items**](docs/guide/items.md) | herbs, materials and accessories of your own: name, description, icon, what a herb does, an accessory's look, a model of your own from Blender, how it lies on the ground, the medicine cat's recipe, some to start with | `items.json`, with the pictures and models it names | the mod pak (the items, pictures and models); the script loader (models on cats and on the ground, see-through accessories); your save (**Starting with some**) |
| [**Animations**](docs/guide/animations.md) | the game's own animations as emotes, or in another's place, with no Blender; your own, made in Blender from a start kit: emotes on a key, or animations for scripts and stories | `animations.json`, with the .glb files it names | the mod pak (the animations); the script loader (emotes on keys, and the mod menu's Emotes page) |
| [**Characters**](docs/guide/characters.md) | cats of your own: name, title, a new look each time or the same look every time, colours, eyes, size, where they stand, what they say | `npcs.json` | Sandbox mode, in its sandbox games |
| [**Questlines**](docs/guide/questlines.md) | quests with those cats, step by step (talk, pick things up, go somewhere), one after another, with rewards | `quests.json` | Sandbox mode |
| [**Game data**](docs/guide/data.md) | the numbers the game plays by: **Quick changes** in words (running speed, XP from fights, what prey is worth, cat sizes, scars...), **Find a number**, and **All tables**, cell by cell | `data.json` | the mod pak |
| [**Save**](docs/guide/save.md) | your own save, in the game you choose (the one you played last at first): your cat's level and experience, the fresh-kill pile, what your cat carries, and anything else in it; each change made once, after a backup, and each one can be put back | nothing, with **Change my save now**, which changes your save at once; or `save.json`, kept as a mod to share | your save |
| [**Tweaks**](docs/guide/tweaks.md) | small changes while you play: stamina kept full, a heal key, the clock held, the fresh-kill pile kept up | `tweaks.json` | the script loader (a helper that comes with Clan Mod Studio, so mods that run code needn't be allowed), with a Tweaks page in the mod menu |

**Advanced** shows once mods that run code are allowed. Its page,
[Try Lua in the game](docs/guide/console.md), is for people who write scripts.

**Save to mod** reads the file the way Apply first does. A line under the Editing mod bar says what in it
would keep it out of the game, and what Apply would leave out. What only shows once your mods are put
together (a table's rows, a model or a picture, two mods changing the same thing) is found when you
apply. The page asks before you switch mods, import a file over your changes, or close it with changes
unsaved. When you come back to the studio's window, a page with nothing unsaved reads its file again if
something else changed it (the game's mod menu saves some files), and says so.

### Stories with cats of your own

**Items**, **Characters** and **Questlines** make a whole story with no code. Your cats and quests come
into the game through the Sandbox mode mod ([its page](https://github.com/HexOffender/wcmods-sandbox)):
- **Getting it:** **Add all four** in **Get set up**, or **Add Sandbox mode** in the strip at the top of the
  Characters and Questlines pages, or download `sandbox-<version>.zip` from its releases and drop it on
  the Mods page. It runs a script, so mods that run code must be allowed.
- **In the game:** *Sandbox Mode* on the game's main menu starts a cat with no story, and your cats are
  there. Walk up to one and use the game's *Talk* prompt (Interact: E, or A on a controller).
- **A mod with cats or quests works with Sandbox mode**, rather than needing it: switching the mod on
  switches Sandbox mode on when you have it, and without it the mod still goes in, its cats waiting.
  Items are real items, in story games too.
- **Same look every time** needs Sandbox mode 0.5 or newer, and **Where they walk** (a cat walking a
  route of points, with a wait at each) needs 0.6. With an older one those cats get a new look each time,
  or stand still, and the Characters page says so.
- **Use where my cat is standing** fills in a place from the running game. It talks to the game
  through the studio's connection to it, so it needs mods that run code allowed.

The strip at the top of both pages says what Sandbox mode can show and what to press, and their guides
([Characters](docs/guide/characters.md), [Questlines](docs/guide/questlines.md)) walk through a first cat
and a first quest.

### Sharing what you make

Every page under Make mods but Save has a **Share** fold under its Editing mod bar: the mod's **Name**,
**Author**, **Version** and **Description**, **Save as .zip** for others to add on their Mods page, and
**Export** and **Import** for just that page's file (**Export palette.json**, say). The .zip is named
after the mod's folder and version (`moonlit-cats-1.2.zip`). On the other side the mod goes in under its
folder name, whatever the file is called, so a newer version replaces the older one.
- **Save page changes** are shared as a whole mod: **Keep it as a mod to share** on the Save page, then
  **Save as .zip** under that mod's **More** on the Mods page.
- **Whoever gets it** drops the .zip on their Mods page. A mod that runs code needs them to allow mods
  that run code, and characters and questlines need Sandbox mode on their side too.

### Not checked in the game yet

These are built and tested without the game, but nobody has watched them in it yet
([docs/verified.md](docs/verified.md) has the whole list, by date):
- **Palettes:** coat colours on screen, and a cat wearing a new pattern or marking colour.
- **Game data:** changes other than the running speed (a faster run was seen in play; the other tables
  load the same way, but no other change has been watched).
- **Save:** a save changed with **Change my save now**, then loaded; **Put it back**.
- **Tweaks:** skipping the story's scenes, which is refused for now. The others, and the mod menu's
  Tweaks page with its Save, have run in the game.
- **Animations:** the run in the trot's place, and **Try it on my cat**; animations on the clans' cats,
  and on animals other than mice and birds. The game's own animations as emotes, and in another's place,
  have been seen working.
- **Names:** new cats getting added or removed name parts, and the ban list; renamed areas, quests and
  items on the game's own screens.
- **Items:** accessory models on other cats; models dropped on the ground by a questline's reward.
- **Controls:** controller buttons, the side mouse buttons and the wheel.
- **Questlines:** a quest starting over by itself after you change its steps (with Sandbox mode 0.5),
  and **Start every questline over**.
- **Characters:** a cat walking its route (**Where they walk**): a timed wait, an event, a release, the
  walk back and a skipped point have run in the game, but not a cat stopping while you talk to it,
  carrying on after its area loads again, or waiting on a quest. Since 0.5.0 every Character is the
  game's walking cat: its label, *Talk* prompt and turning to you haven't been watched on it yet.
- **Mods that go with Clan Mod Studio:** **Add all four** on a fresh install.
- **Try Lua in the game:** the page itself with the game running (what it asks the game has been tried
  against it).
- **The mod menu:** parts of some pages
  ([docs/mod-menu.md](docs/mod-menu.md#not-checked-in-the-game-yet)).

## Play with mods

First set up as in [Start here](#start-here). Then, on the **Mods** page
([its guide](docs/guide/mods.md)):

- **Add a mod:** drop its .zip on **Drop a mod's .zip here** (or onto `Clan Mod Studio` itself), then
  press **Add to my mods**. Before anything is added, the preview says what the mod changes, whether it
  runs code, and what else it needs. A .zip with several mods lets you tick the ones you want, and
  whether each goes in switched on (as it ships, unless you change it), then **Add these**. Adding a mod
  never runs anything in it.
  - A mod that needs one you don't have goes in switched off and says what it needs. When that's one of
    the mods that go with Clan Mod Studio, the preview has its **Add** button (**Add Sandbox mode**, say).
  - A mod made for a newer Clan Mod Studio is left out, and says to update.
- **Mods to try:** Clan Mod Studio comes with no mods of its own.
  [wcmods-examples](https://github.com/HexOffender/wcmods-examples) has themed palettes, eye and coat
  colours, mouse look, controls, game tweaks and more. Download it (**Code**, then **Download ZIP**) and
  drop that .zip on the page. Some were made for an older [game build](docs/guide/README.md#game-build),
  the version of the game before an update: the Mods page checks the ones that are only data on your
  version by itself, and the ones that build go in with the next **Play**. One with a script waits for
  its maker to update it, or **Use it anyway…**.
- **Switch mods on and off** on their cards under **Your mods**. A mod that needs another switches that
  one on too, and switching off a mod that others need asks first. A mod's **More** has its
  **Priority** (when two mods change the same thing, the higher number wins), **Open its folder**,
  **Save as .zip** and **Remove**.
- **Play** (top right) puts what changed in the game, then starts it. **Apply to game** does only the
  first part. Both need the game closed. Until then, **Not in the game yet**, under **Get set up**, lists
  what's waiting. While they work, the build log at the bottom right shows what happens and ends with a
  sentence: which mods went in, or what kept one out. After **Play** it closes by itself unless there's
  a warning. **Last apply** opens the last one again. If some mods can't be made ready, nothing goes in
  until you fix them or switch them off, or press **Apply the rest anyway**.
- **Mod packs** are mods shared and played together: a story with its cats, quests and items, and the
  colours and names that suit it. A pack someone sent you is added like any mod. On the **Mod packs**
  page, **Play only this pack** turns its mods on and the rest off. Your own tools (Menu pages, Creator
  palettes, the Emote wheel, and any mod made as a tool) and the mods its mods work with stay as they
  were. **Back to my mods** puts yours back, and so does removing the pack while it plays.
  [Mod packs](docs/guide/packs.md) has the rest.
  - A pack's card says what would keep one of its mods out of the game: a story pack's cats need Sandbox
    mode, which runs code, so mods that run code must be allowed.
  - A pack's **Save as .zip** carries every mod in it. One made from My mods carries it as "<pack>: its
    own content", so whoever adds it keeps their own My mods.
  - When a pack holds a mod you have, yours is replaced only if that mod's box is ticked. It's ticked for
    you when the pack's copy is different (its files' contents, not only their names and sizes) and
    newer. An older copy than yours of one of the mods that go with Clan Mod Studio is never ticked, in a
    pack or in a .zip of its own.

### The mod menu in the game

With the script loader in, press Insert in the game for the [mod menu](docs/guide/README.md#mod-menu)
(View on a controller). Its Overview page lists the keys and what's where, and Installed mods lists
what went in. Its pages about your cat, the world, quests, fights and cheats come with the Menu pages
mod, which **Add all four** adds; Menu pages runs code, so it needs mods that run code allowed. The
menu's key, controller button and size are under **Options**, on Settings and repair.
[docs/mod-menu.md](docs/mod-menu.md) says the rest, cheats included.

### Remapping keys

Change keys on the **Controls** page ([its guide](docs/guide/controls.md)), **Save to mod**, then
**Play** or **Apply to game**. From then on the new keys work however you start the game, from Steam too.
- The new key does the action. The old key stops doing it but keeps its other jobs. The game's prompts
  and its Controls tab show the new key, and the mod menu's Overview lists it.
- If a key already does something, the page says what it will stop doing before you save, and so does
  Apply. The mod menu's key and button (Insert and View, unless you changed them), mouse look's key (F6,
  while mouse look is on) and F11 are taken. **Which keys are free?** lists every key that already does
  something; any key it doesn't list is free.
- Moving the cat and the camera can't be changed this way, because the game reads those keys itself.
  For the keyboard, start the game with `Play with key remaps.bat`, the old key remapper, which is on its
  way out (deprecated). It stops by itself when the game closes. For the sticks, use Steam's controller
  settings.
- A second key for an action works while you explore: it does what the game's key does there. A second
  key for Confirm, Back or the tabs in menus gives up its own job in menus, and letters still type on the
  name screen.
- Inventory, Quest log, Map and Meow have no controller button in the game.
- Key changes need the script loader. Without it, only `Play with key remaps.bat` does the keyboard's
  actions, second keys and keys in menus. Mouse look has its own card on the Controls page.
- Not tried in the game yet: controller buttons, the side mouse buttons and the wheel.

[docs/remapping.md](docs/remapping.md) says how it works inside the game and what the old key remapper
does; [formats.md, controls.json](docs/formats.md#controlsjson) is the file.

### If a cat shows as Cat 1

Or as `<MISSING STRING TABLE ENTRY>`: its name is text only a mod gives, and that mod is off, or the game
isn't reading your mods. Turn the mod back on and apply. Or, on the **Names** page, press **Give it a
game name** on the cat's row, **Save to mod**, and apply. Or put back a save backup from before
(Settings and repair). The [Names guide](docs/guide/names.md) has more.

### Backups, crashes and taking mods out

All on the **Settings and repair** page ([its guide](docs/guide/settings.md)):
- **Save backups**, listed by when and why. **Back up now** makes one; **Restore** (press it twice) puts
  one back, and keeps the save you had as another backup. The next Apply makes your mods' save changes
  again where the restored save hasn't got them: switch those mods off first to keep them out.
- **Removed and replaced mods** are kept (in `backups\mods` in your files' folder), and **Put it back**
  brings one back.
- **Take all mods out of the game** takes out everything your mods put in the game; the script loader
  stays. Your mods stay switched on here, so **Play** puts them back: to play without mods, start the
  game from Steam. What an apply wrote into your save stays there; a save backup puts the save back.
- **Check my mods** builds your mods without putting them in the game, to see what each does and any
  problems.
- **Make your own mod** starts an empty mod from a name, for the Make pages to save into.
- **The game crashed last time** shows at the top of Backups and repair and on the Mods page, until you
  close it, when the game crashed since the last Apply (or Take all mods out; before the first Apply it
  shows none). It names the mod it was in, when the report can tell, with **Copy the report** and a
  button to turn that mod off.

### Is it safe?

- **The game's own files are never changed.** Everything an Apply puts in has a name of its own, and
  **Take all mods out of the game** removes it.
- **Your save is backed up** before anything changes it. Each save change is made once: a later Apply
  never undoes what you played since, and switching its mod off leaves the save as it is (the Save
  page's **Done so far** puts a change back).
- **Mods that run code** stay out of the game until you allow them. Allow them only for mods from people
  you trust.
- **Looks or gameplay:** Palettes and the colours on Your cat change only how cats look, never their
  traits or stats. Game data and Save change how the game plays, and Apply warns when a Game data change
  touches something risky ([docs/setup.md](docs/setup.md#looks-and-gameplay)).

### Your files and updating

- **Your files** (your mods, Clan Mod Studio's settings and your backups) are in a folder of your own,
  `%LOCALAPPDATA%\WCMods`, not in Clan Mod Studio's folder. **Open the folder**, on Settings and repair,
  opens it.
- **Updating:** unzip a new download over the old folder, or `git pull` if you cloned it. Only Clan Mod
  Studio changes; your files stay as they are. If the studio is open when it's updated, **Restart the
  studio** shows at the top: save your changes, press it, and the page comes back by itself.
- **After a game update,** "Game updated" shows at the top and the Mods page says what it means: mods
  made for the older [game build](docs/guide/README.md#game-build) are left out until they're updated, or
  until you use them anyway ([docs/updating.md](docs/updating.md)).
- **What Clan Mod Studio needs,** where each of your files is, updating from an older version, and
  setting up by hand: [docs/setup.md](docs/setup.md).

## Write mods with code

Clan Mod Studio is built on wcmods, the library and command line in this repository. Start at
[docs/README.md](docs/README.md), which says what to read first:
- [docs/formats.md](docs/formats.md): every file a mod can hold, with examples.
- [docs/scripting.md](docs/scripting.md): Lua in the game with `WCModsGame`.
- [docs/SDK.md](docs/SDK.md): the mod folder and `mod.json`, Python build steps, studio pages, new
  content, the shared Lua modules and C++ mods.
- [docs/cli.md](docs/cli.md): every command, with examples.
- [docs/mechanics/](docs/mechanics/README.md): the game's rules, with the numbers to change for each.

### A mod's files

A mod is a folder in your mods folder (`%LOCALAPPDATA%\WCMods\mods`) with a `mod.json` and some of these
files. The pages under Make mods write them for you:

| File | What it changes |
|---|---|
| `palette.json` | eye, coat, pattern and marking colours; new pattern and marking slots |
| `cats.json` | colours only one cat wears, which slots it wears, its shape and size, its scars |
| `controls.json`, `mouselook.json` | key and button remaps; mouse look |
| `tweaks.json` | small changes while you play: stamina, a heal key, the clock, the fresh-kill pile |
| `data.json` | the game's tables: XP, costs, speeds, tuning values |
| `items.json` | new herbs, materials and accessory looks, with pictures and models of the mod's own |
| `animations.json` | animations of the mod's own for cats and animals: emotes, and ones scripts play |
| `npcs.json`, `quests.json` | cats of the mod's own, and questlines with them (for Sandbox mode) |
| `names.json` | cat name parts, rogue names, the ban list, the cats in your save, other names shown |
| `save.json` | edits to your save, each made once per save |
| `scripts/`, `settings.json` | a script that runs in the game, and its settings |

[docs/formats.md](docs/formats.md) describes each one with examples, and the command line's `new` starts
a mod from a template ([docs/cli.md](docs/cli.md#making-mods)). Mods can also replace whole game files
(`files/Wrc/...`), ship cooked content (`paks/`, not yet tried with this game), run Lua in the game,
and bring build steps, studio pages and C++ ([docs/SDK.md](docs/SDK.md)).

### Scripts in the game

A mod's `scripts/main.lua` runs in the game with no Python, and its `settings.json` gets a page in the mod
menu. The shared `WCModsGame` module covers a lot of the game:
- your cat's health, stamina, level, stats, traits, looks, size and position;
- items, the fresh-kill pile, the time of day, quests and fights;
- the save, the game's managers and its developer switches;
- timers, keys, events and hooks;
- an inspector for any of the game's objects.

With mods that run code allowed, the studio's **Try Lua in the game** page, the mod menu's Lua
(advanced) page and the command line's `lua` run Lua in the game while it's open. The studio's page
has a box that runs a line of Lua and an inspector for the game's objects; nothing there is saved into a
mod, and a line at its top says whether the game can hear the studio. See
[docs/scripting.md](docs/scripting.md); the example is
[game-tweaks](https://github.com/HexOffender/wcmods-examples/tree/main/game-tweaks) in wcmods-examples.

On the Mods page, a script mod's card says, before any Apply, what would stop its script from loading (a
`function` with no `end`, by file and line, or a `settings.json` that isn't right). After the game has
run, it says whether the script loaded when the game last started. Its **More** has **What it said**, the
script's lines from the game's log, newest first, and **Settings**, the rows of its page in the mod menu,
to change before the game starts. A script's errors carry its mod's name: they show on its card, on the
mod menu's Log page, and, for a script that didn't start, at the top of the screen once your cat is in
the world ([Script mods](docs/scripting.md#script-mods)). The mod's name on its errors, and the line at
the top of the screen, haven't been watched in the game yet.

### More than files

Scripts can draw on screen (menus, debug text, markers on places in the world) with
[`WCModsDraw`](docs/SDK.md#wcmodsdraw), and find nearby pickups, cats and quest objectives with
[`WCModsWorld`](docs/SDK.md#wcmodsworld); the example is
[quest-markers](https://github.com/HexOffender/wcmods-examples/tree/main/quest-markers) in wcmods-examples,
a quest of its own with markers on screen. Mods can run C++ in the game too, as UE4SS C++ mods, built
against the game's UE4SS ([C++ mods](docs/SDK.md#c-mods) lists what that needs, and
[docs/cli.md](docs/cli.md#c-mods) the commands; a C++ mod's **More** on the Mods page has **Build C++**).
A C++ mod can put a tab of its own in the game's pause screen, inventory and settings, change the HUD and
draw over it, with the game's own controls ([`WCMods.hpp`](docs/SDK.md#wcmodshpp)); Lua scripts get the
same through it ([the game's own menus and HUD](docs/scripting.md#the-games-own-menus-and-hud)).

### Sharing a mod

**Save as .zip** (under a mod's **More**, or in a Make page's **Share** part) or the command line's `pack`
writes a .zip with the mod's folder in it, and that's what the Mods page's **Add a mod** takes.
- A .zip can hold several mod folders, or one mod's files at its top. A mod is named by its mod.json's
  `"id"`, else its folder's name; one at the top of a .zip with no `"id"` is named after the .zip with a
  version at its end dropped ("Cool Mod v1.3.zip" goes in as `cool-mod`), so the next version replaces
  it. One an older Clan Mod Studio named with the version in it is found by its name and replaced.
- A mod made for a newer Clan Mod Studio (its mod.json's `"wcmods"`) is left out, and says to update.
- A mod pack (`"pack": true` in its mod.json, its mods in `"requires"`) carries every mod in it in its
  .zip. A mod that says `"tool": true` stays on while a pack plays on its own.
- Mods with code (a `section.py`, `scripts/`, `dlls/`, `cpp/`, a `studio/` page) stay out of the game
  until mods that run code are allowed (**Options** on Settings and repair, or `"allow_code_mods": true`
  in `wcmods.json`).

### Command line

Everything the studio does is also a command: `python wcmods.py --help` lists them in groups, and
[docs/cli.md](docs/cli.md) explains each one, with examples.

## Work on Clan Mod Studio

[CONTRIBUTING.md](CONTRIBUTING.md) says how to run the checks and where things go, and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) is the map of the code: the sections a build is made of, the
file formats under `wcmods/formats/`, the exe analysis under `wcmods/exe/`, the in-game Lua under
`wcmods/lua/`, Clan Mod Studio's pages under `studio/`, and the guide under `docs/guide/`.
- **What an install writes:** everything goes into `<game>\Wrc\Content\Paks\~mods\zzz_WCMods_*`,
  `<game>\Wrc\Binaries\Win64\ue4ss\Mods\WCMods*` and `ue4ss\Mods\shared\WCMods*`, and uninstall removes
  those ([docs/setup.md](docs/setup.md#what-an-install-puts-in-the-game)).
- **What's checked:** the tests that run without the game (CONTRIBUTING.md says how), the self-test,
  which checks every file format against your install, and the in-game tests
  ([docs/cli.md](docs/cli.md#testing-and-checking), [docs/agent.md](docs/agent.md)).
  [docs/verified.md](docs/verified.md) lists what has been confirmed in the game, by date, and what
  hasn't been yet.
- **The game's insides:** [docs/reverse-engineering.md](docs/reverse-engineering.md) collects what we've
  worked out, with the tools in `tools/re/`, and [docs/mechanics/](docs/mechanics/README.md) explains the
  game's rules with the numbers to change for each.
