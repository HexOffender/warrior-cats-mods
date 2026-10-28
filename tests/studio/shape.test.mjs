// studio/lib/shape.js's placeMesh, which draws a model where items.json's "place" puts it, against what
// wcmods.models.place does at install: fixtures/place.json, written by tests/unit/test_repo.py.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { install } from "./lib/dom.mjs";

const dom = install();
const shape = await import(dom.studio("lib/shape.js"));
const fixture = JSON.parse(fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "place.json"), "utf8"));

function close(a, b, what) {
  assert.equal(a.length, b.length, `${what}: ${a.length} numbers, not ${b.length}`);
  for (let i = 0; i < a.length; i++) assert.ok(Math.abs(a[i] - b[i]) < 1e-4, `${what}: [${i}] is ${a[i]}, not ${b[i]}`);
}

test("placeMesh leaves a mesh alone without a place, and keeps its triangles", () => {
  const mesh = fixture.mesh;
  assert.equal(shape.placeMesh(mesh, null), mesh);
  assert.equal(shape.placeMesh(null, { scale: 2 }), null);
  const placed = shape.placeMesh(mesh, {});
  close(placed.p, mesh.p, "no change");
  assert.deepEqual(placed.t, mesh.t);
  assert.notEqual(placed.p, mesh.p, "a copy, not the mesh itself");
});

for (const c of fixture.cases) {
  test(`placeMesh matches models.place for ${JSON.stringify(c.place)}${c.base ? " about the base" : ""}`, () => {
    close(shape.placeMesh(fixture.mesh, c.place, c.base).p, c.p, JSON.stringify(c.place));
  });
}

test("a turn about the middle keeps the middle, and a move moves it", () => {
  const mesh = { p: [0, 0, 0, 2, 0, 0, 0, 4, 0, 0, 0, 6], t: [0, 1, 2] };
  const mid = m => [0, 1, 2].map(k => { const vals = []; for (let i = k; i < m.p.length; i += 3) vals.push(m.p[i]); return (Math.min(...vals) + Math.max(...vals)) / 2; });
  const turned = shape.placeMesh(mesh, { yaw: 180 });
  close(mid(turned), mid(mesh), "middle after a half turn");
  close(turned.p.slice(3, 6), [0, 4, 0], "the point at the right end is at the left end after a half turn");
  const moved = shape.placeMesh(mesh, { left: 1, forward: -2, up: 3 });
  close(mid(moved), [1 + 1, 2 - 2, 3 + 3], "middle after a move");
  const grounded = shape.placeMesh(mesh, { scale: 2 }, true);
  assert.equal(Math.min(grounded.p[2], grounded.p[5], grounded.p[8], grounded.p[11]), 0, "the base stays on the ground when scaled");
});
