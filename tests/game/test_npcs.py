"""Cats of a mod's own (Game.npcs), the game's screens (Game.screens), and a mod's quests on the mod menu
(Game.quests.report)."""
import time

import pytest

SPAWN = """
local me = Game.cat():location()
WCMODS_TEST_NPC = Game.npcs.spawn({ at = { me.X + 150, me.Y + 150, me.Z }, yaw = 90, size = 0.8, eyes = 3,
    colours = { fur = "#ff0000", markings = "#0000ff" } })
return WCMODS_TEST_NPC:valid()
"""

# The body's colours and eye row as the game draws them.
LOOK = """
local a = WCMODS_TEST_NPC:actorOrNil()
if not a then return nil end
local m = a.Mesh:GetMaterial(0)
local out = {}
m.VectorParameterValues:ForEach(function(_, e)
    local v = e:get()
    local n = v.ParameterInfo.Name:ToString()
    if n == "Fur Color" or n == "Markings Mask Color" then
        out[n] = { v.ParameterValue.R, v.ParameterValue.G, v.ParameterValue.B }
    end
end)
m.ScalarParameterValues:ForEach(function(_, e)
    local v = e:get()
    if v.ParameterInfo.Name:ToString() == "IndexIrisColorCurveLeft" then out.eyes = v.ParameterValue end
end)
out.distance = WCMODS_TEST_NPC:distance()
out.near = WCMODS_TEST_NPC:near(400)
return out
"""


def test_npc_spawns_with_its_colours(agent):
    try:
        assert agent.lua(SPAWN) is True
        look = None
        for _ in range(10):         # the colours go on with the spawn, or by the keeper twice a second
            look = agent.lua(LOOK)
            if look and look.get("Fur Color", [0])[0] > 0.9:
                break
            time.sleep(0.5)
        assert look, "no npc"
        fur, marks = look["Fur Color"], look["Markings Mask Color"]
        assert fur[0] > 0.9 and fur[1] < 0.05 and fur[2] < 0.05, fur
        assert marks[2] > 0.9 and marks[0] < 0.05, marks
        assert look["eyes"] == 4, look          # iris slot 3 is the atlas' row 4
        assert 100 < look["distance"] < 400 and look["near"] is True, look
    finally:
        agent.lua("if WCMODS_TEST_NPC then WCMODS_TEST_NPC:remove() end")
    assert agent.lua("return WCMODS_TEST_NPC:valid()") is False


def test_npc_comes_back(agent):
    """A cat the game takes away (here: destroyed) is spawned again by the keeper."""
    try:
        assert agent.lua(SPAWN) is True
        agent.lua("WCMODS_TEST_NPC:actorOrNil():K2_DestroyActor()")
        back = None
        for _ in range(20):        # once the engine has let the old one go, within a few seconds
            time.sleep(0.5)
            back = agent.lua("return WCMODS_TEST_NPC:valid() and WCMODS_TEST_NPC.spawns")
            if back == 2:
                break
        assert back == 2, back
    finally:
        agent.lua("if WCMODS_TEST_NPC then WCMODS_TEST_NPC:remove() end")


LOOKED = """
local me = Game.cat():location()
WCMODS_TEST_NPC = Game.npcs.spawn({ at = { me.X + 150, me.Y + 150, me.Z }, yaw = 90,
    look = { body = 9, tail = 0, ears = 9, pattern = 20, marking = 0 }, slots = { fur = 3, pattern = 10 } })
return WCMODS_TEST_NPC:valid()
"""
# The look's fields in the cat's data, and the meshes of its tail and ears.
LOOKED_DATA = """
local comp = WCMODS_TEST_NPC:actorOrNil().MeshCustomizationComponent
local d = comp.CustomData
return { d.BodyValue, d.FurIdx, d.TailIdx, d.EarIdx, d.PatternIdx, d.MarkingIdx, d.FurColorIdx, d.Pattern01ColorIdx,
         comp.TailSkelMeshComp:GetSkeletalMeshAsset():GetFName():ToString(),
         comp.EarSkelMeshComp:GetSkeletalMeshAsset():GetFName():ToString() }
"""
LOOK_FIELDS = [9, 9, 0, 9, 20, 0, 3, 10]


