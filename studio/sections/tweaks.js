// Tweaks: small changes while you play, ticked here and saved as tweaks.json in a mod (wcmods/tweaks.py). They run
// as wcmods' own in-game script (wcmods/lua/tweaks.lua), like mouse look, so no mod's code runs and nothing has to
// be allowed. What the page offers (each tweak's default, the keys a heal can go on) is the server's (/tweaks).

// Hours (12.5) as the time box's "12:30", and back.
export const toClock = h => { const m = Math.round(Number(h) * 60) % (24 * 60); return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`; };
export const fromClock = s => { const [h, m] = String(s).split(":").map(Number); return Number.isFinite(h) && Number.isFinite(m) ? h + m / 60 : null; };

export default {
  title: "Tweaks",
  async mount(root, wc) {
    const { el, api, toast } = wc;
    let offer;
    try { offer = await api.get("/tweaks"); }
    catch (e) { root.append(el("div", { class: "error-card" }, el("h2", { text: "Tweaks couldn't load" }), el("p", { text: e.message }))); return; }
    const D = offer.defaults;
    // Keys something else in your mods has you press ({key: what}), and tweaks not available yet ({key: why}).
    const taken = offer.taken || {}, unchecked = offer.unchecked || {};
    let state = { ...D }, notes = {};   // the tweaks as the page has them, and the file's "_" notes, kept
    const out = wc.codePanel("tweaks.json");

    // What the file holds: only the tweaks that are on (a missing key is off), the hour only with the clock held,
    // and the file's own notes.
    const value = () => {
      const v = { ...notes };
      if (state.keep_stamina_full) v.keep_stamina_full = true;
      if (state.heal_key) v.heal_key = state.heal_key;
      if (state.hold_time) { v.hold_time = true; v.time_of_day = state.time_of_day; }
      if (state.min_fresh_kill > 0) v.min_fresh_kill = state.min_fresh_kill;
      if (state.skip_scenes && !unchecked.skip_scenes) v.skip_scenes = true;   // (refused while it's unchecked)
      return v;
    };
    const target = wc.modTarget({
      file: "tweaks.json",
      onLoad: obj => {
        obj = obj && typeof obj === "object" ? obj : {};
        notes = Object.fromEntries(Object.entries(obj).filter(([k]) => k.startsWith("_")));
        state = { ...D, ...Object.fromEntries(Object.entries(obj).filter(([k]) => k in D)) };
        render();
      },
      getValue: () => value(),
    });

    const body = el("div", { class: "tweaks", style: { display: "contents" } });   // its cards spaced as the page's own
    root.append(
      wc.pageHead({ eyebrow: "Make mods", title: "Tweaks", help: "help:tweaks",
        lede: "Small changes while you play: stamina that stays full, a key that heals your cat, a clock that stands still, a fresh-kill pile that never runs low. Tick them here, save, and play. No code, and nothing to allow." }),
      ...(offer.ue4ss ? [] : [el("div", { class: "banner" }, el("strong", { text: "Needs the script loader" }),
        el("span", { text: "Tweaks run in the game with the script loader, which Get set up (on the Mods page) installs." }))]),
      target.element, body, out.element);

    function changed(key, v) {
      state = { ...state, [key]: v };
      target.markDirty();
      out.set(value());
    }
    const check = (id, label, on, fn) => {
      const box = el("input", { type: "checkbox", id, checked: on });
      box.addEventListener("change", () => fn(box.checked));
      return el("label", { class: "row", for: id }, box, el("strong", { text: label }));
    };

    function render() {
      out.set(value());
      // The keys offered, and the file's own key when something else has taken it since (said under the row).
      const keys = state.heal_key && !offer.heal_keys.includes(state.heal_key) ? [...offer.heal_keys, state.heal_key] : offer.heal_keys;
      const keySelect = el("select", { id: "tw-key", "aria-label": "The key that heals" },
        ...keys.map(k => el("option", { value: k, text: k })));
      keySelect.disabled = !state.heal_key;   // (the property: a later tick of its box sets it again)
      keySelect.value = state.heal_key || offer.heal_keys.find(k => k === "F5") || offer.heal_keys[0];
      const clash = el("p", { class: "note warn", id: "tw-key-clash" });
      const sayClash = () => {
        const k = state.heal_key;
        clash.hidden = !(k && taken[k]);
        clash.textContent = k && taken[k] ? `${k} is also ${taken[k]}, so pressing it would do both: pick another key.` : "";
      };
      keySelect.addEventListener("change", () => { changed("heal_key", keySelect.value); sayClash(); });
      sayClash();
      const inUse = Object.entries(taken).map(([k, what]) => `${k} (${what})`);
      const clock = el("input", { type: "time", id: "tw-time", value: toClock(state.time_of_day), "aria-label": "The time to hold" });
      clock.disabled = !state.hold_time;
      clock.addEventListener("change", () => { const h = fromClock(clock.value); if (h !== null) changed("time_of_day", h); });
      const pile = el("input", { type: "number", id: "tw-pile", min: 0, max: 100, step: 1, value: String(state.min_fresh_kill || 20),
        "aria-label": "The least the pile holds", style: { width: "6rem" } });
      pile.disabled = !(state.min_fresh_kill > 0);
      pile.addEventListener("change", () => {
        const n = Math.round(Number(pile.value));
        if (!Number.isFinite(n) || n < 1 || n > 100) { toast("The fresh-kill pile goes from 1 to 100.", "bad"); pile.value = String(state.min_fresh_kill || 20); return; }
        changed("min_fresh_kill", n);
      });
      wc.clear(body).append(
        el("div", { class: "card" }, el("h2", { text: "Your cat" }),
          check("tw-stamina", "Keep my cat's stamina full", state.keep_stamina_full, on => changed("keep_stamina_full", on)),
          el("div", { class: "row" },
            check("tw-heal", "Heal my cat with a key", !!state.heal_key, on => { changed("heal_key", on ? keySelect.value : ""); keySelect.disabled = !on; sayClash(); }),
            keySelect),
          clash,
          el("p", { class: "note", text: "The key fills your cat's health and stamina, while the game is in front. F10 and F11 are the game's own and F12 is Steam's screenshot key"
            + (inUse.length ? `, and these are left out as your mods use them: ${inUse.join(", ")}.` : ".") })),
        el("div", { class: "card" }, el("h2", { text: "The day" }),
          el("div", { class: "row" },
            check("tw-hold", "Hold the clock at", state.hold_time, on => { changed("hold_time", on); clock.disabled = !on; }), clock),
          el("p", { class: "note", text: "The sun stays where it is: 06:00 is morning, 21:00 night." })),
        el("div", { class: "card" }, el("h2", { text: "The camp" }),
          el("div", { class: "row" },
            check("tw-pile-on", "Keep the fresh-kill pile at least", state.min_fresh_kill > 0,
              on => { changed("min_fresh_kill", on ? Math.round(Number(pile.value)) || 20 : 0); pile.disabled = !on; }), pile),
          el("p", { class: "note", text: "Out of 100, the pile's own count: 90 and over is Full, 50 Good, under 25 Critical." })),
        // Skipping the story's scenes waits for a check in the game (wcmods/tweaks.py, UNCHECKED): no row till then.
        ...(unchecked.skip_scenes ? [] : [el("div", { class: "card" }, el("h2", { text: "The story" }),
          check("tw-scenes", "Skip the story's scenes", state.skip_scenes, on => changed("skip_scenes", on)),
          el("p", { class: "note", text: "Each of the story's scenes is skipped as it starts, with the game's own hold-to-skip. Sandbox mode does the same for its cats, and the tweak leaves those to it." }))]),
        el("p", { class: "note", text: "Cheats (god mode, game speed) are elsewhere: the mod menu's Cheats page, with Menu pages, and \"Cheats on when the game starts\" on the Settings and repair page. In the game, the mod menu (Insert) has a Tweaks page to change these while you play." }));
    }

    await target.refresh();
    const off = wc.installedEvent(target, () => target.refresh());
    return { unmount() { off(); } };
  },
};
