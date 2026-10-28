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

The card at the top picks the cat: **Your cat**, or any cat in your save, listed by game (the one you played
last first) and clan (the clan of your cat in that game first), with its role. Type in **Find a cat** to narrow the list. The card's
heading names the cat and its game. The drawn cat shows the look as you've chosen it, and
**In your save now** says what the cat has in your save, and from which game: its colours, eyes, scars
and shape.

### Which game is "your cat"

Your save holds a game for each cat you've started, each said by its number as the game's cat choice
numbers them (the first is your 1st game). With **Your cat** chosen, **Which game** says whose look it is:

- **The cat in the game you're playing (whichever it is when you Apply)**, the first choice. It changes
  the cat of the game you're playing when you apply, whichever that is then. It's the one to use for a mod
  you'll share: it changes the cat of whoever adds it. **In your save now** shows the game you played last.
- One of your games ("Sharppaw, your 5th game"). Only that game's cat changes, whichever game you're
  playing: its scars, its shape and the game's colours it wears go into that game in your save when you
  apply. Its colours of its own go on your cat while you play it, over the first choice's where both choose
  a part, found by its name, so another of your
  games whose cat has the very same name gets them too: the page says which. For someone you share the
  mod with, it's the cat in their game with that number.

Each choice has a look of its own in the file, so you can give the game you're playing one look and your
5th game another. A choice with a look already says "changed" in the list. Where a game's own look and
the first choice's both choose a part, the game's own wins while it's the game you're playing when you
apply, and the page says so on both. Two cats called Sharppaw in two games are told apart by their games'
numbers, never by the name.

Another cat in a game other than the one you played last gets its scars, shape and the game's colours in
that game, but its colours of its own go on only while its game is the one you're playing when you apply.

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
  colours aren't on that page. The page changes the colours of **The cat in the game you're playing**: in a
  game chosen in **Which game** with colours of its own, those win where both choose a part, and the page
  says so. Nobody has watched that Save in the game yet
  ([what's been checked](../verified.md#not-yet-confirmed-in-game)).

You can't:

- change a cat's traits: body, ears and face chose them when the cat was made, and they stay;
- give a cat a coat number past the game's 25 (the Palettes page says why);
- keep a size through a rank-up: the game sets your cat's size again when it ranks up. The next
  **Apply to game** writes yours again;
- see scars without the game's own *Injury system* switch on. It's in the game's Gameplay settings; on
  the Save page, type Injury in **Find in your save**.

Good to know:

- With **The cat in the game you're playing**, colours of its own go on the cat you're playing, whichever
  game it's in, and the game's colours, the shape and the scars go into the game you were playing when you
  applied. With one game chosen, they go into that game's cat only.
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
- The wrong game. **Which game** starts on **The cat in the game you're playing**: that's whichever game
  you play when you apply, not always the one you played last. Choose a game there to change only that
  game's cat.
- A name two cats share. Choosing one of them in the list changes just that cat's game colours,
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
