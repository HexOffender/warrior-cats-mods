// Game data: change the numbers the game plays by. Quick changes for the ones people ask for, a search across
// every table, and every table behind a fold. Writes data.json in a mod; the logic is studio/lib/data.js.
import * as D from "../lib/data.js";

const GROUPS = [
  { title: "Progress and rewards", match: n => /^(CombatBaseExperience|SkirmishRank|Consumables|BarteringCost|HousingCost|QuestGossipCost|VisitRewards|OnlineGifts)\.csv$/.test(n) },
  { title: "Tuning", match: n => n === "TuningData.csv" },
  { title: "Fights", match: n => /^(AttackMove|CharacterAttacks|CharacterStatsBase|ClanSpecificBase|CombatStance|AICombatChances|CombatDilemmas)\.csv$/.test(n) || n.startsWith("Effects/") },
  { title: "Cats and names", match: n => n.startsWith("NPC/") || /^(PrefixNameFilters|SuffixNameFilters|TraitsFilters)\.csv$/.test(n) },
  { title: "Other", match: () => true },
];
// Each table's kind comes from the server (wcmods/sections/files.py classify), so the chips match the build's
// warnings. Their meaning is said in the chip, not only on hover.
const KIND_INFO = {
  online: ["bad", "Online", "Online: the den-visit server may ignore changes here"],
  traits: ["warn", "Traits", "Traits: changes which personality new cats get"],
  appearance: ["good", "Looks", "Appearance only"],
  story: ["warn", "Story", "Quests and talk: a wrong value can stop a quest"],
  gameplay: ["", "", ""],
};
const QUICK_TABLES = () => [...new Set(quickRows().map(q => q.table))];
let quickData = { rows: [], groups: [], checked: "" };
const quickRows = () => quickData.rows || [];
const NONASSET = "Wrc/Content/Gameplay/DataTables/NonAsset/";

// A data file next to this page (data-quick.json, data-titles.json): plain data, not code.
async function staticJson(name) {
  const res = await fetch(`/studio/sections/${name}`);
  if (!res.ok) throw new Error(`${name} didn't load`);
  return res.json();
}

