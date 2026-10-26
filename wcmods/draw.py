"""WCModsDraw: a shared UE4SS Lua module that draws text and 2D shapes on screen.

For custom menus, debug text and world markers (with WCModsView). Installed next to WCModsView as
ue4ss/Mods/shared/WCModsDraw/WCModsDraw.lua; see docs/SDK.md, "Overlays".

It draws with the game's own UI system (UMG): one widget on the viewport holding a canvas, with text
blocks and images kept in pools. Painters say what to draw each frame; an element only gets a call
into the game when something about it changed, and elements a frame didn't use are hidden.
"""
from .lua import source as lua_source

SHARED_NAME = "WCModsDraw"

LUA = lua_source("draw.lua")


def lua():
    return LUA
