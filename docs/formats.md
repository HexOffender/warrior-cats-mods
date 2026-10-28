# The files a mod is made of

A mod is a folder under `mods/` in your files' folder ([`wcmods.json`](#wcmodsjson) says where) with a `mod.json` (its name and what it needs; [SDK.md](SDK.md#mod-folder)
lists every key) and any of the files below. Clan Mod Studio's Make pages write them; you can also write
them by hand, and `python wcmods.py new <name> --kind <palette|controls|...>` starts one from a template.
A mod that only holds these files runs no code. The game's rules behind the numbers are in
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
Eye keys are the game's slot names (`python wcmods.py eyes`). Some names don't match the colour
(`Yellow` is green). One colour keeps the game's shading; a list is spread from pupil to rim. The
cat creator's eye buttons are recoloured to match. Coat, pattern and marking keys are slots 0–24
(0–14 natural, 15–24 bright extras); `python wcmods.py tables` lists the game's originals.

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
whisker colours it keeps in its code, and a coat slot past 24 has none, which crashes it. To give
just your cat a coat colour of its own, use `cats.json`'s `colours`.

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
cat maker's Fur picker and paints them on the cats that chose them.

#### Ready-made palettes

Ten themed palettes are in [wcmods-examples](https://github.com/HexOffender/wcmods-examples): ThunderClan Forest, RiverClan
Waters, ShadowClan Night, WindClan Moor, SkyClan Sunset, StarClan Silverpelt, Dark Forest, Leaf-bare
Frost, Pastel Kits and Vivid Clans (`palette-*`). Add the ones you want from its .zip on the Mods page,
or with `python wcmods.py add ../wcmods-examples/palette-dark-forest`. Each one recolours coats,
patterns, markings and eyes. The
natural coats are a colour grade of the game's own, so every slot keeps its place from light to dark;
the bright extras and the eyes get the theme's own colours.

To switch quickly, tick palettes under **Quick palettes** on the Palettes page and press **Apply**,
with the game closed. That turns the ticked palettes on, turns the other palette-only mods off, and
installs. If the install fails, the previous choice is put back. Mods that hold anything besides a
palette are never touched.

Pick one theme at a time; two themes together show only one of them. Eyes-only and coats-only
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
            "WindClan/Warrior/3": { "scars": "none" } } }
```
`player` is your cat, in the game you're playing. **`cats`** changes other cats in your save the same
way, each by its name (`"Duskfang"`, as it shows with your names mods) or its place as the Names page
and the Your cat page show it (`"WindClan/Warrior/3"`, for one of two cats with the same name), in the
game you're playing, or with the game's slot first for another (`"2/Duskfang"`), as `names.json`'s
`cats` picks them. Every cat called the name changes, with a warning when that's more than one. Mods
apply in priority order, so a later mod's choice wins even when it names the cat another way.
- **`colours`** go onto the cat's own materials while you play. That covers menus and the HUD's
  portrait (the cat choice's small pictures show the saved colours), and every part is optional. No other cat changes, and any colour works, including paws, ears,
  nose and whiskers, which have no slots at all. The game sets a cat's colours again whenever it
  sets the cat up, so the UE4SS script (`WCModsCatLook`) puts them back twice a second. Another cat's
  are found by its name, so they go on only in the game you're playing, and a cat with the same name
  gets them too (with a warning). A rank-up changes a cat's name (Gustpaw becomes Gust-something),
  so install again after one. Uninstalling brings the saved colours back.
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

### `data.json`
```json
{ "CombatBaseExperience.csv": { "*": { "BaseExperience": "x2" } },
  "TuningData.csv": { "Gameplay.Exploration.Player.MoveAndRun.Run.Speed": 450 } }
```
Rows are matched by their first column. `"-": ["53"]` removes rows and `"+": [{ "#": "91", ... }]`
adds them (missing columns stay empty).

### `items.json`
```json
{ "items": [ { "id": "MoonHerb", "like": "MediumHealingHerb", "name": "Moon Herb",
               "description": "Health Recovery (medium). Picked under a full moon.",
               "recipe": { "Dandelion": 2, "Cotton": 1 }, "give": 3 } ] }
