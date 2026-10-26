// WCMods/UiLua.hpp: Ui.hpp for Lua mods. A C++ mod built with the SDK puts a WCModsCpp.ui table into every Lua
// mod's state as it starts (Mod.hpp's on_lua_start), so a script can make and place the engine's controls, put
// a tab in the game's screens, reach the HUD and keep an overlay, with the C++ doing the work. Widgets are
// UE4SS's own UObject values, so everything UE4SS lets a script do with a widget still works on them. The
// script asks rather than being called: ui.clicked(w), ui.tab_page(id), looked at from its own frame loop.
// WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every function, and docs/scripting.md shows a
// script using it.
#pragma once

#include <string>
#include <string_view>
#include <vector>

#include <LuaMadeSimple/LuaMadeSimple.hpp>
#include <LuaType/LuaUObject.hpp>
#include <lua.hpp>

#include <WCMods/Core.hpp>
#include <WCMods/Menu.hpp>
#include <WCMods/Ui.hpp>

namespace wcmods
{
    namespace detail
    {
    namespace uilua
    {
        // ---------------------------------------------------------------------------- values in and out
        // Whether a userdata is one of UE4SS's object wrappers (a UObject, an actor, a class...), by the name of
        // its metatable: an FText, a struct or an array handed in by mistake isn't read as an object.
        inline auto is_object_userdata(lua_State* L, int index) -> bool
        {
            if (!lua_isuserdata(L, index) || lua_islightuserdata(L, index)) return false;
            if (luaL_getmetafield(L, index, "__name") == LUA_TNIL) return false;
            std::string name = lua_type(L, -1) == LUA_TSTRING ? lua_tostring(L, -1) : "";
            lua_pop(L, 1);
            for (const char* kind : {"UObject", "AActor", "UClass", "UWorld", "UFunction", "UDataTable", "UEnum", "UInterface"})
                if (name == kind) return true;
            return false;
        }
        inline auto object_at(lua_State* L, int index) -> UObject*
        {
            if (!is_object_userdata(L, index)) return nullptr;
            RC::LuaMadeSimple::Lua lua(L);
            try
            {
                return lua.get_userdata<RC::LuaType::UObject>(index, true).get_remote_cpp_object();
            }
            catch (...)
            {
                return nullptr;
            }
        }
        inline auto widget_at(lua_State* L, int index) -> Widget { return Widget(object_at(L, index)); }
        inline auto push_object(lua_State* L, UObject* o) -> int
        {
            if (!o)
            {
                lua_pushnil(L);
                return 1;
            }
            RC::LuaMadeSimple::Lua lua(L);
            RC::LuaType::auto_construct_object(lua, o);
            return 1;
        }
        inline auto push_widget(lua_State* L, const Widget& w) -> int { return push_object(L, w.object()); }
        inline auto push_slot(lua_State* L, const Slot& s) -> int { return push_object(L, s.object()); }
        inline auto text_at(lua_State* L, int index, std::wstring_view fallback = {}) -> std::wstring { return lua_text(L, index, fallback); }
        inline auto number_at(lua_State* L, int index, double fallback = 0) -> double
        {
            return lua_isnumber(L, index) ? lua_tonumber(L, index) : fallback;
        }
        inline auto bool_at(lua_State* L, int index, bool fallback = false) -> bool
        {
            return lua_isboolean(L, index) ? lua_toboolean(L, index) != 0 : fallback;
        }
        inline auto color_at(lua_State* L, int index, UiColor fallback) -> UiColor
        {
            return lua_type(L, index) == LUA_TSTRING ? UiColor::hex(text_at(L, index)) : fallback;
        }
        inline auto margin_at(lua_State* L, int index) -> Margin
        {
            // Four numbers, or a table {l, t, r, b} / {all}.
            if (lua_istable(L, index))
            {
                double v[4]{};
                size_t n = lua_rawlen(L, index);
                for (size_t i = 0; i < 4 && i < n; ++i)
                {
                    lua_rawgeti(L, index, static_cast<lua_Integer>(i + 1));
                    v[i] = number_at(L, -1);
                    lua_pop(L, 1);
                }
                if (n == 1) return Margin(static_cast<float>(v[0]));
                if (n == 2) return Margin(static_cast<float>(v[0]), static_cast<float>(v[1]));
                return Margin(static_cast<float>(v[0]), static_cast<float>(v[1]), static_cast<float>(v[2]), static_cast<float>(v[3]));
            }
            return Margin(static_cast<float>(number_at(L, index)), static_cast<float>(number_at(L, index + 1)),
                          static_cast<float>(number_at(L, index + 2)), static_cast<float>(number_at(L, index + 3)));
        }
        inline auto align_of(std::wstring_view s) -> Align
        {
            if (s == L"left" || s == L"top" || s == L"start") return Align::Start;
            if (s == L"center" || s == L"middle") return Align::Center;
            if (s == L"right" || s == L"bottom" || s == L"end") return Align::End;
            return Align::Fill;
        }
        inline auto visibility_of(lua_State* L, int index) -> Visibility
        {
            if (lua_isboolean(L, index)) return lua_toboolean(L, index) ? Visibility::SelfHitTestInvisible : Visibility::Collapsed;
            std::wstring s = text_at(L, index);
            if (s == L"visible") return Visibility::Visible;
            if (s == L"hidden") return Visibility::Hidden;
            if (s == L"collapsed") return Visibility::Collapsed;
            if (s == L"passive") return Visibility::HitTestInvisible;
            return Visibility::SelfHitTestInvisible;
        }
        inline auto visibility_name(Visibility v) -> const wchar_t*
        {
            switch (v)
            {
            case Visibility::Visible: return L"visible";
            case Visibility::Collapsed: return L"collapsed";
            case Visibility::Hidden: return L"hidden";
            case Visibility::HitTestInvisible: return L"passive";
            default: return L"shown";
            }
        }
        // A list of strings from a table argument.
        inline auto strings_at(lua_State* L, int index) -> std::vector<std::wstring>
        {
            std::vector<std::wstring> out;
            if (!lua_istable(L, index)) return out;
            size_t n = lua_rawlen(L, index);
            for (size_t i = 1; i <= n; ++i)
            {
                lua_rawgeti(L, index, static_cast<lua_Integer>(i));
                out.push_back(text_at(L, -1));
                lua_pop(L, 1);
            }
            return out;
        }
        inline auto widgets_at(lua_State* L, int index) -> std::vector<Widget>
        {
            std::vector<Widget> out;
            if (!lua_istable(L, index)) return out;
            size_t n = lua_rawlen(L, index);
            for (size_t i = 1; i <= n; ++i)
            {
                lua_rawgeti(L, index, static_cast<lua_Integer>(i));
                out.push_back(widget_at(L, -1));
                lua_pop(L, 1);
            }
            return out;
        }
        // An options table's fields, by name (nil when absent).
        inline auto field_number(lua_State* L, int index, const char* key, double fallback) -> double
        {
            if (!lua_istable(L, index)) return fallback;
            lua_getfield(L, index, key);
            double v = number_at(L, -1, fallback);
            lua_pop(L, 1);
            return v;
        }
        inline auto field_text(lua_State* L, int index, const char* key) -> std::wstring
        {
            if (!lua_istable(L, index)) return {};
            lua_getfield(L, index, key);
            std::wstring v = text_at(L, -1);
            lua_pop(L, 1);
            return v;
        }
        inline auto field_bool(lua_State* L, int index, const char* key, bool fallback) -> bool
        {
            if (!lua_istable(L, index)) return fallback;
            lua_getfield(L, index, key);
            bool v = bool_at(L, -1, fallback);
            lua_pop(L, 1);
            return v;
        }
        inline auto has_field(lua_State* L, int index, const char* key) -> bool
        {
            if (!lua_istable(L, index)) return false;
            lua_getfield(L, index, key);
            bool v = !lua_isnil(L, -1);
            lua_pop(L, 1);
            return v;
        }

