// The Questlines page's quests as data (studio/lib/quests-model.js): quests.json in and out, the objective the
// game shows for a step left without one, and what keeps a quest from working, circles of "Starts after"
// among them. No DOM needed.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install } from "../lib/dom.mjs";

const dom = install();
const model = await import(dom.studio("lib/quests-model.js"));

const MOSS = "Gameplay.Inventory.Materials.Moss";
const cats = [{ id: "mossfoot", name: "Mossfoot" }, { id: "sparrowpaw", name: "Sparrowpaw" }];
const names = { cat: id => (cats.find(c => c.id === id) || {}).name || id, item: tag => ({ [MOSS]: "Moss" })[tag] || tag.split(".").pop() };
const quest = over => ({ id: "moss", title: "Moss for Mossfoot", giver: "mossfoot", after: [], reward: {}, steps: [
  { do: "talk", lines: ["Bring me moss?"] }, { do: "collect", item: MOSS, count: 2 }], ...over });

test("toJson writes no automatic objective, keeps one of the maker's own, and gives a talk step the giver", () => {
  const { quests, extra } = model.load({ quests: [quest({ steps: [
    { do: "talk", lines: ["Hi"] },
    { do: "collect", item: MOSS, count: 2, objective: "Find 2 Moss" },              // today's words: automatic
    { do: "collect", item: MOSS, count: 2, objective: "Find Moss ×2" },             // the page's old words: automatic
    { do: "visit", place: "medicine-cat", objective: "Visit your Clan's medicine cat" },
    { do: "visit", at: [1, 2, 3], level: "L_WorldMap_01_P", objective: "Go to the old oak", _note: "the oak" }] })] }, names);
  const steps = model.toJson(quests, extra).quests[0].steps;
  assert.deepEqual(steps, [
    { do: "talk", npc: "mossfoot", lines: ["Hi"] },
    { do: "collect", item: MOSS, count: 2 },
    { do: "collect", item: MOSS, count: 2 },
    { do: "visit", place: "medicine-cat", radius: 400 },
    { do: "visit", at: [1, 2, 3], level: "L_WorldMap_01_P", radius: 400, objective: "Go to the old oak", _note: "the oak" },
  ]);
});

test("toJson keeps Starts after to quests that are there, leaves an empty reward out, and keeps the notes", () => {
  const { quests, extra } = model.load({ _note: "mine", _help: "old", quests: [
    quest({ id: "a", after: ["b", "gone", "a"], reward: {}, _why: "a note", description: "  About moss.  " }),
    quest({ id: "b", reward: { [MOSS]: 2 } })] }, names);
  const out = model.toJson(quests, extra);
  assert.equal(out._help, model.HELP);
  assert.equal(out._note, "mine");
  const [a, b] = out.quests;
  assert.deepEqual(a.after, ["b"]);
  assert.ok(!("reward" in a));
  assert.equal(a._why, "a note");
  assert.equal(a.description, "About moss.");
  assert.deepEqual(b.reward, { [MOSS]: 2 });
  assert.ok(!("description" in b));
  assert.ok(!JSON.stringify(out).includes("_auto") && !JSON.stringify(out).includes("_new"));
});

test("load counts an objective equal to the automatic one, today's or the page's old words, as automatic", () => {
  const { quests } = model.load({ quests: [quest({ steps: [
    { do: "talk", npc: "sparrowpaw", lines: ["Hi"], objective: "Talk to Sparrowpaw" },
    { do: "collect", item: MOSS, count: 1, objective: "Find Moss" },
    { do: "collect", item: MOSS, count: 3, objective: "Find Moss ×3" },
    { do: "visit", place: "medicine-cat", objective: "Visit the nearest medicine cat" },
    { do: "visit", at: [1, 2, 3], objective: "Go to the marked place" },
    { do: "talk", lines: ["Hi"], objective: "Say hello to Mossfoot" }] })] }, names);
  assert.deepEqual(quests[0].steps.map(s => s._auto), [true, true, true, true, true, false]);
});

