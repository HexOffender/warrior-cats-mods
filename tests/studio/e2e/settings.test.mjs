// Settings and repair in a real browser (lib/browser.mjs), on a studio of its own (lib/studio.mjs): Back up now
// waits for a save, and the card of the game's last crash since the last Apply, there and on the Mods page until
// it's closed on either. The crash report
// is a made-up one in the layout Unreal writes, in the test's own crash folder (WCMODS_CRASHES). Skipped, with
// a reason, when no Chromium is found: set WC_BROWSER to one, or WC_REQUIRE_BROWSER=1 (as CI does) to fail
// instead of skipping.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { findBrowser, launch } from "../lib/browser.mjs";
import { dataFolder, makeGame, makeMod, removeFolders, startStudio } from "../lib/studio.mjs";

const browserPath = findBrowser();
const required = process.env.WC_REQUIRE_BROWSER === "1";
const skip = browserPath || required ? false : "no Chromium found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)";

let browser, studio, folders;

before(async () => {
  if (skip) return;
  if (!browserPath) throw new Error("WC_REQUIRE_BROWSER=1, and no Chromium was found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)");
  folders = dataFolder();
  makeGame(folders.game);
  // A C++ mod whose source is on the crash's stack.
  const mod = makeMod(folders.data, "my-tabs", { name: "My tabs" });
  fs.mkdirSync(path.join(mod, "cpp", "src"), { recursive: true });
  fs.writeFileSync(path.join(mod, "cpp", "src", "main.cpp"), "// the mod");
  const crash = path.join(folders.root, "Crashes", "UECC-Windows-1");
  fs.mkdirSync(crash, { recursive: true });
  fs.writeFileSync(path.join(crash, "CrashContext.runtime-xml"), `<?xml version="1.0" encoding="UTF-8"?>
<FGenericCrashContext><RuntimeProperties><CrashType>Crash</CrashType>
<ErrorMessage>Unhandled Exception: EXCEPTION_ACCESS_VIOLATION reading address 0x10</ErrorMessage>
<CallStack>main!MyTabs::on_draw() [${path.join(mod, "cpp", "src", "main.cpp")}:42]
Wrc_Win64_Shipping!UnknownFunction []</CallStack></RuntimeProperties></FGenericCrashContext>`, "utf16le");
  // An Apply an hour ago (wcmods.json's "crash_after", local time as Python writes it): the crash is since then.
  // Without one, a fresh folder shows no crash at all.
  const hourAgo = new Date(Date.now() - 3600e3);
  const local = new Date(hourAgo.getTime() - hourAgo.getTimezoneOffset() * 60000).toISOString().slice(0, 19);
  const conf = path.join(folders.data, "wcmods.json");
  fs.writeFileSync(conf, JSON.stringify({ ...JSON.parse(fs.readFileSync(conf, "utf8")), crash_after: local }));
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
  if (folders) await removeFolders(folders);
});

test("Back up now is disabled without a save", { skip }, async () => {
  const p = await browser.page();
  await p.goto(studio.url + "#settings");
  await p.waitFor(() => [...document.querySelectorAll("button")].some(b => b.textContent === "Back up now"));
  const backUp = () => p.evaluate(() => [...document.querySelectorAll("button")].find(b => b.textContent === "Back up now").disabled);
  assert.equal(await backUp(), true);
  assert.match(await p.text("#main"), /No save yet: start the game once and get into the forest\./);
  fs.writeFileSync(path.join(folders.saves, "WrcGame.sav"), "a save");
  await p.reload();
  await p.waitFor(() => [...document.querySelectorAll("button")].some(b => b.textContent === "Back up now" && !b.disabled));
  await p.click({ text: "Back up now" });
  await p.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => /^Backed up: Today \d\d:\d\d, backed up by you\./.test(t.textContent)));
  assert.deepEqual(p.consoleErrors(), []);
  await p.close();
});

test("the crash card offers Turn it off, Copy the report and Close, on Settings and repair and the Mods page", { skip }, async () => {
  const p = await browser.page();
  await p.goto(studio.url + "#settings");
  await p.waitFor(".banner.crash");
  assert.match(await p.text(".banner.crash"), /The game crashed last time.*EXCEPTION_ACCESS_VIOLATION.*It was in My tabs \(cpp\/src\/main\.cpp:42, MyTabs::on_draw\(\)\)\./s);
  assert.deepEqual(await p.evaluate(() => [...document.querySelectorAll(".banner.crash button")].map(b => b.textContent)),
    ["Copy the report", "Turn My tabs off", "Close"]);
  await p.click({ text: "Turn My tabs off" });
  await p.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.startsWith("My tabs is off.")));
  assert.equal(JSON.parse(fs.readFileSync(path.join(folders.data, "mods", "my-tabs", "mod.json"), "utf8")).enabled, false);
  // The Mods page shows it too, until it's closed there or here.
  await p.goto("about:blank");   // a fresh load: the page opens on the Mods page
  await p.goto(studio.url + "#mods");
  await p.waitFor("#mod-choose");
  await p.waitFor(".banner.crash");
  await p.click({ text: "Close" });
  await p.waitFor(() => !document.querySelector(".banner.crash"));
  await p.reload();
  await p.waitFor('[data-key="mod:my-tabs"]');
  assert.equal(await p.count(".banner.crash"), 0, "closed on the Mods page stays closed");
  await p.goto("about:blank");
  await p.goto(studio.url + "#settings");
  await p.waitFor(() => [...document.querySelectorAll("h2")].some(h => h.textContent === "Backups and repair"));
  assert.equal(await p.count(".banner.crash"), 0, "and on Settings and repair");
  // No card, and no "null" where it would be (the DOM's own append prints one).
  assert.doesNotMatch(await p.text("#main"), /\bnull\b/);
  assert.deepEqual(p.consoleErrors(), []);
  await p.close();
});
