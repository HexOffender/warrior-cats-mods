"""Mod packs: a set of mods shared and played together as one experience (a story with its cats, quests,
items, colours and names, say).

A pack is a mod of its own with nothing in it but its mod.json:
    {"name": "The Moonlit Path", "pack": true, "requires": ["moonlit-cats", "moonlit-palette"], ...}
so turning it on turns its mods on ("requires", as for any mod). Its .zip (modzip.pack) carries every mod in
it, so whoever adds it gets them all. Playing a pack on its own turns every other mod off and remembers
which were on (wcmods.json "pack_before": the pack, its name, and the mods on before it), for going back
to them, even once the pack is removed. The player's own tools stay on (kept): the mods that go with Clan
Mod Studio that are tools (addons.py: Menu pages, Creator palettes, the Emote wheel) and any mod whose
mod.json says "tool": true; so do the mods a pack's mods work with ("uses") that were on.
"""
from . import addons
from . import mods as modlib

# Left on when a pack is played on its own: the mods that go with Clan Mod Studio that are the player's own
# tools, not a pack's choice. A mod of anyone's says the same with "tool": true in its mod.json (kept()).
KEPT = tuple(a.id for a in addons.ADDONS if a.tool)


def is_pack(mod):
    return bool(mod.meta.get("pack"))


def is_tool(mod):
    """Whether a mod is the player's own tool, which stays on whatever pack is played."""
    return mod.id in KEPT or mod.meta.get("tool") is True


def contents(found, pack):
    """The mods a pack carries: what it requires, and what they require in turn (ids, missing ones too)."""
    return modlib.needed(found, pack.id)


def problems(cfg, found, pack):
    """What keeps a pack's mods out of the game, one sentence each: a mod that runs code while mods that run
    code aren't allowed, one made for an older version of the game (and not used anyway), one that needs a
    newer Clan Mod Studio."""
    from .exe import gamebuild
    by_id = {m.id: m for m in found}
    build = gamebuild.steam_build(cfg)
    out = []
    for i in contents(found, pack):
        m = by_id.get(i)
        if m is None or m.problem:
            continue
        if m.has_code() and not cfg.data.get("allow_code_mods"):
            out.append(f"{m.name} runs code, so it stays out until you allow mods that run code")
        if build is not None and build not in gamebuild.made_for(m) and not gamebuild.allowed(cfg, m.id, build):
            out.append(f"{m.name} was made for an older version of the game, so it's left out until it's updated")
        newer = modlib.needs_newer(m.wcmods_min)
        if newer:
            out.append(f"{m.name} {newer}")
    return out


def describe(cfg, found):
    """The packs in the mods folder, for the studio: their details, their mods, what keeps any of them out of
    the game, and which is being played. A pack played on its own and then removed is still "playing" (by
    its id, with "playing_name" and "playing_removed"), so Back to my mods stays on offer."""
    by_id = {m.id: m for m in found}
    before = cfg.data.get("pack_before") if isinstance(cfg.data.get("pack_before"), dict) else {}
    playing = before.get("pack")
    out = []
    for p in found:
        if not is_pack(p):
            continue
        inside = contents(found, p)
        out.append({"id": p.id, "name": p.name, "description": p.description, "author": p.author, "version": p.version,
                    "enabled": p.enabled, "playing": p.id == playing, "problems": problems(cfg, found, p),
                    "mods": [{"id": i, "name": by_id[i].name if i in by_id else addons.find(i).name if addons.find(i) else i,
                              "present": i in by_id, "enabled": i in by_id and by_id[i].enabled,
                              "kinds": by_id[i].kinds() if i in by_id else [], "direct": i in p.requires,
                              "tool": i in by_id and is_tool(by_id[i])} for i in inside]})
    removed = bool(playing) and playing not in by_id
    return {"packs": out, "playing": playing or None, "playing_removed": removed,
            "playing_name": (by_id[playing].name if playing in by_id else before.get("name") or playing) if playing else None}


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
    """Play a pack on its own: its mods on, every other mod off but the player's tools (is_tool) and the mods
    its mods work with ("uses") that were on. What was on before is kept in wcmods.json, once, so going back
    after trying several packs returns to your own mods. Returns {"on": [...], "off": [...]}."""
    by_id = {m.id: m for m in found}
    if pack_id not in by_id or not is_pack(by_id[pack_id]):
        raise LookupError(f"no mod pack named {pack_id}")
    inside = contents(found, by_id[pack_id])
    missing = [i for i in inside if i not in by_id]
    if missing:
        raise ValueError(f"{by_id[pack_id].name} needs {', '.join(modlib.missing_name(i) for i in missing)}, which "
                         "isn't in your mods; add the pack's .zip again")
    cfg.reload()
    before = cfg.data.get("pack_before")
    if not isinstance(before, dict) or not isinstance(before.get("on"), list):
        before = {"on": [m.id for m in found if m.enabled]}
    before["pack"] = pack_id
    before["name"] = by_id[pack_id].name
    cfg.data["pack_before"] = before
    cfg.save()
    used = {u for i in inside for u in by_id[i].uses}
    keep = {m.id for m in found if m.enabled and (is_tool(m) or m.id in used)}
    return _set(found, {pack_id, *inside} | keep)


def stop(cfg, found):
    """Back to your own mods after playing a pack: the ones on before it, and only those. It works whether or
    not the pack is still in your mods."""
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
