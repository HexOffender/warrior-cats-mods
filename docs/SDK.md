# wcmods SDK

For mod makers who write code. A mod made of JSON files alone needs none of this: those files are in
[formats.md](formats.md), and Clan Mod Studio writes them. If your mod is Lua that runs in the game,
read [scripting.md](scripting.md) first; this page then has the mod folder and `mod.json`, Python build
steps and studio pages, repacking and new content, the shared Lua modules a script can draw and find
things with, and C++ mods. [docs/README.md](README.md) lists every page.

The mod manager is built from **sections**. Each section handles one kind of mod content: the eleven
built-in ones are replacement files, game data, new items, names, palettes, your cat's colours,
controls, mouse look, save edits, in-game scripts and C++ mods. A mod can add code of its own in four
places:

| Part | File in the mod folder | Runs in | Built on |
|---|---|---|---|
| Build step | `section.py` | `wcmods build` / `install` | `wcmods.sdk` (Python) |
| Studio page | `studio/section.js` | `wcmods studio`, in your browser | `studio/lib/wc.js` |
| In-game script | `scripts/main.lua` (no Python), or written by its `section.py` | the game, through UE4SS | UE4SS Lua, plus the six shared modules below: `WCModsGame`, `WCModsDraw`, `WCModsMenu`, `WCModsView`, `WCModsWorld`, `WCModsNames` |
| C++ mod | `cpp/` (source), built into `dlls/main.dll` | the game, through UE4SS | UE4SS's C++ API, plus `WCMods.hpp` (see [C++ mods](#c-mods)) |

All of them only run when `"allow_code_mods": true` is set in `wcmods.json`, because they are
code. Without it, the build warns and skips them. Everything else in the mod still works.

**Scripting the game itself** (your cat, items, the fresh-kill pile, time of day, quests, fights,
events, hooks, the inspector and the live console) is in [scripting.md](scripting.md).

What we know about the game's insides (classes, offsets, how traits, colours and the camera work)
is in [reverse-engineering.md](reverse-engineering.md). How the game's rules work (combat,
progression, items, quests and more), and which table rows to change, is in
[mechanics/](mechanics/README.md).

