"""Reading UE4SS.log for what each script mod did when the game last started (wcmods/scriptlog.py), over logs laid
out as UE4SS 3.0.1 writes them (read from the installed game's log on 2026-10-28), in the harness's made-up game
folder; and the Mods page's line and What it said from it."""
import os

import pytest

from wcmods import scriptlog

from unit_helpers import make_mod

# A session: UE4SS's start-up dump (with names that have "Error" in them), three script mods started (one loads,
# one doesn't, one prints without its name as it starts and then fails every frame), and their lines after.
LOG = """\
[2026-10-28 09:12:01.1398320] Console created
[2026-10-28 09:12:01.1475629] UE4SS - v3.0.1 Beta #0 - Git SHA #83330635
[2026-10-28 09:12:03.9967231] FArchiveState::ArIsError = 0x29
[2026-10-28 09:12:04.0088003] UWorld::bKismetScriptError = 0x18D
[2026-10-28 09:12:04.1243987] [Lua] Exposing size of 'class RC::Unreal::FObjectProperty' as 0x8
[2026-10-28 09:12:04.1491677] Starting Lua mod 'WCModsCore'
[2026-10-28 09:12:04.1655815] [Lua] [WCModsCore] loaded
[2026-10-28 09:12:04.1656879] Starting Lua mod 'WCModsScript_game_tweaks'
[2026-10-28 09:12:04.1967715] [RegisterHook] Registered native hook (3, 4) for Function /Script/Wrc.GuiHudWrc:OnItemPickedUp
[2026-10-28 09:12:04.2100175] [Lua] [Game Tweaks] loaded
[2026-10-28 09:12:04.2100573] Starting Lua mod 'WCModsScript_broken_script'
[2026-10-28 09:12:04.2200000] [Lua] [Broken script] can't load: scripts/main.lua:3: 'end' expected (to close 'function' at line 1) near <eof>
[2026-10-28 09:12:04.2523795] Starting Lua mod 'WCModsScript_noisy_script'
[2026-10-28 09:12:04.2600000] [Lua] hello from a plain print
[2026-10-28 09:12:04.4195790] Starting mods (from enabled.txt (D:\\Game\\ue4ss\\Mods), no defined load order)...
[2026-10-28 09:12:04.4199433] Event loop start
[2026-10-28 09:12:36.2840828] [Lua] [Noisy script] error in onFrame: scripts/main.lua:2: attempt to index a nil value (global 'cat')
stack traceback:
\t[C]: in ?
[2026-10-28 09:13:36.2840828] [Lua] [Noisy script] error in onFrame: scripts/main.lua:2: attempt to index a nil value (global 'cat') (3600 more)
[2026-10-28 09:13:40.0819344] Error: [Lua::Registry::get_function_ref] Ref was not function
[2026-10-28 09:13:41.0000000] [Lua] [Game Tweaks] healed Fawnstar
"""
SCRIPTS = {"game-tweaks": "Game Tweaks", "broken-script": "Broken script", "noisy-script": "Noisy script",
           "never-ran": "Never ran"}


@pytest.fixture
def game_log(studio, fake_game):
    """Four script mods, the last install (built before the session above) having put them in, and a function that
    writes UE4SS.log (text, or bytes as they are) in the made-up game: returns it."""
    for mod_id, name in SCRIPTS.items():
        make_mod(studio, mod_id, {"name": name}, {"scripts/main.lua": "-- " + mod_id})
    cfg = studio.ctx.cfg
    cfg.data["installed"] = {"mods": list(SCRIPTS), "built": "2026-10-28T09:00:00", "ue4ss": True}
    cfg.data["installed_ue4ss"] = ["WCModsMenuHost"] + [f"WCModsScript_{i.replace('-', '_')}" for i in SCRIPTS]
    cfg.save()
    path = os.path.join(fake_game, "Wrc", "Binaries", "Win64", "ue4ss", "UE4SS.log")

    def write(text=LOG):
        with open(path, "wb") as f:
            f.write(text if isinstance(text, bytes) else text.encode("utf-8"))
        return path
    return write


def report(studio):
    return scriptlog.report(studio.ctx.cfg, studio.mods())


def test_started_and_loaded(studio, game_log):
    path = game_log()
    r = report(studio)
    assert (r["log"], r["session"], r["run_since_apply"]) == (path, "2026-10-28 09:12:01", True)
    tweaks = r["mods"]["game-tweaks"]
    assert (tweaks["state"], tweaks["said"]) == ("loaded", "Loaded when the game last started")
    assert tweaks["started"] and tweaks["loaded"] and tweaks["errors"] == []
    assert tweaks["lines"] == ["09:13:41  healed Fawnstar", "09:12:04  loaded"]   # newest first


def test_cant_load_is_an_error(studio, game_log):
    game_log()
    broken = report(studio)["mods"]["broken-script"]
    assert broken["started"] and not broken["loaded"] and broken["state"] == "failed"
    assert broken["said"] == ("Didn't load when the game last started: scripts/main.lua:3: 'end' expected (to close "
                              "'function' at line 1) near <eof>")
    # How older versions of the script bootstrap said it, from a log written before this one.
    game_log(LOG.replace("can't load: ", "can't load scripts/main.lua: "))
    assert report(studio)["mods"]["broken-script"]["errors"][0].startswith("scripts/main.lua:3: 'end' expected")


def test_runtime_error_carries_the_mods_name(studio, game_log):
    game_log()
    noisy = report(studio)["mods"]["noisy-script"]
    assert noisy["loaded"] and noisy["state"] == "errors"
    # Said again a minute later with a count, it's still one error; the plain print as it started is its own.
    assert noisy["errors"] == ["onFrame: scripts/main.lua:2: attempt to index a nil value (global 'cat')"]
    assert noisy["said"] == ("Loaded when the game last started, then hit an error: onFrame: scripts/main.lua:2: attempt "
                             "to index a nil value (global 'cat')")
    assert noisy["lines"][-1] == "09:12:04  hello from a plain print"
    assert noisy["lines"][1].startswith("09:12:36  error in onFrame:") and "stack traceback:" in noisy["lines"][1]


