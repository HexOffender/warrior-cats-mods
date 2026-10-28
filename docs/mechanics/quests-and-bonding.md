# Quests, dialogue and bonding

The kinds of quests, how dialogue answers are scored, and what bonding with a cat gives you. Part
of the [mechanics notes](README.md).

**Sources:** `QuestDialogues.csv` (1215 rows), `StoryDialogues.csv` (2937),
`QuestDynamicObjectives.csv`, `QuestObjectives.csv`, `QuestGossipCost.csv`,
`NPC/NarrativeRole.csv`, `CombatDilemmas.csv`, `TuningData.csv` (`Progression.Bonding.*`) and the
save. How the numbers are used is inferred from the data; of the quest code, only how it fills
dialogue in from the tables has been read (below).

## Kinds of quest

**Main story:** `Quest.Main.<n>`, `Quest.Rank.<n>` and the tutorial `Quest.Chapter00.MQ<n>`
(`QuestObjectives.csv` has its fixed objectives). The save records each quest's `Status`,
`Result`, `Giver` and `UsedObjectiveRank`.

**Procedural quests** (`Quest.Procedural.<Family>.<Kind>.<Rank>`) are given by clan cats. Their
text comes in versions for each rank:

| Family | Kinds |
|---|---|
| Survival | Gather (collect 3 herbs from a list), Hunt |
| Combat | Defend, MarkTerritory (3 markers), ChaseOff, Patrol, Rescue, BossDefend |
| Progression | Escort, Deliver, Recruit, RankUp / RankUp2 / RankUp3, StarClan, and three unique quests per clan (`<Clan>.Unique1..3`, for Apprentice, Deputy and Leader) |
| Discovery | FindLocation, FindItem |
| Sleep | Rest1 … Rest13 |

**Side quests** (`Quest.Procedural.SideQuest.*`) come in sets of 16, each with a target
(`QuestDynamicObjectives.MaxQuantity`):
- **Milestones:** Pounce, Climb, and three combat challenges (NoHerbs, NoTricks, NoDefensive).
  Targets run 1–5.
- **Collect** (2–3 items), **WinFights** (1–3) and **Trading** (1–2).
- **Race:** the targets are 60, 75 or 120, probably seconds. The map has 44 `BP_RaceTrigger`s.

**Gossip:** `QuestGossipCost.csv` gives a cost to each side quest's hint. All 112 are empty, so
gossip is free.

## Dialogue answers and their scores

Each player line has a `Score`, a `ClanBonding` and a `Trait`. The trait is one of the three
Social traits: Brave, Ambitious or Wise. It also picks the voice (`vo_dialog_brave` …).

**Procedural quest dialogue** offers one answer per Social trait:

| Answer | Score | ClanBonding |
|---|---|---|
| Best | +6 | +2 |
| Middling | +3 | +1 |
| Worst | 0 | 0 |

Which trait's answer is best changes from quest to quest.

**Story conversations** (`Gameplay.Dialogue.Story.<Short|Long>.<Character>.<Main|Unique>.<n>`)
ask two or three questions. Each question has three answers, and each answer has a short and a
long line:

| Answer | Score | ClanBonding |
|---|---|---|
| Right | +9 | +2 |
| Neutral | 0 | 0 |
| Wrong | -3 | -4 |

The NPC replies to each answer (`Context.2.Right` …), and the conversation ends with
`Context.End.<Right|Wrong|Neutral>`.

**Monologues** (`Gameplay.Dialogue.Story.Monologue.<Filler|Interaction|Encounter>.<Character>…`)
have Positive, Neutral and Negative versions, and each gives +1 clan bonding. The version is
probably picked by your bonding.

**How the tables reach a conversation** (read from the graphs and the code; the reverse-engineering
notes, *Dialogue graphs*):
- Story and quest conversations are templates the quest manager fills in as they play. A story tag picks
  its template by its kind: Short and Long the first time and `End` after, Interaction 1 to 3 on the first
  three talks, Filler, Encounter or Activity Transition.
- Each line is the row `<tag>.<SubTag>` (story) or `<quest>.<AutoFillSuffix>` (quest). Its `Talker` says
  who speaks and its `StringKey` the words (`DebugText` only when the key is missing).
- An answer button takes its `Trait`, `Score` and `ClanBonding` from its row. So the scores above are
  the ones the game puts on the buttons; what it does with them after is still the open question below.
- A cat's own talks are graphs the quest sublevels place: one root per quest state (`Quest.Main.1.0`,
  `Quest.Main.1.Complete`…), each starting a story talk by tag.

