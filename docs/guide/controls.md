# Controls

The Controls page changes which key, mouse button or controller button does what in the game. You pick a
row, press Change, press the key you want, and save it to a mod.

## What it changes in the game

After **Apply to game**, the new key does the action, however you start the game (from Steam too). The old
key stops doing that action but keeps its other jobs: with Interact on F, E still shows the map's legend. The
game's own prompts and its Controls tab show the new key.

A key can do something already. Then the page says, under the row, what it will stop doing: put Interact on I
and the Inventory row says I no longer opens the inventory. Give that action another key too, or pick a key
the game doesn't use. **Which keys are free?**, lower on the page, lists every key that already does something.

## A five-minute first try

1. Open **Controls**. On the **Interact** row, press **Change**, then press F.
2. The cell reads F, with "was E" beside it, and under it: "F does Interact. E still shows the map's legend."
3. Press **Save to mod** at the top, then **Apply to game** (with the game closed), then **Play**.
4. In the game, walk up to a tunnel: F opens the travel map, and the prompt shows F.
5. Back on the page, press **Add another key** under Interact, then press H. The line says "H does what E does
   while you explore". Save, apply, and both F and H interact.
6. Now try Change on Interact and press I. The cell goes amber, and the Inventory row says I no longer opens
   the inventory. Press **Undo** to put it back on F, as saved.

## What you can and can't do

- **Move an action** (Pounce, Interact, Run, Crouch, Scent tracking, Drop, Talk to a friend, Place a den
  decoration, Return to camp, Reset the camera, Pause menu, Inventory, Quest log, Map, Meow) to a key, a mouse
  button or a controller button. It works in the game. Inventory, Quest log, Map and Meow have no controller
  button in the game, so they stay on the keyboard.
- **Add another key** to an action. It does what the game's key does while you explore, and nothing in menus.
- **In menus**, give Confirm, Back, Previous tab and Next tab another key. The game's own keys keep working,
  but a key you add gives up its own job in menus: add Backspace to Confirm and it no longer goes back (the
  Back row says so). A letter still types on the name screen.
- **Moving and the camera** (W, A, S, D and the arrows) can't be changed by Apply, because the game reads those
  keys itself. Change them under **Moving and the camera**, then start the game with Play with key remaps.bat,
  which is in the studio's folder. Those rows say "needs Play with key remaps.bat".
- **The controller's sticks** can't be changed by a mod at all. Use Steam's controller settings: right-click
  the game in Steam, then Properties, Controller. Stick speed and inverting are in the game's own Settings,
  Player Configuration.
- **Controller presets** (Nintendo layout, Swap bumpers and triggers) swap the buttons for you.
- **Mouse look** turns the camera with the mouse. Its card saves by itself into the Mouse Look mod.

Not tried in the game yet: controller buttons, Mouse 4, Mouse 5 and the wheel. They are made the same way as
the keys that were tried, but nobody has checked them on a real controller or mouse yet. The page marks them
"not tried in the game yet".

Some keys are taken: the mod menu's key (Insert, unless you changed it on Settings and repair) and its
controller button, mouse look's key (F6, while mouse look is on) and F11 (the game's full screen key). The page won't put an action
on them. The Emote wheel's T and an emote's key can take an action, but then they do both while that mod is on.

**Escape, Tab, Enter, Space and Backspace.** When you press Change, the box that opens listens for any key.
Escape closes it without changing anything, and Tab moves between its buttons. To use Escape or Tab
themselves, press Tab until its button is lit and press Enter, or click the button. Enter and Space work as
keys when no button in the box is lit.

## Did it reach the game?

The page shows what Apply will do before you apply: the line under each changed row comes from the same check
Apply runs. After **Apply to game**, the log at the bottom right lists anything about your keys that needs a
second look, in the same words. If a row says "needs Play with key remaps.bat", that change works only when
you start the game with that file. Without the script loader, a banner at the top of the page says so: Get
set up, on the Mods page, installs it.

If a key still does the old thing in the game, check that the mod is on (the Mods page) and that you applied
after saving. If another mod changes the same action, **Also in this build** under the table says which mod
wins: the one that comes later in the list.

## Common mistakes

- **Saving but not applying.** Save to mod keeps your change in the mod; Apply to game puts it in the game.
- **Picking a key that already does something.** Read the line under the row: it says what that key stops
  doing. **Which keys are free?** lists the keys that are used.
- **Expecting W, A, S, D or the sticks to change.** They need Play with key remaps.bat or Steam, as above.
- **Two mods changing the same key.** The later mod wins; turn one off or change one of them.

## Undo

- **Undo** on a row puts back what the mod had for it when you opened it (or last saved it). A row the mod
  already had changed shows **Back to** and the game's key instead, which puts the game's key back.
- A key that's already a second key, or a moving key, can't be used for something else until you remove it
  there: the box that asks for the key says where it is.
- **Back to the game's keys**, at the top of each column, puts every key in that column back. Press it twice.
- **Remove** takes away a second key, or a change listed under For mod makers.
- Nothing reaches the game until you apply, so switching to another mod and back reloads what's saved. After
  an apply, switch the mod off (or change it back) and apply again. More in
  [How Clan Mod Studio works](studio.md#what-undo-means-here).
