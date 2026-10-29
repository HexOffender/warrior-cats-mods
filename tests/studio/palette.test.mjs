// studio/lib/palette.js, the Palettes page's file logic, under node:test: reading a palette.json the way the build
// reads it, writing back what the page can't show, the whole-tab changes, a new colour's number and the eye strips.
import { test } from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { STUDIO } from "./lib/dom.mjs";

const P = await import(pathToFileURL(path.join(STUDIO, "lib", "palette.js")).href);
const { color } = await import(pathToFileURL(path.join(STUDIO, "lib", "colour.js")).href);

// The game's eye names as the atlas has them (conftest.EYE_LABELS on the Python side): the eye white, 20, 5 extra.
const LABELS = ["Sclera", "Yellow", "Amber", "Hazel", "Copper", "Green", "Olive", "Mint", "Teal", "Sky", "Blue", "Ice",
  "Grey", "Silver", "Violet", "Lilac", "Rose", "Red", "Brown", "Black", "White", "Dlc1", "Dlc2", "Dlc3", "Dlc4", "Dlc5"];
const opts = { labels: LABELS, gameSlots: 25 };

test("eyeRow takes the game's names in any case and numbers that are rows, as eyeatlas.resolve does", () => {
  for (const [key, row] of [["Amber", 2], ["amber ", 2], ["SCLERA", 0], ["iris2", 2], ["row2", 2], ["2", 2], ["iris03", 3],
    ["dlc1", 21], ["25", 25]]) assert.equal(P.eyeRow(LABELS, key), row, key);
  for (const key of ["30", "row26", "iris99", "Ambre", "", "iris", "-1", "2.5"]) assert.equal(P.eyeRow(LABELS, key), null, key);
});

test("a palette's colours load in every form the build takes", () => {
  const s = P.fromPalette({
    eyes: { Amber: "orange", Sky: ["#001018", [0, 229, 255]], Sclera: "#f7f3e8ff", iris3: [255, 0, 0] },
    fur: { 0: "teal", 3: "#11223344", 4: "abc", 5: [0, 0, 255, 128] },
  }, opts);
  assert.deepEqual(s.eyes, {
    2: { mode: "single", colors: ["#FF8C00"] }, 9: { mode: "grad", colors: ["#001018", "#00E5FF"] },
    0: { mode: "single", colors: ["#F7F3E8"] }, 3: { mode: "single", colors: ["#FF0000"] },
  });
  assert.deepEqual(s.fur, { 0: "#008080", 3: "#112233", 4: "#AABBCC", 5: "#0000FF" });
  assert.deepEqual(s.unread, []);
});

test("what the page can't show is listed with why, and written back as it was", () => {
  const file = {
    eyes: { Ambre: "#ffffff", Amber: "not a colour", Hazel: "#00ff00", _note: "mine" },
    fur: { 30: "#ffffff", x: "#000000", 3: ["#000000", "#ffffff"], 4: "#123456", _why: "warm" },
    pattern: { 25: "#ff00cc" }, hats: { 0: "#ffffff" },
    iris_ui: { 1: "#ff0000" }, coats: { Ash: { fur: "#9a9590", like: 12 } }, name: "Dawn", _help: "old help",
  };
  const s = P.fromPalette(file, opts);
  assert.deepEqual(s.unread.map(P.describeUnread), [
    '"hats": {"0":"#ffffff"} (not something a palette has)',
    'Eyes "Ambre": "#ffffff" (not one of the game\'s eye colours)',
    'Eyes "Amber": "not a colour" (not a colour this page reads)',
    'Coat "3": ["#000000","#ffffff"] (only eyes take more than one colour)',
    'Coat "x": "#000000" (not a colour number)',
  ]);
  assert.deepEqual(s.kept, { iris_ui: { 1: "#ff0000" }, coats: { Ash: { fur: "#9a9590", like: 12 } }, name: "Dawn", _help: "old help" });
  const back = P.toPalette(s, LABELS);
  assert.equal(back._help, "old help", "a help line written by hand is kept, as every \"_\" key is");
  assert.equal(Object.keys(back)[0], "_help");
  assert.deepEqual(back.eyes, { Ambre: "#ffffff", Amber: "not a colour", _note: "mine", Hazel: "#00FF00" });
  // A coat past the game's 25 is read like a new pattern colour: the build makes it a coat preset.
  assert.deepEqual(back.fur, { 3: ["#000000", "#ffffff"], 30: "#FFFFFF", x: "#000000", _why: "warm", 4: "#123456" });
  assert.deepEqual(back.pattern, { 25: "#FF00CC" });
  assert.deepEqual(back.hats, { 0: "#ffffff" });
  assert.deepEqual(back.coats, file.coats);
  assert.deepEqual(back.iris_ui, file.iris_ui);
  assert.equal(back.name, "Dawn");
  // Removing one (the page's Remove button) leaves it out of the file.
  s.unread = s.unread.filter(u => u.key !== "Ambre");
  assert.equal("Ambre" in P.toPalette(s, LABELS).eyes, false);
});

