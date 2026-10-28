# Animations

The Animations page puts animations on your cat and the animals: one of the game's own, or one you made
in Blender. You don't need Blender to start: the game's own yawns, stretches and photo poses are all there.

## What it changes in the game

Each animation does one of three things:

- **An emote on my cat.** A key you choose (or a controller button) plays it on your cat, and the mod
  menu gets an Emotes page with a button for it. It plays over what your cat is doing, where it stands;
  the key again, or walking off, stops it.
- **Plays where the game plays one of its own.** Every cat (or every animal of that kind) plays it
  wherever the game played the one it replaces: a trot of your own, say. It's fitted to that one's
  length, and its footsteps stay where they were.
- **Only for scripts and stories.** A script or a mod's story plays it on a cat or an animal.

Emotes and animations for scripts need the script loader in the game, which **Get set up**, on the Mods
page, installs.

## A five-minute first try

1. Press **Add an animation** and name it *Yawn*.
2. Under **Where it comes from**, keep **One of the game's animations**, and choose **Yawn** from the
   list (it's under Everyday).
3. Under **What it does**, keep **An emote on my cat**. Press **Press a key…**, then F7.
4. Press **Save to mod**, then **Apply and play**.

In the forest, F7 makes your cat yawn, and F7 again stops it. The mod menu (Insert opens it, unless you
changed its key) has an Emotes page with a Yawn button.

A second try, every cat trotting with the run: add another animation, choose **Run** from the game's
list, then **Plays where the game plays one of its own**, and choose **Trot** under **In place of**.
Save, and apply.

## What you can and can't do

You can:

- use any of the game's animations for that animal. The everyday ones come first by plain names (Yawn,
  Stretch, Shake, Sniff, Play, Sleep, Meow, Get up, Walk, Trot, Run, Idle), then the photo poses by the
  game's own names for them, then all of them by the game's technical names;
- see one on your cat before you choose it: **Try it on my cat** plays it in the game, while the game
  runs with your cat in the forest. It needs mods that run code allowed (Settings and repair);
- put an emote on a key or a controller button, with the claws out, looping, faster or slower;
- make animations for mice, rats, rabbits, squirrels, birds, foxes, badgers, dogs and snakes too, from
  their own animations;
- make your own in Blender: **Start kits (for Blender)**, at the top of the page, saves an animal rigged the
  game's way, and **A file I made in Blender** takes the file you export, up to 60 seconds long;
- stop an emote the Emote wheel started with the emote's own key.

You can't, yet:

- move your cat with an animation: it plays where the cat stands;
- give only your cat its own walk or idle: every cat shares the game's;
- swim, fly or climb: those would be new ways of moving, not animations;
- add a sound, or move the face (blinking, the pupils);
- use the game's animations that are added on top of another pose (like the second meow): they can't
  play on their own, so the list leaves them out.

## Did it reach the game?

After **Apply to game**, each animation in the list gets a chip: **In the game** (with its key, for an
emote), or **Left out**. The animation's own page says why one was left out, and a line at the top sums
it up: "In the game: Yawn (F7), Flap; left out: Wave (nothing chosen for it to play yet)". When you open
the studio again later, the chips are the last Apply's, and say when it was. The whole story is in
[the log](studio.md#the-log), under **Last apply**.

In the game, press the emote's key, or open the mod menu's Emotes page. A replacement shows wherever the
game plays the one it replaced.

## Common mistakes

- **Nothing chosen yet.** An animation needs one of the game's, or a file. Until it has one, the list says
  "needs an animation" and it's left out of the game; the rest of the mod still goes in.
- **A key something else uses.** F6 turns mouse look on and off unless you changed its key, F11 is the
  game's full screen, and Insert opens the mod menu. Two emotes on one key: only one of them would play.
  The key dialog says so when you press a key another emote has.
- **Leaving the key dialog.** Escape, **Cancel**, a click outside it or going to another page cancels it,
  and the key stays as it was.
- **A file that's too long, or in two parts.** Animations can be up to 60 seconds. Blender's "glTF
  Separate" makes a .gltf with a .bin beside it, and the page takes one file: export as glTF Binary
  (.glb).
- **Changing For.** A file made for cats has none of a mouse's bones, so changing For puts the animation
  aside; change it back before you save or leave the page and it comes back. Changing **Where it comes
  from** or **What it does** puts aside what the other choice used, the same way.
- **Sharing a mod with one of the game's animations.** Whoever adds it needs this version of Clan Mod
  Studio or newer (0.4.0); an older one leaves that mod's animations out.

## Undo

Nothing reaches your mod until you press **Save to mod**, and nothing reaches the game until you
apply: see [what Undo means here](studio.md#what-undo-means-here).

- **Remove** takes an animation out (press it twice). A file it used stays in the mod's folder.
- To take an animation out of the game, remove it or switch its mod off on the Mods page, and apply
  again. A replaced animation is the game's own again.
