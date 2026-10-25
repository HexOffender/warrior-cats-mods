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
| Game | Warrior Cats: Clans of the Forest, Steam app 3960600, build 24847281 |
| Engine | Unreal Engine 5.7 (Shipping), project name `Wrc` |
| Exe | `Wrc\Binaries\Win64\Wrc-Win64-ShippingDRM.exe`, 183,670,344 bytes, SHA-256 `f50eb374f8611e4e…` (its PE timestamp, 1974, is a placeholder) |
| Code | C++ classes are `Swt…` (the studio's shared framework) and `Wrc…` (this game), in `/Script/Wrc`; Blueprints are `BP_…_C`, widgets `WBP_…_C` |
| UE4SS | v3.0.1 Beta, Git 83330635 (`experimental-latest`) |

## How we find things

- **Strings to code:** scan the exe for RIP-relative `lea`/`mov` instructions whose target is a
  string's address. `tools/re/xrefs.py <exe> "<text>"` lists both. Tuning keys
  (`Gameplay.Exploration.Camera.TurnRate.Yaw`) lead to the code that loads them. Each key is read
  into a member, so a loader reveals a struct's layout (`tools/re/tunemap.py` maps each key to its
  offset from a dumpbin listing of the loader).
- **Reflection data:** UHT's property tables survive in the exe. Each entry is: name pointer at
  +0, RepNotify pointer at +8, flags (u64) at +16, generator flags (u8) at +24, array dimension
  (u16) at +48 and offset (u16) at +50. Find a pointer to a property's name and decode the table
  around it. Enums are tables of `{const char* name, int64 value}`. `tools/re/uht.py` does both.
- **Disassembly:** `dumpbin /disasm:nobytes /range:<start>,<end>` from Visual Studio. Function
  starts follow `int 3` padding.
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

Detailed in SDK.md, "Game files, repacking and new content". The key facts:
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
- Oodle comes from another game's `oo2core_8_win64.dll` (here Planet Zoo's), through `OodleLZ_Decompress`.

### Cooked packages and DataTables

Worked out on 2026-10-24 on `DT_QuestObjectsInfo`. `wcmods/cooked.py` reads and writes them; its
selftest check decodes all 412 rows, re-encodes them and rebuilds the package byte for byte.

**A zen package (UE 5.7):**
- **Summary:** 60 bytes: `bHasVersioningInfo`, `HeaderSize`, the package name (index, number),
  `PackageFlags`, `CookedHeaderSize`, then the offsets of the imported public export hashes, import
  map, export map, export bundle entries, dependency bundle headers and entries, imported package
  names, and (new in 5.6/5.7) the cell import and export maps.
