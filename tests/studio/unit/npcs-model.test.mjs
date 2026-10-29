// The Characters page's cats as data (studio/lib/npcs-model.js): npcs.json in and out, what keeps a cat from
// being what its maker meant, the size's words and the quests that name a cat. No DOM needed.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install } from "../lib/dom.mjs";

const dom = install();
const model = await import(dom.studio("lib/npcs-model.js"));

const FULL = {
  id: "mossfoot", name: "Mossfoot", title: "Elder", colours: { fur: "#7a6a58" }, eyes: 6, size: 0.7,
  look: { body: 6, fur: 2, tail: 7, ears: 3, eyes: 1, whiskers: 4, face: 5, pattern: 12, marking: 3 },
  slots: { fur: 9, pattern: 4, marking: 0 }, at: [1, 2, 3], yaw: 90, level: "L_WorldMap_01_P",
  lines: ["The forest is yours, young one."], _note: "the elder by the river",
};

test("round_trip_keeps_every_field", () => {
  const file = { _help: "old help", _note: "a note of the file's own", npcs: [FULL] };
  const { cats, extra } = model.load(file);
  const back = model.toJson(cats, extra);
  assert.deepEqual(back.npcs, [FULL]);
  assert.equal(back._note, "a note of the file's own");
  assert.equal(back._help, model.HELP, "the page writes its own help");
});

test("round_trip_keeps_patrol_data and its forward-compatible nested keys", () => {
  const patrol = { points: [{ x: 1, y: 2, z: 3, wait: { min: 1, max: 4, future: true } }],
    mode: "pingpong", wait: { until: { event: "storm", future: "kept" } }, future: { enabled: true } };
  const { cats, extra } = model.load({ npcs: [{ ...FULL, patrol }] });
  assert.deepEqual(model.toJson(cats, extra).npcs[0].patrol, patrol);
});

test("a cat with a new look each time writes no look or slots", () => {
  const { cats } = model.load({ npcs: [{ id: "a", name: "A" }] });
  assert.equal(model.isFixed(cats[0]), false);
  const o = model.toJson(cats).npcs[0];
  assert.deepEqual(o, { id: "a", name: "A", lines: [] });
});

test("At one spot with no spot yet survives a round trip as not chosen yet", () => {
  const { cats } = model.load({ npcs: [{ id: "a", name: "A", at: null }] });
  assert.equal(cats[0]._placing, true);
  assert.deepEqual(model.problems(cats[0]), ["Where they stand is At one spot, but no spot is filled in yet: use where your cat is standing, or type all three numbers. Until then they stand beside your cat."]);
  const o = model.toJson(cats).npcs[0];
  assert.equal(o.at, null);
  assert.ok(!("_placing" in o));
  // Filled in, the spot is written with its facing and level; taken away again, it's beside your cat.
  Object.assign(cats[0], { at: [5, 6, 7], yaw: 10, level: "L_WorldMap_01_P" });
  assert.deepEqual(model.toJson(cats).npcs[0].at, [5, 6, 7]);
  assert.deepEqual(model.problems(cats[0]), []);
  delete cats[0].at; delete cats[0]._placing;
  assert.ok(!("at" in model.toJson(cats).npcs[0]));
});

test("a title of spaces is dropped and a name of spaces falls back to the id", () => {
  const { cats } = model.load({ npcs: [{ id: "a", name: "  ", title: "  " }] });
  const o = model.toJson(cats).npcs[0];
  assert.equal(o.name, "a");
  assert.ok(!("title" in o));
  assert.deepEqual(model.problems(cats[0]), ["It has no name yet: type one in Name."]);
});

test("an all-random fixed look becomes a new look each time", () => {
  const { cats } = model.load({ npcs: [{ id: "a", name: "A", look: {}, slots: {} }] });
  assert.equal(model.isFixed(cats[0]), false);
  const o = model.toJson(cats).npcs[0];
  assert.ok(!("look" in o) && !("slots" in o));
  cats[0].slots = { fur: 3 };
  assert.equal(model.isFixed(cats[0]), true);
  assert.deepEqual(model.toJson(cats).npcs[0].slots, { fur: 3 });
});

