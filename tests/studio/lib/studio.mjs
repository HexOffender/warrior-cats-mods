// The studio for the end-to-end tests: `python wcmods.py studio --no-browser --port 0` on a folder of its own
// (WCMODS_DATA, with a made-up game folder named in its wcmods.json), so neither Steam's game nor the real save
// is ever looked at.
//
//   const folders = dataFolder();                  // root, game, saves, data
//   fixtureGame(folders);                          // the made-up game with a few tables, and the tests' save
//   const studio = await startStudio(folders.data);
//   ... studio.url ...
//   studio.stop(); removeFolder(folders.root);
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { REPO } from "./dom.mjs";

export const EXE = "Wrc-Win64-ShippingDRM.exe";   // config.EXE_NAME: what makes a folder the game's
const sleep = ms => new Promise(r => setTimeout(r, ms));
const python = () => process.env.PYTHON || "python";

// A studio started on a free port over `data`; its URL is on the first line it prints.
export async function startStudio(data, env = {}) {
  const proc = spawn(python(), ["-I", "wcmods.py", "studio", "--no-browser", "--port", "0"],
    { cwd: REPO, env: { ...process.env, WCMODS_DATA: data, ...env }, stdio: ["ignore", "pipe", "pipe"] });
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
// folder, both made up.
export function dataFolder() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-"));
  const game = path.join(root, "Game"), saves = path.join(root, "Saves"), data = path.join(root, "data");
  for (const d of [game, saves, data]) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(data, "wcmods.json"), JSON.stringify({ game_dir: game, save_dir: saves }));
  return { root, game, saves, data };
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

// Read the save the studio wrote, as JSON (through wcmods' own codec).
export function readSave(saves) {
  const code = "import sys, json; sys.path.insert(0, sys.argv[1]); from wcmods.formats.save import SaveGame; " +
    "print(SaveGame.load(sys.argv[2]).json_text)";
  const r = spawnSync(python(), ["-I", "-c", code, REPO, path.join(saves, "WrcGame.sav")], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}