test("a round trip keeps eye names, sorts numbers, and keeps a one-colour eye list a list", () => {
  const s = P.fromPalette({ fur: { 10: "#0000ff", 2: "#ff0000" }, eyes: { iris9: ["#ffb300"], amber: "#00ff00" } }, opts);
  assert.deepEqual(s.eyes[9], { mode: "grad", colors: ["#FFB300", "#FFB300"] }, "flat, pupil to rim, as the build paints it");
  const back = P.toPalette(s, LABELS);
  assert.deepEqual(Object.keys(back.fur), ["2", "10"]);
  assert.deepEqual(back.eyes, { Amber: "#00FF00", Sky: ["#FFB300", "#FFB300"] });
  assert.deepEqual(P.fromPalette(back, opts).eyes, s.eyes, "and it reads back the same");
  assert.deepEqual(P.toPalette(P.fromPalette(null, opts), LABELS), { _help: P.HELP }, "no file: nothing but the help line");
});

test("the page's own help line is written afresh", () => {
  const s = P.fromPalette({ _help: "Written by Clan Mod Studio. An older wording.", fur: { 3: "#ff0000" } }, opts);
  assert.deepEqual(s.kept, {});
  assert.equal(P.toPalette(s, LABELS)._help, P.HELP);
});

test("two keys for one eye or one colour, in an order the page can read: the later is the page's, as in the build", () => {
  const s = P.fromPalette({ eyes: { Amber: "#ff0000", iris2: "#00ff00" }, fur: { "03": "#111111", "003": "#222222" } }, opts);
  assert.deepEqual(s.eyes[2].colors, ["#00FF00"]);
  assert.deepEqual(s.fur, { 3: "#222222" });
  assert.deepEqual(s.unread, [
    { section: "eyes", key: "Amber", value: "#ff0000", why: '"iris2", later in the file, also names the Amber eye: the game uses that one', slot: 2 },
    { section: "fur", key: "03", value: "#111111", why: '"003", later in the file, also names coat colour 3: the game uses that one', slot: 3 },
  ]);
  assert.match(P.describeUnread(s.unread[0], s), /; Save puts the colour set here in its place\)$/);
  // Save keeps the one the page shows, which is the one the build takes: it doesn't flip to the earlier.
  const back = P.toPalette(s, LABELS);
  assert.deepEqual([back.eyes, back.fur], [{ Amber: "#00FF00" }, { 3: "#222222" }]);
  assert.deepEqual(P.fromPalette(back, opts).unread, []);
});

