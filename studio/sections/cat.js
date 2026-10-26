// Your cat: colours only your cat wears (coat, paws, ears, nose, whiskers), which colour slots it uses,
// new pattern and marking slots from palettes included, and its scars. Writes cats.json (see wcmods/catcolours.py).
const PARTS = [
  { id: "fur", name: "Coat", note: "Replaces your coat colour, whichever coat slot you have." },
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
];

export default {
  title: "Your cat",
  async mount(root, wc) {
    const { el, api, clear, toast, color } = wc;
    // extra: the file's other keys; playerExtra: the player's other keys; scarsRaw: scar entries the card
    // can't show (a mistake for the build to report), all kept as they are.
    let look = { colours: {}, slots: {}, scars: {} }, extra = {}, playerExtra = {}, scarsRaw = {};
    const [info, tablesRes] = await Promise.all([api.get("/cat"), api.get("/game/tables")]);
    const TABLES = tablesRes.tables || {};

    const target = wc.modTarget({
      file: "cats.json",
      onLoad: obj => { load(obj); render(); },
      getValue: () => toJson(),
    });
    const coloursCard = el("div", { class: "card" }), slotsCard = el("div", { class: "card" }),
      scarsCard = el("div", { class: "card" });
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
        el("p", { class: "note", text: "Colours only your cat wears: other cats keep theirs. Save to a mod, then Apply to game." })),
      el("div", { class: "banner info" }, el("strong", { text: "Two ways to colour your cat" }),
        el("span", { text: "Colours go onto your cat while you play (needs UE4SS), so any colour works, even for paws, ears and nose. Colour slots pick from the game's colours, plus new pattern and marking colours your palettes add; they go into your save on install, after a backup." })),
      target.element, coloursCard, slotsCard, scarsCard, out.element);

    function load(obj) {
      look = { colours: {}, slots: {}, scars: {} }; extra = {}; playerExtra = {}; scarsRaw = {};
      const p = obj && obj.player;
      if (p && typeof p === "object") {
        for (const [k, v] of Object.entries(p.colours || {})) { const c = color.normHex(v); if (c) look.colours[k] = c; }
        for (const [k, v] of Object.entries(p.slots || {})) if (Number.isInteger(v)) look.slots[k] = v;
        // Scars as numbers: "none" is 0, an ear's name its number ("body" is the save's name for the back).
        if (p.scars === "none") for (const s of SCAR_PARTS) look.scars[s.id] = 0;
        else if (p.scars && typeof p.scars === "object") {
          for (const [key, raw] of Object.entries(p.scars)) {
            if (key.startsWith("_")) continue;
            const k = key === "body" ? "back" : key;
            let v = raw === "none" ? 0 : raw;
            if (typeof v === "string") v = scarNumber(k, v);
            if (Number.isInteger(v) && v >= 0 && v <= scarTypes(k).length && k in SCARS.types) look.scars[k] = v;
            else scarsRaw[key] = raw;
          }
        }
        for (const [k, v] of Object.entries(p)) if (!["colours", "slots", "scars"].includes(k)) playerExtra[k] = v;
      }
      for (const [k, v] of Object.entries(obj || {})) if (k !== "player" && !k.startsWith("_")) extra[k] = v;
    }
    function toJson() {
      const player = { ...playerExtra };
      if (Object.keys(look.colours).length) player.colours = { ...look.colours };
      if (Object.keys(look.slots).length) player.slots = { ...look.slots };
      const scars = Object.entries(look.scars), raw = Object.entries(scarsRaw);
      if (!raw.length && scars.length === SCAR_PARTS.length && scars.every(([, n]) => n === 0)) player.scars = "none";
      else if (scars.length || raw.length) {
        player.scars = Object.fromEntries(raw);
        for (const s of SCAR_PARTS) {
          if (!(s.id in look.scars)) continue;
          const n = look.scars[s.id];
          player.scars[s.id] = n === 0 ? "none" : (scarName(s.id, n) || n);
        }
      }
      return { _help: "Written by Clan Mod Studio. See README, \"cats.json\".", ...(Object.keys(player).length ? { player } : {}), ...extra };
    }
    function changed() { target.markDirty(); out.set(toJson()); }

    // The colour a slot shows with the enabled palettes: a palette's colour, else the game's.
    const slotHex = (part, i) => (info.palette[part] || {})[i] || (TABLES[SLOT_PARTS.find(s => s.id === part).table] || [])[i] || null;

    function render() { renderColours(); renderSlots(); renderScars(); out.set(toJson()); }

    function renderColours() {
      // The parts the build knows (catcolours.PARTS), labelled here; a part with no label shows its id.
      const parts = Object.keys(info.parts || {}).map(id => PARTS.find(p => p.id === id) || { id, name: id });
      const rows = parts.map(p => {
        const on = p.id in look.colours;
        const inp = el("input", { type: "color", value: (look.colours[p.id] || "#a0a0a0").toLowerCase(), "aria-label": `${p.name} colour`, disabled: !on });
        const box = el("input", { type: "checkbox", checked: on, "aria-label": `Use my own ${p.name.toLowerCase()} colour` });
        inp.addEventListener("input", () => { look.colours[p.id] = color.normHex(inp.value); changed(); });
        box.addEventListener("change", () => {
          if (box.checked) look.colours[p.id] = color.normHex(inp.value); else delete look.colours[p.id];
          inp.disabled = !box.checked; changed();
        });
        return el("div", { class: "row" }, el("label", { class: "row", style: { minWidth: "150px", flexWrap: "nowrap" } }, box, el("strong", { text: p.name })),
          inp, el("span", { class: "muted", text: p.note || "" }));
      });
      clear(coloursCard).append(el("h2", { text: "Colours" }),
        el("p", { class: "note", text: "Tick a part to give your cat its own colour; unticked parts keep the game's. They show while you play, in menus and portraits, and go away if you turn the mod off." }),
        ...rows);
    }

    function renderSlots() {
      const blocks = SLOT_PARTS.map(s => {
        const base = (TABLES[s.table] || []).length || info.game_slots;
        const extraSlots = Object.keys(info.palette[s.id] || {}).map(Number).filter(i => i >= base).sort((a, b) => a - b);
        const slots = [...Array(base).keys(), ...extraSlots];
        const cur = info.current[s.id], chosen = look.slots[s.id];
        const swatch = i => {
          const hex = slotHex(s.id, i) || "#888888";
          const feral = s.id === "fur" && info.feral_slots.includes(i);
          const picked = chosen === i, now = cur === i && chosen === undefined;
          // Picked shows as a ring and a tick, yours now as a thinner ring; screen readers hear both. The
          // number is black on a light colour and white on a dark one.
          const ink = color.luminance(color.hexToLinear(hex)) > 0.18 ? ["#000", "#fff"] : ["#fff", "#000"];
          const mark = { position: "absolute", fontWeight: "700", color: ink[0], textShadow: `0 0 2px ${ink[1]}` };
          return el("button", { class: "btn swatch", type: "button", "data-focus": `slot:${s.id}:${i}`,
            title: `${s.name} slot ${i}${i >= base ? " (new)" : ""}${feral ? " (Feral Edition)" : ""}${cur === i ? ", yours now" : ""}`,
            "aria-pressed": String(picked), "aria-label": `${s.name} slot ${i}${i >= base ? ", new" : ""}${cur === i ? ", yours now" : ""}`,
            style: { width: "38px", height: "38px", padding: "0", background: hex, position: "relative",
              boxShadow: picked ? "0 0 0 3px var(--accent)" : now ? "0 0 0 2px var(--ink)" : "",
              border: i >= base ? "2px dashed var(--field)" : "" },
            onclick: () => { if (look.slots[s.id] === i) delete look.slots[s.id]; else look.slots[s.id] = i; changed(); renderSlots(); } },
            picked ? el("span", { "aria-hidden": "true", style: { ...mark, top: "1px", left: "4px", fontSize: "0.85rem" }, text: "✓" }) : null,
            el("span", { "aria-hidden": "true", style: { ...mark, bottom: "1px", right: "3px", fontSize: "0.75rem" }, text: String(i) }));
        };
        const state = chosen === undefined ? `yours now: slot ${cur ?? "?"} (kept)` : `slot ${chosen}${cur !== undefined ? ` (now ${cur})` : ""}`;
        return el("div", { style: { display: "grid", gap: "6px" } },
          el("div", { class: "row spread" }, el("h3", { text: s.name }), el("span", { class: "muted", text: state })),
          el("div", { class: "row", style: { flexWrap: "wrap", gap: "6px" } }, ...slots.map(swatch)),
          s.id !== "fur" && !extraSlots.length ? el("p", { class: "note", text: "Palettes can add new colours here (Palettes page, New colours)." }) : null);
      });
      clear(slotsCard).append(el("h2", { text: "Colour slots" }),
        el("p", { class: "note", text: "Pick a slot to wear it; click it again to keep the one in your save. Dashed slots are new ones your palettes add, which only your cat wears. Coat slots 20-24 belong to the Feral Edition." }),
        ...blocks);
    }
    // What a scar number looks like, from the build's list; a number past it (a save the game wrote)
    // as its number.
    function scarLabel(part, n) {
      if (n === 0) return "No scar";
      return (scarTypes(part)[n - 1] || [null, `Scar ${n}`])[1];
    }

    function renderScars() {
      // An entry the card can't show (written by hand), for this place: kept until another choice is made.
      const rawFor = id => Object.keys(scarsRaw).find(k => (k === "body" ? "back" : k) === id);
      const rows = SCAR_PARTS.map(s => {
        const top = scarTypes(s.id).length, rawKey = rawFor(s.id);
        const now = s.id in SCARS.current ? scarLabel(s.id, SCARS.current[s.id]).toLowerCase() : "no save yet";
        const sel = el("select", { "aria-label": `${s.name} scar` },
          el("option", { value: "", text: `Keep my save's (${now})` }),
          ...[...Array(top + 1).keys()].map(n => el("option", { value: String(n), text: scarLabel(s.id, n) })),
          rawKey !== undefined ? el("option", { value: "raw", text: `As written: ${JSON.stringify(scarsRaw[rawKey])} (not a scar the game has)` }) : null);
        sel.value = s.id in look.scars ? String(look.scars[s.id]) : rawKey !== undefined ? "raw" : "";
        sel.addEventListener("change", () => {
          if (sel.value === "raw") return;
          if (rawKey !== undefined) delete scarsRaw[rawKey];
          if (sel.value === "") delete look.scars[s.id]; else look.scars[s.id] = Number(sel.value);
          changed();
        });
        return el("div", { class: "row" }, el("strong", { text: s.name, style: { minWidth: "150px" } }), sel);
      });
      const none = el("button", { class: "btn", type: "button", text: "No scars at all",
        onclick: () => { for (const s of SCAR_PARTS) look.scars[s.id] = 0; scarsRaw = {}; changed(); renderScars(); } });
      const keep = el("button", { class: "btn", type: "button", text: "Keep my save's scars",
        onclick: () => { look.scars = {}; scarsRaw = {}; changed(); renderScars(); } });
      clear(scarsCard).append(el("h2", { text: "Scars" }),
        el("p", { class: "note", text: "Choose your cat's scars, or none. An eye scar shuts that eye; right and left are your cat's own. They go into your save on install, after a backup, and show with the game's Injury system setting on (its Gameplay settings). A boss fight can still give new ones." }),
        ...rows, el("div", { class: "row" }, none, keep));
    }

    await target.refresh();   // last: loading renders, which needs everything above
    return {};
  },
};
