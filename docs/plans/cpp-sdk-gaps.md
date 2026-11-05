# The C++ SDK's gaps

What [cpp-sdk-coverage.md](cpp-sdk-coverage.md) left open when its sixteen steps were done (2026-11-05, build
26337109, #116 to #131), and a plan to close each. As before, the steps are done one at a time in one session, each
its own pull request, reviewed and merged before the next starts. The Lua side stays out of scope, except where the
Lua modules wcmods installs break the C++ mods' game (step 1).

## The gaps

| Gap | Why it was left | Step |
|---|---|---|
| A Lua error, "Ref was not function", logged now and then (no traceback); the harness fails the test it lands in | not traced | 1 |
| Setting the camera (distance, field of view, pitch, lag) | the game rewrites them every frame from the camera actor's settings, whose place moved on 26337109; reading the old place crashed the game | 2 |
| Your cat's walk, run, sprint and climb speeds | the game sets them every frame from the player's exploration settings, which moved too | 3 |
| The world map's own travel, and unlocking a place | the map's Travel picks the place under its pointer, which isn't reflected | 4 |
| Photo mode | no reflected way in | 5 |
| Playing a story scene by its tag, and skipping one | the sequencer managers reflect only talks and the skip popup | 6 |
| What a talk answer's `Score` and `ClanBonding` do | `ResolveBondAnswer` not traced | 7 |

## 1. Lua on one thread

**Found.** The error comes from UE4SS's `Registry::get_function_ref`: a stored function reference that, when a hook,
a timer or a game-thread action came to call it, held something else. No traceback means C++ called it, not Lua.
UE4SS runs Lua on three threads: the game thread (hooks, `ExecuteInGameThread`, `LoopInGameThread*`), each mod's
async thread (`LoopAsync`, `ExecuteWithDelay`) and its event loop (key binds). Only the queues are locked; the game
thread runs Lua without the lock. Two threads in one Lua state at once break its registry, its garbage collector and
its stacks (re doc, *UE4SS in this game*: the "never mix" rule). wcmods' own modules still do it:
- `catcolours.lua` (WCModsCatLook) has a `LoopAsync(500)` beside the mod menu page's per-frame loop;
- `palettes.lua`, `models.lua` and `playstate.lua` each run a `LoopAsync` whose callback calls
  `ExecuteInGameThread`, so it can run while the game thread runs the last one;
- every key bind (`Game.onKey`, the mod menu's Insert and Escape, mouse look's toggle) runs a Lua callback on the
  event loop, and each makes a closure and calls `ExecuteInGameThread` there: Lua allocating on one thread while
  the game thread's frame loop allocates on another.

**The fix.** Timers on the game thread (`LoopInGameThreadWithDelay`, with `LoopAsync` only where it's missing, which
keeps the hazard on such a UE4SS); key binds that only count the press (no allocation, no table write), acted on by
the module's game-thread loop. A mod's script gets the same through its bootstrap, which points its own `LoopAsync`,
`ExecuteWithDelay` and `RegisterKeyBind` at the game-thread calls.

**Proof.** A stress script reproduces the error (or the crash) with the old pattern; the same load with the new
one runs clean for as long. The whole `test_cpp_sdk.py` suite with no Lua error logged.

**Seen (2026-11-05).** In the bridge's Lua state, a per-frame loop building 400 small tables plus a `LoopAsync(1)`
whose callback made 50 strings and queued an `ExecuteInGameThread` making 200: within 2 s the log had `Ref was not
function` (no traceback) three times, `bad argument #1 to 'tostring'` from a numeric `for`'s own counter and
`attempt to concatenate a function value`, then the game crashed. The same work with `LoopInGameThreadWithDelay(1)`
in place of the `LoopAsync`, after the fix was installed: 190 s, 11,146 frames, no error. Under stubs (local Lua
5.4), `Game.onKey`'s bind callback allocated nothing over 10,000 calls and its handlers ran once per press on the
next frame. In game, on a fresh launch: `test_cpp_sdk.py` 48 passed (the real-key test skipped: Windows wouldn't
bring the game in front, so no real key press could be tried), `test_scripts.py` 16 passed, `test_menu.py` 5
passed (the rest need mods not installed, or the game in front), and no Lua error in the log.

## 2. The camera's setters

**Known.** The camera actor (`SwtAdventureCameraActor`, `BP_AdventureCamera_C`, on the controller) keeps its
settings in a struct read in BeginPlay from `Gameplay.Exploration.Camera.*` (re doc, *The exploration camera*, from
build 26184573); each frame its interpolators (`ArmLength`, `FOV`...) write the spring arm and the camera component.

**Find out.** Where the settings struct and the interpolator map sit on 26337109, found from the code that reads
them (BeginPlay's tuning reads, Tick's interpolator lookups) rather than by offset, so the next update can be checked
the same way; which members a change has to go to for it to hold.

**The calls.** `set_camera(CameraSettings)` with distance, field of view, pitch limits and lag; `reset_camera()`.

**Proof.** In game: the camera's distance from the cat and the camera manager's field of view at the new values,
held for seconds of walking; put back after.

## 3. Your cat's speeds

**Known.** The player's exploration settings are loaded at one place (`MoveAndRun` speeds, stamina, jump, turn
rates, the Energetic drain), and the character movement's `MaxWalkSpeed` is rewritten every frame from them.

