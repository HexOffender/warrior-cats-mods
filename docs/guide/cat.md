# Your cat

The Your cat page gives your cat (or any other cat in your save) a look of its own: colours nobody
else has, which of the game's colours it wears, its shape and its scars. It saves them as `cats.json`
in a mod ([How Clan Mod Studio works](studio.md) explains mods, Save to mod and Apply).

## What it changes in the game

There are two ways to colour a cat, and the page has a card for each:

- **Colours of its own** go onto the cat while you play: its coat, paw pads, inner ears, nose and
  whiskers, any colour at all. Nothing else changes, no other cat gets them, and they show in menus
  and portraits too. They need the script loader (Get set up, on the Mods page, installs it), and they
  go away when you switch the mod off.
- **Colours from the game's picker** choose which of the game's own numbered colours the cat wears:
  its coat, pattern, markings and each eye, as the cat maker would. New pattern and marking colours your
  palettes add (the Palettes page) are there too, as dashed squares.

The other cards change the cat itself: its **Shape** (body, fur, tail, ears, eyes, whiskers, face,
pattern, markings and size) and its **Scars**. The game's colours, the shape and the scars go into your
save when you apply, and the studio makes a copy of your save first.

**Whose look** at the top picks the cat: your cat, or any cat in the game you're playing, listed by clan
(yours first) with its role, and found by its name (or by its place, when two cats share a name). Type in
**Find a cat** to narrow the list. Below it, the drawn cat shows the look as you've chosen it, and **In
your save now** says what the cat has in your save: its colours, eyes, scars and shape, and when your mods
last went in the game.

## A five-minute first try

1. Open **Your cat**. Under **Colours of its own**, tick **Nose** and pick a bright pink.
2. Under **Colours from the game's picker**, press a different square in the **Coat colour** row.
3. Press **Save to mod**. The first time, the studio makes **My mods** for you and switches it on.
4. Close the game if it's open, then press **Play**. It applies your mods first.
5. In the forest, your cat has the pink nose and the new coat, and so does its picture.

## What you can and can't do

You can:

- give your cat, or any cat in your save, colours of its own, a different coat, pattern, marking and
  eye colour, a different shape and size, and scars (or none);
- pick a new pattern or marking colour a palette adds, which only the cats set to it wear;
- change colours of its own while you play: the mod menu in the game (Insert) has a Colours page with
  sliders, and its Save writes them back into the mod. It writes the cats.json of your last Apply with
  the new colours in it, so apply again first, or edits saved on this page since then are overwritten.
  Nobody has watched that Save in the game yet: the [list of what's been checked](../verified.md) has
  it under "Not yet confirmed in game".

You can't:

- change a cat's traits: body, ears and face chose them when the cat was made, and they stay;
- give a cat a new coat number (the game has 25), or keep a size through a rank-up: the game sets the
  size again when your cat ranks up;
- see scars without the game's own **Injury system** switch on (the Save page has it, under the game's
  settings).

Good to know:

- Colours of its own go on the cat you're playing, whichever save slot it's in. The game's colours,
  the shape and the scars go into the game you were playing when you applied.
- Another cat's colours of its own go on by its name, so a cat with the same name gets them too, and a
  rank-up changes a cat's name: apply again after one.
- Coats 20 to 24 belong to the game's Feral Edition; a game without it gives those cats another coat.
- "Now" (the thinner ring, "now: 11 (kept)", and the In your save now card) is what your save holds. It's
  read again after every Apply, after a save on any page, and when you come back to the studio's window.
- A cats.json written by hand may name a cat by a shorter place ("WindClan/Warrior/1" for
  "Clans/WindClan/Warrior/1") or by a name in another case: the list puts it on the cat it changes, "in the
  file as" that key. A name two cats share changes both, and the list shows it as its own entry.
- The drawing is a sketch of the cat's face: it shows the colours and the ear and eye scars, not the body
  shape, the back and chest scars or the paws.

## Did it reach the game?

- After **Save to mod**, a line under the Editing mod bar says if anything would keep the file out of
  the game, and a grey list says what Apply would warn about: a new colour no palette that's on adds
  (it would show no colour), a Feral coat, or a name no cat in your save has.
- After **Apply to game** or **Play**, the line at the top of the log names the mods that went in, and
  this page's "now" shows what's in your save.
- In the game, your cat's picture at the top of the screen shows its new look.

## Common mistakes

- **No script loader.** Colours of its own need it; the status at the top of the studio says "No script
  loader" until Get set up installs it.
- **Scars that don't show.** Switch on the game's Injury system (the Save page, or the game's own
  Gameplay settings).
- **A name two cats share.** Both change. Pick the cat by its place instead, in Whose look.
- **A new colour from a palette that's off.** The cat shows no colour there until that palette is on.
- **A cats.json written by hand.** Anything the page can't change (a part it doesn't know, a number past
  the game's) is listed under "Things this page can't change" on its card, kept as written until you
  press **Remove**. A cat written as something other than a look (`"player": "none"`) is listed under
  Whose look; once you choose a look for that cat here, Save writes it in its place, and the list says so.
- **"Your save couldn't be read".** The game was probably writing it. Wait a moment and come back to
  the window; colours of its own work all the same.

## Undo

- **Before you save**: press a chosen square again to keep the one in your save; untick a colour of its
  own; choose "Keep what my cat has now" for a shape part or a scar, or press **Keep the scars it has
  now**.
- **Colours of its own, after you apply**: switch the mod off on the Mods page and apply again, and they
  go.
- **The game's colours, the shape and the scars, after you apply**: they stay in your save even with the
  mod off. Choose the old ones on this page and apply again, or put back the copy of your save the studio
  made before: **Backups and repair**, on the Settings and repair page.
