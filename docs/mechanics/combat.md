# Combat

How a fight works: stats, the damage formula, hitting and missing, stances, moves, status
conditions, dilemmas and the AI. Part of the [mechanics notes](README.md).

**Sources:** the formulas were read from the exe's code (build 24847281, addresses below). The
numbers are from `DataTables/NonAsset`: `TuningData.csv`, `AttackMove.csv`, `CharacterAttacks.csv`,
`CharacterStatsBase.csv`, `CombatStance.csv`, `CombatDilemmas.csv`, `AICombatChances.csv`,
`CombatBaseExperience.csv`, `SkirmishRank.csv` and the two `Effects/` tables. Names come from
`Strings_EN.csv`.

## The combatant

Each cat or animal in a fight has a combat component that holds its stats, level, stance and the
move it's using:

| Offset | What |
|---|---|
| +0x128 | The current move: a copy of its `AttackMove` row (so its `Stance` is at +0x15B, `Damage` +0x160, `Accuracy` +0x164, `StaminaCost` +0x168) |
| +0x1A0 | Its current stance (`ESwtAdventureCombatStance`) |
| +0x1A8 | Its stats struct (`Prowess` +0x1C4, `Strength` +0x1C8, `Resilience` +0x1CC, `Instinct` +0x1D0, `Agility` +0x1D4, `Stamina` +0x1D8) |
| +0x378–0x3A0 | Combat tuning, loaded at `0x1417D7940` (agility penalty, stance modifiers, damage formula, rest) |
| +0x3D8 | Its clan |
| +0x3DC | Its level |

A character actor points to its combat component at +0x848.

