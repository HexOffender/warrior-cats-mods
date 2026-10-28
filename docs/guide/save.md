# Save

The Save page changes your own save: your cat's level, its experience, the fresh-kill pile, what it
carries. Each change is made once, with a copy of your save kept first, and you can put any of them back.

## What it changes in the game

Your save is the game's record of everything you've played: one game for each cat you've started, and
the game's settings. The page reads it, shows your cat (the one you play now), and changes the values you
ask it to. Nothing else in the save moves.

You make a list of changes first. **Change my save now** makes them all, after it keeps a copy of your save
in **Settings and repair**. The game has to be closed: it writes its save as you play, and would write over
the change.

## A five-minute first try

1. Close the game, and open **Save**. It shows **Your cat**, with its level and the fresh-kill pile.
2. Press **Fill the fresh-kill pile**. **Changes to make** shows "your cat's fresh-kill pile: 62 -> 100".
3. Press **Change my save now**. The page says when it was done, and that a copy of your save from before
   is in Settings and repair.
4. **Done so far** shows the change, with **Put it back**.
5. Press **Play**.

## What you can and can't do

You can:
- set your cat's level (1 to 20), its experience and the fresh-kill pile (0 to 100);
- press **Max level** (level 20, experience 0), **Fill the fresh-kill pile** or **Give herbs** (five more
  each of Horsetail Stalks, Marigold Petal, Comfrey Poultice and Lamb's Ear Leaves);
- change how many of each thing your cat carries, take things out, and add things by name;
- change anything else in the save under **Advanced**, where the whole save is, with a search;
- keep the list as a mod to share, under **Keep it as a mod to share**: whoever installs it gets each
  change once, in their own save. A mod made there starts off, and saving doesn't turn it on, so your own
  save isn't changed by it. While the mod is on (you turned it on, or it was on already), the next Apply
  makes its changes in your own save too, once, and the fold says so. Turn it off on the Mods page if
  it's only to share.

You can't, here:
- change your cat's rank: promotions come from the rank-up quests, so Max level leaves the rank as it is;
- change key bindings: the game keeps its own copy and ignores the save's. The **Controls** page does it;
- change a cat's looks or name by hand: **Your cat** and **Names** do those safely;
- keep health and stamina changed: they refill in play, so the page shows them and doesn't change them.

## Did it reach the game?

- **Done so far** lists every change made to this save, by this page or by a mod, with what it was
  before and when.
- A change from a mod's `save.json` is made when the mod is applied. If you had no save yet then, the
  status at the top says "save edits are waiting for a save" once the game has made one: press Apply.
- Start the game and look: your level shows in the mod menu's Stats page, and the fresh-kill pile at camp.

## Common mistakes

- **The game is open.** The page says so and waits. Close the game first.
- **A number out of range.** Level goes from 1 to 20, the fresh-kill pile from 0 to 100, counts from 0.
  The page says the range and keeps the save's value.
- **Expecting a change to come back.** Each change is made once. If you play on past it (level 10, then 14
  in play), the next Apply leaves 14 alone. To make it again, change it here again.
- **The wrong cat.** The page changes the cat you play now. To change another, play it once, then come
  back.
- **A new cat in the same slot.** A mod's change is made once for each save slot, not each cat: start a
  new cat in a slot where it was made, and the new cat doesn't get it. Make it here, with **Change my save
  now**.
- **The combat stats.** When a fight starts the game works out stats from your level, so a change under
  Advanced may not last.

## Undo

- **Not made yet:** **Remove** beside the change in **Changes to make**.
- **One change made:** **Put it back** in **Done so far** writes what it was before, after another copy of
  your save. If the save has moved on since (your cat is level 14 now), the page asks first.
- **Everything:** **Settings and repair** keeps a copy of your save from before every change. Putting one
  back puts the whole save back, with the list of what had been changed in it then: the changes your mods
  made since that copy are made again at the next Apply (if the mods are still on), and the ones it has
  already aren't. A copy of the save you had is kept first, so putting that back undoes it.

[How Clan Mod Studio works](studio.md) has Apply and the log. The file a mod shares is in
[the file formats](../formats.md#savejson).
