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
    auto run_world_more(UObject* cat) -> void;   // World.hpp and Story.hpp reads, once your cat is there
    auto setup_story() -> void;          // Story.hpp: the events, and a quest report
    auto snapshot_story() -> void;       // the events' counts, into values
    auto snapshot_menu() -> void;        // what the pages' rows hold, and the menu's state, into values
    auto snapshot_status() -> void;      // your cat's status condition members now, into values (test_game.cpp)
    auto snapshot_fight() -> void;       // the fight's fighters with their hidden members, into values (test_world.cpp)
    auto snapshot_items() -> void;       // items() and the kept save now, into values (test_world.cpp)
    auto setup_ui() -> void;             // Ui.hpp: a tab in the pause screen, a screen watch (test_ui.cpp)
    auto run_ui() -> void;               // Ui.hpp: every widget, an overlay, the HUD, on the game thread when asked
    auto snapshot_ui() -> void;          // the tab's and page's state and the events so far, into values
    auto teardown_ui() -> void;          // the overlay and the HUD label off again
    auto run_tables_units() -> void;     // Tables.hpp's tuning map reader, without the game (test_tables.cpp)
    auto run_tables_request() -> void;   // Tables.hpp: the DataTables and the tuning, in the game ("tables")
    auto run_words_request() -> void;    // Words.hpp: the game's words, in the game ("words")
    auto run_sounds_request() -> void;   // sounds and music (World.hpp), in the game ("sounds")
    auto run_npcs_request() -> void;     // Npcs.hpp: a cat of the mod's own, in the game ("npcs")
    auto run_talks_request() -> void;    // Talk.hpp: conversations, in the game ("talks")
    auto run_ai_request() -> void;         // Ai.hpp: the game's AI, in the game ("ai")
    auto run_ai_move_request() -> void;    // Ai.hpp: moving an AI ("ai_move")
    auto run_ai_trees_request() -> void;   // Ai.hpp: swapping trees, following ("ai_trees")
    auto run_ai_fight_request() -> void;   // Ai.hpp: a fight's AI ("ai_fight")
    auto run_ai_notice_request() -> void;  // Ai.hpp: noticing your cat ("ai_notice")
    auto run_bond_answers_request() -> void;   // Bonds.hpp and Talk.hpp: a story talk and its answers' bonds ("bond_answers")
    auto run_bonds_request() -> void;    // Bonds.hpp: your cat's bonds, in the game ("bonds")
    auto run_looks_request() -> void;    // Looks.hpp: cats' looks and the clan's cats, in the game ("looks")
    auto run_items_request() -> void;    // Items.hpp: items, and pickups dropped and collected, in the game ("drop")
    auto run_quests_request() -> void;   // Story.hpp: quests, scenes, dilemmas, in the game ("questline")
    auto run_fights_request() -> void;   // Story.hpp: fights started, won, fled and lost, in the game ("fights")
    auto run_dens_request() -> void;     // Dens.hpp: dens, hotspots, decorations placed, timed, taken off ("dens")
    auto run_map_request() -> void;      // Map.hpp: the HUD's quest pieces, markers, the clock, travel, the camera ("map")
    auto run_map_end_request() -> void;  // the markers taken off, the clock let go ("map_end")
    auto run_camera_request() -> void;   // Map.hpp's camera settings: read, set, held, put back ("camera")
    auto run_scenes_request() -> void;      // Story.hpp: the scenes the game has, one played and skipped ("scenes")
    auto run_photo_request() -> void;       // Map.hpp: photo mode on, its UI hidden and shown, a photo, off ("photo")
    auto run_map_travel_request() -> void;  // Map.hpp: a place unlocked, travelled to through the map and back ("map_travel")
    auto run_effects_request() -> void;  // Effects.hpp: effects played and stopped, movement, the sense ("effects")
    auto run_speeds_request() -> void;   // Effects.hpp: your cat's speeds read, set, taken by the game, put back ("speeds")
    auto run_anims_request() -> void;    // Animations.hpp: mods' animations played and stopped, in the game ("anims")
    auto run_ui_units() -> void;         // Ui.hpp's rule for the arrows on a tab's page, without the game (test_ui.cpp)
    auto run_native_units() -> void;     // Core.hpp's pattern check and World.hpp's map reader, without the game (test_native.cpp)
    auto run_native_request(const std::string& what) -> bool;   // native, inventory_add, command_open, sky, sound...: false for another

    // The after-hook that forges GetConsoleVariableFloatValue's result (test_events.cpp sets it up, run_writes
    // checks it and takes it out).
    inline HookId set_return_hook{};
    auto forge_cvar_hook() -> HookId;   // puts it in when it isn't (test_game.cpp)

    inline auto text(std::wstring_view w) -> std::string { return utf8(w); }
    inline auto text(const std::wstring& w) -> std::string { return utf8(w); }
} // namespace t
