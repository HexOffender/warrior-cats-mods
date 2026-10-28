// Palettes: recolour the eyes, coats, patterns and markings every cat can wear, on a drawn cat, and add new pattern
// and marking colours. Writes palette.json in a mod; reading and writing it, and the whole-tab changes, are
// lib/palette.js. The page opens without the game's files: the eyes wait for the game folder, and the game's coat,
// pattern and marking colours show as numbered cards until the game has run once with the script loader.
import * as P from "../lib/palette.js";

const CAT_SVG = `
<svg viewBox="0 0 360 330" role="img" aria-label="Preview cat with the selected colours">
  <defs>
    <radialGradient id="irisL" cx="50%" cy="50%" r="50%"></radialGradient>
    <radialGradient id="irisR" cx="50%" cy="50%" r="50%"></radialGradient>
    <clipPath id="almondL"><path d="M88 184 Q124 146 162 180 Q124 214 88 184 Z"/></clipPath>
    <clipPath id="almondR"><path d="M272 184 Q236 146 198 180 Q236 214 272 184 Z"/></clipPath>
    <clipPath id="headClip"><path d="M180 80 C252 80 318 120 322 196 C326 262 262 306 180 306 C98 306 34 262 38 196 C42 120 108 80 180 80 Z"/></clipPath>
  </defs>
  <g data-part="outline" stroke-width="3" stroke-linejoin="round">
    <path data-part="coat" d="M70 152 L90 36 Q96 26 106 33 L172 100 Z"/>
    <path data-part="coat" d="M290 152 L270 36 Q264 26 254 33 L188 100 Z"/>
    <path data-part="coat" d="M180 80 C252 80 318 120 322 196 C326 262 262 306 180 306 C98 306 34 262 38 196 C42 120 108 80 180 80 Z"/>
  </g>
  <path d="M92 128 L103 58 L150 106 Z" fill="var(--ear)" opacity="0.85"/>
  <path d="M268 128 L257 58 L210 106 Z" fill="var(--ear)" opacity="0.85"/>
  <g clip-path="url(#headClip)">
    <g data-part="pattern" fill="none" stroke-width="9" stroke-linecap="round">
      <path d="M180 92 L180 134"/><path d="M158 98 Q163 118 168 136"/><path d="M202 98 Q197 118 192 136"/>
      <path d="M136 108 Q147 124 154 142"/><path d="M224 108 Q213 124 206 142"/>
      <path d="M36 190 Q72 184 102 196"/><path d="M38 216 Q74 208 104 220"/><path d="M46 244 Q78 236 108 244"/>
      <path d="M324 190 Q288 184 258 196"/><path d="M322 216 Q286 208 256 220"/><path d="M314 244 Q282 236 252 244"/>
    </g>
    <g data-part="marking">
      <path d="M180 144 C170 172 166 198 168 218 L192 218 C194 198 190 172 180 144 Z"/>
      <ellipse cx="180" cy="258" rx="66" ry="50"/><ellipse cx="180" cy="318" rx="90" ry="40"/>
    </g>
  </g>
  <g>
    <path data-part="sclera" d="M88 184 Q124 146 162 180 Q124 214 88 184 Z"/>
    <circle clip-path="url(#almondL)" cx="125" cy="181" r="27" fill="url(#irisL)"/>
    <ellipse cx="125" cy="181" rx="5.5" ry="18" fill="#0b0b0c"/><circle cx="133" cy="171" r="4" fill="#ffffff" opacity="0.85"/>
    <path data-part="lid" d="M88 184 Q124 146 162 180 Q124 214 88 184 Z" fill="none" stroke-width="3"/>
  </g>
  <g>
    <path data-part="sclera" d="M272 184 Q236 146 198 180 Q236 214 272 184 Z"/>
    <circle clip-path="url(#almondR)" cx="235" cy="181" r="27" fill="url(#irisR)"/>
    <ellipse cx="235" cy="181" rx="5.5" ry="18" fill="#0b0b0c"/><circle cx="243" cy="171" r="4" fill="#ffffff" opacity="0.85"/>
    <path data-part="lid" d="M272 184 Q236 146 198 180 Q236 214 272 184 Z" fill="none" stroke-width="3"/>
  </g>
  <path d="M168 236 L192 236 Q195 238 190 245 L183 252 Q180 255 177 252 L170 245 Q165 238 168 236 Z" fill="var(--nose)"/>
  <path data-part="mouth" d="M180 254 L180 262 M180 262 Q170 272 160 266 M180 262 Q190 272 200 266" fill="none" stroke-width="2.5" stroke-linecap="round"/>
  <g data-part="whiskers" stroke-width="1.6" stroke-linecap="round" opacity="0.75">
    <path d="M148 252 L62 238 M148 259 L58 262 M150 266 L66 286"/><path d="M212 252 L298 238 M212 259 L302 262 M210 266 L294 286"/>
  </g>
</svg>`;

