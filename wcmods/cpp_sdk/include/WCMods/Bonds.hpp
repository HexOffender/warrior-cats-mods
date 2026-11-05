// Bonds.hpp: your cat's bonds, the game's relationship system. Each is a whole number in your cat's slot of the save
// under GameplayProgression/Bonding: one per clan (L"RiverClan": the clan's regard for you) and one per story cat, by
// its narrative role (L"TheMistrustfulLeader"). Read and changed through the game's own bond code (four native
// functions wcmods finds for the installed build: game.NATIVE's Bonding:*), so the game's defaults (a role's
// BaseBonding, the tuning's clan default) and what it does on a change come with them. Game thread only. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods", documents every call.
//
// Not the save manager's reflected GetGameProgressionData and SetGameProgressionData: those work on the account-wide
// part of the save (Shared), not your cat's slot (docs/reverse-engineering.md, "Bonds").
#pragma once

#include <cstdint>
#include <optional>
#include <utility>
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
    // The clans whose bonds the game keeps, as its save names them.
    inline constexpr const wchar_t* BOND_CLANS[] = {L"ThunderClan", L"ShadowClan", L"RiverClan", L"WindClan"};

    namespace detail
    {
        inline constexpr const TCHAR* NARRATIVE_ROLES = STR("/Script/SwtQuest.ENarrativeRole");
        inline constexpr const TCHAR* CLAN_TYPES = STR("/Script/SwtQuest.EClanType");

        // A bond's key as the game's code takes it: a clan (EClanType) or a role (ENarrativeRole), by its value.
        struct BondKey
        {
            bool clan{};
            uint8_t value{};
        };
        // The two enums' names and values, read from the game once (they're fixed for a build).
        inline auto bond_keys() -> const std::vector<std::pair<std::wstring, BondKey>>&
        {
            static std::vector<std::pair<std::wstring, BondKey>> keys;
            if (keys.empty())
            {
                for (auto& [n, v] : enum_names(CLAN_TYPES))
                    for (const wchar_t* c : BOND_CLANS)
                        if (n == c) keys.push_back({n, BondKey{true, static_cast<uint8_t>(v)}});
                for (auto& [n, v] : enum_names(NARRATIVE_ROLES))
                    if (v > 0 && v <= 255) keys.push_back({n, BondKey{false, static_cast<uint8_t>(v)}});
            }
            return keys;
        }
        inline auto bond_key(std::wstring_view key) -> std::optional<BondKey>
        {
            for (auto& [n, k] : bond_keys())
                if (n == key) return k;
            return std::nullopt;
        }

        // The game's functions, each under a structured exception handler: a fault (a game update that changed what
        // one takes, which the pattern check didn't catch) is logged and given back as nullopt or false instead of
        // closing the game. Nothing here may need unwinding (MSVC's __try rule).
        inline auto call_get_personal(void* fn, uint8_t role, int32_t& out) -> bool
        {
            __try
            {
                out = reinterpret_cast<int32_t (*)(uint8_t, int32_t)>(fn)(role, -1);
                return true;
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
                return false;
            }
        }
        inline auto call_get_clan(void* fn, uint8_t clan, int32_t& out) -> bool
        {
            __try
            {
                out = reinterpret_cast<int32_t (*)(uint8_t)>(fn)(clan);
                return true;
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
                return false;
            }
        }
        inline auto call_add(void* fn, uint8_t key, int32_t amount) -> bool
        {
            __try
            {
                reinterpret_cast<void (*)(uint8_t, int32_t)>(fn)(key, amount);
                return true;
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
                return false;
            }
        }
    } // namespace detail

    // A bond's value now, as the game reads it: a clan's (L"RiverClan") or a story cat's by its role
    // (L"TheMistrustfulLeader"); one never changed reads as the game's default for it (the role's BaseBonding, the
    // tuning's Gameplay.Progression.Bonding.Clan.Default, 67). nullopt for a key that's neither, in menus (no cat), or
    // when wcmods hasn't got the game's function on this build.
    inline auto bond(std::wstring_view key) -> std::optional<int>
    {
        if (!assert_game_thread(L"bond") || !player()) return std::nullopt;
        auto k = detail::bond_key(key);
        if (!k) return std::nullopt;
        void* fn = native_address(k->clan ? L"Bonding:GetClan" : L"Bonding:GetPersonal");
        int32_t v = 0;
        if (!fn) return std::nullopt;
        bool ok = k->clan ? detail::call_get_clan(fn, k->value, v) : detail::call_get_personal(fn, k->value, v);
        if (!ok)
        {
            log(L"the game's bond read failed for {}", key);
            return std::nullopt;
        }
        return v;
    }
    // Add to a bond (a negative amount takes away), through the game's own AddPersonalBonding or AddClanScore. Kept
    // in your cat's slot from the game's next save on. False as for bond().
    inline auto add_bond(std::wstring_view key, int amount) -> bool
    {
        if (!assert_game_thread(L"add_bond") || !player()) return false;
        auto k = detail::bond_key(key);
        if (!k) return false;
        void* fn = native_address(k->clan ? L"Bonding:AddClan" : L"Bonding:AddPersonal");
        if (!fn) return false;
        if (amount == 0) return true;
        if (detail::call_add(fn, k->value, amount)) return true;
        log(L"the game's bond change failed for {}", key);
        return false;
    }
    // Set a bond to a value from 0 to 100: what add_bond adds, from what bond() reads. False, with nothing changed, for
    // a value outside those (the game keeps a bond within them), or as for bond().
    inline auto set_bond(std::wstring_view key, int value) -> bool
    {
        if (value < 0 || value > 100) return false;
        auto now = bond(key);
        if (!now) return false;
        if (*now == value) return true;
        if (!add_bond(key, value - *now)) return false;
        auto after = bond(key);
        return after && *after == value;
    }

    // The ranks the game gives a story cat's bond (EBondingRanks), by the tuning's thresholds
    // (Gameplay.Progression.Bonding.Personal.*: Neutral 10, Friendly 28, Friend 46, CloseBond 73 in the game's own).
    enum class BondRank { Unfriendly, Neutral, Friendly, Friend, CloseBond };
    // A clan's regard (EBondingTypes), by Gameplay.Progression.Bonding.Clan.Negative (33) and .Positive (67).
    enum class ClanBond { Neutral, Positive, Negative };

    // The thresholds, read from the tuning now (a mod may change them while the game runs: Tables.hpp).
    struct BondThresholds
    {
        float neutral{10}, friendly{28}, friend_{46}, close{73}, clan_negative{33}, clan_positive{67};
    };
    inline auto bond_thresholds() -> BondThresholds
    {
        BondThresholds t;
        auto at = [](const wchar_t* key, float& into) {
            if (auto v = tuning(key)) into = *v;
        };
        at(L"Gameplay.Progression.Bonding.Personal.Neutral", t.neutral);
        at(L"Gameplay.Progression.Bonding.Personal.Friendly", t.friendly);
        at(L"Gameplay.Progression.Bonding.Personal.Friend", t.friend_);
        at(L"Gameplay.Progression.Bonding.Personal.CloseBond", t.close);
        at(L"Gameplay.Progression.Bonding.Clan.Negative", t.clan_negative);
        at(L"Gameplay.Progression.Bonding.Clan.Positive", t.clan_positive);
        return t;
    }
    inline auto bond_rank(int value, const BondThresholds& t) -> BondRank
    {
        if (value >= t.close) return BondRank::CloseBond;
        if (value >= t.friend_) return BondRank::Friend;
        if (value >= t.friendly) return BondRank::Friendly;
        if (value >= t.neutral) return BondRank::Neutral;
        return BondRank::Unfriendly;
    }
    inline auto clan_bond(int value, const BondThresholds& t) -> ClanBond
    {
        if (value >= t.clan_positive) return ClanBond::Positive;
        if (value <= t.clan_negative) return ClanBond::Negative;
        return ClanBond::Neutral;
    }
    inline auto bond_rank(int value) -> BondRank { return bond_rank(value, bond_thresholds()); }
    inline auto clan_bond(int value) -> ClanBond { return clan_bond(value, bond_thresholds()); }
    inline auto bond_rank_name(BondRank r) -> const wchar_t*
    {
        static const wchar_t* names[] = {L"Unfriendly", L"Neutral", L"Friendly", L"Friend", L"CloseBond"};
        return names[static_cast<int>(r)];
    }
    inline auto clan_bond_name(ClanBond c) -> const wchar_t*
    {
        static const wchar_t* names[] = {L"Neutral", L"Positive", L"Negative"};
        return names[static_cast<int>(c)];
    }

    // The story cats' roles (ENarrativeRole, without None): L"TheStarvingWarrior", L"ThunderClanDeputy"...
    inline auto bond_roles() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        for (auto& [n, k] : detail::bond_keys())
            if (!k.clan) out.push_back(n);
        return out;
    }
    struct Bond
    {
        std::wstring key;        // L"RiverClan", L"TheMistrustfulLeader"
        bool clan{};             // a clan's bond, or a story cat's
        int value{};
        std::wstring rank;       // a cat's BondRank name, or a clan's ClanBond name
        int base{};              // a story cat's bond before any change (its role's BaseBonding)
        std::wstring giver_role; // which of your clan's cats plays the role (EGiverRole: L"Warrior", L"Elder"...)
        int giver_index{};       // and which of them (from 1; 0 for the one of its kind)
        std::wstring cat_name;   // an iconic cat's own name ("Firestar"); the others' come from the clan's cats
    };
    namespace detail
    {
        // The story roles the game set up for this game (the NPC generation manager's NarrativeRoleMap: your clan's
        // roles, each with its BaseBonding and the camp cat that plays it), by role name.
        inline auto story_roles() -> std::vector<Bond>
        {
            std::vector<Bond> out;
            for (auto& [clan, list] : map_entries(manager(STR("npcs")), L"NarrativeRoleMap"))
                for (auto& r : elements(get(list, L"Roles")))
                {
                    Bond b;
                    b.key = get(r, L"narrativeRole").string();
                    if (b.key.empty() || b.key == L"None") continue;
                    b.base = static_cast<int>(get(r, L"BaseBonding").number());
                    b.giver_role = get(r, L"NPCRole").string();
                    b.giver_index = static_cast<int>(get(r, L"NPCIndex").number());
                    if (get(r, L"bIconic").boolean())
                        if (auto name = words(get(r, L"IconicName").string())) b.cat_name = *name;
                    out.push_back(std::move(b));
                }
            return out;
        }
    } // namespace detail
    // Your cat's bonds: the four clans', then each story role the game set up in this game (your clan's), as bond()
    // reads them. Empty in menus.
    inline auto bonds() -> std::vector<Bond>
    {
        std::vector<Bond> out;
        if (!assert_game_thread(L"bonds") || !player()) return out;
        const BondThresholds t = bond_thresholds();
        for (const wchar_t* c : BOND_CLANS)
            if (auto v = bond(c))
            {
                Bond b;
                b.key = c;
                b.clan = true;
                b.value = *v;
                b.rank = clan_bond_name(clan_bond(*v, t));
                out.push_back(std::move(b));
            }
        for (Bond& b : detail::story_roles())
            if (auto v = bond(b.key))
            {
                b.value = *v;
                b.rank = bond_rank_name(bond_rank(*v, t));
                out.push_back(std::move(b));
            }
        return out;
    }
} // namespace wcmods
