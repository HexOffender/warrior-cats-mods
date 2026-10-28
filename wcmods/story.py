"""Cats and questlines of a mod's own, as data (npcs.json and quests.json), made on Clan Mod Studio's
Characters and Questlines pages with no code. wcmods checks them and puts every mod's together in the
game (sections/story.py); the Sandbox mode mod (github.com/HexOffender/wcmods-sandbox) brings the cats
into the forest with a sandbox cat and runs the questlines.

npcs.json, the mod's cats:

    {
      "npcs": [
        {
          "id": "mossfoot", "name": "Mossfoot", "title": "Elder",
          "colours": { "fur": "#7a6a58", "pattern": "#4a3f33", "markings": "#d8cfc0" },
          "eyes": 6, "size": 0.8,
          "look": { "body": 6, "fur": 2, "tail": 7, "ears": 3, "eyes": 1, "whiskers": 4, "face": 5,
                    "pattern": 12, "marking": 3 },
          "slots": { "fur": 9, "pattern": 4, "marking": 0 },
          "lines": ["The forest is yours, young one."]
        }
      ]
    }

  Without "look" and "slots" the game makes up the cat's look each time it appears, as it does for its own
  filler cats: its shape, pattern and colour slots ("colours" go on top). "look" fixes its shape, as
  cats.json's does (catcolours.LOOK: body to face each one of the game's 10, pattern and marking one of
  its 21), and "slots" its coat, pattern and marking colour slots, so it looks the same every time; a part
  left out (and the eye colour, without "eyes") is made up again each time it appears.

  A cat with no "at" turns up beside your sandbox cat the first time it comes into the forest, and stays
  there for that cat; "at": [x, y, z] (with "yaw" and "level") puts it in one place for every cat. "at":
  null is the Characters page's "At one spot" with no spot filled in yet: the same as no "at" until it is.
  "lines" is what it says when it has nothing to do with a quest.

quests.json, the mod's questlines:

    {
      "quests": [
        {
          "id": "dandelions", "title": "Dandelions for Mossfoot", "giver": "mossfoot", "after": [],
          "steps": [
            { "do": "talk", "npc": "mossfoot", "lines": ["Bring me three dandelions?"] },
            { "do": "collect", "item": "Gameplay.Inventory.Materials.Dandelion", "count": 3 },
            { "do": "visit", "at": [-60040, -200, 813], "radius": 400, "objective": "Go to the old oak" },
            { "do": "visit", "place": "medicine-cat" },
            { "do": "talk", "lines": ["Thank you!"] }
          ],
          "reward": { "Gameplay.Inventory.Consumable.SmallHealingHerb": 2 }
        }
      ]
    }

  A questline starts by itself once the quests in its "after" are done (at once with none), and its steps
  go in order: "talk" (to "npc", the giver if left out: the step is done after its last line), "collect"
  (pick up "count" of "item" from the step's start) and "visit" (go within "radius" cm of "at", or of the
  nearest of a "place": the medicine cat). "objective" is what the game's objective panel says; left out,
  the build fills it in from the step at Apply (objective()), with the cat's and the item's names as they
  are then. "description" is a sentence about the quest, shown under its title on the mod menu's
  Questlines page. "reward" is dropped at your cat's paws when the last step is done.

Ids are a mod's own: a quest names the mod's own cats and quests. Keys starting with "_" are notes.

A mod with cats or questlines says "uses": ["sandbox"] in its mod.json (the studio writes it): Sandbox mode
comes on with it when it's in the mods folder, and a mod without it still goes in (its items, palettes and
names with it), waiting for Sandbox mode to show its cats. sandbox() says what the installed one can show.
"""
import json
import os
import re

from .catcolours import LOOK, LOOK_MAX
from .mods import version_key
from .palettes import GAME_SLOTS

