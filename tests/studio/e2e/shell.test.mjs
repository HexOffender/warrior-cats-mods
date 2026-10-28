// Clan Mod Studio in a real browser: `python wcmods.py studio --no-browser --port 0` on a folder of its own
// (WCMODS_DATA, with a made-up game folder named in its wcmods.json), driven headless over the DevTools
// protocol (lib/browser.mjs). Skipped, with a reason, when no Chromium is found: set WC_BROWSER to one, or
// WC_REQUIRE_BROWSER=1 (as CI does) to fail instead of skipping.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { findBrowser, launch } from "../lib/browser.mjs";
import { REPO } from "../lib/dom.mjs";

const EXE = "Wrc-Win64-ShippingDRM.exe";   // config.EXE_NAME: what makes a folder the game's
const browserPath = findBrowser();
const required = process.env.WC_REQUIRE_BROWSER === "1";
const skip = browserPath || required ? false : "no Chromium found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)";
const sleep = ms => new Promise(r => setTimeout(r, ms));

// A studio started on a free port over the test's folders; its URL is on the first line it prints. The game
// counts as closed (WCMODS_FAKE_RUNNING=0) unless `env` says otherwise, whether or not the real one is running
// on this machine; its temp folder (the inbox a dropped mod waits in) is the test's, not the one a studio of
// the player's would share.
async function startStudio(folders, env = {}) {
  const python = process.env.PYTHON || "python";
  const own = { ...process.env, WCMODS_DATA: folders.data, WCMODS_FAKE_RUNNING: "0", TEMP: folders.temp, TMP: folders.temp,
    TMPDIR: folders.temp, ...env };
  delete own.WCMODS_GAME_BUILD;   // a build number a developer set to try an update
  const proc = spawn(python, ["-I", "wcmods.py", "studio", "--no-browser", "--port", "0"],
    { cwd: REPO, env: own, stdio: ["ignore", "pipe", "pipe"] });
  let out = "", err = "";
  proc.stdout.on("data", d => { out += d; });
  proc.stderr.on("data", d => { err += d; });
  // On Windows `python` may be a launcher with the real interpreter under it: the whole tree goes.
  const stop = () => {
    if (proc.exitCode !== null) return;
    if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(proc.pid), "/T", "/F"], { stdio: "ignore" });
    else proc.kill();
  };
  const end = Date.now() + 30000;
  for (;;) {
    const m = /running at (http:\/\/127\.0\.0\.1:\d+\/)/.exec(out);
    if (m) return { url: m[1], proc, stop, output: () => out + err };
    if (proc.exitCode !== null) throw new Error(`the studio ended (${proc.exitCode}): ${out}${err}`);
    if (Date.now() > end) { stop(); throw new Error(`the studio didn't say where it runs in 30 s: ${out}${err}`); }
    await sleep(50);
  }
}

// A folder of the player's own, with wcmods.json naming a game folder (empty: not the game yet) and a saves
// folder, both made up, so the real game folder and the real save are never used, and a temp folder. Steam
// is still read (its registry key and library list, read only): once the made-up folder holds the game,
// Get set up and the Mods page say whether Steam starts another copy, and nothing here depends on the answer.
function dataFolder() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-"));
  const game = path.join(root, "Game"), saves = path.join(root, "Saves"), data = path.join(root, "data");
  const temp = path.join(root, "temp");
  for (const d of [game, saves, data, temp]) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(data, "wcmods.json"), JSON.stringify({ game_dir: game, save_dir: saves }));
  return { root, game, saves, data, temp };
}

function makeGame(game) {
  const win64 = path.join(game, "Wrc", "Binaries", "Win64");
  fs.mkdirSync(path.join(win64, "ue4ss", "Mods"), { recursive: true });
  fs.mkdirSync(path.join(game, "Wrc", "Content", "Paks"), { recursive: true });
  fs.writeFileSync(path.join(win64, EXE), "");
}

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
  if (folders) for (let i = 0; i < 5; i++) {
    try { fs.rmSync(folders.root, { recursive: true, force: true }); break; } catch (e) { await sleep(300); }
  }
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
  await page.waitFor(() => [...document.querySelectorAll(".target select option")].some(o => o.value === "e2e-mod"));
  assert.equal(await page.evaluate(() => document.querySelector(".target select").value), "e2e-mod");
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
