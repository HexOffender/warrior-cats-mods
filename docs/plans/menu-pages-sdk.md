# What the Menu pages review found in wcmods

This plan covers wcmods bugs that came out of reviewing the Menu pages mod (the in-game mod menu's pages about the
game, [HexOffender/wcmods-menu-pages](https://github.com/HexOffender/wcmods-menu-pages)). They're in the shared
Lua runtime (`WCModsGame`, `WCModsMenu`, `WCModsWorld`, the script bootstrap, Tweaks), and a few in the C++ SDK.

It comes from three reviews of Menu pages:
- a full review of the mod;
- Copilot's review of [HexOffender/wcmods-menu-pages#1](https://github.com/HexOffender/wcmods-menu-pages/pull/1);
- a second review of that PR's fixes.

A separate skeptic checked every finding, and the wcmods ones were checked again against the code at `f0d062e`
(Clan Mod Studio 0.5.0). The handoff they were written up in is `wcmods-handoff.md` in the Menu pages repository.
File and line references below are as of `f0d062e`.

Menu pages works around every one of these in its PR #1. They're wcmods bugs, though: they hit every script, and
several of wcmods' own pages (the automatic settings page, the Inspector, Tweaks) too.

## What it is for

**Someone writing a script** should be able to trust the runtime's calls to do what `docs/scripting.md` and
`docs/SDK.md` say:
- a menu control hands back the value it was given until the player touches it;
- a call about "nobody" gives nil, never their own cat;
- a Save either writes the whole file or says it couldn't, and never leaves half a file;
- a JSON file with something wrong in it is refused, not half read;
- a move the game refused says so.

**A player** shouldn't see one mod undo another's: two clock holds fighting, or one mod's status line taking over
another's.

**Menu pages** (and any other script that supports more than one wcmods) should be able to tell at runtime which
wcmods it's on, so it can take the fixed path where it's there and keep its workaround where it isn't.

## Where it stands

### What to know before starting

- **Unit tests run no Lua.** `tests/unit/test_lua.py` checks the text of the Lua wcmods writes, with its
  `body(src, start, end)` helper, so a unit test pins the shape of a fix. The in-game agent tests check behaviour:
  `python wcmods.py agent test -k <name>`, with throwaway mods under `tests/game/mods/`.
- **`game.lua`'s main chunk is near Lua's 200-local limit** (188 at `f0d062e`). New state goes in fields of
  existing tables (`fileCache.size`, `Game.dev.enums`), not in new main-chunk locals. `luacheck.py` doesn't catch
  this.
- **A second `local live = {}` at `game.lua:1991`** (the NPC list) shadows the items one at :1597, so code for the
  items has to sit before line 1991.
- **Scripts can't read wcmods' version at runtime.** There's no `Menu.version`, and `Game.version` is a fixed `1`
  (`game.lua:11`). `mod.json`'s `"wcmods"` minimum already lets a mod require a fixed wcmods, but that drops 0.5.0.
- **The game dumps are local only.** `vanilla/` is gitignored, so a unit test that reads `vanilla/sdk/...` (the
  class dumps, `api-index.txt`) skips when it's missing.

### Already fixed

**W13**, the task runner logging a failing callback every tick, was fixed in `881c433` (v0.4.0): `failed()` at
`game.lua:20-60` says it once, then once a minute with a count. `test_lua.py`'s
`test_runtime_errors_are_said_once_then_once_a_minute` and `test_scripts.py`'s
`test_frame_error_is_logged_once_with_the_mods_name` pin it.

### Confirmed bugs

| # | Issue | Where | Priority |
|---|---|---|---|
| W1 | `ui.number` changes a value nobody touched: it rounds, the box clamps, and its 32-bit float reads back off | `menu.lua:696-734` | high |
| W2 | `Fight:current()`, `Fight:mainEnemy()` and `Fighter:cat()` give your own cat when there's nobody there | `game.lua:3335-3345`, through `Game.cat` :1358 | high |
| W17 | `Menu.saveJson` writes in place, ignores write errors, and writes `Game.json.null` as `{}` | `menu.lua:1104-1112`, `script_bootstrap.lua:26-32`, `bridge.lua:79-87` | medium (data loss) |
| W16 | `Game.json.decode` accepts text after the first value; a `null` settings file passes as a table | `game.lua:583`, `script_bootstrap.lua:97-101` | medium |
| W7 | `Game.items` keeps an earlier save's pickup totals | `game.lua:1597-1621`, `World.hpp:221-266` | medium |
| W3 | `Cat:teleport` says it worked when the engine refused the move | `game.lua:1519` | medium |
| W6 | `Game.save.file` decodes the whole save again every second | `game.lua:1328-1340` | medium (performance) |
| W5 | Tweaks' "Hold the clock" and Menu pages' "Hold this time" fight; there's no shared clock hold | `tweaks.lua:20-33`, `game.lua:3127-3140` | medium |
| W4 | `Menu.status` is last-writer-wins, and nobody can tell whose line is up | `menu.lua:1024-1029`, `menu_host.lua:452-477` | medium |
| W15 | `test_menu.py`, Menu pages' release check, covers none of its PR #1's fixes | `tests/game/test_menu.py` | medium (tests) |
| W18 | Scripts can't tell which wcmods they run on | `game.lua:11` | medium |
| W12 | `ui.progress` runs ready-made text through `string.format` | `menu.lua:822-837` | low |
| W11 | `Game.dev.list` gives enum and bitmask settings as bare numbers | `game.lua:3394-3405` | low |
| W14 | A fight's `director`, `Fighter:actor()` and `cat.actor` aren't documented | `scripting.md:396-414` | low (docs) |
| W10 | The quest calls `describe` and `objectives` aren't documented | `scripting.md:385-394` | low (docs) |
| W9 | `Menu.classes()` is undocumented, and scripts used it for GameplayStatics | `menu.lua:75-100` | low (docs) |
| W8 | `World.label`'s cache can return an old label for a recycled address | `world.lua:266-293` | low |

The details of each are in its step below.

## What a script writer should be able to do

- Put a stored value in `ui.number` and get the same value back, frame after frame, until the player changes it;
  a value outside `min`/`max` stays as it is.
- Ask a fight who's up and get nil between turns.
- Save a settings file knowing that a full disk leaves the old file whole and says "couldn't save".
- Hold the clock from any script, see who else holds it, and let go without undoing someone else's hold.
- Set a status line that stays up while their page shows, and ask whose line is up.
- Read `Game.wcmods` to tell 0.6.0 from 0.5.0.

## The plan

Each step is one commit (or a small group) with its unit test and its docs, in the order below, highest first.

**Where it stands (2026-11-04).** Every step is done on the branch `claude/menu-pages-sdk-fixes-604058`, one commit
each, with W6 before W7 (W7's "the game saved since" reads W6's `fileCache.size`). The unit tests pass, every Lua
module wcmods writes compiles with `luac`, and the fixed functions were run against UE4SS stubs with a local Lua 5.4
(not part of the suite: the unit tests run no Lua). In game (build 26337109, with the test mods, all-tweaks and Menu
pages' review branch): every new and extended test passes, `test_scripts.py` (16), `test_menu.py` (17, two skipped:
Game Tweaks not installed, the window behind others), `test_tweaks.py`, `test_world.py`, `test_bridge.py`,
`test_studio_console.py`, and `test_cat.py`'s teleport and GodMode tests. `test_npcs.py`'s
`test_npc_walks_to_a_place` failed where the dev save's cat stands (the den's rock is in the way of its +Y walk) and
passed from open ground 4 m off. Not run: `test_cpp_sdk.py`, which needs the C++ test mod built. Left for later: the
C++ SDK's halves of W6 and W7 (they need a C++ build to check), and W7's two questions for the game (below).

**After #112 merged,** a follow-up PR fixed four low findings from its review: the bootstrap reads a stopped Save's
`settings.json.new` before its `.old` (step 3), a clock hold whose Lua state has gone is no hold (step 8), and two
stale lines of docs (step 10 and `scripting.md`'s `held()` row). Both Lua changes were run against stubs with a
local Lua 5.4, as before; not in game.

**In-game checks** run through the agent: `python wcmods.py agent test <file>`, after `agent install --with <mod
folder>` for a throwaway mod. Two rules apply:
- check who launched a running game before an agent command sends it keys;
- never scan with `FindAllOf` through the bridge in a probe.

### 1. W1: `ui.number` gives back what it was given

**Problem.** Three ways an untouched box hands back a different value, which callers read as the player's change and
write back:
- **Rounding.** With `whole`, frame 2 rounds `GetValue()` (2.5 to 3), compares it with the caller's 2.5, and returns 3.
- **Clamping.** A value outside min/max reads back clamped.
- **Float precision.** `USpinBox` holds a 32-bit float: 100.1 reads back as 100.09999847412109, 123456789 as
  123456792.

It hits the automatic settings page (`script_bootstrap.lua:182-188`), whose Save then writes the change, against
`menu.lua:1065-1066`'s promise; the Inspector (`menu_host_pages.lua:326-328`); the C++ settings page
(`Menu.hpp:369-372`); and Menu pages' Stats before PR #1.

**Fix.** Like `ui.slider`, stretch the range to take the value, but to the next power of two, so there's room to
move it both ways and a write doesn't change the range (which resets the box). Compare what the box shows with what
the box made of the value (`e.base`), not with the value. Clamp agent input to the range.

**Tests.**
- Unit: `ui.number`'s body has `past(value)` and `e.base = e.s:GetValue()`, and no longer rounds `now` before the
  comparison.
- In game: `noisy-script`'s settings get `"far": 100.1, "count": 12, "_max_count": 10`; the settings Save test asserts
  they read and save as 12 and 100.1. `late-page` gets `ui.number("Half", 2.5, { whole = true })`, which reads 2.5
  after a few frames. `test_cpp_sdk.py`'s number checks still pass.

**Docs.** `SDK.md`'s `ui.number` row: a value outside min/max is shown as it is, and the range stretches to take it.

**Menu pages can drop** `around()` and use `whole = true` again (with W18).

### 2. W2: nobody is nobody

**Problem.** `Game.cat(nil)` is your cat, so with no one's turn, no main enemy, or a body that can't be read, these
wrappers hand back the player. Before PR #1, Menu pages' Weaken on such an enemy row set the player's health to 1.
The C++ SDK doesn't do this (`Cat{nullptr}` is false).

**Fix.** Guard the three wrappers: `a ~= nil and Game.cat(a) or nil`. `studio/sections/console.js`'s fight example
calls `x:cat():kind()`, which now errors for a fighter with no body; guard it.

**Tests.**
- Unit: the three bodies have `~= nil and Game.cat(`, and the old one-line forms are gone.
- In game (`test_scripts.py`): `test_a_fight_with_no_one_there_is_not_your_cat`, on empty `Fight` and `Fighter`
  wrappers.

**Docs.** `scripting.md`'s Fights rows say these are nil when it's nobody's turn, there's no main enemy, or the body
can't be read.

**Menu pages can drop** `catAt`/`catOf` (with W18).

### 3. W17: a Save that writes the whole file or says it couldn't

**Problem.** `Menu.saveJson` opens the target with `"wb"`, which empties it, then doesn't check `f:write` or
`f:close`, and returns true. A write cut short (a full disk) leaves a truncated file and says "Saved". Every Lua Save
goes through it: every script's settings page (`MOD.save()`), Tweaks, Mouse look, Your cat's colours. `MOD.save()`'s
fallback without WCModsMenu, and `bridge.lua`'s `writeWhole`, do the same. And `Game.json.null` (an empty table with
a metatable) is written `{}`, so a `null` in a hand-edited file comes back as `{}` on the next Save.

**Fix.** Encode first (an encode error leaves nothing behind), write to `<path>.new`, check the write and the close,
move the old file aside to `<path>.old` (Windows' `os.rename` won't replace a file), rename the new one in, and put
the old one back if that fails. `encode` writes `Game.json.null` as `null`, found through `package.loaded.WCModsGame`
as `listy()` does. The bootstrap's fallback and the bridge's `writeWhole` check their writes the same way.

**After the review.** A Save that stops between the two renames (the game closed) leaves no `settings.json`, the
file before at `settings.json.old`, and the last Save at `settings.json.new`, already read back. The bootstrap read
only the `.old`, and the next Save opened the `.new` with `"wb"`: the last Save was gone. With no `settings.json` it
now reads the `.new` when that decodes to an object, else the `.old`, and logs which. And when the new file can't go
in and the old one can't be put back either, the error says the old one is at `<path>.old` (in `Menu.saveJson` and
the fallback both).

