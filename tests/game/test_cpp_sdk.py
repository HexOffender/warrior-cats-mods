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
                 progression = Game.save.progression("GameplayProgression", "Level"),
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


def _screen_current(agent):
    """The pause screen's current tab control's name, or None without the screen."""
    return agent.lua(f'local s = {PAUSE} if not s then return nil end return Game.name(s.CurrentNav.CurrentControl)')


def _open_pause(agent):
    """Open the pause screen with the keyboard's pause key (P; Enter pauses only in the game's gamepad mode),
    pressing again when the game ignored it (it does for a moment after a screen closes)."""
    for _ in range(4):
        agent.key("P")
        try:
            agent.wait_lua(f'{PAUSE} ~= nil', timeout=2)
            time.sleep(0.6)   # the screen's fade-in
            return True
        except Exception:
            time.sleep(0.8)
    return False


def _walk_to_tab(agent, title, tries=8):
    """Press the game's next-tab key until the pause screen's navigation is on the tab with `title`."""
    for _ in range(tries):
        name = _screen_current(agent)
        if name and agent.lua(f'local s = {PAUSE} local c = s.CurrentNav.CurrentControl return c.Text:ToString()') == title:
            return True
        agent.key("Two")
        time.sleep(0.4)
    return False


def test_ui_widgets(agent):
    """Ui.hpp: every kind of widget made, placed, styled and read back; an overlay on the viewport; the HUD's
    parts; the game's font on the text."""
    r = _request(agent, "ui")
    assert not _failed(r, "ui"), _failed(r, "ui")
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
    when Lua uses them, and leaving the tab puts the game's panel back."""
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
        general = agent.lua(f'local s = {PAUSE} return s.mcGuiPanelGeneral:GetVisibility(), s.mcGuiPanelBonds:GetVisibility()')
        assert general == [1, 1], general   # the game's panels are collapsed while the page shows
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
        # Back to the game's first tab: its panel shows again, the page is gone.
        for _ in range(8):
            agent.key("One")
            time.sleep(0.3)
        v = _request(agent, "ui_snapshot")["values"]
        assert v["ui.tab.active"] is False and v["ui.screen.current"] == "mcGuiTabGeneral", v
        assert agent.lua(f'return {PAUSE}.mcGuiPanelGeneral:GetVisibility()') == 3
    finally:
        agent.key("BackSpace")
        time.sleep(1)
        agent.key("BackSpace")
        time.sleep(0.5)
    v = _request(agent, "ui_snapshot")["values"]
    assert v["ui.screen"] is None and v["ui.screen_shown"] is False and v["ui.tab.page"] is False, v


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
        ui.add(col, { row, ui.labelled("Switch", c), ui.labelled("Slider", s) })
        local canvas = ui.overlay("lua-test", 1200)
        local slot = ui.add(canvas, col)
        ui.place(slot, { position = { 300, 300 }, auto = true })
        local w, h, scale = ui.viewport()
        local vis = ui.visible(t)
        return { text = ui.text(t), kind = Game.className(t), checked = ui.checked(c), value = ui.value(s),
                 rows = #ui.children(col), found = ui.find(col, Game.name(b)):GetAddress() == b:GetAddress(), vis = vis, w = w, scale = scale,
                 canvas = Game.className(canvas), clicked = ui.clicked(b), changed = ui.changed(s),
                 theme = ui.theme().text_size, hud = Game.className(ui.hud()), mini = Game.className(ui.hud("mcGuiMinimap")) }
    """)
    assert out["text"] == "From Lua" and out["kind"] == "TextBlock" and out["checked"] is True, out
    assert abs(out["value"] - 0.25) < 0.01 and out["rows"] == 3 and out["found"] is True, out
    assert out["vis"] == "visible" and out["w"] > 100 and out["scale"] > 0 and out["canvas"] == "CanvasPanel", out
    assert out["clicked"] is False and out["changed"] is False and out["theme"] > 0, out
    assert out["hud"] == "WBP_GuiHudGameWrc_C" and out["mini"] == "WBP_GuiHudControlMinimap_C", out
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
    finally:
        agent.key("BackSpace")
        time.sleep(1)
        agent.lua("WCModsCpp.ui.remove_tab('lua-tab') WCModsCpp.ui.remove_overlay('lua-test')")
    assert agent.lua("local t = WCModsCpp.ui.tabs() for _, id in ipairs(t) do if id == 'lua-tab' then return false end end return true")
