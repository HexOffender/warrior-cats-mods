# Try Lua in the game

This page is for people who write scripts in Lua, the language the game's mods are scripted in. If you want
the game to look or play differently and you don't write code, you don't need it: the Make pages (Palettes,
Your cat, Controls, Names, Items, Animations, Characters, Questlines, Game data and Save) change the game
without any. The page is only in the side bar, under Advanced, once **Allow mods that run code** is ticked.

## What it changes in the game

It types one line of Lua into the game while the game runs, and shows what came back: what the line
printed, what it returned, or the error it hit. A line can read almost anything about the game (your cat,
the clock, the fresh-kill pile, quests, a fight) and change it, at once, in the running game.

Nothing you do here is saved into a mod. It gets there through a small helper the studio puts in the game
(the studio's connection to it), which goes in with every **Apply to game** or **Play** while mods that run
code are allowed.

## A five-minute first try

1. On the Settings and repair page, under **Options**, tick **Allow mods that run code**, and press
   **Allow mods that run code** again to say yes.
2. Press **Play** (top right). It puts the connection in the game first.
3. Play until your cat is in the forest.
4. Back in the studio, open **Try Lua in the game**. The line at the top says "The game is running and
   listening (in the forest)".
5. Under **Try one:**, press **Your cat**, then **Run**. Your cat's name, level, health and stats come back.
6. Press **Set 6:00**, then **Run**: it's morning in the game at once.
7. Under **Look inside an object**, leave Game.player() in the **Object** box and press **Inspect**: every
   property your cat holds, with its value, and every function it has.

## What you can and can't do

You can:

- read and change what scripts can, as [Scripting the game](../scripting.md#wcmodsgame) lists: your cat's
  health, stamina, level and stats, the time of day, the fresh-kill pile, quests and fights;
- keep a value for the next line: a global you set (x = 5) is there until the game closes;
- look inside any of the game's objects, and with **Show the engine's own members too**, the members every
  object of the engine has as well;
- go back through the lines you ran with Ctrl+Up and Ctrl+Down, and run a line with Ctrl+Enter.

You can't:

- save anything into a mod from here. A line that should run every time the game starts belongs in a mod's
  script: start from [Game Tweaks](https://github.com/HexOffender/wcmods-examples/tree/main/game-tweaks)
  and [Script mods](../scripting.md#script-mods);
- run a line while the game is loading, or held still behind another window: the line is taken back after
  15 seconds, and it won't run later on its own;
- run a line for ever: one that keeps going (a loop with no end) is stopped after a second or so;
- read every object of a wide kind at once (every actor, every widget): that has crashed the game, above
  all just after a level loads, so none of the examples does it;
- put items straight into your cat's inventory: the game has no way in for a script. A line can drop them
  on the ground by your cat instead, for it to pick up.

## Did it reach the game?

The line at the top of the page says whether the game can hear the studio:

- "The game is running and listening (in the forest)": Run and Inspect work.
- "The game is running but not answering": it's loading, or its window is behind another one and the
  game is held still. Bring the game to the front, or wait for the forest.
- "The game is running without the studio's connection to it": see the first mistake below.
- "The game is closed": press **Play**.

After **Run**, what came back shows under the box: what the line printed, then its values (nil is
nothing), then how long it took. An error shows in red, with the line it was on.

For a script in a mod, its card on the Mods page says whether it loaded when the game last started, and
under More, **What it said** shows its lines, newest first (**Open the log file** opens the whole log). In
the game, the mod menu's Log page (under Tools) shows them too, and a script that didn't start is named at
the top of the screen once your cat is in the world.

## Common mistakes

- The page says the game runs "without the studio's connection to it". Mods that run code were allowed
  after the game was started, or after the last Apply. Close the game, press **Apply to game**, then **Play**.
- Capitals. Lua tells capitals apart: Game.cat() works, game.cat() and Game.Cat() don't. The error
  line names what it couldn't find ("attempt to index a nil value (global 'game')").
- Nothing comes back from a line that does something. A line only shows a value it returns or prints:
  Game.cat():heal() heals your cat and shows nothing; return Game.cat():health() shows the health.
- A value looks wrong after a change. What a line sets is the game's own value, and the game sets
  some of them again itself (a level-up works out the stats, a new fight sets up its fighters). Change it
  again after that, or make the change in a script that keeps it.

## Undo

- Before you press **Run**, nothing has happened. **Clear what it said** empties the output.
- After **Run**, the line has done its work in the running game. What it changed lasts until the game
  sets it again, and the game saves its own values (your cat's level, stats and health, the fresh-kill
  pile) at its next save like any other. So before changing those, press **Back up now** on the Settings
  and repair page; to undo, put that backup back under **Backups and repair**.
- To be rid of the page, untick **Allow mods that run code**. The page leaves the side bar, and
  the next Apply takes the studio's connection out of the game.
