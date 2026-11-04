// Words.hpp: the game's words while it runs, on request ("words"), for tests/game/test_cpp_sdk.py to compare with
// what the game shows: a cat's name by its key, an item's name found from the text in its row, changed and shown
// by the HUD, and put back.
#include "checks.hpp"

#include <string>

namespace t
{
    namespace
    {
        auto hud_texts_containing(const std::wstring& what) -> Json
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

    auto run_words_request() -> void
    {
        phase("words");
        // ----- keys and words
        auto names = word_keys(L"STR_CAT_NAME");
        value("words.name_keys", static_cast<double>(names.size()));
        value("words.all_keys", static_cast<double>(word_keys().size()));
        auto ember = words(L"STR_CAT_NAME2_PAW");
        value("words.ember", ember ? Json(text(*ember)) : Json());
        expect("words.missing", !words(L"STR_NO_SUCH_KEY") && !set_words(L"STR_NO_SUCH_KEY", L"x") && !restore_words(L"STR_NO_SUCH_KEY")
                                    && !words(L"STR_CAT_NAME2_PAW", L"NoSuchTable"));
        expect("words.not_set_yet", !restore_words(L"STR_CAT_NAME2_PAW"));

        // ----- the herb's name: its key from the text in its row, changed, seen by the row's own text and the HUD
        const std::wstring herb = L"Gameplay.Inventory.Consumable.SmallCatnip";
        Table items = table(L"DT_QuestObjectsInfo");
        Value name_text;
        for (auto& [row_name, row] : items.rows())
            if (get(row, L"itemTag.TagName").text == herb) name_text = get(row, L"Name");
        auto where = words_key(name_text);
        value("words.herb_table", where ? Json(text(where->first)) : Json());
        value("words.herb_key", where ? Json(text(where->second)) : Json());
        expect("words.key_of_plain_value", !words_key(Value::of(std::wstring_view(L"not a text property"))));
        if (!where)
        {
            done("words");
            return;
        }
        const std::wstring key = where->second, table_id = where->first;
        value("words.herb_before", words(key, table_id) ? Json(text(*words(key, table_id))) : Json());
        expect("words.set", set_words(key, L"WCMods Word Herb", table_id) && words(key, table_id) == std::optional<std::wstring>(L"WCMods Word Herb"));
        // The row's own text, made before the change, shows the new words: it's the same display string.
        value("words.row_text_after", text(get(items.row(L"NewRow_44"), L"Name").shown()));
        int have = inventory_count(utf8(herb)).value_or(0);
        bool added = add_item(herb, 1);
        value("words.added", added);
        after(1.5, [key, table_id, herb, have, added] {
            value("words.hud_texts", hud_texts_containing(L"WCMods Word Herb"));
            expect("words.restore", restore_words(key, table_id) && !restore_words(key, table_id));
            value("words.herb_after", words(key, table_id) ? Json(text(*words(key, table_id))) : Json());
            if (added) remove_item(herb, inventory_count(utf8(herb)).value_or(0) - have);
            done("words");
        });
    }
} // namespace t
