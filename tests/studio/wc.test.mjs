// studio/lib/wc.js, the helpers every page uses, under node:test with the DOM shim in lib/dom.mjs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "./lib/dom.mjs";

const dom = install();
const wc = await import(dom.studio("lib/wc.js"));

// ---------- colours ----------
test("normHex takes 3 or 6 hex digits with or without # and gives #RRGGBB in capitals", () => {
  assert.equal(wc.color.normHex("abc"), "#AABBCC");
  assert.equal(wc.color.normHex("#a1B2c3"), "#A1B2C3");
  assert.equal(wc.color.normHex("  #fff "), "#FFFFFF");
  for (const bad of ["#ZZZZZZ", "#ff", "red", "", null, "#ffff"]) assert.equal(wc.color.normHex(bad), null, String(bad));
});

test("sRGB hex to linear and back round-trips, with black and white at the ends", () => {
  assert.deepEqual(wc.color.hexToLinear("#000000"), [0, 0, 0]);
  assert.deepEqual(wc.color.hexToLinear("#FFFFFF"), [1, 1, 1]);
  const mid = wc.color.hexToLinear("#808080");
  assert.ok(mid[0] > 0.2 && mid[0] < 0.22, "#808080 is about 0.21 linear");
  for (const hex of ["#FF8000", "#123456", "#0A0B0C"]) assert.equal(wc.color.linearToHex(wc.color.hexToLinear(hex)), hex);
  assert.equal(wc.color.linearToHex([2, -1, 0.5]), "#FF00BC");   // clamped
});

