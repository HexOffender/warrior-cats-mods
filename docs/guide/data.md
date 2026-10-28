# Game data

The Game data page changes the numbers the game plays by: how fast your cat runs, how much a fight is
worth, what prey is worth to the fresh-kill pile, how big the Clan cats are and how scarred. Your changes
go in a mod, as `data.json`. The game's own files are never changed.

## What it changes in the game

The game keeps its numbers in tables: one row for each thing, one column for each number about it.
**XP from fights** has a row for each animal and the experience it gives. **Tuning** has hundreds of
single numbers, from running speed to how often a cat has two different eyes. The page changes cells in
those tables.

How it gets there: when you apply, the studio puts the changed tables in the game's folder, in a file of
its own, and the game reads them in place of its own.

The page has three parts, from the top:

- **Find a number**: a search across every table. Type what the number does (run, xp, mouse, scars, build
  time) and pick it from the list.
- **Quick changes**: the changes people ask for most, in groups (Moving, Levelling, Food, Dens, Clan cats,
  Day and night). Each has a slider, a box for the number, the game's own value and a **Normal** button
  that puts it back.
- **All tables**: every table, cell by cell, for anything Quick changes doesn't have. At its top,
  **Your changes** lists every change in the mod in words. Under a row's name is what the mechanics notes
  say about it, where they say anything; most rows show only their name.

Every quick change is an ordinary change to a cell: it shows in All tables too, and in the file under
**For mod makers**.

## A five-minute first try

1. Open **Game data**. Under **Quick changes**, the Moving group is open, and **Running speed** says
   "Normal: 390".
2. Drag its slider to 600, or type 600 in its box. The row says "390 -> 600", and the Editing mod bar
   says "Unsaved changes".
3. Press **Save to mod**. It goes in **My mods**, unless you picked another mod in the bar.
4. Press **Apply and play** at the top right (it says **Play** when there's nothing new to apply). It puts
   your mod in the game, then starts it.
5. [The log](README.md#build-log), at the bottom right, lists "Tuning: Running speed 390 -> 600 (My
   mods)". It closes by itself a few seconds later, unless there's a warning; **Last apply**, at the
   top, opens it again.
6. In the forest, run.

Nobody has watched a change from this page in play yet, so look closely: you may be the first. The log
shows the number went in either way.

## What you can and can't do

You can:

- change any number in the tables the page lists: speeds, stamina, levels, prey, den build times, fights,
  the Clan cats' sizes and scars, herbs;
- multiply a whole column with **Multiply**, above a table (every animal's XP times 2, say), and keep one
  row out of it by typing that row's own value back in;
- tick a TRUE/FALSE column, and pick a word from a list where a column has only a few;
- find a number by what it does, and open its table on that row.

You can't, here:

- multiply a column of **Tuning**: its one value column holds hundreds of numbers that have nothing to do
  with each other, so change them one at a time;
- add or remove rows: the page changes the rows the game has. A file written by hand can add and remove
  rows, and the page keeps those as they are;
- change your own cat's level or what it carries: that's your save, on the [Save](save.md) page;
- change the map's own data: the page leaves those tables out;
- change the cats you already have through **Cat sizes** or **Scars**. The game chooses a cat's size,
  scars and eyes when it makes the cat, so cats already in your save keep theirs. A new game, or new kits,
  show the change.

Some tables carry a word beside their name. **Online** tables feed the online den visits, and the server
may ignore changes there. **Traits** tables change which traits new cats get. **Story** tables are quests
and talk: a wrong value there can stop a quest.

## Did it reach the game?

- The game gets a change only when it's saved (**Save to mod**) and applied (**Apply to game**, or
  **Play**, which applies first).
- After an apply, the log lists the numbers your mods changed under "The game's numbers it changes:",
  one a line, up to twenty (**Last apply** shows it again). A warning there names a change that didn't go
  in, and its mod.
- If the page is open when you apply, each change is marked "in the game since" the time of that apply,
  and one made since says "not in the game yet".
- In play, nothing from this page has been checked yet. The tables go in the same way as the game's text,
  which does change in the game, but no change to these numbers has been watched in play. Quick changes
  says so at its top. The rows that say "Read by the game's code" are ones the game is known to
  ask for; for most other rows, nobody knows yet whether the game uses them.

## Common mistakes

- A comma in a number. The page says "Use a number like 1.5" and keeps the box open. Use a point: 1.5,
  not 1,5.
- A chance over 1. Columns whose names end in Chance (the scars), the numbers in **How foes choose** and
  how likely a fight move is to hit go from 0 (never) to 1 (always), and the page won't let one go over 1.
  Other columns whose numbers are all from 0 to 1 (the cat sizes) can go past 1: the page lets it in and
  says so, in case it was a slip.
- Two mods changing the same number. Multipliers stack: two mods that both double XP make it four times,
  and nothing is said. A number set outright by the mod with the higher **Priority** (under its **More**
  on the Mods page) wins, and the log says so.
- A quick change over a number set by hand. A file written by hand may have set the row another way, say
  XP from fights set to 30 instead of multiplied. The row says "This row is set by hand to 30, in
  data.json", and moving its slider asks first: **Replace it** or **Keep it**.
- A table the game doesn't have. A file written by hand, or made for an older
  [version of the game](README.md#game-build), can name one. The page shows it under the list of tables
  with a **Remove**, and the rest of the file still goes in.
- "The game's tables can't be read". The studio hasn't found the game. **Get set up**, on the Mods page,
  finds it.

## Undo

- Before saving, one change: its **Normal** button, in Quick changes or in **Your changes**, or type the
  game's value back into the cell.
- Before saving, a whole table: **Put this table back**, above the table in All tables. Press it twice.
- Before saving, everything: pick another mod in the bar and choose **Switch without saving**.
- After saving: the same buttons, then **Save to mod** again.
- After an apply: switch the mod off on the Mods page and apply again. The game goes back to its own
  numbers, and nothing of this page is in your save. Clan cats the game made while the mod was on keep
  the size and scars they got.

[How Clan Mod Studio works](studio.md) has the Editing mod bar, Save to mod and Apply. The file's own
rules are in [the file formats](../formats.md#datajson).
