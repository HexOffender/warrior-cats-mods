import * as wc from "./lib/wc.js";

const { el, api, clear, toast, bus } = wc;
const nav = document.getElementById("nav");
const main = document.getElementById("main");
const statusBox = document.getElementById("status");
const loaded = {};   // section id -> { pane, module, handle }
let info = null;
let active = null;

function chip(text, kind, title) {
  return el("span", { class: `chip ${kind}`, title: title || false }, el("i"), text);
}

const installBtn = document.getElementById("installBtn");

async function refreshStatus() {
  let changes = null;
  try {
    [info, changes] = await Promise.all([api.get("/info"), api.get("/changes").catch(() => null)]);
  } catch (e) {
    clear(statusBox).append(chip("Studio server not reachable", "bad", e.message));
    return null;
  }
  const waiting = changes ? changes.on.length + changes.off.length + changes.changed.length : 0;
  clear(statusBox).append(...[
    chip(info.game_running ? "Game running" : "Game closed", info.game_running ? "warn" : "good",
      info.game_running ? "Close the game to apply mods" : ""),
    info.ue4ss ? null : chip("No UE4SS", "warn", "The mod menu, mouse look, colours on your own cat and in-game scripts need UE4SS"),
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
  installBtn.disabled = info.game_running;
  installBtn.title = info.game_running ? "Close the game first" : "Build your mods and put them in the game";
  return info;
}

// The side bar: managing mods first, then the pages for making them.
const GROUPS = { play: "Your mods", make: "Make mods" };
function renderNav() {
  clear(nav);
  const rank = s => Object.keys(GROUPS).indexOf(s.group || "make");
  let last = null;
  for (const s of [...info.sections].sort((a, b) => rank(a) - rank(b))) {
    const g = s.group || "make";
    if (g !== last) {
      nav.append(el("span", { class: "nav-group", text: GROUPS[g] || g }));
      last = g;
    }
    nav.append(el("button", {
      id: `nav-${s.id}`, "aria-current": active === s.id ? "page" : false,
      onclick: () => open(s.id),
    }, s.title, s.from_mod ? el("small", { text: "mod" }) : null));
  }
}

async function open(id) {
  const spec = info.sections.find(s => s.id === id) || info.sections[0];
  active = spec.id;
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
      el("button", { class: "btn", text: "Try again", onclick: () => { pane.remove(); delete loaded[spec.id]; open(spec.id); } })));
  }
}

// ---------- build / install ----------
const drawer = document.getElementById("drawer");
const drawerLog = document.getElementById("drawerLog");
document.getElementById("drawerClose").addEventListener("click", () => { drawer.hidden = true; });

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
  drawer.hidden = false;
  document.getElementById("drawerTitle").textContent = title;
  drawerLog.textContent = "Working…";
  drawer.querySelector(".force")?.remove();
  try {
    const r = await api.post(path, body);
    const manifest = r.result && r.result.sections ? r.result : null;
    const lines = [...(manifest ? summarize(manifest) : []), "", ...r.log];
    drawerLog.textContent = lines.join("\n").trim() || "Done.";
    toast(`${title}: done`);
    bus.emit("installed", r.result);
    if (path === "/palettes/apply") bus.emit("mods-changed");   // it turned mods on and off
  } catch (e) {
    drawerLog.textContent = e.message;
    toast(e.message, "bad");
    if ((path === "/install" || path === "/palettes/apply") && e.message.startsWith("not installing")) {
      drawer.append(el("div", { class: "row force", style: { padding: "0 14px 14px" } },
        wc.confirmButton("Apply the rest anyway", "Click again: the failed mods' earlier changes are removed",
          () => runTask(path, title, { ...body, force: true }), "btn danger")));
    }
  }
  await refreshStatus();
}
installBtn.addEventListener("click", () => runTask("/install", "Apply to game"));
bus.on("apply", () => runTask("/install", "Apply to game"));
bus.on("run-task", ({ path, title, body }) => runTask(path, title, body));
bus.on("mods-changed", () => refreshStatus());

// ---------- boot ----------
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
})();
