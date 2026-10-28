// The Game data page's logic, without the page (studio/sections/data.js draws it): data.json read and written
// back with the file's own row removals and additions kept as they are, what a cell shows (the rule the build
// follows, wcmods/formats/csvdata.py: "*" first, a named row wins over it, a row's own "xN" multiplies the
// value from before "*"), the number check, what kind of column a column is, the Quick changes rows
// (data-quick.json) and the search across every table. Plain data in, plain data out: tested under node.

export const NUM = /^-?\d+(\.\d+)?$/;
const MULT = /^\s*[x*]\s*(-?\d+(\.\d+)?)\s*$/i;
export const HELP = "Written by Clan Mod Studio. Rows are matched by their first column; \"*\" is every row; \"x2\" multiplies the game's value. Inside one file \"*\" goes first and a named row wins over it.";

export const isNumber = s => typeof s === "string" && NUM.test(s.trim());
// N for an "xN" value, else null.
export function multiplier(v) {
  const m = typeof v === "string" ? MULT.exec(v) : null;
  return m ? Number(m[1]) : null;
}
// A number as the file writes it: whole when it's whole and the cell had no decimals, else at most six decimals.
export function numberText(v, original = "") {
  if (Number.isInteger(v) && !String(original).includes(".")) return String(v);
  const s = v.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  return s === "" || s === "-0" ? "0" : s;
}
// A typed number, trimmed and rounded to six decimals; null when it isn't one ("1,5", "abc", "").
export function readNumber(raw) {
  const s = String(raw ?? "").trim();
  return NUM.test(s) ? Number(Number(s).toFixed(6)) : null;
}
const shown = (v, original = "") => typeof v === "boolean" ? (v ? "TRUE" : "FALSE") : typeof v === "number" ? numberText(v, original) : String(v);

// ---------- data.json in and out ----------
// The page's model of a data.json: edits[table][row][column] = value ("__first__" for a {row: value} edit whose
// column isn't known until the table is read), rowOps[table] = the file's own "-" and "+" (kept as they are),
// notes = the file's own "_" keys (a "_help", a "_note"), at the top and in each table, kept as they are, and
// the entries skipped because they aren't a table's edits (named, so the page can say so).
export function clean(obj) {
  const edits = {}, rowOps = {}, skipped = [], notes = { top: {}, tables: {} };
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return { edits, rowOps, skipped, notes };
  for (const [t, e] of Object.entries(obj)) {
    if (t.startsWith("_")) { notes.top[t] = e; continue; }
    if (!e || typeof e !== "object" || Array.isArray(e)) { skipped.push(t); continue; }
    edits[t] = {};
    for (const [row, spec] of Object.entries(e)) {
      if (row.startsWith("_")) { (notes.tables[t] ||= {})[row] = spec; continue; }
      if (row === "-" || row === "+") { (rowOps[t] ||= {})[row] = spec; continue; }
      edits[t][row] = spec && typeof spec === "object" && !Array.isArray(spec) ? { ...spec } : { __first__: spec };
    }
  }
  return { edits, rowOps, skipped, notes };
}
// Back to data.json: the file's own "_" keys (its own _help, else the page's), then each table: its "_" keys,
// "-", "*", the rows and "+" (the build's order; a reader sees it too). headers: {table: its header}, for the
// tables read, so a {row: value} edit gets its column's name.
export function toJson(edits, rowOps = {}, headers = {}, notes = { top: {}, tables: {} }) {
  const o = { _help: HELP, ...(notes.top || {}) };
  for (const t of new Set([...Object.keys(edits), ...Object.keys(rowOps)])) {
    const r = { ...(notes.tables?.[t] || {}) }, ops = rowOps[t] || {}, own = Object.keys(r).length;
    if ("-" in ops) r["-"] = ops["-"];
    const rows = edits[t] || {};
    for (const row of ["*", ...Object.keys(rows).filter(k => k !== "*")]) {
      if (!(row in rows)) continue;
      const c = { ...rows[row] };
      if ("__first__" in c) {
        const h = headers[t]?.[1];
        if (!h) { r[row] = c.__first__; continue; }
        if (!(h in c)) c[h] = c.__first__;
        delete c.__first__;
      }
      if (Object.keys(c).length) r[row] = c;
    }
    if ("+" in ops) r["+"] = ops["+"];
    // Notes alone stay only for a table the file had with nothing else (Put this table back takes it out).
    if (Object.keys(r).length > own || (own && edits[t] && !Object.keys(edits[t]).length)) o[t] = r;
  }
  return o;
}
// How many changes a table has: a cell each, "*" once per column, and a row removed or added each.
export function countEdits(edits, rowOps, t) {
  let n = Object.values(edits[t] || {}).reduce((sum, c) => sum + Object.keys(c).length, 0);
  for (const op of Object.values(rowOps?.[t] || {})) n += Array.isArray(op) ? op.length : 1;
  return n;
}
// The file's own row removals and additions, in words: "1 row removed, 1 row added by hand".
export function rowOpsWords(ops) {
  if (!ops) return "";
  const n = v => Array.isArray(v) ? v.length : typeof v === "string" ? 1 : 0;
  const parts = [];
  if ("-" in ops) parts.push(`${n(ops["-"])} row${n(ops["-"]) === 1 ? "" : "s"} removed`);
  if ("+" in ops) parts.push(`${n(ops["+"])} row${n(ops["+"]) === 1 ? "" : "s"} added`);
  return parts.length ? `${parts.join(", ")} by hand` : "";
}

