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

test("a patrol's [x, y, z] points load as {x, y, z}, and a patrol the page can't show is kept as it is", () => {
  const { cats } = model.load({ npcs: [{ id: "a", name: "A", patrol: { points: [[1, 2, 3], { x: 4, y: 5, z: 6, level: "L" }, "junk"], speed: 90 } },
    { id: "b", name: "B", patrol: { points: "not a list", future: 1 } }, { id: "c", name: "C", patrol: [1, 2] }] });
  assert.deepEqual(model.toJson(cats).npcs[0].patrol, { points: [{ x: 1, y: 2, z: 3 }, { x: 4, y: 5, z: 6, level: "L" }, { x: null, y: null, z: null }], speed: 90 });
  assert.deepEqual(model.toJson(cats).npcs[1].patrol, { points: "not a list", future: 1 });
  assert.deepEqual(model.toJson(cats).npcs[2].patrol, [1, 2]);
  for (const c of cats.slice(1)) {
    assert.deepEqual(model.problems(c), ["Their patrol isn't laid out as this page writes it, so they stand still: start a new route under Where they walk."]);
  }
});

test("a new patrol starts where the cat stands, or with no points; the page's kept route isn't saved", () => {
  assert.deepEqual(model.newPatrol({ at: [1, 2, 3], level: "L_WorldMap_01_P" }), { points: [{ x: 1, y: 2, z: 3, level: "L_WorldMap_01_P" }] });
  assert.deepEqual(model.newPatrol({ at: [1, 2, 3] }), { points: [{ x: 1, y: 2, z: 3 }] });
  const c = { id: "a", name: "A", lines: [], _patrol: { points: [] } };
  assert.ok(!("_patrol" in model.toJson([c]).npcs[0]));
  assert.ok(!("patrol" in model.toJson([c]).npcs[0]));
});

test("movePoint swaps a point with its neighbour, and not past either end", () => {
  const patrol = { points: [{ x: 1 }, { x: 2 }, { x: 3 }] };
  assert.equal(model.movePoint(patrol, 0, -1), false);
  assert.equal(model.movePoint(patrol, 2, 1), false);
  assert.equal(model.movePoint(patrol, 1, -1), true);
  assert.deepEqual(patrol.points.map(p => p.x), [2, 1, 3]);
});

test("waitKind names every wait story.py takes", () => {
  const cases = [[undefined, "default"], ["none", "none"], [0, "seconds"], [4.5, "seconds"], [[1, 3], "range"], [{ min: 1, max: 3 }, "range"],
    ["release", "until"], [{ until: { quest: "q" }, timeout: 5 }, "until"], [{ timeout: 5 }, "other"], ["trigger", "other"], [null, "other"]];
  for (const [w, kind] of cases) assert.equal(model.waitKind(w), kind, JSON.stringify(w));
});

test("waitAs changes a wait's kind, keeping its seconds and the keys it doesn't know", () => {
  assert.equal(model.waitAs(7, "seconds"), 7, "the same kind is the same wait");
  assert.deepEqual(model.waitAs(7, "range"), { min: 7, max: 12 });
  assert.equal(model.waitAs([2, 9], "seconds"), 2);
  assert.equal(model.waitAs({ min: 2, max: 9 }, "none"), "none");
  assert.equal(model.waitAs("none", "seconds"), 5);
  assert.equal(model.waitAs(7, "default"), undefined);
  assert.deepEqual(model.waitAs({ min: 1, max: 2, future: true }, "until"), { future: true, until: {} });
  assert.deepEqual(model.waitAs({ until: { event: "e" }, timeout: 3, future: true }, "range"), { future: true, min: 3, max: 8 });
  // A range's numbers go back as they came: a list stays a list, an object keeps its keys.
  assert.deepEqual(model.withRange([1, 2], 3, 4), [3, 4]);
  assert.deepEqual(model.withRange({ min: 1, max: 2, future: 1 }, 3, 4), { min: 3, max: 4, future: 1 });
  assert.deepEqual(model.rangeOf({ min: 1 }), [1, null]);
});

