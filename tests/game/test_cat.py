"""Your cat through WCModsGame (docs/scripting.md), and moving it."""


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


def test_enums_are_read_from_the_game(agent):
    """Game.enums' numbers come from the game's own enums, by name (docs/reverse-engineering.md, "The game's
    enums"): every enum wcmods/game.py ENUMS names is at its path, with the names build 26184573's exe has, in
    order; ECommands gives the Talk prompt's Interact; a missing enum is nil, not a crash."""
    from wcmods import game
    for key, path, names in game.ENUMS:
        assert agent.lua(f'local _, order = Game.enumNames("{path}") return order') == names, key
    assert agent.lua('local t = Game.enumNames("/Script/SwtEngine.ECommands") '
                     "return { t.NoCommand, t.Player_Interact, t.TOTAL, t.ECommands_MAX == nil }") == [0, 67, 110, True]
    assert agent.lua('return Game.enumNames("/Script/SwtEngine.ENoSuchEnum") == nil') is True
    got = agent.lua("local e = Game.enums return { e.status.Poisoned, e.clan.Total, e.characterType[25] }")
    assert got == [3, 5, "BossDog"]
