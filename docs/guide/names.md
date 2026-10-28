# Names

The Names page renames the cats in your save, changes the names the game hands out to new cats, and
renames other words the game shows. It saves them as `names.json` in your mod.

## What it changes in the game

- **Cats in your save**: a new name for any cat, yours included.
- **Prefixes** and **Suffixes**: a clan cat's name is two parts, a prefix and a suffix (Otter + paw).
  The suffix changes with rank: kits are -kit, apprentices -paw, leaders -star. Rename a part and every
  name with it changes (Otterpaw, Otterheart and Otterstar become Mothpaw, Mothheart and Mothstar). Add
  a part and the game can hand it out to new cats. Remove one and it stops (cats that have it keep it).
- **Rogue and loner names**: cats outside the clans have one whole name, from a list of their own.
- **Ban list**: names the game never gives a new cat, mostly the books' characters.
- **Cameo cats and any other name**: the cameo cats (Brightheart, Rock and the others) and any text in
  the game that's exactly a name.
- **Places, quests and items**: an area's name, a quest's title or an item's name.

Renames change the English text. Other languages keep their own. A name you add shows in every
language, in English.

How it gets there: renamed and added words go in with your mods when you apply, and the game shows
them in place of its own. Cats' new names are written into your save at the same time, after a backup.

## A five-minute first try

1. Open Names. Under **Cats in your save**, your cat is first ("your cat" is under its name).
2. Type Sparkle in its **New name** box, then press Tab. The line under the box says "Sparkle at every
   rank": a name that isn't a prefix + suffix stays the same as your cat grows up.
3. Tick **grows with rank**. The line now gives your cat's name for its rank ("Sparklepaw now; the end
   changes with each rank" for an apprentice): Sparkle is your cat's own prefix.
4. Press **Save to mod**.
5. Close the game if it's open, then press **Play** (top right; it reads **Apply and play** while changes
   wait).
6. Your cat's new name shows on screen while you play, and on the *Select Your Cat* screen.

## What you can and can't do

You can:

- give any cat in your save a new name: a prefix + suffix the game has (Mothheart), a name of your own
  (Sparkle), or, with **grows with rank** ticked, a prefix of your own;
- give a rogue or loner one of the rogue names, or any name of your own;
- in **Prefixes**, **Suffixes** and **Rogue and loner names**: type a new text under **Rename to**, tick
  **Remove**, or add one in the **Add** row at the top of the card. A new prefix or suffix is handed out
  as often as the one you pick beside it ("used like Wren"), or as an average one. The kit, paw and star
  suffixes can be renamed but not removed;
- click a name on the **Ban list** to allow it again, or ban any prefix + suffix the game can make with
  **Ban name**;
- rename a cameo cat in its row, or any other name: type it in **Any name**, the new one in **New
  text**, and press **Add**;
- rename an area, a quest's title or an item under **Places, quests and items**, near the bottom of the
  page. Open it, find the one you want with **Find a place, quest or item**, and type its new name.
  Some quests share one title (Rest 1, 2 and 3): their row says so, and the new title shows on all of
  them.

You can't, yet:

- make the game hand out a whole name of your own to new clan cats (Luna for a new kit). The game builds
  their names from the two lists, so a new name for new cats has to be a new prefix or suffix;
- rename a cat while the game is open: close it first, then apply;
- change names in other languages;
- rename an item another mod adds: its name comes with that mod, and its row says so;
- add a line for a cat to say, or change a quest itself (only its title).

A name of your own is text your mod adds to the game. The game shows it only while that mod is on, so
keep the mod on, and keep it on when you share it.

## Did it reach the game?

- Before you apply, **After Apply** says what each cat will be called. A changed cat never shows a blank
  there: if the game would have no text for the name, it says **no text** and the cat keeps its name.
- **What this does**, near the top, counts the names that change and lists the cats being renamed, with
  a **Check** beside anything worth a look.
- After you apply, the list shows your cats' new names straight away.
- In the game, your cat's name shows on screen while you play and on the *Select Your Cat* screen.
- A renamed area, quest title or item shows in the [mod menu](README.md#mod-menu)'s pages, which come
  with [Menu pages](README.md#menu-pages).
- Not checked in the game yet: new cats being given added parts, no longer given removed ones, or
  following the ban list's changes; the suggestions on the game's name screen; a rogue name given to a
  clan cat; one of the game's prefixes given to a rogue or loner; and renamed areas, quest titles and
  items on the game's own screens (the area's name as you walk in, the quest log, the inventory).

## Common mistakes

- A cat shows as Cat 1, or as `<MISSING STRING TABLE ENTRY>`. The save has the cat's new name, but the
  game has no text for it, because the mod that named it is off. The cat's row says "name from a mod
  that's off", and a box above the list names the cats. Turn that mod back on and apply. If it's the mod
  you're editing, the box says "This mod is off": **Save to mod** turns it on. Or press **Give it a game
  name** on the cat's row, then **Save to mod** and apply. If it happens with the mod on, check that the
  apply finished, and that **Get set up**, on the Mods page, found the copy of the game Steam starts.
- No cats in the list: "No save yet". Start the game once, and your cats show here.
- A typo. Wrenhart isn't Wren + heart, so it becomes a name of its own that never changes. The line
  under the box says which: "Wren + heart: grows with rank", or "Wrenhart at every rank".
- Renaming a word that's also something else. Rock is a cameo cat and a material, and Fox is a rogue
  name and an animal. **Any name** renames every text that's exactly that word, and the line under it
  says what else changes ("also changes the material Rock").
- Two parts with the same text. Renaming Otter to Wren gives two prefixes called Wren, and the page
  warns about it.
- Taking out an earlier rename. **Earlier renames** lists renames already in your save, and ones for
  cats this save doesn't have. Keep them: a cat can need one for its name to have text. If taking one
  out (its ×) would leave a cat without, the page asks first.

## Undo

- Before you save: switch to another mod in the Editing mod bar, choose **Switch without saving**, and
  switch back. Or reload the page.
- Saved, not applied yet: clear the cat's box (or press **Reset** on a part's row), then **Save to
  mod**.
- Parts, rogue names, the ban list, other names, places, quests and items come with the mod: switch it
  off on the Mods page and apply, and the game's own are back. A cat with a name of your own then shows
  as Cat 1, so give it a game name first.
- A cat renamed in your save keeps its new name, even with the mod off. To change it back, type its old
  name in its box (or press **Give it a game name**, which offers the name it had), then **Save to mod**
  and apply. If its first rename is listed under **Earlier renames**, take that out with its × too, or
  a later apply can rename the cat again.
- Everything at once: your save is backed up before every apply that renames cats. On
  [Settings and repair](settings.md), under **Save backups**, press **Restore** beside one from before
  (press it twice). The next apply renames the cats again if the mod is still on, so switch it off
  first. **Take all mods out of the game**, on the same page, says first which cats would lose their
  names.
