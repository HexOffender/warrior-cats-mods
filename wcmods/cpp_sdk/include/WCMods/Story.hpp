// WCMods/Story.hpp: quests, fights, and the game's events as one list. Game thread only. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <cstring>

#include <algorithm>
#include <cmath>
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
#include <WCMods/Tables.hpp>
#include <WCMods/Ui.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // ============================================================================================ quests
    struct Quest
    {
        UObject* quest{};
        std::wstring id;       // "Gather": the quest graph's name without its prefix
        std::wstring tag;      // its graph's gameplay tag ("Quest.Procedural.Survival.Gather"), or empty
        std::wstring alias;    // its place in the story ("Quest.Main.1"), which the game keeps its progress by, or empty
        std::wstring graph;    // the quest graph object's name
        std::wstring type;     // "MainQuest", "SideQuest"
        std::wstring status;   // "QuestAvailable", "OngoingQuest", "QuestComplete", "QuestTurnedIn"...
        std::wstring result;   // "Any", "Success", "Fail"
        bool tracked{};
        double xp{};
    };
    // What an objective has its cat gather, track or visit (a gather objective's Targets): the targets' tag, how
    // many count so far of how many (the HUD's "1/3"), and the target actors in the world now.
    struct QuestTarget
    {
        std::wstring tag;
        int current{}, target{};
        std::vector<UObject*> actors;
    };
    struct Objective
    {
        UObject* objective{};
        std::wstring id;
        int index{};
        std::optional<double> current, target;
        std::wstring status;   // "NotStarted", "InProgress", "Failed", "Succeeded"...
        UObject* point{};      // where to go, when it has one
        std::vector<QuestTarget> targets;
    };

    inline auto quest_manager() -> UObject* { return manager(STR("quests")); }

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
        // Whether one of the manager's quests has this alias. The game's status calls add the id they're asked about
        // to the save's QuestProgression (seen in game), so they're only asked about the story's own.
        inline auto known_alias(std::wstring_view alias) -> bool
        {
            if (alias.empty() || alias == L"None") return false;
            for (Value& e : elements(quest_manager(), L"Quests"))
            {
                UObject* q = get(e, L"Quest").object;
                if (q && get(q->GetOuterPrivate(), L"QuestAlias.TagName").string() == alias) return true;
            }
            return false;
        }
    } // namespace detail

    // A quest's status and result by its story id, its alias (quest_status(L"Quest.Main.1") -> L"OngoingQuest"), as the
    // game keeps them; empty for an id none of the manager's quests has (the game's own call would add it to the
    // save). (A quest object's own QuestStatus stays None while it's under way.)
    inline auto quest_status(std::wstring_view alias) -> std::wstring
    {
        if (!detail::known_alias(alias)) return {};
        auto r = detail::quest_call(STR("GetQuestStatus"), alias);
        return r ? r->get(L"ReturnValue").string() : std::wstring{};
    }
    inline auto quest_result(std::wstring_view alias) -> std::wstring
    {
        if (!detail::known_alias(alias)) return {};
        auto r = detail::quest_call(STR("GetQuestResult"), alias);
        return r ? r->get(L"ReturnValue").string() : std::wstring{};
    }

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
        out.alias = get(graph, L"QuestAlias.TagName").string();
        if (out.alias == L"None") out.alias.clear();
        out.type = get(q, L"questType").text;
        // The game keeps a quest's progress by its alias; the object's own fields are only right before and after.
        out.status = out.alias.empty() ? std::wstring{} : quest_status(out.alias);
        if (out.status.empty() || out.status == L"None") out.status = get(q, L"QuestStatus").text;
        out.result = out.alias.empty() ? std::wstring{} : quest_result(out.alias);
        if (out.result.empty()) out.result = get(q, L"QuestResult").text;
        out.tracked = get(q, L"bTracked").boolean();
        out.xp = get(q, L"ExperienceReward").number();
        return out;
    }

    // Every quest the manager holds (its Quests list holds {Quest, Line, Node} entries), each with its live status:
    // two calls to the quest manager a quest, so a few times a second at most, not every frame.
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

    inline auto quest_successes(std::wstring_view alias) -> std::optional<double>
    {
        if (!detail::known_alias(alias)) return std::nullopt;
        auto r = detail::quest_call(STR("GetCurrentSuccessCount"), alias);
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

    namespace detail
    {
        // The quest and objective ids your cat's save holds (QuestProgression/<chapter>/<id>), as of the last save: the
        // game's GetObjectiveStatus adds an id it's asked about, so it's only asked about these.
        inline auto saved_quest_ids() -> std::set<std::wstring>
        {
            std::set<std::wstring> ids;
            auto save = read_save();
            if (!save.data) return ids;
            const Json& chapters = slot_of(*save.data)["QuestProgression"];
            for (const Json& chapter : chapters.values())
                for (const std::string& id : chapter.keys()) ids.insert(wide(id));
            return ids;
        }
    } // namespace detail

    // A quest's objectives, in order. `status` is the game's for an objective your cat's save has (empty for the
    // rest: the game's call would add the id); it said NotStarted for a gather objective under way.
    inline auto objectives(UObject* quest) -> std::vector<Objective>
    {
        std::vector<Objective> out;
        if (!quest) return out;
        UObject* qm = quest_manager();
        const std::set<std::wstring> saved = detail::saved_quest_ids();
        for (UObject* o : find_all(STR("ObjectiveBase")))
        {
            if (get(o, L"QuestBase").object != quest) continue;
            Objective ob;
            ob.objective = o;
            if (auto r = call_reflected(o, STR("GetObjectiveIDString"))) ob.id = r->get(L"ReturnValue").string();
            ob.index = static_cast<int>(get(o, L"ObjectiveIdx").number());
            if (auto n = call<int32_t>(o, STR("GetCurrentNumber"))) ob.current = *n;
            if (auto n = call<int32_t>(o, STR("GetTargetNumber"))) ob.target = *n;
            if (!ob.id.empty() && saved.contains(ob.id))
            {
                auto r = call_reflected(qm, STR("GetObjectiveStatus"), [&](Params& p) { p.set_nth(0, Value::of(std::wstring_view(ob.id))); });
                if (r) ob.status = r->get(L"ReturnValue").string();
            }
            ob.point = get(o, L"ObjectivePoint").object;
            for (auto& [key, t] : map_entries(o, L"Targets"))   // a gather objective's targets (others have none)
            {
                QuestTarget qt;
                qt.tag = get(t, L"ActorsTag").string();
                qt.current = static_cast<int>(get(t, L"CurrentCount").number());
                qt.target = static_cast<int>(get(t, L"TargetCount").number());
                for (Value& w : elements(get(t, L"AllActors")))
                    if (w.object) qt.actors.push_back(w.object);
                ob.targets.push_back(std::move(qt));
            }
            out.push_back(ob);
        }
        std::sort(out.begin(), out.end(), [](const Objective& a, const Objective& b) { return a.index < b.index; });
        return out;
    }

    // The objective a quest is on: the one whose targets are out in the world (a gather objective's), else the first
    // the game says is in progress; nullptr when neither (the quest not started or done, or an objective without
    // targets: the game's GetObjectiveStatus read NotStarted for a live one, so a fight's or an escort's isn't found).
    inline auto current_objective(UObject* quest) -> UObject*
    {
        UObject* in_progress = nullptr;
        for (Objective& o : objectives(quest))
        {
            for (QuestTarget& t : o.targets)
                if (!t.actors.empty()) return o.objective;
            if (!in_progress && o.status == L"InProgress") in_progress = o.objective;
        }
        return in_progress;
    }
    // Finish an objective as the game does when its last target is in (SetObjectiveFinished): succeeded or failed.
    // The quest goes on to its next objective, or is complete (its status QuestComplete, its result Success), and
    // the game's own flow follows (the "Return to the Camp now?" question, the giver's turn-in).
    inline auto finish_objective(UObject* objective, bool succeeded = true) -> bool
    {
        if (!assert_game_thread(L"finish_objective") || !objective) return false;
        return call_reflected(objective, STR("SetObjectiveFinished"), [&](Params& p) {
                   p.set_nth(0, Value::of(std::wstring_view(succeeded ? L"Succeeded" : L"Failed")));
               }).has_value();
    }
    // Collect one of an objective's targets (a QuestTarget's actor) the way the player does: your cat is put on it,
    // the game's Interact is pressed a moment later, so the game's own pickup counts it (the HUD's "1/3", the quest's
    // events, and any other target in reach), and your cat is put back where it was. Calling the objective's handlers
    // instead doesn't count. False with no cat or target, or when a den entrance or another interactable is within 2 m
    // of it (Interact would use that instead); the count changes about a second later.
    inline auto collect_target(UObject* target) -> bool
    {
        if (!assert_game_thread(L"collect_target") || !player() || !target) return false;
        auto at = location(target);
        auto home = location(player());
        if (!at || !home) return false;
        for (Kind k : {Kind::Dens, Kind::Interactables, Kind::QuestGivers})
            for (const Nearby& n : nearby(k, 200, target))
                if (n.actor != target)
                {
                    log(L"collect_target: {} is in reach of it, so Interact could use that: not collected", n.name);
                    return false;
                }
        if (!teleport(player(), {at->x, at->y, at->z + 40})) return false;
        after(0.8, [] { command(L"Player_Interact"); });   // once the game has seen the cat in its reach
        after(1.6, [home] {
            if (player()) teleport(player(), *home);
        });
        return true;
    }

    // ============================================================================================ the story
    // The story scenes your cat has watched, by the save's names (L"ProphecyIntro", L"RankUpApprentice"), as of the last
    // save.
    inline auto scenes_seen() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        auto save = detail::read_save();   // the cached parse, not a copy of it
        if (!save.data) return out;
        const Json& seen = detail::slot_of(*save.data)["Sequences"];
        for (size_t i = 0; i < seen.keys().size(); ++i)
            if (seen.values()[i].boolean()) out.push_back(wide(seen.keys()[i]));
        return out;
    }
    // The scenes playing now (the sequencer manager's ActiveSequences), by tag.
    inline auto scenes_playing() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        if (!assert_game_thread(L"scenes_playing")) return out;
        for (auto& [tag, s] : map_entries(manager(STR("sequencer")), L"ActiveSequences"))
            out.push_back(get(tag, L"TagName").string());
        return out;
    }
    // A scene the game can play: its tag (Gameplay.Narrative.Prophecy.Intro.ShadowClan), its kind (ESwtEngineSequencerType:
    // 1 Intro, 2 Outro, 3 CutScene, 4 Podium, 5 Gameplay, 6 Combat, 7 Quest), its level sequence's name, and whether
    // it hides the HUD and the world's actors while it plays.
    struct Scene
    {
        std::wstring tag;
        int type{};
        std::wstring sequence;
        bool hides_hud{}, hides_actors{};
    };
    // Every scene the sequencer manager has: its RegisteredSequences, a table of rows (SwtEngineSequencersStruct)
    // for each kind.
    inline auto scenes() -> std::vector<Scene>
    {
        std::vector<Scene> out;
        if (!assert_game_thread(L"scenes")) return out;
        for (auto& [kind, table] : map_entries(manager(STR("sequencer")), L"RegisteredSequences"))
        {
            Table t(table.object);
            if (!t) continue;
            for (auto& [row_name, row] : t.rows())
            {
                Scene s;
                s.tag = get(row, L"sequenceId.TagName").string();
                s.type = static_cast<int>(kind.number());
                UObject* seq = get(row, L"LevelSequencer").object;
                s.sequence = seq ? name(seq) : std::wstring{};
                s.hides_hud = get(row, L"bHideGameplayHud").boolean();
                s.hides_actors = get(row, L"bHideGameplayActors").boolean();
                if (!s.tag.empty()) out.push_back(std::move(s));
            }
        }
        return out;
    }
    // How play_scene plays one: from `start` seconds in, at `rate`, held on its last frame at its end (`pause_at_end`, as
    // a talk's scene can be), and as the kind of scene it's registered as unless `type` says (scenes()).
    struct PlayScene
    {
        double rate = 1.0;
        double start = 0.0;
        bool pause_at_end = false;
        std::optional<int> type;
    };
    namespace detail
    {
        // The arguments the sequencer manager's PlaySequence takes (0x88 bytes; game.NATIVE says what each is).
        struct alignas(8) PlaySequenceArgs
        {
            uint8_t bytes[0x88]{};
        };
        inline auto play_sequence_args(const RC::Unreal::FName& tag, int type, const PlayScene& how) -> PlaySequenceArgs
        {
            PlaySequenceArgs a;
            a.bytes[0x00] = how.pause_at_end ? 1 : 0;
            const float rate = static_cast<float>(how.rate), start = static_cast<float>(how.start);
            std::memcpy(a.bytes + 0x18, &rate, 4);
            std::memcpy(a.bytes + 0x20, &start, 4);
            const uint32_t empty_map[4] = {0, 0x80, 0xFFFFFFFFu, 0};   // the actors to put in it: none
            std::memcpy(a.bytes + 0x50, empty_map, sizeof empty_map);
            const int32_t kind = type;
            std::memcpy(a.bytes + 0x7C, &kind, 4);
            std::memcpy(a.bytes + 0x80, &tag, 8);
            return a;
        }
    } // namespace detail

    // Play one of the game's scenes by its tag (scenes() lists them), through the sequencer manager's own PlaySequence
    // (signed): the camera, and the HUD and the world's actors hidden as the scene says, until it ends; scenes_playing()
    // has it meanwhile. A story scene (the prophecy intro, a rank-up) is only the film: what the game does around it
    // (marking it seen, the ceremony after) isn't run. False for a tag the game hasn't, outside the world, or without the
    // function on this build.
    //   wcmods::play_scene(L"Quest.Chapter00");   // the sandbox's establishing shot
    inline auto play_scene(std::wstring_view tag, const PlayScene& how = {}) -> bool
    {
        if (!assert_game_thread(L"play_scene") || !player()) return false;
        UObject* mgr = manager(STR("sequencer"));
        using Play = void* (*)(UObject*, const void*);
        auto play = native<Play>(L"SwtSequencerManager:PlaySequence");
        if (!mgr || !play) return false;
        int type = how.type.value_or(-1);
        if (type < 0)
            for (auto& s : scenes())
                if (s.tag == tag) type = s.type;
        if (type < 0) return false;
        RC::Unreal::FName name(std::wstring(tag), RC::Unreal::FNAME_Find);
        if (name == RC::Unreal::FName(STR("None"), RC::Unreal::FNAME_Find)) return false;
        auto args = detail::play_sequence_args(name, type, how);
        return play(mgr, args.bytes) != nullptr;
    }

    // Skip the scene playing, as holding the skip button does: the game's skip popup (WBP_GuiPopupSkip_C) given its
    // hold button's command, pressed and released 2.5 s later. False when the popup isn't up (a scene the game doesn't
    // let you skip, or none playing).
    inline auto skip_scene() -> bool
    {
        if (!assert_game_thread(L"skip_scene")) return false;
        Widget popup = ui::screen(L"GuiPopupSkip");
        if (!popup) return false;
        std::wstring command = get(popup.object(), L"mcGuiHoldButtonSkip.ButtonCommand").string();
        if (auto at = command.find(L"::"); at != std::wstring::npos) command = command.substr(at + 2);
        if (command.empty() || !ui::detail::screen_command(popup, command, 0, false)) return false;
        wcmods::detail::in_process_event([popup, command] { ui::detail::screen_command(popup, command, 0); });
        after(2.5, [popup, command] { wcmods::detail::in_process_event([popup, command] { ui::detail::screen_command(popup, command, 1); }); });
        return true;
    }

    // A value of your cat's progression in the save, by its path under the slot's GameplayProgression
    // (L"Chapter00/L_WorldMap_01_P", L"FreshKill/Cycle"), as of the last save; null when it isn't there.
    inline auto progression(std::wstring_view path) -> Json
    {
        auto save = detail::read_save();
        if (!save.data) return Json();
        const Json* at = &detail::slot_of(*save.data)["GameplayProgression"];
        size_t start = 0;
        while (start <= path.size())
        {
            size_t end = path.find(L'/', start);
            std::wstring_view part = path.substr(start, end == std::wstring_view::npos ? std::wstring_view::npos : end - start);
            if (!part.empty()) at = &(*at)[utf8(part)];
            if (end == std::wstring_view::npos) break;
            start = end + 1;
        }
        return *at;
    }
    // A mood value the game keeps (the save manager's MoodData: a whole number under a primary and a sub key), or
    // nullopt when it hasn't got one. It asks HasMoodData first: the game's GetMoodData writes a missing key into
    // the save as 0, as its other progression reads do.
    inline auto mood(std::wstring_view primary, std::wstring_view sub) -> std::optional<int>
    {
        if (!assert_game_thread(L"mood")) return std::nullopt;
        UObject* sm = save_manager();
        auto keys = [&](Params& p) {
            p.set_nth(0, Value::of(primary));
            p.set_nth(1, Value::of(sub));
        };
        auto has = call_reflected(sm, STR("HasMoodData"), keys);
        if (!has || !has->get(L"ReturnValue").boolean()) return std::nullopt;
        auto r = call_reflected(sm, STR("GetMoodData"), keys);
        return r ? std::optional<int>(static_cast<int>(r->get(L"ReturnValue").number())) : std::nullopt;
    }
    inline auto set_mood(std::wstring_view primary, std::wstring_view sub, int value) -> bool
    {
        if (!assert_game_thread(L"set_mood")) return false;
        return call_reflected(save_manager(), STR("SetMoodData"), [&](Params& p) {
                   p.set_nth(0, Value::of(primary));
                   p.set_nth(1, Value::of(sub));
                   p.set_nth(2, Value::of(value));
               }).has_value();
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

    // The roaming animals within `radius` cm of your cat that a fight can start with (BP_Exploration_Character_Base,
    // not a scene's copy), nearest first.
    inline auto fight_animals(double radius = 5000) -> std::vector<UObject*>
    {
        std::vector<UObject*> out;
        if (!assert_game_thread(L"fight_animals")) return out;
        for (const Nearby& n : nearby(Kind::Creatures, radius))
        {
            std::wstring full = full_name(n.actor);
            if (full.find(L"MovieScene") == std::wstring::npos && full.find(L"Default__") == std::wstring::npos) out.push_back(n.actor);
        }
        return out;
    }
    // Start a fight with a roaming animal the player's way: your cat is put 1.5 m behind it, facing it, and the game's
    // pounce is pressed a moment later; the game's own fight follows (combat_active(), the fight menu, CombatStart).
    // False outside the world or for no animal; the fight starts about a second later.
    inline auto start_fight(UObject* animal) -> bool
    {
        if (!assert_game_thread(L"start_fight") || !player() || !animal || combat_active()) return false;
        auto at = location(animal);
        auto fwd = call_reflected(animal, STR("GetActorForwardVector"));
        if (!at || !fwd) return false;
        const double fx = get(fwd->get(L"ReturnValue"), L"X").number(), fy = get(fwd->get(L"ReturnValue"), L"Y").number();
        if (!teleport(player(), {at->x - fx * 150, at->y - fy * 150, at->z + 30})) return false;
        const double yaw = std::atan2(fy, fx) * 180.0 / 3.14159265358979323846;
        call_reflected(player(), STR("K2_SetActorRotation"), [&](Params& p) {
            set(p.nth(0), L"Yaw", yaw);
            p.set_nth(1, Value::of(false));
        });
        if (UObject* c = controller()) call_reflected(c, STR("SetControlRotation"), [&](Params& p) { set(p.nth(0), L"Yaw", yaw); });
        after(0.6, [] {   // still in the world and not in a fight by then
            if (player() && !combat_active()) command(L"Player_Pounce");
        });
        return true;
    }

    namespace detail
    {
        inline auto fight_menu_screen() -> Widget { return ui::screen(L"WBP_GuiPopupCombat_C"); }
        // Where a button is on one of the fight menu's panels (L"PanelCombatMenu": Attack, Rest, Item, Flee;
        // L"PanelCombatAttacks": the moves), in the panel's own order (its NavControls' ControlsNavigation), and
        // where the selection is (ControlSelected). A target of -1 when the menu, the panel or the button isn't there.
        struct FightSpot
        {
            int target = -1, selected = 0;
        };
        inline auto fight_spot(const wchar_t* panel_name, std::wstring_view button) -> FightSpot
        {
            FightSpot s;
            Widget menu = fight_menu_screen();
            UObject* panel = menu ? get(menu.object(), panel_name).object : nullptr;
            if (!panel) return s;
            UObject* selected = get(panel, L"ControlSelected").object;
            int i = 0;
            for (Value& c : elements(get(panel, L"NavControls").object, L"ControlsNavigation"))
            {
                if (!c.object) continue;
                if (wcmods::name(c.object) == button) s.target = i;
                if (c.object == selected) s.selected = i;
                ++i;
            }
            return s;
        }
        // One step of a pick, 0.3 s after the last (presses in one frame don't move the selection): the selection
        // read again, Up or Down toward the button (the panels aren't relied on to wrap round), or Confirm and then
        // `then` once it's there. Read each time, as a screen can let a command go by (more so with the game's window
        // behind). Given up after `tries` steps, or when the menu or the button has gone.
        inline auto fight_step(const wchar_t* panel_name, std::wstring button, std::function<void()> then, int tries) -> void
        {
            after(0.3, [panel_name, button, then, tries] {
                const FightSpot s = fight_spot(panel_name, button);
                if (s.target < 0 || tries <= 0) return;
                if (s.target != s.selected)
                {
                    ui::send(fight_menu_screen(), s.target < s.selected ? L"Button_Up" : L"Button_Down");
                    return fight_step(panel_name, button, then, tries - 1);
                }
                ui::send(fight_menu_screen(), L"Button_Confirm");
                if (then) then();
            });
        }
        // Pick a button on one of the fight menu's panels as its own keys do: the selection moved to it a press at a
        // time, then Confirm, then `then` (fight_step). False when the menu or the button isn't there.
        inline auto fight_pick(const wchar_t* panel_name, std::wstring_view button, std::function<void()> then = {}) -> bool
        {
            const FightSpot s = fight_spot(panel_name, button);
            if (s.target < 0) return false;
            const int distance = s.target > s.selected ? s.target - s.selected : s.selected - s.target;
            fight_step(panel_name, std::wstring(button), std::move(then), distance + 4);
            return true;
        }
    } // namespace detail

    // Your cat's fighter in the fight now: the player's side's one the AI doesn't play (its tier 0); its actor() is
    // your cat. Empty outside a fight. (player() is nullptr during one: the controller holds the fight's own pawn.)
    inline auto fight_cat() -> Fighter
    {
        for (Fighter& f : fight_players())
            if (f.ai_tier() && *f.ai_tier() == 0) return f;
        return {};
    }
    namespace detail
    {
        // How many moves your cat has in this fight (its fighter's moves), or -1 when that can't be read.
        inline auto fight_move_count() -> int
        {
            Fighter me = fight_cat();
            if (!me || !me.move_count()) return -1;
            return static_cast<int>(me.moves().size());
        }
    } // namespace detail

    // The fight menu (WBP_GuiPopupCombat_C), shown on your cat's turn; an empty Widget when it isn't up.
    inline auto fight_menu() -> Widget { return detail::fight_menu_screen(); }
    // Your cat's turn, through the fight menu as its own keys pick: an attack (move 0 to 3, as the attack panel lists
    // them; its target confirmed), a rest, or fleeing (the fight ends: CombatEnd). False when the menu isn't up (not
    // your cat's turn) or hasn't got it, or for a move your cat hasn't got (a young cat has fewer than four); the
    // turn plays out over the next seconds.
    inline auto fight_attack(int move = 0) -> bool
    {
        if (!assert_game_thread(L"fight_attack") || move < 0 || move > 3) return false;
        const int moves = detail::fight_move_count();
        if (moves >= 0 && move >= moves) return false;
        return detail::fight_pick(L"PanelCombatMenu", L"mcGuiButtonAttack", [move] {
            after(0.6, [move] {   // the moves' panel, once it's open
                detail::fight_pick(L"PanelCombatAttacks", L"mcGuiButtonAttack" + std::to_wstring(move + 1), [] {
                    after(0.6, [] { ui::send(detail::fight_menu_screen(), L"Button_Confirm"); });   // the target, when it asks
                });
            });
        });
    }
    inline auto fight_rest() -> bool { return assert_game_thread(L"fight_rest") && detail::fight_pick(L"PanelCombatMenu", L"mcGuiButtonRest"); }
    inline auto flee() -> bool { return assert_game_thread(L"flee") && detail::fight_pick(L"PanelCombatMenu", L"mcGuiButtonFlee"); }
    // End the fight the game's own way: the losing side's health set to 0 and your cat's turn taken (an attack), so the
    // game sees the side fall and finishes the fight as it does: a win with its rewards, or a loss (your cat back at
    // its respawn spot, healed). False outside a fight or when it isn't your cat's turn (the menu isn't up): call it
    // again then. The game's EndCombat leaves the cat without a body: not used.
    inline auto end_fight(bool won) -> bool
    {
        if (!assert_game_thread(L"end_fight") || !combat_active()) return false;
        // The attack has to be there before anyone's health is touched.
        if (detail::fight_spot(L"PanelCombatMenu", L"mcGuiButtonAttack").target < 0 || detail::fight_move_count() == 0) return false;
        for (Fighter& f : won ? fight_enemies() : fight_players())
        {
            Resource hp = resource(f.actor(), STR("SwtQuestHealthComponent"));
            if (hp) *hp.value = 0;
        }
        return fight_attack(0);
    }
    // A dilemma the fight is asking now (its popup, WBP_GuiPopupDilemma_C): its title, question, the bonus it shows,
    // and the two choices' words. The game picks them from CombatDilemmas.csv at a fight's start, while choosing a
    // move, on an attack, or at its end, by chance (0.15, 1 at a boss's end) and the fighters' state; a solo fight's
    // win can ask Dilemma13 or 14. (The cheats manager's ForcedDilemma made no dilemma come in the release build.)
    struct Dilemma
    {
        std::wstring title, question, bonus, option1, option2;
    };
    namespace detail
    {
        // A game button's words as shown (its text block; its own Text property holds a placeholder, "TXT").
        inline auto button_words(UObject* button) -> std::wstring
        {
            Widget b(button);
            std::wstring words = b.find(L"mcGuiTextNormal").text();
            return words.empty() ? b.find(L"mcGuiTextSelected").text() : words;
        }
        // Whether a game button (a GuiButtonState: the fight menu's, a dilemma's choices) shows as selected: its
        // CanvasSelected is shown. False for no button.
        inline auto button_selected(UObject* button) -> bool
        {
            UObject* c = button ? get(button, L"CanvasSelected").object : nullptr;
            if (!c) return false;
            const Visibility v = Widget(c).visibility();
            return v != Visibility::Collapsed && v != Visibility::Hidden;
        }
        // Which of a dilemma popup's choices shows as selected (0, 1), or -1 when neither does.
        inline auto dilemma_selected(UObject* popup) -> int
        {
            if (button_selected(get(popup, L"mcGuiOption1").object)) return 0;
            if (button_selected(get(popup, L"mcGuiOption2").object)) return 1;
            return -1;
        }
        // One step of answering, `wait` s after the last, while the same popup is up: toward the choice (Right, Left)
        // or Confirm once the selection is on it, as a screen can let a command go by. `assumed` is where the
        // selection is taken to be when neither choice reads as selected (the first, at the start).
        inline auto answer_step(UObject* popup, int option, int assumed, int tries, double wait) -> void
        {
            after(wait, [popup, option, assumed, tries] {
                Widget now = ui::screen(L"WBP_GuiPopupDilemma_C");
                if (!now || now.object() != popup || tries <= 0) return;
                int at = dilemma_selected(popup);
                if (at < 0) at = assumed;
                if (at != option)
                {
                    ui::send(now, option == 1 ? L"Button_Right" : L"Button_Left");
                    return answer_step(popup, option, option, tries - 1, 0.4);
                }
                ui::send(now, L"Button_Confirm");
                answer_step(popup, option, option, tries - 1, 1.5);   // still up then: the Confirm went by
            });
        }
    } // namespace detail
    inline auto dilemma() -> std::optional<Dilemma>
    {
        if (!assert_game_thread(L"dilemma")) return std::nullopt;
        Widget popup = ui::screen(L"WBP_GuiPopupDilemma_C");
        if (!popup) return std::nullopt;
        UObject* p = popup.object();
        Dilemma d;
        d.title = get(p, L"mcGuiTextTitle.Text").string();
        d.question = get(p, L"mcGuiTextQuestion.Text").string();
        d.bonus = get(p, L"mcGuiTextBonus.Text").string();
        d.option1 = detail::button_words(get(p, L"mcGuiOption1").object);
        d.option2 = detail::button_words(get(p, L"mcGuiOption2").object);
        return d;
    }
    // Answer the dilemma asking now, as its own keys do: the first choice (0) or the second (1), the selection moved
    // over to it (Right, Left) and then Confirm, a step at a time, each looking at which choice shows as selected,
    // until the popup goes; the fight then ends as the game does. False when none is asking. (The game's
    // OnDilemmaCompleted hook didn't fire for an answer at a fight's end, so there's no event for it.)
    inline auto answer_dilemma(int option) -> bool
    {
        if (!assert_game_thread(L"answer_dilemma") || option < 0 || option > 1) return false;
        Widget popup = ui::screen(L"WBP_GuiPopupDilemma_C");
        if (!popup) return false;
        detail::answer_step(popup.object(), option, 0, 8, 0.3);
        return true;
    }

    // Give a fighter (its actor) a status condition (ESwtAdventureStatusType: L"Poisoned", L"Blinded", L"Furious",
    // L"Stressed") through its status component's own ApplyStatusType: the game's Status event fires. False for no
    // fighter or status component, or a name the enum hasn't got.
    inline auto apply_status(UObject* actor, std::wstring_view status) -> bool
    {
        if (!assert_game_thread(L"apply_status") || !actor) return false;
        UObject* sc = component(actor, STR("SwtAdventureStatusComponent"));
        if (!sc || !enum_value(STR("/Script/SwtAdventure.ESwtAdventureStatusType"), status)) return false;
        bool named = false;
        auto r = call_reflected(sc, STR("ApplyStatusType"), [&](Params& p) { named = p.set_nth(0, Value::of(status)); });
        return r.has_value() && named;
    }

    // ============================================================================================ events
    // The game's events as one list, each with what it carries in an EventInfo:
    //   Level         name: the level loaded
    //   Player        object: your cat, or nullptr when it went
    //   Phase         name: the game's phase now ("Game", "PreGame"...), a: the one before
    //   CombatStart   object: the combat director;  CombatEnd: nothing
    //   GenericEvent  name: the event's name (the game's own SwtGameUtil broadcasts)
    //   QuestStatus   object: the quest, a: its status (an enum), b: whether exact
    //   Damage        a: the damage struct (Character, Damage...; its bytes last the callback): set(e.a, L"Damage", n)
    //                 changes the hit before the game applies it (seen: 22 made 220)
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
