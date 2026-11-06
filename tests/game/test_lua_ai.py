"""The game's AI from Lua (Game.ai, docs/scripting.md "The game's AI"; the Lua plan's step 2): an animal's AI read,
its blackboard written, its logic stopped and started; moved, stopped, turned, given back to its tree, running away;
noticing your cat, ignoring it, calmed; another tree run on it, its trees set; following your cat. Each test puts your
cat 300 units from the nearest animal it can find (700 for the moves), the animals near given 30 s before they chase,
and your cat back where it was after. An animal walked into your cat catches it as a chase does, and a fight starts
(seen: a mouse moved to 90 units of it), so the moves and the following keep 200 units or more from it. Game.ai's tree reads are compared with C++'s in test_cpp_sdk.py
(test_lua_ai_trees_match_cpp)."""
import math
import time

# The nearest animal with an AI, your cat OFF units from it; the animals near slow to chase (30 s), as they were after.
SETUP = """
local me = Game.cat():location()
local a
for _, n in ipairs(Game.animals.near(60000)) do
    if n.distance > 200 and Game.ai.controller(n.actor) then a = n.actor break end
end
if not a then return "no animal" end
local at = a:K2_GetActorLocation()
local x, y = at.X + OFF, at.Y
local g = Game.ground(x, y, at.Z + 200)
Game.cat():teleport(x, y, (g or at.Z) + 60)
WCMODS_AI = { home = me, animal = a, slowed = {} }
for _, n in ipairs(Game.animals.near(4000)) do
    local c = Game.cat(n.actor)
    local s = c:senses()
    if s and s.ReactToChase then
        WCMODS_AI.slowed[#WCMODS_AI.slowed + 1] = { actor = n.actor, was = s.ReactToChase }
        c:setSense("ReactToChase", 30)
    end
end
return true
"""

TEARDOWN = """
local s = WCMODS_AI
if not s then return true end
Game.ai.ignorePlayerEverywhere(false)
if s.animal and s.animal:IsValid() then
    Game.ai.stopFollowing(s.animal, false)
    Game.ai.stopMoving(s.animal)
    if Game.ai.ignoringPlayer(s.animal) then Game.ai.ignorePlayer(s.animal, false) end
    if s.trees then Game.ai.setTrees(s.animal, s.trees.roaming, s.trees.fight) end
    Game.ai.calm(s.animal)
    Game.ai.restart(s.animal)
end
for _, w in ipairs(s.slowed) do
    if w.actor:IsValid() then Game.cat(w.actor):setSense("ReactToChase", w.was) end
end
Game.cat():teleport(s.home.X, s.home.Y, s.home.Z)
WCMODS_AI = nil
return true
"""


def _setup(agent, off=300):
    got = agent.lua(SETUP.replace("OFF", str(off)))
    assert got is True, got
    agent.wait(lambda: agent.lua("local a = WCMODS_AI.animal return Game.ai.running(a) and not Game.ai.asleep(a)"), 8,
               "the animal to wake with your cat near")


def _teardown(agent):
    agent.lua(TEARDOWN)


def _distance(agent, a="WCMODS_AI.animal", b="Game.player()"):
    return agent.lua(f"local p, q = {a}:K2_GetActorLocation(), {b}:K2_GetActorLocation() "
                     "return math.sqrt((p.X - q.X) ^ 2 + (p.Y - q.Y) ^ 2)")


BB_ENEMY = [["SelfActor", "Object"], ["Detected", "Bool"], ["StartLocation", "Vector"], ["Target", "Object"],
            ["DetectionRange", "Float"], ["RoamingLocation", "Vector"], ["bShouldAllowMovement", "Bool"],
            ["PointOfInterest", "Vector"], ["Hunted", "Bool"], ["ChaseReactionTime", "Float"], ["ArrivedAtTarget", "Bool"],
            ["HunterPawn", "Object"], ["SplineReference", "Object"], ["CurrentIndexSpline", "Int"]]


