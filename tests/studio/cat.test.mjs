// studio/lib/cat.js, the drawn cat Palettes and Your cat share, under node:test: which scars it draws where. The
// painting itself (fills, strokes, the eye strips) is checked in a real browser by e2e/looks.test.mjs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { STUDIO } from "./lib/dom.mjs";

const { scarShapes, catSvg } = await import(pathToFileURL(path.join(STUDIO, "lib", "cat.js")).href);

test("ear scars are torn or notched, on the cat's own right, left or both, as catcolours.SCAR_TYPES counts them", () => {
  const ears = n => scarShapes({ ear: n }).ears.map(e => `${e.kind}-${e.side}`);
  assert.deepEqual([1, 2, 3, 4, 5, 6].map(ears), [["torn-right"], ["torn-left"], ["torn-right", "torn-left"],
    ["notch-right"], ["notch-left"], ["notch-right", "notch-left"]]);
  assert.deepEqual(ears(0), []);
  assert.deepEqual(ears(7), [], "a number past the game's draws nothing");
  // The cat's right ear is on the drawing's left: its cut is on the left half of the 360-wide picture.
  const right = scarShapes({ ear: 4 }).ears[0].d.match(/\d+/g).map(Number).filter((_, i) => i % 2 === 0);
  assert.ok(right.every(x => x < 180), right.join(","));
});

test("an eye scar shuts an eye: odd numbers the cat's right, even its left", () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5, 6].map(n => scarShapes({ eye: n }).shut), [null, "right", "left", "right", "left", "right", "left"]);
  assert.deepEqual(scarShapes(), { ears: [], shut: null });
});

test("two drawings on one page don't share their ids", () => {
  const ids = svg => [...svg.matchAll(/id="([^"]+)"/g)].map(m => m[1]);
  const a = ids(catSvg("pal")), b = ids(catSvg("cat"));
  assert.ok(a.length >= 5 && a.every(id => id.startsWith("pal-")));
  assert.deepEqual(a.filter(id => b.includes(id)), []);
  assert.match(catSvg("cat", "Hawkleaf's look"), /aria-label="Hawkleaf's look"/);
});
