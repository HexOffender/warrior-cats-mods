// WCMods/World.hpp: what's around your cat, the game's own screens and input, traces to the ground, the
// save, your items, and a cat's name, clan and traits. Game thread only. WCMods.hpp includes it;
// docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/Tables.hpp>

namespace wcmods
{
    namespace detail
    {
        // Your cat's exploration component (ExplorationControlComponent, which the character reflects as
        // ExplorationControl): its exploration settings, the turning (Map.hpp's set_camera) and the speeds (Effects.hpp's
        // set_player_speeds). nullptr outside the world or in a fight, or for one a level change left behind.
        inline constexpr const wchar_t* exploration_class = L"/Script/SwtAdventure.ExplorationControlComponent";
        inline auto exploration_control() -> UObject*
        {
            UObject* e = get(player(), L"ExplorationControl").object;
            return object_staying(e, nullptr) ? e : nullptr;
        }

        // What an object's settings were before a mod first changed them, for putting back: the object (weakly: a new
        // one can take a destroyed one's address) and its settings. A mod's own: two mods that both change them keep
        // theirs each. The camera's (set_camera) and your cat's speeds (set_player_speeds) use it.
        template <typename Settings>
        struct Kept
        {
            RC::Unreal::FWeakObjectPtr object;
            bool set{};
            Settings before;
            auto is(UObject* o) const -> bool { return set && object.Get() == o; }
            // Keep what `o` has now (read()) unless it's kept already.
            template <typename Read>
            auto keep(UObject* o, Read read) -> void
            {
                if (is(o)) return;
                object = o;
                set = true;
                before = read();
            }
            // Put back what was kept on `o` with put(before), then forget it. True when there's nothing to put back
            // (never kept, or kept on an object that's gone); false, keeping it for another try, when put() fails.
            template <typename Put>
            auto put_back(UObject* o, Put put) -> bool
            {
                if (!is(o))
                {
                    *this = {};
                    return true;
                }
                Settings was = before;
                if (!put(was)) return false;
                *this = {};
                return true;
            }
        };
    } // namespace detail

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

    // The navigation meshes the AIs walk on (the world's navigation system's NavDataSet): the forest has two, one for
    // the animals (RecastNavMeshEnemy, agents 25 cm round) and one for the cats (RecastNavMeshPlayer, 1 cm: the walking
    // cats and the SDK's own). The one an actor walks on goes by its movement's agent radius.
    namespace detail
    {
        inline auto nav_meshes() -> std::vector<UObject*>
        {
            std::vector<UObject*> out;
            for (auto& v : elements(get(world(), L"NavigationSystem.NavDataSet")))
                if (v.object) out.push_back(v.object);
            return out;
        }
        inline auto nav_mesh_for(UObject* actor) -> UObject*
        {
            Value r = get(actor, L"CharacterMovement.NavAgentProps.AgentRadius");
            if (r.kind == Value::Kind::None) return nullptr;
            UObject* best = nullptr;
            double best_d = 1e18;
            for (UObject* m : nav_meshes())
            {
                double d = std::abs(get(m, L"AgentRadius").number() - r.number());
                if (d < best_d) best = m, best_d = d;
            }
            return best;
        }
        // The mesh `actor` walks on, else the cats' (the one with the smallest agents).
        inline auto walk_mesh(UObject* actor) -> UObject*
        {
            if (UObject* m = actor ? nav_mesh_for(actor) : nullptr) return m;
            UObject* best = nullptr;
            double smallest = 1e18;
            for (UObject* m : nav_meshes())
                if (double r = get(m, L"AgentRadius").number(1e18); r < smallest) best = m, smallest = r;
            return best;
        }
        inline auto project_on(UObject* mesh, Vec3 place, double height = 0) -> std::optional<Vec3>
        {
            UObject* nav = object(STR("/Script/NavigationSystem.Default__NavigationSystemV1"));
            auto r = call_reflected(nav, STR("K2_ProjectPointToNavigation"), [&](Params& p) {
                p.set_nth(0, Value::of(world()));
                Value at = p.nth(1);
                set(at, L"X", place.x);
                set(at, L"Y", place.y);
                set(at, L"Z", place.z);
                p.set_nth(3, Value::of(mesh));
                if (height > 0)   // QueryExtent: a metre round, `height` up and down (none: the mesh's own)
                {
                    Value extent = p.nth(5);
                    set(extent, L"X", 100.0);
                    set(extent, L"Y", 100.0);
                    set(extent, L"Z", height);
                }
            });
            if (!r || !r->get(L"ReturnValue").boolean()) return std::nullopt;
            Value out = r->get(L"ProjectedLocation");
            return Vec3{get(out, L"X").number(), get(out, L"Y").number(), get(out, L"Z").number()};
        }
    } // namespace detail
    // The nearest point on the navigation mesh to a place, within the mesh's own search box (the engine's
    // K2_ProjectPointToNavigation): on the mesh `actor` walks on, else on either; nullopt off the meshes, or outside
    // the world. It looks a little way up and down (the mesh's own search box); `height` (cm) looks that far up and
    // down instead, a metre round, for a place whose height isn't known (the ground from the sky, a tree's top).
    inline auto nav_point(Vec3 place, UObject* actor = nullptr, double height = 0) -> std::optional<Vec3>
    {
        if (!assert_game_thread(L"nav_point") || !world()) return std::nullopt;
        if (UObject* mesh = actor ? detail::nav_mesh_for(actor) : nullptr) return detail::project_on(mesh, place, height);
        for (UObject* mesh : detail::nav_meshes())
            if (auto on = detail::project_on(mesh, place, height)) return on;
        return std::nullopt;
    }

