// The Game data page in a real browser, over the made-up game (tests/studio/fixtures/game.py: a few of the
// game's tables, cut down): Quick changes writes ordinary cell edits, the search finds numbers by what they do,
// and the grid commits once on Enter, cancels on Escape, keeps its filter, refuses text in a number column, lets
// a row out of a multiplier, and doesn't let a slow table take over a fast one. And with the game's files
// unreadable, the page says so.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { findBrowser, launch } from "../lib/browser.mjs";
import { dataFolder, fixtureGame, makeGame, removeFolder, startStudio } from "../lib/studio.mjs";

const browserPath = findBrowser();
const required = process.env.WC_REQUIRE_BROWSER === "1";
const skip = browserPath || required ? false : "no Chromium found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)";

let browser, studio, folders;

before(async () => {
  if (skip) return;
  if (!browserPath) throw new Error("WC_REQUIRE_BROWSER=1, and no Chromium was found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)");
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
});

async function open() {
  const page = await browser.page();
  await page.goto(studio.url + "#data");
  await page.waitFor('.section[data-page="data"][data-ready]', 20000);
  return page;
}
// The file the page would save, as the page shows it under For mod makers.
const file = page => page.evaluate(() => { const o = JSON.parse(document.querySelector('.section[data-page="data"] .code pre').textContent); delete o._help; return o; });
const dirty = page => page.text(".target .dirty");
// Open All tables and a table in it by its title, and wait for its rows.
async function table(page, title) {
  await page.evaluate(`window.wanted = ${JSON.stringify(title)}; document.getElementById("data-all").open = true;
    [...document.querySelectorAll(".table-pick")].find(b => b.firstChild.textContent === wanted).click()`);
  await page.waitFor(() => { const h = document.querySelector(".data-table h2"); return h && h.firstChild.textContent === window.wanted && document.querySelector(".data-table tbody tr"); });
}
const cell = (row, col) => `.data-table [data-focus="cell:${row}:${col}"]`;
const cellText = (page, row, col) => page.evaluate(`document.querySelector(${JSON.stringify(cell(row, col))}).textContent`);

test("dragging Running speed shows the edit in All tables and in data.json, and Normal puts it back clean", { skip }, async () => {
  const page = await open();
  assert.equal(await page.text('[data-key="quick:run-speed"] .quick-now'), "Normal: 390");
  await page.evaluate(() => { const s = document.querySelector('[data-key="quick:run-speed"] input[type="range"]'); s.value = "600"; s.dispatchEvent(new Event("input")); s.dispatchEvent(new Event("change")); });
  await page.waitFor(() => document.querySelector('[data-key="quick:run-speed"] .quick-now').textContent === "390 -> 600");
  assert.deepEqual(await file(page), { "TuningData.csv": { "Gameplay.Exploration.Player.MoveAndRun.Run.Speed": { MaxValue: 600 } } });
  assert.equal(await dirty(page), "Unsaved changes");
  await table(page, "Tuning");
  await page.type("#data-row-filter", "Run.Speed");
  await page.waitFor(() => document.querySelectorAll(".data-table tbody tr").length === 1);
  assert.match(await cellText(page, "Gameplay.Exploration.Player.MoveAndRun.Run.Speed", 1), /^600390$/);   // the value, and the game's under it
  assert.equal(await page.count(".data-table td.edited"), 1);
  // A factor row: every animal's XP, with the first ones in words.
  await page.evaluate(() => { const n = document.getElementById("quick-xp-fights"); n.value = "2"; n.dispatchEvent(new Event("change")); });
  await page.waitFor(() => document.querySelector('[data-key="quick:xp-fights"] .quick-preview').textContent.startsWith("Fish 10 -> 20, WeakMice 25 -> 50"));
  assert.deepEqual((await file(page))["CombatBaseExperience.csv"], { "*": { BaseExperience: "x2" } });
  // Normal takes each back; the page is back to its file, so there's nothing to save.
  await page.evaluate(() => { document.querySelector('[data-key="quick:xp-fights"]').closest("details").open = true; });   // Levelling, a closed fold
  await page.click('[aria-label="Put XP from fights back to normal"]');
  await page.click('[aria-label="Put Running speed back to normal"]');
  await page.waitFor(() => document.querySelector('[data-key="quick:run-speed"] .quick-now').textContent === "Normal: 390");
  assert.deepEqual(await file(page), {});
  assert.equal(await dirty(page), "");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a value out of a quick row's range, or a chance over 1, is refused in words", { skip }, async () => {
  const page = await open();
  await page.evaluate(() => { const n = document.getElementById("quick-run-speed"); n.value = "5000"; n.dispatchEvent(new Event("change")); });
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.includes("Running speed goes from 100 to 1200")));
  await page.evaluate(() => { const n = document.getElementById("quick-scars-leader"); n.value = "2"; n.dispatchEvent(new Event("change")); });
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.includes("a chance can't go over 1")));
  assert.deepEqual(await file(page), {});
  await page.close();
});