**What the scores feed** (inferred):
- `Score` probably adds to your bond with the cat you're talking to.
- `ClanBonding` adds to your standing with the clan.
- `Gameplay.Progression.Bonding.TraitModifier` is 1. It may add to answers that match your own
  Social trait, but that isn't traced.

## Bonding

**Your bond with a cat** goes through four levels (`Bonding.Personal.*`):

| Level | Bond at least |
|---|---|
| Neutral | 10 |
| Friendly | 28 |
| Friend | 46 |
| Close bond | 73 |

- **The starting bond** is each narrative role's `BaseBonding`: 0 for most, 5 for rogues and
  loners, 20 for key characters, and 28 for the Warrior Father and the Queen Mother.
- **Getting there:** at +9 for a right answer, about six right answers take a cat from 20 to
  Close bond.
- **Clan bonding** starts at 67 (`Bonding.Clan.Default`). It counts as Positive from 67 up and
  Negative below 33 (`.Positive`, `.Negative`).
- **The save** keeps a `Bonding` map. It was empty in the save looked at.

**Rewards** (`NarrativeRole.csv`): reaching each level with a key character gives a reward:
- **Friendly:** a single herb or catnip.
- **Friend:** often one of that clan's moves.
- **Close bond:** ten pouches or herbs.

`RewardNeutral` is empty for everyone.

<!-- table:bond_rewards -->
| Clan | Role | Who | Base bonding | Friendly | Friend | Close bond |
|---|---|---|---|---|---|---|
| ThunderClan | TheAgingLeader | ThunderClan Leader | 20 | HealingHerbPouch x1 | move ThunderClan.5 | GingerRootPouch x10 |
| ThunderClan | TheUnchosenApprentice | ThunderClan Apprentice | 20 | BigCatnip x1 | move ThunderClan.2 | ChestnutPouch x10 |
| ThunderClan | TheAmbitiousWarrior | ThunderClan Warrior | 20 | BigHealingHerb x1 | move ThunderClan.4 | LavenderPouch x10 |
| ThunderClan | TheOverprotectiveQueen | ThunderClan Queen | 20 | HealingHerbPouch x1 | move ThunderClan.1 | TurmericPouch x10 |
| ThunderClan | ThunderClanDeputy | ThunderClan Deputy | 20 | BigCatnip x1 | PeppermintPouch x5 | HealingHerbPouch x10 |
| ThunderClan | ThunderClanMedicineCat | ThunderClan MedicineCat | 20 | BigHealingHerb x1 | GingerRootPouch x5 | SuperHealingHerb x10 |
| ThunderClan | ThunderClanWarrior | ThunderClan Warrior | 0 | HealingHerbPouch x1 | TurmericPouch | SuperHealingHerb x10 |
| ThunderClan | ThunderClanElder | ThunderClan Elder | 20 | BigCatnip x1 | PeppermintPouch x5 | HealingHerbPouch x10 |
| RiverClan | TheMistrustfulLeader | RiverClan Leader | 20 | BigHealingHerb x1 | move RiverClan.5 | ChestnutPouch x10 |
| RiverClan | TheRedeemableRogue | None RogueCat | 5 | HealingHerbPouch x1 | move RiverClan.2 | LavenderPouch x10 |
| RiverClan | TheLoner | None RogueCat | 5 | BigCatnip x1 | move RiverClan.4 | TurmericPouch x10 |
| RiverClan | TheRegretfulWarrior | RiverClan Warrior | 20 | BigHealingHerb x1 | move RiverClan.1 | PeppermintPouch x10 |
| RiverClan | RiverClanQueen | RiverClan Queen | 20 | HealingHerbPouch x1 x1 | GingerRootPouch x5 | HealingHerbPouch x10 |
| RiverClan | RiverClanDeputy | RiverClan Deputy | 20 | BigCatnip x1 | ChestnutPouch x5 | SuperHealingHerb x10 |
| RiverClan | RiverClanMedicineCat | RiverClan MedicineCat | 20 | HealingHerbPouch x1 | TurmericPouch | SuperHealingHerb x10 |
| RiverClan | RiverClanElder | RiverClan Elder | 20 | BigCatnip x1 | ChestnutPouch x5 | SuperHealingHerb x10 |
| ShadowClan | TheAmbitiousApprentice | ShadowClan Apprentice | 20 | BigHealingHerb x1 | move ShadowClan.2 | TurmericPouch x10 |
| ShadowClan | TheSelfDoubtingWarrior | ShadowClan Warrior | 20 | BigCatnip x1 | move ShadowClan.4 | PeppermintPouch x10 |
| ShadowClan | TheResentfulElder | ShadowClan Elder | 20 | BigHealingHerb x1 | move ShadowClan.1 | GingerRootPouch x10 |
| ShadowClan | ShadowClanQueen | ShadowClan Queen | 20 | BigCatnip x1 | LavenderPouch x5 | HealingHerbPouch x10 |
| ShadowClan | ShadowClanDeputy | ShadowClan Deputy | 20 | HealingHerbPouch x1 | TurmericPouch | SuperHealingHerb x10 |
| ShadowClan | ShadowClanLeader | ShadowClan Leader | 20 | move ShadowClan.5 | GingerRootPouch x5 | SuperHealingHerb x10 |
| ShadowClan | ShadowClanMedicineCat | ShadowClan MedicineCat | 20 | BigCatnip x1 | LavenderPouch x5 | SuperHealingHerb x10 |
| WindClan | TheProudLoner | None RogueCat | 5 | HealingHerbPouch x1 | move WindClan.5 | PeppermintPouch x10 |
| WindClan | TheWarriorFather | WindClan Warrior | 28 | BigCatnip x1 | move WindClan.2 | GingerRootPouch x10 |
| WindClan | TheZealousWarrior | WindClan Warrior | 20 | BigHealingHerb x1 | move WindClan.4 | ChestnutPouch x10 |
| WindClan | TheInsecureLeader | WindClan Leader | 20 | HealingHerbPouch x1 | move WindClan.1 | LavenderPouch x10 |
| WindClan | TheQueenMother | WindClan Queen | 28 | BigCatnip x1 | TurmericPouch x5 | HealingHerbPouch x10 |
| WindClan | WindClanDeputy | WindClan Deputy | 20 | HealingHerbPouch x1 | TurmericPouch | SuperHealingHerb x10 |
| WindClan | WindClanMedicineCat | WindClan MedicineCat | 20 | HealingHerbPouch x1 | TurmericPouch | SuperHealingHerb x10 |
<!-- /table -->

