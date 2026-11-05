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
    # A hook on a native function Blueprints call every frame: a call through ProcessEvent (Lua's here)
    # brings parameters, and the hook reads the very location Lua got back (the last read of the player's own;
    # Lua and the mod call it on other actors too); Blueprint bytecode's calls, many a frame, come without;
    # and the game is still up.
    before = _request(agent, "events")["values"]["hook.native.with"]
    loc = agent.lua("local l = Game.player():K2_GetActorLocation(); return {l.X, l.Y, l.Z}")
    v = _request(agent, "events")["values"]
    assert v["hook.native.with"] >= before + 1 and v["hook.native.read"] >= 1, (before, v["hook.native.with"], v["hook.native.read"])
    assert all(abs(a - b) < 0.01 for a, b in zip(v["hook.native.last"], loc)) and len(loc) == 3, (v["hook.native.last"], loc)
    assert v["hook.native.without"] >= 1, v["hook.native.without"]
    # A bytecode call's return value is readable all the same (the cat stands still: the same location).
    assert all(abs(a - b) < 0.01 for a, b in zip(v["hook.native.last_bytecode"], loc)), (v["hook.native.last_bytecode"], loc)
    _request(agent, "unhook_native")
    before = _request(agent, "events")["values"]["hook.native.with"]
    agent.lua("return Game.player():K2_GetActorLocation()")
    assert _request(agent, "events")["values"]["hook.native.with"] == before, "the native hook still fired after unhook"


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


def test_reflect_matches_lua(agent):
    """Reflect.hpp: properties by path (an object, a float, an enum in a struct, an array, a map, a struct's
    member), describe, spawn, and a write Lua then reads back."""
    r = _ready(agent, "world")
    assert not _failed(r, "world"), _failed(r, "world")
    v = r["values"]
    lua = agent.lua("""
        local p = Game.player()
        local look = Game.cat():customization()
        local n = 0
        for _ in pairs(Game.cat():rewards() or {}) do n = n + 1 end
        return { state = Game.name(Game.controller().PlayerState), tags = p.Tags:GetArrayNum(), clan = look.ClanType,
                 clan_name = Game.cat():clan(), rewards = n, x = p:K2_GetActorLocation().X, dilation = p.CustomTimeDilation }""")
    assert v["reflect.player_state"] == lua["state"], (v["reflect.player_state"], lua["state"])
    assert v["reflect.tags"] == lua["tags"], (v["reflect.tags"], lua["tags"])
    assert v["reflect.clan"] == lua["clan"] and v["reflect.clan.name"].lower().replace(" ", "") == str(lua["clan_name"]).lower().replace(" ", ""), (v["reflect.clan"], v["reflect.clan.name"], lua)
    assert v["reflect.rewards"] == lua["rewards"], (v["reflect.rewards"], lua["rewards"])
    assert abs(v["reflect.x"] - lua["x"]) < 100, (v["reflect.x"], lua["x"])
    assert v["reflect.spawned"] == "Actor", v["reflect.spawned"]
    try:
        assert lua["dilation"] == 0.75, lua["dilation"]   # set(cat, "CustomTimeDilation", 0.75), seen by Lua
    finally:
        agent.lua("Game.player().CustomTimeDilation = 1")


def test_background_work(agent):
    """Events.hpp: work on a thread of its own, its result handed to the game thread; the thread checks."""
    time.sleep(0.5)
    v = _request(agent, "events")["values"]
    assert v["background.result"] == 500500 and v["background.plain"] is True, v
    assert v["background.off_game_thread"] is True and v["background.assert_off"] is True, v
    assert v["background.then_on_game_thread"] is True, v


def test_settings_reload(agent):
    """Events.hpp: a change to settings.json on disk reaches settings() and on_settings_changed."""
    settings_path = os.path.join(_folder(agent), "settings.json")
    with open(settings_path, encoding="utf-8") as f:
        before_text = f.read()
    before = json.loads(before_text)
    reloads = _request(agent, "events")["values"].get("settings.reloads", 0)
    try:
        changed = dict(before, number=3.5)
        time.sleep(1.1)   # a file time coarser than a second still differs from the last one seen
        with open(settings_path, "w", encoding="utf-8", newline="") as f:
            json.dump(changed, f, indent=2)
        end = time.time() + 5
        while time.time() < end:
            v = _request(agent, "events")["values"]
            if v.get("settings.reloads", 0) > reloads:
                break
            time.sleep(0.3)
        assert v.get("settings.reloads", 0) > reloads and v["settings.number_now"] == 3.5, v
    finally:
        time.sleep(1.1)
        with open(settings_path, "w", encoding="utf-8", newline="") as f:
            f.write(before_text)
    end = time.time() + 5
    while time.time() < end:
        v = _request(agent, "events")["values"]
        if v["settings.number_now"] == before["number"]:
            break
        time.sleep(0.3)
    assert v["settings.number_now"] == before["number"], v


def test_world_matches_lua(agent):
    """World.hpp: what's nearby, the game's screens, the ground, the save, items, and a cat's name, clan and
    traits, against what Lua sees."""
    r = _ready(agent, "world")
    assert not _failed(r, "world"), _failed(r, "world")
    v = r["values"]
    assert _close_pause(agent), "the pause screen stayed up"   # screens were recorded with none showing
    v["nearby.pickups.now"] = _request(agent, "events")["values"]["nearby.pickups.now"]   # counted just now
    lua = agent.lua("""
        local World = require("WCModsWorld")
        local N = require("WCModsNames")
        local c = Game.cat()
        local at = c:location()
        local items, n = Game.items.list(), 0
        for _ in pairs(items) do n = n + 1 end
        return { pickups = #World.nearby("pickups", 5000), screens = Game.screens(), ground = Game.ground(at.X, at.Y, at.Z),
                 slot = Game.save.slot(), inventory = Game.save.state("Inventory"), items = n,
                 inventory_text = Game.save.stateText("Inventory"),
                 progression = Game.save.progression("Chapter00", "ShowVictory"),
                 setting = Game.save.setting("SettingsData", "Minimap"),
                 name = c:name(), clan = c:clan(), traits = c:traits(),
                 marigold = N.item("Gameplay.Inventory.Consumable.MediumHealingHerb") }""")
    assert abs(v["nearby.pickups.now"] - lua["pickups"]) <= 1, (v["nearby.pickups.now"], lua["pickups"])
    assert v["nearby.pickups"] >= 0 and v["nearby.cats"] >= 0, v
    assert v["screens"] == (lua["screens"] or []), (v["screens"], lua["screens"])
    assert lua["ground"] is None or abs(v["ground"] - lua["ground"]) < 5, (v["ground"], lua["ground"])
    assert v["save.slot"] == lua["slot"], (v["save.slot"], lua["slot"])
    inv = lua.get("inventory") or {}
    assert v["save.inventory_keys"] == (len(inv) if isinstance(inv, dict) else -1), (v["save.inventory_keys"], inv)
    assert v["save.inventory_text"] == lua["inventory_text"] and lua["inventory_text"], (v["save.inventory_text"], lua["inventory_text"])
    assert v["items.count"] == lua["items"], (v["items.count"], lua["items"])
    assert v["save.progression"] == lua["progression"] and v["save.setting"] == lua["setting"], (v["save.progression"], lua["progression"], v["save.setting"], lua["setting"])
    # A name the tables don't know (an install without the game's name tables) is nil in Lua and "" in C++.
    assert v["cat.name"] == (lua.get("name") or ""), (v["cat.name"], lua.get("name"))
    assert v["cat.clan"].lower() == str(lua["clan"]).lower(), (v["cat.clan"], lua["clan"])
    assert v["cat.traits"] == (lua["traits"] or []), (v["cat.traits"], lua["traits"])
    assert v["item_name.marigold"] == (lua["marigold"] or ""), (v["item_name.marigold"], lua["marigold"])
    if v["items.count"]:
        tag = v["items.first_tag"]
        got = agent.lua("return Game.items.count(%r), Game.items.type(%r) or ''" % (tag, tag))
        assert v["items.first_count"] == got[0] and v["items.first_type"] == got[1], (v["items.first_count"], v["items.first_type"], got)


