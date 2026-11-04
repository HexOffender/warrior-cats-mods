// Words.hpp: the game's words while it runs. Every line it shows (a cat's name, a talk's line, an item's name,
// the HUD's messages) is a key of a string table (SwtStrings, loaded from Strings_<language>.csv), and every
// text made from a key shows the one display string the engine keeps for it. Read a key's words, change them,
// put them back. Game thread only. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <map>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <Unreal/FString.hpp>
#include <Unreal/FText.hpp>
#include <Unreal/ITextData.hpp>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>

namespace wcmods
{
    // The game's own string table: every line it shows.
    inline constexpr std::wstring_view game_strings = L"SwtStrings";

    namespace detail
    {
        inline auto string_tables_library() -> UObject* { return wcmods::object(STR("/Script/Engine.Default__KismetStringTableLibrary")); }
        inline auto text_library() -> UObject* { return wcmods::object(STR("/Script/Engine.Default__KismetTextLibrary")); }

        inline auto is_entry(std::wstring_view table, std::wstring_view key) -> bool
        {
            auto r = call_reflected(string_tables_library(), STR("IsRegisteredTableEntry"), [&](Params& p) {
                p.set_nth(0, Value::of(table));
                p.set_nth(1, Value::of(key));
            });
            return r && r->get(L"ReturnValue").boolean();
        }
        // `fn(display)` with the display string a text made from the key shows: the engine's one string for the
        // key, which every text made from it shares (so a change to it is every such text's). False when the
        // table hasn't got the key.
        template <typename Fn>
        inline auto with_display(std::wstring_view table, std::wstring_view key, Fn&& fn) -> bool
        {
            if (!is_entry(table, key)) return false;
            auto r = call_reflected(text_library(), STR("TextFromStringTable"), [&](Params& p) {
                p.set_nth(0, Value::of(table));
                p.set_nth(1, Value::of(key));
            });
            if (!r) return false;
            auto* text = static_cast<RC::Unreal::FText*>(r->raw(L"ReturnValue"));
            RC::Unreal::ITextData* data = text ? text->GetTextData() : nullptr;
            if (!data) return false;
            fn(const_cast<RC::Unreal::FString&>(data->GetDisplayString()));
            return true;
        }
        struct WordsState
        {
            std::mutex lock;
            std::map<std::pair<std::wstring, std::wstring>, std::wstring> originals;   // (table, key) -> the game's words
        };
        inline auto words_state() -> WordsState&
        {
            static WordsState s;
            return s;
        }
    } // namespace detail

    // A key's words as the game shows them now (L"STR_CAT_NAME2_PAW" is "Emberpaw"); nullopt for a key the table
    // hasn't got. `table` is SwtStrings unless you say another.
    inline auto words(std::wstring_view key, std::wstring_view table = game_strings) -> std::optional<std::wstring>
    {
        if (!assert_game_thread(L"words")) return std::nullopt;
        std::optional<std::wstring> out;
        detail::with_display(table, key, [&](RC::Unreal::FString& s) { out = std::wstring(*s); });
        return out;
    }
    // Change a key's words: every text made from the key shows them from then on, so a screen, popup or line
    // the game makes after it does (the HUD's "OBTAINED" message, a talk's line); a text the game already laid
    // out may keep the old words until it's made again. False for a key the table hasn't got. The game's words
    // are kept, for restore_words.
    inline auto set_words(std::wstring_view key, std::wstring_view new_words, std::wstring_view table = game_strings) -> bool
    {
        if (!assert_game_thread(L"set_words")) return false;
        return detail::with_display(table, key, [&](RC::Unreal::FString& s) {
            auto& st = detail::words_state();
            std::lock_guard lock(st.lock);
            st.originals.try_emplace({std::wstring(table), std::wstring(key)}, std::wstring(*s));
            s = RC::Unreal::FString(std::wstring(new_words).c_str());
        });
    }
    // Put a key's words back as the game had them; false when set_words didn't change it.
    inline auto restore_words(std::wstring_view key, std::wstring_view table = game_strings) -> bool
    {
        if (!assert_game_thread(L"restore_words")) return false;
        std::optional<std::wstring> was;
        {
            auto& st = detail::words_state();
            std::lock_guard lock(st.lock);
            auto it = st.originals.find({std::wstring(table), std::wstring(key)});
            if (it == st.originals.end()) return false;
            was = it->second;
            st.originals.erase(it);
        }
        return detail::with_display(table, key, [&](RC::Unreal::FString& s) { s = RC::Unreal::FString(was->c_str()); });
    }
    // The table's keys, those starting with `prefix` when one is given (L"STR_CAT_NAME"), in the table's order.
    inline auto word_keys(std::wstring_view prefix = {}, std::wstring_view table = game_strings) -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        if (!assert_game_thread(L"word_keys")) return out;
        auto r = call_reflected(detail::string_tables_library(), STR("GetKeysFromStringTable"),
                                [&](Params& p) { p.set_nth(0, Value::of(table)); });
        if (!r) return out;
        for (Value& v : elements(r->get(L"ReturnValue")))
            if (v.text.starts_with(prefix)) out.push_back(v.text);
        return out;
    }
    // Which table and key a text the game holds was made from (an item's Name in its row, a widget's text), or
    // nullopt for a text that isn't from a string table. `text` is a Value of a text property (get() gives one).
    inline auto words_key(const Value& text) -> std::optional<std::pair<std::wstring, std::wstring>>
    {
        if (!assert_game_thread(L"words_key") || text.kind != Value::Kind::Text || !text.at || text.type != L"TextProperty") return std::nullopt;
        if (!text.property) return std::nullopt;
        auto r = call_reflected(detail::text_library(), STR("StringTableIdAndKeyFromText"), [&](Params& p) {
            // Copied by the text property's own copy (the engine's), which counts the reference the parameters'
            // buffer gives back when it goes.
            if (void* into = p.raw(L"Text")) text.property->CopySingleValue(into, text.at);
        });
        if (!r) return std::nullopt;
        std::wstring table = r->get(L"OutTableId").text, key = r->get(L"OutKey").text;
        if (table.empty() || table == L"None" || key.empty()) return std::nullopt;
        return std::make_pair(table, key);
    }
} // namespace wcmods
