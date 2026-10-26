// WCMods/Ui.hpp: the game's own UI (UMG) for C++ mods: pages of your own in the game's menus (a tab in the
// pause screen, the inventory, the settings...), the HUD and its parts, overlays on the viewport, and every
// kind of control the engine has, made, placed, styled and watched from C++. Everything calls back on the game
// thread. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call. UiLua.hpp hands the same to
// Lua mods as WCModsCpp.ui.
//
//   wcmods::ui::tab(L"WBP_GuiScreenPause_C", L"Mods", [](wcmods::Widget page) {
//       page.add(wcmods::ui::heading(L"My mod"));
//       auto on = wcmods::ui::checkbox(true);
//       page.add(wcmods::ui::row({wcmods::ui::text(L"Enabled"), on}));
//       on.on_toggle([](bool v) { wcmods::log(L"enabled: {}", v); });
//   });
//
//   wcmods::ui::hud().find(L"mcGuiMinimap").collapse();          // no minimap
//   auto note = wcmods::ui::text(L"Hello", {.size = 40});
//   wcmods::ui::overlay(L"notes").add(note).at(100, 100);        // on the viewport, over the game's UI
//
// Sizes are in the game's own units: its UI is laid out for a 3840x2160 screen and scaled to fit, so a
// 52-point title and a 1100-wide panel look as the game's do. A Widget is a handle: it knows when the game
// has destroyed what it points at (then it's false), and every call on an empty one does nothing.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
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

#include <Unreal/CoreUObject/UObject/Class.hpp>
#include <Unreal/CoreUObject/UObject/UnrealType.hpp>
#include <Unreal/FText.hpp>
#include <Unreal/UObjectArray.hpp>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>

namespace wcmods
{
    // ============================================================================================ plain values
    // ESlateVisibility, as the engine numbers it.
    enum class Visibility { Visible = 0, Collapsed = 1, Hidden = 2, HitTestInvisible = 3, SelfHitTestInvisible = 4 };
    // How a widget sits in its slot (EHorizontalAlignment / EVerticalAlignment share the numbers).
    enum class Align { Fill = 0, Start = 1, Center = 2, End = 3 };
    // A colour as an image editor shows it (sRGB), with its alpha; converted to the engine's linear colours
    // where a call wants one. UiColor::hex(L"#ffcc00") or UiColor::hex(L"#ffcc0080"). (UE4SS has a Color of its own.)
    struct UiColor
    {
        float r{}, g{}, b{}, a{1};
        static auto hex(std::wstring_view text) -> UiColor
        {
            UiColor c{1, 1, 1, 1};
            if (!text.empty() && text[0] == L'#') text.remove_prefix(1);
            if (text.size() != 6 && text.size() != 8) return c;
            auto part = [&](size_t at) {
                int v = 0;
                for (size_t i = at; i < at + 2; ++i)
                {
                    wchar_t ch = text[i];
                    int d = ch >= L'0' && ch <= L'9' ? ch - L'0' : ch >= L'a' && ch <= L'f' ? ch - L'a' + 10 : ch >= L'A' && ch <= L'F' ? ch - L'A' + 10 : 0;
                    v = v * 16 + d;
                }
                return v / 255.0f;
            };
            c.r = part(0), c.g = part(2), c.b = part(4);
            if (text.size() == 8) c.a = part(6);
            return c;
        }
        // "#rrggbb" or "#rrggbbaa" (when the alpha isn't 1).
        auto to_hex() const -> std::wstring
        {
            auto byte = [](float v) { return static_cast<int>(std::lround(std::clamp(v, 0.0f, 1.0f) * 255)); };
            std::wstring out = std::format(L"#{:02x}{:02x}{:02x}", byte(r), byte(g), byte(b));
            if (a < 0.999f) out += std::format(L"{:02x}", byte(a));
            return out;
        }
    };
    struct Margin
    {
        float left{}, top{}, right{}, bottom{};
        Margin() = default;
        Margin(float all) : left(all), top(all), right(all), bottom(all) {}
        Margin(float horizontal, float vertical) : left(horizontal), top(vertical), right(horizontal), bottom(vertical) {}
        Margin(float l, float t, float r, float b) : left(l), top(t), right(r), bottom(b) {}
    };
    struct Vec2
    {
        double x{}, y{};
    };

    namespace detail
    {
        // The engine's structs as they're laid out in this game (UE 5: FVector2D is two doubles).
        struct FVector2D_ { double x, y; };
        struct FMargin_ { float left, top, right, bottom; };
        struct FLinearColor_ { float r, g, b, a; };
        struct FAnchors_ { FVector2D_ min, max; };
        struct FSlateColor_ { FLinearColor_ color; uint8_t rule; uint8_t pad[3]; };
        struct FSlateChildSize_ { float value; uint8_t rule; uint8_t pad[3]; };
        static_assert(sizeof(FVector2D_) == 16 && sizeof(FMargin_) == 16 && sizeof(FLinearColor_) == 16 && sizeof(FAnchors_) == 32);
        static_assert(sizeof(FSlateColor_) == 20 && sizeof(FSlateChildSize_) == 8);

        inline auto linear_channel(float c) -> float { return c <= 0.04045f ? c / 12.92f : std::pow((c + 0.055f) / 1.055f, 2.4f); }
        inline auto srgb_channel(float c) -> float { return c <= 0.0031308f ? c * 12.92f : 1.055f * std::pow(c, 1 / 2.4f) - 0.055f; }
        inline auto linear(UiColor c) -> FLinearColor_ { return {linear_channel(c.r), linear_channel(c.g), linear_channel(c.b), c.a}; }
        inline auto from_linear(FLinearColor_ c) -> UiColor { return {srgb_channel(c.r), srgb_channel(c.g), srgb_channel(c.b), c.a}; }

        // Whether an object the game may have destroyed is still the object it was: its slot in the engine's
        // object array still holds it, it isn't on its way out, and it's still of the class it was.
        inline auto object_alive(UObject* o, UClass* was) -> bool
        {
            if (!o) return false;
            int32_t index = o->GetInternalIndex();
            if (index < 0 || index >= RC::Unreal::UObjectArray::GetNumElements()) return false;
            auto* item = RC::Unreal::UObjectArray::IndexToObject(index);
            if (!item || item->GetUObject() != o || !item->IsValid(false)) return false;
            return !was || o->GetClassPrivate() == was;
        }

        inline auto umg_class(std::wstring_view kind) -> UClass*
        {
            if (kind.find(L'/') != std::wstring_view::npos) return find_class(std::wstring(kind).c_str());
            return find_class((L"/Script/UMG." + std::wstring(kind)).c_str());
        }
        inline auto is_kind(UObject* o, const TCHAR* umg_path) -> bool { return is_a(o, umg_path); }
    } // namespace detail

    class Widget;

    // ============================================================================================ a widget's slot
    // How a widget sits in its parent: padding, how much room it takes (boxes), its anchors and place (a canvas),
    // its row and column (a grid). Each call applies when the slot is that kind, and is quietly nothing otherwise.
    class Slot
    {
      public:
        Slot() = default;
        explicit Slot(UObject* slot) : m_slot(slot), m_class(slot ? slot->GetClassPrivate() : nullptr) {}
        auto object() const -> UObject* { return valid() ? m_slot : nullptr; }
        auto valid() const -> bool { return detail::object_alive(m_slot, m_class); }
        explicit operator bool() const { return valid(); }
        auto type() const -> std::wstring { return class_name(object()); }

        // Room around the widget (boxes, overlays, borders, a scroll box, a grid).
        auto padding(Margin m) -> Slot&
        {
            call_reflected(object(), STR("SetPadding"), [&](Params& p) { put(p, L"InPadding", detail::FMargin_{m.left, m.top, m.right, m.bottom}); });
            return *this;
        }
        // In a horizontal or vertical box: take a share of the room left (`weight`), or only what's needed.
        auto fill(float weight = 1) -> Slot& { return child_size(true, weight); }
        auto fit() -> Slot& { return child_size(false, 1); }
        // Where it sits across its slot and down it (Align::Fill stretches it).
        auto align(Align horizontal, Align vertical) -> Slot&
        {
            call_reflected(object(), STR("SetHorizontalAlignment"), [&](Params& p) { p.set_nth(0, Value::of(static_cast<int>(horizontal))); });
            call_reflected(object(), STR("SetVerticalAlignment"), [&](Params& p) { p.set_nth(0, Value::of(static_cast<int>(vertical))); });
            return *this;
        }
        // A canvas: anchors (0..1 of the canvas, min and max corners), the offsets from them (left, top, and
        // right, bottom when the anchors differ, else width, height), the place and size, the alignment (which
        // point of the widget sits at its position), whether it sizes itself, and its layer.
        auto anchors(double min_x, double min_y, double max_x, double max_y) -> Slot&
        {
            call_reflected(object(), STR("SetAnchors"), [&](Params& p) { put(p, L"InAnchors", detail::FAnchors_{{min_x, min_y}, {max_x, max_y}}); });
            return *this;
        }
        auto stretch(Margin inset = {}) -> Slot&   // fill the canvas, less an inset
        {
            anchors(0, 0, 1, 1);
            return offsets(inset);
        }
        auto offsets(Margin m) -> Slot&
        {
            call_reflected(object(), STR("SetOffsets"), [&](Params& p) { put(p, L"InOffset", detail::FMargin_{m.left, m.top, m.right, m.bottom}); });
            return *this;
        }
        auto position(double x, double y) -> Slot&
        {
            call_reflected(object(), STR("SetPosition"), [&](Params& p) { put(p, L"InPosition", detail::FVector2D_{x, y}); });
            return *this;
        }
        auto size(double w, double h) -> Slot&
        {
            if (!is_canvas()) return *this;   // a box slot's SetSize takes a share, not pixels (fill(), fit())
            call_reflected(object(), STR("SetSize"), [&](Params& p) { put(p, L"InSize", detail::FVector2D_{w, h}); });
            return *this;
        }
        auto alignment(double x, double y) -> Slot&
        {
            call_reflected(object(), STR("SetAlignment"), [&](Params& p) { put(p, L"InAlignment", detail::FVector2D_{x, y}); });
            return *this;
        }
        auto auto_size(bool on) -> Slot&
        {
            call_reflected(object(), STR("SetAutoSize"), [&](Params& p) { p.set_nth(0, Value::of(on)); });
            return *this;
        }
        // On a canvas: the widget's top-left at a place, sized to its content.
        auto at(double x, double y) -> Slot& { return auto_size(true).position(x, y); }
        auto layer(int z) -> Slot&
        {
            call_reflected(object(), STR("SetZOrder"), [&](Params& p) { p.set_nth(0, Value::of(z)); });
            return *this;
        }
        // A grid: the cell, and how many it spans.
        auto cell(int row, int column, int row_span = 1, int column_span = 1) -> Slot&
        {
            call_reflected(object(), STR("SetRow"), [&](Params& p) { p.set_nth(0, Value::of(row)); });
            call_reflected(object(), STR("SetColumn"), [&](Params& p) { p.set_nth(0, Value::of(column)); });
            call_reflected(object(), STR("SetRowSpan"), [&](Params& p) { p.set_nth(0, Value::of(row_span)); });
            call_reflected(object(), STR("SetColumnSpan"), [&](Params& p) { p.set_nth(0, Value::of(column_span)); });
            return *this;
        }

