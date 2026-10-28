# Palettes

The Palettes page changes the colours every cat in the game picks from: the eyes, the coats, the
patterns and the markings. It saves them as `palette.json` in a mod, like every Make page saves its
own file ([How Clan Mod Studio works](studio.md) explains mods, Save to mod and Apply).

## What it changes in the game

The game keeps a numbered list of colours for each part of a cat: 26 eye colours (the eye white, 20
standard ones and 5 extra ones that come with a game add-on), and 25 coat, 25 pattern and 25 marking
colours. A cat doesn't store a colour, it stores a number: "coat 3", "pattern 7".

- **Recolouring** one of the game's colours changes every cat that wears that number, in every save.
  Coat 3 stays coat 3, so a cat's traits and stats never change; it just looks different.
- **New colours** add pattern and marking colours past the game's (number 25 and up) without changing
  any of the game's. Only the cats set to a new number wear it: your cat, on the Your cat page, or a
  cat made in the cat maker with the Creator palettes mod.
- **Eye colours** go in through the game's own files, so they work on their own. Coat, pattern and
  marking colours are changed while the game runs, by the script loader (Get set up, on the Mods page,
  installs it).

## A five-minute first try

1. Open Palettes and press **Pattern**.
2. Press **Add a new pattern colour**. A card called "New pattern colour 25" appears; press the colour
   box on it and pick a pink.
3. Press **Save to mod**. The first time, the studio makes **My mods** for you and switches it on.
4. Open **Your cat**. Under **Colours from the game's picker**, the Pattern colour row now ends with a
   dashed square, number 25, in your pink. Press it, then press **Save to mod**.
5. Press **Play**. It applies your mods first, then starts the game.

Your cat now wears your new pattern colour, and no other cat does.

## What you can and can't do

You can:

- give any of the game's eye, coat, pattern and marking colours a colour of your own, on its card;
- give an eye **One colour** (it keeps the game's shading, dark at the pupil) or a **Gradient** of two
  to four colours spread from the pupil (left of the strip) to the rim (right);
- add as many new pattern and marking colours as you like. Each keeps its number for good, so a cat set
  to one keeps it whatever else you switch on;
- restyle a whole tab at once: **Vivid**, **Pastel**, **Moonlit** or **Ember** under "Restyle this
  tab". On the Eyes tab they change every eye colour, the extra ones too, and leave the eye white alone;
- start again from the game's colours, or from another palette you have (**Start from**). Both keep your
  new colours;
- switch between ready-made palettes in one go with **Quick palettes**: tick the ones you want and press
  Apply. That switches the ticked ones on, the other palette-only mods off, and puts them in the game.

You can't:

- add new coat colours. The game pairs each coat with paw, ear, nose and whisker colours of its own,
  and a coat without them crashes it. To give just your cat a coat colour nobody else has, use
  **Colours of its own** on the Your cat page;
- add new eye colours: the game has exactly 26;
- see the real pattern shapes or the paws, ears, nose and whiskers in the drawing. It's a sketch of a
  cat's face with your colours on it; in the game, paws, ears, nose and whiskers follow the coat;
- pick a new colour in the cat maker without the Creator palettes mod.

Before the game has run once with the script loader, the studio doesn't know the game's own coat,
pattern and marking colours. Their cards show stripes and a number ("shows after one Play") instead of
a colour, and they still take a colour of yours. Press Play once and come back, and the real colours
are there. Until the studio has found the game, the Eyes tab waits; the other tabs work.

Two things haven't been watched in the game yet: coat colours changing on screen, and a cat wearing a
new pattern or marking colour. The pieces that make them work have been, one by one.

## Did it reach the game?

- After **Save to mod**, a line under the Editing mod bar says if anything would keep the file out of
  the game, and a grey list says what Apply would leave out (an eye name the game hasn't got) or where
  another palette wins (two palettes adding the same new colour number: the one later in the Mods list
  shows).
- After **Apply to game** or **Play**, the line at the top of the log names the mods that went in, and
  the status at the top says "Game up to date". **Last apply** shows that log again.
- In the game, eye colours show straight away. Coat, pattern and marking colours change a couple of
  seconds after the game starts, once the script loader has run.

## Common mistakes

- **Recolouring a coat to change just your cat.** Every cat with that coat number changes. For one cat,
  use Colours of its own on the Your cat page.
- **Ticking two full themes** under Quick palettes. Only one of them shows (the one later in the Mods
  list). Pick one theme; eyes-only or coats-only palettes go on top of it.
- **Going by an eye's name.** Some of the game's names don't match the colour (Yellow is green). Go by
  the strip on the card.
- **Applying with changes unsaved.** Apply puts in what's saved. If you apply with changes still on the
  page, the bar says "Not in the game yet: Save to mod, then Apply" until you save them.
- **Applying while the game runs.** Close the game first; the buttons say so while it's open.
- **A palette.json written by hand.** Entries the page can't show (a misspelt eye, a coat number past
  24, something a palette hasn't got) are listed under the tabs, "entries this page can't show". They
  stay in the file as written until you press their **Remove**.

## Undo

- **The last whole-tab change**: after Vivid, Reset tab, Start from or Game colours, an **Undo** button
  appears beside "Restyle this tab" and puts the tab back. It goes when you save or switch mods.
- **One colour**: **Reset** on its card puts the game's colour back; **Remove** takes a new colour out.
- **Before you save**: switch to another mod in the bar and leave the changes behind, and the page goes
  back to what's saved.
- **After you apply**: switch the mod off on the Mods page (or fix it) and apply again, and the game's
  colours come back. A cat set to a new colour shows no colour while the palette that adds it is off; it
  keeps the number, so switching the palette back on brings the colour back.
