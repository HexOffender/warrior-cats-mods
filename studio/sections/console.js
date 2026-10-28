// Try Lua in the game (the "console" page): for people who write scripts. It types a line of Lua into the running
// game through the bridge (wcmods/bridge.py) and shows what it printed and returned, and looks inside the game's
// objects. Nothing here is saved into a mod. Listed only with mods that run code allowed, under Advanced.
// The status strip's words are the server's (/game/bridge's `said`, from studio.BRIDGE_SAID), so the strip and
// what a refused Run says are one sentence each.

// The examples: a label, the Lua, and, where a page does the same without code, which one.
export const EXAMPLES = [
  { label: "Your cat", code: "local c = Game.cat()\nreturn { name = c:name(), level = c:level(), health = c:health(), stats = c:stats(), traits = c:traits() }",
    instead: "The Save page changes these without code." },
  { label: "Time of day", code: "return Game.time.get()" },
  { label: "Set 6:00", code: "return Game.time.set(6, 0)",
    instead: "The mod menu's World page (in the game) sets and holds the time without code." },
  { label: "Fresh-kill", code: "return Game.freshKill.value(), Game.freshKill.level()",
    instead: "The Save page changes the pile without code." },
  { label: "Items", code: "return Game.items.list()" },
  { label: "The fight", code: "local f = Game.fight()\nif not f then return \"no fight\" end\nlocal out = {}\nfor _, x in ipairs(f:all()) do out[#out + 1] = { kind = x:cat():kind(), level = x:level(), stats = x:stats() } end\nreturn out" },
];
// (No example scans the world, World.nearby or Game.findAll: reading many objects through the bridge has crashed
// the game just after a level loads. The mod menu's own Nearby page lists what's around.)

// A value the game sent back, as text: nil as nil, a string or number as it is, a table as an indented list of
// "key: value" lines. The bridge writes nil as the string "nil", and an empty Lua table as {} or [].
export function show(v, indent = "") {
  if (v === null || v === undefined || v === "nil") return "nil";
  if (typeof v !== "object") return String(v);
  const entries = Array.isArray(v) ? v.map((x, i) => [i + 1, x]) : Object.entries(v);
  if (!entries.length) return "(empty)";
  return entries.map(([k, x]) => {
    const deep = x && typeof x === "object" && (Array.isArray(x) ? x.length : Object.keys(x).length);
    return `${indent}${k}: ${deep ? "\n" + show(x, indent + "  ") : show(x)}`;
  }).join("\n");
}

// The box's text with `text` put in at `at` (the cursor), on a line of its own: what's typed is kept. Gives the
// new text and where the cursor goes, after what was put in.
export function insertAt(value, text, at = value.length) {
  if (!value.trim()) return { value: text, caret: text.length };
  const before = value.slice(0, at), after = value.slice(at);
  const pre = before && !before.endsWith("\n") ? "\n" : "";
  const post = after && !after.startsWith("\n") ? "\n" : "";
  return { value: before + pre + text + post + after, caret: (before + pre + text).length };
}

