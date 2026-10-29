# The guide

Help for Clan Mod Studio, a page at a time. **Help**, at the top of the studio, opens this list in a
panel; **How this works**, under a page's title, opens the page about it; **Open in a tab** shows the
page you're reading in a tab of its own. Each line below says what that page changes in the game, in
the order of the side bar.

## Start here

- [How Clan Mod Studio works](studio.md): your mods folder, the **Editing mod** bar and My mods,
  **Save to mod**, **Apply to game** and **Play**, the log, what Undo means here, and where your files
  are.

## Your mods

- [The Mods page](mods.md): which mods are in the game. **Get set up** once, add mods, switch them on and
  off, and see whether they got there.
- [Mods that go with Clan Mod Studio](companion-mods.md) (a card on the Mods page): four mods that bring
  what you make into the game: pages in the mod menu, *Sandbox Mode* on the main menu, your new colours in
  the cat maker, and an emote wheel. Which versions are out, and how to get them.
- [Mod packs](packs.md): mods that play together as one experience, on their own or with yours.
- [Settings and repair](settings.md): the mod menu's key and size, the game's own command window,
  whether mods may run code, putting back your save or a mod you removed, and taking every mod out of
  the game.

## Make mods

- [Palettes](palettes.md): the colours every cat picks from (eyes, coats, patterns and markings), and
  new coat, pattern and marking colours.
- [Your cat](cat.md): one cat's look, yours or any cat in your save: colours only it wears, which of the
  game's colours it wears, its shape and its scars.
- [Controls](controls.md): which key, mouse button or controller button does what in the game.
- [Names](names.md): the names of the cats in your save, the names the game gives new cats, and other
  words the game shows; and what to do when a cat shows as Cat 1.
- [Items](items.md): herbs, materials and things to wear of your own, in the inventory with their own
  names and icons.
- [Animations](animations.md): animations on your cat and the animals: emotes on a key, or one in place
  of one of the game's own, taken from the game's animations or made by you in Blender.
- [Characters](characters.md): cats of your own that come into the forest in
  [Sandbox mode](#sandbox-mode) games, with their looks, where they stand and what they say.
- [Questlines](questlines.md): quests those cats hand out, step by step, with a reward at the end.
- [Game data](data.md): the numbers the game plays by: how fast your cat runs, what a fight is worth,
  what prey is worth, how big the Clan cats are.
- [Save](save.md): your own save: your cat's level, the fresh-kill pile, what it carries. Each change is
  made once, after a copy of your save is kept, and can be put back.
- [Tweaks](tweaks.md): small changes while you play: stamina that stays full, a key that heals your
  cat, a clock that stands still, a fresh-kill pile that never runs low.

## Advanced

- [Try Lua in the game](console.md): for people who write scripts. It runs one line in the game while it
  plays and shows what came back. It's in the side bar only once [mods that run code](#code-mods) are
  allowed, and nothing on the other pages needs it.

## Words you'll meet

The other pages link these words here, the first time they use them.

### Slot

The game keeps each kind of colour in a numbered list: 26 eye colours, and 25 each for coats, patterns
and markings. Each place in a list is a slot, and a cat keeps slot numbers, not colours: "coat 3". So
changing what slot 3 holds, on [Palettes](palettes.md), changes every cat with coat 3, while
[Your cat](cat.md) chooses which slots one cat wears. Your save has slots too, one for each game you've
started: those are save slots.

### Script loader

A free add-on for the game (its name is UE4SS) that lets mods run inside the game while you play.
**Get set up**, on the [Mods page](mods.md), installs it when you press **Install it**. These all need
it: the mod menu; key changes from Controls, and mouse look; emotes on keys; models on cats; your cat's
own colours; the coat, pattern and marking colours from Palettes; Tweaks; mods with scripts; and the
mods that go with Clan Mod Studio. Until it's in, the top of the studio says **No script loader**.
**Take all mods out of the game** leaves it installed.

### Code mods

Mods that run code: small programs that run inside the game, or steps that run on your computer when
your mods are applied. The studio calls them mods that run code. They stay out of the game until you
allow them with **Allow mods that run code**: **Get set up** asks once, and Options, on
[Settings and repair](settings.md), has the same switch. Code can do anything your account can, so
allow it only if you trust every such mod you've added. The four mods that go with Clan Mod Studio are
code mods, and they're fine.

### Sandbox mode

A mod that goes with Clan Mod Studio. It adds *Sandbox Mode* to the game's main menu: a cat in any
Clan, in the normal forest, with no story. The cats you make on [Characters](characters.md) and the
quests you make on [Questlines](questlines.md) come into the game only in a Sandbox Mode game.
[Mods that go with Clan Mod Studio](companion-mods.md) says how to get it, and which version you need.

### Menu pages

A mod that goes with Clan Mod Studio: pages in the [mod menu](#mod-menu) about your cat, the world,
quests, fights and cheats. Without it the mod menu still opens, with its Overview, Installed mods and
Log pages. [Mods that go with Clan Mod Studio](companion-mods.md) says how to get it.

### Mod menu

The menu your mods bring into the game: Insert opens it while you play (View on a controller). Its
Overview lists the keys your mods use and which pages are where, and Installed mods lists the mods that
went in. Its key, button and size are under Options on [Settings and repair](settings.md). It needs the
[script loader](#script-loader).

### Build log

What **Apply to game**, **Play** and **Check my mods** write as they work, in the panel at the bottom
right: a sentence at the top saying what happened, then every line. **Last apply** (top right) opens
the last Apply, Play or Take all mods out again, and it's kept in your files' folder as
`last-apply.log`. [The log](studio.md#the-log) says more.

### Game build

Steam updates the game now and then, and each version of it has a number: its build. A mod notes the
builds it was made for (one you make in the studio notes the build you made it on). After an update,
the top of the studio says **Game updated**, and the Mods page checks your mods on the new build. One
that only changes the game's data goes in if the check finds nothing wrong. One that runs code, or
can't be checked, is left out until its maker updates it, or until you press **Use it anyway…** on its
card. [The Mods page](mods.md) says more.

## The other docs

The rest of what Clan Mod Studio can do is written up in the project's other docs. They open on GitHub,
so they need the internet: the [README](../../README.md) for players (getting set up, the mod menu in
the game, remapping keys), the [file formats](../formats.md) each page writes, for people who'd rather
write a mod's files by hand, and [docs/README.md](../README.md), which lists every doc and who it's for.
