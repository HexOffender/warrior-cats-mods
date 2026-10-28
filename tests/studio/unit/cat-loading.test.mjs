// Your cat (studio/sections/cat.js) under the DOM shim: the first GET /cat on a real save takes a couple of seconds,
// so until it answers the page shows its title and "Reading your save…", not nothing; the line goes once it answers.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "../lib/dom.mjs";

const dom = install();
// GET /cat with no save yet (wcmods/studio.py cat_info): no cats, the game's 25 slots, nothing chosen.
const NO_SAVE = {
  current: {}, save_problem: "No save yet: start the game once and come back", palette: {}, eyes: {}, game_slots: 25,
  slot_parts: ["fur", "pattern", "marking", "eye_left", "eye_right"], feral_slots: [20, 21, 22, 23, 24],
  parts: { fur: "Fur Color", paws: "Paws Color", ears: "Ears Color", nose: "Nose Color", whiskers: "Whiskers Color" },
  scars: { current: {}, types: { ear: [], eye: [], back: [], chest: [] } },
  look: { current: {}, parts: { body: 2, fur: 2, tail: 2, ears: 2, eyes: 2, whiskers: 2, face: 2, pattern: 2, marking: 2 }, size: [0.05, 1.5] },
  cats: [], your_clan: null, current_slot: null,
};

test("Your cat says it's reading your save until GET /cat answers", async () => {
  let answer;
  dom.routes = { "GET /cat": () => new Promise(resolve => { answer = resolve; }), "GET /mods": () => [] };
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  const page = (await import(dom.studio("sections/cat.js"))).default;
  const root = dom.document.createElement("div");
  dom.body.append(root);
  const mounted = page.mount(root, wc);
  await tick();
  const text = () => root.textContent;
  assert.equal(root.querySelector("h1").textContent, "Your cat");
  assert.equal(root.querySelector(".reading").textContent, "Reading your save…");
  assert.equal(root.querySelector(".reading").getAttribute("role"), "status");
  assert.ok(text().includes("How this works"), "its help is there while it waits");
  // It answers (no save yet, here): the page draws its cards, and the reading line goes.
  answer(NO_SAVE);
  // The drawn cat needs a real browser's SVG (e2e/looks.test.mjs draws it), so under the shim the page stops at
  // drawing it, after its cards are on the page: what's checked here is all there by then.
  const done = await mounted.then(() => null, e => e);
  assert.ok(!done || /paintCat/.test(done.stack), done && done.stack);
  assert.equal(root.querySelector(".reading"), null);
  assert.ok(!text().includes("Reading your save"), text().slice(0, 200));
  assert.ok(root.querySelector(".cat-stage"), "the page's cards are drawn");
  assert.equal(root.querySelectorAll("h1").length, 1, "one title, not a second one when the page draws");
  assert.equal(root.children[0].querySelector("h1").textContent, "Your cat", "the title stays at the top");
});

test("when GET /cat fails, Your cat throws, so the page loader puts its error card where the reading line was", async () => {
  dom.routes = { "GET /cat": () => { throw { status: 500, error: "Something went wrong" }; }, "GET /mods": () => [] };
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  const page = (await import(dom.studio("sections/cat.js"))).default;
  const root = dom.document.createElement("div");
  dom.body.append(root);
  // The studio's page loader (app.js open) puts the error card in the page's place when mount throws.
  await assert.rejects(page.mount(root, wc), /Something went wrong/);
});