      private:
        UObject* m_slot{};
        UClass* m_class{};
        auto child_size(bool fill, float weight) -> Slot&
        {
            // A box slot's SetSize takes an FSlateChildSize; a canvas slot's takes a size in pixels (size()).
            if (!is_box()) return *this;
            call_reflected(object(), STR("SetSize"), [&](Params& p) { put_nth(p, 0, detail::FSlateChildSize_{weight, static_cast<uint8_t>(fill ? 1 : 0)}); });
            return *this;
        }
        auto is_box() const -> bool
        {
            return wcmods::is_a(object(), STR("/Script/UMG.HorizontalBoxSlot")) || wcmods::is_a(object(), STR("/Script/UMG.VerticalBoxSlot"));
        }
        auto is_canvas() const -> bool { return wcmods::is_a(object(), STR("/Script/UMG.CanvasPanelSlot")); }
        template <typename T>
        static auto put(Params& p, std::wstring_view name, const T& value) -> void
        {
            if (void* at = p.raw(name)) std::memcpy(at, &value, sizeof(T));
        }
        template <typename T>
        static auto put_nth(Params& p, int index, const T& value) -> void
        {
            if (void* at = p.nth(index).at) std::memcpy(at, &value, sizeof(T));
        }
        friend class Widget;
    };

    // ============================================================================================ a widget
    // A handle on any widget of the game's UI: one of the engine's controls or panels, one the mod made, or a
    // part of the game's own screens. It checks the object is still there before every call, so a widget the
    // game destroyed (a screen that closed) is false and does nothing.
    class Widget
    {
      public:
        Widget() = default;
        explicit Widget(UObject* object) : m_object(object), m_class(object ? object->GetClassPrivate() : nullptr) {}

        auto object() const -> UObject* { return valid() ? m_object : nullptr; }
        auto valid() const -> bool { return detail::object_alive(m_object, m_class); }
        explicit operator bool() const { return valid(); }
        auto operator==(const Widget& other) const -> bool { return m_object == other.m_object; }
        // Its name ("mcGuiMinimap"), its class ("TextBlock", "WBP_GuiButtonTab_C"), and whether it's of a class
        // by path (L"/Script/UMG.PanelWidget") or a subclass.
        auto name() const -> std::wstring { return wcmods::name(object()); }
        auto type() const -> std::wstring { return class_name(object()); }
        auto is_a(const TCHAR* class_path) const -> bool { return wcmods::is_a(object(), class_path); }

        // ---------------------------------------------------------------------------- the tree
        // The widget this one sits in; the widgets in this one (a panel's children, or a user widget's root).
        auto parent() const -> Widget
        {
            auto r = call_reflected(object(), STR("GetParent"));
            return Widget(r ? r->get(L"ReturnValue").object : nullptr);
        }
        auto children() const -> std::vector<Widget>
        {
            std::vector<Widget> out;
            UObject* o = object();
            if (!o) return out;
            if (Value tree = wcmods::get(o, L"WidgetTree.RootWidget"); tree.object)
            {
                out.emplace_back(tree.object);
                return out;
            }
            auto n = call_reflected(o, STR("GetChildrenCount"));
            int count = n ? static_cast<int>(n->get(L"ReturnValue").number()) : 0;
            for (int i = 0; i < count; ++i)
            {
                auto c = call_reflected(o, STR("GetChildAt"), [&](Params& p) { p.set_nth(0, Value::of(i)); });
                if (c && c->get(L"ReturnValue").object) out.emplace_back(c->get(L"ReturnValue").object);
            }
            return out;
        }
        auto child(int index) const -> Widget
        {
            auto all = children();
            return index >= 0 && index < static_cast<int>(all.size()) ? all[static_cast<size_t>(index)] : Widget();
        }
        auto count() const -> int { return static_cast<int>(children().size()); }
        // A widget in here by its name, anywhere down the tree ("mcGuiMinimap"); the game's own screens name
        // their parts, so this is how to reach them. The first found, or an empty Widget.
        auto find(std::wstring_view name) const -> Widget
        {
            Widget hit;
            walk([&](const Widget& w) {
                if (w.name() == name) hit = w;
                return !hit;
            });
            return hit;
        }
        // Every widget in here of a class ("TextBlock"), or every widget when the class is empty.
        auto find_all(std::wstring_view type = {}) const -> std::vector<Widget>
        {
            std::vector<Widget> out;
            walk([&](const Widget& w) {
                if (type.empty() || w.type() == type) out.push_back(w);
                return true;
            });
            return out;
        }
        // Every widget down the tree, `fn(widget)` on each (false stops).
        auto walk(const std::function<bool(const Widget&)>& fn) const -> void
        {
            bool go = true;
            walk_from(*this, fn, go, 0);
        }

        // Put a widget inside this one: at the end of a panel (a box, a canvas, an overlay, a grid...), or as the
        // one content of a border, a size box, a button, a scroll box's... The slot it got, to place it with.
        auto add(const Widget& child) -> Slot
        {
            UObject* o = object();
            UObject* c = child.object();
            if (!o || !c) return {};
            if (wcmods::is_a(o, STR("/Script/UMG.ContentWidget")))
            {
                call_reflected(o, STR("SetContent"), [&](Params& p) { p.set_nth(0, Value::of(c)); });
                return child.slot();
            }
            if (!wcmods::is_a(o, STR("/Script/UMG.PanelWidget"))) return {};
            auto r = call_reflected(o, STR("AddChild"), [&](Params& p) { p.set_nth(0, Value::of(c)); });
            return Slot(r ? r->get(L"ReturnValue").object : nullptr);
        }
        auto add(std::initializer_list<Widget> widgets) -> Widget&
        {
            for (const Widget& w : widgets) add(w);
            return *this;
        }
        // Take a child out; take this one out of wherever it is; take every child out.
        auto remove(const Widget& child) -> bool
        {
            auto r = call_reflected(object(), STR("RemoveChild"), [&](Params& p) { p.set_nth(0, Value::of(child.object())); });
            return r && r->get(L"ReturnValue").boolean();
        }
        auto remove() -> void { call_reflected(object(), STR("RemoveFromParent")); }
        auto clear() -> void { call_reflected(object(), STR("ClearChildren")); }
        // The slot this widget sits in.
        auto slot() const -> Slot { return Slot(wcmods::get(object(), L"Slot").object); }
        // On a canvas: put it at a place (its top-left there, sized to its content).
        auto at(double x, double y) -> Widget&
        {
            slot().auto_size(true).position(x, y);
            return *this;
        }

        // ---------------------------------------------------------------------------- showing
        auto visibility() const -> Visibility
        {
            auto r = call_reflected(object(), STR("GetVisibility"));
            return r ? static_cast<Visibility>(static_cast<int>(r->get(L"ReturnValue").number())) : Visibility::Collapsed;
        }
        auto set_visibility(Visibility v) -> Widget&
        {
            call_reflected(object(), STR("SetVisibility"), [&](Params& p) { p.set_nth(0, Value::of(static_cast<int>(v))); });
            return *this;
        }
        // Shown and taking input; shown and letting input through to what's under it; hidden but keeping its
        // room; gone (no room).
        auto show() -> Widget& { return set_visibility(Visibility::Visible); }
        auto show_passive() -> Widget& { return set_visibility(Visibility::SelfHitTestInvisible); }
        auto hide() -> Widget& { return set_visibility(Visibility::Hidden); }
        auto collapse() -> Widget& { return set_visibility(Visibility::Collapsed); }
        // Whether it's drawn now (on screen, and nothing up the tree hides it).
        auto visible() const -> bool
        {
            auto r = call_reflected(object(), STR("IsVisible"));
            return r && r->get(L"ReturnValue").boolean();
        }
        auto enabled() const -> bool { return wcmods::get(object(), L"bIsEnabled").boolean(); }
        auto set_enabled(bool on) -> Widget&
        {
            call_reflected(object(), STR("SetIsEnabled"), [&](Params& p) { p.set_nth(0, Value::of(on)); });
            return *this;
        }
        auto opacity() const -> float { return static_cast<float>(wcmods::get(object(), L"RenderOpacity").number(1)); }
        auto set_opacity(float value) -> Widget&
        {
            call_reflected(object(), STR("SetRenderOpacity"), [&](Params& p) { p.set_nth(0, Value::of(static_cast<double>(value))); });
            return *this;
        }
        // Drawn bigger or smaller, turned (degrees), moved from where it's laid out, around a pivot (0..1 of it).
        auto set_scale(double x, double y) -> Widget&
        {
            call_reflected(object(), STR("SetRenderScale"), [&](Params& p) { Slot::put(p, L"Scale", detail::FVector2D_{x, y}); });
            return *this;
        }
        auto set_angle(float degrees) -> Widget&
        {
            call_reflected(object(), STR("SetRenderTransformAngle"), [&](Params& p) { p.set_nth(0, Value::of(static_cast<double>(degrees))); });
            return *this;
        }
        auto set_translation(double x, double y) -> Widget&
        {
            call_reflected(object(), STR("SetRenderTranslation"), [&](Params& p) { Slot::put(p, L"Translation", detail::FVector2D_{x, y}); });
            return *this;
        }
        auto set_pivot(double x, double y) -> Widget&
        {
            call_reflected(object(), STR("SetRenderTransformPivot"), [&](Params& p) { Slot::put(p, L"Pivot", detail::FVector2D_{x, y}); });
            return *this;
        }
        auto set_tooltip(std::wstring_view text) -> Widget&
        {
            call_reflected(object(), STR("SetToolTipText"), [&](Params& p) { p.set_nth(0, Value::of(text)); });
            return *this;
        }
        // The keyboard's (and a controller's) focus: give it to this widget, and whether it or a widget in it has it.
        auto focus() -> Widget&
        {
            call_reflected(object(), STR("SetKeyboardFocus"));
            return *this;
        }
        auto focused() const -> bool
        {
            auto a = call_reflected(object(), STR("HasKeyboardFocus"));
            auto b = call_reflected(object(), STR("HasFocusedDescendants"));
            return (a && a->get(L"ReturnValue").boolean()) || (b && b->get(L"ReturnValue").boolean());
        }
        auto hovered() const -> bool
        {
            auto r = call_reflected(object(), STR("IsHovered"));
            return r && r->get(L"ReturnValue").boolean();
        }

