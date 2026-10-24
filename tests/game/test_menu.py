"""The mod menu: every page draws, and the pages' controls do what they say."""
import time

from wcmods.agent import skip


def setup(agent):
    # The mod menu is a mod of its own (mods/mod-menu); without it there's nothing here to test.
    if not agent.menu.pages():
        skip("the mod menu isn't in the game (is the Mod menu mod on?)")


def teardown(agent):
    agent.menu.close()


def test_every_page_draws(agent):
    """Each page opens without an error and shows something; a picture of each goes in the report."""
    pages = agent.menu.pages()
    assert len(pages) >= 10, [p["title"] for p in pages]
    bad = {}
    for p in pages:
        page = agent.menu.open(p["id"])
        if page.errors() or not page.rows:
            bad[p["title"]] = page.errors() or "no rows"
        agent.menu.shot("page-" + p["title"], scale=0.6)
    assert not bad, bad


def test_status_line_and_overview(agent):
    page = agent.menu.open("Overview")
    cat = agent.cat()
    assert page.has(cat["name"]), page.text()
    assert page.find("Heal", "button") and page.find("Morning", "button"), page.text()


def test_stats_page_matches_the_cat(agent):
    cat = agent.cat()
    page = agent.menu.open("Stats")
    assert page.get("Name") == cat["name"], page.get("Name")
    assert page.get("Level") == cat["level"], page.get("Level")
    assert page.find("Health").value == cat["health"]


def test_health_slider_and_heal(agent):
    page = agent.menu.open("Stats")
    full = page.find("Health").options[1]
    agent.menu.set("Health", full - 20)
    assert agent.cat()["health"] == full - 20
    agent.menu.open("Overview")
    agent.menu.press("Heal")
    assert agent.cat()["health"] == full


def test_hold_the_time(agent):
    """World's "Hold this time" keeps the clock where it is while it's on."""
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
    page = agent.menu.open("Items")
    assert page.find("Item", "choice"), page.text()
    assert page.find("How many", "number")
    assert page.has("Herbs and pouches") or page.has("Nothing yet"), page.text()


def test_quests_page(agent):
    page = agent.menu.open("Quests")
    assert page.has("quests in all"), page.text()
    for show in ("Available", "Done", "All", "Active"):
        agent.menu.set("Show", show)
        assert agent.menu.read().get("Show") == show


def test_log_page(agent):
    agent.menu.open("Log")
    agent.menu.set("Show", "Everything")
    page = agent.menu.read()
    assert len([r for r in page.rows if r.kind == "note"]) > 5, page.text()
    agent.menu.set("Show", "Mods")


def test_console_page(agent):
    if not any(p["id"] == "Console" for p in agent.menu.pages()):
        skip("the Console page is only there with code mods allowed")
    agent.menu.open("Console")
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
    """A script mod's automatic settings page (examples/game-tweaks, when it's installed)."""
    ids = [p["id"] for p in agent.menu.pages()]
    if "script:game-tweaks" not in ids:
        skip("Game Tweaks isn't installed (agent install --with examples/game-tweaks)")
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
