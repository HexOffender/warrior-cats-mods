// studio/lib/save.js: the Save page's logic. The list of changes to make (save.json's shape), checked against
// the ranges the game takes; a path in words; what's shown and not changed; the presets; the combat stats.
// The words and ranges are the server's (wcmods/sections/savedit.py WORDS and RANGES), read from it here as
// GET /api/save hands them to the page, so the two languages are checked on the same patterns.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { install, REPO } from "../lib/dom.mjs";

const dom = install();
const S = await import(dom.studio("lib/save.js"));

const code = "import json, sys; sys.path.insert(0, sys.argv[1]); from wcmods.sections import savedit; " +
  "print(json.dumps({'words': savedit.WORDS, 'ranges': savedit.RANGES}))";
const server = spawnSync(process.env.PYTHON || "python", ["-I", "-c", code, REPO], { encoding: "utf8" });
if (server.status !== 0) throw new Error(`couldn't read savedit's words and ranges: ${server.stderr}`);
const { words: WORDS, ranges: RANGES } = JSON.parse(server.stdout);
const P = "1/GameplayProgression", INV = `${P}/State/Inventory`;
const DATA = { "1": { GameplayProgression: { Level: 5, FreshKill: { Value: 62 }, Stats: "(Prowess=90.000000,Strength=85.000000)",
  State: { Inventory: { "Gameplay.Inventory.Consumable.SmallHealingHerb": 2, "Gameplay.Inventory.Materials.Moss": 4 } } } },
  Shared: { General: { CurrentCatSlot: 1 }, SettingsData: { MasterVolume: 1 },
            InputKeyboard: { Player_Jump: "0,Player_Jump,SpaceBar,1.000000.1" } } };
const SAY = { words: WORDS, cats: { "1": "Fawnstar" }, current: "1", items: { "Gameplay.Inventory.Materials.Moss": "Moss" } };

test("a range clamp refuses -5 and 999999 for Level", () => {
  assert.equal(S.rangeProblem(`${P}/Level`, -5, RANGES), "Level goes from 1 to 20, not -5");
  assert.equal(S.rangeProblem(`${P}/Level`, 999999, RANGES), "Level goes from 1 to 20, not 999999");
  assert.equal(S.rangeProblem(`${P}/Level`, 2.5, RANGES), "Level has to be a whole number");
  assert.equal(S.rangeProblem(`${P}/Level`, 1e301, RANGES), "Level goes from 1 to 20, not 1e+301");
  assert.equal(S.rangeProblem(`${P}/Level`, NaN, RANGES), "Level has to be a number");
  assert.equal(S.rangeProblem(`${P}/Level`, 20, RANGES), null);
  assert.equal(S.rangeProblem(`${INV}/X`, -1, RANGES), "A count of things carried goes from 0 or more, not -1");
  assert.equal(S.rangeProblem("Shared/SettingsData/MasterVolume", 0.5, RANGES), null);
  assert.equal(S.rangeProblem("0/Anything/Else", -9, RANGES), null);
  assert.deepEqual(S.rangeFor(`${P}/Level`, RANGES).max, 20);
});

test("a preset expands to the right paths and values", () => {
  const list = S.emptyList();
  S.preset("max-level", list, DATA, "1");
  assert.deepEqual(list.set, { [`${P}/Level`]: 20 });   // no Experience in this save: only what it has
  S.preset("fill-pile", list, DATA, "1");
  assert.equal(list.set[`${P}/FreshKill/Value`], 100);
  S.preset("give-herbs", list, DATA, "1");
  assert.equal(list.set[`${INV}/Gameplay.Inventory.Consumable.SmallHealingHerb`], 7, "an item it has: five more");
  assert.deepEqual(list.add[INV], { "Gameplay.Inventory.Consumable.MediumHealingHerb": 5, "Gameplay.Inventory.Consumable.BigHealingHerb": 5,
    "Gameplay.Inventory.Consumable.SmallCatnip": 5 });
  // A cat that hasn't started yet: nothing.
  const none = S.emptyList();
  S.preset("max-level", none, DATA, "0");
  assert.equal(S.isEmpty(none), true);
  // A pile that's full already: nothing goes in the list (the page says "already full", not "added").
  const full = S.emptyList(), at100 = JSON.parse(JSON.stringify(DATA));
  at100["1"].GameplayProgression.FreshKill.Value = 100;
  S.preset("fill-pile", full, at100, "1");
  assert.equal(S.isEmpty(full), true);
  // The herbs Give herbs names, in a sentence.
  assert.equal(S.andList(["Horsetail Stalks", "Marigold Petal", "Comfrey Poultice", "Lamb's Ear Leaves"]),
    "Horsetail Stalks, Marigold Petal, Comfrey Poultice and Lamb's Ear Leaves");
  assert.equal(S.andList(["Moss"]), "Moss");
  assert.equal(S.andList(["Moss", "Fern"]), "Moss and Fern");
});

test("describe turns a path into words", () => {
  assert.equal(S.describe(`${P}/Level`, SAY), "Fawnstar's level");
  assert.equal(S.describe(`${INV}/Gameplay.Inventory.Materials.Moss`, SAY), "Fawnstar's Moss");
  assert.equal(S.describe(`${INV}/Gameplay.Inventory.Consumable.SmallHealingHerb`, SAY), "Fawnstar's Small Healing Herb");
  assert.equal(S.describe("0/GameplayProgression/Level", SAY), "your 1st game's cat's level");
  assert.equal(S.describe(`${P}/Level`, { ...SAY, cats: {} }), "your cat's level");
  assert.equal(S.describe("Shared/SettingsData/MasterVolume", SAY), "the game's setting master volume");
  assert.equal(S.describe(`${P}/QuestProgression`, SAY), "Fawnstar's quest progression");
  assert.equal(S.describe("Shared/General/CurrentCatSlot", SAY), "Current Cat Slot");
  assert.equal(S.itemWords("Gameplay.Inventory.Cosmetic.Neck.DogCollar.1"), "Neck Dog Collar 1");
  assert.equal(S.said(null), "none");
  assert.equal(S.said(true), "on");
  assert.equal(S.said(0.5), "0.5");
});