export default {
  title: "Game data",
  async mount(root, wc) {
    const { el, api, clear, toast } = wc;
    let edits = {}, rowOps = {}, fileNotes = { top: {}, tables: {} };   // the file's own "_" keys, kept as they are
    let names = [], kinds = {}, hidden = [], titles = {}, notes = {}, index = null, indexing = null;
    const cache = {}, loading = {};   // table -> its rows (GET /game/data/<table>); the request on its way
    const views = {};                 // table -> what the grid had: its filter, the multiply choices, its scroll
    let current = null;               // the table open in All tables

    const headers = () => Object.fromEntries(Object.entries(cache).map(([n, t]) => [n, t.header]));
    const target = wc.modTarget({
      file: "data.json",
      onLoad: obj => {
        // A file the page didn't write may hold anything: what isn't a table's changes is said and left out.
        const c = D.clean(obj);
        edits = c.edits; rowOps = c.rowOps; fileNotes = c.notes;
        baseline = snapshot();
        if (c.skipped.length) toast(`data.json has ${c.skipped.join(", ")}, which isn't a table's changes; it's left out when you save`, "bad");
        changed(false);
      },
      getValue: () => D.toJson(edits, rowOps, headers(), fileNotes),
    });
    const out = wc.codePanel("data.json");
    const problem = el("div", { hidden: true });
    const findBox = el("input", { type: "search", id: "data-find", placeholder: "run, xp, mouse, scars, build time", "aria-label": "Find a number by what it does", autocomplete: "off" });
    const findResults = el("ul", { class: "find-results", id: "data-find-results", "aria-live": "polite" });
    const quickBox = el("div", { class: "card", id: "data-quick" });
    const listBox = el("div", { class: "card data-list" });
    const tableBox = el("div", { class: "stack data-table", style: { minWidth: "0" } });
    const yours = el("div", { class: "stack", id: "data-yours" });
    const allFold = el("details", { class: "card fold", id: "data-all" },
      el("summary", {}, el("h2", { text: "All tables" }), el("span", { class: "muted", text: "Every table the game plays by, cell by cell" })),
      yours,
      el("div", { class: "data-grid" }, listBox, tableBox));
    const makersFold = el("details", { class: "card fold" },
      el("summary", {}, el("h2", { text: "For mod makers" }), el("span", { class: "muted", text: "The data.json this page writes" })),
      el("p", { class: "note", text: "Every change on this page is a line in data.json: a table, a row by its first column (\"*\" is every row), a column and a value. docs/formats.md says the rest." }),
      out.element);

    root.append(
      wc.pageHead({ eyebrow: "Gameplay", title: "Game data", help: "help:data",
        lede: "Change the numbers the game plays by: how fast you run, how much a fight is worth, what prey is worth, how big the Clan cats are. Your changes go in a mod; the game's own files stay as they are." }),
      target.element, problem,
      el("div", { class: "card" }, el("h2", { text: "Find a number" }),
        el("label", { class: "field" }, el("span", { class: "lbl", text: "Find a number by what it does" }), findBox), findResults),
      quickBox, allFold, makersFold);

    // ---------- after any change ----------
    // dirty: the page has something to save. The open table's cells, the list's counts, the quick rows and the
    // file panel follow; a rebuild of the grid keeps its filter, multiply choices and scroll.
    let tableHook = null;   // the open table's parts that follow a change without a rebuild (Put this table back)
    // What the page holds, to tell a change from a change undone (Normal after a drag): back to the file is clean.
    let baseline = "";
    const snapshot = () => JSON.stringify(D.toJson(edits, rowOps, {}, fileNotes));
    function changed(dirty = true, rebuild = true) {
      if (dirty) { if (snapshot() === baseline) target.markClean(); else target.markDirty(); }
      out.set(D.toJson(edits, rowOps, headers(), fileNotes));
      renderList();
      refreshQuick();
      renderYours();
      if (rebuild && current && cache[current]) renderTable();
      else tableHook?.();
    }

    // ---------- Your changes, and what's in the game ----------
    // applied: what the last Apply from this studio put in the game (its manifest's csv_changes), for "in the
    // game since 15:30". It comes with the "installed" event (wc.bus.on: whether or not the page has unsaved
    // changes), and nothing is read again for it. Before an Apply here, nothing is said either way.
    let applied = null;
    const since = (t, row, column, value) => applied && applied.mods.includes(target.current)
      && applied.cells.get(`${t}|${row}|${column}`) === String(value) ? applied.when : null;
    const said = when => (applied && applied.mods.includes(target.current) ? (when ? `in the game since ${when}` : "not in the game yet") : null);
    const asked = new Set();   // tables Your changes has asked for, once each
    function renderYours() {
      const list = D.changeList(edits, rowOps, cache);
      for (const c of list) {
        if (cache[c.table] || !inGame(c.table) || asked.has(c.table)) continue;
        asked.add(c.table);
        getTable(c.table).then(() => renderYours()).catch(() => { /* its line says ? for the game's value */ });
      }
      clear(yours).append(el("h3", { text: "Your changes" }));
      if (!list.length) { yours.append(el("p", { class: "muted", text: "This mod doesn't change any table yet." })); return; }
      const ul = el("ul", { class: "changes" });
      for (const c of list) {
        let words, mark = null, undo;
        if (c.kind === "cell") {
          words = `${title(c.table)}: ${D.rowName(cache[c.table], c.row)}, ${c.column}: ${c.was ?? "?"} -> ${c.now}`;
          mark = said(since(c.table, c.row, c.column, c.now));
          undo = () => { D.unsetCell(edits, c.table, cache[c.table]?.header, c.row, c.column); changed(); };
        } else if (c.kind === "all") {
          words = `${title(c.table)}: ${c.said}`;
          const any = applied && [...applied.cells.keys()].some(k => k.startsWith(`${c.table}|`) && k.endsWith(`|${c.column}`));
          mark = said(any ? applied.when : null);
          undo = () => { D.unsetCell(edits, c.table, cache[c.table]?.header, "*", c.column); changed(); };
        } else {
          words = `${title(c.table)}: ${c.said}`;
          undo = () => { delete rowOps[c.table]; changed(); };
        }
        ul.append(el("li", { class: "row" }, el("span", { text: words }), mark ? el("span", { class: "muted", text: `(${mark})` }) : null,
          el("button", { class: "btn ghost small", type: "button", text: c.kind === "rows" ? "Remove" : "Normal", "aria-label": `Put back ${words}`, onclick: undo })));
      }
      yours.append(ul);
    }

    // ---------- reading tables ----------
    function getTable(n) {
      if (cache[n]) return Promise.resolve(cache[n]);
      return loading[n] ||= api.get(`/game/data/${n.split("/").map(encodeURIComponent).join("/")}`)
        .then(t => { cache[n] = t; return t; })
        .finally(() => { delete loading[n]; });
    }
    const title = n => D.tableTitle(n, titles);
    const inGame = n => names.includes(n) || (n.startsWith(NONASSET) && names.includes(n.slice(NONASSET.length)));

    // ---------- Find a number ----------
    let findTimer = null;
    async function find() {
      const q = findBox.value.trim();
      if (q && !index && !indexing) {
        indexing = api.get("/game/data/index").then(r => { index = r.tables; }).catch(() => { index = {}; })
          .finally(() => { indexing = null; if (findBox.value.trim()) find(); });
      }
      const hits = D.search(q, { quick: quickRows(), titles, notes, index: index || {} });
      clear(findResults);
      if (!q) return;
      for (const h of hits) {
        findResults.append(el("li", {}, el("button", { class: "btn ghost hit", type: "button", onclick: () => go(h) },
          el("strong", { class: h.kind === "row" ? "mono" : false, text: h.text }),
          el("span", { class: "muted", text: ` ${h.where || ""}` }))));
      }
      if (indexing) findResults.append(el("li", { class: "muted", text: "Looking through every table…" }));
      else if (!hits.length) findResults.append(el("li", { class: "muted", text: `Nothing called "${q}". Try another word: run, xp, prey, scars, den.` }));
    }
    findBox.addEventListener("input", () => { clearTimeout(findTimer); findTimer = setTimeout(find, 120); });
    async function go(hit) {
      if (hit.kind === "quick") {
        const row = quickBox.querySelector(`[data-key="quick:${CSS.escape(hit.id)}"]`);
        if (!row) return;
        row.closest("details").open = true;
        row.scrollIntoView({ block: "center" });
        row.querySelector('input[type="number"]')?.focus();
        return;
      }
      allFold.open = true;
      await openTable(hit.table, { row: hit.row });
    }

    // ---------- Quick changes ----------
    const quickRefresh = [];   // one function per quick row: draws its value again from the edits
    function renderQuick() {
      quickRefresh.length = 0;
      clear(quickBox).append(el("h2", { text: "Quick changes" }),
        el("p", { class: "note", text: "The changes people ask for most. Each one is an ordinary change to a table: it shows in All tables and in data.json too." }),
        el("p", { class: "muted", text: quickData.checked || "" }));
      (quickData.groups || []).forEach((g, gi) => {
        const rows = quickRows().filter(q => q.group === g);
        if (!rows.length) return;
        const fold = el("details", { class: "fold quick-group", open: gi === 0 }, el("summary", {}, el("h3", { text: g })));
        for (const q of rows) fold.append(quickRow(q));
        quickBox.append(fold);
      });
    }
    function quickRow(q) {
      const box = el("div", { class: "quick-row", "data-key": `quick:${q.id}` });
      const table = () => cache[q.table];
      const id = `quick-${q.id}`;
      const num = el("input", { type: "number", id, min: q.min, max: q.max, step: q.step || "any", "aria-label": q.label });
      const slider = el("input", { type: "range", min: q.min, max: q.max, step: q.step || "any", "aria-label": `${q.label}, slider`, tabindex: "-1" });
      const normalBtn = el("button", { class: "btn small ghost", type: "button", text: "Normal", "aria-label": `Put ${q.label} back to normal` });
      const now = el("span", { class: "quick-now" });
      const preview = el("p", { class: "muted quick-preview" });
      // A change over the file's own edit of these cells asks first (quickHand): never replaced without a word.
      const ask = el("div", { class: "row quick-ask", role: "group", "aria-label": `${q.label}: replace the value set by hand?`, hidden: true });
      const short = q.row && q.row !== "*" ? q.row.split(".").slice(-2).join(".") : q.row === "*" ? "every row" : `${(q.rows || []).length} rows`;
      box.append(
        el("div", { class: "quick-head" }, el("label", { for: id, class: "lbl", text: q.label }), now),
        el("div", { class: "row quick-controls" }, slider, num, el("span", { class: "muted", text: q.unit || "" }), normalBtn),
        ask,
        el("p", { class: "note", text: q.what }),
        preview,
        el("p", { class: "muted where" }, `Where: ${title(q.table)}, ${short}${(q.columns || [q.column]).length > 1 ? ` (${q.columns.join(", ")})` : ""}. `,
          q.doc ? wc.docLink(q.doc, "How it works") : null));
      const draw = () => {
        const t = table();
        if (!t) {
          box.classList.add("missing");
          num.disabled = slider.disabled = normalBtn.disabled = true;
          now.textContent = names.length && !inGame(q.table) ? "The game hasn't got this table" : "Loading…";
          return;
        }
        if (!D.quickCells(q, t).length) {
          num.disabled = slider.disabled = normalBtn.disabled = true;
          now.textContent = "The game's table hasn't got this row";
          return;
        }
        num.disabled = slider.disabled = false;
        const normal = D.quickNormal(q, t), value = D.quickCurrent(q, t, edits[q.table]);
        const edited = D.quickEdited(q, t, edits[q.table]), hand = D.quickHand(q, t, edits[q.table]);
        if (document.activeElement !== num) num.value = String(value);
        slider.value = String(value);
        normalBtn.disabled = !edited;
        box.classList.toggle("edited", edited);
        // The file's own edit, said as it is (the box can't hold "0.08" as a factor), not as a change of the row's.
        now.textContent = hand ? `This row is ${hand}, in data.json` : edited ? `${q.kind === "factor" ? "×1" : normal} -> ${q.kind === "factor" ? "×" + value : value}` : `Normal: ${q.kind === "factor" ? "×1" : normal}`;
        if (edited) {
          // In the game when every cell it changes has, in the last Apply, the value it shows.
          const all = D.quickCells(q, t).every(c => {
            const v = D.valueFor(edits[q.table], t.header, t.rows.find(r => r[0] === c.row), c.index);
            return !v || v.bad || since(q.table, c.row, c.column, v.value);
          });
          const mark = said(all ? applied?.when : null);
          if (mark) now.textContent += ` · ${mark}`;
        }
        preview.textContent = q.kind === "factor" && !hand ? D.quickPreview(q, t, value, q.names || {}, edits[q.table]) : "";
        preview.hidden = !preview.textContent;
      };
      const hideAsk = () => { ask.hidden = true; clear(ask); };
      const write = (raw, replace = false) => {
        const t = table();
        if (!t) return;
        hideAsk();
        const r = D.quickWrite(q, t, edits, raw, { replace });
        if (r.error) { toast(r.error, "bad"); draw(); return; }
        if (r.hand) {
          const to = q.kind === "factor" ? `×${D.readNumber(raw)}` : String(D.readNumber(raw));
          ask.append(el("span", { text: `This row is ${r.hand} in data.json. Replace that with ${to}?` }),
            el("button", { class: "btn small", type: "button", text: "Replace it", onclick: () => { write(raw, true); num.focus(); } }),
            el("button", { class: "btn small ghost", type: "button", text: "Keep it", onclick: () => { hideAsk(); draw(); num.focus(); } }));
          ask.hidden = false;
          wc.announce(ask.firstChild.textContent);
          return;
        }
        changed(true, current === q.table);
      };
      slider.addEventListener("input", () => { num.value = slider.value; const t = table(); if (t && q.kind === "factor" && !D.quickHand(q, t, edits[q.table])) preview.textContent = D.quickPreview(q, t, Number(slider.value), q.names || {}, edits[q.table]); });
      slider.addEventListener("change", () => write(slider.value));
      num.addEventListener("change", () => write(num.value));
      num.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); write(num.value); } });
      normalBtn.addEventListener("click", () => { const t = table(); if (t) write(D.quickNormal(q, t)); num.focus(); });
      quickRefresh.push(draw);
      draw();
      return box;
    }
    function refreshQuick() { for (const draw of quickRefresh) draw(); }

    // ---------- the list of tables ----------
    function renderList() {
      clear(listBox).append(el("h3", { text: "Tables" }));
      const shown = new Set();
      for (const g of GROUPS) {
        const items = names.filter(n => !shown.has(n) && !hidden.includes(n) && g.match(n));
        if (!items.length) continue;
        items.forEach(n => shown.add(n));
        listBox.append(el("span", { class: "eyebrow", text: g.title }));
        for (const n of items) {
          const [cls, short] = KIND_INFO[kinds[n] || "gameplay"] || KIND_INFO.gameplay;
          const c = D.countEdits(edits, rowOps, n);
          listBox.append(el("button", {
            class: "btn ghost table-pick", "aria-current": current === n ? "true" : false, "data-focus": `table:${n}`, type: "button",
            onclick: () => openTable(n),
          }, el("span", { text: title(n) }),
            el("span", { class: "row" }, c ? el("span", { class: "count", text: String(c), "aria-label": `${c} change${c === 1 ? "" : "s"}` }) : null,
              short ? el("span", { class: `chip ${cls}`, text: short }) : null)));
        }
      }
      // What the file changes that isn't in the list: a table the game hasn't got, or map data the page doesn't list.
      const extra = [...new Set([...Object.keys(edits), ...Object.keys(rowOps)])].filter(n => !inGame(n) || hidden.includes(n));
      for (const n of extra) {
        const why = inGame(n) ? "map data this page doesn't list" : "a table the game doesn't have";
        listBox.append(el("p", { class: "note also" }, `This mod also changes ${why}: `, el("span", { class: "mono", text: n }), " ",
          el("button", { class: "btn small ghost", type: "button", text: "Remove", "aria-label": `Remove the changes to ${n}`,
            onclick: () => { delete edits[n]; delete rowOps[n]; delete fileNotes.tables[n]; changed(); } })));
      }
    }

    // ---------- a table ----------
    async function openTable(n, opts = {}) {
      current = n;
      const view = (views[n] ||= { filter: "", mulCol: null, mulBy: "2", scroll: 0 });
      if (opts.row !== undefined) { view.filter = opts.row; view.scroll = 0; }
      renderList();
      if (!cache[n]) clear(tableBox).append(el("p", { class: "muted", text: `Loading ${title(n)}…` }));
      try {
        await getTable(n);
      } catch (e) {
        if (current === n) clear(tableBox).append(el("div", { class: "error-card" }, el("p", { text: e.message })));
        return;
      }
      if (current !== n) return;   // another table was picked while this one loaded: that one shows
      renderTable({ focusRow: opts.row });
      changed(false, false);       // its header is known now: a {row: value} edit gets its column's name
    }

    function renderTable({ focusRow } = {}) {
      const t = cache[current];
      if (!t) return;
      const n = current, view = views[n];
      const { header, rows } = t, texts = t.texts || {};
      const colKinds = header.map((_, i) => D.columnKind(header, rows, i, n));
      const tEdits = () => edits[n] || {};
      const [kindCls, , kindSaid] = KIND_INFO[kinds[n] || "gameplay"] || KIND_INFO.gameplay;
      const label = i => i === 1 && titles[n]?.value ? titles[n].value : D.headerLabel(header[i], i);
      const wrapOld = tableBox.querySelector(".table-wrap");
      if (wrapOld) view.scroll = wrapOld.scrollTop;

      const filterBox = el("input", { type: "search", id: "data-row-filter", placeholder: "Filter rows", "aria-label": "Filter rows", value: view.filter });
      const body = el("tbody");
      // What the mechanics notes say about the table and its rows (data-notes.json).
      const told = D.notesFor(n, rows.map(r => r[0]), notes);
      const aboutTable = titles[n]?.what ? null : told.table[0];
      const noted = Object.keys(told.rows).length;
      const card = el("div", { class: "card" },
        el("div", { class: "row spread" }, el("h2", {}, title(n), " ", el("span", { class: "muted mono file", text: n })),
          kindSaid ? el("span", { class: `chip ${kindCls}` }, el("i"), kindSaid) : null),
        titles[n]?.what ? el("p", { class: "note" }, titles[n].what, ". ", titles[n].doc ? wc.docLink(titles[n].doc, "How it works") : null) : null,
        aboutTable ? el("p", { class: "note" }, aboutTable.text, " ", wc.docLink(`docs/mechanics/${aboutTable.doc}${aboutTable.anchor}`, "How it works")) : null,
        el("p", { class: "note", text: `${rows.length} rows. Press Enter on a value to change it, or click it; arrow keys move between values.${rows.some((r, i) => rows.findIndex(x => x[0] === r[0]) !== i) ? " Some row names repeat; a change applies to every row with that name." : ""}` }),
        noted ? el("p", { class: "muted", text: `The mechanics notes explain ${noted === rows.length ? "every row" : `${noted} of these rows`}: their line shows under the row's name.${noted < rows.length ? " The others show their name only." : ""}` }) : null);

      // The file's own row removals and additions, kept as they are.
      if (rowOps[n]) {
        card.append(el("div", { class: "row" }, el("span", { class: "chip warn" }, el("i"), D.rowOpsWords(rowOps[n])),
          el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove the rows removed and added by hand in ${title(n)}`,
            onclick: () => { delete rowOps[n]; changed(); } })));
      }
      // Multiplying a whole column: not on Tuning, whose one value column holds hundreds of unrelated numbers.
      const numericCols = header.map((_, i) => i).filter(i => colKinds[i].kind === "number");
      if (numericCols.length && n !== "TuningData.csv") {
        const mulCol = el("select", { id: "data-mul-col", "aria-label": "Column to multiply" }, ...numericCols.map(i => el("option", { value: header[i], text: label(i) })));
        if (view.mulCol && numericCols.some(i => header[i] === view.mulCol)) mulCol.value = view.mulCol;
        const mulBy = el("input", { type: "number", id: "data-mul-by", step: "0.1", min: "0", value: view.mulBy, style: { width: "6rem" }, "aria-label": "Multiply by" });
        const go = el("button", { class: "btn small", type: "button" });
        const say = () => { view.mulCol = mulCol.value; view.mulBy = mulBy.value; go.textContent = `Every ${label(header.indexOf(mulCol.value))} × ${mulBy.value || "?"}`; };
        mulCol.addEventListener("change", say); mulBy.addEventListener("input", say); say();
        go.addEventListener("click", () => {
          const col = header.indexOf(mulCol.value), f = Number(mulBy.value);
          const why = D.multiplyProblem(colKinds[col], header, rows, col, f, texts);
          if (why) return toast(why, "bad");
          D.setCell(edits, n, header, "*", mulCol.value, `x${f}`);
          changed();
          const warn = D.multiplyWarning(colKinds[col], header, rows, col, f, texts);
          if (warn) toast(warn);
        });
        card.append(el("div", { class: "row" }, el("span", { class: "lbl", text: "Multiply" }), mulCol, el("span", { text: "by" }), mulBy, go));
      }
      const star = tEdits()["*"] || {};
      const starKeys = Object.keys(star).filter(k => k !== "__first__");
      if (starKeys.length) {
        card.append(el("div", { class: "row" }, ...starKeys.map(c => {
          const m = D.multiplier(star[c]);
          const said = `${label(header.indexOf(c)) || c} ${m !== null ? "× " + m : "= " + star[c]} on every row`;
          return el("span", { class: "chip warn" }, el("i"), said, el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove ${said}`,
            onclick: () => { D.unsetCell(edits, n, header, "*", c); changed(); } }));
        })));
      }
      const putBack = wc.confirmButton("Put this table back", "Press again: every change to this table goes", () => {
        delete edits[n]; delete rowOps[n]; delete fileNotes.tables[n]; changed();
      }, "btn small ghost");
      tableHook = () => { putBack.disabled = !D.countEdits(edits, rowOps, n); };
      tableHook();
      card.append(el("div", { class: "row" }, putBack), filterBox);
      const cellRow = new Map();   // a cell -> its row (row names can repeat)
      const wrap = el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
        el("thead", {}, el("tr", {}, ...header.map((h, i) => el("th", { scope: "col", text: label(i) })))), body));
      clear(tableBox).append(card, wrap);
      wrap.addEventListener("scroll", () => { view.scroll = wrap.scrollTop; });

      // ---- the cells ----
      let active = null;   // the one cell Tab stops at (a roving tab stop); arrow keys move it
      const setActive = td => { if (active && active !== td) active.tabIndex = -1; active = td; td.tabIndex = 0; };
      function show(td, row, i) {
        const v = row[i] ?? "";
        const ed = D.valueFor(tEdits(), header, row, i);
        td.classList.toggle("edited", !!ed && !ed.bad);
        const english = s => texts[s] ? el("span", { title: s, text: texts[s] }) : el("span", { text: s || "—" });
        if (colKinds[i].kind === "bool") {
          const now = ed ? /^true$/i.test(ed.value) : /^true$/i.test(v);
          const box = el("input", { type: "checkbox", checked: now, tabindex: "-1", "aria-label": `${row[0]} ${label(i)}` });
          box.addEventListener("change", () => commitValue(row, i, box.checked));
          clear(td).append(box, ed ? el("span", { class: "was", text: `was ${v}` }) : null);
          return;
        }
        if (!ed) { clear(td).append(english(v)); return; }
        const mark = ed.bad ? null : said(since(n, row[0], header[i], ed.value));
        clear(td).append(el("span", {}, english(ed.value), el("span", { class: "was", text: ed.bad ? `${ed.how}` : `${v}${ed.how !== "set" ? " · " + ed.how : ""}${mark ? " · " + mark : ""}` })));
      }
      // A value for a cell: the game's own takes the row's edit away, unless "*" covers the column (then it keeps
      // the row out of it); anything else is set. Only that cell (and its namesakes) is drawn again.
      function commitValue(row, i, value) {
        const col = header[i], before = JSON.stringify(edits[n]?.[row[0]] ?? null);
        const starHere = D.valueFor({ "*": tEdits()["*"] }, header, row, i) !== null;
        const same = typeof value === "boolean" ? value === /^true$/i.test(row[i] ?? "") :
          colKinds[i].kind === "number" ? D.readNumber(row[i]) === value : String(row[i] ?? "") === String(value);
        if (same && !starHere) D.unsetCell(edits, n, header, row[0], col);
        else D.setCell(edits, n, header, row[0], col, value);
        if (JSON.stringify(edits[n]?.[row[0]] ?? null) !== before) changed(true, false);
        for (const td of body.querySelectorAll(`[data-focus="${CSS.escape(`cell:${row[0]}:${i}`)}"]`)) show(td, cellRow.get(td) || row, i);
      }
      function edit(td, row, i) {
        const kind = colKinds[i], ed = D.valueFor(tEdits(), header, row, i);
        const start = ed && !ed.bad ? ed.value : row[i] ?? "";
        const box = kind.kind === "choice"
          ? el("select", { "aria-label": `${row[0]} ${label(i)}` }, ...[...new Set([...kind.options, start])].map(o => el("option", { value: o, text: o })))
          : el("input", { type: "text", value: start, "aria-label": `${row[0]} ${label(i)}`, inputmode: kind.kind === "number" ? "decimal" : false });
        box.value = start;
        clear(td).append(box);
        box.focus();
        if (box.select) box.select();
        let done = false;
        const finish = ok => {
          if (done) return true;
          if (ok) {
            const raw = box.value;
            if (raw.trim() === String(start).trim()) { ok = false; }   // nothing typed: nothing changes
            else {
              const r = D.readCell(kind, raw);
              if (r.error) { toast(r.error, "bad"); box.setAttribute("aria-invalid", "true"); return false; }
              done = true;
              box.removeEventListener("blur", onBlur);
              commitValue(row, i, r.value);
              if (r.warn) toast(`${D.rowLabel(header, row, texts)}'s ${label(i)}: ${r.warn}`);
              td.focus();
              return true;
            }
          }
          done = true;
          box.removeEventListener("blur", onBlur);
          show(td, row, i);
          td.focus();
          return true;
        };
        // Leaving the box keeps what's typed; a value that can't go in goes back to what it was.
        const onBlur = () => { if (!finish(true)) { done = true; show(td, row, i); } };
        box.addEventListener("blur", onBlur);
        // A dropdown changes with every arrow key: those only choose, and Enter or leaving the box keeps the
        // choice. A pick with the mouse keeps it straight away.
        let byKey = false;
        box.addEventListener("keydown", e => {
          byKey = e.key !== "Enter" && e.key !== "Escape";
          if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); finish(true); }
          else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish(false); }
        });
        if (kind.kind === "choice") {
          box.addEventListener("pointerdown", () => { byKey = false; });
          box.addEventListener("change", () => { if (!byKey) finish(true); });
        }
      }
      function fill() {
        const q = filterBox.value.trim().toLowerCase();
        view.filter = filterBox.value;
        clear(body);
        cellRow.clear();
        active = null;
        let count = 0;
        for (const row of rows) {
          if (q && !row.join(" ").toLowerCase().includes(q) && !row.some(v => texts[v]?.toLowerCase().includes(q))) continue;
          if (++count > 600) { body.append(el("tr", {}, el("td", { colspan: header.length, class: "muted", text: "Showing the first 600 rows; filter to find others." }))); break; }
          body.append(el("tr", { "data-row": row[0] }, ...row.map((v, i) => {
            const kind = colKinds[i];
            const td = el(i === 0 ? "th" : "td", { class: `${kind.kind === "number" ? "num" : ""} ${kind.kind}`, scope: i === 0 ? "row" : false, tabindex: "-1", "data-focus": `cell:${row[0]}:${i}` });
            cellRow.set(td, row);
            if (i === 0) {
              td.append(texts[v] ? el("span", { title: v, text: texts[v] }) : el("span", { class: "mono", text: v }));
              const note = told.rows[v]?.[0];
              if (note) td.append(el("span", { class: "row-note", text: note.text }));
            }
            else if (kind.kind === "note") td.append(el("span", { class: "muted", text: v }));
            else show(td, row, i);
            if (!active && i > 0 && kind.kind !== "note") setActive(td);
            td.addEventListener("focus", () => setActive(td));
            const editable = i > 0 && kind.kind !== "note";
            if (editable) {
              td.addEventListener("click", e => {
                if (kind.kind === "bool") { if (e.target === td) td.querySelector("input")?.click(); return; }
                if (!td.querySelector("input, select")) edit(td, row, i);
              });
              td.addEventListener("keydown", e => {
                if (e.target !== td) return;
                if (e.key === "Enter" || e.key === "F2") {
                  e.preventDefault();
                  if (kind.kind === "bool") td.querySelector("input")?.click();
                  else edit(td, row, i);
                } else if (e.key === " " && kind.kind === "bool") { e.preventDefault(); td.querySelector("input")?.click(); }
              });
            }
            return td;
          })));
        }
        if (!count) body.append(el("tr", {}, el("td", { colspan: header.length, class: "muted", text: "No row has that in it." })));
      }
      // Arrow keys move between cells: one tab stop for the whole grid.
      body.addEventListener("keydown", e => {
        const td = e.target.closest?.("td, th");
        if (!td || e.target !== td) return;
        const tr = td.parentElement, at = [...tr.children].indexOf(td);
        let next = null;
        if (e.key === "ArrowRight") next = td.nextElementSibling;
        else if (e.key === "ArrowLeft") next = td.previousElementSibling;
        else if (e.key === "ArrowDown") next = tr.nextElementSibling?.children[at];
        else if (e.key === "ArrowUp") next = tr.previousElementSibling?.children[at];
        else if (e.key === "Home") next = tr.children[0];
        else if (e.key === "End") next = tr.children[tr.children.length - 1];
        if (next && next.hasAttribute("data-focus")) { e.preventDefault(); setActive(next); next.focus(); }
      });
      filterBox.addEventListener("input", fill);
      fill();
      wrap.scrollTop = view.scroll;
      if (focusRow !== undefined) {
        const tr = body.querySelector(`tr[data-row="${CSS.escape(focusRow)}"]`);
        if (tr) { tr.scrollIntoView({ block: "center" }); const td = tr.querySelector("td[data-focus]"); if (td) { setActive(td); td.focus(); } }
      }
    }

    // ---------- start ----------
    // After an Apply the file is read again (so the bar's list and the file are what the install saw), unless
    // the page has changes not saved yet.
    const off = wc.installedEvent(target, () => target.refresh().catch(() => { /* the bar says */ }));
    // What that Apply put in the game, for "in the game since": kept whether or not the page has unsaved changes.
    const offApplied = wc.bus.on("installed", d => {
      const now = D.inGameFrom(d, new Date().toTimeString().slice(0, 5));
      if (now) { applied = now; changed(false); }
    });
    const handle = { unmount() { clearTimeout(findTimer); off(); offApplied(); } };
    try {
      [quickData, titles, notes] = await Promise.all([staticJson("data-quick.json"), staticJson("data-titles.json"), staticJson("data-notes.json")]);
    } catch (e) { toast(`Quick changes couldn't load: ${e.message}`, "bad"); }
    try {
      ({ tables: names, kinds, hidden = [] } = await api.get("/game/data"));
    } catch (e) {
      // No game yet, or its files can't be read: the file can still be looked at and saved.
      problem.hidden = false;
      problem.append(el("div", { class: "error-card" }, el("h2", { text: "The game's tables can't be read" }),
        el("p", { text: e.message }),
        el("p", { class: "note", text: "Get set up, on the Mods page, finds the game. Until then this page can show its file, under For mod makers, but not the tables." })));
      quickBox.hidden = true;
      allFold.hidden = true;
      findBox.disabled = true;
      await target.refresh();
      root.dataset.ready = "true";
      return handle;
    }
    renderQuick();
    // All tables opens on XP from fights, the first time it's opened.
    allFold.addEventListener("toggle", () => {
      if (allFold.open && !current) openTable(names.includes("CombatBaseExperience.csv") ? "CombatBaseExperience.csv" : names.find(x => !hidden.includes(x)));
    });
    await target.refresh();
    renderList();
    // The tables Quick changes needs, read once (the grid shares them).
    await Promise.all(QUICK_TABLES().filter(inGame).map(n => getTable(n).catch(() => null)));
    changed(false, false);
    root.dataset.ready = "true";   // for the end-to-end tests: everything the page reads at the start is in
    return handle;
  },
};
