# Replacing game files

1. Find the file: `python wcmods.py files "*NPC/*.csv"`
2. Copy it out: `python wcmods.py extract "*NPC/Scars.csv"` (lands in `vanilla/`)
3. Copy it into this mod's `files/` folder **keeping the full path**, e.g.
   `files/Wrc/Content/Gameplay/DataTables/NonAsset/NPC/Scars.csv`
4. Edit it. Keep the header row, the column order, and the CRLF line endings.
5. `python wcmods.py enable <this-mod>` then `python wcmods.py install`

Appearance-only candidates live in `Wrc/Content/Gameplay/DataTables/NonAsset/NPC/`:
CatSize (size ranges per role), Scars (scar chances), and how often each fur colour, pattern,
marking, eye colour, fur type, tail and whisker option appears per Clan (FurBaseColor,
FurPattern1Color, FurPattern2Color, Eye1Color, Eye2Color, PatternType, MarkingType, FurType,
TailType, WhiskerType). These shape cats the game *generates*, so they show up in newly
generated Clans, not cats already in your save. Fur, pattern, marking and tail choices also
steer which names the game suggests.

Not appearance-only: BodyType, EarType and FaceType. The game rolls traits (Ambitious, Brave,
Wise, Energetic, Curious, Patient) from body, ear and face shape, and the gameplay traits
change things like stamina drain and drop chances. `build` warns about these, and about any
file it doesn't know to be appearance-only.
