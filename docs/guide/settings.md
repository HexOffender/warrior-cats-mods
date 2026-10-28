# Settings and repair

## What it changes in the game

The page has three parts:

- **Options**: the [mod menu](README.md#mod-menu)'s key, controller button and size; whether
  [Menu pages](README.md#menu-pages) starts with cheats on; **The game's own command window**; and whether
  [mods that run code](README.md#code-mods) may go in the game.
- **Backups and repair**: copies of your save, and putting one back; mods you removed, put back; a check
  of your mods; and taking every mod out of the game.
- **Make your own mod**: an empty mod to start from, from its **Name** alone.

How it gets there: the mod menu's key, button and size, and mods that run code, go in the next time you
press **Play** or **Apply to game**. The command window and the cheats are read when the game starts, so
they change from its next start, with no Apply. A backup is a copy of the game's save folder, kept in your
files' folder.

## A five-minute first try

1. Open **Settings and repair** (in the side bar, under Your mods).
2. Under **Options**, choose a key in **Opens with**, say Home. The message says "Saved. Apply to game to
   use it."
3. Under **Save backups**, press **Back up now**. A copy of your save appears in the list, named with
   today's time and "backed up by you".
4. Press **Play** (top right; **Apply and play** when there's something to apply).
5. In the forest, press Home: the mod menu opens. (It needs the [script loader](README.md#script-loader).)

## What you can and can't do

You can:

- Choose the mod menu's key (**Opens with**), a controller button that opens it too
  (**or on a controller**), and its **Size**. In the game, A- and A+ in the menu's top bar change its size
  until the game closes.
- Say whether Menu pages starts with cheats on (**Cheats on when the game starts**), while Menu pages is in
  your mods. Its *Cheats* page in the mod menu switches them on and off while you play.
- Switch on **The game's own command window**: ~ or F10 opens it in the game, for people who know the game
  engine's own commands.
- Allow mods that run code (**Allow mods that run code**). A warning first names your mods that do; press
  **Allow mods that run code** in it to say yes. Get set up, on the Mods page, asks the same thing once.
- Back up your save at any time (**Back up now**), and put a backup back (**Restore**, pressed twice). The
  ten newest are listed, each named in words: when, and why ("backed up by you", "before Apply (save
  edits)", "First safety copy"). Restoring backs up the save you have first.
- Bring back a mod you removed, or the older copy of one you replaced (**Put it back**, under
  **Removed and replaced mods**). It comes back switched off.
- Check every mod without putting anything in the game (**Check my mods**). The
  [build log](README.md#build-log) says what each one does and any problems.
- Take every mod out of the game (**Take all mods out of the game**, pressed twice). Your mods stay in
  your mods folder.
- See what crashed the game. If it crashed since your last Apply (or since you took all mods out),
  **The game crashed last time** shows at the top of Backups and repair: when, what the game said, the mod
  it was in when the report can tell, **Copy the report** (for whoever helps you), a button to turn that
  mod off, and **Close**. The Mods page shows the same card.
- Open the folder with your mods, settings and backups (**Open the folder**).
- Start an empty mod: type a **Name** under **Make your own mod** (its folder shows under the box) and
  press **Make it**. It's made switched on; pick it in the Editing mod bar on any Make page.

You can't:

- Restore a save while the game is running: close it first.
- Back up a save that isn't there yet: **Back up now** is greyed out until you've started the game once
  and got into the forest.
- Open the mod menu, or use the game's own command window, without the script loader. If the page says
  the script loader has no console mod in it, install the script loader again (Get set up, on the Mods
  page).
- Give the mod menu just any key: it's Insert, Home, End, Delete, Page Up, Page Down, or F1 to F12 but F11
  (the game's full-screen key).
- Undo a save edit by taking the mods out: what an Apply wrote into your save stays. The Save page's
  **Done so far** puts a save edit back (not yet checked in the game), and a save backup puts the whole
  save back.

## Did it reach the game?

- After changing the mod menu's key, button or size, the chip at the top says there's a change to apply,
  and the Mods page's "Not in the game yet" says "apply again: the mod menu's settings changed". **Play**
  puts it in.
- The command window and the cheats change from the next time the game starts.
- After allowing mods that run code, the Mods page's cards stop saying "Runs code, so the game won't get
  it until you allow mods that run code". The game gets them at the next **Play** or **Apply to game**.
- After **Restore**, the message says your save is back as it was, and names the copy kept of the one you
  had.
- After **Take all mods out of the game**, the build log says what came out, and the chip at the top says
  "Not applied yet" (or "Nothing installed") instead of "Game up to date".

## Common mistakes

- You allowed mods that run code, and nothing changed. Press **Apply to game** (top right) or **Play**:
  allowing doesn't put anything in by itself.
- You took all mods out, and **Play** put them back. Play puts your mods in. To play without them, switch
  them off on the Mods page first, or start the game from Steam.
- Your save edits came back after restoring. The next Apply makes your mods' save changes again, if those
  mods are still on; switch them off first to keep them out.
- The new key doesn't open the mod menu. Press **Play** or **Apply to game** first: the key goes in with
  your mods. The mod menu also needs the script loader.
- **Take all mods out of the game** names some cats first. Those cats have names only your mods give, and
  after taking the mods out they'd show as `<MISSING STRING TABLE ENTRY>`. Give them game names on the
  Names page (**Open Names**) and Apply first, or press **Take them out anyway** and put a save backup
  back later.

## Undo

- An option: change it back. The mod menu's key, button and size go in at the next **Play**; the command
  window and the cheats at the game's next start.
- Allowing mods that run code: untick **Allow mods that run code**, then **Apply to game**: they come out.
- A restore: the save you had is in the list too ("the save you had before a restore"); **Restore** it.
- **Take all mods out of the game**: **Play** or **Apply to game** puts your mods back in.
- A mod you made and don't want: **Remove** it, under its **More** on the Mods page. It's kept, so
  **Put it back** brings it back.
