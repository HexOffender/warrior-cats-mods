// WCMods/Story.hpp: quests, fights, and the game's events as one list. Game thread only. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <algorithm>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>

namespace wcmods
{
    // ============================================================================================ quests
    struct Quest
    {
        UObject* quest{};
        std::wstring id;       // "Main_03": the quest graph's name without its prefix
        std::wstring tag;      // its gameplay tag ("Quest.Main.3"), or empty
        std::wstring graph;    // the quest graph object's name
        std::wstring type;     // "MainQuest", "SideQuest"
        std::wstring status;   // "QuestAvailable", "OngoingQuest", "QuestComplete", "QuestTurnedIn"...
        std::wstring result;   // "Any", "Success", "Fail"
        bool tracked{};
        double xp{};
    };
    struct Objective
    {
        UObject* objective{};
        std::wstring id;
        int index{};
        std::optional<double> current, target;
        std::wstring status;   // "NotStarted", "InProgress", "Failed", "Succeeded"...
        UObject* point{};      // where to go, when it has one
    };

    inline auto quest_manager() -> UObject* { return manager(STR("quests")); }

    // A quest object described: it's named after its class, and the quest graph that holds it says which
    // quest it is.
    inline auto describe_quest(UObject* q) -> Quest
    {
        Quest out;
        out.quest = q;
        if (!q) return out;
        UObject* graph = q->GetOuterPrivate();
        out.graph = name(graph);
        out.id = out.graph;
        for (auto prefix : {L"QuestGraphProcedural_", L"QuestGraph_"})
            if (out.id.starts_with(prefix)) out.id = out.id.substr(std::wstring_view(prefix).size());
        if (out.id.empty()) out.id = name(q);
        out.tag = get(graph, L"questTag.TagName").string();
        if (out.tag == L"None") out.tag.clear();
        out.type = get(q, L"questType").text;
        out.status = get(q, L"QuestStatus").text;
        out.result = get(q, L"QuestResult").text;
        out.tracked = get(q, L"bTracked").boolean();
        out.xp = get(q, L"ExperienceReward").number();
        return out;
    }

    // Every quest the manager holds (its Quests list holds {Quest, Line, Node} entries).
    inline auto quests() -> std::vector<Quest>
    {
        std::vector<Quest> out;
        for (Value& entry : elements(quest_manager(), L"Quests"))
        {
            UObject* q = get(entry, L"Quest").object;
            if (q) out.push_back(describe_quest(q));
        }
        return out;
    }

    // The quest the player follows, or nullptr.
    inline auto tracked_quest() -> UObject*
    {
        auto r = call_reflected(quest_manager(), STR("GetCurrentTrackedQuest"));
        return r ? r->get(L"ReturnValue").object : nullptr;
    }

    namespace detail
    {
        // The quest manager's calls that take a tag: the tag goes into the first parameter.
        inline auto quest_call(const TCHAR* function, std::wstring_view tag, const std::function<void(Params&)>& more = {}) -> std::optional<Params>
        {
            return call_reflected(quest_manager(), function, [&](Params& p) {
                set(p.nth(0), L"TagName", tag);
                if (more) more(p);
            });
        }
    } // namespace detail

    // A quest's status and result by its tag: quest_status(L"Quest.Main.3") -> L"OngoingQuest"; empty when unknown.
    inline auto quest_status(std::wstring_view tag) -> std::wstring
    {
        auto r = detail::quest_call(STR("GetQuestStatus"), tag);
        return r ? r->get(L"ReturnValue").string() : std::wstring{};
    }
    inline auto quest_result(std::wstring_view tag) -> std::wstring
    {
        auto r = detail::quest_call(STR("GetQuestResult"), tag);
        return r ? r->get(L"ReturnValue").string() : std::wstring{};
    }
    inline auto quest_successes(std::wstring_view tag) -> std::optional<double>
    {
        auto r = detail::quest_call(STR("GetCurrentSuccessCount"), tag);
        if (!r) return std::nullopt;
        Value v = r->get(L"ReturnValue");
        return v ? std::optional<double>(v.number()) : std::nullopt;
    }
    // Start or hand out a quest by tag, the way the game's own quest givers do.
    inline auto start_quest(std::wstring_view tag) -> bool
    {
        UObject* c = controller();
        return c && detail::quest_call(STR("StartQuestOfTag"), tag, [&](Params& p) { p.set_nth(1, Value::of(c)); }).has_value();
    }
    inline auto give_quest(std::wstring_view tag) -> bool { return detail::quest_call(STR("GiveQuestOfTag"), tag).has_value(); }
    // Follow a quest, or stop.
    inline auto track_quest(UObject* quest, bool on = true) -> bool
    {
        return quest && call_reflected(quest_manager(), STR("SetTracked"), [&](Params& p) {
                            p.set_nth(0, Value::of(quest));
                            p.set_nth(1, Value::of(on));
                        }).has_value();
    }

