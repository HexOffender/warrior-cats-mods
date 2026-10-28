// studio/lib/story.js: the parts the Items, Characters and Questlines pages share, the ones that are plain data.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install } from "./lib/dom.mjs";

const dom = install();
const story = await import(dom.studio("lib/story.js"));

test("slug makes an id from a name, unique among the ids taken", () => {
  assert.equal(story.slug("Mossfoot"), "mossfoot");
  assert.equal(story.slug("Moss foot, the Elder"), "moss-foot-the-elder");
  assert.equal(story.slug("Éclair Brûlée"), "eclair-brulee");
  assert.equal(story.slug("Mossfoot", ["mossfoot"]), "mossfoot-2");
  assert.equal(story.slug("Mossfoot", ["mossfoot", "mossfoot-2"]), "mossfoot-3");
  assert.equal(story.slug(""), "thing");
  assert.equal(story.slug("", [], "cat"), "cat");
  assert.equal(story.slug("---"), "thing");
  assert.equal(story.slug("-leading"), "leading");
  assert.equal(story.slug("x".repeat(60)).length, 40);
  assert.equal(story.slug("🐱"), "thing");
});

test("ownItems gives a mod's items.json the tags the game gives them", () => {
  const items = { items: [
    { id: "moss", kind: "material", name: "Moss" },
    { id: "mint", kind: "consumable" },
    { id: "bark", like: "Gameplay.Inventory.Materials.Stick", name: "Bark" },
    { id: "berry", like: "Gameplay.Inventory.Consumable.Berries" },
    { id: "odd", kind: "accessory" },
    { kind: "material", name: "no id" },
    null,
  ] };
  assert.deepEqual(story.ownItems(items), [
    { tag: "Gameplay.Inventory.Materials.moss", name: "Moss" },
    { tag: "Gameplay.Inventory.Consumable.mint", name: "mint" },
    { tag: "Gameplay.Inventory.Materials.bark", name: "Bark" },
    { tag: "Gameplay.Inventory.Consumable.berry", name: "berry" },
  ]);
  assert.deepEqual(story.ownItems(null), []);
  assert.deepEqual(story.ownItems({}), []);
});

test("itemChoices groups the game's items with the mod's own first, leaving empty groups out, and names a tag", () => {
  const game = { items: [
    { tag: "Gameplay.Inventory.Consumable.Mint", name: "Mint", kind: "consumable" },
    { tag: "Gameplay.Inventory.Materials.Moss", name: "Moss", kind: "material" },
    { tag: "Gameplay.Inventory.Cosmetic.Neck.DogCollar.1", name: "Dog collar", kind: "accessory" },
  ] };
  const own = [{ tag: "Gameplay.Inventory.Materials.bark", name: "Bark" }];
  const c = story.itemChoices(game, own);
  assert.deepEqual(c.groups.map(([g, list]) => [g, list.map(i => i.name)]),
    [["Your items", ["Bark"]], ["Herbs", ["Mint"]], ["Materials", ["Moss"]], ["Accessories", ["Dog collar"]]]);
  assert.equal(c.name("Gameplay.Inventory.Materials.bark"), "Bark");
  assert.equal(c.name("Gameplay.Inventory.Materials.Unknown"), "Unknown");
  assert.equal(c.name(""), "");
  const none = story.itemChoices({ items: [] });
  assert.deepEqual(none.groups, []);
});

test("itemSelect offers the choices in groups and keeps a value that isn't among them", () => {
  const c = story.itemChoices({ items: [{ tag: "Gameplay.Inventory.Materials.Moss", name: "Moss", kind: "material" }] });
  const picked = [];
  const s = story.itemSelect(c, "Gameplay.Inventory.Materials.Gone", v => picked.push(v), "Reward");
  assert.equal(s.getAttribute("aria-label"), "Reward");
  assert.deepEqual(s.options.map(o => o.value), ["", "Gameplay.Inventory.Materials.Moss", "Gameplay.Inventory.Materials.Gone"]);
  assert.equal(s.options.at(-1).textContent, "Gone");
  assert.equal(s.value, "Gameplay.Inventory.Materials.Gone");
  s.value = "Gameplay.Inventory.Materials.Moss";
  s.dispatch("change");
  assert.deepEqual(picked, ["Gameplay.Inventory.Materials.Moss"]);
});

