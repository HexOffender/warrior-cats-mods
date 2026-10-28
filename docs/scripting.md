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
| **Live** | Clan Mod Studio's Try Lua in the game (under Advanced), the mod menu's Lua (advanced) page, and `wcmods lua`, which run Lua in the game while it's open | [The game bridge](#the-game-bridge) |

All of them are code, so they only run with `"allow_code_mods": true` in `wcmods.json`. Every call on
this page was tried in game on build 24847281 and rechecked on 26184573, patch 1.1 ([reverse-engineering.md, Game updates](reverse-engineering.md#game-updates)), unless it says otherwise. The game's rules and numbers
are in [mechanics/](mechanics/README.md), and its insides in
[reverse-engineering.md](reverse-engineering.md).

## Script mods

```
mods/my-mod/
  mod.json            {"name", ...; "uses": ["mod-menu"] for its page; "settings_page": false for none}
                      (every key: SDK.md, Mod folder)
  scripts/main.lua    runs when the game starts
  scripts/*.lua       more files, for require("name") from main.lua
  settings.json       optional: the script's settings
```

Install (`python wcmods.py install`, or Apply to game in the studio) with the game closed. wcmods turns each
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
| `log(fmt, ...)` | Print `[Mod name] text` to `ue4ss\UE4SS.log`. It's `string.format` underneath, so a `%` in the text is written `%%` |
| `page(fn, {title, order, group})` | A page in the mod menu (`fn(ui)`, as in [SDK.md](SDK.md#wcmodsmenu)). The menu goes in with UE4SS, as scripts do; returns false only if `WCModsMenu` is missing. A page made later, from a timer, takes the place of the settings page below rather than being a second one |

**A settings page for free:** a mod with a `settings.json` and no page of its own gets one. It has a row
per setting (on/off, number, text, `"#rrggbb"` colours) and a Save button, which says under it whether it saved;
keys starting with `_` show as notes ([formats.md](formats.md#scripts-and-settingsjson) has which value makes
which row, and what Save writes). `"settings_page": false` in `mod.json` turns that off. The page is in the mod
menu, which goes in with every install; say `"uses": ["mod-menu"]` in `mod.json` so Clan Mod Studio shows that
the mod has one.

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

Errors in a script go to `UE4SS.log` with the mod's name: the script's own, and `WCModsGame`'s about it (a
timer's, a key's, a hook's), once, then once a minute with how many more times it happened. The script keeps
running, and a broken script doesn't stop the others. The files are loaded by their names in the mod, so an
error says `scripts/main.lua:12: ...`.

**Where a script's words and errors show:**
- **In Clan Mod Studio:** before any Apply, the mod's card on the Mods page says what would stop its Lua from
  loading at all (a `function` with no `end`, a string left open, by file and line) and what's wrong with its
  `settings.json`. After the game has run, the card says whether the script loaded when the game last started
  (or why not), and under More, What it said has its lines, newest first.
- **In the game:** a script that didn't start is named at the top of the screen for ten seconds once your cat
  is in the world, and in red on the mod menu's Overview; the mod menu's Log page (Tools) shows the scripts'
  lines, a plain `print` too.
- **On disk:** `<game>\Wrc\Binaries\Win64\ue4ss\UE4SS.log`, a new one each time the game starts.

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
- **Some calls are costly every frame:** `Game.save.file()` and `Game.items.list()` read and decode the whole
  save (kept for a second), and `Game.quests.objectives(q)` looks through every objective in the game each time.
  Call them from `Game.every`, not `Game.onFrame`.

### Objects

| Call | Gives |
|---|---|
| `Game.valid(o)` | Whether `o` is a live object |
| `Game.alive(o)` | Whether it's live and staying: not destroyed, or left behind by a level that unloaded (UE4SS calls those valid until the engine collects them) |
| `Game.get(o, "A.B.C", default)` | A property path, or `default` when any step is missing. Numbers index arrays (from 1) |
| `Game.set(o, "A.B", value)` | Set one; true, or false and why |
| `Game.call(o, "Function", ...)` | Call a function safely: `true, results...` or `false, error` |
| `Game.find("Class")`, `Game.findAll("Class")` | One object of a class (kept while it lasts; never one on its way out, like the last level's HUD) or all of them; short class names, e.g. `"WrcRoamingEnemy"` |
| `Game.object(path)`, `Game.load(path)` | An object by its path; load an asset, a mod's own too (`/Game/WCMods/<mod>/...`, which UE4SS's `LoadAsset` can't find) |
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
| `Game.every(seconds, fn)`, `Game.after(seconds, fn)` | Every so often; once later. These return an id for `Game.cancel(id)`, which a function may call on itself |
| `Game.onKey("F6", fn, {"CONTROL"}, help)` | `fn` on the game thread when the key (with modifiers) is pressed; with `help` ("Heal your cat") the mod menu's Overview lists it. The key is one of UE4SS's names, in capitals (`F1`-`F12`, `A`-`Z`, `SPACE`, `ONE`-`NINE`; the modifiers `SHIFT`, `CONTROL`, `ALT`) or its number. Returns an id for `Game.cancel`; for a name UE4SS doesn't know it logs "no key called f6 (did you mean F6? ...)" and returns false, and the rest of the script runs |
| `Game.onPress({"T", "Gamepad_DPad_Up"}, fn, help)` | `fn(key)` when any of the keys or controller buttons is pressed in the game's own input (Unreal's key names). Unlike `onKey`, it only hears them while the game has the focus, it hears the controller, and `agent key` can press them. Returns an id for `Game.cancel` |
| `Game.pressed(key)`, `Game.keyDown(key)` | Whether a key or button went down this frame, and whether it's held, in the game's own input, for a frame function |
| `Game.on(event, fn)`, `Game.off(handle)` | Listen to an event |
| `Game.emit(event, ...)` | Send one of your own (it reaches listeners in the same script) |

| Event | Arguments | How it's watched | Tried in game |
|---|---|---|---|
| `level` | new level name, old | polled twice a second | yes |
| `player` | your cat's actor or nil | polled | yes |
| `phase` | new, old (`Game.enums.phase`) | polled | yes |
| `combatStart` / `combatEnd` | a fight (below); `combatEnd` has nothing | polled | yes |
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
| `level()`, `setLevel(n)`, `xp()`, `setXp(v)`, `xpNeeded()` | Level and experience (your cat: only your cat has a level component out of a fight, so another cat's are nil, and setting them gives false and why) | read |
| `stats()`, `setStat(name, v)` | `{Prowess, Strength, Resilience, Instinct, Agility, Stamina}` (your cat, as above; a fight's own copy, any fighter's, is under `Game.fighter`) | read and set |
| `location()`, `teleport(x, y, z)` / `teleport({X,Y,Z})` / `teleport(actor)` | Where it is; move it | yes |
| `scale()`, `setScale(f)` | Size (the same call as the menu's size cheat) | read |
| `setTimeDilation(f)` | This cat's own time: 2 is twice as fast | no |
| `kind()` | `"Cat"`, `"WeakMice"`, `"BossFox"`, … | yes |
| `rewards()`, `setRewards({tag = n})` | What an animal drops when beaten | read; a change isn't what it drops, which comes from the game's character table (`DT_Characters`) |
| `applyStatus("Poisoned")`, `removeStatus(s)`, `clearStatus()` | Status conditions, through the game's own functions | yes: the member below changed with each |
| `status()`, `statusRounds()` | The condition it has now (`"Poisoned"`, `"None"`) and how many rounds it has had it, from the component's own members; each round's end rolls rounds × 20% to shake it off (don't call the component's `ProcessEndOfRound` outside a fight: with Poisoned it needs the fight's director) | yes: applied, counted over rounds, cured and cleared |
| `senses()`, `setSense(name, v)` | An animal's senses, its own copy of its size class's tuning: `ConeAngle`, `ConeDistance`, `SoundRadius`, `SoundSpeed`, `PounceDistance`, `ProximityDistance`, `TargetDistance`, `WalkSpeedRoaming`, `WalkSpeedChasing`, `ZoneEntryDistance`, `ZoneExitDistance`, `ReactToChase` and `Range` (the size class); nil for a cat | read: a mouse's matched the tuning's Small values |
| `ai()` | What an animal's AI knows: `detected`, `target` (a Cat), `hunted`, `reactionTime`, and `blackboard` for the rest by key (`bb:GetValueAsBool(FName("Hunted"))`) | read |
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
| `look`, `slots` | Its shape, as in `cats.json`: `{ body = 6, fur = 2, tail = 7, ears = 3, eyes = 1, whiskers = 4, face = 5, pattern = 12, marking = 3 }` (0–9, pattern and marking 0–20); and the colour slots it wears, `{ fur = 9, pattern = 4, marking = 0 }`. What they leave out, and the eye colour without `eyes`, is made up each time it's spawned |
| `prefix`, `suffix` | Name IDs (`"STR_CAT_NAME1"`, `"_PAW"`), for the name the game itself knows it by |
| `npc:valid()`, `npc:actorOrNil()` | Whether it's in the world now, and its actor |
| `npc:location()`, `npc:distance()`, `npc:near(cm)` | Where it is; how far your cat is; whether your cat is within `cm` (300) |
| `npc:face(target)`, `npc:moveTo(x, y, z)`, `npc:remove()` | Turn to a place or actor (your cat with none); move it, onto the ground there; take it away for good |
| `Game.npcs.spot(cm, side)` | A place beside your cat with room for a cat (220 cm away, to its front left by default), and a yaw facing your cat: `local at, yaw = Game.npcs.spot()` |

Move a cat with `npc:moveTo` rather than removing it and spawning it again: a new cat's look is made up
again (all of it, or what its `look` and `slots` leave out), so a new one can look different. That also
happens when the game unloads the cat and wcmods spawns it again. Give it a whole `look`, `slots` and
`eyes` and it looks the same every time.

`Game.trace(from, to)` gives where a straight line first hits something, and `Game.ground(x, y, z)`
the height of the ground below a place.

**The game's own label and Talk prompt.** The game fills in and shows these only for the cats it set up
itself, so wcmods does it for a mod's cats. The label is the one the game's quest givers wear: its icon, a
line in green, the name and the role. The prompt is the game's, with the glyph of its Interact key or
button, which follows the keyboard or the controller:

```lua
npc:label({ name = "Brindlemoon", title = "Elder", extra = "A Soft Nest", icon = "available" })
npc:prompt("Talk")
Game.npcs.onInteract(function(who)
    if who == npc then Game.dialogue.say("Brindlemoon", "Good hunting.") end
    if who == nil then Game.dialogue.hide() end      -- Interact again while the box is up
end)
```

| Call | |
|---|---|
| `npc:label({name, title, extra, icon, range})` | The game's label over its head: the name, the title under it, `extra` (a line above it, in the game's green), and `icon`, one of the game's quest marks: `"available"` (a new quest), `"ongoing"`, `"done"` (to hand in). It shows while your cat is within `range` cm (2000). `npc:label(nil)` takes it away |
| `npc:prompt(text, reach)` | The game's prompt ("Talk") while your cat is within `reach` cm (250), at the cat, or at the screen's edge on its side when it's out of view. The cat in view comes first, and the game's own prompt (a pickup, a tunnel, its own cats) wins over it. `npc:prompt(nil)` takes it away |
| `Game.npcs.onInteract(fn)` | `fn(npc)` when the game's Interact is pressed with that cat's prompt showing; `fn(nil)` when it's pressed while this script's dialogue box is up, so the same key moves a talk on |
| `Game.npcs.interactKeys()` | The keys Interact is on: the keyboard's and the controller's from your settings (`E`, `Gamepad_FaceButton_Bottom`), or where wcmods' in-game remap moved them (the shared variable `WCModsRemap.Player_Interact`), and the left mouse button, which the prompt shows |

**The game's quest HUD and map markers.** The objective panel, the quest banners and the minimap's markers
are the game's own too. The game shows them only for its own quests, so in Sandbox mode, which has none,
nothing of the game's takes them back:

| Call | |
|---|---|
| `Game.hud.objective({title, location, activity, goals})` | The game's current-objective panel, on the left: the quest's title, a place under it (with the game's pin), what to do now, and up to three `goals`, `{name, progress ("1/2"), icon (a texture's asset path), done}`. `Game.hud.objective(nil)` puts it away |
| `Game.hud.banner(kind, {kind, title, text, seconds})` | One of the game's banners, with its particles: `"begin"` (a quest taken up: its kind, "Quest", its title and the first objective), `"update"`, `"done"` ("Quest completed!") or `"failed"`. It goes after `seconds` (4.5) |
| `Game.mapMarker(where, {icon, border, map})` | A marker on the minimap and the world map, the game's own point of interest: `where` is a place (`{x, y, z}`) or an actor it follows; `icon` is `"search"` (a ?), `"talk"`, `"barter"`, `"freshkill"`, `"trainer"`, `"den"`, `"outpost"`, `"skirmish"`, `"madcat"`, a Clan, or a material's path; it stays at the minimap's edge when it's further off (`border = false` doesn't). Returns a marker with `remove()` and `moveTo(x, y, z)`; or nil and why for a place without its three numbers, or an actor that isn't there any more |
| `npc:mapMarker(icon)` | The same on a mod's cat, put back on it when it's spawned again; `npc:mapMarker(nil)` takes it off |

Where the label or prompt isn't wanted, a script draws its own with `WCModsDraw`. What they say goes in the
game's own dialogue box:

| Call | |
|---|---|
| `Game.dialogue.say(name, text)` | Show the game's dialogue box (`WBP_QuestGiver_Dialogue`) with a speaker's name and a line, with its own fade-in; again with another line to change it. Returns false and why if the box can't be made |
| `Game.dialogue.hide()`, `Game.dialogue.showing()` | Fade it out (a box a failed `say` left half made too); whether it's up |
| `Game.dialogue.busy()`, `Game.dialogue.claim()` | Whether another mod's cat is talking (each mod has its own box, so two could overlap); take the box for this script's talk, false if it's taken. Check `busy()` before starting a talk. The claim lasts while the box is up, however long the talk waits for a key, and `hide()` lets it go |

The box is only the picture: it takes no input, so the script moves the talk on with its own key (the
box shows Enter, the game's own key for it, so take that too). The answer buttons stay hidden. [custom-npc](https://github.com/HexOffender/wcmods-examples/tree/main/custom-npc) in
wcmods-examples does: a name over the cat's head, and lines to say on a key.
[moonlit-path](https://github.com/HexOffender/wcmods-examples/tree/main/moonlit-path) builds a
questline on one.

### Items

| Call | Gives or does |
|---|---|
| `Game.items.list()`, `Game.items.count(tag)` | Your items, `{["Gameplay.Inventory.Materials.Dandelion"] = 6, …}`: as of the game's last save (it writes `WrcGame.json` each time), with pickups since then from the HUD's pickup messages |
| `Game.items.drop(tag, count, where)` | A pickup holding the items on the ground by your cat (or below `where`), for the cat to pick up as usual. It returns the actor. A mod's herb or material lies there as its own model (items.json `model`), or as the game's pickup of the herb it's `like`. Seen in game: the cat collects it with Interact, and `itemPickedUp` fires |
| `Game.items.info(tag)`, `Game.items.type(tag)` | What the quest manager knows of an item (nothing, as shipped: its item stats table is empty), and an item's kind: the quest manager's answer where it has one, else from the tag: `"Consumable"` (herbs and pouches), `"Collectible"` (materials), `"Equipment"` (accessories) or `"Quest"`; nil for a tag that isn't an item's |

**Why items can't be put in the inventory directly:** the inventory is native, with no reflected way to
change it. Triggering a pickup's `OnInteracted` from Lua plays its effect and removes it, but doesn't
hand over the items. So `drop` uses the game's own pickup: the rewards go through the normal path when
the cat picks it up.

### Animations

Mods' animations ([SDK.md, Animations](SDK.md#animations-animationsjson)) and the game's own sequences,
played on a cat or an animal over what it's doing, in the slot its AnimBlueprint plays the game's
montages in:

```lua
Game.anims.play(nil, "my-mod/Wave")                         -- your cat, once
Game.anims.play(npc, "my-mod/Swim", { loop = true })       -- a clan cat, until it's stopped
Game.cat():animate("/Game/Art/Characters/CatMaster/Animations/A_CatMaster_Stretch_1.A_CatMaster_Stretch_1")
Game.anims.stop(npc)
```

| Call | Gives or does |
|---|---|
| `Game.anims.play(who, id, opts)` | Play an animation on `who` (an actor or a `Game.cat()`; your cat when nil): a mod's by its id (`"<mod id>/<id>"`), or one of the game's sequences by its path. `opts`: `loop`, `speed`, `blend` (seconds in and out); a mod's animation brings its own. Returns the montage playing it, or nil and why (`"Swim is for cat, not mouse"`) |
| `Game.anims.stop(who, blend)` | Stop what `play` started on it, blending out; true if something stopped |
| `Game.anims.playing(who)` | The id of what `play` started on it, while it plays; else nil |
| `Game.anims.list()` | Every mod's animation: `{["my-mod/Wave"] = {name, kind, path, loop, speed, blend, seconds, emote, key}}` |
| `Game.anims.kind(who)` | What it is, by its mesh: `"cat"`, `"mouse"`, `"bird"`... (nil for others) |
| `cat:animate(id, opts)`, `cat:stopAnimation(blend)` | The same on a `Game.cat()` |

A mod's animation is for one skeleton (its `for`): every cat with the game's cat mesh (yours, the clans',
quest givers) shares the cats', and each kind of animal has its own. Each UE4SS script has a Lua state of
its own, so `playing` and `stop` know what that script started (the emotes' script keeps its own).
Seen in game: an emote and a looping swim on your cat, a spin on a roaming mouse and on a bird. A far
or hidden animal doesn't move its bones until it's in view (the engine's way), though the montage plays.

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
| `team()`, `aiTier()`, `setAITier(t)`, `moveCount()` | Its team (`"Player"`, `"Enemy"`), the AI's tier for this fight (`"Tier1"`…`"Tier6"`; `"None"` for your cat) and how many moves it has to pick from: the game's own members, filled when the fight is set up (seen: a weak mouse at level 1, `"Tier1"`, 3 moves; your cat 3 moves and no tier) |

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
| `Game.save.folder()` | A folder for a script's own files: `WCMods` in the game's Saved folder, beside its saves. Every install makes it, and updating a mod or wcmods leaves it alone |
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
describe how). Offsets can move when the game updates; these were found on build 24847281 and
confirmed on 26184573 (patch 1.1).

## The game bridge

With code mods allowed, every install adds `WCModsBridge`, a small UE4SS mod. Several times a second it
looks for a request from wcmods, runs the Lua in it, and writes back what it printed and returned. It
also writes a status file once a second. Requests and replies are files in
`%LOCALAPPDATA%\Wrc\Saved\WCMods\bridge\` (beside the game's saves), written whole and then renamed, one
request at a time.

- **A request that isn't picked up within the timeout is withdrawn** (15 seconds; a loading screen, or the game
  held still behind another window): the bridge runs a request only once it has taken it, so one taken back
  never runs later. One the game took and is still running says so instead.
- **A line that runs on is stopped** after about a hundred million steps of Lua (a second or so), with the
  error "this line ran too long and was stopped". A call that hangs inside the game's own code isn't counted.
- **Allowing code mods asks for an Apply:** until the bridge is in the game, the studio counts "mods that run
  code are allowed now" as a change to apply, so Play applies first.

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

Clan Mod Studio has `lua` and `inspect` as its **Try Lua in the game** page (under Advanced in the side bar,
with code mods allowed): a Lua box with examples (Ctrl+Up and Ctrl+Down go back through the lines run), and an
inspector that opens an object's properties one click at a time, with the engine's own members too when asked.
`find` is the command line's only, and none of the page's examples scans the world: reading many objects at once
has crashed the game just after a level loads. A line at the top of the page says whether the game can hear the
studio: listening (and where), running but not answering (loading, or held still behind another window),
running without the studio's connection (code mods were allowed after the last Apply: close the game, Apply,
Play), or closed.

The bridge only takes requests from files on your own computer, and only runs when code mods are
allowed, as the rest of this page does. Any program on your computer that can write that folder can run Lua in
the game through it, as wcmods does.

## In the mod menu

The mod menu (Insert) has these pages built on `WCModsGame`, in the side bar's groups
([SDK.md, `WCModsMenu`](SDK.md#wcmodsmenu)). From At a glance to Game switches they're the Menu pages
mod's ([SDK.md, Menu pages](SDK.md#menu-pages)), a script like any other, built only on what this page
and SDK.md describe; the rest are the window's own. They're live, and a change applies at once:

- **Overview:** scripts that didn't start this time (in red, with why), the menu's keys, the keys scripts use
  (from `Game.onKey`'s `help` and `Menu.key`), and each group's pages.
- **At a glance:** your cat's health, stamina and experience as bars, the territory, area, time and
  fresh-kill pile, the quest you follow, and quick buttons (Heal, Full stamina, Morning, Evening).
- **Stats:** health, stamina and its regeneration, fight stamina, size, level and experience, and
  the six stats.
- **World:** the clock, with presets and "Hold this time", and the fresh-kill pile, with "Keep it at
  least here". The area is the last one your cat walked into (the game says so as you cross the
  boundary).
- **Travel:** where your cat is, Back (to where it was before the last jump), spots you save by name
  (kept in `places.json` in `Game.save.folder()`, `%LOCALAPPDATA%\Wrc\Saved\WCMods`), the game's
  checkpoints, and every area by territory. A jump lands on the ground.
- **Items:** what you carry, by kind, and an item to drop by your cat as a pickup.
- **Quests:** the quest you follow and its objectives (with "Go to objective" when an objective has
  a place), and every quest by state, with Follow. The titles are the game's own, for your rank.
- **Fight:** during a fight, both sides with health and stamina, stats, stance and moves; Heal,
  Weaken, Cure status, and "Double what it drops" (the extra is a pickup by your cat once the fight
  is won).
- **Game switches:** the game's developer switches: "always full" for each resource, and every on/off
  and number setting.
- **Log:** the end of UE4SS.log, newest first: Mods (every line a script printed, a plain `print` too),
  Errors (a script's errors and what goes with them, not UE4SS's own start-up names with "Error" in them), or
  Everything.
- **Inspector** (with code mods allowed): start from your cat, the player state, the game state, the
  game instance, the fight, any manager, or a class name. You'll see the class chain, every property
  with its value, and every function. Numbers and switches can be changed in place, object properties
  open with a click, and functions without parameters can be called. Find by class works once your cat is in
  the world, lists the first 30 and refuses the widest classes (`Actor`, `UserWidget`, ...), since reading
  thousands of objects has crashed the game.
- **Lua (advanced)** (with code mods allowed, for people who write scripts): type Lua, Run, and see what it
  printed and returned.

A script mod with a `settings.json` and no page of its own gets one under Mods: a row for each
setting (`heal_key` shows as "Heal key"), and Save, which says under it "Saved to settings.json." or why it
couldn't.

## The game's own menus and HUD

A C++ mod built with wcmods' SDK ([SDK.md, C++ mods](SDK.md#c-mods)) puts a `WCModsCpp.ui` table into every
script's state as the game starts, so a script can put a tab of its own in the game's pause screen, the
inventory or the settings, reach the HUD and its parts, keep an overlay, and make, place and style any of
the engine's controls, with the C++ doing the work. Widgets come back as UE4SS's own objects, so
everything a script can do with a widget (`:SetText(FText(...))`, `:SetVisibility(1)`, reading its
properties) still works on them. Any C++ mod with the SDK brings it (the C++ SDK test mod,
`tests/cpp-sdk`, does); without one, `WCModsCpp.ui` is nil, and a script checks before using it.

```lua
local ui = WCModsCpp and WCModsCpp.ui
if ui then
    -- A tab in the pause screen. Its page is there while the screen is up, made anew each time it opens
    -- (the game makes its screens anew), so the script fills it when it sees a new one.
    local id = ui.tab("WBP_GuiScreenPause_C", "My mod")
    local seen = 0
    local on = ui.check(MOD.settings.on)
    Game.onFrame(function()
        local page, generation = ui.tab_page(id)
        if page and generation ~= seen then
            seen = generation
            on = ui.check(MOD.settings.on)
            ui.add(page, { ui.heading("My mod"), ui.labelled("Enabled", on),
                           ui.labelled("Speed", ui.slider(MOD.settings.speed, 0.5, 3, 0.1)) })
        end
        if ui.changed(on) then MOD.settings.on = ui.checked(on) end
    end)
    -- The HUD's parts, and a label of your own over the game.
    ui.visible(ui.hud("mcGuiMinimap"), false)
    local canvas = ui.overlay("my-notes")
    local label = ui.text("Hello", { size = 48 })
    ui.add(canvas, label)
    ui.at(label, 100, 100)
end
```

Sizes are the game's own units (its UI is laid out for a 3840×2160 screen): a 52-point title and a
700-wide control look as the game's do. The script asks rather than being called: `ui.clicked(w)` and
`ui.changed(w)` are true on the frame a button was clicked or a value changed (the first ask starts the
watch), and `ui.tab_page(id)` gives the page and a count of how many times it has been built.

| `ui.` | Does |
|---|---|
| `tab(screen, title, id, {hide_panels, scroll, focus, mouse, inset})` | A tab in one of the game's screens by its class (`"WBP_GuiScreenPause_C"`, `"WBP_GuiPopupInventory_C"`, `"WBP_GuiPopupGameSettings_C"`), which the game's tab keys reach; gives back its id (the title's when `id` is nil). Keep the title short |
| `tab_page(id)`, `tab_active(id)`, `remove_tab(id)`, `tabs()` | The page (a column to add rows to) and its build count while the screen is up, else nil; whether the game's navigation is on the tab; taking it out; every id |
| `screen(class)`, `hud()`, `hud(part)` | A screen of the game's while it shows (`screen("WBP_GuiPopupInventory_C")`); the HUD; one of its parts by name (`hud("mcGuiMinimap")`, `mcGuiEnergyBar`, `mcGuiQuestObjective`, `CanvasOver` to add to) |
| `overlay(name, layer, passive)`, `remove_overlay(name)` | A canvas of the script's own on the viewport, by name, kept; `passive` (the default) lets the mouse through. It goes with the level and comes back empty when asked for again |
| `make(kind)`, `game_widget(class or widget)` | Any of the engine's widgets by class (`"TextBlock"`, `"Button"`, `"CheckBox"`, `"Slider"`, `"SpinBox"`, `"ComboBoxString"`, `"EditableTextBox"`, `"ProgressBar"`, `"Image"`, `"Border"`, `"SizeBox"`, `"ScrollBox"`, `"CanvasPanel"`, `"WidgetSwitcher"`... any in `/Script/UMG`), plain; one of the game's own widget Blueprints by its class path or the class of a widget you have |
| `text(str, {size, color, wrap, justify})`, `heading(str)`, `note(str)` | Text in the game's font; a heading; smaller grey text. `text(widget)` reads a widget's text and `text(widget, str)` sets it |
| `button(label, color)`, `check(on)`, `slider(value, lo, hi, step)`, `number(value, lo, hi, step)`, `input(text, hint)`, `choice({options}, selected)`, `progress(fraction, color)`, `image(path, w, h)`, `rect(color, w, h)` | The controls, styled for the game's screens |
| `hbox()`, `vbox()`, `scroll()`, `border(color, {padding})`, `box(w, h)`, `spacer(w, h)`, `canvas()`, `row({widgets}, gap)`, `labelled(label, control, width)`, `scaled(control, width)` | Layouts, a row, a labelled control as the game's settings rows, a control grown to the game's size: a check box by a render transform in a box of its drawn size; a number box, text box or drop-down in a scale box with its font set to `text_size / control_scale` so its text comes out at the theme's size (`font(w, size)` after `labelled` for another); a button, text or layout as it is |
| `add(parent, child)`, `add(parent, {children})`, `remove(widget)`, `remove(parent, child)`, `clear(widget)` | Put a widget in a panel or content widget (gives back the slot); take one out; take every child out |
| `parent(w)`, `children(w)`, `find(w, name)`, `find_all(w, class)`, `slot(w)` | The tree: the widget it sits in, the widgets in it, one by name anywhere down the tree, every one of a class, its slot |
| `place(slot or widget, {padding, fill, halign, valign, anchors, offsets, position, size, alignment, auto, layer, stretch, row, column})`, `at(w, x, y)` | How a widget sits in its slot (a box's room and share, a canvas's anchors, place and size, a grid's cell); on a canvas, its top-left at a place |
| `visible(w, mode)`, `visible(w)` | Shown (`true` or `"shown"`), `"visible"` (taking input), `"passive"` (letting input through), `"hidden"`, `"collapsed"` or `false`; asked, its mode and whether it's drawn |
| `enabled(w, on)`, `opacity(w, f)`, `focus(w)`, `focused(w)`, `hovered(w)`, `valid(w)` | Enabled; opacity; the keyboard's focus; the mouse over it; whether the game still has it |
| `font(w, size, typeface)`, `color(w, hex)`, `tint(w, hex)`, `wrap(w, on)`, `justify(w, how)`, `hint(w, text)`, `padding(w, l, t, r, b)`, `size(w, w, h)`, `scale(w, x, y)`, `angle(w, deg)`, `translate(w, x, y)`, `tooltip(w, text)`, `image(w, path)` | How it looks |
| `value(w, v)`, `value(w)`, `checked(w, on)`, `range(w, lo, hi, step)`, `options(w, {...})`, `options(w)`, `option(w, s)`, `option(w)`, `active(w, i)`, `play(w, animation, reverse)` | What a control holds and offers |
| `clicked(w)`, `changed(w)` | True on the frame a button was clicked or a value changed since the last ask |
| `viewport()`, `cursor(on)`, `theme()`, `theme({...})` | The viewport's width, height and scale; the mouse cursor; the helpers' look (`text_size`, `heading_size`, `text`, `heading`, `muted`, `accent`, `button`, `panel`, `typeface`, `game_font`, `control_scale`, `control_width`) |

Colours are `"#rrggbb"` or `"#rrggbbaa"`, as an image editor shows them. The functions run on the thread
that calls them: a script calls them from its frame loop or a key, on the game thread, never from
`LoopAsync`. Two scripts (or a script and a C++ mod) can each have tabs in one screen.

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