    // A random place on the navigation mesh about `radius` cm of a place (with its height) or less, that a cat there
    // could walk to: the engine's K2_GetRandomReachablePointInRadius on the mesh `actor` walks on, else the cats'. (It
    // picks a polygon the circle touches and a place in it: it can lie a little past `radius`.) nullopt off the mesh,
    // or with no mesh (another level).
    inline auto random_nav_point(Vec3 around, double radius, UObject* actor = nullptr) -> std::optional<Vec3>
    {
        if (!assert_game_thread(L"random_nav_point") || !world()) return std::nullopt;
        UObject* mesh = detail::walk_mesh(actor);
        UObject* nav = object(STR("/Script/NavigationSystem.Default__NavigationSystemV1"));
        if (!mesh || !nav) return std::nullopt;
        auto r = call_reflected(nav, STR("K2_GetRandomReachablePointInRadius"), [&](Params& p) {
            p.set_nth(0, Value::of(world()));
            Value at = p.nth(1);
            set(at, L"X", around.x);
            set(at, L"Y", around.y);
            set(at, L"Z", around.z);
            p.set_nth(3, Value::of(radius));
            p.set_nth(4, Value::of(mesh));
        });
        if (!r || !r->get(L"ReturnValue").boolean()) return std::nullopt;
        Value out = r->nth(2);
        return Vec3{get(out, L"X").number(), get(out, L"Y").number(), get(out, L"Z").number()};
    }

    // How far a cat walks from one place to another along the navigation mesh (cm; on the mesh `actor` walks on, else
    // the cats'), or nullopt when there's no whole path: the other place cut off from this one (a patch of ground
    // closed round by rocks or water), off the mesh, or further than the search goes. The engine's search stops at 2048
    // steps of the cats' fine mesh: paths of 80 m were found by ShadowClan's camp, ones of 120 m gave out (a cat walked
    // there still gets there: its walk finds the way as it goes).
    inline auto nav_path_length(Vec3 from, Vec3 to, UObject* actor = nullptr) -> std::optional<double>
    {
        if (!assert_game_thread(L"nav_path_length") || !world()) return std::nullopt;
        UObject* mesh = detail::walk_mesh(actor);
        UObject* nav = object(STR("/Script/NavigationSystem.Default__NavigationSystemV1"));
        UObject* system = get(world(), L"NavigationSystem").object;
        if (!mesh || !nav || !system) return std::nullopt;
        // FindPathToLocationSynchronously gives nothing without the world's main navigation data, and there's none (the
        // two meshes are only in NavDataSet): the mesh is made it for the call, and what was there put back at once.
        // (GetPathLength needs none, but measures between its polygons' middles: metres out, shorter than the line.)
        struct PutBack
        {
            UObject* system;
            UObject* was;
            ~PutBack() { set(system, L"MainNavData", was); }   // however the call ends
        } put_back{system, get(system, L"MainNavData").object};
        set(system, L"MainNavData", mesh);
        auto r = call_reflected(nav, STR("FindPathToLocationSynchronously"), [&](Params& p) {
            p.set_nth(0, Value::of(world()));
            for (auto [i, v] : {std::pair{1, from}, std::pair{2, to}})
            {
                Value at = p.nth(i);
                set(at, L"X", v.x);
                set(at, L"Y", v.y);
                set(at, L"Z", v.z);
            }
            p.set_nth(3, Value::of(mesh));   // the context: the mesh itself
        });
        UObject* path = r ? r->get(L"ReturnValue").object : nullptr;
        auto valid = path ? call_reflected(path, STR("IsValid")) : std::nullopt;
        auto partial = path ? call_reflected(path, STR("IsPartial")) : std::nullopt;
        if (!valid || !valid->get(L"ReturnValue").boolean() || !partial || partial->get(L"ReturnValue").boolean()) return std::nullopt;
        auto length = call_reflected(path, STR("GetPathLength"));
        return length ? std::optional<double>(length->get(L"ReturnValue").number()) : std::nullopt;
    }

