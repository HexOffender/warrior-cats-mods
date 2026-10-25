// What the test mod's files share: checks and values go into results.json (main.cpp writes it), which
// tests/game/test_cpp_sdk.py reads and compares with what Lua sees.
#pragma once

#include <WCMods/WCMods.hpp>

#include <string>
#include <string_view>

namespace t
{
    using namespace wcmods;

    // A check, by name: whether it passed, and a word on what was seen. Recorded under the phase running now.
    auto expect(std::string_view name, bool ok, std::string detail = {}) -> bool;
    // A value for the Python side to compare with what Lua sees (results.json's "values").
    auto value(std::string_view name, Json v) -> void;
    // The phase checks are recorded under ("init", "world", "writes"); done(phase) marks one finished.
    auto phase(std::string_view name) -> void;
    auto done(std::string_view name) -> void;
    auto flush() -> void;   // write results.json

    auto run_core() -> void;             // Core.hpp, before the world (on UE4SS's thread)
    auto setup_events() -> void;         // Events.hpp: timers, keys, hooks, level and player events
    auto snapshot_events() -> void;      // the event counters so far, into values
    auto run_world(UObject* cat) -> void;   // Game.hpp reads, once your cat is there
    auto run_writes() -> void;           // Game.hpp writes, when the Python side asks
    auto setup_menu() -> void;           // Menu.hpp: pages, keys with help, shared values
    auto run_reflect(UObject* cat) -> void;   // Reflect.hpp, once your cat is there
    auto setup_background() -> void;     // Events.hpp: other threads, settings that change
    auto snapshot_menu() -> void;        // what the pages' rows hold, and the menu's state, into values

    // The after-hook that forges GetConsoleVariableFloatValue's result (test_events.cpp sets it up, run_writes
    // checks it and takes it out).
    inline HookId set_return_hook{};
    auto forge_cvar_hook() -> HookId;   // puts it in when it isn't (test_game.cpp)

    inline auto text(std::wstring_view w) -> std::string { return utf8(w); }
    inline auto text(const std::wstring& w) -> std::string { return utf8(w); }
} // namespace t
