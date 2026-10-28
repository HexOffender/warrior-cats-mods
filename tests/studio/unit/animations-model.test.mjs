// studio/lib/animations-model.js: the Animations page's pure parts. An animation's id, the animations.json it
// saves, where it comes from and what it does, the switches that put settings aside, the game's sequences in
// their groups by their plain names, and the keys an emote shouldn't share.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install } from "../lib/dom.mjs";

const dom = install();
const m = await import(dom.studio("lib/animations-model.js"));

const CAT = "/Game/Art/Characters/CatMaster/Animations/";
// The game's sequences as /game/anim-sequences gives them.
const SEQS = [
  { name: "A_CatMaster_A_Final_Showdown", paths: [CAT + "A_CatMaster_A_Final_Showdown"], additive: false, label: null, group: null },
  { name: "A_CatMaster_Meow_1", paths: [CAT + "A_CatMaster_Meow_1"], additive: true, label: null, group: null },
  { name: "A_CatMaster_Pose_Photo_Mode_10", paths: [CAT + "PhotoMode/A_CatMaster_Pose_Photo_Mode_10"], additive: false, label: "Floof Nap", group: "poses" },
  { name: "A_CatMaster_Pose_Photo_Mode_2", paths: [CAT + "PhotoMode/A_CatMaster_Pose_Photo_Mode_2"], additive: false, label: "Loafing Lunar", group: "poses" },
  { name: "A_CatMaster_Sit_1", paths: [CAT + "A_CatMaster_Sit_1", CAT + "Cinematic/A_CatMaster_Sit_1"], additive: false, label: null, group: null },
  { name: "A_CatMaster_Trot_1", paths: [CAT + "A_CatMaster_Trot_1"], additive: false, label: "Trot", group: "everyday" },
  { name: "A_CatMaster_Yawn_1", paths: [CAT + "A_CatMaster_Yawn_1"], additive: false, label: "Yawn", group: "everyday" },
];

test("animId makes letters and digits from a name, unique without case", () => {
  assert.equal(m.animId("Tail wave"), "TailWave");
  assert.equal(m.animId("3 hops"), "Anim3Hops");
  assert.equal(m.animId("Wave", ["wave"]), "Wave2", "Wave and wave would be one file and one package");
  assert.equal(m.animId("Wave", ["Wave", "WAVE2"]), "Wave3");
});

test("toJson leaves out the defaults, false, empty values, _new and _info, and keeps hand-written notes", () => {
  const out = m.toJson([{ id: "Yawn", name: "Yawn", for: "cat", game: "A_CatMaster_Yawn_1", emote: true, key: "F7", loop: false,
    claws: undefined, clip: "", _new: true, _info: { clips: [] }, _note: "mine" },
  { id: "Flap", name: "Flap", for: "bird", game: "A_Bird_Flying_Loop_1", loop: true }], { other: 1 });
  assert.deepEqual(out.animations, [{ id: "Yawn", name: "Yawn", game: "A_CatMaster_Yawn_1", emote: true, key: "F7", _note: "mine" },
    { id: "Flap", name: "Flap", for: "bird", game: "A_Bird_Flying_Loop_1", loop: true }]);
  assert.equal(out.other, 1);
});

test("where it comes from and what it does are read from the animation", () => {
  const chosen = new WeakMap();
  const bare = { id: "New" };
  assert.equal(m.sourceOf(bare, chosen), "game", "nothing picked yet: the game's, which needs no Blender");
  chosen.set(bare, "file");
  assert.equal(m.sourceOf(bare, chosen), "file");
  assert.equal(m.sourceOf({ game: "A_CatMaster_Yawn_1" }), "game");
  assert.equal(m.sourceOf({ file: "animations/a.glb" }), "file");
  assert.equal(m.roleOf({ emote: true }), "emote");
  assert.equal(m.roleOf({ emote: true, replaces: "A_CatMaster_Trot_1" }), "replaces");
  assert.equal(m.roleOf({}), "scripts");
  const roles = new WeakMap(), waiting = {};
  roles.set(waiting, "replaces");
  assert.equal(m.roleOf(waiting, roles), "replaces", "chosen to replace one, before that one is picked");
});

test("switching what it does puts the settings the next choice doesn't use aside, and back", () => {
  const stash = new WeakMap();
  const a = { id: "Yawn", name: "Yawn", game: "A_CatMaster_Yawn_1", emote: true, key: "F7", claws: true, loop: true, speed: 1.5 };
  m.switchChoice(a, stash, "role", "emote", "scripts", m.ROLE_KEYS);
  assert.deepEqual(a, { id: "Yawn", name: "Yawn", game: "A_CatMaster_Yawn_1", loop: true, speed: 1.5 }, "loop and speed go on for scripts");
  m.switchChoice(a, stash, "role", "scripts", "replaces", m.ROLE_KEYS);
  assert.deepEqual(a, { id: "Yawn", name: "Yawn", game: "A_CatMaster_Yawn_1" }, "a replacement plays as the game played it");
  a.replaces = "A_CatMaster_Trot_1";
  m.switchChoice(a, stash, "role", "replaces", "emote", m.ROLE_KEYS);
  assert.deepEqual(a, { id: "Yawn", name: "Yawn", game: "A_CatMaster_Yawn_1", emote: true, key: "F7", claws: true }, "the emote's key and claws come back");
  m.switchChoice(a, stash, "role", "emote", "scripts", m.ROLE_KEYS);
  m.switchChoice(a, stash, "role", "scripts", "replaces", m.ROLE_KEYS);
  assert.equal(a.replaces, "A_CatMaster_Trot_1", "and so does the one it replaced");
});

