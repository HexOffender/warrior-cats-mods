# The game's AI from C++

The C++ SDK reads what the game's AI knows: an animal's senses (`senses()`, writable), its blackboard
(`blackboard_bool`, `npc_detected`, `npc_target`) and a fighter's AI tier and moves (`Fighter::ai_tier()`, `moves()`).
Nothing changes what an AI does. This plan gives C++ mods the AI itself: its keys, its trees, its moves, an enemy's
choices in a fight, animals of the game's put in the world, and the clan cats' walking.

It's done as the coverage and gaps plans were (build 26337109): one step at a time in one session, each its own pull
request, reverse-engineered first, tested in game, reviewed (code-review, high), fixed and merged before the next
starts. The Lua side stays out of scope.

## What the game has

Found on 2026-11-05 in the header dump and the game files:

| Part | What |
|---|---|
| Controllers | `ASwtQuestAIController` (`AAIController`: `DefaultMaxWalkSpeed`, `bArrivedAtTarget`) and its kinds: `ASwtAdventureAIController` (an animal's: `BehaviorTree` for roaming, `CombatBehaviorTree` for a fight, `OnAITurnOrderEnded`), `ASwtAdventureChaseOffAIController`, `ASwtQuestWalkingAIController` and `ASwtQuestEscorteeAIController` (each its own `BehaviorTree`). Blueprints: `AIC_Wrc_Enemy_Controller`, `_BossEnemy_`, `_Quest_Enemy_`, `_Quest_Escort_`, `_Tutorial_Mentor_`, `_WalkingNPC_` |
| Trees | `BT_Enemy` (roaming), `BT_ChaseOff_Enemy`, `BT_CombatEnemy`, `BT_BossEnemy`, `BT_AttackEnemy`, `BT_Escort`, `BT_Mentor`, `BT_WalkingNPC` |
| Blackboards | `BB_Enemy` (`Detected`, `Target`, `StartLocation`, `RoamingLocation`, `DetectionRange`, `ChaseReactionTime`, `Hunted`, `HunterPawn`, `PointOfInterest`, `bShouldAllowMovement`, `ArrivedAtTarget`, `SplineReference`, `CurrentIndexSpline`), `BB_CombatEnemy` (`AffectedByCondition`, `IsExhausted`, `IsAlive`, `AllyWithStatus`, `AllyWithLowHealth`, `WeakestEnemy`, `SlowestEnemy`, `SelectedAttack`, `itemTag`), `BB_Escort`, `BB_Mentor` (keys not read) |
| Tree nodes | Roaming states (`BTTask_EnemyIdle`, `_EnemyWalking`, `_EnemyGrazing`, `_EnemyChecking`, `_EnemyHunted`), `USwtAdventureCalculateRoaming`, detection (`BTService_DetectionTask`, `UWrcDoDetectionTask`, `UWrcEnableDetectionTask`, `BTTask_FlushDetectedCharacter`), moves (`BTTask_GoToLocation`, `_GoToIndexSplineLocation`, `_SplineWalking`, `_NPCSplineWalking`), a fight's (`BTTask_SelectRandomAttack`, `_SelectSpecificAttack`, `_SelectAncestralAttack`, `_AttackHealthiestEnemy`, `_CheapestStaminaAttack`, `_DebuffStrongestEnemy`, `_SetRandomTargetAndAttack`, `_TargetSelf`, `_CureAllyHealth`, `_CureAllyStatus`, `_UseItem`, `_UseRest`, `_SetNextCat`), and 20 decorators (`ChanceCheck` by `EAICombatTypeChance`, `CheckLowHealth`, `CheckWeakestEnemy`, `AmIABoss`, `DoIHaveAHealthItem`...) |
| A fight's choices | `AICombatChances.csv`: each tier's chance of each kind of choice (Terrible: random only; Tier 1 to 6; Perfect). An enemy's tier comes from your level (`Gameplay.Combat.Dynamic.Difficulty.*`), kept in its combat component (+0x3F8, `WCM_AITier`) |
| Animals in the world | `BP_Exploration_Character_Base_C < WrcRoamingEnemy`, made by the prey generators (`BP_Enemy_Generator_C < SwtAdventurePreyGenerator`: combat tags per clan, `SpawnedPreys`); `Gameplay.Exploration.Enemy.Roaming.Radius` 500 |
| Clan cats walking | `BP_WalkingNPC_Character_Base_C < SwtAdventureWalkingNPC` on `BP_WalkingNPC_Spline_C` paths (the track path manager), the walking controller and `BT_WalkingNPC`. The SDK's own cats (`spawn_npc`) are this class |
| The engine's own calls | reflected in `AIModule`: `AAIController::RunBehaviorTree`, `MoveToLocation`, `MoveToActor`, `SetFocus`, `ClearFocus`, `GetMoveStatus`; `UBlackboardComponent::SetValueAs*`, `ClearValue`; `UBrainComponent::StopLogic`, `RestartLogic`, `IsRunning`; `UAIBlueprintHelperLibrary::SpawnAIFromClass` |

## 1. An AI's keys and logic

**Known.** The blackboard reads; the engine's blackboard and brain calls are reflected.

**Find out.** Which keys the game's own code writes back (noticing a cat sets `Detected` and `Target` from the
detection component, `0x14189F530`; losing it clears them, `0x14189F760`), so a mod knows which writes hold; whether
a stopped AI stays stopped through the game's own restarts (an animal sleeps and wakes as you leave and enter its
zone); which tree each kind of animal and cat runs.

