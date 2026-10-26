"""Cat names: the game's name tables, and the edits that rename, add and remove names (names.json).

How the game names cats (checked against its tables and save):
- A clan cat's name is a prefix and a suffix: NPC/PreffixName.csv lists the prefixes ("Otter", ID
  STR_CAT_NAME53) with how often each clan uses them; NPC/SuffixName.csv lists the suffixes ("paw",
  ID _PAW) with how often each rank gets them. The name shown is the English text under the key
  prefix ID + suffix ID (STR_CAT_NAME53_PAW = "Otterpaw") in Strings_EN.csv. Every such text is
  exactly prefix + suffix; one combination (Black + face) is left out on purpose.
- PrefixNameFilters.csv and SuffixNameFilters.csv score names against a cat's clan, looks (and, for
  suffixes, personality) for the name screen's suggestions.
- Rogues and loners take a whole name from NPC/RogueNames.csv (text under STR_ROGUE_CAT_NAME_<n>;
  the table's Name column is only a label). Canon cameo cats have fixed texts (STR_CAT_NAME_ICONIC_<n>).
- NPC/NameBanList.csv lists prefix + suffix combinations the game never hands out (canon names).
- The save stores each cat as text with PrefixNameId="..." and SuffixNameId="..." (the player under
  GameplayProgression, NPCs under NPCData); story roles like {THE AGING LEADER} show the name of
  the NPC cast in them (NPCData/NarrativeRoles). A save holds a game per cat slot started (the
  account data's numbered keys, each with its own player cat and clans); Shared/General/CurrentCatSlot
  is the one being played, and what "player", a name or a place means unless a slot is given first.

Names added by mods get IDs made from the name (STR_CAT_NAME_WCM_SPARROW), so a saved cat keeps its
name whatever other mods add. Removing a prefix or suffix only stops the game handing it out: its
texts stay, so cats that already have it keep their names.
"""
import json
import os
import re

PREFIXES = "NPC/PreffixName.csv"
PREFIX_LOOKS = "PrefixNameFilters.csv"
SUFFIXES = "NPC/SuffixName.csv"
SUFFIX_LOOKS = "SuffixNameFilters.csv"
ROGUES = "NPC/RogueNames.csv"
BANNED = "NPC/NameBanList.csv"
LANGUAGES = ("EN", "DE", "ES", "FR", "IT", "NL")
TABLES = (PREFIXES, PREFIX_LOOKS, SUFFIXES, SUFFIX_LOOKS, ROGUES, BANNED)
CLANS = ("ThunderClan", "RiverClan", "ShadowClan", "WindClan", "OutOfClans")
RANKS = ("Kit", "Apprentice", "Warrior", "Deputy", "Leader", "MedicineCat", "Queen", "Elder", "RogueCat",
         "RogueCatLeader", "StarClanAncestor")
PLAYER_TAIL = "GameplayProgression/Gameplay.Combat.Character.Cat.Player/Customization"   # your cat: <slot>/PLAYER_TAIL
SECTIONS = ("prefixes", "suffixes", "rogues", "banned", "names", "text", "cats")
# A whole field name: not the tail of a longer one (say, MotherPrefixNameId).
_FIELD = re.compile(r'(?<![A-Za-z0-9_])(PrefixNameId|SuffixNameId)="([^"]*)"')
_SLOT_TARGET = re.compile(r"^(\d+)/(.*)$")   # a cats key with the slot first: 1/player, 1/Blaze, 1/RiverClan/Warrior/3


def current_slot(data):
    """The slot being played, as its key in the account data ("1"); "0" when the save doesn't say."""
    try:
        return str(data["Shared"]["General"]["CurrentCatSlot"])
    except (KeyError, TypeError):
        return "0"


def is_player(path):
    return path.split("/", 1)[1:] == [PLAYER_TAIL]


def place(path):
    """Where a cat is, without its slot: "player" for your cat, else its path under NPCData
    ("Clans/RiverClan/Warrior/3", "NarrativeRoles/TheAgingLeader")."""
    if is_player(path):
        return "player"
    parts = path.split("/")
    return "/".join(parts[2:] if parts[1:2] == ["NPCData"] else parts[1:])