// An edit's value for a column, the column's name matched without regard to case as the build matches it; the
// second column also takes a {row: value} edit.
function pick(spec, name, col) {
  if (!spec) return undefined;
  if (name in spec) return spec[name];
  const low = String(name).toLowerCase();
  const k = Object.keys(spec).find(x => x.toLowerCase() === low);
  if (k !== undefined) return spec[k];
  return col === 1 && "__first__" in spec ? spec.__first__ : undefined;
}
// What a cell shows: { value, how: "set" | "×N" | "all rows" | "unchanged (not a number)", bad } or null for
// the game's own. The build's rule (csvdata.apply_edits), so the page shows what the game gets.
export function valueFor(tableEdits, header, row, col) {
  const t = tableEdits || {};
  const name = header[col], original = row[col] ?? "";
  const times = (n, own) => isNumber(original)
    ? { value: numberText(Number(original) * n, original), how: `×${n}`, own }
    : { value: original, how: "unchanged (not a number)", own, bad: true };
  const own = pick(t[row[0]], name, col);
  if (own !== undefined) {
    const n = multiplier(own);
    return n !== null ? times(n, true) : { value: shown(own, original), how: "set", own: true };
  }
  const all = pick(t["*"], name, col);
  if (all !== undefined) {
    const n = multiplier(all);
    return n !== null ? times(n, false) : { value: shown(all, original), how: "all rows" };
  }
  return null;
}
// Set one cell's edit. Returns true.
export function setCell(edits, table, header, rowKey, colName, value) {
  const r = ((edits[table] ||= {})[rowKey] ||= {});
  if ("__first__" in r) { if (!(header[1] in r)) r[header[1]] = r.__first__; delete r.__first__; }
  for (const k of Object.keys(r)) if (k !== colName && k.toLowerCase() === colName.toLowerCase()) delete r[k];
  r[colName] = value;
  return true;
}
// Take one cell's edit away. Returns whether there was one.
export function unsetCell(edits, table, header, rowKey, colName) {
  const r = edits[table]?.[rowKey];
  if (!r) return false;
  let gone = false;
  for (const k of Object.keys(r)) if (k.toLowerCase() === colName.toLowerCase()) { delete r[k]; gone = true; }
  if (header && colName === header[1] && "__first__" in r) { delete r.__first__; gone = true; }
  if (!Object.keys(r).length) delete edits[table][rowKey];
  if (!Object.keys(edits[table]).length) delete edits[table];
  return gone;
}

