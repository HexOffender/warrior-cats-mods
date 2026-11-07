// Day.hpp in the game (docs/plans/clan-life.md, S7), on request, for tests/game/test_cpp_sdk.py:
// - "day": the parts of the day and how dark each time is (plain numbers), the calls as parts begin and new days
//   start with the clock set from one time to another, and the day's length (the clock's speed measured);
// - "day_sky_noon", "day_sky_dusk", "day_sky_night", "day_sky_dawn", "day_sky_half", "day_sky_read", "day_sky_off",
//   "day_sky_again":
//   the clock held at a time with the sky following it, and what the sky shows then (the Python side takes a picture
//   of each).
#include "checks.hpp"

#include <chrono>
#include <cmath>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        auto now_s() -> double
        {
            using namespace std::chrono;
            return duration<double>(steady_clock::now().time_since_epoch()).count();
        }
        struct Seen
        {
            Json parts = Json::array();
            int new_days{};
        };
        auto seen() -> Seen&
        {
            static Seen s;
            return s;
        }
        auto listen() -> void
        {
            static bool listening = false;
            if (listening) return;
            listening = true;
            on_day_part([](DayPart p) { seen().parts.push(Json(utf8(day_part_name(p)))); });
            on_new_day([] { ++seen().new_days; });
        }
        auto last_part() -> std::string
        {
            const Json& p = seen().parts;
            return p.size() ? p[p.size() - 1].string() : "";
        }

        // Plain numbers: the parts at their edges, how dark each time is.
        auto check_parts() -> void
        {
            using P = DayPart;
            struct At
            {
                int h, m, s;
                P part;
            };
            bool all = true;
            for (At a : {At{4, 59, 59, P::Night}, At{5, 0, 0, P::Dawn}, At{6, 59, 59, P::Dawn}, At{7, 0, 0, P::Morning},
                         At{11, 0, 0, P::Sunhigh}, At{14, 0, 0, P::Afternoon}, At{18, 0, 0, P::Sundown}, At{20, 59, 0, P::Sundown},
                         At{21, 0, 0, P::Night}, At{0, 0, 0, P::Night}})
                all = all && day_part_at(a.h * 3600 + a.m * 60 + a.s) == a.part;
            expect("parts_at", all);
            expect("parts_wrap", day_part_at(-60) == P::Night && day_part_at(86400 + 5 * 3600) == P::Dawn);
            // dark by night, light by day, half way in the middle of the dusk and the dawn, never a step
            const double h = 3600;
            Json amounts = Json::object();
            for (double at : {12 * h, 19.5 * h, 20.25 * h, 21 * h, 23 * h, 3 * h, 5 * h, 6 * h, 7 * h})
                amounts.set(std::to_string(at / h), Json(night_amount(at)));
            value("day.amounts", amounts);
            double biggest_step = 0, prev = night_amount(0);
            for (int s = 1; s <= 86400; s += 10)
            {
                const double a = night_amount(s);
                biggest_step = std::max(biggest_step, std::abs(a - prev));
                prev = a;
            }
            value("day.biggest_step", Json(biggest_step));
            DayParts odd;
            odd.morning = odd.dawn;   // not after dawn
            expect("parts_out_of_order", !set_day_parts(odd));
            DayParts early;
            early.dawn = 4 * 3600;
            const bool set = set_day_parts(early);
            expect("parts_set", set && day_part_at(4 * 3600 + 60) == P::Dawn && day_parts().dawn == 4 * 3600);
            set_day_parts({});
        }

        auto measure_rate(std::function<void(double)> then) -> void
        {
            float* s = day_seconds();
            if (!s) return then(-1);
            const double t0 = now_s(), s0 = *s;
            after(1.5, [t0, s0, then] {
                float* s = day_seconds();
                then(s ? (*s - s0) / (now_s() - t0) : -1);
            });
        }

        // What the sky shows: its light and fog, the preset it shows, how dark the clock says, the presets' numbers.
        auto sky_now() -> Json
        {
            Json j = Json::object();
            UObject* s = sky();
            UObject* light = get(s, L"DirectionalLight").object;
            UObject* fog = get(s, L"ExponentialHeightFog").object;
            j.set("light", Json(light ? get(light, L"Intensity").number(-1) : -1));
            j.set("fog", Json(fog ? get(fog, L"FogDensity").number(-1) : -1));
            auto shown = sky_shown();
            j.set("shown", Json(shown ? utf8(*shown) : ""));
            float* clock = day_seconds();
            j.set("clock", Json(clock ? *clock : -1));
            j.set("amount", Json(clock ? night_amount(*clock) : -1));
            j.set("area_sun", Json(get(sky_values(L"ShadowClan"), L"SunIntensity").number(-1)));
            j.set("area_fog", Json(get(sky_values(L"ShadowClan"), L"FogDensity").number(-1)));
            j.set("night_sun", Json(get(sky_values(L"Night"), L"SunIntensity").number(-1)));
            j.set("night_fog", Json(get(sky_values(L"Night"), L"FogDensity").number(-1)));
            j.set("on", Json(day_sky_on()));
            return j;
        }
    } // namespace

    auto run_day_request() -> void
    {
        phase("day");
        hold_time(std::nullopt);
        check_parts();
        float* speed = clock_speed();
        value("day.speed", Json(speed ? *speed : -1));
        float* clock = day_seconds();
        expect("part_now", clock && day_part() == day_part_at(*clock));
        listen();
        seen() = {};
        // the clock run into dawn: dawn begins
        set_time(4, 59, 0);
        after(1.5, [] {
            value("day.into_dawn", seen().parts);
            expect("into_dawn", last_part() == "dawn", last_part());
            // the clock run past midnight: a new day
            set_time(23, 59, 0);
            after(1.5, [] {
                value("day.past_midnight", Json(seen().new_days));
                // set forward within the day (to the morning): the part, no new day
                set_time(10, 0);
                after(0.6, [] {
                    value("day.to_morning", Json(last_part()));
                    // set back a few hours: not a new day
                    set_time(3, 0);
                    after(0.6, [] {
                        value("day.set_back", Json(seen().new_days));
                        // from the evening to the next morning: a new day
                        set_time(22, 0);
                        after(0.6, [] {
                            set_time(6, 0);
                            after(0.6, [] {
                                value("day.next_morning", Json(seen().new_days));
                                value("day.next_morning_part", Json(last_part()));
                                value("day.parts", seen().parts);
                                // the day's length
                                value("day.length_game", Json(day_length().value_or(-1)));
                                measure_rate([](double before) {
                                    value("day.rate_game", Json(before));
                                    value("day.length_too_short", Json(set_day_length(30)));
                                    value("day.length_set", Json(set_day_length(120)));
                                    value("day.length_now", Json(day_length().value_or(-1)));
                                    measure_rate([](double fast) {
                                        value("day.rate_fast", Json(fast));
                                        set_day_length(std::nullopt);
                                        value("day.length_back", Json(day_length().value_or(-1)));
                                        measure_rate([](double back) {
                                            value("day.rate_back", Json(back));
                                            done("day");
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

    auto run_day_sky_request(const std::string& what) -> void
    {
        phase(what);
        const std::string name = what.substr(std::string("day_sky_").size());
        auto at = [](double hours) { hold_time(static_cast<int>(hours * 3600)); };
        if (name == "noon")
        {
            at(12);
            expect("on", day_sky(true));
            expect("bad_darkest", !day_sky(true, {.darkest = 1.5}));
        }
        else if (name == "dusk") at(20.25);
        else if (name == "night") at(23);
        else if (name == "dawn") at(6);
        else if (name == "half")
        {
            at(23);
            day_sky(true, {.darkest = 0.5});
        }
        else if (name == "off") day_sky(false);
        else if (name == "again")   // on again after off
        {
            at(23);
            day_sky(true);
        }
        // (read: as it is.) A second for the sky to follow, longer while it's going from one preset to another (the
        // game's own fade into the area's sky after a load, about 5 s)
        auto waited = std::make_shared<int>(0);
        auto read = std::make_shared<std::function<void()>>();
        *read = [what, name, waited, read] {
            if (name != "read" && !sky_shown() && ++*waited < 20)
            {
                after(0.5, *read);
                return;
            }
            value("day_sky." + name, sky_now());
            if (name == "off" || name == "half") hold_time(std::nullopt);
            if (name == "half") day_sky(true);   // back to the whole night for the next
            done(what);
        };
        after(1.0, *read);
    }
} // namespace t