def target_of(cat):
    """The cats key that picks this cat by place: "player" or its place, with the slot first
    ("1/player", "1/Clans/RiverClan/Warrior/3") for a cat in a game other than the one being played."""
    where = place(cat["paths"][0])
    return where if cat["current"] else f"{cat['slot']}/{where}"


def _parse_target(target):
    """A cats key as (slot or None, the rest: "player", a name or a place)."""
    m = _SLOT_TARGET.match(target)
    return (m.group(1), m.group(2)) if m else (None, target)


def _slot_order(slot):
    return (0, int(slot)) if slot.isdigit() else (1, slot)


def strings_path(lang):
    return f"Wrc/Content/Gameplay/Strings/NonAsset/Strings_{lang}.csv"


class GameNames:
    """The game's names, read from its tables: read_text(path) returns a NonAsset or Wrc/ file's text."""

    def __init__(self, read_text):
        from .csvdata import Table
        self.tables = {t: Table(read_text(t)) for t in TABLES}
        self.strings = {lang: Table(read_text(strings_path(lang))) for lang in LANGUAGES}
        self.text = {r.fields[0]: r.fields[1] for r in self.strings["EN"].rows if len(r.fields) > 1}

        def rows(table, cols):
            t = self.tables[table]
            idx = [t.column(c) for c in cols]
            return [[r.fields[i] if i < len(r.fields) else "" for i in idx] for r in t.rows if r.fields and r.fields[0]]

        self.prefixes = [{"row": n, "text": txt, "id": pid, "weights": dict(zip(CLANS, map(_num, w)))}
                         for n, txt, *w, pid in rows(PREFIXES, ("#", "Preffix", *CLANS, "Preffix_ID"))]
        self.suffixes = [{"row": n, "text": txt, "id": sid, "weights": dict(zip(RANKS, map(_num, w)))}
                         for n, txt, *w, sid in rows(SUFFIXES, ("#", "Suffix", *RANKS, "Suffix_ID"))]
        self.rogues = [{"row": n, "label": label, "id": rid, "text": self.text.get(rid, label)}
                       for n, label, rid in rows(ROGUES, ("#", "Name", "PrefixID"))]
        self.banned = [{"row": n, "name": name, "prefix": p, "suffix": s}
                       for n, name, p, s in rows(BANNED, ("#", "Name", "PrefixID", "SuffixID"))]
        self.iconic = {k: v for k, v in self.text.items() if k.startswith("STR_CAT_NAME_ICONIC_")}

    def summary(self):
        return {"prefixes": self.prefixes, "suffixes": self.suffixes, "rogues": self.rogues,
                "banned": self.banned, "iconic": self.iconic}


def _num(s):
    try:
        return float(s)
    except ValueError:
        return 0.0


def slug(name):
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return s or "X" + "".join(f"{ord(c):X}" for c in name)


def validate(raw, where="names.json"):
    """Check a names.json and return it without help keys. Raises ValueError for mistakes."""
    if not isinstance(raw, dict):
        raise ValueError(f"{where} should be an object")
    out = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if key not in SECTIONS:
            raise ValueError(f"{where}: '{key}' should be one of {', '.join(SECTIONS)}")
        if not isinstance(value, dict):
            raise ValueError(f"{where}: '{key}' should be an object")
        if key in ("prefixes", "suffixes", "rogues"):
            allowed = ("rename", "add", "remove") + (("weights",) if key != "rogues" else ())
            for op, v in value.items():
                if op.startswith("_"):
                    continue
                if op not in allowed:
                    raise ValueError(f"{where}: {key}.{op} should be one of {', '.join(allowed)}")
                want = list if op == "remove" or (key == "rogues" and op == "add") else dict
                if not isinstance(v, want):
                    raise ValueError(f"{where}: {key}.{op} should be a{'' if want is dict else ' list'}"
                                     f"{'n object' if want is dict else ''}")
        if key == "banned":
            for op, v in value.items():
                if op.startswith("_"):
                    continue
                if op not in ("add", "remove", "clear"):
                    raise ValueError(f"{where}: banned.{op} should be add, remove or clear")
                if op != "clear" and not isinstance(v, list):
                    raise ValueError(f"{where}: banned.{op} should be a list of names")
        out[key] = {k: v for k, v in value.items() if not str(k).startswith("_")}
    return out


