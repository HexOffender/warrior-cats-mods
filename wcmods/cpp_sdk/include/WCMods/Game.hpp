// WCMods/Game.hpp: the game through UE4SS: its objects, the world and its managers, your cat, the clock, the
// fresh-kill pile and the developer switches. Game thread only: call these from Events.hpp's every_frame,
// timers, keys and hooks, or from on_unreal_init and later in a UE4SS hook. WCMods.hpp includes it;
// docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

#include <Unreal/AActor.hpp>
#include <Unreal/CoreUObject/UObject/Class.hpp>
#include <Unreal/FString.hpp>
#include <Unreal/NameTypes.hpp>
#include <Unreal/UObject.hpp>
#include <Unreal/UObjectGlobals.hpp>
#include <Unreal/UnrealCoreStructs.hpp>
#include <Unreal/World.hpp>

#include <WCMods/Core.hpp>

namespace wcmods
{
    using RC::Unreal::AActor;
    using RC::Unreal::FVector;
    using RC::Unreal::TCHAR;
    using RC::Unreal::UClass;
    using RC::Unreal::UFunction;
    using RC::Unreal::UWorld;

    // ============================================================================================ objects
    // Names: "BP_Exploration_Character_Player_C_2147479642", the full path, and the class's name.
    inline auto name(UObject* o) -> std::wstring { return o ? o->GetName() : std::wstring{}; }
    inline auto full_name(UObject* o) -> std::wstring { return o ? o->GetFullName() : std::wstring{}; }
    inline auto class_name(UObject* o) -> std::wstring
    {
        return o && o->GetClassPrivate() ? o->GetClassPrivate()->GetName() : std::wstring{};
    }

    // A pointer to a reflected property's value inside an object (its own or a parent class's), or nullptr:
    //   UObject** pawn = wcmods::property<UObject*>(controller, STR("Pawn"));
    //   float* dilation = wcmods::property<float>(cat, STR("CustomTimeDilation"));
    template <typename T>
    auto property(UObject* object, const TCHAR* name) -> T*
    {
        if (!object) return nullptr;
        return object->GetValuePtrByPropertyNameInChain<T>(name);
    }

    // A class by its path ("/Script/SwtAdventure.SwtAdventureCharacter"), or nullptr. Classes last the whole
    // run, so one found is kept.
    inline auto find_class(const TCHAR* path) -> UClass*
    {
        static std::mutex lock;
        static std::unordered_map<std::wstring, UClass*> found;
        std::wstring key(path);
        {
            std::lock_guard guard(lock);
            if (auto it = found.find(key); it != found.end()) return it->second;
        }
        UClass* cls = RC::Unreal::UObjectGlobals::StaticFindObject<UClass*>(nullptr, nullptr, path);
        if (cls)
        {
            std::lock_guard guard(lock);
            found[key] = cls;
        }
        return cls;
    }

    // Any object by its full path ("/Script/Engine.Default__GameplayStatics"), or nullptr.
    inline auto object(const TCHAR* path) -> UObject*
    {
        return RC::Unreal::UObjectGlobals::StaticFindObject<UObject*>(nullptr, nullptr, path);
    }

    // Every object of a class, by its short name ("WrcRoamingEnemy"), subclasses too. It goes through all
    // the game's objects: a few times a second is fine, every frame isn't.
    inline auto find_all(const TCHAR* class_name) -> std::vector<UObject*>
    {
        std::vector<UObject*> found;
        RC::Unreal::UObjectGlobals::FindAllOf(class_name, found);
        return found;
    }

    // The first object of a class, by its short name, or nullptr.
    inline auto find_first(const TCHAR* class_name) -> UObject*
    {
        return RC::Unreal::UObjectGlobals::FindFirstOf(class_name);
    }

    // Whether an object is of a class (by its path), or a subclass.
    inline auto is_a(UObject* o, const TCHAR* class_path) -> bool
    {
        UClass* cls = find_class(class_path);
        return o && cls && o->IsA(cls);
    }

    // Call one of an object's reflected functions (its own or a parent class's), with a struct laid out
    // like its parameters: the inputs, then the outputs, then the return value, in the order the function
    // declares them, each aligned as C++ would:
    //   struct { int32_t Hours; int32_t Minutes; int32_t Seconds; } t{};
    //   wcmods::call(wcmods::game_state(), STR("GetDayClockTime"), t);
    // False when the object or the function isn't there. `python wcmods.py inspect "Game.gameState()"`
    // lists an object's functions with their parameters.
    template <typename Params>
    auto call(UObject* object, const TCHAR* function, Params& params) -> bool
    {
        if (!object) return false;
        UFunction* fn = object->GetFunctionByNameInChain(function);
        if (!fn) return false;
        object->ProcessEvent(fn, &params);
        return true;
    }

