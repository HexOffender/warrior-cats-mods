# Controls

The Controls page changes which key, mouse button or controller button does what in the game. You pick a
row, press **Change**, press the key you want, and save it to a mod as `controls.json`.

## What it changes in the game

After **Apply to game**, the new key does the action, however you start the game (from Steam too). A
small helper that runs with the game makes the change, through the [script loader](README.md#script-loader).
The old key stops doing that action but keeps its other jobs: with Interact on F, E still shows the map's
legend. The game's own prompts and its Controls tab show the new key, and the [mod menu](README.md#mod-menu)'s
Overview lists every key you changed ("Interact (was E)" beside F). Nothing is written into your save.

A key can do something already. Then the page says, under the row, what it will stop doing: put Interact
on I, and the **Inventory** row says I no longer opens the inventory. Give that action another key too, or
pick a key the game doesn't use. **Which keys are free?**, lower on the page, lists every key that already
does something.

## A five-minute first try

1. Open **Controls**. On the **Interact** row, under **Keyboard and mouse**, press **Change**, then
   press F.
2. The cell reads F, with "was E" beside it, and under it: "F does Interact. E still shows the map's
   legend."
3. Press **Save to mod**.
4. Close the game if it's open, then press **Play** (top right; it reads **Apply and play** while changes
   wait).
5. In the game, walk up to a tunnel: F opens the travel map, and the prompt shows F.
6. Back on the page, press **Add another key** under Interact, then press H. The line says "H does what E
   does while you explore (Interact)". Save and apply again, and both F and H interact.
7. Now press **Change** on Interact and press I. The **Inventory** row warns that I no longer opens the
   inventory. Press **Undo** to put Interact back on F, as saved.

## What you can and can't do

You can:

- move an action to a key, a mouse button or a controller button, under **Keys while you play**: Pounce,
  Interact, Run, Crouch, Scent tracking, Drop, Talk to a friend, Place a den decoration, Return to camp,
  Reset the camera, Pause menu, Inventory, Quest log, Map and Meow. Inventory, Quest log, Map and Meow
  have no controller button in the game, so they stay on the keyboard;
- give an action a second key with **Add another key**. It does what the game's key does while you
  explore, and nothing in menus;
- give Confirm, Back, Previous tab and Next tab another key, on the **In menus** card. The game's own keys
  keep working, but a key you add gives up its own job in menus: add Backspace to Confirm and it no longer
  goes back (the Back row says so). A letter still types on the name screen;
- swap the controller's buttons with **Nintendo layout** or **Swap bumpers and triggers**, under
  **Controller presets**;
- turn the camera with the mouse, on the **Mouse look** card: **Turn and tilt the camera with the mouse**,
  how fast it turns, the key that switches it off and on in the game, and (in **Tilt limits**) how far
  down and up it tilts. The card saves by itself into a mod of its own, Mouse Look, and needs the script
  loader.

You can't:

- move the moving and camera keys (W, A, S, D and the arrows) with Apply: the game reads those keys
  itself. You can still change them under **Moving and the camera**, but they work only when you start
  the game by double-clicking Play with key remaps.bat, in the studio's folder (keyboard and mouse only).
  That file starts the old key remapper, a helper outside the game that's on its way out: the
  [build log](README.md#build-log) calls it deprecated. Those rows say "needs Play with key remaps.bat";
- change the controller's sticks with a mod. Use Steam's controller settings (right-click the game in
  Steam, then Properties, Controller). Stick speed and inverting are in the game's own *Settings*,
  *Player Configuration*;
- put an action on the mod menu's key (Insert, unless you changed it on Settings and repair) or its
  controller button, on mouse look's key (F6, while mouse look is on), or on F11, the game's full screen
  key. The page refuses them. The Emote wheel's key and an emote's key can take an action, but then they
  do both while that mod is on.

Not tried in the game yet: controller buttons, Mouse 4, Mouse 5 and the wheel, the controller presets,
and changed keys in den decorating, the name screen, cutscenes and minigames. The buttons are made the
same way as the keys that were tried, but nobody has checked them on a real controller or mouse yet. The
page marks them "not tried in the game yet" ([what's been checked](../verified.md#not-yet-confirmed-in-game)).

When you press **Change**, a box asks for the key. Escape closes it without changing anything, and Tab
moves between its buttons. To use Escape, Tab, Enter, Space or Backspace themselves, click its button in
the box. For a mouse button, click in the box's mouse area, or turn the wheel there.

## Did it reach the game?

- Under the **Editing mod** bar, one line says whether your saved keys are in the game: "In the game since
  your last Apply." or "Saved, not in the game yet: Apply to game." (also after a game update, when Apply
  has to be made again).
- A mod made for an older version of the game (an older [game build](README.md#game-build)) is left out by
  Apply, and the line says so; the Mods page says how to use it anyway.
- Before you apply, the line under each changed row says what Apply will do: it comes from the same check
  Apply runs. After **Apply to game**, the build log lists anything about your keys that needs a second
  look, in the same words.
- If you press **Play** with changes that need Play with key remaps.bat, the build log stays open and
  says so.
- Without the script loader, a banner at the top of the page says "Key changes need the script loader."
  **Get set up**, on the Mods page, installs it.
- If a key still does the old thing in the game, check that the mod is on (the Mods page) and that you
  applied after saving. If another mod changes the same action, **Also in this build**, under the table,
  says which mod wins: the one that comes later in the list.

## Common mistakes

- Saving but not applying. **Save to mod** keeps your change in the mod; **Apply to game** puts it in the
  game.
- Picking a key that already does something. Read the line under the row: it says what that key stops
  doing. **Which keys are free?** lists the keys that are used.
- Expecting W, A, S, D or the sticks to change. They need Play with key remaps.bat, or Steam's settings,
  as above.
- Two mods changing the same key. The later mod wins; switch one off or change one of them.

## Undo

- **Undo** on a row puts back what the mod had for it when you opened it (or last saved it). A row the mod
  already had changed shows a Back to button with the game's key ("Back to E"), which puts the game's key
  back.
- **Remove** takes away a second key, or a change listed under **For mod makers**.
- **Back to the game's keys**, at the top of each column, puts every key in that column back. Press it
  twice.
- A key that's already a second key, or a moving key, can't be used for something else until you remove
  it there: the box that asks for the key says where it is.
- Nothing reaches the game until you apply. To drop everything since you last saved, pick another mod in
  the **Editing mod** bar, choose **Switch without saving**, and switch back. After an apply, switch the
  mod off (or change it back) and apply again. More in
  [How Clan Mod Studio works](studio.md#what-undo-means-here).