test("the search finds a number by a word people use, and opens it", { skip }, async () => {
  const page = await open();
  await page.type("#data-find", "mouse");
  await page.waitFor(() => [...document.querySelectorAll("#data-find-results .hit")].some(b => b.textContent.startsWith("A mouse is worth")));
  await page.click('#data-find-results .hit');
  await page.waitFor(() => document.activeElement && document.activeElement.id === "quick-prey-mouse");
  // A row of any table, by its name or description, opens the table on that row.
  await page.evaluate(() => { const f = document.getElementById("data-find"); f.value = ""; f.dispatchEvent(new Event("input")); });
  await page.type("#data-find", "target maximum speed running");
  await page.waitFor(() => [...document.querySelectorAll("#data-find-results .hit")].some(b => b.textContent.includes("Gameplay.Exploration.Player.MoveAndRun.Run.Speed")), 15000);
  await page.evaluate(() => [...document.querySelectorAll("#data-find-results .hit")].find(b => b.textContent.includes("MoveAndRun.Run.Speed")).click());
  await page.waitFor(() => document.getElementById("data-all").open && document.getElementById("data-row-filter")?.value === "Gameplay.Exploration.Player.MoveAndRun.Run.Speed");
  assert.equal(await page.count(".data-table tbody tr"), 1);
  await page.close();
});

test("Enter commits once and keeps the filter and the scroll; Escape leaves the cell as it was and the page clean", { skip }, async () => {
  const page = await open();
  await table(page, "XP from fights");
  await page.type("#data-row-filter", "Mice");
  await page.waitFor(() => document.querySelectorAll(".data-table tbody tr").length === 2);
  // Escape: nothing changes.
  await page.click(cell("Mice", 1));
  await page.waitFor(`${cell("Mice", 1)} input`);
  await page.type(`${cell("Mice", 1)} input`, "99");
  await page.press("Escape");
  await page.waitFor(() => !document.querySelector(".data-table td input"));
  assert.equal(await cellText(page, "Mice", 1), "25");
  assert.equal(await dirty(page), "", "Escape leaves the page clean");
  assert.deepEqual(await file(page), {});
  // Enter: one change, the filter kept, focus back on the cell.
  await page.click(cell("Mice", 1));
  await page.waitFor(`${cell("Mice", 1)} input`);
  await page.evaluate(`document.querySelector(${JSON.stringify(cell("Mice", 1) + " input")}).select()`);
  await page.type(`${cell("Mice", 1)} input`, "30");
  await page.press("Enter");
  await page.waitFor(() => !document.querySelector(".data-table td input"));
  assert.equal(await cellText(page, "Mice", 1), "3025");
  assert.deepEqual(await file(page), { "CombatBaseExperience.csv": { Mice: { BaseExperience: 30 } } });
  assert.equal(await page.evaluate(() => document.getElementById("data-row-filter").value), "Mice");
  assert.equal(await page.count(".data-table tbody tr"), 2);
  assert.equal(await page.evaluate(() => document.activeElement.dataset.focus), "cell:Mice:1");
  assert.equal(await page.evaluate(() => document.querySelector('.table-pick[aria-current="true"] .count').textContent), "1");
  // The arrow keys move between cells, and Enter opens the one there.
  await page.press("ArrowRight");
  assert.equal(await page.evaluate(() => document.activeElement.dataset.focus), "cell:Mice:2");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("typing text into a number column is refused", { skip }, async () => {
  const page = await open();
  await table(page, "XP from fights");
  await page.click(cell("Fish", 1));
  await page.waitFor(`${cell("Fish", 1)} input`);
  await page.evaluate(`document.querySelector(${JSON.stringify(cell("Fish", 1) + " input")}).select()`);
  await page.type(`${cell("Fish", 1)} input`, "1,5");
  await page.press("Enter");
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.includes("Use a number like 1.5")));
  assert.equal(await page.evaluate(`document.querySelector(${JSON.stringify(cell("Fish", 1) + " input")}).getAttribute("aria-invalid")`), "true", "the box stays, marked");
  await page.press("Escape");
  await page.waitFor(() => !document.querySelector(".data-table td input"));
  assert.equal(await cellText(page, "Fish", 1), "10");
  assert.deepEqual(await file(page), {});
  await page.close();
});

