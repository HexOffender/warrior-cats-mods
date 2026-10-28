"""Save edits made once per save (pipeline.apply_save_ops, saverecord): a change is made after a backup and
recorded, never made again over what the player has played since; a mod whose value changes makes it again,
"always" makes it every time; a mod another mod's change won over isn't counted as made; restoring a backup puts
back the record it kept (or, for one made before the record, forgets what came after it); Put it back writes
the old value and stays put back. Over a temp save in the studio fixture's folders, never the player's."""
import json
import os
import time

import pytest

from wcmods import pipeline, saverecord
from wcmods.formats.save import SAV_NAME, SaveGame, list_backups
from wcmods.formats.savejson import SaveDoc

from unit_helpers import make_mod, write_save

LEVEL = "1/GameplayProgression/Level"
INV = "1/GameplayProgression/State/Inventory"
SAVE = {"acct": {"1": {"GameplayProgression": {"Level": 5, "Experience": 120,
                                               "State": {"Inventory": {"Gameplay.Inventory.Materials.Moss": 4,
                                                                       "Gameplay.Inventory.Materials.Cobweb": 1}}}},
                 "Shared": {"General": {"CurrentCatSlot": 1}}}}


@pytest.fixture
def cfg(studio):
    write_save(studio.ctx.cfg.save_dir, SAVE)
    return studio.ctx.cfg


def backups(studio):
    return list_backups(studio.ctx.backups)


def doc(cfg):
    return SaveDoc(SaveGame.load(os.path.join(cfg.save_dir, SAV_NAME)).json_text)


def level_op(value, source="my-mod", **more):
    return {"op": "set", "path": LEVEL, "value": value, "section": "save", "source": source, "once": True,
            "label": "your cat's level", **more}


def apply(studio, ops):
    lines = []
    out = pipeline.apply_save_ops(studio.ctx.cfg, ops, studio.ctx.backups, lines.append)
    return out, lines


def play(cfg, path, value):
    """The game moving the save on: a value changed in play."""
    d = doc(cfg)
    d.set(path, value)
    data = json.loads(d.text)
    write_save(cfg.save_dir, data)


def test_a_matching_set_makes_no_backup(studio, cfg):
    out, lines = apply(studio, [level_op(5)])
    assert out["changed"] == [] and out["backup"] is None and backups(studio) == []
    assert "  save already matches; nothing to change" in lines
    # Recorded all the same: it's made, as far as this save goes.
    assert saverecord.entry(saverecord.load(cfg), "acct", "my-mod", LEVEL)["value"] == 5


def test_a_changed_set_backs_up_writes_and_records(studio, cfg):
    out, lines = apply(studio, [level_op(10)])
    assert doc(cfg).get(LEVEL) == 10 and len(backups(studio)) == 1
    assert out["backup"] == backups(studio)[0] and out["backup"].endswith("-before-save-edits")
    assert "  save: your cat's level: 5 -> 10" in lines
    assert out["applied"] == [{"source": "my-mod", "path": LEVEL, "label": "your cat's level", "was": 5, "now": 10, "op": "set"}]
    e = saverecord.entry(saverecord.load(cfg), "acct", "my-mod", LEVEL)
    assert e["value"] == 10 and e["was"] == 5 and e["backup"] == out["backup"] and e["label"] == "your cat's level"


def test_applying_again_after_the_save_moved_on_leaves_it(studio, cfg):
    apply(studio, [level_op(10)])
    play(cfg, LEVEL, 14)
    out, lines = apply(studio, [level_op(10)])   # an Apply for something else, the mod still on
    assert doc(cfg).get(LEVEL) == 14 and out["changed"] == [] and len(backups(studio)) == 1


def test_a_changed_mod_value_applies_again(studio, cfg):
    apply(studio, [level_op(10)])
    out, _ = apply(studio, [level_op(18)])
    assert doc(cfg).get(LEVEL) == 18 and out["applied"][0]["was"] == 10


