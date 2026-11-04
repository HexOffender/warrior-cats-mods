// The game's native functions (Core.hpp), and what World.hpp and Ui.hpp do with them and with the game's own
// commands: the live inventory and adding to it, opening and closing the game's screens, the sky's presets,
// the game's sounds and animations, and saving. The pure parts are checked at init without the game (a
// pattern against bytes, a map laid out by hand); the rest on request, for tests/game/test_cpp_sdk.py to
// confirm with Lua and with the save file.
#include "checks.hpp"

#include <atomic>
#include <cstring>
#include <ctime>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        constexpr auto ITEM = L"Gameplay.Inventory.Consumable.SmallCatnip";   // added and taken away again
        std::atomic<int> picked_up{};   // the HUD's OnItemPickedUp, as the game calls it
        std::string picked_tag;
        std::atomic<int> picked_quantity{}, picked_total{};
        HookId pickup_hook{};

        // A TMap<FGameplayTag, int32> laid out by hand as the game's TSet is (World.hpp's tag_counts): 0x50
        // bytes, its elements 20 bytes each.
        struct FakeMap
        {
            alignas(8) uint8_t map[0x50]{};
            std::vector<uint8_t> elements;
            std::vector<uint32_t> heap_bits;

            // `used` says which slots are in use; each element is (index, number, count) = (100 + i, i, 10 * i).
            explicit FakeMap(std::vector<bool> used, bool on_heap = false)
            {
                const int32_t n = static_cast<int32_t>(used.size());
                elements.assign(used.size() * 20, 0xEE);   // free slots hold junk
                int32_t free_count = 0;
                uint32_t bits[4]{};
                for (int32_t i = 0; i < n; ++i)
                {
                    if (!used[i])
                    {
                        ++free_count;
                        continue;
                    }
                    const uint32_t index = 100 + i, number = i;
                    const int32_t count = 10 * i;
                    std::memcpy(&elements[i * 20], &index, 4);
                    std::memcpy(&elements[i * 20 + 4], &number, 4);
                    std::memcpy(&elements[i * 20 + 8], &count, 4);
                    bits[i / 32] |= 1u << (i % 32);
                }
                uint8_t* data = elements.data();
                std::memcpy(map, &data, 8);
                std::memcpy(map + 0x08, &n, 4);
                std::memcpy(map + 0x0C, &n, 4);
                if (on_heap)
                {
                    heap_bits.assign(bits, bits + 4);
                    const uint32_t* hb = heap_bits.data();
                    std::memcpy(map + 0x20, &hb, 8);
                    std::memset(map + 0x10, 0xFF, 16);   // stale inline words: the heap's are the ones
                }
                else
                {
                    std::memcpy(map + 0x10, bits, 16);
                }
                const int32_t max_bits = 128;
                std::memcpy(map + 0x28, &n, 4);
                std::memcpy(map + 0x2C, &max_bits, 4);
                std::memcpy(map + 0x34, &free_count, 4);
            }
            auto set_i32(size_t at, int32_t v) -> FakeMap&
            {
                std::memcpy(map + at, &v, 4);
                return *this;
            }
        };

        auto pairs_text(const std::vector<detail::TagCount>& pairs) -> std::string
        {
            std::string out;
            for (const auto& p : pairs) out += std::to_string(p.name_index) + "/" + std::to_string(p.name_number) + "=" + std::to_string(p.count) + " ";
            return out;
        }

        auto object_text(UObject* o) -> Json { return o ? Json(text(name(o))) : Json(); }

        // The fog's density and the sun's brightness now, which the sky's presets set.
        auto sky_now() -> Json
        {
            Json out = Json::object();
            auto fog = call_reflected(sky(), STR("GetExponentialHeightFog"));
            auto light = call_reflected(sky(), STR("GetDirectionLightComponent"));
            out.set("fog", fog ? Json(get(fog->get(L"ReturnValue").object, L"FogDensity").number()) : Json());
            out.set("light", light ? Json(get(light->get(L"ReturnValue").object, L"Intensity").number()) : Json());
            return out;
        }
    } // namespace

    auto run_native_units() -> void
    {
        // ----- a pattern against bytes, as native_address checks the game's code
        const uint8_t code[] = {0x44, 0x89, 0x44, 0x24, 0x18, 0x48, 0x89, 0x54};
        expect("native.pattern.exact", detail::pattern_matches(code, sizeof code, "44 89 44 24 18 48 89 54"));
        expect("native.pattern.wildcards", detail::pattern_matches(code, sizeof code, "44 89 ?? 24 ?? 48"));
        expect("native.pattern.differs", !detail::pattern_matches(code, sizeof code, "44 89 44 24 19"));
        expect("native.pattern.longer_than_the_code", !detail::pattern_matches(code, 4, "44 89 44 24 18"));
        expect("native.pattern.empty_and_junk", !detail::pattern_matches(code, sizeof code, "")
                                                    && !detail::pattern_matches(code, sizeof code, "4G 89")
                                                    && !detail::pattern_matches(code, sizeof code, "4"));

        // ----- a map laid out by hand, as the inventory's is
        std::vector<detail::TagCount> pairs;
        FakeMap three({true, true, false, true});
        bool ok = detail::tag_counts(three.map, pairs);
        expect("native.map.in_use", ok && pairs.size() == 3 && pairs[0].name_index == 100 && pairs[1].count == 10
                                        && pairs[2].name_index == 103 && pairs[2].name_number == 3 && pairs[2].count == 30,
               pairs_text(pairs));
        FakeMap heap({false, true, true}, true);
        ok = detail::tag_counts(heap.map, pairs);
        expect("native.map.heap_bits", ok && pairs.size() == 2 && pairs[0].name_index == 101, pairs_text(pairs));
        FakeMap empty({});
        expect("native.map.empty", detail::tag_counts(empty.map, pairs) && pairs.empty());
        // What doesn't add up as a map is refused, whole: free slots that disagree with the bits, a count past
        // what fits, a negative count, no elements behind a count, more slots than the inline bit words hold
        // with no bit array on the heap, and no map at all.
        FakeMap wrong_free({true, true, false});
        wrong_free.set_i32(0x34, 0);
        FakeMap past_max({true});
        past_max.set_i32(0x0C, 0);
        FakeMap negative({true});
        negative.set_i32(0x08, -1);
        FakeMap no_data({true});
        std::memset(no_data.map, 0, 8);
        FakeMap inline_too_many({true});
        inline_too_many.set_i32(0x28, 200).set_i32(0x2C, 256);
        expect("native.map.refused", !detail::tag_counts(wrong_free.map, pairs) && pairs.empty()
                                         && !detail::tag_counts(past_max.map, pairs) && !detail::tag_counts(negative.map, pairs)
                                         && !detail::tag_counts(no_data.map, pairs) && !detail::tag_counts(inline_too_many.map, pairs)
                                         && !detail::tag_counts(nullptr, pairs));

        // ----- a name offsets.json hasn't got
        expect("native.unknown", native_address(L"NoSuchClass:NoSuchFunction") == nullptr
                                     && native<void (*)()>(L"NoSuchClass:NoSuchFunction") == nullptr);
    }

    auto run_native_request(const std::string& what) -> bool
    {
        if (what == "native")
        {
            phase("native");
            void* add = native_address(L"SwtQuestInventoryComponent:AddItem");
            auto [base, size] = detail::game_image();
            expect("native.found", add != nullptr && base != nullptr);
            value("native.add_item_rva", add ? Json(static_cast<double>(static_cast<const uint8_t*>(add) - base)) : Json());
            expect("native.cached", native_address(L"SwtQuestInventoryComponent:AddItem") == add);
            UObject* inv = inventory_component();
            value("native.inventory_class", text(class_name(inv)));
            Json now = inventory();
            expect("native.inventory", now.is_object(), now.dump(0));
            value("native.inventory", now);
            value("native.inventory_count", inventory_count(utf8(ITEM)) ? Json(*inventory_count(utf8(ITEM))) : Json());
            expect("native.is_item_tag", is_item_tag(ITEM) && is_item_tag(L"Gameplay.Inventory.Materials.Bone")
                                             && !is_item_tag(L"Gameplay.Inventory.Consumable.NoSuchHerb")
                                             && !is_item_tag(L"Animation.Exploration.Meow") && !is_item_tag(L""));
            done("native");
            return true;
        }
        if (what == "inventory_add")
        {
            phase("inventory_add");
            if (!pickup_hook)
                pickup_hook = on_function(STR("/Script/Wrc.GuiHudWrc:OnItemPickedUp"), [](Call& call) {
                    picked_tag = utf8(get(call.param(0), L"TagName").text);
                    picked_quantity = static_cast<int>(call.param(1).number());
                    picked_total = static_cast<int>(call.param(2).number());
                    picked_up++;
                });
            const int before = inventory_count(utf8(ITEM)).value_or(-1);
            const int heard = picked_up.load();
            const bool added = add_item(ITEM, 2);
            const int after = inventory_count(utf8(ITEM)).value_or(-1);
            value("add.before", before);
            value("add.after", after);
            value("add.save_state", save_state(L"Inventory"));   // the save manager's copy, which Lua reads too
            value("add.heard", picked_up.load() - heard);
            value("add.heard_tag", picked_tag);
            value("add.heard_quantity", picked_quantity.load());
            value("add.heard_total", picked_total.load());
            expect("add_item", added && before >= 0 && after == before + 2, std::to_string(before) + " -> " + std::to_string(after));
            expect("add_item.refused", !add_item(L"Gameplay.Inventory.Consumable.NoSuchHerb") && !add_item(L"Animation.Exploration.Meow")
                                           && !add_item(ITEM, 0) && !add_item(ITEM, -1) && inventory_count(utf8(ITEM)).value_or(-1) == after);
            done("inventory_add");
            return true;
        }
        if (what == "inventory_remove")
        {
            phase("inventory_remove");
            const int before = inventory_count(utf8(ITEM)).value_or(-1);
            const bool removed = remove_item(ITEM, 2);
            const int after = inventory_count(utf8(ITEM)).value_or(-1);
            value("remove.before", before);
            value("remove.after", after);
            value("remove.save_state", save_state(L"Inventory"));
            expect("remove_item", removed && after == before - 2, std::to_string(before) + " -> " + std::to_string(after));
            // Nothing to take away: refused, and nothing changes (the game would add the item at -1 and drop it).
            // The first of these the cat hasn't got; it holds them all only in a save made to.
            const wchar_t* unheld = nullptr;
            for (auto tag : {L"Gameplay.Inventory.Consumable.FullHealingHerb", L"Gameplay.Inventory.Consumable.BigCatnip",
                             L"Gameplay.Inventory.Materials.Bone", L"Gameplay.Inventory.Materials.BirdNest"})
                if (!unheld && inventory_count(utf8(tag)).value_or(1) == 0) unheld = tag;
            value("remove.unheld", unheld ? Json(utf8(unheld)) : Json());
            const int left = inventory_count(utf8(ITEM)).value_or(-1);
            expect("remove_item.nothing_held", (!unheld || !remove_item(unheld, 1)) && !remove_item(ITEM, 0) && !remove_item(ITEM, -1)
                                                   && inventory_count(utf8(ITEM)).value_or(-1) == left);
            done("inventory_remove");
            return true;
        }
        if (what == "command_open")
        {
            phase("command_open");
            expect("command.unknown", !command(L"NoSuchCommand"));
            expect("command", command(L"Player_Show_Inventory"));
            done("command_open");
            return true;
        }
        if (what == "command_close")
        {
            phase("command_close");
            auto shown = ui::screen(L"WBP_GuiPopupInventory_C");
            value("command.shown", static_cast<bool>(shown));
            expect("ui.send.unknown", !ui::send(shown, L"NoSuchCommand") && !ui::send(Widget{}, L"Button_Back"));
            expect("ui.close", ui::close(shown));
            done("command_close");
            return true;
        }
        if (what == "sky")
        {
            phase("sky");
            UObject* s = sky();
            value("sky.class", text(class_name(s)));
            value("sky.before", sky_now());
            expect("set_sky.unknown", !set_sky(L"NoSuchPreset") && !set_sky(L"NoSuchPreset", false));
            expect("set_sky", set_sky(L"Night"));
            value("sky.night", sky_now());
            done("sky");
            return true;
        }
        if (what == "sky_values")
        {
            // The presets' table, Night's fog read from its row, the fog held at Night, the row's fog made ten times
            // thicker and the fog read again; a colour's part, what isn't there refused; all put back.
            phase("sky_values");
            Table presets = sky_presets();
            value("skyv.table", text(presets.name()));
            value("skyv.struct", text(presets.row_struct_name()));
            Json rows = Json::array();
            for (auto& r : presets.row_names()) rows.push(text(r));
            value("skyv.rows", rows);
            double row_fog = get(sky_values(L"Night"), L"FogDensity").number();
            value("skyv.night_row_fog", row_fog);
            value("skyv.night_table_fog", get(presets.row(L"Night"), L"FogDensity").number());
            value("skyv.thunder_sun", get(sky_values(L"ThunderClan"), L"SunIntensity").number());
            expect("skyv.missing", sky_values(L"NoSuchPreset").kind == Value::Kind::None && !set_sky_value(L"NoSuchPreset", L"FogDensity", 1)
                                       && !set_sky_value(L"Night", L"NoSuchField", 1) && !set_sky_value(L"Night", L"SunColor", 1));
            expect("skyv.held", set_sky(L"Night"));
            after(0.5, [row_fog] {
                value("skyv.fog_before", sky_now());
                expect("skyv.set", set_sky_value(L"Night", L"FogDensity", row_fog * 10) && set_sky_value(L"Night", L"SunColor.R", 0.5)
                                       && get(sky_values(L"Night"), L"SunColor.R").number() == 0.5);
                after(0.5, [row_fog] {
                    value("skyv.fog_after", sky_now());
                    restore_sky_values();
                    value("skyv.night_row_fog_restored", get(sky_values(L"Night"), L"FogDensity").number());
                    expect("skyv.restored", get(sky_values(L"Night"), L"FogDensity").number() == row_fog);
                    sky_follow_area();
                    done("sky_values");
                });
            });
            return true;
        }
        if (what == "sky_area")
        {
            phase("sky_area");
            expect("sky_follow_area", sky_follow_area());
            value("sky.area", sky_now());
            done("sky_area");
            return true;
        }
        if (what == "sound")
        {
            phase("sound");
            value("sound.manager", text(class_name(audio_manager())));
            auto ids = sound_ids();
            value("sound.count", static_cast<double>(ids.size()));
            bool has = false;
            for (auto& id : ids) has = has || id == L"ui_select";
            expect("sound_ids", has);
            UObject* ui = play_sound(L"ui_select");
            value("sound.ui", ui ? Json(text(class_name(ui))) : Json());
            value("sound.ui_sound", ui ? object_text(get(ui, L"Sound").object) : Json());
            value("sound.ui_playing", ui ? Json(call<bool>(ui, STR("IsPlaying")).value_or(false)) : Json());
            auto at = cat().location();
            UObject* there = at ? play_sound(L"vo_cat1_happy1", *at) : nullptr;
            value("sound.there_sound", there ? object_text(get(there, L"Sound").object) : Json());
            expect("play_sound", ui && there);
            expect("play_sound.unknown", play_sound(L"no_such_sound") == nullptr);
            done("sound");
            return true;
        }
        if (what == "montage")
        {
            phase("montage");
            UObject* me = player();
            UObject* m = play_montage(me, L"Animation.Exploration.Meow");
            value("montage.name", object_text(m));
            value("montage.playing", montage_playing(me));
            expect("play_montage", m != nullptr && montage_playing(me));
            expect("play_montage.unknown", play_montage(me, L"Animation.Exploration.NoSuchMove") == nullptr
                                               && play_montage(nullptr, L"Animation.Exploration.Meow") == nullptr);
            done("montage");
            return true;
        }
        if (what == "save")
        {
            phase("save");
            auto before = save_hash();
            // What formats/save.py's next_hash says the new Hash is made of: the time of the write (UTC, to the
            // second) and the storage manager's address, seeded with the old Hash.
            const auto t0 = std::time(nullptr);
            const bool saved = save_game();
            const auto t1 = std::time(nullptr);
            auto after = save_hash();
            // As text: a uint64 doesn't fit a JSON number.
            value("save.hash_before", before ? Json(std::to_string(*before)) : Json());
            value("save.hash_after", after ? Json(std::to_string(*after)) : Json());
            value("save.time_before", static_cast<double>(t0));
            value("save.time_after", static_cast<double>(t1));
            value("save.storage_address", std::to_string(reinterpret_cast<uintptr_t>(manager(STR("storage")))));
            value("save.save_manager_address", std::to_string(reinterpret_cast<uintptr_t>(save_manager())));
            expect("save_game", saved && before && after);
            done("save");
            return true;
        }
        return false;
    }
} // namespace t
