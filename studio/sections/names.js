// Names page: rename your cats, the names new cats get (the game's name parts and rogue names, the ban list) and
// any name the game shows (cameo cats too). Writes names.json (see wcmods/names.py); names-logic.js holds the
// parts with no page in them. What each row will do comes from the studio's preview of the file as it is on the
// page (POST /names/preview), which names the cats as the next Apply would.
import {
  KEEP, readNames, writeNames, splitName, catNames, catKey, countNames, entryKeyFor, entryKeysFor, entryText, catEntry,
  canGrow, outcomeLine, gameNameFor, rankWords, slotHeading, whereWords, clansWords, ranksWords, summary, notesAt,
  textOf, questDetail, itemDetail, otherTexts, KIND_WORDS,
} from "./names-logic.js";

const LEDE = "Rename your cats, the names new cats get, and the words the game shows.";
const MISSING = "<MISSING STRING TABLE ENTRY>";

export default {
  title: "Names",
  async mount(root, wc) {
    const { el, api, clear, toast } = wc;
    let spec = readNames({}, null).spec, extra = {}, game = null, view = null, timer = null, seq = 0;
    let nameCount = new Map();
    let catFilter = "", openSlots = null, settling = false;   // kept across redraws of the cats card
    let catsStale = false;   // after an Apply: the next preview draws the cats again (their names, the keys of their rows)
    const filters = { prefixes: "", suffixes: "" };           // what's typed in each card's Find box, kept through Add
    // What's drawn, for updating in place after a preview.
    let rows = new Map();          // a cat's target -> its row: { c, tr, box, grows, growsLabel, line, after, said, mod, key }
    let earlierBox = null, banner = null, offBanner = null, ask = null;
    let partRows = { prefixes: [], suffixes: [], rogues: [] };   // [{ x, tr, rename, remove, reset, said }]
    let nameRows = [];   // [{ name, also }]
    let banChips = [];   // [{ b, chip }]
    let texts = null, placeRows = [];   // the Places card's lists (GET /names/texts), once opened, and its rows
    let drawnProblem = null;   // the save problem the cats card says, if any
    // Whether the cats card has to be drawn again for the latest preview: other cats, or another save problem.
    const listChanged = () => [...rows.keys()].join("|") !== (view.cats || []).map(c => c.target).join("|")
      || (view.save_problem || null) !== drawnProblem;
    const cards = { cats: card("cats"), prefixes: card("prefixes"), suffixes: card("suffixes"), rogues: card("rogues"),
                    names: card("names"), banned: card("banned"),
                    places: el("details", { class: "card fold names-places", "data-key": "names:places" }) };
    cards.places.addEventListener("toggle", () => openPlaces());
    const notes = el("div", { class: "card names-summary" });
    const out = wc.codePanel("names.json");
    const loading = el("p", { class: "note", role: "status", text: "Reading the game's names…" });

    root.append(
      wc.pageHead({ eyebrow: "Cat names and words", title: "Names", lede: LEDE, help: "help:names" }),
      el("ul", { class: "names-rules" },
        el("li", { text: "Renames change the English text." }),
        el("li", { text: "New names (a new prefix, a name of your own) are text this mod adds, so keep the mod on." }),
        el("li", { text: "Cat renames go into your save when you Apply, after a backup." })),
      missingFold(), loading);

    // Read the game's names first: when that fails (no game found yet, its files unreadable), the error goes up,
    // and app.js says it with Try again, with nothing half drawn.
    game = await api.get("/names");
    view = game;
    loading.remove();

    const target = wc.modTarget({
      file: "names.json",
      onLoad: obj => { load(obj); render(); preview(); },
      getValue: () => writeNames(spec, extra),
    });
    root.append(target.element, notes, cards.cats, cards.prefixes, cards.suffixes, cards.rogues, cards.names, cards.banned, cards.places, out.element);
    // After an Apply the save has the new names: the cats are read again even with changes not saved (the file
    // isn't touched), and the file itself only while there are none (wc.installedEvent).
    const off = [
      wc.bus.on("installed", () => { catsStale = true; preview(); }),
      wc.installedEvent(target, () => target.refresh().catch(() => { /* the bar says */ })),
    ];
    await target.refresh();

    // ---------- model ----------
    function load(obj) {
      const r = readNames(obj, game);
      spec = r.spec; extra = r.extra;
      if (r.unplaced.length) {
        toast(`Some names in this file aren't in the game's lists, so they aren't shown here (they stay in the file): ${r.unplaced.slice(0, 6).join(", ")}${r.unplaced.length > 6 ? "…" : ""}`);
      }
    }
    function changed() {
      target.markDirty();
      out.set(writeNames(spec, extra));
      clearTimeout(timer);
      timer = setTimeout(() => preview(), 350);
    }
    // The preview of the file as it is on the page. Rows update in place, so typing never loses its place; the
    // cats card is drawn again only when the list of cats changes (after an Apply, or a save that's readable again).
    async function preview({ cats = false } = {}) {
      out.set(writeNames(spec, extra));
      const mine = ++seq;
      try {
        const v = await api.post("/names/preview", { spec: writeNames(spec, extra), mod: target.current });
        if (mine !== seq) return;   // an older answer that came back late
        view = v;
        renderNotes();
        if (cats || catsStale || listChanged()) { catsStale = false; renderCats(); } else updateCats();
        updateParts();
      } catch (e) {
        if (mine === seq) clear(notes).append(el("h2", { text: "What this does" }), el("p", { class: "names-bad", role: "alert", text: e.message }));
      }
    }
    const toggle = (list, item, on) => { const i = list.indexOf(item); if (on && i < 0) list.push(item); if (!on && i >= 0) list.splice(i, 1); };
    const setRename = (map, from, to) => { to = to.trim(); if (!to || to === from) delete map[from]; else map[from] = to; };

    // ---------- rendering ----------
    // Each card is a scope of its own, so focus finds its own Remove buttons again.
    function card(id) { return el("div", { class: "card", "data-key": `names:${id}` }); }
    function render() {
      renderCats();
      renderAffixes("prefixes", "Prefixes", "The first part of a clan cat's name. Renaming changes every name with it (Otterpaw, Otterheart…).", game.prefixes, p => clansWords(p.weights));
      renderAffixes("suffixes", "Suffixes", "The second part, which changes with rank: kits are -kit, apprentices -paw, leaders -star. Those three can be renamed but not removed.", game.suffixes, s => ranksWords(s.weights));
      renderRogues(); renderNames(); renderBanned(); renderPlaces(); renderNotes();
      updateParts();
      out.set(writeNames(spec, extra));
    }

    // The fold under the page's head: what to do when a cat shows as Cat 1 or the missing-text line.
    function missingFold() {
      return el("details", { class: "fold names-missing", "data-key": "names:missing" },
        el("summary", {}, el("strong", { text: `If a cat shows as Cat 1 or ${MISSING}` })),
        el("p", { text: `The save has the cat's new name, but the game has no text for it. A name a mod made (a new prefix, a name of your own) is text only that mod gives, so the game shows ${MISSING} while the mod is off, and your cat is called Cat 1 in dialogue and the den. Three ways back:` }),
        el("ol", {},
          el("li", { text: "Turn the mod that named the cat back on, then Apply to game." }),
          el("li", { text: "Or give the cat a game name here: its row has Give it a game name. Save to mod, then Apply to game." }),
          el("li", { text: "Or put back a backup of your save from before (Settings and repair)." })),
        el("p", { class: "note", text: "If it happens with the mod on, check that Apply to game finished, and that Get set up found the copy of the game Steam starts." }));
    }

    // ---------- cats in your save ----------
    function renderCats() {
      const cats = view.cats || [];
      const box = cards.cats;
      rows = new Map();
      drawnProblem = view.save_problem || null;
      earlierBox = banner = offBanner = ask = null;
      nameCount = countNames(cats);
      const intro = el("p", { class: "note", text: `Type a new name. A prefix + suffix the game has (Mothheart) grows with rank, like any clan cat's; any other name stays the same at every rank, unless you tick "grows with rank". Story roles show the cat cast in them.` });
      if (view.save_problem) {
        clear(box).append(el("h2", { text: "Cats in your save" }), el("div", { class: "banner names-problem", role: "alert" },
          el("span", { text: view.save_problem }),
          el("button", { class: "btn small", type: "button", text: "Try again", onclick: () => preview({ cats: true }) })));
        return;
      }
      if (!cats.length) {
        clear(box).append(el("h2", { text: "Cats in your save" }), el("p", { class: "note", text: "No save yet: start the game once, and your cats show here." }));
        return;
      }
      const slots = [...new Set(cats.map(c => c.slot))];   // the game being played comes first
      if (!openSlots) openSlots = new Set(slots.slice(0, 1));
      const trs = [];
      const table = list => el("div", { class: "table-wrap" }, el("table", { class: "grid-table names-cats" },
        el("thead", {}, el("tr", {}, el("th", { text: "Cat" }), el("th", { text: "Rank" }), el("th", { text: "New name" }), el("th", { text: "After Apply" }))),
        el("tbody", {}, ...list.map(c => { const r = catRow(c); trs.push(r.tr); return r.tr; }))));
      // One game: the table as it always was. Several: a fold per game, the one being played open.
      const groups = slots.length > 1 ? slots.map(slot => {
        const list = cats.filter(c => c.slot === slot);
        const fold = el("details", { class: "fold", open: openSlots.has(slot), "data-slot": slot },
          el("summary", {}, el("strong", { text: slotHeading(slot, list) }),
            el("span", { class: "muted", text: `${list.length} cat${list.length === 1 ? "" : "s"}${list[0].current ? " · played last" : ""}` })),
          table(list));
        // Toggles come later than the change, so a search's own unfolding (below) is told apart from the player's.
        fold.addEventListener("toggle", () => { if (catFilter || settling) return; if (fold.open) openSlots.add(slot); else openSlots.delete(slot); });
        return fold;
      }) : [table(cats)];
      const find = el("input", { type: "search", value: catFilter, placeholder: "Find a cat", "aria-label": "Find a cat by name, rank or place", style: { minWidth: "14rem" } });
      const count = el("span", { class: "muted", role: "status" });
      const applyFilter = () => {
        catFilter = find.value.trim().toLowerCase();
        let shown = 0;
        for (const tr of trs) { const hit = !catFilter || tr.dataset.find.includes(catFilter); tr.hidden = !hit; shown += hit; }
        settling = true;
        for (const g of groups) {
          if (g.tagName !== "DETAILS") continue;
          const hits = trs.filter(tr => !tr.hidden && g.contains(tr)).length;
          g.hidden = !!catFilter && !hits;   // while searching, every game with a match is unfolded
          g.open = catFilter ? hits > 0 : openSlots.has(g.dataset.slot);
        }
        setTimeout(() => { settling = false; }, 0);   // after the toggle events these changes queue
        count.textContent = catFilter ? `${shown} of ${cats.length} cats` : `${cats.length} cats${slots.length > 1 ? ` in ${slots.length} games` : ""}`;
      };
      find.addEventListener("input", applyFilter);
      banner = el("div", { class: "banner warn names-losing", role: "status", hidden: true });
      offBanner = el("div", { class: "banner warn names-off", role: "status", hidden: true });
      ask = el("div", { class: "banner warn", role: "group", "aria-label": "Forget this rename?", hidden: true });
      earlierBox = el("div", { class: "row names-earlier", style: { flexWrap: "wrap" } });
      clear(box).append(...[el("h2", { text: "Cats in your save" }), intro, banner, offBanner,
        el("div", { class: "row" }, find, count),
        !cats.some(c => c.current) && view.current_slot != null
          ? el("p", { class: "note", text: `The game you're playing has no named cats yet, so "your cat" means no one until it does; the games below are your others.` }) : null,
        ...groups, ask, earlierBox].filter(Boolean));
      applyFilter();
      updateCats();
    }

    function catRow(c) {
      const r = { c, key: entryKeyFor(c, spec.cats, nameCount) };
      const { text, grows } = entryText(r.key ? spec.cats[r.key] : undefined);
      r.box = el("input", { type: "text", value: text, placeholder: "New name", "aria-label": `New name for ${c.name}`, spellcheck: "false" });
      r.grows = el("input", { type: "checkbox", checked: grows, "aria-label": `${c.name}'s new name grows with rank` });
      r.growsLabel = el("label", { class: "row names-grows" }, r.grows, el("span", { text: "grows with rank" }));
      r.line = el("div", { class: "muted names-line" });
      r.said = el("div", { class: "names-said" });
      r.name = el("strong", { text: c.name });
      r.mod = el("div", { class: "names-mod" });
      r.after = el("td", { class: "names-after" });
      r.box.addEventListener("input", () => showGrows(r));
      r.box.addEventListener("change", () => write(r));
      r.grows.addEventListener("change", () => write(r));
      r.tr = el("tr", { "data-key": `cat:${c.target}`, "data-find": "" },
        el("td", {}, r.name, el("div", { class: "muted names-where", text: whereWords(c) }), r.mod),
        el("td", { class: "muted", text: rankWords(c.role) }),
        el("td", {}, r.box, r.growsLabel, r.line, r.said), r.after);
      rows.set(c.target, r);
      return r;
    }
    // "grows with rank" shows for a clan cat whose new name isn't a prefix + suffix (which grows on its own).
    function showGrows(r) {
      const can = canGrow(r.c, r.box.value, game, view.final);
      r.growsLabel.hidden = !can;
      r.growsLabel.querySelector("span").textContent = can ? `grows with rank (${r.box.value.trim()}kit, ${r.box.value.trim()}paw…)` : "grows with rank";
    }
    function write(r) {
      const key = catKey(r.c, nameCount);
      const value = catEntry(r.box.value, r.grows.checked && canGrow(r.c, r.box.value, game, view.final), key, r.c);
      // The box replaces every entry for this cat: one an older page wrote by its IDs too, not only the one it showed.
      for (const k of new Set([r.key, ...entryKeysFor(r.c, spec.cats, nameCount)])) if (k && k !== key) delete spec.cats[k];
      if (value === undefined) delete spec.cats[key]; else spec.cats[key] = value;
      r.key = value === undefined ? null : key;
      changed();
    }
    // The rows, the banner and the earlier renames, from the latest preview, in place.
    function updateCats() {
      const cats = view.cats || [];
      const losing = new Map((view.losing_text || []).map(x => [x.target, x]));
      for (const c of cats) {
        const r = rows.get(c.target);
        if (!r) continue;
        r.c = c;
        r.name.textContent = c.name;
        r.tr.setAttribute("data-find", `${c.name} ${c.with_mods} ${rankWords(c.role)} ${whereWords(c)}`.toLowerCase());
        const key = r.key || catKey(c, nameCount);
        // What the planner says about this cat's entry, then about any other entry for it (renamed twice).
        const others = entryKeysFor(c, spec.cats, nameCount).filter(k => k !== key);
        const said = [key, ...others].flatMap(k => notesAt(view, `cats.${k}`));
        r.line.textContent = outcomeLine(c, r.box.value, game, view.final, said[0]);
        r.line.className = `names-line${c.how === "none" ? " names-bad" : " muted"}`;
        clear(r.said).append(...said.filter(t => t !== r.line.textContent).map(t => el("div", { class: "names-note", text: t })));
        showGrows(r);
        clear(r.mod);
        if (c.mod_named) {
          r.mod.append(el("span", { class: "chip", text: c.name_known && !c.named_by_off_mod ? "name from a mod" : "name from a mod that's off" }), " ",
            el("button", { class: "btn link small", type: "button", text: "Give it a game name", "aria-label": `Give ${c.name} a game name`,
              onclick: () => giveGameName(r) }));
        }
        clear(r.after);
        const gone = losing.get(c.target);
        if (c.how === "none" || gone) {
          r.after.append(el("span", { class: "chip bad", text: "no text", title: c.how === "none" ? (said[0] || "") : `${MISSING}: no mod in your next Apply gives this name's text` }),
            el("div", { class: "muted names-why", text: c.how === "none" ? "keeps its name" : `shows as ${MISSING}` }));
        } else if (c.with_mods && c.with_mods !== c.name) {
          r.after.append(el("span", { text: c.with_mods }));
        }
      }
      if (banner) {
        const lost = view.losing_text || [];
        banner.hidden = !lost.length;
        clear(banner);
        if (lost.length) {
          banner.append(el("strong", { text: `${lost.length === 1 ? "A cat" : `${lost.length} cats`} would show as ${MISSING} after the next Apply` }),
            el("span", { text: "Their names are text only a mod gives, and that mod is off (or its rename was taken out here). Turn it back on, or give them game names:" }),
            el("div", { class: "row", style: { flexWrap: "wrap" } }, ...lost.map(x => {
              const r = rows.get(x.target);
              return el("button", { class: "btn small", type: "button", text: `${x.name || "this cat"}: give it a game name`, onclick: () => r && giveGameName(r) });
            })));
        }
      }
      if (offBanner) {
        // The mod being edited is off: the cats only it names show as the missing-text line now, though the list
        // names them (its file counts here, since Save to mod turns it on).
        const off = view.mod_off ? view.off_named || [] : [];
        offBanner.hidden = !off.length;
        clear(offBanner);
        if (off.length) {
          offBanner.append(el("strong", { text: `This mod is off: ${off.length === 1 ? "this cat shows" : "these cats show"} as ${MISSING} until it's on and applied` }),
            el("span", { text: `${off.map(x => x.name || "a cat").join(", ")}. Save to mod turns it on; then press Apply to game.` }));
        }
      }
      renderEarlier();
    }
    function giveGameName(r) {
      const name = gameNameFor(r.c, spec.cats, game, view.final);
      if (!name) { toast("There's no game name to offer for this cat", "bad"); return; }
      r.box.value = name;
      r.grows.checked = false;
      showGrows(r);
      write(r);
      r.box.focus();
      toast(`${r.c.name} will be called ${name}. Save to mod, then Apply to game.`);
    }

    // Entries for cats not listed under that key: renames already in the save (the cat has its new name now), or
    // cats this save doesn't have. They stay in names.json until taken out here; taking one out asks first when a
    // cat would lose its name for it.
    function renderEarlier() {
      if (!earlierBox) return;
      // A row's own entries: the one its box shows, and any other for the same cat (its row says it's renamed twice).
      const used = new Set([...rows.values()].flatMap(r => [r.key, ...entryKeysFor(r.c, spec.cats, nameCount)]).filter(Boolean));
      const keys = Object.keys(spec.cats).filter(k => !used.has(k));
      clear(earlierBox);
      if (!keys.length) return;
      earlierBox.append(el("span", { class: "lbl", title: "Already in your save, or cats this save doesn't have. Keep them so their names keep working.", text: "Earlier renames" }),
        ...keys.map(k => {
          const { text } = entryText(spec.cats[k]);
          const who = k === "player" ? "your cat" : k.includes("/") ? k.split("/").join(" · ") : k;
          return el("span", { class: "chip" }, el("span", { text: `${who} → ${text}` }),
            el("button", { class: "btn ghost small", type: "button", text: "×", "aria-label": `Forget the rename of ${who}`, onclick: () => forget(k) }));
        }));
    }
    async function forget(key) {
      const without = { ...spec.cats };
      delete without[key];
      let lost = [];
      try {
        const v = await api.post("/names/preview", { spec: writeNames({ ...spec, cats: without }, extra), mod: target.current });
        const before = new Set((view.losing_text || []).map(x => x.target));
        lost = (v.losing_text || []).filter(x => !before.has(x.target));
      } catch (e) { /* asked as if nothing changed: the preview says what's wrong */ }
      const go = () => { delete spec.cats[key]; ask.hidden = true; changed(); renderEarlier(); };
      if (!lost.length) { go(); return; }
      const names = lost.map(x => x.name || "a cat").join(", ");
      const said = `Forget this rename? ${names} would show as ${MISSING} until you give ${lost.length === 1 ? "it" : "them"} another name.`;
      clear(ask).append(el("span", { text: said }),
        el("div", { class: "row" },
          el("button", { class: "btn danger small", type: "button", text: "Forget it", onclick: go }),
          el("button", { class: "btn ghost small", type: "button", text: "Keep it", onclick: () => { ask.hidden = true; } })));
      ask.hidden = false;
      wc.announce(said);
      ask.querySelector("button").focus();
    }

    // ---------- prefixes and suffixes ----------
    function renderAffixes(kind, title, note, items, usedBy) {
      const s = spec[kind], noun = kind.slice(0, -2);
      const filter = el("input", { type: "search", value: filters[kind], placeholder: `Find a ${noun}`, "aria-label": `Find a ${noun}` });
      const body = el("tbody");
      const seen = new Set();
      partRows[kind] = [];
      const rowsHere = items.filter(x => !seen.has(x.text) && seen.add(x.text)).map(x => {
        const locked = kind === "suffixes" && KEEP.includes(x.text);
        const p = { x, kind };
        p.rename = el("input", { type: "text", value: s.rename[x.text] || "", placeholder: x.text, "aria-label": `New text for ${x.text}`, spellcheck: "false",
          onchange: e => { setRename(s.rename, x.text, e.target.value); showReset(p); changed(); } });
        p.remove = locked ? null : el("input", { type: "checkbox", checked: s.remove.includes(x.text), "aria-label": `Remove ${x.text}`,
          onchange: e => { toggle(s.remove, x.text, e.target.checked); p.tr.className = e.target.checked ? "muted" : ""; showReset(p); changed(); } });
        p.reset = el("button", { class: "btn ghost small", type: "button", text: "Reset", "aria-label": `Reset ${x.text}`, onclick: () => {
          delete s.rename[x.text]; toggle(s.remove, x.text, false);
          p.rename.value = ""; if (p.remove) p.remove.checked = false; p.tr.className = ""; showReset(p); changed();
        } });
        p.said = el("div", { class: "names-said" });
        p.tr = el("tr", { "data-name": x.text.toLowerCase(), class: s.remove.includes(x.text) ? "muted" : "" },
          el("td", {}, el("strong", { text: x.text }), p.said),
          el("td", {}, p.rename),
          el("td", { class: "muted", text: usedBy(x) }),
          el("td", {}, el("div", { class: "row", style: { flexWrap: "nowrap" } },
            locked ? el("span", { class: "muted", text: "needed" }) : el("label", { class: "row", style: { flexWrap: "nowrap", whiteSpace: "nowrap" } },
              p.remove, el("span", { text: "Remove" })), p.reset)));
        showReset(p);
        partRows[kind].push(p);
        return p.tr;
      });
      for (const [name, opts] of Object.entries(s.add)) {
        const like = opts && opts.like ? items.find(x => x.text.toLowerCase() === String(opts.like).toLowerCase()) : null;
        const said = el("div", { class: "names-said" });
        partRows[kind].push({ added: name, kind, said });
        body.append(el("tr", {},
          el("td", {}, el("strong", { text: name }), el("span", { class: "chip good", style: { marginLeft: "6px" }, text: "new" }), said),
          el("td", { class: "muted", text: like ? `used like ${like.text}` : "used like an average one" }),
          el("td", { class: "muted", text: like ? usedBy(like) : kind === "prefixes" ? "every clan, average" : "most ranks, average" }),
          el("td", {}, el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove ${name}`, onclick: () => { delete s.add[name]; changed(); rerenderPart(kind); } }))));
      }
      body.append(...rowsHere);
      const applyFilter = () => {
        filters[kind] = filter.value;
        const q = filter.value.trim().toLowerCase();
        for (const tr of rowsHere) tr.hidden = !!q && !tr.dataset.name.includes(q);
      };
      filter.addEventListener("input", applyFilter);
      const addName = el("input", { type: "text", placeholder: kind === "prefixes" ? "Sparrow" : "whisper", "aria-label": `New ${noun}`, spellcheck: "false" });
      const likeBox = el("select", { "aria-label": "Copy how often it's used from" },
        el("option", { value: "", text: "used like an average one" }),
        ...[...new Set(items.map(x => x.text))].map(t => el("option", { value: t, text: `used like ${t}` })));
      const add = () => {
        const name = addName.value.trim();
        if (!name) return;
        if (items.some(x => x.text.toLowerCase() === name.toLowerCase()) || Object.keys(s.add).some(n => n.toLowerCase() === name.toLowerCase())) { toast(`${name} is already a ${noun}`, "bad"); return; }
        s.add[name] = likeBox.value ? { like: likeBox.value } : {};
        changed(); rerenderPart(kind);
      };
      clear(cards[kind]).append(el("div", { class: "row spread" }, el("h2", { text: title }), filter),
        el("p", { class: "note", text: note }),
        el("div", { class: "row" }, el("span", { class: "lbl", text: "Add" }), addName, likeBox,
          el("button", { class: "btn small", type: "button", text: `Add ${noun}`, onclick: add })),
        el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, el("th", { text: kind === "prefixes" ? "Prefix" : "Suffix" }), el("th", { text: "Rename to" }),
            el("th", { text: kind === "prefixes" ? "Given out in" : "Given to" }), el("th", { text: "" }))), body)));
      applyFilter();
    }
    function rerenderPart(kind) {
      if (kind === "prefixes") renderAffixes("prefixes", "Prefixes", "The first part of a clan cat's name. Renaming changes every name with it (Otterpaw, Otterheart…).", game.prefixes, p => clansWords(p.weights));
      else if (kind === "suffixes") renderAffixes("suffixes", "Suffixes", "The second part, which changes with rank: kits are -kit, apprentices -paw, leaders -star. Those three can be renamed but not removed.", game.suffixes, s => ranksWords(s.weights));
      else if (kind === "rogues") renderRogues();
      updateParts();
    }
    // A Reset shows only on a row with a change.
    function showReset(p) {
      const s = spec[p.kind];
      p.reset.hidden = !(s.rename[p.x.text] || s.remove.includes(p.x.text));
    }

    // ---------- rogue and loner names ----------
    function renderRogues() {
      const s = spec.rogues;
      partRows.rogues = [];
      const trs = game.rogues.map(r => {
        const p = { x: r, kind: "rogues" };
        p.rename = el("input", { type: "text", value: s.rename[r.text] || "", placeholder: r.text, "aria-label": `New name for ${r.text}`, spellcheck: "false",
          onchange: e => { setRename(s.rename, r.text, e.target.value); showReset(p); changed(); } });
        p.remove = el("input", { type: "checkbox", checked: s.remove.includes(r.text), "aria-label": `Remove ${r.text}`,
          onchange: e => { toggle(s.remove, r.text, e.target.checked); p.tr.className = e.target.checked ? "muted" : ""; showReset(p); changed(); } });
        p.reset = el("button", { class: "btn ghost small", type: "button", text: "Reset", "aria-label": `Reset ${r.text}`, onclick: () => {
          delete s.rename[r.text]; toggle(s.remove, r.text, false); p.rename.value = ""; p.remove.checked = false; p.tr.className = ""; showReset(p); changed();
        } });
        p.said = el("div", { class: "names-said" });
        p.tr = el("tr", { class: s.remove.includes(r.text) ? "muted" : "" },
          el("td", {}, el("strong", { text: r.text }), p.said),
          el("td", {}, p.rename),
          el("td", {}, el("div", { class: "row", style: { flexWrap: "nowrap" } },
            el("label", { class: "row", style: { flexWrap: "nowrap", whiteSpace: "nowrap" } }, p.remove, el("span", { text: "Remove" })), p.reset)));
        showReset(p);
        partRows.rogues.push(p);
        return p.tr;
      });
      const added = s.add.map(n => {
        const said = el("span", { class: "names-said" });
        partRows.rogues.push({ added: n, kind: "rogues", said });
        return el("span", { class: "chip good" }, el("span", { text: n }), said,
          el("button", { class: "btn ghost small", type: "button", text: "×", "aria-label": `Remove ${n}`, onclick: () => { toggle(s.add, n, false); changed(); rerenderPart("rogues"); } }));
      });
      const name = el("input", { type: "text", placeholder: "Moss", "aria-label": "New rogue name", spellcheck: "false" });
      clear(cards.rogues).append(el("h2", { text: "Rogue and loner names" }),
        el("p", { class: "note", text: "Cats outside the clans get one whole name from this list." }),
        el("div", { class: "row" }, el("span", { class: "lbl", text: "Add" }), name,
          el("button", { class: "btn small", type: "button", text: "Add name", onclick: () => {
            const n = name.value.trim();
            if (!n) return;
            if (game.rogues.some(r => r.text.toLowerCase() === n.toLowerCase()) || s.add.some(x => x.toLowerCase() === n.toLowerCase())) { toast(`${n} is already a rogue name`, "bad"); return; }
            s.add.push(n); changed(); rerenderPart("rogues");
          } }), ...added),
        el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, el("th", { text: "Name" }), el("th", { text: "Rename to" }), el("th", { text: "" }))),
          el("tbody", {}, ...trs))));
    }

    // The planner's notes beside the parts' rows, and the ban list's names, from the latest preview.
    function updateParts() {
      for (const kind of ["prefixes", "suffixes", "rogues"]) {
        for (const p of partRows[kind]) {
          const at = p.added ? [`${kind}.add.${p.added}`] : ["rename", "remove", "weights"].map(op => `${kind}.${op}.${p.x.text}`);
          clear(p.said).append(...at.flatMap(w => notesAt(view, w)).map(t => el("div", { class: "names-note", text: t })));
        }
      }
      updateNames();
      updateBanned();
      updatePlaces();
    }

    // ---------- cameo cats and any name ----------
    function renderNames() {
      const map = spec.names;
      const iconic = Object.values(game.iconic);
      const free = Object.keys(map).filter(k => !iconic.includes(k));
      nameRows = [];
      const row = name => {
        const also = el("div", { class: "muted names-also" });
        nameRows.push({ name, also });
        return el("tr", {},
          el("td", {}, el("strong", { text: name }), also),
          el("td", {}, el("input", { type: "text", value: map[name] || "", placeholder: name, "aria-label": `New text for ${name}`, spellcheck: "false",
            onchange: e => { setRename(map, name, e.target.value); changed(); } })));
      };
      const choices = el("datalist", { id: "names-choices" }, ...catNames(game, view.final).map(n => el("option", { value: n })));
      const from = el("input", { type: "text", list: "names-choices", placeholder: "Name as the game shows it", "aria-label": "Name as the game shows it", spellcheck: "false" });
      const to = el("input", { type: "text", placeholder: "New text", "aria-label": "New text", spellcheck: "false" });
      clear(cards.names).append(el("h2", { text: "Cameo cats and any other name" }),
        el("p", { class: "note", text: "Changes every text that's exactly this name, wherever the game shows it. Some cameo names are also clan names (Brightheart is Bright + heart), so both change, and a name can also be something else in the game (Rock is a cameo cat and a material): what else changes shows under it." }),
        el("div", { class: "row" }, el("span", { class: "lbl", text: "Any name" }), from, choices, el("span", { class: "muted", text: "becomes" }), to,
          el("button", { class: "btn small", type: "button", text: "Add", onclick: () => {
            const f = from.value.trim(), t = to.value.trim();
            if (!f || !t) return;
            map[f] = t; changed(); renderNames(); updateNames();
          } })),
        el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, el("th", { text: "Name" }), el("th", { text: "Becomes" }))),
          el("tbody", {}, ...iconic.map(row), ...free.map(row)))));
    }
    function updateNames() {
      for (const r of nameRows) {
        const hits = view.names_hits?.[r.name];
        const said = notesAt(view, `names.${r.name}`);
        r.also.textContent = said[0] || (hits && hits.elsewhere.length ? `also changes ${hits.elsewhere.join(", ")}` : "");
      }
    }

    // ---------- the ban list ----------
    function renderBanned() {
      const s = spec.banned;
      banChips = game.banned.map(b => {
        const off = s.remove.includes(b.name);
        const chip = el("button", { class: "chip", type: "button", "aria-pressed": String(!off), title: off ? "Allowed again; click to ban it" : "Banned; click to allow it",
          style: off ? { textDecoration: "line-through", opacity: "0.6" } : {}, text: b.name,
          onclick: () => { toggle(s.remove, b.name, !off); changed(); renderBanned(); updateBanned(); } });
        return { b, chip };
      });
      const added = s.add.map(n => el("span", { class: "chip warn" }, el("span", { text: n }),
        el("button", { class: "btn ghost small", type: "button", text: "×", "aria-label": `Unban ${n}`, onclick: () => { toggle(s.add, n, false); changed(); renderBanned(); } })));
      const name = el("input", { type: "text", placeholder: "Lionheart", "aria-label": "Name to ban", spellcheck: "false" });
      clear(cards.banned).append(el("h2", { text: "Ban list" }),
        el("p", { class: "note", text: "Names the game never hands out (mostly canon characters). Click one to allow it again. You can ban any prefix + suffix the game can make." }),
        el("div", { class: "row", style: { flexWrap: "wrap" } }, ...banChips.map(x => x.chip)),
        el("div", { class: "row", style: { flexWrap: "wrap" } }, el("span", { class: "lbl", text: "Ban" }), name,
          el("button", { class: "btn small", type: "button", text: "Ban name", onclick: () => {
            const n = name.value.trim();
            if (!n || s.add.includes(n)) return;
            if (!splitName(n, game, view.final)) { toast(`${n} isn't a prefix + suffix the game can make, so it can't be banned`, "bad"); return; }
            s.add.push(n); changed(); renderBanned();
          } }), ...added));
    }
    // A banned name shows as it will read after this page's renames (Lionstar, once Tiger is renamed Lion).
    function updateBanned() {
      for (const { b, chip } of banChips) chip.textContent = textOf(game, b.prefix, b.suffix, view.final) || b.name;
    }

    // ---------- places, quests and items ----------
    // Folded at first: the lists are read from the game (GET /names/texts) the first time it's opened. Each
    // Rename box writes names.json's "text" by the key the game shows that text from.
    function renderPlaces() {
      const s = spec.text;
      const count = Object.keys(s).length;
      const fold = cards.places;
      const wasOpen = fold.open;
      clear(fold).append(el("summary", {}, el("h2", { text: "Places, quests and items" }),
        el("span", { class: "muted", text: count ? `${count} renamed` : "Rename an area, a quest's title or an item" })));
      fold.open = wasOpen;
      if (!texts) {
        fold.append(el("p", { class: "note", role: "status", text: "Opens with the game's areas, quest titles and items." }));
        return;
      }
      placeRows = [];
      const filter = el("input", { type: "search", placeholder: "Find a place, quest or item", "aria-label": "Find a place, quest or item", style: { minWidth: "16rem" } });
      // One row per text: a title several quests share, or a name several items share, is one box.
      const row = (item, detail, other = false) => {
        const said = el("div", { class: "names-said" });
        const shown = () => (other ? otherText(item.key) : item.text);   // the game's text: typing it back takes the entry out
        const box = item.key ? el("input", { type: "text", value: s[item.key] || "", placeholder: item.text, "aria-label": `New text for ${item.text}`, spellcheck: "false",
          onchange: e => { const v = e.target.value.trim(); if (!v || v === shown()) delete s[item.key]; else s[item.key] = v; changed(); renderPlacesCount(); } })
          : el("span", { class: "muted", text: "Its name comes with the mod that adds it, so it can't be renamed here" });
        // Another text this file renames: the game's text for it, its key only in the tooltip.
        const name = el("strong", { text: item.text, ...(other ? { title: item.key } : {}) });
        const tr = el("tr", { "data-find": `${item.text} ${detail}`.toLowerCase() },
          el("td", {}, name, el("div", { class: "muted names-where", text: detail }), said), el("td", {}, box));
        placeRows.push({ key: item.key, tr, said, name, box, other, detail });
        return tr;
      };
      const table = trs => el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
        el("thead", {}, el("tr", {}, el("th", { text: "In the game" }), el("th", { text: "Rename to" }))), el("tbody", {}, ...trs)));
      const part = (title, trs) => el("details", { class: "fold", "data-key": `names:places:${title}` },
        el("summary", {}, el("strong", { text: title }), el("span", { class: "muted", text: `${trs.length}` })), table(trs));
      const areas = texts.areas.map(a => row(a, `area ${a.code}`));
      const quests = texts.quests.map(q => row(q, questDetail(q)));
      const kinds = [...new Set(texts.items.map(i => i.kind))];
      const items = kinds.map(k => part(KIND_WORDS[k] || k, texts.items.filter(i => i.kind === k).map(i => row(i, itemDetail(i)))));
      const others = otherTexts(s, texts).map(key => row({ key, text: otherText(key) }, "other text in the game", true));
      filter.addEventListener("input", () => {
        const q = filter.value.trim().toLowerCase();
        for (const r of placeRows) r.tr.hidden = !!q && !r.tr.dataset.find.includes(q);
        // While searching, a list with a match is unfolded and one without any is out of the way.
        for (const d of fold.querySelectorAll("details")) {
          const hits = [...d.querySelectorAll("tr")].filter(tr => tr.dataset.find && !tr.hidden).length;
          d.hidden = !!q && !hits;
          if (q) d.open = hits > 0;
        }
      });
      fold.append(
        el("p", { class: "note", text: "Each is a text the game shows. Renaming it changes it in English wherever the game uses it, and in the mod menu's pages. Not every game screen has been checked yet: if one still shows the old name, the mod menu shows yours." }),
        el("div", { class: "row" }, filter),
        part("Areas", areas), part("Quest titles", quests), ...items,
        ...(others.length ? [part("Other text", others)] : []));   // not null, which the page would show as "null"
      updatePlaces();
    }
    function renderPlacesCount() {
      const n = Object.keys(spec.text).length;
      const said = cards.places.querySelector("summary")?.querySelector("span");
      if (said) said.textContent = n ? `${n} renamed` : "Rename an area, a quest's title or an item";
    }
    async function openPlaces() {
      if (texts || !cards.places.open) return;
      clear(cards.places).append(el("summary", {}, el("h2", { text: "Places, quests and items" })),
        el("p", { class: "note", role: "status", text: "Reading the game's areas, quests and items…" }));
      cards.places.open = true;
      try { texts = await api.get("/names/texts"); }
      catch (e) {
        cards.places.append(el("div", { class: "banner names-problem", role: "alert" },
          el("span", { text: `Couldn't read the game's areas, quests and items: ${e.message}` }),
          el("button", { class: "btn small", type: "button", text: "Try again", onclick: () => openPlaces() })));
        return;
      }
      renderPlaces();
    }
    // The game's text for a key a "text" entry renames (the preview's text_now); none when the game hasn't one.
    function otherText(key) {
      const now = view?.text_now?.[key];
      return now === undefined ? "…" : now || "A text the game doesn't have yet";
    }
    function updatePlaces() {
      for (const r of placeRows) {
        clear(r.said).append(...(r.key ? notesAt(view, `text.${r.key}`) : []).map(t => el("div", { class: "names-note", text: t })));
        if (r.other) {
          const text = otherText(r.key);
          r.name.textContent = text;
          r.box.setAttribute("aria-label", `New text for ${text}`);
          r.box.setAttribute("placeholder", text);
          r.tr.setAttribute("data-find", `${text} ${r.key} ${r.detail}`.toLowerCase());
        }
      }
    }

    // ---------- what this does ----------
    function renderNotes() {
      const w = view?.warnings || [];
      clear(notes).append(el("h2", { text: "What this does" }), el("p", { class: "note", text: summary(view) }),
        ...w.map(t => el("div", { class: "row" }, el("span", { class: "chip warn", text: "Check" }), el("span", { text: t }))));
    }

    return { unmount() { clearTimeout(timer); off.forEach(f => f()); } };
  },
};