**Tests.**
- Unit: `Menu.saveJson` writes a `.new`, checks `f:write`'s and `f:close`'s results, renames, and puts the old file
  back on a failed rename; `encode` knows `json.null`; the fallback and `writeWhole` check their writes.
- In game: `noisy-script`'s settings get `"gone": null`, and the settings Save test asserts the saved file has `null`.
  A short write can't be made on demand, so that path rests on the unit test.
- After the review: the unit test checks the bootstrap reads the `.new` before the `.old`, and both saves' errors.
  Run against stubs (not in the suite): a stopped Save's `.new` read, a half-written `.new` passed over for the
  `.old`, a bad `settings.json` not passed over, and a failed restore's error naming the `.old`.

**Menu pages can drop** its own `.new`/`.old` save in `world.lua`'s `savePlaces` (with W18).

### 4. W16: JSON with something after it is refused

**Problem.** `pcall(value)` returns after the first value, so `[] [ {...} ]` decodes as an empty list, and a caller
that saves throws the rest away. A top-level `null` decodes to `Game.json.null`, which is a table, so a
`settings.json` holding `null` makes `MOD.settings` that shared sentinel, and the first setting written goes into it.
The bootstrap also drops decode's error and logs "couldn't read settings.json (nil)".

**Fix.** In `decode`, after the value, skip white space and fail with "text after the value" when anything is left
(inside the `pcall`, since `Game.save.file` and `Game.save.state` don't catch errors). In the bootstrap, keep the
error and refuse `Game.json.null`.

**Tests.**
- Unit: the decode `pcall` checks `pos <= #text`; the bootstrap refuses `Game.json.null` and logs `err`. A `null`
  settings file can only be checked this way: the build refuses a `settings.json` that isn't an object.
- In game: `Game.json.decode("[] [1]")` is nil.

**Docs.** `scripting.md` says so. The repository has no changelog: the release notes for the release that brings
this should say that a JSON file with something after its value no longer loads (left for the release).

**Menu pages can drop** `listEnd()` (with W18); it still checks for a list.

### 5. W7: pickups since the level loaded

**Problem.** `live` (`game.lua:1597`), the HUD's pickup totals laid over the save in `Game.items.list`, is never
cleared. Pick up Dandelion (6) in slot A, load slot B (2), and `Game.items.count` still says 6. The same happens
when a slot is reloaded without saving, and when the game saves after the items were used. The C++ SDK's
`detail::Pickups::live` (`World.hpp:221-266`) has the same bug.

**Fix.** Stamp the pickups with the HUD that sent them (the hook's first argument: its address and its name, which
has its instance number), and drop them when the HUD now is another; and remember the save file's size (W6's `fileCache.size`) with them, dropping them when the game has written the save
since. No poller (`Game.on("level")` would start the level poller in every Lua state, which has crashed the game
during loads), and no new main-chunk local: the state goes in one table that takes `live`'s place. The pickups are
dropped for a save only when the save just read is the file as it is now and has another size than at the last
pickup, so a save the game wrote just before a pickup, not yet read, doesn't drop it; that's looked at whenever
there are pickups, once each time the save is decoded. A save rewritten at the same size isn't noticed. The save slot
isn't in the stamp: `Game.save.slot()` stays 0 whatever the cat (#111), and another cat is a new HUD. The review
found the first stamp's holes (it went through `Game.find`, nil for a second after a load, and through the slot). The
C++ `items()` has the same bug; it's fixed in #113, which needed a C++ build to check. `test_cpp_sdk.py`'s Lua-against-C++ count check counts
tags, which agree while no pickup has happened.

