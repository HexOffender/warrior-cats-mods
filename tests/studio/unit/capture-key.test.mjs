// wc.captureKey, the dialog that asks for a key (the Controls page's rebinding and the Animations page's emote
// key), under the DOM shim: it cancels on Escape, on Cancel and on a click outside it; one is open at a time;
// a key that's taken is said and needs a second press, on a controller too; and once it's closed, no keystroke
// anywhere is taken. The Controls page's extras: a mouse zone, a why line, and menus that take no mouse button.
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

// A controller the test presses, read a frame at a time: frames() runs the frames asked for since the last call.
function fakePad() {
  const pressed = new Set(), queue = [];
  const real = { raf: globalThis.requestAnimationFrame, caf: globalThis.cancelAnimationFrame, pads: navigator.getGamepads };
  globalThis.requestAnimationFrame = fn => queue.push(fn);
  globalThis.cancelAnimationFrame = () => {};   // a closed dialog's frame just finds it closed
  navigator.getGamepads = () => [{ id: "Test pad (STANDARD GAMEPAD)", axes: [0, 0, 0, 0],
    buttons: Array.from({ length: 16 }, (_, i) => ({ pressed: pressed.has(i), value: pressed.has(i) ? 1 : 0 })) }];
  return {
    press: i => pressed.add(i), release: i => pressed.delete(i),
    frames() { const run = queue.splice(0).filter(Boolean); for (const fn of run) fn(); return run.length; },
    restore() { globalThis.requestAnimationFrame = real.raf; globalThis.cancelAnimationFrame = real.caf; navigator.getGamepads = real.pads; },
  };
}

test("the controller is read until the dialog closes: a taken button pressed again is used", async () => {
  const pad = fakePad();
  try {
    const got = wc.captureKey({ title: "Pad", pad: true, reserved: { Gamepad_DPad_Up: "D-pad up is Wave's button too" } });
    pad.frames();                     // the first frame: nothing pressed
    pad.press(12);
    pad.frames();
    assert.match(overlay().querySelector("#capture-msg").textContent, /Wave's button too.*again to use it anyway/);
    assert.equal(pad.frames(), 1, "still listening after the taken button");
    assert.ok(overlay(), "held down, it isn't a second press");
    pad.release(12);
    pad.frames();
    pad.press(12);
    pad.frames();
    assert.equal(await got, "Gamepad_DPad_Up");
    assert.equal(pad.frames(), 0, "and it stops listening once it's closed");
  } finally { pad.restore(); }
});

test("a button held when the dialog opens isn't taken for a press", async () => {
  const pad = fakePad();
  try {
    pad.press(0);
    const got = wc.captureKey({ title: "Held", pad: true });
    pad.frames(); pad.frames();
    assert.ok(overlay(), "A was down before it opened");
    pad.press(1);
    pad.frames();
    assert.equal(await got, "Gamepad_FaceButton_Right");
  } finally { pad.restore(); }
});

test("zone: clicks and the wheel bind mouse buttons only in its box; a click outside still cancels", async () => {
  let got = wc.captureKey({ title: "Zone", zone: true });
  const o = overlay(), box = o.querySelector(".capture-zone");
  assert.equal(box.textContent, "Or click a mouse button, or turn the wheel, here");
  o.dispatch("mousedown", { target: o.querySelector("h2"), button: 2 });
  assert.ok(overlay(), "a click on the dialog's words binds nothing, and doesn't cancel");
  o.dispatch("mousedown", { target: box, button: 2 });
  assert.equal(await got, "RightMouseButton");
  got = wc.captureKey({ title: "Wheel", zone: "Click or scroll here" });
  assert.equal(overlay().querySelector(".capture-zone").textContent, "Click or scroll here");
  overlay().dispatch("wheel", { target: overlay().querySelector(".capture-zone"), deltaY: -3 });
  assert.equal(await got, "MouseScrollUp");
  got = wc.captureKey({ title: "Outside", zone: true });
  overlay().dispatch("mousedown", { target: overlay(), button: 0 });
  assert.equal(await got, null);
  wc.captureKey({ title: "No zone on a pad", pad: true, zone: true });
  assert.equal(overlay().querySelector(".capture-zone"), null);
  press("Escape");
});

test("why: a refused key is said in the alert line and the dialog stays; a warning lets it through and is said after", async () => {
  const why = k => (k === "Insert" ? { refuse: "Insert opens the mod menu (wcmods); pick another key." }
    : k === "F6" ? "F6 turns mouse look on and off" : k === "G" ? { warn: "G also opens the Emote wheel (Emote wheel)." } : null);
  const got = wc.captureKey({ title: "Why", why });
  const line = overlay().querySelector(".capture-why");
  assert.equal(line.hidden, true);
  assert.equal(line.getAttribute("role"), "alert");
  press("Insert");
  assert.equal(line.hidden, false);
  assert.equal(line.textContent, "Insert opens the mod menu (wcmods); pick another key.");
  press("Insert");
  assert.ok(overlay(), "a refused key isn't used on a second press");
  press("F6");
  assert.equal(line.textContent, "F6 turns mouse look on and off");
  press("KeyG", "g");
  assert.equal(await got, "G");
  await tick();
  assert.match(dom.byId.toasts.textContent, /G also opens the Emote wheel/);
});

test("where menus: a mouse button is refused, and there's no zone", async () => {
  const got = wc.captureKey({ title: "Menus", where: "menus", mouse: true, zone: true });
  assert.equal(overlay().querySelector(".capture-zone"), null);
  overlay().dispatch("mousedown", { target: overlay().querySelector("h2"), button: 0 });
  assert.match(overlay().querySelector(".capture-why").textContent, /In menus a click goes to the button under the cursor/);
  press("Enter");
  assert.equal(await got, "Enter");
});
