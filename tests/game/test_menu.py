"""The mod menu: every page draws, and the pages' controls do what they say. The window and its own pages
(Overview, Installed mods, Log, Menu, and the Inspector and Lua console with code mods allowed) are wcmods';
the pages about the game are the Menu pages mod's, so their tests skip without it (python wcmods.py
menu-pages, or Get set up in Clan Mod Studio, then install with code mods allowed)."""
import time

from wcmods import menupages
from wcmods.agent import skip
from wcmods.sections import scripts

WINDOW = ("Overview", "Installed mods", "Log", "Menu")   # the window's own pages, always there


def setup(agent):
    # The window goes in with every install while UE4SS is there.
    if not agent.menu.pages():
        skip("the mod menu isn't in the game (is UE4SS installed, and wcmods installed since?)")


def teardown(agent):
    agent.menu.close()


def need_pages(agent):
    """Skip a test of the Menu pages mod's pages when it isn't in the game; fail when it was installed but its
    pages aren't there (its script didn't load)."""
    if any(p["id"] == "At a glance" for p in agent.menu.pages()):
        return
    agent.cfg.reload()
    installed = scripts.ue4ss_name(menupages.ID) in (agent.cfg.data.get("installed_ue4ss") or [])
    assert not installed, (f"{scripts.ue4ss_name(menupages.ID)} is installed but its pages aren't in the menu: "
                           "its script didn't load (the Log page, or UE4SS.log, says why)")
    skip("the Menu pages mod isn't in the game (agent install --with ../wcmods-menu-pages/menu-pages)")


def test_every_page_draws(agent):
    """Each page opens without an error and shows something; a picture of each goes in the report."""
    pages = agent.menu.pages()
    titles = [p["title"] for p in pages]
    assert all(t in titles for t in WINDOW), titles
    bad = {}
    for p in pages:
        page = agent.menu.open(p["id"])
        if page.errors() or not page.rows:
            bad[p["title"]] = page.errors() or "no rows"
        agent.menu.shot("page-" + p["title"], scale=0.6)
    assert not bad, bad


def test_overview_keys_and_whats_where(agent):
    """The window's Overview: its keys, each group's pages, and how to get the Menu pages mod while it's not in."""
    page = agent.menu.open("Overview")
    assert page.find("Keys", "section") and page.find("What's where", "section"), page.text()
    assert page.get("Escape") == "Close this menu", page.text()
    assert page.has("Installed mods"), page.text()   # Home's pages, under "What's where"
    if not any(p["id"] == "At a glance" for p in agent.menu.pages()):
        assert page.has("Menu pages"), page.text()


def test_at_a_glance(agent):
    need_pages(agent)
    page = agent.menu.open("At a glance")
    cat = agent.cat()
    assert page.has(cat.get("name") or "?"), page.text()   # the page shows "?" for a cat with no name
    assert page.find("Heal", "button") and page.find("Morning", "button"), page.text()


def test_stats_page_matches_the_cat(agent):
    need_pages(agent)
    cat = agent.cat()
    page = agent.menu.open("Stats")
    assert page.get("Name") == (cat.get("name") or "?"), page.get("Name")
    assert page.get("Level") == cat["level"], page.get("Level")
    assert page.find("Health").value == cat["health"]


def test_health_slider_and_heal(agent):
    need_pages(agent)
    page = agent.menu.open("Stats")
    full = page.find("Health").options[1]
    agent.menu.set("Health", full - 20)
    assert agent.cat()["health"] == full - 20
    agent.menu.open("At a glance")
    agent.menu.press("Heal")
    assert agent.cat()["health"] == full


def test_hold_the_time(agent):
    """World's "Hold this time" keeps the clock where it is while it's on."""
    need_pages(agent)
    agent.menu.open("World")
    agent.menu.press("Noon")
    agent.menu.set("Hold this time", True)
    try:
        held = agent.lua("return Game.time.seconds()")
        time.sleep(3)     # a game day takes about 20 minutes: 3 s is about 3.5 game minutes
        now = agent.lua("return Game.time.seconds()")
        assert abs(now - held) < 90, f"the clock moved from {held:.0f} to {now:.0f}"
        assert agent.menu.read().get("Hold this time") is True
    finally:
        agent.menu.set("Hold this time", False)
    time.sleep(2)
    assert agent.lua("return Game.time.seconds()") != held, "the clock should run again"


