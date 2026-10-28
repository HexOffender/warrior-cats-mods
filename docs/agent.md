# The agent controller

`python wcmods.py agent ...` drives the running game so a change can be tried in it rather than only
built. It can:

- start the game and play into the forest;
- run Lua and read and use the mod menu;
- press keys, walk, travel, and take pictures of the window;
- read UE4SS's log and spot crashes;
- run a suite of in-game tests that leaves a report with pictures.

It's made for an AI agent working on this repository (Claude Code runs these commands) as much as for
people. Every command prints plain text, and the ones that return data take `--json`. The same is a
Python API, `wcmods.agent.Agent`.

Everything on this page was tried in game on build 24847281 and rechecked on 26184573, patch 1.1 ([reverse-engineering.md, Game updates](reverse-engineering.md#game-updates)), unless it says otherwise.

## What it needs

- **The game:** Windows, the game from Steam, and UE4SS (as for any code mod).
- **A test install:** `agent install` builds your enabled mods with code mods allowed for that one
  build, so the bridge ([scripting.md, The game bridge](scripting.md#the-game-bridge)) goes in.
  - **Code runs:** that means the code of every mod that's on runs too (its `section.py` as it
    builds, its scripts in the game), mods you've downloaded included, even with "allow_code_mods"
    off in `wcmods.json`. Turn off any mod you don't trust first, or use `--no-code-mods` (no bridge).
  - **`wcmods.json`:** your settings in it stay as they are ("allow_code_mods" included). Like any
    install, it updates the record of what's installed (`installed`, `installed_ue4ss`,
    `installed_ue4ss_shared`), which the studio's Apply button compares against.
  - **More mods:** `--with <mod folder>` adds a mod that isn't in `mods/`, switched on for the build
    and used even if its `mod.json` names another version of the game (the tests' own mods name none),
    e.g. `--with ../wcmods-examples/game-tweaks` (from a checkout of wcmods-examples beside wcmods).
- **Afterwards:** `agent install --normal` installs as `wcmods.json` says, like `wcmods install`.
  Until then, with "allow_code_mods" off, the studio says the game has code from a test install, and
  its Apply to game and Play take it out (`wcmods play` warns about it).
  If tests changed your save, `wcmods restore <backup>` puts it back; the test runner backs it up
  first and prints the name.

## A session

```bash
python wcmods.py agent install --with ../wcmods-examples/game-tweaks
```

```bash
python wcmods.py agent launch --world
```

```bash
python wcmods.py agent menu read Stats
```

```bash
python wcmods.py agent menu set Health 150
```

```bash
python wcmods.py agent shot stats --menu
```

```bash
python wcmods.py agent test
```

```bash
python wcmods.py agent quit
```

`launch --world` starts the game through Steam, waits for the bridge, then plays into the forest
(the splash, the main menu's Prophecy button, then save slot 1). It took 36 s from a closed game. `menu read` prints the page as
rows (below), `shot` prints the PNG's path, and `test` writes `agent-output/runs/<time>/report.md`
and `report.html`.

## Commands

| Command | What it does |
|---|---|
| `status [--json]` | Whether the game is running, its window (size, in front, minimised), the bridge, the level, your cat, the mod menu's page, a crash reporter |
| `launch [--world] [--cat N]` | Start the game through Steam and wait for the bridge; `--world` plays into the forest with save slot N |
| `enter [--cat N]` | From the splash or main menu, play into the forest (tried with slot 1) |
| `quit [--force]` | Close the game the way its menu does (`QuitGame`); `--force` ends it if it won't close |
| `install [--with DIR]... [--no-code-mods] [--normal] [--force]` | A test build (above); `--normal` is `wcmods install` |
| `lua CODE` / `lua -f FILE` | Run Lua in the game; prints what it printed and returned (JSON) |
| `check FILE...` | Compile Lua files with the game's own Lua 5.4, without running them (there's no Lua on the machine otherwise) |
| `wait EXPR [--timeout S]` | Wait until a Lua expression is truthy: `agent wait "Game.cat() ~= nil"` |
| `cat [--teleport X,Y,Z]` | Your cat: name, level, clan, health, stamina, xp, where it is |
| `move [--forward F] [--right R] [--seconds S] [--turn DEG]` | Walk relative to the camera; prints how far it went |
| `key KEY... [--hold S] [--repeat N]` | Press keys for the game's own controls; several are held together (`key W LeftShift --hold 2` runs) |
| `hotkey KEY [--mod KEY]... [--focus]` | Press a key the way UE4SS's key binds see it (Insert, a script's `Game.onKey`) |
| `shot [NAME] [--menu] [--scale F] [--region x,y,w,h] [--out PATH]` | A PNG of the game's window, or just the mod menu |
| `screens [--press SCREEN BUTTON]` | The game's own screens that show; click a button on one |
| `menu pages` | The mod menu's pages, by group |
| `menu open [PAGE]`, `menu close` | Open the menu (on a page, by title or id), close it |
| `menu read [PAGE] [--json]` | The page's rows |
| `menu press LABEL`, `menu set LABEL VALUE`, `menu section TITLE [close]` | Use a control |
| `menu scroll top\|end\|N\|LABEL`, `menu shot [PAGE [NAME]]` | Scroll the page; a picture of the menu |
| `log [--errors] [--grep TEXT] [--lines N]` | The end of UE4SS.log, or only the lines saying a script went wrong |
| `crash [--close]` | Whether the crash reporter is open; `--close` closes it. Nothing is ever sent |
| `test [PATHS] [-k TEXT] [--launch] [--stop] [--list] [--no-backup]` | Run the in-game tests (below) |
| `run SCRIPT.py [ARGS]` | Run a Python script with `agent` ready in it |

A command that can't do what it's asked prints `error: ...` and exits with 1. For example, a menu
control that isn't on the page gives an error that lists the controls the page has.

## The mod menu

The menu's pages are drawn by their scripts every frame ([SDK.md, `WCModsMenu`](SDK.md#wcmodsmenu)). The pages
about the game (Stats below, World, Travel, Quests, Cheats ...) are the Menu pages mod's: for a test
install with them, `agent install --with ../wcmods-menu-pages/menu-pages` (a checkout of
[wcmods-menu-pages](https://github.com/HexOffender/wcmods-menu-pages) beside wcmods), or have it in your
mods. Each row tells the menu module what it shows. The agent reads those rows rather than pixels, and uses a control by
handing the page its new value. The page then runs exactly as if the player had clicked:

```
== Stats ==
# Your cat
Name: Callie
Health: 233   (0..233)   <slider>
Stamina back per second: 20   (0..500)   <number>
[-] Level and experience
Level: 20   (1..20)   <number>
[ Heal ]
```

- **Row kinds:** `heading`, `text`, `note`, `field`, `button`, `switch`, `toggle`, `slider`,
  `number`, `input`, `choice`, `radio`, `color`, `progress` and `section`. `[-]` is an open section
  and `[+]` a closed one. Rows inside a closed section aren't drawn, so they aren't there to read
  until you open it.
- **Focus:** `<- focus` marks the control that has the keyboard's (and a controller's) focus, and
  `(focus: ...)` under the rows says when it's in the top bar or on a tab instead. `key Tab`,
  `key Down` and `key Enter` then drive the menu the way a keyboard does (`key` can't hold Shift
  for Shift+Tab).
- **Labels:** a control is named by its label, in any case. Where two rows share a label (Stats has a
  Stamina slider and a Stamina stat), the first is used. Name the other by its place on the page,
  `@n`, which `menu read --json` gives as `n`.
- **Values:** a switch or toggle takes `on`/`off` (nothing toggles it), a slider or number box takes
  a number, a radio or drop-down list takes one of its options, a text box takes the text, a colour
  takes `#rrggbb`, and a section takes `open` or `close`. A button is pressed.
- **Pages:** `menu open` takes a page's title or id. A script's settings page has the id
  `script:<mod id>`, e.g. `script:game-tweaks`.

How it works: every Lua state that draws a page has its own copy of `WCModsMenu`, so requests go
through UE4SS's shared variables, which they all see:

- **Reading:** `WCModsMenu.agent.read` (a token) asks for the rows, answered as JSON in
  `WCModsMenu.agent.page`.
- **Using a control:** `WCModsMenu.agent.act` (`token\tlabel\tvalue`) asks to use one, answered in
  `WCModsMenu.agent.done`.
- **Scrolling:** `WCModsMenu.agent.scroll` scrolls the page.

The script whose page is showing answers on its next frame and clears the request, so no other page
acts on it. `--menu` pictures are cropped to the window. It's drawn centred, at the size of its scale
box times the UI's scale; UE4SS hands back the engine's cached widget geometry as zeros, so that
can't be asked.

## Keys, walking and the game's screens

- **The game's own controls:** `key` posts key presses to the game's window (`WM_KEYDOWN` and
  `WM_KEYUP`): W, A, S, D walk, SpaceBar pounces, E interacts, Escape pauses, I opens the inventory, T
  opens the map, BackSpace is Back. A posted P only sometimes pauses (P sends `Button_Start`, which pauses
  only in its gamepad mode; `Player_Pause` is on Escape, whatever the save says), so use Escape. The pause screen's Main Menu asks first: press
  `WBP_GuiPopupCommonYesNo_C`'s `mcGuiButtonYes` (seen in game, build 26184573). It doesn't move the
  mouse or change which window is in front. This was tried with the game in front; behind other
  windows the game may throttle itself, and that hasn't been checked.
- **UE4SS's key binds:** binds such as the mod menu's Insert and a script's `Game.onKey` read the
  real keyboard, so posted keys don't reach them. `hotkey` presses keys for real (`SendInput`),
  which only lands in the game when it's in front. It refuses otherwise, and `--focus` brings the
  game to the front first (Windows may refuse; `--focus` hasn't been tried yet).
- **Walking without keys:** `move` walks the cat with movement input from Lua each frame, relative
  to the camera, whatever window is in front. `turn` (Python) and `move --turn` turn the camera.
  `cat --teleport` moves the cat at once.
- **The game's own screens:** `screens` lists the screens that show (the splash, main menu and cat
  choice are what `enter` uses). `screens --press SCREEN BUTTON` clicks a button on one by its
  property name, the way a click does.
- **No mouse:** the menu is driven through its rows and the game's screens through their buttons,
  so the agent never needs the mouse.

## Pictures

`shot` uses `PrintWindow`, so other windows covering the game don't matter. A minimised game can't
be captured, and the agent says so. Pictures go to `agent-output/shots/` numbered in order (`--out`
picks the path), or to the run's `shots/` during tests. `--scale 0.5` halves them, which is plenty
for looking at a page and a quarter of the size.

From Python, `agent.picture()` gives an `Image` without saving it:

- **Changing it:** `crop(x, y, w, h)`, `scaled(f)` and `save(path)`.
- **Looking at it:** `pixel(x, y)`, `mean()`, `blank()` (true for a capture of a window that isn't
  drawn) and `diff(other)` (0 for the same picture to 1).
- **Files:** `Image.load(path)` reads an 8-bit RGB or RGBA PNG. That's enough to check something
  changed on screen, or that a colour is where a mod puts it.

## The log and crashes

- **The log:** `log` reads `ue4ss/UE4SS.log` and `log --errors` keeps the lines that say a script
  went wrong. From Python, `agent.log_mark()` then `agent.errors_since(mark)` gives the ones written
  in between, which is how a test sees its own.
- **Crashes:** `status` and `crash` say whether Unreal's crash reporter is open, and `crash --close`
  closes it. Nothing is ever sent.

## Python

```python
from wcmods.agent import Agent

agent = Agent(r"D:\projects\warrior-cats-mods")
agent.launch(world=True)
page = agent.menu.open("World")
agent.menu.press("Noon")
agent.menu.set("Hold this time", True)
assert agent.menu.read().get("Hold this time") is True
print(agent.lua("return Game.time.get()"))     # [12, 0, 4]
agent.shot("noon", menu=True)
```

| | |
|---|---|
| `status()`, `crashed()`, `close_crash_reporter()` | As the commands |
| `launch(world, cat)`, `enter(cat)`, `quit(force)`, `restart(world)` | Starting and stopping |
| `install(extra, code_mods, force)`, `install_normal()` | Installing; the game must be closed |
| `backup_save(reason)`, `restore_save(name)` | Your save, by backup name |
| `lua(code)` | One value back, a list for several, None for none; `LuaError` with the game's traceback; `BridgeDown` when it doesn't answer |
| `compile(source, name)` | None, or the compile error |
| `wait(fn, timeout, what)`, `wait_lua(expr, timeout)` | Wait for something to be true (a bridge that's loading is tried again) |
| `cat()`, `location()`, `teleport(x, y, z)`, `move(forward, right, seconds)`, `turn(degrees)` | Your cat |
| `pause(on)`, `speed(factor)` | Pause the game; run it faster or slower (time dilation) |
| `key(name, hold)`, `keys(*names, hold)`, `hotkey(name, modifiers, focus)` | Keys |
| `screens()`, `press_ui(screen, button)` | The game's own screens |
| `picture(menu, region)`, `shot(name, scale, menu, region, path)` | Pictures |
| `log_mark()`, `log_since(mark)`, `errors_since(mark)` | The log |
| `menu.pages()`, `menu.open(page)`, `menu.close()`, `menu.is_open()`, `menu.current()` | The mod menu |
| `menu.read()` | A `Page`: `rows`, `find(label, kind)`, `get(label)`, `has(text)`, `errors()`, `controls()`, `text()` |
| `menu.press(label)`, `menu.set(label, value)`, `menu.section(title, open)`, `menu.act(label, value)` | Use a control; returns the row's (kind, label) |
| `menu.scroll(to)`, `menu.region()`, `menu.shot(name)` | Scroll, where the window is, a picture of it |

`agent run script.py` runs a script with `agent` already made, for a quick check that's more than one
command.

## In-game tests

`tests/game/test_*.py` hold tests that run in the game: `agent test` runs them all, `agent test -k
travel` the ones with "travel" in their name, `agent test --list` lists them, and `--launch` starts
the game (and plays into the forest) when a test needs it. Each function `test_*(agent)` is a test,
in the file's order:

```python
"""What these tests are for."""
from wcmods.agent import skip

NEEDS = "world"          # "world" (the default): your cat in the forest; "game": the game and
                         # the bridge, anywhere; "nothing": not even the game
LOG_ERRORS_OK = False    # True: script errors in the log don't fail a test


def setup(agent):        # before each test in the file (optional)
    agent.menu.close()


def teardown(agent):     # after each, even one that failed (optional)
    agent.menu.close()


def test_noon(agent):
    """The docstring goes in the report."""
    agent.menu.open("World")
    agent.menu.press("Noon")
    assert agent.lua("local h = Game.time.get() return h") == 12
```

- **Results:** an `AssertionError` fails a test, any other exception is an error, and
  `skip("why")` skips it.
- **The log:** a script error written to UE4SS.log while a test runs fails it as well, which is how
  the suite found a bug in the Inspector page the first time it ran.
- **Failures:** a failing test gets a picture of the game.
- **Crashes:** a crash, or the game closing, ends the run.
- **The report:** every run writes `agent-output/runs/<time>/` with `report.md` (for reading in a
  terminal or by an agent), `report.html` (with the pictures) and `report.json`.
- **Your save:** the runner backs up your save first, because tests change your cat and the world
  and the game saves as it goes. It prints the backup's name for `wcmods restore` (`--no-backup`
  skips this).
- **Clean up:** tests should put back what they change, as the ones here do: health, the clock,
  where your cat stands, a saved travel spot.

The suite here has 80 tests:

- **The bridge, Lua and pictures:** `test_bridge.py`.
- **Your cat and moving it:** `test_cat.py`.
- **The clock and the fresh-kill pile:** `test_world.py`.
- **The C++ SDK:** `test_cpp_sdk.py`. A C++ mod (`tests/cpp-sdk`) calls everything docs/SDK.md
  documents and records what it got; the tests compare that with Lua and have it make changes Lua
  confirms. It needs the mod built and installed first (`cpp build tests/cpp-sdk`, then `agent install
  --with tests/cpp-sdk`); the tests say so and skip otherwise.
- **The game's own animations:** `test_animations.py`. A test mod (`tests/animations-mod`) plays the
  game's Yawn as an emote on F7, a claws-out copy of its Stretch on F8, and the sleep loop in the trot's
  place, all without a file; the tests press the keys and read the anim instance, and measure the head
  while the cat trots. It needs the mod installed first (`agent install --with tests/animations-mod`);
  the tests say so and skip otherwise. All three passed in the game on 2026-10-28.
- **The mod menu:** `test_menu.py`. Every page draws without an error (with a picture of each), the
  Stats page matches your cat, the Health slider and Heal work, "Hold this time" holds the clock,
  and a Travel spot can be saved and forgotten. It also checks a jump and Back, the Items, Quests,
  Log, Lua (advanced) and Inspector pages, a script's settings page, and that Insert opens and closes the
  menu.
- **Scripts and the runtime:** `test_scripts.py`. A script's errors carry its mod's name and are said once,
  a misspelt key doesn't stop it, another cat's level isn't yours, a task can cancel itself and add another,
  a script that doesn't start is named, a script's settings page saves and says so (with a setting's help
  under its row), and a page made from a timer is the only one. Most need three throwaway mods in the test
  install (`agent install --with tests/game/mods/noisy-script --with tests/game/mods/broken-script --with
  tests/game/mods/late-page`) and skip without them.
- **The studio's Try Lua in the game:** `test_studio_console.py`, its routes against the running game.
- **Tweaks:** `test_tweaks.py`. Stamina kept full, the clock held, the fresh-kill pile kept up, the heal key, and
  the mod menu's Tweaks page and its Save, with a throwaway mod in the test install (`agent install --with
  tests/game/mods/all-tweaks`); they skip without it. Skipping the story's scenes waits for a check by hand, which
  the file's top says how to run (with `tests/game/mods/skip-scenes`).

## What it changes, and what it won't do

- **What it changes:** the game as it runs (and so, at the game's next save, your save). Back up
  first: the runner does, and `wcmods backup` does by hand.
- **What it leaves alone:** your settings in `wcmods.json` (an install only updates its record of
  what's installed) and your mods' files, unless a test presses a page's Save. It never sends crash
  reports.
- **Closing the game:** it ends the game only with `quit --force`, after the normal quit didn't work.
- **Keys:** `hotkey`, the one command that presses real keys, does nothing unless the game is in
  front (or `--focus` puts it there).
- **Limits:**
  - Fights can be watched and changed through `Game.fight` (docs/scripting.md), but the agent can't
    play one: the combat screen doesn't take the game's commands from Lua.
  - Driving the game's own menus beyond the splash, main menu and cat choice means finding their
    screen and button names (`screens`, then `inspect`).