def mod_specs(mod_list):
    """Validated names.json of each enabled mod, in the order given (priority order)."""
    out = []
    for m in mod_list:
        path = os.path.join(m.folder, "names.json")
        if m.enabled and os.path.isfile(path):
            with open(path, encoding="utf-8-sig") as f:
                out.append(validate(json.load(f), f"{m.id}/names.json"))
    return out


def cat_list(plan, cats, ops=()):
    """The cats in a save for showing: the target to name them by (cats key in names.json), their slot
    (the game they're in) and whether it's the one being played, where they are in it, their rank, story
    roles and their name before and after the plan (ops: plan_cats' renames, which win over the plan's
    text changes). The game being played comes first, your cat first in each."""
    renamed = {op["path"]: op["to"] for op in ops}
    out = []
    for cat in cats:
        first, ids = cat["paths"][0], cat["ids"]
        roles = [p.rsplit("/", 1)[-1] for p in cat["paths"] if "/NarrativeRoles/" in p]
        out.append({"target": target_of(cat), "slot": cat["slot"], "current": cat["current"], "player": cat["player"],
                    "where": "you" if cat["player"] and cat["current"] else "your cat" if cat["player"] else place(first),
                    "roles": roles, "role": ids.get("Role", "Player" if cat["player"] else ""),
                    "name": plan.current_name(ids), "with_mods": renamed.get(first, plan.display(ids))})
    return out


def merge(specs):
    """names.json contents from several mods in priority order; later ones win name by name."""
    out = {"prefixes": {}, "suffixes": {}, "rogues": {}, "banned": {"add": [], "remove": [], "clear": False},
           "names": {}, "text": {}, "cats": {}}
    def drop(items, names):
        low = {str(n).lower() for n in names}
        if isinstance(items, dict):
            for k in [k for k in items if k.lower() in low]:
                del items[k]
        else:
            items[:] = [x for x in items if str(x).lower() not in low]

    for spec in specs:
        for kind in ("prefixes", "suffixes", "rogues"):
            part = spec.get(kind, {})
            # A later mod's add undoes an earlier removal of the same name, and its remove an earlier add.
            drop(out[kind].get("remove", []), part.get("add", []))
            drop(out[kind].get("add", {} if kind != "rogues" else []), part.get("remove", []))
            for op, v in part.items():
                cur = out[kind].setdefault(op, [] if isinstance(v, list) else {})
                if isinstance(v, list):
                    cur += [x for x in v if x not in cur]
                elif op == "weights":
                    for name, w in v.items():
                        cur.setdefault(name, {}).update(w)
                else:
                    cur.update(v)
        b = spec.get("banned", {})
        if b.get("clear"):
            out["banned"]["add"] = []
        out["banned"]["clear"] |= bool(b.get("clear"))
        drop(out["banned"]["remove"], b.get("add", []))
        drop(out["banned"]["add"], b.get("remove", []))
        for op in ("add", "remove"):
            out["banned"][op] += [x for x in b.get(op, []) if x not in out["banned"][op]]
        for kind in ("names", "text", "cats"):
            out[kind].update(spec.get(kind, {}))
    return out