def test_npc_keeps_the_look_its_given(agent):
    """A fixed look goes on over the one the game makes up, stays, and is the same when it's spawned again."""
    try:
        assert agent.lua(LOOKED) is True
        first = agent.lua(LOOKED_DATA)
        assert first[:8] == LOOK_FIELDS, first
        time.sleep(2)                       # the game setting it up again doesn't take it back
        assert agent.lua(LOOKED_DATA)[:8] == first[:8]
        agent.lua("WCMODS_TEST_NPC:actorOrNil():K2_DestroyActor()")
        again = None
        for _ in range(20):
            time.sleep(0.5)
            if agent.lua("return WCMODS_TEST_NPC:valid() and WCMODS_TEST_NPC.spawns") == 2:
                again = agent.lua(LOOKED_DATA)
                break
        # The tail and ear meshes the game picks for a walking cat aren't set by the look (known gap).
        assert again[:8] == first[:8], (first, again)
    finally:
        agent.lua("if WCMODS_TEST_NPC then WCMODS_TEST_NPC:remove() end")


def test_npc_walks_to_a_place(agent):
    """npc:walkTo moves it with its AI controller and character movement, and says when it got there."""
    try:
        assert agent.lua(SPAWN) is True
        assert agent.lua("return WCMODS_TEST_NPC:actorOrNil().Controller ~= nil") is True
        agent.lua("""
            WCMODS_WALK = nil
            local l = WCMODS_TEST_NPC:location()
            WCMODS_START = { X = l.X, Y = l.Y }
            WCMODS_TEST_NPC:walkTo(l.X + 200 * math.cos(math.rad(90)), l.Y + 200, l.Z,
                { done = function(n, r) WCMODS_WALK = r end })
        """)
        assert agent.lua("return WCMODS_TEST_NPC:walking()") is True
        result = None
        for _ in range(50):
            time.sleep(0.5)
            result = agent.lua("return WCMODS_WALK")
            if result:
                break
        assert result in ("arrived", "blocked"), result
        assert agent.lua("return WCMODS_TEST_NPC:walking()") is False
        moved = agent.lua("local l = WCMODS_TEST_NPC:location(); return math.abs(l.Y - WCMODS_START.Y)")
        assert moved > 100, moved
    finally:
        agent.lua("if WCMODS_TEST_NPC then WCMODS_TEST_NPC:remove() end")


def test_walking_npcs_go_round_each_other(agent):
    """Two cats swapping places walk past each other (and the player's cat); neither is left blocked."""
    try:
        agent.lua("""
            local me = Game.cat():location()
            WCMODS_X = {}
            WCMODS_A = Game.npcs.spawn({ at = { X = me.X + 300, Y = me.Y, Z = me.Z + 100 } })
            WCMODS_B = Game.npcs.spawn({ at = { X = me.X - 300, Y = me.Y, Z = me.Z + 100 } })
            WCMODS_A:walkTo(me.X - 300, me.Y + 20, me.Z, { done = function(n, r) WCMODS_X.a = r end })
            WCMODS_B:walkTo(me.X + 300, me.Y - 20, me.Z, { done = function(n, r) WCMODS_X.b = r end })
        """)
        for _ in range(30):
            time.sleep(0.5)
            if agent.lua("return WCMODS_X.a ~= nil and WCMODS_X.b ~= nil"):
                break
        assert agent.lua("return {WCMODS_X.a, WCMODS_X.b}") == ["arrived", "arrived"]
    finally:
        agent.lua("for _, n in ipairs({ WCMODS_A, WCMODS_B }) do n:remove() end")


def test_a_spawned_npc_has_the_games_own_ai_logic_off(agent):
    """The game's behaviour tree on a spawned cat is left stopped (the game aborted a few minutes after one spawned);
    walkTo is what moves it."""
    try:
        assert agent.lua(SPAWN) is True
        assert agent.lua("return WCMODS_TEST_NPC:actorOrNil().Controller.BrainComponent:IsRunning()") is False
    finally:
        agent.lua("if WCMODS_TEST_NPC then WCMODS_TEST_NPC:remove() end")


