// The HUD's quest pieces, map markers, the clock held, places and travel, the camera (Map.hpp), on request ("map",
// then "map_end"), for tests/game/test_cpp_sdk.py. "map" leaves two markers up for the test's picture of the minimap;
// "map_end" takes them off and lets the clock go.
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
        std::vector<MapMarker> markers;
        auto flat(Vec3 a, Vec3 b) -> double { return std::hypot(a.x - b.x, a.y - b.y); }
    } // namespace

    auto run_map_request() -> void
    {
        phase("map");
        // ----- refused
        expect("map.refused", !map_marker(static_cast<UObject*>(nullptr)) && !travel(Place{}));
        // ----- the objective panel and a banner
        HudObjective spec;
        spec.title = L"WCMods Test";
        spec.location = L"Sandbox";
        spec.activity = L"Find moss";
        spec.goals = {{L"Moss", L"1/2", L"", false}, {L"Feather", L"2/2", L"", true}};
        expect("map.objective", hud_objective(spec));
        expect("map.banner", hud_banner(Banner::Begin, {.kind = L"Side Quest", .title = L"A Mod's Quest", .text = L"New Objective", .seconds = 3.0}));
        // ----- the clock held a little after 6:00
        expect("map.hold", hold_time(6 * 3600 + 5));
        // ----- markers: at a place by your cat, and on your cat
        auto home = location(player());
        if (!home) return done("map");
        const int before = map_marker_count();
        markers.clear();
        markers.push_back(map_marker(Vec3{home->x + 800, home->y, home->z}, L"search"));
        markers.push_back(map_marker(player(), L"talk"));
        value("map.markers_before", before);
        value("map.markers_made", static_cast<int>(markers[0].valid()) + static_cast<int>(markers[1].valid()));
        value("map.markers_after", map_marker_count());
        expect("map.marker_moved", markers[0].move_to(Vec3{home->x + 1000, home->y + 200, home->z}));
        value("map.marker_at", location(markers[0].actor) ? Json(flat(*location(markers[0].actor), {home->x + 1000, home->y + 200, 0})) : Json());
        // ----- the camera
        if (auto c = camera())
        {
            value("map.camera.distance", Json(c->distance));
            value("map.camera.fov", Json(c->fov));
        }
        // ----- places, and a travel back to your cat's camp from 60 m off
        auto all = places();
        value("map.places", static_cast<int>(all.size()));
        Json open = Json::array();
        const Place* camp = nullptr;
        const Place* locked = nullptr;
        for (auto& p : all)
        {
            if (p.unlocked) open.push(Json(text(p.tag + L" " + p.zone)));
            if (p.unlocked && p.tag == L"Gameplay.Checkpoints.Shadowclan.0") camp = &p;
            if (!p.unlocked && !locked) locked = &p;
        }
        value("map.unlocked", open);
        expect("map.locked_refused", locked && !travel(*locked));
        if (!camp) return done("map");
        const Place target = *camp;
        const Vec3 back = *home;
        teleport(player(), {home->x - 6000, home->y, home->z + 200});
        after(1.0, [target, back] {
            if (auto b = hud_banner_shown(Banner::Begin))
            {
                Json words = Json::object();
                for (auto& [n, w] : *b) words.set(utf8(n), Json(text(w)));
                value("map.banner.words", words);
            }
            auto away = location(player());
            value("map.away_from_camp", away ? Json(flat(*away, target.at)) : Json());
            expect("map.travel", travel(target));
            after(1.5, [target, back] {
                auto at = location(player());
                value("map.at_camp", at ? Json(flat(*at, target.at)) : Json());
                if (auto s = day_seconds()) value("map.time_held", Json(static_cast<double>(*s)));
                value("map.time_held_is", time_held() ? Json(*time_held()) : Json());
                // The HUD's pieces, read back.
                if (auto o = hud_objective_shown())
                {
                    value("map.objective.title", Json(text(o->title)));
                    value("map.objective.activity", Json(text(o->activity)));
                    value("map.objective.location", Json(text(o->location)));
                    Json goals = Json::array();
                    for (auto& g : o->goals) goals.push(Json(text(g.name + L" " + g.progress + (g.done ? L" done" : L""))));
                    value("map.objective.goals", goals);
                }
                teleport(player(), back);
                after(1.5, [] {
                    value("map.banner_gone", !hud_banner_shown(Banner::Begin));
                    expect("map.objective_hidden", hide_objective());
                    after(1.0, [] {
                        value("map.objective_gone", !hud_objective_shown());
                        done("map");
                    });
                });
            });
        });
    }

    auto run_map_end_request() -> void
    {
        phase("map_end");
        const int before = map_marker_count();
        for (auto& m : markers) m.remove();
        value("map_end.removed", before - map_marker_count());
        value("map_end.still_valid", static_cast<int>(markers.size() >= 2 && (markers[0].valid() || markers[1].valid())));
        markers.clear();
        expect("map_end.release", hold_time(std::nullopt) && !time_held());
        done("map_end");
    }

    namespace
    {
        auto settings_json(const CameraSettings& s) -> Json
        {
            Json o = Json::object();
            auto put = [&](const char* name, const std::optional<double>& v) { o.set(name, v ? Json(*v) : Json()); };
            put("distance", s.distance);
            put("fov", s.fov);
            put("pitch", s.pitch);
            put("speed_distance", s.speed_distance);
            put("speed_fov", s.speed_fov);
            put("lag", s.lag);
            put("rotation_lag", s.rotation_lag);
            put("turn_yaw", s.turn_yaw);
            put("turn_pitch", s.turn_pitch);
            put("pitch_min", s.pitch_min);
            put("pitch_max", s.pitch_max);
            return o;
        }
        // What shows: the camera's distance and field of view (camera()), the arm's length, the lens's pitch, and the
        // arm's lag as the arm has it.
        auto shown(const char* key) -> void
        {
            Json o = Json::object();
            if (auto c = camera())
            {
                o.set("distance", Json(c->distance));
                o.set("fov", Json(c->fov));
                UObject* arm = get(c->actor, L"AdventureArmComponent").object;
                UObject* lens = get(c->actor, L"CameraComponent").object;
                o.set("arm", Json(get(arm, L"TargetArmLength").number()));
                o.set("lag_on", Json(get(arm, L"bEnableCameraLag").boolean()));
                o.set("lag_speed", Json(get(arm, L"CameraLagSpeed").number()));
                // How far above your cat the lens is, as an angle: a tilt down raises it.
                auto me = location(player());
                auto r = call_reflected(lens, STR("K2_GetComponentLocation"));
                if (me && r && c->distance > 0)
                {
                    const double dz = get(r->get(L"ReturnValue"), L"Z").number() - me->z;
                    o.set("elevation", Json(std::asin(std::clamp(dz / c->distance, -1.0, 1.0)) * 180.0 / 3.14159265358979));
                }
            }
            value(key, o);
        }
    } // namespace

    auto run_camera_request() -> void
    {
        phase("camera");
        auto before = camera_settings();
        expect("camera.read", before.has_value());
        if (!before) return done("camera");
        value("camera.before", settings_json(*before));
        shown("camera.shown_before");
        expect("camera.set", set_camera({.distance = 300, .fov = 60, .pitch = -35, .lag = 0, .turn_yaw = 110, .pitch_max = 60}));
        after(2.0, [] {
            shown("camera.shown_set");
            if (auto s = camera_settings()) value("camera.set_read", settings_json(*s));
            // A second set keeps the first's "before": reset puts back the game's, not this.
            expect("camera.set_again", set_camera({.speed_fov = 0}));
            expect("camera.reset", reset_camera());
            after(2.0, [] {
                shown("camera.shown_reset");
                if (auto s = camera_settings()) value("camera.reset_read", settings_json(*s));
                expect("camera.reset_again", reset_camera());   // nothing to put back: true
                done("camera");
            });
        });
    }
} // namespace t
