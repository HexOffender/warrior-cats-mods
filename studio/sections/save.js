// Save: changes to your cat's save (its level, the fresh-kill pile, what it carries), each made once, with a
// copy of the save kept first, and each one can be put back. A list of changes to make, then Change my save
// now; or kept as a mod's save.json to share. The logic is studio/lib/save.js.
//
// A save holds a game for each cat started. The page changes one game at a time, the one chosen in Which game
// (GET /save's "games", lib/games.js), starting on the game played last; the list of changes to make can hold
// changes to several games, each under its game, so choosing another game never loses one.
import * as S from "../lib/save.js";
import * as G from "../lib/games.js";

const STORE = "wc-save-changes";   // sessionStorage: the list of changes to make, kept across page switches
const GAME = "wc-save-game";       // sessionStorage: the game chosen, and the game played last when it was chosen
const SHOW = 200;                  // a group in the tree shows this many keys, then "Show more"

export default {
  title: "Save",
  async mount(root, wc) {
    const { el, api, clear, toast } = wc;
    // slot: the game the page changes (chosen in Which game); current: the game played last, as the save says.
    let save = null, data = null, slot = null, current = "0", games = [], say = {}, list = S.emptyList();
    let items = { names: {}, kinds: {}, list: [], problem: null };
    let modFile = null;   // the share fold's mod: its save.json, as a list
    let uid = 0;
    const nextId = () => `sv-${++uid}`;

    const status = el("p", { class: "banner", role: "status", hidden: true });
    const errorBox = el("div", { hidden: true });
    const gameCard = el("div", { class: "card", id: "save-game" });
    const gamePick = el("select", { id: "save-game-pick" });
    gamePick.addEventListener("change", () => chooseGame(gamePick.value));
    const catCard = el("div", { class: "card", id: "save-cat" });
    const carryCard = el("div", { class: "card", id: "save-carry" });
    const pendingCard = el("div", { class: "card", id: "save-pending" });
    const doneCard = el("div", { class: "card", id: "save-done" });
    const out = wc.codePanel("save.json");
    const modWords = el("div", { class: "stack" });
    // A mod is made off here, and saving never turns one on: while it's on, the next Apply would make its changes
    // in your own save too (once), which is what Change my save now is for.
    const target = wc.modTarget({
      file: "save.json", share: false,   // shared as a whole mod, from the Mods page
      turnOn: false,
      savedSays: m => m.enabled
        ? `Saved in ${m.name}, which is on: the next Apply makes these changes in your own save too, once. Turn it off on the Mods page to only share it.`
        : `Saved in ${m.name}. It's off, so your own save isn't changed by it. Share it from the Mods page.`,
      onLoad: obj => { modFile = obj ? S.fromSaveJson(obj) : null; drawModFile(); },
      onSaved: obj => { modFile = S.fromSaveJson(obj); drawModFile(); },
      getValue: () => {
        if (S.isEmpty(list)) { toast("There are no changes in the list to keep in a mod yet", "bad"); return undefined; }
        return S.toSaveJson(list);
      },
    });
    const shareFold = el("details", { class: "card fold", id: "save-share" },
      el("summary", {}, el("h3", { text: "Keep it as a mod to share" }), el("span", { class: "muted", text: "The list above, as a mod's save.json" })),
      el("p", { class: "note", text: "Save to mod puts the list above in the mod's save.json, in place of what it had. Whoever installs the mod gets each change once, in their own save, after a copy of it is kept; playing on past a change is never undone." }),
      el("p", { class: "note", text: "A mod made here starts off, and saving doesn't turn it on, so your own save isn't changed by it. If you turn it on, the next Apply makes these changes in your own save too, once." }),
      el("p", { class: "note", id: "save-share-games", text: "Each change is for one game, by its number: in whoever adds the mod, it goes into their game with the same number (a change to your 5th game goes into their 5th game), whichever cat that is. A change to the game's settings goes to every game." }),
      target.element, modWords);
    const treeBox = el("div", { class: "stack" });
    const statsBox = el("div");
    const advanced = el("details", { class: "card fold", id: "save-advanced" },
      el("summary", {}, el("h2", { text: "Advanced" }), el("span", { class: "muted", text: "Everything in your save, the combat stats, and save.json" })),
      statsBox, treeBox, out.element);

    root.append(
      wc.pageHead({ eyebrow: "Your save", title: "Save", help: "help:save",
        lede: "Change what your cat has: its level, the fresh-kill pile, what it carries. Each change is made once, with a copy of your save kept first, and you can put any of them back." }),
      status, errorBox, gameCard, catCard, carryCard, pendingCard, doneCard, advanced);

    // ---------- reading the save ----------
    async function load() {
      try {
        save = await api.get("/save");
      } catch (e) {
        save = null;
        const none = e.status === 404;
        clear(errorBox).append(el("div", { class: "error-card" },
          el("h2", { text: none ? "No save yet: start the game once and come back" : "Couldn't read your save" }),
          el("p", { text: none ? "The game makes its save when you first play. This page changes that save." : e.message }),
          none ? null : el("p", { class: "note", text: "Your save is kept as it is. Settings and repair has the copies of it the studio kept, to put one back." }),
          el("button", { class: "btn", type: "button", text: "Try again", onclick: () => start() })));
        errorBox.hidden = false;
        for (const card of [gameCard, catCard, carryCard, pendingCard, doneCard, advanced]) card.hidden = true;
        return false;
      }
      errorBox.hidden = true;
      for (const card of [gameCard, catCard, carryCard, pendingCard, doneCard, advanced]) card.hidden = false;
      data = save.data;
      const before = slot === null ? keptGame() : { slot, last: current };
      current = String(save.current_cat?.slot ?? getSlot());
      games = G.pickable(save.games || [], current);
      // The game kept from before while the game played last is the same; after another game was played, that one.
      slot = G.startSlot(games, current, before) ?? current;
      say = { words: save.words, cats: save.cats || {}, current, items: items.names };
      running(save.game_running);
      drawGames();
      return true;
    }
    const getSlot = () => String(S.getPath(data, "Shared/General/CurrentCatSlot") ?? 0);
    const game = () => G.gameOf(games, slot);
    const cap = t => t.charAt(0).toUpperCase() + t.slice(1);

    // ---------- Which game ----------
    const gameKey = () => `${GAME}:${save?.account || ""}`;
    function keptGame() {
      try { return JSON.parse(sessionStorage.getItem(gameKey()) || "null"); } catch (e) { return null; }
    }
    function keepGame() {
      try { sessionStorage.setItem(gameKey(), JSON.stringify({ slot, last: current })); } catch (e) { /* the choice lasts as long as the page */ }
    }
    function drawGames() {
      clear(gamePick).append(...games.map(g => el("option", { value: g.slot, text: G.gameLabel(g) })));
      gamePick.value = slot;
      const twins = G.sameName(games, game());
      clear(gameCard).append(...[el("h2", { text: "Which game" }),
        games.length > 1
          ? el("div", { class: "field" }, el("label", { for: "save-game-pick", class: "lbl", text: "The game to change" }), gamePick)
          : el("p", { id: "save-game-only", text: `Your save has one game: ${G.gameLabel(game())}.` }),
        el("p", { class: "note", text: "Your save keeps a game for each cat you've started, numbered as the game's cat choice numbers them. This page starts on the game you played last; what's below is for the game chosen here." }),
        twins.length ? el("p", { class: "note heads-up", id: "save-game-twins", text: `${game().name}, the cat in ${G.gameWords(slot)}, has the same name as the cat in ${S.andList(twins.map(g => G.gameWords(g.slot)))}: the games' numbers tell them apart.` }) : null].filter(Boolean));
    }
    // Another game chosen: everything below is for it. The list of changes keeps every game's, each under its game.
    function chooseGame(to) {
      if (!games.some(g => g.slot === to) || to === slot) return;
      slot = to;
      keepGame();
      drawGames();
      drawAll();
      wc.announce(`Changing ${G.catInGame(game())}.`);
    }
    function running(on) {
      status.hidden = !on;
      status.textContent = on ? "The game is running: close it before changing your save." : "";
      const go = pendingCard.querySelector("#save-now");
      if (go) go.disabled = !!on || S.isEmpty(list);
    }
    async function loadItems() {
      try {
        const r = await api.get("/game/items");
        items = { names: {}, kinds: {}, list: r.items, problem: null };
        for (const i of r.items) { items.names[i.tag] = i.name; items.kinds[i.tag] = i.kind; }
      } catch (e) {
        items = { names: {}, kinds: {}, list: [], problem: /found the game/.test(e.message) ? "the game folder isn't set (Get set up, on the Mods page)" : "the game's files can't be read now" };
      }
      say.items = items.names;
    }

    // ---------- the list of changes to make ----------
    const storeKey = () => `${STORE}:${save?.account || ""}`;
    function keep() {
      try { sessionStorage.setItem(storeKey(), JSON.stringify(list)); } catch (e) { /* storage blocked: the list lasts as long as the page */ }
    }
    function restore() {
      try { list = S.fromSaveJson(JSON.parse(sessionStorage.getItem(storeKey()) || "null")); } catch (e) { list = S.emptyList(); }
    }
    // After any change to the list: what shows it follows, in place (the cat's boxes keep focus and Tab).
    function listChanged() {
      keep();
      refreshCat();
      drawCarry();
      drawPending();
      for (const [draw, node] of leaves) { if (node.isConnected) draw(); else leaves.delete(draw); }
      out.set(S.toSaveJson(list));
    }
    // A typed value, checked against the range the game takes; true when it went in the list.
    function setChecked(path, value) {
      const why = S.rangeProblem(path, value, save.ranges);
      if (why) { toast(why, "bad"); return false; }
      S.setValue(list, data, path, value);
      listChanged();
      return true;
    }

    // ---------- Your cat ----------
    const catFields = [];
    function drawCat() {
      catFields.length = 0;
      const P = `${slot}/GameplayProgression`;
      clear(catCard).append(el("h2", { text: cap(G.catInGame(game())) }));
      if (!S.getPath(data, P)) {
        catCard.append(el("p", { class: "note", text: "This cat hasn't started yet: play once, then come back." }));
        return;
      }
      const row = el("div", { class: "row cat-fields" });
      for (const [label, path] of [["Level", `${P}/Level`], ["Experience", `${P}/Experience`], ["Fresh-kill pile", `${P}/FreshKill/Value`]]) {
        if (typeof S.getPath(data, path) !== "number") continue;
        row.append(numberField(label, path));
      }
      // The herbs by the names the game gives them (Horsetail Stalks, ...), from its item table when it can be read.
      const herbs = S.HERBS.map(t => items.names[t] || S.itemWords(t));
      catCard.append(row,
        el("div", { class: "row presets" }, el("span", { class: "lbl", text: "Quick" }),
          presetButton("Max level", "max-level", "Level 20, experience 0. Your rank stays as it is: promotions come from the rank-up quests.",
            "Your cat is at level 20 already."),
          presetButton("Fill the fresh-kill pile", "fill-pile", "The pile to 100, the most it holds.", "The fresh-kill pile is already full."),
          presetButton("Give herbs", "give-herbs", `Five more of each of ${S.andList(herbs)}.`, "Your cat can't carry anything yet.")),
        el("p", { class: "muted", text: "These only add to the list of changes below. Nothing changes in your save until you say so." }));
    }
    function numberField(label, path) {
      const id = nextId(), range = S.rangeFor(path, save.ranges);
      const inp = el("input", { type: "number", id, step: range.whole ? "1" : "any", min: range.min ?? false, max: range.max ?? false, style: { width: "8rem" } });
      const was = el("span", { class: "was" });
      const refresh = () => {
        const now = S.after(list, data, path), orig = S.getPath(data, path);
        if (document.activeElement !== inp) inp.value = String(now ?? "");
        was.textContent = path in list.set ? `in your save now: ${orig}` : "";
      };
      inp.addEventListener("change", () => {
        const v = inp.value.trim() === "" ? NaN : Number(inp.value);
        if (!Number.isFinite(v)) { toast(`${label}: use a number`, "bad"); refresh(); return; }
        if (!setChecked(path, v)) { inp.value = String(S.after(list, data, path)); }
      });
      catFields.push(refresh);
      refresh();
      return el("div", { class: "field" }, el("label", { for: id, text: label }), inp, was);
    }
    // already: what the toast says when the preset changes nothing (the save has it already).
    function presetButton(text, name, what, already) {
      return el("button", { class: "btn small", type: "button", title: what, "aria-description": what, onclick: () => {
        const before = JSON.stringify(list);
        S.preset(name, list, data, slot);
        if (JSON.stringify(list) === before) { toast(already); return; }
        listChanged();
        toast(`${text}: added to the changes to make. Change my save now makes them.`);
      } }, text);
    }
    function refreshCat() { for (const fn of catFields) fn(); }

    // ---------- What it carries ----------
    const KIND_GROUPS = [["consumable", "Herbs"], ["material", "Materials"], ["accessory", "Accessories"]];
    // The card is drawn again only when its rows change (an item added or taken out); a new count updates its
    // row in place, so the box keeps focus and Tab goes on to the next one. Each row's parts are keyed by the
    // item (ids and data-focus), so after a redraw focus comes back to the same item's box or button.
    let carryShape = null;
    const carryRows = [];   // each row's update: its count and "in your save now"
    function drawCarry() {
      const inv = `${slot}/GameplayProgression/State/Inventory`;
      const has = S.getPath(data, inv);
      const added = list.add[inv] || {};
      const tags = has && typeof has === "object"
        ? [...new Set([...Object.keys(has), ...Object.keys(added)])].sort((a, b) => S.describe(`${inv}/${a}`, say).localeCompare(S.describe(`${inv}/${b}`, say)))
        : [];
      const gone = list.remove.filter(p => p.startsWith(`${inv}/`));
      const shape = JSON.stringify([inv, !!has, tags, gone, items.problem, items.list.length]);
      if (shape === carryShape) { for (const fn of carryRows) fn(); return; }
      carryShape = shape;
      carryRows.length = 0;
      clear(carryCard).append(el("h2", { text: "What it carries" }));
      if (!has || typeof has !== "object") { carryCard.hidden = true; return; }
      carryCard.hidden = false;
      const rows = el("div", { class: "carry" });
      for (const tag of tags) {
        const path = `${inv}/${tag}`;
        if (list.remove.includes(path)) continue;
        const name = items.names[tag] || S.itemWords(tag), id = `save-carry-${tag}`;
        const icon = el("img", { class: "item-icon-small", alt: "", width: "28", height: "28", hidden: true });
        if (!items.problem && items.names[tag]) api.image(`/game/icon?of=${encodeURIComponent(tag)}`).then(u => { icon.src = u; icon.hidden = false; }).catch(() => {});
        const inp = el("input", { type: "number", id, min: "0", step: "1", style: { width: "6rem" } });
        const note = el("span", { class: "muted" });
        const update = () => {
          const now = S.after(list, data, path), was = S.getPath(data, path);
          if (document.activeElement !== inp) inp.value = String(now ?? 0);
          note.textContent = was === undefined ? "new" : now !== was ? `in your save now: ${was}` : "";
        };
        inp.addEventListener("change", () => {
          const v = Number(inp.value);
          if (inp.value.trim() === "" || !Number.isFinite(v)) { toast(`${name}: use a number`, "bad"); inp.value = String(S.after(list, data, path) ?? 0); return; }
          const why = S.rangeProblem(path, v, save.ranges);
          if (why) { toast(why, "bad"); inp.value = String(S.after(list, data, path) ?? 0); return; }
          if (S.getPath(data, path) === undefined) S.addKey(list, data, inv, tag, v); else S.setValue(list, data, path, v);
          listChanged();
        });
        carryRows.push(update);
        update();
        rows.append(el("div", { class: "row carry-row", "data-key": `carry:${tag}` }, icon,
          el("label", { for: id, text: name }), note,
          el("span", { style: { flex: "1" } }), inp,
          el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove ${name}`, "data-focus": `carry-out:${tag}`,
            onclick: () => { S.removeKey(list, data, path); listChanged(); } })));
      }
      for (const path of gone) {
        const tag = path.slice(inv.length + 1);
        rows.append(el("div", { class: "row carry-row gone", "data-key": `carry:${tag}` }, el("span", { text: `${S.describe(path, say)}: taken out` }),
          el("button", { class: "btn ghost small", type: "button", text: "Keep it", "data-focus": `carry-out:${tag}`,
            onclick: () => { S.forget(list, { kind: "remove", path }); listChanged(); } })));
      }
      carryCard.append(tags.length ? rows : el("p", { class: "muted", text: "Your cat isn't carrying anything." }));
      // Add: the game's items by name, grouped.
      if (items.problem) {
        carryCard.append(el("p", { class: "note", text: `Can't list items to add: ${items.problem}.` }));
        return;
      }
      const pick = el("select", { id: "save-add-item", "aria-label": "Item to add" });
      for (const [kind, title] of KIND_GROUPS) {
        const choices = items.list.filter(i => i.kind === kind && !(i.tag in has) && !(i.tag in added));
        if (choices.length) pick.append(el("optgroup", { label: title }, ...choices.map(i => el("option", { value: i.tag, text: i.name }))));
      }
      const qty = el("input", { type: "number", id: "save-add-qty", min: "1", step: "1", value: "1", style: { width: "5rem" }, "aria-label": "How many" });
      if (pick.querySelector("option")) {
        carryCard.append(el("div", { class: "row" }, el("span", { class: "lbl", text: "Add" }), pick, qty,
          el("button", { class: "btn small", type: "button", id: "save-add", text: "Add to the list", onclick: () => {
            const n = Number(qty.value);
            const why = S.rangeProblem(`${inv}/${pick.value}`, n, save.ranges) || (n < 1 ? "Add at least one" : null);
            if (why) return toast(why, "bad");
            S.addKey(list, data, inv, pick.value, n);
            listChanged();
          } })));
      }
    }

    // ---------- Changes to make ----------
    // A list's heading for a game's changes: "Your 5th game: Sharppaw", the one chosen above said so; the game's
    // settings are every game's.
    const gameHead = (at, chosen = true) => at === null ? "The game's settings, for every game"
      : `${G.gameTitle(G.gameOf(games, at))}${chosen && at === slot ? " (the game chosen above)" : ""}`;
    // A button's words name the game too while the save has more than one (two may have a cat called Sharppaw).
    const inGame = at => (games.length > 1 && at !== null ? ` in ${G.gameWords(at)}` : "");
    function drawPending() {
      const changes = S.entries(list, data, say);
      clear(pendingCard).append(el("h2", { text: "Changes to make" }));
      if (!changes.length) {
        pendingCard.append(el("p", { class: "muted", text: "Nothing yet. Change a number above, press a quick button, or add something your cat carries." }));
      } else {
        // Each game's changes under its name, so changes to two games (two cats called Sharppaw) are told apart.
        for (const [at, inIt] of G.byGame(changes)) {
          const ul = el("ul", { class: "changes", "data-slot": at ?? "every" });
          for (const c of inIt) {
            const words = `${c.label}: ${S.said(c.was)} -> ${c.kind === "remove" ? "taken out" : S.said(c.now)}`;
            ul.append(el("li", { class: "row" }, el("span", { text: words }),
              el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove ${c.label}${inGame(at)} from the list`,
                onclick: () => { S.forget(list, c); listChanged(); } })));
          }
          pendingCard.append(el("h3", { class: "game-head", text: gameHead(at) }), ul);
        }
      }
      const go = el("button", { class: "btn primary", id: "save-now", type: "button", text: "Change my save now", disabled: !changes.length || !!save?.game_running });
      go.addEventListener("click", changeNow);
      pendingCard.append(el("div", { class: "row" }, go,
        el("span", { class: "muted", text: "A copy of your save is kept first (Settings and repair), and each change can be put back." })),
        shareFold);
    }
    async function changeNow() {
      const go = pendingCard.querySelector("#save-now");
      if (go) go.disabled = true;
      try {
        const where = G.byGame(S.entries(list, data, say)).map(([at]) => (at === null ? "the game's settings" : G.gameWords(at)));
        const r = await api.post("/save/apply", { changes: S.toChanges(list) });
        list = S.emptyList();
        keep();
        const when = new Date().toTimeString().slice(0, 5);
        toast(`Done at ${when}: ${r.applied.length} change${r.applied.length === 1 ? "" : "s"} made, in ${S.andList(where)}. A copy of your save from before is in Settings and repair.`);
        wc.announce(`Done at ${when}.`);
        await reload();
      } catch (e) {
        toast(e.message, "bad");
        if (go) go.disabled = false;
      }
    }
    // The share fold's mod: what its save.json changes, in words. mods: the mod list, when read afresh.
    function drawModFile(mods = target.mods) {
      clear(modWords);
      // Whether the mod is on: if it is, its changes go in your own save too at the next Apply.
      const mod = mods.find(m => m.id === target.current);
      if (mod?.enabled && modFile && !S.isEmpty(modFile)) {
        modWords.append(el("p", { class: "banner", id: "save-share-on", text: `${mod.name} is on: the next Apply makes its changes in your own save too, once. Turn it off on the Mods page if it's only to share.` }));
      }
      if (!modFile || S.isEmpty(modFile)) { modWords.append(el("p", { class: "muted", text: "This mod has no save changes yet." })); return; }
      modWords.append(el("p", { class: "lbl", text: "In this mod's save.json now:" }),
        el("ul", { class: "changes" }, ...S.entries(modFile, data || {}, say).map(c => {
          const at = G.slotOfPath(c.path), game = at === null ? "Every game" : cap(G.gameWords(at));
          return el("li", { text: `${game}: ${c.label}: ${c.kind === "remove" ? "taken out" : S.said(c.now)}` });
        })),
        el("button", { class: "btn small", type: "button", text: "Copy these into my list", onclick: () => {
          for (const c of S.entries(modFile, data || {}, say)) {
            if (c.kind === "remove") S.removeKey(list, data, c.path);
            else if (c.kind === "add") S.addKey(list, data, c.path.slice(0, c.path.lastIndexOf("/")), c.path.slice(c.path.lastIndexOf("/") + 1), c.now);
            else S.setValue(list, data, c.path, c.now);
          }
          listChanged();
        } }));
    }

    // ---------- Done so far ----------
    async function drawDone() {
      let changes = [];
      try { changes = (await api.get("/save/applied")).changes; } catch (e) { /* said by the save's own card */ }
      const modName = id => id === "studio" ? "this page" : (target.mods.find(m => m.id === id) || {}).name || id;
      clear(doneCard).append(el("h2", { text: "Done so far" }));
      if (!changes.length) {
        doneCard.append(el("p", { class: "muted", text: "Nothing changed in this save yet, by this page or by a mod." }));
        return;
      }
      for (const [at, inIt] of G.byGame(changes)) {
        const ul = el("ul", { class: "changes done", "data-slot": at ?? "every" });
        for (const c of inIt) {
          const when = (c.when || "").replace("T", " ").slice(0, 16);
          const line = el("li", { class: "stack", "data-key": `done:${c.source}:${c.path}` });
          const what = c.before ? `${c.label}: ${S.said(c.value)}` : `${c.label}: ${S.said(c.was)} -> ${c.op === "remove" ? "taken out" : S.said(c.value)}`;
          const tail = c.undone ? `put back ${c.undone.replace("T", " ").slice(0, 16)}` : c.before ? "made before this version kept a record, so it can't be put back here" : when;
          const head = el("div", { class: "row" }, el("span", { text: what }), el("span", { class: "muted", text: `(${modName(c.source)}, ${tail})` }));
          line.append(head);
          if (c.can_undo) {
            const ask = el("div", { class: "row", hidden: true });
            const back = el("button", { class: "btn small", type: "button", text: "Put it back", "aria-label": `Put back ${c.label}${inGame(at)}` });
            const moved = !(c.op === "remove" ? c.current === null : JSON.stringify(c.current) === JSON.stringify(c.value));
            back.addEventListener("click", () => {
              if (!moved) return putBack(c, back);
              clear(ask).append(el("span", { text: `${c.label} is ${S.said(c.current)} now; putting it back makes it ${S.said(c.was)}.` }),
                el("button", { class: "btn small danger", type: "button", text: "Put it back anyway", onclick: () => putBack(c, back) }),
                el("button", { class: "btn small ghost", type: "button", text: "Keep it", onclick: () => { ask.hidden = true; back.focus(); } }));
              ask.hidden = false;
              wc.announce(ask.textContent);
              ask.querySelector("button").focus();
            });
            head.append(back);
            line.append(ask);
          }
          ul.append(line);
        }
        doneCard.append(el("h3", { class: "game-head", text: gameHead(at, false) }), ul);
      }
    }
    async function putBack(c, button) {
      button.disabled = true;
      try {
        const r = await api.post("/save/undo", { source: c.source, path: c.path });
        toast(`Put back: ${r.label} is ${S.said(r.now)} again. A copy of your save from before is in Settings and repair.`);
        await reload();
      } catch (e) {
        toast(e.message, "bad");
        button.disabled = false;
      }
    }

    // ---------- Advanced: the whole save ----------
    const leaves = new Map();   // a row's draw -> its row: its "in the list" mark drawn again (the tree isn't rebuilt for a change)
    const openPaths = new Set();
    function leaf(value, path, label) {
      const id = nextId();
      const lockedWhy = S.readOnly(path, value);
      const box = el("div", { class: "row leaf" }, el("label", { for: id, class: "mono", text: label, title: path }));
      if (value === null || lockedWhy) {
        box.append(el("span", { id, class: "mono value", text: value === null ? "empty" : S.said(value) }),
          el("span", { class: "muted", text: value === null ? "empty: nothing to change here" : lockedWhy }));
        return box;
      }
      let control;
      if (typeof value === "boolean") {
        control = el("input", { type: "checkbox", id });
        control.addEventListener("change", () => { S.setValue(list, data, path, control.checked); listChanged(); });
      } else if (typeof value === "number") {
        const range = S.rangeFor(path, save.ranges);
        control = el("input", { type: "number", id, step: "any", min: range.min ?? false, max: range.max ?? false, style: { width: "10rem" } });
        control.addEventListener("change", () => {
          const v = control.value.trim() === "" ? NaN : Number(control.value);   // as typed: no rounding
          if (!Number.isFinite(v)) { toast("Use a number", "bad"); draw(); return; }
          if (!setChecked(path, v)) draw();
        });
      } else {
        control = el("input", { type: "text", id, style: { width: "min(100%, 34rem)" } });
        control.addEventListener("change", () => { S.setValue(list, data, path, control.value); listChanged(); });
      }
      const mark = el("span", { class: "chip warn", hidden: true }, el("i"), "in the list");
      const draw = () => {
        const now = S.after(list, data, path);
        if (document.activeElement !== control) {
          if (typeof value === "boolean") control.checked = !!now; else control.value = now ?? "";
        }
        mark.hidden = !(path in list.set);
      };
      leaves.set(draw, box);
      draw();
      box.append(control, mark);
      return box;
    }
    function group(value, path, label) {
      const keys = Object.keys(value);
      // A game's own group (the save's "4") says which game it is: "your 5th game: Sharppaw".
      const whose = /^\d+$/.test(path) ? el("span", { class: "game-of", text: `  ${G.gameTitle(G.gameOf(games, path))}${path === slot ? ", the game chosen above" : ""}` }) : null;
      const d = el("details", { "data-path": path }, el("summary", {}, el("span", { class: "mono", text: label }), whose,
        el("span", { class: "muted", text: `  ${Array.isArray(value) ? "list" : "group"} · ${keys.length}` })));
      let shown = 0;
      const box = el("div", { class: "tree-kids" });
      const more = el("button", { class: "btn small ghost", type: "button" });
      const showMore = () => {
        for (const k of keys.slice(shown, shown + SHOW)) box.append(node(value[k], path ? `${path}/${k}` : k, k));
        shown = Math.min(keys.length, shown + SHOW);
        more.hidden = shown >= keys.length;
        more.textContent = `Show ${Math.min(SHOW, keys.length - shown)} more of ${keys.length}`;
      };
      more.addEventListener("click", showMore);
      d.addEventListener("toggle", () => {
        if (d.open) openPaths.add(path); else openPaths.delete(path);
        if (!d.open || shown) return;
        d.append(box, more);
        showMore();
      });
      if (openPaths.has(path)) d.open = true;
      return d;
    }
    const node = (value, path, label) => value && typeof value === "object" ? group(value, path, label) : leaf(value, path, label);
    function drawTree() {
      leaves.clear();
      const find = el("input", { type: "search", id: "save-find", placeholder: "Level, Inventory, Minimap…", "aria-label": "Find in your save" });
      const found = el("div", { class: "stack", id: "save-found" });
      find.addEventListener("input", () => {
        const q = find.value.trim().toLowerCase();
        clear(found);
        if (q.length < 2) return;
        const hits = [];
        const walk = (v, p) => {
          if (hits.length >= 60) return;
          if (v && typeof v === "object") { for (const k of Object.keys(v)) walk(v[k], p ? `${p}/${k}` : k); return; }
          if (p.toLowerCase().includes(q) || S.describe(p, say).toLowerCase().includes(q)) hits.push([v, p]);
        };
        walk(data, "");
        for (const [v, p] of hits) found.append(el("div", { class: "stack hit" }, el("span", { class: "muted", text: S.describe(p, say) }), leaf(v, p, p)));
        if (!hits.length) found.append(el("p", { class: "muted", text: "Nothing in your save is called that." }));
        else if (hits.length >= 60) found.append(el("p", { class: "muted", text: "The first 60; type more to narrow it." }));
      });
      openPaths.add("");
      clear(treeBox).append(el("h3", { text: "Everything in your save" }),
        el("p", { class: "note", text: "Open a group to see its values; a change goes in the list of changes to make. Key bindings and cats' records are shown, not changed: their own pages change them." }),
        el("label", { class: "field" }, el("span", { class: "lbl", text: "Find in your save" }), find), found,
        group(data, "", "your save"));
    }
    function drawStats() {
      const path = `${slot}/GameplayProgression/Stats`;
      const orig = S.getPath(data, path);
      clear(statsBox);
      if (typeof orig !== "string") return;
      const fields = Object.keys(S.readStats(orig)).map(k => {
        const id = nextId();
        const inp = el("input", { type: "number", id, step: "any", value: String(S.readStats(S.after(list, data, path))[k]), style: { width: "6.5rem" } });
        inp.addEventListener("change", () => {
          const v = Number(inp.value);
          if (inp.value.trim() === "" || !Number.isFinite(v)) { toast(`${k}: use a number`, "bad"); inp.value = String(S.readStats(S.after(list, data, path))[k]); return; }
          S.setValue(list, data, path, S.writeStat(S.after(list, data, path), k, v));
          listChanged();
        });
        return el("div", { class: "field" }, el("label", { for: id, text: k }), inp);
      });
      statsBox.append(el("div", { class: "card inner" }, el("h3", { text: `Combat stats, ${G.gameWords(slot)}` }),
        el("p", { class: "note", text: "When a fight starts the game works out stats from your cat's level, so a change here may not last." }),
        el("div", { class: "row" }, ...fields)));
    }

    // ---------- start, and after a change ----------
    function drawAll() {
      carryShape = null;   // the save was read again: every row is drawn anew
      drawCat(); drawCarry(); drawPending(); drawTree(); drawStats(); drawModFile();
      out.set(S.toSaveJson(list));
    }
    async function reload() {
      if (!await load()) return;
      drawAll();
      await drawDone();
    }
    async function start() {
      if (!await load()) { root.dataset.ready = "true"; return; }
      restore();
      await loadItems();
      drawAll();
      await target.refresh().catch(() => { /* the bar says */ });
      await drawDone();
      root.dataset.ready = "true";   // for the end-to-end tests: everything the page reads at the start is in
    }
    // After an Apply a mod's save changes may have been made: the save and Done so far are read again (the list
    // of changes to make stays).
    const off = wc.installedEvent(target, () => reload());
    const offFocus = wc.bus.on("focus", async () => {
      try { running((await api.get("/changes")).game_running); } catch (e) { /* the shell says */ }
    });
    // Turned on or off (on the Mods page, say): the share fold says so, from the list as it is now (the bar reads
    // it again too, but after this hears the news).
    const offMods = wc.bus.on("mods-changed", async () => {
      try { drawModFile(await api.get("/mods")); } catch (e) { /* the bar says */ }
    });
    // Leaving the studio with changes still in the list: the browser asks first.
    const beforeUnload = e => { if (!S.isEmpty(list)) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", beforeUnload);
    await start();
    return { unmount() { off(); offFocus(); offMods(); window.removeEventListener("beforeunload", beforeUnload); } };
  },
};
