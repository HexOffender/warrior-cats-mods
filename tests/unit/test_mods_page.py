"""Getting set up and the Mods page, through the studio's API over temporary folders: a mod saying which
wcmods it needs, what Apply says it leaves out, the new Get set up steps (scripts, the mods that go with Clan
Mod Studio), and how a mod is named, switched on and previewed when it's added from a .zip or a folder."""
import datetime
import json
import os
import time
import zipfile

import pytest

from wcmods import __version__, mods, modzip, onboarding, pipeline
from wcmods.mods import discover
from wcmods.pipeline import InstallBlocked
from wcmods.studio import NO_GAME

from conftest import make_mod


def call(st, method, path, body=None, query=None, upload=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, query, upload)


def get(st, path, query=None):
    return call(st, "GET", path, query=query)


def post(st, path, body=None, query=None, upload=None):
    return call(st, "POST", path, body, query, upload)


def zip_of(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data if isinstance(data, (str, bytes)) else json.dumps(data))
    return str(path)


def card(st, mod_id):
    return next(m for m in get(st, "mods") if m["id"] == mod_id)


# ---------- the "wcmods" minimum ----------
def test_versions_compare_as_numbers_and_trailing_zeros_dont_count():
    assert __version__ == "0.4.0"
    assert mods.version_key("0.4") == mods.version_key("0.4.0") == (0, 4)
    assert mods.version_key("0.10") > mods.version_key("0.9") and mods.version_key("1") == (1,)
    for bad in ("banana", "", "0.4-beta", "v0.4", None, 0.4, True, "1..2"):
        assert mods.version_key(bad) is None


def test_a_mod_can_say_the_wcmods_it_needs(studio, fake_game, tmp_path):
    make_mod(studio, "future", {"name": "Future palette", "wcmods": "9.0"})
    make_mod(studio, "needs-future", {"name": "Needs future", "requires": ["future"]})
    make_mod(studio, "today", {"name": "Today", "wcmods": "0.4"})
    make_mod(studio, "older", {"name": "Older", "wcmods": "0.2.0"})
    make_mod(studio, "typo", {"name": "Typo", "wcmods": "banana"})   # hand-edited: as good as none
    found = discover(studio.ctx.mods_root)
    too = mods.too_new(found)
    assert too == {"future": f"needs Clan Mod Studio 9.0 or newer; you have {__version__}: update it",
                   "needs-future": "needs Future palette, which needs a newer Clan Mod Studio"}
    # Not a missing requirement, which would stop the install: left out, with the reason on each card.
    assert mods.unmet(found, pipeline.leave_out(studio.ctx.cfg, found)) == {}
    assert card(studio, "future")["problems"] == [f"left out: it needs Clan Mod Studio 9.0 or newer; you have {__version__}: update it"]
    assert card(studio, "needs-future")["problems"] == ["left out: it needs Future palette, which needs a newer Clan Mod Studio"]
    assert card(studio, "today")["problems"] == [] and card(studio, "typo")["wcmods"] is None
    # The build leaves them out with a warning; what stops this install is only the made-up game's files.
    manifest = pipeline.build(studio.ctx.cfg, found, studio.ctx.build_dir, log=lambda m: None)
    assert "future" not in manifest["mods"] and "needs-future" not in manifest["mods"] and "today" in manifest["mods"]
    assert set(manifest["left_out"]) == {"future", "needs-future"} and "requirements" not in manifest["sections"]
    assert any(w.startswith("Future palette is left out: it needs Clan Mod Studio 9.0") for w in manifest["warnings"])
    with pytest.raises(InstallBlocked) as e:
        pipeline.install(studio.ctx.cfg, studio.ctx.build_dir, studio.ctx.backups, log=lambda m: None)
    assert e.value.mods() == [] and "Future" not in str(e.value)
    pipeline.install(studio.ctx.cfg, studio.ctx.build_dir, studio.ctx.backups, log=lambda m: None, force=True)
    assert set(studio.ctx.cfg.data["installed"]["mods"]) == {"today", "older", "typo"}


def test_a_zip_whose_wcmods_isnt_a_version_is_refused_and_a_newer_one_is_said(studio, tmp_path):
    bad = zip_of(tmp_path / "bad.zip", {"bad/mod.json": {"name": "Bad", "wcmods": "banana"}})
    with pytest.raises(ValueError, match='mod.json\'s "wcmods" should be a version like "0.4.0"'):
        post(studio, "mods/add", query={"step": "preview"}, upload=bad)
    for value in (0.4, ["0.4"]):
        with pytest.raises(ValueError, match='"wcmods" should be a version'):
            post(studio, "mods/add", query={"step": "preview"},
                 upload=zip_of(tmp_path / "b.zip", {"b/mod.json": {"name": "B", "wcmods": value}}))
    later = zip_of(tmp_path / "later.zip", {"later/mod.json": {"name": "Later", "wcmods": "1.0"}})
    (m,) = post(studio, "mods/add", query={"step": "preview"}, upload=later)["mods"]
    assert m["wcmods"] == "1.0" and m["too_new"] == f"needs Clan Mod Studio 1.0 or newer; you have {__version__}: update it"


