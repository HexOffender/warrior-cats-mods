// studio/lib/items-model.js: the Items page's pure parts. An item's id, the items.json it saves, tags and
// kinds, what a new accessory look needs, the Kind switch, and the words for effects, who for and badges.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install } from "../lib/dom.mjs";

const dom = install();
const m = await import(dom.studio("lib/items-model.js"));

// A few of the game's items, as /game/items gives them.
const HERBS = [
  { tag: "Gameplay.Inventory.Consumable.SmallHealingHerb", short: "SmallHealingHerb", kind: "consumable", name: "Horsetail Stalks",
    effect: "Gameplay.Effect.Consumable.Health.1", type: "Health", target: "Owner", combat: true, exploring: true, fight_only: false, group: "Health", words: "Heals 25 health" },
  { tag: "Gameplay.Inventory.Consumable.MediumHealingHerb", short: "MediumHealingHerb", kind: "consumable", name: "Marigold Petal",
    effect: "Gameplay.Effect.Consumable.Health.2", type: "Health", target: "Owner", combat: true, exploring: true, fight_only: false, group: "Health", words: "Heals 50 health" },
  { tag: "Gameplay.Inventory.Consumable.HealingHerbPouch", short: "HealingHerbPouch", kind: "consumable", name: "Wintergreen Berries",
    effect: "Gameplay.Effect.Consumable.Health.2", type: "Health", target: "OwnerTeam", combat: true, exploring: true, fight_only: false, group: "Health", words: "Heals the whole team 50 health" },
  { tag: "Gameplay.Inventory.Consumable.ThistlePouch", short: "ThistlePouch", kind: "consumable", name: "Juniper Poultice",
    effect: "Gameplay.Effect.Consumable.Buff.Strength.1", type: "BuffStrength", target: "OwnerTeam", combat: true, exploring: false, fight_only: true, group: "Stats", words: "Whole team +50% Strength for the fight" },
  { tag: "Gameplay.Inventory.Consumable.NewOne", short: "NewOne", kind: "consumable", name: "Mystery Moss",
    effect: "Gameplay.Effect.Consumable.Glow.1", type: "Glow", target: "Owner", combat: true, exploring: true, fight_only: false, group: "Free" },
];
const byTag = new Map([...HERBS, { tag: "Gameplay.Inventory.Materials.Dandelion", short: "Dandelion", kind: "material", name: "Dandelion" }].map(i => [i.tag, i]));

test("itemId makes letters and digits from a name, unique among the mod's and the game's ids", () => {
  assert.equal(m.itemId("Moon Herb"), "MoonHerb");
  assert.equal(m.itemId("étoile du soir"), "EtoileDuSoir");
  assert.equal(m.itemId("123"), "Item123");
  assert.equal(m.itemId(""), "Item");
  assert.equal(m.itemId("Moon Herb", ["MoonHerb"]), "MoonHerb2");
  assert.equal(m.itemId("Moon Herb", ["moonherb", "MoonHerb2"]), "MoonHerb3", "ids that differ only in case are one file on Windows");
  assert.equal(m.itemId("Medium Healing Herb", [], ["MediumHealingHerb"]), "MediumHealingHerb2", "never one the game has");
  assert.equal(m.itemId("x".repeat(60)).length, 40);
});

test("toJson leaves out the page's _new, empty values and an empty recipe, and keeps hand-written notes", () => {
  const items = [{ id: "MoonHerb", name: "Moon Herb", description: "", icon: null, recipe: {}, _new: true, _note: "mine", give: 3 },
    { id: "Stone", kind: "material", name: "Stone", description: "A stone.", recipe: { Dandelion: 2 }, rarity: "Rare" }];
  const out = m.toJson(items, { recipes: { "Cosmetic.Head.MossPatch.1": { Moss: 3 } } });
  assert.deepEqual(out.items, [{ id: "MoonHerb", name: "Moon Herb", _note: "mine", give: 3 },
    { id: "Stone", kind: "material", name: "Stone", description: "A stone.", recipe: { Dandelion: 2 }, rarity: "Rare" }]);
  assert.deepEqual(out.recipes, { "Cosmetic.Head.MossPatch.1": { Moss: 3 } });
  assert.match(out._help, /Clan Mod Studio \(Items\)/);
});

