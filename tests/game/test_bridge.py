"""The bridge, the window and the agent's own tools: if these fail, nothing else can be trusted."""
import os

from wcmods.agent import Image

NEEDS = "game"


def test_lua_round_trip(agent):
    """Lua runs in the game and its values come back, several at once too."""
    assert agent.lua("return 6 * 7") == 42
    assert agent.lua("return 'a', true, nil") == ["a", True, None]
    agent.lua("agentTestValue = 5")
    assert agent.lua("return agentTestValue") == 5, "globals should stay for the next call"


def test_lua_errors_come_back(agent):
    from wcmods.agent import LuaError
    try:
        agent.lua("error('on purpose')")
    except LuaError as e:
        assert "on purpose" in str(e)
    else:
        raise AssertionError("a Lua error should raise LuaError")


def test_compile_check(agent):
    """The game's own Lua checks a chunk without running it."""
    assert agent.compile("local x = 1 return x") is None
    err = agent.compile("local x = ", "broken.lua")
    assert err and "broken.lua" in err, err


def test_status(agent):
    st = agent.status()
    assert st["running"] and st["bridge"], st
    assert st["window"] and st["window"][0] > 0 and st["window"][1] > 0, st
    assert not st["crash_reporter"]


def test_picture(agent):
    """A picture of the window isn't blank, and saves and loads as a PNG."""
    img = agent.picture()
    assert not img.blank(), "the capture is one colour (is the game minimised?)"
    path = agent.shot("window", scale=0.5)
    back = Image.load(path)
    assert (back.width, back.height) == (img.width // 2, img.height // 2)
    assert os.path.getsize(path) > 10000
