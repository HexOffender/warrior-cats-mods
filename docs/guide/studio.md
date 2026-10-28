# How Clan Mod Studio works

Clan Mod Studio is two things: the page you're reading this in, and the black window that opened with
it. The black window is the studio itself (it runs on your computer and nowhere else); the page is how
you talk to it. Close the black window and the page stops working, and says so. Close the page and the
window keeps running: open the page again from the window's address, or double-click Clan Mod Studio
again and it finds the one that's open.

## Your mods folder

Every mod is a folder, and all of them are in one place: your mods folder. It's outside the studio's
own folder, in your files' folder (`%LOCALAPPDATA%\WCMods`, which is `C:\Users\<you>\AppData\Local\WCMods`),
so updating the studio never touches it. Open the folder, on the Settings and repair page, shows it.

A mod you download goes in as a folder of its own when you drop its .zip on the Mods page. A mod you
make on one of the Make pages is a folder too, with one file for each page you used: `palette.json` for
Palettes, `cats.json` for Your cat, and so on. You can look inside; they're plain text.

## The Editing mod bar and My mods

Every Make page has an **Editing mod** bar at its top. It says which mod that page saves into. The
first time, it's **My mods**: a mod the studio makes for you on your first save, so you don't have to
think about folders to get started. Everything you make on any page goes into My mods until you pick
another mod in the bar, or make a new one with **New mod…**.

When would you want more than one? When you want to share one thing and keep another to yourself, or
switch one thing off without the rest: a mod is what you switch on and off, and what you share.

The bar remembers your choice across pages: pick a mod on Palettes and the Names page opens on it too.

## Save to mod

Nothing you change on a page is in the mod until you press **Save to mod**. "Unsaved changes" shows in
the bar while there's something to save. If you switch to another mod in the bar with changes unsaved,
the studio asks what to do with them (save them first, leave them behind, or stay); if you close the
page, the browser asks too.

Saving checks the file the same way applying would. If something in it would keep it out of the game,
a line under the bar says what, and the file is saved all the same: fix it when you like, and the line
goes when a save is fine. (When the studio can't read the game's files, say while Steam is updating it,
the check waits for Apply.)

A mod that's off is switched on when you save into it: saving means you want it in the game.

## Apply to game and Play

Saving puts your work in the mod. **Apply to game** (top right) puts your mods in the game: it reads
every mod that's on, makes the files the game needs, and copies them into the game's folder. The game
has to be closed for that. The status at the top says when there's something to apply ("2 changes to
apply", "Not applied yet"), and "Game up to date" once there isn't.

**Play** does the same, then starts the game through Steam. If nothing's changed, it just starts the
game. So the usual rhythm is: change something, Save to mod, Play.

Nothing of the game's own is ever changed: everything the studio puts in has its own name and comes
out again with **Take all mods out of the game** (Settings and repair).

## The log

While the studio applies, the panel at the bottom right shows what it's doing, line by line, as it goes;
when it's done, the line at the top says what happened in a sentence: which mods went in, or what kept
one out. After Play the panel closes by itself unless there's a warning, in which case it stays until
you close it. When your mods change the game's numbers, the panel lists them too, one a line ("Tuning:
Running speed 390 -> 450 (My mods)"), up to twenty. **Last apply**, at the top, opens the last one again;
it's also kept as `last-apply.log` in your files' folder, for anyone helping you.

If some mods can't be made ready, nothing goes in, and the panel says which and why. Fix or switch
off those mods, or press **Apply the rest anyway** to put the others in; a mod that's skipped that way
comes out of the game until it's fixed.

## What Undo means here

There's no Undo button, and there's no need for one: nothing happens until you save, and nothing
reaches the game until you apply.

- On a page, before you save: switch to another mod and back, and the page reloads what's saved.
- After a save: the file is yours to change again; save over it.
- After an apply: switch the mod off (or fix it) and apply again, and the game is back to how it was
  without it.
- Your save game: the studio makes a safety copy before anything touches it. **Backups and repair**, on
  the Settings and repair page, puts one back.
- A mod you removed is kept too: **Put it back** is on the same page.

## Where your files are

Everything that's yours is in your files' folder, `%LOCALAPPDATA%\WCMods`:

- `mods\`: your mods, one folder each.
- `wcmods.json`: the studio's settings (where the game is, what's installed). If it's ever damaged, the
  studio sets it aside, starts afresh and says so at the top; Get set up, on the Mods page, finds the
  game again.
- `backups\`: copies of your save game, and mods you removed or replaced.
- `last-apply.log`: what the last Apply or Play did.
- `studio.log`: the details behind a "Something went wrong" message, for anyone helping you.

The studio's own folder (the one with `Clan Mod Studio.bat` in it) holds only the studio. Updating it,
or getting a fresh copy, leaves all of the above alone.
