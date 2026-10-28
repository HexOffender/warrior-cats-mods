// studio/lib/colour.js under node:test: parse reads a colour every way wcmods/colors.py does, and its names are
// colors.py's NAMED (read from the Python file, so the two can't drift apart).
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { REPO, STUDIO } from "./lib/dom.mjs";

const { color } = await import(pathToFileURL(path.join(STUDIO, "lib", "colour.js")).href);

test("parse takes names, [r, g, b] lists and 3, 6 or 8 hex digits, as colors.parse does", () => {
  const cases = [
    ["orange", "#FF8C00"], [" Teal ", "#008080"], ["#11223344", "#112233"], ["11223344", "#112233"], ["abc", "#AABBCC"],
    ["#a1b2c3", "#A1B2C3"], ["##fff", "#FFFFFF"], [[255, 0, 0], "#FF0000"], [[300, -5, 127.6], "#FF0080"],
    [[0, 229, 255, 128], "#00E5FF"], [["255", "0", "0"], "#FF0000"], [123, "#112233"],
  ];
  for (const [value, want] of cases) assert.equal(color.parse(value), want, JSON.stringify(value));
});

test("parse refuses what colors.parse refuses", () => {
  for (const bad of ["#GGGGGG", "#ff", "#ffff", "#fffffff", "reddish", "", null, undefined, true, {}, [], [1, 2], [1, 2, 3, 4, 5],
    ["a", 0, 0], [1, null, 2], ["", 0, 0]]) {
    assert.equal(color.parse(bad), null, JSON.stringify(bad));
  }
});

test("parse's names are wcmods/colors.py's NAMED", () => {
  const py = fs.readFileSync(path.join(REPO, "wcmods", "colors.py"), "utf8");
  const block = /NAMED = \{([^}]*)\}/.exec(py)[1];
  const named = Object.fromEntries([...block.matchAll(/"(\w+)":\s*"([0-9a-f]{6})"/g)].map(m => [m[1], m[2]]));
  assert.ok(Object.keys(named).length >= 15, "read colors.py's names");
  assert.deepEqual(color.NAMED, named);
});

test("normHex stays the pickers' check: 3 or 6 hex digits only", () => {
  assert.equal(color.normHex("abc"), "#AABBCC");
  for (const bad of ["red", "#11223344", "[255,0,0]"]) assert.equal(color.normHex(bad), null, bad);
});
