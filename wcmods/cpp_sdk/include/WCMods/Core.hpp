// WCMods/Core.hpp: the part of wcmods' C++ SDK that doesn't touch the game: text, JSON, files, the mod's
// own info and settings, logging, and where the game's hidden members sit on this build. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstdio>
#include <exception>
#include <filesystem>
#include <format>
#include <fstream>
#include <functional>
#include <memory>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <type_traits>
#include <vector>

#include <DynamicOutput/DynamicOutput.hpp>
#include <Unreal/Core/Windows/WindowsHWrapper.hpp>
#include <Unreal/UObject.hpp>

namespace wcmods
{
    using RC::Unreal::UObject;

    // ============================================================================================ text
    // The game and UE4SS use wide strings; wcmods' JSON files are UTF-8.
    inline auto wide(std::string_view utf8) -> std::wstring
    {
        if (utf8.empty()) return {};
        int n = MultiByteToWideChar(CP_UTF8, 0, utf8.data(), static_cast<int>(utf8.size()), nullptr, 0);
        std::wstring out(static_cast<size_t>(n), L'\0');
        MultiByteToWideChar(CP_UTF8, 0, utf8.data(), static_cast<int>(utf8.size()), out.data(), n);
        return out;
    }

    inline auto utf8(std::wstring_view text) -> std::string
    {
        if (text.empty()) return {};
        int n = WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
        std::string out(static_cast<size_t>(n), '\0');
        WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), out.data(), n, nullptr, nullptr);
        return out;
    }

    // ============================================================================================ JSON
    // A JSON value, for settings.json and the files wcmods writes beside the mod. Reading a key or index
    // that isn't there gives null, so settings()["speed"].number(1.0) never throws.
    class Json
    {
      public:
        enum class Type { Null, Bool, Number, String, Array, Object };

        Json() = default;
        Json(std::nullptr_t) {}
        Json(bool v) : m_type(Type::Bool), m_bool(v) {}
        // Any number: int, size_t, float, double...
        template <typename T>
            requires(std::is_arithmetic_v<T> && !std::is_same_v<T, bool>)
        Json(T v) : m_type(Type::Number), m_number(static_cast<double>(v)) {}
        Json(std::string v) : m_type(Type::String), m_string(std::move(v)) {}
        Json(const char* v) : m_type(Type::String), m_string(v) {}
        Json(std::wstring_view v) : m_type(Type::String), m_string(utf8(v)) {}

        static auto array() -> Json { Json j; j.m_type = Type::Array; return j; }
        static auto object() -> Json { Json j; j.m_type = Type::Object; return j; }

        auto type() const -> Type { return m_type; }
        auto is_null() const -> bool { return m_type == Type::Null; }
        auto is_bool() const -> bool { return m_type == Type::Bool; }
        auto is_number() const -> bool { return m_type == Type::Number; }
        auto is_string() const -> bool { return m_type == Type::String; }
        auto is_array() const -> bool { return m_type == Type::Array; }
        auto is_object() const -> bool { return m_type == Type::Object; }

        // The value, or `fallback` when it's another type.
        auto boolean(bool fallback = false) const -> bool { return is_bool() ? m_bool : fallback; }
        auto number(double fallback = 0.0) const -> double { return is_number() ? m_number : fallback; }
        auto string(std::string fallback = {}) const -> std::string { return is_string() ? m_string : fallback; }
        auto wstring(std::wstring fallback = {}) const -> std::wstring { return is_string() ? wide(m_string) : fallback; }

        // Arrays and objects: their size, an element, a key's value (null when it isn't there).
        auto size() const -> size_t { return m_values.size(); }
        auto operator[](size_t i) const -> const Json& { return i < m_values.size() ? m_values[i] : null_value(); }
        auto operator[](std::string_view key) const -> const Json&
        {
            for (size_t i = 0; i < m_keys.size(); ++i)
                if (m_keys[i] == key) return m_values[i];
            return null_value();
        }
        auto has(std::string_view key) const -> bool
        {
            return std::find(m_keys.begin(), m_keys.end(), key) != m_keys.end();
        }
        auto keys() const -> const std::vector<std::string>& { return m_keys; }
        auto values() const -> const std::vector<Json>& { return m_values; }

        // Set a key (an object; a null value becomes one), keeping the keys' order.
        auto set(std::string_view key, Json value) -> Json&
        {
            if (is_null()) m_type = Type::Object;
            for (size_t i = 0; i < m_keys.size(); ++i)
                if (m_keys[i] == key) return m_values[i] = std::move(value);
            m_keys.emplace_back(key);
            m_values.push_back(std::move(value));
            return m_values.back();
        }
        // Add an element (an array; a null value becomes one).
        auto push(Json value) -> Json&
        {
            if (is_null()) m_type = Type::Array;
            m_values.push_back(std::move(value));
            return m_values.back();
        }

        // Parse JSON text; nullopt (and why, in `error`) when it isn't JSON.
        static auto parse(std::string_view text, std::string* error = nullptr) -> std::optional<Json>
        {
            Parser p{text};
            try
            {
                p.space();
                Json value = p.value(0);
                p.space();
                if (p.at < text.size()) p.fail("text after the value");
                return value;
            }
            catch (const std::exception& e)
            {
                if (error) *error = e.what();
                return std::nullopt;
            }
        }

        // The value as JSON text: indented by `indent` spaces a level, or on one line with 0.
        auto dump(int indent = 2) const -> std::string
        {
            std::string out;
            write(out, indent, 0);
            return out;
        }

      private:
        Type m_type{Type::Null};
        bool m_bool{};
        double m_number{};
        std::string m_string;
        std::vector<std::string> m_keys;   // an object's keys, in order, beside their values
        std::vector<Json> m_values;        // an array's elements, or an object's values

        static auto null_value() -> const Json&
        {
            static const Json null;
            return null;
        }

        struct Parser
        {
            std::string_view text;
            size_t at{};

            [[noreturn]] auto fail(const char* what) const -> void
            {
                throw std::runtime_error(std::format("{} at character {}", what, at + 1));
            }
            auto space() -> void
            {
                while (at < text.size() && (text[at] == ' ' || text[at] == '\t' || text[at] == '\n' || text[at] == '\r')) ++at;
            }
            auto take(std::string_view word) -> bool
            {
                if (text.substr(at, word.size()) != word) return false;
                at += word.size();
                return true;
            }
            auto hex4() -> unsigned
            {
                if (at + 4 > text.size()) fail("a short \\u escape");
                unsigned v{};
                auto [end, ec] = std::from_chars(text.data() + at, text.data() + at + 4, v, 16);
                if (ec != std::errc{} || end != text.data() + at + 4) fail("a bad \\u escape");
                at += 4;
                return v;
            }
            auto string() -> std::string
            {
                std::string out;
                ++at;   // the opening quote
                while (true)
                {
                    if (at >= text.size()) fail("an unfinished string");
                    char c = text[at++];
                    if (c == '"') return out;
                    if (c != '\\')
                    {
                        out += c;
                        continue;
                    }
                    if (at >= text.size()) fail("an unfinished string");
                    switch (char e = text[at++])
                    {
                    case '"': case '\\': case '/': out += e; break;
                    case 'b': out += '\b'; break;
                    case 'f': out += '\f'; break;
                    case 'n': out += '\n'; break;
                    case 'r': out += '\r'; break;
                    case 't': out += '\t'; break;
                    case 'u':
                    {
                        unsigned cp = hex4();
                        if (cp >= 0xD800 && cp < 0xDC00 && take("\\u"))
                        {
                            unsigned low = hex4();
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00);
                        }
                        if (cp < 0x80) out += static_cast<char>(cp);
                        else if (cp < 0x800) out += {static_cast<char>(0xC0 | cp >> 6), static_cast<char>(0x80 | (cp & 0x3F))};
                        else if (cp < 0x10000)
                            out += {static_cast<char>(0xE0 | cp >> 12), static_cast<char>(0x80 | (cp >> 6 & 0x3F)),
                                    static_cast<char>(0x80 | (cp & 0x3F))};
                        else
                            out += {static_cast<char>(0xF0 | cp >> 18), static_cast<char>(0x80 | (cp >> 12 & 0x3F)),
                                    static_cast<char>(0x80 | (cp >> 6 & 0x3F)), static_cast<char>(0x80 | (cp & 0x3F))};
                        break;
                    }
                    default: fail("a bad escape");
                    }
                }
            }
            auto value(int depth) -> Json
            {
                if (depth > 200) fail("too much nesting");
                if (at >= text.size()) fail("a missing value");
                char c = text[at];
                if (c == '"') return Json(string());
                if (c == '{')
                {
                    Json obj = Json::object();
                    ++at;
                    space();
                    if (take("}")) return obj;
                    while (true)
                    {
                        space();
                        if (at >= text.size() || text[at] != '"') fail("a key that isn't a string");
                        std::string key = string();
                        space();
                        if (!take(":")) fail("a missing ':'");
                        space();
                        obj.set(key, value(depth + 1));
                        space();
                        if (take("}")) return obj;
                        if (!take(",")) fail("a missing ',' or '}'");
                    }
                }
                if (c == '[')
                {
                    Json arr = Json::array();
                    ++at;
                    space();
                    if (take("]")) return arr;
                    while (true)
                    {
                        space();
                        arr.push(value(depth + 1));
                        space();
                        if (take("]")) return arr;
                        if (!take(",")) fail("a missing ',' or ']'");
                    }
                }
                if (take("true")) return Json(true);
                if (take("false")) return Json(false);
                if (take("null")) return Json();
                double v{};
                auto [end, ec] = std::from_chars(text.data() + at, text.data() + text.size(), v);
                if (ec != std::errc{} || end == text.data() + at) fail("something that isn't JSON");
                at = static_cast<size_t>(end - text.data());
                return Json(v);
            }
        };

        static auto quote(std::string& out, std::string_view s) -> void
        {
            out += '"';
            for (char c : s)
            {
                switch (c)
                {
                case '"': out += "\\\""; break;
                case '\\': out += "\\\\"; break;
                case '\n': out += "\\n"; break;
                case '\r': out += "\\r"; break;
                case '\t': out += "\\t"; break;
                default:
                    if (static_cast<unsigned char>(c) < 0x20) out += std::format("\\u{:04x}", static_cast<int>(c));
                    else out += c;
                }
            }
            out += '"';
        }

        auto write(std::string& out, int indent, int level) const -> void
        {
            auto newline = [&](int lvl) {
                if (indent > 0) out += '\n' + std::string(static_cast<size_t>(indent * lvl), ' ');
            };
            switch (m_type)
            {
            case Type::Null: out += "null"; break;
            case Type::Bool: out += m_bool ? "true" : "false"; break;
            case Type::Number:
                if (!std::isfinite(m_number))
                    out += "null";   // JSON has no NaN or infinity
                else if (m_number == static_cast<double>(static_cast<long long>(m_number)) && m_number > -1e15 && m_number < 1e15)
                    out += std::to_string(static_cast<long long>(m_number));
                else
                    out += std::format("{}", m_number);
                break;
            case Type::String: quote(out, m_string); break;
            case Type::Array:
            case Type::Object:
            {
                bool obj = m_type == Type::Object;
                out += obj ? '{' : '[';
                for (size_t i = 0; i < m_values.size(); ++i)
                {
                    if (i) out += ',';
                    newline(level + 1);
                    if (obj)
                    {
                        quote(out, m_keys[i]);
                        out += indent > 0 ? ": " : ":";
                    }
                    m_values[i].write(out, indent, level + 1);
                }
                if (!m_values.empty()) newline(level);
                out += obj ? '}' : ']';
                break;
            }
            }
        }
    };

    // ============================================================================================ files
    inline auto read_file(const std::filesystem::path& path) -> std::optional<std::string>
    {
        std::ifstream f(path, std::ios::binary);
        if (!f) return std::nullopt;
        std::ostringstream s;
        s << f.rdbuf();
        std::string text = s.str();
        if (text.starts_with("\xEF\xBB\xBF")) text.erase(0, 3);   // a byte order mark
        return text;
    }

    // Write a file whole: to a temporary file first, then over the old one, so a crash never leaves half.
    inline auto write_file(const std::filesystem::path& path, std::string_view text) -> bool
    {
        auto tmp = path;
        tmp += L".tmp";
        {
            std::ofstream f(tmp, std::ios::binary | std::ios::trunc);
            if (!f) return false;
            f.write(text.data(), static_cast<std::streamsize>(text.size()));
            if (!f) return false;
        }
        std::error_code ec;
        std::filesystem::rename(tmp, path, ec);
        return !ec;
    }

    // ============================================================================================ the mod
    // Who this mod is, from the wcmods.json wcmods writes beside its main.dll on every install.
    struct ModInfo
    {
        std::wstring id;              // its folder's name in mods/
        std::wstring name;            // mod.json's "name"
        std::wstring version;         // mod.json's "version"
        std::wstring author;          // mod.json's "author"
        std::wstring description;     // mod.json's "description"
        std::filesystem::path folder;          // the mod's folder in mods/
        std::filesystem::path settings_file;   // its settings.json, or empty without one
        std::filesystem::path installed;       // where UE4SS runs it from: ue4ss/Mods/WCModsCpp_<id>/
        bool found{};                 // false when wcmods.json wasn't there (a DLL put in by hand)
    };

    namespace detail
    {
        inline auto this_dll() -> std::filesystem::path
        {
            HMODULE module{};
            GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               reinterpret_cast<LPCWSTR>(&this_dll), &module);
            std::wstring path(MAX_PATH, L'\0');
            while (true)
            {
                DWORD n = GetModuleFileNameW(module, path.data(), static_cast<DWORD>(path.size()));
                if (n < path.size())
                {
                    path.resize(n);
                    return path;
                }
                path.resize(path.size() * 2);
            }
        }

        struct State
        {
            ModInfo info;
            Json settings = Json::object();
            std::mutex settings_lock;
            std::optional<Json> offsets;   // Mods/shared/WCModsGame/offsets.json, read on first use
            std::mutex offsets_lock;
        };

        inline auto log_line(std::wstring_view name, std::wstring_view text) -> void
        {
            RC::Output::send(STR("[{}] {}\n"), std::wstring(name), std::wstring(text));
        }

        inline auto state() -> State&
        {
            static State st;
            static std::once_flag loaded;
            std::call_once(loaded, [] {
                auto dll = this_dll();
                st.info.installed = dll.parent_path().parent_path();   // .../WCModsCpp_<id>/dlls/main.dll
                st.info.id = st.info.name = st.info.installed.filename().wstring();
                auto text = read_file(st.info.installed / L"wcmods.json");
                std::string why;
                auto data = text ? Json::parse(*text, &why) : std::nullopt;
                if (data && data->is_object())
                {
                    const Json& d = *data;
                    st.info.found = true;
                    st.info.id = d["id"].wstring(st.info.id);
                    st.info.name = d["name"].wstring(st.info.id);
                    st.info.version = d["version"].wstring();
                    st.info.author = d["author"].wstring();
                    st.info.description = d["description"].wstring();
                    st.info.folder = d["folder"].wstring();
                    st.info.settings_file = d["settings_file"].wstring();
                    if (d["settings"].is_object()) st.settings = d["settings"];
                }
                else if (text)
                {
                    log_line(st.info.name, std::format(L"wcmods.json isn't readable ({})", wide(why)));
                }
                // settings.json as it is now, so what save_settings() wrote last time is still there after the
                // game restarts; the copy from the install when it can't be read.
                if (!st.info.settings_file.empty())
                {
                    if (auto now = read_file(st.info.settings_file))
                    {
                        auto parsed = Json::parse(*now, &why);
                        if (parsed && parsed->is_object()) st.settings = std::move(*parsed);
                        else log_line(st.info.name, std::format(L"couldn't read settings.json ({}); using the settings "
                                                                L"from the install", wide(why)));
                    }
                }
            });
            return st;
        }
    } // namespace detail

    inline auto mod() -> const ModInfo& { return detail::state().info; }

    // ============================================================================================ log
    // A line in UE4SS.log (and its consoles), starting with the mod's name:
    //   wcmods::log(L"{} cats nearby", count);
    template <typename... Args>
    auto log(std::wformat_string<Args...> fmt, Args&&... args) -> void
    {
        detail::log_line(mod().name, std::format(fmt, std::forward<Args>(args)...));
    }

    namespace detail
    {
        // Run a callback, keeping an exception in it from reaching the game (which would close it).
        template <typename Fn>
        auto guarded(const wchar_t* what, Fn&& fn) -> void
        {
            try
            {
                fn();
            }
            catch (const std::exception& e)
            {
                log_line(mod().name, std::format(L"error in {}: {}", what, wide(e.what())));
            }
            catch (...)
            {
                log_line(mod().name, std::format(L"error in {}", what));
            }
        }
    } // namespace detail

    // ============================================================================================ settings
    // settings.json (an empty object without one). Change it while you play, and save_settings() writes it
    // back, so the next install starts with it. Use it from one thread at a time, or hold settings_lock().
    inline auto settings() -> Json& { return detail::state().settings; }
    inline auto settings_lock() -> std::mutex& { return detail::state().settings_lock; }

    // Write settings() back to the mod's settings.json. False when the mod has none or it can't be written.
    inline auto save_settings() -> bool
    {
        auto& s = detail::state();
        if (s.info.settings_file.empty()) return false;
        std::string text;
        {
            std::lock_guard lock(s.settings_lock);
            text = s.settings.dump(2) + "\n";
        }
        return write_file(s.info.settings_file, text);
    }

    // ============================================================================================ the game's hidden members
    // Much of the game's own state isn't reflected, so UE4SS can't see it by name: your cat's health and
    // stamina, level and stats, the clock. wcmods knows where those members sit in their objects for the
    // installed game build, and writes them on every install (Mods/shared/WCModsGame/offsets.json, the same
    // ones WCModsGame's Lua uses: wcmods/game.py's HIDDEN lists them).
    //   wcmods::offset(L"/Script/SwtQuest.SwtQuestResourceComponent", L"WCM_Value")   -> 0x10C
    // nullopt when wcmods hasn't got it for this build (a game update moved it where wcmods can't find it).
    inline auto offset(std::wstring_view cls, std::wstring_view member) -> std::optional<int32_t>
    {
        auto& s = detail::state();
        std::lock_guard lock(s.offsets_lock);
        if (!s.offsets)
        {
            auto text = read_file(s.info.installed.parent_path() / L"shared" / L"WCModsGame" / L"offsets.json");
            auto parsed = text ? Json::parse(*text) : std::nullopt;
            s.offsets = parsed ? std::move(*parsed) : Json::object();
            if (!parsed) detail::log_line(s.info.name, L"Mods/shared/WCModsGame/offsets.json isn't there; install again with wcmods");
        }
        const Json& found = (*s.offsets)["members"][utf8(cls) + ":" + utf8(member)]["offset"];
        if (!found.is_number() || found.number() <= 0) return std::nullopt;
        return static_cast<int32_t>(found.number());
    }

    // A pointer to that member inside `object`, or nullptr (no object, or no offset on this build):
    //   float* value = wcmods::member<float>(component, L"/Script/SwtQuest.SwtQuestResourceComponent", L"WCM_Value");
    template <typename T>
    auto member(UObject* object, std::wstring_view cls, std::wstring_view member_name) -> T*
    {
        if (!object) return nullptr;
        auto at = offset(cls, member_name);
        if (!at) return nullptr;
        return reinterpret_cast<T*>(reinterpret_cast<uint8_t*>(object) + *at);
    }
} // namespace wcmods