test("fullTag and kindOf read the short names items.json uses", () => {
  assert.equal(m.fullTag("Neck.DogCollar.1", byTag), "Gameplay.Inventory.Cosmetic.Neck.DogCollar.1");
  assert.equal(m.fullTag("Cosmetic.Neck.DogCollar.2", byTag), "Gameplay.Inventory.Cosmetic.Neck.DogCollar.2");
  assert.equal(m.fullTag("Dandelion", byTag), "Gameplay.Inventory.Materials.Dandelion");
  assert.equal(m.fullTag("SmallHealingHerb", byTag), "Gameplay.Inventory.Consumable.SmallHealingHerb");
  assert.equal(m.fullTag("Gameplay.Inventory.Consumable.X", byTag), "Gameplay.Inventory.Consumable.X");
  assert.equal(m.fullTag("Nothing", byTag), null);
  assert.equal(m.fullTag("", byTag), null);
  assert.equal(m.kindOf({ like: "Dandelion" }, byTag), "material");
  assert.equal(m.kindOf({ kind: "accessory", like: "Dandelion" }, byTag), "accessory");
  assert.equal(m.kindOf({ like: "Nothing" }, byTag), null);
});

test("needsOwn: an accessory with no look, model, place or opacity of its own gets a colour back", () => {
  for (const own of [{ texture: { tint: "#fff" } }, { model: "models/a.glb" }, { place: { up: 1 } }, { opacity: 0.5 }]) {
    assert.equal(m.needsOwn({ like: "Neck.DogCollar.1", ...own }, "accessory"), false, JSON.stringify(own));
  }
  const bare = { like: "Neck.DogCollar.1" };
  assert.equal(m.needsOwn(bare, "accessory"), true);
  assert.equal(m.needsOwn(bare, "consumable"), false, "a herb's model is optional");
  assert.equal(m.giveOwn(bare, "accessory"), true);
  assert.deepEqual(bare.texture, { tint: m.NEW_LOOK });
  assert.equal(m.giveOwn(bare, "accessory"), false, "once is enough");
});

test("the Kind switch puts each kind's fields aside and brings them back, keeping the name and notes on the item", () => {
  const stash = new WeakMap();
  const start = kind => ({ consumable: "MediumHealingHerb", material: "Dandelion", accessory: "Cosmetic.Neck.DogCollar.1" })[kind];
  const it = { id: "Collar", kind: "accessory", like: "Cosmetic.Neck.DogCollar.1", name: "Collar", description: "Blue.", give: 2,
    texture: "pictures/c.png", model: "models/c.glb", place: { up: 1 }, opacity: 0.5, glass: "#fff", recipe: { Bone: 1 }, _note: "hand" };
  m.switchKind(it, "consumable", stash, start);
  assert.deepEqual(it, { id: "Collar", kind: "consumable", like: "MediumHealingHerb", name: "Collar", description: "Blue.", give: 2, _note: "hand" });
  it.effect = "Gameplay.Effect.Consumable.Health.1";
  m.switchKind(it, "accessory", stash, start);
  assert.deepEqual(it.place, { up: 1 });
  assert.equal(it.model, "models/c.glb");
  assert.deepEqual(it.recipe, { Bone: 1 });
  assert.equal(it.effect, undefined, "the herb's effect is put aside too");
  m.switchKind(it, "consumable", stash, start);
  assert.equal(it.effect, "Gameplay.Effect.Consumable.Health.1", "and comes back with the herb");
  assert.equal(JSON.stringify(m.toJson([it]).items[0]).includes("stash"), false, "nothing of the stash goes in items.json");
  const fresh = { id: "Gem", name: "Gem", description: "x", kind: "material", like: "Dandelion" };
  m.switchKind(fresh, "accessory", stash, start);
  assert.deepEqual(fresh.texture, { tint: m.NEW_LOOK }, "a new accessory starts with a colour of its own");
  assert.equal(fresh.like, "Cosmetic.Neck.DogCollar.1");
});

test("effectName says what an effect does and the herb that does it, preferring the herb for you alone", () => {
  assert.equal(m.effectName("Gameplay.Effect.Consumable.Health.2", HERBS), "Heals 50 health (Marigold Petal)");
  assert.equal(m.effectName("Gameplay.Effect.Consumable.Buff.Strength.1", HERBS), "Whole team +50% Strength for the fight (Juniper Poultice)");
  assert.equal(m.effectName("Gameplay.Effect.Consumable.Glow.1", HERBS), "Mystery Moss's", "a herb without words is named the old way");
  assert.equal(m.effectName("Gameplay.Effect.Consumable.Fly.1", HERBS), "Fly 1");
});

