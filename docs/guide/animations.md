# Animations

The Animations page puts animations on your cat and the animals: one of the game's own, or one you made
in Blender. You don't need Blender to start: the game's yawns, stretches and photo poses are all on the
page. It saves them as `animations.json` in your mod.

## What it changes in the game

Under **What it does**, each animation does one of three things:

- **An emote on my cat**: a key you choose (or a controller button) plays it on your cat, and the
  [mod menu](README.md#mod-menu) gets an Emotes page with a button for it. It plays over what your cat
  is doing, where it stands. The key again, or walking off, stops it.
- **Plays where the game plays one of its own**: every cat (or every animal of that kind) plays it
  wherever the game played the one it replaces: a trot of your own, say. It's fitted to that one's
  length, and its footsteps stay where they were.
- **Only for scripts and stories**: a script or a mod's story plays it on a cat or an animal.

How it gets there: an animation in another's place goes in with your mods when you apply. Emotes and
the ones for scripts play through the [script loader](README.md#script-loader), which **Get set up**,
on the Mods page, installs. Nothing goes into your save.

## A five-minute first try

1. Open Animations and press **Add an animation**. In **Name**, type "Yawn" in place of "New
   animation".
2. Under **Where it comes from**, keep **One of the game's animations**. In **The game's animation**,
   choose Yawn (under Everyday).
3. Under **What it does**, keep **An emote on my cat**. Press **Press a key…**, then F7.
4. Press **Save to mod**.
5. Close the game if it's open, then press **Play** (top right; it reads **Apply and play** while changes
   wait).
6. In the forest, press F7: your cat yawns. Press it again while it plays to stop it. The mod menu
   (Insert opens it, unless you changed its key) has an Emotes page with a Yawn button too.

This has been seen working in the game: F7 played the game's Yawn, and F7 again stopped it. If F7 does
nothing for you, the [build log](README.md#build-log) says why.

A second try, every cat trotting with the run: add another animation, choose Run in **The game's
animation**, then **Plays where the game plays one of its own**, and choose Trot in **In place of**.
Save, and press **Play**. (An animation from a file, and the game's own sleep loop, have been seen in the
trot's place; the run hasn't yet.)

## What you can and can't do

You can:

- use any of the game's animations for that animal. The everyday ones come first by plain names (Yawn,
  Stretch, Shake, Sniff, Play, Sleep, Meow, Get up, Walk, Trot, Run, Idle), then the photo poses by the
  game's own names for them, then all of them by the game's file names;
- see one on your cat before you choose it: **Try it on my cat** plays it in the game while it runs
  with your cat in the forest. It needs [mods that run code](README.md#code-mods) allowed (**Allow mods
  that run code**, on [Settings and repair](settings.md));
- put an emote on a key (**Press a key…**) or a controller button (**Press a controller button…**),
  with its claws out (**Claws out while it plays**);
- under **How it plays**: **Loop until it's stopped**, a **Speed** (1 is as made), and a **Blend**
  (seconds to ease in from what the cat was doing, and back);
- make animations for mice, rats, rabbits, squirrels, birds, foxes, badgers, dogs and snakes too, from
  their own animations (**For**). An animal's plays in another's place, or for scripts: emotes are your
  cat's;
- make your own in Blender: **Start kits (for Blender)**, near the top of the page, saves each animal
  rigged the game's way, and **A file I made in Blender** takes the .glb file you export, up to 60
  seconds long;
- show your emotes on a wheel too, with the Emote wheel, one of the
  [mods that go with Clan Mod Studio](companion-mods.md). It has no release yet, and the page says so;
  once it has a release, the page has an **Add the Emote wheel** button until you have it.

You can't, yet:

- move your cat or an animal with an animation: it plays where it stands. Swimming, flying or a new way
  to walk would be animations only;
- play on part of the body: an animation moves the whole body;
- play on the named cats with models of their own (Brightheart, Tallstar and the others);
- give only your cat its own walk or idle: every cat shares the game's;
- add a sound, or move the face (blinking, the pupils);
- use the game's animations that are added on top of another pose (one of the meows is one): they
  can't play on their own, so the list leaves them out.

## Did it reach the game?

After you apply, each animation in the list gets a chip: **In the game** (with its key, for an emote),
or **Left out**. The top of the animation says why one was left out, and a line at the top of the page
sums it up: "In the game: Yawn (F7), Flap; left out: Wave (nothing chosen for it to play yet)." One
added since says **Not applied yet**. When you open the studio again later, the line at the top is the
last apply's, with its date. The whole story is in the build log: **Last apply**, at the top, opens it.

In the game, press the emote's key, or open the mod menu's Emotes page. A replacement shows wherever the
game plays the one it replaced.

Seen working in the game: emotes from files made in Blender (on a key and on the Emotes page, with
claws out, stopped by the key again and by walking off); the game's own animations as emotes (the Yawn,
and a Stretch with claws out); an animation from a file, and the game's own sleep loop, in the trot's
place; and mice's and birds' animations played by a script. Not checked yet: the run in the trot's
place, and **Try it on my cat**; an emote on a controller button; animations on the clans' cats; the
rats', rabbits', squirrels', foxes', badgers', dogs' and snakes'; and an emote's key stopping what the
Emote wheel started.

## Common mistakes

- Nothing chosen yet. An animation needs one of the game's, or a file. Until it has one, the list says
  "needs an animation" and it's left out of the game; the rest of the mod still goes in. The save says
  so under the Editing mod bar: "Saved. Left out of the game until finished: Wave (nothing chosen to
  play yet)." It says why, the same way, when one of the game's animations named in the file isn't in
  the game (a name typed by hand, with a mistake in it).
- A key something else uses. F6 turns mouse look on and off (unless you changed its key), F11 is the
  game's full screen, Insert opens the mod menu, and the game's own keys (E, Space...) do their own
  thing. F7 and F8 are free. Two emotes on one key: only one of them plays. The key dialog says why a
  key is taken, and uses it only if you press it again.
- Leaving the key dialog. Escape, **Cancel**, a click outside it, or going to another page cancels it,
  and the key stays as it was.
- A file not made from a start kit. The page says how many of the game's bones it has; the bones it
  hasn't got stay where they rest. Start from the start kit, and keep its bones' names.
- A file that's too long, or in two parts. Animations can be up to 60 seconds. Blender's "glTF
  Separate" makes a .gltf with a .bin beside it, and the page takes one file: export as glTF Binary
  (.glb).
- Changing **For**. A file made for cats has none of a mouse's bones, so changing **For** puts the
  animation aside; change it back before you leave the page and it comes back. Changing **Where it comes
  from** or **What it does** puts aside what the other choice used, the same way.
- Sharing a mod with one of the game's animations. Whoever adds it needs Clan Mod Studio 0.4.0 or newer.
  An older one leaves each of the game's animations out (its log says "no file chosen yet") and puts the
  mod's others in.

## Undo

Nothing reaches your mod until you press **Save to mod**, and nothing reaches the game until you apply
([what Undo means here](studio.md#what-undo-means-here)).

- Changes you haven't saved: switch to another mod in the Editing mod bar, choose **Switch without
  saving**, and switch back.
- An animation: its **Remove** button, at the foot of its card (press it twice). A file it used stays in
  the mod's folder.
- In the game: remove it, or switch its mod off on the Mods page, and apply again. A replaced animation
  is the game's own again. Nothing of an animation is in your save.
