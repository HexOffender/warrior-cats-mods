"""The world through WCModsGame: the clock, its hold, and the fresh-kill pile."""
import time


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


def test_a_held_clock_stays_on_its_second(agent):
    """A hold sets the clock every frame: read ten times over 1.5 s, it's never more than a few game-seconds past the
    hour held (set twice a second, it ran up to half a game-minute ahead between sets)."""
    was = agent.lua("return Game.time.seconds()")
    try:
        assert agent.lua('return (Game.time.hold(15 * 3600, "agent"))') is True
        time.sleep(0.5)
        reads = []
        for _ in range(10):
            reads.append(agent.lua("return Game.time.seconds()"))
            time.sleep(0.15)
        assert all(0 <= r - 15 * 3600 < 5 for r in reads), reads
    finally:
        agent.lua('Game.time.hold(nil, "agent") return true')
        agent.lua(f"if Game.time.held() == nil then Game.time.setSeconds({was}) end return true")


def test_quest_status_asks_only_about_the_games_quests(agent):
    """Game.quests.status, result and successes answer nil for an id none of the quest manager's quests has, without
    asking the game (whose call adds the id to the save's QuestProgression: a save written after has no such id); a
    quest's status by its alias is what describe gives it."""
    bogus = "Quest.WCModsTest.NoSuchQuest"
    got = agent.lua(f"""
        local out = {{ status = Game.quests.status("{bogus}"), result = Game.quests.result("{bogus}"),
                      successes = Game.quests.successes("{bogus}"), count = 0 }}
        for _, q in ipairs(Game.quests.all()) do
            out.count = out.count + 1
            if q.alias and not out.alias then
                out.alias, out.described = q.alias, q.status
                out.byAlias = Game.quests.status(q.alias)
            end
        end
        return out""")
    assert "status" not in got and "result" not in got and "successes" not in got, got
    if got.get("alias"):
        assert got["byAlias"] and got["byAlias"] == got["described"], got
    assert agent.lua('return (Game.save.write("WCModsTest"))') is True
    time.sleep(2.5)   # the save written, and Game.save.file()'s look at the file
    saved = agent.lua(f"""
        local slot = Game.save.slotData()
        if type(slot) ~= "table" or type(slot.QuestProgression) ~= "table" then return "no QuestProgression" end
        for chapter, ids in pairs(slot.QuestProgression) do
            if type(ids) == "table" and ids["{bogus}"] ~= nil then return chapter end
        end
        return false""")
    assert saved is False, saved


def test_clock_hold_is_one_for_every_script(agent):
    """One hold of the clock for every script: held at 15:00 by the agent (the bridge's own Lua state), it stays there
    for 3 s, a hold Tweaks had (all-tweaks holds 09:00) giving way; let go, Tweaks takes it back to its own hour. With
    no Tweaks hold up first, only the first half is checked. The clock is put back after."""
    was = agent.lua("return Game.time.seconds()")
    first = agent.lua("local s, who = Game.time.held() return { s = s, who = who }")
    first = first if isinstance(first, dict) else {}   # nobody holding: an empty table, which comes back as []
    tweaks_on = first.get("who") == "Tweaks"
    try:
        assert agent.lua('return (Game.time.hold(15 * 3600, "agent"))') is True   # (true, nil: the first only)
        time.sleep(3)
        assert agent.lua("local s, who = Game.time.held() return { s = s, who = who }") == {"s": 54000, "who": "agent"}
        assert abs(agent.lua("return Game.time.seconds()") - 15 * 3600) < 120
        assert agent.lua('return Game.time.hold(nil, "agent")') is True
        if tweaks_on:
            agent.wait(lambda: agent.lua("return select(2, Game.time.held())") == "Tweaks", 3, "Tweaks to hold the clock again")
            agent.wait(lambda: abs(agent.lua("return Game.time.seconds()") - first["s"]) < 120, 3,
                       "the clock to go back to Tweaks' hour")
    finally:
        agent.lua('Game.time.hold(nil, "agent") return true')
        # Put back unless a hold has it (Tweaks' puts its own hour back).
        agent.lua(f"if Game.time.held() == nil then Game.time.setSeconds({was}) end return true")