**Tests.**
- Unit: `Game.items.list` drops the pickups when the HUD or the save's size changed; the hook stamps them with the
  HUD that sent the message. (The C++ `items()` and its check are #113's.)
- In game: not written. It needs picking up a dropped item with the Interact key, a way back to the main menu, and a
  test that quits and restores its own save; see "Not in this plan".
- C++: `World.hpp`'s `detail::Pickups` and `items()`, the same stamp (the HUD that sent the message, `call.self()`,
  and the save's size): #113.

**Docs.** `scripting.md` says "pickups since the level loaded", and that a same-size save isn't noticed. `SDK.md`'s
C++ row says the C++ SDK keeps them since the mod started until #113.

### 6. W3: a refused move says so

**Problem.** `K2_TeleportTo` returns false when there's no room, and `Cat:teleport` throws that away. Menu pages'
Travel says "Went to X"; `agent.teleport` never raises for a refused move; and the C++ `teleport` already returns
the bool.

**Fix.** Keep the bool; `false, "the game wouldn't move it there (no room)"` when it's false. The check is
`== false`, so a nil from UE4SS keeps today's result.

**Tests.**
- Unit: the body returns `K2_TeleportTo`'s result and checks `moved == false`.
- In game (`test_cat.py`): `K2_TeleportTo` gives a boolean, and `Game.cat():teleport(...)` is true for the +300 move.

**Docs.** `scripting.md`'s teleport row.

### 7. W6: the save file decoded once per change

**Problem.** Every call more than a second after the last re-reads and re-decodes `WrcGame.json` (about 40 ms for
a 500 KB save), changed or not, so a page or `Game.onFrame` that reads items or traits gets a hitch every second.

**Fix.** Keep the decoded table while the file's size hasn't changed: look at the size at most 4 times a second,
and decode again at least every 30 s. A failed decode (the game caught mid-write) keeps the last good table. Move
`fileCache` up to just after `Game.save = {}`, so `Game.save.write` can clear it. The C++ `save_file()` still parses
the file on every call; the same size check there is left for later, with W7's C++ half.

**Tests.**
- Unit: the body checks `f:seek("end")` against `fileCache.size`; `fileCache` is declared before
  `Game.save.write`, which clears it.
- In game: the table `Game.save.file()` gives is the same one 2.5 s later (flaky only if the game saves meanwhile).

**Docs.** `scripting.md`: a same-size rewrite of the save is seen up to 30 s late.

**Menu pages can drop** its 10 s throttles (with W18).

### 8. W5: one clock hold for every script

**Problem.** Tweaks writes the clock every 0.5 s; Menu pages' World page every 1 s; wcmods-examples' game-tweaks the
same. With two holds on, the clock flips between them; with only Tweaks' on, Menu pages' Morning, Dusk and Clock
slider are undone within half a second. `test_cpp_sdk.py`'s clock check races Tweaks.

**Fix.** `Game.time.hold(seconds, who)` and `Game.time.held()`, one hold shared through a UE4SS shared variable
(`"WCModsGame.clockHold"`, `"<seconds>\t<who>"`): the last script to hold it owns it, and letting go only lets go of
your own. Every script that has asked for a hold keeps the clock at the shared hour. Tweaks asks for its hold when its
switch or hour changes (at the start too), lets go when the switch goes off, gives way while another script holds
the clock, and takes it back once nobody holds it; its page says whose hold it is meanwhile. The `shared`, `share`
and `clean` helpers move above `Game.time = {}`. `Game.time.set` and `setSeconds` stay plain writes, which a hold
puts back.

**Tests.**
- Unit: both functions exist and `shared` is defined before `Game.time = {}`; `test_tweaks.py` checks Tweaks'
  script uses `Game.time.hold(`.
- In game (`test_world.py`): `test_clock_hold_is_one_for_every_script`.

**Docs.** `scripting.md`'s Time rows, `formats.md`'s tweaks row and `guide/tweaks.md`.

**Menu pages then:** move Hold this time (and `P.setTime`) to `Game.time.hold` and `held()`. Until it does, it still
writes the clock itself, so with Tweaks' hold on too the two still fight; the docs say so.

**After the review: a hold whose state has gone.** UE4SS keeps a shared variable through a restart of the mods, so
the hold could name a script whose new Lua state never holds again: no state kept the clock at its hour, and Tweaks,
which gives way at the start to a hold that's up, gave way for good (it retakes the clock only when nobody holds it).
The hold is now `"<seconds>\t<who>\t<os.clock()>"`: the holder's 0.5 s task writes the stamp again while the hold is
its own, and `held()` says nil for a hold not kept up for 3 s (`Game.time.holding.STALE`), so Tweaks takes the
clock back within about 3 s. The 3 s are counted from the start of the reader's run of tasks before this one
(`ticks.before`, the scheduler's `lastFrame` made a table), not from now: a frame the game takes long over (a level
loading, the game behind another window) stops every state at once, and the first to run after it would otherwise
take every hold for gone. `os.clock()` is the process's, the same in every state, as the dialogue claim already
uses it. A hold with no stamp is none.
- Unit: the stamp's format, `held()`'s check, the heartbeat in the task, and `ticks.before`.
- Run against stubs (not in the suite), two to four `game.lua` states sharing one store: a live hold is seen by
  another state; after a 10 s frame the first state to run still sees it; a hold whose state stops is none within
  3 s; Tweaks' own `holdClock` gives way to a fresh-looking hold left by a restart, then takes the clock within 4 s;
  it gives way to a live hold and takes the clock back when it's let go.
- In game: not yet (`test_world.py`'s hold test still passes as written: the agent's state keeps its hold up).

### 9. W4: one status line per script, and whose is up

**Problem.** `Menu.status` writes one shared line with no owner, so a script whose line ticks takes over everyone
else's. PR #1 reads the undocumented `Menu.shared("status")` and steps aside when the line isn't its own, which
only works if every script cooperates.

**Fix.** One line per script, and the host chooses: the line of the mod whose page is showing wins; otherwise the
line that went up most recently. Updating a line keeps its place, so a ticking line doesn't take over.
- `Menu.status(text)` keeps its signature, writes `"status.lines"` (`owner\tsince\tline` per script, owner from
  `caller(2)` as `Menu.page` has it) on the game thread, and still writes `"status"` for older hosts.
- The host picks from `"status.lines"` and writes `"status.shown"` (`owner\tline`).
- `Menu.statusShown()` gives the line shown and whose it is. `Menu.ownerOf` is exported for the host.
- `Menu.shared`/`share` get a comment: the host's internals.

**Tests.**
- Unit: `Menu.status` has `caller(2)`, `"status.lines"` and still shares `"status"`; `Menu.statusShown` exists; the
  host reads `status.lines` and writes `status.shown`.
- In game (`test_menu.py`): another script's line stays up against Menu pages' ticking one on a page Menu pages
  doesn't own, and `statusShown()` names it.

**Docs.** `SDK.md`'s `Menu.status` row and its shared-variable list.

### 10. W15: Menu pages' release check covers its fixes

**Fix.** Three tests in `test_menu.py`'s style (`need_pages`, try/finally restore), each failing on Menu pages before
its PR #1:
1. `test_opening_stats_changes_nothing`: fractional and out-of-range stats, XP and regen read the same after Stats
   and its sections are opened.
2. `test_travel_keeps_a_places_file_it_cant_read`: for three broken `places.json` files, the page says it couldn't
   read it, Save this spot says it couldn't save, the file is byte for byte the same, and no `places.json.new` is
   left.
3. `test_another_scripts_status_line_stays_up`: checks wcmods' W4 with a live Menu pages line. On a page Menu pages
   doesn't own (Overview), another script's line stays up against Menu pages' ticking one; on Menu pages' own page
   its line wins and follows your cat's health; and once the other line is cleared, Menu pages' comes back. It passes
   on Menu pages v1.0, and fails only on PR #1's commits before bd3abac, the ones that froze the line.

Plus `agent.menu.status()` / `status_shown()` helpers in `wcmods/agent/menu.py`, in place of raw `ModRef` strings.
The "God mode (nothing hurts you)" label assertion stays as it is.

**Run with:** `python wcmods.py agent install --with ../wcmods-menu-pages/menu-pages --with
tests/game/mods/all-tweaks`, then `python wcmods.py agent test tests/game/test_menu.py`; `-k` matches one substring,
so `-k stats`, `-k travel` and `-k status` run them one at a time.

### 11. W18: the wcmods version, at runtime

**Fix.** `Game.wcmods = "0.6.0"` and `Game.wcmodsNumber` (a comparable number, `major * 10000 + minor * 100 +
patch`), filled through new `@WCMODS@` and `@WCMODS_NUMBER@` tokens in `game.py`'s `lua()` from `wcmods/__init__.py`'s
`__version__`. `Game.version` stays `1`. A script checks `(Game.wcmodsNumber or 0) >= 600`; on 0.5.0 both are nil.
`__version__` is still 0.5.0 (the release PR raises it), so a build between releases says 500 and a script keeps its
workarounds there; the docs say so. The release that brings this should be 0.6.0.

**Tests.** Unit: `game.lua()` has the version from `__version__` and no token left; in game, `Game.wcmods` matches
`wcmods.__version__`.

**Docs.** `scripting.md` (Game).

### 12. The low ones

- **W12, `ui.progress`'s text.** `opts.text` is shown as it is; `opts.format` stays a format string but is shown as
  it is when `string.format` fails, and is formatted once. Unit: the body has `opts.text` and `pcall(string.format`.
  Docs: `SDK.md`'s row.
- **W11, the cheats' enums.** A static `Game.dev.enums` maps each enum setting to its enum's path, with
  `flags = true` for `GodMode` (a bitmask: None 0, InfiniteLife 1, Combat 2, Stealth 4, AvoidCombat 8). `Game.dev.list`
  gives those rows `enum`, `flags` and `choices` (read with `Game.enumNames`, cached). `EGodModeTypeFlag` stays out of
  `game.py`'s ENUMS, whose fallback numbers are list positions. Unit: `GodMode` has `flags = true`, and, when
  `vanilla/sdk/api-index.txt` is there, every game-module path names an enum in it.
- **W14, a fight's objects.** Docs only: `fight.director`, `Game.combatDirector()`, `fighter:actor()`,
  `fighter.component` and `cat.actor` in `scripting.md`. Unit: the Fights section names them.
- **W10, the quest calls.** Docs only: `Game.quests.describe`, `objectives` and `manager` rows, `all()`'s and
  `reported()`'s fields, and what `start`, `give` and `track` return. Unit: every `function Game.quests.<name>(` is
  named in the Quests section.
- **W9, `Menu.classes()`.** Docs only: a comment saying it's the menu's own, and a sentence in `SDK.md` pointing
  scripts to `Game.library("GameplayStatics")`. `.statics` keeps working, since released Menu pages 1.0 calls it.
- **W8, `World.label`'s cache.** Key it on the address and the actor's FName (which has the instance number), and
  clear it when a class query refreshes. Unit: the key line and the class branch.

## Not in this plan

- **The C++ halves of W6 and W7.** `World.hpp`'s `save_file()` has no cache and `items()` keeps the pickups as the
  Lua did. Both want a C++ build of the SDK's test mod to check (`python wcmods.py cpp build`, which builds all of
  UE4SS the first time from a fresh checkout), and `test_cpp_sdk.py`'s world test run after.
