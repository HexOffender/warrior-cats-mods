// WCMods/Events.hpp: when a mod's code runs: every frame, on timers, on keys, when the game calls one of its
// functions, when the level changes and when your cat appears or goes. Everything here calls back on the
// game thread, where the game's objects are safe to touch. WCMods.hpp includes it; docs/SDK.md, "C++ mods",
// documents every call.
#pragma once

#include <atomic>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <initializer_list>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>

#include <Input/KeyDef.hpp>
#include <Unreal/FFrame.hpp>
#include <Unreal/FString.hpp>
#include <Unreal/FURL.hpp>
#include <Unreal/FWorldContext.hpp>
#include <Unreal/Hooks/Hooks.hpp>
#include <Unreal/UFunctionStructs.hpp>
#include <Unreal/UObjectGlobals.hpp>

#include <WCMods/Core.hpp>
#include <WCMods/Game.hpp>

namespace wcmods
{
    using Key = RC::Input::Key;              // wcmods::Key::F6, Key::T, Key::NUM_ONE...
    using Modifier = RC::Input::ModifierKey; // wcmods::Modifier::CONTROL, SHIFT, ALT
    using TimerId = uint64_t;
    using HookId = uint64_t;

    // ============================================================================================ the game thread
    namespace detail
    {
        struct Timer
        {
            TimerId id{};
            double remaining{};
            double every{};
            bool repeat{};
            std::shared_ptr<std::function<void()>> fn;
        };
        struct PlayerWatch
        {
            std::function<void(UObject*)> fn;
            bool told{};   // whether it has had the state as it was when it was added
        };
        struct Ticks
        {
            std::mutex lock;
            std::vector<std::function<void()>> once;
            // Shared, so a frame's run works on the callbacks themselves (a lambda's own state, like a timer,
            // carries on) while another thread adds one.
            std::vector<std::shared_ptr<std::function<void(float)>>> every_frame;
            std::vector<Timer> timers;
            TimerId next_timer{1};
            std::vector<std::shared_ptr<PlayerWatch>> player_watches;
            UObject* last_player{};
            double since_player_check{};
            std::optional<RC::Unreal::Hook::GlobalCallbackId> hook;
            std::atomic<DWORD> game_thread_id{};   // known from the first frame on
        };
        inline auto ticks() -> Ticks&
        {
            static Ticks t;
            return t;
        }

        inline auto on_tick(float dt) -> void
        {
            auto& t = ticks();
            t.game_thread_id = GetCurrentThreadId();
            std::vector<std::function<void()>> once;
            std::vector<std::shared_ptr<std::function<void(float)>>> every;
            std::vector<std::shared_ptr<std::function<void()>>> due;
            std::vector<std::shared_ptr<PlayerWatch>> watches;
            bool check_player = false;
            {
                std::lock_guard lock(t.lock);
                once.swap(t.once);
                every = t.every_frame;
                for (auto it = t.timers.begin(); it != t.timers.end();)
                {
                    it->remaining -= dt;
                    if (it->remaining > 0)
                    {
                        ++it;
                        continue;
                    }
                    due.push_back(it->fn);
                    if (it->repeat)
                    {
                        it->remaining = it->every;
                        ++it;
                    }
                    else
                    {
                        it = t.timers.erase(it);
                    }
                }
                t.since_player_check += dt;
                if (!t.player_watches.empty() && t.since_player_check >= 0.25)
                {
                    t.since_player_check = 0;
                    check_player = true;
                    watches = t.player_watches;
                }
            }
            for (auto& fn : once) guarded(L"on_game_thread", fn);
            for (auto& fn : every) guarded(L"every_frame", [&] { (*fn)(dt); });
            for (auto& fn : due) guarded(L"a timer", [&] { (*fn)(); });
            if (check_player)
            {
                UObject* now = player();
                bool changed;
                {
                    std::lock_guard lock(t.lock);
                    changed = now != t.last_player;
                    t.last_player = now;
                }
                for (auto& w : watches)
                {
                    if (!changed && w->told) continue;
                    w->told = true;
                    guarded(L"on_player", [&] { w->fn(now); });
                }
            }
        }