def test_travel_save_spot_and_forget(agent):
    need_pages(agent)
    name = "agent test spot"
    agent.menu.open("Travel")
    agent.menu.set("Name for a saved spot", name)
    agent.menu.press("Save this spot")
    page = agent.menu.read()
    go = page.find("Go: " + name)
    assert go, page.text()
    # Its Forget button is the next row (one row of two buttons); by place, so another spot's stays.
    agent.menu.press(f"@{go.n + 1}")
    assert not agent.menu.read().find("Go: " + name), "the spot should be gone"


def test_travel_jump_and_back(agent):
    need_pages(agent)
    page = agent.menu.open("Travel")
    sections = [r.label for r in page.rows if r.kind == "section" and r.label.startswith("Areas: ")]
    if not sections:
        skip("no areas found to travel to")
    start = agent.location()
    agent.menu.section(sections[0])
    page = agent.menu.read()
    at = page.find(sections[0]).n
    target = next((r for r in page.rows if r.n > at and r.kind == "button"), None)
    assert target, page.text()
    agent.menu.press(f"@{target.n}")
    time.sleep(1)
    moved = agent.location()
    assert sum((a - b) ** 2 for a, b in zip(moved, start)) ** 0.5 > 300, f"didn't jump: {start} -> {moved}"
    agent.shot("after-jump", scale=0.5)
    agent.menu.press("Back")
    time.sleep(1)
    back = agent.location()
    assert sum((a - b) ** 2 for a, b in zip(back, start)) ** 0.5 < 300, f"Back didn't return: {start} -> {back}"
    agent.menu.section(sections[0], open=False)


def test_items_page(agent):
    need_pages(agent)
    page = agent.menu.open("Items")
    assert page.find("Item", "choice"), page.text()
    assert page.find("How many", "number")
    assert page.has("Herbs and pouches") or page.has("Nothing yet"), page.text()


def test_quests_page(agent):
    need_pages(agent)
    page = agent.menu.open("Quests")
    assert page.has("quests in all"), page.text()
    for show in ("Available", "Done", "All", "Active"):
        agent.menu.set("Show", show)
        assert agent.menu.read().get("Show") == show


def test_cheats_page_switches_cheats_on_and_off(agent):
    need_pages(agent)
    agent.menu.open("Cheats")
    page = agent.menu.read()
    assert page.find("Start with cheats on"), page.text()
    was = page.get("Cheats")
    agent.menu.set("Cheats", True)
    assert agent.menu.read().find("God mode (nothing hurts you)"), agent.menu.read().text()
    agent.menu.set("Cheats", bool(was))


def test_log_page(agent):
    agent.menu.open("Log")
    agent.menu.set("Show", "Everything")
    page = agent.menu.read()
    assert len([r for r in page.rows if r.kind == "note"]) > 5, page.text()
    agent.menu.set("Show", "Mods")


def test_console_page(agent):
    if not any(p["id"] == "Lua console" for p in agent.menu.pages()):
        skip("the Lua console page is only there with code mods allowed")
    agent.menu.open("Lua console")
    agent.menu.set("Lua", "6 * 7")
    agent.menu.press("Run")
    assert agent.menu.read().has("42"), agent.menu.read().text()
    agent.menu.press("Clear")


def test_inspector_opens_your_cat(agent):
    if not any(p["id"] == "Inspector" for p in agent.menu.pages()):
        skip("the Inspector page is only there with code mods allowed")
    agent.menu.open("Inspector")
    agent.menu.press("Your cat")
    page = agent.menu.read()
    assert page.find("Properties", "section"), page.text()


def test_script_settings_page(agent):
    """A script mod's automatic settings page (wcmods-examples' game-tweaks, when it's installed)."""
    ids = [p["id"] for p in agent.menu.pages()]
    if "script:game-tweaks" not in ids:
        skip("Game Tweaks isn't installed (agent install --with ../wcmods-examples/game-tweaks)")
    page = agent.menu.open("script:game-tweaks")
    assert page.find("Heal key", "input"), page.text()
    assert page.find("Save", "button")


def test_insert_opens_and_closes(agent):
    """The menu's own key, pressed for real (UE4SS key binds read the keyboard)."""
    if not agent.status()["foreground"]:
        skip("the game isn't in front, and a real key press would go to another window")
    agent.menu.close()
    agent.hotkey("Insert")
    agent.wait(agent.menu.is_open, 5, "Insert to open the menu")
    agent.hotkey("Insert")
    agent.wait(lambda: not agent.menu.is_open(), 5, "Insert to close the menu")
