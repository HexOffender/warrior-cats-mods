// Events.hpp: every frame, timers, keys, hooks on the game's functions, level and player events.
#include "checks.hpp"

#include <UE4SSProgram.hpp>

#include <atomic>
#include <filesystem>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        DWORD init_thread{}, game_thread{};
        std::atomic<int> frames{}, once_ran{}, every_ran{}, after_ran{}, cancelled_inside_ran{}, cancelled_before_ran{},
                cancelled_outside_ran{}, f9{}, ctrl_f9{}, pre_restart{}, post_restart{}, unhooked_ran{}, native_with{},
                native_without{}, native_read{};
        HookId native_hook{};
        std::atomic<bool> frames_on_game_thread{true}, dt_positive{true};
        TimerId cancelled_inside{}, cancelled_outside{};
        std::vector<std::string> levels;
        Json players = Json::array();
        std::string restart_self, restart_pawn, restart_pawn_after;
        bool world_done{};

        auto handle_request() -> void
        {
            auto path = mod().folder / L"request.txt";
            auto text = read_file(path);
            if (!text) return;
            std::error_code ec;
            std::filesystem::remove(path, ec);
            std::string what = *text;
            while (!what.empty() && (what.back() == '\n' || what.back() == '\r' || what.back() == ' ')) what.pop_back();
            if (what == "writes")
            {
                phase("writes");
                run_writes();
                done("writes");
            }
            else if (what == "events")
            {
                snapshot_events();
                done("events");
            }
            else if (what == "unreport")
            {
                report_quest("cpp-sdk-test");
                done("unreport");
            }
            else if (what == "unhook_native")
            {
                unhook(native_hook);
                native_hook = 0;
                done("unhook_native");
            }
        }
    } // namespace

    auto snapshot_events() -> void
    {
        value("frames", frames.load());
        value("frames.on_game_thread", frames_on_game_thread.load());
        value("frames.dt_positive", dt_positive.load());
        value("on_game_thread.ran", once_ran.load());
        value("on_game_thread.other_thread", game_thread != 0 && game_thread != init_thread);
        value("every.ran", every_ran.load());
        value("after.ran", after_ran.load());
        value("cancel.inside", cancelled_inside_ran.load());
        value("cancel.before", cancelled_before_ran.load());
        value("cancel.outside", cancelled_outside_ran.load());
        value("key.f9", f9.load());
        value("key.ctrl_f9", ctrl_f9.load());
        value("hook.pre", pre_restart.load());
        value("hook.post", post_restart.load());
        value("hook.self", restart_self);
        value("hook.pawn", restart_pawn);
        value("hook.pawn_after", restart_pawn_after);
        value("hook.unhooked_ran", unhooked_ran.load());
        value("hook.native.with", native_with.load());
        value("hook.native.without", native_without.load());
        value("hook.native.read", native_read.load());
        Json names = Json::array();
        for (auto& l : levels) names.push(l);
        value("levels", names);
        value("players", players);
        snapshot_menu();
        snapshot_story();
    }

    auto setup_events() -> void
    {
        init_thread = GetCurrentThreadId();

        every_frame([](float dt) {
            frames++;
            if (dt <= 0) dt_positive = false;
            if (game_thread && GetCurrentThreadId() != game_thread) frames_on_game_thread = false;
        });
        on_game_thread([] {
            once_ran++;
            game_thread = GetCurrentThreadId();
        });

        every(0.5, [] { every_ran++; });
        after(1.0, [] { after_ran++; });
        cancelled_inside = every(0.1, [] {
            if (++cancelled_inside_ran == 3) cancel(cancelled_inside);
        });
        TimerId never = after(100.0, [] { cancelled_before_ran++; });
        cancel(never);
        cancelled_outside = every(0.2, [] { cancelled_outside_ran++; });
        after(1.5, [] { cancel(cancelled_outside); });
        every(0.25, handle_request);

        expect("on_key", on_key(Key::F9, [] { f9++; }));
        expect("on_key.modifiers", on_key(Key::F9, {Modifier::CONTROL}, [] { ctrl_f9++; }));
        auto& program = RC::UE4SSProgram::get_program();
        expect("on_key.registered", program.is_keydown_event_registered(Key::F9));
        RC::Input::Handler::ModifierKeyArray held{};
        held[0] = Modifier::CONTROL;
        expect("on_key.modifiers_registered", program.is_keydown_event_registered(Key::F9, held));

        // The controller getting its pawn as the forest loads: before (the pawn is the parameter) and after.
        struct RestartParams
        {
            UObject* NewPawn;
        };
        HookId pre = on_function(STR("/Script/Engine.PlayerController:ClientRestart"), [](Call& call) {
            pre_restart++;
            restart_self = text(name(call.self()));
            restart_pawn = text(name(call.params<RestartParams>().NewPawn));
            // The same parameter by name and by position (Reflect.hpp), with no struct.
            if (call.param(L"NewPawn").object != call.params<RestartParams>().NewPawn || call.param(0).object != call.param(L"NewPawn").object
                || call.param(L"Nope") || call.param(7))
                restart_pawn = "param() disagreed";
        });
        HookId post = after_function(STR("/Script/Engine.PlayerController:ClientRestart"), [](Call& call) {
            post_restart++;
            restart_pawn_after = text(name(call.param(L"NewPawn").object));
        });
        expect("on_function.id", pre != 0 && post != 0 && pre != post);
        // A hook on a native function Blueprints call every frame, K2_GetActorLocation: it fires for calls
        // through the engine (with parameters) and from Blueprint bytecode (without), and the game goes on.
        // The Python side takes it off again, from outside the callback.
        native_hook = after_function(STR("/Script/Engine.Actor:K2_GetActorLocation"), [](Call& call) {
            if (!call.has_params())
            {
                native_without++;
                return;
            }
            native_with++;
            Value at = call.param(L"ReturnValue");
            if (at.kind == Value::Kind::Struct && call.param(0).kind == Value::Kind::Struct) native_read++;
        });
        expect("after_function.native", native_hook != 0);
        HookId gone = on_function(STR("/Script/Engine.PlayerController:ClientRestart"), [](Call&) { unhooked_ran++; });
        expect("unhook.id", gone != 0);
        unhook(gone);
        unhook(gone);   // a second time is harmless
        unhook(0);
        // set_return, on a function only this mod calls (run_writes reads a console variable's float value
        // through it and expects 4242 back), unhooked there afterwards.
        expect("after_function.set_return.id", forge_cvar_hook() != 0);
        expect("on_function.missing", on_function(STR("/Script/Nope.Nope:Nope"), [](Call&) {}) == 0);
        expect("after_function.missing", after_function(STR("/Script/Engine.PlayerController:NoSuchFunction"), [](Call&) {}) == 0);

        on_level([](std::wstring_view level) { levels.push_back(text(level)); });
        on_player([](UObject* cat) {
            players.push(cat ? Json(text(name(cat))) : Json());
            if (cat && !world_done)
            {
                world_done = true;
                phase("world");
                run_world(cat);
                done("world");
            }
        });
    }
} // namespace t
