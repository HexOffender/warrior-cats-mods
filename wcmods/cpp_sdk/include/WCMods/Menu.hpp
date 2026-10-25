// WCMods/Menu.hpp: the mod menu for C++ mods, and values C++ and Lua mods share. UE4SS hands a C++ mod every
// Lua mod's state as it starts, and wcmods puts a WCModsCpp.mods[<id>] table into each: the mod menu (a Lua
// script, WCModsMenuHost) draws a C++ mod's pages and lists its keys through it, and Lua and C++ pass values
// to each other through it. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call.
//
//   wcmods::menu_page(L"My mod", [](wcmods::Ui& ui) {
//       ui.heading(L"My mod");
//       on = ui.on_off(L"Enabled", on);
//       speed = ui.slider(L"Speed", speed, 0.5, 3, {.step = 0.1, .format = L"x%.1f"});
//       if (ui.button(L"Save", L"primary")) wcmods::save_settings();
//   });
//
// A mod with a settings.json gets a page of its settings without asking (settings_page(false) turns it off),
// as script mods do. Pages draw on the game thread, every frame while they show.
#pragma once

#include <algorithm>
#include <cmath>
#include <functional>
#include <initializer_list>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <LuaMadeSimple/LuaMadeSimple.hpp>
#include <Mod/CppUserModBase.hpp>
#include <lua.hpp>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>

namespace wcmods
{
    namespace detail
    {
        inline auto lua_push_text(lua_State* L, std::wstring_view text) -> void
        {
            std::string u = utf8(text);
            lua_pushlstring(L, u.data(), u.size());
        }
        inline auto lua_text(lua_State* L, int index, std::wstring_view fallback) -> std::wstring
        {
            size_t n = 0;
            const char* s = lua_type(L, index) == LUA_TSTRING ? lua_tolstring(L, index, &n) : nullptr;
            return s ? wide(std::string_view(s, n)) : std::wstring(fallback);
        }
        inline auto lua_set_field(lua_State* L, const char* key, double value) -> void
        {
            lua_pushnumber(L, value);
            lua_setfield(L, -2, key);
        }
        inline auto lua_set_field(lua_State* L, const char* key, bool value) -> void
        {
            lua_pushboolean(L, value);
            lua_setfield(L, -2, key);
        }
        inline auto lua_set_field(lua_State* L, const char* key, std::wstring_view value) -> void
        {
            lua_push_text(L, value);
            lua_setfield(L, -2, key);
        }
        inline auto lua_push_list(lua_State* L, std::initializer_list<std::wstring_view> items) -> void
        {
            lua_newtable(L);
            int i = 1;
            for (auto item : items)
            {
                lua_push_text(L, item);
                lua_rawseti(L, -2, i++);
            }
        }

        // Call ui.<name>(args...) on the ui table at `table`, with `push_args` pushing the arguments and giving
        // their count, and `read` reading the one result at the top of the stack; `fallback` when the call
        // can't be made. The stack is left as it was.
        template <typename Result, typename Push, typename Read>
        auto ui_call(lua_State* L, int table, const char* name, Result fallback, Push&& push_args, Read&& read) -> Result
        {
            int top = lua_gettop(L);
            lua_getfield(L, table, name);
            if (!lua_isfunction(L, -1))
            {
                lua_settop(L, top);
                return fallback;
            }
            int nargs = push_args();
            if (lua_pcall(L, nargs, 1, 0) != LUA_OK)
            {
                size_t n = 0;
                const char* why = lua_tolstring(L, -1, &n);
                log_line(mod().name, std::format(L"ui.{}: {}", wide(name), why ? wide(std::string_view(why, n)) : L"error"));
                lua_settop(L, top);
                return fallback;
            }
            Result r = read();
            lua_settop(L, top);
            return r;
        }
    } // namespace detail

    // ============================================================================================ a page's rows
    // The `ui` a page's function gets: each call is one row of the page, and gives back what the player set it
    // to, or the value it was given when they didn't touch it (these call WCModsMenu's ui.* in Lua). Text is
    // wide here; the conversion to Lua's UTF-8 is done for you.
    class Ui
    {
      public:
        struct SliderOptions
        {
            double step{};           // 0: smooth
            std::wstring format;     // how the value shows, like L"x%.1f"
        };
        struct NumberOptions
        {
            std::optional<double> min, max;
            double step{1};
            bool whole{false};       // whole numbers only, shown without decimals
        };

