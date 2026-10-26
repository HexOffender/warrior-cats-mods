// Ui.hpp: every kind of widget made, placed, styled and read back; a tab of the mod's own in the pause screen;
// an overlay on the viewport; the HUD and its parts; what the player does, as events. The Python side opens the
// pause screen, walks to the tab with the game's own keys, looks at the page, and uses its controls through Lua.
#include "checks.hpp"

#include <atomic>
#include <format>
#include <string>

namespace t
{
    namespace
    {
        std::atomic<int> clicks{}, toggles{}, changes{}, texts{}, screen_events{}, builds{};
        bool screen_shown{};
        std::string tab_id, gone_id;
        // The page's controls, named for the Python side (results.json carries their paths) to drive through Lua.
        struct Page
        {
            Widget page, button, check, slider, number, input, choice, progress;
            bool last_toggle{};
            double last_change{};
            std::wstring last_text;
        } pg;

        auto path_of(const Widget& w) -> Json
        {
            UObject* o = w.object();
            if (!o) return Json();
            std::wstring full = full_name(o);   // "Class /Path.To:Object" -> the path
            auto space = full.find(L' ');
            return Json(text(space == std::wstring::npos ? full : full.substr(space + 1)));
        }

        // The tab's page: a row of each kind of control, as a mod's settings page would be.
        auto build_page(Widget page) -> void
        {
            builds++;
            pg.page = page;
            page.add(ui::heading(L"SDK test page"));
            page.add(ui::note(L"Rows made from C++ with Ui.hpp, in the game's own pause screen."));
            pg.button = ui::button(L"Poke");
            pg.button.on_click([] { clicks++; });
            pg.check = ui::checkbox(true);
            pg.check.on_toggle([](bool on) {
                toggles++;
                pg.last_toggle = on;
            });
            pg.slider = ui::slider(0.5, 0, 1, 0.05);
            pg.slider.on_change([](double v) {
                changes++;
                pg.last_change = v;
            });
            pg.number = ui::number(3, 0, 10, 1);
            pg.input = ui::input(L"cat", L"a name");
            pg.input.on_text([](std::wstring s) {
                texts++;
                pg.last_text = s;
            });
            pg.choice = ui::choice({L"One", L"Two", L"Three"}, L"Two");
            pg.progress = ui::progress(0.5);
            page.add(ui::labelled(L"Poke it", pg.button));
            page.add(ui::labelled(L"Switch", pg.check));
            page.add(ui::labelled(L"Slider", pg.slider));
            page.add(ui::labelled(L"Number", pg.number));
            page.add(ui::labelled(L"Name", pg.input));
            page.add(ui::labelled(L"Pick", pg.choice));
            page.add(ui::labelled(L"Progress", pg.progress));
            page.add(ui::row({ui::text(L"Left"), ui::text(L"Right")}));
            page.add(ui::spacer(10, 30));
            page.add(ui::rect(UiColor::hex(L"#f0c846"), 400, 6));
        }
    } // namespace

    // At init, off the game thread: registering is all that happens here.
    auto setup_ui() -> void
    {
        expect("ui.theme", ui::theme().text_size > 0 && ui::theme().heading_size > ui::theme().text_size);
        tab_id = ui::tab(L"WBP_GuiScreenPause_C", L"SDK", build_page, {.id = "sdk-ui-tab"});
        expect("ui.tab.id", tab_id == "sdk-ui-tab");
        gone_id = ui::tab(L"WBP_GuiScreenPause_C", L"Gone", [](Widget) {});
        expect("ui.tab.default_id", gone_id == "WBP_GuiScreenPause_C:Gone");
        auto ids = ui::tabs();
        expect("ui.tabs", ids.size() == 2 && ids[0] == tab_id && ids[1] == gone_id);
        ui::remove_tab(gone_id);
        expect("ui.remove_tab", ui::tabs().size() == 1);
        expect("ui.tab_page.before", !ui::tab_page(tab_id) && !ui::tab_active(tab_id));
        ui::on_screen(L"WBP_GuiScreenPause_C", [](Widget s, bool shown) {
            screen_events++;
            screen_shown = shown && s;
        });
        expect("ui.color.hex", UiColor::hex(L"#ff8000").to_hex() == L"#ff8000" && UiColor::hex(L"#ff800080").to_hex() == L"#ff800080"
                                   && UiColor::hex(L"nope").to_hex() == L"#ffffff");
    }