    // A quest's objectives, in order.
    inline auto objectives(UObject* quest) -> std::vector<Objective>
    {
        std::vector<Objective> out;
        if (!quest) return out;
        UObject* qm = quest_manager();
        for (UObject* o : find_all(STR("ObjectiveBase")))
        {
            if (get(o, L"QuestBase").object != quest) continue;
            Objective ob;
            ob.objective = o;
            if (auto r = call_reflected(o, STR("GetObjectiveIDString"))) ob.id = r->get(L"ReturnValue").string();
            ob.index = static_cast<int>(get(o, L"ObjectiveIdx").number());
            if (auto n = call<int32_t>(o, STR("GetCurrentNumber"))) ob.current = *n;
            if (auto n = call<int32_t>(o, STR("GetTargetNumber"))) ob.target = *n;
            if (!ob.id.empty())
            {
                auto r = call_reflected(qm, STR("GetObjectiveStatus"), [&](Params& p) { p.set_nth(0, Value::of(std::wstring_view(ob.id))); });
                if (r) ob.status = r->get(L"ReturnValue").string();
            }
            ob.point = get(o, L"ObjectivePoint").object;
            out.push_back(ob);
        }
        std::sort(out.begin(), out.end(), [](const Objective& a, const Objective& b) { return a.index < b.index; });
        return out;
    }

    // The chapter the story is in ("Chapter00"), or empty.
    inline auto chapter() -> std::wstring
    {
        UObject* context = player() ? player() : world();
        auto r = call_reflected(object(STR("/Script/SwtQuest.Default__BFLSwtQuest")), STR("GetChapter"),
                                [&](Params& p) { p.set_nth(0, Value::of(context)); });
        if (!r) return {};
        for (int i = 1; i < r->count(); ++i)
        {
            Value v = r->nth(i);
            if (v.kind == Value::Kind::Text || v.kind == Value::Kind::Enum) return v.string();
        }
        return {};
    }

    // ============================================================================================ fights
    // The fight going on now: the game state's combat director, or nullptr.
    inline auto combat_director() -> UObject*
    {
        UObject* d = get(game_state(), L"Director").object;
        return is_a(d, STR("/Script/SwtAdventure.SwtAdventureCombatDirector")) ? d : nullptr;
    }
    inline auto combat_active() -> bool { return combat_director() != nullptr; }

