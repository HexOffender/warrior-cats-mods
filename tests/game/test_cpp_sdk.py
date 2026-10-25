"""The C++ SDK (docs/SDK.md, "C++ mods"), checked in the game.

tests/cpp-sdk is a C++ mod that calls everything the SDK documents and records what it got in
tests/cpp-sdk/results.json. These tests read that, compare it with what Lua sees of the same things, and ask
the mod to make changes that Lua then confirms. It has to be built and installed first, with the game closed:

    python wcmods.py cpp build tests/cpp-sdk
    python wcmods.py agent install --with tests/cpp-sdk
    python wcmods.py agent test tests/game/test_cpp_sdk.py --launch

"""
import filecmp
import json
import os
import time

from wcmods.agent import AgentError, skip
from wcmods.sections.cpp import source_time

NEEDS = "world"
MOD_DIR = os.path.join("tests", "cpp-sdk")
UE4SS_NAME = "WCModsCpp_cpp_sdk"
DEV_SWITCH = "bAllowAlwaysEquipItem"
CVAR = "r.ScreenPercentage"


def _folder(agent):
    return os.path.join(agent.root, MOD_DIR)


def _results(agent):
    path = os.path.join(_folder(agent), "results.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except ValueError:   # half written
            return None


def _ready(agent, phase, timeout=30):
    """results.json once the mod has finished `phase`."""
    end = time.time() + timeout
    while time.time() < end:
        r = _results(agent)
        if r and phase in r.get("done", []):
            return r
        time.sleep(0.2)
    r = _results(agent)
    raise AssertionError(f"the C++ test mod didn't finish its {phase} phase in {timeout} s "
                         f"(results.json: {'missing' if not r else 'done ' + str(r.get('done'))})")


def _request(agent, what, timeout=30):
    """Ask the mod to run a phase (it looks for request.txt four times a second) and wait for it: the
    results once one more phase has finished than before, so a phase asked for twice is run twice."""
    r = _results(agent)
    served = r.get("served", 0) if r else 0
    with open(os.path.join(_folder(agent), "request.txt"), "w", encoding="utf-8") as f:
        f.write(what)
    end = time.time() + timeout
    while time.time() < end:
        r = _results(agent)
        if r and r.get("served", 0) > served and what in r.get("done", []):
            return r
        time.sleep(0.2)
    raise AssertionError(f"the C++ test mod didn't run its {what} phase in {timeout} s")


def _failed(results, phase):
    return [f"{c['name']}: {c['detail']}" if c["detail"] else c["name"]
            for c in results["checks"] if c["phase"] == phase and not c["ok"]]


def setup(agent):
    """The mod in the game must be the one built from the source here, or the results mean nothing."""
    built = os.path.join(_folder(agent), "dlls", "main.dll")
    installed = os.path.join(agent.cfg.ue4ss_mods_dir, UE4SS_NAME, "dlls", "main.dll")
    if not os.path.isfile(built):
        skip("the C++ SDK test mod isn't built: python wcmods.py cpp build tests/cpp-sdk")
    if source_time(os.path.join(_folder(agent), "cpp")) > os.path.getmtime(built):
        skip("tests/cpp-sdk's source changed after its main.dll was built: python wcmods.py cpp build tests/cpp-sdk")
    if not os.path.isfile(installed):
        skip("the C++ SDK test mod isn't in the game: python wcmods.py agent install --with tests/cpp-sdk "
             "(with the game closed)")
    if not filecmp.cmp(built, installed, shallow=False):
        skip("the C++ SDK test mod in the game isn't the one built here: python wcmods.py agent install --with "
             "tests/cpp-sdk (with the game closed)")


def test_mod_loads(agent):
    """UE4SS starts the mod from its DLL (ModBase, WCMODS_MOD), and it writes results.json at init."""
    assert any(f"Starting C++ mod '{UE4SS_NAME}'" in line for line in agent.log_since(0)), "UE4SS didn't start the mod"
    r = _ready(agent, "init")
    assert r["passed"] > 0, r


def test_core(agent):
    """Core.hpp: the mod's info and settings, Json, text, files, offsets, log."""
    r = _ready(agent, "init")
    assert not _failed(r, "init"), _failed(r, "init")
    assert any("[C++ SDK test] hello 42 wide" in line for line in agent.log_since(0)), "wcmods::log didn't reach UE4SS.log"
    with open(os.path.join(_folder(agent), "written.txt"), encoding="utf-8") as f:
        assert f.read() == "line one\nSöhne 🐱\n", "write_file wrote something else"
    shared = os.path.join(agent.cfg.ue4ss_mods_dir, "shared", "WCModsGame", "offsets.json")
    with open(shared, encoding="utf-8") as f:
        members = json.load(f)["members"]
    v = r["values"]
    assert v["offset.WCM_Value"] == members["/Script/SwtQuest.SwtQuestResourceComponent:WCM_Value"]["offset"], v["offset.WCM_Value"]
    assert v["offset.WCM_Level"] == members["/Script/SwtAdventure.SwtAdventureLevelComponent:WCM_Level"]["offset"]


def test_events(agent):
    """Events.hpp: every frame, on_game_thread, timers and cancel, keys registered, level and player events."""
    _ready(agent, "world")
    time.sleep(2.0)   # the timers that run for a while
    r = _request(agent, "events")
    v = r["values"]
    assert v["frames"] > 60 and v["frames.dt_positive"] and v["frames.on_game_thread"], v
    assert v["on_game_thread.ran"] == 1 and v["on_game_thread.other_thread"], v
    assert v["every.ran"] >= 3 and v["after.ran"] == 1, v
    # The 0.2 s timer ran until the 1.5 s one cancelled it: up to 7 times, fewer when the first frames after
    # init were long (loading), never more.
    assert v["cancel.inside"] == 3 and v["cancel.before"] == 0 and 1 <= v["cancel.outside"] <= 9, v
    assert not _failed(r, "init"), _failed(r, "init")   # on_key, on_function and unhook checks
    assert "L_WorldMap_01_P" in v["levels"] and v["levels"][-1] == agent.lua("return Game.levelName()"), v["levels"]
    players = v["players"]
    assert players and players[0] is None and players[-1] == agent.lua("return Game.name(Game.player())"), players


def test_hooks(agent):
    """A hook before and after the controller gets its pawn, with the parameter; an unhooked one never runs."""
    r = _request(agent, "events")
    v = r["values"]
    assert v["hook.pre"] >= 1 and v["hook.post"] >= 1, v
    assert v["hook.self"] == agent.lua("return Game.name(Game.controller())"), v["hook.self"]
    assert v["hook.pawn"] == v["hook.pawn_after"] == agent.lua("return Game.name(Game.player())"), v
    assert v["hook.unhooked_ran"] == 0, v


def test_world_reads_match_lua(agent):
    """Game.hpp's reads, taken as your cat arrived, against what Lua sees."""
    r = _ready(agent, "world")
    assert not _failed(r, "world"), _failed(r, "world")
    v = r["values"]
    lua = agent.lua("""
        local c = Game.cat()
        local stats = c:stats()
        local at = c:location()
        return { name = Game.name(Game.player()), class = Game.className(Game.player()), level_name = Game.levelName(),
                 full = Game.fullName(Game.player()), max_health = c:maxHealth(), max_stamina = c:maxStamina(),
                 regen = c:staminaRegen(), level = c:level(), strength = stats.Strength, agility = stats.Agility,
                 scale = c:scale(), at = { at.X, at.Y, at.Z }, seconds = Game.time.seconds(),
                 fk_max = Game.freshKill.max(), fk_period = Game.freshKill.decayTime(),
                 gi = Game.className(Game.gameInstance()), gs = Game.className(Game.gameState()),
                 gm = Game.className(Game.gameMode()), quests = Game.className(Game.manager("quests")),
                 health_comp = Game.className(c:component("Health")), fk_comp = Game.className(Game.freshKill.component()),
                 dev = Game.dev.get(%r) }""" % DEV_SWITCH)
    assert v["player.name"] == lua["name"] and v["player.class"] == lua["class"] and v["player.full_name"] == lua["full"], v
    assert v["level_name"] == lua["level_name"], v["level_name"]
    assert v["cat.max_health"] == lua["max_health"] and v["cat.max_stamina"] == lua["max_stamina"], v
    assert v["cat.stamina_regen"] == lua["regen"] and v["cat.level"] == lua["level"], v
    assert v["cat.stat.Strength"] == lua["strength"] and v["cat.stat.Agility"] == lua["agility"], v
    assert v["cat.scale"] == lua["scale"], v
    assert all(abs(a - b) < 100 for a, b in zip(v["cat.location"], lua["at"])), (v["cat.location"], lua["at"])
    assert v["time.seconds"] <= lua["seconds"] < v["time.seconds"] + 7200, (v["time.seconds"], lua["seconds"])
    assert v["fresh_kill.max"] == lua["fk_max"] and v["fresh_kill.decay.period"] == lua["fk_period"], v
    assert (v["game_instance.class"], v["game_state.class"], v["game_mode.class"]) == (lua["gi"], lua["gs"], lua["gm"]), v
    assert v["manager.quests.class"] == lua["quests"] and v["component.health.class"] == lua["health_comp"], v
    assert v["fresh_kill.component.class"] == lua["fk_comp"] and v["dev_switch.value"] == lua["dev"], v
    assert v["call.clock.hours"] == v["time.hours"], v


def test_writes_seen_by_lua(agent):
    """Game.hpp's writes (heal, set_time, teleport, set_scale, a switch, a console command, pointers,
    save_settings), each read back through Lua, then put back."""
    settings_path = os.path.join(_folder(agent), "settings.json")
    with open(settings_path, encoding="utf-8") as f:
        settings_before = f.read()
    cat = agent.cat()
    before = {"at": cat["at"], "seconds": agent.lua("return Game.time.seconds()"),
              "dev": agent.lua("return Game.dev.get(%r)" % DEV_SWITCH),
              "cvar": agent.lua("return Game.library('KismetSystemLibrary'):GetConsoleVariableIntValue(%r)" % CVAR),
              "fk": agent.lua("return Game.freshKill.value()")}
    try:
        r = _request(agent, "writes")
        assert not _failed(r, "writes"), _failed(r, "writes")
        v = r["values"]
        hours, minutes = agent.lua("local h, m = Game.time.get() return h, m")
        assert hours == 12 and 30 <= minutes < 50, (hours, minutes)
        assert agent.lua("return Game.cat():scale()") == 1.5
        assert agent.lua("return Game.dev.get(%r)" % DEV_SWITCH) == v["writes.dev_switch"] != before["dev"]
        assert agent.lua("return Game.library('KismetSystemLibrary'):GetConsoleVariableIntValue(%r)" % CVAR) == v["writes.cvar"] != before["cvar"]
        if v["writes.teleport.ok"]:
            at = agent.location()
            assert abs(at[0] - v["writes.location.after"][0]) < 60 and abs(at[1] - v["writes.location.after"][1]) < 60, (at, v["writes.location.after"])
        fk = agent.lua("return Game.freshKill.value()")
        assert abs(fk - v["writes.fresh_kill.after"]) <= 2, (fk, v["writes.fresh_kill.after"])
        assert agent.lua("return Game.cat():health() == Game.cat():maxHealth()"), "heal() didn't fill health"
        with open(settings_path, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["runs"] == v["writes.runs"] and saved["written_by"] == "test_game.cpp" and saved["text"] == "hi there", saved
        assert any("[C++ SDK test] writes done" in line for line in agent.log_since(0))
    finally:
        agent.lua("Game.cat():setScale(1)")
        agent.lua("Game.time.setSeconds(%r)" % before["seconds"])
        agent.lua("Game.dev.set(%r, %s)" % (DEV_SWITCH, "true" if before["dev"] else "false"))
        agent.lua("local c = Game.controller() Game.library('KismetSystemLibrary'):ExecuteConsoleCommand(c, %r, c)"
                  % f"{CVAR} {before['cvar']}")
        agent.lua("Game.freshKill.set(%r)" % before["fk"])
        agent.teleport(*before["at"])
        with open(settings_path, "w", encoding="utf-8", newline="") as f:
            f.write(settings_before)


def test_menu_page(agent):
    """A page drawn from C++ (Menu.hpp): every kind of row, read and used through the menu, with what the
    player set seen by the mod, and the menu's open state and page shared with it."""
    agent.menu.open()                   # the menu picks a C++ mod's pages up as it opens
    agent.menu.open("C++ SDK page")
    page = agent.menu.read()
    for label in ("Switch", "Tick", "Speed", "Count", "Name", "Tint", "Mode", "Pick", "Poke", "More"):
        assert page.find(label), f"no row {label!r} on the page: {page.text()}"
    assert page.has("Rows drawn from C++.") and page.has("A note.") and page.has("Inside the section."), page.text()
    try:
        agent.menu.set("Switch", False)
        agent.menu.set("Tick", True)
        agent.menu.set("Speed", 2.5)
        agent.menu.set("Count", 7)
        agent.menu.set("Name", "Otterpaw")
        agent.menu.set("Tint", "#102030")
        agent.menu.set("Mode", "Busy")
        agent.menu.set("Pick", "Three")
        agent.menu.set("Inner", True)
        agent.menu.press("Poke")
        v = _request(agent, "events")["values"]
        assert v["ui.on_off"] is False and v["ui.toggle"] is True and v["ui.inner"] is True, v
        assert abs(v["ui.slider"] - 2.5) < 0.01 and v["ui.number"] == 7, v
        assert v["ui.input"] == "Otterpaw" and v["ui.color"] == "#102030", v
        assert v["ui.radio"] == "Busy" and v["ui.choice"] == "Three", v
        assert v["ui.pokes"] >= 1 and v["ui.draws"] > 0, v
        assert v["menu.open"] is True and v["menu.page"] == "cpp-sdk-page", v
        agent.menu.open("Second page")
        assert agent.menu.read().has("Nothing here.")
    finally:
        agent.menu.close()
    v = _request(agent, "events")["values"]
    assert v["menu.open"] is False, v


def test_settings_page(agent):
    """The page a C++ mod with a settings.json gets without asking: a row for each setting by its kind, and
    Save writing the file."""
    settings_path = os.path.join(_folder(agent), "settings.json")
    with open(settings_path, encoding="utf-8") as f:
        settings_before = f.read()
    try:
        agent.menu.open()
        agent.menu.open("C++ SDK test")
        page = agent.menu.read()
        assert page.has("The C++ SDK test mod's settings"), page.text()   # the _help note
        for label in ("Number", "Whole", "Text", "Flag", "Runs", "Save"):
            assert page.find(label), f"no row {label!r}: {page.text()}"
        assert page.has("List") and page.has('[1,"two",false]'), page.text()   # a list shows as JSON
        agent.menu.set("Number", 2.25)
        agent.menu.set("Whole", 9)
        agent.menu.set("Flag", False)
        agent.menu.set("Text", "changed")
        agent.menu.press("Save")
        time.sleep(0.3)
        with open(settings_path, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["number"] == 2.25 and saved["whole"] == 9 and saved["flag"] is False and saved["text"] == "changed", saved
        assert saved["list"] == [1, "two", False] and saved["nested"] == {"k": "v"} and saved["_help"].startswith("The C++"), saved
    finally:
        # The rows back as they were and saved, so the mod's settings in memory match the file put back.
        try:
            agent.menu.set("Number", 1.5)
            agent.menu.set("Whole", 7)
            agent.menu.set("Flag", True)
            agent.menu.set("Text", "hi there")
            agent.menu.press("Save")
            time.sleep(0.3)
        finally:
            agent.menu.close()
            with open(settings_path, "w", encoding="utf-8", newline="") as f:
                f.write(settings_before)


def test_keys_listed(agent):
    """Keys bound with what they do are listed on the mod menu's Overview page."""
    agent.menu.open()
    try:
        agent.menu.open("Overview")
        page = agent.menu.read()
        assert page.has("F10") and page.has("Poke the test page"), page.text()
        assert page.has("Shift+F10") and page.has("Shift poke"), page.text()
    finally:
        agent.menu.close()


def test_shared_values(agent):
    """Values shared both ways: a Lua mod reads what the C++ mod shares, and WCModsCpp.share reaches it."""
    mod = 'WCModsCpp.mods["cpp-sdk"]'
    r = _request(agent, "events")
    assert r["values"]["lua_mods_started"] >= 3, r["values"].get("lua_mods_started")   # the host, the bridge, and more
    assert agent.lua(f"return {mod}.get('hello')") == 42
    assert agent.lua(f"return {mod}.get('name'), {mod}.get('flag'), {mod}.get('nope')") == ["cpp", True, None]
    agent.lua("WCModsCpp.share('ping', 7)")
    v = _request(agent, "events")["values"]
    assert v["shared.ping"] == 7, v
    agent.lua("WCModsCpp.share('ping', 'pong')")
    assert _request(agent, "events")["values"]["shared.ping"] == "pong"


def test_keys_pressed(agent):
    """F9 and Ctrl+F9 reach the mod's on_key callbacks. UE4SS reads the real keyboard, so the game has to be
    in front; when Windows won't allow that from here, this is skipped (the registration is checked above)."""
    try:
        agent.hotkey("F9", focus=True)
        time.sleep(0.3)
        agent.hotkey("F9", modifiers=("LeftControl",), focus=True)
    except AgentError as e:
        skip(str(e))
    time.sleep(0.5)
    v = _request(agent, "events")["values"]
    assert v["key.f9"] >= 1, v["key.f9"]
    assert v["key.ctrl_f9"] >= 1, v["key.ctrl_f9"]
