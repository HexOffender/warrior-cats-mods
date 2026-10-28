"""Tweaks in the game (tweaks.json, WCModsTweaks): stamina kept full, the clock held, the fresh-kill pile kept up, the
heal key, and the mod menu's Tweaks page with its Save. The throwaway mod goes in with a test install:

    python wcmods.py agent install --with tests/game/mods/all-tweaks

The tests skip without it. The story's scenes skip is checked by hand, on a fresh story cat (not a sandbox one)."""
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
    """The game's own input hears a key the agent posts to its window: F7 heals."""
    if not agent.status()["foreground"]:
        skip("the game isn't in front, and the heal key listens to the game's own input")
    agent.lua("local c = Game.cat() c:setHealth(c:maxHealth() / 2)")
    agent.key("F7")
    agent.wait(lambda: agent.lua("local c = Game.cat() return c:health() >= c:maxHealth() - 0.01"), 3, "F7 to heal")


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
        agent.lua("Game.time.set(9, 0, 0)")
        time.sleep(0.5)
