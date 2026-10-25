# wcmods SDK

The mod manager is built from **sections**. Each section handles one kind of mod content: the
built-in ones are replacement files, game data, names, palettes, your cat's colours, controls,
mouse look and save edits. A mod can add code of its own in three places:

| Part | File in the mod folder | Runs in | Built on |
|---|---|---|---|
| Build step | `section.py` | `wcmods build` / `install` | `wcmods.sdk` (Python) |
| Studio page | `studio/section.js` | `wcmods studio`, in your browser | `studio/lib/wc.js` |
| In-game script | `scripts/main.lua` (no Python), or written by its `section.py` | the game, through UE4SS | UE4SS Lua, plus the shared modules below: `WCModsGame`, `WCModsDraw`, `WCModsMenu`, `WCModsView`, `WCModsWorld` |

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
                       "game_builds" (the game's builds it was made for; docs/updating.md),
                       "studio_title" (nav label), "studio_files" (["my-settings.json"])}
  menu.json           the in-game mod menu itself       -> only mods/mod-menu (see "WCModsMenu")
  files/Wrc/...       replacement game files            -> section "files"
  paks/<name>.pak     cooked content made with Unreal   -> installed as is, with its .utoc/.ucas
                      Engine 5.7 (see "New content")
  data.json           CSV cell edits                    -> section "data"
  items.json          new herbs and materials           -> section "items" (see "New items")
  names.json          cat names                         -> section "names"
  palette.json        colour palettes                   -> section "palettes"
  cats.json           your cat's own colours and slots  -> section "cats"
  controls.json       key and button remaps             -> section "controls" (checked at build;
                                                           applied by `wcmods play`, keyboard and mouse)
  mouselook.json      mouse look settings               -> section "mouselook"
  save.json           save edits                        -> section "save"
  scripts/main.lua    an in-game Lua script (code mod)  -> section "scripts" (docs/scripting.md)
  settings.json       that script's settings            (MOD.settings; a mod menu page edits them)
  section.py          your own build step               (code mod)
  studio/section.js   your own studio page              (code mod)
```

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
(format-preserving save JSON), `wcmods.cooked` (cooked DataTables), `wcmods.colors`, `wcmods.palettes`, `wcmods.eyeatlas`,
`wcmods.gamefiles`, `wcmods.names` (the game's name tables). `wcmods.sdk.lua_value(data)` writes
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
| `zzz_WCMods_P.utoc` / `.ucas` | Patched copies of existing cooked packages (the eye colour atlas, and anything a section passes to `ctx.patch_package`). Each keeps the game's chunk ID and its container header entry (imports, shader maps), with BLAKE3-160 chunk hashes, so the engine loads ours instead of the game's |
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

A mod can add herbs and materials of its own, and change the recipes of the game's herbs and
accessories. wcmods writes everything the game needs for a new item:
- the item's gameplay tag;
- its row in the cooked item table, `DT_QuestObjectsInfo`: name, description and icon (the inventory
  leaves out an item without one);
- for a herb, what using it does (`Consumables.csv`) and a recipe at the medicine cat's bartering
  (`BarteringCost.csv`);
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
      "icon": "Rock",
      "give": 2
    }
  ],
  "recipes": {
    "Cosmetic.Head.MossPatch.1": { "Moss": 3, "Ivy": 1, "Moonstone": 1 }
  }
}
```

| Key | |
|---|---|
| `id` | Letters and digits. The item's tag is `Gameplay.Inventory.Consumable.<id>` for a herb or `Gameplay.Inventory.Materials.<id>`. It can't be one the game or another mod already has; the build says if it is |
| `name`, `description` | What the inventory and bartering show, the same in every language |
| `like` | A game item to start from, by its short name (`"MediumHealingHerb"`) or whole tag: its kind, effect, when it can be used, icon, icon group, rarity and colour. The item's other keys override those |
| `kind` | `"consumable"` (a herb or pouch) or `"material"`, when there's no `like` |
| `icon` | An item to borrow the icon of (`"Rock"`), or a texture of the game's, e.g. `"/Game/Art/UXD/Textures/gui_icons/gui_icons_inventory/T_UI_Icon_Flower_Marigold_D"` (`wcmods files "*gui_icons_inventory*"` lists them) |
| `effect` | Herbs: what using one does, one of the game's herb effects, such as `Gameplay.Effect.Consumable.Health.2` (+50 health). [items.md](mechanics/items.md) lists them |
| `type`, `target` | Herbs: the effect's kind (`Health`, `Stamina`, `BuffStrength`, …), and who it's for: `Owner`, or `OwnerTeam` for your whole team |
| `combat`, `exploring`, `fight_only` | Herbs: `true` or `false` for usable in fights, usable while exploring, and whether its effect ends with the fight |
| `group`, `rarity`, `color` | The badge by its icon (`Health`, `Stamina`, `Stats`, `Status`, `Damage`, `Experience`, `Free`, or `None`), the rarity (`Common`, `Uncommon`, `Rare`, `Mythic`, `None`) and the category colour (`Consumable`, `Quest`, `Den`, `None`) |
| `recipe` | Herbs: what the medicine cat wants for one, e.g. `{"Dandelion": 2, "Moonstone": 1}`. Any material, the game's or one a mod adds |
| `give` | How many you start with: given once, in the save slot you play, if you have none yet |