test("the read-only rule covers bindings, cat records and struct text", () => {
  assert.match(S.readOnly("Shared/InputKeyboard/Player_Jump", "0,Player_Jump,SpaceBar,1.000000.1"), /Controls page/);
  assert.match(S.readOnly("Shared/InputGamepad", {}), /Controls page/);
  assert.match(S.readOnly(`${P}/Gameplay.Combat.Character.Cat.Player/Customization`, "(ClanType=RiverClan)"), /Your cat and Names pages/);
  assert.match(S.readOnly(`${P}/Gameplay.Combat.Character.Cat.Player/State/Health`, 100), /Refills in play/);
  assert.match(S.readOnly("0/NPCData/Clans/x", "(Role=Warrior,FurIdx=2)"), /one piece of text/);
  assert.match(S.readOnly(`${P}/Stats`, DATA["1"].GameplayProgression.Stats), /Combat stats card/);
  assert.equal(S.readOnly(`${P}/Level`, 5), null);
  assert.equal(S.readOnly("Shared/SettingsData/MasterVolume", 1), null);
});

test("an add for an item the save has becomes a set", () => {
  const list = S.emptyList();
  S.addKey(list, DATA, INV, "Gameplay.Inventory.Materials.Moss", 9);
  assert.deepEqual(list, { set: { [`${INV}/Gameplay.Inventory.Materials.Moss`]: 9 }, add: {}, remove: [] });
  S.addKey(list, DATA, INV, "Gameplay.Inventory.Materials.Stick", 3);
  assert.deepEqual(list.add, { [INV]: { "Gameplay.Inventory.Materials.Stick": 3 } });
  // Remove: an added one leaves the list; one the save has is taken out of the save.
  S.removeKey(list, DATA, `${INV}/Gameplay.Inventory.Materials.Stick`);
  S.removeKey(list, DATA, `${INV}/Gameplay.Inventory.Materials.Moss`);
  assert.deepEqual(list, { set: {}, add: {}, remove: [`${INV}/Gameplay.Inventory.Materials.Moss`] });
  assert.equal(S.after(list, DATA, `${INV}/Gameplay.Inventory.Materials.Moss`), undefined);
  // The save's own value takes a change away.
  S.setValue(list, DATA, `${P}/Level`, 6);
  S.setValue(list, DATA, `${P}/Level`, 5);
  assert.deepEqual(list.set, {});
});

test("the list in words, as save.json, and as the changes the route takes", () => {
  const list = S.emptyList();
  S.setValue(list, DATA, `${P}/FreshKill/Value`, 100);
  S.addKey(list, DATA, INV, "Gameplay.Inventory.Consumable.SmallCatnip", 5);
  S.removeKey(list, DATA, `${INV}/Gameplay.Inventory.Materials.Moss`);
  assert.deepEqual(S.entries(list, DATA, SAY).map(c => `${c.label}: ${S.said(c.was)} -> ${c.kind === "remove" ? "taken out" : S.said(c.now)}`), [
    "Fawnstar's fresh-kill pile: 62 -> 100", "Fawnstar's Small Catnip: none -> 5", "Fawnstar's Moss: 4 -> taken out"]);
  assert.deepEqual(S.toChanges(list), [{ path: `${P}/FreshKill/Value`, value: 100 },
    { add: INV, key: "Gameplay.Inventory.Consumable.SmallCatnip", value: 5 }, { remove: `${INV}/Gameplay.Inventory.Materials.Moss` }]);
  const file = S.toSaveJson(list);
  assert.deepEqual(S.fromSaveJson(file), list);
  assert.ok(file._help.includes("once"));
  assert.deepEqual(S.fromSaveJson({ set: { _help: "x", a: 1 }, add: { _help: "y" }, remove: "nope" }), { set: { a: 1 }, add: {}, remove: [] });
  assert.deepEqual(S.problems({ set: { [`${P}/Level`]: 30 }, add: {}, remove: [] }, RANGES, SAY), ["Fawnstar's level: Level goes from 1 to 20, not 30"]);
  S.forget(list, { kind: "remove", path: `${INV}/Gameplay.Inventory.Materials.Moss` });
  S.forget(list, { kind: "add", path: `${INV}/Gameplay.Inventory.Consumable.SmallCatnip` });
  S.forget(list, { kind: "set", path: `${P}/FreshKill/Value` });
  assert.equal(S.isEmpty(list), true);
});

test("a combat stat changes in place, the rest of the text as it was", () => {
  const text = DATA["1"].GameplayProgression.Stats;
  assert.deepEqual(S.readStats(text), { Prowess: 90, Strength: 85 });
  assert.equal(S.writeStat(text, "Strength", 88.5), "(Prowess=90.000000,Strength=88.500000)");
  assert.equal(S.writeStat("(Prowess=1.000000,Odd=x,Strength=2.000000)", "Prowess", 3), "(Prowess=3.000000,Odd=x,Strength=2.000000)");
});
