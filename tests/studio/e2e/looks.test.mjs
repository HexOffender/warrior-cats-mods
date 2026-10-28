// The Palettes and Your cat pages in a real browser, against a studio over a folder of its own with a made-up game
// (lib/studio.mjs: the exe and folders, no paks, so the game's files can't be read). The game's colour tables come
// from a made-up UE4SS.log where a test needs them, and the save from lib/studio.mjs's writeSave. Skipped, with a
// reason, when no Chromium is found: set WC_BROWSER to one, or WC_REQUIRE_BROWSER=1 to fail instead.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { findBrowser, launch } from "../lib/browser.mjs";
import { dataFolder, e2eSkip, makeGame, remove, removeFolders, requireBrowser, sleep, startStudio, warmUp, writeSave,
  writeTables } from "../lib/studio.mjs";

const browserPath = findBrowser();
const skip = e2eSkip(browserPath);

let browser, studio, folders;

before(async () => {
  if (skip) return;
  requireBrowser(browserPath);
  folders = dataFolder();
  makeGame(folders.game);
  studio = await startStudio(folders);
  browser = await launch({ browser: browserPath });
  await warmUp(browser, studio.url);
});

after(async () => {
  if (studio) studio.stop();
  if (browser) await browser.close();
  if (folders) await removeFolders(folders);
});

// ---------- the folder ----------
const modsDir = () => path.join(folders.data, "mods");
const fileOf = (mod, name) => path.join(modsDir(), mod, name);
const readJson = file => JSON.parse(fs.readFileSync(file, "utf8"));
function makeMod(id, files, meta = {}) {
  fs.mkdirSync(path.join(modsDir(), id), { recursive: true });
  fs.writeFileSync(fileOf(id, "mod.json"), JSON.stringify({ name: id === "my-mods" ? "My mods" : id, enabled: true, ...meta }));
  for (const [name, doc] of Object.entries(files)) fs.writeFileSync(fileOf(id, name), JSON.stringify(doc));
}
// Each test starts with no mods, no colour tables and no save.
async function fresh() {
  await remove(modsDir());
  await remove(path.join(folders.game, "Wrc", "Binaries", "Win64", "ue4ss", "UE4SS.log"));
  await remove(path.join(folders.saves, "WrcGame.sav"));
}
// The game's tables: 25 colours each, all told apart.
const TABLES = Object.fromEntries(["FurColors", "PatternMaskColors", "MarkingMaskColors", "IrisColors"].map((t, k) =>
  [t, [...Array(25).keys()].map(i => "#" + [40 + i * 8, 30 + k * 50, 200 - i * 6].map(v => v.toString(16).padStart(2, "0")).join("").toUpperCase())]));
// A save: your cat (a leader, wearing coat `fur`) and one warrior.
const CAT = (role, prefix, suffix, fur) => `(ClanType=RiverClan,Role=${role},PrefixNameId="${prefix}",SuffixNameId="${suffix}",` +
  `FurColorIdx=${fur},Pattern01ColorIdx=5,Pattern02ColorIdx=7,EyeLeftColorIdx=2,EyeRightColorIdx=4,ScarEarId=1,BodyValue=2,` +
  "FurIdx=2,TailIdx=1,EarIdx=0,EyeValue=3,PatternIdx=4,CatSize=1.1)";
const SAVE = fur => ({ acct: {
  0: { GameplayProgression: { "Gameplay.Combat.Character.Cat.Player": { Customization: CAT("Leader", "STR_CAT_NAME1", "_STAR", fur) } },
    NPCData: { RiverClan: { Warrior: [CAT("Warrior", "STR_CAT_NAME2", "_HEART", 9)] } } },
  Shared: { General: { CurrentCatSlot: 0 } } } });