export default {
  title: "Try Lua in the game",
  async mount(root, wc) {
    const { el, api, clear, toast, bus } = wc;
    const strip = el("div", { class: "strip", role: "status" }, el("i", { "aria-hidden": "true" }), el("span", { text: "Asking the game…" }));
    const code = el("textarea", { id: "con-code", spellcheck: "false", "aria-label": "Lua to run", placeholder: "Game.cat():name()",
      "aria-describedby": "con-keys", style: { minHeight: "140px" } });
    const out = el("div", { class: "con-out", role: "log", "aria-label": "What the game said" });
    const outBox = el("div", { class: "code", tabindex: "0" }, out);
    const runBtn = el("button", { class: "btn primary", text: "Run", disabled: true });
    const expr = el("input", { type: "text", id: "con-expr", value: "Game.player()", style: { width: "100%" } });
    const inspectBtn = el("button", { class: "btn primary", text: "Inspect", disabled: true });
    const everything = el("input", { type: "checkbox", id: "con-all" });
    const filter = el("input", { type: "search", id: "con-filter", "aria-label": "Filter by name", placeholder: "filter by name", style: { width: "16rem" } });
    const view = el("div");
    let state = null, said = "", lastInfo = null, polling = false;
    const busy = new Set();   // the buttons whose request is under way: they stay off until it's back
    const history = [];   // lines run, oldest first, for Ctrl+Up and Ctrl+Down
    let back = 0, draft = "";

    root.append(
      wc.pageHead({ eyebrow: "Advanced", title: "Try Lua in the game", help: "help:console",
        lede: "For people who write scripts: this types a line of Lua into the running game and shows what comes back. Nothing here is saved into a mod. To change the game without code, use the Make pages." }),
      strip,
      el("div", { class: "card" },
        el("h2", { text: "Run a line" }),
        el("div", { class: "row", role: "group", "aria-label": "Try one" }, el("span", { class: "lbl", text: "Try one:" }),
          ...EXAMPLES.map(x => el("button", { class: "btn small", type: "button", text: x.label, "aria-label": `Try one: ${x.label}`, onclick: () => example(x) }))),
        code,
        el("p", { class: "note", id: "con-keys", text: "Ctrl+Enter runs it; Ctrl+Up and Ctrl+Down go back through the lines you ran. An expression shows its value, print() shows too, and globals you set stay for the next line (until the game closes). Game is WCModsGame." }),
        el("div", { class: "row" }, runBtn, el("button", { class: "btn", type: "button", text: "Clear what it said", onclick: () => clear(out) })),
        outBox),
      el("div", { class: "card" },
        el("h2", { text: "Look inside an object" }),
        el("p", { class: "note", text: "A Lua expression for one of the game's objects: Game.player(), Game.manager(\"quests\"), Game.gameState(). Press a property that's an object to look inside it." }),
        el("div", { class: "field" }, el("label", { for: "con-expr", text: "Object" }), expr),
        el("div", { class: "row" }, inspectBtn,
          el("label", { class: "row", for: "con-all" }, everything, "Show the engine's own members too"), filter),
        view));

    // ---------- whether the game can hear the studio ----------
    function setState(st) {
      state = st.state;
      said = st.said || "";
      strip.className = `strip ${state || ""}`;
      clear(strip).append(el("i", { "aria-hidden": "true" }), el("span", { text: said }));
      const listening = state === "listening";
      for (const b of [runBtn, inspectBtn]) {
        if (!busy.has(b)) b.disabled = !listening;
        b.title = listening ? "" : said;
      }
    }
    // Only while the page shows: the shell hides a page another page is open over, and only takes it down when it
    // leaves the side bar.
    async function poll() {
      if (root.hidden || polling) return;
      polling = true;
      try { setState(await api.get("/game/bridge")); }
      catch (e) { /* the studio itself is down: the top bar says so */ }
      finally { polling = false; }
    }

    // ---------- run a line ----------
    function line(text, cls) {
      out.append(el("div", { class: cls || false, text }));
      outBox.scrollTop = outBox.scrollHeight;
    }
    // What was typed is kept, the example going in on a line of its own; another example still as it was is replaced
    // (two examples in one box wouldn't run: a return has to be the last thing).
    function example(x) {
      const typed = code.value.trim() && !EXAMPLES.some(e => e.code === code.value.trim());
      const r = typed ? insertAt(code.value, x.code, code.selectionEnd ?? code.value.length) : { value: x.code, caret: x.code.length };
      code.value = r.value;
      code.focus();
      code.setSelectionRange(r.caret, r.caret);
      back = 0;
    }
    async function run() {
      const text = code.value.trim();
      if (!text || busy.has(runBtn)) return;
      if (state !== "listening") { toast(said || "The game isn't listening", "bad"); return; }
      if (history[history.length - 1] !== text) history.push(text);
      back = 0;
      line("> " + text.split("\n").join("\n  "), "muted");
      const x = EXAMPLES.find(e => e.code === text);
      busy.add(runBtn);
      runBtn.disabled = true;
      try {
        const r = await api.post("/game/lua", { code: text });
        if (r.output) line(r.output);
        if (r.ok) {
          const res = r.result || [];
          if (res.length) line(res.map(v => show(v)).join("\n"));
          line(`${r.ms} ms`, "con-ms");
          if (x && x.instead) line(x.instead, "con-note");
        } else {
          line(r.error, "bad");
        }
      } catch (e) {
        line(e.message, "bad");
        poll();
      } finally {
        busy.delete(runBtn);
        runBtn.disabled = state !== "listening";
      }
    }
    runBtn.addEventListener("click", run);
    code.addEventListener("keydown", e => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); return; }
      if (!(e.ctrlKey || e.metaKey) || (e.key !== "ArrowUp" && e.key !== "ArrowDown") || !history.length) return;
      e.preventDefault();
      if (e.key === "ArrowUp") {
        if (back === 0) draft = code.value;
        back = Math.min(back + 1, history.length);
      } else {
        back = Math.max(back - 1, 0);
      }
      code.value = back ? history[history.length - back] : draft;
    });

    // ---------- look inside an object ----------
    async function inspect() {
      const what = expr.value.trim();
      if (!what) {
        clear(view).append(el("p", { class: "note", text: "Type something to look at, e.g. Game.player()" }));
        expr.focus();
        return;
      }
      if (state !== "listening") { toast(said || "The game isn't listening", "bad"); return; }
      clear(view).append(el("p", { class: "muted", text: "Asking the game…" }));
      busy.add(inspectBtn);
      inspectBtn.disabled = true;
      try {
        const r = await api.post("/game/inspect", { expr: what, all: everything.checked });
        if (!r.ok) throw new Error(r.error);
        lastInfo = (r.result || [])[0] || {};
        if (lastInfo.error) throw new Error(lastInfo.error);
        render();
      } catch (e) {
        clear(view).append(el("p", { class: "note bad", text: e.message }));
        poll();
      } finally {
        busy.delete(inspectBtn);
        inspectBtn.disabled = state !== "listening";
      }
    }
    inspectBtn.addEventListener("click", inspect);
    expr.addEventListener("keydown", e => { if (e.key === "Enter") inspect(); });
    filter.addEventListener("input", () => lastInfo && render());

    // The bridge writes an empty Lua table as {} (Lua can't tell it from an empty list), so a list that
    // has nothing in it, like a function's parameters, may come back as an object.
    const list = v => Array.isArray(v) ? v : [];

    function render() {
      const f = filter.value.toLowerCase();
      const info = { ...lastInfo, props: list(lastInfo.props), funcs: list(lastInfo.funcs), parents: list(lastInfo.parents) };
      const want = name => !f || name.toLowerCase().includes(f);
      const props = el("table", { class: "grid-table" },
        el("tr", {}, el("th", { text: "Property" }), el("th", { text: "Type" }), el("th", { text: "Value" })),
        ...info.props.filter(p => want(p.name)).map(p => {
          const isObject = p.type === "ObjectProperty" || p.type === "ObjectPtrProperty";
          const name = isObject
            ? el("button", { class: "chip", text: p.name, title: "Look inside", onclick: () => { expr.value = `(${expr.value}).${p.name}`; inspect(); } })
            : el("span", { text: p.name });
          return el("tr", {}, el("td", {}, name), el("td", { class: "muted", text: String(p.type).replace(/Property$/, "") }),
            el("td", { text: p.value }));
        }));
      const funcs = el("table", { class: "grid-table" },
        el("tr", {}, el("th", { text: "Function" }), el("th", { text: "From" })),
        ...info.funcs.filter(x => want(x.name)).map(x => el("tr", {},
          el("td", { text: `${x.name}(${list(x.params).join(", ")})${x.returns ? " -> " + x.returns.replace(/Property$/, "") : ""}` }),
          el("td", { class: "muted", text: x.owner }))));
      clear(view).append(
        el("p", {}, el("strong", { text: info.name })),
        el("p", { class: "note", text: info.parents.join(" < ") }),
        el("h3", { text: `Properties (${info.props.length})` }), el("div", { class: "table-wrap" }, props),
        el("h3", { text: `Functions (${info.funcs.length})` }), el("div", { class: "table-wrap" }, funcs));
    }

    await poll();
    const timer = setInterval(poll, 3000);
    const off = [bus.on("focus", () => poll()), bus.on("installed", () => poll())];
    return { poll, unmount() { clearInterval(timer); off.forEach(f => f()); } };
  },
};