    // A fighter: a cat or animal's combat component, with its stats for this fight (wcmods' hidden members
    // on it; the pointers are nullptr when wcmods hasn't got them on this build).
    struct Fighter
    {
        UObject* component{};
        explicit operator bool() const { return component != nullptr; }
        auto actor() -> UObject*
        {
            auto r = call_reflected(component, STR("GetOwnerCharacter"));
            return r ? r->get(L"ReturnValue").object : nullptr;
        }
        auto level() -> int32_t* { return member<int32_t>(component, L"/Script/SwtAdventure.TurnBasedCombatComponent", L"WCM_Level"); }
        auto stance() -> uint8_t* { return member<uint8_t>(component, L"/Script/SwtAdventure.TurnBasedCombatComponent", L"WCM_Stance"); }
        auto stat(Stat which) -> float*
        {
            static constexpr const wchar_t* names[] = {L"WCM_Prowess", L"WCM_Strength", L"WCM_Resilience",
                                                       L"WCM_Instinct", L"WCM_Agility", L"WCM_Stamina"};
            return member<float>(component, L"/Script/SwtAdventure.TurnBasedCombatComponent", names[static_cast<int>(which)]);
        }
        // The move it has picked (an AttackMove row: Damage, Accuracy, StaminaCost...), as a struct Value.
        auto move() -> Value { return get(component, L"AttackSelected"); }
        auto targets() -> std::vector<UObject*>
        {
            std::vector<UObject*> out;
            for (Value& v : elements(component, L"CurrentTarget"))
                if (v.object) out.push_back(v.object);
            return out;
        }
        // Its team (ESwtAdventureCombatTeam: 1 the player's side, 2 the enemy's), the AI's tier for this fight
        // (EAICombatProfile: 1–6, 7 Terrible, 8 Perfect; 0 for your cat), and the moves it has to pick from,
        // each an AttackMove row as a struct Value (AttackMoveTag, Damage, Accuracy, StaminaCost, Stance...):
        // the component's own members, filled when the fight is set up (0 and none outside one). The pointers
        // are nullptr when wcmods hasn't got the members on this build.
        auto team() -> uint8_t* { return member<uint8_t>(component, L"/Script/SwtAdventure.TurnBasedCombatComponent", L"WCM_Team"); }
        auto ai_tier() -> int32_t* { return member<int32_t>(component, L"/Script/SwtAdventure.TurnBasedCombatComponent", L"WCM_AITier"); }
        auto move_count() -> int32_t* { return member<int32_t>(component, L"/Script/SwtAdventure.TurnBasedCombatComponent", L"WCM_MoveCount"); }
        auto moves() -> std::vector<Value>
        {
            std::vector<Value> out;
            int32_t* count = move_count();
            if (!count) return out;
            // The count is a TArray's (pointer, count, capacity): the data pointer is the 8 bytes before it and
            // the capacity the 4 after. A count that doesn't fit its capacity isn't an array's (a game update
            // that moved the member somewhere else): nothing is read then.
            const int32_t capacity = *(count + 1);
            if (*count <= 0 || *count > 32 || capacity < *count) return out;
            uint8_t* data = *reinterpret_cast<uint8_t**>(reinterpret_cast<uint8_t*>(count) - 8);
            auto* type = static_cast<RC::Unreal::UStruct*>(object(STR("/Script/SwtAdventure.SwtAdventureAttackMoveStruct")));
            if (!data || !type) return out;
            const int32_t size = type->GetStructureSize();
            for (int32_t i = 0; i < *count; ++i) out.push_back(struct_at(type, data + i * size));
            return out;
        }
    };
    // A fighter from a cat's actor or its combat component.
    inline auto fighter(UObject* actor_or_component) -> Fighter
    {
        if (!actor_or_component) return {};
        if (is_a(actor_or_component, STR("/Script/SwtAdventure.SwtAdventureCharacter")))
            return Fighter{get(actor_or_component, L"TurnBasedCombatComponent").object};
        return Fighter{actor_or_component};
    }

    namespace detail
    {
        inline auto fighters(const wchar_t* party) -> std::vector<Fighter>
        {
            std::vector<Fighter> out;
            for (Value& v : elements(combat_director(), party))
                if (v.object) out.push_back(fighter(v.object));
            return out;
        }
    } // namespace detail
    inline auto fight_players() -> std::vector<Fighter> { return detail::fighters(L"PlayerParty"); }
    inline auto fight_enemies() -> std::vector<Fighter> { return detail::fighters(L"EnemyParty"); }
    // Who acts in what order this round, whose turn it is, and the main enemy: actors.
    inline auto fight_turn_order() -> std::vector<UObject*>
    {
        std::vector<UObject*> out;
        for (Value& v : elements(combat_director(), L"TurnOrder"))
            if (v.object) out.push_back(v.object);
        return out;
    }
    inline auto fight_current() -> UObject* { return get(combat_director(), L"CurrentTurnAttackCharacter").object; }
    inline auto fight_main_enemy() -> UObject* { return get(combat_director(), L"MainEnemyCombatCharacter").object; }

    // ============================================================================================ events
    // The game's events as one list, each with what it carries in an EventInfo:
    //   Level         name: the level loaded
    //   Player        object: your cat, or nullptr when it went
    //   Phase         name: the game's phase now ("Game", "PreGame"...), a: the one before
    //   CombatStart   object: the combat director;  CombatEnd: nothing
    //   GenericEvent  name: the event's name (the game's own SwtGameUtil broadcasts)
    //   QuestStatus   object: the quest, a: its status (an enum), b: whether exact
    //   Damage        a: the damage struct (Character, Damage...; its bytes last the callback)
    //   TurnEnded     nothing
    //   Status        object: the status component (its owner is the cat), a: the status type
    enum class Event { Level, Player, Phase, CombatStart, CombatEnd, GenericEvent, QuestStatus, Damage, TurnEnded, Status };
    struct EventInfo
    {
        Event event{};
        std::wstring name;
        UObject* object{};
        Value a, b;
    };