def test_items_follow_pickups_and_the_save(agent):
    """World.hpp's save_file() and items() (W6, W7), with Lua's beside them. The save read 2.5 s apart is the same
    parse while the file hasn't changed. A pickup message from the HUD lays its total over the save's in C++'s
    items() and Lua's alike, and the game writing its save after it drops it in both, so the save's count is back.
    The message is the HUD's own OnItemPickedUp sent from Lua, with no toast and a total the inventory hasn't got,
    so the save written after it still has the real count. The save is C++'s save_game() (which drops the kept
    parse), after two of an item the cat hasn't got go in through the game's AddItem, so the file grows: a save at
    the same size as at the pickup keeps the pickups (the known limit). They're taken out and saved again after."""
    _ready(agent, "world")
    _close_screens(agent)
    path = _save_path("WrcGame.json")
    written = os.path.getmtime(path)
    _request(agent, "items")
    time.sleep(2.5)
    v = _request(agent, "items")["values"]
    if os.path.getmtime(path) == written:   # the game didn't save meanwhile
        assert v["save.kept"] is True, ("parsed again", v["save.read_size"], os.path.getsize(path))
    held = {t: n for t, n in v["items.now"].items() if isinstance(n, (int, float)) and n > 0}
    if not held:
        skip("this cat has no items to test with")
    if held.get(ITEM):
        skip(f"this cat has {ITEM} already, so adding it may not change the save's size")
    tag = sorted(held)[0]
    real, fake = held[tag], held[tag] + 5
    agent.lua("Game.items.list() return true")   # Lua's watch is on (it starts with the module)
    size = os.path.getsize(path)
    sent = agent.lua("""
        local hud = Game.find("WBP_GuiHudGameWrc_C")
        if not hud then return "no HUD" end
        local ok, err = Game.call(hud, "OnItemPickedUp", {TagName = FName(%r)}, 5, %d, false)
        return ok or tostring(err)""" % (tag, fake))
    assert sent is True, sent
    laid = _request(agent, "items")["values"]["items.now"]
    assert laid.get(tag) == fake and agent.lua("return Game.items.count(%r)" % tag) == fake, \
        (laid.get(tag), agent.lua("return Game.items.count(%r)" % tag), fake)
    added = _phase(agent, "inventory_add")
    try:
        assert added["add.after"] == added["add.before"] + 2, added
        _phase(agent, "save")
        assert _saved_inventory(agent).get(ITEM) == added["add.after"]
        assert os.path.getsize(path) != size, ("the save didn't grow", size)
        time.sleep(1)   # more than a quarter second since Lua last looked at the file's size
        after = _request(agent, "items")["values"]["items.now"]
        lua_after = agent.lua("return Game.items.count(%r), Game.items.count(%r)" % (tag, ITEM))
        assert after.get(tag) == real and lua_after[0] == real, (after.get(tag), lua_after, real)
        assert after.get(ITEM) == added["add.after"] == lua_after[1], (after.get(ITEM), lua_after, added["add.after"])
    finally:
        _phase(agent, "inventory_remove")
        _phase(agent, "save")
    assert _saved_inventory(agent).get(ITEM, 0) == added["add.before"]


def test_story_matches_lua(agent):
    """Story.hpp: quests, the fight that isn't on, the events that fire outside a fight, and a quest
    reported to the mod menu."""
    r = _ready(agent, "world")
    assert not _failed(r, "world"), _failed(r, "world")
    v = r["values"]
    lua = agent.lua("""
        local all = Game.quests.all()
        local first = all[1]
        local tracked = Game.quests.tracked()
        local out = { count = #all, chapter = Game.quests.chapter(), combat = Game.combat.active(),
                      tracked = tracked and Game.quests.describe(tracked).id or nil }
        if first then
            out.first = { id = first.id, tag = first.tag, status = first.status, type = first.type, tracked = first.tracked,
                          objectives = #Game.quests.objectives(first.quest),
                          status_by_tag = first.tag and Game.quests.status(first.tag) or nil }
        end
        return out""")
    # A Lua nil is a missing key here.
    assert v["quests.count"] == lua["count"], (v["quests.count"], lua["count"])
    assert (v["quests.chapter"] or None) == lua.get("chapter"), (v["quests.chapter"], lua.get("chapter"))
    assert v["quests.tracked"] == lua.get("tracked"), (v["quests.tracked"], lua.get("tracked"))
    if lua["count"]:
        f = lua["first"]
        assert v["quests.first.id"] == f["id"] and (v["quests.first.tag"] or None) == f.get("tag"), (v["quests.first.id"], v["quests.first.tag"], f)
        assert v["quests.first.status"] == f.get("status") and v["quests.first.type"] == f.get("type"), (v["quests.first.status"], v["quests.first.type"], f)
        assert v["quests.first.tracked"] == bool(f.get("tracked")) and v["quests.first.objectives"] == f["objectives"], (v, f)
        if f.get("tag"):
            assert v["quests.first.status_by_tag"] == f.get("status_by_tag"), (v["quests.first.status_by_tag"], f.get("status_by_tag"))
    assert lua["combat"] is False
    e = _request(agent, "events")["values"]
    assert e["events.level"] >= 1 and e["events.player"] >= 1, e
    assert e["events.phase"] >= 1 and e["events.first_phase"], e
    assert e["events.combat"] == 0, e
    reported = agent.lua("return Game.quests.reported()")
    mine = [q for q in (reported or []) if q["id"] == "cpp-sdk-test"]
    assert mine and mine[0]["title"] == "The C++ test quest" and mine[0]["status"] == "active" and mine[0]["progress"] == "1 / 2", reported
    _request(agent, "unreport")
    end = time.time() + 5
    while time.time() < end:
        reported = agent.lua("return Game.quests.reported()")
        if not any(q["id"] == "cpp-sdk-test" for q in (reported or [])):
            break
        time.sleep(0.3)
    assert not any(q["id"] == "cpp-sdk-test" for q in (reported or [])), reported


STATUS_NAMES = ["None", "Blinded", "Furious", "Poisoned", "Stressed"]
SENSES = (("cone_angle", "ConeAngle"), ("cone_distance", "ConeDistance"), ("sound_radius", "SoundRadius"), ("sound_speed", "SoundSpeed"),
          ("pounce_distance", "PounceDistance"), ("proximity_distance", "ProximityDistance"), ("target_distance", "TargetDistance"),
          ("walk_speed_roaming", "WalkSpeedRoaming"), ("walk_speed_chasing", "WalkSpeedChasing"), ("zone_entry_distance", "ZoneEntryDistance"),
          ("zone_exit_distance", "ZoneExitDistance"), ("react_to_chase", "ReactToChase"))


def test_hidden_members_match_lua(agent):
    """The game's own members wcmods maps (Game.hpp's status condition, Story.hpp's fighter extras, World.hpp's
    senses and AI blackboard) against Lua's view of the same objects."""
    r = _ready(agent, "world")
    assert not _failed(r, "world"), _failed(r, "world")
    v = r["values"]
    lua = agent.lua("""
        local c = Game.cat()
        local sc = c:statusComponent()
        local out = { status = c:status(), rounds = c:statusRounds(), cure = Game.get(sc, "WCM_SelfCureChance"),
                      poison = Game.get(sc, "WCM_PoisonDamage") }
        local f = Game.fighter(c.actor)
        out.team, out.tier, out.moves = f:team(), f:aiTier(), f:moveCount()
        local name = %s
        if name then
            for _, a in ipairs(FindAllOf("WrcRoamingEnemy") or {}) do
                if Game.valid(a) and Game.name(a) == name then
                    local animal = Game.cat(a)
                    out.senses = animal:senses()
                    local ai = animal:ai()
                    out.detected = ai and ai.detected
                    out.target = ai and ai.target and Game.name(ai.target.actor) or nil
                end
            end
        end
        return out""" % ("nil" if v.get("senses.actor") is None else json.dumps(v["senses.actor"])))
    assert v["cat.status"] is not None and v["cat.status_rounds"] is not None, (v["cat.status"], v["cat.status_rounds"])
    assert STATUS_NAMES[v["cat.status"]] == lua["status"] and v["cat.status_rounds"] == lua["rounds"], (v["cat.status"], v["cat.status_rounds"], lua)
    assert abs(v["cat.self_cure_chance"] - lua["cure"]) < 1e-6 and abs(v["cat.poison_damage"] - lua["poison"]) < 1e-6, lua
    assert ["None", "Player", "Enemy"][v["fighter.team"]] == lua["team"], (v["fighter.team"], lua["team"])
    assert v["fighter.ai_tier"] == 0 and lua["tier"] == "None" and v["fighter.move_count"] == lua["moves"] == 0, (v["fighter.ai_tier"], lua)   # no fight on
    if v.get("senses.actor"):
        s = lua["senses"]
        for key, name in SENSES:
            assert abs(v["senses." + key] - s[name]) < 1e-3, (key, v["senses." + key], s[name])
        assert s["Range"] in ("Tiny", "Small", "Medium", "Large"), s
        assert v["ai.detected"] == bool(lua.get("detected")) and v.get("ai.target") == lua.get("target"), (v["ai.detected"], v.get("ai.target"), lua)


def test_status_seen_by_cpp(agent):
    """A condition given through Lua shows in the C++ members at once, with its rounds at 1, and goes with
    Lua's clearStatus (C++'s own apply/remove round trip is a check of the writes phase)."""
    assert agent.lua("return Game.cat():applyStatus('Blinded')") is True
    try:
        v = _request(agent, "status")["values"]
        assert v["status.now"] == 1 and v["status.rounds.now"] == 1, (v["status.now"], v["status.rounds.now"])
    finally:
        agent.lua("Game.cat():clearStatus()")
    v = _request(agent, "status")["values"]
    assert v["status.now"] == 0, v["status.now"]
    assert agent.lua("return Game.cat():status()") == "None"
    # No fight on: the fight snapshot is empty.
    f = _request(agent, "fight")["values"]
    assert f["fight.active"] is False and f["fight.fighters"] == [], f


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


# The pause screen that's up: a closed one lingers as a dead object a while, so FindFirstOf can't be trusted.
PAUSE = ('(function() for _, s in ipairs(FindAllOf("WBP_GuiScreenPause_C") or {}) do '
         'if s:IsValid() and s:IsInViewport() and s:IsVisible() then return s end end return nil end)()')


INVENTORY = ('(function() for _, s in ipairs(FindAllOf("WBP_GuiPopupInventory_C") or {}) do '
             'if s:IsValid() and s:IsInViewport() and s:IsVisible() then return s end end return nil end)()')
FIXTURES = {"HorizontalBox_23", "CanvasTitle", "CanvasBackground", "mcGuiFooter"}   # what a page leaves showing beside the tab row


def _screen_current(agent, screen=PAUSE):
    """The screen's current tab control's name, or None without the screen or a current tab."""
    return agent.lua(f'local s = {screen} if not s then return nil end local c = s.CurrentNav.CurrentControl '
                     f'if not c or not c:IsValid() then return nil end return Game.name(c)')


