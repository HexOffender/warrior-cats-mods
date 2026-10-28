# The Mods page

## What it changes in the game

The Mods page decides which mods are in the game. A mod switched on here goes in the next time you press
**Play** or **Apply to game** (top right); a mod switched off comes out. Nothing in the game changes until
then.

From top to bottom, the page has:

- **Get set up**: the things to do once, each with a tick. When they're all done it folds to one line, and
  **Show the steps** opens it again.
- **Mods that go with Clan Mod Studio**: four mods of their own that bring what you make into the game:
  [Menu pages](README.md#menu-pages), [Sandbox mode](README.md#sandbox-mode), Creator palettes and the
  Emote wheel. **What they do** opens [their page](companion-mods.md).
- **Add a mod**: where a mod's .zip goes, from a friend or a download.
- **Your mods**: every mod in your mods folder, with a switch each.

How it gets there: Play and Apply to game copy what your mods make into the game's folder, under names of
their own, so the game's own files are never changed.

## A five-minute first try

1. Open Clan Mod Studio. The Mods page opens first, with **Get set up** at the top.
2. It finds the game and makes a safety copy of your save by itself. If it asks **Where's the game?**, copy
   the game's folder in (in Steam: right-click the game, Manage, Browse local files) and press
   **Use this folder**. If it says **Start the game once**, do that first, then come back.
3. Close the game if it's open, and press **Install it** to put in the
   [script loader](README.md#script-loader).
4. Press **Allow** on **Let mods run their own scripts**, read the warning about
   [mods that run code](README.md#code-mods), and press **Allow mods that run code**.
5. Press **Add all four**. Clan Mod Studio downloads them from GitHub.
6. Press **Play** (**Apply and play** when there's something to apply). In the forest, press Insert: the
   [mod menu](README.md#mod-menu) opens, with Menu pages' pages about your cat.
7. Back in the studio, drop a mod's .zip on **Drop a mod's .zip here**, press **Add to my mods**, then
   **Play** again.

## What you can and can't do

You can:

- Add a mod from its .zip, or pick a few out of a .zip that holds many (**Add these**). Before anything is
  added, the preview shows what each one changes, whether it runs code, and what else it needs.
- Choose whether each one goes in switched on (**Switch it on**, or **Switched on** beside each one in a
  .zip that holds several). Each starts as its maker shipped it: Creator palettes' ten themed palettes
  start off, say.
- Drop a mod's .zip on Clan Mod Studio itself (the file you double-click to open it): the Mods page shows
  the same preview.
- Add a folder: put it in your mods folder (**mods folder**, under Add a mod), then press **look again**.
- Switch mods on and off. A mod that needs another switches that one on too, and switching off a mod that
  others need asks first.
- Find a mod by its name, its author or the words in its description, in **Find a mod**, and show only
  the mods that are **On** or **Off**.
- Under a mod's **More**: give it a **Priority** (when two mods change the same thing, the higher number
  wins), **Open its folder**, **Save as .zip** to share it, or **Remove** it. A mod with a script in the
  game and settings of its own shows the settings there too, with **Save settings**; the script reads them
  when the game starts.

You can't:

- Change what's in the game while the game is running: it keeps its files open, so **Apply to game** and
  **Play** are greyed out. Close it, change what you like, press **Play**.
- Put in a mod that needs a mod you don't have. It's added switched off, and its card says what it needs.
- Put in a mod made for a newer Clan Mod Studio. Its card says it needs a newer Clan Mod Studio: get it
  (unzip a new download over the old folder; your mods stay where they are).
- Put in a mod that runs code while mods that run code aren't allowed. Its card says so.
- Count on a mod whose card says "New models or textures": it brings them in the game's own format, and
  no mod like that has been tried in the game yet.

## Did it reach the game?

- Under Get set up, "Not in the game yet" lists what's waiting (a mod on, a mod off, a mod changed, a mod
  left out and why, or a reason to apply again, such as mods that run code being allowed since the last
  time), with **Apply to game**. Before your first Apply it says "Nothing is installed yet". When nothing
  is waiting, it says "The game has your mods as they are here".
- The chip at the top says "Game up to date" once the game has everything.
- **Last apply** (top) opens the [build log](README.md#build-log) of the last Apply or Play: which mods
  went in, by name, or what kept one out.
- A mod's card says in red why that mod isn't in the game: it needs a mod that's off or missing, it was
  made for an older version of the game, or it needs a newer Clan Mod Studio.
- A mod with a script in the game has a line on its card saying how the script did when the game last
  started. **What it said**, under its **More**, shows what the script wrote.
- In the game, the mod menu's *Installed mods* page lists what went in.

## Common mistakes

- You added a mod and nothing changed in the game. Press **Play** (or **Apply to game**) after adding: the
  "Not in the game yet" banner says what's still waiting.
- A mod went in switched off. The message says why, for example "Added Moonlit cats, switched off: it
  needs Sandbox mode." Add the mod it needs (one of the four has its **Add** on the Mods that go with Clan
  Mod Studio card), then switch yours on.
- You have two copies of the same mod. An older Clan Mod Studio named a downloaded mod after its file
  name, version and all. Remove the older one (**More**, then **Remove**). From now on, a newer .zip of a
  mod replaces the copy you have, and the preview says so ("Replaces the Cool Mod 1.2 you have with 1.3").
- "Your mods go into another copy of the game." Steam starts a different copy of the game than the one
  your mods go into. Press **Use Steam's copy**.
- "Close the game, then apply." The game is still running. Close it, then press **Apply to game**.
- A mod is left out after Steam updated the game to a new [game build](README.md#game-build). A mod with no
  code in it, like a palette or names, is checked on the new version when the page opens ("Checking your
  mods on the new version…"), and the ones that work go in with the next **Play**. One that doesn't says
  why: **Turn it off** and wait for its maker (it's checked again when it changes), or
  **Use it anyway…**. A mod that runs code can't be checked here: wait for its maker, or
  **Use it anyway…** after its warning, and back up your save first.
- The game crashed. **The game crashed last time** shows at the top of this page, with the mod it was in
  when the report can tell; [Settings and repair](settings.md) has the same card.

## Undo

- Before adding: **Cancel** on the preview, and nothing is added.
- After adding: switch the mod off, or **Remove** it (under its **More**; press it twice). A mod you
  remove or replace is kept: **Put it back**, on the Settings and repair page, brings it back, switched
  off.
- A step of Get set up you said **Not now** to: **Show the steps** opens the card again. The scripts step
  has **Allow…**, and the card of the mods that go with Clan Mod Studio adds those one at a time.
  Allowing mods that run code can also be changed at any time under **Options**, on the Settings and
  repair page.
- After Play: switch the mod off and press **Play** again; it comes out of the game. What a mod wrote into
  your save stays in your save: put back a save backup to undo that ([Settings and repair](settings.md)).
