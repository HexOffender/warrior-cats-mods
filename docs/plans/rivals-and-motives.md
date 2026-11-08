# Rivals, memories and motives: the plan

Asked by the owner on 2026-11-07:
- "Real time combat, rivals that remember you, and more. So if you kill a kit's parents, they remember and train
  to kill you."
- "I want to give the NPCs more depth and a reason for their behaviour apart from just fulfilling basic needs."

**Approved on 2026-11-07**, with decision 1 changed by the owner: "Killing medicine cats and kits should be seen as
a severe crime, it should be possible but other cats should be critical of it. Going against the clan's code should
carry consequences politically. Top members like a deputy or leader are more likely to get away with it." Then:
"If you are a regular warrior then you should face exile for breaking the warrior code", and "You should also be
able to mate with cats outside of your own clan". Part E is those changes, with the warrior code as the books'
site lists it (https://warriorcats.com/content/article/warrior-code-2).

It builds on three things:
- [Clan life](clan-life.md): every Clan's cats with names, ranks, traits, liking, a day by the clock, moons, mates
  and kits.
- [Real-time combat](https://github.com/HexOffender/wcmods-realtime-combat): fights with animals.
- New SDK calls, listed in Part D and approved with the plan.

The idea of enemies who remember you is the one *Shadow of Mordor* made famous. Warner Bros. holds a US patent on
its "Nemesis system", so this is a design of the mod's own: Warriors cats, Clans, kin and the warrior code, not
that game's orcs, ranks and screens.

## What there is now, and what's missing

- **Clan life's cats choose by needs.** Each has hunger, tiredness, loneliness, comfort and play, two traits, and a
  liking for each other cat. They choose what to do from those, and the deputy's orders. Nothing has happened to
  them: no memories, no goals of their own, no opinion of your cat beyond a bond that talking raises.
- **Fights are with animals only.** Real-time combat fights the game's animals, with health and moves of its own;
  the turn-based fights it replaces pit cats against animals and rogues. The mod's cats can't be fought, and Clan
  life has no deaths (a setting, off).
- **What the game gives us:**
  - Rogues: named (23 names in `RogueNames.csv`), and a rogue leader.
  - Scars on a cat's look.
  - Every cat's fight moves in its montage table, which Real-time combat already plays on animals by tag.
  - Whether rogue cats walk the open world on their own is to be found out (Part D).

## The idea

Every cat has a life story. Things happen to it and it remembers them. It has opinions of the cats around it,
your cat included, and those come from what happened. It wants things (to be deputy, to keep its kits safe, to
prove itself, to settle a score), and those wants decide much of what it does and says. Its needs only decide the
rest.

A cat with a grudge against your cat becomes a **rival**. It grows (it trains, gets scars, rises in its Clan) and it
comes after you. How that ends, by fighting, by sparing or by making peace, becomes part of both your stories, and
of its kin's.

## Part A: a mind for each cat (Clan life)

1. **Memories.** Each cat keeps what happened to it and to those close to it:
   - "Ashfur pulled me out of the river."
   - "Emberpaw killed my mother at the ShadowClan border."
   - "Rookclaw was made deputy when it should have been me."

   Each memory has who, what, where, which moon, and how strongly it was felt. Small ones fade over the moons;
   big ones (a death, a rescue, a betrayal) stay.

   **Witnesses and gossip:** a cat that saw something remembers it too. Big news spreads through the Clan as
   cats share tongues, and to the other Clans at Gatherings. So a killing at the border is known in both camps
   within a moon.
2. **Opinions.** Liking stays. Next to it, for each other cat and for your cat, there's **respect** and **fear**,
   and a **grudge**, all made from memories. A cat can like you, fear you, or respect you while hating you.
3. **Wants (motives).** Each cat has one or two wants at a time, from its traits, its rank and what's happened to
   it. Each comes with what it does about it:

   | Want | What the cat does |
   |---|---|
   | Rise in the Clan (ambitious, proud) | Volunteers for patrols, trains hard, keeps close to the leader, resents whoever got the place it wanted |
   | Keep its kin safe (loyal, kind; queens) | Keeps its kits near, is wary of strangers and of cats it fears, guards the nursery |
   | Prove itself (anxious young cats) | Takes risks on patrol, asks for extra training, wants to be noticed |
   | Avenge someone (a grudge) | Trains to fight, watches for its enemy, asks to patrol where they'll meet |
   | Win a cat's affection | Shares tongues with it, brings it prey |
   | Keep the Clan fed (a good hunter) | Hunts more than it's told to |
   | Make peace, or keep the warrior code (wise, patient) | Calms quarrels, speaks for sparing an enemy |

   Wants change as things happen. One that's met gives way to the next: made deputy, it wants to lead. One
   that's settled gives way to calm, or to a new grudge.
4. **What they say.** A talk draws on a cat's memories, opinions and wants:
   - "You fought well at the border. Brackenfur hasn't stopped talking about it."
   - "I'll be deputy one day. You'll see."
   - "Don't come near my kits."

   The talk box shows lines only until clickable answers come (wcmods' S5).
5. **Between the Clan's own cats too.**
   - Two warriors who want the same place become rivals.
   - A cat whose mate left it is cold to the new pair.
   - Apprentices who trained together stay close.

   You see it in who shares tongues with whom, who patrols together, and what they say.

**Proof:** unit tests for memories fading, opinions following memories, gossip spreading, and wants changing
choices (an ambitious warrior volunteers more than a lazy one). In game, a cat that saw something happen says so,
and the Clan's talk turns to it.

## Part B: fighting cats (Real-time combat, with Part D's SDK step)

- **Who can be fought:** Clan life's cats of other Clans, and rogues, with health, blocks, dodges, hits and the
  cats' own fight moves, as animals are fought now. Kits and medicine cats can be attacked too, and killed, but
  that is the worst of crimes against the warrior code (Part E). A kit doesn't fight back: it cowers or runs. A
  medicine cat defends itself only weakly.
- **What starts a fight:**
  - you trespass, or they do (Clan life's step 7)
  - a border skirmish
  - a rival's challenge or ambush
  - rogues raiding the camp
- **How a fight ends:** a beaten cat **yields** and runs (the warrior code doesn't ask warriors to kill). You
  choose: let it go, or give the killing blow (a held key). Killing is the biggest memory there is, for everyone
  who sees it or hears of it.
- **Several at once:** your cat's blows land on every cat and animal in front of it, so a fight can be with
  several cats at once (the owner's, 2026-11-07).
- **Your party** (next, the owner's, 2026-11-07): up to three clanmates you ask along, who follow you and fight
  beside you. Its own part below, Part B2.
- **What Clan life hears:** Real-time combat tells it what happened: who fought whom, who yielded, who was spared,
  who was killed, who saw it. Real-time combat runs without Clan life too.

**Proof:** in game, a fight with a WindClan warrior that yields; one spared, one killed. Clan life's record shows
both, with their witnesses. (Done: Real-time combat #12, Clan life #7, with wcmods #175 and #176.)

## Part B2: your party (Clan life and Real-time combat)

The game's own party is up to two clanmates the story picks, who only exist in its fights. Here your party is
clanmates of Clan life's, in the forest with you.

- **Asking them along** (Clan life, the Clanmates page): **Come with me** by a clanmate's name, **Send home** for one
  with you. Up to three (a setting, `party_size`).
  - Who says yes: a grown clanmate of your Clan whose bond with you is 40 or more, and who doesn't hold a grudge
    against you. Your mate always comes.
  - Who says no, and why, in its own words: kits; elders; the medicine cat and its apprentice (their duties); a
    queen with kits; the leader (it leads, it doesn't follow), unless you're the deputy; a cat that holds a grudge
    against you; a cat of another Clan.
- **With you:** each walks at your cat's heels wherever you go, out of camp and across the territories, kept in the
  world while the camp's other cats come and go. Left far behind (a fast travel, a teleport), it's put beside you
  again. Its label says "With you". It goes home when you send it, at nightfall, or when you leave the game.
- **In a fight** (Real-time combat). Clan life shares the party's cats (`ClanLife.party`), and Real-time combat
  drives them while a fight lasts, then gives them back:
  - Each goes after a foe: the one you're locked on to, else the one nearest it. It closes in and strikes with the
    cats' quick claw, at a cat's pace. Its blows go through the foes' guards, dodges and counters as yours do.
  - It never fights a cat of its own Clan. Against your clanmates, it stands back. (Part E judges you for that
    fight.)
  - Your blows don't land on it.
  - A foe's swing hurts the party's cats in front of it as it hurts you. Beaten, a party cat goes down until the fight
    is over, then gets up hurt (not killed: deaths stay with Part E's choices).
  - A bar over each one's head shows its health, as for foes.
- **What Clan life hears:** each cat that fought beside you remembers it (a new memory, *fought beside you*: liking
  and respect for you). A clanmate beaten in your fight remembers that too.

**Proof:**
- in game, a clanmate asked along, following your cat out of camp and back; a refusal with its reason; sent home
- a fight with an animal: the party's cats strike it and it's beaten
- a party cat hurt by the animal
- each remembers fighting beside you
- unit tests for who says yes

## Part C: rivals (Clan life)

- **Who becomes one:**
  - kin of a cat you killed (its kits, mate, littermates, mentor or apprentice)
  - a cat you beat and shamed in front of others
  - a cat whose place you took
  - a rogue or an animal that got away from you
- **How they grow:**
  - **Training:** a rival trains whenever it can. Its fighting grows faster than other cats' do, and it picks up
    the moves it has seen you use. It learns your habits: if you always open with the same attack, it learns to
    block it.
  - **Rising:** a Clan rival rises in its Clan, so the kit whose mother you killed can be its deputy one day.
  - **Scars:** each fight with you leaves a scar on it, shown on its look, and remembered in what it says.
  - **Followers:** a rogue rival gathers a band. A Clan rival turns its friends against you.
- **How they come after you:**
  - waiting on your patrol routes
  - an ambush when you're alone in its territory
  - a challenge at the border
  - words at a Gathering: "Tell Emberpaw I haven't forgotten."
- **How it ends:**
  - **Killed:** its own kin may take the grudge up. That's how a feud runs down the moons.
  - **Spared:** by its traits, the grudge softens to a grudging respect ("I owe you a life"), or burns hotter.
  - **Reconciled:** you help its kin, save its life, or talk to it over many moons, and the grudge fades. It may
    even become a friend.
- **An example:**
  1. In a border fight you kill Mosspelt of ShadowClan, and her kit Ashkit hears of it.
  2. As Ashpaw, she asks her mentor for extra battle training.
  3. As Ashclaw, she ambushes you near the Thunderpath. You win and spare her.
  4. She doesn't forgive you, but she won't strike you when you're hurt.
  5. Moons later she's ShadowClan's deputy, and her own kits hear the story from her.
- **Animals:**
  - A fox that got away comes back as "the one-eared fox", scarred, sometimes with its mate.
  - A badger whose den your patrol drove it from comes back.

**Proof:** unit tests for who becomes a rival, a rival's growing and its endings. In game: a rival made by a kill,
growing over moons (sped up with the clock), its ambush, and each ending once.

## Part E: the warrior code, and what breaking it costs

The warrior code is how Clan cats judge each other. Breaking it is possible, for your cat and for the mod's own,
and it has consequences.

- **The code**, as the books' site lists its fifteen rules (in short, in the mod's words):
  1. defend your Clan with your life, friends in other Clans or not
  2. don't hunt or trespass on another Clan's land
  3. elders and kits eat first, and apprentices hunt for the elders before they eat
  4. kill prey only to eat it, and thank StarClan for it
  5. a kit is apprenticed at six moons, not before
  6. a new warrior keeps a silent vigil for a night
  7. only a cat that has mentored an apprentice can be made deputy
  8. the deputy becomes leader when the leader dies or retires
  9. a new deputy is named before moonhigh
  10. no fighting at a Gathering's truce
  11. mark the borders and challenge trespassers
  12. never leave a kit in pain or danger, even another Clan's
  13. the leader's word is law
  14. an honourable warrior doesn't kill to win, except against a code-breaker or to defend itself
  15. no kittypet's soft life

  Clan life already keeps 3, 5, 7, 8 and 9 for the mod's cats, or will, in its ceremonies. The rest can be
  broken.

- **Breaches, from the worst down:**
  - **Severe:**
    - killing a kit or a medicine cat (the books treat both as among the worst things a cat can do, though no
      rule names them)
    - killing a cat that had yielded, or a clanmate (rules 1 and 14)
    - leaving a kit to die (rule 12)
  - **Serious:**
    - killing in a fight that could have ended with a yield (rule 14)
    - attacking at a Gathering (rule 10)
    - defying the leader's order (rule 13)
    - siding with another Clan against your own (rule 1)
  - **Lesser:**
    - hunting or trespassing on another Clan's land (rule 2)
    - eating before the elders and kits (rule 3)
    - killing prey for no reason (rule 4)
    - letting a trespasser go (rule 11)
    - lying about any of these
- **Who knows:** a breach is a memory (Part A), for the cats who saw it and the cats they tell. With no witnesses
  it can stay secret, but a body found with your scent near it starts rumours and suspicion.
- **What it costs:**
  - **Opinions:** every cat that knows thinks less of you; the kind and the wise most of all, the ruthless least.
    Fear rises. The victim's kin start a grudge (Part C).
  - **Standing in your Clan:** Clan life keeps the Clan's regard for each cat, and for your cat, shown on the
    Clanmates page. For your cat it moves the game's own bond with your Clan too (`wcmods::add_bond`).
  - **Between the Clans:** the victim's Clan's regard for your whole Clan drops. Expect angry borders, raids,
    and a Gathering where its leader demands justice.
  - **The leader's judgement** for a known breach:
    - **a warrior is exiled** for a severe or serious breach: the Clan's cats drive it out of camp, and it lives as a
      rogue until it earns its way back (if it can)
    - for a lesser one, a rebuke or punishment duties (ticks for the elders, the dirtplace, no Gathering), and exile
      once the lesser ones add up
    - losing an apprentice, or being handed over to the victim's Clan for its judgement, as the leader's traits
      lean
- **Rank shields a cat.** The higher it stands, the more it gets away with:
  - A **deputy**'s witnesses are slower to speak up, from fear or loyalty, and the leader judges it more lightly.
  - A **leader** judges itself and is never exiled by its own Clan. Its Clan still knows, though. Respect falls,
    loyal cats grow uneasy, a code-minded cat may challenge it or turn to another Clan, and the other Clans may
    unite against it.
  - A **kit or apprentice** is judged as one too young to know better: punished, not exiled for a first breach,
    but watched ever after.
  - A **medicine cat**'s own breach shocks the Clans most, but the Clan needs it: StarClan's judgement is said to
    follow instead, and its standing never recovers.
- **Mates from other Clans.** You can take a mate from another Clan, and so can the mod's cats; you meet at
  Gatherings, at the borders, or on patrol. It isn't a breach by itself (rule 1 allows friends in other Clans),
  but it makes cats doubt your loyalty. Kept secret, it's safe. Once known, your standing falls a little in both
  Clans, and if you ever side with your mate's Clan against your own, that's a serious breach. Your kits are
  raised in the Clan of the one who carried them, and may be teased for being half-Clan.
- **The mod's cats break it too.** An ambitious, ruthless cat may kill a rival to rise (the books' Tigerstar),
  an avenger may kill a yielded enemy, a desperate one may steal prey. The same consequences follow, so the
  Clans have politics of their own: suspicions, exiles, feuds and leaders who lose their Clan's trust.

**Proof:** unit tests for a breach's weight, who comes to know, opinions and standing falling, the leader's
judgement by rank (the same killing judged for a warrior, a deputy and a leader), and the mod's cats choosing a
breach only as their traits and wants allow. In game: a breach witnessed, its news spreading, and a judgement
given.

**In two steps** (the owner's go-ahead, 2026-11-07):

- **E1, your cat's breaches** (Clan life, and a small addition to Real-time combat). Next.
  - **What counts:**
    - from your fights: killing a kit, a medicine cat or a clanmate (severe)
    - giving the killing blow to another Clan's cat that had yielded (serious, rule 14; not if that cat was a
      known code-breaker)
    - striking a kit or a medicine cat (serious)
    - striking a clanmate (lesser)
    - a strike counts only when your cat hits the same cat more than once in a fight: one blow in a crowded fight is
      taken as an accident and forgiven (the owner's, 2026-11-07). Your party's blows aren't yours, and your party
      never goes after a kit or a medicine cat itself
    - an exile's fights with its old Clan aren't breaches, except against kits and medicine cats
  - **Who knows:** the cats who remember it (the witnesses, then gossip). At each dawn, those of your Clan who know
    may tell the leader. A deputy's witnesses are slower to speak (fear, loyalty), the leader always knows its own.
    Word of a killing in another Clan reaches your leader at the next dawn (that Clan demands justice).
  - **The leader's judgement** at that dawn, by your rank (a test switch sets it; the game keeps none for a
    Sandbox mode cat):
    - **warrior** (or queen, elder): exiled for a severe or serious breach. Lesser breaches bring punishment
      duties, and exile at the third.
    - **apprentice or kit:** punished for a first serious or severe breach, exiled for the next
    - **deputy:** stripped of the deputyship and punished for a severe one, rebuked for the rest
    - **leader:** judges itself. Standing falls, nothing more.
    - **medicine cat:** left to StarClan, standing falling furthest
    - a kind or wise leader punishes a warrior's first serious breach instead of exiling it
  - **Standing:** your standing in a Clan is the game's own Clan bond (`wcmods::add_bond`). A judgement lowers it
    in your Clan, and a breach against another Clan's cat lowers it there too. Each Clan's regard for the others is
    kept, falling when your Clan's cat harms one of theirs, and shown on the Allegiances page. Taking a mate from
    another Clan lowers your standing a little in both.
  - **Exile, in play:**
    - your Clan's cats drive you out of its camp: Clan life shares their names (`ClanLife.hostile`), and Real-time
      combat has them fight you as it does any hostile cat
    - no clanmate walks with you, and they talk to you as to an outsider
    - after three days you can ask the leader to take you back. It agrees once its grudge against you has faded.
  - **Punished:** punishment duties for three days. Your party goes home, and clanmates won't come along until
    they're done.
  - The Clanmates page shows your standing in each Clan, an exile or punishment, and the breaches your Clan knows.
- **E2, the Clans' own cats' breaches**, with Clan life's step 7 (borders and Gatherings):
  - the mod's cats breaking the code as their traits and wants allow (ambition, revenge, theft), judged the same way
  - trespass and hunting on another Clan's land
  - justice demanded at Gatherings, raids
  - rumours from a body found
  - a deputy who loses its deputyship

## Part D: the SDK (wcmods), listed for approval

- **S8, cats as fighters:**
  - **Find out:** whether a walking cat (the mod's own) plays the fight montages, hit reactions and dodges by tag,
    as animals and your cat do.
  - **Calls:** hits on any cat, a defeat, and a lying-still end (`Pose::Still` is there). Scars put on a living
    cat's look (`set_look` has the scars).
  - **Proof:** in game, a mod's cat that attacks, reels when hit, dodges and yields.
  - **Done (2026-11-07):** the walking cats play every fight move already (they share your cat's montage table), so
    S8 added what fights need around it: scars kept on a mod's cat (`NpcSpec::scars`, `Npc::set_scars`) and tags on
    its actor for other mods to know it by (`NpcSpec::tags`, `Npc::tag`, `actor_tags`, `has_tag`, `add_tag`).
- **S9, rogues in the open world:**
  - **Find out:** whether the game puts rogue cats out on its own (its enemy generators' fight parties name
    rogues).
  - **Calls:** if it does, rogues found as animals are. If it doesn't, rogues are the mod's own cats, with the
    game's rogue names and looks.
- **Your own rank** (kit to leader, asked the same day) would be its own SDK step, planned separately if you want
  it. Rivals rising and you rising fit together.

Each step updates `docs/SDK.md`, its header's comments and the in-game tests, as the other SDK plans do.

## The order

1. **Part A, memories and opinions** (Clan life). No fighting needed: rescues, rivalries for rank, mates and
   gossip give cats memories already.
2. **Part A, wants** (Clan life): choices and talk follow them.
3. **S8** (SDK), then **Part B** (Real-time combat): fighting cats, yielding, sparing and killing, told to Clan life.
   Done.
3b. **Part B2, your party** (Clan life and Real-time combat): clanmates who come with you and fight beside you. Next
   (the owner's, 2026-11-07).
4. **Deaths from fights** (Clan life): grief and kin's grudges, and Part E: breaches, standing, judgements, exile.
   E1 (your cat's breaches) next; E2 (the Clans' own) with Clan life's step 7.
5. **Part C, rivals** (Clan life): grudges become rivals that grow and come after you; endings.
6. **S9** and **rogue and animal rivals** (Real-time combat and Clan life).

Each is a pull request with its own tests, as before. Clan life's step 7 (borders, trespass, Gatherings) brings
the meetings where rivals show up, so it comes alongside step 5.

## Decisions (the owner's, 2026-11-07)

1. **Kits and medicine cats** can be attacked and killed, as the worst crimes against the warrior code, with the
   consequences in Part E (the owner's change: the plan had said never).
2. **A beaten cat** yields and runs; killing it is your choice (a held key).
3. **Deaths** come from fights only while Real-time combat is installed, apart from Clan life's old-age deaths
   (still off by default).
4. **When a rival beats you,** you're beaten the way the game's own defeat works, not dead for good, and the rival
   remembers winning.
5. **Part A comes first.**
6. **A warrior is exiled** for breaking the code; rank shields a deputy and a leader (the owner's).
7. **Mates from other Clans** are allowed, frowned on but not forbidden (the owner's).
8. **Several cats at once:** blows land on every cat in front of you, so you can fight several at once (the owner's).
   Changed 2026-11-07 after the video review (the owner's): a light attack or a lunge lands on one cat or animal,
   the one you're locked on to when it's in reach, else the nearest; only the heavy attack, a wide swing, lands on
   every one in front. In a camp the old rule made every swing a brawl (each cat struck joined in).
9. **Your party fights beside you** in Real-time combat, next after Part B (the owner's): Part B2.
10. **An accidental blow is forgiven:** striking a kit, a medicine cat or a clanmate is a breach only when your cat
    hits it more than once in a fight (the owner's).

## What might not work

- **Fight moves on the mod's cats:** the walking cats may not play the fight montages (only their own moves were
  tried in S1). Then the moves come from your cat's montages played on them, or the fights look plainer.
- **Learning your habits:** Real-time combat has to report what you do in each fight, a small addition there.
- **Words:** all of it needs lines, in the books' manner and the mod's own. There will be many to write, and some
  will repeat until there are more.
- **Talk answers** stay words only until wcmods' S5. Choices like "spare" or "make peace" come from keys or the
  mod menu until then.

## Not in this plan

Wars between whole Clans, StarClan and the Dark Forest, prophecies and dreams, voice.