test("a new cat keeps the same look every time, with every part and colour slot set", async () => {
  const { slug } = await import(dom.studio("lib/story.js"));
  let n = 0;
  const rnd = () => ((n++ * 0.37) % 1);
  const options = { parts: { body: 9, fur: 9, tail: 9, ears: 9, eyes: 9, whiskers: 9, face: 9, pattern: 20, marking: 20 }, game_slots: 25 };
  const c = model.newCat(["new-cat"], options, slug, rnd);
  assert.equal(c.id, "new-cat-2");
  assert.equal(c.name, "New cat");
  assert.equal(model.isFixed(c), true);
  assert.deepEqual(Object.keys(c.look), model.LOOK_PARTS.map(([p]) => p));
  for (const [p, v] of Object.entries(c.look)) assert.ok(Number.isInteger(v) && v >= 0 && v <= options.parts[p], `${p} ${v}`);
  assert.deepEqual(Object.keys(c.slots), ["fur", "pattern", "marking"]);
  assert.ok(c.slots.fur < model.RANDOM_COATS && c.slots.pattern < 25 && c.slots.marking < 25);
  assert.ok(Number.isInteger(c.eyes) && c.eyes < model.EYES);
  // Rolled again, the eyes stay; "Game's choice" eyes stay the game's.
  const eyes = c.eyes;
  model.roll(c, options, rnd);
  assert.equal(c.eyes, eyes);
  delete c.eyes;
  model.roll(c, options, rnd);
  assert.equal(c.eyes, undefined);
});

test("colours that aren't an object and lines that aren't a list load as none", () => {
  const { cats } = model.load({ npcs: [{ id: "a", name: "A", colours: null, lines: "hello" }, null, "x", { id: "b", name: "B", colours: [1] }] });
  assert.equal(cats.length, 2);
  assert.deepEqual(cats[0].colours, {});
  assert.deepEqual(cats[0].lines, []);
  assert.deepEqual(cats[1].colours, {});
  assert.deepEqual(model.load(null), { cats: [], extra: {} });
});

test("too many lines, a line too long and a palette's colour slot nobody adds are said", () => {
  const cat = { id: "a", name: "A", lines: Array(31).fill("Hi"), slots: { pattern: 27, marking: 4 } };
  assert.deepEqual(model.problems(cat, { gameSlots: 25, addedSlots: { pattern: [], marking: [] } }), [
    "What they say has 31 lines; 30 is the most. Take some out.",
    "They wear pattern colour 27, which no palette that's on adds, so it shows no colour there. Choose another, or turn that palette on.",
  ]);
  assert.deepEqual(model.problems({ ...cat, lines: ["x".repeat(401)] }, { addedSlots: { pattern: [27] } }),
    ["A line of what they say is longer than 400 letters. Split it into two lines."]);
  assert.deepEqual(model.problems({ ...cat, lines: [] }), [], "without the palettes' slots, nothing is said about them");
});

test("sizeText names the game's sizes for its own cats", () => {
  const cases = [[0.4, "40%, apprentice size"], [0.5, "50%, apprentice size"], [0.6, "60%, between apprentice and elder size"],
    [0.65, "65%, elder size"], [0.7, "70%, elder or warrior size"], [0.75, "75%, elder or warrior size"], [0.8, "80%, warrior size"],
    [0.85, "85%, between warrior and leader size"], [0.9, "90%, leader size"], [1, "100%, leader size"],
    [1.05, "105%, bigger than a leader"], [0.3, "30%, smaller than an apprentice"], [undefined, "85%, between warrior and leader size"]];
  for (const [v, said] of cases) assert.equal(model.sizeText(v), said, String(v));
  // The slider's steps of 0.05 come as floats that aren't quite round.
  assert.equal(model.sizeText(0.1 + 0.2 + 0.35), "65%, elder size");
});

test("questsNaming finds the quests that give or talk with a cat", () => {
  const quests = { quests: [
    { id: "moss", title: "Moss for Mossfoot", giver: "mossfoot", steps: [] },
    { id: "talk", title: "A word", steps: [{ do: "talk", npc: "mossfoot" }] },
    { id: "other", title: "Other", giver: "sparrowpaw", steps: [{ do: "collect" }] },
    null,
  ] };
  assert.deepEqual(model.questsNaming(quests, "mossfoot"), ["Moss for Mossfoot", "A word"]);
  assert.deepEqual(model.questsNaming(null, "mossfoot"), []);
});
