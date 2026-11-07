// World.hpp's places on the navigation mesh (docs/plans/clan-life.md, S4), on request ("nav_paths"), for
// tests/game/test_cpp_sdk.py: 20 random places a cat could walk to round your cat, each with a path from it, each
// walked to by a cat of the mod's own (20 cats, made asleep and woken); a place on the mesh close by with no path to
// it (a patch the mesh doesn't join up with); nothing off the map.
#include "checks.hpp"

#include <algorithm>
#include <cmath>
#include <memory>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        struct NavRun
        {
            Vec3 me{};
            std::vector<Vec3> points;
            std::vector<Npc> cats;
            int arrived{}, ended{};
            std::vector<int> results;
        };
        auto flat(Vec3 a, Vec3 b) -> double { return std::hypot(a.x - b.x, a.y - b.y); }

        auto finish(const std::shared_ptr<NavRun>& r) -> void
        {
            value("nav.arrived", Json(r->arrived));
            value("nav.ended", Json(r->ended));
            // the ones that didn't get there: where to, how far off they ended, how they ended
            Json missed = Json::array();
            for (size_t i = 0; i < r->cats.size(); ++i)
            {
                if (r->results[i] == static_cast<int>(WalkResult::Arrived)) continue;
                const Vec3 at = r->cats[i].place(), to = r->points[i];
                Json m = Json::array();
                for (double x : {to.x, to.y, to.z, flat(at, to), at.z, static_cast<double>(r->results[i])}) m.push(Json(x));
                missed.push(m);
            }
            value("nav.missed", missed);
            for (Npc& n : r->cats) n.remove();
            done("nav_paths");
        }
        // Each cat walks to its place; the walks' ends counted.
        auto walk_all(const std::shared_ptr<NavRun>& r) -> void
        {
            r->results.assign(r->cats.size(), -1);
            for (size_t i = 0; i < r->cats.size(); ++i)
                r->cats[i].walk_to(r->points[i], {}, [r, i](WalkResult w) {
                    ++r->ended;
                    r->results[i] = static_cast<int>(w);
                    if (w == WalkResult::Arrived) ++r->arrived;
                });
            auto waited = std::make_shared<int>(0);
            auto poll = std::make_shared<std::function<void()>>();
            *poll = [r, waited, poll] {
                if (r->ended < static_cast<int>(r->cats.size()) && ++*waited < 60)
                {
                    after(0.5, *poll);
                    return;
                }
                finish(r);
            };
            after(0.5, *poll);
        }
    } // namespace

    auto run_nav_paths_request() -> void
    {
        phase("nav_paths");
        auto here = location(player());
        auto me = here ? nav_point(*here, nullptr, 300) : std::nullopt;
        if (!me)
        {
            done("nav_paths");
            return;
        }
        auto r = std::make_shared<NavRun>();
        r->me = *me;
        // 20 random places within 15 m, each with a whole path from your cat's place, no shorter than the straight line
        Json lengths = Json::array();
        int within = 0, pathed = 0, sane = 0, round = 0;
        // (on the level of your cat's place, within 40 cm up or down: the cats' mesh is made for a cat 25 cm tall taking
        // slopes up to 89 degrees and steps of 35 cm, rock tops and ledges among them, where walking cats manage 45)
        for (int i = 0, tries = 0; static_cast<int>(r->points.size()) < 20 && tries < 200; ++i, ++tries)
        {
            auto p = random_nav_point(r->me, 1500);
            if (!p || std::abs(p->z - r->me.z) > 40) continue;
            r->points.push_back(*p);
            within += flat(*p, r->me) <= 1510;
            auto len = nav_path_length(r->me, *p);
            pathed += len.has_value();
            sane += len && *len >= flat(*p, r->me) - 50;
            round += len && *len > flat(*p, r->me) * 1.3 + 100;   // a way round
            lengths.push(len ? Json(*len) : Json());
        }
        value("nav.points", Json(static_cast<int>(r->points.size())));
        value("nav.within", Json(within));
        value("nav.pathed", Json(pathed));
        value("nav.sane", Json(sane));
        value("nav.round", Json(round));
        value("nav.lengths", lengths);
        // a place on the mesh within 40 m with no path to it: a patch the mesh doesn't join up with, all its own random
        // places close by
        Json cut = Json();
        for (int gx = -4; gx <= 4 && cut.is_null(); ++gx)
            for (int gy = -4; gy <= 4 && cut.is_null(); ++gy)
            {
                auto p = nav_point({r->me.x + gx * 1000, r->me.y + gy * 1000, r->me.z}, nullptr, 3000);
                if (!p || flat(*p, r->me) > 4000 || nav_path_length(r->me, *p)) continue;
                double reach = 0;
                for (int i = 0; i < 12; ++i)
                    if (auto q = random_nav_point(*p, 3000)) reach = std::max(reach, flat(*q, *p));
                cut = Json::object();
                cut.set("distance", Json(flat(*p, r->me)));
                cut.set("reach", Json(reach));
                cut.set("back", Json(nav_path_length(*p, r->me).has_value()));
            }
        value("nav.cut_off", cut);
        // nothing off the map
        value("nav.off_map", Json(!random_nav_point({900000, 900000, -90000}, 1000) && !nav_path_length(r->me, {900000, 900000, -90000})));
        // a cat for each place, made asleep round your cat and woken (a cat a frame), then walked
        for (size_t i = 0; i < r->points.size(); ++i)
        {
            auto at = random_nav_point(r->me, 400);
            r->cats.push_back(spawn_npc({.at = at.value_or(r->me), .yaw = i * 18.0, .size = 0.7, .asleep = true}));
        }
        auto woken = std::make_shared<int>(0);
        for (Npc& n : r->cats) n.wake([woken](Npc) { ++*woken; });
        auto waited = std::make_shared<int>(0);
        auto poll = std::make_shared<std::function<void()>>();
        *poll = [r, woken, waited, poll] {
            if (*woken < static_cast<int>(r->cats.size()) && ++*waited < 40)
            {
                after(0.25, *poll);
                return;
            }
            value("nav.woken", Json(*woken));
            walk_all(r);
        };
        after(0.25, *poll);
    }
} // namespace t