```
New herbs, materials and accessory looks: a name, a description and an icon in the inventory, what
the herb does (one of the game's herb effects), a recipe at the medicine cat's bartering, and some
to start with. `like` borrows the rest from a game item, and `"recipes"` changes what the game's own
herbs and accessories cost. An icon or a look can be a PNG of the mod's own or one of the game's
recoloured (`{"tint": "#a8c4ff"}`, made from your game files at install); `python wcmods.py texture
<item or accessory>` saves the game's as a PNG to paint over. A new look can also have a shape of its
own, `"model": "models/my-collar.glb"`: an OBJ or glTF file made in Blender or the like, in metres
around the cat that `python wcmods.py model <accessory>` saves to start from; it follows the cat's
body and needs the script loader (UE4SS) in the game. `"place"` moves, turns and scales that shape (or
the accessory's own) where it sits on the cat, and `"opacity"` below 1 makes it see-through glass of the
`"glass"` colour. New looks work for neck, body and paw accessories, not head ones. A herb's or a
material's `"model"` (with a `"texture"` PNG and a `"place"`) is how it lies on the ground when a script
drops it for the cat to pick up; without one it lies there as the game's pickup of the herb it's
`like`. Every key is in [SDK.md, New items](SDK.md#new-items-itemsjson).

### `animations.json`
```json
{ "animations": [ { "id": "Wave", "name": "Wave", "file": "animations/wave.glb", "emote": true, "key": "F6" },
                  { "id": "Spin", "name": "Spin", "file": "animations/spin.glb", "for": "mouse", "loop": true } ] }
```
Animations of the mod's own, made in Blender and saved as glTF (`.glb`), for cats or one kind of animal
(`"for"`: mouse, rat, rabbit, squirrel, bird, fox, badger, dog, snake). A cat's can be an emote: a button
on the mod menu's Emotes page, and a key. Scripts play any of them (`Game.anims.play`). `python wcmods.py
animation <kind>` saves the animal rigged to the game's skeleton to animate. They play over what the
animal is doing, where it stands, and need the script loader (UE4SS). One with `"replaces":
"A_CatMaster_Trot_1"` (one of the game's sequences) plays in that one's place instead, for every cat or
every animal of the kind, fitted to its length. Every key is in
[SDK.md, Animations](SDK.md#animations-animationsjson).

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
sandbox cat, so a mod with them needs it (`"requires": ["sandbox"]`, which the studio adds).
- `id`: small letters, digits and dashes; quests name the cat by it. `name` and `title` (smaller, above
  the name) show over its head.
- `colours`: any of `fur`, `pattern`, `markings`, `nose`, `paws`, `whiskers`, `ears`; the rest are the
  game's. `eyes` is an iris colour slot (0 to 24), `size` the cat's size (0.3 to 1.5; the game's are about
  0.4 to 1.1). Left out, it's 0.85, a grown cat, as the Characters page shows it.
- Its look: with no `look` or `slots`, the game makes it up each time the cat appears, as it does for its
  own clan cats (its shape, pattern and colour slots; `colours` go on top). `look` fixes the shape, as
  `cats.json`'s does: `body`, `fur`, `tail`, `ears`, `eyes` (their shape), `whiskers` and `face` each one
  of the game's 10 (0–9), `pattern` and `marking` one of its 21 (0–20). `slots` fixes the colour slots it
  wears: `fur` 0–24 (its nose, paws, ears and whiskers go with it), `pattern` and `marking` any slot,
  including new ones a palette adds. A part left out of both (and the eye colour, without `eyes`) is
  made up again each time it appears. The Characters page's **Fixed** look fills in all of them at
  random, to keep or change.
- Where it stands: with no `at`, beside the sandbox cat the first time it comes into the forest, and there
  for that cat after. `"at": [x, y, z]` (cm, with `yaw` in degrees and `level`) puts it in one place for
  every cat; the studio fills it in from where your cat stands.
- `lines`: what it says when you talk to it (G, or the d-pad's up) and no quest wants it.

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
Questlines with the mod's own cats, made on the Questlines page, run by Sandbox mode.
- A quest starts once the quests in `after` (this mod's) are done, at once with none. `giver` is one of
  the mod's cats: a talk step with no `npc` is with them.
- Its `steps` go in order. `talk`: the cat says its `lines`, and the step is done after the last.
  `collect`: pick up `count` of `item` (its whole tag; a mod's own item is
  `Gameplay.Inventory.Consumable.<id>` or `...Materials.<id>`) from the step's start. `visit`: go within
  `radius` cm (400) of `at`, or of the nearest `place` (`medicine-cat`).
- `objective` is what the quest panel says for a step (the studio writes one when it's left empty).
- `reward`: items dropped at the cat's paws when the last step is done.
- How far each sandbox cat has got is kept in `sandbox-story.json` beside the game's saves.

wcmods checks both files at install and puts every enabled mod's together into one UE4SS mod,
`WCModsStory`, which shares them as JSON text in the UE4SS shared variable `WCMods.story`
(`{"format": 1, "mods": [{"id", "name", "npcs", "quests"}]}`), for any script to read.

### Mod packs
```json
{ "name": "The Moonlit Path", "description": "...", "version": "1.0", "author": "...",
  "pack": true, "requires": ["moonlit-cats", "moonlit-palette"] }
