"""The world through WCModsGame: the clock and the fresh-kill pile."""


def test_time_round_trip(agent):
    was = agent.lua("return Game.time.seconds()")
    try:
        agent.lua("Game.time.set(12, 0, 0)")
        noon = agent.lua("return Game.time.seconds()")
        assert abs(noon - 12 * 3600) < 300, noon
        h = agent.lua("local h = Game.time.get() return h")
        assert h == 12, h
    finally:
        agent.lua(f"Game.time.setSeconds({was})")


def test_fresh_kill(agent):
    v = agent.lua("return Game.freshKill.value()")
    assert 0 <= v <= agent.lua("return Game.freshKill.max()"), v
    assert agent.lua("return Game.freshKill.level()") in ("Full", "Abundant", "Good", "Scarcity", "Critical")
