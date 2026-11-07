// CatTables.hpp: the game's tables for making clan cats, and the colours of the cat maker's colour slots, for a mod
// that makes cats of its own the game's way (docs/plans/clan-life.md, S6). The tables are the game's NonAsset/NPC
// CSVs as wcmods' install leaves them, name mods' changes in (wcmods/npctables.py writes them as
// Mods/shared/WCModsGame/npc_tables.json); the colours are the GUI manager's, palette mods' changes in. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <map>
#include <string>
#include <utility>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>

namespace wcmods
{
    // A name prefix ("Ash", its words' key "STR_CAT_NAME17") and how often each clan's cats get it (by the clans'
    // names: ThunderClan, RiverClan, ShadowClan, WindClan, OutOfClans); a suffix ("pelt", "_PELT") and how often each
    // role gets it (Kit, Apprentice, Warrior, Deputy, Leader, MedicineCat, Queen, Elder, RogueCat, RogueCatLeader,
    // StarClanAncestor). A cat's name is its prefix's words then its suffix's (cat_name).
    struct CatNamePart
    {
        std::wstring word, id;
        std::map<std::wstring, double> weights;
    };
    struct CatScarChances
    {
        std::wstring role, group;   // the role, and whose ("All")
        double ear{}, body{}, eye{};
    };
    struct CatTables
    {
        std::vector<CatNamePart> prefixes, suffixes;
        std::vector<std::wstring> banned;                                    // whole names the game never gives
        std::vector<std::pair<std::wstring, std::wstring>> rogues;           // a rogue's whole name, its words' key
        // Each look part's weights per clan, by option from 0 (0: never): body, face, ears, eyes, tail, whiskers, fur,
        // pattern, marking (the cat maker's parts) and coat, pattern_colour, marking_colour, eye_colour, eye_colour2
        // (its colour slots)
        std::map<std::wstring, std::map<std::wstring, std::vector<double>>> looks;
        std::vector<int> banned_patterns;                                    // patterns the game keeps off its cats
        std::map<std::wstring, std::vector<int>> kit_parts;                  // the options a kit may have, by part
        std::map<std::wstring, std::pair<double, double>> sizes;             // each role's size range (its scale)
        std::vector<CatScarChances> scars;
        // How many of each role each clan's game makes: <clan's table> -> role -> clan -> how many
        std::map<std::wstring, std::map<std::wstring, std::map<std::wstring, int>>> generators;
        double odd_eyes{0.15};                                               // the chance of two eye colours
        std::vector<std::wstring> missing;                                   // tables the game hadn't got
        explicit operator bool() const { return !prefixes.empty(); }
    };

    namespace detail
    {
        inline auto read_cat_tables() -> CatTables
        {
            CatTables t;
            auto text = read_file(mod().installed.parent_path() / L"shared" / L"WCModsGame" / L"npc_tables.json");
            auto parsed = text ? Json::parse(*text) : std::nullopt;
            if (!parsed || !parsed->is_object())
            {
                log_line(mod().name, L"Mods/shared/WCModsGame/npc_tables.json isn't there; install again with wcmods");
                return t;
            }
            const Json& j = *parsed;
            auto weights = [](const Json& w) {
                std::map<std::wstring, double> out;
                for (size_t i = 0; i < w.keys().size(); ++i) out[wide(w.keys()[i])] = w.values()[i].number(0);
                return out;
            };
            auto ints = [](const Json& a) {
                std::vector<int> out;
                for (const Json& v : a.values()) out.push_back(static_cast<int>(v.number(0)));
                return out;
            };
            for (const Json& p : j["prefixes"].values()) t.prefixes.push_back({wide(p["word"].string()), wide(p["id"].string()), weights(p["weights"])});
            for (const Json& s : j["suffixes"].values()) t.suffixes.push_back({wide(s["word"].string()), wide(s["id"].string()), weights(s["weights"])});
            for (const Json& b : j["banned"].values()) t.banned.push_back(wide(b["name"].string()));
            for (const Json& r : j["rogues"].values()) t.rogues.emplace_back(wide(r["word"].string()), wide(r["id"].string()));
            const Json& looks = j["looks"];
            for (size_t i = 0; i < looks.keys().size(); ++i)
            {
                const Json& by_clan = looks.values()[i];
                auto& part = t.looks[wide(looks.keys()[i])];
                for (size_t k = 0; k < by_clan.keys().size(); ++k)
                    for (const Json& w : by_clan.values()[k].values()) part[wide(by_clan.keys()[k])].push_back(w.number(0));
            }
            t.banned_patterns = ints(j["banned_patterns"]);
            const Json& kit = j["kit_parts"];
            for (size_t i = 0; i < kit.keys().size(); ++i) t.kit_parts[wide(kit.keys()[i])] = ints(kit.values()[i]);
            const Json& sizes = j["sizes"];
            for (size_t i = 0; i < sizes.keys().size(); ++i)
                t.sizes[wide(sizes.keys()[i])] = {sizes.values()[i][0].number(0), sizes.values()[i][1].number(0)};
            for (const Json& s : j["scars"].values())
                t.scars.push_back({wide(s["role"].string()), wide(s["group"].string()), s["ear"].number(0), s["body"].number(0), s["eye"].number(0)});
            const Json& gens = j["generators"];
            for (size_t i = 0; i < gens.keys().size(); ++i)
            {
                const Json& roles = gens.values()[i];
                auto& table = t.generators[wide(gens.keys()[i])];
                for (size_t r = 0; r < roles.keys().size(); ++r)
                {
                    const Json& clans = roles.values()[r];
                    for (size_t c = 0; c < clans.keys().size(); ++c)
                        table[wide(roles.keys()[r])][wide(clans.keys()[c])] = static_cast<int>(clans.values()[c].number(0));
                }
            }
            t.odd_eyes = j["odd_eyes"].number(0.15);
            for (const Json& m : j["missing"].values()) t.missing.push_back(wide(m.string()));
            return t;
        }
    } // namespace detail

    // The game's tables for making clan cats, read once (any thread); empty (false) without the file.
    inline auto cat_tables() -> const CatTables&
    {
        static const CatTables t = detail::read_cat_tables();
        return t;
    }

    // A colour slot's colour, 0 to 255 a channel, as the game stores it.
    struct SlotColour
    {
        int r{}, g{}, b{};
    };
    // The cat maker's colour slots as the game has them now (palette mods' changes in), by slot number from 0: the
    // coats (a look's FurColorIdx, the "coat" weights), pattern colours (Pattern01ColorIdx), marking colours
    // (Pattern02ColorIdx) and eyes (EyeLeftColorIdx, EyeRightColorIdx). From the GUI manager's FurColors,
    // PatternMaskColors, MarkingMaskColors and IrisColors; empty without the manager. Game thread only.
    struct ColourSlots
    {
        std::vector<SlotColour> coats, patterns, markings, eyes;
    };
    inline auto colour_slots() -> ColourSlots
    {
        ColourSlots out;
        if (!assert_game_thread(L"colour_slots")) return out;
        UObject* gui = manager(STR("gui"));
        if (!gui) return out;
        auto read = [&](const wchar_t* member, std::vector<SlotColour>& into) {
            for (const Value& c : elements(get(gui, member)))
                into.push_back({static_cast<int>(get(c, L"R").number()), static_cast<int>(get(c, L"G").number()),
                                static_cast<int>(get(c, L"B").number())});
        };
        read(L"FurColors", out.coats);
        read(L"PatternMaskColors", out.patterns);
        read(L"MarkingMaskColors", out.markings);
        read(L"IrisColors", out.eyes);
        return out;
    }
} // namespace wcmods