def test_lua_ai_reads_and_writes_an_animals_ai(agent):
    """An awake animal's AI (AIC_Wrc_Enemy_Controller_C, its brain running, BB_Enemy's 14 keys, its trees BT_Enemy and
    BT_CombatEnemy, detection mask 3); keys of each kind written and read back (an int into a Float key), a place
    cleared, the wrong type and a key it hasn't refused; its logic stopped and started again. Your cat has no AI."""
    try:
        _setup(agent)
        v = agent.lua("""
            local a = WCMODS_AI.animal
            local keys = {}
            for _, k in ipairs(Game.ai.keys(a)) do keys[#keys + 1] = { k.name, k.type } end
            local t = Game.ai.trees(a)
            WCMODS_AI.trees = { roaming = t.roaming, fight = t.fight }
            local out = { controller = Game.className(Game.ai.controller(a)), brain = Game.className(Game.ai.brain(a)),
                          running = Game.ai.running(a), asleep = Game.ai.asleep(a), keys = keys,
                          roaming = t.roaming:GetFName():ToString(), fight = t.fight:GetFName():ToString(),
                          flags = Game.ai.detectionFlags(a), detected = Game.ai.get(a, "Detected"),
                          me = { controller = Game.ai.controller(Game.player()) == nil, keys = #Game.ai.keys(Game.player()),
                                 stop = Game.ai.stop(Game.player()), flags = Game.ai.detectionFlags(Game.player()) == nil } }
            local reaction, index = Game.ai.get(a, "ChaseReactionTime"), Game.ai.get(a, "CurrentIndexSpline")
            out.setFloat = Game.ai.set(a, "ChaseReactionTime", 30)
            out.float = Game.ai.get(a, "ChaseReactionTime")
            out.setInt = Game.ai.set(a, "CurrentIndexSpline", 2)
            out.int = Game.ai.get(a, "CurrentIndexSpline")
            out.setVector = Game.ai.set(a, "PointOfInterest", { 100, 200, 300 })
            out.vector = Game.ai.get(a, "PointOfInterest")
            out.cleared = Game.ai.clear(a, "PointOfInterest")
            out.vectorAfter = Game.ai.get(a, "PointOfInterest") == nil
            out.setObject = Game.ai.set(a, "HunterPawn", Game.cat())
            out.object = Game.ai.get(a, "HunterPawn") == Game.player() or Game.ai.get(a, "HunterPawn"):GetAddress() == Game.player():GetAddress()
            Game.ai.clear(a, "HunterPawn")
            out.wrong = { Game.ai.set(a, "Detected", 5) }
            out.missing = { Game.ai.set(a, "NoSuchKey", true) }
            Game.ai.set(a, "ChaseReactionTime", reaction)
            Game.ai.set(a, "CurrentIndexSpline", index)
            out.stop = Game.ai.stop(a)
            out.stopped = Game.ai.running(a)
            out.restart = Game.ai.restart(a)
            out.restarted = Game.ai.running(a)
            return out""")
        assert (v["controller"], v["brain"]) == ("AIC_Wrc_Enemy_Controller_C", "BehaviorTreeComponent"), v
        assert v["running"] is True and v["asleep"] is False and v["keys"] == BB_ENEMY, v
        assert (v["roaming"], v["fight"], v["flags"], v["detected"]) == ("BT_Enemy", "BT_CombatEnemy", 3, False), v
        assert v["me"] == {"controller": True, "keys": 0, "stop": False, "flags": True}, v["me"]
        assert v["setFloat"] is True and v["float"] == 30 and v["setInt"] is True and v["int"] == 2, v
        assert v["setVector"] is True and v["vector"] == {"X": 100, "Y": 200, "Z": 300}, v
        assert v["cleared"] is True and v["vectorAfter"] is True and v["setObject"] is True and v["object"] is True, v
        assert v["wrong"] == [False, "Detected is a Bool key"] and v["missing"] == [False, "no key called NoSuchKey"], v
        assert (v["stop"], v["stopped"], v["restart"], v["restarted"]) == (True, False, True, True), v
    finally:
        _teardown(agent)