**The calls.** `set_blackboard(actor, key, bool | float | int | vector | object)`, `clear_blackboard(actor, key)`;
`stop_ai(actor)`, `restart_ai(actor)`, `ai_running(actor)`; `ai_tree(actor)` (the tree running, by name), and the
game's trees and blackboards listed.

**Proof.** In game: an animal stopped while your cat walks past it and started again; `PointOfInterest` written and
the animal going to check it; a key written and read back. (`BT_Enemy` doesn't read `PointOfInterest`: the proof
became a walking cat stopped and set walking again by `bShouldAllowMovement`, and an animal sent into its chase branch
by `Detected` and `Target`.)

## 2. Moving an animal or a cat

**Known.** `MoveToLocation` and `MoveToActor` are reflected on every AI controller; the move's end is the
controller's `ReceiveMoveCompleted`.

**Find out.** Whether a tree takes the animal back while it moves (stop its logic first, or `bShouldAllowMovement`);
whether the SDK's own cats get a controller (`AutoPossessAI`, or one spawned for them) and walk on the navigation
mesh around the camps.

**The calls.** `move_to(actor, place)`, `move_to(actor, other)` (with the move's end passed to `done`, in place of
an `on_move_done`), `stop_moving(actor)`, `moving(actor)`; `face(actor, place or other)`.

**Proof.** In game: an animal and one of the mod's cats each walk to a place and stop there, the end reported.

## 3. Noticing and ignoring your cat

**Known.** The senses (step 1 of the coverage plan); noticing and losing a cat; the detection tasks
(`UWrcEnableDetectionTask`, `BTTask_FlushDetectedCharacter`); a chase-off controller and tree.

**Find out.** The detection component's own switch (what `UWrcEnableDetectionTask` sets); what the chase-off tree
does and when the game uses it; what `Hunted` and `HunterPawn` make an animal do (flee).

**The calls.** `ignore_player(actor, true)` (one animal) and for all (`ignore_player_everywhere`); `notice_player(actor)`
(it gives chase now); `flee(actor, from)`; `calm(actor)` (back to roaming, as the game's losing does).

**Proof.** In game: your cat walking right past a mouse that ignores it; a far animal turning to chase on command; one
fleeing from your cat; one calmed mid-chase.

## 4. Swapping trees

**Known.** An animal's controller keeps its two trees as reflected members; `RunBehaviorTree` starts one with its
blackboard.

**Find out.** What each of the game's trees does (their nodes and keys: read from the assets, or in game from the
tree's root); `BB_Escort`'s and `BB_Mentor`'s keys and who fills them (the controllers' Blueprints); whether a tree
from another controller runs on an animal's (an escort tree on a clan cat, a boss's fight tree on a mouse).

**The calls.** `run_tree(actor, tree)` now; `set_trees(actor, roaming, fight)` so the game's own restarts keep them;
`follow(actor, target)` (a cat that follows your cat: through the escort tree was the plan, but its task doesn't drive another
controller's cat, so it's a `move_to` after the target), `stop_following(actor)`.

**Proof.** In game: one of the mod's cats following your cat about with the escort tree, and let go; an ordinary
enemy fighting with the boss's tree.

## 5. A fight's AI

**Known.** The combat tree on an animal's controller picks a move into `SelectedAttack`; the tiers' chances; an
enemy's tier at +0x3F8 (a hidden member, read).

**Find out.** How an AI's turn runs: when the combat tree runs, what reads `SelectedAttack` and the target, and the
turn's end (`OnAITurnOrderEnded`, `OnAITurnOrderCompleted`); where the game keeps `AICombatChances.csv` (a map of the
tuning manager's, as the talk tables are, or a data table); whether the tier can be written before the tree reads it.

