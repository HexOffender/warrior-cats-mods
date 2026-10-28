"""Your cat through WCModsGame (docs/scripting.md), and moving it."""
import importlib.util
import os

from wcmods.agent import skip
from wcmods.exe import pe

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _distance(a, b):
    return sum((p - q) ** 2 for p, q in zip(a, b)) ** 0.5


def named(cat):
    """Whether a cat's name can be read: one that a names mod gave it ("STR_CAT_NAME_WCM...") has no text in
    a test install without that mod, in the game either."""
    return bool(cat.get("name")) or str(cat.get("nameId", "")).startswith("STR_CAT_NAME_WCM")


def test_cat_reads(agent):
    c = agent.cat()
    assert c, "no cat"
    assert named(c) and c["clan"], c
    assert 1 <= c["level"] <= 20, c
    assert 0 < c["health"] <= c["maxHealth"], c
    assert 0 <= c["stamina"] <= c["maxStamina"], c


def test_health_round_trip(agent):
    """Setting health shows straight away; healing fills it."""
    full = agent.lua("return Game.cat():maxHealth()")
    try:
        agent.lua(f"Game.cat():setHealth({full // 2})")
        assert agent.lua("return Game.cat():health()") == full // 2
    finally:
        agent.lua("Game.cat():heal()")
    assert agent.lua("return Game.cat():health()") == full


def test_walk_with_lua(agent):
    """Movement input from Lua walks the cat, whatever window is in front."""
    start = agent.location()
    try:
        went = agent.move(forward=1, seconds=1.5)
        assert went > 50, f"only moved {went:.0f} cm"
    finally:
        agent.teleport(*start)


def test_walk_with_a_key(agent):
    """A key posted to the window walks the cat, the way a player's does. S walks towards the camera,
    the way that's usually open."""
    start = agent.location()
    try:
        agent.key("S", hold=1.5)
        went = _distance(agent.location(), start)
        assert went > 50, f"only moved {went:.0f} cm"
    finally:
        agent.teleport(*start)


def test_teleport(agent):
    start = agent.location()
    try:
        agent.teleport(start[0] + 300, start[1], start[2] + 50)
        now = agent.location()
        assert abs(now[0] - (start[0] + 300)) < 60, (start, now)
    finally:
        agent.teleport(*start)


def _exe_enums(agent, names):
    """The installed exe's enums, {enum: {name: value}} in each table's order, read with tools/re/uht.py as
    `uht.py <exe> lua` reads them: what the game's own enums should give in game, whatever the build."""
    exe_path = pe.game_exe(agent.cfg)
    if not exe_path:
        skip("the game's exe isn't found")
    spec = importlib.util.spec_from_file_location("wcmods_uht", os.path.join(REPO, "tools", "re", "uht.py"))
    uht = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uht)
    exe = uht.Exe(exe_path)
    return {name: uht.enum_values(exe, name) for name in names}


# Each Game.enums table as the bridge's Lua state sees it: its names, its numbers' names, # and whether it has the
# game's own numbers (its metatable's fromGame) rather than build 26184573's fallback.
ENUMS_LUA = """
local out = {}
for key, e in pairs(Game.enums) do
    local names, numbers = {}, {}
    for k, v in pairs(e) do
        if type(k) == "string" then names[k] = v else numbers[tostring(k)] = v end
    end
    local mt = getmetatable(e)
    out[key] = { names = names, numbers = numbers, length = #e, fromGame = mt ~= nil and mt.fromGame == true }
end
return out
"""


def test_enums_are_read_from_the_game(agent):
    """Game.enums' numbers come from the game's own enums, by name (docs/reverse-engineering.md, "The game's
    enums"): every enum wcmods/game.py ENUMS names is at its path and gives the installed exe's names and numbers,
    in order, and so do ECommands (the Talk prompt's Interact) and EGuiConsolesTypes (the in-game remap's UI_PC);
    the engine's <Enum>_MAX is there in game but left out; a missing enum is nil, not a crash; and each
    Game.enums table holds the game's numbers, not build 26184573's fallback."""
    from wcmods import game
    paths = {key: path for key, path, _ in game.ENUMS}
    paths["(ECommands)"] = "/Script/SwtEngine.ECommands"
    paths["(EGuiConsolesTypes)"] = "/Script/SwtEngine.EGuiConsolesTypes"
    exe = _exe_enums(agent, {path.rsplit(".", 1)[-1] for path in paths.values()})
    for key, path in paths.items():
        want = exe[path.rsplit(".", 1)[-1]]
        assert want, f"the exe has no table for {path}"
        got = agent.lua(f'local byName, order = Game.enumNames("{path}") return {{ byName = byName, order = order }}')
        assert got == {"byName": want, "order": list(want)}, key
    assert agent.lua('return Game.enumNames("/Script/SwtEngine.ENoSuchEnum") == nil') is True
    # The engine adds EClanType_MAX to the enum in game (the class dump taken in game on 24847281 lists it):
    # Game.enumNames leaves it out, above.
    last = agent.lua("local e = Game.object('/Script/SwtQuest.EClanType') if not e then return nil end local last "
                     "pcall(function() e:ForEachName(function(k) pcall(function() last = k:ToString() end) end) end) "
                     "return last")
    assert str(last).endswith("EClanType_MAX"), last
    got = agent.lua(ENUMS_LUA)
    assert set(got) == {k for k, _, _ in game.ENUMS}
    for key, path, _ in game.ENUMS:
        want = exe[path.rsplit(".", 1)[-1]]
        numbers = {}
        for name, n in want.items():
            numbers.setdefault(str(n), name)   # a number with two names: the first
        e = got[key]
        assert e["fromGame"] is True, f"Game.enums.{key} has build 26184573's numbers, not the game's"
        assert e["names"] == want and e["numbers"] == numbers, key
        if set(want.values()) == set(range(len(want))):   # numbered 0..n, so # is n (with gaps it could be any border)
            assert e["length"] == len(want) - 1, key