def test_a_label_shows_only_near_and_in_sight(agent):
    """The label's opacity is 0 beyond its range, and 1 (not faded) close by with a clear line; the default range is
    1000 cm. A cat given no label shows none (its widget's own design-time text stays hidden)."""
    try:
        agent.lua("""
            local me = Game.cat():location()
            WCMODS_TEST_NPC = Game.npcs.spawn({ at = { me.X + 150, me.Y + 150, me.Z } })
            WCMODS_TEST_NPC:label({ name = "Near" })
            WCMODS_FAR = Game.npcs.spawn({ at = { me.X + 150, me.Y + 150, me.Z } })
            WCMODS_FAR:label({ name = "Far", range = 50 })
            WCMODS_BARE = Game.npcs.spawn({ at = { me.X - 150, me.Y + 150, me.Z } })
        """)
        time.sleep(1.5)
        op = "local ok, v = pcall(function() return %s.labelWidgets.mcGuiActorName:GetRenderOpacity() end) return v"
        assert agent.lua(op % "WCMODS_FAR") == 0
        assert agent.lua(op % "WCMODS_BARE") == 0
        # The same line the label's check draws, from the camera to the cat's head: a rock where the test runs
        # can be in the way, and then the label is rightly hidden.
        clear = agent.lua("""
            local from = Game.controller().PlayerCameraManager:GetCameraLocation()
            local l = WCMODS_TEST_NPC:location()
            local to = { X = l.X, Y = l.Y, Z = l.Z + 60 }
            local hit = Game.trace({ X = from.X, Y = from.Y, Z = from.Z }, to)
            return hit == nil or math.sqrt((to.X - hit.X) ^ 2 + (to.Y - hit.Y) ^ 2 + (to.Z - hit.Z) ^ 2) < 100
        """)
        near = agent.lua(op % "WCMODS_TEST_NPC")
        if not clear:
            assert near == 0, near
            pytest.skip("something is between the camera and the near cat here, so its label is hidden")
        assert near == 1, near
    finally:
        agent.lua("for _, n in ipairs({ WCMODS_TEST_NPC, WCMODS_FAR, WCMODS_BARE }) do n:remove() end")


def test_removing_a_walking_npc_ends_its_walk(agent):
    """npc:remove() on a cat on its way ends the walk at once: done hears "cancelled" and walking() is false."""
    try:
        assert agent.lua(SPAWN) is True
        agent.lua("""
            WCMODS_WALK = nil
            local l = WCMODS_TEST_NPC:location()
            WCMODS_TEST_NPC:walkTo(l.X + 800, l.Y, l.Z, { done = function(n, r) WCMODS_WALK = r end })
        """)
        assert agent.lua("return WCMODS_TEST_NPC:walking()") is True
        agent.lua("WCMODS_TEST_NPC:remove()")
        assert agent.lua("return {WCMODS_WALK, WCMODS_TEST_NPC:walking()}") == ["cancelled", False]
    finally:
        agent.lua("if WCMODS_TEST_NPC then WCMODS_TEST_NPC:remove() end")


def test_a_removed_npc_is_let_go_and_still_listed(agent):
    """npc:remove() takes it out of the keeper's list (it isn't spawned again) but Game.npcs.all() keeps it."""
    try:
        assert agent.lua(SPAWN) is True
        agent.lua("WCMODS_TEST_NPC:remove()")
        time.sleep(1.5)                     # three turns of the keeper
        assert agent.lua("return WCMODS_TEST_NPC:valid()") is False
        assert agent.lua("for _, n in ipairs(Game.npcs.all()) do if n == WCMODS_TEST_NPC then return n.removed end end") is True
    finally:
        agent.lua("if WCMODS_TEST_NPC then WCMODS_TEST_NPC:remove() end")


