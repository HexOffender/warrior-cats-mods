// Questlines: quests of the mod's own (quests.json), step by step: talk to one of the mod's cats, pick
// things up, go somewhere; a reward at the end. The Sandbox mode mod runs them with a sandbox cat.
import { slug, listEditor, field, linesBox, wherePicker, itemChoices, itemSelect, ownItems, sandboxNote } from "../lib/story.js";

const STEP_LABEL = { talk: "Talk", collect: "Collect", visit: "Go somewhere" };
const PLACES = { "medicine-cat": "your Clan's medicine cat" };

export default {
  title: "Questlines",
  async mount(root, wc) {
    const { el, api, toast, clear } = wc;
    let quests = [], extra = {}, cats = [], own = [];
    let game = { items: [] };
    try { game = await api.get("/game/items"); } catch (e) { toast(`Couldn't read the game's items: ${e.message}`, "bad"); }
    let choices = itemChoices(game);

    const target = wc.modTarget({
      file: "quests.json",
      // The mod's cats and items first: an objective that's the one the page would write stays "auto".
      onLoad: async (obj, id) => { await loadMod(id); load(obj); draw(); },
      getValue: () => toJson(),
      onSaved: saved => wc.settleNew(quests, saved.quests),   // saved quests keep their ids from now on
    });
    const catsNote = el("div", { class: "banner", hidden: true });
    const out = wc.codePanel("quests.json");
    const editor = listEditor({
      noun: "questline", empty: "No questlines yet. Add one: a cat asks for something, you do it, and they reward you.",
      label: q => [el("strong", { text: q.title || "(no title)" }), el("span", { class: "muted", text: ` ${q.steps.length} step${q.steps.length === 1 ? "" : "s"}` })],
      add: () => {
        const title = "A new quest";
        const giver = cats[0]?.id;
        quests.push({ id: slug(title, quests.map(q => q.id), "quest"), title, giver, after: [], reward: {}, _new: true,
          steps: giver ? [{ do: "talk", npc: giver, lines: [] }] : [] });
        editor.choose(quests.length - 1);
        changed(true);
      },
    });
    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Sandbox mode" }),
        el("h1", { text: "Questlines" }),
        el("p", { class: "note", text: "Quests of your own, with your cats from the Characters page. A quest is a list of steps done in order: talk to a cat, pick things up, go somewhere. It can wait for other quests to be done first, so quests make a story. The reward is dropped at your cat's paws at the end." })),
      target.element);
    const note = await sandboxNote();
    if (note) target.element.after(note);
    root.append(catsNote, editor.element, out.element);
    await target.refresh();

    async function loadMod(id) {
      cats = []; own = [];
      for (const [file, set] of [["npcs.json", v => { cats = (v.npcs || []).filter(c => c && c.id); }],
        ["items.json", v => { own = ownItems(v); }]]) {
        try {
          const r = await api.get(`/mods/${encodeURIComponent(id)}/file/${file}`);
          if (r.exists) set(JSON.parse(r.text));
        } catch (e) { /* a new mod, or a file that isn't JSON: the Characters or Items page says */ }
      }
      choices = itemChoices(game, own);
      catsNote.hidden = cats.length > 0;
      clear(catsNote).append(el("strong", { text: "This mod has no cats yet" }),
        el("span", { text: "Talking steps and quest givers are cats of the same mod. Make some on the Characters page (with this mod chosen), then come back." }));
    }
    function load(obj) {
      extra = {};
      quests = [];
      for (const [k, v] of Object.entries(obj || {})) if (k !== "quests" && !k.startsWith("_")) extra[k] = v;
      for (const q of (obj && Array.isArray(obj.quests) ? obj.quests : [])) {
        if (!q || typeof q !== "object") continue;
        quests.push({ after: [], reward: {}, ...q, steps: (q.steps || []).map(s => ({ ...s, _auto: !s.objective || s.objective === autoObjective(s, q) })) });
      }
    }
    const catName = id => (cats.find(c => c.id === id) || {}).name || id || "someone";
    function autoObjective(s, q) {
      if (s.do === "talk") return `Talk to ${catName(s.npc || q.giver)}`;
      if (s.do === "collect") return s.item ? `Find ${choices.name(s.item)}${(s.count || 1) > 1 ? ` ×${s.count}` : ""}` : "Find something";
      if (s.do === "visit") return s.place ? `Visit ${PLACES[s.place] || s.place}` : "Go to the marked place";
      return "";
    }
    function toJson() {
      const list = quests.map(q => {
        const o = { id: q.id, title: (q.title || "").trim() || q.id };
        if (q.description && q.description.trim()) o.description = q.description.trim();
        if (q.giver) o.giver = q.giver;
        o.after = (q.after || []).filter(a => quests.some(x => x.id === a));
        o.steps = q.steps.map(s => {
          const step = { do: s.do };
          if (s.do === "talk") { step.npc = s.npc || q.giver; step.lines = s.lines || []; }
          if (s.do === "collect") { step.item = s.item; step.count = s.count || 1; }
          if (s.do === "visit") {
            if (s.place) step.place = s.place; else { step.at = s.at; if (s.level) step.level = s.level; }
            step.radius = s.radius || 400;
          }
          step.objective = !s._auto && s.objective && s.objective.trim() ? s.objective.trim() : autoObjective(s, q);
          return step;
        });
        if (Object.keys(q.reward || {}).length) o.reward = q.reward;
        return o;
      });
      return { _help: "Written by Clan Mod Studio (Questlines). This mod's questlines, which the Sandbox mode mod runs. See docs/formats.md, quests.json.", ...extra, quests: list };
    }
    // What would stop the quests going in, said beside them (saving still works; the build says it too).
    function problems(q) {
      const p = [];
      if (!q.steps.length) p.push("It has no steps yet.");
      q.steps.forEach((s, n) => {
        const at = `Step ${n + 1}`;
        if (s.do === "talk" && !(s.npc || q.giver)) p.push(`${at}: who to talk to?`);
        if (s.do === "talk" && s.npc && !cats.some(c => c.id === s.npc)) p.push(`${at}: ${s.npc} isn't one of this mod's cats any more.`);
        if (s.do === "talk" && !(s.lines || []).length) p.push(`${at}: what do they say? (at least one line)`);
        if (s.do === "collect" && !s.item) p.push(`${at}: which item?`);
        if (s.do === "visit" && !s.place && !s.at) p.push(`${at}: where? Type a spot or use where your cat is standing.`);
      });
      if (q.giver && !cats.some(c => c.id === q.giver)) p.push(`The giver, ${q.giver}, isn't one of this mod's cats any more.`);
      return p;
    }
    let showIssues = null;   // the open quest's "Not ready yet" note, said again as it changes
    function changed(redraw = false) {
      target.markDirty();
      out.set(toJson());
      if (redraw) draw();
      else showIssues?.();
    }
    function draw() {
      out.set(toJson());
      editor.render(quests, drawQuest);
    }

    function drawQuest(box, q, i) {
      const redraw = () => { clear(box); drawQuest(box, q, i); };
      const title = el("input", { type: "text", value: q.title || "", maxlength: "60", oninput: () => {
        q.title = title.value;
        if (q._new) q.id = slug(q.title, quests.filter(x => x !== q).map(x => x.id), "quest");
        changed();
      }, onchange: () => draw() });
      const desc = el("input", { type: "text", value: q.description || "", placeholder: "Optional: a sentence about it, for the Quests page",
        oninput: () => { q.description = desc.value; changed(); } });
      const giver = el("select", { "aria-label": "Quest giver", onchange: () => { q.giver = giver.value || undefined; changed(); redraw(); } },
        el("option", { value: "", text: "Nobody (it starts on its own)" }),
        ...cats.map(c => el("option", { value: c.id, text: c.name })));
      giver.value = q.giver || "";
      const others = quests.filter(x => x !== q);
      const after = others.length ? el("div", { class: "stack" }, ...others.map(o => el("label", { class: "row" },
        el("input", { type: "checkbox", checked: (q.after || []).includes(o.id), onchange: e => {
          q.after = (q.after || []).filter(a => a !== o.id).concat(e.target.checked ? [o.id] : []);
          changed();
        } }), el("span", { text: o.title || o.id }))))
        : el("p", { class: "muted", text: "It starts as soon as a sandbox cat comes into the forest. With more quests, you can make one wait for others." });

      const steps = el("ol", { class: "steps-list" });
      q.steps.forEach((s, n) => steps.append(drawStep(q, s, n, redraw)));
      const addStep = kind => {
        const s = { do: kind, _auto: true };
        if (kind === "talk") { s.npc = q.giver || cats[0]?.id; s.lines = []; }
        if (kind === "collect") s.count = 1;
        if (kind === "visit") s.radius = 400;
        q.steps.push(s);
        changed(); redraw();
      };

      const rewards = el("div", { class: "stack" });
      const drawRewards = () => {
        clear(rewards);
        for (const [tag, n] of Object.entries(q.reward || {})) {
          const count = el("input", { type: "number", min: "1", max: "99", value: n, style: { width: "5em" }, "aria-label": `How many ${choices.name(tag)}`,
            onchange: () => { q.reward[tag] = Math.max(1, Math.min(99, Math.round(Number(count.value) || 1))); changed(); } });
          rewards.append(el("div", { class: "row" }, count, el("span", { text: choices.name(tag) }),
            el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${choices.name(tag)} from the reward`,
              onclick: () => { delete q.reward[tag]; changed(); drawRewards(); } })));
        }
        const pick = itemSelect(choices, "", tag => {
          if (!tag) return;
          q.reward = { ...(q.reward || {}), [tag]: (q.reward || {})[tag] || 1 };
          changed(); drawRewards();
        }, "Add an item to the reward");
        rewards.append(el("div", { class: "row" }, el("span", { class: "lbl", text: "Add" }), pick));
      };
      drawRewards();

      const issues = el("div", { class: "banner" });
      showIssues = () => {
        const p = problems(q);
        issues.hidden = !p.length;
        issues.replaceChildren(el("strong", { text: "Not ready yet" }), el("ul", { class: "notes" }, ...p.map(t => el("li", { text: t }))));
      };
      showIssues();
      box.append(
        el("div", { class: "card" },
          field("Title", title), field("About it", desc),
          field("Quest giver", giver, "Their name gets a ! over it while the quest is waiting to be talked about."),
          el("span", { class: "muted mono", text: `id: ${q.id}` })),
        el("div", { class: "card" }, el("h3", { text: "Starts after" }), after),
        el("div", { class: "card" }, el("h3", { text: "Steps" }),
          el("p", { class: "note", text: "Done in order. The quest panel in the game shows each step's objective, with a marker on where to go." }),
          q.steps.length ? steps : el("div", { class: "empty", text: "No steps yet." }),
          el("div", { class: "row" }, el("span", { class: "lbl", text: "Add a step:" }),
            ...Object.entries(STEP_LABEL).map(([k, label]) => el("button", { class: "btn small", text: label, onclick: () => addStep(k) })))),
        el("div", { class: "card" }, el("h3", { text: "Reward" }),
          el("p", { class: "note", text: "Dropped at your cat's paws when the last step is done, to pick up." }), rewards),
        issues,
        el("div", { class: "row" },
          wc.confirmButton(`Remove ${q.title || "this quest"}`, "Press again to remove", () => {
            quests.splice(i, 1);
            for (const x of quests) x.after = (x.after || []).filter(a => a !== q.id);
            changed(true);
          }, "btn danger")));
    }

    function drawStep(q, s, n, redraw) {
      const objective = el("input", { type: "text", maxlength: "80", value: s._auto ? "" : s.objective || "", placeholder: autoObjective(s, q),
        oninput: () => { s.objective = objective.value; s._auto = !objective.value.trim(); changed(); } });
      const body = el("div", { class: "stack" });
      if (s.do === "talk") {
        const who = el("select", { "aria-label": "Who to talk to", onchange: () => { s.npc = who.value; changed(); objective.placeholder = autoObjective(s, q); } },
          ...cats.map(c => el("option", { value: c.id, text: c.name })));
        if (s.npc && !cats.some(c => c.id === s.npc)) who.append(el("option", { value: s.npc, text: `${s.npc} (not in this mod)` }));
        who.value = s.npc || q.giver || "";
        body.append(field("Who", who), field("What they say", linesBox(s.lines || [], v => { s.lines = v; changed(); },
          "One line each; G shows the next.\nThere you are! I need your help.\nCould you bring me some moss?"), "The step is done after the last line."));
      } else if (s.do === "collect") {
        const count = el("input", { type: "number", min: "1", max: "99", value: s.count || 1, style: { width: "5em" }, "aria-label": "How many",
          oninput: () => { s.count = Math.max(1, Math.min(99, Math.round(Number(count.value) || 1))); changed(); objective.placeholder = autoObjective(s, q); } });
        const item = itemSelect(choices, s.item, v => { s.item = v; changed(); objective.placeholder = autoObjective(s, q); });
        body.append(el("div", { class: "row" }, el("span", { class: "lbl", text: "Pick up" }), count, item),
          el("p", { class: "muted", style: { fontSize: "0.85rem" }, text: "What you pick up from this step on counts. The items stay in your inventory." }));
      } else {
        const kind = el("select", { "aria-label": "Where", onchange: () => {
          if (kind.value === "spot") delete s.place; else { s.place = kind.value; delete s.at; delete s.level; }
          changed(); redraw();
        } }, el("option", { value: "spot", text: "A spot in the forest" }),
        ...Object.entries(PLACES).map(([k, label]) => el("option", { value: k, text: `The nearest: ${label}` })));
        kind.value = s.place || "spot";
        const radius = el("input", { type: "number", min: "100", max: "5000", step: "50", value: s.radius || 400, style: { width: "6em" }, "aria-label": "How close, in cm",
          onchange: () => { s.radius = Math.max(100, Math.min(5000, Number(radius.value) || 400)); changed(); } });
        body.append(field("Where", kind));
        if (!s.place) body.append(wherePicker({ at: s.at, level: s.level }, spot => {
          s.at = spot.at || undefined;
          if (spot.level) s.level = spot.level;
          changed();
        }));
        body.append(el("div", { class: "row" }, el("span", { class: "lbl", text: "Done within" }), radius, el("span", { class: "muted", text: "cm (a cat is about 100)" })));
      }
      const move = (d) => { const j = n + d; if (j < 0 || j >= q.steps.length) return; [q.steps[n], q.steps[j]] = [q.steps[j], q.steps[n]]; changed(); redraw(); };
      return el("li", { class: "step-card", "data-key": `step:${n}` },
        el("div", { class: "row spread" },
          el("strong", { text: `${n + 1}. ${STEP_LABEL[s.do] || s.do}` }),
          el("span", { class: "row" },
            el("button", { class: "btn ghost small", text: "↑", "aria-label": `Move step ${n + 1} up`, disabled: n === 0, onclick: () => move(-1) }),
            el("button", { class: "btn ghost small", text: "↓", "aria-label": `Move step ${n + 1} down`, disabled: n === q.steps.length - 1, onclick: () => move(1) }),
            el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove step ${n + 1}`, onclick: () => { q.steps.splice(n, 1); changed(); redraw(); } }))),
        body,
        field("Objective", objective, "What the quest panel says. Leave it empty for the one shown."));
    }
    return {};
  },
};