        // ---------------------------------------------------------------------------- making
        inline auto f_make(lua_State* L) -> int
        {
            std::wstring kind = text_at(L, 1);
            Widget w = kind.ends_with(L"_C") && kind.find(L'/') != std::wstring::npos ? ui::game_widget(kind.c_str()) : ui::widget(kind);
            return push_widget(L, w);
        }
        inline auto f_game_widget(lua_State* L) -> int
        {
            // By a class path, or by the class of a widget given.
            if (UObject* o = object_at(L, 1)) return push_widget(L, ui::game_widget(o->IsA<RC::Unreal::UClass>() ? static_cast<UClass*>(o) : o->GetClassPrivate()));
            return push_widget(L, ui::game_widget(text_at(L, 1).c_str()));
        }
        inline auto f_text(lua_State* L) -> int
        {
            // ui.text(str [, {size=, color=, wrap=, justify=}]) makes a text block; ui.text(widget [, str]) reads or sets one.
            if (UObject* o = object_at(L, 1))
            {
                Widget w(o);
                if (lua_gettop(L) >= 2 && !lua_isnil(L, 2))
                {
                    w.set_text(text_at(L, 2));
                    return 0;
                }
                lua_push_text(L, w.text());
                return 1;
            }
            ui::TextOptions o;
            o.size = static_cast<float>(field_number(L, 2, "size", 0));
            if (has_field(L, 2, "color")) o.color = UiColor::hex(field_text(L, 2, "color"));
            o.wrap = field_bool(L, 2, "wrap", false);
            o.justify = align_of(field_text(L, 2, "justify"));
            return push_widget(L, ui::text(text_at(L, 1), o));
        }
        inline auto f_heading(lua_State* L) -> int { return push_widget(L, ui::heading(text_at(L, 1))); }
        inline auto f_note(lua_State* L) -> int { return push_widget(L, ui::note(text_at(L, 1))); }
        inline auto f_button(lua_State* L) -> int
        {
            std::optional<UiColor> c;
            if (lua_type(L, 2) == LUA_TSTRING) c = UiColor::hex(text_at(L, 2));
            return push_widget(L, ui::button(text_at(L, 1), c));
        }
        inline auto f_check(lua_State* L) -> int { return push_widget(L, ui::checkbox(bool_at(L, 1))); }
        inline auto f_slider(lua_State* L) -> int
        {
            return push_widget(L, ui::slider(number_at(L, 1), number_at(L, 2, 0), number_at(L, 3, 1), number_at(L, 4, 0)));
        }
        inline auto f_number(lua_State* L) -> int
        {
            std::optional<double> lo, hi;
            if (lua_isnumber(L, 2)) lo = lua_tonumber(L, 2);
            if (lua_isnumber(L, 3)) hi = lua_tonumber(L, 3);
            return push_widget(L, ui::number(number_at(L, 1), lo, hi, number_at(L, 4, 1)));
        }
        inline auto f_input(lua_State* L) -> int { return push_widget(L, ui::input(text_at(L, 1), text_at(L, 2))); }
        inline auto f_choice(lua_State* L) -> int
        {
            Widget c = ui::widget(L"ComboBoxString");
            for (auto& s : strings_at(L, 1)) c.add_option(s);
            std::wstring sel = text_at(L, 2);
            if (!sel.empty()) c.set_option(sel);
            else c.set_value(0);
            return push_widget(L, c);
        }
        inline auto f_progress(lua_State* L) -> int
        {
            std::optional<UiColor> c;
            if (lua_type(L, 2) == LUA_TSTRING) c = UiColor::hex(text_at(L, 2));
            return push_widget(L, ui::progress(number_at(L, 1), c));
        }
        inline auto f_image(lua_State* L) -> int
        {
            // ui.image(path [, w, h]) makes one; ui.image(widget, path) sets a widget's picture.
            if (UObject* o = object_at(L, 1))
            {
                Widget(o).set_image(text_at(L, 2).c_str());
                return 0;
            }
            return push_widget(L, ui::image(text_at(L, 1).c_str(), number_at(L, 2), number_at(L, 3)));
        }
        inline auto f_rect(lua_State* L) -> int { return push_widget(L, ui::rect(color_at(L, 1, {}), number_at(L, 2), number_at(L, 3))); }
        inline auto f_hbox(lua_State* L) -> int { return push_widget(L, ui::hbox()); }
        inline auto f_vbox(lua_State* L) -> int { return push_widget(L, ui::vbox()); }
        inline auto f_scroll(lua_State* L) -> int { return push_widget(L, ui::scroll()); }
        inline auto f_border(lua_State* L) -> int
        {
            std::optional<UiColor> c;
            if (lua_type(L, 1) == LUA_TSTRING) c = UiColor::hex(text_at(L, 1));
            return push_widget(L, ui::border(c, lua_gettop(L) >= 2 ? margin_at(L, 2) : Margin{}));
        }
        inline auto f_box(lua_State* L) -> int { return push_widget(L, ui::box(number_at(L, 1), number_at(L, 2))); }
        inline auto f_spacer(lua_State* L) -> int { return push_widget(L, ui::spacer(number_at(L, 1), number_at(L, 2))); }
        inline auto f_canvas(lua_State* L) -> int { return push_widget(L, ui::canvas()); }
        inline auto f_row(lua_State* L) -> int
        {
            Widget h = ui::hbox();
            auto widgets = widgets_at(L, 1);
            float gap = static_cast<float>(number_at(L, 2, 24));
            for (size_t i = 0; i < widgets.size(); ++i)
            {
                Slot s = h.add(widgets[i]);
                s.align(Align::Fill, Align::Center);
                if (i == 0 && widgets.size() > 1) s.fill(1);
                if (i > 0) s.padding({gap, 0, 0, 0});
            }
            return push_widget(L, h);
        }
        inline auto f_labelled(lua_State* L) -> int
        {
            return push_widget(L, ui::labelled(text_at(L, 1), widget_at(L, 2), number_at(L, 3, 0)));
        }
        inline auto f_scaled(lua_State* L) -> int { return push_widget(L, ui::scaled(widget_at(L, 1), number_at(L, 2, 0))); }

