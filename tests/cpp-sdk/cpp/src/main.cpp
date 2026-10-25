// The C++ SDK's test mod (docs/SDK.md, "C++ mods"): calls everything the SDK documents and records what it
// got in results.json beside this mod, for tests/game/test_cpp_sdk.py to compare with what Lua sees.
//
//   python wcmods.py cpp build tests/cpp-sdk
//   python wcmods.py agent install --with tests/cpp-sdk
//   python wcmods.py agent test tests/game/test_cpp_sdk.py --launch
#include "checks.hpp"

#include <filesystem>
#include <mutex>

namespace t
{
    namespace
    {
        std::mutex lock;
        Json checks = Json::array();
        Json values = Json::object();
        Json finished = Json::array();
        std::string current = "init";
        int passed = 0, failed = 0;
        int served = 0;   // how many phases have finished: the Python side waits for it to grow
    } // namespace

    auto phase(std::string_view name) -> void
    {
        std::lock_guard guard(lock);
        current = name;
    }

    auto done(std::string_view name) -> void
    {
        {
            std::lock_guard guard(lock);
            finished.push(std::string(name));
            served++;
        }
        flush();
    }

    auto expect(std::string_view name, bool ok, std::string detail) -> bool
    {
        std::lock_guard guard(lock);
        Json c = Json::object();
        c.set("phase", current);
        c.set("name", std::string(name));
        c.set("ok", ok);
        c.set("detail", detail);
        checks.push(c);
        (ok ? passed : failed)++;
        if (!ok) log(L"FAIL {}: {}", wide(name), wide(detail));
        return ok;
    }

    auto value(std::string_view name, Json v) -> void
    {
        std::lock_guard guard(lock);
        values.set(name, std::move(v));
    }

    auto flush() -> void
    {
        std::lock_guard guard(lock);
        Json out = Json::object();
        out.set("phase", current);
        out.set("done", finished);
        out.set("served", served);
        out.set("passed", passed);
        out.set("failed", failed);
        out.set("checks", checks);
        out.set("values", values);
        write_file(mod().folder / L"results.json", out.dump(2) + "\n");
    }
} // namespace t

class CppSdkTest : public wcmods::ModBase
{
  public:
    // A mod that overrides on_lua_start calls ModBase's from it, or loses the mod menu and shared values.
    auto on_lua_start(RC::StringViewType mod_name, RC::LuaMadeSimple::Lua& lua, RC::LuaMadeSimple::Lua& main_lua,
                      RC::LuaMadeSimple::Lua& async_lua, RC::LuaMadeSimple::Lua* hook_lua) -> void override
    {
        wcmods::ModBase::on_lua_start(mod_name, lua, main_lua, async_lua, hook_lua);
        t::value("lua_mods_started", ++m_lua_mods);
    }

    auto on_unreal_init() -> void override
    {
        // A fresh results.json each run, so a stale one can't pass for this one.
        std::error_code ec;
        std::filesystem::remove(wcmods::mod().folder / L"results.json", ec);
        t::phase("init");
        t::run_core();
        t::setup_events();
        t::setup_menu();
        t::setup_background();
        t::done("init");
    }

  private:
    int m_lua_mods{};
};

WCMODS_MOD(CppSdkTest)