test("a row typed under a multiplier shows set and writes that number", { skip }, async () => {
  const page = await open();
  await table(page, "XP from fights");
  assert.equal(await page.text("#data-all .data-table button.btn.small:not(.ghost)"), "Every BaseExperience × 2");
  await page.click({ text: "Every BaseExperience × 2" });
  await page.waitFor(() => [...document.querySelectorAll(".data-table .chip")].some(c => c.textContent.startsWith("BaseExperience × 2 on every row")));
  assert.equal(await cellText(page, "Mice", 1), "5025 · ×2");
  await page.click(cell("Mice", 1));
  await page.waitFor(`${cell("Mice", 1)} input`);
  assert.equal(await page.evaluate(`document.querySelector(${JSON.stringify(cell("Mice", 1) + " input")}).value`), "50", "the editor opens with the value shown");
  await page.evaluate(`document.querySelector(${JSON.stringify(cell("Mice", 1) + " input")}).select()`);
  await page.type(`${cell("Mice", 1)} input`, "25");   // the game's own: kept out of the multiplier
  await page.press("Enter");
  await page.waitFor(() => !document.querySelector(".data-table td input"));
  assert.equal(await cellText(page, "Mice", 1), "2525");
  assert.deepEqual(await file(page), { "CombatBaseExperience.csv": { "*": { BaseExperience: "x2" }, Mice: { BaseExperience: 25 } } });
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => document.querySelector(".target .dirty").textContent === "");
  const saved = JSON.parse(fs.readFileSync(path.join(folders.data, "mods", "my-mods", "data.json"), "utf8"));
  assert.deepEqual(saved["CombatBaseExperience.csv"], { "*": { BaseExperience: "x2" }, Mice: { BaseExperience: 25 } });
  await page.close();
});

test("a slow table answering after a fast one doesn't take over", { skip }, async () => {
  const page = await open();
  await page.evaluate(() => {
    const real = window.fetch;
    window.fetch = (url, opts) => String(url).includes("AttackMove") ? new Promise(r => setTimeout(r, 1500)).then(() => real(url, opts)) : real(url, opts);
    document.getElementById("data-all").open = true;
  });
  await page.waitFor(".table-pick");
  await page.evaluate(() => [...document.querySelectorAll(".table-pick")].find(b => b.firstChild.textContent === "Fight moves").click());
  await page.evaluate(() => [...document.querySelectorAll(".table-pick")].find(b => b.firstChild.textContent === "Herbs").click());
  await page.waitFor(() => document.querySelector(".data-table h2")?.firstChild.textContent === "Herbs");
  await new Promise(r => setTimeout(r, 2000));   // the slow one has answered by now
  assert.equal(await page.evaluate(() => document.querySelector(".data-table h2").firstChild.textContent), "Herbs");
  // Herbs' cells still change: its TRUE/FALSE column is a checkbox, its Target column a choice of words.
  await page.click(`${cell("Gameplay.Inventory.Consumable.SmallCatnip", 3)} input`);
  await page.waitFor(() => document.querySelector(".data-table td.edited"));
  assert.deepEqual((await file(page))["Consumables.csv"], { "Gameplay.Inventory.Consumable.SmallCatnip": { bExploration: true } });
  assert.equal(await page.evaluate(() => document.querySelector('.table-pick[aria-current="true"]').firstChild.textContent), "Herbs");
  await page.close();
});

