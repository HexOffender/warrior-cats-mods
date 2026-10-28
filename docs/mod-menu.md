# The mod menu in the game

The mod menu is a window in the game with pages from wcmods and from your mods. It goes in with every
Apply while the [script loader](guide/README.md#script-loader) is in the game. This page is for players;
mod makers who want a page of their own in it start at [SDK.md, `WCModsMenu`](SDK.md#wcmodsmenu).

## Opening it

- **With the keyboard:** Insert opens it, and Insert or Escape closes it. Tab or the arrow keys move
  between its controls, and Enter or Space presses one.
- **With a controller:** View opens it, the d-pad moves between its controls and A presses them, and
  View or B closes it. Opened from a controller, the game pauses while it's open. It doesn't open from a
  controller while something else has the game paused, such as the game's own pause menu.
- **Its size:** A- and A+ in its top bar change it until the game closes.
- **Its settings:** under **Options**, on the Settings and repair page in Clan Mod Studio: **Opens
  with** (its key), **or on a controller** (its button, View to begin with) and **Size**. They apply on
  the next Apply. The Controls page won't put an action on the menu's key.

## What's in it

The side bar groups its pages; a group shows once a page is in it.
- **Home:** **Overview** (the keys, the keys your mods use or changed, and where each page is) and
  **Installed mods** (what went in, and what each part of the build set up). With Menu pages, **At a
  glance** too.
- **Your cat:** **Colours** (your cat's own colours) and **Mouse look**, when your mods have them, and
  **Emotes**, with your emotes. With Menu pages, **Stats**.
- **World**, **Story**, **Fight** and **Cheats:** the Menu pages mod's pages (below).
- **Mods:** the pages your mods add. A script mod with a `settings.json` gets one, and so do Tweaks.
- **Tools:** **Log** (the script loader's log, newest first: your mods' lines, the errors, or
  everything), **Menu** (its size, pausing, the line under its title) and, with mods that run code
  allowed, **Inspector** and **Lua (advanced)**, for people who write scripts.

Changes there are live: mouse look and your cat's colours change as you move their sliders. **Save** on
those pages writes the change back into the mod, so the next Apply keeps it.

## Menu pages

The pages about the game are a mod of their own, Menu pages
([HexOffender/wcmods-menu-pages](https://github.com/HexOffender/wcmods-menu-pages)): **At a glance**,
your cat's **Stats**, **World**, **Travel**, **Nearby**, **Items**, **Quests**, **Fight**, **Cheats** and
**Game switches**, and the line under the menu's title saying how your cat is doing.
- **Getting it:** it's one of the [mods that go with Clan Mod Studio](guide/companion-mods.md).
  **Add all four** in Get set up, or **Add** on its row of their card on the Mods page, downloads its
  latest release and adds it, and **Get the latest** updates it, keeping its settings. Its .zip can be
  added like any mod, and the command line's `addons add menu-pages` does the same
  ([cli.md](cli.md#mods)).
- **It's a script that runs in the game,** so like any script it runs only with mods that run code
  allowed (**Options**, on the Settings and repair page). Without it, or with it off, the menu's
  **Overview** says what's missing.

## Cheats

Cheats are the engine's cheat manager, which the game's release build leaves off. On Menu pages'
**Cheats** page, the **Cheats** switch turns them on and off while you play. With them on, it has:
- **God mode (nothing hurts you)**;
- **Moving:** Walk, Fly or Ghost. W A S D or the left stick move the way the camera faces; Space and Left
  Ctrl, or the triggers, go up and down. Fly stops at walls; Ghost goes through them. **Flying speed**
  sets how fast.
- **Cat size**, which scales the whole cat;
- **Teleport to where the camera looks**;
- **Game speed**;
- **Engine command**, a box for any engine command, with **stat fps** and **stat unit** a press away.

With cheats on, the cheat commands of the game's own command window work too (`god`, `slomo 0.5`,
`teleport`). Its own `fly`, `ghost` and `changesize` don't stick: the game puts its cat back to its own
movement each frame and resets its model's scale, so the page does those itself, and moves the cat
while it flies.

**Start with cheats on**, at the top of the page, makes them start on from the next time the game starts.
**Cheats on when the game starts**, under **Options** on Settings and repair (while Menu pages is in your
mods), is the same switch, and so is the command line's `cheats on`.

Some cheats can break a quest or a save, so back up your save first if you're unsure (**Back up now**, on
Settings and repair).

## The game's own command window

`~` or F10 opens the game's own console, through the script loader. **The game's own command window**,
under **Options** on Settings and repair, switches it on or off from the next time the game starts.

## Not checked in the game yet

Seen working in the game: the menu opening with Insert and readable at 1920x1080, its live settings,
its pages about the game running without errors, and on the Cheats page, cheats switching on, fly, ghost
and cat size. Not yet checked ([verified.md](verified.md#not-yet-confirmed-in-game)):
- **Save** on the Mouse look and Colours pages;
- cats' own names in **Nearby**'s labels;
- god mode, game speed and teleport on the Cheats page;
- the pause menu while the old key remapper runs;
- the **Tweaks** page and its **Save**;
- a script that didn't start being named on the **Overview**, and the **Log** page's filters.
