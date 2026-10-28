// Clan Mod Studio in a real browser: `python wcmods.py studio --no-browser --port 0` on a folder of its own
// (WCMODS_DATA, with a made-up game folder named in its wcmods.json), driven headless over the DevTools
// protocol (lib/browser.mjs). Skipped, with a reason, when no Chromium is found: set WC_BROWSER to one, or
// WC_REQUIRE_BROWSER=1 (as CI does) to fail instead of skipping.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { launch } from "../lib/browser.mjs";
import { browserPath, skip, sleep, startStudio, dataFolder, makeGame, remove, removeFolders } from "../lib/studio.mjs";

let browser, studio, folders;

before(async () => {
  if (skip) return;
  if (!browserPath) throw new Error("WC_REQUIRE_BROWSER=1, and no Chromium was found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)");
  folders = dataFolder();
  // One after the other, each kept as soon as it's up, so `after` can end whatever started if the other fails.
  studio = await startStudio(folders);
  browser = await launch({ browser: browserPath });
  // A first load, with time to spare: a cold browser and studio have taken 15 s on CI, and every test's own
  // waits are 10 s.
  const page = await browser.page();
  await page.goto(studio.url, { timeout: 60000 });
  await page.waitFor("#nav button", 60000);
  await page.close();
});

after(async () => {
  if (studio) studio.stop();
  if (browser) await browser.close();
  await removeFolders(folders);
});

test("the studio opens with no console errors, its status chips and its pages", { skip }, async () => {
  const page = await browser.page();
  await page.goto(studio.url);
  await page.waitFor("#nav button");
  await page.waitFor(() => document.querySelectorAll("#status .chip").length > 0);
  await page.waitFor(() => document.querySelector("#main .section h1"));
  assert.deepEqual(page.consoleErrors(), []);
  assert.equal(await page.evaluate("document.title"), "Mods · Clan Mod Studio");
  const chips = await page.evaluate(() => [...document.querySelectorAll("#status .chip")].map(c => c.dataset.said));
  assert.deepEqual(chips, ["Game closed", "No script loader", "No save yet", "Nothing installed"]);
  const pages = await page.evaluate(() => [...document.querySelectorAll("#nav button")].map(b => b.textContent));
  assert.deepEqual(pages, ["Mods", "Mod packs", "Settings and repair", "Palettes", "Your cat", "Controls", "Names", "Items",
    "Animations", "Characters", "Questlines", "Game data", "Save"]);
  assert.equal(await page.evaluate(() => document.querySelector("#nav button[aria-current]").textContent), "Mods");
  assert.equal(await page.text("#playBtn"), "Play");
  await page.close();
});

test("the console record counts a page file that fails to load, and not the API saying no", { skip }, async () => {
  const page = await browser.page();
  await page.goto(studio.url);
  await page.waitFor("#nav button");
  assert.equal(await page.evaluate(() => fetch("/api/info").then(r => r.status)), 403);   // no token: refused
  await page.evaluate(() => new Promise(ok => {
    const s = Object.assign(document.createElement("script"), { src: "/studio/not-there.js", onerror: ok, onload: ok });
    document.head.append(s);
  }));
  const missing = () => page.consoleErrors().some(e => /status of 404 .*\/studio\/not-there\.js/.test(e));
  for (let i = 0; i < 100 && !missing(); i++) await sleep(50);   // the browser's log comes on its own
  assert.ok(missing(), page.consoleErrors().join("\n"));
  assert.ok(!page.consoleErrors().some(e => e.includes("/api/info")), page.consoleErrors().join("\n"));
  await page.close();
});