MOVE = """
local a = WCMODS_AI.animal
local p, q = a:K2_GetActorLocation(), Game.player():K2_GetActorLocation()
local dx, dy = q.X - p.X, q.Y - p.Y
local len = math.sqrt(dx * dx + dy * dy)
local to = { X = p.X + dx / len * %(along)s, Y = p.Y + dy / len * %(along)s, Z = p.Z }
WCMODS_AI.result, WCMODS_AI.to, WCMODS_AI.from = nil, to, { X = p.X, Y = p.Y }
local ok, why = Game.ai.moveTo(a, to, { speed = %(speed)s, restartAfter = %(restart)s, done = function(r) WCMODS_AI.result = r end })
return { ok = ok, why = why, speed = Game.get(a, "CharacterMovement.MaxWalkSpeed"), running = Game.ai.running(a) }
"""


def test_lua_ai_moves_an_animal(agent):
    """An animal 700 units from your cat sent 150 toward it at 200 cm/s (its walk speed set, its logic stopped) arrives
    and stands;
    sent 400 units back and stopped after a second, its move is cancelled; turned to face your cat; a short move with
    restartAfter gives it back to its tree; run from your cat, it ends well away. The nav mesh under your cat, none in
    the sky; your cat (no AI) refused."""
    try:
        _setup(agent, 700)
        started = agent.lua(MOVE % {"along": 150, "speed": 200, "restart": "false"})
        assert started["ok"] is True and started["speed"] == 200 and started["running"] is False, started
        assert agent.lua("return Game.ai.moving(WCMODS_AI.animal)") is True
        result = agent.wait(lambda: agent.lua("return WCMODS_AI.result"), 10, "the move to end")
        off = agent.lua("local p = WCMODS_AI.animal:K2_GetActorLocation() local t = WCMODS_AI.to "
                        "return math.sqrt((p.X - t.X) ^ 2 + (p.Y - t.Y) ^ 2)")
        assert result == "arrived" and off < 80, (result, off)
        assert agent.lua("return { Game.ai.moving(WCMODS_AI.animal), Game.ai.running(WCMODS_AI.animal) }") == [False, False]

        started = agent.lua(MOVE % {"along": -400, "speed": 200, "restart": "false"})
        assert started["ok"] is True, started
        time.sleep(1.0)
        assert agent.lua("return Game.ai.stopMoving(WCMODS_AI.animal)") is True
        assert agent.lua("return WCMODS_AI.result") == "cancelled"

        yaw = agent.lua("""
            local a = WCMODS_AI.animal
            Game.ai.face(a, Game.player())
            local p, q = a:K2_GetActorLocation(), Game.player():K2_GetActorLocation()
            return { a:K2_GetActorRotation().Yaw, math.deg(math.atan(q.Y - p.Y, q.X - p.X)) }""")
        assert abs((yaw[0] - yaw[1] + 180) % 360 - 180) < 5, yaw

        started = agent.lua(MOVE % {"along": 60, "speed": 0, "restart": "true"})
        assert started["ok"] is True, started
        assert agent.wait(lambda: agent.lua("return WCMODS_AI.result"), 10, "the short move to end") == "arrived"
        assert agent.lua("return Game.ai.running(WCMODS_AI.animal)") is True

        nav = agent.lua("""
            local me = Game.cat():location()
            local on, sky = Game.ai.navPoint(me, Game.player()), Game.ai.navPoint({ me.X, me.Y, me.Z + 5000 })
            return { off = on and math.abs(on.Z - me.Z), sky = sky == nil, refused = { Game.ai.moveTo(Game.player(), me) } }""")
        assert nav["off"] is not None and nav["off"] < 50 and nav["sky"] is True and nav["refused"] == [False, "no AI"], nav

        # Run from a place behind it, the way with room (the test cat's start is by a den, whose walls stopped a mouse
        # 150 units on).
        got = agent.lua("""
            local a = WCMODS_AI.animal
            local at = a:K2_GetActorLocation()
            for i = 0, 7 do
                local r = math.rad(i * 45)
                local dx, dy = math.cos(r), math.sin(r)
                local to = { X = at.X + dx * 800, Y = at.Y + dy * 800, Z = at.Z }
                local on = Game.ai.navPoint(to, a)
                local clear = not Game.trace({ X = at.X, Y = at.Y, Z = at.Z + 30 }, { X = to.X, Y = to.Y, Z = at.Z + 30 })
                if on and clear and math.sqrt((on.X - to.X) ^ 2 + (on.Y - to.Y) ^ 2) < 150 then
                    WCMODS_AI.from, WCMODS_AI.start, WCMODS_AI.result = { X = at.X - dx * 300, Y = at.Y - dy * 300, Z = at.Z }, at, nil
                    return (Game.ai.flee(a, WCMODS_AI.from, 800, { speed = 400, restartAfter = true,
                                                                  done = function(r) WCMODS_AI.result = r end }))
                end
            end
            return "no way with room" """)
        assert got is True, got
        agent.wait(lambda: agent.lua("return WCMODS_AI.result"), 10, "the flight to end")
        ran = agent.lua("local p, s = WCMODS_AI.animal:K2_GetActorLocation(), WCMODS_AI.start "
                        "return { math.sqrt((p.X - s.X) ^ 2 + (p.Y - s.Y) ^ 2), WCMODS_AI.result, Game.ai.running(WCMODS_AI.animal) }")
        assert ran[0] > 500 and ran[2] is True, ran
    finally:
        _teardown(agent)


