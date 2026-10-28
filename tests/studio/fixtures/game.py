"""A made-up game for the tests: a game folder with the exe, UE4SS's mods folder and a base pak holding a few of
the game's data tables (cut down, with their real headers and keys) and its English text, beside an empty
container, so the Game data page and its routes work without the real game. A save goes in a saves folder
the same way the tests' other saves do.

From pytest, conftest.py loads it (the fixtures data_game and save). From the end-to-end tests:

    python -I tests/studio/fixtures/game.py <game folder> [<saves folder>]

writes the game into the first folder and, with a second, the tests' save into it.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from wcmods.config import EXE_NAME  # noqa: E402
from wcmods.formats.blake3 import blake3  # noqa: E402
from wcmods.formats.iostore import ModContainerWriter  # noqa: E402
from wcmods.formats.pak import PakWriter  # noqa: E402
from wcmods.gamefiles import BASE_PAK, BASE_UTOC, NONASSET  # noqa: E402

STRINGS_EN = "Wrc/Content/Gameplay/Strings/NonAsset/Strings_EN.csv"
LEVELS = [80, 100, 135, 180, 230, 300, 400, 520, 680, 890, 1160, 1500, 2000, 2600, 3400, 4400, 5800, 7500, 10000]

# The game's tables as it ships them (line endings and all), with only some of their rows.
TABLES = {
    "TuningData.csv": "\r\n".join([
        "---,MaxValue,Description",
        "Gameplay.Exploration.Metrics.Cat.Player.Height,15,The average height of the cat from the ground to its head.",
        "Gameplay.Exploration.Player.MoveAndRun.Walk.Speed,175,The target maximum speed of the cat while walking.",
        "Gameplay.Exploration.Player.MoveAndRun.Run.Speed,390,The target maximum speed of the cat while running.",
        "Gameplay.Exploration.Player.MoveAndRun.Stamina.DrainRate,-10,The rate at which stamina is consumed while running.",
        "Gameplay.Exploration.Stamina.RegenRate,20,The rate at which stamina regenerates when not running.",
        "Gameplay.Exploration.Jump.Height.Min,85,The minimum vertical height of a jump (when starting from a standstill).",
        "Gameplay.Exploration.Jump.Height.Max,85,The maximum vertical height of a jump (when starting from Run_Speed).",
        "Gameplay.Combat.Rest.Stamina,0.4,",
        "Gameplay.Exploration.MaxLevel,20,",
        *[f"Gameplay.Exploration.Level.{n},{xp}," for n, xp in enumerate(LEVELS, start=2)],
        "Gameplay.Exploration.DayNight.ClockSpeed,72,",
        "Gameplay.Inventory.Capacity.Apprentice,100,",
        "Gameplay.Inventory.Capacity.Warrior,120,",
        "Gameplay.Inventory.Capacity.Deputy,140,",
        "Gameplay.Inventory.Capacity.Leader,160,",
        "Gameplay.NPC.Heterochromia.Chance,0.15,",
        "Gameplay.Exploration.FreshKillPile.Decay.Time,90,",
        "Gameplay.Exploration.FreshKillPile.Mice,1,",
        "Gameplay.Exploration.FreshKillPile.Bird,2,",
        "Gameplay.Exploration.FreshKillPile.Squirrel,3,",
        "Gameplay.Exploration.FreshKillPile.Fish,3,",
        "Gameplay.Exploration.FreshKillPile.Rat,4,",
        "Gameplay.Exploration.FreshKillPile.Rabbit,5,",
    ]) + "\r\n",
    "CombatBaseExperience.csv": "\r\n".join([
        "Enemy,BaseExperience,DifficultyOffset", "Fish,10,0", "WeakMice,25,0", "Mice,25,0", "Squirrel,30,0",
        "Rabbit,40,0", "Bird,30,0", "Rat,60,0", "Badger,70,1",
    ]),
    "HousingCost.csv": "\r\n".join([
        "---,Cost,BuildTime,Rarity,MaxQuantity,Size,bIsHidden",
        'Gameplay.Inventory.Decoration.1,"Gameplay.Inventory.Materials.Dandelion,3;Gameplay.Inventory.Materials.Moss,1",0,Common,-1,Medium,FALSE',
        'Gameplay.Inventory.Decoration.4,"Gameplay.Inventory.Materials.Pine,1;Gameplay.Inventory.Materials.Cotton,3",4800,Uncommon,-1,Medium,FALSE',
        'Gameplay.Inventory.Decoration.11,"Gameplay.Inventory.Materials.Leaves,1",0,Rare,-1,Large,FALSE',
    ]) + "\r\n",
    "NPC/CatSize.csv": "\r\n".join([
        "--,Role,MinScale,MaxScale", "1,Kit,0.1,0.15", "2,Apprentice,0.4,0.5", "3,Elder,0.65,0.75", "4,Warrior,0.7,0.8",
        "5,MedicineCat,0.7,0.8", "6,Queen,0.7,0.8", "7,Deputy,0.7,0.8", "8,Leader,0.9,1", "9,StarClanAncestor,0.9,1",
        "10,RogueCat,0.7,0.8", "11,RogueCatLeader,0.9,1",
    ]),
    "NPC/Scars.csv": "\r\n".join([
        ",Role,Group,EarChance,BodyChance,EyeChance", "1,Kit,All,0.00,0.00,0.00", "2,Apprentice,All,0.00,0.00,0.00",
        "3,Warrior,All,0.10,0.05,0.00", "4,MedicineCat,All,0.10,0.05,0.00", "5,Queen,All,0.10,0.05,0.00",
        "6,Deputy,All,0.75,0.10,0.00", "7,Leader,All,0.85,0.50,0.00", "8,Elder,All,0.85,0.50,0.50",
        "9,StarClanAncestor,Clans,0.95,0.75,0.25", "10,StarClanAncestor,Out of clans,1.00,0.85,0.50",
        "11,RogueCat,All,0.50,0.50,0.50", "12,RogueCatLeader,All,0.50,0.50,0.50",
    ]),
    "Consumables.csv": "\r\n".join([
        "---,EffectOnUse,bCombat,bExploration,Target,bRemoveAfterCombat,Type",
        "Gameplay.Inventory.Consumable.SmallHealingHerb,Gameplay.Effect.Consumable.Health.1,TRUE,TRUE,Owner,FALSE,Health",
        "Gameplay.Inventory.Consumable.MediumHealingHerb,Gameplay.Effect.Consumable.Health.2,TRUE,TRUE,Owner,FALSE,Health",
        "Gameplay.Inventory.Consumable.HealingHerbPouch,Gameplay.Effect.Consumable.Health.2,TRUE,TRUE,OwnerTeam,FALSE,Health",
        "Gameplay.Inventory.Consumable.SmallCatnip,Gameplay.Effect.Consumable.Stamina.1,TRUE,FALSE,Owner,FALSE,Stamina",
        "Gameplay.Inventory.Consumable.ThistlePouch,Gameplay.Effect.Consumable.Buff.Strength.1,TRUE,FALSE,OwnerTeam,TRUE,BuffStrength",
    ]) + "\r\n",
    "AttackMove.csv": "\n".join([
        "#,Name,Power,Stance", "1,STR_ATTACK_QUICK_CLAW,10,Offensive", "2,STR_ATTACK_POUNCE,25,Offensive",
        "3,STR_ATTACK_DODGE,0,Defensive",
    ]) + "\n",
    "OnlineGifts.csv": "---,Amount\nGameplay.Inventory.Materials.Moss,2\n",
    "HeightMap/L_Test_Height_0.csv": "X,Y,Z\n0,0,0\n",
}
TEXTS = "\r\n".join(["---,Text", "STR_ATTACK_QUICK_CLAW,Quick Claw", "STR_ATTACK_POUNCE,Pounce",
                     "STR_ATTACK_DODGE,Dodge"]) + "\r\n"


def write_game(game):
    """The game's folder as config.is_game_dir knows one, with the base pak and an empty container."""
    win64 = os.path.join(game, "Wrc", "Binaries", "Win64")
    paks = os.path.join(game, "Wrc", "Content", "Paks")
    os.makedirs(os.path.join(win64, "ue4ss", "Mods"), exist_ok=True)
    os.makedirs(paks, exist_ok=True)
    with open(os.path.join(win64, EXE_NAME), "wb"):
        pass
    pak = PakWriter()
    for name, text in TABLES.items():
        pak.add(NONASSET + name, text.encode("utf-8"))
    pak.add(STRINGS_EN, TEXTS.encode("utf-8"))
    pak.write(os.path.join(paks, BASE_PAK), BASE_PAK)
    stem = BASE_UTOC[:-len(".utoc")]
    ModContainerWriter(blake3(stem.lower().encode(), 8)).write(os.path.join(paks, BASE_UTOC),
                                                              os.path.join(paks, stem + ".ucas"))
    return game


