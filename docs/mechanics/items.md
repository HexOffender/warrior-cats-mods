# Items, herbs and bartering

What the items do and what they cost. Part of the [mechanics notes](README.md).

**Sources:** `Consumables.csv`, `BarteringCost.csv`, `Effects/GenericEffect.csv`,
`Effects/CombatStatBuffEffect.csv`, `UniqueIds/L_WorldMap_01_P.csv` and the enums in the exe.

**Item tags:**
- `Gameplay.Inventory.Consumable.*`: herbs, catnip and pouches.
- `Gameplay.Inventory.Materials.*`: crafting materials and fresh-kill.
- `Gameplay.Inventory.Cosmetic.<Head|Neck|Body|Legs>.*`: accessories.
- `Gameplay.Inventory.Decoration.<n>`: den decorations (see [clan-life.md](clan-life.md#dens)).

`EItemRarity`: Common, Uncommon, Rare, Mythic.

A mod can add herbs and materials of its own with `items.json` ([SDK.md, New items](../SDK.md#new-items-itemsjson)). What
makes an item, and how accessories are listed, is in
[reverse-engineering.md](../reverse-engineering.md#items).

## What consumables do

Each consumable runs an effect, `Gameplay.Effect.Consumable.<X>`. Its numbers are in the
parameter row of the same name, `Gameplay.Params.<X>` (matched by name):

| Item | Where | On | Effect |
|---|---|---|---|
| Small Healing Herb | anywhere | you | +25 health |
| Medium Healing Herb | anywhere | you | +50 health |
| Big Healing Herb | anywhere | you | +100 health |
| Full Healing Herb | anywhere | you | full health (100%) |
| Super Healing Herb | anywhere | you | `Health.FullRecover` (no parameter row; probably full health and cures) |
| Healing Herb Pouch | anywhere | your team | +50 health each |
| Small / Medium / Big Catnip | combat | you | +25 / +50 / +100 stamina |
| Catnip Pouch | combat | your team | +50 stamina each |
| Thistle Pouch | combat | your team | +50% Strength for the fight |
| Fish Scale Pouch | combat | your team | +50% Resilience for the fight |
| Cat Thyme Pouch | combat | your team | +50% Instinct for the fight |
| Feather Pouch | combat | your team | +50% Agility for the fight |
| Herb Spices Pouch | combat | you | "Berserk" (`Buff.Berserk.1`, no parameter row) |
| Eyewort / Chamomile / Antidote Herb / Valerian Root Pouch | combat | your team | cures Blinded / Furious / Poisoned / Stressed |
| Peppermint / Ginger Root / Chestnut / Lavender / Turmeric Pouch | combat | your team | +0.25 to the Offensive / Defensive / Trick / Sneaky / Reckless stance multiplier for 1 round |
| Sage Pouch | exploring | you | +200 XP |

- **`bRemoveAfterCombat`:** the combat-only pouches are marked with it, so their effects end with
  the fight.
- **Unused parameter rows:** `Params.Stamina.4` (+20%), `Stamina.FullHeal`, `MaxHealth.1` (+50%)
  and stronger stance buffs (`Buff.<Stance>.2`, +0.5) exist, but no consumable uses them.

`ESwtAdventureConsumableType` lists the kinds in the same order: Health, Stamina, BuffStrength,
BuffResilence, BuffInstinct, BuffAgility, BuffBerserk, the four antidotes, the five stance moves,
and Exp.

## Where items come from

- **Pickups** in the world give what they're named after, except the rarer herbs and pouches.
  Those give their main ingredient instead:
  - Big Healing Herb gives Comfrey, Full gives Goldenrod and Super gives Broom.
  - Herb Spices gives Willow, Lavender Borage, Chestnut Thyme, Ginger Root Burdock and Peppermint
    Juniper.
  - Counts are in [exploration.md](exploration.md#the-map).
- **Interactables:** clawing, digging and brushing past flowers give materials. What each gives is
  set in its Blueprint, not in the tables.
- **Other sources:** fights, quests, den visits, online gifts and bonding rewards (see
  [quests-and-bonding.md](quests-and-bonding.md)).
- **Curious cats** have a 50% chance of +1 on each consumable they get (see
  [progression.md](progression.md#what-traits-do-in-play)).

**The 27 materials:** Berry Fern, Birdnest, Bone, Borage, Broom, Burdock, Cattail Reed, Cobwebs,
Comfrey, Cotton, Dandelion, Dirt Mound, Fur, Goldenrod, Heather, Ivy, Juniper, Leaves, Moss, Oak
Gall, Pine, Poppy, Rock, Rope, Sharpening Tree Bark, Thyme and Willow.

## Bartering

The medicine cat barters, through the "Bartering" answer in their dialogue.

`BarteringCost.csv` gives the materials each item costs: 24 consumables (all but the Sage Pouch)
and 31 accessories (8 head, 4 neck, 11 body, 8 leg). No row is hidden (`bIsHidden`).

<!-- table:barter -->
| Item | Cost |
|---|---|
| Consumable.SmallHealingHerb | 3 Dandelion |
| Consumable.MediumHealingHerb | 6 Dandelion, 2 BerryFern |
| Consumable.BigHealingHerb | 1 Comfrey, 3 Dandelion, 1 Leaves |
| Consumable.FullHealingHerb | 1 Goldenrod, 1 Heather, 1 Heather |
| Consumable.SuperHealingHerb | 1 Broom, 1 Oakgall, 1 Fur |
| Consumable.HealingHerbPouch | 1 SharpeningTreeBark, 1 Birdnest, 2 Cobwebs |
| Consumable.SmallCatnip | 3 Poppy |
| Consumable.MediumCatnip | 6 Poppy, 2 Pine |
| Consumable.BigCatnip | 2 CattailReed, 1 BerryFern, 1 Rock |
| Consumable.CatnipPouch | 3 Moss, 2 Heather, 2 Fur |
| Consumable.ThistlePouch | 1 Rock, 1 Bone, 1 SharpeningTreeBark |
| Consumable.FishScalePouch | 1 SharpeningTreeBark, 1 Cobwebs, 1 Birdnest |
| Consumable.CatThymePouch | 1 CattailReed, 1 Fur, 1 Pine |
| Consumable.FeatherPouch | 2 Cotton, 1 Leaves, 1 Oakgall |
| Consumable.HerbSpicesPouch | 1 Moss, 3 Poppy, 1 Ivy |
| Consumable.EyewortPouch | 3 Dandelion, 1 Moss |
| Consumable.ChamomilePouch | 3 Cotton, 1 Oakgall |
| Consumable.AntidoteHerbPouch | 1 Moss, 2 Cobwebs |
| Consumable.ValerianRootPouch | 1 Fur, 1 Birdnest |
| Consumable.PeppermintPouch | 1 Juniper, 1 Rock, 1 Bone |
| Consumable.GingerRootPouch | 1 Burdock, 1 SharpeningTreeBark, 1 Cobwebs |
| Consumable.ChestnutPouch | 1 Thyme, 1 CattailReed, 1 Rope |
| Consumable.LavenderPouch | 1 Borage, 1 Moss, 1 Fur |
| Consumable.TurmericPouch | 1 Willow, 1 Birdnest, 1 Cobwebs |
| Cosmetic.Head.DandelionHeaddress.1 | 5 Dandelion, 1 Leaves, 1 BerryFern |
| Cosmetic.Head.DryPoppyCrown.1 | 4 Poppy, 1 Leaves, 1 Ivy |
| Cosmetic.Head.SkullCap.1 | 2 Bone, 6 Cobwebs, 4 Rock |
| Cosmetic.Head.MapleLeaf.1 | 3 BerryFern, 3 Ivy, 3 Heather |
| Cosmetic.Head.SharpBonePiercing.1 | 2 Bone, 4 DirtMound, 3 Pine |
| Cosmetic.Head.WildFlowersPendant.1 | 9 Dandelion, 7 Poppy, 2 BerryFern |
| Cosmetic.Head.BigLeaf.1 | 2 BerryFern, 2 Leaves, 3 Moss |
| Cosmetic.Head.MossPatch.1 | 3 Moss, 2 Ivy, 3 DirtMound |
| Cosmetic.Neck.DogCollar.2 | 2 Bone, 1 Rope, 10 Poppy |
| Cosmetic.Neck.RopeNecklace.1 | 1 Rope, 5 Cotton, 2 Fur |
| Cosmetic.Neck.ShellCollar.2 | 6 CattailReed, 4 Rock, 1 Rope |
| Cosmetic.Neck.SnailNecklace.2 | 4 CattailReed, 3 Ivy, 1 Rope |
| Cosmetic.Body.SpikySeeds.1 | 2 Pine, 2 Leaves, 2 Berryfern |
| Cosmetic.Body.SpikySeeds.2 | 2 Pine, 3 DirtMound, 3 Moss |
| Cosmetic.Body.LittleLeaves.2 | 7 Poppy, 2 Leaves, 2 Heather |
| Cosmetic.Body.HeatherPetals.1 | 3 Heather, 3 Leaves, 3 Berryfern |
| Cosmetic.Body.HeatherPetals.2 | 11 Dandelion, 2 Birdnest, 2 Fur |
| Cosmetic.Body.PineNeedles.1 | 3 Pine, 2 Fur, 3 Leaves |
| Cosmetic.Body.PineNeedles.2 | 3 Pine, 3 SharpeningTreeBark, 8 Poppy |
| Cosmetic.Body.YellowPrimroses.1 | 11 Dandelion, 2 Birdnest, 6 Cotton |
| Cosmetic.Body.YellowPrimroses.2 | 3 Heather, 11 Dandelion, 3 Berryfern |
| Cosmetic.Body.MudMarks.1 | 4 Cobwebs, 4 Moss, 3 DirtMound |
| Cosmetic.Body.MudMarks.2 | 4 Moss, 4 Cobwebs, 3 Ivy |
| Cosmetic.Legs.GreenBrier.2 | 7 Poppy, 2 Leaves, 1 Birdnest |
| Cosmetic.Legs.GreenBrier.3 | 2 Birdnest, 4 Moss, 3 Berryfern |
| Cosmetic.Legs.GreenBrier.4 | 4 Cattailreed, 4 DirtMound, 2 Bone |
| Cosmetic.Legs.PaleStalkBangle.2 | 3 Cattailreed, 5 Cotton, 1 Rope |
| Cosmetic.Legs.PaleStalkBangle.3 | 4 Moss, 4 Cobwebs, 3 Rock |
| Cosmetic.Legs.OakWrap.1 | 2 SharpeningTreeBark, 1 Oakgall, 2 Leaves |
| Cosmetic.Legs.OakWrap.2 | 4 Moss, 7 Cotton, 1 Rope |
| Cosmetic.Legs.OakWrap.3 | 4 SharpeningTreeBark, 4 Heather, 3 Fur |
<!-- /table -->

**Data quirks:**
- **Full Healing Herb** lists Heather twice (1 + 1).
- **Spelling:** some accessory rows write `Berryfern` and `Cattailreed`. Gameplay tags compare
  without case, so these still match.
