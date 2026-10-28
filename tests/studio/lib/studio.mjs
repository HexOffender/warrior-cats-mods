// Clan Mod Studio for the end-to-end tests (e2e/): `python wcmods.py studio --no-browser --port 0` started from a
// copy of wcmods, on folders of the test's own (WCMODS_DATA, with a made-up game folder named in its
// wcmods.json, a saves folder and a temp folder), so neither Steam's game, the real save nor the repository's
// own folder is ever touched.
//
//   const { browserPath, skip } = e2eBrowser();
//   const release = await takeTurn();           // in `before`: one end-to-end file at a time
//   const folders = dataFolder();
//   const studio = await startStudio(folders);   // studio.url, studio.stop()
//   await removeFolders(folders);                // in `after`, then release()
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";
import { findBrowser } from "./browser.mjs";
import { REPO } from "./dom.mjs";

export const EXE = "Wrc-Win64-ShippingDRM.exe";   // config.EXE_NAME: what makes a folder the game's
export const sleep = ms => new Promise(r => setTimeout(r, ms));

// The browser the tests drive, and whether they skip: without one they skip, saying so, unless
// WC_REQUIRE_BROWSER=1 (as CI sets), when needBrowser() in `before` fails them instead.
export function e2eBrowser() {
  const browserPath = findBrowser();
  const required = process.env.WC_REQUIRE_BROWSER === "1";
  return { browserPath, skip: browserPath || required ? false : "no Chromium found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)" };
}
export function needBrowser(browserPath) {
  if (!browserPath) throw new Error("WC_REQUIRE_BROWSER=1, and no Chromium was found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)");
}

// The end-to-end files take turns: node --test runs files side by side, and two studios with a Chromium each
// make a small machine slow enough for the tests' waits to run out. Each file holds this lock from its `before`
// to its `after` (takeTurn() resolves to the release); the holder touches it every few seconds while it holds
// it. A lock that's stale is taken over: its process is gone, it's empty (written by a run that died before it
// said who it was), or nobody has touched it for STALE_MS (a run that hangs). One that stays held longer than
// `wait` ms (WC_E2E_LOCK_WAIT_MIN minutes, 20 by default) gives up with an error that names the lock.
export const LOCK = path.join(os.tmpdir(), "wc-studio-e2e.lock");
const STALE_MS = 10 * 60 * 1000, TOUCH_MS = 10 * 1000, EMPTY_MS = 5 * 1000;
export async function takeTurn({ lock = LOCK, wait = Number(process.env.WC_E2E_LOCK_WAIT_MIN || 20) * 60 * 1000 } = {}) {
  const alive = pid => { try { process.kill(pid, 0); return true; } catch (e) { return e.code === "EPERM"; } };
  const end = Date.now() + wait;
  for (;;) {
    try {
      fs.writeFileSync(lock, String(process.pid), { flag: "wx" });
      const touch = setInterval(() => { try { const now = new Date(); fs.utimesSync(lock, now, now); } catch (e) { /* gone */ } }, TOUCH_MS);
      touch.unref();
      return () => {
        clearInterval(touch);
        try { if (fs.readFileSync(lock, "utf8") === String(process.pid)) fs.rmSync(lock); } catch (e) { /* gone */ }
      };
    } catch (e) {
      if (e.code !== "EEXIST") throw e;
      let text = null, age = 0;
      try { text = fs.readFileSync(lock, "utf8").trim(); age = Date.now() - fs.statSync(lock).mtimeMs; } catch (e2) { continue; /* just removed */ }
      const pid = Number(text);
      const stale = (text === "" && age > EMPTY_MS) || (pid > 0 && !alive(pid)) || (text !== "" && !(pid > 0)) || age > STALE_MS;
      if (stale) { try { fs.rmSync(lock); } catch (e2) { /* another took it over */ } continue; }
      if (Date.now() > end) {
        throw new Error(`waited ${wait >= 60000 ? `${Math.round(wait / 60000)} minutes` : `${Math.round(wait / 1000)} s`} for the end-to-end tests' lock ${lock}, held by process ${text || "(none written)"}; ` +
          "if no other test run is going, delete that file");
      }
      await sleep(200);
    }
  }
}

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
// folder, both made up, so the real game folder and the real save are never used, and a temp folder. Steam
// is still read (its registry key and library list, read only): once the made-up folder holds the game,
// Get set up and the Mods page say whether Steam starts another copy, and nothing here depends on the answer.
export function dataFolder() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-"));
  const game = path.join(root, "Game"), saves = path.join(root, "Saves"), data = path.join(root, "data");
  const temp = path.join(root, "temp");
  for (const d of [game, saves, data, temp]) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(data, "wcmods.json"), JSON.stringify({ game_dir: game, save_dir: saves }));
  return { root, game, saves, data, temp, app: appCopy() };
}

export async function remove(folder) {
  for (let i = 0; i < 5; i++) {
    try { fs.rmSync(folder, { recursive: true, force: true }); return; } catch (e) { await sleep(300); }
  }
}
// The test's folders and its copy of wcmods.
export async function removeFolders(folders) {
  await remove(folders.root);
  await remove(folders.app);
}

// The made-up game folder becomes one the studio takes for the game: the exe and its folders, no paks.
export function makeGame(game) {
  const win64 = path.join(game, "Wrc", "Binaries", "Win64");
  fs.mkdirSync(path.join(win64, "ue4ss", "Mods"), { recursive: true });
  fs.mkdirSync(path.join(game, "Wrc", "Content", "Paks"), { recursive: true });
  fs.writeFileSync(path.join(win64, EXE), "");
}

// A small PNG of one colour, w x h, to choose as a picture.
export function pngFile(file, w = 32, h = 32, rgba = [200, 60, 160, 255]) {
  const chunk = (type, data) => {
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const out = Buffer.alloc(12 + data.length);
    out.writeUInt32BE(data.length, 0);
    body.copy(out, 4);
    out.writeUInt32BE(zlib.crc32(body), 8 + data.length);
    return out;
  };
  const head = Buffer.alloc(13);
  head.writeUInt32BE(w, 0); head.writeUInt32BE(h, 4); head[8] = 8; head[9] = 6;
  const row = Buffer.concat([Buffer.from([0]), Buffer.from(Array.from({ length: w }, () => rgba).flat())]);
  const raw = Buffer.concat(Array.from({ length: h }, () => row));
  fs.writeFileSync(file, Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", head),
    chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]));
  return file;
}
