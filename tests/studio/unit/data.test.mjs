// studio/lib/data.js: the Game data page's logic. data.json in and out with the file's own "-" and "+" kept,
// what a cell shows (the build's rule, csvdata.apply_edits), the number check, column kinds, Quick changes and
// the search across tables.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { install, STUDIO } from "../lib/dom.mjs";

const dom = install();
const D = await import(dom.studio("lib/data.js"));
const QUICK = JSON.parse(fs.readFileSync(path.join(STUDIO, "sections", "data-quick.json"), "utf8"));
const TITLES = JSON.parse(fs.readFileSync(path.join(STUDIO, "sections", "data-titles.json"), "utf8"));

const XP = { header: ["Enemy", "BaseExperience", "DifficultyOffset"], rows: [["Fish", "10", "0"], ["Mice", "25", "0"], ["Rat", "60", "0"]] };
// The headers of the game's tables the Quick changes name (as the game ships them), and the rows they use.
const HEADERS = {
  "TuningData.csv": ["---", "MaxValue", "Description"],
  "CombatBaseExperience.csv": XP.header,
  "HousingCost.csv": ["---", "Cost", "BuildTime", "Rarity", "MaxQuantity", "Size", "bIsHidden", "MontageToPlay", "BoneToAttach", "bFaceAgainstMyForward", "bDisableCollisionOnInteract"],
  "NPC/CatSize.csv": ["--", "Role", "MinScale", "MaxScale"],
  "NPC/Scars.csv": ["", "Role", "Group", "EarChance", "BodyChance", "EyeChance"],
};
const TUNING = { header: HEADERS["TuningData.csv"], rows: [
  ["Gameplay.Exploration.Player.MoveAndRun.Run.Speed", "390", "The target maximum speed of the cat while running."],
  ["Gameplay.Exploration.Player.MoveAndRun.Stamina.DrainRate", "-10", ""],
  ["Gameplay.NPC.Heterochromia.Chance", "0.15", ""],
] };
const SCARS = { header: HEADERS["NPC/Scars.csv"], rows: [["7", "Leader", "All", "0.85", "0.50", "0.00"], ["3", "Warrior", "All", "0.10", "0.05", "0.00"]] };
const quick = id => QUICK.rows.find(q => q.id === id);

test("clean and toJson keep \"-\" and \"+\" arrays untouched", () => {
  const file = { _help: "x", "NPC/Scars.csv": { "-": ["12"], "+": [{ "": "13", Role: "Kit" }], "3": { EarChance: 0.2 } } };
  const c = D.clean(file);
  assert.deepEqual(c.rowOps, { "NPC/Scars.csv": { "-": ["12"], "+": [{ "": "13", Role: "Kit" }] } });
  assert.deepEqual(c.edits, { "NPC/Scars.csv": { "3": { EarChance: 0.2 } } });
  const out = D.toJson(c.edits, c.rowOps);
  assert.deepEqual(out["NPC/Scars.csv"], file["NPC/Scars.csv"]);
  assert.ok(Array.isArray(out["NPC/Scars.csv"]["-"]) && Array.isArray(out["NPC/Scars.csv"]["+"]));
  assert.equal(D.rowOpsWords(c.rowOps["NPC/Scars.csv"]), "1 row removed, 1 row added by hand");
  assert.equal(D.countEdits(c.edits, c.rowOps, "NPC/Scars.csv"), 3);
});

test("clean skips a null table with its name", () => {
  const c = D.clean({ "TuningData.csv": null, "Nope.csv": [1], "CombatBaseExperience.csv": { Mice: 30 } });
  assert.deepEqual(c.skipped, ["TuningData.csv", "Nope.csv"]);
  assert.deepEqual(c.edits, { "CombatBaseExperience.csv": { Mice: { __first__: 30 } } });
  assert.deepEqual(D.clean(null), { edits: {}, rowOps: {}, skipped: [] });
});

test("shorthand expands to the second column once the table is cached", () => {
  const { edits } = D.clean({ "TuningData.csv": { "Run.Speed": 450 } });
  assert.deepEqual(D.toJson(edits)["TuningData.csv"], { "Run.Speed": 450 });
  assert.deepEqual(D.toJson(edits, {}, { "TuningData.csv": TUNING.header })["TuningData.csv"], { "Run.Speed": { MaxValue: 450 } });
  // "*" is written first, whatever order the edits were made in.
  const e = { "CombatBaseExperience.csv": { Mice: { BaseExperience: 25 }, "*": { BaseExperience: "x2" } } };
  assert.deepEqual(Object.keys(D.toJson(e)["CombatBaseExperience.csv"]), ["*", "Mice"]);
});

