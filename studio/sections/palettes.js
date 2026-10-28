// Palettes: recolour the eyes, coats, patterns and markings every cat can wear, on a drawn cat, and add new pattern
// and marking colours. Writes palette.json in a mod; reading and writing it, and the whole-tab changes, are
// lib/palette.js. The page opens without the game's files: the eyes wait for the game folder, and the game's coat,
// pattern and marking colours show as numbered cards until the game has run once with the script loader.
import * as P from "../lib/palette.js";
import { catSvg, paintCat } from "../lib/cat.js";

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
    const eyeName = r => P.eyeWord(LABELS, r);   // "Eye white", "Extra eye 1", else the game's name

    let state = P.blank();
    let undo = null;   // { label, state }: the last whole-tab change, for its Undo button
    const view = { tab: LABELS ? "eyes" : "pattern", fur: 2, pattern: 3, marking: 10, eyeL: 2, eyeR: 2, vanilla: false };

    // ---------- layout ----------
    const target = wc.modTarget({
      file: "palette.json",
      onLoad: obj => { state = P.fromPalette(obj, { labels: LABELS, gameSlots: GAME }); undo = null; renderAll(); otherSlotsReady = loadOtherSlots(); },
      getValue: () => P.toPalette(state, LABELS),
      // Saved: the last whole-tab change can't be undone past it, and the page reads what it wrote as it reads any
      // file (a save doesn't read the file back), so what Save left out leaves the lists. Not when something changed
      // while it saved: that stays on the page, still to be saved.
      onSaved: (saved, { changed }) => {
        undo = null;
        if (changed) { renderStyleRow(); return; }
        state = P.fromPalette(saved, { labels: LABELS, gameSlots: GAME }); renderAll();
      },
    });
    // A change on the page: unsaved now, and the list of what the page can't show redrawn when an entry there is
    // now (or no longer) one the page's own takes the place of at Save.
    let replacedSeen = "";
    const edited = () => {
      target.markDirty();
      if (state.unread.length && replacedNow() !== replacedSeen) renderUnread();
    };
    const replacedNow = () => state.unread.map(u => (P.replaced(state, u) ? 1 : 0)).join("");
    // curHex: the colour a slot shows with this palette: its own, else the game's, else another palette's new one.
    const curHex = (sec, i) => state[sec][i] || TABLE(sec)[i] || otherHex(sec, i);

    const stage = el("div", { class: "cat-stage" });
    stage.innerHTML = catSvg("pal", "The drawn cat, in the colours chosen below");
    const svg = stage.querySelector("svg");
    const picks = el("div", { style: { display: "grid", gridTemplateColumns: "auto minmax(0,1fr)", gap: "8px 12px", alignItems: "center" } });
    // Which colours the drawn cat shows: this palette's, or the game's own (to compare).
    const shows = el("div", { class: "row", role: "group", "aria-label": "Cat shows" }, el("span", { class: "muted", text: "Cat shows:" }));
    for (const [vanilla, text] of [[false, "my colours"], [true, "the game's"]]) {
      shows.append(el("button", { class: "chip", type: "button", text, "aria-pressed": String(view.vanilla === vanilla), onclick: () => {
        view.vanilla = vanilla;
        shows.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.textContent === text)));
        drawCat();
      } }));
    }
    const tabs = el("div", { class: "row", role: "tablist", "aria-label": "Palette sections" });
    const panel = el("div", { role: "tabpanel", id: "pal-panel", style: { display: "grid", gap: "16px" } });
    const startRow = el("div", { class: "row pal-row" });
    const styleRow = el("div", { class: "row pal-row" });
    const tablesLine = el("p", { class: "note heads-up pal-tables", hidden: true });
    const unreadBox = el("div", { hidden: true });
    const strip = el("div", { class: "card pal-strip" });
    // Switching between ready-made palettes: folded, and left open or folded as it was through a redraw.
    const quick = el("details", { class: "card fold pal-quick" });
    let quickOpen = false;
    quick.addEventListener("toggle", () => { quickOpen = quick.open; });

    root.append(
      wc.pageHead({ eyebrow: "Appearance only", title: "Palettes",
        lede: "Recolour the eyes, coats, patterns and markings every cat can wear, or add new pattern and marking colours. " +
          "A cat keeps the colour it has (coat 3 stays coat 3), so its traits don't change. Eye colours go in through the " +
          "game's files; the rest need the script loader.",
        help: "help:palettes" }),
      strip, quick, target.element, startRow, styleRow,
      el("div", { style: { display: "grid", gridTemplateColumns: "minmax(260px, 360px) minmax(0, 1fr)", gap: "24px", alignItems: "start" }, class: "pal-grid" },
        el("div", { class: "card", style: { position: "sticky", top: "84px" } }, stage, shows, picks,
          el("p", { class: "note", text: "In the game, paws, ears, nose and whiskers follow the coat; this drawing can't show them, nor the game's real pattern shapes." })),
        el("div", { style: { display: "grid", gap: "12px", minWidth: "0" } }, tabs, tablesLine, unreadBox, panel)));
    const narrow = window.matchMedia("(max-width: 900px)");
    const applyNarrow = () => { root.querySelector(".pal-grid").style.gridTemplateColumns = narrow.matches ? "minmax(0,1fr)" : "minmax(260px, 360px) minmax(0, 1fr)"; };
    narrow.addEventListener("change", applyNarrow); applyNarrow();

    // ---------- quick palettes ----------
    // Mods that hold only a palette work as presets: Apply turns the ticked ones on, the other
    // palette-only mods off, and installs. Mods with anything besides a palette aren't touched, and
    // neither are palettes that only add new colours (cats may be wearing them).
    let quickPick = null;     // ids ticked here; null means "start from what's on"
    let quickData = [];       // [{mod, palette (null if its file can't be read)}]
    let quickOn = new Map();  // each one's on or off when the list was last read
    const quickButtons = el("div", { class: "row" });
    // The list is read again after an Apply (fresh: the ticks start from what's on) and whenever a mod is made or
    // changed (a Save to mod makes My mods, or turns its mod on): a palette switched on or off since the last read
    // is ticked or unticked to match, and the creator's other ticks stay. One read after another, so an earlier one
    // never draws over a later one.
    let quickQueue = Promise.resolve();
    const renderQuick = (fresh = false) => (quickQueue = quickQueue.catch(() => {}).then(() => readQuick(fresh)));
    async function readQuick(fresh) {
      const list = (await api.get("/mods")).filter(m => m.preset);
      quickData = await Promise.all(list.map(async m => {
        try { return { mod: m, palette: JSON.parse((await api.get(`/mods/${encodeURIComponent(m.id)}/file/palette.json`)).text) || {} }; }
        catch (e) { return { mod: m, palette: null }; }
      }));
      if (fresh || quickPick === null) quickPick = new Set(list.filter(m => m.enabled).map(m => m.id));
      else {
        for (const m of list) {
          const was = quickOn.get(m.id);
          if (m.enabled && was !== true) quickPick.add(m.id);
          else if (!m.enabled && was === true) quickPick.delete(m.id);
        }
        for (const id of [...quickPick]) if (!list.some(m => m.id === id)) quickPick.delete(id);   // not a quick palette now
      }
      quickOn = new Map(list.map(m => [m.id, m.enabled]));
      drawQuick();
    }
    // Apply: unsaved colours on this page go in too, saved first (nothing is installed if that fails). The palette
    // just saved is ticked, whatever the list said before: Apply turns an unticked quick palette off, and with it
    // the colours just saved (a first Save makes My mods, which the list hadn't got).
    async function applyQuick() {
      if (target.dirty) {
        const before = new Set(quickPick || []);
        if (!await target.save()) return;
        await renderQuick();
        const saved = quickData.find(d => d.mod.id === target.current && d.palette !== null);
        if (saved && !before.has(saved.mod.id)) {
          quickPick.add(saved.mod.id);
          drawQuick();
          toast(`Ticked ${saved.mod.name} too, so the colours you just saved go in.`);
        }
      }
      wc.bus.emit("run-task", { path: "/palettes/apply", title: "Apply palettes", body: { ids: [...(quickPick || [])], install: true } });
    }
    // Why Apply waits, in the shell's words (app.js greys its own Apply for the same reasons).
    const applyWait = () => (!info ? "" : !info.game_dir ? "Find the game first: Get set up, on the Mods page"
      : info.game_running ? "Close the game first" : "");
    async function readInfo() {
      try { info = await api.get("/info"); } catch (e) { /* keep the last answer */ }
      drawQuickButtons();
      renderStrip();
    }

    // ---------- what reaches the game ----------
    // Each kind of colour and what it needs: eyes go in through the game's files; coat, pattern and marking colours
    // through the script loader; new colours and coat presets reach the cat maker only with the Creator palettes mod
    // (which runs code). Read again after an Apply, a change to the mods, and on coming back to the window.
    const CREATOR = { id: "creator-palettes", url: "https://github.com/HexOffender/wcmods-creator-palettes" };
    async function renderStrip() {
      let mods = [];
      try { mods = await api.get("/mods"); } catch (e) { /* the bar says what's wrong */ }
      const creator = mods.find(m => m.id === CREATOR.id);
      const link = () => el("a", { href: CREATOR.url, target: "_blank", rel: "noopener", text: "the Creator palettes mod" });
      const line = (what, ready, ...said) => el("li", { class: "row" },
        el("span", { class: `chip ${ready ? "good" : "warn"}`, "data-said": ready ? "ready" : "not yet" },
          el("i", { "aria-hidden": "true" }), ready ? "ready" : "not yet"),
        el("strong", { text: what }), el("span", { class: "muted" }, ...said));
      const loader = !!(info && info.ue4ss), code = !!(info && info.allow_code_mods);
      const built = info && info.installed && info.installed.built;
      put(strip, el("h2", { text: "What reaches the game" }),
        el("ul", { class: "pal-strip-lines" },
          line("Eye colours", true, "through the game's own files"),
          line("Coat, pattern and marking colours", loader,
            loader ? "through the script loader" : "need the script loader: Get set up, on the Mods page, installs it"),
          line("New colours and coat presets in the cat maker", !!(creator && creator.enabled && loader && code),
            ...(!creator ? ["need ", link(), ", added on the Mods page"]
              : !creator.enabled ? ["Creator palettes is in your mods but off: switch it on, on the Mods page"]
              : !code ? ["Creator palettes is on, but mods that run code aren't allowed (Settings and repair)"]
              : !loader ? ["Creator palettes needs the script loader too"]
              : ["with Creator palettes"]))),
        el("p", { class: "note", text: built ? `Your mods last went in the game ${new Date(built).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}.`
          : "Nothing has gone in the game yet: Apply to game, at the top, puts your mods in." }));
    }
    function drawQuickButtons() {
      const n = quickPick ? quickPick.size : 0, why = applyWait();
      put(quickButtons,
        el("button", { class: "btn primary", text: n ? `Apply ${n} and install` : "Use the game's colours and install", disabled: !!why,
          title: why || "Turns the ticked palettes on and the other palette-only mods off, then puts them in the game", onclick: applyQuick }),
        el("button", { class: "btn ghost", text: "Untick all", onclick: () => { quickPick?.clear(); drawQuick(); } }),
        why ? el("span", { class: "muted", text: why }) : null);
    }
    function drawQuick() {
      if (quickPick === null) return;   // not read yet
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
        box.addEventListener("change", () => { if (box.checked) quickPick.add(m.id); else quickPick.delete(m.id); drawQuick(); });
        const swatches = broken ? [el("span", { class: "chip warn", text: "Its palette can't be read: the Mods page says why" })] : [
          el("div", { class: "row pal-dots", title: "Coats 0-14" }, el("span", { class: "muted", text: "coats" }),
            ...[...Array(15).keys()].map(s => dot(color.parse(p.fur?.[String(s)]) || TABLE("fur")[s] || "#888888"))),
          LABELS ? el("div", { class: "row pal-dots", title: "Eyes" }, el("span", { class: "muted", text: "eyes" }),
            ...GROUPS.standard.map(r => dot(eyeRim(p, r), true))) : null];
        return el("label", { for: `quick-${m.id}`, style: { display: "grid", gap: "6px", padding: "10px 12px", borderRadius: "10px",
            border: "1px solid var(--line, rgba(0,0,0,.12))", cursor: broken ? "default" : "pointer" } },
          el("div", { class: "row" }, box, el("strong", { text: m.name }),
            m.enabled ? el("span", { class: "chip", text: "on" }) : null),
          el("span", { class: "muted", style: { fontSize: "0.8rem" }, text: m.description || m.id }), ...swatches);
      });
      drawQuickButtons();
      // Two ticked palettes that both change the coats, or both the eyes: only the later one's show.
      const ticked = quickData.filter(d => d.palette && quickPick.has(d.mod.id));
      const twice = part => ticked.filter(d => Object.keys(d.palette[part] || {}).some(k => !k.startsWith("_"))).length > 1;
      put(quick, el("summary", {}, el("h2", { text: "Switch between ready-made palettes" }),
          el("span", { class: "muted", text: quickData.length ? `${quickData.length} palette mod${quickData.length === 1 ? "" : "s"}` : "none yet" })),
        el("p", { class: "note", text: "Tick the palettes to use, then Apply: it switches the ticked ones on and the other palettes that hold nothing else off, and puts them in the game. Mods with more than a palette in them, and palettes that only add new colours, aren't touched." }),
        el("p", { class: "note", text: "Pick one full theme; a palette that changes only the eyes or only the coats goes on top of it. To change one, choose it under Editing mod below." }),
        tiles.length ? null : el("p", { class: "empty", text: "No palette mods yet. Ten themed palettes, and palettes for eyes and coats, are in wcmods-examples (Add a mod, on the Mods page, says where)." }),
        el("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: "10px" } }, ...tiles),
        twice("fur") || twice("eyes") ? el("p", { class: "note heads-up", role: "status",
          text: `Two of the ticked palettes change the ${twice("fur") ? "coats" : "eyes"}: only the one later in the Mods list shows. Untick one.` }) : null,
        quickButtons);
      quick.open = quickOpen;
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
          onclick: () => {
            const eyesOutOfSight = !LABELS && state.kept.eyes !== undefined;
            wholeTab("Game colours", P.gameColours(state, GAME));
            if (eyesOutOfSight) toast("The file's eye colours went too, though this page can't show them until it finds the game's. Undo puts them back.");
          } }),
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
      replacedSeen = replacedNow();
      clear(unreadBox);
      const n = state.unread.length;
      unreadBox.hidden = !n;
      if (!n) return;
      const box = el("details", { class: "card fold pal-unread", open: unreadOpen },
        el("summary", {}, el("strong", { text: `${n} ${n === 1 ? "entry" : "entries"} this page can't show` }),
          el("span", { class: "muted", text: "kept in the file as written until you remove them" })),
        el("ul", { class: "notes" }, ...state.unread.map((u, i) => el("li", { class: "row" },
          el("span", { text: P.describeUnread(u, state) }),
          el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${P.describeUnread(u)}`,
            onclick: () => { state.unread.splice(i, 1); edited(); renderUnread(); } })))));
      box.addEventListener("toggle", () => { unreadOpen = box.open; });
      unreadBox.append(box);
    }

    // ---------- cat ----------
    function drawCat() {
      const pick = sec => (view.vanilla ? TABLE(sec)[view[sec]] : curHex(sec, view[sec])) || NEUTRAL;
      const eye = row => P.eyeRamp(origRow(row), view.vanilla ? null : state.eyes[row]);
      paintCat(svg, { coat: pick("fur"), pattern: pick("pattern"), marking: pick("marking"), eyeWhite: rimOf(eye(0)),
        rightEye: eye(view.eyeR), leftEye: eye(view.eyeL) });
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
        const eyeOpts = LABELS.slice(1).map((l, i) => [i + 1, `${eyeName(i + 1)}${GROUPS.extra.includes(i + 1) ? " (from a game add-on)" : ""}${state.eyes[i + 1] ? " (changed)" : ""}`]);
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
    // A colour's code as text, beside its picker: it shows the colour now, takes any colour a palette.json may
    // hold (a code someone shared, a name like "orange", "255, 136, 0") on Enter or when it's left, and selects
    // itself when clicked, ready to copy. sync() shows the colour again (not while it's being typed in).
    function codeBox(label, current, take) {
      const box = el("input", { type: "text", class: "code-box", spellcheck: "false", autocomplete: "off", size: "9", "aria-label": label });
      box.addEventListener("focus", () => box.select());
      const commit = () => {
        const text = box.value.trim();
        if (text === (current() || "")) return;   // nothing new (Enter, then leaving the box)
        const c = color.parse(/^\d+\s*,\s*\d+\s*,\s*\d+$/.test(text) ? text.split(",").map(Number) : text);
        if (!c) {
          toast(`"${text}" isn't a colour: try a code like #FF8800, or a name like orange`, "bad");
          box.value = current() || "";
          return;
        }
        take(c);
        box.value = c;
      };
      box.addEventListener("change", commit);
      box.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); commit(); } });
      box.sync = () => { if (document.activeElement !== box) box.value = current() || ""; };
      return box;
    }
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
      const name = el("strong");
      const inp = el("input", { type: "color", id: `pal-${sec.id}-${i}`, "aria-label": `New colour for ${sec.noun} colour ${i}` });
      inp.addEventListener("input", () => { state[sec.id][i] = color.normHex(inp.value); edited(); card._update(); drawCat(); });
      inp.addEventListener("change", () => { renderTabs(); renderPicks(); });
      const code = codeBox(`Colour code for ${sec.noun} colour ${i}`, () => curHex(sec.id, i),
        c => { state[sec.id][i] = c; edited(); card._update(); drawCat(); renderTabs(); renderPicks(); });
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
      card.append(pair, name, el("div", { class: "row" }, inp, code, reset));
      card._update = () => {
        const cur = curHex(sec.id, i), changed = !!state[sec.id][i];
        newSw.style.background = cur || "";
        newSw.className = cur ? "" : "pal-unknown";
        name.textContent = isNew ? `New ${sec.noun} colour ${i}` : `${changed ? "● " : ""}${sec.noun[0].toUpperCase()}${sec.noun.slice(1)} ${i}`;
        name.style.color = changed && !isNew ? "var(--changed)" : "";
        code.sync();
        code.placeholder = cur ? "" : "after one Play";
        code.title = changed && orig ? `The game's: ${orig}` : "";
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
      const name = el("strong"), hex = el("span", { class: "muted" });
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
          const code = codeBox(`Colour code for ${eyeName(row)}${o && o.mode === "grad" ? `, colour ${k + 1}` : ""}`,
            () => (state.eyes[row] ? state.eyes[row].colors[k] : vanillaRim(row)),
            c2 => { ensure().colors[k] = c2; inp.value = c2.toLowerCase(); edited(); card._update(); drawCat(); renderTabs(); renderPicks(); });
          inp.addEventListener("input", () => { ensure().colors[k] = color.normHex(inp.value); code.sync(); edited(); card._update(); drawCat(); });
          inp.addEventListener("change", () => { renderTabs(); renderPicks(); });
          code.sync();
          inputs.append(el("span", { class: "row pal-stop" }, inp, code));
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
        hex.textContent = o ? (o.mode === "grad" ? `${o.colors.length}-colour gradient` : `the game's ${vanillaRim(row)}`) : "the game's colour";
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

    // After an Apply or Play: the quick palettes (their ticks afresh) and the status are read again, and the file too,
    // unless there are unsaved changes here (installedEvent), which stay, the bar saying they aren't in the game yet.
    // A mod made or changed anywhere (a Save here makes My mods) reads the quick palettes again too.
    const offs = [
      wc.installedEvent(target, () => target.refresh()),
      wc.bus.on("installed", () => { renderQuick(true).catch(() => {}); readInfo(); }),
      wc.bus.on("focus", readInfo),
      wc.bus.on("mods-changed", () => { renderPresets(); renderStrip(); otherSlotsReady = loadOtherSlots(); renderQuick().catch(() => {}); }),
    ];
    await Promise.all([target.refresh(), renderQuick(), renderStrip()]);
    return { unmount() { for (const off of offs) off(); narrow.removeEventListener("change", applyNarrow); } };
  },
};