// ---------- columns ----------
// A first header that's empty or punctuation ("", "---", "#") is the row's name: "Row".
export function headerLabel(h, i) {
  return i === 0 && /^[\s\p{P}\p{S}]*$/u.test(h || "") ? "Row" : h;
}
// Columns that are chances though their names don't end in "Chance": every number column of AICombatChances,
// and AttackMove's Accuracy (how likely a move is to hit).
export const CHANCE_COLUMNS = { "AICombatChances.csv": "*", "AttackMove.csv": ["Accuracy"] };
export function chanceColumn(table, name) {
  const listed = CHANCE_COLUMNS[table];
  return /chance$/i.test(name || "") || listed === "*" || (Array.isArray(listed) && listed.includes(name));
}
// What a column holds, so the page offers the right box: "key" (the first), "note" (a Description), "bool"
// (TRUE/FALSE: a checkbox), "number", "choice" (at most eight words, which repeat: a dropdown of them) or "text".
// A number column is a chance by its name (chanceColumn), with every value from 0 to 1: nothing over 1 goes in.
// Another whose values are all from 0 to 1, with decimals (CatSize's scales, a rumble's length), is `unit`:
// a value past 1 is only asked about.
export function columnKind(header, rows, i, table = "") {
  if (i === 0) return { kind: "key" };
  if (/^description$/i.test(header[i] || "")) return { kind: "note" };
  const values = rows.map(r => (r[i] ?? "").trim()).filter(Boolean);
  if (!values.length) return { kind: "text" };
  if (values.every(v => /^(true|false)$/i.test(v))) return { kind: "bool" };
  if (values.every(v => NUM.test(v))) {
    const nums = values.map(Number);
    const unit = nums.every(n => n >= 0 && n <= 1);
    const chance = unit && chanceColumn(table, header[i]);
    return unit && !chance && values.some(v => v.includes(".")) ? { kind: "number", chance, unit: true } : { kind: "number", chance };
  }
  const words = [...new Set(values)];
  if (words.length >= 2 && words.length <= 8 && words.length < values.length && values.every(v => /^[A-Za-z][A-Za-z ]*$/.test(v))) {
    return { kind: "choice", options: words.sort() };
  }
  return { kind: "text" };
}
// What a typed value becomes in a column of that kind: { value } or { error } in words; { value, warn } for a
// value past what a `unit` column has (it goes in, and the page says so).
export function readCell(kind, raw) {
  if (kind.kind === "number") {
    const n = readNumber(raw);
    if (n === null) return { error: "Use a number like 1.5" };
    if (kind.chance && (n < 0 || n > 1)) return { error: "This is a chance: use a number from 0 to 1" };
    if (kind.unit && (n < 0 || n > 1)) return { value: n, warn: `Every other value in this column is from 0 to 1; ${numberText(n)} goes in, if that's what you meant` };
    return { value: n };
  }
  if (kind.kind === "bool") return { value: raw === true || /^true$/i.test(String(raw)) };
  return { value: String(raw) };
}
// A row in words, for a message: its Role or Name (CatSize's row "3" is Elder), the English for a STR_ key
// (texts: {key: English}), else its first column.
export function rowLabel(header, row, texts = {}) {
  const i = header.findIndex((h, k) => k > 0 && /^(role|name)$/i.test(h || ""));
  const said = i > 0 ? String(row[i] ?? "").trim() : "";
  if (said) return texts[said] || said;
  return texts[row[0]] || row[0];
}
// Multiplying a column by f: refused with the first row it would break, for a chance column (over 1).
export function multiplyProblem(kind, header, rows, col, f, texts = {}) {
  if (!(f > 0)) return "Use a number above 0";
  if (!kind.chance) return null;
  const over = rows.find(r => isNumber(r[col] ?? "") && Number(r[col]) * f > 1);
  return over ? `${rowLabel(header, over, texts)} would be ${numberText(Number(over[col]) * f, over[col])}, and a chance can't go over 1` : null;
}
// Multiplying a `unit` column (every value from 0 to 1) past 1: it goes in, with this said; else null.
export function multiplyWarning(kind, header, rows, col, f, texts = {}) {
  if (!kind.unit || !(f > 0)) return null;
  const over = rows.filter(r => isNumber(r[col] ?? "") && Number(r[col]) * f > 1);
  if (!over.length) return null;
  const first = over[0];
  return `${rowLabel(header, first, texts)}'s ${header[col]} is ${numberText(Number(first[col]) * f, first[col])} now${over.length > 1 ? ` (and ${over.length - 1} more over 1)` : ""}; every value here was from 0 to 1, so check that's what you meant`;
}

