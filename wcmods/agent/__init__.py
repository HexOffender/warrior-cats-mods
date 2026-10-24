"""The agent controller: drive the running game from Python or the command line, to test mods and the
SDK in it and see the results (`python wcmods.py agent ...`; docs/agent.md).

    from wcmods.agent import Agent
    agent = Agent(root)
    agent.launch(world=True)
    agent.menu.open("Stats").get("Name")
    agent.shot("stats")

controller.py has the Agent, menu.py drives the mod menu, window.py the game's window (pictures, keys),
image.py the pictures, runner.py runs tests/game and writes its report.
"""
from .controller import Agent, AgentError, BridgeDown, LuaError
from .image import Image
from .runner import Skip, skip

__all__ = ["Agent", "AgentError", "BridgeDown", "LuaError", "Image", "Skip", "skip"]