def write_save(folder, data):
    """WrcGame.sav holding `data` in folder, laid out as the game lays out its saves."""
    from wcmods.formats.save import SAV_NAME
    from wcmods.selftest import _small_save
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, SAV_NAME)
    with open(path, "wb") as f:
        f.write(_small_save(json.dumps(data, indent="\t")))
    return path


# The save the end-to-end tests play with: your cat (Fawnstar, as the game would name it) in slot 1, part way
# through, with things in its inventory; and a second cat in slot 0.
def e2e_save():
    cat = ('(ClanType=RiverClan,Role=Warrior,PrefixNameId="STR_CAT_NAME1",SuffixNameId="_STAR",FurColorIdx=3,'
           'Pattern01ColorIdx=5,BodyValue=2,CatSize=1.1)')
    progress = {"Level": 5, "Experience": 120, "FreshKill": {"Value": 62, "Timer": 0, "Cycle": 0},
                "Stats": "(Prowess=90.000000,Strength=85.000000)",
                "Gameplay.Combat.Character.Cat.Player": {"Customization": cat, "State": {"Health": 100, "Stamina": 100}},
                "State": {"Inventory": {"Gameplay.Inventory.Consumable.SmallHealingHerb": 2,
                                        "Gameplay.Inventory.Materials.Moss": 4}}}
    return {"acct": {
        "0": {"GameplayProgression": {"Level": 2, "Experience": 10}},
        "1": {"GameplayProgression": progress},
        "Shared": {"General": {"CurrentCatSlot": 1},
                   "SettingsData": {"MasterVolume": 1, "Minimap": True},
                   "InputKeyboard": {"Player_Jump": "0,Player_Jump,SpaceBar,1.000000.1"}}}}


if __name__ == "__main__":
    write_game(sys.argv[1])
    if len(sys.argv) > 2:
        write_save(sys.argv[2], e2e_save())