        // ---------------------------------------------------------------------------- text
        // The text a text block, a text box, a rich text block or a button (its text block) shows.
        auto text() const -> std::wstring
        {
            UObject* o = text_object();
            auto r = call_reflected(o, STR("GetText"));
            if (r) return r->get(L"ReturnValue").string();
            if (Value t = wcmods::get(o, L"Text"); t) return t.string();   // a game control with a Text property
            return {};
        }
        auto set_text(std::wstring_view text) -> Widget&
        {
            UObject* o = text_object();
            if (!call_reflected(o, STR("SetText"), [&](Params& p) { p.set_nth(0, Value::of(text)); }))
            {
                // A game control (a GuiButtonState tab): its Text property, and the blocks it shows it in.
                wcmods::set(object(), L"Text", Value::of(text));
                for (const wchar_t* block : {L"mcGuiTextNormal", L"mcGuiTextSelected", L"mcGuiTextDisabled", L"mcGuiTextPressed", L"mcGuiTextOver",
                                             L"mcGuiTextTitleNormal", L"mcGuiTextTitleSelected", L"mcGuiTextTitleDisabled", L"mcGuiTextTitleOver"})
                    call_reflected(wcmods::get(object(), block).object, STR("SetText"), [&](Params& p) { p.set_nth(0, Value::of(text)); });
            }
            return *this;
        }
        // A text box's hint, shown while it's empty.
        auto set_hint(std::wstring_view text) -> Widget&
        {
            call_reflected(object(), STR("SetHintText"), [&](Params& p) { p.set_nth(0, Value::of(text)); });
            return *this;
        }
        // The text's size (points, in the game's units: its titles are 52, its rows about 36) and, with a name,
        // its font ("Regular", "Bold"; the face must exist in the font). Keeps the font that was set.
        auto set_font(float size, std::wstring_view typeface = {}) -> Widget&
        {
            UObject* o = text_object();
            Value font = wcmods::get(o, L"Font");
            if (!font) font = wcmods::get(o, L"WidgetStyle.Font");
            if (font.kind != Value::Kind::Struct) return *this;
            if (!call_reflected(o, STR("SetFont"), [&](Params& p) {
                    void* at = p.raw(L"InFontInfo");
                    auto* type = static_cast<RC::Unreal::UStruct*>(static_cast<RC::Unreal::FStructProperty*>(font.property)->GetStruct());
                    if (!at || !type) return;
                    std::memcpy(at, font.at, static_cast<size_t>(type->GetStructureSize()));
                    Value in = p.get(L"InFontInfo");
                    wcmods::set(in, L"Size", static_cast<double>(size));
                    if (!typeface.empty()) wcmods::set(in, L"TypefaceFontName", typeface);
                }))
            {
                wcmods::set(font, L"Size", static_cast<double>(size));
                if (!typeface.empty()) wcmods::set(font, L"TypefaceFontName", typeface);
            }
            return *this;
        }
        // The text's colour (a text block, a text box, a rich text block, a button's text).
        auto set_color(UiColor c) -> Widget&
        {
            UObject* o = text_object();
            auto lin = detail::linear(c);
            if (!call_reflected(o, STR("SetColorAndOpacity"), [&](Params& p) {
                    Value v = p.nth(0);
                    if (v.type == L"SlateColor") Slot::put_nth(p, 0, detail::FSlateColor_{lin, 0});
                    else Slot::put_nth(p, 0, lin);
                }))
                call_reflected(o, STR("SetForegroundColor"), [&](Params& p) {
                    if (p.nth(0).type == L"SlateColor") Slot::put_nth(p, 0, detail::FSlateColor_{lin, 0});
                    else Slot::put_nth(p, 0, lin);
                });
            return *this;
        }
        auto set_wrap(bool on) -> Widget&
        {
            call_reflected(text_object(), STR("SetAutoWrapText"), [&](Params& p) { p.set_nth(0, Value::of(on)); });
            return *this;
        }
        auto set_justify(Align how) -> Widget&   // Start, Center, End
        {
            int j = how == Align::Center ? 1 : how == Align::End ? 2 : 0;
            call_reflected(text_object(), STR("SetJustification"), [&](Params& p) { p.set_nth(0, Value::of(j)); });
            return *this;
        }
        // A shadow under the text (an offset of 0 takes it off).
        auto set_shadow(float offset = 2, UiColor c = {0, 0, 0, 0.8f}) -> Widget&
        {
            UObject* o = text_object();
            call_reflected(o, STR("SetShadowOffset"), [&](Params& p) { Slot::put(p, L"InShadowOffset", detail::FVector2D_{offset, offset}); });
            call_reflected(o, STR("SetShadowColorAndOpacity"), [&](Params& p) { Slot::put(p, L"InShadowColorAndOpacity", detail::linear(c)); });
            return *this;
        }

        // ---------------------------------------------------------------------------- values
        // What a control holds: a slider's or spin box's number, a progress bar's fraction, a check box (1 or
        // 0), a drop-down's chosen index.
        auto value() const -> double
        {
            UObject* o = object();
            if (auto r = call_reflected(o, STR("GetValue"))) return r->get(L"ReturnValue").number();
            if (auto r = call_reflected(o, STR("GetSelectedIndex"))) return r->get(L"ReturnValue").number();
            if (auto r = call_reflected(o, STR("IsChecked"))) return r->get(L"ReturnValue").boolean() ? 1 : 0;
            if (Value v = wcmods::get(o, L"Percent"); v) return v.number();
            return 0;
        }
        auto set_value(double v) -> Widget&
        {
            UObject* o = object();
            if (call_reflected(o, STR("SetValue"), [&](Params& p) { p.set_nth(0, Value::of(v)); })) return *this;
            if (call_reflected(o, STR("SetSelectedIndex"), [&](Params& p) { p.set_nth(0, Value::of(static_cast<int>(v))); })) return *this;
            if (call_reflected(o, STR("SetIsChecked"), [&](Params& p) { p.set_nth(0, Value::of(v != 0)); })) return *this;
            call_reflected(o, STR("SetPercent"), [&](Params& p) { p.set_nth(0, Value::of(v)); });
            return *this;
        }
        // A slider's or spin box's range, and the step it moves in (0 keeps it smooth).
        auto set_range(double lo, double hi, double step = 0) -> Widget&
        {
            UObject* o = object();
            call_reflected(o, STR("SetMinValue"), [&](Params& p) { p.set_nth(0, Value::of(lo)); });
            call_reflected(o, STR("SetMaxValue"), [&](Params& p) { p.set_nth(0, Value::of(hi)); });
            call_reflected(o, STR("SetMinSliderValue"), [&](Params& p) { p.set_nth(0, Value::of(lo)); });
            call_reflected(o, STR("SetMaxSliderValue"), [&](Params& p) { p.set_nth(0, Value::of(hi)); });
            if (step > 0)
            {
                call_reflected(o, STR("SetStepSize"), [&](Params& p) { p.set_nth(0, Value::of(step)); });
                call_reflected(o, STR("SetDelta"), [&](Params& p) { p.set_nth(0, Value::of(step)); });
            }
            return *this;
        }
        auto checked() const -> bool { return value() != 0; }
        auto set_checked(bool on) -> Widget& { return set_value(on ? 1 : 0); }
        // A drop-down's options, and the one chosen (by its text).
        auto add_option(std::wstring_view text) -> Widget&
        {
            call_reflected(object(), STR("AddOption"), [&](Params& p) { p.set_nth(0, Value::of(text)); });
            return *this;
        }
        auto set_options(std::initializer_list<std::wstring_view> options) -> Widget&
        {
            call_reflected(object(), STR("ClearOptions"));
            for (auto o : options) add_option(o);
            return *this;
        }
        auto options() const -> std::vector<std::wstring>
        {
            std::vector<std::wstring> out;
            auto n = call_reflected(object(), STR("GetOptionCount"));
            int count = n ? static_cast<int>(n->get(L"ReturnValue").number()) : 0;
            for (int i = 0; i < count; ++i)
            {
                auto r = call_reflected(object(), STR("GetOptionAtIndex"), [&](Params& p) { p.set_nth(0, Value::of(i)); });
                out.push_back(r ? r->get(L"ReturnValue").string() : std::wstring{});
            }
            return out;
        }
        auto option() const -> std::wstring
        {
            auto r = call_reflected(object(), STR("GetSelectedOption"));
            return r ? r->get(L"ReturnValue").string() : std::wstring{};
        }
        auto set_option(std::wstring_view text) -> Widget&
        {
            call_reflected(object(), STR("SetSelectedOption"), [&](Params& p) { p.set_nth(0, Value::of(text)); });
            return *this;
        }