    namespace detail
    {
        struct GameEvents
        {
            std::mutex lock;
            std::map<Event, std::vector<std::shared_ptr<std::function<void(const EventInfo&)>>>> listeners;
            std::set<Event> started;
            bool combat_was{};
            std::wstring phase_was;
            bool polling{};
        };
        inline auto game_events() -> GameEvents&
        {
            static GameEvents e;
            return e;
        }
        inline auto emit(EventInfo info) -> void
        {
            std::vector<std::shared_ptr<std::function<void(const EventInfo&)>>> fns;
            {
                auto& e = game_events();
                std::lock_guard lock(e.lock);
                if (auto it = e.listeners.find(info.event); it != e.listeners.end()) fns = it->second;
            }
            for (auto& fn : fns) guarded(L"an event", [&] { (*fn)(info); });
        }
        inline auto poll_events() -> void
        {
            auto& e = game_events();
            bool combat = combat_active();
            std::wstring phase = get(game_state(), L"CurrentPhase").text;
            bool combat_changed, phase_changed;
            std::wstring phase_was;
            {
                std::lock_guard lock(e.lock);
                combat_changed = combat != e.combat_was;
                phase_changed = phase != e.phase_was;
                phase_was = e.phase_was;
                e.combat_was = combat;
                e.phase_was = phase;
            }
            if (combat_changed)
            {
                if (combat) emit({Event::CombatStart, {}, combat_director()});
                else emit({Event::CombatEnd});
            }
            if (phase_changed && !phase.empty()) emit({Event::Phase, phase, nullptr, Value::of(std::wstring_view(phase_was))});
        }
        // What starts an event's flow the first time something listens: true when the game has what it needs.
        inline auto start_event(Event event) -> bool
        {
            auto hook = [](const TCHAR* path, std::function<void(Call&)> fn) { return on_function(path, std::move(fn)) != 0; };
            switch (event)
            {
            case Event::Level:
                on_level([](std::wstring_view level) { emit({Event::Level, std::wstring(level)}); });
                return true;
            case Event::Player:
                on_player([](UObject* cat) { emit({Event::Player, {}, cat}); });
                return true;
            case Event::Phase:
            case Event::CombatStart:
            case Event::CombatEnd:
            {
                auto& e = game_events();
                bool start;
                {
                    std::lock_guard lock(e.lock);
                    start = !e.polling;
                    e.polling = true;
                }
                if (start) every(0.25, poll_events);
                return true;
            }
            case Event::GenericEvent:
                return hook(STR("/Script/SwtEngine.SwtGameUtil:BroadcastGenericEvent"),
                            [](Call& c) { emit({Event::GenericEvent, c.param(0).string()}); });
            case Event::QuestStatus:
                return hook(STR("/Script/SwtQuest.SwtQuestGameplayGameState:OnQuestStatusChanged"),
                            [](Call& c) { emit({Event::QuestStatus, {}, c.param(0).object, c.param(1), c.param(2)}); });
            case Event::Damage:
                return hook(STR("/Script/SwtAdventure.SwtAdventureCombatDirector:OnRegisterDamage"),
                            [](Call& c) { emit({Event::Damage, {}, c.self(), c.param(0)}); });
            case Event::TurnEnded:
                return hook(STR("/Script/SwtAdventure.SwtAdventureCombatDirector:OnCombatantTurnEnded"),
                            [](Call& c) { emit({Event::TurnEnded, {}, c.self()}); });
            case Event::Status:
                return hook(STR("/Script/SwtAdventure.SwtAdventureStatusComponent:ApplyStatusType"),
                            [](Call& c) { emit({Event::Status, {}, c.self(), c.param(0)}); });
            }
            return false;
        }
    } // namespace detail

    // `fn(info)` on the game thread when the event happens. False when the game hasn't got what the event
    // listens to (a function the hook can't find); then nothing will come.
    inline auto on(Event event, std::function<void(const EventInfo&)> fn) -> bool
    {
        auto& e = detail::game_events();
        bool start;
        {
            std::lock_guard lock(e.lock);
            e.listeners[event].push_back(std::make_shared<std::function<void(const EventInfo&)>>(std::move(fn)));
            start = e.started.insert(event).second;
        }
        if (!start) return true;
        bool ok = detail::start_event(event);
        if (!ok)
        {
            std::lock_guard lock(e.lock);
            e.started.erase(event);
        }
        return ok;
    }
} // namespace wcmods