// ---------- the page ----------
// Press the button (or other element) with this text inside one page's pane: hidden panes of other pages have
// buttons with the same words (Save to mod).
async function press(page, scope, text, tag = "button") {
  const mark = `e2e-${Math.random().toString(36).slice(2)}`;
  const found = await page.evaluate(`(() => {
    const n = [...document.querySelectorAll(${JSON.stringify(`${scope} ${tag}`)})].find(x => x.textContent.trim() === ${JSON.stringify(text)});
    if (!n) return false;
    n.setAttribute("data-e2e", ${JSON.stringify(mark)});
    return true;
  })()`);
  if (!found) throw new Error(`no ${tag} "${text}" in ${scope}`);
  await page.click(`[data-e2e="${mark}"]`);
}
const PAL = '[data-page="palettes"]', CATP = '[data-page="cat"]';
const emit = (page, evt) => page.evaluate(`import("/studio/lib/wc.js").then(wc => { wc.bus.emit(${JSON.stringify(evt)}, {}); return true; })`);
const status = (page, scope) => page.evaluate(`document.querySelector(${JSON.stringify(`${scope} .target .dirty`)}).textContent`);
async function waitForFile(file, check) {
  const end = Date.now() + 10000;
  for (;;) {
    try { if (fs.existsSync(file) && check(readJson(file))) return readJson(file); } catch (e) { /* half written */ }
    if (Date.now() > end) throw new Error(`${file} didn't come to be as expected: ${fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "missing"}`);
    await sleep(50);
  }
}
// The node tests run their files side by side, each with a studio and a browser of its own: on a busy machine a
// page's first load (the studio reading the made-up game for the first time) can take a while.
const SLOW = 30000;
async function openPalettes(page, url = studio.url) {
  await page.goto(url + "#palettes", { timeout: SLOW });
  await page.waitFor(`${PAL} #pal-tab-pattern`, SLOW);
  // Laid out for good once the file is in (the Editing mod bar's list), the quick palettes are drawn above it and the
  // Start from row has its chips: clicks before that can land where a button was a moment ago.
  await page.waitFor(() => document.querySelector('[data-page="palettes"] .target select')?.options.length > 0
    && [...document.querySelectorAll('[data-page="palettes"] h2')].some(h => h.textContent === "Quick palettes")
    && document.querySelector('[data-page="palettes"] [data-focus="pal:from:game"]'));
  await sleep(200);
}
const noNullText = scope => `[...document.querySelectorAll(${JSON.stringify(`${scope} *`)})].filter(n => [...n.childNodes].some(c => c.nodeType === 3 && c.textContent.trim() === "null")).length`;

