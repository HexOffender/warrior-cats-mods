# Exploration

Moving about the forest: speed, stamina, jumping and climbing, stealth and how animals notice you,
pouncing, scent tracking, time of day, and the map. Part of the [mechanics notes](README.md).

**Sources:** `TuningData.csv` (`Gameplay.Exploration.*`), `LocationsData.csv`, `UniqueIds/` and
`Effects/GenericEffect.csv`. Distances are Unreal units (centimetres) and speeds are cm/s. Many
row descriptions are the designers' own, quoted where useful.

**Which keys the code uses:**
- The player's movement, jump and stamina keys are loaded at `0x14179F650` into the player's
  exploration settings (see [reverse-engineering.md](../reverse-engineering.md#the-exploration-camera)
  for the offsets).
- Detection keys are built from a format string, `Gameplay.Exploration.Detection.%s`, so they're
  used even though the exe doesn't name them whole.
- Treat any other number here as tuning data that something reads, not as code-confirmed.

## Moving

| | Value |
|---|---|
| Walk | 175, reached at 175/s² acceleration |
| Run | 390, acceleration 175 |
| Crouch | 0.5 × walk speed, turning at 65°/s |
| Turning | `Rotation.Rate.Min` 520 and `.Max` 200 (°/s, probably at rest and at full speed); AI chasing turns at 720 |
| Gravity | -980 |
| The mentor in the tutorial | walks 180 and runs 400, so it keeps ahead of you |
| Fleeing prey | 5 × its walking speed (`Prey.Flee.WalkSpeed.Factor`) |
| Mice (`EnemyMouse`) | walk 100, run 550 |

## Stamina

| | Value |
|---|---|
| Maximum | 100 (`Stamina.Max`) |
| Back when not running | 20 per second (`Stamina.RegenRate`) |
| Running | -10 per second (`MoveAndRun.Stamina.DrainRate`) |
| Climbing | -24 per second (`Climb.Stamina.DrainRate`) |
| Energetic cats | running -5, climbing -18 (see [progression.md](progression.md#what-traits-do-in-play)) |

`Gameplay.Exploration.Stamina.Bonus.Modifier.1` to `.16` run from 0.125 to 2.0 in steps of 0.125.
What uses them isn't known; a stamina bonus level from sleeping or sunspots is a guess.
**Sunspots** (`BP_Interactable_Sleep_Sunspot`, 17 on the map) give `Sunspot.Reward.Movement.1` 8
and `.2` 16, units unknown.

Exploration health never drops below 1 (`Exploration.Health.Min`), so you can't die out of combat.
Hazards deal fixed amounts: `Params.Damage.1.Health` -50. A clan invader (`Params.Damage.ClanInvader`)
also deals -50, with `CanKillPlayer` 0.

## Jumping, climbing and falling

**Jumping:**
- A jump is 85 high and 200–250 long. Air control is 150 sideways and forward, capped at 500.
- Taking off from a run is 100 (`Jump.RunSpeed`).

**Jump spots** (`BP_Jump_Spline_HotSpot`) snap you along a set path. Their radii are 150, 120 and
60, and they become usable within 120 (`Jump.Hotspot.InteractThreshold`).

**Climbing:**
- You climb at normal speed (`Climb.Modifier.Speed` 1).
- Trees and walls are `BP_SplineClimb_Target_TreeClimb` / `_Wall`: 42 trees, 6 walls and 13
  other spots in the main map.

**Falling:**
- Climb falls have `Climb.Fall.Multi.BaseHeight` 5,000,000 and `Climb.Fall.DamageRate` 0.1. How
  they combine isn't traced; 5,000,000 could be a squared distance (about 22 m).
- Walking off an edge: `Edge.Fall.Percent` 0.3, `.Height` 5 and `.Forward` 50.

## Stealth and being noticed

**Your cat** gives off three detection spheres, as the designers describe them:

| Sphere | Radius | Crouching |
|---|---|---|
| Visual | 30 | × 0.5 ("within an NPC's vision cone") |
| Sound | 100 at walking speed | × 0.5 |
| Scent | 150 | × 0.75 |

Movement areas change these: `BP_MovementModifier_Invisible` and `_Loud`
(`SwtAdventureMovementModifierArea`).

**Animals and NPCs** have the same senses at every size class (Tiny, Small, Medium, Large):

| | Value |
|---|---|
| Vision cone | 75° wide, 450 deep |
| Hearing | 450 |
| How far you can pounce on it | 400 |
| Close range (`Proximity.Distance`) | 100 (200 for Small) |
| How far you can target it (`Target.Distance`) | 1200 |
| Walking about / chasing | 70 / 400 |
| Wakes up when you're within / sleeps again past (`PlayerZone`) | 1600 / 2000 |
| Delay before chasing (`Time.ReactToChase`, Small, Medium, Large) | 0.5 s |

`Detection.LostCharacter.Delay` is named in the exe too.

**Where they live:** each animal's detection component (`SwtAdventureDetectionComponent`, its
`ExplorationDetectionComponent`) copies its size class's values in when it's made (`0x1417B8B50`,
from `Gameplay.Exploration.Detection.<class>.*`), so a change there is that animal's alone:

| Offset | Key | Offset | Key |
|---|---|---|---|
| +0x57C | `Cone.Angle` | +0x598 | `Target.Distance` |
| +0x580 | `Cone.Distance` | +0x59C | `WalkSpeed.Roaming` |
| +0x588 | `Pounce.Distance` | +0x5A0 | `WalkSpeed.Chasing` |
| +0x58C | `Sound.Radius` | +0x5A4 | `PlayerZone.EntryDistance` |
| +0x590 | `Sound.Speed` | +0x5A8 | `PlayerZone.ExitDistance` |
| +0x594 | `Proximity.Distance` | +0x5AC | `Time.ReactToChase` |

Read in game from a mouse (Small): 75, 450, 400, 450, 1, 200, 1200, 70, 400, 1600, 2000 and 0.5.
`WCModsGame` maps them as a cat's `senses()`; the C++ SDK as `wcmods::senses(actor)`.

**What the AI knows** is on its controller's blackboard (`BB_Enemy`): `Detected`, `Target`,
`StartLocation`, `RoamingLocation`, `DetectionRange`, `ChaseReactionTime`, `Hunted`, `HunterPawn`,
`PointOfInterest`, `bShouldAllowMovement`, `ArrivedAtTarget`, `SplineReference`, `CurrentIndexSpline`.
Noticing a cat (`OnCharacterDetected`, `0x14189F530`) sets `Detected`, `Target`, `StartLocation`,
`ChaseReactionTime` and `DetectionRange` from the detection component and starts a timer; losing it
(`0x14189F760`) clears `Detected` and `Target`. A fighter's AI (`BB_CombatEnemy`) keeps
`AffectedByCondition`, `IsExhausted`, `IsAlive`, `AllyWithStatus`, `AllyWithLowHealth`, `WeakestEnemy`,
`SlowestEnemy`, `SelectedAttack` and `itemTag`.

**Size classes for metrics:** the player cat is 15 tall, 10 wide and 31 long. NPC cats are 25 tall.
Small and medium enemies are 25 tall, and large ones 65.

## Pouncing and sneak attacks

- **A pounce** flies at 500, × 1.2 with an Agility bonus (`Pounce.Multi.AgilityBonus`), and lands
  50 short of the target (`Pounce.Offset` -50).
- **A pounced animal** loses 30% of its health (`Params.Damage.PounceVictim.Health` -0.3,
  `UsePercent`), so a pounce opens a fight with a head start.
- **`SneakAttack.AutoDefeatDelta` 3:** probably, a sneak attack on an animal 3 or more levels
  below you wins outright (a guess from the name).
- **Prey burrows** (`BP_Interactable_Dig_Combat_PreyBurrow`, 48 on the map) start a fight when
  dug.

## Scent tracking

| | Value |
|---|---|
| How long a sniff lasts | 10 s |
| Between sniffs | 12 s (`Cooldown`) |
| Range | 1200 / 1600 / 3000 (three levels, probably upgrades) |
| Sensing sphere | 32 |
| The trail | starts 500 ahead (`AheadDistance`), fades in and out over 0.5 s |
| The hint | runs at 850 (50 for the second tracking element) |
| Looking at the trail | works within 1000 |

**Trail colours** (`Gameplay.Exploration.Tracking.*`, RGB):
- areas and places: (0, 100, 200);
- enemies: red;
- allies: green;
- collectables: blue.

## Time of day

| | Value |
|---|---|
| Clock speed | 72 (`DayNight.ClockSpeed`) |
| A new game starts at | 21600 = 6:00 (`DayNight.StartTime`, seconds into the day) |

If the clock runs 72 game seconds per real second, a full day takes 20 real minutes. The cheats
popup has `advance_12_hours` and `set_time_6am`.

## The map

**Territories:** `LocationsData.csv` names 50 areas, each with a code. The save lists the ones
you've found (`"LocationsDiscovered": "R-05;R-06;R-08"`):

| Territory | Codes | Areas |
|---|---|---|
| ThunderClan | T-01 … T-13 | Greenleaf Twolegplace, Granite-Grip Glade, Echo-Woods, Star-Path Ridges, The Clearing, Abandoned Twoleg Nest, Rising-Mist Path, Oak-Shade Shallows, The Hollow, ThunderClan Camp, Dark-Reed Stretch, The Sky Oak, Mouth-Side Meadow |
| ShadowClan | S-01 … S-13 | Obsidian Heights, Moss-Hollow Sink, Cold-Stone Trail, The Quiet-Nest, The Twisted-Tangle, The Talon-Climb, Twoleg's Shadow, ShadowClan Camp, Split-Tongue Way, Sentry-Shadow Slopes, Abandoned Thunderpath, Gloaming Thicket, Murk-Log Crossing |
| WindClan | W-01 … W-10 | Quick-Silver Rills, Reed-Whistle Delta, Heather-Step Way, WindClan Camp, Leap-Stone Ridges, Lookout Bluffs, Bright-Water Flats, Splinter-Path, Whispering Copses, Warren-Way |
| RiverClan | R-01 … R-10 | Pine-Rim Twolegplace, Gloom-Step Heights, Murmuring Ripples, The Gulping Mouth, RiverClan Camp, Willow-Weep, Moss-Grip Delta, The Stone-Span, Shimmer-Stream, The Horseplace |
| Moonpool | M-01 … M-03 | Ancestors' Veil, The Moonpool, Star-Mist Falls |
| The Island | I-01 | The Island |

Each area's name shows when you walk into its `BP_ZoneNameTrigger` (`WrcZoneNameTrigger`).

**What's out there.** `UniqueIds/L_WorldMap_01_P.csv` lists the 3727 world objects that keep
state (an ID, the actor, and its `SoftData`: rewards, location and a class number). The main
ones:

| Object | Count | Gives |
|---|---|---|
| Dandelions, poppies, bog cotton you brush past | 480, 439, 265 | (set in the Blueprint) |
| Animal spawners (`BP_Enemy_Generator`) | 167 | |
| Claw: bushes, fishing spots, spider webs, vines, bird nests, special bushes | 129, 32, 30, 29, 24, 19 | (set in the Blueprint) |
| Dig: dirt mounds, prey burrows | 105, 48 | |
| Sharpen: bark, rock | 43, 43 | |
| Play: cattail reeds | 62 | |
| Healing herb pickups: small, medium | 80, 83 (+25 others) | 1 of that herb |
| Catnip pickups: small, medium, big | 64, 40, 17 | 1 of that catnip |
| "Big/Full/Super Healing Herb" pickups | 65, 32, 26 | Their main ingredient instead: Comfrey, Goldenrod, Broom |
| Pouch pickups (Lavender, Chestnut, Ginger Root, Peppermint, Herb Spices) | 16–32 each | Their ingredient: Borage, Thyme, Burdock, Juniper, Willow |
| Other pouch pickups (Healing, Eyewort, Valerian, Antidote, Chamomile, Fish Scale, Cat Thyme, Sage) | 5–24 each | The pouch itself (Cat Thyme also gives Thyme) |
| Den entrances | 64 (+5 multi-rank) | |
| Race triggers, quest triggers, tutorial triggers | 44, 36, 36 | |
| Checkpoints | 22 | |
| Sunspots | 17 | |

`bAvailable` is False for all but 2. The `_Ori`, `_Updated` and `_Updated_2` files are older
copies.

**Other world settings:**
- **The minimap** renders a 1024 texture covering 2343 units (`Minimap.Render.*`).
- **Distance hiding:** objects hide by distance at 2343 and 4686 (`HideByDistance.Radius.1/2`).
- **Photo mode** moves, zooms and turns at 100, between 50 and 200 from the cat.
- **Growling** has a 2.5 s cooldown.
- **The travel record** counts up to 9,999,999 (a statistic).
