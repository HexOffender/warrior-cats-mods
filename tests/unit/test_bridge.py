"""The game bridge (wcmods/bridge.py) over a temp folder, with no game: a thread plays the game's part (bridge.lua's
poll: take request.lua by removing it, write reply.json) where a test needs one. The Lua side is checked by its
shape here and run in the game by tests/game/test_bridge.py."""
import json
import os
import re
import threading
import time
from types import SimpleNamespace

import pytest

from wcmods import bridge, luacheck
from wcmods.bridge import Bridge, BridgeError


@pytest.fixture
def br(tmp_path):
    """A Bridge whose folder (WCMods/bridge beside the saves, as the game's) is under tmp_path, made."""
    b = Bridge(SimpleNamespace(save_dir=str(tmp_path / "Saved" / "SaveGames")))
    os.makedirs(b.dir)
    return b


def write_status(b, age=0.0, **status):
    path = os.path.join(b.dir, "status.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(status or {"time": 1}, f)
    then = time.time() - age
    os.utime(path, (then, then))


def game(b, answer=lambda rid: {"id": rid, "ok": True, "result": [42], "output": "", "ms": 0}, after=0.05):
    """The game's side in a thread: waits for request.lua, takes it (removes it), and writes what answer(rid) gives
    (a reply, a list of them, or None for none) as reply.json. Returns the thread and what it saw."""
    seen = {}

    def run():
        request = os.path.join(b.dir, "request.lua")
        end = time.time() + 5
        while time.time() < end and not os.path.exists(request):
            time.sleep(0.01)
        time.sleep(after)
        with open(request, encoding="utf-8") as f:
            text = f.read()
        seen["request"] = text
        rid = re.match(r"--wcmods-id:(\w+)", text).group(1)
        os.remove(request)
        replies = answer(rid)
        for reply in replies if isinstance(replies, list) else [replies]:
            if reply is None:
                continue
            tmp = os.path.join(b.dir, "reply.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(reply, f)
            os.replace(tmp, os.path.join(b.dir, "reply.json"))
            time.sleep(0.15)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t, seen


def test_no_status_means_no_game(br):
    assert br.status() is None
    with pytest.raises(BridgeError, match="isn't running with the bridge") as e:
        br.run("return 1")
    assert e.value.kind == "down"
    assert not os.path.exists(os.path.join(br.dir, "request.lua"))


def test_status_age_decides_alive(br):
    write_status(br, age=6)
    assert br.status()["alive"] is False
    write_status(br, age=1, world="L_WorldMap_01_P")
    st = br.status()
    assert st["alive"] is True and st["world"] == "L_WorldMap_01_P" and 0.5 < st["age"] < bridge.ALIVE


def test_half_written_status_is_none(br):
    with open(os.path.join(br.dir, "status.json"), "w", encoding="utf-8") as f:
        f.write('{"time": 1, "wor')
    assert br.status() is None


def test_status_retries_during_a_rewrite(br):
    # The bridge removes status.json, then renames the new one in: a reader in between looks again a moment later.
    def rewrite():
        time.sleep(0.02)
        write_status(br, world="L_WorldMap_01_P")

    t = threading.Thread(target=rewrite)
    t.start()
    st = br.status()
    t.join()
    assert st is not None and st["alive"] and st["world"] == "L_WorldMap_01_P"


def test_a_request_runs_and_its_reply_comes_back(br):
    write_status(br)
    t, seen = game(br)
    reply = br.run("return 6 * 7", timeout=5)
    t.join()
    assert reply["ok"] and reply["result"] == [42]
    assert seen["request"].endswith("\nreturn 6 * 7")
    assert os.listdir(br.dir) == ["status.json"], "the reply, the request and the lock are all gone"


def test_reply_with_another_id_is_ignored(br):
    write_status(br)
    t, _ = game(br, answer=lambda rid: [{"id": "someone-else", "ok": True, "result": [1]},
                                        {"id": rid, "ok": True, "result": [2]}])
    reply = br.run("return 2", timeout=5)
    t.join()
    assert reply["result"] == [2]


def test_timeout_withdraws_the_request(br):
    # The game never takes it (a loading screen): it's taken back, so it can't run later, and the lock goes.
    write_status(br)
    with pytest.raises(BridgeError, match="the request was withdrawn, so it won't run later") as e:
        br.run("Game.time.set(6, 0)", timeout=0.3)
    assert e.value.kind == "withdrawn"
    assert sorted(os.listdir(br.dir)) == ["status.json"]


def test_timeout_leaves_a_request_the_game_took(br):
    # The game took it and is still on it (a long line): nothing to withdraw, and the message says so.
    write_status(br)
    t, _ = game(br, answer=lambda rid: None)
    with pytest.raises(BridgeError, match="the game took the request and is still running it") as e:
        br.run("while true do end", timeout=0.5)
    t.join()
    assert e.value.kind == "running"
    assert not os.path.exists(os.path.join(br.dir, "request.lua")) and not os.path.exists(os.path.join(br.dir, "lock"))


def test_a_reply_that_comes_as_the_time_runs_out_is_kept(br, monkeypatch):
    # The game took the request, and its reply landed between the last look and the timeout: it's the answer,
    # not "still running" (and not a reply left for the next request to throw away).
    write_status(br)
    real = Bridge._withdraw

    def withdraw_after_the_reply(request, rid):
        os.remove(request)   # the game takes it ...
        with open(os.path.join(br.dir, "reply.json"), "w", encoding="utf-8") as f:
            json.dump({"id": rid, "ok": True, "result": [7]}, f)   # ... and answers, just too late for the loop
        return real(request, rid)

    monkeypatch.setattr(Bridge, "_withdraw", staticmethod(withdraw_after_the_reply))
    assert br.run("return 7", timeout=0.2)["result"] == [7]
    assert os.listdir(br.dir) == ["status.json"]


def test_lock_held_by_another_client(br):
    write_status(br)
    open(os.path.join(br.dir, "lock"), "w").close()
    with pytest.raises(BridgeError, match="another wcmods command is talking to the game") as e:
        br.run("return 1", timeout=0.3)
    assert e.value.kind == "busy"
    assert os.path.exists(os.path.join(br.dir, "lock")), "another client's lock is left alone"
    assert not os.path.exists(os.path.join(br.dir, "request.lua"))


def test_stale_lock_is_taken_over(br):
    write_status(br)
    lock = os.path.join(br.dir, "lock")
    open(lock, "w").close()
    old = time.time() - bridge.STALE_LOCK - 5
    os.utime(lock, (old, old))
    t, _ = game(br)
    assert br.run("return 1", timeout=5)["ok"]
    t.join()
    assert not os.path.exists(lock)


def test_inspect_code_refuses_a_blank_expression():
    for blank in ("", "   ", None):
        with pytest.raises(ValueError, match=r"type an object to look at, e\.g\. Game\.player\(\)"):
            bridge.inspect_code(blank)


def test_inspect_code_compiles():
    for everything in (False, True):
        lua = bridge.inspect_code("Game.player()", everything)
        assert not luacheck.check(lua)
        assert lua.startswith("\nlocal o = (Game.player())") and f"Game.properties(o, {str(everything).lower()})" in lua


def test_where_says_the_level_in_words():
    assert bridge.where({"world": "L_WorldMap_01_P"}) == "in the forest"
    assert bridge.where({"world": "L_MainMenu_P"}) == "in the main menu"
    assert bridge.where({"world": "L_Den"}) == "in L_Den"
    assert bridge.where({}) == bridge.where(None) == "loading"


def test_bridge_script_takes_only_what_it_removed_and_stops_a_runaway_line(tmp_path):
    # bridge.lua runs a request only once it has removed it (a request being withdrawn is never run), and a line
    # that runs on is stopped by a count hook set around it and cleared after, in the bridge's own Lua state.
    lua = bridge.script(SimpleNamespace(save_dir=str(tmp_path / "Saves")))
    assert not luacheck.check(lua) and not re.findall(r"@[A-Z_]+@", lua)
    assert "if not os.remove(REQUEST) then return end" in lua
    run = lua[lua.index("local function run(code)"):lua.index("local function poll()")]
    hook = run.index("debug.sethook(stop, \"\", RUNAWAY)")
    assert hook < run.index("xpcall(fn, debug.traceback)") < run.index("debug.sethook()")
    assert 'error("this line ran too long and was stopped", 2)' in lua and "local RUNAWAY = 100000000" in lua
