// Ai.hpp: the game's AI. A roaming animal or a clan cat walking its path has an AI controller running one of the game's
// behaviour trees (BT_Enemy for an animal, BT_CombatEnemy in its fights, BT_WalkingNPC for a walking cat), which keeps
// what it knows on its blackboard (BB_Enemy...). From C++: an AI's tree and what it's doing now, its blackboard's keys
// read and written, its logic stopped and started again, the game's trees read as data, an AI sent to a place or
// after another actor, an animal made to ignore your cat, notice it, give it up or run from it, another of the game's
// trees run on an AI, an AI made to follow another actor, and a fight's AI: its chances by tier, an enemy's tier and
// moves, your cat's turns taken for you (docs/plans/cpp-sdk-ai.md).
// Game thread only. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call.
//
//   for (UObject* a : wcmods::fight_animals(2000)) wcmods::stop_ai(a);           // the animals near your cat stand still
//   wcmods::move_to(mouse, wcmods::Vec3{x, y, z});                                // it walks there and stands
#pragma once

#include <algorithm>
#include <chrono>
#include <cstring>
#include <cmath>
#include <format>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Npcs.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/Story.hpp>
#include <WCMods/Tables.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // ============================================================================================ an AI and its tree
    // The game's behaviour trees, by name: each is /Game/Gameplay/Blueprints/AI/<name>.
    inline constexpr const wchar_t* AI_TREES[] = {L"BT_Enemy",      L"BT_ChaseOff_Enemy", L"BT_CombatEnemy", L"BT_BossEnemy",
                                                  L"BT_AttackEnemy", L"BT_Escort",         L"BT_Mentor",      L"BT_WalkingNPC"};

    // An actor's AI controller (a roaming animal's AIC_Wrc_Enemy_Controller_C, a walking cat's
    // AIC_Wrc_WalkingNPC_Controller_C), or nullptr (your cat, a cat standing in camp).
    inline auto ai_controller(UObject* actor) -> UObject*
    {
        UObject* c = get(actor, L"Controller").object;
        return c && is_a(c, STR("/Script/AIModule.AIController")) ? c : nullptr;
    }
    // Its brain: the behaviour tree component that runs its tree; nullptr without an AI.
    inline auto ai_brain(UObject* actor) -> UObject* { return get(ai_controller(actor), L"BrainComponent").object; }

    // One of the game's trees by its name (L"BT_Enemy"), loaded; nullptr for a name AI_TREES hasn't.
    inline auto ai_tree_named(std::wstring_view name) -> UObject*
    {
        if (!assert_game_thread(L"ai_tree_named")) return nullptr;
        for (const wchar_t* t : AI_TREES)
            if (name == t) return load(std::wstring(L"/Game/Gameplay/Blueprints/AI/") + t + L"." + t);
        return nullptr;
    }

    namespace detail
    {
        // The brain's stack of running trees (InstanceStack, a hidden member: the main tree first, a subtree it runs
        // after it), each element starting with {the tree's root node, its active node}. {} when it isn't running.
        inline auto main_tree_instance(UObject* brain) -> std::pair<UObject*, UObject*>
        {
            if (!brain || !is_a(brain, STR("/Script/AIModule.BehaviorTreeComponent"))) return {};
            const auto* stack = member<uint8_t>(brain, L"/Script/AIModule.BehaviorTreeComponent", L"WCM_InstanceStack");
            if (!stack) return {};
            const auto* data = *reinterpret_cast<UObject* const* const*>(stack);
            const int32_t num = *reinterpret_cast<const int32_t*>(stack + 8);
            if (!data || num < 1 || num > 64) return {};
            return {data[0], data[1]};
        }
    } // namespace detail

    // The tree an AI runs now (its main tree: L"BT_Enemy" for a roaming animal), or nullptr when its logic is stopped,
    // or without an AI, or without the member on this build.
    inline auto ai_tree(UObject* actor) -> UObject*
    {
        if (!assert_game_thread(L"ai_tree")) return nullptr;
        UObject* root = detail::main_tree_instance(ai_brain(actor)).first;
        return root ? get(root, L"TreeAsset").object : nullptr;
    }
    // What an AI is doing now: its main tree's active node, by its name in the tree (L"Grazing", L"Idle", L"NPC Spline
    // Walking") and its class (L"BTTask_EnemyGrazing"); empty when none is active (between nodes, or stopped). While
    // the tree runs a subtree (BT_CombatEnemy runs BT_AttackEnemy, BT_ChaseOff_Enemy runs BT_BossEnemy) it's that
    // Run Behavior node (L"BTTask_RunBehavior"): the subtree's own nodes aren't read.
    struct AiTask
    {
        std::wstring name, kind;
        explicit operator bool() const { return !kind.empty(); }
    };
    inline auto ai_task(UObject* actor) -> AiTask
    {
        if (!assert_game_thread(L"ai_task")) return {};
        UObject* active = detail::main_tree_instance(ai_brain(actor)).second;
        if (!active) return {};
        return {get(active, L"NodeName").string(), class_name(active)};
    }

    // Whether an AI's logic runs, and whether it's asleep: the game pauses a roaming animal's while your cat is far
    // from it (about 2,000 units: its zone, the tuning's Detection.*.PlayerZone.ExitDistance) and wakes it as your cat
    // comes back. False without an AI.
    inline auto ai_running(UObject* actor) -> bool
    {
        if (!assert_game_thread(L"ai_running")) return false;
        return call<bool>(ai_brain(actor), STR("IsRunning")).value_or(false);
    }
    inline auto ai_asleep(UObject* actor) -> bool
    {
        if (!assert_game_thread(L"ai_asleep")) return false;
        return call<bool>(ai_brain(actor), STR("IsPaused")).value_or(false);
    }
    // Stop an AI's logic: its tree stops and it stands where it is, through the game's own sleeping and waking as your
    // cat goes and comes back (seen in game), until restart_ai(). Its blackboard keeps what it knew. False without an AI.
    inline auto stop_ai(UObject* actor) -> bool
    {
        if (!assert_game_thread(L"stop_ai")) return false;
        UObject* brain = ai_brain(actor);
        if (!brain) return false;
        return call_reflected(brain, STR("StopLogic"), [](Params& p) { p.set_nth(0, Value::of(std::wstring_view(L"wcmods"))); })
            .has_value();
    }
    // Start an AI's logic again from its tree's start (RestartLogic), stopped or not. False without an AI.
    inline auto restart_ai(UObject* actor) -> bool
    {
        if (!assert_game_thread(L"restart_ai")) return false;
        return call(ai_brain(actor), STR("RestartLogic"));
    }

    // ============================================================================================ its blackboard
    // A key of an AI's blackboard: its name and its type (L"Bool", L"Int", L"Float", L"Vector", L"Object", L"Enum",
    // L"Name", L"String", L"Rotator", L"Class").
    struct AiKey
    {
        std::wstring name, type;
    };
    // Its blackboard's keys (its asset's, then the asset's parents'), in the asset's order: BB_Enemy's SelfActor,
    // Detected, StartLocation, Target, DetectionRange, RoamingLocation, bShouldAllowMovement, PointOfInterest, Hunted,
    // ChaseReactionTime, ArrivedAtTarget, HunterPawn, SplineReference, CurrentIndexSpline. Empty without an AI.
    inline auto blackboard_keys(UObject* actor) -> std::vector<AiKey>
    {
        std::vector<AiKey> out;
        if (!assert_game_thread(L"blackboard_keys")) return out;
        UObject* board = blackboard(actor);
        int guard = 0;
        for (UObject* asset = board ? get(board, L"BlackboardAsset").object : nullptr; asset && guard++ < 8;
             asset = get(asset, L"Parent").object)
            for (auto& k : elements(asset, L"Keys"))
            {
                AiKey key{get(k, L"EntryName").string(), {}};
                if (UObject* type = get(k, L"KeyType").object)
                {
                    key.type = class_name(type);
                    if (key.type.starts_with(L"BlackboardKeyType_")) key.type = key.type.substr(18);
                }
                if (!key.name.empty()) out.push_back(std::move(key));
            }
        return out;
    }
    namespace detail
    {
        inline auto blackboard_key_type(UObject* actor, std::wstring_view key) -> std::wstring
        {
            for (auto& k : blackboard_keys(actor))
                if (k.name == key) return k.type;
            return {};
        }
        // The board and the key's name for a write of a `type` key: {nullptr, None} when the AI hasn't such a key.
        inline auto board_for(UObject* actor, std::wstring_view key, std::wstring_view type) -> std::pair<UObject*, RC::Unreal::FName>
        {
            if (blackboard_key_type(actor, key) != type) return {nullptr, {}};
            return {blackboard(actor), RC::Unreal::FName(std::wstring(key), RC::Unreal::FNAME_Find)};
        }
        template <typename T>
        struct KeyValue
        {
            RC::Unreal::FName key;
            T value{};
        };
        struct KeyVector
        {
            RC::Unreal::FName key;
            float x{}, y{}, z{};
        };
        struct KeyOnly
        {
            RC::Unreal::FName key;
        };
    } // namespace detail

    // An Int key's value and a Vector key's; nullopt without the key (a Vector key not set reads as nullopt too).
    inline auto blackboard_int(UObject* actor, std::wstring_view key) -> std::optional<int>
    {
        if (!assert_game_thread(L"blackboard_int")) return std::nullopt;
        auto [board, name] = detail::board_for(actor, key, L"Int");
        if (!board) return std::nullopt;
        detail::KeyValue<int32_t> p{name};
        if (!call(board, STR("GetValueAsInt"), p)) return std::nullopt;
        return p.value;
    }
    inline auto blackboard_vector(UObject* actor, std::wstring_view key) -> std::optional<Vec3>
    {
        if (!assert_game_thread(L"blackboard_vector")) return std::nullopt;
        auto [board, name] = detail::board_for(actor, key, L"Vector");
        if (!board) return std::nullopt;
        detail::KeyValue<bool> set{name};
        if (!call(board, STR("IsVectorValueSet"), set) || !set.value) return std::nullopt;
        detail::KeyVector p{name};
        if (!call(board, STR("GetValueAsVector"), p)) return std::nullopt;
        return Vec3{p.x, p.y, p.z};
    }

    // Write a key: a Bool, an Int, a Float, a Vector (a place) or an Object (an actor) key, by the value's type (an int
    // writes a Float key too: set_blackboard(mouse, L"ChaseReactionTime", 30)). The
    // tree sees it at once (a decorator watching the key may change what the AI does). False, with nothing written,
    // when the AI hasn't a key of that name and type. What the game's own code writes back over a key: blackboard
    // notes in docs/reverse-engineering.md, "The game's AI".
    inline auto set_blackboard(UObject* actor, std::wstring_view key, bool value) -> bool
    {
        if (!assert_game_thread(L"set_blackboard")) return false;
        auto [board, name] = detail::board_for(actor, key, L"Bool");
        detail::KeyValue<bool> p{name, value};
        return board && call(board, STR("SetValueAsBool"), p);
    }
    inline auto set_blackboard(UObject* actor, std::wstring_view key, double value) -> bool;
    inline auto set_blackboard(UObject* actor, std::wstring_view key, int value) -> bool
    {
        if (!assert_game_thread(L"set_blackboard")) return false;
        if (detail::blackboard_key_type(actor, key) == L"Float") return set_blackboard(actor, key, static_cast<double>(value));
        auto [board, name] = detail::board_for(actor, key, L"Int");
        detail::KeyValue<int32_t> p{name, value};
        return board && call(board, STR("SetValueAsInt"), p);
    }
    inline auto set_blackboard(UObject* actor, std::wstring_view key, double value) -> bool
    {
        if (!assert_game_thread(L"set_blackboard")) return false;
        auto [board, name] = detail::board_for(actor, key, L"Float");
        detail::KeyValue<float> p{name, static_cast<float>(value)};
        return board && call(board, STR("SetValueAsFloat"), p);
    }
    inline auto set_blackboard(UObject* actor, std::wstring_view key, Vec3 value) -> bool
    {
        if (!assert_game_thread(L"set_blackboard")) return false;
        auto [board, name] = detail::board_for(actor, key, L"Vector");
        detail::KeyVector p{name, static_cast<float>(value.x), static_cast<float>(value.y), static_cast<float>(value.z)};
        return board && call(board, STR("SetValueAsVector"), p);
    }
    inline auto set_blackboard(UObject* actor, std::wstring_view key, UObject* value) -> bool
    {
        if (!assert_game_thread(L"set_blackboard")) return false;
        auto [board, name] = detail::board_for(actor, key, L"Object");
        detail::KeyValue<UObject*> p{name, value};
        return board && call(board, STR("SetValueAsObject"), p);
    }
    // Clear a key (a Vector key reads as not set again, an Object key as nullptr, a Bool as false). False without the key.
    inline auto clear_blackboard(UObject* actor, std::wstring_view key) -> bool
    {
        if (!assert_game_thread(L"clear_blackboard")) return false;
        auto type = detail::blackboard_key_type(actor, key);
        if (type.empty()) return false;
        auto [board, name] = detail::board_for(actor, key, type);
        detail::KeyOnly p{name};
        return board && call(board, STR("ClearValue"), p);
    }

    // ============================================================================================ the game's trees as data
    // A node of a behaviour tree, as ai_tree_nodes() reads it: how deep it is, what it is (L"composite": a selector or a
    // sequence; L"task", what the AI does; L"decorator", a condition on the branch below it; L"service", something run
    // while its branch runs), its class (L"BTTask_EnemyGrazing", L"BTDecorator_Blackboard"), its name in the tree
    // (L"Grazing") and its own settings (L"BlackboardKey" = L"Detected", L"FlowAbortMode" = L"Both", L"WaitTime" = L"5").
    struct AiNode
    {
        int depth{};
        std::wstring role, kind, name;
        std::vector<std::pair<std::wstring, std::wstring>> settings;
    };
    namespace detail
    {
        inline auto ai_node_settings(UObject* node) -> std::vector<std::pair<std::wstring, std::wstring>>
        {
            static const std::wstring_view skip[] = {
                L"NodeName", L"TreeAsset", L"ParentNode", L"ExecutionIndex", L"MemoryOffset", L"TreeDepth", L"bIsInstanced",
                L"bIsInjected", L"bCreateNodeInstance", L"bOwnsGameplayTasks", L"Children", L"Services", L"bApplyDecoratorScope",
                L"bIgnoreRestartSelf", L"CachedDescription", L"UberGraphFrame", L"AIOwner", L"ActorOwner", L"bShowPropertyDetails",
                L"bCheckConditionOnlyBlackBoardChanges", L"bIsObservingBB", L"bNotifyActivation", L"bNotifyDeactivation",
                L"bNotifyProcessed", L"bNotifyTick", L"bNotifyBecomeRelevant", L"bNotifyCeaseRelevant", L"bNotifyOnSearch",
                L"bShowEventDetails", L"bTickIntervals", L"CustomDescription", L"PropertyData", L"PropertyBlackboardKeys"};
            std::vector<std::pair<std::wstring, std::wstring>> out;
            for (auto& m : describe(node))
            {
                bool skipped = false;
                for (auto s : skip) skipped = skipped || m.name == s;
                if (skipped) continue;
                const Value& v = m.value;
                std::wstring text;
                switch (v.kind)
                {
                case Value::Kind::Bool: text = v.b ? L"true" : L"false"; break;
                case Value::Kind::Int: text = std::to_wstring(v.i); break;
                case Value::Kind::Float: text = std::format(L"{}", v.f); break;
                case Value::Kind::Enum:
                case Value::Kind::Text: text = v.text; break;
                case Value::Kind::Object:
                    if (v.object) text = name(v.object);
                    break;
                case Value::Kind::Struct:
                    if (m.type.find(L"BlackboardKeySelector") != std::wstring::npos) text = get(v, L"SelectedKeyName").string();
                    break;
                default: break;
                }
                if (!text.empty() && text != L"None") out.emplace_back(m.name, std::move(text));
            }
            return out;
        }
        inline auto ai_node(int depth, std::wstring_view role, UObject* node) -> AiNode
        {
            return {depth, std::wstring(role), class_name(node), get(node, L"NodeName").string(), ai_node_settings(node)};
        }
        inline auto ai_walk(UObject* composite, int depth, std::vector<AiNode>& out) -> void
        {
            if (!composite || depth > 32 || out.size() > 2000) return;
            out.push_back(ai_node(depth, L"composite", composite));
            for (auto& s : elements(composite, L"Services"))
                if (s.object) out.push_back(ai_node(depth + 1, L"service", s.object));
            for (auto& child : elements(composite, L"Children"))
            {
                for (auto& d : elements(get(child, L"Decorators")))
                    if (d.object) out.push_back(ai_node(depth + 1, L"decorator", d.object));
                if (UObject* c = get(child, L"ChildComposite").object) ai_walk(c, depth + 1, out);
                else if (UObject* task = get(child, L"ChildTask").object)
                {
                    out.push_back(ai_node(depth + 1, L"task", task));
                    for (auto& s : elements(task, L"Services"))
                        if (s.object) out.push_back(ai_node(depth + 2, L"service", s.object));
                }
            }
        }
    } // namespace detail
    // A behaviour tree's nodes, from its root, each after the decorators that guard it (its tree's own decorators
    // first, at depth 0): what the game's AI does and when. Empty for nullptr or what isn't a tree.
    //   for (auto& n : wcmods::ai_tree_nodes(wcmods::ai_tree_named(L"BT_Enemy"))) wcmods::log(L"{} {}", n.kind, n.name);
    inline auto ai_tree_nodes(UObject* tree) -> std::vector<AiNode>
    {
        std::vector<AiNode> out;
        if (!tree || !assert_game_thread(L"ai_tree_nodes") || !is_a(tree, STR("/Script/AIModule.BehaviorTree"))) return out;
        for (auto& d : elements(tree, L"RootDecorators"))
            if (d.object) out.push_back(detail::ai_node(0, L"decorator", d.object));
        detail::ai_walk(get(tree, L"RootNode").object, 0, out);
        return out;
    }
    // A tree's blackboard: its asset's name (L"BB_Enemy").
    inline auto ai_tree_blackboard(UObject* tree) -> std::wstring { return name(get(tree, L"BlackboardAsset").object); }

    // ============================================================================================ moving
    // The navigation meshes the AIs walk on (the world's navigation system's NavDataSet): the forest has two, one for
    // the animals (RecastNavMeshEnemy, agents 25 cm round) and one for the cats (RecastNavMeshPlayer, 1 cm: the walking
    // cats and the SDK's own). The one an actor walks on goes by its movement's agent radius.
    namespace detail
    {
        inline auto nav_meshes() -> std::vector<UObject*>
        {
            std::vector<UObject*> out;
            for (auto& v : elements(get(world(), L"NavigationSystem.NavDataSet")))
                if (v.object) out.push_back(v.object);
            return out;
        }
        inline auto nav_mesh_for(UObject* actor) -> UObject*
        {
            Value r = get(actor, L"CharacterMovement.NavAgentProps.AgentRadius");
            if (r.kind == Value::Kind::None) return nullptr;
            UObject* best = nullptr;
            double best_d = 1e18;
            for (UObject* m : nav_meshes())
            {
                double d = std::abs(get(m, L"AgentRadius").number() - r.number());
                if (d < best_d) best = m, best_d = d;
            }
            return best;
        }
        inline auto project_on(UObject* mesh, Vec3 place) -> std::optional<Vec3>
        {
            UObject* nav = object(STR("/Script/NavigationSystem.Default__NavigationSystemV1"));
            auto r = call_reflected(nav, STR("K2_ProjectPointToNavigation"), [&](Params& p) {
                p.set_nth(0, Value::of(world()));
                Value at = p.nth(1);
                set(at, L"X", place.x);
                set(at, L"Y", place.y);
                set(at, L"Z", place.z);
                p.set_nth(3, Value::of(mesh));
            });
            if (!r || !r->get(L"ReturnValue").boolean()) return std::nullopt;
            Value out = r->get(L"ProjectedLocation");
            return Vec3{get(out, L"X").number(), get(out, L"Y").number(), get(out, L"Z").number()};
        }
    } // namespace detail
    // The nearest point on the navigation mesh to a place, within the mesh's own search box (the engine's
    // K2_ProjectPointToNavigation): on the mesh `actor` walks on, else on either; nullopt off the meshes, or outside
    // the world.
    inline auto nav_point(Vec3 place, UObject* actor = nullptr) -> std::optional<Vec3>
    {
        if (!assert_game_thread(L"nav_point") || !world()) return std::nullopt;
        if (UObject* mesh = actor ? detail::nav_mesh_for(actor) : nullptr) return detail::project_on(mesh, place);
        for (UObject* mesh : detail::nav_meshes())
            if (auto on = detail::project_on(mesh, place)) return on;
        return std::nullopt;
    }

    // How move_to moves an AI: at `speed` cm/s (its walk speed set; 0 keeps the one it has, and a roaming animal's own
    // is a slow 70), close enough within `radius` cm, along the nav mesh round obstacles unless `avoid` is false (a
    // straight line), and its logic started again when the move ends, however it ends (`restart_after`: stop_moving
    // and another move_to too); else it stands there with its logic stopped until restart_ai().
    struct MoveOptions
    {
        double speed{0};
        double radius{50};
        bool avoid{true};
        bool restart_after{false};
    };
    namespace detail
    {
        struct AiMove
        {
            UObject* actor{};
            UClass* cls{};
            WalkState walk;
            bool restart_after{};
        };
        struct AiMoves
        {
            std::vector<std::shared_ptr<AiMove>> all;
            std::optional<TimerId> ticker;
        };
        inline auto ai_moves() -> AiMoves&
        {
            static AiMoves m;
            return m;
        }
        inline auto end_move(const std::shared_ptr<AiMove>& m, WalkResult result) -> void
        {
            auto& all = ai_moves().all;
            all.erase(std::remove(all.begin(), all.end(), m), all.end());
            if (object_staying(m->actor, m->cls))
            {
                if (result != WalkResult::Arrived)
                    if (UObject* c = ai_controller(m->actor)) call_reflected(c, STR("StopMovement"));
                if (m->restart_after) restart_ai(m->actor);
            }
            if (auto done = std::move(m->walk.done)) guarded(L"a move's done", [&] { done(result); });
        }
        inline auto ai_move_of(UObject* actor) -> std::shared_ptr<AiMove>
        {
            for (auto& m : ai_moves().all)
                if (m->actor == actor) return m;
            return nullptr;
        }
        inline auto start_ai_moves() -> void
        {
            auto& s = ai_moves();
            if (s.ticker) return;
            s.ticker = every(0.1, [] {
                auto all = ai_moves().all;   // a copy: a move's done may start another
                for (auto& m : all)
                    guarded(L"a move", [&] {
                        if (!object_staying(m->actor, m->cls)) return end_move(m, WalkResult::Cancelled);
                        if (auto r = walk_step(m->actor, m->walk)) end_move(m, *r);
                    });
            });
        }
        inline auto begin_move(UObject* actor, Vec3 to, UObject* goal, const MoveOptions& o, std::function<void(WalkResult)> done) -> bool
        {
            if (!assert_game_thread(L"move_to") || !actor || actor == player() || !ai_controller(actor)) return false;
            if (goal && !object_staying(goal, nullptr)) return false;
            if (auto old = ai_move_of(actor)) end_move(old, WalkResult::Cancelled);
            const bool was_running = ai_running(actor);
            stop_ai(actor);   // its tree would send it elsewhere
            if (o.speed > 0)
                if (UObject* mv = get(actor, L"CharacterMovement").object) set(mv, L"MaxWalkSpeed", o.speed);
            // Along the mesh, to the mesh's own point nearest the place: the controller stops there, and the walk
            // measures its arrival against it (a place off the mesh was never reached: seen, a flight that stood short).
            if (o.avoid && !goal)
                if (auto on = nav_point(to, actor)) to = *on;
            auto m = std::make_shared<AiMove>();
            m->actor = actor;
            m->cls = actor->GetClassPrivate();
            m->restart_after = o.restart_after;
            m->walk.to = to;
            m->walk.options = WalkOptions{o.speed, o.radius, o.avoid};
            m->walk.done = std::move(done);
            m->walk.started = m->walk.best_at = std::chrono::steady_clock::now();
            if (goal)
            {
                m->walk.goal = goal;
                m->walk.goal_class = goal->GetClassPrivate();
                m->walk.goal_at = to;
            }
            if (issue_move(actor, to, o.radius, o.avoid) == 0)
            {
                // Refused: its logic as it was (running again unless it had been stopped), then done told.
                m->restart_after = was_running;
                end_move(m, WalkResult::Blocked);
                return false;
            }
            ai_moves().all.push_back(m);
            start_ai_moves();
            return true;
        }
    } // namespace detail

    // Send an AI (a roaming animal, a walking cat, a mod's cat) to a place, or after another actor (it follows it as
    // it moves, until it's within the radius), through its controller's own MoveToLocation, along the nav mesh: its
    // logic is stopped first (its tree would send it elsewhere), and when the move ends `done(result)` is called:
    // Arrived; Blocked (no path, or stuck after five steps aside); Cancelled (stop_moving(), another move_to, it or
    // the goal gone). False, with `done` told Blocked, when the controller can't go there at all (its logic left as it
    // was: running again if it ran); false without calling `done` for your cat (no AI), nullptr or a goal that's gone. A mod's own cat has Npc::walk_to, which
    // keeps its walk across respawns: use one or the other on it.
    //   wcmods::move_to(mouse, wcmods::Vec3{x, y, z}, {.speed = 200, .restart_after = true});
    inline auto move_to(UObject* actor, Vec3 to, MoveOptions options = {}, std::function<void(WalkResult)> done = {}) -> bool
    {
        return detail::begin_move(actor, to, nullptr, options, std::move(done));
    }
    inline auto move_to(UObject* actor, UObject* goal, MoveOptions options = {}, std::function<void(WalkResult)> done = {}) -> bool
    {
        auto at = location(goal);
        if (!at) return false;
        return detail::begin_move(actor, *at, goal, options, std::move(done));
    }
    // End a move (its done told Cancelled) and stop the AI where it is (its controller's StopMovement: a move of the
    // game's own too). False without an AI.
    inline auto stop_moving(UObject* actor) -> bool
    {
        if (!assert_game_thread(L"stop_moving")) return false;
        UObject* c = ai_controller(actor);
        if (!c) return false;
        if (auto m = detail::ai_move_of(actor)) detail::end_move(m, WalkResult::Cancelled);
        return call(c, STR("StopMovement"));
    }
    // Whether an AI is moving: a move_to's under way, or one of its tree's own (its controller's GetMoveStatus is
    // Moving).
    inline auto moving(UObject* actor) -> bool
    {
        if (!assert_game_thread(L"moving")) return false;
        if (detail::ai_move_of(actor)) return true;
        auto st = call_reflected(ai_controller(actor), STR("GetMoveStatus"));
        return st && st->get(L"ReturnValue").number() == 3;   // EPathFollowingStatus::Moving
    }
    // Turn an actor to face a place or another actor, now (its yaw, and its controller's when it has one). False when
    // it isn't there.
    inline auto face(UObject* actor, Vec3 at) -> bool
    {
        if (!assert_game_thread(L"face")) return false;
        auto here = location(actor);
        if (!here) return false;
        const double yaw = std::atan2(at.y - here->y, at.x - here->x) * 180.0 / 3.14159265358979323846;
        auto r = call_reflected(actor, STR("K2_SetActorRotation"), [&](Params& p) {
            set(p.nth(0), L"Yaw", yaw);
            p.set_nth(1, Value::of(false));
        });
        if (UObject* c = get(actor, L"Controller").object)
            call_reflected(c, STR("SetControlRotation"), [&](Params& p) { set(p.nth(0), L"Yaw", yaw); });
        return r.has_value();
    }
    inline auto face(UObject* actor, UObject* other) -> bool
    {
        auto at = location(other);
        return at && face(actor, *at);
    }

    // ============================================================================================ noticing your cat
    // A roaming animal notices a cat through its detection component (its ExplorationDetectionComponent): its
    // DetectionType says by what, a mask of EAdventureDetectionFlags (1 Vision, 2 Sound, 4 Cone, 8 InPursue; 3 on a
    // roaming animal), and noticing takes it a moment (in sight 250 units off, 2 to 3 s). Noticed, its tree waits its
    // reaction time and chases (Ai.hpp's blackboard notes); a chase that catches your cat starts a fight.
    // Its detection mask now; nullopt for what has no detection component (your cat, a walking cat).
    inline auto detection_flags(UObject* actor) -> std::optional<int>
    {
        if (!assert_game_thread(L"detection_flags")) return std::nullopt;
        Value v = get(detection_component(actor), L"DetectionType");
        if (v.kind == Value::Kind::None) return std::nullopt;
        return static_cast<int>(v.number());
    }
    // Set it (0 notices nothing; the game's own code leaves it as set, seen in game). False without the component.
    inline auto set_detection_flags(UObject* actor, int flags) -> bool
    {
        if (!assert_game_thread(L"set_detection_flags")) return false;
        UObject* c = detection_component(actor);
        return c && set(c, L"DetectionType", flags);
    }
    // Make it lose your cat, as the game's own losing does (its OnCharacterLost): its chase ends and it walks back to
    // where it started, then roams. False for what isn't a roaming animal.
    inline auto calm(UObject* actor) -> bool
    {
        if (!assert_game_thread(L"calm") || !actor || !player()) return false;
        return call_reflected(actor, STR("OnCharacterLost"), [](Params& p) { p.set_nth(0, Value::of(player())); }).has_value();
    }
    // Make it notice your cat now, as the game's own noticing does (its OnCharacterDetected: Detected, Target, where it
    // started and its reaction time on its blackboard), even while it ignores your cat (seen); it gives chase after its
    // reaction time (senses().react_to_chase, 0.5 s). With its mask 0 the chase's own detection may lose your cat as it
    // goes (not tried). False for what isn't a roaming animal (or a boss, or prey to pounce).
    inline auto notice_player(UObject* actor) -> bool
    {
        if (!assert_game_thread(L"notice_player") || !actor || !player()) return false;
        return call_reflected(actor, STR("OnCharacterDetected"), [](Params& p) { p.set_nth(0, Value::of(player())); }).has_value();
    }
    namespace detail
    {
        struct Ignoring
        {
            std::map<UObject*, int> was;      // the animals made to ignore your cat, and the mask each had
            std::set<UObject*> by_stealth;    // those ignore_player_everywhere zeroed (turning it off puts back only these)
            bool everywhere{};
            std::optional<TimerId> keeper;
        };
        inline auto ignoring() -> Ignoring&
        {
            static Ignoring i;
            return i;
        }
    } // namespace detail
    // Make an animal ignore your cat (its detection mask 0: it notices nothing, by sight or sound; one that had noticed
    // your cat loses it), or notice again with the mask it had (`ignore` false). False without a detection component.
    inline auto ignore_player(UObject* actor, bool ignore = true) -> bool
    {
        if (!assert_game_thread(L"ignore_player")) return false;
        auto flags = detection_flags(actor);
        if (!flags) return false;
        auto& was = detail::ignoring().was;
        if (ignore)
        {
            detail::ignoring().by_stealth.erase(actor);   // the mod's own now: stealth turned off leaves it
            if (!was.contains(actor)) was[actor] = *flags;
            set_detection_flags(actor, 0);
            if (blackboard_bool(actor, L"Detected").value_or(false)) calm(actor);
            return true;
        }
        detail::ignoring().by_stealth.erase(actor);
        auto it = was.find(actor);
        if (it == was.end()) return *flags != 0 || set_detection_flags(actor, 3);   // not ignore_player's: left as it is
        const int back = it->second;   // (a mask of 0 it was given otherwise gets the roaming animals' 3)
        was.erase(it);
        return set_detection_flags(actor, back);
    }
    // Whether it ignores your cat (by ignore_player, or its mask 0 for any reason).
    inline auto ignoring_player(UObject* actor) -> bool { return detection_flags(actor) == 0; }
    // All the roaming animals ignore your cat while it's on: each within 5,000 units of your cat as it comes near (a
    // look once a second); off, each it changed is back to the mask it had (one the mod made to ignore your cat itself
    // stays so). A stealth mode.
    inline auto ignore_player_everywhere(bool on) -> void
    {
        if (!assert_game_thread(L"ignore_player_everywhere")) return;
        auto& s = detail::ignoring();
        s.everywhere = on;
        auto sweep = [] {
            auto& st = detail::ignoring();
            std::erase_if(st.was, [](auto& e) { return !detail::object_staying(e.first, nullptr); });
            std::erase_if(st.by_stealth, [&](UObject* a) { return !st.was.contains(a); });
            if (!st.everywhere) return;
            for (const Nearby& n : nearby(Kind::Creatures, 5000))
                if (!st.was.contains(n.actor) && ignore_player(n.actor, true)) st.by_stealth.insert(n.actor);
        };
        if (on)
        {
            sweep();
            if (!s.keeper) s.keeper = every(1.0, [sweep] { detail::guarded(L"ignore_player_everywhere", sweep); });
            return;
        }
        if (s.keeper)
        {
            cancel(*s.keeper);
            s.keeper.reset();
        }
        auto mine = s.by_stealth;
        for (UObject* actor : mine)
            if (detail::object_staying(actor, nullptr)) ignore_player(actor, false);
        s.by_stealth.clear();
    }
    // Make it run from a place or another actor: `distance` cm the other way, at its chase speed (senses().
    // walk_speed_chasing, 400) unless `options` says, given back to its tree at the end (a move_to: `done` is told how
    // it ended). False as move_to is.
    inline auto flee(UObject* actor, Vec3 from, double distance = 800, std::optional<MoveOptions> options = std::nullopt,
                     std::function<void(WalkResult)> done = {}) -> bool
    {
        if (!assert_game_thread(L"flee")) return false;
        auto at = location(actor);
        if (!at) return false;
        double dx = at->x - from.x, dy = at->y - from.y, len = std::hypot(dx, dy);
        if (len < 1) dx = 1, dy = 0, len = 1;
        // The way away, on the mesh (a rock, a river or the mesh's edge that way stops it short: it runs as far as it
        // can, then its move is Blocked; seen in game, a mouse stood 490 units on of 600).
        Vec3 to{at->x + dx / len * distance, at->y + dy / len * distance, at->z};
        if (auto g = ground(to.x, to.y, at->z + 500)) to.z = *g;
        if (auto on = nav_point(to, actor)) to = *on;
        MoveOptions o = options.value_or(MoveOptions{});
        if (!options)
        {
            auto s = senses(actor);
            o.speed = s.walk_speed_chasing ? *s.walk_speed_chasing : 400;
            o.restart_after = true;
        }
        return move_to(actor, to, o, std::move(done));
    }
    inline auto flee(UObject* actor, UObject* from, double distance = 800, std::optional<MoveOptions> options = std::nullopt,
                     std::function<void(WalkResult)> done = {}) -> bool
    {
        auto at = location(from);
        return at && flee(actor, *at, distance, options, std::move(done));
    }

    // ============================================================================================ swapping trees
    // Run another of the game's trees on an AI now (its controller's RunBehaviorTree: the tree's blackboard put in, a
    // tree on another blackboard starting with its keys clear), from its start. The game starts its controller's own
    // trees again on its own occasions (a fight, the fight's end: set_trees). False without an AI or a tree.
    //   wcmods::run_tree(mouse, wcmods::ai_tree_named(L"BT_BossEnemy"));   // it idles and grazes, nothing else
    inline auto run_tree(UObject* actor, UObject* tree) -> bool
    {
        if (!assert_game_thread(L"run_tree") || !tree || !is_a(tree, STR("/Script/AIModule.BehaviorTree"))) return false;
        UObject* c = ai_controller(actor);
        if (!c) return false;
        if (auto m = detail::ai_move_of(actor)) detail::end_move(m, WalkResult::Cancelled);
        auto r = call_reflected(c, STR("RunBehaviorTree"), [&](Params& p) { p.set_nth(0, Value::of(tree)); });
        return r && r->get(L"ReturnValue").boolean();
    }
    // The trees an AI's controller starts on its own: `roaming`, its BehaviorTree (a roaming animal's BT_Enemy, a
    // walking cat's BT_WalkingNPC), and `fight`, its CombatBehaviorTree (a roaming animal's BT_CombatEnemy; a walking
    // cat's controller has none). nullptr where it has none.
    struct AiTrees
    {
        UObject* roaming{};
        UObject* fight{};
    };
    inline auto ai_trees_set(UObject* actor) -> AiTrees
    {
        if (!assert_game_thread(L"ai_trees_set")) return {};
        UObject* c = ai_controller(actor);
        return {get(c, L"BehaviorTree").object, get(c, L"CombatBehaviorTree").object};
    }
    // Set them, for the game's own starts to run: `fight` when its turn comes in a fight (on the fight's own actor: a
    // fight's enemy isn't the roaming animal, set it at CombatStart). Only BT_CombatEnemy works as a fight tree: its
    // attack subtree BT_AttackEnemy set alone ran, but never handed the turn on, and the fight stalled (seen). nullptr
    // leaves one as it is. Not the tree running now: run_tree() is that.
    // False without an AI, or a tree its controller has no place for.
    inline auto set_trees(UObject* actor, UObject* roaming, UObject* fight = nullptr) -> bool
    {
        if (!assert_game_thread(L"set_trees")) return false;
        UObject* c = ai_controller(actor);
        if (!c) return false;
        bool ok = true;
        if (roaming) ok = set(c, L"BehaviorTree", roaming) && ok;
        if (fight) ok = set(c, L"CombatBehaviorTree", fight) && ok;
        return ok;
    }

    // ============================================================================================ following
    // How follow() keeps after its target: within `distance` cm of it (it sets off again when the target is farther
    // than that and a little), at `speed` cm/s (0 keeps its own), looking `every` seconds.
    struct FollowOptions
    {
        double distance{150};
        double speed{0};
        double every{0.25};
    };
    namespace detail
    {
        struct Follow
        {
            UObject* actor{};
            UClass* cls{};
            UObject* target{};
            UClass* target_cls{};
            FollowOptions options;
            bool was_running{};
            TimerId timer{};
            std::chrono::steady_clock::time_point wait_till{};   // after a move that ended Blocked: a pause first
            bool ended{};   // a look already due when it ended (the same frame's timers) does nothing
        };
        inline auto follows() -> std::vector<std::shared_ptr<Follow>>&
        {
            static std::vector<std::shared_ptr<Follow>> all;
            return all;
        }
        inline auto follow_of(UObject* actor) -> std::shared_ptr<Follow>
        {
            for (auto& f : follows())
                if (f->actor == actor) return f;
            return nullptr;
        }
        inline auto end_follow(const std::shared_ptr<Follow>& f, bool put_back) -> void
        {
            if (f->ended) return;
            f->ended = true;
            cancel(f->timer);
            auto& all = follows();
            all.erase(std::remove(all.begin(), all.end(), f), all.end());
            if (!object_staying(f->actor, f->cls)) return;
            if (auto m = ai_move_of(f->actor)) end_move(m, WalkResult::Cancelled);
            if (put_back && f->was_running) restart_ai(f->actor);
        }
        inline auto keep_following(const std::shared_ptr<Follow>& f) -> void
        {
            if (f->ended) return;
            if (!object_staying(f->actor, f->cls) || !object_staying(f->target, f->target_cls)) return end_follow(f, true);
            // Its tree run again by someone (restart_ai, run_tree): the follow is over, that kept.
            if (ai_running(f->actor)) return end_follow(f, false);
            if (ai_move_of(f->actor)) return;   // on its way
            if (std::chrono::steady_clock::now() < f->wait_till) return;
            auto me = location(f->actor), them = location(f->target);
            if (!me || !them || std::hypot(me->x - them->x, me->y - them->y) <= f->options.distance + 60) return;
            // A move that can't get there (asleep far from your cat, the target off its mesh) waits 2 s before the next.
            std::weak_ptr<Follow> weak = f;
            auto blocked = [weak](WalkResult r) {
                if (auto g = weak.lock(); g && r == WalkResult::Blocked) g->wait_till = std::chrono::steady_clock::now() + std::chrono::seconds(2);
            };
            if (!move_to(f->actor, f->target, {.speed = f->options.speed, .radius = f->options.distance}, blocked))
                f->wait_till = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        }
    } // namespace detail
    // Make an AI follow another actor (your cat, another cat) about: whenever it's farther than `distance` from it, it
    // goes after it (a move_to with the target as its goal, its logic stopped), and waits when it's close. Until
    // stop_following(), it or the target gone, or its tree run again (restart_ai, run_tree). False without an AI, a
    // target, or for your cat. (The game's own escort tree, BT_Escort, doesn't do it: run on a mod's cat with its keys
    // set, its Move To Location stood still.)
    //   wcmods::follow(cat.actor(), wcmods::player());   // a cat at your cat's heels
    inline auto follow(UObject* actor, UObject* target, FollowOptions options = {}) -> bool
    {
        if (!assert_game_thread(L"follow") || !actor || !target || actor == target || actor == player()) return false;
        if (!ai_controller(actor) || !location(target)) return false;
        bool was_running = ai_running(actor);
        if (auto old = detail::follow_of(actor))
        {
            was_running = old->was_running;
            detail::end_follow(old, false);
        }
        stop_ai(actor);   // its tree would wander off between goes
        auto f = std::make_shared<detail::Follow>();
        f->actor = actor;
        f->cls = actor->GetClassPrivate();
        f->target = target;
        f->target_cls = target->GetClassPrivate();
        f->options = options;
        f->was_running = was_running;
        detail::follows().push_back(f);
        f->timer = every(std::max(0.05, options.every), [f] { detail::guarded(L"follow", [&] { detail::keep_following(f); }); });
        detail::keep_following(f);
        return true;
    }
    // Stop following: it stands where it is, and its tree runs again if it ran before follow() (`put_back`; false
    // leaves it standing). False when it wasn't following.
    inline auto stop_following(UObject* actor, bool put_back = true) -> bool
    {
        if (!assert_game_thread(L"stop_following")) return false;
        auto f = detail::follow_of(actor);
        if (!f) return false;
        detail::end_follow(f, put_back);
        return true;
    }
    // Whether it's following something (by follow()).
    inline auto following(UObject* actor) -> bool { return detail::follow_of(actor) != nullptr; }

    // ============================================================================================ a fight's AI
    // In a fight each enemy is its own actor (BP_Combat_Character_Base_C, not the roaming animal) with its controller:
    // as a round starts its fight tree (BT_CombatEnemy, then BT_AttackEnemy) picks its target, and its move goes into
    // its combat component's AttackSelected as its turn comes, the hit about 1.7 s later (seen in game). Its choices
    // are behind chance checks by its tier (Fighter::ai_tier: 1 to 6, 7 Terrible, 8 Perfect), from AICombatChances.csv.

    // A tier's chances (AICombatChances.csv's row, which the tuning manager keeps as a map of its own), each 0 to
    // 1: curing its status, healing, resting when exhausted, supporting an ally, a buff, a debuff, attacking the weakest
    // cat, the slowest, a random move, a move by stance, one that hits all, the strongest, one that gives a status.
    struct AiChances
    {
        float cure_status{}, cure_health{}, exhausted{}, support{}, buff{}, debuff{}, attack_weakest{}, attack_slower{},
            select_random{}, select_stance{}, select_aoe{}, select_powerful{}, select_status{};
    };
    namespace detail
    {
        // The tuning manager's map of AICombatChances.csv (TMap<FString, FSwtAdventureAICombatChances>: 0x58-byte slots,
        // the tier's name, then the row from +0x10), found by what it holds: among its unreflected members (+0x460 to
        // +0x8C0: +0x690 on build 26337109), the map whose names include Tier1 and Perfect. No signature can find it: the
        // lookup reaches it through the manager's global, and its loader loads every table with the same code
        // (docs/reverse-engineering.md, "The game's AI"). Looked for once.
        inline auto chances_map() -> const uint8_t*
        {
            static std::optional<size_t> at;
            auto* m = reinterpret_cast<const uint8_t*>(manager(STR("tuning")));
            if (!m || !is_a(manager(STR("tuning")), STR("/Script/SwtAdventure.SwtAdventureTuningManager"))) return nullptr;
            auto holds = [&](size_t off) {
                std::vector<const uint8_t*> slots;
                if (!set_slots(m + off, 0x58, slots) || slots.size() < 2 || slots.size() > 16) return false;
                bool tier1 = false, perfect = false;
                for (const uint8_t* e : slots)
                {
                    std::wstring n = fstring_at(e);
                    tier1 = tier1 || same_key(n, L"Tier1");
                    perfect = perfect || same_key(n, L"Perfect");
                }
                return tier1 && perfect;
            };
            if (at && holds(*at)) return m + *at;
            at.reset();
            for (size_t off = 0x460; off < 0x8C0; off += 8)
                if (holds(off))
                {
                    at = off;
                    return m + off;
                }
            return nullptr;
        }
        // The map's slot for a tier by its name (L"Terrible", L"Tier1"... L"Tier6", L"Perfect").
        inline auto chances_row(std::wstring_view tier) -> Value
        {
            const uint8_t* map = chances_map();
            std::vector<const uint8_t*> slots;
            if (!set_slots(map, 0x58, slots)) return {};
            for (const uint8_t* e : slots)
                if (same_key(fstring_at(e), tier))
                    return struct_at(STR("/Script/SwtAdventure.SwtAdventureAICombatChances"), const_cast<uint8_t*>(e) + 0x10);
            return {};
        }
        inline constexpr const wchar_t* CHANCE_FIELDS[] = {L"CureStatus", L"CureHealth", L"Exhausted", L"Support", L"Buff", L"Debuff",
                                                           L"AttackWeakest", L"AttackSlower", L"SelectRandom", L"SelectStance",
                                                           L"SelectAOE", L"SelectPowerful", L"SelectStatus"};
    } // namespace detail
    // A tier's chances by its name (L"Terrible", L"Tier1" to L"Tier6", L"Perfect"); nullopt for another, or without
    // the table on this build.
    inline auto ai_chances(std::wstring_view tier) -> std::optional<AiChances>
    {
        if (!assert_game_thread(L"ai_chances")) return std::nullopt;
        Value row = detail::chances_row(tier);
        if (row.kind != Value::Kind::Struct) return std::nullopt;
        AiChances c;
        float* out[] = {&c.cure_status, &c.cure_health, &c.exhausted, &c.support, &c.buff, &c.debuff, &c.attack_weakest,
                        &c.attack_slower, &c.select_random, &c.select_stance, &c.select_aoe, &c.select_powerful, &c.select_status};
        for (size_t k = 0; k < 13; ++k) *out[k] = static_cast<float>(get(row, detail::CHANCE_FIELDS[k]).number());
        return c;
    }
    // Set one of a tier's chances by the column's name (L"SelectRandom", L"AttackWeakest", L"CureHealth"...: the
    // table's own), 0 to 1, for every fighter of that tier from then on (the game reads the row as its tree decides).
    // False for a tier or a column the table hasn't, or a chance outside 0 to 1.
    inline auto set_ai_chance(std::wstring_view tier, std::wstring_view kind, double chance) -> bool
    {
        if (!assert_game_thread(L"set_ai_chance") || !(chance >= 0 && chance <= 1)) return false;
        bool known = false;
        for (const wchar_t* f : detail::CHANCE_FIELDS) known = known || kind == f;
        Value row = detail::chances_row(tier);
        return known && row.kind == Value::Kind::Struct && set(row, kind, chance);
    }
    // Set a fighter's tier for this fight (EAICombatProfile: 1 to 6, 7 Terrible: a random move every time, 8 Perfect):
    // its tree's chance checks read it as they go (seen: a tier written as the fight began read back so). False
    // outside a fight's fighter, or without the member.
    inline auto set_ai_tier(Fighter fighter, int tier) -> bool
    {
        if (!assert_game_thread(L"set_ai_tier") || tier < 1 || tier > 8) return false;
        int32_t* t = fighter.ai_tier();
        if (!t) return false;
        *t = tier;
        return true;
    }

    namespace detail
    {
        // A fighter whose moves limit_moves() cut: its component, and what's where (the move each place holds now, by
        // the place it had) and how many it had.
        struct Limited
        {
            UObject* component{};
            UClass* cls{};
            std::vector<int> at;
            int32_t count{};
        };
        inline auto limited() -> std::vector<Limited>&
        {
            static std::vector<Limited> all;
            return all;
        }
        inline auto move_array(Fighter& f, int32_t*& count, uint8_t*& data, int32_t& size) -> bool
        {
            count = f.move_count();
            auto* type = static_cast<RC::Unreal::UStruct*>(object(STR("/Script/SwtAdventure.SwtAdventureAttackMoveStruct")));
            if (!count || !type || *count <= 0 || *count > 32 || *(count + 1) < *count) return false;
            data = *reinterpret_cast<uint8_t**>(reinterpret_cast<uint8_t*>(count) - 8);
            size = type->GetStructureSize();
            return data && size > 0;
        }
        // Two moves swapped in place (the engine moves array elements as bytes too).
        inline auto swap_moves(uint8_t* data, int32_t size, int a, int b) -> void
        {
            if (a == b) return;
            std::vector<uint8_t> tmp(static_cast<size_t>(size));
            std::memcpy(tmp.data(), data + a * size, size);
            std::memcpy(data + a * size, data + b * size, size);
            std::memcpy(data + b * size, tmp.data(), size);
        }
        inline auto put_back(Limited& l) -> void
        {
            Fighter f{l.component};
            int32_t* count = f.move_count();
            if (!count) return;
            *count = l.count;   // every move counted again, then each back in its place
            int32_t* c2 = nullptr;
            uint8_t* data = nullptr;
            int32_t size = 0;
            if (!move_array(f, c2, data, size)) return;
            for (int pos = 0; pos < l.count; ++pos)
                for (int j = pos; j < l.count; ++j)
                    if (l.at[j] == pos)
                    {
                        swap_moves(data, size, pos, j);
                        std::swap(l.at[pos], l.at[j]);
                        break;
                    }
        }
        inline auto watch_fight_end() -> void
        {
            static bool on = false;
            if (on) return;
            on = true;
            wcmods::on(Event::CombatEnd, [](const EventInfo&) {
                for (auto& l : limited())
                    if (object_staying(l.component, l.cls)) put_back(l);
                limited().clear();
            });
        }
    } // namespace detail
    // Limit a fighter to some of its moves (by their place in Fighter::moves(), as the fight began): its moves are put
    // in that order at the front and its count cut to them, so whatever its tree picks is one of them (seen: an enemy
    // limited to its third move used it). The others are kept behind, back with restore_moves() or as the fight ends.
    // Call it again to change the limit (places are always the first ones'). False outside a fight, or for a place it
    // hasn't.
    inline auto limit_moves(Fighter fighter, const std::vector<int>& moves) -> bool
    {
        if (!assert_game_thread(L"limit_moves") || !fighter || moves.empty()) return false;
        int32_t* count = nullptr;
        uint8_t* data = nullptr;
        int32_t size = 0;
        auto& all = detail::limited();
        auto it = std::find_if(all.begin(), all.end(), [&](auto& l) { return l.component == fighter.component; });
        if (it != all.end()) detail::put_back(*it);   // from the full list again
        if (!detail::move_array(fighter, count, data, size)) return false;
        for (int m : moves)
            if (m < 0 || m >= *count) return false;
        detail::Limited l;
        l.component = fighter.component;
        l.cls = fighter.component->GetClassPrivate();
        l.count = *count;
        for (int k = 0; k < *count; ++k) l.at.push_back(k);
        for (size_t pos = 0; pos < moves.size(); ++pos)
        {
            int j = static_cast<int>(std::find(l.at.begin(), l.at.end(), moves[pos]) - l.at.begin());
            if (j < static_cast<int>(pos)) return false;   // the same place twice
            detail::swap_moves(data, size, static_cast<int>(pos), j);
            std::swap(l.at[pos], l.at[j]);
        }
        *count = static_cast<int32_t>(moves.size());
        if (it != all.end()) *it = l;
        else all.push_back(l);
        detail::watch_fight_end();
        return true;
    }
    // Give it all its moves back, in their order. False when limit_moves() didn't cut them.
    inline auto restore_moves(Fighter fighter) -> bool
    {
        if (!assert_game_thread(L"restore_moves")) return false;
        auto& all = detail::limited();
        auto it = std::find_if(all.begin(), all.end(), [&](auto& l) { return l.component == fighter.component; });
        if (it == all.end()) return false;
        if (detail::object_staying(it->component, it->cls)) detail::put_back(*it);
        all.erase(it);
        return true;
    }

    namespace detail
    {
        struct AutoFight
        {
            bool on{};
            std::optional<TimerId> timer;
            std::chrono::steady_clock::time_point next{};
            int turns{};
        };
        inline auto auto_fight_state() -> AutoFight&
        {
            static AutoFight a;
            return a;
        }
        // Your cat's move with the most damage it has the stamina for (by Fighter::moves(): Damage, StaminaCost), or -1.
        inline auto best_move() -> int
        {
            Fighter me = fight_cat();
            Resource st = Cat{me.actor()}.combat_stamina();   // in a fight player() is nullptr: the fight's own cat
            const double stamina = st ? *st.value : 1e9;
            int best = -1;
            double best_damage = -1;
            auto all = me.moves();
            for (int k = 0; k < static_cast<int>(all.size()) && k < 4; ++k)
            {
                double cost = get(all[k], L"StaminaCost").number(), damage = get(all[k], L"Damage").number();
                if (cost <= stamina && damage > best_damage) best = k, best_damage = damage;
            }
            return best;
        }
    } // namespace detail
    // Take your cat's turns in fights for you (on) or not: on each of its turns (the fight menu up) its move with the
    // most damage it has the stamina for, else a rest; until turned off. The SDK's own player, not the game's AI (your
    // cat's fighter has no AI controller). How many turns it took: auto_fight_turns().
    inline auto auto_fight(bool on) -> void
    {
        if (!assert_game_thread(L"auto_fight")) return;
        auto& a = detail::auto_fight_state();
        a.on = on;
        if (!on)
        {
            if (a.timer) cancel(*a.timer);
            a.timer.reset();
            return;
        }
        if (a.timer) return;
        a.timer = every(0.3, [] {
            detail::guarded(L"auto_fight", [] {
                auto& a = detail::auto_fight_state();
                if (!a.on || !combat_active() || !fight_menu() || std::chrono::steady_clock::now() < a.next) return;
                int move = detail::best_move();
                bool went = move >= 0 ? fight_attack(move) : fight_rest();
                if (went)
                {
                    ++a.turns;
                    a.next = std::chrono::steady_clock::now() + std::chrono::seconds(3);   // the menu goes as the turn plays
                }
            });
        });
    }
    inline auto auto_fight_turns() -> int { return detail::auto_fight_state().turns; }
} // namespace wcmods