        // ---------------------------------------------------------------------------- looks
        // An image's picture: a texture by its path (one the game has loaded), or an object.
        auto set_image(const TCHAR* texture_path) -> Widget& { return set_image(wcmods::object(texture_path)); }
        auto set_image(UObject* texture) -> Widget&
        {
            if (!texture) return *this;
            if (!call_reflected(object(), STR("SetBrushFromTexture"), [&](Params& p) {
                    p.set_nth(0, Value::of(texture));
                    p.set_nth(1, Value::of(false));
                }))
                call_reflected(object(), STR("SetBrushResourceObject"), [&](Params& p) { p.set_nth(0, Value::of(texture)); });
            return *this;
        }
        // The colour an image, a border, a button's background, a progress bar's fill or a slider's bar is drawn in.
        auto set_tint(UiColor c) -> Widget&
        {
            UObject* o = object();
            auto lin = detail::linear(c);
            auto with = [&](const TCHAR* fn) { return call_reflected(o, fn, [&](Params& p) { Slot::put_nth(p, 0, lin); }).has_value(); };
            if (wcmods::is_a(o, STR("/Script/UMG.Image"))) with(STR("SetColorAndOpacity"));
            if (wcmods::is_a(o, STR("/Script/UMG.Button"))) with(STR("SetBackgroundColor"));
            else if (wcmods::is_a(o, STR("/Script/UMG.Border"))) with(STR("SetBrushColor"));
            else if (wcmods::is_a(o, STR("/Script/UMG.ProgressBar"))) with(STR("SetFillColorAndOpacity"));
            else if (wcmods::is_a(o, STR("/Script/UMG.Slider")))
            {
                with(STR("SetSliderBarColor"));
                with(STR("SetSliderHandleColor"));
            }
            else if (!wcmods::is_a(o, STR("/Script/UMG.Image"))) with(STR("SetColorAndOpacity"));
            return *this;
        }
        // Room inside a border, a user widget, a blur box, a background blur.
        auto set_padding(Margin m) -> Widget&
        {
            call_reflected(object(), STR("SetPadding"), [&](Params& p) { Slot::put(p, L"InPadding", detail::FMargin_{m.left, m.top, m.right, m.bottom}); });
            return *this;
        }
        // A size box's width and height (0 leaves one free), a spacer's size, an image's size.
        auto set_size(double w, double h) -> Widget&
        {
            UObject* o = object();
            if (wcmods::is_a(o, STR("/Script/UMG.SizeBox")))
            {
                if (w > 0) call_reflected(o, STR("SetWidthOverride"), [&](Params& p) { p.set_nth(0, Value::of(w)); });
                else call_reflected(o, STR("ClearWidthOverride"));
                if (h > 0) call_reflected(o, STR("SetHeightOverride"), [&](Params& p) { p.set_nth(0, Value::of(h)); });
                else call_reflected(o, STR("ClearHeightOverride"));
            }
            else if (wcmods::is_a(o, STR("/Script/UMG.Spacer")))
                call_reflected(o, STR("SetSize"), [&](Params& p) { Slot::put(p, L"InSize", detail::FVector2D_{w, h}); });
            else if (wcmods::is_a(o, STR("/Script/UMG.Image")))
                call_reflected(o, STR("SetDesiredSizeOverride"), [&](Params& p) { Slot::put(p, L"DesiredSize", detail::FVector2D_{w, h}); });
            else
                slot().size(w, h);
            return *this;
        }
        // A widget switcher: which child shows.
        auto set_active(int index) -> Widget&
        {
            call_reflected(object(), STR("SetActiveWidgetIndex"), [&](Params& p) { p.set_nth(0, Value::of(index)); });
            return *this;
        }
        // A user widget's animation by name, played; and whether one is playing.
        auto play(std::wstring_view animation, bool reverse = false) -> bool
        {
            UObject* anim = wcmods::get(object(), animation).object;
            if (!anim) return false;
            if (reverse) return call_reflected(object(), STR("PlayAnimationReverse"), [&](Params& p) {
                              p.set_nth(0, Value::of(anim));
                              p.set_nth(1, Value::of(1.0));
                              p.set_nth(2, Value::of(false));
                          }).has_value();
            return call_reflected(object(), STR("PlayAnimation"), [&](Params& p) {
                       p.set_nth(0, Value::of(anim));
                       p.set_nth(1, Value::of(0.0));
                       p.set_nth(2, Value::of(1));
                       p.set_nth(3, Value::of(0));
                       p.set_nth(4, Value::of(1.0));
                       p.set_nth(5, Value::of(false));
                   }).has_value();
        }

        // ---------------------------------------------------------------------------- anything else
        // Any property by its path and any reflected function, as Reflect.hpp has them: for the parts of a
        // control this handle doesn't cover (python wcmods.py inspect lists them).
        auto get(std::wstring_view path) const -> Value { return wcmods::get(object(), path); }
        auto set(std::wstring_view path, const Value& value) -> bool { return wcmods::set(object(), path, value); }
        auto set(std::wstring_view path, bool value) -> bool { return set(path, Value::of(value)); }
        auto set(std::wstring_view path, double value) -> bool { return set(path, Value::of(value)); }
        auto set(std::wstring_view path, int value) -> bool { return set(path, Value::of(value)); }
        auto set(std::wstring_view path, std::wstring_view value) -> bool { return set(path, Value::of(value)); }
        auto set(std::wstring_view path, const wchar_t* value) -> bool { return set(path, Value::of(value)); }
        auto set(std::wstring_view path, UObject* value) -> bool { return set(path, Value::of(value)); }
        auto call(const TCHAR* function, const std::function<void(Params&)>& fill = {}) const -> std::optional<Params>
        {
            return call_reflected(object(), function, fill);
        }

        // ---------------------------------------------------------------------------- what the player does
        // `fn()` when a button is clicked, `fn(value)` when a slider, spin box or drop-down (its index) changes,
        // `fn(on)` when a check box is ticked or unticked, `fn(text)` when a text box's text changes; each looked
        // at every frame on the game thread while the widget lasts.
        auto on_click(std::function<void()> fn) -> Widget&;
        auto on_change(std::function<void(double)> fn) -> Widget&;
        auto on_toggle(std::function<void(bool)> fn) -> Widget&;
        auto on_text(std::function<void(std::wstring)> fn) -> Widget&;
        // The same, asked rather than told: true on the frame a button was clicked, or a value changed since
        // the last time it was asked (the first ask starts the watch and says false).
        auto clicked() -> bool;
        auto changed() -> bool;

      private:
        UObject* m_object{};
        UClass* m_class{};

        // The object that holds the text: the widget, or a button's text block.
        auto text_object() const -> UObject*
        {
            UObject* o = object();
            if (o && wcmods::is_a(o, STR("/Script/UMG.ContentWidget")) && !wcmods::is_a(o, STR("/Script/UMG.Border")))
            {
                auto r = call_reflected(o, STR("GetContent"));
                UObject* content = r ? r->get(L"ReturnValue").object : nullptr;
                if (content && wcmods::is_a(content, STR("/Script/UMG.TextLayoutWidget"))) return content;
            }
            return o;
        }
        static auto walk_from(const Widget& w, const std::function<bool(const Widget&)>& fn, bool& go, int depth) -> void
        {
            if (!go || depth > 40 || !w) return;
            go = fn(w);
            if (!go) return;
            for (const Widget& c : w.children()) walk_from(c, fn, go, depth + 1);
        }
    };

    // ============================================================================================ events
    namespace detail
    {
        struct Watch
        {
            Widget widget;
            enum class Kind { Click, Change, Toggle, Text } kind;
            std::function<void()> click;
            std::function<void(double)> change;
            std::function<void(bool)> toggle;
            std::function<void(std::wstring)> text;
            bool pressed{};        // a button: was it down last frame
            bool by_mouse{};       // and did the mouse press it (else a key or a controller)
            double last{};         // a value
            std::wstring last_text;
            bool primed{};         // the first look sets `last` rather than reporting a change
            bool fired{};          // a click or change seen, for clicked()/changed()
            bool polled{};         // made by clicked()/changed() rather than a callback
        };
        struct UiState
        {
            std::mutex lock;
            std::vector<std::shared_ptr<Watch>> watches;
            bool ticking{};
        };
        inline auto ui_state() -> UiState&
        {
            static UiState s;
            return s;
        }

        // Look at one watch: did its widget do something this frame? Calls the callback (a callback watch) or
        // marks it (a polled one).
        inline auto look(Watch& w) -> void
        {
            UObject* o = w.widget.object();
            if (!o) return;
            auto mark = [&](auto&& call) {
                if (w.polled) w.fired = true;
                else guarded(L"a widget's event", call);
            };
            switch (w.kind)
            {
            case Watch::Kind::Click:
            {
                auto r = call_reflected(o, STR("IsPressed"));
                bool down = r && r->get(L"ReturnValue").boolean();
                if (down && !w.pressed) w.by_mouse = w.widget.hovered();
                bool released = w.pressed && !down;
                w.pressed = down;
                if (!released) return;
                if (w.by_mouse ? w.widget.hovered() : w.widget.focused()) mark([&] { w.click(); });
                return;
            }
            case Watch::Kind::Change:
            case Watch::Kind::Toggle:
            {
                double now = w.widget.value();
                if (!w.primed)
                {
                    w.primed = true;
                    w.last = now;
                    return;
                }
                if (now == w.last) return;
                w.last = now;
                if (w.kind == Watch::Kind::Toggle) mark([&] { w.toggle(now != 0); });
                else mark([&] { w.change(now); });
                return;
            }
            case Watch::Kind::Text:
            {
                std::wstring now = w.widget.text();
                if (!w.primed)
                {
                    w.primed = true;
                    w.last_text = now;
                    return;
                }
                if (now == w.last_text) return;
                w.last_text = now;
                mark([&] { w.text(now); });
                return;
            }
            }
        }

        inline auto ui_tick() -> void
        {
            std::vector<std::shared_ptr<Watch>> watches;
            {
                UiState& s = ui_state();
                std::lock_guard lock(s.lock);
                std::erase_if(s.watches, [](const std::shared_ptr<Watch>& w) { return !w->widget.valid(); });
                watches = s.watches;
            }
            for (auto& w : watches)
                if (!w->polled) look(*w);
        }

        inline auto add_watch(std::shared_ptr<Watch> w) -> void
        {
            UiState& s = ui_state();
            bool start = false;
            {
                std::lock_guard lock(s.lock);
                s.watches.push_back(std::move(w));
                if (!s.ticking) s.ticking = start = true;
            }
            if (start) every_frame([](float) { ui_tick(); });
        }
        // The polled watch for a widget (clicked()/changed()), made on the first ask.
        inline auto polled_watch(const Widget& widget, Watch::Kind kind) -> std::shared_ptr<Watch>
        {
            UiState& s = ui_state();
            {
                std::lock_guard lock(s.lock);
                for (auto& w : s.watches)
                    if (w->polled && w->kind == kind && w->widget == widget) return w;
            }
            auto w = std::make_shared<Watch>();
            w->widget = widget;
            w->kind = kind;
            w->polled = true;
            add_watch(w);
            return w;
        }
    } // namespace detail

    inline auto Widget::on_click(std::function<void()> fn) -> Widget&
    {
        auto w = std::make_shared<detail::Watch>();
        w->widget = *this;
        w->kind = detail::Watch::Kind::Click;
        w->click = std::move(fn);
        detail::add_watch(w);
        return *this;
    }
    inline auto Widget::on_change(std::function<void(double)> fn) -> Widget&
    {
        auto w = std::make_shared<detail::Watch>();
        w->widget = *this;
        w->kind = detail::Watch::Kind::Change;
        w->change = std::move(fn);
        detail::add_watch(w);
        return *this;
    }
    inline auto Widget::on_toggle(std::function<void(bool)> fn) -> Widget&
    {
        auto w = std::make_shared<detail::Watch>();
        w->widget = *this;
        w->kind = detail::Watch::Kind::Toggle;
        w->toggle = std::move(fn);
        detail::add_watch(w);
        return *this;
    }
    inline auto Widget::on_text(std::function<void(std::wstring)> fn) -> Widget&
    {
        auto w = std::make_shared<detail::Watch>();
        w->widget = *this;
        w->kind = detail::Watch::Kind::Text;
        w->text = std::move(fn);
        detail::add_watch(w);
        return *this;
    }
    inline auto Widget::clicked() -> bool
    {
        auto w = detail::polled_watch(*this, detail::Watch::Kind::Click);
        w->fired = false;
        detail::look(*w);
        return w->fired;
    }
    inline auto Widget::changed() -> bool
    {
        auto w = detail::polled_watch(*this, detail::Watch::Kind::Change);
        w->fired = false;
        detail::look(*w);
        return w->fired;
    }

