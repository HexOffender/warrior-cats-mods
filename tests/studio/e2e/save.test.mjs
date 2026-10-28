// The Save page in a real browser, over the made-up game and a save of its own in a temp folder (never the
// player's): a preset goes in the list in words, Change my save now writes it and lists it under Done so far,
// Put it back puts the old value back (asking first when the save moved on), and the whole save under Advanced
// keeps decimals, keeps its groups open and shows key bindings without changing them.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launch } from "../lib/browser.mjs";
import { REPO } from "../lib/dom.mjs";

import { browserChoice, dataFolder, fixtureGame, readSave, removeFolder, requireBrowser, startStudio, takeTurn } from "../lib/studio.mjs";

const { browserPath, skip } = browserChoice();
const P = "1/GameplayProgression";

let browser, studio, folders, release;

before(async () => {
  if (skip) return;
  requireBrowser(browserPath);
  release = await takeTurn();   // one end-to-end file at a time
  folders = dataFolder();
  fixtureGame(folders);
  studio = await startStudio(folders);
  browser = await launch({ browser: browserPath });
  // A first load, with time to spare: a cold browser and studio are slow, and every test's own waits are 10 s.
  const page = await browser.page();
  await page.goto(studio.url, { timeout: 60000 });
  await page.waitFor("#nav button", 60000);
  await page.close();
});

after(async () => {
  if (studio) studio.stop();
  if (browser) await browser.close();
  if (folders) await removeFolder(folders.root);
  if (release) release();
});

async function open() {
  const page = await browser.page();
  await page.goto(studio.url + "#save");
  await page.waitFor('.section[data-page="save"][data-ready]', 20000);
  return page;
}
const pending = page => page.evaluate(() => [...document.querySelectorAll("#save-pending .changes li span:first-child")].map(s => s.textContent));
const done = page => page.evaluate(() => [...document.querySelectorAll("#save-done .changes > li")].map(li => li.querySelector(".row > span").textContent));
// The game moving the save on: one value changed in the file, as play would.
function play(path, value) {
  const code = "import sys, json; sys.path.insert(0, sys.argv[1]); from wcmods.formats.save import SaveGame, write_save; " +
    "from wcmods.formats.savejson import SaveDoc; s = SaveGame.load(sys.argv[2] + '/WrcGame.sav'); d = SaveDoc(s.json_text); " +
    "d.set(sys.argv[3], json.loads(sys.argv[4])); s.json_text = d.text; write_save(sys.argv[2], s)";
  const r = spawnSync(process.env.PYTHON || "python", ["-I", "-c", code, REPO, folders.saves, path, JSON.stringify(value)], { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
}

test("a preset adds to the list in words, and nothing is written until Change my save now", { skip }, async () => {
  const page = await open();
  assert.equal(await page.text("#save-cat h2"), "Your cat");
  await page.click({ text: "Fill the fresh-kill pile" });
  await page.waitFor(() => document.querySelectorAll("#save-pending .changes li").length === 1);
  assert.deepEqual(await pending(page), ["your cat's fresh-kill pile: 62 -> 100"]);
  assert.equal(readSave(folders.saves).acct["1"].GameplayProgression.FreshKill.Value, 62, "the save is as it was");
  await page.click({ text: "Give herbs" });
  await page.waitFor(() => document.querySelectorAll("#save-pending .changes li").length === 5);
  const words = await pending(page);
  assert.ok(words.includes("your cat's Small Healing Herb: 2 -> 7"), words.join(" | "));
  assert.ok(words.includes("your cat's Small Catnip: none -> 5"), words.join(" | "));
  // One taken off the list again.
  await page.click('[aria-label="Remove your cat\'s Small Catnip from the list"]');
  await page.waitFor(() => document.querySelectorAll("#save-pending .changes li").length === 4);
  // The list is kept while the tab is open (a reload finds it again), and closing the tab asks first.
  const kept = await page.evaluate(() => JSON.parse(sessionStorage.getItem("wc-save-changes:acct")));
  // An item the cat has already is a new count for it; the others are added.
  assert.deepEqual(kept.set, { [`${P}/FreshKill/Value`]: 100, [`${P}/State/Inventory/Gameplay.Inventory.Consumable.SmallHealingHerb`]: 7 });
  assert.deepEqual(Object.keys(kept.add[`${P}/State/Inventory`]), ["Gameplay.Inventory.Consumable.MediumHealingHerb", "Gameplay.Inventory.Consumable.BigHealingHerb"]);
  assert.equal(await page.evaluate(() => { const e = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(e); return e.defaultPrevented; }), true);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("Change my save now writes the list and shows each change under Done so far", { skip }, async () => {
  const page = await open();
  await page.click({ text: "Fill the fresh-kill pile" });
  await page.click({ text: "Give herbs" });
  await page.waitFor(() => document.querySelectorAll("#save-pending .changes li").length === 5);
  await page.click('[aria-label="Remove your cat\'s Small Catnip from the list"]');
  await page.waitFor(() => document.querySelectorAll("#save-pending .changes li").length === 4);
  await page.click("#save-now");
  await page.waitFor(() => document.querySelectorAll("#save-done .changes > li").length === 4, 15000);
  const save = readSave(folders.saves).acct["1"].GameplayProgression;
  assert.equal(save.FreshKill.Value, 100);
  assert.equal(save.State.Inventory["Gameplay.Inventory.Consumable.SmallHealingHerb"], 7);
  assert.equal(await page.evaluate(() => document.querySelectorAll("#save-pending .changes li").length), 0, "the list is empty again");
  assert.ok((await done(page)).includes("your cat's fresh-kill pile: 62 -> 100"));
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => /^Done at \d\d:\d\d/.test(t.textContent)));
  // The pile is full now: the preset says so, and adds nothing.
  await page.click({ text: "Fill the fresh-kill pile" });
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent === "The fresh-kill pile is already full."));
  assert.equal(await page.evaluate(() => document.querySelectorAll("#save-pending .changes li").length), 0);
  await page.close();
});

