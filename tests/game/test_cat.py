"""Your cat through WCModsGame (docs/scripting.md), and moving it."""


def _distance(a, b):
    return sum((p - q) ** 2 for p, q in zip(a, b)) ** 0.5


def test_cat_reads(agent):
    c = agent.cat()
    assert c, "no cat"
    assert c["name"] and c["clan"], c
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
