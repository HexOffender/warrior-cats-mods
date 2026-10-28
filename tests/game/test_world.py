"""The world through WCModsGame: the clock and the fresh-kill pile."""


def tweaks_clock_off(agent):
    """The Tweaks in the same test install (tests/game/mods/all-tweaks) hold the clock, setting it back twice a
    second: switch that off on their mod menu page while a test moves the clock. Returns what puts it back."""
    there = any("Tweaks" in (p["id"], p["title"]) for p in agent.menu.pages())
    if not there or not agent.menu.open("Tweaks").get("Hold the clock"):
        agent.menu.close()
        return lambda: None
    agent.menu.set("Hold the clock", False)
    agent.menu.close()

    def back():
        agent.menu.open("Tweaks")
        agent.menu.set("Hold the clock", True)
        agent.menu.close()
    return back


def test_time_round_trip(agent):
    hold_again = tweaks_clock_off(agent)
    was = agent.lua("return Game.time.seconds()")
    try:
        agent.lua("Game.time.set(12, 0, 0)")
        noon = agent.lua("return Game.time.seconds()")
        assert abs(noon - 12 * 3600) < 300, noon
        h = agent.lua("local h = Game.time.get() return h")
        assert h == 12, h
    finally:
        agent.lua(f"Game.time.setSeconds({was})")
        hold_again()


def test_fresh_kill(agent):
    v = agent.lua("return Game.freshKill.value()")
    assert 0 <= v <= agent.lua("return Game.freshKill.max()"), v
    assert agent.lua("return Game.freshKill.level()") in ("Full", "Abundant", "Good", "Scarcity", "Critical")


def test_cat_names_from_the_game(agent):
    """A name WCModsNames hasn't got comes from the game's own string table, which holds whole names
    under prefix id + suffix id: "STR_CAT_NAME1_PAW" is "Woodpaw" (any name in it would do)."""
    got = agent.lua('local N = require("WCModsNames") return { N.name("STR_CAT_NAME1_PAW", ""), N.name("NOT_A_NAME", "_X") }')
    assert got and got[0] == "Woodpaw" and len(got) == 1, got