def _page_state(agent, screen=PAUSE):
    """What a page should have taken while it shows: the screen's children beside its tab row that are drawn
    (as a set of names), whether the cursor shows, and the visibility of the game's fade widgets."""
    out = agent.lua(f"""local s = {screen} local tab = s.CurrentNav.CurrentControl local area = tab:GetParent():GetParent()
        local tree = s.WidgetTree local showing = {{}}
        for i = 1, area:GetChildrenCount() do
            local c = area:GetChildAt(i - 1)
            local o = c:GetOuter()
            if o and o:IsValid() and o:GetAddress() == tree:GetAddress() and c:GetVisibility() ~= 1 then showing[#showing+1] = Game.name(c) end
        end
        local fades = {{}}
        for _, w in ipairs(FindAllOf("UserWidget") or {{}}) do
            if w:IsValid() and w:IsInViewport() and Game.className(w):find("Fade") then fades[#fades+1] = w:GetVisibility() end
        end
        return table.concat(showing, ","), Game.controller().bShowMouseCursor, table.concat(fades, ",")""")
    return {"showing": set(out[0].split(",")) - {""}, "cursor": out[1], "fades": [int(v) for v in out[2].split(",") if v]}


def _close_pause(agent):
    """Close the pause screen when it's up. The game has been seen to put it up on its own after its window
    changed focus (test_keys_pressed brings the game to the front), and the checks that expect no screen
    showing need it down."""
    for _ in range(3):
        if not agent.lua(f'return {PAUSE} ~= nil'):
            return True
        agent.key("BackSpace")
        time.sleep(1)
    return not agent.lua(f'return {PAUSE} ~= nil')


def _open_pause(agent):
    """Open the pause screen with the pause key: P on the game's keyboard layout, Escape on its mouse-and-keyboard
    layout (the game switches to that once it has seen the mouse move; Enter pauses only in its gamepad mode),
    pressing again when the game ignored it (it does for a moment after a screen closes)."""
    for i in range(4):
        agent.key("P" if i % 2 == 0 else "Escape")
        try:
            agent.wait_lua(f'{PAUSE} ~= nil', timeout=2)
            time.sleep(0.6)   # the screen's fade-in
            return True
        except Exception:
            time.sleep(0.8)
    return False


# The game's keys for the next tab and the one before on the keyboard: the arrows since build 26337109 (its tab
# row shows their pictures; 1 and 2 moved nothing, seen 2026-11-03), 1 and 2 before it.
NEXT_TAB, PREV_TAB = "Right", "Left"


def _walk_to_tab(agent, title, tries=8, key=NEXT_TAB, screen=PAUSE):
    """Press a tab key (NEXT_TAB for the next tab, PREV_TAB for the one before) until the screen's navigation is
    on the tab with `title`. On build 26337109 the inventory can open with its item grid holding the selection
    (no tab current, the arrows moving among the items): Up goes to its tab row first. Each press waits (2 s at
    most) for the tab to change before the next: behind other windows the game ticks slowly, and a walk that
    pressed again too soon went past the tab."""
    for _ in range(tries):
        name = _screen_current(agent, screen)
        if name is None and agent.lua(f'return {screen} ~= nil'):
            agent.key("Up")
            time.sleep(0.4)
            continue
        if name and agent.lua(f'local s = {screen} local c = s.CurrentNav.CurrentControl return c.Text:ToString()') == title:
            return True
        agent.key(key)
        end = time.time() + 2
        time.sleep(0.3)
        while time.time() < end and _screen_current(agent, screen) == name:
            time.sleep(0.2)
        time.sleep(0.2)
    return False


def test_ui_widgets(agent):
    """Ui.hpp: every kind of widget made, placed, styled and read back; an overlay on the viewport; the HUD's
    parts; the game's font on the text."""
    assert _close_pause(agent), "the pause screen stayed up"   # ui::screen() is checked to find none
    r = _request(agent, "ui")
    assert not _failed(r, "ui"), _failed(r, "ui")
    ran = {c["name"] for c in r["checks"]}
    assert {"ui.arrows.row_place", "ui.arrows.row_place_nested", "ui.arrows.controls", "ui.slider.unlocked"} <= ran, ran
    v = r["values"]
    assert v["ui.widget.kinds"] >= 36, v["ui.widget.kinds"]
    assert v["ui.text.font"] == "Amarante", v["ui.text.font"]
    assert v["ui.hud.class"] == "WBP_GuiHudGameWrc_C", v["ui.hud.class"]
    w, h = agent.lua("local v = Game.library('WidgetLayoutLibrary'):GetViewportSize(Game.controller()) return v.X, v.Y")
    assert (v["ui.viewport.w"], v["ui.viewport.h"]) == (w, h), (v["ui.viewport.w"], v["ui.viewport.h"], w, h)
    # The overlay's label and the HUD's are the game's widgets now: Lua sees them, on screen, with their text.
    for key, text in (("ui.overlay.label", "SDK overlay"), ("ui.hud.label", "SDK HUD")):
        assert agent.lua(f"local w = StaticFindObject({v[key]!r}) return w:GetText():ToString(), w:IsVisible()") == [text, True], key
    assert agent.lua(f"local m = StaticFindObject({v['ui.hud.minimap']!r}) return Game.className(m)") == "WBP_GuiHudControlMinimap_C"
    agent.shot("ui-overlay-hud", scale=0.5)
    _request(agent, "ui_teardown")
    assert agent.lua(f"local w = StaticFindObject({v['ui.overlay.label']!r}) return w == nil or not w:IsValid() or not w:IsVisible()")


def test_ui_tab(agent):
    """A tab of the mod's own in the pause screen (Ui.hpp's ui::tab): the game's own tab key reaches it, its page
    shows with every kind of control, the game's panel is hidden meanwhile, the controls' events reach the mod
    when Lua uses them, and leaving the tab puts the game's panel back.

    The arrows (the tab keys since build 26337109) while the page has the keyboard: Left and Right move along a row
    of buttons and, from its ends or a control alone in its row, move the game's tab as on its own tabs; a slider
    keeps them for its value; one arrow moves one tab; Up from the page's top gives the keyboard back to the tab
    row and Down takes it in again; the keyboard goes back to the screen with the page."""
    assert _open_pause(agent), "the pause screen didn't open"
    try:
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.screen"] and v["ui.screen_shown"] is True and v["ui.screen_events"] >= 1, v
        assert v["ui.tab.page"] is True and v["ui.tab.builds"] >= 1 and v["ui.tab.rows"] >= 10, v
        assert v["ui.tab.active"] is False, v
        assert _walk_to_tab(agent, "SDK"), _screen_current(agent)
        time.sleep(0.3)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is True, v
        assert v["ui.page.focus"] == "button", v["ui.page.focus"]   # the page has the keyboard: Slate takes the arrows' presses
        drawn = agent.lua(f"""local s = {PAUSE}
            local function drawn(w)
                while w and w:IsValid() do local v = w:GetVisibility() if v == 1 or v == 2 then return false end w = w:GetParent() end
                return true
            end
            return drawn(s.mcGuiPanelGeneral), drawn(s.mcGuiPanelBonds)""")
        assert drawn == [False, False], drawn   # the game's panels are under a collapsed canvas while the page shows
        # And so is everything else the screen put beside the tab row (the Bonds tab's cat cards, in plain size
        # boxes, among them), but its title, footer and background; the page has the mouse: the cursor shows, and
        # the game's fade widget over the screens no longer takes hits.
        state = _page_state(agent)
        assert state["showing"] <= FIXTURES and state["cursor"] is True and state["fades"] and set(state["fades"]) == {3}, state
        assert agent.lua(f"local p = StaticFindObject({v['ui.page.panel']!r}) return p:IsVisible()") is True
        agent.shot("ui-tab", scale=0.5)
        # The page's controls, used the way the player would (through the widgets themselves).
        agent.lua(f"StaticFindObject({v['ui.page.check']!r}):SetIsChecked(false)")
        agent.lua(f"StaticFindObject({v['ui.page.slider']!r}):SetValue(0.8)")
        agent.lua(f"StaticFindObject({v['ui.page.input']!r}):SetText(FText('Otterpaw'))")
        time.sleep(0.3)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.toggles"] >= 1 and v["ui.last_toggle"] is False, v
        assert v["ui.changes"] >= 1 and abs(v["ui.last_change"] - 0.8) < 0.01, v
        assert v["ui.texts"] >= 1 and v["ui.last_text"] == "Otterpaw", v
        # The arrows on the page. A row of two buttons: from the right one, Left moves to the left one and the tab
        # stays; from the left one, Left leaves the tab for the one before it. (A focus given by a script or the
        # mouse less than 0.6 s before an arrow counts as the arrow's own move: wait longer.)
        agent.lua(f"StaticFindObject({v['ui.page.row_b']!r}):SetKeyboardFocus()")
        time.sleep(0.8)
        assert _request(agent, "ui_snapshot")["values"]["ui.page.focus"] == "row_b"
        agent.key(PREV_TAB)
        time.sleep(0.5)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is True and v["ui.page.focus"] == "row_a", (v["ui.tab.active"], v["ui.page.focus"])
        agent.key(PREV_TAB)
        time.sleep(0.8)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is False and v["ui.screen.current"] == "mcGuiTabBonds", (v["ui.tab.active"], v["ui.screen.current"])
        # The keyboard went back to the screen with the page: the next arrow reaches the game's tab row itself.
        agent.key(NEXT_TAB)
        time.sleep(0.8)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is True and v["ui.page.focus"] == "button", (v["ui.tab.active"], v["ui.page.focus"])
        # One arrow moves one tab, onto the page and off it: Left once from the button is Bonds, Right once is back.
        agent.key(PREV_TAB)
        time.sleep(0.8)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.screen.current"] == "mcGuiTabBonds", v["ui.screen.current"]
        agent.key(NEXT_TAB)
        time.sleep(0.8)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is True and v["ui.screen.current"] != "mcGuiTabBonds", v["ui.screen.current"]
        # Up from the page's top gives the keyboard back to the tab row; Down takes it into the page again.
        agent.key("Up")
        time.sleep(0.8)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is True and v["ui.page.focus"] is None, (v["ui.tab.active"], v["ui.page.focus"])
        agent.key("Down")
        time.sleep(0.8)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is True and v["ui.page.focus"] == "button", (v["ui.tab.active"], v["ui.page.focus"])
        # A slider keeps Left for its value: the tab stays and the value goes down.
        agent.lua(f"StaticFindObject({v['ui.page.slider']!r}):SetKeyboardFocus()")
        time.sleep(0.8)
        before = v["ui.last_change"]
        agent.key(PREV_TAB)
        time.sleep(0.8)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is True and v["ui.page.focus"] == "slider", (v["ui.tab.active"], v["ui.page.focus"])
        assert v["ui.last_change"] < before - 0.01, (before, v["ui.last_change"])
        # The button again: Left leaves the tab.
        agent.lua(f"StaticFindObject({v['ui.page.button']!r}):SetKeyboardFocus()")
        time.sleep(0.8)
        # Back to the game's first tab: its panel shows again, the page is gone.
        for _ in range(8):
            agent.key(PREV_TAB)
            time.sleep(0.3)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is False and v["ui.screen.current"] == "mcGuiTabGeneral", v
        assert agent.lua(f'return {PAUSE}.mcGuiPanelGeneral:GetVisibility()') == 3
        # And the mouse given back: the cursor hidden as the game had it, the fade widget taking hits again.
        state = _page_state(agent)
        assert state["cursor"] is False and 3 not in state["fades"], state
    finally:
        agent.key("BackSpace")
        time.sleep(1)
        agent.key("BackSpace")
        time.sleep(0.5)
    v = _request(agent, "ui_snapshot")["values"]
    assert v["ui.screen"] is None and v["ui.screen_shown"] is False and v["ui.tab.page"] is False, v


