// Cats' looks: colours only that cat wears (coat, paws, ears, nose, whiskers), which of the game's colours it uses
// (new pattern and marking colours from palettes included), its scars and its shape (body, ears, tail, pattern...),
// for your cat and for any cat in your save (cats.json's "cats", by name or place). Writes cats.json (see
// wcmods/catcolours.py); reading and writing it is lib/catlook.js, and the drawn cat lib/cat.js (the Palettes page's).
import * as C from "../lib/catlook.js";
import { catSvg, paintCat } from "../lib/cat.js";
import { eyeRamp, plainRow } from "../lib/palette.js";

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
  { id: "body", name: "Body", note: "the fur's shape follows it, as in the cat maker" }, { id: "fur", name: "Fur shape" },
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
    // GET /cat, the game's colour tables and eye colours (either may not be readable yet), and the studio's status
    // (the script loader, the last Apply).
    const [firstInfo, tablesRes, eyesRes, firstStatus] = await Promise.all([api.get("/cat"),
      api.get("/game/tables").catch(() => ({ tables: null })), api.get("/game/eyes").catch(() => null), api.get("/info").catch(() => null)]);
    let info = firstInfo, status = firstStatus;
    const TABLES = tablesRes.tables || {};
    const EYE_LIN = eyesRes ? eyesRes.rows.map(r => r.map(h => color.hexToLinear("#" + h))) : null;
    const known = () => C.knownFrom(info);
    const others = () => info.cats || [];
    // An eye colour as the game draws it: atlas row slot + 1 (row 0 is the eye white), with an enabled palette's
    // colour on it. Without the game's files, the cat maker's button colour (IrisColors) on a plain strip.
    const eyeOf = row => (info.eyes || {})[String(row)] || null;
    function eyeStrip(slot) {
      if (EYE_LIN && EYE_LIN[slot + 1]) return eyeRamp(EYE_LIN[slot + 1], eyeOf(slot + 1));
      const hex = (TABLES.IrisColors || [])[slot];
      return hex ? eyeRamp(plainRow(64), { mode: "single", colors: [hex] }) : plainRow(64);
    }
    const rimOf = ramp => color.linearToHex(ramp[ramp.length - 1]);
    const eyeName = slot => (eyesRes ? eyesRes.labels[slot + 1] : null);

    const target = wc.modTarget({
      file: "cats.json",
      onLoad: obj => { ({ looks, fileExtra } = C.load(obj, known())); if (!looks[who]) who = "player"; render(); },
      getValue: () => C.toJson(looks, fileExtra, known()),
      // Saved: the page reads what it wrote as it reads any file (a save doesn't read the file back), on the same
      // cat. Not when something changed while it saved: that stays on the page, still to be saved.
      onSaved: (saved, { changed }) => { if (changed) return; ({ looks, fileExtra } = C.load(saved, known())); render(); },
    });
    const saveLine = el("div", { class: "banner", role: "status", hidden: true });
    const whoCard = el("div", { class: "card" }), lookCard = el("div", { class: "card" }),
      coloursCard = el("div", { class: "card" }), slotsCard = el("div", { class: "card" }), scarsCard = el("div", { class: "card" });
    // types: each place's scars as [name, label], scar n being the n-th (catcolours.SCAR_TYPES).
    const scars = () => info.scars || { current: {}, types: {} };
    const scarTypes = part => scars().types[part] || [];
    const out = wc.codePanel("cats.json");
    // The drawn cat, as the choices on this page would make it, and what the save holds now.
    const stage = el("div", { class: "cat-stage" });
    stage.innerHTML = catSvg("cat", "The drawn cat, with its look as chosen on this page");
    const svg = stage.querySelector("svg");
    const nowCard = el("div", { class: "card" });
    root.append(
      wc.pageHead({ eyebrow: "Your cat", title: "Your cat",
        lede: "Your cat's look, or any other cat's in your save: colours only that cat wears, which of the game's colours it uses, its scars and its shape. Save to a mod, then Apply to game.",
        help: "help:cat" }),
      el("div", { class: "banner info" }, el("strong", { text: "Two ways to colour a cat" }),
        el("span", { text: "Colours of its own go onto the cat while you play (they need the script loader), so any colour works, even for paws, ears and nose. The game's colours, scars and shape pick from the game's own, plus new pattern and marking colours your palettes add; they go into your save on Apply, after a backup." })),
      saveLine, target.element, whoCard,
      el("div", { class: "cat-top" },
        el("div", { class: "card" }, stage,
          el("p", { class: "note", text: "The drawing shows colours and head scars; the body shape, the back and chest scars and the paws aren't in it." })),
        nowCard),
      lookCard, coloursCard, slotsCard, scarsCard,
      el("details", { class: "card fold" },
        el("summary", {}, el("h3", { text: "For people who edit the file by hand" }), el("span", { class: "muted", text: "this page's cats.json, as Save writes it" })),
        out.element));

    function changed() {
      target.markDirty();
      out.set(C.toJson(looks, fileExtra, known()));
      drawCat();
      // A cat's entry kept as written ("player": "none") says beside it once a look set here takes its place.
      if (Object.keys(fileExtra).some(k => k === "player" || (k.startsWith("cats.") && !k.startsWith("cats._")))) renderWho();
    }

    // What the page can't change, under the card it belongs to: each kept as written until its Remove.
    function cantChange(entries) {
      if (!entries.length) return null;
      return el("div", { class: "stack" },
        el("strong", { text: "Things this page can't change" }),
        el("p", { class: "note", text: "They're in the file as written, and Save says whether they keep it out of the game. Remove takes one out." }),
        el("ul", { class: "notes" }, ...entries.map(e => el("li", { class: "row" },
          el("span", { class: "mono", text: `${e.where}: ${JSON.stringify(e.value)}` }),
          // A cat's entry that isn't a look ("player": "none"): the look set here takes its place at Save.
          C.lookFor(looks, e.where, known()) ? el("span", { class: "muted", text: "the look set on this page takes its place when you save" }) : null,
          el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${e.where}`, onclick: () => { e.remove(); changed(); render(); } })))));
    }
    const rawOf = key => C.cantChange(look()).filter(e => e.where.startsWith(key + "."));

    // ---------- whose look ----------
    const look = () => (looks[who] = looks[who] || C.blank());
    const mine = () => who === "player";
    // The cat being changed: the one whose target the key is, else the first the key means (the build's way).
    const other = () => others().find(c => c.target === who) || C.catsFor(who, others())[0];
    const fileKeys = () => Object.keys(looks).filter(t => t !== "player");
    const changedLook = t => looks[t] && Object.keys(C.oneJson(looks[t], known())).length > 0;
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

    // The cats to choose from, by clan (yours first), each by its name and role, with the file's keys that mean no
    // single cat (a name two cats share, a cat not in the save) after them. The filter box narrows the list.
    let filter = "";
    const GROUP_WORDS = { NarrativeRoles: "Story roles" };
    function whoOptions() {
      const cats = others(), keys = fileKeys(), f = filter.trim().toLowerCase(), chosen = whoValue();
      // The chosen cat stays in the list whatever the filter says, so the box never shows another one.
      const shown = c => !f || `cat:${c.target}` === chosen || [c.name, c.where, C.roleWords(c.role)].some(s => s.toLowerCase().includes(f));
      const optionFor = c => {
        const key = C.keyFor(c, keys, cats), kept = key !== c.target && key in looks;
        const shared = keys.filter(k => C.catsFor(k, cats).length > 1 && C.catsFor(k, cats).includes(c));
        const label = [c.name, C.roleWords(c.role)].filter(Boolean).join(", ")
          + (changedLook(key) || shared.some(changedLook) ? ", changed" : "") + (kept ? ` (in the file as "${key}")` : "");
        return el("option", { value: `cat:${c.target}`, text: label, title: c.where });
      };
      const clans = [...new Set(cats.map(c => c.clan || ""))]
        .sort((a, b) => (b === info.your_clan) - (a === info.your_clan) || (b.endsWith("Clan") - a.endsWith("Clan")) || a.localeCompare(b));
      const groups = clans.map(clan => {
        const inIt = cats.filter(c => (c.clan || "") === clan && shown(c));
        return inIt.length ? el("optgroup", { label: GROUP_WORDS[clan] || clan || "Other cats" }, ...inIt.map(optionFor)) : null;
      });
      // Keys that mean two or more cats, or none the page lists.
      const anyNames = cats.some(c => (c.aliases?.names || []).length);
      const loose = keys.filter(k => C.catsFor(k, cats).length !== 1).map(k => {
        const hits = C.catsFor(k, cats);
        const why = hits.length > 1 ? `changes ${hits.length} cats called ${hits[0].name}`
          : !saveRead() ? "your save can't be read now"
          : /^\d+\//.test(k) ? "a cat in another game"
          : !k.includes("/") && !anyNames ? "found by its name once the game's files can be read"
          : "not in your save";
        return el("option", { value: `key:${k}`, text: `"${k}" (${why})` });
      });
      return [el("option", { value: "player", text: "Your cat" }), ...groups,
        loose.length ? el("optgroup", { label: "In the file" }, ...loose) : null];
    }
    // The option that stands for `who`: your cat, the cat a key of its own means, else the key itself.
    function whoValue() {
      if (mine()) return "player";
      const cats = others(), hits = C.catsFor(who, cats);
      const own = cats.find(c => c.target === who) || (hits.length === 1 && C.keyFor(hits[0], fileKeys(), cats) === who ? hits[0] : null);
      return own ? `cat:${own.target}` : `key:${who}`;
    }
    function renderWho() {
      const sel = el("select", { "aria-label": "Whose look" }, ...whoOptions());
      sel.value = whoValue();
      sel.addEventListener("change", () => {
        const v = sel.value;
        const cat = v.startsWith("cat:") && others().find(c => c.target === v.slice(4));
        who = v === "player" ? "player" : cat ? C.keyFor(cat, fileKeys(), others()) : v.slice(4);
        render();
      });
      const find = el("input", { type: "search", value: filter, placeholder: "Find a cat", "aria-label": "Find a cat by name, place or role" });
      find.addEventListener("input", () => {
        filter = find.value;
        const keep = sel.value;
        clear(sel).append(...whoOptions().filter(Boolean));
        sel.value = keep;
      });
      const hits = mine() ? [] : C.catsFor(who, others());
      const note = mine() ? "Your cat, in the game you're playing. Choose another cat to change its look the same way: it's found by its name (or its place, when two share a name), and only it changes."
        : hits.length > 1 ? `"${who}" changes ${hits.length} cats called ${hits[0].name} (${hits.map(c => c.where).join(", ")}). Choose one of them above to change just it.`
        : `${whoName()} is changed by ${/\//.test(who) ? "its place" : "its name"} (${who}). Its colours go on by its name, so a cat with the same name gets them too; a rank-up changes a cat's name: apply again after one to keep its colours on it.`;
      put(whoCard, el("h2", { text: "Whose look" }),
        el("div", { class: "row" }, find, sel),
        el("p", { class: "note", text: note }));
      // Yours lists the file's own keys too; another cat's, its own entry when the file has it as something else.
      const theirs = !mine() && `cats.${who}` in fileExtra ? { [`cats.${who}`]: fileExtra[`cats.${who}`] } : null;
      const raw = [...C.cantChange(look(), mine() ? fileExtra : null), ...(theirs ? C.cantChange(C.blank(), theirs) : [])]
        .filter(e => !/^(colours|slots|scars|look)\./.test(e.where))
        .map(e => (theirs && e.where in theirs ? { ...e, remove: () => { delete fileExtra[e.where]; } } : e));
      const block = cantChange(raw);
      if (block) whoCard.append(block);
    }

    // The colour a slot shows with the enabled palettes: a palette's colour, else the game's; an eye, its rim.
    const slotHex = (part, i) => (part.startsWith("eye") ? (EYE_LIN || TABLES.IrisColors ? rimOf(eyeStrip(i)) : null)
      : (info.palette[part] || {})[i] || (TABLES[SLOT_PARTS.find(s => s.id === part).table] || [])[i] || null);

    function render() {
      renderSaveLine(); renderWho(); renderNow(); renderLook(); renderColours(); renderSlots(); renderScars(); drawCat();
      out.set(C.toJson(looks, fileExtra, known()));
    }

    // ---------- the drawn cat, and what the save holds now ----------
    // The page's choice for a part, else what the save has now.
    const wears = (key, part) => { const l = look(), cur = (now() || {})[key] || {}; return part in l[key] ? l[key][part] : cur[part]; };
    function drawCat() {
      const l = look(), slot = part => wears("slots", part);
      paintCat(svg, {
        coat: l.colours.fur || slotHex("fur", slot("fur")) || "#9A8F84",
        pattern: slotHex("pattern", slot("pattern")) || undefined, marking: slotHex("marking", slot("marking")) || undefined,
        eyeWhite: EYE_LIN ? rimOf(eyeRamp(EYE_LIN[0], eyeOf(0))) : undefined,
        rightEye: eyeStrip(slot("eye_right") ?? 0), leftEye: eyeStrip(slot("eye_left") ?? 0),
        nose: l.colours.nose, ears: l.colours.ears, whiskers: l.colours.whiskers,
        scars: { ear: wears("scars", "ear"), eye: wears("scars", "eye") },
      });
    }
    function renderNow() {
      const cur = now(), name = mine() ? "your cat" : whoName();
      const built = status && status.installed && status.installed.built;
      const when = built ? new Date(built).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : null;
      const line = (label, text) => el("li", {}, el("strong", { text: `${label}: ` }), text);
      const eye = slot => (eyeName(slot) ? `${eyeName(slot)} (${slot})` : String(slot));
      const scarText = Object.entries(cur ? cur.scars || {} : {}).filter(([, n]) => n > 0)
        .map(([part, n]) => `${SCAR_PARTS.find(s => s.id === part)?.name.toLowerCase() || part}: ${scarLabel(part, n).toLowerCase()}`);
      const shape = cur ? LOOK_PARTS.filter(p => p.id in (cur.look || {})).map(p => `${p.name.toLowerCase()} ${cur.look[p.id]}`) : [];
      put(nowCard, el("h2", { text: "In your save now" }),
        !saveRead() ? el("p", { class: "note", text: `Unknown: ${info.save_problem}.` })
          : !cur ? el("p", { class: "note", text: `${name[0].toUpperCase()}${name.slice(1)} isn't in the game you're playing, so the save has nothing for it.` })
          : el("ul", { class: "notes" },
            line("Colours", `coat ${cur.slots.fur}, pattern ${cur.slots.pattern}, markings ${cur.slots.marking}`),
            line("Eyes", `left ${eye(cur.slots.eye_left)}, right ${eye(cur.slots.eye_right)}`),
            line("Scars", scarText.length ? scarText.join("; ") : "none"),
            line("Shape", shape.join(", ") + (cur.look && cur.look.size != null ? `, size ${cur.look.size}` : ""))),
        el("p", { class: "note", text: `${when ? `Last applied ${when}. ` : ""}It's read again after every Apply. Switching the mod off doesn't undo the game's colours, the shape or the scars: they stay in your save. To put them back, choose the old ones here and apply again, or put back the copy of your save the studio made (Backups and repair, on the Settings and repair page).` }));
    }

    function renderLook() {
      const l = look(), cur = (now() || {}).look || {}, parts = (info.look || {}).parts || {};
      const rows = LOOK_PARTS.filter(p => p.id in parts).map(p => {
        const sel = el("select", { "aria-label": p.name },
          el("option", { value: "", text: `Keep what ${mine() ? "my cat" : "it"} has now${p.id in cur ? ` (${cur[p.id]})` : saveRead() ? "" : " (unknown now)"}` }),
          ...[...Array(parts[p.id] + 1).keys()].map(n => el("option", { value: String(n), text: String(n) })));
        sel.value = p.id in l.look ? String(l.look[p.id]) : "";
        sel.addEventListener("change", () => { if (sel.value === "") delete l.look[p.id]; else l.look[p.id] = Number(sel.value); changed(); });
        return el("div", { class: "row" }, el("strong", { text: p.name, style: { minWidth: "150px" } }), sel,
          el("span", { class: "muted", text: p.note || "" }));
      });
      const [lo, hi] = (info.look || {}).size || [0.05, 1.5];
      const on = "size" in l.look;
      const clampSize = v => Math.max(lo, Math.min(hi, Number(v) || 0.8));
      // A slider with the game's sizes marked (a kit, a warrior, a leader), and the number beside it.
      const marks = el("datalist", { id: "cat-size-marks" }, ...[[0.1, "kit"], [0.75, "warrior"], [1, "leader"]]
        .map(([v, label]) => el("option", { value: String(v), label })));
      const size = el("input", { type: "range", min: String(lo), max: String(hi), step: "0.05", list: "cat-size-marks",
        value: String(clampSize(l.look.size ?? cur.size)), "aria-label": "Size", disabled: !on, style: { width: "min(260px, 60vw)" } });
      const shown = el("output", { class: "mono", text: Number(size.value).toFixed(2) });
      const box = el("input", { type: "checkbox", checked: on, "aria-label": "Change the size" });
      size.addEventListener("input", () => { shown.textContent = Number(size.value).toFixed(2); });
      size.addEventListener("change", () => { const v = clampSize(size.value); l.look.size = v; size.value = v; changed(); });
      box.addEventListener("change", () => { if (box.checked) { l.look.size = clampSize(size.value); size.value = l.look.size; } else delete l.look.size; size.disabled = !box.checked; changed(); });
      put(lookCard, el("h2", { text: "Shape" }),
        el("p", { class: "note", text: `${mine() ? "Your cat's" : `${whoName()}'s`} body, fur, tail, ears, eyes, whiskers and face, each one of the game's 10 (the cat maker shows a clan's 7 of them), and its pattern and markings (21 each). They go into your save on Apply, after a backup.${mine() ? " Body, ears and face chose your cat's traits when it was made; the traits stay as they are." : ""}` }),
        ...rows,
        el("div", { class: "row" }, el("label", { class: "row", style: { minWidth: "150px" } }, box, el("strong", { text: "Size" })), size, shown, marks,
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
      const noLoader = status && status.game_dir && !status.ue4ss;
      put(coloursCard, el("h2", { text: "Colours of its own" }),
        el("p", { class: "note", text: `Tick a part to give ${whoName()} its own colour; unticked parts keep the game's. They show while you play, in menus and portraits, and go away if you turn the mod off. In the game, Insert opens the mod menu: its Colours page changes them while you play, and its Save keeps them in this mod.` }),
        noLoader ? el("p", { class: "note heads-up", text: "They need the script loader, which isn't installed yet: Get set up, on the Mods page, installs it." }) : null,
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
            title: `${s.name} ${i}${s.id.startsWith("eye") && eyeName(i) ? ` (${eyeName(i)})` : ""}${i >= base ? " (new)" : ""}${feral ? " (Feral Edition)" : ""}${cur === i ? ", now" : ""}`,
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
      const feral = info.feral_slots.includes(wears("slots", "fur"));
      put(slotsCard, el("h2", { text: "Colours from the game's picker" }),
        el("p", { class: "note", text: `Pick one of the game's colours for ${whoName()} to wear, by its number; click it again to keep the one in your save. Dashed ones are new colours your palettes add, which only the cats set to them wear.` }),
        feral ? el("p", { class: "note heads-up", text: `Coat ${wears("slots", "fur")} is one of the Feral Edition's (coats 20-24): a game without it gives this cat another coat.` }) : null,
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
          el("option", { value: "", text: `Keep what ${mine() ? "my cat" : "it"} has now (${isNow})` }),
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
      const keep = el("button", { class: "btn", type: "button", text: "Keep the scars it has now", "data-focus": "scars:keep",
        onclick: () => { l.scars = {}; l.raw.scars = {}; changed(); renderScars(); } });
      put(scarsCard, el("h2", { text: "Scars" }),
        el("p", { class: "note", text: `Choose ${whoName()}'s scars, or none. An eye scar shuts that eye; right and left are the cat's own. They go into your save on Apply, after a backup. A boss fight can still give new ones.` }),
        el("p", { class: "note heads-up" }, "Scars show only with the game's Injury system on: ",
          el("a", { href: "#save", text: "the Save page" }), " has the switch, under the game's settings."),
        ...rows, el("div", { class: "row" }, none, keep));
      const block = cantChange(rawOf("scars"));
      if (block) scarsCard.append(block);
    }

    // What your cat wears now is read again after an Apply or Play (it wrote the save), after another page saved a
    // mod (a palette's new colour), and on coming back to the window (the game may have changed the save): the
    // page's own choices stay, unsaved ones too. The file itself is read again after an Apply only while nothing
    // here is unsaved (installedEvent); coming back re-reads it when it changed (the bar does that).
    async function readCat() {
      try { [info, status] = await Promise.all([api.get("/cat"), api.get("/info").catch(() => status)]); } catch (e) { return; }
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
