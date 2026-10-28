# Palettes

The Palettes page changes the colours every cat in the game picks from: the eyes, the coats, the
patterns and the markings. It saves them as `palette.json` in a mod, like every Make page saves its
own file ([How Clan Mod Studio works](studio.md) explains mods, **Save to mod** and **Apply to game**).

## What it changes in the game

The game keeps a numbered list of colours for each part of a cat: 26 eye colours (the eye white, 20
standard ones and 5 extra ones that come with a game add-on), and 25 coat, 25 pattern and 25 marking
colours. A cat doesn't store a colour. It stores a number, a [slot](README.md#slot): "coat 3",
"pattern 7".

- Recolouring one of the game's colours changes every cat that wears that number, in every save. Coat 3
  stays coat 3, so a cat's traits and stats never change; it just looks different.
- New colours add pattern and marking colours past the game's (number 25 and up) without changing any
  of the game's. Only a cat set to a new number wears it: one you set on the Your cat page, or one made
  in the game's cat maker with the [Creator palettes](companion-mods.md) mod.
- Eye colours go in through the game's own files, so they work on their own. Coat, pattern and marking
  colours, and the cat maker's eye buttons, are changed while the game runs by the
  [script loader](README.md#script-loader) (**Get set up**, on the Mods page, installs it).

## A five-minute first try

1. Open **Your cat**. Under **In your save now**, the Eyes line names your cat's eye colours.
2. Open **Palettes**. On the **Eyes** tab, find the card with that name, under **Standard eyes** or
   **Extra eyes**.
3. Press the colour box on that card and pick a bright colour your cat's eyes aren't. The strip on the
   card shows it.
4. Press **Save to mod**. The first time, the studio makes **My mods** for you and switches it on.
5. Close the game if it's open, then press **Play** (top right; it reads **Apply and play** while changes
   wait).
6. In the forest, your cat's eyes are the new colour, and so are the eyes of every cat with that eye
   colour.

With no save yet, pick any eye: every cat with it changes. If the Eyes tab asks you to find the game
first, **Get set up**, on the Mods page, does that. Coat, pattern and marking colours work the same way on
their tabs, through the script loader.

## What you can and can't do

You can:

- give any of the game's eye, coat, pattern and marking colours a colour of your own, on its card: with
  the colour box, or by typing in the box beside it. That box takes a code someone shared (`#FF8800`), a
  colour name like "orange" (any name a web page knows, "peachpuff" too), or three numbers
  ("255, 136, 0"). Click it and its code is selected, ready to copy;
