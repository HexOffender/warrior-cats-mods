// Day.hpp: the day (docs/plans/clan-life.md, S7). The game has a clock (Game.hpp's time_of_day, day_seconds and
// set_time) that runs 72 times real time as it ships, so a day lasts 20 minutes; it wraps at midnight and stops while
// the game is paused (the inventory). Nothing in the game follows it: the sky follows the area your cat is in. This
// adds the parts of the day as the Warriors books name them, calls as each part begins and as a new day starts, the
// day's length, and a sky that follows the clock (dusk, night and dawn over each area's own sky).
//
//   wcmods::on_day_part([](wcmods::DayPart p) { if (p == wcmods::DayPart::Dawn) send_the_dawn_patrol(); });
//   wcmods::on_new_day([] { ++moons_days; });
//   wcmods::set_day_length(40 * 60);   // a day of 40 minutes
//   wcmods::day_sky(true);             // dark at night
#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/Tables.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // ============================================================================================ the parts of the day
    // As the books name them: dawn (patrols go out), morning, sunhigh, afternoon, sundown, night.
    enum class DayPart
    {
        Dawn,
        Morning,
        Sunhigh,
        Afternoon,
        Sundown,
        Night,
    };
    constexpr std::array<DayPart, 6> day_parts_in_order{DayPart::Dawn, DayPart::Morning, DayPart::Sunhigh,
                                                        DayPart::Afternoon, DayPart::Sundown, DayPart::Night};
    constexpr auto day_part_name(DayPart p) -> std::wstring_view
    {
        switch (p)
        {
        case DayPart::Dawn: return L"dawn";
        case DayPart::Morning: return L"morning";
        case DayPart::Sunhigh: return L"sunhigh";
        case DayPart::Afternoon: return L"afternoon";
        case DayPart::Sundown: return L"sundown";
        case DayPart::Night: return L"night";
        }
        return L"";
    }

    // When each part begins, in seconds into the day (the game's clock: 0 at midnight, 21600 at 6:00).
    struct DayParts
    {
        int dawn = 5 * 3600, morning = 7 * 3600, sunhigh = 11 * 3600, afternoon = 14 * 3600, sundown = 18 * 3600,
            night = 21 * 3600;
        constexpr auto start(DayPart p) const -> int
        {
            switch (p)
            {
            case DayPart::Dawn: return dawn;
            case DayPart::Morning: return morning;
            case DayPart::Sunhigh: return sunhigh;
            case DayPart::Afternoon: return afternoon;
            case DayPart::Sundown: return sundown;
            case DayPart::Night: return night;
            }
            return 0;
        }
        // Each after the one before, within the day.
        constexpr auto valid() const -> bool
        {
            return 0 <= dawn && dawn < morning && morning < sunhigh && sunhigh < afternoon && afternoon < sundown &&
                   sundown < night && night < 86400;
        }
    };
    namespace detail
    {
        inline auto parts_now() -> DayParts&
        {
            static DayParts p;
            return p;
        }
        // Seconds into the day, whatever the number (a clock set past midnight or before it).
        inline auto in_day(double seconds) -> double
        {
            const double s = std::fmod(seconds, 86400.0);
            return s < 0 ? s + 86400.0 : s;
        }
    } // namespace detail
    // This mod's parts of the day (each mod has its own), and changing them; false for parts out of order.
    inline auto day_parts() -> DayParts { return detail::parts_now(); }
    inline auto set_day_parts(const DayParts& parts) -> bool
    {
        if (!parts.valid()) return false;
        detail::parts_now() = parts;
        return true;
    }

    // The part of the day at a time (seconds into the day), and now (nullopt outside the forest).
    inline auto day_part_at(double seconds, const DayParts& parts) -> DayPart
    {
        const double s = detail::in_day(seconds);
        if (s >= parts.night || s < parts.dawn) return DayPart::Night;
        if (s >= parts.sundown) return DayPart::Sundown;
        if (s >= parts.afternoon) return DayPart::Afternoon;
        if (s >= parts.sunhigh) return DayPart::Sunhigh;
        if (s >= parts.morning) return DayPart::Morning;
        return DayPart::Dawn;
    }
    inline auto day_part_at(double seconds) -> DayPart { return day_part_at(seconds, day_parts()); }
    inline auto day_part() -> std::optional<DayPart>
    {
        float* s = day_seconds();
        if (!s) return std::nullopt;
        return day_part_at(*s);
    }

    // How dark the clock says it is: 0 by day, 1 by night. Over the dusk (the second half of sundown) it goes from 0
    // to 1 and over the dawn (dawn to morning) back to 0, easing in and out, so there's no step at either end.
    inline auto night_amount(double seconds, const DayParts& parts) -> double
    {
        const double s = detail::in_day(seconds);
        auto ease = [](double x) {
            x = std::clamp(x, 0.0, 1.0);
            return x * x * (3 - 2 * x);
        };
        const double dusk = parts.sundown + (parts.night - parts.sundown) / 2.0;
        if (s >= parts.night || s < parts.dawn) return 1;
        if (s >= dusk) return ease((s - dusk) / (parts.night - dusk));
        if (s < parts.morning) return 1 - ease((s - parts.dawn) / static_cast<double>(parts.morning - parts.dawn));
        return 0;
    }
    inline auto night_amount(double seconds) -> double { return night_amount(seconds, day_parts()); }

    // ============================================================================================ the day's length
    // The clock's speed (game seconds a real second: 72 as the game ships), to read and write. The game copies it from
    // its tuning (Gameplay.Exploration.DayNight.ClockSpeed) into its game state as the world starts, and that copy is
    // what the clock runs by. nullptr outside the forest, or when wcmods hasn't got it on this build.
    inline auto clock_speed() -> float*
    {
        return member<float>(game_state(), L"/Script/SwtAdventure.SwtAdventureGameplayGameState", L"WCM_ClockSpeed");
    }
    // How long a day lasts, in real seconds (1200 as the game ships), or nullopt outside the forest.
    inline auto day_length() -> std::optional<double>
    {
        float* speed = clock_speed();
        if (!speed || *speed <= 0) return std::nullopt;
        return 86400.0 / *speed;
    }

    // ============================================================================================ the sky by the clock
    // The sky that follows the clock (day_sky): each area's own sky as the game has it by day, going toward `night`
    // (one of the sky's presets) over the dusk, as far as `darkest` (0 to 1) at night, and back over the dawn.
    struct DaySky
    {
        std::wstring night = L"Night";
        double darkest = 1.0;
    };

    namespace detail
    {
        // The presets the game picks by area (the ones day_sky darkens), and the sky's post-process volume for each
        // preset it has one for: the volume at full weight is the preset showing.
        constexpr std::array<const wchar_t*, 6> area_skies{L"NeutralDay", L"ThunderClan", L"RiverClan", L"ShadowClan", L"WindClan", L"MoonPool"};
        constexpr std::array<std::pair<const wchar_t*, const wchar_t*>, 9> sky_volumes{{
            {L"PostProcess-neutralday", L"NeutralDay"},
            {L"PostProcess-ThunderClan", L"ThunderClan"},
            {L"PostProcess-RiverClan", L"RiverClan"},
            {L"PostProcess-ShadowClan", L"ShadowClan"},
            {L"PostProcess-WindClan", L"WindClan"},
            {L"PostProcess-MoonPool", L"MoonPool"},
            {L"PostProcess-night", L"Night"},
            {L"PostProcess-MainMenu", L"MainMenu"},
            {L"PostProcess-CatCreator", L"CatCreator"},
        }};
        inline auto is_area_sky(std::wstring_view preset) -> bool
        {
            for (const wchar_t* a : area_skies)
                if (preset == a) return true;
            return false;
        }
        inline auto sky_shown_in(UObject* sky_actor) -> std::optional<std::wstring>
        {
            if (!sky_actor) return std::nullopt;
            std::optional<std::wstring> shown;
            for (auto [volume, preset] : sky_volumes)
            {
                UObject* v = get(sky_actor, volume).object;
                if (!v || !get(v, L"bEnabled").boolean()) continue;
                const double weight = get(v, L"BlendWeight").number();
                if (weight <= 0.001) continue;
                if (weight < 0.999 || shown) return std::nullopt;   // two at once: going from one to the other
                shown = preset;
            }
            return shown;
        }

        // The numbers in a sky preset's row (WrcSkyBoxStruct: floats, and colours' parts), as offsets in the row.
        struct SkyNumber
        {
            ptrdiff_t at{};
            bool is_float{true};   // else a double
        };
        inline auto sky_numbers_of(RC::Unreal::UStruct* type, uint8_t* base, uint8_t* row, std::vector<SkyNumber>& out) -> void
        {
            using namespace RC::Unreal;
            for (FProperty* p : properties_in_chain(type))
            {
                const std::wstring kind = property_type(p);
                uint8_t* at = p->ContainerPtrToValuePtr<uint8_t>(base);
                if (kind == L"FloatProperty") out.push_back({at - row, true});
                else if (kind == L"DoubleProperty") out.push_back({at - row, false});
                else if (kind == L"StructProperty")
                    if (UScriptStruct* inner = static_cast<FStructProperty*>(p)->GetStruct()) sky_numbers_of(inner, at, row, out);
            }
        }
        inline auto read_number(const uint8_t* row, const SkyNumber& n) -> double
        {
            return n.is_float ? *reinterpret_cast<const float*>(row + n.at) : *reinterpret_cast<const double*>(row + n.at);
        }
        inline auto write_number(uint8_t* row, const SkyNumber& n, double v) -> void
        {
            if (n.is_float) *reinterpret_cast<float*>(row + n.at) = static_cast<float>(v);
            else *reinterpret_cast<double*>(row + n.at) = v;
        }

        struct DayState
        {
            std::mutex lock;   // the calls lists and the options (a mod may set them from any thread)
            bool started{};
            std::vector<std::shared_ptr<std::function<void(DayPart)>>> on_part;
            std::vector<std::shared_ptr<std::function<void()>>> on_day;
            std::optional<DayPart> last_part;
            std::optional<double> last_seconds;
            // the day's length set_day_length keeps (real seconds), and the game state it was last put on
            std::optional<double> length;
            // the sky
            bool sky_on{};
            DaySky sky_options;
            UObject* sky{};
            RC::Unreal::UClass* sky_class{};
            std::chrono::steady_clock::time_point sky_looked{};
            std::vector<SkyNumber> numbers;
            std::map<std::wstring, std::vector<double>> was;   // each preset's numbers as the game had them, in `sky`
            double applied{-1};                                 // the night amount the presets were last set to
            std::optional<std::wstring> shown;                  // what the sky showed then
        };
        inline auto day_state() -> DayState&
        {
            static DayState d;
            return d;
        }

        // The game's own numbers back into each preset this changed, in the sky it changed them in.
        inline auto restore_day_sky(DayState& d) -> void
        {
            if (d.sky && !d.was.empty() && object_alive(d.sky, d.sky_class))
                for (auto& [preset, numbers] : d.was)
                    if (uint8_t* row = sky_copy_in(d.sky, preset))
                        for (size_t i = 0; i < numbers.size() && i < d.numbers.size(); ++i) write_number(row, d.numbers[i], numbers[i]);
            d.was.clear();
            d.applied = -1;
        }
        // Each area's preset `amount` of the way to the night's, and the one showing put on again so it shows now
        // (not while it's going from one to another, while another of the game's is up, or while set_sky holds one:
        // that puts its preset on every frame anyway).
        inline auto set_night_amount(DayState& d, double amount, const std::optional<std::wstring>& shown) -> void
        {
            const auto night = d.was.find(d.sky_options.night);
            if (night == d.was.end()) return;
            for (auto& [preset, numbers] : d.was)
            {
                if (preset == d.sky_options.night) continue;
                uint8_t* row = sky_copy_in(d.sky, preset);
                if (!row) continue;
                for (size_t i = 0; i < numbers.size() && i < d.numbers.size(); ++i)
                    write_number(row, d.numbers[i], numbers[i] + (night->second[i] - numbers[i]) * amount);
            }
            d.applied = amount;
            bool held;
            {
                auto& h = sky_hold();
                std::lock_guard lock(h.lock);
                held = h.timer != 0;
            }
            if (shown && is_area_sky(*shown) && !held) apply_sky(d.sky, *shown);
        }
        // The sky found (again, after a new level), and its presets' numbers kept as the game has them (again after
        // they were put back: day_sky off, or another night).
        inline auto find_day_sky(DayState& d) -> bool
        {
            using namespace std::chrono;
            if (!d.sky || !object_alive(d.sky, d.sky_class))
            {
                d.sky = nullptr;
                d.was.clear();
                d.applied = -1;
                d.shown.reset();
                if (steady_clock::now() - d.sky_looked < seconds(2)) return false;   // sky() looks through every object
                d.sky_looked = steady_clock::now();
                UObject* s = sky();
                if (!s) return false;
                d.sky = s;
                d.sky_class = s->GetClassPrivate();
            }
            if (!d.was.empty()) return true;
            if (d.numbers.empty())
            {
                auto* type = static_cast<RC::Unreal::UStruct*>(object(STR("/Script/Wrc.WrcSkyBoxStruct")));
                uint8_t* row = sky_copy_in(d.sky, d.sky_options.night);
                if (!type || !row) return false;
                sky_numbers_of(type, row, row, d.numbers);
            }
            std::vector<std::wstring> presets{d.sky_options.night};
            for (const wchar_t* a : area_skies) presets.emplace_back(a);
            for (const std::wstring& preset : presets)
            {
                const uint8_t* row = sky_copy_in(d.sky, preset);
                if (!row || d.was.contains(preset)) continue;
                auto& kept = d.was[preset];
                for (const SkyNumber& n : d.numbers) kept.push_back(read_number(row, n));
            }
            d.applied = -1;
            return d.was.contains(d.sky_options.night);
        }
        inline auto day_sky_tick(DayState& d, double seconds) -> void
        {
            if (!find_day_sky(d)) return;
            const double amount = night_amount(seconds) * std::clamp(d.sky_options.darkest, 0.0, 1.0);
            const auto shown = sky_shown_in(d.sky);
            if (std::abs(amount - d.applied) < 0.002 && shown == d.shown) return;
            set_night_amount(d, amount, shown);
            d.shown = shown;
        }

        // Four times a second, once anything here is asked for: the parts' and days' calls, the day's length kept,
        // the sky.
        inline auto day_tick() -> void
        {
            auto& d = day_state();
            float* clock = day_seconds();
            if (!clock || !player())
            {
                d.last_part.reset();
                d.last_seconds.reset();
                return;
            }
            const double now = *clock;
            std::optional<double> length;
            bool sky_on;
            std::vector<std::shared_ptr<std::function<void(DayPart)>>> on_part;
            std::vector<std::shared_ptr<std::function<void()>>> on_day;
            {
                std::lock_guard lock(d.lock);
                length = d.length;
                sky_on = d.sky_on;
                on_part = d.on_part;
                on_day = d.on_day;
            }
            // the length kept: the game sets its speed again from its tuning as each world starts
            if (length)
                if (float* speed = clock_speed())
                {
                    const float want = static_cast<float>(86400.0 / *length);
                    if (std::abs(*speed - want) > 1e-4f) *speed = want;
                }
            // a new day: the clock went past midnight (it's half a day or more lower than it was: a clock set back a
            // few hours isn't one, a clock set from the evening to the next morning is)
            if (d.last_seconds && *d.last_seconds - now >= 43200)
                for (auto& fn : on_day) guarded(L"on_new_day", [&] { (*fn)(); });
            d.last_seconds = now;
            const DayPart part = day_part_at(now);
            if (d.last_part && *d.last_part != part)
                for (auto& fn : on_part) guarded(L"on_day_part", [&] { (*fn)(part); });
            d.last_part = part;
            if (sky_on) day_sky_tick(d, now);
        }
        inline auto start_day() -> void
        {
            auto& d = day_state();
            {
                std::lock_guard lock(d.lock);
                if (d.started) return;
                d.started = true;
            }
            every(0.25, [] { guarded(L"the day", day_tick); });
        }
        // As the mod is taken out: the sky's presets and the clock's speed as the game had them.
        inline auto stop_day() -> void
        {
            auto& d = day_state();
            restore_day_sky(d);
            if (d.length)
                if (float* speed = clock_speed())
                    *speed = tuning(L"Gameplay.Exploration.DayNight.ClockSpeed").value_or(72.0f);
        }
    } // namespace detail

    // `fn(part)` on the game thread as each part of the day begins while you play: the clock running into it, or set
    // into it (set_time). Not as your cat comes into the world: day_part() says where the day is then.
    inline auto on_day_part(std::function<void(DayPart)> fn) -> void
    {
        auto& d = detail::day_state();
        {
            std::lock_guard lock(d.lock);
            d.on_part.push_back(std::make_shared<std::function<void(DayPart)>>(std::move(fn)));
        }
        detail::start_day();
    }
    // `fn()` on the game thread as a new day starts while you play: the clock running past midnight, or set from one
    // day into the next (from the evening to the morning). Setting it back a few hours isn't a new day.
    inline auto on_new_day(std::function<void()> fn) -> void
    {
        auto& d = detail::day_state();
        {
            std::lock_guard lock(d.lock);
            d.on_day.push_back(std::make_shared<std::function<void()>>(std::move(fn)));
        }
        detail::start_day();
    }

    // Make a day last `real_seconds` (1200, 20 minutes, as the game ships), from now on while the mod runs, put on
    // again as each world starts (the game sets its own speed then). nullopt gives the game's own back. False for a
    // day shorter than a minute or longer than a real day.
    inline auto set_day_length(std::optional<double> real_seconds) -> bool
    {
        if (real_seconds && (*real_seconds < 60 || *real_seconds > 86400)) return false;
        auto& d = detail::day_state();
        bool was_set;
        {
            std::lock_guard lock(d.lock);
            was_set = d.length.has_value();
            d.length = real_seconds;
        }
        detail::start_day();
        if (float* speed = clock_speed())
        {
            if (real_seconds) *speed = static_cast<float>(86400.0 / *real_seconds);
            else if (was_set) *speed = tuning(L"Gameplay.Exploration.DayNight.ClockSpeed").value_or(72.0f);
        }
        return true;
    }

    // The preset the sky shows now (L"ShadowClan", L"NeutralDay", L"Night", L"MainMenu" while the inventory is up...),
    // by its post-process volumes; nullopt while it goes from one to another, or without the sky.
    inline auto sky_shown() -> std::optional<std::wstring> { return detail::sky_shown_in(sky()); }

    // The sky follows the clock: by day each area's own sky as the game has it, then over the dusk it goes toward
    // `options.night` (as far as `options.darkest`), stays there through the night, and comes back over the dawn. It
    // works on the areas' presets' numbers (sky_values), so the game's own fades between areas, and its skies for the
    // inventory, dens and fights, stay as they are; a preset set_sky holds shows its numbers too. False for a darkest
    // outside 0 to 1. Off (`on` false) puts the game's numbers back.
    inline auto day_sky(bool on, DaySky options = {}) -> bool
    {
        if (options.darkest < 0 || options.darkest > 1) return false;
        if (!assert_game_thread(L"day_sky")) return false;
        auto& d = detail::day_state();
        {
            std::lock_guard lock(d.lock);
            const bool night_changed = options.night != d.sky_options.night;
            // the game's numbers back (kept again with the new night's on the next tick)
            if (!on || night_changed) detail::restore_day_sky(d);
            d.sky_on = on;
            d.sky_options = std::move(options);
            d.applied = -1;
        }
        if (!on)
        {
            // shown at once
            UObject* s = d.sky && detail::object_alive(d.sky, d.sky_class) ? d.sky : sky();
            if (auto shown = detail::sky_shown_in(s); shown && detail::is_area_sky(*shown)) detail::apply_sky(s, *shown);
            return true;
        }
        detail::start_day();
        return true;
    }
    inline auto day_sky_on() -> bool
    {
        auto& d = detail::day_state();
        std::lock_guard lock(d.lock);
        return d.sky_on;
    }
} // namespace wcmods
