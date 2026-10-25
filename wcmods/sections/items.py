"""New items (items.json): herbs and materials of a mod's own, with a name, a description, an icon, what
they do, a recipe at the medicine cat's bartering, and some to start with; and new recipes for the
game's own herbs and accessories.

    {
      "items": [
        {
          "id": "MoonHerb",
          "like": "MediumHealingHerb",
          "name": "Moon Herb",
          "description": "Health Recovery (medium). Picked under a full moon.",
          "recipe": { "Dandelion": 2, "Cotton": 1 },
          "give": 3
        }
      ],
      "recipes": { "Cosmetic.Head.MossPatch.1": { "Moss": 3, "Ivy": 1 } }
    }

An item needs four things in the game, and this section writes them all:
  * its gameplay tag (Gameplay.Inventory.Consumable.<id> or ...Materials.<id>), in an ini under
    Wrc/Config/Tags, which the game registers at startup;
  * for a herb, a Consumables.csv row: what using it does, and when;
  * a row in the cooked DT_QuestObjectsInfo table: its name, description and icon (the inventory leaves
    out items without one);
  * for "recipe", a BarteringCost.csv row, and for "give", the item in your save (once).

"like" names a game item to start from (its effect, when it can be used, icon and icon group); the
item's own keys override those. "recipes" changes what the medicine cat wants for one of the game's
items, by its tag (with or without "Gameplay.Inventory."). See docs/SDK.md for every key.
"""
import os
import re

from .. import cooked, csvdata
from ..save import SAV_NAME, SaveGame
from ..savejson import SaveDoc
from ..sdk import Section

TAG_ROOT = "Gameplay.Inventory."
KINDS = {"consumable": "Consumable", "material": "Materials"}
TAGS_INI = "Wrc/Config/Tags/WCModsItems.ini"
INVENTORY = "GameplayProgression/State/Inventory"     # in the save slot being played
TABLE = "DT_QuestObjectsInfo"
ID = re.compile(r"[A-Za-z][A-Za-z0-9]{0,47}$")
KEYS = {"id", "kind", "like", "name", "description", "icon", "effect", "type", "target", "combat", "exploring",
        "fight_only", "group", "rarity", "color", "recipe", "give"}


class ItemsSection(Section):
    id = "items"
    title = "New items"
    files = ("items.json",)

    def collect(self, mod, ctx):
        raw = self.read_json(mod, "items.json")
        if not isinstance(raw, dict):
            raise ValueError('items.json should be an object: {"items": [...], "recipes": {...}}')
        items = raw.get("items", [])
        recipes = raw.get("recipes", {})
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            raise ValueError('items.json: "items" should be a list of items, e.g. [{"id": "MoonHerb", ...}]')
        if not isinstance(recipes, dict) or not all(isinstance(r, dict) for r in recipes.values()):
            raise ValueError('items.json: "recipes" should map game items to materials, e.g. '
                             '{"Cosmetic.Head.MossPatch.1": {"Moss": 3}}')
        for i, item in enumerate(items):
            what = f"items.json: item {i + 1}"
            unknown = sorted(k for k in item if k not in KEYS and not k.startswith("_"))
            if unknown:
                raise ValueError(f"{what}: unknown key(s) {', '.join(unknown)} (docs/SDK.md lists them)")
            if not isinstance(item.get("id"), str) or not ID.match(item["id"]):
                raise ValueError(f"{what}: \"id\" should be letters and digits, starting with a letter (e.g. \"MoonHerb\")")
            for key in ("name", "description"):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    raise ValueError(f"{what} ({item['id']}): \"{key}\" is missing")
        return {"items": items, "recipes": recipes} if items or recipes else None

    def build(self, ctx, items):
        if ctx.game.oodle is None:
            # DT_QuestObjectsInfo is compressed in the game's files, and without a row there the
            # inventory doesn't show the item.
            ctx.warn("new items left out: they need the Oodle DLL (oo2core_*_win64.dll, from another game) to "
                     "read the game's item table")
            return
        game = Game(ctx)
        slot = _current_slot(ctx)
        made = {}                      # tag -> mod id
        # Materials first, so a mod's herb can be made from a material it adds.
        ordered = sorted(((mod, item) for mod, data in items for item in data["items"]),
                         key=lambda mi: game.kind(mi[1]) != "material")
        for mod, item in ordered:
            try:
                tag, rows = game.item(item, made)
            except ValueError as e:
                ctx.warn(f"{mod.id}: {item['id']}: {e}")
                continue
            made[tag] = mod.id
            text = f"{TAG_ROOT}{mod.id}.{item['id']}"
            ctx.add_table_row(TABLE, f"WCMods_{item['id']}", dict(rows["info"], **{
                "Name": cooked.base_text(item["name"], text + ".Name"),
                "Description": cooked.base_text(item["description"], text + ".Description")}), source=mod.id)
            if "use" in rows:
                ctx.edit_csv("Consumables.csv", {"+": [rows["use"]]}, source=mod.id)
            if "recipe" in rows:
                ctx.edit_csv("BarteringCost.csv", {"+": [rows["recipe"]]}, source=mod.id)
            give = item.get("give")
            if give and slot is None:
                ctx.warn(f"{mod.id}: {item['id']}: no save yet to give it in; start the game once, then install again")
            elif give:
                ctx.add_save_key(f"{slot}/{INVENTORY}", tag, give, source=mod.id, only_new=True)
        for mod, data in items:
            for name, recipe in data["recipes"].items():
                tag = name if name.startswith(TAG_ROOT) else TAG_ROOT + name
                if tag not in game.recipes:
                    ctx.warn(f"{mod.id}: recipes: the medicine cat has no recipe for {name} (a game item's tag, "
                             "e.g. Cosmetic.Head.MossPatch.1)")
                    continue
                try:
                    cost = game.cost(recipe, made)
                except ValueError as e:
                    ctx.warn(f"{mod.id}: recipes: {name}: {e}")
                    continue
                ctx.edit_csv("BarteringCost.csv", {tag: {"Cost": cost}}, source=mod.id)
        if made:
            lines = ["[/Script/GameplayTags.GameplayTagsList]"]
            lines += [f'GameplayTagList=(Tag="{tag}",DevComment="wcmods: {by}")' for tag, by in sorted(made.items())]
            ctx.add_file(TAGS_INI, ("\r\n".join(lines) + "\r\n").encode("utf-8"), source="items")
            ctx.note("items", sorted(made))