**Enums** (from the exe's enum tables):
- `ESwtAdventureCombatStance`: None 0, Neutral 1, Offensive 2, Defensive 3, Trick 4, Sneaky 5,
  Reckless 6.
- `ESwtAdventureCombatAttribute`: None 0, Prowess 1, Strength 2, Resilience 3, Instinct 4,
  Agility 5.
- `ESwtAdventureTargetAttack`: None 0, SingleSelf 1, SingleEnemy 2, AOESelf 3, AOEEnemy 4.
- `ESwtAdventureStatusType`: None 0, Blinded 1, Furious 2, Poisoned 3, Stressed 4.

## Stats

Six stats, read from the code:

| Stat | What it does |
|---|---|
| **Prowess** | Health, very likely. Setting up a fighter passes round(Prowess) to two setters on the component at +0x650, most likely max and current health (`0x1417D6F8D` on). It also adds to stamina. |
| **Stamina** | Combat stamina. The maximum is **0.4 × Prowess + Stamina** (`0x1417D6F0A`). Moves cost stamina. |
| **Strength, Instinct, Agility** | Attack and defence, picked by stance (see the damage formula). |
| **Resilience** | Named as the defence stat for three stances in `CombatStance.csv`, but the damage code doesn't read that column (below). |
| **Agility** | Also gives speed (below). |

**Getting a stat** (`0x1417D87A0` for Prowess, and the same shape for each stat):
stat × (1 + the sum of the fighter's percentage buffs). So a +5% Strength buff and a +2% one make
1.07 × Strength.

**Speed** (`0x1417D9800`): Agility × (1 + Speed buffs), halved when stamina is at or below 30% of
the maximum (`Agility.StaminaModifier.Stamina` 0.3, `.Agility` 0.5). It probably decides who acts
first (a guess).

**Base stats** come from `CharacterStatsBase.csv` and grow with level (see
[progression.md](progression.md)):

| Who | Prowess | Strength | Resilience | Instinct | Agility | Stamina |
|---|---|---|---|---|---|---|
| Player, ThunderClan | 90 | 95 | 85 | 85 | 80 | 100 |
| Player, ShadowClan | 80 | 75 | 65 | 105 | 80 | 100 |
| Player, RiverClan | 90 | 85 | 75 | 75 | 85 | 100 |
| Player, WindClan | 80 | 85 | 85 | 75 | 90 | 100 |
| Clan cat, ThunderClan | 75 | 80 | 70 | 70 | 65 | 100 |
| Clan cat, ShadowClan | 65 | 60 | 50 | 90 | 65 | 100 |
| Clan cat, RiverClan | 75 | 70 | 60 | 60 | 70 | 100 |
| Clan cat, WindClan | 65 | 70 | 70 | 60 | 75 | 100 |
| Cat, no clan | 75 | 70 | 70 | 70 | 70 | 100 |
| Mouse (weak / normal) | 50 / 55 | 50 / 55 | 50 / 55 | 50 / 55 | 50 / 55 | 60 / 65 |
| Squirrel (weak / normal) | 60 / 65 | 55 / 60 | 55 / 60 | 55 / 60 | 65 / 70 | 65 / 70 |
| Rabbit (weak / normal / boss) | 60 / 65 / 65 | 55 / 60 / 60 | 55 / 60 / 60 | 70 / 75 / 75 | 60 / 65 / 65 | 65 / 70 / 70 |
| Bird (weak / normal) | 60 / 65 | 55 / 60 | 55 / 60 | 55 / 60 | 65 / 70 | 60 / 65 |
| Rat (weak / normal) | 70 / 75 | 70 / 75 | 70 / 75 | 70 / 75 | 70 / 75 | 70 / 75 |
| Snake (normal / threat, boss) | 75 / 80 | 75 / 80 | 75 / 80 | 80 / 85 | 55 / 60 | 75 / 80 |
| Badger (normal, boss / threat) | 80 / 85 | 80 / 85 | 80 / 85 | 80 / 85 | 80 / 85 | 90 / 95 |
| Fox (threat / titan, boss) | 90 / 95 | 75 / 80 | 75 / 80 | 90 / 95 | 90 / 95 | 95 / 100 |
| Dog (threat / titan, boss) | 95 / 100 | 85 / 90 | 80 / 85 | 85 / 90 | 85 / 90 | 105 / 110 |

`ClanSpecificBase.csv` has a second, lower set of clan bases (ThunderClan 70/80/70/70/50/100). The
stat code reads `CharacterStatsBase` (its row layout matches: `Prowess` 0x1C … `Stamina` 0x30), so
what `ClanSpecificBase` is for isn't known.

## The damage formula

Read from `0x1417DBC20` (the hit's damage). The constants are tuning keys
(`Gameplay.Combat.Damage.Formula.*`) loaded into the attacker's component:

```
            Power × A × (1 + 0.5 × attacker level)
base  =  ─────────────────────────────────────────────  + 2
          max(1, D × (5 + 0.3 × defender level))

damage = round(base × stance modifier × 0.015 × (85 + R))
```

- **Power** is the move's `Damage` (component +0x160).
- **A** is the attacker's stat named in the `Attack` column of `CombatStance.csv`, for the
  attacker's current stance. Sneaky averages Agility and Instinct, and Reckless averages Agility
  and Strength (`0x1417D9B60`).
- **D** is the defender's stat, looked up the same way: the `Attack` column, for the stance of the
  move being used. So an Offensive move matches Strength against Strength, and a Trick move
  Instinct against Instinct. **The `Defense` column (Resilience for Offensive, Defensive and
  Reckless) isn't read here,** so Resilience may not reduce damage at all. That's surprising, and
  worth testing in game: compare damage taken with and without a Resilience buff (Fish Scale
  Pouch, Stone Guard).
- **R** is a random whole number from 0 to 15: rand() × 16 / 32767, capped at 15. So a hit does
  85–100% of its top damage.
- **0.015, 1, 0.5, 5 and 0.3** are `Universal.Factor`, `Numerator.Constant`, `Numerator.Factor`,
  `Denominator.Constant` and `Denominator.Factor`. The floor of 1 and the +2 are constants in the
  code.
- **The rounding** is Unreal's `RoundToInt` (the code computes (2x + 0.5) >> 1).

It's the Pokémon damage formula with different constants. Some worked examples:

| Hit | Damage |
|---|---|
| Level 1 ThunderClan player (Strength 95), Quick Claw (30), into a level 1 mouse (Strength 55), neutral stances | 21–25 |
| Two level 10 cats with 100 in the stat, a 30-power move | 31–37 |
| Level 20 cat with 190 Strength, a 35-power move at stance advantage (1.5), into a level 20 dog with 90 | about 171 |

**A preset damage:** if the move's tag matches the one stored at +0x300, the damage stored at
+0x3E4 is used instead, and cleared. This is probably for scripted hits.

**Area moves:** after the main target, the code goes through the other fighters on that side and
deals round(damage × a per-target factor) to each (`0x1417BE5D0` gives the factor).

## Hitting and missing

Read from the code around `0x1417DB2C2`:
1. **Stamina:** if the attacker's stamina minus the move's `StaminaCost` would go below 0, the
   move isn't used.
2. **Chance to hit:** the move's `Accuracy`, minus 0.2 if the attacker is Blinded
   (`Gameplay.Combat.StatusCondition.Blinded.Attacks.Accuracy`).
3. **The roll:** rand() / 32767, a number from 0 to 1. It's a hit if the roll is at or below the
   chance. So accuracy 1 always hits, unless the attacker is Blinded.
4. **A forced miss:** before the roll, a flag looked up by the defender's byte at +0x1A1 can make
   it a miss. This may be a dodge or a "Substitute" decoy (not traced).

Prowess, Instinct and Agility don't change the chance to hit.

## Stances

Every move has a stance, and the fighter takes it on. The multiplier is `CombatStance.csv`'s value
for the attacker's stance (row) against the defender's current stance (column):

| Attacker \ defender | Offensive | Defensive | Trick | Sneaky | Reckless | Neutral | Attack stat | Defense stat (unused) |
|---|---|---|---|---|---|---|---|---|
| **Offensive** | 1 | 0.5 | 1.5 | 1 | 1.5 | 1 | Strength | Resilience |
| **Defensive** | 1.5 | 1 | 0.5 | 1 | 1.5 | 1 | Strength | Resilience |
| **Trick** | 0.5 | 1.5 | 1 | 1 | 1.5 | 1 | Instinct | Instinct |
| **Sneaky** | 2 | 2 | 2 | 2 | 1.5 | 2 | Agility (+ Instinct) | Instinct |
| **Reckless** | 1.5 | 1.5 | 1.5 | 1.5 | 1.5 | 1.5 | Agility (+ Strength) | Resilience |

- **The triangle:** Offensive beats Trick, Trick beats Defensive, and Defensive beats Offensive.
- **Sneaky** always does double (1.5 against Reckless), but its moves are less accurate (0.7–0.75).
- **Reckless** always does 1.5×.
- **Anything against a Reckless defender** does 1.5×.
- **A Neutral attacker, or a fighter with no stance,** gets `StanceModifier.Neutral` (1)
  (`0x1417D98C0`). The tuning's `Advantage` 1.5 and `Disadvantage` 0.5 aren't read there; the
  table's own values are used.
- **Stance buffs:** the fighter's stance buffs feed the multiplier as
  (1 + buff) × table value + a flat part (two calls to `0x1417BD850`). These are probably the stance
  pouches, e.g. Peppermint (`Buff.Offensive.1`, +0.25 for 1 round).

## Status conditions

What the game's own help text says, with the numbers from `TuningData`:

| Status | Effect | Number |
|---|---|---|
| Blinded | "a much lower chance to land attacks" | −0.2 accuracy (read from the code) |
| Furious | "You lose control of move choice" | |
| Poisoned | "You lose 10% health at the end of every round" | `StatusCondition.Poison.Damage` 0.1 |
| Stressed | "You use double stamina for every attack" | |

A fighter has a 20% chance to shake off its status, probably each round
(`StatusCondition.SelfCure.Chance`).
Antidote pouches cure them: Eyewort (Blinded), Chamomile (Furious), Antidote Herb (Poisoned) and
Valerian Root (Stressed).

## Moves

**Player moves:** 20 Universal, 10 for each clan, and 15 Ancestor (StarClan) moves. Every one but
the starting moves is `bLockedByDefault`. Each has a rank it needs (`Rank`). The move tags are
`Gameplay.Combat.Attack.<Category>.<n>`.

<!-- table:moves -->
| Move | Name | Stance | Rank | Target | Damage | Accuracy | Stamina | Status | Effect |
|---|---|---|---|---|---|---|---|---|---|
| Universal.1 | Taunting Strike | Offensive | Apprentice | SingleEnemy | 15 | 1 | 20 | Furious 100% |  |
| Universal.2 | Quick Claw | Offensive | Apprentice | SingleEnemy | 30 | 1 | 20 |  |  |
| Universal.3 | Strong Claw | Offensive | Warrior | SingleEnemy | 35 | 0.9 | 25 |  |  |
| Universal.4 | Giga Stomp | Offensive | Deputy | AOEEnemy | 25 | 1 | 40 |  |  |
| Universal.5 | Provoking Stare | Defensive | Apprentice | SingleEnemy | 15 | 1 | 20 | Stressed 100% |  |
| Universal.6 | Tackle | Defensive | Apprentice | SingleEnemy | 30 | 1 | 20 |  |  |
| Universal.7 | Shoulder Bash | Defensive | Warrior | SingleEnemy | 35 | 0.9 | 30 |  |  |
| Universal.8 | Spiked Somersault | Defensive | Deputy | AOEEnemy | 25 | 1 | 40 |  |  |
| Universal.9 | Sand Throw | Trick | Apprentice | SingleEnemy | 15 | 1 | 20 | Blinded 100% |  |
| Universal.10 | Rock Throw | Trick | Apprentice | SingleEnemy | 30 | 1 | 20 |  |  |
| Universal.11 | Mud Shot | Trick | Warrior | SingleEnemy | 35 | 0.9 | 30 |  |  |
| Universal.12 | Sand Splash | Trick | Deputy | AOEEnemy | 25 | 1 | 40 |  |  |
| Universal.13 | Poisonous Claw | Sneaky | Apprentice | SingleEnemy | 25 | 0.75 | 30 | Poisoned 100% |  |
| Universal.14 | Leap-and-Hold | Sneaky | Apprentice | SingleEnemy | 35 | 0.75 | 25 |  |  |
| Universal.15 | Sneak Attack | Sneaky | Warrior | SingleEnemy | 40 | 0.75 | 35 |  |  |
| Universal.16 | Ambush | Sneaky | Deputy | AOEEnemy | 30 | 0.75 | 45 |  |  |
| Universal.17 | Enraged Charge | Reckless | Apprentice | SingleEnemy | 20 | 0.85 | 25 |  |  |
| Universal.18 | Tail Attack | Reckless | Apprentice | SingleEnemy | 25 | 1 | 25 |  |  |
| Universal.19 | Strong Tail | Reckless | Warrior | SingleEnemy | 35 | 0.9 | 35 |  |  |
| Universal.20 | Hyper Roar | Reckless | Deputy | AOEEnemy | 25 | 1 | 45 |  |  |
| ThunderClan.1 | Sharp Claw | Offensive | Warrior | SingleEnemy | 30 | 1 | 30 |  | Strength +2% (self, rest of the fight) |
| ThunderClan.2 | Poisonous Fang | Offensive | Deputy | SingleEnemy | 25 | 1 | 30 | Poisoned 100% |  |
| ThunderClan.3 | Strong Push | Defensive | Warrior | SingleEnemy | 20 | 1 | 15 |  |  |
| ThunderClan.4 | Bulk up | Defensive | Deputy | SingleSelf | 0 | 1 | 15 |  | Strength +5% (self, rest of the fight), max 3 uses |
| ThunderClan.5 | Loud Hissing | Trick | Warrior | AOEEnemy | 20 | 1 | 40 |  |  |
| ThunderClan.6 | Teeth Grip | Trick | Deputy | SingleEnemy | 30 | 0.9 | 40 |  | Speed -2% (the target, rest of the fight) |
| ThunderClan.7 | Lightning Strike | Sneaky | Warrior | SingleEnemy | 30 | 0.7 | 35 |  | Resilience -2% (the target, rest of the fight) |
| ThunderClan.8 | Poisonous Stab | Sneaky | Leader | SingleEnemy | 40 | 0.7 | 35 | Poisoned 80% |  |
| ThunderClan.9 | Upright Lock | Reckless | Warrior | SingleEnemy | 25 | 1 | 35 |  | Instinct -2% (the target, rest of the fight) |
| ThunderClan.10 | Berserk Rush | Reckless | Leader | SingleEnemy | 30 | 1 | 35 | Furious 100% |  |
| ShadowClan.1 | Wrestle | Offensive | Warrior | SingleEnemy | 20 | 1 | 25 | Stressed 60% |  |
| ShadowClan.2 | Body Slam | Offensive | Deputy | SingleEnemy | 30 | 1 | 30 |  | Agility -2% (the target, rest of the fight) |
| ShadowClan.3 | Warning Growl | Defensive | Warrior | AOEEnemy | 0 | 1 | 45 |  | Strength -5% (the target, rest of the fight), max 3 uses |
| ShadowClan.4 | Dirt Kick | Defensive | Deputy | AOEEnemy | 15 | 1 | 45 | Blinded 60% |  |
| ShadowClan.5 | Deceptive Strike | Trick | Warrior | SingleEnemy | 30 | 1 | 30 |  | Instinct -2% (the target, rest of the fight) |
| ShadowClan.6 | Unbalancing Strike | Trick | Deputy | SingleEnemy | 15 | 1 | 20 | Stressed 100% |  |
| ShadowClan.7 | Belly Rake | Sneaky | Warrior | SingleEnemy | 25 | 0.7 | 30 | Poisoned 60% |  |
| ShadowClan.8 | Covered Lunge | Sneaky | Leader | SingleEnemy | 35 | 0.7 | 35 |  | Agility +2% (self, rest of the fight) |
| ShadowClan.9 | Last Stand | Reckless | Warrior | SingleEnemy | 45 | 0.9 | 30 |  | Health -5% (self, rest of the fight) |
| ShadowClan.10 | Overwhelm | Reckless | Leader | SingleEnemy | 30 | 0.9 | 35 |  | Strength -2% (the target, rest of the fight) |
| RiverClan.1 | Scatter Attack | Offensive | Warrior | AOEEnemy | 25 | 1 | 40 |  |  |
| RiverClan.2 | Throat Snap | Offensive | Deputy | SingleEnemy | 30 | 1 | 30 |  | Agility -2% (the target, rest of the fight) |
| RiverClan.3 | Stone Guard | Defensive | Warrior | SingleSelf | 0 | 1 | 15 |  | Resilience +5% (self, rest of the fight), max 3 uses |
| RiverClan.4 | Hunker Down | Defensive | Deputy | SingleSelf | 0 | 1 | 25 |  | StaminaMultiplier +50% (self, 2 rounds) |
| RiverClan.5 | Play Dead | Trick | Warrior | SingleEnemy | 15 | 0.9 | 20 | Furious 60% |  |
| RiverClan.6 | Hissing Parry | Trick | Deputy | SingleEnemy | 15 | 0.9 | 20 | Stressed 70% |  |
| RiverClan.7 | Poisonous Surprise | Sneaky | Warrior | SingleEnemy | 20 | 0.7 | 25 | Poisoned 80% |  |
| RiverClan.8 | Dust Bomb | Sneaky | Leader | SingleEnemy | 20 | 0.7 | 25 | Blinded 90% |  |
| RiverClan.9 | Pin Down | Reckless | Warrior | SingleEnemy | 25 | 0.9 | 30 |  | Strength -2% (the target, rest of the fight) |
| RiverClan.10 | Mega Splash | Reckless | Leader | AOEEnemy | 40 | 0.9 | 55 |  |  |
| WindClan.1 | Tail Whip | Offensive | Warrior | AOEEnemy | 25 | 1 | 40 |  |  |
| WindClan.2 | Hunting Leap | Offensive | Deputy | SingleEnemy | 30 | 1 | 30 |  | Agility +2% (self, rest of the fight) |
| WindClan.3 | Thick Fur | Defensive | Warrior | SingleSelf | 0 | 1 | 15 |  | Resilience +5% (self, rest of the fight), max 3 uses |
| WindClan.4 | Defensive Curl | Defensive | Deputy | SingleSelf | 0 | 1 | 15 |  | Strength +5% (self, rest of the fight), max 3 uses |
| WindClan.5 | Dust Cloud | Trick | Warrior | AOEEnemy | 15 | 0.9 | 45 | Blinded 60% |  |
| WindClan.6 | Misdirection | Trick | Deputy | SingleEnemy | 0 | 1 | 25 | Blinded 90% |  |
| WindClan.7 | Guerilla Attack | Sneaky | Warrior | AOEEnemy | 35 | 0.7 | 45 |  |  |
| WindClan.8 | Elders' Guidance | Sneaky | Leader | SingleSelf | 0 | 1 | 25 |  | Strength +5%, Instinct +5% (self, rest of the fight), max 3 uses |
| WindClan.9 | Partner Fighting | Reckless | Warrior | SingleSelf | 0 | 1 | 30 |  | Damage +50% (self, 1 round) |
| WindClan.10 | Payback | Reckless | Leader | SingleEnemy | 0 | 1 | 30 |  |  |
| Ancestor.1 | Go for the Ears | Offensive | Warrior | SingleEnemy | 40 | 1 | 45 |  | Instinct -3% (the target, rest of the fight) |
| Ancestor.2 | StarClan Charge | Offensive | Deputy | SingleEnemy | 55 | 1 | 45 |  |  |
| Ancestor.3 | Ancestral Roar | Offensive | Leader | AOEEnemy | 35 | 1 | 55 |  |  |
| Ancestor.4 | Go for the Tail | Defensive | Warrior | SingleEnemy | 40 | 1 | 45 |  | Resilience -3% (the target, rest of the fight) |
| Ancestor.5 | Spirit Ward | Defensive | Deputy | AOESelf | 0 | 1 | 35 |  | Resilience +3%, Instinct +3% (self, rest of the fight) |
| Ancestor.6 | Foresight | Defensive | Leader | AOESelf | 0 | 1 | 35 |  | Agility +8% (self, rest of the fight) |
| Ancestor.7 | Go for the Eyes | Trick | Warrior | SingleEnemy | 35 | 1 | 45 | Blinded 60% |  |
| Ancestor.8 | Go for the Paws | Trick | Deputy | SingleEnemy | 35 | 1 | 50 |  | Speed -8% (the target, rest of the fight) |
| Ancestor.9 | Sand Storm | Trick | Leader | AOEEnemy | 30 | 1 | 65 |  | Resilience -3%, Instinct -3% (the target, rest of the fight) |
| Ancestor.10 | Substitute | Sneaky | Warrior | AOESelf | 0 | 1 | 60 |  | Agility +3% (self, rest of the fight) |
| Ancestor.11 | Invisible Strike | Sneaky | Deputy | SingleEnemy | 60 | 0.7 | 50 |  |  |
| Ancestor.12 | Poisonous Smoke | Sneaky | Leader | AOEEnemy | 25 | 0.7 | 55 | Poisoned 90% |  |
| Ancestor.13 | Killing Bite | Reckless | Warrior | SingleEnemy | 50 | 0.9 | 50 |  |  |
| Ancestor.14 | Final Showdown | Reckless | Deputy | AOEEnemy | 30 | 0.9 | 55 |  |  |
| Ancestor.15 | Force of Will | Reckless | Leader | AOESelf | 0 | 1 | 55 |  | Stamina +100% (own team, now) |
<!-- /table -->

**Reading the effects:** an effect tag `Gameplay.Effect.Movement.X` takes its numbers from the row
`Gameplay.Params.Movement.X` in `Effects/CombatStatBuffEffect.csv` (stat percentages) or
`Effects/GenericEffect.csv` (everything else). The two tables' `Target` codes, worked out from
which rows use them: 1 the user, 2 a clanmate, 4 the user's team, 7 the move's target, and 0 for an
item's own target. `NumTurns`: -1 is the rest of the fight, 0 is at once, n is n rounds. "With
each attack" moves (Sharp Claw, Bulk Up) stack every time they're used, up to `MaxEffectUses`
when it's set.

**Data quirks:**
- **`bDone`:** 57 of the 75 player moves (124 of all 185) are `bDone = FALSE`, among them Tackle,
  which most players start with. So it doesn't stop a move being used. It's probably a production
  checklist flag.
- **Tag spelling:** `CharacterAttacks.csv` writes `Thunderclan.1` and `Shadowclan.1` where the tags
  are `ThunderClan.1`. Gameplay tags compare without case, so they still match.

**Starting moves** (`CharacterAttacks.csv`, `InitialAttacks`):

| Player in | Moves |
|---|---|
| ThunderClan | Taunting Strike, Tackle, Rock Throw |
| ShadowClan | Quick Claw, Tackle, Rock Throw |
| RiverClan | Quick Claw, Tackle, Sand Throw |
| WindClan | Quick Claw, Provoking Stare, Rock Throw |

Clan NPCs start with Sharp Claw (ThunderClan.1; ShadowClan cats get Wrestle instead), Shoulder
Bash, Sand Throw and Enraged Charge.
In Skirmish, opponents get `FixedAttacks` by tier (0–4) plus random picks from `RandomAttacks`.

**Learning moves:**
- **A trainer:** the Trainer Cat at the Training Grounds (`STR_TRAINING_LEARN_*`, the
  `...WarriorMoveLearn` narrative roles) teaches Universal, Clan and Ancestor moves.
- **Bonding:** for key characters, the "Friend" bonding reward is a clan move (see
  [quests-and-bonding.md](quests-and-bonding.md)).
- **Den visits:** `VisitRewards.csv` lists every move, but all at weight 0, so visits never give
  one.
- **The belt:** the save keeps your equipped moves as `AttackBelt`.

**Animals and bosses** use their own move sets. `CharacterAttacks.csv` gives each boss phase a
signature move in `FixedAttacks`, e.g. the Starving Warrior's Ancestral Roar and the Proud
Loner's StarClan Charge.

<!-- table:enemy_moves -->
| Set | Moves (damage / accuracy / stamina, stance) |
|---|---|
| WeakMice | Rodent Bite 20/1/10 Offensive; Tackle 30/1/20 Defensive; Sand Throw 15/1/20 Trick Blinded 100% |
| Mice | Rodent Bite 20/1/10 Offensive; Tackle 30/1/20 Defensive; Sand Throw 15/1/20 Trick Blinded 100%; Enraged Charge 20/0.85/25 Reckless |
| WeakSquirrel | Somersault 25/1/20 Trick; Tackle 30/1/20 Defensive; Taunting Strike 15/1/20 Offensive Furious 100% |
| Squirrel | Somersault 25/1/20 Trick; Tackle 30/1/20 Defensive; Taunting Strike 15/1/20 Offensive Furious 100%; Poisonous Claw 25/0.75/30 Sneaky Poisoned 100% |
| WeakRabbit | Flying Kick 25/1/20 Defensive; Quick Claw 30/1/20 Offensive; Sand Throw 15/1/20 Trick Blinded 100% |
| Rabbit | Flying Kick 25/1/20 Defensive; Quick Claw 30/1/20 Offensive; Sand Throw 15/1/20 Trick Blinded 100%; Leap-and-Hold 35/0.75/25 Sneaky |
| BossRabbit | Foresight 0/1/25 Defensive; Flying Kick 25/1/20 Defensive; Quick Claw 30/1/20 Offensive; Sand Throw 15/1/20 Trick Blinded 100%; Leap-and-Hold 35/0.75/25 Sneaky; Enraged Charge 20/0.85/25 Reckless |
| WeakBird | Peck 10/1/25 Offensive Furious 100%; Provoking Stare 15/1/20 Defensive Stressed 100%; Rock Throw 30/1/20 Trick |
| Bird | Peck 10/1/25 Offensive Furious 100%; Provoking Stare 15/1/20 Defensive Stressed 100%; Rock Throw 30/1/20 Trick; Enraged Charge 20/0.85/25 Reckless |
| WeakRat | Rodent Bite 20/1/10 Offensive; Tail Attack 25/1/25 Reckless; Leap-and-Hold 35/0.75/25 Sneaky; Rock Throw 30/1/20 Trick; Tackle 30/1/20 Defensive |
| Rat | Rodent Bite 20/1/10 Offensive; Poisonous Bite 10/1/25 Trick Poisoned 80%; Leap-and-Hold 35/0.75/25 Sneaky; Tail Attack 25/1/25 Reckless; Tackle 30/1/20 Defensive |
| Snake | Poisonous Bite 10/1/25 Trick Poisoned 80%; Tackle 30/1/20 Defensive; Taunting Strike 15/1/20 Offensive Furious 100%; Tail Attack 25/1/25 Reckless; Sneak Attack 40/0.75/35 Sneaky |
| ThreatSnake | Poisonous Bite 10/1/25 Trick Poisoned 80%; Tackle 30/1/20 Defensive; Taunting Strike 15/1/20 Offensive Furious 100%; Mud Shot 35/0.9/30 Trick; Strong Tail 35/0.9/35 Reckless |
| BossSnake | Poisonous Smoke 20/0.6/55 Sneaky Poisoned 90%; Poisonous Bite 10/1/25 Trick Poisoned 80%; Tackle 30/1/20 Defensive; Taunting Strike 15/1/20 Offensive Furious 100%; Mud Shot 35/0.9/30 Trick; Strong Tail 35/0.9/35 Reckless |
| Badger | Relentless asault 40/0.9/30 Reckless; Shoulder Bash 35/0.9/30 Defensive; Strong Claw 35/0.9/25 Offensive; Sand Throw 15/1/20 Trick Blinded 100%; Poisonous Claw 25/0.75/30 Sneaky Poisoned 100% |
| ThreatBadger | Relentless asault 40/0.9/30 Reckless; Shoulder Bash 35/0.9/30 Defensive; Giga Stomp 25/1/40 Offensive; Sand Throw 15/1/20 Trick Blinded 100%; Poisonous Claw 25/0.75/30 Sneaky Poisoned 100% |
| BossBadger | Go for the Tail 40/1/45 Defensive; Relentless asault 40/0.9/30 Reckless; Shoulder Bash 35/0.9/30 Defensive; Giga Stomp 25/1/40 Offensive; Sand Throw 15/1/20 Trick Blinded 100%; Poisonous Claw 25/0.75/30 Sneaky Poisoned 100% |
| ThreatFox | Shadow Skulk 40/0.5/35 Sneaky Stressed 100%; Shoulder Bash 35/0.9/30 Defensive; Quick Claw 30/1/20 Offensive; Sand Throw 15/1/20 Trick Blinded 100%; Tail Attack 25/1/25 Reckless |
| TitanFox | Shadow Skulk 40/0.5/35 Sneaky Stressed 100%; Spiked Somersault 25/1/40 Defensive; Quick Claw 30/1/20 Offensive; Sand Throw 15/1/20 Trick Blinded 100%; Strong Tail 35/0.9/35 Reckless |
| BossFox | Go for the Paws 35/1/50 Trick; Shadow Skulk 40/0.5/35 Sneaky Stressed 100%; Spiked Somersault 25/1/40 Defensive; Quick Claw 30/1/20 Offensive; Sand Throw 15/1/20 Trick Blinded 100%; Strong Tail 35/0.9/35 Reckless |
| ThreatDog | Furious Bite 40/0.9/35 Offensive Stressed 100%; Tackle 30/1/20 Defensive; Leap-and-Hold 35/0.75/25 Sneaky; Sand Throw 15/1/20 Trick Blinded 100%; Hyper Roar 25/1/45 Reckless; Provoking Stare 15/1/20 Defensive Stressed 100% |
| TitanDog | Furious Bite 40/0.9/35 Offensive Stressed 100%; Tackle 30/1/20 Defensive; Leap-and-Hold 35/0.75/25 Sneaky; Sand Throw 15/1/20 Trick Blinded 100%; Hyper Roar 25/1/45 Reckless; Giga Stomp 25/1/40 Offensive |
| BossDog | Killing Bite 50/0.8/50 Reckless; Giga Stomp 25/1/40 Offensive; Leap-and-Hold 35/0.75/25 Sneaky; Sand Throw 15/1/20 Trick Blinded 100%; Hyper Roar 25/1/45 Reckless; Furious Bite 40/0.9/35 Offensive Stressed 100% |
<!-- /table -->

## Dilemmas and the warrior code

A dilemma is a two-choice popup in a fight (`CombatDilemmas.csv`). Each choice is tagged with a
warrior-code value, `ECombatWarriorCode`: Loyalty 1, Respect 2, Generosity 3, Experience 4,
Honor 5, Authority 6 (no dilemma uses Authority). What the warrior-code tally does isn't known.

**When they come up** (`ESwtAdventureDilemmaType`): CombatBeginning, MovementChoosing,
ReceivingAttack, CombatEnding, BossEnding and Narrative.
- Fight dilemmas have a 15% chance when their condition holds.
- At most one MovementChoosing and one ReceivingAttack dilemma come up per fight
  (`Dilemma.*.Max` 1).
- The conditions use `ESwtAdventureDilemmaTriggerStat`: Health, Stamina, Status, CriticalHit
  (unused) and NumRounds.

<!-- table:dilemmas -->
| Dilemma | When | Chance | Choice A | Choice B |
|---|---|---|---|---|
| A Clan's Bond | CombatBeginning | 0.15 | Generosity: Your cat gets 30% Resilience boost. | Experience: You and your Clanmates receive a 25% Speed bonus. |
| Beginner´s Luck | CombatBeginning | 0.15 | Generosity: Clanmate gets 20% Strength boost. | Experience: Your Clanmate gets a 20% Speed boost. |
| The Weight of Battle | MovementChoosing, TeamMate Status GreaterThanOrEqualTo 1 | 0.15 | Loyalty: You recover 20% of Stamina. | Respect: Your Clanmate's status affliction is cured. |
| A Shared Meal | MovementChoosing, EnemyTeamMate Health LessThan 0.5 | 0.15 | Generosity: Your cat’s Instinct and Agility are boosted 10% for the rest of the battle. | Experience: Strength and Resilience boost by 15% until next round. |
| All for One and One for All! | ReceivingAttack, TeamMate Health LessThan 0.5 | 0.15 | Generosity: Damage is split. | Experience: Strength and Resilience boost by 20% until next round. |
| The Will of the Warrior | ReceivingAttack, Player Health LessThan 0.5 | 0.15 | Loyalty: Receive 15% Strength and Resilience bonus until next round. | Respect: Recover 80% of your health. |
| A Final Show of Strength | CombatEnding, Team Health GreaterThan 0 | 0.15 | Honor: You receive 20% extra XP. | Loyalty: You receive double fresh-kill. |
| The Warrior’s Pride | CombatEnding, Team NumRounds LessThanOrEqualTo 3 | 0.15 | Respect: You receive a random bonus item. | Honor: You receive 15% extra XP. |
| Name a Warrior | Narrative | 1 | Loyalty: {THE UNCHOSEN APPRENTICE} is finally a warrior! | Respect: {THE UNCHOSEN APPRENTICE} suffers another disappointment. |
| Appoint a Deputy | Narrative | 1 | Loyalty: {THE AMBITIOUS WARRIOR} smugly accepts becoming your deputy. | Respect: {THE AMBITIOUS WARRIOR} glares angrily at you. |
| Appoint a Deputy | Narrative | 1 | Loyalty: {THE AMBITIOUS APPRENTICE} is overjoyed to become your deputy. | Respect: {THE SELF DOUBTING WARRIOR} is proud to become your deputy. |
| Appoint a Deputy | Narrative | 1 | Loyalty: {THE ZEALOUS WARRIOR} haughtily accepts being your deputy. | Respect: {THE ZEALOUS WARRIOR} appears quite unhappy with you. |
| Growing RiverClan | Narrative | 1 | Loyalty: {THE LONER} is pleased to join RiverClan. | Respect: {THE LONER} seems to shrink with disappointment. |
<!-- /table -->

**Boss endings** (Dilemmas 17–32): when a boss fight lasts 5–7 rounds or more, a dilemma at the end
always comes up, and both choices give the same scar: ear, eye or body, depending on the boss. The
16 dilemmas cover 18 boss fights: the Starving Warrior (3), the Proud Loner, the Zealous Warrior
and the Insecure Leader (one dilemma), the Rogue Leader, the Ambitious Apprentice and the
Self-Doubting Warrior (one dilemma), the Vengeful Rogue (2), a badger, a snake, a rabbit, and the
secret fox, dog, snake and badger.

## The AI

**Tiers:** `AICombatChances.csv` gives each AI tier its chance to make each kind of choice:

| Tier | Cure status | Heal | Exhausted | Support | Buff | Debuff | Hit weakest | Hit slower | Random | Stance | Area | Strongest | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Terrible | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| Tier 1 | 0.5 | 0.5 | 0.8 | 0.1 | 0.5 | 0.5 | 0 | 0 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| Tier 2 | 0.6 | 0.6 | 0.8 | 0.2 | 0.5 | 0.5 | 0 | 0 | 0.4 | 0.5 | 0.5 | 0.6 | 0.6 |
| Tier 3 | 0.7 | 0.7 | 0.9 | 0.3 | 0.5 | 0.5 | 0.2 | 0.4 | 0.3 | 0.7 | 0.5 | 0.7 | 0.7 |
| Tier 4 | 0.8 | 0.8 | 0.9 | 0.4 | 0.5 | 0.5 | 0.2 | 0.4 | 0.2 | 0.7 | 0.5 | 0.8 | 0.8 |
| Tier 5 | 0.9 | 0.9 | 0.9 | 0.5 | 0.5 | 0.5 | 0.5 | 0.6 | 0.15 | 0.9 | 0.5 | 0.9 | 0.9 |
| Tier 6 | 0.9 | 0.9 | 0.9 | 0.6 | 0.5 | 0.5 | 0.5 | 0.8 | 0.1 | 0.9 | 0.5 | 0.9 | 0.9 |
| Perfect | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 1 |

**Dynamic difficulty** (`Gameplay.Combat.Dynamic.*`): the enemy's tier is picked from a range set by
your level, and its level is yours −1 to +1.

| Your level | Enemy tiers |
|---|---|
| 1–6 | 1–3 |
| 7–11 | 2–4 |
| 12–15 | 3–5 |
| 16–20 | 4–6 |

**Skirmish:**
- **Ranks** (`SkirmishRank.csv`): each rank has a level offset (a triple, probably one per
  opponent) and an AI profile: Novice (0,0,0) profile 2, Adept (0,1,0) 3, Veteran (1,1,1) 4, Elite
  (1,2,1) 5 and Legend (2,2,2) 6.
- **The ELO you need:** Adept 1500, Veteran 3000, Elite 5000 and Legend 7500.

**Defender mode:** clan defenders fight at a set level (`Defender.ForcedLevel` 20; by difficulty,
Easy 17, Medium 17, Hard 18, Insane 18, BossEasy 18, BossHard 19). Defenders recover 25% health
and 50% stamina (`Params.Defender.*.Recover`; when isn't traced).

## After the fight

- **Experience:** each enemy type has a `BaseExperience` in `CombatBaseExperience.csv`:
  - prey: fish 10, mice 25, squirrels 25/30, rabbits 20/40, birds 20/30, rats 30/60;
  - cats 45, snakes 50/70, badgers 70/80, foxes 80/100, dogs 100/120;
  - bosses 400, 800 or 1200 by story stage, and 2000 for the secret ones.
  - `DifficultyOffset` is 0 for prey and cats, and 1–2 for predators (probably added to their tier
    or level).
- **Extra XP and fresh-kill:** dilemmas can add 15–20% XP or double the fresh-kill.
- **Rest:** resting in a fight restores 40% of stamina (`Combat.Rest.Stamina` 0.4).
- **Fleeing:** `Flee.Probability` is 1, so fleeing always works. What `Flee.Penalty` 0.5 costs
  isn't known.

## Camera framing

`QuestCineCameraSettings.csv` places the fight camera for each party size: 1v1 at (-258, 98, 36)
with a 55 mm lens, 2v2 at 50 mm, 3v3 at 45 mm, all at f/16.