const SECTIONS = [
  { id: "eyes", title: "Eyes" },
  { id: "fur", title: "Coat", table: "FurColors", noun: "coat" },
  { id: "pattern", title: "Pattern", table: "PatternMaskColors", noun: "pattern" },
  { id: "marking", title: "Markings", table: "MarkingMaskColors", noun: "marking" },
];
const NEUTRAL = "#9a8f84";   // a colour the page doesn't know yet, on the drawn cat

export default {
  title: "Palettes",
  async mount(root, wc) {
    const { el, api, clear, toast, color } = wc;
    // clear() hands back the bare element, whose own append writes a null as the text "null": this leaves them out.
    const put = (node, ...kids) => { clear(node).append(...kids.filter(k => k != null && k !== false)); return node; };
    // The game's eye colours and colour tables, and the studio's status: each may be missing (no game folder yet,
    // the game's files unreadable, the game not yet run with the script loader), and the page opens all the same.
    const [eyes, tablesRes, firstInfo] = await Promise.all([
      api.get("/game/eyes").catch(() => null),
      api.get("/game/tables").catch(() => ({ tables: null, game_slots: 25 })),
      api.get("/info").catch(() => null)]);
    let info = firstInfo;
    const LABELS = eyes ? eyes.labels : null;
    const EYE_LIN = eyes ? eyes.rows.map(r => r.map(h => color.hexToLinear("#" + h))) : null;
    const GROUPS = LABELS ? P.eyeGroups(LABELS) : null;
    const GAME = tablesRes.game_slots || 25;
    const TABLES = tablesRes.tables || {};
    const TABLE = id => TABLES[SECTIONS.find(s => s.id === id).table] || [];
    const origRow = r => (EYE_LIN ? EYE_LIN[r] : P.plainRow(64, r === 0));
    const rimOf = ramp => color.linearToHex(ramp[ramp.length - 1]);
    const vanillaRim = r => rimOf(origRow(r));
    const eyeName = r => (LABELS ? LABELS[r] : `eye ${r}`);

    let state = P.blank();
    let undo = null;   // { label, state }: the last whole-tab change, for its Undo button
    const view = { tab: LABELS ? "eyes" : "pattern", fur: 2, pattern: 3, marking: 10, eyeL: 2, eyeR: 2, vanilla: false };

    // ---------- layout ----------
    const target = wc.modTarget({
      file: "palette.json",
      onLoad: obj => { state = P.fromPalette(obj, { labels: LABELS, gameSlots: GAME }); undo = null; renderAll(); otherSlotsReady = loadOtherSlots(); },
      getValue: () => P.toPalette(state, LABELS),
      // A save keeps what's on the page (it isn't read back); the last whole-tab change can't be undone past it.
      onSaved: () => { undo = null; renderStyleRow(); },
    });
    const edited = () => target.markDirty();
    // curHex: the colour a slot shows with this palette: its own, else the game's, else another palette's new one.
    const curHex = (sec, i) => state[sec][i] || TABLE(sec)[i] || otherHex(sec, i);

    const stage = el("div", { style: { background: "radial-gradient(120% 90% at 50% 30%, var(--stage), var(--stage-2))", borderRadius: "12px" } });
    stage.innerHTML = CAT_SVG;
    const svg = stage.querySelector("svg");
    svg.style.width = "100%"; svg.style.height = "auto"; svg.style.display = "block";
    const picks = el("div", { style: { display: "grid", gridTemplateColumns: "auto minmax(0,1fr)", gap: "8px 12px", alignItems: "center" } });
    const vanillaBox = el("input", { type: "checkbox", id: "pal-vanilla" });
    vanillaBox.addEventListener("change", () => { view.vanilla = vanillaBox.checked; drawCat(); });
    const tabs = el("div", { class: "row", role: "tablist", "aria-label": "Palette sections" });
    const panel = el("div", { role: "tabpanel", id: "pal-panel", style: { display: "grid", gap: "16px" } });
    const startRow = el("div", { class: "row pal-row" });
    const styleRow = el("div", { class: "row pal-row" });
    const tablesLine = el("p", { class: "note pal-tables", hidden: true });
    const unreadBox = el("div", { hidden: true });
    const quick = el("div", { class: "card" });

    root.append(
      wc.pageHead({ eyebrow: "Appearance only", title: "Palettes",
        lede: "Recolour the eyes, coats, patterns and markings every cat can wear, or add new pattern and marking colours. " +
          "A cat keeps the colour it has (coat 3 stays coat 3), so its traits don't change. Eye colours go in through the " +
          "game's files; the rest need the script loader.",
        help: "help:palettes" }),
      quick, target.element, startRow, styleRow,
      el("div", { style: { display: "grid", gridTemplateColumns: "minmax(260px, 360px) minmax(0, 1fr)", gap: "24px", alignItems: "start" }, class: "pal-grid" },
        el("div", { class: "card", style: { position: "sticky", top: "84px" } }, stage, picks,
          el("label", { class: "row muted", for: "pal-vanilla" }, vanillaBox, "Show the game's original colours")),
        el("div", { style: { display: "grid", gap: "12px", minWidth: "0" } }, tabs, tablesLine, unreadBox, panel)));
    const narrow = window.matchMedia("(max-width: 900px)");
    const applyNarrow = () => { root.querySelector(".pal-grid").style.gridTemplateColumns = narrow.matches ? "minmax(0,1fr)" : "minmax(260px, 360px) minmax(0, 1fr)"; };
    narrow.addEventListener("change", applyNarrow); applyNarrow();

    // ---------- quick palettes ----------
    // Mods that hold only a palette work as presets: Apply turns the ticked ones on, the other
    // palette-only mods off, and installs. Mods with anything besides a palette aren't touched, and
    // neither are palettes that only add new colours (cats may be wearing them).
    let quickPick = null;   // ids ticked here; null means "start from what's on"
    let quickData = [];     // [{mod, palette (null if its file can't be read)}]
    const quickButtons = el("div", { class: "row" });
    async function renderQuick() {
      const list = (await api.get("/mods")).filter(m => m.preset);
      quickData = await Promise.all(list.map(async m => {
        try { return { mod: m, palette: JSON.parse((await api.get(`/mods/${encodeURIComponent(m.id)}/file/palette.json`)).text) || {} }; }
        catch (e) { return { mod: m, palette: null }; }
      }));
      if (quickPick === null) quickPick = new Set(list.filter(m => m.enabled).map(m => m.id));
      drawQuick();
    }
    // Why Apply waits, in the shell's words (app.js greys its own Apply for the same reasons).
    const applyWait = () => (!info ? "" : !info.game_dir ? "Find the game first: Get set up, on the Mods page"
      : info.game_running ? "Close the game first" : "");
    async function readInfo() {
      try { info = await api.get("/info"); } catch (e) { /* keep the last answer */ }
      drawQuickButtons();
    }
    function drawQuickButtons() {
      const n = quickPick ? quickPick.size : 0, why = applyWait();
      put(quickButtons,
        el("button", { class: "btn primary", text: n ? `Apply ${n} and install` : "Use the game's colours and install", disabled: !!why,
          title: why || "Turns the ticked palettes on and the other palette-only mods off, then puts them in the game", onclick: async () => {
            // Unsaved colours on this page go in too: saved first, and nothing is installed if that fails.
            if (target.dirty && !await target.save()) return;
            wc.bus.emit("run-task", { path: "/palettes/apply", title: "Apply palettes", body: { ids: [...quickPick], install: true } });
          } }),
        el("button", { class: "btn ghost", text: "Untick all", onclick: () => { quickPick.clear(); drawQuick(); } }),
        why ? el("span", { class: "muted", text: why }) : null);
    }
    function drawQuick() {
      const dot = (hex, round) => el("span", { class: "swatch", title: hex, style: { display: "inline-block", width: "13px", height: "13px",
        background: hex, borderRadius: round ? "50%" : "3px", boxShadow: "inset 0 0 0 1px rgba(0,0,0,.18)" } });
      const eyeRim = (p, r) => {
        const v = p.eyes && LABELS && Object.entries(p.eyes).find(([k]) => P.eyeRow(LABELS, k) === r)?.[1];
        return color.parse(Array.isArray(v) && v.length && typeof v[0] !== "number" ? v[v.length - 1] : v) || vanillaRim(r);
      };
      const tiles = quickData.map(({ mod: m, palette: p }) => {
        const broken = p === null;
        if (broken) quickPick.delete(m.id);
        const box = el("input", { type: "checkbox", id: `quick-${m.id}`, checked: quickPick.has(m.id), disabled: broken });
        box.addEventListener("change", () => { if (box.checked) quickPick.add(m.id); else quickPick.delete(m.id); drawQuickButtons(); });
        const swatches = broken ? [el("span", { class: "chip warn", text: "Its palette can't be read: the Mods page says why" })] : [
          el("div", { style: { display: "flex", gap: "2px", flexWrap: "wrap" }, title: "Coats 0-14" },
            ...[...Array(15).keys()].map(s => dot(color.parse(p.fur?.[String(s)]) || TABLE("fur")[s] || "#888888"))),
          LABELS ? el("div", { style: { display: "flex", gap: "2px", flexWrap: "wrap" }, title: "Eyes" },
            ...GROUPS.standard.map(r => dot(eyeRim(p, r), true))) : null];
        return el("label", { for: `quick-${m.id}`, style: { display: "grid", gap: "6px", padding: "10px 12px", borderRadius: "10px",
            border: "1px solid var(--line, rgba(0,0,0,.12))", cursor: broken ? "default" : "pointer" } },
          el("div", { class: "row" }, box, el("strong", { text: m.name }),
            m.enabled ? el("span", { class: "chip", text: "on" }) : null),
          el("span", { class: "muted", style: { fontSize: "0.8rem" }, text: m.description || m.id }), ...swatches);
      });
      drawQuickButtons();
      put(quick, el("div", { class: "stack" },
        el("h2", { text: "Quick palettes" }),
        el("p", { class: "note", text: "Tick the palettes to use and apply them: it turns those on, turns the other palette mods off, and installs. " +
          "Pick one full theme; eyes-only or coats-only palettes (Gemstone Eyes, Richer Coats, StarClan Glow Eyes) go on top of it. To change one, pick it under Editing mod below." }),
        tiles.length ? null : el("p", { class: "empty", text: "No palette mods yet. Ten themed palettes, and palettes for eyes and coats, are in wcmods-examples (Add a mod, on the Mods page, says where)." }),
        el("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: "10px" } }, ...tiles),
        quickButtons));
    }

    // ---------- Start from, Restyle this tab, Undo ----------
    // A whole-tab change replaces the page's state; the one before is kept for Undo until the next save or mod switch.
    function wholeTab(label, next) {
      undo = { label, state };
      state = next;
      edited();
      renderAll();
    }
    async function renderPresets() {
      let mods = [];
      try { mods = await api.get("/mods"); } catch (e) { /* the bar says what's wrong */ }
      put(startRow, el("span", { class: "eyebrow", text: "Start from" }),
        el("button", { class: "chip", "data-focus": "pal:from:game", text: "Game colours",
          title: "Every change to the game's own colours and eyes goes; your new colours stay",
          onclick: () => wholeTab("Game colours", P.gameColours(state, GAME)) }),
        ...mods.filter(m => m.kinds.includes("palette") && m.id !== target.current).map(m => el("button", {
          class: "chip", "data-focus": `pal:from:${m.id}`, text: m.name,
          title: `${m.name}'s eyes and its changes to the game's colours; your new colours stay`, onclick: async () => {
            let other;
            try { other = JSON.parse((await api.get(`/mods/${encodeURIComponent(m.id)}/file/palette.json`)).text); }
            catch (e) { toast(`${m.name}'s palette can't be read: the Mods page says why`, "bad"); return; }
            wholeTab(`Start from ${m.name}`, P.startFrom(state, other, { labels: LABELS, gameSlots: GAME }));
            toast(`Copied ${m.name}'s colours. Undo puts yours back.`);
          } })));
    }
    function renderStyleRow() {
      const sec = SECTIONS.find(s => s.id === view.tab);
      const can = sec.id === "eyes" ? !!LABELS : TABLE(sec.id).length > 0;
      const wait = sec.id === "eyes" ? "Needs the game's eye colours" : "Needs the game's colours: press Play once, then come back";
      put(styleRow, el("span", { class: "eyebrow", text: "Restyle this tab" }),
        ...Object.entries(color.MOODS).map(([k, m]) => el("button", { class: "chip", "data-focus": `pal:mood:${k}`, text: m.name, disabled: !can,
          title: !can ? wait : sec.id === "eyes" ? `${m.name} on every eye colour, extra eyes too; the eye white stays`
            : `${m.name} on the game's ${TABLE(sec.id).length} ${sec.noun} colours; your new colours stay`,
          onclick: () => wholeTab(m.name, P.restyle(state, sec.id, k, { eyeRims: LABELS ? LABELS.map((_, r) => vanillaRim(r)) : [], table: TABLE(sec.id) })) })),
        el("button", { class: "btn ghost small", "data-focus": "pal:reset", text: "Reset tab",
          title: sec.id === "eyes" ? "Every eye back to the game's" : `The game's ${sec.noun} colours back as they were; your new colours stay`,
          onclick: () => wholeTab(`Reset ${sec.title}`, P.resetTab(state, sec.id, GAME)) }),
        undo ? el("button", { class: "btn small", "data-focus": "pal:undo", text: `Undo ${undo.label}`, onclick: () => {
          state = undo.state; undo = null; edited(); renderAll(); toast("Put back as it was");
        } }) : null);
    }

    // ---------- what the page can't show ----------
    let unreadOpen = false;   // the list stays open (or folded) through a redraw, as it was left
    function renderUnread() {
      clear(unreadBox);
      const n = state.unread.length;
      unreadBox.hidden = !n;
      if (!n) return;
      const box = el("details", { class: "card fold pal-unread", open: unreadOpen },
        el("summary", {}, el("strong", { text: `${n} ${n === 1 ? "entry" : "entries"} this page can't show` }),
          el("span", { class: "muted", text: "kept in the file as written until you remove them" })),
        el("ul", { class: "notes" }, ...state.unread.map((u, i) => el("li", { class: "row" },
          el("span", { text: P.describeUnread(u) }),
          el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${P.describeUnread(u)}`,
            onclick: () => { state.unread.splice(i, 1); edited(); renderUnread(); } })))));
      box.addEventListener("toggle", () => { unreadOpen = box.open; });
      unreadBox.append(box);
    }

    // ---------- cat ----------
    function setIris(id, row) {
      const g = svg.querySelector("#" + id);
      const ramp = P.eyeRamp(origRow(row), view.vanilla ? null : state.eyes[row]);
      g.textContent = "";
      for (let k = 0; k <= 8; k++) {
        const st = document.createElementNS("http://www.w3.org/2000/svg", "stop");
        st.setAttribute("offset", `${18 + k * 10.25}%`);
        st.setAttribute("stop-color", color.linearToHex(ramp[Math.round(k * (ramp.length - 1) / 8)]));
        g.append(st);
      }
    }
    function drawCat() {
      const pick = sec => (view.vanilla ? TABLE(sec)[view[sec]] : curHex(sec, view[sec])) || NEUTRAL;
      const coat = pick("fur"), pat = pick("pattern"), mark = pick("marking"), outline = color.shade(coat, 0.55);
      const scl = view.vanilla || !state.eyes[0] ? vanillaRim(0) : rimOf(P.eyeRamp(origRow(0), state.eyes[0]));
      svg.querySelectorAll('[data-part="coat"]').forEach(n => { n.setAttribute("fill", coat); n.setAttribute("stroke", outline); });
      svg.querySelector('[data-part="pattern"]').setAttribute("stroke", pat);
      svg.querySelector('[data-part="marking"]').setAttribute("fill", mark);
      svg.querySelectorAll('[data-part="sclera"]').forEach(n => n.setAttribute("fill", scl));
      svg.querySelectorAll('[data-part="lid"], [data-part="mouth"]').forEach(n => n.setAttribute("stroke", outline));
      svg.querySelector('[data-part="whiskers"]').setAttribute("stroke", mark);
      setIris("irisL", view.eyeL); setIris("irisR", view.eyeR);
    }
    function renderPicks() {
      clear(picks);
      const sel = (id, label, options, key) => {
        const s = el("select", { id }, ...options.map(([v, t]) => el("option", { value: v, text: t })));
        if (!options.some(([v]) => Number(v) === view[key])) view[key] = Number(options[0]?.[0] ?? 0);
        s.value = view[key];
        s.addEventListener("change", () => { view[key] = Number(s.value); drawCat(); refreshCards(); });
        picks.append(el("label", { for: id, text: label }), s);
      };
      for (const sec of SECTIONS.slice(1)) {
        const n = TABLE(sec.id).length || GAME;
        // The game's colours, then this palette's new ones, then those other palettes that are on add.
        const own = Object.keys(state[sec.id]).map(Number).filter(i => i >= GAME).sort((a, b) => a - b);
        const theirs = sec.id === "fur" ? [] : (slotsElsewhere[sec.id] || []).filter(o => !own.includes(o.slot)).sort((a, b) => a.slot - b.slot);
        sel(`pal-pick-${sec.id}`, sec.title, [
          ...[...Array(n).keys()].map(i => [i, `${i} · ${curHex(sec.id, i) || "the game's"}${state[sec.id][i] ? " (changed)" : ""}`]),
          ...own.map(i => [i, `${i} (new) · ${state[sec.id][i]}`]),
          ...theirs.map(o => [o.slot, `${o.slot} (new, from ${o.name}) · ${o.hex}`])], sec.id);
      }
      if (LABELS) {
        const eyeOpts = LABELS.slice(1).map((l, i) => [i + 1, `${l}${state.eyes[i + 1] ? " (changed)" : ""}`]);
        sel("pal-pick-eyeL", "Left eye", eyeOpts, "eyeL");
        sel("pal-pick-eyeR", "Right eye", eyeOpts, "eyeR");
      }
    }

    // ---------- tabs ----------
    // The arrow keys (and Home, End) move between the tabs; Tab goes on into the open one.
    function pickTab(id) { view.tab = id; renderTabs(); renderPanel(); renderStyleRow(); }
    tabs.addEventListener("keydown", e => {
      const i = SECTIONS.findIndex(s => s.id === view.tab);
      const to = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: SECTIONS.length - 1 }[e.key];
      if (to === undefined) return;
      e.preventDefault();
      pickTab(SECTIONS[(to + SECTIONS.length) % SECTIONS.length].id);
      document.getElementById(`pal-tab-${view.tab}`)?.focus();
    });
    function renderTabs() {
      clear(tabs);
      for (const s of SECTIONS) {
        const n = Object.keys(state[s.id]).length;
        const on = view.tab === s.id;
        tabs.append(el("button", { class: "chip", role: "tab", id: `pal-tab-${s.id}`, "aria-selected": String(on), "aria-controls": "pal-panel",
          tabindex: on ? "0" : "-1", onclick: () => pickTab(s.id) },
          s.title, n ? el("span", { class: "mono", style: { color: "var(--changed)" }, text: ` ${n}` }, el("span", { class: "sr-only", text: " changed" })) : null));
      }
      panel.setAttribute("aria-labelledby", `pal-tab-${view.tab}`);
      // Until the game has run with the script loader, its coat, pattern and marking colours aren't known here.
      const waiting = view.tab !== "eyes" && !TABLE(view.tab).length;
      tablesLine.hidden = !waiting;
      tablesLine.textContent = !waiting ? "" : info && !info.ue4ss
        ? "The game's own colours show here once the game has run with the script loader: Get set up, on the Mods page, installs it; then press Play once and come back. Until then each colour is a numbered card that still takes a colour of yours."
        : "Press Play once, then come back: the game's own colours show here. Until then each colour is a numbered card that still takes a colour of yours.";
    }
    const grid = cards => el("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: "10px" } }, ...cards);
    const group = (title, sub, cards) => el("div", { style: { display: "grid", gap: "8px" } },
      el("h3", {}, title, el("span", { class: "eyebrow", style: { marginLeft: "8px" }, text: sub })), grid(cards));
    const range = (from, to) => [...Array(Math.max(0, to - from)).keys()].map(i => i + from);
    let addBtn = null;
    function renderPanel() {
      clear(panel);
      addBtn = null;
      if (view.tab === "eyes") {
        if (!LABELS) {
          panel.append(el("p", { class: "empty", text: !info || !info.game_dir
            ? "Find the game first: Get set up, on the Mods page, asks where it is. The Coat, Pattern and Markings tabs work without it."
            : "The game's eye colours can't be read just now (is Steam updating the game?). The other tabs still work; open this page again in a moment." }));
          return;
        }
        put(panel, el("p", { class: "note", text: "Strips run from the pupil (left) to the rim (right). One colour keeps the game's shading; a gradient spreads your colours across the iris. Some of the game's names don't match the colour, so go by the strip." }),
          group("Standard eyes", `${GROUPS.standard.length} colours`, GROUPS.standard.map(eyeCard)),
          group("Eye white", "behind every iris", GROUPS.white.map(eyeCard)),
          GROUPS.extra.length ? group("Extra eyes", "from a game add-on", GROUPS.extra.map(eyeCard)) : null);
        return;
      }
      const sec = SECTIONS.find(s => s.id === view.tab);
      const n = TABLE(sec.id).length || GAME;
      panel.append(group("Natural", `colours 0-${Math.min(15, n) - 1}`, range(0, Math.min(15, n)).map(i => tableCard(sec, i))));
      if (n > 15) panel.append(group("Bright extras", `colours 15-${n - 1}`, range(15, n).map(i => tableCard(sec, i))));
      if (sec.id === "fur") {
        panel.append(el("p", { class: "note", text: "Coats can't take new colours: the game pairs each coat with paw, ear and nose colours of its own. To give just your cat a coat colour of its own, use the Your cat page." }));
        return;
      }
      // New colours past the game's: only cats set to them wear them (the Your cat page), so the game's colours stay.
      const extra = Object.keys(state[sec.id]).map(Number).filter(i => i >= GAME).sort((a, b) => a - b);
      addBtn = el("button", { class: "btn small", id: `pal-add-${sec.id}`, text: `Add a new ${sec.noun} colour`,
        disabled: !othersRead, title: othersRead ? "" : "Checking the other palettes…", onclick: async () => {
          await otherSlotsReady;   // a number another palette already adds is never taken
          const next = P.nextSlot(Object.keys(state[sec.id]).map(Number), (slotsElsewhere[sec.id] || []).map(o => o.slot), GAME);
          state[sec.id][next] = TABLE(sec.id)[next % n] || curHex(sec.id, view[sec.id]) || "#888888";
          view[sec.id] = next;
          edited(); renderPanel(); renderTabs(); renderPicks(); drawCat();
          document.getElementById(`pal-${sec.id}-${next}`)?.focus();
        } });
      panel.append(el("div", { style: { display: "grid", gap: "8px" } },
        el("h3", {}, "New colours", el("span", { class: "eyebrow", style: { marginLeft: "8px" }, text: `colour ${GAME} and up` })),
        el("p", { class: "note", text: `Adds ${sec.noun} colours without changing any of the game's, so other cats keep theirs. Each new colour keeps its number for good, so a cat set to it keeps it whatever else you turn on. Pick one for your cat on the Your cat page, or in the cat maker with the Creator palettes mod.` }),
        extra.length ? grid(extra.map(i => tableCard(sec, i))) : null, el("div", { class: "row" }, addBtn)));
    }
    // New colours other palettes that are on already add, so a new one here doesn't take their number.
    let slotsElsewhere = {}, othersRead = false, otherSlotsReady = Promise.resolve();
    async function loadOtherSlots() {
      othersRead = false;
      if (addBtn) { addBtn.disabled = true; addBtn.title = "Checking the other palettes…"; }
      const found = {};
      try {
        for (const m of await api.get("/mods")) {
          if (m.id === target.current || !m.kinds.includes("palette") || !m.enabled) continue;
          try {
            const p = JSON.parse((await api.get(`/mods/${encodeURIComponent(m.id)}/file/palette.json`)).text) || {};
            for (const sec of P.GROWABLE) {
              for (const [k, v] of Object.entries(p[sec] || {})) {
                if (/^[0-9]+$/.test(k) && Number(k) >= GAME) (found[sec] ||= []).push({ slot: Number(k), hex: color.parse(v) || "#888888", name: m.name });
              }
            }
          } catch (e) { /* a palette that can't be read: nothing to avoid */ }
        }
      } catch (e) { /* no mod list: the bar says what's wrong */ }
      slotsElsewhere = found;
      othersRead = true;
      if (addBtn) { addBtn.disabled = false; addBtn.title = ""; }
      renderPicks();
    }
    const otherHex = (sec, i) => (slotsElsewhere[sec] || []).find(o => o.slot === i)?.hex;
    const cardBox = () => el("div", { class: "card", style: { padding: "10px", gap: "8px" } });
    function tableCard(sec, i) {
      const isNew = i >= GAME;
      const orig = isNew ? null : TABLE(sec.id)[i] || null;   // the game's colour, once it's known
      const card = cardBox();
      const newSw = el("span", {});
      const before = el("span", orig ? { style: { background: orig } }
        : { class: "pal-unknown", title: isNew ? "A new colour" : "The game's colour shows after one Play" });
      const pair = el("button", { class: "btn swatch", style: { padding: "0", height: "38px", display: "grid", gridTemplateColumns: "1fr 1fr", overflow: "hidden" },
        "aria-label": `Show ${sec.noun} colour ${i} on the cat`, onclick: () => { view[sec.id] = i; renderPicks(); drawCat(); refreshCards(); } },
        before, newSw);
      const name = el("strong"), hex = el("span", { class: "hex muted" });
      const inp = el("input", { type: "color", id: `pal-${sec.id}-${i}`, "aria-label": `New colour for ${sec.noun} colour ${i}` });
      inp.addEventListener("input", () => { state[sec.id][i] = color.normHex(inp.value); edited(); card._update(); drawCat(); });
      inp.addEventListener("change", () => { renderTabs(); renderPicks(); });
      const reset = el("button", { class: "btn ghost small", text: isNew ? "Remove" : "Reset", "aria-label": `${isNew ? "Remove" : "Reset"} ${sec.noun} colour ${i}`, onclick: () => {
        delete state[sec.id][i];
        edited();
        if (isNew) {
          if (view[sec.id] === i) view[sec.id] = 0;
          renderPanel(); renderTabs(); renderPicks(); drawCat();
          document.getElementById(`pal-add-${sec.id}`)?.focus();
          return;
        }
        card._update(); drawCat(); renderTabs(); renderPicks();
      } });
      card.append(pair, el("div", { class: "row spread" }, name, hex), el("div", { class: "row" }, inp, reset));
      card._update = () => {
        const cur = curHex(sec.id, i), changed = !!state[sec.id][i];
        newSw.style.background = cur || "";
        newSw.className = cur ? "" : "pal-unknown";
        name.textContent = isNew ? `New ${sec.noun} colour ${i}` : `${changed ? "● " : ""}${sec.noun[0].toUpperCase()}${sec.noun.slice(1)} ${i}`;
        name.style.color = changed && !isNew ? "var(--changed)" : "";
        hex.textContent = changed && orig ? `${orig} → ${cur}` : cur || "shows after one Play";
        hex.className = cur ? "hex muted" : "muted";
        inp.value = (cur || "#888888").toLowerCase(); reset.disabled = !changed;
        card.style.boxShadow = view[sec.id] === i ? "0 0 0 2px var(--accent)" : "";
        pair.setAttribute("aria-pressed", String(view[sec.id] === i));
      };
      card._update();
      return card;
    }
    function eyeCard(row) {
      const card = cardBox();
      const newRamp = el("span", { style: { height: "18px", borderRadius: "5px", border: "1px solid var(--line)" } });
      const pick = el("button", { class: "btn swatch", style: { padding: "4px", display: "grid", gap: "3px" }, "aria-label": `Show ${eyeName(row)} on the cat`,
        onclick: () => { if (row > 0) { view.eyeL = view.eyeR = row; renderPicks(); } drawCat(); refreshCards(); } },
        el("span", { style: { height: "18px", borderRadius: "5px", border: "1px solid var(--line)", background: rampCss(origRow(row)) } }), newRamp);
      const name = el("strong"), hex = el("span", { class: "hex muted" });
      const one = el("button", { class: "chip", "data-focus": `pal:eye:${row}:one`, text: "One colour", onclick: () => setMode("single") });
      const grad = el("button", { class: "chip", "data-focus": `pal:eye:${row}:grad`, text: "Gradient", onclick: () => setMode("grad") });
      const inputs = el("div", { class: "row" });
      const reset = el("button", { class: "btn ghost small", text: "Reset", "aria-label": `Reset ${eyeName(row)}`, onclick: () => { delete state.eyes[row]; edited(); rebuild(); card._update(); drawCat(); renderTabs(); renderPicks(); } });
      card.append(pick, el("div", { class: "row spread" }, name, hex), el("div", { class: "row" }, one, grad, reset), inputs);
      const ensure = () => (state.eyes[row] ||= { mode: "single", colors: [vanillaRim(row)] });
      function setMode(mode) {
        const o = ensure();
        if (mode === "grad" && o.colors.length < 2) o.colors = ["#101418", o.colors[0]];
        if (mode === "single") o.colors = [o.colors[o.colors.length - 1]];
        o.mode = mode; edited(); rebuild(); card._update(); drawCat(); renderTabs();
      }
      function rebuild() {
        clear(inputs);
        const o = state.eyes[row];
        (o ? o.colors : [vanillaRim(row)]).forEach((c, k) => {
          const inp = el("input", { type: "color", id: `pal-eye-${row}-${k}`, value: c.toLowerCase(), "aria-label": `${eyeName(row)} colour ${k + 1}` });
          inp.addEventListener("input", () => { ensure().colors[k] = color.normHex(inp.value); edited(); card._update(); drawCat(); });
          inp.addEventListener("change", () => { renderTabs(); renderPicks(); });
          inputs.append(inp);
        });
        if (o && o.mode === "grad") {
          if (o.colors.length < 4) inputs.append(el("button", { class: "btn small", "data-focus": `pal:eye:${row}:add-stop`, text: "+ stop", "aria-label": `Add a colour to ${eyeName(row)}'s gradient`, onclick: () => { o.colors.push(o.colors[o.colors.length - 1]); edited(); rebuild(); card._update(); drawCat(); } }));
          if (o.colors.length > 2) inputs.append(el("button", { class: "btn small", "data-focus": `pal:eye:${row}:drop-stop`, text: "− stop", "aria-label": `Take the last colour off ${eyeName(row)}'s gradient`, onclick: () => { o.colors.pop(); edited(); rebuild(); card._update(); drawCat(); } }));
        }
      }
      card._update = () => {
        const o = state.eyes[row];
        newRamp.style.background = rampCss(P.eyeRamp(origRow(row), o));
        name.textContent = `${o ? "● " : ""}${eyeName(row)}`;
        name.style.color = o ? "var(--changed)" : "";
        hex.textContent = o ? (o.mode === "grad" ? `${o.colors.length}-colour gradient` : `${vanillaRim(row)} → ${o.colors[0]}`) : vanillaRim(row);
        one.setAttribute("aria-pressed", String(!o || o.mode === "single"));
        grad.setAttribute("aria-pressed", String(!!o && o.mode === "grad"));
        reset.disabled = !o;
        card.style.boxShadow = row > 0 && (view.eyeL === row || view.eyeR === row) ? "0 0 0 2px var(--accent)" : "";
      };
      rebuild(); card._update();
      return card;
    }
    function rampCss(ramp) {
      const stops = [];
      for (let k = 0; k <= 8; k++) { const x = Math.round(k * (ramp.length - 1) / 8); stops.push(`${color.linearToHex(ramp[x])} ${(k * 12.5).toFixed(1)}%`); }
      return `linear-gradient(90deg, ${stops.join(", ")})`;
    }
    function refreshCards() { panel.querySelectorAll(".card").forEach(c => c._update && c._update()); }
    function renderAll() { renderTabs(); renderPanel(); renderPicks(); drawCat(); renderPresets(); renderStyleRow(); renderUnread(); }

    // After an Apply or Play: the quick palettes and the status are read again, and the file too, unless there are
    // unsaved changes here (installedEvent), which stay, the bar saying they aren't in the game yet.
    const offs = [
      wc.installedEvent(target, () => target.refresh()),
      wc.bus.on("installed", () => { quickPick = null; renderQuick().catch(() => {}); readInfo(); }),
      wc.bus.on("focus", readInfo),
      wc.bus.on("mods-changed", () => { renderPresets(); otherSlotsReady = loadOtherSlots(); }),
    ];
    await Promise.all([target.refresh(), renderQuick()]);
    return { unmount() { for (const off of offs) off(); narrow.removeEventListener("change", applyNarrow); } };
  },
};