test("two keys for one colour where one is a plain number: a conflict, both written back untouched", () => {
  // The browser reads "3" and "9" first whatever the file's order, so the page can't tell which the build takes.
  const s = P.fromPalette({ eyes: { iris09: "#ff0000", 9: "#00ff00" }, pattern: { "03": "#111111", 3: "#222222" } }, opts);
  assert.deepEqual([s.eyes, s.pattern], [{}, {}], "neither is the page's");
  assert.deepEqual(s.unread.map(u => [u.section, u.key, u.slot]), [["eyes", "9", 9], ["eyes", "iris09", 9], ["pattern", "3", 3], ["pattern", "03", 3]]);
  assert.match(s.unread[0].why, /^"9" and "iris09" both name the Sky eye, and which one the game uses depends on their order in the file/);
  assert.match(s.unread[2].why, /^"3" and "03" both name pattern colour 3/);
  let back = P.toPalette(s, LABELS);
  assert.deepEqual([back.eyes, back.pattern], [{ 9: "#00ff00", iris09: "#ff0000" }, { 3: "#222222", "03": "#111111" }]);
  // A colour set on the page takes the place of both.
  s.pattern[3] = "#333333";
  assert.ok(P.replaced(s, s.unread[2]) && P.replaced(s, s.unread[3]) && !P.replaced(s, s.unread[0]));
  back = P.toPalette(s, LABELS);
  assert.deepEqual(back.pattern, { 3: "#333333" });
  assert.deepEqual(back.eyes, { 9: "#00ff00", iris09: "#ff0000" });
});

test("a part that isn't a list of colours stays as written until the page has colours of its own in it", () => {
  const s = P.fromPalette({ fur: ["#ffffff"], eyes: "Amber" }, opts);
  assert.deepEqual(s.unread.map(u => [u.section, u.key]), [["eyes", null], ["fur", null]]);
  assert.deepEqual(P.toPalette(s, LABELS), { _help: P.HELP, fur: ["#ffffff"], eyes: "Amber" });
  s.fur[2] = "#123456";
  assert.equal(P.describeUnread(s.unread[1], s), 'Coat: ["#ffffff"] (not a list of colours by number; Save puts your colours on this tab in its place)');
  assert.equal(P.describeUnread(s.unread[0], s), 'Eyes: "Amber" (not a list of eye colours by name)');
  const back = P.toPalette(s, LABELS);
  assert.deepEqual(back.fur, { 2: "#123456" }, "the page's colours, not the old value written over them");
  assert.equal(back.eyes, "Amber");
});

test("an unreadable entry for a colour the page sets gives way to the page's", () => {
  const s = P.fromPalette({ fur: { 3: ["#000000", "#ffffff"] }, eyes: { Amber: "not a colour" } }, opts);
  s.fur[3] = "#445566";
  s.eyes[2] = { mode: "single", colors: ["#00FF00"] };
  const back = P.toPalette(s, LABELS);
  assert.deepEqual([back.fur, back.eyes], [{ 3: "#445566" }, { Amber: "#00FF00" }]);
});

test("the eyes in the page's words", () => {
  assert.deepEqual([0, 2, 21, 25].map(r => P.eyeWord(LABELS, r)), ["Eye white", "Amber", "Extra eye 1", "Extra eye 5"]);
  assert.deepEqual([0, 2, 21].map(r => P.eyeWord(LABELS, r, true)), ["the eye white", "Amber", "extra eye 1"]);
});

test("without the game's eye names the file's eyes are kept as they are", () => {
  const eyes = { Amber: "#ffb300", Whatever: "#000000" };
  const s = P.fromPalette({ eyes, fur: { 3: "#ff0000" } }, { labels: null });
  assert.deepEqual(s.eyes, {});
  assert.deepEqual(s.unread, []);
  assert.deepEqual(P.toPalette(s, null), { _help: P.HELP, fur: { 3: "#FF0000" }, eyes });
});

test("without the game's eye names, Game colours and Start from change the file's eyes all the same", () => {
  const s = P.fromPalette({ eyes: { Amber: "#ffb300", _why: "warm" }, fur: { 3: "#ff0000" } }, { labels: null });
  const game = P.gameColours(s, 25);
  assert.deepEqual(game.kept.eyes, { _why: "warm" }, "the eyes go, their note stays");
  assert.equal("eyes" in P.toPalette(P.gameColours(P.fromPalette({ eyes: { Amber: "#ffb300" } }, { labels: null }), 25), null), false);
  const from = P.startFrom(s, { eyes: { Sky: "#0000ff" }, fur: { 5: "#555555" } }, { labels: null });
  assert.deepEqual(from.kept.eyes, { Sky: "#0000ff", _why: "warm" });
  assert.deepEqual(P.startFrom(s, { fur: {} }, { labels: null }).kept.eyes, { _why: "warm" });
  assert.deepEqual(s.kept.eyes, { Amber: "#ffb300", _why: "warm" }, "the state it was given is left alone (Undo)");
});

