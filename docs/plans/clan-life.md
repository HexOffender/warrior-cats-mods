# Clan life: the plan

A C++ mod, **Clan life**, that gives every Clan a camp full of cats who live the way Clan cats do in the books.
Each cat has a name, a rank, a look that fits its name and family, needs of its own, and duties. The leader
decides what the Clan needs, the deputy turns that into patrols, the patrol leaders and mentors carry it out, and
everyone else gets on with Clan life: hunting, marking the borders, gathering herbs, training, feeding the elders,
guarding the camp at night, sharing tongues at sundown. Your own Clan lives this way too, and you're part of it: the
deputy gives you duties, you can join a patrol, and you can bring clanmates along.

It needs a few new things in wcmods' C++ SDK first (part 1). The mod itself is part 2, in its own repository like
Real-time combat. Everything is done as before: one step per pull request, worked out in the game first, tested in
game, reviewed (code-review, high), fixed and merged before the next step starts.

Written on 2026-11-06, from three pieces of research: the books (the official site's articles on the roles of the
Clans and the warrior code, the Warriors Wiki, and the Allegiances of several books), what players and reviewers say
about the game (Steam reviews and discussions, press reviews, patch notes), and what wcmods already knows about the
game's data and code.

## The books and the game

| | In the books | In the game now | With Clan life |
|---|---|---|---|
| **Who lives in a camp** | 20 to 30 cats: leader, deputy, medicine cat (often with an apprentice), about a dozen warriors, 2 to 6 apprentices, 2 to 4 queens with kits, 3 to 5 elders | Your Clan: about 20 cats made by the game, mostly standing at fixed spots or walking set paths. The other Clans' camps are empty: the game only makes your own Clan's cats | Every Clan has a full camp of named cats, with lore-like numbers of each rank |
| **What they do** | Duties by rank and time of day: dawn patrol, hunting, herbs, training, chores for the elders, sharing tongues, night guard | They stand or walk the same path; only quest givers say anything new. Players say the static cats break the immersion | Each cat picks what to do from its needs, its rank and its orders, and does it where you can see it |
| **Hierarchy** | The leader decides, the deputy assigns patrols each morning, patrol leaders pick who comes, mentors give their apprentices orders | None you can see. You go from apprentice to leader in a few quests with no ceremony | Orders go down the ranks where you can watch them, and requests (the elders' bedding, the medicine cat's herbs) go up |
| **The fresh-kill pile** | Prey goes to the pile first; elders, queens and kits eat first, the leader last | A number that drains by itself; only you fill it | Clan hunters fill it, and cats eat from it in the books' order (your Clan's pile is the game's own) |
| **Patrols and borders** | Border patrols at dawn and dusk renew the scent marks; meeting another Clan's patrol means a tense exchange at the line | No patrols; trespassing has no consequence | Patrols walk real routes along the borders; patrols meet at the line; another Clan's patrol challenges you in its territory |
| **Moons and ceremonies** | Kits become apprentices at six moons, apprentices warriors after an assessment and a vigil; elders retire | A cat's rank only changes in the story | The Clan ages by the moon, with ceremonies held at the camp's speaking rock |
| **Gatherings** | Every full moon on the island, under a truce; medicine cats meet at the Moonpool at the half-moon | The Island and the Moonpool exist; no Gathering happens | The Clans gather on the Island at each full moon, and you can be chosen to go |
| **Families** | Kin, mates, littermates, mentors and apprentices | No families | Kits look like their parents, littermates are born together, mentors are named at the ceremony |
| **The party** | Clanmates hunt and patrol together | Up to two clanmates, picked by the story, who only exist in fights | A patrol you can join, and clanmates you can take with you who walk, hunt and (with Real-time combat) fight beside you |

What carries over from real cats: grooming, the hunting crouch and pounce, tasting the air, tails and ears, carrying
prey and moss in the jaws, sleeping curled up in the sun. Everything else is the books' cats: they talk, follow a
code and hold ceremonies.

## What the game gives us

From the repo's notes and the game's data (the in-game checks it still needs are listed with each step):

