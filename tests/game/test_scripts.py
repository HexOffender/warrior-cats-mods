"""The script runtime in the game: a script's errors carry its mod's name and are said once, a misspelt key doesn't
stop a script, another cat's level isn't yours, a task can cancel itself and add another, a script that doesn't
start is named, and a script's settings page saves and says so. The throwaway mods go in with a test install:

    python wcmods.py agent install --with tests/game/mods/noisy-script --with tests/game/mods/broken-script

The tests that need one skip without it; the bridge's own tests need nothing more."""
import json
import os
import time

from wcmods import scriptlog
from wcmods.agent import skip
from wcmods.sections import scripts

HERE = os.path.dirname(os.path.abspath(__file__))
NOISY = os.path.join(HERE, "mods", "noisy-script")


def need(agent, mod_id):
    """Skip unless the last install put the mod's script in the game."""
    agent.cfg.reload()
    if scripts.ue4ss_name(mod_id) not in (agent.cfg.data.get("installed_ue4ss") or []):
        skip(f"{mod_id} isn't in the game (agent install --with tests/game/mods/{mod_id})")


def lines_with(agent, text, mark=0):
    return [line for line in agent.log_since(mark) if text in line]


def test_frame_error_is_logged_once_with_the_mods_name(agent):
    """A frame function that fails every frame: one line with the mod's name, then at most one a minute with a
    count, never one a frame."""
    need(agent, "noisy-script")
    said = lines_with(agent, "[Noisy script] error in onFrame:")
    assert said, "the frame function's error isn't in the log with the mod's name"
    assert "attempt to index a nil value (local 'cat')" in said[0] and "scripts/main.lua:" in said[0], said[0]
    assert not said[0].rstrip().endswith("more)"), said[0]
    assert all(line.rstrip().endswith("more)") for line in said[1:]), said[1:]
    mark = agent.log_mark()
    time.sleep(2)
    assert len(lines_with(agent, "[Noisy script] error in onFrame:", mark)) <= 1, "said again within two seconds"


def test_bad_key_does_not_stop_the_script(agent):
    need(agent, "noisy-script")
    log = agent.log_since(0)
    bad = [i for i, line in enumerate(log) if "[Noisy script] no key called f6" in line]
    went_on = [i for i, line in enumerate(log) if "[Noisy script] still here" in line]
    assert bad and went_on and bad[0] < went_on[-1], "the misspelt key should be said, and the script go on after it"
    assert "did you mean F6?" in log[bad[0]], log[bad[0]]


def test_a_task_that_cancels_itself_and_adds_another_is_fine(agent):
    """In the bridge's own Lua state (it has its own scheduler): no "invalid key to 'next'", and the new task runs."""
    mark = agent.log_mark()
    agent.lua("""
WCMODS_T = 0
local id
id = Game.onFrame(function()
    Game.cancel(id)
    Game.after(0, function() WCMODS_T = 1 end)
end)
""")
    agent.wait(lambda: agent.lua("return WCMODS_T") == 1, 5, "the task added by a task that cancelled itself")
    assert not lines_with(agent, "invalid key to 'next'", mark)


def test_on_key_gives_an_id_that_cancels_it_and_false_for_a_wrong_name(agent):
    ids = agent.lua("""
local id = Game.onKey("F9", function() end)
local bad = Game.onKey("f9", function() end)
Game.cancel(id)
return type(id), bad
""")
    assert ids == ["number", False], ids


def test_another_cats_level_is_nil(agent):
    """A cat of a mod's own beside yours: its level, xp and stats are nil, and setting them says why, while yours
    are numbers. One object read, no scans; the cat goes again after."""
    try:
        assert agent.lua("""
local me = Game.cat():location()
WCMODS_TEST_NPC = Game.npcs.spawn({ at = { me.X + 150, me.Y + 150, me.Z }, yaw = 90 })
return WCMODS_TEST_NPC:valid()
""") is True
        agent.wait(lambda: agent.lua("return WCMODS_TEST_NPC:actorOrNil() ~= nil"), 10, "the cat to be in the world")
        r = agent.lua("""
local other = Game.cat(WCMODS_TEST_NPC:actorOrNil())
local ok, why = other:setLevel(3)
return { other = other:level(), xp = other:xp(), stats = other:stats(), set = ok, why = why, mine = Game.cat():level() }
""")
        assert r.get("other") is None and r.get("xp") is None and r.get("stats") is None, r
        assert r["set"] is False and r["why"] == "only your cat has a level component out of a fight", r
        assert isinstance(r["mine"], int) and r["mine"] >= 1, r
    finally:
        agent.lua("if WCMODS_TEST_NPC then WCMODS_TEST_NPC:remove() WCMODS_TEST_NPC = nil end")


def test_a_script_that_doesnt_load_is_named(agent):
    """broken-script's main.lua is missing an end: the log says so by file and line, the studio's card would say
    "Didn't load", and the mod menu's Overview lists it in red."""
    need(agent, "broken-script")
    found = scriptlog.report(agent.cfg, [m for m in _mods(agent) if m.id == "broken-script"])
    entry = found["mods"].get("broken-script")
    assert entry and entry["started"] and entry["state"] == "failed", entry
    assert entry["errors"][0].startswith("scripts/main.lua:"), entry["errors"]
    page = agent.menu.open("Overview")
    assert page.has("Broken script didn't start"), page.text()
    agent.menu.close()


def test_report_has_the_scripts_runtime_error(agent):
    need(agent, "noisy-script")
    entry = scriptlog.report(agent.cfg, [m for m in _mods(agent) if m.id == "noisy-script"])["mods"]["noisy-script"]
    assert entry["loaded"] and entry["state"] == "errors", entry
    assert entry["errors"][0].startswith("onFrame: scripts/main.lua:"), entry["errors"]
    assert any(line.endswith("still here") for line in entry["lines"]), entry["lines"]


def test_save_on_the_settings_page_says_so_and_keeps_an_empty_list(agent):
    """Noisy script's automatic settings page: change a number, Save; the page says "Saved to settings.json.", and
    the file keeps its empty list and its other numbers as they were. The file is put back after."""
    need(agent, "noisy-script")
    path = os.path.join(NOISY, "settings.json")
    with open(path, encoding="utf-8") as f:
        before = f.read()
    try:
        page = agent.menu.open("script:noisy-script")
        assert page.find("Speed"), page.text()
        agent.menu.set("Speed", 2.5)
        agent.menu.press("Save")
        page = agent.wait(lambda: (lambda p: p if p.has("Saved to settings.json.") else None)(agent.menu.read()), 5,
                          "the page to say it saved")
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["keys"] == [] and saved["speed"] == 2.5 and saved["ratio"] == 0.1234567, saved
    finally:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(before)
        agent.menu.close()


def _mods(agent):
    """Your mods and the test install's own (--with), as the build saw them."""
    from wcmods import mods as modlib
    found = modlib.discover(agent.cfg.mods_root)
    for folder in ("noisy-script", "broken-script"):
        found.append(modlib.Mod(os.path.join(HERE, "mods", folder)))
    return found