- give an eye **One colour** (it keeps the game's shading, dark at the pupil) or a **Gradient** of two
  to four colours, spread from the pupil (the left of the strip) to the rim (the right);
- add as many new pattern and marking colours as you like, with the button under **New colours** on the
  Pattern and Markings tabs ("Add a new pattern colour"). Each keeps its number for good, so a cat set to
  one keeps it whatever else you switch on. The Your cat page shows them as dashed squares;
- restyle a whole tab at once with **Vivid**, **Pastel**, **Moonlit** or **Ember**, under
  **Restyle this tab**. On the Eyes tab they change every eye but the eye white. Your new colours stay
  as they are;
- start again from the game's colours (**Game colours**) or from another palette of yours (its name),
  under **Start from**. Both keep your new colours;
- compare with the game's own colours: beside the drawn cat, **the game's** shows them and
  **my colours** brings yours back;
- switch between ready-made palettes in one go, under **Switch between ready-made palettes** (open it
  from its heading). Tick the ones you want and press the Apply button under them ("Apply 2 and
  install" with two ticked). It switches the ticked ones on and the other palette-only mods off, and
  puts them in the game. Colours you haven't saved are saved first, and the palette you're editing is
  ticked too (a toast says so). Mods with more than a palette in them aren't listed, and nor are
  palettes that only add new colours.

You can't:

- add new coat colours. The game pairs each coat with paw, ear, nose and whisker colours of its own,
  and a coat without them crashes it. To give just your cat a coat colour nobody else has, use
  **Colours of its own** on the Your cat page;
- add new eye colours: the game has exactly 26;
- pick a new colour in the game's cat maker without the Creator palettes mod, which needs
  [mods that run code](README.md#code-mods) allowed and the script loader;
- see the real pattern shapes, or the paws, ears, nose and whiskers, in the drawing. It's a sketch of a
  cat's face; in the game, paws, ears, nose and whiskers follow the coat.

Before the game has run once with the script loader, the studio doesn't know the game's own coat,
pattern and marking colours. Their cards show stripes and "after one Play" instead of a colour, and they
still take a colour of yours; the restyle buttons wait. Press **Play** once and come back, and the real
colours are there. Until the studio has found the game, the Eyes tab waits; the other tabs work.

Two things haven't been watched in the game yet: coat colours changing on screen, and a cat wearing a
new pattern or marking colour. The pieces that make them work have been checked one by one
([what's been checked](../verified.md#not-yet-confirmed-in-game)).

## Did it reach the game?

- **What reaches the game**, at the top of the page, says it before you start. Each line has a chip,
  "ready" or "not yet", and says what's missing: eye colours need the game found; coat, pattern and
  marking colours need the script loader (Apply warns when it's missing); new colours and coat presets
  reach the cat maker only with the Creator palettes mod on, mods that run code allowed and the script
  loader in. The last line says when your mods last went in the game.
- After **Save to mod**, a line under the **Editing mod** bar says if anything would keep the file out of
  the game. **Good to know before you apply** lists what Apply would leave out (an eye name the game hasn't
  got) or where another palette wins (two palettes adding the same new colour number: the one later in
  the Mods list shows).
- After **Apply to game** or **Play**, the line at the top of the [build log](README.md#build-log) names
  the mods that went in, and the status at the top says "Game up to date". **Last apply** shows that log
  again.
- In the game, eye colours show straight away. Coat, pattern and marking colours change a couple of
  seconds after the game starts, once the script loader has run.

## Common mistakes

- Recolouring a coat to change just your cat. Every cat with that coat number changes. For one cat, use
  **Colours of its own** on the Your cat page.
- Ticking two full themes under **Switch between ready-made palettes**. Where two ticked palettes change
  the same colour, only the one later in the Mods list shows there, and the page names both and asks you
  to untick one. Pick one theme. A palette that changes only the eyes or only the coats goes on top of a
  theme when it's later in the Mods list; the page says that too, as a plain note.
- Going by an eye's name. Some of the game's names don't match the colour (*Yellow* is green). Go by the
  strip on the card.
- Applying with changes unsaved. Apply puts in what's saved. If you apply with changes still on the
  page, the bar says "Not in the game yet: Save to mod, then Apply" until you save them.
- A palette.json written by hand, or by someone else. What the page can't show (a misspelt eye, a coat
  number past 24, one colour written twice) is listed under the tabs as "entries this page can't show",
  each with a **Remove**. It stays in the file as written until you remove it, or set that colour on the
  page, which then takes its place.

## Undo

- One colour, before you save: **Reset** on its card puts the game's colour back; **Remove** takes a new
  colour out.
- The last whole-tab change: after a restyle, **Reset tab**, **Game colours** or a Start from, an Undo
  button appears after **Reset tab** ("Undo Vivid", say) and puts it back. It goes when you save or
  switch mods.
- Everything since you last saved: pick another mod in the **Editing mod** bar and choose
  **Switch without saving**. Switch back, and the page shows what's saved.
- Ready-made palettes: press **Untick all**, then **Use the game's colours and install**.
- After you apply: switch the mod off on the Mods page and apply again, and the game's colours come
  back. Nothing of a palette is in your save. A cat set to a new colour shows none while the palette
  that adds it is off; it keeps the number, so switching the palette back on brings the colour back.