        Ui(lua_State* L, int table) : m_L(L), m_table(lua_absindex(L, table)) {}

        // A heading; wrapped text; smaller grey text.
        auto heading(std::wstring_view text) -> void { row("heading", text); }
        auto text(std::wstring_view text) -> void { row("text", text); }
        auto note(std::wstring_view text) -> void { row("note", text); }
        // A line; some room (in pixels, as on a 1080-pixel screen).
        auto separator() -> void
        {
            detail::ui_call<int>(m_L, m_table, "separator", 0, [] { return 0; }, [] { return 0; });
        }
        auto space(double height) -> void
        {
            detail::ui_call<int>(m_L, m_table, "space", 0, [&] { lua_pushnumber(m_L, height); return 1; }, [] { return 0; });
        }
        // A name and its value, for showing something.
        auto field(std::wstring_view label, std::wstring_view value) -> void
        {
            detail::ui_call<int>(m_L, m_table, "field", 0, [&] { push(label); push(value); return 2; }, [] { return 0; });
        }
        // A bar from 0 to 1.
        auto progress(std::wstring_view label, double fraction) -> void
        {
            detail::ui_call<int>(m_L, m_table, "progress", 0, [&] { push(label); lua_pushnumber(m_L, fraction); return 2; }, [] { return 0; });
        }
        // A button: true the frame it's clicked. kind: L"primary", L"danger", L"good", or nothing.
        auto button(std::wstring_view label, std::wstring_view kind = {}) -> bool
        {
            return detail::ui_call<bool>(m_L, m_table, "button", false, [&] {
                push(label);
                lua_newtable(m_L);
                if (!kind.empty()) detail::lua_set_field(m_L, "kind", kind);
                return 2;
            }, [&] { return lua_toboolean(m_L, -1) != 0; });
        }
        // A check box, and an On/Off switch: each gives back true or false.
        auto toggle(std::wstring_view label, bool value) -> bool { return flag("toggle", label, value); }
        auto on_off(std::wstring_view label, bool value) -> bool { return flag("switch", label, value); }
        // One of a few options as buttons, and as a drop-down list: each gives back the chosen one.
        auto radio(std::wstring_view label, std::wstring_view value, std::initializer_list<std::wstring_view> options) -> std::wstring
        {
            return pick("radio", label, value, options);
        }
        auto choice(std::wstring_view label, std::wstring_view value, std::initializer_list<std::wstring_view> options) -> std::wstring
        {
            return pick("choice", label, value, options);
        }
        // A slider between lo and hi, with its value shown.
        auto slider(std::wstring_view label, double value, double lo, double hi, SliderOptions options = {}) -> double
        {
            return detail::ui_call<double>(m_L, m_table, "slider", value, [&] {
                push(label);
                lua_pushnumber(m_L, value);
                lua_pushnumber(m_L, lo);
                lua_pushnumber(m_L, hi);
                lua_newtable(m_L);
                if (options.step > 0) detail::lua_set_field(m_L, "step", options.step);
                if (!options.format.empty()) detail::lua_set_field(m_L, "format", std::wstring_view(options.format));
                return 5;
            }, [&] { return lua_isnumber(m_L, -1) ? lua_tonumber(m_L, -1) : value; });
        }
        // A number box you can drag or type in.
        auto number(std::wstring_view label, double value, NumberOptions options = {}) -> double
        {
            return detail::ui_call<double>(m_L, m_table, "number", value, [&] {
                push(label);
                lua_pushnumber(m_L, value);
                lua_newtable(m_L);
                if (options.min) detail::lua_set_field(m_L, "min", *options.min);
                if (options.max) detail::lua_set_field(m_L, "max", *options.max);
                detail::lua_set_field(m_L, "step", options.step);
                detail::lua_set_field(m_L, "whole", options.whole);
                return 3;
            }, [&] { return lua_isnumber(m_L, -1) ? lua_tonumber(m_L, -1) : value; });
        }
        // A text box, with a hint shown while it's empty.
        auto input(std::wstring_view label, std::wstring_view value, std::wstring_view hint = {}) -> std::wstring
        {
            return detail::ui_call<std::wstring>(m_L, m_table, "input", std::wstring(value), [&] {
                push(label);
                push(value);
                lua_newtable(m_L);
                if (!hint.empty()) detail::lua_set_field(m_L, "hint", hint);
                return 3;
            }, [&] { return detail::lua_text(m_L, -1, value); });
        }
        // A colour swatch with red, green and blue sliders: L"#rrggbb" in and out.
        auto color(std::wstring_view label, std::wstring_view hex) -> std::wstring
        {
            return detail::ui_call<std::wstring>(m_L, m_table, "color", std::wstring(hex), [&] {
                push(label);
                push(hex);
                return 2;
            }, [&] { return detail::lua_text(m_L, -1, hex); });
        }
        // A part that opens and closes with a click on its title; `fn(ui)` draws what's inside.
        auto section(std::wstring_view title, std::function<void(Ui&)> fn, bool open = true) -> void
        {
            detail::ui_call<int>(m_L, m_table, "section", 0, [&] {
                push(title);
                lua_pushlightuserdata(m_L, &fn);
                lua_pushvalue(m_L, m_table);
                lua_pushcclosure(m_L, &Ui::section_thunk, 2);
                lua_newtable(m_L);
                detail::lua_set_field(m_L, "open", open);
                return 3;
            }, [] { return 0; });
        }

