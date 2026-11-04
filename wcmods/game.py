"""WCModsGame: the shared UE4SS Lua module for scripting the game itself.

The player's cat (stats, health, stamina, level, traits, looks), items, the fresh-kill pile, time of day,
quests, combat (fighters, moves, statuses, damage), the save's live data, the game's managers and its
developer switches, plus the plumbing scripts need: safe object access, timers, keys, hooks and events.
Installed with every build as ue4ss/Mods/shared/WCModsGame/WCModsGame.lua; docs/scripting.md documents
every call.

Most of the game's own C++ state isn't visible to Lua through reflection (its health, stamina, level
and stat components have no reflected members). Where the reverse-engineering notes found a value's
offset (docs/mechanics/), the module maps it with UE4SS's RegisterCustomProperty, so scripts read and
write it like any other property. Everything else goes through what the game does reflect: its
managers, the combat director, the quest and save managers.
"""
import re

from .lua import source as lua_source

SHARED_NAME = "WCModsGame"

# Members the game doesn't reflect, found by reverse-engineering build 24847281 (docs/mechanics/,
# docs/reverse-engineering.md) and confirmed unchanged on 26184573, patch 1.1 (the level component read in
# game, the rest by signatures.py, which covers the level component too since 2026-10-28), and on 26337109
# (2026-11-03, every one found again by signatures.py, none moved): class, then
# (property name, offset in the object, type). Rendered into
# the Lua as Game.hidden. They're offsets inside objects, so ASLR doesn't move them, but a game update
# that changes a class's layout does: signatures.py finds them again in a new build, and lua() takes the
# offsets it found.
HIDDEN = [
    # Every resource component (health, stamina, combat stamina, level, fresh-kill pile).
    ("/Script/SwtQuest.SwtQuestResourceComponent", [
        ("WCM_ResourceType", 0x108, "IntProperty"), ("WCM_Value", 0x10C, "FloatProperty"),
        ("WCM_Max", 0x110, "FloatProperty"), ("WCM_Scale", 0x114, "FloatProperty")]),
    ("/Script/SwtQuest.SwtQuestStaminaComponent", [("WCM_Regen", 0x11C, "FloatProperty")]),
    # The player state's level component: level, and the cat's stats out of combat. +0x124 is the level
    # cap (Gameplay.Exploration.MaxLevel, read from the code), not a shown level: the name is older.
    ("/Script/SwtAdventure.SwtAdventureLevelComponent", [
        ("WCM_Level", 0x120, "IntProperty"), ("WCM_LevelShown", 0x124, "IntProperty"),
        ("WCM_Prowess", 0x154, "FloatProperty"), ("WCM_Strength", 0x158, "FloatProperty"),
        ("WCM_Resilience", 0x15C, "FloatProperty"), ("WCM_Instinct", 0x160, "FloatProperty"),
        ("WCM_Agility", 0x164, "FloatProperty"), ("WCM_Stamina", 0x168, "FloatProperty")]),
    ("/Script/SwtAdventure.SwtAdventureFreshKillPileComponent", [
        ("WCM_DecayTimer", 0x130, "FloatProperty"), ("WCM_DecayTime", 0x134, "FloatProperty")]),
    ("/Script/SwtAdventure.SwtAdventureGameplayGameState", [("WCM_DayTime", 0x438, "FloatProperty")]),
    # A fighter's combat component (set up when a fight starts). Its team (ESwtAdventureCombatTeam: 1 the
    # player's side, 2 the enemy's), how many moves it has to pick from (the array's data pointer sits at +0x1E0; its elements
    # are AttackMove rows, 0x68 bytes each, which the C++ SDK reads), and the AI's tier for this fight
    # (EAICombatProfile: 1–6, 7 Terrible, 8 Perfect; picked from the range your level sets).
    ("/Script/SwtAdventure.TurnBasedCombatComponent", [
        ("WCM_Stance", 0x1A0, "ByteProperty"), ("WCM_Team", 0x1A1, "ByteProperty"),
        ("WCM_Prowess", 0x1C4, "FloatProperty"), ("WCM_Strength", 0x1C8, "FloatProperty"),
        ("WCM_Resilience", 0x1CC, "FloatProperty"), ("WCM_Instinct", 0x1D0, "FloatProperty"),
        ("WCM_Agility", 0x1D4, "FloatProperty"), ("WCM_Stamina", 0x1D8, "FloatProperty"),
        ("WCM_MoveCount", 0x1E8, "IntProperty"),
        ("WCM_Clan", 0x3D8, "ByteProperty"), ("WCM_Level", 0x3DC, "IntProperty"),
        ("WCM_PresetDamage", 0x3E4, "IntProperty"), ("WCM_AITier", 0x3F8, "IntProperty")]),
    # A cat's or animal's status condition component: the condition it has now (ESwtAdventureStatusType:
    # 0 none, 1 Blinded, 2 Furious, 3 Poisoned, 4 Stressed), how many rounds it has had it (1 when applied;
    # a round's end rolls rounds × SelfCureChance to shake it off), and the tuning the component keeps.
    ("/Script/SwtAdventure.SwtAdventureStatusComponent", [
        ("WCM_Status", 0xE0, "ByteProperty"), ("WCM_StatusRounds", 0x144, "IntProperty"),
        ("WCM_SelfCureChance", 0x148, "FloatProperty"), ("WCM_PoisonDamage", 0x14C, "FloatProperty")]),
    # A roaming animal's senses (its detection component): the TuningData's
    # Gameplay.Exploration.Detection.<size class>.* values, copied in when the animal is made.
    ("/Script/SwtAdventure.SwtAdventureDetectionComponent", [
        ("WCM_ConeAngle", 0x57C, "FloatProperty"), ("WCM_ConeDistance", 0x580, "FloatProperty"),
        ("WCM_PounceDistance", 0x588, "FloatProperty"), ("WCM_SoundRadius", 0x58C, "FloatProperty"),
        ("WCM_SoundSpeed", 0x590, "FloatProperty"), ("WCM_ProximityDistance", 0x594, "FloatProperty"),
        ("WCM_TargetDistance", 0x598, "FloatProperty"), ("WCM_WalkSpeedRoaming", 0x59C, "FloatProperty"),
        ("WCM_WalkSpeedChasing", 0x5A0, "FloatProperty"), ("WCM_ZoneEntryDistance", 0x5A4, "FloatProperty"),
        ("WCM_ZoneExitDistance", 0x5A8, "FloatProperty"), ("WCM_ReactToChase", 0x5AC, "FloatProperty")]),
    # The player state's inventory component: its items, a native TMap<FGameplayTag, int32> (an item's tag to
    # its count; the TSet's elements are 20 bytes: the tag's FName, the count, and the hash's two links), read
    # from its constructor and the code that adds an item (NATIVE). C++ only (wcmods::inventory): UE4SS's
    # RegisterCustomProperty can't describe a map, so the Lua leaves it out (CPP_ONLY).
    ("/Script/SwtQuest.SwtQuestInventoryComponent", [("WCM_Items", 0x150, "MapProperty")]),
    # The tuning manager's TuningData.csv (TMap<FString, a row of {MaxValue float, Description FString}>, 0x38-byte
    # elements), which the game's tuning lookup reads on every call (docs/reverse-engineering.md, "Tuning").
    ("/Script/SwtEngine.SwtTuningManager", [("WCM_TuningData", 0x50, "MapProperty")]),
    # The sky's copy of its presets (TMap<ESkyboxPostProcessEnum, FWrcSkyBoxStruct>, 0x168-byte elements: the preset
    # at +0, its row from +8), made from SkyParamsDB as it starts; what putting a preset on reads.
    ("/Script/Wrc.WrcSkyboxActor", [("WCM_Presets", 0x378, "MapProperty")]),
]

