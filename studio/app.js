import * as wc from "./lib/wc.js";

const { el, api, clear, toast, bus } = wc;
const nav = document.getElementById("nav");
const main = document.getElementById("main");
const statusBox = document.getElementById("status");
const loaded = {};   // section id -> { pane, module, handle }
let info = null;
let active = null;

// A status chip. What it means (tip) shows on hover and keyboard focus, and screen readers hear it.
function chip(text, kind, tip) {
  return el("span", { class: `chip ${kind}`, "data-tip": tip || false, tabindex: tip ? "0" : false },
    el("i", { "aria-hidden": "true" }), text, tip ? el("span", { class: "sr-only", text: `: ${tip}` }) : null);
}
// The status is a live region: it's only redrawn when it says something new, so screen readers aren't
// told the same thing every few seconds.
let statusSaid = "";
function setStatus(chips) {
  const said = chips.map(c => `${c.className}|${c.textContent}`).join("\n");
  if (said === statusSaid) return;
  statusSaid = said;
  clear(statusBox).append(...chips);
}

const installBtn = document.getElementById("installBtn");
const playBtn = document.getElementById("playBtn");
let busy = false;   // a build, install or Play is running: the buttons wait for it

async function refreshStatus() {
  let changes = null;
  try {
    [info, changes] = await Promise.all([api.get("/info"), api.get("/changes").catch(() => null)]);
  } catch (e) {
    setStatus([chip("Studio server not reachable", "bad", e.message)]);
    return null;
  }
  const waiting = changes ? changes.on.length + changes.off.length + changes.changed.length + (changes.redo || []).length : 0;
  setStatus([
    chip(info.game_running ? "Game running" : "Game closed", info.game_running ? "warn" : "good",
      info.game_running ? "Close the game to apply mods" : ""),
    info.game_build && info.game_build.build && !info.game_build.verified
      ? chip("Game updated", "warn", `Build ${info.game_build.build}. Mods made for the older version are left out until they're updated; the Mods page says more.`)
      : null,
    info.ue4ss ? null : chip("No script loader", "warn", "Most mods need the script loader (UE4SS): Get set up, on the Mods page, installs it"),
    info.save_found ? null : chip("No save yet", "warn", "Start the game once, so there's a save"),
    info.code_changed
      ? chip("Restart the studio", "bad", "wcmods was updated while the studio was open. Close this window and open Clan Mod Studio again before applying.")
      : null,
    info.install_outdated
      ? chip("Apply again", "warn", "The installed mods were built by an older wcmods, and the game can't find their files. Apply to rebuild them.")
      : changes && changes.any
        ? chip(changes.installed ? `${waiting} change${waiting === 1 ? "" : "s"} to apply` : "Not applied yet", "warn", "Apply to game puts them in")
        // /changes reads wcmods.json afresh (an install from the command line shows at once); /info may not.
        : (changes ? changes.installed : info.installed)
          ? chip("Game up to date", "good")
          : chip("Nothing installed", ""),
  ].filter(Boolean));
  // Off while the game runs, before the game is found, and while one of them is working.
  const why = !info.game_dir ? "Find the game first: Get set up, on the Mods page" : info.game_running ? "Close the game first" : "";
  installBtn.disabled = !!why || busy;
  installBtn.title = why || "Build your mods and put them in the game";
  // Play applies what's waiting first, then starts the game (with key remaps, when mods have any).
  playBtn.disabled = !!why || busy;
  playBtn.textContent = info.game_running ? "Playing" : changes && changes.any ? "Apply and play" : "Play";
  playBtn.title = info.game_running ? "The game is running" : why || "Start the game" + (changes && changes.any ? ", after putting your changes in" : "");
  return info;
}

// The side bar: managing mods first, then the pages for making them. Made once; opening a page only
// moves aria-current, so the button you pressed keeps focus.
const GROUPS = { play: "Your mods", make: "Make mods" };
function renderNav() {
  if (!nav.childElementCount) {
    const rank = s => Object.keys(GROUPS).indexOf(s.group || "make");
    let last = null;
    for (const s of [...info.sections].sort((a, b) => rank(a) - rank(b))) {
      const g = s.group || "make";
      if (g !== last) {
        nav.append(el("span", { class: "nav-group", "aria-hidden": "true", text: GROUPS[g] || g }));
        last = g;
      }
      nav.append(el("button", { id: `nav-${s.id}`, onclick: () => open(s.id, true) },
        s.title, s.from_mod ? el("small", { text: "mod" }, el("span", { class: "sr-only", text: " page" })) : null));
    }
  }
  for (const b of nav.querySelectorAll("button")) {
    if (b.id === `nav-${active}`) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  }
}

// asked: the player chose the page (not the studio opening on it), so screen readers are told.
async function open(id, asked = false) {
  const spec = info.sections.find(s => s.id === id) || info.sections[0];
  active = spec.id;
  document.title = `${spec.title} · Clan Mod Studio`;
  if (asked) wc.announce(`${spec.title} page`);
  try { localStorage.setItem("wc-section", active); } catch (e) { /* storage blocked */ }
  try { history.replaceState(null, "", "#" + active); } catch (e) { /* ignore */ }
  renderNav();
  for (const [sid, entry] of Object.entries(loaded)) entry.pane.hidden = sid !== active;
  if (loaded[active]) return;
  const pane = el("div", { class: "section" }, el("p", { class: "muted", text: `Loading ${spec.title}…` }));
  main.append(pane);
  loaded[active] = { pane };
  try {
    const mod = await import(spec.module);
    const section = mod.default;
    clear(pane);
    loaded[spec.id].handle = await section.mount(pane, wc);
  } catch (e) {
    // Sections load independently: one failing doesn't take the others down.
    console.error(e);
    clear(pane).append(el("div", { class: "error-card" },
      el("h2", { text: `${spec.title} couldn't load` }),
      el("p", { text: e.message }),
      el("p", { class: "note", text: spec.from_mod ? `This page comes from the mod "${spec.from_mod}".` : "The other sections still work." }),
      el("button", { class: "btn", text: "Try again", onclick: () => { pane.remove(); delete loaded[spec.id]; open(spec.id, true); } })));
  }
}

