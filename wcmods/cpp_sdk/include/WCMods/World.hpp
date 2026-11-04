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

    namespace detail
    {
        // Call a reflected function only when `fill` could set what it needs (an enum's name it hasn't got
        // leaves the call out): nullopt when the object, the function or a parameter isn't there.
        inline auto call_if(UObject* object, const TCHAR* function, const std::function<bool(Params&)>& fill) -> std::optional<Params>
        {
            UFunction* fn = object ? object->GetFunctionByNameInChain(function) : nullptr;
            if (!fn) return std::nullopt;
            Params params(fn);
            if (!fill(params)) return std::nullopt;
            object->ProcessEvent(fn, params.bytes());
            return params;
        }
    } // namespace detail

    // One of the game's commands, as its controls give it (ECommands: L"Player_Show_Inventory",
    // L"Player_Pause", L"Player_Show_Map", L"Player_Show_Quest", L"Player_Interact", L"Player_Growl"...):
    // pressed, then released, through the player's input component, which hands it to what the game has
    // bound it to, so the inventory or the pause screen opens as with its key: a tap, both halves in one frame.
    // For one the game acts on while it's held (Player_Run), give the halves apart: command(name, true), then
    // command(name, false) later. False without a player, or for a name ECommands hasn't got. A screen that's open takes its
    // own commands: ui::send (Ui.hpp).
    inline auto command(std::wstring_view name, bool pressed) -> bool
    {
        UObject* input = get(controller(), L"InputComponent").object;
        return detail::call_if(input, STR("OnListenCommandInternal"), [&](Params& p) {
                   return p.set_nth(0, Value::of(name)) && p.set_nth(1, Value::of(pressed ? 0 : 1));   // EInputEvent: IE_Pressed, IE_Released
               }).has_value();
    }
    inline auto command(std::wstring_view name) -> bool { return command(name, true) && command(name, false); }

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
        // %LOCALAPPDATA% as the wide text it is (the CRT's own copy, freed here), so a user name outside the
        // ANSI code page comes through whole.
        wchar_t* base = nullptr;
        size_t length = 0;
        std::filesystem::path local = _wdupenv_s(&base, &length, L"LOCALAPPDATA") == 0 && base ? base : L"";
        std::free(base);
        return local / L"Wrc" / L"Saved" / L"SaveGames" / L"WrcGame.json";
    }
    inline auto save_file() -> Json
    {
        auto text = read_file(save_path());
        auto parsed = text ? Json::parse(*text) : std::nullopt;
        return parsed ? *parsed : Json();
    }
    // The cat's slot is the one the file names as its current cat (Shared.General.CurrentCatSlot): the save
    // game's CurrentSaveSlotIndex (save_slot) stayed 0 while the cat in play was the file's slot 8 (seen in
    // game, 2026-11-03), so it's the fallback only.
    inline auto slot_data() -> Json
    {
        Json file = save_file();
        if (!file.is_object() || file.size() == 0) return Json();
        const Json& account = file.values()[0];
        const Json& current = account["Shared"]["General"]["CurrentCatSlot"];
        const int slot = current.is_number() ? static_cast<int>(current.number()) : save_slot();
        return account[std::to_string(slot)];
    }
    // Save now, as the game does at its checkpoints (its save manager's Save): WrcGame.sav and WrcGame.json
    // are written, the state the save manager holds included. False without the save manager.
    inline auto save_game(std::wstring_view context = L"WCMods") -> bool
    {
        return call_reflected(object(STR("/Script/SwtEngine.Default__SwtSaveManager")), STR("Save"), [&](Params& p) {
                   p.set_nth(0, Value::of(context));
                   p.set_nth(1, Value::of(false));   // NewBAsyncSave
                   p.set_nth(2, Value::of(false));   // bNextTickSave
               }).has_value();
    }
    // The save's Hash, as the game holds it (USwtSaveGame.Hash, also in WrcGame.sav's header), or nullopt
    // without a save loaded. The game gives it a new value each time it writes the save.
    inline auto save_hash() -> std::optional<uint64_t>
    {
        Value h = get(save_manager(), L"SaveGame.Hash");
        if (h.kind != Value::Kind::Int) return std::nullopt;
        return static_cast<uint64_t>(h.i);
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

    // ============================================================================================ the inventory, live
    namespace detail
    {
        // One pair of a TMap<FGameplayTag, int32>: the tag's FName (its two numbers) and the count.
        struct TagCount
        {
            uint32_t name_index{}, name_number{};
            int32_t count{};
        };
        // The pairs of a TMap<FGameplayTag, int32> as the game lays one out (UE5's TSet, 0x50 bytes): +0x00 the
        // elements (20 bytes each: the FName, the count, and the hash's two links), +0x08 how many slots, +0x0C
        // how many fit; +0x10 the bit array of the slots in use (four words inline, or +0x20's when longer),
        // +0x28 its bits; +0x34 how many slots are free. False, with nothing, when what's there doesn't add up
        // as a map (a game update that moved it): the slots in use must be the slots less the free ones.
        inline auto tag_counts(const uint8_t* map, std::vector<TagCount>& out) -> bool
        {
            out.clear();
            if (!map) return false;
            auto read_i32 = [&](size_t at) { return *reinterpret_cast<const int32_t*>(map + at); };
            const uint8_t* data = *reinterpret_cast<const uint8_t* const*>(map);
            const int32_t num = read_i32(0x08), max = read_i32(0x0C), num_bits = read_i32(0x28), max_bits = read_i32(0x2C);
            const int32_t num_free = read_i32(0x34);
            if (num < 0 || max < num || max > (1 << 20) || num_free < 0 || num_free > num || num_bits < num || max_bits < num_bits) return false;
            if (num > 0 && !data) return false;
            const auto* heap_bits = *reinterpret_cast<const uint32_t* const*>(map + 0x20);
            if (!heap_bits && num_bits > 128) return false;   // more slots than the four inline words hold
            const auto* bits = heap_bits ? heap_bits : reinterpret_cast<const uint32_t*>(map + 0x10);
            for (int32_t i = 0; i < num; ++i)
            {
                if (!((bits[i / 32] >> (i % 32)) & 1u)) continue;
                const uint8_t* e = data + static_cast<size_t>(i) * 20;
                out.push_back({*reinterpret_cast<const uint32_t*>(e), *reinterpret_cast<const uint32_t*>(e + 4),
                               *reinterpret_cast<const int32_t*>(e + 8)});
            }
            if (out.size() == static_cast<size_t>(num - num_free)) return true;
            out.clear();
            return false;
        }

        // The game's AddItem, called under a structured exception handler: a fault in it (a game update that
        // changed what it takes, which the pattern check didn't catch) is logged and given back as false
        // instead of closing the game. Nothing here may need unwinding (MSVC's __try rule).
        inline auto call_add_item(void* fn, UObject* component, uint64_t tag, int32_t count, bool popup) -> bool
        {
            __try
            {
                reinterpret_cast<void (*)(UObject*, uint64_t, int32_t, bool)>(fn)(component, tag, count, popup);
                return true;
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
                return false;
            }
        }
    } // namespace detail

    // Your cat's inventory component (the player state's), or nullptr in menus.
    inline auto inventory_component() -> UObject* { return get(controller(), L"PlayerState.InventoryComponent").object; }

    // Your items now, from the inventory itself: {tag: count}, every kind (herbs, materials, accessories,
    // quest items). Null when there's no inventory (menus) or wcmods hasn't got its map on this build.
    inline auto inventory() -> Json
    {
        auto* map = member<uint8_t>(inventory_component(), L"/Script/SwtQuest.SwtQuestInventoryComponent", L"WCM_Items");
        std::vector<detail::TagCount> pairs;
        if (!detail::tag_counts(map, pairs)) return Json();
        Json out = Json::object();
        for (const auto& p : pairs) out.set(utf8(RC::Unreal::FName(p.name_index, p.name_number).ToString()), p.count);
        return out;
    }
    // How many of an item you have now (0 for none), or nullopt when the inventory can't be read.
    inline auto inventory_count(std::string_view tag) -> std::optional<int>
    {
        Json all = inventory();
        if (!all.is_object()) return std::nullopt;
        return static_cast<int>(all[tag].number(0));
    }

    // Whether a tag is one of the game's items: a registered tag under Gameplay.Inventory (a mod's new
    // items are registered from their ini at startup). The inventory takes nothing else.
    inline auto is_item_tag(std::wstring_view tag) -> bool
    {
        auto r = call_reflected(object(STR("/Script/GameplayTags.Default__BlueprintGameplayTagLibrary")), STR("MatchesTag"), [&](Params& p) {
            set(p.nth(0), L"TagName", tag);
            set(p.nth(1), L"TagName", std::wstring_view(L"Gameplay.Inventory"));
            p.set_nth(2, Value::of(false));   // bExactMatch: a child tag matches
        });
        return r && r->get(L"ReturnValue").boolean();
    }

    // Put items in your inventory the way a pickup does, through the game's own code (game.py's NATIVE): the
    // count goes up (to the game's limit per item), the HUD shows the pickup when `popup` (its OnItemPickedUp,
    // which on_function sees), quests that count items hear of it, and the save's state has it (written at
    // the next save). remove_item takes them away, as many as you have at most (an item at 0 goes), and
    // nothing of an item you haven't got (the game's code would add it at -1, tell the HUD, then drop it).
    // False on another thread, in menus, for a count below 1 (remove_item takes items away), for a tag that
    // isn't an item's (is_item_tag), or when wcmods hasn't got the function on this build.
    namespace detail
    {
        inline auto add_native(std::wstring_view tag, int count, bool popup) -> bool
        {
            if (count == 0 || !assert_game_thread(L"add_item")) return false;
            UObject* component = inventory_component();
            if (!component || !is_item_tag(tag)) return false;
            RC::Unreal::FName name(tag, RC::Unreal::FNAME_Find);
            const uint32_t index = name.GetComparisonIndex().ToUnstableInt();
            if (index == 0) return false;
            void* fn = native_address(L"SwtQuestInventoryComponent:AddItem");
            if (!fn) return false;
            // The FGameplayTag is its FName: 8 bytes, passed by value in a register.
            const uint64_t raw = index | (static_cast<uint64_t>(static_cast<uint32_t>(name.GetNumber())) << 32);
            if (call_add_item(fn, component, raw, count, popup)) return true;
            log(L"the game's AddItem failed for {}", tag);
            return false;
        }
    } // namespace detail
    inline auto add_item(std::wstring_view tag, int count = 1, bool popup = true) -> bool
    {
        return count > 0 && detail::add_native(tag, count, popup);
    }
    inline auto remove_item(std::wstring_view tag, int count = 1) -> bool
    {
        if (count <= 0) return false;
        auto have = inventory_count(utf8(tag));
        if (!have || *have <= 0) return false;
        return detail::add_native(tag, -std::min(count, *have), false);
    }

    // Your items: {tag: count} as of the game's last save, with any pickups since then, as the Lua module's
    // Game.items.list() has them. Call it once early (on_unreal_init) so the pickups since get counted.
    // inventory() reads the inventory itself.
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
    // What kind of item a tag is: "Consumable" (herbs and pouches), "Collectible" (materials), "Equipment"
    // (accessories) or "Quest"; empty for a tag that isn't an item's. The game's own answer first (the quest
    // manager's GetItemType), but its item stats table ships empty, so that is None for every item, and then
    // the kind comes from the tag: Gameplay.Inventory.Consumable, .Materials, .Cosmetic or .Quest.
    inline auto item_type(std::wstring_view tag) -> std::wstring
    {
        auto r = call_reflected(manager(STR("quests")), STR("GetItemType"), [&](Params& p) { set(p.nth(0), L"TagName", tag); });
        std::wstring kind = r ? r->get(L"ReturnValue").string() : std::wstring{};
        if (!kind.empty() && kind != L"None") return kind;
        static const std::pair<std::wstring_view, const wchar_t*> kinds[] = {{L"Gameplay.Inventory.Consumable.", L"Consumable"},
                                                                            {L"Gameplay.Inventory.Materials.", L"Collectible"},
                                                                            {L"Gameplay.Inventory.Cosmetic.", L"Equipment"},
                                                                            {L"Gameplay.Inventory.Quest.", L"Quest"}};
        for (const auto& [prefix, name] : kinds)
            if (tag.starts_with(prefix)) return name;
        return {};
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
            // A whole name first (a fixed name or a cat's own prefix is under prefix + suffix; a cameo cat or
            // a rogue under the prefix alone), then the tables' parts.
            const Json& full = n.data["whole"][utf8(prefix + suffix)];
            if (full.is_string()) return full.wstring();
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

    // ============================================================================================ an animal's senses and AI
    // A roaming animal's senses: its detection component's own copy of the tuning for its size class (the
    // TuningData's Gameplay.Exploration.Detection.<Tiny|Small|Medium|Large>.* values), so a change is this
    // animal's alone. Pointers to read and write; empty (false) for a cat (no such component) or when wcmods
    // hasn't got the members on this build.
    struct Senses
    {
        float* cone_angle{};           // how wide its vision cone is, in degrees (75)
        float* cone_distance{};        // and how deep (450)
        float* sound_radius{};         // how far it hears (450)
        float* sound_speed{};          // (1)
        float* pounce_distance{};      // how far away you can pounce on it from (400)
        float* proximity_distance{};   // close range (100; 200 for Small)
        float* target_distance{};      // how far away you can target it from (1200)
        float* walk_speed_roaming{};   // how fast it walks about (70)
        float* walk_speed_chasing{};   // and chases (400)
        float* zone_entry_distance{};  // it wakes up when you're within this (1600)
        float* zone_exit_distance{};   // and sleeps again past this (2000)
        float* react_to_chase{};       // seconds before it gives chase (0.5)
        // True when any of them is there (a game update can lose some and keep the rest): check the one you use.
        explicit operator bool() const
        {
            return cone_angle || cone_distance || sound_radius || sound_speed || pounce_distance || proximity_distance || target_distance
                   || walk_speed_roaming || walk_speed_chasing || zone_entry_distance || zone_exit_distance || react_to_chase;
        }
    };
    inline auto detection_component(UObject* actor) -> UObject* { return get(actor, L"ExplorationDetectionComponent").object; }
    inline auto senses(UObject* actor) -> Senses
    {
        UObject* c = detection_component(actor);
        constexpr auto cls = L"/Script/SwtAdventure.SwtAdventureDetectionComponent";
        return {member<float>(c, cls, L"WCM_ConeAngle"),         member<float>(c, cls, L"WCM_ConeDistance"),
                member<float>(c, cls, L"WCM_SoundRadius"),       member<float>(c, cls, L"WCM_SoundSpeed"),
                member<float>(c, cls, L"WCM_PounceDistance"),    member<float>(c, cls, L"WCM_ProximityDistance"),
                member<float>(c, cls, L"WCM_TargetDistance"),    member<float>(c, cls, L"WCM_WalkSpeedRoaming"),
                member<float>(c, cls, L"WCM_WalkSpeedChasing"),  member<float>(c, cls, L"WCM_ZoneEntryDistance"),
                member<float>(c, cls, L"WCM_ZoneExitDistance"),  member<float>(c, cls, L"WCM_ReactToChase")};
    }

    // What an animal's AI knows: its controller's blackboard, and its keys by name. A roaming animal's AI
    // keeps Detected, Target, StartLocation, RoamingLocation, DetectionRange, ChaseReactionTime, Hunted,
    // HunterPawn, PointOfInterest, bShouldAllowMovement and ArrivedAtTarget; a fighter's, AffectedByCondition,
    // IsExhausted, IsAlive, AllyWithStatus, AllyWithLowHealth, WeakestEnemy, SlowestEnemy and SelectedAttack.
    // nullptr / nullopt without an AI controller (your cat); a key the board hasn't got reads as false, 0
    // or nullptr, as the engine answers. Each call walks to the board and calls into it by reflection: a few
    // times a second for the animals you watch, not every frame for every animal.
    inline auto blackboard(UObject* actor) -> UObject* { return get(actor, L"Controller.Blackboard").object; }
    namespace detail
    {
        inline auto blackboard_value(UObject* actor, const TCHAR* function, std::wstring_view key) -> std::optional<Value>
        {
            auto r = call_reflected(blackboard(actor), function, [&](Params& p) { p.set_nth(0, Value::of(key)); });
            if (!r) return std::nullopt;
            return r->get(L"ReturnValue");
        }
    } // namespace detail
    inline auto blackboard_bool(UObject* actor, std::wstring_view key) -> std::optional<bool>
    {
        auto v = detail::blackboard_value(actor, STR("GetValueAsBool"), key);
        if (!v) return std::nullopt;
        return v->boolean();
    }
    inline auto blackboard_float(UObject* actor, std::wstring_view key) -> std::optional<double>
    {
        auto v = detail::blackboard_value(actor, STR("GetValueAsFloat"), key);
        if (!v) return std::nullopt;
        return v->number();
    }
    inline auto blackboard_object(UObject* actor, std::wstring_view key) -> UObject*
    {
        auto v = detail::blackboard_value(actor, STR("GetValueAsObject"), key);
        return v ? v->object : nullptr;
    }
    // Whether an animal has noticed a cat, and the cat it's after (nullptr when none).
    inline auto npc_detected(UObject* actor) -> bool { return blackboard_bool(actor, L"Detected").value_or(false); }
    inline auto npc_target(UObject* actor) -> UObject* { return blackboard_object(actor, L"Target"); }

    // ============================================================================================ the sky
    // The world's sky (BP_DayNightSky_C, a WrcSkyboxActor) while you play, or nullptr. Its light, fog and
    // clouds come from presets (ESkyboxPostProcessEnum): L"NeutralDay", L"Night", L"CinematicNight",
    // L"CinematicNightMoonPool", L"ThunderClan", L"RiverClan", L"ShadowClan", L"WindClan", L"MoonPool"... The
    // game picks one by the area your cat is in, and others while a fight, the inventory or a den is up.
    inline auto sky() -> UObject*
    {
        // The one in the level, not the class's defaults or one going away. (It's in a streamed part of the
        // world, whose outers lead to that part's own UWorld, not world(): seen in game.)
        using namespace RC::Unreal;
        const auto not_it = static_cast<EObjectFlags>(RF_ClassDefaultObject | RF_ArchetypeObject | RF_BeginDestroyed | RF_FinishDestroyed);
        if (!player()) return nullptr;
        for (UObject* a : find_all(STR("WrcSkyboxActor")))
            if (a && !a->HasAnyFlags(not_it)) return a;
        return nullptr;
    }
    namespace detail
    {
        // The preset set_sky holds: put on again at the end of every frame, on the sky it was put on.
        struct SkyHold
        {
            std::mutex lock;
            TimerId timer{};
            UObject* sky{};
        };
        inline auto sky_hold() -> SkyHold&
        {
            static SkyHold h;
            return h;
        }
        inline auto apply_sky(UObject* s, std::wstring_view preset) -> bool
        {
            return call_if(s, STR("ApplyStraight"), [&](Params& p) { return p.set_nth(0, Value::of(preset)); }).has_value();
        }
        inline auto release_sky() -> void
        {
            auto& h = sky_hold();
            TimerId t;
            {
                std::lock_guard lock(h.lock);
                t = h.timer;
                h.timer = 0;
                h.sky = nullptr;
            }
            if (t) cancel(t);
        }
    } // namespace detail

    // Put a preset on, at once. The game fades back to the area's own sky by itself within about 5 s (its native
    // code; seen in game, 2026-11-03), so with `hold` (the default) the preset is put on again at the end of
    // every frame until sky_follow_area(), another set_sky, or a new level; the game's own changes (the
    // inventory's, a fight's) wait meanwhile. False without the sky, or for a name the enum hasn't got.
    inline auto set_sky(std::wstring_view preset, bool hold = true) -> bool
    {
        detail::release_sky();
        UObject* s = sky();
        if (!detail::apply_sky(s, preset)) return false;
        if (!hold) return true;
        auto& h = detail::sky_hold();
        std::lock_guard lock(h.lock);
        h.sky = s;
        h.timer = every(0, [name = std::wstring(preset), cls = s->GetClassPrivate()] {
            auto& h = detail::sky_hold();
            UObject* held;
            {
                std::lock_guard lock(h.lock);
                held = h.sky;
            }
            if (!detail::object_alive(held, cls) || !detail::apply_sky(held, name)) detail::release_sky();
        });
        return true;
    }
    // Let go of a held preset and give the area's sky back, at once.
    inline auto sky_follow_area() -> bool
    {
        detail::release_sky();
        return call_reflected(sky(), STR("DoZoneDetectionFunction"), [&](Params& p) { p.set_nth(0, Value::of(false)); }).has_value();
    }

    // ============================================================================================ sounds
    // The game's sounds by their ids in its AudioEvents table (390 on build 26337109): music (L"mus_camp"),
    // effects (L"cat_step"), menu sounds (L"ui_select"), and cats' voices (L"vo_cat1_happy1"). sound_ids()
    // lists them, as the game's audio manager holds them.
    inline auto audio_manager() -> UObject* { return manager(STR("audio")); }
    inline auto sound_ids() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        for (auto& [id, sound] : map_entries(audio_manager(), L"AudioEventsInfo")) out.push_back(id.string());
        return out;
    }
    namespace detail
    {
        inline auto play_event(std::wstring_view id, const Vec3* at) -> UObject*
        {
            auto r = call_reflected(object(STR("/Script/SwtNativeAudio.Default__SwtNativeAudioManager")), STR("K2_PlayEventOf"), [&](Params& p) {
                p.set(L"EventType", id);
                Value t = p.get(L"atTransform");
                set(t, L"Rotation.W", 1.0);
                for (const wchar_t* axis : {L"Scale3D.X", L"Scale3D.Y", L"Scale3D.Z"}) set(t, axis, 1.0);
                if (at)
                {
                    set(t, L"Translation.X", at->x);
                    set(t, L"Translation.Y", at->y);
                    set(t, L"Translation.Z", at->z);
                }
                p.set(L"bIsSound2D", at == nullptr);
            });
            return r ? r->get(L"ReturnValue").object : nullptr;
        }
    } // namespace detail
    // Play one as the game does: heard the same everywhere (as the menu's sounds are), or from a place.
    // The audio component that plays it, or nullptr when the id isn't one of the game's.
    inline auto play_sound(std::wstring_view id) -> UObject* { return detail::play_event(id, nullptr); }
    inline auto play_sound(std::wstring_view id, Vec3 at) -> UObject* { return detail::play_event(id, &at); }

    // ============================================================================================ the game's own animations
    // Play one of the game's animations on a cat or an animal by its tag, as the game does: its
    // PlayMontageComponent plays that row of its animation table (your cat's: L"Animation.Exploration.Meow",
    // L"Animation.Exploration.Interaction.Dig", L"Animation.Exploration.Interaction.Sniff", L"Animation.Combat.Hit.1"...;
    // docs/reverse-engineering.md, "How cats and animals are animated"), cutting off what it plays now.
    // The montage, or nullptr (no component, or no such row).
    inline auto play_montage(UObject* actor, std::wstring_view tag, double rate = 1.0) -> UObject*
    {
        auto r = call_reflected(get(actor, L"PlayMontageComponent").object, STR("K2_PlayMontageOfTag"), [&](Params& p) {
            set(p.nth(0), L"TagName", tag);
            p.set_nth(1, Value::of(rate));
            p.set_nth(2, Value::of(true));    // bForceInterrupt
            p.set_nth(3, Value::of(false));   // bQueueIfCurrentlyPlaying
            p.set_nth(4, Value::of(false));   // bStopMontages
        });
        return r ? r->get(L"ReturnValue").object : nullptr;
    }
    // Whether any montage plays on an actor's mesh now (the game's own, or one a mod played).
    inline auto montage_playing(UObject* actor) -> bool
    {
        auto anim = call_reflected(get(actor, L"Mesh").object, STR("GetAnimInstance"));
        UObject* instance = anim ? anim->get(L"ReturnValue").object : nullptr;
        return call<bool>(instance, STR("IsAnyMontagePlaying")).value_or(false);
    }
} // namespace wcmods