test("a file's own row removals and additions, and a table the game hasn't got, are shown and kept", { skip }, async () => {
  fs.mkdirSync(path.join(folders.data, "mods", "by-hand"), { recursive: true });
  fs.writeFileSync(path.join(folders.data, "mods", "by-hand", "mod.json"), JSON.stringify({ name: "By hand", enabled: true }));
  const hand = { "NPC/Scars.csv": { "-": ["12"], "+": [{ "": "13", Role: "Kit", Group: "All", EarChance: 0 }], "3": { EarChance: 0.2 } }, "Nope.csv": { A: 1 } };
  fs.writeFileSync(path.join(folders.data, "mods", "by-hand", "data.json"), JSON.stringify(hand));
  const page = await browser.page();
  await page.goto(studio.url + "#data");
  await page.waitFor('.section[data-page="data"][data-ready]', 20000);
  await page.evaluate(() => { const s = document.querySelector('.target select'); s.value = "by-hand"; s.dispatchEvent(new Event("change")); });
  await page.waitFor(() => document.querySelector(".data-list .also"));
  assert.match(await page.text(".data-list .also"), /This mod also changes a table the game doesn't have: Nope.csv/);
  await table(page, "Scars");
  assert.match(await page.text(".data-table .chip.warn"), /^1 row removed, 1 row added by hand$/);
  // Saved as they were: "-" and "+" are lists still.
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => document.querySelector(".problems:not([hidden])"));
  assert.match(await page.text(".problems"), /Saved; this part will be left out: the game has no table 'Nope.csv'/);
  const saved = JSON.parse(fs.readFileSync(path.join(folders.data, "mods", "by-hand", "data.json"), "utf8"));
  assert.deepEqual(saved["NPC/Scars.csv"]["-"], ["12"]);
  assert.deepEqual(saved["NPC/Scars.csv"]["+"], hand["NPC/Scars.csv"]["+"]);
  assert.deepEqual(saved["Nope.csv"], { A: 1 });
  await page.close();
});

test("Every MaxScale × 1.5 in Cat sizes goes in, with a word that names the row by its role", { skip }, async () => {
  const page = await open();
  await table(page, "Cat sizes");
  await page.evaluate(() => {
    const c = document.getElementById("data-mul-col"); c.value = "MaxScale"; c.dispatchEvent(new Event("change"));
    const b = document.getElementById("data-mul-by"); b.value = "1.5"; b.dispatchEvent(new Event("input"));
  });
  await page.click({ text: "Every MaxScale × 1.5" });
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.startsWith("Elder's MaxScale is 1.125 now")));
  assert.deepEqual((await file(page))["NPC/CatSize.csv"], { "*": { MaxScale: "x1.5" } }, "not refused as a chance");
  assert.ok(![...await page.evaluate(() => [...document.querySelectorAll("#toasts .toast")].map(t => t.textContent))].some(t => /chance/.test(t)));
  // A chance column (Scars' EarChance) is still refused, naming the row by its role.
  await table(page, "Scars");
  await page.evaluate(() => {
    const c = document.getElementById("data-mul-col"); c.value = "EarChance"; c.dispatchEvent(new Event("change"));
    const b = document.getElementById("data-mul-by"); b.value = "2"; b.dispatchEvent(new Event("input"));
  });
  await page.click({ text: "Every EarChance × 2" });
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.startsWith("Deputy would be 1.5, and a chance can't go over 1")));
  assert.equal((await file(page))["NPC/Scars.csv"]?.["*"], undefined, "refused: nothing on every row");
  await page.close();
});

