"""The agent controller: drive the running game from Python or the command line, to test mods and the
SDK in it and see the results (`python wcmods.py agent ...`; docs/agent.md).

    from wcmods.agent import Agent
    agent = Agent(root)
    agent.launch(world=True)
    agent.menu.open("Stats").get("Name")
    agent.shot("stats")

controller.py has the Agent, menu.py drives the mod menu, window.py the game's window (pictures, keys),
image.py the pictures, runner.py runs tests/game and writes its report.

The names below are imported on first use: window.py loads user32 as it's imported, so importing the
package (for menu.py, say, which needs no window) works off Windows too.
"""
__all__ = ["Agent", "AgentError", "BridgeDown", "LuaError", "Image", "Skip", "skip"]
_WHERE = {"Agent": "controller", "AgentError": "controller", "BridgeDown": "controller", "LuaError": "controller",
          "Image": "image", "Skip": "runner", "skip": "runner"}


def __getattr__(name):
    if name in _WHERE:
        import importlib
        return getattr(importlib.import_module(f".{_WHERE[name]}", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
