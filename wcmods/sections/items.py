"""New items (items.json): herbs, materials and accessories of a mod's own, with a name, a description,
an icon (the game's, or a picture of the mod's own), what they do, a recipe at the medicine cat's
bartering, and some to start with; and new recipes for the game's own herbs and accessories.

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
  * its gameplay tag (Gameplay.Inventory.Consumable.<id> or ...Materials.<id>; an accessory's is the
    next variation of the accessory it's "like", Gameplay.Inventory.Cosmetic.Neck.DogCollar.3), in an
    ini under Wrc/Config/Tags, which the game registers at startup;
  * for a herb, a Consumables.csv row: what using it does, and when;
  * a row in the cooked DT_QuestObjectsInfo table: its name, description and icon (the inventory leaves
    out items without one);
  * for "recipe", a BarteringCost.csv row, and for "give", the item in your save (once).
A picture of the mod's own ("icon" or an accessory's "texture", a PNG), or one of the game's in other
colours ({"from": ..., "tint": "#a8c4ff"}, made from the player's own game files), becomes a new
texture, a copy of one of the game's (texture.py, recolor.py). An accessory's new look goes into the
game's list of its looks, in the GUI manager Blueprint (accessories.py).

"like" names a game item to start from (its effect, when it can be used, icon and icon group); the
item's own keys override those. "recipes" changes what the medicine cat wants for one of the game's
items, by its tag (with or without "Gameplay.Inventory."). See docs/SDK.md for every key.
"""
import hashlib
import json
import os
import re

from .. import accessories, names, recolor
from ..formats import cooked, csvdata, png, texture
from ..formats.save import SAV_NAME, SaveGame
from ..formats.savejson import SaveDoc
from ..sdk import Section

TAG_ROOT = "Gameplay.Inventory."
KINDS = {"consumable": "Consumable", "material": "Materials", "accessory": "Cosmetic"}
TAGS_INI = "Wrc/Config/Tags/WCModsItems.ini"
INVENTORY = "GameplayProgression/State/Inventory"     # in the save slot being played
TABLE = "DT_QuestObjectsInfo"
ID = re.compile(r"[A-Za-z][A-Za-z0-9]{0,47}$")
KEYS = {"id", "kind", "like", "name", "description", "icon", "effect", "type", "target", "combat", "exploring",
        "fight_only", "group", "rarity", "color", "recipe", "give", "texture"}