def test_ui_inventory_tab(agent):
    """A tab of the mod's own in the inventory (ui::tab on WBP_GuiPopupInventory_C): reached with the game's tab
    key, its page covers the item grids and info beside the tab row, and leaving puts them back."""
    agent.key("I")
    agent.wait_lua(f"{INVENTORY} ~= nil", timeout=4)
    time.sleep(0.8)
    try:
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.inventory.page"] is True and v["ui.inventory.active"] is False, v
        assert _walk_to_tab(agent, "SDK", tries=8, screen=INVENTORY), _screen_current(agent, INVENTORY)
        time.sleep(0.5)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.inventory.active"] is True, v
        state = _page_state(agent, INVENTORY)
        assert state["showing"] <= FIXTURES and state["cursor"] is True, state
        agent.shot("ui-inventory-tab", scale=0.5)
        assert _walk_to_tab(agent, "Consumable", tries=8, key=PREV_TAB, screen=INVENTORY), _screen_current(agent, INVENTORY)
        time.sleep(0.5)
        state = _page_state(agent, INVENTORY)
        assert "CanvasGrids" in state["showing"] and state["cursor"] is False, state
    finally:
        agent.key("BackSpace")
        time.sleep(1)
    assert agent.lua(f"return {INVENTORY} == nil")


def test_ui_lua(agent):
    """WCModsCpp.ui (UiLua.hpp): a Lua mod makes and places widgets, keeps an overlay and puts a tab in the pause
    screen through the C++ mod's functions."""
    assert agent.lua("return type(WCModsCpp.ui) == 'table' and type(WCModsCpp.ui.tab) == 'function'")
    out = agent.lua("""
        local ui = WCModsCpp.ui
        local t = ui.text("From Lua", { size = 40, color = "#ff8800" })
        local b = ui.button("Go")
        local c = ui.check(true)
        local s = ui.slider(0.25, 0, 1)
        local row = ui.row({ t, b })
        local col = ui.vbox()
        local switch = ui.labelled("Switch", c)
        ui.add(col, { row, switch, ui.labelled("Slider", s) })
        local canvas = ui.overlay("lua-test", 1200)
        local slot = ui.add(canvas, col)
        ui.place(slot, { position = { 300, 300 }, auto = true })
        local w, h, scale = ui.viewport()
        local vis = ui.visible(t)
        return { text = ui.text(t), kind = Game.className(t), checked = ui.checked(c), value = ui.value(s),
                 rows = #ui.children(col), found = ui.find(col, Game.name(b)):GetAddress() == b:GetAddress(), vis = vis, w = w, scale = scale,
                 canvas = Game.className(canvas), clicked = ui.clicked(b), changed = ui.changed(s),
                 theme = ui.theme().text_size, hud = Game.className(ui.hud()), mini = Game.className(ui.hud("mcGuiMinimap")),
                 check_scale = c.RenderTransform.Scale.X, check_room = Game.className(ui.children(switch)[2]),
                 check_tall = ui.children(switch)[2].HeightOverride }
    """)
    assert out["text"] == "From Lua" and out["kind"] == "TextBlock" and out["checked"] is True, out
    assert abs(out["value"] - 0.25) < 0.01 and out["rows"] == 3 and out["found"] is True, out
    assert out["vis"] == "visible" and out["w"] > 100 and out["scale"] > 0 and out["canvas"] == "CanvasPanel", out
    assert out["clicked"] is False and out["changed"] is False and out["theme"] > 0, out
    assert out["hud"] == "WBP_GuiHudGameWrc_C" and out["mini"] == "WBP_GuiHudControlMinimap_C", out
    # labelled() from Lua goes through the same scaled(): the check box grown by a render transform in a size box.
    assert abs(out["check_scale"] - 3) < 1e-3 and out["check_room"] == "SizeBox" and abs(out["check_tall"] - 72) < 1e-3, out
    agent.shot("ui-lua-overlay", scale=0.5)
    # A tab from Lua: registered now, its page there once the pause screen is up, filled by the script.
    tab = agent.lua("""
        local ui = WCModsCpp.ui
        local id = ui.tab("WBP_GuiScreenPause_C", "Lua tab", "lua-tab")
        return id, ui.tab_page(id) == nil, ui.tab_active(id), ui.tabs()
    """)
    assert tab[0] == "lua-tab" and tab[1] is True and tab[2] is False and "lua-tab" in tab[3], tab
    assert _open_pause(agent), "the pause screen didn't open"
    try:
        page = agent.lua("""
            local ui = WCModsCpp.ui
            local page, gen = ui.tab_page("lua-tab")
            if page then ui.add(page, { ui.heading("Lua page"), ui.note("Made by a Lua mod through WCModsCpp.ui.") }) end
            return page ~= nil, gen, page and #ui.children(page) or 0
        """)
        assert page[0] is True and page[1] >= 1 and page[2] == 2, page
        assert _walk_to_tab(agent, "Lua tab"), _screen_current(agent)
        time.sleep(0.3)
        assert agent.lua("return WCModsCpp.ui.tab_active('lua-tab')") is True
        agent.shot("ui-lua-tab", scale=0.5)
        # Back to the SDK tab with the tab key the other way, through whatever tabs other mods have between: the
        # tab leaving gives the mouse and the panels back, the one arriving takes them, and keeps them.
        assert _walk_to_tab(agent, "SDK", tries=10, key=PREV_TAB), _screen_current(agent)
        time.sleep(0.8)
        state = _page_state(agent)
        assert state["showing"] <= FIXTURES and state["cursor"] is True and set(state["fades"]) == {3}, state
    finally:
        agent.key("BackSpace")
        time.sleep(1)
        agent.lua("WCModsCpp.ui.remove_tab('lua-tab') WCModsCpp.ui.remove_overlay('lua-test')")
    assert agent.lua("local t = WCModsCpp.ui.tabs() for _, id in ipairs(t) do if id == 'lua-tab' then return false end end return true")


# ---------- the game's native functions, its commands, the sky, sounds, animations and saving (test_native.cpp) ----------
ITEM = "Gameplay.Inventory.Consumable.SmallCatnip"   # added and taken away again
SKY = ("local sky = Game.find('BP_DayNightSky_C') local f = sky:GetExponentialHeightFog() "
       "local l = sky:GetDirectionLightComponent() return { fog = f.FogDensity, light = l.Intensity }")


def _phase(agent, what):
    """One of test_native.cpp's phases, run with none of its checks failing: its values."""
    r = _request(agent, what)
    assert not _failed(r, what), _failed(r, what)
    return r["values"]


def _offsets(agent):
    with open(os.path.join(agent.cfg.ue4ss_mods_dir, "shared", "WCModsGame", "offsets.json"), encoding="utf-8") as f:
        return json.load(f)


def _save_path(name):
    return os.path.join(os.environ["LOCALAPPDATA"], "Wrc", "Saved", "SaveGames", name)