    // On the game thread, in the forest, when the Python side asks: widgets of every kind, off screen and on it.
    auto run_ui() -> void
    {
        // ----- every kind of widget by class
        int made = 0;
        for (const wchar_t* kind : {L"TextBlock", L"Button", L"CheckBox", L"Slider", L"SpinBox", L"ComboBoxString", L"EditableTextBox",
                                    L"MultiLineEditableTextBox", L"EditableText", L"ProgressBar", L"Image", L"Border", L"SizeBox", L"Spacer",
                                    L"HorizontalBox", L"VerticalBox", L"ScrollBox", L"CanvasPanel", L"Overlay", L"GridPanel", L"UniformGridPanel",
                                    L"WrapBox", L"WidgetSwitcher", L"ScaleBox", L"ExpandableArea", L"BackgroundBlur", L"Throbber",
                                    L"CircularThrobber", L"RichTextBlock", L"InputKeySelector", L"NamedSlot", L"SafeZone", L"InvalidationBox",
                                    L"RetainerBox", L"ListView", L"TileView", L"TreeView", L"MenuAnchor", L"StackBox", L"ScrollBar"})
        {
            Widget w = ui::widget(kind);
            if (w && w.type() == kind) made++;
            else log(L"ui::widget({}) gave {}", kind, w ? w.type() : L"nothing");
        }
        expect("ui.widget.kinds", made >= 36, std::to_string(made));
        value("ui.widget.kinds", made);
        expect("ui.widget.by_path", ui::widget(L"/Script/UMG.TextBlock").type() == L"TextBlock");
        expect("ui.widget.missing", !ui::widget(L"NoSuchWidget"));

        // ----- text
        Widget tx = ui::text(L"Hello", {.size = 40, .color = UiColor::hex(L"#ff0000"), .wrap = true, .justify = Align::Center});
        expect("ui.text", tx && tx.type() == L"TextBlock" && tx.text() == L"Hello");
        expect("ui.text.size", tx.get(L"Font.Size").number() == 40, std::to_string(tx.get(L"Font.Size").number()));
        expect("ui.text.wrap", tx.get(L"AutoWrapText").number() == 1 || tx.get(L"AutoWrapText").boolean());
        expect("ui.text.justify", tx.get(L"Justification").number() == 1);
        tx.set_text(L"Changed");
        expect("set_text", tx.text() == L"Changed");
        tx.set_font(30, L"Regular");
        expect("set_font", tx.get(L"Font.Size").number() == 30 && tx.get(L"Font.TypefaceFontName").string() == L"Regular");
        value("ui.text.font", text(name(tx.get(L"Font.FontObject").object)));
        tx.set_color(UiColor::hex(L"#00ff00"));
        expect("set_color", tx.get(L"ColorAndOpacity.SpecifiedColor.G").number() > 0.99 && tx.get(L"ColorAndOpacity.SpecifiedColor.R").number() < 0.01);
        tx.set_shadow(2);
        expect("set_shadow", tx.get(L"ShadowOffset.X").number() == 2);
        tx.set_wrap(false);
        tx.set_justify(Align::End);
        expect("set_justify", tx.get(L"Justification").number() == 2);
        expect("ui.heading", ui::heading(L"H").get(L"Font.Size").number() == ui::theme().heading_size);
        expect("ui.note", ui::note(L"n").type() == L"TextBlock");
        tx.set_tooltip(L"tip");
        expect("set_tooltip", tx.get(L"ToolTipText").string() == L"tip");

        // ----- controls
        Widget b = ui::button(L"Press");
        expect("ui.button", b.type() == L"Button" && b.text() == L"Press");
        b.set_text(L"Pressed?");
        expect("ui.button.set_text", b.text() == L"Pressed?");
        expect("clicked.false", !b.clicked());
        Widget c = ui::checkbox(true);
        expect("ui.checkbox", c.type() == L"CheckBox" && c.checked() && c.value() == 1);
        c.set_checked(false);
        expect("set_checked", !c.checked());
        Widget s = ui::slider(0.5, 0, 2, 0.1);
        expect("ui.slider", s.type() == L"Slider" && std::abs(s.value() - 0.5) < 1e-6 && s.get(L"MaxValue").number() == 2);
        s.set_value(1.5);
        expect("set_value", std::abs(s.value() - 1.5) < 1e-6);
        s.set_range(0, 10, 0.5);
        expect("set_range", s.get(L"MaxValue").number() == 10 && std::abs(s.get(L"StepSize").number() - 0.5) < 1e-6);
        expect("changed.primes", !s.changed());
        s.set_value(3);
        expect("changed.true", s.changed() && !s.changed());
        Widget n = ui::number(3, 0, 10, 1);
        expect("ui.number", n.type() == L"SpinBox" && n.value() == 3 && n.get(L"MaxValue").number() == 10);
        Widget in = ui::input(L"abc", L"hint");
        expect("ui.input", in.type() == L"EditableTextBox" && in.text() == L"abc" && in.get(L"HintText").string() == L"hint");
        in.set_hint(L"other");
        expect("set_hint", in.get(L"HintText").string() == L"other");
        Widget ch = ui::choice({L"One", L"Two"}, L"Two");
        expect("ui.choice", ch.type() == L"ComboBoxString" && ch.option() == L"Two" && ch.options().size() == 2 && ch.value() == 1);
        ch.set_option(L"One");
        expect("set_option", ch.option() == L"One" && ch.value() == 0);
        ch.add_option(L"Three");
        expect("add_option", ch.options().size() == 3 && ch.options()[2] == L"Three");
        ch.set_options({L"A", L"B"});
        ch.set_value(1);
        expect("set_options", ch.options().size() == 2 && ch.option() == L"B");
        Widget p = ui::progress(0.25);
        expect("ui.progress", p.type() == L"ProgressBar" && std::abs(p.value() - 0.25) < 1e-6);
        p.set_tint(UiColor::hex(L"#0000ff"));
        expect("set_tint", p.get(L"FillColorAndOpacity.B").number() > 0.99);
        Widget img = ui::image(STR("/Engine/EngineResources/DefaultTexture"), 64, 48);
        expect("ui.image", img.type() == L"Image");
        Widget r = ui::rect(UiColor::hex(L"#ff0000"), 10, 20);
        expect("ui.rect", r.type() == L"Image" && r.get(L"ColorAndOpacity.R").number() > 0.99);
        r.set_image(STR("/Engine/EngineResources/DefaultTexture"));

        // ----- layouts and the tree
        expect("ui.layouts", ui::hbox().type() == L"HorizontalBox" && ui::vbox().type() == L"VerticalBox" && ui::scroll().type() == L"ScrollBox"
                                 && ui::canvas().type() == L"CanvasPanel" && ui::overlay_box().type() == L"Overlay" && ui::grid().type() == L"GridPanel"
                                 && ui::uniform_grid().type() == L"UniformGridPanel" && ui::wrap().type() == L"WrapBox" && ui::switcher().type() == L"WidgetSwitcher");
        Widget sc = ui::scale(2);
        expect("ui.scale", sc.type() == L"ScaleBox" && sc.get(L"UserSpecifiedScale").number() == 2);
        Widget v = ui::vbox();
        Slot s1 = v.add(tx);
        expect("add", s1 && s1.type() == L"VerticalBoxSlot" && s1.object() != nullptr);
        s1.padding(Margin(4)).fill(2).align(Align::Fill, Align::Center);
        expect("slot.padding", get(s1.object(), L"Padding.Left").number() == 4 && get(s1.object(), L"Padding.Bottom").number() == 4);
        expect("slot.fill", get(s1.object(), L"Size.SizeRule").number() == 1 && get(s1.object(), L"Size.Value").number() == 2);
        expect("slot.align", get(s1.object(), L"VerticalAlignment").number() == 2);
        s1.fit();
        expect("slot.fit", get(s1.object(), L"Size.SizeRule").number() == 0);
        v.add({b, c});
        expect("children", v.count() == 3 && v.children().size() == 3 && v.child(0) == tx && v.child(2) == c && !v.child(3));
        expect("parent", tx.parent() == v && tx.slot().object() == s1.object());
        expect("find", v.find(tx.name()) == tx && !v.find(L"nope"));
        expect("find_all", v.find_all(L"Button").size() == 1 && v.find_all().size() == 5);   // the box, 3 children, the button's text
        int walked = 0;
        v.walk([&](const Widget&) {
            walked++;
            return walked < 2;
        });
        expect("walk", walked == 2);
        expect("remove", v.remove(c) && v.count() == 2 && !v.remove(c));
        b.remove();
        expect("remove.self", v.count() == 1);
        v.clear();
        expect("clear", v.count() == 0);
        Widget cv = ui::canvas();
        Slot cs = cv.add(b);
        expect("add.canvas", cs.type() == L"CanvasPanelSlot");
        cs.anchors(0, 0, 1, 1).offsets(Margin(1, 2, 3, 4)).layer(3).auto_size(false);
        expect("slot.anchors", get(cs.object(), L"LayoutData.Anchors.Maximum.X").number() == 1 && get(cs.object(), L"LayoutData.Offsets.Left").number() == 1
                                   && get(cs.object(), L"LayoutData.Offsets.Bottom").number() == 4 && get(cs.object(), L"ZOrder").number() == 3);
        cs.position(10, 20).size(100, 50).alignment(0.5, 0.5);
        expect("slot.position", get(cs.object(), L"LayoutData.Offsets.Left").number() == 10 && get(cs.object(), L"LayoutData.Offsets.Right").number() == 100
                                    && get(cs.object(), L"LayoutData.Alignment.X").number() == 0.5);
        b.at(5, 6);
        expect("at", get(cs.object(), L"LayoutData.Offsets.Left").number() == 5 && get(cs.object(), L"bAutoSize").boolean());
        cs.stretch(Margin(10));
        expect("slot.stretch", get(cs.object(), L"LayoutData.Anchors.Maximum.Y").number() == 1 && get(cs.object(), L"LayoutData.Offsets.Right").number() == 10);
        // A box slot's share and a canvas slot's size are different SetSizes: each leaves the other kind alone.
        cs.fill(2).fit();
        expect("slot.fill.canvas", get(cs.object(), L"LayoutData.Offsets.Right").number() == 10);
        Widget vb2 = ui::vbox();
        Slot bs2 = vb2.add(ui::text(L"x"));
        bs2.fill(1).size(50, 50);
        expect("slot.size.box", get(bs2.object(), L"Size.SizeRule").number() == 1 && get(bs2.object(), L"Size.Value").number() == 1);
        Widget g = ui::grid();
        Slot gs = g.add(ui::text(L"cell"));
        gs.cell(1, 2);
        expect("slot.cell", get(gs.object(), L"Row").number() == 1 && get(gs.object(), L"Column").number() == 2);
        Widget bd = ui::border(UiColor::hex(L"#102030"), Margin(5, 6));
        expect("ui.border", bd.type() == L"Border" && bd.get(L"Padding.Left").number() == 5 && bd.get(L"Padding.Top").number() == 6);
        bd.set_padding(Margin(7));
        expect("set_padding", bd.get(L"Padding.Right").number() == 7);
        bd.add(tx);
        expect("add.content", tx.parent() == bd && bd.count() == 1);
        Widget bx = ui::box(100, 50);
        expect("ui.box", bx.type() == L"SizeBox" && bx.get(L"WidthOverride").number() == 100 && bx.get(L"HeightOverride").number() == 50);
        bx.set_size(0, 60);
        expect("set_size", bx.get(L"HeightOverride").number() == 60 && !bx.get(L"bOverride_WidthOverride").boolean());
        Widget sp = ui::spacer(10, 20);
        expect("ui.spacer", sp.type() == L"Spacer" && sp.get(L"Size.Y").number() == 20);
        Widget sw = ui::switcher();
        sw.add({ui::text(L"a"), ui::text(L"b")});
        sw.set_active(1);
        expect("set_active", sw.get(L"ActiveWidgetIndex").number() == 1);
        Widget rw = ui::row({ui::text(L"a"), ui::text(L"b")}, 10);
        expect("ui.row", rw.type() == L"HorizontalBox" && rw.count() == 2 && get(rw.child(1).slot().object(), L"Padding.Left").number() == 10);
        float grow = ui::theme().control_scale;
        auto close_to = [](double a, double b) { return std::abs(a - b) < 1e-3; };   // floats the widgets store, doubles computed here
        Widget lb = ui::labelled(L"Label", ui::slider(0), 300);
        expect("ui.labelled", lb.count() == 2 && lb.child(0).text() == L"Label" && lb.child(1).type() == L"ScaleBox"
                                  && lb.child(1).child(0).type() == L"SizeBox" && lb.child(1).child(0).child(0).type() == L"Slider"
                                  && lb.child(1).get(L"UserSpecifiedScale").number() == grow);
        // A check box is grown by a render transform instead (a scale box didn't grow one in the game), in a box
        // that reserves the room it's drawn in: its 24-pixel pictures and its style's padding, times the scale.
        Widget lc = ui::labelled(L"Check", ui::checkbox(), 300);
        Widget room = lc.child(1);
        Widget cb = room.child(0);
        double pad_x = cb.get(L"WidgetStyle.Padding.Left").number() + cb.get(L"WidgetStyle.Padding.Right").number();
        double pad_y = cb.get(L"WidgetStyle.Padding.Top").number() + cb.get(L"WidgetStyle.Padding.Bottom").number();
        expect("ui.labelled.checkbox", room.type() == L"SizeBox" && cb.type() == L"CheckBox" && close_to(cb.get(L"RenderTransform.Scale.X").number(), grow)
                                           && close_to(cb.get(L"RenderTransform.Scale.Y").number(), grow) && cb.get(L"RenderTransformPivot.X").number() == 0
                                           && close_to(room.get(L"WidthOverride").number(), 300) && close_to(room.get(L"HeightOverride").number(), (24 + pad_y) * grow),
               text(std::format(L"{} holding {}, scale {}, room {}x{}, padding {}x{}", room.type(), cb.type(), cb.get(L"RenderTransform.Scale.X").number(),
                                room.get(L"WidthOverride").number(), room.get(L"HeightOverride").number(), pad_x, pad_y)));
        // A bare scaled check box's room, as computed from its style, and as known for checkbox() at the default
        // theme (24-pixel pictures, the engine's 2-pixel padding on the left, three times): 78 x 72.
        Widget bare = ui::scaled(ui::checkbox());
        double bare_w = bare.get(L"WidthOverride").number(), bare_h = bare.get(L"HeightOverride").number();
        expect("ui.scaled", close_to(ui::scaled(ui::slider(0)).get(L"UserSpecifiedScale").number(), grow)
                                && ui::scaled(ui::button(L"b")).get(L"UserSpecifiedScale").number() == 1
                                && close_to(bare_h, (24 + pad_y) * grow) && close_to(bare_w, (24 + pad_x) * grow)
                                && (grow != 3.0f || (close_to(bare_w, 78) && close_to(bare_h, 72))),
               text(std::format(L"bare check box room {}x{} at scale {}", bare_w, bare_h, grow)));
        // The text in a scaled number box, text box or drop-down is set to come out at the theme's text_size.
        double field = ui::theme().text_size / grow;
        expect("ui.labelled.field_font", close_to(ui::labelled(L"N", ui::number(1)).child(1).child(0).child(0).get(L"Font.Size").number(), field)
                                             && close_to(ui::labelled(L"T", ui::input(L"x")).child(1).child(0).child(0).get(L"WidgetStyle.TextStyle.Font.Size").number(), field)
                                             && close_to(ui::labelled(L"C", ui::choice({L"a"})).child(1).child(0).child(0).get(L"Font.Size").number(), field));
        Widget nb = ui::number(1);
        nb.set_font(20);
        expect("set_font.spinbox", nb.get(L"Font.Size").number() == 20);
        Widget tb = ui::input(L"a");
        tb.set_font(20);
        expect("set_font.textbox", tb.get(L"WidgetStyle.TextStyle.Font.Size").number() == 20);

        // ----- state
        tx.hide();
        expect("hide", tx.visibility() == Visibility::Hidden);
        tx.collapse();
        expect("collapse", tx.visibility() == Visibility::Collapsed);
        tx.show();
        expect("show", tx.visibility() == Visibility::Visible);
        tx.show_passive();
        expect("show_passive", tx.visibility() == Visibility::SelfHitTestInvisible);
        tx.set_visibility(Visibility::HitTestInvisible);
        expect("set_visibility", tx.visibility() == Visibility::HitTestInvisible && !tx.visible());   // not on screen
        tx.set_enabled(false);
        expect("set_enabled", !tx.enabled());
        tx.set_enabled(true);
        expect("enabled", tx.enabled());
        tx.set_opacity(0.5f);
        expect("set_opacity", std::abs(tx.opacity() - 0.5) < 1e-6);
        tx.set_scale(2, 3).set_angle(45).set_translation(7, 8).set_pivot(0.25, 0.75);
        expect("set_scale", tx.get(L"RenderTransform.Scale.Y").number() == 3 && tx.get(L"RenderTransform.Angle").number() == 45
                                && tx.get(L"RenderTransform.Translation.X").number() == 7 && tx.get(L"RenderTransformPivot.Y").number() == 0.75);
        tx.focus();
        expect("focused", !tx.focused() && !tx.hovered());   // not on screen
        expect("is_a", tx.is_a(STR("/Script/UMG.Widget")) && !tx.is_a(STR("/Script/UMG.Button")) && !tx.name().empty() && tx.object() && tx.valid());
        expect("get.set.call", tx.set(L"RenderOpacity", 0.7) && std::abs(tx.get(L"RenderOpacity").number() - 0.7) < 1e-6
                                   && tx.call(STR("GetRenderOpacity")) && std::abs(tx.call(STR("GetRenderOpacity"))->get(L"ReturnValue").number() - 0.7) < 1e-6);
        expect("play.missing", !tx.play(L"NoAnim"));
        expect("widget.empty", !Widget() && Widget().text().empty() && !Widget().add(tx) && Widget().children().empty());

        // ----- the viewport, the cursor
        Vec2 vs = ui::viewport_size();
        expect("viewport_size", vs.x > 100 && vs.y > 100, std::format("{}x{}", vs.x, vs.y));
        value("ui.viewport.w", vs.x);
        value("ui.viewport.h", vs.y);
        expect("viewport_scale", ui::viewport_scale() > 0);
        expect("show_cursor", ui::show_cursor(false));

        // ----- an overlay on the viewport, with a label the Python side looks for
        Widget ov = ui::overlay(L"sdk-test", {.layer = 1500});
        expect("overlay", ov && ov.type() == L"CanvasPanel");
        expect("overlay.same", ui::overlay(L"sdk-test") == ov);
        Widget label = ui::text(L"SDK overlay", {.size = 48});
        ov.add(label).at(120, 120);
        expect("overlay.add", label.parent() == ov);
        value("ui.overlay.label", path_of(label));
        Widget other = ui::overlay(L"sdk-gone");
        expect("overlay.other", other && !(other == ov));
        ui::remove_overlay(L"sdk-gone");
        Widget again = ui::overlay(L"sdk-gone");
        expect("remove_overlay", again && !(again == other));   // taken off, so asked for again it's a new one
        ui::remove_overlay(L"sdk-gone");

        // ----- the HUD
        Widget hud = ui::hud();
        expect("hud", hud && hud.is_a(STR("/Script/Wrc.GuiHudWrc")), text(hud.type()));
        value("ui.hud.class", text(hud.type()));
        Widget mini = ui::hud_part(L"mcGuiMinimap");
        expect("hud_part", mini && mini.type() == L"WBP_GuiHudControlMinimap_C", text(mini.type()));
        value("ui.hud.minimap", path_of(mini));
        Widget over = hud.find(L"CanvasOver");
        expect("hud.find", over && over.type() == L"CanvasPanel");
        Widget hud_label = ui::text(L"SDK HUD", {.size = 44, .color = UiColor::hex(L"#f0c846")});
        over.add(hud_label).at(240, 240);
        expect("hud.add", hud_label.parent() == over);
        value("ui.hud.label", path_of(hud_label));

        // ----- the game's screens: none of the pause screen now
        expect("screen.none", !ui::screen(L"WBP_GuiScreenPause_C"));
        value("ui.screen_events", screen_events.load());
        expect("game_widget.missing", !ui::game_widget(STR("/Game/Nope/WBP_Nope.WBP_Nope_C")));
    }