test("choosing an effect brings who it's for and when from its herb, and the same as the start takes them away", () => {
  const it = { id: "MoonHerb", like: "MediumHealingHerb" };
  m.chooseEffect(it, "Gameplay.Effect.Consumable.Buff.Strength.1", HERBS);
  assert.deepEqual(it, { id: "MoonHerb", like: "MediumHealingHerb", effect: "Gameplay.Effect.Consumable.Buff.Strength.1", type: "BuffStrength",
    target: "OwnerTeam", combat: true, exploring: false, fight_only: true });
  m.chooseEffect(it, "", HERBS);
  assert.deepEqual(it, { id: "MoonHerb", like: "MediumHealingHerb" });
});

test("What it does offers one choice a herb, so the team's herbs are there too", () => {
  const EFFECTS = ["Gameplay.Effect.Consumable.Buff.Strength.1", "Gameplay.Effect.Consumable.Health.2", "Gameplay.Effect.Consumable.Fly.1"];
  assert.deepEqual(m.effectChoices(HERBS, EFFECTS), [
    { value: "ThistlePouch", text: "Whole team +50% Strength for the fight (Juniper Poultice)" },
    { value: "MediumHealingHerb", text: "Heals 50 health (Marigold Petal)" },
    { value: "HealingHerbPouch", text: "Heals the whole team 50 health (Wintergreen Berries)" },
    { value: "Gameplay.Effect.Consumable.Fly.1", text: "Fly 1" },
    { value: "SmallHealingHerb", text: "Heals 25 health (Horsetail Stalks)" },
    { value: "NewOne", text: "Mystery Moss's" }]);
  // Choosing the team's herb brings its who-for, and the item reads back as that choice, not Marigold Petal.
  const it = { id: "MoonHerb", like: "SmallHealingHerb" };
  m.chooseEffect(it, "HealingHerbPouch", HERBS);
  assert.deepEqual([it.effect, it.target, it.type], ["Gameplay.Effect.Consumable.Health.2", "OwnerTeam", "Health"]);
  assert.equal(m.effectChoice(it, HERBS), "HealingHerbPouch");
  m.chooseEffect(it, "MediumHealingHerb", HERBS);
  assert.equal(m.effectChoice(it, HERBS), "MediumHealingHerb");
  assert.equal(m.effectChoice({ effect: "Gameplay.Effect.Consumable.Health.2" }, HERBS), "MediumHealingHerb", "written by hand: the herb for you");
  assert.equal(m.effectChoice({ effect: "Gameplay.Effect.Consumable.Fly.1" }, HERBS), "Gameplay.Effect.Consumable.Fly.1");
  assert.equal(m.effectChoice({}, HERBS), "");
  // An effect no herb has is kept as it is.
  m.chooseEffect(it, "Gameplay.Effect.Consumable.Fly.1", HERBS);
  assert.deepEqual(it, { id: "MoonHerb", like: "SmallHealingHerb", effect: "Gameplay.Effect.Consumable.Fly.1" });
});

test("renameItem: the mod's other items' recipes follow a material's new id, in the same place", () => {
  const stone = { id: "NewHerb", kind: "material", _new: true };
  const herb = { id: "MoonHerb", recipe: { Dandelion: 2, NewHerb: 1, Moss: 3 } };
  const other = { id: "Collar", recipe: { Moss: 1 } };
  const items = [stone, herb, other, { id: "Plain" }];
  m.renameItem(items, stone, "Moonstone");
  assert.equal(stone.id, "Moonstone");
  assert.deepEqual(Object.entries(herb.recipe), [["Dandelion", 2], ["Moonstone", 1], ["Moss", 3]]);
  assert.deepEqual(other.recipe, { Moss: 1 });
  m.renameItem(items, stone, "Moonstone");
  assert.deepEqual(Object.keys(herb.recipe), ["Dandelion", "Moonstone", "Moss"], "the same id again changes nothing");
});

test("whoAndWhen and badgeWords say it in words", () => {
  assert.equal(m.whoAndWhen({}, HERBS[1]), "Used anywhere, for you");
  assert.equal(m.whoAndWhen({}, HERBS[3]), "Used in fights only, for your whole team; it wears off when the fight ends");
  assert.equal(m.whoAndWhen({ combat: false }, HERBS[1]), "Used while exploring only, for you");
  assert.equal(m.whoAndWhen({ target: "OwnerTeam" }, HERBS[1]), "Used anywhere, for your whole team");
  assert.equal(m.badgeWords("Health", HERBS), "Health: like Horsetail Stalks and Marigold Petal and others");
  assert.equal(m.badgeWords("Stats", HERBS), "Stats: like Juniper Poultice");
  assert.equal(m.badgeWords("Damage", HERBS), "Damage");
  assert.equal(m.badgeWords("None", HERBS), "No badge");
});

