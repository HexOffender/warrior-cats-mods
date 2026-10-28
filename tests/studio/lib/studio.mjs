// What the end-to-end tests (e2e/*.test.mjs) share: a Clan Mod Studio, `python wcmods.py studio --no-browser
// --port 0`, started over folders of the test's own (WCMODS_DATA, with a made-up game folder and saves folder named
// in its wcmods.json, and a temp folder), so the real game folder and the real save are never used, run from a
// copy of wcmods of its own, and the browser that drives it (lib/browser.mjs).
//
//   const folders = dataFolder();                  // root, game, saves, data, temp, app (a copy of wcmods)
//   const studio = await startStudio(folders);    // studio.url, studio.stop()
//   makeGame(folders.game);                        // the folder holds "the game" now (no paks), or
//   fixtureGame(folders);                          // the made-up game with a few tables, and the tests' save
//   writeMod(folders, "my-mod", { name: "My mod" }, { "npcs.json": {...} });
//   await removeFolders(folders);                  // at the end (removeFolder(folders.root) does as well)
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { findBrowser } from "./browser.mjs";
import { REPO } from "./dom.mjs";

export const EXE = "Wrc-Win64-ShippingDRM.exe";   // config.EXE_NAME: what makes a folder the game's
export const sleep = ms => new Promise(r => setTimeout(r, ms));
const python = () => process.env.PYTHON || "python";

// The Chromium to drive, and the reason to skip when there's none: none found skips the tests, unless
// WC_REQUIRE_BROWSER=1 (as CI does), when they fail instead (each file's `before` throws on browserPath null).
export function browserChoice() {
  const browserPath = findBrowser();
  const required = process.env.WC_REQUIRE_BROWSER === "1";
  return { browserPath, skip: browserPath || required ? false : "no Chromium found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)" };
}
export const NO_BROWSER = "WC_REQUIRE_BROWSER=1, and no Chromium was found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)";
// The same, found once for a file: `browserPath` (null when there's none), `skip` (the reason, or false).
export const { browserPath, skip } = browserChoice();
export const required = process.env.WC_REQUIRE_BROWSER === "1";

// wcmods as the studio runs it (wcmods.py, wcmods/, studio/ and docs/), copied into `root`/app (a folder of its
// own when no root is given). Started from the repository, the studio would take it for wcmods' folder and move
// a mods/, wcmods.json or backups/ kept there (a supported way to keep them) into the test's folder, which is
// deleted.
export function appCopy(root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-app-"))) {
  const app = path.join(root, "app");
  const skipCache = src => !src.split(path.sep).includes("__pycache__");
  for (const d of ["wcmods", "studio", "docs"]) fs.cpSync(path.join(REPO, d), path.join(app, d), { recursive: true, filter: skipCache });
  fs.copyFileSync(path.join(REPO, "wcmods.py"), path.join(app, "wcmods.py"));
  return app;
}

// A studio started over the test's folders (on a free port, or `port`), from `root` (a copy of wcmods, the
// folders' own unless said); its URL is on the first line it prints. The game counts as closed
// (WCMODS_FAKE_RUNNING=0) unless `env` says otherwise, whether or not the real one is running on this machine;
// its temp folder (the inbox a dropped mod waits in) is the test's, not the one a studio of the player's would
// share.
export async function startStudio(folders, env = {}, { root = folders.app, port = 0 } = {}) {
  const own = { ...process.env, WCMODS_DATA: folders.data, WCMODS_FAKE_RUNNING: "0", TEMP: folders.temp, TMP: folders.temp,
    TMPDIR: folders.temp, ...env };
  delete own.WCMODS_GAME_BUILD;   // a build number a developer set to try an update
  const proc = spawn(python(), ["-I", "wcmods.py", "studio", "--no-browser", "--port", String(port)],
    { cwd: root, env: own, stdio: ["ignore", "pipe", "pipe"] });
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

// A first load, with time to spare: a cold browser and studio have taken 15 s on CI, and every test's own
// waits are 10 s.
export async function warmUp(browser, url) {
  const page = await browser.page();
  await page.goto(url, { timeout: 60000 });
  await page.waitFor("#nav button", 60000);
  await page.close();
}

// A folder of the player's own, with wcmods.json naming a game folder (empty: not the game yet) and a saves
// folder, both made up, so the real game folder and the real save are never used, a temp folder, and a copy
// of wcmods to run the studio from. `settings` go in wcmods.json too. Steam is still read (its registry key
// and library list, read only): once the made-up folder holds the game, Get set up and the Mods page say
// whether Steam starts another copy, and nothing here depends on the answer.
// `app` is the copy of wcmods a studio over these folders runs from, inside `root`: removing root takes it too.
export function dataFolder(settings = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-"));
  const game = path.join(root, "Game"), saves = path.join(root, "Saves"), data = path.join(root, "data");
  const temp = path.join(root, "temp");
  for (const d of [game, saves, data, temp]) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(data, "wcmods.json"), JSON.stringify({ game_dir: game, save_dir: saves, ...settings }));
  return { root, game, saves, data, temp, app: appCopy(root) };
}

