// Quests and the story (Story.hpp), on request ("questline"), for tests/game/test_cpp_sdk.py, which backs the save up first
// and puts it back after (this moves the test cat's story on). The gather quest (Quest.Main.1) started by its tag, its
// status read by its alias; its objective's targets; one collected the player's way (the HUD's count); the objective
// finished, the quest complete; the quest events counted; the scenes seen and playing; mood read without adding a key;
// a progression value.
#include "checks.hpp"

#include <memory>
#include <string>

namespace t
{
    namespace
    {
        constexpr const wchar_t* GATHER = L"Quest.Procedural.Survival.Gather";
        constexpr const wchar_t* ALIAS = L"Quest.Main.1";
        int status_events = 0;
        bool hooked = false;

        auto gather_quest() -> UObject*
        {
            for (Quest& q : quests())
                if (q.alias == ALIAS) return q.quest;
            return nullptr;
        }
        auto hud_goal() -> Json
        {
            Widget hud = ui::hud().find(L"mcGuiQuestObjective");
            Widget goal = hud ? hud.find(L"mcGuiGoal1") : Widget{};
            return goal ? Json(text(goal.find(L"mcGuiGoalName").text() + L" " + goal.find(L"mcGuiGoalValues").text())) : Json();
        }
        auto targets_json(UObject* objective) -> Json
        {
            Json out = Json::array();
            for (Objective& o : objectives(gather_quest()))
                if (o.objective == objective)
                    for (QuestTarget& t : o.targets)
                    {
                        Json x = Json::object();
                        x.set("tag", Json(text(t.tag)));
                        x.set("current", Json(t.current));
                        x.set("target", Json(t.target));
                        x.set("actors", Json(static_cast<int>(t.actors.size())));
                        out.push(x);
                    }
            return out;
        }
    } // namespace

    auto run_quests_request() -> void
    {
        phase("questline");
        if (!hooked)
        {
            on(Event::QuestStatus, [](const EventInfo&) { status_events++; });
            hooked = true;
        }
        status_events = 0;
        // ----- the quests, each by its story id
        Json listed = Json::array();
        for (Quest& q : quests())
            if (!q.alias.empty()) listed.push(Json(text(q.alias + L" " + q.tag + L" " + q.status)));
        value("questline.listed", listed);
        Quest before = describe_quest(gather_quest());
        value("questline.before", text(before.status));
        value("questline.alias_status", text(quest_status(ALIAS)));
        value("questline.nosuch_status", text(quest_status(L"Quest.WCModsTest.NoSuch")));   // saved below: not added?
        // ----- the scenes, mood, progression
        Json seen = Json::array();
        for (auto& s : scenes_seen()) seen.push(Json(text(s)));
        value("questline.scenes_seen", seen);
        value("questline.scenes_playing", static_cast<int>(scenes_playing().size()));
        auto m = mood(L"WCModsTest", L"NoSuchMood");
        auto has = call_reflected(save_manager(), STR("HasMoodData"), [&](Params& p) {
            p.set_nth(0, Value::of(std::wstring_view(L"WCModsTest")));
            p.set_nth(1, Value::of(std::wstring_view(L"NoSuchMood")));
        });
        expect("questline.mood_missing", !m && has && !has->get(L"ReturnValue").boolean());   // asked, and still not there
        expect("questline.mood_set", set_mood(L"WCModsTest", L"Set", 7) && mood(L"WCModsTest", L"Set") == 7);   // the save is put back after
        value("questline.progression", progression(L"FreshKill/Cycle"));
        expect("questline.progression_missing", progression(L"NoSuch/Path").is_null());

        // ----- started by its tag, as a quest giver does
        if (before.status != L"OngoingQuest") start_quest(GATHER);
        after(2.0, [] {
            UObject* q = gather_quest();
            Quest now = describe_quest(q);
            value("questline.started", text(now.status));
            value("questline.hud_before", hud_goal());
            UObject* o = current_objective(q);
            value("questline.objective", o ? Json(text(full_name(o))) : Json());
            value("questline.targets_before", targets_json(o));
            // ----- one target collected the player's way: the first with nothing else in Interact's reach (the
            // forest's gatherables grow back over the game's days, and one can stand by a target: collect_target
            // refuses that one)
            auto home = location(player());
            bool collected = false;
            int tried = 0;
            for (Objective& ob : objectives(q))
                if (ob.objective == o)
                    for (QuestTarget& t : ob.targets)
                        for (UObject* a : t.actors)
                            if (!collected)
                            {
                                ++tried;
                                collected = collect_target(a);
                            }
            value("questline.collect_tried", tried);
            expect("questline.collect", collected);
            expect("questline.collect_refused", !collect_target(nullptr));
            after(3.0, [o, home] {
                value("questline.hud_after_collect", hud_goal());
                value("questline.targets_after", targets_json(o));
                value("questline.events_after_collect", status_events);
                if (home) teleport(player(), *home);
                // ----- the objective finished: the quest is complete
                expect("questline.finish", finish_objective(o) && !finish_objective(nullptr));
                after(2.0, [] {
                    save_game(L"WCMods quest test");   // the save is put back after the test
                    Quest done_q = describe_quest(gather_quest());
                    value("questline.finished", text(done_q.status));
                    value("questline.finished_result", text(done_q.result));
                    value("questline.events", status_events);
                    std::wstring all;
                    for (auto& s : screens()) all += s + L" ";
                    value("questline.screens", text(all));
                    after(2.0, [] {
                        value("questline.saved_quests", slot_data()["QuestProgression"]);
                        done("questline");
                    });
                });
            });
        });
    }

