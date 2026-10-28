# Progression

Levels, experience, ranks, how stats grow, and what personality traits do in play. Part of the
[mechanics notes](README.md). How traits are *chosen* is in
[reverse-engineering.md](../reverse-engineering.md#character-creation-and-traits).

## Levels and experience

The level cap is 20 (`Gameplay.Exploration.MaxLevel`). `Gameplay.Exploration.Level.<n>` gives the
experience for each level:

| Level | XP | Running total | Level | XP | Running total |
|---|---|---|---|---|---|
| 2 | 80 | 80 | 12 | 1160 | 4675 |
| 3 | 100 | 180 | 13 | 1500 | 6175 |
| 4 | 135 | 315 | 14 | 2000 | 8175 |
| 5 | 180 | 495 | 15 | 2600 | 10775 |
| 6 | 230 | 725 | 16 | 3400 | 14175 |
| 7 | 300 | 1025 | 17 | 4400 | 18575 |
| 8 | 400 | 1425 | 18 | 5800 | 24375 |
| 9 | 520 | 1945 | 19 | 7500 | 31875 |
| 10 | 680 | 2625 | 20 | 10000 | 41875 |
| 11 | 890 | 3515 | | | |

The save keeps `Experience` next to `Level`. The table is the XP needed for each level, not a running
total, and the counter starts again at each level (read from the code on build 26184573,
[reverse-engineering.md](../reverse-engineering.md#the-games-live-state), "The level component's
code"):
- **The bar:** at level n, the XP bar is `Level.<n+1>` (`0x141658D20`).
- **Levelling up:** XP that reaches the bar, below the cap, makes the cat a level higher, and what's
  over carries into the next level's bar (`0x141658A90`), so one big reward can give several levels.
- **At the cap** (`MaxLevel`, which the level component keeps at +0x124), XP stops levelling, and
  setting the level shows the bar full (`0x141658870`).

**Where XP comes from:**
- **Fights:** each enemy's `BaseExperience` (see [combat.md](combat.md#after-the-fight)).
- **XP effects:** `Effects/GenericEffect.csv` has `Gameplay.Params.XP.50` to `XP.400` (50–400 XP),
  probably quest rewards.
- **The Sage Pouch:** gives 200 XP (`Params.XP.1`).
- **Dilemmas:** "A Final Show of Strength" and "The Warrior's Pride" add 20% and 15%.

## Ranks

`ECharacterRank`: None 0, Apprentice 1, Warrior 2, Deputy 3, Leader 4.

`Gameplay.Progression.Rank.*` sets the last level of each rank, and the combat difficulty brackets
use the same split:

| Rank | Levels | Inventory space | Cat's size | Moves it can learn |
|---|---|---|---|---|
| Apprentice | 1–6 | 100 | 0.45 | Apprentice moves |
| Warrior | 7–11 | 120 | 0.7 | + Warrior moves |
| Deputy | 12–15 | 140 | 0.8 | + Deputy moves |
| Leader | 16–20 | 160 | 1.0 | + Leader moves |

- **Getting promoted:** promotions come from quests (`Quest.Procedural.Progression.RankUp`,
  `RankUp2` and `RankUp3` in the dialogue tables, and the "Name a Warrior" / "Appoint a Deputy"
  narrative dilemmas). Whether levels stop at a rank's cap until its quest is done isn't checked.
- **Inventory:** space is `Gameplay.Inventory.Capacity.<Rank>`, with no limit per item
  (`Inventory.MaxQuantity` -1). The combat item belt holds 4 (`Belt.MaxQuantity`).
- **Size:** the cat's size is `Gameplay.Exploration.Player.<Rank>.Scale` (the mod menu's size cheat
  builds on this).
- **Names:** an apprentice's name ends in -paw, and a leader's in -star (see
  [reverse-engineering.md](../reverse-engineering.md#names)).

## How stats grow

**The base part** is read from the code (`0x1417D8010`, which builds a fighter's stats):

```
stat = round(base + MaxBaseGrowth × (level − 1) × 0.05)
```

- **base** is the `CharacterStatsBase.csv` row for the cat's type and clan (see
  [combat.md](combat.md#stats)).
- **0.05** is a constant in the code, so a stat gains 95% of its growth by level 20.
- **`Gameplay.Combat.MaxBaseGrowth.*`:** Prowess 150, Strength 100, Resilience 120, Instinct 120,
  Agility 100.
- **Stamina doesn't grow.** The code reads `MaxBaseGrowth.StaminaBase` (100), then never uses it,
  and stamina stays at its base (100 for cats).

**Social traits add growth on top.** `Gameplay.Combat.<Trait>.<Stat>` gives each Social trait
extra growth, scaled the same way (× (level − 1) × 0.05):

| Trait | Strength | Resilience | Instinct |
|---|---|---|---|
| Brave | +20 | 0 | +10 |
| Ambitious | 0 | +10 | +20 |
| Wise | +10 | +20 | 0 |

**Checked against a save, and live:** the same numbers sit in the player state's level component
while you play (`Game.cat():stats()`, [scripting.md](../scripting.md)), and an enemy scaled to level 20
had stats grown by the same formula. A RiverClan cat, Brave + Energetic, level 20, has Prowess 233,
Strength 199, Resilience 189, Instinct 199, Agility 180 and Stamina 100.
- Without the trait, the formula gives 233, 180, 189, 189, 180, 100.
- Brave adds 20 × 0.95 = 19 Strength and 10 × 0.95 = 9.5 Instinct.
- That makes 199 and 198.5, which rounds to 199. Every number matches.

The function above doesn't add the trait part. Your cat's level component does, building the key from
the trait's name (read from the code on build 26184573: `0x1417C6410`, which recomputes the stats
whenever the level is set). For each of the cat's traits that is Brave, Ambitious or Wise
(`ECharacterTrait` 1–3), it reads `Gameplay.Combat.` + the trait's name + `.Strength`, `.Resilience`
and `.Instinct`, multiplies each by (level − 1) × 0.05 and adds it to the stat; then it rounds all six
stats to whole numbers (`FMath::RoundToInt`, halves up). So the trait keys never appear as whole
strings. Whether the fight's copy of your stats gets the trait part too isn't traced.
`MaxNatureGrowth.Strength/Resilience/Instinct` (30 each) is probably the cap on a trait's bonus.
That's a guess: no trait comes near it, and `0x1417C6410` doesn't read it.

**Level 20 stats by clan**, before traits:

| Clan | Prowess | Strength | Resilience | Instinct | Agility | Stamina |
|---|---|---|---|---|---|---|
| ThunderClan | 233 | 190 | 199 | 199 | 175 | 100 |
| ShadowClan | 223 | 170 | 179 | 219 | 175 | 100 |
| RiverClan | 233 | 180 | 189 | 189 | 180 | 100 |
| WindClan | 223 | 180 | 199 | 189 | 185 | 100 |

## What traits do in play

| Trait | Type | Effect | Status |
|---|---|---|---|
| Brave, Ambitious, Wise | Social | Extra stat growth (above) | Matches the save |
| Brave, Ambitious, Wise | Social | Dialogue: every player answer is voiced in one of the three (see [quests-and-bonding.md](quests-and-bonding.md)) | From the tables |
| Energetic | Gameplay | Less stamina drain: `Trait.Bonus.Energic.MoveAndRun.DrainRate` -5 (running normally drains -10) and `.Climb.DrainRate` -18 (climbing drains -24) | The code loads both, into the player's exploration settings at +0x208 and +0x20C. Whether they replace or add to the normal drain isn't traced; replacing is what the numbers suggest |
| Curious | Gameplay | **Extra items:** getting a consumable has a 50% chance of +1 (`Trait.Bonus.Curious.Drop.Chance` 0.5, `.PlusQuantity` 1) | Read from the code |
| Curious | Gameplay | **Extra fresh-kill: doesn't work.** See below | Read from the code |
| Patient | Gameplay | **Nothing in the exe.** `TuningData` has `Trait.Bonus.Patient.FreshKill.Chance` 0.5 / `.PlusQuantity` 1, but the exe never mentions "Patient" in a tuning key | Read from the code |

**The fresh-kill bonus bug** (`0x1417C4D20`, run when the player gets an item):
1. If the item is tagged `Gameplay.Inventory.Consumable`, it reads the two `Curious.Drop` keys and,
   if one of the player's traits is Curious (5), rolls for +1.
2. If the item is tagged `Gameplay.Inventory.Materials.FreshKill`, it does the same with
   `Gameplay.Exploration.Trait.Bonus.Curious.FreshKill.Chance` and `.PlusQuantity`, and checks for
   **Curious** again.
3. **The bug:** `TuningData` has no `Curious.FreshKill` rows (the fresh-kill rows are under
   `Patient`). The lookup fails, the chance stays at its default of 0, and the roll (rand()/32767 at
   or below 0) almost never passes.

So, in build 24847281 (and 26184573, which changed none of these tables):
- Curious gets extra consumables.
- No one gets extra fresh-kill.
- Patient does nothing that the exe knows about. A Blueprint could still use the Patient rows;
  that's not checked.

**A data fix:** adding `Gameplay.Exploration.Trait.Bonus.Curious.FreshKill.Chance` (0.5) and
`.PlusQuantity` (1) rows to `TuningData` would turn the fresh-kill bonus on, but for Curious cats.
Giving it to Patient needs a code or Lua change.

**Bonding:** `Gameplay.Progression.Bonding.TraitModifier` is 1, and what it does isn't traced. It
may reward answers that match your Social trait.
