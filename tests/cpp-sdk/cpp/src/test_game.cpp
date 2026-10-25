// Game.hpp: the game's objects, the world and its managers, your cat, the clock, the fresh-kill pile and the
// developer switches. Reads once your cat is there; writes when the Python side asks, which then reads them
// back through Lua.
#include "checks.hpp"

#include <cmath>
#include <cstdint>

namespace t
{
    namespace
    {
        constexpr auto DEV_SWITCH = STR("bAllowAlwaysEquipItem");
        constexpr auto CVAR = STR("r.ScreenPercentage");

        auto cvar_int(const TCHAR* name) -> std::optional<int32_t>
        {
            struct Params
            {
                RC::Unreal::FString VariableName;
                int32_t ReturnValue;
            } p{RC::Unreal::FString(name), 0};
            if (!call(object(STR("/Script/Engine.Default__KismetSystemLibrary")), STR("GetConsoleVariableIntValue"), p)) return std::nullopt;
            return p.ReturnValue;
        }

        auto vec(const Vec3& v) -> Json
        {
            Json j = Json::array();
            j.push(v.x);
            j.push(v.y);
            j.push(v.z);
            return j;
        }

        auto game_objects(UObject* actor) -> void
        {
            UObject* c = controller();
            expect("controller", c != nullptr);
            expect("player", player() == actor && actor != nullptr);
            value("player.name", text(name(actor)));
            value("player.full_name", text(full_name(actor)));
            value("player.class", text(class_name(actor)));
            expect("name.null", name(nullptr).empty() && full_name(nullptr).empty() && class_name(nullptr).empty());
            auto pawn = property<UObject*>(c, STR("Pawn"));
            expect("property", pawn && *pawn == actor);
            expect("property.missing", property<float>(actor, STR("NoSuchProperty")) == nullptr && property<float>(nullptr, STR("Pawn")) == nullptr);
            auto dilation = property<float>(actor, STR("CustomTimeDilation"));
            expect("property.float", dilation && *dilation > 0.f);

            UClass* actor_class = find_class(STR("/Script/Engine.Actor"));
            expect("find_class", actor_class != nullptr && find_class(STR("/Script/Engine.Actor")) == actor_class);
            expect("find_class.missing", find_class(STR("/Script/Nope.Nope")) == nullptr);
            expect("object", object(STR("/Script/Engine.Default__KismetSystemLibrary")) != nullptr && object(STR("/Script/Nope.Nope")) == nullptr);
            auto controllers = find_all(STR("PlayerController"));
            bool has = false;
            for (UObject* o : controllers) has = has || o == c;
            expect("find_all", !controllers.empty() && has, std::to_string(controllers.size()));
            expect("find_all.missing", find_all(STR("NoSuchClassAnywhere")).empty());
            expect("find_first", find_first(STR("PlayerController")) != nullptr && find_first(STR("NoSuchClassAnywhere")) == nullptr);
            expect("is_a", is_a(actor, STR("/Script/Engine.Pawn")) && is_a(actor, STR("/Script/Engine.Actor"))
                              && !is_a(actor, STR("/Script/Engine.PlayerController")) && !is_a(nullptr, STR("/Script/Engine.Actor"))
                              && !is_a(actor, STR("/Script/Nope.Nope")));

            struct Clock
            {
                int32_t Hours, Minutes, Seconds;
            } t{};
            expect("call.params", call(game_state(), STR("GetDayClockTime"), t) && 0 <= t.Hours && t.Hours < 24);
            value("call.clock.hours", t.Hours);
            value("call.clock.minutes", t.Minutes);
            expect("call.none", call(c, STR("ClientClearCameraLensEffects")));
            auto called_dilation = call<float>(actor, STR("GetActorTimeDilation"));
            auto ticking = call<bool>(actor, STR("IsActorTickEnabled"));
            expect("call.result", called_dilation && *called_dilation == 1.f && ticking.has_value(),
                   called_dilation ? std::to_string(*called_dilation) : "(none)");
            expect("call.refused", !call(nullptr, STR("IsActorTickEnabled")) && !call(actor, STR("NoSuchFunction"))
                                       && !call<bool>(actor, STR("NoSuchFunction")) && !call<double>(actor, STR("GetActorTimeDilation"))
                                       && !call(actor, STR("GetActorTimeDilation")));

            expect("world", world() != nullptr);
            value("level_name", text(level_name()));
            value("game_instance.class", text(class_name(game_instance())));
            value("game_state.class", text(class_name(game_state())));
            value("game_mode.class", text(class_name(game_mode())));
            UObject* quests = manager(STR("quests"));
            expect("manager", quests != nullptr && manager(STR("QuestManager")) == quests && manager(STR("cheats")) != nullptr);
            expect("manager.missing", manager(STR("nope")) == nullptr && manager(STR("NoSuchManager")) == nullptr);
            value("manager.quests.class", text(class_name(quests)));
            UObject* health = component(actor, STR("SwtQuestHealthComponent"));
            expect("component", health != nullptr && component(nullptr, STR("SwtQuestHealthComponent")) == nullptr
                                   && component(actor, STR("NoSuchComponent")) == nullptr);
            value("component.health.class", text(class_name(health)));
        }