    // The same for a function that takes nothing and gives nothing back.
    inline auto call(UObject* object, const TCHAR* function) -> bool
    {
        if (!object) return false;
        UFunction* fn = object->GetFunctionByNameInChain(function);
        if (!fn || fn->GetParmsSize() != 0) return false;
        object->ProcessEvent(fn, nullptr);
        return true;
    }

    // The same for a function that takes nothing and gives one value back, which this returns (nullopt when
    // the function isn't there, or its result isn't that size):
    //   auto dilation = wcmods::call<float>(cat, STR("GetActorTimeDilation"));
    template <typename R>
    auto call(UObject* object, const TCHAR* function) -> std::optional<R>
    {
        if (!object) return std::nullopt;
        UFunction* fn = object->GetFunctionByNameInChain(function);
        if (!fn || fn->GetParmsSize() != sizeof(R)) return std::nullopt;
        R result{};
        object->ProcessEvent(fn, &result);
        return result;
    }

    // ============================================================================================ the world
    // The player's controller, or nullptr (in menus, while loading).
    inline auto controller() -> UObject*
    {
        for (UObject* c : find_all(STR("PlayerController")))
        {
            auto player = property<UObject*>(c, STR("Player"));
            if (player && *player) return c;
        }
        return nullptr;
    }

    // Your cat's actor (the player's pawn) while you play, else nullptr.
    inline auto player() -> UObject*
    {
        auto pawn = property<UObject*>(controller(), STR("Pawn"));
        if (!pawn || !*pawn) return nullptr;
        return is_a(*pawn, STR("/Script/SwtAdventure.SwtAdventureCharacter")) ? *pawn : nullptr;
    }

    // The world, or nullptr: through the player's controller, else the engine's viewport.
    inline auto world() -> UObject*
    {
        if (UObject* c = controller())
            if (UWorld* w = static_cast<AActor*>(c)->GetWorld()) return w;
        auto viewport = property<UObject*>(find_first(STR("GameEngine")), STR("GameViewport"));
        auto w = viewport && *viewport ? property<UObject*>(*viewport, STR("World")) : nullptr;
        return w ? *w : nullptr;
    }

    // The level's name: "L_WorldMap_01_P" in the forest, "L_MainMenu…" and others elsewhere; empty between.
    inline auto level_name() -> std::wstring { return name(world()); }

    inline auto game_instance() -> UObject*
    {
        auto gi = property<UObject*>(world(), STR("OwningGameInstance"));
        return gi && *gi ? *gi : find_first(STR("GameInstance"));
    }
    inline auto game_state() -> UObject*
    {
        auto gs = property<UObject*>(world(), STR("GameState"));
        return gs ? *gs : nullptr;
    }
    inline auto game_mode() -> UObject*
    {
        auto gm = property<UObject*>(world(), STR("AuthorityGameMode"));
        return gm ? *gm : nullptr;
    }

    // The game's managers, which hang off its game instance: by a short name ("quests", "save", "cheats",
    // "combat", "npcs", "tuning"...), or by the property that holds one ("QuestManager"). nullptr when the
    // game instance isn't up yet.
    inline auto manager(const TCHAR* which) -> UObject*
    {
        static const std::pair<std::wstring_view, const TCHAR*> names[] = {
            {L"config", STR("GameConfig")}, {L"util", STR("GameUtil")}, {L"save", STR("SaveManager")},
            {L"gui", STR("GuiManager")}, {L"cheats", STR("CheatsManager")}, {L"flow", STR("FlowManager")},
            {L"storage", STR("StorageManager")}, {L"services", STR("GameServices")},
            {L"analytics", STR("AnalyticsManager")}, {L"online", STR("OnlineServicesManager")},
            {L"achievements", STR("AchievementsManager")}, {L"records", STR("RecordsManager")},
            {L"challenges", STR("ChallengesManager")}, {L"montages", STR("MontagesManager")},
            {L"tracer", STR("ActorTracerManager")}, {L"vfx", STR("VfxManager")}, {L"quests", STR("QuestManager")},
            {L"sequencer", STR("SequencerManager")}, {L"tuning", STR("TuningManager")},
            {L"audio", STR("NativeAudioManager")}, {L"cloud", STR("OnlineCloudManager")},
            {L"effects", STR("EffectManager")}, {L"npcs", STR("NPCGenerationManager")},
            {L"combat", STR("CombatManager")}, {L"paths", STR("TrackPathManager")}, {L"tutorial", STR("TutorialManager")},
        };
        const TCHAR* prop = which;
        for (auto& [short_name, property_name] : names)
            if (short_name == which) prop = property_name;
        auto m = property<UObject*>(game_instance(), prop);
        return m ? *m : nullptr;
    }

