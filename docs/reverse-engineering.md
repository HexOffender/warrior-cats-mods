# Reverse engineering notes

Everything we've worked out about how *Warrior Cats: Clans of the Forest* works inside, in one
place. wcmods is built on these findings; the SDK ([SDK.md](SDK.md)) is the part meant for using
them. The game's rules (combat, progression, exploration, clan life, items, quests and NPCs) have
their own pages under [mechanics/](mechanics/README.md); this page covers the engine side and
links to them.

**Adding to it:** put a finding under its topic, and say how it was confirmed, e.g. "seen in game",
"matches the save" or "read from the code". Flag guesses as guesses. Addresses are for the build
below and move with game updates; offsets inside objects usually survive small updates. Move a
question from *Open questions* when it's answered.

## The build these notes are for

| | |
|---|---|
| Game | Warrior Cats: Clans of the Forest, Steam app 3960600, build 26184573 (patch 1.1, 2026-10-26); the notes were made on build 24847281, the first release |
| Engine | Unreal Engine 5.7 (Shipping), project name `Wrc` |
| Exe | `Wrc\Binaries\Win64\Wrc-Win64-ShippingDRM.exe`, 183,669,832 bytes, SHA-256 `cd8aafb4d2a423bd…` (on 24847281: 183,670,344 bytes, `f50eb374f8611e4e…`; its PE timestamp, 1974, is a placeholder) |
| Code | C++ classes are `Swt…` (the studio's shared framework) and `Wrc…` (this game), in `/Script/Wrc`; Blueprints are `BP_…_C`, widgets `WBP_…_C` |
| UE4SS | v3.0.1 Beta, Git 83330635 (`experimental-latest`) |

### Game updates

- **Build 26184573, patch 1.1 (2026-10-26):** the patch adds mouse control of the camera, bug
  fixes and quality-of-life changes. Nothing wcmods reads moved: every class in `game.HIDDEN` is
  the same size, every signed member is where it was (`python wcmods.py game signatures check`),
  and the level component, which had no signature then, was read in game at its old offsets: the
  level at +0x120 and the level cap at +0x124 (20, 20) and the stats at +0x154–0x168 (233, 199,
  189, 199, 180, 100) matched the save's `Stats`. The anchor functions `signatures.py` keeps (combat,
  status and detection code around `0x1417B8000`–`0x1417DC000`) each sit 0x260 later than on
  24847281; the code addresses elsewhere in these notes are still 24847281's unless they say so.
