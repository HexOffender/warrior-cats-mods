// Ai.hpp: the game's AI, on request ("ai"), for tests/game/test_cpp_sdk.py (docs/plans/cpp-sdk-ai.md, step 1). The
// game's trees read as data; an animal's and a walking cat's AI, their keys written and read back, a walking cat
// stopped and set walking again by its own key, an animal sent into its tree's chase branch and back, an animal's
// logic stopped through the game's sleep and wake (your cat away and back) and started again. Moving ("ai_move", step
// 2): an animal walked to a place, stopped midway, given back to its tree at the end; a mod's cat after your cat; an
// animal turned to face your cat. Noticing ("ai_notice", step 3): an animal ignoring your cat, noticing it by the game's
// own call, giving it up, running from it. Trees ("ai_trees", step 4): another of the game's trees run on an animal and
// back, its own trees set and read back; a mod's cat following your cat about, and let go. A fight's AI ("ai_fight",
// step 5): the chances by tier, an enemy limited to one move at the Terrible tier, your cat's turns taken by auto_fight.
// Animals put in the world ("ai_spawn", step 6): a rabbit spawned, roaming, noticing your cat, fought and its rewards.
// The clan cats' walking ("ai_walk", step 7): a cat of the mod's walking a loop, stopping to talk; a game cat's path.
#include "checks.hpp"

