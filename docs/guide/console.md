# Try Lua in the game

This page is for people who write scripts in Lua, the language the game's mods are scripted in. If you
want the game to look or play differently and you don't write code, you don't need it: the Make pages
(Palettes, Your cat, Controls, Names, Items, Animations, Characters, Questlines, Game data, Save and
Tweaks) change the game without any, and [Tweaks](tweaks.md) keeps stamina full, heals on a key or holds
the clock with a tick. The page shows in the side bar, under Advanced, only once
[mods that run code](README.md#code-mods) are allowed.

## What it changes in the game

It types one line of Lua into the game while the game runs, and shows what came back: what the line
printed, what it returned, or the error it hit. A line can read almost anything about the game (your cat,
the clock, the fresh-kill pile, quests, a fight) and change it, at once, in the running game.

Nothing you do here is saved into a mod. The line gets to the game through a small helper the studio puts
in it (the studio's connection to the game). It goes in with every **Apply to game** or **Play** while mods
that run code are allowed, and it needs the [script loader](README.md#script-loader).

## A five-minute first try

1. On the [Settings and repair](settings.md) page, under **Options**, tick **Allow mods that run code**,
   and press **Allow mods that run code** again to say yes.
2. Close the game if it's open, then press **Play** (top right; it reads **Apply and play** while changes
   wait). It puts the connection in the game first, then starts it.
3. Play until your cat is in the forest.
4. Back in the studio, open **Try Lua in the game**. The line at the top says "The game is running and
   listening (in the forest)".
5. Under **Try one:**, press **Your cat**, then **Run**. Your cat's name, level, health, stats and traits
   come back.
6. Press **Set 6:00**, then **Run**: it's morning in the game at once.
7. Under **Look inside an object**, leave `Game.player()` in the **Object** box and press **Inspect**:
   the properties your cat's object holds, with their values, and its functions.

What this page asks the game has been tried against the running game: the "listening" line, a line run,
and your cat's properties and functions. Nobody has used the page itself with the game running yet.

## What you can and can't do

You can:

- read and change what scripts can, as [Scripting the game](../scripting.md#wcmodsgame) lists: your cat's
  health, stamina, level and stats, the time of day, the fresh-kill pile, quests and fights;
- keep a value for the next line: a global you set (`x = 5`) is there until the game closes;
- look inside any of the game's objects, and with **Show the engine's own members too**, see the members
  every object of the engine has as well;
- go back through the lines you ran with Ctrl+Up and Ctrl+Down, and run a line with Ctrl+Enter.

You can't:

- save anything into a mod from here. A line that should run every time the game starts belongs in a mod's
  script: start from [Game Tweaks](https://github.com/HexOffender/wcmods-examples/tree/main/game-tweaks)
  and [Script mods](../scripting.md#script-mods);
- run a line while the game is loading, or held still behind another window: the line is taken back after
  15 seconds, and it won't run later on its own;
- run a line for ever: one that keeps going (a loop with no end) is stopped after a second or so, with
  "this line ran too long and was stopped" (written for this, not yet seen in the game);
- read every object of a wide kind at once (every actor, every widget): that has crashed the game, above
  all just after a level loads, so none of the examples does it;
- put items straight into your cat's inventory: the game has no way in for a script. A line can drop them
  on the ground by your cat instead, for it to pick up.

## Did it reach the game?

The line at the top of the page says whether the game can hear the studio:

- "The game is running and listening (in the forest)": **Run** and **Inspect** work. It says "in the main
  menu" or "loading" when you're there.
- "The game is running but not answering: it may be loading, or held still behind another window". Bring
  the game to the front, or wait for the forest.
- "The game is running without the studio's connection to it: close the game, press Apply to game, then
  Play". See the mistakes below.
- "The game is closed: press Play".

After **Run**, what came back shows under the box: what the line printed, then its values, then how long
it took. An error shows in red, with the number of the line it was on.

For a script in a mod, its card on the Mods page says whether it loaded when the game last started, and
under **More**, **What it said** shows its lines, newest first (**Open the log file** opens the whole log).
In the game, the [mod menu](README.md#mod-menu)'s Log page (under Tools) shows them too.

## Common mistakes

- **Run** and **Inspect** stay grey. They work only while the line at the top says the game is listening.
- The page says the game runs "without the studio's connection to it". Mods that run code were allowed
  after the game was started or after the last apply, or the script loader isn't in (**Get set up**, on the
  Mods page, puts it in). Close the game, press **Apply to game**, then **Play**.
- Capitals. Lua tells capitals apart: `Game.cat()` works, `game.cat()` and `Game.Cat()` don't. The error
  names what it couldn't find ("attempt to index a nil value (global 'game')").
- Nothing comes back. A single expression shows its value, but a line of several statements shows only
  what it prints or returns: `local c = Game.cat(); c:heal()` heals your cat and shows nothing, and
  `local c = Game.cat(); c:heal(); return c:health()` shows the health too.
- A value looks wrong after a change. What a line sets is the game's own value, and the game sets some of
  them again itself (a level-up works out the stats, a new fight sets up its fighters). Change it again
  after that, or make the change in a script that keeps it.

## Undo

- Before you press **Run**, nothing has happened. **Clear what it said** empties the output.
- After **Run**, the line has done its work in the running game. What it changed lasts until the game sets
  it again, and the game saves its own values (your cat's level, stats and health, the fresh-kill pile) at
  its next save like any other. So before changing those, press **Back up now** on the Settings and repair
  page. To undo, close the game and press **Restore** beside that copy, under **Save backups** (press it
  twice).
- To be rid of the page, untick **Allow mods that run code**. The page leaves the side bar, and the next
  apply takes the studio's connection out of the game, with every other mod that runs code
  ([Menu pages](README.md#menu-pages) and [Sandbox mode](README.md#sandbox-mode) among them).