Data quirk: RiverClanQueen's Friendly reward is `HealingHerbPouch;1;1` (an extra `;1`).

## The story cast

`NPC/NarrativeRole.csv` has 102 roles, 25 or 26 per clan. Each has:
- **Who plays it:** `NPCClan`, `NPCRole` and `NPCIndex`.
- **Iconic cats:** `bIconic` marks the 8 canon cameos, each with a fixed name (`IconicName`,
  `STR_CAT_NAME_ICONIC_<n>`): Brightheart, Mapleshade, Cloudtail, Tawnypelt, Squirrelstar,
  Crowfeather, Ivypool and Tallstar.
- **What can happen to it:** `bCanBeTraitor` and `bCanBeDefender`.
- **Role and clan changes:** `UpdateRole` / `UpdateClan`, e.g. TheAgingLeader is
  `Quest.Rank.3,Dead` (dies at rank quest 3), and the clan's kit is
  `Quest.Rank.1,Apprentice;Quest.Main.6,Warrior`.
- **Voice and moves:** `CatVoice` and its own starting moves.

Most roles are the story's archetypes: TheAgingLeader, TheUnchosenApprentice, TheAmbitiousWarrior,
TheOverprotectiveQueen, TheStarvingWarrior (ShadowClan, the first boss), TheMistrustfulLeader,
TheRedeemableRogue, TheLoner, TheRegretfulWarrior, TheZealousWarrior, TheInsecureLeader,
TheProudLoner, TheWarriorFather, TheQueenMother, TheResentfulElder, TheVengefulRogue and others.
The rest are camp jobs: `…WarriorGossip`, `…WarriorFreshkill`, `…WarriorMoveLearn` (the trainer),
`…WarriorSideQuest`, `…WarriorSkirmish`, `…WarriorOFriends` (online friends), `…WarriorSideRace`,
`…WarriorDelivery1/2`, and the nursery kits.

The save keeps unlocked roles under `Unlocked/NarrativeRoles`, and copies of the cast under
`NPCData/NarrativeRoles` (see [reverse-engineering.md](../reverse-engineering.md#the-save)).

**Narrative dilemmas** are the story's big choices: naming the Unchosen Apprentice a warrior,
choosing a deputy (three versions), and letting the Loner join RiverClan. Each choice carries a
warrior-code value (Loyalty or Respect). See [combat.md](combat.md#dilemmas-and-the-warrior-code).