def _saved_inventory(agent):
    """The inventory in WrcGame.json, which the game writes at every save, for the cat in play: the slot the file
    names as its current cat (not the save game's CurrentSaveSlotIndex, which stayed 0 for slot 8's cat)."""
    with open(_save_path("WrcGame.json"), encoding="utf-8") as f:
        account = next(iter(json.load(f).values()))
    slot = account["Shared"]["General"]["CurrentCatSlot"]
    assert agent.lua("return (Game.save.slotData() or {}).Meta ~= nil"), "Lua's slotData() found no slot"
    return account[str(slot)]["GameplayProgression"]["State"].get("Inventory", {})


def _close(a, b):
    return all(abs(a[k] - b[k]) <= 1e-4 * max(1.0, abs(b[k])) for k in ("fog", "light"))


def _close_screens(agent):
    """No pause screen and no inventory up: a test that failed with one open leaves it for the next, which
    then runs without the HUD (the game takes it away while a screen is up) and under the inventory's sky.
    The inventory is closed as its Back does, the release in a later frame than the press."""
    assert _close_pause(agent), "the pause screen stayed up"
    for _ in range(3):
        if agent.lua(f"return {INVENTORY} == nil"):
            return
        for event in (0, 1):
            agent.lua(f"local s = {INVENTORY} if s then Game.call(s, 'OnListenCommand', 25, {event}, Game.controller()) end return true")
            time.sleep(0.3)
        time.sleep(1.0)
    assert agent.lua(f"return {INVENTORY} == nil"), "the inventory stayed up"


def test_unhook_loop(agent):
    """Events.hpp's unhook, hard: 50 hooks on ClientRestart made and taken off at once, then 20 rounds of a hook on
    K2_GetActorLocation (called from Blueprints many times a frame) that takes itself off from inside its own
    callback. The game keeps running and every round's hook went (UE4SS frees a hook taken off later, not while
    its callbacks run): the C++ SDK's unhook isn't what crashed UE4SS on 2026-11-03."""
    r = _request(agent, "unhook_loop", timeout=60)
    assert not _failed(r, "unhook_loop"), _failed(r, "unhook_loop")
    ran = {c["name"] for c in r["checks"] if c["phase"] == "unhook_loop"}
    assert {"unhook_loop.made", "unhook_loop.rounds"} <= ran, ran
    assert r["values"]["unhook_loop.calls"] >= 60, r["values"]["unhook_loop.calls"]   # three calls a round, at least
    assert agent.lua("return Game.cat() ~= nil")   # still playing


def test_tables_units(agent):
    """Tables.hpp's tuning map reader, at init without the game, on a map laid out as the game's: its keys, values
    and descriptions in order past a free slot, a write through a row seen in the map, what doesn't add up refused,
    and keys matched whatever their case."""
    r = _ready(agent, "init")
    ran = {c["name"] for c in r["checks"] if c["name"].startswith("tables.")}
    assert {"tables.tuning_map.read", "tables.tuning_map.write", "tables.tuning_map.refused", "tables.tuning_map.none",
            "tables.tuning.same_key"} <= ran, ran
    assert not _failed(r, "init"), _failed(r, "init")


def test_tables_and_tuning(agent):
    """Tables.hpp in the game: every DataTable in memory, the item table by name and by path with its rows (the game's 412 and mods'), a row
    read, rows added (a copy, and one of defaults) and taken out; TuningData's keys and numbers, one changed and read
    back by the game's own lookup (its native GetValue, which every tuning read in the game goes through), and put
    back; and an item's name changed in its row, then shown by the HUD when the item is added."""
    r = _request(agent, "tables", timeout=30)
    assert not _failed(r, "tables"), _failed(r, "tables")
    v = r["values"]
    assert v["tables.count"] >= 60, v["tables.count"]   # 69 in the forest on 26337109
    info = v["tables.items_info"]
    # The game's 412 rows, and one more for each item an installed mod adds (tests/items-mod's block).
    assert info["rows"] >= 412 and info["struct"] == "QuestObjectsInfoDataStruct", info
    assert info["path"] == "/Game/Gameplay/DataTables/Quests/DT_QuestObjectsInfo.DT_QuestObjectsInfo", info
    assert v["tables.items.size"] == info["rows"] and v["tables.items.names"] == info["rows"], (v["tables.items.size"], v["tables.items.names"])
    assert v["tables.herb.row"] and v["tables.herb.name"] == "Lamb's Ear Leaves", (v["tables.herb.row"], v["tables.herb.name"])
    # TuningData.csv's numbers (Metrics.Cat.Player.Height 15 with its description; MaxLevel 20), all 441 keys.
    assert v["tuning.keys"] == 441, v["tuning.keys"]
    assert v["tuning.some"]["Gameplay.Exploration.Metrics.Cat.Player.Height"] == 15, v["tuning.some"]
    assert v["tuning.some"]["Gameplay.Exploration.MaxLevel"] == 20, v["tuning.some"]
    assert v["tuning.description"] == "The average height of the cat from the ground to its head.", v["tuning.description"]
    assert v["tuning.lookup_found"] is True and v["tuning.game_before"] == 20 and v["tuning.game_after"] == 33, v
    # The HUD named the added herb by the row's new name, and the name went back after.
    assert v["tables.herb.added"] is True
    assert any("WCMods Test Herb" in t for t in v["tables.hud_texts"]), v["tables.hud_texts"]
    assert v["tables.herb.name_after"] == "Lamb's Ear Leaves", v["tables.herb.name_after"]
    # Put back whole, the name follows its string-table key again (set() had made it a plain text).
    assert v["tables.herb.name_key_after"] == "STR_ITEM_CONSUMABLE_NAME_7", v["tables.herb.name_key_after"]


def test_words(agent):
    """Words.hpp in the game: the string table's keys, the test cat's name by its key, the key an item's name in its
    row was made from, that key's words changed (the row's own text shows them, and so does the HUD's message when
    the item is added) and put back; a key the table hasn't got is refused."""
    r = _request(agent, "words", timeout=30)
    assert not _failed(r, "words"), _failed(r, "words")
    ran = {c["name"] for c in r["checks"] if c["phase"] == "words"}
    assert {"words.missing", "words.not_set_yet", "words.key_of_plain_value", "words.set", "words.restore"} <= ran, ran
    v = r["values"]
    assert v["words.all_keys"] > 8000 and v["words.name_keys"] > 2000, (v["words.all_keys"], v["words.name_keys"])
    assert v["words.ember"] == "Emberpaw", v["words.ember"]   # the test cat, STR_CAT_NAME2 + _PAW
    assert (v["words.herb_table"], v["words.herb_key"]) == ("SwtStrings", "STR_ITEM_CONSUMABLE_NAME_7"), v
    assert v["words.herb_before"] == "Lamb's Ear Leaves" and v["words.herb_after"] == "Lamb's Ear Leaves", v
    assert v["words.row_text_after"] == "WCMods Word Herb", v["words.row_text_after"]
    assert v["words.added"] is True and "WCMods Word Herb" in v["words.hud_texts"], v["words.hud_texts"]


def test_sounds_and_music(agent):
    """Sounds and music (World.hpp) in the game: the cat's steps (cat_step) made the menu's select sound, and while
    the cat walks only that plays, from the game's own native play (no hook sees it); muted and put back; the
    music read (the ShadowClan camp's track), another track played and stopped, and the game's again; the
    volumes set and the sounds paused and going on."""
    # The phase samples what plays for 4 s, so the walk goes on while it runs: the request is written here, and the
    # results waited for after the walk.
    before = _results(agent)
    served = before.get("served", 0) if before else 0
    with open(os.path.join(_folder(agent), "request.txt"), "w", encoding="utf-8") as f:
        f.write("sounds")
    time.sleep(0.6)
    agent.key("W", hold=3.5)
    end = time.time() + 20
    r = _results(agent)
    while not (r and r.get("served", 0) > served and "sounds" in r.get("done", [])) and time.time() < end:
        time.sleep(0.3)
        r = _results(agent)
    assert r and r.get("served", 0) > served, "the sounds phase didn't finish"
    assert not _failed(r, "sounds"), _failed(r, "sounds")
    v = r["values"]
    assert v["sounds.step_before"] == "S_Cue_cat_step" and v["sounds.ui_select_duration"] > 0.1, v
    assert v["sounds.heard_walking"] == ["S_Cue_ui_select"], v["sounds.heard_walking"]   # the steps, and no step sound
    assert v["sounds.music_sound"].startswith("MS_mus_") and v["sounds.music_id"], v
    assert v["sounds.music_after_play"] == "MS_mus_camp" and v["sounds.music_after_stop"] is None, v


def test_sky_values(agent):
    """The sky's preset values (World.hpp): its table (DT_SkyBoxParams, a row per preset), and the copy of it the sky
    applies (a hidden member): Night's fog read from it is the table's and what Night puts on; with Night held, its
    fog made ten times thicker there, the fog on screen is ten times thicker; a colour's part set; what isn't
    there refused; all put back."""
    r = _request(agent, "sky_values", timeout=15)
    assert not _failed(r, "sky_values"), _failed(r, "sky_values")
    v = r["values"]
    assert (v["skyv.table"], v["skyv.struct"]) == ("DT_SkyBoxParams", "WrcSkyBoxStruct"), v
    assert len(v["skyv.rows"]) == 13 and {"NeutralDay", "Night", "ThunderClan"} <= set(v["skyv.rows"]), v["skyv.rows"]
    fog = v["skyv.night_row_fog"]
    assert fog == v["skyv.night_table_fog"] and abs(v["skyv.fog_before"]["fog"] - fog) < 1e-6, v
    assert abs(v["skyv.fog_after"]["fog"] - fog * 10) < 1e-4, (v["skyv.fog_after"], fog)
    assert v["skyv.night_row_fog_restored"] == fog and v["skyv.thunder_sun"] > 0, v


