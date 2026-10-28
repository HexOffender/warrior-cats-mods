// Cats' looks: colours only that cat wears (coat, paws, ears, nose, whiskers), which of the game's colours it uses
// (new pattern and marking colours from palettes included), its scars and its shape (body, ears, tail, pattern...),
// for your cat and for any cat in your save (cats.json's "cats", by name or place). Writes cats.json (see
// wcmods/catcolours.py); reading and writing it is lib/catlook.js.
import * as C from "../lib/catlook.js";

const PARTS = [
  { id: "fur", name: "Coat", note: "Replaces the coat colour, whichever of the game's coats it has." },
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

export default {
  title: "Your cat",
  async mount(root, wc) {
    const { el, api, clear, toast, color } = wc;
    // clear() hands back the bare element, whose own append writes a null as the text "null": this leaves them out.
    const put = (node, ...kids) => { clear(node).append(...kids.filter(k => k != null && k !== false)); return node; };
    // looks: each cat's choices, "player" for yours and the others by their cats.json key (lib/catlook.js says
    // what each holds); fileExtra: the file's other keys, kept as they are.
    let looks = { player: C.blank() }, fileExtra = {}, who = "player";
    const [firstInfo, tablesRes] = await Promise.all([api.get("/cat"), api.get("/game/tables").catch(() => ({ tables: null }))]);
    let info = firstInfo;
    const TABLES = tablesRes.tables || {};
    const known = () => C.knownFrom(info);
    const others = () => info.cats || [];

    const target = wc.modTarget({
      file: "cats.json",
      onLoad: obj => { ({ looks, fileExtra } = C.load(obj, known())); if (!looks[who]) who = "player"; render(); },
      getValue: () => C.toJson(looks, fileExtra, known()),
    });
    const saveLine = el("div", { class: "banner", role: "status", hidden: true });
    const whoCard = el("div", { class: "card" }), lookCard = el("div", { class: "card" }),
      coloursCard = el("div", { class: "card" }), slotsCard = el("div", { class: "card" }), scarsCard = el("div", { class: "card" });
    // types: each place's scars as [name, label], scar n being the n-th (catcolours.SCAR_TYPES).
    const scars = () => info.scars || { current: {}, types: {} };
    const scarTypes = part => scars().types[part] || [];
    const out = wc.codePanel("cats.json");
    root.append(
      wc.pageHead({ eyebrow: "Your cat", title: "Your cat",
        lede: "Your cat's look, or any other cat's in your save: colours only that cat wears, which of the game's colours it uses, its scars and its shape. Save to a mod, then Apply to game.",
        help: "help:cat" }),
      el("div", { class: "banner info" }, el("strong", { text: "Two ways to colour a cat" }),
        el("span", { text: "Colours of its own go onto the cat while you play (they need the script loader), so any colour works, even for paws, ears and nose. The game's colours, scars and shape pick from the game's own, plus new pattern and marking colours your palettes add; they go into your save on Apply, after a backup." })),
      saveLine, target.element, whoCard, lookCard, coloursCard, slotsCard, scarsCard, out.element);

    function changed() { target.markDirty(); out.set(C.toJson(looks, fileExtra, known())); }

    // What the page can't change, under the card it belongs to: each kept as written until its Remove.
    function cantChange(entries) {
      if (!entries.length) return null;
      return el("div", { class: "stack" },
        el("strong", { text: "Things this page can't change" }),
        el("p", { class: "note", text: "They're in the file as written, and Save says whether they keep it out of the game. Remove takes one out." }),
        el("ul", { class: "notes" }, ...entries.map(e => el("li", { class: "row" },
          el("span", { class: "mono", text: `${e.where}: ${JSON.stringify(e.value)}` }),
          el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${e.where}`, onclick: () => { e.remove(); changed(); render(); } })))));
    }
    const rawOf = key => C.cantChange(look()).filter(e => e.where.startsWith(key + "."));

    // ---------- whose look ----------
    const look = () => (looks[who] = looks[who] || C.blank());
    const mine = () => who === "player";
    const other = () => others().find(c => c.target === who);
    const whoName = () => mine() ? "your cat" : (other() ? other().name : who);
    // What the save has now for the cat chosen (null for a cat cats.json names that isn't in the save, or for a
    // save that can't be read now).
    const saveRead = () => !info.save_problem;
    const now = () => !saveRead() ? null : mine() ? { slots: info.current, scars: scars().current, look: (info.look || {}).current || {} }
      : (other() || {}).current || null;

    function renderSaveLine() {
      saveLine.hidden = saveRead();
      clear(saveLine);
      if (!saveRead()) saveLine.append(el("strong", { text: "What your cat wears now isn't shown" }), el("span", { text: `${info.save_problem}. Colours of its own work all the same.` }));
    }

    function renderWho() {
      const changedMark = t => looks[t] && Object.keys(C.oneJson(looks[t], known())).length ? ", changed" : "";
      const sel = el("select", { "aria-label": "Whose look" },
        el("option", { value: "player", text: "Your cat" }),
        ...others().map(c => el("option", { value: c.target, text: `${c.name} (${c.where}${changedMark(c.target)})` })),
        ...Object.keys(looks).filter(t => t !== "player" && !others().some(c => c.target === t))
          .map(t => el("option", { value: t, text: `${t} (${saveRead() ? "not in the game you're playing" : "your save can't be read now"})` })));
      sel.value = who;
      sel.addEventListener("change", () => { who = sel.value; render(); });
      put(whoCard, el("h2", { text: "Whose look" }),
        el("div", { class: "row" }, sel),
        el("p", { class: "note", text: mine() ? "Your cat, in the game you're playing. Choose another cat to change its look the same way: it's found by its name (or its place, when two share a name), and only it changes."
          : `${whoName()} is changed by ${/\//.test(who) ? "its place" : "its name"} (${who}). Its colours go on by its name, so a cat with the same name gets them too; a rank-up changes a cat's name: apply again after one to keep its colours on it.` }));
      const raw = C.cantChange(look(), mine() ? fileExtra : null).filter(e => !/^(colours|slots|scars|look)\./.test(e.where));
      const block = cantChange(raw);
      if (block) whoCard.append(block);
    }

    // The colour a slot shows with the enabled palettes: a palette's colour, else the game's.
    const slotHex = (part, i) => (info.palette[part] || {})[i] || (TABLES[SLOT_PARTS.find(s => s.id === part).table] || [])[i] || null;

    function render() {
      renderSaveLine(); renderWho(); renderLook(); renderColours(); renderSlots(); renderScars();
      out.set(C.toJson(looks, fileExtra, known()));
    }

    function renderLook() {
      const l = look(), cur = (now() || {}).look || {}, parts = (info.look || {}).parts || {};
      const rows = LOOK_PARTS.filter(p => p.id in parts).map(p => {
        const sel = el("select", { "aria-label": p.name },
          el("option", { value: "", text: `Keep the save's${p.id in cur ? ` (${cur[p.id]})` : saveRead() ? "" : " (unknown now)"}` }),
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
      put(lookCard, el("h2", { text: "Shape" }),
        el("p", { class: "note", text: `${mine() ? "Your cat's" : `${whoName()}'s`} body, fur, tail, ears, eyes, whiskers and face, each one of the game's 10 (the cat maker shows a clan's 7 of them), and its pattern and markings (21 each). They go into your save on Apply, after a backup.${mine() ? " Body, ears and face chose your cat's traits when it was made; the traits stay as they are." : ""}` }),
        ...rows,
        el("div", { class: "row" }, el("label", { class: "row", style: { minWidth: "150px" } }, box, el("strong", { text: "Size" })), size,
          el("span", { class: "muted", text: `${cur.size != null ? `now ${cur.size}; ` : ""}a kit is about 0.1, a warrior 0.75, a leader 1.0${mine() ? ". The game sets your cat's size again when it ranks up" : ""}` })));
      const block = cantChange(rawOf("look"));
      if (block) lookCard.append(block);
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
      put(coloursCard, el("h2", { text: "Colours of its own" }),
        el("p", { class: "note", text: `Tick a part to give ${whoName()} its own colour; unticked parts keep the game's. They show while you play, in menus and portraits, and go away if you turn the mod off.` }),
        ...rows);
      const block = cantChange(rawOf("colours"));
      if (block) coloursCard.append(block);
    }

    function renderSlots() {
      const l = look(), current = (now() || {}).slots || {};
      const shown = saveRead();
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
            title: `${s.name} ${i}${i >= base ? " (new)" : ""}${feral ? " (Feral Edition)" : ""}${cur === i ? ", now" : ""}`,
            "aria-pressed": String(picked), "aria-label": `${s.name} ${i}${i >= base ? ", new" : ""}${cur === i ? ", now" : ""}`,
            style: { width: "38px", height: "38px", padding: "0", background: hex, position: "relative",
              boxShadow: picked ? "0 0 0 3px var(--accent)" : isNow ? "0 0 0 2px var(--ink)" : "",
              border: i >= base ? "2px dashed var(--field)" : "" },
            onclick: () => { if (l.slots[s.id] === i) delete l.slots[s.id]; else l.slots[s.id] = i; changed(); renderSlots(); } },
            picked ? el("span", { "aria-hidden": "true", style: { ...mark, top: "1px", left: "4px", fontSize: "0.85rem" }, text: "✓" }) : null,
            el("span", { "aria-hidden": "true", style: { ...mark, bottom: "1px", right: "3px", fontSize: "0.75rem" }, text: String(i) }));
        };
        const nowText = !shown ? "unknown" : cur ?? "?";
        const state = chosen === undefined ? `now: ${nowText} (kept)` : `${chosen}${cur !== undefined ? ` (now ${cur})` : ""}`;
        return el("div", { style: { display: "grid", gap: "6px" } },
          el("div", { class: "row spread" }, el("h3", { text: s.name }), el("span", { class: "muted", text: state })),
          el("div", { class: "row", style: { flexWrap: "wrap", gap: "6px" } }, ...slots.map(swatch)),
          (s.id === "pattern" || s.id === "marking") && !extraSlots.length ? el("p", { class: "note", text: "Palettes can add new colours here (Palettes page, New colours)." }) : null);
      });
      const tablesMissing = !Object.keys(TABLES).length;
      put(slotsCard, el("h2", { text: "Colours from the game's picker" }),
        el("p", { class: "note", text: `Pick one of the game's colours for ${whoName()} to wear, by its number; click it again to keep the one in your save. Dashed ones are new colours your palettes add, which only the cats set to them wear. Coats 20-24 belong to the Feral Edition.` }),
        tablesMissing ? el("p", { class: "note", text: "The game's colours show here once the game has run with the script loader (press Play once after an Apply); until then they're grey squares with their numbers." }) : null,
        ...blocks);
      const block = cantChange(rawOf("slots"));
      if (block) slotsCard.append(block);
    }
    // What a scar number looks like, from the build's list; a number past it (a save the game wrote)
    // as its number.
    function scarLabel(part, n) {
      if (n === 0) return "No scar";
      return (scarTypes(part)[n - 1] || [null, `Scar ${n}`])[1];
    }

    function renderScars() {
      const l = look(), current = (now() || {}).scars || {};
      // A place's entry the page can't show (written by hand) goes when the page chooses for that place.
      const dropRaw = id => { for (const k of Object.keys(l.raw.scars)) if ((k === "body" ? "back" : k) === id) delete l.raw.scars[k]; };
      const rows = SCAR_PARTS.map(s => {
        const top = scarTypes(s.id).length;
        const isNow = !saveRead() ? "unknown now" : s.id in current ? scarLabel(s.id, current[s.id]).toLowerCase() : "not in your save";
        const sel = el("select", { "aria-label": `${s.name} scar` },
          el("option", { value: "", text: `Keep the save's (${isNow})` }),
          ...[...Array(top + 1).keys()].map(n => el("option", { value: String(n), text: scarLabel(s.id, n) })));
        sel.value = s.id in l.scars ? String(l.scars[s.id]) : "";
        sel.addEventListener("change", () => {
          const had = rawOf("scars").length;
          dropRaw(s.id);
          if (sel.value === "") delete l.scars[s.id]; else l.scars[s.id] = Number(sel.value);
          changed();
          if (rawOf("scars").length !== had) renderScars();   // its entry left the list of things the page can't change
        });
        return el("div", { class: "row" }, el("strong", { text: s.name, style: { minWidth: "150px" } }), sel);
      });
      const none = el("button", { class: "btn", type: "button", text: "No scars at all", "data-focus": "scars:none",
        onclick: () => { for (const s of SCAR_PARTS) l.scars[s.id] = 0; l.raw.scars = {}; changed(); renderScars(); } });
      const keep = el("button", { class: "btn", type: "button", text: "Keep the save's scars", "data-focus": "scars:keep",
        onclick: () => { l.scars = {}; l.raw.scars = {}; changed(); renderScars(); } });
      put(scarsCard, el("h2", { text: "Scars" }),
        el("p", { class: "note", text: `Choose ${whoName()}'s scars, or none. An eye scar shuts that eye; right and left are the cat's own. They go into your save on Apply, after a backup, and show with the game's Injury system setting on (its Gameplay settings). A boss fight can still give new ones.` }),
        ...rows, el("div", { class: "row" }, none, keep));
      const block = cantChange(rawOf("scars"));
      if (block) scarsCard.append(block);
    }

    // What your cat wears now is read again after an Apply or Play (it wrote the save), after another page saved a
    // mod (a palette's new colour), and on coming back to the window (the game may have changed the save): the
    // page's own choices stay, unsaved ones too. The file itself is read again after an Apply only while nothing
    // here is unsaved (installedEvent); coming back re-reads it when it changed (the bar does that).
    async function readCat() {
      try { info = await api.get("/cat"); } catch (e) { return; }
      render();
    }
    const offs = [
      wc.installedEvent(target, () => target.refresh()),
      ...["installed", "mods-changed", "focus"].map(evt => wc.bus.on(evt, readCat)),
    ];
    await target.refresh();   // last: loading renders, which needs everything above
    return { unmount() { for (const off of offs) off(); } };
  },
};
