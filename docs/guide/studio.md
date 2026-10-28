# How Clan Mod Studio works

Clan Mod Studio is two things: the page you're reading this in, and the black window that opened with
it. The black window is the studio itself: it runs on your computer and nowhere else. The page is how
you talk to it.

- Close the black window and the page stops working, and says so (**Studio closed**). Double-click Clan
  Mod Studio again and the page comes back by itself. Anything you hadn't saved is still on it, ready to
  save.
- Close the page and the window keeps running. Open the page again from the address the window shows,
  or double-click Clan Mod Studio again: it finds the studio that's open.

If the studio is updated while it's open, **Restart the studio** shows at the top. Press it: a fresh
studio opens in a new window, and the page comes back by itself. The page reloads, so if one of your
pages has unsaved changes, it asks you to save them first. If the new studio hasn't answered in half a
minute, the page says so.

## The top of the page

- **Help** opens this guide. On every page, **How this works**, under the title, opens the guide's page
  about it.
- The small coloured labels (chips) say how things stand: **Game closed** or **Game running**;
  **No script loader** and **No save yet** while Get set up has something left to do; **Game updated**
  after a Steam update ([game build](README.md#game-build)); and whether the game has your mods:
  "2 changes to apply", **Not applied yet**, **Apply again** or **Game up to date**. Point at a chip to
  read what it means.
- At the right are **Last apply**, **Apply to game** and **Play**: the parts below say what each does.

## Your mods folder

Every mod is a folder, and all of them are in one place: your mods folder. It's in your files' folder,
outside the studio's own folder, so updating the studio never touches it. On most computers that's
`C:\Users\<you>\AppData\Local\WCMods`. Settings and repair shows where yours is, and
**Open the folder** there opens it; **mods folder**, under Add a mod on the Mods page, opens the mods
folder itself.

A mod you download goes in as a folder of its own when you drop its .zip on the Mods page. A mod you
make on the Make pages is a folder too, with one file for each page you used (`palette.json` for
Palettes, `cats.json` for Your cat, and so on) beside its `mod.json`, which holds its name, version and
description. You can look inside: they're plain text.

## The Editing mod bar and My mods

Every Make page has an **Editing mod** bar near its top. (On the Save page it's inside
**Keep it as a mod to share**, since that page changes your own save directly.) The bar says which mod
the page saves into. The first time, it's **My mods**: a mod the studio makes for you on your first
save, so you don't have to think about folders to get started. Everything you make goes into My mods
until you pick another mod in the bar, or make a new one with **New mod…** (type a folder name, then
**Create**).

When would you want more than one? When you want to share one thing and keep another to yourself, or
switch one thing off without the rest: a mod is what you switch on and off, and what you share.

The bar remembers your choice across pages: pick a mod on Palettes and the Names page opens on it too.

Under the bar, **Share** opens the mod's name, author, version and description, **Save as .zip** for
sending the whole mod to someone, and two buttons named after the page's file (Export palette.json and
Import palette.json… on Palettes) for that one file.

## Save to mod

Nothing you change on a page is in the mod until you press **Save to mod**. "Unsaved changes" shows in
the bar while there's something to save. If you pick another mod in the bar with changes unsaved, or
import a file over them, the studio asks first: **Save and switch** (or **Save and load**),
**Switch without saving** (or **Load without saving**), or **Stay**. If you close the page, the browser
asks too.

Saving checks the file the way Apply does first. If something in it would keep it out of the game (a
colour that isn't one, a quest naming a cat the mod hasn't got), a line under the bar starts "Saved, but
it can't go in the game yet" and says what. The file is saved all the same: fix it when you like, and
the line goes at the next save that's fine. "Good to know before you apply" lists what Apply will leave
out or warn about. What only shows once all your mods are put together is still found when you apply: a
table's rows and columns, a model or a picture, two mods changing the same thing. While the studio
can't read the game's files (say while Steam is updating it), the check waits for Apply.

When the save is fine, a mod that's off is switched on: saving means you want it in the game. The Save
page is the one exception. A mod made there starts off and stays off, since one that's on changes your
own save at the next Apply.

## Apply to game and Play

Saving puts your work in the mod. **Apply to game** (top right) puts your mods in the game: it reads
every mod that's on, makes the files the game needs, and copies them into the game's folder. It works
once Get set up has found the game, and only while the game is closed: while it runs, Apply to game and
Play wait. The chip at the top says when there's something to apply ("2 changes to apply",
**Not applied yet**), and **Game up to date** once there isn't.