test("Get set up asks where the game is, and finds it once the folder holds the game", { skip }, async () => {
  const page = await browser.page();
  await page.goto(studio.url + "#mods");
  await page.waitFor(".setup .steps li");
  const steps = async () => page.evaluate(() => [...document.querySelectorAll(".setup .step strong")].map(s => s.textContent.replace(/^(Done|To do): /, "")));
  assert.deepEqual(await steps(), ["Where's the game?", "Start the game once", "Install the script loader", "Add the menu's pages"]);
  assert.equal(await page.evaluate(() => document.querySelector(".setup .step.done")), null);
  makeGame(folders.game);
  await page.reload();
  await page.waitFor(".setup .steps li");
  assert.deepEqual(await steps(), ["Found the game", "Start the game once", "Install the script loader", "Add the menu's pages"]);
  assert.equal(await page.text(".setup .step.done .mono"), folders.game);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a mod made from a Make page's Editing-mod bar shows on the Mods page", { skip }, async () => {
  const page = await browser.page();
  await page.goto(studio.url + "#npcs");   // Characters: a Make page that opens without the game's files
  // The bar is laid out for good once the mod list is in its select (the New mod button moves with it).
  await page.waitFor(() => document.querySelector('.target select[aria-label="Mod that stores npcs.json"]')?.options.length > 0);
  await page.click({ text: "New mod…" });
  await page.waitFor(() => { const i = document.querySelector('input[aria-label="New mod folder name"]'); return i && i.getClientRects().length > 0; });
  await page.type('input[aria-label="New mod folder name"]', "e2e-mod");
  await page.click({ text: "Create" });
  // The new mod is listed first (the bar reads the list again for "mods-changed"), then chosen.
  await page.waitFor(() => document.querySelector(".target select").value === "e2e-mod");
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.includes("Created mod e2e-mod")));
  assert.ok(fs.existsSync(path.join(folders.data, "mods", "e2e-mod", "mod.json")), "the mod's folder is there");
  await page.goto(studio.url + "#mods");
  await page.waitFor('[data-key="mod:e2e-mod"]');
  assert.equal(await page.text('[data-key="mod:e2e-mod"] label strong'), "E2E Mod");
  assert.equal(await page.evaluate(() => document.querySelector("#mod-on-e2e-mod").checked), true);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("Apply and Play wait while the game is running", { skip }, async () => {
  makeGame(folders.game);   // with the game found, only the running game holds Apply back
  const running = await startStudio(folders, { WCMODS_FAKE_RUNNING: "1" });
  try {
    const page = await browser.page();
    await page.goto(running.url);
    await page.waitFor(() => [...document.querySelectorAll("#status .chip")].some(c => c.dataset.said === "Game running"));
    assert.equal(await page.evaluate(() => document.getElementById("installBtn").disabled), true);
    assert.equal(await page.evaluate(() => document.getElementById("installBtn").title), "Close the game first");
    assert.equal(await page.text("#playBtn"), "Playing");
    assert.equal(await page.evaluate(() => document.getElementById("playBtn").disabled), true);
    await page.close();
  } finally {
    running.stop();
  }
  // And not otherwise: the first studio (the game closed, whatever this machine runs), with the same game
  // folder, offers to apply.
  const page = await browser.page();
  await page.goto(studio.url);
  await page.waitFor(() => [...document.querySelectorAll("#status .chip")].some(c => c.dataset.said === "Game closed"));
  await page.waitFor(() => !document.getElementById("installBtn").disabled);
  assert.equal(await page.evaluate(() => document.getElementById("installBtn").title), "Build your mods and put them in the game");
  await page.close();
});

