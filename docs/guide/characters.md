# Characters

## What it changes in the game

Cats of your own come into the forest when you play a sandbox cat. Each one wears the name and title you
gave it over its head, has the look you chose, stands beside your cat or at a spot you picked, and says
your lines when you walk up to it and use the game's *Talk* prompt. The Questlines page gives them quests
to hand out.

How it gets there: your cats are saved in your mod, and Apply puts them in the game. Then
[Sandbox mode](README.md#sandbox-mode), a mod of its own, brings them into the forest with a sandbox cat.
Sandbox mode runs inside the game, so it needs the [script loader](README.md#script-loader) and
[mods that run code](README.md#code-mods) allowed. The studio writes nothing into your save.

## A five-minute first try

1. Open **Characters** and press **Add a cat**. The new cat already has a look of its own.
2. Type a name in **Name**, say Mossfoot, and a title in **Title** if you like (Elder).
3. Under **Colours**, tick **Coat** and choose a colour.
4. Type a line or two in **What they say**, one line each.
5. Press **Save to mod**. The strip under the Editing mod bar says whether Sandbox mode is ready. If
   Sandbox mode is in your mods but off, saving turns it on and says so.
6. Close the game if it's open, then press **Play** (top right; it reads **Apply and play** while changes
   wait).
7. On the game's main menu choose *Sandbox Mode*, then make a new cat or choose one of your sandbox cats.
8. Mossfoot stands beside your cat. Walk up and use the *Talk* prompt (E, or A on a controller); press
   it again, or Enter, for the next line.

### Getting Sandbox mode

The strip under the Editing mod bar (on Questlines too) says where Sandbox mode stands, and what to press:

- "Sandbox mode 0.4 is on" (with the version you have): nothing to do.
- "Sandbox mode is off": press **Turn it on**, then apply.
- "You'll need Sandbox mode": press **Add Sandbox mode**, which fetches the newest release (0.4) from its
  releases page on GitHub. Or download the newest .zip from that page (the strip links it) and drop it on
  the Mods page. If mods that run code aren't allowed yet, the strip says to allow them too.
- "Sandbox mode is left out since the game's update": it was made for an older
  [game build](README.md#game-build), so Apply leaves it out. **Open the Mods page**: its card has
  **Use it anyway…**. Then apply.
- "Sandbox mode is in, but mods that run code aren't allowed, so it can't run": press
  **Open Settings and repair**, tick **Allow mods that run code**, then apply.
- "Your fixed looks need Sandbox mode 0.5": a fixed look is **Same look every time**. Your cats go in,
  but until you have 0.5 the game makes their look up each time. 0.5 isn't out yet
  ([Which versions are out](companion-mods.md#which-versions-are-out)). When it is,
  **Check for newer versions** on the Mods page shows "Newer one out: 0.5", and **Get the latest** brings
  it.

Your mod goes in the game without Sandbox mode all the same (its items, palettes and names with it); only
the cats wait for it.

## What you can and can't do

You can:

- give a cat a **Name**, and a **Title** shown smaller above it;
- choose **Same look every time** (its shape, pattern and colours chosen once and kept; a new cat starts
  with one) or **New look each time**, as the game does with its own cats. With the same look,
  **Fine-tune** sets each part of its shape and the colour [slot](README.md#slot) each colour comes from
  (pattern and markings can wear new ones your palettes add), and **Roll a new look** picks them all
  again. The same look needs Sandbox mode 0.5, which isn't out yet
  ([Getting Sandbox mode](#getting-sandbox-mode));
- tick a colour of its own for **Coat**, **Pattern**, **Markings**, **Nose**, **Paw pads**,
  **Inside the ears** or **Whiskers**, over the look's;
- choose its eye colour under **Eyes** (the first one, **Game's choice**, is made up each time) and its
  **Size**, from apprentice size to bigger than a leader;
- have it stand **Beside your cat** (beside your sandbox cat the first time it comes into the forest, and
  there after that) or **At one spot** for every sandbox cat; **Use where my cat is standing** reads the
  spot from the game while your cat is in the forest;
- give it up to 30 lines to say when it has no quest for you;
- **Make a copy** of a cat, to start the next one from it.

You can't, yet:

- make a cat walk, follow you or patrol: it stands where it's put;
- make it smaller than an apprentice, or give it scars or accessories;
- see its shape and pattern on the page: the drawing shows its colours only;
- give it answers to choose from when you talk;
- meet it in a story (*Prophecy Mode*) game: only sandbox cats see your cats.

## Did it reach the game?

- After Apply, the top line of the [build log](README.md#build-log) counts your cats: "1 cat from My
  mods; Sandbox mode 0.4 will show them." If it says "they're waiting for Sandbox mode", a warning in the
  build log says what's missing and what to do.
- In the game, your cats are there (beside your cat, or at their spot) a moment after a sandbox cat
  comes into the forest.
- The [mod menu](README.md#mod-menu) (Insert) has Sandbox mode's Questlines page. It has a
  "Bring Mossfoot here" button for each cat that stands beside you.
- A line under the Editing mod bar that starts "Saved, but it can't go in the game yet" says what to fix.
- A cat with **Same look every time** that looks different each time means your Sandbox mode is older than
  0.5, which isn't out yet. The strip says so, and so does the build log after Apply.

## Common mistakes

- Playing a story cat: your cats come only into *Sandbox Mode* games.
- Pressing G: older guides said G, but it's the game's own *Talk* prompt, E (or A on a controller).
- At one spot, with no spot: until all three numbers are filled in, the cat stands beside your cat,
  and the **Not ready yet** note at the top of the cat says so. Press **Use where my cat is standing**
  with your cat in the forest, or type the numbers.
- A palette's colour, with the palette off: a cat set to a pattern or markings colour that only a
  palette adds shows no colour there while that palette is off. The **Not ready yet** note says so. Turn
  the palette on, or choose another colour.
- Removing a cat a quest uses: the message names the quest, so choose another cat there, on the
  Questlines page, before you apply.

## Undo

- Before saving: switch to another mod in the Editing mod bar, choose **Switch without saving**, and
  switch back. The page shows what's saved.
- After saving: change the cat and save again, or press **Remove** (twice) and save.
- After Apply: switch the mod off on the Mods page (or remove the cats) and apply again. The cats are gone
  the next time a sandbox cat comes into the forest.
- Sandbox mode remembers where each cat stood beside each sandbox cat, in a file of its own beside the
  game's saves (not in your save). "Bring Mossfoot here", on the mod menu's Questlines page, moves a cat
  beside you again.

For the file this page writes, see [npcs.json](../formats.md#npcsjson).
