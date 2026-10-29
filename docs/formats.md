# The files a mod is made of

A mod is a folder under `mods/` in your files' folder ([`wcmods.json`](#wcmodsjson) says where) with a `mod.json` (its name, what it needs, and
optionally the oldest Clan Mod Studio that can build it, `"wcmods": "0.4.0"`; [SDK.md](SDK.md#mod-folder)
lists every key) and any of the files below. Clan Mod Studio's Make pages write them; you can also write
them by hand, and `python wcmods.py new <name> --kind <palette|controls|...>` starts one from a template.
A mod that only holds these files runs no code, but for [`scripts/`](#scripts-and-settingsjson), an in-game
script, which comes last. The game's rules behind the numbers are in
[mechanics/](mechanics/README.md); how each file reaches the game is in the [README](../README.md#clan-mod-studio)'s table.

Besides these, a mod can hold **`files/Wrc/...`**, whole replacement files at their game path
(`python wcmods.py extract <pattern>` copies one out to start from), and **`paks/`**, cooked content
made with Unreal Engine 5.7 for new models, textures and sounds, installed as it is under a
`zzz_WCMods_` name ([SDK.md, New content](SDK.md#new-content-models-textures-sounds); not yet tried
with this game). Mods with code are in [SDK.md](SDK.md).


### `palette.json`
```json
{ "eyes": { "Amber": "#FFB300", "Sky": ["#001B2E", "#00E5FF"] },
  "fur": { "3": "#D9380B" }, "pattern": { "0": "#3B2A6B" }, "marking": { "0": "#FFF4E0" } }
```
Eye keys are the game's names for its eye colours, in any case (`Amber`, `amber`), or their numbers
(`iris3`, `row3` or `3`). `python wcmods.py eyes` lists them: `Sclera` is the eye white (0), then the 20
standard colours, then `Dlc1` to `Dlc5`, the extra eyes that come with a game add-on. Some names don't
match the colour (`Yellow` is green). One colour keeps the game's shading, dark at the pupil; a list is
spread from pupil to rim, so a list of one colour (`["#ffb300"]`) is that colour flat. The cat
creator's eye buttons are recoloured to match. Coat, pattern and marking keys are slots 0–24 (0–14
natural, 15–24 bright extras; `"03"` is 3); `python wcmods.py tables` lists the game's originals, and
the Palettes page shows them once the game has run with the script loader (by their numbers until
then).

A colour is `#RGB`, `#RRGGBB` or `#RRGGBBAA` (the alpha is dropped), with or without the `#`, one of
the names black, white, red, green, blue, gold, silver, pink, purple, teal, orange, cyan, magenta,
lime and navy, or `[r, g, b]` from 0 to 255. Keys starting with `_`, and `name` and `description`,
are notes: wcmods ignores them, and the Palettes page keeps them. Anything else the page can't show (a
misspelt eye, a coat past 24, a part a palette hasn't got) it lists under its tabs, keeps as written
and offers to remove, until the page sets that colour itself. Save to mod says what would keep the
file out of the game, and what Apply would leave out of it (an eye the game hasn't got is skipped,
with a warning; the rest goes in). A colour named twice in one part (`"03"` and `"3"`, `"Amber"` and
`"iris2"`) is the later one in the file; Save to mod says which.

Where palettes that are on set the same colour, the one later in the Mods list wins, colour by
colour, and eyes too, whatever each calls them (a name in one, a number in another). The Mods page
sets the order (a mod's priority).

A recoloured slot changes every cat with that slot. To add colours instead, give **pattern** and
**marking** colours slot numbers from 25 up:
```json
{ "pattern": { "25": "#ff00cc" }, "marking": { "25": "#00e5ff", "26": "#7cfc00" } }
```
The game's colours stay as they are, and only cats set to a new slot wear it (the Your cat page or
`cats.json` picks it for your cat). Slot numbers are fixed, so several palettes can each add colours,
and your cat keeps its colour whatever else you turn on. Quick palettes leave alone a palette that
only adds slots. The game checks these indexes against the colour list's real size, so a new slot
nobody adds just shows no colour, never a crash. The cat maker doesn't offer new slots by itself: the
[Creator palettes](https://github.com/HexOffender/wcmods-creator-palettes) mod puts them in its colour
pickers, a palette at a time, from the shared module `WCModsPalettes`, which every install writes: each
palette's new pattern and marking slots, by mod. The themed palettes in wcmods-examples add theirs in a
range each (100-124, 125-149...), so they can all be on together.

Coat colours can't take new slots. The game pairs each of its coat colours with paw, ear, nose and
whisker colours it keeps in its code, and a coat slot past 24 has none, which crashes it. A `fur`
colour numbered 25 and up is still written as a pattern one is (`"fur": {"100": "#9fb6e0"}`), but it
becomes a coat preset (below), never a slot of the game's: named "Coat colour 100", saved with the game
coat (0–19) it looks most like, and keeping that coat's paw, ear, nose and whisker colours. Its id, for
scripts, is `<mod id>/fur/100`. To give just your cat a coat colour of its own, use `cats.json`'s
`colours`; `cats.json` can't set a coat number past 24.

A palette can offer **coat presets** instead: painted on, not new slots.
```json
{ "coats": { "Ash":  { "fur": "#9a9590", "nose": "#3a3330", "paws": "#4a4442", "ears": "#b8a0a0", "like": 12 },
             "Snow": { "fur": "#ffffff", "like": 10 } } }
```
Each has a name (up to 40 characters, no `/`), its coat colour (`fur`), the `nose`, `paws`,
`whiskers` and `ears` colours it wants (the rest stay the game's), and `like`: the game's coat (0–24)
a cat wearing it is saved with. Use 0–19: 20–24 are the Feral Edition's, which a game without it
swaps for another coat. The save only ever holds that game coat, so turning the mod off
leaves the cat on it. wcmods doesn't paint presets itself: it lists them in `WCModsPalettes`, and
[Creator palettes](https://github.com/HexOffender/wcmods-creator-palettes) 1.2 offers them in the
cat maker's Fur picker and paints them on the cats that chose them. A palette with `coats` needs wcmods
0.4.0 or newer (an older one stops at "unknown palette section coats"), so it says `"wcmods": "0.4.0"` in its
mod.json, and an older Clan Mod Studio leaves it out instead. The Mods page's card of the mods that go with
Clan Mod Studio adds Creator palettes from its GitHub release, once it has one.

#### Ready-made palettes

Ten themed palettes are in [wcmods-examples](https://github.com/HexOffender/wcmods-examples): ThunderClan Forest, RiverClan
Waters, ShadowClan Night, WindClan Moor, SkyClan Sunset, StarClan Silverpelt, Dark Forest, Leaf-bare
Frost, Pastel Kits and Vivid Clans (`palette-*`). Add the ones you want from its .zip on the Mods page,
or with `python wcmods.py add ../wcmods-examples/palette-dark-forest`. Each one recolours coats,
patterns, markings and eyes. The
natural coats are a colour grade of the game's own, so every slot keeps its place from light to dark;
the bright extras and the eyes get the theme's own colours.

To switch quickly, tick palettes under **Switch between ready-made palettes** on the Palettes page and press **Apply**,
with the game closed. That turns the ticked palettes on, turns the other palette-only mods off, and
installs. If the install fails, the previous choice is put back. Mods that hold anything besides a
palette are never touched.

Pick one theme at a time: where two palettes change the same colour, only the later one's shows (the
Palettes page names them when both are ticked), so two themes show only the later one's coats and eyes. Eyes-only and coats-only
palettes (Gemstone Eyes, Richer Coats, StarClan Glow Eyes) go on top of a theme, because the themes
are priority -10. From the command line:

```
python wcmods.py palette                                     # list the palette mods and which are on
python wcmods.py palette palette-starclan-silverpelt         # use just that one, and install
python wcmods.py palette palette-dark-forest gemstone-eyes   # Dark Forest coats with gemstone eyes
python wcmods.py palette --none                              # back to the game's colours
```

`tools/make_palettes.py --out ../wcmods-examples` generates them from the game's colours
(`colour_tables.json` and the eye atlas), into a checkout of wcmods-examples. Edit its themes and run it
again to change them. It keeps each one's priority and anything else you added to its `mod.json`. A
palette you've added is your own copy, so add it again to get the new one.

### `cats.json`
```json
{ "player": { "colours": { "fur": "#9fb6e0", "paws": "#ffb6c1", "ears": "#ff9aa6", "nose": "#ff7b9a", "whiskers": "#ffffff" },
              "slots": { "fur": 11, "pattern": 25, "marking": 26, "eyes": 3 },
              "scars": { "ear": "notch-left", "eye": "claws-right", "back": "none" },
              "look": { "body": 6, "ears": 2, "tail": 7, "pattern": 12, "size": 0.9 } },
  "cats": { "Duskfang": { "look": { "fur": 0, "tail": 9 }, "slots": { "fur": 0 }, "colours": { "nose": "#202020" } },
            "WindClan/Warrior/3": { "scars": "none" },
            "4/player": { "look": { "tail": 2 }, "colours": { "ears": "#ffd0e0" } } } }
```
`player` is your cat: its `slots`, `scars` and `look` go into the game you were playing when you
applied, and its `colours` go on whichever cat you play, in any save slot. **`cats`** changes other cats in your save the same
way, each by its name (`"Duskfang"`, as it shows with your names mods) or its place as the Names page
shows it (`"WindClan/Warrior/3"`, for one of two cats with the same name), in the game you're playing,
or with the game's slot first for another (`"2/Duskfang"`), as `names.json`'s `cats` picks them. Both
place forms work: `"Clans/WindClan/Warrior/1"` as the Your cat page shows and writes it, and
`"WindClan/Warrior/1"` as the Names page shows it; places match as written, names in any case. A place
without its clan (`"Warrior/1"`) means that place in every clan, so it changes each clan's cat there.
Every cat called the name changes, with a warning when that's more than one. Mods apply in priority
order, and within one file a later key wins, part by part, over an earlier one that finds the same cat,
so a later choice wins even when it names the cat another way (the Your cat page writes a cat's own
entry after the others that reach it).

**Your cat in one game.** A save holds a game for each cat you've started, numbered from 0 in the file
and from 1 in the game's cat choice (`4` is your 5th game). `player` is your cat in whichever game you're
playing when you apply, which is what a mod to share wants. To change only one game's cat, write
`"<slot>/player"` under `cats` (`"4/player"`, your 5th game's): its `slots`, `scars` and `look` go into
that game whichever one you're playing, after `player`'s when it's the game being played (its own win, part
by part). Its `colours` go on your cat while it has that cat's name, over `player`'s part by part (and
over the mod menu's Colours page, which changes `player`'s while you play), so another game whose cat has the very same name gets them too, with a warning;
a rank-up changes the name, so apply again after one. In someone else's save it's the cat in their game
with that number. The Your cat page writes it when you choose a game in **Which game**. A `"<slot>/player"`
for a game with no cat of yours changes nothing, with a warning.
- **`colours`** go onto the cat's own materials while you play. That covers menus and the HUD's
  portrait (the cat choice's small pictures show the saved colours), and every part is optional. No other cat changes, and any colour works, including paws, ears,
  nose and whiskers, which have no slots at all. The game sets a cat's colours again whenever it
  sets the cat up, so the UE4SS script (`WCModsCatLook`) puts them back twice a second. Another cat's
  are found by its name, so they go on only in the game you're playing, and a cat with the same name
  gets them too (with a warning). A rank-up changes a cat's name (Gustpaw becomes Gust-something),
  so install again after one. Uninstalling brings the saved colours back.
  A colour is written any way `palette.json` takes one (the Your cat page writes `#RRGGBB`).
- **`slots`** picks which colour slot the cat wears, written into your save on install, after a
  backup: `fur` 0–24 (20–24 are the Feral Edition's, which the game swaps without it), `pattern`
  and `marking` any slot, including new ones a palette adds, and the eyes' colours 0–24:
  `eye_left`, `eye_right`, or `eyes` for both. Leave a part out to keep your save's.
- **`look`** sets the cat's shape in your save the same way. `body`, `fur`, `tail`, `ears`, `eyes`,
  `whiskers` and `face` are each one of the game's 10 (0–9): the cat maker shows a clan's 7 of them
  (a WindClan cat's body 3–9, say), and the clans' cats use all 10. The body sets the fur's shape to
  match, as the cat maker does. `pattern` and `marking` are one of its 21 (0–20), the cat maker's grids
  in order. `size` is a scale: the game's cats go from about 0.1 (a kit) to 1.0 (a leader). Body, ears
  and face chose your cat's traits when it was made; the traits are kept apart, so they stay. The
  game sets your cat's size again when it ranks up.
- **`scars`** chooses your cat's scars, written into your save on install after a backup: `"none"`
  for none at all, or each place on its own (leave one out to keep your save's):
  - `ear`: `torn-right`, `torn-left`, `torn-both`, `notch-right`, `notch-left`, `notch-both`;
  - `eye` (it shuts the eye): `ring-right`, `ring-left`, `slash-right`, `slash-left`,
    `claws-right`, `claws-left`, the cat's own right and left;
  - `back`: `bite-1`, `bite-2`, `claws-1`, `claws-2`, a bite or claw marks in one of two spots;
  - `chest`: `bite` or `claws`;
  - `"none"` for no scar there. Numbers work too: a place's scars in this order, from 1.

  Scars show with the game's own Injury system switch on (its Gameplay settings). A boss fight can
  still give new ones. The studio's **Your cat** page has a Scars card for them.

Keys starting with `_` are notes, kept as they are. Anything else the Your cat page can't change (a
part the build doesn't know, a number past the game's, a cat written as something other than a look,
like `"player": "none"`) it lists under "Things this page can't change", keeps as written and offers
to remove; a look chosen for that cat on the page takes its place. Save to mod says what would keep
the file out of the game.

### `controls.json`
```json
{ "keyboard": { "Player_Interact": "F", "Player_Movement_Up": "K" },
  "keys": { "T": "W", "H": "E" },
  "menus": { "keys": { "Escape": "BackSpace" } },
  "gamepad": { "Player_Run": "LT" } }
```

- **`keyboard`** moves an action to a new key: here Interact goes from E to F. Actions are the game's;
  the Controls page shows each with the game's own key (`keymap.game_keys`, `GET /game/keys`).
  `python wcmods.py controls` lists the save's copy of the bindings, which the game ignores and which
  puts Pause on Enter, while the game pauses on Escape. The game's axis actions list only one
  direction, so `Player_Movement_Up` is the back key (S) and `Player_Camera_Right` is the left key.
  The Controls screen's `Player_Show_Inventory` (I), `Player_Show_Quest` (K), `Player_Show_Map` (M)
  and `Player_Growl` (L) aren't in the save, but move the same way (the Controls page has rows for them:
  Inventory, Quest log, Map and Meow). So does any other of the game's
  commands (`keymap.COMMANDS`): `Button_Confirm` and `Button_Back` (Enter and Backspace, in menus),
  `Button_Skip`, `Button_ShoulderL`/`R` (the tabs, on 1 and 2), `Player_Play` (J) and the rest. Which
  key sends which is in [reverse-engineering.md, Input](reverse-engineering.md#input). A new key can be
  a mouse button.
- **`keys`** maps a key you press straight to a game key while you play. Use it for keys no action
  lists: the built-in W, D, Up and Right, or any other key the game uses. `"T": "W"` makes T go
  forward and W stop. The game key stops working on its own once something stands in for it, unless
  an action still uses it (then it's a second key for that job). The key you press stops doing its own
  job too (I standing for anything stops opening the inventory), and the page and the build say what.
  A second key for an action is a pair standing for the action's game key: `"H": "E"` makes H interact
  as E does, even when Interact has moved to F. It does what that key does while you explore, and
  nothing in menus; the Controls page shows it on the action's row as "also on H".
- **`menus`** is a separate set of key pairs used only in the game's menus (every screen but the HUD,
  a fight's menu included).
  Here `Escape` closes menus (it stands for Backspace); `{"I": "Up", "K": "Down", "F": "Enter"}` would
  move through them with I and K and confirm with F. The game's own keys keep working too, but the key
  you press does the other key's job there instead of its own (Backspace standing for Enter no longer goes
  back), and the build says what it stops doing. A letter,
  digit or Space used here still types on the name screen and does the other key's job there too, and
  the build warns about it. A press finishes as it started: the Escape that closes a menu is released
  as Backspace. A pair standing for an arrow key or WASD also goes to the old key remapper, as the map
  zooms and moves on those keys by reading them itself.
- **`gamepad`** moves an action to a controller button, like `keyboard` (here Run goes to LT). The
  left stick and the right stick can't be moved by a mod; change them in Steam's controller settings
  (right-click the game in Steam, then Properties, Controller). An entry that puts a stick action on the
  game's own stick does nothing and says nothing.

Keys are Unreal key names. Controller buttons also take short names (A/B/X/Y, LB/RB, LT/RT,
Start). The build checks the names; a value that isn't a key's name in quotes (`null`, a list) is
refused with the entry it's in. Several mods' files merge, the later one in the mods' order (the
higher priority) winning per action or key. The build's warnings are sentences that say what each
change does and stops doing ("I now does Interact, so it no longer opens the inventory; give Inventory
another key"); they're in the Apply drawer, and the Controls page shows the same ones on its rows
before you apply (`keymap.describe`). Keys wcmods' own scripts listen on (the mod menu's key and
controller button, mouse look's `toggle_key` while a mouse look mod is on) and F11 are kept free by the
page, and a mod's keys (an
emote's `key`, the Emote wheel's) are warned about. Two things carry the remaps out
([remapping.md](remapping.md) has the details):
- **Inside the game**, the `WCModsRemap` UE4SS script (written by `wcmods/gameremap.py` from
  `keymap.native_plan`) does every action and command that's a button, on any key, mouse button or
  controller button, and every `keys` and `menus` pair whose game key sends commands
  (`keymap.KEY_COMMANDS`). The command is sent when its new key is pressed, and the game's own is dropped
  when it comes from the old key, which keeps its other jobs (Space still confirms dialogue when Pounce
  moves). A key that takes an action stops doing its own action, and the build warns. Other scripts read
  where an action is now from the shared variable `WCModsRemap.<action>` (its keys, comma-separated).
  The game's pictures of keys (prompts, menu footers, the Controls tab) show the new keys too.
- **The old key remapper outside the game** (`python wcmods.py play`, deprecated) is the only way to the
  rest, keyboard and mouse only, when you start the game with it: movement and the camera (axes the game reads every frame), `keys` entries for them or for keys
  that send nothing, and mouse buttons in `menus`. Remapping Escape (or Enter, Space, Backspace, Tab)
  there while playing means prompts and dialogue shown during play don't get it; the build warns about
  that. Without UE4SS, it does everything it can.

### `mouselook.json`
```json
{ "sensitivity": 1.0, "invert": false, "smoothing": 0, "toggle_key": "F6" }
```
The game's own camera took no mouse input at release (`DefaultViewportMouseCaptureMode=NoCapture`
in its settings, so no binding can change that); patch 1.1 (October 2026) added a rough mouse control
of the camera of its own. Mouse look stays, because it's smoother and adjustable. It's a UE4SS script. While you explore with the cursor hidden, it captures the mouse and moves the camera
(`BP_AdventureCamera`) itself. It lets go whenever the game shows its cursor. The arrow keys
and right stick still work. `toggle_key` switches it off and on in game (the Controls page won't put an
action on it while mouse look is on). R (or LB) levels the
tilt. `pitch_min`/`pitch_max` limit the tilt (default -20/23, the game's own). `smoothing` is how
long the camera takes to catch up with the mouse, in milliseconds: 0 (the default) follows it at
once, and the game eases the arrow keys and stick over about 200. `"debug": true` logs what it
does to `ue4ss\UE4SS.log`, including whether each turn stayed and how even the frames were. The
Mouse look card on the Controls page sets every one of these (the tilt limits in its Tilt limits fold,
`debug` under For mod makers) and saves them by itself into the `mouse-look` mod, keeping any other keys
the file has; the in-game page edits the same file.

How it turns the camera, and how the game's own camera works (`SwtAdventureCameraActor`, its
tuning keys, splines and the lean while the cat moves), is in
[reverse-engineering.md, The exploration camera](reverse-engineering.md#the-exploration-camera).

Known issues:
- With `smoothing` above 0, fast diagonal moves roll the camera slightly, because the spring arm
  eases turn and tilt together.
- Mouse look stops when the engine's look input is switched off (`IsLookInputIgnored`), but the
  game's own camera locks (`EInputRestriction::CameraRotationDisabled`) aren't visible to scripts,
  so the mouse may still turn the camera where the arrow keys can't.

### `tweaks.json`
```json
{ "keep_stamina_full": true, "heal_key": "F5", "hold_time": true, "time_of_day": 6.5,
  "min_fresh_kill": 20, "skip_scenes": false }
```
Small changes while you play, ticked on the studio's Tweaks page. Every key is optional, and a missing one is off:
- `keep_stamina_full`: your cat's stamina topped up twice a second;
- `heal_key`: a key from `F1` to `F9` that fills your cat's health and stamina, heard in the game's own input
  (while the game is in front); `""` for none. `F10` and `F11` are the game's own, and `F12` is Steam's for a
  screenshot. The Tweaks page doesn't offer a key your mods already have you press: the mod menu's, mouse look's
  on and off key (`toggle_key`, F6 unless a `mouselook.json` says otherwise), a key a `controls.json` remap puts
  an action or another key on. A file that has one anyway is warned about at Apply, by what else uses it; on the
  mod menu's key, the heal is left out (the menu keeps its key);
- `hold_time` and `time_of_day`: the clock held at that hour (0 to 24, `6.5` is 06:30);
- `min_fresh_kill`: the camp's fresh-kill pile kept at least this full (0 to 100, the pile's own count);
- `skip_scenes`: not available yet, and refused with `true` ("it hasn't been checked that skipping keeps the
  story's steps"): each of the story's scenes skipped as it starts, with the game's own hold-to-skip, as Sandbox
  mode skips them for its cats. It was only seen working in sandbox games; whether a skipped scene still does
  what it does at its end (a quest step, a ceremony's rank) is the check it waits for. Even then, a cat Sandbox
  mode has in the forest is left to Sandbox mode.

Keys starting with `_` are notes. With several mods, each tweak comes from the one with the highest priority that
sets it. They go in as `WCModsTweaks`, wcmods' own UE4SS script (no mod's code runs, so no "Allow mods that run
code"), which also adds a Tweaks page to the mod menu: its Save writes the top mod's `tweaks.json`, keeping its
notes. The script carries the tweaks it was installed with, so a change saved in the game is a change to apply.
With no tweak on (a `tweaks.json` of `{}`, or every box unticked), nothing goes in the game, and the mod menu has
no Tweaks page.
The tweaks are Game Tweaks' (the example script in wcmods-examples), with no code to write.

### `data.json`
```json
{ "CombatBaseExperience.csv": { "*": { "BaseExperience": "x2" }, "Mice": { "BaseExperience": 25 } },
  "TuningData.csv": { "Gameplay.Exploration.Player.MoveAndRun.Run.Speed": 450 } }
```
Changes to the game's tables (`Gameplay/DataTables/NonAsset`): the Game data page writes it. A key is a
table's name (`NPC/Scars.csv` for one in a subfolder, or a full `Wrc/...` path), then its rows by their
first column, then the columns to change:
- **Values** are numbers, text, `true`/`false` (written `TRUE`/`FALSE`) or `"xN"`, which multiplies the
  number in the cell (`"x0.5"` halves it). A number is written with at most six decimals. A text that
  reads as a number (`"0.08"`) is a number. A cell that holds a number keeps it when the value isn't one
  (`"abc"`, `"1,5"`), and the build says so.
- **Columns** match without regard to case. `{ "row": value }` changes the table's second column (its
  value column, in TuningData).
- **Every row** is `"*"`. `"-": ["53"]` removes rows (`"-": "53"` is one row) and `"+": [{ "#": "91", ... }]`
  adds them, missing columns left empty.
- **The order inside one file is fixed**, whatever order the keys are in: removals, then `"*"`, then the
  named rows, then additions. A named row's own value wins over `"*"`, so the file above doubles every
  animal's XP except mice, which stay at 25. A named row's own `"xN"` multiplies the cell as it was
  before this file's `"*"`, so the two never compound.
- **Between mods**, each mod's file goes in priority order on what the one before left, so multipliers
  stack: two mods' `"*"` `"x2"` make x4, and nothing is said about it. When a later mod sets a plain value
  in a cell an earlier one changed, the later one's value is what the game gets, and the build says so
  once per table, column and pair of mods ("my-tweaks sets BaseExperience in CombatBaseExperience.csv
  where double-xp changed it too (Mice): the game gets my-tweaks's value there").
- **A table the game hasn't got** is left out with a warning, and the file's other tables still go in;
  so is a row it hasn't got.
- **Keys starting with `_`** (`"_help"`, `"_note"`) are notes, at the top, in a table or in a row: the
  build skips them and the Game data page keeps them as they are.
- **Quests and talk** (QuestDialogues, StoryDialogues, QuestObjectives, QuestDynamicObjectives,
  NarrativeRole) can be changed like any table, with a warning: a wrong value can stop a quest.

In wcmods 0.3 and before the keys' order decided: a row written before `"*"` was multiplied by it too, which
the Game data page never showed (it writes numbered rows before `"*"`). Such a file now builds to the row's
own value, and for a release the build says so, cell by cell ("this file's own value now wins over its
`"*"`").

### `items.json`
```json
{ "items": [ { "id": "MoonHerb", "like": "MediumHealingHerb", "name": "Moon Herb",
               "description": "Health Recovery (medium). Picked under a full moon.",
               "recipe": { "Dandelion": 2, "Cotton": 1 }, "give": 3 } ] }
```
New herbs, materials and accessory looks: a name, a description and an icon in the inventory, what
the herb does (one of the game's herb effects), a recipe at the medicine cat's bartering, and some
to start with. Each item needs a name and a description: one without is left out of the game, with a
warning, and the rest go in. `like` borrows the rest from a game item, and `"recipes"` changes what the
game's own herbs and accessories cost. An icon or a look can be a PNG of the mod's own or one of the
game's recoloured (`{"tint": "#a8c4ff"}`, made from your game files at install); the Items page's "Save
the game's icon to paint over" (and look) saves the game's as a PNG to paint over. A new look can also
have a shape of its own, `"model": "models/my-collar.glb"`: an OBJ or glTF file made in Blender or the
like, in metres around the cat that the Items page's "Save a start kit to model on" saves to start from;
it follows the cat's body and needs the script loader (UE4SS) in the game. `"place"` moves, turns and scales that shape (or
the accessory's own) where it sits on the cat, and `"opacity"` below 1 makes it see-through glass of the
`"glass"` colour. New looks work for neck, body and paw accessories, not head ones. A herb's or a
material's `"model"` (with a `"texture"` PNG and a `"place"`) is how it lies on the ground when a script
drops it for the cat to pick up; without one it lies there as the game's pickup of the herb it's
`like`. Every key is in [SDK.md, New items](SDK.md#new-items-itemsjson).

### `animations.json`
```json
{ "animations": [ { "id": "Yawn", "name": "Yawn", "game": "A_CatMaster_Yawn_1", "emote": true, "key": "F7" },
                  { "id": "Wave", "name": "Wave", "file": "animations/wave.glb", "emote": true, "key": "F8" },
                  { "id": "Spin", "name": "Spin", "file": "animations/spin.glb", "for": "mouse", "loop": true } ] }
```
Animations for cats or one kind of animal (`"for"`: mouse, rat, rabbit, squirrel, bird, fox, badger,
dog, snake): one of the game's own (`"game"`, by its name, no Blender needed; needs wcmods 0.4.0 or
newer: an older one leaves each such animation out, "no file chosen yet", and installs the others) or the mod's own, made in Blender and saved as glTF (`"file"`, a `.glb`). A cat's can be an emote:
a button on the mod menu's Emotes page, and a key. Scripts play any of them (`Game.anims.play`). The
Animations page's start kit saves the animal rigged to the game's skeleton to animate. They play over
what the animal is doing, where it stands, and need the script loader (UE4SS). One with `"replaces":
"A_CatMaster_Trot_1"` (one of the game's sequences) plays in that one's place instead, for every cat or
every animal of the kind, fitted to its length. Each needs a name, and a file or one of the game's: one
without is left out with a warning. Every key is in [SDK.md, Animations](SDK.md#animations-animationsjson).

### `npcs.json`
```json
{ "npcs": [ { "id": "mossfoot", "name": "Mossfoot", "title": "Elder",
              "colours": { "fur": "#7a6a58", "pattern": "#4a3f33", "markings": "#d8cfc0" },
              "eyes": 6, "size": 0.8,
              "look": { "body": 6, "fur": 2, "tail": 7, "ears": 3, "pattern": 12, "marking": 3 },
              "slots": { "fur": 9, "pattern": 4, "marking": 0 },
              "lines": ["The forest is yours, young one."] } ] }
```
Cats of the mod's own, made on Clan Mod Studio's Characters page. The
[Sandbox mode](https://github.com/HexOffender/wcmods-sandbox) mod brings them into the forest with a
sandbox cat, so a mod with them works with it: `"uses": ["sandbox"]` in its `mod.json`, which the studio
writes when it saves cats or quests ([SDK.md](SDK.md#mod-folder)). Turning the mod on turns Sandbox mode
on when it's there, and without it the mod still goes in (its items, palettes and names too), its cats
waiting for Sandbox mode. A mod an older studio saved says `"requires": ["sandbox"]` instead; for a mod
with no code of its own (no scripts, C++ mod, `section.py` or studio page) wcmods reads that as `uses`
too, so it never keeps the mod out, and saving it again on either page writes it as `uses`. A mod with
code of its own keeps it as a real need. Fixed looks need Sandbox mode 0.5 or newer; an older one makes
the look up each time (the page and Apply say so).
- `id`: small letters, digits and dashes; quests name the cat by it. `name` and `title` (smaller, above
  the name) show over its head.
- `colours`: any of `fur`, `pattern`, `markings`, `nose`, `paws`, `whiskers`, `ears`; the rest are the
  game's. `eyes` is an iris colour slot (0 to 24), `size` the cat's size (0.3 to 1.5; the game's are about
  0.4 to 1.1). Left out, it's 0.85, a grown cat, as the Characters page shows it.
- Its look: with no `look` or `slots`, the game makes it up anew whenever it puts the cat in the forest,
  as it does for its own clan cats (its shape, pattern and colour slots; `colours` go on top). `look`
  fixes the shape, as `cats.json`'s does: `body`, `fur`, `tail`, `ears`, `eyes` (their shape), `whiskers`
  and `face` each one of the game's 10 (0–9), `pattern` and `marking` one of its 21 (0–20). `slots` fixes
  the colour slots it wears: `fur` 0–24 (its nose, paws, ears and whiskers go with it), `pattern` and
  `marking` any slot, including new ones a palette adds (while that palette is on: Apply warns about one
  no palette that's on adds). A part left out of both (and the eye colour, without `eyes`) is made up
  again each time; an empty `look` is the same as none. The Characters page's **Same look every time**
  (the default for a new cat) fills in all of them at random, to keep or change.
- Where it stands: with no `at`, beside the sandbox cat the first time it comes into the forest, and there
  for that cat after. `"at": [x, y, z]` (cm, with `yaw` in degrees and `level`) puts it in one place for
  every cat; the studio fills it in from where your cat stands. `"at": null` is the page's **At one spot**
  with no spot filled in yet: until it is, the cat stands beside your cat (the page says so).
- `lines`: what it says when you walk up to it and use the game's *Talk* prompt (the Interact key, E or
  A on a controller; Interact or Enter shows the next line) and no quest wants it.
- `patrol`: an optional object for Sandbox mode's NPC patrol runner (Sandbox mode 0.6 or newer; with an older one
  the cat stands still, and the Characters page and Apply say so); the page's **Where they walk** makes one,
  with its points as `{x, y, z}` objects. Its fields and nested objects are passed
  through to the runner; unknown nested keys are kept for forward compatibility. For example:
  ```json
  { "patrol": {
      "points": [
        { "x": 100, "y": 200, "z": 0, "level": "L_WorldMap_01_P", "wait": [1, 3] },
        [400, 200, 0]
      ],
      "mode": "pingpong", "speed": 120, "retries": 2, "enabled": true,
      "wait": { "until": { "quest": "dandelions", "step": 2 }, "timeout": 60 }
  } }
  ```
  `points` is a list of `{x, y, z, level?, wait?}` objects or `[x, y, z]` arrays. `mode` is `pingpong`
  (the default, traveling back and forth), `loop` (wrap from the last point to the first), or `once`.
  `speed` is in cm/s (more than 0); `retries` (a whole number, 0 or more: how often a blocked walk is tried
  again before the point is skipped) and `enabled` control the runner. `wait` sets a default or per-point pause:
  a number of seconds, `{ "min": seconds, "max": seconds }` or `[min, max]` for a random range, `"none"`
  to pass through, `"release"` to wait for a script, or `{ "until": { "quest": "id", "step": 2 } }`.
  An `until` can name a `quest` (an id or `mod/id`; with `step`, the step's number, 1 or more, is reached,
  otherwise the quest is done), an in-game `event` raised by `Sandbox.raise(name)`, or a `release` (`true`, or
  a name); `timeout` is optional and measured in seconds (more than 0).

### `quests.json`
```json
{ "quests": [ {
    "id": "dandelions", "title": "Dandelions for Mossfoot", "giver": "mossfoot", "after": [],
    "steps": [
      { "do": "talk", "lines": ["Bring me three dandelions?"] },
      { "do": "collect", "item": "Gameplay.Inventory.Materials.Dandelion", "count": 3 },
      { "do": "visit", "place": "medicine-cat" },
      { "do": "visit", "at": [-60040, -200, 813], "radius": 400, "objective": "Go to the old oak" },
      { "do": "talk", "npc": "mossfoot", "lines": ["Thank you!"] } ],
    "reward": { "Gameplay.Inventory.Consumable.SmallHealingHerb": 2 } } ] }
```
Questlines with the mod's own cats, made on the Questlines page, run by Sandbox mode (`"uses":
["sandbox"]`, as for `npcs.json`).
- A quest starts once the quests in `after` (this mod's) are done, at once with none; quests that wait
  for each other in a circle are refused. `giver` is one of the mod's cats: a talk step with no `npc` is
  with them, and the giver wears the game's quest mark while the quest waits for you.
- `description`: a sentence about the quest, shown under its title on the mod menu's Questlines page
  (Sandbox mode 0.5 or newer).
- Its `steps` go in order. `talk`: the cat says its `lines`, and the step is done after the last.
  `collect`: pick up `count` of `item` (its whole tag; a mod's own item is
  `Gameplay.Inventory.Consumable.<id>` or `...Materials.<id>`) from the step's start. `visit`: go within
  `radius` cm (400) of `at`, or of the nearest `place` (`medicine-cat`). A visit with a `level` is done
  only in that level.
- `objective` is what the game's objective panel says for a step. Left out, Apply fills it in with the
  names the cat and the item have then: "Talk to Mossfoot", "Find 2 Moss", "Visit the nearest medicine
  cat", "Go to the marked place". (A file an older studio saved has those words written in; the page
  takes them out on its next save, so they follow renames.)
- `reward`: items dropped at the cat's paws when the last step is done.
- How far each sandbox cat has got is kept by Sandbox mode in `sandbox-story.json` beside the game's
  saves, one record per sandbox cat. From Sandbox mode 0.5, a record belongs to the cat that was in the
  save slot when it was written (the registry's `made` stamp), so a new sandbox cat made in the slot of a
  deleted one starts every questline from the beginning, with its cats beside it; a record 0.4 wrote stays
  that cat's. Each quest's record keeps its shape too (its steps' `do`, with a `collect` step's `item` and
  `count`): a quest a cat hasn't finished starts over when its shape changes (a step added or taken out, a
  step's `do` changed, a `collect` step's `item` or `count` changed), with a log line and the game's
  update banner. New `lines`, objectives, a new `title` or another spot don't restart it, and a finished
  quest stays finished (its reward isn't dropped again). The mod menu's Questlines page starts one quest
  over, and the Questlines page's **Start every questline over** (with the game closed) clears every mod's
  quests for every sandbox cat and keeps where its cats stand.

wcmods checks both files at install and puts every enabled mod's together into one UE4SS mod,
`WCModsStory`, which shares them as JSON text in the UE4SS shared variable `WCMods.story`
(`{"format": 1, "mods": [{"id", "name", "npcs", "quests"}], "icons": {item tag: texture}}`), for any
script to read; every step has its `objective` there, filled in at install when the file left it out.

### Mod packs
```json
{ "name": "The Moonlit Path", "description": "...", "version": "1.0", "author": "...",
  "pack": true, "requires": ["moonlit-cats", "moonlit-palette"] }
```
A mod pack is a mod.json and nothing else: a set of mods that go together as one experience. Its mods
are its `"requires"`, so turning it on turns them on. Its .zip (Save as .zip, or `wcmods pack`) carries
every mod in it. Clan Mod Studio's Mod packs page makes them, plays one on its own (every other mod
off, but your own tools and the mods its mods `"uses"` that were on) and goes back to your own mods
(`"pack_before"` in `wcmods.json` remembers them, and the pack's name, so going back works even after the
pack is removed). A mod is one of your own tools when its mod.json says `"tool": true`, or it's Menu pages,
Creator palettes or the Emote wheel. In a pack's .zip, My mods (`my-mods`) goes in as `<pack>-mods`, named
"<pack name>: its own content" (`<pack>-mods-2` and so on when the pack holds a mod by that name already),
with every `requires` and `uses` naming it rewritten, so whoever adds it keeps their own My mods; the
folders on your side are unchanged. Only mod.json's `requires` and `uses` are rewritten: anything inside
the mods that names `my-mods` itself (a script reading `mods/my-mods`, a coat preset's id made from it)
still says `my-mods` in the pack, so give such content a mod of its own before packing it.

### `names.json`
```json
{ "prefixes": { "rename": { "Otter": "Moth" }, "add": { "Sparrow": { "like": "Wren" } }, "remove": ["Pigeon"] },
  "suffixes": { "rename": { "pelt": "coat" }, "add": { "whisper": {} }, "remove": ["face"] },
  "rogues":   { "rename": { "Chesnut": "Chestnut" }, "add": ["Moss"], "remove": ["Fury"] },
  "banned":   { "add": ["Lionheart"], "remove": ["Tigerstar"] },
  "names":    { "Brightheart": "Brightfur" },
  "cats":     { "player": "Mothheart", "Blaze": { "fixed": "Sparkle" }, "Cedarkit": { "prefix": "Glimmer" } } }
```
A clan cat's name is a prefix and a suffix (Otter + paw). The suffix changes with rank: kits are
-kit, apprentices -paw, leaders -star. `python wcmods.py names` lists every part with your mods'
changes, and `names --cats` lists the cats in your save. The **Names** page in the studio edits all
of this. Names are matched by their English text (any case) or ID.

- **`prefixes` / `suffixes`:**
  - `rename` changes every name with that part: Otterpaw, Otterheart and the rest become Mothpaw,
    Mothheart.
  - `add` makes a new part that every combination exists for. `like` copies how often another part
    is used (each clan for prefixes, each rank for suffixes) and how it's suggested on the name
    screen. Without it, the new part gets the average. An added part's object can also say how
    often it's used, as `weights` does: `clans` for a prefix (`{ "RiverClan": 0.05 }`), `ranks` for a
    suffix (`{ "Warrior": 0.1 }`); and `looks`, its scores on the name screen against a cat's looks
    (the filters table's columns: `{ "Body_1": 2 }`).
  - `remove` stops the game handing a part out; cats that already have it keep their names. The
    kit, paw and star suffixes are kept, because kits, apprentices and leaders need them.
  - `weights` sets how often one is used, e.g. `{ "Fern": { "ThunderClan": 0.07 } }` (a number, or a
    number in quotes).
  - Renaming a part to another part's text is warned about: the game would have two parts it can't
    tell apart by name.
- **`rogues`:** the whole names cats outside the clans get.
- **`banned`:** names the game never hands out (mostly canon characters). `add` takes any prefix +
  suffix the game can make, and `"clear": true` empties the list.
- **`names`:** changes every text that's exactly this name, including the nine canon cameo cats.
  Some cameo names are also clan names (Brightheart is Bright + heart), so both change, and some are
  something else in the game too (Rock is a cameo cat and a crafting material, Fox a rogue and an
  animal): the Names page says under each entry what else it renames.
- **`text`:** sets any of the game's texts by its key, in English, for anything that isn't a cat's
  name: an area, a quest's title, an item's name. `{ "STR_RIVERCLAN_ZONE_5": "Willow Hollow",
  "QST_Gather.Apprentice.Title": "Gather for the elders", "STR_ITEM_CONSUMABLE_NAME_7": "Sunpetal" }`. The
  Names page's Places, quests and items card lists them and writes this, one row per text: some texts
  are shared (one title for the Rest 1, 2 and 3 quests), and renaming one renames everything that shows
  it. The mod menu's pages read the build's renamed texts, so they show the new names. A key the game
  hasn't got is added, with a warning.
- **`cats`:** renames cats in your save on install, after a backup. Each key picks a cat: `player`,
  its current name, or its place from `names --cats` (`RiverClan/Warrior/3`), with `"was"` for the
  name it has there (`{ "name": "Mothheart", "was": "Woodheart" }`), so the entry stops counting if
  another cat takes that place. A cat whose name only a mod gives is also found by the name made
  from its IDs while that mod is off, or by its current IDs (`STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART`,
  or `STR_CAT_NAME53` for a rogue called Otter, as an older Names page wrote such a cat); never by
  the prefix's ID alone for a clan cat (`STR_CAT_NAME53` isn't Otterheart). When two entries pick
  one cat, the last one renames it and the build warns about the other. A save holds a game per cat
  slot you've started; a key means the game you're playing, and a slot first (`1/player`, `1/Blaze`,
  `1/RiverClan/Warrior/3`) picks a cat in another one (slot 1 is the Names page's "Your 2nd game").
  The Names page lists each game's cats under its own heading, the one you're playing first.
  - A plain name that's a prefix + suffix the game can make (new ones included) grows with rank like
    any clan cat's. Any other plain name is used as a fixed name, a rogue name too (Storm on a clan
    cat); only a rogue or loner given a rogue name takes that rogue's own name.
  - `{ "prefix": "Glimmer" }` gives the cat its own prefix that grows with rank: Glimmerkit, then
    Glimmerpaw. One of the game's prefixes (`{ "prefix": "Otter" }`) keeps the cat's suffix; a rogue
    or loner, who has no suffix, is then called Otter, a text the mod adds (the game has none for a
    prefix alone), so that rogue needs the mod on like any name of your own.
  - `{ "fixed": "Sparkle" }` never changes.
  - A rename the game would have no text for (a prefix kept with a suffix from a mod that's off) is
    left out, with a warning, and the cat keeps its name.

  Story roles (`{THE AGING LEADER}` in dialogue) show the cat cast in them, so renaming that cat
  renames the role. A cat is skipped if its name changed between building and installing.

  A name the game doesn't have (a new prefix, a fixed name) is text wcmods adds to the game, so the
  game shows it only while the mod is installed. If a renamed cat shows as `<MISSING STRING TABLE
  ENTRY>` (dialogue and the den call it "Cat 1"), the save has its new name but the game hasn't got
  its text. A build warns when the mod that named a cat is off or left out (the save keeps the name
  either way), and when Steam starts another copy of the game than the one wcmods installs into (the
  Mods page offers to switch to Steam's). Otherwise the game isn't loading wcmods' pak, which the mod
  menu's Overview says. Turn the mod back on or check the game folder in Get set up, then Apply
  again, or put the save back from Backups and repair (the Settings and repair page). The Names page
  lists such a cat by its name, says it would show as `<MISSING STRING TABLE ENTRY>`, and offers it a
  game name; when the mod it's editing is the one that's off, it says so ("This mod is off") for the
  cats only that mod names. "Take all mods out of the game" says first which cats in your save have
  names only your mods give.

The build refuses a `names.json` whose values are the wrong kind (a rename to nothing, a weight that
isn't a number, a name in a list that isn't text, a `names` or `text` entry whose new text is empty or
not in quotes), saying where in the file; Save to mod says it under the Editing mod bar. Shapes that
only do nothing are warnings instead: a `cats` entry with both `name` and `fixed` uses the name, and
says so.

Renames change the English text only. The other languages translate names, and those translations
stay. Added names and parts appear in every language with their English text. Added parts get IDs
made from their name (`STR_CAT_NAME_WCM_SPARROW`), so saved cats keep their names whatever else
your mods add.

### `wcmods.json`

Not a mod file: wcmods' own settings, made on the first run and edited by Clan Mod Studio and the
commands. Every key is optional. It's in your files' folder, `%LOCALAPPDATA%\WCMods`, with `mods\` and
`backups\` (`WCMODS_DATA` moves the folder; `python wcmods.py status` shows where it is), so updating
wcmods never touches it. Older versions kept all three in the wcmods folder; the first start after
updating moves them out (`wcmods/userdata.py`). A damaged one (not JSON) is set aside as
`wcmods.json.broken-<date>-<time>` and the settings start afresh: the studio says so at the top of its
page and the commands print it, and Get set up finds the game again. Beside them, `cache\downloads\`
keeps the last .zip of each of the mods that go with Clan Mod Studio fetched from GitHub
(`wcmods/addons.py`); it can be deleted at any time.

| Key | What it is |
|---|---|
| `game_dir` | The game's folder (the one with `Wrc` in it). Found through Steam; set it when it isn't, or Get set up asks for it. When it isn't the copy Steam starts, builds, `status` and Play say so, and the Mods page offers to switch |
| `save_dir` | Where the game keeps its saves, when it isn't `%LOCALAPPDATA%\Wrc\Saved\SaveGames` |
| `oodle_dll` | An `oo2core_*_win64.dll` from another installed game, for faster decoding of the game's files (wcmods decodes them itself without one) |
| `allow_code_mods` | `true` lets mods that carry code run it (build steps, in-game scripts, studio pages, C++): only for mods from people you trust. Options on the Settings and repair page |
| `allow_outdated` | `{ "<mod>": [<build>, ...] }`: mods used anyway on game builds they weren't made for ("Use it anyway", `wcmods allow-outdated`) |
| `rechecked` | `{ "build": <build>, "when": "<date and time>", "results": { "<mod>": "ok" or why it didn't build }, "signatures": { "<mod>": "<its version, file count, size and newest time>" }, "warnings": { "<mod>": ["<what the check's build warned of it>"] } }`: what the check after a game update found, for the installed build (`wcmods/exe/gamebuild.py`, `recheck`). A mod that passed is also marked in its own mod.json's `game_builds`; one marked "couldn't check: the game's files can't be read right now" is tried again, and so is any mod whose signature changed since |
| `pack_before` | `{ "pack": "<pack>", "name": "<its name>", "on": ["<mod>", ...] }`: while a mod pack is played on its own, the mods that were on before it (the Mod packs page's Back to my mods) |
| `console` | Whether the game's `~` console (UE4SS's console enabler) is on |
| `debug_cat_look` | `true` makes your cat's colours script log every cat it sees |
| `installed`, `installed_ue4ss`, `installed_ue4ss_shared` | What the last install put in the game: the mods, when they were built, the game build, the mods folder they came from, the UE4SS mods and shared modules, and `save_pending` when it had save edits but no save to make them in. The studio compares them with your mods; leave them alone |
| `crash_after` | When the last install, or Take all mods out, happened: the studio's crash card shows only a game crash from after it (none at all before the first) |
| `menu_key`, `menu_pad`, `menu_scale` | The mod menu's key (`INS`, `HOME`, `END`, `DEL`, `PAGE_UP`, `PAGE_DOWN`, `F1`-`F12` but F11), the controller button that opens it too (an Unreal key name, `""` for none) and its size (0.6 to 2.2). Options on the Settings and repair page; an install puts them in the game ([SDK.md, `WCModsMenu`](SDK.md#wcmodsmenu)) |
| `skip_code` | `true` once Get set up's "Let mods run their own scripts" was told "Not now" (or mods that run code were turned off on the Settings and repair page): the step counts as done, and `allow_code_mods` stays as it is |
| `setup_addons` | `"added"` once Get set up's "Add all four" has run (whatever came of each one; the Mods page's card of the mods that go with Clan Mod Studio says), or `"not now"` |
| `skip_menu_pages` | `true` once an older Get set up was told "Not now" for the Menu pages mod; read as `setup_addons: "not now"`, and adding Menu pages clears it |
| `cheats` | From when the mod menu was a mod of its own: whether its cheats started on. Adding the Menu pages mod takes it into that mod's `settings.json` |

The file starts with a `_help` line saying the same.

### `save.json`
```json
{ "set": { "1/GameplayProgression/Level": 20 },
  "add": { "1/GameplayProgression/State/Inventory": { "Gameplay.Inventory.Consumable.SmallCatnip": 5 } },
  "remove": [ "1/GameplayProgression/State/Inventory/Gameplay.Inventory.Materials.Cobweb" ] }
```
Changes to the player's own save (`WrcGame.sav`), made when the mod is applied, with the game closed and
a copy of the save kept first. The Save page writes it (Keep it as a mod to share); its own Change my save
now makes the same changes straight away, without a mod.
- **Paths** start inside the save's account object and are split by `/` (a key with a `/` in it can't be
  named). `Shared/...` is the game's settings and controls; `0/`, `1/` ... is a game each, one for every
  cat started, numbered from 0 (`4/` is the game the cat choice shows 5th, the Save page's "your 5th
  game"), and `Shared/General/CurrentCatSlot` says which was played last. A change is for the game its
  path names: in whoever installs the mod, it goes into their game with that number, whichever cat that
  is. The Save page writes the paths of the game chosen in its **Which game**; its Advanced part shows the
  whole save.
- **`set`** changes a value the save has (a path it hasn't got is skipped, with a warning). **`add`** adds
  keys to an object, or sets them when the object has them already: an item to the inventory, by its tag.
  **`remove`** takes out an item carried (`<slot>/GameplayProgression/State/Inventory/<tag>`) or one
  element of a list (a path ending in its number). Anything else is left out with a warning: never a
  whole game (`"2"`), `Shared` (the game's settings and controls) or a cat's
  `<slot>/GameplayProgression`. Removals go after the sets and adds.
- **Each change is made once per save.** What was made is kept in [`save-changes.json`](#save-changesjson),
  so the next Apply doesn't make it again over what the player has played since: a level set to 10 and
  played on to 14 stays 14. A mod whose value changes (Level 20 becomes 18) makes it again.
  `"always": true` makes every change at every install instead, as before.
- **Once per slot, not per cat.** The record is by the save's account and the path, and a path names a
  slot: a new cat started in a slot where a change was made doesn't get it. The Save page's Change my
  save now makes it for that cat.
- **Two mods changing one path:** the one with the higher priority is what the save gets. The other is
  recorded as not made (`lost_to`), so it isn't made later in the winner's place either.
- **Ranges:** a value outside what the game takes is left out with a warning: Level 1 to 20; Experience,
  health, stamina and counts of things carried 0 or more (whole numbers for Level, Experience and counts);
  the fresh-kill pile 0 to 100; a volume 0 to 1.
- **Restoring a backup** (Settings and repair, or `wcmods restore`) puts back the record that backup kept
  with the save (every save backup has it, as `wcmods-save-changes.json` beside the save files), so the
  next Apply makes again only what that save hasn't got. Restoring keeps a backup of the save you had
  first ("before-restore"), with its record: restoring that undoes the restore. A backup made before
  the record was kept (by wcmods 0.3) has none: the changes recorded since it are forgotten (made
  again), the ones put back since count as made, and the ones made before the record was kept stay.
- **A save that can't be read**, or no save yet, leaves the save edits out and the rest of the install goes
  in. Made before there was a save, they wait: once the game has made one, the studio's status says
  "save edits are waiting for a save" until the next Apply.

Before wcmods 0.4 every `set` and `add` was made again at every install. The first install with this
version makes no change for the mods that were in the last install: their changes are recorded as made
already (unless a mod changed since that install), so nobody's progress is put back one last time. When
there was no save at that install (no backup of one from then, and the save file made since), nothing
was made then, so the changes are made now. Turning a mod off leaves its changes in the save; the Save
page's Done so far puts each one back. An older wcmods ignores `remove` and `always`.

### `save-changes.json`

Not a mod file: the record of the save edits made to your save, beside `wcmods.json` in your files'
folder (`wcmods/saverecord.py`). By the save's account, then by who made the change (a mod's id, or
`studio` for the Save page), then by path:
```json
{ "acct": { "my-mod": { "1/GameplayProgression/Level": { "op": "set", "value": 20, "was": 5,
    "label": "Fawnstar's level", "when": "2026-10-28T15:30:12", "backup": "20261028-153012-before-save-edits" } } } }
```
`was` is what Put it back writes; `undone` says when it was put back, and keeps the record so a mod still
on doesn't make the change again; `before` marks a change made before wcmods kept this record, which can't
be put back from here; `lost_to` marks a change another mod's change to the same path won over, which
wasn't made. Every save backup keeps a copy of this file as it was then (`wcmods-save-changes.json`,
`null` when there was none yet), which a restore puts back. Delete the file and the next Apply treats
the last install's mods as made, as on the first install with this version.

### `scripts/` and `settings.json`
```
scripts/main.lua      runs when the game starts
scripts/*.lua         more files for require("name") (scripts/lib/util.lua is require("lib.util"))
settings.json         optional: the script's settings, MOD.settings
```
```json
{ "_help": "Game Tweaks' settings: change them on its page in the mod menu (Insert).",
  "keep_stamina_full": false, "time_of_day": 12.0, "min_fresh_kill": 0, "heal_key": "F5", "spots": [] }
```
A script is code, so it only goes in the game with mods that run code allowed (Options, on the Settings and
repair page). Everything under `scripts/` goes in as a UE4SS mod of its own, `WCModsScript_<mod id>`, with the
characters that aren't letters or digits as `_`: two mods whose ids differ only in those, or in capitals
(`my-mod`, `my_mod`, `My.Mod`), would go in as one, so both are refused, by name, until one is renamed; and a new
mod too like another is refused when it's made. How a script is written is in
[scripting.md, Script mods](scripting.md#script-mods).

What's checked before the game sees it, and said in words on the mod's card on the Mods page (and when the
studio saves `settings.json`):
- `scripts/` needs a `main.lua`;
- each `.lua` file's blocks and brackets: a `function`, `if`, `for` or `while` without its `end`, a `repeat`
  without its `until`, a bracket or a string left open. A file with one of these won't load in the game, so
  the card says the first one, by file and line; the rest of the install still goes in;
- `settings.json` has to be JSON (a byte order mark from Notepad is fine) holding an object. A mistake, such as
  a comma after the last setting, is said with its line, and keeps the mod out of the install until it's
  fixed, since the script would start without its settings.

Keys starting with `_` are notes. A script with a `settings.json` and no page of its own gets one in the mod
menu (`"settings_page": false` in `mod.json` turns it off), and the same rows under More on its card on Clan Mod
Studio's Mods page (Settings, with Save settings), a row for each key, by its value:
- `true` or `false`: a switch;
- a number: a number box. A whole number (`3`) stays whole; one written with a point (`12.0`, `1.5`) moves in
  steps of 0.1 and is saved with its point, so the script still gets a number with a fraction;
- `"#rrggbb"`: a colour;
- any other text: a text box;
- a list or an object: shown as it is, to change in the file;
- a `_` key with text: a note.

Three kinds of note go with a setting, by its name: `"_help_<key>"` shows under that setting's row,
`"_min_<key>"` and `"_max_<key>"` are the lowest and highest a number takes (the studio refuses a Save outside
them; the game's number box stops there).
```json
{ "_help": "Game Tweaks' settings: change them on the mod's card in Clan Mod Studio, or on its page in the mod menu (Insert).",
  "heal_key": "F5", "_help_heal_key": "A key UE4SS knows: F1 to F12, a letter, SPACE. Empty for none.",
  "time_of_day": 12.0, "_min_time_of_day": 0, "_max_time_of_day": 24 }
```
A file without them reads as before. Older versions of wcmods show a `_help_<key>` as a note at the top of the
page, and ignore the bounds.

The game's Save writes the file again, from what the script has now: the notes first, then the settings in the
order of their names, two spaces in, an empty list as `[]`, and every number as it was read (`12.0` stays
`12.0`, `0.1234567` stays `0.1234567`); the page says under the button whether it saved. The studio's Save
settings keeps the file's own order and writes back what it didn't change as it was. A key written twice counts
as the last one, as the script reads it: the card says so, and its Save writes that one only. A whole number
past 2^53 (9007199254740991) shows as the file has it and is written back so, but can't be changed on the card
(the studio's numbers would lose its last digits). The script reads the file
afresh each time the game starts, so what was saved is there next time, and a change made by hand counts once
the game starts again: a script already in the game doesn't need an Apply for it, and the studio doesn't count
it as a change to apply.