    // The scenes the game has; one played (the sandbox's establishing shot, which isn't a story scene) and skipped.
    namespace
    {
        // The running scene's player (the sequencer manager's ActiveSequences' SequencePlayer), and its time
        // (UMovieSceneSequencePlayer's FQualifiedFrameTime: the frame, its fraction, then the frame rate).
        auto scene_player() -> UObject*
        {
            for (auto& [tag, s] : map_entries(manager(STR("sequencer")), L"ActiveSequences"))
                if (UObject* p = get(s, L"SequencePlayer").object) return p;
            return nullptr;
        }
        struct QualifiedTime
        {
            int32_t frame;
            float sub;
            int32_t num, den;
        };
        auto scene_seconds(const TCHAR* function) -> Json
        {
            auto t = call<QualifiedTime>(scene_player(), function);
            if (!t || t->num == 0) return Json();
            return Json((t->frame + t->sub) * t->den / static_cast<double>(t->num));
        }
        auto scene_state(const std::string& prefix) -> void
        {
            Json now = Json::array();
            for (auto& t : scenes_playing()) now.push(Json(utf8(t)));
            value(prefix + ".playing", now);
            value(prefix + ".skip_popup", static_cast<bool>(ui::screen(L"GuiPopupSkip")));
            UObject* p = scene_player();
            auto rate = call<float>(p, STR("GetPlayRate"));
            value(prefix + ".rate", rate ? Json(static_cast<double>(*rate)) : Json());
            value(prefix + ".time", scene_seconds(STR("GetCurrentTime")));
            value(prefix + ".duration", scene_seconds(STR("GetDuration")));
            Widget hud = ui::screen(L"WBP_GuiHudGameWrc_C");
            value(prefix + ".hud", static_cast<bool>(hud));
        }
        auto scene_after(const std::string& prefix) -> void
        {
            value(prefix + ".playing_after", static_cast<int>(scenes_playing().size()));
            value(prefix + ".skip_popup_after", static_cast<bool>(ui::screen(L"GuiPopupSkip")));
            value(prefix + ".player_after", player() != nullptr);
            Widget hud = ui::screen(L"WBP_GuiHudGameWrc_C");
            value(prefix + ".hud_after", static_cast<bool>(hud));
        }
    } // namespace

    auto run_scenes_request() -> void
    {
        phase("scenes");
        Json all = Json::array();
        for (auto& sc : scenes())
        {
            Json o = Json::object();
            o.set("tag", Json(utf8(sc.tag)));
            o.set("type", Json(sc.type));
            o.set("sequence", Json(utf8(sc.sequence)));
            o.set("hud", Json(sc.hides_hud));
            all.push(o);
        }
        value("scenes.all", all);
        value("scenes.playing_before", static_cast<int>(scenes_playing().size()));
        expect("scenes.refused", !play_scene(L"Gameplay.WCModsTest.NoSuchScene") && !skip_scene() &&
                                     !play_scene(L"Quest.Chapter00", {.rate = 0.0}) &&
                                     !play_scene(L"Quest.Chapter00", {.length = -1.0}));
        // Its 10 s made to last 5 (whatever the rate); a second scene refused while it plays.
        expect("scenes.play", play_scene(L"Quest.Chapter00", {.rate = 4.0, .length = 5.0}));
        expect("scenes.refused_second", !play_scene(L"Quest.Chapter00"));
        after(1.0, [] {
            scene_state("scenes");
            expect("scenes.skip", skip_scene());
            after(5.0, [] {
                scene_after("scenes");
                // At four times the speed (its end 2.5 s in), held there: 4 s in, no longer playing but the skip popup
                // up (seen: the last frame on screen, "Hold skip"), another refused; then skipped.
                expect("scenes.play_held", play_scene(L"Quest.Chapter00", {.rate = 4.0, .pause_at_end = true}));
                after(1.0, [] { scene_state("scenes.fast"); });
                after(4.0, [] {
                    scene_state("scenes.held");
                    expect("scenes.held.refused", !play_scene(L"Quest.Chapter00"));
                    expect("scenes.held.skip", skip_scene());
                    after(5.0, [] {
                        scene_after("scenes.held");
                        done("scenes");
                    });
                });
            });
        });
    }

} // namespace t