    // Whether the world is there at a place for a cat to stand on (a place with its height, within a couple of metres):
    // the navigation mesh by it, and the ground under that point loaded, a trace down from half a metre above it meeting
    // something within 2 m below (the navigation mesh can lie over half a metre above the ground). The navigation mesh, the Clans' terrain and the camps' floors were there all
    // over the map from ShadowClan's camp; the zones round your cat stream in and out (their props, effects and gameplay levels), and other
    // levels (a den inside) have none of it. False off the navigation mesh (a place whose height is metres out is
    // looked for from the ground below it too).
    inline auto ready_at(Vec3 place) -> bool
    {
        if (!assert_game_thread(L"ready_at")) return false;
        auto on = nav_point(place);
        if (!on)
            if (auto g = ground(place.x, place.y, place.z)) on = nav_point({place.x, place.y, *g});
        return on && trace({on->x, on->y, on->z + 50}, {on->x, on->y, on->z - 200}).has_value();
    }

    // ============================================================================================ the save
    // The game's save manager holds the save's live data. Its reflected calls below work on the account-wide part
    // (the save's Shared: Shared/GameplayProgression and its State, the settings), not the slot of the cat played:
    // that one the game's own code reaches natively (its bonds: Bonds.hpp; its inventory: inventory()). Reading a
    // progression key that isn't there writes it into the save as 0.
    inline auto save_manager() -> UObject* { return manager(STR("save")); }