def test_pending_lists_held_back_mods_as_left_out_not_off(studio, fake_game, monkeypatch):
    make_mod(studio, "unpinned", {"name": "Unpinned"})   # no game_builds: made for 24847281
    cfg = studio.ctx.cfg
    built = (datetime.datetime.now() + datetime.timedelta(minutes=1)).isoformat(timespec="seconds")
    cfg.data["installed"] = {"mods": ["unpinned"], "built": built, "game_build": 99999999}
    cfg.save()
    monkeypatch.setenv("WCMODS_GAME_BUILD", "99999999")
    p = pipeline.pending(cfg, discover(studio.ctx.mods_root))
    assert p["left_out"] == {"unpinned": "made for an older version of the game"}
    assert p["off"] == [] and p["on"] == [] and p["any"] is True   # still in the game: the next install takes it out
    changes = get(studio, "changes")
    assert changes["names"]["unpinned"] == "Unpinned" and changes["left_out"] == p["left_out"]
    # Once it's out of the game (an install without it), it's left out with nothing to apply.
    cfg.data["installed"]["mods"] = []
    cfg.save()
    p = pipeline.pending(cfg, discover(studio.ctx.mods_root))
    assert p["left_out"] and p["any"] is False


def test_requirements_are_named_by_name_and_a_missing_addon_by_its_name(studio):
    make_mod(studio, "story", {"name": "Moonlit story", "requires": ["sandbox", "helper", "ghost-mod"]})
    make_mod(studio, "helper", {"name": "Helper", "enabled": False})
    assert card(studio, "story")["problems"] == ["needs Sandbox mode, which isn't in your mods",
                                                 "needs Helper, which is off",
                                                 "needs ghost-mod, which isn't in your mods"]
    with pytest.raises(ValueError, match="Moonlit story needs Sandbox mode, ghost-mod, which isn't in your mods"):
        mods.switch(discover(studio.ctx.mods_root), "story", True)


# ---------- Get set up ----------
def loader(game):
    win64 = os.path.join(game, "Wrc", "Binaries", "Win64")
    for name in ("dwmapi.dll", os.path.join("ue4ss", "UE4SS.dll")):
        with open(os.path.join(win64, name), "wb") as f:
            f.write(b"MZ")