    // An actor's component of a class, by its short name ("SwtQuestHealthComponent"), or nullptr.
    inline auto component(UObject* owner, const TCHAR* class_name) -> UObject*
    {
        if (!owner) return nullptr;
        for (UObject* c : find_all(class_name))
            if (c->GetOuterPrivate() == owner) return c;
        return nullptr;
    }

    // Run a console command as the player ("stat fps", "r.ScreenPercentage 80"; cheat commands like "slomo 0.5"
    // work once the mod menu's Cheats page has turned cheats on), the way the mod menu's console box does.
    // False without a player.
    inline auto console(const TCHAR* command) -> bool
    {
        UObject* c = controller();
        if (!c) return false;
        struct Params
        {
            UObject* WorldContextObject;
            RC::Unreal::FString Command;
            UObject* SpecificPlayer;
        } params{c, RC::Unreal::FString(command), c};
        return call(object(STR("/Script/Engine.Default__KismetSystemLibrary")), STR("ExecuteConsoleCommand"), params);
    }

    // ============================================================================================ places
    struct Vec3
    {
        double x{}, y{}, z{};
    };
    inline auto to_vec3(FVector v) -> Vec3 { return {v.X(), v.Y(), v.Z()}; }
    inline auto to_fvector(Vec3 v) -> FVector
    {
        FVector f;
        f.SetX(v.x);
        f.SetY(v.y);
        f.SetZ(v.z);
        return f;
    }

    // Where an actor is, or nullopt.
    inline auto location(UObject* actor) -> std::optional<Vec3>
    {
        if (!actor) return std::nullopt;
        return to_vec3(static_cast<AActor*>(actor)->K2_GetActorLocation());
    }

    // Move an actor there, keeping its facing. False when it isn't there or the game refuses.
    inline auto teleport(UObject* actor, Vec3 to) -> bool
    {
        if (!actor) return false;
        auto* a = static_cast<AActor*>(actor);
        return a->K2_TeleportTo(to_fvector(to), a->K2_GetActorRotation());
    }

    // ============================================================================================ your cat
    // One of a cat's resources (health, stamina): pointers to its value now and its maximum, which you can
    // read and write; empty (false) when the cat or its component isn't there, or wcmods hasn't got the
    // members on this game build. Pointers into the game's objects are good for this frame: look them
    // up again next time rather than keeping them.
    struct Resource
    {
        float* value{};
        float* max{};
        explicit operator bool() const { return value && max; }
    };

    // A resource component of an actor's, by the component's class: how the Cat calls below find theirs.
    inline auto resource(UObject* owner, const TCHAR* component_class) -> Resource
    {
        UObject* c = component(owner, component_class);
        constexpr auto cls = L"/Script/SwtQuest.SwtQuestResourceComponent";
        return {member<float>(c, cls, L"WCM_Value"), member<float>(c, cls, L"WCM_Max")};
    }

    enum class Stat { Prowess, Strength, Resilience, Instinct, Agility, Stamina };

    // Your cat (wcmods::cat()), or any cat's actor. Everything gives nullptr / nullopt / an empty Resource
    // when the cat isn't there, so a check is one `if`.
    struct Cat
    {
        UObject* actor{};
        explicit operator bool() const { return actor != nullptr; }

        auto component(const TCHAR* class_name) -> UObject* { return wcmods::component(actor, class_name); }

        auto health() -> Resource { return resource(actor, STR("SwtQuestHealthComponent")); }
        auto stamina() -> Resource { return resource(actor, STR("SwtQuestStaminaComponent")); }
        auto combat_stamina() -> Resource { return resource(actor, STR("SwtCombatStaminaComponent")); }
        // Stamina back per second (20 in the game as it ships).
        auto stamina_regen() -> float*
        {
            return member<float>(component(STR("SwtQuestStaminaComponent")), L"/Script/SwtQuest.SwtQuestStaminaComponent", L"WCM_Regen");
        }
        // Full health; false when the cat or its maximum isn't there.
        auto heal() -> bool
        {
            Resource hp = health();
            if (!hp) return false;
            *hp.value = *hp.max;
            return true;
        }