test("a dropdown cell keeps its choice on Enter, not on the first arrow key", { skip }, async () => {
  const page = await open();
  await table(page, "Fight moves");
  await page.click(cell("1", 3));
  await page.waitFor(`${cell("1", 3)} select`);
  await page.press("ArrowUp");   // Offensive -> Defensive: still choosing
  await page.waitFor(() => document.querySelector('.data-table [data-focus="cell:1:3"] select')?.value !== "Offensive");
  assert.equal(await page.count(`${cell("1", 3)} select`), 1, "the box is still open");
  assert.equal((await file(page))["AttackMove.csv"], undefined, "nothing kept yet");
  const chosen = await page.evaluate(() => document.querySelector('.data-table [data-focus="cell:1:3"] select').value);
  await page.press("Enter");
  await page.waitFor(() => !document.querySelector(".data-table td select"));
  assert.deepEqual((await file(page))["AttackMove.csv"], { "1": { Stance: chosen } });
  await page.close();
});

test("a quick row over a number set by hand says so, asks before replacing it, and the file's notes stay", { skip }, async () => {
  fs.mkdirSync(path.join(folders.data, "mods", "hand-xp"), { recursive: true });
  fs.writeFileSync(path.join(folders.data, "mods", "hand-xp", "mod.json"), JSON.stringify({ name: "Hand XP", enabled: true }));
  const hand = { _help: "My own words", _note: "flat XP", "CombatBaseExperience.csv": { _note: "30 for all", "*": { BaseExperience: 30 } } };
  fs.writeFileSync(path.join(folders.data, "mods", "hand-xp", "data.json"), JSON.stringify(hand));
  const page = await open();
  await page.evaluate(() => { const s = document.querySelector('.target select'); s.value = "hand-xp"; s.dispatchEvent(new Event("change")); });
  const now = () => document.querySelector('[data-key="quick:xp-fights"] .quick-now').textContent;
  await page.waitFor(() => document.querySelector('[data-key="quick:xp-fights"] .quick-now').textContent === "This row is set by hand to 30, in data.json");
  await page.evaluate(() => { document.querySelector('[data-key="quick:xp-fights"]').closest("details").open = true; });
  await page.evaluate(() => { const n = document.getElementById("quick-xp-fights"); n.value = "2"; n.dispatchEvent(new Event("change")); });
  await page.waitFor(() => !document.querySelector('[data-key="quick:xp-fights"] .quick-ask').hidden);
  assert.equal(await page.text('[data-key="quick:xp-fights"] .quick-ask span'), "This row is set by hand to 30 in data.json. Replace that with ×2?");
  assert.deepEqual((await file(page))["CombatBaseExperience.csv"], { _note: "30 for all", "*": { BaseExperience: 30 } }, "not replaced yet");
  await page.click({ text: "Keep it" });
  await page.waitFor(() => document.querySelector('[data-key="quick:xp-fights"] .quick-ask').hidden);
  assert.equal(await page.evaluate(now), "This row is set by hand to 30, in data.json");
  await page.evaluate(() => { const n = document.getElementById("quick-xp-fights"); n.value = "2"; n.dispatchEvent(new Event("change")); });
  await page.click({ text: "Replace it" });
  await page.waitFor(() => document.querySelector('[data-key="quick:xp-fights"] .quick-now').textContent === "×1 -> ×2");
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => document.querySelector(".target .dirty")?.textContent === "");
  const saved = JSON.parse(fs.readFileSync(path.join(folders.data, "mods", "hand-xp", "data.json"), "utf8"));
  assert.deepEqual(saved, { _help: "My own words", _note: "flat XP", "CombatBaseExperience.csv": { _note: "30 for all", "*": { BaseExperience: "x2" } } });
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("with the game's files unreadable the page says so, and still shows its file", { skip }, async () => {
  const empty = dataFolder();
  makeGame(empty.game);   // the exe and the folders, no paks
  const other = await startStudio(empty);
  try {
    const page = await browser.page();
    await page.goto(other.url + "#data");
    await page.waitFor('.section[data-page="data"][data-ready]', 20000);
    assert.equal(await page.text('.section[data-page="data"] .error-card h2'), "The game's tables can't be read");
    assert.match(await page.text('.section[data-page="data"] .error-card'), /Steam updating or verifying/);
    assert.equal(await page.evaluate(() => document.getElementById("data-quick").hidden), true);
    assert.deepEqual(page.consoleErrors().filter(e => !/400/.test(e)), []);
    await page.close();
  } finally {
    other.stop();
    await removeFolder(empty.root);
  }
});