def test_npcs(agent):
    """Npcs.hpp in the game: a cat of the mod's own spawned 2 m from your cat (moved 8 m from the den entrance whose
    Travel prompt would take the Interact) on the game's walking cat, with its look, size, name and fur colour; its
    label (name, title, icon) and its Talk prompt showing; the game's Interact, given as its controls give it, heard
    for it; moved, walked 5 m with its own AI controller, and removed. The loader and the enum lookup on the way."""
    r = _request(agent, "npcs", timeout=40)
    assert not _failed(r, "npcs"), _failed(r, "npcs")
    v = r["values"]
    assert v["npcs.moved"] is True and v["npcs.spot"] is True, v
    assert v["npcs.class"] == "BP_WalkingNPC_Character_Base_C" and abs(v["npcs.distance"] - 200) < 50, v
    assert (v["npcs.body"], v["npcs.tail"], v["npcs.fur_slot"], v["npcs.override"]) == (3, 2, 4, True), v
    assert (v["npcs.label_name"], v["npcs.label_title"], v["npcs.label_opacity"]) == ("Brindlemoon", "Elder", 1), v
    assert v["npcs.game_prompt_up"] is False and v["npcs.prompt_on"] is True and v["npcs.prompt_shown"] is True, v
    assert v["npcs.prompt_text"] == "Talk", v
    assert v["npcs.fur_r"] > 0.99 and v["npcs.fur_b"] < 0.01, v   # #ff8800
    assert v["npcs.interact_sent"] is True and v["npcs.interacts"] == 1 and v["npcs.interacted_is_it"] is True, v
    assert v["npcs.walk_started"] is True and v["npcs.walked"] > 400 and v["npcs.walk_result"] == 1, v   # Arrived
    assert v["npcs.walking_after"] is False and v["npcs.walk_result_after"] == 1, v
    assert v["npcs.removed_gone"] is True and v["npcs.left"] == 0, v


def test_talks(agent):
    """Talk.hpp in the game: a line of the mod's own in the dialogue box with answers on its buttons; the game's talks
    by tag, read from their graphs (the RiverClan prophecy's four narrated lines, the WindClan rank-up's "I DO" and
    its bonding nodes) as Lua reads the same graphs; the prophecy played to its end (its action passed on, its end
    called once), the rank-up's bonded opening, its answer (a wrong number refused) and its actions; the first
    line's words changed through its key and shown, then put back; a talk of the mod's own with its second answer
    chosen; a hook that says something as a talk ends. The
    game is quit after the suite, so a talk that left the game's screens in a bad state shows as a crash there."""
    r = _request(agent, "talks", timeout=30)
    assert not _failed(r, "talks"), _failed(r, "talks")
    v = r["values"]
    assert (v["talks.say_line"], v["talks.say_speaker"], v["talks.say_answers"]) == ("Hello from C++", "Brindlemoon", ["Yes", "No"]), v
    assert len(v["talks.tags"]) == 30 and "Gameplay.Narrative.Prophecy.Intro.RiverClan" in v["talks.tags"], v["talks.tags"]
    # The same graph read by Lua: its talking nodes from the root, each to its first child.
    lua_lines = agent.lua(
        "local g = StaticFindObject('/Game/Quests/NpcDialogues/Cinematic/CinematicDialogue_ProphecyIntro_RiverClan."
        "CinematicDialogue_ProphecyIntro_RiverClan') "
        "local function first(a) local r = nil a:ForEach(function(i, x) if not r then r = x:get() end end) return r end "
        "local out = {} local n = first(g.RootNodes) local guard = 0 "
        "while n and n:IsValid() and guard < 20 do guard = guard + 1 "
        "if n:GetClass():GetFName():ToString() == 'QuestDialogueTalkingNode' then out[#out + 1] = n.Paragraph:ToString() end "
        "n = first(n.ChildrenNodes) end "
        "return table.concat(out, '\\n')")
    assert v["talks.prophecy_lines"] == lua_lines.split("\n"), (v["talks.prophecy_lines"], lua_lines)
    assert v["talks.prophecy_graph"] == "CinematicDialogue_ProphecyIntro_RiverClan" and v["talks.prophecy_nodes"] == 5, v
    assert v["talks.rankup_graph"] == "CinematicDialogue_RankUp_WindClan_Warrior" and v["talks.rankup_answers"] == ["I DO"], v
    assert v["talks.rankup_bonding_nodes"] == [3, 3], v
    assert v["talks.first_key"] == "STR_Script.RiverClan.Prophecy.Intro.Narrator.1", v["talks.first_key"]
    assert v["talks.played_lines"] == v["talks.prophecy_lines"] and v["talks.played_steps"] == 4, v
    assert set(v["talks.played_speakers"]) == {"Narrator"} and v["talks.played_ends"] == 1, v
    assert v["talks.played_actions"] == ["QuestDialogueActionCreateScreen"], v["talks.played_actions"]
    assert v["talks.rankup_opening"].startswith("The apprentice was ready to become a warrior"), v["talks.rankup_opening"]
    assert v["talks.answer_line"].startswith('"Do you promise to protect this Clan') and v["talks.answers_shown"] == ["I DO"], v
    assert v["talks.chosen"] == ["I DO"] and v["talks.rankup_ends"] == 1, v
    assert v["talks.rankup_actions"][0] == "QuestDialogueActionResolveConfirm", v["talks.rankup_actions"]
    assert v["talks.changed_line"] == "WCMods changed this line", v["talks.changed_line"]
    assert v["talks.restored_line"] == v["talks.prophecy_lines"][0], v["talks.restored_line"]
    assert (v["talks.after_end_line"], v["talks.after_end_ends"], v["talks.box_after"]) == ("After the talk", 1, False), v
    assert v["talks.own_after"] == "Another time, then.", v["talks.own_after"]
    # The box said again as it was going stayed: still in the viewport after the removal's 0.4 s.
    assert v["talks.after_end_in_view"] is True, v


def test_bonds(agent):
    """Bonds.hpp in the game, on the test cat (ShadowClan): the ranks by the tuning's thresholds; the clan's bond (67,
    the tuning's default) and one of the clan's story cats' (its role's base, 20) read through the game's own bond
    code; added to and set (set_bond refuses a value outside 0 to 100; the game's own add stops there); the pause screen's Bonds panel shows both (the
    clan bar's score and the cat's row); the game's save has them under the slot's Bonding; put back after (a bond
    can't be taken out of the save, so the slot keeps the two at their defaults)."""
    _close_screens(agent)
    try:
        r = _request(agent, "bonds", timeout=40)
    finally:
        _close_screens(agent)
    assert not _failed(r, "bonds"), _failed(r, "bonds")
    v = r["values"]
    role = v["bonds.role"]
    assert v["bonds.roles"] > 100 and v["bonds.first_role"] == "TheStarvingWarrior", v
    assert v["bonds.name_from_ids"] == "Emberpaw", v["bonds.name_from_ids"]
    assert role and v["bonds.clan_before"] == 67 and v["bonds.role_before"] == 20, v
    assert (v["bonds.clan_after"], v["bonds.role_after"], v["bonds.role_high"], v["bonds.role_low"]) == (42, 50, 100, 0), v
    listed = {b["key"]: b for b in v["bonds.listed"]}
    assert listed["ShadowClan"]["value"] == 42 and listed["ShadowClan"]["rank"] == "Neutral", listed["ShadowClan"]
    assert listed[role]["value"] == 50 and listed[role]["rank"] == "Friend" and listed[role]["base"] == 20, listed[role]
    panel = v["bonds.panel"]
    assert panel and panel["clan_score"] == "42/100" and panel["clan_info"] == "Neutral", panel
    assert "50/100" in [row["score"] for row in panel["rows"]], panel["rows"]
    assert v["bonds.saved"].get("ShadowClan") == 42 and v["bonds.saved"].get(role) == 50, v["bonds.saved"]
    assert (v["bonds.clan_restored"], v["bonds.role_restored"]) == (67, 20), v
    assert v["bonds.saved_after"].get("ShadowClan") == 67 and v["bonds.saved_after"].get(role) == 20, v["bonds.saved_after"]


def _save_npc_data(agent):
    """The test cat's NPCData as the game last saved it."""
    with open(os.path.join(os.environ["LOCALAPPDATA"], "Wrc", "Saved", "SaveGames", "WrcGame.json"), encoding="utf-8") as f:
        account = next(iter(json.load(f).values()))
    return account[str(account["Shared"]["General"]["CurrentCatSlot"])]["NPCData"]


def _linear(rgb):
    """"r,g,b" bytes (an sRGB FColor) as the "r,g,b" linear colour a material parameter holds, to 3 places."""
    def one(c):
        c = int(c) / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return [one(c) for c in rgb.split(",")]


def _drawn(colour, rgb):
    """Whether a material's colour is a slot's FColor, as the game draws it."""
    return all(abs(float(a) - b) < 0.006 for a, b in zip(colour.split(","), _linear(rgb)))


