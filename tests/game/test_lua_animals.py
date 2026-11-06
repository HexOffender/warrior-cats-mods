"""Animals and the clan cats' walking from Lua (Game.animals, Game.walkers; docs/scripting.md "The game's AI"; the Lua
plan's step 3): the game's fight parties; a rabbit put in the world by a borrowed generator, listed, taken out (the
generator given back) and spawned again with respawn; the walking cats near and their paths; a mod's cat walking a
square of the script's own, stopped and walking on; a game cat given a path and its own back."""
import math
import time

RABBIT = "Gameplay.Combat.Generator.Fixed.Rabbit.01.L6"


def test_lua_animal_kinds(agent):
    """DT_Combat_Generator's 323 parties, as C++'s animal_kinds lists them; the rabbit's is one rabbit at level 6."""
    got = agent.lua(f"""
        local kinds = Game.animals.kinds()
        local out = {{ count = #kinds }}
        for _, k in ipairs(kinds) do
            if k.tag == "{RABBIT}" then out.rabbit = {{ party = k.party, levels = k.levels }} end
        end
        return out""")
    assert got["count"] == 323, got["count"]
    assert got["rabbit"] == {"party": ["Gameplay.Combat.Character.Rabbit"], "levels": [6]}, got.get("rabbit")


# A spot 800 units in front of your cat, on the ground.
SPOT = """
local me, f = Game.cat():location(), Game.player():GetActorForwardVector()
local x, y = me.X + f.X * 800, me.Y + f.Y * 800
WCMODS_SPOT = { X = x, Y = y, Z = (Game.ground(x, y, me.Z + 300) or me.Z) + 20 }
WCMODS_HOME = me
return true
"""

# Spawned, made to ignore your cat at once (noticing it, a rabbit chases your cat into a fight).
SPAWN = """
local a, why = Game.animals.spawn("%s", WCMODS_SPOT, { respawn = %s })
if not a then return { why = why } end
Game.ai.ignorePlayer(a)
WCMODS_RABBIT = a
local g
for _, n in ipairs(Game.animals.near(3000)) do
    if n.actor:GetAddress() == a:GetAddress() then
        WCMODS_GEN = n.generator
        g = n
    end
end
local at, gat = a:K2_GetActorLocation(), WCMODS_GEN:K2_GetActorLocation()
return { listed = g ~= nil, kind = g and g.kind, model = g and g.model, running = Game.ai.running(a),
         off = math.sqrt((at.X - WCMODS_SPOT.X) ^ 2 + (at.Y - WCMODS_SPOT.Y) ^ 2),
         genOff = math.sqrt((gat.X - WCMODS_SPOT.X) ^ 2 + (gat.Y - WCMODS_SPOT.Y) ^ 2),
         genTag = WCMODS_GEN.ThunderClanCombatTags.ApprenticeSetup.TagName:ToString() }
"""

GENERATOR = """
local g = WCMODS_GEN
local at = g:K2_GetActorLocation()
return { off = math.sqrt((at.X - WCMODS_SPOT.X) ^ 2 + (at.Y - WCMODS_SPOT.Y) ^ 2),
         tag = g.ThunderClanCombatTags.ApprenticeSetup.TagName:ToString(), preys = #g.SpawnedPreys }
"""


def test_lua_spawn_an_animal(agent):
    """A rabbit put 800 units in front of your cat: a generator of the game's borrowed (the farthest from your cat), its
    tags the rabbit's, moved there; the rabbit there, its AI running, listed by Game.animals.near with its kind and
    model. Taken out: the generator given back (home again, its own party, its own animal back). Spawned again with
    respawn and taken by the game (destroyed): a new rabbit from the same generator within 5 s, then taken out for good.
    A kind the game hasn't and no place are refused, nothing borrowed."""
    try:
        agent.lua(SPOT)
        got = agent.lua(SPAWN % (RABBIT, "false"))
        assert "why" not in got, got
        assert got["listed"] is True and got["kind"] == RABBIT and got["model"] == "SK_Rabbit", got
        assert got["running"] is True and got["off"] < 300 and got["genOff"] < 50 and got["genTag"] == RABBIT, got
        assert agent.lua("return Game.animals.remove(WCMODS_RABBIT)") is True, "remove refused"
        back = agent.lua(GENERATOR)
        assert back["off"] > 1000 and back["tag"] != RABBIT and back["preys"] >= 1, back
        assert agent.lua("return Game.alive(WCMODS_RABBIT)") is False, "the rabbit still there"

        got = agent.lua(SPAWN % (RABBIT, "true"))
        assert "why" not in got and got["listed"] is True, got
        agent.lua("WCMODS_FIRST = WCMODS_RABBIT:GetAddress() WCMODS_RABBIT:K2_DestroyActor() return true")
        again = agent.wait(lambda: agent.lua(f"""
            for _, n in ipairs(Game.animals.near(3000, WCMODS_SPOT)) do
                if n.kind == "{RABBIT}" and n.actor:GetAddress() ~= WCMODS_FIRST then
                    WCMODS_RABBIT = n.actor
                    Game.ai.ignorePlayer(n.actor)
                    return true
                end
            end
            return false"""), 6, "a new rabbit from the generator")
        assert again is True
        assert agent.lua("return Game.animals.remove(WCMODS_RABBIT)") is True, "remove refused"
        assert agent.lua(GENERATOR)["tag"] != RABBIT, "the generator kept the rabbit's party"

        refused = agent.lua('return { unknown = select(2, Game.animals.spawn("Gameplay.Combat.Generator.NoSuchParty", WCMODS_SPOT)), '
                            'nowhere = select(2, Game.animals.spawn("' + RABBIT + '")), remove = Game.animals.remove(Game.player()) }')
        assert refused == {"unknown": "Gameplay.Combat.Generator.NoSuchParty isn't one of the game's fight parties",
                           "nowhere": "spawn needs a kind and a place", "remove": False}, refused
    finally:
        agent.lua("if Game.alive(WCMODS_RABBIT) then Game.animals.remove(WCMODS_RABBIT) end return true")


