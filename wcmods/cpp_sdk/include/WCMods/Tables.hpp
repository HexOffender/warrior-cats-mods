// Tables.hpp: the game's tables while it runs. Its DataTables (items, characters, fights, animations, the sky's
// presets, den decorations, tutorials...) row by row, read and changed in place, rows added and taken out; and
// TuningData.csv, the tuning every part of the game reads its numbers from. Game thread only. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <cwctype>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <Unreal/CoreUObject/UObject/Class.hpp>
#include <Unreal/Engine/UDataTable.hpp>
#include <Unreal/FMemory.hpp>
#include <Unreal/NameTypes.hpp>
#include <Unreal/UObjectArray.hpp>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>

namespace wcmods
{
    // ============================================================================================ DataTables
    // A DataTable is an asset the game loads with its level or its managers (69 were in memory in the forest on
    // build 26337109): a row struct and a map of row name to the row's bytes. A row is the game's own memory, so a
    // change is what the game reads from then on; code that copied a row's numbers earlier keeps its copy.

    // One of the game's DataTables, or empty (false) when there's no such table in memory.
    class Table
    {
      public:
        Table() = default;
        explicit Table(UObject* object) : m_object(object)
        {
            if (m_object) m_index = m_object->GetInternalIndex();
        }

        // Whether it's still the table it was (the game can unload one with its level).
        explicit operator bool() const { return object() != nullptr; }
        auto object() const -> UObject*
        {
            // By the slot in the engine's object array it was in, not through the pointer, which may be freed.
            if (!m_object || m_index < 0 || m_index >= RC::Unreal::UObjectArray::GetNumElements()) return nullptr;
            auto* item = RC::Unreal::UObjectArray::IndexToObject(m_index);
            if (!item || item->GetUObject() != m_object || !item->IsValid(false)) return nullptr;
            return m_object;
        }
        auto name() const -> std::wstring { return object() ? wcmods::name(m_object) : std::wstring{}; }
        auto path() const -> std::wstring { return object() ? m_object->GetPathName() : std::wstring{}; }
        // The struct its rows are (QuestObjectsInfoDataStruct, WrcSkyBoxStruct...), and its name.
        auto row_struct() const -> RC::Unreal::UScriptStruct*
        {
            auto* t = table();
            return t ? static_cast<RC::Unreal::UScriptStruct*>(t->GetRowStruct()) : nullptr;
        }
        auto row_struct_name() const -> std::wstring
        {
            auto* s = row_struct();
            return s ? s->GetName() : std::wstring{};
        }
        // How many rows, and their names in the table's order.
        auto size() const -> int
        {
            auto* t = table();
            return t ? t->GetRowMap().Num() : 0;
        }
        auto row_names() const -> std::vector<std::wstring>
        {
            std::vector<std::wstring> out;
            if (!assert_game_thread(L"Table::row_names")) return out;
            if (auto* t = table())
                for (auto& pair : t->GetRowMap()) out.push_back(pair.Key.ToString());
            return out;
        }
        auto has(std::wstring_view row_name) const -> bool { return row_bytes(row_name) != nullptr; }
        // A row as a struct Value: get(), set() and describe() work on it, and a set() changes the game's row.
        // None when the table hasn't got the row.
        auto row(std::wstring_view row_name) const -> Value
        {
            uint8_t* bytes = row_bytes(row_name);
            return bytes ? struct_at(row_struct(), bytes) : Value{};
        }
        // Every row, by name, in the table's order.
        auto rows() const -> std::vector<std::pair<std::wstring, Value>>
        {
            std::vector<std::pair<std::wstring, Value>> out;
            auto* t = table();
            auto* s = row_struct();
            if (!t || !s || !assert_game_thread(L"Table::rows")) return out;
            for (auto& pair : t->GetRowMap()) out.emplace_back(pair.Key.ToString(), struct_at(s, pair.Value));
            return out;
        }
        // A row of the mod's own: a copy of the row `from` (another of this table's), or the row struct's defaults
        // without one. A row with that name already is replaced. The new row as a Value, or None when `from`
        // isn't a row of this table. The game sees it where it looks rows up by name; a list it built from the
        // table earlier (a screen's, a manager's) doesn't have it.
        auto add_row(std::wstring_view row_name, std::wstring_view from = {}) -> Value
        {
            auto* t = table();
            auto* s = row_struct();
            if (!t || !s || row_name.empty() || !assert_game_thread(L"Table::add_row")) return {};
            uint8_t* source = nullptr;
            if (!from.empty() && !(source = row_bytes(from))) return {};
            // The row is made as the engine makes one (its own InitializeStruct, which sets the row's vtable and
            // defaults), then filled property by property with the engine's own copies (texts, strings and soft
            // references copied whole). Not UE4SS's AddRow: it copies through the struct's native copy, which UE4SS
            // can't reach on this engine ("ICppStructOps::Copy is unavailable", seen in game on build 26337109).
            // 16-byte aligned, as the engine's own allocator gives a row (UE4SS doesn't export a struct's own alignment).
            auto* fresh = static_cast<uint8_t*>(RC::Unreal::FMemory::Malloc(static_cast<size_t>(s->GetSize()), 16));
            try
            {
                s->InitializeStruct(fresh);
                if (source)
                    for (RC::Unreal::FProperty* p : detail::properties_in_chain(s)) p->CopyCompleteValue_InContainer(fresh, source);
            }
            catch (...)
            {
                // UE4SS throws when it can't reach one of the engine's functions on this build: no row then.
                RC::Unreal::FMemory::Free(fresh);
                log(L"can't make a row of {} on this game build", s->GetName());
                return {};
            }
            if (has(row_name)) remove_row(row_name);
            t->GetRowMap().Add(RC::Unreal::FName(std::wstring(row_name).c_str(), RC::Unreal::FNAME_Add), fresh);
            return row(row_name);
        }
        // Take a row out: false when there's no such row.
        auto remove_row(std::wstring_view row_name) -> bool
        {
            auto* t = table();
            if (!t || !has(row_name) || !assert_game_thread(L"Table::remove_row")) return false;
            t->RemoveRow(RC::Unreal::FName(std::wstring(row_name).c_str(), RC::Unreal::FNAME_Find));
            return !has(row_name);
        }

