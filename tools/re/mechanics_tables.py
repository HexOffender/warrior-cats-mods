"""Fill the generated tables in docs/mechanics/*.md from the game's extracted data tables.

usage: mechanics_tables.py [<Gameplay folder>]   (default vanilla/Wrc/Content/Gameplay)

A doc marks a table as `<!-- table:<name> -->`, optionally followed by the table and
`<!-- /table -->`. Everything between the markers is replaced, so run this again after extracting a
new build. Extract the tables first with `python wcmods.py extract "Gameplay/DataTables/NonAsset/*"`
and `"Gameplay/Strings/NonAsset/*"`.
"""
import csv
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "vanilla", "Wrc", "Content", "Gameplay")
TABLES = os.path.join(ROOT, "DataTables", "NonAsset")

with open(os.path.join(ROOT, "Strings", "NonAsset", "Strings_EN.csv"), encoding="utf-8-sig") as f:
    STRINGS = {r[0]: r[1] for r in csv.reader(f) if len(r) >= 2}


def en(key):
    return STRINGS.get(key, key)


def load(name):
    with open(os.path.join(TABLES, name + ".csv"), encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def pct(v):
    return f"{float(v) * 100:+g}%"


def costs(text):
    out = []
    for part in text.split(";"):
        tag, n = part.split(",")
        out.append(f"{n} {tag.replace('Gameplay.Inventory.Materials.', '')}")
    return ", ".join(out)


# Who an effect's Target code means, worked out from which rows use each code.
WHO = {"0": "item's target", "1": "self", "2": "a clanmate", "4": "own team", "7": "the target"}


def turns(n):
    return {"-1": "rest of the fight", "0": "now", "1": "1 round"}.get(n, f"{n} rounds")


def effects():
    """Effect tag -> description, from the two effect parameter tables (matched by name)."""
    out = {}
    for r in load("Effects/CombatStatBuffEffect"):
        parts = [f"{k} {pct(r[k])}" for k in ("Prowess", "Strength", "Resilience", "Instinct", "Agility", "Speed")
                 if float(r[k])]
        out[r[""]] = f"{', '.join(parts)} ({WHO.get(r['Target'], r['Target'])}, {turns(r['NumTurns'])})"
    generic = {}
    for r in load("Effects/GenericEffect"):
        base, _, field = r[" "].rpartition(".")
        generic.setdefault(base, {})[field] = (r["FloatValue"], r["BooleanValue"] == "TRUE")
    for base, fields in generic.items():
        if base in out:
            continue
        percent = fields.get("UsePercent", ("0", False))[1]
        bits = [f"{k} {pct(v) if percent or abs(float(v)) <= 1 else v}" for k, (v, _) in fields.items()
                if k not in ("Target", "NumTurns", "UsePercent")]
        who = WHO.get(fields.get("Target", ("?",))[0], "?")
        out[base] = f"{', '.join(bits)} ({who}, {turns(fields.get('NumTurns', ('?',))[0])})"
    return out


PLAYER = ("Universal", "Clan", "Ancestor")


def moves():
    eff = effects()
    lines = ["| Move | Name | Stance | Rank | Target | Damage | Accuracy | Stamina | Status | Effect |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in load("AttackMove"):
        if r["Category"] not in PLAYER:
            continue
        status = f"{r['StatusCondition']} {float(r['StatusChance']):.0%}" if r["StatusCondition"] != "None" else ""
        e = eff.get(r["Effect"].replace("Gameplay.Effect.", "Gameplay.Params."), "") if r["Effect"] else ""
        if r["MaxEffectUses"] != "0":
            e += f", max {r['MaxEffectUses']} uses"
        lines.append(f"| {r['AttackMoveTag'].replace('Gameplay.Combat.Attack.', '')} | {en(r['Name'])} | "
                     f"{r['Stance']} | {r['Rank']} | {r['Target']} | {r['Damage']} | {r['Accuracy']} | "
                     f"{r['StaminaCost']} | {status} | {e} |")
    return lines


def enemy_moves():
    sets = {}
    for r in load("AttackMove"):
        if r["Category"] in PLAYER:
            continue
        status = f" {r['StatusCondition']} {float(r['StatusChance']):.0%}" if r["StatusCondition"] != "None" else ""
        sets.setdefault(r["Category"], []).append(
            f"{en(r['Name'])} {r['Damage']}/{r['Accuracy']}/{r['StaminaCost']} {r['Stance']}{status}")
    return ["| Set | Moves (damage / accuracy / stamina, stance) |", "|---|---|"] + \
        [f"| {k} | {'; '.join(v)} |" for k, v in sets.items()]


def dilemmas():
    lines = ["| Dilemma | When | Chance | Choice A | Choice B |", "|---|---|---|---|---|"]
    for r in load("CombatDilemmas"):
        if r["TriggerType"] == "BossEnding":
            continue
        when = r["TriggerType"]
        if r["TriggerStat"] != "None":
            when += f", {r['TriggerCharacter']} {r['TriggerStat']} {r['TriggerCondition']} {r['TriggerValue']}"
        a, b = (f"{r[s + 'WarCode']}: {en(r[s + 'Bonus']).replace('{N}', r[s + 'Value'])}" for s in "AB")
        lines.append(f"| {en(r['Name'])} | {when} | {r['Chance']} | {a} | {b} |")
    return lines


def barter():
    return ["| Item | Cost |", "|---|---|"] + \
        [f"| {r['---'].replace('Gameplay.Inventory.', '')} | {costs(r['Cost'])} |" for r in load("BarteringCost")]


def decorations():
    lines = ["| # | Name | Kind | Rarity | Build time | Max | Cost |", "|---|---|---|---|---|---|---|"]
    for r in load("HousingCost"):
        n = r["---"].rsplit(".", 1)[1]
        kind = r["Size"]
        for anim, what in (("Sleep", "bed"), ("Sharpen", "scratching"), ("Play", "toy")):
            if anim in r["MontageToPlay"]:
                kind += f", {what}"
        most = "any" if r["MaxQuantity"] == "-1" else r["MaxQuantity"]
        lines.append(f"| {n} | {en('STR_ITEM_DECORATION_' + n)} | {kind} | {r['Rarity']} | "
                     f"{int(r['BuildTime']) // 3600} h | {most} | {costs(r['Cost'])} |")
    return lines


def bond_rewards():
    def reward(text):
        return text.replace("Gameplay.Inventory.Consumable.", "").replace("Gameplay.Combat.Attack.", "move ") \
            .replace(";", " x")
    lines = ["| Clan | Role | Who | Base bonding | Friendly | Friend | Close bond |", "|---|---|---|---|---|---|---|"]
    for r in load("NPC/NarrativeRole"):
        if r["RewardFriendly"] or r["RewardFriend"] or r["RewardCloseBond"]:
            lines.append(f"| {r['Clan']} | {r['NarrativeRole']} | {r['NPCClan']} {r['NPCRole']} | "
                         f"{r['BaseBonding']} | {reward(r['RewardFriendly'])} | {reward(r['RewardFriend'])} | "
                         f"{reward(r['RewardCloseBond'])} |")
    return lines


BUILDERS = {f.__name__: f for f in (moves, enemy_moves, dilemmas, barter, decorations, bond_rewards)}
# A marker, and the table after it if one was filled in before (never reaching into the next block).
BLOCK = re.compile(r"<!-- table:(\w+) -->\n(?:(?:(?!<!-- table:).)*?<!-- /table -->\n)?", re.S)


def fill(match):
    name = match.group(1)
    return f"<!-- table:{name} -->\n" + "\n".join(BUILDERS[name]()) + "\n<!-- /table -->\n"


if __name__ == "__main__":
    for path in sorted(glob.glob(os.path.join(REPO, "docs", "mechanics", "*.md"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new = BLOCK.sub(fill, text)
        if new != text:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new)
            print("updated", os.path.relpath(path, REPO))
