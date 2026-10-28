// What the end-to-end tests share: a Clan Mod Studio started over a folder of the test's own, from a copy of
// wcmods of its own, that folder, and a made-up game folder. Each e2e file starts one studio (startStudio)
// on a free port and drives it with lib/browser.mjs.
//
//   const folders = dataFolder();
//   const studio = await startStudio(folders);    // studio.url, studio.stop()
//   makeGame(folders.game);                        // the folder holds "the game" now
//   writeMod(folders, "my-mod", { name: "My mod" }, { "npcs.json": {...} });
//   await removeFolders(folders);                  // at the end
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { findBrowser } from "./browser.mjs";
import { REPO } from "./dom.mjs";

export const EXE = "Wrc-Win64-ShippingDRM.exe";   // config.EXE_NAME: what makes a folder the game's
export const sleep = ms => new Promise(r => setTimeout(r, ms));

// The browser to drive, and the reason to skip when there's none (WC_REQUIRE_BROWSER=1, as CI sets, fails instead).
export const browserPath = findBrowser();
export const required = process.env.WC_REQUIRE_BROWSER === "1";
export const skip = browserPath || required ? false : "no Chromium found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)";

// wcmods as the studio runs it (wcmods.py, wcmods/, studio/ and docs/), copied to a folder of its own. Started
// from the repository, the studio would take it for wcmods' folder and move a mods/, wcmods.json or backups/
// kept there (a supported way to keep them) into the test's folder, which is deleted.
export function appCopy() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-app-"));
  const skipCache = src => !src.split(path.sep).includes("__pycache__");
  for (const d of ["wcmods", "studio", "docs"]) fs.cpSync(path.join(REPO, d), path.join(root, d), { recursive: true, filter: skipCache });
  fs.copyFileSync(path.join(REPO, "wcmods.py"), path.join(root, "wcmods.py"));
  return root;
}

// A studio started over the test's folders (on a free port, or `port`), from `root` (a copy of wcmods, the
// folders' own unless said); its URL is on the first line it prints. The game counts as closed
// (WCMODS_FAKE_RUNNING=0) unless `env` says otherwise, whether or not the real one is running on this machine;
// its temp folder (the inbox a dropped mod waits in) is the test's, not the one a studio of the player's would
// share.
export async function startStudio(folders, env = {}, { root = folders.app, port = 0 } = {}) {
  const python = process.env.PYTHON || "python";
  const own = { ...process.env, WCMODS_DATA: folders.data, WCMODS_FAKE_RUNNING: "0", TEMP: folders.temp, TMP: folders.temp,
    TMPDIR: folders.temp, ...env };
  delete own.WCMODS_GAME_BUILD;   // a build number a developer set to try an update
  const proc = spawn(python, ["-I", "wcmods.py", "studio", "--no-browser", "--port", String(port)],
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

// A folder of the player's own, with wcmods.json naming a game folder (empty: not the game yet) and a saves
// folder, both made up, so the real game folder and the real save are never used, a temp folder, and a copy
// of wcmods to run the studio from. `settings` go in wcmods.json too. Steam is still read (its registry key
// and library list, read only): once the made-up folder holds the game, Get set up and the Mods page say
// whether Steam starts another copy, and nothing here depends on the answer.
export function dataFolder(settings = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-"));
  const game = path.join(root, "Game"), saves = path.join(root, "Saves"), data = path.join(root, "data");
  const temp = path.join(root, "temp");
  for (const d of [game, saves, data, temp]) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(data, "wcmods.json"), JSON.stringify({ game_dir: game, save_dir: saves, ...settings }));
  return { root, game, saves, data, temp, app: appCopy() };
}

// The folder holds the game now: its exe, UE4SS's mods folder and the paks folder (no paks).
export function makeGame(game) {
  const win64 = path.join(game, "Wrc", "Binaries", "Win64");
  fs.mkdirSync(path.join(win64, "ue4ss", "Mods"), { recursive: true });
  fs.mkdirSync(path.join(game, "Wrc", "Content", "Paks"), { recursive: true });
  fs.writeFileSync(path.join(win64, EXE), "");
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

// Remove a folder, trying again while a studio that used it lets go of its files.
export async function remove(folder) {
  for (let i = 0; i < 5; i++) {
    try { fs.rmSync(folder, { recursive: true, force: true }); return; } catch (e) { await sleep(300); }
  }
}
// The test's folders and its copy of wcmods.
export async function removeFolders(folders) {
  if (!folders) return;
  await remove(folders.root);
  await remove(folders.app);
}