// ---------- Quick changes ----------
// An entry of data-quick.json names a table, a row ("*" for every row) or rows, and a column or columns: its
// cells. kind "value" writes a number into each (negate: the table keeps it negative, the page shows it
// positive); "factor" writes "xN" (chance: no cell may go over 1).
export function quickCells(entry, table) {
  if (!table) return [];
  const cols = entry.columns || [entry.column];
  const keys = entry.row === "*" ? table.rows.map(r => r[0]) : entry.rows || [entry.row];
  const out = [];
  for (const key of keys) {
    const row = table.rows.find(r => r[0] === key);
    if (!row) continue;
    for (const col of cols) {
      const i = table.header.findIndex(h => h.toLowerCase() === String(col).toLowerCase());
      if (i > 0) out.push({ row: key, column: table.header[i], index: i, original: row[i] ?? "" });
    }
  }
  return out;
}
// The game's own value for the row: a number for a value entry (null when the table hasn't it), 1 for a factor.
export function quickNormal(entry, table) {
  if (entry.kind === "factor") return 1;
  const first = quickCells(entry, table)[0];
  if (!first || !isNumber(first.original)) return null;
  const n = Number(first.original);
  return entry.negate ? -n : n;
}
// The value the row has now, with this mod's edits. A value row under an "xN" written by hand shows what the
// game gets (390 × 1.5 is 585).
export function quickCurrent(entry, table, tableEdits) {
  const first = quickCells(entry, table)[0];
  if (!first) return null;
  const spec = pick(tableEdits?.[entry.row === "*" ? "*" : first.row], first.column, first.index);
  if (entry.kind === "factor") return spec !== undefined && multiplier(spec) !== null ? multiplier(spec) : 1;
  if (spec === undefined) return quickNormal(entry, table);
  if (multiplier(spec) !== null) {
    const row = table.rows.find(r => r[0] === first.row);
    const shown = row && valueFor(tableEdits, table.header, row, first.index);
    const n = shown && !shown.bad ? readNumber(shown.value) : null;
    return n === null ? quickNormal(entry, table) : entry.negate ? -n : n;
  }
  const n = typeof spec === "number" ? spec : readNumber(spec);
  return n === null ? quickNormal(entry, table) : entry.negate ? -n : n;
}
// The file's own edit of the row's cells, when it isn't one this row writes, in words ("set by hand to 0.08",
// "set by hand to ×1.5"): a factor row over a plain value, a value row over an "xN" or a word, or cells set to
// different values, or only some of them. null when the row's cells are as the row itself would write them.
export function quickHand(entry, table, tableEdits) {
  const cells = quickCells(entry, table);
  const specs = cells.map(c => pick(tableEdits?.[entry.row === "*" ? "*" : c.row], c.column, c.index));
  const set = specs.filter(s => s !== undefined);
  if (!set.length) return null;
  const said = s => multiplier(s) !== null ? `×${multiplier(s)}` : String(s);
  const words = [...new Set(set.map(said))];
  const fits = entry.kind === "factor" ? set.every(s => multiplier(s) !== null)
    : set.every(s => multiplier(s) === null && (typeof s === "number" || readNumber(s) !== null));
  if (fits && words.length === 1 && set.length === specs.length) return null;
  return `set by hand to ${words.join(" and ")}`;
}
// Whether this mod has an edit on any of the row's cells.
export function quickEdited(entry, table, tableEdits) {
  return quickCells(entry, table).some(c => pick(tableEdits?.[entry.row === "*" ? "*" : c.row], c.column, c.index) !== undefined);
}
// Write the row's value into edits (the game's own value takes its edits away). { ok } or { error } in words;
// { hand } (quickHand's words) when the file's own edit is there, which only replace: true writes over.
export function quickWrite(entry, table, edits, value, { replace = false } = {}) {
  const n = typeof value === "number" ? value : readNumber(value);
  if (n === null || !Number.isFinite(n)) return { error: "Use a number like 1.5" };
  if (entry.min !== undefined && n < entry.min || entry.max !== undefined && n > entry.max) {
    return { error: `${entry.label} goes from ${entry.min} to ${entry.max}` };
  }
  const cells = quickCells(entry, table);
  if (!cells.length) return { error: `The game's ${entry.table} hasn't got this row` };
  const hand = replace ? null : quickHand(entry, table, edits[entry.table]);
  if (hand) return { hand };
  const t = entry.table, header = table.header;
  if (entry.kind === "factor") {
    if (entry.chance) {
      const over = cells.find(c => isNumber(c.original) && Number(c.original) * n > 1);
      if (over) return { error: `That makes ${over.column} ${numberText(Number(over.original) * n, over.original)}, and a chance can't go over 1` };
    }
    // "*" once per column; else each row's own cells.
    const targets = entry.row === "*" ? [...new Set(cells.map(c => c.column))].map(col => ["*", col]) : cells.map(c => [c.row, c.column]);
    for (const [row, col] of targets) {
      if (n === 1) unsetCell(edits, t, header, row, col);
      else setCell(edits, t, header, row, col, `x${Number(n.toFixed(6))}`);
    }
    return { ok: true };
  }
  const normal = quickNormal(entry, table);
  for (const c of cells) {
    if (n === normal) unsetCell(edits, t, header, c.row, c.column);
    else setCell(edits, t, header, c.row, c.column, entry.negate ? -n : n);
  }
  return { ok: true };
}
// A factor row's first cells, before and after: "Fish 10 -> 20, Mice 25 -> 25 (its own value), ...". The after is
// what the game would get with the mod's other edits (tableEdits), as the build merges them: a row with a value
// of its own keeps it under "*".
export function quickPreview(entry, table, value, rowNames = {}, tableEdits = {}) {
  const cells = quickCells(entry, table).filter(c => isNumber(c.original));
  const trial = { [entry.table]: JSON.parse(JSON.stringify(tableEdits || {})) };
  const wrote = quickWrite(entry, table, trial, value, { replace: true });
  const after = trial[entry.table] || {};
  const many = new Set(cells.map(c => c.row)).size > 1;
  const said = cells.slice(0, 3).map(c => {
    const name = many ? rowNames[c.row] || c.row : c.column;
    if (!wrote.ok) return `${name} ${c.original.trim()} -> ${numberText(Number(c.original) * value, c.original)}`;
    const row = table.rows.find(r => r[0] === c.row);
    const v = valueFor(after, table.header, row, c.index);
    const own = v && v.own && entry.row === "*" ? " (its own value)" : "";
    return `${name} ${c.original.trim()} -> ${v && !v.bad ? v.value : c.original.trim()}${own}`;
  });
  return said.join(", ") + (cells.length > 3 ? ", ..." : "");
}

