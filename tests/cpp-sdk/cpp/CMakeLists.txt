# The C++ SDK's test mod: `python wcmods.py cpp build tests/cpp-sdk`. One file a header of the SDK.
wcmods_mod(${WCMODS_TARGET}
    src/main.cpp
    src/test_core.cpp
    src/test_game.cpp
    src/test_events.cpp
)
