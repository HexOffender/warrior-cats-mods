# Remapping keys: how it works

How wcmods changes the game's keys, for mod makers and for anyone working on wcmods. Creators start from the
Controls page in Clan Mod Studio and its guide ([guide/controls.md](guide/controls.md)); the README's
[Remapping keys](../README.md#remapping-keys) has the short version, and [formats.md](formats.md#controlsjson)
the file.

## Why remaps happen while the game runs

The game doesn't take remaps from mods. It keeps a copy of your bindings in the save
(`Shared/InputKeyboard`, `Shared/InputGamepad`) but ignores edits to it, its own rebinding
screen (`WBP_GuiPopupControlConfig`) is hidden and not wired up on PC, and the bindings themselves
live in native code no script can reach ([reverse-engineering.md, Input](reverse-engineering.md#input)
has what was found). The save's copy also puts Pause on Enter, while the game pauses on Escape (Enter
confirms); `python wcmods.py controls` lists that copy and says so. So wcmods remaps while the game runs,
from its own table of the game's keys (`wcmods/keymap.py`, served to the studio as `GET /game/keys`). Set
your keys on the Controls page (or in `controls.json`), save them to a mod, and install mods (game closed).
Then:

| What you remap | Done by |
|---|---|
| The game's actions that are buttons: Interact, Pounce, Run, Crouch, Scent tracking, Drop, Talk to friend, Place den decoration, Return to camp, Reset camera, Pause, and the Controls screen's Inventory (I), Quest (K), Map (M) and Meow (L), onto keyboard keys, mouse buttons or controller buttons | **the game**, through wcmods' `WCModsRemap` script: start the game any way you like, from Steam too |
| Any other of the game's commands, everywhere: the menus' Confirm, Back, Skip, tab buttons and the rest (`"keyboard": {"Button_Skip": "G"}`) | **the game** |
| A key that stands for another while you play (`"keys": {"H": "E"}`) | **the game** |
| A key that stands for another in menus, the "In menus" list (`"menus"`): I and K for Up and Down, F for Enter | **the game** (mouse buttons there: the old key remapper) |
| Movement and the camera (Move back, Move left, Camera down, Camera left, and keys standing for W, D, Up or Right) | only **the old key remapper** outside the game (deprecated, below) |
| The controller's sticks | **Steam Input** (in Steam, right-click the game, then Properties, Controller) |
| Anything, without UE4SS | **the old key remapper**, for keyboard and mouse |

What the build will do with a `controls.json` is said before Apply, in the same words: `keymap.describe`
runs the plans below on the mods' merged files and gives a sentence per entry, which the Controls page shows
on its rows (through `POST /controls/check`) and the build gives as its warnings in the Apply drawer.

## Inside the game

The `WCModsRemap` script is installed with your mods whenever they remap anything it
can do, with "Allow mods that run code" on or off (it's wcmods' own script, like mouse look's). Every key
the game hears becomes one or more of its commands (Interact, Pounce, and in menus Up, Confirm, Back...),
and the script works on those:
- **Moving an action or command** (`keyboard`, `gamepad`): the new key does it, in play and in the game's
  menus, and the old key stops doing it but keeps its other jobs. With Interact on F, E still shows info on
  the map; with Pounce moved off Space, Space still confirms dialogue. A key that takes an action stops doing
  its own (with Interact on Q, Q no longer tracks scents; the build says so).
- **A key standing for another** while you play (`keys`) or in menus (`menus`): it does all of that key's
  jobs there, and none of its own. Menus are every screen but the HUD: the title and cat maker, the
  pause menu and its pages, the inventory, the map, photo mode, a fight's menu, and talking to a cat.
  Letters still type on the name screen, and do the other key's job there too (the build says so).
  A few screens read some keys directly, like movement: the map's zoom and move (arrows, WASD), photo
  mode's camera (Shift+WASD, Z/C) and turning the cat in the cat maker (Q/E). A menu pair standing for
  an arrow key or WASD therefore also goes to the old key remapper, which can do those (the build says so).

The game's pictures of keys follow too: prompts such as Travel and Talk, the menus' footers (Back,
Confirm) and the pause screen's Controls tab show the new key, from the game's own pictures. A command
that didn't move keeps the game's picture (with Escape standing for Backspace in menus, the footers' Back
shows Escape while Confirm keeps Enter).
The keyboard's pictures follow keyboard moves and a controller's follow controller moves. A key the game
has no picture for (the middle mouse button, the wheel) leaves the game's picture as it was. Movement and
the camera, which only the old key remapper can move, keep theirs. Seen working in game: Interact on F, Run on G,
Scent tracking on the middle mouse button, Map on N (in the map screen too), H as a second Interact, the
pause menu moved with I and K and confirmed with U, O closing menus, the next tab on PageDown instead of
2, and a fight's menu and moves picked with I, K and U; the old keys did nothing. The Travel and Talk
prompts and the Controls tab showed F for Interact, and the pause screen's Back showed Escape for a
menu pair. Scripts that listen for Interact themselves (`Game.npcs`, for a mod's own cats) follow it to its
new key. The mod menu's Overview lists each key with a new job beside Insert and F6 ("F: Interact (was E)",
"H: Interact, like E", "U: Confirm and Skip in menus"): the script hands `keymap.native_plan`'s `menu_keys`
to `Menu.key` when the menu is installed.

Keys wcmods' own scripts listen on (`RegisterKeyBind`) do their job whatever the game does: the mod menu's
key and controller button, mouse look's key, and the keys mods declare (an emote's key in `animations.json`,
the Emote wheel's `settings.json`). The build and the Controls page warn when a remap lands on one of them
(`sections/controls.keys_in_use`); the page refuses wcmods' own and F11.

## The old key remapper outside the game (deprecated)

Remapping is done inside the game now, and the
old key remapper is kept only for what a script can't reach: what the game reads as axes every frame
(movement and the camera, the map's zoom and move) and mouse buttons in the "In menus" list (in menus, a
click goes to the button under the cursor, not to the game's keys). The studio's Play doesn't start it
any more; when your mods have remaps only it can do, the build and Play say so. While you play, the keys in your mods' `controls.json` stand in for the game's. "Play"
means the game window is in front and you're exploring, not in a menu. A small UE4SS script
(`WCModsPlayState`, installed with your mods when the remapper has work to do) tells the remapper
which it is. Windows can't, because the game draws its own cursor. Without that script, remaps
apply whenever the game is in front. The remapper holds back the key you press and sends the
game's key in its place, and it stops when the game closes. Menus, the name screen and other
programs keep your normal keys, except for the menu remaps you set (the Controls page's "In menus"
list). A key whose action moved stops doing it, unless another action still uses it. Mouse buttons
and the wheel can stand in for keys.

To use it, start the game with `Play with key remaps.bat` or `python wcmods.py play` instead of from
Steam or the studio's Play. Its "play" means no game screen is showing: exploring, photo mode, or
talking to a cat. When everything you remap is done inside the game, `play` just starts the game:

```
python wcmods.py play              # start the game through Steam and remap until it closes
python wcmods.py remap             # the same, when the game is already running (or about to be)
python wcmods.py play --dry-run    # report which remaps would happen, without changing any keys
python wcmods.py play --in-menus   # remap in menus too
python wcmods.py play --debug      # log the window in front, the play state, and remapped key presses
```

Microsoft PowerToys Keyboard Manager can stand in for the key remapper, if you'd rather not run it:
choose *Remap a key*, map your new key to the game's key (for example T to W for forward), and set
the target app to `Wrc-Win64-ShippingDRM.exe` so the remap only applies in the game. Don't remap the
same keys with it and wcmods at once.

The key remapper runs as a normal program using Windows' low-level keyboard hook. Ctrl+C stops it,
and anything it was holding down is let go. Details:

- **A press finishes as it started.** A key you were already holding when you went from a menu into
  play keeps going to the game unchanged until you let go, so nothing gets stuck. A remapped key
  stops repeating when a menu opens.
- **Some keys keep their old job.** Enter, Space, Escape, Backspace and Tab are never held back when
  their action moves, because prompts and dialogue shown while you play may need them; the build
  and `play` say so.
- **Other programs' keys pass through.** Keys sent by other programs (Steam Input's keyboard buttons,
  macro tools) aren't remapped or held back. A controller button that Steam Input turns into W still
  walks forward.
- **Mouse remaps cost a little.** Remapping a mouse button or the wheel adds a mouse hook, which
  Windows calls for every mouse movement. Remap keyboard keys only if you notice any lag.

## What Apply puts in the game folder

All of it under UE4SS's mods folder (`Wrc\Binaries\Win64\ue4ss\Mods`), each only when there's work for it:
`WCModsRemap` (the in-game remaps, written from `controls.json`), `WCModsPlayState` (tells the old key
remapper whether you're in a menu) and `WCModsMouseLook` (mouse look, from `mouselook.json`). Take all mods
out of the game, on Settings and repair, removes them with the rest.

## Not checked in the game yet

- Controller buttons, and the controller button presets (no real controller has been tried).
- The side mouse buttons (Mouse 4, Mouse 5) and the wheel, inside the game.
- A remapped key held while a screen opens; den decorating, the name screen, cutscenes and minigames.
- The old key remapper in the pause menu, and with the new play state (the agent's keys don't pass through
  Windows' keyboard hook).