// ---------- Your changes, and what's in the game ----------
// A row's name in words: its key, with the next column's word beside a number ("8 (Leader)" in NPC/CatSize).
export function rowName(table, key) {
  const row = table?.rows.find(r => r[0] === key);
  return row && /^\d+$/.test(key) && row[1] && !NUM.test(row[1]) ? `${key} (${row[1]})` : key;
}
// Every change in the file, for the Your changes card: { table, kind: "cell" | "all" | "rows", row, column,
// was, now, said }. A cell's "now" is what the game gets (valueFor), its "was" the game's own; both null
// while the table isn't read.
export function changeList(edits, rowOps = {}, cache = {}) {
  const out = [];
  for (const [t, rows] of Object.entries(edits)) {
    const table = cache[t];
    for (const [row, cols] of Object.entries(rows)) {
      for (const [col, value] of Object.entries(cols)) {
        const column = col === "__first__" ? table?.header?.[1] ?? "value" : col;
        if (row === "*") {
          const n = multiplier(value);
          out.push({ table: t, kind: "all", row, column, said: `every ${column} ${n !== null ? "× " + n : "= " + shown(value)}` });
          continue;
        }
        const i = table ? table.header.findIndex(h => h.toLowerCase() === column.toLowerCase()) : -1;
        const r = table?.rows.find(x => x[0] === row);
        const seen = r && i > 0 ? valueFor({ [row]: { [column]: value } }, table.header, r, i) : null;
        out.push({ table: t, kind: "cell", row, column: i > 0 ? table.header[i] : column, was: r && i > 0 ? r[i] : null,
          now: seen ? seen.value : typeof value === "string" ? value : shown(value) });
      }
    }
  }
  for (const [t, ops] of Object.entries(rowOps)) out.push({ table: t, kind: "rows", said: rowOpsWords(ops) });
  return out;
}
// What the last Apply put in the game, from its manifest's csv_changes: { when, cells: Map("table|row|column" ->
// value) }, the data tables only; null when the manifest has none.
export function inGameFrom(manifest, when, nonasset = "Wrc/Content/Gameplay/DataTables/NonAsset/") {
  const m = manifest && (manifest.sections ? manifest : manifest.manifest);
  if (!m || !m.csv_changes) return null;
  const cells = new Map();
  for (const [path, changes] of Object.entries(m.csv_changes)) {
    if (!path.startsWith(nonasset)) continue;
    for (const c of changes) if (c.column !== "(row)") cells.set(`${path.slice(nonasset.length)}|${c.row}|${c.column}`, c.to);
  }
  return { when, cells, mods: m.mods || [] };
}

