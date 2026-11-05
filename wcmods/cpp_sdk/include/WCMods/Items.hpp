// Items.hpp: the game's items and things on the ground. What an item is (its row in the item table,
// DT_QuestObjectsInfo: its name, description, icon, rarity; and for a herb what using it does, Consumables), and a
// pickup of one dropped for your cat to collect the usual way: the game's own pickup of that item, or a mod's own
// model for a herb or material that has one (items.json "model", from the install's WCModsItems.json). As Lua's
// Game.items.drop (docs/scripting.md), which these follow. A herb's use comes through the game's own lookup (a native
// function wcmods finds for the installed build: game.NATIVE's SwtAdventureTuningManager:GetConsumable). Game thread only. WCMods.hpp includes it; docs/SDK.md,
// "C++ mods", documents every call.
//
//   if (auto info = wcmods::item_info(L"Gameplay.Inventory.Materials.Moss")) wcmods::log(L"{}", info->name);
//   wcmods::drop_item(L"Gameplay.Inventory.Materials.Moss", 3);   // beside your cat
#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/Tables.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // What an item is. `kind` is item_type()'s ("Consumable", "Collectible", "Equipment", "Quest"); `rarity`
    // (EItemRarity), `group` (EItemGroupIconType: the icon's corner mark) and `colour` (EItemCategoryColorType) by
    // their names. For a herb, what using it does (its Consumables.csv row, as items.json's keys name it): `effect`,
    // the effect it runs (Gameplay.Effect.Consumable.Health.1), `use_type` (ESwtAdventureConsumableType), `target`
    // (ESwtAdventureTargetEffect: Owner or OwnerTeam), whether it can be used `in_fights` and `exploring`, and
    // whether it's `fight_only` (gone after the fight); `usable` says the herb has a row. Empty and false otherwise.
    struct ItemInfo
    {
        std::wstring tag, name, description, icon, kind, rarity, group, colour;
        bool usable{};
        std::wstring effect, use_type, target;
        bool in_fights{}, exploring{}, fight_only{};
    };

    namespace detail
    {
        inline constexpr const wchar_t* ITEM_TABLE = L"DT_QuestObjectsInfo";

        inline constexpr const wchar_t* PICKUPS = L"/Game/Gameplay/Blueprints/WorldElements/Pickups/";
        inline constexpr const wchar_t* FALLBACK_PICKUP = L"SmallHealingHerb";   // a mod's item without a pickup of its own

        // The game's lookup of a herb's Consumables.csv row (game.NATIVE's SwtAdventureTuningManager:GetConsumable;
        // the rows live only in the adventure tuning manager's map): 1 found, 0 not, -1 when the call failed.
        inline auto call_get_consumable(void* fn, const void* key, void* row) -> int
        {
            __try
            {
                return reinterpret_cast<bool (*)(const void*, void*)>(fn)(key, row) ? 1 : 0;
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
                return -1;
            }
        }
        inline auto enum_name_of(const TCHAR* enum_path, int64_t v) -> std::wstring
        {
            for (auto& [n, value] : enum_names(enum_path))
                if (value == v) return n;
            return std::to_wstring(v);
        }
        // A herb's row into `info`: what using it does.
        inline auto read_use(std::wstring_view tag, ItemInfo& info) -> void
        {
            void* fn = native_address(L"SwtAdventureTuningManager:GetConsumable");
            if (!fn) return;
            RC::Unreal::FString key(std::wstring(tag).c_str());
            alignas(16) uint8_t row[0x28]{};   // FSwtAdventureConsumableStruct, zeroed: an empty EffectOnUse
            const int found = call_get_consumable(fn, &key, row);
            if (found < 0) log(L"item_info: the game's consumable lookup failed for {}", tag);
            if (found != 1) return;   // (after a failure its copy of the string, if any, is left: nothing can say what's there)
            auto* effect = reinterpret_cast<RC::Unreal::FString*>(row + 0x18);
            info.usable = true;
            info.in_fights = row[0x10] != 0;
            info.exploring = row[0x11] != 0;
            info.target = enum_name_of(STR("/Script/SwtAdventure.ESwtAdventureTargetEffect"), row[0x12]);
            info.fight_only = row[0x13] != 0;
            info.use_type = enum_name_of(STR("/Script/SwtAdventure.ESwtAdventureConsumableType"), row[0x14]);
            const TCHAR* text = **effect;
            info.effect = text ? text : L"";
            std::destroy_at(effect);   // the game's copy of the string, freed by its own allocator
        }
        // How a mod's herb or material lies on the ground (the install's WCModsItems.json: {"pickups": {tag:
        // {"mesh", "texture", "arm", "normal", "class"}}}), read once.
        inline auto ground_looks() -> const Json&
        {
            static Json looks;
            static std::once_flag read;
            std::call_once(read, [] {
                auto text = read_file(mod().installed.parent_path() / L"shared" / L"WCModsItems" / L"WCModsItems.json");
                auto parsed = text ? Json::parse(*text) : std::nullopt;
                looks = parsed ? (*parsed)["pickups"] : Json::object();
            });
            return looks;
        }
        // The game's pickup BP_Pickup_<short>, loaded first when `load_it` (a short with none would only fail).
        inline auto pickup_class(std::wstring_view short_name, bool load_it) -> UObject*
        {
            std::wstring path = std::wstring(PICKUPS) + L"BP_Pickup_" + std::wstring(short_name) + L".BP_Pickup_" +
                                std::wstring(short_name) + L"_C";
            if (UObject* cls = object(path.c_str())) return cls;
            return load_it ? load(path) : nullptr;
        }
        // A mod's model in place of the pickup's own herb: a skeletal mesh component with the model (a copy of an
        // accessory's mesh made at install, on its root bone) and its pictures on a dynamic material. The pickup is
        // still collected by its own interact sphere.
        inline auto dress_pickup(UObject* pickup, const Json& look) -> bool
        {
            UObject* mesh = load(look["mesh"].wstring());
            UObject* cls = object(STR("/Script/Engine.SkeletalMeshComponent"));
            if (!mesh || !cls) return false;
            auto made = call_reflected(pickup, STR("AddComponentByClass"), [&](Params& p) {
                p.set_nth(0, Value::of(cls));
                p.set_nth(1, Value::of(false));
                transform_of(p, L"RelativeTransform", {0, 0, 0}, 0);
                p.set_nth(3, Value::of(false));
            });
            UObject* comp = made ? made->get(L"ReturnValue").object : nullptr;
            if (!comp) return false;
            call_reflected(comp, STR("SetSkeletalMeshAsset"), [&](Params& p) { p.set_nth(0, Value::of(mesh)); });
            call_reflected(comp, STR("SetCollisionEnabled"), [&](Params& p) { p.set_nth(0, Value::of(0)); });
            auto m = call_reflected(comp, STR("GetMaterial"), [&](Params& p) { p.set_nth(0, Value::of(0)); });
            UObject* mat = m ? m->get(L"ReturnValue").object : nullptr;
            auto d = mat ? call_reflected(comp, STR("CreateDynamicMaterialInstance"), [&](Params& p) {
                p.set_nth(0, Value::of(0));
                p.set_nth(1, Value::of(mat));
                p.set_nth(2, Value::of(std::wstring_view(L"WCModsGround")));
            })
                         : std::nullopt;
            UObject* mid = d ? d->get(L"ReturnValue").object : nullptr;
            static const std::pair<const char*, const wchar_t*> params[] = {
                {"texture", L"LYR1 Albedo"}, {"arm", L"LYR1 ARM"}, {"normal", L"LYR1 Normal"}};
            for (auto& [key, param] : params)
            {
                UObject* tex = mid && look[key].is_string() ? load(look[key].wstring()) : nullptr;
                if (!tex) continue;
                call_reflected(mid, STR("SetTextureParameterValue"), [&](Params& p) {
                    p.set_nth(0, Value::of(std::wstring_view(param)));
                    p.set_nth(1, Value::of(tex));
                });
            }
            if (UObject* own = get(pickup, L"StaticMeshComponent").object)
            {
                call_reflected(own, STR("SetVisibility"), [&](Params& p) {
                    p.set_nth(0, Value::of(false));
                    p.set_nth(1, Value::of(false));
                });
                call_reflected(own, STR("SetCollisionEnabled"), [&](Params& p) { p.set_nth(0, Value::of(0)); });
            }
            return true;
        }
    } // namespace detail

    namespace detail
    {
        // The item table's row names by tag (its row names mean nothing: NewRow_45), read again when the table or
        // its row count changes (a mod's row added or taken out).
        inline auto item_rows() -> const std::map<std::wstring, std::wstring>&
        {
            static std::map<std::wstring, std::wstring> by_tag;
            static UObject* of{};
            static int rows{-1};
            Table items = table(ITEM_TABLE);
            if (items.object() != of || items.size() != rows)
            {
                by_tag.clear();
                for (auto& [row_name, row] : items.rows()) by_tag[get(row, L"itemTag.TagName").string()] = row_name;
                of = items.object();
                rows = items.size();
            }
            return by_tag;
        }
    } // namespace detail

    // What an item is, from the game's tables as they are now (a mod's items and a table edit included); nullopt
    // for a tag the item table hasn't got.
    inline auto item_info(std::wstring_view tag) -> std::optional<ItemInfo>
    {
        if (!assert_game_thread(L"item_info") || tag.empty()) return std::nullopt;
        const auto& rows = detail::item_rows();
        auto found = rows.find(std::wstring(tag));
        Value row = found != rows.end() ? table(detail::ITEM_TABLE).row(found->second) : Value{};
        if (row && get(row, L"itemTag.TagName").string() == tag)
        {
            ItemInfo info;
            info.tag = std::wstring(tag);
            info.name = get(row, L"Name").string();
            info.description = get(row, L"Description").string();
            info.icon = soft_path(get(row, L"Icon"));
            info.kind = item_type(tag);
            info.rarity = get(row, L"ItemRarity").string();
            info.group = get(row, L"ItemGroupIcon").string();
            info.colour = get(row, L"ItemCategoryColor").string();
            detail::read_use(tag, info);
            return info;
        }
        return std::nullopt;
    }

    // Every item the item table has, by tag.
    inline auto item_tags() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        if (!assert_game_thread(L"item_tags")) return out;
        for (auto& [tag, row_name] : detail::item_rows())
            if (!tag.empty() && tag != L"None") out.push_back(tag);
        return out;
    }

    // Put a pickup holding `count` of an item on the ground for your cat to collect with Interact, as the game's
    // own pickups are: half a metre in front of your cat, or below `at`. It lies as the game's pickup of that
    // item, a mod's herb or material as its own model (items.json "model") or as the game's pickup it names, and
    // anything else as the small healing herb's. Not kept: it's gone with the level, and the save doesn't hold it.
    // The pickup's actor, or nullptr in menus, for a count below 1, or for a tag that isn't an item's (one the game
    // hasn't registered would get into the save and crash the game when it quits).
    inline auto drop_item(std::wstring_view tag, int count = 1, std::optional<Vec3> at = std::nullopt) -> UObject*
    {
        if (!assert_game_thread(L"drop_item") || !player() || count < 1 || tag.empty() || !is_item_tag(tag)) return nullptr;
        const Json& look = detail::ground_looks()[utf8(tag)];
        std::wstring short_name(tag.substr(tag.rfind(L'.') + 1));
        UObject* cls = detail::pickup_class(short_name, false);
        if (!cls && look["class"].is_string()) cls = detail::pickup_class(look["class"].wstring(), true);
        if (!cls) cls = detail::pickup_class(detail::FALLBACK_PICKUP, true);
        auto from = at ? at : location(player());
        if (!cls || !from) return nullptr;
        Vec3 spot = *from;
        if (!at)   // in front of your cat, where its Interact reaches (the game's choice of what's in reach faces it)
            if (auto f = call_reflected(player(), STR("GetActorForwardVector")))
            {
                Value v = f->get(L"ReturnValue");
                spot.x += get(v, L"X").number() * 50;
                spot.y += get(v, L"Y").number() * 50;
            }
        // On the ground below: a cat's location is the middle of its body. A line that starts inside a rock hits
        // where it starts, so that height is kept as it is.
        auto g = trace({spot.x, spot.y, from->z + 50}, {spot.x, spot.y, from->z - 300});
        if (g && g->z < from->z + 49) spot.z = g->z;
        UObject* a = detail::spawn_deferred(cls, spot, 0, [](UObject* a) {
            // Not one of the level's pickups: nothing for the save to remember of it.
            set(a, L"bUseSaveData", false);
            set(a, L"bUseUniqueIDPersistence", false);
        });
        if (!a) return nullptr;
        Value reward = get(a, L"Reward");
        map_clear(reward);
        map_add(reward, [&](const Value& key, const Value& n) {
            set(key, L"TagName", tag);
            set(n, L"", count);
        });
        if (look["mesh"].is_string()) detail::dress_pickup(a, look);
        return a;
    }
} // namespace wcmods