# The kinds in HIDDEN only the C++ SDK reads (offsets.json): the Lua's Game.hidden leaves them out.
CPP_ONLY = {"MapProperty"}

# The game's native functions the C++ SDK calls (wcmods::native, Core.hpp): "class:name", the function's RVA on
# gamebuild.VERIFIED_BUILD, and what it takes. signatures.json keeps a pattern of each one's first instructions
# that's unique in the exe (signatures.make), so another build finds it again (signatures.check); offsets.json
# gives C++ mods its RVA on the installed build with that pattern, which the SDK checks the code against before
# it calls anything. Found on 26337109 (docs/reverse-engineering.md, "Items").
NATIVE = [
    ("SwtQuestInventoryComponent:AddItem", 0x1654430,
     "adds a count of an item to an inventory, or takes it away (a negative count; at 0 the item goes): "
     "(the component, the item's FGameplayTag by value, int32 count, bool show it on the HUD); then tells the "
     "component's listeners (the HUD's OnItemPickedUp) and writes the inventory into the save's state"),
    ("SwtTuningManager:GetValue", 0x12BBA60,
     "a TuningData.csv key's MaxValue, as every tuning read in the game gets it: (const FString* key) -> float, "
     "0 for a key the table hasn't got; reads the tuning manager (a global) and its map, WCM_TuningData"),
]