// ---------- the mechanics notes (data-notes.json, from docs/mechanics by tools/re/mechanics_notes.py) ----------
const escapeRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const parts = (token, part) => token.split(/<[^>]+>/).map(escapeRe).join(part);
// The tables a table token names ("CatSize.csv" is NPC/CatSize.csv), by their file's name.
export function tokenTables(token, tables) {
  if (!/\.csv$/i.test(token)) return [];
  const re = new RegExp(`(^|/)${parts(token, "[^/.]+")}$`, "i");
  return tables.filter(t => re.test(t));
}
// The rows a key token names: a key that is the token, or ends with "." and the token; <x> stands for one part
// of a key. A plain token that fits more than one row names none (it's ambiguous); a pattern names all it fits.
export function tokenRows(token, keys) {
  if (/\.csv$/i.test(token)) return [];
  const re = new RegExp(`(^|\\.)${parts(token, "[^.]+")}$`);
  const hits = keys.filter(k => re.test(k));
  return /<[^>]+>/.test(token) || hits.length === 1 ? hits : [];
}
// A table's notes: { table: [notes about the table], rows: {key: [notes]} }.
export function notesFor(table, keys, notes = {}) {
  const out = { table: [], rows: {} };
  for (const [token, list] of Object.entries(notes)) {
    if (token.startsWith("_") || !Array.isArray(list)) continue;
    if (tokenTables(token, [table]).length) { out.table.push(...list); continue; }
    for (const key of tokenRows(token, keys)) (out.rows[key] ||= []).push(...list);
  }
  return out;
}

// A table's name in words: its title (data-titles.json), else its file's name split into words
// ("QuestObjectives.csv" -> "Quest objectives", "NPC/EarType.csv" -> "NPC ear type").
export function tableTitle(name, titles = {}) {
  if (titles[name]?.title) return titles[name].title;
  const words = name.replace(/\.csv$/i, "").replace(/[/_]+/g, " ").replace(/(?<=[a-z])(?=[A-Z0-9])|(?<=[0-9])(?=[A-Za-z])/g, " ").trim().split(/\s+/);
  const said = words.map((w, i) => /^[A-Z0-9]{2,}$/.test(w) ? w : i === 0 ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : w.toLowerCase());
  return said.join(" ");
}

// ---------- the search across tables ----------
// Every word of the query, in any order, somewhere in the text.
const has = (text, words) => { const low = text.toLowerCase(); return words.every(w => low.includes(w)); };
// Hits for a query: the quick rows (by their labels, words people use and what they do), the tables (by their
// titles), then any row of any table (by its name and its description). Each { kind: "quick" | "table" | "row",
// text, table, row, id }; at most `limit`.
export function search(query, { quick = [], titles = {}, index = {}, notes = {}, limit = 30 } = {}) {
  const words = String(query || "").toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const out = [];
  const title = t => tableTitle(t, titles);
  for (const q of quick) {
    if (has([q.label, q.group, q.what, ...(q.synonyms || [])].join(" "), words)) {
      out.push({ kind: "quick", id: q.id, text: q.label, where: `${q.group}, in Quick changes`, table: q.table });
    }
  }
  for (const [t, info] of Object.entries(titles)) {
    if (has([t, info.title, info.what].join(" "), words)) out.push({ kind: "table", text: info.title, where: info.what, table: t });
  }
  // The mechanics notes' lines, on the tables and rows they name (the rows once the index is in).
  const tables = Object.keys(index);
  for (const [token, list] of Object.entries(notes)) {
    if (token.startsWith("_") || !Array.isArray(list)) continue;
    const note = list.find(n => has(`${n.text} ${n.heading}`, words));
    if (!note) continue;
    for (const t of tokenTables(token, tables)) out.push({ kind: "table", text: title(t), where: note.text, table: t });
    for (const t of tables) {
      for (const row of tokenRows(token, index[t].rows || [])) out.push({ kind: "row", text: row, where: `${note.text} (${title(t)})`, table: t, row });
    }
  }
  for (const [t, info] of Object.entries(index)) {
    for (const row of info.rows || []) {
      const desc = info.descriptions?.[row] || "";
      if (has(`${row} ${desc}`, words)) {
        out.push({ kind: "row", text: row, where: `${desc ? desc + " " : ""}(${title(t)})`, table: t, row });
        if (out.length >= limit * 2) break;
      }
    }
  }
  const seen = new Set();
  return out.filter(h => { const k = `${h.kind}:${h.table}:${h.row || h.id || ""}`; if (seen.has(k)) return false; seen.add(k); return true; })
    .slice(0, limit);
}
