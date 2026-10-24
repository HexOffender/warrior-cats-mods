# Clan cats: how NPCs are made

How the game fills each clan with cats: how many of each role, their size, scars, looks and
names. Part of the [mechanics notes](README.md). Names are covered in more depth in
[reverse-engineering.md](../reverse-engineering.md#names).

**Sources:** `NPC/*.csv` and `TuningData.csv` (`NPC.Heterochromia.Chance`). They're used by the NPC
generation manager (`BP_WrcNPCGenerationManager_C < WrcNPCGenerationManager <
SwtAdventureNPCGenerationManager`). `EGiverRole` lists the roles: Kit, Apprentice, Elder,
Warrior, MedicineCat, Queen, Deputy, Leader, StarClanAncestor, RogueCat, RogueCatLeader, Dead and
Manifestation.

## How many cats

`<Clan>NpcGenerator.csv` sets how many cats of each role to make. Each clan's table has a column
per clan, so a clan's world can hold cats of others:

| Role | ThunderClan | ShadowClan | RiverClan | WindClan |
|---|---|---|---|---|
| Kit | 5 | 4 | 4 | 4 |
| Apprentice | 1 | 1 | 1 | 1 |
| Elder | 1 | 1 | 1 | 1 |
| Warrior | 11 (+1 ShadowClan) | 10 | 10 | 12 |
| Medicine cat | 1 | 1 | 1 | 1 |
| Queen | 1 | 1 | 1 | 1 |
| Deputy | 1 | 1 | 1 (+1 ThunderClan) | 1 |
| Leader | 1 | 1 | 1 (+1 ThunderClan) | 1 |
| StarClan ancestor | 1 | 1 | 1 | 1 |
| Rogues (no clan) | 0 | rogue leader 1 | rogues 2, rogue leader 1 | rogue 1 |

These are the generated cats. The story cast (`NarrativeRole.csv`) comes on top (see
[quests-and-bonding.md](quests-and-bonding.md#the-story-cast)).

## Size

`CatSize.csv` gives each role a scale range:

| Role | Scale |
|---|---|
| Kit | 0.10–0.15 |
| Apprentice | 0.40–0.50 |
| Elder | 0.65–0.75 |
| Warrior, medicine cat, queen, deputy, rogue | 0.70–0.80 |
| Leader, StarClan ancestor, rogue leader | 0.90–1.00 |

The player's size goes by rank instead: 0.45, 0.7, 0.8 and 1.0 (see
[progression.md](progression.md#ranks)). The npc-size-variety example in [wcmods-examples](https://github.com/HexOffender/wcmods-examples) widens these ranges.

## Scars

`Scars.csv` gives the chance of an ear, body and eye scar by role:

| Role | Ear | Body | Eye |
|---|---|---|---|
| Kit, apprentice | 0 | 0 | 0 |
| Warrior, medicine cat, queen | 10% | 5% | 0 |
| Deputy | 75% | 10% | 0 |
| Leader | 85% | 50% | 0 |
| Elder | 85% | 50% | 50% |
| StarClan ancestor (of a clan) | 95% | 75% | 25% |
| StarClan ancestor (outside the clans) | 100% | 85% | 50% |
| Rogue, rogue leader | 50% | 50% | 50% |

Your own cat gets scars from boss fights (see [combat.md](combat.md#dilemmas-and-the-warrior-code)).

## Looks

Each body part has a weight table per clan: `BodyType`, `FaceType`, `EarType`, `EyeType`,
`TailType`, `WhiskerType` and `FurType` (10 options), `PatternType` and `MarkingType` (21), and
`FurBaseColor`, `FurPattern1Color`, `FurPattern2Color`, `Eye1Color` and `Eye2Color` (20). A
weight of 0 means a clan never gets that option. Options below are counted from 1, in table
order (the game's own indexes start at 0).

**What stands out:**
- **NPCs only get body types 6–10.** Every clan's `BodyType` row is 0 for options 1–5. Since
  traits come from body, ears and face, NPC traits lean the same way (see
  [reverse-engineering.md](../reverse-engineering.md#character-creation-and-traits)).
- **Faces differ by clan.** ShadowClan and WindClan faces are options 1–7, ThunderClan's 3–9 and
  RiverClan's 4–10.
- **Coats differ by clan.** `FurBaseColor`:
  - RiverClan is mostly coats 9, 11 and 13 (0.2–0.3 each);
  - ShadowClan's most common is 15 (0.3);
  - WindClan's are 2, 8 and 12 (0.2 each).
  - Options 16–20 have weight 0 everywhere, so NPCs don't get them.
- **Markings:** only 8 of the 21 markings are ever used, at 0.1 each (options 1, 2, 7, 9, 10, 11,
  14 and 20; the weights add up to 0.8).
- **Eyes:** each clan has five eye colours at 0.2. Cats outside the clans have a wider spread. `Eye2Color` is the same as `Eye1Color`, and a
  cat gets two different eyes 15% of the time (`NPC.Heterochromia.Chance`).
- **Banned patterns:** `PatternBanList.csv` names 11 patterns kept off NPCs: gentleman 15, motted
  7, sprinkled 8, leopard 10, calico 11, tortoiseshell 12, pirate 16, lovely 17, bandid 18, starry 19
  and chimera 20.
- **Kits' looks:** `ForcedAppearance.csv` has one row, Kit: body (6,7,8,9), fur (2,3,4,5), eyes
  (0,1,2,3), ears (1,2,3,4), whiskers (1,2,3,4), tail (0,1,2,3,5) and face (0,1,2,3). These are
  probably the only options a kit can get.

## Names

- **Clan cats:** a prefix from `PreffixName.csv` (89, weighted per clan) and a suffix from
  `SuffixName.csv` (26, one set per role: -kit, -paw, a warrior suffix, -star).
- **Rogues:** a whole name from `RogueNames.csv` (22).
- **Banned names:** `NameBanList.csv` keeps 30 canon names (Tigerstar, Jayfeather, Lionblaze …)
  from being generated.
- **Your cat's name suggestions:** the name screen scores prefixes with `PrefixNameFilters.csv`
  (clan and looks) and suffixes with `SuffixNameFilters.csv` (traits too).