# The game's inventory icon a new icon is a copy of (512 x 512, DXT5).
ICON_LIKE = "/Game/Art/UXD/Textures/gui_icons/gui_icons_inventory/T_UI_Icon_Inventory_Horsetail_D"
TEXT_KEYS = ("kind", "like", "effect", "type", "target", "group", "rarity", "color")
PICTURE_KEYS = ("icon", "texture")         # text, or a recolour: {"from": ..., "tint": "#rrggbb", ...}
FLAG_KEYS = ("combat", "exploring", "fight_only")


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
            for key in TEXT_KEYS:
                if item.get(key) is not None and not isinstance(item[key], str):
                    raise ValueError(f"{what} ({item['id']}): \"{key}\" should be text")
            for key in PICTURE_KEYS:
                v = item.get(key)
                if isinstance(v, dict):
                    recolor.check(v, f"{what} ({item['id']}): \"{key}\"")
                    if v.get("from") is not None and not isinstance(v["from"], str):
                        raise ValueError(f"{what} ({item['id']}): \"{key}\".from should be text")
                elif v is not None and not isinstance(v, str):
                    raise ValueError(f"{what} ({item['id']}): \"{key}\" should be text or a recolour")
            for key in FLAG_KEYS:
                if item.get(key) is not None and not isinstance(item[key], bool):
                    raise ValueError(f"{what} ({item['id']}): \"{key}\" should be true or false")
            if item.get("recipe") is not None and not isinstance(item["recipe"], dict):
                raise ValueError(f"{what} ({item['id']}): \"recipe\" should map materials to how many")
        return {"items": items, "recipes": recipes} if items or recipes else None

    def build(self, ctx, items):
        game = Game(ctx)
        slot = _current_slot(ctx)
        made = {}                      # tag -> mod id
        looks = []                     # new accessory looks, for the GUI manager's lists
        # Materials first, so a mod's herb can be made from a material it adds; and the highest priority
        # mod first, so where two add the same item, the later one wins as everywhere else.
        ordered = sorted(((mod, item) for mod, data in reversed(items) for item in data["items"]),
                         key=lambda mi: game.kind(mi[1]) != "material")
        for mod, item in ordered:
            try:
                tag, rows = game.item(item, made)
                look = rows.get("look")
                icon = rows["info"]["Icon"]
                if isinstance(icon, (Picture, Recolour)):        # a new texture for the icon
                    like_icon = icon.source if isinstance(icon, Recolour) else rows.get("icon_like", ICON_LIKE)
                    asset = ctx.add_texture(f"{mod.id}/T_{item['id']}_Icon", lambda: icon.read(mod, ctx),
                                            like_icon, source=mod.id, key=icon.key(mod, ctx))
                    rows["info"]["Icon"] = cooked.soft_path(asset)
                if look:                             # the accessory's new look: a copy of its texture
                    picture = look["picture"]
                    asset = ctx.add_texture(f"{mod.id}/T_{item['id']}_BC", lambda: picture.read(mod, ctx),
                                            look["like"], source=mod.id, key=picture.key(mod, ctx))
                    looks.append({"name": look["name"], "var": look["var"], "path": asset, "tag": tag})
                    game.added[look["name"]] = game.added.get(look["name"], 0) + 1
            except ValueError as e:
                ctx.warn(f"{mod.id}: {item['id']}: {e}")
                continue
            made[tag] = mod.id
            text = f"{TAG_ROOT}{mod.id}.{item['id']}"
            # The row's name, from the tag: a herb and a material may share an id.
            row = "WCMods_" + tag[len(TAG_ROOT):].replace(".", "_")
            ctx.add_table_row(TABLE, row, dict(rows["info"], **{
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
        if looks:
            data = accessories.add_looks(ctx.read_game_file(accessories.GUI_MANAGER), looks)
            ctx.patch_package(accessories.GUI_MANAGER, data, source="items")
            ctx.note("looks", [f"{e['name']} {e['var']}" for e in looks])
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
        self.added = {}                # accessory name -> new looks given out so far
        self._looks = None

    def looks(self):
        """The game's looks for each accessory: {name: [texture asset paths]} (variation n is [n - 1])."""
        if self._looks is None:
            self._looks = accessories.read_variations(self.ctx.read_game_file(accessories.GUI_MANAGER))
        return self._looks

    def full(self, name, kinds=("Consumable", "Materials", "Cosmetic")):
        """An item tag from a short name ("Dandelion", "Neck.DogCollar.1") or the whole tag."""
        if name.startswith(TAG_ROOT):
            return name
        if name.startswith("Cosmetic."):
            return TAG_ROOT + name
        for k in kinds:
            if TAG_ROOT + k + "." + name in self.info:
                return TAG_ROOT + k + "." + name
        return None

    def kind(self, item):
        """The item's kind: its "kind", or the kind of the item it's "like"."""
        like = self.full(item["like"]) if item.get("like") else None
        return item.get("kind") or ("consumable" if like and ".Consumable." in like else
                                    "material" if like and ".Materials." in like else
                                    "accessory" if like and ".Cosmetic." in like else None)

    def item(self, item, made):
        """(tag, {"info": row values, "use": Consumables row, "recipe": BarteringCost row}) for an item."""
        like = None
        if item.get("like"):
            like = self.full(item["like"])
            if like is None or like not in self.info:
                raise ValueError(f"\"like\": the game has no item {item['like']}")
        kind = self.kind(item)
        if kind not in KINDS:
            raise ValueError('"kind" should be "consumable", "material" or "accessory" (or give "like")')
        if like and f".{KINDS[kind]}." not in like:
            raise ValueError(f"\"like\" {like} isn't a {kind}")
        look = None
        if kind == "accessory":
            look = self.look(item, like)
            tag = f"{TAG_ROOT}Cosmetic.{look['slot']}.{look['name']}.{look['var']}"
        else:
            if item.get("texture") is not None:
                raise ValueError('only accessories take a "texture" (their look); an item\'s picture is its "icon"')
            tag = f"{TAG_ROOT}{KINDS[kind]}.{item['id']}"
        if tag in self.info or tag in self.use:
            raise ValueError(f"the game already has {tag}; change it with data.json instead")
        if tag in made:
            raise ValueError(f"{made[tag]} adds {tag} too, and comes later, so its item is used")
        base = self.info.get(like, {})
        info = {"itemTag": tag,
                "Icon": self.icon(item.get("icon"), base),
                "ItemRarity": _enum("rarity", item.get("rarity"), cooked.ITEM_RARITY, base.get("ItemRarity", 0)),
                "ItemGroupIcon": _enum("group", item.get("group"), cooked.ITEM_GROUP_ICON, base.get("ItemGroupIcon", 0)),
                "ItemCategoryColor": _enum("color", item.get("color"), cooked.ITEM_CATEGORY_COLOR,
                                           base.get("ItemCategoryColor", 0))}
        rows = {"info": info}
        if look:
            rows["look"] = look
            if isinstance(info["Icon"], Picture):    # a copy of the accessory's own icon, for its format
                rows["icon_like"] = f"{base['Icon']['package']}.{base['Icon']['asset']}"
        if kind == "consumable":
            rows["use"] = self.consumable(tag, item, self.use.get(like, {}))
        elif any(item.get(k) is not None for k in ("effect", "type", "target", "combat", "exploring", "fight_only")):
            raise ValueError(f"{kind}s can't be used, so they take no effect, type, target or when to use them")
        if item.get("recipe"):
            if kind == "material":
                raise ValueError("the medicine cat's bartering only makes herbs and accessories, not materials")
            rows["recipe"] = {"---": tag, "Cost": self.cost(item["recipe"], made), "bIsHidden": "FALSE"}
        give = item.get("give")
        if give is not None and (not isinstance(give, int) or isinstance(give, bool) or not 0 < give <= 999):
            raise ValueError('"give" should be a whole number from 1 to 999')
        return tag, rows

    def look(self, item, like):
        """An accessory's new look: {"slot", "name", "var", "like" (the texture to copy), "picture"}."""
        if not like:
            raise ValueError('an accessory needs "like": the game accessory it is a new look of, e.g. "Neck.DogCollar.1"')
        parts = like[len(TAG_ROOT):].split(".")
        if len(parts) != 4 or not parts[3].isdigit():
            raise ValueError(f"\"like\" {like} isn't an accessory with a look (Cosmetic.<slot>.<name>.<n>)")
        _, slot, name, var = parts
        if slot == "Head":
            raise ValueError("the game always shows a head accessory's first look, so new looks can be neck, body "
                             "or paw accessories")
        lists = self.looks()
        if name not in lists:
            raise ValueError(f"the game has no list of looks for {name}, so it can't take a new one")
        if not 0 < int(var) <= len(lists[name]):
            raise ValueError(f"{name} has {len(lists[name])} look(s), not {var}")
        base = lists[name][int(var) - 1]
        spec = item.get("texture")
        if isinstance(spec, dict):
            if spec.get("from") is not None:
                raise ValueError('an accessory\'s "texture" recolours its own look, so it takes no "from"')
            picture = Recolour(spec, base)
        elif isinstance(spec, str) and spec.lower().endswith(".png"):
            picture = Picture(spec)
        else:
            raise ValueError('an accessory needs "texture": its new look, a recolour of its own ({"tint": "#a8c4ff"}) '
                             "or a PNG in the mod's folder (paint over the game's: python wcmods.py texture "
                             f"{like[len(TAG_ROOT):]})")
        return {"slot": slot, "name": name, "var": len(lists[name]) + self.added.get(name, 0) + 1,
                "like": base, "picture": picture}

    def icon(self, icon, base):
        if isinstance(icon, dict):                # the game's icon (or another texture) recoloured
            src = icon.get("from")
            if src is None:
                if not base:
                    raise ValueError('"icon": say which icon to recolour ("from": an item, or a texture "/Game/...")')
                return Recolour(icon, f"{base['Icon']['package']}.{base['Icon']['asset']}")
            if src.startswith("/Game/"):
                if not self.ctx.game.exists(cooked.game_file(src)):
                    raise ValueError(f"\"icon\": the game has no texture {src}")
                return Recolour(icon, src)
            other = self.full(src)
            if other is None or other not in self.info:
                raise ValueError(f"\"icon\": the game has no item {src} to recolour the icon of")
            soft = self.info[other]["Icon"]
            return Recolour(icon, f"{soft['package']}.{soft['asset']}")
        if not icon:
            if not base:
                raise ValueError('"icon" is missing: give a picture of your own ("icons/moon-herb.png"), an item '
                                 'to borrow the icon of, or a texture of the game\'s ("/Game/Art/UXD/Textures/...")')
            return base["Icon"]
        if icon.lower().endswith(".png"):
            return Picture(icon)
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
            # Only materials: the game's recipes never ask for a herb.
            if tag is None or not (tag in self.materials or (tag in made and tag.startswith(TAG_ROOT + "Materials."))):
                raise ValueError(f"\"recipe\": there's no material {name} (the game's are "
                                 f"{', '.join(sorted(t.rsplit('.', 1)[-1] for t in self.materials))})")
            if not isinstance(n, int) or isinstance(n, bool) or not 0 < n <= 99:
                raise ValueError(f"\"recipe\": {name} should be a whole number from 1 to 99")
            parts.append(f"{tag},{n}")
        if not parts:
            raise ValueError('"recipe" is empty')
        return ";".join(parts)


class Picture:
    """A PNG in the mod's folder, made into a texture once the item is known to be good."""

    def __init__(self, rel):
        self.rel = rel

    def _bytes(self, mod):
        folder = os.path.realpath(mod.folder)
        path = os.path.realpath(os.path.join(folder, self.rel))
        if os.path.commonpath([folder, path]) != folder:
            raise ValueError(f"{self.rel}: pictures must be in the mod's own folder")
        if not os.path.isfile(path):
            raise ValueError(f"there's no picture {self.rel} in the mod's folder")
        with open(path, "rb") as f:
            return f.read()

    def key(self, mod, ctx):
        """Text that changes when the picture does, for the texture cache."""
        return "png|" + hashlib.sha1(self._bytes(mod)).hexdigest()

    def read(self, mod, ctx):
        """(width, height, RGBA) of the picture."""
        try:
            return png.read(self._bytes(mod))
        except (ValueError, OSError) as e:
            raise ValueError(f"{self.rel}: {e}") from None
        except Exception as e:                  # a broken file: zlib.error, struct.error, ...
            raise ValueError(f"{self.rel} isn't a PNG wcmods can read ({type(e).__name__}: {e})") from None


class Recolour:
    """One of the game's textures in other colours (recolor.py), made from the player's game files."""

    def __init__(self, spec, source):
        self.spec, self.source = spec, source       # source: the texture's asset path

    def key(self, mod, ctx):
        """Text that changes when the recolour or the game's texture does, for the texture cache."""
        path = texture.content_path(self.source.split(".", 1)[0])
        data = ctx.game.read(path) if ctx.game.exists(path) else b""
        return f"recolour|{self.source}|{hashlib.sha1(data).hexdigest()}|{json.dumps(self.spec, sort_keys=True)}"

    def read(self, mod, ctx):
        w, h, rgba = texture.load(ctx.game, self.source).image(0)
        return w, h, recolor.apply(rgba, self.spec)


def _current_slot(ctx):
    """The save slot being played ("0".."8"), or None without a save."""
    sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
    if not os.path.isfile(sav):
        return None
    try:
        return names.current_slot(SaveDoc(SaveGame.load(sav).json_text).data)
    except ValueError:   # a save wcmods can't read: the first slot, as before
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
