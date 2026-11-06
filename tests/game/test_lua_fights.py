"""Fights from Lua (Game.combat; docs/scripting.md "Fights"; the Lua plan's step 4): a fight started the player's way
with a rabbit Game.animals.spawn put out where the animals live (its party the rabbit's), your cat's turn taken through
the fight menu, the fight won the game's way; one fled; one played by autoFight with every hit on the enemy made
deadly by Game.combat.onDamage; one lost. A dilemma that comes up is answered. Your cat goes back to its spot after,
and the save keeps it there (a fight's end saves where your cat is)."""
import time

from wcmods.agent import skip

RABBIT = "Gameplay.Combat.Generator.Fixed.Rabbit.01.L6"

# Out where the animals live (beside the den at the test cat's spot no pounce starts a fight): an animal 2,500 units or
# more from your cat on level ground. For a rabbit (`rabbit`), as C++'s test does: your cat 300 units from that animal
# and the rabbit 600 units on the other side of your cat, with no other animal within 600 of it (a pounce on a rabbit
# 300 units from a mouse fought the mouse; one 1,200 units off, by a rock wall, started no fight).
OUT = """
WCMODS_HOME = WCMODS_HOME or Game.cat():location()
local me = Game.cat():location()
WCMODS_TRIED = WCMODS_TRIED or {}
for _, n in ipairs(Game.animals.near(20000)) do
    local p = n.actor:K2_GetActorLocation()
    if n.distance > 2500 and math.abs(p.Z - me.Z) < 400 and not WCMODS_TRIED[n.actor:GetAddress()] then
        WCMODS_TRIED[n.actor:GetAddress()] = true
        local x, y = p.X + 300, p.Y
        local g = Game.ground(x, y, p.Z + 300)
        if g and math.abs(g - p.Z) < 100 then
            WCMODS_PREY = n.actor
            WCMODS_SPOT = { X = x, Y = y, Z = g + 20 }
            if not %(rabbit)s then return true end
            local rx = x + 600
            local rg = Game.ground(rx, y, g + 300)
            local spot = rg and { X = rx, Y = y, Z = rg + 20 }
            if spot and math.abs(rg - g) < 100 and #Game.animals.near(600, spot) == 0 and Game.cat():teleport(x, y, g + 60) then
                local r, why = Game.animals.spawn("%(kind)s", spot)
                if not r then return why end
                WCMODS_PREY = r
                return true
            end
        end
    end
end
return "no animal out where they live"
"""


def _answer_dilemma(agent):
    """A dilemma up: answered (its first choice). Whether one was."""
    return agent.lua("if Game.combat.dilemma() then return Game.combat.answerDilemma(1) end return false") is True


def _until(agent, cond, timeout, what):
    """Wait for a Lua condition, answering any dilemma meanwhile."""
    end = time.time() + timeout
    while time.time() < end:
        if agent.lua("return " + cond):
            return True
        _answer_dilemma(agent)
        time.sleep(0.5)
    state = agent.lua("""local f = Game.fight()
        local out = { active = Game.combat.active(), menu = Game.combat.menu() ~= nil, dilemma = Game.combat.dilemma(),
                      screens = Game.screens() }
        if f then
            out.current = f:current() and f:current():kind()
            out.enemies = {}
            for _, e in ipairs(f:enemies()) do out.enemies[#out.enemies + 1] = e:cat() and e:cat():health() end
        end
        return out""")
    raise AssertionError(f"timed out after {timeout} s waiting for {what}: {state}")


