"""wcmods' in-game Lua, as files: the shared modules (game.lua is WCModsGame, menu.lua WCModsMenu, draw,
world and view theirs), the mod menu's host script and its pages, and the scripts the sections write for
mods (palettes, your cat's colours, mouse look, the play state, a script mod's bootstrap). The Python module
beside each one reads it with source() and fills its @TOKENS@ in; nothing here runs outside the game."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def source(name):
    """The text of one of these files, as it is."""
    with open(os.path.join(HERE, name), encoding="utf-8", newline="") as f:
        return f.read()