      private:
        lua_State* m_L;
        int m_table;

        auto push(std::wstring_view text) -> void { detail::lua_push_text(m_L, text); }
        auto row(const char* name, std::wstring_view text) -> void
        {
            detail::ui_call<int>(m_L, m_table, name, 0, [&] { push(text); return 1; }, [] { return 0; });
        }
        auto flag(const char* name, std::wstring_view label, bool value) -> bool
        {
            return detail::ui_call<bool>(m_L, m_table, name, value, [&] {
                push(label);
                lua_pushboolean(m_L, value);
                return 2;
            }, [&] { return lua_isboolean(m_L, -1) ? lua_toboolean(m_L, -1) != 0 : value; });
        }
        auto pick(const char* name, std::wstring_view label, std::wstring_view value, std::initializer_list<std::wstring_view> options) -> std::wstring
        {
            return detail::ui_call<std::wstring>(m_L, m_table, name, std::wstring(value), [&] {
                push(label);
                push(value);
                detail::lua_push_list(m_L, options);
                return 3;
            }, [&] { return detail::lua_text(m_L, -1, value); });
        }
        static auto section_thunk(lua_State* L) -> int
        {
            auto* fn = static_cast<std::function<void(Ui&)>*>(lua_touserdata(L, lua_upvalueindex(1)));
            Ui inner(L, lua_upvalueindex(2));
            if (fn && *fn) detail::guarded(L"ui.section", [&] { (*fn)(inner); });
            return 0;
        }
    };

    // ============================================================================================ pages
    struct PageOptions
    {
        int order{50};               // its place in its group of the side bar, lower first
        std::string group{"mods"};   // "home", "cat", "world", "story", "fight", "cheats", "mods", "tools", or one of its own
        std::string id;              // what tells it from another page with the same title (the title without)
    };

    namespace detail
    {
        struct Page
        {
            std::string id;
            std::wstring title;
            int order{};
            std::string group;
            std::shared_ptr<std::function<void(Ui&)>> fn;
        };
        struct Bridge
        {
            std::mutex lock;
            std::vector<Page> pages;
            std::map<std::string, Json> from_lua;   // what Lua shared (WCModsCpp.share)
            std::map<std::string, Json> to_lua;     // what this mod shares (WCModsCpp.mods[id].get)
            std::vector<std::wstring> keys;         // "F9\twhat it does" lines for the Overview
            bool settings_page{true};
        };
        inline auto bridge() -> Bridge&
        {
            static Bridge b;
            return b;
        }