def test_always_re_forces(studio, cfg):
    op = {k: v for k, v in level_op(10).items() if k != "once"}   # "always": true in save.json
    apply(studio, [op])
    play(cfg, LEVEL, 14)
    apply(studio, [op])
    assert doc(cfg).get(LEVEL) == 10
    assert saverecord.entry(saverecord.load(cfg) or {}, "acct", "my-mod", LEVEL) is None   # not in the record


def test_a_higher_mods_value_wins_and_neither_is_made_again(studio, cfg):
    ops = [level_op(10, "low"), level_op(20, "high")]
    out, _ = apply(studio, ops)
    assert doc(cfg).get(LEVEL) == 20
    # Only the winner's change was made: the lower mod's is recorded as not made, and isn't listed as done.
    assert [(a["source"], a["now"]) for a in out["applied"]] == [("high", 20)]
    low = saverecord.entry(saverecord.load(cfg), "acct", "low", LEVEL)
    assert low["lost_to"] == "high" and low["backup"] is None
    assert [c["source"] for c in studio.api("GET", ["save", "applied"], {}, None)["changes"]] == ["high"]
    with pytest.raises(ValueError, match="wasn't made: high's change there went in instead"):
        pipeline.undo_save_change(cfg, "low", LEVEL, studio.ctx.backups)
    play(cfg, LEVEL, 7)
    apply(studio, ops)
    assert doc(cfg).get(LEVEL) == 7, "the lower mod's value isn't made in the winner's place"


def test_two_mods_adding_one_item_record_the_first_as_not_made(studio, cfg):
    herb = f"{INV}/Gameplay.Inventory.Consumable.SmallCatnip"
    add = lambda n, source: {"op": "insert", "path": INV, "key": "Gameplay.Inventory.Consumable.SmallCatnip",
                             "value": n, "section": "save", "source": source, "once": True}
    out, _ = apply(studio, [add(3, "low"), add(5, "high")])
    assert doc(cfg).get(herb) == 5
    assert [(a["source"], a["was"], a["now"]) for a in out["applied"]] == [("high", None, 5)]
    record = saverecord.load(cfg)
    assert saverecord.entry(record, "acct", "low", herb)["lost_to"] == "high"
    assert saverecord.entry(record, "acct", "high", herb)["was"] is None, "what was there before either"


def test_insert_only_new_and_remove(studio, cfg):
    herb, moss, cobweb = (f"{INV}/Gameplay.Inventory.{t}" for t in ("Consumable.SmallCatnip", "Materials.Moss", "Materials.Cobweb"))
    ops = [{"op": "insert", "path": INV, "key": "Gameplay.Inventory.Consumable.SmallCatnip", "value": 5,
            "section": "save", "source": "my-mod", "once": True},
           {"op": "insert", "path": INV, "key": "Gameplay.Inventory.Materials.Moss", "value": 9,
            "section": "items", "source": "kit", "only_new": True},   # a starting item: the save has some, so kept
           {"op": "remove", "path": cobweb, "section": "save", "source": "my-mod", "once": True}]
    out, _ = apply(studio, ops)
    d = doc(cfg)
    assert d.get(herb) == 5 and d.get(moss) == 4 and not d.exists(cobweb)
    assert {a["path"]: (a["was"], a["now"]) for a in out["applied"]} == {herb: (None, 5), cobweb: (1, None)}
    play(cfg, herb, 1)   # used four in play
    out, _ = apply(studio, ops)
    assert doc(cfg).get(herb) == 1 and out["changed"] == []
    # A remove of something already gone does nothing, and isn't an error.
    out, _ = apply(studio, [{"op": "remove", "path": f"{INV}/Nope", "section": "save", "source": "x", "once": True}])
    assert out["changed"] == []