test("Put it back puts the old value back", { skip }, async () => {
  const page = await open();
  await page.click('[aria-label="Put back your cat\'s fresh-kill pile"]');
  await page.waitFor(() => [...document.querySelectorAll("#save-done .muted")].some(s => s.textContent.includes("put back")), 15000);
  assert.equal(readSave(folders.saves).acct["1"].GameplayProgression.FreshKill.Value, 62);
  await page.close();
});

test("Put it back asks first when the save moved on since", { skip }, async () => {
  const page = await open();
  await page.evaluate(() => { const n = document.querySelector('#save-cat input[type="number"]'); n.value = "10"; n.dispatchEvent(new Event("change")); });
  await page.waitFor(() => document.querySelectorAll("#save-pending .changes li").length === 1);
  assert.deepEqual(await pending(page), ["your cat's level: 5 -> 10"]);
  await page.click("#save-now");
  await page.waitFor(() => (document.querySelector("#save-done .changes > li .row > span") || {}).textContent === "your cat's level: 5 -> 10", 15000);
  play(`${P}/Level`, 14);   // played on to 14
  await page.reload();
  await page.waitFor('.section[data-page="save"][data-ready]', 20000);
  await page.click('[aria-label="Put back your cat\'s level"]');
  await page.waitFor(() => [...document.querySelectorAll("#save-done li > .row:not([hidden]) span")].some(s => s.textContent === "your cat's level is 14 now; putting it back makes it 5."));
  assert.equal(readSave(folders.saves).acct["1"].GameplayProgression.Level, 14, "nothing changes until it's said");
  await page.click({ text: "Put it back anyway" });
  await page.waitFor(() => [...document.querySelectorAll("#save-done .changes > li")].some(li => li.textContent.startsWith("your cat's level: 5 -> 10") && li.textContent.includes("put back")), 15000);
  assert.equal(readSave(folders.saves).acct["1"].GameplayProgression.Level, 5);
  await page.close();
});

test("Tab from Level moves to Experience, and a level out of range is refused", { skip }, async () => {
  const page = await open();
  await page.type('#save-cat input[type="number"]', "");
  await page.evaluate(() => { const n = document.querySelector('#save-cat input[type="number"]'); n.select(); });
  await page.press("Backspace");
  await page.type('#save-cat input[type="number"]', "25");
  await page.press("Tab");
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.includes("Level goes from 1 to 20, not 25")));
  const label = await page.evaluate(() => document.querySelector(`label[for="${document.activeElement.id}"]`)?.textContent);
  assert.equal(label, "Experience", "focus moved on to the next box");
  assert.equal(await page.evaluate(() => document.querySelector('#save-cat input[type="number"]').value), "5", "back to the value the save has");
  assert.equal(await page.evaluate(() => document.querySelectorAll("#save-pending .changes li").length), 0);
  await page.close();
});

