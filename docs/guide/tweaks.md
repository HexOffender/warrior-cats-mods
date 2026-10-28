# Tweaks

Small changes to how the game plays, ticked on one page: stamina that stays full, a key that heals your cat, a
clock that stands still, a fresh-kill pile that never runs low. No code, and nothing to allow.

## What it changes in the game

While you play, a small helper that comes with the studio keeps the tweaks you ticked: twice a second it tops up
your cat's stamina, puts the clock back to your hour and fills the fresh-kill pile back to your number; and your
key fills your cat's health and stamina. The tweaks are saved as `tweaks.json` in the mod on the **Editing mod**
bar (My mods, to begin with), and go in the game with **Apply to game** or **Play**, like every Make page's. With
nothing ticked, nothing goes in the game.

## A five-minute first try

1. Open **Tweaks**.
2. Tick **Heal my cat with a key** and pick F5.
3. Tick **Keep my cat's stamina full**.
4. Press **Save to mod**.
5. Press **Play** (top right) and go into the forest.
6. Run until you'd expect your stamina bar to drop: it stays full. Take a fall or a fight, then press F5: your
   cat's health is full again.
7. Press Insert for the mod menu: its Tweaks page has the same rows, to change while you play.

## What you can and can't do

You can:

- keep your cat's stamina full while exploring;
- heal your cat (health and stamina) with a key from F1 to F9;
- hold the time of day at any hour;
- keep the camp's fresh-kill pile at least as full as you say (out of 100);
- change all of them in the game, on the mod menu's Tweaks page, whose Save keeps them for next time.

You can't:

- put the heal on F10 or F11 (the game's own: its command window and full screen), F12 (Steam's screenshot
  key), or a key your mods already use: the mod menu's, mouse look's on and off key (F6 unless you changed it),
  a key a remap on the Controls page uses. The page lists the ones it leaves out, and says so if the key your
  mod has is one of them;
- skip the story's scenes yet: it hasn't been checked that a skipped scene still does what it does at its end
  (a quest step, a ceremony's rank), so it waits for that;
- use the heal key while another window is in front: it listens to the game's own keys, as the game does;
- end a fight, or win one, from here: cheats are on the mod menu's Cheats page, with Menu pages (Get set up adds
  it), and "Cheats on when the game starts" is on the Settings and repair page.

## Did it reach the game?

- In the game, press Insert: the mod menu's Tweaks page lists what's on. If there's no Tweaks page, the game
  hasn't got them: close it, press **Apply to game**, then **Play**.
- The mod's card on the Mods page says "Tweaks", and the status at the top of the studio says "Game up to date"
  once they're in.
- The log (the mod menu's Log page, under Tools) has a line "[Tweaks] on: ..." listing them when the game starts.

## Common mistakes

- The heal key does nothing: the game's window wasn't in front, or the key is the one another mod or the mod
  menu uses. Pick another key, save, and Apply.
- The clock moves anyway: **Hold the clock at** is ticked, but the hour box is what it holds; a scene of the story
  can set the time for itself, and the tweak puts it back half a second later.
- The story doesn't go on: with the clock held the day never turns, so a step of the story that waits for the
  next day (or for night) waits too. Untick **Hold the clock at** (or untick it on the mod menu's Tweaks page)
  until the story has moved on.
- The heal key also does something else: it's a key another of your mods uses (Apply says which). Pick another
  on the Tweaks page; on the mod menu's own key, the heal is left out until you do.
- A change made on the mod menu's Tweaks page is gone after an Apply: press Save on that page before closing the
  game, so it's written into the mod; otherwise the studio's tweaks go in again.
- Two mods with tweaks: for each tweak, the mod with the higher priority (its card's More, Priority) wins.

## Undo

- Before saving: untick the box, or switch to another mod on the **Editing mod** bar and leave the changes behind.
- After saving: untick what you don't want, **Save to mod**, then **Apply to game**. Or switch the mod off on the
  Mods page and apply.
- In the game: the mod menu's Tweaks page has "Back to installed", which puts back what the last Apply put in.
  Nothing a tweak does changes your save on its own, but the game saves what it holds at its next save (a full
  pile, the hour): back up first (Settings and repair, **Back up now**) if that matters to you.
