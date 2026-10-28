# Your cat

The Your cat page gives your cat, or any other cat in your save, a look of its own: colours nobody
else has, which of the game's colours it wears, its shape and its scars. It saves them as `cats.json`
in a mod ([How Clan Mod Studio works](studio.md) explains mods, **Save to mod** and **Apply to game**).

## What it changes in the game

There are two ways to colour a cat, and the page has a card for each:

- **Colours of its own** go onto the cat while you play: its coat, paw pads, inner ears, nose and
  whiskers, any colour at all. No other cat gets them, and they show in menus and portraits too. They go
  on through the [script loader](README.md#script-loader) (**Get set up**, on the Mods page, installs it),
  and they go away when you switch the mod off.
- **Colours from the game's picker** choose which of the game's own numbered colours
  ([slots](README.md#slot)) the cat wears: its coat, pattern, markings and each eye, as the cat maker
  would. New pattern and marking colours your palettes add (the Palettes page) are there too, as dashed
  squares.

The **Shape** card changes the cat itself: its body, fur shape, tail, ears, eyes, whiskers, face,
pattern, markings and **Size**. The **Scars** card chooses its scars. The game's colours, the shape and
the scars are written into your save when you apply, after the studio makes a copy of your save.

**Whose look**, at the top, picks the cat: **Your cat**, or any cat in the game you're playing, listed
by clan (yours first) with its role. Type in **Find a cat** to narrow the list. The drawn cat shows the
look as you've chosen it, and **In your save now** says what the cat has in your save: its colours,
eyes, scars and shape.

## A five-minute first try

1. Open **Your cat**. Under **Colours of its own**, tick **Nose** and pick a bright pink.
2. Under **Colours from the game's picker**, press a different square in the **Coat colour** row.
3. Press **Save to mod**. The first time, the studio makes **My mods** for you and switches it on.
4. Close the game if it's open, then press **Play** (top right; it reads **Apply and play** while changes
   wait).
5. In the forest, your cat has the pink nose and the new coat, and so does its picture on screen.

The pink nose needs the script loader; the new coat doesn't.

## What you can and can't do

You can:

- give your cat, or any cat in your save, colours of its own, another coat, pattern, marking and eye
  colour, another shape and size, and scars (or **No scars at all**);
- pick a new pattern or marking colour a palette adds. Only the cats set to it wear it;
- change your cat's colours of its own while you play. In the game, Insert opens the
  [mod menu](README.md#mod-menu): its Colours page has sliders for them, and its Save writes them into a
  mod (the **Colours of its own** card names which one). The page is there while a mod that's on gives a
  cat colours of its own. Its Save writes the cats.json of your last Apply with the new colours in it,
  so apply again before you use it, or changes saved on this page since then are lost. Other cats'
  colours aren't on that page. Nobody has watched that Save in the game yet
  ([what's been checked](../verified.md#not-yet-confirmed-in-game)).

You can't:

- change a cat's traits: body, ears and face chose them when the cat was made, and they stay;
- give a cat a coat number past the game's 25 (the Palettes page says why);
- keep a size through a rank-up: the game sets your cat's size again when it ranks up. The next
  **Apply to game** writes yours again;
- see scars without the game's own *Injury system* switch on. It's in the game's Gameplay settings; on
  the Save page, type Injury in **Find in your save**.

Good to know:

- Colours of its own go on the cat you're playing, whichever save slot it's in. The game's colours, the
  shape and the scars go into the game you were playing when you applied.
- Another cat's colours of its own go on by its name, only in the game you're playing. A rank-up
  changes a cat's name (Gustpaw becomes Gust-something), so apply again after one.
- Coats 20 to 24 belong to the game's Feral Edition; a game without it gives those cats another coat.
  The page warns when you pick one.
- The drawing is a sketch of the cat's face: it shows the colours and the ear and eye scars, not the
  body shape, the back and chest scars or the paws.
- **In your save now**, and the thinner ring around a square, show what your save holds. They're read
  again after every Apply, after a save on any page, and when you come back to the studio's window.

## Did it reach the game?

- After **Save to mod**, a line under the **Editing mod** bar says if anything would keep the file out of
  the game. **Good to know before you apply** lists what Apply would warn about: a new colour no palette
  that's on adds (it would show no colour), or a Feral Edition coat.
- After **Apply to game** or **Play**, the line at the top of the [build log](README.md#build-log) names
  the mods that went in, and **In your save now** shows what your save has. With no save yet, the log
  says so: the game's colours, the shape and the scars wait for a save and the next Apply.
- In the game, your cat shows its new look in the forest, and its picture on screen does too.

## Common mistakes

- No script loader. Colours of its own need it. The status at the top of the studio says "No script
  loader" until **Get set up**, on the Mods page, installs it.
- No save, or a save that can't be read. With no save yet, start the game once and come back. "Your save
  couldn't be read" usually means the game was writing it: wait a moment and come back to the window.
  Colours of its own work all the same.
- Scars that don't show. Switch on the game's *Injury system* (its Gameplay settings).
- A name two cats share. Choosing one of them in **Whose look** changes just that cat's game colours,
  shape and scars. Its colours of its own still go on every cat with its name, because the game tells
  them apart only by name.
- A new colour from a palette that's off. The cat shows no colour there until that palette is on again.
- A cats.json written by hand. What the page can't change is listed under
  **Things this page can't change** on its card, kept as written until you press **Remove**.

## Undo

- Before you save: press a chosen square again to keep the one in your save; untick a colour of its own
  or **Size**; choose "Keep what my cat has now" for a shape part or a scar, or press
  **Keep the scars it has now**. Or pick another mod in the **Editing mod** bar and choose
  **Switch without saving**.
- Colours of its own, after you apply: switch the mod off on the Mods page and apply again, and they go.
- The game's colours, the shape and the scars, after you apply: they stay in your save even with the mod
  off. Choose the old ones on this page and apply again. Or switch the mod off, then put back the copy of
  your save the studio made before: **Restore** beside it, under **Save backups** on the Settings and
  repair page (press it twice). You lose what you played since that copy. Switch the mod off first:
  while it's on, the next Apply writes its changes again.