**The calls.** `limit_moves(fighter, places)` (the mod picks an enemy's moves: an `on_ai_turn` would come too late,
its move is set as its turn starts) and `restore_moves`; `set_ai_tier(fighter, tier)`; `ai_chances(tier)`,
`set_ai_chance(tier, kind, chance)`; `auto_fight(on)` (your cat's turns played for you by the SDK: its fighter has no
AI to give them to).

**Proof.** In game: an enemy using the move the mod picked on each of its turns; a Terrible tier attacking at random;
your cat's turns played by the game's AI to the fight's end.

## 6. Putting an animal in the world

**Known.** The roaming animals' class and their generators; the engine's `SpawnAIFromClass` spawns a pawn with a
tree.

**Find out.** What makes a roaming animal (its kind and size, its combat tags (`FCombatSetup`), its level and team
for a fight) and how a generator spawns one (its Blueprint, or native code); whether a spawned one fights and gives
its rewards like a generator's.

**The calls.** `spawn_animal(kind, place)` (a mouse, a rabbit, a fox...) with its AI running, `animals()` near your
cat, `remove_animal(actor)`.

**Proof.** In game: a rabbit put beside your cat roaming, noticing it, and a fight with it won with its rewards.

## 7. The clan cats' walking

**Known.** The walking cats, their spline paths, their controller and tree; the SDK's cats are the same class.

**Find out.** How a walker picks its path (`SplineReference`, `CurrentIndexSpline`, the track path manager);
whether a path can be made while the game runs (a spline on a spawned actor); what stops a walker when you talk to it.

**The calls.** `walkers()` with their paths; `walk_path(actor, points, loop)` for a game's cat or the mod's own;
`stop_walking(actor)`, `walk_again(actor)`.

**Proof.** In game: one of the mod's cats walking a loop of points around the camp, stopping when your cat talks to
it, and going on after.

## Status

| Step | State | Pull request |
|---|---|---|
| 1. An AI's keys and logic | done: `Ai.hpp`: an AI's controller, brain, tree (the component's `InstanceStack`, a hidden member, signed) and active node; its blackboard's keys read and written by type; its logic stopped (it stays stopped through the game's sleep and wake) and restarted; the game's eight trees read as data, which say what each key does. Seen in game | #145 |
| 2. Moving an animal or a cat | done: `move_to` a place or after another actor through the controller's own `MoveToLocation` (the AI's logic stopped first, its speed set or kept, given back at the end on request), `stop_moving`, `moving`, `face`; the walk engine (arrival, stalls, steps aside) shared with `Npc::walk_to`. Seen in game on an animal and a mod's cat | #146 |
| 3. Noticing and ignoring your cat | done: an animal's detection mask (its component's `DetectionType`, which the game leaves as set; corrected in step 5's PR: it's the detection's flags only when the caller gives none, so `ignore_player` makes the detection sphere ignore cats); `ignore_player` (one, or every animal near: a stealth mode), `notice_player` and `calm` through the animal's own `OnCharacterDetected` and `OnCharacterLost`, `flee` (a `move_to` away, onto the mesh: `nav_point`). The chase-off tree isn't the game's way of fleeing (it's a spline walk to a boss's place), so `flee` is a move. Seen in game | #147 |
| 4. Swapping trees | done: `run_tree` (the controller's own `RunBehaviorTree`), `ai_trees_set` and `set_trees` (its reflected `BehaviorTree` and `CombatBehaviorTree`); `follow` and `stop_following`, built on `move_to` (the escort tree's Move To Location doesn't move another controller's cat). `BT_BossEnemy` is a roaming tree, not a fight tree: a fight tree set is seen in step 5's fight | #148 |
| 5. A fight's AI | done: the tiers' chances read and set (`AICombatChances.csv`'s map, found by what it holds: no signature reaches it); `set_ai_tier`; `limit_moves` and `restore_moves` (the fighter's moves array reordered and its count cut: the tree's pick is one of them); `auto_fight` takes your cat's turns (the SDK's own player: your cat has no AI controller). A fight tree other than `BT_CombatEnemy` stalls the fight; the cheats' `ForcedDifficulty` isn't obeyed. Seen in a fight | #149 |
| 6. Putting an animal in the world | done: `animal_kinds` (`DT_Combat_Generator`'s parties); `spawn_animal` borrows one of the game's placed generators (a generator spawned at run time gave another's fight party), sets its party tags to the kind and moves it to the place, and gives it back after (or respawns, on request); `animals`, `remove_animal`. Seen in game: a rabbit roaming, noticing your cat, and a fight with it won with its rewards | this branch, `claude/cpp-ai-spawn` |
| 7. The clan cats' walking | not started | |