        inline auto hook_ticks() -> void
        {
            auto& t = ticks();
            std::lock_guard lock(t.lock);   // no frame runs on_tick before the hook is in, so this can't wait on one
            if (t.hook) return;
            RC::Unreal::Hook::FCallbackOptions options{};
            options.OwnerModName = mod().name;
            options.HookName = STR("wcmods ticks");
            t.hook = RC::Unreal::Hook::RegisterEngineTickPostCallback(
                    [](auto&, RC::Unreal::UEngine*, float dt, bool) { on_tick(dt); }, options);
        }
    } // namespace detail

    // Run `fn` once on the game thread, at the end of the next frame. Call it from on_unreal_init or later.
    inline auto on_game_thread(std::function<void()> fn) -> void
    {
        auto& t = detail::ticks();
        {
            std::lock_guard lock(t.lock);
            t.once.push_back(std::move(fn));
        }
        detail::hook_ticks();
    }

    // Run `fn(seconds since the last frame)` on the game thread at the end of every frame, from now until the
    // game closes. Call it from on_unreal_init or later. Keep it quick: the game waits for it.
    inline auto every_frame(std::function<void(float)> fn) -> void
    {
        auto& t = detail::ticks();
        {
            std::lock_guard lock(t.lock);
            t.every_frame.push_back(std::make_shared<std::function<void(float)>>(std::move(fn)));
        }
        detail::hook_ticks();
    }

    // ============================================================================================ timers
    namespace detail
    {
        inline auto add_timer(double seconds, bool repeat, std::function<void()> fn) -> TimerId
        {
            auto& t = ticks();
            TimerId id;
            {
                std::lock_guard lock(t.lock);
                id = t.next_timer++;
                t.timers.push_back({id, seconds, seconds, repeat, std::make_shared<std::function<void()>>(std::move(fn))});
            }
            hook_ticks();
            return id;
        }
    } // namespace detail

    // `fn()` on the game thread every so many seconds (of real time), starting that long from now:
    //   wcmods::every(5, [] { wcmods::cat().heal(); });
    inline auto every(double seconds, std::function<void()> fn) -> TimerId { return detail::add_timer(seconds, true, std::move(fn)); }

    // `fn()` once on the game thread, that many seconds from now.
    inline auto after(double seconds, std::function<void()> fn) -> TimerId { return detail::add_timer(seconds, false, std::move(fn)); }

    // Stop a timer. Fine to call from inside its own callback.
    inline auto cancel(TimerId id) -> void
    {
        auto& t = detail::ticks();
        std::lock_guard lock(t.lock);
        std::erase_if(t.timers, [&](const detail::Timer& timer) { return timer.id == id; });
    }

    // ============================================================================================ your cat's comings and goings
    // `fn(cat)` when your cat appears (the forest loads), changes (a new area) or goes (menus; nullptr), on
    // the game thread, looked for four times a second; and once right away, with how things are now.
    inline auto on_player(std::function<void(UObject*)> fn) -> void
    {
        auto& t = detail::ticks();
        {
            std::lock_guard lock(t.lock);
            t.player_watches.push_back(std::make_shared<detail::PlayerWatch>(detail::PlayerWatch{std::move(fn), false}));
            t.since_player_check = 1;   // look on the next frame
        }
        detail::hook_ticks();
    }

    // ============================================================================================ other threads
    // Whether this is the game thread (known once a frame has run; false before). assert_game_thread says
    // so in the log when it isn't: for a mod's own checks on code that must only run there.
    inline auto on_game_thread_now() -> bool
    {
        DWORD game = detail::ticks().game_thread_id;
        return game != 0 && GetCurrentThreadId() == game;
    }
    inline auto assert_game_thread(const wchar_t* what = L"this") -> bool
    {
        if (on_game_thread_now()) return true;
        detail::log_line(mod().name, std::format(L"{} ran off the game thread; the game's objects aren't safe there", what));
        return false;
    }