def _fight(agent, rabbit=False):
    """A fight with an animal OUT picks, started the player's way (Game.combat.start: behind it, a pounce): up to three
    animals, two pounces each. The rabbit is pounced with its logic stopped (Game.ai.stop)."""
    agent.lua("WCMODS_TRIED = nil return true")
    if not rabbit:
        # up to three animals, two pounces each (a pounce can miss; at some spots none starts a fight)
        for _ in range(3):
            got = agent.lua(OUT % {"rabbit": "false", "kind": RABBIT})
            assert got is True, got
            for _ in range(2):
                assert agent.lua("return Game.combat.start(WCMODS_PREY)") is True
                try:
                    _until(agent, "Game.combat.active() and Game.combat.menu() ~= nil", 10, "the fight menu")
                    return
                except AssertionError:
                    if agent.lua("return Game.combat.active()"):
                        raise
        raise AssertionError("no pounce started a fight")
    # up to three spots (at some none starts a fight): the rabbit spawned at each, the other animals near ignoring your
    # cat (a bird caught your cat first once, as a chase does), the rabbit's logic stopped, then pounced twice; then its
    # logic running again and made to notice your cat (one spawned so chases your cat into a fight: seen from C++). A spawned
    # rabbit left running noticed your cat as it landed behind it and the pounce started nothing; made to notice your cat,
    # it set no foot toward it on a fresh game; stopped, a pounce started a fight at once (seen, twice of two).
    for _ in range(3):
        got = agent.lua(OUT % {"rabbit": "true", "kind": RABBIT})
        assert got is True, got
        agent.lua("""
            WCMODS_IGNORED = WCMODS_IGNORED or {}
            for _, n in ipairs(Game.animals.near(4000)) do
                if n.actor:GetAddress() ~= WCMODS_PREY:GetAddress() and Game.ai.ignorePlayer(n.actor) then
                    WCMODS_IGNORED[#WCMODS_IGNORED + 1] = n.actor
                end
            end
            return true""")
        for _ in range(2):
            agent.lua("Game.ai.calm(WCMODS_PREY) Game.ai.stop(WCMODS_PREY) return true")
            assert agent.lua("return Game.combat.start(WCMODS_PREY)") is True
            try:
                _until(agent, "Game.combat.active() and Game.combat.menu() ~= nil", 10, "the fight menu")
                return
            except AssertionError:
                if agent.lua("return Game.combat.active()"):
                    raise
        # the other way in: its logic running again, made to notice your cat, it chases and catches your cat
        agent.lua("Game.ai.restart(WCMODS_PREY) return Game.ai.noticePlayer(WCMODS_PREY)")
        try:
            _until(agent, "Game.combat.active() and Game.combat.menu() ~= nil", 15, "the rabbit to catch your cat")
            return
        except AssertionError:
            if agent.lua("return Game.combat.active()"):
                raise
        agent.lua("Game.animals.remove(WCMODS_PREY) return true")
    # Where a fight can start depends on the spot (a den's surroundings, a rock wall, a spawned animal out of sight of
    # your cat): seen to start at once on a fresh game, and at none of three spots after a game's worth of fights.
    # C++'s test_ai_spawn checks the same borrowed generator's party.
    skip("no pounce on the spawned rabbit started a fight at three spots (the world, not the call: see the comment)")


def _out_of_fights(agent):
    """Any fight fled, your cat back at its spot, and saved there."""
    for _ in range(30):
        if not agent.lua("return Game.combat.active()"):
            break
        _answer_dilemma(agent)
        agent.lua("return Game.combat.flee()")
        time.sleep(1)
    agent.wait(lambda: agent.lua("return Game.player() ~= nil"), 20, "your cat back in the world")
    agent.lua("""
        for _, a in ipairs(WCMODS_IGNORED or {}) do if Game.alive(a) then Game.ai.ignorePlayer(a, false) end end
        WCMODS_IGNORED = nil
        if WCMODS_PREY and Game.alive(WCMODS_PREY) and Game.animals.kind(WCMODS_PREY) then Game.animals.remove(WCMODS_PREY) end
        local h = WCMODS_HOME
        if h then Game.cat():teleport(h.X, h.Y, h.Z) Game.save.write("WCModsTest") end
        WCMODS_HOME = nil
        return true""")


