"""Mod packs: a set of mods shared and played together as one experience (a story with its cats, quests,
items, colours and names, say).

A pack is a mod of its own with nothing in it but its mod.json:
    {"name": "The Moonlit Path", "pack": true, "requires": ["moonlit-cats", "moonlit-palette"], ...}
so turning it on turns its mods on ("requires", as for any mod). Its .zip (modzip.pack) carries every mod in
it, so whoever adds it gets them all. Playing a pack on its own turns every other mod off and remembers
which were on (wcmods.json "pack_before"), for going back to them.
"""
from . import menupages
from . import mods as modlib

KEPT = (menupages.ID,)   # left on when a pack is played on its own: the in-game menu's pages aren't a pack's choice


def is_pack(mod):
    return bool(mod.meta.get("pack"))


def contents(found, pack):
    """The mods a pack carries: what it requires, and what they require in turn (ids, missing ones too), and
    the mods they use that are in the mods folder (mods.carried)."""
    return modlib.carried(found, pack.id)


def describe(cfg, found):
    """The packs in the mods folder, for the studio: their details, their mods, and which is being played."""
    by_id = {m.id: m for m in found}
    playing = (cfg.data.get("pack_before") or {}).get("pack")
    out = []
    for p in found:
        if not is_pack(p):
            continue
        inside = contents(found, p)
        out.append({"id": p.id, "name": p.name, "description": p.description, "author": p.author, "version": p.version,
                    "enabled": p.enabled, "playing": p.id == playing,
                    "mods": [{"id": i, "name": by_id[i].name if i in by_id else i, "present": i in by_id,
                              "enabled": i in by_id and by_id[i].enabled, "kinds": by_id[i].kinds() if i in by_id else [],
                              "direct": i in p.requires} for i in inside]})
    return {"packs": out, "playing": playing if playing in by_id else None}


def save(mods_root, found, pack_id, name, ids, description="", author="", version="", game_build=None):
    """Make a pack (or change one): its details and the mods in it. Returns the pack."""
    by_id = {m.id: m for m in found}
    ids = list(dict.fromkeys(i for i in ids if isinstance(i, str)))
    if not ids:
        raise ValueError("choose at least one mod for the pack")
    for i in ids:
        if i not in by_id:
            raise ValueError(f"there's no mod {i} in your mods folder")
        if is_pack(by_id[i]):
            raise ValueError(f"{by_id[i].name} is a mod pack itself; choose its mods instead")
    if pack_id in by_id:
        p = by_id[pack_id]
        if not is_pack(p):
            raise ValueError(f"{p.name} is a mod, not a mod pack")
    else:
        p = modlib.create(mods_root, pack_id, name, description, enabled=False, game_build=game_build)
    p.update(name=name or p.name, description=description, author=author, version=version, pack=True, requires=ids)
    return p


def play(cfg, found, pack_id):
    """Play a pack on its own: its mods on, every other mod off (but KEPT). What was on before is kept in
    wcmods.json, once, so going back after trying several packs returns to your own mods.
    Returns {"on": [...], "off": [...]}."""
    by_id = {m.id: m for m in found}
    if pack_id not in by_id or not is_pack(by_id[pack_id]):
        raise LookupError(f"no mod pack named {pack_id}")
    missing = [i for i in contents(found, by_id[pack_id]) if i not in by_id]
    if missing:
        raise ValueError(f"{by_id[pack_id].name} needs {', '.join(missing)}, which isn't in your mods; add the pack's .zip again")
    cfg.reload()
    before = cfg.data.get("pack_before")
    if not isinstance(before, dict) or not isinstance(before.get("on"), list):
        before = {"on": [m.id for m in found if m.enabled]}
    before["pack"] = pack_id
    cfg.data["pack_before"] = before
    cfg.save()
    want = {pack_id, *contents(found, by_id[pack_id])} | {i for i in KEPT if i in by_id and by_id[i].enabled}
    return _set(found, want)


def stop(cfg, found):
    """Back to your own mods after playing a pack: the ones on before it, and only those."""
    cfg.reload()
    before = cfg.data.pop("pack_before", None)
    cfg.save()
    if not isinstance(before, dict) or not isinstance(before.get("on"), list):
        return {"on": [], "off": []}
    return _set(found, set(before["on"]))


def _set(found, want):
    on, off = [], []
    for m in found:
        now = m.id in want
        if m.enabled != now:
            m.set_enabled(now)
            (on if now else off).append(m.id)
    return {"on": on, "off": off}
