// A C++ mod: keeps your cat's stamina full while settings.json's "full_stamina" is on. WCMods.hpp is wcmods'
// C++ SDK on top of UE4SS's; docs/SDK.md, "C++ mods", has every call. Needs "allow_code_mods": true in
// wcmods.json; `python wcmods.py cpp build <this mod>`, then install.
#include <WCMods/WCMods.hpp>

class MyCppMod : public wcmods::ModBase
{
  public:
    auto on_unreal_init() -> void override
    {
        wcmods::log(L"loaded (full stamina: {})", wcmods::settings()["full_stamina"].boolean(true));

        // Looking up your cat goes through the game's objects, so it's done four times a second, not every frame.
        wcmods::every_frame([waited = 0.0f](float dt) mutable {
            waited += dt;
            if (waited < 0.25f) return;
            waited = 0.0f;
            if (!wcmods::settings()["full_stamina"].boolean(true)) return;
            if (auto stamina = wcmods::stamina(wcmods::player())) *stamina.value = *stamina.max;
        });
    }
};

WCMODS_MOD(MyCppMod)