def test_names_and_look_ops_are_not_recorded(studio, cfg):
    apply(studio, [{"op": "set", "path": "1/GameplayProgression/Experience", "value": 200, "section": "cats", "source": "c"},
                   {"op": "insert", "path": INV, "key": "Gameplay.Inventory.Materials.Stick", "value": 1,
                    "section": "items", "source": "kit", "only_new": True}])
    assert saverecord.listing(saverecord.load(cfg)) == []


def test_the_first_install_after_upgrading_records_without_writing(studio, cfg):
    # The last install (by an older version) had my-mod on; it set Level 10 at every install, and the cat has
    # played on to 14 since. No record yet.
    make_mod(studio, "my-mod", files={"save.json": {"set": {LEVEL: 10}}})
    old = time.time() + 5   # built after the mod's files were written
    cfg.data["installed"] = {"mods": ["my-mod"], "built": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(old))}
    play(cfg, LEVEL, 14)
    out, _ = apply(studio, [level_op(10), level_op(3, "new-mod")])
    assert doc(cfg).get(LEVEL) == 3, "a mod that wasn't in the last install makes its change"
    record = saverecord.load(cfg)
    before = saverecord.entry(record, "acct", "my-mod", LEVEL)
    assert before["before"] is True and before["was"] is None and before["value"] == 10
    play(cfg, LEVEL, 14)
    apply(studio, [level_op(10)])
    assert doc(cfg).get(LEVEL) == 14


def test_a_save_made_after_a_03_install_leaves_its_changes_to_make(studio, cfg, monkeypatch):
    # wcmods 0.3 installed my-mod before there was any save (it said so only in its log), and the game made
    # the save later: the first install with a record makes the change, as nothing made it before.
    make_mod(studio, "my-mod", files={"save.json": {"set": {LEVEL: 10}}})
    built = time.time() + 5
    cfg.data["installed"] = {"mods": ["my-mod"], "built": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(built))}
    monkeypatch.setattr(pipeline, "_made_at", lambda path: built + 60)   # the save was made after that install
    out, _ = apply(studio, [level_op(10)])
    assert doc(cfg).get(LEVEL) == 10 and out["applied"][0]["was"] == 5
    assert "before" not in saverecord.entry(saverecord.load(cfg), "acct", "my-mod", LEVEL)


def test_a_save_backed_up_before_a_03_install_counts_as_there(studio, cfg, monkeypatch):
    # A backup of the save older than the last install: the save was there, so that install made the change.
    make_mod(studio, "my-mod", files={"save.json": {"set": {LEVEL: 10}}})
    from wcmods.formats import save as savefile
    old, _ = savefile.backup(cfg.save_dir, studio.ctx.backups, "manual")   # as 0.3 made them: no record in it
    built = time.time() + 5
    cfg.data["installed"] = {"mods": ["my-mod"], "built": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(built))}
    monkeypatch.setattr(pipeline, "_made_at", lambda path: built + 60)   # however new the file looks
    play(cfg, LEVEL, 14)
    apply(studio, [level_op(10)])
    assert doc(cfg).get(LEVEL) == 14
    assert saverecord.entry(saverecord.load(cfg), "acct", "my-mod", LEVEL)["before"] is True
    assert os.path.basename(old) in backups(studio)


def test_a_backup_keeps_the_record_and_a_restore_leaves_it_out_of_the_saves(studio, cfg):
    from wcmods.formats.save import RECORD_NAME
    out, _ = apply(studio, [level_op(10)])
    where, files = saverecord.backup(cfg, studio.ctx.backups, "manual")
    assert RECORD_NAME not in files and os.path.isfile(os.path.join(where, RECORD_NAME))
    assert saverecord.kept(where) == saverecord.load(cfg)
    # The first backup was made while there was no record yet: it keeps that (null).
    assert saverecord.kept(os.path.join(studio.ctx.backups, out["backup"])) is None
    saverecord.restore(cfg, studio.ctx.backups, os.path.basename(where))
    assert RECORD_NAME not in os.listdir(cfg.save_dir)


