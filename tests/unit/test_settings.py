"""Settings and repair through the studio's API: restoring a backup (and what it says), backups only of a save
that's there, only backups put back, why the console can't be used, a controller button set by hand, and
making a mod from a name alone."""
import datetime
import json
import os

import pytest

from wcmods import pipeline
from wcmods.formats import save
from wcmods.formats.save import SAV_NAME
from wcmods.mods import discover

from unit_helpers import make_mod, write_save


def call(st, method, path, body=None, query=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, query, None)


def test_a_restore_says_where_the_old_save_went_and_asks_for_nothing(studio, save):
    make_mod(studio, "edits")
    cfg = studio.ctx.cfg
    built = (datetime.datetime.now() + datetime.timedelta(minutes=1)).isoformat(timespec="seconds")
    cfg.data["installed"] = {"mods": ["edits"], "built": built}
    cfg.save()
    first = call(studio, "POST", "backup")["name"]
    before = pipeline.pending(cfg, discover(studio.ctx.mods_root))
    r = call(studio, "POST", "restore", {"name": first})
    assert r["restored"] == [SAV_NAME] and r["before"].endswith("-before-restore")
    assert r["before_label"].startswith("Today ") and r["before_label"].endswith("the save you had before a restore")
    # Restoring is how save edits are undone: nothing asks to apply again.
    assert pipeline.pending(cfg, discover(studio.ctx.mods_root)) == before


def test_backup_without_a_save_leaves_no_folder_from_any_caller(studio, tmp_path):
    backups = studio.ctx.backups
    with pytest.raises(ValueError, match="no save to back up yet"):
        save.backup(studio.ctx.cfg.save_dir, backups, "manual")
    with pytest.raises(ValueError, match="no save to back up yet"):
        save.backup(str(tmp_path / "not-there"), backups, "before-save-edits")   # a save folder the game hasn't made
    with pytest.raises(ValueError, match="no save to back up yet"):
        call(studio, "POST", "backup")
    assert save.list_backups(backups) == [] and not os.path.isdir(backups)
    # A restore with no save of your own yet puts the backup back without a "before" copy of nothing.
    write_save(studio.ctx.cfg.save_dir)
    first = call(studio, "POST", "backup")["name"]
    os.remove(os.path.join(studio.ctx.cfg.save_dir, SAV_NAME))
    r = call(studio, "POST", "restore", {"name": first})
    assert r["before"] is None and r["restored"] == [SAV_NAME]


def test_restore_refuses_a_name_outside_the_backups(studio, save):
    first = call(studio, "POST", "backup")["name"]
    os.makedirs(os.path.join(studio.ctx.backups, "mods", "20260101-000000-removed-x"))
    for bad in ("..", "../data", "mods", "mods/20260101-000000-removed-x", "20260101-000000-nope", first + "/.."):
        with pytest.raises(LookupError, match="no backup called"):
            call(studio, "POST", "restore", {"name": bad})
    assert [b["name"] for b in call(studio, "GET", "backups")] == [first]   # no "before" copy made for a refusal


def test_backups_are_named_in_words():
    day = datetime.date(2026, 10, 28)
    assert save.backup_label("20261028-153000-studio", day) == "Today 15:30, backed up by you"
    assert save.backup_label("20261027-091200-first-run", day) == "First safety copy, Yesterday 09:12"
    assert save.backup_label("20261001-080000-before-save-edits-2", day) == "1 Oct 2026 08:00, before Apply (save edits)"
    assert save.backup_label("20261028-153000-something-new", day) == "Today 15:30, something new"
    assert save.backup_label("odd", day) == "odd"


def test_console_unavailable_says_why(studio, fake_game):
    assert call(studio, "GET", "ingame")["console_why"] == "no console mod in it"   # the made-up game has ue4ss/Mods
    os.rename(os.path.join(fake_game, "Wrc", "Binaries", "Win64", "ue4ss"), os.path.join(fake_game, "x"))
    assert call(studio, "GET", "ingame")["console_why"] == "no script loader"
    os.makedirs(os.path.join(fake_game, "Wrc", "Binaries", "Win64", "ue4ss", "Mods", "ConsoleEnablerMod"))
    o = call(studio, "GET", "ingame")
    assert o["console_available"] is True and o["console_why"] is None


def test_a_hand_set_pad_can_be_chosen_again(studio):
    cfg = studio.ctx.cfg
    cfg.data["menu_pad"] = "Gamepad_RightShoulder"   # set by hand in wcmods.json, not one the studio offers
    cfg.save()
    o = call(studio, "GET", "ingame")
    assert o["pad"] == "Gamepad_RightShoulder" and "Gamepad_RightShoulder" not in [p for p, _ in o["pads"]]
    call(studio, "PATCH", "ingame", {"pad": o["pads"][0][0]})
    assert call(studio, "PATCH", "ingame", {"pad": "Gamepad_RightShoulder"})["pad"] == "Gamepad_RightShoulder"
    with pytest.raises(ValueError, match="pad should be one of"):
        call(studio, "PATCH", "ingame", {"pad": "not a key!"})


def test_make_your_own_mod_takes_a_name(studio):
    assert call(studio, "GET", "mods/new-id", query={"name": "Étoile's Tweaks"}) == {"id": "etoile-s-tweaks"}
    m = call(studio, "POST", "mods", {"name": "Étoile's Tweaks", "enabled": True})
    assert m["id"] == "etoile-s-tweaks" and m["name"] == "Étoile's Tweaks" and m["enabled"] is True
    assert call(studio, "GET", "mods/new-id", query={"name": "Étoile's tweaks"}) == {"id": "etoile-s-tweaks-2"}
    assert call(studio, "POST", "mods", {"name": "ÉTOILE'S TWEAKS"})["id"] == "etoile-s-tweaks-2"
    with open(os.path.join(studio.ctx.mods_root, "etoile-s-tweaks", "mod.json"), encoding="utf-8") as f:
        assert json.load(f)["name"] == "Étoile's Tweaks"
