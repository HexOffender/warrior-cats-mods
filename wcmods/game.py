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
    # Its subclass's talk tables, StoryDialogues.csv and QuestDialogues.csv (TMap<FString,
    # FSwtQuestStoryDialoguesStruct>, 0x60-byte elements), which a bond talk's answer looks its row up in
    # (docs/reverse-engineering.md, "A bond talk's answer").
    ("/Script/SwtQuest.SwtQuestTuningManager", [
        ("WCM_StoryDialogues", 0x280, "MapProperty"), ("WCM_QuestDialogues", 0x2D0, "MapProperty")]),
    # The sky's copy of its presets (TMap<ESkyboxPostProcessEnum, FWrcSkyBoxStruct>, 0x168-byte elements: the preset
    # at +0, its row from +8), made from SkyParamsDB as it starts; what putting a preset on reads.
    ("/Script/Wrc.WrcSkyboxActor", [("WCM_Presets", 0x378, "MapProperty")]),
    # The exploration camera's settings (SwtAdventureCameraActor, BP_AdventureCamera_C): a struct at +0x3F8 its
    # BeginPlay fills from TuningData's Gameplay.Exploration.Camera.*, and which its Tick reads every frame for the
    # arm's length, the arm's tilt and the lens's field of view (docs/reverse-engineering.md, "The exploration
    # camera"). The field of view at +0x3F8 isn't a tuning key: 90, the lens's own. Lag is copied onto the spring arm
    # once, in BeginPlay. Its copies of the turn rates and pitch limits (+0x448 to +0x458) aren't read: the turning
    # is the exploration component's.
    ("/Script/SwtAdventure.SwtAdventureCameraActor", [
        ("WCM_Fov", 0x3F8, "FloatProperty"), ("WCM_ArmPitch", 0x404, "FloatProperty"),
        ("WCM_ArmLength", 0x408, "FloatProperty"), ("WCM_LagVertical", 0x410, "FloatProperty"),
        ("WCM_LagHorizontal", 0x414, "FloatProperty"), ("WCM_LagRotation", 0x418, "FloatProperty"),
        ("WCM_SpeedArmLength", 0x41C, "FloatProperty"), ("WCM_SpeedFov", 0x424, "FloatProperty")]),
    # Your cat's exploration settings (ExplorationControlComponent, BP_Exploration_Control), filled by its BeginPlay
    # from Gameplay.Exploration.*: the turning the mouse and stick do (the camera's input reads these, not the
    # camera's own copies) and the pitch it allows; and its speeds, which the component writes into its character's
    # CharacterMovement every frame (MaxWalkSpeed: walk or, while running, run, times the crouch or climb factor;
    # MaxAcceleration the same with the accelerations). How it's moving is the flags at +0x110: 4 running,
    # 1 crouched, 2 climbing.
    ("/Script/SwtAdventure.ExplorationControlComponent", [
        ("WCM_MoveFlags", 0x110, "IntProperty"),
        ("WCM_WalkSpeed", 0x12C, "FloatProperty"), ("WCM_WalkAcceleration", 0x130, "FloatProperty"),
        ("WCM_RunSpeed", 0x134, "FloatProperty"), ("WCM_RunAcceleration", 0x138, "FloatProperty"),
        ("WCM_CrouchFactor", 0x148, "FloatProperty"), ("WCM_ClimbFactor", 0x150, "FloatProperty"),
        ("WCM_TurnYaw", 0x1CC, "FloatProperty"), ("WCM_TurnPitch", 0x1D0, "FloatProperty"),
        ("WCM_PitchMin", 0x1D8, "FloatProperty"), ("WCM_PitchMax", 0x1DC, "FloatProperty")]),
    # The world map (GuiPopupWorldMap, WBP_GuiPopupWorldMap_C): where its pointer is in the map's layers (the
    # pointer's spot, which doesn't move) and the layers' translation (doubles; a second copy at +0x638), which moving
    # the map changes and the map puts on CanvasLayers each frame. The place under the pointer is the item at the
    # pointer's spot less the translation. C++ only: UE4SS's custom properties have no double.
    ("/Script/Wrc.GuiPopupWorldMap", [
        ("WCM_PointerX", 0x618, "DoubleProperty"), ("WCM_PointerY", 0x620, "DoubleProperty"),
        ("WCM_TranslationX", 0x628, "DoubleProperty"), ("WCM_TranslationY", 0x630, "DoubleProperty"),
        ("WCM_TranslationToX", 0x638, "DoubleProperty"), ("WCM_TranslationToY", 0x640, "DoubleProperty")]),
]

