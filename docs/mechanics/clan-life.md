# Clan life: fresh-kill, dens, visits and gifts

The clan's food supply, building up your den, and what visits and online gifts hand out. Part of
the [mechanics notes](README.md).

**Sources:** `TuningData.csv` (`FreshKillPile.*`, `Housing.*`), `Effects/GenericEffect.csv`,
`HousingCost.csv`, `VisitRewards.csv`, `OnlineGifts.csv`, the save, and the exe's strings and
enums.

## The fresh-kill pile

Each camp has a pile (`BP_FreshKill_Pile_<Clan>_C < SwtAdventureFreshKillPileActor`) with a value
from 0 to 100. The fresh-kill cat (`BP_Quest_Giver_FreshKill_C < SwtAdventureFreshKillActor`)
takes your prey.

| | Value |
|---|---|
| Starts at | 100 (`InitialValue`) |
| Most it holds | 100 (`Cap`) |
| Goes down | 1 every 90 s (`Decay.Value`, `Decay.Time`), so a full pile empties in 2.5 hours of play |
| Cycles | `ResetCycles` 6 (meaning not traced) |

The exe names these five keys itself. The save keeps the pile as
`"FreshKill": {"Value": 92, "Timer": 3.93, "Cycle": 0}`, where `Timer` counts toward the next drop.

**What prey is worth** (`FreshKillPile.<Prey>`):

| Mouse | Bird | Squirrel | Fish | Rat | Rabbit |
|---|---|---|---|---|---|
| 1 | 2 | 3 | 3 | 4 | 5 |

