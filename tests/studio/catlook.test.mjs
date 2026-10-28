// studio/lib/catlook.js, the Your cat page's cats.json, under node:test: what it reads, what it writes back, and
// what it keeps as written because the page can't change it.
import { test } from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { STUDIO } from "./lib/dom.mjs";

const C = await import(pathToFileURL(path.join(STUDIO, "lib", "catlook.js")).href);

// What GET /cat says the build takes (wcmods/catcolours.py), as the page gets it.
const INFO = {
  parts: { fur: "Fur Color", paws: "Paws Color", ears: "Ears Color", nose: "Nose Color", whiskers: "Whiskers Color" },
  slot_parts: ["fur", "pattern", "marking", "eye_left", "eye_right"], game_slots: 25,
  look: { parts: { body: 9, fur: 9, tail: 9, ears: 9, eyes: 9, whiskers: 9, face: 9, pattern: 20, marking: 20 }, size: [0.05, 1.5] },
  scars: { types: {
    ear: [["torn-right", "Torn, right"], ["torn-left", "Torn, left"], ["torn-both", "Torn, both"], ["notch-right", "Notched, right"],
      ["notch-left", "Notched, left"], ["notch-both", "Notched, both"]],
    eye: [["ring-right", ""], ["ring-left", ""], ["slash-right", ""], ["slash-left", ""], ["claws-right", ""], ["claws-left", ""]],
    back: [["bite-1", ""], ["bite-2", ""], ["claws-1", ""], ["claws-2", ""]], chest: [["bite", ""], ["claws", ""]] } },
};
const K = C.knownFrom(INFO);
const round = one => C.oneJson(C.parseOne(one, K), K);

test("scars: none stays none, one place none is just that place", () => {
  assert.deepEqual(round({ scars: "none" }), { scars: "none" });
  assert.deepEqual(round({ scars: { back: "none" } }), { scars: { back: "none" } });
  const l = C.parseOne({ scars: { ear: "notch-left", body: 2 } }, K);
  assert.deepEqual(l.scars, { ear: 5, back: 2 }, "by name, and the save's word for the back");
  assert.deepEqual(C.oneJson(l, K), { scars: { ear: "notch-left", back: "bite-2" } });
});

test("eyes: one number for both is written back as one, two numbers stay two", () => {
  const l = C.parseOne({ slots: { eyes: 3 } }, K);
  assert.deepEqual(l.slots, { eye_left: 3, eye_right: 3 });
  assert.deepEqual(C.oneJson(l, K), { slots: { eyes: 3 } });
  assert.deepEqual(round({ slots: { eye_left: 3, eye_right: 5 } }), { slots: { eye_left: 3, eye_right: 5 } });
});

test("colours in any form the build reads load, and go back as #RRGGBB", () => {
  const l = C.parseOne({ colours: { fur: "red", nose: [0, 255, 0], paws: "#11223344", ears: "abc" } }, K);
  assert.deepEqual(l.colours, { fur: "#FF0000", nose: "#00FF00", paws: "#112233", ears: "#AABBCC" });
  assert.deepEqual(C.oneJson(l, K).colours, { fur: "#FF0000", nose: "#00FF00", paws: "#112233", ears: "#AABBCC" });
});

test("what the page can't change is listed, written back as it was, and goes when removed", () => {
  const one = { slots: { coat: 3, fur: 30, pattern: 40 }, colours: { tail: "#ffffff", nose: "not a colour" },
    scars: { ear: 9, eye: "ring-left" }, look: { wings: 2, tail: 12, body: 4 }, notes: "mine", _why: "kept" };
  const l = C.parseOne(one, K);
  assert.deepEqual(l.slots, { pattern: 40 }, "new pattern colours are any number");
  assert.deepEqual(C.cantChange(l).map(e => [e.where, e.value]), [
    ["notes", "mine"], ["colours.tail", "#ffffff"], ["colours.nose", "not a colour"], ["slots.coat", 3], ["slots.fur", 30],
    ["scars.ear", 9], ["look.wings", 2], ["look.tail", 12]]);
  const back = C.oneJson(l, K);
  assert.deepEqual(back, { notes: "mine", _why: "kept", colours: { tail: "#ffffff", nose: "not a colour" },
    slots: { coat: 3, fur: 30, pattern: 40 }, scars: { ear: 9, eye: "ring-left" }, look: { wings: 2, tail: 12, body: 4 } });
  for (const e of C.cantChange(l).filter(e => e.where === "slots.coat" || e.where === "notes")) e.remove();
  const after = C.oneJson(l, K);
  assert.equal("coat" in after.slots, false);
  assert.equal("notes" in after, false);
  assert.equal(after._why, "kept", "a note in the file is kept, and isn't listed");
});

