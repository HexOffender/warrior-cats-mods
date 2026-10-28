// Questlines: quests of the mod's own (quests.json), step by step: talk to one of the mod's cats, pick
// things up, go somewhere; a reward at the end. The Sandbox mode mod runs them with a sandbox cat. The
// file's rules are in lib/quests-model.js; what the story pages share is in lib/story.js.
import { slug, listEditor, field, linesBox, wherePicker, itemChoices, itemSelect, ownItems, sandboxStrip } from "../lib/story.js";
import * as model from "../lib/quests-model.js";

const { STEP_LABEL, PLACES } = model;

export default {
  title: "Questlines",
  async mount(root, wc) {
    const { el, api, toast, clear } = wc;
    // Everything the drawing reads is declared here, before the first await: the file can come in (and the
    // editor be drawn) while the rest of mount() still waits.
    let quests = [], extra = {}, cats = [], own = [];
    let game = { items: [] };
    let choices = itemChoices(game);
    let showIssues = null;   // the open quest's "Not ready yet" note, said again as it changes
    const names = {
      cat: id => (cats.find(c => c.id === id) || {}).name || id,
      item: tag => choices.name(tag),
    };

    const strip = sandboxStrip({ help: "questlines",
      route: "To play them: Apply to game, Play, Sandbox Mode on the main menu, then a new cat or one of your sandbox cats. The step you're on shows in the objective panel on the left and on the mod menu's Questlines page (not in the game's own quest list)." });
    let loading = Promise.resolve();   // the file being opened (its mod's cats and items come first)
    const target = wc.modTarget({
      file: "quests.json",
      // The mod's cats and items first: an objective that's the one the game would show stays automatic.
      onLoad: (obj, id) => {
        loading = (async () => { await loadMod(id); ({ quests, extra } = model.load(obj, names)); draw(); })();
      },
      getValue: () => model.toJson(quests, extra),
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
          steps: giver ? [{ do: "talk", npc: giver, lines: [], _auto: true }] : [] });
        editor.choose(quests.length - 1);
        changed();
        draw();
        const input = root.querySelector('[data-focus="quest:title"]');
        if (input) { input.focus(); input.select?.(); }
      },
    });
    editor.ready(false);   // until the file is read

    // Starting over: progress is Sandbox mode's, beside the game's saves; the studio can clear it with the game closed.
    const startOver = wc.confirmButton("Start every questline over", "Press again to start them all over", async () => {
      try {
        const r = await api.del("/story/progress");
        toast(r.cats ? `Every questline starts over, for ${r.cats} sandbox cat${r.cats === 1 ? "" : "s"}. Where their cats stand is kept.`
          : "Nothing to start over: no sandbox cat has begun a questline yet.");
      } catch (e) { toast(e.message, "bad"); }
    });
    root.append(
      wc.pageHead({ eyebrow: "Sandbox mode", title: "Questlines", help: "help:questlines",
        lede: "Quests of your own, with your cats from the Characters page. A quest is a list of steps done in order: talk to a cat, pick things up, go somewhere. It can wait for other quests to be done first, so quests make a story. The reward is dropped at your cat's paws at the end." }),
      target.element, strip.element, catsNote, editor.element,
      el("div", { class: "card" },
        el("h3", { text: "Starting over" }),
        el("p", { class: "note", text: "How far each sandbox cat has got is kept by Sandbox mode, one record per sandbox cat, in sandbox-story.json beside the game's saves. A new sandbox cat starts every questline from the beginning, and with Sandbox mode 0.5 or newer a quest whose steps you change starts over by itself. The mod menu's Questlines page (Insert, in the game) starts one quest over." }),
        el("div", { class: "row" }, startOver,
          el("span", { class: "muted", style: { fontSize: "0.85rem" }, text: "For all your sandbox cats, with the game closed. Where their cats stand is kept." }))),
      el("details", { class: "fold", "data-key": "makers:quests" },
        el("summary", {}, el("h3", { text: "For mod makers" }), el("span", { class: "muted", text: "the file this page writes" })),
        out.element));

    try { game = await api.get("/game/items"); } catch (e) { /* no game yet: the mod's own items, and tags typed in files */ }
    choices = itemChoices(game);
    await target.refresh();
    await loading;
    editor.ready(true);
    await strip.refresh();

    // The mod's cats (npcs.json) and items (items.json), read only when the mod has them: a mod that isn't made
    // yet (My mods before its first save) has no files to ask for.
    async function loadMod(id) {
      cats = []; own = [];
      const m = target.mods.find(x => x.id === id);
      const files = [["characters", "npcs.json", v => { cats = (Array.isArray(v.npcs) ? v.npcs : []).filter(c => c && c.id); }],
        ["items", "items.json", v => { own = ownItems(v); }]];
      for (const [kind, file, set] of files) {
        if (!m || !m.kinds.includes(kind)) continue;
        try {
          const r = await api.get(`/mods/${encodeURIComponent(id)}/file/${file}`);
          if (r.exists) set(JSON.parse(r.text));
        } catch (e) { /* a file that isn't JSON: the Characters or Items page says */ }
      }
      choices = itemChoices(game, own);
      catsNote.hidden = cats.length > 0;
      clear(catsNote).append(el("strong", { text: "This mod has no cats yet" }),
        el("span", { text: "Talking steps and quest givers are cats of the same mod. Make some on the Characters page (with this mod chosen), then come back." }));
    }
    function changed() {
      target.markDirty();
      out.set(model.toJson(quests, extra));
      showIssues?.();
    }
    function draw() {
      out.set(model.toJson(quests, extra));
      editor.render(quests, drawQuest);
    }

    function drawQuest(box, q, i) {
      const redraw = () => { clear(box); drawQuest(box, q, i); };
      const issues = el("div", { class: "banner", role: "status" });
      const stepMarks = [];   // each step card's "not ready" line
      showIssues = () => {
        const p = model.problems(q, quests, cats);
        issues.hidden = !p.length;
        issues.replaceChildren(el("strong", { text: "Not ready yet" }), el("ul", { class: "notes" }, ...p.map(x => el("li", { text: x.text }))));
        stepMarks.forEach((mark, n) => {
          const mine = p.filter(x => x.step === n);
          mark.hidden = !mine.length;
          mark.textContent = mine.map(x => x.text.replace(/^Step \d+: (.)/, (_, c) => c.toUpperCase())).join(" ");
          mark.closest?.(".step-card")?.classList.toggle("not-ready", mine.length > 0);
        });
      };

      // ---- the quest
      const title = el("input", { type: "text", value: q.title || "", maxlength: "60", "data-focus": "quest:title", oninput: () => {
        q.title = title.value;
        if (q._new) q.id = slug(q.title, quests.filter(x => x !== q).map(x => x.id), "quest");
        editor.relabel(i);
        changed();
      } });
      const desc = el("input", { type: "text", value: q.description || "", maxlength: "400", "data-focus": "quest:about",
        placeholder: "Optional: a sentence about it, shown under its title on the mod menu's Questlines page",
        oninput: () => { q.description = desc.value; changed(); } });
      const giver = el("select", { "aria-label": "Given by", onchange: () => {
        const was = q.giver;
        q.giver = giver.value || undefined;
        // A talk step that named the old giver follows the new one.
        for (const s of q.steps) if (s.do === "talk" && (!s.npc || s.npc === was)) s.npc = q.giver;
        changed(); redraw();
      } },
        el("option", { value: "", text: "Nobody (it starts on its own)" }),
        ...cats.map(c => el("option", { value: c.id, text: c.name })));
      if (q.giver && !cats.some(c => c.id === q.giver)) giver.append(el("option", { value: q.giver, text: `${q.giver} (not in this mod)` }));
      giver.value = q.giver || "";

      // ---- starts after: a quest that already waits for this one can't be ticked (it would be a circle)
      const others = quests.filter(x => x !== q);
      const after = others.length ? el("div", { class: "stack" }, ...others.map(o => {
        const ticked = (q.after || []).includes(o.id);
        const loops = !ticked && model.waitsFor(quests, o.id).has(q.id);
        const why = loops ? `${o.title || o.id} already waits for this quest` : null;
        return el("label", { class: "row", title: why },
          el("input", { type: "checkbox", checked: ticked, disabled: loops, "aria-describedby": loops ? `why-${i}-${o.id}` : null,
            "data-focus": `after:${o.id}`, onchange: e => {
              q.after = (q.after || []).filter(a => a !== o.id).concat(e.target.checked ? [o.id] : []);
              changed(); redraw();
            } }),
          el("span", { text: o.title || o.id }),
          loops ? el("span", { class: "muted", id: `why-${i}-${o.id}`, text: `(${why})` }) : null);
      })) : el("p", { class: "muted", text: "It starts as soon as a sandbox cat comes into the forest. With more quests, you can make one wait for others." });

      // ---- steps
      const steps = el("ol", { class: "steps-list" });
      q.steps.forEach((s, n) => {
        const mark = el("p", { class: "step-problem", role: "note", hidden: true });
        stepMarks.push(mark);
        steps.append(drawStep(q, s, n, redraw, mark));
      });
      const addStep = kind => {
        const s = { do: kind, _auto: true };
        if (kind === "talk") { s.npc = q.giver || cats[0]?.id; s.lines = []; }
        if (kind === "collect") s.count = 1;
        if (kind === "visit") s.radius = 400;
        q.steps.push(s);
        changed(); redraw();
      };

      // ---- reward
      const rewards = el("div", { class: "stack" });
      const drawRewards = () => {
        clear(rewards);
        for (const [tag, n] of Object.entries(q.reward || {})) {
          const count = el("input", { type: "number", min: "1", max: "99", value: n, style: { width: "5em" }, "aria-label": `How many ${choices.name(tag)}`,
            onchange: () => { q.reward[tag] = Math.max(1, Math.min(99, Math.round(Number(count.value) || 1))); changed(); } });
          rewards.append(el("div", { class: "row" }, count, el("span", { text: choices.name(tag) }),
            el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove ${choices.name(tag)} from the reward`,
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

      box.append(
        issues,
        el("div", { class: "card" },
          el("h3", { text: "The quest" }),
          field("Title", title), field("About it", desc),
          field("Given by", giver, "They wear the game's quest mark while the quest waits for you.")),
        el("div", { class: "card" }, el("h3", { text: "Starts after" }), after),
        el("div", { class: "card" }, el("h3", { text: "Steps" }),
          el("p", { class: "note", text: "Done in order. The game's objective panel on the left shows the step you're on; a marker on the map shows where to go." }),
          q.steps.length ? steps : el("div", { class: "empty", text: "No steps yet." }),
          el("div", { class: "row" }, el("span", { class: "lbl", text: "Add a step:" }),
            ...Object.entries(STEP_LABEL).map(([k, label]) => el("button", { class: "btn small", type: "button", text: label, onclick: () => addStep(k) })))),
        el("div", { class: "card" }, el("h3", { text: "Reward" }),
          el("p", { class: "note", text: "Dropped at your cat's paws when the last step is done, to pick up." }), rewards),
        el("div", { class: "row" },
          wc.confirmButton(`Remove ${q.title || "this quest"}`, "Press again to remove", () => {
            quests.splice(i, 1);
            for (const x of quests) x.after = (x.after || []).filter(a => a !== q.id);
            changed(); draw();
            toast(`Removed ${q.title || "the quest"}.`);
          }, "btn danger")));
      showIssues();
    }

    function drawStep(q, s, n, redraw, mark) {
      const auto = () => model.autoObjective(s, q, names);
      const objective = el("input", { type: "text", maxlength: "80", value: s._auto ? "" : s.objective || "", placeholder: auto(),
        "aria-label": `Step ${n + 1}'s objective`,
        oninput: () => { s.objective = objective.value; s._auto = !objective.value.trim(); changed(); } });
      const body = el("div", { class: "stack" });
      if (s.do === "talk") {
        const who = el("select", { "aria-label": "Who to talk to", onchange: () => { s.npc = who.value; changed(); objective.placeholder = auto(); } },
          ...cats.map(c => el("option", { value: c.id, text: c.name })));
        if (s.npc && !cats.some(c => c.id === s.npc)) who.append(el("option", { value: s.npc, text: `${s.npc} (not in this mod)` }));
        who.value = s.npc || q.giver || "";
        body.append(field("Who", who), field("What they say", linesBox(s.lines || [], v => { s.lines = v; changed(); },
          "One line each; Interact or Enter shows the next.\nThere you are! I need your help.\nCould you bring me some moss?"), "The step is done after the last line."));
      } else if (s.do === "collect") {
        const count = el("input", { type: "number", min: "1", max: "99", value: s.count || 1, style: { width: "5em" }, "aria-label": "How many",
          oninput: () => { s.count = Math.max(1, Math.min(99, Math.round(Number(count.value) || 1))); changed(); objective.placeholder = auto(); } });
        const item = itemSelect(choices, s.item, v => { s.item = v; changed(); objective.placeholder = auto(); });
        body.append(el("div", { class: "row" }, el("span", { class: "lbl", text: "Pick up" }), count, item),
          el("p", { class: "muted", style: { fontSize: "0.85rem" }, text: "What you pick up from this step on counts. The items stay in your inventory." }));
      } else {
        const kind = el("select", { "aria-label": "Where", onchange: () => {
          if (kind.value === "spot") delete s.place; else { s.place = kind.value; delete s.at; delete s.level; }
          changed(); redraw();
        } }, el("option", { value: "spot", text: "A spot in the forest" }),
        ...Object.entries(PLACES).map(([k, label]) => el("option", { value: k, text: label[0].toUpperCase() + label.slice(1) })));
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
      const move = d => { const j = n + d; if (j < 0 || j >= q.steps.length) return; [q.steps[n], q.steps[j]] = [q.steps[j], q.steps[n]]; changed(); redraw(); };
      return el("li", { class: "step-card", "data-key": `step:${n}` },
        el("div", { class: "row spread" },
          el("strong", { text: `${n + 1}. ${STEP_LABEL[s.do] || s.do}` }),
          el("span", { class: "row" },
            el("button", { class: "btn ghost small", type: "button", text: "↑", "aria-label": `Move step ${n + 1} up`, disabled: n === 0, onclick: () => move(-1) }),
            el("button", { class: "btn ghost small", type: "button", text: "↓", "aria-label": `Move step ${n + 1} down`, disabled: n === q.steps.length - 1, onclick: () => move(1) }),
            el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove step ${n + 1}`, onclick: () => { q.steps.splice(n, 1); changed(); redraw(); } }))),
        mark,
        body,
        field("Objective", objective, "What the game's objective panel says. Leave it empty for the words shown, with the names as they are when you Apply."));
    }

    // After an Apply the file is read again (unless there are unsaved changes), and the strip asked again; a
    // save on Characters or Items (any mod changed) brings their cats and items here.
    const offInstalled = wc.installedEvent(target, () => { target.refresh(); });
    const offApplied = wc.bus.on("installed", () => { strip.refresh(); });
    const offChanged = wc.bus.on("mods-changed", async () => {
      strip.refresh();
      if (!target.current) return;
      await target.refresh();   // the list; the file only when nothing here is unsaved
      if (target.dirty) { await loadMod(target.current); draw(); }
    });
    return { unmount() { offInstalled(); offApplied(); offChanged(); } };
  },
};