      private:
        auto table() const -> RC::Unreal::UDataTable* { return static_cast<RC::Unreal::UDataTable*>(object()); }
        auto row_bytes(std::wstring_view row_name) const -> uint8_t*
        {
            auto* t = table();
            if (!t || row_name.empty() || !t->GetRowStruct()) return nullptr;
            // FNAME_Find: a name nobody has made can't be a row, and isn't added to the game's names to ask. It
            // gives None for those; a row really named None is looked up as None.
            RC::Unreal::FName key(std::wstring(row_name).c_str(), RC::Unreal::FNAME_Find);
            if (key == RC::Unreal::FName() && _wcsicmp(std::wstring(row_name).c_str(), L"None") != 0) return nullptr;
            return t->FindRowUnchecked(key);
        }
        UObject* m_object{};
        int32_t m_index{};
    };

    // Every DataTable in memory: each one's name, path, row struct and row count. It goes through the game's
    // objects: a few times a second at most, not every frame.
    struct TableInfo
    {
        std::wstring name;
        std::wstring path;
        std::wstring row_struct;
        int rows{};
    };
    inline auto tables() -> std::vector<TableInfo>
    {
        std::vector<TableInfo> out;
        if (!assert_game_thread(L"tables")) return out;
        for (UObject* o : find_all(STR("DataTable")))
        {
            Table t(o);
            if (!t) continue;
            out.push_back({t.name(), t.path(), t.row_struct_name(), t.size()});
        }
        return out;
    }
    // A DataTable by its name (L"DT_QuestObjectsInfo") or its path (L"/Game/Gameplay/DataTables/Quests/
    // DT_QuestObjectsInfo.DT_QuestObjectsInfo"), when it's in memory; empty when it isn't. By name it looks
    // through the game's objects; by path it doesn't.
    inline auto table(std::wstring_view name_or_path) -> Table
    {
        if (name_or_path.empty() || !assert_game_thread(L"table")) return {};
        if (name_or_path.front() == L'/')
        {
            UObject* o = wcmods::object(std::wstring(name_or_path).c_str());
            return o && is_a(o, STR("/Script/Engine.DataTable")) ? Table(o) : Table();
        }
        for (UObject* o : find_all(STR("DataTable")))
            if (o && wcmods::name(o) == name_or_path) return Table(o);
        return {};
    }

