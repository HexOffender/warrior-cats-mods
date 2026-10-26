"""WCModsView: a shared UE4SS Lua module with what the player's camera sees, for overlays.

Installed as ue4ss/Mods/shared/WCModsView/WCModsView.lua whenever wcmods installs into UE4SS, so any
UE4SS script (wcmods' own, a mod's section.py, or one written by hand) can `require("WCModsView")` and
turn world positions into screen positions. See docs/SDK.md, "Overlays".
"""
from .lua import source as lua_source

SHARED_NAME = "WCModsView"
NEAR_PLANE = 10.0   # Unreal's near clipping plane (r.SetNearClipPlane), in centimetres

LUA = lua_source("view.lua")


def lua():
    return LUA.replace("@NEAR_PLANE@", repr(NEAR_PLANE))