def test_a_reported_quest_keeps_its_description(agent):
    """Game.quests.report's sixth field: a description goes in and comes back; a quest without one gives ""."""
    try:
        got = agent.lua("""
Game.quests.report("wcmods-test-q", { title = "A test", status = "active", objective = "Do it", progress = "1/2",
                                      by = "tests", description = "A quest\\tabout nothing." })
Game.quests.report("wcmods-test-r", { title = "Another" })
local out = {}
for _, q in ipairs(Game.quests.reported()) do out[q.id] = q end
return { out["wcmods-test-q"].description, out["wcmods-test-q"].by, out["wcmods-test-r"].description }
""")
        assert got == ["A quest about nothing.", "tests", ""], got
    finally:
        agent.lua('Game.quests.report("wcmods-test-q", nil) Game.quests.report("wcmods-test-r", nil)')


def test_drop_refuses_a_tag_that_isnt_one(agent):
    """Game.items.drop takes only one of the game's items (Game.items.isItem: a tag the game has registered, under
    Gameplay.Inventory): no tag, one the game hasn't got and one that isn't an item's are refused, nothing spawned."""
    assert agent.lua("return select(2, Game.items.drop(nil))") == "drop needs an item tag like Gameplay.Inventory.Materials.Moss"
    got = agent.lua("""
        local unknown, cat = "Gameplay.Inventory.Materials.NoSuchThing", "Gameplay.Combat.Character.Cat.Player"
        return { moss = Game.items.isItem("Gameplay.Inventory.Materials.Moss"), unknown = Game.items.isItem(unknown),
                 cat = Game.items.isItem(cat), empty = Game.items.isItem(""), unknownDrop = select(2, Game.items.drop(unknown)),
                 catDrop = select(2, Game.items.drop(cat)) }""")
    assert got == {"moss": True, "unknown": False, "cat": False, "empty": False,
                   "unknownDrop": "Gameplay.Inventory.Materials.NoSuchThing isn't one of the game's items",
                   "catDrop": "Gameplay.Combat.Character.Cat.Player isn't one of the game's items"}, got


MOSS = "Gameplay.Inventory.Materials.Moss"
# Interact, pressed and let go, as the game's controls give it: the controller's input component hears the command.
INTERACT = """
local n = Game.enumNames("/Script/SwtEngine.ECommands").Player_Interact
local input = Game.controller().InputComponent
input:OnListenCommandInternal(n, 0)
input:OnListenCommandInternal(n, 1)
return n
"""


def test_a_drop_lies_in_front_of_your_cat_for_interact(agent):
    """Game.items.drop with no place puts the pickup 50 cm in front of your cat (its forward vector), on the ground,
    where the game's Interact reaches: Interact, as the game's controls give it (the input component's command), collects
    it, Game.items.count goes up by one and the pickup hides. Your cat goes 8 m off its spot first (the test cat stands
    by a den's Travel prompt, which would take the Interact) and back after. The test cat keeps the moss: Lua can't take
    items away."""
    home = agent.lua("local l = Game.cat():location() return { l.X, l.Y, l.Z }")
    try:
        agent.lua(f"""
            local x, y = {home[0]} - 800, {home[1]}
            local g = Game.ground(x, y, {home[2]})
            return Game.cat():teleport(x, y, (g or {home[2]}) + 60)""")
        time.sleep(1.0)
        got = agent.lua(f"""
            local me = Game.player()
            local at = Game.cat():location()
            local f = me:GetActorForwardVector()
            WCMODS_TEST_MOSS_BEFORE = Game.items.count("{MOSS}")
            local p, why = Game.items.drop("{MOSS}", 1)
            WCMODS_TEST_DROP = p
            if not p then return {{ why = why }} end
            local l = p:K2_GetActorLocation()
            return {{ dx = l.X - at.X, dy = l.Y - at.Y, fx = f.X, fy = f.Y, z = l.Z, catZ = at.Z }}""")
        assert "why" not in got, got
        off = ((got["dx"] - got["fx"] * 50) ** 2 + (got["dy"] - got["fy"] * 50) ** 2) ** 0.5
        assert off < 1 and got["z"] < got["catZ"], got   # 50 cm in front, on the ground below the cat's middle
        time.sleep(0.7)   # the game sees the cat in the pickup's reach a frame or more later
        agent.lua(INTERACT)
        agent.wait(lambda: agent.lua(f'return Game.items.count("{MOSS}") == WCMODS_TEST_MOSS_BEFORE + 1'), 4,
                   "Interact to collect the dropped moss")
        assert agent.lua("return WCMODS_TEST_DROP.bHidden") is True
    finally:
        agent.lua("if WCMODS_TEST_DROP and WCMODS_TEST_DROP:IsValid() then WCMODS_TEST_DROP:K2_DestroyActor() end "
                  "WCMODS_TEST_DROP = nil return true")
        agent.teleport(*home)


