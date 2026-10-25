// Core.hpp: text, Json, files, the mod's info and settings, the log, the hidden members' offsets.
#include "checks.hpp"

#include <cmath>
#include <filesystem>
#include <limits>
#include <type_traits>

// A character is text, not a number: Json("x") is a string, and Json('x') doesn't compile.
static_assert(!std::is_constructible_v<wcmods::Json, char>);
static_assert(!std::is_constructible_v<wcmods::Json, wchar_t>);
static_assert(std::is_constructible_v<wcmods::Json, std::size_t>);
static_assert(std::is_constructible_v<wcmods::Json, long>);
static_assert(std::is_constructible_v<wcmods::Json, float>);

namespace t
{
    namespace
    {
        auto core_mod() -> void
        {
            const ModInfo& m = mod();
            expect("mod.found", m.found, "wcmods.json read");
            expect("mod.id", m.id == L"cpp-sdk", text(m.id));
            expect("mod.name", m.name == L"C++ SDK test", text(m.name));
            expect("mod.version", m.version == L"1.0", text(m.version));
            expect("mod.author", m.author == L"wcmods", text(m.author));
            expect("mod.description", m.description.starts_with(L"Calls everything"), text(m.description));
            expect("mod.folder", std::filesystem::is_regular_file(m.folder / L"mod.json"), text(m.folder.wstring()));
            expect("mod.settings_file", m.settings_file.filename() == L"settings.json", text(m.settings_file.wstring()));
            expect("mod.installed", m.installed.filename() == L"WCModsCpp_cpp_sdk"
                                       && std::filesystem::is_regular_file(m.installed / L"dlls" / L"main.dll"),
                  text(m.installed.wstring()));
        }

        auto core_settings() -> void
        {
            Json& s = settings();
            expect("settings.is_object", s.is_object());
            expect("settings.number", s["number"].number() == 1.5, std::to_string(s["number"].number()));
            expect("settings.whole", s["whole"].number() == 7 && s["whole"].is_number());
            expect("settings.text", s["text"].string() == "hi there" && s["text"].wstring() == L"hi there", s["text"].string());
            expect("settings.flag", s["flag"].boolean() && s["flag"].is_bool());
            expect("settings.list", s["list"].is_array() && s["list"].size() == 3 && s["list"][0].number() == 1
                                       && s["list"][1].string() == "two" && s["list"][2].is_bool() && !s["list"][2].boolean());
            expect("settings.nested", s["nested"].is_object() && s["nested"]["k"].string() == "v" && s["nested"].has("k")
                                         && !s["nested"].has("z"));
            expect("settings.missing_is_null", s["nope"].is_null() && s["nope"]["deeper"].is_null() && s["list"][9].is_null());
            expect("settings.fallbacks", s["nope"].number(2.5) == 2.5 && s["nope"].string("x") == "x" && s["nope"].boolean(true)
                                            && s["nope"].wstring(L"w") == L"w" && s["text"].number(9) == 9);
            expect("settings.keys_in_order", s.keys().size() >= 8 && s.keys()[0] == "_help" && s.keys()[1] == "number");
            expect("settings.values", s.values().size() == s.keys().size());
            expect("settings.type", s.type() == Json::Type::Object && s["text"].type() == Json::Type::String);
            expect("settings_lock", settings_lock().try_lock());
            settings_lock().unlock();
        }

