// World.hpp and Story.hpp: what's nearby, the game's screens and input, traces, the save, items, names,
// quests, fights and the game's events, with values for the Python side to compare with Lua.
#include "checks.hpp"

#include <atomic>
#include <string>

namespace t
{
    namespace
    {
        std::atomic<int> level_events{}, player_events{}, phase_events{}, combat_events{};
        std::string first_phase;
    }

    auto run_world_more(UObject* actor) -> void
    {
        // ----- what's around
        auto pickups = nearby(Kind::Pickups, 5000);
        value("nearby.pickups", static_cast<double>(pickups.size()));
        bool sorted = true, has = true;
        for (size_t i = 0; i < pickups.size(); ++i)
        {
            if (i && pickups[i].distance < pickups[i - 1].distance) sorted = false;
            if (!pickups[i].actor || pickups[i].name.empty() || pickups[i].type.empty() || pickups[i].distance > 5000) has = false;
        }
        expect("nearby.sorted", sorted && has);
        value("nearby.cats", static_cast<double>(nearby(Kind::Cats, 20000).size()));
        value("nearby.first_pickup", pickups.empty() ? Json() : Json(text(pickups[0].name)));
        expect("nearby.from", nearby(Kind::Pickups, 5000, actor).size() == pickups.size() && nearby(Kind::Pickups, 0).empty());
        auto shown = screens();
        Json list = Json::array();
        for (auto& s : shown) list.push(text(s));
        value("screens", list);

        // ----- the game's input: nothing is pressed while a test runs
        expect("pressed", !pressed(L"T") && !key_down(L"T") && !pressed(L"Gamepad_FaceButton_Top"));

        // ----- traces
        auto at = location(actor);
        expect("location_for_trace", at.has_value());
        if (at)
        {
            auto g = ground(at->x, at->y, at->z);
            expect("ground", g.has_value() && std::abs(*g - at->z) < 300, g ? std::to_string(*g) : "(none)");
            value("ground", g ? Json(*g) : Json());
            auto hit = trace({at->x, at->y, at->z + 100}, {at->x, at->y, at->z - 1000});
            expect("trace", hit.has_value() && std::abs(hit->x - at->x) < 1);
            expect("trace.nothing", !trace({at->x, at->y, at->z + 5000}, {at->x, at->y, at->z + 9000}));
        }

        // ----- the save
        expect("save_manager", save_manager() != nullptr);
        value("save.slot", save_slot());
        Json inventory = save_state(L"Inventory");
        value("save.inventory_keys", static_cast<double>(inventory.is_object() ? inventory.size() : -1));
        Json missing = save_state(L"NoSuchState");
        expect("save_state.missing", missing.is_null() || missing.size() == 0, missing.dump(0));
        expect("set_save_state", inventory.is_object() ? set_save_state(L"Inventory", inventory) : true);
        auto level = save_progression(L"GameplayProgression", L"Level");
        value("save.progression", level ? Json(*level) : Json());
        auto minimap = save_setting(L"SettingsData", L"Minimap");
        value("save.setting", minimap ? Json(*minimap) : Json());
        Json file = save_file();
        expect("save_file", file.is_object() && file.size() > 0);
        Json slot = slot_data();
        expect("slot_data", slot.is_object() && slot["GameplayProgression"].is_object(), slot.is_object() ? "object" : "none");
        expect("save_path", save_path().filename() == L"WrcGame.json");

        // ----- items
        Json mine = items();
        expect("items", mine.is_object());
        value("items.count", static_cast<double>(mine.size()));
        if (mine.size() > 0)
        {
            const std::string& tag = mine.keys()[0];
            value("items.first_tag", tag);
            value("items.first_count", item_count(tag));
            value("items.first_type", text(item_type(wide(tag))));
            value("items.first_name", text(item_name(tag)));
        }
        expect("item_count.missing", item_count("Gameplay.Inventory.NoSuchThing") == 0);

        // ----- names, clans, traits
        value("cat.name", text(cat_name(actor)));
        value("cat.clan", text(cat_clan(actor)));
        Json traits = Json::array();
        for (auto& tr : cat_traits()) traits.push(text(tr));
        value("cat.traits", traits);
        expect("cat_name.null", cat_name(nullptr).empty() && cat_clan(nullptr).empty());
        value("item_name.marigold", text(item_name("Gameplay.Inventory.Consumable.MediumHealingHerb")));

        // ----- quests
        auto all = quests();
        value("quests.count", static_cast<double>(all.size()));
        if (!all.empty())
        {
            const Quest& q = all[0];
            value("quests.first.id", text(q.id));
            value("quests.first.tag", text(q.tag));
            value("quests.first.status", text(q.status));
            value("quests.first.type", text(q.type));
            value("quests.first.tracked", q.tracked);
            expect("describe_quest", q.quest != nullptr && !q.graph.empty() && !q.status.empty());
            if (!q.tag.empty())
            {
                value("quests.first.status_by_tag", text(quest_status(q.tag)));
                value("quests.first.result_by_tag", text(quest_result(q.tag)));
                auto n = quest_successes(q.tag);
                value("quests.first.successes", n ? Json(*n) : Json());
            }
            auto obs = objectives(q.quest);
            value("quests.first.objectives", static_cast<double>(obs.size()));
            bool ordered = true;
            for (size_t i = 1; i < obs.size(); ++i) ordered = ordered && obs[i - 1].index <= obs[i].index;
            expect("objectives.ordered", ordered && objectives(nullptr).empty());
        }
        UObject* tracked = tracked_quest();
        value("quests.tracked", tracked ? Json(text(describe_quest(tracked).id)) : Json());
        expect("quest_manager", quest_manager() != nullptr);
        expect("track_quest", (tracked ? track_quest(tracked, true) : true) && !track_quest(nullptr));
        value("quests.chapter", text(chapter()));
        value("quests.nosuch_status", text(quest_status(L"Quest.NoSuchQuestAnywhere")));   // the game answers for any tag
        // Starting and handing out take a tag the game hasn't got: the calls go through, and nothing happens.
        expect("start_quest", start_quest(L"Quest.NoSuchQuestAnywhere") && give_quest(L"Quest.NoSuchQuestAnywhere"));

        // ----- calling by reflection, on its own
        double dilation = get(actor, L"CustomTimeDilation").number();   // run_reflect changed it; the game's time dilation is 1
        auto r = call_reflected(actor, STR("GetActorTimeDilation"));
        expect("call_reflected", r && r->function() != nullptr && r->bytes() != nullptr && r->count() == 1
                                     && std::abs(r->nth(0).number() - dilation) < 0.001 && std::abs(r->get(L"ReturnValue").number() - dilation) < 0.001
                                     && r->has(L"ReturnValue") && !r->has(L"Nope") && !r->nth(5) && !call_reflected(actor, STR("NoSuchFunction"))
                                     && !call_reflected(nullptr, STR("X")),
               r ? std::to_string(r->get(L"ReturnValue").number()) + " vs " + std::to_string(dilation) : "(none)");
        // A struct's bytes out (raw), and an output parameter set by position (set_nth) before the call.
        auto where = call_reflected(actor, STR("K2_GetActorLocation"));
        expect("call_reflected.raw", where && where->raw(L"ReturnValue") != nullptr && at
                                         && std::abs(to_vec3(*static_cast<FVector*>(where->raw(L"ReturnValue"))).x - at->x) < 1);
        auto clock_call = call_reflected(game_state(), STR("GetDayClockTime"), [](Params& p) { p.set_nth(0, Value::of(0)); });
        expect("call_reflected.set_nth", clock_call && clock_call->count() == 3 && clock_call->nth(0).kind == Value::Kind::Int);

        // ----- fights (none while a test runs)
        expect("combat_inactive", !combat_active() && combat_director() == nullptr && fight_players().empty() && fight_enemies().empty()
                                      && fight_turn_order().empty() && fight_current() == nullptr && fight_main_enemy() == nullptr);
        Fighter me = fighter(actor);
        expect("fighter", static_cast<bool>(me) && me.component != actor && !fighter(nullptr) && me.actor() == actor
                              && fighter(me.component).component == me.component);
        expect("fighter.members", me.level() != nullptr && me.stance() != nullptr && me.stat(Stat::Strength) != nullptr);
        expect("fighter.move", me.move().kind == Value::Kind::Struct || me.move().kind == Value::Kind::None);
        value("fighter.targets", static_cast<double>(me.targets().size()));
    }