    namespace ui
    {
        // ============================================================================================ making widgets
        // The look the helpers below give what they make: the game's own font (Amarante, when it's loaded) and
        // its light text, in the game's units. Change it to change what the helpers make from then on.
        struct Theme
        {
            float text_size{36};
            float heading_size{52};
            UiColor text{UiColor::hex(L"#f2f2f2")};
            UiColor heading{UiColor::hex(L"#f6e7a6")};
            UiColor muted{UiColor::hex(L"#b9c3cf")};
            UiColor accent{UiColor::hex(L"#f0c846")};
            UiColor field{UiColor::hex(L"#101418c0")};
            UiColor button{UiColor::hex(L"#2a3442")};
            UiColor panel{UiColor::hex(L"#0b1218a0")};
            std::wstring typeface{L"Regular"};
            bool game_font{true};
            // The engine's own controls (check boxes, sliders, number and text boxes, drop-downs) are drawn for a
            // 1080-pixel screen; in the game's 2160-tall layout they're tiny, so labelled() and scaled() grow them.
            float control_scale{3.0f};
            double control_width{700};   // the control's room in a labelled row, in the game's units
        };
        inline auto theme() -> Theme&
        {
            static Theme t;
            return t;
        }

        namespace detail
        {
            // Where new widgets belong: a widget tree of the mod's own, under its overlay, until they're added
            // somewhere; the engine moves nothing, so the outer only matters for naming and lifetime.
            inline auto outer() -> UObject*;
            inline auto game_font() -> UObject*
            {
                static UObject* font{};
                if (!font) font = wcmods::object(STR("/Game/Art/UXD/Fonts/Amarante/Amarante.Amarante"));
                return font;
            }
            inline auto style_text(Widget w, float size, UiColor color) -> Widget
            {
                Theme& t = theme();
                UObject* font = t.game_font ? game_font() : nullptr;
                if (font) wcmods::set(w.object(), L"Font.FontObject", font);
                w.set_font(size, t.typeface);
                w.set_color(color);
                return w;
            }
        } // namespace detail

        namespace detail
        {
            // The engine's text and number boxes and drop-downs come white with dark text; the theme's field colour
            // and text go on their style's brushes (a brush the style hasn't got is quietly skipped).
            inline auto style_field(Widget& w) -> void
            {
                auto lin = wcmods::detail::linear(theme().field);
                auto text = wcmods::detail::linear(theme().text);
                auto tint = [&](std::wstring_view path, wcmods::detail::FLinearColor_ c) {
                    std::wstring base(path);
                    wcmods::set(w.object(), base + L".R", static_cast<double>(c.r));
                    wcmods::set(w.object(), base + L".G", static_cast<double>(c.g));
                    wcmods::set(w.object(), base + L".B", static_cast<double>(c.b));
                    wcmods::set(w.object(), base + L".A", static_cast<double>(c.a));
                };
                for (const wchar_t* brush : {L"WidgetStyle.BackgroundImageNormal", L"WidgetStyle.BackgroundImageHovered", L"WidgetStyle.BackgroundImageFocused",
                                             L"WidgetStyle.BackgroundImageReadOnly", L"WidgetStyle.BackgroundBrush", L"WidgetStyle.HoveredBackgroundBrush",
                                             L"WidgetStyle.ActiveBackgroundBrush", L"WidgetStyle.ActiveFillBrush", L"WidgetStyle.HoveredFillBrush",
                                             L"WidgetStyle.InactiveFillBrush", L"ItemStyle.InactiveBrush", L"ItemStyle.EvenRowBackgroundBrush",
                                             L"ItemStyle.OddRowBackgroundBrush", L"WidgetStyle.ComboButtonStyle.ButtonStyle.Normal",
                                             L"WidgetStyle.ComboButtonStyle.ButtonStyle.Hovered", L"WidgetStyle.ComboButtonStyle.ButtonStyle.Pressed",
                                             L"WidgetStyle.ComboButtonStyle.MenuBorderBrush"})
                    tint(std::wstring(brush) + L".TintColor.SpecifiedColor", lin);
                for (const wchar_t* fg : {L"WidgetStyle.ForegroundColor", L"ForegroundColor", L"ItemStyle.TextColor", L"ItemStyle.SelectedTextColor",
                                          L"WidgetStyle.ComboButtonStyle.ButtonStyle.NormalForeground", L"WidgetStyle.ComboButtonStyle.ButtonStyle.HoveredForeground",
                                          L"WidgetStyle.ComboButtonStyle.ButtonStyle.PressedForeground"})
                {
                    tint(std::wstring(fg) + L".SpecifiedColor", text);
                    wcmods::set(w.object(), std::wstring(fg) + L".ColorUseRule", 0);
                }
                auto accent = wcmods::detail::linear(theme().accent);
                for (const wchar_t* brush : {L"ItemStyle.ActiveBrush", L"ItemStyle.ActiveHoveredBrush", L"ItemStyle.InactiveHoveredBrush",
                                             L"ItemStyle.EvenRowBackgroundHoveredBrush", L"ItemStyle.OddRowBackgroundHoveredBrush",
                                             L"ItemStyle.ActiveHighlightedBrush", L"ItemStyle.InactiveHighlightedBrush", L"ItemStyle.SelectorFocusedBrush"})
                    tint(std::wstring(brush) + L".TintColor.SpecifiedColor", accent);
            }
            // A check box's pictures, bigger: the engine's are 16 pixels, small even scaled.
            inline auto size_checkbox(Widget& w, double px) -> void
            {
                for (const wchar_t* brush : {L"UncheckedImage", L"UncheckedHoveredImage", L"UncheckedPressedImage", L"CheckedImage", L"CheckedHoveredImage",
                                             L"CheckedPressedImage", L"UndeterminedImage", L"UndeterminedHoveredImage", L"UndeterminedPressedImage"})
                {
                    wcmods::set(w.object(), L"WidgetStyle." + std::wstring(brush) + L".ImageSize.X", px);
                    wcmods::set(w.object(), L"WidgetStyle." + std::wstring(brush) + L".ImageSize.Y", px);
                }
            }
        } // namespace detail

        // One of the engine's widgets by its class ("TextBlock", "Button", "CheckBox", "Slider", "SpinBox",
        // "ComboBoxString", "EditableTextBox", "MultiLineEditableTextBox", "ProgressBar", "Image", "Border",
        // "SizeBox", "Spacer", "HorizontalBox", "VerticalBox", "ScrollBox", "CanvasPanel", "Overlay",
        // "GridPanel", "UniformGridPanel", "WrapBox", "WidgetSwitcher", "ScaleBox", "ExpandableArea",
        // "BackgroundBlur", "Throbber", "CircularThrobber", "RichTextBlock"... any class in /Script/UMG), or by
        // a full class path. Plain, as the engine makes it: the helpers below style theirs. Empty when there's
        // no such class.
        inline auto widget(std::wstring_view kind) -> Widget
        {
            UClass* cls = wcmods::detail::umg_class(kind);
            if (!cls) return {};
            RC::Unreal::FStaticConstructObjectParameters params{cls};
            params.Outer = detail::outer();
            return Widget(RC::Unreal::UObjectGlobals::StaticConstructObject(params));
        }
        // One of the game's own widget Blueprints, by its class path ("/Game/Art/UXD/Blueprints/Controls/
        // gui_settings/WBP_GuiButtonTab.WBP_GuiButtonTab_C"), or by the class of a widget you have (the tabs of
        // a screen): made the way the game makes its widgets, for the player. Empty when the class isn't loaded.
        inline auto game_widget(UClass* cls) -> Widget
        {
            UObject* pc = controller();
            UObject* lib = wcmods::object(STR("/Script/UMG.Default__WidgetBlueprintLibrary"));
            if (!cls || !pc || !lib) return {};
            auto r = call_reflected(lib, STR("Create"), [&](Params& p) {
                p.set(L"WorldContextObject", pc);
                p.set(L"WidgetType", static_cast<UObject*>(cls));
                p.set(L"OwningPlayer", pc);
            });
            return Widget(r ? r->get(L"ReturnValue").object : nullptr);
        }
        inline auto game_widget(const TCHAR* class_path) -> Widget { return game_widget(find_class(class_path)); }

