// Bonds.hpp: your cat's bonds, the game's relationship system. Each is a whole number in your cat's slot of the save
// under GameplayProgression/Bonding: one per clan (L"RiverClan": the clan's regard for you) and one per story cat, by
// its narrative role (L"TheMistrustfulLeader"). Read and changed through the game's own bond code (native functions
// wcmods finds for the installed build: game.NATIVE's Bonding:*), so the game's defaults (a role's BaseBonding, the
// tuning's clan default) and what it does on a change come with them. And a bond talk's answers: the rows of the game's
// talk tables, and what the game does with an answer (answer_bond). Game thread only. WCMods.hpp includes it;
// docs/SDK.md, "C++ mods", documents every call.
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

    // ============================================================================================ a talk's answers
    // A row of the game's talk tables, StoryDialogues.csv (the story talks) and QuestDialogues.csv (the quests'), as its
    // tuning manager loads them, by row name (L"Gameplay.Dialogue.Story.Short.TheMistrustfulLeader.Main.7.Right.1.Short"):
    // a line's words and who says them, and for a bond talk's answer what it does to your bonds.
    struct TalkRow
    {
        std::wstring name;
        int score{};               // an answer's: to the bond with the cat talked to
        int clan_bonding{};        // and to your clan's regard
        std::wstring talker;       // who says it: L"NPC" (the cat talked to) or L"Player" (your cat)
        int trait{};               // ECharacterTrait the answer speaks for (0 None, 1 Brave, 2 Ambitious, 3 Wise, 4 Energetic, 5 Curious, 6 Patient)
        std::wstring string_key;   // its words' key in the game's strings (L"QST_Story.Short.TheMistrustfulLeader.Main.7.Right.1.Short")
        std::wstring debug_text;   // the words the game shows when the key has none
        std::wstring voice;        // its voice-over event
        // The words as the game shows them: the key's, else the row's DebugText.
        auto text() const -> std::wstring
        {
            if (!string_key.empty())
                if (auto w = words(string_key); w && !w->empty()) return *w;
            return debug_text;
        }
    };
    namespace detail
    {
        // The tuning manager's two maps (TMap<FString, FSwtQuestStoryDialoguesStruct>, docs/reverse-engineering.md,
        // "A bond talk's answer"): 0x60-byte slots, the row's name, then the row (its reflected struct) from +0x10,
        // then the hash's links.
        inline auto talk_rows_map(bool story) -> const uint8_t*
        {
            return member<uint8_t>(manager(STR("tuning")), L"/Script/SwtQuest.SwtQuestTuningManager",
                                   story ? L"WCM_StoryDialogues" : L"WCM_QuestDialogues");
        }
        inline auto talk_row_at(const uint8_t* slot) -> TalkRow
        {
            TalkRow r;
            r.name = fstring_at(slot);
            Value row = struct_at(STR("/Script/SwtQuest.SwtQuestStoryDialoguesStruct"), const_cast<uint8_t*>(slot) + 0x10);
            r.score = static_cast<int>(get(row, L"Score").number());
            r.clan_bonding = static_cast<int>(get(row, L"ClanBonding").number());
            r.talker = get(row, L"Talker").string();
            r.trait = static_cast<int>(get(row, L"Trait").number());
            r.voice = get(row, L"VoiceOver").string();
            r.string_key = get(row, L"StringKey").string();
            r.debug_text = get(row, L"DebugText").string();
            return r;
        }
        // Each slot of both maps (the story table's first, as the game looks), with `pick` deciding by its name.
        template <typename Pick>
        auto talk_slots(Pick&& pick) -> std::vector<const uint8_t*>
        {
            std::vector<const uint8_t*> out;
            for (bool story : {true, false})
            {
                std::vector<const uint8_t*> slots;
                if (!set_slots(talk_rows_map(story), 0x60, slots)) continue;
                for (const uint8_t* e : slots)
                {
                    const auto* text = *reinterpret_cast<const wchar_t* const*>(e);
                    const int32_t num = *reinterpret_cast<const int32_t*>(e + 8);
                    if (text && num > 0 && pick(std::wstring_view(text, static_cast<size_t>(num - 1)))) out.push_back(e);
                }
            }
            return out;
        }
        inline auto starts_with_key(std::wstring_view name, std::wstring_view prefix) -> bool
        {
            return name.size() >= prefix.size() && same_key(name.substr(0, prefix.size()), prefix);
        }
    } // namespace detail
    // One row by its name (the game's names ignore case), from the story table, else the quest one, as the game's
    // bond answer looks. nullopt when neither has it, or when wcmods hasn't got the tables on this build.
    inline auto talk_row(std::wstring_view name) -> std::optional<TalkRow>
    {
        if (!assert_game_thread(L"talk_row")) return std::nullopt;
        auto found = detail::talk_slots([&](std::wstring_view n) { return detail::same_key(n, name); });
        if (found.empty()) return std::nullopt;
        return detail::talk_row_at(found.front());
    }
    // Every row whose name starts with `prefix` (a story talk's tag and a dot: L"Gameplay.Dialogue.Story.Short.
    // TheMistrustfulLeader.Main.7."), in no particular order.
    inline auto talk_rows(std::wstring_view prefix) -> std::vector<TalkRow>
    {
        std::vector<TalkRow> out;
        if (!assert_game_thread(L"talk_rows")) return out;
        for (const uint8_t* e : detail::talk_slots([&](std::wstring_view n) { return detail::starts_with_key(n, prefix); }))
            out.push_back(detail::talk_row_at(e));
        return out;
    }

    // What the game's bond answer did, as answer_bond() did it.
    struct BondAnswer
    {
        std::wstring node;      // the answer's row name: your cat's Bonding/Nodes keeps it once answered
        int trait{};            // the trait it speaks for (its row's)
        int bonus{};            // Gameplay.Progression.Bonding.TraitModifier (1) when your cat has that trait, else 0
        bool first{};           // the node wasn't answered before: it's marked now, and the cat's bond moved
        std::wstring role;      // the story cat whose bond moved (its narrative role); empty when none did
        int personal{};         // what its bond got: Score + bonus (0 when none moved)
        std::wstring clan;      // your clan, whose regard moved
        int clan_change{};      // what it got: ClanBonding + bonus
    };
    namespace detail
    {
        inline auto call_has_node(void* fn, const void* key, bool& out) -> bool
        {
            __try
            {
                out = reinterpret_cast<bool (*)(const void*)>(fn)(key);
                return true;
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
                return false;
            }
        }
        inline auto call_add_node(void* fn, const void* key) -> bool
        {
            __try
            {
                reinterpret_cast<void (*)(const void*)>(fn)(key);
                return true;
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
                return false;
            }
        }
        inline auto has_node(std::wstring_view node, bool& out) -> bool
        {
            void* fn = native_address(L"Bonding:HasNode");
            RC::Unreal::FString key(std::wstring(node).c_str());
            return fn && call_has_node(fn, &key, out);
        }
    } // namespace detail
    // Whether your cat has answered a bond talk's node (its Bonding/Nodes, through the game's own check), now. nullopt
    // in menus or without the game's function on this build.
    inline auto bond_node(std::wstring_view node) -> std::optional<bool>
    {
        if (!assert_game_thread(L"bond_node") || !player()) return std::nullopt;
        bool had = false;
        if (!detail::has_node(node, had)) return std::nullopt;
        return had;
    }
    // Answer a bond talk's node as the game's own talk does: what its QuestDialogueActionResolveBondAnswer does, read
    // from its code (docs/reverse-engineering.md, "A bond talk's answer"). `node` is the answer's row (talk_row: the
    // talk's tag, a dot and the answer node's SubTag); `role` the story cat talked to (L"TheMistrustfulLeader"; empty
    // for a cat that plays none: then the node is marked with no cat's bond moved, as the game does for such a cat).
    // - A row with no trait does nothing: nullopt. So does a node no table has.
    // - The bonus: Gameplay.Progression.Bonding.TraitModifier (1) when your cat has the answer's trait (cat_traits()).
    // - The first time your cat answers the node: the node is marked, and the story cat's bond gets the row's Score
    //   plus the bonus (AddPersonalBonding).
    // - Every time: your clan's regard gets the row's ClanBonding plus the bonus (AddClanScore).
    // What the game shows with it (the cat's reaction, the bond and trait notices, a rank change's popup) isn't shown.
    // The game also counts each conversation's resolved answers so one talk doesn't resolve an answer twice;
    // answer_bond keeps no such count: called again for a node, it moves your clan's regard again (not the cat's bond).
    // nullopt, with nothing changed, as above, for a role that isn't a story cat's, in menus, or without the game's
    // functions on this build.
    inline auto answer_bond(std::wstring_view node, std::wstring_view role) -> std::optional<BondAnswer>
    {
        if (!assert_game_thread(L"answer_bond") || !player()) return std::nullopt;
        if (!role.empty())
            if (auto k = detail::bond_key(role); !k || k->clan) return std::nullopt;
        if (!native_address(L"Bonding:AddNode") || !native_address(L"Bonding:AddPersonal") || !native_address(L"Bonding:AddClan"))
            return std::nullopt;
        auto row = talk_row(node);
        if (!row || row->trait == 0) return std::nullopt;
        BondAnswer a;
        a.node = node;
        a.trait = row->trait;
        static const wchar_t* traits[] = {L"None", L"Brave", L"Ambitious", L"Wise", L"Energetic", L"Curious", L"Patient"};
        if (a.trait > 0 && a.trait < 7)
            for (auto& t : cat_traits())
                if (t == traits[a.trait])
                    a.bonus = static_cast<int>(tuning(L"Gameplay.Progression.Bonding.TraitModifier").value_or(1.0f));
        a.clan = cat_clan(player());
        bool had = false;
        if (!detail::has_node(node, had))
        {
            log(L"the game's bond node check failed for {}", node);
            return std::nullopt;
        }
        if (!had)
        {
            RC::Unreal::FString key(std::wstring(node).c_str());
            if (!detail::call_add_node(native_address(L"Bonding:AddNode"), &key))
            {
                log(L"the game's bond node mark failed for {}", node);
                return std::nullopt;
            }
            a.first = true;
            if (!role.empty() && add_bond(role, row->score + a.bonus))
            {
                a.role = role;
                a.personal = row->score + a.bonus;
            }
        }
        auto c = detail::bond_key(a.clan);
        if (c && c->clan && add_bond(a.clan, row->clan_bonding + a.bonus)) a.clan_change = row->clan_bonding + a.bonus;
        return a;
    }
} // namespace wcmods
