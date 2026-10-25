# This mod's C++: `python wcmods.py cpp build <this mod>` builds it into dlls/main.dll. wcmods_mod (from
# wcmods/cpp_sdk/WCMods.cmake) makes the DLL, linked against UE4SS, with WCMods.hpp on the include path. Add
# your .cpp files to its list. docs/SDK.md, "C++ mods".
wcmods_mod(${WCMODS_TARGET}
    src/main.cpp
)