    auto setup_story() -> void
    {
        expect("on.level", on(Event::Level, [](const EventInfo& e) {
            if (e.event == Event::Level && !e.name.empty()) level_events++;
        }));
        expect("on.player", on(Event::Player, [](const EventInfo& e) {
            if (e.event == Event::Player) player_events++;
        }));
        expect("on.phase", on(Event::Phase, [](const EventInfo& e) {
            phase_events++;
            if (first_phase.empty()) first_phase = text(e.name);
        }));
        expect("on.combat", on(Event::CombatStart, [](const EventInfo&) { combat_events++; }) && on(Event::CombatEnd, [](const EventInfo&) { combat_events++; }));
        expect("on.generic_event", on(Event::GenericEvent, [](const EventInfo&) {}));
        expect("on.quest_status", on(Event::QuestStatus, [](const EventInfo&) {}));
        expect("on.damage", on(Event::Damage, [](const EventInfo&) {}));
        expect("on.turn_ended", on(Event::TurnEnded, [](const EventInfo&) {}));
        expect("on.status", on(Event::Status, [](const EventInfo&) {}));
        expect("on.again", on(Event::Level, [](const EventInfo&) {}));   // a second listener on a started event
        report_quest("cpp-sdk-test", {.title = L"The C++ test quest", .status = L"active", .objective = L"Pass every check", .progress = L"1 / 2"});
    }

    auto snapshot_story() -> void
    {
        // Counted now, for a Lua count taken right after: pickups come and go.
        value("nearby.pickups.now", static_cast<double>(nearby(Kind::Pickups, 5000).size()));
        value("events.level", level_events.load());
        value("events.player", player_events.load());
        value("events.phase", phase_events.load());
        value("events.first_phase", first_phase);
        value("events.combat", combat_events.load());
    }
} // namespace t