def test_lua_ai_notices_ignores_and_calms(agent):
    """An animal (slow to chase, 30 s) with your cat 250 units in front of it, facing it, notices your cat within 6 s
    (Detected on its blackboard, its detection tracking it); calm() makes it give your cat up; made to ignore your cat (its detection
    sphere ignoring cats, mask 0) it doesn't notice it in 6 s, noticePlayer() makes it notice at once anyway, and
    un-ignored its sphere and mask are back (its tree's Detected watched: its detection's set may keep your cat from
    before); ignorePlayerEverywhere covers every animal near and is undone."""
    try:
        _setup(agent)
        agent.lua("""
            local a = WCMODS_AI.animal
            local p, f = a:K2_GetActorLocation(), a:GetActorForwardVector()
            Game.cat():teleport(p.X + f.X * 250, p.Y + f.Y * 250, p.Z + 30)
            Game.ai.face(Game.player(), a)
            return true""")
        # (its detection's set and the tree's Detected each catch up within a moment of the other)
        agent.wait(lambda: agent.lua("local a = WCMODS_AI.animal return Game.ai.get(a, 'Detected') and Game.ai.trackingPlayer(a)"), 6,
                   "the animal to notice your cat")
        assert agent.lua("return Game.ai.calm(WCMODS_AI.animal)") is True, "calm refused"
        agent.wait(lambda: agent.lua("return Game.ai.get(WCMODS_AI.animal, 'Detected') == false"), 3, "the animal to give your cat up")

        got = agent.lua("""
            local a = WCMODS_AI.animal
            return { Game.ai.ignorePlayer(a), Game.ai.ignoringPlayer(a), Game.ai.detectionFlags(a) }""")
        assert got == [True, True, 0], got
        for i in range(6):   # (its detection's set may keep your cat from before: the tree's Detected is what acts)
            time.sleep(1)
            assert agent.lua("return Game.ai.get(WCMODS_AI.animal, 'Detected')") is False, f"noticed after {i + 1} s, ignoring"
        assert agent.lua("return Game.ai.noticePlayer(WCMODS_AI.animal)") is True, "noticePlayer refused"
        assert agent.lua("return Game.ai.get(WCMODS_AI.animal, 'Detected')") is True
        got = agent.lua("""
            local a = WCMODS_AI.animal
            Game.ai.calm(a)
            return { Game.ai.ignorePlayer(a, false), Game.ai.ignoringPlayer(a), Game.ai.detectionFlags(a) }""")
        assert got == [True, False, 3], got

        got = agent.lua("""
            Game.ai.ignorePlayerEverywhere(true)
            local near, ignoring = 0, 0
            for _, n in ipairs(Game.animals.near(5000)) do
                near = near + 1
                if Game.ai.ignoringPlayer(n.actor) then ignoring = ignoring + 1 end
            end
            Game.ai.ignorePlayerEverywhere(false)
            local after = 0
            for _, n in ipairs(Game.animals.near(5000)) do
                if Game.ai.ignoringPlayer(n.actor) then after = after + 1 end
            end
            return { near = near, ignoring = ignoring, after = after }""")
        assert got["near"] >= 1 and got["ignoring"] == got["near"] and got["after"] == 0, got
    finally:
        _teardown(agent)


