// WCMods/World.hpp: what's around your cat, the game's own screens and input, traces to the ground, the
// save, your items, and a cat's name, clan and traits. Game thread only. WCMods.hpp includes it;
// docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <map>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>

namespace wcmods
{
    // ============================================================================================ what's around
    // The kinds of things nearby() finds, each the game's classes for it (as WCModsWorld sorts them).
    enum class Kind { Pickups, Interactables, Objectives, Cats, QuestGivers, Creatures, Climbing, Dens, FreshKill, Zones, Checkpoints };

    struct Nearby
    {
        UObject* actor{};
        Vec3 location;
        double distance{};
        std::wstring name;    // the actor's name
        std::wstring type;    // its class
    };

    namespace detail
    {
        inline auto kind_classes(Kind kind) -> std::vector<const TCHAR*>
        {
            switch (kind)
            {
            case Kind::Pickups: return {STR("SwtAdventurePickupActor")};
            case Kind::Interactables: return {STR("BP_Interactable_Base_C"), STR("SwtAdventureInteractableSequence"), STR("SwtAdventureInteractByContact")};
            case Kind::Objectives: return {STR("SwtQuestObjectivePoint"), STR("QuestBoxTrigger"), STR("BP_Objective_Base_C"), STR("BP_ScentObjective_C"), STR("BP_InterativeObjective_C")};
            case Kind::Cats: return {STR("SwtAdventureWalkingNPC"), STR("SwtAdventureQuestActor")};
            case Kind::QuestGivers: return {STR("BP_Quest_Giver_Base_C"), STR("SwtAdventureQuestHintActor"), STR("SwtAdventureFreshKillActor")};
            case Kind::Creatures: return {STR("WrcRoamingEnemy")};
            case Kind::Climbing: return {STR("SwtAdventureSplineClimbTarget"), STR("SwtAdventureJumpHotspotBase")};
            case Kind::Dens: return {STR("SwtAdventureHousingDoorActor")};
            case Kind::FreshKill: return {STR("SwtAdventureFreshKillPileActor")};
            case Kind::Zones: return {STR("WrcZoneNameTrigger")};
            case Kind::Checkpoints: return {STR("BP_Checkpoint_Base_C")};
            }
            return {};
        }
    } // namespace detail

    // Things of a kind within `radius` centimetres of your cat (or of `from`), nearest first. It goes
    // through the game's objects: a few times a second, not every frame.
    inline auto nearby(Kind kind, double radius = 3000, UObject* from = nullptr) -> std::vector<Nearby>
    {
        std::vector<Nearby> out;
        UObject* me = player();
        if (!from) from = me;
        auto origin = location(from);
        if (!origin) return out;
        for (const TCHAR* cls : detail::kind_classes(kind))
        {
            for (UObject* a : find_all(cls))
            {
                if (a == me || a == from) continue;
                auto at = location(a);
                if (!at) continue;
                double dx = at->x - origin->x, dy = at->y - origin->y, dz = at->z - origin->z;
                double d = std::sqrt(dx * dx + dy * dy + dz * dz);
                if (d <= radius) out.push_back({a, *at, d, name(a), class_name(a)});
            }
        }
        std::sort(out.begin(), out.end(), [](const Nearby& p, const Nearby& q) { return p.distance < q.distance; });
        return out;
    }

