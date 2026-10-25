// WCMods.hpp: wcmods' C++ SDK, on top of UE4SS's own. A C++ mod's source (cpp/src/) includes it, and
// `wcmods cpp build` puts it on the include path. docs/SDK.md, "C++ mods", documents every call.
//
//   #include <WCMods/WCMods.hpp>
//
//   class MyMod : public wcmods::ModBase
//   {
//     public:
//       auto on_unreal_init() -> void override
//       {
//           wcmods::every(0.25, [] {
//               if (auto hp = wcmods::cat().health()) *hp.value = *hp.max;   // never hurt
//           });
//           wcmods::on_key(wcmods::Key::F7, [] { wcmods::set_time(6); });   // dawn
//       }
//   };
//   WCMODS_MOD(MyMod)
//
// It's five headers, which this one includes:
//   WCMods/Core.hpp     text, JSON, files, the mod's info and settings, the log, the game's hidden members
//   WCMods/Game.hpp     the game's objects, the world and its managers, your cat, the clock, the fresh-kill pile
//   WCMods/Reflect.hpp  any property by its path, as the kind it is; arrays, maps, structs; calling by
//                       reflection; spawning actors
//   WCMods/World.hpp    what's nearby, the game's screens and input, traces, the save, items, cats' names
//   WCMods/Story.hpp    quests, fights, and the game's events as one list
//   WCMods/Events.hpp   every frame, timers, keys, hooks on the game's functions, level and player events,
//                       other threads, settings that change on disk
//   WCMods/Menu.hpp     pages in the mod menu (a settings page comes free), keys on its Overview, values
//                       shared with Lua mods
//   WCMods/Mod.hpp      wcmods::ModBase and WCMODS_MOD
//
// Anything that touches the game's objects runs on the game thread: inside every_frame, a timer, a key, a
// hook, on_player or on_level, and after on_unreal_init. (UE4SS calls on_update from a thread of its own.)
// Look objects up again rather than keeping them: the game destroys its actors when the level changes.
#pragma once

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Menu.hpp>
#include <WCMods/Mod.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/Story.hpp>
#include <WCMods/World.hpp>
