"""Replacement game files from a mod's files/ folder."""
import os

from ..gamefiles import NONASSET
from ..sdk import Section

ONLINE_FILES = ("OnlineGifts.csv", "VisitRewards.csv")
NPC_DIR = NONASSET + "NPC/"
# NPC generation tables that only change looks. Fur, pattern, marking and tail choices also steer
# suggested names (PrefixNameFilters/SuffixNameFilters), but never traits or stats.
APPEARANCE_FILES = {NPC_DIR + f for f in (
    "CatSize.csv", "Scars.csv", "FurBaseColor.csv", "FurPattern1Color.csv", "FurPattern2Color.csv",
    "Eye1Color.csv", "Eye2Color.csv", "EyeType.csv", "FurType.csv", "PatternType.csv", "MarkingType.csv",
    "PatternBanList.csv", "WhiskerType.csv", "TailType.csv", "ForcedAppearance.csv")}
# Traits (with gameplay bonuses) are rolled from body, ear and face shape (TraitsFilters.csv).
TRAIT_FILES = {NPC_DIR + "BodyType.csv", NPC_DIR + "EarType.csv", NPC_DIR + "FaceType.csv",
               NONASSET + "TraitsFilters.csv"}


def classify(path):
    """'online', 'traits', 'appearance' or 'gameplay' for a game file path."""
    if path.endswith(ONLINE_FILES):
        return "online"
    if path in TRAIT_FILES:
        return "traits"
    if path in APPEARANCE_FILES:
        return "appearance"
    return "gameplay"


class FilesSection(Section):
    id = "files"
    title = "Replacement files"
    files = ("files",)

    def collect(self, mod, ctx):
        root = os.path.join(mod.folder, "files")
        out = {}
        for dirpath, _, names in os.walk(root):
            for fn in names:
                full = os.path.join(dirpath, fn)
                out[os.path.relpath(full, root).replace("\\", "/")] = full
        return out or None

    def build(self, ctx, items):
        added = []
        owner = {}   # rel -> mod id that supplied it; items run lowest priority first, so later wins
        for mod, files in items:
            for rel, full in sorted(files.items()):
                if not rel.startswith(("Wrc/", "Engine/")):
                    ctx.warn(f"{mod.id}: files/{rel} ignored (paths must start with Wrc/ or Engine/)")
                    continue
                kind = classify(rel)
                if kind == "online":
                    ctx.warn(f"{mod.id}: {rel} feeds the online den-visit features; changes there may be "
                             "visible to or rejected by the server")
                elif kind == "traits":
                    ctx.warn(f"{mod.id}: {rel} changes which traits cats get, and traits have gameplay effects "
                             "(not appearance-only)")
                elif kind == "gameplay":
                    ctx.warn(f"{mod.id}: {rel} isn't on the known appearance-only list; it may change gameplay")
                if rel in owner:
                    ctx.log(f"  {rel}: {mod.id} overrides {owner[rel]}")
                with open(full, "rb") as f:
                    ctx.add_file(rel, f.read(), source=mod.id)
                owner[rel] = mod.id
                added.append(rel)
        if added:
            ctx.note("files", sorted(set(added)))