def _at(agent, who):
    return agent.lua(f"local l = {who}:K2_GetActorLocation() return {{ l.X, l.Y }}")


def test_lua_walkers_and_paths(agent):
    """The walking cats near your cat and their paths (the nearest on the game's own path, there and back); a mod's cat
    walking a square of the script's own round a spot at 100 cm/s (listed as the script's loop of four, walking well
    round, never far from the square); stopped, it stands; walked on, it walks. A game cat (your cat 1,200 units from
    it) given a path of two places there and back at 150 cm/s (two of its own path's neighbouring points) walks it, then its own path again at its own speed. What
    isn't a walking cat, and one place, are refused; the mod's cat removed, its path goes."""
    try:
        got = agent.lua("""
            local w = Game.walkers.near(30000)
            local mine = Game.cat():location()
            WCMODS_HOME = mine
            local first = w[1]
            return { count = #w, points = first and #first.points, loop = first and first.loop, modPath = first and first.modPath }""")
        assert got["count"] >= 1 and got["points"] >= 2 and got["loop"] is False and got["modPath"] is False, got

        # ----- a mod's cat on a square loop
        agent.lua("""
            local me = Game.cat():location()
            local c = { X = me.X + 400, Y = me.Y, Z = me.Z }
            WCMODS_CENTRE = c
            WCMODS_NPC = Game.npcs.spawn({ at = { c.X, c.Y - 200, c.Z }, yaw = 0 })
            return true""")
        agent.wait(lambda: agent.lua("return WCMODS_NPC:actorOrNil() ~= nil"), 5, "the mod's cat")
        got = agent.lua("""
            local c = WCMODS_CENTRE
            local function g(x, y) return { X = x, Y = y, Z = (Game.ground(x, y, c.Z + 200) or c.Z) } end
            local ok, why = Game.walkers.walkPath(WCMODS_NPC, { g(c.X - 200, c.Y - 200), g(c.X + 200, c.Y - 200),
                                                                g(c.X + 200, c.Y + 200), g(c.X - 200, c.Y + 200) }, { speed = 100 })
            local entry
            for _, w in ipairs(Game.walkers.near(3000)) do
                if w.actor:GetAddress() == WCMODS_NPC:actorOrNil():GetAddress() then entry = w end
            end
            return { ok = ok, why = why, modPath = entry and entry.modPath, loop = entry and entry.loop,
                     points = entry and #entry.points, walking = Game.walkers.walking(WCMODS_NPC) }""")
        assert got == {"ok": True, "modPath": True, "loop": True, "points": 4, "walking": True}, got
        walked, far, last = 0.0, 0.0, _at(agent, "WCMODS_NPC:actorOrNil()")
        centre = agent.lua("return { WCMODS_CENTRE.X, WCMODS_CENTRE.Y }")
        for _ in range(8):
            time.sleep(1)
            now = _at(agent, "WCMODS_NPC:actorOrNil()")
            walked += math.dist(now, last)
            far = max(far, math.dist(now, centre))
            last = now
        assert walked > 400 and far < 450, (walked, far)

        assert agent.lua("return Game.walkers.stop(WCMODS_NPC)") is True, "stop refused"
        time.sleep(1)
        a = _at(agent, "WCMODS_NPC:actorOrNil()")
        time.sleep(2)
        stood = math.dist(a, _at(agent, "WCMODS_NPC:actorOrNil()"))
        assert stood < 10 and agent.lua("return Game.walkers.walking(WCMODS_NPC)") is False, stood
        assert agent.lua("return Game.walkers.walkAgain(WCMODS_NPC)") is True, "walkAgain refused"
        on, last = 0.0, _at(agent, "WCMODS_NPC:actorOrNil()")
        for _ in range(6):   # the way walked (round the square's corners, where it ends up is no measure)
            time.sleep(0.5)
            now = _at(agent, "WCMODS_NPC:actorOrNil()")
            on += math.dist(now, last)
            last = now
        assert on > 120, (on, agent.lua("local a = WCMODS_NPC:actorOrNil() local v = a:GetVelocity() "
                                        "return { Game.ai.running(a), Game.ai.get(a, 'bShouldAllowMovement'), math.sqrt(v.X * v.X + v.Y * v.Y), "
                                        "Game.ai.controller(a):GetMoveStatus(), Game.walkers.walking(WCMODS_NPC) }"))

        refused = agent.lua("return { { Game.walkers.walkPath(Game.player(), { {0, 0, 0}, {1, 1, 1} }) }, "
                            "{ Game.walkers.walkPath(WCMODS_NPC, { {0, 0, 0} }) }, Game.walkers.ownPath(Game.player()) }")
        assert refused == [[False, "not a walking cat"], [False, "a path needs two places or more"], False], refused

        # ----- a game cat: your cat 1,200 units from it (one stands while your cat is near)
        got = agent.lua("""
            local w
            for _, x in ipairs(Game.walkers.near(30000)) do
                if not x.modPath and #x.points >= 2 and x.actor:GetAddress() ~= WCMODS_NPC:actorOrNil():GetAddress() then w = x break end
            end
            if not w then return "no game cat walking" end
            WCMODS_WALKER, WCMODS_OWN = w.actor, w.path:GetFName():ToString()
            local at = w.actor:K2_GetActorLocation()
            -- two neighbouring points of its own path, which the game walks (a line of the test's own ran into a rock)
            local k, best = 1, nil
            for i = 1, #w.points - 1 do
                local p = w.points[i]
                local d = math.sqrt((p.X - at.X) ^ 2 + (p.Y - at.Y) ^ 2)
                if not best or d < best then k, best = i, d end
            end
            local line = { w.points[k], w.points[k + 1] }
            -- your cat 1,200 units off, away from the line (a side with room for it: a teleport with none fails)
            local away = false
            for turn = 0, 315, 45 do
                local r = math.rad(turn) + math.atan(at.Y - line[2].Y, at.X - line[2].X)
                local x, y = at.X + math.cos(r) * 1200, at.Y + math.sin(r) * 1200
                if Game.cat():teleport(x, y, (Game.ground(x, y, at.Z + 300) or at.Z) + 60) then
                    local me = Game.cat():location()
                    if math.sqrt((me.X - at.X) ^ 2 + (me.Y - at.Y) ^ 2) > 1000 then away = true break end
                end
            end
            local ok, why = Game.walkers.walkPath(w.actor, line, { loop = false, speed = 150 })
            return { ok = ok, why = why, away = away, speed = Game.get(w.actor, "Controller.DefaultMaxWalkSpeed") }""")
        assert got == {"ok": True, "away": True, "speed": 150}, got
        moved, last = 0.0, _at(agent, "WCMODS_WALKER")
        for _ in range(8):   # the way walked (at the line's ends it turns back)
            time.sleep(0.5)
            now = _at(agent, "WCMODS_WALKER")
            moved += math.dist(now, last)
            last = now
        assert moved > 200, moved
        got = agent.lua("""
            local ok = Game.walkers.ownPath(WCMODS_WALKER)
            local s = Game.ai.get(WCMODS_WALKER, "SplineReference")
            return { ok = ok, path = s and s:GetOwner():GetFName():ToString(), own = WCMODS_OWN,
                     speed = Game.get(WCMODS_WALKER, "Controller.DefaultMaxWalkSpeed"), again = Game.walkers.ownPath(WCMODS_WALKER) }""")
        assert got["ok"] is True and got["path"] == got["own"] and got["speed"] == 50 and got["again"] is False, got

        # ----- the mod's cat gone: its path goes (looked at every 2 s)
        agent.lua("local s = Game.ai.get(WCMODS_NPC:actorOrNil(), 'SplineReference') WCMODS_PATH = s:GetOwner() "
                  "WCMODS_NPC:remove() return true")
        agent.wait(lambda: agent.lua("return not Game.alive(WCMODS_PATH)"), 5, "the mod's path to go with its cat")
    finally:
        agent.lua("if Game.alive(WCMODS_WALKER) then Game.walkers.ownPath(WCMODS_WALKER) end "
                  "if WCMODS_NPC then WCMODS_NPC:remove() end "
                  "if WCMODS_HOME then Game.cat():teleport(WCMODS_HOME.X, WCMODS_HOME.Y, WCMODS_HOME.Z) end return true")
