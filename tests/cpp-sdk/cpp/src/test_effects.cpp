// Effects, movement and the scent sense (Effects.hpp), on request ("effects"), for tests/game/test_cpp_sdk.py. The
// game's own effects by name and a Niagara system by its path, each seen playing and one stopped; your cat's movement
// values, its jump and gravity changed and put back, its walk speed refused, an animal's walk speed; the sense used.
#include "checks.hpp"

#include <memory>
#include <string>

namespace t
{
    auto run_effects_request() -> void
    {
        phase("effects");
        auto me = location(player());
        if (!me) return done("effects");
        const Vec3 above{me->x, me->y, me->z + 50};
        // ----- the game's effects, and one by its path
        Json names = Json::array();
        for (auto& n : game_effects()) names.push(Json(text(n)));
        value("effects.names", names);
        auto poison = std::make_shared<Effect>(game_effect(L"Poisoned", above));
        auto buff = std::make_shared<Effect>(spawn_effect(L"/Game/Art/Vfx/Niagaras/Animations/Animation_Combat/NS_Buff.NS_Buff", above));
        expect("effects.refused", !game_effect(L"NoSuchEffect", above) && !spawn_effect(static_cast<UObject*>(nullptr), above)
                                      && !spawn_effect(player(), above) && !spawn_effect(L"", above));
        // ----- movement
        if (auto m = movement(player()))
        {
            Json o = Json::object();
            o.set("walk", Json(m->walk_speed));
            o.set("jump", Json(m->jump_speed));
            o.set("gravity", Json(m->gravity));
            o.set("mode", Json(text(m->mode)));
            value("effects.movement", o);
        }
        expect("effects.walk_refused", !set_walk_speed(player(), 400) && !set_walk_speed(nullptr, 400) && !movement(nullptr)
                                           && !set_jump_speed(nullptr, 1) && !set_gravity(nullptr, 1));
        expect("effects.jump", set_jump_speed(player(), 700) && set_gravity(player(), 0.8));
        // An animal's walk speed (one roaming nearby)
        UObject* animal = nullptr;
        for (auto& n : nearby(Kind::Creatures, 5000))
            if (full_name(n.actor).find(L"MovieScene") == std::wstring::npos && movement(n.actor)) animal = n.actor;
        double animal_was = animal ? movement(animal)->walk_speed : 0;
        if (animal) expect("effects.animal_walk", set_walk_speed(animal, animal_was + 111));
        // ----- the scent sense
        value("effects.sense_before", sense() ? Json(*sense()) : Json());
        expect("effects.use_sense", use_sense());
        after(0.3, [poison, buff] {
            value("effects.poison_playing", poison->playing());
            value("effects.buff_playing", buff->playing());
            poison->stop();
            value("effects.poison_stopped", !poison->playing() && !*poison);
        });
        after(1.0, [animal, animal_was] {
            if (auto m = movement(player()))
            {
                value("effects.jump_after", Json(m->jump_speed));
                value("effects.gravity_after", Json(m->gravity));
            }
            if (animal && movement(animal)) value("effects.animal_walk_after", Json(movement(animal)->walk_speed - animal_was));
            set_jump_speed(player(), 420);
            set_gravity(player(), 1.0);
            if (animal) set_walk_speed(animal, animal_was);
        });
        after(3.0, [buff] {
            value("effects.sense_3s", sense() ? Json(*sense()) : Json());
            buff->stop();
            done("effects");
        });
    }

    namespace
    {
        auto speeds_json(const PlayerSpeeds& s) -> Json
        {
            Json o = Json::object();
            auto put = [&](const char* name, const std::optional<double>& v) { o.set(name, v ? Json(*v) : Json()); };
            put("walk", s.walk);
            put("run", s.run);
            put("walk_acceleration", s.walk_acceleration);
            put("run_acceleration", s.run_acceleration);
            put("crouch", s.crouch);
            put("climb", s.climb);
            o.set("running", Json(s.running));
            o.set("crouching", Json(s.crouching));
            o.set("climbing", Json(s.climbing));
            return o;
        }
        auto movement_now(const char* key) -> void
        {
            UObject* mv = get(player(), L"CharacterMovement").object;
            Json o = Json::object();
            o.set("walk", Json(get(mv, L"MaxWalkSpeed").number()));
            o.set("acceleration", Json(get(mv, L"MaxAcceleration").number()));
            value(key, o);
        }
    } // namespace

    auto run_speeds_request() -> void
    {
        phase("speeds");
        auto before = player_speeds();
        expect("speeds.read", before.has_value());
        if (!before) return done("speeds");
        value("speeds.before", speeds_json(*before));
        movement_now("speeds.movement_before");
        expect("speeds.set", set_player_speeds({.walk = 400, .run = 800, .walk_acceleration = 900}));
        after(0.5, [] {
            movement_now("speeds.movement_set");   // the game's own write, a few frames on
            if (auto s = player_speeds()) value("speeds.set_read", speeds_json(*s));
            expect("speeds.set_again", set_player_speeds({.climb = 2}));   // keeps the first "before"
            expect("speeds.reset", reset_player_speeds());
            after(0.5, [] {
                movement_now("speeds.movement_reset");
                if (auto s = player_speeds()) value("speeds.reset_read", speeds_json(*s));
                expect("speeds.reset_again", reset_player_speeds());
                done("speeds");
            });
        });
    }
} // namespace t
