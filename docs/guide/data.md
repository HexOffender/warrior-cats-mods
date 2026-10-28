# Game data

The Game data page changes the numbers the game plays by: how fast your cat runs, how much a fight is
worth, what prey is worth to the fresh-kill pile, how big the Clan cats are and how scarred. Your changes
go in a mod, as `data.json`; the game's own files are never changed.

## What it changes in the game

The game keeps its numbers in tables: one row for each thing, one column for each number about it.
**XP from fights** has a row for each animal and its experience; **Tuning** has hundreds of single
numbers, from running speed to how often a cat has two different eyes. The page changes cells in those
tables. When you apply, the changed tables go into your mod's pak, and the game reads them instead of its
own.

The page has three parts:
- **Quick changes:** the changes people ask for most, in words, each with a slider, a box for the number,
  the game's normal value and a **Normal** button that puts it back.
- **Find a number:** a search across every table. Type what the number does ("run", "xp", "mouse",
  "scars", "build time") and pick it from the list.
- **All tables:** every table, cell by cell, for anything Quick changes doesn't have.

Every quick change is an ordinary change to a cell: it shows in All tables too, and in the file under
**For mod makers**.

## A five-minute first try

1. Open **Game data**. Quick changes is at the top, with **Running speed** at 390.
2. Drag its slider to 600, or type 600 in its box. The row says "390 -> 600", and the Editing mod bar
   says "Unsaved changes".
3. Press **Save to mod**. It goes in **My mods**, unless you picked another mod in the bar.
4. Press **Apply to game**. The log says your mod went in.
5. Press **Play**, and run in the forest.

## What you can and can't do

You can:
- change any number in any table the game reads as it plays: speeds, stamina, levels, prey, den build
  times, fights, the Clan cats' sizes and scars, herbs;
- multiply a whole column (every animal's XP times 2, say), and keep one row out of it by typing its own
  value;
- switch a TRUE/FALSE column with a tick, and pick a word from a list where a column has only a few;
- search for a number by what it does, and open its table on that row.

You can't, here:
- make the game read a number it doesn't ask for: a row of your own in Tuning does nothing;
- change your own cat's level or what it carries: that's your save, on the **Save** page;
- change the map's data (heights and places): the page doesn't list those tables.

Some changes are for cats the game makes from now on: the Clan cats' sizes, scars and eyes are chosen when
a cat is made, so cats already in your save keep theirs. A new game, or new kits, show them.

## Did it reach the game?

- The page saves a change only when you press **Save to mod**, and the game gets it only when you
  **Apply to game** (or **Play**, which applies first).
- After an Apply, the log says which mods went in. A warning there names a change the game didn't take,
  with the mod it's in.
- Running speed, walking, jumping and stamina are read by the game's own code. For the other quick changes
  the numbers come from the tables; that the game plays by them hasn't been seen in play yet, which the
  card says.

## Common mistakes

- **Text in a number column.** The page says "Use a number like 1.5" and keeps the box open. Use a point,
  not a comma: 1.5, not 1,5.
- **A chance over 1.** Scars and two different eyes are chances from 0 (never) to 1 (always). The page
  won't let one go over 1.
- **Two mods changing the same number.** The one with the higher priority wins, and the log says which.
  Two mods that both double XP make it four times.
- **A table the game doesn't have.** A file written by hand, or made for an older version of the game, can
  name one. The page shows it under the list of tables with a **Remove**, and the rest of the file still
  goes in.
- **A change that does nothing yet.** Sizes and scars change cats made from now on, not the ones you
  have.

## Undo

- **One change:** its **Normal** button in Quick changes, or type the game's value back into the cell.
- **A whole table:** **Put this table back**, above the table, in All tables.
- **Not saved yet:** switch to another mod in the bar and choose **Switch without saving**, or close the
  page.
- **Everything:** turn the mod off on the Mods page and apply. The game goes back to its own numbers.

[How Clan Mod Studio works](studio.md) has the Editing mod bar, Save to mod and Apply. The file's own rules
are in [the file formats](../formats.md#datajson).
