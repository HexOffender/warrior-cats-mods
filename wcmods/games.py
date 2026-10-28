"""The games in a save: one for each cat started, as the account data's numbered keys ("0" to "8"), each with its
own cat of yours, its clans and its progress. One list for every page that changes a save (the Save page's and
Your cat's game pickers, GET /save's and GET /cat's "games") and the words for a game (names.game_words: slot "4"
is "your 5th game").

The game numbers them as its cat choice does: its first button, mcGuiButtonCat1, is slot 0, so a game's number is
its slot + 1 (docs/reverse-engineering.md, the cat choice). Shared/General/CurrentCatSlot is the game played last:
the one the game opens on, and the one "player" means at Apply (names.current_slot).

Sandbox mode (the companion mod, wcmods-sandbox) keeps its own list of the games it made, sandbox.json in the
scripts' folder beside the saves (pipeline.saved_folder: %LOCALAPPDATA%\\Wrc\\Saved\\WCMods): {"cats": [{"slot": 4,
"clan": "ThunderClan", "prefix": "STR_CAT_NAME6", "made": ...}]}. It's only read here, never written: the file is
the mod's. A game counts as a sandbox game while the cat in it is still the one the mod made there (the same clan
and the same first part of its name, as the mod itself checks), so a slot started again in story mode isn't."""
import json
import os
import re

from . import names

SANDBOX_FILE = "sandbox.json"
_CLAN = re.compile(r"(?<![A-Za-z0-9_])ClanType=(\w+)")
_PREFIX = re.compile(r'(?<![A-Za-z0-9_])PrefixNameId="([^"]*)"')


def sandbox_entries(folder):
    """The Sandbox mode mod's list of its games, from sandbox.json in `folder` (pipeline.saved_folder): its
    entries that are objects. [] when the file isn't there, can't be read or isn't laid out that way."""
    if not folder:
        return []
    try:
        with open(os.path.join(folder, SANDBOX_FILE), encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    cats = data.get("cats") if isinstance(data, dict) else None
    return [e for e in cats if isinstance(e, dict)] if isinstance(cats, list) else []


def _slot_number(value):
    """A sandbox entry's slot as the save's key ("4"), or None for one that isn't a whole number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return str(value)
    if isinstance(value, str) and value.isdigit():
        return value
    return None


def is_sandbox(slot, clan, prefix, entries):
    """Whether sandbox.json's entries say Sandbox mode made the cat in `slot`: the first entry for that slot, while
    its clan and prefix (when it says them) are the cat's now, as the mod's own registry.lua checks."""
    for e in entries:
        if _slot_number(e.get("slot")) != str(slot):
            continue
        return e.get("clan") in (None, clan) and e.get("prefix") in (None, prefix)
    return False


def _at(data, path):
    node = data
    for part in path.split("/"):
        if isinstance(node, dict):
            node = node.get(part)
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
    return node


def in_save(data, shown=None, sandbox=()):
    """Every game in a save's account data that has a cat of yours, in the game's order (slot 0 first):
    [{"slot": "4", "n": 5, "name": "Sharppaw" or None, "clan": "ThunderClan" or None, "rank": "Apprentice" or None,
    "level": 1 or None, "sandbox": bool, "current": bool}]. n is the game's number as its cat choice shows it
    (slot + 1); name the cat's name through shown(cat) (the studio's cat namer: as it shows with the names mods
    that are on), None without one; clan and rank from the cat's record, level from the game's progress; sandbox
    from sandbox.json's entries (sandbox_entries); current for the game played last. A slot without a cat of
    yours (a game never started, or one the game emptied) isn't a game here."""
    current = names.current_slot(data)
    out = {}
    for cat in names.cats_in_save(data):
        slot = cat["slot"]
        if not cat["player"] or not slot.isdigit() or slot in out:
            continue
        text = _at(data, cat["paths"][0])
        text = text if isinstance(text, str) else ""
        clan, prefix = _CLAN.search(text), _PREFIX.search(text)
        clan = clan.group(1) if clan else None
        level = _at(data, f"{slot}/GameplayProgression/Level")
        name = shown(cat) if shown else ""
        out[slot] = {"slot": slot, "n": int(slot) + 1, "name": name or None, "clan": clan,
                     "rank": cat["ids"].get("Role") or None,
                     "level": level if isinstance(level, (int, float)) and not isinstance(level, bool) else None,
                     "sandbox": is_sandbox(slot, clan, prefix.group(1) if prefix else None, sandbox),
                     "current": slot == current}
    return [out[s] for s in sorted(out, key=int)]


def words(slot):
    """A game in a sentence, as every page says it: slot "4" is "your 5th game" (names.game_words)."""
    return names.game_words(slot)