**Play** does the same, then starts the game through Steam. While changes are waiting it reads
**Apply and play**; with nothing waiting, it just starts the game. So the usual rhythm is: change
something, **Save to mod**, **Play**.

The game's own files are never changed: what goes in sits beside them, under names of its own, and
**Take all mods out of the game** (Settings and repair) takes it out again. Two things stay: the
[script loader](README.md#script-loader), and what an Apply wrote into your save
([What Undo means here](#what-undo-means-here) says what that is).

## The log

While the studio applies, a panel at the bottom right, the [build log](README.md#build-log), shows what
it's doing, line by line, as it goes. When it's done, the line at the top says what happened in a
sentence: which mods went in, or what kept one out. After Play the panel closes by itself, unless
there's something to read (a warning, a mod that didn't go in); then it stays until you press **Close**.
When your mods change the game's numbers, the panel lists them too, one a line ("Tuning: Running speed
390 -> 450 (My mods)"), up to twenty. **Check my mods**, on Settings and repair, uses the same panel and
puts nothing in the game.

**Last apply** (top right) opens the last Apply, Play or Take all mods out again. It's also kept as
`last-apply.log` in your files' folder, for anyone helping you.

If some mods can't be made ready, nothing goes in, and the panel says which and why. Fix those mods or
switch them off, or press **Apply the rest anyway** (twice: the second press is to be sure) to put the
others in. A mod skipped that way comes out of the game until it's fixed.

## What Undo means here

There's no one Undo for the whole studio (a few pages have their own for their last change). You
rarely need one: nothing happens until you save, and nothing reaches the game until you apply.

- On a page, before you save: pick another mod in the bar, choose **Switch without saving**, then pick
  yours again. Or reload the page and let the browser leave without saving. Either way the page shows
  what's saved.
- After a save: a save replaces what the mod had. Change it back on the page and save again.
- After an apply, for everything that goes in the game's files (colours, keys, the words the game
  shows, game data, items, animations, your cats and quests, tweaks): switch the mod off, or change it
  back and save, then apply again. The game is back to how it was without it.
- What an apply wrote into your save stays when you switch the mod off: your cat's game colours, shape
  and scars from Your cat, cats renamed on Names, items from **Starting with some** on Items, and the
  changes in a mod's `save.json`. On Your cat, choose the old ones and apply again. On Save,
  **Put it back** under **Done so far** undoes one change, the page's own or a mod's. Any of them goes
  back with a save backup made before that apply (**Restore**, under Save backups on the Settings and
  repair page), but you lose what you played since.
- Your save game: the studio makes a copy of your save before anything changes it. **Restore**, on the
  Settings and repair page, puts one back.
- A mod you removed or replaced is kept too: **Put it back**, under Removed and replaced mods on the
  same page, brings it back switched off.

## Where your files are

Everything that's yours is in your files' folder (`C:\Users\<you>\AppData\Local\WCMods` on most
computers):

- `mods\`: your mods, one folder each.
- `wcmods.json`: the studio's settings (where the game is, what's installed). If it's ever damaged, the
  studio sets it aside, starts afresh and says so at the top (**Settings were reset**); Get set up, on
  the Mods page, finds the game again.
- `backups\`: copies of your save, and mods you removed or replaced.
- `save-changes.json`: the changes already made in your save by the Save page and by mods' `save.json`,
  so each one is made once.
- `cache\`: the last download of each of the mods that go with Clan Mod Studio.
- `last-apply.log`: what the last Apply, Play or Take all mods out did.
- `studio.log`: the details behind a "Something went wrong" message, for anyone helping you. It's kept
  small: past about a megabyte it starts again, with the one before kept as `studio.log.1`.

The studio's own folder (the one with Clan Mod Studio in it, the file you double-click) holds the studio
and its working files, nothing of yours. Updating it, or getting a fresh copy, leaves all of the above
alone.
