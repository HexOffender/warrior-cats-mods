# Questlines

## What it changes in the game

Your cats from the Characters page give quests to a sandbox cat. A cat with a quest for you wears the
game's quest mark, and talking to it takes the quest up. The step you're on shows in the game's objective
panel on the left, with a marker on the map where to go, and at the end the reward is dropped at your
cat's paws. A quest can wait for others to be done first, so quests can tell a story.

How it gets there: your quests are saved in your mod, and Apply puts them in the game. Then
[Sandbox mode](README.md#sandbox-mode) runs them for each sandbox cat and remembers how far it has got, in
a file of its own beside the game's saves. The studio writes nothing into your save.

## A five-minute first try

1. Make a cat on **Characters** first (say Mossfoot) and save it. Keep the same mod chosen in the Editing
   mod bar on both pages.
2. Open **Questlines**, press **Add a questline** and type "Moss for Mossfoot" in **Title**. **Given by**
   is your first cat already, and the first step is a **Talk** with that cat.
3. In that step's **What they say**, type two lines, one line each.
4. Beside **Add a step**, press **Pick up**. In the new step, set the number to 2 and choose Moss.
5. Press **Talk** again and type a thank-you line. Under **Reward**, choose an item in the **Add** list.
6. Press **Save to mod**, then **Apply and play** at the top right.
7. On the game's main menu choose *Sandbox Mode*, then make a new cat.
8. Walk up to Mossfoot and use the *Talk* prompt (E, or A on a controller); Interact or Enter shows the
   next line. The objective panel says "Find 2 Moss". Pick up two, talk to Mossfoot again, and the
   reward drops at your paws.

Sandbox mode has to be in your mods and on. The strip under the Editing mod bar says what to do, as
[Getting Sandbox mode](characters.md#getting-sandbox-mode) explains.

## What you can and can't do

You can:

- make steps that are done in order: **Talk** to one of your cats, **Pick up** some of an item, or
  **Go somewhere** (a spot in the forest, or the nearest medicine cat), with **Done within** for how
  close is close enough;
- give the quest to one of your cats in **Given by**, or to nobody, so it starts on its own;
- make a quest wait for others under **Starts after**;
- give a reward of items, your own herbs and materials from the Items page included;
- write your own words for a step's **Objective**, or leave it empty for the words shown, which take the
  names your cats and items have when you apply;
- say what the quest is about in **About it**, shown under its title on the mod menu's Questlines page
  (with Sandbox mode 0.5 or newer).

You can't, yet:

- put a quest in the game's own quest list: it shows in the objective panel and on the mod menu's
  Questlines page instead;
- take the items away when they're handed in: they stay in your inventory;
- make a step to hunt, fight or climb, or give experience as a reward;
- give the player answers to choose from when a cat talks;
- send the player anywhere but a spot, or the nearest medicine cat by name;
- use a cat from another mod: quest givers and talking steps are the same mod's cats.

Not checked in the game yet: a quest starting over by itself after you change it (Sandbox mode 0.5,
under Undo), and **Start every questline over**. Both have been tested without the game, but nobody has
watched them in it yet.

## Did it reach the game?

- After Apply, the top line of the [log](README.md#build-log) counts them: "1 cat and 1 questline from My
  mods; Sandbox mode 0.5 will show them." The log also warns about a quest that names an item the game
  hasn't got and no mod adds.
- In the game, a cat with a quest for you wears the game's quest mark, and the objective panel shows the
  step you're on.
- The [mod menu](README.md#mod-menu) (Insert) has Sandbox mode's Questlines page, listing every quest with
  how far you've got: "Not started yet", the step you're on, or "Done".
- A line under the Editing mod bar that starts "Saved, but it can't go in the game yet" says what keeps
  the quests out, such as quests that wait for each other in a circle. The **Not ready yet** note at the
  top of the quest says it as you work, and marks the step.

## Common mistakes

- Quests that wait for each other: if A starts after B and B after A, neither ever starts. The page
  won't let you tick the box that closes a circle, and says so if one is in the file already.
- A talk step with nothing to say: each talk needs at least one line.
- A cat from another mod: quests use the cats saved in the same mod, so choose that mod in the Editing
  mod bar on both pages.
- Moss you had already: a **Pick up** step counts only what you pick up after the step starts.
- It's done already: a sandbox cat that finished a quest doesn't get it again. Start it over (below).

## Undo

- Before saving: switch to another mod in the Editing mod bar, choose **Switch without saving**, and
  switch back.
- After saving: change the quest and save again, or press **Remove** (twice) and save.
- After Apply: switch the mod off on the Mods page and apply again. What a reward gave your cat stays in
  its inventory, like anything it picks up.
- One quest again: the mod menu's Questlines page has a "Start Moss for Mossfoot over" button for a quest
  you've begun or finished. With Sandbox mode 0.5 and more than one quest, it also has "Start every
  questline over", for the cat you're playing.
- Every quest again: **Start every questline over**, under **Starting over** on this page (press it
  twice), starts every mod's questlines over, not only this mod's, for all your sandbox cats. Close the
  game first. Where their cats stand is kept.
- With Sandbox mode 0.5 or newer, a quest a cat hasn't finished starts over by itself when you add or take
  out a step, change a step's kind (moving steps can do that), or change what or how many a **Pick up**
  step wants. New lines, objectives or a new title don't restart it, and a finished quest stays finished.

For the file this page writes, see [quests.json](../formats.md#questsjson).
