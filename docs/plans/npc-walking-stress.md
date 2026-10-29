# Walking NPCs: stress test and limits

What `Game.npcs.spawn` / `npc:walkTo` do with many cats at once, measured in the real game with the agent controller
(2026-10-28, forest, sandbox build). The probe is `docs/plans/npc-walking-stress.lua` (`STRESS_START(n)`, then
`STRESS_REPORT()`, then `STRESS_CLEAN()`): `n` cats with random colours, size and eyes, in these behaviours:
random destination, back and forth, a four-point route there and back, a loop, `avoid = false`, an unreachable
goal (60 000 cm off the nav mesh), interrupted by `stop()` / `moveTo()` / another `walkTo`, pairs walking head on,
and one cat crossing the player's cat. Speeds 90-450 cm/s, radii 15-120.

## Numbers (60-75 s per run)

| | 0 cats | 10 cats | 50 cats |
|---|---|---|---|
| spawned | | 10 / 10 | 50 / 50, none lost |
| walks: arrived / blocked / cancelled | | 14 / 7 / 1 | 125 / 37 / 6 (136 / 37 / 6 after 2 min) |
| frame time, mean (p95, max) | 16.7 ms (16.7, 16.7) | 17.2 ms (16.7, 30.7) | 20.5 ms (21.8, 33.4) |
| frames per second | 60 | 58 | 49 |
| Lua sampling pass (50 positions + 1225 pair distances) | | 0.3 ms | 1.6 ms |
| closest two cats / pair-samples under 40 cm | | 43 cm / 0 | 3 cm / 108 of about 160 000 |
| cats that never moved | | 0 | 6 (3 unreachable, 2 head on, 1 `avoid = false`: all ended `blocked`) |

- The cost is about 0.07 ms a cat per frame (movement, path following, RVO), nearly all the game's. That is a
  rough figure: the 0-cat run sits on the game's 60 frames a second cap, so the frame time it's taken from
  isn't the frame's real cost. wcmods' own per-tick watch (`walkWatch`, every 0.1 s) is a few traces and a distance a cat: not measurable next to it.
- Blocked walks are the intended ones (unreachable goals, `avoid = false` into rocks) plus goals on a ledge the nav
  mesh reaches but the cat can't climb to, or in a pocket a path leads into and the capsule won't enter.
- Overlaps are brief (a pass-by under RVO), not pile-ups; nothing got stuck inside another cat.
- Cleanup: all 50 gone one frame after `remove()` (the game's own five walking cats are all `FindAllOf` still
  finds). After a level change all 50 came back, each with its controller. No UE4SS log errors in any run.
- Recommended: up to 50 walkers is fine; keep them to ones that matter (about 30 in view) as every walker also
  loads the game's navigation. Don't give many cats the same goal (they bunch up at it).

## What was wrong, and what was changed

- **The game aborted after a few minutes with a spawned cat** (`Abort signal received` from inside UE4SS, 87-240 s
  after launch; with no cats, none in 5.5 minutes; idle cat, 87 s). The cat's own AI logic (its behaviour tree,
  `Controller.BrainComponent`, running) is the likely cause: with `StopLogic` called when it spawns, a cat soaked
  for over ten minutes with no abort. Not proven (the dump only shows UE4SS frames), but spawn now stops it, since
  `walkTo` is all that moves the cat. (Brain stopped or running made no clear difference to walking.)
- **Walkers stalled all over**: the nav mesh is built for a 1 cm wide agent, the cat is 25 cm wide and nothing
  visible is in its way, yet it stops at places (a seam between two nav pieces, grass, a trigger volume). The
  old check (not closer to the goal in 3 s) also misread a path that goes round something as a stall. Now:
  `walkTo` counts a stall (not moved 15 cm in a second, the move idle, or no new closest distance in 8 s), steps 150
  cm to a clear side and asks for the path again, up to 5 times in a row (a new closest distance resets the
  count) before `"blocked"`. Arrivals in the 50-cat run went from about 0 to 125 (single cat 1 of 9 to 6 of 9).
- A single cat in the open still ends `blocked` on goals a few hundred cm across some spots (it paths into an
  invisible edge there): ask `"blocked"` to mean "try something else".

## Not known

- Why the cat stops at those spots (an edge of the nav mesh, an invisible collision wall).
- Whether the abort is the behaviour tree; whether other walking cats' trees are safe for long.
- Memory use (the crash report doesn't carry it); long (hour) runs.
