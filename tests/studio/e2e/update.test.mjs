// After a game update, on the Mods page in a real browser (lib/browser.mjs): the banner that says which mods are
// left out, on the build wcmods was checked on too, and the re-check of the held-back data mods, started once
// per visit to the page. The made-up game's files can't be read, so the re-check says it couldn't check.
// Skipped, with a reason, when no Chromium is found: set WC_BROWSER to one, or WC_REQUIRE_BROWSER=1 (as CI
// does) to fail instead of skipping.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { launch } from "../lib/browser.mjs";

import { browserChoice, dataFolder, makeGame, makeMod, removeFolders, requireBrowser, startStudio, takeTurn } from "../lib/studio.mjs";

const { browserPath, skip } = browserChoice();
const VERIFIED = 26184573;   // gamebuild.VERIFIED_BUILD

let browser, verified, newer, verifiedFolders, newerFolders, release;

// Every request the page makes, and whether the re-check's line was ever on it, from the page's first moment.
const WATCH = `
  window.calls = [];
  const real = window.fetch;
  window.fetch = (url, init) => { window.calls.push(\`\${(init && init.method) || "GET"} \${url}\`); return real(url, init); };
  new MutationObserver(() => {
    if (document.body && document.body.textContent.includes("Checking your mods on the new version")) window.sawChecking = true;
    if (document.getElementById("status")?.textContent.includes("Checking your mods on the new version")) window.sawChip = true;
  }).observe(document, { childList: true, subtree: true, characterData: true });`;

before(async () => {
  if (skip) return;
  requireBrowser(browserPath);
  release = await takeTurn();   // one end-to-end file at a time
  // On the verified build: a script mod made for an older build (left out; only its maker can vouch for it), and
  // a mod whose game_builds holds no build number.
  verifiedFolders = dataFolder();
  makeGame(verifiedFolders.game);
  const script = makeMod(verifiedFolders.data, "old-script", { name: "Old script", game_builds: [1] });
  fs.mkdirSync(path.join(script, "scripts"));
  fs.writeFileSync(path.join(script, "scripts", "main.lua"), "print(1)");
  makeMod(verifiedFolders.data, "typo", { name: "Typo", game_builds: ["soon"] });
  // On a newer build: a palette made for the verified one, which the re-check tries.
  newerFolders = dataFolder();
  makeGame(newerFolders.game);
  const palette = makeMod(newerFolders.data, "dark-forest", { name: "Dark Forest", game_builds: [VERIFIED] });
  fs.writeFileSync(path.join(palette, "palette.json"), JSON.stringify({ fur: { 3: "#112233" } }));
  verified = await startStudio(verifiedFolders, { WCMODS_GAME_BUILD: String(VERIFIED) });
  newer = await startStudio(newerFolders, { WCMODS_GAME_BUILD: "99999999" });
  browser = await launch({ browser: browserPath });
  const first = await browser.page();
  await first.goto(verified.url, { timeout: 60000 });
  await first.waitFor("#nav button", 60000);
  await first.close();
});

after(async () => {
  for (const s of [verified, newer]) if (s) s.stop();
  if (browser) await browser.close();
  for (const f of [verifiedFolders, newerFolders]) if (f) await removeFolders(f);
  if (release) release();
});

test("the update banner shows on the verified build when a mod is left out", { skip }, async () => {
  const p = await browser.page();
  await p.goto(verified.url + "#mods");
  await p.waitFor(() => [...document.querySelectorAll(".banner strong")].some(s => s.textContent === "Some mods are left out on this version of the game"));
  const banner = await p.evaluate(() => [...document.querySelectorAll(".banner")].find(b => b.textContent.includes("left out on this version")).textContent);
  assert.match(banner, /Old script was made for the older version and can't be checked here \(code, or the game's own kind of files\): its maker has to update it/);
  assert.match(await p.text('[data-key="mod:old-script"] .notes'), /its maker has to update it|left out until it's updated/);
  assert.equal(await p.count('[data-key="mod:old-script"] button[aria-label="Use Old script anyway…"]'), 1);
  assert.match(await p.text('[data-key="mod:typo"] .notes'), /Mod\.json's game_builds should be a list of build numbers like \[26184573\]\./);
  assert.deepEqual(p.consoleErrors(), []);
  await p.close();
});

test("a recheck_due page starts the check once and shows its progress", { skip }, async () => {
  const p = await browser.page();
  await p.send("Page.addScriptToEvaluateOnNewDocument", { source: WATCH });
  await p.goto(newer.url + "#mods");
  await p.waitFor(() => document.body.textContent.includes("Dark Forest couldn't be checked on the new version"), 30000);
  assert.equal(await p.evaluate(() => window.sawChecking === true), true, "the banner said it was checking");
  assert.equal(await p.evaluate(() => window.sawChip === true), true, "the status at the top said so too");
  const config = JSON.parse(fs.readFileSync(path.join(newerFolders.data, "wcmods.json"), "utf8"));
  assert.equal(config.rechecked.build, 99999999);
  assert.match(config.rechecked.results["dark-forest"], /^couldn't check: the game's files can't be read right now/);
  // The page asked once; looking again doesn't ask again (the next visit to the page does).
  await p.click({ text: "look again" });
  await p.waitFor(() => window.calls.filter(c => c === "GET /api/changes").length >= 2);
  assert.equal(await p.evaluate(() => window.calls.filter(c => c === "POST /api/mods/recheck").length), 1);
  assert.deepEqual(p.consoleErrors(), []);
  await p.close();
});