test("valueFor agrees with apply_edits for a row edit under a multiplier", () => {
  const t = { "*": { BaseExperience: "x2" }, Mice: { BaseExperience: 25 } };
  assert.deepEqual(D.valueFor(t, XP.header, XP.rows[0], 1), { value: "20", how: "×2", own: false });
  assert.deepEqual(D.valueFor(t, XP.header, XP.rows[1], 1), { value: "25", how: "set", own: true });
  assert.equal(D.valueFor(t, XP.header, XP.rows[0], 2), null);
  // A column named without its case, as the build matches it.
  assert.equal(D.valueFor({ Rat: { baseexperience: 1 } }, XP.header, XP.rows[2], 1).value, "1");
});

test("valueFor shows a row's own x0.5 as its number", () => {
  const t = { "*": { BaseExperience: "x2" }, Mice: { BaseExperience: "x0.5" } };
  assert.deepEqual(D.valueFor(t, XP.header, XP.rows[1], 1), { value: "12.5", how: "×0.5", own: true });
});

test("valueFor on an empty cell under x2 says unchanged", () => {
  const header = ["Key", "Value"], row = ["A", ""];
  assert.deepEqual(D.valueFor({ "*": { Value: "x2" } }, header, row, 1), { value: "", how: "unchanged (not a number)", own: false, bad: true });
  assert.equal(D.valueFor({ "*": { Value: "x2" } }, header, ["B", "Tag.X"], 1).how, "unchanged (not a number)");
});

test("a number check accepts 25, \" 25 \" and 1.50 and refuses 1,5 and abc", () => {
  assert.equal(D.readNumber("25"), 25);
  assert.equal(D.readNumber(" 25 "), 25);
  assert.equal(D.readNumber("1.50"), 1.5);
  assert.equal(D.readNumber("0.1234567"), 0.123457);   // six decimals, as the file writes it
  for (const bad of ["1,5", "abc", "", "x2", "1e3"]) assert.equal(D.readNumber(bad), null, bad);
  assert.deepEqual(D.readCell({ kind: "number" }, "abc"), { error: "Use a number like 1.5" });
  assert.deepEqual(D.readCell({ kind: "number", chance: true }, "1.5"), { error: "This is a chance: use a number from 0 to 1" });
  assert.deepEqual(D.readCell({ kind: "text" }, "Owner"), { value: "Owner" });
  assert.equal(D.numberText(37.5, "25"), "37.5");
  assert.equal(D.numberText(50, "25"), "50");
  assert.equal(D.numberText(1, "0.5"), "1");
});

test("countEdits counts a \"*\" entry once per column", () => {
  const edits = { "CombatBaseExperience.csv": { "*": { BaseExperience: "x2", DifficultyOffset: 1 }, Mice: { BaseExperience: 30 } } };
  assert.equal(D.countEdits(edits, {}, "CombatBaseExperience.csv"), 3);
  assert.equal(D.countEdits(edits, {}, "TuningData.csv"), 0);
});

test("every table has a name in words, its title or its file's", () => {
  assert.equal(D.tableTitle("CombatBaseExperience.csv", TITLES), "XP from fights");
  assert.equal(D.tableTitle("QuestObjectives.csv", TITLES), "Quest objectives");
  assert.equal(D.tableTitle("NPC/EarType.csv", TITLES), "NPC ear type");
  assert.equal(D.tableTitle("NPC/FurPattern1Color.csv"), "NPC fur pattern 1 color");
  assert.equal(D.tableTitle("GameSharedForceFeedback.csv"), "Game shared force feedback");
});

test("a punctuation-only header is Row", () => {
  for (const h of ["", "---", "--", "#", " ", "_"]) assert.equal(D.headerLabel(h, 0), "Row", JSON.stringify(h));
  assert.equal(D.headerLabel("Enemy", 0), "Enemy");
  assert.equal(D.headerLabel("---", 1), "---");
});