        inline auto lua_push_json(lua_State* L, const Json& v) -> void
        {
            switch (v.type())
            {
            case Json::Type::Bool: lua_pushboolean(L, v.boolean()); break;
            case Json::Type::Number: lua_pushnumber(L, v.number()); break;
            case Json::Type::String: lua_push_text(L, v.wstring()); break;
            case Json::Type::Null: lua_pushnil(L); break;
            default: lua_push_text(L, wide(v.dump(0))); break;   // a list or object, as JSON text
            }
        }
        inline auto lua_json(lua_State* L, int index) -> Json
        {
            switch (lua_type(L, index))
            {
            case LUA_TBOOLEAN: return Json(lua_toboolean(L, index) != 0);
            case LUA_TNUMBER: return Json(lua_tonumber(L, index));
            case LUA_TSTRING: return Json(utf8(lua_text(L, index, L"")));
            default: return Json();
            }
        }

        // "full_stamina" or "fullStamina" -> "Full stamina", as the mod menu labels a script's settings.
        inline auto label_of(std::string_view key) -> std::wstring
        {
            std::wstring out;
            for (wchar_t c : wide(key))
            {
                if (c == L'_') out += L' ';
                else if (c >= L'A' && c <= L'Z' && !out.empty() && out.back() != L' ') out += L' ', out += static_cast<wchar_t>(c - L'A' + L'a');
                else if (c >= L'A' && c <= L'Z') out += static_cast<wchar_t>(c - L'A' + L'a');
                else out += c;
            }
            if (!out.empty() && out[0] >= L'a' && out[0] <= L'z') out[0] = static_cast<wchar_t>(out[0] - L'a' + L'A');
            return out;
        }
        inline auto is_hex_colour(const std::string& s) -> bool
        {
            if (s.size() != 7 || s[0] != '#') return false;
            return std::all_of(s.begin() + 1, s.end(), [](char c) { return std::isxdigit(static_cast<unsigned char>(c)); });
        }

        // The settings page a mod gets without asking: a row for each setting, by its kind, and Save.
        inline auto settings_rows(Ui& ui) -> void
        {
            ui.heading(mod().name);
            bool save = false;
            {
                // The settings are held while the rows change them; save_settings takes the same lock, so it
                // waits until they're let go.
                std::lock_guard lock(settings_lock());
                Json& s = settings();
                std::vector<std::string> keys = s.keys();
                for (const std::string& key : keys)
                {
                const Json& v = s[key];   // set() below writes into the same slot, after v has been read
                std::wstring label = label_of(key);
                if (!key.empty() && key[0] == '_')
                {
                    if (v.is_string()) ui.note(v.wstring());
                }
                else if (v.is_bool())
                {
                    s.set(key, ui.on_off(label, v.boolean()));
                }
                else if (v.is_number())
                {
                    bool whole = v.number() == std::floor(v.number());
                    double n = ui.number(label, v.number(), {.step = whole ? 1.0 : 0.1, .whole = whole});
                    s.set(key, whole ? std::round(n) : n);
                }
                else if (v.is_string() && is_hex_colour(v.string()))
                {
                    s.set(key, ui.color(label, v.wstring()));
                }
                else if (v.is_string())
                {
                    s.set(key, ui.input(label, v.wstring()));
                }
                else
                {
                    ui.field(label, wide(v.dump(0)));
                }
                }
                save = ui.button(L"Save", L"primary");
            }
            if (save && !save_settings()) log_line(mod().name, L"couldn't save settings.json");
        }

        inline auto ensure_settings_page() -> void
        {
            Bridge& b = bridge();
            std::lock_guard lock(b.lock);
            if (!b.settings_page || !settings().is_object() || settings().size() == 0) return;
            std::string id = "settings:" + utf8(mod().id);
            for (auto& p : b.pages)
                if (p.id == id) return;
            b.pages.push_back({id, mod().name, 40, "mods", std::make_shared<std::function<void(Ui&)>>(settings_rows)});
        }