def test_restoring_a_backup_puts_its_record_back(studio, cfg):
    out, _ = apply(studio, [level_op(10)])
    assert saverecord.load(cfg)["acct"]["my-mod"]
    studio.api("POST", ["restore"], {"name": out["backup"]}, None)
    assert doc(cfg).get(LEVEL) == 5 and saverecord.load(cfg) == {}
    apply(studio, [level_op(10)])   # the next Apply makes the mod's change again
    assert doc(cfg).get(LEVEL) == 10


def test_undoing_a_restore_with_the_before_restore_backup_keeps_the_save_as_played(studio, cfg):
    first, _ = apply(studio, [level_op(10)])
    play(cfg, LEVEL, 14)
    studio.api("POST", ["restore"], {"name": first["backup"]}, None)   # the level 5 save, from before the mod
    assert doc(cfg).get(LEVEL) == 5
    undo = [b for b in backups(studio) if "-before-restore" in b][-1]
    studio.api("POST", ["restore"], {"name": undo}, None)   # changed my mind: the level 14 save again
    assert doc(cfg).get(LEVEL) == 14
    out, lines = apply(studio, [level_op(10)])
    assert doc(cfg).get(LEVEL) == 14 and out["changed"] == [], lines


def test_restoring_a_backup_from_before_the_record_keeps_the_changes_made_before_it(studio, cfg):
    from wcmods.formats import save as savefile
    make_mod(studio, "my-mod", files={"save.json": {"set": {LEVEL: 10}}})
    play(cfg, LEVEL, 10)   # 0.3 made the mod's level at every install
    old, _ = savefile.backup(cfg.save_dir, studio.ctx.backups, "manual")   # a backup 0.3 made: no record in it
    built = time.time() + 5
    cfg.data["installed"] = {"mods": ["my-mod"], "built": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(built))}
    apply(studio, [level_op(10), level_op(3, "new-mod")])   # the first install with a record
    assert saverecord.entry(saverecord.load(cfg), "acct", "my-mod", LEVEL)["before"] is True
    studio.api("POST", ["restore"], {"name": os.path.basename(old)}, None)
    record = saverecord.load(cfg)
    assert saverecord.entry(record, "acct", "my-mod", LEVEL)["before"] is True, "made before that backup too"
    assert saverecord.entry(record, "acct", "new-mod", LEVEL) is None, "made after it: made again"
    play(cfg, LEVEL, 12)
    apply(studio, [level_op(10)])
    assert doc(cfg).get(LEVEL) == 12, "the old mod's change isn't made once more"


def test_restoring_the_backup_a_put_back_made_brings_the_change_back_as_made(studio, cfg):
    apply(studio, [level_op(10)])
    play(cfg, LEVEL, 12)
    r = pipeline.undo_save_change(cfg, "my-mod", LEVEL, studio.ctx.backups)
    assert doc(cfg).get(LEVEL) == 5
    studio.api("POST", ["restore"], {"name": r["backup"]}, None)   # the save from just before the put back
    assert doc(cfg).get(LEVEL) == 12
    e = saverecord.entry(saverecord.load(cfg), "acct", "my-mod", LEVEL)
    assert "undone" not in e and e["value"] == 10
    assert pipeline.undo_save_change(cfg, "my-mod", LEVEL, studio.ctx.backups)["now"] == 5   # it can go again


