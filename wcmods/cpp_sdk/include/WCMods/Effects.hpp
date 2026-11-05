// Effects.hpp: visual effects (the engine's Niagara systems, and the game's own by name), cats' and animals' movement
// values, and your cat's scent sense. Game thread only. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents
// every call.
//
//   auto fx = wcmods::game_effect(L"Poisoned", *wcmods::location(wcmods::player()));   // fx.stop() ends it
//   wcmods::set_jump_speed(wcmods::player(), 700);                                      // the cat jumps higher
//   wcmods::use_sense();                                                                // the scent sense, as Q does
#pragma once

#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // ============================================================================================ effects
    // A visual effect playing: the engine's Niagara component, which goes by itself when its system ends.
    struct Effect
    {
        UObject* component{};
        UClass* component_class{};   // what it was, to tell it's still there
        explicit operator bool() const { return component != nullptr; }
        // Whether it's still there and playing.
        auto playing() const -> bool
        {
            if (!detail::object_staying(component, component_class)) return false;
            auto r = call_reflected(component, STR("IsActive"));
            return r && r->get(L"ReturnValue").boolean();
        }
        // End it now (its component destroyed). Safe to call twice, and after it ended by itself.
        auto stop() -> void
        {
            if (detail::object_staying(component, component_class)) call_reflected(component, STR("DestroyComponent"), [&](Params& p) {
                p.set_nth(0, Value::of(false));
            });
            component = nullptr;
        }
    };
    // Play a Niagara system (its object, or its object path, loaded if it isn't yet) at a place, the engine's own
    // way (NiagaraFunctionLibrary's SpawnSystemAtLocation), going by itself when it ends. An empty Effect for a
    // system that isn't there, or outside the world.
    inline auto spawn_effect(UObject* system, Vec3 at, double scale = 1.0) -> Effect
    {
        Effect e;
        UObject* lib = object(STR("/Script/Niagara.Default__NiagaraFunctionLibrary"));
        // The world, through the player's controller: it's there in a fight too, when player() isn't.
        UObject* in_world = controller();
        if (!assert_game_thread(L"spawn_effect") || !system || !lib || !in_world) return e;
        if (!is_a(system, STR("/Script/Niagara.NiagaraSystem"))) return e;
        auto r = call_reflected(lib, STR("SpawnSystemAtLocation"), [&](Params& p) {
            p.set_nth(0, Value::of(in_world));
            p.set_nth(1, Value::of(system));
            Value where = p.nth(2);
            set(where, L"X", at.x);
            set(where, L"Y", at.y);
            set(where, L"Z", at.z);
            Value size = p.nth(4);
            for (const wchar_t* axis : {L"X", L"Y", L"Z"}) set(size, axis, scale);
            p.set_nth(5, Value::of(true));   // bAutoDestroy
            p.set_nth(6, Value::of(true));   // bAutoActivate
            p.set_nth(8, Value::of(true));   // bPreCullCheck
        });
        e.component = r ? r->get(L"ReturnValue").object : nullptr;
        e.component_class = e.component ? e.component->GetClassPrivate() : nullptr;
        return e;
    }
    inline auto spawn_effect(std::wstring_view system_path, Vec3 at, double scale = 1.0) -> Effect
    {
        if (system_path.empty()) return {};
        UObject* system = object(std::wstring(system_path).c_str());
        return spawn_effect(system ? system : load(system_path), at, scale);
    }

    namespace detail
    {
        // The game's own effects by name, from its VFX manager: L"Buff", L"Debuff", L"Climb", the status conditions'
        // (L"Poisoned", L"Blinded", L"Furious", L"Stressed": StatusNiagaraSystems) and a reward's or pickup's
        // (L"PickUp", L"Interactable", L"OnContact": RewardNiagaraSystem).
        inline auto game_effect_systems() -> std::map<std::wstring, UObject*>
        {
            std::map<std::wstring, UObject*> out;
            UObject* vfx = manager(STR("vfx"));
            if (!vfx) return out;
            for (auto [name, member] : {std::pair{L"Buff", L"BuffNiagaraSystem"}, std::pair{L"Debuff", L"DebuffNiagaraSystem"},
                                        std::pair{L"Climb", L"ClimbStartSystem"}})
                if (UObject* s = get(vfx, member).object) out[name] = s;
            for (const wchar_t* map : {L"StatusNiagaraSystems", L"RewardNiagaraSystem", L"PickedNiagaraSystem"})
                for (auto& [key, system] : map_entries(vfx, map))
                    if (system.object && !key.string().empty()) out.emplace(key.string(), system.object);
            return out;
        }
    } // namespace detail
    // The names game_effect knows, the game's own effects (its VFX manager's).
    inline auto game_effects() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        if (!assert_game_thread(L"game_effects")) return out;
        for (auto& [name, system] : detail::game_effect_systems()) out.push_back(name);
        return out;
    }
    // Play one of the game's own effects by name (game_effects()) at a place: a fight's buff and debuff, a status
    // condition's (the poison's bubbles...), the climb's start, a pickup's. An empty Effect for a name it hasn't got.
    inline auto game_effect(std::wstring_view name, Vec3 at, double scale = 1.0) -> Effect
    {
        if (!assert_game_thread(L"game_effect")) return {};
        auto systems = detail::game_effect_systems();
        auto it = systems.find(std::wstring(name));
        return it == systems.end() ? Effect{} : spawn_effect(it->second, at, scale);
    }

    // ============================================================================================ movement
    // A cat's or an animal's movement values (its CharacterMovement): walking speed (cm/s), crouched, how fast it gets
    // there, its jump's upward speed, its gravity (1 the world's), the step it walks up and its movement mode
    // (EMovementMode: L"MOVE_Walking", L"MOVE_Falling", L"MOVE_Swimming"...). Nullopt for an actor without one.
    struct Movement
    {
        double walk_speed{}, crouched_speed{}, acceleration{}, jump_speed{}, gravity{}, step_height{};
        std::wstring mode;
    };
    inline auto movement(UObject* actor) -> std::optional<Movement>
    {
        // An actor kept from earlier may be gone (a level change, the forest streaming it out): not called into then.
        if (!assert_game_thread(L"movement") || !detail::object_staying(actor, nullptr)) return std::nullopt;
        UObject* mv = get(actor, L"CharacterMovement").object;
        if (!mv) return std::nullopt;
        Movement m;
        m.walk_speed = get(mv, L"MaxWalkSpeed").number();
        m.crouched_speed = get(mv, L"MaxWalkSpeedCrouched").number();
        m.acceleration = get(mv, L"MaxAcceleration").number();
        m.jump_speed = get(mv, L"JumpZVelocity").number();
        m.gravity = get(mv, L"GravityScale").number();
        m.step_height = get(mv, L"MaxStepHeight").number();
        m.mode = get(mv, L"MovementMode").string();
        return m;
    }
    namespace detail
    {
        inline auto set_movement_value(UObject* actor, const wchar_t* member, double v) -> bool
        {
            if (!object_staying(actor, nullptr)) return false;
            UObject* mv = get(actor, L"CharacterMovement").object;
            return mv && set(mv, member, v);
        }
        // Your cat's own character (player() is nullptr in a fight, when it's the fight's actor's).
        inline auto is_your_cat(UObject* actor) -> bool
        {
            return actor && (actor == player() || name(actor->GetClassPrivate()) == L"BP_Exploration_Character_Player_C");
        }
    } // namespace detail
    // Change how high it jumps (its jump's upward speed, 420 on the test cat) and its gravity (1 the world's): the game
    // leaves both as set. False for an actor without movement.
    inline auto set_jump_speed(UObject* actor, double speed) -> bool
    {
        return assert_game_thread(L"set_jump_speed") && detail::set_movement_value(actor, L"JumpZVelocity", speed);
    }
    inline auto set_gravity(UObject* actor, double scale) -> bool
    {
        return assert_game_thread(L"set_gravity") && detail::set_movement_value(actor, L"GravityScale", scale);
    }
    // Change how fast it walks. For a mod's cat or an animal it stays; on your cat the game sets it again every frame
    // from its own walk and run settings, so it doesn't (seen: 400 read 175 a tenth of a second later), and this
    // returns false for your cat: set_player_speeds changes those.
    inline auto set_walk_speed(UObject* actor, double speed) -> bool
    {
        if (!assert_game_thread(L"set_walk_speed") || !actor || detail::is_your_cat(actor)) return false;
        return detail::set_movement_value(actor, L"MaxWalkSpeed", speed);
    }

    // ============================================================================================ your cat's speeds
    // Your cat's own speeds: its exploration component (BP_Exploration_Control) writes its character's MaxWalkSpeed
    // every frame from these, walking or (Shift) running, times the crouch or climb factor while it crouches or climbs,
    // and MaxAcceleration the same way. There's no sprint apart from running. The defaults on build 26337109 (from
    // TuningData's Gameplay.Exploration.Player.*) are in brackets.
    struct PlayerSpeeds
    {
        std::optional<double> walk;               // cm/s (175): MoveAndRun.Walk.Speed
        std::optional<double> run;                // cm/s (390): MoveAndRun.Run.Speed
        std::optional<double> walk_acceleration;  // cm/s² (175)
        std::optional<double> run_acceleration;   // cm/s² (175)
        std::optional<double> crouch;             // the factor while crouched (0.5): Crouch.Modifier.Speed
        std::optional<double> climb;              // the factor while climbing (1): Climb.Modifier.Speed
        // How it's moving now (read only): running, crouched, climbing.
        bool running{}, crouching{}, climbing{};
    };

    namespace detail
    {
        inline constexpr int speed_fields = 6;
        inline auto speed_member(UObject* explore, int which) -> float*
        {
            static constexpr const wchar_t* names[speed_fields] = {L"WCM_WalkSpeed", L"WCM_RunSpeed", L"WCM_WalkAcceleration",
                                                                   L"WCM_RunAcceleration", L"WCM_CrouchFactor", L"WCM_ClimbFactor"};
            return member<float>(explore, exploration_class, names[which]);
        }
        inline auto speed_field(PlayerSpeeds& s, int which) -> std::optional<double>&
        {
            std::optional<double>* fields[speed_fields] = {&s.walk, &s.run, &s.walk_acceleration, &s.run_acceleration,
                                                           &s.crouch, &s.climb};
            return *fields[which];
        }
        inline auto read_speeds(UObject* explore) -> PlayerSpeeds
        {
            PlayerSpeeds s;
            for (int i = 0; i < speed_fields; ++i)
                if (float* m = speed_member(explore, i)) speed_field(s, i) = *m;
            if (int32_t* flags = member<int32_t>(explore, exploration_class, L"WCM_MoveFlags"))
            {
                s.running = (*flags & 4) != 0;
                s.crouching = (*flags & 1) != 0;
                s.climbing = (*flags & 2) != 0;
            }
            return s;
        }
        // What your cat had before this mod first set them, for reset_player_speeds.
        inline auto speeds_kept() -> Kept<PlayerSpeeds>&
        {
            static Kept<PlayerSpeeds> kept;
            return kept;
        }
    } // namespace detail

    // Your cat's speeds now, every one set, and how it's moving; nullopt outside the world, in a fight (player() is
    // nullptr then), or on a build wcmods hasn't the speeds for.
    inline auto player_speeds() -> std::optional<PlayerSpeeds>
    {
        if (!assert_game_thread(L"player_speeds")) return std::nullopt;
        UObject* e = detail::exploration_control();
        if (!e || !detail::speed_member(e, 0)) return std::nullopt;
        return detail::read_speeds(e);
    }

    // Set the speeds given (the rest stay): the game takes them the next frame. The first set keeps what your cat had,
    // for reset_player_speeds. False outside the world or in a fight, or for a speed this build has nowhere for
    // (nothing set then). Lasts while your cat's character does: a level change starts it from the game's again.
    //   wcmods::set_player_speeds({.walk = 300, .run = 700});   // a quick cat
    inline auto set_player_speeds(const PlayerSpeeds& speeds) -> bool
    {
        if (!assert_game_thread(L"set_player_speeds")) return false;
        UObject* e = detail::exploration_control();
        if (!e) return false;
        PlayerSpeeds given = speeds;
        for (int i = 0; i < detail::speed_fields; ++i)
            if (detail::speed_field(given, i) && !detail::speed_member(e, i)) return false;
        detail::speeds_kept().keep(e, [&] { return detail::read_speeds(e); });
        for (int i = 0; i < detail::speed_fields; ++i)
            if (auto& v = detail::speed_field(given, i)) *detail::speed_member(e, i) = static_cast<float>(*v);
        return true;
    }

    // Put back the speeds your cat had before this mod first set them. True when there's nothing to put back (never
    // set, or the character it was set on is gone); false outside the world or in a fight (kept for another try).
    inline auto reset_player_speeds() -> bool
    {
        if (!assert_game_thread(L"reset_player_speeds")) return false;
        UObject* e = detail::exploration_control();
        if (!e) return false;
        return detail::speeds_kept().put_back(e, [](const PlayerSpeeds& before) { return set_player_speeds(before); });
    }

    // ============================================================================================ the scent sense
    // Your cat's scent sense (Q): the game's own, through its command, as the key does. It comes on over about two
    // seconds, lasts about ten and fades (its post-process component, BP_Exploration_SenseHandler). True when the
    // command was sent, which doesn't say it came on: while it's already on, another does nothing (seen); sense()
    // says what shows. False outside the world.
    inline auto use_sense() -> bool
    {
        return assert_game_thread(L"use_sense") && player() && command(L"Player_Scent_Tracking");
    }
    // How much the scent sense shows now: 0 off, 1 full (its post-process blend); nullopt outside the world.
    inline auto sense() -> std::optional<double>
    {
        if (!assert_game_thread(L"sense")) return std::nullopt;
        UObject* s = player() ? component(player(), STR("SwtAdventureExplorationSenseComponent")) : nullptr;
        if (!s) return std::nullopt;
        return get(s, L"bEnabled").boolean() ? get(s, L"BlendWeight").number() : 0.0;
    }
} // namespace wcmods
