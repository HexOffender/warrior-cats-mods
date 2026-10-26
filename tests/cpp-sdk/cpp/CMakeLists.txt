# The C++ SDK's test mod: `python wcmods.py cpp build tests/cpp-sdk`. One file a header of the SDK.
wcmods_mod(${WCMODS_TARGET}
    src/main.cpp
    src/test_core.cpp
    src/test_game.cpp
    src/test_events.cpp
    src/test_menu.cpp
    src/test_reflect.cpp
    src/test_world.cpp
    src/test_ui.cpp
)