def test_setup_status_counts_the_new_steps(studio, fake_game, save):
    loader(fake_game)
    post(studio, "setup/backup")
    s = get(studio, "setup")
    assert all(s[k]["ok"] for k in ("game", "save", "backup", "loader")) and not s["done"]
    assert s["code"] == {"ok": False, "allowed": False, "skipped": False}
    assert s["addons"] == {"ok": False, "missing": ["menu-pages", "sandbox", "creator-palettes", "emote-wheel"], "choice": None}
    assert post(studio, "setup/code", {"skip": True}) == {"result": {"skipped": True}}
    assert get(studio, "setup")["code"] == {"ok": True, "allowed": False, "skipped": True}
    with pytest.raises(ValueError):
        post(studio, "setup/code", {})
    with pytest.raises(ValueError, match='"added" or "not now"'):
        post(studio, "setup/addons", {"choice": "maybe"})
    post(studio, "setup/addons", {"choice": "added"})
    s = get(studio, "setup")
    assert s["addons"]["ok"] and s["addons"]["choice"] == "added" and s["done"]
    with open(studio.ctx.cfg.path, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["skip_code"] is True and saved["setup_addons"] == "added"


def test_the_setup_steps_are_done_by_allowing_code_and_having_all_four(studio):
    call(studio, "PATCH", "settings", {"allow_code_mods": True})
    assert get(studio, "setup")["code"] == {"ok": True, "allowed": True, "skipped": False}
    for i in ("menu-pages", "sandbox", "creator-palettes", "emote-wheel"):
        make_mod(studio, i)
    assert get(studio, "setup")["addons"] == {"ok": True, "missing": [], "choice": None}
    # Turning code off on Settings and repair is a choice made: the step doesn't ask again.
    call(studio, "PATCH", "settings", {"allow_code_mods": False})
    assert get(studio, "setup")["code"] == {"ok": True, "allowed": False, "skipped": True}


def test_an_older_studios_not_now_for_menu_pages_is_not_now_for_the_addons(studio):
    post(studio, "setup/pages", {"skip": True})
    assert get(studio, "setup")["addons"]["choice"] == "not now" and get(studio, "setup")["addons"]["ok"]


def test_setup_status_does_not_reload_the_shared_config(studio):
    cfg = studio.ctx.cfg
    cfg.data["noted_by_an_install"] = ["not saved yet"]
    shared = cfg.data
    with open(cfg.path, "w", encoding="utf-8") as f:   # what another command wrote meanwhile
        json.dump({"save_dir": cfg.save_dir, "skip_code": True}, f)
    s = onboarding.status(cfg, studio.ctx.backups)
    assert s["code"]["skipped"] is True                   # read afresh
    assert cfg.data is shared and cfg.data["noted_by_an_install"] == ["not saved yet"]   # and not swapped


def test_info_says_no_game_for_a_moved_game_folder(studio, fake_game, tmp_path):
    assert get(studio, "info")["game_dir"] == fake_game
    moved = tmp_path / "Moved"
    moved.mkdir()   # a folder that's there, but not the game's any more
    studio.ctx.cfg.data["game_dir"] = str(moved)
    studio.ctx.cfg.save()
    assert get(studio, "info")["game_dir"] is None and get(studio, "setup")["game"]["ok"] is False
    with pytest.raises(ValueError, match=NO_GAME):
        post(studio, "install")


# ---------- adding mods: names, ids, on and off ----------
def test_safe_id_keeps_accented_letters():
    assert modzip.safe_id("Étoile") == "etoile"
    assert modzip.safe_id("Noël's Mod") == "noel-s-mod"
    assert modzip.safe_id("Ça va") == "ca-va" and modzip.safe_id("???") == "mod"


def test_a_folder_and_a_zip_agree_on_a_mods_id(studio, tmp_path):
    folder = tmp_path / "drop" / "My Story Folder"
    folder.mkdir(parents=True)
    (folder / "mod.json").write_text(json.dumps({"id": "my-story", "name": "My story"}), encoding="utf-8")
    assert [m["id"] for m in modzip.inspect_folder(str(folder.parent), studio.ctx.mods_root)] == ["my-story"]
    added = modzip.add_folder(str(folder.parent), studio.ctx.mods_root, studio.ctx.backups, ids=["my-story"])
    assert [a["id"] for a in added] == ["my-story"] and os.path.isdir(os.path.join(studio.ctx.mods_root, "my-story"))
    z = zip_of(tmp_path / "story.zip", {"My Story Folder/mod.json": {"id": "my-story", "name": "My story"}})
    (m,) = modzip.inspect(z, studio.ctx.mods_root)
    assert m["id"] == "my-story" and m["existing"]["name"] == "My story"


def test_a_version_in_the_zips_name_does_not_become_part_of_the_id(studio, tmp_path):
    first = zip_of(tmp_path / "Cool Mod v1.2.zip", {"mod.json": {"name": "Cool Mod", "version": "1.2"}})
    seen = post(studio, "mods/add", query={"step": "preview", "name": "Cool Mod v1.2.zip"}, upload=first)["mods"]
    assert [m["id"] for m in seen] == ["cool-mod"]
    post(studio, "mods/add", query={"step": "add", "name": "Cool Mod v1.2.zip"}, upload=first)
    second = zip_of(tmp_path / "Cool Mod v1.3.zip", {"mod.json": {"name": "Cool Mod", "version": "1.3"}})
    (m,) = post(studio, "mods/add", query={"step": "preview", "name": "Cool Mod v1.3.zip"}, upload=second)["mods"]
    assert m["id"] == "cool-mod" and m["existing"] == {"name": "Cool Mod", "version": "1.2"}
    post(studio, "mods/add", query={"step": "add", "name": "Cool Mod v1.3.zip"}, upload=second)
    assert [(x["id"], x["version"]) for x in get(studio, "mods")] == [("cool-mod", "1.3")]
    # A name that's nothing but a number stays as it is; a mod folder's name is the maker's, kept whole.
    assert modzip.inspect(zip_of(tmp_path / "2048.zip", {"mod.json": {"name": "Tiles"}}), studio.ctx.mods_root)[0]["id"] == "2048"
    assert modzip.inspect(zip_of(tmp_path / "x.zip", {"kit-2/mod.json": {}}), studio.ctx.mods_root)[0]["id"] == "kit-2"


def test_a_mod_added_by_an_older_studio_is_replaced_by_name(studio, tmp_path):
    make_mod(studio, "cool-mod-v1.2", {"name": "Cool Mod", "version": "1.2"})
    z = zip_of(tmp_path / "Cool Mod v1.3.zip", {"mod.json": {"name": "Cool Mod", "version": "1.3"}})
    (m,) = post(studio, "mods/add", query={"step": "preview", "name": "Cool Mod v1.3.zip"}, upload=z)["mods"]
    assert m["id"] == "cool-mod-v1.2" and m["existing"] == {"name": "Cool Mod", "version": "1.2"}
    post(studio, "mods/add", query={"step": "add", "name": "Cool Mod v1.3.zip"}, upload=z)
    assert [(x["id"], x["version"]) for x in get(studio, "mods")] == [("cool-mod-v1.2", "1.3")]
    # Two mods with that name: no telling which, so it goes in under its own id.
    make_mod(studio, "other-cool", {"name": "Cool Mod"})
    (m,) = modzip.inspect(z, studio.ctx.mods_root, "Cool Mod v1.3.zip")
    assert m["id"] == "cool-mod" and m["existing"] is None


def test_adding_a_mod_whose_requirement_is_missing_leaves_it_off_and_says_why(studio, tmp_path):
    z = zip_of(tmp_path / "moonlit.zip", {"moonlit/mod.json": {"name": "Moonlit cats", "requires": ["sandbox"]},
                                           "moonlit/npcs.json": {"npcs": []}})
    (added,) = post(studio, "mods/add", query={"step": "add"}, upload=z)["added"]
    assert added["on"] is False and added["missing"] == ["sandbox"]
    assert added["off_because"] == "needs Sandbox mode, which you don't have"
    assert card(studio, "moonlit")["enabled"] is False and get(studio, "changes")["any"] is False
    # Once the mod it needs is there, adding it again (or switching it on) turns both on.
    make_mod(studio, "sandbox", {"name": "Sandbox mode", "enabled": False})
    (added,) = post(studio, "mods/add", query={"step": "add"}, upload=z)["added"]
    assert added["on"] is True and added["also_on"] == ["Sandbox mode"] and "off_because" not in added
    # A requirement inside the same .zip (a pack's own mods) is met by it.
    pack = zip_of(tmp_path / "pack.zip", {"a/mod.json": {"name": "A", "requires": ["b"]}, "b/mod.json": {"name": "B"}})
    assert {a["id"]: a["on"] for a in post(studio, "mods/add", query={"step": "add"}, upload=pack)["added"]} == {"a": True, "b": True}


def test_a_multi_mod_zip_keeps_each_mods_shipped_state(studio, tmp_path):
    files = {"creator-palettes/mod.json": {"name": "Creator palettes"},
             "palette-dark-forest/mod.json": {"name": "Dark Forest", "enabled": False},
             "palette-pastel-kits/mod.json": {"name": "Pastel Kits", "enabled": False}}
    z = zip_of(tmp_path / "creator-palettes-1.2.0.zip", files)
    seen = post(studio, "mods/add", query={"step": "preview"}, upload=z)["mods"]
    assert {m["id"]: m["enabled"] for m in seen} == {"creator-palettes": True, "palette-dark-forest": False,
                                                     "palette-pastel-kits": False}
    # The page sends the ticked mods, and of those the ones whose "on" box is ticked.
    q = {"step": "add", "ids": "creator-palettes,palette-dark-forest", "on": "creator-palettes"}
    post(studio, "mods/add", query=q, upload=z)
    assert {m["id"]: m["enabled"] for m in get(studio, "mods")} == {"creator-palettes": True, "palette-dark-forest": False}
    post(studio, "mods/add", query={**q, "on": "creator-palettes,palette-dark-forest"}, upload=z)
    assert {m["id"]: m["enabled"] for m in get(studio, "mods")} == {"creator-palettes": True, "palette-dark-forest": True}
    # The old way, one answer for all, still works.
    post(studio, "mods/add", query={"step": "add", "ids": "palette-pastel-kits", "enable": "1"}, upload=z)
    assert card(studio, "palette-pastel-kits")["enabled"] is True


def test_the_inboxs_add_takes_each_mods_on_state(studio, tmp_path):
    z = zip_of(tmp_path / "two.zip", {"a/mod.json": {"name": "A"}, "b/mod.json": {"name": "B"}})
    onboarding.put_inbox(z)
    added = post(studio, "mods/inbox/add", {"ids": ["a", "b"], "on": ["b"]})["added"]
    assert {a["id"]: a["on"] for a in added} == {"a": False, "b": True}


def test_a_shown_inbox_entry_does_not_expire(studio, tmp_path):
    z = zip_of(tmp_path / "dropped.zip", {"dropped/mod.json": {"name": "Dropped"}})

    def age():   # as if it was left there twenty minutes ago
        with open(onboarding.INBOX, encoding="utf-8") as f:
            data = json.load(f)
        data["time"] = time.time() - 1200
        with open(onboarding.INBOX, "w", encoding="utf-8") as f:
            json.dump(data, f)
    onboarding.put_inbox(z)
    age()
    assert onboarding.inbox() is None   # never shown: gone after ten minutes
    onboarding.put_inbox(z)
    assert get(studio, "mods/inbox")["name"] == "dropped.zip"   # the page shows it
    age()
    assert onboarding.inbox() == os.path.abspath(z) and get(studio, "mods/inbox")["name"] == "dropped.zip"