test("isPicture tells the mod's own pictures from the game's items and textures", () => {
  assert.equal(m.isPicture("pictures/MoonHerb-icon.png"), true);
  assert.equal(m.isPicture("icons/moon.PNG"), true);
  assert.equal(m.isPicture("Rock"), false);
  assert.equal(m.isPicture("/Game/Art/UXD/Textures/T_Rock"), false);
  assert.equal(m.isPicture({ tint: "#fff" }), false);
});

// ---------- whether it reached the game ----------
const MANIFEST = {
  built: "2026-10-28T10:00:00", mods: ["mine"],
  notes: { items: { items: { "mine/MoonHerb": "Gameplay.Inventory.Consumable.MoonHerb", "mine/Pebble": "Gameplay.Inventory.Materials.Pebble",
    "mine/Blue": "Gameplay.Inventory.Cosmetic.Neck.DogCollar.3", "mine/Gem": ["Gameplay.Inventory.Materials.Gem", "Gameplay.Inventory.Consumable.Gem"] } } },
  warnings: ["items: mine: Lost: it has no description, so it's left out of the game",
    "items: mine: Pebble: its model on the ground: there's no model models/p.obj in the mod's folder; it lies there as the game's pickup instead",
    "items: mine: MoonHerb: no save yet to give it in; start the game once, then install again",
    "items: other: MoonHerb: something about another mod's"],
  sections: { items: { status: "ok", mods: ["mine"], errors: [], failed: [] } },
};

test("itemStatus says whether an item went in, and why one didn't, in the page's words", () => {
  assert.deepEqual(m.itemStatus(MANIFEST, "mine", { id: "MoonHerb" }), { state: "in", also: ["no save to give it in yet"], look: null });
  assert.deepEqual(m.itemStatus(MANIFEST, "mine", { id: "Pebble" }), { state: "in", also: ["on the ground it's the game's pickup"], look: null });
  assert.deepEqual(m.itemStatus(MANIFEST, "mine", { id: "Blue" }), { state: "in", also: [], look: 3 });
  assert.equal(m.itemStatus(MANIFEST, "mine", { id: "Gem" }).state, "in", "a herb and a material with one id");
  assert.deepEqual(m.itemStatus(MANIFEST, "mine", { id: "Lost" }), { state: "out", why: "it has no description, so it's left out of the game" });
  assert.deepEqual(m.itemStatus(MANIFEST, "mine", { id: "Unsaved" }), { state: "out", why: "it didn't go in" });
  assert.match(m.itemStatus(MANIFEST, "gone", { id: "MoonHerb" }).why, /its mod wasn't in the last Apply/);
  assert.equal(m.itemStatus({ manifest: MANIFEST }, "mine", { id: "Blue" }).look, 3, "as /build/last gives it");
});

test("itemStatus leaves it unsaid when it can't tell: no build, or an older wcmods' note", () => {
  assert.equal(m.itemStatus(null, "mine", { id: "MoonHerb" }), null);
  assert.equal(m.itemStatus({ log: [] }, "mine", { id: "MoonHerb" }), null);
  const old = { ...MANIFEST, notes: { items: { items: ["Gameplay.Inventory.Consumable.MoonHerb"] } } };
  assert.equal(m.itemStatus(old, "mine", { id: "MoonHerb" }), null, "the old list of tags can't tell items apart");
  // The section ran and made nothing: every item is out, with what kept it out.
  const none = { ...MANIFEST, notes: {}, warnings: [], sections: { items: { status: "partial", mods: ["mine"], errors: ["x"], failed: [["mine", "items.json: item 1: \"icon\" should be text"]] } } };
  assert.deepEqual(m.itemStatus(none, "mine", { id: "MoonHerb" }), { state: "out", why: "items.json: item 1: \"icon\" should be text" });
});

test("itemsSummary counts what went in and names the first left out", () => {
  const items = [{ id: "MoonHerb", name: "Moon Herb" }, { id: "Lost", name: "Lost Herb" }, { id: "Blue", name: "Blue Collar" }];
  assert.equal(m.itemsSummary(MANIFEST, "mine", items), "2 of 3 items went in. Lost Herb was left out: it has no description, so it's left out of the game.");
  assert.equal(m.itemsSummary(MANIFEST, "mine", [items[0]]), "1 of 1 item went in.");
  assert.equal(m.itemsSummary(null, "mine", items), null);
});