test("Tab from a count in What it carries moves on to its Remove, and the count goes in the list", { skip }, async () => {
  const page = await open();
  const moss = '[id="save-carry-Gameplay.Inventory.Materials.Moss"]';
  await page.waitFor(moss);
  // Give herbs names what it gives (by the game's names when its item table can be read; here, the tags in words).
  assert.match(await page.evaluate(() => [...document.querySelectorAll("#save-cat .presets button")].find(b => b.textContent === "Give herbs").title),
    /^Five more of each of Small Healing Herb, Medium Healing Herb, Big Healing Herb and Small Catnip\.$/);
  await page.evaluate(`(n => { n.focus(); n.select(); })(document.querySelector(${JSON.stringify(moss)}))`);
  await page.press("Backspace");
  await page.type(moss, "9");
  await page.press("Tab");
  await page.waitFor(() => document.querySelectorAll("#save-pending .changes li").length === 1);
  assert.deepEqual(await pending(page), ["your cat's Moss: 4 -> 9"]);
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-label")), "Remove Moss", "focus went on, not back or to the top");
  assert.match(await page.text('[data-key="carry:Gameplay.Inventory.Materials.Moss"]'), /in your save now: 4/);
  // Taking it out: the row is "taken out", with focus on its Keep it.
  await page.press("Enter");
  await page.waitFor(() => document.querySelector('[data-key="carry:Gameplay.Inventory.Materials.Moss"].gone'));
  await page.waitFor(() => document.activeElement?.textContent === "Keep it");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("the tree keeps a typed decimal, keeps its groups open, and shows key bindings without changing them", { skip }, async () => {
  const page = await open();
  await page.click("#save-advanced > summary");
  await page.type("#save-find", "MasterVolume");
  await page.waitFor(() => document.querySelector('#save-found input[type="number"]'));
  await page.evaluate(() => { const n = document.querySelector('#save-found input[type="number"]'); n.value = "0.5"; n.dispatchEvent(new Event("change")); });
  await page.waitFor(() => document.querySelectorAll("#save-pending .changes li").length === 1);
  assert.deepEqual(await pending(page), ["the game's setting master volume: 1 -> 0.5"]);
  // Groups opened by hand stay open through a change, and focus stays in the page.
  for (const at of ["1", "1/GameplayProgression"]) {
    await page.waitFor(`#save-advanced details[data-path="${at}"] > summary`);
    await page.click(`#save-advanced details[data-path="${at}"] > summary`);
    await page.waitFor(`#save-advanced details[data-path="${at}"][open]`);
  }
  // A group's rows are made as it opens.
  const box = await page.waitFor(() => { const l = [...document.querySelectorAll("#save-advanced .tree-kids label")].find(x => x.title === "1/GameplayProgression/Experience"); return l && l.htmlFor; });
  await page.type(`#${box}`, "");
  await page.evaluate(`(() => { const n = document.getElementById(${JSON.stringify(box)}); n.value = "130.5"; n.dispatchEvent(new Event("change")); })()`);
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.includes("Experience has to be a whole number")));
  assert.equal(await page.evaluate(() => !!document.querySelector('#save-advanced details[data-path="1/GameplayProgression"][open]')), true);
  assert.notEqual(await page.evaluate(() => document.activeElement === document.body), true, "focus is still in the page");
  // A key binding: shown, with where it's changed.
  await page.evaluate(() => { const f = document.getElementById("save-find"); f.value = ""; f.dispatchEvent(new Event("input")); });
  await page.type("#save-find", "Player_Jump");
  await page.waitFor(() => document.querySelector("#save-found .leaf"));
  assert.equal(await page.count("#save-found .leaf input"), 0, "no box to type in");
  assert.match(await page.text("#save-found .leaf"), /The Controls page changes them/);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("Keep it as a mod to share makes a mod that's off, and says so when it's on", { skip }, async () => {
  const page = await open();
  await page.click({ text: "Fill the fresh-kill pile" });
  await page.waitFor(() => document.querySelectorAll("#save-pending .changes li").length === 1);
  await page.click("#save-share > summary");
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent === "Saved in My mods. It's off, so your own save isn't changed by it. Share it from the Mods page."));
  const meta = JSON.parse(fs.readFileSync(path.join(folders.data, "mods", "my-mods", "mod.json"), "utf8"));
  assert.equal(meta.enabled, false);
  assert.ok(fs.existsSync(path.join(folders.data, "mods", "my-mods", "save.json")));
  assert.equal(readSave(folders.saves).acct["1"].GameplayProgression.FreshKill.Value, 62, "your own save is as it was");
  assert.equal(await page.count("#save-share-on"), 0);
  // Turned on (on the Mods page): the fold says the next Apply makes its changes in your own save too.
  await page.evaluate(async () => (await import("/studio/lib/wc.js")).api.patch("/mods/my-mods", { enabled: true }));
  await page.click(`[aria-label="Remove your cat's fresh-kill pile from the list"]`);   // nothing left to ask about on leaving
  await page.waitFor(() => document.querySelectorAll("#save-pending > .changes li").length === 0);   // the fold's own list stays
  await page.reload();
  await page.waitFor('.section[data-page="save"][data-ready]', 20000);
  await page.waitFor("#save-share-on");
  assert.match(await page.text("#save-share-on"), /^My mods is on: the next Apply makes its changes in your own save too, once\./);
  await page.evaluate(async () => (await import("/studio/lib/wc.js")).api.patch("/mods/my-mods", { enabled: false }));
  await page.close();
});

test("without a save the page says to start the game once", { skip }, async () => {
  const empty = dataFolder();
  const other = await startStudio(empty);
  try {
    const page = await browser.page();
    await page.goto(other.url + "#save");
    await page.waitFor('.section[data-page="save"][data-ready]', 20000);
    assert.equal(await page.text('.section[data-page="save"] .error-card h2'), "No save yet: start the game once and come back");
    assert.deepEqual(page.consoleErrors().filter(e => !/404/.test(e)), []);
    await page.close();
  } finally {
    other.stop();
    await removeFolder(empty.root);
  }
  assert.ok(path.isAbsolute(folders.saves));
});
