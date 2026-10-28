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
game's list of its looks, in the GUI manager Blueprint (accessories.py). An accessory's "model" (an OBJ
or glTF file in the mod's folder) gives that look a shape of its own: a copy of the accessory's mesh
with the model in it, tied to the cat's body (models.py, formats/skelmesh.py), which the in-game script
WCModsModels puts on any cat wearing the look. "place" moves, turns and scales that shape (or the
accessory's own, as a copy) where it sits on the cat. "opacity" below 1 lets the cat show through it: the
script wears it in the cats' eye glass then, in its "glass" colour, as no see-through material the game
has for cats shows a picture.

A herb's or a material's "model" is how it lies on the ground as a pickup (a script's Game.items.drop,
a story's reward), with "texture" (a PNG) painted on it and "place" to move, turn and size it there: a
copy of an accessory's mesh with the model on its root bone, which WCModsGame shows in place of the
pickup's own when it drops one. The install lists them in the shared Lua module WCModsItems. Without a
model, a herb lies there as the game's pickup of the herb it's "like", when the game has one.

"like" names a game item to start from (its effect, when it can be used, icon and icon group); the
item's own keys override those. "recipes" changes what the medicine cat wants for one of the game's
items, by its tag (with or without "Gameplay.Inventory."). See docs/SDK.md for every key.
"""
import hashlib
import json
import os
import re

from .. import accessories, colors, models, names, recolor
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
        "fight_only", "group", "rarity", "color", "recipe", "give", "texture", "model", "place", "opacity", "glass"}
# The game's inventory icon a new icon is a copy of (512 x 512, DXT5).
ICON_LIKE = "/Game/Art/UXD/Textures/gui_icons/gui_icons_inventory/T_UI_Icon_Inventory_Horsetail_D"
TEXT_KEYS = ("kind", "like", "effect", "type", "target", "group", "rarity", "color")
PICTURE_KEYS = ("icon", "texture")         # text, or a recolour: {"from": ..., "tint": "#rrggbb", ...}
FLAG_KEYS = ("combat", "exploring", "fight_only")
MODELS_SCRIPT = "WCModsModels"            # the in-game script that puts mods' models on the cats wearing them
SLOT_FIELDS = {"Head": "Head", "Neck": "Neck", "Body": "Body", "Legs": "Paw"}   # tag slot -> the cat's CustomData
GLASS = "#ffffff"                         # a see-through accessory's colour, unless it says
# What makes a new accessory look its own: without one of these it would be the look it's "like" again. Said
# in the Items page's words; docs/SDK.md has the keys for a hand-written file.
OWN_LOOK = ("texture", "model", "place", "opacity")
NOTHING_OWN = "it has nothing of its own yet: choose a colour or a picture under Look, or a model"
ACCESSORY_LIKE = re.compile(r"(Gameplay\.Inventory\.)?Cosmetic\.|(Head|Neck|Body|Legs)\.")
PICTURE_FILES = (".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tga", ".dds")   # pictures, but not PNGs
ITEMS_LUA = "WCModsItems"                 # the shared Lua module that tells WCModsGame how mod items look on the ground
PICKUPS = "Wrc/Content/Gameplay/Blueprints/WorldElements/Pickups/BP_Pickup_"   # the game's pickups, one class each
# The accessory a model on the ground is a copy of: one LOD, no body-shape morphs, the accessories' usual
# material (M_Characters_NPC), whose look's texture a picture is a copy of (2048 x 2048, as herbs' are).
GROUND_LIKE = "SharpBonePiercing"
GROUND_PLAIN = (200, 196, 186)            # a model on the ground without a picture: a plain light grey
# Under a model's picture, its ARM (ambient occlusion, roughness, metal) is all-lit, quite rough, not
# metal, and its normal map flat, in place of the copied accessory's.
GROUND_ARM = (255, 204, 0)
FLAT_NORMAL = "/Engine/EngineMaterials/FlatNormal.FlatNormal"
# What using each of the game's herbs does, in a creator's words, by its short id (docs/mechanics/items.md,
# "What consumables do", one herb a row). The Items page names an effect by these words and the herb that
# has it ("Heals 50 health (Marigold Petal)"); a herb a game update adds is named the old way until it's here.
EFFECT_WORDS = {
    "SmallHealingHerb": "Heals 25 health",
    "MediumHealingHerb": "Heals 50 health",
    "BigHealingHerb": "Heals 100 health",
    "FullHealingHerb": "Heals to full health",
    "SuperHealingHerb": "Full health, and maybe cures (not checked)",
    "HealingHerbPouch": "Heals the whole team 50 health",
    "SmallCatnip": "+25 stamina",
    "MediumCatnip": "+50 stamina",
    "BigCatnip": "+100 stamina",
    "CatnipPouch": "Whole team +50 stamina",
    "ThistlePouch": "Whole team +50% Strength for the fight",
    "FishScalePouch": "Whole team +50% Resilience for the fight",
    "CatThymePouch": "Whole team +50% Instinct for the fight",
    "FeatherPouch": "Whole team +50% Agility for the fight",
    "HerbSpicesPouch": "Berserk for the fight",
    "EyewortPouch": "Cures Blinded",
    "ChamomilePouch": "Cures Furious",
    "AntidoteHerbPouch": "Cures Poisoned",
    "ValerianRootPouch": "Cures Stressed",
    "PeppermintPouch": "Whole team's Offensive stance stronger for a round",
    "GingerRootPouch": "Whole team's Defensive stance stronger for a round",
    "ChestnutPouch": "Whole team's Trick stance stronger for a round",
    "LavenderPouch": "Whole team's Sneaky stance stronger for a round",
    "TurmericPouch": "Whole team's Reckless stance stronger for a round",
    "SagePouch": "+200 XP",
}


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
        kept = []
        for i, item in enumerate(items):
            what = f"items.json: item {i + 1}"
            unknown = sorted(k for k in item if k not in KEYS and not k.startswith("_"))
            if unknown:
                raise ValueError(f"{what}: unknown key(s) {', '.join(unknown)} (docs/SDK.md lists them)")
            if not isinstance(item.get("id"), str) or not ID.match(item["id"]):
                raise ValueError(f"{what}: \"id\" should be letters and digits, starting with a letter (e.g. \"MoonHerb\")")
            for key in ("name", "description"):
                if item.get(key) is not None and not isinstance(item[key], str):
                    raise ValueError(f"{what} ({item['id']}): \"{key}\" should be text")
            # One the Items page saved half made: the others still go in, and the save says so.
            blank = next((key for key in ("name", "description") if not (item.get(key) or "").strip()), None)
            if blank:
                if ctx is not None:
                    ctx.warn(f"{mod.id}: {item['id']}: it has no {blank}, so it's left out of the game")
                continue
            if _accessory(item) and item.get("like") and all(item.get(k) is None for k in OWN_LOOK):
                if ctx is not None:
                    ctx.warn(f"{mod.id}: {item['id']}: {NOTHING_OWN}, so it's left out of the game")
                continue
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
            model = item.get("model")
            if model is not None and (not isinstance(model, str) or not model.lower().endswith(models.FORMATS)):
                raise ValueError(f"{what} ({item['id']}): \"model\" should be a model file in the mod's folder "
                                 f"({', '.join(models.FORMATS)}), e.g. \"models/my-collar.obj\"")
            if item.get("place") is not None:
                models.check_place(item["place"], f"{what} ({item['id']})")
            opacity = item.get("opacity")
            if opacity is not None and (isinstance(opacity, bool) or not isinstance(opacity, (int, float))
                                        or not 0 <= opacity <= 1):
                raise ValueError(f"{what} ({item['id']}): \"opacity\" should be a number from 0 (none of it shows) "
                                 "to 1 (all of it)")
            if item.get("glass") is not None:
                try:
                    colors.parse(item["glass"])
                except ValueError:
                    raise ValueError(f"{what} ({item['id']}): \"glass\" should be a colour like \"#a8e0ff\"") from None
            for key in FLAG_KEYS:
                if item.get(key) is not None and not isinstance(item[key], bool):
                    raise ValueError(f"{what} ({item['id']}): \"{key}\" should be true or false")
            if item.get("recipe") is not None and not isinstance(item["recipe"], dict):
                raise ValueError(f"{what} ({item['id']}): \"recipe\" should map materials to how many")
            kept.append(item)
        return {"items": kept, "recipes": recipes} if kept or recipes else None

    def build(self, ctx, items):
        game = Game(ctx)
        slot = _current_slot(ctx)
        made = {}                      # tag -> mod id
        who = {}                       # "<mod>/<id>" -> tag: the build's note, for the Items page
        looks = []                     # new accessory looks, for the GUI manager's lists
        worn = {}                      # the cat's slot -> accessory -> look number -> {"mesh", "opacity", "glass"}
        ground = {}                    # tag -> how a herb or a material lies on the ground (WCModsItems)
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
                    # Named by its kind too: a herb and a material may share an id.
                    asset = ctx.add_texture(f"{mod.id}/T_{KINDS[game.kind(item)]}_{item['id']}_Icon", lambda: icon.read(mod, ctx),
                                            like_icon, source=mod.id, key=icon.key(mod, ctx))
                    rows["info"]["Icon"] = cooked.soft_path(asset)
                if look:                             # the accessory's new look: a copy of its texture
                    picture, shape, spot = look["picture"], look["model"], item.get("place")
                    mesh = None
                    if shape is not None:            # a shape of its own: a copy of the accessory's mesh
                        mesh = ctx.add_mesh(f"{mod.id}/SK_{item['id']}", lambda: models.place(shape.read(mod, ctx), spot),
                                            look["mesh"], source=f"{mod.id}: {item['id']}",
                                            key=f"{shape.key(mod, ctx)}|{json.dumps(spot, sort_keys=True)}")
                    asset = look["like"]             # a model without a picture of its own wears the look's
                    if picture is not None:
                        asset = ctx.add_texture(f"{mod.id}/T_{item['id']}_BC", lambda: picture.read(mod, ctx),
                                                look["like"], source=mod.id, key=picture.key(mod, ctx))
                    looks.append({"name": look["name"], "var": look["var"], "path": asset, "tag": tag})
                    see_through = item.get("opacity") is not None and item["opacity"] < 1
                    if mesh or see_through:          # what the WCModsModels script does when a cat wears it
                        entry = {"mesh": mesh} if mesh else {}
                        if see_through:
                            entry["opacity"] = float(item["opacity"])
                            entry["glass"] = [round(c, 4) for c in colors.to_linear(colors.parse(item.get("glass", GLASS)))]
                        worn.setdefault(SLOT_FIELDS[look["slot"]], {}).setdefault(look["name"], {})[look["var"]] = entry
                    game.added[look["name"]] = game.added.get(look["name"], 0) + 1
                pickup = rows.get("pickup")
                entry = None
                if pickup and pickup["model"] is not None:   # a model of its own on the ground
                    try:
                        entry = ground_model(ctx, game, mod, item, tag, pickup)
                    except ValueError as e:                    # the item's still good, only its look there isn't
                        ctx.warn(f"{mod.id}: {item['id']}: its model on the ground: {e}; it lies there as the game's "
                                 "pickup instead")
                if entry is None and pickup and pickup["class"]:
                    entry = {"class": pickup["class"]}
                if entry:
                    ground[tag] = entry
            except ValueError as e:
                ctx.warn(f"{mod.id}: {item['id']}: {e}")
                continue
            made[tag] = mod.id
            key = f"{mod.id}/{item['id']}"     # a herb and a material may share an id: then both, in a list
            who[key] = [*who[key], tag] if isinstance(who.get(key), list) else [who[key], tag] if key in who else tag
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
        if worn:
            if not ctx.cfg.ue4ss_mods_dir:
                ctx.warn("accessories with a model, a place or an opacity of their own need the script loader (UE4SS), "
                         "which isn't installed: Get set up on the Mods page adds it. Until then they show as the "
                         "game's shape, solid")
            ctx.add_ue4ss_mod(MODELS_SCRIPT, {"Scripts/main.lua": models.script(worn), "enabled.txt": ""})
            ctx.note("models", {slot: {name: sorted(v) for name, v in byname.items()} for slot, byname in worn.items()})
        if ground:
            if not ctx.cfg.ue4ss_mods_dir and any("mesh" in g for g in ground.values()):
                ctx.warn("herbs and materials lie on the ground only where a script drops them, and scripts need the "
                         "script loader (UE4SS), which isn't installed: Get set up on the Mods page adds it")
            ctx.add_ue4ss_shared(ITEMS_LUA, items_lua(ground))
            ctx.note("ground", sorted(t[len(TAG_ROOT):] for t, g in ground.items() if "mesh" in g))
        if made:
            lines = ["[/Script/GameplayTags.GameplayTagsList]"]
            lines += [f'GameplayTagList=(Tag="{tag}",DevComment="wcmods: {by}")' for tag, by in sorted(made.items())]
            ctx.add_file(TAGS_INI, ("\r\n".join(lines) + "\r\n").encode("utf-8"), source="items")
            ctx.note("items", dict(sorted(who.items())))   # each item by its mod and id: an accessory's tag is a look number


def ground_model(ctx, game, mod, item, tag, pickup):
    """{"mesh", "texture", "arm", "normal", "class"}: a herb's or a material's model on the ground, made
    into a copy of GROUND_LIKE's mesh, with its picture a copy of that accessory's look."""
    shape, spot, picture = pickup["model"], item.get("place"), pickup["picture"]
    name = f"{mod.id}/{tag[len(TAG_ROOT):].split('.')[0]}_{item['id']}"     # a herb and a material may share an id
    mesh = ctx.add_mesh(f"{name}_SK", lambda: models.place(shape.read(mod, ctx), spot, base=True), game.ground_mesh(),
                        source=f"{mod.id}: {item['id']}", key=f"{shape.key(mod, ctx)}|{json.dumps(spot, sort_keys=True)}",
                        on_cat=False)
    if picture is None:
        look = game.ground_plain()
    else:
        look = ctx.add_texture(f"{name}_BC", lambda: picture.read(mod, ctx), game.ground_look(), source=mod.id,
                               key=picture.key(mod, ctx))
    out = {"mesh": mesh, "texture": look, "arm": game.ground_arm(), "normal": FLAT_NORMAL}
    if pickup["class"]:
        out["class"] = pickup["class"]
    return out


def items_lua(ground):
    """The WCModsItems module: {tag: {"mesh", "texture", "arm", "normal", "class"}} for the herbs and
    materials of the mods that look their own way on the ground (each key there only when it has one)."""
    from ..sdk import lua_value
    return ("-- Written by wcmods from your mods' items.json: how their herbs and materials look on the ground.\n"
            "-- Do not edit; edit items.json (or the Items page in Clan Mod Studio) and install again.\n"
            "-- WCModsGame's Game.items.drop reads it: a mesh with its picture in place of the pickup's own, or\n"
            "-- the game's pickup (class) of the herb an item is like.\n"
            f"return {{ pickups = {lua_value(ground)} }}\n")


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
        self._meshes = None
        self._pickups = None
        self._plain = {}               # the shared plain textures under models on the ground: "arm", "look"

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
            for key in ("opacity", "glass"):
                if item.get(key) is not None:
                    raise ValueError(f'only accessories take "{key}": a herb\'s or a material\'s model is solid')
            pickup = self.pickup(item, like)
            tag = f"{TAG_ROOT}{KINDS[kind]}.{item['id']}"
        if tag in self.info or tag in self.use:
            # Said where the Items page shows it; docs/SDK.md says how to change the game's own (data.json).
            raise ValueError(f"the game already has an item called {item['id']}: give yours another name")
        if tag in made:
            raise ValueError(f"{made[tag]} adds an item called {item['id']} too, and comes later, so its item is used")
        base = self.info.get(like, {})
        info = {"itemTag": tag,
                "Icon": self.icon(item.get("icon"), base),
                "ItemRarity": _enum("rarity", item.get("rarity"), cooked.ITEM_RARITY, base.get("ItemRarity", 0)),
                "ItemGroupIcon": _enum("group", item.get("group"), cooked.ITEM_GROUP_ICON, base.get("ItemGroupIcon", 0)),
                "ItemCategoryColor": _enum("color", item.get("color"), cooked.ITEM_CATEGORY_COLOR,
                                           base.get("ItemCategoryColor", 0))}
        rows = {"info": info}
        if kind != "accessory":
            rows["pickup"] = pickup
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
        shape = ModelFile(item["model"]) if item.get("model") else None
        if shape is None and item.get("place"):
            shape = GameShape(self.meshes().get(name))      # the accessory's own shape, put elsewhere
        if isinstance(spec, dict):
            if spec.get("from") is not None:
                raise ValueError('an accessory\'s "texture" recolours its own look, so it takes no "from"')
            picture = Recolour(spec, base)
        elif isinstance(spec, str) and spec.lower().endswith(".png"):
            picture = Picture(spec)
        elif spec is None and (shape is not None or item.get("opacity") is not None):
            picture = None                       # it wears the look it's "like" as it is, in a new shape or see-through
        elif spec is None:
            raise ValueError(NOTHING_OWN)
        else:
            raise ValueError("its look should be a colour, or a PNG picture in the mod's folder")
        mesh = None
        if shape is not None:
            mesh = self.meshes().get(name)
            if mesh is None:
                raise ValueError(f"the game has no model for {name} to copy")
        return {"slot": slot, "name": name, "var": len(lists[name]) + self.added.get(name, 0) + 1,
                "like": base, "picture": picture, "model": shape, "mesh": mesh}

    def meshes(self):
        """The game's model for each accessory: {name: skeletal mesh asset path}."""
        if self._meshes is None:
            self._meshes = accessories.read_meshes(self.ctx.read_game_file(accessories.GUI_MANAGER))
        return self._meshes

    def pickup(self, item, like):
        """How a herb or a material lies on the ground: {"model" (a ModelFile, or None), "picture" (a Picture,
        or None), "class"}, class being the game's pickup of the item it's like (BP_Pickup_<class>), if any."""
        spec = item.get("texture")
        if spec is not None and not (isinstance(spec, str) and spec.lower().endswith(".png")):
            raise ValueError('a herb\'s or a material\'s "texture" is a picture (a PNG) painted on its "model"; its '
                             'picture in the inventory is its "icon"')
        if item.get("model") is None:
            for key in ("texture", "place"):
                if item.get(key) is not None:
                    raise ValueError(f'"{key}" goes with a "model": how the item looks on the ground')
        if self._pickups is None:
            self._pickups = {p[len(PICKUPS):-len(".uasset")] for p in self.ctx.game.find(PICKUPS + "*.uasset")}
        short = like.rsplit(".", 1)[-1] if like else None
        return {"model": ModelFile(item["model"]) if item.get("model") else None,
                "picture": Picture(spec) if spec else None,
                "class": short if short in self._pickups else None}

    def ground_mesh(self):
        """The mesh a model on the ground is a copy of (its asset path)."""
        mesh = self.meshes().get(GROUND_LIKE)
        if mesh is None:
            raise ValueError(f"the game has no {GROUND_LIKE} mesh to make a model on the ground from")
        return mesh

    def ground_look(self):
        """The texture a model on the ground's picture is a copy of (its asset path)."""
        looks = self.looks().get(GROUND_LIKE)
        if not looks:
            raise ValueError(f"the game has no {GROUND_LIKE} look to make a picture on the ground from")
        return looks[0]

    def ground_arm(self):
        """The plain ARM texture under every model on the ground's picture, made once an install."""
        like = self.ground_look().replace("_BC", "_ARM")
        if "arm" not in self._plain and not self.ctx.game.exists(texture.content_path(like.split(".", 1)[0])):
            raise ValueError(f"the game has no {like} to make a plain ARM texture from")
        return self._shared_plain("arm", "_items/T_GroundARM", GROUND_ARM, like)

    def ground_plain(self):
        """The one plain grey picture for models on the ground without one of their own."""
        return self._shared_plain("look", "_items/T_GroundPlain", GROUND_PLAIN, self.ground_look())

    def _shared_plain(self, what, name, rgb, like):
        if what not in self._plain:
            plain = Plain(rgb)
            self._plain[what] = self.ctx.add_texture(name, plain.read, like, source="items", key=plain.key())
        return self._plain[what]

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
        if os.path.splitext(icon)[1].lower() in PICTURE_FILES or "/" in icon and not icon.startswith("/Game/"):
            raise ValueError(f"\"icon\": icons are PNG pictures, and {icon} isn't one (save it as .png)")
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


class ModelFile:
    """A model in the mod's folder (models.py: .obj, .gltf, .glb), made into a mesh once the item is
    known to be good."""
    what = "model"                 # what the messages call it

    def __init__(self, rel):
        self.rel = rel

    def _path(self, mod, rel):
        folder = os.path.realpath(mod.folder)
        path = os.path.realpath(os.path.join(folder, os.path.dirname(self.rel), rel))
        if os.path.commonpath([folder, path]) != folder:
            raise ValueError(f"{self.rel}: {self.what}s must be in the mod's own folder")
        return path

    def _bytes(self, mod, rel=None):
        path = self._path(mod, rel or os.path.basename(self.rel))
        if not os.path.isfile(path):
            raise ValueError(f"there's no {self.what if rel is None else 'file'} {rel or self.rel} in the mod's folder")
        with open(path, "rb") as f:
            return f.read()

    def key(self, mod, ctx=None):
        """Text that changes when the model does (with a .gltf, the files it names too), for the mesh cache."""
        data = self._bytes(mod)
        h = hashlib.sha1(data)
        if self.rel.lower().endswith(".gltf"):
            try:
                for b in json.loads(data.decode("utf-8")).get("buffers", []):
                    uri = b.get("uri") or ""
                    if uri and not uri.startswith("data:"):
                        h.update(self._bytes(mod, uri))
            except (ValueError, AttributeError):
                pass                             # read() says what's wrong with it
        return "model|" + h.hexdigest()

    def read(self, mod, ctx=None):
        """The model (models.Model)."""
        def sibling(name):
            try:
                return self._bytes(mod, name)
            except ValueError:
                return None
        try:
            return models.read(self.rel, self._bytes(mod), sibling)
        except ValueError as e:
            raise ValueError(f"{self.rel}: {e}") from None


class GameShape:
    """An accessory's own shape (its mesh's first LOD), as a model to place somewhere else on the cat."""

    def __init__(self, mesh):
        self.mesh = mesh                          # its asset path

    def key(self, mod, ctx):
        return "game|" + self.mesh

    def read(self, mod, ctx):
        from ..formats import skelmesh
        if not self.mesh:
            raise ValueError("the game has no model for this accessory to place")
        return models.from_mesh(skelmesh.SkeletalMesh(ctx.read_game_file(texture.content_path(self.mesh.split(".", 1)[0]))))


class Plain:
    """A picture of one colour, for a model without one of its own: as big as the texture it goes in
    (the accessories' looks are 2048 x 2048), so it isn't scaled up pixel by pixel."""

    def __init__(self, rgb, size=2048):
        self.rgb, self.size = tuple(rgb), size

    def key(self, mod=None, ctx=None):
        return "plain|" + ",".join(map(str, self.rgb))

    def read(self, mod=None, ctx=None):
        return self.size, self.size, bytes(self.rgb + (255,)) * (self.size * self.size)


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


def _accessory(item):
    """Whether an item is an accessory, from its "kind" or the look it's "like", without the game's tables."""
    if item.get("kind") is not None:
        return item["kind"] == "accessory"
    like = item.get("like")
    return isinstance(like, str) and ACCESSORY_LIKE.match(like) is not None


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