- **Name map:** an FNameBatch:
  - the count, the string bytes and the hash version (`0xC1640000`);
  - a u64 hash per name: CityHash64 v1.1 of the name in lower case (`wcmods/cityhash.py`; the
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

Worked out on 2026-10-24 for icons and accessory looks (`wcmods/texture.py`), and verified in game:
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

### The save

`%LOCALAPPDATA%\Wrc\Saved\SaveGames\WrcGame.sav`:
- **The container:** a GVAS file whose `SwtSaveGame` holds `Hash`, `GamerId`, `Version`,
  `saveSlots` and `CompressedData`.
- **`CompressedData`:** an Unreal compressed archive (zlib, 128 KiB blocks). It wraps
  `[u32 len+8][u32 len][JSON bytes, each minus 1][u32 len]`. `WrcGame.json` beside it is the
  same JSON in plain text.
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
- **Key bindings** are kept in the save, but the game ignores edits to them, and its rebinding
  screen doesn't work on PC (README, "Remapping keys").

## Engine settings that matter

- **UI scale:** `DefaultEngine.ini` sets `UIScaleRule = ScaleToFit` with
  `DesignScreenSize = (X=3840,Y=2160)`. At 1920x1080 every UI widget is drawn at half size. The mod
  menu sits in a scale box set to (screen height / 1080) / UI scale to undo that. Seen in game: the
  first version was too small to read, and the scaled one is right.
- **Slate's default images are shipped** (`Engine/Content/Slate/…`, 762 files), so stock UMG
  buttons, check boxes, sliders and drop-downs draw properly.
- **Input:**
  - `DefaultInput.ini` sets `DefaultViewportMouseCaptureMode=NoCapture`, so the mouse never
    reaches the game.
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
| `SwtAdventureLevelComponent` | the player state | value is XP; +0x120 and +0x124: the level (20, 20); +0x138: the stats struct, so `Prowess` +0x154, `Strength` +0x158, `Resilience` +0x15C, `Instinct` +0x160, `Agility` +0x164, `Stamina` +0x168 (all equal to the save's) |
| `SwtAdventureFreshKillPileComponent` | the game state (`FreshKillPileComponent`) | +0x130: seconds since it last dropped (counts up in real seconds); +0x134: 90, `Decay.Time` |

Writing them works: the values changed in memory, and the game's own code read them back. The HUD
isn't told, so a bar may show the old value until something else updates it.

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
  - `NPC/PreffixName.csv` (the game's spelling) has 89 prefixes, with a weight per clan.
  - `NPC/SuffixName.csv` has 26 suffixes, with a weight per rank: kits get -kit, apprentices
    -paw, leaders -star.
- **The name shown** is the English text under the key prefix ID + suffix ID
  (`STR_CAT_NAME53` + `_PAW` gives `STR_CAT_NAME53_PAW` = "Otterpaw"), in each language's
  `Strings_*.csv`. Every combination is its own line and is exactly prefix + suffix; one
  (Black + face, `STR_CAT_NAME27_FACE`) is left out on purpose.
- **The save** stores `PrefixNameId` and `SuffixNameId`. A rank-up swaps the suffix ID.
  Apprentices may leave the suffix out, which then comes from their rank.
- **Name screen suggestions:** `PrefixNameFilters.csv` and `SuffixNameFilters.csv` score names
  against a cat's clan, looks and (for suffixes) traits.
- **Rogues** take a whole name from `NPC/RogueNames.csv` (`STR_ROGUE_CAT_NAME_<n>`; the table's
  Name column is only a label).
- **The nine canon cameo cats** use `STR_CAT_NAME_ICONIC_<n>`.
- **`NPC/NameBanList.csv`** holds 30 combinations that are never handed out (canon names).

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
  - Its colour and pattern indexes are replaced by others when the cat is set up.
  - `RefreshShape` on its `MeshCustomizationComponent` doesn't change the colours.
- **Colours** are vector parameters on each part's dynamic material:
  - "Fur Color", "Pattern Mask Color", "Markings Mask Color", "Nose Color", "Paws Color" and
    "Whiskers Color", plus "Ears Color" on the ears.
  - The eyes are scalars, `IndexIrisColorCurveLeft/Right`: a row of the eye atlas, the iris slot + 1.
  - Setting them recolours the cat at once.
- **The save:** the cat's `SwtAdventureIUIDComponent` has `bWasDynamicallySpawned` and no ID (-1).
  wcmods switches it off before the spawn finishes. After a session with two spawned cats, the
  save's `NPCData` was the same size as before.
- **No Talk prompt:** the game shows none for a spawned filler, so the examples draw the name and the
  talk themselves.
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

**Not tried yet:**
- The HUD's `OnItemPickedUp(tag, quantity, total, bCanShowPopup)` is reflected. Calling it may give
  the game's "… OBTAINED" toast for anything.
- Answers in the dialogue box's own buttons.
- The rewards and bonding level-up parts (`UGuiDialogueRewards`, `UGuiDialogueLevelUp`), which the
  game shows in the same box.
- The game's quest log (`UGuiHudQuest`) works from native quest objects (`UQuestBase`), so a mod's
  quests can't go in it without real quest data. They go on the mod menu's Quests page instead
  (`Game.quests.report`).

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
  switches the release build obeys.
- **Scripting:**
  - **Items:** how to put items in the inventory from a script without a pickup (the inventory
    is native; `Game.items.drop` leaves a pickup to collect).
  - **Accessories:** whether a new texture variation of an accessory (a 2nd or 3rd entry in
    `AccesoryVariations`) can be added and worn.
  - **Fights:** how to end one cleanly (`EndCombat` doesn't), and whether the combat director's
    `OnRegisterDamage` hook sees every hit.
  - **Save stores:** what the save manager's `Get/SetGameProgressionData` keys are (`"Level"` read
    0).
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
