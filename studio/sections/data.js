// Game data: edit the game's runtime tables (XP, costs, rewards, tuning). Writes data.json in a mod.
const GROUPS = [
  { title: "Progress & rewards", match: n => /^(CombatBaseExperience|SkirmishRank|Consumables|BarteringCost|HousingCost|QuestGossipCost|VisitRewards|OnlineGifts)\.csv$/.test(n) },
  { title: "Tuning", match: n => n === "TuningData.csv" },
  { title: "Combat", match: n => /^(AttackMove|CharacterAttacks|CharacterStatsBase|ClanSpecificBase|CombatStance|AICombatChances|CombatDilemmas)\.csv$/.test(n) || n.startsWith("Effects/") },
  { title: "Cats & names", match: n => n.startsWith("NPC/") || /^(PrefixNameFilters|SuffixNameFilters|TraitsFilters)\.csv$/.test(n) },
  { title: "Other", match: n => !/^(HeightMap|UniqueIds)\//.test(n) },
];
// Each table's kind comes from the server (wcmods/sections/files.py classify), so the badges match build warnings.
const KIND_INFO = {
  online: ["bad", "Online feature: the den-visit server may see or reject changes"],
  traits: ["warn", "Changes which traits cats get (traits have gameplay effects)"],
  appearance: ["good", "Appearance only"],
  gameplay: ["", "Changes gameplay"],
};
const NUM = /^-?\d+(\.\d+)?$/;

export default {
  title: "Game data",
  async mount(root, wc) {
    const { el, api, clear, toast } = wc;
    let edits = {};                  // { "Table.csv": { rowKey | "*": { column: value } } }
    let names = [], kinds = {};
    const kindOf = n => { const k = kinds[n] || "gameplay"; return [k, ...KIND_INFO[k]]; };
    let current = null, tableData = null, filter = "";
    const cache = {};

    const target = wc.modTarget({
      file: "data.json",
      onLoad: obj => { edits = clean(obj); renderList(); if (current) renderTable(); out.set(toJson()); },
      getValue: () => toJson(),
    });
    const listBox = el("div", { class: "card", style: { alignContent: "start" } });
    const tableBox = el("div", { style: { display: "grid", gap: "12px", minWidth: "0" } });
    const out = wc.codePanel("data.json");
    const search = el("input", { type: "search", id: "data-search", placeholder: "Find a table", "aria-label": "Find a table" });
    search.addEventListener("input", renderList);

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Gameplay" }),
        el("h1", { text: "Game data" }),
        el("p", { class: "note", text: "Edit the tables the game reads at runtime: combat XP, costs, rewards, speeds and hundreds of tuning values. These change gameplay, not just looks. Edits are saved as data.json in a mod; the game's own files are never modified." })),
      target.element,
      el("div", { class: "data-grid", style: { display: "grid", gridTemplateColumns: "minmax(220px, 280px) minmax(0, 1fr)", gap: "20px", alignItems: "start" } },
        listBox, tableBox),
      out.element);
    const narrow = window.matchMedia("(max-width: 900px)");
    const applyNarrow = () => { root.querySelector(".data-grid").style.gridTemplateColumns = narrow.matches ? "minmax(0,1fr)" : "minmax(220px, 280px) minmax(0, 1fr)"; };
    narrow.addEventListener("change", applyNarrow); applyNarrow();

    function clean(obj) {
      const o = {};
      for (const [t, e] of Object.entries(obj || {})) {
        if (t.startsWith("_") || typeof e !== "object") continue;
        o[t] = {};
        for (const [row, spec] of Object.entries(e)) {
          if (row.startsWith("_")) continue;
          o[t][row] = typeof spec === "object" && spec !== null ? { ...spec } : { __first__: spec };
        }
      }
      return o;
    }
    function toJson() {
      const o = { _help: "Written by Clan Mod Studio. Rows are matched by their first column; \"*\" is every row; \"x2\" multiplies the game's value." };
      for (const [t, rows] of Object.entries(edits)) {
        const r = {};
        for (const [row, cols] of Object.entries(rows)) {
          const c = { ...cols };
          if ("__first__" in c) {
            // A {row: value} shorthand edit: name its column if this table is loaded, otherwise keep it as-is.
            const h = cache[t]?.header?.[1];
            if (!h) { r[row] = c.__first__; continue; }
            if (!(h in c)) c[h] = c.__first__;
            delete c.__first__;
          }
          if (Object.keys(c).length) r[row] = c;
        }
        if (Object.keys(r).length) o[t] = r;
      }
      return o;
    }
    const countEdits = t => Object.values(edits[t] || {}).reduce((n, c) => n + Object.keys(c).length, 0);

    function renderList() {
      filter = search.value.trim().toLowerCase();
      clear(listBox).append(el("h2", { text: "Tables" }), search);
      const shown = new Set();
      for (const g of GROUPS) {
        const items = names.filter(n => !shown.has(n) && g.match(n) && (!filter || n.toLowerCase().includes(filter)));
        if (!items.length) continue;
        items.forEach(n => shown.add(n));
        listBox.append(el("span", { class: "eyebrow", style: { marginTop: "6px" }, text: g.title }));
        for (const n of items) {
          const [kind, cls] = kindOf(n);
          const c = countEdits(n);
          listBox.append(el("button", {
            class: "btn ghost", "aria-current": current === n ? "true" : false, "data-focus": `table:${n}`,
            style: { textAlign: "left", display: "flex", justifyContent: "space-between", gap: "6px", color: current === n ? "var(--ink)" : "", background: current === n ? "var(--accent-soft)" : "" },
            onclick: () => openTable(n),
          }, el("span", { text: n.replace(/\.csv$/, "") }),
            el("span", { class: "row" }, c ? el("span", { class: "mono", style: { color: "var(--changed)" }, text: String(c) }) : null,
              kind !== "gameplay" ? el("span", { class: `chip ${cls}`, style: { padding: "0 6px", fontSize: "0.75rem" }, text: kind }) : null)));
        }
      }
    }

    async function openTable(n) {
      current = n;
      renderList();
      clear(tableBox).append(el("p", { class: "muted", text: `Loading ${n}…` }));
      try {
        cache[n] ||= await api.get(`/game/data/${n.split("/").map(encodeURIComponent).join("/")}`);
        tableData = cache[n];
        renderTable();
      } catch (e) { clear(tableBox).append(el("div", { class: "error-card" }, el("p", { text: e.message }))); }
    }

    function valueFor(row, col) {
      const t = edits[current] || {};
      const colName = tableData.header[col];
      const direct = t[row[0]] && (t[row[0]][colName] ?? (col === 1 ? t[row[0]].__first__ : undefined));
      if (direct !== undefined) return { value: String(direct), how: "set" };
      const all = t["*"] && t["*"][colName];
      if (all !== undefined) {
        const m = /^\s*[x*]\s*(-?\d+(\.\d+)?)\s*$/i.exec(String(all));
        if (m && NUM.test(row[col])) { const v = +row[col] * +m[1]; return { value: String(Number.isInteger(v) ? v : +v.toFixed(6)), how: `×${m[1]}` }; }
        return { value: String(all), how: "all rows" };
      }
      return null;
    }
    function setCell(rowKey, colName, raw) {
      const t = (edits[current] ||= {});
      const r = (t[rowKey] ||= {});
      if ("__first__" in r) { if (!(tableData.header[1] in r)) r[tableData.header[1]] = r.__first__; delete r.__first__; }
      const v = NUM.test(raw.trim()) ? Number(raw.trim()) : raw;
      r[colName] = v;
      target.markDirty(); out.set(toJson()); renderList();
    }
    function unsetCell(rowKey, colName) {
      const t = edits[current] || {};
      if (t[rowKey]) {
        delete t[rowKey][colName];
        if (tableData && colName === tableData.header[1]) delete t[rowKey].__first__;
        if (!Object.keys(t[rowKey]).length) delete t[rowKey];
      }
      target.markDirty(); out.set(toJson()); renderList();
    }

    function renderTable() {
      if (!tableData || tableData.name !== current) return;
      const { header, rows } = tableData;
      const [kind, cls, why] = kindOf(current);
      const numericCols = header.map((h, i) => i > 0 && rows.length && rows.every(r => r[i] === undefined || r[i] === "" || NUM.test(r[i]))).map((v, i) => v ? i : -1).filter(i => i > 0);
      const filterBox = el("input", { type: "search", id: "data-row-filter", placeholder: "Filter rows", "aria-label": "Filter rows" });
      const mulCol = el("select", { id: "data-mul-col", "aria-label": "Column to multiply" }, ...numericCols.map(i => el("option", { value: header[i], text: header[i] })));
      const mulBy = el("input", { type: "number", id: "data-mul-by", step: "0.1", value: "2", style: { width: "6rem" }, "aria-label": "Multiply by" });
      const body = el("tbody");
      const allRow = edits[current]?.["*"] || {};

      clear(tableBox).append(
        el("div", { class: "card" },
          el("div", { class: "row spread" }, el("h2", { text: current }), el("span", { class: `chip ${cls}`, title: why }, el("i"), kind)),
          el("p", { class: "note", text: `${rows.length} rows. Click a value to change it. ${rows.some((r, i) => rows.findIndex(x => x[0] === r[0]) !== i) ? "Some row names repeat; an edit applies to every row with that name." : ""}` }),
          numericCols.length ? el("div", { class: "row" }, el("span", { class: "lbl", text: "Multiply every" }), mulCol, el("span", { text: "by" }), mulBy,
            el("button", { class: "btn small", text: "Apply to all rows", onclick: () => {
              const f = Number(mulBy.value);
              if (!f || f <= 0) return toast("Use a number above 0", "bad");
              ((edits[current] ||= {})["*"] ||= {})[mulCol.value] = `x${f}`;
              target.markDirty(); out.set(toJson()); renderList(); renderTable();
            } })) : null,
          Object.keys(allRow).length ? el("div", { class: "row" }, ...Object.entries(allRow).map(([c, v]) =>
            el("span", { class: "chip warn" }, el("i"), `${c}: ${v} on every row`, el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${c}: ${v} on every row`, onclick: () => { unsetCell("*", c); renderTable(); } })))) : null,
          filterBox),
        el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, ...header.map((h, i) => el("th", { text: i === 0 ? (h.replace(/^-+$/, "") || "Row") : h })))), body)));

      function fill() {
        const q = filterBox.value.trim().toLowerCase();
        clear(body);
        let shown = 0;
        for (const row of rows) {
          if (q && !row.join(" ").toLowerCase().includes(q)) continue;
          if (++shown > 600) { body.append(el("tr", {}, el("td", { colspan: header.length, class: "muted", text: "Showing the first 600 rows; filter to find others." }))); break; }
          body.append(el("tr", {}, ...row.map((v, i) => {
            if (i === 0) return el("td", { class: "mono", style: { fontSize: "0.8rem" }, text: v });
            if (header[i] === "Description") return el("td", { class: "muted", style: { fontSize: "0.85rem", minWidth: "16rem" }, text: v });
            const ed = valueFor(row, i);
            const td = el("td", { class: `${NUM.test(v) ? "num" : ""} ${ed ? "edited" : ""}` });
            const show = () => {
              clear(td).append(ed ? el("span", {}, el("span", { text: ed.value }), el("span", { class: "was", text: `${v}${ed.how !== "set" ? " · " + ed.how : ""}` })) : el("span", { text: v || "—" }));
            };
            show();
            td.tabIndex = 0;
            td.dataset.focus = `cell:${row[0]}:${i}`;
            const edit = () => {
              const inp = el("input", { type: "text", value: ed && ed.how === "set" ? ed.value : v, "aria-label": `${row[0]} ${header[i]}` });
              clear(td).append(inp); inp.focus(); inp.select();
              const commit = () => {
                const nv = inp.value;
                if (nv === v) unsetCell(row[0], header[i]); else if (!ed || nv !== ed.value) setCell(row[0], header[i], nv);
                renderTable();
              };
              inp.addEventListener("keydown", e => { if (e.key === "Enter") commit(); if (e.key === "Escape") renderTable(); });
              inp.addEventListener("blur", commit);
            };
            td.addEventListener("click", () => { if (!td.querySelector("input")) edit(); });
            td.addEventListener("keydown", e => { if (e.key === "Enter" && !td.querySelector("input")) edit(); });
            return td;
          })));
        }
      }
      filterBox.addEventListener("input", fill);
      fill();
    }

    ({ tables: names, kinds } = await api.get("/game/data"));
    await target.refresh();
    renderList();
    openTable(names.includes("CombatBaseExperience.csv") ? "CombatBaseExperience.csv" : names[0]);
  },
};
