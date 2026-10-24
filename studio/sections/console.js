// Console: run Lua in the running game through the bridge (wcmods/bridge.py), and look inside the game's
// objects. Only shown with "allow_code_mods": true, because it runs code in the game.
const EXAMPLES = [
  ["Your cat", "local c = Game.cat()\nreturn { name = c:name(), level = c:level(), health = c:health(), stats = c:stats(), traits = c:traits() }"],
  ["Time of day", "return Game.time.get()"],
  ["Set 6:00", "return Game.time.set(6, 0)"],
  ["Fresh-kill", "return Game.freshKill.value(), Game.freshKill.level()"],
  ["Items", "return Game.items.list()"],
  ["Nearby animals", "local World = require(\"WCModsWorld\")\nlocal out = {}\nfor i, it in ipairs(World.nearby(\"creatures\", 5000)) do\n  out[i] = string.format(\"%s %.0f m\", it.label, it.distance / 100)\nend\nreturn out"],
  ["The fight", "local f = Game.fight()\nif not f then return \"no fight\" end\nlocal out = {}\nfor _, x in ipairs(f:all()) do out[#out + 1] = { kind = x:cat():kind(), level = x:level(), stats = x:stats() } end\nreturn out"],
];

export default {
  title: "Console",
  async mount(root, wc) {
    const { el, api, clear, toast } = wc;
    const status = el("span", { class: "chip" }, el("i"), "…");
    const code = el("textarea", { id: "con-code", spellcheck: false, placeholder: "Game.cat():name()", style: { minHeight: "140px" } });
    const log = el("pre", { class: "log", style: { whiteSpace: "pre-wrap" } });
    const runBtn = el("button", { class: "btn primary", text: "Run (Ctrl+Enter)" });
    const expr = el("input", { type: "text", id: "con-expr", value: "Game.player()", style: { width: "100%" } });
    const filter = el("input", { type: "search", id: "con-filter", placeholder: "filter by name", style: { width: "16rem" } });
    const view = el("div");
    let lastInfo = null;

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Scripting" }),
        el("h1", { text: "Console" }),
        el("p", { class: "note", text: "Runs Lua in the running game, with WCModsGame as Game (docs/scripting.md). An expression shows its value; print shows too. Globals you set stay for the next run. It needs the game running after an install with code mods allowed." })),
      el("div", { class: "card" },
        el("div", { class: "row spread" }, el("strong", { text: "Lua" }), status),
        el("div", { class: "row", style: { flexWrap: "wrap", gap: "6px" } },
          ...EXAMPLES.map(([label, text]) => el("button", { class: "btn", text: label, onclick: () => { code.value = text; code.focus(); } }))),
        code,
        el("div", { class: "actions" }, runBtn, el("button", { class: "btn", text: "Clear output", onclick: () => clear(log) })),
        el("div", { class: "code" }, log)),
      el("div", { class: "card" },
        el("strong", { text: "Inspector" }),
        el("p", { class: "note", text: "A Lua expression for an object: Game.player(), Game.manager(\"quests\"), Game.gameState(). Click an object's property to look inside it." }),
        el("div", { class: "field" }, el("label", { for: "con-expr", text: "Object" }), expr),
        el("div", { class: "actions" }, el("button", { class: "btn primary", text: "Inspect", onclick: () => inspect() }), filter),
        view));

    function line(text, cls) {
      log.append(el("div", { class: cls || false, text }));
      log.parentElement.scrollTop = log.parentElement.scrollHeight;
    }

    async function run() {
      const text = code.value.trim();
      if (!text) return;
      line("> " + text.split("\n").join("\n  "), "muted");
      runBtn.disabled = true;
      try {
        const r = await api.post("/game/lua", { code: text });
        if (r.output) line(r.output);
        if (r.ok) {
          const res = r.result || [];
          if (res.length) line("= " + JSON.stringify(res.length > 1 ? res : res[0], null, 2));
          line(`(${r.ms} ms)`, "muted");
        } else {
          line("error: " + r.error);
        }
      } catch (e) {
        line("error: " + e.message);
      } finally {
        runBtn.disabled = false;
      }
    }
    runBtn.addEventListener("click", run);
    code.addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); } });

    async function inspect() {
      clear(view).append(el("p", { class: "muted", text: "Asking the game…" }));
      try {
        const r = await api.post("/game/inspect", { expr: expr.value });
        if (!r.ok) throw new Error(r.error);
        lastInfo = (r.result || [])[0] || {};
        if (lastInfo.error) throw new Error(lastInfo.error);
        render();
      } catch (e) {
        clear(view).append(el("p", { class: "note", text: e.message }));
      }
    }
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
          return el("tr", {}, el("td", {}, name), el("td", { class: "muted", text: p.type.replace(/Property$/, "") }),
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

    async function poll() {
      try {
        const st = await api.get("/game/bridge");
        const live = st.alive;
        status.className = `chip ${live ? "good" : "warn"}`;
        clear(status).append(el("i"), live
          ? `Game running: ${st.world || "loading"}${st.player ? ", your cat is in" : ""}`
          : st.never ? "The bridge hasn't run yet: install, then start the game" : "Game not running");
      } catch (e) { /* the studio itself is down; the status bar says so */ }
    }
    poll();
    const timer = setInterval(poll, 3000);
    return { unmount() { clearInterval(timer); } };
  },
};
