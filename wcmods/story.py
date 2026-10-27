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
          "lines": ["The forest is yours, young one."]
        }
      ]
    }

  A cat with no "at" turns up beside your sandbox cat the first time it comes into the forest, and stays
  there for that cat; "at": [x, y, z] (with "yaw" and "level") puts it in one place for every cat. "lines"
  is what it says when it has nothing to do with a quest.

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
  nearest of a "place": the medicine cat). "objective" is what the quest panel says (made up from the step
  when left out). "reward" is dropped at your cat's paws when the last step is done.

Ids are a mod's own: a quest names the mod's own cats and quests. Keys starting with "_" are notes.
"""
import json
import re

FILES = ("npcs.json", "quests.json")
FORMAT = 1
SANDBOX_ID = "sandbox"   # the mod that runs them: its folder name, what a mod gives in "requires"
SHARED_VARIABLE = "WCMods.story"   # what the game gets: every mod's cats and questlines, as JSON text

ID = re.compile(r"[a-z0-9][a-z0-9-]{0,47}$")
HEX = re.compile(r"#[0-9A-Fa-f]{6}$")
COLOURS = ("fur", "pattern", "markings", "nose", "paws", "whiskers", "ears")
# Places a "visit" step can name: the actor class of each (the nearest one counts).
PLACES = {"medicine-cat": "BP_Quest_Giver_Bartering_C"}
STEPS = ("talk", "collect", "visit")
ITEM_ROOT = "Gameplay.Inventory."
MAX_LINE, MAX_LINES, MAX_STEPS, MAX_COUNT = 400, 30, 40, 99

NPC_KEYS = {"id", "name", "title", "colours", "eyes", "size", "at", "yaw", "level", "lines"}
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


def bundle(items):
    """Every mod's cats and questlines, [(mod, {"npcs", "quests"})], as the JSON text the game gets."""
    return json.dumps({"format": FORMAT, "mods": [{"id": mod.id, "name": mod.name, **data} for mod, data in items]},
                      ensure_ascii=False, separators=(",", ":"))


def items_used(data):
    """The item tags a mod's quests name (collect steps and rewards)."""
    out = set()
    for q in data["quests"]:
        out.update(q.get("reward", {}))
        out.update(s["item"] for s in q["steps"] if s["do"] == "collect")
    return out