def test_a_timers_error_counts_whatever_it_says_and_a_scripts_own_words_dont(studio, game_log):
    # WCModsGame starts a timer's, key's or hook's error with "error in", so one raised with error("no cat yet")
    # counts too; a script's own line that happens to say "key" or "every" doesn't.
    game_log(LOG + "[2026-10-28 09:14:00.0000000] [Lua] [Game Tweaks] key pressed: F5, every cat healed\n"
                   "[2026-10-28 09:14:01.0000000] [Lua] [Game Tweaks] error in every: scripts/main.lua:9: no cat yet\n")
    tweaks = report(studio)["mods"]["game-tweaks"]
    assert tweaks["errors"] == ["every: scripts/main.lua:9: no cat yet"] and tweaks["state"] == "errors"
    assert tweaks["lines"][1] == "09:14:00  key pressed: F5, every cat healed"


def test_ue4ss_boot_dump_is_not_an_error(studio, game_log):
    # ArIsError, bKismetScriptError and UE4SS's own "Error:" line belong to no mod.
    game_log()
    for mod_id, entry in report(studio)["mods"].items():
        assert not any("ArIsError" in e or "Kismet" in e or "Registry" in e for e in entry["errors"] + entry["lines"]), mod_id


def test_a_mod_with_no_lines_did_not_start(studio, game_log):
    game_log()
    never = report(studio)["mods"]["never-ran"]
    assert not never["started"] and never["state"] == "not-started"
    assert never["said"] == "Didn't start when the game last started (the script loader didn't run it)"


def test_log_older_than_the_apply_is_not_run_since(studio, game_log):
    game_log()
    cfg = studio.ctx.cfg
    cfg.data["installed"]["built"] = "2026-10-28T10:00:00"   # applied after that session
    cfg.save()
    r = report(studio)
    assert r["run_since_apply"] is False
    assert {i: m["said"] for i, m in r["mods"].items()} == {i: "Hasn't run since you applied" for i in SCRIPTS}


def test_no_log_file(studio, game_log):
    r = report(studio)
    assert (r["log"], r["session"], r["run_since_apply"]) == (None, None, False)
    assert r["mods"]["game-tweaks"]["state"] == "waiting" and r["mods"]["game-tweaks"]["lines"] == []


def test_a_mod_not_installed_gets_no_line(studio, game_log):
    # Left out of the last install (mods that run code were off): nothing to say about a game it wasn't in.
    game_log()
    cfg = studio.ctx.cfg
    cfg.data["installed_ue4ss"] = ["WCModsMenuHost"]
    cfg.save()
    tweaks = report(studio)["mods"]["game-tweaks"]
    assert tweaks["installed"] is False and tweaks["state"] is None and tweaks["said"] is None


def test_crlf_and_bom(studio, game_log):
    game_log(b"\xef\xbb\xbf" + LOG.replace("\n", "\r\n").encode("utf-8"))
    r = report(studio)
    assert r["session"] == "2026-10-28 09:12:01"
    assert r["mods"]["game-tweaks"]["lines"] == ["09:13:41  healed Fawnstar", "09:12:04  loaded"]
    assert r["mods"]["broken-script"]["state"] == "failed"


def test_start_lines_past_the_tail_are_still_found(studio, game_log, monkeypatch):
    # A long session: UE4SS's start lines are at the top and the mods' latest lines at the end, with more than the
    # tail between them. Both ends are read; what's between isn't needed.
    monkeypatch.setattr(scriptlog, "HEAD", 4096)
    monkeypatch.setattr(scriptlog, "TAIL", 4096)
    head, rest = LOG.split("[2026-10-28 09:12:36", 1)
    filler = "".join(f"[2026-10-28 09:12:{10 + i % 40:02d}.0000000] [Lua] [WCModsBridge] busy {i}\n" for i in range(400))
    game_log(head + filler + "[2026-10-28 09:12:36" + rest)
    r = report(studio)
    assert r["mods"]["game-tweaks"]["state"] == "loaded" and r["mods"]["broken-script"]["state"] == "failed"
    assert r["mods"]["game-tweaks"]["lines"][0] == "09:13:41  healed Fawnstar"
    assert r["mods"]["noisy-script"]["state"] == "errors"


def test_the_card_says_how_the_script_did_and_more_shows_what_it_said(studio, game_log, sandbox):
    path = game_log()
    cards = {m["id"]: m for m in studio.api("GET", ["mods"], {})}
    assert cards["game-tweaks"]["script_run"] == {"state": "loaded", "said": "Loaded when the game last started"}
    assert cards["broken-script"]["script_run"]["state"] == "failed"
    said = studio.api("GET", ["mods", "noisy-script", "log"], {})
    assert said["log"] == path and said["run_since_apply"] and said["lines"][0].startswith("09:13:36  error in onFrame:")
    make_mod(studio, "no-script")
    with pytest.raises(LookupError, match="has no in-game script"):
        studio.api("GET", ["mods", "no-script", "log"], {})
    # Open the log file opens UE4SS.log itself, in whatever opens text files.
    assert studio.api("POST", ["open"], {"what": "log"}) == {"opened": path}
    assert sandbox.opened[-1] == path


def test_opening_the_log_before_the_game_made_one_says_so(studio, fake_game):
    with pytest.raises(LookupError, match="There's no log yet"):
        studio.api("POST", ["open"], {"what": "log"})