        // ---------------------------------------------------------------------------- the tree
        inline auto f_add(lua_State* L) -> int
        {
            Widget parent = widget_at(L, 1);
            if (lua_istable(L, 2))
            {
                for (auto& w : widgets_at(L, 2)) parent.add(w);
                return push_widget(L, parent);
            }
            return push_slot(L, parent.add(widget_at(L, 2)));
        }
        inline auto f_remove(lua_State* L) -> int
        {
            Widget w = widget_at(L, 1);
            if (UObject* child = object_at(L, 2)) lua_pushboolean(L, w.remove(Widget(child)));
            else
            {
                w.remove();
                lua_pushboolean(L, true);
            }
            return 1;
        }
        inline auto f_clear(lua_State* L) -> int
        {
            widget_at(L, 1).clear();
            return 0;
        }
        inline auto f_parent(lua_State* L) -> int { return push_widget(L, widget_at(L, 1).parent()); }
        inline auto f_children(lua_State* L) -> int
        {
            lua_newtable(L);
            int i = 1;
            for (const Widget& c : widget_at(L, 1).children())
            {
                push_widget(L, c);
                lua_rawseti(L, -2, i++);
            }
            return 1;
        }
        inline auto f_find(lua_State* L) -> int { return push_widget(L, widget_at(L, 1).find(text_at(L, 2))); }
        inline auto f_find_all(lua_State* L) -> int
        {
            lua_newtable(L);
            int i = 1;
            for (const Widget& c : widget_at(L, 1).find_all(text_at(L, 2)))
            {
                push_widget(L, c);
                lua_rawseti(L, -2, i++);
            }
            return 1;
        }
        inline auto f_slot(lua_State* L) -> int { return push_slot(L, widget_at(L, 1).slot()); }
        // ui.place(widget or slot, {padding=, fill=, halign=, valign=, anchors={x0,y0,x1,y1}, offsets=, position={x,y},
        //          size={w,h}, alignment={x,y}, auto=, layer=, row=, column=})
        inline auto f_place(lua_State* L) -> int
        {
            UObject* o = object_at(L, 1);
            Slot s = wcmods::is_a(o, STR("/Script/UMG.PanelSlot")) ? Slot(o) : Widget(o).slot();
            if (!s || !lua_istable(L, 2)) return 0;
            auto numbers = [&](const char* key, size_t n, double* out) {
                lua_getfield(L, 2, key);
                bool ok = lua_istable(L, -1);
                if (ok)
                    for (size_t i = 0; i < n; ++i)
                    {
                        lua_rawgeti(L, -1, static_cast<lua_Integer>(i + 1));
                        out[i] = number_at(L, -1);
                        lua_pop(L, 1);
                    }
                lua_pop(L, 1);
                return ok;
            };
            double v[4]{};
            if (has_field(L, 2, "padding"))
            {
                lua_getfield(L, 2, "padding");
                s.padding(lua_istable(L, -1) ? margin_at(L, lua_gettop(L)) : Margin(static_cast<float>(number_at(L, -1))));
                lua_pop(L, 1);
            }
            if (has_field(L, 2, "fill"))
            {
                lua_getfield(L, 2, "fill");
                if (lua_isboolean(L, -1) && !lua_toboolean(L, -1)) s.fit();
                else s.fill(static_cast<float>(number_at(L, -1, 1)));
                lua_pop(L, 1);
            }
            if (has_field(L, 2, "halign") || has_field(L, 2, "valign"))
                s.align(align_of(field_text(L, 2, "halign")), align_of(field_text(L, 2, "valign")));
            if (numbers("anchors", 4, v)) s.anchors(v[0], v[1], v[2], v[3]);
            if (numbers("offsets", 4, v)) s.offsets({static_cast<float>(v[0]), static_cast<float>(v[1]), static_cast<float>(v[2]), static_cast<float>(v[3])});
            if (numbers("position", 2, v)) s.position(v[0], v[1]);
            if (numbers("size", 2, v)) s.size(v[0], v[1]);
            if (numbers("alignment", 2, v)) s.alignment(v[0], v[1]);
            if (has_field(L, 2, "auto")) s.auto_size(field_bool(L, 2, "auto", true));
            if (has_field(L, 2, "layer")) s.layer(static_cast<int>(field_number(L, 2, "layer", 0)));
            if (has_field(L, 2, "row") || has_field(L, 2, "column"))
                s.cell(static_cast<int>(field_number(L, 2, "row", 0)), static_cast<int>(field_number(L, 2, "column", 0)),
                       static_cast<int>(field_number(L, 2, "row_span", 1)), static_cast<int>(field_number(L, 2, "column_span", 1)));
            if (has_field(L, 2, "stretch"))
            {
                lua_getfield(L, 2, "stretch");
                s.stretch(lua_istable(L, -1) ? margin_at(L, lua_gettop(L)) : Margin{});
                lua_pop(L, 1);
            }
            return 0;
        }
        inline auto f_at(lua_State* L) -> int
        {
            widget_at(L, 1).at(number_at(L, 2), number_at(L, 3));
            return 0;
        }