- **The W7 in-game test.** It needs three things the agent doesn't have: picking up a dropped item with
  `agent.key` on the Interact key, a way back to the main menu (`controller.py`'s `enter()` only goes in), and a test
  that quits, restores its own save and relaunches (`restore_save` refuses while the game runs, and a test that
  leaves the game closed stops the run). Until then, W7 rests on its unit test and the two runtime questions below.
- **Two runtime questions for W7:** that loading a save always makes a new HUD, and that moving between areas in
  `L_WorldMap_01_P` keeps the same one. If the HUD outlives a load, only the save's size still catches a save
  since; another cat's pickups would stay laid over it.
- **Menu pages' own changes.** Each step says what Menu pages can drop; that's its repository's work, after W18.
- **wcmods-examples' game-tweaks clock.** It can move to `Game.time.hold` in its own repository.
- **`ui.slider`'s float comparison** for values above 32 (40.1 reads back 1.5e-6 off). It has the same shape as
  W1's, but sliders take ranges the caller chose; worth a look if a slider is seen changing a value.
- **Left from the review of #112**, each small and none a blocker:
  - W4: `Menu.statusShown()` is stale while the menu is closed and after the window is rebuilt; `caller(2)` names the
    wrong owner when `Menu.status` is called through `pcall` or as a tail call; and a line taken down and put back
    up counts as new, so a script that takes its line down when the menu closes is the newest each time it opens
    (Menu pages 1.0 does; its PR #1 keeps the line up on a wcmods with `Menu.statusShown`).
  - W11: `Game.dev.choices` keeps its cache in the public `Game.dev.enums` entries, and drops the game's order of
    the names.
  - W6: `Game.save.write` drops the last good table, so a read that catches the file half written right after a
    write gives nil.
  - The bootstrap still takes a `settings.json` that holds a JSON list.

## Decisions for the owner

Each was taken as below on the branch; they're for the owner to confirm.

1. **W2:** guard the three wrappers (done), or also make an explicit `Game.cat(nil)` return nil. The plan keeps
   `Game.cat(nil)` as "mine": a script that passes a nil variable to mean "mine" would break, and the wrappers were
   the only callers in the repo that hit it by accident.
2. **W4:** per-script status lines chosen by the host (done), or just an owner field. The plan takes the per-script
   lines: the owner field still needs every script to cooperate.
3. **W5:** the last holder wins, and wcmods' own Tweaks gives way to another mod's hold, taking the clock back once
   that's let go. The plan takes both.
4. **W6:** a same-size save change is seen up to 30 s late. The plan accepts it, and the docs say so.
5. **W16:** a file with junk after its JSON value used to load and now won't (the bootstrap falls back to the mod's
   defaults, as for any bad file). The plan accepts it; the release notes should say so (there's no changelog in the
   repository).
6. **W18:** a new field (`Game.wcmods`, `Game.wcmodsNumber`), leaving `Game.version` alone. The plan takes the new
   field: redefining `Game.version` changes the type of a field that's there.