    // Heavy work (a file, the network, a long computation) on a thread of its own, then `then(result)` on the
    // game thread with what it gave back. `work` must not touch the game's objects; `then` may:
    //   wcmods::run_in_background([] { return read_big_file(); }, [](std::string data) { use(data); });
    template <typename Work, typename Then>
    auto run_in_background(Work work, Then then) -> void
    {
        std::thread([work = std::move(work), then = std::move(then)]() mutable {
            using Result = decltype(work());
            if constexpr (std::is_void_v<Result>)
            {
                bool ok = true;
                detail::guarded(L"run_in_background", [&] { work(); });
                if (ok) on_game_thread([then = std::move(then)]() mutable { then(); });
            }
            else
            {
                std::optional<Result> result;
                detail::guarded(L"run_in_background", [&] { result = work(); });
                if (result) on_game_thread([then = std::move(then), r = std::move(*result)]() mutable { then(std::move(r)); });
            }
        }).detach();
    }
    // The same for work that gives nothing back and needs nothing after.
    inline auto run_in_background(std::function<void()> work) -> void
    {
        std::thread([work = std::move(work)] { detail::guarded(L"run_in_background", work); }).detach();
    }

    // ============================================================================================ settings that change
    namespace detail
    {
        struct SettingsWatch
        {
            std::mutex lock;
            std::vector<std::shared_ptr<std::function<void()>>> fns;
            bool started{};
            std::filesystem::file_time_type seen{};
            uintmax_t size{};
        };
        inline auto settings_watch() -> SettingsWatch&
        {
            static SettingsWatch w;
            return w;
        }
        inline auto settings_stamp(std::filesystem::file_time_type& when, uintmax_t& size) -> bool
        {
            std::error_code ec;
            const auto& path = mod().settings_file;
            if (path.empty() || !std::filesystem::is_regular_file(path, ec)) return false;
            when = std::filesystem::last_write_time(path, ec);
            size = std::filesystem::file_size(path, ec);
            return !ec;
        }
    } // namespace detail

    // `fn()` on the game thread when settings.json changed on disk (the studio, a text editor, Save on its
    // page from another install), after settings() has been read again. Looked for once a second.
    inline auto on_settings_changed(std::function<void()> fn) -> void
    {
        auto& w = detail::settings_watch();
        bool start = false;
        {
            std::lock_guard lock(w.lock);
            w.fns.push_back(std::make_shared<std::function<void()>>(std::move(fn)));
            if (!w.started)
            {
                w.started = start = true;
                detail::settings_stamp(w.seen, w.size);
            }
        }
        if (!start) return;
        every(1.0, [] {
            auto& w = detail::settings_watch();
            std::filesystem::file_time_type when{};
            uintmax_t size{};
            if (!detail::settings_stamp(when, size)) return;
            std::vector<std::shared_ptr<std::function<void()>>> fns;
            {
                std::lock_guard lock(w.lock);
                if (when == w.seen && size == w.size) return;
                w.seen = when;
                w.size = size;
                fns = w.fns;
            }
            if (!reload_settings()) return;
            for (auto& f : fns) detail::guarded(L"on_settings_changed", [&] { (*f)(); });
        });
    }

    // ============================================================================================ keys
    namespace detail
    {
        // Keys go through UE4SS's mod object (ModBase sets this up), so a key is tied to the mod and goes
        // with it. The mod's callback gets the game thread.
        using KeyBinder = std::function<void(Key, const std::vector<Modifier>&, std::function<void()>)>;
        inline auto key_binder() -> KeyBinder&
        {
            static KeyBinder binder;
            return binder;
        }
        inline auto bind_key(Key key, const std::vector<Modifier>& modifiers, std::function<void()> fn) -> bool
        {
            if (!key_binder())
            {
                log_line(mod().name, L"on_key needs the mod to be a wcmods::ModBase");
                return false;
            }
            auto shared = std::make_shared<std::function<void()>>(std::move(fn));
            // The key's callback comes on UE4SS's input thread and hands the work to the game thread; the hook
            // that carries it goes in now, from the mod's own thread, rather than from the input thread at the
            // first press.
            hook_ticks();
            key_binder()(key, modifiers, [shared] { on_game_thread([shared] { (*shared)(); }); });
            return true;
        }
    } // namespace detail