The example mods are in their own repository, [wcmods-examples](https://github.com/HexOffender/wcmods-examples). Three complete
ones:
- [game-tweaks](https://github.com/HexOffender/wcmods-examples/tree/main/game-tweaks): an in-game script with its settings and a
  mod menu page, and no Python.
- [faster-run](https://github.com/HexOffender/wcmods-examples/tree/main/faster-run): a build step and a studio page.
- [quest-markers](https://github.com/HexOffender/wcmods-examples/tree/main/quest-markers): an in-game script with a custom quest,
  markers on screen and a mod menu page.

It also has palettes, eye and coat colours, mouse look, controls and game data mods to start from. To
try one, drop the repository's .zip on the studio's Mods page and tick it (or `python wcmods.py add
../wcmods-examples/<name>`), and allow code mods for the three above.

## Mod folder

```
mods/my-mod/
  mod.json            {"name", "description", "enabled", "priority", "version", "author",
                       "requires" (mods it can't work without), "uses" (mods it works with),
                       "game_builds", "settings_page", "studio_title", "studio_files": below}
  files/Wrc/...       replacement game files            -> section "files"
  paks/<name>.pak     cooked content made with Unreal   -> installed as is, with its .utoc/.ucas
                      Engine 5.7 (see "New content")
  data.json           CSV cell edits                    -> section "data"
  items.json          new herbs, materials and looks    -> section "items" (see "New items")
  names.json          cat names                         -> section "names"
  palette.json        colour palettes                   -> section "palettes"
  cats.json           your cat's own colours and slots  -> section "cats"
  controls.json       key and button remaps             -> section "controls" (checked at build;
                                                           applied by `wcmods play`, keyboard and mouse)
  mouselook.json      mouse look settings               -> section "mouselook"
  save.json           save edits                        -> section "save"
  scripts/main.lua    an in-game Lua script (code mod)  -> section "scripts" (docs/scripting.md)
  settings.json       that script's settings            (MOD.settings; a mod menu page edits them),
                      or the C++ mod's (wcmods::settings())
  cpp/                a C++ mod's source (code mod)     -> built by `wcmods cpp build` (see "C++ mods")
  dlls/main.dll       the C++ mod it builds             -> section "cpp"
  section.py          your own build step               (code mod)
  studio/section.js   your own studio page              (code mod)
```

Only `mod.json`'s `name` is needed; the rest is what Clan Mod Studio shows and how the mod fits with others:

- **`requires`:** the mods it can't work without, by folder name. Turning it on turns them on.
  While one is missing or off, building leaves this mod out and says why (installing stops, as for
  any mod that didn't build, unless `--force`).
- **`uses`:** mods it works with when they're on. `mod-menu` means the mod menu, for a page in it:
  that's wcmods' own, so it's always there (in `requires` too). Nothing is turned on for them; the
  studio just shows it.
- **`game_builds`:** the builds of the game it was made for (a mod without it was made for
  24847281). After a game update, a mod that doesn't list the new build is left out until it's
  updated, or you choose "Use it anyway" for that build. See [updating.md](updating.md).
- **`priority`:** mods are applied in priority order, then by folder name, and the higher one wins
  when two set the same thing.
- **`settings_page`:** for a script mod with a `settings.json`: `false` keeps it off the mod menu's
  Mods group (it gets a page there by default; [scripting.md](scripting.md#script-mods)).
- **`studio_title`** and **`studio_files`:** for a mod with a `studio/section.js` page: the side bar's
  label, and the files its page edits.

A mod without code is just these files ([formats.md](formats.md)); mods with code (a `section.py`,
`scripts/`, a `studio/` page, `cpp/`) stay out of the game until the player allows mods that run code.

## Python: `wcmods.sdk`

```python
from wcmods.sdk import Section

class MySection(Section):
    id = "my-section"          # unique; shown in build reports
    title = "My section"
    files = ("my-settings.json",)   # the section runs for mods that have any of these

    def collect(self, mod, ctx):
        # Read and validate this mod's files. Raise ValueError for mistakes the user
        # should fix: the build reports it and skips just this mod.
        return self.read_json(mod, "my-settings.json")

    def build(self, ctx, items):
        # items: [(mod, data)] for every enabled mod, lowest priority first.
        ...
```

Sections run independently. If `build` raises, everything that section added is rolled back,
the build report marks it FAILED, and the other sections carry on.

### BuildContext

| Call | Does |
|---|---|
| `ctx.read_game_file(path)` | Bytes of any game file (pak or IoStore, Oodle handled), e.g. `"Wrc/Config/DefaultGame.ini"` |
| `ctx.read_data_table("TuningData.csv")` | Text of a runtime CSV under `Gameplay/DataTables/NonAsset/` |
| `ctx.table("AttackMove.csv")` | That table's rows as dicts (column -> text, plus `"key"`), as the game ships them |
| `ctx.tuning(key)` / `ctx.tuning()` | A `TuningData.csv` value as a number, or all of them |
| `ctx.tune({key: value}, source=mod.id)` | Change `TuningData` values (numbers or `"x1.5"`), merged with other mods' edits; warns about keys the table doesn't have |
| `ctx.text("STR_ATTACK_QUICK_CLAW")` | A line of the game's English text (or `language="FR"`, …) |
| `ctx.edit_csv(name, edits, source=mod.id)` | Queue cell edits (and row removals `"-"` / additions `"+"`, see `csvdata.py`); they merge with every other section's edits to the same table |
| `ctx.add_file(path, data, source=mod.id)` | Add or replace a loose file in the mod pak |
| `ctx.patch_package(path, data)` | Replace a cooked `.uasset` with patched bytes (goes into the IoStore mod container) |
| `ctx.cooked_table("DT_QuestObjectsInfo")` | The rows of a cooked table wcmods can read (`cooked.TABLES`), as `[(row name, {field: value})]`, as the game ships them |
| `ctx.add_table_row(table, row, values, source=mod.id)` | Add a row to one of those tables; rows from every section are merged and written into a copy of the game's asset (fields in `cooked.SCHEMAS`; text as `cooked.base_text("Moon Herb", key)`) |
| `ctx.add_texture(name, image, like, source=mod.id, key=None)` | A new texture `/Game/WCMods/<name>`, a copy of the game's texture `like` (same size, format and mips) with the pixels of `image`: `(width, height, RGBA bytes)` as `png.read` gives, or a function that makes them. With `key` (text that changes when the picture does), an install reuses the texture it made last time. Returns the new asset path, for an icon or a look |
| `ctx.add_package(path, data, chunk_id, imports, shaders, bulk=None)` | Add a cooked package the game hasn't got, with its chunk ID, container header entry and `.ubulk`; `add_texture` is the easy way |
| `ctx.cache_dir` | A folder for work an install can reuse (wcmods' `cache/`; the selftest's stays in its temp folder) |
| `ctx.add_ue4ss_mod(name, {"Scripts/main.lua": text})` | Ship a UE4SS Lua mod; installed and registered only when UE4SS is present. `.lua` files get a structure check (balanced blocks and brackets) and problems become build warnings |
| `ctx.edit_save(path, value)` | Set an existing save value on install, e.g. `"0/GameplayProgression/Level"` |
| `ctx.add_save_key(object_path, key, value, only_new=False)` | Add a key to a save object, e.g. a new inventory item. With `only_new`, a key the save already has keeps its value |
| `ctx.warn(msg)` / `ctx.log(msg)` / `ctx.note(key, value)` | Report to the user / the build log / the build manifest (notes show on the mod menu's first page) |
| `ctx.game`, `ctx.cfg`, `ctx.mods` | The game reader (`find`, `exists`, `data_tables`), the tool's configuration, and the enabled mods |

CSV edits use `{row: {column: value}}`. `"*"` means every row, `"x1.5"` multiplies the game's
number, and key/value tables like `TuningData.csv` accept `{row: value}`. Save paths use `/`,
because the game's keys contain dots. They start inside the save's account object: `Shared/...`
for shared data, and `0/...` for cat slot 0.

Helpers you can import: `wcmods.csvdata` (format-preserving CSV editing), `wcmods.savejson`
(format-preserving save JSON), `wcmods.cooked` (cooked DataTables), `wcmods.texture` (the game's
textures, read and copied), `wcmods.png`, `wcmods.bcn` (DXT1/DXT5) (those six live under
`wcmods/formats/` and keep these names too), `wcmods.recolor`,
`wcmods.accessories` (the game's lists of accessory looks), `wcmods.colors`, `wcmods.palettes`,
`wcmods.eyeatlas`, `wcmods.gamefiles`, `wcmods.names` (the game's name tables). `wcmods.sdk.lua_value(data)` writes
JSON-style data (dicts, lists, strings, numbers, booleans) as a Lua literal, for handing a mod's
settings to its in-game script.

## Game files, repacking and new content

### Where the game keeps its files

Everything is in `<game>\Wrc\Content\Paks\`:

| File | Holds |
|---|---|
| `pakchunk0-Windows.pak` | Loose files that aren't cooked assets: the data tables (`Gameplay/DataTables/NonAsset/*.csv`), the text tables (`Strings_EN.csv` and the other languages), configs (`.ini`), the UI's images and the movies. Pak version 12, Oodle-compressed |
| `pakchunk0-Windows.utoc` / `.ucas` | An IoStore container with every cooked asset (`.uasset` / `.ubulk`): models, textures, materials, animations, Blueprints, sounds and levels. The `.utoc` lists 12-byte chunk IDs and where each sits in the `.ucas`, which is stored in 64 KB Oodle blocks; its container header records each package's imports and shader maps |
| `global.utoc` / `.ucas` | The engine's script objects and global shaders |

`python wcmods.py files "<pattern>"` lists what's in them (`"*NPC/*.csv"`, `"*SK_*"`), and
`extract "<pattern>"` copies matches into `vanilla/`. Tables and text come out as plain files.
Cooked assets come out as their raw bytes; a viewer such as FModel shows what's inside.

### What wcmods builds (repacking)

Each install writes fresh files into `Paks\~mods\`. The game mounts that folder after its own
paks, and the `_P` (patch) suffix lets a file there override the game's. The game's own files are
never changed, and uninstall deletes everything starting with `zzz_WCMods_`.

| File | What wcmods puts in it |
|---|---|
| `zzz_WCMods_P.pak` | Every replacement loose file (`files/`) and every edited table and text file (`data.json`, `names.json`, section CSV edits, merged across mods), plus `Wrc/WCMods/BuildInfo.json` naming the mods built. Pak version 12, uncompressed, mount point `../../../`. File names in its directory index are UTF-8 with no terminator, as the game's own pak stores them; written the older way, the engine never finds them |
| `zzz_WCMods_P.utoc` / `.ucas` | Patched copies of existing cooked packages (the eye colour atlas, the item table, and anything a section passes to `ctx.patch_package`). Each keeps the game's chunk ID and its container header entry (imports, shader maps), with BLAKE3-160 chunk hashes, so the engine loads ours instead of the game's. New packages (`ctx.add_texture`) go in beside them under `/Game/WCMods/`, with chunk IDs worked out from their names the way the engine does |
| `zzz_WCMods_<mod>_<name>_P.*` | Cooked content a mod ships itself (`paks/`, below), copied as it is |

Next to these, UE4SS scripts go into `Binaries\Win64\ue4ss\Mods\WCMods*`, and the shared modules
into `ue4ss\Mods\shared\WCMods*`.

### Changing what the game already has

- **Tables and text:** `data.json` and `names.json` edit cells and rows, merged with other mods'
  edits to the same table. From a `section.py`, use `ctx.edit_csv`.
- **Whole loose files** (a config, a movie, a table rewritten by hand): extract it, change it, and
  put it in the mod at the same path under `files/`, e.g. `files/Wrc/Content/.../TuningData.csv`.
- **Bytes of a cooked asset:** `ctx.patch_package(path, data)` replaces a package with patched
  bytes, such as new pixels in a texture. That's how eye palettes recolour the eye atlas.
- **Rows of a cooked table:** some tables are cooked assets rather than CSVs, such as
  `DT_QuestObjectsInfo` (every item's name, description and icon). `ctx.add_table_row` adds rows to
  them, written into a copy of the game's own asset at install. `items.json` (below) uses it.
- **While the game runs:** UE4SS scripts change objects in memory: colours, the camera, cheats.

### New items (`items.json`)

A mod can add herbs, materials and new looks for the game's accessories, with icons of its own,
and change the recipes of the game's herbs and accessories. wcmods writes everything the game needs
for a new item:
- the item's gameplay tag;
- its row in the cooked item table, `DT_QuestObjectsInfo`: name, description and icon (the inventory
  leaves out an item without one);
- for a herb, what using it does (`Consumables.csv`), and for a herb or an accessory, a recipe at
  the medicine cat's bartering (`BarteringCost.csv`);
- a new icon or look as a texture of its own;
- and some in your save to start with.

```json
{
  "items": [
    {
      "id": "MoonHerb",
      "like": "MediumHealingHerb",
      "name": "Moon Herb",
      "description": "Health Recovery (medium). Picked under a full moon.",
      "rarity": "Uncommon",
      "recipe": { "Dandelion": 2, "Moonstone": 1 },
      "give": 3
    },
    {
      "id": "Moonstone",
      "kind": "material",
      "name": "Moonstone",
      "description": "A pale stone that glows at night.",
      "icon": { "from": "Rock", "tint": "#c4d4ff" },
      "give": 2
    },
    {
      "id": "MoonlitCollar",
      "like": "Neck.DogCollar.1",
      "name": "Moonlit Collar",
      "description": "A collar the colour of moonlight on water.",
      "texture": { "tint": "#a8c4ff" },
      "icon": { "tint": "#a8c4ff" },
      "recipe": { "Bone": 1, "Moonstone": 2 }
    }
  ],
  "recipes": {
    "Cosmetic.Head.MossPatch.1": { "Moss": 3, "Ivy": 1, "Moonstone": 1 }
  }
}
```

| Key | |
|---|---|
| `id` | Letters and digits. The item's tag is `Gameplay.Inventory.Consumable.<id>` for a herb or `Gameplay.Inventory.Materials.<id>`, and an accessory's is its accessory's next look (below). It can't be one the game or another mod already has; the build says if it is |
| `name`, `description` | What the inventory and bartering show, the same in every language |
| `like` | A game item to start from, by its short name (`"MediumHealingHerb"`) or whole tag: its kind, effect, when it can be used, icon, icon group, rarity and colour. An accessory's is the look it's a copy of, `"Neck.DogCollar.1"`. The item's other keys override those |
| `kind` | `"consumable"` (a herb or pouch), `"material"` or `"accessory"`, when there's no `like` |
| `icon` | An item to borrow the icon of (`"Rock"`), a texture of the game's, e.g. `"/Game/Art/UXD/Textures/gui_icons/gui_icons_inventory/T_UI_Icon_Flower_Marigold_D"` (`wcmods files "*gui_icons_inventory*"` lists them), a PNG in the mod's folder (`"icons/moon-herb.png"`), or a recolour (below) |
| `texture` | Accessories: the new look, a recolour of the one it's `like` (`{"tint": "#a8c4ff"}`) or a PNG in the mod's folder |
| `effect` | Herbs: what using one does, one of the game's herb effects, such as `Gameplay.Effect.Consumable.Health.2` (+50 health). [items.md](mechanics/items.md) lists them |
| `type`, `target` | Herbs: the effect's kind (`Health`, `Stamina`, `BuffStrength`, …), and who it's for: `Owner`, or `OwnerTeam` for your whole team |
| `combat`, `exploring`, `fight_only` | Herbs: `true` or `false` for usable in fights, usable while exploring, and whether its effect ends with the fight |
| `group`, `rarity`, `color` | The badge by its icon (`Health`, `Stamina`, `Stats`, `Status`, `Damage`, `Experience`, `Free`, or `None`), the rarity (`Common`, `Uncommon`, `Rare`, `Mythic`, `None`) and the category colour (`Consumable`, `Quest`, `Den`, `None`) |
| `recipe` | Herbs and accessories: what the medicine cat wants for one, e.g. `{"Dandelion": 2, "Moonstone": 1}`. Any material, the game's or one a mod adds |
| `give` | How many you start with: given once, in the save slot you play, if you have none yet |

`"recipes"` changes what the medicine cat wants for one of the game's herbs or accessories, by its
tag with or without `Gameplay.Inventory.`. Accessories are
`Cosmetic.<Head|Neck|Body|Legs>.<name>.<variation>`, e.g. `Cosmetic.Neck.DogCollar.2` (`wcmods
extract "*BarteringCost.csv"` shows them all). The ingredients are as for an item's `recipe`, new
materials included.

**Pictures.** An icon or a look can be the mod's own picture or one of the game's in other colours.
Either way wcmods makes it into a texture at install: a copy of one of the game's (the same size,
format and mips) under `/Game/WCMods/<mod>/`, with new pixels. A recolour is made from your own game
files, so a mod ships no picture of the game's:

| Recolour key | |
|---|---|
| `from` | Icons: which picture to recolour, an item (`"Rock"`) or a texture (`"/Game/..."`). Left out, it's the icon of the item it's `like`. An accessory's `texture` always recolours its own look |
| `tint` | `"#a8c4ff"`: the picture's light and shade in that colour |
| `strength` | With `tint`, from 0 to 1: how far toward it (1 is all the way) |
| `hue` | Degrees to turn its colours round the colour wheel, e.g. `180` |
| `saturation`, `brightness` | Multipliers: `0.5` is half as colourful, `1.2` a fifth lighter |

For a picture of your own, `python wcmods.py texture <what>` saves one of the game's as a PNG to
paint over: an item's icon (`SmallHealingHerb`), an accessory's look (`Neck.DogCollar.1`) or any
texture (`/Game/...`). Keep the size, or wcmods scales it; inventory icons are 512 x 512 with a
transparent background, accessories' icons 256 x 256 and their looks 2048 x 2048. Making a big look
takes about 15 seconds the first time; installs after that reuse it from `cache/`.

**Accessories.** An accessory is one of the game's models with a list of looks (textures): the Red
Dog Collar is DogCollar's look 2. A new accessory is a new look for one of them, so its tag is the
next one, `Gameplay.Inventory.Cosmetic.Neck.DogCollar.3`, and wcmods adds its texture to the game's
list. Neck, body and paw accessories can take new looks; the game always shows a head accessory's
first look, so those can't. The number depends on the other enabled mods that add looks to the same
accessory, so switching one of those on or off can change which look an accessory you already have
is. Bartering shows accessories you already have as an empty slot, the game's and a mod's alike.

What it can't do (yet):
- **New effects:** each herb effect is one of the game's Blueprints, so a new herb does what one of
  the game's does (heal 25, 50 or 100, stamina, a stat buff, a cure, experience).
- **New accessory models:** a new shape to wear needs a model cooked with Unreal (see "New
  content"), and new looks for head accessories don't show. `"recipes"` can change what an existing
  one costs.
- **Growing in the world:** new materials aren't found in the forest; they come from `give`, a
  recipe or a script.

### New content: models, textures, sounds

New models, sounds and Blueprints have to be cooked by Unreal Engine itself; wcmods only makes
textures, as copies of the game's (`items.json` and `ctx.add_texture`, above). Once cooked, a mod
ships them in a `paks/` folder and wcmods installs them like everything else. The steps are the
usual ones for Unreal 5 games that use IoStore. **They haven't been tried with this game yet.** The
game doesn't insist on signed paks, though (wcmods' own unsigned container loads), which is what
makes this possible.

1. **Use the game's engine version:** Unreal Engine 5.7. Make a project named `Wrc`, so its content
   mounts at `/Game` the same way the game's does.
2. **Keep your assets in a folder of your own**, e.g. `/Game/Mods/MyHat/`, so nothing clashes with
   the game's.
3. **Set Project Settings → Packaging:**
   - turn on *Use Io Store* and *Use Pak File*;
   - turn off *Share Material Shader Code*, so your materials' shaders travel inside your packages
     instead of a shader library that would clash with the game's;
   - turn on *Generate Chunks*, and give your folder a chunk of its own with a Primary Asset Label
     (chunk 100, say).
4. **Package for Windows.** From the output, take `pakchunk100-Windows.pak`, `.utoc` and `.ucas`
   and put all three in `mods/<your mod>/paks/`. Install, and they go into `~mods` as
   `zzz_WCMods_<your mod>_pakchunk100-Windows_P.*`. A `.utoc` and `.ucas` need the `.pak` of the
   same name beside them, or the game won't mount them.
5. **Make the game use it**, in one of two ways:
   - **Replace one of the game's assets:** give yours exactly the same path and name; find them with
     `wcmods files "*SK_*"` or FModel. For a skeletal model, keep the game's skeleton (its
     animations are tied to it) and the same material slots.
   - **Add something new:** load it from a UE4SS script and put it in the world. For example, a hat
     on your cat:

```lua
-- A sketch: a hat from a mod's own cooked paks, on your cat. "head" must be a socket or bone of
-- the cat's skeleton (FModel shows their names).
local World = require("WCModsWorld")
local MeshComponent = StaticFindObject("/Script/Engine.StaticMeshComponent")
local SNAP = 2   -- EAttachmentRule::SnapToTarget
local hat, wornBy

LoopInGameThreadAfterFrames(30, function()   -- about twice a second, on the game thread
    pcall(function()
        local cat = World.player()
        if not cat or wornBy == cat:GetAddress() then return end
        hat = hat or LoadAsset("/Game/Mods/MyHat/SM_Hat.SM_Hat")
        local part = cat:AddComponentByClass(MeshComponent, true,
            { Rotation = { X = 0, Y = 0, Z = 0, W = 1 }, Translation = { X = 0, Y = 0, Z = 0 },
              Scale3D = { X = 1, Y = 1, Z = 1 } }, false)
        part:SetStaticMesh(hat)
        part:K2_AttachToComponent(cat.Mesh, FName("head"), SNAP, SNAP, SNAP, false)
        wornBy = cat:GetAddress()   -- a new area brings a new cat, which gets a new hat
    end)
end)
```

The same way, a script can spawn actors from a mod's own Blueprints (load the class, then
`GameplayStatics:BeginDeferredActorSpawnFromClass` and `FinishSpawningActor`), play its sounds, or
show its textures with the menu's `ui.image` and `WCModsDraw`'s `texture` option.

## In-game scripts

The simplest in-game script is a mod's `scripts/main.lua`, with no Python at all
([scripting.md](scripting.md#script-mods)). A mod's `section.py` can also ship a UE4SS Lua script with
`ctx.add_ue4ss_mod`, for scripts written from the mod's settings at build time. wcmods installs either
into `ue4ss/Mods/<name>/` when UE4SS is present, registers it, and removes it on uninstall or when the
mod is turned off. Next to it, every install puts six shared modules in `ue4ss/Mods/shared/`. Any
UE4SS script can `require` them, wcmods' or one written by hand:

| Module | What it does |
|---|---|
| `WCModsGame` | The game itself: your cat's health, stamina, level and stats, items, the fresh-kill pile, time of day, quests, fights, the save, the game's managers and developer switches; timers, keys, events and hooks. See [scripting.md](scripting.md) |
| `WCModsDraw` | Text and 2D shapes on screen: panels, buttons, debug text, markers on places in the world |
| `WCModsMenu` | Pages in the mod menu (Insert): buttons, switches, sliders, drop-downs, text boxes, colours, images |
| `WCModsView` | What the camera sees: its matrices, and world-to-screen positions |
| `WCModsWorld` | Finds things in the world (pickups, interactables, quest objectives, cats, creatures) and the game's managers |
| `WCModsNames` | Cats' names: every name part's text after your name mods, and `name(prefix id, suffix id)`, which falls back on the game's own text; items', areas' and quests' names: `item(tag)`, `area(code)` (`"R-05"` is `"Willow-Weep"`), `quest(tag, rank)` (a quest's title for a rank: `"Apprentice"`, `"Warrior"`, `"Deputy"` or `"Leader"`, or another rank's). Written on each install from the game's tables; `WCModsGame` and `WCModsWorld` use it |

### Shipping a script

The script is a template in the mod folder. The build step fills in the mod's settings, and the
path the menu page saves them back to:

```python
# mods/my-overlay/section.py
import os
from wcmods.sdk import Section, lua_value

class MyOverlay(Section):
    id = "my-overlay"
    title = "My overlay"
    files = ("my-overlay.json",)

    def collect(self, mod, ctx):
        return self.read_json(mod, "my-overlay.json")

    def build(self, ctx, items):
        mod, settings = items[-1]           # the highest-priority mod's settings
        with open(os.path.join(mod.folder, "overlay.lua"), encoding="utf-8") as f:
            script = f.read()
        path = os.path.abspath(os.path.join(mod.folder, "my-overlay.json"))
        script = script.replace("@SETTINGS@", lua_value(settings)).replace("@SAVE_PATH@", lua_value(path))
        ctx.add_ue4ss_mod("WCModsMyOverlay", {"Scripts/main.lua": script, "enabled.txt": ""})
```

```lua
-- mods/my-overlay/overlay.lua: markers on nearby pickups, and a mod menu page to change them live.
local Draw = require("WCModsDraw")
local Menu = require("WCModsMenu")
local World = require("WCModsWorld")
local SETTINGS = @SETTINGS@     -- e.g. { on = true, range = 3000, color = "#7ee081" }
local SAVE_PATH = @SAVE_PATH@

-- What's nearby, looked up twice a second rather than every frame.
local found, foundAt = {}, nil
local function nearby()
    if foundAt == nil or os.clock() - foundAt >= 0.5 then
        foundAt, found = os.clock(), World.nearby("pickups", SETTINGS.range)
    end
    return found
end

Draw.onFrame(function(d)
    if not SETTINGS.on then return end
    for i, it in ipairs(nearby()) do
        if i > 10 then break end
        d.marker(it.location, it.label, { color = SETTINGS.color, edge = true })
    end
end)

Menu.page("My overlay", function(ui)
    ui.heading("My overlay")
    SETTINGS.on = ui.switch("Markers", SETTINGS.on)
    SETTINGS.range = ui.slider("Range", SETTINGS.range, 500, 10000, { step = 500, format = "%.0f cm" })
    SETTINGS.color = ui.color("Colour", SETTINGS.color)
    if ui.button("Save", { kind = "primary" }) then Menu.saveJson(SAVE_PATH, SETTINGS) end
end)

print("[MyOverlay] loaded\n")
```

Changes on the page apply at once, because the page and the markers share `SETTINGS`. Save writes
them to the mod's JSON, so the next install builds the script with them. `print` goes to
`ue4ss\UE4SS.log`; end each line with `\n`.

Name the script anything. Names starting with `WCMods` are wcmods' own: an install also clears
out any `WCMods...` script that no enabled mod ships any more, even if wcmods.json lost track of it.

### Rules that keep the game running

- **One thread per script.** The shared modules run on the game thread
  (`LoopInGameThreadAfterFrames`). In a script that uses them, don't also use `LoopAsync`: it runs
  its callback on another thread in the same Lua state, and two threads in one Lua state at once
  crash the game. For something every so often, count time in a painter or a menu page.
  `RegisterKeyBind` is fine; do the work inside `ExecuteInGameThread`.
- **Objects last a level.** When the level changes, the game destroys its actors and widgets, and a
  destroyed object's slot can be taken by another object. Such an object can still look valid while
  being something else. Look things up again (the shared modules do this themselves), and check
  the class of anything you keep: `o:GetClass():GetFName():ToString()`.
- **Guard engine calls with `pcall`.** An error inside a callback that UE4SS calls itself (a hook,
  or a `ForEach`) goes to UE4SS's log, not to the `pcall` around the code that set it up, so guard
  the callback's own body too.
- **Rotators:** UE4SS drops the pitch of a rotator passed as a Lua table, so build ones that need
  a pitch with `KismetMathLibrary:MakeRotator(roll, pitch, yaw)`.
- **Input:** leave the input mode alone while the mod menu is open
  (`ModRef:GetSharedVariable("WCModsMenu.open")`), as mouse look does.

## `WCModsDraw`

```lua
local Draw = require("WCModsDraw")

Draw.onFrame(function(d)
    local y = d.panel(20, 20, 260, 90, "Debug")        -- returns where the content starts
    d.text(32, y, "Hello", { size = 16, color = "#ffe9a8" })
    if d.button(32, y + 28, 120, 26, "Do it") then print("clicked\n") end
    d.line(300, 40, 420, 90, { color = "#ff6060", thickness = 3 })
    d.marker(someLocation, "The old oak", { sub = "Find the herbs", edge = true })
end)
```

The painter runs every frame on the game thread. Whatever a frame doesn't draw is hidden, so a
painter just draws what should be on screen now. Positions and sizes are pixels from the
viewport's top left, the same as `WCModsView`. Colours are `"#rrggbb"`, `"#rrggbbaa"` or
`{r, g, b, a}` from 0 to 1, in sRGB like an image editor's.

| Call | Draws |
|---|---|
| `d.text(x, y, text, {size, color, align, valign, shadow})` | Text; `size` in pixels (16), `align` left/center/right and `valign` top/middle/bottom place it against x, y. Multi-line with `\n` |
| `d.rect(x, y, w, h, {color, outline, angle, texture})` | A filled rectangle, or an outline `outline` pixels thick. `angle` turns it around its middle; `texture` is a texture object or its path |
| `d.line(x1, y1, x2, y2, {color, thickness})` | A line |
| `d.polyline(points, {color, thickness, closed})` | Lines through `{{x, y}, ...}` |
| `d.circle(x, y, radius, {color, thickness, segments})` | A circle's outline |
| `d.panel(x, y, w, h, title?, {color, border, titleColor})` | A dark panel with a title bar; returns the y where its content starts |
| `d.button(x, y, w, h, label, {color, hoverColor, border, size})` | A button; returns true the frame it's clicked |
| `d.marker(location, label?, {sub, color, size, textSize, edge, maxDistance, distance, from})` | A diamond on a place in the world, its label above, and its distance (and `sub`) below. With `edge`, a place off screen or behind the camera shows at the screen's edge, in its direction. Returns the screen x, y, or nil |
| `d.measure(text, size)` | About how wide and tall text would be, in pixels |
| `d.mouse()`, `d.hover(x, y, w, h)`, `d.clicked()` | The mouse in pixels and whether the cursor is shown; whether it's over a box; whether the left button went down this frame |
| `d.width`, `d.height`, `d.scale`, `d.view`, `d.player` | The viewport, the game's UI scale, this frame's `WCModsView` view, and your cat's location |

`Draw.remove(id)` stops a painter (`onFrame` returns its id). `Draw.setVisible(on)` and
`Draw.isVisible()` show or hide everything a script draws, e.g. on a key. `Draw.setZOrder(z)` sets
where the overlay sits among the game's UI (1000, above it, by default).

How it works: one widget on the viewport (the game's own UI system, UMG) holds a canvas of text
blocks and images, kept in pools. An element only gets a call into the game when something about it
changed. The overlay never takes clicks, so the game's UI and controls work as before; buttons
watch the player's left mouse button instead. They work while the cursor shows and the game reads
the mouse, and a click also reaches whatever game UI is under them. For menus that take clicks
properly, use `WCModsMenu`. Each script that requires the module gets its own overlay, made again
by itself after a level change.

## `WCModsMenu`

The mod menu is wcmods' own: every install with UE4SS puts in its window (`WCModsMenuHost`, with its
own pages, below) and this module, so a script can count on `require("WCModsMenu")`. Its pages about
the game are a mod of their own, **Menu pages** (below), which adds them through this module as any
mod does.
- **A mod with a page** says `"uses": ["mod-menu"]` in its `mod.json`, which the studio shows as
  "Page in the mod menu". Mouse look and script mods with a `settings.json` show it without saying so.
  (`mod-menu` was the menu's own mod when it was one; it's always there now, so it's met in
  `"requires"` too.)

The menu's settings are in `wcmods.json`, set under Options on the Settings and repair page in Clan
Mod Studio: `"menu_key"` (`INS`, `HOME`, `END`, `DEL`, `PAGE_UP`, `PAGE_DOWN` or `F1`-`F12` but F11),
`"menu_pad"` (the controller button that opens it too, as an Unreal key name: View,
`Gamepad_Special_Left`, by default and `""` for none) and `"menu_scale"` (0.6 to 2.2, 1 by default).
When the menu was a mod of its own they were in `mods/mod-menu/menu.json`; the first start after
updating moves them into `wcmods.json` and removes that folder.

Insert (or a controller's View button) opens the menu in game, and Insert or Escape closes it (View or
B too, when the controller opened it). While it's open, the menu has the keyboard and mouse, the cursor
shows, and the game's controls wait. "Pause the game" stops the game too, and A- and A+ resize it.

The menu works without a mouse too:
- **Moving:** Tab, the arrow keys or a controller's d-pad move between the controls. Tab goes round
  the window: the top bar, the side bar, then the page. Opening the menu puts focus on the page's
  tab, so Up and Down pick a page, Enter opens it and Right goes into it.
- **Using a control:** Enter, Space or A presses a button, ticks a box or opens a list. A slider
  takes Enter to grab it, Left and Right to move it, and Enter again to let go.
- **From a controller:** View (`"menu_pad"` in `wcmods.json`; Options in the studio picks another
  button, or none) opens it, and View or B closes it. The game can only hear a controller while it has
  input, so a menu opened this way leaves the game its input and pauses it instead. It doesn't open
  while something else has the game paused, such as the game's own pause menu.
- **Seeing where you are:** the control with focus has a gold ring. The page you're on, and a chosen
  option, are light with dark text, so they show without relying on colour.

Under the title, a status line says how to open and close the menu, or what a script tells it
(`Menu.status`): with Menu pages, your cat's name, level, rank, health and stamina, where it is, the
time and the fresh-kill pile. The side bar lists the pages in groups; a group shows once a page is in
it:

| Group | Pages |
|---|---|
| Home | **Overview** (the keys, the keys scripts use, and each group's pages; how to get Menu pages while the build hasn't got it), **Installed mods** (each mod and what each part of the build set up); with Menu pages, **At a glance** (your cat and the world, quick buttons) |
| Your cat | **Colours**, **Mouse look**; with Menu pages, **Stats** (health, stamina, size, level, stats) |
| World | With Menu pages: **World** (the clock, which can be held, and the fresh-kill pile), **Travel** (saved spots, checkpoints and areas, and Back), **Nearby** (what's around your cat, `WCModsWorld`), **Items** (what you carry, and an item to drop) |
| Story | With Menu pages: **Quests** (the one you follow and its objectives, with "Go to objective"; the rest by state) |
| Fight | With Menu pages: **Fight** (both sides during a fight) |
| Cheats | With Menu pages: **Cheats** (the engine's cheat manager), **Game switches** (the developers' own) |
| Mods | Pages scripts add, and a script mod's settings page |
| Tools | **Log** (UE4SS's log, newest first), **Menu** (its size, pausing, the status line), and with code mods allowed **Inspector** and **Lua console** |

### Menu pages

The pages about the game are a mod of their own, **Menu pages** (`mods/menu-pages`), from
[HexOffender/wcmods-menu-pages](https://github.com/HexOffender/wcmods-menu-pages). It's an in-game
script (`scripts/`), so it runs only with mods that run code allowed, like any script.
- **Getting it:** Get set up in Clan Mod Studio ("Add the menu's pages") downloads its latest
  release's `menu-pages-*.zip` and adds it, as `python wcmods.py menu-pages` does (`--zip file` for one
  you downloaded). Its card's "Get the latest" updates it, keeping whether it's on and its
  `settings.json` (`wcmods/menupages.py`). Its `.zip` can be added like any mod's too.
- **Its settings:** `settings.json`'s `"cheats"`, whether the Cheats page starts with cheats on (its
  "Start with cheats on" switch, or `python wcmods.py cheats on|off`).
- **After a game update:** like any mod, it lists the builds it was made for (`"game_builds"`), and a
  build leaves it out on a newer one until a release adds it, or the player chooses "Use it anyway".
- **What it uses:** only what any mod can: this module (`Menu.page`, `Menu.status`), `WCModsGame`,
  `WCModsWorld`, `WCModsDraw` and `WCModsNames` (`area`, `quest` and `item` for the game's names). Its
  saved travel spots are in `Game.save.folder()`, so they stay when it's updated.

Cheats is the engine's cheat manager, switched on and off live. It has god mode, fly and ghost, cat
size, game speed, teleport and an engine command box. Flying and size are done by the page itself,
because the game undoes the engine's own `fly`, `ghost` and `changesize`. The pages built on
`WCModsGame` are in [scripting.md, In the mod menu](scripting.md#in-the-mod-menu).

wcmods' mouse look and your cat's colours have live settings with Save, and any script can add a page
(a C++ mod too: `wcmods::menu_page` in [C++ mods](#c-mods) draws the same rows from C++):

```lua
local Menu = require("WCModsMenu")
local settings = { on = true, speed = 1, mode = "Calm", tint = "#ffcc00" }

Menu.page("My mod", function(ui)
    ui.heading("My mod")
    settings.on = ui.switch("Enabled", settings.on)
    settings.speed = ui.slider("Speed", settings.speed, 0.5, 3, { step = 0.1, format = "x%.1f" })
    settings.mode = ui.radio("Mode", settings.mode, { "Calm", "Busy" })
    settings.tint = ui.color("Tint", settings.tint)
    ui.section("More", function()
        settings.name = ui.input("Name", settings.name, { hint = "your cat's name" })
        settings.count = ui.number("Count", settings.count or 3, { min = 0, max = 10, step = 1 })
    end, { open = false })
    if ui.button("Save", { kind = "primary" }) then Menu.saveJson(SAVE_PATH, settings) end
end, { group = "mods", order = 40, id = "my-mod-settings" })
```

`id` tells the page from another mod's with the same title (without it, the title is the id; a page
whose title another mod already uses gets the title plus its mod's name).

While the menu shows a page, its function runs every frame. Each `ui` call is one row of the page,
and returns what the player set it to, or the value it was given when they didn't touch it. So one
line per setting keeps a script's live settings and the page in step. The rows are the game's own UI
widgets (real buttons, check boxes, sliders, drop-downs and text boxes, which take clicks and typing
properly), kept from frame to frame and changed only when something changes. A page whose rows
change (more items, a section opened) rebuilds from the first row that differs. Sizes are as on a
1080-pixel screen: the window undoes the game's UI shrink (it draws for 3840x2160 and scales down).

| Call | Row |
|---|---|
| `ui.heading(text)`, `ui.text(text, {size, color})`, `ui.note(text)` | A heading; wrapped text; smaller grey text |
| `ui.field(label, value, {color})` | A name and its value, for showing settings |
| `ui.columns({ {label, value, color}, ... })` | Several values side by side, each label small above its value |
| `ui.separator()`, `ui.space(h)` | A line; some room |
| `ui.button(label, {kind})` | A button; true the frame it's clicked. `kind`: `"primary"`, `"danger"`, `"good"` |
| `ui.buttons(labels, {kinds})` | A row of buttons; the index of the one clicked, or nil |
| `ui.toggle(label, value, {swatch})` | A check box (with a colour swatch by the label, if given); returns true or false |
| `ui.switch(label, value)` | An On/Off switch; returns true or false |
| `ui.radio(label, value, options)` | One of a few options, as buttons; returns the chosen one |
| `ui.choice(label, value, options)` | A drop-down list; returns the chosen option |
| `ui.slider(label, value, lo, hi, {step, format, color})` | A slider with its value shown (`format` like `"%.2f"`); returns the value |
| `ui.number(label, value, {min, max, step, whole})` | A number box you can drag or type in; returns the number (`whole`: whole numbers only, shown without decimals) |
| `ui.input(label, value, {hint})` | A text box; returns its text |
| `ui.color(label, "#rrggbb")` | A swatch with red, green and blue sliders; returns `"#rrggbb"` |
| `ui.progress(label, fraction, {color, format})` | A bar from 0 to 1 |
| `ui.image(texture, w, h, {color})` | A picture: a texture object or its path |
| `ui.section(title, fn, {open, id})` | A part that opens and closes with a click on its title; `fn(ui)` draws what's inside |

`Menu.page(title, fn, {group, order, id})` adds a page. `group` puts it under one of the side bar's
groups (`Menu.groups`: `home`, `cat`, `world`, `story`, `fight`, `cheats`, `mods`, `tools`; `mods` by
default, and a group of its own comes after `mods`). `order` sorts it within the group (lower
first, 50 by default). `Menu.isOpen()` says whether the menu is open, `Menu.open(page)` opens it (on
a page, by title or id) and `Menu.close()` closes it, e.g. from a script's own key.
`Menu.key("F6", "Mouse look on and off")` lists a key a script uses on the Overview page
(`Game.onKey`'s fourth argument does the same). `Menu.status(text)` sets the line under the window's
title while the menu is open (one line; nil or `""` puts back the menu's own, and the last script to
set it wins); the player can hide it on the Menu page.
`Menu.saveJson(path, value)` writes a Lua value as JSON (keys sorted, notes like `"_help"` first)
and returns true, or false and why; `Menu.list(t)` marks a table as a JSON list, so an empty one is
written `[]`. `Menu.json(value)` gives the JSON text, `Menu.color(hex)` the linear colour the game's
UI wants, and `Menu.theme` the menu's colours.
- **Colours:** text is at least 4.5:1 on what it's on, as drawn. `theme.danger` is for text;
  `theme.danger_fill`, `theme.good` and `theme.accent` are for buttons. A button's colour is a tint of
  the engine's button image, which draws it at about half the brightness.
- **Keyboard and controller, for a script's own widgets:** `Menu.clicked(state, key, button)` is true
  the frame a button is clicked, by the mouse or with focus. `Menu.ring(widget)` puts a focus ring
  round a widget, and `Menu.focused(widget)` says whether it, or something in it, has focus.

How it fits together: each UE4SS mod has a Lua state of its own, so the menu window belongs to a
script wcmods installs with every build, `WCModsMenuHost`. It shares its content panel with the
others through UE4SS's shared variables (`WCModsMenu.open`, `.page`, `.content`, `.tree`,
`.generation`, `.pages`, `.keys`, `.request`). The script that owns the page on show builds its rows
straight into that panel, so a page always runs next to the settings it changes. The same rows
answer the agent controller (`wcmods agent menu ...`), which reads a page and uses its controls by
label through `WCModsMenu.agent.*` (docs/agent.md, "The mod menu").

## `WCModsView`

```lua
local View = require("WCModsView")

Draw.onFrame(function(d)                 -- or any game-thread loop
    local view = d.view                  -- this frame's view; View.current() gets one anywhere
    if not view then return end
    local x, y, depth = View.worldToScreen(someActor:K2_GetActorLocation(), view)
    if x then
        -- x, y: pixels from the viewport's top left; depth: distance in front of the camera
    end
end)
```

| Field or function | What it is |
|---|---|
| `View.current()` | The camera's view now, or nil until there's a camera and a viewport |
| `view.location`, `view.rotation` | The camera's position `{X, Y, Z}` and rotation `{Pitch, Yaw, Roll}` |
| `view.forward`, `view.right`, `view.up` | Its directions, as `{x, y, z}` lists |
| `view.fov` | Horizontal field of view, in degrees |
| `view.width`, `view.height` | The viewport, in pixels |
| `view.rect` | The part of the viewport the picture fills, `{x, y, width, height}` (the whole viewport unless the camera keeps its own aspect ratio) |
| `view.viewMatrix`, `view.projectionMatrix`, `view.viewProjection` | Unreal's matrices, 4 rows of 4, for row vectors (`clip = {X, Y, Z, 1} * viewProjection`). The projection is reversed-Z with the near plane at 10 cm, as the renderer builds it |
| `View.worldToScreen(location, view?)` | Screen x, y in pixels and the depth, or `nil` behind the camera. Takes `{X, Y, Z}` or an `FVector`; gets a view itself when none is passed |
| `View.cameraSpace(location, view?)` | Where a place is from the camera in centimetres: right, up, forward (negative is behind) |
| `View.engineWorldToScreen(location)` | The same through `GameplayStatics.ProjectWorldToScreen`. Slower, but handy to check against (checked in game: the two agree to the pixel) |

The view is the camera manager's last one, which is the picture on screen now. Get one per
update and reuse it for every point.

## `WCModsWorld`

```lua
local World = require("WCModsWorld")

for _, it in ipairs(World.nearby("pickups", 3000)) do     -- within 30 m of your cat, nearest first
    print(string.format("%s, %.0f m\n", it.label, it.distance / 100))
end
local quests = World.manager("quests")                    -- the game's quest manager object
```

| Call | What it gives |
|---|---|
| `World.nearby(kind, radius?, from?)` | What's within `radius` cm of `from` (an actor or `{X, Y, Z}`; your cat by default), nearest first, as `{actor, location, distance, name, label, class}`. Your cat itself is left out |
| `World.find(kind)` | Every actor of a kind, or of a class given by name (e.g. `"BP_Pickup_Herb_1_C"`) |
| `World.player()` | Your cat (the player's pawn), or nil in menus |
| `World.location(actor)`, `World.distance(a, b)` | `{X, Y, Z}`; centimetres between two actors or locations |
| `World.label(actor, kind?)` | A readable name: from its class (`BP_Pickup_SmallHealingHerb_C` is "Small Healing Herb", `BP_Interactable_Claw_Bush_C` "Bush (claw)"); with kind `cats` or `questGivers`, the cat's own name ("Otterpaw (Deputy)"); with `creatures`, its model ("Mouse") |
| `World.kindOrder()`, `World.kindLabel(kind)`, `World.kindColor(kind)` | The kinds in the menu's order, their names ("Quest givers") and colours (`World.kindInfo` holds them; scripts can change them) |
| `World.describe(actor)`, `World.parents(class)` | Its name, label, class, the classes that's made from, and location |
| `World.manager(name)` | One of the game's managers: `quests`, `npcs`, `tracer`, `gui`, `storage`, `paths`, `tutorial`, `combat`, `tuning`, or a class name |
| `World.addKind(kind, classes)`, `World.rescan()` | Add or change a kind; look again at the next query |

The kinds, and the game's classes they cover. An actor counts when its class is made from one of
them; the list was checked in game, from the classes the game's own objects report:

| Kind | Classes | What they are |
|---|---|---|
| `pickups` | `SwtAdventurePickupActor` | Herbs, catnip, healing herbs, pouches |
| `interactables` | `BP_Interactable_Base_C`, `SwtAdventureInteractableSequence`, `SwtAdventureInteractByContact` | Dig, claw, sharpen, sleep and play spots; scenes like the fallen tree; flowers |
| `objectives` | `SwtQuestObjectivePoint`, `QuestBoxTrigger`, `BP_Objective_Base_C`, `BP_ScentObjective_C`, `BP_InterativeObjective_C` | Quest places and trigger areas |
| `cats` | `SwtAdventureWalkingNPC`, `SwtAdventureQuestActor` | Clan cats walking about, quest givers, cats idling in camp |
| `questGivers` | `BP_Quest_Giver_Base_C`, `SwtAdventureQuestHintActor`, `SwtAdventureFreshKillActor` | Cats with a quest, gossip or a fresh-kill task |
| `creatures` | `WrcRoamingEnemy` | Prey and other animals roaming the territory |
| `climbing` | `SwtAdventureSplineClimbTarget`, `SwtAdventureJumpHotspotBase` | Climbable trees and walls; jump spots |
| `dens` | `SwtAdventureHousingDoorActor` | Den entrances |
| `freshKill` | `SwtAdventureFreshKillPileActor` | The fresh-kill pile |
| `zones` | `WrcZoneNameTrigger` | The areas whose names the game shows |
| `checkpoints` | `BP_Checkpoint_Base_C` | Checkpoints |

The game's managers hang off its game instance (`BP_WrcGameInstance_C`): quests, NPC generation,
the actor tracer, the GUI, storage, track paths, the tutorial, combat, tuning and its own cheats
manager (`CheatsManager`).

It reads the engine's actor list with one `FindAllOf("Actor")` at most every `World.refresh`
seconds (2 by default), and sorts each actor into kinds by its class, worked out once per class.
Queries in between use that list, so they're cheap, but still look things up a few times a second
rather than every frame when there are many. Call them on the game thread (in a painter, a menu
page, or inside `ExecuteInGameThread`).

## C++ mods

A mod can run C++ in the game as a UE4SS C++ mod: what Lua can't do quickly, or at all (code every
frame over many objects, hooks on engine functions, native libraries). It's built from the mod's
`cpp/` into its `dlls/main.dll`, and an install puts that in the game as `ue4ss/Mods/WCModsCpp_<id>/`.

```
mods/my-mod/
  mod.json
  cpp/CMakeLists.txt     wcmods_mod(${WCMODS_TARGET} src/main.cpp)
  cpp/src/main.cpp       the mod (WCMods.hpp, below)
  settings.json          optional: its settings, as wcmods::settings()
  dlls/main.dll          made by `wcmods cpp build`
  dlls/build.json        which UE4SS it was built against (also made by `cpp build`)
```

`python wcmods.py new my-mod --kind cpp` makes one: a mod that keeps your cat's stamina full while its
setting is on, and heals it on F7. Like scripts, C++ mods only run with `"allow_code_mods": true`, and building one runs its
CMake files, so `cpp build` needs that too.

### Building

A UE4SS C++ mod links against UE4SS itself, so it's built together with UE4SS's source, at the commit of
the UE4SS.dll in the game. A DLL built for one UE4SS can crash the game with another: an install leaves
out a mod whose `dlls/build.json` names another UE4SS, and warns about one without a `build.json`. Building
needs, once:

- **Visual Studio 2022 or later** with "Desktop development with C++" (MSVC 14.43 or later; Community is
  free). It brings CMake and Ninja; wcmods finds them there.
- **Rust** ([rustup.rs](https://rustup.rs), or `winget install Rustlang.Rustup`): UE4SS's pattern scanner
  is written in it.
- **git**, and a **GitHub account linked to an Epic Games account**. UE4SS's Unreal headers (UEPseudo)
  are only open to members of the EpicGames organisation on GitHub: link the accounts on epicgames.com
  (Account, Apps and Accounts) and accept the invitation GitHub emails you.

```bash
python wcmods.py cpp setup
```

```bash
python wcmods.py cpp build my-mod
```

`cpp setup` gets UE4SS's source at the game's UE4SS (the commit in `UE4SS.log`, so start the game once
with UE4SS first, or pass `--commit 83330635`) into `cache/ue4ss-src`, submodules included. Run it again
after updating UE4SS. `cpp build` builds the named mods (or every enabled mod with a `cpp/`) in
`cache/cpp`, then copies each `main.dll` and writes its `build.json`. The first build compiles UE4SS too
(several minutes); later ones only the mods. It prints the steps and any errors; `cache/cpp/build.log`
has everything. `python wcmods.py cpp` says what's ready. Install afterwards (or press Play in the
studio) to put the DLL in the game.

More ways to build and look:

- **`python wcmods.py cpp build my-mod --watch`** builds again whenever a file in `cpp/` changes
  (Ctrl+C stops), for working on a mod: install or Play after each.
- **`python wcmods.py cpp ide my-mod --open`** makes a Visual Studio solution (`WCModsCpp.slnx`, or `.sln` from an older Visual Studio) in `cache/cpp/ide`, with
  UE4SS as the mods link it, to edit, build (in the `Game__Shipping__Win64` configuration, the one the
  game's UE4SS is) and debug: attach the debugger to `Wrc-Win64-ShippingDRM.exe`.
- **Clan Mod Studio** shows a mod with `cpp/` a **Build C++** button under its More (with code mods
  allowed); the studio builds in the background and says how it went.
- **`python wcmods.py cpp crash`** reads the game's last crash (Unreal writes each to
  `%LOCALAPPDATA%\Wrc\Saved\Crashes`) and says whether a C++ mod was on the stack, which, and where in
  its source (a DLL built here has its symbols), so a game that closed with no word isn't a mystery.
  `agent crash` says it too.
- **A mod for several UE4SS versions:** `cpp build my-mod --keep` also copies the DLL and its
  `build.json` into `dlls/<UE4SS commit>/`. A mod can carry such a folder for each UE4SS it was built
  with; an install uses `dlls/main.dll` when it's for the game's UE4SS, else the folder for it. The
  rest of `dlls/` (a helper DLL) goes in with either.

A mod's `cpp/CMakeLists.txt` is plain CMake. `wcmods_mod(target sources...)` (from
`wcmods/cpp_sdk/WCMods.cmake`) makes the DLL, linked against UE4SS, with `WCMods.hpp` and the mod's own
`src/` on the include path; add sources to it, and anything else (`FetchContent`,
`target_link_libraries`) after it. The DLL uses Microsoft's C++ runtime (`MSVCP140.dll`), which players
have from the Visual C++ Redistributable; one built with a newer Visual Studio than theirs may need its
latest version.

A mod can also ship `dlls/main.dll` built (with its `build.json`) and no `cpp/`. Players then need the
UE4SS it was built for; the install says when theirs is another. Other DLLs in `dlls/` go in beside it.

### `WCMods.hpp`

wcmods' C++ SDK, headers on top of UE4SS's own API (`RC::CppUserModBase`, `RC::Unreal::...`;
UE4SS's [C++ guides](https://docs.ue4ss.com) cover that), which `WCMods.hpp` includes together:

| Header | Holds |
|---|---|
| `WCMods/Core.hpp` | text, JSON, files, the mod's info and settings, the log, the game's hidden members |
| `WCMods/Game.hpp` | the game's objects, the world and its managers, your cat, the clock, the fresh-kill pile, the developer switches |
| `WCMods/Events.hpp` | every frame, timers, keys, hooks on the game's functions, level and player events |
| `WCMods/Reflect.hpp` | any property by its path, as the kind it is; arrays, maps and structs; what an object has; spawning actors |
| `WCMods/World.hpp` | what's nearby, the game's screens and input, traces to the ground, the save, items, cats' names, clans and traits |
| `WCMods/Story.hpp` | quests, fights, and the game's events as one list |
| `WCMods/Menu.hpp` | pages in the mod menu (a settings page comes free), keys on its Overview, values shared with Lua mods |
| `WCMods/Ui.hpp` | the game's own UI: a tab of your own in its screens (the pause menu, the inventory, the settings), the HUD and its parts, overlays, every control the engine has |
| `WCMods/UiLua.hpp` | the same for Lua mods, as `WCModsCpp.ui` ([scripting.md, The game's own menus and HUD](scripting.md#the-games-own-menus-and-hud)) |
| `WCMods/Mod.hpp` | `wcmods::ModBase` and `WCMODS_MOD` |

The mod from `new --kind cpp`:

```cpp
#include <WCMods/WCMods.hpp>

class MyCppMod : public wcmods::ModBase
{
  public:
    auto on_unreal_init() -> void override
    {
        wcmods::log(L"loaded (full stamina: {})", wcmods::settings()["full_stamina"].boolean(true));

        // Four times a second (looking up your cat goes through the game's objects, so not every frame).
        wcmods::every(0.25, [] {
            if (!wcmods::settings()["full_stamina"].boolean(true)) return;
            if (auto stamina = wcmods::cat().stamina()) *stamina.value = *stamina.max;
        });

        wcmods::on_key(wcmods::Key::F7, [] {
            if (wcmods::cat().heal()) wcmods::log(L"healed");
        });

        wcmods::on_player([](wcmods::UObject* cat) {
            if (auto level = wcmods::Cat{cat}.level()) wcmods::log(L"your cat is here, level {}", *level);
        });
    }
};

WCMODS_MOD(MyCppMod)
```

Everything that reaches into the game gives `nullptr`, `nullopt`, `false` or an empty `Resource` when
what it asks for isn't there (no cat in a menu, a component the game hasn't made yet, a member wcmods
hasn't got on this game build), so a check is one `if`. A pointer into one of the game's objects is
good for the frame you got it in: look it up again next time rather than keeping it.

**The mod (`Mod.hpp`, `Core.hpp`)**

| Call | Does |
|---|---|
| `wcmods::ModBase` | A `RC::CppUserModBase` named, versioned and described from the mod's `mod.json`. Override UE4SS's `on_unreal_init`, `on_update` and the rest as you need |
| `WCMODS_MOD(Class)` | The two functions UE4SS calls in `main.dll` (`start_mod`, `uninstall_mod`); end the file with it |
| `wcmods::mod()` | The mod: `id`, `name`, `version`, `author`, `description`, `folder` (in `mods/`), `settings_file`, `installed` (its folder in `ue4ss/Mods`) |
| `wcmods::log(L"{} cats", n)` | A line in `UE4SS.log` starting with the mod's name (`std::format`) |
| `wcmods::settings()` | `settings.json` as a `wcmods::Json`, read as the game starts: `settings()["speed"].number(1.0)`. A key that isn't there is null, so the fallback is used. `settings_lock()` is its mutex, for a mod that changes it off the game thread |
| `wcmods::save_settings()` | Write `settings()` back to `settings.json`, so the next install starts with it |
| `wcmods::Json` | A JSON value: `boolean`, `number`, `string`, `wstring` (each with a fallback), `type()`, `is_null`, `is_bool`, `is_number`, `is_string`, `is_array`, `is_object`, `[key]`, `[index]`, `has`, `keys`, `values`, `set`, `push`, `size`, `Json::parse(text)`, `dump()`; made from any number, text or bool, `Json::object()`, `Json::array()` |
| `wcmods::read_file(path)`, `write_file(path, text)` | A file's text (nullopt when it isn't there); written whole, through a temporary file |
| `wcmods::wide(utf8)`, `utf8(wide)` | Convert text: the game's is wide, wcmods' files are UTF-8 |
| `wcmods::offset(cls, member)`, `member<T>(object, cls, member)` | The game's members that aren't reflected (health, stamina, level, stats, the clock; `wcmods/game.py`'s `HIDDEN`), where they are on the installed game build: wcmods writes them on every install to `ue4ss/Mods/shared/WCModsGame/offsets.json`, the same ones `WCModsGame` uses. `nullopt` / `nullptr` for one a game update moved where wcmods can't find it |
| `wcmods::reload_settings()` | Read `settings.json` again, when something else wrote it; false, with the settings as they were, when it can't be read |

**The game (`Game.hpp`)**, game thread only:

| Call | Does |
|---|---|
| `wcmods::name(o)`, `full_name(o)`, `class_name(o)` | An object's name, its full path, and its class's name |
| `wcmods::property<T>(object, STR("Pawn"))` | A pointer to a reflected property's value, its own or a parent class's |
| `wcmods::find_class(STR("/Script/..."))`, `object(STR("/Script/Engine.Default__GameplayStatics"))` | A class, or any object, by its full path |
| `wcmods::find_all(STR("WrcRoamingEnemy"))`, `find_first(...)` | Every object of a class (subclasses too), or the first. They go through all the game's objects: a few times a second, not every frame |
| `wcmods::is_a(o, STR("/Script/Engine.Pawn"))` | Whether an object is of a class, or a subclass |
| `wcmods::call(object, STR("GetDayClockTime"), params)` | Call one of an object's reflected functions, with a struct laid out like its parameters (inputs, outputs, return value, in order); `call(object, name)` for one that takes and gives nothing, `call<float>(object, STR("GetActorTimeDilation"))` for one that takes nothing and gives a value back (an optional). `python wcmods.py inspect "Game.gameState()"` lists an object's functions and their parameters |
| `wcmods::controller()`, `player()` | The player's controller and your cat's actor while you play, else `nullptr` |
| `wcmods::world()`, `level_name()` | The world, and the level's name (`L_WorldMap_01_P` in the forest) |
| `wcmods::game_instance()`, `game_state()`, `game_mode()` | The game's own objects |
| `wcmods::manager(STR("quests"))` | One of the game's managers, by a short name (`quests`, `save`, `cheats`, `combat`, `npcs`, `tuning`, `gui`...) or by the property that holds it (`QuestManager`) |
| `wcmods::component(actor, STR("SwtQuestHealthComponent"))` | An actor's component of a class, by short name |
| `wcmods::console(STR("stat fps"))` | A console command as the player, the way the mod menu's console box runs one; cheat commands need the mod menu's Cheats page to have turned cheats on |
| `wcmods::location(actor)`, `teleport(actor, {x, y, z})` | Where an actor is (`Vec3`, or nullopt), and moving it there. `to_vec3` and `to_fvector` convert to and from the engine's `FVector` |
| `wcmods::cat()` | Your cat as a `Cat` (false in menus); `Cat{actor}` for any cat |
| `Cat::health()`, `stamina()`, `combat_stamina()` | A `Resource`: `value` and `max` pointers you read and write; false when it isn't there. `heal()` fills health; `stamina_regen()` is stamina back per second. `wcmods::resource(actor, STR("SwtQuestHealthComponent"))` is the same for any actor's resource component |
| `Cat::status_component()`, `status()`, `status_rounds()`, `self_cure_chance()`, `poison_damage()` | The status condition component and the game's own members on it: the condition now (0 none, 1 Blinded, 2 Furious, 3 Poisoned, 4 Stressed), how many rounds it has lasted (each round's end rolls rounds × the chance to shake it off, 0.2 as it ships), and poison's damage (0.1 of health); pointers to read and write |
| `Cat::apply_status(3)`, `remove_status(3)`, `clear_status()` | Give, take off or clear a condition through the game's own functions, which tell its UI and the AI too (the rounds start at 1). Don't call the component's end-of-round outside a fight: with Poisoned it queues the damage on the fight's director, which isn't there |
| `Cat::level()`, `xp()`, `xp_needed()`, `stat(wcmods::Stat::Strength)` | Pointers on the level component (`level_component()`, on the player state): the level, experience and what the next level needs, and the six stats |
| `Cat::location()`, `teleport({x, y, z})`, `scale()`, `set_scale(1.5)`, `time_dilation()` | Where it is, moving it, its size, and how fast time runs for it |
| `wcmods::time_of_day()`, `day_seconds()`, `set_time(6, 30)` | The clock (`hours`, `minutes`, `seconds`), the seconds into the day to read and write, and setting it |
| `wcmods::fresh_kill()`, `fresh_kill_decay()`, `fresh_kill_component()` | The fresh-kill pile: how full (a `Resource`), its decay (`elapsed` seconds since it last dropped, `period` between drops), and the component |
| `wcmods::dev_switch(STR("bAllowAlwaysEquipItem"))` | One of the game's developer switches on its cheats manager, a bool to read and write; the mod menu's Cheats page lists them |

**Any property (`Reflect.hpp`)**, game thread only:

`property<T>` trusts you about the type. These check: a property is read as the kind it is, and
written only with a value of that kind.

```cpp
auto clan = wcmods::get(cat, L"MeshCustomizationComponent.CustomData.ClanType");   // an enum: clan.text
auto speed = wcmods::get(cat, L"CustomTimeDilation").number();
wcmods::set(cat, L"CustomTimeDilation", 0.5);
for (auto& [tag, count] : wcmods::map_entries(cat, L"rewards"))
    wcmods::log(L"{}: {}", wcmods::get(tag, L"TagName").text, count.i);
```

| Call | Does |
|---|---|
| `wcmods::get(object, L"Controller.PlayerState")` | A property's value by its path (names joined with dots, an element as `[2]`), as a `Value`: `kind` says what it is (`Bool`, `Int`, `Float`, `Text`, `Object`, `Enum`, `Struct`, `Array`, `Map`, `None` when there's no such property), with `boolean()`, `number()`, `string()`, `object`, an enum's name in `text`, the property's class in `type`, and `shown()` as text. `get(value, path)` goes on from a struct or object it gave |
| `wcmods::set(object, path, value)` | Write a bool, a number (to an int, float or enum), text (to an FString or FName, or an enum's name) or an object; false when there's no such property or it isn't that kind |
| `wcmods::elements(object, path)`, `elements(value)` | An array's elements, each a `Value` |
| `wcmods::map_entries(object, path)`, `map_entries(value)` | A map's pairs, each key and value a `Value` (the game's tag-count maps: a tag struct, whose `TagName` is the tag, and a count) |
| `wcmods::describe(object)`, `describe(value)` | Every property of an object or struct, with its name, type and value now: `python wcmods.py inspect` in C++ |
| `wcmods::struct_at(STR("/Script/SwtAdventure.SwtAdventureAttackMoveStruct"), bytes)`, `struct_at(type, bytes)` | A struct Value over bytes no property describes (a struct in one of the game's own arrays, as `Fighter::moves()` gives), by the struct's path or its `UStruct`; `get`, `set` and `describe` work on it. None without the type or the bytes |
| `Value::of(x)` | A `Value` from a bool, number, text or object, for `set` |
| `wcmods::call_reflected(object, STR("GetQuestStatus"), [&](wcmods::Params& p) { ... })` | Call a reflected function through its parameters by name or position (`p.set(L"Key", v)`, `p.set_nth(0, v)`, `p.raw(L"Start")` for a struct's bytes, `p.get(L"ReturnValue")`, `p.nth(i)`, `p.count()`, `p.has(name)`, `p.function()` and `p.bytes()` for the rest): for outputs that are structs, inputs that are arrays or strings, returns that are enums or texts, with no struct to lay out. nullopt when the object or function isn't there |
| `wcmods::spawn(STR("/Script/Engine.Actor"), {x, y, z})`, `destroy(actor)` | An actor of a class at a place (plain actors; the game's own cats need more, see the Lua module's `Game.npcs`), and taking one out |

**What's around, the game's input, the save, items and names (`World.hpp`)**, game thread only:

| Call | Does |
|---|---|
| `wcmods::nearby(wcmods::Kind::Pickups, 3000)` | Things of a kind within so many centimetres of your cat (or of a `from` actor), nearest first, each with `actor`, `location`, `distance`, `name` and `type`. Kinds: `Pickups`, `Interactables`, `Objectives`, `Cats`, `QuestGivers`, `Creatures`, `Climbing`, `Dens`, `FreshKill`, `Zones`, `Checkpoints`, the classes `WCModsWorld` sorts them by. A few times a second, not every frame |
| `wcmods::screens()` | The game's own screens and popups showing now, by class; none while you're just playing |
| `wcmods::pressed(L"T")`, `key_down(L"Gamepad_FaceButton_Top")` | A key or controller button that went down this frame, or is held, in the game's own input (Unreal's key names); only while the game has the focus |
| `wcmods::trace(from, to)`, `ground(x, y, z)` | Where a line first hits the world, and the ground's height below a place |
| `wcmods::save_manager()` | The game's save manager, which the save calls below go through |
| `wcmods::save_state(L"Inventory")`, `save_state_text(key)`, `set_save_state(key, json)` | A part of the current slot's live state as Json (and as the text the manager gives), through the save manager, and replacing one |
| `wcmods::save_progression(primary, sub)`, `save_setting(primary, sub)` | Whole-number progression and settings values |
| `wcmods::save_slot()`, `save_path()`, `save_file()`, `slot_data()` | The slot in use; the save as plain JSON (`WrcGame.json`, written at every save), whole and this cat's slot of it |
| `wcmods::items()`, `item_count(tag)`, `item_type(tag)`, `item_name(tag)` | Your items as `{tag: count}` from the last save with the pickups since (call `items()` once early so they're counted), one's count, its kind, and its name after the mods that add items. The kind is `Consumable` (herbs and pouches), `Collectible` (materials), `Equipment` (accessories) or `Quest`: the quest manager's `GetItemType` where it answers, else from the tag (`Gameplay.Inventory.Consumable`, `.Materials`, `.Cosmetic`, `.Quest`), as the game's item stats table ships empty and that call says None for every item |
| `wcmods::cat_name(actor)`, `cat_clan(actor)`, `cat_traits()` | A cat's name as the game shows it (your name mods included: wcmods writes `names.json` beside `WCModsNames` on every install), its clan, and your cat's traits from the last save |
| `wcmods::senses(animal)`, `detection_component(animal)` | A roaming animal's senses, as a `Senses` of pointers to read and write: `cone_angle`, `cone_distance`, `sound_radius`, `sound_speed`, `pounce_distance`, `proximity_distance`, `target_distance`, `walk_speed_roaming`, `walk_speed_chasing`, `zone_entry_distance`, `zone_exit_distance`, `react_to_chase`. They're the detection component's own copy of the tuning for its size class, so a change is this animal's alone; false for a cat |
| `wcmods::npc_detected(animal)`, `npc_target(animal)`, `blackboard(animal)`, `blackboard_bool(animal, L"Hunted")`, `blackboard_float(...)`, `blackboard_object(...)` | What an animal's AI knows: whether it has noticed a cat and which, and its controller's blackboard by key (Detected, Target, StartLocation, RoamingLocation, DetectionRange, ChaseReactionTime, Hunted, HunterPawn, PointOfInterest, bShouldAllowMovement, ArrivedAtTarget; in a fight AffectedByCondition, IsExhausted, IsAlive, WeakestEnemy, SlowestEnemy, SelectedAttack). nullptr / nullopt without an AI controller |

**Quests, fights and events (`Story.hpp`)**, game thread only:

| Call | Does |
|---|---|
| `wcmods::quest_manager()` | The game's quest manager, which the quest calls go through |
| `wcmods::quests()`, `describe_quest(object)` | Every quest the manager holds, each a `Quest` (`quest`, `id`, `tag`, `graph`, `type`, `status`, `result`, `tracked`, `xp`) |
| `wcmods::quest_status(tag)`, `quest_result(tag)`, `quest_successes(tag)` | By a quest's tag (`L"Quest.Main.3"`), with the enums' names |
| `wcmods::tracked_quest()`, `track_quest(quest, on)`, `start_quest(tag)`, `give_quest(tag)` | The quest followed; following one; starting or handing one out the way the game's quest givers do |
| `wcmods::objectives(quest)` | Its objectives in order: `id`, `index`, `current`, `target`, `status`, `point` (where to go) |
| `wcmods::chapter()` | The chapter the story is in ("Chapter00") |
| `wcmods::combat_active()`, `combat_director()` | Whether a fight is on, and its director |
| `wcmods::fighter(actor)`, `fight_players()`, `fight_enemies()` | A `Fighter` (a cat's combat component: `actor()`, `level()`, `stance()`, `stat(Stat)`, `move()`, `targets()`), and each side of the fight |
| `Fighter::team()`, `ai_tier()`, `move_count()`, `moves()` | The game's own members a fight sets up: the team (1 yours, 2 the enemy's), the AI's tier (1–6; 0 for your cat), and the moves it picks from, each an AttackMove row as a struct Value (`get(m, L"Damage")`, `get(m, L"AttackMoveTag.TagName")`). Seen in game: a weak mouse at level 1, tier 1, 3 moves; your cat 3 moves and no tier |
| `wcmods::fight_turn_order()`, `fight_current()`, `fight_main_enemy()` | Who acts in what order, whose turn it is, and the main enemy |
| `wcmods::on(wcmods::Event::CombatStart, fn)` | `fn(info)` when the event happens: `Level`, `Player`, `Phase`, `CombatStart`, `CombatEnd`, `GenericEvent`, `QuestStatus`, `Damage`, `TurnEnded`, `Status`, each with what it carries in the `EventInfo` (`name`, `object`, `a`, `b`; Story.hpp lists them). False when the game hasn't got what the event listens to |

The events of fights (`CombatStart`, `CombatEnd`, `Damage`, `TurnEnded`, `Status`) and quests (`QuestStatus`, `GenericEvent`) are checked as far as a test outside a fight can: their hooks are found on this build, and they're the same functions the Lua module's `Game.on` uses; `Level`, `Player` and `Phase` are seen firing.

**When code runs (`Events.hpp`)**, everything calling back on the game thread:

| Call | Does |
|---|---|
| `wcmods::every_frame(fn)` | `fn(seconds since the last frame)` at the end of every frame. Keep it quick: the game waits for it |
| `wcmods::on_game_thread(fn)` | `fn()` once, at the end of the next frame: from `on_update` or another thread, to get to the game |
| `wcmods::every(5, fn)`, `after(2, fn)`, `cancel(id)` | `fn()` every so many seconds, or once that many seconds from now; both give a `TimerId` |
| `wcmods::on_key(wcmods::Key::F6, fn)`, `on_key(key, {wcmods::Modifier::CONTROL}, fn)` | `fn()` when a key is pressed, in the game or out of it (UE4SS sees the keyboard only, not a controller, and the game gets the key too) |
| `wcmods::on_player(fn)` | `fn(cat)` when your cat appears (the forest loads), changes (a new area) or goes (menus; `nullptr`), looked for four times a second, and once right away |
| `wcmods::on_level(fn)` | `fn(level name)` once a level has loaded |
| `wcmods::on_function(STR("/Script/Wrc.GuiHudWrc:OnItemPickedUp"), fn)`, `after_function(...)`, `unhook(id)` | `fn(call)` just before, or just after, the game runs one of its functions, by its full path. `call.self()` is the object, `call.params<Params>()` its input parameters as a struct laid out like them (changed before the call, they change what the game does; the return value isn't in it), `call.set_return(v)` its result. 0 and a line in the log when there's no such function |
| `call.param(L"Tag")`, `call.param(0)`, `call.param(L"ReturnValue")`, `call.has_params()` | In a hook, a parameter by its name or position as `get()` gives it, with no struct to lay out: an input (when `has_params()`), an out parameter, or in `after_function` the return value, read from where the engine put each; a struct's bytes are the call's own |
| `wcmods::run_in_background(work, then)` | `work()` on a thread of its own (a file, the network, a long computation; never the game's objects), then `then(result)` on the game thread with what it gave back; `run_in_background(work)` for work that needs nothing after |
| `wcmods::on_game_thread_now()`, `assert_game_thread(L"what")` | Whether this is the game thread (known once a frame has run); the second says so in the log when it isn't |
| `wcmods::on_settings_changed(fn)` | `fn()` on the game thread when `settings.json` changed on disk (the studio, a text editor), after `settings()` has been read again; looked for once a second |

Hooks see every call that goes through the engine: an event or RPC (`ClientRestart`,
`OnItemPickedUp`), a Blueprint's call, or `wcmods::call`'s; native code calling native code directly is
never seen. A native function that a Blueprint's bytecode calls (`Actor:K2_GetActorLocation`, many
times a frame) fires the hook too, but its inputs aren't there to read: the frame is the caller's,
whose variables are what `params<T>()` would read as the parameters (nonsense, or a read of address 0
that closes the game when the caller has none). `call.has_params()` tells the two kinds of call apart
the way the engine does, by whether the frame has bytecode: it's true for a call through ProcessEvent
(an event, an RPC, Lua's or `wcmods::call`'s), and when it's false `param()` gives None for an input.
The return value is the exception: the engine has the function write it where the caller wants it, so
`call.param(L"ReturnValue")` reads it in `after_function` whichever way the function was called (not
`params<T>()`, whose slot for it stays as the stack left it). The crash was the first version of these
docs' unexplained one; the game's own crash record (`cpp crash`) named the line. The test mod hooks
`K2_GetActorLocation` through a whole run, reads back the location Lua's call got from the frame with
inputs and from a Blueprint's call without, and takes the hook off from outside the callback.

**The mod menu, and Lua (`Menu.hpp`)**

A C++ mod with a `settings.json` gets a page of its settings in the mod menu without asking, as script
mods do: a row for each setting by its kind (a switch, a number box, a colour, a text box; notes for
`"_help"`), and Save, which writes the file. A mod can add pages of its own:

```cpp
wcmods::menu_page(L"My mod", [](wcmods::Ui& ui) {
    ui.heading(L"My mod");
    on = ui.on_off(L"Enabled", on);
    speed = ui.slider(L"Speed", speed, 0.5, 3, {.step = 0.1, .format = L"x%.1f"});
    if (ui.button(L"Save", L"primary")) wcmods::save_settings();
});
```

| Call | Does |
|---|---|
| `wcmods::menu_page(title, fn, {order, group, id})` | A page: `fn(ui)` draws its rows every frame while it shows, on the game thread; gives back the page's id. `group` and `order` place it in the side bar as `Menu.page` does for scripts. The menu picks pages up when it opens, so one can be added at any time; one with an earlier page's id takes over its drawing, under the title the menu first saw |
| `wcmods::settings_page(false)` | No page of the settings. A page the menu has already picked up stays in its side bar until the game restarts, saying it's gone |
| `Ui::heading`, `text`, `note`, `separator`, `space(h)`, `field(label, value)`, `progress(label, fraction)` | Rows that show something |
| `Ui::button(label, kind)` | True the frame it's clicked; `kind` L"primary", L"danger", L"good" or nothing |
| `Ui::on_off(label, value)`, `toggle(label, value)` | An On/Off switch and a check box; each gives back true or false |
| `Ui::radio(label, value, {options})`, `choice(label, value, {options})` | One of a few options as buttons, and as a drop-down; each gives back the chosen one |
| `Ui::slider(label, value, lo, hi, {step, format})`, `number(label, value, {min, max, step, whole})`, `input(label, text, hint)`, `color(label, L"#rrggbb")` | A slider, a number box, a text box and a colour; each gives back what it holds |
| `Ui::section(title, fn, open)` | A part that opens and closes with a click on its title; `fn(ui)` draws what's inside |
| `wcmods::on_key(key, L"what it does", fn)`, `on_key(key, {modifiers}, help, fn)` | `on_key`, with the key listed on the Overview page with what it does; `key_name(key)` is the name it's listed by |
| `wcmods::menu_open()`, `menu_page_shown()` | Whether the menu is open, and the id of the page it shows |
| `wcmods::shared(name)`, `share(name, value)` | Values passed between Lua and C++ mods: `WCModsCpp.share(name, value)` in any Lua script reaches every C++ mod's `shared(name)`, and a C++ mod's `share(name, value)` is read in Lua as `WCModsCpp.mods["<mod id>"].get(name)`. A bool, number or string (null when there's none) |
| `wcmods::report_quest("my-quest", {.title, .status, .objective, .progress})`, `report_quest(id)` | A quest of the mod's own on the mod menu's Quests page (status L"available", L"active" or L"done"); report it again as it changes, and alone to take it off |

How it works: UE4SS hands a C++ mod every Lua mod's state as it starts (`on_lua_start`), and `ModBase`
puts a `WCModsCpp.mods["<mod id>"]` table into each, with `pages()`, `draw(id, ui)`, `keys()`,
`set(name, value)` and `get(name)`. A mod that overrides `on_lua_start` itself calls
`ModBase::on_lua_start` from it, or loses all of this. The mod menu's own script draws a C++ mod's pages through `draw` (every `Ui`
call is one of its `ui.*` rows), lists its keys, and tells it when the menu opens and which page
shows. The Lua stays where the menu is; the C++ page's function only ever runs on the game thread.

**The game's own UI (`Ui.hpp`)**, game thread only

The game's menus are UMG, like the mod menu, and `Ui.hpp` works with them directly: a tab of the mod's
own in the pause screen, the inventory or the settings, with a page of the engine's controls in the game's
font; the HUD and its parts; overlays on the viewport; and any widget the engine has, made, placed, styled
and watched. Sizes are the game's own units: its UI is laid out for a 3840×2160 screen and scaled to fit,
so a 52-point title and a 700-wide control look as the game's do.

```cpp
wcmods::ui::tab(L"WBP_GuiScreenPause_C", L"Mods", [](wcmods::Widget page) {
    page.add(wcmods::ui::heading(L"My mod"));
    auto on = wcmods::ui::checkbox(wcmods::settings()["on"].boolean());
    on.on_toggle([](bool v) { wcmods::settings().set("on", v); });
    page.add(wcmods::ui::labelled(L"Enabled", on));
    page.add(wcmods::ui::labelled(L"Speed", wcmods::ui::slider(1, 0.5, 3, 0.1)));
});
wcmods::ui::hud_part(L"mcGuiMinimap").collapse();                       // no minimap
wcmods::ui::overlay(L"notes").add(wcmods::ui::text(L"Hello")).at(100, 100);   // over the game's UI
```

A `Widget` is a handle on any widget: it knows when the game has destroyed what it points at (then it's
false, and every call on it does nothing), and compares equal to another handle on the same widget. The
helpers in `wcmods::ui` make widgets styled by `ui::theme()` (the game's Amarante font, its light text,
36-point rows and 52-point headings; change it to change what they make). The engine's own controls
(check boxes, sliders, number and text boxes, drop-downs) are drawn for a 1080-pixel screen, so
`labelled()` and `scaled()` grow them by the theme's `control_scale`: a slider, a number or text box or a
drop-down in a scale box, with its text set to `text_size / control_scale` so that it comes out at the
theme's size (set the font after `labelled()` for another); a check box by a render transform (in the game,
a scale box didn't grow one), in a box that reserves the room it's drawn in: its pictures and its style's
padding times `control_scale`, so 24 × `control_scale` tall for `checkbox()`. A button, text or a layout is
left as it is.

| Call | Does |
|---|---|
| `wcmods::ui::tab(L"WBP_GuiScreenPause_C", L"Mods", fn, {id, inset, hide_game_panels, scroll, focus, mouse})` | A tab of the mod's own in one of the game's screens, by the screen's class (`WBP_GuiScreenPause_C`, `WBP_GuiPopupInventory_C`, `WBP_GuiPopupGameSettings_C`, `WBP_GuiPopupSettings_C`...): a tab button like the screen's own after them, which the game's tab keys reach (1 and 2, a controller's shoulder buttons), and `fn(page)` filling its page (a column to add rows to) each time the screen opens. The game's panels hide while the page shows and come back after. Gives back the tab's id. Keep the title short, as the game's are |
| `wcmods::ui::tab_page(id)`, `tab_active(id)`, `remove_tab(id)`, `tabs()` | The tab's page while its screen is up (else empty), whether the game's navigation is on it, taking it out, and every tab's id |
| `wcmods::ui::screen(L"WBP_GuiPopupInventory_C")`, `on_screen(type, fn)` | One of the game's screens while it shows (a base class works too, `GuiPopupCommonSettings`), and `fn(screen, shown)` when a screen of a class comes on the viewport and when it goes, looked for four times a second. `wcmods::screens()` (World.hpp) lists the ones showing |
| `wcmods::ui::hud()`, `hud_part(L"mcGuiMinimap")` | The HUD while you play (`WBP_GuiHudGameWrc_C`), and one of its parts by name: `mcGuiMinimap`, `mcGuiEnergyBar`, `mcGuiHudCharacter`, `mcGuiQuestObjective`, `mcGuiContextualMenu`, `mcGuiSenseControl`, `mcGuiAreaName`...; its layers `CanvasExploration`, `CanvasCombat` and `CanvasOver` take widgets of your own |
| `wcmods::ui::overlay(L"name", {layer, passive})`, `remove_overlay(name)` | A canvas of the mod's own on the viewport, by name, made once and kept: add widgets and place them with `at(x, y)` or their slot. `passive` (the default) lets the mouse through to the game. It goes with the level and comes back empty when asked for again |
| `wcmods::ui::widget(L"ExpandableArea")` | Any of the engine's widgets by its class, plain: `TextBlock`, `Button`, `CheckBox`, `Slider`, `SpinBox`, `ComboBoxString`, `EditableTextBox`, `MultiLineEditableTextBox`, `EditableText`, `ProgressBar`, `Image`, `Border`, `SizeBox`, `Spacer`, `HorizontalBox`, `VerticalBox`, `ScrollBox`, `CanvasPanel`, `Overlay`, `GridPanel`, `UniformGridPanel`, `WrapBox`, `WidgetSwitcher`, `ScaleBox`, `ExpandableArea`, `BackgroundBlur`, `Throbber`, `CircularThrobber`, `RichTextBlock`, `InputKeySelector`, `ListView`... (any class in `/Script/UMG`), or by a full class path |
| `wcmods::ui::game_widget(class)` | One of the game's own widget Blueprints, by its class or its path, made the way the game makes its widgets |
| `wcmods::ui::text(L"Hi", {size, color, wrap, justify})`, `heading(str)`, `note(str)` | Text in the game's font; a heading; smaller grey text |
| `wcmods::ui::button(label, color)`, `checkbox(on)`, `slider(value, lo, hi, step)`, `number(value, lo, hi, step)`, `input(text, hint)`, `choice({options}, selected)`, `progress(fraction, color)`, `image(texture path, w, h)`, `rect(color, w, h)` | The controls, styled: a button with a label, a check box, a slider, a number box you can drag or type in, a text box with a hint, a drop-down, a bar, a picture (a texture the game has loaded), a flat colour |
| `wcmods::ui::hbox()`, `vbox()`, `scroll()`, `border(color, padding)`, `box(w, h)`, `spacer(w, h)`, `canvas()`, `overlay_box()`, `grid()`, `uniform_grid()`, `wrap()`, `switcher()`, `scale(factor)` | Layouts: widgets side by side, one under another, a list that scrolls, a box around one widget, a fixed size, empty room, free placement, one over another, grids, a flow that wraps, one of several, and a scaled one |
| `wcmods::ui::row({widgets}, gap)`, `labelled(label, control, width)`, `scaled(control, width)` | A row (the first widget takes the room left), a labelled control as the game's settings rows, and a control grown to the game's size: a check box by a render transform in a box of its drawn size, a number or text box or drop-down in a scale box with its text fitted, a button, text or layout as it is |
| `Widget::add(child)`, `add({children})`, `remove(child)`, `remove()`, `clear()` | Put a widget in a panel (at the end) or in a content widget (as its one content), giving back its `Slot`; take one out; take this one out of wherever it is; take every child out |
| `Widget::parent()`, `children()`, `child(i)`, `count()`, `find(name)`, `find_all(type)`, `walk(fn)` | The tree: the widget this one sits in, the widgets in it, one by its name anywhere down the tree (the game's screens name their parts: `find(L"mcGuiFooter")`), every one of a class, and `fn(widget)` down the tree (false stops) |
| `Widget::slot()`, `at(x, y)` | The slot it sits in, and on a canvas, its top-left at a place |
| `Slot::padding(m)`, `fill(weight)`, `fit()`, `align(h, v)` | In a box: room around it, a share of the room left or only what it needs, where it sits (`Align::Fill`, `Start`, `Center`, `End`) |
| `Slot::anchors(x0, y0, x1, y1)`, `stretch(inset)`, `offsets(m)`, `position(x, y)`, `size(w, h)`, `alignment(x, y)`, `auto_size(on)`, `layer(z)`, `at(x, y)`, `cell(row, column, spans)` | On a canvas: its anchors and offsets, its place and size, which point of it sits at its position, whether it sizes itself, its layer; on a grid, its cell |
| `Widget::show()`, `show_passive()`, `hide()`, `collapse()`, `set_visibility(v)`, `visibility()`, `visible()` | Shown and taking input; shown and letting input through; hidden keeping its room; gone; any `Visibility`; what it's set to; whether it's drawn now |
| `Widget::set_enabled(on)`, `enabled()`, `set_opacity(f)`, `opacity()`, `set_scale(x, y)`, `set_angle(deg)`, `set_translation(x, y)`, `set_pivot(x, y)`, `set_tooltip(text)` | Enabled or greyed; its opacity; drawn bigger, turned, moved, around a pivot; a tooltip |
| `Widget::focus()`, `focused()`, `hovered()` | The keyboard's (and a controller's) focus: give it, whether it or a widget in it has it; whether the mouse is over it |
| `Widget::text()`, `set_text(str)`, `set_hint(str)`, `set_font(size, typeface)`, `set_color(c)`, `set_wrap(on)`, `set_justify(a)`, `set_shadow(offset, c)` | The text a text block, text box or button shows, and how: the game's font sizes (52 titles, 36 rows), a colour, wrapping, justification, a shadow. A game control with a `Text` property (a tab button) takes `set_text` too |
| `Widget::value()`, `set_value(v)`, `set_range(lo, hi, step)`, `checked()`, `set_checked(on)` | What a control holds: a slider's or number box's number, a bar's fraction, a drop-down's index, a check box (1 or 0, or as a bool); a range and step |
| `Widget::options()`, `add_option(s)`, `set_options({s})`, `option()`, `set_option(s)` | A drop-down's options and the one chosen |
| `Widget::set_image(texture)`, `set_tint(c)`, `set_padding(m)`, `set_size(w, h)`, `set_active(i)`, `play(animation, reverse)` | A picture; the colour an image, border, button, bar or slider is drawn in; room inside a border; a size box's, spacer's or image's size; a switcher's child; a user widget's animation by name (`AniScreenIn`) |
| `Widget::on_click(fn)`, `on_change(fn)`, `on_toggle(fn)`, `on_text(fn)`, `clicked()`, `changed()` | `fn()` when a button is clicked, `fn(value)` when a slider, number box or drop-down changes, `fn(on)` when a check box is ticked, `fn(text)` when a text box's text changes, each looked at every frame while the widget lasts; or asked: true on the frame it happened (the first ask starts the watch) |
| `Widget::get(path)`, `set(path, value)`, `call(function, fill)`, `object()`, `valid()`, `name()`, `type()`, `is_a(path)` | Any property and any reflected function, as `Reflect.hpp` has them (`python wcmods.py inspect` lists a widget's); the `UObject*`; whether it's still there; its name, class, and whether it's of a class |
| `UiColor::hex(L"#ffcc00")`, `to_hex()`, `Margin`, `Vec2`, `Visibility`, `Align` | A colour as an image editor shows it (converted to the engine's linear colours where a call wants one; UE4SS has a `Color` of its own, hence the name), room on four sides, a pair, and the enums |
| `wcmods::ui::theme()` | What the helpers make: `text_size`, `heading_size`, `text`, `heading`, `muted`, `accent`, `field`, `button`, `panel` colours, `typeface`, `game_font`, `control_scale`, `control_width` |
| `wcmods::ui::viewport_size()`, `viewport_scale()`, `show_cursor(on)` | The viewport in pixels and the UI's scale; the mouse cursor (the game hides it in its menus: shown, your controls take the mouse) |

How a tab works: the game's screens keep their tabs (the pause screen's General, Controls, Quest...; the
inventory's Consumable, Materials, Accessories; the settings' Audio, Gameplay...) as `GuiButtonState`
controls in a row, listed in the screen's `NavControls` navigation, which the tab keys move along. A tab of
the mod's own is one more of the game's tab buttons (made from the class of the screen's own, so it looks
the same), put after them in the row and appended to that list, so the game's own navigation selects it;
the row is drawn smaller when the tabs no longer fit. While the navigation is on it, the page (a border
over the panels' area, the panels hidden) shows and the keyboard goes to its first control: the arrows,
Tab and Enter then move among and use the page's controls. The cat maker's categories are a circular
icon menu (`GuiCircularMenu`), not a tab row, so `tab()` doesn't reach it; its screen and parts are
still there through `screen()`, `find()` and `add()`.

What `hide_game_panels` hides while the page shows, and puts back as it was after: everything the screen
put beside the tab row, in the canvas the row sits in: the panels its tabs switch between (the pause
screen's General, Controls, Quest, Party and Bonds, in a canvas of their own), and what a tab adds there
(the Bonds tab's cat cards, in plain size boxes), each with what's inside it. The screen's fixtures stay:
its title, footer and background, told by their names (`CanvasTitle`, `mcGuiFooter`, `CanvasBackground`),
and so does what a mod added to the area (a tab's page frame). The page's frame is drawn in the theme's
`panel` colour, translucent, so a panel left showing would show through: say if one does.

The tab's page is built again each time the screen opens, because the game makes its screens anew; keep
the state the page shows in your own variables, as the example does with the settings. While the page
shows, it takes the mouse (`mouse`, on unless you say otherwise): the cursor is shown, the game's input
mode is set to game-and-UI, as the game's own menus leave it, and the game's fade widgets (which sit over
its screens with a full-screen picture that would take every click) let the mouse through, so the page's
controls, its scroll bar and the wheel answer it; the cursor goes back as it was, the fades take hits
again and the input is flushed when the page goes. The keyboard goes to the page's first control (`focus`).
Tabs of one mod on one screen are put away before the next is shown, whatever order they were made in,
so a tab leaving never undoes what the next took; and while a page shows it keeps what it hid hidden and
the mouse its own, looked at four times a second, so a panel the game shows again, or another mod's tab
leaving the same screen, takes them away for a moment at most.

The same rules as for scripts keep the game running:

- **The game thread.** Touch the game's objects only on the game thread: in `every_frame`, a timer, a
  key, a hook, `on_player`, `on_level`, or a UE4SS hook. UE4SS calls `on_update` from a thread of its own.
- **Look things up again.** The game destroys its actors when the level changes, so get your cat with
  `cat()` when you need it rather than keeping the pointer.
- **Keep frames quick.** `find_all` goes through the game's objects; do it a few times a second, not
  every frame, as the example does.
- **Exceptions** thrown in callbacks are caught and logged; one that reaches the game closes it. A
  crash (a bad pointer) closes it too, and there's nothing to catch: check for `nullptr`.

### Testing the SDK

Every call above is checked in the game. `tests/cpp-sdk` is a C++ mod that calls all of them (one file
a header, `test_core.cpp`, `test_game.cpp`, `test_events.cpp`, `test_ui.cpp`...) and records what it got in its
`results.json`; `tests/game/test_cpp_sdk.py` reads that, compares it with what Lua sees of the same
things, and asks the mod to make changes (heal, the clock, a teleport, the cat's size, a switch, a
console command, its settings, a tab in the pause screen with every kind of control, an overlay, a label on
the HUD) that Lua then confirms, before putting them back. With the game closed:

```bash
python wcmods.py cpp build tests/cpp-sdk
```

```bash
python wcmods.py agent install --with tests/cpp-sdk
```

```bash
python wcmods.py agent test tests/game/test_cpp_sdk.py --launch
```

`python wcmods.py selftest` checks, without the game, that every call the headers declare is both in
this document and called by the test mod, so a new call can't go undocumented or untested. Keys are the
one part that needs you: UE4SS reads the real keyboard, so the key test presses F9 only when the game
can be put in front, and says so when it can't.

## JavaScript: `studio/lib/wc.js`

A studio page is an ES module whose default export has a `mount(root, wc)` function:

```js
export default {
  title: "My page",
  async mount(root, wc) {
    const r = await wc.api.get("/mods/my-mod/file/my-settings.json");
    root.append(wc.el("h1", { text: "My page" }));
    return { unmount() {} };   // optional
  },
};
```

Each page is loaded only when it's opened, and a page that throws shows an error card without
affecting the others.

| Export | What it gives you |
|---|---|
| `api.get/post/put/patch/del(path)` | The studio API (token handled). Routes are listed below |
| `el(tag, attrs, ...children)`, `$`, `clear` | Small DOM helpers |
| `toast(msg, "bad"?)`, `confirmButton(label, armedLabel, fn)` | Feedback, and two-step confirm |
| `modTarget({file, defaultId, defaultName, onLoad, getValue})` | The "Editing mod: … Save to mod" bar the built-in pages use |
| `codePanel(title)` | A copyable JSON preview |
| `color` | sRGB/linear conversion, HSL, `mood(hex, "vivid"\|"pastel"\|"moonlit"\|"ember")` |
| `input` | Browser key/mouse/gamepad to Unreal key names, plus Xbox/PlayStation/Switch labels |
| `bus.on/emit` | Page-to-page events: `mods-changed`, `installed`, `run-task` |
| `getPath(obj, "a/b/c")` | Read a save path |

API routes: `GET /info`, `GET|POST /mods`, `PATCH /mods/<id>`,
`GET|PUT|DELETE /mods/<id>/file/<name>` (the built-in files plus the mod's `studio_files`),
`POST /build`, `/install`, `/uninstall`, `/palettes/apply`, `GET /backups`, `POST /backup`,
`/restore`, `GET|PATCH /ingame` (the game console, cheats at start, the mod menu's key and size),
`GET /game/bridge` (whether the game runs with the bridge), `POST /game/lua` `{code}` and
`/game/inspect` `{expr}` (run Lua in the game, or describe an object; code mods only),
`GET /names`, `POST /names/preview`, `GET /cat`, `GET /game/eyes`, `/game/tables`,
`/game/bindings`, `/game/data`, `/game/data/<table>`, `/save`.

The server listens on 127.0.0.1 only, and every API call needs the per-run token that the page
gets when it loads. Other websites therefore can't drive it. The studio runs the wcmods code it
started with: if wcmods is updated while it's open, it refuses to build or install (and says
"Restart the studio") until it's opened again.
