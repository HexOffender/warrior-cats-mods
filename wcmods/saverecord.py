"""What save edits have been made to your save, so each is made once: save-changes.json in your files'
folder, beside wcmods.json. It's about your save, not a setting, so it isn't in wcmods.json.

    { "<account>": { "<source>": {
        "1/GameplayProgression/Level": { "op": "set", "value": 20, "was": 5, "label": "Fawnstar's level",
                                         "when": "2026-10-28T15:30:12", "backup": "20261028-153012-before-save-edits" } } } }

<account> is the one key at the top of the save's JSON (SaveDoc.account): one per player account, so another
account's save starts clean. <source> is a mod's id, or "studio" for the Save page's Change my save now.
The key is the path the change is at (an inventory item's path for an add). "was" is what Put it back
writes; "undone" (when it was put back) keeps the record, so a mod that is still on doesn't make the change
again; "before" marks a change made before this version, whose "was" isn't known.

pipeline.apply_save_ops reads and writes it; restoring a backup forgets what was made after it
(forget_since), because the restored save hasn't got those changes.
"""
import datetime
import json
import os
import re

FILE = "save-changes.json"
STUDIO = "studio"   # the source of the Save page's own changes


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


def forget_since(cfg, backup_name):
    """Drop every change made at or after the backup's time: a save put back from that backup hasn't got
    them, so the next Apply makes the mods' ones again. Returns how many were dropped."""
    record = load(cfg)
    since = _stamp(backup_name)
    if not record or not since:
        return 0
    dropped = 0
    for account in list(record):
        for source in list(record[account]):
            changes = record[account][source]
            for key in list(changes):
                if _stamp(changes[key].get("when")) >= since:
                    del changes[key]
                    dropped += 1
            if not changes:
                del record[account][source]
        if not record[account]:
            del record[account]
    if dropped:
        store(cfg, record)
    return dropped


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