# The game's enums Game.enums gives scripts: the name scripts use, the enum's path in the game (its module's
# /Script package, from the class dump's `## [Module]` blocks), and its names in order. In game each is read
# from the game's own enum the first time it's used, so a game update that renumbers one is followed; these
# lists, numbered from 0, are the fallback for when that read fails. They're build 26184573's, each the whole
# enum as the exe's enum table has it (`python tools/re/uht.py <exe> lua` checks them against an exe).
ENUMS = [
    ("clan", "/Script/SwtQuest.EClanType", ["None", "ThunderClan", "ShadowClan", "RiverClan", "WindClan", "Total"]),
    ("rank", "/Script/SwtQuest.ECharacterRank", ["None", "Apprentice", "Warrior", "Deputy", "Leader", "Total"]),
    ("trait", "/Script/SwtQuest.ECharacterTrait",
     ["None", "Brave", "Ambitious", "Wise", "Energetic", "Curious", "Patient"]),
    ("stance", "/Script/SwtAdventure.ESwtAdventureCombatStance",
     ["None", "Neutral", "Offensive", "Defensive", "Trick", "Sneaky", "Reckless"]),
    ("status", "/Script/SwtAdventure.ESwtAdventureStatusType", ["None", "Blinded", "Furious", "Poisoned", "Stressed"]),
    ("aiProfile", "/Script/SwtAdventure.EAICombatProfile",
     ["None", "Tier1", "Tier2", "Tier3", "Tier4", "Tier5", "Tier6", "Terrible", "Perfect"]),
    ("team", "/Script/SwtAdventure.ESwtAdventureCombatTeam", ["None", "Player", "Enemy"]),
    ("detectionRange", "/Script/SwtAdventure.EAdventureDetectionRange", ["Tiny", "Small", "Medium", "Large"]),
    ("stat", "/Script/SwtAdventure.ESwtAdventureCombatAttribute",
     ["None", "Prowess", "Strength", "Resilience", "Instinct", "Agility"]),
    ("resource", "/Script/SwtQuest.EQuestResourceType",
     ["Health", "Level", "Stamina", "StaminaCombat", "Currency", "FreshKill", "Count"]),
    ("questStatus", "/Script/SwtQuest.EQuestStatus",
     ["None", "QuestAvailable", "OngoingQuest", "QuestComplete", "QuestTurnedIn", "DialogueProgress"]),
    ("questResult", "/Script/SwtQuest.EQuestResultTypes", ["Any", "Success", "Fail"]),
    ("questType", "/Script/SwtQuest.EQuestType", ["MainQuest", "SideQuest"]),
    ("objectiveStatus", "/Script/SwtQuest.EObjectiveStatus",
     ["NotStarted", "InProgress", "Failed", "FailedTimePressure", "Succeeded"]),
    ("phase", "/Script/SwtQuest.EGamePhase",
     ["None", "PreCinematic", "CinematicIntro", "PreGame", "Game", "PostGame", "TutorialIntro"]),
    ("itemType", "/Script/SwtQuest.EItemType", ["None", "Consumable", "Equipment", "Quest", "Collectible"]),
    ("characterType", "/Script/SwtQuest.ESwtQuestCharacterType",
     ["None", "Cat", "BossCat", "WeakMice", "Mice", "WeakSquirrel", "Squirrel", "WeakRabbit", "Rabbit", "BossRabbit",
      "WeakBird", "Bird", "WeakRat", "Rat", "Snake", "ThreatSnake", "BossSnake", "Badger", "ThreatBadger", "BossBadger",
      "ThreatFox", "TitanFox", "BossFox", "ThreatDog", "TitanDog", "BossDog"]),
]

