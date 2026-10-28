// The studio for the end-to-end tests: `python wcmods.py studio --no-browser --port 0` on folders of its own
// (WCMODS_DATA, with a made-up game folder named in its wcmods.json), so neither Steam's game nor the real save
// is ever used.
//
//   const folders = dataFolder();                  // root, game, saves, data, temp
//   fixtureGame(folders);                          // the made-up game with a few tables, and the tests' save
//   const studio = await startStudio(folders);
//   ... studio.url ...
//   studio.stop(); await removeFolder(folders.root);
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { REPO } from "./dom.mjs";

export const EXE = "Wrc-Win64-ShippingDRM.exe";   // config.EXE_NAME: what makes a folder the game's
const sleep = ms => new Promise(r => setTimeout(r, ms));
const python = () => process.env.PYTHON || "python";

// A studio started on a free port over the test's folders; its URL is on the first line it prints. The game
// counts as closed (WCMODS_FAKE_RUNNING=0) unless `env` says otherwise, whether or not the real one is running
// on this machine; its temp folder (the inbox a dropped mod waits in) is the test's, not the one a studio of
// the player's would share.
export async function startStudio(folders, env = {}) {
  const own = { ...process.env, WCMODS_DATA: folders.data, WCMODS_FAKE_RUNNING: "0", TEMP: folders.temp, TMP: folders.temp,
    TMPDIR: folders.temp, ...env };
  delete own.WCMODS_GAME_BUILD;   // a build number a developer set to try an update
  const proc = spawn(python(), ["-I", "wcmods.py", "studio", "--no-browser", "--port", "0"],
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
export function dataFolder() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-"));
  const game = path.join(root, "Game"), saves = path.join(root, "Saves"), data = path.join(root, "data");
  const temp = path.join(root, "temp");
  for (const d of [game, saves, data, temp]) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(data, "wcmods.json"), JSON.stringify({ game_dir: game, save_dir: saves }));
  return { root, game, saves, data, temp };
}

// The game's folder as config.is_game_dir knows one: the exe and the folders, no paks (nothing to read).
export function makeGame(game) {
  const win64 = path.join(game, "Wrc", "Binaries", "Win64");
  fs.mkdirSync(path.join(win64, "ue4ss", "Mods"), { recursive: true });
  fs.mkdirSync(path.join(game, "Wrc", "Content", "Paks"), { recursive: true });
  fs.writeFileSync(path.join(win64, EXE), "");
}

// The made-up game with a few of the game's tables (tests/studio/fixtures/game.py) and, with saves, the tests'
// save (your cat in slot 1, level 5, 62 in the fresh-kill pile, two herbs and four moss).
export function fixtureGame({ game, saves }) {
  const args = ["-I", path.join(REPO, "tests", "studio", "fixtures", "game.py"), game, ...(saves ? [saves] : [])];
  const r = spawnSync(python(), args, { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`the made-up game wasn't made: ${r.stdout}${r.stderr}`);
}

export async function removeFolder(root) {
  for (let i = 0; i < 5; i++) {
    try { fs.rmSync(root, { recursive: true, force: true }); return; } catch (e) { await sleep(300); }
  }
}

// The save the studio wrote, as JSON (through wcmods' own codec).
export function readSave(saves) {
  const code = "import sys, json; sys.path.insert(0, sys.argv[1]); from wcmods.formats.save import SaveGame; " +
    "print(SaveGame.load(sys.argv[2]).json_text)";
  const r = spawnSync(python(), ["-I", "-c", code, REPO, path.join(saves, "WrcGame.sav")], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}
