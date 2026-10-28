// The Mod packs page in a real browser (lib/browser.mjs), on a studio of its own (lib/studio.mjs): the form keeps
// what's typed when the page redraws, a pack with a missing mod lists it as dropped when changed, and a new
// pack doesn't start with your own tools ticked. Skipped, with a reason, when no Chromium is found: set
// WC_BROWSER to one, or WC_REQUIRE_BROWSER=1 (as CI does) to fail instead of skipping.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { findBrowser, launch } from "../lib/browser.mjs";
import { dataFolder, makeGame, makeMod, removeFolder, startStudio } from "../lib/studio.mjs";

const browserPath = findBrowser();
const required = process.env.WC_REQUIRE_BROWSER === "1";
const skip = browserPath || required ? false : "no Chromium found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)";

let browser, studio, folders;

before(async () => {
  if (skip) return;
  if (!browserPath) throw new Error("WC_REQUIRE_BROWSER=1, and no Chromium was found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)");
  folders = dataFolder();
  makeGame(folders.game);
  makeMod(folders.data, "alpha", { name: "Alpha" });
  makeMod(folders.data, "menu-pages", { name: "Menu pages" });   // one of your own tools: stays on whatever pack plays
  makeMod(folders.data, "moon", { name: "Moon", pack: true, requires: ["alpha", "ghost"], enabled: false });
  studio = await startStudio(folders);
  browser = await launch({ browser: browserPath });
  const first = await browser.page();
  await first.goto(studio.url, { timeout: 60000 });
  await first.waitFor("#nav button", 60000);
  await first.close();
});

after(async () => {
  if (studio) studio.stop();
  if (browser) await browser.close();
  if (folders) await removeFolder(folders.root);
});

const ticked = p => p.evaluate(() => [...document.querySelectorAll('[data-key="pack-form"] input[type="checkbox"]')].filter(b => b.checked).map(b => b.getAttribute("aria-label")));

test("the pack form keeps typed text across a redraw, and starts without your own tools ticked", { skip }, async () => {
  const p = await browser.page();
  await p.goto(studio.url + "#packs");
  await p.waitFor('input[aria-label="Pack name"]');
  assert.deepEqual(await ticked(p), ["Alpha"], "the mods you have on, but Menu pages");
  await p.type('input[aria-label="Pack name"]', "The Moonlit Path");
  await p.type('textarea[aria-label="Description"]', "A walk by night.");
  await p.click('input[aria-label="Menu pages"]');
  // Another page changes a mod: every page hears it, and this one draws its form again.
  await p.evaluate(async () => { (await import("/studio/lib/wc.js")).bus.emit("mods-changed"); return true; });
  await p.waitFor(() => document.querySelector('input[aria-label="Pack name"]') && !document.querySelector('input[aria-label="Pack name"]').matches(":focus"));
  assert.equal(await p.evaluate(() => document.querySelector('input[aria-label="Pack name"]').value), "The Moonlit Path");
  assert.equal(await p.evaluate(() => document.querySelector('textarea[aria-label="Description"]').value), "A walk by night.");
  assert.deepEqual(await ticked(p), ["Alpha", "Menu pages"]);
  assert.deepEqual(p.consoleErrors(), []);
  await p.close();
});

test("Change it with a missing mod lists it as dropped", { skip }, async () => {
  const p = await browser.page();
  await p.goto(studio.url + "#packs");
  await p.waitFor('[data-key="pack:moon"]');
  assert.match(await p.text('[data-key="pack:moon"]'), /Missing: ghost\./);
  await p.click({ text: "Change it" });
  await p.waitFor('[data-key="dropped"]');
  assert.equal(await p.text('[data-key="dropped"]'), "Not in your mods: ghost. It's dropped from the pack when you save.");
  assert.deepEqual(await ticked(p), ["Alpha"], "only the mods that are here");
  await p.click({ text: "Save the pack" });
  await p.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.startsWith("Saved Moon.")));
  await p.waitFor(() => !document.querySelector('[data-key="pack:moon"]').textContent.includes("Missing"));
  assert.deepEqual(p.consoleErrors(), []);
  await p.close();
});
