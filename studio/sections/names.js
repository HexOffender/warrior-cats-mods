// Names page: rename, add and remove the game's name parts and rogue names, edit the ban list and any name
// the game shows (cameo cats too), and rename cats in your save. Writes names.json (see wcmods/names.py).
const EMPTY = () => ({
  prefixes: { rename: {}, add: {}, remove: [] }, suffixes: { rename: {}, add: {}, remove: [] },
  rogues: { rename: {}, add: [], remove: [] }, banned: { add: [], remove: [] }, names: {}, cats: {},
});
// Kits, apprentices and leaders have one suffix each; the build keeps them even if asked to remove them.
const KEEP = ["kit", "paw", "star"];
const CLAN_LABEL = { ThunderClan: "Thunder", RiverClan: "River", ShadowClan: "Shadow", WindClan: "Wind", OutOfClans: "outside clans" };

export default {
  title: "Names",
  async mount(root, wc) {
    const { el, api, clear, toast } = wc;
    let spec = EMPTY(), extra = {}, game = null, view = null, timer = null, seq = 0;
    const afterCells = new Map();   // cat target -> cell showing the name it will have

    const target = wc.modTarget({
      file: "names.json", defaultId: "my-names", defaultName: "My Names",
      onLoad: obj => { load(obj); render(); preview(); },
      getValue: () => toJson(),
    });
    const box = { prefixes: card(), suffixes: card(), rogues: card(), names: card(), banned: card(), cats: card() };
    const notes = el("div", { class: "card" });
    const out = wc.codePanel("names.json");

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Cat names" }),
        el("h1", { text: "Names" }),
        el("p", { class: "note", text: "A clan cat's name is a prefix and a suffix (Otter + paw). Rename, add or remove either part, edit rogue names and the ban list, rename any name the game shows, or rename the cats in your save. Save to a mod, then Apply to game." })),
      el("div", { class: "banner info" }, el("strong", { text: "What changes where" }),
        el("span", { text: "Renames change the English text. Added names show in every language, with their English text. Removing a name only stops the game handing it out: cats that already have it keep it. Cat renames go into your save on install, after a backup." })),
      target.element, notes, box.cats, box.prefixes, box.suffixes, box.rogues, box.names, box.banned, out.element);

    try { game = await api.get("/names"); view = game; }
    catch (e) { root.prepend(el("div", { class: "error-card" }, el("strong", { text: "Couldn't read the game's names" }), el("span", { text: e.message }))); return {}; }
    await target.refresh();

    // ---------- model ----------
    function load(obj) {
      spec = EMPTY(); extra = {};
      obj = obj && typeof obj === "object" ? obj : {};
      for (const [k, v] of Object.entries(obj)) {
        if (k.startsWith("_")) continue;
        if (!(k in spec)) { extra[k] = v; continue; }   // e.g. "text": kept as it is
        for (const [op, val] of Object.entries(v || {})) {
          if (k === "names" || k === "cats") spec[k][op] = val;
          else if (op in spec[k]) spec[k][op] = Array.isArray(spec[k][op]) ? [...val] : { ...val };
          else (extra[k] ||= {})[op] = val;   // weights, banned.clear: not edited here, kept
        }
      }
    }
    function toJson() {
      const o = { _help: "Written by Clan Mod Studio. See README, \"names.json\"." };
      for (const [k, v] of Object.entries(spec)) {
        const part = {};
        if (k === "names" || k === "cats") Object.assign(part, v);
        else for (const [op, val] of Object.entries(v)) if (Array.isArray(val) ? val.length : Object.keys(val).length) part[op] = val;
        Object.assign(part, extra[k] || {});
        if (Object.keys(part).length) o[k] = part;
      }
      for (const [k, v] of Object.entries(extra)) if (!(k in spec)) o[k] = v;
      return o;
    }
    function changed() {
      target.markDirty();
      out.set(toJson());
      clearTimeout(timer);
      timer = setTimeout(preview, 350);
    }
    async function preview() {
      out.set(toJson());
      const mine = ++seq;
      try {
        const v = await api.post("/names/preview", { spec: toJson() });
        if (mine !== seq) return;
        view = v;
        renderNotes();
        for (const c of view.cats) { const cell = afterCells.get(catKey(c)); if (cell) cell.textContent = c.with_mods === c.name ? "" : c.with_mods; }
      } catch (e) { if (mine === seq) { clear(notes).append(el("p", { class: "note", text: e.message })); } }
    }
    const toggle = (list, item, on) => { const i = list.indexOf(item); if (on && i < 0) list.push(item); if (!on && i >= 0) list.splice(i, 1); };
    const setRename = (map, from, to) => { to = to.trim(); if (!to || to === from) delete map[from]; else map[from] = to; };

    // ---------- rendering ----------
    function card() { return el("div", { class: "card" }); }
    function render() {
      afterCells.clear();
      renderAffixes("prefixes", "Prefixes", "The first part of a clan cat's name. Renaming changes every name with it (Otterpaw, Otterheart...).", game.prefixes, p => clans(p.weights));
      renderAffixes("suffixes", "Suffixes", "The second part, which changes with rank: kits are -kit, apprentices -paw, leaders -star. Those three can be renamed but not removed.", game.suffixes, s => ranks(s.weights));
      renderRogues(); renderNames(); renderBanned(); renderCats(); renderNotes();
      out.set(toJson());
    }
    function clans(w) { return Object.entries(w).filter(([, v]) => v > 0).map(([k]) => CLAN_LABEL[k] || k).join(", ") || "not given out"; }
    function ranks(w) { return Object.entries(w).filter(([, v]) => v > 0).map(([k]) => k.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase()).join(", ") || "not given out"; }

    function renderAffixes(kind, title, note, items, usedBy) {
      const s = spec[kind];
      const filter = el("input", { type: "search", placeholder: `Find a ${kind.slice(0, -2)}`, "aria-label": `Find a ${kind.slice(0, -2)}` });
      const body = el("tbody");
      const seen = new Set();
      const rows = items.filter(x => !seen.has(x.text) && seen.add(x.text)).map(x => {
        const locked = kind === "suffixes" && KEEP.includes(x.text);
        const rename = el("input", { type: "text", value: s.rename[x.text] || "", placeholder: x.text, "aria-label": `New text for ${x.text}`, spellcheck: "false",
          onchange: e => { setRename(s.rename, x.text, e.target.value); changed(); } });
        const tr = el("tr", { "data-name": x.text.toLowerCase(), class: s.remove.includes(x.text) ? "muted" : "" },
          el("td", {}, el("strong", { text: x.text }), el("div", { class: "muted mono", style: { fontSize: "0.72rem" }, text: x.id })),
          el("td", {}, rename),
          el("td", { class: "muted", text: usedBy(x) }),
          el("td", {}, locked ? el("span", { class: "muted", text: "needed" }) : el("label", { class: "row", style: { flexWrap: "nowrap", whiteSpace: "nowrap" } },
            el("input", { type: "checkbox", checked: s.remove.includes(x.text), onchange: e => {
              toggle(s.remove, x.text, e.target.checked); tr.className = e.target.checked ? "muted" : ""; changed(); } }), el("span", { text: "Remove" }))));
        return tr;
      });
      for (const [name, opts] of Object.entries(s.add)) {
        body.append(el("tr", {},
          el("td", {}, el("strong", { text: name }), el("span", { class: "chip good", style: { marginLeft: "6px" }, text: "new" })),
          el("td", { class: "muted", text: opts && opts.like ? `like ${opts.like}` : "default weights" }),
          el("td", { class: "muted", text: kind === "prefixes" ? "every clan, average" : "most ranks, average" }),
          el("td", {}, el("button", { class: "btn ghost small", text: "Remove", onclick: () => { delete s.add[name]; changed(); render(); } }))));
      }
      body.append(...rows);
      filter.addEventListener("input", () => {
        const q = filter.value.trim().toLowerCase();
        for (const tr of rows) tr.hidden = !!q && !tr.dataset.name.includes(q);
      });
      const addName = el("input", { type: "text", placeholder: kind === "prefixes" ? "Sparrow" : "whisper", "aria-label": `New ${kind.slice(0, -2)}`, spellcheck: "false" });
      const like = el("select", { "aria-label": "Copy how often it's used from" },
        el("option", { value: "", text: "used like an average one" }),
        ...[...new Set(items.map(x => x.text))].map(t => el("option", { value: t, text: `used like ${t}` })));
      const add = () => {
        const name = addName.value.trim();
        if (!name) return;
        if (items.some(x => x.text.toLowerCase() === name.toLowerCase()) || name in s.add) { toast(`${name} is already a ${kind.slice(0, -2)}`, "bad"); return; }
        s.add[name] = like.value ? { like: like.value } : {};
        changed(); render();
      };
      clear(box[kind]).append(el("div", { class: "row spread" }, el("h2", { text: title }), filter),
        el("p", { class: "note", text: note }),
        el("div", { class: "row" }, el("span", { class: "lbl", text: "Add" }), addName, like,
          el("button", { class: "btn small", text: `Add ${kind.slice(0, -2)}`, onclick: add })),
        el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, el("th", { text: kind === "prefixes" ? "Prefix" : "Suffix" }), el("th", { text: "Rename to" }),
            el("th", { text: kind === "prefixes" ? "Given out in" : "Given to" }), el("th", { text: "" }))), body)));
    }

    function renderRogues() {
      const s = spec.rogues;
      const rows = game.rogues.map(r => {
        const tr = el("tr", { class: s.remove.includes(r.text) ? "muted" : "" },
          el("td", {}, el("strong", { text: r.text })),
          el("td", {}, el("input", { type: "text", value: s.rename[r.text] || "", placeholder: r.text, "aria-label": `New name for ${r.text}`, spellcheck: "false",
            onchange: e => { setRename(s.rename, r.text, e.target.value); changed(); } })),
          el("td", {}, el("label", { class: "row", style: { flexWrap: "nowrap", whiteSpace: "nowrap" } }, el("input", { type: "checkbox", checked: s.remove.includes(r.text),
            onchange: e => { toggle(s.remove, r.text, e.target.checked); tr.className = e.target.checked ? "muted" : ""; changed(); } }), el("span", { text: "Remove" }))));
        return tr;
      });
      const added = s.add.map(n => el("span", { class: "chip good" }, el("span", { text: n }),
        el("button", { class: "btn ghost small", text: "×", "aria-label": `Remove ${n}`, onclick: () => { toggle(s.add, n, false); changed(); render(); } })));
      const name = el("input", { type: "text", placeholder: "Moss", "aria-label": "New rogue name", spellcheck: "false" });
      clear(box.rogues).append(el("h2", { text: "Rogue and loner names" }),
        el("p", { class: "note", text: "Cats outside the clans get one whole name from this list." }),
        el("div", { class: "row" }, el("span", { class: "lbl", text: "Add" }), name,
          el("button", { class: "btn small", text: "Add name", onclick: () => {
            const n = name.value.trim();
            if (!n) return;
            if (game.rogues.some(r => r.text.toLowerCase() === n.toLowerCase()) || s.add.includes(n)) { toast(`${n} is already a rogue name`, "bad"); return; }
            s.add.push(n); changed(); render();
          } }), ...added),
        el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, el("th", { text: "Name" }), el("th", { text: "Rename to" }), el("th", { text: "" }))),
          el("tbody", {}, ...rows))));
    }

    function renderNames() {
      const map = spec.names;
      const iconic = Object.values(game.iconic);
      const free = Object.keys(map).filter(k => !iconic.includes(k));
      const row = name => el("tr", {},
        el("td", {}, el("strong", { text: name })),
        el("td", {}, el("input", { type: "text", value: map[name] || "", placeholder: name, "aria-label": `New text for ${name}`, spellcheck: "false",
          onchange: e => { setRename(map, name, e.target.value); changed(); } })));
      const from = el("input", { type: "text", placeholder: "Name as the game shows it", "aria-label": "Name as the game shows it", spellcheck: "false" });
      const to = el("input", { type: "text", placeholder: "New text", "aria-label": "New text", spellcheck: "false" });
      clear(box.names).append(el("h2", { text: "Cameo cats and any other name" }),
        el("p", { class: "note", text: "Changes every text that's exactly this name. Some cameo names are also clan names (Brightheart is Bright + heart), so both change." }),
        el("div", { class: "row" }, el("span", { class: "lbl", text: "Any name" }), from, el("span", { class: "muted", text: "becomes" }), to,
          el("button", { class: "btn small", text: "Add", onclick: () => {
            const f = from.value.trim(), t = to.value.trim();
            if (!f || !t) return;
            map[f] = t; changed(); render();
          } })),
        el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, el("th", { text: "Name" }), el("th", { text: "Becomes" }))),
          el("tbody", {}, ...iconic.map(row), ...free.map(row)))));
    }

    function renderBanned() {
      const s = spec.banned;
      const chips = game.banned.map(b => {
        const off = s.remove.includes(b.name);
        return el("button", { class: "chip", "aria-pressed": String(!off), title: off ? "Allowed again; click to ban it" : "Banned; click to allow it",
          style: off ? { textDecoration: "line-through", opacity: "0.6" } : {}, text: b.name,
          onclick: () => { toggle(s.remove, b.name, !off); changed(); render(); } });
      });
      const added = s.add.map(n => el("span", { class: "chip warn" }, el("span", { text: n }),
        el("button", { class: "btn ghost small", text: "×", "aria-label": `Unban ${n}`, onclick: () => { toggle(s.add, n, false); changed(); render(); } })));
      const name = el("input", { type: "text", placeholder: "Lionheart", "aria-label": "Name to ban", spellcheck: "false" });
      clear(box.banned).append(el("h2", { text: "Ban list" }),
        el("p", { class: "note", text: "Names the game never hands out (mostly canon characters). Click one to allow it again. You can ban any prefix + suffix the game can make." }),
        el("div", { class: "row", style: { flexWrap: "wrap" } }, ...chips),
        el("div", { class: "row", style: { flexWrap: "wrap" } }, el("span", { class: "lbl", text: "Ban" }), name,
          el("button", { class: "btn small", text: "Ban name", onclick: () => {
            const n = name.value.trim();
            if (n && !s.add.includes(n)) { s.add.push(n); changed(); render(); }
          } }), ...added));
    }

    // How names.json's "cats" names this cat: "player", its name when no other cat has it, else its place
    // in the save. A place can shift as cats come and go, so entries keyed by place also say "was".
    function catKey(c) {
      if (c.target === "player") return "player";
      return game.cats.filter(o => o.name === c.name).length > 1 ? c.target : c.name;
    }
    function renderCats() {
      if (!game.cats.length) {
        clear(box.cats).append(el("h2", { text: "Cats in your save" }), el("p", { class: "note", text: "No save yet; start the game once." }));
        return;
      }
      const keys = new Set(game.cats.map(catKey));
      const rows = game.cats.map(c => {
        const key = catKey(c);
        const cur = spec.cats[key];
        const mode = cur && typeof cur === "object" ? (cur.fixed ? "fixed" : cur.prefix ? "prefix" : "name") : "name";
        const value = cur && typeof cur === "object" ? (cur.fixed || cur.prefix || cur.name || "") : (cur || "");
        const text = el("input", { type: "text", value, placeholder: c.name, "aria-label": `New name for ${c.name}`, spellcheck: "false" });
        const kind = el("select", { "aria-label": `How ${c.name}'s new name works` },
          el("option", { value: "name", text: "whole name" }), el("option", { value: "prefix", text: "prefix (grows with rank)" }),
          el("option", { value: "fixed", text: "fixed (never changes)" }));
        kind.value = mode;
        const update = () => {
          const v = text.value.trim();
          if (!v) delete spec.cats[key];
          else if (key.includes("/")) spec.cats[key] = { [kind.value]: v, was: c.name };
          else spec.cats[key] = kind.value === "name" ? v : { [kind.value]: v };
          changed();
        };
        text.addEventListener("change", update); kind.addEventListener("change", update);
        const after = el("td", { class: "muted", text: c.with_mods === c.name ? "" : c.with_mods });
        afterCells.set(key, after);
        return el("tr", {},
          el("td", {}, el("strong", { text: c.name }), el("div", { class: "muted", style: { fontSize: "0.78rem" },
            text: [c.where.replace(/\//g, " · "), c.roles.length ? `story role: ${c.roles.join(", ")}` : ""].filter(Boolean).join(" — ") })),
          el("td", { class: "muted", text: c.role.replace(/([a-z])([A-Z])/g, "$1 $2") }),
          el("td", {}, el("div", { class: "row" }, text, kind)), after);
      });
      // Entries for cats not listed under that key: renames already in the save (the cat has its new
      // name now), or cats this save doesn't have. They stay in names.json until removed here.
      const earlier = Object.keys(spec.cats).filter(k => !keys.has(k)).map(k => {
        const v = spec.cats[k];
        const to = typeof v === "object" ? (v.name || v.prefix || v.fixed) : v;
        return el("span", { class: "chip" }, el("span", { text: `${k} → ${to}` }),
          el("button", { class: "btn ghost small", text: "×", "aria-label": `Forget the rename of ${k}`,
            onclick: () => { delete spec.cats[k]; changed(); render(); } }));
      });
      clear(box.cats).append(el("h2", { text: "Cats in your save" }),
        el("p", { class: "note", text: "Give any cat a new name. A whole name like Mothheart must be a prefix + suffix (new ones count); a prefix grows with rank (Sparkle: Sparklepaw, then Sparkleheart); a fixed name stays the same. Story roles show the cat cast in them." }),
        el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, el("th", { text: "Cat" }), el("th", { text: "Rank" }), el("th", { text: "New name" }), el("th", { text: "After install" }))),
          el("tbody", {}, ...rows))),
        earlier.length ? el("div", { class: "row", style: { flexWrap: "wrap" } },
          el("span", { class: "lbl", title: "Already in your save, or cats this save doesn't have. Keep them so their names keep working.", text: "Earlier renames" }), ...earlier) : null);
    }

    function renderNotes() {
      const w = view?.warnings || [], r = view?.renames || [];
      clear(notes).append(el("h2", { text: "What this does" }),
        el("p", { class: "note", text: `${view?.changed_texts || 0} English names change or are added${r.length ? `; ${r.length} cat${r.length > 1 ? "s" : ""} renamed in your save: ${r.map(x => `${x.from} → ${x.to}`).join(", ")}` : ""}.` }),
        ...w.map(t => el("div", { class: "row" }, el("span", { class: "chip warn", text: "Check" }), el("span", { text: t }))));
    }

    return { unmount() { clearTimeout(timer); } };
  },
};