// The folder holds the game now: its exe, UE4SS's mods folder and the paks folder (no paks).
export function makeGame(game) {
  const win64 = path.join(game, "Wrc", "Binaries", "Win64");
  fs.mkdirSync(path.join(win64, "ue4ss", "Mods"), { recursive: true });
  fs.mkdirSync(path.join(game, "Wrc", "Content", "Paks"), { recursive: true });
  fs.writeFileSync(path.join(win64, EXE), "");
}

// WrcGame.sav holding `data` (the save's JSON) in the saves folder, as the game lays it out (through wcmods'
// own writer, the one tests/unit/unit_helpers.py's write_save uses).
export function writeSave(saves, data) {
  const code = "import os, sys; sys.path.insert(0, sys.argv[1]); from wcmods.selftest import _small_save; " +
    "from wcmods.formats.save import SAV_NAME; open(os.path.join(sys.argv[2], SAV_NAME), 'wb').write(_small_save(sys.argv[3]))";
  const r = spawnSync(python(), ["-I", "-c", code, REPO, saves, JSON.stringify(data)], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`couldn't write the save: ${r.stderr}`);
}

// A mod in the player's mods folder: mod.json (on, unless `meta` says) and files ({name: text or JSON-able}).
export function writeMod(folders, id, meta = {}, files = {}) {
  const dir = path.join(folders.data, "mods", id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "mod.json"), JSON.stringify({ name: id, enabled: true, ...meta }));
  for (const [name, value] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(dir, name)), { recursive: true });
    fs.writeFileSync(path.join(dir, name), typeof value === "string" ? value : JSON.stringify(value, null, 2));
  }
  return dir;
}
export const readJson = file => JSON.parse(fs.readFileSync(file, "utf8"));

// Remove a folder, trying again while a studio that used it lets go of its files (Windows).
export async function remove(folder) {
  for (let i = 0; i < 5; i++) {
    try { fs.rmSync(folder, { recursive: true, force: true }); return; } catch (e) { await sleep(300); }
  }
}
export const removeFolder = remove;
// A dataFolder's folders, with the copy of wcmods its studios ran from.
export async function removeFolders(folders) {
  if (!folders) return;
  await remove(folders.root);
  if (folders.app && fs.existsSync(folders.app)) await remove(folders.app);   // a copy made outside root
}

// The made-up game with a few of the game's tables (tests/studio/fixtures/game.py) and, with saves, the tests'
// save (your cat in slot 1, level 5, 62 in the fresh-kill pile, two herbs and four moss).
export function fixtureGame({ game, saves }) {
  const args = ["-I", path.join(REPO, "tests", "studio", "fixtures", "game.py"), game, ...(saves ? [saves] : [])];
  const r = spawnSync(python(), args, { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`the made-up game wasn't made: ${r.stdout}${r.stderr}`);
}

// The save the studio wrote, as JSON (through wcmods' own codec).
export function readSave(saves) {
  const code = "import sys, json; sys.path.insert(0, sys.argv[1]); from wcmods.formats.save import SaveGame; " +
    "print(SaveGame.load(sys.argv[2]).json_text)";
  const r = spawnSync(python(), ["-I", "-c", code, REPO, path.join(saves, "WrcGame.sav")], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}
