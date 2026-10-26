// WCMods/Mod.hpp: the mod's own class, and the two functions UE4SS calls in its main.dll. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods".
#pragma once

#include <array>
#include <functional>
#include <vector>

#include <Mod/CppUserModBase.hpp>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Menu.hpp>
#include <WCMods/UiLua.hpp>

namespace wcmods
{
    // A UE4SS C++ mod named and described from its mod.json (through wcmods.json). Derive from it, override
    // UE4SS's on_unreal_init (and the rest of RC::CppUserModBase as you need), and end the file with
    // WCMODS_MOD(YourClass).
    class ModBase : public RC::CppUserModBase
    {
      public:
        ModBase()
        {
            const ModInfo& m = mod();
            ModName = m.name;
            ModVersion = m.version;
            ModAuthors = m.author;
            ModDescription = m.description;
            // wcmods::on_key binds keys through this mod, so UE4SS ties them to it.
            detail::key_binder() = [this](Key key, const std::vector<Modifier>& modifiers, std::function<void()> fn) {
                if (modifiers.empty())
                {
                    register_keydown_event(key, fn);
                    return;
                }
                RC::Input::Handler::ModifierKeyArray held{};   // unused slots stay MOD_KEY_START_OF_ENUM
                for (size_t i = 0; i < modifiers.size() && i < held.size(); ++i) held[i] = modifiers[i];
                register_keydown_event(key, held, fn);
            };
        }

        ~ModBase() override { detail::key_binder() = nullptr; }

        // Each Lua mod's state gets WCModsCpp as it starts, for the mod menu and shared values (Menu.hpp) and
        // the game's UI (UiLua.hpp). A
        // mod that overrides this calls ModBase::on_lua_start from its own, or loses those. (UE4SS's
        // register_on_lua_start is left to the mod: it keeps one function a mod, and this doesn't take it.)
        auto on_lua_start(RC::StringViewType mod_name, RC::LuaMadeSimple::Lua& lua, RC::LuaMadeSimple::Lua& main_lua,
                          RC::LuaMadeSimple::Lua& async_lua, RC::LuaMadeSimple::Lua* hook_lua) -> void override
        {
            RC::CppUserModBase::on_lua_start(mod_name, lua, main_lua, async_lua, hook_lua);
            detail::lua_started(lua);
            detail::lua_started_ui(lua);
        }
    };
} // namespace wcmods

// The two functions UE4SS calls in a C++ mod's main.dll: one makes the mod, the other takes it out.
#define WCMODS_MOD(ModClass)                                                                                   \
    extern "C" __declspec(dllexport) RC::CppUserModBase* start_mod()                                           \
    {                                                                                                          \
        return new ModClass();                                                                                 \
    }                                                                                                          \
    extern "C" __declspec(dllexport) void uninstall_mod(RC::CppUserModBase* mod)                               \
    {                                                                                                          \
        ::wcmods::detail::stop();                                                                              \
        ::wcmods::detail::stop_menu();                                                                         \
        ::wcmods::detail::stop_ui();                                                                           \
        delete mod;                                                                                            \
    }
