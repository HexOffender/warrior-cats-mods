# Scripts, the Console page and the in-game runtime

This plan covers the parts of Clan Mod Studio that run code in the game:

- script mods (`scripts/` and `settings.json`);
- the Console page and the game bridge;
- the shared Lua runtime (`WCModsGame`, the script bootstrap and the mod menu's own pages);
- a new Tweaks page that needs no code.

It comes from the 2026-10 audit maps for console-scripts, lua-runtime and re, after the skeptics checked them. Claims the skeptics refuted are not planned as bugs.

It was checked against the code on 3af2898 and against the three branches already under way:

- the test harness, `claude/studio-tests`;
- the Leaf and Bark look, `claude/studio-look`;
- the shell, `claude/studio-shell`.

Where one of those branches already does something, this plan says so and builds on it.

## What it is for

**No-code tweaks.** A creator who wants the game to act a little differently while they play should get it by ticking boxes: a key that heals, a clock that stays at dusk, a fresh-kill pile that never runs low. They should not need code, and they should not need to turn on "Allow mods that run code".

**Scripts.** A creator who writes a script should see three things in the studio:
- what is wrong with the script, before Apply;
- whether it loaded when the game started;
- what it said.

**The Console.** It is for the few people who write Lua. It is a place to try a line in the running game. It is clearly marked as advanced, and nothing done there is saved into a mod.

## Where it stands

### What works, and how we know

**The bridge.** `tests/game/test_bridge.py` checks the round trip in the game (`test_lua_round_trip`, `test_lua_errors_come_back`, `test_status`):
- a line runs and several values come back;
- a Lua error comes back as an error;
- globals stay for the next line.

The tests branch adds `test_the_bridge_is_never_or_alive_or_stale` for `GET /game/bridge`.

**The in-game pages.** `tests/game/test_menu.py` checks them:
- the Lua console page: `test_console_page` runs `6 * 7`;
- the Inspector page: `test_inspector_opens_your_cat` finds a Properties section;
- a script's automatic settings page: `test_script_settings_page` finds Game Tweaks' Heal key and Save;
- the Log page: `test_log_page`.

**Building script mods.** Script mods build into `WCModsScript_<id>` with their settings and extra files, as `wcmods/selftest.py` shows (it needs the installed game).

**The luacheck safety net.** It catches a missing `end`, an unbalanced bracket and an unclosed string. Only indirect tests reach it: `tests/unit/test_lua.py` and the other unit tests that compile the Lua wcmods writes.

**Crash safety.** The runtime is careful about crashing the game:
- every engine call sits behind `valid()` and `pcall`;
- objects are looked up again for each level;
- the bridge writes its files whole and then renames them.

### Already done on the branches under way

The shell branch does these:

- **Play no longer hides build warnings.** `onboarding.play` returns its manifest. The drawer closes itself four seconds after Play only when that manifest has no warning and no failed section (`studio/app.js`, `if (path === "/play" && !trouble)`).
- **The install refusal has studio wording.** `pipeline.InstallBlocked` says "press Apply the rest anyway" in the studio and keeps `--force` for the command line. This was the only polish left of the refuted stray-comma claim.
- **The `/game/lua` refusal is in plain words.** It says "allow mods that run code first (Options, on the Settings and repair page)".
- **Broken JSON is refused at save.** A mod file saved from the studio that isn't valid JSON is refused in `mods.file_problem`'s words ("settings.json isn't valid: Expecting ',' at line 3").
- **Pages are unmounted when they leave the side bar.** `app.js` calls a page's `unmount()` when it leaves the side bar, for example when code mods are turned off. Switching to another page still only hides it.
- **Per-mod build failures.** Each section's report has a per-mod `failed` list, and `install()` and `pending()` are rewritten. This plan's `pipeline.py` changes go on top of the shell's version.

The tests branch's CI runs `node --test "tests/studio/**/*.test.mjs"`, so this plan names its page tests `*.test.mjs`.

### What has never been checked

- The studio's own Console page has never been run against the game. `docs/verified.md` (line 233) lists it as not yet verified.
- These have no unit tests:
  - `Bridge.run`;
  - `wcmods/sections/scripts.py`;
  - the cases in `wcmods/luacheck.py`;
  - the `/game/lua` and `/game/inspect` routes;
  - `script_bootstrap.lua` and `bridge.lua`;
  - all of `console.js`.

### Half-finished

- **The Inspector's "everything" switch** has a backend: `bridge.inspect_code(expr, everything)`, and `studio.py` reads `body.get("all")`. But `console.js` never sends it.
- **`find`.** `docs/scripting.md` (lines 474-475) says the studio has the same as the command line's four commands. The page has no `find`.
- **Starting a script mod.** It can only be started from the command line (`wcmods new --kind script`).
- **Script settings in the studio.** A script's `settings.json` has no page in the studio. The only ways to change Game Tweaks' heal key are the game's mod menu or editing the file by hand.
- **The status poll never stops.** `console.js` returns `unmount()`, but switching pages only hides the page. Once the Console has been opened, its status poll runs every 3 s for the rest of the session.
- **`docs/ARCHITECTURE.md`** maps the scripts section to the `console` page. That page neither reads nor writes `scripts/` or `settings.json`.

### Confirmed bugs

Each bug gives file:line, the severity in brackets, and the skeptic's correction where there was one.

1. **Play hid a script's mistake.** `studio/app.js:177` [high]. Play closed the drawer four seconds after it started, and the drawer was the only place a build warning showed. A script whose Lua failed luacheck ("'function' is never closed") went in silently, and nothing on its card said so afterwards.
   - Skeptic's narrowing: a script built with code mods off is not silent, because the card says "Runs code, so the game won't get it...". "Apply to game" keeps the drawer open, but the main button reads "Apply and play", so Play is the common path.
   - The shell branch now keeps the drawer open when Play has warnings.
   - What is left for this plan: a script's mistakes have no home on its card, before Apply or after the drawer is closed.
2. **A timed-out bridge request runs later.** `wcmods/bridge.py:114` [medium]. A request that the game thread doesn't pick up within the timeout (a loading screen, or the game stalled behind the studio window) raises "no reply within 15 s". But it leaves `request.lua` on disk, and the bridge runs it whenever the game ticks again, after the creator was told nothing happened. A probe confirmed it.
   - Correction: a second Run does not queue, because `os.replace` overwrites the stale file. A request runs twice only if the game resumed in between.
3. **Two script mods can share one install name.** `wcmods/sdk.py:361` [medium] (the audit said `scripts.py:29`). Two enabled script mods whose ids differ only in punctuation (`my-mod`, `my_mod`, `my.mod`) map to one UE4SS name, `WCModsScript_my_mod`. `add_ue4ss_mod` assigns into its dict with no check, so the later mod's script and settings silently replace the earlier one's while the Mods page shows both on.
   - Ids that differ only in case also collide on disk (`WCModsScript_My_Mod` and `WCModsScript_my_mod` are one folder on Windows). `mods.create` only makes lowercase ids, but a dropped .zip keeps its folder's name.
   - `cpp.ue4ss_name` has the same shape, so two C++ mods collide the same way.
   - Animations already guard this exact case (`sdk.py:320-322`).
4. **The Console and the top bar disagree.** `studio/sections/console.js:126` [medium]. When the game runs without `WCModsBridge` and an old `status.json` is on disk, the Console chip says "Game not running" while the top bar says "Game running".
   - Run then answers with a command the creator never typed.
   - Root cause (found by the skeptic): `pipeline.pending()` doesn't count turning on "Allow mods that run code" as a change. Line 404 only handles the reverse case. So Play right after allowing code mods starts the game without applying and without the bridge.
5. **A broken frame function floods the log.** `wcmods/lua/game.lua:517` [medium]. A frame function or timer that errors is pcalled, logged and kept. `UE4SS.log` gets `[WCModsGame] onFrame: <error>` once per frame for the whole session, and the Log page shows forty copies.
   - No line says which mod's script it was. UE4SS's print prefix is only `[Lua]`, and the mod's name comes only from `MOD.log` in the bootstrap.
   - `draw.lua:31-37` deduplicates its errors; `game.lua` does not.
6. **A misspelt key stops the rest of a script.** `wcmods/lua/game.lua:587` (585 with modifiers) [medium]. `Game.onKey("f6", ...)` with a name that is not one of UE4SS's `Key` constants passes the raw string to `RegisterKeyBind` outside any `pcall`.
   - UE4SS's "No overload found for function RegisterKeyBind" leaves `main.lua` at that line, so everything registered after it is missing.
   - The Log page shows UE4SS's wording, not a plain message.
   - `onKey` also returns nothing, so a key can't be cancelled the way an `onPress` can.
   - Game Tweaks works around this with its own `Key[S.heal_key]` guard.
7. **Another cat's level is your cat's.** `wcmods/lua/game.lua:1132` [medium; the RE skeptic said low]. `Cat:component("Level")` falls back to the player's `PlayerState` whenever the wrapped cat has none, which is every cat but yours.
   - So `Game.cat(npcActor):level()`, `:xp()` and `:stats()` answer with your cat's numbers.
   - And `:setLevel()`, `:setXp()` and `:setStat()` change your cat, silently.
   - Only a hand-written script can reach this.
8. **Save on the automatic settings page says nothing.** `wcmods/lua/script_bootstrap.lua:107` [low, down from medium]. It shows nothing on success, and logs a failure only to `UE4SS.log`. wcmods' own pages (`catcolours.lua:233-241`, `mouselook.lua:376-382`) draw "Saved to ..." or "Couldn't save: ..." under the button.
9. **The scheduler changes its task table while walking it.** `wcmods/lua/game.lua:514` [low, down from medium]. `runTasks` iterates `tasks` with `pairs()` while callbacks add and remove entries.
   - Only one case breaks: a task that cancels itself and then adds a task in the same callback. That can drop its own key and raise "invalid key to 'next'", which skips the other tasks for that frame. The loop keeps running.
   - No shipped script cancels itself.
10. **The dialogue claim lapses.** `wcmods/lua/game.lua:2426` [low, down from medium]. The dialogue claim is renewed only by `say()`. A script that says one line and waits for a key loses the claim half a second later, and another mod's cat in reach can open a box over it.
   - The sandbox and both example scripts call `say()` every frame, so nothing shipped overlaps today.

### Confirmed, but already fixed or planned elsewhere

These are listed so nobody plans them twice:

- **`wcmods/pipeline.py:446`** [low, polish]: the `--force` wording in the refusal. Done on the shell branch (`InstallBlocked.describe`).
- **`wcmods/world.py:59`** [low]: `place_names` and rank-less quest titles. Both the names plan (step 7) and the RE roadmap (step 5) plan it; one of them should own it.
- **`wcmods/exe/signatures.json:109`** [medium]: the level component has no signature sites. After any game update, `Cat:level()`, `xp()`, `stats()` and `setStat()` return nil until wcmods ships new signatures. This is the RE roadmap's step 4, and nothing here touches it.
- **`wcmods/lua/game.lua:1811`** [low]: `INTERACT_COMMAND = 67`. The RE roadmap's step 6.
- **`tools/re/memscan.py:69`** [low]. The RE roadmap's step 5.

### Low findings the skeptics did not check

These are likely but unconfirmed. Most get a one-line fix inside a step below.

**Planned in this plan:**

- **Status bar nag.** `pipeline.py:379` marks a mod "changed" when any file in its folder is newer than the last install. So an in-game Save, or the "Cheats on when the game starts" box, makes the status bar say "1 change to apply" for a file the game re-reads at start anyway (step 6).
- **Empty lists.** `menu.lua:1034` writes an empty list from `settings.json` back as `{}`. Its `LIST` marker is not `Game.json.listMeta` (step 6).
- **Rounded floats.** `menu.lua:1022` rounds floats to six significant digits on every Save (step 6).
- **A Notepad edit is ignored.** `script_bootstrap.lua:59` re-reads `settings.json` with `Game.json.decode`, whose whitespace skip (`game.lua:418`) does not skip a UTF-8 BOM. So a file saved by Notepad is ignored until the next Apply (step 1).
- **A left-out script looks set up.** `scripts.py:51` leaves a script out when code mods are off, but the in-game Installed mods page still lists the mod as set up (step 4).
- **Console page gaps** (step 3):
  - `console.js:77` sends an empty Object box and shows a parse error;
  - `console.js:130` polls forever;
  - `console.js:34` overwrites what was typed when an example is clicked.
- **Two pages.** `script_bootstrap.lua:77` gives a script that makes its page from a timer two pages (step 6).
- **The Log page's filters** (step 5). In `menu_host_pages.lua:128`:
  - the Mods filter hides a script's plain `print` lines;
  - the Errors filter matches UE4SS's own boot dump (`ArIsError`).
- **A gap in `status.json`.** `bridge.lua:85` removes, then renames, `status.json`. For a moment `Bridge.status()` sees no file (step 2).
- **Two `game.lua` lows** (step 1):
  - `hide()` can't take down a box whose `say()` failed half-way (2458);
  - the dialogue id is the address of a throw-away table (2390).

**Planned by other plans:**

- **The story plan's step 7:**
  - the prompt watcher never stops (2023);
  - removed cats stay in the `npcs` list (2071);
  - `Game.items.drop(nil)` throws a raw error and `Game.npcs.spawn({})` puts a cat at 0,0,0 (1457).
- **The names plan:** `world_names.lua:37`.
- **The RE roadmap:** `world.lua:258` (`World.label`'s cache) and `tools/re/xrefs.py:43`.

**Left out:** the `LoopAsync` fallback (`game.lua:531`). See "Not in this plan".

### Shared with other plans

Several sibling plans (all under review, not under way) plan the same lines. Each should have one owner.

**The runtime fixes in `game.lua`.** The story plan's step 7 lists the same fixes: the scheduler, the error log with the mod's name, `onKey`, `Cat:component("Level")`, the dialogue claim, `hide()` and `talkId`. The RE roadmap's step 6 also has `Cat:component("Level")`.
- This plan's PR 1 is proposed as their one home, with one in-game test each in `tests/game/test_scripts.py`.
- The story plan keeps what only studio cats use: the prompt watcher, `npcWatch`, `items.drop`, `npcs.spawn` and `quests.report`'s description.
- The RE roadmap keeps `INTERACT_COMMAND` and the enums.
- The wording for another cat's level is the RE roadmap's: "only your cat has a level component out of a fight".
- The story plan keeps a failing task running; so does this plan.

**`pending()` and code mods newly allowed.** The mods-setup plan (its bug 11, step 7) fixes the same root cause as bug 4 here, with a new `installed["code"]` key and a condition that some enabled mod has code. Step 2 below proposes one change for both: the condition "code mods are allowed, UE4SS is there, and `WCModsBridge` isn't in `installed_ue4ss`". It is better because:
- it needs no new key;
- it works for an install recorded by an older wcmods;
- it also covers someone who allows code mods only to use the Console, with no code mod on.

**Reading `UE4SS.log`.** The mods-setup plan's `GET /crash` (its step 7) reads the Lua error lines from `UE4SS.log`. It should take them from step 5's `scriptlog.py`, so there is one reader of that file.

**The Console's help page.** The docs-guide plan's step 8 writes `docs/guide/console.md`. Step 3 here changes what that page describes.

## What a creator should be able to do

### On the Mods page

A script mod's card carries the problems with its files right now, as red lines. They are there before any Apply, and they go when the file is fixed:
- "scripts/main.lua, line 1: a `function` is never closed with `end`, so the script won't run"
- "settings.json isn't valid: Expecting ',' at line 3"

Under them is one line about the last game start:
- "Loaded when the game last started", in green;
- "Didn't load when the game last started: scripts/main.lua:3: unexpected symbol near 'x'", in red;
- "Hasn't run since you applied", in grey.

Under More, there are two blocks:
- **Settings.** It shows the rows the in-game page shows, for a script whose mod menu page is the automatic one. It has a Save button and the note "The script reads these when the game starts; while you play, change them on its page in the mod menu".
- **What it said.** The mod's own lines from the log, newest first, with an "Open the log file" button.

### In the game

A script that didn't load says so, once your cat is in the world. A line at the top of the screen reads "My script didn't start: scripts/main.lua, line 3. Insert, then Log, says more" for ten seconds. The mod menu's Overview lists it in red.

### On a new Tweaks page

The Tweaks page is under Make mods and is always listed. It has these rows:
- "Keep my cat's stamina full";
- "Heal my cat with a key", with a key picker;
- "Hold the clock at", with a time;
- "Keep the fresh-kill pile at least", with a number;
- "Skip the story's opening scenes".

It saves `tweaks.json` into the mod on the Editing-mod bar (My mods by default), like every other Make page, and Apply puts it in.

The tweaks run as wcmods' own in-game script, as mouse look and Your cat's colours do. So they don't need "Allow mods that run code", and a mod with tweaks shares without the "runs code" warning. In the game, the mod menu gets a Tweaks page to change them while you play, and its Save writes the same file.

### On the Console page

The page moves under an "Advanced" group and is titled "Try Lua in the game". Its first line says what it is: it types a line of Lua into the running game; nothing here is saved into a mod; Tweaks and the other Make pages change the game without code.

A status strip says one of four things:
- "The game is running and listening (in the forest)";
- "The game is running but not answering: it may be loading, or held still behind another window";
- "The game is running without the studio's connection to it: close the game, press Apply to game, then Play";
- "The game is closed: press Play".

Below it are two cards:
- **"Run a line":** a box, Run, and "Try one" buttons. The output prints `nil` as nil and a table as an indented list.
- **"Look inside an object":** an Object box, Inspect, "Show the engine's own members too", and a filter.

### The five-minute first try

1. Open Tweaks.
2. Tick "Heal my cat with a key" and pick F5.
3. Press Save to mod (My mods).
4. Press "Apply and play".
5. In the forest, run until your stamina bar is low, then press F5. Stamina and health fill.
6. Press Insert. The mod menu's Tweaks page shows the same rows.

Nothing asks to allow code.

### For someone who writes Lua

1. Allow mods that run code.
2. Add Game Tweaks from wcmods-examples.
3. Delete an `end` in its `scripts/main.lua`. The card says at once which line is unclosed.
4. Press Play anyway. In the forest, the top of the screen says Game Tweaks didn't start.
5. Fix the line and Play again. The card says "Loaded when the game last started", and What it said shows "[Game Tweaks] loaded".

## The plan

Each step leaves the studio working on its own.

**Order.** Steps 1 and 2 change code only; the pages change from step 3. Step 7 depends only on the branches under way, so it can land at any time.

**In-game checks** run through the agent: `python wcmods.py agent test <file>`, after `agent install --with <mod folder>` for a throwaway mod. Two rules apply:
- check who launched a running game before an agent command sends it keys;
- never scan with `FindAllOf` through the bridge in a probe.

### 1. Runtime: errors with the mod's name, said once; a key that fails softly; only your cat has a level

**Files:**
- `wcmods/lua/game.lua`, `wcmods/lua/script_bootstrap.lua`, `wcmods/lua/draw.lua`;
- `docs/scripting.md`, `docs/verified.md`;
- `tests/unit/test_lua.py`;
- a new `tests/game/test_scripts.py`, with a throwaway mod in `tests/game/mods/noisy-script/`.

**The mod's name on every line.**
- In `game.lua`, `log()` starts a line with `[<mod name>]` when `Game.modName` is set, and keeps `[WCModsGame]` otherwise.
- The bootstrap sets `Game.modName = MOD.name` right after `require`.
- Each UE4SS mod has its own Lua state with its own copy of the module (the dialogue claim relies on the same fact). So the name cannot leak between mods.
- The bridge and the menu host set no name and keep `[WCModsGame]`.
- `draw.lua`'s `report()` takes the same name from `package.loaded.WCModsGame` when there is one.
- Every runtime message that goes through `log()` now says whose script it was: a key's error, a hook's, "couldn't spawn". That is the first half of the medium UX finding about jargon with no next step; the story plan adds the hints.

**The scheduler.**
- `runTasks` collects the task ids first and loops over that snapshot, skipping an id that was cancelled meanwhile. A callback may then add or cancel freely.
- Failures are deduplicated on `what .. err`, as `draw.lua`'s `report()` does. The first failure is logged, then one line a minute with a count, for example: `[Game Tweaks] every: attempt to index a nil value (field 'cat') (1812 more)`.
- The task keeps running, as the story plan also asks. A timer that only fails while a level loads must not be killed for it.

**`Game.onKey`.**
- It checks `Key[key]` first (a number still passes). For an unknown name it returns false and logs "no key called f6 (UE4SS's names: F6, SPACE, A ...)".
- It lists the key on the Overview only once the key is accepted.
- It wraps `RegisterKeyBind` in `pcall` and logs UE4SS's message on failure.
- It keeps one bind per key and modifiers, with a table of handlers.
- It returns an id that `Game.cancel` also understands.

**Other cats' level.**
- `Cat:component("Level")` uses the fallback to the player's state only when `self:isPlayer()`.
- So another cat's `level()`, `xp()` and `stats()` are nil, and `setLevel()`, `setXp()` and `setStat()` return false with "only your cat has a level component out of a fight".
- A fighter has its own: `Game.fighter(cat):stats()`.

**The dialogue claim.**
- `Game.dialogue.say()` starts, once, a `Game.every(0.25)` that renews `TALK_AT` while `showing()`. `hide()` cancels it.
- `hide()` removes the widget whenever it is in the viewport, whatever `talk.text` says.
- `talkId` keeps its table alive (`local talkKey = {}`).

**The BOM.** The bootstrap strips a leading UTF-8 BOM before `Game.json.decode`, and `ws()` (`game.lua:418`) skips one too.

**Unit tests** read the source, as `tests/unit/test_lua.py` already does, since there's no interpreter:
- `test_log_names_the_script_when_it_has_a_name`
- `test_on_key_checks_the_name_and_returns_an_id`
- `test_level_component_is_only_your_cats`
- `test_run_tasks_runs_a_snapshot`
- `test_dialogue_claim_is_renewed_while_the_box_is_up`
- `test_bootstrap_names_the_mod_for_game_log`
- `test_bootstrap_strips_a_bom`
- every module still compiles under luacheck.

**In-game tests.** `tests/game/test_scripts.py` installs `noisy-script`. Its `main.lua` has an `onFrame` that indexes nil, then `Game.onKey("f6", ...)` followed by `MOD.log("still here")`. Its `settings.json` holds an empty list, for step 6.
- `test_frame_error_is_logged_once_with_the_mods_name`: `agent.log_since(mark)` holds one `[Noisy script] onFrame:` line over two seconds.
- `test_bad_key_does_not_stop_the_script`: the log has "no key called f6" and then "still here".

Two more tests need no throwaway mod, because the bridge has its own Lua state with its own scheduler:
- `test_a_task_that_cancels_itself_and_adds_another_is_fine`. It runs `local id; id = Game.onFrame(function() Game.cancel(id); Game.after(0, function() WCMODS_T = 1 end) end)`. Then `WCMODS_T` is 1 and the log has no "invalid key to 'next'".
- `test_another_cats_level_is_nil`. It spawns a cat beside yours with `Game.npcs.spawn`, as `test_npcs.py` does. Then `Game.cat(WCMODS_TEST_NPC:actorOrNil()):level()` is nil while yours is a number. It reads one object with no scans, and removes the cat afterwards.

These are the in-game tests the story plan and the RE roadmap name for the same fixes; one copy, here.

**Docs.**
- `scripting.md` line 72 becomes true: "Errors in a script go to UE4SS.log with the mod's name, once, then once a minute with a count".
- The keys table says `onKey` takes UE4SS's names, returns an id, and fails with a log line on a wrong name.
- The cat table says another cat's wrapper has no level component.
- The dialogue table says the claim lasts while the box is up.
- `verified.md` records what the in-game run confirmed.

### 2. The bridge: a withdrawn request, a stopped runaway line, a status that tells the truth

**Files:**
- `wcmods/bridge.py`, `wcmods/lua/bridge.lua`;
- `wcmods/studio.py` (`/game/bridge`, `/game/lua`, `/game/inspect`);
- `wcmods/pipeline.py` (`pending()`, as the shell branch rewrote it);
- `tests/unit/test_bridge.py` (new), `tests/unit/test_pipeline.py` (new), `tests/unit/test_studio_api.py` (the tests branch's);
- `tests/game/test_studio_console.py` (new);
- `docs/scripting.md`.

**A request that times out is withdrawn.** In `Bridge.run`, the timeout branch reads `request.lua` and removes it when its first line is `--wcmods-id:<rid>`.
- `bridge.lua`'s `poll()` removes the file before running it, so a file that is still there was never taken.
- The message then says "no reply within 15 s; the request was withdrawn".
- When the file is gone, it says "no reply within 15 s: the game took it and is still running it".

**The status file's gap.** `status()` retries once after 50 ms when `status.json` is missing but its folder exists (the moment between remove and rename).

**A blank object.** `inspect_code("")` raises `ValueError("type an object to look at, e.g. Game.player()")`.

**A runaway line is stopped.** In `bridge.lua`'s `run()`, a count hook is set before the `xpcall` and cleared after it: `debug.sethook(function() error("this line ran too long and was stopped", 2) end, "", 100000000)`.
- The `debug` library is there: `bridge.lua` already uses `debug.traceback`.
- The hook lives in the bridge's own Lua state, so scripts are untouched.
- A call that hangs inside UE4SS's C code is not counted.

**`/game/bridge` tells the truth.** It returns the status plus `"game_running": game_running()` and `"bridge_installed": bridge.NAME in installed_ue4ss`. The `/game/lua` and `/game/inspect` routes turn `BridgeError` into the same words the strip uses (the shell's handler passes a RuntimeError's text through as it is):
- "The game is running without the studio's connection to it: close the game, press Apply to game, then Play";
- "The game is running but not answering: it may be loading, or held still behind another window";
- "The game is closed: press Play".

**The root cause, in `pending()`** (on the shell's version, which reads `cfg.peek()`). When code mods are allowed, UE4SS is there and `WCModsBridge` is not in `installed_ue4ss`, `redo` gains "mods that run code are allowed now, and the game doesn't have them yet".
- The bridge goes in with every install while code mods are allowed (`pipeline.py:289`), so Play then applies first.
- This is the one change proposed for the mods-setup plan's bug 11 as well (see "Shared with other plans").

**Unit tests** in `tests/unit/test_bridge.py`, all against a temp folder with no game:
- `test_no_status_means_no_game`
- `test_status_age_decides_alive`: 6 s old is dead, 1 s old is alive.
- `test_timeout_withdraws_the_request`: the file is gone, and so is the lock.
- `test_timeout_leaves_a_request_the_game_took`: a thread removes `request.lua` first, and the message says it's still running.
- `test_reply_with_another_id_is_ignored`: a thread writes a reply with the wrong id, then the right one.
- `test_lock_held_by_another_client`
- `test_stale_lock_is_taken_over`
- `test_half_written_status_is_none`
- `test_status_retries_during_a_rewrite`
- `test_inspect_code_refuses_a_blank_expression`
- `test_inspect_code_compiles` (luacheck).

In `tests/unit/test_pipeline.py`:
- `test_pending_counts_code_mods_newly_allowed`: it asks for an Apply with no code mod on, and stays quiet once the bridge is in `installed_ue4ss`.

With the harness fixture:
- `test_the_bridge_is_never_or_alive_or_stale` (the tests branch's). It compares the whole answer, so it gains the two new keys.
- `test_game_bridge_reports_running_without_the_bridge`.

**In game.** `tests/game/test_studio_console.py` builds a `Studio` in-process. It posts `/game/lua` with `return 6 * 7`, posts `/game/inspect` with `Game.player()` (expecting `props`), and reads `/game/bridge` (expecting `alive` and `bridge_installed`). That is the check `verified.md` has been missing for the Console page.

Two manual checks:
- `while true do end` from the page comes back as "stopped" within a few seconds;
- a Run pressed on a loading screen does not change the clock once the forest is in.

**Docs.** The bridge section of `scripting.md` gains:
- the folder;
- "a request that isn't picked up within the timeout is withdrawn";
- "a line is stopped after about a hundred million steps";
- "any program that can write that folder can run Lua in the game".

### 3. The Console page: advanced, plain, and honest about the game

**Files:**
- `studio/sections/console.js`, `studio/sections/console.css`;
- `studio/app.js`: one line, on top of the shell's `app.js`. `GROUPS` gains `advanced: "Advanced"` as its last entry. Without it, the page would sort first under a bare "advanced", because `renderNav` ranks a group it doesn't know as -1;
- `wcmods/studio.py`: the `CODE_SECTIONS` entry gets `"group": "advanced"` and the title "Try Lua in the game";
- `studio/sections/settings.js`: the "Game console" option's words;
- `wcmods/lua/menu_host_pages.lua`: the in-game "Lua console" page's title;
- `docs/guide/console.md`, `docs/scripting.md`, `README.md`;
- `tests/studio/console.test.mjs`.

**The page's head.** It uses the look branch's `wc.pageHead({eyebrow: "Advanced", title: "Try Lua in the game", lede, help})`, with the lede from "What a creator should be able to do".

**The status strip** has four states, fed by `/game/bridge`:
- **listening:** `alive`;
- **not answering:** `game_running` and `bridge_installed`, but not `alive`;
- **without the connection:** `game_running`, but not `bridge_installed`;
- **closed:** not `game_running`. Play applies first when the bridge is missing (step 2), so "press Play" is right whether or not the bridge was ever installed.

Level names become words: `L_WorldMap_01_P` is "in the forest", `L_MainMenu` is "in the main menu", and none is "loading". Run and Inspect are disabled, with the strip's sentence as their title, unless the game is listening.

**The poll.** `poll()` returns early while `root.hidden` is true. The shell unmounts a page only when it leaves the side bar, so the page has to stop its own requests while another page is open.

**The input box.**
- An example button inserts its text at the cursor on a new line when the box isn't empty.
- Ctrl+Up and Ctrl+Down step through lines run before. Plain Up still moves the cursor.

**The output.**
- `nil` prints without quotes.
- A single string or number prints plainly.
- A table prints as an indented `key: value` list.
- The milliseconds show as a muted label.

**Inspect.**
- It sends `all` from a "Show the engine's own members too" box.
- It refuses an empty Object with "Type something to look at, e.g. Game.player()", before asking the server.

**The examples.**
- "Nearby animals" is dropped. It is a `FindAllOf` scan, the kind recorded crashing the game right after entering the world, and the in-game Nearby page lists the same thing.
- An example whose job a no-code page does says so beside its output:
  - "Set 6:00": "Tweaks' Hold the clock at keeps a time without code";
  - "Fresh-kill" and "Your cat": "the Save page changes these without code".

**Three "consoles", three names.**
- The Options row becomes "The game's own command window (~ or F10, for engine commands like god and slomo with cheats on)".
- The in-game page becomes "Lua (advanced)".
- The studio page is "Try Lua in the game".

**Tests** in `tests/studio/console.test.mjs`, with the DOM shim (`tests/studio/lib/dom.mjs`) and a stubbed `api`:
- the four strip states, from four `/game/bridge` answers;
- Run is disabled while the game isn't listening;
- a reply `{ok: false, error}` renders an error line and keeps the input;
- a thrown fetch error enables Run again;
- an empty Object box never calls the server;
- an example does not overwrite typed text;
- the poll stops while the pane is hidden.

In game, the `test_studio_console.py` test from step 2 covers the routes.

**Docs.**
- `scripting.md` says the studio has Run and Inspect (with the engine's members), and that `find` is the command line's.
- `README.md`'s list of studio pages puts the Console under Advanced.
- `docs/guide/console.md` is the docs-guide plan's page. This PR changes its words for the four states and the names, or writes the page if that plan hasn't yet. It is written for the creator who should probably not be there, and points them at Tweaks.

### 4. A script's mistakes on its card before Apply, and one UE4SS name per mod

**Files:**
- `wcmods/sections/scripts.py`, `wcmods/sections/cpp.py`;
- `wcmods/sdk.py` (`add_ue4ss_mod`), `wcmods/mods.py` (`create`);
- `wcmods/studio.py` (`/mods`), `studio/sections/mods.js`;
- `wcmods/lua/menu_host_pages.lua` (Installed mods);
- `tests/unit/test_scripts.py` (new), `tests/unit/test_luacheck.py` (new), `tests/unit/test_mods.py`, `tests/unit/test_studio_api.py`;
- `docs/formats.md`.

**One check for a script's files.** A new `scripts.problems(mod)` returns sentences in the creator's words:
- it runs luacheck over each `.lua` under `scripts/`, for example "scripts/main.lua, line 1: a `function` is never closed with `end`, so the script won't run";
- it reads `settings.json`, in `mods.file_problem`'s words, and adds "settings.json should hold an object" for a list;
- its result is cached by the files' sizes and times.

**On the card.** `GET /mods` adds `script_problems` for mods with `scripts/`, and `modCard` shows them as red lines. They go away when the file is fixed, before any Apply.

**In the build.** The build uses the same function. `ScriptsSection.build` warns "<mod name>: <sentence>" for each problem. `add_ue4ss_mod` takes `check=False` for the files already checked, so the warning no longer names `WCModsScript_x/Scripts/mod/main.lua`.

A problem stays a warning, as now: that one script won't load, but the rest of the install is fine. The shell's drawer now stays open when Play has warnings, so a build warning from another page is no longer lost either. No per-mod record of warnings in `wcmods.json` is needed, so the format doesn't change.

**One UE4SS name per mod.** `ScriptsSection.collect` compares `ue4ss_name(mod.id).lower()` with every other enabled mod in `ctx.mods` that has `scripts/`. On a match it raises `ValueError("my-mod and my_mod would both go in as WCModsScript_my_mod: rename one of them")`.
- The check is in `collect`, not `build`. A `ValueError` in `collect` fails only those two mods: the section's status is partial, the shell's per-mod `failed` list names both, and `InstallBlocked` refuses. One raised in `build` would roll back every script mod, Menu pages and Sandbox mode included.
- Names are compared without case, because Windows folder names ignore it.
- The shell's `check_file` runs `collect`, so the Editing-mod bar shows the clash at save too.
- `add_ue4ss_mod` raises if a name is already taken, as a backstop.
- `cpp.py` gets the same check.
- `mods.create` refuses an id whose letters and digits match an existing mod's: "my_mod is too like my-mod: pick another name".

**With code mods off.** The warning at `scripts.py:53` (`"allow_code_mods": true in wcmods.json`) is reworded the way the shell reworded `section.py`'s: "<name> has an in-game script (scripts/), which only runs with mods that run code allowed (Options, on the Settings and repair page); left out". `build()` also notes `{"left out": "mods that run code are off"}` for each mod. The in-game Installed mods page then shows that in the danger colour, instead of listing the script as in.

**Tests** in `tests/unit/test_scripts.py`, with the harness's `make_mod` and a `BuildContext` over a temp folder:
- `test_needs_main_lua`
- `test_settings_must_be_an_object`
- `test_settings_with_a_trailing_comma_name_the_line`
- `test_bootstrap_fills_every_token_and_compiles`: the settings have a note, a bool, `1.0`, `3`, `[]`, a nested list and a name. `["speed"] = 1.0` and `["n"] = 3` are present, and no `@TOKEN@` is left.
- `test_settings_page_off`
- `test_mod_name_with_quotes_and_newline`
- `test_code_mods_off_warns_notes_and_adds_nothing`
- `test_ids_differing_in_punctuation_or_case_are_refused_naming_both`: the other script mods still build.
- `test_subfolders_land_under_mod`
- `test_problems_name_the_file_and_line_in_words`

`tests/unit/test_luacheck.py` holds the audit's table of cases:
- `function f() if x then end`;
- a lone `end`;
- `repeat ... end`;
- an unclosed string, and an unclosed `--[[`;
- keywords inside strings, long strings and comments;
- `goto` and labels, `a::b`, `0x1p4`, `.5`, `1e5`, `1..2`;
- CRLF line counts;
- an unclosed `if ... elseif`.

`tests/unit/test_mods.py` and the API tests:
- `/mods` returns `script_problems`, and they clear when the file is fixed;
- `POST /mods` refuses `my_mod` beside `my-mod`.

No game is needed.

**Docs.** `formats.md` gets its missing entry, `### scripts/ and settings.json`:
- what Python accepts: an object;
- `_` keys are notes;
- which value type becomes which control;
- nested values show read-only;
- what an in-game Save does to the file.

### 5. "Did it load? What did it say?", in the studio and in the game

**Files:**
- a new `wcmods/scriptlog.py`;
- `wcmods/studio.py`: `GET /mods/<id>/log`, and `/open` with `what: "log"`, which opens the file itself rather than making a folder;
- `studio/sections/mods.js`;
- `wcmods/lua/script_bootstrap.lua`;
- `wcmods/lua/menu_host_pages.lua` (the Overview and the Log page's filters);
- `tests/unit/test_scriptlog.py` (new), `tests/game/test_scripts.py`;
- a throwaway mod `tests/game/mods/broken-script/`;
- `docs/scripting.md`, `README.md`, `docs/guide/mods.md`.

**Reading the log.** `scriptlog.report(cfg, mods)` reads `UE4SS.log` (`ue4ss.log_path(cfg.win64_dir)`).
- UE4SS starts a new log at each game start, so the file is one session.
- It reads the first 512 KB for UE4SS's own start lines. The installed log, read on 2026-10-28, shows them as `Starting Lua mod 'WCModsScript_<id>'`.
- It reads the last 2 MB for the mod's own lines.
- It tolerates CRLF and a BOM.

For each enabled script mod it finds:
- the start line;
- the mod's lines (`[Lua] [<mod name>] ...`), which after step 1 cover timers and keys too;
- the mod's error lines: the bootstrap's `can't load scripts/main.lua:` and `error:`, plus the agent's `ERROR_LINE` pattern (`wcmods/agent/controller.py:31`), applied only to the mod's own lines, so UE4SS's boot dump never counts.

The session's first timestamp, against the `installed` record's `built` time (both local time), says whether the game has run since the Apply:

```json
{ "session": "2026-10-28 09:12:01", "run_since_apply": true, "started": true,
  "errors": ["scripts/main.lua:12: attempt to index a nil value (field 'cat')"],
  "lines": ["[Game Tweaks] loaded", "[Game Tweaks] healed Fawnstar"] }
```

**The card.**
- Its line comes from the report: "Loaded when the game last started", "Didn't load when the game last started: <the first error>", or "Hasn't run since you applied". A mod that was never installed gets no line.
- What it said, under More, shows the last thirty lines newest first, and "Open the log file".
- The Mods page refreshes the report when the page mounts, when the shell's `installedEvent` fires, and when the top bar's `game_running` turns false.

**In the game.** When a script fails to load or errors at the top level, the bootstrap does two things:
- It adds `<mod name>\t<first line of the error>` to a shared variable, `WCModsMenu.failed`. The Overview shows it in the danger colour at the top, the way it already shows the names warning.
- Once your cat is in the world (`Game.player()`), it draws "<mod name> didn't start: scripts/main.lua, line 3. Insert, then Log, says more." at the top of the screen for ten seconds with WCModsDraw (`Draw.onFrame`, then `Draw.remove`).

This answers the runtime map's high UX finding: when nothing appears, nothing tells the creator why.

**The Log page's filters.**
- Mods keeps every `[Lua]` line, plain `print` lines included.
- Errors matches `error:`, `Error:`, "attempt to", "can't load" and "stack traceback", rather than the bare word.

**Tests** in `tests/unit/test_scriptlog.py`, over fixture text:
- `test_started_and_loaded`
- `test_cant_load_is_an_error`
- `test_runtime_error_carries_the_mods_name`
- `test_ue4ss_boot_dump_is_not_an_error` (`ArIsError` and `bKismetScriptError` lines)
- `test_log_older_than_the_apply_is_not_run_since`
- `test_no_log_file`
- `test_crlf_and_bom`
- `test_start_lines_past_the_tail_are_still_found`
- `test_a_mod_with_no_lines_did_not_start`

**In game,** `tests/game/test_scripts.py` gains:
- `test_a_script_that_doesnt_load_is_named`. It uses `broken-script`, whose `main.lua` is missing an `end`. The report has `started` and one error naming the line, and `agent.menu.read()` on the Overview has "didn't start".
- `test_report_has_the_scripts_runtime_error`, with `noisy-script`.

A manual check: `agent.shot` right after the cat enters the world shows the ten-second note.

**Docs.**
- `scripting.md` and the README's mod menu section say where a script's words and errors show:
  - in the studio: the card, and What it said;
  - in the game: the top-of-screen note, and Insert, Tools, Log;
  - on disk: `<game>\Wrc\Binaries\Win64\ue4ss\UE4SS.log`.
- They also say that a luacheck problem means the script won't load at all, and that a plain `print` now shows under Mods.

### 6. A script's settings in the studio, and an in-game Save that says so

**Files:**
- `studio/sections/mods.js` (the Settings block under More);
- `wcmods/studio.py` (`/mods` says whether a mod has a `settings.json` and the automatic page);
- `wcmods/pipeline.py` (`_newest` and `pending()`, on the shell's version);
- `wcmods/lua/script_bootstrap.lua`, `wcmods/lua/menu.lua`;
- `wcmods/templates/script/settings.json`;
- `tests/studio/mod-settings.test.mjs`;
- `tests/unit/test_pipeline.py`, `tests/unit/test_lua.py`, `tests/game/test_scripts.py`;
- a throwaway mod `tests/game/mods/late-page/`;
- `docs/formats.md`, `docs/scripting.md`.

**Which mods get a Settings block.** Only script mods whose mod menu page is the automatic one (`"settings_page"` is not false).
- Menu pages and Sandbox mode make their own pages and keep their own settings.
- Menu pages' cheats switch stays where it is, on Settings and repair.

**How the block works.**
- It reads `GET /mods/<id>/file/settings.json`, a file the route already allows.
- It renders rows by the bootstrap's rules:
  - a boolean is a switch;
  - a number is a number box. A value written with a `.` keeps step 0.1 and is written back with a `.0` when whole, so `12.0` stays a float for the game;
  - a `#rrggbb` string is a colour;
  - any other string is a text box;
  - a `_` key is a note;
  - anything nested is a read-only box with "edit this one in the file".
- Save writes the text back through `PUT`, in the file's own key order.
- While the game runs, a note says the game already read these, and that a Save on its in-game page will write over them.

**Three optional keys.** The format grows three keys that both pages honour:
- `_help_<key>` shows under that row;
- `_min_<key>` and `_max_<key>` bound a number (`ui.number` already takes `min` and `max`).

Compatibility: older versions show a `_help_<key>` text as a note at the top of the in-game page, and ignore the bounds. A file without these keys is read exactly as before.

```json
{
  "_help": "Game Tweaks' settings. Change them on the mod's card in Clan Mod Studio, or on its page in the mod menu (Insert).",
  "heal_key": "F5",
  "_help_heal_key": "A key UE4SS knows: F1 to F12, a letter, SPACE. Empty for none.",
  "time_of_day": 12.0,
  "_min_time_of_day": 0,
  "_max_time_of_day": 24
}
```

**No more false "1 change to apply".** `_newest` takes a `skip` set. `pending()` skips `settings.json` for a mod with `scripts/` whose `WCModsScript_<id>` is already in `installed_ue4ss`, because that script re-reads the file at start. An in-game Save, or the "Cheats on when the game starts" box, no longer turns Play into "Apply and play". A mod that wasn't installed with its settings still asks for an Apply.

**In the bootstrap.**
- Save keeps a `status` upvalue ("Saved to settings.json." or "Couldn't save: <why>"), drawn with `ui.note` under the button, as `catcolours.lua` does.
- The automatic page leaves out `_min_`/`_max_` keys, and shows each `_help_<key>` under its row.

**In `menu.lua`.**
- `Menu.page` replaces a page with the same id made by the same script, instead of adding a second one. A script's own `MOD.page` made later from a timer takes the automatic page's id, `script:<id>`, so it replaces that page. The tab keeps the mod's name.
- `encode` treats a table whose metatable is `WCModsGame`'s `json.listMeta` (required lazily) as a list, so `[]` survives a Save.
- Floats are written in the shortest form that reads back the same (`%.15g`, then `%.17g`), keeping the `.0` rule.

The script template's `settings.json` shows the `_help_<key>` form.

**Tests.**
- `tests/studio/mod-settings.test.mjs` renders the example above: five rows, the note under Heal key, and the bounds on Time of day. It checks that Save sends `12.0`, not `12`, and keeps the key order.
- `test_pending_ignores_a_script_mods_settings_json_once_installed` in `test_pipeline.py`. It also checks that a mod not installed yet still asks for an Apply.
- A regex test that the bootstrap draws `status`.

**In game,** in `tests/game/test_scripts.py`:
- `test_save_on_the_settings_page_says_so_and_keeps_an_empty_list`, with `noisy-script`. It changes a number and presses Save, reads "Saved to settings.json." on the page, and finds `"keys": []` and the number in the file. Then it puts the file back.
- `test_a_page_made_from_a_timer_is_the_only_one`, with `late-page`. Its `main.lua` calls `MOD.page` from `Game.after(2, ...)`. The test counts the pages with the id `script:late-page`, once.

For the failure wording, remove the folder's write permission by hand.

**Docs.**
- `formats.md`'s new entry carries the `_help_`, `_min_` and `_max_` keys, the Save rules, and what older versions do with them.
- `scripting.md`'s `MOD.page` row says a page made later replaces the automatic one.
- The "settings page for free" paragraph points at the card.

### 7. Tweaks: tick boxes, with no code mods needed

**Files:**
- a new `wcmods/tweaks.py` (validate, merge, script);
- a new `wcmods/sections/tweaks.py`, added to `BUILTIN` in `wcmods/sections/__init__.py` after `MouseLookSection`;
- a new `wcmods/lua/tweaks.lua`;
- `wcmods/mods.py`: `CONTENT` gains `("tweaks.json", "tweaks")`, and `menu_page()` is true for it;
- `wcmods/studio.py`: a `BUILTIN_SECTIONS` entry in the Make mods group, and `tweaks.json` in `MOD_FILES`;
- `studio/sections/tweaks.js`, `studio/sections/tweaks.css`;
- `studio/sections/mods.js` (the "Tweaks" kind label);
- `docs/guide/tweaks.md`, `docs/formats.md`, `docs/ARCHITECTURE.md`, `README.md`, `docs/scripting.md`, `docs/verified.md`;
- `tests/unit/test_tweaks.py`, `tests/unit/test_studio_api.py`, `tests/studio/tweaks.test.mjs`, `tests/game/test_tweaks.py`;
- a throwaway mod `tests/game/mods/all-tweaks/`.

**The model is mouse look.** The tweaks are a section like `mouselook.py`: data in a JSON file of the mod's, and a script that is wcmods' own.
- A Make page edits one file through the shell's `wc.modTarget({file: "tweaks.json"})`, with the dirty guard, Share and the Editing-mod bar as they are. My mods is the default, as on every Make page.
- The section's `collect()` validates the file, so the shell's `check_file` shows a mistake under the bar at save.
- `build()` merges every enabled mod's `tweaks.json`, the higher priority winning each key, as `mouselook.merge` does. It writes one UE4SS mod, `WCModsTweaks`, from `wcmods/lua/tweaks.lua`, with the settings filled in with `lua_value`.
- No mod's own code runs. So, like mouse look and Your cat's colours, it doesn't need "Allow mods that run code", and a shared mod with tweaks carries no "runs code" warning.
- The script uses `WCModsGame`, which goes in with every install that has UE4SS.
- The page says "Needs the script loader (Get set up installs it)" when `/info` says UE4SS isn't there.

**The format,** `tweaks.json`. Every key is optional, and a missing key is off:

```json
{
  "keep_stamina_full": true,
  "heal_key": "F5",
  "hold_time": false,
  "time_of_day": 12.0,
  "min_fresh_kill": 20,
  "skip_intro": false
}
```

`tweaks.validate` refuses mistakes with a sentence:
- a key it doesn't know: "tweaks.json: there's no tweak called 'stamina' (there are keep_stamina_full, heal_key, ...)"; `_` keys are kept as notes;
- a value of the wrong type;
- a `time_of_day` outside 0 to 24;
- a `min_fresh_kill` outside 0 to 100 (the pile's range in `scripting.md`);
- a `heal_key` that isn't one of F1 to F12. F10 is left out, because it opens the game's console when that's on, and so is the mod menu's own key.

The keys and their meaning are Game Tweaks' (`wcmods-examples/game-tweaks`), so what is known to work there works here.

**The script.** `tweaks.lua` does this:
- Every 0.5 s, it tops up stamina, holds the clock (`Game.time.setSeconds`) and keeps the pile at its floor (`Game.freshKill.set`), as Game Tweaks does.
- It heals on a frame function that reads `S.heal_key` each frame with `Game.pressed`, as `Game.onPress` does. So a key changed on the in-game page works at once, it only fires while the game has the focus, and the agent's `key()` can press it.
- It skips the opening scenes the way the Sandbox mode does: the game's own hold-to-skip on `GuiPopupSkipQuest` while a narrative sequence plays (`wcmods-sandbox/sandbox/scripts/world.lua:119-160`, seen in sandbox games).

**The in-game page.** It adds a Tweaks page to the mod menu: switches, a number, a time, and a `ui.choice` of the same keys. Save writes the top mod's `tweaks.json`, keeping its `_` notes, and shows "Saved to mods/<id>/tweaks.json." or "Couldn't save: ...", exactly as mouse look's page does.

Like mouse look, the script carries the settings it was installed with. So a change saved in the game shows as "1 change to apply", and Play applies it.

**The studio page.** One card per area:
- **Your cat:** "Keep my cat's stamina full", and "Heal my cat with a key" with the key picker.
- **The day:** "Hold the clock at", with a time box.
- **The camp:** "Keep the fresh-kill pile at least", with a number from 0 to 100.
- **Starting the game:** "Skip the story's opening scenes".

A foot note says where cheats are: the mod menu's Cheats page, and "Cheats on when the game starts" on Settings and repair. The page doesn't repeat that switch.

The shell's Settings-page sentence lists the Make pages from `/info`, and Tweaks belongs in that list, since it saves into My mods like the others.

**The opening-scenes skip needs one manual check** on a fresh story cat, not a sandbox one. If the opening scene doesn't skip there, the row is left out of the page and the format. Sandbox mode already skips those scenes for its own cats.

A sixth tweak, "Jump to a spot with a key" (using `/game/where` and `Game.cat():teleport`), can follow once the five are in.

**Unit tests** in `tests/unit/test_tweaks.py`:
- `test_every_combination_builds_a_script_that_compiles` (luacheck)
- `test_unknown_keys_and_bad_values_are_refused_in_words`
- `test_heal_key_must_be_one_of_the_offered_keys`
- `test_higher_priority_mod_wins_each_key`
- `test_the_in_game_save_goes_to_the_top_mod_keeping_its_notes`
- `test_tweaks_need_no_code_mods`: with `allow_code_mods` off, `WCModsTweaks` is in the build and nothing warns.

Studio API tests:
- `PUT /mods/my-mods/file/tweaks.json` with a bad key returns the shell's `problems`;
- the mod's card has the "tweaks" kind and no `code`.

`tests/studio/tweaks.test.mjs`: ticking a box and saving writes the key; the picker offers F1 to F12 without F10.

**In game,** `tests/game/test_tweaks.py` installs `all-tweaks`, with every box ticked except the skip:
- `test_stamina_stays_full`: the agent runs for three seconds, and stamina equals `maxStamina`.
- `test_clock_holds`: as `test_hold_the_time`.
- `test_fresh_kill_floor`: the pile is set to 10 through the bridge, and is back at the floor within a second.
- `test_heal_key`: health is lowered through the bridge, `agent.key("F5")`, and health is full. A key posted to the window reaches the game's own input, which this reads.
- `test_the_tweaks_page_saves`: `agent.menu.open("Tweaks")`, change the time, Save, and read the status line and the file. Then put it back.

**Docs.**
- `docs/guide/tweaks.md` is the help panel.
- `formats.md` gets `tweaks.json`.
- The README's Make mods table gains a Tweaks row: "Tweaks | small changes while you play: stamina, a heal key, the clock, the fresh-kill pile, the opening scenes | `tweaks.json` | a UE4SS script wcmods writes (no code mods needed)".
- `ARCHITECTURE.md`'s table gains the `tweaks` section, and its Scripts row becomes "`scripts` | the mod's card (settings); the Console runs Lua live | `scripts/`, `settings.json`".
- `verified.md` records the in-game run and the skip check.

### 8. The docs sweep

**Files:** `docs/scripting.md`, `docs/formats.md`, `docs/ARCHITECTURE.md`, `docs/verified.md`, `README.md`, `docs/guide/console.md`, `docs/guide/tweaks.md`. This rides on the last of the PRs to land.

Each step above updates its own pages. This step reads them end to end once. `scripting.md` also gains the notes the audit found missing:
- `MOD.log` is printf-style, so a `%` in a message must be written `%%`.
- `combatEnd` passes nothing today.
- What is costly to call every frame:
  - `Game.save.file()` and `Game.items.list()` decode the whole save (about 40 ms, cached for 1 s);
  - `Game.quests.objectives` does a `FindAllOf` per call.

`verified.md` moves the studio's Console page to confirmed once `test_studio_console.py` has run. It also records the UE4SS log format that the Log page and `scriptlog.py` depend on, per UE4SS version.

## Not in this plan

**Refuted by the skeptics, so not bugs to fix again:**

- **The Inspector's Find and `wcmods find` crashing the game.** The guards the audit asked for are already there. The recorded crashes were property reads across many objects right after entering the world, which is a general limit of scripting through UE4SS. It stays a reverse-engineering gap. The Console drops its one scanning example, as step 3 says.
- **`Game.find` handing back a dead HUD after a level reload.** The engine collects the old world on a load. A one-line `GARBAGE` flag check in `gameHud()` is fine if someone is in that code.
- **`World.location` and `Game.mapMarker` crashing on a stale actor.** UE4SS's `IsValid` is a null check, so the proposed guard can't tell a destroyed actor from a live one.
- **A `settings.json` with a stray comma blocking Apply.** It is the install guard every section shares. Its wording is done on the shell branch.

**Planned by other plans:** see "Confirmed, but already fixed or planned elsewhere" and "Shared with other plans" above.

**Needs reverse engineering first:**

- "Skip the tutorial" and "unlock all checkpoints" through the cheats manager's switches. The release build ignores `bSkipTutorial` and `bSkipSequences`, and where `ESwtCheatsEnableType` is set is unknown. Skipping the opening scenes with the game's own hold-to-skip (step 7) is a different thing and is known to work in sandbox games.
- A `wcmods find` or Nearby that is safe right after a level load.
- Whether `LoopInGameThreadAfterFrames` keeps ticking while the menu's Pause holds the game. Until that is known, the Console's "not answering" state says it in words.
- The save manager's progression keys, for a tweak that unlocks rank or checkpoints.
- A clean way to end a fight from a key.
- Whether UE4SS's log format is stable across its releases. `scriptlog.py` and the Log page ignore lines they don't recognise.

**Known impossible today:**

- "Give me 5 Dandelion" straight into the inventory from the console or a tweak. Nothing reflected adds to the native inventory; `Game.items.drop` is the only way.
- A "leave this fight" button. `EndCombat` leaves the cat bodiless with the fight menu up.
- Opening one of the game's own screens from a script.

**Also out:**

- A Lua interpreter in CI for the runtime's logic (see the open questions).
- Console history saved per mod as snippets.
- A studio Inspector that edits and calls. The in-game one does, and two half-featured copies are worse than one.
- A "start from a script" choice on Make your own mod. Tweaks covers the no-code wish. Lua writers start from Game Tweaks or `wcmods new --kind script`, and the Console's help page says so.
- The `LoopAsync` fallback (`game.lua:531`, with the same shape in `bridge.lua` and `Menu.page`). It is unchecked, and only matters on a UE4SS without `LoopInGameThreadAfterFrames`. The one Get set up installs has it.
- A "last time the game ran" line in the Apply summary. The card is its home, and a line about the previous session read at Play would confuse a creator who just fixed the script.

## Open questions

1. **Where the Console lives.** Does it stay in the side bar under "Advanced" when code mods are allowed? Or should it only appear from a link on the Settings page's Options, so the side bar never shows a code tool to a creator who turned code mods on for a downloaded mod? The plan assumes the Advanced group.
2. **The studio's Inspector.** Should the studio keep its read-only Inspector, now that the in-game one reads, edits and calls?
   - Dropping it halves `console.js` and the docs.
   - Keeping it helps someone writing a script at their desk with the game running beside.
3. **A Lua 5.4 interpreter in CI.** Is it acceptable: a `tests/lua/` suite with UE4SS stubs, skipped when `lua5.4` is not on PATH? The story plan proposes the same for the sandbox repository (`leafo/gh-actions-lua`), so one decision covers both. It is the only way to test the scheduler, the JSON codec and the dialogue claim without the game.
4. **The settings-metadata keys.** Should `_help_<key>`, `_min_<key>` and `_max_<key>` be the convention, or a single `"_rows": {...}` object? Separate keys survive old versions and hand edits better. One object is tidier for a mod with many settings.
5. **Should a script's luacheck problem block Apply,** as a section's file error does, or stay a warning shown on the card? The plan keeps it a warning: that one script won't load, but the install is fine.
6. **Tweaks without the code switch.** Is it right for a tweaks script that is wcmods' own, with data-only settings, to run without "Allow mods that run code", as mouse look and Your cat's colours already do? The plan assumes yes. If every in-game script should sit behind the switch, the page's top line says so, and nothing else changes.
7. **One owner each.** Who owns the shared runtime fixes (this plan, the story plan or the RE roadmap), and the `pending()` change for code mods newly allowed (this plan or the mods-setup plan)? The plan proposes this one for both, with the bridge-based condition.