`"recipes"` changes what the medicine cat wants for one of the game's herbs or accessories, by its
tag with or without `Gameplay.Inventory.`. Accessories are
`Cosmetic.<Head|Neck|Body|Legs>.<name>.<variation>`, e.g. `Cosmetic.Neck.DogCollar.2` (`wcmods
extract "*BarteringCost.csv"` shows them all). The ingredients are as for an item's `recipe`, new
materials included.

What it can't do (yet):
- **New effects:** each herb effect is one of the game's Blueprints, so a new herb does what one of
  the game's does (heal 25, 50 or 100, stamina, a stat buff, a cure, experience).
- **New accessories:** what a cat wears is a model and its textures, listed in the game's own code
  (`EAccesoryIds`), so a new one needs new art. `"recipes"` can change what an existing one costs.
- **Growing in the world:** new materials aren't found in the forest; they come from `give` or a
  script.
- New items need the Oodle DLL, because the item table is compressed in the game's files.

### New content: models, textures, sounds

New assets have to be cooked by Unreal Engine itself; wcmods doesn't cook. Once cooked, a mod
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
| `WCModsNames` | Cats' names: every name part's text after your name mods, and `name(prefix id, suffix id)`, which falls back on the game's own text (written on each install; `WCModsGame` and `WCModsWorld` use it) |

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

The mod menu is a mod of its own: **Mod menu**, `mods/mod-menu`, the one mod that comes with wcmods. It starts
on.
- **While it's on:** a build puts in its window (`WCModsMenuHost`) and this module.
- **While it's off:** there's neither, and `pcall(require, "WCModsMenu")` fails, so a script that
  adds a page checks first:

```lua
local okMenu, Menu = pcall(require, "WCModsMenu")
if okMenu then Menu.page("My mod", function(ui) ... end) end
```

- **A mod that only works with the menu** says so in its `mod.json`: `"requires": ["mod-menu"]`.
  Turning it on then turns the menu on too, and a build leaves it out while the menu is off.
- **A mod that only adds a page** says `"uses": ["mod-menu"]`, which the studio shows as "Page in
  the mod menu". Mouse look and script mods with a `settings.json` show it without saying so.

The menu's settings are in its `menu.json`, set on its card in Clan Mod Studio: `"key"` (`INS`,
`HOME`, `END`, `DEL`, `PAGE_UP`, `PAGE_DOWN` or `F1`-`F12` but F11), `"pad"` (the controller button
that opens it too, as an Unreal key name: View, `Gamepad_Special_Left`, by default and `""` for none),
`"size"` (0.6 to 2.2, 1 by default) and `"cheats"` (whether the Cheats page starts with cheats on).
Older setups kept these in `wcmods.json` as `"menu_key"`, `"menu_scale"` and `"cheats"`. Those still
count, and the first change in the studio moves them into `menu.json`.

Insert (or a controller's View button) opens the menu in game, and Insert or Escape closes it (View or
B too, when the controller opened it). While it's open, the menu has the keyboard and mouse, the cursor
shows, and the game's controls wait. "Pause the game" stops the game too, and A- and A+ resize it.

The menu works without a mouse too:
- **Moving:** Tab, the arrow keys or a controller's d-pad move between the controls. Tab goes round
  the window: the top bar, the side bar, then the page. Opening the menu puts focus on the page's
  tab, so Up and Down pick a page, Enter opens it and Right goes into it.
- **Using a control:** Enter, Space or A presses a button, ticks a box or opens a list. A slider
  takes Enter to grab it, Left and Right to move it, and Enter again to let go.
- **From a controller:** View (`"pad"` in `menu.json`; the menu's card in the studio picks another
  button, or none) opens it, and View or B closes it. The game can only hear a controller while it has
  input, so a menu opened this way leaves the game its input and pauses it instead. It doesn't open
  while something else has the game paused, such as the game's own pause menu.
- **Seeing where you are:** the control with focus has a gold ring. The page you're on, and a chosen
  option, are light with dark text, so they show without relying on colour.

Under the title, a status line shows your cat (name, level, rank, health, stamina, clan), the time
and the fresh-kill pile. The side bar lists the pages in groups:

| Group | Pages |
|---|---|
| Home | **Overview** (your cat and the world at a glance, quick buttons, the keys scripts use), **Installed mods** (each mod and what each part of the build set up) |
| Your cat | **Stats** (health, stamina, size, level, stats), **Colours**, **Mouse look** |
| World | **World** (the clock, which can be held, and the fresh-kill pile), **Travel** (saved spots, checkpoints and areas, and Back), **Nearby** (what's around your cat, `WCModsWorld`), **Items** (what you carry, and an item to drop) |
| Story | **Quests** (the one you follow and its objectives, with "Go to objective"; the rest by state) |
| Fight | **Fight** (both sides during a fight) |
| Cheats | **Cheats** (the engine's cheat manager), **Game switches** (the developers' own) |
| Mods | Pages scripts add, and a script mod's settings page |
| Tools | **Log** (UE4SS's log, newest first), **Menu** (its size, pausing, the status line), and with code mods allowed **Inspector** and **Console** |

Cheats is the engine's cheat manager, switched on and off live (`"cheats"` says whether it starts
on). It has god mode, fly and ghost, cat size, game speed, teleport and a console command box. Flying
and size are done by the menu itself, because the game undoes the engine's own `fly`, `ghost` and
`changesize`. The pages built on `WCModsGame` are in docs/scripting.md, "In the mod menu".

wcmods' mouse look and your cat's colours have live settings with Save, and any script can add a page:

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
end, { group = "mods", order = 40 })
```

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
(`Game.onKey`'s fourth argument does the same).
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
