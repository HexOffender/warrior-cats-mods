// wc.captureKey, the dialog that asks for a key (the Controls page's rebinding and the Animations page's emote
// key), under the DOM shim: it cancels on Escape, on Cancel and on a click outside it; one is open at a time;
// a key that's taken is said and needs a second press; and once it's closed, no keystroke anywhere is taken.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "../lib/dom.mjs";

const dom = install();
const wc = await import(dom.studio("lib/wc.js"));
const keys = await import(dom.studio("lib/keys.js"));

const press = (code, key = code) => window.dispatchEvent({ type: "keydown", code, key, preventDefault() {}, stopPropagation() {} });
const overlay = () => document.body.querySelector('[role="dialog"]');
const button = text => overlay().querySelectorAll("button").find(b => b.textContent === text);

test("a key pressed in the dialog is the game's name for it, and the dialog goes", async () => {
  const got = wc.captureKey({ title: "The key for Yawn" });
  assert.ok(overlay(), "the dialog is open");
  assert.equal(document.activeElement, overlay().querySelector(".card"), "focus starts on the dialog itself");
  press("F7");
  assert.equal(await got, "F7");
  assert.equal(overlay(), null);
  assert.equal(dom.windowListeners.keydown.length, 0, "its keyboard listener goes with it");
});

test("Escape, Cancel and a click outside cancel, and leave nothing listening", async () => {
  let got = wc.captureKey({ title: "Escape" });
  press("Escape");
  assert.equal(await got, null);
  got = wc.captureKey({ title: "Cancel" });
  button("Cancel").click();
  assert.equal(await got, null);
  got = wc.captureKey({ title: "Outside" });
  const o = overlay();
  o.dispatch("mousedown", { target: o, button: 0 });
  assert.equal(await got, null);
  assert.equal(overlay(), null);
  press("KeyE", "e");   // typing on the page afterwards is the page's
  assert.equal(dom.windowListeners.keydown.length, 0);
});

test("leaving the page cancels, and opening a second dialog cancels the first", async () => {
  let got = wc.captureKey({ title: "Leaving" });
  window.dispatchEvent({ type: "hashchange" });
  assert.equal(await got, null);
  const first = wc.captureKey({ title: "First" });
  const second = wc.captureKey({ title: "Second" });
  assert.equal(await first, null);
  assert.equal(document.body.querySelectorAll('[role="dialog"]').length, 1, "one at a time");
  press("F8");
  assert.equal(await second, "F8");
});

test("Tab moves among the dialog's buttons and is never a key; a key the game doesn't know is said", async () => {
  const got = wc.captureKey({ title: "Tab", chips: ["Escape"] });
  press("Tab");
  assert.equal(document.activeElement, button("Escape"), "Tab went to the first button");
  press("Tab");
  assert.equal(document.activeElement, button("Cancel"));
  press("MetaLeft", "Meta");
  assert.match(overlay().querySelector("#capture-msg").textContent, /isn't one the game knows/);
  button("Escape").click();   // its chip binds Escape itself
  assert.equal(await got, "Escape");
});

test("a key that's taken is said, and a second press uses it anyway", async () => {
  const got = wc.captureKey({ title: "Taken", reserved: { F8: "F8 is Wave's key too, and only one of them would play" } });
  press("F8");
  await tick();
  assert.ok(overlay(), "still open after the first press");
  assert.match(overlay().querySelector("#capture-msg").textContent, /Wave's key too.*Press F8 again to use it anyway/);
  press("F8");
  assert.equal(await got, "F8");
});

test("the controller dialog offers its buttons, and ignores the keyboard but for Escape", async () => {
  const got = wc.captureKey({ title: "Pad", pad: true });
  assert.equal(overlay().querySelectorAll("button.chip").length, keys.PAD_BUTTONS.length);
  press("KeyA", "a");
  assert.ok(overlay(), "a key isn't a controller button");
  overlay().querySelectorAll("button.chip")[12].click();
  assert.equal(await got, "Gamepad_DPad_Up");
});

test("with mouse buttons on, a click inside binds the button instead of cancelling", async () => {
  const got = wc.captureKey({ title: "Mouse", mouse: true });
  const o = overlay();
  o.dispatch("mousedown", { target: o.querySelector("h2"), button: 3 });
  assert.equal(await got, "ThumbMouseButton");
});