    // What the tab and its page hold now, and the events so far.
    auto snapshot_ui() -> void
    {
        value("ui.tab.active", ui::tab_active(tab_id));
        value("ui.tab.page", ui::tab_page(tab_id) ? Json(true) : Json(false));
        value("ui.tab.builds", builds.load());
        value("ui.tab.rows", ui::tab_page(tab_id) ? ui::tab_page(tab_id).count() : -1);
        value("ui.page.button", path_of(pg.button));
        value("ui.page.check", path_of(pg.check));
        value("ui.page.slider", path_of(pg.slider));
        value("ui.page.input", path_of(pg.input));
        value("ui.page.choice", path_of(pg.choice));
        value("ui.page.panel", path_of(pg.page));
        value("ui.clicks", clicks.load());
        value("ui.toggles", toggles.load());
        value("ui.last_toggle", pg.last_toggle);
        value("ui.changes", changes.load());
        value("ui.last_change", pg.last_change);
        value("ui.texts", texts.load());
        value("ui.last_text", text(pg.last_text));
        value("ui.screen_events", screen_events.load());
        value("ui.screen_shown", screen_shown);
        Widget screen = ui::screen(L"WBP_GuiScreenPause_C");
        value("ui.screen", screen ? path_of(screen) : Json());
        value("ui.screen.current", screen ? Json(text(name(get(screen.object(), L"CurrentNav.CurrentControl").object))) : Json());
    }

    // Take the overlay and the HUD label off again.
    auto teardown_ui() -> void
    {
        ui::remove_overlay(L"sdk-test");
        Widget hud = ui::hud();
        for (Widget& w : hud.find(L"CanvasOver").find_all(L"TextBlock"))
            if (w.text() == L"SDK HUD") w.remove();
        expect("teardown.hud", hud.find(L"CanvasOver").find_all(L"TextBlock").empty() || hud.find(L"CanvasOver").find_all(L"TextBlock")[0].text() != L"SDK HUD");
    }
} // namespace t