test("Help opens the guide in a panel, its links move between its pages, and Escape puts focus back", { skip }, async () => {
  const page = await browser.page();
  await page.goto(studio.url);
  await page.waitFor("#nav button");
  await page.click("#helpBtn");
  await page.waitFor(() => !document.getElementById("help").hidden && document.querySelector("#helpBody h1"));
  assert.equal(await page.text("#helpTitle"), "The guide");
  assert.equal(await page.evaluate(() => document.activeElement.id), "helpTitle", "the panel takes focus");
  await page.click({ text: "How Clan Mod Studio works", tag: "a" });
  await page.waitFor(() => document.getElementById("helpTitle").textContent === "How Clan Mod Studio works");
  const headings = await page.evaluate(() => [...document.querySelectorAll("#helpBody h2")].map(h => h.textContent));
  assert.ok(headings.includes("The log") && headings.includes("What Undo means here"), headings.join(", "));
  assert.equal(await page.count("#helpBody script, #helpBody iframe, #helpBody style"), 0, "only the renderer's tags");
  assert.equal(await page.evaluate(() => document.getElementById("helpOpen").getAttribute("href")), "/help/studio");
  // A link to a heading of another page (studio.md#the-log) opens the panel there.
  await page.evaluate(async () => (await import("/studio/lib/wc.js")).openHelp("studio#the-log"));
  await page.waitFor(() => document.getElementById("helpOpen").getAttribute("href") === "/help/studio#the-log");
  await page.waitFor(() => document.getElementById("helpBody").scrollTop > 0);
  await page.press("Escape");
  await page.waitFor(() => document.getElementById("help").hidden);
  assert.equal(await page.evaluate(() => document.activeElement.id), "helpBtn", "focus goes back where it was");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("Apply with the game's files unreadable: a sentence at the top of the log, Apply the rest anyway, and Last apply brings it back", { skip }, async () => {
  makeGame(folders.game);   // the exe and folders, no paks: nothing the build can read
  const page = await browser.page();
  await page.goto(studio.url);
  await page.waitFor(() => !document.getElementById("installBtn").disabled);
  await page.click("#installBtn");
  await page.waitFor(() => !document.getElementById("drawer").hidden && document.getElementById("drawerSummary").textContent.includes("can't be read"), 30000);
  const summary = await page.text("#drawerSummary");
  assert.match(summary, /^Nothing went in the game, because some mods couldn't be made ready: .*the game's files can't be read/);
  assert.match(summary, /press Apply the rest anyway/);
  assert.doesNotMatch(summary, /--force|Traceback|Error\b/);
  await page.waitFor(() => [...document.querySelectorAll("#drawer button")].some(b => b.textContent === "Apply the rest anyway"));
  assert.equal(await page.evaluate(() => document.getElementById("drawerLog").getAttribute("role")), "log");
  assert.equal(await page.evaluate(() => document.getElementById("drawerSummary").getAttribute("aria-live")), "polite");
  assert.equal(await page.evaluate(() => document.activeElement.id), "drawerTitle", "the log takes focus");
  // Closed, then brought back with Last apply, from last-apply.log in the player's folder.
  await page.click("#drawerClose");
  await page.waitFor(() => document.getElementById("drawer").hidden);
  assert.ok(fs.existsSync(path.join(folders.data, "last-apply.log")), "last-apply.log is kept");
  await page.click("#lastApplyBtn");
  await page.waitFor(() => !document.getElementById("drawer").hidden);
  assert.match(await page.text("#drawerTitle"), /^Apply to game \(\d{4}-\d\d-\d\d \d\d:\d\d\)$/);
  assert.match(await page.text("#drawerSummary"), /can't be read/);
  // The code hasn't changed: no Restart the studio; and nothing is installed.
  const chips = await page.evaluate(() => [...document.querySelectorAll("#status .chip")].map(c => c.dataset.said));
  assert.ok(!chips.includes("Restart the studio") && chips.includes("Not applied yet"), chips.join(", "));
  await page.close();
});

// The Characters page with a cat added and not saved: a Make page that opens without the game's files.
async function unsavedCat(page, url) {
  await page.goto(url + "#npcs");
  await page.waitFor(() => document.querySelector('.target select[aria-label="Mod that stores npcs.json"]')?.options.length > 0, 20000);
  await page.click({ text: "Add a cat" });
  await page.waitFor(() => document.querySelector(".target .dirty")?.textContent === "Unsaved changes");
  await page.evaluate("window.__notReloaded = true");   // a reload takes it away
}
// eslint-disable-next-line no-new-func -- waitFor runs a function's source in the page, so the pattern goes in it
const toastSays = (page, re) => page.waitFor(new Function(`return [...document.querySelectorAll("#toasts .toast")].some(t => ${re}.test(t.textContent))`));

test("unsaved changes outlast the studio's window closing: the page keeps them, finds it again and saves to it", { skip }, async () => {
  const d = dataFolder();
  const first = await startStudio(d);
  const port = Number(new URL(first.url).port);
  const page = await browser.page();
  let second = null;
  try {
    await unsavedCat(page, first.url);
    const mod = await page.evaluate(() => document.querySelector(".target select").value);
    first.stop();
    // A save that can't reach it, and the studio still not there a few seconds later: the card, not a reload.
    await page.click({ text: "Save to mod" });
    await toastSays(page, /window was closed/);
    await page.waitFor(() => /black window was closed/.test(document.querySelector(".error-card h2")?.textContent || ""), 15000);
    assert.match(await page.text(".error-card p"), /unsaved changes stay on this page/);
    assert.equal(await page.evaluate("window.__notReloaded"), true);
    // Opened again (on the same port, with a new token): the page carries on as it was, and saves.
    second = await startStudio(d, {}, { port });
    assert.equal(Number(new URL(second.url).port), port, `the studio came back on port ${port}`);
    await page.waitFor(() => !document.querySelector(".error-card"), 15000);
    await toastSays(page, /open again\. Your unsaved changes are still here/);
    assert.equal(await page.evaluate("window.__notReloaded"), true, "the page wasn't reloaded");
    assert.equal(await page.text(".target .dirty"), "Unsaved changes");
    await page.click({ text: "Save to mod" });
    await page.waitFor(() => document.querySelector(".target .dirty")?.textContent === "", 10000);
    const saved = JSON.parse(fs.readFileSync(path.join(d.data, "mods", mod, "npcs.json"), "utf8"));
    assert.deepEqual(saved.npcs.map(c => c.name), ["New cat"]);
    // Nothing went wrong but the requests that found the studio closed, which the browser logs itself.
    assert.deepEqual(page.consoleErrors().filter(e => !/ERR_CONNECTION_REFUSED/.test(e)), []);
  } finally {
    first.stop();
    if (second) second.stop();
    await page.close();
    await remove(d.root);
    await remove(d.app);
  }
});

test("Restart the studio waits for unsaved changes to be saved, and a new studio that never answers is said after 30 s", { skip, timeout: 120000 }, async () => {
  const d = dataFolder();   // a copy of wcmods of its own: it's "updated" here
  const s = await startStudio(d, { WCMODS_NO_RESTART: "1" });   // answers, but never restarts
  const page = await browser.page();
  try {
    await unsavedCat(page, s.url);
    // wcmods updated under the running studio: Restart the studio shows.
    const later = new Date(Date.now() + 60000);
    fs.utimesSync(path.join(d.app, "wcmods", "guide.py"), later, later);
    // Coming back to the window looks again (the page may still be starting up the first time: until it does).
    const restartShows = () => [...document.querySelectorAll("#status button.chip")].some(c => c.dataset.said === "Restart the studio");
    for (let i = 0; !await page.evaluate(restartShows); i++) {
      assert.ok(i < 15, "Restart the studio shows once the window comes back to the front");
      await page.evaluate("window.dispatchEvent(new Event('focus'))");
      await sleep(1000);
    }
    await page.click("#status button.chip");   // Restart the studio
    await toastSays(page, /^Save your changes first \(Characters\), then press Restart the studio/);
    assert.equal(await page.evaluate("window.__notReloaded"), true);
    await page.click({ text: "Save to mod" });
    await page.waitFor(() => document.querySelector(".target .dirty")?.textContent === "", 10000);
    // Saved: it restarts. The new studio never answers here (its page can't be had), so after 30 s the page
    // says what to do, and goes on waiting.
    await page.evaluate(() => {
      window.__fetch = window.fetch;
      window.fetch = (url, init) => (url === "/" ? Promise.reject(new TypeError("Failed to fetch")) : window.__fetch(url, init));
    });
    await page.click("#status button.chip");   // Restart the studio
    await page.waitFor(() => [...document.querySelectorAll("#status .chip")].some(c => c.dataset.said === "Restarting…"));
    const started = Date.now();
    await page.waitFor(() => /black window was closed/.test(document.querySelector(".error-card h2")?.textContent || ""), 40000);
    assert.ok(Date.now() - started > 25000, `said after ${Date.now() - started} ms`);
    // It answers again: with nothing unsaved, the page reloads to be the new studio's own.
    await page.evaluate("window.fetch = window.__fetch");
    await page.waitFor(() => document.readyState === "complete" && window.__notReloaded === undefined && document.querySelector("#nav button"), 15000);
  } finally {
    s.stop();
    await page.close();
    await remove(d.root);
    await remove(d.app);
  }
});