test("a new colour's number is past the game's, this palette's and every other palette's", () => {
  assert.equal(P.nextSlot([], [], 25), 25);
  assert.equal(P.nextSlot([3, 25, 26], [], 25), 27);
  assert.equal(P.nextSlot([25], [100, 101, 7], 25), 102);
  assert.equal(P.nextSlot([3, 4], [1, 24], 25), 25, "the game's own colours don't count");
});

test("the eye groups come from the game's names", () => {
  const g = P.eyeGroups(LABELS);
  assert.deepEqual(g.white, [0]);
  assert.deepEqual(g.extra, [21, 22, 23, 24, 25]);
  assert.equal(g.standard.length, 20);
  assert.deepEqual(P.eyeGroups(["Sclera", "Amber", "Dlc", "Sky"]), { white: [0], standard: [1, 3], extra: [2] });
});

test("Reset tab and Game colours keep the new colours; Start from keeps them too", () => {
  const s = P.fromPalette({ eyes: { Amber: "#ff0000" }, fur: { 3: "#000000" }, pattern: { 3: "#111111", 25: "#ff00cc" },
    marking: { 26: "#00e5ff" }, coats: { Ash: { fur: "#9a9590", like: 12 } }, hats: {} }, opts);
  const reset = P.resetTab(s, "pattern", 25);
  assert.deepEqual(reset.pattern, { 25: "#FF00CC" });
  assert.deepEqual(reset.fur, { 3: "#000000" }, "only the tab");
  assert.deepEqual(P.resetTab(s, "eyes", 25).eyes, {});
  const game = P.gameColours(s, 25);
  assert.deepEqual([game.eyes, game.fur, game.pattern, game.marking], [{}, {}, { 25: "#FF00CC" }, { 26: "#00E5FF" }]);
  assert.deepEqual(game.kept.coats, { Ash: { fur: "#9a9590", like: 12 } });
  assert.equal(game.unread.length, 1, "what the page can't show stays until its Remove");
  const from = P.startFrom(s, { fur: { 5: "#555555" }, pattern: { 4: "#444444", 100: "#abcdef" }, eyes: { Sky: "#0000ff" } }, opts);
  assert.deepEqual(from.fur, { 5: "#555555" });
  assert.deepEqual(from.pattern, { 4: "#444444", 25: "#FF00CC" }, "their changes to the game's colours, and ours new ones");
  assert.deepEqual(from.eyes, { 9: { mode: "single", colors: ["#0000FF"] } });
  assert.deepEqual(from.kept, s.kept);
  assert.notEqual(reset, s, "each gives a new state: the old one is the Undo");
  assert.deepEqual(s.pattern, { 3: "#111111", 25: "#FF00CC" }, "and leaves the one it was given alone");
});

test("a mood restyles every eye but the eye white, extra eyes included, or the tab's game colours", () => {
  const rims = LABELS.map((_, r) => (r === 0 ? "#F0F0F0" : "#806040"));
  const s = P.restyle(P.blank(), "eyes", "vivid", { eyeRims: rims });
  assert.equal(Object.keys(s.eyes).length, 25);
  assert.equal(s.eyes[0], undefined, "the eye white stays");
  assert.deepEqual(s.eyes[21], { mode: "single", colors: [color.mood("#806040", "vivid")] });
  const t = P.restyle(P.fromPalette({ pattern: { 25: "#ff00cc" } }, opts), "pattern", "pastel", { table: ["#202020", "#a0a0a0"] });
  assert.deepEqual(t.pattern, { 0: color.mood("#202020", "pastel"), 1: color.mood("#a0a0a0", "pastel"), 25: "#FF00CC" });
});

