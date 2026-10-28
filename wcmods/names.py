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

The game looks a cat's name up by one key (lookup_key): its prefix ID and suffix ID, a kit's or
apprentice's rank suffix when its save text leaves the suffix out, and the prefix ID alone for a cat with
no suffix (a rogue or loner). A key with no text shows as <MISSING STRING TABLE ENTRY> (and "Cat 1" in
dialogue), so the planner never gives a cat IDs whose key has no text.
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
# The ranks in a sentence ("the only suffix for apprentices").
RANK_WORDS = {"Kit": "kits", "Apprentice": "apprentices", "Warrior": "warriors", "Deputy": "deputies",
              "Leader": "leaders", "MedicineCat": "medicine cats", "Queen": "queens", "Elder": "elders",
              "RogueCat": "rogues and loners", "RogueCatLeader": "rogue leaders", "StarClanAncestor": "StarClan's cats"}
# How a cat's new name works out (Plan.cat_how, cat_list's "how"): a prefix + suffix the tables have ("parts"),
# a name that stays the same at every rank ("fixed"), a rogue name on a rogue or loner ("rogue"), one of the
# game's prefixes kept with the cat's suffix ("prefix"), a prefix only that cat has ("own-prefix"), or none:
# the game would have no text for it, so the cat keeps its name.
HOWS = ("parts", "fixed", "rogue", "prefix", "own-prefix", "none")
# The IDs wcmods makes for names of its own (from the name, slug()): a fixed name, a prefix of a cat's own (or
# a prefix a mod adds), a rogue name a mod adds.
FIXED_BASE, OWN_BASE, ROGUE_BASE = "STR_CAT_NAME_WCM_FIXED_", "STR_CAT_NAME_WCM_", "STR_ROGUE_CAT_NAME_WCM_"
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


def slot_of(target):
    """The game slot a cats key names first ("2" in "2/Duskfang"), or None for the game being played."""
    return _parse_target(target)[0]


def by_place(target):
    """Whether a cats key picks a cat by its place (Clans/RiverClan/Warrior/3) rather than its name."""
    return "/" in _parse_target(target)[1]


def describe_target(target):
    """A cats key in words, for a sentence: "your cat", "Blaze", "the cat at RiverClan · Warrior · 3", with "in
    your 3rd game" after it for a cat in a game other than the one being played (game_words)."""
    slot, want = _parse_target(target)
    if want.lower() == "player":
        who = "your cat"
    elif "/" in want:
        who = "the cat at " + " · ".join(p for p in want.split("/") if p)
    else:
        who = want
    return who + (f" in {game_words(slot)}" if slot is not None else "")


def ordinal(n):
    """1st, 2nd, 3rd, 4th, 11th, 21st."""
    n = int(n)
    end = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{end}"


def game_words(slot):
    """A cat slot as the Names page heads its games: slot "1" is "your 2nd game"."""
    slot = str(slot)
    return f"your {ordinal(int(slot) + 1) if slot.isdigit() else slot} game"


def _cap(text):
    return text[:1].upper() + text[1:]


def _slot_order(slot):
    return (0, int(slot)) if slot.isdigit() else (1, slot)


def strings_path(lang):
    return f"Wrc/Content/Gameplay/Strings/NonAsset/Strings_{lang}.csv"


class GameNames:
    """The game's names, read from its tables: read_text(path) returns a NonAsset or Wrc/ file's text."""

    def __init__(self, read_text):
        from .formats.csvdata import Table
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
    """Check a names.json and return it without help keys. Raises ValueError, with a sentence, for what would
    stop the build or give cats broken names: the wrong kind of value anywhere the planner reads one (a weight
    that isn't a number, a rename to nothing). Shapes that only do nothing (a cats entry with two of name,
    prefix and fixed) are the planner's warnings instead, so they don't hold the other mods back."""
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
        value = {k: v for k, v in value.items() if not str(k).startswith("_")}
        if key in ("prefixes", "suffixes", "rogues"):
            allowed = ("rename", "add", "remove") + (("weights",) if key != "rogues" else ())
            for op, v in value.items():
                if op not in allowed:
                    raise ValueError(f"{where}: {key}.{op} should be one of {', '.join(allowed)}")
                want = list if op == "remove" or (key == "rogues" and op == "add") else dict
                if not isinstance(v, want):
                    raise ValueError(f"{where}: {key}.{op} should be a{'' if want is dict else ' list'}"
                                     f"{'n object' if want is dict else ''}")
            _check_parts(key, value, where)
        if key == "banned":
            for op, v in value.items():
                if op not in ("add", "remove", "clear"):
                    raise ValueError(f"{where}: banned.{op} should be add, remove or clear")
                if op != "clear" and not isinstance(v, list):
                    raise ValueError(f"{where}: banned.{op} should be a list of names")
                if op != "clear":
                    _check_names(v, f"banned.{op}", where)
        if key in ("names", "text"):
            for old, new in value.items():   # null would be "None" in the game, a number its digits
                if not isinstance(new, str) or not new.strip():
                    raise ValueError(f"{where}: {key}.{old} should be the new text, "
                                     f"{'not empty' if new is None or isinstance(new, str) else 'in quotes'}")
        if key == "cats":
            for target, how in value.items():
                if isinstance(how, dict) and "was" in how and not isinstance(how["was"], str):
                    raise ValueError(f"{where}: cats.{target}.was should be the name the cat had, in quotes")
        out[key] = value
    return out