def test_lua_ai_runs_other_trees_and_follows_your_cat(agent):
    """The boss's roaming tree run on an animal (its own trees still set, the same 14 keys) and its own again; its trees
    set (BT_BossEnemy, BT_AttackEnemy) and read back, then as they were; following your cat 200 units off: within 300,
    after it when your cat moves 600 away, and given back to its tree once let go. BT_Enemy read as data (26 nodes, its Hunted
    and Detected branches)."""
    try:
        _setup(agent)
        got = agent.lua("""
            local a = WCMODS_AI.animal
            local t = Game.ai.trees(a)
            WCMODS_AI.trees = { roaming = t.roaming, fight = t.fight }
            local out = { ran = Game.ai.runTree(a, "BT_BossEnemy"), running = Game.ai.running(a), keys = #Game.ai.keys(a),
                          stillSet = Game.ai.trees(a).roaming:GetFName():ToString(), bad = Game.ai.runTree(a, "BT_Nothing") }
            out.back = Game.ai.runTree(a, t.roaming)
            out.set = Game.ai.setTrees(a, "BT_BossEnemy", "BT_AttackEnemy")
            local s = Game.ai.trees(a)
            out.setRoaming, out.setFight = s.roaming:GetFName():ToString(), s.fight:GetFName():ToString()
            Game.ai.setTrees(a, t.roaming, t.fight)
            out.restored = Game.ai.trees(a).roaming:GetFName():ToString()
            local nodes = Game.ai.treeNodes("BT_Enemy")
            local lines = {}
            for _, n in ipairs(nodes) do
                local s = n.depth .. " " .. n.role .. " " .. n.kind .. " '" .. n.name .. "'"
                for _, kv in ipairs(n.settings) do s = s .. " " .. kv.name .. "=" .. kv.value end
                lines[#lines + 1] = s
            end
            out.lines = lines
            out.blackboard = Game.ai.treeBlackboard("BT_Enemy")
            return out""")
        assert got["ran"] is True and got["running"] is True and got["keys"] == 14 and got["stillSet"] == "BT_Enemy", got
        assert got["bad"] is False and got["back"] is True, got
        assert (got["set"], got["setRoaming"], got["setFight"], got["restored"]) == (True, "BT_BossEnemy", "BT_AttackEnemy", "BT_Enemy"), got
        lines = got["lines"]
        assert len(lines) == 26 and lines[0].startswith("0 composite BTComposite_Selector") and got["blackboard"] == "BB_Enemy", lines
        assert any("BlackboardKey=Hunted" in x for x in lines) and any("BlackboardKey=Detected" in x for x in lines), lines

        assert agent.lua("return Game.ai.follow(WCMODS_AI.animal, Game.player(), { distance = 200, speed = 300 })") is True
        assert agent.lua("return { Game.ai.following(WCMODS_AI.animal), Game.ai.running(WCMODS_AI.animal) }") == [True, False]
        agent.wait(lambda: _distance(agent) < 300, 8, "the animal to come to your cat")
        agent.lua("""
            local a = WCMODS_AI.animal
            local p, q = a:K2_GetActorLocation(), Game.player():K2_GetActorLocation()
            local dx, dy = q.X - p.X, q.Y - p.Y
            local len = math.max(1, math.sqrt(dx * dx + dy * dy))
            local x, y = q.X + dx / len * 600, q.Y + dy / len * 600
            Game.cat():teleport(x, y, (Game.ground(x, y, q.Z + 200) or q.Z) + 60)
            return true""")
        assert _distance(agent) > 400
        agent.wait(lambda: _distance(agent) < 300, 10, "the animal to follow your cat")
        got = agent.lua("local a = WCMODS_AI.animal return { Game.ai.stopFollowing(a), Game.ai.following(a), Game.ai.running(a), "
                        "Game.ai.stopFollowing(a), Game.ai.follow(Game.player(), a) }")
        assert got == [True, False, True, False, False], got
    finally:
        _teardown(agent)