        // The functions Lua gets as WCModsCpp.mods[<id>]: pages(), draw(id, ui), set(name, value), get(name), keys().
        inline auto cf_pages(lua_State* L) -> int
        {
            ensure_settings_page();
            Bridge& b = bridge();
            std::lock_guard lock(b.lock);
            lua_newtable(L);
            int i = 1;
            for (auto& p : b.pages)
            {
                lua_newtable(L);
                lua_set_field(L, "id", std::wstring_view(wide(p.id)));
                lua_set_field(L, "title", std::wstring_view(p.title));
                lua_set_field(L, "order", static_cast<double>(p.order));
                lua_set_field(L, "group", std::wstring_view(wide(p.group)));
                lua_rawseti(L, -2, i++);
            }
            return 1;
        }
        inline auto cf_draw(lua_State* L) -> int
        {
            std::string id = utf8(lua_text(L, 1, L""));
            if (id.empty() || !lua_istable(L, 2)) return 0;
            std::shared_ptr<std::function<void(Ui&)>> fn;
            {
                Bridge& b = bridge();
                std::lock_guard lock(b.lock);
                for (auto& p : b.pages)
                    if (p.id == id) fn = p.fn;
            }
            Ui ui(L, 2);
            if (!fn || !*fn)
            {
                // The menu keeps a page it picked up; one the mod took away since (settings_page(false)) says so.
                ui.note(L"This page is gone.");
                return 0;
            }
            guarded(L"a menu page", [&] { (*fn)(ui); });
            return 0;
        }
        inline auto cf_set(lua_State* L) -> int
        {
            std::string name = utf8(lua_text(L, 1, L""));
            if (name.empty()) return 0;
            Json value = lua_json(L, 2);
            Bridge& b = bridge();
            std::lock_guard lock(b.lock);
            b.from_lua[name] = std::move(value);
            return 0;
        }
        inline auto cf_get(lua_State* L) -> int
        {
            std::string name = utf8(lua_text(L, 1, L""));
            Json value;
            {
                Bridge& b = bridge();
                std::lock_guard lock(b.lock);
                if (auto it = b.to_lua.find(name); it != b.to_lua.end()) value = it->second;
            }
            lua_push_json(L, value);
            return 1;
        }
        inline auto cf_keys(lua_State* L) -> int
        {
            std::wstring lines;
            {
                Bridge& b = bridge();
                std::lock_guard lock(b.lock);
                for (auto& line : b.keys) lines += line + L"\n";
            }
            lua_push_text(L, lines);
            return 1;
        }

        // ModBase calls this as each Lua mod's state starts, before its scripts run: the state gets WCModsCpp
        // (shared by every C++ mod) with this mod's table under WCModsCpp.mods.
        inline auto lua_started(RC::LuaMadeSimple::Lua& lua) -> void
        {
            lua_State* L = lua.get_lua_state();
            int top = lua_gettop(L);
            static const char* setup =
                    "WCModsCpp = WCModsCpp or { mods = {} }\n"
                    "WCModsCpp.share = WCModsCpp.share or function(name, value)\n"
                    "    for _, m in pairs(WCModsCpp.mods) do pcall(m.set, name, value) end\n"
                    "end\n";
            if (luaL_loadstring(L, setup) != LUA_OK || lua_pcall(L, 0, 0, 0) != LUA_OK)
            {
                log_line(mod().name, std::format(L"can't set up WCModsCpp in a Lua mod: {}", lua_text(L, -1, L"error")));
                lua_settop(L, top);
                return;
            }
            lua_getglobal(L, "WCModsCpp");
            lua_getfield(L, -1, "mods");
            lua_newtable(L);
            lua_pushcfunction(L, cf_pages);
            lua_setfield(L, -2, "pages");
            lua_pushcfunction(L, cf_draw);
            lua_setfield(L, -2, "draw");
            lua_pushcfunction(L, cf_set);
            lua_setfield(L, -2, "set");
            lua_pushcfunction(L, cf_get);
            lua_setfield(L, -2, "get");
            lua_pushcfunction(L, cf_keys);
            lua_setfield(L, -2, "keys");
            std::string id = utf8(mod().id);
            lua_setfield(L, -2, id.c_str());
            lua_settop(L, top);
        }

        // As the mod is taken out: its pages draw nothing from then on.
        inline auto stop_menu() -> void
        {
            Bridge& b = bridge();
            std::lock_guard lock(b.lock);
            b.pages.clear();
            b.keys.clear();
        }

