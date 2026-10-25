# Scripting the game

How to write Lua that runs inside *Warrior Cats: Clans of the Forest*: read and change your cat, items,
the fresh-kill pile, the time of day, quests and fights, react to what happens, and look inside any of
the game's objects while it runs. It's built on UE4SS (the script loader wcmods installs mods into) and
the shared modules wcmods installs with every build, mainly **`WCModsGame`**.

Three ways in:

| | What it is | Where |
|---|---|---|
| **A script mod** | `scripts/main.lua` (and `settings.json`) in a mod folder. No Python needed | [Script mods](#script-mods) |
| **A build step** | A mod's `section.py` that writes a script from the mod's settings, for mods that build things too | [SDK.md](SDK.md#in-game-scripts) |
| **Live** | The console in the mod menu and in Clan Mod Studio, and `wcmods lua`, which run Lua in the game while it's open | [The game bridge](#the-game-bridge) |

All of them are code, so they only run with `"allow_code_mods": true` in `wcmods.json`. Every call on
this page was tried in game on build 24847281 unless it says otherwise. The game's rules and numbers
are in [mechanics/](mechanics/README.md), and its insides in
[reverse-engineering.md](reverse-engineering.md).

## Script mods

```
mods/my-mod/
  mod.json            {"name", "description", "enabled", "priority", "version", "author",
                       "uses": ["mod-menu"] (for its page), "settings_page" (optional, true)}
  scripts/main.lua    runs when the game starts
  scripts/*.lua       more files, for require("name") from main.lua
  settings.json       optional: the script's settings
```

Install (`python wcmods.py install`, or Install in the studio) with the game closed. wcmods turns each
mod's `scripts/` into a UE4SS mod of its own, `WCModsScript_<mod id>`, and writes its `main.lua`. That
sets up two globals, then runs yours:

- **`Game`**: `WCModsGame` (below).
- **`MOD`**: this mod.

| `MOD.` | What it is |
|---|---|
| `id`, `name`, `folder` | The mod's folder name, its name, and its folder on disk |
| `settings` | `settings.json` as a table (empty without one), read from the file each time the game starts, so what `save()` wrote is back after a restart. Change it and the script sees the change at once |
| `settingsFile` | Where `MOD.save()` writes, or nil |
| `save()` | Write `MOD.settings` back to `settings.json`, for the next time the game starts and the next install. Returns true, or false and why |
| `log(fmt, ...)` | Print `[Mod name] text` to `ue4ss\UE4SS.log` |
| `page(fn, {title, order, group})` | A page in the mod menu (`fn(ui)`, as in [SDK.md](SDK.md#wcmodsmenu)). The menu is a mod of its own; while it's off this does nothing and returns false |

**A settings page for free:** a mod with a `settings.json` and no page of its own gets one. It has a row
per setting (on/off, number, text, `"#rrggbb"` colours) and a Save button, and keys starting with `_` show as notes.
`"settings_page": false` in `mod.json` turns that off. The page is in the mod menu, so it shows while
the Mod menu mod is on; say `"uses": ["mod-menu"]` in `mod.json` so Clan Mod Studio shows that the
mod has one. A script that can't work without the menu says `"requires": ["mod-menu"]` instead.

`python wcmods.py new my-script --kind script` makes a new one to start from.
[game-tweaks](https://github.com/HexOffender/wcmods-examples/tree/main/game-tweaks), in wcmods-examples, is a complete one: it
keeps stamina full, holds the time of day, keeps the fresh-kill pile up and heals on a key, with its
settings on a page. Add it in the studio (or `wcmods add ../wcmods-examples/game-tweaks`), allow code
mods, and apply.

```lua
-- mods/my-mod/scripts/main.lua
local S = MOD.settings                       -- e.g. { keep_full = true }

Game.every(1, function()
    local cat = Game.cat()                   -- nil in menus and while loading
    if cat and S.keep_full then cat:setStamina(cat:maxStamina()) end
end)

Game.onKey("F6", function() Game.cat():heal() end)
Game.on("combatStart", function(fight) MOD.log("%d enemies", #fight:enemies()) end)
```

Errors in a script go to `UE4SS.log` with the mod's name. A broken script doesn't stop the others.

## `WCModsGame`

```lua
local Game = require("WCModsGame")   -- a script mod has it as Game already
```

### How it reaches the game

- **Reflection:** most of what scripts use is what the game itself exposes to Unreal's reflection:
  its managers, the quest manager's functions, the combat director, status conditions, the cheats
  manager's switches.
- **Mapped values:** the game's health, stamina, level, stat and clock values aren't reflected. They're
  native fields the reverse-engineering notes found the offsets of. `WCModsGame` maps each one with
  UE4SS's `RegisterCustomProperty`, so it reads and writes like any other property (`WCM_Value` and
  so on, listed in `Game.hidden`).
- **The game thread:** everything runs on the game thread, from a timer, an event, a key, a menu page or
  a painter.

**The rules that keep the game running** (they're why the module checks everything):
- **Never call a function on an object that isn't there.** UE4SS crashes the game inside its own code
  when you do, and `pcall` can't catch it. `Game.call(o, "Name", ...)` and every `Game` call check first.
  When you call a method yourself, check `Game.valid(o)` first. A far-away animal with no mesh loaded
  was enough to crash the game once.
- **UE4SS hands back placeholders, not nil:** an object that isn't there comes back as an invalid
  object, and a property the object doesn't have comes back as a `TrivialObject`. `Game.get` turns both
  into nil (or your default).
- **Objects last a level:** look things up again rather than keeping them. `Game.cat()` is cheap.
- **One thread:** don't use `LoopAsync` in a script that uses these modules (see SDK.md).

### Objects

| Call | Gives |
|---|---|
| `Game.valid(o)` | Whether `o` is a live object |
| `Game.get(o, "A.B.C", default)` | A property path, or `default` when any step is missing. Numbers index arrays (from 1) |
| `Game.set(o, "A.B", value)` | Set one; true, or false and why |
| `Game.call(o, "Function", ...)` | Call a function safely: `true, results...` or `false, error` |
| `Game.find("Class")`, `Game.findAll("Class")` | One object of a class (kept while it lasts) or all of them; short class names, e.g. `"WrcRoamingEnemy"` |
| `Game.object(path)`, `Game.load(path)` | An object by its path; load an asset |
| `Game.library(name)` | A function library for static calls: `GameplayStatics`, `KismetSystemLibrary`, `KismetMathLibrary`, `BFLSwtQuest`, `QuestManager`, `SaveManager`, … (`Game.libraries`) |
| `Game.className(o)`, `Game.name(o)`, `Game.fullName(o)`, `Game.parents(o)`, `Game.isA(o, "Class")` | What an object is |
| `Game.str(v)` | The text of an FString, FName or FText |
| `Game.tag("Quest.Main.1")`, `Game.tagName(tag)` | Gameplay tags to and from the game |
| `Game.vector(x, y, z)`, `Game.rotator(pitch, yaw, roll)` | Values to pass (the rotator keeps its pitch) |
| `Game.list(array)`, `Game.map(tmap)` | A TArray or TSet as a Lua list; a TMap as a table, keyed by tag name, object name or text |
| `Game.setTagCounts(tmap, {tag = n})` | Replace a `TMap<FGameplayTag, int32>` (rewards, costs) |
| `Game.properties(o, all)`, `Game.functions(o, all)` | What an object holds and can do: `{name, type, owner, value}` and `{name, owner, params = {{name, type, out}}, returns}`. Mapped values are included. `all` adds the engine's Actor/Object members |
| `Game.show(v)` | A short readable form of anything |

### The world

| Call | Gives |
|---|---|
| `Game.player()` | Your cat's actor (nil in menus and while loading) |
| `Game.controller()`, `Game.world()`, `Game.levelName()` | The player controller, the world, and its level: `"L_WorldMap_01_P"` for the forest |
| `Game.screens()` | The game's own screens and popups showing now (the inventory, the map, the pause menu, …) by class; empty while you're just playing. An overlay can hide while one is open |
| `Game.gameInstance()`, `Game.gameState()`, `Game.gameMode()` | The game's top objects |
| `Game.manager(name)` | One of the game's managers (below) |

**The managers** (`Game.managers` maps each name to its property on the game instance):

| Name | Class (in game) | Name | Class (in game) |
|---|---|---|---|
| `quests` | `BP_WrcQuestManager_C` | `save` | `WrcSaveManager` |
| `cheats` | `BP_WrcCheatsManager_C` | `combat` | `BP_WrcCombatManager_C` |
| `gui` | `BP_WrcGuiManager_C` | `npcs` | `BP_WrcNPCGenerationManager_C` |
| `tuning` | `BP_WrcTuningManager_C` | `effects` | `BP_WrcEffectManager_C` |
| `audio` | `BP_WrcAudioManager_C` | `sequencer` | `BP_WrcSequencerManager_C` |
| `tutorial` | `BP_WrcTutorialManager_C` | `paths` | `BP_WrcTrackPathManager_C` |
| `tracer` | `BP_WrcActorTracerManager_C` | `storage` | `BP_WrcStorageManager_C` |
| `config` | `BP_WrcGameConfig_C` | `flow` | `WrcFlowManager` |

Also `util`, `vfx`, `achievements`, `analytics`, `online`, `cloud`, `services`, `montages`, `records` and `challenges`.

### Timers, keys and events

| Call | Does |
|---|---|
| `Game.onFrame(fn)` | `fn(dt)` every frame |
| `Game.every(seconds, fn)`, `Game.after(seconds, fn)` | Every so often; once later. These return an id for `Game.cancel(id)` |
| `Game.onKey("F6", fn, {"CONTROL"}, help)` | `fn` on the game thread when the key (with modifiers) is pressed; with `help` ("Heal your cat") the mod menu's Overview lists it |
| `Game.onPress({"T", "Gamepad_DPad_Up"}, fn, help)` | `fn(key)` when any of the keys or controller buttons is pressed in the game's own input (Unreal's key names). Unlike `onKey`, it only hears them while the game has the focus, it hears the controller, and `agent key` can press them. Returns an id for `Game.cancel` |
| `Game.pressed(key)`, `Game.keyDown(key)` | Whether a key or button went down this frame, and whether it's held, in the game's own input, for a frame function |
| `Game.on(event, fn)`, `Game.off(handle)` | Listen to an event |
| `Game.emit(event, ...)` | Send one of your own (it reaches listeners in the same script) |

| Event | Arguments | How it's watched | Tried in game |
|---|---|---|---|
| `level` | new level name, old | polled twice a second | yes |
| `player` | your cat's actor or nil | polled | yes |
| `phase` | new, old (`Game.enums.phase`) | polled | yes |
| `combatStart` / `combatEnd` | a fight (below) | polled | yes |
| `itemPickedUp` | tag, how many, new total | hook on the HUD's `OnItemPickedUp` | yes |
| `questStatus` | quest, status, exact | hook on `SwtQuestGameplayGameState:OnQuestStatusChanged` | hooked; not yet seen firing |
| `genericEvent` | name | hook on `SwtGameUtil:BroadcastGenericEvent` | hooked; not yet seen firing |
| `damage` | `{target, damage, missed, stance, status}` | hook on the combat director's `OnRegisterDamage` | hooked; not yet seen firing (no hit was made in testing) |
| `turnEnded` | | hook on `OnCombatantTurnEnded` | hooked; not yet seen firing |
| `status` | fighter, status | hook on `ApplyStatusType` | hooked; not yet seen firing |

### Hooks

`Game.hook(path, fn, {post = true})` runs `fn(self, args...)` when the game calls one of its functions.
The path is `"/Script/<Module>.<Class>:<Function>"`; `wcmods inspect` and the inspector list a class's
functions. It returns a handle for `Game.unhook(h)`.

`Game.hookRaw(path, fn)` gives `fn(self, params)`, where `params[i]:get()` and `params[i]:set(v)` read
and change the call's own parameters before the game uses them. Seen working in game: a hook changed
the tag a quest lookup was asked about.

Some limits:
- **Post hooks** run after the call, and by then the parameters may already be cleared.
- **Only calls through Unreal fire hooks.** Unreal's function calls (Blueprints, delegates, Lua) fire
  them; native C++ calling C++ directly doesn't.
- **Hooks are per script:** they come off when the script stops.

### Your cat (and other cats)

`Game.cat()` is yours. `Game.cat(actor)` wraps any cat or animal; it works on fighters too.

| Method | Gives or does | Tried in game |
|---|---|---|
| `name()`, `clan()`, `traits()` | `"Callie"`, `"RiverClan"`, `{"Brave", "Energetic"}` (traits from the last save) | yes |
| `customization()` | The looks and name IDs: `ClanType`, `BodyValue`, `EarIdx`, `FurColorIdx`, `PrefixNameId`, `CatSize`, … | yes |
| `health()`, `maxHealth()`, `setHealth(v)`, `setMaxHealth(v)`, `heal()` | Health (the maximum is Prowess) | read and set |
| `stamina()`, `maxStamina()`, `setStamina(v)`, `setMaxStamina(v)` | Exploring stamina | read and set |
| `staminaRegen()`, `setStaminaRegen(v)` | Stamina back per second (20) | read |
| `combatStamina()`, `maxCombatStamina()`, `setCombatStamina(v)` | Fight stamina (the maximum is 0.4 × Prowess + Stamina) | read |
| `level()`, `setLevel(n)`, `xp()`, `setXp(v)`, `xpNeeded()` | Level and experience (your cat) | read |
| `stats()`, `setStat(name, v)` | `{Prowess, Strength, Resilience, Instinct, Agility, Stamina}` (your cat; a fight's own copy is under `Game.fighter`) | read and set |
| `location()`, `teleport(x, y, z)` / `teleport({X,Y,Z})` / `teleport(actor)` | Where it is; move it | yes |
| `scale()`, `setScale(f)` | Size (the same call as the menu's size cheat) | read |
| `setTimeDilation(f)` | This cat's own time: 2 is twice as fast | no |
| `kind()` | `"Cat"`, `"WeakMice"`, `"BossFox"`, … | yes |
| `rewards()`, `setRewards({tag = n})` | What an animal drops when beaten | read; a change isn't what it drops, which comes from the game's character table (`DT_Characters`) |
| `applyStatus("Poisoned")`, `removeStatus(s)`, `clearStatus()` | Status conditions | applied without an error; the effect wasn't watched |
| `component(kind)` | The raw component: `"Health"`, `"Stamina"`, `"StaminaCombat"`, `"Level"` | yes |

**When changes stick:** a value set here is the game's own value, so it lasts until the game sets it
again. Examples are a level-up working out the stats, a fight setting up a fighter, or loading a save.
The game saves whatever it holds at its next save.

### Cats of a mod's own (`Game.npcs`)

`Game.npcs.spawn(opts)` puts a cat of the mod's own in the world: one of the game's clan cats (its
"filler" class, `BP_Quest_Filler_C`) with the colours, eyes and size you give it. wcmods keeps it
there: the cat is spawned again when the game unloads it (a level change, an area far off), and its
colours go back on whenever the game sets it up again. It isn't one of the save's cats, so it's gone
when the script stops, and it never ends up in your save.

```lua
local npc = Game.npcs.spawn({
    at = { -60040, -200, 813 }, yaw = 180,     -- where it stands (World.location of your cat, say) and faces
    size = 0.9, eyes = 15,                      -- the game's cat size; an iris colour slot (0-24)
    colours = { fur = "#8c919e", pattern = "#3a3d47", markings = "#f2f2f7", nose = "#c98a92", paws = "#d9a0a8" },
})
Game.every(0.5, function()
    if npc:near(300) then npc:face() end       -- turns to your cat when it's within 3 m
end)
```

| Option or method | |
|---|---|
| `at`, `yaw`, `level` | Where it stands (on the ground below `at`), which way it faces (degrees), and the level it's in (by default the one it first appears in) |
| `ground` | `false` puts it exactly at `at`, not on the ground below |
| `colours` | `fur`, `pattern`, `markings`, `nose`, `paws`, `whiskers`, `ears` as `"#rrggbb"`; the rest stay the game's |
| `eyes`, `size` | An iris colour slot, as in `palette.json`, and the cat's size (the game's are about 0.4–1.1) |
| `prefix`, `suffix` | Name IDs (`"STR_CAT_NAME1"`, `"_PAW"`), for the name the game itself knows it by |
| `npc:valid()`, `npc:actorOrNil()` | Whether it's in the world now, and its actor |
| `npc:location()`, `npc:distance()`, `npc:near(cm)` | Where it is; how far your cat is; whether your cat is within `cm` (300) |
| `npc:face(target)`, `npc:moveTo(x, y, z)`, `npc:remove()` | Turn to a place or actor (your cat with none); move it, onto the ground there; take it away for good |
| `Game.npcs.spot(cm, side)` | A place beside your cat with room for a cat (220 cm away, to its front left by default), and a yaw facing your cat: `local at, yaw = Game.npcs.spot()` |

Move a cat with `npc:moveTo` rather than removing it and spawning it again: the game chooses a new
cat's patterns itself (wcmods puts back only the colours), so a new one can look different. That also
happens when the game unloads the cat and wcmods spawns it again.

`Game.trace(from, to)` gives where a straight line first hits something, and `Game.ground(x, y, z)`
the height of the ground below a place.

The game gives these cats no Talk prompt or name of their own on screen; a script draws them with
`WCModsDraw`. What they say can go in the game's own dialogue box:

| Call | |
|---|---|
| `Game.dialogue.say(name, text)` | Show the game's dialogue box (`WBP_QuestGiver_Dialogue`) with a speaker's name and a line, with its own fade-in; again with another line to change it. Returns false and why if the box can't be made |
| `Game.dialogue.hide()`, `Game.dialogue.showing()` | Fade it out; whether it's up |
| `Game.dialogue.busy()`, `Game.dialogue.claim()` | Whether another mod's cat is talking (each mod has its own box, so two could overlap); take the box for this script's talk, false if it's taken. Check `busy()` before starting a talk |

The box is only the picture: it takes no input, so the script moves the talk on with its own key (the
box shows Enter, the game's own key for it, so take that too). The answer buttons stay hidden. [custom-npc](https://github.com/HexOffender/wcmods-examples/tree/main/custom-npc) in
wcmods-examples does: a name over the cat's head, and lines to say on a key.
[moonlit-path](https://github.com/HexOffender/wcmods-examples/tree/main/moonlit-path) builds a
questline on one.

### Items

| Call | Gives or does |
|---|---|
| `Game.items.list()`, `Game.items.count(tag)` | Your items, `{["Gameplay.Inventory.Materials.Dandelion"] = 6, …}`: as of the game's last save (it writes `WrcGame.json` each time), with pickups since then from the HUD's pickup messages |
| `Game.items.drop(tag, count, where)` | A pickup holding the items on the ground by your cat (or at `where`), for the cat to pick up as usual. It returns the actor. Seen in game: the cat collects it with Interact, and `itemPickedUp` fires |
| `Game.items.info(tag)`, `Game.items.type(tag)` | What the quest manager knows of an item (often nothing) |

**Why items can't be put in the inventory directly:** the inventory is native, with no reflected way to
change it. Triggering a pickup's `OnInteracted` from Lua plays its effect and removes it, but doesn't
hand over the items. So `drop` uses the game's own pickup: the rewards go through the normal path when
the cat picks it up.

### The world's state

| Call | Gives or does |
|---|---|
| `Game.time.get()` | The clock: hours, minutes, seconds |
| `Game.time.seconds()`, `Game.time.setSeconds(s)`, `Game.time.set(h, m, s)` | Seconds into the day (21600 is 6:00); set the clock |
| `Game.freshKill.value()`, `.max()`, `.set(v)`, `.level()` | The camp's fresh-kill pile (0–100), and Full/Abundant/Good/Scarcity/Critical |
| `Game.freshKill.timer()`, `.decayTime()`, `.setDecayTime(v)` | Seconds since it last went down, and how often it does (90) |

### Quests

| Call | Gives or does |
|---|---|
| `Game.quests.all()` | Every quest: `{quest, id, graph, type, status, result, tracked, xp, rewards}`. `id` comes from its quest graph: `"Tutorial"`, `"Deliver"`, `"RiverClan_Unique1"` |
| `Game.quests.tracked()` | The quest being followed, or nil |
| `Game.quests.report(id, {title, status, objective, progress})` | List a quest of the mod's own on the mod menu's Quests page: `status` is `"available"`, `"active"` or `"done"`. Report again when it changes; `nil` takes it off. `Game.quests.reported()` reads them back |
| `Game.quests.status(tag)`, `.result(tag)`, `.successes(tag)` | By quest tag: `"QuestAvailable"`, `"OngoingQuest"`, … |
| `Game.quests.start(tag)`, `.give(tag)`, `.track(quest, on)` | The quest manager's own StartQuestOfTag, GiveQuestOfTag and SetTracked. Not tried yet; they can move the story on |
| `Game.quests.chapter()` | `"Chapter00"` |

### Fights

`Game.fight()` is the fight going on now (or nil). `Game.combat.active()` says whether there is one.

| Fight | Gives |
|---|---|
| `players()`, `enemies()`, `all()` | The fighters |
| `turnOrder()`, `current()`, `mainEnemy()` | Cats, in this round's order; whose turn it is |
| `kind()` | The director's class (story, boss, skirmish, defender…) |

A fighter (`Game.fighter(cat or actor)`) is a cat's combat component, set up when a fight starts:

| Fighter | Gives or does |
|---|---|
| `stats()`, `setStat(name, v)` | This fight's stats (the damage formula uses these) |
| `level()`, `setLevel(n)`, `stance()` | Its level, and its stance now |
| `move()`, `moveTag()`, `setMove({Damage = 80, Accuracy = 1})` | The move it picked (its AttackMove row), and changing it before it lands (not tried: no move was picked in testing) |
| `targets()`, `cat()` | Who it's attacking; the cat itself (health, status…) |

**Seen in game** (a level 20 cat against a weak bird):
- The fighter stats matched the stat formula.
- Health matched Prowess.
- Fight stamina was 0.4 × Prowess + Stamina, for both sides.
- Setting the bird's Strength and health worked.

**There's no way to end a fight from a script yet.** The combat manager's `EndCombat` ends it, but
leaves your cat with no body and the fight menu on screen.

### The game's developer switches

The cheats manager carries the developers' own settings. The release build obeys some and ignores
others, so try each one.

| Call | Does |
|---|---|
| `Game.dev.list()` | Every on/off and number setting, with its value (about 50) |
| `Game.dev.get(name)`, `Game.dev.set(name, v)` | e.g. `bAlwaysSucceedAttack`, `bFastHousingCrafting`, `GodMode`, `bAllowCatSizeOverride`, `CatSizeOverride` |
| `Game.dev.fullResource("Stamina", true)` | Keep a resource full: Health, Level, Stamina, StaminaCombat, Currency, FreshKill (the game's `AlwaysHasFullResource`; the switch was set in game, but whether the game obeys it wasn't checked) |

### The save

| Call | Gives |
|---|---|
| `Game.save.file()`, `Game.save.slotData()` | The whole save as of the game's last save, as a table; this cat's slot in it |
| `Game.save.write()` | Save now (the game's own Save) |
| `Game.save.slot()` | The save slot in use |
| `Game.save.progression(primary, sub)`, `setProgression`, `setting`, `setSetting` | The save manager's number stores. What their keys are isn't worked out yet |

### JSON and enums

- **JSON:** `Game.json.encode(v)`, `Game.json.decode(text)` (null is `Game.json.null`), and
  `Game.json.list(t)` to write an empty table as `[]`.
- **Enums:** `Game.enums.<name>` maps each way, name to number and number to name (`Game.enums.status.Poisoned
  == 3`). The enums are `clan`, `rank`, `trait`, `stance`, `status`, `stat`, `resource`, `questStatus`,
  `questResult`, `questType`, `objectiveStatus`, `phase`, `itemType` and `characterType`.

### Mapped values

`Game.hidden` lists every mapped field by class, as `{name, offset, type}`. Add your own the same way:

```lua
RegisterCustomProperty({ Name = "MY_Field", Type = PropertyTypes.FloatProperty,
                         BelongsToClass = "/Script/SwtAdventure.SwtAdventureGameplayGameState", OffsetInternal = 0x438 })
print(Game.gameState().MY_Field)
```

Only fixed-size types work (numbers, booleans, names, strings, objects, and arrays of those), not
maps or structs. To find an offset, read the object's memory while you watch the game (the notes
describe how). Offsets can move when the game updates; the build these are for is 24847281.

## The game bridge

With code mods allowed, every install adds `WCModsBridge`, a small UE4SS mod. Several times a second it
looks for a request from wcmods, runs the Lua in it, and writes back what it printed and returned. It
also writes a status file once a second. Requests and replies are files in
`%LOCALAPPDATA%\Wrc\Saved\WCMods\bridge\`, written whole and then renamed, one request at a time.

```bash
python wcmods.py game
```

```bash
python wcmods.py lua "Game.cat():name()"
```

```bash
python wcmods.py lua -f my-test.lua
```

```bash
python wcmods.py inspect "Game.manager('quests')"
```

```bash
python wcmods.py find WrcRoamingEnemy
```

- **`game`:** whether the game is running with the bridge, and where.
- **`lua`:** an expression prints its value; a chunk can `print` and `return`. Globals stay between runs.
- **`inspect`:** an object's classes, properties (with values) and functions (with parameters).
- **`find`:** a class's objects, with where they are.
- **`--json`:** prints the raw reply, for scripts.

From Python, `wcmods.bridge.Bridge(cfg).run(code)` returns `{"ok", "result", "output", "error", "ms"}`.

Clan Mod Studio has the same as its **Console** page: a Lua box with examples, and an inspector that
opens an object's properties one click at a time.

The bridge only takes requests from files on your own computer, and only runs when code mods are
allowed, as the rest of this page does.

## In the mod menu

The mod menu (Insert) builds these pages on `WCModsGame`, in the side bar's groups (docs/SDK.md,
"`WCModsMenu`"). They're live, and a change applies at once:

- **Overview:** your cat's health, stamina and experience as bars, the territory, area, time and
  fresh-kill pile, the quest you follow, quick buttons (Heal, Full stamina, Morning, Evening), the
  keys scripts use (from `Game.onKey`'s `help` and `Menu.key`), and where things are in the menu.
- **Stats:** health, stamina and its regeneration, fight stamina, size, level and experience, and
  the six stats.
- **World:** the clock, with presets and "Hold this time", and the fresh-kill pile, with "Keep it at
  least here". The area is the last one your cat walked into (the game says so as you cross the
  boundary).
- **Travel:** where your cat is, Back (to where it was before the last jump), spots you save by name
  (kept in `%LOCALAPPDATA%\Wrc\Saved\WCMods\places.json`), the game's checkpoints, and every area by
  territory. A jump lands on the ground.
- **Items:** what you carry, by kind, and an item to drop by your cat as a pickup.
- **Quests:** the quest you follow and its objectives (with "Go to objective" when an objective has
  a place), and every quest by state, with Follow. The titles are the game's own, for your rank.
- **Fight:** during a fight, both sides with health and stamina, stats, stance and moves; Heal,
  Weaken, Cure status, and "Double what it drops" (the extra is a pickup by your cat once the fight
  is won).
- **Game switches:** the game's developer switches: "always full" for each resource, and every on/off
  and number setting.
- **Log:** the end of UE4SS.log, newest first: the mods' lines, the errors, or everything.
- **Inspector** (with code mods allowed): start from your cat, the player state, the game state, the
  game instance, the fight, any manager, or a class name. You'll see the class chain, every property
  with its value, and every function. Numbers and switches can be changed in place, object properties
  open with a click, and functions without parameters can be called.
- **Console** (with code mods allowed): type Lua, Run, and see what it printed and returned.

A script mod with a `settings.json` and no page of its own gets one under Mods: a row for each
setting (`heal_key` shows as "Heal key"), and Save.

## Testing in the game

`python wcmods.py agent ...` drives the running game for you or an agent:

- **Run the game:** start it, play into the forest, run Lua.
- **Use the menu:** read and use the mod menu's pages by their labels.
- **Act and look:** press keys, walk, and take pictures.
- **Test:** run `tests/game`, which leaves a report with pictures.

See [agent.md](agent.md).

## Editor support

```bash
python wcmods.py game types
```

That asks UE4SS, through the bridge, to write Lua type annotations for every class the game has loaded
into `ue4ss\Mods\shared\types\` (about 8 MB). Point the Lua language server (VS Code's "Lua" extension)
at that folder for autocompletion of the game's classes. Run it once you're in the world, so the
gameplay Blueprints are loaded.

The full class list with offsets comes from UE4SS's header dump (`GenerateSDK`, which also runs
through the bridge). It's how this module was written, and it's the place to look for anything not
wrapped here: `python wcmods.py lua "GenerateSDK()"` writes it to `ue4ss\CXXHeaderDump\`.
