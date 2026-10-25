// Menu.hpp: a page in the mod menu with every kind of row, the settings page, keys on the Overview, and
// values shared with Lua. The Python side reads and uses the pages through the menu, and asks Lua.
#include "checks.hpp"

#include <atomic>
#include <string>

namespace t
{
    namespace
    {
        std::atomic<int> f10{}, shift_f10{}, pokes{};
        struct Rows
        {
            bool on{true}, ticked{false}, inner{false};
            double speed{1.0}, count{3};
            std::wstring name{L"cat"}, tint{L"#ffcc00"}, mode{L"Calm"}, pick{L"Two"};
            int draws{};
        } rows;

        auto draw(Ui& ui) -> void
        {
            rows.draws++;
            ui.heading(L"C++ SDK page");
            ui.text(L"Rows drawn from C++.");
            ui.note(L"A note.");
            ui.separator();
            ui.space(4);
            ui.field(L"Draws", std::to_wstring(rows.draws));
            rows.on = ui.on_off(L"Switch", rows.on);
            rows.ticked = ui.toggle(L"Tick", rows.ticked);
            rows.speed = ui.slider(L"Speed", rows.speed, 0.5, 3.0, {.step = 0.1, .format = L"x%.1f"});
            rows.count = ui.number(L"Count", rows.count, {.min = 0, .max = 10, .step = 1, .whole = true});
            rows.name = ui.input(L"Name", rows.name, L"a name");
            rows.tint = ui.color(L"Tint", rows.tint);
            rows.mode = ui.radio(L"Mode", rows.mode, {L"Calm", L"Busy"});
            rows.pick = ui.choice(L"Pick", rows.pick, {L"One", L"Two", L"Three"});
            ui.progress(L"Progress", rows.speed / 3.0);
            ui.section(L"More", [](Ui& inner) {
                inner.note(L"Inside the section.");
                rows.inner = inner.toggle(L"Inner", rows.inner);
            });
            if (ui.button(L"Poke", L"primary")) pokes++;
        }
    } // namespace

    auto setup_menu() -> void
    {
        expect("menu_page", menu_page(L"C++ SDK page", draw, {.order = 45, .group = "mods", .id = "cpp-sdk-page"}) == "cpp-sdk-page");
        expect("menu_page.default_id", menu_page(L"Second page", [](Ui& ui) { ui.note(L"Nothing here."); }) == "Second page");
        settings_page(true);
        share("hello", 42);
        share("name", "cpp");
        share("flag", true);
        expect("key_name", key_name(Key::F10) == L"F10" && key_name(Key::LEFT_ARROW) == L"Left Arrow" && key_name(Key::ONE) == L"1"
                               && key_name(Key::NUM_ONE) == L"Num 1");
        expect("on_key.help", on_key(Key::F10, L"Poke the test page", [] { f10++; }));
        expect("on_key.help.modifiers", on_key(Key::F10, {Modifier::SHIFT}, L"Shift poke", [] { shift_f10++; }));
        expect("menu_open.closed_at_start", !menu_open() && menu_page_shown().empty());
        expect("shared.missing", shared("nope").is_null());
    }

    auto snapshot_menu() -> void
    {
        value("menu.open", menu_open());
        value("menu.page", text(menu_page_shown()));
        value("shared.ping", shared("ping"));
        value("ui.draws", rows.draws);
        value("ui.on_off", rows.on);
        value("ui.toggle", rows.ticked);
        value("ui.inner", rows.inner);
        value("ui.slider", rows.speed);
        value("ui.number", rows.count);
        value("ui.input", text(rows.name));
        value("ui.color", text(rows.tint));
        value("ui.radio", text(rows.mode));
        value("ui.choice", text(rows.pick));
        value("ui.pokes", pokes.load());
        value("key.f10", f10.load());
        value("key.shift_f10", shift_f10.load());
    }
} // namespace t