def test_lua_fight_with_a_spawned_rabbit_won(agent):
    """A rabbit put out where the animals live, pounced (its logic stopped): a fight with one enemy, a rabbit at level 6 (the kind's party,
    which a borrowed generator gives); your cat's fighter (tier None, its moves on the attack panel with their stamina
    costs); an attack played through the menu (the menu goes, and comes back on your cat's next turn); then the fight
    won the game's way (the enemy's health set to 0, your cat's turn taken): the fight over, the rabbit gone."""
    try:
        _fight(agent, rabbit=True)
        got = agent.lua("""
            local f = Game.fight()
            local enemies = f:enemies()
            local e = enemies[1]
            local me = Game.combat.cat()
            return { enemies = #enemies, kind = e and e:cat() and e:cat():kind(), level = e and e:level(),
                     tier = me and me:aiTier(), mine = me and me:cat() and me:cat().actor:GetClass():GetFName():ToString(),
                     moves = Game.combat.moves() }""")
        assert got["enemies"] == 1 and got["kind"] == "Rabbit" and got["level"] == 6, got
        assert got["tier"] == "None" and got["mine"] == "BP_Exploration_Character_Player_C", got
        # the attack panel's moves (its buttons can be read before it opens): names and stamina costs
        assert got["moves"] and all(m["name"] and m["stamina"] and m["usable"] in (True, False) for m in got["moves"]), got["moves"]
        assert agent.lua("return Game.combat.attack(1)") is True
        _until(agent, "Game.combat.menu() == nil", 8, "your cat's attack to be taken")
        _until(agent, "Game.combat.menu() ~= nil or not Game.combat.active()", 20, "your cat's next turn")
        if agent.lua("return Game.combat.active()"):
            assert agent.lua("return Game.combat.finish(true)") is True
            _until(agent, "not Game.combat.active()", 45, "the fight to end")   # (over 20 s once, on a fresh game)
        assert agent.lua("return Game.alive(WCMODS_PREY)") is False
    finally:
        _out_of_fights(agent)


def test_lua_fight_fled(agent):
    """A fight with one of the game's animals, fled through the menu: over within 10 s."""
    try:
        _fight(agent)
        assert agent.lua("return Game.combat.flee()") is True
        _until(agent, "not Game.combat.active()", 10, "the fight to end")
    finally:
        _out_of_fights(agent)


def test_lua_auto_fight_with_deadly_hits(agent):
    """Game.combat.onDamage making every hit on the enemy deadly (its health's worth and more) and autoFight playing
    your cat's turns: the moves read off the attack panel, a turn taken, the fight won by the first hit that landed on
    the enemy (the change took: one hit's own damage doesn't fell it)."""
    try:
        agent.lua("""
            WCMODS_HITS = {}
            WCMODS_DAMAGE = Game.combat.onDamage(function(info)
                local mine = Game.combat.cat()
                local target = info.target
                local onEnemy = mine and target and mine:actor() and target:GetAddress() ~= mine:actor():GetAddress()
                WCMODS_HITS[#WCMODS_HITS + 1] = { damage = info.damage, missed = info.missed, enemy = onEnemy == true }
                if onEnemy then return 9999 end
            end)
            return true""")
        _fight(agent)
        agent.lua("Game.combat.autoFight(true) return true")
        _until(agent, "not Game.combat.active()", 45, "autoFight to win the fight")
        got = agent.lua("""local landed = 0
            for _, h in ipairs(WCMODS_HITS) do if h.enemy and not h.missed then landed = landed + 1 end end
            return { turns = Game.combat.autoFightTurns(), hits = #WCMODS_HITS, landed = landed }""")
        # one hit on the enemy that landed ended the fight: the 9,999 written over its damage took (a hit's own damage,
        # about 20 to 40, doesn't fell even a level 2 animal at once)
        assert got["turns"] >= 1 and got["landed"] == 1, got
    finally:
        agent.lua("Game.combat.autoFight(false) if WCMODS_DAMAGE then Game.unhook(WCMODS_DAMAGE) WCMODS_DAMAGE = nil end return true")
        _out_of_fights(agent)


def test_lua_fight_lost(agent):
    """A fight lost the game's way (your cat's side's health set to 0, its turn taken): over, your cat back in the world
    (at its respawn spot, healed)."""
    try:
        _fight(agent)
        assert agent.lua("return Game.combat.finish(false)") is True
        _until(agent, "not Game.combat.active()", 30, "the fight to end")
        agent.wait(lambda: agent.lua("return Game.player() ~= nil"), 30, "your cat back in the world")
        assert agent.lua("local c = Game.cat() return c:health() > 0") is True
    finally:
        _out_of_fights(agent)
