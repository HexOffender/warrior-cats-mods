"""The story from Lua (docs/scripting.md "Quests" and "The story"; the Lua plan's step 5): the game's scenes, those seen
and playing, the skip that isn't there, progression; then, on a backed-up save, a mood set and the gather quest
(Quest.Main.1) played as C++'s test_quests does: started by its tag, its objective's targets out in the world, one
collected the player's way, the objective finished and the quest complete. The save is put back after."""
import time

GATHER = "Quest.Procedural.Survival.Gather"
ALIAS = "Quest.Main.1"


def test_lua_scenes_and_progression(agent):
    """The scenes the sequencer manager has (60 on build 26337109, most of them fight cameras, the sandbox's establishing
    shot among the story's), none playing and no skip popup; the scenes your cat has seen (the prophecy's intro); a
    progression value from the save, and nil for a path it hasn't."""
    got = agent.lua("""
        local list = Game.scenes.list()
        local byKind, chapter = {}, nil
        for _, s in ipairs(list) do
            byKind[s.kind or "?"] = (byKind[s.kind or "?"] or 0) + 1
            if s.tag == "Quest.Chapter00" then chapter = s end
        end
        return { count = #list, byKind = byKind, chapter = chapter and { type = chapter.type, kind = chapter.kind },
                 playing = #Game.scenes.playing(), skip = Game.scenes.skip(), seen = Game.scenes.seen(),
                 intro = Game.scenes.seen("ProphecyIntro"), cycle = Game.progression("FreshKill/Cycle") ~= nil,
                 missing = Game.progression("NoSuch/Path") == nil }""")
    assert got["count"] >= 40 and got["byKind"].get("Combat", 0) >= 30, (got["count"], got["byKind"])
    assert got["chapter"] is not None and got["chapter"]["kind"] in ("CutScene", "Quest", "Gameplay"), got["chapter"]
    assert got["playing"] == 0 and got["skip"] is False, got
    assert "ProphecyIntro" in got["seen"] and got["intro"] is True, got["seen"]
    assert got["cycle"] is True and got["missing"] is True, got


QUEST = f"""
local q
for _, d in ipairs(Game.quests.all()) do if d.alias == "{ALIAS}" then q = d end end
WCMODS_QUEST = q and q.quest
return q and {{ status = q.status, alias = Game.quests.alias(q.quest), tag = q.tag }}
"""


def test_lua_gather_quest_played(agent):
    """On a backed-up save: a mood asked about without adding it, then set; the gather quest (Quest.Main.1) started by its
    tag (OngoingQuest); its objective under way found, its three targets out in the world; one collected the player's
    way (Game.quests.collect: your cat on it, Interact), the count going up; the objective finished, the quest complete
    with Success. The game is closed and the save put back after, then started again."""
    backup = agent.backup_save("before-lua-story-test")
    try:
        got = agent.lua("""
            local before = Game.mood("WCModsTest", "NoSuchMood")
            local ok = Game.setMood("WCModsTest", "Set", 7)
            return { before = before == nil, set = ok, after = Game.mood("WCModsTest", "Set"),
                     still = Game.mood("WCModsTest", "NoSuchMood") == nil }""")
        assert got == {"before": True, "set": True, "after": 7, "still": True}, got

        q = agent.lua(QUEST)
        assert q and q["alias"] == ALIAS and q["tag"] == GATHER, q
        if q["status"] != "OngoingQuest":
            assert agent.lua(f'return (Game.quests.start("{GATHER}"))') is True
        agent.wait(lambda: agent.lua(QUEST)["status"] == "OngoingQuest", 5, "the quest to be under way")
        got = agent.lua("""
            local o = Game.quests.current(WCMODS_QUEST)
            WCMODS_OBJECTIVE = o
            for _, x in ipairs(Game.quests.objectives(WCMODS_QUEST)) do
                if o and x.objective:GetAddress() == o:GetAddress() then
                    WCMODS_TARGETS = x.targets[1] and x.targets[1].actors or {}
                    local t = x.targets[1]
                    return { tag = t and t.tag, current = t and t.current, target = t and t.target, actors = t and #t.actors }
                end
            end
            return "no objective under way" """)
        assert isinstance(got, dict) and got["current"] == 0 and got["target"] == 3 and got["actors"] == 3, got
        # the first target with nothing else in Interact's reach
        collected = agent.lua("""
            local why = {}
            for _, a in ipairs(WCMODS_TARGETS) do
                local ok, reason = Game.quests.collect(a)
                if ok then return true end
                why[#why + 1] = reason
            end
            return why""")
        assert collected is True, collected
        time.sleep(3)
        got = agent.lua("""
            for _, x in ipairs(Game.quests.objectives(WCMODS_QUEST)) do
                if x.objective:GetAddress() == WCMODS_OBJECTIVE:GetAddress() then return x.targets[1].current end
            end""")
        assert got >= 1, got
        assert agent.lua("return Game.quests.finishObjective(WCMODS_OBJECTIVE)") is True
        agent.wait(lambda: agent.lua(QUEST)["status"] == "QuestComplete", 5, "the quest to be complete")
        assert agent.lua("for _, d in ipairs(Game.quests.all()) do if d.alias == '" + ALIAS + "' then return d.result end end") == "Success"
        assert agent.lua("return Game.quests.finishObjective(nil)") is False
    finally:
        agent.quit(force=True)
        try:
            agent.restore_save(backup)
        finally:
            agent.launch(world=True)   # the next tests need the game, whatever happened