        auto game_cat(UObject* actor) -> void
        {
            Cat c = cat();
            expect("cat", c && c.actor == actor);
            Cat none{nullptr};
            expect("cat.none", !none && !none.health() && !none.level() && !none.location() && !none.scale() && !none.teleport({0, 0, 0})
                                  && !none.set_scale(1) && !none.heal() && !none.time_dilation() && !none.stat(Stat::Agility));

            Resource hp = c.health();
            expect("cat.health", hp && *hp.value > 0 && *hp.value <= *hp.max);
            value("cat.health", hp ? Json(*hp.value) : Json());
            value("cat.max_health", hp ? Json(*hp.max) : Json());
            Resource same = resource(actor, STR("SwtQuestHealthComponent"));
            expect("resource", same.value == hp.value && same.max == hp.max);
            Resource st = c.stamina();
            expect("cat.stamina", st && *st.value >= 0 && *st.max > 0);
            value("cat.max_stamina", st ? Json(*st.max) : Json());
            auto regen = c.stamina_regen();
            expect("cat.stamina_regen", regen != nullptr && *regen > 0);
            value("cat.stamina_regen", regen ? Json(*regen) : Json());
            Resource combat = c.combat_stamina();
            value("cat.combat_stamina.present", static_cast<bool>(combat));   // only in a fight
            expect("cat.level_component", c.level_component() != nullptr);
            auto level = c.level();
            expect("cat.level", level && *level >= 1 && *level <= 20);
            value("cat.level", level ? Json(*level) : Json());
            auto xp = c.xp();
            auto needed = c.xp_needed();
            expect("cat.xp", xp && needed && *xp >= 0 && *needed >= 0);
            value("cat.xp", xp ? Json(*xp) : Json());
            auto strength = c.stat(Stat::Strength);
            expect("cat.stat", strength && *strength > 0 && c.stat(Stat::Prowess) && c.stat(Stat::Resilience) && c.stat(Stat::Instinct)
                                  && c.stat(Stat::Agility) && c.stat(Stat::Stamina) && c.stat(Stat::Agility) != strength);
            value("cat.stat.Strength", strength ? Json(*strength) : Json());
            value("cat.stat.Agility", c.stat(Stat::Agility) ? Json(*c.stat(Stat::Agility)) : Json());
            auto at = c.location();
            expect("cat.location", at.has_value() && location(actor) && location(actor)->x == at->x);
            if (at) value("cat.location", vec(*at));
            auto scale = c.scale();
            expect("cat.scale", scale && *scale > 0);
            value("cat.scale", scale ? Json(*scale) : Json());
            auto dilation = c.time_dilation();
            expect("cat.time_dilation", dilation && *dilation == 1.f);
            FVector f = to_fvector({1.5, -2, 3});
            Vec3 back = to_vec3(f);
            expect("vec3.round_trip", back.x == 1.5 && back.y == -2 && back.z == 3);
            expect("teleport.null", !teleport(nullptr, {0, 0, 0}) && !location(nullptr));

            // ----- the status condition: the game's own members on the status component
            expect("cat.status_component", c.status_component() != nullptr && class_name(c.status_component()) == L"SwtAdventureStatusComponent");
            auto status = c.status();
            auto rounds = c.status_rounds();
            expect("cat.status", status && rounds && *status <= 4 && *rounds >= 0);
            value("cat.status", status ? Json(*status) : Json());
            value("cat.status_rounds", rounds ? Json(*rounds) : Json());
            auto cure = c.self_cure_chance();
            auto poison = c.poison_damage();
            expect("cat.status_tuning", cure && poison && *cure > 0 && *cure < 1 && *poison > 0 && *poison < 1);
            value("cat.self_cure_chance", cure ? Json(*cure) : Json());
            value("cat.poison_damage", poison ? Json(*poison) : Json());
            expect("cat.none.status", !none.status_component() && !none.status() && !none.status_rounds() && !none.apply_status(1)
                                          && !none.remove_status(1) && !none.clear_status());
        }