    // A part of the account-wide state (Shared/GameplayProgression/State: "Currency", "Decorations"), as Json; an
    // empty object for a key it hasn't got.
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
    // Whole-number values in the account-wide progression (Shared/GameplayProgression/<primary>/<sub>), and settings
    // values. A progression read of a key that isn't there adds it as 0.
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
    namespace detail
    {
        // save_file()'s parsed save, and when, at what size and from a file written when it was read. Parsing it takes
        // about 40 ms (half a megabyte), so it's kept while the file's size and write time stay the same (a save
        // rewrites it at the same size often: a checkpoint unlocked is 0 to 1): they're looked at at most 4 times a
        // second, and the file is parsed again at least every 30 s. A file caught half written gives the last one
        // parsed whole, and save_game() drops it. As the Lua's fileCache, which looks at the size only.
        struct SaveFile
        {
            std::mutex lock;
            std::shared_ptr<const Json> data;
            std::optional<std::uintmax_t> size;   // the file's size when data was read
            std::filesystem::file_time_type written{};   // and its write time
            std::chrono::steady_clock::time_point at{}, checked{};
        };
        inline auto save_cache() -> SaveFile&
        {
            static SaveFile s;
            return s;
        }
        // The save file's size now, or nullopt without one.
        inline auto save_size() -> std::optional<std::uintmax_t>
        {
            std::error_code error;
            std::uintmax_t n = std::filesystem::file_size(save_path(), error);
            return error ? std::nullopt : std::optional<std::uintmax_t>(n);
        }
        // The save as read (null without a file), the file's size then, when it was parsed and when that file was
        // written: for items() and places(), with no copy of it.
        struct SaveRead
        {
            std::shared_ptr<const Json> data;
            std::optional<std::uintmax_t> size;
            std::chrono::steady_clock::time_point at{};
            std::filesystem::file_time_type written{};
        };
        inline auto read_save() -> SaveRead
        {
            using namespace std::chrono_literals;
            SaveFile& c = save_cache();
            std::lock_guard lock(c.lock);
            auto now = std::chrono::steady_clock::now();
            if (c.data && now - c.checked < 250ms) return {c.data, c.size, c.at, c.written};
            // The file's size and write time from one look at it (a directory entry caches both).
            std::error_code error;
            std::filesystem::directory_entry file(save_path(), error);
            std::optional<std::uintmax_t> size;
            std::filesystem::file_time_type written{};
            if (!error) size = file.file_size(error);
            if (error || !size) return {};
            written = file.last_write_time(error);
            c.checked = now;
            if (c.data && size == c.size && written == c.written && now - c.at < 30s) return {c.data, c.size, c.at, c.written};
            auto text = read_file(save_path());
            auto parsed = text ? Json::parse(*text) : std::nullopt;
            if (!parsed) return {c.data, c.size, c.at, c.written};
            c.data = std::make_shared<const Json>(std::move(*parsed));
            c.at = now;
            c.size = size;
            c.written = written;
            return {c.data, c.size, c.at, c.written};
        }
        // This cat's slot in the save: the one the file names as its current cat (Shared.General.CurrentCatSlot).
        // The save game's CurrentSaveSlotIndex (save_slot) stayed 0 while the cat in play was the file's slot 8
        // (seen in game, 2026-11-03), so it's the fallback only.
        inline auto slot_of(const Json& file) -> const Json&
        {
            static const Json none;
            if (!file.is_object() || file.size() == 0) return none;
            const Json& account = file.values()[0];
            const Json& current = account["Shared"]["General"]["CurrentCatSlot"];
            const int slot = current.is_number() ? static_cast<int>(current.number()) : save_slot();
            return account[std::to_string(slot)];
        }
    } // namespace detail
    // The whole save, parsed again only when the file has changed (see detail::SaveFile), as a copy of its own.
    inline auto save_file() -> Json
    {
        auto save = detail::read_save();
        return save.data ? *save.data : Json();
    }
    // This cat's slot of it (detail::slot_of says which).
    inline auto slot_data() -> Json
    {
        auto save = detail::read_save();
        return save.data ? detail::slot_of(*save.data) : Json();
    }
    // Save now, as the game does at its checkpoints (its save manager's Save): WrcGame.sav and WrcGame.json
    // are written, the state the save manager holds included. False without the save manager. save_file()
    // reads the file again after it (as the Lua's Game.save.write).
    inline auto save_game(std::wstring_view context = L"WCMods") -> bool
    {
        {
            detail::SaveFile& c = detail::save_cache();
            std::lock_guard lock(c.lock);
            c.data.reset();
        }
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
        // The HUD's pickup messages since the level loaded: tag -> total (live). They're stamped with the HUD that
        // sent them (its address and its name, which has its instance number: a save loaded, or another cat, is a new
        // HUD), and with the save file's size at the last one. Another HUD, or a save the game wrote since at another
        // size (which has them then), drops them, and the save says again. A save rewritten at the same size isn't
        // noticed: the pickups stay laid over it until the next load. As the Lua's pickups table.
        struct Pickups
        {
            std::mutex lock;
            std::map<std::string, double> live;
            UObject* hud{};                       // the HUD that sent them, of this class and by this name
            UClass* hud_class{};
            std::wstring hud_name;
            std::optional<std::uintmax_t> size;   // the save file's size at the last one
            std::optional<std::chrono::steady_clock::time_point> seen;   // the parse of the save last looked at
            bool watching{};
        };
        inline auto pickups() -> Pickups&
        {
            static Pickups p;
            return p;
        }
        inline auto drop_pickups(Pickups& p) -> void
        {
            p.live.clear();
            p.hud = nullptr;
            p.hud_class = nullptr;
            p.hud_name.clear();
            p.size.reset();
            p.seen.reset();
        }
        // The HUD now (GuiHudWrc's one class in game is WBP_GuiHudGameWrc_C): the pickups' own while it's there and
        // staying, else the first one that is, else nullptr: none for a moment after a load, which keeps them. As the
        // Lua's Game.find, which keeps the one it found.
        inline auto pickups_hud(const Pickups& p) -> UObject*
        {
            if (object_staying(p.hud, p.hud_class)) return p.hud;
            UObject* h = find_first(STR("WBP_GuiHudGameWrc_C"));
            return object_staying(h, nullptr) ? h : nullptr;
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
            // The HUD that sends it stamps it: a message from another HUD than the pickups' starts them again.
            on_function(STR("/Script/Wrc.GuiHudWrc:OnItemPickedUp"), [](Call& call) {
                std::string tag = utf8(get(call.param(0), L"TagName").text);
                double total = call.param(2).number();
                if (tag.empty()) return;
                UObject* hud = call.self();
                std::wstring hud_name = name(hud);
                auto size = save_size();
                Pickups& p = pickups();
                std::lock_guard lock(p.lock);
                if (hud && (hud != p.hud || hud_name != p.hud_name))
                {
                    drop_pickups(p);
                    p.hud = hud;
                    p.hud_class = hud->GetClassPrivate();
                    p.hud_name = std::move(hud_name);
                }
                p.live[tag] = total;
                p.size = size;
                p.seen.reset();
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
            std::vector<const uint8_t*> slots;
            if (!set_slots(map, 20, slots)) return false;   // Core.hpp: the slots in use, checked
            for (const uint8_t* e : slots)
                out.push_back({*reinterpret_cast<const uint32_t*>(e), *reinterpret_cast<const uint32_t*>(e + 4),
                               *reinterpret_cast<const int32_t*>(e + 8)});
            return true;
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

    // Your items: {tag: count} as of the game's last save, with the pickups since the level loaded (and since
    // that save), as the Lua module's Game.items.list() has them. Call it once early (on_unreal_init) so the
    // pickups get counted. inventory() reads the inventory itself.
    inline auto items() -> Json
    {
        detail::watch_pickups();
        Json out = Json::object();
        auto save = detail::read_save();
        if (save.data)
        {
            const Json& inv = detail::slot_of(*save.data)["GameplayProgression"]["State"]["Inventory"];
            if (inv.is_object())
                for (size_t i = 0; i < inv.keys().size(); ++i) out.set(inv.keys()[i], inv.values()[i]);
        }
        detail::Pickups& p = detail::pickups();
        std::lock_guard lock(p.lock);
        if (!p.live.empty())
        {
            UObject* hud = detail::pickups_hud(p);   // none to go by keeps them
            bool other = hud && p.hud && (hud != p.hud || name(hud) != p.hud_name);
            bool saved = false;
            if (p.seen != save.at)   // once for each parse of the save, not each call
            {
                p.seen = save.at;
                // The save read above is the file as it is now, and the game wrote it after the last pickup.
                saved = p.size && save.size && *save.size != *p.size && save.size == detail::save_size();
            }
            if (other || saved) detail::drop_pickups(p);
        }
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

    // A cat's name as the game shows it from its name ids (L"STR_CAT_NAME2", L"_PAW": "Emberpaw"), after your name
    // mods; empty when neither gives words.
    inline auto cat_name_of(std::wstring prefix, std::wstring suffix) -> std::wstring;
    // A cat's name as the game shows it ("Otterpaw"), from its name ids and your name mods, or empty.
    inline auto cat_name(UObject* actor) -> std::wstring
    {
        return cat_name_of(get(actor, L"MeshCustomizationComponent.CustomData.PrefixNameId").string(),
                           get(actor, L"MeshCustomizationComponent.CustomData.SuffixNameId").string());
    }
    inline auto cat_name_of(std::wstring prefix, std::wstring suffix) -> std::wstring
    {
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
    // A personality trait's name by its ECharacterTrait value (0 None, 1 Brave, 2 Ambitious, 3 Wise, 4 Energetic,
    // 5 Curious, 6 Patient); empty for another.
    inline auto trait_name(int trait) -> std::wstring
    {
        static const wchar_t* names[] = {L"None", L"Brave", L"Ambitious", L"Wise", L"Energetic", L"Curious", L"Patient"};
        return trait >= 0 && trait < 7 ? names[trait] : std::wstring{};
    }
    // Your cat's personality traits from the last save ({L"Brave", L"Energetic"}).
    inline auto cat_traits() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        Json slot = slot_data();
        const Json& list = slot["GameplayProgression"]["Traits"];
        for (size_t i = 0; i < list.size(); ++i)
        {
            const Json& t = list[i]["Type"];
            if (t.is_string()) out.push_back(t.wstring());
            else if (t.is_number() && t.number() >= 0 && t.number() < 7) out.push_back(trait_name(static_cast<int>(t.number())));
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
    // times a second for the animals you watch, not every frame for every animal. Writing keys, and the rest of an AI:
    // Ai.hpp.
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

    // The presets' values. The sky's SkyParamsDB (DT_SkyBoxParams) is where they come from: a row per preset
    // (NeutralDay, Night, ThunderClan...) of WrcSkyBoxStruct: the sun (SunIntensity, SunColor, SunHeight, SunRadius,
    // SunBrightness), the skylight, the height fog (FogDensity, FogHeightFalloff, FogInscatteringColor,
    // FogMaxOpacity, FogStartDistance...), the clouds, the horizon and zenith colours, the stars (StarsBrightness).
    // As the sky starts it copies them into a map of its own by preset (one of wcmods' hidden members), and putting a
    // preset on reads that copy: a row changed in the table later shows only in a sky made after (a new level),
    // while sky_values() is the copy itself, so a change there shows the next time the preset goes on (seen in game).
    inline auto sky_presets() -> Table
    {
        if (!assert_game_thread(L"sky_presets")) return {};
        UObject* db = get(sky(), L"SkyParamsDB").object;
        return db ? Table(db) : Table();
    }
    namespace detail
    {
        // ESkyboxPostProcessEnum's value for a preset's name, or -1.
        inline auto sky_preset_value(std::wstring_view preset) -> int64_t
        {
            auto* e = static_cast<RC::Unreal::UEnum*>(wcmods::object(STR("/Script/Wrc.ESkyboxPostProcessEnum")));
            if (!e) return -1;
            for (auto& pair : e->ForEachName())
                if (detail::short_enum_name(pair.Key.ToString()) == preset) return pair.Value;
            return -1;
        }
        // The sky's copy of a preset's row: its map's 0x168-byte slots hold the preset (a byte, +0) and the row from +8
        // (its vtable first, as the struct's reflected layout has it). nullptr without the sky, the map or the preset.
        // In a sky already found (sky() looks through every object).
        inline auto sky_copy_in(UObject* sky_actor, std::wstring_view preset) -> uint8_t*
        {
            const int64_t want = sky_preset_value(preset);
            auto* map = member<uint8_t>(sky_actor, L"/Script/Wrc.WrcSkyboxActor", L"WCM_Presets");
            std::vector<const uint8_t*> slots;
            if (want < 0 || !set_slots(map, 0x168, slots)) return nullptr;
            for (const uint8_t* e : slots)
                if (*e == static_cast<uint8_t>(want)) return const_cast<uint8_t*>(e) + 8;
            return nullptr;
        }
        inline auto sky_copy(std::wstring_view preset) -> uint8_t* { return sky_copy_in(sky(), preset); }
        // (preset, field) -> the game's value, and the sky it was taken from: a new level's sky makes its own copy,
        // so a value kept from another sky isn't written into it.
        struct SkyChange
        {
            double was{};
            UObject* sky{};
        };
        inline auto sky_changes() -> std::map<std::pair<std::wstring, std::wstring>, SkyChange>&
        {
            static std::map<std::pair<std::wstring, std::wstring>, SkyChange> changes;
            return changes;
        }
        // Each change back, in the sky it was made in (restore_sky_values, and the mod going).
        inline auto restore_sky_now() -> void
        {
            auto changes = sky_changes();
            sky_changes().clear();
            UObject* now = sky();
            for (auto& [where, change] : changes)
            {
                if (change.sky != now) continue;   // that sky has gone with its level, and its copy with it
                uint8_t* row = sky_copy(where.first);
                if (row) set(struct_at(STR("/Script/Wrc.WrcSkyBoxStruct"), row), where.second, change.was);
            }
        }
    } // namespace detail
    // A preset's values as putting it on uses them (by ESkyboxPostProcessEnum's name: L"Night", L"ThunderClan"...), a
    // struct Value that get and set work on (a colour's parts are L"SunColor.R", .G, .B, .A); None without the sky, for
    // a preset it hasn't got, or when wcmods hasn't got the sky's map on this build.
    inline auto sky_values(std::wstring_view preset) -> Value
    {
        if (!assert_game_thread(L"sky_values")) return {};
        uint8_t* row = detail::sky_copy(preset);
        return row ? struct_at(STR("/Script/Wrc.WrcSkyBoxStruct"), row) : Value{};
    }
    // Change one of a preset's numbers (a field, or a colour's part: L"FogDensity", L"SunColor.R"), keeping the game's
    // for restore_sky_values. It shows when the preset next goes on: at once for one set_sky holds (it's put on again
    // every frame). False without the sky, for a preset or field it hasn't got.
    inline auto set_sky_value(std::wstring_view preset, std::wstring_view field, double value) -> bool
    {
        Value row = sky_values(preset);
        if (row.kind != Value::Kind::Struct) return false;
        Value now = get(row, field);
        if (now.kind != Value::Kind::Float && now.kind != Value::Kind::Int) return false;
        const double was = now.number();
        if (!set(row, field, value)) return false;
        auto& changes = detail::sky_changes();
        auto key = std::make_pair(std::wstring(preset), std::wstring(field));
        auto it = changes.find(key);
        if (it == changes.end() || it->second.sky != sky()) changes[key] = {was, sky()};   // the first change in this sky
        return true;
    }
    // Every value set_sky_value changed back to the game's, in the sky it changed them in (a new level's sky has its
    // own copy, from the table).
    inline auto restore_sky_values() -> void
    {
        if (!assert_game_thread(L"restore_sky_values")) return;
        detail::restore_sky_now();
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

    // What the game plays for an id is the audio manager's AudioEventsMap (id -> the loaded sound, 389 on build
    // 26337109), which its own code reads each time it plays one (natively: a hook on K2_PlayEventOf sees none of
    // it). Changing an entry changes what the game plays for that id from the next time on: the cat's steps,
    // a menu's sounds, a track the music triggers ask for.
    namespace detail
    {
        inline auto sound_entry(std::wstring_view id) -> UObject**
        {
            for (auto& [key, sound] : map_entries(audio_manager(), L"AudioEventsMap"))
                if (key.string() == id && sound.at) return static_cast<UObject**>(sound.at);
            return nullptr;
        }
        // id -> the game's own sound, and whether wcmods put it in the root set. The map held the only reference to
        // it, so while it's out of the map it's kept in the root set (else the engine's garbage collection could
        // free it and restoring would write a freed object back).
        struct KeptSound
        {
            UObject* sound{};
            bool rooted{};
        };
        inline auto replaced_sounds() -> std::map<std::wstring, KeptSound>&
        {
            static std::map<std::wstring, KeptSound> kept;
            return kept;
        }
        inline auto replace_entry(std::wstring_view id, UObject* with) -> bool
        {
            UObject** entry = sound_entry(id);
            if (!entry || !with) return false;
            auto [it, first] = replaced_sounds().try_emplace(std::wstring(id), KeptSound{*entry, false});
            if (first && *entry && !(*entry)->IsRootSet())
            {
                (*entry)->SetRootSet();
                it->second.rooted = true;
            }
            *entry = with;
            return true;
        }
    } // namespace detail
    // The sound the game plays for an id now (a SoundCue or MetaSound), or nullptr for an id it hasn't got.
    inline auto sound_of(std::wstring_view id) -> UObject*
    {
        if (!assert_game_thread(L"sound_of")) return nullptr;
        UObject** entry = detail::sound_entry(id);
        return entry ? *entry : nullptr;
    }
    // Make the game play another of its sounds for an id (L"cat_step" as L"ui_select"), or a sound object the mod
    // has: from the next time it plays that id. False for an id it hasn't got. The game's own is kept.
    inline auto replace_sound(std::wstring_view id, std::wstring_view other_id) -> bool
    {
        if (!assert_game_thread(L"replace_sound")) return false;
        UObject** other = detail::sound_entry(other_id);
        return other && detail::replace_entry(id, *other);
    }
    inline auto replace_sound(std::wstring_view id, UObject* sound) -> bool
    {
        if (!assert_game_thread(L"replace_sound") || !is_a(sound, STR("/Script/Engine.SoundBase"))) return false;
        return detail::replace_entry(id, sound);
    }
    namespace detail
    {
        // A sound's own volume: a cue's VolumeMultiplier, a wave's (and a MetaSound's) Volume.
        inline auto volume_path(UObject* sound) -> const wchar_t*
        {
            if (is_a(sound, STR("/Script/Engine.SoundCue"))) return L"VolumeMultiplier";
            if (is_a(sound, STR("/Script/Engine.SoundWave"))) return L"Volume";
            return nullptr;
        }
        struct MutedSound
        {
            UObject* sound{};
            double volume{};
        };
        inline auto muted_sounds() -> std::map<std::wstring, MutedSound>&   // id -> the sound turned down, and its volume
        {
            static std::map<std::wstring, MutedSound> muted;
            return muted;
        }
        // restore_sound without the game-thread check, for the mod going (stop_sounds).
        inline auto restore_now(std::wstring_view id) -> bool
        {
            bool did = false;
            auto& muted = muted_sounds();
            if (auto m = muted.find(std::wstring(id)); m != muted.end())
            {
                if (const wchar_t* path = volume_path(m->second.sound)) set(m->second.sound, path, m->second.volume);
                muted.erase(m);
                did = true;
            }
            auto& kept = replaced_sounds();
            if (auto it = kept.find(std::wstring(id)); it != kept.end())
            {
                if (UObject** entry = sound_entry(id)) *entry = it->second.sound;
                if (it->second.rooted && it->second.sound) it->second.sound->ClearRootSet();
                kept.erase(it);
                did = true;
            }
            return did;
        }
    } // namespace detail
    // Silence an id: its sound's own volume set to 0 (a cue's VolumeMultiplier, a wave's Volume), so the game plays
    // it unheard; another id that plays the same sound is silent too. False for an id the game hasn't got, or a
    // sound with no volume of its own.
    inline auto mute_sound(std::wstring_view id) -> bool
    {
        UObject* sound = sound_of(id);
        const wchar_t* path = sound ? detail::volume_path(sound) : nullptr;
        if (!path) return false;
        detail::muted_sounds().try_emplace(std::wstring(id), detail::MutedSound{sound, get(sound, path).number()});
        return set(sound, path, 0.0);
    }
    // Give an id its own sound back (and its volume, when it was muted); false when it wasn't replaced or muted.
    inline auto restore_sound(std::wstring_view id) -> bool
    {
        if (!assert_game_thread(L"restore_sound")) return false;
        return detail::restore_now(id);
    }
    namespace detail
    {
        // As the mod is taken out: the sky's values it changed go back (UE4SS may do this off the game thread).
        inline auto stop_sky() -> void { restore_sky_now(); }
        // As the mod is taken out: every sound it replaced or muted goes back, so the change doesn't outlive it.
        inline auto stop_sounds() -> void
        {
            std::vector<std::wstring> ids;
            for (auto& [id, kept] : replaced_sounds()) ids.push_back(id);
            for (auto& [id, m] : muted_sounds()) ids.push_back(id);
            for (auto& id : ids) restore_now(id);   // UE4SS may take a mod out off the game thread
        }
    } // namespace detail
    // How long an id's sound is, in seconds (a looping one's one pass); nullopt for an id the game hasn't got.
    inline auto sound_duration(std::wstring_view id) -> std::optional<double>
    {
        UObject* s = sound_of(id);
        if (!s) return std::nullopt;
        auto r = call_reflected(object(STR("/Script/SwtNativeAudio.Default__SwtNativeAudioManager")), STR("GetAudioAssetDuration"),
                                [&](Params& p) { p.set_nth(0, Value::of(s)); });
        return r ? std::optional<double>(r->get(L"ReturnValue").number()) : std::nullopt;
    }
    // Stop a sound play_sound (or the game) started: false for nothing.
    inline auto stop_sound(UObject* component) -> bool
    {
        if (!component || !is_a(component, STR("/Script/Engine.AudioComponent")) || !assert_game_thread(L"stop_sound")) return false;
        return call_reflected(component, STR("Stop")).has_value();
    }

    // The music: the track playing now, on the audio component the game plays music on (one whose sound is of
    // the manager's music classes, S_Class_Music). The game changes track as the cat moves between its music
    // triggers (72 in the forest, each naming a track id, mus_shadowclan_b...) and in a fight; play_music() plays
    // a track until the game next changes it (replace_sound on the track's id keeps the change).
    struct Music
    {
        UObject* component{};   // nullptr when no music plays
        std::wstring sound;     // its sound's name (MS_mus_camp_shadowclan)
        std::wstring id;        // the id it's under in AudioEventsMap, when it's one of them
    };
    namespace detail
    {
        inline auto music_classes() -> std::vector<UObject*>
        {
            std::vector<UObject*> out;
            for (Value& c : elements(get(audio_manager(), L"SoundMusicClasses")))
                if (c.object) out.push_back(c.object);
            return out;
        }
        inline auto is_music(UObject* component, const std::vector<UObject*>& classes) -> bool
        {
            UObject* s = component ? get(component, L"Sound").object : nullptr;
            return s && std::find(classes.begin(), classes.end(), get(s, L"SoundClassObject").object) != classes.end();
        }
        inline auto is_playing(UObject* component) -> bool
        {
            auto r = call_reflected(component, STR("IsPlaying"));
            return r && r->get(L"ReturnValue").boolean();
        }
        // The component the music was last found on: looked at first, so music() goes through every audio
        // component only when it has changed (a new level).
        inline auto last_music() -> UObject*&
        {
            static UObject* last{};
            return last;
        }
        inline auto music_component(bool playing_only) -> UObject*
        {
            auto classes = music_classes();
            UObject*& last = last_music();
            if (last && object_alive(last, nullptr) && is_music(last, classes) && (!playing_only || is_playing(last))) return last;
            for (UObject* c : find_all(STR("AudioComponent")))
                if (is_music(c, classes) && is_playing(c)) return last = c;
            return playing_only || !(last && object_alive(last, nullptr)) ? nullptr : last;
        }
    } // namespace detail
    inline auto music() -> Music
    {
        Music m;
        if (!assert_game_thread(L"music")) return m;
        UObject* c = detail::music_component(true);
        if (!c) return m;
        UObject* s = get(c, L"Sound").object;
        m.component = c;
        m.sound = name(s);
        for (auto& [key, sound] : map_entries(audio_manager(), L"AudioEventsMap"))
            if (sound.object == s) m.id = key.string();
        return m;
    }
    // Play one of the game's tracks by its id now (L"mus_camp"), on the music's own component (the one it was last
    // found on, even between tracks), in place of what plays; with none found, as a sound heard everywhere.
    // False for an id the game hasn't got.
    inline auto play_music(std::wstring_view id) -> bool
    {
        UObject* s = sound_of(id);
        if (!s || !assert_game_thread(L"play_music")) return false;
        Music now;
        now.component = detail::music_component(false);
        if (!now.component) return play_sound(id) != nullptr;
        call_reflected(now.component, STR("SetSound"), [&](Params& p) { p.set_nth(0, Value::of(s)); });
        return call_reflected(now.component, STR("Play"), [&](Params& p) { p.set_nth(0, Value::of(0.0)); }).has_value();
    }
    // Stop the music, fading over `seconds` (0: at once). False when none plays.
    inline auto stop_music(double seconds = 1.0) -> bool
    {
        Music now = music();
        if (!now.component) return false;
        if (seconds <= 0) return call_reflected(now.component, STR("Stop")).has_value();
        return call_reflected(now.component, STR("FadeOut"), [&](Params& p) {
                   p.set_nth(0, Value::of(seconds));
                   p.set_nth(1, Value::of(0.0));
               }).has_value();
    }

    // The game's volumes, as its Audio settings set them (0 to 1); and every sound paused or going on.
    enum class Volume
    {
        Master,
        Music,
        Effects,
        VoiceOver
    };
    inline auto set_volume(Volume which, double level) -> bool
    {
        if (!assert_game_thread(L"set_volume")) return false;
        const TCHAR* fn = which == Volume::Master ? STR("SetMasterVolume") : which == Volume::Music ? STR("SetMusicVolume")
                        : which == Volume::Effects ? STR("SetEffectsVolume") : STR("SetVoiceOverVolume");
        return call_reflected(object(STR("/Script/SwtNativeAudio.Default__SwtNativeAudioManager")), fn,
                              [&](Params& p) { p.set_nth(0, Value::of(level)); }).has_value();
    }
    inline auto pause_sounds(bool paused) -> bool
    {
        if (!assert_game_thread(L"pause_sounds")) return false;
        return call_reflected(audio_manager(), STR("PauseAllEvents"), [&](Params& p) { p.set_nth(0, Value::of(paused)); }).has_value();
    }
    inline auto sounds_paused() -> bool
    {
        auto r = call_reflected(audio_manager(), STR("IsPaused"));
        return r && r->get(L"ReturnValue").boolean();
    }

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