test("a column of TRUE/FALSE is a checkbox and a five-word column a dropdown", () => {
  const header = ["---", "bCombat", "Target", "Chance", "Name", "Power", "Description"];
  const rows = [["a", "TRUE", "Owner", "0.10", "Moss", "10", "The first."], ["b", "FALSE", "OwnerTeam", "0.5", "Fern", "20", "The second."],
    ["c", "true", "Owner", "1", "Dock", "30", ""], ["d", "FALSE", "Enemy", "0", "Reed", "40", ""]];
  assert.deepEqual(D.columnKind(header, rows, 0), { kind: "key" });
  assert.deepEqual(D.columnKind(header, rows, 1), { kind: "bool" });
  assert.deepEqual(D.columnKind(header, rows, 2), { kind: "choice", options: ["Enemy", "Owner", "OwnerTeam"] });
  assert.deepEqual(D.columnKind(header, rows, 3), { kind: "number", chance: true });
  assert.deepEqual(D.columnKind(header, rows, 4), { kind: "text" }, "every word once: names, not a choice");
  assert.deepEqual(D.columnKind(header, rows, 5), { kind: "number", chance: false });
  assert.deepEqual(D.columnKind(header, rows, 6), { kind: "note" });
  assert.equal(D.multiplyProblem({ kind: "number", chance: true }, header, rows, 3, 3), "b would be 1.5, and a chance can't go over 1");
  assert.equal(D.multiplyProblem({ kind: "number" }, header, rows, 5, 0), "Use a number above 0");
  assert.equal(D.multiplyProblem({ kind: "number" }, header, rows, 5, 2), null);
});

test("setCell and unsetCell say whether anything was there to take away", () => {
  const edits = {};
  D.setCell(edits, "CombatBaseExperience.csv", XP.header, "Mice", "BaseExperience", 30);
  assert.deepEqual(edits, { "CombatBaseExperience.csv": { Mice: { BaseExperience: 30 } } });
  assert.equal(D.unsetCell(edits, "CombatBaseExperience.csv", XP.header, "Mice", "BaseExperience"), true);
  assert.deepEqual(edits, {});
  assert.equal(D.unsetCell(edits, "CombatBaseExperience.csv", XP.header, "Mice", "BaseExperience"), false);
  // A {row: value} edit turns into its column's name when the cell is changed.
  const e2 = { "TuningData.csv": { "Run.Speed": { __first__: 450 } } };
  D.setCell(e2, "TuningData.csv", TUNING.header, "Run.Speed", "Description", "Fast");
  assert.deepEqual(e2["TuningData.csv"]["Run.Speed"], { MaxValue: 450, Description: "Fast" });
});