FILES = ("npcs.json", "quests.json")
FORMAT = 1
SANDBOX_ID = "sandbox"   # the mod that runs them: its folder name, what a mod gives in "uses"
SANDBOX_NAME = "Sandbox mode"   # its name, for a studio that hasn't got it yet
SANDBOX_RELEASES = "https://github.com/HexOffender/wcmods-sandbox/releases"
# What a cat or a questline can say that a Sandbox mode older than this ignores: {field: version}.
SANDBOX_NEEDS = {"look": "0.5", "slots": "0.5"}
PROGRESS_FILE = "sandbox-story.json"   # Sandbox mode's record of each sandbox cat's quests, in Game.save.folder()
SHARED_VARIABLE = "WCMods.story"   # what the game gets: every mod's cats and questlines, as JSON text

ID = re.compile(r"[a-z0-9][a-z0-9-]{0,47}$")
HEX = re.compile(r"#[0-9A-Fa-f]{6}$")
COLOURS = ("fur", "pattern", "markings", "nose", "paws", "whiskers", "ears")
# Places a "visit" step can name: the actor class of each (the nearest one counts), and its words.
PLACES = {"medicine-cat": "BP_Quest_Giver_Bartering_C"}
PLACE_WORDS = {"medicine-cat": "the nearest medicine cat"}
STEPS = ("talk", "collect", "visit")
ITEM_ROOT = "Gameplay.Inventory."
MAX_LINE, MAX_LINES, MAX_STEPS, MAX_COUNT = 400, 30, 40, 99

# A fixed look's colour slots: the coat's (the game's 25, which also pick its nose, paws, ears and whiskers) and
# the pattern's and markings' (any slot: new ones a palette adds too).
SLOTS = ("fur", "pattern", "marking")
NPC_KEYS = {"id", "name", "title", "colours", "eyes", "size", "look", "slots", "at", "yaw", "level", "lines"}
QUEST_KEYS = {"id", "title", "description", "giver", "after", "steps", "reward"}
STEP_KEYS = {"do", "objective", "npc", "lines", "item", "count", "at", "level", "place", "radius"}


def _unknown(obj, allowed, where):
    extra = sorted(k for k in obj if k not in allowed and not str(k).startswith("_"))
    if extra:
        raise ValueError(f"{where}: unknown key(s) {', '.join(extra)}")


def _text(obj, key, where, required=True, limit=80):
    v = obj.get(key)
    if v is None and not required:
        return None
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{where}: \"{key}\" should be text" + ("" if required else " (or left out)"))
    if len(v) > limit:
        raise ValueError(f"{where}: \"{key}\" is longer than {limit} letters")
    return v.strip()


def _number(obj, key, where, lo, hi, whole=False):
    v = obj.get(key)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int if whole else (int, float)) or not lo <= v <= hi:
        raise ValueError(f"{where}: \"{key}\" should be a {'whole ' if whole else ''}number from {lo} to {hi}")
    return v


def _lines(obj, key, where, required=False):
    v = obj.get(key)
    if v is None and not required:
        return []
    if not isinstance(v, list) or not all(isinstance(s, str) and s.strip() for s in v) or (required and not v):
        raise ValueError(f"{where}: \"{key}\" should be a list of lines to say" + (", at least one" if required else ""))
    if len(v) > MAX_LINES:
        raise ValueError(f"{where}: \"{key}\" has more than {MAX_LINES} lines")
    for s in v:
        if len(s) > MAX_LINE:
            raise ValueError(f"{where}: a line in \"{key}\" is longer than {MAX_LINE} letters: {s[:40]}...")
    return [s.strip() for s in v]


def _at(obj, where):
    v = obj.get("at")
    if v is None:
        return None
    if (not isinstance(v, list) or len(v) != 3
            or not all(isinstance(n, (int, float)) and not isinstance(n, bool) and abs(n) < 1e7 for n in v)):
        raise ValueError(f"{where}: \"at\" should be a place, [x, y, z]")
    return [round(n) for n in v]


def _parts(obj, key, where):
    """A cat's "look" or "slots": {part: number}, {} when it's left out (the game chooses)."""
    v = obj.get(key)
    if v is None:
        return {}
    known = LOOK if key == "look" else SLOTS
    if not isinstance(v, dict):
        raise ValueError(f"{where}: \"{key}\" should map parts ({', '.join(known)}) to numbers")
    out = {}
    for part, n in v.items():
        if str(part).startswith("_"):
            continue
        if part not in known:
            raise ValueError(f"{where}: \"{key}\" has no part {part} (it takes {', '.join(known)})")
        top = LOOK_MAX.get(part, 9) if key == "look" else GAME_SLOTS - 1 if part == "fur" else None
        if isinstance(n, bool) or not isinstance(n, int) or n < 0 or (top is not None and n > top):
            raise ValueError(f"{where}: {key} {part} should be a whole number from 0"
                             + (f" to {top}" if top is not None else " up"))
        out[part] = n
    return out