test("shade scales lightness and the moods keep a valid hex", () => {
  assert.equal(wc.color.shade("#FFFFFF", 0.5), "#808080");
  assert.equal(wc.color.shade("#FF0000", 1), "#FF0000");
  assert.equal(wc.color.shade("#404040", 0), "#000000");
  assert.deepEqual(Object.keys(wc.color.MOODS), ["vivid", "pastel", "moonlit", "ember"]);
  for (const mood of Object.keys(wc.color.MOODS)) assert.match(wc.color.mood("#9A8A78", mood), /^#[0-9A-F]{6}$/, mood);
  const sat = hex => wc.color.rgbToHsl(wc.color.hexToRgb(hex))[1];
  assert.ok(sat(wc.color.mood("#C04040", "pastel")) < sat("#C04040"), "pastel washes the colour out");
  assert.ok(sat(wc.color.mood("#C04040", "vivid")) > sat("#C04040"), "vivid deepens it");
});

// ---------- input names ----------
test("browser key codes become the game's key names", () => {
  const cases = { KeyW: "W", Digit3: "Three", Digit0: "Zero", Numpad7: "NumPadSeven", Space: "SpaceBar", Enter: "Enter",
    NumpadEnter: "Enter", ArrowUp: "Up", Backquote: "Tilde", F13: "F13", F1: "F1", ShiftLeft: "LeftShift", Quote: "Apostrophe" };
  for (const [code, key] of Object.entries(cases)) assert.equal(wc.input.keyFromEvent({ code }), key, code);
  for (const code of ["MetaLeft", "ContextMenu", "Unidentified", ""]) assert.equal(wc.input.keyFromEvent({ code }), null, code);
});

test("key labels read as a player would, per controller", () => {
  assert.equal(wc.input.keyLabel(""), "—");
  assert.equal(wc.input.keyLabel("Three"), "3");
  assert.equal(wc.input.keyLabel("NumPadSeven"), "Num 7");
  assert.equal(wc.input.keyLabel("SpaceBar"), "Space");
  assert.equal(wc.input.keyLabel("LeftMouseButton"), "Left mouse");
  assert.equal(wc.input.keyLabel("Gamepad_FaceButton_Bottom"), "A");
  assert.equal(wc.input.keyLabel("Gamepad_FaceButton_Bottom", "playstation"), "✕");
  assert.equal(wc.input.keyLabel("Gamepad_FaceButton_Bottom", "switch"), "B");
  assert.equal(wc.input.keyLabel("Gamepad_DPad_Up"), "D-pad ↑");
  assert.equal(wc.input.keyLabel("F7"), "F7");
  assert.equal(wc.input.PAD_BUTTONS.length, 16);
});

// ---------- small helpers ----------
test("getPath walks objects and lists by a save path", () => {
  assert.equal(wc.getPath({ a: { b: [10, 20] } }, "a/b/1"), 20);
  assert.deepEqual(wc.getPath({ a: { b: [10, 20] } }, "/a/b/"), [10, 20]);   // slashes at the ends don't count
  assert.equal(wc.getPath({ a: null }, "a/b"), undefined);
  assert.equal(wc.getPath({}, "x"), undefined);
});

test("el() sets text, classes, style, attributes and listeners; false and null are left out", () => {
  const clicks = [];
  const n = wc.el("button", { class: "btn", text: "Go", disabled: false, "aria-label": null, title: true, style: { flex: "1" },
    onclick: () => clicks.push(1) }, "x", null, false, ["y", " z"]);
  assert.equal(n.tagName, "BUTTON");
  assert.equal(n.className, "btn");
  assert.equal(n.textContent, "Goxy z");
  assert.equal(n.getAttribute("disabled"), null);
  assert.equal(n.getAttribute("aria-label"), null);
  assert.equal(n.getAttribute("title"), "");
  assert.equal(n.style.flex, "1");
  n.dispatch("click");
  assert.equal(clicks.length, 1);
  assert.equal(wc.clear(n).textContent, "");
  assert.equal(wc.docLink("docs/formats.md").getAttribute("href"), wc.DOCS + "docs/formats.md");
  assert.equal(wc.docLink("README.md#x", "Read").textContent, "Read");
});

test("announce fills the polite or the assertive region a moment later, joining what's said at once", async () => {
  wc.announce("one");
  wc.announce("two");
  wc.announce("careful", "bad");
  assert.equal(dom.byId.say.textContent, "");
  await tick(80);
  assert.equal(dom.byId.say.textContent, "one two");
  assert.equal(dom.byId.shout.textContent, "careful");
});

test("toast shows a message; a problem gets a close button and is heard on the assertive region", async () => {
  dom.byId.toasts.textContent = "";
  wc.toast("Saved palette.json in my-mods.");
  wc.toast("palette.json in my-mods isn't valid JSON", "bad");
  const [plain, bad] = dom.byId.toasts.children;
  assert.ok(!plain.classList.contains("bad") && !plain.querySelector("button"));
  assert.ok(bad.classList.contains("bad"));
  const close = bad.querySelector("button");
  assert.equal(close.getAttribute("aria-label"), "Close this message");
  assert.equal(close.getAttribute("tabindex"), "-1");
  await tick(80);
  assert.equal(dom.byId.shout.textContent, "palette.json in my-mods isn't valid JSON");
  close.dispatch("click");
  assert.ok(!dom.byId.toasts.children.includes(bad), "closed");
  assert.ok(dom.byId.toasts.children.includes(plain), "the other stays");
});

test("confirmButton: the first press arms, the second runs; blur disarms", async () => {
  let ran = 0;
  const b = wc.confirmButton("Remove", "Press again", async () => { ran++; }, "btn danger");
  assert.equal(b.className, "btn danger");
  b.dispatch("click");
  assert.equal(b.textContent, "Press again");
  assert.ok(b.classList.contains("armed"));
  assert.equal(ran, 0);
  b.dispatch("blur");
  assert.equal(b.textContent, "Remove");
  b.dispatch("click");
  b.dispatch("click");
  await tick();
  assert.equal(ran, 1);
  assert.equal(b.textContent, "Remove");
});

test("bus: listeners hear what's emitted until they're taken off, and one throwing doesn't stop the others", () => {
  const heard = [];
  const off = wc.bus.on("thing", d => heard.push(d));
  wc.bus.on("thing", () => { throw new Error("oops"); });
  wc.bus.on("thing", d => heard.push(d + "!"));
  const quiet = console.error;
  console.error = () => {};
  try { wc.bus.emit("thing", "a"); } finally { console.error = quiet; }
  off();
  console.error = () => {};
  try { wc.bus.emit("thing", "b"); } finally { console.error = quiet; }
  assert.deepEqual(heard, ["a", "a!", "b!"]);
});

// ---------- the API ----------
test("api sends the token and turns an error answer into a thrown message", async () => {
  dom.routes = {
    "GET /mods": () => [{ id: "a" }],
    "POST /mods": b => ({ made: b.id }),
    "GET /broken": () => { throw { status: 400, error: "the request needs \"id\"" }; },
  };
  assert.deepEqual(await wc.api.get("/mods"), [{ id: "a" }]);
  assert.equal(dom.calls.at(-1).headers["X-WC-Token"], "test-token");
  assert.equal(dom.calls.at(-1).headers["Content-Type"], undefined);
  assert.deepEqual(await wc.api.post("/mods", { id: "x" }), { made: "x" });
  assert.equal(dom.calls.at(-1).headers["Content-Type"], "application/json");
  await assert.rejects(wc.api.get("/broken"), { message: 'the request needs "id"' });
  await assert.rejects(wc.api.get("/nope"), { message: "unknown API route GET /nope" });
});

// ---------- which mod a page edits ----------
function mods(list) {
  return list.map(([id, name, kinds, enabled]) => ({ id, name, kinds, enabled, requires: [], author: "", version: "", description: "" }));
}

test("modTarget labels each mod by whether it has the page's file and whether it's on, My mods first when new", async () => {
  localStorage.clear();
  dom.routes = {
    "GET /mods": () => mods([["zeta", "Zeta", [], true], ["alpha", "Alpha", ["palette"], true], ["beta", "Beta", [], false]]),
    "GET /mods/my-mods/file/palette.json": () => ({ exists: false, text: null }),
  };
  const loaded = [];
  const t = wc.modTarget({ file: "palette.json", onLoad: (obj, id) => loaded.push([obj, id]), getValue: () => ({}) });
  await t.refresh();
  const select = t.element.querySelector("select");
  assert.deepEqual(select.options.map(o => [o.value, o.textContent]), [
    ["my-mods", "My mods (new)"], ["alpha", "Alpha"], ["beta", "Beta (no palette.json yet) · off"], ["zeta", "Zeta (no palette.json yet)"]]);
  assert.equal(select.value, "my-mods");
  assert.deepEqual(loaded, [[null, "my-mods"]]);   // a mod that isn't there yet: nothing fetched
  assert.ok(!dom.calls.some(c => c.url.includes("/mods/my-mods/file")));
  assert.equal(localStorage.getItem("wc-target"), "my-mods");
  const npcs = wc.modTarget({ file: "npcs.json", onLoad() {}, getValue() {}, share: false });
  dom.routes["GET /mods"] = () => mods([["story", "Story", ["characters", "questlines"], true]]);
  dom.routes["GET /mods/story/file/npcs.json"] = () => ({ exists: true, text: "{\"npcs\": []}" });
  await npcs.refresh("story");
  assert.equal(npcs.element.querySelector("select").options.find(o => o.value === "story").textContent, "Story");
  assert.equal(npcs.element.querySelector("details"), null, "share: false leaves the Share card out");
});

test("modTarget starts on the mod last chosen on any page, and says when its file isn't JSON", async () => {
  localStorage.clear();
  localStorage.setItem("wc-target:controls.json", "beta");   // the old, per-file key counts once
  dom.routes = {
    "GET /mods": () => mods([["alpha", "Alpha", ["controls"], true], ["beta", "Beta", ["controls"], true]]),
    "GET /mods/beta/file/controls.json": () => ({ exists: true, text: "{broken" }),
    "GET /mods/alpha/file/controls.json": () => ({ exists: true, text: "{\"a\": 1}" }),
  };
  dom.byId.toasts.textContent = "";
  const loaded = [];
  const t = wc.modTarget({ file: "controls.json", onLoad: (obj, id) => loaded.push([obj, id]), getValue: () => ({}) });
  await t.refresh();
  assert.deepEqual(loaded, [[null, "beta"]]);
  assert.equal(localStorage.getItem("wc-target:controls.json"), null);
  assert.equal(localStorage.getItem("wc-target"), "beta");
  assert.match(dom.byId.toasts.textContent, /controls.json in beta isn't valid JSON/);
  const select = t.element.querySelector("select");
  select.value = "alpha";
  select.dispatch("change");
  await tick();
  assert.deepEqual(loaded.at(-1), [{ a: 1 }, "alpha"]);
  assert.equal(t.current, "alpha");
});

test("modTarget's Save to mod makes a missing mod first, writes the file, and only then turns an off mod on", async () => {
  localStorage.clear();
  const calls = [];
  const list = mods([["my-mods", "My mods", [], false]]);
  dom.routes = {
    "GET /mods": () => list,
    "GET /mods/my-mods/file/palette.json": () => ({ exists: true, text: JSON.stringify({ fur: { 3: "#FF0000" } }) }),
    "PUT /mods/my-mods/file/palette.json": b => { calls.push(["put", b.text]); return { saved: "palette.json", requires: [], problem: null }; },
    "PATCH /mods/my-mods": b => { calls.push(["patch", b]); list[0].enabled = true; return list[0]; },
  };
  const loaded = [];
  const t = wc.modTarget({ file: "palette.json", share: false, onLoad: (obj, id) => loaded.push([obj, id]), getValue: () => ({ fur: { 3: "#00FF00" } }) });
  await t.refresh();
  assert.deepEqual(loaded.at(-1), [{ fur: { 3: "#FF0000" } }, "my-mods"]);
  t.markDirty();
  assert.equal(t.element.querySelector(".dirty").textContent, "Unsaved changes");
  assert.equal(await t.save(), true);
  assert.deepEqual(calls.map(c => c[0]), ["put", "patch"]);
  assert.deepEqual(calls[1][1], { enabled: true });
  assert.equal(t.element.querySelector(".dirty").textContent, "");
  // The page said the value is wrong: nothing is written.
  const silent = wc.modTarget({ file: "palette.json", share: false, onLoad() {}, getValue: () => undefined });
  await silent.refresh();
  calls.length = 0;
  assert.equal(await silent.save(), false);
  assert.deepEqual(calls, []);
});

test("modTarget's New mod makes the mod and moves to it", async () => {
  localStorage.clear();
  const list = mods([["alpha", "Alpha", ["palette"], true]]);
  dom.routes = {
    "GET /mods": () => list,
    "GET /mods/alpha/file/palette.json": () => ({ exists: false, text: null }),
    "GET /mods/fresh/file/palette.json": () => ({ exists: false, text: null }),
    "POST /mods": b => { list.push(...mods([[b.id, b.id, [], b.enabled]])); return list.at(-1); },
  };
  const loaded = [];
  const t = wc.modTarget({ file: "palette.json", share: false, onLoad: (obj, id) => loaded.push(id), getValue: () => ({}) });
  await t.refresh();
  const newBtn = t.element.querySelectorAll("button").find(b => b.textContent === "New mod…");
  const box = t.element.querySelector("input");
  assert.ok(box.closest("span").hidden, "the name box waits behind the button");
  newBtn.dispatch("click");
  assert.ok(!box.closest("span").hidden);
  box.value = " fresh ";
  box.closest("span").querySelectorAll("button").find(b => b.textContent === "Create").dispatch("click");
  await tick(10);
  assert.deepEqual(dom.calls.filter(c => c.method === "POST").at(-1).body, { id: "fresh", enabled: true });
  assert.equal(t.current, "fresh");
  assert.equal(loaded.at(-1), "fresh");
  assert.ok(box.closest("span").hidden);
});