        auto game_world_state() -> void
        {
            auto now = time_of_day();
            auto secs = day_seconds();
            expect("time_of_day", now && secs && now->hours == static_cast<int>(*secs / 3600) % 24
                                     && now->minutes == static_cast<int>(*secs / 60) % 60);
            value("time.seconds", secs ? Json(*secs) : Json());
            value("time.hours", now ? Json(now->hours) : Json());
            Resource fk = fresh_kill();
            expect("fresh_kill", fk && *fk.max > 0 && *fk.value >= 0 && fresh_kill_component() != nullptr);
            value("fresh_kill.value", fk ? Json(*fk.value) : Json());
            value("fresh_kill.max", fk ? Json(*fk.max) : Json());
            value("fresh_kill.component.class", text(class_name(fresh_kill_component())));
            FreshKillDecay decay = fresh_kill_decay();
            expect("fresh_kill_decay", decay && *decay.period > 0 && *decay.elapsed >= 0);
            value("fresh_kill.decay.period", decay ? Json(*decay.period) : Json());
            bool* sw = dev_switch(DEV_SWITCH);
            expect("dev_switch", sw != nullptr && dev_switch(STR("bNoSuchSwitch")) == nullptr);
            value("dev_switch.value", sw ? Json(*sw) : Json());
            auto cvar = cvar_int(CVAR);
            expect("cvar.read", cvar.has_value());
            value("cvar.before", cvar ? Json(*cvar) : Json());
        }
    } // namespace

    auto forge_cvar_hook() -> HookId
    {
        if (!set_return_hook)
        {
            set_return_hook = after_function(STR("/Script/Engine.KismetSystemLibrary:GetConsoleVariableFloatValue"),
                                             [](Call& call) { call.set_return<float>(4242.f); });
        }
        return set_return_hook;
    }

    auto run_world(UObject* actor) -> void
    {
        game_objects(actor);
        game_cat(actor);
        game_world_state();
        run_reflect(actor);
        run_world_more(actor);
    }

