"""The game's own animations without a file (animations.json's "game"; docs/SDK.md, Animations), in the game.

tests/animations-mod plays the game's Yawn as an emote on F7, its Stretch with the claws out (a copy) on F8,
both looping, and puts the sleep loop in the trot's place. It has to be installed first, with the game closed:

    python wcmods.py agent install --with tests/animations-mod
    python wcmods.py agent test -k animations --launch

Not run yet: written with the change that added "game" (2026-10-28), for the next pass in the game. The emote
script's montage lives in its own Lua state, so the bridge reads the anim instance (IsAnyMontagePlaying), as
docs/reverse-engineering.md says.
"""
import threading
import time

from wcmods.agent import skip

NEEDS = "world"
MOD = "animations-mod"
PLAYING = "Game.player().Mesh:GetAnimInstance():IsAnyMontagePlaying()"
# How far the head is above the root bone, in cm (the sleep loop curls the cat up: under 3.5 cm while it
# moves, against about 14 with the game's trot; docs/verified.md, 2026-10-27).
HEAD_ABOVE_ROOT = """local m = Game.player().Mesh
local h, r = m:GetSocketLocation(FName("head")), m:GetSocketLocation(FName("root"))
return h.Z - r.Z"""


def setup(agent):
    if not agent.lua(f'return Game.anims.list()["{MOD}/Yawn"] ~= nil'):
        skip(f"the animations test mod isn't in the game: python wcmods.py agent install --with tests/{MOD} "
             "(with the game closed)")


def _toggle(agent, key):
    agent.key(key)
    time.sleep(0.3)


def test_a_game_animation_plays_as_an_emote(agent):
    """F7 plays the game's Yawn on your cat by its own path (no package made), and F7 again stops it."""
    assert agent.lua(f'return Game.anims.list()["{MOD}/Yawn"].path') == \
        "/Game/Art/Characters/CatMaster/Animations/A_CatMaster_Yawn_1.A_CatMaster_Yawn_1"
    try:
        _toggle(agent, "F7")
        assert agent.wait_lua(PLAYING, timeout=5, what="the yawn to play")
    finally:
        _toggle(agent, "F7")
    agent.wait(lambda: not agent.lua("return " + PLAYING), timeout=5, what="the yawn to stop")


def test_claws_out_on_a_game_animation(agent):
    """F8 plays the copy of the game's Stretch with the claws out: its package loads and plays, and the
    claws' curve is down while it does."""
    assert agent.lua(f'return Game.anims.list()["{MOD}/Stretch"].path') == f"/Game/WCMods/{MOD.replace('-', '_')}/A_Stretch.A_Stretch"
    try:
        _toggle(agent, "F8")
        assert agent.wait_lua(PLAYING, timeout=5, what="the stretch to play")
        time.sleep(0.5)
        claws = agent.lua('local ok, v = pcall(function() return Game.player().Mesh:GetAnimInstance()'
                          ':GetCurveValue(FName("shp_claw_hiden_l")) end) return ok and v or nil')
        if claws is not None:
            assert claws < 0.5, f"the claws' curve is {claws}: still in"
        agent.shot("claws-out")
    finally:
        _toggle(agent, "F8")
    agent.wait(lambda: not agent.lua("return " + PLAYING), timeout=5, what="the stretch to stop")


def test_the_trot_can_be_another_game_animation(agent):
    """With W held the cat trots, and the trot is now the game's sleep loop: its head stays low."""
    start = agent.location()
    heights = []
    try:
        standing = agent.lua(HEAD_ABOVE_ROOT)
        walking = threading.Thread(target=agent.key, args=("W",), kwargs={"hold": 2.0})
        walking.start()
        time.sleep(0.8)
        for _ in range(8):
            heights.append(agent.lua(HEAD_ABOVE_ROOT))
            time.sleep(0.12)
        walking.join()
    finally:
        agent.teleport(*start)
    assert standing > 10, f"standing, the head is {standing:.1f} cm above the root: not the game's idle"
    assert max(heights) < 3.5 + 1.5, f"trotting, the head is {min(heights):.1f} to {max(heights):.1f} cm above the root"
