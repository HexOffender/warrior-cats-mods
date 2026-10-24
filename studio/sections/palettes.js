// Palettes: recolour eyes, coats, patterns and markings on a live cat. Writes palette.json in a mod.
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
  { id: "fur", title: "Coat", table: "FurColors", noun: "Coat" },
  { id: "pattern", title: "Pattern", table: "PatternMaskColors", noun: "Pattern" },
  { id: "marking", title: "Markings", table: "MarkingMaskColors", noun: "Marking" },
];

export default {
  title: "Palettes",
  async mount(root, wc) {
    const { el, api, clear, toast, color } = wc;
    const [eyesRes, tablesRes] = await Promise.all([api.get("/game/eyes"), api.get("/game/tables")]);
    const EYE_LABEL = eyesRes.labels;
    const EYE_LIN = eyesRes.rows.map(r => r.map(h => color.hexToLinear("#" + h)));
    const W = EYE_LIN[0].length;
    const STD = [...Array(20).keys()].map(i => i + 1), DLC = [21, 22, 23, 24, 25];
    const TABLES = tablesRes.tables || {};
    const TABLE = id => TABLES[SECTIONS.find(s => s.id === id).table] || [];

    let state = blank();
    const view = { tab: "eyes", fur: 2, pattern: 3, marking: 10, eyeL: 2, eyeR: 2, vanilla: false };
    function blank() { return { eyes: {}, fur: {}, pattern: {}, marking: {} }; }

    // ---------- maths (mirrors wcmods/palettes.apply_eyes) ----------
    function eyeRamp(row, ov) {
      const orig = EYE_LIN[row];
      if (!ov) return orig;
      if (ov.mode === "grad" && ov.colors.length > 1) {
        const stops = ov.colors.map(color.hexToLinear), n = stops.length;
        return orig.map((_, x) => {
          const t = x / (W - 1) * (n - 1), i = Math.min(Math.floor(t), n - 2), f = t - i;
          return [0, 1, 2].map(k => stops[i][k] + (stops[i + 1][k] - stops[i][k]) * f);
        });
      }
      const target = color.hexToLinear(ov.colors[0]);
      const lums = orig.map(color.luminance), peak = Math.max(...lums);
      const ramp = lums[0] < 0.02 * Math.max(peak, 1e-6);
      return orig.map((_, x) => { const s = ramp && peak > 0 ? lums[x] / peak : 1; return target.map(c => c * s); });
    }
    const vanillaRim = row => color.linearToHex(EYE_LIN[row][W - 1]);
    function rampCss(ramp) {
      const stops = [];
      for (let k = 0; k <= 8; k++) { const x = Math.round(k * (W - 1) / 8); stops.push(`${color.linearToHex(ramp[x])} ${(k * 12.5).toFixed(1)}%`); }
      return `linear-gradient(90deg, ${stops.join(", ")})`;
    }
    function eyeRow(key) {
      const k = String(key).trim().toLowerCase();
      const i = EYE_LABEL.findIndex(l => l.toLowerCase() === k);
      if (i >= 0) return i;
      const m = /^(?:row|iris)?(\d+)$/.exec(k);
      return m && +m[1] < EYE_LABEL.length ? +m[1] : null;
    }
    function fromPalette(p) {
      const s = blank();
      for (const [key, val] of Object.entries((p && p.eyes) || {})) {
        const row = eyeRow(key);
        const colors = (Array.isArray(val) ? val : [val]).map(color.normHex);
        if (row == null || colors.some(c => !c)) continue;
        s.eyes[row] = { mode: colors.length > 1 ? "grad" : "single", colors };
      }
      for (const sec of ["fur", "pattern", "marking"]) {
        for (const [key, val] of Object.entries((p && p[sec]) || {})) {
          const i = Number(key), c = color.normHex(val);
          if (Number.isInteger(i) && c) s[sec][i] = c;
        }
      }
      return s;
    }
    function toPalette() {
      const out = { _help: "Written by Clan Mod Studio. Eye keys are the game's slot names; coat/pattern/marking keys are slot numbers." };
      const eyeKeys = Object.keys(state.eyes).map(Number).sort((a, b) => a - b);
      if (eyeKeys.length) {
        out.eyes = {};
        for (const r of eyeKeys) { const ov = state.eyes[r]; out.eyes[EYE_LABEL[r]] = ov.mode === "grad" ? ov.colors.slice() : ov.colors[0]; }
      }
      for (const sec of ["fur", "pattern", "marking"]) {
        const keys = Object.keys(state[sec]).map(Number).sort((a, b) => a - b);
        if (keys.length) { out[sec] = {}; for (const i of keys) out[sec][String(i)] = state[sec][i]; }
      }
      return out;
    }
    const curHex = (sec, i) => state[sec][i] || TABLE(sec)[i];

    // ---------- layout ----------
    const target = wc.modTarget({
      file: "palette.json", defaultId: "my-palette", defaultName: "My Palette",
      onLoad: obj => { state = fromPalette(obj); renderAll(); loadOtherSlots().catch(() => {}); },
      getValue: () => toPalette(),
    });
    const stage = el("div", { style: { background: "radial-gradient(120% 90% at 50% 30%, var(--stage), var(--stage-2))", borderRadius: "12px" } });
    stage.innerHTML = CAT_SVG;
    const svg = stage.querySelector("svg");
    svg.style.width = "100%"; svg.style.height = "auto"; svg.style.display = "block";
    const picks = el("div", { style: { display: "grid", gridTemplateColumns: "auto minmax(0,1fr)", gap: "8px 12px", alignItems: "center" } });
    const vanillaBox = el("input", { type: "checkbox", id: "pal-vanilla" });
    vanillaBox.addEventListener("change", () => { view.vanilla = vanillaBox.checked; drawCat(); });
    const tabs = el("div", { class: "row", role: "tablist", "aria-label": "Palette sections" });
    const panel = el("div", { role: "tabpanel", id: "pal-panel", style: { display: "grid", gap: "16px" } });
    const presetRow = el("div", { class: "row" });
    const quick = el("div", { class: "card" });

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Appearance only" }),
        el("h1", { text: "Palettes" }),
        el("p", { class: "note", text: "A palette redraws a colour slot; your cat keeps the same slot, so traits and stats don't change. Eye colours work on their own; coat, pattern and marking colours, and the cat creator's eye buttons, need UE4SS." })),
      ...(tablesRes.tables ? [] : [el("div", { class: "banner" }, el("strong", { text: "Coat colours not loaded yet" }),
        el("span", { text: "Start the game once with UE4SS and the mods installed; its log provides the coat, pattern and marking colours." }))]),
      quick, target.element, presetRow,
      el("div", { style: { display: "grid", gridTemplateColumns: "minmax(260px, 360px) minmax(0, 1fr)", gap: "24px", alignItems: "start" }, class: "pal-grid" },
        el("div", { class: "card", style: { position: "sticky", top: "84px" } }, stage, picks,
          el("label", { class: "row muted", for: "pal-vanilla" }, vanillaBox, "Show the game's original colours")),
        el("div", { style: { display: "grid", gap: "12px", minWidth: "0" } }, tabs, panel)));
    const narrow = window.matchMedia("(max-width: 900px)");
    const applyNarrow = () => { root.querySelector(".pal-grid").style.gridTemplateColumns = narrow.matches ? "minmax(0,1fr)" : "minmax(260px, 360px) minmax(0, 1fr)"; };
    narrow.addEventListener("change", applyNarrow); applyNarrow();

    // ---------- quick palettes ----------
    // Mods that hold only a palette work as presets: Apply turns the ticked ones on, the other
    // palette-only mods off, and installs. Mods with anything besides a palette aren't touched, and
    // neither are palettes that only add new colour slots (cats may be wearing them).
    let quickPick = null;   // ids ticked here; null means "start from what's on"
    let quickData = [];     // [{mod, palette (null if its file can't be read)}]
    async function renderQuick() {
      const list = (await api.get("/mods")).filter(m => m.preset);
      quickData = await Promise.all(list.map(async m => {
        try { return { mod: m, palette: JSON.parse((await api.get(`/mods/${encodeURIComponent(m.id)}/file/palette.json`)).text) || {} }; }
        catch (e) { return { mod: m, palette: null }; }
      }));
      if (quickPick === null) quickPick = new Set(list.filter(m => m.enabled).map(m => m.id));
      drawQuick();
    }
    function drawQuick() {
      const dot = (hex, round) => el("span", { class: "swatch", title: hex, style: { display: "inline-block", width: "13px", height: "13px",
        background: hex, borderRadius: round ? "50%" : "3px", boxShadow: "inset 0 0 0 1px rgba(0,0,0,.18)" } });
      const eyeRim = (p, r) => {
        const v = p.eyes && Object.entries(p.eyes).find(([k]) => eyeRow(k) === r)?.[1];
        return color.normHex(Array.isArray(v) ? v[v.length - 1] : v) || vanillaRim(r);
      };
      const tiles = quickData.map(({ mod: m, palette: p }) => {
        const broken = p === null;
        if (broken) quickPick.delete(m.id);
        const box = el("input", { type: "checkbox", id: `quick-${m.id}`, checked: quickPick.has(m.id), disabled: broken });
        box.addEventListener("change", () => { if (box.checked) quickPick.add(m.id); else quickPick.delete(m.id); renderQuickButtons(); });
        const swatches = broken ? [el("span", { class: "chip warn", text: "palette.json can't be read; fix it on the Mods page or in the file" })] : [
          el("div", { style: { display: "flex", gap: "2px", flexWrap: "wrap" }, title: "Coats 0-14" },
            ...[...Array(15).keys()].map(s => dot(color.normHex(p.fur?.[String(s)]) || TABLE("fur")[s] || "#888888"))),
          el("div", { style: { display: "flex", gap: "2px", flexWrap: "wrap" }, title: "Eyes" }, ...STD.map(r => dot(eyeRim(p, r), true)))];
        return el("label", { for: `quick-${m.id}`, style: { display: "grid", gap: "6px", padding: "10px 12px", borderRadius: "10px",
            border: "1px solid var(--line, rgba(0,0,0,.12))", cursor: broken ? "default" : "pointer" } },
          el("div", { class: "row" }, box, el("strong", { text: m.name }),
            m.enabled ? el("span", { class: "chip", text: "on" }) : null),
          el("span", { class: "muted", style: { fontSize: "0.8rem" }, text: m.description || m.id }), ...swatches);
      });
      const buttons = el("div", { class: "row" });
      function renderQuickButtons() {
        const n = quickPick.size;
        clear(buttons).append(
          el("button", { class: "btn primary", text: n ? `Apply ${n} and install` : "Use the game's colours and install", onclick: () =>
            wc.bus.emit("run-task", { path: "/palettes/apply", title: "Apply palettes", body: { ids: [...quickPick], install: true } }) }),
          el("button", { class: "btn ghost", text: "Untick all", onclick: () => { quickPick.clear(); drawQuick(); } }),
          el("span", { class: "muted", text: "Close the game first." }));
      }
      renderQuickButtons();
      clear(quick).append(el("h2", { text: "Quick palettes" }),
        el("p", { class: "note", text: "Tick the palettes to use and apply them: it turns those on, turns the other palette mods off, and installs. " +
          "Pick one full theme; eyes-only or coats-only palettes (Gemstone Eyes, Richer Coats, StarClan Glow Eyes) go on top of it. To change one, pick it under Editing mod below." }),
        tiles.length ? null : el("p", { class: "empty", text: "No palette mods yet. Ten themes, and palettes for eyes and coats, are under Example mods on the Mods page." }),
        el("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: "10px" } }, ...tiles),
        buttons);
    }
    const offInstalled = wc.bus.on("installed", () => { quickPick = null; renderQuick(); target.refresh(); });
    async function renderPresets() {
      const mods = await api.get("/mods");
      clear(presetRow).append(el("span", { class: "eyebrow", text: "Start from" }),
        el("button", { class: "chip", text: "Game colours", onclick: () => { state = blank(); target.markDirty(); renderAll(); } }));
      for (const m of mods.filter(m => m.kinds.includes("palette") && m.id !== target.current)) {
        presetRow.append(el("button", { class: "chip", text: m.name, title: `Copy ${m.id}'s palette here`, onclick: async () => {
          const r = await api.get(`/mods/${encodeURIComponent(m.id)}/file/palette.json`);
          try { state = fromPalette(JSON.parse(r.text)); target.markDirty(); renderAll(); toast(`Copied ${m.name}`); } catch (e) { toast(e.message, "bad"); }
        } }));
      }
      presetRow.append(el("span", { class: "eyebrow", style: { marginLeft: "12px" }, text: "Restyle this tab" }),
        ...Object.entries(color.MOODS).map(([k, m]) => el("button", { class: "chip", text: m.name, onclick: () => applyMood(k) })),
        el("button", { class: "btn ghost small", text: "Reset tab", onclick: () => { state[view.tab] = {}; target.markDirty(); renderAll(); } }));
    }
    function applyMood(key) {
      if (view.tab === "eyes") for (const r of STD) state.eyes[r] = { mode: "single", colors: [color.mood(vanillaRim(r), key)] };
      else TABLE(view.tab).forEach((h, i) => { state[view.tab][i] = color.mood(h, key); });
      target.markDirty(); renderAll();
    }

    // ---------- cat ----------
    function setIris(id, row) {
      const g = svg.querySelector("#" + id);
      const ramp = eyeRamp(row, view.vanilla ? null : state.eyes[row]);
      g.textContent = "";
      for (let k = 0; k <= 8; k++) {
        const st = document.createElementNS("http://www.w3.org/2000/svg", "stop");
        st.setAttribute("offset", `${18 + k * 10.25}%`);
        st.setAttribute("stop-color", color.linearToHex(ramp[Math.round(k * (W - 1) / 8)]));
        g.append(st);
      }
    }
    function drawCat() {
      const pick = sec => (view.vanilla ? TABLE(sec)[view[sec]] : curHex(sec, view[sec])) || "#9a8f84";
      const coat = pick("fur"), pat = pick("pattern"), mark = pick("marking"), outline = color.shade(coat, 0.55);
      const scl = view.vanilla || !state.eyes[0] ? vanillaRim(0) : color.linearToHex(eyeRamp(0, state.eyes[0])[W - 1]);
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
        s.value = view[key];
        s.addEventListener("change", () => { view[key] = Number(s.value); drawCat(); refreshCards(); });
        picks.append(el("label", { for: id, text: label }), s);
      };
      for (const [sec, label] of [["fur", "Coat"], ["pattern", "Pattern"], ["marking", "Markings"]]) {
        sel(`pal-pick-${sec}`, label, TABLE(sec).map((_, i) => [i, `${i} · ${curHex(sec, i)}${state[sec][i] ? " (changed)" : ""}`]), sec);
      }
      const eyeOpts = EYE_LABEL.slice(1).map((l, i) => [i + 1, `${l}${state.eyes[i + 1] ? " (changed)" : ""}`]);
      sel("pal-pick-eyeL", "Left eye", eyeOpts, "eyeL");
      sel("pal-pick-eyeR", "Right eye", eyeOpts, "eyeR");
    }

    // ---------- tabs ----------
    // The arrow keys (and Home, End) move between the tabs; Tab goes on into the open one.
    function pickTab(id) { view.tab = id; renderTabs(); renderPanel(); }
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
    }
    const grid = cards => el("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: "10px" } }, ...cards);
    const group = (title, sub, cards) => el("div", { style: { display: "grid", gap: "8px" } },
      el("h3", {}, title, el("span", { class: "eyebrow", style: { marginLeft: "8px" }, text: sub })), grid(cards));
    function renderPanel() {
      clear(panel);
      if (view.tab === "eyes") {
        panel.append(el("p", { class: "note", text: "Strips run from the pupil (left) to the rim (right). One colour keeps the game's shading; a gradient spreads your colours across the iris. Some of the game's names don't match the colour, so go by the strip." }),
          group("Standard eyes", "20 slots", STD.map(eyeCard)), group("Eye white", "sclera", [eyeCard(0)]), group("DLC eyes", "5 slots", DLC.map(eyeCard)));
      } else {
        const sec = SECTIONS.find(s => s.id === view.tab);
        const n = TABLE(sec.id).length;
        if (!n) { panel.append(el("p", { class: "empty", text: "These colours load from the game's log once UE4SS has run." })); return; }
        panel.append(group("Natural", "slots 0-14", [...Array(Math.min(15, n)).keys()].map(i => tableCard(sec, i))));
        if (n > 15) panel.append(group("Extras", `slots 15-${n - 1}`, [...Array(n - 15).keys()].map(i => tableCard(sec, i + 15))));
        if (sec.id === "fur") {
          panel.append(el("p", { class: "note", text: "Coats can't take new slots: the game pairs each coat with paw, ear and nose colours of its own. To give just your cat a new coat colour, use the Your cat page." }));
          return;
        }
        // New slots past the game's: only cats set to them wear them (Your cat page), so the game's colours stay.
        const extra = Object.keys(state[sec.id]).map(Number).filter(i => i >= n).sort((a, b) => a - b);
        const add = el("button", { class: "btn small", text: `Add a new ${sec.noun.toLowerCase()} colour`, onclick: () => {
          const next = Math.max(n, ...extra.map(i => i + 1), ...otherSlots(sec.id).map(i => i + 1));
          state[sec.id][next] = TABLE(sec.id)[next % n] || "#888888";
          target.markDirty(); renderPanel(); renderTabs(); renderPicks();
        } });
        panel.append(el("div", { style: { display: "grid", gap: "8px" } },
          el("h3", {}, "New colours", el("span", { class: "eyebrow", style: { marginLeft: "8px" }, text: `slot ${n} and up` })),
          el("p", { class: "note", text: "Adds colours without changing any of the game's, so other cats keep theirs. Pick one for your cat on the Your cat page. Each new colour keeps its slot number, so your cat keeps it whatever else you turn on." }),
          extra.length ? grid(extra.map(i => tableCard(sec, i))) : null, el("div", { class: "row" }, add)));
      }
    }
    // Slots past the game's that other palette mods already add, so a new one here doesn't clash.
    let slotsElsewhere = {};
    async function loadOtherSlots() {
      slotsElsewhere = {};
      for (const m of await api.get("/mods")) {
        if (m.id === target.current || !m.kinds.includes("palette")) continue;
        try {
          const p = JSON.parse((await api.get(`/mods/${encodeURIComponent(m.id)}/file/palette.json`)).text) || {};
          for (const sec of ["pattern", "marking"]) for (const k of Object.keys(p[sec] || {})) (slotsElsewhere[sec] ||= []).push(Number(k));
        } catch (e) { /* unreadable palette: nothing to avoid */ }
      }
    }
    const otherSlots = sec => (slotsElsewhere[sec] || []).filter(i => i >= TABLE(sec).length);
    const cardBox = () => el("div", { class: "card", style: { padding: "10px", gap: "8px" } });
    function tableCard(sec, i) {
      const isNew = i >= TABLE(sec.id).length;
      const orig = isNew ? (state[sec.id][i] || "#888888") : TABLE(sec.id)[i];
      const card = cardBox();
      const newSw = el("span", { style: { background: orig } });
      const pair = el("button", { class: "btn swatch", style: { padding: "0", height: "38px", display: "grid", gridTemplateColumns: "1fr 1fr", overflow: "hidden" },
        "aria-label": `Show ${sec.noun.toLowerCase()} slot ${i} on the cat`, onclick: () => { view[sec.id] = i; renderPicks(); drawCat(); refreshCards(); } },
        el("span", { style: { background: orig } }), newSw);
      const name = el("strong"), hex = el("span", { class: "hex muted" });
      const inp = el("input", { type: "color", id: `pal-${sec.id}-${i}`, "aria-label": `New colour for ${sec.noun.toLowerCase()} slot ${i}` });
      inp.addEventListener("input", () => { state[sec.id][i] = color.normHex(inp.value); target.markDirty(); card._update(); drawCat(); });
      inp.addEventListener("change", () => { renderTabs(); renderPicks(); });
      const reset = el("button", { class: "btn ghost small", text: isNew ? "Remove" : "Reset", "aria-label": `${isNew ? "Remove" : "Reset"} ${sec.noun.toLowerCase()} slot ${i}`, onclick: () => {
        delete state[sec.id][i];
        target.markDirty();
        if (isNew) { if (view[sec.id] === i) view[sec.id] = 0; renderPanel(); renderTabs(); renderPicks(); drawCat(); return; }
        card._update(); drawCat(); renderTabs(); renderPicks();
      } });
      card.append(pair, el("div", { class: "row spread" }, name, hex), el("div", { class: "row" }, inp, reset));
      card._update = () => {
        const cur = curHex(sec.id, i) || orig, changed = !!state[sec.id][i];
        newSw.style.background = cur;
        name.textContent = isNew ? `New ${sec.noun.toLowerCase()} ${i}` : `${changed ? "● " : ""}${sec.noun} ${i}`;
        name.style.color = changed && !isNew ? "var(--changed)" : "";
        hex.textContent = changed && !isNew ? `${orig} → ${cur}` : cur;
        inp.value = cur.toLowerCase(); reset.disabled = !changed;
        card.style.boxShadow = view[sec.id] === i ? "0 0 0 2px var(--accent)" : "";
        pair.setAttribute("aria-pressed", String(view[sec.id] === i));
      };
      card._update();
      return card;
    }
    function eyeCard(row) {
      const card = cardBox();
      const newRamp = el("span", { style: { height: "18px", borderRadius: "5px", border: "1px solid var(--line)" } });
      const pick = el("button", { class: "btn swatch", style: { padding: "4px", display: "grid", gap: "3px" }, "aria-label": `Show ${EYE_LABEL[row]} on the cat`,
        onclick: () => { if (row > 0) { view.eyeL = view.eyeR = row; renderPicks(); } drawCat(); refreshCards(); } },
        el("span", { style: { height: "18px", borderRadius: "5px", border: "1px solid var(--line)", background: rampCss(EYE_LIN[row]) } }), newRamp);
      const name = el("strong"), hex = el("span", { class: "hex muted" });
      const one = el("button", { class: "chip", text: "One colour", onclick: () => setMode("single") });
      const grad = el("button", { class: "chip", text: "Gradient", onclick: () => setMode("grad") });
      const inputs = el("div", { class: "row" });
      const reset = el("button", { class: "btn ghost small", text: "Reset", "aria-label": `Reset ${EYE_LABEL[row]}`, onclick: () => { delete state.eyes[row]; rebuild(); card._update(); drawCat(); renderTabs(); renderPicks(); } });
      card.append(pick, el("div", { class: "row spread" }, name, hex), el("div", { class: "row" }, one, grad, reset), inputs);
      const ensure = () => (state.eyes[row] ||= { mode: "single", colors: [vanillaRim(row)] });
      function setMode(mode) {
        const o = ensure();
        if (mode === "grad" && o.colors.length < 2) o.colors = ["#101418", o.colors[0]];
        if (mode === "single") o.colors = [o.colors[o.colors.length - 1]];
        o.mode = mode; target.markDirty(); rebuild(); card._update(); drawCat(); renderTabs();
      }
      function rebuild() {
        clear(inputs);
        const o = state.eyes[row];
        (o ? o.colors : [vanillaRim(row)]).forEach((c, k) => {
          const inp = el("input", { type: "color", id: `pal-eye-${row}-${k}`, value: c.toLowerCase(), "aria-label": `${EYE_LABEL[row]} colour ${k + 1}` });
          inp.addEventListener("input", () => { ensure().colors[k] = color.normHex(inp.value); target.markDirty(); card._update(); drawCat(); });
          inp.addEventListener("change", () => { renderTabs(); renderPicks(); });
          inputs.append(inp);
        });
        if (o && o.mode === "grad") {
          if (o.colors.length < 4) inputs.append(el("button", { class: "btn small", text: "+ stop", onclick: () => { o.colors.push(o.colors[o.colors.length - 1]); rebuild(); card._update(); drawCat(); } }));
          if (o.colors.length > 2) inputs.append(el("button", { class: "btn small", text: "− stop", onclick: () => { o.colors.pop(); rebuild(); card._update(); drawCat(); } }));
        }
      }
      card._update = () => {
        const o = state.eyes[row];
        newRamp.style.background = rampCss(eyeRamp(row, o));
        name.textContent = `${o ? "● " : ""}${EYE_LABEL[row]}`;
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
    function refreshCards() { panel.querySelectorAll(".card").forEach(c => c._update && c._update()); }
    function renderAll() { renderTabs(); renderPanel(); renderPicks(); drawCat(); renderPresets(); }

    await Promise.all([target.refresh(), renderQuick()]);
    return { unmount() { offInstalled(); } };
  },
};
