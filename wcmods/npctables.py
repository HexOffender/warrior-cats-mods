"""The game's tables for making clan cats, for C++ mods (docs/plans/clan-life.md, S6).

The game makes its clan cats from the CSV tables in NonAsset/NPC/: name prefixes weighted per clan
(PreffixName.csv), suffixes weighted by role (SuffixName.csv), the canon names it never hands out (NameBanList.csv),
rogues' whole names, a weight table per clan for each look part and colour (BodyType.csv ... Eye2Color.csv), the
patterns it keeps off its cats, the parts a kit may have (ForcedAppearance.csv), sizes and scar chances by role, how
many of each role each clan's game makes (<Clan>NpcGenerator.csv), and the chance of odd eyes (TuningData's
Gameplay.NPC.Heterochromia.Chance). A mod that makes cats of its own (Clan life) makes them the game's way from these.

build(read_text) reads them as the build leaves them (name mods' changes in), and the install writes the result as
Mods/shared/WCModsGame/npc_tables.json, which the C++ SDK's wcmods::cat_tables() reads. Options are numbered as the
game's cat maker numbers them, from 0 (a table's first weight is option 0's).
"""
import re

from .formats.csvdata import Table

NPC = "Wrc/Content/Gameplay/DataTables/NonAsset/NPC/"
TUNING = "Wrc/Content/Gameplay/DataTables/NonAsset/TuningData.csv"
CLANS = ("ThunderClan", "RiverClan", "ShadowClan", "WindClan", "OutOfClans")
ROLES = ("Kit", "Apprentice", "Warrior", "Deputy", "Leader", "MedicineCat", "Queen", "Elder", "RogueCat",
         "RogueCatLeader", "StarClanAncestor")
# Each look part's table, by the names the C++ SDK's NpcSpec uses for parts (and the colour slots' own).
LOOKS = {"body": "BodyType", "face": "FaceType", "ears": "EarType", "eyes": "EyeType", "tail": "TailType",
         "whiskers": "WhiskerType", "fur": "FurType", "pattern": "PatternType", "marking": "MarkingType",
         "coat": "FurBaseColor", "pattern_colour": "FurPattern1Color", "marking_colour": "FurPattern2Color",
         "eye_colour": "Eye1Color", "eye_colour2": "Eye2Color"}
# ForcedAppearance.csv's columns, by the same names.
KIT_COLUMNS = {"Body": "body", "Fur": "fur", "Eye": "eyes", "Ear": "ears", "Whisker": "whiskers", "Tail": "tail",
               "Face": "face"}
GENERATORS = ("ThunderClan", "ShadowClan", "RiverClan", "WindClan")
ODD_EYES = "Gameplay.NPC.Heterochromia.Chance"


def _num(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def _ints(s):
    """'(6,7,8,9)' -> [6, 7, 8, 9]."""
    return [int(n) for n in re.findall(r"-?\d+", s or "")]


def _numbers(s):
    """'(0.10, 0.20, ...)' -> [0.1, 0.2, ...]."""
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", s or "")]


def _col(table, name):
    """A column's index by its name, or None when the table hasn't got it (Table.column raises)."""
    try:
        return table.column(name)
    except KeyError:
        return None


def _rows(table, *cols):
    """Each row's cells under these columns (by name; "" for a column the table hasn't got, or a short row), for rows
    with a first cell."""
    idx = [_col(table, c) for c in cols]
    return [[r.fields[i] if i is not None and 0 <= i < len(r.fields) else "" for i in idx]
            for r in table.rows if r.fields and r.fields[0]]


def build(read_text):
    """The tables as one dict (the JSON written for C++ mods). read_text(path) gives a game file's text by its
    path under the game's content (Wrc/Content/...), as the build leaves it. A table the game hasn't got is left
    empty (and named in "missing")."""
    out = {"clans": list(CLANS), "roles": list(ROLES), "prefixes": [], "suffixes": [], "banned": [], "rogues": [],
           "looks": {}, "banned_patterns": [], "kit_parts": {}, "sizes": {}, "scars": [], "generators": {},
           "odd_eyes": 0.15, "missing": []}

    def table(name):
        try:
            return Table(read_text(NPC + name))
        except Exception as e:   # the game hasn't got it (an update renamed it), or it doesn't read: left out, and why
            out["missing"].append(name)
            out.setdefault("problems", {})[name] = f"{type(e).__name__}: {e}"
            return None

    if (t := table("PreffixName.csv")) is not None:
        for _, word, *w, pid in _rows(t, "#", "Preffix", *CLANS, "Preffix_ID"):
            out["prefixes"].append({"word": word, "id": pid, "weights": dict(zip(CLANS, map(_num, w)))})
    if (t := table("SuffixName.csv")) is not None:
        for _, word, *w, sid in _rows(t, "#", "Suffix", *ROLES, "Suffix_ID"):
            out["suffixes"].append({"word": word, "id": sid, "weights": dict(zip(ROLES, map(_num, w)))})
    if (t := table("NameBanList.csv")) is not None:
        out["banned"] = [{"name": n, "prefix": p, "suffix": s} for _, n, p, s in _rows(t, "#", "Name", "PrefixID", "SuffixID")]
    if (t := table("RogueNames.csv")) is not None:
        out["rogues"] = [{"word": n, "id": rid} for _, n, rid in _rows(t, "#", "Name", "PrefixID")]
    for part, name in LOOKS.items():
        if (t := table(name + ".csv")) is not None:
            out["looks"][part] = {clan: _numbers(values) for clan, values in _rows(t, "Clan", "Values") if clan in CLANS}
    if (t := table("PatternBanList.csv")) is not None:
        out["banned_patterns"] = sorted({int(_num(i, -1)) for _, i in _rows(t, "Name", "Index") if _num(i, -1) >= 0})
    if (t := table("ForcedAppearance.csv")) is not None:
        cols = {c: i for c in KIT_COLUMNS if (i := _col(t, c)) is not None}
        for r in t.rows:
            if r.fields and r.fields[0] == "Kit":   # a short row's missing cells read as no options
                out["kit_parts"] = {KIT_COLUMNS[c]: _ints(r.fields[i] if i < len(r.fields) else "") for c, i in cols.items()}
    if (t := table("CatSize.csv")) is not None:
        out["sizes"] = {role: [_num(lo), _num(hi)] for role, lo, hi in _rows(t, "Role", "MinScale", "MaxScale") if role}
        if not out["sizes"]:   # the first column is unnamed ("--"): the rows by position
            out["sizes"] = {r.fields[1]: [_num(r.fields[2]), _num(r.fields[3])] for r in t.rows if len(r.fields) >= 4}
    if (t := table("Scars.csv")) is not None:
        out["scars"] = [{"role": role, "group": group, "ear": _num(e), "body": _num(b), "eye": _num(y)}
                        for role, group, e, b, y in _rows(t, "Role", "Group", "EarChance", "BodyChance", "EyeChance")]
    for clan in GENERATORS:
        if (t := table(clan + "NpcGenerator.csv")) is not None:
            cols = {c: i for c in CLANS if (i := _col(t, c)) is not None}   # by name: the columns' order differs
            out["generators"][clan] = {r.fields[0]: {c: int(_num(r.fields[i])) for c, i in cols.items() if i < len(r.fields)}
                                       for r in t.rows if r.fields and r.fields[0]}
    try:
        tuning = Table(read_text(TUNING))
        for r in tuning.rows:
            if r.fields and r.fields[0] == ODD_EYES and len(r.fields) > 1:
                out["odd_eyes"] = _num(r.fields[1], 0.15)
    except Exception:
        out["missing"].append("TuningData.csv")
    return out
