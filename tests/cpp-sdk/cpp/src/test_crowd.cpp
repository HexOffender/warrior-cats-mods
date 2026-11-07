// Npcs.hpp's many cats, near and far (docs/plans/clan-life.md, S3), on request ("crowd", "crowd_walk"), for
// tests/game/test_cpp_sdk.py. "crowd": a cat with the game's name ids and odd eyes, put to sleep and woken the same cat
// where it was moved to; one 35 m off frozen by the game until its freeze distance takes your cat in, then walking;
// 30 cats made asleep and woken at once, coming in a cat a frame (then three), the frames timed; ready_at where your
// cat stands and off the map. "crowd_walk": 30 cats asleep at two camps, your cat taken from one to the other in
// steps, each cat woken within 40 m of it once its ground is there and put to sleep beyond 60 m; the frames timed, and
// every cat that came in standing on its ground.
#include "checks.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <memory>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        // Frame times, kept while a run wants them.
        struct Frames
        {
            bool on{};
            int count{};
            double max_ms{};
            int slow{};   // over 50 ms
        };
        auto frames() -> Frames&
        {
            static Frames f;
            static bool hooked = false;
            if (!hooked)
            {
                hooked = true;
                every_frame([](float dt) {
                    Frames& fr = frames();
                    if (!fr.on) return;
                    ++fr.count;
                    fr.max_ms = std::max(fr.max_ms, dt * 1000.0);
                    if (dt > 0.05f) ++fr.slow;
                });
            }
            return f;
        }
        auto start_frames() -> void
        {
            Frames fresh;
            fresh.on = true;
            frames() = fresh;
        }
        auto frames_json() -> Json
        {
            Frames& f = frames();
            Json j = Json::object();
            j.set("count", Json(f.count));
            j.set("max_ms", Json(f.max_ms));
            j.set("slow", Json(f.slow));
            return j;
        }
        auto custom(UObject* a, const wchar_t* field) -> Value
        {
            return get(get(a, L"MeshCustomizationComponent").object, std::wstring(L"CustomData.") + field);
        }
        // The parts and slots that make its look, as the game holds them.
        auto look_of(UObject* a) -> Json
        {
            Json j = Json::object();
            for (const wchar_t* f : {L"BodyValue", L"FurValue", L"TailIdx", L"EarIdx", L"EyeValue", L"FaceValue", L"PatternIdx",
                                     L"MarkingIdx", L"FurColorIdx", L"PatternColorIdx", L"MarkingColorIdx", L"EyeLeftColorIdx",
                                     L"EyeRightColorIdx"})
                j.set(text(std::wstring_view(f)), Json(custom(a, f).number(-1)));
            return j;
        }
        auto ahead(double cm, double side = 0) -> Vec3
        {
            auto me = location(player()).value_or(Vec3{});
            auto rot = call_reflected(player(), STR("K2_GetActorRotation"));
            const double yaw = (rot ? get(rot->get(L"ReturnValue"), L"Yaw").number() : 0) * 3.14159265358979 / 180;
            return {me.x + std::cos(yaw) * cm - std::sin(yaw) * side, me.y + std::sin(yaw) * cm + std::cos(yaw) * side, me.z};
        }

        struct CrowdRun
        {
            Npc one, distant;
            std::vector<Npc> many;
            Json looked = Json::object();
            Vec3 moved_to{};
            int woken{};
            int frame_at_wake{};
            Vec3 distant_from{};
        };

        auto finish(const std::shared_ptr<CrowdRun>& r) -> void
        {
            for (Npc& n : r->many) n.remove();
            r->one.remove();
            r->distant.remove();
            set_npc_spawn_budget(1);
            frames().on = false;
            done("crowd");
        }
        // 30 cats asleep, woken at once: a cat a frame (`budget` 1), then three; the frames timed.
        auto wake_many(const std::shared_ptr<CrowdRun>& r, int budget, std::function<void()> then) -> void
        {
            set_npc_spawn_budget(budget);
            value("crowd.budget_" + std::to_string(budget), Json(npc_spawn_budget()));
            r->woken = 0;
            start_frames();
            for (Npc& n : r->many)
                n.wake([r](Npc) { ++r->woken; });
            value("crowd.waiting_" + std::to_string(budget), Json(npcs_waiting()));
            auto waited = std::make_shared<int>(0);
            auto poll = std::make_shared<std::function<void()>>();
            *poll = [r, budget, then, waited, poll] {
                if (r->woken < static_cast<int>(r->many.size()) && ++*waited < 100)
                {
                    after(0.1, *poll);
                    return;
                }
                Json j = frames_json();
                j.set("woken", Json(r->woken));
                int in = 0;
                for (Npc& n : r->many) in += n.actor() != nullptr;
                j.set("in", Json(in));
                value("crowd.wake_" + std::to_string(budget), j);
                frames().on = false;
                then();
            };
            after(0.1, *poll);
        }
        auto many(const std::shared_ptr<CrowdRun>& r) -> void
        {
            // 30 cats asleep round your cat, 6 to 15 m off, on the navigation mesh (a place off it tried further round)
            for (int i = 0, tries = 0; static_cast<int>(r->many.size()) < 30 && tries < 300; ++i, ++tries)
            {
                const double a = i * 0.7, d = 600 + (i % 10) * 100;
                auto at = nav_point(ahead(std::cos(a) * d, std::sin(a) * d), nullptr, 1000);
                if (!at) continue;
                r->many.push_back(spawn_npc({.at = *at, .yaw = i * 12.0, .size = 0.8, .asleep = true}));
            }
            int asleep = 0, out = 0;
            for (Npc& n : r->many)
            {
                asleep += n.asleep();
                out += n.actor() == nullptr;
            }
            value("crowd.made_asleep", Json(asleep));
            value("crowd.made_out", Json(out));
            // a second of frames with nothing coming in, to set them against
            start_frames();
            after(1.0, [r] {
                value("crowd.frames_idle", frames_json());
                wake_many(r, 1, [r] {
                    int slept = 0;
                    for (Npc& n : r->many) slept += n.sleep();
                    value("crowd.slept_many", Json(slept));
                    after(0.5, [r] { wake_many(r, 3, [r] { finish(r); }); });
                });
            });
        }
        // One 35 m off: the game freezes it (your cat outside its 23 m) until its freeze distance takes your cat in.
        auto freeze(const std::shared_ptr<CrowdRun>& r) -> void
        {
            r->distant = spawn_npc({.at = ahead(3500), .size = 0.8});
            after(1.5, [r] {
                value("crowd.far_frozen", Json(r->distant.frozen()));
                value("crowd.far_set", Json(r->distant.set_freeze_beyond(6000)));
                after(0.5, [r] {
                    value("crowd.far_unfrozen", Json(!r->distant.frozen()));
                    r->distant_from = r->distant.place();
                    Vec3 to = r->distant_from;
                    to.y += 300;
                    r->distant.walk_to(to);
                    after(3.0, [r] {
                        auto at = r->distant.place();
                        value("crowd.far_walked", Json(std::hypot(at.x - r->distant_from.x, at.y - r->distant_from.y)));
                        r->distant.remove();
                        many(r);
                    });
                });
            });
        }
        // The same cat, put to sleep and woken where it was moved to.
        auto sleep_wake(const std::shared_ptr<CrowdRun>& r) -> void
        {
            UObject* a = r->one.actor();
            r->looked = look_of(a);
            value("crowd.one_look", r->looked);
            value("crowd.one_prefix", Json(text(custom(a, L"PrefixNameId").string())));
            value("crowd.one_suffix", Json(text(custom(a, L"SuffixNameId").string())));
            const Vec3 was = r->one.place();
            value("crowd.slept", Json(r->one.sleep()));
            value("crowd.asleep", Json(r->one.asleep() && !r->one.actor() && !r->one.waking()));
            const Vec3 kept = r->one.place();
            value("crowd.kept_place", Json(std::hypot(kept.x - was.x, kept.y - was.y)));
            value("crowd.slept_again", Json(r->one.sleep()));
            r->moved_to = {was.x + 100, was.y, was.z};
            value("crowd.moved_asleep", Json(r->one.move_to(r->moved_to)));
            auto woke = std::make_shared<bool>(false);
            value("crowd.wake", Json(r->one.wake([woke](Npc) { *woke = true; })));
            value("crowd.waking", Json(r->one.waking()));
            after(1.0, [r, woke] {
                value("crowd.woke_done", Json(*woke));
                UObject* a = r->one.actor();
                value("crowd.woke_in", Json(a != nullptr && !r->one.asleep()));
                value("crowd.woke_same_look", Json(a && look_of(a).dump() == r->looked.dump()));
                value("crowd.woke_spawns", Json(r->one.spawns()));
                auto at = r->one.place();
                value("crowd.woke_at", Json(std::hypot(at.x - r->moved_to.x, at.y - r->moved_to.y)));
                value("crowd.wake_again", Json(r->one.wake()));
                r->one.remove();
                freeze(r);
            });
        }
    } // namespace

    auto run_crowd_request() -> void
    {
        phase("crowd");
        if (!player())
        {
            done("crowd");
            return;
        }
        auto r = std::make_shared<CrowdRun>();
        // ready_at: where your cat stands, and off the map
        value("crowd.ready_here", Json(ready_at(*location(player()))));
        value("crowd.ready_off_map", Json(ready_at({900000, 900000, -90000})));
        // a place 10 m above your cat: off the navigation mesh's own search, found from the ground below it; and the
        // navigation mesh under it found with a search height
        const Vec3 me = *location(player());
        value("crowd.ready_high", Json(ready_at({me.x, me.y, me.z + 1000})));
        value("crowd.nav_high", Json(!nav_point({me.x, me.y, me.z + 1000}) && nav_point({me.x, me.y, me.z + 1000}, nullptr, 1500)));
        // a cat with the game's name ids and odd eyes
        r->one = spawn_npc({.at = ahead(300), .yaw = 180, .size = 0.9, .prefix = L"STR_CAT_NAME2", .suffix = L"_PAW", .eyes = 3, .eyes2 = 10});
        expect("crowd.spawned", r->one.actor() != nullptr);
        if (!r->one.actor()) return finish(r);
        after(1.0, [r] { sleep_wake(r); });
    }

    namespace
    {
        // ---------------------------------------------------------------- crowd_walk
        struct WalkRun
        {
            Vec3 home{};
            std::vector<Npc> cats;
            std::vector<Vec3> path;
            size_t step{};
            int wakes{}, sleeps{}, fell{}, came{}, waited_max{}, ground_waits{}, skipped{};
            TimerId manager{};
            Json skipped_at = Json::array(), fell_at = Json::array();
        };
        auto walk_finish(const std::shared_ptr<WalkRun>& r) -> void
        {
            cancel(r->manager);
            frames().on = false;
            Json j = frames_json();
            j.set("wakes", Json(r->wakes));
            j.set("sleeps", Json(r->sleeps));
            j.set("came", Json(r->came));
            j.set("fell", Json(r->fell));
            j.set("waited_max", Json(r->waited_max));
            j.set("steps", Json(static_cast<int>(r->step)));
            j.set("ground_waits", Json(r->ground_waits));
            j.set("skipped", Json(r->skipped));
            int asleep_at_end = 0;
            for (Npc& n : r->cats) asleep_at_end += n.asleep();
            j.set("asleep_at_end", Json(asleep_at_end));
            j.set("skipped_at", r->skipped_at);
            j.set("fell_at", r->fell_at);
            // the cats asked to come in that never did: where, and whether their ground was there by the end
            Json waiting = Json::array();
            for (Npc& n : r->cats)
                if (n.waking())
                {
                    const Vec3 at = n.place();
                    Json w = Json::array();
                    for (double x : {at.x, at.y, at.z}) w.push(Json(x));
                    w.push(Json(ready_at(at)));
                    waiting.push(w);
                }
            j.set("never_came", waiting);
            value("crowd_walk.result", j);
            for (Npc& n : r->cats) n.remove();
            teleport(player(), r->home);
            done("crowd_walk");
        }
        // Each quarter second: the cats within 40 m of your cat woken, those beyond 60 m put to sleep.
        auto manage(const std::shared_ptr<WalkRun>& r) -> void
        {
            auto me = location(player());
            if (!me) return;
            r->waited_max = std::max(r->waited_max, npcs_waiting());
            for (Npc& n : r->cats)
            {
                const Vec3 at = n.place();
                const double d = std::hypot(at.x - me->x, at.y - me->y);
                if (d < 4000 && n.asleep())
                {
                    ++r->wakes;
                    const Vec3 nav = at;   // (on the navigation mesh: the cats were put there)
                    n.wake([r, nav](Npc c) {
                        // a second after it comes in, not fallen through: not well under its place on the navigation mesh
                        ++r->came;
                        after(1.0, [r, c, nav] {
                            auto l = c.location();
                            if (l && l->z < nav.z - 150)
                            {
                                ++r->fell;
                                Json f = Json::array();
                                for (double x : {l->x, l->y, l->z, nav.z}) f.push(Json(x));
                                r->fell_at.push(f);
                            }
                        });
                    });
                }
                else if (d > 6000 && n.actor())
                {
                    ++r->sleeps;
                    n.sleep();
                }
            }
        }
        auto walk_step(const std::shared_ptr<WalkRun>& r) -> void
        {
            if (r->step >= r->path.size())
            {
                after(4.0, [r] { walk_finish(r); });
                return;
            }
            const Vec3 to = r->path[r->step];
            // your cat only where its ground is there (it would fall through the coarse stand-in)
            if (!ready_at(to) && ++r->ground_waits % 20 != 0)   // (6 s on, that step's passed by)
            {
                after(0.3, [r] { walk_step(r); });
                return;
            }
            if (!ready_at(to))
            {
                ++r->skipped;
                Json sk = Json::array();
                for (double x : {to.x, to.y, to.z}) sk.push(Json(x));
                r->skipped_at.push(sk);
                ++r->step;
                after(0.1, [r] { walk_step(r); });
                return;
            }
            ++r->step;
            if (auto g = ground(to.x, to.y, to.z + 100)) teleport(player(), {to.x, to.y, *g + 60});
            after(0.4, [r] { walk_step(r); });
        }
    } // namespace

    auto run_crowd_walk_request() -> void
    {
        phase("crowd_walk");
        auto r = std::make_shared<WalkRun>();
        auto me = location(player());
        if (!me || level_name() != L"L_WorldMap_01_P")
        {
            value("crowd_walk.skipped", Json(text(level_name())));
            done("crowd_walk");
            return;
        }
        r->home = *me;
        // ShadowClan's camp and ThunderClan's, 15 cats asleep round each on the navigation mesh
        const Vec3 camps[] = {{-14900, 9000, 1660}, {-19200, 32900, 1300}};
        for (const Vec3& c : camps)
            for (int i = 0; i < 15; ++i)
            {
                const double a = i * 0.9, d = 300 + (i % 5) * 120;
                // (the ground from the sky may be a tree's top or an overhang: the navigation mesh under it, 30 m down)
                Vec3 at{c.x + std::cos(a) * d, c.y + std::sin(a) * d, c.z};
                if (auto g = ground(at.x, at.y, 8000)) at.z = *g;
                auto on = nav_point(at, nullptr, 3000);
                if (!on) continue;
                r->cats.push_back(spawn_npc({.at = *on, .yaw = i * 24.0, .size = 0.8, .asleep = true}));
            }
        // from the one camp to the other, 8 m a step
        const Vec3 a = camps[0], b = camps[1];
        const double length = std::hypot(b.x - a.x, b.y - a.y);
        const int steps = static_cast<int>(length / 800);
        for (int i = 0; i <= steps; ++i)
        {
            const double t = static_cast<double>(i) / steps;
            Vec3 at{a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, 0};
            at.z = ground(at.x, at.y, 8000).value_or(a.z);
            if (auto on = nav_point(at, nullptr, 3000)) r->path.push_back(*on);
        }
        value("crowd_walk.steps_planned", Json(static_cast<int>(r->path.size())));
        value("crowd_walk.cats", Json(static_cast<int>(r->cats.size())));
        start_frames();
        r->manager = every(0.25, [r] { manage(r); });
        walk_step(r);
    }
} // namespace t