test("linesBox holds one line of talk per line of text and reports them trimmed, without blanks", () => {
  const said = [];
  const box = story.linesBox(["Hello.", "Bring me moss?"], lines => said.push(lines), "What they say");
  assert.equal(box.tagName, "TEXTAREA");
  assert.equal(box.getAttribute("rows"), "3");
  assert.equal(box.getAttribute("placeholder"), "What they say");
  assert.equal(box.value, "Hello.\nBring me moss?");
  box.value = "  One \n\n Two  \n";
  box.dispatch("input");
  assert.deepEqual(said, [["One", "Two"]]);
  assert.equal(story.linesBox(Array(5).fill("x"), () => {}).getAttribute("rows"), "6");
});

test("field wraps an input with its label and an optional hint", () => {
  const input = dom.document.createElement("input");
  const f = story.field("Name", input, "As the clan calls them");
  assert.equal(f.tagName, "LABEL");
  assert.equal(f.children[0].textContent, "Name");
  assert.equal(f.children[1], input);
  assert.equal(f.children[2].textContent, "As the clan calls them");
  assert.equal(story.field("Name", input).children.length, 2);
});

test("listEditor redraws one list button in place, and holds Add back until the page is ready", () => {
  const added = [];
  const ed = story.listEditor({ noun: "cat", empty: "None", label: c => c.name, add: () => added.push(1) });
  const cats = [{ name: "Mossfoot" }, { name: "Sparrowpaw" }];
  ed.render(cats, (box, c) => box.append(c.name));
  const buttons = () => ed.element.querySelectorAll("button.pick");
  const first = buttons()[0];
  cats[0].name = "Mossfoot the Elder";
  ed.relabel(0);
  assert.equal(buttons()[0], first, "the same button, not a new one");
  assert.equal(first.textContent, "Mossfoot the Elder");
  const add = ed.element.querySelectorAll("button").find(b => b.textContent === "Add a cat");
  ed.ready(false);
  assert.equal(add.disabled, true);
  ed.ready(true);
  add.click();
  assert.deepEqual(added, [1]);
});

test("wherePicker gives a spot only once all three numbers are in, rounded, and names each number", () => {
  const got = [];
  const picker = story.wherePicker({ at: null }, spot => got.push(spot));
  const inputs = picker.querySelectorAll("input");
  assert.deepEqual(inputs.map(i => i.getAttribute("aria-label")), ["X, across the map", "Y, along the map", "Z, height"]);
  const type = (i, v) => { inputs[i].value = v; inputs[i].dispatch("input"); };
  type(0, "1"); type(2, "3");
  assert.deepEqual(got.at(-1), { at: null });
  type(1, "2.6");
  assert.deepEqual(got.at(-1), { at: [1, 3, 3] });
  assert.equal(story.levelWords("L_WorldMap_01_P"), "the forest");
  assert.equal(story.levelWords("L_Other"), "L_Other");
});

test("wherePicker shows the studio's sentence alone when the spot can't be read, and the level in words when it can", async () => {
  const toasts = dom.byId.toasts;
  dom.routes = { "POST /game/where": () => { throw { status: 400, error: "The game is closed: press Play, stand where you want the cat and press this again" }; } };
  const got = [];
  const picker = story.wherePicker({}, spot => got.push(spot));
  const grab = picker.querySelectorAll("button").find(b => b.textContent === "Use where my cat is standing");
  grab.click();
  await new Promise(r => setTimeout(r, 10));
  assert.equal(toasts.children.at(-1).children[0].textContent, "The game is closed: press Play, stand where you want the cat and press this again");
  dom.routes = { "POST /game/where": () => ({ at: [10, 20, 30], yaw: 90, level: "L_WorldMap_01_P" }) };
  grab.click();
  await new Promise(r => setTimeout(r, 10));
  assert.deepEqual(got.at(-1), { at: [10, 20, 30], yaw: 90, level: "L_WorldMap_01_P" });
  assert.equal(toasts.children.at(-1).children[0].textContent, "Got your cat's spot in the forest.");
  assert.ok(picker.textContent.includes("in the forest"));
});