#include <chrono>
#include <cstring>
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
            o.set("tracking", Json(tracking_player(x)));
            o.set("ignoring", Json(ignoring_player(x)));
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
                // ----- a, its detection still tracking your cat and its tree restarted, made to ignore it: it doesn't
                // notice your cat again (seen in a suite run before ignore_player gave your cat up itself: noticed
                // again within 6 s, its mask 0)
                restart_ai(p->a);
                expect("notice.ignore_tracked", ignore_player(p->a));
                after(6.0, [p] {
                value("notice.ignored_tracked", detection_state(p->a));
                value("notice.cats_response_ignoring", Json(detail::cats_response(p->a).value_or(-1)));
                ignore_player(p->a, false);
                value("notice.cats_response_back", Json(detail::cats_response(p->a).value_or(-1)));
                calm(p->a);
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
        });
    }


    namespace
    {
        struct TreesRun
        {
            UObject* animal{};
            Npc cat;
            Vec3 home{};
            Vec3 left_cat{}, left_you{};   // where the cat and your cat were as it was let go
        };
        auto moved_since(UObject* x, Vec3 from) -> double
        {
            auto at = location(x);
            return at ? std::hypot(at->x - from.x, at->y - from.y) : -1.0;
        }
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
                            r->left_cat = location(r->cat.actor()).value_or(Vec3{});
                            r->left_you = location(player()).value_or(Vec3{});
                            after(4.0, [r] {
                                value("trees.left_4", Json(cat_off(r)));
                                // Its own way since (your cat could be moved by the game meanwhile: seen once, the
                                // distance shrank by 660 in a suite run)
                                value("trees.left_moved", Json(moved_since(r->cat.actor(), r->left_cat)));
                                value("trees.you_moved", Json(moved_since(player(), r->left_you)));
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

    // A fight's AI ("ai_fight", step 5): the tiers' chances read and one set; a fight in which the enemy is limited to
    // one of its moves and its tier set to Terrible, made to last (its health raised), your cat's turns taken by
    // auto_fight; after three enemy turns its moves given back and the fight won.
    namespace
    {
        struct FightRun
        {
            Fighter enemy;
            UObject* enemy_actor{};
            int all_moves{};
            std::string only;
            int enemy_turns{}, attempts{};
            UObject* last_turn{};
            UObject* answered{};   // the end's dilemma popup answered, and when
            std::chrono::steady_clock::time_point answered_at;
            Json used = Json::array();
            std::chrono::steady_clock::time_point began;
            TimerId timer{};
            bool set_up{}, ending{};
            // The animals tried, nearest first from where the test began (listed again after a pounce, the one just
            // missed would be the nearest)
            Vec3 home{};   // your cat put back there at the end, as the other AI tests do (the tests after start there)
            std::vector<std::pair<UObject*, UClass*>> animals;
        };
        auto chances_json(const std::optional<AiChances>& c) -> Json
        {
            if (!c) return Json();
            Json a = Json::array();
            for (float f : {c->cure_status, c->cure_health, c->exhausted, c->support, c->buff, c->debuff, c->attack_weakest,
                            c->attack_slower, c->select_random, c->select_stance, c->select_aoe, c->select_powerful, c->select_status})
                a.push(Json(std::round(f * 100) / 100));
            return a;
        }
        auto tag_of(const Value& move) -> std::string { return text(get(move, L"AttackMoveTag.TagName").string()); }
        auto fight_once(const std::shared_ptr<FightRun>& r) -> void;
        auto finish(const std::shared_ptr<FightRun>& r) -> void
        {
            after(1.0, [r] {   // the game done putting your cat back after the fight first
                teleport(player(), r->home);
                done("ai_fight");
            });
        }
        auto fight_tick(const std::shared_ptr<FightRun>& r) -> void
        {
            const double t = std::chrono::duration<double>(std::chrono::steady_clock::now() - r->began).count();
            if (!combat_active())
            {
                if (r->ending || r->set_up)   // over
                {
                    cancel(r->timer);
                    value("fight.over", Json(true));
                    value("fight.used", r->used);
                    value("fight.enemy_turns", Json(r->enemy_turns));
                    value("fight.auto_turns", Json(auto_fight_turns()));
                    finish(r);
                }
                else if (t > 12)   // the pounce missed: the next animal
                {
                    cancel(r->timer);
                    fight_once(r);
                }
                return;
            }
            if (!r->set_up && !fight_enemies().empty())
            {
                r->set_up = true;
                r->enemy = fight_enemies().front();
                r->enemy_actor = r->enemy.actor();
                auto all = r->enemy.moves();
                r->all_moves = static_cast<int>(all.size());
                value("fight.moves", Json(r->all_moves));
                const int last = r->all_moves - 1;
                r->only = last >= 0 ? tag_of(all[last]) : std::string();
                // A place twice: refused with nothing moved.
                expect("fight.limit_twice", last >= 1 && !limit_moves(r->enemy, {last, 0, last}) && tag_of(r->enemy.moves().front()) == tag_of(all[0]));
                value("fight.only", Json(r->only));
                expect("fight.limit", last >= 0 && limit_moves(r->enemy, {last}) && r->enemy.moves().size() == 1
                                          && tag_of(r->enemy.moves().front()) == r->only);
                expect("fight.tier", set_ai_tier(r->enemy, 7) && r->enemy.ai_tier() && *r->enemy.ai_tier() == 7);
                if (Resource hp = resource(r->enemy_actor, STR("SwtQuestHealthComponent")))
                {
                    *hp.max = 2000;
                    *hp.value = 2000;
                }
                auto_fight(true);
            }
            // The end's dilemma (by chance): the first answer, as test_fights does; once per popup (again if it's still up
            // 2 s on).
            if (r->ending && dilemma())
            {
                UObject* popup = ui::screen(L"WBP_GuiPopupDilemma_C").object();
                const auto now = std::chrono::steady_clock::now();
                if ((popup != r->answered || now - r->answered_at > std::chrono::seconds(2)) && answer_dilemma(0))
                {
                    r->answered = popup;
                    r->answered_at = now;
                }
            }
            UObject* cur = fight_current();
            if (cur && cur != r->last_turn && cur == r->enemy_actor) ++r->enemy_turns;
            r->last_turn = cur;
            // The move it used: what AttackSelected holds as its turn plays.
            if (cur && cur == r->enemy_actor)
            {
                std::string tag = tag_of(r->enemy.move());
                if (!tag.empty() && tag != "None" && (r->used.size() == 0 || r->used[r->used.size() - 1].string() != tag + "@" + std::to_string(r->enemy_turns)))
                    r->used.push(Json(tag + "@" + std::to_string(r->enemy_turns)));
            }
            if (r->enemy_turns >= 3 && !r->ending && cur != r->enemy_actor)
            {
                auto_fight(false);
                if (fight_menu())
                {
                    expect("fight.restore", restore_moves(r->enemy) && static_cast<int>(r->enemy.moves().size()) == r->all_moves);
                    expect("fight.restore_again", !restore_moves(r->enemy));
                    r->ending = end_fight(true);
                }
            }
            if (t > 150)
            {
                cancel(r->timer);
                auto_fight(false);
                expect("fight.time", false, "the fight took too long");
                finish(r);
            }
        }
        auto fight_once(const std::shared_ptr<FightRun>& r) -> void
        {
            if (r->animals.empty())
                for (UObject* x : fight_animals(20000))
                    r->animals.emplace_back(x, x->GetClassPrivate());
            bool started = false;
            while (!started && r->attempts < 3 && r->attempts < static_cast<int>(r->animals.size()))
            {
                auto [x, cls] = r->animals[r->attempts++];
                started = detail::object_staying(x, cls) && start_fight(x);
            }
            value("fight.attempts", Json(r->attempts));
            if (!started)
            {
                expect("fight.started", false, std::format("no fight after {} tries, of {} animals", r->attempts, r->animals.size()));
                finish(r);
                return;
            }
            r->began = std::chrono::steady_clock::now();
            r->timer = every(0.1, [r] { detail::guarded(L"ai_fight test", [&] { fight_tick(r); }); });
        }
    } // namespace

    auto run_ai_fight_request() -> void
    {
        phase("ai_fight");
        // ----- the tiers' chances
        value("fight.tier1", chances_json(ai_chances(L"Tier1")));
        value("fight.terrible", chances_json(ai_chances(L"Terrible")));
        value("fight.perfect", chances_json(ai_chances(L"Perfect")));
        expect("fight.chances_refused", !ai_chances(L"Tier9") && !set_ai_chance(L"Tier1", L"NoSuchColumn", 0.5)
                                            && !set_ai_chance(L"Tier1", L"SelectRandom", 2.0) && !set_ai_chance(L"Tier9", L"SelectRandom", 0.5));
        const float was = ai_chances(L"Tier1") ? ai_chances(L"Tier1")->select_random : 0.5f;
        expect("fight.chance_set", set_ai_chance(L"Tier1", L"SelectRandom", 0.9) && ai_chances(L"Tier1")
                                       && std::abs(ai_chances(L"Tier1")->select_random - 0.9) < 1e-6);
        expect("fight.chance_back", set_ai_chance(L"Tier1", L"SelectRandom", was));
        expect("fight.refused", !set_ai_tier(Fighter{}, 7) && !limit_moves(Fighter{}, {0}) && !restore_moves(Fighter{}));
        // ----- a fight
        auto r = std::make_shared<FightRun>();
        r->home = *location(player());
        fight_once(r);
    }
    // Animals put in the world ("ai_spawn", step 6), out where the animals live (by your cat's starting spot, beside a
    // den, a pounce starts no fight): the kinds read; what isn't a kind refused; a rabbit spawned 600 units behind your
    // cat by a borrowed generator, roaming, then pounced: a fight with it won, its rewards given, it gone and the
    // generator given back after; another (respawn) noticing your cat, put back by its generator 2 s after it's gone
    // (your cat away by then), then removed for good.
    namespace
    {
        constexpr const wchar_t* RABBIT = L"Gameplay.Combat.Generator.Fixed.Rabbit.01.L6";
        struct SpawnRun
        {
            UObject* rabbit{};
            UClass* rabbit_class{};
            UObject* generator{};
            UClass* generator_class{};
            Vec3 generator_home{};         // where the borrowed generator was, and its tag, to see them given back
            std::wstring generator_tag_was;
            Vec3 home{};
            Json inventory_before;   // your cat's items before the fight
            double xp_before{};
            UObject* answered{};
            std::chrono::steady_clock::time_point began;
            TimerId timer{};
            bool ending{};
            int pounces{1};
            UObject* second{};
        };
        auto spawn_finish(const std::shared_ptr<SpawnRun>& r) -> void
        {
            after(1.0, [r] {
                teleport(player(), r->home);
                done("ai_spawn");
            });
        }
        auto spawn_second(const std::shared_ptr<SpawnRun>& r) -> void;
        // `then` once `cond` holds (looked at every 0.5 s), or after `seconds` anyway.
        auto when_or_after(std::function<bool()> cond, double seconds, std::function<void()> then) -> void
        {
            if (cond() || seconds <= 0) return then();
            after(0.5, [cond, seconds, then] { when_or_after(cond, seconds - 0.5, then); });
        }
        // After the fight: the rewards, and the rabbit gone and its generator given back.
        auto spawn_after_fight(const std::shared_ptr<SpawnRun>& r) -> void
        {
            // what the fight gave: every item that went up
            Json got = Json::object();
            Json now = inventory();
            if (now.is_object())
                for (size_t i = 0; i < now.keys().size(); ++i)
                {
                    const std::string& tag = now.keys()[i];
                    const double more = now.values()[i].number(0) - r->inventory_before[tag].number(0);
                    if (more > 0) got.set(tag, Json(more));
                }
            value("spawn.items_got", got);
            float* xp = Cat{player()}.xp();
            value("spawn.xp_got", Json(xp ? *xp - r->xp_before : -1.0));
            after(2.5, [r] {   // the keeper looks once a second
                value("spawn.rabbit_gone", Json(!detail::object_staying(r->rabbit, r->rabbit_class)));
                value("spawn.put_after", Json(static_cast<int>(detail::borrowed().all.size())));
                auto at = detail::object_staying(r->generator, r->generator_class) ? location(r->generator) : std::nullopt;
                value("spawn.generator_home", Json(at && std::hypot(at->x - r->generator_home.x, at->y - r->generator_home.y) < 5));
                value("spawn.generator_tag_back", Json(text(get(r->generator, L"ShadowClanCombatTags.ApprenticeSetup.TagName").string())));
                value("spawn.generator_tag_was", Json(text(r->generator_tag_was)));
                spawn_second(r);
            });
        }
        auto spawn_fight_tick(const std::shared_ptr<SpawnRun>& r) -> void
        {
            const double t = std::chrono::duration<double>(std::chrono::steady_clock::now() - r->began).count();
            if (!combat_active())
            {
                if (r->ending)
                {
                    cancel(r->timer);
                    spawn_after_fight(r);
                }
                else if (t > 12 && r->pounces < 3 && detail::object_staying(r->rabbit, r->rabbit_class))
                {
                    // Pounced again, as test_fights does (a pounce can miss; and right after another test's fight a
                    // pounce started none: seen)
                    ++r->pounces;
                    start_fight(r->rabbit);
                    r->began = std::chrono::steady_clock::now();
                }
                else if (t > 12)
                {
                    cancel(r->timer);
                    expect("spawn.fight", false, "no fight with the rabbit after three pounces");
                    spawn_finish(r);
                }
                return;
            }
            if (!r->ending && fight_menu())
            {
                Json enemies = Json::array();
                for (Fighter f : fight_enemies())
                {
                    Json e = Json::object();
                    e.set("model", Json(text(name(get(f.actor(), L"Mesh.SkeletalMesh").object))));
                    e.set("level", Json(f.level() ? *f.level() : -1));
                    enemies.push(e);
                }
                value("spawn.enemies", enemies);
                r->ending = end_fight(true);
            }
            if (r->ending && dilemma())   // the end's dilemma (by chance): its first answer, once per popup
            {
                UObject* popup = ui::screen(L"WBP_GuiPopupDilemma_C").object();
                if (popup != r->answered && answer_dilemma(0)) r->answered = popup;
            }
            if (t > 90)
            {
                cancel(r->timer);
                expect("spawn.time", false, "the fight took too long");
                spawn_finish(r);
            }
        }
        // Another, respawning: it notices your cat in front of it; gone, its generator puts it back; removed for good.
        auto spawn_second(const std::shared_ptr<SpawnRun>& r) -> void
        {
            auto me = *location(player());
            r->second = spawn_animal(RABBIT, Vec3{me.x + 600, me.y, me.z + 50}, {.respawn = true});
            expect("spawn.second", r->second != nullptr);
            if (!r->second) return spawn_finish(r);
            if (auto s = senses(r->second); s.react_to_chase) *s.react_to_chase = 30;   // it notices, but doesn't chase
            after(2.0, [r] {
                stand_before(r->second, 250);
                // noticed within 10 s (looked at every 0.5 s: in one run it hadn't at 6 s)
                when_or_after([r] { return blackboard_bool(r->second, L"Detected").value_or(false) || tracking_player(r->second); }, 10.0, [r] {
                    value("spawn.noticed", detection_state(r->second));
                    calm(r->second);
                    // your cat 2,500 units off first: the new one, not slowed as this one is, would chase your cat
                    // into a fight (seen)
                    auto me = *location(player());
                    Vec3 off{me.x + 2500, me.y, me.z + 100};
                    if (auto g = ground(off.x, off.y, off.z + 1000)) off.z = *g + 30;
                    teleport(player(), off);
                    destroy(r->second);   // gone, as the game takes an animal away
                    after(4.0, [r] {
                        UObject* again = nullptr;   // listed by animals(), its kind the mod's
                        for (const Animal& a : animals(6000))
                            if (a.kind == RABBIT && a.actor != r->second) again = a.actor;
                        value("spawn.respawned", Json(again != nullptr));
                        UObject* gen = again ? get(again, L"PreyGenerator").object : nullptr;
                        Vec3 gen_home{};
                        for (auto& b : detail::borrowed().all)
                            if (b.generator == gen) gen_home = b.home;
                        expect("spawn.remove", again && remove_animal(again));
                        after(2.5, [r, gen, gen_home] {
                            bool back = false;
                            for (const Animal& a : animals(6000)) back = back || a.kind == RABBIT;
                            value("spawn.removed_stays_gone", Json(!back));
                            auto at = gen ? location(gen) : std::nullopt;
                            value("spawn.removed_generator_home", Json(at && std::hypot(at->x - gen_home.x, at->y - gen_home.y) < 5));
                            spawn_finish(r);
                        });
                    });
                });
            });
        }
    } // namespace

    auto run_ai_spawn_request() -> void
    {
        phase("ai_spawn");
        auto r = std::make_shared<SpawnRun>();
        r->home = *location(player());
        // ----- the kinds
        auto kinds = animal_kinds();
        value("spawn.kinds", Json(static_cast<int>(kinds.size())));
        for (const AnimalKind& k : kinds)
            if (k.tag == RABBIT)
            {
                Json party = Json::array();
                for (size_t i = 0; i < k.party.size(); ++i) party.push(Json(text(k.party[i]) + "@" + std::to_string(k.levels[i])));
                value("spawn.rabbit_kind", party);
            }
        // ----- your cat out where the animals live
        if (auto x = fight_animals(6000); !x.empty())
            if (auto there = location(x.front()))
            {
                Vec3 spot{there->x + 300, there->y, there->z + 50};
                if (auto g = ground(spot.x, spot.y, spot.z + 500)) spot.z = *g + 30;
                teleport(player(), spot);
            }
        // ----- refused
        auto me = *location(player());
        const size_t borrowed_before = detail::borrowed().all.size();
        expect("spawn.refused", !spawn_animal(L"", me) && !spawn_animal(L"Gameplay.Combat.Generator.NoSuchKind", me)
                                    && detail::borrowed().all.size() == borrowed_before && !remove_animal(nullptr) && !remove_animal(player()));
        // ----- a rabbit 600 units behind your cat
        r->rabbit = spawn_animal(RABBIT, Vec3{me.x - 600, me.y, me.z + 50});
        if (!r->rabbit)
        {
            expect("spawn.rabbit", false, "no rabbit");
            return spawn_finish(r);
        }
        r->rabbit_class = r->rabbit->GetClassPrivate();
        r->generator = get(r->rabbit, L"PreyGenerator").object;
        r->generator_class = r->generator ? r->generator->GetClassPrivate() : nullptr;
        for (auto& b : detail::borrowed().all)
            if (b.animal == r->rabbit)
            {
                r->generator_home = b.home;
                r->generator_tag_was = b.tags.size() > 4 ? b.tags[4] : std::wstring();   // ShadowClan's apprentice
            }
        value("spawn.model", Json(text(name(get(r->rabbit, L"Mesh.SkeletalMesh").object))));
        value("spawn.generator_class", Json(text(name(r->generator ? r->generator->GetClassPrivate() : nullptr))));
        value("spawn.ai_running", Json(ai_running(r->rabbit)));
        // slow to chase (30 s): noticing your cat, it chased your cat into a fight of its own before the pounce (seen in
        // a suite run). Made to ignore your cat instead, a pounce on it started no fight (seen).
        if (auto s = senses(r->rabbit); s.react_to_chase) *s.react_to_chase = 30;
        bool listed = false;
        for (const Animal& a : animals(2000))
            if (a.actor == r->rabbit) listed = a.kind == RABBIT && a.generator == r->generator && a.model == L"SK_Rabbit";
        value("spawn.listed", Json(listed));
        after(2.0, [r] {
            // ----- roaming: its tree running, something to do
            value("spawn.task", Json(text(ai_task(r->rabbit).name)));
            value("spawn.ai_running_2s", Json(ai_running(r->rabbit)));
            // ----- a fight with it, won: its rewards
            Json rw = Json::array();
            for (auto& [k, v] : map_entries(r->rabbit, L"rewards")) rw.push(Json(text(get(k, L"TagName").string())));
            value("spawn.rewards", rw);   // its reward table's keys, by rank (not items)
            r->inventory_before = inventory();
            float* xp = Cat{player()}.xp();
            r->xp_before = xp ? *xp : 0;
            expect("spawn.start_fight", start_fight(r->rabbit));
            r->began = std::chrono::steady_clock::now();
            r->timer = every(0.1, [r] { detail::guarded(L"ai_spawn test", [&] { spawn_fight_tick(r); }); });
        });
    }
    // The clan cats' walking ("ai_walk", step 7): the game's walking cats and their paths; one of the mod's cats walking
    // a loop of four points round your cat, stopping while your cat talks to it and walking on after; a game cat given
    // a path of the mod's (there and back), then its own back; the mod's path gone with its cat.
    namespace
    {
        struct WalkRun
        {
            Npc cat;
            Vec3 center{};
            UObject* game_cat{};
            UObject* game_had{};
            double game_speed{};
            Vec3 last{};
            double walked{};
            double off_center{};
            UObject* path{};
        };
        auto off(UObject* x, Vec3 from) -> double
        {
            auto at = location(x);
            return at ? std::hypot(at->x - from.x, at->y - from.y) : -1.0;
        }
        auto walker_json(const Walker& w) -> Json
        {
            Json o = Json::object();
            o.set("points", Json(static_cast<int>(w.points.size())));
            o.set("loop", Json(w.loop));
            o.set("walking", Json(w.walking));
            o.set("mod_path", Json(w.mod_path));
            o.set("path_class", Json(text(name(w.path ? w.path->GetClassPrivate() : nullptr))));
            return o;
        }
        auto walk_game_cat(const std::shared_ptr<WalkRun>& r) -> void;
    } // namespace

    auto run_ai_walk_request() -> void
    {
        phase("ai_walk");
        auto r = std::make_shared<WalkRun>();
        // ----- the game's walking cats
        auto all = walkers();
        value("walk.walkers", Json(static_cast<int>(all.size())));
        if (!all.empty()) value("walk.first", walker_json(all.front()));
        for (const Walker& w : all)
            if (!r->game_cat && !w.mod_path && w.points.size() >= 2) r->game_cat = w.actor;
        // ----- refused
        r->center = *location(player());
        std::vector<Vec3> square;
        for (auto [dx, dy] : std::vector<std::pair<double, double>>{{300, 300}, {300, -300}, {-300, -300}, {-300, 300}})
        {
            Vec3 pt{r->center.x + dx, r->center.y + dy, r->center.z};
            if (auto g = ground(pt.x, pt.y, pt.z + 300)) pt.z = *g;
            square.push_back(pt);
        }
        expect("walk.refused", !walk_path(player(), square) && !walk_path(nullptr, square) && !stop_walking(nullptr)
                                   && !walk_again(player()) && !own_path(player()));
        // ----- one of the mod's cats walking the square, as a loop
        r->cat = spawn_npc({.at = {r->center.x + 300, r->center.y + 300, r->center.z}});
        after(1.5, [r, square] {
            UObject* c = r->cat.actor();
            expect("walk.one_point", !walk_path(c, {square.front()}));
            expect("walk.path", walk_path(c, square, {.loop = true, .speed = 100}));
            for (auto& m : detail::mod_paths().all)
                if (m.actor == c) r->path = m.path;
            after(1.0, [r] {
                UObject* c = r->cat.actor();
                value("walk.cat_walking", Json(walking(c)));
                for (const Walker& w : walkers())
                    if (w.actor == c) value("walk.cat_listed", walker_json(w));
                r->last = location(c).value_or(Vec3{});
                // 8 s of it: how far it went, and how far it ever was from the square's middle
                static int ticks = 0;
                ticks = 0;
                static TimerId ticker{};
                ticker = every(0.5, [r] {
                    UObject* c = r->cat.actor();
                    auto at = location(c);
                    if (at)
                    {
                        r->walked += std::hypot(at->x - r->last.x, at->y - r->last.y);
                        r->off_center = std::max(r->off_center, std::hypot(at->x - r->center.x, at->y - r->center.y));
                        r->last = *at;
                    }
                    if (++ticks < 16) return;
                    cancel(ticker);
                    value("walk.walked_8s", Json(r->walked));
                    value("walk.off_center_max", Json(r->off_center));
                    // ----- your cat talks to it: it stops while the talk is up, and walks on after
                    expect("walk.stop", stop_walking(c) && say(L"Brindlemoon", L"Walk with me a while?"));
                    after(0.5, [r] {
                        r->last = location(r->cat.actor()).value_or(Vec3{});
                        after(3.0, [r] {
                            UObject* c = r->cat.actor();
                            value("walk.moved_talking", Json(off(c, r->last)));
                            value("walk.walking_talking", Json(walking(c)));
                            expect("walk.again", hide_talk() && walk_again(c));
                            r->last = location(c).value_or(Vec3{});
                            after(3.0, [r] {
                                UObject* c = r->cat.actor();
                                value("walk.moved_after", Json(off(c, r->last)));
                                value("walk.walking_after", Json(walking(c)));
                                walk_game_cat(r);
                            });
                        });
                    });
                });
            });
        });
    }

    namespace
    {
        // A game cat given a path of the mod's (there and back), then its own back; the mod's cat removed, its path gone.
        auto walk_game_cat(const std::shared_ptr<WalkRun>& r) -> void
        {
            auto finish = [r] {
                r->cat.remove();
                teleport(player(), r->center);
                after(2.5, [r] {   // the keeper looks every 2 s
                    value("walk.path_gone", Json(!r->path || !detail::object_staying(r->path, nullptr)));
                    value("walk.mod_paths_after", Json(static_cast<int>(detail::mod_paths().all.size())));
                    done("ai_walk");
                });
            };
            if (!r->game_cat)
            {
                expect("walk.game_cat", false, "no walking cat of the game's near");
                return finish();
            }
            UObject* g = r->game_cat;
            r->game_had = detail::spline_of(g);
            auto at = *location(g);
            value("walk.game_off", Json(off(g, r->center)));
            // your cat 1,200 units off it first: with your cat 300 units off, the game's cat stood (seen)
            Vec3 by{at.x - 1200, at.y, at.z + 50};
            if (auto gr = ground(by.x, by.y, by.z + 500)) by.z = *gr + 30;
            teleport(player(), by);
            std::vector<Vec3> line{at, Vec3{at.x + 500, at.y, at.z}};
            r->game_speed = get(ai_controller(g), L"DefaultMaxWalkSpeed").number();
            expect("walk.game_path", walk_path(g, line, {.loop = false, .speed = 150}));
            for (const Walker& w : walkers())
                if (w.actor == g) value("walk.game_listed", walker_json(w));
            r->last = at;
            after(4.0, [r, finish] {
                UObject* g = r->game_cat;
                value("walk.game_moved", Json(off(g, r->last)));
                expect("walk.own_path", own_path(g) && detail::spline_of(g) == r->game_had && !own_path(g));
                value("walk.game_speed_back", Json(get(ai_controller(g), L"DefaultMaxWalkSpeed").number() == r->game_speed));
                value("walk.game_walking_own", Json(walking(g)));
                finish();
            });
        }
    } // namespace
} // namespace t
