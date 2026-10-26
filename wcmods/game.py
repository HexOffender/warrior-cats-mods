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
from .lua import source as lua_source

SHARED_NAME = "WCModsGame"

# Members the game doesn't reflect, found by reverse-engineering build 24847281 (docs/mechanics/,
# docs/reverse-engineering.md) and confirmed unchanged on 26184573, patch 1.1 (the level component read in
# game, the rest by signatures.py): class, then (property name, offset in the object, type). Rendered into
# the Lua as Game.hidden. They're offsets inside objects, so ASLR doesn't move them, but a game update
# that changes a class's layout does: signatures.py finds them again in a new build, and lua() takes the
# offsets it found.
HIDDEN = [
    # Every resource component (health, stamina, combat stamina, level, fresh-kill pile).
    ("/Script/SwtQuest.SwtQuestResourceComponent", [
        ("WCM_ResourceType", 0x108, "IntProperty"), ("WCM_Value", 0x10C, "FloatProperty"),
        ("WCM_Max", 0x110, "FloatProperty"), ("WCM_Scale", 0x114, "FloatProperty")]),
    ("/Script/SwtQuest.SwtQuestStaminaComponent", [("WCM_Regen", 0x11C, "FloatProperty")]),
    # The player state's level component: level, and the cat's stats out of combat.
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


def offsets_json(offsets=None, build=None):
    """The same members for C++ mods, written beside the module as offsets.json:
    {"game_build", "members": {"class:property": {"offset", "type"}}}; `offsets` as for hidden()."""
    members = {f"{cls}:{name}": {"offset": offset, "type": kind}
               for cls, fields in hidden(offsets) for name, offset, kind in fields}
    return {"game_build": build, "members": members}


def lua(offsets=None):
    """The module's Lua; `offsets` as for hidden()."""
    rows = []
    for cls, fields in hidden(offsets):
        items = ", ".join(f'{{ "{n}", 0x{o:X}, "{k}" }}' for n, o, k in fields)
        rows.append(f'    ["{cls}"] = {{ {items} }},')
    return LUA.replace("@HIDDEN@", "{\n" + "\n".join(rows) + "\n}")
