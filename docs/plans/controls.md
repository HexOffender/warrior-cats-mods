# Controls: the plan

The Controls page and everything behind it: `controls.json`, `mouselook.json`, `wcmods/keymap.py`,
`wcmods/sections/controls.py`, `wcmods/lua/remap.lua` and the Mouse look card. Written from the
audit map (`audit/controls.json`), the skeptics' verdicts and the code as it stands on
`claude/clan-mod-studio-overhaul-27fa18` (3af2898), then checked a second time against that code, the three
branches under way (`claude/studio-shell` c97edf4, `claude/studio-look` 4a597a8, `claude/studio-tests` 73840ad)
and the sibling plan `docs/plans/docs-guide.md`. Line numbers are from 3af2898. Where it builds on work under
way in other branches (the shell, the "Leaf and Bark" look, the test harness), it says so and names what it
uses from them.

## What it is for

A creator opens the Controls page, moves an action to the key, mouse button or controller button they
like (or gives it a second key), saves, applies, and the game does it from then on, with its own
prompts showing the new key. The page tells them beforehand what each change will and won't do, in
their words, so nothing silently stops working, and afterwards whether it is in the game yet.

## Where it stands

**What works, and how we know.** The pipeline from `controls.json` to the game is sound: `ControlsSection`
collects the four sections (keyboard, gamepad, keys, menus) and merges them across mods, `keymap.native_plan`
turns moved actions and key pairs into commands to send on the new key and to drop from the old one, in play
and in menus, `gameremap.script` writes the plan into `remap.lua` and the build ships it as the `WCModsRemap`
script. That is covered by unit tests in three files whose 49 tests all pass (`tests/unit/test_lua.py`
`test_key_remap_plan`, `test_in_game_remap_plan`, `test_in_game_menu_keys_and_any_command`,
`test_in_game_remap_warnings`, `test_in_game_remap_script`, `test_key_remapper_gets_only_what_the_game_cant_do`,
the two `play` tests and the two mouse look tests; `tests/unit/test_mods.py` runs the remapper's press logic and
the menu pairs through `selftest`; `tests/unit/test_formats.py` reads the save's bindings), and it was seen
working in the game on 2026-10-27 (`docs/verified.md` 182-200): Interact on F, Run on G, Scent tracking on the
middle mouse button, Map on N, H as a second Interact, the pause menu moved with I and K and confirmed with U,
O closing menus, the next tab on PageDown, and the key pictures following. On the page, press-to-bind, the
extra-keys and in-menus lists, the Mouse look card (sensitivity, invert, smoothing, saved straight into a
`mouse-look` mod) and Save/Import/Export through `wc.modTarget` do what they say; the two controller button
presets write what they say but have never been tried in the game. Nothing in the studio's JavaScript has a
test yet (the harness branch adds `wc.js` tests, including `input.keyFromEvent` and `keyLabel`, but none for
this page).

**Half-finished.** Mouse look's `toggle_key`, `pitch_min`/`pitch_max` and `debug` are file-only, although
the in-game page (`mouselook.lua` 355-388) offers them. The backend can move Inventory (I), Quest (K),
Map (M) and Meow (L) (`keymap.SCREEN_KEYBOARD`) and any menu command, but the page has no row for them.
Movement, the camera and mouse buttons in menus reach the game only through `Play with key remaps.bat` and
command-line flags that the page quotes verbatim. Controller buttons and the wheel are shipped but have never
been tried in the game (README 240, verified.md 242), and the old remapper has never been tried in the pause
menu (README 255). `remap.lua` never calls `Menu.key`, so the mod menu's Overview lists Insert and F6 but not
the keys a mod moved. `controls.apply` and the pipeline's `"controls"` save op still exist although nothing
emits them. A D-pad button can stand for a key in `"keys"` (file only), and the page can write a mouse button
into "In menus", which only the deprecated remapper honours. Entries the page has no row for (a keyboard move
of `Button_ShoulderR`, `Player_Play` or another command, a `"keys"` pair standing for J or Enter) are kept on
save but never shown.

**Confirmed bugs** (every high and medium one checked by a skeptic; one refuted, below):

1. [high] `studio/sections/controls.js:152` (`resetDevice`) and `:186` (the row's Default button) write the
   page's `DEFAULTS` as explicit overrides instead of deleting the override, and `DEFAULTS.keyboard.Player_Pause`
   is `"Enter"` (line 30) while the build's `keymap.GAME_KEYBOARD` has Escape (`keymap.py:25`), so "Keyboard
   defaults" saves `"Player_Pause": "Enter"` and `native_plan` turns it into a real move (send Pause on Enter,
   drop it from Escape, in play and menus) with no chip and no warning; the skeptic confirmed by running it and
   noted that the other 14 keyboard entries the button writes are no-ops (the four axis ones reach
   `keymap.plan` and are ignored there as unchanged).
2. [high] `controls.js:48` (`SWAPS.sticks`), `:153` (`resetDevice("gamepad")` writes the four stick actions)
   and, as the skeptic added, the Change button on the controller cell of the four axis rows (`cell()` skips
   only `raw` rows at `:174`; `capture()` offers the stick axes at 313) write stick remaps that `native_plan`
   discards with a warning (`keymap.py:171`), so the page shows "changed" chips and "Apply to game to use it"
   while the sticks never change. "Controller defaults" adds the four warnings even when nothing changed.
3. [high by one of its two skeptics, medium by the other; the root cause of 1 and 10] `controls.js:30` and
   `:127`: the page's idea of "the game's key" is the save (`GET /game/bindings`, `studio.py:439`, which lists
   Pause on Enter) falling back to `DEFAULTS`, while the build uses `keymap.GAME_KEYBOARD`; so putting any
   action on Enter shows a false "Also bound to Pause menu", setting Pause to Escape shows a phantom "changed"
   chip, and the real Enter clash (Confirm and Skip in menus) is never mentioned.
4. [medium] `controls.js:156` (`conflicts()`) compares only the page's 19 rows with each other; the skeptic
   narrowed the list of keys that are really silenced to I, K, M, L and Escape (the `SCREEN_KEYBOARD` keys and
   the real pause key), since `native_plan` drops nothing for J, P, T, V, 1-4, Enter or Backspace and R already
   has a row; the only notice is a jargon line in the Apply drawer, and its advice ("move Player_Show_Inventory
   too") cannot be followed on the page.
5. [medium] `wcmods/keymap.py:209` (corrected from 205): an extra-keys pair whose game key is W/S/A/D or an
   arrow and whose pressed key is I, K, M, L, J, P, T, V or 1-4 goes to `rest` before the own-job warning, and
   `keymap.plan` (line 271) knows only `GAME_KEYBOARD`, so `"I": "W"` (the example in `docs/formats.md:137`)
   silently loses the inventory key under the old remapper; `test_key_remap_plan` (`test_lua.py:97-102`) and
   `selftest.py:104-106` assert the absence of that warning and must change with the fix.
6. [medium] `controls.js:272` and `docs/formats.md:137`: both "Escape for the pause key" examples make Escape
   stop pausing while exploring (Escape is already the pause key; `"keys"` is play-only, so it still closes
   menus), and the page shows nothing when the pair is added.
7. [medium] `controls.js:342`: in the keyboard capture dialog every keydown is captured (Tab binds Tab, Enter
   binds Enter), focus starts on Cancel (line 381) and never moves, so a keyboard-only user cannot reach the
   mouse-only Escape button (line 327).
8. [medium] `controls.js:89`: the page never reads `/info.ue4ss`; without the loader every remap goes to the
   deprecated remapper (`sections/controls.py:44`, `62-63`) while the banner still promises in-game remaps; the
   skeptic noted the studio itself is not silent (the global "No script loader" chip at `app.js:48` and the
   drawer warning), but the page is, and the warning at `controls.py:62` names neither the .bat nor Get set up.
9. [medium] `studio/app.js:177` (corrected from `onboarding.py:126`): `runTask` hides the Play drawer four
   seconds after any Play and never reads `result.remaps`, so the one message saying a movement remap needs
   `Play with key remaps.bat` vanishes; the order of `os.startfile` and the log inside `onboarding.play` is not
   the cause, since `Studio.run` returns the whole log after `play()` returns. (The shell branch's `runTask`
   keeps the drawer open when the manifest has warnings, `trouble` in its app.js; a Play that applied nothing,
   or applied without warnings, still hides it while `result.remaps` is true, so the bug stands there.)
10. [medium] `controls.js:127`: `effective()` and `setKey()` return without writing when the chosen key equals
    the save's value; the skeptic found the "Interact = F in the save" trigger near-unreachable (no released
    wcmods ever wrote bindings into a save), but the same code hits every save through Pause: Change then Enter
    writes nothing, and Default after a change writes `"Player_Pause": "Enter"` (bug 1).