test("autoObjective says what the build will fill in, with today's names", () => {
  const q = quest();
  assert.equal(model.autoObjective({ do: "talk" }, q, names), "Talk to Mossfoot");
  assert.equal(model.autoObjective({ do: "talk", npc: "sparrowpaw" }, q, names), "Talk to Sparrowpaw");
  assert.equal(model.autoObjective({ do: "collect", item: MOSS, count: 2 }, q, names), "Find 2 Moss");
  assert.equal(model.autoObjective({ do: "collect", item: MOSS, count: 1 }, q, names), "Find Moss");
  assert.equal(model.autoObjective({ do: "collect" }, q, names), "Find something");
  assert.equal(model.autoObjective({ do: "visit", place: "medicine-cat" }, q, names), "Visit the nearest medicine cat");
  assert.equal(model.autoObjective({ do: "visit", at: [1, 2, 3] }, q, names), "Go to the marked place");
});

test("problems says each thing that keeps a quest from working, with the step it's on", () => {
  const q = quest({ title: " ", giver: "gone", steps: [
    { do: "talk", npc: "nobody", lines: [] }, { do: "collect" }, { do: "visit" }, { do: "talk", npc: "mossfoot", lines: ["Hi"] }] });
  assert.deepEqual(model.problems(q, [q], cats), [
    { text: "It has no title yet: type one in Title.", step: null },
    { text: "Given by gone, who isn't one of this mod's cats any more: choose another in Given by.", step: null },
    { text: "Step 1: nobody isn't one of this mod's cats any more: choose another.", step: 0 },
    { text: "Step 1: what do they say? Type at least one line.", step: 0 },
    { text: "Step 2: which item? Choose one.", step: 1 },
    { text: "Step 3: where? Use where your cat is standing, or type all three numbers.", step: 2 },
  ]);
  assert.deepEqual(model.problems(quest({ steps: [] }), [], cats), [{ text: "It has no steps yet: add a Talk, Pick up or Go somewhere step.", step: null }]);
  assert.deepEqual(model.problems(quest(), [quest()], cats), []);
  const nobody = quest({ giver: undefined, steps: [{ do: "talk", lines: ["Hi"] }] });
  assert.deepEqual(model.problems(nobody, [nobody], cats), [{ text: "Step 1: who to talk to? Choose a cat.", step: 0 }]);
});

test("a two-quest circle of Starts after is said on both quests", () => {
  const a = quest({ id: "a", title: "A", after: ["b"] }), b = quest({ id: "b", title: "B", after: ["a"] });
  for (const [q, said] of [[a, "A → B → A"], [b, "B → A → B"]]) {
    assert.deepEqual(model.problems(q, [a, b], cats), [{ text: `Starts after goes round in a circle: ${said}. None of them would ever start: untick one.`, step: null }]);
  }
});

test("a three-quest circle is found, and a diamond is fine", () => {
  const a = quest({ id: "a", title: "A", after: ["c"] }), b = quest({ id: "b", title: "B", after: ["a"] }), c = quest({ id: "c", title: "C", after: ["b"] });
  assert.deepEqual(model.circle([a, b, c], a), ["a", "c", "b", "a"]);
  assert.match(model.problems(b, [a, b, c], cats)[0].text, /B → A → C → B/);
  // d waits for b and c, which both wait for a: no circle anywhere.
  const top = quest({ id: "a" }), left = quest({ id: "b", after: ["a"] }), right = quest({ id: "c", after: ["a"] }), d = quest({ id: "d", after: ["b", "c"] });
  for (const q of [top, left, right, d]) assert.equal(model.circle([top, left, right, d], q), null);
  assert.deepEqual([...model.waitsFor([top, left, right, d], "d")].sort(), ["a", "b", "c"]);
  assert.equal(model.waitsFor([top, left, right, d], "a").size, 0);
});