// ---------- Palettes ----------
test("Palettes opens without the game's files: the eyes say why, and the game's colours are numbered cards", { skip }, async () => {
  await fresh();
  const page = await browser.page();
  await openPalettes(page);
  assert.equal(await page.evaluate(`document.querySelector('${PAL} #pal-tab-pattern').getAttribute("aria-selected")`), "true",
    "it opens on Pattern, as the eyes can't be shown");
  assert.equal(await page.count(`${PAL} #pal-panel .card`), 25);
  assert.equal(await page.text(`${PAL} #pal-panel .card strong`), "Pattern 0");
  assert.match(await page.text(`${PAL} .pal-tables`), /^Press Play once, then come back/);
  assert.equal(await page.evaluate(`document.querySelector('${PAL} [data-focus="pal:mood:vivid"]').disabled`), true);
  await page.click(`${PAL} #pal-tab-eyes`);
  await page.waitFor(() => document.querySelector('[data-page="palettes"] #pal-panel .empty'));
  assert.match(await page.text(`${PAL} #pal-panel .empty`), /The game's eye colours can't be read just now/);
  assert.equal(await page.evaluate(noNullText(PAL)), 0, "no stray null among the quick palettes");
  // Its help link opens the Palettes page of the guide.
  await page.click(`${PAL} .section-head .btn.link`);
  await page.waitFor(() => !document.getElementById("help").hidden && document.querySelector("#helpBody h2"));
  assert.equal(await page.text("#helpTitle"), "Palettes");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("the five-minute first try: a new pattern colour made on Palettes, worn on Your cat", { skip }, async () => {
  await fresh();
  const page = await browser.page();
  await page.goto(studio.url + "#cat", { timeout: SLOW });   // open first: it reads again when a palette is saved
  await page.waitFor(`${CATP} [data-focus="slot:pattern:3"]`, SLOW);
  assert.equal(await page.count(`${CATP} [data-focus="slot:pattern:25"]`), 0);
  await page.evaluate(() => { location.hash = "#palettes"; });
  await page.waitFor(`${PAL} #pal-tab-pattern`);
  await page.waitFor(() => { const b = document.getElementById("pal-add-pattern"); return b && !b.disabled; });
  await page.click(`${PAL} #pal-add-pattern`);
  await page.waitFor(`${PAL} #pal-pattern-25`);
  assert.equal(await page.evaluate("document.activeElement.id"), "pal-pattern-25", "focus goes to the new colour's picker");
  assert.equal(await page.text(`${PAL} #pal-tab-pattern .mono`), " 1 changed");
  await press(page, PAL, "Save to mod");
  const pal = await waitForFile(fileOf("my-mods", "palette.json"), p => p.pattern && p.pattern["25"]);
  assert.equal(pal.pattern["25"], "#888888");
  await page.evaluate(() => { location.hash = "#cat"; });
  await page.waitFor(`${CATP} [data-focus="slot:pattern:25"]`);
  await page.click(`${CATP} [data-focus="slot:pattern:25"]`);
  await press(page, CATP, "Save to mod");
  const cats = await waitForFile(fileOf("my-mods", "cats.json"), c => c.player);
  assert.deepEqual(cats.player, { slots: { pattern: 25 } });
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("unsaved colours survive an Apply, and the bar says they aren't in the game yet", { skip }, async () => {
  await fresh();
  makeMod("my-mods", { "palette.json": { pattern: { 25: "#ff00cc" } } });
  const page = await browser.page();
  await openPalettes(page);
  await page.click(`${PAL} #pal-tab-pattern`);
  await page.waitFor(() => { const b = document.getElementById("pal-add-pattern"); return b && !b.disabled; });
  await page.click(`${PAL} #pal-add-pattern`);
  await page.waitFor(`${PAL} #pal-pattern-26`);
  assert.equal(await status(page, PAL), "Unsaved changes");
  await emit(page, "installed");
  await sleep(500);
  assert.equal(await page.count(`${PAL} #pal-pattern-26`), 1, "the new colour is still on the page");
  assert.equal(await status(page, PAL), "Not in the game yet: Save to mod, then Apply");
  await press(page, PAL, "Save to mod");
  await waitForFile(fileOf("my-mods", "palette.json"), p => p.pattern["26"]);
  await page.waitFor(() => document.querySelector('[data-page="palettes"] .target .dirty').textContent === "");
  await page.close();
});

test("Quick palettes' Apply saves the page first, and waits while the game runs", { skip }, async () => {
  await fresh();
  makeMod("my-mods", { "palette.json": { fur: { 3: "#112233" } } });
  const page = await browser.page();
  await openPalettes(page);
  await page.click(`${PAL} #pal-tab-fur`);
  await page.waitFor(`${PAL} #pal-fur-4`);
  await page.evaluate(() => {
    const inp = document.getElementById("pal-fur-4");
    inp.value = "#445566";
    inp.dispatchEvent(new Event("input"));
  });
  // Every request the page makes, in order.
  await page.evaluate(() => {
    window.calls = [];
    const real = window.fetch;
    window.fetch = (url, init) => { window.calls.push(`${(init && init.method) || "GET"} ${url}`); return real(url, init); };
  });
  await press(page, PAL, "Apply 1 and install");   // My mods holds only a palette, so it's one of the quick palettes
  await page.waitFor(() => window.calls.includes("POST /api/palettes/apply"), 15000);
  const calls = await page.evaluate("window.calls");
  const put = calls.indexOf("PUT /api/mods/my-mods/file/palette.json");
  assert.ok(put >= 0 && put < calls.indexOf("POST /api/palettes/apply"), calls.join(", "));
  assert.equal(readJson(fileOf("my-mods", "palette.json")).fur["4"], "#445566");
  await page.close();
  // With the game running, the button waits, as the shell's Apply does.
  const running = await startStudio(folders, { WCMODS_FAKE_RUNNING: "1" });
  try {
    const p2 = await browser.page();
    await openPalettes(p2, running.url);
    await p2.waitFor(() => [...document.querySelectorAll('[data-page="palettes"] .btn.primary')].some(b => b.textContent === "Apply 1 and install"));
    const button = await p2.evaluate(() => {
      const b = [...document.querySelectorAll('[data-page="palettes"] .btn.primary')].find(x => x.textContent === "Apply 1 and install");
      return { disabled: b.disabled, title: b.title };
    });
    assert.deepEqual(button, { disabled: true, title: "Close the game first" });
    await p2.close();
  } finally {
    running.stop();
  }
});

test("a first Quick Apply with colours unsaved makes My mods, ticks it and puts it in, rather than turning it off", { skip }, async () => {
  await fresh();
  const page = await browser.page();
  await openPalettes(page);
  assert.equal(await page.count(`${PAL} input[id^="quick-"]`), 0, "no quick palettes yet");
  await page.click(`${PAL} #pal-tab-pattern`);
  await page.waitFor(`${PAL} #pal-pattern-3`);
  await page.evaluate(() => { const i = document.getElementById("pal-pattern-3"); i.value = "#123456"; i.dispatchEvent(new Event("input")); });
  // Every request the page makes, in order, with what it sent.
  await page.evaluate(() => {
    window.calls = [];
    const real = window.fetch;
    window.fetch = (url, init) => { window.calls.push({ call: `${(init && init.method) || "GET"} ${url}`, body: init && init.body }); return real(url, init); };
  });
  await press(page, PAL, "Use the game's colours and install");
  await page.waitFor(() => window.calls.some(c => c.call === "POST /api/palettes/apply"), 15000);
  const sent = await page.evaluate(() => window.calls.find(c => c.call === "POST /api/palettes/apply").body);
  assert.deepEqual(JSON.parse(sent).ids, ["my-mods"], "the palette just saved is one of those Apply turns on");
  assert.equal(readJson(fileOf("my-mods", "palette.json")).pattern["3"], "#123456");
  await page.waitFor(`${PAL} #quick-my-mods`);
  assert.equal(await page.evaluate(`document.querySelector('${PAL} #quick-my-mods').checked`), true, "its tile is drawn, ticked");
  assert.ok(await page.evaluate(() => [...document.querySelectorAll("#toasts span")].some(s => s.textContent === "Ticked My mods too, so the colours you just saved go in.")));
  await page.close();
});

test("Restyle, Undo and Reset tab change the game's colours and keep the new ones", { skip }, async () => {
  await fresh();
  writeTables(folders.game, TABLES);
  makeMod("my-mods", { "palette.json": { pattern: { 25: "#ff00cc" } } });
  const page = await browser.page();
  await openPalettes(page);
  await page.click(`${PAL} #pal-tab-pattern`);
  await page.waitFor(`${PAL} #pal-pattern-25`);
  assert.equal(await page.count(`${PAL} .pal-tables:not([hidden])`), 0, "the game's colours are in");
  const changed = () => page.evaluate(`(document.querySelector('${PAL} #pal-tab-pattern .mono') || { textContent: "" }).textContent`);
  assert.equal(await changed(), " 1 changed");
  await page.click(`${PAL} [data-focus="pal:mood:vivid"]`);
  await page.waitFor(`${PAL} [data-focus="pal:undo"]`);
  assert.equal(await changed(), " 26 changed");
  assert.equal(await page.text(`${PAL} [data-focus="pal:undo"]`), "Undo Vivid");
  await page.click(`${PAL} [data-focus="pal:undo"]`);
  await page.waitFor(() => !document.querySelector('[data-page="palettes"] [data-focus="pal:undo"]'));
  assert.equal(await changed(), " 1 changed");
  await page.click(`${PAL} [data-focus="pal:mood:ember"]`);
  await page.waitFor(`${PAL} [data-focus="pal:undo"]`);
  await page.click(`${PAL} [data-focus="pal:reset"]`);
  await page.waitFor(() => document.querySelector('[data-page="palettes"] [data-focus="pal:undo"]')?.textContent === "Undo Reset Pattern");
  assert.equal(await changed(), " 1 changed");
  assert.equal(await page.count(`${PAL} #pal-pattern-25`), 1, "the new colour keeps its card");
  // The preview's dropdown lists the new colour, with the game's.
  const options = await page.evaluate(() => [...document.getElementById("pal-pick-pattern").options].map(o => o.textContent));
  assert.equal(options.length, 26);
  assert.equal(options[3], `3 · ${TABLES.PatternMaskColors[3]}`);
  assert.equal(options[25], "25 (new) · #FF00CC");
  // Saved, there's nothing to undo: the file is what the page shows.
  await press(page, PAL, "Save to mod");
  await page.waitFor(() => !document.querySelector('[data-page="palettes"] [data-focus="pal:undo"]'));
  assert.deepEqual(readJson(fileOf("my-mods", "palette.json")).pattern, { 25: "#FF00CC" });
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("what Palettes can't show is listed with a Remove, and Save says what keeps the file out of the game", { skip }, async () => {
  await fresh();
  makeMod("my-mods", { "palette.json": { pattern: { x: "#ffffff", 3: "#123456" }, hats: { a: 1 } } });
  const page = await browser.page();
  await openPalettes(page);
  await page.waitFor(`${PAL} .pal-unread summary strong`);
  assert.equal(await page.text(`${PAL} .pal-unread summary strong`), "2 entries this page can't show");
  await page.click(`${PAL} .pal-unread summary`);
  await page.click(`${PAL} button[aria-label^='Remove Pattern "x"']`);
  await page.waitFor(() => !document.querySelector(`[data-page="palettes"] button[aria-label^='Remove Pattern "x"']`));
  await press(page, PAL, "Save to mod");
  await page.waitFor(() => !document.querySelector('[data-page="palettes"] .problems').hidden);
  assert.match(await page.text(`${PAL} .problems`), /unknown part 'hats'/);
  let saved = readJson(fileOf("my-mods", "palette.json"));
  assert.deepEqual([saved.pattern, saved.hats], [{ 3: "#123456" }, { a: 1 }]);
  assert.equal(await page.evaluate(`document.querySelector('${PAL} .pal-unread').open`), true, "the list stays open after the save");
  await page.click(`${PAL} button[aria-label^='Remove "hats"']`);
  await page.waitFor(() => !document.querySelector(`[data-page="palettes"] button[aria-label^='Remove "hats"']`));
  await press(page, PAL, "Save to mod");
  await page.waitFor(() => document.querySelector('[data-page="palettes"] .problems').hidden);
  saved = readJson(fileOf("my-mods", "palette.json"));
  assert.equal("hats" in saved, false);
  await page.close();
});

test("one colour named twice is listed as a conflict, written back as it was, and Save says which one Apply uses", { skip }, async () => {
  await fresh();
  makeMod("my-mods", {});
  // Written as text: an object in this file would put "3" first, whatever order it's typed in.
  fs.writeFileSync(fileOf("my-mods", "palette.json"), '{"pattern": {"03": "#111111", "3": "#222222"}}');
  const page = await browser.page();
  await openPalettes(page);
  await page.waitFor(`${PAL} .pal-unread summary strong`);
  assert.equal(await page.text(`${PAL} .pal-unread summary strong`), "2 entries this page can't show");
  const listed = await page.evaluate(`[...document.querySelectorAll('${PAL} .pal-unread li span')].map(s => s.textContent)`);
  assert.ok(listed.every(t => t.includes('"3" and "03" both name pattern colour 3')), listed.join(" | "));
  // Another change saved: both are written back as they were, and the note under the bar says which one Apply uses.
  await page.click(`${PAL} #pal-tab-pattern`);
  await page.waitFor(`${PAL} #pal-pattern-5`);
  await page.evaluate(() => { const i = document.getElementById("pal-pattern-5"); i.value = "#555555"; i.dispatchEvent(new Event("input")); });
  await press(page, PAL, "Save to mod");
  await page.waitFor(() => !document.querySelector('[data-page="palettes"] .save-notes').hidden);
  const saved = readJson(fileOf("my-mods", "palette.json"));
  assert.deepEqual(saved.pattern, { 3: "#222222", "03": "#111111", 5: "#555555" });
  assert.match(await page.text(`${PAL} .save-notes li`), /^Pattern: "3" and "03" both name pattern colour 3, and Apply uses "03", the later in the file: remove the other$/);
  // Set on the page, the colour takes the place of both.
  await page.evaluate(() => { const i = document.getElementById("pal-pattern-3"); i.value = "#333333"; i.dispatchEvent(new Event("input")); });
  await page.waitFor(() => [...document.querySelectorAll('[data-page="palettes"] .pal-unread li span')].every(s => s.textContent.endsWith("; Save puts the colour set here in its place)")));
  await press(page, PAL, "Save to mod");
  await waitForFile(fileOf("my-mods", "palette.json"), p => p.pattern["3"] === "#333333");
  assert.deepEqual(readJson(fileOf("my-mods", "palette.json")).pattern, { 3: "#333333", 5: "#555555" });
  await page.waitFor(() => document.querySelector('[data-page="palettes"] .pal-unread')?.closest("[hidden]") || !document.querySelector('[data-page="palettes"] .pal-unread'));
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("Save says when another palette adds the same new colour, and which one shows", { skip }, async () => {
  await fresh();
  makeMod("dark", { "palette.json": { pattern: { 25: "#000000" } } }, { name: "Dark Forest", priority: 5 });
  makeMod("my-mods", { "palette.json": { pattern: { 25: "#ff00cc" } } });
  const page = await browser.page();
  await openPalettes(page);
  await page.click(`${PAL} #pal-tab-pattern`);
  await page.waitFor(`${PAL} #pal-pattern-25`);
  await page.evaluate(() => { const i = document.getElementById("pal-pattern-25"); i.value = "#ff00dd"; i.dispatchEvent(new Event("input")); });
  await press(page, PAL, "Save to mod");
  await page.waitFor(() => !document.querySelector('[data-page="palettes"] .save-notes').hidden);
  assert.equal(await page.text(`${PAL} .save-notes li`),
    "Pattern colour 25 is also added by Dark Forest, which is later in the Mods list, so its colour shows");
  await page.close();
});

// ---------- Your cat ----------
test("Your cat opens on a save it can't read, then shows what the cat wears, and keeps up after an Apply", { skip }, async () => {
  await fresh();
  fs.writeFileSync(path.join(folders.saves, "WrcGame.sav"), "");   // half written, while the game saves
  const page = await browser.page();
  await page.goto(studio.url + "#cat", { timeout: SLOW });
  await page.waitFor(`${CATP} [data-focus="slot:fur:3"]`, SLOW);
  assert.match(await page.text(`${CATP} .banner[role="status"]`), /Your save couldn't be read \(it may be half written/);
  assert.equal(await page.evaluate(`document.querySelector('${CATP} input[aria-label="Use its own nose colour"]').disabled`), false,
    "the colours of its own still work");
  const nowText = () => page.evaluate(`[...document.querySelectorAll('${CATP} h3')].find(h => h.textContent === "Coat colour").nextSibling.textContent`);
  assert.equal(await nowText(), "now: unknown (kept)");
  await writeSave(folders.saves, SAVE(3));
  await emit(page, "focus");
  await page.waitFor(() => document.querySelector('[data-page="cat"] .banner[role="status"]').hidden);
  assert.equal(await nowText(), "now: 3 (kept)");
  // Chosen on the page (unsaved), then an Apply writes the save: "now" follows it, and the choice stays.
  await page.click(`${CATP} [data-focus="slot:fur:5"]`);
  await writeSave(folders.saves, SAVE(11));
  await emit(page, "installed");
  await page.waitFor(() => [...document.querySelectorAll('[data-page="cat"] h3')].find(h => h.textContent === "Coat colour").nextSibling.textContent === "5 (now 11)");
  assert.equal(await status(page, CATP), "Not in the game yet: Save to mod, then Apply");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a cats.json written by hand: colour names load, and what the page can't change is listed and removable", { skip }, async () => {
  await fresh();
  makeMod("my-mods", { "cats.json": { player: { colours: { nose: "red" }, slots: { coat: 3, fur: 4 } } } });
  writeTables(folders.game, TABLES);   // the game's colours in: no "now grey" line, and nothing in its place
  const page = await browser.page();
  await page.goto(studio.url + "#cat", { timeout: SLOW });
  await page.waitFor(`${CATP} button[aria-label="Remove slots.coat"]`, SLOW);
  assert.equal(await page.evaluate(noNullText(CATP)), 0, "no stray null where a line is left out");
  assert.deepEqual(await page.evaluate(`(() => { const box = document.querySelector('${CATP} input[aria-label="Use its own nose colour"]');
    const pick = document.querySelector('${CATP} input[aria-label="Nose colour"]'); return [box.checked, pick.value]; })()`), [true, "#ff0000"]);
  assert.equal(await status(page, CATP), "", "reading \"red\" as #FF0000 changes nothing");
  assert.equal(await page.evaluate(`document.querySelector('${CATP} [data-focus="slot:fur:4"]').getAttribute("aria-pressed")`), "true");
  // Saved as it is, Save says what keeps it out of the game; removed, it's fine.
  await press(page, CATP, "Save to mod");
  await page.waitFor(() => !document.querySelector('[data-page="cat"] .problems').hidden);
  assert.match(await page.text(`${CATP} .problems`), /player\.slots\.coat should be one of fur, pattern, marking/);
  await page.click(`${CATP} button[aria-label="Remove slots.coat"]`);
  await page.waitFor(() => !document.querySelector('[data-page="cat"] button[aria-label="Remove slots.coat"]'));
  await press(page, CATP, "Save to mod");
  await page.waitFor(() => document.querySelector('[data-page="cat"] .problems').hidden);
  assert.deepEqual(readJson(fileOf("my-mods", "cats.json")).player, { colours: { nose: "#FF0000" }, slots: { fur: 4 } });
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});