class Plan:
    """What a merged names.json does to the game: CSV edits per table and language, save renames."""

    def __init__(self, game, spec):
        self.game, self.spec = game, spec
        self.edits = {}           # table path -> csvdata edits
        self.warnings = []
        self.renames = []         # [(target, how)] for cats in the save, resolved by plan_cats
        self.cat_renames = []     # [(name before, name after)] per renamed cat, filled by plan_cats
        # Copies, weights included: GameNames is read once and shared (the studio previews many plans).
        self.prefixes = [dict(p, final=p["text"], weights=dict(p["weights"])) for p in game.prefixes]
        self.suffixes = [dict(s, final=s["text"], weights=dict(s["weights"])) for s in game.suffixes]
        self.final = dict(game.text)   # English key -> text after this plan
        self.added_keys = {}           # key -> English text, added to every language
        self._plan()

    # ---- helpers ----
    def _edit(self, table, row=None, cells=None, add=None, remove=None):
        e = self.edits.setdefault(table, {})
        if remove is not None:
            e.setdefault("-", []).append(remove)
        if add is not None:
            e.setdefault("+", []).append(add)
        if cells:
            e.setdefault(row, {}).update(cells)

    def _find(self, items, name, kind):
        low = name.lower()
        hits = [x for x in items if x["text"].lower() == low or x["id"].lower() == low]
        if not hits:
            self.warnings.append(f"{kind}: the game has no '{name}'")
        return hits

    def _next_row(self, table):
        nums = [int(r.fields[0]) for r in self.game.tables[table].rows if r.fields and r.fields[0].isdigit()]
        nums += [int(a[self.game.tables[table].header[0]]) for a in self.edits.get(table, {}).get("+", [])]
        return str(max(nums, default=0) + 1)

    def _set_text(self, key, text):
        if self.final.get(key) == text:
            return
        self.final[key] = text
        if key in self.game.text:
            self._edit(strings_path("EN"), key, {"SourceString": text})
        else:
            self.added_keys[key] = text

    # ---- the plan ----
    def _plan(self):
        sp = self.spec
        self._plan_affixes("prefixes", self.prefixes, PREFIXES, PREFIX_LOOKS, "Preffix", "Prefix", CLANS,
                           "clans", "STR_CAT_NAME_WCM_", sp.get("prefixes", {}))
        self._plan_affixes("suffixes", self.suffixes, SUFFIXES, SUFFIX_LOOKS, "Suffix", "Suffix", RANKS,
                           "ranks", "_WCM_", sp.get("suffixes", {}))
        self._plan_combinations()
        self._plan_rogues(sp.get("rogues", {}))
        self._plan_banned(sp.get("banned", {}))
        # Cats' own names need their texts in every build, whether or not the cat is in the save now
        # (once renamed it no longer has its old name, and there may be no save at all).
        self.renames = [(target, _norm(how)) for target, how in sp.get("cats", {}).items()]
        for target, how in self.renames:
            self._custom_texts(how, target)
        for old, new in sp.get("names", {}).items():
            keys = [k for k, v in self.final.items() if v == old]
            if not keys:
                self.warnings.append(f"names: nothing in the game is called '{old}'")
            for k in keys:
                self._set_text(k, str(new))
        for key, text in sp.get("text", {}).items():
            if key not in self.final:
                self.warnings.append(f"text: the game has no text '{key}'; added it")
            self._set_text(key, str(text))
        self._finish_strings()

    def _plan_affixes(self, kind, items, table, looks, text_col, looks_col, weight_cols, weight_key, id_base, spec):
        removed = set()
        for old, new in spec.get("rename", {}).items():
            for x in self._find(items, old, f"{kind}.rename"):
                x["final"] = str(new)
                self._edit(table, x["row"], {text_col: str(new)})
                if self._looks_row(looks, x["row"], x["text"]):
                    self._edit(looks, x["row"], {looks_col: str(new)})
        for name, weights in spec.get("weights", {}).items():
            for x in self._find(items, name, f"{kind}.weights"):
                bad = [c for c in weights if c not in weight_cols]
                if bad:
                    self.warnings.append(f"{kind}.weights.{name}: no column {', '.join(bad)} "
                                         f"(columns: {', '.join(weight_cols)})")
                cells = {c: float(v) for c, v in weights.items() if c in weight_cols}
                x["weights"].update(cells)
                self._edit(table, x["row"], cells)
        for name in spec.get("remove", []):
            for x in self._find(items, name, f"{kind}.remove"):
                if kind == "suffixes" and not self._can_remove_suffix(x, removed):
                    continue
                removed.add(x["id"])
                self._edit(table, remove=x["row"])
                if self._looks_row(looks, x["row"], x["text"]):
                    self._edit(looks, remove=x["row"])
        for name, opts in spec.get("add", {}).items():
            opts = opts if isinstance(opts, dict) else {}
            if any(x["final"].lower() == name.lower() for x in items):
                self.warnings.append(f"{kind}.add: '{name}' is already a {kind[:-2]}; skipped")
                continue
            like = None
            if opts.get("like"):
                hits = self._find(items, opts["like"], f"{kind}.add.{name}.like")
                like = hits[0] if hits else None
            weights = dict(like["weights"]) if like else {c: _average(items, c) for c in weight_cols}
            if kind == "suffixes" and not like:
                weights.update(Kit=0.0, Apprentice=0.0, Leader=0.0)   # those ranks have their own suffixes
            weights.update({c: float(v) for c, v in opts.get(weight_key, {}).items() if c in weight_cols})
            new_id = id_base + slug(name)
            clash = [x for x in items if x["id"] == new_id]
            if clash:
                self.warnings.append(f"{kind}.add: '{name}' would share an ID with '{clash[0]['text']}'; skipped")
                continue
            row = self._next_row(table)
            self._edit(table, add={"#": row, text_col: name, **weights,
                                   ("Preffix_ID" if kind == "prefixes" else "Suffix_ID"): new_id})
            look = self._looks_cells(looks, like["row"] if like else None, opts.get("looks", {}))
            look_key = self.game.tables[looks].header[0]
            self._edit(looks, add={look_key: self._next_row(looks), looks_col: name, **look})
            items.append({"row": row, "text": name, "final": name, "id": new_id, "weights": weights, "new": True})
        if kind == "prefixes":
            for clan in CLANS[:4]:
                if not any(x["weights"].get(clan, 0) > 0 for x in items if x["id"] not in removed):
                    self.warnings.append(f"prefixes: no prefix is left for {clan}")

    def _looks_row(self, looks, row, text):
        t = self.game.tables[looks]
        hit = t.find_rows(row)
        return bool(hit) and len(hit[0].fields) > 1 and hit[0].fields[1].lower() == text.lower()

    def _looks_cells(self, looks, like_row, overrides):
        t = self.game.tables[looks]
        cols = t.header[2:]
        base = None
        if like_row is not None:
            hit = t.find_rows(like_row)
            base = hit[0].fields[2:] if hit else None
        cells = dict(zip(cols, base)) if base else {c: 1 for c in cols}
        for c, v in overrides.items():
            if c in cols:
                cells[c] = v
            else:
                self.warnings.append(f"looks: no column '{c}'")
        return cells

    def _can_remove_suffix(self, x, removed):
        for rank in RANKS:
            if x["weights"].get(rank, 0) > 0 and not any(
                    s is not x and s["id"] not in removed and s["weights"].get(rank, 0) > 0 for s in self.suffixes):
                self.warnings.append(f"suffixes.remove: '{x['text']}' is the only suffix for {rank}; kept it")
                return False
        return True

    def _plan_combinations(self):
        for p in self.prefixes:
            for s in self.suffixes:
                key = p["id"] + s["id"]
                new = p.get("new") or s.get("new")
                if key not in self.game.text and not new:
                    continue   # a combination the game leaves out on purpose
                text = p["final"] + s["final"]
                if new or self.final.get(key) != text:
                    self._set_text(key, text)

    def _plan_rogues(self, spec):
        rogues = [dict(r, final=r["text"]) for r in self.game.rogues]
        for old, new in spec.get("rename", {}).items():
            hits = [r for r in rogues if old.lower() in (r["final"].lower(), r["label"].lower(), r["id"].lower())]
            if not hits:
                self.warnings.append(f"rogues.rename: no rogue is called '{old}'")
            for r in hits:
                r["final"] = str(new)
                self._set_text(r["id"], str(new))
                self._edit(ROGUES, r["row"], {"Name": str(new)})
        for name in spec.get("remove", []):
            hits = [r for r in rogues if name.lower() in (r["final"].lower(), r["label"].lower(), r["id"].lower())]
            if not hits:
                self.warnings.append(f"rogues.remove: no rogue is called '{name}'")
            for r in hits:
                self._edit(ROGUES, remove=r["row"])
        for name in spec.get("add", []):
            if any(r["final"].lower() == str(name).lower() for r in rogues):
                self.warnings.append(f"rogues.add: '{name}' is already a rogue name; skipped")
                continue
            rid = "STR_ROGUE_CAT_NAME_WCM_" + slug(str(name))
            clash = [r for r in rogues if r["id"] == rid]
            if clash:
                self.warnings.append(f"rogues.add: '{name}' would share an ID with '{clash[0]['final']}'; skipped")
                continue
            self._edit(ROGUES, add={"#": self._next_row(ROGUES), "Name": str(name), "PrefixID": rid})
            self._set_text(rid, str(name))
            rogues.append({"row": None, "label": name, "id": rid, "text": name, "final": name})
        self.rogues = rogues

    def split(self, name):
        """(prefix, suffix) pairs whose final text makes this name, after this plan's changes."""
        low = name.lower()
        return [(p, s) for p in self.prefixes for s in self.suffixes
                if low == (p["final"] + s["final"]).lower()]

    def _plan_banned(self, spec):
        rows = list(self.game.banned)
        drop = set()
        if spec.get("clear"):
            drop = {b["row"] for b in rows}
        for name in spec.get("remove", []):
            hits = [b for b in rows if b["name"].lower() == name.lower()
                    or self.final.get(b["prefix"] + b["suffix"], "").lower() == name.lower()]
            if not hits:
                self.warnings.append(f"banned.remove: '{name}' isn't on the ban list")
            drop |= {b["row"] for b in hits}
        for row in sorted(drop, key=lambda r: (len(r), r)):
            self._edit(BANNED, remove=row)
        for b in rows:   # the Name column is a label: keep it in step with parts this plan renames
            key = b["prefix"] + b["suffix"]
            shown = self.final.get(key)
            if b["row"] not in drop and shown and shown != self.game.text.get(key):
                self._edit(BANNED, b["row"], {"Name": shown})
        kept = {(b["prefix"], b["suffix"]) for b in rows if b["row"] not in drop}
        for name in spec.get("add", []):
            pairs = self.split(name)
            if not pairs:
                self.warnings.append(f"banned.add: '{name}' isn't a prefix + suffix the game can make")
            for p, s in pairs:
                if (p["id"], s["id"]) in kept:
                    continue
                kept.add((p["id"], s["id"]))
                self._edit(BANNED, add={"#": self._next_row(BANNED), "Name": name, "PrefixID": p["id"],
                                        "SuffixID": s["id"]})

    def _finish_strings(self):
        """Added keys go into every language (with the English text), so no language shows a blank.
        Rebuilt from added_keys each time, so it can run again after plan_cats."""
        for lang in LANGUAGES:
            table = self.game.strings[lang]
            have = {r.fields[0] for r in table.rows if r.fields}
            rows = [{table.header[0]: k, table.header[1]: v} for k, v in self.added_keys.items() if k not in have]
            if rows:
                self.edits.setdefault(strings_path(lang), {})["+"] = rows

    # ---- cats in the save ----
    def plan_cats(self, cats):
        """cats: cats_in_save(). Returns save ops (one per copy of each renamed cat); self.cat_renames
        lists (from, to) per cat. A cat that already has its new name needs nothing."""
        ops, self.cat_renames = [], []
        for target, how in self.renames:
            hits = self._targets(target, how, cats)
            if not hits:
                if not any(self._has(c, how) for c in cats):
                    self.warnings.append(f"cats: no cat in your save is called '{target}'")
                continue
            if len(hits) > 1 and "/" not in _parse_target(target)[1]:
                self.warnings.append(f"cats: {len(hits)} cats are called '{target}', and all of them are renamed; "
                                     "use a cat's place from `names --cats` to pick one")
            for cat in hits:
                ids = cat["ids"]
                fields = self._new_ids(how, ids, target)
                if not fields or self._has(cat, how):
                    continue
                expect = {k: v for k, v in ids.items() if k in ("PrefixNameId", "SuffixNameId")}
                before, after = self.current_name(ids), self._shown(fields, ids)
                self.cat_renames.append((before, after))
                for path in cat["paths"]:
                    ops.append({"op": "name", "path": path, "set": fields, "expect": expect,
                                "from": before, "to": after, "where": _where(path, cat["current"])})
        return ops

    def _has(self, cat, how):
        fields = self._new_ids(how, cat["ids"], None)
        return bool(fields) and all(cat["ids"].get(k, "") == v for k, v in fields.items())

    def display(self, ids, final=True):
        """The name a cat shows. A kit or apprentice whose save text leaves out the suffix shows its rank's."""
        suffix = ids.get("SuffixNameId") or _RANK_SUFFIX.get(ids.get("Role", ""), "")
        key = ids.get("PrefixNameId", "") + suffix
        text = self.final if final else self.game.text
        return text.get(key) or text.get(ids.get("PrefixNameId", ""), "")

    def current_name(self, ids):
        """The name a cat has now: the game's own text for its IDs, else the text a names mod gives them (a
        cat renamed by an earlier install), else the IDs themselves (renamed by a mod that's off now)."""
        return (self.display(ids, final=False) or self.display(ids)
                or ids.get("PrefixNameId", "") + ids.get("SuffixNameId", ""))

    def _targets(self, target, how, cats):
        """Cats a cats entry means: "player", a name or a place (RiverClan/Warrior/3), each with a slot
        first ("1/player", "1/Blaze") for a game other than the one being played. Without a slot, a name
        or place means the game being played, or any game when that one has no such cat (so a names.json
        from before a second game was started keeps working); "player" is only ever the cat being played.
        A place can shift as the game adds and removes cats, so a place with "was" only counts while the
        cat there still has that name."""
        slot, want = _parse_target(target)
        if not want:
            return []
        if want.lower() == "player":
            hits = [c for c in cats if c["player"]]
            return [c for c in hits if c["slot"] == slot] if slot is not None else [c for c in hits if c["current"]]
        if "/" in want:
            # A place as names --cats shows it, or (as older names.json files could say it) with the NPCData
            # step kept, or a cat's whole path in the save.
            hits = [c for c in cats if any(place(p) == want or place(p).endswith("/" + want)
                                           or p == target or p.endswith("/" + want) for p in c["paths"])]
            if how.get("was"):
                hits = [c for c in hits if self._called(c, how["was"])]
        else:
            hits = [c for c in cats if self._called(c, want)]
        if slot is not None:
            return [c for c in hits if c["slot"] == slot]
        here = [c for c in hits if c["current"]]
        return here or hits

    def _called(self, cat, name):
        return name.lower() in (self.display(cat["ids"]).lower(), self.display(cat["ids"], final=False).lower())

    def _shown(self, fields, ids):
        return self.display({**ids, **fields})

    def _new_ids(self, how, ids, target):
        """The name IDs a cats entry gives this cat. The texts they need come from _custom_texts."""
        if how.get("name"):
            name = str(how["name"])
            rogue = [r for r in self.rogues if r["final"].lower() == name.lower()]
            if rogue and ids.get("PrefixNameId", "").startswith("STR_ROGUE_CAT_NAME"):
                return {"PrefixNameId": rogue[0]["id"]}
            pairs = self.split(name)
            if pairs:
                p, s = pairs[0]
                return {"PrefixNameId": p["id"], "SuffixNameId": s["id"]}
            return {"PrefixNameId": _fixed_id(name)}
        if how.get("prefix"):
            known = [p for p in self.prefixes if p["final"].lower() == str(how["prefix"]).lower()]
            return {"PrefixNameId": known[0]["id"] if known else _own_prefix_id(how["prefix"])}
        if how.get("fixed"):
            return {"PrefixNameId": _fixed_id(how["fixed"])}
        if target is not None:
            self.warnings.append(f"cats.{target}: give a name, {{\"prefix\": ...}} or {{\"fixed\": ...}}")
        return None

    def _custom_texts(self, how, target):
        """Texts for names no table has: a cat's own prefix (it grows with rank), or a fixed name (also
        what a whole name that isn't a prefix + suffix becomes)."""
        fixed = how.get("fixed")
        if how.get("name"):
            name = str(how["name"])
            if self.split(name) or any(r["final"].lower() == name.lower() for r in self.rogues):
                return
            fixed = name
        elif how.get("prefix"):
            name = str(how["prefix"])
            if any(p["final"].lower() == name.lower() for p in self.prefixes):
                return
            pid = _own_prefix_id(name)
            self._set_text(pid, name)          # a rogue or loner shows it with no suffix
            for s in self.suffixes:
                self._set_text(pid + s["id"], name + s["final"])
            return
        if fixed:
            pid = _fixed_id(fixed)
            self._set_text(pid, str(fixed))
            for s in self.suffixes:
                self._set_text(pid + s["id"], str(fixed))
        elif not how.get("name") and not how.get("prefix"):
            self.warnings.append(f"cats.{target}: give a name, {{\"prefix\": ...}} or {{\"fixed\": ...}}")