def test_a_backup_with_no_record_forgets_what_came_after_it_and_undoes_later_put_backs(studio, cfg):
    write_save(cfg.save_dir, SAVE)
    folder = os.path.join(studio.ctx.backups, "20261028-110000-manual")
    os.makedirs(folder)
    with open(os.path.join(cfg.save_dir, SAV_NAME), "rb") as f, open(os.path.join(folder, SAV_NAME), "wb") as g:
        g.write(f.read())
    k = lambda n: f"1/GameplayProgression/K{n}"
    saverecord.store(cfg, {"acct": {"m": {
        k(1): {"op": "set", "value": 1, "when": "2026-10-28T10:00:00"},
        k(2): {"op": "set", "value": 2, "when": "2026-10-28T12:00:00"},
        k(3): {"op": "set", "value": 3, "before": True, "when": "2026-10-28T13:00:00"},
        k(4): {"op": "set", "value": 4, "when": "2026-10-28T10:00:00", "undone": "2026-10-28T12:00:00",
               "undone_backup": "x"}}},
        "other": {"m": {k(2): {"op": "set", "value": 2, "when": "2026-10-28T12:00:00"}}}})
    saverecord.put_back(cfg, folder)
    record = saverecord.load(cfg)
    assert sorted(record["acct"]["m"]) == [k(1), k(3), k(4)]
    assert "undone" not in record["acct"]["m"][k(4)] and "undone_backup" not in record["acct"]["m"][k(4)]
    assert k(2) in record["other"]["m"], "another account's save wasn't put back"


def test_an_undone_record_is_not_made_again(studio, cfg):
    apply(studio, [level_op(10)])
    play(cfg, LEVEL, 12)
    lines = []
    r = pipeline.undo_save_change(cfg, "my-mod", LEVEL, studio.ctx.backups, lines.append)
    assert r["before"] == 12 and r["now"] == 5 and doc(cfg).get(LEVEL) == 5
    assert r["backup"].endswith("-before-put-back") and "  save: your cat's level: 12 -> 5 (put back)" in lines
    assert saverecord.entry(saverecord.load(cfg), "acct", "my-mod", LEVEL)["undone"]
    apply(studio, [level_op(10)])
    assert doc(cfg).get(LEVEL) == 5
    with pytest.raises(ValueError, match="put back already"):
        pipeline.undo_save_change(cfg, "my-mod", LEVEL, studio.ctx.backups)
    with pytest.raises(LookupError):
        pipeline.undo_save_change(cfg, "other", LEVEL, studio.ctx.backups)


def install(studio, ops, mods=("my-mod",)):
    build = os.path.join(str(studio.ctx.root), "build")
    os.makedirs(build, exist_ok=True)
    manifest = {"mods": list(mods), "built": "2026-10-28T15:30:00", "sections": {}, "outputs": [], "ue4ss_mods": [],
                "ue4ss_shared": [], "notes": {}, "save_ops": ops, "warnings": []}
    with open(os.path.join(build, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    return pipeline.install(studio.ctx.cfg, build, studio.ctx.backups, log=lambda m: None)


def test_no_save_marks_save_pending_and_pending_says_so(studio, fake_game):
    cfg = studio.ctx.cfg
    install(studio, [level_op(10)])
    assert cfg.data["installed"]["save_pending"] is True
    assert pipeline.pending(cfg, studio.mods())["redo"] == []   # still no save: nothing to do yet
    write_save(cfg.save_dir, SAVE)
    p = pipeline.pending(cfg, studio.mods())
    assert "save edits are waiting for a save" in p["redo"] and p["any"]
    install(studio, [level_op(10)])
    assert "save_pending" not in cfg.data["installed"] and doc(cfg).get(LEVEL) == 10


def test_a_failing_apply_still_records_the_install(studio, fake_game, monkeypatch):
    cfg = studio.ctx.cfg
    write_save(cfg.save_dir, SAVE)

    def boom(*a, **k):
        raise RuntimeError("save re-encode check failed; nothing written")
    monkeypatch.setattr(pipeline, "apply_save_ops", boom)
    manifest = install(studio, [level_op(10)])
    assert cfg.data["installed"]["mods"] == ["my-mod"]
    assert any("your save edits couldn't be made" in w and "your save is as it was" in w for w in manifest["warnings"])
