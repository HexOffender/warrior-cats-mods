"""What save edits have been made to your save, so each is made once: save-changes.json in your files'
folder, beside wcmods.json. It's about your save, not a setting, so it isn't in wcmods.json.

    { "<account>": { "<source>": {
        "1/GameplayProgression/Level": { "op": "set", "value": 20, "was": 5, "label": "Fawnstar's level",
                                         "when": "2026-10-28T15:30:12", "backup": "20261028-153012-before-save-edits" } } } }

<account> is the one key at the top of the save's JSON (SaveDoc.account): one per player account, so another
account's save starts clean. <source> is a mod's id, or "studio" for the Save page's Change my save now.
The key is the path the change is at (an inventory item's path for an add). "was" is what Put it back
writes; "undone" (when it was put back) keeps the record, so a mod that is still on doesn't make the change
again; "before" marks a change made before this version, whose "was" isn't known; "lost_to" marks a mod's
change another mod's change to the same path won over (not made, and not made later either).

pipeline.apply_save_ops reads and writes it. Every save backup keeps the record as it was then, beside the save
files (backup(), save.RECORD_NAME), and restoring a backup puts that record back with the save (restore()), so
the record always says what the save in the folder has had made: the next Apply makes again only what that
save hasn't got.
"""
import datetime
import json
import os
import re

from .formats import save as savefile

FILE = "save-changes.json"
STUDIO = "studio"   # the source of the Save page's own changes
_NONE = object()    # a backup that keeps no record (made by wcmods 0.3 or before)


def path(cfg):
    return os.path.join(cfg.data_dir, FILE)


def load(cfg):
    """The record, or None when there's none yet (the first install since save edits were made once)."""
    p = path(cfg)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):   # damaged: as if there were none, which records without writing
        return None
    return data if isinstance(data, dict) else None


def store(cfg, record):
    os.makedirs(cfg.data_dir, exist_ok=True)
    tmp = path(cfg) + ".wcmods-tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path(cfg))


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def entry(record, account, source, key):
    return ((record.get(account) or {}).get(source) or {}).get(key)


def note(record, account, source, key, **fields):
    """Record a change (replacing what was there for that source and key)."""
    record.setdefault(account, {}).setdefault(source, {})[key] = fields
    return fields


def _stamp(text):
    """"20261028-153012" from a backup's name or an ISO time, for comparing which came first."""
    m = re.match(r"^(\d{8})-(\d{6})", text or "")
    if m:
        return m.group(1) + "-" + m.group(2)
    m = re.match(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)", text or "")
    return "".join(m.groups()[:3]) + "-" + "".join(m.groups()[3:]) if m else ""


def backup(cfg, backups_root, reason="manual"):
    """A backup of the saves folder (formats.save.backup) with the record as it is now kept in it
    (save.RECORD_NAME: null while there's no record yet), for restore() to put back with the save. Returns
    (the backup's folder, the save files copied)."""
    where, copied = savefile.backup(cfg.save_dir, backups_root, reason)
    with open(os.path.join(where, savefile.RECORD_NAME), "w", encoding="utf-8", newline="\n") as f:
        json.dump(load(cfg), f, indent=1, ensure_ascii=False)
        f.write("\n")
    return where, copied


def kept(folder):
    """The record a backup keeps: a dict, None (there was no record yet when it was made), or _NONE when the
    backup keeps none (wcmods 0.3 or before made it) or it can't be read."""
    p = os.path.join(folder, savefile.RECORD_NAME)
    if not os.path.isfile(p):
        return _NONE
    try:
        with open(p, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return _NONE
    return data if data is None or isinstance(data, dict) else _NONE


def _account_of(save_dir):
    """The account of the save in a folder, or None when there's none or it can't be read."""
    from .formats.savejson import SaveDoc
    try:
        return SaveDoc(savefile.SaveGame.load(os.path.join(save_dir, savefile.SAV_NAME)).json_text).account
    except Exception:   # noqa: BLE001 - no save, or one that can't be read: every account's record is put back
        return None


def restore(cfg, backups_root, name):
    """Put a backed-up save back, after a backup of the save as it is now ("before-restore", which keeps the
    record as it is now, so restoring that undoes this; none while there's no save, as savefile.backup never
    makes an empty one), and the record with it (put_back). Only a backup list_backups() lists (LookupError
    before anything is made). Returns (the files put back, the before-restore backup's name or None)."""
    if name not in savefile.list_backups(backups_root):
        raise LookupError(f"there's no backup called {name}")
    before = None
    if savefile.has_save(cfg.save_dir):
        before = os.path.basename(backup(cfg, backups_root, "before-restore")[0])
    restored = savefile.restore(backups_root, name, cfg.save_dir)
    put_back(cfg, os.path.join(backups_root, name))
    return restored, before


def put_back(cfg, folder):
    """The record after the save in `folder` (a backup) has been put back: for the save's account, the record
    that backup keeps, so the next Apply makes again exactly what that save hasn't got. A backup that keeps
    none (made by wcmods 0.3 or before, or before the first install with a record) is older than every change
    recorded since: those are forgotten, a change put back since counts as made again (the backup's save has
    it), and the changes made before wcmods kept a record ("before") stay, since that save had them too."""
    record, snap = load(cfg), kept(folder)
    account = _account_of(cfg.save_dir)
    if isinstance(snap, dict):
        record = record or {}
        for acc in ([account] if account else sorted(set(record) | set(snap))):
            if acc in snap:
                record[acc] = snap[acc]
            else:
                record.pop(acc, None)
        store(cfg, record)
        return
    if not record:
        return
    since = _stamp(os.path.basename(folder))
    for acc in ([account] if account else list(record)):
        sources = record.get(acc) or {}
        for source in list(sources):
            changes = sources[source]
            for key in list(changes):
                e = changes[key]
                if e.get("before"):
                    continue
                if not since or _stamp(e.get("when")) >= since:
                    del changes[key]
                elif e.get("undone") and _stamp(e["undone"]) >= since:
                    e.pop("undone", None)
                    e.pop("undone_backup", None)
            if not changes:
                del sources[source]
        if acc in record and not record[acc]:
            del record[acc]
    store(cfg, record)


def listing(record, account=None):
    """Every change, newest first, as [{"account", "source", "key", ...the record's fields}]."""
    out = []
    for acc, sources in (record or {}).items():
        if account is not None and acc != account:
            continue
        for source, changes in sources.items():
            for key, fields in changes.items():
                out.append({"account": acc, "source": source, "key": key, **fields})
    out.sort(key=lambda e: e.get("when") or "", reverse=True)
    return out