```
A mod pack is a mod.json and nothing else: a set of mods that go together as one experience. Its mods
are its `"requires"`, so turning it on turns them on. Its .zip (Save as .zip, or `wcmods pack`) carries
every mod in it. Clan Mod Studio's Mod packs page makes them, plays one on its own (every other mod
off, but Menu pages) and goes back to your own mods (`"pack_before"` in `wcmods.json` remembers them).

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
page and the commands print it, and Get set up finds the game again.

| Key | What it is |
|---|---|
| `game_dir` | The game's folder (the one with `Wrc` in it). Found through Steam; set it when it isn't, or Get set up asks for it. When it isn't the copy Steam starts, builds, `status` and Play say so, and the Mods page offers to switch |
| `save_dir` | Where the game keeps its saves, when it isn't `%LOCALAPPDATA%\Wrc\Saved\SaveGames` |
| `oodle_dll` | An `oo2core_*_win64.dll` from another installed game, for faster decoding of the game's files (wcmods decodes them itself without one) |
| `allow_code_mods` | `true` lets mods that carry code run it (build steps, in-game scripts, studio pages, C++): only for mods from people you trust. Options on the Settings and repair page |
| `allow_outdated` | `{ "<mod>": [<build>, ...] }`: mods used anyway on game builds they weren't made for ("Use it anyway", `wcmods allow-outdated`) |
| `pack_before` | `{ "pack": "<pack>", "on": ["<mod>", ...] }`: while a mod pack is played on its own, the mods that were on before it (the Mod packs page's Back to my mods) |
| `console` | Whether the game's `~` console (UE4SS's console enabler) is on |
| `debug_cat_look` | `true` makes your cat's colours script log every cat it sees |
| `installed`, `installed_ue4ss`, `installed_ue4ss_shared` | What the last install put in the game: the mods, when they were built, the game build, the mods folder they came from, the UE4SS mods and shared modules. The studio compares them with your mods; leave them alone |
| `menu_key`, `menu_pad`, `menu_scale` | The mod menu's key (`INS`, `HOME`, `END`, `DEL`, `PAGE_UP`, `PAGE_DOWN`, `F1`-`F12` but F11), the controller button that opens it too (an Unreal key name, `""` for none) and its size (0.6 to 2.2). Options on the Settings and repair page; an install puts them in the game ([SDK.md, `WCModsMenu`](SDK.md#wcmodsmenu)) |
| `skip_menu_pages` | `true` once Get set up was told "Not now" for the Menu pages mod |
| `cheats` | From when the mod menu was a mod of its own: whether its cheats started on. Adding the Menu pages mod takes it into that mod's `settings.json` |

The file starts with a `_help` line saying the same.

### `save.json`
```json
{ "set": { "0/GameplayProgression/Level": 5 },
  "add": { "0/GameplayProgression/State/Inventory": { "Gameplay.Inventory.Consumable.SmallCatnip": 5 } } }
```