        struct TextOptions
        {
            float size{};          // 0: the theme's
            std::optional<UiColor> color;
            bool wrap{};
            Align justify{Align::Start};
        };
        // Text in the game's font; a heading; smaller grey text.
        inline auto text(std::wstring_view str, TextOptions o = {}) -> Widget
        {
            Widget w = widget(L"TextBlock");
            w.set_text(str);
            detail::style_text(w, o.size > 0 ? o.size : theme().text_size, o.color.value_or(theme().text));
            if (o.wrap) w.set_wrap(true);
            if (o.justify != Align::Start) w.set_justify(o.justify);
            return w;
        }
        inline auto heading(std::wstring_view str) -> Widget { return text(str, {.size = theme().heading_size, .color = theme().heading}); }
        inline auto note(std::wstring_view str) -> Widget { return text(str, {.size = theme().text_size * 0.8f, .color = theme().muted, .wrap = true}); }
        // A button with a label; clicks through on_click / clicked().
        inline auto button(std::wstring_view label, std::optional<UiColor> color = {}) -> Widget
        {
            Widget b = widget(L"Button");
            Widget t = text(label);
            b.add(t);
            b.set_tint(color.value_or(theme().button));
            return b;
        }
        inline auto checkbox(bool on = false) -> Widget
        {
            Widget c = widget(L"CheckBox");
            detail::size_checkbox(c, 24);
            c.set_checked(on);
            return c;
        }
        inline auto slider(double value, double lo = 0, double hi = 1, double step = 0) -> Widget
        {
            Widget s = widget(L"Slider");
            s.set_range(lo, hi, step);
            s.set_value(value);
            s.set_tint(theme().accent);
            return s;
        }
        // A number box you can drag or type in.
        inline auto number(double value, std::optional<double> lo = {}, std::optional<double> hi = {}, double step = 1) -> Widget
        {
            Widget s = widget(L"SpinBox");
            if (lo && hi) s.set_range(*lo, *hi, step);
            else if (step > 0) s.call(STR("SetDelta"), [&](Params& p) { p.set_nth(0, Value::of(step)); });
            s.set_value(value);
            detail::style_field(s);
            return s;
        }
        inline auto input(std::wstring_view value = {}, std::wstring_view hint = {}) -> Widget
        {
            Widget t = widget(L"EditableTextBox");
            t.set_text(value);
            if (!hint.empty()) t.set_hint(hint);
            detail::style_field(t);
            return t;
        }
        inline auto choice(std::initializer_list<std::wstring_view> options, std::wstring_view selected = {}) -> Widget
        {
            Widget c = widget(L"ComboBoxString");
            detail::style_field(c);
            c.set_options(options);
            if (!selected.empty()) c.set_option(selected);
            else if (options.size() > 0) c.set_value(0);
            return c;
        }
        inline auto progress(double fraction, std::optional<UiColor> color = {}) -> Widget
        {
            Widget p = widget(L"ProgressBar");
            p.set_value(fraction);
            p.set_tint(color.value_or(theme().accent));
            return p;
        }
        inline auto image(const TCHAR* texture_path, double w = 0, double h = 0) -> Widget
        {
            Widget i = widget(L"Image");
            i.set_image(texture_path);
            if (w > 0 && h > 0) i.set_size(w, h);
            return i;
        }
        // A flat colour, w by h.
        inline auto rect(UiColor color, double w, double h) -> Widget
        {
            Widget i = widget(L"Image");
            i.set_tint(color);
            i.set_size(w, h);
            return i;
        }
        // Layouts: widgets side by side, one under another, a list that scrolls, a box around one widget (a
        // colour and room inside), a fixed size, empty room, free placement, one over another, a grid, a flow
        // that wraps, one of several, and a scaled one.
        inline auto hbox() -> Widget { return widget(L"HorizontalBox"); }
        inline auto vbox() -> Widget { return widget(L"VerticalBox"); }
        inline auto scroll() -> Widget { return widget(L"ScrollBox"); }
        inline auto border(std::optional<UiColor> color = {}, Margin padding = {}) -> Widget
        {
            Widget b = widget(L"Border");
            b.set_tint(color.value_or(theme().panel));
            b.set_padding(padding);
            return b;
        }
        inline auto box(double w, double h = 0) -> Widget
        {
            Widget s = widget(L"SizeBox");
            s.set_size(w, h);
            return s;
        }
        inline auto spacer(double w, double h) -> Widget
        {
            Widget s = widget(L"Spacer");
            s.set_size(w, h);
            return s;
        }
        inline auto canvas() -> Widget { return widget(L"CanvasPanel"); }
        inline auto overlay_box() -> Widget { return widget(L"Overlay"); }
        inline auto grid() -> Widget { return widget(L"GridPanel"); }
        inline auto uniform_grid() -> Widget { return widget(L"UniformGridPanel"); }
        inline auto wrap() -> Widget { return widget(L"WrapBox"); }
        inline auto switcher() -> Widget { return widget(L"WidgetSwitcher"); }
        inline auto scale(double factor) -> Widget
        {
            Widget s = widget(L"ScaleBox");
            s.call(STR("SetStretch"), [&](Params& p) { p.set_nth(0, Value::of(7)); });   // EStretch::UserSpecified
            s.call(STR("SetUserSpecifiedScale"), [&](Params& p) { p.set_nth(0, Value::of(factor)); });
            return s;
        }
        // Widgets in a row, each with `gap` between, the first taking the room left (a label and its control).
        inline auto row(std::initializer_list<Widget> widgets, float gap = 24) -> Widget
        {
            Widget h = hbox();
            size_t i = 0;
            for (const Widget& w : widgets)
            {
                Slot s = h.add(w);
                s.align(Align::Fill, Align::Center);
                if (i == 0 && widgets.size() > 1) s.fill(1);
                if (i > 0) s.padding({gap, 0, 0, 0});
                ++i;
            }
            return h;
        }
        // One of the engine's controls grown to the game's size (the theme's control_scale), in a scale box; a
        // button or text is left as it is (they're made at the game's size already).
        inline auto scaled(const Widget& control, double width = 0) -> Widget
        {
            UObject* o = control.object();
            bool plain = wcmods::is_a(o, STR("/Script/UMG.Button")) || wcmods::is_a(o, STR("/Script/UMG.TextLayoutWidget")) || wcmods::is_a(o, STR("/Script/UMG.PanelWidget"));
            float factor = plain ? 1.0f : theme().control_scale;
            Widget s = scale(factor);
            if (width > 0)
            {
                Widget b = box(width / factor);
                b.add(control);
                control.slot().align(Align::Fill, Align::Center);
                s.add(b);
            }
            else
            {
                s.add(control);
            }
            return s;
        }
        // A labelled control, as the game's settings rows: the label at the left, the control (scaled to the
        // game's size) at the right in its room (the theme's control_width when 0).
        inline auto labelled(std::wstring_view label, const Widget& control, double control_width = 0) -> Widget
        {
            Widget h = hbox();
            h.add(text(label)).fill(1).align(Align::Fill, Align::Center);
            h.add(scaled(control, control_width > 0 ? control_width : theme().control_width)).fit().align(Align::End, Align::Center);
            return h;
        }

        // ============================================================================================ the viewport
        inline auto viewport_size() -> Vec2
        {
            UObject* lib = wcmods::object(STR("/Script/UMG.Default__WidgetLayoutLibrary"));
            auto r = call_reflected(lib, STR("GetViewportSize"), [&](Params& p) { p.set(L"WorldContextObject", controller()); });
            if (!r) return {};
            Value v = r->get(L"ReturnValue");
            return {get(v, L"X").number(), get(v, L"Y").number()};
        }
        inline auto viewport_scale() -> double
        {
            UObject* lib = wcmods::object(STR("/Script/UMG.Default__WidgetLayoutLibrary"));
            auto r = call_reflected(lib, STR("GetViewportScale"), [&](Params& p) { p.set(L"WorldContextObject", controller()); });
            return r ? r->get(L"ReturnValue").number(1) : 1;
        }
        // Show the mouse cursor (the game hides it in its menus; your controls take the mouse when it shows).
        inline auto show_cursor(bool on) -> bool { return wcmods::set(controller(), L"bShowMouseCursor", on); }

        // ============================================================================================ overlays
        namespace detail
        {
            struct Overlay
            {
                std::wstring name;
                int z{};
                Widget root;      // the user widget on the viewport
                Widget canvas;    // its root canvas, what the mod adds to
                UObject* owner{}; // the player controller it was made for
            };
            struct Overlays
            {
                std::mutex lock;
                std::map<std::wstring, Overlay> all;
                Widget scratch;   // a tree of the mod's own, the outer of new widgets
            };
            inline auto overlays() -> Overlays&
            {
                static Overlays o;
                return o;
            }
            // A user widget with a canvas as its root, for the player: an empty screen of the mod's own.
            inline auto make_user_widget(UObject* pc, int z, bool passive) -> std::pair<Widget, Widget>
            {
                Widget root;
                if (UClass* common = find_class(STR("/Script/CommonUI.CommonUserWidget"))) root = game_widget(common);
                if (!root)
                {
                    RC::Unreal::FStaticConstructObjectParameters params{find_class(STR("/Script/UMG.UserWidget"))};
                    params.Outer = pc;
                    root = Widget(RC::Unreal::UObjectGlobals::StaticConstructObject(params));
                }
                if (!root) return {};
                UObject* tree = get(root.object(), L"WidgetTree").object;
                if (!tree)
                {
                    RC::Unreal::FStaticConstructObjectParameters params{find_class(STR("/Script/UMG.WidgetTree"))};
                    params.Outer = root.object();
                    tree = RC::Unreal::UObjectGlobals::StaticConstructObject(params);
                    wcmods::set(root.object(), L"WidgetTree", tree);
                }
                RC::Unreal::FStaticConstructObjectParameters params{find_class(STR("/Script/UMG.CanvasPanel"))};
                params.Outer = tree;
                Widget canvas(RC::Unreal::UObjectGlobals::StaticConstructObject(params));
                wcmods::set(tree, L"RootWidget", canvas.object());
                root.set_visibility(passive ? Visibility::HitTestInvisible : Visibility::SelfHitTestInvisible);
                root.call(STR("AddToViewport"), [&](Params& p) { p.set_nth(0, Value::of(z)); });
                return {root, canvas};
            }
            inline auto outer() -> UObject*
            {
                Overlays& o = overlays();
                std::lock_guard lock(o.lock);
                UObject* pc = controller();
                if (!o.scratch || get(o.scratch.object(), L"WidgetTree").object == nullptr)
                {
                    RC::Unreal::FStaticConstructObjectParameters params{find_class(STR("/Script/UMG.UserWidget"))};
                    params.Outer = pc ? pc : wcmods::object(STR("/Script/UMG.Default__UserWidget"));
                    o.scratch = Widget(RC::Unreal::UObjectGlobals::StaticConstructObject(params));
                    if (o.scratch && !get(o.scratch.object(), L"WidgetTree").object)
                    {
                        RC::Unreal::FStaticConstructObjectParameters tp{find_class(STR("/Script/UMG.WidgetTree"))};
                        tp.Outer = o.scratch.object();
                        wcmods::set(o.scratch.object(), L"WidgetTree", RC::Unreal::UObjectGlobals::StaticConstructObject(tp));
                    }
                }
                UObject* tree = o.scratch ? get(o.scratch.object(), L"WidgetTree").object : nullptr;
                return tree ? tree : pc;
            }
        } // namespace detail

        struct OverlayOptions
        {
            int layer{1000};    // its z-order on the viewport: the game's screens sit low, the mod menu at 2000
            bool passive{true}; // lets the mouse through to the game (false: its controls take clicks)
        };
        // A canvas of the mod's own on the viewport, by name, made the first time and kept: add widgets to it
        // and place them with their slot (at(x, y), or anchors). It goes with the level (the game clears the
        // viewport), and comes back empty the next time it's asked for; nullptr-like (false) with no player yet.
        inline auto overlay(std::wstring_view name, OverlayOptions options = {}) -> Widget
        {
            detail::Overlays& o = detail::overlays();
            std::lock_guard lock(o.lock);
            UObject* pc = controller();
            if (!pc) return {};
            std::wstring key(name);
            auto it = o.all.find(key);
            if (it != o.all.end() && it->second.owner == pc && it->second.root && it->second.canvas) return it->second.canvas;
            auto [root, canvas] = detail::make_user_widget(pc, options.layer, options.passive);
            if (!root) return {};
            o.all[key] = {key, options.layer, root, canvas, pc};
            return canvas;
        }
        // Take an overlay off the screen.
        inline auto remove_overlay(std::wstring_view name) -> void
        {
            detail::Overlays& o = detail::overlays();
            std::lock_guard lock(o.lock);
            auto it = o.all.find(std::wstring(name));
            if (it == o.all.end()) return;
            if (it->second.root) it->second.root.remove();
            o.all.erase(it);
        }