        inline auto modifier_name(Modifier m) -> std::wstring
        {
            switch (m)
            {
            case Modifier::SHIFT: return L"Shift";
            case Modifier::CONTROL: return L"Ctrl";
            case Modifier::ALT: return L"Alt";
            default: return L"?";
            }
        }
        inline auto list_key(std::wstring name, std::wstring_view help) -> void
        {
            std::wstring text(help);
            for (wchar_t& c : text)
                if (c == L'\t' || c == L'\n') c = L' ';
            Bridge& b = bridge();
            std::lock_guard lock(b.lock);
            b.keys.push_back(name + L"\t" + text);
        }
    } // namespace detail

    // A page in the mod menu: `fn(ui)` draws its rows every frame while it shows, on the game thread. Gives
    // back the page's id (what the menu opens it by). The menu picks new pages up when it opens, so a page can
    // be added at any time; one with the id of an earlier page takes over its drawing (the side bar keeps
    // the title the menu first saw).
    inline auto menu_page(std::wstring title, std::function<void(Ui&)> fn, PageOptions options = {}) -> std::string
    {
        std::string id = options.id.empty() ? utf8(title) : options.id;
        detail::Page page{id, std::move(title), options.order, options.group, std::make_shared<std::function<void(Ui&)>>(std::move(fn))};
        detail::Bridge& b = detail::bridge();
        std::lock_guard lock(b.lock);
        for (auto& p : b.pages)
        {
            if (p.id == id)
            {
                p = std::move(page);
                return id;
            }
        }
        b.pages.push_back(std::move(page));
        return id;
    }

    // Whether the mod gets a page of its settings.json without asking (it does, like script mods).
    inline auto settings_page(bool on) -> void
    {
        detail::Bridge& b = detail::bridge();
        std::lock_guard lock(b.lock);
        b.settings_page = on;
        if (!on) std::erase_if(b.pages, [](const detail::Page& p) { return p.id.starts_with("settings:"); });
    }

    // A value a Lua mod shared with C++ mods (`WCModsCpp.share(name, value)`; a bool, number or string, null
    // when there's none), and one for Lua mods to read (`WCModsCpp.mods["<id>"].get(name)`).
    inline auto shared(std::string_view name) -> Json
    {
        detail::Bridge& b = detail::bridge();
        std::lock_guard lock(b.lock);
        auto it = b.from_lua.find(std::string(name));
        return it == b.from_lua.end() ? Json() : it->second;
    }
    inline auto share(std::string_view name, Json value) -> void
    {
        detail::Bridge& b = detail::bridge();
        std::lock_guard lock(b.lock);
        b.to_lua[std::string(name)] = std::move(value);
    }

    // Whether the mod menu is open, and the id of the page it shows (the menu shares both).
    inline auto menu_open() -> bool { return shared("menu.open").boolean(); }
    inline auto menu_page_shown() -> std::wstring { return shared("menu.page").wstring(); }