LUA = lua_source("game.lua")


def hidden(offsets=None):
    """HIDDEN with the offsets for the installed game: `offsets` maps "class:property" to an offset, or to
    None for one a game update moved where it couldn't be found again (left out, so reading it gives
    nil); one it doesn't name is left out too. Without `offsets`, the ones found on build 24847281."""
    out = []
    for cls, fields in HIDDEN:
        kept = []
        for name, offset, kind in fields:
            if offsets is not None:
                offset = offsets.get(f"{cls}:{name}")
            if isinstance(offset, int) and offset > 0:
                kept.append((name, offset, kind))
        if kept:
            out.append((cls, kept))
    return out


def offsets_json(offsets=None, build=None, functions=None):
    """The same members for C++ mods, written beside the module as offsets.json, with the native functions:
    {"game_build", "members": {"class:property": {"offset", "type"}}, "functions": {"class:name": {"rva",
    "pattern"}}}; `offsets` as for hidden(). `functions` maps each of NATIVE's names to its RVA on the installed
    build, or to None for one a game update took where it couldn't be found again (left out, as is one with no
    pattern in signatures.json); without it, NATIVE's own (the verified build's)."""
    from .exe import signatures
    members = {f"{cls}:{name}": {"offset": offset, "type": kind}
               for cls, fields in hidden(offsets) for name, offset, kind in fields}
    try:
        patterns = {n: f.get("pattern") for n, f in signatures.load().get("functions", {}).items()}
    except (OSError, ValueError):
        patterns = {}
    natives = {}
    for name, rva, _ in NATIVE:
        at = rva if functions is None else functions.get(name)
        if isinstance(at, int) and at > 0 and patterns.get(name):
            natives[name] = {"rva": at, "pattern": patterns[name]}
    return {"game_build": build, "members": members, "functions": natives}


def version_number(version):
    """A wcmods version as the number scripts compare (Game.wcmodsNumber): major * 10000 + minor * 100 + patch,
    "0.6.0" -> 600. Anything after the digits of a part ("0.6.0rc1") is left out."""
    parts = [int(re.match(r"\d*", p).group() or 0) for p in str(version).split(".")[:3]]
    parts += [0] * (3 - len(parts))
    return parts[0] * 10000 + parts[1] * 100 + parts[2]


def lua(offsets=None, saved=None):
    """The module's Lua; `offsets` as for hidden(); `saved`, the folder Game.save.folder() names (the one
    an install makes, pipeline.saved_folder), or None for the usual one. Game.wcmods is this wcmods' version."""
    from . import __version__
    from .sdk import lua_value
    rows = []
    for cls, fields in hidden(offsets):
        items = ", ".join(f'{{ "{n}", 0x{o:X}, "{k}" }}' for n, o, k in fields if k not in CPP_ONLY)
        if items:
            rows.append(f'    ["{cls}"] = {{ {items} }},')
    enums = "".join(f"\n    {key} = {{ {lua_value(path)}, {lua_value(names)} }}," for key, path, names in ENUMS)
    return (LUA.replace("@HIDDEN@", "{\n" + "\n".join(rows) + "\n}").replace("@SAVED@", lua_value(saved))
            .replace("@ENUMS@", "{" + enums + "\n}").replace("@WCMODS@", lua_value(__version__))
            .replace("@WCMODS_NUMBER@", str(version_number(__version__))))