test("a size outside the game's scale isn't taken in, and is kept as written", () => {
  const l = C.parseOne({ look: { size: 3 } }, K);
  assert.deepEqual(l.look, {});
  assert.deepEqual(C.cantChange(l).map(e => e.where), ["look.size"]);
  assert.deepEqual(C.oneJson(l, K), { look: { size: 3 } });
  assert.deepEqual(C.parseOne({ look: { size: 0.45 } }, K).look, { size: 0.45 });
});

// Cats as GET /cat lists them: two called Hawkleaf, and Mothfang, called Duskfang before a names mod.
const CATS = [
  { target: "Clans/WindClan/Warrior/0", name: "Hawkleaf", aliases: { names: ["hawkleaf"],
    places: ["Clans/WindClan/Warrior/0", "WindClan/Warrior/0", "Warrior/0", "NPCData/Clans/WindClan/Warrior/0"] } },
  { target: "Clans/WindClan/Warrior/1", name: "Hawkleaf", aliases: { names: ["hawkleaf"],
    places: ["Clans/WindClan/Warrior/1", "WindClan/Warrior/1", "Warrior/1", "NPCData/Clans/WindClan/Warrior/1"] } },
  { target: "Mothfang", name: "Mothfang", aliases: { names: ["duskfang", "mothfang"],
    places: ["Clans/WindClan/Deputy/0", "WindClan/Deputy/0", "Deputy/0", "NarrativeRoles/TheDeputy"] } },
];

test("a file's key lands on the cats the build would change: places as written, names in any case", () => {
  assert.deepEqual(C.catsFor("WindClan/Warrior/1", CATS), [CATS[1]]);
  assert.deepEqual(C.catsFor(" Warrior/1 ", CATS), [CATS[1]]);
  assert.deepEqual(C.catsFor("windclan/warrior/1", CATS), [], "places keep their case, as the build matches them");
  assert.deepEqual(C.catsFor("hawkleaf", CATS), [CATS[0], CATS[1]], "a name two cats share changes both");
  assert.deepEqual(C.catsFor("DUSKFANG", CATS), [CATS[2]], "the name before a names mod's rename too");
  assert.deepEqual(C.catsFor("NarrativeRoles/TheDeputy", CATS), [CATS[2]]);
  assert.deepEqual(C.catsFor("2/Duskfang", CATS), [], "another game's cat");
  assert.deepEqual(C.catsFor("Nobody", CATS), []);
});

test("a cat's look is kept under a key that means it alone", () => {
  assert.equal(C.keyFor(CATS[1], ["WindClan/Warrior/1", "Hawkleaf"], CATS), "WindClan/Warrior/1");
  assert.equal(C.keyFor(CATS[0], ["WindClan/Warrior/1", "Hawkleaf"], CATS), "Clans/WindClan/Warrior/0",
    "the shared name isn't its own: a new entry by its place");
  assert.equal(C.keyFor(CATS[2], ["duskfang", "Mothfang"], CATS), "Mothfang", "its own target first");
  assert.equal(C.keyFor(CATS[2], ["duskfang"], CATS), "duskfang");
  assert.equal(C.roleWords("MedicineCat"), "medicine cat");
  assert.equal(C.roleWords(""), "");
});

test("the whole file round-trips: other cats, notes, the file's own keys, and a cat with nothing left goes", () => {
  const file = { _help: "old", version: 2, player: { look: { tail: 3 } },
    cats: { Hawkleaf: { slots: { fur: 4 } }, "WindClan/Warrior/1": { scars: "none" }, _comment: "two cats" } };
  const { looks, fileExtra } = C.load(file, K);
  assert.deepEqual(Object.keys(looks), ["player", "Hawkleaf", "WindClan/Warrior/1"]);
  assert.deepEqual(C.cantChange(looks.player, fileExtra).map(e => e.where), ["version"]);
  const back = C.toJson(looks, fileExtra, K);
  assert.deepEqual(back, { _help: C.HELP, player: { look: { tail: 3 } },
    cats: { _comment: "two cats", Hawkleaf: { slots: { fur: 4 } }, "WindClan/Warrior/1": { scars: "none" } }, version: 2 });
  // Every part of a cat cleared on the page: it's left out of the file.
  looks.Hawkleaf.slots = {};
  assert.equal("Hawkleaf" in C.toJson(looks, fileExtra, K).cats, false);
  assert.deepEqual(C.toJson(C.load(null, K).looks, {}, K), { _help: C.HELP });
});
