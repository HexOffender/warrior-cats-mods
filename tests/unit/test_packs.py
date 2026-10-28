"""Mod packs (wcmods/packs.py, modzip.pack) through the studio's API: a pack removed while it plays, the
player's own tools staying on, what keeps a pack's mods out of the game, a pack's .zip made from My mods, and
the preview of a pack holding a mod the player already has."""
import io
import json
import os
import zipfile

from wcmods import modzip, packs
from wcmods.exe import gamebuild
from wcmods.mods import discover

from unit_helpers import make_mod


def call(st, method, path, body=None, query=None, upload=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, query, upload)


def on(studio):
    return {m.id for m in discover(studio.ctx.mods_root) if m.enabled}


def test_removing_the_playing_pack_restores_the_players_mods(studio):
    make_mod(studio, "mine")
    make_mod(studio, "story", {"enabled": False})
    call(studio, "POST", "packs", {"name": "Moon", "mods": ["story"]})
    call(studio, "POST", "packs/moon/play")
    assert on(studio) == {"moon", "story"}
    r = call(studio, "POST", "mods/moon/remove")
    assert r["back_to_my_mods"] is True and on(studio) == {"mine"}
    assert "pack_before" not in studio.ctx.cfg.data and call(studio, "GET", "packs")["playing"] is None


def test_back_to_my_mods_works_when_the_pack_is_gone(studio):
    make_mod(studio, "mine")
    make_mod(studio, "story", {"enabled": False})
    call(studio, "POST", "packs", {"name": "Moon", "mods": ["story"]})
    call(studio, "POST", "packs/moon/play")
    modzip.remove(next(m for m in discover(studio.ctx.mods_root) if m.id == "moon"), studio.ctx.backups)   # by hand
    desc = call(studio, "GET", "packs")
    assert desc["playing"] == "moon" and desc["playing_removed"] is True and desc["playing_name"] == "Moon"
    assert call(studio, "POST", "packs/stop") == {"on": ["mine"], "off": ["story"]}
    assert call(studio, "GET", "packs")["playing"] is None


def test_tools_stay_on_when_a_pack_plays(studio):
    for i in ("menu-pages", "creator-palettes", "emote-wheel", "palette-coat-presets"):
        make_mod(studio, i)
    make_mod(studio, "my-remaps", {"tool": True})
    make_mod(studio, "mine")
    make_mod(studio, "helper")                                  # a mod the pack's mod works with ("uses")
    make_mod(studio, "story", {"enabled": False, "uses": ["helper"]})
    call(studio, "POST", "packs", {"name": "Moon", "mods": ["story"]})
    call(studio, "POST", "packs/moon/play")
    assert on(studio) == {"moon", "story", "helper", "menu-pages", "creator-palettes", "emote-wheel", "my-remaps"}
    tools = {m["id"] for m in call(studio, "GET", "mods") if m["tool"]}
    assert tools == {"menu-pages", "creator-palettes", "emote-wheel", "my-remaps"}
    assert packs.KEPT == ("menu-pages", "creator-palettes", "emote-wheel")


def test_a_pack_with_a_missing_mod_can_be_saved_from_the_page(studio):
    make_mod(studio, "a")
    make_mod(studio, "b")
    call(studio, "POST", "packs", {"name": "Moon", "mods": ["a", "b"]})
    modzip.remove(next(m for m in discover(studio.ctx.mods_root) if m.id == "b"), studio.ctx.backups)
    (p,) = call(studio, "GET", "packs")["packs"]
    assert [(m["id"], m["present"], m["direct"]) for m in p["mods"]] == [("a", True, True), ("b", False, True)]
    # Change it sends the mods that are here: the missing one is dropped.
    assert call(studio, "POST", "packs", {"id": "moon", "name": "Moon", "mods": ["a"]})["requires"] == ["a"]


def test_a_packs_zip_renames_my_mods_and_rewrites_requires(studio, tmp_path):
    make_mod(studio, "my-mods", {"name": "My mods"}, {"names.json": {"prefixes": {"add": ["Moon"]}}})
    make_mod(studio, "moon-cats", {"requires": ["my-mods"], "uses": ["my-mods", "mod-menu"]})
    call(studio, "POST", "packs", {"name": "The Moonlit Path", "mods": ["my-mods", "moon-cats"]})
    found = discover(studio.ctx.mods_root)
    blob = modzip.pack(next(m for m in found if m.id == "the-moonlit-path"), found)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        tops = {n.split("/")[0] for n in z.namelist()}
        meta = {t: json.loads(z.read(f"{t}/mod.json")) for t in tops}
    assert tops == {"the-moonlit-path", "the-moonlit-path-mods", "moon-cats"}
    assert meta["the-moonlit-path"]["requires"] == ["the-moonlit-path-mods", "moon-cats"]
    assert meta["moon-cats"]["requires"] == ["the-moonlit-path-mods"] and meta["moon-cats"]["uses"] == ["the-moonlit-path-mods", "mod-menu"]
    assert meta["the-moonlit-path-mods"]["name"] == "The Moonlit Path: its own content"
    # Your own folders are as they were.
    with open(os.path.join(studio.ctx.mods_root, "moon-cats", "mod.json"), encoding="utf-8") as f:
        assert json.load(f)["requires"] == ["my-mods"]
    # Someone with a My mods of their own adds it: theirs stays, the pack's content goes in beside it, on.
    zpath = tmp_path / "moon.zip"
    zpath.write_bytes(blob)
    other, backups = tmp_path / "other", tmp_path / "backups"
    os.makedirs(other / "my-mods")
    (other / "my-mods" / "mod.json").write_text(json.dumps({"name": "My mods", "enabled": True}), encoding="utf-8")
    modzip.add_zip(str(zpath), str(other), str(backups))
    assert {m.id for m in discover(str(other)) if m.enabled} >= {"the-moonlit-path", "the-moonlit-path-mods", "moon-cats", "my-mods"}