**Find out.** The settings' place on 26337109, from the loader's tuning reads; which member walking, running,
sprinting and climbing each read.

**The calls.** `player_speeds()` and `set_player_speeds(Speeds)` (walk, run, sprint, climb), and put back.

**Proof.** In game: `MaxWalkSpeed` at the new walk speed seconds later, and the cat covering more ground in the same
time; put back after.

## 4. The world map's travel

**Known.** A checkpoint's Interact opens the world map (`WBP_GuiPopupWorldMap_C`) in travel mode, with Travel on the
map item under its pointer (`CurrentWidgetOverlapping`, a `GuiItemCheckPointMap`); `SetCheckpointUnlockState` and the
checkpoint reads sit next to the bond functions (0x1416A7DE0, 0x1416A7D20).

**Find out.** Which checkpoint a map item is; what Travel calls; how a checkpoint is unlocked so the map and the
save agree.

**The calls.** `open_travel_map()`, `map_travel(place)` through the map's own Travel, `unlock_place(place)`.

**Proof.** In game: a travel through the map to a checkpoint (your cat there after the fade); a locked place
unlocked, shown on the map and kept in the save.

## 5. Photo mode

**Known.** The player's `PhotoModeControlComponent` (`BP_PhotoMode_Control`) holds its camera actor and screen; the
pause menu and a talk's `PhotoMode` action open it; its keys are `Player_PhotoMode_Shoot`, `_Exit` and `_HideUI`.

**Find out.** What the pause menu's button calls, and whether a mod can call it from play.

**The calls.** `photo_mode(on)`, `in_photo_mode()`, `take_photo()`.

**Proof.** In game: photo mode open (its popup and camera), a photo taken, closed back to play.

## 6. Story scenes

**Known.** The sequencer managers keep `RegisteredSequences` and `ActiveSequences`; the first load plays
`Gameplay.Narrative.Prophecy.Intro.<Clan>`; the skip popup ends one safely; `GoToEndAndStop` leaves the game waiting.

**Find out.** The manager's own virtual that plays a registered sequence by tag (read from what the first load calls).

**The calls.** `play_scene(tag)`, `skip_scene()`, the scene's end as an event.

**Proof.** In game: a scene played by tag, in `ActiveSequences`, skipped through the game's popup, play back to the
cat, and the game quits cleanly after.

## 7. A talk answer's bond

**Known.** A bond talk's answers carry `Score` and `ClanBonding`; the game's bond code (`AddPersonalBonding`,
`AddClanScore`, `AddNodeToPersonalBonding`) is signed for C++ (re doc, *Bonds*).

**Find out.** What `ResolveBondAnswer` does with an answer: which bond the score goes to, the node it marks, and
the trait's part.

**The calls.** `Talk.hpp`'s answers apply what the game's would, unless the mod says not to.

**Proof.** In game: a bond talk answered from C++ moves that cat's bond and the clan's as the game's own talk does,
and marks the node.

## Status

| Step | State | Pull request |
|---|---|---|
| 1. Lua on one thread | done: the error traced to Lua run on two threads in one state and reproduced; wcmods' timers on the game thread, key binds that only count; a script's own LoopAsync, ExecuteWithDelay and key binds pointed at the game thread by its bootstrap; the rule in SDK.md and scripting.md | #132 |
| 2. The camera's setters | done: nothing had moved on 26337109 (the crash was a bad read of the interpolators' map); the camera's settings (distance, field of view, tilt, the speed's extra, lag) and your cat's turning and pitch limits as hidden members with signatures; `camera_settings`, `set_camera`, `reset_camera`, seen holding in game | #133 |
| 3. Your cat's speeds | done: unmoved too; the exploration component's walk and run speeds, accelerations, crouch and climb factors and how it's moving as hidden members, signed (the two speed getters are leaf functions .pdata leaves out: `Finder.span` reads them to their ret); `player_speeds`, `set_player_speeds`, `reset_player_speeds`, the game's own per-frame write seen taking them, and more ground walked. There's no sprint apart from running | #134 |
| 4. The world map's travel | done: a place unlocked (and locked) through the game's own SetCheckpointUnlockState, signed (its last argument is the checkpoint, a world context, not a slot); the travel map opened by the checkpoint's Interact (the only way it comes in travel mode); the map moved to put a place under its pointer (its translation, found unreflected) and Travel (Confirm) pressed: the game's own travel there and back | this branch, `claude/cpp-map-travel` |
| 5. Photo mode | not started | |
| 6. Story scenes | not started | |
| 7. A talk answer's bond | not started | |