- **Your Clan's cats** are in your save (`NPCData/<Clan>/<role>`, each cat's look and name), made by the game's NPC
  generator from `<Clan>NpcGenerator.csv`: for a ShadowClan game, a leader, a deputy, a medicine cat, an elder, a
  queen, one apprentice, 10 warriors and 4 kits. The SDK reads them (`clan_cats()`). Only your own Clan's are made.
- **The game's rules for making cats:** prefixes weighted per Clan (`PreffixName.csv`, 90), suffixes per rank
  (`SuffixName.csv`), 31 canon names banned, look weights per Clan for every part (WindClan's coats lean on three
  colours, RiverClan's on three others), banned patterns, kits' allowed looks, sizes and scars by rank. The mod uses
  the same tables, so its cats look like the game's.
- **Cats of a mod's own** (`spawn_npc`): the game's walking clan cat with a fixed look, a size and a name, its label
  over its head, the Talk prompt, walking on the navigation mesh. 50 walking cats ran at 49 frames a second (about 30
  in view is the advice).
- **The camps:** each Clan's camp is a gameplay sublevel with seven den entrances: ThunderClan's around (-19200,
  32900), ShadowClan's (-14900, 9000), WindClan's (-33600, 33800) and RiverClan's (-46800, 2100). Each Clan's
  stand points for its cats come with its own quest sublevel, which likely only loads in that Clan's game. The Island
  and the Moonpool are places on the map.
- **The clock:** the game has one (about 20 real minutes a day) that the SDK reads and sets. The sky doesn't follow
  it (it follows the area you're in), so players see no day and night. The SDK can set the sky.
- **Animations a cat can show:** sitting (`CharacterSequenceState` Sit, SitLeft, SitRight, Meditative), stand poses,
  the camp jobs' states (sharpening, a training stance, training attacks and hits), and montages for digging,
  sniffing, sleeping, sharpening, playing, meowing, stretching, yawning and shaking. No eating, grooming or
  carrying ones were found; stand-ins until there are (a sniff and a dig for eating, a stretch for grooming). The skeleton has a `mouth` bone; nothing attaches anything to it yet.
- **The party:** a fight feature. The story adds up to two clanmates (`Party` on your cat and controller), who fight
  beside you and are never seen in the forest.
- **Limits:** the world streams in by area, a teleport into an unloaded area falls through the ground, and the
  navigation mesh is prebuilt per sublevel. So cats far from you can't walk for real: the mod keeps them as data and
  only puts the near ones in the world (below).

## How it works

### The Clans

When you first play a cat with the mod on, it makes four Clans and keeps them with your save slot
(`clan-life.json` beside the game's saves, one record per slot, as Sandbox mode keeps its own):

- **Numbers per Clan:** a leader, a deputy, a medicine cat (sometimes with an apprentice), 9 to 13 warriors, 2 to 5
  apprentices, 1 to 3 queens with 1 to 4 kits each, 2 to 4 elders: 22 to 32 cats. Your Clan starts from the cats the
  game made for it (same names and looks), topped up to these numbers.
- **Names:** the game's own prefixes and suffixes, by its weights per Clan, never a banned canon name, never twice
  in a Clan. Kits end in -kit, apprentices -paw, the leader -star.
- **Looks that fit the name:** in the books a mother names a kit for its looks, so the coat comes first and the
  prefix is picked to match it. The mod has a table from each of the game's 90 prefixes to the coats, patterns and
  eyes it suits (Ash-, Stone-, Mist- grey; Sand-, Fire-, Russet- gingers; Spotted-, Dapple- patterns; Snow-, White-
  white or very pale; Thistle-, Fern-, Rowan- anything). Each Clan's looks follow the game's weights for that Clan,
  so WindClan's cats come out lean and brown or grey, RiverClan's sleek, as the game draws them.
- **Families:** mates, and kits that take after their parents (coat, pattern and eyes from one or the other, with
  some variation). Littermates are born together. Each apprentice has a mentor, a warrior who has the time.
- **Who they are:** two traits each (loyal, ambitious, lazy, gruff, kind, playful, proud, anxious, wise...) that move
  what they choose to do and what they say, and a liking for each other cat that grows when they patrol or share
  tongues together. Medicine cats take no mates, as in the books.

The mod menu gets an **Allegiances** page, in the style of the books' first pages: each Clan's cats by rank, with
their mentors, mates and kits.

### Time

The schedule follows the game's clock: **dawn** (patrols go out), **morning** (chores, training, herbs),
**sunhigh** (rest, sharing tongues), **afternoon** (hunting), **sundown** (the evening patrol, eating, sharing
tongues, the elders' stories), **night** (sleep, a guard at the entrance). A **moon** is a number of days (a
setting, 1 by default, so a kit is apprenticed after about two hours of play). Full moon: a Gathering. Half-moon:
the medicine cats go to the Moonpool. Optionally, the sky darkens at night (the game's Night sky preset).

### Needs, choices and orders

Each cat has needs, as in The Sims: **hunger**, **energy**, **company** and **comfort** (warmth, being groomed),
and for kits and apprentices **play**. Each thing a cat can do offers to meet some of them: eating at the pile,
sleeping in its den, sharing tongues with a friend, lying in the sun, grooming, playing, telling stories. A free
cat picks the best offer for its needs, its traits and the time of day, within what its rank allows (a kit never
leaves camp; an apprentice needs leave; a warrior doesn't eat before the elders are fed).

**Orders come first.** A cat with an order does it, unless it's exhausted or starving (then whoever gave the order
picks someone else next time). The orders go down the ranks:

1. **The leader**, as each part of the day begins, looks at the Clan: the pile, how fresh each border's scent marks
   are, the herb store, the elders' bedding, the apprentices' training, any danger seen near the camp. It sets the
   day's priorities, coloured by its traits (a cautious leader sends more border patrols). Where you can see it, it
   comes out to the speaking rock and the deputy goes up to it.
2. **The deputy** turns them into patrols: which border is stalest, how many hunters the pile needs. It names a
   patrol leader for each (a senior warrior, rested, fed, not the same one each time), who picks two or three cats,
   taking mentors with their apprentices. It keeps warriors in camp, and names the night guard. Where you can see it,
   the deputy calls each cat over and says what it wants.
3. **Patrol leaders** lead the way, decide when to turn home, and report to the leader on the way back in.
4. **Mentors** give their apprentices chores and training. When an apprentice is ready, the mentor tells the
   leader.
5. **The medicine cat** sends its apprentice for herbs, or asks the deputy for a warrior to go with it.
6. **Queens** call their kits back and ask an apprentice for prey or bedding; **elders** ask for ticks, bedding and
   prey. Their requests go up to the mentors and the deputy, who turn them into orders.

### Near and far

Cats far from you are data: each has a task, a place and a time, and moves along its task's route by the clock (a
patrol halfway along the WindClan border is halfway along it). When you come near a camp or a patrol (about 80 m,
a setting), the mod puts those cats in the world where the data says they are, walking, sitting or sleeping, and
takes them out again when you go. At most 30 cats are in the world at once (a setting, 10 to 50), the nearest first.

### Places

Each Clan has a territory file the mod ships: the camp's places (each den's entrance, the speaking rock, the
fresh-kill pile, the entrance, the guard's spot, sunning spots, the nursery's play area, the dirtplace), the border
routes, hunting grounds, herb spots (from where the map's herbs grow), the training ground, and for RiverClan the
fishing spots. The Island and the Moonpool get theirs too. They're found in the game (step 2 of the mod) with a
recording page in the mod menu: stand there, press a button, and the spot is saved.

### Alongside other mods

- **Sandbox mode:** Clan life follows it as Real-time combat does: it's on while you play a Sandbox mode cat, and
  your Clan is the one Sandbox mode says.
- **Real-time combat:** the mod's cats aren't animals, so lock-on and hits leave them alone. Step 8 lets clanmates
  fight beside you, through a small addition to Real-time combat.
- **Clan Mod Studio's characters and questlines:** their cats keep their spots; Clan life's cats keep clear of them.

## Part 1: the SDK (wcmods)

### S0. The new game build

Steam updated the game to build 26391405 (patch 1.3) on 2026-11-06. Before any in-game work, wcmods checks
what it reads on the new build (its signatures and hidden members), as it did for 26337109, and the full test suites
run on it. Real-time combat and Sandbox mode get the new build in their `game_builds` once their own tests pass.

### S1. Poses and moves for clan cats

**Find out:** which of the anim instance's states (`CharacterSequenceState`, `StandPose`, `FillerState`) a walking
clan cat obeys, which montages play on it (sleep, dig, sniff, sharpen, play, stretch, yawn, meow), how a sleep loops
and ends (`Get_Up_1`), whether `Crouch` gives the hunting crouch, and whether any of the 247 sequences is an eat or a
groom.

**Calls:** `Npc::pose(Pose::Stand | Sit | SitLeft | SitRight | Lie | Sleep | Crouch | TrainingStance ...)`,
`Npc::play(move, {loop})` for the montages, `Npc::stop_pose()`; the poses and moves listed for mods.

**Proof:** in game, a spawned cat sits, lies down, sleeps and gets up, crouches and stalks, spars (stance, attack,
hit), digs and sniffs; screenshots of each.

### S2. Carrying in the jaws

**Find out:** whether a mesh attached to the `mouth` bone stays in the jaws through the walk and run cycles, and the
game's own models for prey (mouse, bird, squirrel, fish, rabbit), moss and herbs (the pickups' and fresh-kill's).

**Calls:** `carry(actor, model)` and `drop(actor)` for any cat, yours included; the models listed by name.

**Proof:** in game, a clan cat walks across the camp with a mouse, then with moss, and drops it; your cat carries one.

### S3. Many cats, near and far

**Find out:** what a spawn costs (a hitch with 10 at once?), whether the ground and navigation mesh are loaded at a
spot before putting a cat there (the far camps), how far each camp's sublevel and nav data load, and whether hidden
cats (the game's distance hiding) still walk.

**Calls:** a cat that can be put in the world and taken out again keeping its handle and look (`Npc::sleep()`,
`Npc::wake()`), spawns spread over frames with a budget, and `ready_at(place)` (ground and navigation loaded there).

**Proof:** in game, 30 cats put in and taken out as your cat walks between two camps, frame times measured; no cat
falls through the ground at a far camp.

### S4. Finding places on the navigation mesh

**Find out:** the engine's random reachable point and path queries (`GetRandomReachablePointInRadius`, a path's
length) with the cats' navigation data passed (without one they fail, as found in the AI plan).

**Calls:** `random_nav_point(around, radius)`, `nav_path_length(from, to)` (or nothing when there's no path).

**Proof:** in game, 20 random points round a camp, each walked to by a cat; a point across water gives no path.

### S5. Cats talking

**Find out:** how the talk box's answer buttons can be clicked (today `say` shows answers as words only), and a
light way to show a line over a cat's head or as a subtitle that doesn't stop play (the label's extra line, or a
HUD text).

**Calls:** `ask(speaker, words, answers, done)` with clickable answers (keyboard, mouse and controller);
`Npc::speak(words, seconds)` for chatter between cats, shown when you're near.

**Proof:** in game, a cat asks your cat a question and each answer is picked once (mouse, keys, controller); two
cats exchange lines as you walk past.

### S6. The game's tables for making cats

Added on 2026-11-06 with the owner's yes, for the mod's step 1: the game makes its clan cats from its `NonAsset/NPC`
tables (prefixes weighted per Clan, suffixes by rank, the banned canon names, the look weights per Clan, the kits'
parts, sizes and scars by rank, how many of each rank), and the mod makes its cats the same way. Copying the tables
into the mod would be the game's data in its repository, and stale after a name mod or an update.

**Calls:** wcmods' install writes them, as the build leaves them (name mods' changes in), beside `offsets.json`
(`Mods/shared/WCModsGame/npc_tables.json`, `wcmods/npctables.py`); `wcmods::cat_tables()` reads them, and
`wcmods::colour_slots()` gives the cat maker's colour slots' colours from the GUI manager (to tell a grey coat from a
ginger one, palette mods' changes in).

**Proof:** unit tests for the tables from small CSVs; in game, the C++ test mod reads the 90 prefixes, 27 suffixes,
31 banned names and 14 look tables as the game ships them, and the coat colours as Lua reads them.

Each S step updates `docs/SDK.md`, its header's comments and the in-game tests (`tests/game/test_cpp_sdk.py`).

## Part 2: the mod (wcmods-clan-life)

A new public repository, HexOffender/wcmods-clan-life, laid out like wcmods-realtime-combat: `clan-life/` (mod.json,
settings.json, the C++ source, the territory files), unit tests for the rules (`rules.hpp`, plain C++, run in CI),
in-game tests with wcmods' agent, `tools/pack.py`, `docs/plan.md` (this part).

### 1. The Clans

The four Clans made and kept per save slot: numbers, names, looks that fit names and families, mates, mentors,
traits, liking. Your Clan from the game's own cats, topped up. The mod menu's Allegiances page. The gate (Sandbox
mode, on and off).

**Proof:** unit tests for the rules (no banned names, no repeats, numbers in range, kits like their parents, each
apprentice with a mentor); in game, the Allegiances page for a ThunderClan and a WindClan sandbox cat, the same after
quitting and coming back.

### 2. The territories

Each camp's places, the border routes, hunting grounds, herb spots, training grounds, the Island and the Moonpool,
found in the game and written into the territory files, with the recording page. Answers the open questions: what
the other camps hold in a sandbox game, which of your camp's cats are the game's, whether far camps' ground and
navigation load (S3), and whether a walking cat can reach each place (S4).

**Proof:** in game, a cat walks every route and reaches every place in all four territories; screenshots of each
camp with its places marked.

### 3. Life in camp

The near cats in the world, living by their needs: sleeping in their dens at night and getting up at dawn, eating at
the pile in the books' order, sharing tongues with friends, lying in the sun, elders telling stories to kits, kits
playing by the nursery and called back by their queen, the medicine cat in its den. Each cat's label: its name, its
rank, and what it's doing ("Sharing tongues with Ashfur"). Far cats as data, by the clock.

**Proof:** unit tests for the needs and choices; in game, a camp watched through a day at a fast clock: everyone
asleep at night, the pile eaten in order, nobody standing still for long; 30 cats at a steady frame rate.

### 4. Duties and orders

The chain of command: the leader's priorities, the deputy's patrols, patrol leaders, mentors, requests going up.
Border patrols walking the routes and marking the scent line; hunting patrols stalking, catching (out of sight, or
on an animal near), burying and carrying prey home to the pile (your Clan's pile is the game's, so it fills); the
medicine cat's herb runs; apprentices' chores (elders' bedding, ticks with mouse bile, prey for the elders and
queens) and training with their mentors; the night guard. The orders shown where you can see them: the deputy
calling cats over, a line over its head.

**Proof:** unit tests for the deputy's picks (no cat on two patrols, apprentices with their mentors, rested cats
first) and the leader's priorities; in game, a dawn patrol formed, walking the border and back, a hunter bringing
prey to the pile (its number going up), an apprentice taking moss to the elders' den.

### 5. Your place in the Clan

- **Talking** to any cat: what it says comes from its rank, what it's doing, its traits, its liking for you, and the
  Clan's news (the pile, a new apprentice, a patrol that smelled fox). The lines are written for the mod in the
  books' manner, not copied from them.
- **Your duties:** the deputy gives you one each morning (join the dawn patrol, hunt for the pile, take moss to the
  elders), with the game's objective panel. Doing them raises your standing with the Clan (the game's clan bond).
- **Joining a patrol:** it waits for you at the entrance, and you walk the route with it; as a senior warrior you
  can be asked to lead one.
- **Taking clanmates along:** ask a friend to come with you (its liking for you decides), and it walks with you,
  hunts beside you, and goes home when you tell it to or at nightfall.

**Proof:** in game, a morning duty given, done and counted; a patrol joined from start to end; a friend following
your cat across a territory and home again.

### 6. Moons and ceremonies

The Clan ages by the moon. Kits apprenticed at six moons, warriors named when their mentors judge them ready (with
the night's silent vigil after), elders retiring, kits born in the nursery, a new deputy named when one is needed.
Each ceremony at the speaking rock: the leader calls the Clan, the cats gather, the words are said (the mod's own,
in the books' spirit), the Clan calls the new name. You can attend, and when it's your apprentice or your naming,
you're at the centre. Death of old age or sickness is a setting (off by default).

**Proof:** unit tests for ageing and who's next; in game at a fast clock, an apprentice ceremony and a warrior
ceremony watched from start to end, the Allegiances page changed after.

### 7. Between the Clans

- **Borders:** patrols of two Clans that meet at their border stop on their own sides and exchange words, tense or
  calm by how the Clans stand.
- **Trespass:** a patrol that finds you in its territory challenges you and sees you to the border (you can say
  sorry and leave, or stay and be chased out).
- **Gatherings:** at each full moon the leaders, deputies, medicine cats and some chosen cats of every Clan walk to
  the Island. The leaders speak from the Great Rock's place with the moon's news (from the mod's own record: new
  apprentices, warriors, kits, deaths), and the rest mingle. Your leader may choose you.
- **The Moonpool:** at the half-moon the medicine cats go there at night.

**Proof:** in game, two patrols meeting at the ThunderClan and ShadowClan border; your cat challenged and walked to
the border; a Gathering from the walk there to the walk home.

### 8. With Real-time combat

Clanmates with you (step 5) and patrols near a fight join it: they go after the animal you're fighting and hit it
with the cats' own fight moves, and a patrol that meets an animal fights it. It needs a small addition to Real-time
combat (allies it knows about), done as its own pull request there.

**Proof:** in game, a friend helping your cat beat a rabbit; a patrol driving an animal off.

### 9. Settings and the release

The mod menu page: on or off, how many cats in the world, how near before they appear, the length of a moon, the
night sky, ceremonies, deaths, how often you get duties. README, keys, `tools/pack.py`, the release zip (published only
on your yes).

## The order

S0 first: the combat fixes you asked for need the new build too, and come straight after it. Then S6 (the mod's
step 1 needs it), and S1 to S5 in turn, with the mod's step 1 alongside them. Steps 2 to 9 follow in order, each
after the SDK steps it uses (2 after S3 and S4, 3 after S1, 4 after S2, 5 after S5).

## Decisions for you

1. **Sandbox mode only, or story games too?** I'd start with Sandbox mode only, as Real-time combat does. The story
   moves your Clan's cats around (raids, deaths, new roles) and uses the camps for its scenes; adding cats there could
   clash with it. The other three Clans' camps could come to story games later.
2. **Your own camp:** keep the game's own camp cats (the fresh-kill cat, the trader, the move trainer) where they
   stand, so their trades and lessons still work, and add the rest of the Clan around them? I'd say yes.
3. **How long is a moon?** 1 game day (about 20 minutes of play) by default, as a setting. A kit is then apprenticed
   after about two hours, which lets ceremonies happen while you play.
4. **Deaths:** off by default, a setting to turn on?
5. **The repository:** a new public one, HexOffender/wcmods-clan-life. That needs your yes when I get there.

## What might not work

- **Far camps:** if a camp's sublevel or navigation only loads in that Clan's own game, its cats can't walk there.
  Then they'd stand at their spots and do the jobs that need no walking until it's solved (S3 and step 2 find out).
- **Eating and grooming:** the game may have no animation for either; stand-ins until they're made (as with the
  combat mod's guard).
- **Carrying:** if a mesh in the mouth doesn't hold through the walk, prey is carried out of sight only.
- **Clickable answers:** if the talk box's buttons can't be wired, answers become keys (1 to 4) with the words shown.
- **Talking:** the game's talk box stops play while it's up, as for every game talk.

## Not in this plan

Swimming (RiverClan can't swim in the game), fights between Clans' cats (the game's fights only pit cats against
animals and rogues; a border skirmish would need cat fighters in Real-time combat), seasons and weather (the game
has neither), StarClan and dreams, voice for the mod's lines.