def _check_parts(kind, value, where):
    """The leaves of prefixes, suffixes or rogues (their containers are checked already)."""
    for old, new in value.get("rename", {}).items():
        if not isinstance(new, str) or not new.strip():
            raise ValueError(f"{where}: {kind}.rename.{old} should be the new text, "
                             f"{'not empty' if new is None or isinstance(new, str) else 'in quotes'}")
    _check_names(value.get("remove", []), f"{kind}.remove", where)
    if kind == "rogues":
        _check_names(value.get("add", []), "rogues.add", where)
        return
    cols, col_key, noun = (CLANS, "clans", "prefix") if kind == "prefixes" else (RANKS, "ranks", "suffix")
    example = f'{{"{cols[0] if kind == "prefixes" else "Warrior"}": 0.07}}'
    for name, weights in value.get("weights", {}).items():
        if not isinstance(weights, dict):
            raise ValueError(f"{where}: {kind}.weights.{name} should be an object like {example}")
        for col, w in weights.items():
            if not _number(w):
                raise ValueError(f"{where}: {kind}.weights.{name}.{col} should be a number")
    for name, opts in value.get("add", {}).items():
        if not isinstance(opts, dict):
            continue   # read as {} (the average part), as it always was
        if opts.get("like") is not None and not isinstance(opts["like"], str):
            raise ValueError(f"{where}: {kind}.add.{name}.like should be the name of a {noun}, in quotes")
        if col_key in opts and (not isinstance(opts[col_key], dict) or not all(map(_number, opts[col_key].values()))):
            raise ValueError(f"{where}: {kind}.add.{name}.{col_key} should be an object like {example}")
        if "looks" in opts and not isinstance(opts["looks"], dict):
            raise ValueError(f"{where}: {kind}.add.{name}.looks should be an object")


def _check_names(items, what, where):
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{where}: {what} should be a list of names in quotes")


def _number(v):
    """A weight: a number, or a number in quotes (float() reads it, as the planner always has)."""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


def read_spec(mod):
    """A mod's names.json, checked (validate), or None when it has none. ValueError (or OSError) says what's
    wrong with it."""
    path = os.path.join(mod.folder, "names.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8-sig") as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"{mod.id}/names.json isn't valid: {e.msg} at line {e.lineno}") from None
    return validate(raw, f"{mod.id}/names.json")


def mod_specs(mod_list, bad=None):
    """Validated names.json of each enabled mod, in the order given (priority order). With `bad`, a file that
    can't be read or fails the check is left out and bad(mod, error) is called; without it, the error goes up."""
    out = []
    for m in mod_list:
        if not m.enabled:
            continue
        try:
            spec = read_spec(m)
        except (OSError, ValueError) as e:
            if bad is None:
                raise
            bad(m, e)
            continue
        if spec is not None:
            out.append(spec)
    return out