        // ============================================================================================ the game's screens
        namespace detail
        {
            // The game's live widgets of a class, by the class's path: UE4SS's search by short name misses some
            // (the HUD's), so this goes by the class itself. A few times a second, not every frame.
            inline auto user_widgets_of(const TCHAR* class_path) -> std::vector<UObject*>
            {
                std::vector<UObject*> out;
                UClass* cls = find_class(class_path);
                if (!cls) return out;
                for (UObject* o : wcmods::find_all(STR("UserWidget")))
                    if (o && o->IsA(cls)) out.push_back(o);
                return out;
            }
        } // namespace detail

        // The game's screen of a class ("WBP_GuiScreenPause_C", "WBP_GuiPopupInventory_C"; a base class works
        // too, "GuiPopupCommonSettings" for the settings popup wherever it's opened from) that's on the viewport
        // now, or an empty Widget. wcmods::screens() (World.hpp) lists the ones showing.
        inline auto screen(std::wstring_view type) -> Widget
        {
            // On the viewport and drawn: a screen the game closed stays on the viewport a while, hidden.
            std::wstring name(type);
            for (UObject* w : wcmods::find_all(name.c_str()))
            {
                auto in = call_reflected(w, STR("IsInViewport"));
                auto shown = call_reflected(w, STR("IsVisible"));
                if (in && in->get(L"ReturnValue").boolean() && shown && shown->get(L"ReturnValue").boolean()) return Widget(w);
            }
            return {};
        }
        // The HUD while you play (the game's WBP_GuiHudGameWrc): its parts are its named widgets, through
        // find(): mcGuiMinimap, mcGuiEnergyBar, mcGuiHudCharacter, mcGuiQuestObjective, mcGuiContextualMenu,
        // mcGuiSenseControl, mcGuiAreaName...; its layers are CanvasExploration, CanvasCombat and CanvasOver,
        // to add to. Looked up again when the level changes.
        inline auto hud() -> Widget
        {
            static Widget kept;
            static UObject* kept_for{};
            UObject* pc = controller();
            if (kept && kept_for == pc)
            {
                auto still = call_reflected(kept.object(), STR("IsInViewport"));
                if (still && still->get(L"ReturnValue").boolean()) return kept;
            }
            kept = {};
            for (UObject* w : detail::user_widgets_of(STR("/Script/Wrc.GuiHudWrc")))
            {
                auto r = call_reflected(w, STR("IsInViewport"));
                if (r && r->get(L"ReturnValue").boolean())
                {
                    kept = Widget(w);
                    kept_for = pc;
                    break;
                }
            }
            return kept;
        }
        inline auto hud_part(std::wstring_view name) -> Widget { return hud().find(name); }

        // ---------------------------------------------------------------------------- watching screens
        namespace detail
        {
            struct ScreenWatch
            {
                std::wstring type;
                std::function<void(Widget, bool)> fn;
                UObject* seen{};   // the instance told about, or nullptr
            };
            struct Screens
            {
                std::mutex lock;
                std::vector<std::shared_ptr<ScreenWatch>> watches;
                bool started{};
            };
            inline auto screens_state() -> Screens&
            {
                static Screens s;
                return s;
            }
        } // namespace detail

        // `fn(screen, shown)` on the game thread when one of the game's screens of a class comes on the viewport
        // (shown true) and when it goes (shown false, the Widget then empty), looked for four times a second.
        inline auto on_screen(std::wstring_view type, std::function<void(Widget, bool)> fn) -> void
        {
            detail::Screens& s = detail::screens_state();
            bool start = false;
            {
                std::lock_guard lock(s.lock);
                s.watches.push_back(std::make_shared<detail::ScreenWatch>(detail::ScreenWatch{std::wstring(type), std::move(fn), nullptr}));
                if (!s.started) s.started = start = true;
            }
            if (!start) return;
            every(0.25, [] {
                std::vector<std::shared_ptr<detail::ScreenWatch>> watches;
                {
                    std::lock_guard lock(detail::screens_state().lock);
                    watches = detail::screens_state().watches;
                }
                std::map<std::wstring, Widget> found;   // one search a screen type, however many watch it
                for (auto& w : watches)
                {
                    if (!found.contains(w->type)) found[w->type] = screen(w->type);
                    Widget now = found[w->type];
                    UObject* o = now.object();
                    if (o == w->seen) continue;
                    if (w->seen) wcmods::detail::guarded(L"on_screen", [&] { w->fn(Widget(), false); });
                    w->seen = o;
                    if (o) wcmods::detail::guarded(L"on_screen", [&] { w->fn(now, true); });
                }
            });
        }

        // ============================================================================================ tabs in the game's screens
        // The game's screens keep their tabs (the pause screen's General, Controls, Quest...; the inventory's
        // Consumable, Materials, Accessories; the settings' Audio, Gameplay...) in a navigation list the player
        // moves along with the tab keys (1 and 2, a controller's shoulder buttons). A tab of the mod's own is one
        // more of the game's tab buttons, in the same row and the same list, with a page of the mod's own that
        // shows while the game's navigation is on it; the game's panel for the tab before it is hidden then.
        struct TabOptions
        {
            std::string id;                 // what tells it from another tab with the same title (the title without)
            Margin inset{200, 440, 200, 340}; // the page's room from the screen's edges, in the game's units
            bool hide_game_panels{true};     // hide the game's panels while the page shows
            bool scroll{true};               // the page scrolls when it's taller than its room
            bool focus{true};                // give the page the keyboard when it shows (its controls take arrows and Enter)
        };
        namespace detail
        {
            struct Tab
            {
                std::string id;
                std::wstring screen_type;
                std::wstring title;
                std::function<void(Widget)> build;
                TabOptions options;
                // What's live now, for the screen instance it was built in:
                UObject* in_screen{};
                Widget button;     // the game-style tab control
                Widget frame;      // the page's border on the screen
                Widget page;       // what the builder filled
                bool active{};
                std::vector<std::pair<Widget, Visibility>> hidden;   // the game's panels this page hid, and how they were
                int generation{};   // how many times it has been built (a new screen each time)
            };
            struct Tabs
            {
                std::mutex lock;
                std::vector<std::shared_ptr<Tab>> tabs;
                bool started{};
            };
            inline auto tabs_state() -> Tabs&
            {
                static Tabs t;
                return t;
            }

            // The screen's navigation list of tabs (NavControls.ControlsNavigation), and the game's tab controls in it.
            inline auto nav_list(UObject* screen) -> Value { return get(screen, L"NavControls.ControlsNavigation"); }
            inline auto nav_controls(UObject* screen) -> std::vector<Widget>
            {
                std::vector<Widget> out;
                for (Value& v : elements(nav_list(screen)))
                    if (v.object) out.emplace_back(v.object);
                return out;
            }
            inline auto nav_append(UObject* screen, UObject* control) -> bool
            {
                Value list = nav_list(screen);
                if (list.kind != Value::Kind::Array || !list.property || !list.at) return false;
                RC::Unreal::FScriptArrayHelper helper(static_cast<RC::Unreal::FArrayProperty*>(list.property), list.at);
                int index = helper.AddValue();
                *reinterpret_cast<UObject**>(helper.GetRawPtr(index)) = control;
                return true;
            }
            inline auto nav_remove(UObject* screen, UObject* control) -> void
            {
                Value list = nav_list(screen);
                if (list.kind != Value::Kind::Array || !list.property || !list.at) return;
                RC::Unreal::FScriptArrayHelper helper(static_cast<RC::Unreal::FArrayProperty*>(list.property), list.at);
                for (int i = helper.Num() - 1; i >= 0; --i)
                    if (*reinterpret_cast<UObject**>(helper.GetRawPtr(i)) == control) helper.RemoveValues(i, 1);
            }
            inline auto nav_current(UObject* screen) -> UObject* { return get(screen, L"CurrentNav.CurrentControl").object; }

            // The game's panels a screen switches between: the user widgets of its own that sit beside the tab row's
            // canvas, as GuiPanels or grids (not the footer, the title, the background).
            inline auto game_panels(UObject* screen, const Widget& tab_row) -> std::vector<Widget>
            {
                std::vector<Widget> out;
                Widget area = tab_row.parent();
                for (const Widget& w : area.children())
                {
                    if (w == tab_row) continue;
                    UObject* o = w.object();
                    if (!o || !wcmods::is_a(o, STR("/Script/UMG.UserWidget"))) continue;
                    std::wstring type = w.type();
                    if (type.find(L"Footer") != std::wstring::npos || type.find(L"Title") != std::wstring::npos) continue;
                    out.push_back(w);
                }
                // Panels in a canvas of their own (the pause screen's CanvasPanels, the inventory's CanvasGrids).
                for (const Widget& w : area.children())
                {
                    UObject* o = w.object();
                    if (!o || !wcmods::is_a(o, STR("/Script/UMG.CanvasPanel"))) continue;
                    for (const Widget& c : w.children())
                        if (wcmods::is_a(c.object(), STR("/Script/SwtEngine.GuiPanel")) || wcmods::is_a(c.object(), STR("/Script/SwtEngine.GuiScrollGrid"))) out.push_back(c);
                }
                return out;
            }

            // The tab row is laid out for the game's own tabs (700 wide each, overlapping by 60) across its 3840-wide
            // screen; with the mod's tabs it can be wider than that, so it's drawn smaller to fit, around its middle.
            inline auto fit_row(Widget row) -> void
            {
                double width = 0;
                for (const Widget& w : row.children())
                {
                    UObject* s = w.slot().object();
                    if (get(s, L"Size.SizeRule").number() == 1) continue;   // a spacer taking the room left
                    if (w.visibility() == Visibility::Collapsed) continue;
                    double own = wcmods::is_a(w.object(), STR("/Script/SwtEngine.GuiControl")) && !wcmods::is_a(w.object(), STR("/Script/SwtEngine.GuiButtonState")) ? 128 : 700;
                    width += own + get(s, L"Padding.Left").number() + get(s, L"Padding.Right").number();
                }
                double factor = width > 3760 ? 3760 / width : 1;
                row.set_pivot(0.5, 0.5);
                row.set_scale(factor, factor);
            }