    // `fn()` on the game thread when a key is pressed, in the game or out of it, from on_unreal_init or later:
    //   wcmods::on_key(wcmods::Key::F6, [] { wcmods::cat().heal(); });
    //   wcmods::on_key(wcmods::Key::H, {wcmods::Modifier::CONTROL}, [] { ... });
    // UE4SS sees the keyboard only (not a controller), and both the game and your mod get the key.
    inline auto on_key(Key key, std::function<void()> fn) -> bool { return detail::bind_key(key, {}, std::move(fn)); }
    inline auto on_key(Key key, std::initializer_list<Modifier> modifiers, std::function<void()> fn) -> bool
    {
        return detail::bind_key(key, std::vector<Modifier>(modifiers), std::move(fn));
    }

    // ============================================================================================ hooks on the game's functions
    // A call of one of the game's functions, handed to on_function and after_function callbacks.
    struct Call
    {
        RC::Unreal::UnrealScriptFunctionCallableContext& context;

        // The object the function was called on.
        auto self() -> UObject* { return context.Context; }
        // Its parameters, as a struct laid out like them (see wcmods::call). Changing them before the call
        // (on_function) changes what the game does.
        template <typename Params>
        auto params() -> Params&
        {
            return context.GetParams<Params>();
        }
        // Set what the function gives back (after_function).
        template <typename T>
        auto set_return(T value) -> void
        {
            context.SetReturnValue(value);
        }
    };

    namespace detail
    {
        struct FunctionHook
        {
            std::wstring path;
            UFunction* function{};
            std::pair<int, int> ids;   // UE4SS's ids for the pre and post callbacks
        };
        struct FunctionHooks
        {
            std::mutex lock;
            std::map<HookId, FunctionHook> hooks;
            HookId next{1};
        };
        inline auto function_hooks() -> FunctionHooks&
        {
            static FunctionHooks h;
            return h;
        }

        inline auto hook_function(const TCHAR* path, std::function<void(Call&)> before, std::function<void(Call&)> after) -> HookId
        {
            using Context = RC::Unreal::UnrealScriptFunctionCallableContext;
            auto wrap = [](std::function<void(Call&)> fn, const wchar_t* when) {
                auto shared = std::make_shared<std::function<void(Call&)>>(std::move(fn));
                return [shared, when](Context& context, void*) {
                    if (!*shared) return;
                    Call call{context};
                    guarded(when, [&] { (*shared)(call); });
                };
            };
            // Looked up here: UE4SS's own lookup hands a function it can't find on as a null pointer.
            UFunction* function = RC::Unreal::UObjectGlobals::StaticFindObject<UFunction*>(nullptr, nullptr, path);
            if (!function)
            {
                log_line(mod().name, std::format(L"can't hook {}: no such function", path));
                return 0;
            }
            std::pair<int, int> ids;
            try
            {
                ids = RC::Unreal::UObjectGlobals::RegisterHook(function, wrap(std::move(before), L"on_function"),
                                                              wrap(std::move(after), L"after_function"), nullptr);
            }
            catch (const std::exception& e)
            {
                log_line(mod().name, std::format(L"can't hook {}: {}", path, wide(e.what())));
                return 0;
            }
            auto& h = function_hooks();
            std::lock_guard lock(h.lock);
            HookId id = h.next++;
            h.hooks[id] = {std::wstring(path), function, ids};
            return id;
        }
    } // namespace detail

    // `fn(call)` on the game thread just before the game runs one of its functions, named by its full path
    // ("/Script/Wrc.GuiHudWrc:OnItemPickedUp"; Blueprint functions too, "/Game/.../BP_X.BP_X_C:Name"):
    //   wcmods::on_function(STR("/Script/Wrc.GuiHudWrc:OnItemPickedUp"), [](wcmods::Call& c) {
    //       struct Params { RC::Unreal::FName Tag; int32_t Quantity; int32_t Total; };   // a gameplay tag is an FName
    //       wcmods::log(L"picked up {}: {} now", c.params<Params>().Tag.ToString(), c.params<Params>().Total);
    //   });
    // 0 (and a line in the log) when there's no such function. The function must be one the game calls
    // through the engine (a Blueprint one, or a native one marked as an event); native code calling native
    // code directly is never seen.
    inline auto on_function(const TCHAR* path, std::function<void(Call&)> fn) -> HookId
    {
        return detail::hook_function(path, std::move(fn), {});
    }