    auto run_writes() -> void
    {
        Cat c = cat();
        if (!expect("writes.cat", static_cast<bool>(c))) return;

        // A condition given through the game's function shows in the member with its rounds at 1, goes when
        // taken off, and clears; the member is the game's own, so Lua sees the same (test_status_seen_by_cpp).
        if (uint8_t* status = c.status(); status && c.status_rounds())
        {
            bool applied = c.apply_status(1) && *status == 1 && *c.status_rounds() == 1;
            bool removed = c.remove_status(1) && *status == 0;
            bool cleared = c.apply_status(3) && *status == 3 && c.clear_status() && *status == 0;
            expect("status.round_trip", applied && removed && cleared,
                   std::to_string(applied) + std::to_string(removed) + std::to_string(cleared));
        }
        else expect("status.round_trip", false, "no status members");

        Resource hp = c.health();
        if (hp)
        {
            float was = *hp.value;
            *hp.value = *hp.max / 2;
            expect("writes.health_pointer", *hp.value == *hp.max / 2);
            expect("heal", c.heal() && *hp.value == *hp.max, std::to_string(was));
        }
        Resource st = c.stamina();
        if (st)
        {
            *st.value = 5;
            expect("writes.stamina_pointer", *st.value == 5);
        }
        if (auto strength = c.stat(Stat::Strength))
        {
            float was = *strength;
            *strength = was + 1;
            expect("writes.stat_pointer", *c.stat(Stat::Strength) == was + 1);
            *strength = was;
        }
        if (auto xp = c.xp())
        {
            float was = *xp;
            *xp = was + 1;
            expect("writes.xp_pointer", *c.xp() == was + 1);
            *xp = was;
        }
        if (auto level = c.level())
        {
            int32_t was = *level;
            *level = was;   // the same value back: the pointer is writable, the save unchanged
            expect("writes.level_pointer", *c.level() == was);
        }

        value("writes.time.before", day_seconds() ? Json(*day_seconds()) : Json());
        expect("set_time", set_time(12, 30) && day_seconds() && std::fabs(*day_seconds() - 45000) < 2);
        expect("set_time.wraps", set_time(25, 0, 0) && std::fabs(*day_seconds() - 3600) < 2 && set_time(-1) && std::fabs(*day_seconds() - 82800) < 2);
        set_time(12, 30);
        value("writes.time.after", *day_seconds());

        auto before = c.location();
        if (before)
        {
            value("writes.location.before", vec(*before));
            Vec3 to{before->x + 150, before->y, before->z + 50};
            bool moved = c.teleport(to);
            auto after = c.location();
            expect("teleport", moved && after && std::fabs(after->x - to.x) < 1 && std::fabs(after->y - to.y) < 1);
            value("writes.teleport.ok", moved);
            if (after) value("writes.location.after", vec(*after));
        }
        expect("set_scale", c.set_scale(1.5) && c.scale() && std::fabs(*c.scale() - 1.5) < 0.001);
        value("writes.scale", c.scale() ? Json(*c.scale()) : Json());

        if (bool* sw = dev_switch(DEV_SWITCH))
        {
            *sw = !*sw;
            value("writes.dev_switch", *sw);
        }

        Resource fk = fresh_kill();
        if (fk)
        {
            value("writes.fresh_kill.before", *fk.value);
            *fk.value = *fk.max > 10 ? *fk.max - 10 : *fk.max;
            expect("writes.fresh_kill_pointer", *fresh_kill().value == *fk.value);
            // The decay timer back to the start of its period, so the pile can't drop before Lua reads it.
            FreshKillDecay decay = fresh_kill_decay();
            if (decay) *decay.elapsed = 0;
            expect("writes.fresh_kill_decay_pointer", decay && *fresh_kill_decay().elapsed < 1);
            value("writes.fresh_kill.after", *fk.value);
        }

        // The after-hook forges this function's result; after unhook it's real again. Put in here as well as at
        // init, so a second writes phase in one session has it too.
        forge_cvar_hook();
        struct FloatParams
        {
            RC::Unreal::FString VariableName;
            float ReturnValue;
        } fp{RC::Unreal::FString(CVAR), 0.f};
        UObject* kismet = object(STR("/Script/Engine.Default__KismetSystemLibrary"));
        bool called = call(kismet, STR("GetConsoleVariableFloatValue"), fp);
        expect("set_return", called && fp.ReturnValue == 4242.f, std::to_string(fp.ReturnValue));
        unhook(set_return_hook);
        set_return_hook = 0;
        FloatParams real{RC::Unreal::FString(CVAR), 0.f};
        call(kismet, STR("GetConsoleVariableFloatValue"), real);
        expect("set_return.unhooked", real.ReturnValue != 4242.f, std::to_string(real.ReturnValue));

        auto cvar = cvar_int(CVAR);
        int32_t want = cvar && *cvar != 83 ? 83 : 84;
        expect("console", console((std::wstring(CVAR) + L" " + std::to_wstring(want)).c_str()));
        auto now = cvar_int(CVAR);
        expect("console.took", now && *now == want, now ? std::to_string(*now) : "(none)");
        value("writes.cvar", now ? Json(*now) : Json());

        Json& s = settings();
        double runs = s["runs"].number();
        {
            std::lock_guard lock(settings_lock());
            s.set("runs", runs + 1);
            s.set("written_by", "test_game.cpp");
        }
        expect("save_settings", save_settings());
        value("writes.runs", runs + 1);
        log(L"writes done");
    }

    auto snapshot_status() -> void
    {
        Cat c = cat();
        auto status = c.status();
        auto rounds = c.status_rounds();
        value("status.now", status ? Json(*status) : Json());
        value("status.rounds.now", rounds ? Json(*rounds) : Json());
    }
} // namespace t