def _id(obj, where):
    v = obj.get("id")
    if not isinstance(v, str) or not ID.match(v):
        raise ValueError(f"{where}: \"id\" should be small letters, digits and dashes (e.g. \"mossfoot\")")
    return v


def item_tag(tag, where):
    if not isinstance(tag, str) or not tag.startswith(ITEM_ROOT) or len(tag) > 120:
        raise ValueError(f"{where}: an item is its whole tag, e.g. \"Gameplay.Inventory.Materials.Dandelion\"")
    return tag


def npcs(raw):
    """npcs.json checked, as a list of cats with only the keys the game uses. Raises ValueError."""
    if not isinstance(raw, dict) or not isinstance(raw.get("npcs", []), list):
        raise ValueError('npcs.json should be an object: {"npcs": [...]}')
    out, seen = [], set()
    for i, npc in enumerate(raw.get("npcs", [])):
        where = f"npcs.json: cat {i + 1}"
        if not isinstance(npc, dict):
            raise ValueError(f"{where} should be an object")
        nid = _id(npc, where)
        where = f"npcs.json: {nid}"
        if nid in seen:
            raise ValueError(f"{where}: two cats have this id")
        seen.add(nid)
        _unknown(npc, NPC_KEYS, where)
        cat = {"id": nid, "name": _text(npc, "name", where, limit=40)}
        title = _text(npc, "title", where, required=False, limit=40)
        if title:
            cat["title"] = title
        colours = npc.get("colours") or {}
        if not isinstance(colours, dict):
            raise ValueError(f"{where}: \"colours\" should map parts ({', '.join(COLOURS)}) to \"#rrggbb\"")
        for part, value in colours.items():
            if part not in COLOURS:
                raise ValueError(f"{where}: \"colours\" has no part {part} (it takes {', '.join(COLOURS)})")
            if not isinstance(value, str) or not HEX.match(value):
                raise ValueError(f"{where}: colour {part} should be like \"#7a6a58\"")
        if colours:
            cat["colours"] = {k: v.lower() for k, v in colours.items()}
        for key, lo, hi, whole in (("eyes", 0, 24, True), ("size", 0.3, 1.5, False), ("yaw", -360, 360, False)):
            v = _number(npc, key, where, lo, hi, whole)
            if v is not None:
                cat[key] = v
        for key in ("look", "slots"):
            parts = _parts(npc, key, where)
            if parts:
                cat[key] = parts
        at = _at(npc, where)
        if at:
            cat["at"] = at
            level = _text(npc, "level", where, required=False)
            if level:
                cat["level"] = level
        else:
            cat.pop("yaw", None)   # beside your cat, it faces your cat
        cat["lines"] = _lines(npc, "lines", where)
        out.append(cat)
    return out