# The bridge's own box (each Lua state has its own), from Game.dialogue's upvalues.
TALK_BOX = """
local function talkState()
    for i = 1, 50 do
        local n, v = debug.getupvalue(Game.dialogue.showing, i)
        if n == nil then return nil end
        if n == "talk" then return v end
    end
end
"""


def _out_of_the_talk(agent):
    """Wait for the box's fade-out to end and your cat to be out of the talk: in one, the game takes no key of its
    controls (the inventory's I, in test_screens)."""
    agent.wait(lambda: agent.lua("return Game.get(Game.controller(), 'WCM_TalkFlags') == 0"), 3,
               "the talk flags to clear after the box went")


def test_the_talk_box_lets_your_cat_go(agent):
    """The box's own code puts your cat "in a talk" (the controller's talk flags, 0x21; no animal notices it while
    they're on): Game.dialogue.hide() clears them once the box is gone, back to what they were (0)."""
    before = agent.lua("return Game.get(Game.controller(), 'WCM_TalkFlags')")
    assert before == 0, before
    try:
        assert agent.lua('return (Game.dialogue.say("Brindlemoon", "Good hunting."))') is True
        time.sleep(0.5)
        assert agent.lua("return Game.get(Game.controller(), 'WCM_TalkFlags')") == 0x21
        agent.lua("Game.dialogue.hide() return true")
        _out_of_the_talk(agent)
        assert agent.lua("return Game.dialogue.showing()") is False
    finally:
        agent.lua("Game.dialogue.hide() return true")
        _out_of_the_talk(agent)


def test_a_line_said_as_the_box_fades_out_brings_it_back(agent):
    """say() while hide()'s fade-out plays: the box plays its fade-in again (it was left faded, with the new line in
    it, before) and stays up, in a talk."""
    try:
        agent.lua(TALK_BOX + """
            WCMODS_TEST_FADE = {}
            Game.dialogue.say("Brindlemoon", "First line.")
            local w = talkState().widget
            Game.after(0.6, function()
                Game.dialogue.hide()
                Game.after(0.1, function()
                    WCMODS_TEST_FADE.fadingOut = w:IsAnimationPlaying(w.AniScreenOut)
                    Game.dialogue.say("Brindlemoon", "Second line.")
                    WCMODS_TEST_FADE.fadingIn = w:IsAnimationPlaying(w.AniScreenIn)
                    Game.after(0.8, function()
                        WCMODS_TEST_FADE.inView = w:IsInViewport()
                        WCMODS_TEST_FADE.showing = Game.dialogue.showing()
                        WCMODS_TEST_FADE.flags = Game.get(Game.controller(), "WCM_TalkFlags")
                    end)
                end)
            end)
            return true""")
        got = agent.wait(lambda: agent.lua("return WCMODS_TEST_FADE.flags and WCMODS_TEST_FADE"), 5, "the box's fade-in")
        assert got == {"fadingOut": True, "fadingIn": True, "inView": True, "showing": True, "flags": 0x21}, got
    finally:
        agent.lua("Game.dialogue.hide() WCMODS_TEST_FADE = nil return true")
        _out_of_the_talk(agent)


def test_screens(agent):
    open_now = agent.lua("return Game.screens()") or []
    assert not open_now, f"a screen is already open: {open_now}"
    agent.key("I")
    try:
        shown = []
        for _ in range(8):
            time.sleep(0.5)
            shown = agent.lua("return Game.screens()") or []
            if shown:
                break
        assert any("Inventory" in s for s in shown), shown
    finally:
        time.sleep(1)                   # it doesn't take keys while it opens
        for _ in range(4):
            agent.key("BackSpace")      # the inventory's Back
            time.sleep(1)
            if agent.lua("return #Game.screens()") == 0:
                break
    assert agent.lua("return #Game.screens()") == 0
