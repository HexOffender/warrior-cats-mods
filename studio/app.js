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

async function refreshStatus() {
  try {
    info = await api.get("/info");
  } catch (e) {
    clear(statusBox).append(chip("Studio server not reachable", "bad", e.message));
    return null;
  }
  clear(statusBox).append(
    chip(info.game_running ? "Game running" : "Game closed", info.game_running ? "warn" : "good",
      info.game_running ? "Close the game before installing" : ""),
    chip(info.ue4ss ? "UE4SS installed" : "No UE4SS", info.ue4ss ? "good" : "warn"),
    chip(info.save_found ? "Save found" : "No save yet", info.save_found ? "good" : "warn"),
    chip(info.installed ? `Installed: ${info.installed.mods.length} mods` : "Nothing installed", info.installed ? "good" : ""));
  return info;
}

function renderNav() {
  clear(nav);
  for (const s of info.sections) {
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
  } catch (e) {
    drawerLog.textContent = e.message;
    toast(e.message, "bad");
    if (path === "/install" && e.message.startsWith("not installing")) {
      drawer.append(el("div", { class: "row force", style: { padding: "0 14px 14px" } },
        wc.confirmButton("Install the rest anyway", "Click again: the failed mods' earlier changes are removed",
          () => runTask("/install", "Install mods", { force: true }), "btn danger")));
    }
  }
  await refreshStatus();
}
document.getElementById("buildBtn").addEventListener("click", () => runTask("/build", "Check build"));
document.getElementById("installBtn").addEventListener("click", () => runTask("/install", "Install mods"));
bus.on("run-task", ({ path, title }) => runTask(path, title));
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