def test_looks(agent):
    """Looks.hpp in the game, on the test cat (Emberpaw, ShadowClan): the look struct's defaults are the game's; the
    save's text read; the fur colour slot and the tail changed through the game's own SetDefaultCustomData, and the
    model follows (the body's Fur Color is the slot's colour from the game's table, the tail's mesh changes), then put
    back; kept in the save through the game's SaveCatCustomData and back; a collar worn (its mesh shows) and taken off;
    a spawned cat's look changed the same way; the clan's cats as many as the save's NPCData holds, each cast story
    role placed once, the ones out now matched to their actors."""
    _close_screens(agent)
    r = _request(agent, "looks", timeout=60)
    assert not _failed(r, "looks"), _failed(r, "looks")
    v = r["values"]
    me = v["looks.player"]
    assert (me["ClanType"], me["PrefixNameId"], me["SuffixNameId"]) == ("ShadowClan", "STR_CAT_NAME2", "_PAW"), me
    assert v["looks.role"] == "ShadowClan/None/", v["looks.role"]
    before, after, restored = v["looks.model_before"], v["looks.model_after"], v["looks.model_restored"]
    assert v["looks.after"]["FurColorIdx"] == (me["FurColorIdx"] + 5) % 19 and v["looks.after"]["TailIdx"] == (me["TailIdx"] + 3) % 9
    # The model drew the slot's own colour from the game's table, and another tail (the test cat's own colour, painted
    # by CatLook, isn't the slot's: it's gone until CatLook paints again).
    assert _drawn(after["fur"], after["fur_slot"]) and after["tail"] and after["tail"] != before["tail"], (before, after)
    assert _drawn(restored["fur"], restored["fur_slot"]) and restored["tail"] == before["tail"], (before, restored)
    assert v["looks.restored"] == me, (me, v["looks.restored"])
    # The game's 44 accessories; the collar on the neck, in look 2, its mesh shown, then hidden again.
    assert v["looks.accessories"] == 44 and v["looks.dog_collar"].startswith("Neck/"), (v["looks.accessories"], v["looks.dog_collar"])
    assert (v["looks.worn"]["AccesoryNeckId"], v["looks.worn"]["AccesoryNeckVar"]) == ("DogCollar", 2), v["looks.worn"]
    assert v["looks.model_worn"]["neck"] and v["looks.model_worn"]["neck_visible"] is True, v["looks.model_worn"]
    assert v["looks.model_taken_off"]["neck_visible"] is False, v["looks.model_taken_off"]
    # The save: the changed look kept, then the cat's own again.
    changed = ("FurColorIdx=%d," % ((me["FurColorIdx"] + 5) % 19), "TailIdx=%d," % ((me["TailIdx"] + 3) % 9))
    assert all(c in v["looks.saved_changed"] for c in changed), v["looks.saved_changed"]
    assert v["looks.saved_restored"] == v["looks.saved_text"], (v["looks.saved_text"], v["looks.saved_restored"])
    # A cat of the mod's own: drawn from its look as it spawns (spawn_npc sets it up with the game's own call), and a
    # change moves only what changed (the coat and the ears, not the tail or the fur's mesh).
    nb, na = v["looks.npc_model_before"], v["looks.npc_model_after"]
    assert _drawn(nb["fur"], nb["fur_slot"]) and _drawn(na["fur"], na["fur_slot"]) and na["fur"] != nb["fur"], (nb, na)
    assert na["ears"] and na["ears"] != nb["ears"] and (na["tail"], na["fur_mesh"]) == (nb["tail"], nb["fur_mesh"]), (nb, na)
    changed = {k for k in v["looks.npc_before"] if v["looks.npc_before"][k] != v["looks.npc_after"][k]}
    assert changed == {"EarIdx", "FurColorIdx"}, changed
    # The clan's cats against the save's NPCData.
    npcs = _save_npc_data(agent)
    kept = [c for g, roles in npcs.items() if g not in ("NarrativeRoles", "RemainingNames")
            for cats in roles.values() for c in cats]
    cats = v["looks.clan_cats"]
    listed = [c for c in cats if c["index"] >= 0]
    assert len(listed) == len(kept), (len(listed), len(kept))
    story = sorted(s for c in cats for s in c["story"])
    cast = sorted(k for k, text in npcs["NarrativeRoles"].items() if "PrefixNameId=" in text)
    assert story == cast, (story, cast)
    assert all(c["name"] for c in cats), [c for c in cats if not c["name"]]
    leader = [c for c in cats if "ShadowClanLeader" in c["story"]]
    assert len(leader) == 1 and leader[0]["clan"] == "ShadowClan" and leader[0]["role"] == "Leader", leader


def test_drop_items(agent):
    """Items.hpp in the game: an item's name, icon and kind from the game's tables (a mod's item too, from
    tests/items-mod); map_clear and map_add on a pickup's Reward (a key added again takes the new value); Moss
    dropped beside the cat (8 m off its spot) lies on the ground as a pickup of two, and Interact collects both; the
    mod's block lies as its own model, its pickup's own herb hidden, and is collected too; the inventory put back.
    Needs `agent install --with tests/cpp-sdk --with tests/items-mod`."""
    _close_screens(agent)
    r = _request(agent, "drop", timeout=40)
    assert not _failed(r, "drop"), _failed(r, "drop")
    v = r["values"]
    moss, block = v["drop.moss"], v["drop.block"]
    assert moss["name"] == "Moss" and moss["kind"] == "Collectible" and moss["icon"].startswith("/Game/"), moss
    if not block:
        skip("tests/items-mod isn't installed (agent install --with tests/cpp-sdk --with tests/items-mod)")
    assert block["name"] == "Test Block" and block["kind"] == "Collectible", block
    assert v["drop.tags"] > 50, v["drop.tags"]
    # A herb's use, through the game's own lookup (its Consumables.csv row); a material has none.
    herb = v["drop.herb"]
    assert herb["usable"] is True and herb["effect"].startswith("Gameplay.Effect.Consumable.") and herb["target"] in ("Owner", "OwnerTeam"), herb
    assert herb["in_fights"] or herb["exploring"], herb
    assert moss["usable"] is False and moss["effect"] == "", moss
    assert v["drop.map_after_adds"] == {"Gameplay.Inventory.Materials.Ivy": 1, "Gameplay.Inventory.Materials.Moss": 2}, v
    mp = v["drop.moss_pickup"]
    assert mp["reward"] == {"Gameplay.Inventory.Materials.Moss": 2} and mp["own_visible"] is True and mp["model"] is None, mp
    assert mp["z"] < v["drop.cat_z"], (mp["z"], v["drop.cat_z"])   # on the ground, below the cat's middle
    assert v["drop.moss_after"] == v["drop.moss_before"] + 2, (v["drop.moss_before"], v["drop.moss_after"])
    assert v["drop.moss_pickup_after"]["hidden"] is True, v["drop.moss_pickup_after"]
    bp = v["drop.block_pickup"]
    assert bp["reward"] == {"Gameplay.Inventory.Materials.WCModsTestBlock": 1}, bp
    assert bp["model"] and "WCModsTestBlock" in bp["model"] and bp["own_visible"] is False, bp
    assert v["drop.block_after"] >= 1 and v["drop.block_pickup_after"]["hidden"] is True, v
    assert v["drop.moss_restored"] == v["drop.moss_before"], v


def test_animations_cpp(agent):
    """Animations.hpp in the game: the install's mods' animations (tests/animations-mod's Yawn and Stretch, its Trot
    a replacement, not one of them); your cat is a cat; a mod's animation played, seen playing by its id and
    stopped; a game sequence by its path played and seen; the game's own Meow montage afterwards neither taken for it
    nor stopped. Needs `agent install --with tests/cpp-sdk --with
    tests/animations-mod`."""
    _close_screens(agent)
    r = _request(agent, "anims", timeout=30)
    v = r["values"]
    if "animations-mod/Yawn" not in v["anims.list"]:
        skip("tests/animations-mod isn't installed (agent install --with tests/cpp-sdk --with tests/animations-mod)")
    assert not _failed(r, "anims"), _failed(r, "anims")
    yawn = v["anims.list"]["animations-mod/Yawn"]
    assert yawn["kind"] == "cat" and yawn["loop"] is True and yawn["emote"] is True and yawn["key"] == "F7", yawn
    assert "animations-mod/Trot" not in v["anims.list"], v["anims.list"]
    assert v["anims.kind"] == "cat", v["anims.kind"]
    assert v["anims.one"] == "Yawn", v["anims.one"]
    assert v["anims.playing_before"] == "" and v["anims.playing"] == "animations-mod/Yawn", v
    assert v["anims.playing_after_stop"] == "", v
    assert v["anims.playing_game"].endswith("A_CatMaster_Meow.A_CatMaster_Meow"), v["anims.playing_game"]
    assert v["anims.game_montage_played"] is True and v["anims.game_montage_seen_as"] == "", v


