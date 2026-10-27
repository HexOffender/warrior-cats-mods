// Characters: cats of the mod's own (npcs.json), with their looks, where they stand and what they say. The
// Sandbox mode mod brings them into the forest with a sandbox cat; quests on the Questlines page use them.
import { slug, listEditor, field, linesBox, wherePicker, sandboxNote, catFace } from "../lib/story.js";

const PARTS = [["fur", "Coat"], ["pattern", "Pattern"], ["markings", "Markings"], ["nose", "Nose"], ["paws", "Paw pads"],
  ["ears", "Inside the ears"], ["whiskers", "Whiskers"]];
const DEFAULTS = { fur: "#9a8a78", pattern: "#5b4e40", markings: "#e9e1d4", nose: "#c47c7a", paws: "#d9a0a8", ears: "#e4a9a2", whiskers: "#f4f0e8" };

export default {
  title: "Characters",
  async mount(root, wc) {
    const { el, api, toast } = wc;
    let cats = [], extra = {};
    let eyes = [];
    try {
      const e = await api.get("/game/eyes");
      // Eye slot n is the atlas's row n + 1; its middle is the colour the iris mostly shows.
      eyes = e.rows.slice(1, 26).map(r => "#" + r[Math.floor(r.length * 0.45)]);
    } catch (e) { /* no game yet: the slots show as numbers */ }

    const target = wc.modTarget({
      file: "npcs.json",
      onLoad: obj => { load(obj); draw(); },
      getValue: () => toJson(),
    });
    const out = wc.codePanel("npcs.json");
    const editor = listEditor({
      noun: "cat", empty: "No cats yet. Add a cat, give them a name and colours, and they'll turn up in Sandbox mode.",
      label: c => [el("strong", { text: c.name || "(no name)" }), c.title ? el("span", { class: "muted", text: ` ${c.title}` }) : null],
      add: () => {
        const name = "New cat";
        cats.push({ id: slug(name, cats.map(c => c.id), "cat"), name, colours: {}, lines: [], _new: true });
        editor.choose(cats.length - 1);
        changed(true);
      },
    });
    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Sandbox mode" }),
        el("h1", { text: "Characters" }),
        el("p", { class: "note", text: "Cats of your own, for your questlines and for company. Give them a name, colours and lines to say. Each one turns up beside a sandbox cat the first time it comes into the forest (and stays there for that cat), or always at a spot you choose. Talk to them with G, or the d-pad's up." })),
      target.element);
    const note = await sandboxNote();
    if (note) target.element.after(note);
    root.append(editor.element, out.element);
    await target.refresh();

    function load(obj) {
      extra = {};
      cats = [];
      for (const [k, v] of Object.entries(obj || {})) if (k !== "npcs" && !k.startsWith("_")) extra[k] = v;
      for (const c of (obj && Array.isArray(obj.npcs) ? obj.npcs : [])) if (c && typeof c === "object") cats.push({ colours: {}, lines: [], ...c });
    }
    function toJson() {
      const npcs = cats.map(c => {
        const o = { id: c.id, name: (c.name || "").trim() || c.id };
        if (c.title && c.title.trim()) o.title = c.title.trim();
        if (Object.keys(c.colours || {}).length) o.colours = c.colours;
        for (const k of ["eyes", "size"]) if (c[k] !== undefined && c[k] !== null) o[k] = c[k];
        if (c.at) { o.at = c.at; if (c.yaw !== undefined) o.yaw = c.yaw; if (c.level) o.level = c.level; }
        o.lines = c.lines || [];
        for (const [k, v] of Object.entries(c)) if (!(k in o) && k.startsWith("_") && !["_new", "_placing"].includes(k)) o[k] = v;   // notes kept; the page's own marks not
        return o;
      });
      return { _help: "Written by Clan Mod Studio (Characters). Cats of this mod's own, which the Sandbox mode mod brings into the game. See docs/formats.md, npcs.json.", ...extra, npcs };
    }
    function changed(redraw = false) {
      target.markDirty();
      out.set(toJson());
      if (redraw) draw();
    }
    function draw() {
      out.set(toJson());
      editor.render(cats, drawCat);
    }

    function drawCat(box, c, i) {
      const face = el("div", { class: "face-box" });
      const paint = () => { face.replaceChildren(catFace({ ...DEFAULTS, ...c.colours }, eyes[c.eyes ?? 6] || "#b6c86a")); };
      paint();
      const name = el("input", { type: "text", value: c.name || "", maxlength: "40", oninput: () => {
        c.name = name.value;
        // A new cat's id follows its name until it's saved; after that, quests may name it.
        if (c._new) c.id = slug(c.name, cats.filter(x => x !== c).map(x => x.id), "cat");
        idNote.textContent = `id: ${c.id}`;
        changed();
      }, onchange: () => draw() });
      const title = el("input", { type: "text", value: c.title || "", maxlength: "40", placeholder: "Elder, Loner, Medicine cat…",
        oninput: () => { c.title = title.value; changed(); }, onchange: () => draw() });
      const idNote = el("span", { class: "muted mono", text: `id: ${c.id}` });

      const colours = el("div", { class: "colour-grid" }, ...PARTS.map(([part, label]) => {
        const has = part in (c.colours || {});
        const pick = el("input", { type: "color", value: c.colours[part] || DEFAULTS[part], "aria-label": label, disabled: !has,
          oninput: () => { c.colours[part] = pick.value; paint(); changed(); } });
        const own = el("input", { type: "checkbox", checked: has, "aria-label": `Choose the ${label.toLowerCase()} colour`, onchange: () => {
          if (own.checked) c.colours[part] = pick.value; else delete c.colours[part];
          pick.disabled = !own.checked;
          paint(); changed();
        } });
        return el("label", { class: "row colour" }, own, pick, el("span", { text: label }));
      }));

      const eyeRow = el("div", { class: "swatches", role: "radiogroup", "aria-label": "Eye colour" },
        ...Array.from({ length: 25 }, (_, n) => el("button", { class: "swatch", type: "button", role: "radio",
          "aria-checked": String((c.eyes ?? null) === n), "aria-label": `Eye colour ${n}`, title: `Eye colour ${n}`,
          style: { background: eyes[n] || "var(--stage-2)" }, text: eyes[n] ? "" : String(n),
          onclick: () => { c.eyes = n; paint(); changed(); drawCat(clearBox(box), c, i); } })));

      const size = el("input", { type: "range", min: "0.4", max: "1.2", step: "0.05", value: c.size ?? 0.85, "aria-label": "Size",
        oninput: () => { c.size = Number(size.value); sizeOut.textContent = sizeText(c.size); changed(); } });
      const sizeOut = el("span", { class: "muted", text: sizeText(c.size) });

      const fixed = !!c.at;
      const placeBox = el("div", { class: "stack" });
      const drawPlace = () => {
        placeBox.replaceChildren(...(c.at || c._placing ? [wherePicker({ at: c.at, level: c.level }, spot => {
          c.at = spot.at || null;
          if (spot.yaw !== undefined) c.yaw = (spot.yaw + 180) % 360;   // facing back towards where you stood
          if (spot.level) c.level = spot.level;
          if (!c.at) { delete c.yaw; delete c.level; }
          changed();
        })] : []));
      };
      const radio = (value, label, hint) => el("label", { class: "row", style: { flexWrap: "nowrap", alignItems: "start" } },
        el("input", { type: "radio", name: `place-${i}`, checked: value === fixed, onchange: () => {
          if (value) { c._placing = true; } else { delete c.at; delete c.yaw; delete c.level; delete c._placing; }
          drawPlace(); changed();
        } }),
        el("span", {}, el("strong", { text: label }), el("span", { class: "muted", text: ` ${hint}` })));
      drawPlace();

      const lines = linesBox(c.lines || [], v => { c.lines = v; changed(); },
        "What they say when you talk to them (and they've no quest for you), one line each:\nGood hunting, young one.\nHave you seen the river today? It's running high.");

      box.append(
        el("div", { class: "card" },
          el("div", { class: "cat-head" }, face,
            el("div", { class: "stack", style: { flex: "1", minWidth: "220px" } },
              field("Name", name), field("Title", title, "Shown above their name, smaller. Leave it empty for none."), idNote)),
          el("h3", { text: "Colours" }),
          el("p", { class: "note", text: "Tick a part to choose its colour; the rest stay as the game makes them. The game picks a pattern shape itself, so the drawing only shows the colours." }),
          colours,
          el("h3", { text: "Eyes" }), eyeRow,
          el("div", { class: "row" }, el("span", { class: "lbl", text: "Size" }), size, sizeOut)),
        el("div", { class: "card" },
          el("h3", { text: "Where they are" }),
          radio(false, "Beside your cat", "the first time a sandbox cat comes into the forest, and there after that"),
          radio(true, "At one spot", "the same place for every cat"),
          placeBox),
        el("div", { class: "card" }, el("h3", { text: "What they say" }), lines,
          el("p", { class: "note", text: "On a questline, the quest's own lines come first: these are for the rest of the time." })),
        el("div", { class: "row" },
          el("button", { class: "btn", text: "Make a copy", onclick: () => {
            const copy = JSON.parse(JSON.stringify(c));
            copy.name = `${c.name} 2`;
            copy.id = slug(copy.name, cats.map(x => x.id), "cat");
            copy._new = true;
            cats.splice(i + 1, 0, copy);
            editor.choose(i + 1);
            changed(true);
          } }),
          wc.confirmButton(`Remove ${c.name || "this cat"}`, "Press again to remove", () => {
            cats.splice(i, 1);
            changed(true);
            toast(`Removed ${c.name}. A quest that names them needs another cat before it saves.`);
          }, "btn danger")));
    }
    const clearBox = b => { b.textContent = ""; return b; };
    const sizeText = v => `${Math.round((v ?? 0.85) * 100)}%${(v ?? 0.85) < 0.6 ? " (kit-sized)" : (v ?? 0.85) > 1.05 ? " (big)" : ""}`;
    return {};
  },
};
