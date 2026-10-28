// Cats' looks: colours only that cat wears (coat, paws, ears, nose, whiskers), which colour slots it uses (new
// pattern and marking slots from palettes included), its scars and its shape (body, ears, tail, pattern...), for
// your cat and for any cat in your save (cats.json's "cats", by name or place). Writes cats.json (see
// wcmods/catcolours.py).
const PARTS = [
  { id: "fur", name: "Coat", note: "Replaces the coat colour, whichever coat slot it has." },
  { id: "paws", name: "Paw pads" }, { id: "ears", name: "Inner ears" }, { id: "nose", name: "Nose" },
  { id: "whiskers", name: "Whiskers" },
];
// Scar places, in the order the card shows them (the build's names: catcolours.SCARS).
const SCAR_PARTS = [
  { id: "ear", name: "Ears" }, { id: "eye", name: "Eye" }, { id: "back", name: "Back" }, { id: "chest", name: "Chest" },
];
const SLOT_PARTS = [
  { id: "fur", name: "Coat colour", table: "FurColors" },
  { id: "pattern", name: "Pattern colour", table: "PatternMaskColors" },
  { id: "marking", name: "Marking colour", table: "MarkingMaskColors" },
  { id: "eye_left", name: "Left eye colour", table: "IrisColors" },
  { id: "eye_right", name: "Right eye colour", table: "IrisColors" },
];
// The shape (catcolours.LOOK): the game's options for each part, counted from 0.
const LOOK_PARTS = [
  { id: "body", name: "Body", note: "the fur's shape follows it, as in the cat maker" }, { id: "fur", name: "Fur" },
  { id: "tail", name: "Tail" }, { id: "ears", name: "Ears" }, { id: "eyes", name: "Eyes" },
  { id: "whiskers", name: "Whiskers" }, { id: "face", name: "Face" }, { id: "pattern", name: "Pattern" },
  { id: "marking", name: "Markings" },
];
const KEYS = ["colours", "slots", "scars", "look"];
const blank = () => ({ colours: {}, slots: {}, scars: {}, look: {}, scarsRaw: {}, extra: {} });