    // The game's own screens and popups showing now, by class ("WBP_GuiPopupInventory_C", the map, the
    // pause menu); none while you're just playing.
    inline auto screens() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        for (UObject* w : find_all(STR("GuiScreenWrc")))
        {
            auto visible = call<bool>(w, STR("IsVisible"));
            if (visible && *visible) out.push_back(class_name(w));
        }
        return out;
    }

    // ============================================================================================ the game's input
    namespace detail
    {
        inline auto input_key(const TCHAR* function, std::wstring_view key) -> bool
        {
            // The key is the first parameter (an FKey struct), whatever the game names it.
            auto r = call_reflected(controller(), function, [&](Params& p) { set(p.nth(0), L"KeyName", key); });
            return r && r->get(L"ReturnValue").boolean();
        }
    } // namespace detail

    // Whether a key or controller button went down this frame, or is held now, in the game's own input
    // (Unreal's key names: L"T", L"Gamepad_FaceButton_Top"). Unlike on_key, it only sees keys while the
    // game has the focus, and it sees controller buttons too.
    inline auto pressed(std::wstring_view key) -> bool { return detail::input_key(STR("WasInputKeyJustPressed"), key); }
    inline auto key_down(std::wstring_view key) -> bool { return detail::input_key(STR("IsInputKeyDown"), key); }

    // ============================================================================================ traces
    // Where a straight line from one place to another first hits the world, or nullopt.
    inline auto trace(Vec3 from, Vec3 to) -> std::optional<Vec3>
    {
        UObject* lib = object(STR("/Script/Engine.Default__KismetSystemLibrary"));
        UObject* me = player();
        if (!lib || !me) return std::nullopt;
        auto r = call_reflected(lib, STR("LineTraceSingle"), [&](Params& p) {
            p.set(L"WorldContextObject", me);
            if (auto* s = static_cast<FVector*>(p.raw(L"Start"))) *s = to_fvector(from);
            if (auto* e = static_cast<FVector*>(p.raw(L"End"))) *e = to_fvector(to);
            p.set(L"bIgnoreSelf", true);
        });
        if (!r || !r->get(L"ReturnValue").boolean()) return std::nullopt;
        Value point = get(r->get(L"OutHit"), L"ImpactPoint");
        if (point.kind != Value::Kind::Struct) return std::nullopt;
        return Vec3{get(point, L"X").number(), get(point, L"Y").number(), get(point, L"Z").number()};
    }

    // The height of the ground below a place (from 2 m above it), or nullopt.
    inline auto ground(double x, double y, double z) -> std::optional<double>
    {
        auto hit = trace({x, y, z + 200}, {x, y, z - 20000});
        return hit ? std::optional<double>(hit->z) : std::nullopt;
    }

    // ============================================================================================ the save
    // The game's save manager holds the save's live data: parts of the state as JSON by key ("Inventory"),
    // whole-number progression values, and settings values.
    inline auto save_manager() -> UObject* { return manager(STR("save")); }

    // A part of the current slot's state ("Inventory", "Traits"...), as Json; null when there's none.
    // (The save manager's parameters are set by position, whatever the game names them.)
    // The JSON text the save manager gives for a part of the state, as it is ("null" for a key it hasn't got).
    inline auto save_state_text(std::wstring_view key) -> std::wstring
    {
        auto r = call_reflected(save_manager(), STR("GetStateJsonDataAsString"), [&](Params& p) { p.set_nth(0, Value::of(key)); });
        return r ? r->get(L"ReturnValue").string() : std::wstring{};
    }
    inline auto save_state(std::wstring_view key) -> Json
    {
        std::string text = utf8(save_state_text(key));
        if (text.empty()) return Json();
        auto parsed = Json::parse(text);
        return parsed ? *parsed : Json();
    }
    // Replace a part of the state.
    inline auto set_save_state(std::wstring_view key, const Json& value) -> bool
    {
        std::wstring text = wide(value.dump(0));
        return call_reflected(save_manager(), STR("SetStateJsonDataFromString"), [&](Params& p) {
            p.set_nth(0, Value::of(key));
            p.set_nth(1, Value::of(std::wstring_view(text)));
        }).has_value();
    }
    // Whole-number progression values (the save's GameplayProgression), and settings values.
    inline auto save_progression(std::wstring_view primary, std::wstring_view sub = {}) -> std::optional<double>
    {
        auto r = call_reflected(save_manager(), STR("GetGameProgressionData"), [&](Params& p) {
            p.set_nth(0, Value::of(primary));
            p.set_nth(1, Value::of(sub));
        });
        if (!r) return std::nullopt;
        Value v = r->get(L"ReturnValue");
        return v ? std::optional<double>(v.number()) : std::nullopt;
    }
    inline auto save_setting(std::wstring_view primary, std::wstring_view sub = {}) -> std::optional<double>
    {
        auto r = call_reflected(save_manager(), STR("GetSettingsData"), [&](Params& p) {
            p.set_nth(0, Value::of(primary));
            p.set_nth(1, Value::of(sub));
        });
        if (!r) return std::nullopt;
        Value v = r->get(L"ReturnValue");
        return v ? std::optional<double>(v.number()) : std::nullopt;
    }
    // Which save slot is in use (0 for the first cat).
    inline auto save_slot() -> int { return static_cast<int>(get(save_manager(), L"SaveGame.CurrentSaveSlotIndex").number()); }

    // The game writes its save as plain JSON too (WrcGame.json next to WrcGame.sav), every time it saves:
    // the whole of it as of the last save, and this cat's slot in it (GameplayProgression, NPCData...).
    inline auto save_path() -> std::filesystem::path
    {
        const char* base = std::getenv("LOCALAPPDATA");
        return std::filesystem::path(base ? base : "") / L"Wrc" / L"Saved" / L"SaveGames" / L"WrcGame.json";
    }
    inline auto save_file() -> Json
    {
        auto text = read_file(save_path());
        auto parsed = text ? Json::parse(*text) : std::nullopt;
        return parsed ? *parsed : Json();
    }
    inline auto slot_data() -> Json
    {
        Json file = save_file();
        if (!file.is_object() || file.size() == 0) return Json();
        const Json& account = file.values()[0];
        return account[std::to_string(save_slot())];
    }

    // ============================================================================================ items
    namespace detail
    {
        struct Pickups
        {
            std::mutex lock;
            std::map<std::string, double> live;   // tag -> total, from the HUD's pickup messages since the mod started
            bool watching{};
        };
        inline auto pickups() -> Pickups&
        {
            static Pickups p;
            return p;
        }
        inline auto watch_pickups() -> void
        {
            Pickups& p = pickups();
            {
                std::lock_guard lock(p.lock);
                if (p.watching) return;
                p.watching = true;
            }
            // The HUD's message: the tag, how many were picked up, and the total now (by position, as the Lua does).
            on_function(STR("/Script/Wrc.GuiHudWrc:OnItemPickedUp"), [](Call& call) {
                std::string tag = utf8(get(call.param(0), L"TagName").text);
                double total = call.param(2).number();
                if (tag.empty()) return;
                Pickups& p = pickups();
                std::lock_guard lock(p.lock);
                p.live[tag] = total;
            });
        }
    } // namespace detail

    // Your items: {tag: count} as of the game's last save, with any pickups since then. Call it once early
    // (on_unreal_init) so the pickups since get counted.
    inline auto items() -> Json
    {
        detail::watch_pickups();
        Json out = Json::object();
        Json slot = slot_data();
        const Json& inv = slot["GameplayProgression"]["State"]["Inventory"];
        if (inv.is_object())
            for (size_t i = 0; i < inv.keys().size(); ++i) out.set(inv.keys()[i], inv.values()[i]);
        detail::Pickups& p = detail::pickups();
        std::lock_guard lock(p.lock);
        for (auto& [tag, total] : p.live) out.set(tag, total);
        return out;
    }
    inline auto item_count(std::string_view tag) -> double { return items()[tag].number(); }
    // What kind of item a tag is ("Consumable", "Equipment", "Quest", "Collectible"), or empty.
    inline auto item_type(std::wstring_view tag) -> std::wstring
    {
        auto r = call_reflected(manager(STR("quests")), STR("GetItemType"), [&](Params& p) { set(p.nth(0), L"TagName", tag); });
        return r ? r->get(L"ReturnValue").string() : std::wstring{};
    }

    // ============================================================================================ cats' names, clans and traits
    namespace detail
    {
        struct Names
        {
            std::mutex lock;
            bool loaded{};
            Json data;   // prefixes, suffixes, whole, items: what wcmods wrote at install, after the name mods
            std::map<std::wstring, std::wstring> game_text;
        };
        inline auto names() -> Names&
        {
            static Names n;
            static std::once_flag loaded;   // from any thread: item_name may be asked off the game thread
            std::call_once(loaded, [] {
                auto text = read_file(mod().installed.parent_path() / L"shared" / L"WCModsNames" / L"names.json");
                auto parsed = text ? Json::parse(*text) : std::nullopt;
                std::lock_guard lock(n.lock);
                n.data = parsed ? *parsed : Json::object();
                n.loaded = true;
            });
            return n;
        }
        // The game's own text for a name key, from its string tables (for names wcmods' tables haven't got).
        inline auto game_text(const std::wstring& key) -> std::wstring
        {
            if (key.empty()) return {};
            Names& n = names();
            {
                std::lock_guard lock(n.lock);
                if (auto it = n.game_text.find(key); it != n.game_text.end()) return it->second;
            }
            UObject* lib = object(STR("/Script/Engine.Default__KismetStringTableLibrary"));
            auto tables = call_reflected(lib, STR("GetRegisteredStringTables"));
            std::wstring found;
            if (tables)
            {
                for (Value& id : elements(tables->get(L"ReturnValue")))
                {
                    auto has = call_reflected(lib, STR("IsRegisteredTableEntry"), [&](Params& p) {
                        p.set(L"TableId", std::wstring_view(id.text));
                        p.set(L"Key", std::wstring_view(key));
                    });
                    if (!has || !has->get(L"ReturnValue").boolean()) continue;
                    auto text = call_reflected(lib, STR("GetTableEntrySourceString"), [&](Params& p) {
                        p.set(L"TableId", std::wstring_view(id.text));
                        p.set(L"Key", std::wstring_view(key));
                    });
                    if (text) found = text->get(L"ReturnValue").string();
                    if (!found.empty()) break;
                }
            }
            std::lock_guard lock(n.lock);
            n.game_text[key] = found;
            return found;
        }
    } // namespace detail

    // A cat's name as the game shows it ("Otterpaw"), from its name ids and your name mods, or empty.
    inline auto cat_name(UObject* actor) -> std::wstring
    {
        std::wstring prefix = get(actor, L"MeshCustomizationComponent.CustomData.PrefixNameId").string();
        std::wstring suffix = get(actor, L"MeshCustomizationComponent.CustomData.SuffixNameId").string();
        if (prefix == L"None") prefix.clear();
        if (suffix == L"None") suffix.clear();
        detail::Names& n = detail::names();
        {
            std::lock_guard lock(n.lock);
            const Json& whole = n.data["whole"][utf8(prefix)];
            if (whole.is_string()) return whole.wstring();
            const Json& p = n.data["prefixes"][utf8(prefix)];
            if (p.is_string()) return p.wstring() + n.data["suffixes"][utf8(suffix)].wstring();
        }
        std::wstring text = detail::game_text(prefix + suffix);
        return text.empty() ? detail::game_text(prefix) : text;
    }
    // An item's name from its tag ("Marigold"), after the mods that add items, or empty.
    inline auto item_name(std::string_view tag) -> std::wstring
    {
        detail::Names& n = detail::names();
        std::lock_guard lock(n.lock);
        return n.data["items"][tag].wstring();
    }
    // A cat's clan, by the enum's name ("RiverClan"), or empty.
    inline auto cat_clan(UObject* actor) -> std::wstring { return get(actor, L"MeshCustomizationComponent.CustomData.ClanType").text; }
    // Your cat's personality traits from the last save ({L"Brave", L"Energetic"}).
    inline auto cat_traits() -> std::vector<std::wstring>
    {
        static const wchar_t* names[] = {L"None", L"Brave", L"Ambitious", L"Wise", L"Energetic", L"Curious", L"Patient"};
        std::vector<std::wstring> out;
        Json slot = slot_data();
        const Json& list = slot["GameplayProgression"]["Traits"];
        for (size_t i = 0; i < list.size(); ++i)
        {
            const Json& t = list[i]["Type"];
            if (t.is_string()) out.push_back(t.wstring());
            else if (t.is_number() && t.number() >= 0 && t.number() < 7) out.push_back(names[static_cast<int>(t.number())]);
        }
        return out;
    }
} // namespace wcmods
