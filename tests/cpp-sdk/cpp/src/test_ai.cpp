// Ai.hpp: the game's AI, on request ("ai"), for tests/game/test_cpp_sdk.py (docs/plans/cpp-sdk-ai.md, step 1). The
// game's trees read as data; an animal's and a walking cat's AI, their keys written and read back, a walking cat
// stopped and set walking again by its own key, an animal sent into its tree's chase branch and back, an animal's
// logic stopped through the game's sleep and wake (your cat away and back) and started again. Moving ("ai_move", step
// 2): an animal walked to a place, stopped midway, given back to its tree at the end; a mod's cat after your cat; an
// animal turned to face your cat. Noticing ("ai_notice", step 3): an animal ignoring your cat, noticing it by the game's
// own call, giving it up, running from it. Trees ("ai_trees", step 4): another of the game's trees run on an animal and
// back, its own trees set and read back; a mod's cat following your cat about, and let go.
#include "checks.hpp"

#include <chrono>
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
        expect("ai.write_float_int", set_blackboard(a, L"ChaseReactionTime", 25) && blackboard_float(a, L"ChaseReactionTime") == 25.0);
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

    namespace
    {
        struct MoveRun
        {
            UObject* animal{};
            Npc cat;
            Vec3 start{}, spot{};
            std::vector<std::string> results;
            double arrived_after{-1};
            std::chrono::steady_clock::time_point began;
        };
        auto result_name(WalkResult r) -> std::string
        {
            switch (r)
            {
            case WalkResult::Arrived: return "arrived";
            case WalkResult::Blocked: return "blocked";
            case WalkResult::Cancelled: return "cancelled";
            default: return "none";
            }
        }
        auto yaw_to(UObject* from, UObject* to) -> double
        {
            auto a = location(from), b = location(to);
            if (!a || !b) return 0;
            return std::atan2(b->y - a->y, b->x - a->x) * 180.0 / 3.14159265358979323846;
        }
        auto yaw_of(UObject* actor) -> double
        {
            auto r = call_reflected(actor, STR("K2_GetActorRotation"));
            return r ? get(r->get(L"ReturnValue"), L"Yaw").number() : 0;
        }
    } // namespace

    auto run_ai_move_request() -> void
    {
        phase("ai_move");
        expect("move.refused", !move_to(player(), Vec3{0, 0, 0}) && !move_to(nullptr, Vec3{0, 0, 0}) && !stop_moving(player())
                                   && !moving(nullptr) && !face(nullptr, Vec3{0, 0, 0}));
        auto run = std::make_shared<MoveRun>();
        for (UObject* a : fight_animals(2500))
            if (!run->animal && ai_running(a)) run->animal = a;
        if (!run->animal)
        {
            expect("move.found", false, "no awake animal near");
            done("ai_move");
            return;
        }
        // ----- 300 units toward your cat, at 200 cm/s
        run->start = *location(run->animal);
        auto me = *location(player());
        double dx = me.x - run->start.x, dy = me.y - run->start.y, len = std::max(1.0, std::hypot(dx, dy));
        run->spot = {run->start.x + dx / len * 300, run->start.y + dy / len * 300, run->start.z};
        if (auto g = ground(run->spot.x, run->spot.y, run->start.z + 300)) run->spot.z = *g;
        run->began = std::chrono::steady_clock::now();
        expect("move.go", move_to(run->animal, run->spot, {.speed = 200}, [run](WalkResult r) {
            run->results.push_back(result_name(r));
            run->arrived_after = std::chrono::duration<double>(std::chrono::steady_clock::now() - run->began).count();
        }));
        value("move.speed", Json(get(get(run->animal, L"CharacterMovement").object, L"MaxWalkSpeed").number()));
        value("move.ai_stopped", Json(!ai_running(run->animal)));
        after(0.5, [run] { value("move.moving_mid", Json(moving(run->animal))); });
        after(8.0, [run] {
            auto at = location(run->animal).value_or(Vec3{});
            value("move.first", Json(run->results.empty() ? std::string() : run->results.front()));
            value("move.first_after", Json(run->arrived_after));
            value("move.first_off", Json(std::hypot(at.x - run->spot.x, at.y - run->spot.y)));
            value("move.first_walked", Json(std::hypot(at.x - run->start.x, at.y - run->start.y)));
            value("move.moving_after", Json(moving(run->animal)));
            value("move.ai_after", Json(ai_running(run->animal)));
            // ----- 400 units back the way it came, stopped after a second
            run->results.clear();
            double bx = run->start.x - at.x, by = run->start.y - at.y, blen = std::max(1.0, std::hypot(bx, by));
            run->start = at;
            expect("move.go_back", move_to(run->animal, Vec3{at.x + bx / blen * 400, at.y + by / blen * 400, at.z},
                                           {.speed = 150}, [run](WalkResult r) { run->results.push_back(result_name(r)); }));
            after(1.0, [run] {
                expect("move.stop", stop_moving(run->animal));
                value("move.stopped_result", Json(run->results.empty() ? std::string() : run->results.front()));
                auto here = location(run->animal).value_or(Vec3{});
                after(2.0, [run, here] {
                    auto at = location(run->animal).value_or(Vec3{});
                    value("move.stopped_drift", Json(std::hypot(at.x - here.x, at.y - here.y)));
                    value("move.stopped_moving", Json(moving(run->animal)));
                    // ----- facing your cat
                    expect("move.face", face(run->animal, player()));
                    after(0.3, [run] {
                        double off = std::fmod(std::abs(yaw_of(run->animal) - yaw_to(run->animal, player())) + 360.0, 360.0);
                        value("move.face_off", Json(std::min(off, 360.0 - off)));
                        // ----- a short move given back to its tree at the end
                        auto at = location(run->animal).value_or(Vec3{});
                        run->results.clear();
                        move_to(run->animal, Vec3{at.x + 120, at.y, at.z}, {.speed = 200, .restart_after = true},
                                [run](WalkResult r) { run->results.push_back(result_name(r)); });
                        after(5.0, [run] {
                            value("move.restart_result", Json(run->results.empty() ? std::string() : run->results.front()));
                            value("move.restart_ai", Json(ai_running(run->animal)));
                            // ----- a mod's cat 400 units off, after your cat
                            auto me = *location(player());
                            run->cat = spawn_npc({.at = {me.x + 400, me.y, me.z}});
                            run->results.clear();
                            run->began = std::chrono::steady_clock::now();
                            after(1.0, [run] {
                                UObject* c = run->cat.actor();
                                value("move.cat_controller", Json(text(class_name(ai_controller(c)))));
                                expect("move.cat_go", move_to(c, player(), {.speed = 250, .radius = 120}, [run](WalkResult r) {
                                    run->results.push_back(result_name(r));
                                    run->arrived_after = std::chrono::duration<double>(std::chrono::steady_clock::now() - run->began).count();
                                }));
                                after(8.0, [run] {
                                    UObject* c = run->cat.actor();
                                    auto a = location(c), b = location(player());
                                    value("move.cat_result", Json(run->results.empty() ? std::string() : run->results.front()));
                                    value("move.cat_off", Json(a && b ? std::hypot(a->x - b->x, a->y - b->y) : -1.0));
                                    run->cat.remove();
                                    restart_ai(run->animal);
                                    done("ai_move");
                                });
                            });
                        });
                    });
                });
            });
        });
    }

    namespace
    {
        struct NoticeProbe
        {
            UObject* a{};
            UObject* b{};
            Vec3 home{};
        };
        auto detection_state(UObject* x) -> Json
        {
            Json o = Json::object();
            UObject* c = detection_component(x);
            o.set("type", Json(get(c, L"DetectionType").number()));
            o.set("detected", Json(blackboard_bool(x, L"Detected").value_or(false)));
            o.set("target", Json(text(name(blackboard_object(x, L"Target")))));
            o.set("task", Json(text(ai_task(x).name)));
            o.set("running", Json(ai_running(x)));
            return o;
        }
        // Your cat put `ahead` units in front of an actor, facing it.
        auto stand_before(UObject* x, double ahead) -> void
        {
            auto at = location(x);
            auto fwd = call_reflected(x, STR("GetActorForwardVector"));
            if (!at || !fwd) return;
            double fx = get(fwd->get(L"ReturnValue"), L"X").number(), fy = get(fwd->get(L"ReturnValue"), L"Y").number();
            Vec3 to{at->x + fx * ahead, at->y + fy * ahead, at->z + 30};
            teleport(player(), to);
            face(player(), x);
        }
    } // namespace

    // Noticing ("ai_notice", step 3): an animal seeing your cat in front of it (the control), made to give it up; another
    // made to ignore your cat, not noticing it in front of it, made to notice by the game's own call, and back to its
    // mask; one fleeing from your cat; every animal near ignoring your cat and back. The animals' reaction time is set
    // to 30 s meanwhile, so none gives chase (a chase that catches your cat starts a fight).
    auto run_ai_notice_request() -> void
    {
        phase("ai_notice");
        // The nav mesh: under your cat, and not in the sky far above the world.
        auto me0 = *location(player());
        auto on = nav_point(me0);
        value("notice.nav_here", Json(on ? std::hypot(on->x - me0.x, on->y - me0.y) : -1.0));
        value("notice.nav_sky", Json(nav_point(Vec3{me0.x, me0.y, me0.z + 50000}).has_value()));
        value("notice.nav_meshes", Json(static_cast<int>(detail::nav_meshes().size())));
        expect("notice.refused", !detection_flags(player()) && !set_detection_flags(player(), 0) && !ignore_player(player())
                                     && !calm(nullptr) && !notice_player(nullptr) && !flee(nullptr, Vec3{}));
        auto p = std::make_shared<NoticeProbe>();
        p->home = *location(player());
        // The two animals nearest your cat, woken: your cat put between them (one near the edge of your cat's zone
        // may be asleep, after the tests before).
        auto two = fight_animals(4000);
        if (two.size() < 2)
        {
            expect("notice.found", false, "fewer than two animals near");
            done("ai_notice");
            return;
        }
        p->a = two[0];
        p->b = two[1];
        auto la = *location(p->a), lb = *location(p->b);
        Vec3 mid{(la.x + lb.x) / 2, (la.y + lb.y) / 2, (la.z + lb.z) / 2 + 30};
        if (auto g = ground(mid.x, mid.y, mid.z + 500)) mid.z = *g + 30;
        teleport(player(), mid);
        after(2.0, [p] {
        value("notice.awake", Json(ai_running(p->a) && ai_running(p->b)));
        static double reaction = 0.5;
        if (auto s = senses(p->a); s.react_to_chase) reaction = *s.react_to_chase;
        for (UObject* x : {p->a, p->b})
            if (auto s = senses(x); s.react_to_chase) *s.react_to_chase = 30;
        value("notice.flags", Json(detection_flags(p->a).value_or(-1)));
        // ----- the control: your cat in front of a, 250 units
        stop_ai(p->b);   // b stays where it is meanwhile
        stand_before(p->a, 250);
        after(6.0, [p] {
            value("notice.seen", detection_state(p->a));
            expect("notice.calm", calm(p->a));
            after(1.0, [p] {
                value("notice.calmed", detection_state(p->a));
                stop_ai(p->a);
                // ----- b ignoring your cat in front of it
                restart_ai(p->b);
                expect("notice.ignore", ignore_player(p->b) && ignoring_player(p->b) && detection_flags(p->b) == 0);
                stand_before(p->b, 250);
                after(6.0, [p] {
                    value("notice.ignored", detection_state(p->b));
                    // ----- noticed by the game's own call, ignoring or not; then given up and back to its mask
                    expect("notice.notice", notice_player(p->b));
                    after(1.0, [p] {
                        value("notice.noticed", detection_state(p->b));
                        expect("notice.unignore", ignore_player(p->b, false) && !ignoring_player(p->b));
                        value("notice.flags_back", Json(detection_flags(p->b).value_or(-1)));
                        calm(p->b);
                        restart_ai(p->a);
                        // ----- a running from your cat, 500 units in front of it (an animal far from your cat sleeps,
                        // and stops moving: away from your cat at 2,000 units, it ran 350 of 600 and stood)
                        stand_before(p->a, 500);
                        after(1.0, [p] {
                            auto me = *location(player());
                            auto at = *location(p->a);
                            static double before = 0;
                            before = std::hypot(at.x - me.x, at.y - me.y);
                            value("notice.flee_before", Json(before));
                            static std::string result;
                            result.clear();
                            expect("notice.flee", flee(p->a, player(), 600, std::nullopt, [](WalkResult r) { result = result_name(r); }));
                            value("notice.flee_speed", Json(get(get(p->a, L"CharacterMovement").object, L"MaxWalkSpeed").number()));
                            after(5.0, [p] {
                                auto me = *location(player());
                                auto at = *location(p->a);
                                value("notice.flee_after", Json(std::hypot(at.x - me.x, at.y - me.y)));
                                value("notice.flee_result", Json(result));
                                value("notice.flee_ai", Json(ai_running(p->a)));
                                calm(p->a);
                                teleport(player(), p->home);
                                // ----- every animal near ignoring your cat, and back; b, ignored by the mod itself
                                // before, stays ignored; a mask ignore_player didn't zero is left as it is
                                ignore_player(p->b, true);
                                set_detection_flags(p->a, 15);
                                expect("notice.unignore_other", ignore_player(p->a, false) && detection_flags(p->a) == 15);
                                set_detection_flags(p->a, 3);
                                ignore_player_everywhere(true);
                                after(1.5, [p] {
                                    int near_ignoring = 0, around = 0;
                                    for (const Nearby& n : nearby(Kind::Creatures, 4000))
                                    {
                                        ++around;
                                        if (ignoring_player(n.actor)) ++near_ignoring;
                                    }
                                    value("notice.everywhere_near", Json(around));
                                    value("notice.everywhere_ignoring", Json(near_ignoring));
                                    ignore_player_everywhere(false);
                                    int still = 0;
                                    for (const Nearby& n : nearby(Kind::Creatures, 4000))
                                        if (n.actor != p->b && ignoring_player(n.actor)) ++still;
                                    value("notice.everywhere_after", Json(still));
                                    value("notice.own_ignore_kept", Json(ignoring_player(p->b)));
                                    if (detail::object_staying(p->b, nullptr)) ignore_player(p->b, false);
                                    for (UObject* x : {p->a, p->b})   // either may be gone (your cat went far)
                                        if (detail::object_staying(x, nullptr))
                                            if (auto s = senses(x); s.react_to_chase) *s.react_to_chase = static_cast<float>(reaction);
                                    done("ai_notice");
                                });
                            });
                        });
                    });
                });
            });
        });
        });
    }


    namespace
    {
        struct TreesRun
        {
            UObject* animal{};
            Npc cat;
            Vec3 home{};
        };
        auto tree_name(UObject* t) -> Json { return Json(text(name(t))); }
        auto cat_off(const std::shared_ptr<TreesRun>& r) -> double
        {
            auto a = location(r->cat.actor()), b = location(player());
            return a && b ? std::hypot(a->x - b->x, a->y - b->y) : -1.0;
        }
        // A walkable place `ahead` units from your cat, along +x (or -x), on the cats' mesh.
        auto walkable_from(Vec3 from, double ahead, UObject* by) -> Vec3
        {
            for (double sign : {1.0, -1.0})
                for (double side : {0.0, 300.0, -300.0})
                    if (auto on = nav_point(Vec3{from.x + sign * ahead, from.y + side, from.z}, by)) return Vec3{on->x, on->y, on->z + 30};
            return from;
        }
    } // namespace

    auto run_ai_trees_request() -> void
    {
        phase("ai_trees");
        UObject* boss = ai_tree_named(L"BT_BossEnemy");
        UObject* enemy = ai_tree_named(L"BT_Enemy");
        expect("trees.refused", !run_tree(player(), boss) && !run_tree(nullptr, boss) && !set_trees(player(), boss)
                                    && !follow(player(), player()) && !follow(nullptr, player()) && !stop_following(nullptr)
                                    && !following(nullptr) && !ai_trees_set(player()).roaming);
        auto r = std::make_shared<TreesRun>();
        r->home = *location(player());
        for (UObject* x : fight_animals(2500))
            if (!r->animal && ai_running(x)) r->animal = x;
        if (!r->animal)
        {
            expect("trees.found", false, "no awake animal near");
            done("ai_trees");
            return;
        }
        UObject* a = r->animal;
        auto set_before = ai_trees_set(a);
        value("trees.roaming", tree_name(set_before.roaming));
        value("trees.fight", tree_name(set_before.fight));
        expect("trees.run_boss", run_tree(a, boss));
        after(1.0, [r, enemy] {
            value("trees.ran", tree_name(ai_tree(r->animal)));
            value("trees.ran_task", Json(text(ai_task(r->animal).name)));
            value("trees.ran_keys", Json(static_cast<int>(blackboard_keys(r->animal).size())));
            expect("trees.run_back", run_tree(r->animal, enemy));
            after(1.0, [r] {
                value("trees.back", tree_name(ai_tree(r->animal)));
                // Its own trees set and read back, then as they were.
                UObject* a = r->animal;
                auto was = ai_trees_set(a);
                expect("trees.set", set_trees(a, ai_tree_named(L"BT_BossEnemy"), ai_tree_named(L"BT_AttackEnemy")));
                auto now = ai_trees_set(a);
                value("trees.set_roaming", tree_name(now.roaming));
                value("trees.set_fight", tree_name(now.fight));
                expect("trees.set_back", set_trees(a, was.roaming, was.fight) && ai_trees_set(a).roaming == was.roaming);
                // ----- a mod's cat 300 units off, following your cat
                auto me = *location(player());
                r->cat = spawn_npc({.at = {me.x + 300, me.y, me.z}});
                after(1.0, [r] {
                    UObject* c = r->cat.actor();
                    expect("trees.follow", follow(c, player(), {.distance = 150, .speed = 250}) && following(c));
                    value("trees.follow_moving", Json(moving(c)));
                    after(4.0, [r] {
                        value("trees.close_4", Json(cat_off(r)));
                        // your cat 700 units on: it comes after
                        teleport(player(), walkable_from(*location(player()), 700, r->cat.actor()));
                        value("trees.moved_off", Json(cat_off(r)));
                        after(6.0, [r] {
                            value("trees.followed_6", Json(cat_off(r)));
                            expect("trees.stop", stop_following(r->cat.actor()) && !following(r->cat.actor()));
                            // your cat 700 units on again: it stays
                            teleport(player(), walkable_from(*location(player()), 700, r->cat.actor()));
                            value("trees.left_0", Json(cat_off(r)));
                            after(4.0, [r] {
                                value("trees.left_4", Json(cat_off(r)));
                                r->cat.remove();
                                teleport(player(), r->home);
                                done("ai_trees");
                            });
                        });
                    });
                });
            });
        });
    }
} // namespace t
