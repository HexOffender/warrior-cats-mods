# When the game updates

Steam updates *Warrior Cats: Clans of the Forest* by itself, so a player can have a newer build than
wcmods, or a mod, was made for. wcmods notices, works out what it can by itself, and keeps mods
that weren't made for the new version out of the game until they're updated. The code is
`wcmods/exe/gamebuild.py` (builds and mods) and `wcmods/exe/signatures.py` (finding what moved).

## For players

When Clan Mod Studio sees a build it wasn't checked on, it says "Game updated" at the top, and the
Mods page says what that means:

- **wcmods' own parts:** wcmods looks through the new game for the values it reads directly (your
  cat's health and stamina, level and stats, the clock, the fresh-kill pile, fight stats). Anything
  that moved is followed, and anything it can't find again, or can't vouch for, is switched off
  instead of guessed: the mod menu shows those values as not available. This takes under a minute,
  once per update, and the next Play or Apply puts the result in.
- **Your mods:** a mod made for an older version of the game is left out until its maker updates
  it, and so is a mod that needs it. Its card says so. **Use it anyway…** puts it back in, for this version only, after a warning:
  it may not work, or may behave unpredictably (a broken page, odd values, a crash). Back up your save
  first. After the next update it's left out again.

`python wcmods.py game build` says the same on the command line. `python wcmods.py allow-outdated
<mod>` uses a mod anyway (`--off` stops), and `python wcmods.py status` marks such mods.

To choose when updates happen, set the game's Updates option in Steam (right-click the game,
Properties, Updates) to "Only update this game when I launch it".

## For mod makers

`mod.json` says which builds of the game a mod was made for:

```json
{ "name": "Cool Tweaks", "version": "1.3", "game_builds": [24847281, 26184573] }
```

After the game updates, try your mod on the new build. If it works, add the build's number
(`python wcmods.py game build` shows it) and share the new version. A mod without `game_builds` was
made for build 24847281, like every mod made before the list existed.

## For wcmods: the signatures

`game.HIDDEN` lists members the game doesn't reflect, found by reverse-engineering build 24847281:
health at +0x10C in a resource component, the clock at +0x438 in the game state, and so on. They're
offsets inside objects, so ASLR doesn't move them (the exe is relocated on every launch, and
everything here works in RVAs). A rebuild that adds a member to a class does move them.

`wcmods/exe/signatures.json` keeps, for each class:

- **Its size,** from the class's registration call. The call is
  `GetPrivateStaticClassBody(..., sizeof(T), alignof(T), ..., ClassConstructor, ..., SuperClassFn)`:
  the name's reference leads to it, and `[rsp+20h]` is the size. If the size changes, the layout
  changed.
- **Its own code:**
  - the virtual functions it overrides: its vtable, from the constructor the registration passes,
    against its parent's;
  - its native UFunctions (its `StaticRegisterNatives` table);
  - the functions those call;
  - the functions that ask for the class (call its `StaticClass` or read its `UClass*`);
  - a monitored parent's code, for members the class inherits.

  A function is all of it: the exe's function table (`.pdata`) gives many functions in parts, the
  first with the prologue and the rest chained to it, and `pe.Image.function_at` joins them.
- **Anchors:** functions the reverse-engineering notes tie to a class whose own code hardly touches its
  members, such as `0x1417D8010`, which builds a fighter's stats, or code of an unmonitored parent's
  (the level component's level and cap are `USwtQuestLevelComponent`'s). Each is found in a new build
  by a pattern of its first instructions that's unique in the whole exe.
- **Signatures:** short byte patterns around the instructions that read or write each member. Every
  displacement, branch target and relocated address is a wildcard, and the members' offsets are
  captures. A pattern only has to be unique among the class's code, so it stays short and survives
  changes around it. Not every instruction at a member's offset is the member: one through a stack
  address or a global's pointer (a local, a singleton's field), or one wider than the member (a
  pointer, a vtable slot: `call [rax+0x1C8]`), isn't made a signature.

`check()` on another exe finds each class again the same way, compares its size, and reads each
member's offset out of the code its signatures match. The sites vote on each member:

| Status | Meaning | What wcmods does |
|---|---|---|
| same | the signatures agree it hasn't moved | uses it |
| moved | two or more agree on a new offset, inside the class and aligned | uses the new offset |
| kept | no signature matched, but the exe is the one the signatures were made on, or the class is the same size, another of its members was found where it was, and none moved or disagreed | uses it |
| unsure | one site alone says it moved | leaves it out |
| conflict | the signatures disagree, the offset can't be one, or two members land on one offset | leaves it out |
| lost | no signature matched and it can't be kept | leaves it out |

`gamebuild.layout()` runs the check once per build. It keeps the result in `cache/layout-<key>.json`,
where the key holds the build, the exe's size and time, and a hash of `game.HIDDEN` and
`signatures.json`, so a new wcmods works it out again. The build then gives WCModsGame those offsets
(`game.lua(offsets)`). A member that's left out simply doesn't exist in the game, so reading it gives
nil and the menu's pages say it's not available.

The check never stops a build. If it fails on an exe unlike any wcmods knows, or there's no exe to read,
every member is left out, and it's tried again next time. The install records the build and the key,
so after an update Play and Apply make the install again even when no mod changed.

On build 26184573 (patch 1.1; `signatures.json` was made on it, last on 2026-10-28) the signatures
confirm 34 of the 45 values directly (the number of signatures in brackets):
- the resource component's Value (3), Max (1) and Scale (1);
- stamina regen (1);
- the level component's level (4), level cap (3, `WCM_LevelShown`), Prowess (3), Strength (4),
  Resilience (6), Instinct (4), Agility (2) and Stamina (2);
- the fresh-kill pile's timer (4) and decay time (3);
- the clock (2);
- the combat component's Stance (2), Team (3), Stamina (2), MoveCount (3), Clan (3) and Level (4);
- the status component's Status (5), StatusRounds (3), SelfCureChance (2) and PoisonDamage (1);
- the detection component's ConeAngle (1), ConeDistance (4), SoundRadius (3), SoundSpeed (1),
  ProximityDistance (3), WalkSpeedRoaming (2), ZoneEntryDistance (3), ZoneExitDistance (1) and
  ReactToChase (1).

The rest have no signature of their own: ResourceType, the combat component's stats, preset damage and
AI tier, and three of the detection component's senses. Their classes' code doesn't touch them in a way
that can be told apart, and the stat getters share one shape for all six stats. They're kept when their
class's signed members are found where they were; a same-size reorder of the class's other fields can't
be seen this way. Every class has signatures: `game signatures make` refuses to write a class with none
(it would be switched off by every update, as the level component was until 2026-10-28; see
docs/reverse-engineering.md, "Game updates").

### Commands

```bash
python wcmods.py game build
```

```bash
python wcmods.py game signatures check
```

```bash
python wcmods.py game signatures make
```

- **`game build`:** the installed build, what moved, and the mods made for older ones. `--refresh`
  looks again.
- **`game signatures check`:** checks the installed exe, or `--exe <path>`, against the signatures.
  `--json` prints all of it as JSON (what it looked at goes to stderr).
- **`game signatures make`:** writes `wcmods/exe/signatures.json` from the installed exe, or `--exe <path>`
  with `--build <number>`. Only do this on a build whose `game.HIDDEN` offsets have been confirmed in
  game. It writes nothing when a class gets no signature at all ("not written: no signatures for ..."):
  give that class anchors in `signatures.ANCHORS` first.
- **`WCMODS_GAME_BUILD=<number>`:** makes wcmods act as if that build were installed, to try what an
  update does without one.

The decoder (`wcmods/exe/x64.py`) is checked against the exe's own function table: it decodes 561,065 of
its 563,121 functions exactly to their end (99.6%). The rest hold switch jump tables inside their code,
which aren't instructions.

### When the game updates: checking it

1. Run `python wcmods.py game build` and `python wcmods.py game signatures check --json`.
2. For each member reported moved, lost or in conflict, confirm the offset in game: `wcmods agent`
   runs Lua, and `tools/re/memscan.py` and `peek` find known values in memory. Update `game.HIDDEN`.
3. Run `python wcmods.py selftest` and `python wcmods.py agent test` on the new build.
4. Remake the signatures on the new build (`game signatures make`), set `gamebuild.VERIFIED_BUILD` to
   it (`game.HIDDEN` holds one layout, so it's one build), and note it in `docs/reverse-engineering.md`.
5. Add an `ANCHORS` entry for any class `make` says has no signatures, so it can be found automatically
   next time.