def test_quests(agent):
    """Story.hpp's quests in the game, on the test cat: every quest has its story id (its alias) and its live status
    by it; the gather quest (Quest.Main.1) started by its tag goes on; its objective's three Bedding Moss targets are
    out in the world; one collected the player's way (collect_target: the cat on it, Interact) counts on the HUD and
    the objective (with any other target in its reach), and the game's QuestStatus event fires; the objective finished makes the quest complete with
    Success. Scenes seen from the save, none playing; mood asked about without adding a key. This moves the test
    cat's story on, so the save is backed up first and put back after, the game closed and started again for it."""
    _close_screens(agent)
    backup = agent.backup_save("before-quest-test")
    try:
        r = _request(agent, "questline", timeout=40)
    finally:
        agent.quit(force=True)
        agent.restore_save(backup)
        agent.launch(world=True)
    assert not _failed(r, "questline"), _failed(r, "questline")
    v = r["values"]
    assert any(q.startswith("Quest.Main.1 Quest.Procedural.Survival.Gather ") for q in v["questline.listed"]), v["questline.listed"]
    assert v["questline.before"] in ("QuestAvailable", "OngoingQuest") and v["questline.alias_status"] == v["questline.before"], v
    assert v["questline.started"] == "OngoingQuest", v["questline.started"]
    assert v["questline.hud_before"] == "Bedding Moss 0/3", v["questline.hud_before"]
    before = v["questline.targets_before"]
    assert before and before[0]["current"] == 0 and before[0]["target"] == 3 and before[0]["actors"] == 3, before
    # One Interact counts what's in the cat's reach (one target, or two lying close); the HUD shows the objective's count.
    got = v["questline.targets_after"][0]["current"]
    assert got >= 1 and v["questline.hud_after_collect"] == f"Bedding Moss {got}/3", (got, v["questline.hud_after_collect"])
    assert v["questline.events_after_collect"] >= 1, v
    assert (v["questline.finished"], v["questline.finished_result"]) == ("QuestComplete", "Success"), v
    assert v["questline.events"] > v["questline.events_after_collect"], v
    assert "ProphecyIntro" in v["questline.scenes_seen"] and v["questline.scenes_playing"] == 0, v


def test_ui_arrow_units(agent):
    """Ui.hpp's rule for an arrow on a tab's page, at init without the game: its release is given to the screen
    again from a button or check box, never from a slider, number or text box, not when the page hasn't the
    keyboard, not when the press moved the keyboard along a row, and not when the screen had the press."""
    r = _ready(agent, "init")
    ran = {c["name"] for c in r["checks"] if c["name"].startswith("ui.arrows.")}
    assert {"ui.arrows.passed", "ui.arrows.value_control", "ui.arrows.no_keyboard", "ui.arrows.moved_along_row",
            "ui.arrows.screen_had_press"} <= ran, ran
    assert not _failed(r, "init"), _failed(r, "init")


def test_native_units(agent):
    """Core.hpp's pattern check and World.hpp's map reader, on bytes and a map laid out by hand, at init: the
    code check native_address makes, and the TSet the inventory is, with its slots in use, a bit array on the
    heap, and what doesn't add up as a map refused."""
    r = _ready(agent, "init")
    ran = {c["name"] for c in r["checks"] if c["name"].startswith("native.")}
    assert {"native.pattern.exact", "native.pattern.wildcards", "native.pattern.differs", "native.pattern.longer_than_the_code",
            "native.pattern.empty_and_junk", "native.map.in_use", "native.map.heap_bits", "native.map.empty",
            "native.map.refused", "native.unknown"} <= ran, ran
    assert not _failed(r, "init"), _failed(r, "init")


def test_native_function_and_live_inventory(agent):
    """native_address finds the game's AddItem where offsets.json says, its code checked against the signed
    pattern; inventory() reads the game's own map, which is what the game saves: after save_game, WrcGame.json
    holds those items and no others."""
    _ready(agent, "world")
    v = _phase(agent, "native")
    assert v["native.add_item_rva"] == _offsets(agent)["functions"]["SwtQuestInventoryComponent:AddItem"]["rva"], v
    assert v["native.inventory_class"] == agent.lua(
        "return Game.className(Game.get(Game.get(Game.controller(), 'PlayerState'), 'InventoryComponent'))")
    assert v["native.inventory"], v
    _phase(agent, "save")
    assert _saved_inventory(agent) == v["native.inventory"]


def test_add_item_through_the_games_code(agent):
    """add_item puts items in through the game's own AddItem: the count goes up, the HUD's OnItemPickedUp is told
    by the game (tag, how many, the total) and shows the pickup, and the next save holds it; remove_item takes
    them away again, and the save follows."""
    _ready(agent, "world")
    _close_screens(agent)
    # The HUD hears the pickup: none while a screen or a travel's fade is up (the test cat stands by a den
    # entrance, and a stray key from an earlier test can send it travelling).
    agent.wait_lua("(function() for _, h in ipairs(FindAllOf('GuiHudWrc') or {}) do "
                   "if h:IsValid() and h:IsInViewport() then return true end end return false end)()", timeout=30)
    v = _phase(agent, "inventory_add")
    agent.shot("cpp-sdk-add-item")   # the HUD's "<item> OBTAINED 2"
    try:
        assert v["add.after"] == v["add.before"] + 2, v
        assert (v["add.heard"], v["add.heard_tag"], v["add.heard_quantity"], v["add.heard_total"]) == (1, ITEM, 2, v["add.after"]), v
        _phase(agent, "save")
        assert _saved_inventory(agent).get(ITEM) == v["add.after"]
    finally:
        r = _phase(agent, "inventory_remove")
    assert r["remove.before"] == v["add.after"] and r["remove.after"] == v["add.before"], r
    _phase(agent, "save")
    assert _saved_inventory(agent).get(ITEM, 0) == v["add.before"]


def test_command_opens_a_screen_and_send_closes_it(agent):
    """command(L"Player_Show_Inventory") opens the inventory as its key does, through the player's input
    component; ui::close (Button_Back through the screen's own OnListenCommand) closes it. Lua sees both."""
    _ready(agent, "world")
    _close_screens(agent)
    try:
        _phase(agent, "command_open")
        agent.wait_lua(f"{INVENTORY} ~= nil", timeout=5)
        time.sleep(1.0)   # its fade-in
        agent.shot("cpp-sdk-command-inventory")
        v = _phase(agent, "command_close")
        assert v["command.shown"] is True
        agent.wait_lua(f"{INVENTORY} == nil", timeout=5)
    finally:
        _close_screens(agent)


def _settle_sky(agent, timeout=10):
    """Wait until the sky stops changing: a screen closing fades the area's preset back in, and a preset put on
    meanwhile is mixed into that fade."""
    last, end = None, time.time() + timeout
    while time.time() < end:
        now = agent.lua(SKY)
        if last and _close(now, last):
            return
        last = now
        time.sleep(1.0)


def _near(a, b, start, end):
    """Each of fog and light within 5% of the way from `start` to `end` of b's."""
    return all(abs(a[k] - b[k]) <= 0.05 * abs(end[k] - start[k]) for k in ("fog", "light"))


def test_sky_presets(agent):
    """set_sky(L"Night") puts the night preset on and holds it: 3 s later, when the game alone would have faded
    back to the area's sky, Lua reads C++'s night fog and sun still; sky_follow_area() gives the area's back."""
    _ready(agent, "world")
    _close_screens(agent)
    _settle_sky(agent)
    v = _phase(agent, "sky")
    try:
        assert v["sky.class"] == "BP_DayNightSky_C", v
        assert not _near(v["sky.night"], v["sky.before"], v["sky.before"], v["sky.night"]), v
        time.sleep(3.0)
        night = agent.lua(SKY)
        assert _near(night, v["sky.night"], v["sky.night"], v["sky.before"]), (night, v["sky.night"], v["sky.before"])
        agent.shot("cpp-sdk-sky-night")
    finally:
        a = _phase(agent, "sky_area")
    area = agent.lua(SKY)
    assert _close(area, a["sky.area"]) and _close(area, v["sky.before"]), (area, a, v)
    agent.shot("cpp-sdk-sky-area")


def test_sounds(agent):
    """sound_ids are the audio manager's AudioEventsInfo (the AudioEvents table's rows), and play_sound plays
    one by its id, heard everywhere or from a place; an id the game hasn't got plays nothing."""
    _ready(agent, "world")
    _close_screens(agent)
    v = _phase(agent, "sound")
    count = agent.lua("local n = 0 Game.get(Game.manager('audio'), 'AudioEventsInfo'):ForEach(function() n = n + 1 end) return n")
    assert v["sound.count"] == count > 300, (v, count)
    assert v["sound.manager"] == agent.lua("return Game.className(Game.manager('audio'))"), v
    assert (v["sound.ui"], v["sound.ui_sound"], v["sound.ui_playing"]) == ("AudioComponent", "S_Cue_ui_select", True), v
    assert v["sound.there_sound"] == "S_Cue_vo_cat1_happy1", v


def test_montage(agent):
    """play_montage plays a row of the cat's animation table by its tag: Lua sees the same montage playing."""
    _ready(agent, "world")
    _close_screens(agent)
    v = _phase(agent, "montage")
    seen = agent.lua("local ai = Game.player().Mesh:GetAnimInstance() local m = ai:GetCurrentActiveMontage() "
                     "return { playing = ai:IsAnyMontagePlaying(), montage = m and m:IsValid() and Game.name(m) or false }")
    assert v["montage.name"] == seen["montage"] == "AM_Meow" and v["montage.playing"] and seen["playing"], (v, seen)


def test_save_and_its_hash(agent):
    """save_game writes the save; save_hash is the Hash the game gave it, as WrcGame.sav's header has it
    (formats/save.py); and that Hash is next_hash's: the previous Hash, the time of the write and the storage
    manager's address (the formula read from the code, docs/reverse-engineering.md, "The save")."""
    import datetime
    from wcmods.formats import save
    _ready(agent, "world")
    v = _phase(agent, "save")
    old, new = int(v["save.hash_before"]), int(v["save.hash_after"])
    assert new != old and save.SaveGame.load(_save_path("WrcGame.sav")).hash == new, v
    found = [(t, who) for t in range(int(v["save.time_before"]), int(v["save.time_after"]) + 1)
             for who in ("save.storage_address", "save.save_manager_address")
             if save.next_hash(old, datetime.datetime.fromtimestamp(t, datetime.timezone.utc), int(v[who])) == new]
    assert [who for _, who in found] == ["save.storage_address"], (v, found)