_RANK_SUFFIX = {"Kit": "_KIT", "Apprentice": "_PAW"}
_ROLE = re.compile(r"[(,]Role=(\w+)")


def _norm(how):
    """A cats entry as a dict: a plain string is a whole name."""
    if isinstance(how, str):
        return {"name": how}
    return how if isinstance(how, dict) else {}


def _own_prefix_id(name):
    return "STR_CAT_NAME_WCM_" + slug(str(name))   # a prefix only that cat has: not in the tables


def _fixed_id(name):
    return "STR_CAT_NAME_WCM_FIXED_" + slug(str(name))   # the same text whatever the suffix


def _average(items, col):
    vals = [x["weights"].get(col, 0) for x in items if x["weights"].get(col, 0) > 0]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def cats_in_save(data):
    """Every named cat in a save's account data: [{"paths": [...], "ids": {"PrefixNameId", "SuffixNameId",
    "Role"}, "slot": "1", "player": bool, "current": bool}]. A save holds a game per cat slot started; the
    one being played (current_slot) comes first, then the others by number, your cat first in each. A
    story role (NPCData/NarrativeRoles) holds a copy of a clan or outsider cat's text; copies are one
    cat, listed under all their paths, so a rename reaches every place the game reads it from."""
    found = {}

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}/{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}/{i}" if path else str(i))
        elif isinstance(o, str) and "PrefixNameId=" in o:
            found.setdefault((path.split("/", 1)[0], o), []).append(path)   # the same text in two games is two cats

    walk(data, "")
    current = current_slot(data)
    cats = []
    for (slot, text), paths in found.items():
        ids = dict(_FIELD.findall(text))
        role = _ROLE.search(text)
        if role:
            ids["Role"] = role.group(1)
        # Your cat first, then each cat's own place before the story roles it's cast in.
        paths.sort(key=lambda p: (not is_player(p), "/NarrativeRoles/" in p, p))
        cats.append({"paths": paths, "ids": ids, "slot": slot, "player": is_player(paths[0]), "current": slot == current})
    # The game being played first, then your cat, the clans, and last the cats that are only story roles.
    cats.sort(key=lambda c: (not c["current"], _slot_order(c["slot"]), not c["player"],
                             "/NarrativeRoles/" in c["paths"][0], c["paths"][0]))
    return cats


def _where(path, current=True):
    """A cat's path for people: "you" for your cat, else its place, with the slot first when the cat is
    in a game other than the one being played."""
    where = "you" if is_player(path) else place(path)
    return where if current else f"{path.split('/', 1)[0]}/{'player' if is_player(path) else where}"


def rename_struct(text, fields, expect):
    """Set PrefixNameId/SuffixNameId inside a cat's save text. Returns the new text, or None when the
    cat no longer has the name it had at build time (expect)."""
    have = dict(_FIELD.findall(text))
    if any(have.get(k, "") != v for k, v in expect.items()):
        return None
    for key, value in fields.items():
        field = re.compile(rf'(?<![A-Za-z0-9_]){key}="[^"]*"')
        if field.search(text):
            text = field.sub(lambda m: f'{key}="{value}"', text, count=1)
        elif key == "SuffixNameId":
            text = re.sub(r'((?<![A-Za-z0-9_])PrefixNameId="[^"]*")', lambda m: f'{m.group(1)},SuffixNameId="{value}"',
                          text, count=1)
    return text
