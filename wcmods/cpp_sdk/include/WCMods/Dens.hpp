// Dens.hpp: the clans' dens and what's built in them. Each clan's camp has den doors (WrcHousingDoorActor); a door
// leads to its den, a room the map keeps off to the side (its DestinationComponent is where you come in), and in the
// den are hotspots (SwtAdventureHousingHotspot), places a decoration can be built: a tag (Gameplay.Den.Hotspot.7,
// Gameplay.Den.Hotspot.Personal.1...), a size and the rank whose den it is. Each clan has its own copy of the dens and
// hotspots, with the same tags. A decoration is built through the hotspot's own OnOptionPicked, as the game's build
// screen does, and taken off with its OnDelete: the game shows it and writes it to your cat's slot of the save
// (Housing/Houses/<hotspot tag>: Status, DecorationTag, StartTime), which the next save writes to the file. Game
// thread only. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call.
//
// The game keeps a hotspot's state only in the save's data (docs/reverse-engineering.md, "Dens"): what's built shows
// live, from the hotspot's decoration mesh; whether a build is under way, and since when, is read from the save file,
// as of its last save.
#pragma once

#include <cmath>
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/Tables.hpp>
#include <WCMods/Words.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // ============================================================================================ decorations
    // A decoration the dens can have (DB_Den_Decorations, 60 rows): its tag (Gameplay.Inventory.Decoration.12), its
    // name as the game shows it (STR_ITEM_DECORATION_12), and the model it's built as: a static mesh, or a skeletal
    // one with the animation it plays. What one costs, how long it takes and its size are HousingCost.csv's, which the
    // game keeps in its tuning manager, not in a table (docs/mechanics/clan-life.md lists them).
    struct Decoration
    {
        std::wstring tag, name, mesh, skeletal, animation;
    };
    inline auto decorations() -> std::vector<Decoration>
    {
        std::vector<Decoration> out;
        if (!assert_game_thread(L"decorations")) return out;
        for (auto& [row_name, row] : table(L"DB_Den_Decorations").rows())
        {
            Decoration d;
            d.tag = get(row, L"DecorationTag.TagName").string();
            d.mesh = name(get(row, L"Mesh").object);
            d.skeletal = name(get(row, L"Skeletal").object);
            d.animation = name(get(row, L"AnimSequence").object);
            const auto dot = d.tag.rfind(L'.');
            if (dot != std::wstring::npos) d.name = words(L"STR_ITEM_DECORATION_" + d.tag.substr(dot + 1)).value_or(L"");
            out.push_back(std::move(d));
        }
        return out;
    }

    // ============================================================================================ dens
    // A den: the door into it from the camp (its actor), its clan, the rank whose den it is for a rank's own den
    // (L"Apprentice", L"Warrior", L"Deputy", L"Leader"; empty for the clan's shared dens), and where you come in
    // inside it. A clan's rank dens share one door (BP_Housing_MultiRank_DoorActor), which takes your cat to its
    // rank's: each is a Den of its own here.
    struct Den
    {
        UObject* door{};
        std::wstring clan, rank;
        Vec3 inside{};
    };
    namespace detail
    {
        inline auto component_location(UObject* component) -> std::optional<Vec3>
        {
            auto r = component ? call_reflected(component, STR("K2_GetComponentLocation")) : std::nullopt;
            if (!r) return std::nullopt;
            Value v = r->get(L"ReturnValue");
            return Vec3{get(v, L"X").number(), get(v, L"Y").number(), get(v, L"Z").number()};
        }
        inline auto live(UObject* o) -> bool { return o && full_name(o).find(L"Default__") == std::wstring::npos; }
    } // namespace detail
    // Every clan's dens, or one clan's (L"ShadowClan"). Empty outside the forest.
    inline auto dens(std::wstring_view clan = {}) -> std::vector<Den>
    {
        std::vector<Den> out;
        if (!assert_game_thread(L"dens")) return out;
        for (UObject* d : find_all(STR("WrcHousingDoorActor")))
        {
            if (!detail::live(d) || get(d, L"bIsExit").boolean()) continue;
            const std::wstring c = get(d, L"Clan").string();
            if (!clan.empty() && c != clan) continue;
            const bool multi = name(d->GetClassPrivate()).find(L"MultiRank") != std::wstring::npos;
            // A multi-rank door's DestinationComponent is the apprentices' den (its hotspots are theirs, seen in game).
            const std::pair<const wchar_t*, const wchar_t*> ways[] = {{L"DestinationComponent", multi ? L"Apprentice" : L""},
                                                                    {L"WarriorDestinationComponent", L"Warrior"},
                                                                    {L"DeputyDestinationComponent", L"Deputy"},
                                                                    {L"LeaderDestinationComponent", L"Leader"}};
            for (auto& [member, rank] : ways)
            {
                if (!multi && std::wstring_view(member) != L"DestinationComponent") continue;
                auto at = detail::component_location(get(d, member).object);
                if (!at || (at->x == 0 && at->y == 0 && at->z == 0)) continue;   // a door left in a scene's level
                out.push_back(Den{d, c, rank, *at});
            }
        }
        return out;
    }
    // Take your cat into a den: put where its door brings you in. False outside the world.
    inline auto enter_den(const Den& den) -> bool
    {
        if (!assert_game_thread(L"enter_den") || !player() || !den.door) return false;
        return teleport(player(), {den.inside.x, den.inside.y, den.inside.z + 30});
    }

    // ============================================================================================ hotspots
    // A place in a den a decoration can be built on: its actor, tag, size (EAdventureHousingDecorationSize: L"Tiny",
    // L"Pendant", L"Medium", L"Large", L"Interactable") and the rank whose den it's in; the decoration built on it now
    // (its tag, read from the hotspot's model; empty for none); and, from your cat's slot of the save as of its last
    // save, its status (EAdventureHousingHotspotStatus: 0 None, 1 InProgress, 2 ReadyToAdd, 3 Built), the decoration
    // the save names and when its build started (Unix seconds, 0 for none). Each clan's den has the same tags: the
    // save's entry is your cat's clan's.
    struct Hotspot
    {
        UObject* actor{};
        std::wstring tag, size, rank, decoration;
        int saved_status{};
        std::wstring saved_decoration;
        int64_t started{};
    };
    namespace detail
    {
        inline auto hotspot_decoration(UObject* h, const std::map<std::wstring, std::wstring>& by_model) -> std::wstring
        {
            for (auto [component, member] : {std::pair{L"DecorationComponent", L"StaticMesh"},
                                             std::pair{L"DecorationSkeletalComponent", L"SkeletalMeshAsset"}})
            {
                UObject* c = get(h, component).object;
                auto shown = c ? call_reflected(c, STR("IsVisible")) : std::nullopt;
                if (!shown || !shown->get(L"ReturnValue").boolean()) continue;
                auto it = by_model.find(name(get(c, member).object));
                if (it != by_model.end()) return it->second;
            }
            return L"";
        }
        inline auto decoration_models() -> std::map<std::wstring, std::wstring>
        {
            std::map<std::wstring, std::wstring> by_model;
            for (auto& d : decorations())
            {
                if (!d.mesh.empty()) by_model.emplace(d.mesh, d.tag);
                if (!d.skeletal.empty()) by_model.emplace(d.skeletal, d.tag);
            }
            return by_model;
        }
        inline auto read_hotspot(UObject* h, const std::map<std::wstring, std::wstring>& by_model, const Json& houses) -> Hotspot
        {
            Hotspot s;
            s.actor = h;
            s.tag = get(h, L"UniqueHotspotTag.TagName").string();
            s.size = get(h, L"HotspotSize").string();
            s.rank = get(h, L"RequiredRank").string();
            s.decoration = hotspot_decoration(h, by_model);
            const Json& e = houses[utf8(s.tag)];
            s.saved_status = static_cast<int>(e["Status"].number());
            std::wstring saved = e["DecorationTag"].wstring();
            s.saved_decoration = saved == L"None" ? L"" : saved;
            s.started = static_cast<int64_t>(e["StartTime"].number());
            return s;
        }
    } // namespace detail
    // The hotspots of a den, or every den's with no den given. A hotspot is the den's whose way in is nearest it (the
    // rank dens sit side by side, 6 m apart), within 15 m.
    inline auto hotspots(const Den* den = nullptr) -> std::vector<Hotspot>
    {
        std::vector<Hotspot> out;
        if (!assert_game_thread(L"hotspots")) return out;
        const auto by_model = detail::decoration_models();
        const Json slot = slot_data();
        const Json& houses = slot["Housing"]["Houses"];
        const std::vector<Den> all = den ? dens() : std::vector<Den>{};
        auto flat = [](const Vec3& a, const Vec3& b) { return std::hypot(a.x - b.x, a.y - b.y); };
        for (UObject* h : find_all(STR("SwtAdventureHousingHotspot")))
        {
            if (!detail::live(h)) continue;
            if (den)
            {
                auto at = location(h);
                if (!at) continue;
                const double mine = flat(*at, den->inside);
                if (mine > 1500) continue;
                bool nearer = false;
                for (const Den& other : all)
                    if (flat(*at, other.inside) < mine - 1) nearer = true;
                if (nearer) continue;
            }
            out.push_back(detail::read_hotspot(h, by_model, houses));
        }
        return out;
    }
    // One hotspot, read now (as hotspots() reads them).
    inline auto hotspot(UObject* actor) -> std::optional<Hotspot>
    {
        if (!assert_game_thread(L"hotspot") || !actor || !is_a(actor, STR("/Script/SwtAdventure.SwtAdventureHousingHotspot")))
            return std::nullopt;
        const Json slot = slot_data();
        return detail::read_hotspot(actor, detail::decoration_models(), slot["Housing"]["Houses"]);
    }

    namespace detail
    {
        inline auto known_decoration(std::wstring_view tag) -> bool
        {
            for (auto& d : decorations())
                if (d.tag == tag) return true;
            return false;
        }
        inline auto pick_option(UObject* hotspot, std::wstring_view decoration, int seconds) -> bool
        {
            if (!hotspot || !is_a(hotspot, STR("/Script/SwtAdventure.SwtAdventureHousingHotspot")) || !known_decoration(decoration))
                return false;
            return call_reflected(hotspot, STR("OnOptionPicked"), [&](Params& p) {
                       set(p.nth(0), L"TagName", decoration);
                       set(p.nth(1), L"BuildTime", seconds);   // the rest of the cost left empty: nothing is paid
                       p.set_nth(2, Value::of(seconds <= 0));    // bReadyToGo: built at once
                   }).has_value();
        }
    } // namespace detail
    // Build a decoration (its tag, one of decorations()) on a hotspot at once, nothing paid, as the game's build
    // screen does (the hotspot's OnOptionPicked): it shows, and your cat's slot says Built. Whatever was on the hotspot
    // is replaced. False for a hotspot or decoration the game hasn't got. The size isn't checked.
    inline auto place_decoration(UObject* hotspot, std::wstring_view decoration) -> bool
    {
        return assert_game_thread(L"place_decoration") && detail::pick_option(hotspot, decoration, 0);
    }
    // Start building a decoration that takes `seconds` of real time, as a build the game times (InProgress, its start
    // time in the save); it shows once that time has passed. Nothing is paid. False as place_decoration, or for no time.
    inline auto build_decoration(UObject* hotspot, std::wstring_view decoration, int seconds) -> bool
    {
        return assert_game_thread(L"build_decoration") && seconds > 0 && detail::pick_option(hotspot, decoration, seconds);
    }
    // Take the decoration off a hotspot, as the game's build screen does (its OnDelete): nothing shows, and your cat's
    // slot says None. False for a hotspot the game hasn't got.
    inline auto remove_decoration(UObject* hotspot) -> bool
    {
        if (!assert_game_thread(L"remove_decoration") || !hotspot || !is_a(hotspot, STR("/Script/SwtAdventure.SwtAdventureHousingHotspot")))
            return false;
        return call_reflected(hotspot, STR("OnDelete")).has_value();
    }
} // namespace wcmods