        // ---------------------------------------------------------------------------- state
        inline auto f_visible(lua_State* L) -> int
        {
            Widget w = widget_at(L, 1);
            if (lua_gettop(L) >= 2 && !lua_isnil(L, 2))
            {
                w.set_visibility(visibility_of(L, 2));
                return 0;
            }
            lua_push_text(L, visibility_name(w.visibility()));
            lua_pushboolean(L, w.visible());
            return 2;
        }
        inline auto f_enabled(lua_State* L) -> int
        {
            Widget w = widget_at(L, 1);
            if (lua_gettop(L) >= 2)
            {
                w.set_enabled(bool_at(L, 2, true));
                return 0;
            }
            lua_pushboolean(L, w.enabled());
            return 1;
        }
        inline auto f_opacity(lua_State* L) -> int
        {
            Widget w = widget_at(L, 1);
            if (lua_gettop(L) >= 2)
            {
                w.set_opacity(static_cast<float>(number_at(L, 2, 1)));
                return 0;
            }
            lua_pushnumber(L, w.opacity());
            return 1;
        }
        inline auto f_focus(lua_State* L) -> int
        {
            widget_at(L, 1).focus();
            return 0;
        }
        inline auto f_focused(lua_State* L) -> int
        {
            lua_pushboolean(L, widget_at(L, 1).focused());
            return 1;
        }
        inline auto f_font(lua_State* L) -> int
        {
            widget_at(L, 1).set_font(static_cast<float>(number_at(L, 2, ui::theme().text_size)), text_at(L, 3));
            return 0;
        }
        inline auto f_color(lua_State* L) -> int
        {
            widget_at(L, 1).set_color(color_at(L, 2, ui::theme().text));
            return 0;
        }
        inline auto f_tint(lua_State* L) -> int
        {
            widget_at(L, 1).set_tint(color_at(L, 2, {}));
            return 0;
        }
        inline auto f_wrap(lua_State* L) -> int
        {
            widget_at(L, 1).set_wrap(bool_at(L, 2, true));
            return 0;
        }
        inline auto f_justify(lua_State* L) -> int
        {
            widget_at(L, 1).set_justify(align_of(text_at(L, 2)));
            return 0;
        }
        inline auto f_hint(lua_State* L) -> int
        {
            widget_at(L, 1).set_hint(text_at(L, 2));
            return 0;
        }
        inline auto f_padding(lua_State* L) -> int
        {
            widget_at(L, 1).set_padding(margin_at(L, 2));
            return 0;
        }
        inline auto f_size(lua_State* L) -> int
        {
            widget_at(L, 1).set_size(number_at(L, 2), number_at(L, 3));
            return 0;
        }
        inline auto f_scale(lua_State* L) -> int
        {
            widget_at(L, 1).set_scale(number_at(L, 2, 1), number_at(L, 3, number_at(L, 2, 1)));
            return 0;
        }
        inline auto f_angle(lua_State* L) -> int
        {
            widget_at(L, 1).set_angle(static_cast<float>(number_at(L, 2)));
            return 0;
        }
        inline auto f_translate(lua_State* L) -> int
        {
            widget_at(L, 1).set_translation(number_at(L, 2), number_at(L, 3));
            return 0;
        }
        inline auto f_tooltip(lua_State* L) -> int
        {
            widget_at(L, 1).set_tooltip(text_at(L, 2));
            return 0;
        }
        inline auto f_value(lua_State* L) -> int
        {
            Widget w = widget_at(L, 1);
            if (lua_gettop(L) >= 2 && !lua_isnil(L, 2))
            {
                w.set_value(lua_isboolean(L, 2) ? (lua_toboolean(L, 2) ? 1 : 0) : number_at(L, 2));
                return 0;
            }
            lua_pushnumber(L, w.value());
            return 1;
        }
        inline auto f_checked(lua_State* L) -> int
        {
            Widget w = widget_at(L, 1);
            if (lua_gettop(L) >= 2)
            {
                w.set_checked(bool_at(L, 2));
                return 0;
            }
            lua_pushboolean(L, w.checked());
            return 1;
        }
        inline auto f_range(lua_State* L) -> int
        {
            widget_at(L, 1).set_range(number_at(L, 2), number_at(L, 3, 1), number_at(L, 4, 0));
            return 0;
        }
        inline auto f_options(lua_State* L) -> int
        {
            Widget w = widget_at(L, 1);
            if (lua_istable(L, 2))
            {
                w.call(STR("ClearOptions"));
                for (auto& s : strings_at(L, 2)) w.add_option(s);
                return 0;
            }
            lua_newtable(L);
            int i = 1;
            for (auto& s : w.options())
            {
                lua_push_text(L, s);
                lua_rawseti(L, -2, i++);
            }
            return 1;
        }
        inline auto f_option(lua_State* L) -> int
        {
            Widget w = widget_at(L, 1);
            if (lua_gettop(L) >= 2 && !lua_isnil(L, 2))
            {
                w.set_option(text_at(L, 2));
                return 0;
            }
            lua_push_text(L, w.option());
            return 1;
        }
        inline auto f_active(lua_State* L) -> int
        {
            widget_at(L, 1).set_active(static_cast<int>(number_at(L, 2)));
            return 0;
        }
        inline auto f_play(lua_State* L) -> int
        {
            lua_pushboolean(L, widget_at(L, 1).play(text_at(L, 2), bool_at(L, 3)));
            return 1;
        }
        inline auto f_clicked(lua_State* L) -> int
        {
            lua_pushboolean(L, widget_at(L, 1).clicked());
            return 1;
        }
        inline auto f_changed(lua_State* L) -> int
        {
            lua_pushboolean(L, widget_at(L, 1).changed());
            return 1;
        }
        inline auto f_hovered(lua_State* L) -> int
        {
            lua_pushboolean(L, widget_at(L, 1).hovered());
            return 1;
        }
        inline auto f_valid(lua_State* L) -> int
        {
            lua_pushboolean(L, widget_at(L, 1).valid());
            return 1;
        }

