// Ai.hpp: the game's AI. A roaming animal or a clan cat walking its path has an AI controller running one of the game's
// behaviour trees (BT_Enemy for an animal, BT_CombatEnemy in its fights, BT_WalkingNPC for a walking cat), which keeps
// what it knows on its blackboard (BB_Enemy...). From C++: an AI's tree and what it's doing now, its blackboard's keys
// read and written, its logic stopped and started again, and the game's trees read as data (docs/plans/cpp-sdk-ai.md).
// Game thread only. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call.
//
//   for (UObject* a : wcmods::fight_animals(2000)) wcmods::stop_ai(a);           // the animals near your cat stand still
//   wcmods::set_blackboard(mouse, L"PointOfInterest", wcmods::Vec3{x, y, z});     // somewhere for it to go and look
#pragma once

#include <cmath>
#include <format>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Game.hpp>
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
    // Walking") and its class (L"BTTask_EnemyGrazing"); empty when none is active (between nodes, or stopped).
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
        auto [board, name] = detail::board_for(actor, key, L"Int");
        if (!board) return std::nullopt;
        detail::KeyValue<int32_t> p{name};
        if (!call(board, STR("GetValueAsInt"), p)) return std::nullopt;
        return p.value;
    }
    inline auto blackboard_vector(UObject* actor, std::wstring_view key) -> std::optional<Vec3>
    {
        auto [board, name] = detail::board_for(actor, key, L"Vector");
        if (!board) return std::nullopt;
        detail::KeyValue<bool> set{name};
        if (!call(board, STR("IsVectorValueSet"), set) || !set.value) return std::nullopt;
        detail::KeyVector p{name};
        if (!call(board, STR("GetValueAsVector"), p)) return std::nullopt;
        return Vec3{p.x, p.y, p.z};
    }

    // Write a key: a Bool, an Int, a Float, a Vector (a place) or an Object (an actor) key, by the value's type. The
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
    inline auto set_blackboard(UObject* actor, std::wstring_view key, int value) -> bool
    {
        if (!assert_game_thread(L"set_blackboard")) return false;
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
} // namespace wcmods