test("For and Where it comes from put the file or the sequence aside, and bring them back", () => {
  const stash = new WeakMap();
  const a = { id: "Wave", name: "Wave", file: "animations/Wave.glb", clip: "Wave", _info: { clips: [] }, emote: true, key: "F7" };
  m.switchChoice(a, stash, "kind", "cat", "mouse", m.KIND_KEYS);
  assert.deepEqual(a, { id: "Wave", name: "Wave" }, "a cat's file has none of a mouse's bones");
  a.game = "A_Mice_Walk_1";
  m.switchChoice(a, stash, "kind", "mouse", "cat", m.KIND_KEYS);
  assert.deepEqual(a, { id: "Wave", name: "Wave", file: "animations/Wave.glb", clip: "Wave", _info: { clips: [] }, emote: true, key: "F7" });
  m.switchChoice(a, stash, "source", "file", "game", m.SOURCE_KEYS);
  assert.equal(a.file, undefined);
  assert.equal(a.emote, true, "what it does stays");
  m.switchChoice(a, stash, "source", "game", "file", m.SOURCE_KEYS);
  assert.equal(a.file, "animations/Wave.glb");
});

test("the game's sequences come in groups by their plain names, without the additive ones", () => {
  const groups = m.sequenceGroups(SEQS);
  assert.deepEqual(groups.map(([g]) => g), ["Everyday", "Photo poses", "All of them"]);
  assert.deepEqual(groups[0][1].map(s => s.label), ["Trot", "Yawn"]);
  assert.deepEqual(groups[1][1].map(s => s.label), ["Loafing Lunar", "Floof Nap"], "the poses in the game's own order");
  assert.ok(!groups[2][1].some(s => s.additive), "an additive one can't play on its own");
  assert.deepEqual(m.sequenceOptions(SEQS[6]), [{ value: "A_CatMaster_Yawn_1", text: "Yawn (A_CatMaster_Yawn_1)" }]);
  assert.deepEqual(m.sequenceOptions(SEQS[4]).map(o => o.value), SEQS[4].paths, "a name in two folders is chosen by its path");
  assert.equal(m.findSequence(SEQS, CAT + "Cinematic/A_CatMaster_Sit_1.A_CatMaster_Sit_1"), SEQS[4]);
  assert.equal(m.plainName(SEQS, "A_CatMaster_Trot_1"), "Trot");
  assert.equal(m.plainName(SEQS, CAT + "A_CatMaster_A_Final_Showdown"), "A_CatMaster_A_Final_Showdown", "no plain name known");
  assert.equal(m.plainName(undefined, "A_CatMaster_Yawn_1"), "A_CatMaster_Yawn_1");
});

test("an emote's key: the other emotes' keys in the mod and the full screen key are said", () => {
  const a = { id: "Yawn", emote: true, key: "F7" }, b = { id: "Wave", name: "Wave", emote: true, key: "F8" }, c = { id: "Spin", key: "F9" };
  const reserved = m.emoteReserved([a, b, c], a);
  assert.deepEqual(Object.keys(reserved).sort(), ["F11", "F8"], "not its own key, and not a key on something that isn't an emote");
  assert.match(reserved.F8, /Wave's key too, and only one of them would play/);
});

// ---------- whether it reached the game ----------
const MANIFEST = {
  built: "2026-10-28T10:00:00", mods: ["mine"],
  notes: { animations: { animations: ["mine/Flap", "mine/Yawn"], emotes: ["mine/Yawn"],
    replaced: { "/Game/Art/Characters/CatMaster/Animations/A_CatMaster_Trot_1": "mine/Trot" } } },
  warnings: ["animations: mine: Long: the animation is 70.0 s long; an animation can be up to 60 s",
    "animations: mine: Shake: the key F7 is mine/Yawn's emote too; only the later one plays"],
  sections: { animations: { status: "ok", mods: ["mine"], errors: [], failed: [] } },
};
const YAWN = { id: "Yawn", name: "Yawn", game: "A_CatMaster_Yawn_1", emote: true, key: "F7" };

test("animationStatus says whether an animation went in: an emote on its key, a replacement, or why not", () => {
  assert.deepEqual(m.animationStatus(MANIFEST, "mine", YAWN), { state: "in", key: "F7", also: [] });
  assert.deepEqual(m.animationStatus(MANIFEST, "mine", { id: "Flap", for: "bird" }), { state: "in", key: null, also: [] });
  assert.deepEqual(m.animationStatus(MANIFEST, "mine", { id: "Trot", replaces: "A_CatMaster_Trot_1" }),
    { state: "in", replaced: "/Game/Art/Characters/CatMaster/Animations/A_CatMaster_Trot_1", also: [] });
  assert.deepEqual(m.animationStatus(MANIFEST, "mine", { id: "Long" }),
    { state: "out", why: "the animation is 70.0 s long; an animation can be up to 60 s" });
  assert.match(m.animationStatus(MANIFEST, "gone", YAWN).why, /its mod wasn't in the last Apply/);
  assert.equal(m.animationStatus(null, "mine", YAWN), null);
  assert.equal(m.animationStatus({ ...MANIFEST, notes: {}, sections: {} }, "mine", YAWN), null, "no animations section in that build");
});

test("animationsSummary says what's in the game, with keys, and what's left out", () => {
  const anims = [YAWN, { id: "Flap", name: "Flap" }, { id: "Long", name: "Long" }];
  assert.equal(m.animationsSummary(MANIFEST, "mine", anims),
    "In the game: Yawn (F7), Flap; left out: Long (the animation is 70.0 s long; an animation can be up to 60 s).");
  assert.equal(m.animationsSummary(MANIFEST, "mine", [{ id: "Long", name: "Long" }]),
    "Nothing here went in the game; left out: Long (the animation is 70.0 s long; an animation can be up to 60 s).");
  assert.equal(m.animationsSummary(null, "mine", anims), null);
});