def test_the_preview_marks_a_different_mod_with_the_same_id(studio, tmp_path):
    make_mod(studio, "moon-cats", {"name": "Moon cats"}, {"npcs.json": {"npcs": []}})
    make_mod(studio, "same", {"name": "Same"}, {"names.json": {"a": 1}})
    with open(os.path.join(studio.ctx.mods_root, "same", "names.json"), encoding="utf-8") as f:
        same_text = f.read()
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w") as w:
        w.writestr("pack/mod.json", json.dumps({"name": "Pack", "pack": True, "requires": ["moon-cats", "same"]}))
        w.writestr("moon-cats/mod.json", json.dumps({"name": "Moon cats"}))
        w.writestr("moon-cats/npcs.json", json.dumps({"npcs": [{"id": "moss", "name": "Mossfoot"}]}))
        w.writestr("same/mod.json", json.dumps({"name": "Same", "enabled": False}))
        w.writestr("same/names.json", same_text)
    seen = {m["id"]: m["existing"] for m in call(studio, "POST", "mods/add", query={"step": "preview"}, upload=str(z))["mods"]}
    assert seen["pack"] is None
    assert seen["moon-cats"]["different"] is True and seen["moon-cats"]["take"] is True   # neither says a version
    assert seen["same"]["different"] is False and seen["same"]["take"] is False           # only mod.json differs


def test_a_pack_never_downgrades_an_addon(studio, tmp_path):
    make_mod(studio, "sandbox", {"name": "Sandbox mode", "version": "0.5"}, {"scripts/main.lua": "-- new"})
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w") as w:
        w.writestr("pack/mod.json", json.dumps({"name": "Pack", "pack": True, "requires": ["sandbox"]}))
        w.writestr("sandbox/mod.json", json.dumps({"name": "Sandbox mode", "version": "0.4"}))
        w.writestr("sandbox/scripts/main.lua", "-- old one, longer")
    sandbox = next(m for m in modzip.inspect(str(z), studio.ctx.mods_root) if m["id"] == "sandbox")["existing"]
    assert sandbox["different"] and not sandbox["take"]
    assert sandbox["keep"] == "You have Sandbox mode 0.5; this carries 0.4: keeping yours"
    # A newer one in the pack is ticked.
    z2 = tmp_path / "pack2.zip"
    with zipfile.ZipFile(z2, "w") as w:
        w.writestr("pack/mod.json", json.dumps({"name": "Pack", "pack": True, "requires": ["sandbox"]}))
        w.writestr("sandbox/mod.json", json.dumps({"name": "Sandbox mode", "version": "0.6"}))
        w.writestr("sandbox/scripts/main.lua", "-- newer")
    newer = next(m for m in modzip.inspect(str(z2), studio.ctx.mods_root) if m["id"] == "sandbox")["existing"]
    assert newer["take"] and newer["keep"] is None


def test_describe_lists_a_packs_problems(studio, fake_game, monkeypatch):
    make_mod(studio, "script", {"name": "Script", "game_builds": [gamebuild.VERIFIED_BUILD]}, {"scripts/main.lua": "print(1)"})
    make_mod(studio, "old", {"name": "Old palette", "game_builds": [1]}, {"palette.json": {"fur": {"3": "#112233"}}})
    make_mod(studio, "future", {"name": "Future", "wcmods": "9.0", "game_builds": [gamebuild.VERIFIED_BUILD]})
    make_mod(studio, "fine", {"name": "Fine", "game_builds": [gamebuild.VERIFIED_BUILD]})
    monkeypatch.setenv("WCMODS_GAME_BUILD", str(gamebuild.VERIFIED_BUILD))
    call(studio, "POST", "packs", {"name": "Moon", "mods": ["script", "old", "future", "fine"]})
    (p,) = call(studio, "GET", "packs")["packs"]
    assert p["problems"] == ["Script runs code, so it stays out until you allow mods that run code",
                             "Old palette was made for an older version of the game, so it's left out until it's updated",
                             "Future needs Clan Mod Studio 9.0 or newer; you have 0.4.0: update it"]
    call(studio, "PATCH", "settings", {"allow_code_mods": True})
    assert len(call(studio, "GET", "packs")["packs"][0]["problems"]) == 2