Fresh-kill items are `Gameplay.Inventory.Materials.FreshKill` ("Mouse Fresh-kill", "Bird
Fresh-kill" …).

**How full the pile is changes your cat's stats.** Each level has a bonus in
`Effects/GenericEffect.csv` (`Gameplay.Exploration.FreshKillPile.Bonus.<Level>.<Stat>`):

| Level | Pile at least | Agility | Prowess |
|---|---|---|---|
| Full | 90 | +10% | +10% |
| Abundant | 70 | +5% | +5%, but see below |
| Good | 50 | 0 | 0 |
| Scarcity | 25 | -5% | -5% |
| Critical | 0 | -10% | -10% |

- **A data bug:** the Abundant Prowess row is named `Gameplay.Exploration.FreshKillPile.Bonus.Abundantv`,
  not `…Abundant.Prowess`. A lookup by the right name won't find it, so an Abundant pile probably
  gives no Prowess bonus. Where these rows are read isn't traced (not in the exe as whole names).
- **Getting more:** the "A Final Show of Strength" dilemma can double a fight's fresh-kill
  (`Params.Dilemma.13.B.FreshKillMultiplier` 2).
- **The trait bonus doesn't work** (see
  [progression.md](progression.md#what-traits-do-in-play)).

## Dens

Den entrances are `BP_Housing_DoorActor_C` (64 on the main map, plus 5 `BP_Housing_MultiRank_DoorActor`).
Inside, you build decorations on hotspots.

**Hotspots:**
- **Their states** (`HousingHotspotStatus`): None, InProgress (building), ReadyToAdd, Built.
- **Their sizes:** decoration sizes are `HousingDecorationSize`: Tiny, Pendant, Medium, Large and
  Interactable. A hotspot's size setting is Tiny 8, Pendant 6, Medium 14, Large 20 and
  Interactable 10, and its marker effect is scaled 0.5 to 1.5 to match.
- **Whose den:** `HousingElementMode` is Owner or Guest, for your den and for visiting another
  player's.

**Building:** a decoration costs materials (`HousingCost.csv`) and takes its `BuildTime`:
- Common ones are instant, and so is one rare one.
- Uncommon take 4800, Rare 14400 and Mythic 57600: 1 hour 20 minutes, 4 hours and 16 hours, if these are
  seconds.
- They are probably seconds of real time, like the online den features, but that isn't checked.

**Help from friends:** `Housing.Hotspot.Assist.Time` 86400 (a day) and `.Assist.Quote` 1800 (half
an hour). A guess: a visitor's help takes 30 minutes off a build, once a day.

**Using decorations:**
- Beds play a sleep animation, scratching posts a sharpen animation, and toys a play animation
  for 1.5 s (`Housing.Hotspot.Play.Time`).
- Toys attach to the cat's `camera_ref` bone.
- `MaxQuantity` is 1 for most decorations, and unlimited (-1) for the cheap beds.

The names are `STR_ITEM_DECORATION_<n>`. Matching them to `Decoration.<n>` by number fits every
row: the beds are nests and mats, the scratching ones are bark and stone, and the toys are cones
and balls.

<!-- table:decorations -->
| # | Name | Kind | Rarity | Build time | Max | Cost |
|---|---|---|---|---|---|---|
| 1 | Golden Hay Nest | Medium, bed | Common | 0 h | any | 3 Dandelion, 1 BerryFern, 1 Moss |
| 2 | Leaf-Fall Mat | Medium, bed | Common | 0 h | any | 1 Leaves, 1 Heather, 1 Ivy |
| 3 | Ivy Weave Basket | Medium, bed | Common | 0 h | any | 1 Ivy, 1 Pine, 1 Birdnest |
| 4 | Pine Needle Cushion | Medium, bed | Uncommon | 4 h | any | 1 Pine, 3 Cotton, 1 Fur |
| 5 | Velvet Moss Mat | Medium, bed | Uncommon | 4 h | any | 2 Moss, 1 Fur, 1 Heather |
| 6 | River Reed Cradle | Medium, bed | Uncommon | 4 h | any | 2 CattailReed, 1 Birdnest, 1 Oakgall |
| 7 | Fern Frond Bed | Medium, bed | Uncommon | 4 h | 1 | 1 BerryFern, 1 Leaves, 2 Cobwebs |
| 8 | Bog Cotton Cloud | Medium, bed | Rare | 12 h | 1 | 4 Cotton, 2 Fur, 3 CattailReed |
| 9 | Shadow Moss Braid | Medium, bed | Uncommon | 4 h | 1 | 2 Moss, 1 Rope, 1 BerryFern |
| 10 | Tall Grass Hammock | Medium, bed | Uncommon | 4 h | 1 | 1 Leaves, 3 Cotton, 2 Cobwebs |
| 11 | Shepherd’s Wool Fleece | Large, bed | Rare | 0 h | any | 1 Leaves, 1 BirdNest, 1 Oakgall |
| 12 | Bunny Soft Down | Large, bed | Mythic | 48 h | 1 | 2 Fur, 3 CattailReed, 7 Poppy |
| 13 | Cotton Terry Tangle | Large, bed | Mythic | 48 h | 1 | 5 Cotton, 1 Rope, 1 Birdnest |
| 14 | Forest Pelt Rug | Large, bed | Mythic | 48 h | 1 | 2 Fur, 5 Cotton, 9 Dandelion |
| 15 | Purple Heather Loft | Large, bed | Mythic | 48 h | 1 | 2 Heather, 2 Ivy, 2 Rock |
| 16 | Rough Pine Barker | Medium, scratching | Common | 0 h | 1 | 1 Pine, 1 Bone, 1 Moss |
| 17 | Weathered Pine Stump | Medium, scratching | Uncommon | 4 h | 1 | 2 Cobwebs, 1 SharpeningTreeBark, 1 Rock |
| 18 | Sun-Bleached Driftwood | Medium, scratching | Common | 0 h | 1 | 1 SharpeningTreeBark, 1 DirtMound, 3 Dandelion |
| 19 | Ancient Marrow Bone | Medium, scratching | Mythic | 48 h | 1 | 1 Bone, 2 Rock, 3 DirtMound |
| 20 | Lichen Crust Rock | Medium, scratching | Common | 0 h | 1 | 1 Rock, 1 Moss, 2 Cotton |
| 21 | Gnarly Root Block | Medium, scratching | Mythic | 48 h | 1 | 1 Oakgall, 3 CattailReed, 3 DirtMound |
| 22 | Pressed Earth Peat | Large, scratching | Rare | 12 h | 1 | 2 DirtMound, 4 Cotton, 1 Birdnest |
| 23 | Primordial Fossil Stone | Large, scratching | Mythic | 48 h | 1 | 2 Rock, 1 Oakgall, 7 Poppy |
| 24 | Great Hart Antler | Large, scratching | Mythic | 48 h | 1 | 1 Bone, 2 Rock, 1 Rope |
| 25 | Tough Canvas Scrub | Large, scratching | Mythic | 48 h | 1 | 2 Fur, 1 Rope, 5 Cotton |
| 26 | Plush Pillow Punch | Large, scratching | Mythic | 48 h | 1 | 5 Cotton, 2 Fur, 1 Rope |
| 27 | Seasoned Firewood Log | Large, scratching | Uncommon | 4 h | 1 | 1 SharpeningTreeBark, 2 DirtMound, 2 Cobwebs |
| 28 | Algae-Grip Stone | Large, scratching | Mythic | 48 h | 1 | 3 Moss, 2 Rock, 7 Poppy |
| 29 | Charcoal Smudge Stick | Large, scratching | Rare | 12 h | 1 | 2 Rock, 2 SharpeningTreeBark, 7 Dandelion |
| 30 | Sturdy Wooden Post | Large, scratching | Rare | 12 h | 1 | 2 SharpeningTreeBark, 2 Leaves, 2 Ivy |
| 31 | Moon-Polished Pebble | Tiny | Rare | 12 h | 1 | 2 Rock, 7 Dandelion, 5 Poppy |
| 32 | Silver Song Bell | Pendant | Mythic | 48 h | 1 | 9 Dandelion, 7 Poppy, 5 Cotton |
| 33 | Rainbow Jewelry Beads | Pendant | Mythic | 48 h | 1 | 2 Rock, 1 Rope, 2 BerryFern |
| 34 | Neon Tangle Laces | Pendant | Rare | 12 h | 1 | 1 Rope, 3 Cobwebs, 2 Fur |
| 35 | River Jewel Glass | Tiny | Mythic | 48 h | 1 | 3 CattailReed, 2 Rock, 1 Rope |
| 36 | Badger Talon Relic | Tiny | Rare | 12 h | 1 | 2 Fur, 1 Rope, 1 Bone |
| 37 | Wolf Tooth Charm | Tiny | Mythic | 48 h | 1 | 1 Bone, 2 Fur, 1 Rope |
| 38 | Shimmering Snake Skin | Tiny | Rare | 12 h | 1 | 3 Moss, 1 Rope, 1 Oakgall |
| 39 | Tiny Rat Skull | Tiny | Rare | 12 h | 1 | 1 Bone, 1 Oakgall, 7 Dandelion |
| 40 | Glittering Creek Lure | Pendant | Mythic | 48 h | 1 | 2 Rock, 2 Pine, 3 CattailReed |
| 41 | Spiral Sea Shell | Tiny | Mythic | 48 h | 1 | 1 Bone, 3 CattailReed, 1 Oakgall |
| 42 | Painted Wing Beauty | Pendant | Mythic | 48 h | 1 | 1 Birdnest, 2 Fur, 5 Cotton |
| 43 | Twin-Point Antler | Tiny | Mythic | 48 h | 1 | 1 Bone, 2 Fur, 3 Cobwebs |
| 44 | Silk Weaver Spider | Pendant | Mythic | 48 h | 1 | 3 Moss, 1 Bone, 2 Ivy |
| 45 | Spiral Shell Traveler | Pendant | Rare | 12 h | 1 | 1 Bone, 3 CattailReed, 1 Rope |
| 46 | Crown Bottle Cap | Tiny | Mythic | 48 h | 1 | 2 Rock, 9 Dandelion, 2 Heather |
| 47 | Secret-Gate Key | Pendant | Rare | 12 h | 1 | 2 Rock, 3 Moss, 1 Birdnest |
| 48 | Wild Bird Feathers | Tiny | Mythic | 48 h | 1 | 1 Birdnest, 2 Fur, 3 Cobwebs |
| 49 | Colorful Thread Snarl | Tiny | Mythic | 48 h | 1 | 1 Rope, 7 Poppy, 3 Cobwebs |
| 50 | Giant’s Oak Marble | Tiny | Rare | 12 h | 1 | 1 Oakgall, 2 Rock, 2 Heather |
| 51 | Woody Oak Gall | Tiny | Rare | 12 h | 1 | 1 Oakgall, 2 SharpeningTreeBark, 2 Ivy |
| 52 | Glittering Moonstone Shard | Tiny | Mythic | 48 h | 1 | 2 Rock, 7 Poppy, 1 Birdnest |
| 53 | Dried Poppy Rattle | Tiny | Rare | 12 h | 1 | 5 Poppy, 1 Oakgall, 2 Leaves |
| 54 | Silken Streamer Ribbon | Pendant | Mythic | 48 h | 1 | 1 Rope, 5 Cotton, 7 Poppy |
| 55 | Spiky Pine Cone | Interactable, toy | Rare | 12 h | 1 | 2 Pine, 2 Leaves, 2 Ivy |
| 56 | Rolling Straw Ball | Interactable, toy | Rare | 12 h | 1 | 1 Birdnest, 2 Pine, 2 BerryFern |
| 57 | Amber Resin Globe | Interactable, toy | Mythic | 48 h | 1 | 2 Rock, 1 Oakgall, 3 Cobwebs |
| 58 | Wild Briar Nest | Interactable, toy | Rare | 12 h | 1 | 1 Birdnest, 1 Rope, 2 BerryFern |
| 59 | Fern Knot Tangle | Interactable, toy | Rare | 12 h | 1 | 2 BerryFern, 1 Rope, 3 Cobwebs |
| 60 | Sailor’s Rope Knot | Interactable, toy | Rare | 12 h | 1 | 1 Rope, 3 CattailReed, 1 Birdnest |
<!-- /table -->

## Den visits

Visiting a den hands out a random item from `VisitRewards.csv`:

| Item | Weight | Chance |
|---|---|---|
| Medium Healing Herb | 2 | 1 in 6 |
| Medium Catnip | 2 | 1 in 6 |
| Thistle, Fish Scale, Cat Thyme, Feather Pouch (stat buffs) | 1 each | 1 in 12 each |
| Eyewort, Chamomile, Antidote Herb, Valerian Root Pouch (cures) | 1 each | 1 in 12 each |

The table also lists every other consumable and every combat move at weight 0, so they never come
up.

## Online gifts

`OnlineGifts.csv` gives 1–30 of a random item. All 22 entries have the same weight: Small and
Medium Healing Herb, Small and Medium Catnip, and 18 materials (Dandelion, Poppy, Berry Fern,
Leaves, Heather, Pine, Cattail Reed, Cotton, Dirt Mound, Fur, Sharpening Tree Bark, Bone, Rope,
Oak Gall, Bird Nest, Moss, Rock and Cobweb).

**A data bug:** the last entry is `Gameplay.Inventory.Materials.Cobweb`, but every other table
spells the item `Materials.Cobwebs`. Unless a `Cobweb` tag also exists, that gift gives nothing.
