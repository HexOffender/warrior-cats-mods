// The Mods page's words and choices (studio/lib/modlist.js) and the helpers it shares through wc.js (the code
// warning, the add-on button), under node:test with the DOM shim in lib/dom.mjs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "./lib/dom.mjs";

const dom = install();
const wc = await import(dom.studio("lib/wc.js"));
const list = await import(dom.studio("lib/modlist.js"));

const ADDONS = [
  { id: "menu-pages", name: "Menu pages", about: "Your cat, the world, quests, fights and cheats in the in-game menu" },
  { id: "sandbox", name: "Sandbox mode", about: "Shows the cats and questlines you make" },
];

test("Find a mod ignores capitals and the spaces at either end, and keeps spaces between words", () => {
  const forest = { id: "palette-dark-forest", name: "Dark Forest", description: "Shadowy coats", author: "Ash" };
  for (const typed of ["Dark Forest", "dark forest", "  Dark Forest ", "shadowy", "ASH", "palette-dark", ""]) {
    assert.ok(list.matches(forest, typed), typed);
  }
  assert.ok(!list.matches(forest, "darkforest"), "the space between words counts");
  assert.ok(!list.matches({ id: "x", name: 7 }, "seven"));   // a name that isn't text doesn't break it
});

test("a requirement is named from the .zip first, then your mods, then the mods that go with Clan Mod Studio", () => {
  const pack = { id: "moonlit", name: "The Moonlit Path", requires: ["moonlit-cats", "mine", "sandbox", "ghost"] };
  const inZip = [pack, { id: "moonlit-cats", name: "Moonlit cats" }];
  const have = [{ id: "mine", name: "My mods" }];
  assert.deepEqual(list.needs(pack, inZip, have, ADDONS), [
    { id: "moonlit-cats", name: "Moonlit cats", where: "zip", addon: false },
    { id: "mine", name: "My mods", where: "have", addon: false },
    { id: "sandbox", name: "Sandbox mode", where: "missing", addon: true },
    { id: "ghost", name: "ghost", where: "missing", addon: false },
  ]);
});

test("a pack's requirements inside its .zip are no warning; a missing one is, and says it goes in off", () => {
  const pack = { id: "p", requires: ["a", "b"] };
  const inZip = [pack, { id: "a", name: "A" }, { id: "b", name: "B" }];
  assert.deepEqual(list.needsLine(list.needs(pack, inZip, [], ADDONS)), ["Needs A (in this .zip), B (in this .zip), turned on with it.", ""]);
  const story = { id: "s", requires: ["sandbox"] };
  const [text, kind] = list.needsLine(list.needs(story, [story], [], ADDONS));
  assert.equal(kind, "warn");
  assert.equal(text, "Needs Sandbox mode. You don't have Sandbox mode, so it goes in switched off until you add it.");
  assert.equal(list.needsLine([]), null);
  assert.deepEqual(list.worksWith({ uses: ["sandbox", "mod-menu", "mine"] }, [], [{ id: "mine" }], ADDONS).map(a => a.id), ["sandbox"]);
});

test("each add-on's row gets one chip and at most one button", () => {
  const state = a => { const s = list.addonState(a); return [s.chip, s.kind, s.action]; };
  assert.deepEqual(state({ installed: false }), ["Not added", "", "add"]);
  assert.deepEqual(state({ installed: false, no_release: true }), ["No release yet", "warn", null]);
  assert.deepEqual(state({ installed: true, enabled: true, version: "0.4" }), ["In, 0.4", "good", null]);
  assert.deepEqual(state({ installed: true, enabled: true, version: "0.4", newer: true, latest: "0.5" }), ["Newer one out: 0.5", "warn", "latest"]);
  assert.deepEqual(state({ installed: true, enabled: false, version: "0.4", newer: true, latest: "0.5" }), ["Off", "warn", "on"]);
  assert.deepEqual(state({ installed: true, enabled: true, needs_code: true }), ["Needs scripts allowed", "warn", null]);
  assert.deepEqual(state({ installed: true, enabled: true, too_new: "needs Clan Mod Studio 0.5.0 or newer" }), ["Needs a newer Clan Mod Studio", "bad", null]);
  assert.ok(list.allSet([{ installed: true, enabled: true }, { installed: true, enabled: true, version: "1" }]));
  assert.ok(!list.allSet([{ installed: true, enabled: true }, { installed: false }]) && !list.allSet([]));
});