class Game:
    """What the game already has: its items, their info rows, consumable rows and recipes."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.info = {v.get("itemTag"): v for _, v in ctx.cooked_table(TABLE)}
        self.use = _rows(ctx.read_data_table("Consumables.csv"))
        self.recipes = _rows(ctx.read_data_table("BarteringCost.csv"))
        self.effects = sorted({r["EffectOnUse"] for r in self.use.values()})
        self.types = sorted({r["Type"] for r in self.use.values()})
        self.targets = sorted({r["Target"] for r in self.use.values()})
        self.materials = {t for t in self.info if t.startswith(TAG_ROOT + "Materials.")}

    def full(self, name, kinds=("Consumable", "Materials")):
        """An item tag from a short name ("Dandelion") or the whole tag."""
        if name.startswith(TAG_ROOT):
            return name
        for k in kinds:
            if TAG_ROOT + k + "." + name in self.info:
                return TAG_ROOT + k + "." + name
        return None

    def kind(self, item):
        """The item's kind: its "kind", or the kind of the item it's "like"."""
        like = self.full(item["like"]) if item.get("like") else None
        return item.get("kind") or ("consumable" if like and ".Consumable." in like else
                                    "material" if like and ".Materials." in like else None)

    def item(self, item, made):
        """(tag, {"info": row values, "use": Consumables row, "recipe": BarteringCost row}) for an item."""
        like = None
        if item.get("like"):
            like = self.full(item["like"])
            if like is None or like not in self.info:
                raise ValueError(f"\"like\": the game has no item {item['like']}")
        kind = self.kind(item)
        if kind not in KINDS:
            raise ValueError('"kind" should be "consumable" or "material" (or give "like")'
                             if kind is None or kind != "accessory" else
                             "new accessories need art of their own (a texture for the cat to wear), which "
                             "wcmods can't make yet; see docs/SDK.md")
        if like and KINDS[kind] not in like:
            raise ValueError(f"\"like\" {like} isn't a {kind}")
        tag = f"{TAG_ROOT}{KINDS[kind]}.{item['id']}"
        if tag in self.info or tag in self.use:
            raise ValueError(f"the game already has {tag}; change it with data.json instead")
        if tag in made:
            raise ValueError(f"{made[tag]} adds {tag} too")
        base = self.info.get(like, {})
        info = {"itemTag": tag,
                "Icon": self.icon(item.get("icon"), base),
                "ItemRarity": _enum("rarity", item.get("rarity"), cooked.ITEM_RARITY, base.get("ItemRarity", 0)),
                "ItemGroupIcon": _enum("group", item.get("group"), cooked.ITEM_GROUP_ICON, base.get("ItemGroupIcon", 0)),
                "ItemCategoryColor": _enum("color", item.get("color"), cooked.ITEM_CATEGORY_COLOR,
                                           base.get("ItemCategoryColor", 0))}
        rows = {"info": info}
        if kind == "consumable":
            rows["use"] = self.consumable(tag, item, self.use.get(like, {}))
        elif any(item.get(k) is not None for k in ("effect", "type", "target", "combat", "exploring", "fight_only")):
            raise ValueError("materials can't be used, so they take no effect, type, target or when to use them")
        if item.get("recipe"):
            if kind != "consumable":
                raise ValueError("the medicine cat's bartering only makes herbs and accessories, not materials")
            rows["recipe"] = {"---": tag, "Cost": self.cost(item["recipe"], made), "bIsHidden": "FALSE"}
        give = item.get("give")
        if give is not None and (not isinstance(give, int) or isinstance(give, bool) or not 0 < give <= 999):
            raise ValueError('"give" should be a whole number from 1 to 999')
        return tag, rows

    def icon(self, icon, base):
        if not icon:
            if not base:
                raise ValueError('"icon" is missing: give an item to borrow the icon of, or a texture '
                                 '("/Game/Art/UXD/Textures/...")')
            return base["Icon"]
        if icon.startswith("/Game/"):
            if not self.ctx.game.exists(cooked.game_file(icon)):
                raise ValueError(f"\"icon\": the game has no texture {icon}")
            return cooked.soft_path(icon)
        other = self.full(icon)
        if other is None or other not in self.info:
            raise ValueError(f"\"icon\": the game has no item {icon} to borrow the icon of")
        return self.info[other]["Icon"]

    def consumable(self, tag, item, like):
        effect = item.get("effect", like.get("EffectOnUse"))
        if effect not in self.effects:
            raise ValueError(f"\"effect\" should be one the game's herbs use: {', '.join(self.effects)}"
                             if effect else "\"effect\" is missing (or give \"like\")")
        same = next((r for r in self.use.values() if r["EffectOnUse"] == effect), {})
        like = like or same
        kind = item.get("type", like.get("Type"))
        if kind not in self.types:
            raise ValueError(f"\"type\" should be one of {', '.join(self.types)}")
        target = item.get("target", like.get("Target", "Owner"))
        if target not in self.targets:
            raise ValueError(f"\"target\" should be one of {', '.join(self.targets)}")
        flags = {}
        for key, column in (("combat", "bCombat"), ("exploring", "bExploration"), ("fight_only", "bRemoveAfterCombat")):
            value = item.get(key)
            if value is None:
                flags[column] = like.get(column, "FALSE" if key == "fight_only" else "TRUE")
            elif isinstance(value, bool):
                flags[column] = "TRUE" if value else "FALSE"
            else:
                raise ValueError(f"\"{key}\" should be true or false")
        if flags["bCombat"] == "FALSE" and flags["bExploration"] == "FALSE":
            raise ValueError('an herb usable neither in fights nor while exploring can never be used')
        return {"---": tag, "EffectOnUse": effect, "bCombat": flags["bCombat"], "bExploration": flags["bExploration"],
                "Target": target, "bRemoveAfterCombat": flags["bRemoveAfterCombat"], "Type": kind}

    def cost(self, recipe, made):
        if not isinstance(recipe, dict):
            raise ValueError('"recipe" should map materials to how many, e.g. {"Dandelion": 2}')
        parts = []
        for name, n in recipe.items():
            tag = self.full(name, ("Materials",))
            if tag is None and f"{TAG_ROOT}Materials.{name}" in made:
                tag = f"{TAG_ROOT}Materials.{name}"
            if tag is None or not (tag in self.materials or tag in made):
                raise ValueError(f"\"recipe\": there's no material {name} (the game's are "
                                 f"{', '.join(sorted(t.rsplit('.', 1)[-1] for t in self.materials))})")
            if not isinstance(n, int) or isinstance(n, bool) or not 0 < n <= 99:
                raise ValueError(f"\"recipe\": {name} should be a whole number from 1 to 99")
            parts.append(f"{tag},{n}")
        if not parts:
            raise ValueError('"recipe" is empty')
        return ";".join(parts)


def _current_slot(ctx):
    """The save slot being played ("0".."8"), or None without a save."""
    sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
    if not os.path.isfile(sav):
        return None
    try:
        return str(SaveDoc(SaveGame.load(sav).json_text).get("Shared/General/CurrentCatSlot"))
    except (KeyError, IndexError, ValueError, TypeError):
        return "0"


def _rows(text):
    t = csvdata.Table(text)
    return {r.fields[0]: dict(zip(t.header, r.fields)) for r in t.rows if r.fields}


def _enum(key, value, names, default):
    if value is None:
        return default
    if value not in names:
        raise ValueError(f"\"{key}\" should be one of {', '.join(names)}")
    return names[value]