// ---------- build / install ----------
// The log of an install shows in a panel; opening it takes focus there (its heading, then Close and
// the log), and closing it, with Close or Escape, puts focus back where it was.
const drawer = document.getElementById("drawer");
const drawerLog = document.getElementById("drawerLog");
const drawerTitle = document.getElementById("drawerTitle");
let drawerBack = null;
function showDrawer() {
  if (drawer.hidden) drawerBack = wc.keepPlace();
  drawer.hidden = false;
  drawerTitle.focus();
}
function hideDrawer() {
  if (drawer.hidden) return;
  const inside = drawer.contains(document.activeElement);
  drawer.hidden = true;
  if (inside && drawerBack) drawerBack();
}
document.getElementById("drawerClose").addEventListener("click", hideDrawer);
drawer.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); hideDrawer(); } });

function summarize(manifest) {
  const lines = [];
  for (const [sid, rep] of Object.entries(manifest.sections || {})) {
    if (!rep.mods.length && !rep.errors.length) continue;
    lines.push(`[${rep.status}] ${rep.title}: ${rep.mods.join(", ") || "no mods"}`);
    for (const e of rep.errors) lines.push(`    ${e}`);
  }
  for (const w of manifest.warnings || []) lines.push(`warning: ${w}`);
  return lines;
}

async function runTask(path, title, body = {}) {
  if (busy) return;
  busy = true;
  installBtn.disabled = playBtn.disabled = true;
  drawerTitle.textContent = title;
  showDrawer();
  drawerLog.textContent = "Working…";
  drawer.querySelector(".force")?.remove();
  try {
    const r = await api.post(path, body);
    const manifest = r.result && r.result.sections ? r.result : null;
    const lines = [...(manifest ? summarize(manifest) : []), "", ...r.log];
    drawerLog.textContent = lines.join("\n").trim() || "Done.";
    toast(path === "/play" ? "Starting the game…" : `${title}: done`);
    if (path === "/play") setTimeout(hideDrawer, 4000);
    bus.emit("installed", r.result);
    if (path === "/palettes/apply") bus.emit("mods-changed");   // it turned mods on and off
  } catch (e) {
    drawerLog.textContent = e.message;
    toast(e.message, "bad");
    if ((path === "/install" || path === "/play" || path === "/palettes/apply") && e.message.startsWith("not installing")) {
      drawer.append(el("div", { class: "row force", style: { padding: "0 14px 14px" } },
        wc.confirmButton("Apply the rest anyway", "Press again: the failed mods' earlier changes are removed",
          () => runTask(path, title, { ...body, force: true }), "btn danger")));
    }
  }
  busy = false;
  await refreshStatus();
}
installBtn.addEventListener("click", () => runTask("/install", "Apply to game"));
playBtn.addEventListener("click", () => runTask("/play", "Play"));
bus.on("apply", () => runTask("/install", "Apply to game"));
bus.on("run-task", ({ path, title, body }) => runTask(path, title, body));
bus.on("mods-changed", () => refreshStatus());

// ---------- boot ----------
wc.keepFocus();
// The skip link focuses the page without changing the address (#main isn't a section).
document.querySelector(".skip").addEventListener("click", e => { e.preventDefault(); main.focus(); });
(async () => {
  if (!await refreshStatus()) {
    main.append(el("div", { class: "error-card" }, el("h2", { text: "Can't reach the studio server" }),
      el("p", { text: "Start it with: python wcmods.py studio" })));
    return;
  }
  let first = location.hash.slice(1);
  if (!info.sections.some(s => s.id === first)) {
    try { first = localStorage.getItem("wc-section"); } catch (e) { first = null; }
  }
  await open(info.sections.some(s => s.id === first) ? first : info.sections[0].id);
  window.addEventListener("hashchange", () => {
    const id = location.hash.slice(1);
    if (id !== active && info.sections.some(s => s.id === id)) open(id);
  });
  setInterval(refreshStatus, 15000);
  await checkSetup();
  // Coming back to the studio (after the game, or after dropping a mod on its launcher): look again.
  window.addEventListener("focus", () => { refreshStatus(); checkSetup(); bus.emit("focus"); });
})();

// Whatever page is open: the first safety copy of the save as soon as there's one, and a mod dropped on
// the launcher, which the Mods page offers to add.
async function checkSetup() {
  let s;
  try { s = await api.get("/setup"); } catch (e) { return; }
  if (s.save.ok && !s.backup.ok) {
    try { if ((await api.post("/setup/backup")).name) toast("Made a safety copy of your save."); } catch (e) { /* the step stays undone */ }
  }
  if (s.inbox && active !== "mods" && info.sections.some(x => x.id === "mods")) await open("mods");
}
