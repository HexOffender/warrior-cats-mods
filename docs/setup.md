# Setting up Clan Mod Studio

What Clan Mod Studio needs, where it keeps your files, how to update it, what it puts in the game, and how
to do Get set up's steps by hand. Most people never need this page: **Get set up**, on the Mods page,
does all of it ([the Mods page's guide](guide/mods.md)), and the [README](../README.md#start-here) has the
short version.

## What it needs

Clan Mod Studio sees to all of these: its launcher to Python, and Get set up to the rest.

- **Windows, and the Steam version of the game.** *Warrior Cats: Clans of the Forest* is Steam app
  3960600, made with Unreal Engine 5.7. Clan Mod Studio looks for it in your Steam libraries; when it
  can't find it, Get set up asks for its folder (in Steam, right-click the game, then *Manage*, then
  *Browse local files*).
- **Python 3.10 or newer.** Clan Mod Studio is written in Python, which is free. `Clan Mod Studio.bat`
  and `Play with key remaps.bat` look for it (`py -3`, `python` and `python3`, then where Python puts
  itself for one user).
  - **Without it,** they offer to install Python 3.13 with winget (Windows' own installer), or open
    python.org (in its installer, tick "Add python.exe to PATH"). The Microsoft Store's Python works too.
  - **Nothing else to install:** no packages, no DLLs. [CONTRIBUTING.md](../CONTRIBUTING.md) says why.
- **UE4SS, the [script loader](guide/README.md#script-loader)**, free and open source. It runs small
  helpers inside the game, for coat, pattern, marking and eye-button colours, your cat's own colours,
  mouse look, key changes, tweaks, the mod menu, emotes, models on cats, and scripts from mods.
  - **Installing it:** Get set up's **Install it** downloads the `UE4SS_v*.zip` from UE4SS's
    [experimental-latest release](https://github.com/UE4SS-RE/RE-UE4SS/releases/tag/experimental-latest)
    (about 9 MB; Clan Mod Studio is tried with `UE4SS_v3.0.1-1181-g83330635.zip`) and puts it in the
    game.
    **Use a .zip I downloaded…** takes that .zip from you instead. The game has to be closed.
  - **How it's set up:** its debug console windows are off. Its cheat-manager enabler is off too,
    because the Menu pages mod's Cheats page does that job and can switch cheats off again.
  - **The game's own command window:** UE4SS's console enabler (`ConsoleEnablerMod`) is on, so `~` or
    F10 opens the game's console. **The game's own command window**, under **Options** on the Settings
    and repair page, switches it from the next time the game starts (so does the command line's
    `console off`).
  - **Removing it:** with the game closed, delete `dwmapi.dll` and the `ue4ss` folder from
    `<game>\Wrc\Binaries\Win64`.
- **Nothing else.** The game's files are compressed with Oodle's Kraken, and wcmods decodes them itself
  (`wcmods/formats/kraken.py`, a Python port of the open-source [ooz](https://github.com/powzix/ooz)
  decoder, GPL-3.0). It's pure Python, so it takes a few seconds for a big texture or the item table.
  `"oodle_dll"` in `wcmods.json`, set to an `oo2core_*_win64.dll` that another installed game ships,
  makes that about a hundred times faster, which only shows when extracting many files.

## Your files

Your mods, wcmods' settings and your backups are in a folder of your own, `%LOCALAPPDATA%\WCMods`
(`C:\Users\<you>\AppData\Local\WCMods`), not in Clan Mod Studio's folder, so updating Clan Mod Studio never
touches them. **Open the folder**, under Backups and repair on the Settings and repair page, opens it.

- `mods\`: your mods, one folder each.
- `wcmods.json`: wcmods' own settings. Where the game is, whether mods may run code, the mod menu's key,
  controller button and size, and what's installed. Get set up and Settings and repair edit it for you,
  and [formats.md](formats.md#wcmodsjson) lists every key. If it's ever damaged, it's set aside as
  `wcmods.json.broken-<date and time>`, and the studio starts afresh and says so.
- `backups\`: your save backups, and the mods you removed or replaced (`backups\mods`).
- `save-changes.json`: the changes made to your save, so each one is made once.
- `last-apply.log`: what the last Apply or Play did (the studio's **Last apply**).
- `studio.log`: the details behind a "Something went wrong" message, for whoever helps you.
- `cache\downloads`: the last download of each of the mods that go with Clan Mod Studio.

Setting the `WCMODS_DATA` environment variable to a folder keeps them there instead (Clan Mod Studio's own
folder, say, to keep everything in one place).

Your save itself is the game's, in `%LOCALAPPDATA%\Wrc\Saved\SaveGames` (`"save_dir"` in `wcmods.json`
when it's somewhere else).

## Updating Clan Mod Studio

Unzip a new download over the old folder, or `git pull` if you cloned it. Either way only Clan Mod Studio
changes. Your files stay as they are, the mod menu's settings among them (they're in `wcmods.json`).

- **While the studio is open:** **Restart the studio** shows at the top. Save your changes, press it,
  and a fresh studio opens in a new window while the page comes back by itself.
- **A mod made for a newer Clan Mod Studio** (its mod.json's `"wcmods"`) is left out until you update,
  and its card says so.
- **Moving in from an older version:** older versions kept `mods\`, `wcmods.json` and `backups\` in Clan
  Mod Studio's own folder. The first start after updating moves them into your files' folder; then press
  **Apply to game** once, so the game finds your mods there. Nothing is lost when that folder has some
  already: a mod or a setting that's there stays, and yours goes to the backups (a setting only yours
  has is kept too).
- **If `git pull` won't start:** it may say your changes to `mods/mod-menu` would be overwritten. That's
  because older versions saved the mod menu's settings there. Move the `mod-menu` folder out of `mods`
  (to your desktop, say), pull again, then move it back into `mods`. The next start takes its settings
  into `wcmods.json`.
- **The mod menu's pages about the game** are a mod of their own now, Menu pages. Get set up offers it
  with the other mods that go with Clan Mod Studio; until it's in, the menu has its Overview, your mods'
  pages and its Tools.
- **After a game update,** [updating.md](updating.md) says what wcmods does by itself and what a mod
  "made for an older version" means.

## Setting it up by hand

Everything Get set up does can be done without it:
- **The game's folder:** `"game_dir"` in `wcmods.json`, when wcmods can't find the game in your Steam
  libraries. Get set up's **Where's the game?** writes it. When Steam starts another copy of the game than
  the one your mods go into, the Mods page says so, and **Use Steam's copy** fixes it.
- **A save:** start the game once and get into the forest. The studio backs the save up as soon as there
  is one (**Back up now** on Settings and repair, or the command line's `backup`, makes another).
- **The script loader:** as above. Unzipping UE4SS's .zip into the game yourself, so that `dwmapi.dll`
  and the `ue4ss` folder land in `<game>\Wrc\Binaries\Win64`, works too, but leaves UE4SS's settings as
  they ship: **Install it** also turns its debug console windows and its cheat-manager enabler off.
- **[Mods that run code](guide/README.md#code-mods):** `"allow_code_mods": true` in `wcmods.json`.
  Only for mods from people you trust.
- **The mods that go with Clan Mod Studio:** download each one's .zip from its releases page on GitHub
  and drop it on the Mods page, or use the command line's `addons add <id>` ([cli.md](cli.md#mods)).
- **Putting your mods in the game:** the command line's `install` does what **Apply to game** does
  ([cli.md](cli.md#mods)).

## What an install puts in the game

The game's own files are never changed. Everything an install writes has a name of its own:
- `<game>\Wrc\Content\Paks\~mods\zzz_WCMods_*`: the mod pak, with your mods' game data (tables, text,
  pictures, models, animations), and mods' own cooked paks under the same kind of name.
- `<game>\Wrc\Binaries\Win64\ue4ss\Mods\WCMods*`: wcmods' helpers, and each script or C++ mod, as UE4SS
  mods of their own.
- `<game>\Wrc\Binaries\Win64\ue4ss\Mods\shared\WCMods*`: the shared Lua modules scripts use.

**Take all mods out of the game** (Settings and repair), or the command line's `uninstall`, removes all
of those. Changes to your save are different: they're written into your save, after a backup, and stay
there when the mods come out. A save backup puts the save back.

Before it writes anything, an install builds every mod that's on. If one fails, nothing goes in, since
installing would remove what that mod put in the game before: fix it or switch it off, or choose **Apply
the rest anyway** (`install --force` on the command line).

## Looks and gameplay

The game rolls a cat's traits (Ambitious, Brave, Wise, Energetic, Curious, Patient) from its body, ear
and face shape, and its stats come from its Clan. Your save stores which *slot* each option uses (a
numbered colour or shape), not the colour itself.

- **Palettes change only looks.** They redraw a slot; your cat keeps the same slot, so its traits and
  stats don't change. The names the game suggests follow the slot.
- **Game data and save changes change how the game plays.** That's what they're for. A build warns when a
  Game data change or a replacement file touches the online den-visit tables (`OnlineGifts.csv`,
  `VisitRewards.csv`), the body, ear and face odds that choose traits, or the quest and talk tables (a
  wrong value there can stop a quest). A replacement file that isn't on the list of files known to change
  only looks gets a warning too.