export default {
  title: "Your cat",
  async mount(root, wc) {
    const { el, api, clear, toast, color } = wc;
    // looks: each cat's choices, "player" for yours and the others by their cats.json key. A cat's scarsRaw holds
    // scar entries the card can't show (a mistake for the build to report) and extra its other keys; fileExtra
    // the file's other keys; all kept as they are.
    let looks = { player: blank() }, fileExtra = {}, who = "player";
    const [info, tablesRes] = await Promise.all([api.get("/cat"), api.get("/game/tables")]);
    const TABLES = tablesRes.tables || {};
    const OTHERS = info.cats || [];

    const target = wc.modTarget({
      file: "cats.json",
      onLoad: obj => { load(obj); render(); },
      getValue: () => toJson(),
    });
    const whoCard = el("div", { class: "card" }), lookCard = el("div", { class: "card" }),
      coloursCard = el("div", { class: "card" }), slotsCard = el("div", { class: "card" }), scarsCard = el("div", { class: "card" });
    // types: each place's scars as [name, label], scar n being the n-th (catcolours.SCAR_TYPES).
    const SCARS = info.scars || { current: {}, types: {} };
    const scarTypes = part => SCARS.types[part] || [];
    const scarName = (part, n) => (scarTypes(part)[n - 1] || [])[0];
    const scarNumber = (part, name) => { const i = scarTypes(part).findIndex(t => t[0] === name); return i < 0 ? undefined : i + 1; };
    const out = wc.codePanel("cats.json");
    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Your cat" }),
        el("h1", { text: "Your cat" }),
        el("p", { class: "note", text: "Your cat's look, or any other cat's in your save: colours only that cat wears, its colour slots, scars and shape. Save to a mod, then Apply to game." })),
      el("div", { class: "banner info" }, el("strong", { text: "Two ways to colour a cat" }),
        el("span", { text: "Colours go onto the cat while you play (needs UE4SS), so any colour works, even for paws, ears and nose. Colour slots, scars and shape pick from the game's own, plus new pattern and marking colours your palettes add; they go into your save on install, after a backup." })),
      target.element, whoCard, lookCard, coloursCard, slotsCard, scarsCard, out.element);

    // ---------- the file ----------
    function parseOne(p) {
      const l = blank();
      if (!p || typeof p !== "object") return l;
      for (const [k, v] of Object.entries(p.colours || {})) { const c = color.normHex(v); if (c) l.colours[k] = c; }
      for (const [k, v] of Object.entries(p.slots || {})) {
        if (!Number.isInteger(v)) continue;
        if (k === "eyes") { l.slots.eye_left = v; l.slots.eye_right = v; } else l.slots[k] = v;
      }
      // Scars as numbers: "none" is 0, an ear's name its number ("body" is the save's name for the back).
      if (p.scars === "none") for (const s of SCAR_PARTS) l.scars[s.id] = 0;
      else if (p.scars && typeof p.scars === "object") {
        for (const [key, raw] of Object.entries(p.scars)) {
          if (key.startsWith("_")) continue;
          const k = key === "body" ? "back" : key;
          let v = raw === "none" ? 0 : raw;
          if (typeof v === "string") v = scarNumber(k, v);
          if (Number.isInteger(v) && v >= 0 && v <= scarTypes(k).length && k in SCARS.types) l.scars[k] = v;
          else l.scarsRaw[key] = raw;
        }
      }
      for (const [k, v] of Object.entries(p.look || {})) if (typeof v === "number") l.look[k] = v;
      for (const [k, v] of Object.entries(p)) if (!KEYS.includes(k)) l.extra[k] = v;
      return l;
    }
    function load(obj) {
      looks = { player: parseOne(obj && obj.player) }; fileExtra = {};
      for (const [t, v] of Object.entries((obj && obj.cats) || {})) if (!t.startsWith("_")) looks[t] = parseOne(v);
      for (const [k, v] of Object.entries(obj || {})) if (k !== "player" && k !== "cats" && !k.startsWith("_")) fileExtra[k] = v;
      if (!looks[who]) who = "player";
    }
    function oneJson(l) {
      const o = { ...l.extra };
      if (Object.keys(l.colours).length) o.colours = { ...l.colours };
      if (Object.keys(l.slots).length) {
        o.slots = { ...l.slots };
        if (o.slots.eye_left !== undefined && o.slots.eye_left === o.slots.eye_right) {
          o.slots.eyes = o.slots.eye_left; delete o.slots.eye_left; delete o.slots.eye_right;
        }
      }
      const scars = Object.entries(l.scars), raw = Object.entries(l.scarsRaw);
      if (!raw.length && scars.length === SCAR_PARTS.length && scars.every(([, n]) => n === 0)) o.scars = "none";
      else if (scars.length || raw.length) {
        o.scars = Object.fromEntries(raw);
        for (const s of SCAR_PARTS) {
          if (!(s.id in l.scars)) continue;
          const n = l.scars[s.id];
          o.scars[s.id] = n === 0 ? "none" : (scarName(s.id, n) || n);
        }
      }
      if (Object.keys(l.look).length) o.look = { ...l.look };
      return o;
    }
    function toJson() {
      const player = oneJson(looks.player), cats = {};
      for (const [t, l] of Object.entries(looks)) {
        if (t === "player") continue;
        const o = oneJson(l);
        if (Object.keys(o).length) cats[t] = o;
      }
      return { _help: "Written by Clan Mod Studio. See docs/formats.md, cats.json.", ...(Object.keys(player).length ? { player } : {}),
        ...(Object.keys(cats).length ? { cats } : {}), ...fileExtra };
    }
    function changed() { target.markDirty(); out.set(toJson()); }

    // ---------- whose look ----------
    const look = () => (looks[who] = looks[who] || blank());
    const mine = () => who === "player";
    const other = () => OTHERS.find(c => c.target === who);
    const whoName = () => mine() ? "your cat" : (other() ? other().name : who);
    // What the save has now for the cat chosen (null for a cat cats.json names that isn't in the save).
    const now = () => mine() ? { slots: info.current, scars: SCARS.current, look: (info.look || {}).current || {} }
      : (other() || {}).current || null;

    function renderWho() {
      const sel = el("select", { "aria-label": "Whose look" },
        el("option", { value: "player", text: "Your cat" }),
        ...OTHERS.map(c => el("option", { value: c.target, text: `${c.name} (${c.where}${looks[c.target] && Object.keys(oneJson(looks[c.target])).length ? ", changed" : ""})` })),
        ...Object.keys(looks).filter(t => t !== "player" && !OTHERS.some(c => c.target === t))
          .map(t => el("option", { value: t, text: `${t} (not in the game you're playing)` })));
      sel.value = who;
      sel.addEventListener("change", () => { who = sel.value; render(); });
      clear(whoCard).append(el("h2", { text: "Whose look" }),
        el("div", { class: "row" }, sel),
        el("p", { class: "note", text: mine() ? "Your cat, in the game you're playing. Choose another cat to change its look the same way: it's found by its name (or its place, when two share a name), and only it changes."
          : `${whoName()} is changed by ${/\//.test(who) ? "its place" : "its name"} (${who}). Its colours go on by its name, so a cat with the same name gets them too; a rank-up changes a cat's name: install again after one to keep its colours on it.` }));
    }

    // The colour a slot shows with the enabled palettes: a palette's colour, else the game's.
    const slotHex = (part, i) => (info.palette[part] || {})[i] || (TABLES[SLOT_PARTS.find(s => s.id === part).table] || [])[i] || null;

    function render() { renderWho(); renderLook(); renderColours(); renderSlots(); renderScars(); out.set(toJson()); }

    function renderLook() {
      const l = look(), cur = (now() || {}).look || {}, parts = (info.look || {}).parts || {};
      const rows = LOOK_PARTS.filter(p => p.id in parts).map(p => {
        const sel = el("select", { "aria-label": p.name },
          el("option", { value: "", text: `Keep the save's${p.id in cur ? ` (${cur[p.id]})` : ""}` }),
          ...[...Array(parts[p.id] + 1).keys()].map(n => el("option", { value: String(n), text: String(n) })));
        sel.value = p.id in l.look ? String(l.look[p.id]) : "";
        sel.addEventListener("change", () => { if (sel.value === "") delete l.look[p.id]; else l.look[p.id] = Number(sel.value); changed(); });
        return el("div", { class: "row" }, el("strong", { text: p.name, style: { minWidth: "150px" } }), sel,
          el("span", { class: "muted", text: p.note || "" }));
      });
      const [lo, hi] = (info.look || {}).size || [0.05, 1.5];
      const on = "size" in l.look;
      const clampSize = v => Math.max(lo, Math.min(hi, Number(v) || 0.8));
      const size = el("input", { type: "number", min: String(lo), max: String(hi), step: "0.05", value: String(clampSize(l.look.size ?? cur.size)),
        style: { width: "6em" }, "aria-label": "Size", disabled: !on });
      const box = el("input", { type: "checkbox", checked: on, "aria-label": "Change the size" });
      size.addEventListener("change", () => { const v = clampSize(size.value); l.look.size = v; size.value = v; changed(); });
      box.addEventListener("change", () => { if (box.checked) { l.look.size = clampSize(size.value); size.value = l.look.size; } else delete l.look.size; size.disabled = !box.checked; changed(); });
      clear(lookCard).append(el("h2", { text: "Shape" }),
        el("p", { class: "note", text: `${mine() ? "Your cat's" : `${whoName()}'s`} body, fur, tail, ears, eyes, whiskers and face, each one of the game's 10 (the cat maker shows a clan's 7 of them), and its pattern and markings (21 each). They go into your save on install, after a backup.${mine() ? " Body, ears and face chose your cat's traits when it was made; the traits stay as they are." : ""}` }),
        ...rows,
        el("div", { class: "row" }, el("label", { class: "row", style: { minWidth: "150px" } }, box, el("strong", { text: "Size" })), size,
          el("span", { class: "muted", text: `${cur.size != null ? `now ${cur.size}; ` : ""}a kit is about 0.1, a warrior 0.75, a leader 1.0${mine() ? ". The game sets your cat's size again when it ranks up" : ""}` })));
    }

    function renderColours() {
      const l = look();
      // The parts the build knows (catcolours.PARTS), labelled here; a part with no label shows its id.
      const parts = Object.keys(info.parts || {}).map(id => PARTS.find(p => p.id === id) || { id, name: id });
      const rows = parts.map(p => {
        const on = p.id in l.colours;
        const inp = el("input", { type: "color", value: (l.colours[p.id] || "#a0a0a0").toLowerCase(), "aria-label": `${p.name} colour`, disabled: !on });
        const box = el("input", { type: "checkbox", checked: on, "aria-label": `Use its own ${p.name.toLowerCase()} colour` });
        inp.addEventListener("input", () => { l.colours[p.id] = color.normHex(inp.value); changed(); });
        box.addEventListener("change", () => {
          if (box.checked) l.colours[p.id] = color.normHex(inp.value); else delete l.colours[p.id];
          inp.disabled = !box.checked; changed();
        });
        return el("div", { class: "row" }, el("label", { class: "row", style: { minWidth: "150px", flexWrap: "nowrap" } }, box, el("strong", { text: p.name })),
          inp, el("span", { class: "muted", text: p.note || "" }));
      });
      clear(coloursCard).append(el("h2", { text: "Colours" }),
        el("p", { class: "note", text: `Tick a part to give ${whoName()} its own colour; unticked parts keep the game's. They show while you play, in menus and portraits, and go away if you turn the mod off.` }),
        ...rows);
    }

    function renderSlots() {
      const l = look(), current = (now() || {}).slots || {};
      const blocks = SLOT_PARTS.map(s => {
        const base = (TABLES[s.table] || []).length || info.game_slots;
        const extraSlots = Object.keys(info.palette[s.id] || {}).map(Number).filter(i => i >= base).sort((a, b) => a - b);
        const slots = [...Array(base).keys(), ...extraSlots];
        const cur = current[s.id], chosen = l.slots[s.id];
        const swatch = i => {
          const hex = slotHex(s.id, i) || "#888888";
          const feral = s.id === "fur" && info.feral_slots.includes(i);
          const picked = chosen === i, isNow = cur === i && chosen === undefined;
          // Picked shows as a ring and a tick, the cat's now as a thinner ring; screen readers hear both. The
          // number is black on a light colour and white on a dark one.
          const ink = color.luminance(color.hexToLinear(hex)) > 0.18 ? ["#000", "#fff"] : ["#fff", "#000"];
          const mark = { position: "absolute", fontWeight: "700", color: ink[0], textShadow: `0 0 2px ${ink[1]}` };
          return el("button", { class: "btn swatch", type: "button", "data-focus": `slot:${s.id}:${i}`,
            title: `${s.name} slot ${i}${i >= base ? " (new)" : ""}${feral ? " (Feral Edition)" : ""}${cur === i ? ", now" : ""}`,
            "aria-pressed": String(picked), "aria-label": `${s.name} slot ${i}${i >= base ? ", new" : ""}${cur === i ? ", now" : ""}`,
            style: { width: "38px", height: "38px", padding: "0", background: hex, position: "relative",
              boxShadow: picked ? "0 0 0 3px var(--accent)" : isNow ? "0 0 0 2px var(--ink)" : "",
              border: i >= base ? "2px dashed var(--field)" : "" },
            onclick: () => { if (l.slots[s.id] === i) delete l.slots[s.id]; else l.slots[s.id] = i; changed(); renderSlots(); } },
            picked ? el("span", { "aria-hidden": "true", style: { ...mark, top: "1px", left: "4px", fontSize: "0.85rem" }, text: "✓" }) : null,
            el("span", { "aria-hidden": "true", style: { ...mark, bottom: "1px", right: "3px", fontSize: "0.75rem" }, text: String(i) }));
        };
        const state = chosen === undefined ? `now: slot ${cur ?? "?"} (kept)` : `slot ${chosen}${cur !== undefined ? ` (now ${cur})` : ""}`;
        return el("div", { style: { display: "grid", gap: "6px" } },
          el("div", { class: "row spread" }, el("h3", { text: s.name }), el("span", { class: "muted", text: state })),
          el("div", { class: "row", style: { flexWrap: "wrap", gap: "6px" } }, ...slots.map(swatch)),
          (s.id === "pattern" || s.id === "marking") && !extraSlots.length ? el("p", { class: "note", text: "Palettes can add new colours here (Palettes page, New colours)." }) : null);
      });
      clear(slotsCard).append(el("h2", { text: "Colour slots" }),
        el("p", { class: "note", text: `Pick a slot for ${whoName()} to wear; click it again to keep the one in your save. Dashed slots are new ones your palettes add, which only the cats set to them wear. Coat slots 20-24 belong to the Feral Edition.` }),
        ...blocks);
    }
    // What a scar number looks like, from the build's list; a number past it (a save the game wrote)
    // as its number.
    function scarLabel(part, n) {
      if (n === 0) return "No scar";
      return (scarTypes(part)[n - 1] || [null, `Scar ${n}`])[1];
    }

    function renderScars() {
      const l = look(), current = (now() || {}).scars || {};
      // An entry the card can't show (written by hand), for this place: kept until another choice is made.
      const rawFor = id => Object.keys(l.scarsRaw).find(k => (k === "body" ? "back" : k) === id);
      const rows = SCAR_PARTS.map(s => {
        const top = scarTypes(s.id).length, rawKey = rawFor(s.id);
        const isNow = s.id in current ? scarLabel(s.id, current[s.id]).toLowerCase() : "not in your save";
        const sel = el("select", { "aria-label": `${s.name} scar` },
          el("option", { value: "", text: `Keep the save's (${isNow})` }),
          ...[...Array(top + 1).keys()].map(n => el("option", { value: String(n), text: scarLabel(s.id, n) })),
          rawKey !== undefined ? el("option", { value: "raw", text: `As written: ${JSON.stringify(l.scarsRaw[rawKey])} (not a scar the game has)` }) : null);
        sel.value = s.id in l.scars ? String(l.scars[s.id]) : rawKey !== undefined ? "raw" : "";
        sel.addEventListener("change", () => {
          if (sel.value === "raw") return;
          if (rawKey !== undefined) delete l.scarsRaw[rawKey];
          if (sel.value === "") delete l.scars[s.id]; else l.scars[s.id] = Number(sel.value);
          changed();
        });
        return el("div", { class: "row" }, el("strong", { text: s.name, style: { minWidth: "150px" } }), sel);
      });
      const none = el("button", { class: "btn", type: "button", text: "No scars at all",
        onclick: () => { for (const s of SCAR_PARTS) l.scars[s.id] = 0; l.scarsRaw = {}; changed(); renderScars(); } });
      const keep = el("button", { class: "btn", type: "button", text: "Keep the save's scars",
        onclick: () => { l.scars = {}; l.scarsRaw = {}; changed(); renderScars(); } });
      clear(scarsCard).append(el("h2", { text: "Scars" }),
        el("p", { class: "note", text: `Choose ${whoName()}'s scars, or none. An eye scar shuts that eye; right and left are the cat's own. They go into your save on install, after a backup, and show with the game's Injury system setting on (its Gameplay settings). A boss fight can still give new ones.` }),
        ...rows, el("div", { class: "row" }, none, keep));
    }

    await target.refresh();   // last: loading renders, which needs everything above
    return {};
  },
};
