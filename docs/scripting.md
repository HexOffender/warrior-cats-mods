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
| `settings` | `settings.json` as a table (empty without one), read from the file each time the game starts, so what `save()` wrote is back after a restart. Change it and the script sees the change at once. A file that can't be read (broken JSON, something after the closing `}`, or just `null`) is said in the log, and the settings from the install are used |
| `settingsFile` | Where `MOD.save()` writes, or nil |
| `save()` | Write `MOD.settings` back to `settings.json`, for the next time the game starts and the next install. Returns true, or false and why |
| `log(fmt, ...)` | Print `[Mod name] text` to `ue4ss\UE4SS.log`. It's `string.format` underneath, so a `%` in the text is written `%%` |
| `page(fn, {title, order, group})` | A page in the mod menu (`fn(ui)`, as in [SDK.md](SDK.md#wcmodsmenu)). The menu goes in with UE4SS, as scripts do; returns false only if `WCModsMenu` is missing. A page made later, from a timer, takes the place of the settings page below rather than being a second one |

**A settings page for free:** a mod with a `settings.json` and no page of its own gets one. It has a row
per setting (on/off, number, text, `"#rrggbb"` colours) and a Save button, which says under it whether it saved;
keys starting with `_` show as notes, `"_help_<key>"` under its setting, and `"_min_<key>"`/`"_max_<key>"` bound a
number ([formats.md](formats.md#scripts-and-settingsjson) has which value makes which row, and what Save writes).
The same rows are on the mod's card in Clan Mod Studio, under More, to change before the game starts.
`"settings_page": false` in `mod.json` turns both off. The page is in the mod menu, which goes in with every
install; say `"uses": ["mod-menu"]` in `mod.json` so Clan Mod Studio shows that the mod has one.

`python wcmods.py new my-script --kind script` makes a new one to start from.
[game-tweaks](https://github.com/HexOffender/wcmods-examples/tree/main/game-tweaks), in wcmods-examples, is a complete one: it
keeps stamina full, holds the time of day, keeps the fresh-kill pile up and heals on a key, with its
settings on a page. Add it in the studio (or `wcmods add ../wcmods-examples/game-tweaks`), allow code
mods, and apply. Its tweaks are also on the studio's Tweaks page with no code at all
([formats.md, `tweaks.json`](formats.md#tweaksjson)): a mod holds the settings, and `WCModsTweaks`, wcmods' own
script, acts on them, so nothing has to be allowed.

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
timer's, a key's, a hook's), once, then once a minute with how many more times it happened. An error whose
numbers change each time (`... 3 cats`, `... 4 cats`) counts as one, and each kind of call says at most five
new errors a minute, then how many more it didn't say. The script keeps running, and a broken script doesn't
stop the others. The files are loaded by their names in the mod, so an
error says `scripts/main.lua:12: ...`.

**Where a script's words and errors show:**
- **In Clan Mod Studio:** before any Apply, the mod's card on the Mods page says what would stop its Lua from
  loading at all (a `function` with no `end`, a string left open, by file and line) and what's wrong with its
  `settings.json`. After the game has run, the card says whether the script loaded when the game last started
  (or why not), and under More, What it said has its lines, newest first. The log knows a script's lines by
  its mod's name, so give each mod its own: of two script mods with one name, each card has only what was said
  as its script started, and says why.
- **In the game:** a script that didn't start is named at the top of the screen for ten seconds once your cat
  is in the world, and in red on the mod menu's Overview; the mod menu's Log page (Tools) shows the scripts'
  lines, a plain `print` too.
- **On disk:** `<game>\Wrc\Binaries\Win64\ue4ss\UE4SS.log`, a new one each time the game starts.

## `WCModsGame`

```lua
local Game = require("WCModsGame")   -- a script mod has it as Game already
```

**Which wcmods:** `Game.wcmods` is the version of wcmods (Clan Mod Studio) that installed the module, `"0.6.0"`,
and `Game.wcmodsNumber` a number to compare, major × 10000 + minor × 100 + patch (`600`). Both are nil on 0.5.0
and older, which didn't have them. Between releases, a build of wcmods from its repository says the last release's
number until the next release raises it, so a check for 600 takes the old way there. A script that supports older ones too takes a fixed call where it's there and its own way round where it
isn't: `if (Game.wcmodsNumber or 0) >= 600 then ... end`. (`mod.json`'s `"wcmods"` refuses an older one
outright instead; [SDK.md](SDK.md#mod-folder).)

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
- **One thread:** don't use `LoopAsync`, `ExecuteWithDelay` or a `RegisterKeyBind` that does any work in a script
  that uses these modules: use `Game.every`, `Game.after` and `Game.onKey` (see SDK.md, *Rules that keep the game
  running*).
- **Some calls are costly every frame:** `Game.quests.objectives(q)` looks through every objective in the game each
  time; call it from `Game.every`, not `Game.onFrame`. `Game.save.file()` (and so `Game.items.list()`,
  `cat:traits()` and the slot calls) decodes the whole save, about 40 ms, but only when the file has changed: it
  keeps the table while the file stays the same, looking at its size at most 4 times a second and, at the same size,
  reading its text and comparing it every 2 s.

### Objects

| Call | Gives |
|---|---|
| `Game.valid(o)` | Whether `o` is a live object |
| `Game.alive(o)` | Whether it's live and staying: not destroyed, or left behind by a level that unloaded (UE4SS calls those valid until the engine collects them) |
| `Game.get(o, "A.B.C", default)` | A property path, or `default` when any step is missing. Numbers index arrays (from 1) |
| `Game.set(o, "A.B", value)` | Set one; true, or false and why |
| `Game.call(o, "Function", ...)` | Call a function safely: `true, results...` or `false, error` |
| `Game.find("Class")`, `Game.findAll("Class")` | One object of a class (kept while it lasts; never one on its way out, like the last level's HUD after a load: nil then, for a second, and asked again after) or all of them; short class names, e.g. `"WrcRoamingEnemy"` |
| `Game.object(path)`, `Game.load(path)` | An object by its path; load an asset, a mod's own too (`/Game/WCMods/<mod>/...`, which UE4SS's `LoadAsset` can't find) |
| `Game.enumNames(path)` | One of the game's enums by its path (`"/Script/SwtEngine.ECommands"`): `{name = number}` and its names in order, or nil (see *JSON and enums*) |
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
| `questStatus` | quest, status, exact | hook on `SwtQuestGameplayGameState:OnQuestStatusChanged` | seen firing from C++ on the same hook, as a quest moves on; not tried from Lua |
| `genericEvent` | name | hook on `SwtGameUtil:BroadcastGenericEvent` | hooked; not yet seen firing |
| `damage` | `{target, damage, missed, stance, status}` | hook on the combat director's `OnRegisterDamage` | seen firing from C++ on the same hook, in fights its test starts; not tried from Lua |
| `turnEnded` | | hook on `OnCombatantTurnEnded` | seen firing from C++ on the same hook; not tried from Lua |
| `status` | fighter, status | hook on `ApplyStatusType` | seen firing from C++ on the same hook, for a condition given; not tried from Lua |

### Hooks

`Game.hook(path, fn, {post = true})` runs `fn(self, args...)` when the game calls one of its functions.
The path is `"/Script/<Module>.<Class>:<Function>"`; `wcmods inspect` and the inspector list a class's
functions. It returns a handle for `Game.unhook(h)`.

`Game.hookRaw(path, fn)` gives `fn(self, params)`, where `params[i]:get()` and `params[i]:set(v)` read
and change the call's own parameters before the game uses them. Seen working in game: a hook changed
the tag a quest lookup was asked about.

Some limits:
- **Post hooks** run after the call, and by then the parameters may already be cleared.
- **A native function a Blueprint calls hands you its caller's variables.** Called from a Blueprint's bytecode (as
  `Actor:K2_GetActorLocation` is, many times a frame), a native function fires its hook, but its inputs aren't there
  to read: the call's frame is the caller's, so what `fn` gets as the parameters is that Blueprint's own variables
  (nonsense, or, from C++, a read that closed the game when the caller had none). C++ tells the two kinds of call
  apart (`call.has_params()`, SDK.md); UE4SS's Lua hook can't, so trust a hook's parameters only on an event, an RPC
  or a function Lua or a mod calls.
- **Only calls through Unreal fire hooks.** Unreal's function calls (Blueprints, delegates, Lua) fire
  them; native C++ calling C++ directly doesn't.
- **Hooks are per script:** they come off when the script stops.
- **Don't take a hook off from inside its own `fn`:** UE4SS frees the callback while it's running, and the game
  crashed at the hooked function's next call (seen with UE4SS's own console enabler on `ClientRestart`, which a
  fight's start calls: *Fights from C++* in `reverse-engineering.md`). Take it off a moment later instead:
  `Game.after(0, function() Game.unhook(h) end)` (not tried in game yet).

### Your cat (and other cats)

`Game.cat()` is yours. `Game.cat(actor)` wraps any cat or animal; it works on fighters too. `cat.actor` is the
game's own object for it (its character actor), for `Game.get`, `Game.call` and the game's members the
wrapper doesn't have: `Game.get(cat.actor, "CharacterType")`.

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
| `location()`, `teleport(x, y, z)` / `teleport({X,Y,Z})` / `teleport(actor)` | Where it is; move it: true, or false and why (`"the game wouldn't move it there (no room)"` when the engine refuses the move, and the cat stays where it was) | yes |
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

`Game.npcs.spawn(opts)` puts a cat of the mod's own in the world: one of the game's roaming clan
cats (`BP_WalkingNPC_Character_Base_C`, a Character with the game's own AI controller and character movement,
so it can walk: `npc:walkTo`) with the colours, eyes and size you give it. wcmods keeps it
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
| `at`, `yaw`, `level` | Where it stands (on the ground below `at`), which way it faces (degrees), and the level it's in (by default the one it first appears in). Give it an `at`: without one it stands at 0, 0, 0, and the log says so |
| `ground` | `false` puts it exactly at `at`, not on the ground below |
| `colours` | `fur`, `pattern`, `markings`, `nose`, `paws`, `whiskers`, `ears` as `"#rrggbb"`; the rest stay the game's |
| `eyes`, `size` | An iris colour slot, as in `palette.json`, and the cat's size (the game's are about 0.4–1.1) |
| `look`, `slots` | Its shape, as in `cats.json`: `{ body = 6, fur = 2, tail = 7, ears = 3, eyes = 1, whiskers = 4, face = 5, pattern = 12, marking = 3 }` (0–9, pattern and marking 0–20); and the colour slots it wears, `{ fur = 9, pattern = 4, marking = 0 }`. What they leave out, and the eye colour without `eyes`, is made up each time it's spawned |
| `prefix`, `suffix` | Name IDs (`"STR_CAT_NAME1"`, `"_PAW"`), for the name the game itself knows it by |
| `npc:valid()`, `npc:actorOrNil()` | Whether it's in the world now, and its actor |
| `npc:location()`, `npc:distance()`, `npc:near(cm)` | Where it is; how far your cat is; whether your cat is within `cm` (300) |
| `npc:face(target)`, `npc:moveTo(x, y, z)`, `npc:remove()` | Turn to a place or actor (your cat with none), which it keeps when it's spawned again; move it, onto the ground there; take it away for good (wcmods lets go of it; `Game.npcs.all()` still lists it, with `npc.removed` set) |
| `npc:walkTo(x, y, z, opts)`, `npc:walking()`, `npc:stop()` | Walk there with the cat's own AI controller and character movement: its walk animation, turning to where it goes, kept on the ground, at `opts.speed` cm/s (175). `opts.radius` (30) is how close counts as there (give or take 15 cm, across the ground), and `opts.done = function(npc, result)` is called with `"arrived"`, `"blocked"` (it stopped short or stopped making progress) or `"cancelled"` (`npc:stop()`, `moveTo`, another `walkTo`, `npc:remove()`, the cat unloaded); `npc.walkResult` keeps the last. By default (`opts.avoid`, true) it follows the game's nav mesh round walls and rocks and steers round other cats with the movement's RVO avoidance; `avoid = false` walks a straight line. A stall (it stops, or shuffles without getting closer) is met by stepping aside and asking for the path again, up to five times, before `"blocked"`. 50 walking cats took the game from 60 to about 49 frames a second (measured against its 60 a second cap, so a rough figure); see [docs/plans/npc-walking-stress.md](plans/npc-walking-stress.md). A goal off the nav mesh falls back to a straight line, and an unreachable one ends "blocked". `npc:moveTo` is still a teleport and cancels a walk |
| `Game.npcs.spot(cm, side)` | A place beside your cat with room for a cat (220 cm away, to its front left by default), and a yaw facing your cat: `local at, yaw = Game.npcs.spot()` |

Move a cat with `npc:moveTo` rather than removing it and spawning it again: a new cat's look is made up
again (all of it, or what its `look` and `slots` leave out), so a new one can look different. That also
happens when the game unloads the cat and wcmods spawns it again. Give it a whole `look`, `slots` and
`eyes` and it looks the same every time. (The shape fields set the cat's data, but the game picks a walking
cat's tail and ear meshes itself, so those two can still differ from `look.tail` and `look.ears`.)

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
| `npc:label({name, title, extra, icon, range})` | The game's label over its head: the name, the title under it, `extra` (a line above it, in the game's green), and `icon`, one of the game's quest marks: `"available"` (a new quest), `"ongoing"`, `"done"` (to hand in). It shows while your cat is within `range` cm (1000), fading out over the last 30% of it, and only while nothing (a rock, a wall) is between the camera and the cat's head; it is checked twice a second. `npc:label(nil)` takes it away |
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
| `Game.dialogue.hide()`, `Game.dialogue.showing()` | Fade it out (a box a failed `say` left half made too); whether it's up. A line said while it fades out brings it back in |
| `Game.dialogue.busy()`, `Game.dialogue.claim()` | Whether another mod's cat is talking (each mod has its own box, so two could overlap); take the box for this script's talk, false if it's taken. Check `busy()` before starting a talk. The claim lasts while the box is up, however long the talk waits for a key, and `hide()` lets it go |

**The box puts your cat "in a talk".** As it goes on screen, its own code sets the game's talk flags on your cat's
controller (`WCM_TalkFlags`), and while they're on no animal notices your cat and a pounce starts no fight (seen from
C++). `hide()` (and a `say` that fails) clears them once the box is gone, unless one of the game's own talks is up.

The box is only the picture: it takes no input, so the script moves the talk on with its own key (the
box shows Enter, the game's own key for it, so take that too). The answer buttons stay hidden. [custom-npc](https://github.com/HexOffender/wcmods-examples/tree/main/custom-npc) in
wcmods-examples does: a name over the cat's head, and lines to say on a key.
[moonlit-path](https://github.com/HexOffender/wcmods-examples/tree/main/moonlit-path) builds a
questline on one.

### The game's AI (`Game.ai`)

A roaming animal, or a clan cat walking its path, has an AI controller that runs one of the game's behaviour trees:
`BT_Enemy` for an animal, `BT_CombatEnemy` in its fights, `BT_WalkingNPC` for a walking cat. The tree keeps what it
knows on its blackboard (`BB_Enemy`'s `Detected`, `Target`, `ChaseReactionTime`, ...). `Game.ai` reads and steers it
as C++'s `Ai.hpp` does (SDK.md); what's behind it is in `reverse-engineering.md`, "The game's AI".

An AI is given as its actor, a `Game.cat(...)` or a mod's cat (`Game.npcs`). The calls on an AI answer false or nil
for your cat, which has no AI (`face` turns any actor). What a script changes stays after the script ends (UE4SS
restarting the mods, say): an AI it stopped, an animal it made ignore your cat. Put them back first. What an AI is running at this moment (its tree and task) is C++'s only: the brain's stack of
running trees is an array Lua can't read.

```lua
for _, a in ipairs(Game.animals.near(2000)) do Game.ai.stop(a.actor) end       -- the animals near stand still
Game.ai.moveTo(mouse, { X = x, Y = y, Z = z }, { speed = 200, restartAfter = true })
Game.ai.ignorePlayer(mouse)                                                    -- it no longer notices your cat
Game.ai.follow(npc, Game.player())                                             -- a cat at your cat's heels
```

| Call | Gives or does |
|---|---|
| `Game.animals.near(radius, from)` | The roaming animals within `radius` cm (5000) of your cat, or of `from` (a place or an actor), nearest first: `{ {actor, distance, generator, kind, model}, ... }`. `generator` is the level's generator that spawns it, `kind` is the kind `Game.animals.spawn` gave it (nil for the game's own), and `model` is its model's name (`"SK_Rabbit"`, `"SK_Mice"`) |
| `Game.ai.controller(a)`, `Game.ai.brain(a)` | Its AI controller (`AIC_Wrc_Enemy_Controller_C`, a walking cat's `AIC_Wrc_WalkingNPC_Controller_C`) and the behaviour tree component that runs its tree; nil without an AI |
| `Game.ai.running(a)`, `Game.ai.asleep(a)` | Whether its logic runs, and whether it's asleep: the game pauses a roaming animal's while your cat is about 2,000 units from it, and wakes it as your cat comes back |
| `Game.ai.stop(a)`, `Game.ai.restart(a)` | Stop its logic: it stands where it is, through the game's own sleeping and waking, and its blackboard keeps what it knew. Start it again from its tree's start. False without an AI. A script's stopped AIs stay stopped after the script ends, so start them again first |
| `Game.ai.keys(a)` | Its blackboard's keys in order, `{ {name, type}, ... }`. `type` is `"Bool"`, `"Int"`, `"Float"`, `"Vector"`, `"Object"`, `"Enum"`, `"Name"`, `"String"`, `"Rotator"` or `"Class"`. `BB_Enemy` has 14 |
| `Game.ai.get(a, key)` | A key's value, by its type: a boolean, a number, an object, a string, a place (`{X, Y, Z}`; nil while the key isn't set) or a rotator. Nil without the key |
| `Game.ai.set(a, key, value)`, `Game.ai.clear(a, key)` | Write a key by its type: true, or false and why when the AI hasn't the key or the value doesn't fit it (`"Detected is a Bool key"`). The tree sees it at once. A number goes into a Float, or a whole one into an Int; a place into a Vector; an actor or a `Game.cat` into an Object; nil clears the key |
| `Game.ai.TREES`, `Game.ai.tree(name)` | The game's eight trees by name (`"BT_Enemy"`, `"BT_ChaseOff_Enemy"`, `"BT_CombatEnemy"`, `"BT_BossEnemy"`, `"BT_AttackEnemy"`, `"BT_Escort"`, `"BT_Mentor"`, `"BT_WalkingNPC"`), and one loaded |
| `Game.ai.treeNodes(tree)`, `Game.ai.treeBlackboard(tree)` | A tree (or its name) as data: its nodes from the root, each after the decorators that guard it, `{ {depth, role, kind, name, settings}, ... }`. `role` is `"composite"`, `"task"`, `"decorator"` or `"service"`; `kind` is its class (`"BTTask_EnemyGrazing"`); `settings` are its own members as text (`{ {name = "BlackboardKey", value = "Detected"}, ... }`). The blackboard is the tree's asset's name (`"BB_Enemy"`). The same as C++'s, node for node (tested). An enum setting of a class outside the game's eight trees reads as its number, because UE4SS's Lua can't ask a member for its enum |
| `Game.ai.trees(a)`, `Game.ai.setTrees(a, roaming, fight)` | The trees its controller starts on its own: `{roaming, fight}` (`BT_Enemy`, `BT_CombatEnemy`). Setting them leaves the tree running now alone (that's `runTree`). A fight's enemy is its own actor, so set its `fight` tree at `combatStart`; only `BT_CombatEnemy` works there (seen from C++) |
| `Game.ai.runTree(a, tree)` | Run another tree on it now, from its start (its controller's `RunBehaviorTree`; a tree on another blackboard starts with its keys clear). A move under way ends. The game starts its own trees again on its own occasions (a fight, its end) |
| `Game.ai.navPoint(place, a)` | The nearest point on the nav mesh to a place: the mesh `a` walks on (the animals' and the cats' differ), or either. Nil off the meshes |
| `Game.ai.moveTo(a, to, opts)` | Send it to a place or after an actor (it follows a moving one until it's within the radius), along the nav mesh through its controller, its logic stopped first. `opts`: `speed` (cm/s; a roaming animal's own is a slow 70), `radius` (50), `avoid` (true; false walks a straight line), `restartAfter` (its logic started again when the move ends, however it ends; otherwise it stands there stopped), `done(result)`: `"arrived"`, `"blocked"` or `"cancelled"`. True, or false and why. The walk is the mod cats' own (`npc:walkTo`'s): stalls and steps aside alike |
| `Game.ai.stopMoving(a)`, `Game.ai.moving(a)` | End a move (done told `"cancelled"`) and stand it where it is (a move of its tree's own too); whether it's moving, by `moveTo` or its tree |
| `Game.ai.face(a, at)` | Turn it to a place or an actor now |
| `Game.ai.detectionFlags(a)`, `Game.ai.setDetectionFlags(a, n)` | Its detection mask: 1 Vision, 2 Sound, 4 Cone, 8 InPursue (3 on a roaming animal); nil without a detection component (a walking cat). The roaming tree's services pass flags of their own, so 0 alone doesn't stop it noticing your cat: `ignorePlayer` does |
| `Game.ai.calm(a)`, `Game.ai.noticePlayer(a)` | Make it lose your cat as the game's losing does (it walks back where it started, then roams), or notice it now as the game's noticing does (it gives chase after its reaction time, its senses' `ReactToChase`, even while it ignores your cat). Calmed, it doesn't notice your cat again on its own while your cat stays near: its detection still tracks your cat, and only a cat it starts tracking is noticed (seen) |
| `Game.ai.trackingPlayer(a)` | Whether its detection tracks your cat: noticed and not lost (its detection component's set; the blackboard's `Detected` is the tree's, and they catch up with each other within a moment) |
| `Game.ai.ignorePlayer(a, ignore)`, `Game.ai.ignoringPlayer(a)` | Make it ignore your cat, or notice it again as it did (`ignore` false): its detection sphere stops overlapping cats, its mask goes to 0 and it gives your cat up. It ignores every cat so, and a pounce on it starts no fight (seen from C++) |
| `Game.ai.ignorePlayerEverywhere(on)` | A stealth mode: every animal within 5,000 units of your cat ignores it (a look once a second); off, each it changed is as it was, but not one the script made to ignore your cat itself |
| `Game.ai.flee(a, from, distance, opts)` | Make it run `distance` cm (800) away from a place or an actor, at its chase speed, given back to its tree at the end (a `moveTo`; `opts` as there). A rock, a river or the mesh's edge that way stops it short |
| `Game.ai.follow(a, target, opts)`, `Game.ai.stopFollowing(a, putBack)`, `Game.ai.following(a)` | Make it follow an actor about: whenever it's farther than `opts.distance` (150), it goes after it at `opts.speed` (its own), looking every `opts.every` seconds (0.25). Until `stopFollowing` (its tree runs again if it ran before, unless `putBack` is false), it or the target gone, or its tree run again. The game's own escort tree doesn't do this (seen from C++) |

**An animal walked into your cat catches it** as a chase does, and a fight starts: a mouse moved to 90 units from it
started one. Keep moves and following a couple of metres off, or make the animal ignore your cat first.

**Animals put in the world.** The roaming animals are spawned by the level's generators (`BP_Enemy_Generator_C`). Each
generator has a fight party's tag per clan and rank; the party is a row of `DT_Combat_Generator` and decides what the
fight is. A generator made at run time gave its animal's fight another generator's party (seen from C++). So
`Game.animals.spawn` borrows a placed generator instead: it sets the generator's party tags to the kind, moves it to the
place, and takes its own animal away. Once the script's animal is gone, the generator gets back its tags, its place and
its own animal.

```lua
local rabbit = Game.animals.spawn("Gameplay.Combat.Generator.Fixed.Rabbit.01.L6", spot)   -- one rabbit, level 6
Game.ai.ignorePlayer(rabbit)        -- (noticing your cat, it would chase it into a fight)
Game.animals.remove(rabbit)         -- gone, the generator given back
```

| Call | Gives or does |
|---|---|
| `Game.animals.kinds()` | Every party in the game's table, `{ {tag, party, levels}, ... }`: 323 on build 26337109, of four kinds. Fixed parties are one to three animals, or out-of-clan cats, at a level; the others are Boss, Hybrid and SandboxAttacks. `party` lists each fighter's character tag (`"Gameplay.Combat.Character.Rabbit"`) and `levels` their levels |
| `Game.animals.spawn(kind, place, opts)` | Put an animal of a kind (a party's tag) at a place, as the game puts its own: one of the game's generators is borrowed (the farthest from your cat) and spawns it there. `opts.respawn` gives a new one whenever it's gone and keeps the generator; otherwise the generator is given back once the animal is gone. Gives the animal with its AI running, or nil and why (a kind the game has no party for, no place, no generator free). Its fight is the kind's party |
| `Game.animals.remove(animal)`, `Game.animals.kind(animal)` | Take an animal out of the world. One the script put there goes for good and its generator is given back; one of the game's comes back at its generator's next spawn. False for what isn't a roaming animal. `kind` is the kind the script gave it (nil for the game's own) |

The generators a script borrowed aren't given back if the script ends first, because UE4SS gives Lua no end of its
own: remove each animal first.

**The clan cats' walking.** A clan cat walking about (`BP_WalkingNPC_Character_Base_C`, which a mod's cats are too)
runs `BT_WalkingNPC`. While its blackboard's `bShouldAllowMovement` is set, it walks along its path: the spline its
`SplineReference` holds, which belongs to a `BP_WalkingNPC_Spline_C`. The game's paths go there and back. The game's
walking cats stand while your cat is near (one 300 units off stood, one 1,200 off walked); a mod's cats don't.

| Call | Gives or does |
|---|---|
| `Game.walkers.near(radius)` | The walking cats within `radius` cm (30,000) of your cat, nearest first, the game's and the mods' alike: `{ {actor, path, points, loop, walking, modPath, distance}, ... }`. `path` is its path's actor and `points` its spline's points (world places). `loop` says whether it goes round (else there and back), and `modPath` whether the path is this script's |
| `Game.walkers.walkPath(cat, points, opts)` | Give a walking cat (one of the game's, or a mod's own from `Game.npcs`) a path of its own: a spline through `points` (two places or more; it walks the ground under them), walked from the first as the game walks its paths. `opts.loop` (true) goes round and round; false goes there and back. `opts.speed` is in cm/s (the game's walking cats walk at 50); without it the cat keeps its own speed. A game cat's own path is kept to give back. True, or false and why. Don't `npc:walkTo` a mod's cat while it walks a path: its tree walks it |
| `Game.walkers.ownPath(cat)` | Give a game cat its own path back, at its own speed (the script's path goes). A mod's cat, with no path to go back to, stands. False when it hasn't one of the script's paths |
| `Game.walkers.stop(cat)`, `Game.walkers.walkAgain(cat)`, `Game.walkers.walking(cat)` | Stop a walking cat where it is (`bShouldAllowMovement` cleared, the game's own way), or let it walk on along its path. `walking` says whether it walks now: its logic running, `bShouldAllowMovement` set and a path to walk. C++ also checks that the running tree is `BT_WalkingNPC`, which Lua can't read |

A script's paths aren't taken away if the script ends first: give each cat its own back (`ownPath`), or stop it.

### Items

| Call | Gives or does |
|---|---|
| `Game.items.list()`, `Game.items.count(tag)` | Your items, `{["Gameplay.Inventory.Materials.Dandelion"] = 6, …}`: as of the game's last save (it writes `WrcGame.json` each time), with the pickups since the level loaded from the HUD's pickup messages. Loading a save or another cat (a new HUD), or the game saving after them, drops those pickups, and the save says again. A save the game rewrote at the same size isn't noticed: the pickups stay laid over it until the next load. Items used since the last save aren't seen until the next one |
| `Game.items.drop(tag, count, where)` | A pickup holding the items on the ground 50 cm in front of your cat, where its Interact reaches (or in front of the actor `where`, or below a place `where`), for the cat to pick up as usual. It returns the actor, or nil and why. A `tag` that isn't one of the game's items (`Game.items.isItem`) is refused: a tag the game doesn't know gets into the save with the pickup, and the game crashed at quit (seen from C++). A mod's herb or material lies there as its own model (items.json `model`), or as the game's pickup of the herb it's `like`. Seen in game: the cat collects it with Interact, and `itemPickedUp` fires |
| `Game.items.isItem(tag)` | Whether a tag is one of the game's items: a tag the game has registered, under `Gameplay.Inventory` (a mod's new items are registered from their ini at startup) |
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
| `Game.anims.stop(who, blend)` | Stop what `play` started on it, blending out; true if something stopped. That's what any script's `play` started: each script has a Lua state of its own, so they share what plays (`WCModsAnims.playing.<actor address>`, a shared variable holding its id, its sequence and its montage), and an emote's key stops what the Emote wheel started. Another script's is stopped only while the actor's current montage is still that one, playing that sequence: never one of the game's own |
| `Game.anims.playing(who)` | The id of what `play` started on it (in this script or another), while it plays; else nil |
| `Game.anims.list()` | Every mod's animation: `{["my-mod/Wave"] = {name, kind, path, loop, speed, blend, seconds, emote, key}}`. `path` is the sequence it plays: the mod's own (`/Game/WCMods/my_mod/A_Wave.A_Wave`: a - in the mod's id is a _ in the path), or one of the game's for an animation that uses the game's own (`"game"` in animations.json: `/Game/Art/Characters/CatMaster/Animations/A_CatMaster_Yawn_1.A_CatMaster_Yawn_1`) |
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
| `Game.time.hold(s, who)`, `Game.time.hold(nil, who)` | Hold the clock at `s` seconds into the day, for every script: one hold, shared between them, so two scripts holding it don't fight over the hour. The last script to hold it has it, and the clock is set to that hour every frame while your cat is in the world. `who` names the holder (the mod's name by default); `hold(nil, who)` lets go of your own hold only. Gives back what setting the clock did. The script's Lua state keeps its hold up, saying twice a second that it's still there: a hold whose state has gone (UE4SS restarted the mods, say) is no hold 3 s later. Tweaks' Hold the clock gives way to another script's hold, and takes the clock back once that's let go or gone |
| `Game.time.held()` | The hour held, in seconds, and whose hold it is (`54000, "Tweaks"`); nil when nobody holds the clock, or the hold's script has gone. (Just after a restart of the mods, a script can still see a hold whose script went with it: until the script's second frame, and in hooks before its first for as long as no frame comes. A script with no timer of its own by the frame after it first asks (only hooks and keys, say) sees it for two frames from the first time it asks, or through a level load it first asks in, and never once the hold is about a minute (63 s) old. The other side: if such a script first asks shortly before, during or just after a level load of more than about a minute, it can see a live hold as gone until the holder's first frame after the load) |
| `Game.freshKill.value()`, `.max()`, `.set(v)`, `.level()` | The camp's fresh-kill pile (0–100), and Full/Abundant/Good/Scarcity/Critical |
| `Game.freshKill.timer()`, `.decayTime()`, `.setDecayTime(v)` | Seconds since it last went down, and how often it does (90) |

### Quests

| Call | Gives or does |
|---|---|
| `Game.quests.all()` | Every quest the quest manager holds, each as `describe` gives it |
| `Game.quests.describe(q)` | A quest object as a table: `{quest, id, tag, alias, graph, class, type, status, result, tracked, xp, rewards}`. `quest` is the object itself; `id` comes from its quest graph (`"Tutorial"`, `"Deliver"`, `"RiverClan_Unique1"`), `tag` is the graph's quest tag and `alias` its story id (`"Quest.Main.1"`; nil without one), `graph` the graph's name and `class` the quest's class; `rewards` is `{tag = count}`. `status` and `result` are the game's by the alias, which it keeps a quest's progress by (the quest object's own stay None while it's under way), else the object's own. Nil for no quest |
| `Game.quests.objectives(q)` | A quest's objectives, in order: `{objective, id, index, current, target, status, point, targets}` (`current` and `target` count it up, `point` is where to go when it has one). `status` is the game's for an objective your cat's save has, nil for the rest (asking would add it to the save). [Costly](#how-it-reaches-the-game): it looks through every objective in the game. `targets` are a gather objective's, `{ {tag, current, target, actors}, ... }`: the things to collect, out in the world (empty for the other objectives) |
| `Game.quests.tracked()` | The quest being followed (the object, for `describe` and `objectives`), or nil |
| `Game.quests.manager()` | The game's quest manager, for `Game.get` and `Game.call` on what these don't wrap |
| `Game.quests.report(id, {title, status, objective, progress, by, description})` | List a quest of the mod's own on the mod menu's Quests page: `status` is `"available"`, `"active"` or `"done"`; `by` the mod's name; `description` an optional sentence about it. Report again when it changes; `nil` takes it off. `Game.quests.reported()` reads them back: `{id, title, status, objective, progress, by, description}` each, `description` `""` when there's none (a page from before it was a field shows the first five) |
| `Game.quests.status(alias)`, `.result(alias)`, `.successes(alias)` | By the quest's story id, its alias (`describe`'s `alias`, `"Quest.Main.3"`): `"QuestAvailable"`, `"OngoingQuest"`, … Nil for an id none of the quest manager's quests has: the game's own call adds the id it's asked about to the save's `QuestProgression` (seen from C++) |
| `Game.quests.start(tag)`, `.give(tag)`, `.track(quest, on)` | The quest manager's own StartQuestOfTag, GiveQuestOfTag and SetTracked: true, or false and the error. They can move the story on. `start` was seen putting the gather quest (`"Quest.Procedural.Survival.Gather"`, Quest.Main.1) under way |
| `Game.quests.current(q)` | The objective a quest is on: the one whose targets are out in the world (a gather objective's), else the first the game says is in progress; nil when neither. A fight's or an escort's objective isn't found that way, because the game said NotStarted for a live one (seen from C++) |
| `Game.quests.collect(target)` | Collect one of an objective's targets (an actor from its `targets`) the way the player does. Your cat is put on it and the game's Interact is pressed 0.8 s later, so the game's own pickup counts it (the HUD's "1/3", the quest's events, and any other target in reach). Your cat goes back where it was at 1.6 s. True, or false and why: no cat or target, or a den, an interactable or a quest giver within 2 m of it, which Interact would use instead |
| `Game.quests.finishObjective(objective, succeeded)` | Finish an objective as the game does when its last target is in: succeeded, or failed with `false`. The quest goes on to its next objective or is complete, and the game's own flow follows (the "Return to the Camp now?" question, the giver's turn-in). It moves the story on |
| `Game.quests.alias(q)` | A quest's story id (`"Quest.Main.1"`), which the game keeps its progress by |
| `Game.quests.chapter()` | `"Chapter00"` |

Seen in game, on a backed-up save, as C++'s test does: the gather quest started by its tag, its objective's three
Bedding Moss targets out in the world, one collected (the count went up), the objective finished, and the quest complete
with Success.

### The story

| Call | Gives or does |
|---|---|
| `Game.scenes.list()` | Every scene the game can play: `{ {tag, type, kind, sequence, hidesHud, hidesActors}, ... }`. `type` is the sequencer's kind, 1 to 7, and `kind` its name: Intro, Outro, CutScene, Podium, Gameplay, Combat, Quest. Most (39 of 60 on build 26337109) are the fight cameras (Combat), and a few are exploration shots (Gameplay). Playing one is C++'s `play_scene`, because the game's call for it is native |
| `Game.scenes.playing()` | The scenes playing now, by tag |
| `Game.scenes.seen()`, `Game.scenes.seen(name)` | The story scenes your cat has watched, by the save's names (`"ProphecyIntro"`, `"RankUpApprentice"`), as of the last save; or whether it has watched one |
| `Game.scenes.skip()` | Skip the scene playing, as holding the skip button does: the skip popup's hold button pressed, then let go 2.5 s later. False when the popup isn't up (none playing, or one the game won't let you skip) |
| `Game.progression(path)` | A value of your cat's progression in the save, by its path under the slot's GameplayProgression (`"Chapter00/L_WorldMap_01_P"`, `"FreshKill/Cycle"`), as of the last save; nil when it isn't there |
| `Game.mood(primary, sub)`, `Game.setMood(primary, sub, value)` | A mood value the game keeps (the save manager's MoodData: a whole number under a primary and a sub key), or nil when it hasn't one; set one. `mood` asks `HasMoodData` first, because the game's own `GetMoodData` writes a missing key into the save as 0 |

### Fights

`Game.fight()` is the fight going on now (or nil). `Game.combat.active()` says whether there is one.

| Fight | Gives |
|---|---|
| `players()`, `enemies()`, `all()` | The fighters |
| `turnOrder()`, `current()`, `mainEnemy()` | Cats, in this round's order; whose turn it is, and the fight's main enemy (nil when it's nobody's turn, there's no main enemy, or its body can't be read) |
| `kind()` | The director's class (story, boss, skirmish, defender…) |
| `fight.director`, `Game.combatDirector()` | The fight's combat director, the game's own object the calls above read, for `Game.get` and `Game.call` on what they don't wrap: `Game.get(fight.director, "TurnOrder")`. `Game.combatDirector()` is nil with no fight going on |

A fighter (`Game.fighter(cat or actor)`) is a cat's combat component, set up when a fight starts:

| Fighter | Gives or does |
|---|---|
| `stats()`, `setStat(name, v)` | This fight's stats (the damage formula uses these) |
| `level()`, `setLevel(n)`, `stance()` | Its level, and its stance now |
| `move()`, `moveTag()`, `setMove({Damage = 80, Accuracy = 1})` | The move it picked (its AttackMove row), and changing it before it lands (not tried: no move was picked in testing) |
| `targets()`, `cat()` | Who it's attacking; the cat itself (health, status…), or nil when its body can't be read |
| `actor()`, `fighter.component` | The fighter's character actor (nil when it can't be read), and its combat component, the game's own `TurnBasedCombatComponent` the calls here read, for `Game.get` and `Game.call` |
| `team()`, `aiTier()`, `setAITier(t)`, `moveCount()` | Its team (`"Player"`, `"Enemy"`), the AI's tier for this fight (`"Tier1"`…`"Tier6"`; `"None"` for your cat) and how many moves it has to pick from: the game's own members, filled when the fight is set up (seen: a weak mouse at level 1, `"Tier1"`, 3 moves; your cat 3 moves and no tier) |

**Seen in game** (a level 20 cat against a weak bird):
- The fighter stats matched the stat formula.
- Health matched Prowess.
- Fight stamina was 0.4 × Prowess + Stamina, for both sides.
- Setting the bird's Strength and health worked.

**Playing a fight from a script.** A script can start a fight the player's way and take your cat's turns through the
fight menu, as its own keys do: the selection is moved a press at a time, then confirmed. Each call starts the turn,
which then plays out over the next seconds. The calls are C++'s (`Story.hpp`, `Ai.hpp`), with moves numbered 1 to 4.
The combat manager's `EndCombat` ends a fight but leaves your cat with no body, so `finish` ends one the game's own
way instead.

```lua
Game.combat.start(mouse)                      -- behind it, then the pounce
-- on your cat's turn (Game.combat.menu() isn't nil):
Game.combat.attack(1)                         -- its first move, at the enemy
Game.combat.finish(true)                      -- or won outright
Game.combat.autoFight(true)                   -- or let the script play every turn
```

| Call | Gives or does |
|---|---|
| `Game.combat.start(animal)` | Start a fight with a roaming animal the player's way: your cat is put 1.5 m behind it, facing it, and the game's pounce is pressed 0.6 s later. False outside the world, during a fight, or for no animal. Whether a pounce starts a fight depends on the spot: beside a den none does (seen from C++). An animal spawned by `Game.animals.spawn` and left running noticed your cat as it landed, and the pounce did nothing; with its logic stopped (`Game.ai.stop`), a pounce did start a fight, at most spots |
| `Game.combat.cat()`, `Game.combat.menu()` | Your cat's fighter in the fight now (the player's side's one with no AI tier), and the fight menu (`WBP_GuiPopupCombat_C`), up on your cat's turn. Nil when there's none. `Game.player()` is nil during a fight, because the controller holds the fight's own pawn |
| `Game.combat.attack(move)`, `Game.combat.rest()`, `Game.combat.flee()` | Your cat's turn, through the menu: an attack (move 1 to 4, as the attack panel lists them; its target confirmed), a rest, or fleeing (the fight ends). False when the menu isn't up, or for a move your cat hasn't got (a young cat has fewer than four) |
| `Game.combat.moves()` | The attack panel's moves, `{ {name, stamina, usable}, ... }`: each move's name, its stamina cost and whether it can be used now. Lua can't read the moves' damage: it's in the fighter's moves array, which C++'s `Fighter::moves` reads |
| `Game.combat.finish(won)` | End the fight the game's own way. The losing side's health is set to 0 and your cat's turn is taken (an attack), so the game finishes the fight as it does: a win with its rewards, or a loss. A loss sends your cat back to its respawn spot, healed, and the save keeps that spot. False outside a fight, or when it isn't your cat's turn: call it again then |
| `Game.combat.dilemma()`, `Game.combat.answerDilemma(n)` | A dilemma the fight is asking now (its popup), as `{title, question, bonus, option1, option2}`, or nil. Answer it with choice 1 or 2, a step at a time, as its own keys do, until the popup goes. The game picks dilemmas from `CombatDilemmas.csv`, by chance (0.15, or 1 at a boss's end) and the fighters' state |
| `Game.combat.autoFight(on)`, `Game.combat.autoFightTurns()` | Take your cat's turns for it: on each one, the move costing the most stamina it can use (C++ picks by damage, which Lua can't read), else a rest. Also a rest when the game didn't take the move. Runs until turned off. `autoFightTurns` is how many turns it has taken |
| `Game.combat.onDamage(fn)` | `fn(info)` as a hit lands, before the game applies it. `info` is the `damage` event's: `{target, damage, missed, stance, status}`. If `fn` returns a number, that's the hit's damage (0 for none). It's a hook on the combat director's `OnRegisterDamage`, an event the game calls through the engine, so its parameters are its own. Returns a handle for `Game.unhook` |
| `Game.command(name)` | Press one of the game's controls (an `ECommands` name: `"Player_Pounce"`, `"Player_Interact"`), through the controller's input component, as C++'s `command` does |

**Seen in game:**
- a fight fled through the menu;
- a fight won by `autoFight`, with every hit on the enemy made deadly by `onDamage`;
- a fight lost by `finish(false)`;
- a fight with a rabbit `Game.animals.spawn` put in the world: one enemy, a rabbit at level 6 (the kind's party), won by `finish(true)`. That needs a spot where a fight can start, which the test looks for and skips without.

A fight's end saves where your cat is, and winning gives your cat experience.

### Tables and words

The game's DataTables hold items, characters, fight parties, animations, the sky's presets, den decorations and
tutorials. They load with its level or its managers: 69 were in memory in the forest on build 26337109. A row is the
game's own memory, so a change is what the game reads from then on; code that copied a row's numbers earlier keeps its
copy. Every line the game shows is a key of its string table (`SwtStrings`, loaded from `Strings_<language>.csv`).

Three things are C++'s only:
- adding a row: UE4SS's `AddRow` copies through the row's native copy, which it can't reach on this engine;
- changing words;
- the tuning (`TuningData.csv`): it's raw memory.

```lua
local row = Game.tables.row("DT_Combat_Generator", "Default")
print(row.NumParty)                                        -- 3
Game.tables.set("DT_Combat_Generator", "Default", "NumParty", 2)
print(Game.words("STR_CAT_NAME2_PAW"))                     -- Emberpaw
```

| Call | Gives or does |
|---|---|
| `Game.tables.list()` | Every DataTable in memory: `{ {name, path, rowStruct, rows}, ... }` (`rowStruct` is its rows' struct, `QuestObjectsInfoDataStruct`) |
| `Game.tables.get(nameOrPath)` | A table by its name (`"DT_QuestObjectsInfo"`) or its path (`"/Game/Gameplay/DataTables/Quests/DT_QuestObjectsInfo.DT_QuestObjectsInfo"`), when it's in memory; nil when it isn't. The other calls take a table, a name or a path |
| `Game.tables.rowNames(t)`, `Game.tables.rows(t)` | Its row names, in the table's order; every row, `{ {name, row}, ... }`, each the game's own |
| `Game.tables.row(t, rowName)` | A row by its name: the game's own row (a struct; `Game.get` and `Game.set` work on it). Nil when the table hasn't got it |
| `Game.tables.set(t, rowName, path, value)` | Change a row's value by its path in the row (`"NumParty"`, `"itemName"`): true, or false and why |
| `Game.tables.removeRow(t, rowName)` | Take a row out; false when there's no such row. It's gone until the game loads the table again (a restart), because a script can't put it back. The game frees the row's memory, so don't use a row you got from `row` or `rows` before: writing to it would write into freed memory |
| `Game.words(key, tableId)` | A key's words as the game shows them (`"STR_CAT_NAME2_PAW"` is `"Emberpaw"`), or nil for a key the table hasn't got. `tableId` is `SwtStrings` unless given |
| `Game.wordKeys(prefix, tableId)` | The table's keys, or only those starting with `prefix` (`"STR_CAT_NAME"`), in the table's order. `SwtStrings` has 8,907, read in about 30 ms |

**A plain string where UE4SS wants an FName crashes the game,** inside UE4SS where `pcall` can't catch it. The string
table calls take the table's id as an FName, and these calls make one; UE4SS's own `RemoveRow` and `FindRow` take a
string. The crash is the same the other way round.

### The world, more

The sky, the game's sounds and music, its own animations, visual effects, movement and your cat's speeds, as C++'s
`World.hpp` and `Effects.hpp` have them.

| Call | Gives or does |
|---|---|
| `Game.console(command)` | Run a console command as the console does (`"stat fps"`, `"r.Fog 0"`). The game's own controls are `Game.command` |
| `Game.save.hash()` | The save's Hash as the game holds it; it changes each time the game writes the save. Nil without a save |
| `Game.sky.actor()`, `Game.sky.presets()`, `Game.sky.table()` | The world's sky (`BP_DayNightSky_C`) while you play; its presets by name (`"NeutralDay"`, `"Night"`, `"ThunderClan"`, `"MoonPool"`...); their table, `DT_SkyBoxParams` (a row per preset of the sun, fog, clouds and stars, for `Game.tables`). A row changed in the table shows in a sky made after it (a new level): the sky copies the rows as it starts, into a map only C++ reaches |
| `Game.sky.set(preset, hold)`, `Game.sky.held()`, `Game.sky.followArea()` | Put a preset on at once. The game fades back to the area's own within about 5 s, so with `hold` (the default) it's put on again every frame until `followArea`, another `set`, or a new level. `held` gives the preset held. `followArea` lets go and gives the area's sky back. Seen: Night held for 4 s, its fog and sun unchanged |
| `Game.sounds.ids()`, `Game.sounds.of(id)`, `Game.sounds.duration(id)` | The game's sounds by their ids (390 on build 26337109): music (`"mus_camp"`), effects (`"cat_step"`), menu sounds (`"ui_select"`), cats' voices. Also the sound an id plays now, and its length in seconds |
| `Game.sounds.play(id, at)`, `Game.sounds.stop(component)` | Play one as the game does, heard everywhere or from a place: the audio component, or nil. A menu sound played at a place gives none, because it isn't a sound heard from somewhere |
| `Game.sounds.mute(id)`, `Game.sounds.restore(id)` | Silence an id (its sound's own volume set to 0, which silences any other id with the same sound) and give it back. Playing another sound for an id is C++'s (`replace_sound`) |
| `Game.sounds.setVolume(which, level)`, `Game.sounds.pause(on)`, `Game.sounds.paused()` | The game's volumes as its Audio settings set them (`"Master"`, `"Music"`, `"Effects"`, `"VoiceOver"`; 0 to 1). Pause every sound, or let them go on |
| `Game.music.now()`, `Game.music.play(id)`, `Game.music.stop(seconds)` | The track playing (`{component, sound, id}`), one of the game's tracks played on the music's own component until the game next changes track, and the music faded out (0: at once) |
| `cat:playMontage(tag, rate)`, `cat:montagePlaying()` | Play one of the game's animations by its tag, as the game does (`"Animation.Exploration.Meow"`, `"Animation.Combat.Hit.1"`), cutting off what plays. Whether any montage plays |
| `Game.effects.spawn(system, at, scale)`, `Game.effects.game(name, at, scale)`, `Game.effects.names()` | Play a Niagara system (an object or its path) at a place, or one of the game's own by name (`"Buff"`, `"Debuff"`, `"Climb"`, `"Poisoned"`, `"PickUp"`...). An effect, `{component, playing(), stop()}`, which goes by itself when it ends |
| `cat:movement()`, `cat:setJumpSpeed(v)`, `cat:setGravity(v)`, `cat:setWalkSpeed(v)` | A cat's or an animal's movement: `{walkSpeed, crouchedSpeed, acceleration, jumpSpeed, gravity, stepHeight, mode}`. The game leaves the jump and gravity as set. A walking speed stays on a mod's cat or an animal; your cat's is set every frame from its own speeds, so `setWalkSpeed` is refused for it |
| `Game.speeds()`, `Game.setSpeeds(t)`, `Game.resetSpeeds()` | Your cat's own speeds: `{walk (175), run (390), walkAcceleration, runAcceleration, crouch (0.5), climb (1), running, crouching, climbing}`. Set some (the game takes them the next frame), and put back what it had before the first set |
| `Game.useSense()`, `Game.sense()` | Your cat's scent sense (Q), the game's own through its command; how much it shows now (0 to 1) |

### The game's developer switches

The cheats manager carries the developers' own settings. The release build obeys some and ignores
others, so try each one.

| Call | Does |
|---|---|
| `Game.dev.list()` | Every on/off and number setting, with its value (about 50): `{name, type, value, owner}`. A setting that holds one of an enum's values also has `enum` (the enum's path), `choices` (its names and numbers, `{InfiniteLife = 1, Combat = 2, ...}`) and, for a set of flags whose numbers are added up (`GodMode`), `flags = true`. The enum settings are `GodMode`, `ForceClan`, `ForcedRank`, `ForcePlayWrcNarrativeSequence`, `ForcedLocationType`, `ForcedDifficulty`, `ForcedAttackStatusType`, `ForcedDilemma`, `OverridePlatformType`, `OverrideLanguage` and `DrawDebugTrace` (`Game.dev.enums` has their paths) |
| `Game.dev.choices(name)` | An enum setting's names and numbers, read from the game (`Game.dev.choices("GodMode")` is `{None = 0, InfiniteLife = 1, Combat = 2, Stealth = 4, AvoidCombat = 8}`); nil for another setting |
| `Game.dev.get(name)`, `Game.dev.set(name, v)` | e.g. `bAlwaysSucceedAttack`, `bFastHousingCrafting`, `GodMode`, `bAllowCatSizeOverride`, `CatSizeOverride` |
| `Game.dev.fullResource("Stamina", true)` | Keep a resource full: Health, Level, Stamina, StaminaCombat, Currency, FreshKill (the game's `AlwaysHasFullResource`; the switch was set in game, but whether the game obeys it wasn't checked) |

### The save

| Call | Gives |
|---|---|
| `Game.save.file()`, `Game.save.slotData()` | The whole save as of the game's last save, as a table; this cat's slot in it (the one the file names as its current cat, `Shared.General.CurrentCatSlot`). The table is kept while the file stays the same: at the same size its text is compared every 2 s, so a save that rewrote it at the same size (a count going from 6 to 7) is seen up to 2 s late; `Game.save.write()` drops it. Don't change the table: every call gets the same one |
| `Game.save.write()` | Save now (the game's own Save) |
| `Game.save.folder()` | A folder for a script's own files: `WCMods` in the game's Saved folder, beside its saves. Every install makes it, and updating a mod or wcmods leaves it alone |
| `Game.save.slot()` | The save game's slot index (`CurrentSaveSlotIndex`), which isn't the cat's: it stayed 0 while the cat played was the file's slot 8 (`Game.save.slotData()` follows the file) |
| `Game.save.progression(primary, sub)`, `setProgression`, `setting`, `setSetting` | The save manager's number stores: the account-wide progression (`Shared/GameplayProgression/<primary>/<sub>`, not your cat's slot) and the settings. Reading a progression key that isn't there writes it into the save as 0 |

### JSON and enums

- **JSON:** `Game.json.encode(v)`, `Game.json.decode(text)` (null is `Game.json.null`; a number written with a
  point or an exponent, `12.0`, stays a number with a fraction, as Lua's `tonumber` has it; a list comes back
  marked as one, so it's written `[]` again when empty; a byte order mark at the start is passed over; text after
  the value, as in `[] [1]`, is a mistake like any other: nil and why), and `Game.json.list(t)` to write an empty
  table as `[]`.
- **Enums:** `Game.enums.<name>` maps each way, name to number and number to name (`Game.enums.status.Poisoned
  == 3`). The enums are `clan`, `rank`, `trait`, `stance`, `status`, `aiProfile`, `team`, `detectionRange`,
  `stat`, `resource`, `questStatus`, `questResult`, `questType`, `objectiveStatus`, `phase`, `itemType` and
  `characterType`, each one of the game's own (`clan` is `EClanType`; `wcmods/game.py` lists them all), and
  each the whole enum, so the names it ends on are there too: `clan` and `rank` end with `Total` (5),
  `resource` with `Count` (6), and a list of clans made with `pairs(Game.enums.clan)` gets `Total` unless it
  leaves it out (`Game.enums.clan[5]` is `"Total"`).
- **Where the numbers come from:** each enum is read from the game the first time a script looks anything up in
  it (or walks it with `pairs` or `ipairs`, or takes `#`), so a game update that renumbers one is followed.
  While the game's enum can't be read (a script that looks at one as it loads may be too early), the numbers
  are those of build 26184573, the log says so once, and the game is asked again on a lookup five seconds
  later; `getmetatable(Game.enums.clan).fromGame` is true once the table has the game's own. A name the game
  no longer has reads nil, also said once. `next(Game.enums.clan)` sees an empty table until the first lookup:
  walk one with `pairs`. This reading is checked against the exe, and was seen in the game on 2026-10-28
  ([verified.md](verified.md), "2026-10-28, the overhaul's integration build"); a read too early, then the
  game's numbers a little later, hasn't been seen yet.
- **Any of the game's enums:** `Game.enumNames("/Script/SwtQuest.EGiverRole")` gives `{name = number}` (and its
  names in order as a second result), or nil when the game has no such enum. The path is the module the class
  dump lists it under (`/Script/SwtEngine`, `/Script/SwtQuest`, `/Script/SwtAdventure`, `/Script/Wrc`) and the
  enum's name. The names are without the `EGiverRole::` in front and without the `EGiverRole_MAX` the engine
  adds. Four of the game's enums are plain C++ enums (`EDataType`, `ESwtEngineChannel`, `ESwtServicesError`,
  `EPopupCombatState`): their names have nothing in front, and three keep the last `_MAX` name the engine adds
  (`EPopupCombatState`'s `ST_MAX`, named after the prefix their names share), which in game can't be told from
  one an enum has of its own.

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
  The count goes on inside a function UE4SS calls back from its own C++ (`array:ForEach(function ... end)`),
  so the stop can come out of there, through UE4SS's own code: that hasn't been tried in the game yet, so keep
  a long loop out of a `ForEach` in a line you try.
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
