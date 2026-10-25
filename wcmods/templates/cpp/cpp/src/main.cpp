// A C++ mod: keeps your cat's stamina full while settings.json's "full_stamina" is on, and heals it on F7.
// WCMods.hpp is wcmods' C++ SDK on top of UE4SS's; docs/SDK.md, "C++ mods", has every call. Needs
// "allow_code_mods": true in wcmods.json; `python wcmods.py cpp build <this mod>`, then install.
#include <WCMods/WCMods.hpp>

class MyCppMod : public wcmods::ModBase
{
  public:
    auto on_unreal_init() -> void override
    {
        wcmods::log(L"loaded (full stamina: {})", wcmods::settings()["full_stamina"].boolean(true));

        // Four times a second (looking up your cat goes through the game's objects, so not every frame).
        wcmods::every(0.25, [] {
            if (!wcmods::settings()["full_stamina"].boolean(true)) return;
            if (auto stamina = wcmods::cat().stamina()) *stamina.value = *stamina.max;
        });

        wcmods::on_key(wcmods::Key::F7, [] {
            if (wcmods::cat().heal()) wcmods::log(L"healed");
        });

        wcmods::on_player([](wcmods::UObject* cat) {
            if (auto level = wcmods::Cat{cat}.level()) wcmods::log(L"your cat is here, level {}", *level);
        });
    }
};

WCMODS_MOD(MyCppMod)