def quests(raw, cats=()):
    """quests.json checked against the mod's own cats (their ids), as a list of quests. Raises ValueError."""
    if not isinstance(raw, dict) or not isinstance(raw.get("quests", []), list):
        raise ValueError('quests.json should be an object: {"quests": [...]}')
    cats = set(cats)
    out, ids = [], []
    for i, q in enumerate(raw.get("quests", [])):
        where = f"quests.json: quest {i + 1}"
        if not isinstance(q, dict):
            raise ValueError(f"{where} should be an object")
        qid = _id(q, where)
        where = f"quests.json: {qid}"
        if qid in ids:
            raise ValueError(f"{where}: two quests have this id")
        ids.append(qid)
        _unknown(q, QUEST_KEYS, where)
        quest = {"id": qid, "title": _text(q, "title", where, limit=60)}
        desc = _text(q, "description", where, required=False, limit=MAX_LINE)
        if desc:
            quest["description"] = desc
        giver = q.get("giver")
        if giver is not None:
            if giver not in cats:
                raise ValueError(f"{where}: \"giver\" {giver} isn't one of this mod's cats (npcs.json)")
            quest["giver"] = giver
        after = q.get("after") or []
        if not isinstance(after, list) or not all(isinstance(a, str) for a in after):
            raise ValueError(f"{where}: \"after\" should be a list of quest ids")
        quest["after"] = list(dict.fromkeys(after))
        steps = q.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError(f"{where}: \"steps\" should be a list with at least one step")
        if len(steps) > MAX_STEPS:
            raise ValueError(f"{where}: more than {MAX_STEPS} steps")
        quest["steps"] = [_step(s, f"{where}: step {n + 1}", quest.get("giver"), cats) for n, s in enumerate(steps)]
        reward = q.get("reward") or {}
        if not isinstance(reward, dict):
            raise ValueError(f"{where}: \"reward\" should map items to how many")
        for tag, n in reward.items():
            item_tag(tag, f"{where}: reward")
            if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_COUNT:
                raise ValueError(f"{where}: reward {tag} should be a whole number from 1 to {MAX_COUNT}")
        if reward:
            quest["reward"] = dict(reward)
        out.append(quest)
    known = set(ids)
    for quest in out:
        for a in quest["after"]:
            if a not in known:
                raise ValueError(f"quests.json: {quest['id']}: \"after\" names {a}, which isn't one of this mod's quests")
            if a == quest["id"]:
                raise ValueError(f"quests.json: {quest['id']}: a quest can't come after itself")
    _no_loops(out)
    return out


def _step(s, where, giver, cats):
    if not isinstance(s, dict):
        raise ValueError(f"{where} should be an object")
    _unknown(s, STEP_KEYS, where)
    kind = s.get("do")
    if kind not in STEPS:
        raise ValueError(f"{where}: \"do\" should be {', '.join(STEPS)}")
    step = {"do": kind}
    objective = _text(s, "objective", where, required=False, limit=80)
    if objective:
        step["objective"] = objective
    if kind == "talk":
        npc = s.get("npc") or giver
        if npc is None:
            raise ValueError(f"{where}: who to talk to: \"npc\" (or the quest's \"giver\")")
        if npc not in cats:
            raise ValueError(f"{where}: \"npc\" {npc} isn't one of this mod's cats (npcs.json)")
        step["npc"] = npc
        step["lines"] = _lines(s, "lines", where, required=True)
    elif kind == "collect":
        step["item"] = item_tag(s.get("item"), where)
        step["count"] = _number(s, "count", where, 1, MAX_COUNT, whole=True) or 1
    else:
        at, place = _at(s, where), s.get("place")
        if (at is None) == (place is None):
            raise ValueError(f"{where}: where to go: \"at\": [x, y, z], or a \"place\" ({', '.join(PLACES)})")
        if at:
            step["at"] = at
            level = _text(s, "level", where, required=False)
            if level:
                step["level"] = level
        elif place not in PLACES:
            raise ValueError(f"{where}: \"place\" should be one of {', '.join(PLACES)}")
        else:
            step["place"] = place
            step["class"] = PLACES[place]
        step["radius"] = _number(s, "radius", where, 100, 5000) or 400
    return step


def _no_loops(quests_):
    after = {q["id"]: q["after"] for q in quests_}
    done = set()

    def visit(qid, path):
        if qid in path:
            loop = " -> ".join(path[path.index(qid):] + [qid])
            raise ValueError(f"quests.json: these quests each wait for the other, so none would start: {loop}")
        if qid in done:
            return
        for a in after[qid]:
            visit(a, path + [qid])
        done.add(qid)

    for qid in after:
        visit(qid, [])


def read(npcs_raw, quests_raw):
    """A mod's npcs.json and quests.json (either None when it has none), checked: {"npcs", "quests"}."""
    cats = npcs(npcs_raw) if npcs_raw is not None else []
    qs = quests(quests_raw, [c["id"] for c in cats]) if quests_raw is not None else []
    return {"npcs": cats, "quests": qs}


