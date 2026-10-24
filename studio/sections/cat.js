// Your cat: colours only your cat wears (coat, paws, ears, nose, whiskers), and which colour slots it uses,
// new pattern and marking slots from palettes included. Writes cats.json (see wcmods/catlook.py).
const PARTS = [
  { id: "fur", name: "Coat", note: "Replaces your coat colour, whichever coat slot you have." },
  { id: "paws", name: "Paw pads" }, { id: "ears", name: "Inner ears" }, { id: "nose", name: "Nose" },
  { id: "whiskers", name: "Whiskers" },
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
    let look = { colours: {}, slots: {} }, extra = {};
    const [info, tablesRes] = await Promise.all([api.get("/cat"), api.get("/game/tables")]);
    const TABLES = tablesRes.tables || {};

    const target = wc.modTarget({
      file: "cats.json", defaultId: "my-cat", defaultName: "My Cat",
      onLoad: obj => { load(obj); render(); },
      getValue: () => toJson(),
    });
    const coloursCard = el("div", { class: "card" }), slotsCard = el("div", { class: "card" });
    const out = wc.codePanel("cats.json");
    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Your cat" }),
        el("h1", { text: "Your cat" }),
        el("p", { class: "note", text: "Colours only your cat wears: other cats keep theirs. Save to a mod, then install." })),
      el("div", { class: "banner info" }, el("strong", { text: "Two ways to colour your cat" }),
        el("span", { text: "Colours go onto your cat while you play (needs UE4SS), so any colour works, even for paws, ears and nose. Colour slots pick from the game's colours, plus new pattern and marking colours your palettes add; they go into your save on install, after a backup." })),
      target.element, coloursCard, slotsCard, out.element);

    function load(obj) {
      look = { colours: {}, slots: {} }; extra = {};
      const p = obj && obj.player;
      if (p && typeof p === "object") {
        for (const [k, v] of Object.entries(p.colours || {})) { const c = color.normHex(v); if (c) look.colours[k] = c; }
        for (const [k, v] of Object.entries(p.slots || {})) if (Number.isInteger(v)) look.slots[k] = v;
      }
      for (const [k, v] of Object.entries(obj || {})) if (k !== "player" && !k.startsWith("_")) extra[k] = v;
    }
    function toJson() {
      const player = {};
      if (Object.keys(look.colours).length) player.colours = { ...look.colours };
      if (Object.keys(look.slots).length) player.slots = { ...look.slots };
      return { _help: "Written by Clan Mod Studio. See README, \"cats.json\".", ...(Object.keys(player).length ? { player } : {}), ...extra };
    }
    function changed() { target.markDirty(); out.set(toJson()); }

    // The colour a slot shows with the enabled palettes: a palette's colour, else the game's.
    const slotHex = (part, i) => (info.palette[part] || {})[i] || (TABLES[SLOT_PARTS.find(s => s.id === part).table] || [])[i] || null;

    function render() { renderColours(); renderSlots(); out.set(toJson()); }

    function renderColours() {
      // The parts the build knows (catlook.PARTS), labelled here; a part with no label shows its id.
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
        el("p", { class: "note", text: "Tick a part to give your cat its own colour; unticked parts keep the game's. They show while you play, in menus and portraits, and go away if you uninstall." }),
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
          return el("button", { class: "btn", type: "button",
            title: `${s.name} slot ${i}${i >= base ? " (new)" : ""}${feral ? " (Feral Edition)" : ""}${cur === i ? ", yours now" : ""}`,
            "aria-pressed": String(picked), "aria-label": `${s.name} slot ${i}`,
            style: { width: "38px", height: "38px", padding: "0", background: hex, position: "relative",
              boxShadow: picked ? "0 0 0 3px var(--accent)" : now ? "0 0 0 2px var(--ink)" : "",
              outline: i >= base ? "2px dashed var(--line)" : "" },
            onclick: () => { if (look.slots[s.id] === i) delete look.slots[s.id]; else look.slots[s.id] = i; changed(); renderSlots(); } },
            el("span", { style: { position: "absolute", bottom: "1px", right: "3px", fontSize: "0.62rem", color: "#000", textShadow: "0 0 2px #fff" }, text: String(i) }));
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
    await target.refresh();   // last: loading renders, which needs everything above
    return {};
  },
};
