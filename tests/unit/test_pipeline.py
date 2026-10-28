"""What Apply and Play decide before they build: pipeline.pending, which says what the game hasn't got yet, over a
made-up game folder and a studio's own wcmods.json."""
from wcmods import bridge, pipeline


def installed(cfg, ue4ss_mods, **more):
    """wcmods.json as an install with nothing on, made with the script loader there, leaves it."""
    cfg.data["installed"] = {"mods": [], "built": "2026-10-28T09:00:00", "ue4ss": True, "mods_root": cfg.mods_root,
                             "game_dir": cfg.game_dir, **more}
    cfg.data["installed_ue4ss"] = list(ue4ss_mods)
    cfg.save()


def test_pending_counts_code_mods_newly_allowed(studio, fake_game):
    # Allowing mods that run code since the last install asks for an Apply, with no code mod on (the bridge, which
    # the Console needs, and every mod's code are missing from the game); once the bridge is in, nothing more.
    cfg = studio.ctx.cfg
    installed(cfg, ["WCModsMenuHost"])
    assert pipeline.pending(cfg, [])["redo"] == []
    studio.api("PATCH", ["settings"], {"allow_code_mods": True})
    p = pipeline.pending(cfg, [])
    assert p["redo"] == ["mods that run code are allowed now, and the game doesn't have them yet"] and p["any"]
    cfg.reload()
    installed(cfg, ["WCModsMenuHost", bridge.NAME])
    assert pipeline.pending(cfg, []) == {"installed": True, "on": [], "off": [], "changed": [], "redo": [], "any": False}


def test_pending_says_the_script_loader_once_when_it_came_after_the_install(studio, fake_game):
    # An install made before the script loader was there left out the menu and every script: that's the one
    # reason given, not a second one about code mods too.
    cfg = studio.ctx.cfg
    cfg.data["allow_code_mods"] = True
    installed(cfg, [], ue4ss=False)
    assert pipeline.pending(cfg, [])["redo"] == ["the script loader (UE4SS) is in now"]


def test_pending_asks_nothing_about_code_mods_without_the_script_loader(studio):
    # No game folder, so no UE4SS: nothing that runs code could go in, so allowing it asks for nothing.
    cfg = studio.ctx.cfg
    cfg.data["allow_code_mods"] = True
    installed(cfg, [])
    assert pipeline.pending(cfg, [])["redo"] == []
