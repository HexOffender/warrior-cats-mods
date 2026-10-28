// studio/lib/games.js under node:test: a save's games in the words every page uses (the Save page's and Your cat's
// game pickers, the Names page's games), which game a picker starts on, and the Save page's changes by game.
import { test } from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { STUDIO } from "./lib/dom.mjs";

const G = await import(pathToFileURL(path.join(STUDIO, "lib", "games.js")).href);

// As GET /save's "games" has them (wcmods/games.py): three Sharppaws, the 5th game a sandbox game played last.
const GAMES = [
  { slot: "0", n: 1, name: "Sharppaw", clan: "ThunderClan", rank: "Apprentice", level: 3, sandbox: false, current: false },
  { slot: "2", n: 3, name: "Sharppaw", clan: "ThunderClan", rank: "Apprentice", level: 1, sandbox: false, current: false },
  { slot: "3", n: 4, name: null, clan: "RiverClan", rank: "MedicineCat", level: null, sandbox: false, current: false },
  { slot: "4", n: 5, name: "Sharppaw", clan: "ThunderClan", rank: "Apprentice", level: 1, sandbox: true, current: true },
];

test("a game is said by its number as the game's cat choice shows it, slot + 1", () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 111].map(G.ordinal),
    ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st", "111th"]);
  assert.equal(G.numberOf("4"), 5);
  assert.equal(G.numberOf("Shared"), null);
  assert.equal(G.gameWords("4"), "your 5th game");
  assert.equal(G.gameWords(0), "your 1st game");
  assert.equal(G.gameTitle(GAMES[3]), "Your 5th game: Sharppaw");
  assert.equal(G.gameTitle(GAMES[2]), "Your 4th game", "a cat whose name can't be read: the game alone");
  assert.equal(G.catInGame(GAMES[3]), "your cat in your 5th game: Sharppaw");
});

test("a picker's line says the cat, its clan, its level (else its rank), Sandbox mode and the game played last", () => {
  assert.equal(G.gameLabel(GAMES[3]), "5th game: Sharppaw, ThunderClan, level 1, Sandbox mode, played last");
  assert.equal(G.gameLabel(GAMES[0]), "1st game: Sharppaw, ThunderClan, level 3");
  assert.equal(G.gameLabel(GAMES[2]), "4th game: RiverClan, medicine cat");
  assert.equal(G.gameLabel({ slot: "6" }), "7th game");
});

test("cats with one name in several games are told apart by their games", () => {
  assert.deepEqual(G.sameName(GAMES, GAMES[3]).map(g => g.slot), ["0", "2"]);
  assert.deepEqual(G.sameName(GAMES, GAMES[2]), [], "a name that isn't known is nobody's twin");
  assert.equal(G.andList(["your 1st game", "your 3rd game"]), "your 1st game and your 3rd game");
  assert.equal(G.andList(["a", "b", "c"]), "a, b and c");
});

test("who else wears a game's colours of its own: one twin, or several, in a sentence that agrees", () => {
  assert.equal(G.alsoWearIt(G.sameName(GAMES, GAMES[0]).slice(0, 1)), "your cat in your 3rd game, which has the same name, gets them too");
  assert.equal(G.alsoWearIt(G.sameName(GAMES, GAMES[3])),
    "your cats in your 1st game and your 3rd game, which have the same name, get them too");
});

test("each game's cats list that game's own clan first, never the game played last's", () => {
  const clans = ["ThunderClan", "NarrativeRoles", "RiverClan", "ShadowClan", "Outsiders"];
  assert.deepEqual(G.clanOrder(clans, "RiverClan"), ["RiverClan", "ShadowClan", "ThunderClan", "NarrativeRoles", "Outsiders"]);
  assert.deepEqual(G.clanOrder(clans, "ThunderClan"), ["ThunderClan", "RiverClan", "ShadowClan", "NarrativeRoles", "Outsiders"]);
  assert.deepEqual(G.clanOrder(clans, null), ["RiverClan", "ShadowClan", "ThunderClan", "NarrativeRoles", "Outsiders"]);
  assert.equal(clans[0], "ThunderClan", "the list given is left as it was");
});

test("the Save page says which game it moved to when another was played since it read the save", () => {
  assert.equal(G.movedTo(GAMES[3]), "Now on your 5th game: Sharppaw, the game you played last (it was played since this page read your save). Changes already in the list stay with their games.");
  assert.match(G.movedTo(GAMES[2]), /^Now on your 4th game, the game you played last \(/);
});

test("a picker starts on the game played last, or on the one this tab chose while that's still the same", () => {
  assert.equal(G.startSlot(GAMES, "4", null), "4");
  assert.equal(G.startSlot(GAMES, "4", { slot: "2", last: "4" }), "2", "chosen before, and the game played last is the same");
  assert.equal(G.startSlot(GAMES, "0", { slot: "2", last: "4" }), "0", "another game was played since: that one");
  assert.equal(G.startSlot(GAMES, "4", { slot: "5", last: "4" }), "4", "a game the save hasn't got any more");
  assert.equal(G.startSlot([], null, null), null);
  // The game played last is always offered, even with no cat of yours in it yet.
  assert.deepEqual(G.pickable(GAMES, "1").map(g => [g.slot, g.current]), [["0", false], ["1", true], ["2", false], ["3", false], ["4", true]]);
  assert.equal(G.pickable(GAMES, "4").length, 4);
  assert.equal(G.gameOf(GAMES, "2").level, 1);
  assert.deepEqual(G.gameOf(GAMES, "7"), { slot: "7", n: 8, name: null, clan: null, rank: null, level: null, sandbox: false, current: false });
});

test("the Save page's changes are put under their games, in the game's order, the game's settings last", () => {
  assert.equal(G.slotOfPath("4/GameplayProgression/Level"), "4");
  assert.equal(G.slotOfPath("Shared/SettingsData/MasterVolume"), null);
  const changes = [{ path: "4/GameplayProgression/Level" }, { path: "Shared/SettingsData/MasterVolume" },
    { path: "0/GameplayProgression/Level" }, { path: "4/GameplayProgression/Experience" }];
  assert.deepEqual(G.byGame(changes).map(([slot, list]) => [slot, list.map(c => c.path)]), [
    ["0", ["0/GameplayProgression/Level"]],
    ["4", ["4/GameplayProgression/Level", "4/GameplayProgression/Experience"]],
    [null, ["Shared/SettingsData/MasterVolume"]]]);
});