test("untilWait gives an until wait as an object to edit, the same one when it is one", () => {
  assert.deepEqual(model.untilWait("release"), { until: { release: true } });
  const w = { until: { quest: "q" }, timeout: 4, future: 1 };
  assert.equal(model.untilWait(w), w);
  assert.deepEqual(model.untilWait({ until: "x", future: 1 }), { until: {}, future: 1 });
});

test("a patrol as the page makes it round-trips with its waits", () => {
  const patrol = { points: [{ x: 1, y: 2, z: 3, wait: 4 }, { x: 5, y: 6, z: 7, level: "L", wait: { min: 1, max: 5 } },
    { x: 8, y: 9, z: 10, wait: { until: { quest: "moss", step: 2, event: "storm", release: "gate" }, timeout: 30 } }, { x: 0, y: 0, z: 0, wait: "none" }],
  mode: "loop", speed: 120, retries: 0, enabled: false, wait: [2, 3] };
  const { cats } = model.load({ npcs: [{ id: "a", name: "A", patrol }] });
  assert.deepEqual(model.toJson(cats).npcs[0].patrol, patrol);
  assert.deepEqual(model.problems(cats[0]), []);
});

test("a patrol with no points, or a point missing a number, is said", () => {
  const cat = patrol => ({ id: "a", name: "A", lines: [], patrol });
  assert.deepEqual(model.problems(cat({})), ["Their patrol has no points yet: add one under Where they walk. Until then they stand still."]);
  assert.deepEqual(model.problems(cat({ points: [] })), ["Their patrol has no points yet: add one under Where they walk. Until then they stand still."]);
  assert.deepEqual(model.problems(cat({ points: [{ x: 1, y: 2, z: 3 }, { x: 1, y: null, z: 3 }, { x: null, y: null, z: null }, { x: 1 }] })), [
    "Patrol point 2 has no Y yet: use where your cat is standing, or type all three numbers. Until it has, Apply leaves this mod's cats and questlines out.",
    "Patrol point 3 has no numbers yet: use where your cat is standing, or type all three numbers. Until it has, Apply leaves this mod's cats and questlines out.",
    "Patrol point 4 has no Y or Z yet: use where your cat is standing, or type all three numbers. Until it has, Apply leaves this mod's cats and questlines out.",
  ]);
  assert.deepEqual(model.problems(cat({ points: [{ x: 1, y: 2, z: 3 }] })), [], "one point is a route");
});

test("a speed, tries or wait story.py refuses is said", () => {
  const cat = patrol => ({ id: "a", name: "A", lines: [], patrol: { points: [{ x: 1, y: 2, z: 3 }], ...patrol } });
  assert.deepEqual(model.problems(cat({ speed: 0, retries: 1.5 })), [
    "Their walking speed should be more than 0: type another, or leave it empty for a cat's walk.",
    "Tries before skipping a point should be a whole number, 0 or more: type another, or leave it empty for 2.",
  ]);
  assert.deepEqual(model.problems(cat({ wait: -1 })), ["The patrol's wait should be 0 seconds or more."]);
  assert.deepEqual(model.problems(cat({ wait: { min: 5, max: 2 } })), ["The patrol's wait goes from 5 to 2 seconds: the first should be the smaller."]);
  assert.deepEqual(model.problems(cat({ wait: { min: 5 } })), ["The patrol's wait is a random time, but it needs both numbers: from and to."]);
  assert.deepEqual(model.problems(cat({ points: [{ x: 1, y: 2, z: 3, wait: { until: {}, timeout: 0 } }] })), [
    "Patrol point 1's wait is Until…, but nothing is chosen to wait for: choose a quest, type an event, or tick Released by a script.",
    "Patrol point 1's wait gives up after a time: it should be more than 0 seconds, or empty to wait as long as it takes.",
  ]);
  assert.deepEqual(model.problems(cat({ wait: { until: { quest: "q", step: 0 } } })),
    ["The patrol's wait waits for a step of the quest: its number should be a whole number, 1 or more."]);
  assert.deepEqual(model.problems(cat({ wait: { until: { event: "e", step: 2 } } })), ["The patrol's wait waits for a step, but of no quest: choose the quest."]);
  assert.deepEqual(model.problems(cat({ wait: "release" })), []);
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