test("every quick entry names a column its table has", () => {
  assert.ok(QUICK.rows.length >= 20);
  for (const q of QUICK.rows) {
    assert.ok(QUICK.groups.includes(q.group), `${q.id}: group ${q.group}`);
    assert.ok(HEADERS[q.table], `${q.id}: ${q.table} isn't one the card reads`);
    for (const col of q.columns || [q.column]) assert.ok(HEADERS[q.table].slice(1).includes(col), `${q.id}: ${q.table} has no ${col}`);
    assert.ok(q.row || q.rows, q.id);
    assert.ok(q.what && q.label && q.doc && q.synonyms?.length, `${q.id} says what it does`);
    assert.ok(["value", "factor"].includes(q.kind), q.id);
    assert.ok(/(Read by the game's code|From the tables)/.test(q.what), `${q.id} says how solid it is`);
    assert.ok(!q.what.includes("—"), `${q.id}: no em dash`);
  }
  assert.equal(new Set(QUICK.rows.map(q => q.id)).size, QUICK.rows.length, "ids are one each");
  for (const [t, info] of Object.entries(TITLES)) if (!t.startsWith("_")) assert.ok(info.title && info.what, t);
});

test("a value entry writes the cell and Normal removes it", () => {
  const q = quick("run-speed"), edits = {};
  assert.equal(D.quickNormal(q, TUNING), 390);
  assert.deepEqual(D.quickWrite(q, TUNING, edits, 600), { ok: true });
  assert.deepEqual(edits, { "TuningData.csv": { "Gameplay.Exploration.Player.MoveAndRun.Run.Speed": { MaxValue: 600 } } });
  assert.equal(D.quickCurrent(q, TUNING, edits["TuningData.csv"]), 600);
  assert.equal(D.quickEdited(q, TUNING, edits["TuningData.csv"]), true);
  D.quickWrite(q, TUNING, edits, 390);
  assert.deepEqual(edits, {});
  assert.deepEqual(D.quickWrite(q, TUNING, edits, 5000), { error: "Running speed goes from 100 to 1200" });
  assert.deepEqual(D.quickWrite(q, TUNING, edits, "fast"), { error: "Use a number like 1.5" });
  // A shorthand edit from a file the page didn't write counts too.
  assert.equal(D.quickCurrent(q, TUNING, { "Gameplay.Exploration.Player.MoveAndRun.Run.Speed": { __first__: 450 } }), 450);
});

test("a negated entry shows 10 and writes -10", () => {
  const q = quick("stamina-drain"), edits = {};
  assert.equal(D.quickNormal(q, TUNING), 10);
  D.quickWrite(q, TUNING, edits, 4);
  assert.deepEqual(edits["TuningData.csv"], { "Gameplay.Exploration.Player.MoveAndRun.Stamina.DrainRate": { MaxValue: -4 } });
  assert.equal(D.quickCurrent(q, TUNING, edits["TuningData.csv"]), 4);
  D.quickWrite(q, TUNING, edits, 10);
  assert.deepEqual(edits, {});
});

test("a factor entry writes xN on \"*\" or on each row", () => {
  const xp = quick("xp-fights"), edits = {};
  D.quickWrite(xp, XP, edits, 2);
  assert.deepEqual(edits, { "CombatBaseExperience.csv": { "*": { BaseExperience: "x2" } } });
  assert.equal(D.quickCurrent(xp, XP, edits["CombatBaseExperience.csv"]), 2);
  assert.equal(D.quickPreview(xp, XP, 2), "Fish 10 -> 20, Mice 25 -> 50, Rat 60 -> 120");
  D.quickWrite(xp, XP, edits, 1);
  assert.deepEqual(edits, {});
  const size = quick("size-leader"), sizes = { header: HEADERS["NPC/CatSize.csv"], rows: [["8", "Leader", "0.9", "1"]] };
  D.quickWrite(size, sizes, edits, 1.2);
  assert.deepEqual(edits, { "NPC/CatSize.csv": { "8": { MinScale: "x1.2", MaxScale: "x1.2" } } });
  assert.equal(D.quickPreview(size, sizes, 1.2), "MinScale 0.9 -> 1.08, MaxScale 1 -> 1.2");
});

test("a chance factor over 1 is refused", () => {
  const q = quick("scars-leader"), edits = {};
  assert.deepEqual(D.quickWrite(q, SCARS, edits, 2), { error: "That makes EarChance 1.7, and a chance can't go over 1" });
  assert.deepEqual(edits, {});
  assert.deepEqual(D.quickWrite(q, SCARS, edits, 0), { ok: true });
  assert.deepEqual(edits["NPC/Scars.csv"]["7"], { EarChance: "x0", BodyChance: "x0", EyeChance: "x0" });
  assert.deepEqual(D.quickWrite(quick("two-eyes"), TUNING, {}, 1.5), { error: "Two different eyes goes from 0 to 1" });
});

test("search finds a row by a synonym", () => {
  const hits = D.search("mouse", { quick: QUICK.rows, titles: TITLES });
  assert.equal(hits[0].kind, "quick");
  assert.equal(hits[0].id, "prey-mouse");
  assert.deepEqual(D.search("xp", { quick: QUICK.rows }).map(h => h.id).slice(0, 2), ["xp-fights", "levels"]);
  assert.ok(D.search("experience animal", { titles: TITLES }).some(h => h.kind === "table" && h.table === "CombatBaseExperience.csv"));
  // Any row of any table, by its name or its description.
  const index = { "TuningData.csv": { rows: TUNING.rows.map(r => r[0]), descriptions: { [TUNING.rows[0][0]]: TUNING.rows[0][2] } } };
  const row = D.search("maximum speed", { index, titles: TITLES });
  assert.deepEqual(row, [{ kind: "row", text: TUNING.rows[0][0], where: "The target maximum speed of the cat while running. (Tuning)", table: "TuningData.csv", row: TUNING.rows[0][0] }]);
  assert.deepEqual(D.search("  ", { quick: QUICK.rows }), []);
  assert.equal(D.search("e", { quick: QUICK.rows, limit: 3 }).length, 3);
});