test("eyeRamp keeps a row's shading for one colour and spreads a gradient", () => {
  const orig = P.plainRow(64);
  assert.deepEqual(P.eyeRamp(orig, null), orig);
  const one = P.eyeRamp(orig, { mode: "single", colors: ["#FF0000"] });
  assert.deepEqual(one[0], [0, 0, 0]);
  assert.deepEqual(one[63], [1, 0, 0]);
  const flat = P.eyeRamp(P.plainRow(64, true), { mode: "single", colors: ["#FF0000"] });
  assert.ok(flat.every(p => p[0] === 1), "a flat row (the eye white) takes the colour flat");
  const grad = P.eyeRamp(orig, { mode: "grad", colors: ["#000000", "#FFFFFF"] });
  assert.deepEqual(grad[0], [0, 0, 0]);
  assert.deepEqual(grad[63], [1, 1, 1]);
});

test("ticked palettes overlap only where they change the same colour, and the later one in the Mods list wins it", () => {
  const theme = (name, extra = {}) => ({ name, palette: { fur: Object.fromEntries([...Array(25).keys()].map(i => [i, "#111111"])),
    eyes: Object.fromEntries(LABELS.slice(1, 21).map(l => [l, "#222222"])), pattern: { 100: "#333333" }, ...extra } });
  const eyesOnly = { name: "Gem eyes", palette: { eyes: { amber: "#ff0000", iris9: "#00ff00" }, _note: "eyes" } };
  // A full theme, then a palette for just the eyes: the eyes it changes are the theme's too, on top, as meant.
  assert.deepEqual(P.overlaps([theme("Forest"), eyesOnly], LABELS),
    [{ earlier: "Forest", later: "Gem eyes", what: "2 eyes", onTop: true }]);
  // The other way round, the theme hides them: a conflict, by row whatever each calls the eye.
  assert.deepEqual(P.overlaps([{ name: "Amber", palette: { eyes: { iris2: "#ff0000" } } }, theme("Forest")], LABELS),
    [{ earlier: "Amber", later: "Forest", what: "the Amber eye", onTop: false }]);
  // Two themes: every coat and eye; their new colours have numbers of their own, so they don't meet.
  assert.deepEqual(P.overlaps([theme("Forest"), theme("River", { pattern: { 125: "#444444" } })], LABELS),
    [{ earlier: "Forest", later: "River", what: "25 coats and 20 eyes", onTop: false }]);
  // A coats palette and an eyes palette change nothing in common; "03" is coat 3, as the build counts.
  assert.deepEqual(P.overlaps([{ name: "Coats", palette: { fur: { 3: "#000000" } } }, eyesOnly], LABELS), []);
  assert.deepEqual(P.overlaps([{ name: "A", palette: { fur: { "03": "#000000" }, marking: { 30: "#fff" } } },
    { name: "B", palette: { fur: { 3: "#ffffff" }, marking: { 30: "#000" } } }], LABELS),
    [{ earlier: "A", later: "B", what: "coat 3 and marking colour 30", onTop: false }]);
  // Three themes: the last wins everything, so only it is said to show over the others.
  assert.deepEqual(P.overlaps([theme("A"), theme("B"), theme("C")], LABELS).map(o => `${o.later} over ${o.earlier}`), ["C over A", "C over B"]);
  // A misspelt eye changes nothing in the build; without the game's names, eyes match as written.
  assert.deepEqual(P.overlaps([{ name: "A", palette: { eyes: { Ambre: "#000" } } }, { name: "B", palette: { eyes: { Ambre: "#fff" } } }], LABELS), []);
  assert.deepEqual(P.overlaps([{ name: "A", palette: { eyes: { Amber: "#000" } } }, { name: "B", palette: { eyes: { amber: "#fff" } } }], null),
    [{ earlier: "A", later: "B", what: "an eye", onTop: false }]);
});
