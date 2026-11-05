// Looks.hpp: cats' looks and the clan's cats. A look is the game's FCatCustomData: every cat has one on its look
// component (MeshCustomizationComponent), and the save keeps one per cat. It's read, changed and put on the cat's
// model through the game's own SetDefaultCustomData (a native function wcmods finds for the installed build:
// game.NATIVE's SwtAdventureCustomizableMeshComponent:SetDefaultCustomData), so the meshes, the pattern, the colours,
// the eyes, the accessories and the scars all follow. Accessories worn and taken off; the clan's cats as the save keeps
// them (NPCData), each with the actor that plays it when it's out; a cat's place in the story. Game thread only.
// WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call.
//
//   if (auto l = wcmods::look(wcmods::player())) { l->FurColorIdx = 3; wcmods::set_look(wcmods::player(), *l); }
//   wcmods::wear(cat, L"DogCollar", 2);
//   for (auto& c : wcmods::clan_cats()) wcmods::log(L"{} ({} {})", c.name, c.clan, c.role);
#pragma once

#include <cstdint>
#include <cstdlib>
#include <cwchar>
#include <cwctype>
#include <type_traits>
#include <utility>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // A cat's look: FCatCustomData's fields by the game's own names, as the save's text writes them. The enums
    // (ClanType, Role: an EGiverRole) by their names; CombatStats by its gameplay tag's name. What each number picks:
    // docs/reverse-engineering.md, "Cat models". The defaults are the game's own for the struct (a field the save's
    // text leaves out has its default).
    struct Look
    {
        std::wstring ClanType{L"None"}, Role{L"None"}, CombatStats{L"None"};
        int BodyOffset{}, FaceOffset{}, FurOffset{}, TailOffset{}, EarOffset{}, EyeOffset{}, WhiskerOffset{};
        int BodyValue{}, FaceValue{}, FurValue{}, EyeValue{}, WhiskerValue{};   // the shapes
        int TailIdx{}, EarIdx{}, FurIdx{};                                       // the tail, ears and fur meshes
        int FurColorIdx{}, Pattern01ColorIdx{}, Pattern02ColorIdx{};            // the colour slots
        int PatternIdx{}, MarkingIdx{};                                          // the pattern and marking textures
        int EyeLeftColorIdx{}, EyeRightColorIdx{};
        bool bOverrideColors{};   // keep every field as it is (off: the game makes up the shape, colours and pattern)
        int Design{};
        std::wstring PrefixNameId, SuffixNameId{L"_PAW"};   // the name's ids (L"STR_CAT_NAME2", L"_PAW")
        bool Gender{true};
        float CatSize{0.4f};
        // What's worn in each slot: an EAccesoryIds name (L"DogCollar"), L"None" for nothing, and its look from 1.
        std::wstring AccesoryNeckId{L"None"}, AccesoryPawId{L"None"}, AccesoryHeadId{L"None"}, AccesoryBodyId{L"None"};
        int AccesoryNeckVar{1}, AccesoryPawVar{1}, AccesoryHeadVar{1}, AccesoryBodyVar{1};
        int ScarEyeId{}, ScarEarId{}, ScarBodyId{}, ScarChestId{};   // 0 for none (docs/reverse-engineering.md, "Scars")

        auto operator==(const Look&) const -> bool = default;
    };

    namespace detail
    {
        inline constexpr const TCHAR* LOOK_COMPONENT = STR("/Script/SwtAdventure.SwtAdventureCustomizableMeshComponent");
        inline constexpr const TCHAR* QUEST_ACTOR = STR("/Script/SwtAdventure.SwtAdventureQuestActor");

        using LookMember = std::variant<int Look::*, bool Look::*, float Look::*, std::wstring Look::*>;
        struct LookField
        {
            const wchar_t* name;   // as the struct and the save's text name it
            const wchar_t* path;   // where it's read and written from the struct (CombatStats is a tag)
            LookMember member;
        };
        inline auto look_struct_fields() -> const std::vector<LookField>&
        {
            static const std::vector<LookField> f{
                {L"ClanType", L"ClanType", &Look::ClanType}, {L"Role", L"Role", &Look::Role},
                {L"CombatStats", L"CombatStats.TagName", &Look::CombatStats},
                {L"BodyOffset", L"BodyOffset", &Look::BodyOffset}, {L"FaceOffset", L"FaceOffset", &Look::FaceOffset},
                {L"FurOffset", L"FurOffset", &Look::FurOffset}, {L"TailOffset", L"TailOffset", &Look::TailOffset},
                {L"EarOffset", L"EarOffset", &Look::EarOffset}, {L"EyeOffset", L"EyeOffset", &Look::EyeOffset},
                {L"WhiskerOffset", L"WhiskerOffset", &Look::WhiskerOffset},
                {L"BodyValue", L"BodyValue", &Look::BodyValue}, {L"FaceValue", L"FaceValue", &Look::FaceValue},
                {L"FurValue", L"FurValue", &Look::FurValue}, {L"EyeValue", L"EyeValue", &Look::EyeValue},
                {L"WhiskerValue", L"WhiskerValue", &Look::WhiskerValue},
                {L"TailIdx", L"TailIdx", &Look::TailIdx}, {L"EarIdx", L"EarIdx", &Look::EarIdx}, {L"FurIdx", L"FurIdx", &Look::FurIdx},
                {L"FurColorIdx", L"FurColorIdx", &Look::FurColorIdx},
                {L"Pattern01ColorIdx", L"Pattern01ColorIdx", &Look::Pattern01ColorIdx},
                {L"Pattern02ColorIdx", L"Pattern02ColorIdx", &Look::Pattern02ColorIdx},
                {L"PatternIdx", L"PatternIdx", &Look::PatternIdx}, {L"MarkingIdx", L"MarkingIdx", &Look::MarkingIdx},
                {L"EyeLeftColorIdx", L"EyeLeftColorIdx", &Look::EyeLeftColorIdx},
                {L"EyeRightColorIdx", L"EyeRightColorIdx", &Look::EyeRightColorIdx},
                {L"bOverrideColors", L"bOverrideColors", &Look::bOverrideColors}, {L"Design", L"Design", &Look::Design},
                {L"PrefixNameId", L"PrefixNameId", &Look::PrefixNameId}, {L"SuffixNameId", L"SuffixNameId", &Look::SuffixNameId},
                {L"Gender", L"Gender", &Look::Gender}, {L"CatSize", L"CatSize", &Look::CatSize},
                {L"AccesoryNeckId", L"AccesoryNeckId", &Look::AccesoryNeckId},
                {L"AccesoryPawId", L"AccesoryPawId", &Look::AccesoryPawId},
                {L"AccesoryHeadId", L"AccesoryHeadId", &Look::AccesoryHeadId},
                {L"AccesoryBodyId", L"AccesoryBodyId", &Look::AccesoryBodyId},
                {L"AccesoryNeckVar", L"AccesoryNeckVar", &Look::AccesoryNeckVar},
                {L"AccesoryPawVar", L"AccesoryPawVar", &Look::AccesoryPawVar},
                {L"AccesoryHeadVar", L"AccesoryHeadVar", &Look::AccesoryHeadVar},
                {L"AccesoryBodyVar", L"AccesoryBodyVar", &Look::AccesoryBodyVar},
                {L"ScarEyeId", L"ScarEyeId", &Look::ScarEyeId}, {L"ScarEarId", L"ScarEarId", &Look::ScarEarId},
                {L"ScarBodyId", L"ScarBodyId", &Look::ScarBodyId}, {L"ScarChestId", L"ScarChestId", &Look::ScarChestId}};
            return f;
        }
        inline auto look_component(UObject* cat) -> UObject*
        {
            if (!cat) return nullptr;
            if (is_a(cat, LOOK_COMPONENT)) return cat;
            UObject* c = get(cat, L"MeshCustomizationComponent").object;
            return c && is_a(c, LOOK_COMPONENT) ? c : nullptr;
        }
        inline auto read_look(const Value& data) -> Look
        {
            Look l;
            for (const LookField& f : look_struct_fields())
            {
                Value v = get(data, f.path);
                if (!v) continue;
                std::visit(
                    [&](auto m) {
                        using T = std::remove_cvref_t<decltype(l.*m)>;
                        if constexpr (std::is_same_v<T, int>) l.*m = static_cast<int>(v.number());
                        else if constexpr (std::is_same_v<T, bool>) l.*m = v.boolean();
                        else if constexpr (std::is_same_v<T, float>) l.*m = static_cast<float>(v.number());
                        else l.*m = v.string();
                    },
                    f.member);
            }
            return l;
        }
        // Every field written; false naming the first that couldn't be (an enum's name it hasn't got, say).
        inline auto write_look(const Value& data, const Look& l, std::wstring& failed) -> bool
        {
            for (const LookField& f : look_struct_fields())
            {
                bool ok = std::visit(
                    [&](auto m) {
                        using T = std::remove_cvref_t<decltype(l.*m)>;
                        if constexpr (std::is_same_v<T, int>) return set(data, f.path, l.*m);
                        else if constexpr (std::is_same_v<T, bool>) return set(data, f.path, l.*m);
                        else if constexpr (std::is_same_v<T, float>) return set(data, f.path, static_cast<double>(l.*m));
                        else return set(data, f.path, std::wstring_view(l.*m));
                    },
                    f.member);
                if (!ok)
                {
                    failed = f.name;
                    return false;
                }
            }
            return true;
        }
        inline auto call_save_look(void* fn, void* data) -> bool
        {
            // The key, an FString passed by value (the game's code frees it): empty for your cat's.
            struct
            {
                wchar_t* data;
                int32_t num, max;
            } key{nullptr, 0, 0};
            __try
            {
                reinterpret_cast<void (*)(void*, void*, int32_t)>(fn)(data, &key, -1);
                return true;
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
                return false;
            }
        }
        inline auto call_set_look(void* fn, UObject* component, void* data) -> bool
        {
            __try
            {
                reinterpret_cast<void (*)(void*, void*, bool)>(fn)(component, data, false);
                return true;
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
                return false;
            }
        }
        // Set a look component up again from its own CustomData, through the game's SetDefaultCustomData. False when
        // wcmods hasn't got the function on this build or the game's code failed.
        inline auto draw_look(UObject* component) -> bool
        {
            void* fn = native_address(L"SwtAdventureCustomizableMeshComponent:SetDefaultCustomData");
            Value data = component ? get(component, L"CustomData") : Value{};
            return fn && data.at && call_set_look(fn, component, data.at);
        }
        // Struct text as Unreal writes it ("(Key=Value,Key="text",Tag=(TagName="A.B"))"): each key's value, a
        // quoted one unquoted, a nested one as its text in brackets.
        inline auto struct_text_fields(std::wstring_view s) -> std::map<std::wstring, std::wstring>
        {
            std::map<std::wstring, std::wstring> out;
            size_t i = 0;
            while (i < s.size() && (s[i] == L'(' || std::iswspace(s[i]))) ++i;
            while (i < s.size())
            {
                size_t eq = s.find(L'=', i);
                if (eq == std::wstring_view::npos) break;
                std::wstring key(s.substr(i, eq - i));
                while (!key.empty() && (key.front() == L',' || std::iswspace(key.front()))) key.erase(key.begin());
                i = eq + 1;
                std::wstring value;
                if (i < s.size() && s[i] == L'"')
                {
                    for (++i; i < s.size() && s[i] != L'"'; ++i)
                    {
                        if (s[i] == L'\\' && i + 1 < s.size()) ++i;
                        value += s[i];
                    }
                    ++i;   // the closing quote
                }
                else if (i < s.size() && s[i] == L'(')
                {
                    size_t start = i;
                    int depth = 0;
                    bool quoted = false;
                    for (; i < s.size(); ++i)
                    {
                        if (quoted && s[i] == L'\\')
                        {
                            ++i;   // an escaped character, a quote or a backslash
                            continue;
                        }
                        if (s[i] == L'"') quoted = !quoted;
                        if (quoted) continue;
                        if (s[i] == L'(') ++depth;
                        if (s[i] == L')' && --depth == 0)
                        {
                            ++i;
                            break;
                        }
                    }
                    value = std::wstring(s.substr(start, i - start));
                }
                else
                {
                    size_t end = i;
                    while (end < s.size() && s[end] != L',' && s[end] != L')') ++end;
                    value = std::wstring(s.substr(i, end - i));
                    i = end;
                }
                if (!key.empty()) out[key] = value;
                while (i < s.size() && (s[i] == L',' || s[i] == L')' || std::iswspace(s[i]))) ++i;
            }
            return out;
        }
    } // namespace detail

    // A cat's look now (its look component's CustomData): your cat (player()), any cat's actor, or a look
    // component. nullopt when it hasn't one.
    inline auto look(UObject* cat) -> std::optional<Look>
    {
        if (!assert_game_thread(L"look")) return std::nullopt;
        UObject* c = detail::look_component(cat);
        if (!c) return std::nullopt;
        Value data = get(c, L"CustomData");
        if (!data) return std::nullopt;
        return detail::read_look(data);
    }

    // A look from the save's text for one ("(ClanType=ShadowClan,Role=Leader,TailIdx=8,...)", as NPCData and your cat's
    // Customization keep it): the fields it names, the rest at their defaults (`base`'s, when given). An enum's or a
    // tag's name is taken as it's written.
    inline auto look_from_text(std::wstring_view text, const Look& base = {}) -> Look
    {
        Look l = base;
        auto fields = detail::struct_text_fields(text);
        for (const detail::LookField& f : detail::look_struct_fields())
        {
            auto it = fields.find(f.name);
            if (it == fields.end()) continue;
            const std::wstring& v = it->second;
            std::visit(
                [&](auto m) {
                    using T = std::remove_cvref_t<decltype(l.*m)>;
                    if constexpr (std::is_same_v<T, int>) l.*m = static_cast<int>(std::wcstol(v.c_str(), nullptr, 10));
                    else if constexpr (std::is_same_v<T, bool>) l.*m = v == L"True" || v == L"true";
                    else if constexpr (std::is_same_v<T, float>) l.*m = std::wcstof(v.c_str(), nullptr);
                    else if (std::wstring_view(f.name) == L"CombatStats")
                    {
                        auto tag = detail::struct_text_fields(v);
                        auto name = tag.find(L"TagName");
                        l.*m = name != tag.end() && !name->second.empty() ? name->second : L"None";
                    }
                    else l.*m = v;
                },
                f.member);
        }
        return l;
    }

    // Put a look on a cat: written into its look component's CustomData and set up again through the game's own
    // SetDefaultCustomData, so the model shows it (the tail, ears and fur meshes, the shape, the pattern and colours,
    // the eyes, the accessories and the scars). bOverrideColors is set, so the game keeps every field as given
    // instead of making up the colours and shape again. On a story or camp cat (a SwtAdventureQuestActor) its
    // DefaultCustomData is changed too, as the game does when it gives one a new look. For this actor: a cat the
    // game spawns again (after a level change) has the look its save keeps. False for no cat or look component;
    // false with a line in the log for a field the struct couldn't take (an enum name it hasn't got), when wcmods
    // hasn't got the game's function on this build, or when the game's code failed (the old look is put back in
    // CustomData each time).
    inline auto set_look(UObject* cat, const Look& given) -> bool
    {
        if (!assert_game_thread(L"set_look")) return false;
        UObject* c = detail::look_component(cat);
        if (!c || !native_address(L"SwtAdventureCustomizableMeshComponent:SetDefaultCustomData")) return false;
        Value data = get(c, L"CustomData");
        if (!data || !data.at) return false;
        Look l = given;
        l.bOverrideColors = true;
        const Look before = detail::read_look(data);
        std::wstring failed;
        if (!detail::write_look(data, l, failed))
        {
            std::wstring ignored;
            detail::write_look(data, before, ignored);
            log(L"set_look: the look's {} couldn't be written (an enum or tag name the game hasn't got?)", failed);
            return false;
        }
        // The game's own call copies the look it's given into CustomData: given CustomData itself, it keeps it.
        if (!detail::draw_look(c))
        {
            std::wstring ignored;
            detail::write_look(data, before, ignored);   // CustomData says what the model shows again
            log(L"set_look: the game's SetDefaultCustomData failed");
            return false;
        }
        auto owner_of = call_reflected(c, STR("GetOwner"));
        UObject* owner = owner_of ? owner_of->get(L"ReturnValue").object : nullptr;
        if (owner && is_a(owner, detail::QUEST_ACTOR))
        {
            std::wstring ignored;
            detail::write_look(get(owner, L"DefaultCustomData"), l, ignored);
        }
        return true;
    }

    // Keep a look as your cat's in the save (the game's own SaveCatCustomData, into the slot's GameplayProgression):
    // the game's next save writes it, and the game sets your cat up with it from then on (a new area, the game
    // loaded again). set_look puts it on the model now; this doesn't. bOverrideColors is set, as set_look does. False
    // in menus (no cat), for a field the struct couldn't take, or when wcmods hasn't got the game's function.
    inline auto keep_look(const Look& given) -> bool
    {
        if (!assert_game_thread(L"keep_look") || !player()) return false;
        void* fn = native_address(L"Customization:SaveCatCustomData");
        UObject* cdo = object(STR("/Script/SwtAdventure.Default__SwtAdventureQuestActor"));
        UFunction* holder = cdo ? cdo->GetFunctionByNameInChain(STR("UpdatedClan")) : nullptr;
        if (!fn || !holder) return false;
        // A look struct of the game's own to hand it: UpdatedClan's Data parameter (made and freed with the Params).
        Params p(holder);
        Value data = p.get(L"Data");
        if (!data || !data.at) return false;
        Look l = given;
        l.bOverrideColors = true;
        std::wstring failed;
        if (!detail::write_look(data, l, failed))
        {
            log(L"keep_look: the look's {} couldn't be written (an enum or tag name the game hasn't got?)", failed);
            return false;
        }
        if (detail::call_save_look(fn, data.at)) return true;
        log(L"keep_look: the game's SaveCatCustomData failed");
        return false;
    }

    // An accessory the game has: its EAccesoryIds name, the slot it's worn in (L"Neck", L"Paw", L"Head", L"Body"),
    // and how many looks (variations) it comes in.
    struct Accessory
    {
        std::wstring id, slot;
        int variations{};
    };
    // The game's accessories (the GUI manager's AccesoryMeshes, each one's slot from its item tags,
    // Gameplay.Inventory.Cosmetic.<slot>.<id>.<n>, and its looks from AccesoryVariations), by id. Empty without the
    // GUI manager.
    inline auto accessories() -> std::vector<Accessory>
    {
        static std::vector<Accessory> kept;   // the game's lists don't change once it has started
        if (!assert_game_thread(L"accessories")) return {};
        if (!kept.empty()) return kept;
        std::vector<Accessory> out;
        UObject* gui = manager(STR("gui"));
        if (!gui) return out;
        std::map<std::wstring, std::wstring> slots;
        for (const wchar_t* list : {L"AccesoriesTestTags", L"AccesoriesTestTagsDlc"})
            for (const Value& tag : elements(gui, list))
            {
                std::wstring t = get(tag, L"TagName").string();
                const std::wstring head = L"Gameplay.Inventory.Cosmetic.";
                if (t.rfind(head, 0) != 0) continue;
                std::wstring rest = t.substr(head.size());
                size_t dot = rest.find(L'.');
                if (dot == std::wstring::npos) continue;
                std::wstring slot = rest.substr(0, dot), id = rest.substr(dot + 1);
                id = id.substr(0, id.find(L'.'));
                slots[id] = slot == L"Legs" ? L"Paw" : slot;
            }
        std::map<std::wstring, int> looks;
        for (auto& [id, v] : map_entries(gui, L"AccesoryVariations"))
            looks[id.string()] = static_cast<int>(elements(get(v, L"Textures")).size());
        for (auto& [id, mesh] : map_entries(gui, L"AccesoryMeshes"))
        {
            Accessory a;
            a.id = id.string();
            if (a.id.empty() || a.id == L"None") continue;
            auto s = slots.find(a.id);
            a.slot = s != slots.end() ? s->second : L"";
            auto n = looks.find(a.id);
            a.variations = n != looks.end() ? n->second : 0;
            out.push_back(std::move(a));
        }
        kept = out;
        return out;
    }

    namespace detail
    {
        inline auto accessory_fields(std::wstring_view slot) -> std::pair<std::wstring Look::*, int Look::*>
        {
            if (slot == L"Neck") return {&Look::AccesoryNeckId, &Look::AccesoryNeckVar};
            if (slot == L"Paw") return {&Look::AccesoryPawId, &Look::AccesoryPawVar};
            if (slot == L"Head") return {&Look::AccesoryHeadId, &Look::AccesoryHeadVar};
            if (slot == L"Body") return {&Look::AccesoryBodyId, &Look::AccesoryBodyVar};
            return {nullptr, nullptr};
        }
    } // namespace detail

    // Put an accessory on a cat (L"DogCollar", its look from 1), in its own slot, through set_look; what was in that
    // slot comes off. False for an accessory the game hasn't got, a look it hasn't got, or as set_look.
    inline auto wear(UObject* cat, std::wstring_view accessory, int variation = 1) -> bool
    {
        if (!assert_game_thread(L"wear")) return false;
        for (const Accessory& a : accessories())
        {
            if (a.id != accessory) continue;
            auto [id, var] = detail::accessory_fields(a.slot);
            if (!id || variation < 1 || (a.variations > 0 && variation > a.variations)) return false;
            auto l = look(cat);
            if (!l) return false;
            (*l).*id = a.id;
            (*l).*var = variation;
            return set_look(cat, *l);
        }
        return false;
    }
    // Take off what a cat wears in a slot (L"Neck", L"Paw", L"Head", L"Body"). False for another slot, or as
    // set_look; true when the slot was empty already.
    inline auto take_off(UObject* cat, std::wstring_view slot) -> bool
    {
        if (!assert_game_thread(L"take_off")) return false;
        auto [id, var] = detail::accessory_fields(slot);
        if (!id) return false;
        auto l = look(cat);
        if (!l) return false;
        if ((*l).*id == L"None" || (*l).*id == L"") return true;
        (*l).*id = L"None";
        (*l).*var = 1;
        return set_look(cat, *l);
    }

    // A cat's place: its clan and role (EGiverRole: L"Warrior", L"MedicineCat"), and, for a story or camp cat (a
    // SwtAdventureQuestActor), the story role it plays (ENarrativeRole: L"TheAmbitiousApprentice", or empty). (Such a
    // cat's CurrentRank isn't its rank: the leader read Apprentice and a kit Leader.)
    struct CatRole
    {
        std::wstring clan, role, story_role;
    };
    inline auto role_of(UObject* cat) -> std::optional<CatRole>
    {
        if (!assert_game_thread(L"role_of")) return std::nullopt;
        UObject* c = detail::look_component(cat);
        if (!c) return std::nullopt;
        CatRole r;
        r.clan = get(c, L"CustomData.ClanType").string();
        r.role = get(c, L"CustomData.Role").string();
        if (cat && is_a(cat, detail::QUEST_ACTOR))
        {
            r.story_role = get(cat, L"narrativeRole").string();
            if (r.story_role == L"None") r.story_role.clear();
        }
        return r;
    }

    // One of the clans' cats, as the save keeps it (your cat's slot's NPCData).
    struct ClanCat
    {
        std::wstring clan;    // its group in the save: a clan (L"ShadowClan"), or L"OutOfClans"
        std::wstring role;    // its role's group (EGiverRole: L"Warrior")
        int index{};          // its place in that group; -1 for a story cat the save keeps only as a story role
        std::wstring name;    // as the game shows it ("Tawnypelt"), after your name mods
        Look look;            // as the save keeps it (look_from_text)
        std::vector<std::wstring> story_roles;   // the story roles it plays (NarrativeRoles: L"ShadowClanLeader")
        UObject* actor{};     // the cat out in the world now (its clan, role and name ids the same), or nullptr
    };

    // Every cat the save keeps for your cat's game, as of the last save (slot_data()'s NPCData): each clan's cats by
    // role, the cats outside the clans, then the story cats kept only as their story role (a cameo cat; a role the
    // game hasn't cast yet isn't one). Each with the story roles it plays and, when it's out in the world now, its
    // actor. Empty in menus.
    inline auto clan_cats() -> std::vector<ClanCat>
    {
        std::vector<ClanCat> out;
        if (!assert_game_thread(L"clan_cats") || !player()) return out;
        auto save = detail::read_save();   // the cached parse, not a copy of it
        if (!save.data) return out;
        const Json& npcs = detail::slot_of(*save.data)["NPCData"];
        if (!npcs.is_object()) return out;
        std::vector<std::pair<std::wstring, std::wstring>> story;   // a story role, its cat's text
        const Json& roles = npcs["NarrativeRoles"];
        for (size_t i = 0; i < roles.keys().size(); ++i)
            if (roles.values()[i].is_string()) story.push_back({wide(roles.keys()[i]), roles.values()[i].wstring()});
        std::vector<bool> placed(story.size());
        for (size_t g = 0; g < npcs.keys().size(); ++g)
        {
            const std::string& group = npcs.keys()[g];
            if (group == "NarrativeRoles" || group == "RemainingNames") continue;
            const Json& by_role = npcs.values()[g];
            for (size_t r = 0; r < by_role.keys().size(); ++r)
            {
                const auto& cats = by_role.values()[r].values();
                for (size_t i = 0; i < cats.size(); ++i)
                {
                    if (!cats[i].is_string()) continue;
                    ClanCat c;
                    c.clan = wide(group);
                    c.role = wide(by_role.keys()[r]);
                    c.index = static_cast<int>(i);
                    std::wstring text = cats[i].wstring();
                    c.look = look_from_text(text);
                    c.name = cat_name_of(c.look.PrefixNameId, c.look.SuffixNameId);
                    for (size_t s = 0; s < story.size(); ++s)
                        if (story[s].second == text)
                        {
                            c.story_roles.push_back(story[s].first);
                            placed[s] = true;
                        }
                    out.push_back(std::move(c));
                }
            }
        }
        for (size_t s = 0; s < story.size(); ++s)
        {
            if (placed[s]) continue;
            ClanCat c;
            c.look = look_from_text(story[s].second);
            if (c.look.PrefixNameId.empty()) continue;   // a role the game hasn't cast yet ("" or no name in the save)
            c.clan = c.look.ClanType == L"None" ? L"OutOfClans" : c.look.ClanType;
            c.role = c.look.Role;
            c.index = -1;
            c.name = cat_name_of(c.look.PrefixNameId, c.look.SuffixNameId);
            c.story_roles.push_back(story[s].first);
            out.push_back(std::move(c));
        }
        // The cats out now, by their clan, role and name ids.
        for (const TCHAR* cls : {STR("SwtAdventureWalkingNPC"), STR("SwtAdventureQuestActor")})
            for (UObject* a : find_all(cls))
            {
                UObject* comp = detail::look_component(a);
                if (!comp) continue;
                // A walking cat a mod spawned (spawn_npc, or a Lua mod's Game.npcs) has its save id switched off.
                Value kept = get(a, L"InstancedUniqueIdentifierComponent.bIsEnabled");
                if (kept && !kept.boolean()) continue;
                Value d = get(comp, L"CustomData");
                std::wstring clan = get(d, L"ClanType").string(), role = get(d, L"Role").string();
                std::wstring prefix = get(d, L"PrefixNameId").string(), suffix = get(d, L"SuffixNameId").string();
                for (ClanCat& c : out)
                    if (!c.actor && c.look.Role == role && c.look.PrefixNameId == prefix && c.look.SuffixNameId == suffix
                        && (c.look.ClanType == clan || (c.clan == L"OutOfClans" && clan == L"None")))
                    {
                        c.actor = a;
                        break;
                    }
            }
        return out;
    }
} // namespace wcmods
