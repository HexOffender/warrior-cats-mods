"""A tiny game for the names tests: the six name tables and the text tables as CSV text, with a few rows
each (tests/unit/test_names.py, test_studio_names.py), and cats' save texts. No game needed."""
import re

from wcmods import names

# The six name tables, as the game lays them out, with a few rows each.
PREFIXES = """#,Preffix,ThunderClan,RiverClan,ShadowClan,WindClan,OutOfClans,Preffix_ID
1,Wood,0.04,0,0,0,0.02,STR_CAT_NAME1
2,Ember,0.05,0.01,0.02,0.03,0,STR_CAT_NAME2
3,Otter,0,0.05,0.02,0.01,0,STR_CAT_NAME53
4,Wren,0.02,0.02,0.02,0.02,0,STR_CAT_NAME60
5,Pigeon,0.01,0.01,0.01,0.01,0,STR_CAT_NAME70
"""
PREFIX_LOOKS = """---,Prefix,ThunderClan,RiverClan,ShadowClan,WindClan,Body_1,Fur_1
1,Wood,27,1,2,1,0,1
2,Ember,2,0,27,1,1,1
3,Otter,1,27,1,1,0,2
4,Wren,1,1,1,1,2,0
5,Pigeon,1,1,1,1,0,0
"""
RANK_HEAD = "Kit,Apprentice,Warrior,Deputy,Leader,MedicineCat,Queen,Elder,RogueCat,RogueCatLeader,StarClanAncestor"
SUFFIXES = f"""#,Suffix,{RANK_HEAD},Suffix_ID
1,kit,1,0,0,0,0,0,0,0,0,0,0,_KIT
2,paw,0,1,0,0,0,0,0,0,0,0,0,_PAW
3,heart,0,0,0.1,0.1,0,0.1,0.1,0.1,0.1,0.1,0.05,_HEART
4,star,0,0,0,0,1,0,0,0,0,0,0,_STAR
5,pelt,0,0,0.1,0.1,0,0.1,0.1,0.1,0.1,0.1,0.05,_PELT
"""
SUFFIX_LOOKS = """---,Suffix,ThunderClan,RiverClan,ShadowClan,WindClan,Brave,Body_1
1,kit,0,0,0,0,0,0
2,paw,0,0,0,0,0,0
3,heart,1,1,1,1,2,1
4,star,0,0,0,0,0,0
5,pelt,1,2,1,1,1,1
"""
ROGUES = """#,Name,PrefixID
1,Woody,STR_ROGUE_CAT_NAME_1
2,Fury,STR_ROGUE_CAT_NAME_5
3,Fox,STR_ROGUE_CAT_NAME_10
4,Storm,STR_ROGUE_CAT_NAME_16
"""
BANNED = """#,Name,PrefixID,SuffixID
1,Woodstar,STR_CAT_NAME1,_STAR
"""
PARTS = {"STR_CAT_NAME1": "Wood", "STR_CAT_NAME2": "Ember", "STR_CAT_NAME53": "Otter", "STR_CAT_NAME60": "Wren",
         "STR_CAT_NAME70": "Pigeon"}
ENDS = {"_KIT": "kit", "_PAW": "paw", "_HEART": "heart", "_STAR": "star", "_PELT": "pelt"}
OTHER = {"STR_ROGUE_CAT_NAME_1": "Chesnut", "STR_ROGUE_CAT_NAME_5": "Fury", "STR_ROGUE_CAT_NAME_10": "Fox",
         "STR_ROGUE_CAT_NAME_16": "Storm", "STR_CAT_NAME_ICONIC_8": "Rock", "STR_CAT_NAME_ICONIC_1": "Brightheart",
         "STR_CRAFT_MATERIAL_NAME_20": "Rock", "STR_CHAR_NAME_FOX": "Fox", "QST_Story.Rock.1": "Rock",
         "STR_BOT_NAME_1": "Someone"}


def strings(lang="EN"):
    """Strings_<lang>.csv: every prefix + suffix but Ember + pelt (left out on purpose, as the game leaves out
    Black + face), the rogues and a few other texts. Other languages translate the clan names."""
    rows = ["Key,SourceString"]
    for pid, p in PARTS.items():
        for sid, s in ENDS.items():
            if (pid, sid) != ("STR_CAT_NAME2", "_PELT"):
                rows.append(f"{pid}{sid},{p}{s}" + ("" if lang == "EN" else f" ({lang})"))
    rows += [f"{k},{v}" for k, v in OTHER.items()]
    return "\r\n".join(rows) + "\r\n"


TABLES = {names.PREFIXES: PREFIXES, names.PREFIX_LOOKS: PREFIX_LOOKS, names.SUFFIXES: SUFFIXES,
          names.SUFFIX_LOOKS: SUFFIX_LOOKS, names.ROGUES: ROGUES, names.BANNED: BANNED}


def tiny_game():
    """The game's names (names.GameNames) from the tables above."""
    def read(path):
        if path in TABLES:
            return TABLES[path]
        lang = re.search(r"Strings_(\w+)\.csv$", path).group(1)
        return strings(lang)
    return names.GameNames(read)


def cat(role, prefix, suffix=None, extra=""):
    """A cat's save text, as the game writes it; suffix None leaves the field out (a rogue, or an apprentice)."""
    end = "" if suffix is None else f',SuffixNameId="{suffix}"'
    return f'(ClanType=RiverClan,Role={role},PrefixNameId="{prefix}"{end}{extra})'


def save(player=None, warriors=(), outsiders=(), roles=None, slot="0"):
    """A save's account data: one game, your cat, the RiverClan warriors, the outsiders and the story roles."""
    game = {"NPCData": {"RiverClan": {"Warrior": list(warriors)}}}
    if player:
        game["GameplayProgression"] = {"Gameplay.Combat.Character.Cat.Player": {"Customization": player}}
    if outsiders:
        game["NPCData"]["Outsiders"] = list(outsiders)
    if roles:
        game["NPCData"]["NarrativeRoles"] = dict(roles)
    return {slot: game}