11. [medium] `controls.js:156`: nothing checks a chosen key against the keys wcmods' own scripts listen on
    with `RegisterKeyBind`, which fire regardless of the game: the mod menu's key (Insert by default,
    `menu.py:23`), mouse look's toggle key (F6 by default, `mouselook.py:16`, `mouselook.lua:335`), the Emote
    wheel's T (its `settings.json` `"key"`), emote keys and F11 (the game's fullscreen key); the capture accepts
    Insert and every F-key (`wc.js:475`, `487`) and `native_plan` warns nothing. The same gap exists the other
    way round: choosing on Settings a menu key that `controls.json` already uses.

Refuted: "Mouse look sliders rebuild themselves on every change: focus lost". `wc.keepFocus()` refocuses the
rebuilt `#ml-sens` after `renderMouse()`; the skeptic drove it in Chromium (23 arrow steps, 23 saves, focus
kept). What remains is polish (step 8): each arrow step writes `mouselook.json`, PATCHes the mod and shows a
toast.

Low bugs, not checked by a skeptic, so likely but unconfirmed: `sections/controls.py:21` crashes on a
`controls.json` that is a list (AttributeError instead of a sentence); `controls.py:67` `key_of` lets `null`
and lists through to the plan as the strings `'None'` and `"['F']"`; `keymap.py:205` gives no "still moves
you" warning for a pair whose pressed key is W/S/A/D; `controls.js:37` `ALIASES` lacks half of
`controls.GAMEPAD_ALIASES` so a hand-written `"L2"` shows raw; `controls.js:214` two quick mouse look changes
POST the mod twice; `controls.js:75` heads every bindings error "No save found"; `controls.js:352` binds
"Wheel down" on a sideways wheel (`deltaY === 0`); `wc.js:487` accepts F13-F24, which the game has no key for.

## What a creator should be able to do

The page, top to bottom, with the labels it should carry:

- **Page head** (the look branch's `wc.pageHead({eyebrow, title, lede, help: "help:controls"})`): "Controls",
  lede "Change which key does what. Save to a mod, Apply to game, then play as usual." and the help panel
  showing `docs/guide/controls.md`.
- **Editing mod** bar (the shell's), with the dirty guard and the save-time problems the shell adds, and one
  status line under it: "In the game since your last Apply" or "Saved, not in the game yet: Apply to game"
  (nothing while the mod is off or has unsaved changes, which the bar already says).
- **Without the script loader**, one banner instead of any promise: "Key changes need the script loader: Get
  set up, on the Mods page, installs it. Until then, start the game with Play with key remaps.bat (keyboard and
  mouse only)."
- **Keys while you play**: one table, Action | Keyboard and mouse | Controller (with the existing "Show buttons
  as Xbox / PlayStation / Switch" picker). The rows are Pounce, Interact, Run, Crouch, Scent tracking, Drop,
  Talk to a friend, Place a den decoration, Return to camp, Reset the camera, Pause menu, Inventory, Quest log,
  Map, Meow. Each cell shows the key as a chip, a **Change** button and an **Undo** button only when the row
  was changed (Undo puts the game's key back). Keyboard cells also have a second line "also on H" with
  **Add another key** (controller second keys stay file-only, open question 7). Under a changed cell, one plain
  sentence from the build's own plan: "F does Interact. E still shows the map's legend." or "I does Interact
  and no longer opens the inventory." Rows the game has no controller button for say so instead of a Change
  button. One **Back to the game's keys** button per column (press twice to confirm) clears every change shown
  in it. Controller presets (Nintendo layout, Swap bumpers and triggers) stay, marked "not tried in the game
  yet". No raw action ids anywhere on the page.
- **Moving and the camera**, a group folded under the table: Move forward / back (W / S), Move left / right
  (A / D), Camera up / down (Up / Down), Camera left / right (Left / Right), and the sticks. Its note says the
  one thing that matters: "The game reads these keys itself, so Apply can't change them. For the keyboard,
  start the game with Play with key remaps.bat after Apply. For the sticks, use Steam's controller settings
  (right-click the game in Steam, Properties, Controller); stick speed and inverting are in the game's own
  Settings, Player Configuration." Keyboard cells keep Change and carry the marker "needs Play with key
  remaps.bat"; controller cells have no Change button.
- **In menus**: Confirm (Enter), Back (Backspace), Previous tab (1), Next tab (2), each with "also on"
  and **Add another key** (the game's own key keeps working in menus, so these are always second keys).
- **Which keys are free?**, folded: Key | What it does now | Where from. Every key the game uses (in plain
  words: "E: Interact, and X in menus"), wcmods' own (the mod menu's key and its controller button, mouse
  look's key when mouse look is on, F11 for fullscreen) and the mods that declare a key (the Emote wheel's T
  and its D-pad button, emotes' keys from `animations.json`). The capture dialog greys those out with the
  reason, so the creator picks a free key first time.
- **Mouse look**: the switch, Sensitivity, Invert up/down, Smoothing and **Switches off and on with** (F1-F12
  except F11, or none); **Lowest tilt / Highest tilt** in a closed "Tilt limits" fold inside the card, since
  few creators need them. Labelled "Saves by itself into the Mouse Look mod; needs the script loader." Off with
  a sentence when the loader is missing.
- **For mod makers**, folded: the `controls.json` panel with Copy, Import/Export (the Share card), the
  free-form key pair lists (while you play, in menus) holding every pair no row shows, "Other changes in this
  file" (keyboard or controller entries with no row, each with what the build will do and a Remove), and mouse
  look's "Log what it does" switch.

The five-minute first try: open Controls, on the Interact row press Change, press F; the cell reads "F",
"was E", and under it "F does Interact. E still shows the map's legend."; Save to mod, Apply to game, Play;
in the game F interacts and the Travel prompt shows F. Then Add another key on Interact, press H; the line
says "H does what E does while you explore"; Save, Apply, and both work. Then try Change on Interact and press
I: the cell goes amber, "I does Interact and no longer opens the inventory", and "Which keys are free?" shows
why.

## The plan

Each step leaves the page working and shippable on its own. Tests follow the harness branch's layout:
"model tests" are node:test files at `tests/studio/<name>.test.mjs` (the way `tests/studio/story.test.mjs`
tests `studio/lib/story.js`), here one file, `tests/studio/controls.test.mjs`, which imports the pure model
module directly and `studio/lib/wc.js` through the harness's DOM shim (`tests/studio/lib/dom.mjs`) for the
input-name cases; "browser tests" are in `tests/studio/e2e/controls.test.mjs`, which starts a studio on a
throwaway data folder and drives it with `tests/studio/lib/browser.mjs` the way `e2e/shell.test.mjs` already
does (its `startStudio` and `dataFolder` move to a shared `tests/studio/lib/studio.mjs` when this lands, so
both files use one copy), skipped where no Chromium is found; "API tests" use the harness's
`tests/unit/conftest.py` fixtures (`studio`, `make_mod`, `fake_game`) and live in this plan's own
`tests/unit/test_controls.py`, so they don't collide with the harness branch's `test_studio_api.py`. No
browser test ever presses a real Play or Apply: those are stubbed in the page (below, step 7). No step needs
the game except where "Game check" says so.

### 1. One truth for the game's keys

**Files.** `wcmods/keymap.py`: add `game_keys()` returning `{"keyboard": {**GAME_KEYBOARD, **SCREEN_KEYBOARD},
"gamepad": GAME_GAMEPAD, "built_in": BUILT_IN_KEYS, "axes": AXES, "axis_keys": AXIS_KEYS, "commands":
KEY_COMMANDS, "aliases": controls.GAMEPAD_ALIASES}`; in `native_plan`, a gamepad stick entry equal to the
game's own stick (`GAME_GAMEPAD`) is a no-op like any other unchanged entry, with no warning (today "Controller
defaults" files warn four times). `wcmods/studio.py`: a `GET /game/keys` route returning that plus `"ue4ss"`;
it needs no save, so the page works before the game has ever run. `/game/bindings` stays (`docs/SDK.md` 1429
lists it for mods' own pages) but the Controls page stops using it; `docs/SDK.md` lists `/game/keys` beside it.
`wcmods/cli.py`: `wcmods controls` adds one line under the save's list (not in `--json`), "The game pauses on
Escape, whatever the save says; Apply uses wcmods' own table." New `studio/lib/controls.js`: the page's model
as pure functions over the data `/game/keys` gives (`normalize`, `toJson`, `effective`, `set`, `undo`,
`resetDevice`, `conflicts`, `swap`), importing nothing, so its tests need no page and no DOM.
`studio/sections/controls.js` keeps the view and calls the model.

**Format.** `controls.json` is unchanged. What changes is what the page writes: Undo, a Change to the game's
own key and "Back to the game's keys" delete the entry instead of writing the default, so the Pause row's game
key is Escape and a fresh "Back to the game's keys" produces `{}` (step 3 adds the one exception, another mod
setting the same action). Entries already in a file are written back with the same meaning, even when equal to
the game's key (a no-op in the build, and a later mod may rely on it to win over an earlier one); a controller
alias such as `"LT"` comes back as its full name, `"Gamepad_LeftTrigger"`, which the build reads the same.
`normalize` takes every alias in `GAMEPAD_ALIASES` (`"L2"`, `"circle"`, `"dpad_up"`) and drops a `null` value
instead of writing it back. Files the old buttons wrote load honestly: one made by "Keyboard defaults" (15
keyboard entries, Pause on Enter) shows a single change, Pause on Enter "was Escape", with Undo; one made by
"Controller defaults" now does nothing and says nothing; one made by "Swap sticks" shows step 2's "can't" line
with Remove.

**UI.** `DEFAULTS` and the `/game/bindings` fetch go; the page fetches `/game/keys` on mount. The per-row
Default button goes (Undo does what it promised), "Keyboard defaults" and "Controller defaults" become one
"Back to the game's keys" per column (a `wc.confirmButton`, pressed twice) that deletes the overrides. The
"changed" chip's sr-only text and title read "was E" from the game's key. The "No save found" banner goes with
the fetch (low bug at line 75).

**Tests.** `tests/unit/test_lua.py::test_the_games_own_keys_are_a_no_op`: `native_plan` on
`{"keyboard": game_keys()["keyboard"], "gamepad": game_keys()["gamepad"]}` gives an empty plan,
`gameremap.has_work` False, `keymap.plan(rest)` an empty send and block, and no warnings. Today it fails only on
the four sticks (Pause on Escape is already a no-op in the build); bug 1 itself is the page's, and the model
tests below pin it. API (`tests/unit/test_controls.py`): `test_game_keys_route_serves_the_build_tables`
(`keyboard.Player_Pause` is Escape, `keyboard.Player_Show_Inventory` is I, `ue4ss` false in a temp config, and
it answers with no save). Model: `keyboard reset writes nothing`, `controller reset writes nothing`,
`undo removes the override and nothing else`, `a change to the game's key removes the entry`,
`a loaded entry equal to the game's key is kept`, `normalize accepts L2 and {key: F} and drops null`,
`keys T:W and Y:W round-trip (row T, extra pair Y)`, `conflicts: C shared by Drop and Talk is the games; Drop on X flags Place and Return to camp`
(retired with `conflicts()` in step 3), `setting Pause to Escape is not a change`, `Interact on Enter does not say Pause`,
`a file of the old Keyboard defaults shows one change, Pause`.

**Docs.** `docs/formats.md` 143: `python wcmods.py controls` lists the save's copy, which puts Pause on Enter
while the game pauses on Escape; say so there. `docs/SDK.md` 1429: `/game/keys`. No README change yet.

**Game check.** None: the build's behaviour is untouched except that an unchanged stick no longer warns; the
unit test is the proof.

### 2. Honest movement rows and the page's shape

**Files.** `studio/sections/controls.js`, `studio/lib/controls.js`, `wcmods/keymap.py` for the stick warning's
words. Only if the look branch is in main by then: a new `studio/sections/controls.css` for the new markers (a
"needs the launcher" chip, a "can't" cell) and `"controls"` added to `PAGE_STYLES` in `studio/app.js` (that set
is the look branch's; base `app.js` has none). Otherwise the markers use the existing `chip warn` and `muted`
classes and `app.js` is not touched.

**Format.** Unchanged. The page never writes a gamepad entry for an action in `keymap.AXES`; `swap()` and
`resetDevice` skip axis rows. A stick entry already in a file (hand-written, or from the old "Swap sticks")
still reaches the build and still gets a warning, now in plain words: "the left stick can't be moved by a mod;
change it in Steam's controller settings (right-click the game in Steam, Properties, Controller)" instead of
"gamepad: Player_Movement_Up is a stick, which only Steam Input can move". On the page it shows on its stick
row as that sentence with a **Remove** button; nothing is dropped from the file without the creator's click.

**UI.** `SWAPS.sticks` goes. The eight movement and camera rows become the four two-key rows of the "Moving
and the camera" fold (each key its own Change; `Player_Movement_Up: K` for S, `keys: {T: W}` for W, as today).
Their controller cells are a note, not a button; their keyboard cells carry "needs Play with key remaps.bat".
The page takes its shape: `wc.pageHead` (or the current plain `section-head` until the look branch lands), the
table, the folds, the `controls.json` panel and the "Using your remaps" card gone from the top level into For
mod makers (the card's command lines and `--dry-run` move to `docs/remapping.md` in step 10), every raw id
(`Player_Movement_Up`, "built-in key W") removed from the view, and the banner's paragraph of jargon replaced
by the Moving fold's note and, without the loader, step 7's banner.

**Tests.** Model: `swap(nintendo) maps A/B and X/Y and leaves the sticks`, `swap never touches an axis row`,
`a stick can't be set`, `a loaded stick entry is kept until Remove`. Python: update `test_in_game_remap_warnings`
(`"is a stick"` becomes `"can't be moved by a mod"`). Browser: `the sticks cells have no Change button`,
`the movement cells say they need the launcher`.

**Docs.** `docs/formats.md` gamepad bullet (163-164): the same sentence as the warning.

**Game check.** None.

### 3. What Apply will do, said before Apply

**Files.** `wcmods/keymap.py`: a `NAMES` table (command to plain words: `Player_Interact` "Interact",
`Player_Show_Inventory` "open the inventory", `Button_Confirm` "confirm in menus", `Button_ShoulderR` "the next
tab", `Button_X` "the map's legend" (verified.md: E still toggled it), and so on for every entry of `COMMANDS`
the page can reach) and `say(command)`; every warning `native_plan`, `plan` and `menu_plan` emit rewritten
through it ("I now does Interact, so it stops opening the inventory; give Inventory another key" for
"Player_Show_Inventory is on I, but I now does Player_Interact; move Player_Show_Inventory too"). Bug 5 is
fixed once, in `keymap.plan`: its own-job check (306-308) learns every key that sends one of the game's
`Player_` commands (`SCREEN_KEYBOARD` and `KEY_COMMANDS`: I, K, M, L, J), so `"I": "W"` warns with and without
the loader, worded for the launcher ("with Play with key remaps.bat, I stops opening the inventory").
(`native_plan` needs nothing for it: the pair goes to `rest`, which reaches `keymap.plan` in
`ControlsSection.build` and `remap_plan`; warning in both would say it twice.) In `native_plan`'s `"keys"`
loop, a pressed key in `AXIS_KEYS` gets the same "and still moves you" warning moved actions get at 191-193
(the low bug at 205). `native_plan` also gains one warning the build lacks today, for the moves that break
play without a word: an action moved onto Enter or BackSpace ("Enter now pauses, in menus too, where it still
confirms") and Pause moved off Escape by a `keyboard` entry ("Escape will no longer pause"; the menus pair
`Escape: BackSpace` is not such a move), said as one warning when both apply. So a mod made with the old
"Keyboard defaults" button, which may already be shared, says so in Apply's drawer even where the page never
opens it.
A new `describe(merged, in_game, reserved)` in `wcmods/keymap.py`, next to the plans it runs (not in
`controls.py`, which `keymap` imports: that would be a circular import), runs `native_plan` when `in_game` and
otherwise does what `sections/controls.split` does without the loader (an empty in-game plan, everything left
to `plan` and `menu_plan`; `split` itself stays where it is, since `sections/controls.py` imports `keymap`), then
`plan` and `menu_plan`, and returns `{"rows": {device: {action: {"now", "was", "line"}}}, "pairs": {key: line},
"lines": [...], "needs_launcher": [...], "cannot": [...], "warnings": [...]}`, all plain words, where every
move states its drop ("Enter will pause, and still confirms; Escape will no longer pause" for a hand-written
`"Player_Pause": "Enter"`). `wcmods/controls.py`: a pure `parse(raw)` that raises `ValueError("controls.json
should be an object like {\"keyboard\": {...}}")` for a list and names the action for a `null` or list value
(the two low bugs); `ControlsSection.collect` becomes a thin wrapper over it. `wcmods/studio.py`:
`POST /controls/check` with `{"text", "mod"}`: parses the text, merges it with the other enabled mods'
`controls.json` (the mod under edit at its own priority, as on if it is off, since the shell's Save turns it
on), and returns `describe(...)` plus `"others": {mod id: [actions it also sets, and whether it wins]}` and
`"ue4ss"`. The shell's `Studio.check_file` needs no change: it calls `ControlsSection.collect`, so `parse`'s
sentences become the problems under the Editing-mod bar; `describe`'s lines are shown by the page itself, on
the rows.

**Format.** Unchanged on disk. The warnings' text changes, which `docs/formats.md` quotes in two places, and
`tests/unit/test_lua.py` asserts (nothing else parses it: the shell's drawer only counts warnings). One rule
for what the page writes, now that it knows the other mods: Undo, a Change back to the game's key and "Back
to the game's keys" delete the entry, except when a lower-priority enabled mod sets that action; then the
page writes the game's key explicitly, so this mod's "back to the game's key" wins, and the row says
"puts Interact back on E over example-controls".

**UI.** After every change the page calls `/controls/check` (debounced, 250 ms) and renders
`rows[dev][action].line` under the cell, `needs_launcher` as the chip on movement rows, `cannot` as a refusal
(the page never writes those), and `pairs` under the free-form lists. The page's own `conflicts()` retires
with its model tests: the lines come from the build's plan, so the page and the build can't disagree again.
Under the table, a short "Also in this build" list says only what has no row: other mods' changes
("example-controls also moves Interact, and wins") and entries under For mod makers.

**Tests.** Python, `tests/unit/test_controls.py`: `test_describe_says_each_move_and_its_drop` (Interact on F:
"F does Interact (was E)"; Interact on I: "no longer opens the inventory"; Pause on Enter: "Escape will no
longer pause"), `test_describe_sorts_what_needs_the_launcher_and_what_cant` (`keys T:W` to `needs_launcher`,
a stick to `cannot`), `test_describe_without_ue4ss` (keyboard moves go to `needs_launcher`; controller buttons
and Inventory, Quest log, Map and Meow go to `cannot`, since the old remapper is keyboard and mouse only and
doesn't know the Controls screen's actions), `test_parse_rejects_a_list_a_null_and_a_wrong_section_name`,
`test_parse_accepts_menus_keys_and_flattens_them`, `test_merge_later_mods_win_per_key_and_empty_sections_drop`.
Update in `test_lua.py`: `test_key_remap_plan` and `selftest.py:104` now expect the inventory warning for
`"I": "W"`; the substring asserts in `test_in_game_remap_plan` (its count of two warnings stays),
`test_in_game_menu_keys_and_any_command` and `test_in_game_remap_warnings` move to the new words; add
`test_native_plan_warns_when_a_pressed_key_still_moves_you` (`keys W:E`),
`test_native_plan_warns_when_pause_leaves_escape_or_an_action_lands_on_enter` (the old Keyboard defaults file
gives exactly that one warning),
`test_native_plan_pairs: E:E is nothing, a D-pad source sends on the pad, Escape:P warns about pausing` and
`test_native_plan_and_plan_edges` (the audit's remaining cases: Drop on X warns for Place and Return to camp;
Interact on F with `keys F:W` says F is set both ways; `keymap.plan` on a gamepad section says the remapper is
keyboard and mouse only; `menu_plan` refuses a mouse button standing for a pad button). API:
`test_controls_check_route_merges_with_other_mods_and_says_who_wins`,
`test_controls_check_route_refuses_broken_text_with_a_sentence`. Model: `check lines land on their rows`,
`a cannot item is never written`, `undo writes the game's key when a lower mod sets the action`.

**Docs.** `docs/formats.md` 151-154: the `"keys"` bullet gains "the key you press stops doing its own job
too, and the page and the build say what"; its example at 135-138 becomes `"keys": {"T": "W", "H": "E"}`, and
the `"menus"` example stays `{"Escape": "BackSpace"}` (that one is right: in menus Escape becomes Back, which
closes them, and while you play it still pauses). `controls.js:272`: the note's example becomes "T for W, or H
as a second Interact". README Remapping keys: one sentence that the page and Apply say what each change will
do (the full rewrite is step 10).

**Game check.** None: the plan's commands are unchanged, only its words, three warnings and a route. (The
in-game behaviour behind each sentence is the one verified on 2026-10-27.)

### 4. Which keys are free, and the keys wcmods takes

**Files.** `wcmods/sections/controls.py` (it already reads mods and the config; `keymap` stays pure):
`keys_in_use(cfg, mods)` returning `[{"key", "does", "from"}]` from `KEY_COMMANDS`/`SCREEN_KEYBOARD` through
`keymap.NAMES` ("E: Interact; X in menus"), the mod menu's key (`menusettings.menu_settings(cfg)["key"]`,
mapped from `menu.KEYS` spellings to Unreal names: INS to Insert, HOME to Home, END to End, DEL to Delete,
PAGE_UP to PageUp, PAGE_DOWN to PageDown, F-keys as they are) and its controller button
(`menu_settings(cfg)["pad"]`, `Gamepad_Special_Left` by default, none when `""`), the enabled mouse look mods'
merged `toggle_key` (`MouseLookSection.collect` and `mouselook.merge`; when the merge refuses crossed tilt
limits, each mod's own `toggle_key`), F11 ("the game's fullscreen key"), each emote's `key` in enabled mods'
`animations.json`, and the Emote wheel's `settings.json` `"key"` and `"pad"` when a mod with that id
(`emote-wheel`) is on. Mods' own `Menu.key` entries are only known in game; the fold says so and points at the
mod menu's Overview. `wcmods/studio.py`: `/controls/check` also returns `"in_use"` (no third route).
`keymap.describe` takes the reserved set and adds a line for a clash ("F6 also switches mouse look off and on;
pick another key, or change mouse look's key below"); `ControlsSection.build` passes the same set, so the
drawer says it too, and that also catches the other direction: a menu key chosen on Settings that
`controls.json` already uses warns at the next Apply.

**Format.** Unchanged.

**UI.** The "Which keys are free?" fold. The capture dialog greys reserved keys with the reason (the mod menu's
key and controller button, F11 and mouse look's key refused outright; T, the wheel's D-pad button and emote
keys allowed with the sentence, since the creator may turn that mod off).

**Tests.** Python: `test_keys_in_use_lists_the_games_wcmods_and_mods_keys` (temp cfg with `menu_key` PAGE_UP
and `menu_pad` `""`, a mouse look mod with `toggle_key` F7, an emote on G: PageUp, F7, G and F11 listed with
their sources, Insert and the View button absent), `test_describe_flags_a_reserved_key_once` (Interact on F6
with mouse look on gives one line; with `toggle_key` F7 none). API:
`test_controls_check_route_lists_the_keys_in_use`. Model:
`whyNot(key) refuses the menu key, its pad button and F11 with a sentence`, `whyNot allows T with a warning`.

**Docs.** README: a line under Remapping keys that the mod menu's key and button, mouse look's key and F11 are
taken and the page lists the rest. `docs/formats.md` `mouselook.json`: the toggle key is reserved on the
Controls page.

**Game check.** None.

### 5. More rows, a second key, mouse buttons

**Files.** `studio/lib/controls.js`, `studio/sections/controls.js`, `wcmods/keymap.py` (no behaviour change;
`SCREEN_KEYBOARD` and `KEY_COMMANDS` already carry what the rows need), and for the game check a small
`mouse(button)` in `wcmods/agent/controller.py` with its posting in `wcmods/agent/window.py` (beside
`post_key`), documented in `docs/agent.md` (whose "No mouse" line, 173, then needs the exception).

**Format.** Inventory, Quest log, Map and Meow are `keyboard` entries like any action
(`{"keyboard": {"Player_Show_Map": "N"}}`, verified in game). A second key for an action is a `"keys"` pair
from the new key to the action's game key: `{"keys": {"H": "E"}}` (verified: H opened the travel map), and when
the action has already moved (Interact on F) the pair still names the game's original key E, because that is
the key whose commands `native_plan` copies (`test_in_game_remap_plan` already shows F, pad Y and H together).
`"keys"` pairs work only while you explore, so the page says plainly: a second key does what the game's key
does while you explore, and nothing in menus (H does Interact; a second key for Drop also talks to a friend,
since C does both). The In menus rows are `"menus"` pairs: Confirm "also on U" writes
`{"menus": {"keys": {"U": "Enter"}}}` (verified: U confirmed Resume), Back `{"O": "BackSpace"}` (verified: O
closed menus), Previous and Next tab `{"PageDown": "Two"}` (the verified move used `"Button_ShoulderR":
"PageDown"`; the pair form keeps 2 working, which is the better default for a second key; the agent check
settles it, below). A letter used there still types on the name screen, which the row's line says (the
build's warning at `keymap.py:229`). The game's own menu keys keep working, so these rows never replace a key.
Every pair or entry a row doesn't show (a pair standing for J, Enter while you play, or a second W; a `"keys"`
pair with a D-pad source; a keyboard move of `Button_Skip` or `Player_Play`) stays in the file and is listed
under For mod makers with its line and a Remove, so a mod made before keeps all of it.

**UI.** Four new action rows (controller cell: "no controller button for this", since `GAME_GAMEPAD` has none
and `native_plan` would refuse it), the In menus group with its four rows, "Add another key" (keyboard column
only) with its own capture and a Remove on each second key that drops only the pair. Mouse buttons and the
wheel stay bindable for actions (the middle button is verified) with "not tried in the game yet" beside
Mouse 4, Mouse 5 and the wheel until the game check below clears them; the In menus capture refuses mouse
buttons with "in menus a click goes to the button under the cursor; use a key" (the only thing that honours
them is the deprecated remapper).

**Tests.** Model: `second key writes keys H:E even when the action moved to F`, `removing a second key removes
only the pair`, `a second key for Drop says it also talks`, `confirm also on U writes a menus pair`,
`inventory row writes keyboard Player_Show_Inventory`, `a mouse button is refused in menus with a sentence`,
`pairs and entries without a row round-trip under For mod makers`. Python:
`test_native_plan_second_key_after_a_move_lists_both_keys` (explicit, from the existing icons assert),
`test_native_plan_menu_row_pairs_keep_the_games_key` (U:Enter sends Confirm on U and drops nothing from Enter).

**Docs.** `docs/formats.md`: the `"keys"` bullet's "second key" sentence (while you explore only) and the
Controls screen actions' sentence point at the page's rows. README table rows for second keys and menu keys.
`docs/agent.md`: `mouse(button)` in the controller's table (225).

**Game check.** A new agent test, `tests/game/test_remaps.py`, that installs a test mod folder
(`tests/game/fixtures/remaps/`, a `mod.json` with priority 100 so its keys win over any enabled mod's, and
`controls.json` `{"keyboard": {"Player_Show_Inventory": "O", "Player_Scent_Tracking": "ThumbMouseButton"},
"keys": {"H": "E", "MouseScrollUp": "R"}, "menus": {"keys": {"PageDown": "Two", "U": "Enter"}}}`) with
`agent.install(extra=[...])`, enters the forest on the test cat with `agent.launch(world=True)`, checks with
`agent.key` (posted keys reach `OnKeyPressed`, as the 2026-10-27 checks used) and ends with
`agent.install_normal()`: `test_inventory_row_moves_the_inventory` (O opens the inventory screen, I does not),
`test_second_key_interacts` (H at a tunnel opens the travel map, as E does), `test_next_tab_on_pagedown_in_the_pause_menu`
(the pause screen's tab changes on PageDown and still on 2), and `test_side_button_and_wheel` (the side button
turns scent tracking on; a wheel notch resets the camera). The last uses the new `agent.mouse(...)`, which posts
`WM_XBUTTONDOWN`/`UP` and `WM_MOUSEWHEEL` to the game's window the way the 2026-10-27 middle-button check was
posted (reverse-engineering.md says the side buttons and the wheel reach `OnKeyPressed`); if posted wheel
notches don't arrive, that check becomes a manual one with the game in front, noted in `docs/verified.md`, and
the "not tried" marker stays until it passes. State is read through the bridge one object at a time (the
screen in front, the player's scent tracking flag, the camera's pitch), never with a `FindAllOf` scan, which
crashes the game through the bridge. The game is shared between sessions: the test must own the game
(nobody else's session running it).

### 6. The capture dialog

**Files.** `studio/sections/controls.js` (`capture`, lines 311-392) and `studio/lib/wc.js` (`keyFromEvent`
only: F13 and above return null). No new input module: the harness's DOM shim already lets node:test import
`wc.js`, and `tests/studio/wc.test.mjs` (the harness's file) already covers `keyFromEvent` and `keyLabel`, so
this plan adds only its new cases, in its own `tests/studio/controls.test.mjs`.

**UI.** Focus starts on the dialog itself (`tabindex="-1"`, its title read out), not on Cancel. Any key binds,
except: Escape cancels; Tab and Shift+Tab move focus among the dialog's buttons (the pad branch's code at
334-339, shared); Enter and Space activate the focused button when a button has focus, and bind themselves
when the dialog itself has focus. Chips for the keys the dialog uses itself (Escape, Tab, Enter, Space,
Backspace) and for the mouse buttons and wheel, so every key is reachable by keyboard and a trackpad user can
pick Mouse 4. The unknown-key message loses the DOM code ("That key isn't one the game knows. Try a letter, a
number, an F key or an arrow."); a wheel event with `deltaY === 0` is ignored; reserved keys show greyed with
their reason (step 4).

**Tests.** Model (`tests/studio/controls.test.mjs`, `wc.input` through the DOM shim): `keyFromEvent: F12 is
F12, F13 and F24 are null`. Browser (`tests/studio/e2e/controls.test.mjs`):
`Tab reaches the Escape chip and Enter binds Escape`, `pressing Escape cancels`, `Enter with the dialog focused binds Enter`,
`a sideways wheel binds nothing`, `a reserved key shows its reason and is not bound`.

**Docs.** `docs/guide/controls.md` (step 10) says how to bind Escape, Tab and Enter.

**Game check.** None.

### 7. Without the loader, Play, and whether it's in the game

**Files.** `studio/sections/controls.js`, `studio/app.js` (`runTask`, as the shell branch leaves it),
`wcmods/sections/controls.py` (62-63).

**UI.** The page reads `ue4ss` from `/game/keys` (step 1) and each `/controls/check` answer (step 3), so it
follows Get set up without a reload, and when false shows the one banner from the section above, disables the
Mouse look switch with the same sentence, and marks each row as `describe` says without the loader (step 3):
keyboard rows "needs Play with key remaps.bat"; controller cells and Inventory, Quest log, Map and Meow "needs
the script loader". The shell's `runTask` keeps the drawer open after a Play whose manifest had warnings; this
step adds `|| r.result?.remaps` to that `trouble` test and a long toast "Some of your key changes only work
when you start the game with Play with key remaps.bat", so a Play that applied nothing also keeps it (made on
top of the shell's code, not twice). The no-UE4SS warning at `controls.py:62` names `Play with key remaps.bat`
and Get set up like its sibling at 57-59. The status line under the Editing-mod bar comes from `GET /changes`
(`pipeline.pending`, already there): when the mod under edit is on and in `on` or `changed`, "Saved, not in
the game yet: Apply to game"; when it is on and in neither, "In the game since your last Apply"; when it is
off, or has unsaved changes, nothing (the bar and the shell's "Unsaved changes" say it). It refreshes on the
shell's `wc.installedEvent` and after each save. (Every Make page could use the same line; if the shell later
puts it in `modTarget`, this page drops its own.) The studio still does not start the deprecated remapper (open
question 2).

**Tests.** Python, `test_controls.py`: `test_build_without_ue4ss_requests_no_script_and_names_the_launcher`,
`test_build_with_ue4ss_adds_remap_only_with_work_and_playstate_only_for_the_rest` (the audit's missing build
tests: a lone stick entry adds no UE4SS mod and one warning; `keys T:W` adds `WCModsPlayState` and the "only
work with the old key remapper" line). Browser: `the Play drawer stays open when remaps need the launcher`
(the page's `fetch` replaced through `page.evaluate` so `/api/play` answers `{result: {applied: false,
remaps: true}, log: [...]}`: a real Play would start Steam), `the status line says not in the game yet after
a save`. The existing `test_play_starts_the_game_without_the_old_key_remapper` keeps covering
`onboarding.play`.

**Docs.** README: the loader line in the five-sentence section (step 10).

**Game check.** None.

### 8. The Mouse look card, complete

**Files.** `studio/sections/controls.js` (`renderMouse`, `saveMouseLook`, 212-259), `studio/lib/controls.js`
(a save queue), `wcmods/mouselook.py` (no change: `TOGGLE_KEYS` and the pitch range exist).

**Format.** `mouselook.json` unchanged; the page now writes `toggle_key` (an F-key or `""`), `pitch_min`,
`pitch_max` (within -89..89, the lowest at least a degree under the highest, as the in-game page does) and
`debug`. Files made before keep every key they had (the page writes back what it read, plus what changed).

**UI.** The picker "Switches off and on with" (F1-F12 except F11, and "no key") in the card, the two tilt
sliders in its closed "Tilt limits" fold, debug under For mod makers. Saves are queued through one promise
chain (so two quick changes never POST the mod twice), debounced 300 ms after the last change, and the toast
appears only when the switch itself changed; `render()` no longer rebuilds the card after a settings-only save.
The card is labelled "Saves by itself into the Mouse Look mod" (open question 1). The `mouse-look` id it
creates is the one the examples' mod uses, so an existing one is reused, as today. A new toggle key feeds step
4's reserved keys at the next check.

**Tests.** Python, `test_lua.py`: `test_mouse_look_validate_rejects_bad_values` (sensitivity `"1.5"`, `True`,
0, 11; `toggle_key` `"f6"`, `None`, `"F11"`; smoothing 1500; the unknown `"sensitvity"` lists the known names;
`"_help"` ignored), `test_mouse_look_merge_names_both_mods_for_crossed_tilt_limits`,
`test_mouse_look_build_saves_into_the_top_priority_mod_and_keeps_its_help`. Model: `mouse look saves are queued
and debounced`, `only a switch change toasts`, `tilt sliders keep the lowest under the highest`.

**Docs.** `docs/formats.md` 183-196: the page now offers every setting. The `_help` in the examples'
`mouselook.json` can say so (a follow-up in `wcmods-examples`, not this repo).

**Game check.** Manual: set the toggle key to F7, Apply, start the game, press F7 twice while exploring; the
UE4SS log shows "mouse look off" then "on" (`RegisterKeyBind` reads the real keyboard, so an agent test would
need `agent.hotkey("F7", focus=True)` as `test_keys_pressed` does, which fails when Windows won't give the
game focus).

### 9. Moved keys in the mod menu's Keys list

**Files.** `wcmods/lua/remap.lua`, `wcmods/gameremap.py` (`script` embeds `names`), `wcmods/keymap.py` (`NAMES`
from step 3).

**Format.** The plan handed to the script gains `names = {command = "Interact"}` and `labels = {key = "Mouse
4"}` (the studio's plain key names, for keys a player wouldn't recognise by their Unreal name).

**UI.** In game only: after setup, `pcall(require, "WCModsMenu")` as `mouselook.lua` does (355-357), then one
`Menu.key` per key: each key in `PLAN.play.send` once, named by its `Player_` commands and where they came from
("F: Interact (was E)" for a move, "H: Interact, like E" for a second key; a key whose commands are all
`Button_` ones by the key it stands for, "T: like 1"), and each key that is only in `PLAN.menu.send` (a menus
pair) once with "in menus" ("U: Confirm in menus"). A moved action is in both send sets, so listing both would
show it twice. Mouse buttons and the wheel show by their plain names ("Mouse 4", "Wheel up"). The Overview's
Keys section (`menu_host_pages.lua` 50-58) then lists them beside Insert and F6. Nothing changes when the menu
isn't loaded.

**Tests.** Python: `test_in_game_remap_script_lists_its_keys_in_the_mod_menu` (the Lua contains `Menu.key`,
the names table, each key once, and passes luacheck), and the audit's missing `gameremap` cases:
`test_gameremap_has_no_work_on_an_empty_plan_and_writes_debug` (`has_work` False on an empty plan;
`script(plan, debug=True)` contains `["debug"] = true`).

**Docs.** README: one clause in the five-sentence section.

**Game check.** `test_remaps.py::test_overview_lists_the_moved_keys`: with the step 5 fixture installed,
`agent.menu.open("Overview")`, `page.get("O")` reads "Inventory (was I)" and `page.get("H")` reads
"Interact, like E" (each `Menu.key` line is a field labelled by its key).

### 10. The docs, for a creator

**Files.** `README.md` (Remapping keys, 194-288, and the Controls row at 108-109), `docs/guide/controls.md`
(new; the shell's help panel renders it), `docs/guide/README.md` (lists it), `docs/remapping.md` (new; the
developer notes), `docs/README.md` (lists `docs/remapping.md`), `docs/formats.md`, `docs/ARCHITECTURE.md` (a
link only).

**One owner for two files.** The sibling plan `docs/plans/docs-guide.md` also writes `docs/guide/controls.md`
(its step 5) and moves Remapping keys to `docs/remapping.md` (its step 10). They must be written once: this
step supplies the Controls content and the five sentences; the docs-guide plan supplies the guide's
conventions, which `docs/guide/controls.md` follows; whichever lands first creates the files and the other
edits them (open question 10).

**What README's Remapping keys becomes.** Five sentences and a table, then a link to `docs/remapping.md`. The
heading stays, since `controls.js` links `README.md#remapping-keys` and `docs/formats.md` does too:

1. Change keys on the Controls page in Clan Mod Studio (or in a mod's `controls.json`), Save to mod, Apply to
   game, then start the game any way you like.
2. The new key does the action; the old key stops doing it but keeps its other jobs; the game's prompts and
   its Controls tab show the new key, and the mod menu's Overview lists it.
3. Moving the cat and the camera can't be changed this way, because the game reads those keys itself: for the
   keyboard, start the game with `Play with key remaps.bat`; for the sticks, use Steam's controller settings.
4. If a key already does something else, the page says what it will stop doing before you save, and so does
   Apply; the mod menu's key and button (Insert and View unless you changed them), mouse look's key and F11 are
   taken.
5. Controller buttons haven't been tried in the game yet (and the side mouse buttons and the wheel, until
   step 5's check has run).

| What you change | After Apply | Note |
|---|---|---|
| An action (Interact, Pounce, Run, Crouch, Scent tracking, Drop, Talk, Place, Return to camp, Reset camera, Pause, Inventory, Quest, Map, Meow) on a key, mouse button or controller button | works in the game | the old key keeps its other jobs; Inventory, Quest, Map and Meow have no controller button |
| A second key for an action | works in the game while you explore | it does what the game's key does there |
| A second key for Confirm, Back or the tabs in menus | works in the game | letters still type on the name screen |
| Moving and the camera, on the keyboard | only with `Play with key remaps.bat` | deprecated, keyboard and mouse only |
| The sticks | no | Steam's controller settings |
| Mouse look | works in the game | its own card; needs the script loader |
| Anything, without the script loader | keyboard and mouse only with `Play with key remaps.bat` | Get set up installs the loader |

Everything else now in that section (hooks, `SendInput`, PowerToys, the play-state file, `--dry-run`,
`--in-menus`, `--debug`, "a press finishes as it started", which keys are never held back, the mouse hook's
cost) moves to `docs/remapping.md` unchanged, with the "not checked yet" items in one list at its end, plus
what Apply puts in the game folder for remaps (`ue4ss\Mods\WCModsRemap`, `WCModsPlayState`, `WCModsMouseLook`)
and that taking all mods out removes them. `docs/guide/controls.md` follows the guide's own rules (the
docs-guide plan's six headings: What it changes in the game; A five-minute first try; What you can and can't
do; Did it reach the game?; Common mistakes; Undo), with no table and no command line: the shell's renderer
(`wcmods/guide.py`) has no table tags, so the README's table becomes a short list there, and the five-minute
first try is the one from the section above. The Controls row of the README's page table (108) loses
`WCModsRemap` and "UE4SS script" for "the game itself, through a small helper installed with your mods".
`docs/ARCHITECTURE.md` keeps its module names (it is for contributors) and gains a link to `docs/remapping.md`.
`docs/formats.md` 134-181 keeps the format but takes its examples and warning text from steps 3 and 5, and says
that build warnings show in the Apply drawer and that two mods' files merge with the higher priority winning
per key. `docs/verified.md` gains the step 5 and 9 checks once they have run. The `_help` of the examples'
`example-controls/controls.json` still sends creators to `python wcmods.py controls`; pointing it at the
Controls page is a follow-up in `wcmods-examples`.

**Tests.** None beyond the shell's help route test (`/help/controls` serves the file) and the docs-guide plan's
`tests/unit/test_guide.py` (no tables, no command line, links resolve), which this page must pass.

**Game check.** None.

## Not in this plan

- Moving the cat and the camera (WASD, the arrows) inside the game: known impossible today; they are axes read
  every frame and `PlayerInput`'s mappings aren't reflected (`docs/reverse-engineering.md` 1407-1418, 1474-1480).
  The RE gap that would change it is finding `WrcPlayerInput`'s mapping arrays in memory for a C++ mod.
- Left-handed layouts (IJKL, arrows only) as a preset: the same reason; at best a preset could write `"keys"`
  pairs for the deprecated launcher, which this plan does not add.
- Making the game's own Controls screen (`WBP_GuiPopupControlConfig`) rebind keys: not wired on PC and nothing
  on it is reflected; only its pictures can be changed, which is done.
- Verifying the controller button presets and controller buttons in general: needs a real controller with the
  game in front (the agent can't emulate a pad); the markers stay until someone runs that session.
- The old key remapper in the pause menu: the agent's keys bypass Windows' keyboard hook, so it needs a real
  keyboard session; the remapper is deprecated, and its edge-case tests (`tap` on the wheel, `_guard`,
  `read_state`) are left with it.
- Mouse buttons as menu keys inside the game: needs an RE probe (menus only get a mouse release, so a
  release-driven `OnListenCommand` send would have to be tried on the pause menu first).
- Toggle crouch and hold-to-run: needs design and an in-game check (re-sending pressed/released across frames
  and screens from `OnListenCommand`).
- Camera zoom on the wheel and field of view: needs RE of where the spring arm length is set each frame.
- Chords (Shift+E): needs design and a check; Shift+WASD is photo mode's camera.
- Which key pauses in each of the game's input layouts (P on the keyboard layout, Escape with the mouse, Enter
  in gamepad mode): an RE gap; this plan uses Escape, as the build does, and says so in open question 4.
- Mouse look extras (separate left/right and up/down speed, invert left/right, hold a button to look): a
  known-possible idea from the audit's codeless list, needing no new RE; left for a later plan.

## Open questions

1. Mouse look saves by itself into its own `mouse-look` mod while the rest of the page needs Save to mod. Keep
   that (recommended: it is what the in-game page saves into, and the card gets the label "saves by itself"),
   or route it through Save to mod into the chosen mod's `mouselook.json`?
2. Should the studio get a "Play with movement remaps" button that runs what the .bat runs, with its output in
   the drawer? Recommended no: the remapper is deprecated, and the per-row marker plus the drawer staying open
   (step 7) tell the creator what to double-click. If yes, it is a small addition to `onboarding.play` and
   `runTask`.
3. Once the In menus rows exist (step 5), does the free-form "key stands for key in menus" list stay on the page
   under For mod makers (recommended: it is where existing pairs without a row show) or become file-only?
4. The page will show Escape as the pause key. P pauses on the game's keyboard layout and Enter in its gamepad
   mode (`tests/game/test_cpp_sdk.py` 613-615). Accept Escape until the layout question is settled, or add
   "with a mouse" to the Pause row's chip?
5. Delete `controls.apply` and the pipeline's unreachable `"controls"` save op (recommended; `test_formats.py`'s
   `read_bindings` test stays), or mark them test-only?
6. Side mouse buttons and the wheel: keep offering them with "not tried in the game yet" (recommended) or hide
   them until step 5's check passes?
7. A controller button standing for a key in `"keys"` (file-only today): add a controller capture to Add another
   key, or leave it to the file? Recommended: leave it, until a controller session verifies pad remaps at all.
8. Reserved keys: refuse the mod menu's key and button, F11 and mouse look's key outright and only warn for the
   Emote wheel's keys and emote keys (recommended, since those mods can be off), or warn for all of them?
9. Keys other mods listen on: read the Emote wheel's `settings.json` by its id (recommended for now, it is the
   only such mod), or add a general `mod.json` field (`"keys": {"T": "opens the emote wheel"}`) that any mod can
   fill and the page reads?
10. `docs/guide/controls.md` and `docs/remapping.md` are in both this plan (step 10) and the docs-guide plan
    (its steps 5 and 10). Recommended: this plan's PR 5 writes the Controls content to the docs-guide plan's
    conventions, and the docs-guide plan links to it rather than writing its own; whichever lands first makes
    the files.

## What the review changed

- Bug 3's severity: one skeptic raised it to high, the other kept medium; bug 2 gained the capture's stick axes
  (313); bug 9 notes what the shell's `runTask` already does; bug 11 names the mod menu's current key rather
  than Insert, and the reverse direction from Settings.
- Step 1: no save in `/game/keys`; an unchanged stick is a no-op in `native_plan` (the no-op test would
  otherwise fail on four stick warnings); loaded entries are written back as they were instead of dropped
  (a later mod may rely on one to win); how files from the old buttons load.
- Step 2: `controls.css` is new and needs `"controls"` in the look branch's `PAGE_STYLES`; loaded stick
  entries get a Remove; formats.md's gamepad bullet is 163-164.
- Step 3: `describe` lives in `keymap.py` (`controls.py` would import `keymap`, which imports `controls`); bug 5
  is fixed once, in `keymap.plan`, so it warns with and without the loader and never twice; the missing code
  for the W:E warning added; `check_file` needs no change; the page's own `conflicts()` retires.
- Step 4: `keys_in_use` in `sections/controls.py`, served by `/controls/check`; the Emote wheel's pad button
  included; a fold, not another card.
- Step 5: second keys work only while you explore and only in the keyboard column; every pair or entry with no
  row is kept and shown under For mod makers; the fixture gets a `mod.json`, the test enters the forest and
  reinstalls normally at the end; side buttons and the wheel are tried by posting, as the middle button was.
- Step 6: the dialog's focus rules spelled out.
- Step 7: built on the shell's `runTask`; no-loader rows follow `describe`; the "in the game or not yet" line
  from `/changes` (the audit's high UX issue "No way to see whether the change reached the game").
- Step 9: each key listed once. Step 10: the second-key row says "while you explore", the menu key is named
  as configurable, ARCHITECTURE.md keeps module names, the guide and docs indexes list the new pages.

Second review (against the code at 3af2898, the shell, look and tests branches, and the docs-guide plan):

- Counts fixed: "Keyboard defaults" writes 15 keyboard entries (14 no-ops besides Pause), not 19 and 18; the
  no-op test fails today only on the four sticks, since Pause on Escape is already a no-op in the build; the 49
  passing tests are the three files' totals, not 49 remap tests.
- Tests follow the harness as it is: node:test units at `tests/studio/controls.test.mjs`, browser tests at
  `tests/studio/e2e/controls.test.mjs` (the harness can already start a studio, so they are written now, not
  later), API tests in `tests/unit/test_controls.py` everywhere (the PR list named `test_studio_api.py`). No
  browser test presses a real Play: the page's `fetch` is stubbed, since Play starts Steam.
- `studio/lib/keys.js` dropped: the harness's DOM shim already imports `wc.js` under node:test, and its
  `wc.test.mjs` already covers `keyFromEvent` and `keyLabel`; the F13 rule is a one-line change in `wc.js`.
  `studio/lib/controls.js` stays, as a model with no imports.
- `controls.css` and its `PAGE_STYLES` entry only once the look branch is in main (base `app.js` has neither).
- Backward compatibility: `native_plan` now warns for Pause leaving Escape and actions landing on Enter or
  BackSpace, so mods already shared with the old "Keyboard defaults" file say so at Apply; aliases come back as
  full names with the same meaning; Undo and "Back to the game's keys" write the game's key explicitly when a
  lower-priority mod sets the same action, so "back" stays true in the game.
- Keys in use: the mod menu's controller button (`menu_pad`, View by default) added; a mouse look merge error
  falls back to each mod's own key.
- The status line says nothing for a mod that is off and refreshes on `wc.installedEvent`.
- The Mouse look card stays short: tilt limits in a closed fold.
- Step 5: the agent's `mouse()` is documented in `docs/agent.md`; the game test reads one object at a time
  (no `FindAllOf`). Step 9: plain key names in the Overview, and the audit's missing `gameremap` tests.
- Step 10: one owner with the docs-guide plan for `docs/guide/controls.md` and `docs/remapping.md`; the guide
  page has no table (the shell's renderer has none) and follows the guide's six headings; `docs/SDK.md` lists
  `/game/keys` (step 1); the examples' `_help` is a follow-up in `wcmods-examples`.
- PR list made to match the steps: `wcmods/cli.py` and `docs/SDK.md` in PR 1; the agent's files,
  `docs/agent.md` and the fixture's `mod.json` in PR 3; `tests/game/test_menu.py`, `studio/lib/keys.js` and
  `keys.test.mjs` out; PR 3 waits for PR 2, not PR 4; PR 5 waits for PR 4 too, for the finished Mouse look card.
