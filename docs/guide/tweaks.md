# Tweaks

## What it changes in the game

Small changes to how the game plays, ticked on one page: stamina that stays full, a key that heals your
cat, a clock that stands still, and a fresh-kill pile that never runs low.

While you play, a small helper that comes with the studio keeps the tweaks you ticked. Twice a second it
tops up your cat's stamina, puts the clock back to your hour and fills the fresh-kill pile back up to your
number; your heal key fills your cat's health and stamina. The [mod menu](README.md#mod-menu) gets a
Tweaks page, to change them while you play.

How it gets there: the tweaks are saved as `tweaks.json` in your mod, and **Apply to game** or **Play**
puts them in. The helper runs with the [script loader](README.md#script-loader), which Get set up, on the
Mods page, installs. The helper is the studio's own, so nothing has to be allowed under
[mods that run code](README.md#code-mods). With nothing ticked, nothing goes in the game.

## A five-minute first try

1. Open **Tweaks**.
2. Tick **Heal my cat with a key** and choose a key in the list beside it (F5, say).
3. Tick **Keep my cat's stamina full**.
4. Press **Save to mod**.
5. Press **Apply and play** at the top right, and go into the forest.
6. Run for a while: the stamina bar stays full.
7. After a fight has cost your cat some health, press F5 in the forest: its health is full again.
8. Open the mod menu (Insert): its Tweaks page has the same rows, to change while you play.

## What you can and can't do

You can:

- keep your cat's stamina full (**Keep my cat's stamina full**);
- heal your cat, health and stamina, with a key from F1 to F9 (**Heal my cat with a key**);
- hold the time of day at an hour (**Hold the clock at**): 06:00 is morning, 21:00 night;
- keep the camp's fresh-kill pile at least as full as you say (**Keep the fresh-kill pile at least**), out
  of 100: 90 and over is Full, 50 Good, under 25 Critical;
- change any of them in the game, on the mod menu's Tweaks page. Its "Save" writes them into your mod, so
  the next Apply keeps them.

You can't:

- put the heal on F10 or F11 (the game's own: its command window and full screen) or F12 (Steam's
  screenshot key);
- put it on a key something else in your mods has you press: the mod menu's key, mouse look's on and off
  key when a mod of yours has mouse look (F6 unless you changed it), or a key a remap on the Controls page
  uses. The page leaves those out, names them under the row, and warns if your mod's key is one of them;
- skip the story's scenes yet: nobody has checked that a skipped scene still does what it does at its end
  (a quest step, a ceremony's new rank), so that tweak waits, and the page doesn't show it;
- use the heal key while another window is in front: it listens to the game's own keys;
- turn on god mode or change the game's speed here: those are cheats, on the mod menu's Cheats page, which
  comes with [Menu pages](README.md#menu-pages). With Menu pages in your mods, the Settings and repair page
  also has **Cheats on when the game starts**.

Not checked in the game yet: Tweaks are made from an example script, Game Tweaks, whose stamina, clock and
fresh-kill pile were seen working, but they haven't been run in the game as Tweaks. Least sure are the
heal key and the mod menu's Tweaks page with its "Save".

## Did it reach the game?

- In the game, open the mod menu (Insert): its Tweaks page, under Mods, shows every tweak, with yours
  switched on. No Tweaks page means the game hasn't got them: close it, press **Apply to game**, then
  **Play**.
- On the Mods page, your mod's card has a Tweaks chip, and the status at the top of the studio says
  "Game up to date" once they're in.
- The mod menu's Log page (under Tools) has a line like "[Tweaks] on: stamina full, heal on F5" from when
  the game started.

## Common mistakes

- No script loader: the page says "Needs the script loader". Get set up, on the Mods page, installs it.
- The heal key does nothing: the game's window wasn't in front, or the key is the mod menu's (then Apply
  leaves the heal out, and the [log](README.md#build-log) says so). Pick another key, save, and apply.
- The heal key does something else too: another of your mods uses that key, and the log after Apply
  says which. An emote's key from the Animations page isn't checked, so give the heal a key no emote has.
- The clock jumps: it's put back to your hour twice a second, not stopped, so anything in the game that
  sets another time (a scene, say) shows for a moment.
- The story doesn't go on: with the clock held, the day never turns, so a story step that waits for
  night or the next day may wait for ever. Untick **Hold the clock at** (or switch it off on the mod menu's
  Tweaks page) until the story has moved on.
- A change made in the game is gone after an Apply: press "Save" on the mod menu's Tweaks page
  before you close the game, which writes it into your mod. Otherwise the next Apply puts the studio's
  tweaks back.
- Two mods with tweaks: a tweak ticked in either one is on. Where both set the same one (two heal keys,
  two hours), the mod with the higher **Priority** wins (on its card on the Mods page, under **More**).

## Undo

- Before saving: untick the box, or switch to another mod in the Editing mod bar and choose
  **Switch without saving**.
- After saving: untick what you don't want, **Save to mod**, then **Apply to game**. Or switch the mod off
  on the Mods page and apply.
- In the game: the mod menu's Tweaks page has "Back to installed", which puts back what the last Apply put
  in.
- Your save: a tweak writes nothing into it, but the game saves the fresh-kill pile as it is at its next
  save. To keep the pile you had, back up first (**Back up now**, on the Settings and repair page).

For the file this page writes, see [tweaks.json](../formats.md#tweaksjson).
