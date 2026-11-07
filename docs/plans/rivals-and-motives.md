# Rivals, memories and motives: the plan

Asked by the owner on 2026-11-07:
- "Real time combat, rivals that remember you, and more. So if you kill a kit's parents, they remember and train
  to kill you."
- "I want to give the NPCs more depth and a reason for their behaviour apart from just fulfilling basic needs."

This plan is for the owner to approve before anything is built. It builds on three things:
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
  cats' own fight moves, as animals are fought now.
- **What starts a fight:**
  - you trespass, or they do (Clan life's step 7)
  - a border skirmish
  - a rival's challenge or ambush
  - rogues raiding the camp
- **How a fight ends:** a beaten cat **yields** and runs (the warrior code doesn't ask warriors to kill). You
  choose: let it go, or give the killing blow (a held key). Killing is the biggest memory there is, for everyone
  who sees it or hears of it.
- **Clanmates:** they join in, as Clan life's step 8 plans.
- **What Clan life hears:** Real-time combat tells it what happened: who fought whom, who yielded, who was spared,
  who was killed, who saw it. Real-time combat runs without Clan life too.

**Proof:** in game, a fight with a WindClan warrior that yields; one spared, one killed. Clan life's record shows
both, with their witnesses.

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

## Part D: the SDK (wcmods), listed for approval

- **S8, cats as fighters:**
  - **Find out:** whether a walking cat (the mod's own) plays the fight montages, hit reactions and dodges by tag,
    as animals and your cat do.
  - **Calls:** hits on any cat, a defeat, and a lying-still end (`Pose::Still` is there). Scars put on a living
    cat's look (`set_look` has the scars).
  - **Proof:** in game, a mod's cat that attacks, reels when hit, dodges and yields.
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
4. **Deaths from fights** (Clan life): grief, and kin's grudges.
5. **Part C, rivals** (Clan life): grudges become rivals that grow and come after you; endings.
6. **S9** and **rogue and animal rivals** (Real-time combat and Clan life).

Each is a pull request with its own tests, as before. Clan life's step 7 (borders, trespass, Gatherings) brings
the meetings where rivals show up, so it comes alongside step 5.

## Decisions for you

1. **Kits:** never fought, by you or anyone. I'd say never. Apprentices only fight back when attacked.
2. **A beaten cat:** yields and runs by default, and killing is your choice (a held key)? Or fights to the death?
   I'd say yield, with your choice.
3. **Deaths:** from fights only while Real-time combat is installed, apart from Clan life's old-age deaths (still
   off by default)? I'd say yes.
4. **When a rival beats you:** you're beaten the way the game's own defeat works, not dead for good, and the rival
   remembers winning (and gloats). I'd say yes.
5. **Where to start:** Part A first (depth without fighting), or the fighting first? I'd say Part A first: it gives
   every cat reasons to act right away, and the fighting has something to build on.

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