- **The level component signed (2026-10-28, on 26184573, from the exe alone):** until then it had no
  signature, so every update would have switched your cat's level and stats off, moved or not. The
  cause, read from the code:
  - **Functions come in parts.** MSVC gives a function that saves registers in stages several
    `.pdata` entries: the first with the prologue, and the rest chained to it (`UNW_FLAG_CHAININFO`
    in their unwind info). 221,277 of the exe's 563,063 entries are such parts, of 69,628 functions,
    and every one of those functions' parts lie next to each other. `pe.Image.function_at` answered
    the first part only, so the level component's own code was searched for 10, 15 and 81 bytes; its
    stats function alone (`0x1417C6410`) is 1,400. It now joins the parts (`whole_functions()`), which
    every class's search gets.
  - **That was the whole cause.** The level and the cap (+0x120, +0x124) are members of its parent,
    `USwtQuestLevelComponent` (SwtQuest), but the class's own code reaches them once it's read whole:
    its start-up override (`0x1417C6210`, vtable +0x3F8) stores the cap (`mov [rsi+0x124],eax` at
    `0x1417C6252`) and calls the parent's level setter `0x141658870` directly (at `0x1417C6326`), which
    `class_code()` takes in as a direct callee; its stats function reads the level (`[rbx+0x120]` at
    `0x1417C6629`). `make()` run with whole functions and no anchors for the class at all gives
    signatures for all eight members (the level in 3 separate instructions, the cap in 2).
  - **Its old anchors were no help.** They were fighter-stat functions (`0x1417D8270`, `0x1417D70C0`)
    that touch none of its offsets: read whole, they have no `[reg+0x120]`, `+0x124` or
    `+0x154`–`+0x168` operand. Two of the parent's functions replace them, for redundancy: the XP
    setter `0x141658A90` (found with `callers.py` on the level setter), which adds a fourth separate
    instruction on the level and a third on the cap, and the level setter itself, still searched if a
    rebuild stops the start-up calling it. The parent's start-up `0x141658C00` (found with `xrefs.py` on
    `Gameplay.Exploration.MaxLevel`) isn't one: its only access to the class, the cap's store, is the
    same bytes as `0x1417C6210`'s as far as a signature reaches, so with both searched neither store
    gives a unique pattern; as an anchor it cost the cap its signature in `0x1417C6210` (2 separate
    instructions instead of 3).

  More code searched showed false sites, some already in `signatures.json`. The level component's
  start-up code reads +0x154 of the object behind the global at `0x14A8A6E08` (after an IsA check),
  not its own Prowess; three of the combat component's Stance sites (in `0x141D0B220`) were
  `lea rax,[rbp+0x1A0]`, a stack slot under a frame pointer (`lea rbp,[rsp-0x7D8]`); and the combat
  component's code has vtable calls (`call [rax+0x1C8]`, in `0x141C67940`) at member offsets.
  `signatures.py` now leaves out an access whose base register holds a stack address or a pointer read
  from a global, by a straight read of the function (`_foreign`), and one wider than the member
  (`_access`). `make()` refuses a class with no signature at all instead of writing it.

  Votes are counted by instruction (since a review of this work, the same day). Sites around
  neighbouring instructions overlap and capture the same instruction, and each capture used to count
  as a vote, so a move could be followed on one instruction's word. In the `signatures.json` before
  this work, the detection component's ConeDistance, SoundRadius, ProximityDistance and
  ZoneEntryDistance were each captured in one instruction only, by 2 or 3 sites; in the first one made
  with whole functions, the cap's 3 votes were 2 instructions and ProximityDistance's 3 were the one at
  `0x1417B8123` (it has 2 separate ones now). `check()` now counts each captured displacement once,
  `make()` gives a member sites until 3 separate instructions are captured (none for an instruction a
  site already has), and each site records where it starts on the build it was made on (`"at"`), so
  the count can be checked without the exe (`signatures.instructions()`).

  The result (`python wcmods.py game signatures make`): the level component has 17 signatures over
  all eight members, in separate instructions: the level 4, the cap 3, Prowess 3, Strength 4,
  Resilience 4, Instinct 4, Agility 2, Stamina 2. 34 of the 45 members have a signature (23 before),
  and none lost theirs; 26 are in two separate instructions or more, which a move needs. How it was
  confirmed:
  - `signatures.check()` on the installed exe with its fingerprint changed, so nothing counts as
    the exe they were made on: all eight are found "same" by their signatures (with the old code and
    file: all eight "lost"), and every other class as before or better.
  - The 26 displacements those signatures capture moved by +4 in memory (the file untouched):
    `check()` follows all eight (0x120→0x124 … 0x168→0x16C) and disturbs no other class.
  - Each of the 17 sites read in the disassembly: every one's base register is `this` (rcx, or the
    rbx/rsi it was copied to at the start).
  - `tests/unit/test_signatures.py`, and the selftest's update check (`python wcmods.py selftest`).

  Not seen yet: a real update moving it ([verified.md](verified.md#not-yet-confirmed-in-game)).

## How we find things

- **Strings to code:** scan the exe for RIP-relative `lea`/`mov` instructions whose target is a
  string's address. `tools/re/xrefs.py <exe> "<text>"` lists both. Tuning keys
  (`Gameplay.Exploration.Camera.TurnRate.Yaw`) lead to the code that loads them. Each key is read
  into a member, so a loader reveals a struct's layout (`tools/re/tunemap.py` maps each key to its
  offset from a dumpbin listing of the loader).
- **Reflection data:** UHT's property tables survive in the exe. Each entry is: name pointer at
  +0, RepNotify pointer at +8, flags (u64) at +16, generator flags (u8) at +24, array dimension
  (u16) at +48 and offset (u16) at +50. Find a pointer to a property's name and decode the table
  around it. Enums are tables of `{const char* name, int64 value}`, found through each enum's UHT
  parameters, which name it (*The game's enums*). `tools/re/uht.py` does both, and `uht.py <exe> lua`
  checks every enum number wcmods' Lua keeps against the exe.
- **Disassembly:** `dumpbin /disasm:nobytes /range:<start>,<end>` from Visual Studio. Function
  starts follow `int 3` padding. Without Visual Studio, `wcmods/exe/x64.py` decodes each
  instruction's length and operands (its memory operand's base and displacement, RIP targets,
  branches), though it doesn't name instructions. A function's `.pdata` entry can be only its first
  part: `pe.Image.function_at` gives the whole function (*Game updates*).
- **From members to code:**
  - `tools/re/storemap.py` maps keys to members for loaders that store straight to `this`.
  - `tools/re/dispscan.py <exe> 38C,390,394 2` finds code that uses several members of one
    struct (float instructions with those offsets), which is how the damage formula was found.
  - `tools/re/callers.py <exe> <address>` lists the direct calls to a function.
- **Not every tuning key is in the exe.** About half of `TuningData`'s keys never appear as whole
  strings: some are built from parts (`Gameplay.Exploration.Detection.%s`), others are presumably
  read by Blueprints. A key the code asks for that the table lacks, though, is a real bug (see
  *What traits do*).
- **Data tables:** `tools/re/mechanics_tables.py` fills the generated tables in `mechanics/` from
  the extracted CSVs, with names from `Strings_EN.csv`.
- **Crash dumps:** `cdb -z <crash folder>\UEMinidump.dmp -c ".ecxr; r; u @rip-0x30 L20; kn 12; q"`.
- **Live game:** UE4SS Lua probes (see *UE4SS in this game*). For reading memory from outside,
  `tools/re/memscan.py` uses ReadProcessMemory. Never stop a debugger attached to the game
  without detaching (`qd`): exiting kills the game.
- **The game bridge:** with code mods allowed, `python wcmods.py lua "<code>"`, `inspect` and `find`
  run Lua in the running game and print what comes back ([scripting.md](scripting.md#the-game-bridge)).
  It's the quickest way to try a property, a function or an offset.
- **The class dump:** UE4SS's `GenerateSDK()` and `GenerateUHTCompatibleHeaders()` (run through the
  bridge, or its keybinds) write every loaded class with its properties, offsets and functions. Run in
  the world, the gameplay Blueprints are in it too. Ours is kept in `vanilla/sdk/` (not committed), with
  an index of the game's own modules.
- **Game files:** `python wcmods.py files "<pattern>"` and `extract`. In cooked packages the name
  map is readable, but imports are hashes, so a Blueprint's parent class isn't stored by name. A
  survey in game gets parents instead (*Game objects*).

## Files and formats

### Paks and containers

Detailed in [SDK.md, Game files, repacking and new content](SDK.md#game-files-repacking-and-new-content). The key facts:
- `pakchunk0-Windows.pak` is pak version 12, Oodle-compressed, with no path-hash index
  (`bHasPathHashIndex = 0`), so the engine finds files through the full directory index.
  - **File names are UTF-8 with their exact byte length and no terminator.** Folder names are
    FStrings whose length includes the NUL.
  - Earlier wcmods wrote file names with a NUL, and the engine never matched them. The engine's
    lookup (`FPakFile::Find` at `0x142918420`, then the directory-tree lookup at `0x142919A40`)
    matches the folder, then the exact file name. (Found by reading the mounted `FPakFile` from
    memory and disassembling those functions; fixed in PR #6.)
- `pakchunk0-Windows.utoc/.ucas` is IoStore TOC version 8: a 144-byte header, 12-byte chunk IDs,
  64 KB Oodle blocks, BLAKE3-160 chunk hashes, and an `IoCn` v5 container header. A package's
  chunk ID and header entry (imports, shader maps) can be reused for a patched copy.
- **Mods load from `Paks\~mods\`**, and a `_P` suffix gives patch priority. **Unsigned paks and
  containers are accepted**, so wcmods' own load.
- **A pak there is read only with a `.utoc`/`.ucas` of the same name beside it**, and the reverse.
  Seen on build 26184573 (2026-10-27): `zzz_WCMods_P.pak` holding text edits alone was ignored (the
  HUD named the renamed cat "Cat 1", and `BlueprintPathsLibrary.FileExists` didn't find the pak's
  `Wrc/WCMods/BuildInfo.json` while it found the game's `Strings_EN.csv`). The same pak was read once
  a container sat beside it, an empty one (no chunks but its header) included. Builds before that
  shipped a container only with cooked packages, so their text and table edits were lost whenever a
  build had none.
- **The compression is Kraken throughout.** Every compressed block's Oodle header, in both
  containers (140,969 in the `.ucas`, 639 in the pak, surveyed on 2026-10-26), is decoder type 6
  (Kraken) with no checksums; one pak block is a stored (`0xCC`) Kraken block. So `wcmods/formats/kraken.py`,
  a pure-Python port of the Kraken parts of [ooz](https://github.com/powzix/ooz) (GPL-3.0), decodes
  everything: 5,932 blocks (339 MB) came out identical to `oo2core_8_win64.dll`, at about 4 MB/s.
  An `oo2core` DLL named by `"oodle_dll"` in `wcmods.json` is used instead when it's there, through
  `OodleLZ_Decompress`; the fixtures in `tests/kraken` were made with its `OodleLZ_Compress`
  (`tools/make_kraken_fixtures.py`).

### Cooked packages and DataTables

Worked out on 2026-10-24 on `DT_QuestObjectsInfo`. `wcmods/formats/cooked.py` reads and writes them; its
selftest check decodes all 412 rows, re-encodes them and rebuilds the package byte for byte.

**A zen package (UE 5.7):**
- **Summary:** 60 bytes: `bHasVersioningInfo`, `HeaderSize`, the package name (index, number),
  `PackageFlags`, `CookedHeaderSize`, then the offsets of the imported public export hashes, import
  map, export map, export bundle entries, dependency bundle headers and entries, imported package
  names, and (new in 5.6/5.7) the cell import and export maps.
- **Name map:** an FNameBatch:
  - the count, the string bytes and the hash version (`0xC1640000`);
  - a u64 hash per name: CityHash64 v1.1 of the name in lower case (`wcmods/formats/cityhash.py`; the
    constant k1 is `0xb492b66fbe98f273`);
  - big-endian u16 lengths (bit 15 marks UTF-16), then the strings.
- **Then:** an i64 pad size and that many bytes, so the next field is 8-aligned (true of all 881
  packages checked), then an i64 bulk data map size and its 32-byte entries, then the sections
  above.
- **Export map:** 72-byte entries. `CookedSerialOffset` counts from `HeaderSize`, where the export
  data starts.
- **Growing a package works:**
  - Add names (with their hashes), shift every offset after the name map, and fix the export's size.
  - The container's store entry has no sizes, so the game's chunk ID and header entry still fit.
- **Unversioned properties:**
  - **Header:** u16 fragments: skip count in bits 0–6, "has zeroes" in bit 7, last fragment in
    bit 8, value count in bits 9–15. Then a zero mask (8, 16 or 32×n bits) when any fragment has
    zeroes.
  - **Values:** the values that aren't zero, in the struct's property order. A field left out of
    the header gets the struct's default.
  - **How fields are stored:**
    - A gameplay tag is a nested struct: header `0x0300` and an FName.
    - FText is i32 flags and an i8 history type. 11 is a string table entry (table FName plus key
      FString); 0 is base text (namespace, key and source string, as FStrings).
    - A soft object path is the package FName, the asset FName and a sub-path FString.
    - Byte enums are one byte, left out when zero.
- **A DataTable export:**
  - the object's own properties: an unversioned header and `RowStruct` (an i32 import index);
  - a u32 `HasGuid` = 0, then an i32 row count;
  - each row: its FName and then the row struct.
  - The package file tag follows the export.
- **An empty FString** is written either as length 0 or as a length-1 lone terminator. Keep which,
  to get the same bytes back.

### New packages and textures

Worked out on 2026-10-24 for icons and accessory looks (`wcmods/formats/texture.py`), and verified in game:
an item's icon and a worn collar, both from packages the game hasn't got.

**IDs come from names** (checked against the game's own container by the selftest):
- **Package ID:** CityHash64 of the package name in lower case, as UTF-16LE
  (`/game/art/.../t_ui_icon_inventory_horsetail_d`).
- **Chunk ID:** the package ID (u64), a u16 index (0), a pad byte, then the chunk type: 1 for the
  package itself, 2 for its `.ubulk`.
- **An export's public hash** (export map entry +56): CityHash64 of the object's name in lower case,
  as UTF-16LE.

**A texture package** (`Texture2D`, one export):
- **Pixel format:** an FString such as `PF_DXT5` in the export, with the width and height as two i32
  16 bytes before it.
- **Mips:** one bulk data map entry each (offset, duplicate offset, size, flags). With flag `1 << 8`
  the mip is in the `.ubulk`, at that offset; otherwise it's inline in the export data.
- **The game's:**
  - Inventory icons are `PF_DXT5` 512 x 512, one mip, inline; accessories' icons are `PF_DXT5`
    256 x 256.
  - Accessory looks (`T_A<slot>_<name>_<n>_BC`) are `PF_DXT1` 2048 x 2048 with 12 mips, the big ones
    in the `.ubulk`.
  - 13 head accessories' looks are packages with more than one export.

**Making a new one:** copy one of the game's textures of the same size and format, then:
- put new DXT blocks at each mip's place;
- rename the package and the object in the name map (with their name hashes), and fix the export's
  public hash;
- add it to the mod container under its new ID, with the copied texture's container header entry
  (imports, shader maps) and its `.ubulk` as a type-2 chunk.
The game loads it from a soft path (an item's `Icon`) or a soft reference (an accessory's look) like
one of its own. Nothing else checks it: no asset registry entry was needed.

### Skeletal meshes

Worked out on 2026-10-27 for accessories' models (`wcmods/formats/skelmesh.py`). Every accessory's mesh
and the cat's body (`SK_CatMaster`) read and write back byte for byte, morph data re-encoded included
(the selftest checks all 45), and a copy with new geometry renders on a cat in game.

**The package:** an `AnimCurveMetaData` export (6 bytes), one `UMorphTarget` per body-shape morph
(`SHP_Slim`, `SHP_Brawny`, `SHP_Chubby`, ...; the body has 67, accessories 3 to 7, some head ones
none), then the mesh. Everything is inline: no `.ubulk`, no streamed LODs.

**The mesh export:** its unversioned properties, a u32 HasGuid, then:
- `FStripDataFlags` (5, 0), `ImportedBounds` (7 doubles; the properties hold a second copy of the
  same 56 bytes), the materials (`FSkeletalMaterial`: material, slot name, a u32 "imported name
  follows" (0), `FMeshUVChannelInfo` (two u32 flags, four floats), then a u32 0), the reference
  skeleton (56 bones for an accessory, 57 for the body: FName and parent; bind poses as 10 doubles;
  the name map);
- a u32 bCooked (1), the LOD count (1 to 5) and each LOD's render data;
- a 112-byte tail whose bytes 106 and 107 are the in-lined and non-optional LOD counts.

**A LOD:**
- `FStripDataFlags`, bIsLODCookedOut (0), bInlined (1), `RequiredBones` (u16, every bone);
- the render sections, each with its own strip flags (5, 1: duplicated vertices left out): material
  (u16), base index, triangles, bRecomputeTangent, a u8 mask channel, bCastShadow,
  bVisibleInRayTracing, base vertex, an empty cloth mapping array, `BoneMap` (u16 indices into the
  skeleton), vertices, MaxBoneInfluences, an i16 -1, a zero GUID and -1 (no clothing), bDisabled;
- `ActiveBoneIndices` (the bones used and their parents), then `BuffersSize`: exactly the length of
  the streamed data that follows.

**The streamed data:**
- strip flags, the index size (u8: 2), the indices as a bulk array (element size, count, data);
- the position buffer: stride 12, count, then `FVector3f`s;
- the vertex buffer: strip flags, UV channel count, vertex count, two u32 0s (half-precision UVs,
  8-bit tangents), the tangents (two `FPackedNormal`s a vertex, TangentX with w 127 and TangentZ with
  the binormal sign in w) and the UVs (half floats);
- the skin weights: strip flags, six u32s (variable bones 0, influences 8 in LOD 0 and 4 below, the
  total, vertices, 16-bit indices 0, 16-bit weights 0), then per vertex the bone indices (into the
  section's `BoneMap`) and then as many weights, u8s summing to 255; an empty lookup buffer (strip
  flags, 0, element size 4, count 0);
- the vertex colours (strip flags, stride 4, count, white in the game's), an empty skin weight
  profile map, 32 bytes alike in every mesh (six -1s, 1, 0), a u32 "morph data follows";
- the morph data (`FMorphTargetVertexInfoBuffers`): a u32 array, then per morph its smallest and
  largest delta (`FVector4f`: xyz the position's, w the normal's), its first batch and batch count,
  the total, and the position and normal precisions (0.004 cm and 1/2048). The array starts with a
  10-u32 header per batch of up to 64 moved vertices (data offset in bytes, packed index and position
  bit widths with a has-normals bit and the count, the first vertex, the position minimums, the
  normal bit widths and their minimums), then each batch's bit-packed elements from the u32-aligned
  data offset (index minus the first vertex minus its place in the batch, the position delta and the
  normal delta, each a quantized integer above the batch's minimum), then 3 zero u32s;
- 14 bytes alike in every mesh.

The LOD buffers keep the morphs in the order of the mesh's `MorphTargets` property, an array of the
morph exports' indices in the properties. Each `UMorphTarget` export is its properties (the mesh)
and HasGuid, strip flags, a u32 1, the LOD count, and per LOD: 1, the vertices it moves, how many
deltas it had before quantizing, its section indices, bGeneratedByEngine and a 0.

**Space:** centimetres, Z up, the cat facing +Y, triangles clockwise seen from outside (the cross
product of the edges points in).

### Animations

Worked out on 2026-10-27 from the game's files, and checked in game: a sequence wcmods wrote (a copy of
the game's Stretch with a wagging tail, in a new package) loaded and played on the player's cat.

**What the game has** (`/Game/Art/Characters/<Who>/Animations/`): 757 `AnimSequence`s (`A_…`) and 708
`AnimMontage`s (`AM_…`). The cat has 247 sequences and 149 montages; each roaming animal and boss
(badger, bird, dog, fox, mouse, rabbit, rat, snake, squirrel) has 30 to 40 of its own. Also blend spaces
(`BS_Lean`), aim offsets (`A_CatMaster_AO_*`) and pose assets (`PA_Body`, `PA_Face`... the body-shape
sliders, played by the AnimBlueprint). Every montage plays in the slot `DefaultSlot` (group
`DefaultGroup`).

**Skeletons:** one per kind of animal. The cat's is `/Game/Art/Characters/CatMaster/Skel/SK_CatMaster_Skeleton`,
58 bones: `root`, `Spine_base`, `spine_01`–`05`, `neck`, `head`, `mouth`, `tongue_01`–`03`, the ears,
eyelids, eyes, cheeks and `mustache_L/R`, `Breast`, `belly`, `butt`, front legs (`clavicle_blade`,
`UpperArm_f`, `Forearm_f`, `paw_f`, `Finger_f`), back legs (`thigh_b`, `calf_b`, `HorseLink_b`, `ball_b`,
`thigh_cor_b`), `tail_01`–`05`, then `Camera`, `Camera_ref` and `Target_ref`. The body mesh uses the first
57, accessories the first 56. The animals' have 24 (bird) to 46 (squirrel) bones with names of their
own (`Root`, `Rat_Pelvis`, `Fox_Head`...). The skeleton export's reference skeleton is read like a
mesh's (bones as FName and parent, then poses as 10 doubles: rotation x, y, z, w, translation, scale).
A mesh keeps its bones in an order of its own (the cat's starts `root`, `spine_01`...), not the
skeleton's; the sequences' track tables index the skeleton's.

**A sequence package:** one `AnimSequence` export, plus one export per notify object for sequences with
notifies (footstep sounds: `BP_AnimStepNotify_C`, `AnimNotify_PlayNativeAudioEvent`). It imports its
skeleton and its compression settings (`/Engine/Animation/DefaultAnimBoneCompressionSettings`,
`DefaultAnimCurveCompressionSettings`, `DefaultVariableFrameStrippingSettings`, or the ACL plugin's).
Everything is inline.

**The export:**
- **Properties** (unversioned), the class's own before its parents': for `A_CatMaster_Meow` the
  bone, curve and frame-stripping settings (indexes 0–2, imports), `SequenceLength` (20, a float),
  `Skeleton` (24) and `AssetUserData` (26, one null). The birds' and some foxes' add
  `PlatformTargetFrameRate` (17, a cooked `FPerPlatformFrameRate`: a u32 1, then 24 and 1). Sequences
  with notifies or root motion have more. The sequence export isn't always the first: notify objects
  can come before it.
- a u32 HasGuid (0), the `SkeletonGuid` (16 bytes, the skeleton's), `FStripDataFlags` (5, 0), a u32
  bSerializeCompressedData (1);
- **the compressed data** (`FCompressedAnimSequence`): i32 `CompressedRawDataSize` (only for
  statistics), the track table (an i32 array: each track's bone in the skeleton; the cat's sequences
  have 56 or 57 tracks, bones 0 onwards), the curve names (an array of FNames), an i32 byte count and
  a u32 "in bulk data" (0), the bone data (that many bytes), the bone codec's name (an FString, the
  codec object's name in the settings: `AnimCompress_PerTrackCompression_5`), the curve codec's path
  (an FString), an i32 count and the curve bytes, then the bone codec's own fields;
- the package file tag follows the last export.

**The codecs** (the bone codec's name picks one; `DefaultAnimBoneCompressionSettings` holds
`AnimCompress_BitwiseCompressOnly` (two), `AnimCompress_PerTrackCompression` (eight, `_1` to `_7`)
and `AnimCompress_RemoveLinearKeys`). Of the game's 757 sequences:
- **ACL** (519, `AnimBoneCompressionCodec_ACL_0`, with `/ACLPlugin/ACLAnimBoneCompressionSettings`): the
  bone data is an ACL stream ([ACL streams](#acl-streams)); the codec's fields are an i32 key count and a
  u32 0. Most animals' and
  bosses' sequences and 137 of the cat's. Every sequence of the squirrel, bird, fox, badger, dog and
  snake is in ACL.
- **Unreal's per-track codec** (229: 99 of the cat's, the mice, rats and most rabbit ones). Its fields:
  i32 key count, four u8s (key encoding 2 = per-track, then the translation, rotation and scale formats,
  6 = identity, unused here), then i32s: the byte stream's size, the track offsets' count (2 per
  track), the scale offsets' count (1 per track) and the scale offsets' stride (1). The bone data is the
  track offsets (translation, rotation), the scale offsets, then the byte stream.
- **Unreal's constant-key codec** (9 of the cat's, `AnimCompress_BitwiseCompressOnly_0`): key encoding
  0, translations and scales as 3 floats (format 0), rotations as 3 floats (format 1); four offsets per
  track (offset and key count for translation and rotation) and two per scale.

The codec's object only matters for finding it: the engine decodes Unreal's formats by the key
encoding and formats in the data, so a sequence of full-precision per-track keys under the template's
`AnimCompress_PerTrackCompression_5` plays (seen in game).

**A per-track track** (at its offset in the byte stream; -1 = identity: no translation, no rotation):
- a u32 header: key count (bits 0–23), flags (24–27), format (28–31). Flag bits 0–2 say which of x, y, z
  are stored (the others are 0; none set means all three), bit 3 that a frame table follows;
- format 1 (`Float96NoW`): a float per stored component. Format 2 (`Fixed48NoW`): a u16 per stored
  component; a rotation's is (v - 32767) / 32767, a translation's or scale's (v - 255) / 1 (Unreal's
  `(1 << (15 - 7)) - 1` offset and an integer `255 >> 7` factor: steps of a whole unit; the game only has
  scale 1.0 = 256 in it). Format 3 (`IntervalFixed32NoW`): first a (minimum, range) pair of floats per
  stored component, then a u32 per key, x in bits 21–31, y in 10–20, z in 0–9, each `min + range * q / (2^bits - 1)`;
- rotations drop w (w = sqrt(1 - x² - y² - z²), so w is kept positive);
- one key: the same all through. Keys without a frame table are spread evenly over the sequence (2
  keys: the first and the last frame); with one, the table follows the keys, 4-aligned, a u8 frame
  number per key (u16 from 256 frames on);
- each track is 4-aligned. The game writes each bone's scale, translation, then rotation.

Every track's size computed this way ends where the next begins in all 229 per-track sequences, and
the keys decode to unit rotations that move smoothly, next to the skeleton's reference pose.

**The curves** (morph targets the sequence drives: `shp_claw_hiden_l/r`, `shp_claw_b_hiden_l/r` (claws
in), `shp_pupil_l/r`, `shp_comisure_*` (mouth corners), `shp_extensor_*`, `shp_fat_l/r`...; the animals'
have none). With `AnimCurveCompressionCodec_CompressedRichCurve` the bytes are a 12-byte header per
curve (u8 format (1 = constant), u8 key-time format, u8 pre- and post-infinity, a float value (or i32
key count), an i32 offset of its keys) and then the keys. `A_CatMaster_Meow` holds all six of its curves
at 1.0 (claws in, pupils normal).

**Time:** 30 keys a second (`A_CatMaster_Meow`: 80 keys, 2.633 s; `Stretch_1`: 161 keys, 5.333 s), but
24 where `PlatformTargetFrameRate` says (the birds'); a key's time is its place along the sequence,
(key / (keys - 1)) * length, and every sequence's length is (keys - 1) at its rate.

**Space:** a key is the bone's transform relative to its parent, in centimetres, as the reference pose
(`Spine_base` -10.9 cm along Y and 17.5 cm up from `root`; the spine and tail bones point along -Y).

**Making one** (wcmods' way, seen in game): copy one of the game's sequences on the same skeleton
without notifies (`A_CatMaster_Meow` for cats), put new per-track keys in it (format 1 for every
track, scale, translation and rotation), its key count and `SequenceLength`, then rename the package
and the export (name map and public hash) and add it to the mod container with the template's
container header entry, as for textures. The game loads it by path
(`KismetSystemLibrary:LoadAsset_Blocking`), like a mod's mesh. A copy left with the template's six
curves keeps the claws in; setting the four `shp_claw*_hiden` ones to 0 shows them (seen in game).
- **A copy of an ACL sequence** (the animals with no other kind): its bone compression settings import
  swapped for `/Engine/Animation/DefaultAnimBoneCompressionSettings` (the import map entry's export hash,
  the container header's package ID at the same place, and the name in `ImportedPackageNames`, the
  header's last section: a name batch and an i32 number a name), its codec name for one of those
  settings' codecs, and its curves dropped (they're in ACL too). A bird made that way played (seen in
  game).

### ACL streams

Worked out on 2026-10-27 from ACL 2.1.0's sources (github.com/nfrechette/acl, MIT:
`core/impl/compressed_headers.h`, `compression/impl/write_*.h`, `decompression/impl/*`), then checked
against all 519 of the game's ACL sequences and against the game's own poses (below). `formats/acl.py`
decodes them; wcmods only reads ACL, and writes its own sequences in Unreal's per-track codec.

**What the game has:** every stream is ACL 2.1.0 (tag `0xAC11AC11`, version 10), uniformly sampled
(algorithm 0), of transforms (track type 12, `qvvf`), with no database. Rotations are always format 3
(drop w, variable bits), translations and scales format 1 (variable). Four are additive (default scale
0: the cat's aim offsets `A_CatMaster_AO_CC`, `_CL`, `_CR` and the cinematic `A_CatMaster_Meow_1`); 350
have several segments, 252 are wrap-optimized (loops), 112 have stripped keyframes and 133 no scale.

**Layout** (little-endian; offsets from the stream's start unless said):
- **Headers:** a raw buffer header (u32 size, the stream's length; u32 hash), then the tracks header
  (24 bytes): u32 tag, u16 version, u8 algorithm, u8 track type, u32 tracks (one a sequence track, in its
  track table's order), u32 samples, f32 sample rate, and u32 flags. The flags: bit 0 has scale, bit 1 the
  default scale (0 for an additive sequence, or 1), bit 2 the scale format, bit 3 the translation format,
  bits 4–7 the rotation format, bit 8 a database, bit 9 trivial defaults (only says the compressor's
  defaults were the identity; it isn't what decides them), bit 10 stripped keyframes, bit 30
  wrap-optimized (the repeated last sample is left out, so Unreal's key count is the samples + 1, the last
  key the first again).
- **The transform tracks header** (52 bytes at 32): segments; animated sub tracks (all of them, then
  rotations, translations, scales); constant samples (rotations, translations, scales); then offsets from
  this header: the database (`0xFFFFFFFF`), the segment headers, the sub track types, the constant data
  and the clip range data. With several segments each segment's first sample follows (u32s, then
  `0xFFFFFFFF`).
- **Sub track types:** 2 bits a track, from the most significant, 16 to a u32: 0 default, 1 constant, 2
  animated. The rotations' words, the translations', then the scales' (left out without scale).
- **Constant data:** rotations in groups of 4, x of each, then y, then z (w left out); then translations
  and scales, 3 floats each.
- **Clip range data,** for the animated sub tracks: rotations in groups of up to 4 (the group's minimum
  x, y, z and extent x, y, z, a float each per member); then a translation's or a scale's minimum and
  extent (6 floats).
- **A segment** has a header (16 bytes; 20 with stripped keyframes): the bits one sample takes (all, the
  rotations', the translations') and the offset of its data, and with stripped keyframes a mask of the
  samples it keeps (sample k at bit 31 - k). Its data: a byte per animated sub track, its bits per
  component (0: constant in this segment; 31: raw floats; rotations padded to a multiple of 4); with
  several segments, 2-aligned, the segment ranges (rotations in groups of 4: minimum x of the 4, y, z,
  extent x, y, z, a byte each, or for a sub track constant in the segment its 16-bit sample split high
  and low; 6 bytes a translation or scale); then, 4-aligned, the samples as big-endian bit fields, each
  sample's rotations, then translations, then scales.
- **A value** is `clip_min + clip_extent * (segment_min + segment_extent * q / (2^bits - 1))`, the
  segment's numbers in 255ths; one constant in its segment is `clip_min + clip_extent * sample / 65535`,
  and a raw one its floats as they are. A rotation's w is `sqrt(|1 - x² - y² - z²|)`: near a half turn the
  quantized x, y, z can come out a little over a length of 1, and ACL takes the absolute value (4046
  samples in 94 of the game's sequences; leaving w at 0 there turns a bone up to 3 degrees otherwise),
  then normalizes as it interpolates.
- **Stripped keyframes** lie between the samples the segment keeps: lerped (rotations nlerped) by
  where they are between them. Every segment of the game's keeps its first and last sample, so that's
  all that's needed.

Every segment's sample size computed from the bits per component adds up to the size its header gives,
in all 519 streams.

**Defaults:** what a stream leaves at its default is what Unreal's ACL plugin gives it
(`ACLDecompressionImpl.h`): in a sequence that isn't additive, a rotation or translation is the
skeleton's reference pose for the track's bone (the plugin compresses against
`USkeleton::GetRefLocalPoses`); in an additive one, the identity. A scale is always the header's default
scale, whatever the reference pose's: the prop `A_GPE_TiedBranch_Falling` has no scale sub tracks and its
root's reference scale is 100, and it plays at 1. Where a mesh rests otherwise than its skeleton, no
sequence of the game's that isn't additive leaves a bone at default, so the mesh's rest pose never comes
into it.

**Checked in game** (2026-10-27, build 26184573): the game's own ACL sequences played on the cat,
paused at a key (`Montage_Pause`, `Montage_SetPosition`) and read bone by bone (`GetSocketTransform`,
parent bone space), against the decode of that key:
- `A_CatMaster_Get_Up_1` (6 segments, stripped keyframes) at keys 30, 27 and 8 (27 and 8 stripped);
  `A_CatMaster_NPC_Sniffing_1` at key 47 (stripped, the tail tip turning 2.1 degrees from the key before);
  `A_CatMaster_Powerfull_Loop_1` at key 30 (stripped, the mouth 1.5 degrees from the key before);
  `A_CatMaster_Run_1` (wrap-optimized, with scale) at keys 10 and 19 (its last).
- The rotations of `Spine_base`, `spine_01`, `neck`, `head`, `mouth`, the ears and `tail_01` and `tail_05`
  were the decode's (0.000 degrees apart). The other spine and tail bones, `belly` and `butt` were off by
  the same small angles in every pose and in a per-track control (`A_CatMaster_Stretch_1`): the
  AnimBlueprint's own lean and tail layers. The legs' IK moves them more.
- Translations can't be compared this way: the per-bone translation retargeting gives most bones their
  translation from the skeleton.

### The save

`%LOCALAPPDATA%\Wrc\Saved\SaveGames\WrcGame.sav`:
- **The container:** a GVAS file whose `SwtSaveGame` holds `Hash`, `GamerId`, `Version`,
  `saveSlots` and `CompressedData`.
- **`CompressedData`:** what Unreal's `FArchiveSaveCompressedProxy` writes: one compressed archive
  per 128 KiB of payload, back to back. Each is an 8-byte tag (`C1 83 2A 9E 22 22 22 22`), the block
  size (128 KiB, int64), a compressor byte (3: zlib), a summary (compressed and uncompressed sizes,
  two int64s), one entry per block (the same pair), then the zlib data. A new save is one archive
  (about 80 KiB of JSON); a long-played one is several, and a reader that stops after the first
  gets a payload cut short. The payload is `[u32 len+8][u32 len][JSON bytes, each minus 1][u32 len]`.
  `WrcGame.json` beside it is the same JSON in plain text.
- **The checksum:** the save carries a 64-bit checksum whose formula isn't known. Keeping the
  original value works: the game accepts edited saves and keeps the edits.
- **Your cat:** under
  `<slot>/GameplayProgression/Gameplay.Combat.Character.Cat.Player/Customization`, as one string
  in Unreal's struct text format:
  `(ClanType=RiverClan,BodyOffset=2,FaceOffset=1,…,BodyValue=5,FaceValue=4,…,EarIdx=6,…,PrefixNameId="…",SuffixNameId="_PAW",Gender=True,CatSize=0.45,…)`.
  Fields at their default are left out.
- **Traits:** stored next to the customisation as `"Traits": [{"Type": 1}, {"Type": 4}]` (values
  under *Character creation and traits*).
- **Other cats:** NPCs live under `NPCData`. Story roles (`NPCData/NarrativeRoles`) hold exact
  copies of the NPC cast in them, so a rename must change every copy.
- **Story scenes seen:** each slot lists the story scenes its cat has watched under `Sequences`
  (`ProphecyIntro`, `RankUpApprentice`; *The game's live state*).
- **Account-wide data:** the save manager's `SetGameProgressionData` and
  `SetStateJsonDataFromString` write to `Shared`, data for the whole save, not to a cat's slot
  (seen in game, build 26184573).
- **Key bindings** are kept in the save, but the game ignores edits to them, and its rebinding
  screen doesn't work on PC (*Input* below; the README, [Remapping keys](../README.md#remapping-keys)).

## Engine settings that matter

- **UI scale:** `DefaultEngine.ini` sets `UIScaleRule = ScaleToFit` with
  `DesignScreenSize = (X=3840,Y=2160)`. At 1920x1080 every UI widget is drawn at half size. The mod
  menu sits in a scale box set to (screen height / 1080) / UI scale to undo that. Seen in game: the
  first version was too small to read, and the scaled one is right.
- **Slate's default images are shipped** (`Engine/Content/Slate/…`, 762 files), so stock UMG
  buttons, check boxes, sliders and drop-downs draw properly.
- **Input:**
  - `DefaultInput.ini` sets `DefaultViewportMouseCaptureMode=NoCapture`, so the mouse never
    reached the game at release. Patch 1.1 (build 26184573) added mouse control of the camera without
    changing that setting, so it's done at runtime some other way (not yet looked at). It's rough, so
    wcmods keeps its own mouse look ([formats.md, `mouselook.json`](formats.md#mouselookjson)).
  - The game's mouse axes scale by 0.07 per count (`AxisConfig`).
  - `InputSettings.bEnableMouseSmoothing` is on.
- **Cheat code is compiled in:** the release build still has the engine's cheat code ("God mode
  on", "You feel much lighter", "You feel ethereal" are in the exe). Only the cheat manager
  isn't created.

## Game objects

### Managers (on the game instance)

`BP_WrcGameInstance_C < WrcGameInstance < SwtAdventureGameInstance < SwtQuestGameInstance <
SwtGameInstance < GameInstance`. Its managers are reflected properties:

| Property | Offset | Class |
|---|---|---|
| `GameConfig` | 0x1F0 | |
| `GameUtil` | 0x1F8 | |
| `SaveManager` | 0x200 | |
| `GuiManager` | 0x208 | `BP_WrcGuiManager_C < WrcGuiManager < SwtAdventureGuiManager < … < SwtManager` |
| `CheatsManager` | 0x210 | `BP_WrcCheatsManager_C < WrcCheatsManager < SwtAdventureCheatsManager < SwtQuestCheatsManager < SwtCheatsManager` |
| `FlowManager` | 0x218 | |
| `StorageManager` | 0x220 | `BP_WrcStorageManager_C < SwtStorageManager` |
| `GameServices`, `AnalyticsManager`, `OnlineServicesManager` | 0x228, 0x230, 0x238 | |
| `AchievementsManager`, `RecordsManager`, `ChallengesManager`, `MontagesManager` | 0x240–0x258 | |
| `ActorTracerManager` | 0x260 | `BP_WrcActorTracerManager_C < SwtAdventureTracerManager < SwtActorTracerManager` |
| `VfxManager` | 0x268 | |
| `…Class` properties (`GameConfigClass` 0x270 … `CheatsManagerClass` 0x290) | | The classes the managers are made from |

These managers are also found by class: the quest manager (`BP_WrcQuestManager_C < WrcQuestManager < QuestManager`),
NPC generation (`BP_WrcNPCGenerationManager_C < WrcNPCGenerationManager < SwtAdventureNPCGenerationManager`),
track paths, tutorial, combat and tuning (`BP_WrcTuningManager_C`).

### The game's live state

Most of the game's own C++ classes reflect nothing: the health, stamina, level, inventory and resource
components have no properties or functions Lua can see. Their values were found by reading the
components' memory in game (2026-10-24) and comparing with the save. `WCModsGame` maps them with
`RegisterCustomProperty` ([scripting.md](scripting.md#mapped-values)).

**Resource components** (`SwtQuestResourceComponent` and its children) all share this layout:

| Offset | What | Seen |
|---|---|---|
| +0x108 | The resource type (`EQuestResourceType`: Health 0, Level 1, Stamina 2, StaminaCombat 3, Currency 4, FreshKill 5) | 0–5 |
| +0x10C | The value now | 233 health, 100 stamina, 91 fresh-kill |
| +0x110 | Its maximum | 233, 100, 100 |
| +0x114 | A multiplier, 1 in every one seen | 1.0 |

Where each one is:

| Component | On | Its own fields |
|---|---|---|
| `SwtQuestHealthComponent` | your cat | |
| `SwtQuestStaminaComponent` | your cat | +0x11C: stamina back per second (20) |
| `SwtCombatStaminaComponent` | your cat | fight stamina: 0.4 × Prowess + Stamina (193.2 for Prowess 233) |
| `SwtAdventureLevelComponent` | the player state | value is XP, max the XP for the next level; +0x120: the level (20); +0x124: the level cap, `Gameplay.Exploration.MaxLevel` (20; read from the code, see below: `WCM_LevelShown` is an older name); +0x138: the stats struct, so `Prowess` +0x154, `Strength` +0x158, `Resilience` +0x15C, `Instinct` +0x160, `Agility` +0x164, `Stamina` +0x168 (all equal to the save's) |
| `SwtAdventureFreshKillPileComponent` | the game state (`FreshKillPileComponent`) | +0x130: seconds since it last dropped (counts up in real seconds); +0x134: 90, `Decay.Time` |
| `SwtAdventureStatusComponent` | every cat and animal (`StatusConditionComponent`) | +0xE0: the status condition (`ESwtAdventureStatusType`); +0x144: rounds it has lasted; +0x148: `SelfCure.Chance` 0.2; +0x14C: `Poison.Damage` 0.1 (read from `ApplyStatusType`, `0x141736CD0`, and the end-of-round code; watched in game) |
| `TurnBasedCombatComponent` | every cat and animal (+0x848) | +0x1A1: its team; +0x1E0: its moves (a `TArray` of `AttackMove` rows, count at +0x1E8); +0x3F8: the AI's tier ([combat.md](mechanics/combat.md#the-combatant)) |
| `SwtAdventureDetectionComponent` | roaming animals (`ExplorationDetectionComponent`) | +0x57C–0x5AC: its senses, the tuning for its size class ([exploration.md](mechanics/exploration.md#stealth-and-being-noticed)) |

Writing them works: the values changed in memory, and the game's own code read them back. The HUD
isn't told, so a bar may show the old value until something else updates it.

**The level component's code** (build 26184573, read from the disassembly; the vtable slots are the
level component's). `USwtAdventureLevelComponent` derives from `USwtQuestLevelComponent`, a resource
component whose value is the XP; the level and the cap are the parent's, the stats its own.

| Function | What it does | Found by |
|---|---|---|
| `0x141658C00` | The parent's start-up (vtable +0x3F8, presumably `BeginPlay`): the cap (+0x124) from `Gameplay.Exploration.MaxLevel`, then, for the player's component (`0x1416570E0`), a level and XP from `0x1416AF350` and `0x1416AF7A0`, each given the +0x154 of the object behind the global `0x14A8A6E08` (the save and a slot, presumably), then sets the level | `xrefs.py` on `Gameplay.Exploration.MaxLevel` |
| `0x1417C6210` | The same, overridden by the level component (the parent's code repeated, not called: it stores the cap at `0x1417C6252` and calls the level setter at `0x1417C6326`), which then sets its stats struct (+0x138) from what `0x14180F9D0` returns. That function reads the object behind the global `0x14A8A6E30` (after an IsA check), looks up `Stats` in what that object's vtable +0x498 and +0x368 hand back, and when it's there reads it as a `SwtAdventureCharacterStats` (presumably the save's `Stats`); otherwise it takes `0x14181CD60`'s stats for `PlayerCat`, and with no such object, zeroes | its vtable |
| `0x141658870` | Sets the level: +0x120 = n, the XP bar's size from vtable +0x548, then the XP, or a full bar at the cap; for the player's, the XP and level go to `0x1416AF600` and `0x1416AF1B0` (the save, presumably); calls `0x14120D010` with this+0x128 and a pointer to the level, which reads an array there (count at +8, 16-byte entries): presumably a multicast delegate broadcasting the new level; recomputes the stats (vtable +0x550) | `callers.py` (three calls) |
| `0x141658A90` | Sets the XP (vtable +0x510): clamped between 0 and the bar (+0x110; +0x100 instead while the byte at +0x104 is set); below the cap, XP that reaches the bar sets level + 1 with what's over, which sets the XP again | calls `0x141658870` |
| `0x141658D20` | The XP bar at level n (vtable +0x548): `Gameplay.Exploration.Level.%d` with n + 1 | `xrefs.py` on `Gameplay.Exploration.Level.` |
| `0x1417C6410` | The level component's stats (vtable +0x550): the base stats for its level from `0x1418043E0` (with `PlayerCat`), then each Social trait's `Gameplay.Combat.<trait>.Strength/.Resilience/.Instinct` × (level − 1) × 0.05 added, then all six rounded (`FMath::RoundToInt`); then a resource component its owner hands back gets Prowess as its maximum and value (the health, presumably: in game health equals Prowess) | `dispscan.py` on the six stat offsets |

`0x1418043E0` is called by the fight code too (`0x1417D5830`, `0x1417D5FC5`).

**The clock:** the game state's +0x438 is a float, the seconds into the day. Setting it to 21600 made
the game's own `GetDayClockTime` say 6:00.

**The inventory** is `WrcInventoryComponent` on the player state, a native `TMap` of item tag to
count: its elements at +0x150, with the count at +0x158 (12 for 12 kinds of item). Nothing reflected
reads or changes it:
- Calling a pickup's `OnInteracted` from Lua plays its effect and removes it, but gives nothing.
- The HUD's `OnItemPickedUp(tag, quantity, total, popup)` is told each new total.
- The game writes `WrcGame.json` (the save as plain JSON) every time it saves.

**The fight:** a fight's director is the game state's `Director` (`BP_CombatDirector_C`). Its
reflected `PlayerParty`, `EnemyParty`, `TurnOrder` and `CurrentTurnAttackCharacter` hold the
fighters. Each fighter's combat component (+0x848) is filled when the fight starts.

Read in a fight with a level 20 cat against a weak bird:
- The bird was level 20.
- Its stats were exactly base + growth × 0.95, e.g. Prowess 203 and Strength 150.
- Its health was 203, and its fight stamina 141.2 (0.4 × 203 + 60).
- Calling the combat manager's `EndCombat` ended the fight but left the controller with no pawn and the
  fight menu on screen. Don't use it.

**The quests:** the quest manager's `Quests` is an array of `{Quest, Line, Node}`. Every quest object
is named `SwtAdventureMultiObjectiveQuest_0`, and its outer, a `QuestDynamicGraph` such as
`QuestGraph_Tutorial` or `QuestGraphProcedural_Deliver`, says which quest it is. There are 40 in
`/Game/Quests/QuestLines/QuestLine_Main`.

Seen in game on build 26184573 (2026-10-26), building the Sandbox mode mod:
- **Loading a cat:** the game state (`SwtQuestGameplayGameState`) goes through phases 1 → 4 while a
  cat loads, set by `Server_SetPhase`. The quests are built from `QuestLine_Main` between the quest
  manager's `OnNPCGenerationCompleted` and `Server_SetPhase(2)`.
- **Clearing them:** the quest manager's `ResetQuests(false)` empties `Quests`. Called in a pre-hook of
  `Server_SetPhase` with phase 2, the cat starts with no quest marks anywhere. Called mid-play, the
  quests go but the minimap's quest diamond stays.

**The story scenes:** the first load of a new cat plays `Gameplay.Narrative.Prophecy.Intro.<Clan>`, then
`Gameplay.Narrative.RankUp.<Clan>` (the apprentice ceremony). Seen in game (build 26184573):
- While one plays it's in the sequencer manager's `ActiveSequences`, an array of
  `FSwtActiveSequenceStruct` whose `SequencePlayer` is the running player.
- The save records the ones a cat has seen, per slot, under `Sequences` (`ProphecyIntro`,
  `RankUpApprentice`).
- **Skipping one** works through the game's own skip popup, `WBP_GuiPopupSkip_C`: take its
  `mcGuiHoldButtonSkip.ButtonCommand` and call the popup's `OnListenCommand(cmd, 0, controller)`
  (pressed), then `OnListenCommand(cmd, 1, controller)` (released) about 2.5 s later, as holding the
  button does.
- **Don't** call `SequencePlayer:GoToEndAndStop()` instead: the scene stopped, but the game waited
  for it forever, and a skip after that crashed the game.

**Driving the menus:**
- **Front-end screens:** calling a screen's `OnKeyPressed`/`OnKeyReleased` (Enter) and
  `OnListenCommand(Button_A or Button_Confirm, pressed/released, controller)`, and
  `OnUIPress`/`OnUIRelease(button)`, takes the game from the splash screen through the main menu
  (`mcGuiButtonProphecy`) and the cat choice (`mcGuiButtonCat1`) into the world.
- **The fight menu:** it didn't respond to the same calls.

### What's in the world

Surveyed in game on 2026-10-24: every actor within 50 m of the player's cat (7402 actors
in the level), each with its class chain. These are what `WCModsWorld`'s
kinds are built on:

| What | Class chain |
|---|---|
| Your cat | `BP_Exploration_Character_Player_C < WrcCharacter < SwtAdventureCharacter < QuestCharacter < Character` |
| Your controller | `BP_WrcGameplayPlayerController_C < WrcGameplayPlayerController < AdventureGameplayPlayerController < QuestPlayerController < SwtGameplayPlayerController < SwtPlayerController` |
| Pickups | `BP_Pickup_<Item>_C < BP_PickupActor_Base_C < SwtAdventurePickupActor < SwtAdventureInteractableActor < InteractionTargetActor` |
| Interactables | `BP_Interactable_<Action>_<Thing>_C < BP_Interactable_<Action>_C < BP_Interactable_Base_C < SwtAdventureInteractableActor` (Action: Claw, Dig, Sharpen, Sleep, Play); scenes such as the tied tree are `BP_Interactable_CInematic_C < SwtAdventureInteractableSequence` |
| Flowers you brush past | `BP_InteractableByContact_<Flower>_C < BP_InteractableByContact_Base_C < SwtAdventureInteractByContact` |
| Roaming animals | `BP_Exploration_Character_Base_C < WrcRoamingEnemy < WrcCharacter`, made by `BP_Enemy_Generator_C < WrcPreyGenerator < SwtAdventurePreyGenerator` |
| Clan cats walking about | `BP_WalkingNPC_Character_Base_C < SwtAdventureWalkingNPC < SwtAdventureCharacter`, on `BP_WalkingNPC_Spline_C` |
| Quest givers and camp cats | `BP_Quest_Giver_<Role>_C < BP_Quest_Giver_Base_C < WrcQuestActor < SwtAdventureQuestActor < QuestBaseActor < NPCActor`; also `BP_Quest_Filler_C < SwtAdventureFillerActor`, `BP_Quest_Giver_Gossip_C < SwtAdventureQuestHintActor` and `BP_Quest_Giver_FreshKill_C < SwtAdventureFreshKillActor` |
| Quest places and areas | `WrcObjectivePoint < SwtQuestObjectivePoint < SwtQuestTargetPoint`, `BP_QuestBoxTrigger_C < QuestBoxTrigger`, `BP_RaceTrigger_C < RaceTriggerBox < CaptureBoxTrigger < QuestBoxTrigger` |
| Climbing and jumping | `BP_SplineClimb_Target_TreeClimb_C / _Wall_C < SwtAdventureSplineClimbTarget`, `BP_Jump_Spline_HotSpot_C < SwtAdventureSplineJumpHotspot < SwtAdventureJumpHotspotBase` |
| Den entrances | `BP_Housing_DoorActor_C < WrcHousingDoorActor < SwtAdventureHousingDoorActor` |
| Fresh-kill pile | `BP_FreshKill_Pile_<Clan>_C < BP_FreshKill_PileActor_C < SwtAdventureFreshKillPileActor` |
| Area names | `BP_ZoneNameTrigger_C < WrcZoneNameTrigger` |
| Movement areas | `BP_MovementModifier_Invisible_C / _Loud_C < SwtAdventureMovementModifierArea` |

### Cat models

- **`SwtAdventureCustomizableMeshComponent`** (found by class) holds the parts: `SkelMeshComp`,
  `FurSkelMeshComp`, `TailSkelMeshComp`, `EarSkelMeshComp`, the four accessory components, and
  `CustomData`.
- **Its functions:** `RefreshShape`, `ValidateFurColorIndex`, `ValidatePatternIndex`,
  `ValidateEarIndex`, `ValidateTailIndex`, `ValidateWhiskerIndex`, `ValidateEyeIndex` and the
  accessory validators.
- **Menu and portrait copies of your cat** are `GuiCatCustomActor` (`BP_UI_CatCustomActor_C`). It
  has `CaptureComponent` and `CaptureComponentInventory`, scene captures that take the portraits,
  plus `SetCustomDataFromSave` and `TakePictureWithDelay`. The main menu shows
  `BP_CatActorChild_MainMenu_C` and the creator shows `BP_WrcSK_Customization_Player_C`.

**`CatCustomData` (the customisation struct):**

| Field | Offset | Field | Offset |
|---|---|---|---|
| `ClanType` | 0x00 | `EarIdx` | 0x40 |
| `BodyOffset` | 0x0C | `FurIdx` | 0x44 |
| `FaceOffset` | 0x10 | `FurColorIdx` | 0x48 |
| `EarOffset` | 0x1C | `PatternIdx` | 0x54 |
| `BodyValue` | 0x28 | `MarkingIdx` | 0x58 |
| `FaceValue` | 0x2C | `PrefixNameId` | 0x70 |
| `FurValue` | 0x30 | `SuffixNameId` | 0x80 |
| `EyeValue` | 0x34 | `CatSize` | 0x94 |
| `WhiskerValue` | 0x38 | `Gender` | bit field |
| `TailIdx` | 0x3C | | |

Colour fields: `FurColorIdx` picks the coat, `Pattern01ColorIdx` the pattern colour, and
`Pattern02ColorIdx` the marking colour. `EyeLeftColorIdx` and `EyeRightColorIdx` pick the eyes.

### How cats and animals are animated

Seen in game on 2026-10-27 (build 26184573) and read from the class dump.

- **One AnimBlueprint drives every cat:** your cat's `CharacterMesh0` (`SK_CatMaster`), walking NPCs'
  and quest givers' meshes all run `ABP_CatMaker_C` (parent `GuiCatCustomAnimInst`); the menu and
  portrait cats run its child `ABP_CatMaker_Child_UI`. The fur, tail, ears and the four accessory
  components have no AnimBlueprint: they follow the body (`LeaderPoseComponent` = `CharacterMesh0`).
- **`ABP_CatMaker`:** a locomotion state machine (51 sequence players, random idle breaks), a lean
  blend space, look-at and IK, pose-asset nodes for the body-shape sliders and one `Slot` node, where
  montages play.
- **Animals:** `ABP_Mice_C`, `ABP_Rabbit_C`... are children of `ABP_Enemy_Base` (parent
  `GuiCharacterCustomAnimInst`), which has the slot. Their montages play in `DefaultSlot` too.
- **The game's own montages** are played by tag: `USwtPlayMontageComponent` (on the cat, `PlayMontageComponent`)
  plays a row of a DataTable of `FSwtAnimationStruct` (`AnimationMontage`, `GameplayTag`,
  `bCanBeInterrupted`, `VoiceoverTag`, `UpgradeLevel`, `BlocksInput`) with
  `K2_PlayMontageOfTag(tag, rate, bForceInterrupt, bQueueIfCurrentlyPlaying, bStopMontages)`. The cat's
  table is `DT_Cat_CombatAnimations` (despite its name: `Animation.Exploration.Meow`,
  `Animation.Exploration.Interaction.Dig`/`Sleep.1`/`Sniff`..., `Animation.Combat.Hit.*`, the attacks);
  each animal has its own `DT_<Animal>_CombatAnimations`. The sitting montage is
  `BP_WrcGuiManager`'s `SimpleSitMontg`.
- **Playing a sequence from Lua works**, without a montage asset: load it
  (`KismetSystemLibrary:LoadAsset_Blocking`), then on the mesh's anim instance
  `PlaySlotAnimationAsDynamicMontage(sequence, FName("DefaultSlot"), blendIn, blendOut, rate, loops,
  blendOutTriggerTime, startAt)`. It returns a transient `AnimMontage` (`IsAnyMontagePlaying()` is then
  true). Your cat played `A_CatMaster_Stretch_1` this way in the forest, with its body shape, fur,
  tail, ears and accessories following. The same call plays on the animals: a roaming mouse's
  `ABP_Mice_C` spun a mod's sequence in place, and a bird's `ABP_Bird_C` too.
- **A mesh's rest pose isn't always its skeleton's:** the game skins a mesh with its own reference
  skeleton's bind pose (the skin's inverse bind matrices are from it), and a sequence's keys are
  absolute, so that's the pose a new animation moves bones from and leaves the others in. The rabbit's
  `SK_Rabbit` differs from `SK_Rabbit_Skeleton` on 33 of its 38 bones (up to 17 degrees on the tail;
  `ear_R`, `Eyelid_R` and `cheeks_R` turned 180 degrees about themselves); the cat's `SK_CatMaster`
  only on the front legs (`Forearm_f` 1.2 degrees, `paw_f` and `Finger_f` 0.85 cm and 2 to 3 degrees);
  the other animals' are their skeletons' (read from the files, 2026-10-27).
- **Out of view:** the animals' meshes (`VisibilityBasedAnimTickOption` 4) don't update their bones
  while they're not rendered: a montage on a far bird plays, but its bones stay put until it's seen.
- **Lua states:** `Game.anims` keeps what each UE4SS script started in that script's own Lua state, so
  the bridge can't see the emotes' script's montage (the anim instance's `IsAnyMontagePlaying` can).
- **No emotes:** the game has no emote feature; its one-off animations (meow, sit, dig, sniff,
  stretch, yawn, the photo-mode poses) are played by interactions, the idle breaks and photo mode.
- **No swimming:** cats have no swim animation, state or water movement in the game's files; "swim" is
  only in effects (`NS_Fishes_Swimming_*`, `NS_MallarDuck_Swimming`, `MI_Swan_Swimming`), and water
  only a footstep surface (`EAdventurePhysicalFloorType::Water`).

## Character creation and traits

Worked out on 2026-10-24 and confirmed against a real save.

**The creator:** `WBP_GuiScreenCustomization` has categories BODY, EARS, SIZE, SCARS,
ACCESORIES, the Cat's Nature panel, pattern, markings and colours. After the name screen,
`WBP_GuiScreenSelectTraits` shows the result: "Based on your choices your personality traits
are:".

**The Cat's Nature panel** (`WBP_GuiPanelCustomizationNature`) has six rows, each between two
words. Read as which part each row sets, from its snout icons and the six `…Offset` fields
(**a guess, not yet checked in the creator**):

| Row | Words | Likely part |
|---|---|---|
| 1 | Graceful / Powerful | Body |
| 2 | Efficient / Resilient | Fur |
| 3 | Swift / Steady | Tail |
| 4 | Subtle / Perceptive | Ears |
| 5 | Sensitive / Reserved | Whiskers |
| 6 | Gentle / Tenacious | Face / snout |

**Traits are worked out from body, ears and face, and nothing else.** Colours, patterns,
markings, size and name play no part.

`TraitsFilters.csv` (`DataTables/NonAsset`, row struct `TraitFilter`) gives each trait points for
each of the 10 options of each part:

| Trait | Type | Body 1–10 | Ears 1–10 | Face 1–10 |
|---|---|---|---|---|
| Ambitious | Social | 27 27 13 13 0 0 0 0 0 0 | 0 27 27 13 13 0 0 0 0 0 | 27 27 13 13 0 0 0 0 0 0 |
| Brave | Social | 0 0 0 0 27 13 13 0 27 0 | 0 0 0 0 0 13 13 27 13 27 | 0 0 27 27 13 13 13 0 0 0 |
| Wise | Social | 13 13 0 0 0 0 0 27 0 27 | 27 27 13 13 0 0 0 0 0 0 | 0 0 0 0 0 13 13 13 27 27 |
| Energetic | Gameplay | 0 0 0 0 0 27 27 13 13 0 | 0 0 0 0 27 13 13 27 0 0 | 0 0 13 27 27 13 13 0 0 0 |
| Curious | Gameplay | 13 13 27 27 0 0 0 0 0 0 | 0 0 13 13 27 0 27 27 0 0 | 0 0 0 0 13 13 13 27 27 13 |
| Patient | Gameplay | 0 0 0 0 27 13 13 27 0 0 | 27 13 13 0 0 0 0 0 0 0 | 13 13 0 0 0 27 27 27 0 0 |

**The rule:** add up the points from the chosen `BodyValue`, `EarIdx` and `FaceValue` (the
"Value"/"Idx" fields, not the "Offset" ones). The highest **Social** trait and the highest
**Gameplay** trait are the cat's two traits.

**Checked against a save:** body 5, ears 6, face 4 gives Brave 67, Ambitious 13 and Wise 0, then
Energetic 40, Patient 27 and Curious 0, so Brave + Energetic. The save has
`Traits: [{Type: 1}, {Type: 4}]`, which is Brave + Energetic. Scoring the Offset fields instead
gives Ambitious + Patient, which is wrong.

**Enums** (read from the exe's enum tables):
- `ECharacterTrait`: None 0, Brave 1, Ambitious 2, Wise 3, Energetic 4, Curious 5, Patient 6.
- `ETraitType`: None 0, Social 1, Gameplay 2.
- The table's row order (Ambitious, Brave, Wise, …) is not the enum order.

**`TraitFilter` row layout:** `Trait` at 0x08 and `TraitType` at 0x09, then int32 scores:
`Body_1`..`Body_10` at 0x0C–0x30, `Ear_1`..`Ear_10` at 0x34–0x58, and `Face_1`..`Face_10` at
0x5C–0x80.

**Ties:** in 269 of the 1000 combinations, two traits score the same, e.g. ears 8 gives Energetic
and Curious 27 each. How the game breaks a tie isn't known yet.

**How often each pair comes up** (the other 731 combinations):

| Pair | Combinations |
|---|---|
| Brave + Energetic | 152 |
| Ambitious + Curious | 122 |
| Wise + Curious | 99 |
| Wise + Patient | 96 |
| Brave + Curious | 69 |
| Brave + Patient | 65 |
| Ambitious + Patient | 58 |
| Ambitious + Energetic | 40 |
| Wise + Energetic | 30 |

The clearest Brave + Curious builds (body, ears, face): 3/4, 8, 6/7; 5, 8, 9; and 9, 7, 8.

**What traits do** (details in [mechanics/progression.md](mechanics/progression.md#what-traits-do-in-play)):
- **Social traits (Brave, Ambitious, Wise) add stat growth:** `Gameplay.Combat.<Trait>.<Stat>`,
  e.g. Brave +20 Strength and +10 Instinct, scaled by (level − 1) / 20. This matches a level 20
  save exactly.
- **Energetic:** `Gameplay.Exploration.Trait.Bonus.Energic.MoveAndRun.DrainRate` (-5) and
  `.Climb.DrainRate` (-18), so less stamina drain. Loaded by the code.
- **Curious:** a 50% chance of +1 on each consumable you get (`Curious.Drop.Chance` /
  `.PlusQuantity`). Read from the code at `0x1417C4D20`.
- **The fresh-kill bonus is broken:**
  - The same function gives fresh-kill items a bonus too, but checks for **Curious** and reads
    `Curious.FreshKill.Chance` / `.PlusQuantity`.
  - `TuningData` has no such rows: its fresh-kill rows are `Trait.Bonus.Patient.FreshKill.*`.
  - So the chance stays 0 and no one gets the bonus.
  - **Patient does nothing the exe knows of.** "Patient" never appears in a key the exe uses.
  - (Earlier notes said Curious gives fresh-kill, then that Patient does; the code says neither
    works.)
- **Bonding:** `Gameplay.Progression.Bonding.TraitModifier` (1), use not traced.
- **Names:** `SuffixNameFilters.csv` scores suffixes against traits for the name screen's
  suggestions.
- **Quests:** quest dialogue has trait-flavoured answers (`QST_START_PLAYER_BRAVE_ANSWER_1`,
  `STR_QUEST_DIALOGUE_ACCEPT_BRAVE`).

**Value and Offset:** in the one save looked at, every `…Value`/`…Idx` is its `…Offset` + 3
(body 2→5, face 1→4, fur 3→6, ears 3→6, tail 3→6, whiskers 1→4). That suggests the creator shows
each part's options in groups, with the offset the position inside one. Not yet understood.

## Names

From `wcmods/names.py` (checked against the tables and the save):
- **A clan cat's name** is a prefix and a suffix.
  - `NPC/PreffixName.csv` (the game's spelling) has 90 prefixes, with a weight per clan (counted 2026-10-28).
  - `NPC/SuffixName.csv` has 27 suffixes, with a weight per rank: kits get -kit, apprentices
    -paw, leaders -star.
- **The name shown** is the English text under the key prefix ID + suffix ID
  (`STR_CAT_NAME53` + `_PAW` gives `STR_CAT_NAME53_PAW` = "Otterpaw"), in each language's
  `Strings_*.csv`. Every combination is its own line and is exactly prefix + suffix; one
  (Black + face, `STR_CAT_NAME27_FACE`) is left out on purpose.
- **The save** stores `PrefixNameId` and `SuffixNameId`. A rank-up swaps the suffix ID.
  Apprentices may leave the suffix out, which then comes from their rank.
- **How a name is shown** (seen in game, 2026-10-25): the HUD and the Select Your Cat screen look
  up `PrefixNameId` + `SuffixNameId` as saved in the string table `SwtStrings`, which the game
  loads from `Strings_<language>.csv` under `NonAsset` (the exe holds that path next to
  `SwtStrings`/`SwtNamespace`). The prefix table isn't consulted: an ID in no table shows fine as
  long as the text exists, and a saved `_STAR` reads -star whatever the cat's rank. A key the table
  hasn't got shows as the engine's `<MISSING STRING TABLE ENTRY>`; "Cat 1" is the game's own
  fallback for the player's name, referenced from four places (a cat panel with rank and
  experience, the den, dilemma popups and the trait/name screen).
- **Name screen suggestions:** `PrefixNameFilters.csv` and `SuffixNameFilters.csv` score names
  against a cat's clan, looks and (for suffixes) traits.
- **Rogues** take a whole name from `NPC/RogueNames.csv` (23 of them, `STR_ROGUE_CAT_NAME_<n>`; the table's
  Name column is only a label).
- **The nine canon cameo cats** use `STR_CAT_NAME_ICONIC_<n>`.
- **`NPC/NameBanList.csv`** holds 31 combinations that are never handed out (canon names).

## Colours

- **The colour tables** are `TArray<FColor>` (BGRA bytes) on `SwtAdventureGuiManager`:
  `FurColors` at 0x288, `MarkingMaskColors` at 0x298, `PatternMaskColors` at 0x2A8 and
  `IrisColors` at 0x2B8, with 25 entries each. UE4SS can write and grow them.
- **Pattern and marking slots past 25 are safe:** the game checks those indexes against the
  table's real size (seen: slot 25 read back with its new colour).
- **Coat slots past 24 crash the game:** a coat's paw, ear, nose and whisker colours come from a
  native map at manager+0x800 (coat index to four colours), built from hex strings in the exe. A
  coat slot with no entry there crashes (seen in game).
- **`ValidateFurColorIndex`** swaps coat slots 20–24 (the Feral Edition's) for others unless you
  own that edition (seen: 24 becomes 11). Other values pass through.
- **Material parameters** on the cat's dynamic material instances: "Fur Color", "Pattern Mask
  Color", "Markings Mask Color", "Paws Color", "Ears Color", "Nose Color", "Whiskers Color".
  Setting them with `SetVectorParameterValue` works. The game sets them again whenever it sets a
  cat up.
- **Eyes** come from rows of the `CurveLinearColorAtlas`
  `/Game/Art/Environment/Common/Materials/Curves/Characters/Eyes/Gradients/CurveAtlas_Characters_Eyes_AllColors`
  (64x26). wcmods patches that atlas's pixels in an IoStore copy.

## The exploration camera

Read from its code on 2026-10-24 (`SwtAdventureCameraActor`, used as `BP_AdventureCamera_C`,
whose Blueprint holds only components).

**Structure:**
- root (turns left and right) → spring arm `AdventureArmComponent` (0x2B0,
  `SwtAdventureCameraSpringArm`) → `CameraComponent` (0x2B8).
- Also `TransparencyDetectionComponent` (0x2C0), `TargetActor` (0x2C8, the cat),
  `TransparentActors` (0x318), `SplineActor` (0x368), `CameraModifiers` (0x370).
- The player controller holds the camera actor at +0x4E8.

**Settings** are a struct at +0x3F8, read in BeginPlay (`0x141762140`) from
`Gameplay.Exploration.Camera.*` in `TuningData.csv`:

| Member | Setting | Member | Setting |
|---|---|---|---|
| +0x404 | `BoomArmRotation.Pitch` | +0x448 | `TurnRate.Yaw` |
| +0x408 | `BoomArmTargetLength` | +0x44C | `TurnRate.Pitch` |
| +0x410 | `Lag.Location.Vertical` | +0x454 | `Pitch.Min` |
| +0x414 | `Lag.Location.Horizontal` | +0x458 | `Pitch.Max` |
| +0x418 | `Lag.Rotation` | +0x470 | `Ahead.Rotation` |
| +0x41C | `SpeedExtraArmTargetLength` | +0x474 | `Ahead.Location` |
| +0x424 | `SpeedFov` | +0x478 | `Ahead.Power` |
| | | +0x47C | `Ahead.InterpolationSpeed` |

Climb and crouch settings sit at +0x428 to +0x444, and `LookAtPlayer.Offset` at +0x480.

**BeginPlay copies the lag settings onto the arm:**
- `bEnableCameraLag` (bit 0x20 of arm+0x290) is on when either location lag is non-zero.
- `CameraLagSpeed` (+0x294) is set to the vertical location lag.
- A custom horizontal lag (+0x350) is set to the horizontal one.
- `bEnableCameraRotationLag` (bit 0x40) is on when `Lag.Rotation` isn't 0, and
  `CameraRotationLagSpeed` (+0x298) is set to it (5).
- Nothing sets these again, except a spline change, which switches rotation lag off on a spline
  and back on after it.

**State:**
- **+0x398:** this frame's turn input, an FRotator of doubles (pitch +0x398, yaw +0x3A0, roll
  +0x3A8). The arrow keys and stick add to it, and the rotation update zeroes it.
- **+0x3E0:** the desired rotation.
- **+0x490:** a map of named interpolators, 0x68 bytes each: start +0x40, target +0x44, current
  +0x48, duration +0x4C, done (u8) +0x54, elapsed +0x58.
  - Names: `RotationYaw`, `LookAtYaw`, `RelativeLocationZ`, `RelativeRotationPitch`,
    `LocationX`/`Y`/`Z`, `ArmLength`, `FOV`.
  - `SetInterpTarget` (`0x141767C20`) restarts one. `ResetInterp` (`0x141767960`) finishes one at
    once.

**Each frame** (Tick `0x1417637B0`): settings blends, then position (`0x141765070`), then rotation
(`0x141765770`). The rotation update has three modes:
- **Looking at something** (flag +0x2F0): yaw blends toward the look-at direction
  (`LookAtYaw`).
- **On a camera spline** (`SplineActor` set): yaw follows the spline.
- **Free:** rotation = the root's current rotation + this frame's input, pitch clamped. The yaw
  is written into `RotationYaw`'s target, then `SetActorRotation` uses that target (or the
  current value while the interpolator runs). So a turn made to the root earlier in the frame
  stays. That's how mouse look works.

**Other camera code:**
- **Joining or leaving a spline** (`0x141766F70`) starts 0.8 s blends (`InterpolateDuration.Location`).
- **Teleport and respawn** (`0x141798590`) resets every interpolator and snaps the camera behind
  the cat.
- **Ahead** turns the `CameraComponent` up to 15° toward where the cat moves (a lean, not the
  root).

**Turning input** (the player's exploration component, `0x1417A61B0`):
- yaw input = axis × `TurnRate.Yaw` (+0x1CC on the component's settings) × delta time, added to
  camera+0x3A0;
- pitch = |axis|^`TurnRate.Power` × sign × `TurnRate.Pitch`, added to +0x398, within `Pitch.Min`
  and `Pitch.Max`;
- while `LookAtYaw` is running, it turns the cat instead.

**The player's exploration settings** are loaded at `0x14179F650`: `MoveAndRun` speeds at
+0x12C–0x13C, stamina +0x140/+0x144, jump +0x158–0x170, `TurnRate.*` +0x1CC–0x1E8, and the trait
bonuses `Energic.*.DrainRate` at +0x208/+0x20C.

**Confirmed in game:** with the rotation lag speed at 0 while the mouse is captured, the view
equals the root's yaw every frame. With 5, it trailed fast mouse turns by up to about 40°.

## Cheats and debug features

The game ships its developer cheat system; it just isn't switched on in the release build.

**`SwtCheatsManager` / `WrcCheatsManager`** (on the game instance, `CheatsManager`). Its
properties: `KeyCheatsMap` (0x148), `KonamiCodesMap` (0xF8), `KonamiCodeTimeThreshold` (0xF4),
`DrawDebugTrace` (0xF1), `OverridePlatformType` (0x198), `InitialCurrency` (0x19C),
`FreeCameraController` (0x1A8), `GuiConsole` (0x1B0), `EffectsToApply` (0x1B8),
`SpawnedActors` (0x1D8), `GuiWatermarkWidget` (0x1E8), `bSkipSave`, `bBackupSaveOnWrite`,
`bAllowGamepadAndKeyboardFreeCamera`, `bOverrideLanguage`, `bPrintPlayMontage` and
`bSkipSplineSetupMeshes`.

**Access levels**, `ESwtCheatsEnableType`: None, SoftOnly, DebugConsole, AllEnabled,
AllUnlocked, Dlc1Unlocked, HideAllUI, Marketing. Where the level is stored isn't known yet.

**The cheats popup**, `WBP_GuiPopupCheatsV2` (`EWidgetsIds::GuiPopupCheats`). Its list is filled
from `EPopupCheatsIds`:
- **Story and progress:** `advance_12_hours`, `all_unlocked`, `complete_current_quest`,
  `currency`, `rank_up`, `skip_tutorial`, `set_time_6am`, `unlock_checkpoints`,
  `unlock_defender_menu`, `unlock_starclan_gallery_menu`, `print_quest_log`, `quest_auto_play`.
- **Play:** `god_mode_life`, `stealth`, `teleport_to_camp`, `spectator_mode`, `hide_hud`,
  `toggle_console`.
- **Debug and test:** `backup_save`, `blockmesh`, `cat_creator`, `debug_cat_creator`,
  `enemy_viewer`, `show_den_cat`, `show_vfx`, `stats_fps_stream`, `sequence_forced`,
  `sequence_timecode`, `test_new_map`, `elo_test`, `debug_crash`.
- **Sandboxes:** `prog_sandbox_gameplay`, `program_sandbox_quest`, `program_sandbox_tutorial`,
  `sandbox_combat`, `sandbox_den`, `sandbox_test_attacks`, `scent_dojo`, `popup_training_grounds`,
  `dlc_2`.
- **Online:** `online_add_friends`, `online_connect`, `online_show_friends`,
  `online_skirmish_party`, `online_test_users`, `popup_cheats_online`, `analytics_reset_stats`,
  `analytics_send_stats`.

**What the maps hold** (read in game, 2026-10-24):
- **`KeyCheatsMap`:**
  - Three: `Cheats.Gameplay.DevJumpPoint.Up`
  - Four: `.DevJumpPoint.Down`
  - Five: `.ConsumeItem`
  - Seven: `.BondingDialogue`
  - Eight: `.Effects.Apply.Own`
  - Nine: `Cheats.UXD.ChangeLanguage`
  - Zero: `.ChangeConsoleUI`
- **`KonamiCodesMap`:** `Cheats.Profiler.ToggleShowStats`, `.DebugRenderMenu`, `.ToggleShowConsole`,
  `Cheats.Marketing.FreeCamera`, `Cheats.UXD.HideAllUI`, and `Cheats.Gameplay.ForceCombatWin` /
  `ForceCombatLose`.
- **Other values:** `EnabledMode` is 7, `GodMode` 0, and `AlwaysHasFullResource` has all six
  resources set to false.
- **More switches:** `SwtQuestCheatsManager` and `SwtAdventureCheatsManager` add about 40 more:
  `ForcedLevel`, `ForcedRank`, `bAllCheckpointsUnlocked`, `bAlwaysSucceedAttack`, `ForcedDilemma`,
  `ForcedDifficulty`, `bFastHousingCrafting`, `bAllowCatSizeOverride` / `CatSizeOverride`,
  `bShowFloatingPercent` and more. Whether the release build obeys each isn't known; the mod menu's
  Game switches page sets them.
- **Ignored by the release build** (seen in game, build 26184573): `bUseForcesQuests`,
  `bSkipSequences` and `bSkipTutorial`. With all three set, a new cat's quests were still built and
  the prophecy intro still played. To clear quests or skip scenes, see *The game's
  live state*.

**Cheat gameplay tags** (likely what `KeyCheatsMap` maps keys to): `Cheats.Gameplay.ForceCombatWin` /
`ForceCombatLose`, `ConsumeItem`, `BondingDialogue`, `TestGiveGifts`, `TeleportTest`,
`DevJumpPoint.Down`, `Effects.Apply.Own` / `Them`, `Cheats.Marketing.FreeCamera`,
`Cheats.Profiler.DebugRenderMenu` / `ToggleShowStats`, `Cheats.UXD.HideAllUI`,
`ChangeLanguage`, `ChangeConsoleUI` and `ShowCheatsPopup`.

**The engine's cheat manager:**
- `PlayerController.CheatManager` is empty in the release build, and `CheatClass` is unset, so
  the engine's `CheatManager` class is used.
- Creating one with `StaticConstructObject` turns console cheats on (seen in game).
- `god`, `slomo` and `teleport` work.
- `fly`, `ghost` and `changesize` don't stick:
  - the game puts its cat back to its own movement mode every frame;
  - `ChangeSize` doesn't move the mesh within the capsule (so a bigger cat floats), and the game
    resets the mesh's scale.
- The mod menu flies by moving the cat itself (no gravity, `MOVE_None`) and sizes it by scaling
  the actor (seen working in game).

## UE4SS in this game

- **The engine tick hook is found** (`GameEngineTick`), so `LoopInGameThreadAfterFrames` runs once
  per frame at the start of it. An older UE4SS build missed this hook, and scripts then ran at
  arbitrary points in the frame.
- **Never mix `LoopAsync` with game-thread loops in one script.** `LoopAsync` runs its callback on
  another thread in the same Lua state. With per-frame Lua work going on, the game crashed
  (2026-10-24, access violation reading `0xa` inside UE4SS's Lua glue, a null closure).
- **A destroyed object's slot gets reused.** After a level change, a kept widget looked valid
  but was another object (`attempt to call a TrivialObject value (method 'IsInViewport')`). Check
  the class of anything kept across levels, or look it up again.
- **Rotators passed as Lua tables lose their pitch.** Use `KismetMathLibrary:MakeRotator`.
- **Structs come back from functions fine** (`GetCameraLocation`, `GetViewportSize`). Out
  parameters are passed as a table and filled in (`LineTraceSingle`, `ProjectWorldToScreen`).
- **`ModRef:SetSharedVariable`/`GetSharedVariable`** carry strings, numbers, booleans and UObjects
  between mods' Lua states (not tables or functions). The mod menu is built on them.
- **UMG from Lua works:** an abstract `UserWidget` made with `StaticConstructObject` plus a
  `WidgetTree` and a root `CanvasPanel`, then `AddToViewport`. Stock controls work, and are polled
  for clicks and values (no delegate binding from Lua).
- **Listing a class's members works:** `cls:ForEachProperty` / `ForEachFunction`. An early probe
  listed `SwtAdventureCustomizableMeshComponent`'s. A later survey got nothing, probably because
  its callback called `FProperty:GetClass()` and errored. An error inside such a callback goes to
  UE4SS's log, not to an outer `pcall`, and ends the listing.
- **`os.clock()` advances in real time here** (it's used for throttling in the shared modules).
- **This UE4SS build has a bigger API than its version suggests.** Among the globals are
  `RegisterBeginPlayPostHook`, `RegisterEndPlayPreHook`, `RegisterLoadMapPostHook`,
  `ExecuteInGameThreadWithDelay`, `LoopInGameThreadWithDelay`, the delayed-action functions,
  `RestartCurrentMod`, `GenerateSDK`, `GenerateLuaTypes` and `RegisterCustomProperty`.
  `PropertyTypes` includes Map, Set and Struct.
- **Calling a function on an object that isn't there crashes the game inside UE4SS**, and `pcall`
  can't catch it. In one case a creature far away had no mesh loaded, and `mesh:GetSkeletalMeshAsset()`
  was called on it (2026-10-24, a null read in `UObject::HasAnyInternalFlags` under
  `process_lua_function`). Check `IsValid()` first.
- **A property an object doesn't have reads as a `TrivialObject`**, not nil.
- **TMaps work from Lua:** `map:ForEach(function(k, v) ... k:get() ... end)`, `map:Add(k, v)` and
  `map:Empty()`. Gameplay tag keys read as structs with `TagName`.
- **Array elements come back wrapped:** items of an array a function returns sometimes need `:get()`.
- **Out parameters come back as a table keyed by the parameter's name:**
  `gs:GetDayClockTime(t, t, t)` fills `t.Hours`, `t.Minutes` and `t.Seconds`.
- **Reflection works:** `ForEachProperty` (with each property's class) and `ForEachFunction` work.
  A function's parameters list with `ForEachProperty`, and `HasAnyPropertyFlags(0x100)` (out) and
  `0x400` (return) tell them apart.
- **Custom properties work:** `RegisterCustomProperty` reads and writes native fields of a class. It
  takes fixed-size types only, not maps or structs. Custom properties don't show in `ForEachProperty`.
- **Hooks:** they fire for calls made through Unreal (Lua's own calls included). A pre-hook can change
  a parameter with `param:set()`, and the called function saw the new value. In a post-hook the
  parameters read empty. Two hooks on one function, both removed, left the game fine.

## The game's enums

Worked out on 2026-10-28 on build 26184573, from the exe and the class dump (`vanilla/sdk`, taken in game on
build 24847281); the reading in game is written but not yet run there (docs/verified.md).

- **Where they are.** Each of the game's enums is a native `UEnum` named after its C++ name in its module's
  script package: `/Script/<Module>.<EnumName>`. The module is the `## [Module]` block of `api-index.txt`
  whose `enum E...` lines list it (`ECommands` and `EGuiConsolesTypes` in `SwtEngine`, `EClanType` and the
  quest enums in `SwtQuest`, the combat ones in `SwtAdventure`). `/Script/SwtEngine.ECommands` was found
  this way in game (the in-game remap reads it; verified.md, 2026-10-27); the `SwtQuest` and `SwtAdventure`
  packages are the ones `Game.hidden`'s classes are found in, but no enum in them has been looked up in
  game yet.
- **In the exe.** UHT's enum tables are `{const char* name, int64 value}` pairs. Each enum also has its UHT
  parameters (`FEnumParams`), which name it: OuterFunc at +0, DisplayNameFunc +8, NameUTF8 +16 (the enum's
  name), CppTypeUTF8 +24 (the same, or `<EnumName>::Type` for a namespaced enum), the table +32, ObjectFlags
  (u32) +40, the number of names (i16) +44, EnumFlags (u8) +46 and the C++ form (u8, `UEnum::ECppForm`: 0
  plain, 1 namespaced, 2 enum class) +47. `tools/re/uht.py <exe> enum <EnumName>` finds an enum through
  them and says where it is and its form: `ECommands`' 111 names (NoCommand 0 … TOTAL 110) at 0x14987A870
  (RVA 0x987A870, parameters at 0x14A485F68), `EGuiConsolesTypes`' 11 at 0x14987D640, `EClanType`'s 6 at
  0x149AE3270 (parameters at 0x14A4C2BD8). Of the 202 enums in the game's own modules (the class dump's
  `SwtEngine`, `SwtQuest`, `SwtAdventure`, `SwtNativeAudio` and `Wrc`; `SwtCore` and `SwtOnlineCloud` have
  none), all have parameters in build 26184573's exe, and the dump's form for each: 198 are `enum class`,
  their names carrying the type (`ECommands::Player_Interact`), and 4 are plain,
  their names without it: `EDataType` (`DataTypeNONE` 0 …, table at 0x14987A230), `ESwtEngineChannel`
  (`ECC_None` 0 …, 0x1498D0460) and `ESwtServicesError` (`SWT_NO_ERROR` 0 …, 0x1498CFF70) in `SwtEngine`,
  and `EPopupCombatState` (`ST_NONE` 0 … `ST_SELECT_OPPONENT` 3, 0x149BEBFE0) in `Wrc`. Unreal's own are
  of all three forms (`EInputEvent` is plain: `IE_Pressed` 0, `IE_Released` 1, `IE_Repeat` 2,
  `IE_DoubleClick` 3, `IE_Axis` 4, `IE_MAX` 5, at 0x1485A8BD0, parameters at 0x14A362E90). Where the
  parameters can't be found, `uht.py` falls back on the names' `<EnumName>::` prefix, which finds an enum
  class's table (for all 198 of the game's, the same table as the parameters give) but not a plain enum's.
- **What patch 1.1 changed.** The class dump of build 24847281 lists 109 `ECommands` names, `Player_Interact`
  the 66th (65). Build 26184573's table (above) has `Player_Mouse_Camera_Up` 64 and `Player_Mouse_Camera_Right`
  65 after `Player_Camera_Right` 63, so `Player_Interact` is 67 and everything after it is 2 higher. Every
  enum `Game.enums` names reads the same in both: the dump's lists and the exe's tables have the same names
  in the same order.
- **Reading one from Lua.** `StaticFindObject("/Script/SwtEngine.ECommands"):ForEachName(function(name,
  value) ... end)` gives each name as an `FName` with its type in front (`ECommands::Player_Interact`) and
  its value as a number (seen in game through the in-game remap, which sends the commands it gets this
  way). A missing enum comes back as an invalid object, which must not be asked anything (that crashes the
  game), and an error inside the callback goes to UE4SS's log and ends the listing without reaching a
  `pcall` around it. In game, each enum ends with a `_MAX` name one past its last value, which the exe's
  tables don't have: the engine adds it when it builds the enum (`UEnum::SetEnums` with
  `bAddMaxKeyIfMissing`). The class dump taken in game (`vanilla/sdk/CXXHeaderDump`, UE4SS's
  `GenerateSDK()` on build 24847281) lists it: `EClanType_MAX = 6` (`SwtQuest_enums.hpp`), `ECommands_MAX
  = 109` and `EGuiConsolesTypes_MAX = 11` (`SwtEngine_enums.hpp`); the UHT-compatible dump
  (`UHTHeaderDump`) leaves it out. An enum class's is `<EnumName>_MAX`. A plain enum's is `<prefix>_MAX`,
  the prefix being what its names share up to its last `_` (`EPopupCombatState`'s `ST_MAX = 4`,
  `ESwtEngineChannel`'s `ECC_MAX = 25`, `ESwtServicesError`'s `SWT_MAX = 30`), or `<EnumName>_MAX` when
  they share none (`EDataType_MAX = 11`), all four in the dump. The engine adds none when the enum has that
  name already (from the engine's code: `EInputEvent`'s own `IE_MAX` is in the exe's table, and the dump
  lists it once), so in game a plain enum's last `_MAX` can't be told from one of its own.
  `tests/game/test_cat.py` checks `EClanType_MAX` on build 26184573 when it runs.
  `Game.enumNames(path)` (WCModsGame) and `enumNames(path)` in `WCModsRemap` do this. `Game.enumNames` leaves
  out `<EnumName>_MAX`, so an enum class's, and keeps a plain enum's `<prefix>_MAX` (`ST_MAX`, `ECC_MAX`,
  `SWT_MAX`; `EDataType_MAX` goes); none of `Game.enums`' is plain. The remap's keeps every name, and looks
  up only the ones it knows.
- **What wcmods reads this way:**
  - **`Game.enums`:** each of its 17 lists is one enum (`wcmods/game.py` `ENUMS`: `clan` is `EClanType`,
    `status` is `ESwtAdventureStatusType`, ...), matched to what each is used for by the dump (`ClanType`
    is an `EClanType`, `CurrentPhase` an `EGamePhase`, `AlwaysHasFullResource` a
    `TMap<EQuestResourceType, bool>`, `RemoveStatusType` takes an `ESwtAdventureStatusType`, ...), all 17
    `enum class`. Each list is read from the game the first time a script looks anything up in it (or walks
    it, or takes `#`). The shipped lists, numbered from 0, are the fallback, and are now each the whole enum:
    `clan` and `rank` gained `Total` (5) and `resource` gained `Count` (6), which the old lists left out.
    The fallback answers while the game's enum can't be read, but isn't kept: the game is asked again on a
    lookup 5 seconds later, so a script that looks too early (its Lua starts before the game is up) gets the
    game's numbers once they're there. The table's metatable says which it has (`fromGame`).
  - **The Talk prompt's command:** `Player_Interact` in `ECommands`, read at the first prompt (it was the
    number 67).
  - **The in-game remap:** `NoCommand` from `ECommands` (it was 0), and `UI_PC` from `EGuiConsolesTypes`
    (it was 1): the key of the PC's table in `URegisterButtonsMap.DataGamepadButtonsMap`
    (`TMap<EGuiConsolesTypes, UDataTable*>`), whose pictures count as the keyboard's.
  - **The agent:** `Button_Confirm` from `ECommands` (it was the number 26), which it sends to a screen that
    waits for any key.
- **Checked against the exe:** `python tools/re/uht.py <exe> lua` reads every `Game.enums` list and every
  enum number wcmods keeps in a constant whose comment names it (`-- ECommands::Player_Interact`, or
  `-- ESlateVisibility: Visible, Collapsed` for several), in its Lua files and in the Lua its Python holds
  (the agent's), and compares them with the exe's tables. A line whose comment names a different count of
  values than it has numbers counts as a failure. On build 26184573: 58 of 58 match, 2 not checked:
  - the 17 lists;
  - 4 of the game's numbers: `Player_Interact` 67, `NoCommand` 0, `UI_PC` 1, `Button_Confirm` 26;
  - 37 of Unreal's own: `ESlateVisibility`, `ESlateSizeRule`, `EStretch`, `EUINavigation`,
    `EUINavigationRule`, `EScrollWhenFocusChanges`, `EAttachmentRule`, `ECollisionEnabled::NoCollision` 0,
    `ESpawnActorCollisionHandlingMethod::AlwaysSpawn` 1 (0x1487AC4B0), `ESpawnActorScaleMethod::OverrideRootScale`
    0 (0x14865B5D0), `EUMGSequencePlayMode::Forward` 0 (0x1484E8BE0), `ETextJustify` Left 0, Center 1, Right 2
    (0x147F77880), `EDescendantScrollDestination::TopOrLeft` 1 (0x147F81D30), and the plain `EInputEvent`
    (`IE_Pressed` 0, `IE_Released` 1), `EHorizontalAlignment` (`HAlign_Fill` 0, `HAlign_Left` 1, `HAlign_Center`
    2, `HAlign_Right` 3, 0x147F415D0) and `EVerticalAlignment` (`VAlign_Fill` 0, `VAlign_Top` 1, `VAlign_Center`
    2, 0x147F41690);
  - the 2 not checked are `EInternalObjectFlags::Garbage`, which isn't in a table (that flag set isn't
    reflected).
- **Unreal's own enums stay numbers.** They're the engine's (Unreal 5.7), not the game's, so a game update
  can't move them without a new engine, which would break much more than these. Each is a constant whose
  comment names its value, so the check above covers it: the spawns' `ALWAYS_SPAWN` and `ROOT_SCALE`, the
  animations' `PLAY_FORWARD`, `NO_COLLISION`, `JUSTIFY_CENTER` and the prompt's `HIDDEN` in `game.lua`,
  draw.lua's `JUSTIFY` table, `menu.lua`'s alignments and `TO_THE_TOP`, `menu_host.lua`'s `NAV_RIGHT` and
  `NAV_ESCAPE`, and the remap's `PRESSED` and `RELEASED`.

## Items

Worked out on 2026-10-24 and verified in game with a new herb and a new material (`items.json`).

**What an item is made of:**
- **Its tag:** `Gameplay.Inventory.<Consumable|Materials>.<name>`. The game registers new tags from
  ini files under `Wrc/Config/Tags/` in a pak (`[/Script/GameplayTags.GameplayTagsList]`,
  `GameplayTagList=(Tag="…")`) at startup.
  - `BlueprintGameplayTagLibrary:MatchesTag(tag, "Gameplay.Inventory.Consumable", false)` is true
    for a registered child tag and false for an unregistered one.
- **What it does:** a `Consumables.csv` row:
  - `EffectOnUse`, `bCombat`, `bExploration`, `Target` (`Owner` or `OwnerTeam`), `bRemoveAfterCombat`
    and `Type`;
  - this is what gives the inventory's USE button.
  - Each effect tag runs a Blueprint container (`BP_Heal_Container_2` and the like, mapped in
    `BP_WrcEffectManager`). The numbers come from the `GenericEffect.csv` row of the same name:
    `Effect.Consumable.Health.2` reads `Params.Health.2.Health` = 50. So a new effect strength
    needs a new container, not just data.
- **Name, description and icon:** a row in the cooked `DT_QuestObjectsInfo`:
  - row struct `/Script/SwtQuest.QuestObjectsInfoDataStruct`: `itemTag`, `Name`, `Description`,
    `Icon` (a soft texture), `ItemRarity`, `ItemGroupIcon` and `ItemCategoryColor`;
  - the enums `EItemRarity` (None, Common, Uncommon, Rare, Mythic), `EItemGroupIconType` (None,
    Health, Stamina, Stats, Status, Damage, Experience, Free) and `EItemCategoryColorType` (None,
    Consumable, Quest, Den).
  - **The inventory leaves out an item that has no row.** The UI looks rows up by `itemTag`, live,
    each time a screen opens. The row names are meaningless (`NewRow_45`).
- **A recipe:** a `BarteringCost.csv` row (`Cost` = `tag,n;tag,n`).
  - Bartering is at the medicine cat, a `BP_Quest_Giver_Bartering_C` (`SwtAdventureBarteringActor`),
    through its "Bartering" dialogue answer. In the save tested, that's Tigerstorm.
  - New rows show at the end of the Consumable tab. Trading takes the materials, a mod's new ones
    included.
- **In the save:** `<slot>/GameplayProgression/State/Inventory/<tag>` = count, where `<slot>` is
  `Shared/General/CurrentCatSlot`.

**The quest system's tables** hang off the CDO of `/Script/SwtQuest.SwtQuestConfig`:
- `QuestGraphDB`, `QuestObjectsInfoDB`, `QuestNodeGraphDB` and `QuestObjectivePickupDB`;
- `CharactersDB` (`DT_Characters`) and `CombatGeneratorDB`;
- each with a `…Path` soft path beside it.
- `QuestManager.ItemsStatsDB` (`ItemStatsDataTableStruct`) is empty, so `GetItemType` and
  `GetItemStatsDataFromTag` know no item.

**Adding rows at runtime doesn't work:**
- UE4SS's `dt:AddRow` fails with "Virtual UScriptStruct::ICppStructOps::Copy is unavailable" on
  this engine version.
- The shipping `DataTableFunctionLibrary` has no Add or Fill functions.
- Existing rows can be changed in place from Lua (`row.Name = FText(…)`, `row.Icon = other.Icon`),
  and the inventory shows the change.
- So wcmods writes new rows into a copy of the cooked table at install.

**Accessories:**
- **Tags:** `Gameplay.Inventory.Cosmetic.<Head|Neck|Body|Legs>.<name>.<variation>`, e.g.
  `Neck.DogCollar.2`.
- **The game's list:** `<name>` is a value of the native enum `EAccesoryIds` (HeatherCoronet 1 …
  BeadsBand 44).
- **Models and textures:** the GUI manager (`BP_WrcGuiManager_C`, from `SwtAdventureGuiManager`)
  maps each id to:
  - a skeletal mesh (`AccesoryMeshes`, 44 entries);
  - its variations (`AccesoryVariations`: a `MeshVariationsData` with a `Textures` array; most
    accessories have 1, a few 2 or 4). Variation n is `Textures[n - 1]`, put on the accessory's
    material (`MI_A<slot>_<name>`) as its `LYR1 Albedo` texture.
- **What's worn:** a cat's `CatCustomData` stores the head and body accessories as strings
  (`AccesoryHeadId` at +0xB8, `AccesoryBodyId` at +0xC8), and each slot's variation as an i32 (neck
  +0xD8, paws +0xDC, head +0xE0, body +0xE4).
- **The defaults' bytes** (the Blueprint's `Default__` export):
  - an `AccesoryVariations` entry is the key (the FName `EAccesoryIds::<name>`), the struct's header
    (`0x0300`, its one field), the array's count and 20-byte soft references (package FName, asset
    FName, empty sub-path);
  - `AccesoriesTestTags` is an array of 51 accessory tags (header `0x0300` and an FName each). The
    cheat that gives every accessory uses it; a shorter list beside it is the DLC's.
- **New looks** (`wcmods/accessories.py`):
  - A texture added to the end of an accessory's list in the defaults, at install, is the next
    variation. Its tag (registered from an ini like any item's) is worn with that look: DogCollar's
    look 3 in a mod's blue, verified.
  - Changing the list at runtime doesn't work: the lists are read when the game starts, and from
    UE4SS `map:Add` with a Lua table emptied the entry.
  - **Head accessories always show look 1**, the list and `AccesoriesTestTags` patched or not: a new
    look 2 for BigLeaf was worn as look 1. None of the game's head accessories has a second look.
    Neck, body and paw accessories show theirs.
- **New models** (`wcmods/models.py`, `wcmods/lua/models.lua`), worked out on 2026-10-27:
  - The GUI manager's defaults also hold `AccesoryMeshes`: each accessory's key FName and a soft
    reference to its skeletal mesh (`SK_StringandBones` for StringBones, `SK_Winter` for
    WinterWreath, `SK_DandelionsHeaddress` for DandelionHeaddress).
  - A cat wears accessories on its `SwtAdventureCustomizableMeshComponent`'s `AccSkelNeckComp`,
    `AccSkelPawComp`, `AccSkelBodyComp` and `AccSkelHeadComp` (skeletal mesh components with no mesh
    and hidden when nothing's worn). Its `CustomData` names them: `AccesoryNeckId` (a string,
    "DogCollar", or "None") and `AccesoryNeckVar` (the look), and the same for Paw, Head and Body.
  - Setting a component's mesh (`SetSkeletalMeshAsset`) to a copy of the accessory's mesh worked: it
    kept the accessory's material and the look's picture, followed the cat's bones (grooming,
    walking), and showed in the inventory's picture of the cat too. `RefreshShape` doesn't set the
    accessories again, so a script has to put the model back after the game does.
  - UE4SS's `LoadAsset` can't load a mod's mesh (it isn't in the asset registry);
    `KismetSystemLibrary:LoadAsset_Blocking` with a soft reference made from the path can.
  - An accessory slot that's empty in `CustomData` is hidden again within a second (`SetHiddenInGame`),
    so a test that puts a mesh on one has to clear that over and over.
  - Changing look (DogCollar look 3 to look 1, in the inventory) sets the slot's mesh and a new
    `MaterialInstanceDynamic` of the accessory's material with the look's `LYR1 Albedo`, so nothing a
    script put on the slot for the old look is left. Taking it off hides the slot and leaves its mesh.
  - Calling anything on a null object from Lua crashes the game (EXCEPTION_ACCESS_VIOLATION reading
    0x10 or 0x18, the class and name of a UObject): check `IsValid()` on what `GetMaterial`,
    `K2_GetTextureParameterValue` and the like return first.
- **Materials and see-through accessories** (2026-10-27):
  - Every accessory's material is an instance of `M_Characters_NPC` (three head wreaths:
    `M_EnvPropMasksMaster_GPE_Foliage`). Its parameters are the look (`LYR1 Albedo`, `LYR1 ARM`,
    `LYR1 Normal`), emissive, UV and wind settings: no opacity. About half the instances carry
    shaders of their own (87 KB), the rest use the master's (1 to 1.3 KB).
  - A material the game didn't cook for skinned meshes shows as the engine's grey default on an
    accessory: `M_VFX_PropsMaster`, `M_Blockmesh` and the Interchange glTF materials
    (`/InterchangeAssets/gltf/MaterialInstances/MI_Default_Blend`) all did, whatever their
    parameters said. A "GPUSkin" string in a material's package doesn't mean it was.
  - Of the materials made for cats, `M_Characters_Enemies` (the animals') showed the collar's picture
    properly, but none cut out a picture's see-through parts: a PNG loaded at runtime
    (`KismetRenderingLibrary:ImportFileAsTexture2D`) with clear stripes showed them solid on it, on
    `MI_ANeck_DogCollar` and on `MI_ABody_PineNeedles`; its `LYR1 Opacity Mask Intensity` changed
    nothing. The cats' eye glass (`MI_Cat_Cornea`, parent `M_Character_Eyes_Cornea`) is see-through
    on an accessory: `Glass Opacity` and `Glass Color` set how much and its colour, with no picture.
    That's what a see-through look is worn in.
- **Pickups** (worked out on 2026-10-27 for models on the ground):
  - The game has 23 pickup classes (`/Game/Gameplay/Blueprints/WorldElements/Pickups/BP_Pickup_<Item>`,
    herbs and pouches), and uses a few of them for many items: a herb's look on the ground is its
    class's, whatever its `Reward` holds (Marigold lies as `BP_Pickup_MediumHealingHerb`). Materials
    have none.
  - A pickup's components: `RootComponent` (a scene component), `StaticMeshComponent` (the herb,
    `SM_GPE_<Herb>` with `MI_GPE_<Herb>`, its origin at its base), `InteractionComponent` (a
    `SwtQuestInteractSphereComponent`, hidden, which the cat collects it by), `EffectComponent`,
    `UIDComponent` and `PickupHintComponent` (the sparkle, Niagara). The herbs' textures are 2048 x
    2048 DXT1.
  - Hiding `StaticMeshComponent` and adding a `SkeletalMeshComponent` with `AddComponentByClass`
    worked: with no animation it draws its mesh in the reference pose, so a mesh with every vertex on
    the root bone shows as modelled, at the actor's origin. The cat's whole body showed that way,
    standing, in the default orange of its material without the game's settings. An accessory's
    material takes a `MaterialInstanceDynamic` with `LYR1 Albedo` (the picture), `LYR1 ARM` and
    `LYR1 Normal` (`/Engine/EngineMaterials/FlatNormal` loads), as on a cat.
  - Collected with Interact, the pickup hides itself (`bHidden`) and its added component with it.
  - A cat's location is the middle of its body, about 30 cm above the ground, so a pickup dropped
    there floats; a line traced down from just above finds the ground, but one started inside a rock
    hits where it starts.
- **Bartering** shows an accessory you already have as an empty slot: the Cedar Cuff's went blank
  once one was picked up, and a mod's new look does the same.
- **Take care:** picking up an item with an invalid accessory tag (`Cosmetic.Head.1`) got it into
  the save, and the game crashed on quitting.

## Cats of a mod's own

Worked out on 2026-10-24 for `Game.npcs`, and checked in game with two cats.

- **The class:** the game's clan cats in the world are `BP_Quest_Filler_C`
  (`/Game/Gameplay/Blueprints/Quest/Givers/BP_Quest_Filler`, a `SwtAdventureFillerActor`). There
  were 41 in the forest, and `Game.cat(actor)` reads their looks and name.
- **Spawning:** `BeginDeferredActorSpawnFromClass` and then `FinishSpawningActor` give a working cat
  with the body, fur, tail and ears.
  - The `DefaultCustomData` set in between keeps its `CatSize` and name IDs.
  - The rest of its look is made up when the cat is set up: the shape, pattern, markings and colour and
    eye slots, all of it, whatever `DefaultCustomData` held.
  - With `bOverrideColors` set in `DefaultCustomData`, the game keeps every field of it instead (seen on
    2026-10-27): the tail, ears and fur meshes, the body's shape, the pattern and marking textures, and the
    coat, pattern, marking and eye colours of the slots it names. A field left alone stays at its default,
    0 for all of them (`CatSize` 0.4). That's how `Game.npcs.spawn`'s `look` and `slots` go on.
  - Changed after the spawn, the look isn't drawn: written into `MeshCustomizationComponent.CustomData`,
    `RefreshShape` moved the anim instance's shape values (`ABP_CatMaker`'s `BodyShapeValue` and the rest)
    but kept the meshes, the pattern texture and the colours.
- **Colours** are vector parameters on each part's dynamic material:
  - "Fur Color", "Pattern Mask Color", "Markings Mask Color", "Nose Color", "Paws Color" and
    "Whiskers Color", plus "Ears Color" on the ears.
  - The eyes are scalars, `IndexIrisColorCurveLeft/Right`: a row of the eye atlas, the iris slot + 1.
  - Setting them recolours the cat at once.
- **The save:** the cat's `SwtAdventureIUIDComponent` has `bWasDynamicallySpawned` and no ID (-1).
  wcmods switches it off before the spawn finishes. After a session with two spawned cats, the
  save's `NPCData` was the same size as before.
- **The label and the prompt** (worked out on 2026-10-27, on a spawned filler beside the medicine cat):
  - **The label.** Every quest actor has a `QuestWidgetComponent` whose widget, a
    `WBP_GuiQuestNpcWidgetsContainer` (screen space), holds `mcGuiActorName` (`mcGuiTextName`,
    `mcGuiTextRole`, `mcGuiTextExtraInfo`) and `mcGuiActorStatus` (`CanvasAvailable`, `CanvasOngoing`,
    `CanvasCompleted`). The game fades them in by distance with their render opacity. For a spawned filler
    the label is there, with a placeholder name and role ("Deputy"), at opacity 0, and nothing fades it in.
    Setting the texts and the opacity shows it, in the game's style. The status icon sits over the first
    line unless it's moved up (render translation -100).
  - **The prompt.** The game's Talk prompt didn't come up for a spawned filler, even with its
    `InteractComponent` (a 22 cm sphere, collision off on a spawned one) switched on and an `NpcDialogue`
    given (the medicine cat's is in `QuestComponent.NpcDialogue`). The choice of what's in reach is made in
    native code, and `QuestPlayerController:OnCanInteract` never fired in a hook, not even for a pickup.
  - **The prompt's widget.** The HUD's `mcGuiContextualMenu` (`WBP_GuiContextualMenu`) has three
    `WBP_GuiExplorationPrompt`s: `mcGuiTextAction` and `mcGuiButtonAction`, a `GuiActionButtonControl` whose
    `ActionCommand` 67 is Interact and draws its key or button. The game hides the menu again every frame
    when nothing is in reach, so wcmods makes a prompt of its own from the same class, on the HUD's
    `CanvasExploration`, and listens to Interact's keys itself (`Player_Interact` in the save's
    `InputKeyboard` and `InputGamepad`).
  - **The quest HUD.** `WBP_GuiHudGameWrc`'s `mcGuiQuestObjective` (`GuiHudCurrentObjectives`: `mcGuiTitle`,
    `mcGuiLocation` in `CanvasLocation`, `mcGuiActivity`, and `mcGuiGoal1` to `3`, each with `mcGuiIcon`,
    `mcGuiGoalName`, `mcGuiGoalValues` and `CanvasCheck`; `AniMessageShow`/`Hide`) stays as it's set when
    the game has no quest of its own to show. The banners `mcGuiBeginQuestMessage`, `mcGuiQuestUpdateMessage`
    and `mcGuiQuestCompetedMessage` play with `SequenceEvent()`; their text blocks aren't properties
    (`mcGuiTextQuestType`, `mcGuiTextQuestName`, `mcGuiTextObjective`, `mcGuiText`, found by walking the
    widget tree), and the begin banner stays until it's hidden.
  - **Map markers.** A `SwtAdventurePOIComponent` added at runtime (`AddComponentByClass`, then
    `FinishAddComponent`) on any actor, a plain `Actor` spawned for a place included, registers with the
    minimap (`GuiHudMinimap.POIWidgetMap` grew by one) and leaves it when the actor goes. Its
    `CustomPOIIcon` takes the `MI_UI_Icon*` materials; `bStickPOIToBorder` keeps it at the minimap's edge.
    Textures and materials load with `LoadAsset` on their whole object path, not the package's.
  - **Dialogues** are `NpcDialogue` graphs (`GenericGraph`) of `QuestDialogueNode`s: camera actions,
    `QuestDialogueTalkingNode`s with a `Paragraph` and a `TalkingSource` (0 the cat, 1 you; several "you"
    children of one node are the answer choices) and screens (`QuestDialogueActionCreateScreen`). Giving a
    spawned cat one didn't make the game talk with it, for the reason above.
- **Keys:** the game's Interact (E) would also use whatever else is in reach (a travel tunnel opened
  the map). The examples talk on T and the controller's d-pad up, read from the game's own input
  (`WasInputKeyJustPressed`). That also works with keys the agent posts to the window, which UE4SS
  key binds don't see.

## Scars

Worked out on 2026-10-25 on your cat in game, for `cats.json`'s `"scars"`.

**Where they're kept:** a cat's look (`FCatCustomData`, the text in the save) has `ScarEyeId`,
`ScarEarId`, `ScarBodyId` and `ScarChestId`, 0 (or left out) for none. Clan cats get them by role
(`Scars.csv`); your cat gets them from boss fights.

**How they're drawn:** the look component (`USwtAdventureCustomizableMeshComponent`) turns the
numbers into the body materials' parameters. `RefreshShape()` doesn't redraw scars, but
`OnInjurySystemChanged(true)` does. The game's Injury system setting (`Shared/SettingsData/InjurySystem`,
on the Gameplay settings panel) is `EnableScars`, which shows or hides them all.

| Place | Numbers | What the game does |
|---|---|---|
| Ear | 1–6 | Swaps the ear model: 1 torn right, 2 torn left, 3 both torn, 4 notched right, 5 notched left, 6 both notched (seen on the Mid Upright ear: `SK_Mid_Upright_torn_right` and so on). 7 and up show as 6 |
| Eye | 1–6 | `Enable Eyes_Scars`, with `Eyes_Scars_VariationID` 0 (1–2), 2 (3–4) or 1 (5–6). The eye is also shut |
| Back (`ScarBodyId`) | 1–6 | `Enable Back_Scars`, with `Back_Scars_VariationID` 0 (1–2), 1 (3–4) or 2 (5–6). 7 shows as 1 |
| Chest | 1–2 | `Enable Chest_Scars`, with `Chest_Scars_VariationID` 0 or 1. 3 shows as 1 |

**What they look like:**
- **The shapes:** `T_Cat_Scars_Gradient` holds them, a 2 × 2 grid in each channel. A scar's
  variation is its cell.
  - Red, the eye: 0 a scarred ring, 1 claw marks, 2 a single slash.
  - Green, the back: 0 a star-shaped bite, 1 claw marks, and nothing in 2. So back 5 and 6 seem to
    show no scar, which fits the game's own cats only using 2–4.
  - Blue, the chest: 0 a bite, 1 claw marks, 2 a long slash. No chest number reaches the slash.
  - Which cell each variation shows is read off the texture, in order (0 top left, 1 top right, 2
    bottom left). In game only eye 1–2 (the ring) and 5–6 (marks) were seen; the slash (eye 3–4), the
    back's and the chest's shapes, and back 5–6 showing nothing aren't checked yet.
- **The places:** `T_Cat_Scars_Zones_01` and `_02` are masks of where scars go, in the same channels.
  - The eye's masks are the cat's right eye (01) and left eye (02). Checked in game with the cat
    facing the camera: eye 1 and 5 shut its right eye, and 2 and 6 its left.
  - The back's masks are two spots on the back, which is which not checked yet.
  - The chest's mask is the same in both.
- **One texture for all:** odd numbers set `Scars Zones` to `_01` and even ones to `_02`, but a cat
  has one `Scars Zones`. So an eye and a back scar of opposite parity may not both show where their
  numbers say. Not tried yet.
- **Not from the materials alone:** setting the materials' scar parameters directly (without the
  numbers) didn't stay: the game puts the look back from the numbers, and that also shuts the eye.

The clan cats in a save use eye 1–2, ear 1–6 and back 2–4, and none had a chest scar.

## The game's own UI

Worked out on 2026-10-25 for `Game.dialogue`, and checked in game with both example cats.

**How the game builds its UI:**
- It's UMG, the same as the mod menu. Each screen is a widget Blueprint (`WBP_…`) on a native class:
  `USwtScreen` for screens, and `UGuiWidget` / `UUserWidget` for their parts.
- Screens have the animations `AniScreenIn` and `AniScreenOut` (from `USwtScreen`, 0.25 s each).
- A script can make the game's own widgets and put them on screen, and they look exactly like the
  game's. What it can't do is ask the game to open one of its screens: the GUI manager's
  screen-opening code isn't reflected.

**The dialogue box** (`/Game/Art/UXD/Blueprints/QuestDialogs/WBP_QuestGiver_Dialogue`):
- **Its class:** `UQuestGiverWidget`, from `UQuestBaseWidget`. `…_Dialogue2` and `…_Dialogue3` are
  other versions of it.
- **Its parts:**
  - `mcGuiDialogueTalker`, a `WBP_GuiDialogueTalker` (`UGuiDialogueHead`), holds the speaker's name
    (`mcGuiTextName`) and a clan badge (`mcGuiClanIcon`);
  - `mcGuiTextParagraph` is the line, a `TextBlock` that wraps long lines itself (there's also an
    unused `mcGuiTextParagraphRich`);
  - `mcButton1` … `mcButton4` are the answers (`WBP_GuiButtonDialogueOption`);
  - `mcGuiNext` is the "next" prompt (`WBP_GuiDialogueNext`, showing Enter on a keyboard);
  - `CanvasPanelDialog` holds them all.
- **Making one outside a quest** works without a crash, with no quest, NPC or player set:
  1. `WidgetBlueprintLibrary:Create(controller, class, controller)`, then `AddToViewport(1500)`.
  2. Putting it on screen hides `CanvasPanelDialog` and the line (visibility Hidden), as the game
     shows them while a dialogue goes on. So they're made visible after `AddToViewport`, not before.
  3. The line is centred with `SetJustification(1)`, as the game's lines are. The answer buttons
     are collapsed.
  4. `PlayAnimation(AniScreenIn)` fades it in. `AniScreenOut`, then `RemoveFromParent` 0.3 s later,
     fades it out.
- **What it is then:** only a picture. Made Hit-test invisible, it takes no input, so the script
  moves the talk on with its own key, and Enter (the key the box shows).
- **The clan badge** shows the widget's default. Setting it hasn't been tried.

**One talk at a time.** Each UE4SS mod has its own Lua state, so each gets its own box. Two mods'
cats in reach of the same key talked at once, in two boxes drawn over each other. `Game.dialogue`
keeps a claim in UE4SS shared variables (`WCModsDialogue.owner` and `.at`), renewed while a box is
up, and `busy()` is true for the other mods. When two cats are in reach, the first script to hear
the key talks.

**The screens' tabs** (worked out on 2026-10-25, the basis of the C++ SDK's `ui::tab`):
- A screen with tabs (the pause screen `WBP_GuiScreenPause_C`, the inventory `WBP_GuiPopupInventory_C`,
  the settings `WBP_GuiPopupGameSettings_C` / `WBP_GuiPopupSettings_C`) keeps them as `GuiButtonState`
  controls (`WBP_GuiButtonTab_C`) in a `HorizontalBox` (`HorizontalBox_23`, between a key hint control on
  each side and two spacers), and lists them in its `NavControls.ControlsNavigation` (a `LinearNavigation`).
  The tab keys (1 and 2 on a keyboard, the shoulder buttons on a controller) move `CurrentNav.CurrentControl`
  along that list and the screen's native `OnNavigationChanged` switches the panel (`CurrentPanel`,
  `CurrentGrid`); `ControlSelected` follows. The tabs don't answer the mouse at all.
- A control appended to that list is reached by the keys and selected like the game's own (its
  `CanvasSelected` shown), and the game leaves the last panel up: that's how a mod's tab gets its page in.
  A tab made from `WBP_GuiButtonTab_C` with `WidgetBlueprintLibrary:Create` shows its `Text` property once
  it's constructed (set it before adding it to the row; its text blocks are `mcGuiTextNormal` and
  `mcGuiTextSelected`); it has no inner `UButton`.
- The pause screen's panels sit in `CanvasPanels`, the inventory's grids in `CanvasGrids` (with
  `mcGuiItemInfo` beside them), the settings' panels straight in `CanvasContent`.
- The cat maker (`WBP_GuiScreenCustomization_C`) has no tab row: its categories are a circular icon menu,
  `mcGuiCategoryMenu` (`GuiCircularMenu`: radius 900, 30° apart, four `FCategoryMenuItemsData` icon
  pairs, items made at construct). Making that screen outside the flow and putting it on the viewport
  closed the game (an access violation), so adding a category there is still open.
- **Keys:** on a keyboard, P opens the pause screen and I the inventory; Backspace is Back. Enter pauses
  only while the game is in its gamepad mode (the HUD showing controller glyphs; Enter is the action
  `Player_Pause`). Keys posted to the window (the agent's `key`) are different: Escape pauses every time,
  while a posted P only sometimes does. T opens the map in keyboard mode. The pause screen's Main Menu
  asks first, in `WBP_GuiPopupCommonYesNo_C` (yes is `mcGuiButtonYes`). A closed screen stays
  as an object a while (`FindFirstOf` finds the dead one first): the one showing is the one with
  `IsInViewport()` and `IsVisible()` both true.
- **Slate focus:** `SetKeyboardFocus` on a widget takes the keyboard away from the game's screens until
  `WidgetBlueprintLibrary:SetFocusToGameViewport()` or the game's own focus handling gives it back.

**The main menu** (worked out on build 26184573, 2026-10-26, for the Sandbox mode mod's button; seen
in game):
- Its buttons are `WBP_GuiButtonMenu_C` in the vertical box `VerticalBoxButtons`. Each one's slot has
  a bottom padding of -90, except Exit's (0). The keys move along `NavControls.ControlsNavigation`, a
  `LinearNavigation`.
- **A button of a mod's own:** one made with `WidgetBlueprintLibrary:Create` and added to the box
  shows in the game's style. Appended to the nav list (`list[n+1] = w` grows the TArray from Lua), the
  keys reach it and it takes focus like the game's own.
- **But it's never pressed.** Real presses on the game's own buttons call `SwtScreen:OnUIPress`; the
  screen never calls it for an added button. A mod polls `Game.pressed("Enter")` while its button is
  `NavControls.CurrentControl` instead.
- **Placing it:** `ShiftChild` can't be called from Lua (UE4SS reports a TrivialObject), so
  to put a button in the middle, `RemoveChild` the ones after it and `AddChildToVerticalBox` them
  back in order.
- `w.ParentScreen = s` fails without an error; setting it with `Game.set` works.

**The cat choice** (`WBP_GuiScreenSelectYourCat_C`, seen in game, build 26184573):
- `mcGuiButtonCatN` is save slot N-1. `mcGuiInfo2` is its "<Clan> Prophecy N%" line.
- The keys move through a native `GridNavigation` (`CurrentNav`), so unlike the main menu's its list
  can't be changed from Lua.
- The quest manager's `OnCharacterSlot(slot)` fires when a cat is chosen, and once at startup with the
  last slot played; it doesn't fire as the cursor moves between cats.
- `SetIsEnabled(false)` (`UWidget`) greys a cat's portrait, but the cat can still be chosen.

**Not tried yet:**
- The HUD's `OnItemPickedUp(tag, quantity, total, bCanShowPopup)` is reflected. Calling it may give
  the game's "… OBTAINED" toast for anything.
- Answers in the dialogue box's own buttons.
- The rewards and bonding level-up parts (`UGuiDialogueRewards`, `UGuiDialogueLevelUp`), which the
  game shows in the same box.
- The game's quest log (`UGuiHudQuest`) works from native quest objects (`UQuestBase`), so a mod's
  quests can't go in it without real quest data. They go on the mod menu's Quests page instead
  (`Game.quests.report`).

## Input

Worked out on 2026-10-27 in game (build 26184573), for the in-game key remap (`WCModsRemap`,
`wcmods/gameremap.py`).

- **Legacy input, not Enhanced Input.** The controller (`BP_WrcGameplayPlayerController_C <
  AWrcGameplayPlayerController < … < ASwtPlayerController`) has a `WrcPlayerInput` (`< SwtAdventurePlayerInput
  < SwtPlayerInput < PlayerInput`) and an input component, `PC_InputComponent0` (`WrcInputComponent <
  SwtAdventureInputComponent < SwtInputComponent < InputComponent`). The cat's `PawnInputComponent0` is the
  same class. The Enhanced Input plugin is in the build but nothing uses it.
- **The bindings can't be reached.** `InputSettings` holds only the engine template's (Jump on Space and
  the pad's A, Move Forward / Backward, Move Right / Left, Turn and Look Up on WASD, the mouse and the
  sticks). The game's own actions, named after its `ECommands` enum (`Player_Interact` …), are put into the
  player's `PlayerInput` at runtime. They come from the save's `Shared.InputKeyboard` and `InputGamepad`,
  plus keys the save doesn't list: I Inventory, K Quest, M Map, L Meow and Escape Pause (its Controls screen
  shows them), and the left mouse button for Interact. `PlayerInput`'s action and axis mappings aren't
  reflected (only `DebugExecBindings` and `InvertedAxis` are), and neither is anything on the rebinding
  screen (`GuiPopupControlConfig`, `GuiCustomConfigKey` with an `ActionCommand`). So no script can change
  a binding. The game's pictures of keys can still be changed (below, "Key pictures").
  `InputSettings:AddActionMapping` and `ForceRebuildKeymaps` are reflected, but the engine's rebuild resets
  every player's mappings to `InputSettings`' and would lose the game's own (from the engine's code; not
  tried).
- **What a key does.** Each key the controller's input component gets goes to
  `SwtPlayerController:OnKeyPressed(Key)` and `OnKeyReleased(Key)`. That's every key, mouse buttons
  included (the middle button came through), and controller buttons presumably too. Each of the game's
  actions bound to the key goes to `SwtPlayerController:OnListenCommand(Command, InputEvent)`, before
  `OnKeyPressed`. Each open screen (`SwtScreen`, the HUD's two included) has an input component of its own
  and gets the same as `SwtScreen:OnKeyPressed(Key, fromPlayer)` and `OnListenCommand(Command, InputEvent,
  fromPlayer)`.
- **Who hears a key.** While you explore: the controller, and two screens, the HUD
  (`WBP_GuiHudGameWrc_C`) and `WBP_GuiScreenOnlineOver_C`. With a menu open (the pause screen, the map,
  the inventory): only that menu's screen, not the controller or the HUD. The engine's cursor flag can't
  tell them apart: `bShowMouseCursor` read false in the pause menu and the map, as the game draws its own
  cursor (so `WCModsPlayState`, which tests it, reports those menus as play).
- **In a fight**, keys go to all of them at once: the controller, the HUD's two screens, the fight menu
  (`WBP_GuiPopupCombat_C`: Attack, Rest, Herbs, Flee, then the moves) and `WBP_GuiHudCombatOver_C`. The
  fight menu moves with `Button_Up`/`Down` and picks with `Button_Confirm`, as other menus do. (A fight
  for testing: teleport behind a roaming animal, a `BP_Exploration_Character_Base_C` outside a
  `MovieScene`, and pounce. Digging a prey burrow gave Earth & Stones instead of a fight.)
- **What each key sends** is the same in play, in the pause menu and in a fight. Every key and mouse button was
  pressed on its own with every command turned into NoCommand, so nothing happened (`keymap.KEY_COMMANDS`):

  | Key | Commands |
  |---|---|
  | W / Up, S / Down | `Button_Up`, `Button_Down` |
  | A / Left, D / Right | `Button_Left`, `Button_Right` (A and D also `AnimTool_PreviousAnim`/`NextAnim`) |
  | Enter | `Button_A`, `Button_Confirm`, `Button_Skip` |
  | BackSpace | `Button_B`, `Button_Back` |
  | Escape | `Player_Pause` |
  | SpaceBar | `Button_Y`, `Player_Pounce`, `Player_PhotoMode_Shoot`, `AnimTool_PlayLoopAnim` |
  | E | `Button_X`, `Player_Interact` |
  | C | `Player_Friend_Talk`, `Player_Drop` |
  | X | `Player_ReturnToCamp`, `Player_Den_Place`, `Player_PhotoMode_Exit`, `AnimTool_StopAnim` |
  | Q | `Player_Scent_Tracking`, `Player_PhotoMode_HideUI` |
  | R | `Button_Randomize`, `Player_Camera_Reset` |
  | I | `Player_Show_Inventory`, `Minigame_Button_A` |
  | J | `Player_Play`, `Minigame_Button_X` |
  | K | `Player_Show_Quest`, `Minigame_Button_B` |
  | L | `Player_Growl`, `Minigame_Button_Y` |
  | M | `Player_Show_Map` |
  | P | `Button_Start` |
  | T | `Button_StickR` |
  | V | `Button_Select` |
  | 1, 2, 3, 4 | `Button_ShoulderL`, `Button_ShoulderR` (the menus' tabs), `Button_TriggerL`, `Button_TriggerR` |
  | LeftShift, RightShift | `Player_Run` (LeftShift also `AnimTool_PlayAnim`) |
  | LeftControl, RightControl, right mouse button | `Player_Crouch` |
  | Left mouse button | `Button_Confirm`, `Player_Interact` |

  Nothing else sends a command: the other letters, 0 and 5 to 9, F1 to F12, the number pad, Tab, CapsLock,
  Delete, Home, End, PageUp, PageDown, the punctuation keys, the middle and side mouse buttons and the
  wheel. All of them still reach `OnKeyPressed`. Tilde, Alt, Insert and F11 weren't tried. Two more
  findings:
  - **Pause is on Escape.** The save's `Player_Pause` says Enter, but Enter confirms. P sends
    `Button_Start`.
  - **Mouse presses in menus** go to the button under the cursor. Only their releases reach the screen.
  - **A probe glitch:** in one run, keys stopped reaching the game for a few seconds after a posted F10.
    Pressed again on their own, they were fine.
- **Movement and the camera are axes.** W sends only `Button_Up`, and no reflected function sees the
  axis values, so nothing inside the game can move them. The key remapper outside the game does. Other
  screens read keys that way too, so a key standing for one there needs the key remapper:
  - the map zooms on Up/Down and moves on WASD (holding K for Down didn't zoom; the `Map_Axis_*`
    commands are never sent);
  - photo mode's camera moves on Shift+WASD and goes up and down on Z/C (Z sends nothing);
  - the clan selection and the cat maker turn the cat on Q/E.
- **The game's screens**, surveyed on 2026-10-27 with the test remaps installed: I/K for Up/Down, U for
  Enter, O for Backspace in menus, and `Button_ShoulderR` on PageDown. The screens that hear keys, and
  what the remaps did:

  | Where | Who hears keys | Seen |
  |---|---|---|
  | Title (`WBP_GuiScreenMainMenu_C`) | it and the front end's controller | K, I moved; U opened Prophecy |
  | Select your cat (`…SelectYourCat_C`) | it and the title behind it | K, I moved through the cats; O back; U continued |
  | Clan selection (`…SelectClan_C`) | it and the controller | K and D moved, U chose |
  | Cat maker (`…Customization_C`) | it and the controller | K moved down the sliders; holding O about 5 s asked to go back, as Backspace does |
  | Pause (`WBP_GuiScreenPause_C`) | it | K, I, U; tabs on PageDown. Quest has sub-tabs on 3/4 (`Button_TriggerL`/`R`) |
  | Help (`WBP_GuiPopupHelp_C`), Settings (`…GameSettings_C`) | it and the pause screen | K moved down the lists; O back. Settings has no key bindings (Player Configuration is vibration, inverting and sensitivity) |
  | Yes/no (`…CommonYesNo_C`) | it and the screen behind | O cancelled; A/D choose |
  | Photo mode (`WBP_GuiPopupPhotoMode_C`) | it, the HUD and the controller | K moved down its list; Q hid the UI; X left |
  | Inventory (`…Inventory_C`), map (`…WorldMap_C`) | it | tabs on PageDown, O closed; the map's zoom and move as above |
  | A fight (`WBP_GuiPopupCombat_C`) | it, `…HudCombatOver_C`, the HUD and the controller | K, I, U and O drove the fight menu and the moves |
  | Talking to a cat (`WBP_QuestGiver_Dialogue2_C`) | it alone | F (Interact moved) started the talk; U moved it on |

  Not reached: decorating a den (the apprentice had no den to enter), the name screen, cutscenes,
  minigames and the online screens. Every screen but the HUD counts as a menu for the in-game remap.
  `WCModsPlayState` now calls a menu any visible `GuiScreenWrc`. That covers every screen above except
  photo mode and talks (the dialogue box isn't one), which it counts as play, as it always has. It used
  to test `bShowMouseCursor`, which said "play" in every menu.
- **`ECommands` moved in patch 1.1.** `Player_Mouse_Camera_Up` and `_Right` were added after
  `Player_Camera_Right`, so everything after them is 2 higher than in a class dump of the first release
  (Interact 65 → 67; read from the exe's table, *The game's enums*). Read the numbers from the game:
  `StaticFindObject("/Script/SwtEngine.ECommands"):ForEachName(function(name, value) … end)`, or
  `Game.enumNames("/Script/SwtEngine.ECommands")` in a script.
- **Commands can be sent and changed.**
  - **Sending:** `pc.InputComponent:OnListenCommandInternal(77, 0)` from Lua opened the inventory, as
    `pc:OnListenCommand(77, 0)` did. It reaches the controller's input listeners only, not the screens.
  - **Changing:** a pre-hook on `OnListenCommand` that sets the command with `param:set()` changes what
    the game does: 77 → 76 opened the map on I. NoCommand (0) does nothing.
  - **Not hookable:** `SwtInputComponent:OnListenCommandInternal` never fired in a hook for real keys,
    as the game calls it natively, and `SwtManager:OnListenCommand` and `OnKeyPressed` never fired.
- **The in-game remap** is built on that. On a remapped key's `OnKeyPressed`/`OnKeyReleased` it sends the
  commands to whatever heard the key (the controller through its input component, or the screen). In
  `OnListenCommand` it sets the game's own command to NoCommand when the key it came from
  (`WasInputKeyJustPressed`/`Released`, `IsInputKeyDown`) is one the command moved off. The controller and
  the HUD's two screens get the play set, any other screen the menu set. Seen in game:
  - Interact on F opened the travel map at a tunnel, and E did nothing there.
  - Run on G: 2 s of S+G went 361 units against 256 walking, and LeftShift no longer ran.
  - Scent tracking on the middle mouse button turned on, and Q did nothing.
  - The pause screen's Controls tab showed F for Interact (key pictures, below).
  - In the map, E still toggled the legend (its `Button_X`).
  - Map on N opened the map in play and closed it from inside the map screen; M did neither.
  - **Menu keys:** in the pause menu, I and K moved the selection (the arrows still did), U confirmed
    Resume, and O closed the map, the inventory and the quest page. In play, K and I kept their own jobs.
  - **Tabs:** `Button_ShoulderR` on PageDown went to the next tab, and 2 no longer did.
  - **A second Interact:** H, standing for E while you play, opened the travel map.
  - **In a fight:** K and I moved through Attack, Rest, Herbs and Flee (Down still did), U opened Attack
    and used Provoking Stare, which hit, and O went back. K didn't open the quest page mid-fight.
- **Key pictures** (worked out on 2026-10-27 in game, build 26184573):
  - **The widgets.** Each picture of a key is a button widget holding a command and an image,
    `mcGuiButtonImage`: `GuiActionButtonControl` (`ActionCommand`; the HUD's prompts in
    `mcGuiContextualMenu.mcGuiPrompt1`–`3`, the scent and other HUD hints, and the Controls tab's
    `GuiConfigButtonControl`s inside each `GuiCustomConfigKey`) or `GuiCommandButtonControl`
    (`ButtonCommand`; the footers' `mcGuiCommandBack` (`Button_Back`), `mcGuiCommandConfirm` and
    `mcGuiCommandUse` (`Button_Confirm`), and the tab hints `mcGuiControl1`/`2` (`Button_ShoulderL`/`R`),
    `mcGuiControlLT`/`RT`).
  - **Command to key** is native: the game finds a key bound to the command (Interact's prompt shows the
    left mouse button, not E), from the bindings no script can reach.
  - **Key to picture** comes from the GUI manager's tables, `DataKeysMap` (`DT_Keys`, 94 rows: keyboard
    keys and the two main mouse buttons) and `GamepadButtonsMap.DataGamepadButtonsMap` (one table per
    `EGuiConsolesTypes`: 1 is `DT_GamepadButtonsKeyboard`, 4 and 5 `DT_GamepadButtonsXbox`, and PS4, PS5
    and Switch ones). Rows are `FUIButtonsMap`: `Key`, soft `Image` and `HudImage`, `KeyCode`, `Enabled`.
    UE4SS reads them with `ForEachRow`, and a soft pointer's path is
    `ptr:GetObjectID():GetAssetPathName():ToString()`. The textures load with `LoadAsset`.
  - **When the game sets one:** in its native setup, `OnSetupInputs` (reflected, but a hook never fires:
    it's called natively). That runs when a button is set up and when the input device changes, and the
    HUD's contextual menu runs it for its prompts all the time (a picture set on a prompt from Lua was
    back to the game's the next frame). A prompt made from Lua and given a command gets no picture until
    something sets it up; calling `OnSetupInputs()` from Lua puts the right one on.
  - **Brush size** is the widget's own (32×32 on the footers, 128×128 on prompts), whatever the texture,
    so swapping the texture keeps the layout.
  - **How the in-game remap changes them.** The setup writes to whatever image `mcGuiButtonImage` points
    at. Pointed at a new `Image` made with `StaticConstructObject` and never drawn, the game's choice
    lands there, and the image on screen keeps what a script puts on it. `WCModsRemap` finds the buttons
    with `NotifyOnNewObject` on the two classes (it walks up the class chain, so their Blueprints count),
    swaps the image of each whose command has a new key, and every frame shows the new key's picture from
    the table the game's picture came from (or the game's own when the command didn't move on that
    device, or the key has no picture there). A button counts as play or menu by the first `SwtScreen` up
    its outers; one outside any screen (a prompt made from Lua) is play, and so is the Controls tab, which
    shows play's keys. It compares with the image itself each frame: a prompt's animations reach the
    image by name, and one put the blank picture back on a prompt that then showed again. And a picture the
    game was still loading when the image was swapped lands on the image on screen: the first pause
    screen's Back once showed the widget's default (the pad's A) that way. A key's picture there that the
    script didn't put is taken as the game's choice.
- **Not tried yet:** a controller, the mouse wheel, and a key held while a screen opens (the script lets
  go of an action whose key is no longer down, checked every few frames).

## Game mechanics

The rules of play are in [mechanics/](mechanics/README.md):
- [combat](mechanics/combat.md): the damage formula, hit chance, stances, every move;
- [progression](mechanics/progression.md): XP, ranks, stat growth, traits in play;
- [exploration](mechanics/exploration.md): movement, stamina, stealth, scent, the map;
- [clan life](mechanics/clan-life.md): fresh-kill, dens, visits, gifts;
- [items](mechanics/items.md): herbs, pouches, bartering;
- [quests and bonding](mechanics/quests-and-bonding.md);
- [NPCs](mechanics/npcs.md).

**Struct facts found there:**
- **A fighter's combat component** (the actor's +0x848) holds:
  - its current `AttackMove` row at +0x128;
  - its stance at +0x1A0;
  - its stats at +0x1A8 (`Prowess` +0x1C4 … `Stamina` +0x1D8);
  - its combat tuning at +0x378–0x3A0;
  - its clan at +0x3D8 and its level at +0x3DC.
- **`CombatStance` rows:** the multipliers by defender stance at 0x08–0x1C (Neutral first),
  `Attack` at 0x20 and `Defense` at 0x21.

## Open questions

- **Traits:** how the game breaks a tie between two equal scores, and whether options 1–10 are
  left to right in the creator. Also, why each `…Value` is its `…Offset` + 3 in the one save
  looked at (groups of options?).
- **Cheats:** where the cheats access level (`ESwtCheatsEnableType`) is set (`EnabledMode` is 7),
  whether raising it opens the cheats popup and the key cheats, and which of the cheats manager's
  switches the release build obeys (`bUseForcesQuests`, `bSkipSequences` and `bSkipTutorial` it
  doesn't).
- **Animations:** whether the named characters' own skeletons (`SK_NPC_Brightheart_Skeleton`...) can
  play the cats' sequences; ACL's curves (the cat's ACL sequences keep theirs in ACL too, which wcmods
  doesn't read).
- **Scripting:**
  - **Items:** how to put items in the inventory from a script without a pickup (the inventory
    is native; `Game.items.drop` leaves a pickup to collect).
  - **Accessories:** whether a new texture variation of an accessory (a 2nd or 3rd entry in
    `AccesoryVariations`) can be added and worn.
  - **Fights:** how to end one cleanly (`EndCombat` doesn't), and whether the combat director's
    `OnRegisterDamage` hook sees every hit.
  - **Save stores:** what the save manager's `Get/SetGameProgressionData` keys are (`"Level"` read
    0). They're account-wide (`Shared`), not a cat's.
- **Mouse look:** whether the game ever overrides the root's yaw in free mode. An old build's
  log suggested one turn in five was lost, but the code says no, and the current build's log
  shows none lost after the first seconds.
- **Names:** whether NPC cats carry `SwtAdventureCustomizableMeshComponent` with name IDs (the
  mod menu's cat names rely on it).
- **New content:** whether cooked paks from a `Wrc` project load as expected (unsigned paks do).
- **Combat:**
  - Does Resilience reduce damage? The code reads only the stance table's `Attack` column.
  - Does Agility-based speed set turn order?
  - What makes a forced miss (the defender's flag at +0x1A1)?
  - What do `Flee.Penalty` and the warrior-code tally do?
- **Traits:**
  - Does a Blueprint use the Patient rows?
  - What does `Bonding.TraitModifier` do?
  - Do the Energetic drain values replace the normal drain or add to it?
- **Progression and dialogue:**
  - Does a dialogue answer's `Score` go to your bond with that cat?
  - Do levels stop at a rank's cap until the rank-up quest?
- **Clan life:**
  - Are den build times real hours?
  - What are `FreshKillPile.ResetCycles`, `Stamina.Bonus.Modifier.1..16` and the sunspot rewards?
  - What is `ClanSpecificBase.csv` for?