        auto core_json() -> void
        {
            std::string why;
            auto parsed = Json::parse(R"({"a": [1, 2.5, -3, 1e3, true, null, "s\"q\\\né🐱"], "b": {"c": {}}, "d": []})", &why);
            expect("json.parse", parsed.has_value(), why);
            if (parsed)
            {
                const Json& j = *parsed;
                expect("json.parse.numbers", j["a"][0].number() == 1 && j["a"][1].number() == 2.5 && j["a"][2].number() == -3
                                                && j["a"][3].number() == 1000);
                expect("json.parse.others", j["a"][4].boolean() && j["a"][5].is_null() && j["b"]["c"].is_object()
                                               && j["b"]["c"].size() == 0 && j["d"].is_array() && j["d"].size() == 0);
                expect("json.parse.escapes", j["a"][6].string() == "s\"q\\\n\xC3\xA9\xF0\x9F\x90\xB1", j["a"][6].string());
                expect("json.dump.one_line", j.dump(0) == R"({"a":[1,2.5,-3,1000,true,null,"s\"q\\\né🐱"],"b":{"c":{}},"d":[]})"
                                                 || j.dump(0) == R"({"a":[1,2.5,-3,1000,true,null,"s\"q\\\n)" "\xC3\xA9\xF0\x9F\x90\xB1" R"("],"b":{"c":{}},"d":[]})",
                      j.dump(0));
                auto again = Json::parse(j.dump(2));
                expect("json.round_trip", again && again->dump(0) == j.dump(0));
                expect("json.dump.indented", j.dump(2).starts_with("{\n  \"a\": [\n    1,"), j.dump(2).substr(0, 20));
            }
            for (auto bad : {"{", "[1,2", "{\"a\" 1}", "nope", "", "{\"a\":1} x", "[1,]"})
            {
                std::string err;
                auto r = Json::parse(bad, &err);
                expect(std::string("json.refuses ") + (*bad ? bad : "(empty)"), !r && !err.empty(), err);
            }
            Json n;
            expect("json.null_default", n.is_null() && n.type() == Json::Type::Null);
            n.set("k", 1);
            expect("json.set_makes_object", n.is_object() && n["k"].number() == 1);
            n.set("k", "v");
            expect("json.set_replaces", n["k"].string() == "v" && n.size() == 1);
            n.set("z", Json::array());
            expect("json.keys_order", n.keys().size() == 2 && n.keys()[0] == "k" && n.keys()[1] == "z");
            Json a;
            a.push(true);
            a.push(Json::object());
            expect("json.push_makes_array", a.is_array() && a.size() == 2 && a[0].boolean() && a[1].is_object());
            Json nums = Json::object();
            nums.set("i", -7);
            nums.set("u", 7u);
            nums.set("z", std::size_t{3});
            nums.set("l", 5L);
            nums.set("f", 1.5f);
            nums.set("d", 2.25);
            nums.set("big", 1e20);
            nums.set("nan", std::numeric_limits<double>::quiet_NaN());
            nums.set("inf", std::numeric_limits<double>::infinity());
            expect("json.numbers_dump", nums.dump(0) == R"({"i":-7,"u":7,"z":3,"l":5,"f":1.5,"d":2.25,"big":1e+20,"nan":null,"inf":null})",
                  nums.dump(0));
            Json s = std::wstring_view(L"wide é");
            expect("json.from_wide", s.is_string() && s.string() == "wide \xC3\xA9" && s.wstring() == L"wide é");
            expect("json.from_bool_and_null", Json(true).is_bool() && Json(nullptr).is_null() && Json("c").is_string());
        }

        auto core_text() -> void
        {
            std::string u8 = "S\xC3\xB6hne \xF0\x9F\x90\xB1";
            expect("text.round_trip", utf8(wide(u8)) == u8 && wide(u8) == L"Söhne \U0001F431");
            expect("text.empty", wide("").empty() && utf8(L"").empty());
        }

        auto core_files() -> void
        {
            auto path = mod().folder / L"written.txt";
            std::string body = "line one\nS\xC3\xB6hne \xF0\x9F\x90\xB1\n";
            expect("files.write", write_file(path, body));
            auto back = read_file(path);
            expect("files.read", back && *back == body, back ? *back : "(none)");
            expect("files.read_missing", !read_file(mod().folder / L"not-there.txt"));
            auto bom = mod().folder / L"bom.txt";
            write_file(bom, "\xEF\xBB\xBF{\"x\": 1}");
            auto b = read_file(bom);
            expect("files.read_strips_bom", b && *b == "{\"x\": 1}", b ? *b : "(none)");
            expect("files.write_refused", !write_file(mod().folder / L"no-such-folder" / L"x.txt", "x"));
        }

        auto core_offsets() -> void
        {
            auto value_off = offset(L"/Script/SwtQuest.SwtQuestResourceComponent", L"WCM_Value");
            auto max_off = offset(L"/Script/SwtQuest.SwtQuestResourceComponent", L"WCM_Max");
            auto level_off = offset(L"/Script/SwtAdventure.SwtAdventureLevelComponent", L"WCM_Level");
            expect("offset.known", value_off && max_off && level_off && *max_off == *value_off + 4);
            expect("offset.unknown", !offset(L"/Script/SwtQuest.SwtQuestResourceComponent", L"WCM_Nope")
                                        && !offset(L"/Script/Nope.Nope", L"WCM_Value"));
            value("offset.WCM_Value", value_off ? Json(*value_off) : Json());
            value("offset.WCM_Level", level_off ? Json(*level_off) : Json());
            expect("member.null_object", member<float>(nullptr, L"/Script/SwtQuest.SwtQuestResourceComponent", L"WCM_Value") == nullptr);
        }
    } // namespace

    auto run_core() -> void
    {
        core_mod();
        core_settings();
        core_json();
        core_text();
        core_files();
        core_offsets();
        log(L"hello {} {}", 42, L"wide");   // the Python side looks for this line
        expect("log", true);
    }
} // namespace t
