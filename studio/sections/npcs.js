// Characters: cats of the mod's own (npcs.json), with their looks, where they stand and what they say. The
// Sandbox mode mod brings them into the forest with a sandbox cat; quests on the Questlines page use them.
// The file's rules are in lib/npcs-model.js; what the story pages share is in lib/story.js.
import { slug, listEditor, field, linesBox, wherePicker, sandboxStrip, catFace } from "../lib/story.js";
import * as model from "../lib/npcs-model.js";

const PARTS = [["fur", "Coat"], ["pattern", "Pattern"], ["markings", "Markings"], ["nose", "Nose"], ["paws", "Paw pads"],
  ["ears", "Inside the ears"], ["whiskers", "Whiskers"]];
const DEFAULTS = { fur: "#9a8a78", pattern: "#5b4e40", markings: "#e9e1d4", nose: "#c47c7a", paws: "#d9a0a8", ears: "#e4a9a2", whiskers: "#f4f0e8" };
const { LOOK_PARTS, SLOT_PARTS, EYES } = model;
const TALK = "Walk up to one in the game and use its Talk prompt (E by default, or A on a controller); Interact or Enter shows the next line.";

export default {
  title: "Characters",
  async mount(root, wc) {
    const { el, api, toast } = wc;
    let cats = [], extra = {}, quests = null;   // quests: the mod's quests.json, to say which quests name a cat
    let eyes = [], tables = {};
    // The look's options (how many of each part, the colour slots with your palettes) and the game's colour tables.
    let options = { palette: {}, game_slots: 25, feral_slots: [], parts: {} };
    const partMax = p => model.partMax(options, p);
    const slotHex = (part, n) => (options.palette[part] || {})[n] || (tables[SLOT_PARTS.find(s => s[0] === part)[2]] || [])[n] || null;
    const slotChoices = part => {
      const base = (tables[SLOT_PARTS.find(s => s[0] === part)[2]] || []).length || options.game_slots;
      // Pattern and marking slots past the game's are new ones a palette adds; coats can't have new ones.
      const added = part === "fur" ? [] : Object.keys(options.palette[part] || {}).map(Number).filter(n => n >= base).sort((a, b) => a - b);
      return { game: [...Array(base).keys()], added };
    };
    const addedSlots = () => Object.fromEntries(["pattern", "marking"].map(p => [p, slotChoices(p).added]));
    const showAdded = new Set();   // the colour slot rows showing the slots palettes add (the page's own, not saved)
    const roll = c => model.roll(c, options);

    const strip = sandboxStrip({ help: "characters",
      route: "To see them: Apply to game, Play, Sandbox Mode on the main menu, then a new cat or one of your sandbox cats. Walk up to one and use the game's Talk prompt." });
    const target = wc.modTarget({
      file: "npcs.json",
      onLoad: (obj, id) => { ({ cats, extra } = model.load(obj)); draw(); readQuests(id); },
      getValue: () => toJson(),
      onSaved: saved => wc.settleNew(cats, saved.npcs),   // saved cats keep their ids from now on
    });
    const out = wc.codePanel("npcs.json");
    const idLine = el("p", { class: "note" });
    const editor = listEditor({
      noun: "cat", empty: "No cats yet. Add a cat, give them a name and a look, and they'll turn up in Sandbox mode.",
      label: c => [el("strong", { text: c.name || "(no name)" }), c.title ? el("span", { class: "muted", text: ` ${c.title}` }) : null],
      add: () => {
        // A cat you'll know again: the same look every time, unless you choose otherwise.
        cats.push(model.newCat(cats.map(x => x.id), options, slug));
        editor.choose(cats.length - 1);
        changed();
        draw();
        const input = root.querySelector('[data-focus="cat:name"]');
        if (input) { input.focus(); input.select?.(); }
      },
    });
    editor.ready(false);   // until the file is read: a cat added before would be lost when it comes
    root.append(
      wc.pageHead({ eyebrow: "Sandbox mode", title: "Characters", help: "help:characters",
        lede: `Cats of your own, for your questlines and for company: a name, a look, where they stand and what they say. ${TALK}` }),
      target.element, strip.element, editor.element,
      el("details", { class: "fold", "data-key": "makers:npcs" },
        el("summary", {}, el("h3", { text: "For mod makers" }), el("span", { class: "muted", text: "the cat's id and the file this page writes" })),
        idLine, out.element));

    // What the page draws with: none of it needs the game, but the eye colours and slot colours are nicer with it.
    await Promise.all([
      api.get("/game/eyes").then(e => { eyes = e.rows.slice(1, 26).map(r => "#" + r[Math.floor(r.length * 0.45)]); }).catch(() => {}),
      api.get("/cat/options").then(o => { options = o; }).catch(() => {}),
      api.get("/game/tables").then(t => { tables = t.tables || {}; }).catch(() => {}),
    ]);
    // Add waits for the file; one that can't be read is said, and Add comes back all the same.
    try { await target.refresh(); }
    catch (e) { toast(`The mod's cats couldn't be read: ${e.message}`, "bad"); }
    finally { editor.ready(true); }
    await strip.refresh();

    // The mod's quests, for the remove-a-cat toast: read again when any mod changes (a save on Questlines).
    async function readQuests(id) {
      quests = null;
      const m = target.mods.find(x => x.id === id);
      if (!m || !m.kinds.includes("questlines")) return;
      try {
        const r = await api.get(`/mods/${encodeURIComponent(id)}/file/quests.json`);
        if (r.exists && target.current === id) quests = JSON.parse(r.text);
      } catch (e) { /* not JSON yet: the Questlines page says */ }
    }
    function toJson() { return model.toJson(cats, extra); }
    // Which of Sandbox mode's newer fields the cats use, for the strip.
    function usesFields() {
      const out = [];
      if (cats.some(c => model.isFixed(c))) out.push("look", "slots");
      if (cats.some(c => c.patrol !== undefined)) out.push("patrol");
      return out;
    }
    function changed() {
      target.markDirty();
      out.set(toJson());
      strip.update(usesFields());
      sayId();
    }
    function sayId() {
      const c = cats[editor.chosen];
      idLine.textContent = c ? `${c.name || "This cat"} has the id ${c.id}: quests.json names them by it.` : "No cat chosen.";
    }
    function draw() {
      out.set(toJson());
      editor.render(cats, drawCat);
      sayId();
      strip.update(usesFields());   // another mod's cats (the Editing mod changed) may need another Sandbox mode
    }

    function drawCat(box, c, i) {
      // ---- what isn't right yet, at the top
      const notReady = el("div", { class: "banner", role: "status" });
      const showProblems = () => {
        const p = model.problems(c, { gameSlots: options.game_slots, addedSlots: addedSlots() });
        notReady.hidden = !p.length;
        notReady.replaceChildren(el("strong", { text: "Not ready yet" }), el("ul", { class: "notes" }, ...p.map(t => el("li", { text: t }))));
      };
      const edited = () => { changed(); showProblems(); };

      // ---- who they are
      const face = el("div", { class: "face-box" });
      // Its own colours, over its colour slots' (a fixed look's), over the drawing's.
      const slotted = () => Object.fromEntries(SLOT_PARTS.filter(([p]) => c.slots && c.slots[p] !== undefined && slotHex(p, c.slots[p]))
        .map(([p, , , drawn]) => [drawn, slotHex(p, c.slots[p])]));
      const paint = () => { face.replaceChildren(catFace({ ...DEFAULTS, ...slotted(), ...c.colours }, c.eyes == null ? null : eyes[c.eyes] || "#b6c86a")); };
      paint();
      // Typing a name or title changes only its button in the list: nothing is drawn again, so Tab and clicks land.
      const name = el("input", { type: "text", value: c.name || "", maxlength: String(model.MAX_NAME), "data-focus": "cat:name", oninput: () => {
        c.name = name.value;
        // A new cat's id follows its name until it's saved; after that, quests may name it.
        if (c._new) c.id = slug(c.name, cats.filter(x => x !== c).map(x => x.id), "cat");
        editor.relabel(i);
        edited();
      } });
      const title = el("input", { type: "text", value: c.title || "", maxlength: String(model.MAX_NAME), "data-focus": "cat:title",
        placeholder: "Elder, Loner, Medicine cat…", oninput: () => { c.title = title.value; editor.relabel(i); edited(); } });

      // ---- how they look
      const colours = el("div", { class: "colour-grid" }, ...PARTS.map(([part, label]) => {
        const has = part in c.colours;
        const pick = el("input", { type: "color", value: c.colours[part] || DEFAULTS[part], "aria-label": label, disabled: !has,
          oninput: () => { c.colours[part] = pick.value; paint(); changed(); } });
        const own = el("input", { type: "checkbox", checked: has, "aria-label": `Choose the ${label.toLowerCase()} colour`, onchange: () => {
          if (own.checked) c.colours[part] = pick.value; else delete c.colours[part];
          pick.disabled = !own.checked;
          paint(); changed();
        } });
        return el("label", { class: "row colour" }, own, pick, el("span", { text: label }));
      }));
      const coloursNote = el("p", { class: "note" });
      const eyeChoices = [null, ...Array.from({ length: EYES }, (_, n) => n)];
      const eyeRow = el("div", { class: "swatches", role: "radiogroup", "aria-label": "Eye colour" },
        ...eyeChoices.map(n => el("button", { class: "swatch", type: "button", role: "radio",
          "aria-checked": String((c.eyes ?? null) === n), "aria-label": n === null ? "Game's choice" : `Eye colour ${n}`,
          title: n === null ? "Game's choice: made up each time they appear" : `Eye colour ${n}`,
          style: { background: n === null ? "var(--stage-2)" : eyes[n] || "var(--stage-2)" }, text: n === null ? "?" : eyes[n] ? "" : String(n),
          onclick: () => {
            if (n === null) delete c.eyes; else c.eyes = n;
            for (const [k, b] of [...eyeRow.querySelectorAll("button")].entries()) b.setAttribute("aria-checked", String(eyeChoices[k] === (c.eyes ?? null)));
            paint(); changed();
          } })));

      // A look chosen here and kept, or made up by the game each time they appear. The fine-tuning (the shape's
      // parts and the colour slots) shows with a look that's kept; emptied out, the look is the game's again.
      const fineTune = el("div", { class: "stack" });
      const drawLook = () => {
        sameRadio.checked = model.isFixed(c);
        newRadio.checked = !model.isFixed(c);
        coloursNote.textContent = model.isFixed(c)
          ? "Tick a part to choose its own colour, over the one its colour number (under Fine-tune) gives it."
          : "Tick a part to choose its colour; the rest are made up with the look, each time they appear.";
        const parts = LOOK_PARTS.map(([p, label]) => {
          const sel = el("select", { "aria-label": label, onchange: () => {
            c.look = c.look || {};
            if (sel.value === "") delete c.look[p]; else c.look[p] = Number(sel.value);
            paint(); edited(); drawLook();
          } },
            el("option", { value: "", text: "Random each time" }),
            ...[...Array(partMax(p) + 1).keys()].map(n => el("option", { value: String(n), text: String(n) })));
          sel.value = c.look && c.look[p] !== undefined ? String(c.look[p]) : "";
          return el("label", { class: "row", style: { flexWrap: "nowrap" } }, el("span", { class: "lbl", style: { minWidth: "84px" }, text: label }), sel);
        });
        const slotRows = SLOT_PARTS.map(([p, label]) => {
          const chosen = c.slots ? c.slots[p] : undefined;
          // The game's slots, and the ones palettes add once asked for (or when the cat wears one).
          const { game, added } = slotChoices(p);
          const forced = added.includes(chosen), open = forced || showAdded.has(p);
          return el("div", { class: "stack", style: { gap: "4px" } },
            el("span", { class: "lbl", text: `${label}${chosen === undefined ? ": random each time" : `: ${chosen}`}` }),
            el("div", { class: "swatches", role: "radiogroup", "aria-label": label },
              ...(open ? [...game, ...added] : game).map(n => {
                const hex = slotHex(p, n);
                const feral = p === "fur" && options.feral_slots.includes(n);
                const what = `${label} ${n}${feral ? " (Feral Edition)" : ""}${n >= options.game_slots ? " (a palette's)" : ""}`;
                return el("button", { class: "swatch", type: "button", role: "radio", "aria-checked": String(chosen === n),
                  "aria-label": what, title: what, style: { background: hex || "var(--stage-2)" }, text: hex ? "" : String(n),
                  // Picked again, it goes back to random each time.
                  onclick: () => {
                    c.slots = c.slots || {};
                    if (c.slots[p] === n) delete c.slots[p]; else c.slots[p] = n;
                    paint(); edited(); drawLook();
                  } });
              })),
            added.length && !forced ? el("div", { class: "row" }, el("button", { class: "btn ghost small", type: "button",
              "data-focus": `more:${p}`, "aria-expanded": String(open), text: open ? "Only the game's colours" : `${added.length} more from your palettes`,
              onclick: () => { if (open) showAdded.delete(p); else showAdded.add(p); drawLook(); } })) : null);
        });
        fineTune.replaceChildren(
          el("p", { class: "note", text: "The drawing shows the colours only: the shape and the pattern show only in the game. " +
            "The game picks its walking cats' tail and ears itself, so those two can still differ from Tail and Ears here." }),
          el("div", { class: "colour-grid" }, ...parts),
          ...slotRows,
          el("div", { class: "row" },
            el("button", { class: "btn small", type: "button", text: "Roll a new look", onclick: () => { roll(c); paint(); edited(); drawLook(); } }),
            el("span", { class: "muted", style: { fontSize: "0.85rem" }, text: "Every part and colour number again, at random. Your ticked colours and eye colour stay." })));
      };
      const fold = el("details", { class: "fold", "data-key": "fine-tune" },
        el("summary", {}, el("strong", { text: "Fine-tune" }), el("span", { class: "muted", text: "the shape's parts and the colour numbers" })),
        fineTune);
      const lookRadio = (fixed, label, hint) => {
        const r = el("input", { type: "radio", name: `look-${i}`, "data-focus": `look:${fixed ? "same" : "new"}`, onchange: () => {
          if (fixed) model.keepEyes(roll(c));   // its eyes stay the same colour too
          else { delete c.look; delete c.slots; }
          fold.hidden = !fixed;
          paint(); edited(); drawLook();
        } });
        return [r, el("label", { class: "row", style: { flexWrap: "nowrap", alignItems: "start" } }, r,
          el("span", {}, el("strong", { text: label }), el("span", { class: "muted", text: ` ${hint}` })))];
      };
      const [sameRadio, sameRow] = lookRadio(true, "Same look every time", "their shape, pattern and colours are chosen now and kept; the game makes up anything you leave out.");
      const [newRadio, newRow] = lookRadio(false, "New look each time", "a different cat every time the game puts them in the forest, as it does with its own cats.");
      fold.hidden = !model.isFixed(c);
      drawLook();

      const size = el("input", { type: "range", min: "0.4", max: "1.2", step: "0.05", value: c.size ?? model.DEFAULT_SIZE, "aria-label": "Size",
        "aria-valuetext": model.sizeText(c.size),
        oninput: () => { c.size = Number(size.value); sizeOut.textContent = model.sizeText(c.size); size.setAttribute("aria-valuetext", sizeOut.textContent); changed(); } });
      const sizeOut = el("span", { class: "muted", text: model.sizeText(c.size) });

      // ---- where they stand
      const placeBox = el("div", { class: "stack" });
      const drawPlace = () => {
        placeBox.replaceChildren(...(c.at || c._placing ? [wherePicker({ at: c.at, level: c.level }, spot => {
          c.at = spot.at || null;
          if (spot.yaw !== undefined) c.yaw = (spot.yaw + 180) % 360;   // facing back towards where you stood
          if (spot.level) c.level = spot.level;
          if (!c.at) { delete c.yaw; delete c.level; }
          edited();
        })] : []));
      };
      const placeRadio = (spot, label, hint) => el("label", { class: "row", style: { flexWrap: "nowrap", alignItems: "start" } },
        el("input", { type: "radio", name: `place-${i}`, "data-focus": `place:${spot ? "spot" : "beside"}`, checked: spot === !!(c._placing || c.at), onchange: () => {
          if (spot) { c._placing = true; } else { delete c.at; delete c.yaw; delete c.level; delete c._placing; }
          drawPlace(); edited();
        } }),
        el("span", {}, el("strong", { text: label }), el("span", { class: "muted", text: ` ${hint}` })));
      drawPlace();

      // ---- what they say
      const lines = linesBox(c.lines, v => { c.lines = v; edited(); },
        "What they say when you talk to them (and they've no quest for you), one line each:\nGood hunting, young one.\nHave you seen the river today? It's running high.");

      showProblems();
      box.append(
        notReady,
        el("div", { class: "card" },
          el("h3", { text: "Who they are" }),
          el("div", { class: "cat-head" }, face,
            el("div", { class: "stack", style: { flex: "1", minWidth: "220px" } },
              field("Name", name), field("Title", title, "Shown above their name, smaller. Leave it empty for none.")))),
        el("div", { class: "card" },
          el("h3", { text: "How they look" }),
          sameRow, newRow, fold,
          el("h4", { text: "Colours" }), coloursNote, colours,
          el("h4", { text: "Eyes" }), eyeRow,
          el("div", { class: "row" }, el("span", { class: "lbl", text: "Size" }), size, sizeOut)),
        el("div", { class: "card" },
          el("h3", { text: "Where they stand" }),
          placeRadio(false, "Beside your cat", "the first time a sandbox cat comes into the forest, and there after that, turned to face your cat."),
          placeRadio(true, "At one spot", "the same place for every sandbox cat."),
          placeBox),
        el("div", { class: "card" }, el("h3", { text: "What they say" }), lines,
          el("p", { class: "note", text: `On a questline, the quest's own lines come first: these are for the rest of the time. ${TALK}` })),
        el("div", { class: "row" },
          el("button", { class: "btn", type: "button", text: "Make a copy", onclick: () => {
            const copy = JSON.parse(JSON.stringify(c));
            copy.name = `${c.name} 2`;
            copy.id = slug(copy.name, cats.map(x => x.id), "cat");
            copy._new = true;
            cats.splice(i + 1, 0, copy);
            editor.choose(i + 1);
            changed();
            draw();
          } }),
          wc.confirmButton(`Remove ${c.name || "this cat"}`, "Press again to remove", () => {
            cats.splice(i, 1);
            changed();
            draw();
            const naming = model.questsNaming(quests, c.id);
            toast(naming.length
              ? `Removed ${c.name}. ${naming.join(", ")} ${naming.length > 1 ? "name" : "names"} them: choose another cat there before Apply.`
              : `Removed ${c.name}.`);
          }, "btn danger")));
    }

    // After an Apply the file is read again (unless there are unsaved changes), and the strip asked again;
    // a mod switched or saved anywhere (Sandbox mode turned on on the Mods page, a quest saved) shows here.
    const offInstalled = wc.installedEvent(target, () => { target.refresh(); });
    const offChanged = wc.bus.on("mods-changed", () => { strip.refresh(); readQuests(target.current); });
    const offApplied = wc.bus.on("installed", () => { strip.refresh(); });
    return { unmount() { offInstalled(); offChanged(); offApplied(); } };
  },
};