    // The same, just after the function ran: its outputs and return value are filled in.
    inline auto after_function(const TCHAR* path, std::function<void(Call&)> fn) -> HookId
    {
        return detail::hook_function(path, {}, std::move(fn));
    }

    inline auto unhook(HookId id) -> void
    {
        auto& h = detail::function_hooks();
        detail::FunctionHook found;
        {
            std::lock_guard lock(h.lock);
            auto it = h.hooks.find(id);
            if (it == h.hooks.end()) return;
            found = it->second;
            h.hooks.erase(it);
        }
        try
        {
            RC::Unreal::UObjectGlobals::UnregisterHook(found.function, found.ids);
        }
        catch (const std::exception& e)
        {
            detail::log_line(mod().name, std::format(L"can't unhook {}: {}", found.path, wide(e.what())));
        }
        catch (...)
        {
            detail::log_line(mod().name, std::format(L"can't unhook {}", found.path));
        }
    }

    // ============================================================================================ the level
    namespace detail
    {
        struct LevelWatch
        {
            std::mutex lock;
            std::vector<std::shared_ptr<std::function<void(std::wstring_view)>>> fns;
            std::optional<RC::Unreal::Hook::GlobalCallbackId> hook;
        };
        inline auto level_watch() -> LevelWatch&
        {
            static LevelWatch w;
            return w;
        }
    } // namespace detail

    // `fn(level name)` on the game thread once a level has loaded: "L_WorldMap_01_P" for the forest, the
    // main menu's and the others' names otherwise. The game destroys its actors on the way, so anything
    // kept from before is gone; look it up again.
    inline auto on_level(std::function<void(std::wstring_view)> fn) -> void
    {
        auto& w = detail::level_watch();
        std::lock_guard lock(w.lock);
        w.fns.push_back(std::make_shared<std::function<void(std::wstring_view)>>(std::move(fn)));
        if (w.hook) return;
        RC::Unreal::Hook::FCallbackOptions options{};
        options.OwnerModName = mod().name;
        options.HookName = STR("wcmods levels");
        options.bReadonly = true;
        w.hook = RC::Unreal::Hook::RegisterLoadMapPostCallback(
                [](auto&, RC::Unreal::UEngine*, RC::Unreal::FWorldContext&, RC::Unreal::FURL, RC::Unreal::UPendingNetGame*,
                   RC::Unreal::FString&) {
                    std::vector<std::shared_ptr<std::function<void(std::wstring_view)>>> fns;
                    {
                        std::lock_guard lock(detail::level_watch().lock);
                        fns = detail::level_watch().fns;
                    }
                    std::wstring level = level_name();
                    for (auto& fn : fns) detail::guarded(L"on_level", [&] { (*fn)(level); });
                },
                options);
    }

    // ============================================================================================ shutdown
    namespace detail
    {
        // Called as the mod is taken out (WCMODS_MOD's uninstall_mod): nothing of its may run after that.
        inline auto stop() -> void
        {
            auto& t = ticks();
            std::optional<RC::Unreal::Hook::GlobalCallbackId> hook;
            {
                std::lock_guard lock(t.lock);
                hook.swap(t.hook);
                t.once.clear();
                t.every_frame.clear();
                t.timers.clear();
                t.player_watches.clear();
            }
            // Outside the lock: a frame running now takes it in on_tick, and unregistering may wait for that frame.
            if (hook) RC::Unreal::Hook::UnregisterCallback(*hook);

            auto& w = level_watch();
            std::optional<RC::Unreal::Hook::GlobalCallbackId> level_hook;
            {
                std::lock_guard lock(w.lock);
                level_hook.swap(w.hook);
                w.fns.clear();
            }
            if (level_hook) RC::Unreal::Hook::UnregisterCallback(*level_hook);

            auto& h = function_hooks();
            std::vector<HookId> ids;
            {
                std::lock_guard lock(h.lock);
                for (auto& [id, _] : h.hooks) ids.push_back(id);
            }
            for (HookId id : ids) unhook(id);
        }
    } // namespace detail
} // namespace wcmods