    // ============================================================================================ tuning
    // TuningData.csv: 440 keys (Gameplay.Exploration.MaxLevel, Gameplay.Exploration.Player.MoveAndRun.Run.Speed...)
    // and a number each (its MaxValue column), which the game reads into its components' own members as they
    // start (a loader per part of the game), through one lookup that reads the tuning manager's map each time.
    // A change here is what every later read gets: what read its numbers before keeps them until it reads again
    // (most parts read theirs as they start; when each does wasn't timed).
    namespace detail
    {
        // One of the map's slots: the key (an FString), then the row {vtable, MaxValue float, Description FString},
        // then the hash's links: 0x38 bytes (read in game on build 26337109, docs/reverse-engineering.md, "Tuning").
        struct TuningRow
        {
            std::wstring key;
            float* value{};
            std::wstring description;
        };
        inline auto fstring_at(const uint8_t* at) -> std::wstring
        {
            const auto* text = *reinterpret_cast<const wchar_t* const*>(at);
            const int32_t num = *reinterpret_cast<const int32_t*>(at + 8);
            if (!text || num <= 0 || num > (1 << 16)) return {};
            return std::wstring(text, static_cast<size_t>(num - 1));   // num counts the terminator
        }
        inline auto tuning_rows_in(const uint8_t* map, std::vector<TuningRow>& out) -> bool
        {
            out.clear();
            std::vector<const uint8_t*> slots;
            if (!set_slots(map, 0x38, slots)) return false;
            for (const uint8_t* e : slots)
                out.push_back({fstring_at(e), reinterpret_cast<float*>(const_cast<uint8_t*>(e) + 0x18), fstring_at(e + 0x20)});
            return true;
        }
        inline auto tuning_map() -> uint8_t*
        {
            return member<uint8_t>(manager(STR("tuning")), L"/Script/SwtEngine.SwtTuningManager", L"WCM_TuningData");
        }
        inline auto tuning_rows() -> std::vector<TuningRow>
        {
            std::vector<TuningRow> out;
            tuning_rows_in(tuning_map(), out);
            return out;
        }
        inline auto same_key(std::wstring_view a, std::wstring_view b) -> bool   // the game's FString keys ignore case
        {
            if (a.size() != b.size()) return false;
            for (size_t i = 0; i < a.size(); ++i)
                if (std::towlower(a[i]) != std::towlower(b[i])) return false;
            return true;
        }
        // One key's slot, compared in place (the map's FString against `key`): no string is copied to look.
        inline auto tuning_slot(std::wstring_view key) -> const uint8_t*
        {
            std::vector<const uint8_t*> slots;
            if (!set_slots(tuning_map(), 0x38, slots)) return nullptr;
            for (const uint8_t* e : slots)
            {
                const auto* text = *reinterpret_cast<const wchar_t* const*>(e);
                const int32_t num = *reinterpret_cast<const int32_t*>(e + 8);
                if (text && num == static_cast<int32_t>(key.size()) + 1 && same_key(std::wstring_view(text, key.size()), key)) return e;
            }
            return nullptr;
        }
    } // namespace detail

    // A key's number, as the game's own lookup gives it; nullopt for a key the table hasn't got, or when wcmods
    // hasn't got the tuning manager's map on this build (offsets.json).
    inline auto tuning(std::wstring_view key) -> std::optional<float>
    {
        if (!assert_game_thread(L"tuning")) return std::nullopt;
        const uint8_t* e = detail::tuning_slot(key);
        return e ? std::optional<float>(*reinterpret_cast<const float*>(e + 0x18)) : std::nullopt;
    }
    // Change a key's number: what the game reads from then on (above: not what started before). False for a key
    // the table hasn't got (a key can't be added: the game's code names the ones it reads).
    inline auto set_tuning(std::wstring_view key, float value) -> bool
    {
        if (!assert_game_thread(L"set_tuning")) return false;
        const uint8_t* e = detail::tuning_slot(key);
        if (!e) return false;
        *reinterpret_cast<float*>(const_cast<uint8_t*>(e) + 0x18) = value;
        return true;
    }
    // Every key, in the table's order; and a key's description (its Description column; empty for most).
    inline auto tuning_keys() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        if (!assert_game_thread(L"tuning_keys")) return out;
        for (auto& r : detail::tuning_rows()) out.push_back(r.key);
        return out;
    }
    inline auto tuning_description(std::wstring_view key) -> std::optional<std::wstring>
    {
        if (!assert_game_thread(L"tuning_description")) return std::nullopt;
        const uint8_t* e = detail::tuning_slot(key);
        return e ? std::optional<std::wstring>(detail::fstring_at(e + 0x20)) : std::nullopt;
    }
} // namespace wcmods
