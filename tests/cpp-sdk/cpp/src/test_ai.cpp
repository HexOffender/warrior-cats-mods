// Ai.hpp: the game's AI, on request ("ai"), for tests/game/test_cpp_sdk.py (docs/plans/cpp-sdk-ai.md, step 1). The
// game's trees read as data; an animal's and a walking cat's AI, their keys written and read back, a walking cat
// stopped and set walking again by its own key, an animal sent into its tree's chase branch and back, an animal's
// logic stopped through the game's sleep and wake (your cat away and back) and started again.
#include "checks.hpp"

#include <cmath>
#include <memory>
#include <string>

namespace t
{
    namespace
    {
        auto distance(Vec3 a, Vec3 b) -> double { return std::sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y) + (a.z - b.z) * (a.z - b.z)); }
        auto state(UObject* actor) -> Json
        {
            Json o = Json::object();
            o.set("running", Json(ai_running(actor)));
            o.set("asleep", Json(ai_asleep(actor)));
            o.set("tree", Json(text(name(ai_tree(actor)))));
            AiTask t = ai_task(actor);
            o.set("task", Json(text(t.name)));
            o.set("task_kind", Json(text(t.kind)));
            auto at = location(actor);
            o.set("x", at ? Json(at->x) : Json());
            o.set("y", at ? Json(at->y) : Json());
            return o;
        }
        // A clan cat walking its path, nearest your cat first.
        auto walking_cat() -> UObject*
        {
            const auto not_it = static_cast<RC::Unreal::EObjectFlags>(RC::Unreal::RF_ClassDefaultObject | RC::Unreal::RF_ArchetypeObject);
            UObject* best = nullptr;
            double best_d = 1e18;
            auto me = location(player());
            for (UObject* w : find_all(STR("SwtAdventureWalkingNPC")))
            {
                if (!w || w->HasAnyFlags(not_it) || !ai_running(w)) continue;
                auto at = location(w);
                if (!me || !at) continue;
                if (double d = distance(*me, *at); d < best_d)
                {
                    best_d = d;
                    best = w;
                }
            }
            return best;
        }
        struct AiRun
        {
            UObject* animal{};
            UObject* walker{};
            Vec3 home{};
        };
    } // namespace

    auto run_ai_request() -> void
    {
        phase("ai");
        // ----- the game's trees as data
        Json trees = Json::object();
        for (const wchar_t* tree_name : AI_TREES)
        {
            UObject* tree = ai_tree_named(tree_name);
            auto nodes = ai_tree_nodes(tree);
            Json o = Json::object();
            o.set("loaded", Json(tree != nullptr));
            o.set("blackboard", Json(text(ai_tree_blackboard(tree))));
            o.set("nodes", Json(static_cast<int>(nodes.size())));
            Json lines = Json::array();
            for (auto& n : nodes)
            {
                std::wstring line = std::to_wstring(n.depth) + L" " + n.role + L" " + n.kind + L" '" + n.name + L"'";
                for (auto& [k, v] : n.settings) line += L" " + k + L"=" + v;
                lines.push(Json(text(line)));
            }
            o.set("lines", lines);
            trees.set(text(std::wstring(tree_name)), o);
        }
        value("ai.trees", trees);
        expect("ai.tree_refusals", !ai_tree_named(L"BT_NoSuchTree") && ai_tree_nodes(nullptr).empty() && ai_tree_nodes(player()).empty());

        // ----- your cat has no AI
        expect("ai.player_none", !ai_controller(player()) && !ai_running(player()) && !ai_tree(player()) && !stop_ai(player())
                                     && blackboard_keys(player()).empty() && !set_blackboard(player(), L"Detected", true));

        // ----- an awake roaming animal and a walking cat
        auto run = std::make_shared<AiRun>();
        for (UObject* a : fight_animals(2500))
            if (!run->animal && ai_running(a)) run->animal = a;
        run->walker = walking_cat();
        run->home = location(player()).value_or(Vec3{});
        if (!run->animal || !run->walker)
        {
            expect("ai.found", false, run->animal ? "no walking cat" : "no awake animal near");
            done("ai");
            return;
        }
        UObject* a = run->animal;
        value("ai.animal", Json(text(class_name(a))));
        value("ai.animal_controller", Json(text(class_name(ai_controller(a)))));
        value("ai.animal_brain", Json(text(class_name(ai_brain(a)))));
        value("ai.animal_state", state(a));
        Json keys = Json::array();
        for (auto& k : blackboard_keys(a)) keys.push(Json(text(k.name + L":" + k.type)));
        value("ai.animal_keys", keys);
        value("ai.walker_controller", Json(text(class_name(ai_controller(run->walker)))));
        value("ai.walker_state", state(run->walker));

        // ----- every kind of key written and read back, and the refusals
        const double reaction = blackboard_float(a, L"ChaseReactionTime").value_or(0);
        expect("ai.write_float", set_blackboard(a, L"ChaseReactionTime", 30.0) && blackboard_float(a, L"ChaseReactionTime") == 30.0);
        expect("ai.write_int", set_blackboard(a, L"CurrentIndexSpline", 3) && blackboard_int(a, L"CurrentIndexSpline") == 3);
        Vec3 spot{run->home.x + 100, run->home.y, run->home.z};
        expect("ai.write_vector", set_blackboard(a, L"PointOfInterest", spot) && blackboard_vector(a, L"PointOfInterest").has_value()
                                      && std::abs(blackboard_vector(a, L"PointOfInterest")->x - spot.x) < 1);
        expect("ai.clear_vector", clear_blackboard(a, L"PointOfInterest") && !blackboard_vector(a, L"PointOfInterest"));
        expect("ai.write_refused", !set_blackboard(a, L"Detected", 1.0) && !set_blackboard(a, L"NoSuchKey", true)
                                       && !blackboard_int(a, L"Detected") && !clear_blackboard(a, L"NoSuchKey"));
        expect("ai.write_int_back", set_blackboard(a, L"CurrentIndexSpline", 0));

        // ----- the animal sent into its tree's chase branch (Detected and Target: it waits ChaseReactionTime, 30 s,
        // before it moves), then back (Detected cleared: its roaming again)
        expect("ai.write_chase", set_blackboard(a, L"Target", player()) && set_blackboard(a, L"Detected", true)
                                     && blackboard_object(a, L"Target") == player() && blackboard_bool(a, L"Detected") == true);
        // ----- the walking cat stopped by its own key (BT_WalkingNPC walks only while bShouldAllowMovement is set)
        expect("ai.walker_stop", set_blackboard(run->walker, L"bShouldAllowMovement", false));
        value("ai.walker_stopped_0", state(run->walker));
        after(1.0, [run, reaction] {
            value("ai.chasing_1", state(run->animal));
            value("ai.detected_1", Json(blackboard_bool(run->animal, L"Detected").value_or(false)));
            after(2.0, [run, reaction] {
                value("ai.chasing_3", state(run->animal));
                value("ai.detected_3", Json(blackboard_bool(run->animal, L"Detected").value_or(false)));
                value("ai.walker_stopped_3", state(run->walker));
                expect("ai.calm", set_blackboard(run->animal, L"Detected", false) && clear_blackboard(run->animal, L"Target")
                                      && set_blackboard(run->animal, L"ChaseReactionTime", reaction));
                expect("ai.walker_go", set_blackboard(run->walker, L"bShouldAllowMovement", true));
                after(3.0, [run] {
                    value("ai.calmed", state(run->animal));
                    value("ai.walker_walking", state(run->walker));
                    // ----- stopped: through the game's sleep (your cat 6000 units away) and wake (back), then started
                    expect("ai.stop", stop_ai(run->animal));
                    value("ai.stopped", state(run->animal));
                    auto at = location(run->animal).value_or(run->home);
                    double dx = run->home.x - at.x, dy = run->home.y - at.y, len = std::max(1.0, std::sqrt(dx * dx + dy * dy));
                    Vec3 away{at.x + dx / len * 6000, at.y + dy / len * 6000, run->home.z};
                    if (auto g = ground(away.x, away.y, run->home.z + 2000)) away.z = *g + 50;
                    teleport(player(), away);
                    after(4.0, [run] {
                        value("ai.stopped_away", state(run->animal));
                        teleport(player(), run->home);
                        after(4.0, [run] {
                            value("ai.stopped_back", state(run->animal));
                            expect("ai.restart", restart_ai(run->animal));
                            after(1.0, [run] {
                                value("ai.restarted", state(run->animal));
                                // ----- the walking cat near: walking, stopped by its key, walking again
                                auto w = location(run->walker).value_or(run->home);
                                teleport(player(), Vec3{w.x + 400, w.y, w.z + 50});
                                after(2.0, [run] {
                                    value("ai.near_0", state(run->walker));
                                    after(3.0, [run] {
                                        value("ai.near_3", state(run->walker));
                                        set_blackboard(run->walker, L"bShouldAllowMovement", false);
                                        after(1.0, [run] {
                                            value("ai.near_stopped_1", state(run->walker));
                                            after(3.0, [run] {
                                                value("ai.near_stopped_4", state(run->walker));
                                                set_blackboard(run->walker, L"bShouldAllowMovement", true);
                                                after(3.0, [run] {
                                                    value("ai.near_walking_3", state(run->walker));
                                                    teleport(player(), run->home);
                                                    done("ai");
                                                });
                                            });
                                        });
                                    });
                                });
                            });
                        });
                    });
                });
            });
        });
    }
} // namespace t
