// Ai.hpp: the game's AI. A roaming animal or a clan cat walking its path has an AI controller running one of the game's
// behaviour trees (BT_Enemy for an animal, BT_CombatEnemy in its fights, BT_WalkingNPC for a walking cat), which keeps
// what it knows on its blackboard (BB_Enemy...). From C++: an AI's tree and what it's doing now, its blackboard's keys
// read and written, its logic stopped and started again, the game's trees read as data, an AI sent to a place or
// after another actor, and an animal made to ignore your cat, notice it, give it up or run from it
// (docs/plans/cpp-sdk-ai.md).
// Game thread only. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call.
//
//   for (UObject* a : wcmods::fight_animals(2000)) wcmods::stop_ai(a);           // the animals near your cat stand still
//   wcmods::move_to(mouse, wcmods::Vec3{x, y, z});                                // it walks there and stands
#pragma once

#include <algorithm>
#include <chrono>
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
} // namespace wcmods