        // ---------------------------------------------------------------------------- the viewport, overlays, screens
        inline auto f_viewport(lua_State* L) -> int
        {
            Vec2 v = ui::viewport_size();
            lua_pushnumber(L, v.x);
            lua_pushnumber(L, v.y);
            lua_pushnumber(L, ui::viewport_scale());
            return 3;
        }
        inline auto f_cursor(lua_State* L) -> int
        {
            lua_pushboolean(L, ui::show_cursor(bool_at(L, 1, true)));
            return 1;
        }
        inline auto f_overlay(lua_State* L) -> int
        {
            ui::OverlayOptions o;
            if (lua_isnumber(L, 2)) o.layer = static_cast<int>(lua_tonumber(L, 2));
            if (lua_isboolean(L, 3)) o.passive = lua_toboolean(L, 3) != 0;
            return push_widget(L, ui::overlay(text_at(L, 1, L"lua"), o));
        }
        inline auto f_remove_overlay(lua_State* L) -> int
        {
            ui::remove_overlay(text_at(L, 1, L"lua"));
            return 0;
        }
        inline auto f_screen(lua_State* L) -> int { return push_widget(L, ui::screen(text_at(L, 1))); }
        inline auto f_hud(lua_State* L) -> int
        {
            if (lua_gettop(L) >= 1 && lua_type(L, 1) == LUA_TSTRING) return push_widget(L, ui::hud_part(text_at(L, 1)));
            return push_widget(L, ui::hud());
        }
        inline auto f_tab(lua_State* L) -> int
        {
            ui::TabOptions o;
            o.id = utf8(text_at(L, 3));
            if (lua_istable(L, 4))
            {
                o.hide_game_panels = field_bool(L, 4, "hide_panels", true);
                o.scroll = field_bool(L, 4, "scroll", true);
                o.focus = field_bool(L, 4, "focus", true);
                o.mouse = field_bool(L, 4, "mouse", true);
                lua_getfield(L, 4, "inset");
                if (lua_istable(L, -1)) o.inset = margin_at(L, lua_gettop(L));
                lua_pop(L, 1);
            }
            std::string id = ui::tab(text_at(L, 1), text_at(L, 2), {}, o);
            lua_push_text(L, wide(id));
            return 1;
        }
        inline auto f_tab_page(lua_State* L) -> int
        {
            std::string id = utf8(text_at(L, 1));
            Widget page;
            int generation = 0;
            {
                ui::detail::Tabs& ts = ui::detail::tabs_state();
                std::lock_guard lock(ts.lock);
                for (auto& t : ts.tabs)
                    if (t->id == id)
                    {
                        page = t->page;
                        generation = t->generation;
                    }
            }
            push_widget(L, page);
            lua_pushinteger(L, generation);
            return 2;
        }
        inline auto f_tab_active(lua_State* L) -> int
        {
            lua_pushboolean(L, ui::tab_active(utf8(text_at(L, 1))));
            return 1;
        }
        inline auto f_remove_tab(lua_State* L) -> int
        {
            ui::remove_tab(utf8(text_at(L, 1)));
            return 0;
        }
        inline auto f_tabs(lua_State* L) -> int
        {
            lua_newtable(L);
            int i = 1;
            for (auto& id : ui::tabs())
            {
                lua_push_text(L, wide(id));
                lua_rawseti(L, -2, i++);
            }
            return 1;
        }
        inline auto f_theme(lua_State* L) -> int
        {
            ui::Theme& t = ui::theme();
            if (lua_istable(L, 1))
            {
                if (has_field(L, 1, "text_size")) t.text_size = static_cast<float>(field_number(L, 1, "text_size", t.text_size));
                if (has_field(L, 1, "heading_size")) t.heading_size = static_cast<float>(field_number(L, 1, "heading_size", t.heading_size));
                if (has_field(L, 1, "text")) t.text = UiColor::hex(field_text(L, 1, "text"));
                if (has_field(L, 1, "heading")) t.heading = UiColor::hex(field_text(L, 1, "heading"));
                if (has_field(L, 1, "muted")) t.muted = UiColor::hex(field_text(L, 1, "muted"));
                if (has_field(L, 1, "accent")) t.accent = UiColor::hex(field_text(L, 1, "accent"));
                if (has_field(L, 1, "button")) t.button = UiColor::hex(field_text(L, 1, "button"));
                if (has_field(L, 1, "panel")) t.panel = UiColor::hex(field_text(L, 1, "panel"));
                if (has_field(L, 1, "typeface")) t.typeface = field_text(L, 1, "typeface");
                if (has_field(L, 1, "game_font")) t.game_font = field_bool(L, 1, "game_font", true);
                if (has_field(L, 1, "control_scale")) t.control_scale = static_cast<float>(field_number(L, 1, "control_scale", t.control_scale));
                if (has_field(L, 1, "control_width")) t.control_width = field_number(L, 1, "control_width", t.control_width);
                return 0;
            }
            lua_newtable(L);
            lua_set_field(L, "text_size", static_cast<double>(t.text_size));
            lua_set_field(L, "heading_size", static_cast<double>(t.heading_size));
            lua_set_field(L, "text", std::wstring_view(t.text.to_hex()));
            lua_set_field(L, "heading", std::wstring_view(t.heading.to_hex()));
            lua_set_field(L, "muted", std::wstring_view(t.muted.to_hex()));
            lua_set_field(L, "accent", std::wstring_view(t.accent.to_hex()));
            lua_set_field(L, "button", std::wstring_view(t.button.to_hex()));
            lua_set_field(L, "panel", std::wstring_view(t.panel.to_hex()));
            lua_set_field(L, "typeface", std::wstring_view(t.typeface));
            lua_set_field(L, "game_font", t.game_font);
            lua_set_field(L, "control_scale", static_cast<double>(t.control_scale));
            lua_set_field(L, "control_width", t.control_width);
            return 1;
        }

