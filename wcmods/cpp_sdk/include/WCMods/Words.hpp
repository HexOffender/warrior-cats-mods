// Words.hpp: the game's words while it runs. Every line it shows (a cat's name, a talk's line, an item's name,
// the HUD's messages) is a key of a string table (SwtStrings, loaded from Strings_<language>.csv), and every
// text made from a key shows the one display string the engine keeps for it. Read a key's words, change them,
// put them back. Game thread only. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <algorithm>
#include <cstring>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <Unreal/FMemory.hpp>
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
        // (table, key) -> the game's words, for restore_words and for the mod going (stop_words). Game thread only.
        inline auto words_originals() -> std::map<std::pair<std::wstring, std::wstring>, std::wstring>&
        {
            static std::map<std::pair<std::wstring, std::wstring>, std::wstring> originals;
            return originals;
        }
        // Put new words into the shared display string without freeing what another thread may be reading: the
        // engine can lay out or format a text off the game thread. The new characters go in a buffer at least as
        // long as the old one (zeros after them), so whichever of the old and new pointer and count a reader
        // sees, it reads inside a buffer; the old buffer is freed 10 s later, not at once.
        inline auto replace_string(RC::Unreal::FString& s, std::wstring_view with) -> void
        {
            struct Raw
            {
                wchar_t* data;
                int32_t num;
                int32_t max;
            };
            auto* raw = reinterpret_cast<Raw*>(&s);
            const int32_t needed = static_cast<int32_t>(with.size()) + 1;
            const int32_t room = std::max(needed, raw->num);
            auto* fresh = static_cast<wchar_t*>(RC::Unreal::FMemory::Malloc(static_cast<size_t>(room) * sizeof(wchar_t), 0));
            std::memset(fresh, 0, static_cast<size_t>(room) * sizeof(wchar_t));
            std::memcpy(fresh, with.data(), with.size() * sizeof(wchar_t));
            wchar_t* old = raw->data;
            raw->data = fresh;
            raw->num = needed;
            raw->max = room;
            if (old) after(10.0, [old] { RC::Unreal::FMemory::Free(old); });
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
            detail::words_originals().try_emplace({std::wstring(table), std::wstring(key)}, std::wstring(*s));
            detail::replace_string(s, new_words);
        });
    }
    // Put a key's words back as the game had them when set_words first changed them; false when set_words didn't
    // change it. (After the player changes the game's language, these are the old language's words.)
    inline auto restore_words(std::wstring_view key, std::wstring_view table = game_strings) -> bool
    {
        if (!assert_game_thread(L"restore_words")) return false;
        auto& originals = detail::words_originals();
        auto it = originals.find({std::wstring(table), std::wstring(key)});
        if (it == originals.end()) return false;
        std::wstring was = it->second;
        originals.erase(it);
        return detail::with_display(table, key, [&](RC::Unreal::FString& s) { detail::replace_string(s, was); });
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
    namespace detail
    {
        // As the mod is taken out: the words it changed go back, so they don't outlive it.
        inline auto stop_words() -> void
        {
            auto originals = words_originals();
            words_originals().clear();
            for (auto& [where, was] : originals)
                with_display(where.first, where.second, [&](RC::Unreal::FString& s) { replace_string(s, was); });
        }
    } // namespace detail
} // namespace wcmods