        // The level component holds the level, the experience and the stats out of combat. For your cat it's
        // on the player state (through the controller), not the actor.
        auto level_component() -> UObject*
        {
            auto controller = property<UObject*>(actor, STR("Controller"));
            auto state = controller && *controller ? property<UObject*>(*controller, STR("PlayerState")) : nullptr;
            return wcmods::component(state ? *state : nullptr, STR("SwtAdventureLevelComponent"));
        }
        auto level() -> int32_t*
        {
            return member<int32_t>(level_component(), L"/Script/SwtAdventure.SwtAdventureLevelComponent", L"WCM_Level");
        }
        // Experience, and what the next level needs.
        auto xp() -> float* { return member<float>(level_component(), L"/Script/SwtQuest.SwtQuestResourceComponent", L"WCM_Value"); }
        auto xp_needed() -> float* { return member<float>(level_component(), L"/Script/SwtQuest.SwtQuestResourceComponent", L"WCM_Max"); }
        auto stat(Stat which) -> float*
        {
            static constexpr const wchar_t* names[] = {L"WCM_Prowess", L"WCM_Strength", L"WCM_Resilience",
                                                       L"WCM_Instinct", L"WCM_Agility", L"WCM_Stamina"};
            return member<float>(level_component(), L"/Script/SwtAdventure.SwtAdventureLevelComponent",
                                 names[static_cast<int>(which)]);
        }

        auto location() -> std::optional<Vec3> { return wcmods::location(actor); }
        auto teleport(Vec3 to) -> bool { return wcmods::teleport(actor, to); }
        // The cat's size (the actor's scale, 1 as it ships), as the mod menu's size cheat does it.
        auto scale() -> std::optional<double>
        {
            if (!actor) return std::nullopt;
            return static_cast<AActor*>(actor)->GetActorScale3D().X();
        }
        auto set_scale(double factor) -> bool
        {
            if (!actor) return false;
            static_cast<AActor*>(actor)->SetActorScale3D(to_fvector({factor, factor, factor}));
            return true;
        }
        // How fast time runs for the cat alone (1 as it ships).
        auto time_dilation() -> float* { return property<float>(actor, STR("CustomTimeDilation")); }
    };

    // Your cat while you play; empty (false) in menus and while loading.
    inline auto cat() -> Cat { return Cat{player()}; }

    // ============================================================================================ the world's state
    struct ClockTime
    {
        int32_t hours{}, minutes{}, seconds{};
    };
    // The clock as the game shows it, or nullopt outside the forest.
    inline auto time_of_day() -> std::optional<ClockTime>
    {
        struct Params
        {
            int32_t Hours, Minutes, Seconds;
        } t{};
        if (!call(game_state(), STR("GetDayClockTime"), t)) return std::nullopt;
        return ClockTime{t.Hours, t.Minutes, t.Seconds};
    }
    // Seconds into the day (0 at midnight, 21600 at 6:00), to read and write; nullptr outside the forest or
    // when wcmods hasn't got the member on this build.
    inline auto day_seconds() -> float*
    {
        return member<float>(game_state(), L"/Script/SwtAdventure.SwtAdventureGameplayGameState", L"WCM_DayTime");
    }
    inline auto set_time(int hours, int minutes = 0, int seconds = 0) -> bool
    {
        float* s = day_seconds();
        if (!s) return false;
        *s = static_cast<float>(((hours * 3600 + minutes * 60 + seconds) % 86400 + 86400) % 86400);
        return true;
    }

    // The fresh-kill pile: its component, how full it is (value and max), and its decay (seconds since it
    // last dropped, counting up, and how many seconds between drops: 90 as the game ships).
    inline auto fresh_kill_component() -> UObject*
    {
        auto c = property<UObject*>(game_state(), STR("FreshKillPileComponent"));
        return c ? *c : nullptr;
    }
    inline auto fresh_kill() -> Resource
    {
        UObject* c = fresh_kill_component();
        constexpr auto cls = L"/Script/SwtQuest.SwtQuestResourceComponent";
        return {member<float>(c, cls, L"WCM_Value"), member<float>(c, cls, L"WCM_Max")};
    }
    struct FreshKillDecay
    {
        float* elapsed{};
        float* period{};
        explicit operator bool() const { return elapsed && period; }
    };
    inline auto fresh_kill_decay() -> FreshKillDecay
    {
        UObject* c = fresh_kill_component();
        constexpr auto cls = L"/Script/SwtAdventure.SwtAdventureFreshKillPileComponent";
        return {member<float>(c, cls, L"WCM_DecayTimer"), member<float>(c, cls, L"WCM_DecayTime")};
    }

    // One of the game's developer switches, on its cheats manager: a bool to read and write, or nullptr.
    // The mod menu's Cheats page lists them (and `python wcmods.py inspect "Game.dev.manager()"`).
    inline auto dev_switch(const TCHAR* name) -> bool* { return property<bool>(manager(STR("cheats")), name); }
} // namespace wcmods
