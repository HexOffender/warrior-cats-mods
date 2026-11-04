// Tables.hpp: the game's DataTables row by row, and its tuning. The tuning map's reader is checked at init on a map
// laid out by hand; the rest on request ("tables"), for tests/game/test_cpp_sdk.py to compare with the game's own
// files and to see on screen.
#include "checks.hpp"

#include <cstring>
#include <format>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        // A TuningData map as the game lays it out: 0x38-byte slots of {FString key, row {vtable, float, FString},
        // hash links}, the slots in use in a bit array (inline).
        struct FakeTuning
        {
            alignas(8) uint8_t map[0x50]{};
            std::vector<uint8_t> slots;
            std::vector<std::wstring> keep;   // the strings the FStrings point at

            FakeTuning(const std::vector<std::pair<std::wstring, float>>& rows, std::vector<bool> used)
            {
                const int32_t n = static_cast<int32_t>(used.size());
                slots.assign(used.size() * 0x38, 0xEE);
                keep.reserve(rows.size() * 2);
                uint32_t bits[4]{};
                int32_t free_count = 0;
                size_t r = 0;
                auto put_string = [&](uint8_t* at, const std::wstring& s) {
                    keep.push_back(s);
                    const wchar_t* p = keep.back().c_str();
                    const int32_t num = static_cast<int32_t>(s.size()) + 1;
                    std::memcpy(at, &p, 8);
                    std::memcpy(at + 8, &num, 4);
                    std::memcpy(at + 12, &num, 4);
                };
                for (int32_t i = 0; i < n; ++i)
                {
                    if (!used[i] || r >= rows.size())
                    {
                        ++free_count;
                        continue;
                    }
                    uint8_t* e = &slots[static_cast<size_t>(i) * 0x38];
                    put_string(e, rows[r].first);
                    std::memcpy(e + 0x18, &rows[r].second, 4);
                    put_string(e + 0x20, L"about " + rows[r].first);
                    bits[i / 32] |= 1u << (i % 32);
                    ++r;
                }
                uint8_t* data = slots.data();
                std::memcpy(map, &data, 8);
                std::memcpy(map + 0x08, &n, 4);
                std::memcpy(map + 0x0C, &n, 4);
                std::memcpy(map + 0x10, bits, 16);
                std::memcpy(map + 0x28, &n, 4);
                std::memcpy(map + 0x2C, &n, 4);
                std::memcpy(map + 0x34, &free_count, 4);
            }
        };

        // The texts the HUD shows now that contain `what`.
        auto hud_texts_with(const std::wstring& what) -> Json
        {
            Json out = Json::array();
            Widget hud = ui::hud();
            if (!hud) return out;
            hud.walk([&](const Widget& w) {
                if (w.is_a(STR("/Script/UMG.TextBlock")) && w.text().find(what) != std::wstring::npos) out.push(text(w.text()));
                return true;
            });
            return out;
        }
    } // namespace

    auto run_tables_units() -> void
    {
        // Three keys in four slots, the second free: read in order, their values and descriptions, and a write
        // through a row's pointer is the map's.
        FakeTuning fake({{L"Gameplay.Exploration.MaxLevel", 20.0f}, {L"Gameplay.Exploration.Player.MoveAndRun.Run.Speed", 390.0f},
                         {L"Gameplay.Combat.Flee.Penalty", 0.5f}},
                        {true, false, true, true});
        std::vector<detail::TuningRow> rows;
        bool ok = detail::tuning_rows_in(fake.map, rows);
        expect("tables.tuning_map.read", ok && rows.size() == 3 && rows[0].key == L"Gameplay.Exploration.MaxLevel" && *rows[0].value == 20.0f
                                             && rows[1].key == L"Gameplay.Exploration.Player.MoveAndRun.Run.Speed" && *rows[1].value == 390.0f
                                             && rows[2].description == L"about Gameplay.Combat.Flee.Penalty");
        if (ok && rows.size() == 3)
        {
            *rows[1].value = 780.0f;
            std::vector<detail::TuningRow> again;
            detail::tuning_rows_in(fake.map, again);
            expect("tables.tuning_map.write", again.size() == 3 && *again[1].value == 780.0f);
        }
        // What doesn't add up as a map is refused: more slots in use than the count less the free ones.
        FakeTuning wrong({{L"A", 1.0f}}, {true, true});
        int32_t no_free = 0;
        std::memcpy(wrong.map + 0x34, &no_free, 4);   // two slots, none free, but one in use
        uint32_t one_bit = 1;
        std::memcpy(wrong.map + 0x10, &one_bit, 4);
        expect("tables.tuning_map.refused", !detail::tuning_rows_in(wrong.map, rows) && rows.empty());
        expect("tables.tuning_map.none", !detail::tuning_rows_in(nullptr, rows));
        // The game's keys ignore case.
        expect("tables.tuning.same_key", detail::same_key(L"Gameplay.Exploration.MaxLevel", L"gameplay.exploration.maxlevel")
                                             && !detail::same_key(L"Gameplay.Exploration.MaxLevel", L"Gameplay.Exploration.MaxLevels"));
    }

    auto run_tables_request() -> void
    {
        phase("tables");
        // ----- every DataTable, and the item table by its name and its path
        auto all = tables();
        value("tables.count", static_cast<double>(all.size()));
        Json items_info;
        for (auto& t : all)
            if (t.name == L"DT_QuestObjectsInfo")
            {
                items_info = Json::object();
                items_info.set("rows", t.rows);
                items_info.set("struct", text(t.row_struct));
                items_info.set("path", text(t.path));
            }
        value("tables.items_info", items_info);
        Table items = table(L"DT_QuestObjectsInfo");
        Table by_path = table(L"/Game/Gameplay/DataTables/Quests/DT_QuestObjectsInfo.DT_QuestObjectsInfo");
        expect("tables.by_name_and_path", items && by_path && items.object() == by_path.object()
                                              && items.path() == L"/Game/Gameplay/DataTables/Quests/DT_QuestObjectsInfo.DT_QuestObjectsInfo"
                                              && items.name() == L"DT_QuestObjectsInfo" && items.row_struct() != nullptr
                                              && items.row_struct_name() == L"QuestObjectsInfoDataStruct");
        expect("tables.missing", !table(L"DT_NoSuchTable") && !table(L"/Game/Nope/DT_Nope.DT_Nope") && !table(L""));
        if (!items)
        {
            done("tables");
            return;
        }
        auto names = items.row_names();
        value("tables.items.size", items.size());
        value("tables.items.names", static_cast<double>(names.size()));
        expect("tables.items.rows", static_cast<int>(names.size()) == items.size() && items.rows().size() == names.size());

        // ----- one row: its fields as the cooked file has them (the Python side compares)
        const std::wstring herb = L"Gameplay.Inventory.Consumable.SmallCatnip";
        std::wstring herb_row;
        for (auto& [name, row] : items.rows())
            if (get(row, L"itemTag.TagName").text == herb) herb_row = name;
        value("tables.herb.row", text(herb_row));
        Value row = items.row(herb_row);
        value("tables.herb.name", text(get(row, L"Name").shown()));
        value("tables.herb.rarity", text(get(row, L"ItemRarity").text));
        expect("tables.row.missing", items.row(L"No such row").kind == Value::Kind::None && !items.has(L"No such row"));

        // ----- a row added (a copy, and one of defaults) and taken out again
        const int before = items.size();
        Value copy = items.add_row(L"WCModsTestRow", herb_row);
        expect("tables.add_row.copy", copy.kind == Value::Kind::Struct && items.size() == before + 1 && items.has(L"WCModsTestRow")
                                          && get(copy, L"itemTag.TagName").text == herb);
        set(copy, L"ItemRarity", Value::of(std::wstring_view(L"Mythic")));
        expect("tables.add_row.own_copy", get(items.row(L"WCModsTestRow"), L"ItemRarity").text == L"Mythic"
                                              && get(items.row(herb_row), L"ItemRarity").text != L"Mythic");
        Value fresh = items.add_row(L"WCModsFreshRow");
        expect("tables.add_row.defaults", fresh.kind == Value::Kind::Struct && get(fresh, L"itemTag.TagName").text == L"None"
                                              && items.size() == before + 2);
        expect("tables.add_row.bad_from", items.add_row(L"WCModsBad", L"No such row").kind == Value::Kind::None && !items.has(L"WCModsBad"));
        expect("tables.remove_row", items.remove_row(L"WCModsTestRow") && items.remove_row(L"WCModsFreshRow") && items.size() == before
                                        && !items.remove_row(L"WCModsTestRow"));

        // ----- tuning: every key, one read, written, read back by the game's own lookup, and put back
        auto keys = tuning_keys();
        value("tuning.keys", static_cast<double>(keys.size()));
        Json some = Json::object();
        for (const wchar_t* k : {L"Gameplay.Exploration.MaxLevel", L"Gameplay.Exploration.Player.MoveAndRun.Run.Speed",
                                 L"Gameplay.Exploration.Metrics.Cat.Player.Height"})
            if (auto v = tuning(k)) some.set(utf8(k), static_cast<double>(*v));
        value("tuning.some", some);
        value("tuning.description", tuning_description(L"Gameplay.Exploration.Metrics.Cat.Player.Height")
                                        ? Json(text(*tuning_description(L"Gameplay.Exploration.Metrics.Cat.Player.Height"))) : Json());
        expect("tuning.missing", !tuning(L"No.Such.Key") && !set_tuning(L"No.Such.Key", 1) && !tuning_description(L"No.Such.Key"));
        expect("tuning.any_case", tuning(L"gameplay.exploration.maxlevel") == tuning(L"Gameplay.Exploration.MaxLevel"));
        const std::wstring key = L"Gameplay.Exploration.MaxLevel";
        auto was = tuning(key);
        auto game_lookup = native<float (*)(const RC::Unreal::FString*)>(L"SwtTuningManager:GetValue");
        value("tuning.lookup_found", game_lookup != nullptr);
        if (was && game_lookup)
        {
            RC::Unreal::FString k(key.c_str());
            float game_before = game_lookup(&k);
            set_tuning(key, 33.0f);
            float game_after = game_lookup(&k);
            set_tuning(key, *was);
            float game_restored = game_lookup(&k);
            value("tuning.game_before", static_cast<double>(game_before));
            value("tuning.game_after", static_cast<double>(game_after));
            expect("tuning.game_reads_it", game_before == *was && game_after == 33.0f && game_restored == *was,
                   text(std::format(L"{} then {} then {}", game_before, game_after, game_restored)));
        }

        // ----- a row's change the game shows: the herb renamed, one added, and the HUD's "<name> OBTAINED"
        // message read a moment later; the name and the herb put back after.
        if (!herb_row.empty())
        {
            // set() writes a plain text, cut from the string table's key: the row's own text is kept whole in a copy
            // of the row (add_row copies each property with the engine's copy), and copied back after, so the
            // name follows its key (Words.hpp) again.
            items.remove_row(L"WCModsKeepRow");   // one a run cut short left
            items.add_row(L"WCModsKeepRow", herb_row);
            Value r = items.row(herb_row);
            expect("tables.set_name", set(r, L"Name", std::wstring_view(L"WCMods Test Herb"))
                                          && get(items.row(herb_row), L"Name").shown() == L"WCMods Test Herb");
            int have = inventory_count(utf8(herb)).value_or(0);
            bool added = add_item(herb, 1);
            value("tables.herb.added", added);
            after(1.5, [herb_row, herb, have, added] {
                value("tables.hud_texts", hud_texts_with(L"WCMods Test Herb"));
                Table again = table(L"DT_QuestObjectsInfo");
                Value name_now = get(again.row(herb_row), L"Name"), kept = get(again.row(L"WCModsKeepRow"), L"Name");
                if (name_now.property && name_now.at && kept.at) name_now.property->CopySingleValue(name_now.at, kept.at);
                again.remove_row(L"WCModsKeepRow");
                if (added) remove_item(herb, inventory_count(utf8(herb)).value_or(0) - have);
                value("tables.herb.name_after", text(get(again.row(herb_row), L"Name").shown()));
                auto key = words_key(get(again.row(herb_row), L"Name"));
                value("tables.herb.name_key_after", key ? Json(text(key->second)) : Json());
                done("tables");
            });
            return;
        }
        done("tables");
    }
} // namespace t