def bundle(items, icons=None):
    """Every mod's cats and questlines, [(mod, {"npcs", "quests"})], as the JSON text the game gets, with the
    icons of the items they name ({tag: texture asset path}) for the game's objective panel."""
    return json.dumps({"format": FORMAT, "mods": [{"id": mod.id, "name": mod.name, **data} for mod, data in items],
                       "icons": icons or {}}, ensure_ascii=False, separators=(",", ":"))


def items_used(data):
    """The item tags a mod's quests name (collect steps and rewards)."""
    out = set()
    for q in data["quests"]:
        out.update(q.get("reward", {}))
        out.update(s["item"] for s in q["steps"] if s["do"] == "collect")
    return out


def objective(step, cat_name, item_name):
    """What the game's objective panel says for a step its maker left without one: "Talk to Mossfoot",
    "Find 2 Moss", "Visit the nearest medicine cat", "Go to the marked place". cat_name(id) and item_name(tag)
    give today's names. (The Questlines page shows the same words as the field's placeholder.)"""
    if step["do"] == "talk":
        return f"Talk to {cat_name(step['npc'])}"
    if step["do"] == "collect":
        count = step.get("count", 1)
        return f"Find {count} {item_name(step['item'])}" if count > 1 else f"Find {item_name(step['item'])}"
    if step.get("place"):
        return f"Visit {PLACE_WORDS.get(step['place'], step['place'])}"
    return "Go to the marked place"


def item_words(tag):
    """An item's name from its tag alone, for one nothing names: "SmallHealingHerb" -> "Small Healing Herb"."""
    last = str(tag).rsplit(".", 1)[-1]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", last)


def has_any(folder):
    """Whether a mod's npcs.json or quests.json holds a cat or a quest (files that can't be read count as none)."""
    for name, key in (("npcs.json", "npcs"), ("quests.json", "quests")):
        try:
            with open(os.path.join(folder, name), encoding="utf-8-sig") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict) and isinstance(raw.get(key), list) and raw[key]:
            return True
    return False


def needs_of(data):
    """{field: [names of the cats that use it]} for the fields of SANDBOX_NEEDS a mod's cats and quests use."""
    out = {}
    for cat in data["npcs"]:
        for field in ("look", "slots"):
            if cat.get(field):
                out.setdefault(field, []).append(cat["name"])
    return out


def sandbox(found, allow_code):
    """What Sandbox mode can show of the mods' cats and questlines, for the story pages and the build:
    {"state": "on" | "off" | "no-code" | "missing", "version": its version ("" when it has none, None when it
    isn't there), "name", "needs": SANDBOX_NEEDS, "newest": the newest version they ask for (the one to get),
    "older": the fields of SANDBOX_NEEDS it's too old for, "releases": where to download it, "code_allowed"}. found: the mods folder's mods (mods.discover);
    allow_code: whether mods that run code are allowed, which Sandbox mode, a script, needs."""
    m = next((x for x in found if x.id == SANDBOX_ID), None)
    if m is None:
        state = "missing"
    elif not m.enabled:
        state = "off"
    elif not allow_code:
        state = "no-code"
    else:
        state = "on"
    version = m.version if m else None
    older = sorted(k for k, v in SANDBOX_NEEDS.items() if m is not None and version_key(version) < version_key(v))
    return {"state": state, "version": version, "name": m.name if m else SANDBOX_NAME, "needs": dict(SANDBOX_NEEDS),
            "newest": max(SANDBOX_NEEDS.values(), key=version_key), "older": older, "releases": SANDBOX_RELEASES,
            "code_allowed": bool(allow_code)}


def start_over(folder):
    """Every sandbox cat's questlines back to the start, as the mod menu's "Start every questline over" does:
    sandbox-story.json in `folder` (pipeline.saved_folder) keeps each cat's entry and where its cats stand,
    without its quests. A file that can't be read goes. Returns {"cats": how many sandbox cats it touched}."""
    path = os.path.join(folder, PROGRESS_FILE)
    if not os.path.isfile(path):
        return {"cats": 0}
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except (OSError, ValueError):
        os.remove(path)
        return {"cats": 0, "removed": True}
    touched = 0
    for key, entry in data.items():
        if not key.startswith("_") and isinstance(entry, dict):
            entry["quests"] = {}
            touched += 1
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False)
    return {"cats": touched}