test("the toast after adding says what went in, what went on with it, and what's off and why", () => {
  assert.equal(list.addedToast([{ id: "a", name: "A", on: true, also_on: ["Helper"] }]),
    "Added A. Also on, because it needs them: Helper. Press Play to play with it.");
  assert.equal(list.addedToast([{ id: "m", name: "Moonlit cats", on: false, off_because: "needs Sandbox mode, which you don't have", missing: ["sandbox"] }], ADDONS),
    "Added Moonlit cats, switched off: it needs Sandbox mode. Add it from the add-ons card, then switch it on.");
  assert.equal(list.addedToast([{ id: "m", name: "M", on: false, off_because: "x", missing: ["ghost"] }], ADDONS),
    "Added M, switched off: it needs ghost. Add it, then switch it on.");
  assert.equal(list.addedToast([{ id: "a", name: "A", on: false }]), "Added A.");
});

test("an add-on's toast: the latest already, still off, or its scripts to allow", () => {
  assert.equal(list.addonToast({ name: "Menu pages", version: "1.0", unchanged: true }), "Menu pages 1.0 is the latest already.");
  const r = { id: "menu-pages", name: "Menu pages", version: "1.1", replaced: "x", on: false, added: [{ id: "menu-pages", code: true, on: false }] };
  assert.equal(list.addonToast(r, true), "Menu pages 1.1 is in your mods, with your settings kept. It's still off: switch it on, then Apply.");
  assert.match(list.addonToast({ ...r, on: true, replaced: null }, false), /^Menu pages 1\.1 is in your mods\. It runs its own scripts, so allow that/);
  const palettes = { id: "creator-palettes", name: "Creator palettes", version: "1.2.0", on: true,
    added: [{ id: "creator-palettes", on: true }, { id: "palette-coat-presets", on: true }, { id: "palette-dark-forest", on: false }] };
  assert.equal(list.addonToast(palettes, true), "Creator palettes 1.2.0 is in your mods. It came with 2 more: 1 on, the rest off. Press Play to put it in the game.");
});

test("the changes banner names mods, and says why one is left out", () => {
  const c = { on: ["a"], off: ["b"], changed: [], left_out: { old: "made for an older version of the game" }, redo: ["the mod menu's settings changed"],
    names: { a: "A", b: "B", old: "Old tweaks" } };
  assert.deepEqual(list.changeParts(c), ["A on", "B off", "Old tweaks left out: made for an older version of the game",
    "apply again: the mod menu's settings changed"]);
  assert.equal(list.sentence("needs Sandbox mode, which is off"), "Needs Sandbox mode, which is off.");
  assert.equal(list.sentence("Fine."), "Fine.");
});

test("the code warning names your mods that run code, with their authors, and nothing else", () => {
  const box = wc.codeWarning([
    { id: "menu-pages", name: "Menu pages", author: "wcmods", code: true, about: "the mod menu's pages" },
    { id: "colours", name: "Colours", code: false },
    { id: "odd", name: "Odd script", code: true, kinds: ["in-game script"] },
  ]);
  assert.match(box.textContent, /^Only for mods from people you trust/);
  assert.ok(box.textContent.includes(wc.CODE_WARNING));
  assert.deepEqual(box.querySelectorAll("li").map(li => li.textContent), ["Menu pages, by wcmods: the mod menu's pages", "Odd script: an in-game script"]);
  assert.equal(wc.codeWarning([]).querySelectorAll("li").length, 0);
});

test("an add-on button adds it, says so, and tells the other pages", async () => {
  dom.calls.length = 0;
  dom.routes = {
    "POST /addons/sandbox": () => ({ log: [], result: { id: "sandbox", name: "Sandbox mode", version: "0.4", on: true, unchanged: false, replaced: null,
      added: [{ id: "sandbox", code: true, on: true }] } }),
    "GET /settings": () => ({ allow_code_mods: true }),
  };
  const heard = [];
  const off = wc.bus.on("mods-changed", d => heard.push(d));
  const b = wc.addonButton("sandbox", { label: "Add Sandbox mode", name: "Sandbox mode" });
  b.click();
  assert.equal(b.textContent, "Adding Sandbox mode…");
  assert.equal(b.disabled, true);
  for (let i = 0; i < 20 && b.disabled; i++) await tick(5);
  assert.equal(b.textContent, "Add Sandbox mode");
  assert.deepEqual(heard, [{ from: "addon" }]);
  assert.ok(dom.calls.some(c => c.method === "POST" && c.url === "/api/addons/sandbox"));
  assert.match(dom.byId.toasts.textContent, /Sandbox mode 0\.4 is in your mods\. Press Play/);
  off();
});