    // A key's name as the mod menu's Overview shows it: L"F9", L"Left Arrow", L"Num 1".
    inline auto key_name(Key key) -> std::wstring
    {
        static const std::pair<Key, const wchar_t*> names[] = {
            {Key::LEFT_MOUSE_BUTTON, L"Left Mouse Button"},
            {Key::RIGHT_MOUSE_BUTTON, L"Right Mouse Button"},
            {Key::CANCEL, L"Cancel"},
            {Key::MIDDLE_MOUSE_BUTTON, L"Middle Mouse Button"},
            {Key::XBUTTON_ONE, L"Xbutton One"},
            {Key::XBUTTON_TWO, L"Xbutton Two"},
            {Key::BACKSPACE, L"Backspace"},
            {Key::TAB, L"Tab"},
            {Key::CLEAR, L"Clear"},
            {Key::RETURN, L"Return"},
            {Key::PAUSE, L"Pause"},
            {Key::CAPS_LOCK, L"Caps Lock"},
            {Key::IME_KANA, L"Ime Kana"},
            {Key::IME_HANGUEL, L"Ime Hanguel"},
            {Key::IME_HANGUL, L"Ime Hangul"},
            {Key::IME_ON, L"Ime On"},
            {Key::IME_JUNJA, L"Ime Junja"},
            {Key::IME_FINAL, L"Ime Final"},
            {Key::IME_HANJA, L"Ime Hanja"},
            {Key::IME_KANJI, L"Ime Kanji"},
            {Key::IME_OFF, L"Ime Off"},
            {Key::ESCAPE, L"Escape"},
            {Key::IME_CONVERT, L"Ime Convert"},
            {Key::IME_NONCONVERT, L"Ime Nonconvert"},
            {Key::IME_ACCEPT, L"Ime Accept"},
            {Key::IME_MODECHANGE, L"Ime Modechange"},
            {Key::SPACE, L"Space"},
            {Key::PAGE_UP, L"Page Up"},
            {Key::PAGE_DOWN, L"Page Down"},
            {Key::END, L"End"},
            {Key::HOME, L"Home"},
            {Key::LEFT_ARROW, L"Left Arrow"},
            {Key::UP_ARROW, L"Up Arrow"},
            {Key::RIGHT_ARROW, L"Right Arrow"},
            {Key::DOWN_ARROW, L"Down Arrow"},
            {Key::SELECT, L"Select"},
            {Key::PRINT, L"Print"},
            {Key::EXECUTE, L"Execute"},
            {Key::PRINT_SCREEN, L"Print Screen"},
            {Key::INS, L"Ins"},
            {Key::DEL, L"Del"},
            {Key::HELP, L"Help"},
            {Key::ZERO, L"0"},
            {Key::ONE, L"1"},
            {Key::TWO, L"2"},
            {Key::THREE, L"3"},
            {Key::FOUR, L"4"},
            {Key::FIVE, L"5"},
            {Key::SIX, L"6"},
            {Key::SEVEN, L"7"},
            {Key::EIGHT, L"8"},
            {Key::NINE, L"9"},
            {Key::A, L"A"},
            {Key::B, L"B"},
            {Key::C, L"C"},
            {Key::D, L"D"},
            {Key::E, L"E"},
            {Key::F, L"F"},
            {Key::G, L"G"},
            {Key::H, L"H"},
            {Key::I, L"I"},
            {Key::J, L"J"},
            {Key::K, L"K"},
            {Key::L, L"L"},
            {Key::M, L"M"},
            {Key::N, L"N"},
            {Key::O, L"O"},
            {Key::P, L"P"},
            {Key::Q, L"Q"},
            {Key::R, L"R"},
            {Key::S, L"S"},
            {Key::T, L"T"},
            {Key::U, L"U"},
            {Key::V, L"V"},
            {Key::W, L"W"},
            {Key::X, L"X"},
            {Key::Y, L"Y"},
            {Key::Z, L"Z"},
            {Key::LEFT_WIN, L"Left Win"},
            {Key::RIGHT_WIN, L"Right Win"},
            {Key::APPS, L"Apps"},
            {Key::SLEEP, L"Sleep"},
            {Key::NUM_ZERO, L"Num 0"},
            {Key::NUM_ONE, L"Num 1"},
            {Key::NUM_TWO, L"Num 2"},
            {Key::NUM_THREE, L"Num 3"},
            {Key::NUM_FOUR, L"Num 4"},
            {Key::NUM_FIVE, L"Num 5"},
            {Key::NUM_SIX, L"Num 6"},
            {Key::NUM_SEVEN, L"Num 7"},
            {Key::NUM_EIGHT, L"Num 8"},
            {Key::NUM_NINE, L"Num 9"},
            {Key::MULTIPLY, L"Multiply"},
            {Key::ADD, L"Add"},
            {Key::SEPARATOR, L"Separator"},
            {Key::SUBTRACT, L"Subtract"},
            {Key::DECIMAL, L"Decimal"},
            {Key::DIVIDE, L"Divide"},
            {Key::F1, L"F1"},
            {Key::F2, L"F2"},
            {Key::F3, L"F3"},
            {Key::F4, L"F4"},
            {Key::F5, L"F5"},
            {Key::F6, L"F6"},
            {Key::F7, L"F7"},
            {Key::F8, L"F8"},
            {Key::F9, L"F9"},
            {Key::F10, L"F10"},
            {Key::F11, L"F11"},
            {Key::F12, L"F12"},
            {Key::F13, L"F13"},
            {Key::F14, L"F14"},
            {Key::F15, L"F15"},
            {Key::F16, L"F16"},
            {Key::F17, L"F17"},
            {Key::F18, L"F18"},
            {Key::F19, L"F19"},
            {Key::F20, L"F20"},
            {Key::F21, L"F21"},
            {Key::F22, L"F22"},
            {Key::F23, L"F23"},
            {Key::F24, L"F24"},
            {Key::NUM_LOCK, L"Num Lock"},
            {Key::SCROLL_LOCK, L"Scroll Lock"},
            {Key::BROWSER_BACK, L"Browser Back"},
            {Key::BROWSER_FORWARD, L"Browser Forward"},
            {Key::BROWSER_REFRESH, L"Browser Refresh"},
            {Key::BROWSER_STOP, L"Browser Stop"},
            {Key::BROWSER_SEARCH, L"Browser Search"},
            {Key::BROWSER_FAVORITES, L"Browser Favorites"},
            {Key::BROWSER_HOME, L"Browser Home"},
            {Key::VOLUME_MUTE, L"Volume Mute"},
            {Key::VOLUME_DOWN, L"Volume Down"},
            {Key::VOLUME_UP, L"Volume Up"},
            {Key::MEDIA_NEXT_TRACK, L"Media Next Track"},
            {Key::MEDIA_PREV_TRACK, L"Media Prev Track"},
            {Key::MEDIA_STOP, L"Media Stop"},
            {Key::MEDIA_PLAY_PAUSE, L"Media Play Pause"},
            {Key::LAUNCH_MAIL, L"Launch Mail"},
            {Key::LAUNCH_MEDIA_SELECT, L"Launch Media Select"},
            {Key::LAUNCH_APP1, L"Launch App1"},
            {Key::LAUNCH_APP2, L"Launch App2"},
            {Key::OEM_ONE, L"Oem One"},
            {Key::OEM_PLUS, L"Oem Plus"},
            {Key::OEM_COMMA, L"Oem Comma"},
            {Key::OEM_MINUS, L"Oem Minus"},
            {Key::OEM_PERIOD, L"Oem Period"},
            {Key::OEM_TWO, L"Oem Two"},
            {Key::OEM_THREE, L"Oem Three"},
            {Key::OEM_FOUR, L"Oem Four"},
            {Key::OEM_FIVE, L"Oem Five"},
            {Key::OEM_SIX, L"Oem Six"},
            {Key::OEM_SEVEN, L"Oem Seven"},
            {Key::OEM_EIGHT, L"Oem Eight"},
            {Key::OEM_102, L"Oem 102"},
            {Key::IME_PROCESS, L"Ime Process"},
            {Key::PACKET, L"Packet"},
            {Key::ATTN, L"Attn"},
            {Key::CRSEL, L"Crsel"},
            {Key::EXSEL, L"Exsel"},
            {Key::EREOF, L"Ereof"},
            {Key::PLAY, L"Play"},
            {Key::ZOOM, L"Zoom"},
            {Key::NONAME, L"Noname"},
            {Key::PA1, L"Pa1"},
        };
        for (auto& [k, name] : names)
            if (k == key) return name;
        return std::format(L"Key {}", static_cast<int>(key));
    }

    // on_key, with what the key does: the mod menu's Overview page lists it.
    inline auto on_key(Key key, std::wstring_view help, std::function<void()> fn) -> bool
    {
        detail::list_key(key_name(key), help);
        return on_key(key, std::move(fn));
    }
    inline auto on_key(Key key, std::initializer_list<Modifier> modifiers, std::wstring_view help, std::function<void()> fn) -> bool
    {
        std::wstring name;
        for (Modifier m : modifiers) name += detail::modifier_name(m) + L"+";
        detail::list_key(name + key_name(key), help);
        return on_key(key, modifiers, std::move(fn));
    }
} // namespace wcmods
