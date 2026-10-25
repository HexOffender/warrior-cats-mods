# wcmods' C++ SDK for `wcmods cpp build` (wcmods/cppmods.py includes this in the project it writes).
#
# A mod's cpp/CMakeLists.txt calls wcmods_mod with its target (WCMODS_TARGET, set by wcmods) and sources:
#
#     wcmods_mod(${WCMODS_TARGET}
#         src/main.cpp
#     )
#
# It makes the mod's main.dll, linked against UE4SS, with WCMods.hpp and the mod's own src/ on the include
# path. Anything else CMake can do (more sources, FetchContent, target_link_libraries) works after it.
# docs/SDK.md, "C++ mods".
set(WCMODS_SDK_DIR "${CMAKE_CURRENT_LIST_DIR}")

function(wcmods_mod target)
    add_library(${target} SHARED ${ARGN})
    target_include_directories(${target} PRIVATE "${WCMODS_SDK_DIR}/include" "${CMAKE_CURRENT_SOURCE_DIR}/src")
    target_link_libraries(${target} PUBLIC UE4SS)
    set_target_properties(${target} PROPERTIES
        OUTPUT_NAME main
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/wcmods/${target}")
endfunction()
