"""Clan Mod Studio's Try Lua in the game page against the running game: its routes, called on a studio made here
(no server, no browser), as the page calls them. The page itself is tested without the game in
tests/studio/unit/console.test.mjs and its no-connection state end to end in tests/studio/e2e/shell.test.mjs."""
from wcmods.agent import skip

NEEDS = "world"


def studio(agent):
    from wcmods.cli import Ctx
    from wcmods.studio import Studio
    st = Studio(Ctx(agent.root, agent.cfg.data_dir))
    if not st.ctx.cfg.data.get("allow_code_mods"):
        skip("the page needs mods that run code allowed in wcmods.json (agent install puts the bridge in regardless)")
    return st


def test_the_strip_says_the_game_is_listening(agent):
    r = studio(agent).api("GET", ["game", "bridge"], {})
    assert r["alive"] and r["bridge_installed"] and r["game_running"], r
    assert r["state"] == "listening" and r["said"] == "The game is running and listening (in the forest)", r


def test_run_a_line(agent):
    r = studio(agent).api("POST", ["game", "lua"], {"code": "return 6 * 7"})
    assert r["ok"] and r["result"] == [42], r


def test_look_inside_your_cat(agent):
    st = studio(agent)
    r = st.api("POST", ["game", "inspect"], {"expr": "Game.player()"})
    info = r["result"][0]
    assert r["ok"] and info.get("props") and info.get("funcs"), r
    more = st.api("POST", ["game", "inspect"], {"expr": "Game.player()", "all": True})["result"][0]
    assert len(more["props"]) > len(info["props"]), "the engine's own members are added with all"
