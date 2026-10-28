"""Tweaks in the game (tweaks.json, WCModsTweaks): stamina kept full, the clock held, the fresh-kill pile kept up, the
heal key, and the mod menu's Tweaks page with its Save. The throwaway mod goes in with a test install:

    python wcmods.py agent install --with tests/game/mods/all-tweaks

The tests skip without it.

Skipping the story's scenes is refused (wcmods/tweaks.py, UNCHECKED) until it's checked by hand, on a fresh story
cat (not a sandbox one, whose scenes Sandbox mode skips itself): set WCMODS_UNCHECKED_TWEAKS=1 where the install
runs, then

    python wcmods.py agent install --with tests/game/mods/all-tweaks --with tests/game/mods/skip-scenes

start a new story cat, and watch each opening scene skip ("[Tweaks] skipping the story's ..." in the log) and the
story go on: the first quest step comes, and the apprentice ceremony gives the rank. Then a story step that a later
scene ends (a ceremony, a quest's last scene) on a saved story cat. If all of that holds, take skip_scenes out of
UNCHECKED; test_skip_scenes_is_on_for_the_hand_check checks the install is the right one."""
import os
import time

from wcmods import tweaks
from wcmods.agent import skip

HERE = os.path.dirname(os.path.abspath(__file__))
TWEAKS = os.path.join(HERE, "mods", "all-tweaks", tweaks.FILE)


def setup(agent):
    agent.cfg.reload()
    if tweaks.UE4SS_MOD_NAME not in (agent.cfg.data.get("installed_ue4ss") or []):
        skip("the tweaks aren't in the game (agent install --with tests/game/mods/all-tweaks)")


def teardown(agent):
    agent.menu.close()


def test_stamina_stays_full(agent):
    agent.key("W", hold=3)
    agent.wait(lambda: agent.lua("local c = Game.cat() return c:stamina() >= c:maxStamina() - 0.01"), 3,
               "stamina to be topped up")


def test_clock_holds(agent):
    agent.lua("Game.time.set(15, 0, 0)")
    agent.wait(lambda: abs(agent.lua("return Game.time.seconds()") - 9 * 3600) < 120, 3, "the clock to go back to 09:00")


def test_fresh_kill_floor(agent):
    agent.lua("Game.freshKill.set(10)")
    agent.wait(lambda: agent.lua("return Game.freshKill.value()") >= 40, 3, "the pile to be back at 40")


def test_heal_key(agent):
    """The game's own input hears a key the agent posts to its window: F4 heals (F7 and F8 are the animations test
    mod's emotes, in the same install)."""
    if not agent.status()["foreground"]:
        skip("the game isn't in front, and the heal key listens to the game's own input")
    agent.lua("local c = Game.cat() c:setHealth(c:maxHealth() / 2)")
    agent.key("F4")
    agent.wait(lambda: agent.lua("local c = Game.cat() return c:health() >= c:maxHealth() - 0.01"), 3, "F4 to heal")


def test_skip_scenes_is_on_for_the_hand_check(agent):
    """Only with the hand check's install (above): the log says the skip is on, and the mod menu's Tweaks page has
    its switch. Whether a skipped scene keeps the story's steps is the hand check's to see."""
    on = [line for line in agent.log_since(0) if "[Tweaks] on:" in line]
    if not on or "the story's scenes skipped" not in on[-1]:
        skip("skipping the story's scenes isn't in the game (WCMODS_UNCHECKED_TWEAKS=1, then agent install --with "
             "tests/game/mods/skip-scenes)")
    page = agent.menu.open("Tweaks")
    assert page.find("Skip the story's scenes"), page.text()


def test_the_tweaks_page_saves(agent):
    with open(TWEAKS, encoding="utf-8") as f:
        before = f.read()
    try:
        page = agent.menu.open("Tweaks")
        assert page.find("Keep my cat's stamina full") and page.find("Heal my cat with a key"), page.text()
        agent.menu.set("At", 21)
        agent.menu.press("Save")
        page = agent.wait(lambda: (lambda p: p if p.has("Saved to mods/") else None)(agent.menu.read()), 5, "the page to save")
        import json
        with open(TWEAKS, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["time_of_day"] == 21.0 and saved["_help"].startswith("tests/game/test_tweaks.py"), saved
    finally:
        with open(TWEAKS, "w", encoding="utf-8", newline="\n") as f:
            f.write(before)
        # The page changed the tweaks in the game too: the clock held at 21:00 until they're put back.
        agent.menu.open("Tweaks")
        agent.menu.press("Back to installed")
        agent.lua("Game.time.set(9, 0, 0)")
        time.sleep(0.5)