            // Put the tab on the screen: a tab button like the screen's own after them, in the row and the list,
            // and the page's frame over the panels, hidden.
            inline auto build_tab(Tab& t, UObject* screen) -> bool
            {
                std::vector<Widget> tabs = nav_controls(screen);
                if (tabs.empty()) return false;
                Widget model = tabs.back();
                Widget row = model.parent();
                if (!row) return false;
                Widget button = game_widget(model.object()->GetClassPrivate());
                if (!button) return false;
                wcmods::set(button.object(), L"Text", Value::of(std::wstring_view(t.title)));
                wcmods::set(button.object(), L"ParentScreen", screen);
                // The row: the game's tabs, then a key hint and a spacer; the new tab goes after the last tab, so
                // what follows it is taken off and put back.
                std::vector<Widget> after;
                std::vector<Widget> kids = row.children();
                size_t last = 0;
                for (size_t i = 0; i < kids.size(); ++i)
                    if (kids[i] == model) last = i;
                struct Kept { Widget w; bool fill; float weight; Margin pad; int h, v; };
                std::vector<Kept> kept;
                for (size_t i = last + 1; i < kids.size(); ++i)
                {
                    UObject* s = kids[i].slot().object();
                    kept.push_back({kids[i], get(s, L"Size.SizeRule").number() == 1, static_cast<float>(get(s, L"Size.Value").number(1)),
                                    {static_cast<float>(get(s, L"Padding.Left").number()), static_cast<float>(get(s, L"Padding.Top").number()),
                                     static_cast<float>(get(s, L"Padding.Right").number()), static_cast<float>(get(s, L"Padding.Bottom").number())},
                                    static_cast<int>(get(s, L"HorizontalAlignment").number()), static_cast<int>(get(s, L"VerticalAlignment").number())});
                }
                for (Kept& k : kept) row.remove(k.w);
                Slot mine = row.add(button);
                {
                    Slot ms = model.slot();
                    mine.padding({static_cast<float>(get(ms.object(), L"Padding.Left").number()), static_cast<float>(get(ms.object(), L"Padding.Top").number()),
                                  static_cast<float>(get(ms.object(), L"Padding.Right").number()), static_cast<float>(get(ms.object(), L"Padding.Bottom").number())});
                    mine.align(static_cast<Align>(static_cast<int>(get(ms.object(), L"HorizontalAlignment").number())),
                               static_cast<Align>(static_cast<int>(get(ms.object(), L"VerticalAlignment").number())));
                }
                for (Kept& k : kept)
                {
                    Slot s = row.add(k.w);
                    s.padding(k.pad);
                    s.align(static_cast<Align>(k.h), static_cast<Align>(k.v));
                    if (k.fill) s.fill(k.weight);
                    else s.fit();
                }
                button.show_passive();
                button.set_text(t.title);
                nav_append(screen, button.object());
                fit_row(row);

                // The page: a frame over the panels' area, with a scrolling column inside.
                Widget area = row.parent();
                Widget frame = border(theme().panel, {40, 30, 40, 30});
                Slot fs = area.add(frame);
                fs.stretch(t.options.inset);
                fs.layer(50);
                Widget page = vbox();
                if (t.options.scroll)
                {
                    Widget sc = scroll();
                    sc.call(STR("SetScrollWhenFocusChanges"), [&](Params& p) { p.set_nth(0, Value::of(1)); });
                    sc.add(page);
                    frame.add(sc);
                }
                else
                {
                    frame.add(page);
                }
                frame.collapse();
                t.in_screen = screen;
                t.button = button;
                t.frame = frame;
                t.page = page;
                t.active = false;
                t.hidden.clear();
                t.generation++;
                if (t.build) wcmods::detail::guarded(L"a tab's page", [&] { t.build(page); });
                return true;
            }

            inline auto activate_tab(Tab& t, bool on) -> void
            {
                if (t.active == on) return;
                t.active = on;
                if (on)
                {
                    if (t.options.hide_game_panels)
                    {
                        for (Widget& p : game_panels(t.in_screen, t.button.parent()))
                        {
                            Visibility was = p.visibility();
                            if (was == Visibility::Collapsed) continue;
                            t.hidden.emplace_back(p, was);
                            p.collapse();
                        }
                    }
                    t.frame.show_passive();
                    if (t.options.focus)
                    {
                        // The first control in the page that takes the keyboard without eating the screen's keys (a
                        // text box would take Backspace and the tab keys as typing), else the page itself.
                        Widget first;
                        t.page.walk([&](const Widget& w) {
                            UObject* o = w.object();
                            if (wcmods::is_a(o, STR("/Script/UMG.Button")) || wcmods::is_a(o, STR("/Script/UMG.CheckBox")) || wcmods::is_a(o, STR("/Script/UMG.Slider"))
                                || wcmods::is_a(o, STR("/Script/UMG.ComboBoxString")))
                                first = w;
                            return !first;
                        });
                        (first ? first : t.page).focus();
                    }
                }
                else
                {
                    t.frame.collapse();
                    for (auto& [p, was] : t.hidden) p.set_visibility(was);
                    t.hidden.clear();
                }
            }

            inline auto tabs_tick(float dt) -> void
            {
                std::vector<std::shared_ptr<Tab>> tabs;
                {
                    std::lock_guard lock(tabs_state().lock);
                    tabs = tabs_state().tabs;
                }
                // A tab built in a screen watches that screen itself every frame (is it still there and shown? is
                // the navigation on the tab?); the search through the game's objects for screens coming up is
                // only every quarter second, for the tabs not built yet.
                static double since_search = 1;
                static std::map<std::wstring, UObject*> up;
                since_search += dt;
                bool search = since_search >= 0.25;
                if (search)
                {
                    since_search = 0;
                    up.clear();
                }
                for (auto& t : tabs)
                {
                    if (t->in_screen)
                    {
                        Widget s(t->in_screen);
                        bool shown = s && s.visible() && t->button;
                        if (!shown)
                        {
                            // The screen it was built in went (or its tab did): forget it, build again on the next.
                            if (t->active) activate_tab(*t, false);
                            t->in_screen = nullptr;
                            t->button = t->frame = t->page = {};
                            t->active = false;
                            t->hidden.clear();
                            continue;
                        }
                        activate_tab(*t, nav_current(t->in_screen) == t->button.object());
                        continue;
                    }
                    if (!search) continue;
                    if (!up.contains(t->screen_type)) up[t->screen_type] = screen(t->screen_type).object();
                    UObject* s = up[t->screen_type];
                    if (!s || !build_tab(*t, s)) continue;
                    activate_tab(*t, nav_current(s) == t->button.object());
                }
            }

            inline auto start_tabs() -> void
            {
                Tabs& ts = tabs_state();
                bool start = false;
                {
                    std::lock_guard lock(ts.lock);
                    if (!ts.started) ts.started = start = true;
                }
                if (start) every_frame([](float dt) { wcmods::detail::guarded(L"ui tabs", [&] { tabs_tick(dt); }); });
            }
        } // namespace detail

        // A tab of the mod's own in one of the game's screens, by the screen's class ("WBP_GuiScreenPause_C",
        // "WBP_GuiPopupInventory_C", "WBP_GuiPopupGameSettings_C", "WBP_GuiPopupSettings_C"...): a tab button like
        // the screen's own after them, which the tab keys reach, and `build(page)` filling its page (a column to
        // add rows to) each time the screen opens. Gives back the tab's id. The tab draws nothing until the
        // screen is up; the page is built again for each new screen instance (the game makes its screens anew).
        // Keep the title short (a word, as the game's are: the tab button's room is for about ten letters).
        inline auto tab(std::wstring_view screen_type, std::wstring_view title, std::function<void(Widget)> build, TabOptions options = {}) -> std::string
        {
            std::string id = options.id.empty() ? utf8(screen_type) + ":" + utf8(title) : options.id;
            auto t = std::make_shared<detail::Tab>();
            t->id = id;
            t->screen_type = screen_type;
            t->title = title;
            t->build = std::move(build);
            t->options = options;
            std::vector<std::shared_ptr<detail::Tab>> replaced;
            {
                detail::Tabs& ts = detail::tabs_state();
                std::lock_guard lock(ts.lock);
                std::erase_if(ts.tabs, [&](const std::shared_ptr<detail::Tab>& o) {
                    if (o->id != id) return false;
                    replaced.push_back(o);
                    return true;
                });
                ts.tabs.push_back(t);
            }
            // An earlier tab with this id that's on a screen comes off on the game thread (tab() may be called
            // from on_unreal_init or on_update, off it).
            for (auto& o : replaced)
                if (o->button || o->frame)
                    on_game_thread([o] {
                        if (o->active) detail::activate_tab(*o, false);
                        if (o->in_screen && o->button) detail::nav_remove(o->in_screen, o->button.object());
                        Widget row = o->button ? o->button.parent() : Widget();
                        if (o->button) o->button.remove();
                        if (o->frame) o->frame.remove();
                        if (row) detail::fit_row(row);
                    });
            detail::start_tabs();
            return id;
        }
        // The page of a tab (its column) while its screen is up, else empty; whether the game's navigation is
        // on the tab (its page shows); and taking a tab out (the screen's own are untouched).
        inline auto tab_page(std::string_view id) -> Widget
        {
            detail::Tabs& ts = detail::tabs_state();
            std::lock_guard lock(ts.lock);
            for (auto& t : ts.tabs)
                if (t->id == id) return t->page;
            return {};
        }
        inline auto tab_active(std::string_view id) -> bool
        {
            detail::Tabs& ts = detail::tabs_state();
            std::lock_guard lock(ts.lock);
            for (auto& t : ts.tabs)
                if (t->id == id) return t->active && t->page;
            return false;
        }
        inline auto remove_tab(std::string_view id) -> void
        {
            detail::Tabs& ts = detail::tabs_state();
            std::lock_guard lock(ts.lock);
            std::erase_if(ts.tabs, [&](const std::shared_ptr<detail::Tab>& t) {
                if (t->id != id) return false;
                if (t->active) detail::activate_tab(*t, false);
                if (t->in_screen && t->button) detail::nav_remove(t->in_screen, t->button.object());
                Widget row = t->button ? t->button.parent() : Widget();
                if (t->button) t->button.remove();
                if (t->frame) t->frame.remove();
                if (row) detail::fit_row(row);
                return true;
            });
        }
        // Every tab the mod has, by id.
        inline auto tabs() -> std::vector<std::string>
        {
            std::vector<std::string> out;
            detail::Tabs& ts = detail::tabs_state();
            std::lock_guard lock(ts.lock);
            for (auto& t : ts.tabs) out.push_back(t->id);
            return out;
        }
    } // namespace ui

    namespace detail
    {
        // As the mod is taken out: its tabs, overlays and watches go.
        inline auto stop_ui() -> void
        {
            {
                ui::detail::Tabs& ts = ui::detail::tabs_state();
                std::lock_guard lock(ts.lock);
                for (auto& t : ts.tabs)
                {
                    if (t->button) t->button.remove();
                    if (t->frame) t->frame.remove();
                }
                ts.tabs.clear();
            }
            {
                ui::detail::Overlays& o = ui::detail::overlays();
                std::lock_guard lock(o.lock);
                for (auto& [name, ov] : o.all)
                    if (ov.root) ov.root.remove();
                o.all.clear();
            }
            {
                UiState& s = ui_state();
                std::lock_guard lock(s.lock);
                s.watches.clear();
            }
        }
    } // namespace detail
} // namespace wcmods