# The kinds in HIDDEN only the C++ SDK reads (offsets.json): the Lua's Game.hidden leaves them out.
CPP_ONLY = {"MapProperty", "DoubleProperty"}

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
    # The game's bond code (docs/reverse-engineering.md, "Bonds"): static functions on the cat's slot of the save
    # manager's data (its vtable +0x498, slot -1: the cat played now), each named by its own log line.
    ("Bonding:GetPersonal", 0x169F830,
     "a story cat's bond with your cat: (uint8 ENarrativeRole, int32 slot: -1 for the cat played now) -> int32; the "
     "slot's Bonding/<role>, or the role's BaseBonding from the narrative roles' table when it isn't set"),
    ("Bonding:AddPersonal", 0x169F510,
     "adds to a story cat's bond (\"AddPersonalBonding\"): (uint8 ENarrativeRole, int32 amount), on the cat played "
     "now: the bond as GetPersonal reads it plus the amount, written to the slot's Bonding/<role>"),
    ("Bonding:GetClan", 0x169FE30,
     "a clan's regard for your cat: (uint8 EClanType) -> int32, on the cat played now; the slot's Bonding/<clan>, or "
     "the tuning's Gameplay.Progression.Bonding.Clan.Default when it isn't set"),
    ("Bonding:AddClan", 0x169FBD0,
     "adds to a clan's regard (\"AddClanScore\"): (uint8 EClanType, int32 amount), on the cat played now"),
    ("Bonding:HasNode", 0x169F020,
     "whether a bond talk's answer is in the slot's Bonding/Nodes: (const FString* the answer's row name) -> bool, on "
     "the cat played now"),
    ("Bonding:AddNode", 0x169F230,
     "marks a bond talk's answer in the slot's Bonding/Nodes (\"AddNodeToPersonalBonding\"): (const FString* the "
     "answer's row name), on the cat played now"),
    # A cat's look put on its model (docs/reverse-engineering.md, "Cat models"): named by its profiling stat.
    ("SwtAdventureCustomizableMeshComponent:SetDefaultCustomData", 0x17AF7D0,
     "sets a cat's look up on its model (\"SetDefaultCustomData\"): (the look component, const FCatCustomData*, bool); "
     "copies the look into the component's CustomData, makes up the colour slots unless bOverrideColors, and sets "
     "every part again (meshes, pattern atlas, colours, eyes, accessories, scars); does nothing unless the component's "
     "owner is a SwtAdventureCharacter that's a cat (its byte at +0x890 is 1 or 2)"),
    ("Customization:SaveCatCustomData", 0x18129C0,
     "keeps a look in the save (\"SaveCatCustomData\"): (const FCatCustomData*, FString key by value (the callee frees "
     "it; empty for your cat's, Gameplay.Combat.Character.Cat.Player), int32 slot: -1 for the cat played now); the "
     "struct's text written as the slot's GameplayProgression/<key>/Customization, which the game sets your cat up "
     "from"),
    # What using a herb does (docs/reverse-engineering.md, "Items"): Consumables.csv's rows live only in the
    # adventure tuning manager's map at +0x780 (a DataTable it loads and lets go of); this is the game's own lookup.
    ("SwtAdventureTuningManager:GetConsumable", 0x181DFE0,
     "a herb's Consumables.csv row: (const FString* row name, the herb's tag; FSwtAdventureConsumableStruct* out, 0x28 "
     "bytes: bCombat +0x10, bExploration +0x11, Target +0x12, bRemoveAfterCombat +0x13, Type +0x14, EffectOnUse FString "
     "+0x18, assigned with the game's allocator) -> bool, false for a row it hasn't got; reads the tuning manager (a "
     "global) and its map at +0x780"),
    # What a den decoration costs (docs/reverse-engineering.md, "Dens from C++"): HousingCost.csv's rows live only in
    # the same tuning manager, in its map at +0x6E0; this is the game's own lookup, which its build screen uses.
    ("SwtAdventureTuningManager:GetHousingCost", 0x181E520,
     "a decoration's HousingCost.csv row: (FAdventureHousingCost* out, 0x50 bytes; const FString* the decoration's "
     "tag) -> out, the row copied with the game's allocator (its FStrings: MontageToPlay, BoneToAttach, Cost), or a "
     "default row for a tag it hasn't got; reads the tuning manager (a global) and its map at +0x6E0 (0x68-byte "
     "elements, the row at +0x10)"),
    ("SwtTuningManager:GetValue", 0x12BBA60,
     "a TuningData.csv key's MaxValue, as every tuning read in the game gets it: (const FString* key) -> float, "
     "0 for a key the table hasn't got; reads the tuning manager (a global) and its map, WCM_TuningData"),
    # The places to travel to (docs/reverse-engineering.md, "Travel, the HUD's pieces and the camera from C++"): a static
    # function beside the bond code, on the save manager (a global). Its reader beside it (0x16A7D20: (UID, the
    # checkpoint) -> -1 no entry, 0 locked, 1 unlocked) has no unique pattern: its code is the bond reads' shape.
    # A story scene played by its tag (docs/reverse-engineering.md, "Story scenes from C++"): every sequencer manager's
    # vtable +0x338, the base class's.
    ("SwtSequencerManager:PlaySequence", 0x12B2190,
     "plays a registered sequence: (the sequencer manager, const 0x88-byte arguments*) -> non-null when it started; "
     "the arguments: +0x00 pause at its end (bool), +0x08 a music track's name (FString, empty for none), +0x18 the "
     "play rate (float), +0x20 a length to fit it to, in seconds, setting its rate (float, 0 for its own), +0x28 the actors to put in it (an empty TMap: its bit "
     "array's size word at +0x50 is 0x80 and its free index at +0x58 is -1), +0x78 a flag the talk action sets and "
     "the prophecy intro doesn't, +0x7C its ESwtEngineSequencerType (int32), +0x80 its tag (FGameplayTag)"),
    ("Checkpoints:SetUnlocked", 0x16A7DE0,
     "unlocks a checkpoint or locks it again (\"SetCheckpointUnlockState\"): (const FString* the checkpoint's UID, its "
     "tag; bool unlocked; UObject* the checkpoint, a world context: the save keeps checkpoints under its level's name), "
     "on the cat played now; writes GameplayProgression/<level>/Checkpoints (the save manager's vtable +0x4B8) and "
     "broadcasts the save manager's checkpoint delegate (+0x170) with the UID, which the map's checkpoint markers and "
     "the checkpoint actors hear. The checkpoint's BeginPlay calls it so (0x1416357A0)"),
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