def cat_list(plan, cats, ops=()):
    """The cats in a save for showing: the target to name them by (cats key in names.json), their slot
    (the game they're in) and whether it's the one being played, where they are in it, their rank, story
    roles and their name before and after the plan (ops: plan_cats' renames, which win over the plan's
    text changes). The game being played comes first, your cat first in each.

    Also: how a rename in the plan works out for it ("how", one of HOWS, or None with no rename); whether its
    name now is text a mod gives ("mod_named": an ID with _WCM_ in it, or a key the game's own text doesn't
    have, mod_given); and whether that text is known ("name_known"): when no mod in the plan gives it (that mod
    is off), "name" is made from the IDs (guess_name), and "was" is the IDs themselves, which a cats entry's
    "was" can name it by. "ids": the IDs an older page named such a cat by (Plan.id_name), "" for a cat with a
    name of the game's, so the page finds an entry written that way."""
    renamed = {op["path"]: op["to"] for op in ops}
    out = []
    for cat in cats:
        first, ids = cat["paths"][0], cat["ids"]
        roles = [p.rsplit("/", 1)[-1] for p in cat["paths"] if "/NarrativeRoles/" in p]
        known = plan.known_name(ids)
        raw = ids.get("PrefixNameId", "") + ids.get("SuffixNameId", "")
        out.append({"target": target_of(cat), "slot": cat["slot"], "current": cat["current"], "player": cat["player"],
                    "where": "you" if cat["player"] and cat["current"] else "your cat" if cat["player"] else place(first),
                    "roles": roles, "role": ids.get("Role", "Player" if cat["player"] else ""),
                    "name": plan.current_name(ids), "with_mods": renamed.get(first, plan.display(ids)),
                    "how": plan.cat_how.get(first),
                    "mod_named": "_WCM_" in raw or mod_given(lookup_key(ids), plan.game.text),
                    "name_known": bool(known), "was": known or raw, "ids": plan.id_name(ids)})
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
        self.warnings = []        # sentences, for the build's log and the Names page's "What this does"
        self.notes = []           # [(where, sentence)]: each warning with the part of names.json it's about
        #                           ("cats.player", "prefixes.rename.Otter"), so a page can put it by its row
        self.renames = []         # [(target, how)] for cats in the save, resolved by plan_cats
        self.cat_renames = []     # [(name before, name after)] per renamed cat, filled by plan_cats
        self.rename_targets = []  # the cats key behind each of cat_renames
        self.cat_how = {}         # a cat's first path -> how its rename works out (HOWS), filled by plan_cats
        self.names_hits = {}      # a "names" entry -> {"cats": [...], "elsewhere": [...]}: what it renames, in words
        self.changed = 0          # names changed or added: parts, rogue names and "names" entries that found something
        # Copies, weights included: GameNames is read once and shared (the studio previews many plans).
        self.prefixes = [dict(p, final=p["text"], weights=dict(p["weights"])) for p in game.prefixes]
        self.suffixes = [dict(s, final=s["text"], weights=dict(s["weights"])) for s in game.suffixes]
        self.final = dict(game.text)   # English key -> text after this plan
        self.added_keys = {}           # key -> English text, added to every language
        self._plan()

    # ---- helpers ----
    def _warn(self, where, text):
        if (where, text) in self.notes:   # a cats entry is looked at for its texts and again for each cat
            return
        self.notes.append((where, text))
        self.warnings.append(text)

    def _edit(self, table, row=None, cells=None, add=None, remove=None):
        e = self.edits.setdefault(table, {})
        if remove is not None:
            e.setdefault("-", []).append(remove)
        if add is not None:
            e.setdefault("+", []).append(add)
        if cells:
            e.setdefault(row, {}).update(cells)

    def _find(self, items, name, where, missing):
        """The parts called `name` (text, any case, or ID); none, and `missing` is said about `where`."""
        low = name.lower()
        hits = [x for x in items if x["text"].lower() == low or x["id"].lower() == low]
        if not hits:
            self._warn(where, missing)
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
            given = [k for k in _ENTRY_KINDS if how.get(k)]
            if len(given) > 1:   # a hand-written entry: _new_ids takes the first of them
                said = [f"a {_ENTRY_KINDS[k]} ('{how[k]}')" for k in given]
                self._warn(f"cats.{target}", f"The rename of {describe_target(target)} gives "
                                             f"{', '.join(said[:-1])} and {said[-1]}; only the {_ENTRY_KINDS[given[0]]} "
                                             "is used")
            self._custom_texts(how, target)
        for old, new in sp.get("names", {}).items():
            keys = [k for k, v in self.final.items() if v == old]
            if not keys:
                self._warn(f"names.{old}", f"Nothing in the game is called '{old}'")
            else:
                self.changed += 1
            hits = {"cats": [], "elsewhere": []}
            for k in keys:
                said = text_label(k, old)
                group = hits["cats" if is_name_key(k) else "elsewhere"]
                if said not in group:
                    group.append(said)
            self.names_hits[old] = hits
            for k in keys:
                self._set_text(k, str(new))
        for key, text in sp.get("text", {}).items():
            if key not in self.final:
                self._warn(f"text.{key}", f"The game had no text called {key}, so it's added, as '{text}'")
            self._set_text(key, str(text))
        self._finish_strings()

    def _plan_affixes(self, kind, items, table, looks, text_col, looks_col, weight_cols, weight_key, id_base, spec):
        noun, col_noun = kind[:-2], ("clan" if kind == "prefixes" else "rank")
        removed = set()
        for old, new in spec.get("rename", {}).items():
            hits = self._find(items, old, f"{kind}.rename.{old}",
                              f"There's no {noun} called '{old}' in the game, so nothing is renamed")
            self.changed += bool(hits)
            for x in hits:
                x["final"] = str(new)
                self._edit(table, x["row"], {text_col: str(new)})
                if self._looks_row(looks, x["row"], x["text"]):
                    self._edit(looks, x["row"], {looks_col: str(new)})
        said = set()
        for x in items:   # a rename onto another part's text: two parts the game can't tell apart by name
            if x["final"] == x["text"] or x["final"].lower() in said:
                continue
            if any(y is not x and y["final"].lower() == x["final"].lower() and y["text"].lower() != x["text"].lower()
                   for y in items):
                said.add(x["final"].lower())
                self._warn(f"{kind}.rename.{x['text']}",
                           f"'{x['text']}' renamed to '{x['final']}' would give two {kind} called {x['final']}")
        for name, weights in spec.get("weights", {}).items():
            for x in self._find(items, name, f"{kind}.weights.{name}",
                                f"There's no {noun} called '{name}' in the game, so how often it's used doesn't change"):
                for c in weights:
                    if c not in weight_cols:
                        self._warn(f"{kind}.weights.{name}", f"How often '{name}' is used: '{c}' isn't a {col_noun} "
                                                             f"(the {col_noun}s are {', '.join(weight_cols)})")
                cells = {c: float(v) for c, v in weights.items() if c in weight_cols}
                x["weights"].update(cells)
                self._edit(table, x["row"], cells)
        for name in spec.get("remove", []):
            for x in self._find(items, name, f"{kind}.remove.{name}",
                                f"There's no {noun} called '{name}' in the game, so there's nothing to remove"):
                if kind == "suffixes" and not self._can_remove_suffix(x, removed):
                    continue
                removed.add(x["id"])
                self._edit(table, remove=x["row"])
                if self._looks_row(looks, x["row"], x["text"]):
                    self._edit(looks, remove=x["row"])
        for name, opts in spec.get("add", {}).items():
            opts = opts if isinstance(opts, dict) else {}
            where = f"{kind}.add.{name}"
            if any(x["final"].lower() == name.lower() for x in items):
                self._warn(where, f"'{name}' is already a {noun}, so it isn't added again")
                continue
            like = None
            if opts.get("like"):
                hits = self._find(items, opts["like"], where, f"'{name}' is used like an average {noun}: there's no "
                                                              f"{noun} called '{opts['like']}' to copy")
                like = hits[0] if hits else None
            weights = dict(like["weights"]) if like else {c: _average(items, c) for c in weight_cols}
            if kind == "suffixes" and not like:
                weights.update(Kit=0.0, Apprentice=0.0, Leader=0.0)   # those ranks have their own suffixes
            weights.update({c: float(v) for c, v in opts.get(weight_key, {}).items() if c in weight_cols})
            new_id = id_base + slug(name)
            clash = [x for x in items if x["id"] == new_id]
            if clash:
                self._warn(where, f"'{name}' isn't added: inside the game it would have the same name as "
                                  f"'{clash[0]['text']}'")
                continue
            row = self._next_row(table)
            self._edit(table, add={"#": row, text_col: name, **weights,
                                   ("Preffix_ID" if kind == "prefixes" else "Suffix_ID"): new_id})
            look = self._looks_cells(looks, like["row"] if like else None, opts.get("looks", {}), where, name)
            look_key = self.game.tables[looks].header[0]
            self._edit(looks, add={look_key: self._next_row(looks), looks_col: name, **look})
            items.append({"row": row, "text": name, "final": name, "id": new_id, "weights": weights, "new": True})
            self.changed += 1
        if kind == "prefixes":
            for clan in CLANS[:4]:
                if not any(x["weights"].get(clan, 0) > 0 for x in items if x["id"] not in removed):
                    self._warn("prefixes.remove", f"No prefix is left for {clan}, so the game would have none to "
                                                  "give its cats")

    def _looks_row(self, looks, row, text):
        t = self.game.tables[looks]
        hit = t.find_rows(row)
        return bool(hit) and len(hit[0].fields) > 1 and hit[0].fields[1].lower() == text.lower()

    def _looks_cells(self, looks, like_row, overrides, where="", name=""):
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
                self._warn(where, f"'{name}' on the name screen: '{c}' isn't one of the looks names are matched to")
        return cells

    def _can_remove_suffix(self, x, removed):
        for rank in RANKS:
            if x["weights"].get(rank, 0) > 0 and not any(
                    s is not x and s["id"] not in removed and s["weights"].get(rank, 0) > 0 for s in self.suffixes):
                self._warn(f"suffixes.remove.{x['text']}",
                           f"'{x['text']}' is the only suffix for {RANK_WORDS.get(rank, rank)}, so it's kept")
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
                self._warn(f"rogues.rename.{old}", f"There's no rogue or loner called '{old}', so nothing is renamed")
            self.changed += bool(hits)
            for r in hits:
                r["final"] = str(new)
                self._set_text(r["id"], str(new))
                self._edit(ROGUES, r["row"], {"Name": str(new)})
        for name in spec.get("remove", []):
            hits = [r for r in rogues if name.lower() in (r["final"].lower(), r["label"].lower(), r["id"].lower())]
            if not hits:
                self._warn(f"rogues.remove.{name}",
                           f"There's no rogue or loner called '{name}', so there's nothing to remove")
            for r in hits:
                self._edit(ROGUES, remove=r["row"])
        for name in spec.get("add", []):
            where = f"rogues.add.{name}"
            if any(r["final"].lower() == str(name).lower() for r in rogues):
                self._warn(where, f"'{name}' is already a rogue or loner name, so it isn't added again")
                continue
            rid = ROGUE_BASE + slug(str(name))
            clash = [r for r in rogues if r["id"] == rid]
            if clash:
                self._warn(where, f"'{name}' isn't added: inside the game it would have the same name as "
                                  f"'{clash[0]['final']}'")
                continue
            self._edit(ROGUES, add={"#": self._next_row(ROGUES), "Name": str(name), "PrefixID": rid})
            self._set_text(rid, str(name))
            rogues.append({"row": None, "label": name, "id": rid, "text": name, "final": name})
            self.changed += 1
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
                self._warn(f"banned.remove.{name}", f"'{name}' isn't on the ban list")
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
                self._warn(f"banned.add.{name}", f"'{name}' can't be banned: it isn't a prefix + suffix the game "
                                                 "can make")
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
        lists (from, to) per cat, self.rename_targets the cats key behind each, and self.cat_how how each
        cat's rename works out (HOWS), by its first path. A cat that already has its new name needs nothing.
        A rename the game would have no text for is left out, with a warning: the cat keeps its name rather
        than showing as <MISSING STRING TABLE ENTRY>. A cat two entries mean (an older page's entry by its IDs
        and a newer one by its name, say) is renamed by the last of them, as the Names page shows it, and the
        earlier one is said to be left out."""
        ops, self.cat_renames, self.rename_targets, self.cat_how = [], [], [], {}
        more_texts = False
        found = [(target, how, self._targets(target, how, cats)) for target, how in self.renames]
        last = {}   # a cat's first path -> the last entry that renames it to something
        for i, (_, how, hits) in enumerate(found):
            for cat in hits if _new_name(how) else ():
                last[cat["paths"][0]] = i
        for i, (target, how, hits) in enumerate(found):
            where = f"cats.{target}"
            later = [c for c in hits if last.get(c["paths"][0], i) != i]
            for cat in later:
                self._warn(where, f"{self.current_name(cat['ids'])} is renamed twice; only the later rename, to "
                                  f"'{_new_name(found[last[cat['paths'][0]]][1])}', is used")
            hits = [c for c in hits if last.get(c["paths"][0], i) == i]
            if later and not hits:
                continue
            if not hits:
                if not any(self._has(c, how) for c in cats):
                    self._warn(where, self._not_found(target, how, cats))
                continue
            if len(hits) > 1 and not by_place(target):
                self._warn(where, f"{len(hits)} cats in your save are called '{_parse_target(target)[1]}', and all "
                                  "of them are renamed; pick the one you mean from the list, where it's renamed by "
                                  "its place")
            for cat in hits:
                ids, first = cat["ids"], cat["paths"][0]
                fields = self._new_ids(how, ids, target)
                if not fields:
                    continue
                key = lookup_key({**ids, **fields})
                if key not in self.final:
                    more_texts |= self._text_for_kept_suffix(how, fields, ids, key)
                if key not in self.final:
                    self.cat_how[first] = "none"
                    self._warn(where, f"{_cap(describe_target(target))} would have no text in the game as "
                                      f"'{_new_name(how)}', so it keeps its name; pick a name the game has, or a "
                                      "name of your own")
                    continue
                self.cat_how[first] = self._outcome(how, fields)
                if self._has(cat, how):
                    continue
                expect = {k: v for k, v in ids.items() if k in ("PrefixNameId", "SuffixNameId")}
                before, after = self.current_name(ids), self.final[key]
                self.cat_renames.append((before, after))
                self.rename_targets.append(target)
                for path in cat["paths"]:
                    ops.append({"op": "name", "path": path, "set": fields, "expect": expect,
                                "from": before, "to": after, "where": _where(path, cat["current"])})
        if more_texts:
            self._finish_strings()   # the build hands self.edits to the pak after plan_cats
        return ops

    def _not_found(self, target, how, cats):
        """Why a cats entry found no cat, in words."""
        slot, want = _parse_target(target)
        game = game_words(slot) if slot is not None else "your save"
        if not want:
            return f"'{target}' doesn't say which cat"
        if want.lower() == "player":
            return f"Your cat isn't in {game} yet"
        if "/" in want:
            if how.get("was") and self._targets(target, {}, cats):
                return (f"{_cap(describe_target(target))} isn't called '{how['was']}' any more, so it isn't renamed; "
                        "rename it again from the list")
            return f"There's no cat at {' · '.join(p for p in want.split('/') if p)} in {game}"
        return f"No cat in {game} is called '{want}'"

    def _outcome(self, how, fields):
        """How a cats entry's new IDs work (one of HOWS but "none")."""
        pid = fields.get("PrefixNameId", "")
        if how.get("name"):
            return "rogue" if pid.startswith("STR_ROGUE_CAT_NAME") else "parts" if "SuffixNameId" in fields else "fixed"
        if how.get("prefix"):
            return "own-prefix" if pid.startswith(OWN_BASE) else "prefix"
        return "fixed"

    def _text_for_kept_suffix(self, how, fields, ids, key):
        """A fixed name, or a prefix of the cat's own, on a cat that keeps a suffix the tables don't have (a part
        from a mod that's off): the text under that exact key, since the texts _custom_texts adds are for the
        suffixes the tables have. True when one was added."""
        suffix = ids.get("SuffixNameId", "")
        pid = fields.get("PrefixNameId", "")
        if not suffix or "SuffixNameId" in fields or not pid.startswith(OWN_BASE):
            return False
        if pid.startswith(FIXED_BASE):
            text = str(how.get("fixed") or how.get("name"))
        elif how.get("prefix"):
            text = str(how["prefix"]) + _suffix_words(suffix, self)
        else:
            return False
        self._set_text(key, text)
        return True

    def _has(self, cat, how):
        fields = self._new_ids(how, cat["ids"], None)
        return bool(fields) and all(cat["ids"].get(k, "") == v for k, v in fields.items())

    def display(self, ids, final=True):
        """The name a cat shows. A kit or apprentice whose save text leaves out the suffix shows its rank's.
        Falls back to the prefix's own text, for naming a cat (a rogue's name is its prefix alone); whether the
        game has the cat's text is lookup_key's question, not this one's."""
        text = self.final if final else self.game.text
        return text.get(lookup_key(ids)) or text.get(ids.get("PrefixNameId", ""), "")

    def known_name(self, ids):
        """The name a cat has now when there's text for it: the game's own, else what a names mod in this plan
        gives it (a cat renamed by an earlier install). "" when neither has it (named by a mod that's off)."""
        return self.display(ids, final=False) or self.display(ids)

    def current_name(self, ids):
        """The name a cat has now: known_name, else one made from its IDs (guess_name: renamed by a mod that's off
        now), else the IDs themselves."""
        return (self.known_name(ids) or guess_name(ids, self)
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

    def cats_called(self, target, cats):
        """The cats a cats key means ("player", a name or a place, a slot first for another game), as a
        names.json "cats" entry finds them: for cats.json's other cats."""
        return self._targets(target, {}, cats)

    def _called(self, cat, name):
        """Whether a cat goes by `name`: the name it shows, with this plan or the game alone; the name a mod
        that's off gave it (guess_name, which its IDs say); or its IDs (id_name), as an older page named a cat
        whose name had no text. Never the prefix ID alone for a cat with a suffix: STR_CAT_NAME53, which an
        older page wrote for a rogue given the prefix Otter, isn't Otterheart."""
        ids, low = cat["ids"], name.lower()
        said = {self.display(ids).lower(), self.display(ids, final=False).lower(), guess_name(ids, self).lower(),
                self.id_name(ids).lower()}
        return low in said - {""}

    def id_name(self, ids):
        """A cat's IDs as an older Names page named a cat the game's own text has no name for (one a mod named):
        its prefix ID and suffix ID as the save has them (STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART, or STR_CAT_NAME53
        for a rogue given the prefix Otter). "" for a cat with a name of the game's: such a cat was always named
        by its name."""
        return "" if self.display(ids, final=False) else ids.get("PrefixNameId", "") + ids.get("SuffixNameId", "")

    def _new_ids(self, how, ids, target):
        """The name IDs a cats entry gives this cat. The texts they need come from _custom_texts. A rogue
        name is the rogue's own ID only for a rogue or loner; on a clan cat it's a fixed name."""
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
            self._warn(f"cats.{target}", f"Nothing to rename {describe_target(target)} to: give it a new name")
        return None

    def _custom_texts(self, how, target):
        """Texts for names no table has: a cat's own prefix (it grows with rank), or a fixed name (also
        what a whole name that isn't a prefix + suffix becomes, a rogue name included: on a clan cat it's a
        fixed name, and _new_ids gives the rogue's own ID only to a rogue or loner). One of the game's prefixes
        gets a text under its ID alone, for a rogue or loner, who has no suffix."""
        fixed = how.get("fixed")
        if how.get("name"):
            name = str(how["name"])
            if self.split(name):
                return
            fixed = name
        elif how.get("prefix"):
            name = str(how["prefix"])
            known = [p for p in self.prefixes if p["final"].lower() == name.lower()]
            if known:
                self._set_text(known[0]["id"], known[0]["final"])   # a rogue or loner shows it with no suffix
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
            self._warn(f"cats.{target}", f"Nothing to rename {describe_target(target)} to: give it a new name")


_RANK_SUFFIX = {"Kit": "_KIT", "Apprentice": "_PAW"}
_ROLE = re.compile(r"[(,]Role=(\w+)")


def _norm(how):
    """A cats entry as a dict: a plain string is a whole name."""
    if isinstance(how, str):
        return {"name": how}
    return how if isinstance(how, dict) else {}


def _new_name(how):
    """The name a cats entry asks for, for a sentence."""
    return str(how.get("name") or how.get("prefix") or how.get("fixed") or "")


# The kinds of name a cats entry can give, in the order _new_ids takes them, in words.
_ENTRY_KINDS = {"name": "name", "prefix": "prefix", "fixed": "fixed name"}


def _own_prefix_id(name):
    return OWN_BASE + slug(str(name))   # a prefix only that cat has: not in the tables


def _fixed_id(name):
    return FIXED_BASE + slug(str(name))   # the same text whatever the suffix


def lookup_key(ids):
    """The text key the game shows a cat's name from: its prefix ID and suffix ID; a kit's or apprentice's rank
    suffix when its save text leaves the suffix out; the prefix ID alone for a cat with no suffix (a rogue or
    loner)."""
    return ids.get("PrefixNameId", "") + (ids.get("SuffixNameId") or _RANK_SUFFIX.get(ids.get("Role", ""), ""))


def _words(slugged):
    """A name back from its slug, as near as it goes: SPARKLE is Sparkle, MIST_STAR is Mist Star."""
    return " ".join(w.capitalize() for w in slugged.split("_") if w)


def _suffix_words(suffix, plan=None):
    """A suffix ID's text: the plan's, when its tables have it; else from the ID (_HEART is heart, _WCM_GONE
    gone, as wcmods makes a mod's suffix IDs from their text)."""
    if not suffix:
        return ""
    if plan is not None:
        hit = next((s["final"] for s in plan.suffixes if s["id"] == suffix), None)
        if hit is not None:
            return hit
    return suffix.rsplit("_WCM_", 1)[-1].strip("_").replace("_", " ").lower()


def guess_name(ids, plan=None):
    """A cat's name made from its IDs, for a cat whose name is text only a mod gives while that mod is off:
    wcmods makes those IDs from the name (STR_CAT_NAME_WCM_FIXED_SPARKLE is Sparkle, STR_CAT_NAME_WCM_GLIMMER
    with _PAW is Glimmerpaw). The game's own parts come from plan's tables when there is one. "" when the IDs
    say nothing readable."""
    prefix = ids.get("PrefixNameId", "")
    suffix = ids.get("SuffixNameId") or _RANK_SUFFIX.get(ids.get("Role", ""), "")
    if prefix.startswith(FIXED_BASE):
        return _words(prefix[len(FIXED_BASE):])
    if prefix.startswith(ROGUE_BASE):
        return _words(prefix[len(ROGUE_BASE):])
    if prefix.startswith(OWN_BASE):
        first = _words(prefix[len(OWN_BASE):])
    elif plan is not None:
        first = next((p["final"] for p in plan.prefixes if p["id"] == prefix), "")
    else:
        first = ""
    return first + _suffix_words(suffix, plan) if first else ""


def name_before(ids, specs):
    """The name a cat had before a names.json gave it a name of its own, as that file says: the cats key it was
    renamed by (Wrenheart in {"Wrenheart": {"fixed": "Sparkle"}}), or the entry's "was" for one renamed by its
    place. specs: names.json files, any mod's, on or off; the last that says wins. "" when none says."""
    prefix, found = ids.get("PrefixNameId", ""), ""
    for spec in specs:
        for target, how in (spec.get("cats") or {}).items():
            how = _norm(how)
            text = how.get("prefix") or how.get("fixed") or how.get("name")
            if not text or prefix not in (_fixed_id(text), _own_prefix_id(text)):
                continue
            want = _parse_target(target)[1]
            before = how.get("was") if "/" in want else ("" if want.lower() == "player" else want)
            if isinstance(before, str) and before and not before.startswith("STR_"):
                found = before
    return found


def is_name_key(key):
    """Whether a text key is a cat's name: a clan cat's prefix + suffix, a cameo cat's or a name a mod made
    (STR_CAT_NAME...), or a rogue's (STR_ROGUE_CAT_NAME...)."""
    return key.startswith(("STR_CAT_NAME", "STR_ROGUE_CAT_NAME"))


# What a text key's family is, in words, for what a "names" entry also renames ("the material Rock").
_KEY_WORDS = (("STR_CAT_NAME_ICONIC_", "the cameo cat {}"), ("STR_ROGUE_CAT_NAME", "the rogue name {}"),
              ("STR_CAT_NAME", "the cat name {}"), ("STR_CRAFT_MATERIAL_NAME", "the material {}"),
              ("STR_CHAR_NAME_", "the animal {}"), ("QST_", "a line in a quest"))


def text_label(key, text):
    """A text the game shows, in words, by its key's family: "the material Rock", "the animal Fox"."""
    for start, words in _KEY_WORDS:
        if key.startswith(start):
            return words.format(text)
    return f"other text that says {text}"


def _average(items, col):
    vals = [x["weights"].get(col, 0) for x in items if x["weights"].get(col, 0) > 0]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def cats_in_save(data):
    """Every named cat in a save's account data: [{"paths": [...], "ids": {"PrefixNameId", "SuffixNameId",
    "Role"}, "slot": "1", "player": bool, "current": bool}]. A save holds a game per cat slot started; the
    one being played (current_slot) comes first, then the others by number, your cat first in each. A
    story role (NPCData/NarrativeRoles) holds a copy of a clan or outsider cat's text; copies are one
    cat, listed under all their paths, so a rename reaches every place the game reads it from. Two cats of
    their own with the very same text (twins, as far as the save says) stay two cats; a story role with
    their text goes with the first."""
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
        own = [p for p in paths if "/NarrativeRoles/" not in p]
        groups = [[p] for p in own] or [[]]
        groups[0] += [p for p in paths if "/NarrativeRoles/" in p]
        for group in groups:
            cats.append({"paths": group, "ids": dict(ids), "slot": slot, "player": is_player(group[0]),
                         "current": slot == current})
    # The game being played first, then your cat, the clans, and last the cats that are only story roles.
    cats.sort(key=lambda c: (not c["current"], _slot_order(c["slot"]), not c["player"],
                             "/NarrativeRoles/" in c["paths"][0], c["paths"][0]))
    return cats


def _where(path, current=True):
    """A cat's path for people: "you" for your cat, else its place, with the slot first when the cat is
    in a game other than the one being played."""
    where = "you" if is_player(path) else place(path)
    return where if current else f"{path.split('/', 1)[0]}/{'player' if is_player(path) else where}"


_GAME_PREFIX_ID = re.compile(r"^STR_CAT_NAME\d+$")   # one of the game's prefix IDs, alone


def mod_given(key, game_text=None):
    """Whether the text under a cat's name key (lookup_key) is only ever a mod's: an ID wcmods made (_WCM_ in
    it), or a key the game's own text (game_text: GameNames.text, or a set of its keys) doesn't have, such as
    one of the game's prefix IDs alone, which a rogue or loner given that prefix has (the mod adds its text).
    Without game_text the IDs say: _WCM_, or a game prefix's ID alone."""
    if not key:
        return False
    if "_WCM_" in key:
        return True
    return key not in game_text if game_text is not None else bool(_GAME_PREFIX_ID.match(key))


def named_keys(cats, ops=()):
    """[(cat, its IDs after the renames in ops, the key the game looks its name up by)], in cats' order."""
    renamed = {op["path"]: op["set"] for op in ops if op.get("op") == "name"}
    out = []
    for cat in cats:
        ids = {**cat["ids"], **renamed.get(cat["paths"][0], {})}
        out.append((cat, ids, lookup_key(ids)))
    return out


def losing_text(cats, ops, has_text, game_text=None):
    """Cats whose name is text only a mod gives (mod_given, with the game's own text when there's game_text; after
    the renames in ops: save ops as the build makes them) that has_text(key) says the game won't have. The save
    keeps those IDs whether or not the mod is still on, so the game shows <MISSING STRING TABLE ENTRY>.
    [(cat, its IDs after ops, key)], in cats' order; the key is the one the game looks up (lookup_key)."""
    return [(cat, ids, key) for cat, ids, key in named_keys(cats, ops)
            if mod_given(key, game_text) and not has_text(key)]


def without_text(cats, ops, has_text, game_text=None):
    """losing_text as [(where, key)], where being "you" for your cat or the cat's place."""
    return [(_where(cat["paths"][0], cat["current"]), key)
            for cat, _, key in losing_text(cats, ops, has_text, game_text)]


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
