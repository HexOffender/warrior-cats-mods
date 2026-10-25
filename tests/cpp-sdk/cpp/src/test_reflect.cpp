// Reflect.hpp: properties by path as the kind they are, arrays, maps, structs, describe, spawn; and
// Events.hpp's other threads and settings that change on disk.
#include "checks.hpp"

#include <atomic>
#include <chrono>
#include <numeric>
#include <thread>
#include <vector>

namespace t
{
    namespace
    {
        std::atomic<int> reloads{};
    }

    auto run_reflect(UObject* actor) -> void
    {
        Value state = get(actor, L"Controller.PlayerState");
        expect("get.object", state.kind == Value::Kind::Object && state.object != nullptr && state.type == L"ObjectProperty", text(state.type));
        value("reflect.player_state", text(name(state.object)));
        Value dilation = get(actor, L"CustomTimeDilation");
        expect("get.float", dilation.kind == Value::Kind::Float && dilation.number() == 1.0 && dilation.type == L"FloatProperty", text(dilation.shown()));
        Value hidden = get(actor, L"bHidden");
        expect("get.bool", hidden.kind == Value::Kind::Bool && !hidden.boolean(true) && hidden.type == L"BoolProperty");
        Value none = get(actor, L"NoSuchProperty");
        expect("get.missing", !none && none.kind == Value::Kind::None && !get(nullptr, L"Tags") && !get(actor, L"Controller.Nope.Deeper")
                                  && !get(actor, L"Tags[99]") && !get(actor, L"CustomTimeDilation[0]"));
        Value tags = get(actor, L"Tags");
        expect("get.array", tags.kind == Value::Kind::Array && tags.shown().starts_with(L"["));
        value("reflect.tags", static_cast<double>(elements(tags).size()));
        expect("elements.by_path", elements(actor, L"Tags").size() == elements(tags).size());
        Value clan = get(actor, L"MeshCustomizationComponent.CustomData.ClanType");
        expect("get.enum", clan.kind == Value::Kind::Enum && !clan.text.empty() && clan.number() >= 0, text(clan.text));
        value("reflect.clan", static_cast<double>(clan.i));
        value("reflect.clan.name", text(clan.text));
        Value custom = get(actor, L"MeshCustomizationComponent.CustomData");
        expect("get.struct", custom.kind == Value::Kind::Struct && !custom.type.empty(), text(custom.type));
        expect("get.from_struct", get(custom, L"ClanType").i == clan.i && get(custom, L"ClanType").text == clan.text && !get(custom, L"Nope"));
        Value x = get(actor, L"RootComponent.RelativeLocation.X");
        expect("get.struct_member", x.kind == Value::Kind::Float, text(x.shown()));
        value("reflect.x", x.number());
        auto rewards = map_entries(actor, L"rewards");
        value("reflect.rewards", static_cast<double>(rewards.size()));
        bool pairs_ok = true;
        for (auto& [k, v] : rewards) pairs_ok = pairs_ok && k.kind == Value::Kind::Struct && v.kind == Value::Kind::Int;
        expect("map_entries", pairs_ok && map_entries(actor, L"Tags").empty() && map_entries(actor, L"Nope").empty());
        if (!rewards.empty())
        {
            Value tag_name = get(rewards[0].first, L"TagName");
            expect("map_entries.key_struct", tag_name.kind == Value::Kind::Text && !tag_name.text.empty(), text(tag_name.text));
        }

        auto members = describe(actor);
        bool has_dilation = false, has_root = false;
        for (auto& m : members)
        {
            if (m.name == L"CustomTimeDilation") has_dilation = m.type == L"FloatProperty" && m.value.number() == 1.0;
            if (m.name == L"RootComponent") has_root = m.value.kind == Value::Kind::Object;
        }
        expect("describe", members.size() > 20 && has_dilation && has_root, std::to_string(members.size()));
        auto fields = describe(custom);
        bool has_clan = false;
        for (auto& m : fields) has_clan = has_clan || (m.name == L"ClanType" && m.value.kind == Value::Kind::Enum);
        expect("describe.struct", !fields.empty() && has_clan && describe(none).empty(), std::to_string(fields.size()));

        // Writes: a float the Python side reads back through Lua, a bool and an enum put straight back.
        expect("set.float", set(actor, L"CustomTimeDilation", 0.75) && get(actor, L"CustomTimeDilation").number() == 0.75);
        bool relevant = get(actor, L"bAlwaysRelevant").boolean();
        expect("set.bool", set(actor, L"bAlwaysRelevant", !relevant) && get(actor, L"bAlwaysRelevant").boolean() == !relevant
                               && set(actor, L"bAlwaysRelevant", relevant));
        expect("set.enum_by_name", set(actor, L"MeshCustomizationComponent.CustomData.ClanType", std::wstring_view(clan.text))
                                       && get(actor, L"MeshCustomizationComponent.CustomData.ClanType").i == clan.i);
        expect("set.enum_by_number", set(actor, L"MeshCustomizationComponent.CustomData.ClanType", static_cast<int>(clan.i)));
        expect("set.refused", !set(actor, L"CustomTimeDilation", L"text") && !set(actor, L"bHidden", 1.5) && !set(actor, L"Nope", true)
                                  && !set(nullptr, L"bHidden", true) && !set(actor, L"Tags", true));
        expect("set.object", set(actor, L"Controller.PlayerState", state.object));
        // Text into an FString and an FName: the same text back in, then read again.
        Value player_name = get(actor, L"Controller.PlayerState.PlayerNamePrivate");
        expect("get.fstring", player_name.kind == Value::Kind::Text && player_name.type == L"StrProperty", text(player_name.type));
        expect("set.fstring", set(actor, L"Controller.PlayerState.PlayerNamePrivate", std::wstring_view(player_name.text))
                                  && get(actor, L"Controller.PlayerState.PlayerNamePrivate").string() == player_name.text);
        Value socket = get(actor, L"RootComponent.AttachSocketName");
        expect("get.fname", socket.kind == Value::Kind::Text && socket.type == L"NameProperty", text(socket.type));
        expect("set.fname", set(actor, L"RootComponent.AttachSocketName", std::wstring_view(socket.text))
                                && get(actor, L"RootComponent.AttachSocketName").string() == socket.text);
        expect("value.of", Value::of(true).boolean() && Value::of(2.5).number() == 2.5 && Value::of(3).number() == 3
                               && Value::of(L"x").string() == L"x" && Value::of(actor).object == actor && Value::of(int64_t{7}).i == 7);

        auto at = location(actor);
        UObject* spawned = at ? spawn(STR("/Script/Engine.Actor"), {at->x, at->y, at->z + 300}) : nullptr;
        expect("spawn", spawned != nullptr && is_a(spawned, STR("/Script/Engine.Actor")), text(name(spawned)));
        value("reflect.spawned", text(class_name(spawned)));
        expect("spawn.missing", spawn(STR("/Script/Nope.Nope"), {0, 0, 0}) == nullptr);
        expect("destroy", destroy(spawned) && !destroy(nullptr));
    }

    auto setup_background() -> void
    {
        value("background.started", true);
        run_in_background(
                [] {
                    std::vector<int> numbers(1000);
                    std::iota(numbers.begin(), numbers.end(), 1);
                    value("background.off_game_thread", !on_game_thread_now());
                    value("background.assert_off", !assert_game_thread(L"the background check"));
                    std::this_thread::sleep_for(std::chrono::milliseconds(50));
                    return std::accumulate(numbers.begin(), numbers.end(), 0);
                },
                [](int sum) {
                    value("background.result", sum);
                    value("background.then_on_game_thread", on_game_thread_now() && assert_game_thread());
                });
        run_in_background([] { value("background.plain", true); });

        on_settings_changed([] {
            reloads++;
            value("settings.reloads", reloads.load());
            value("settings.number_now", settings()["number"].number());
        });
        expect("reload_settings", reload_settings() && settings()["number"].number() == 1.5);
    }
} // namespace t