        struct Entry
        {
            const char* name;
            lua_CFunction fn;
        };
        inline auto entries() -> const std::vector<Entry>&
        {
            static const std::vector<Entry> all = {
                {"make", f_make},         {"game_widget", f_game_widget}, {"text", f_text},        {"heading", f_heading},
                {"note", f_note},         {"button", f_button},     {"check", f_check},      {"slider", f_slider},
                {"number", f_number},     {"input", f_input},       {"choice", f_choice},    {"progress", f_progress},
                {"image", f_image},       {"rect", f_rect},         {"hbox", f_hbox},        {"vbox", f_vbox},
                {"scroll", f_scroll},     {"border", f_border},     {"box", f_box},          {"spacer", f_spacer},
                {"canvas", f_canvas},     {"row", f_row},           {"labelled", f_labelled}, {"scaled", f_scaled},
                {"add", f_add},           {"remove", f_remove},     {"clear", f_clear},      {"parent", f_parent},
                {"children", f_children}, {"find", f_find},         {"find_all", f_find_all}, {"slot", f_slot},
                {"place", f_place},       {"at", f_at},
                {"visible", f_visible},   {"enabled", f_enabled},   {"opacity", f_opacity},  {"focus", f_focus},
                {"focused", f_focused},   {"font", f_font},         {"color", f_color},      {"tint", f_tint},
                {"wrap", f_wrap},         {"justify", f_justify},   {"hint", f_hint},        {"padding", f_padding},
                {"size", f_size},         {"scale", f_scale},       {"angle", f_angle},      {"translate", f_translate},
                {"tooltip", f_tooltip},   {"value", f_value},       {"checked", f_checked},  {"range", f_range},
                {"options", f_options},   {"option", f_option},     {"active", f_active},    {"play", f_play},
                {"clicked", f_clicked},   {"changed", f_changed},   {"hovered", f_hovered},  {"valid", f_valid},
                {"viewport", f_viewport}, {"cursor", f_cursor},     {"overlay", f_overlay},  {"remove_overlay", f_remove_overlay},
                {"screen", f_screen},     {"hud", f_hud},           {"tab", f_tab},          {"tab_page", f_tab_page},
                {"tab_active", f_tab_active}, {"remove_tab", f_remove_tab}, {"tabs", f_tabs}, {"theme", f_theme},
            };
            return all;
        }
    } // namespace uilua

    // ModBase calls this as each Lua mod's state starts, after lua_started (Menu.hpp): the state gets
    // WCModsCpp.ui, once (the first C++ mod to start puts it there; every mod's is the same).
    inline auto lua_started_ui(RC::LuaMadeSimple::Lua& lua) -> void
    {
        lua_State* L = lua.get_lua_state();
        int top = lua_gettop(L);
        lua_getglobal(L, "WCModsCpp");
        if (!lua_istable(L, -1))
        {
            lua_settop(L, top);
            return;
        }
        lua_getfield(L, -1, "ui");
        if (lua_istable(L, -1))
        {
            lua_settop(L, top);
            return;
        }
        lua_pop(L, 1);
        lua_newtable(L);
        for (const uilua::Entry& e : uilua::entries())
        {
            lua_pushcfunction(L, e.fn);
            lua_setfield(L, -2, e.name);
        }
        lua_setfield(L, -2, "ui");
        lua_settop(L, top);
    }
    } // namespace detail
} // namespace wcmods
