"""Cats of a mod's own (Game.npcs), the game's screens (Game.screens), and a mod's quests on the mod menu
(Game.quests.report)."""
import time

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
local m = a.SkeletalMeshComponent:GetMaterial(0)
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
        assert agent.lua(LOOKED_DATA) == first
        agent.lua("WCMODS_TEST_NPC:actorOrNil():K2_DestroyActor()")
        again = None
        for _ in range(20):
            time.sleep(0.5)
            if agent.lua("return WCMODS_TEST_NPC:valid() and WCMODS_TEST_NPC.spawns") == 2:
                again = agent.lua(LOOKED_DATA)
                break
        assert again == first, (first, again)
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
    assert agent.lua("return select(2, Game.items.drop(nil))") == "drop needs an item tag like Gameplay.Inventory.Materials.Moss"


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
