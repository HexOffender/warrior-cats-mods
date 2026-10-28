"""The game's conversations, read from its cooked dialogue graphs and its two dialogue tables (read-only).

docs/reverse-engineering.md, "Dialogue graphs", has the format and how each part was confirmed. In short:
  * A conversation is a graph (the GenericGraph plugin's UGenericGraph): UNpcDialogue, UBondDialogue (an
    NpcDialogue with a DialogueTag) or UQuestDialogue, one export of a package under /Game/Quests. Its nodes
    and edges are exports whose outer is the graph. The graph lists RootNodes and AllNodes; each node lists
    ParentNodes, ChildrenNodes and, in Edges, the edge object that leads to each child. An edge's EdgeType is
    0 for "go on" and 1 to 4 for answer button 1 to 4, with the button's text, trait, score and clan bonding.
  * A line is a talking node (QuestDialogueTalkingNode and its subclasses): Paragraph (FText), TalkingSource
    (who says it), TalkingSourceText (the name shown), VOEvent (the voice).
  * Every line in the graphs the game plays is a key of the string table SwtStrings, which the game loads
    from Strings_<language>.csv, or a placeholder; never the English words themselves. (The template
    packages' saved copies of their graph, which nothing plays, do hold some inline key names and English.)
  * Story and quest conversations are templates the game fills in as it plays them ("autofill", read from
    the code): a node's SubTag (story) or AutoFillSuffix (quest) is joined to the conversation's tag, and that
    row of StoryDialogues.csv or QuestDialogues.csv gives the line's StringKey, speaker, voice, and an
    answer's trait, score and clan bonding. A key Strings_EN hasn't got shows the row's DebugText: older
    English in StoryDialogues.csv, the key itself in QuestDialogues.csv.

conversations(game) gives every conversation with its lines in order. Nothing here writes graphs.
"""
import struct

from .formats import csvdata
from .formats.anim import script_index
from .formats.cooked import OBJECT_EXPORT, OBJECT_NULL, DataTable, FormatError, ZenPackage, _Values, object_index

STRINGS = "Wrc/Content/Gameplay/Strings/NonAsset/Strings_EN.csv"
TABLES = "Wrc/Content/Gameplay/DataTables/NonAsset/"
QUESTS = "Wrc/Content/Quests/"
SEQUENCES = "Wrc/Content/Gameplay/DataTables/Sequencer/DT_QuestSequenceDialogues.uasset"

PARAGRAPH = [("Paragraph", "text"), ("ParagraphSingular", "text"), ("TalkingSource", "u8"),
             ("TalkingSourceText", "text"), ("VOEvent", "str")]     # FParagraphValues
BUTTON = [("Text", "text")]                                          # FQuestCustomButton
NODE = "GenericGraphNode"

# The dialogue classes: (base class, module, own properties in declaration order), from the class dump
# (vanilla/sdk/UHTHeaderDump). An export numbers its properties from its own class's first, then each base
# class's (found by decoding: docs/reverse-engineering.md). A field of a type wcmods can't read ("floatrange")
# makes reading refuse the export if a game update ever sets it.
CLASSES = {
    "GenericGraph": (None, "GenericGraphRuntime", [
        ("Name", "str"), ("DataTable", "obj"), ("NodeType", ("array", "obj")), ("EdgeType", "obj"),
        ("GraphTags", "tags"), ("RootNodes", ("array", "obj")), ("AllNodes", ("array", "obj")),
        ("bEdgeEnabled", "bool")]),
    "GenericGraphNode": (None, "GenericGraphRuntime", [
        ("Graph", "obj"), ("EdgeTypeOverride", "obj"), ("ParentNodes", ("array", "obj")),
        ("ChildrenNodes", ("array", "obj")), ("Edges", ("map", "obj", "obj"))]),
    "GenericGraphEdge": (None, "GenericGraphRuntime", [("Graph", "obj"), ("StartNode", "obj"), ("EndNode", "obj")]),
    "NpcDialogue": ("GenericGraph", "SwtQuest", [
        ("PlayerBgColor", "color"), ("NPCBgColor", "color"), ("DialoguePartyTags", "tags")]),
    "BondDialogue": ("NpcDialogue", "SwtQuest", [
        ("DialogueTag", "tag"), ("bShuffleOptions", "bool"), ("WidgetId", "u8")]),
    "QuestDialogue": ("GenericGraph", "SwtQuest", [
        ("QuestName", "text"), ("QuestNameAlt1", "text"), ("QuestNameAlt2", "text"), ("QuestSecondaryTitle", "text"),
        ("QuestLongDescription", "text"), ("DialoguePartyTags", "tags"), ("AutoFillPrefix", "str")]),
    "NpcDialogueRoot": (NODE, "SwtQuest", [
        ("WidgetId", "u8"), ("RawTitle", "text"), ("questTag", "tag"), ("QuestTags", "tags"),
        ("bOnlyForQuestObjective", "bool")]),
    "QuestDialogueRoot": (NODE, "SwtQuest", [("RootType", "u8"), ("WidgetId", "u8")]),
    "GossipDialogueRoot": (NODE, "SwtQuest", [("Title", "text")]),
    "QuestDialogueBranch": (NODE, "SwtQuest", [("ResultType", "u8")]),
    "QuestDialogueNode": (NODE, "SwtQuest", [
        ("bKeepShowingHud", "bool"), ("bSkipConfirmation", "bool"), ("TimeToWaitToNextNode", "f32"),
        ("AutoFillSuffix", "str"), ("bAllowAutoFill", "bool")]),
    "QuestDialogueTalkingNode": ("QuestDialogueNode", "SwtQuest", [
        ("Paragraph", "text"), ("ParagraphSingular", "text"), ("TalkingSource", "u8"), ("TalkingSourceText", "text"),
        ("CustomBgColor", "color"), ("PlayerBgColor", "color"), ("NPCBgColor", "color"), ("bSkipTalkMontage", "bool"),
        ("VOEvent", "str"), ("bVOEventFromParagraph", "bool"), ("bTalkingSourceWithColon", "bool"),
        ("DialogueContext", "u8"), ("ForcedTime", "f32")]),
    "QuestDialogueBondNode": ("QuestDialogueTalkingNode", "SwtQuest", [
        ("SubTag", "str"), ("DeathBoth", ("struct", PARAGRAPH)), ("Traitor", ("struct", PARAGRAPH)),
        ("GiverRole", ("struct", PARAGRAPH)), ("BondingRankParagraphs", ("map", "name", ("struct", PARAGRAPH))),
        ("BondingTypesParagraphs", ("map", "name", ("struct", PARAGRAPH)))]),
    "QuestDialogueBondingTypeNode": ("QuestDialogueTalkingNode", "SwtQuest", [
        ("SubTag", "str"), ("BondingTypesTexts", ("map", "name", "text")), ("BondingSource", "u8")]),
    "QuestDialogueMultiTextTalkingNode": ("QuestDialogueTalkingNode", "SwtQuest", [
        ("MultiParagraph", ("array", "text"))]),
    "QuestDialogueEdge": ("GenericGraphEdge", "SwtQuest", [
        ("EdgeType", "u8"), ("Button", ("struct", BUTTON)), ("TraitType", "u8"), ("Score", "i32"),
        ("ClanBonding", "i32"), ("bAllowAutoFill", "bool"), ("AutoFillSuffix", "str")]),
    "QuestDialogueActionBase": ("QuestDialogueNode", "SwtQuest", [("bStopVoiceover", "bool")]),
    "QuestDialogueActionActivateDialogueView": ("QuestDialogueActionBase", "SwtQuest", [
        ("CharacterCameraTag", "tag"), ("ObjectCameraTag", "tag"), ("bBlend", "bool"),
        ("RelativeOffsetDistance", "floatrange"), ("StartValue", "f32"), ("EndValue", "f32")]),
    "QuestDialogueActionAllowMovement": ("QuestDialogueActionBase", "SwtQuest", []),
    "QuestDialogueActionAnimOnActor": ("QuestDialogueActionBase", "SwtQuest", [
        ("actorTag", "name"), ("bRotateToPlayer", "bool"), ("bEndMontageOnClosingDialog", "bool"),
        ("AnimationMontageToPlay", "soft"), ("LoadedMontageAsset", "obj")]),
    "QuestDialogueActionApplyEffect": ("QuestDialogueActionBase", "SwtQuest", [("EffectToApply", "tag")]),
    "QuestDialogueActionBroadcastStoryboard": ("QuestDialogueActionBase", "SwtQuest", [("TagToBroadcast", "name")]),
    "QuestDialogueActionCharacterAnims": ("QuestDialogueActionBase", "SwtQuest", [
        ("CharacterId", "tag"), ("montageTag", "tag")]),
    "QuestDialogueActionCreateScreen": ("QuestDialogueActionBase", "SwtQuest", [
        ("WidgetId", "u8"), ("bPauseSequence", "bool")]),
    "QuestDialogueActionFastTravel": ("QuestDialogueActionBase", "SwtQuest", []),
    "QuestDialogueActionHideWidget": ("QuestDialogueActionBase", "SwtQuest", [
        ("TimeHidden", "f32"), ("bShowWidgetAtEnd", "bool"), ("CallerWidget", "obj")]),
    "QuestDialogueActionNpcValidation": ("QuestDialogueActionBase", "SwtQuest", [
        ("bIconic", "bool"), ("bCheckFirstInteraction", "bool"), ("InteractionTag", "tag")]),
    "QuestDialogueActionPlaySequence": ("QuestDialogueActionBase", "SwtQuest", [
        ("bHideDialogueWidget", "bool"), ("SequenceType", "i32"), ("sequenceId", "tag"), ("bForceTime", "bool"),
        ("ForcedTime", "f32"), ("PlayRate", "f32"), ("bPauseAtEnd", "bool"), ("bReplacePlayerInSequence", "bool"),
        ("bReplaceNpcInSequence", "bool"), ("PlayMontageForNpcInSequence", "tag"),
        ("bAddNpcNameAsMontageLeafTag", "bool")]),
    "QuestDialogueActionResolveDialogue": ("QuestDialogueActionBase", "SwtQuest", []),
    "QuestDialogueActionResolveAcceptQuest": ("QuestDialogueActionResolveDialogue", "SwtQuest", []),
    "QuestDialogueActionResolveConfirm": ("QuestDialogueActionResolveDialogue", "SwtQuest", []),
    "QuestDialogueActionResolveDecision": ("QuestDialogueActionResolveDialogue", "SwtQuest", []),
    "QuestDialogueActionResolveDeclineQuest": ("QuestDialogueActionResolveDialogue", "SwtQuest", []),
    "QuestDialogueActionResolveBondAnswer": ("QuestDialogueActionResolveDecision", "SwtQuest", [
        ("FallbackDialogueTag", "tag"), ("SubTag", "str")]),
    "QuestDialogueActionRestoreExplorationCamera": ("QuestDialogueActionBase", "SwtQuest", []),
    "QuestDialogueActionSave": ("QuestDialogueActionBase", "SwtQuest", []),
    "QuestDialogueActionSaveDialogueInteraction": ("QuestDialogueActionBase", "SwtQuest", [("TagToUse", "tag")]),
    "QuestDialogueActionSaveStoryInteraction": ("QuestDialogueActionBase", "SwtQuest", []),
    "QuestDialogueActionShowWidget": ("QuestDialogueActionBase", "SwtQuest", [
        ("WidgetClass", "soft"), ("bForceShowHud", "bool"), ("CreatedWidget", "obj")]),
    "QuestDialogueActionStayInPlace": ("QuestDialogueActionBase", "SwtQuest", []),
    "QuestDialogueActionStoryDialogue": ("QuestDialogueActionBase", "SwtQuest", [("StoryDialogueTag", "tag")]),
    "QuestDialogueActionWait": ("QuestDialogueActionBase", "SwtQuest", [("TimeToWait", "f32")]),
    "AdventureDialogueActionAnyPlayerPartyCombatValidation": ("QuestDialogueActionBase", "SwtAdventure", []),
    "AdventureDialogueActionClanRole": ("QuestDialogueActionBase", "SwtAdventure", [
        ("narrativeRole", "u8"), ("NewClan", "u8"), ("NewRole", "u8"), ("bExile", "bool")]),
    "AdventureDialogueActionEnterDefenderCombatValidation": (
        "AdventureDialogueActionAnyPlayerPartyCombatValidation", "SwtAdventure", []),
    "AdventureDialogueActionEnterSkirmishCombatValidation": (
        "AdventureDialogueActionAnyPlayerPartyCombatValidation", "SwtAdventure", []),
    "AdventureDialogueActionFreshKillPile": ("QuestDialogueActionBase", "SwtAdventure", []),
    "AdventureDialogueActionOnlineValidation": ("QuestDialogueActionBase", "SwtAdventure", []),
    "AdventureDialogueActionPhotoMode": ("QuestDialogueActionBase", "SwtAdventure", [
        ("bSelfie", "bool"), ("bInstantTrigger", "bool")]),
    "AdventureDialogueActionSendGift": ("QuestDialogueActionBase", "SwtAdventure", []),
    "AdventureDialogueActionSetDefenderCombatFormat": ("QuestDialogueActionBase", "SwtAdventure", [
        ("DefenderCombatFormat", "u8")]),
    "AdventureDialogueActionStartCombat": ("QuestDialogueActionBase", "SwtAdventure", [
        ("CombatType", "u8"), ("CombatTag", "tag")]),
    "AdventureDialogueActionStartDefenderCombat": ("AdventureDialogueActionStartCombat", "SwtAdventure", []),
    "AdventureDialogueActionStartDefenderCombatValidation": (
        "AdventureDialogueActionAnyPlayerPartyCombatValidation", "SwtAdventure", []),
    "AdventureDialogueActionStartSkirmishCombatValidation": (
        "AdventureDialogueActionAnyPlayerPartyCombatValidation", "SwtAdventure", []),
    "AdventureDialogueActionStartTrainingGroundsCombat": ("AdventureDialogueActionStartCombat", "SwtAdventure", []),
}
GRAPHS = ("NpcDialogue", "BondDialogue", "QuestDialogue")
TALKING = ("QuestDialogueTalkingNode", "QuestDialogueBondNode", "QuestDialogueBondingTypeNode",
           "QuestDialogueMultiTextTalkingNode")
SPEAKERS = ("npc", "player", "current", "custom")                                    # ETalkingSource
TALKERS = {"NPC": "npc", "Player": "player"}                                          # the tables' Talker
TRAITS = ("None", "Brave", "Ambitious", "Wise", "Energetic", "Curious", "Patient")   # ECharacterTrait

# The templates the quest manager fills: its StoryDialogueTemplates and QuestDialogueTemplates maps, read from
# BP_WrcQuestManager's class defaults (EQuestStoryDialogueTypes / EQuestFlowDialogueTypes -> graph).
STORY_TEMPLATES = {
    "Short": "StoryDialogues/StoryDialogue_Short_Template",
    "Long": "StoryDialogues/StoryDialogue_Long_Template",
    "Monologue_Filler": "StoryDialogues/StoryDialogue_Monologue_Filler_Template",
    "Monologue_Encounter": "StoryDialogues/StoryDialogue_Monologue_Encounter_Template",
    "Monologue_Interaction_1": "StoryDialogues/StoryDialogue_Monologue_Interaction_1_Template",
    "Monologue_Interaction_2": "StoryDialogues/StoryDialogue_Monologue_Interaction_2_Template",
    "Monologue_Interaction_3": "StoryDialogues/StoryDialogue_Monologue_Interaction_3_Template",
    "End": "StoryDialogues/StoryDialogue_End_Template",
    "Activity_Transition": "StoryDialogues/StoryDialogue_Monologue_ActivityTransition_Template",
}
QUEST_TEMPLATES = {
    "MainQuest": "QuestDialogues/QuestDialogue_MainQuest_Template",
    "SideQuest": "QuestDialogues/QuestDialogue_SideQuest_Template",
    "UniqueQuest": "QuestDialogues/QuestDialogue_UniqueQuest_Template",
}
# How the game picks a story tag's template, read from the code (build 26184573, 0x14168F4F0): the first parent
# tag the conversation's tag is under, and the type for the first talk, the second, and so on (the last one
# repeats; Monologue.Interaction has nothing after its third). Filler2 and Filler3 have no template.
STORY_TYPES = [
    ("Gameplay.Dialogue.Story.Long", ["Long", "End"]),
    ("Gameplay.Dialogue.Story.Short", ["Short", "End"]),
    ("Gameplay.Dialogue.Story.Monologue.Interaction",
     ["Monologue_Interaction_1", "Monologue_Interaction_2", "Monologue_Interaction_3"]),
    ("Gameplay.Dialogue.Story.Monologue.Filler", ["Monologue_Filler"]),
    ("Gameplay.Dialogue.Story.Monologue.Encounter", ["Monologue_Encounter"]),
    ("Gameplay.Dialogue.Activity.Transition", ["Activity_Transition"]),
]
QUEST_TITLES = ("Title", "Title2", "Title_Alternative_1", "Title_Alternative_2")
# The keys the game puts on a quest answer button its row left empty (0x141663B70): Decline for button 4, else
# Accept; an answer with a trait gets "<the graph's AutoFillPrefix>.<Context|Return>.Answer.<Trait>.Short".
DECLINE, ACCEPT = "STR_QUEST_DIALOGUE_DECLINE", "STR_QUEST_DIALOGUE_ACCEPT"
# DT_QuestSequenceDialogues' rows (FSwtQuestSequenceDialoguesStruct): the tag PlaySequenceDialogue is given, the
# dialogue box (EWidgetsIds) and the graph.
SEQUENCE_ROW = [("SequenceDialogueId", "tag"), ("WidgetToUse", "u8"), ("DialogueToUse", "obj")]


def properties(cls):
    """A class's properties in the order its exports number them: its own, then its base class's, and so on."""
    out = []
    while cls is not None:
        base, _, own = CLASSES[cls]
        out += own
        cls = base
    return out


SCHEMA = {cls: properties(cls) for cls in CLASSES}
CLASS_OF = {script_index(f"/Script/{module}.{cls}"): cls for cls, (_, module, _) in CLASSES.items()}


class Object:
    """One export: a graph, a node or an edge. index is its export index; props its properties as decoded
    (object references are FPackageIndex values: export i is i + 1)."""
    __slots__ = ("index", "name", "cls", "props", "outer", "public")

    def __init__(self, index, name, cls, props, outer, public):
        self.index, self.name, self.cls, self.props, self.outer, self.public = index, name, cls, props, outer, public

    def __repr__(self):
        return f"<{self.cls} {self.name} #{self.index}>"


class Graph:
    """A conversation's graph: the graph object, and its nodes and edges by export index."""

    def __init__(self, package, graph, objects):
        self.package, self.graph, self.objects = package, graph, objects
        self.name, self.cls, self.props = graph.name, graph.cls, graph.props

    def __repr__(self):
        return f"<{self.cls} {self.package}.{self.name}: {len(self.objects)} objects>"

    def get(self, ref):
        """The node or edge an object reference points at (None for none or another package's object)."""
        return self.objects.get(ref - 1) if ref and ref > 0 else None

    def roots(self):
        return [n for n in map(self.get, self.props.get("RootNodes", [])) if n]

    def children(self, node):
        """[(child, the edge to it or None)], in ChildrenNodes order."""
        edges = dict(node.props.get("Edges", []))
        return [(self.get(c), self.get(edges.get(c))) for c in node.props.get("ChildrenNodes", []) if self.get(c)]

    def walk(self):
        """Every node reachable from the roots, once, in reading order (depth first, children in order)."""
        seen, out = set(), []
        stack = list(reversed(self.roots()))
        while stack:
            n = stack.pop()
            if n.index in seen:
                continue
            seen.add(n.index)
            out.append(n)
            stack += [c for c, _ in reversed(self.children(n)) if c.index not in seen]
        return out


def read_graphs(data, package="", only=None):
    """The graphs in a package's bytes. only: just the graph of that name (a template package also holds many
    copies of its graph that nothing uses). Raises FormatError for a class or field wcmods doesn't know."""
    pkg = ZenPackage(data)
    values = _Values(pkg)
    entries = [pkg.export_entry(i) for i in range(pkg.export_count)]

    def outer(e):
        kind, i = object_index(e.outer)
        return i if kind == OBJECT_EXPORT else None if kind == OBJECT_NULL else -1

    wanted = None
    if only is not None:
        top = [i for i, e in enumerate(entries) if e.name == only and outer(e) is None]
        if not top:
            raise FormatError(f"{package}: no graph {only}")
        wanted = {top[0]} | {i for i, e in enumerate(entries) if outer(e) == top[0]}
    objects = {}
    for i, e in enumerate(entries):
        if wanted is not None and i not in wanted:
            continue
        cls = CLASS_OF.get(e.cls)
        if cls is None:
            raise FormatError(f"{package}: {e.name} is of a class wcmods doesn't know ({e.cls:#x})")
        try:
            props = values.read_object(pkg.export_data[e.offset:e.offset + e.size], SCHEMA[cls])
        except (ValueError, IndexError, struct.error) as ex:     # FormatError and a bad string are ValueErrors
            raise FormatError(f"{package}: {e.name} ({cls}): {ex}") from None
        objects[i] = Object(i, e.name, cls, props, outer(e), e.public)
    return [Graph(package, g, {i: o for i, o in objects.items() if o.outer == g.index})
            for g in objects.values() if g.cls in GRAPHS and g.outer is None]


# ------------------------------------------------------------------------------------------------ text
def text_key(text):
    """The string table key an FText shows, or None (inline text, a placeholder, or none)."""
    return text.get("key") if isinstance(text, dict) and "table" in text else None


def _text(text, strings):
    """(key, English) of a graph's FText: a table key and its words, or (None, the inline words)."""
    if not isinstance(text, dict):
        return None, None
    if "table" in text:
        return text["key"], strings.get(text["key"])
    return None, text.get("text") or text.get("invariant")


def _autofill(obj):
    """Whether the game fills this node or edge in (bAllowAutoFill, true unless a graph turns it off)."""
    return obj.props.get("bAllowAutoFill", True) is not False


def _table(read_text, path):
    """A dialogue table's rows: {row name: {column: value}}."""
    t = csvdata.Table(read_text(path))
    return {r.fields[0]: dict(zip(t.header[1:], r.fields[1:])) for r in t.rows if r.fields and r.fields[0]}


def _strings(read_text):
    t = csvdata.Table(read_text(STRINGS))
    return {r.fields[0]: r.fields[1] for r in t.rows if len(r.fields) > 1}


# ------------------------------------------------------------------------------------------------ lines
class _Builder:
    """Turns a graph into lines. When a table fills the graph in, resolve(node) gives a talking node's row name
    and its variants' row names, and resolve(edge, child) an answer's row name (None: the graph's own text).
    default(edge, child, trait) gives the key the game puts on an answer whose row shows nothing (quest talks)."""

    def __init__(self, graph, strings, rows=None, resolve=None, default=None):
        self.graph, self.strings, self.rows, self.resolve, self.default = graph, strings, rows or {}, resolve, default

    def row_line(self, name):
        """(key, English, row, the row's columns, fallback) for a dialogue table row, as the game's code shows it
        (0x14162DC10): the Strings_EN words of the row's StringKey (fallback None). When the key is empty, or
        Strings_EN hasn't got it or has it empty, the game shows the row's DebugText instead: fallback "debug",
        with that text. In QuestDialogues.csv DebugText is the key itself (every row), so there the game shows
        the raw key: fallback "key" and English None, not the key passed off as words."""
        row = self.rows.get(name)
        if row is None:
            return None, None, None, None, None
        key = row.get("StringKey") or None
        text = self.strings.get(key) if key else None
        if text:
            return key, text, name, row, None
        debug = row.get("DebugText") or None
        if debug is not None and debug == key:
            return key, None, name, row, "key"
        return key, debug, name, row, "debug"

    def row_fields(self, name):
        """{"key", "text", "row", "fallback"} of row_line."""
        key, text, row, _, fallback = self.row_line(name)
        return {"key": key, "text": text, "row": row, "fallback": fallback}

    def variants(self, obj):
        p = obj.props
        out = []
        for label in ("DeathBoth", "Traitor", "GiverRole"):
            if isinstance(p.get(label), dict) and p[label].get("Paragraph"):
                out.append((label, p[label]["Paragraph"]))
        for field in ("BondingRankParagraphs", "BondingTypesParagraphs"):
            out += [(when.split("::")[-1], v.get("Paragraph")) for when, v in p.get(field, []) if isinstance(v, dict)]
        out += [(when.split("::")[-1], v) for when, v in p.get("BondingTypesTexts", [])]
        out += [("one of", v) for v in p.get("MultiParagraph", [])]
        result = []
        for when, t in out:
            key, text = _text(t, self.strings)
            if key or text:
                result.append({"when": when, "key": key, "text": text, "row": None, "fallback": None})
        return result

    def line(self, node):
        p = node.props
        source = p.get("TalkingSource", 0)
        line = {"node": node.index, "speaker": SPEAKERS[source] if source < len(SPEAKERS) else None,
                "speaker_key": text_key(p.get("TalkingSourceText")), "key": None, "text": None, "row": None,
                "fallback": None, "variants": [], "answers": [], "next": []}
        filled = self.resolve(node) if self.resolve else None
        if filled:
            name, variants = filled
            key, text, row, cols, fallback = self.row_line(name)
            line.update(key=key, text=text, row=row, fallback=fallback)
            line["variants"] = [dict(self.row_fields(v), when=v[len(name) + 1:]) for v in variants]
            source_row = cols or (self.rows.get(variants[0]) if variants else None) or {}
            line["speaker"] = TALKERS.get(source_row.get("Talker"), line["speaker"])
        else:
            line["key"], line["text"] = _text(p.get("Paragraph"), self.strings)
            line["variants"] = self.variants(node)
        return line

    def answer(self, edge, child):
        p = edge.props
        a = {"slot": p.get("EdgeType", 0), "key": None, "text": None, "row": None, "fallback": None,
             "trait": TRAITS[p.get("TraitType", 0)] if p.get("TraitType", 0) < len(TRAITS) else None,
             "score": p.get("Score", 0), "clan_bonding": p.get("ClanBonding", 0), "next": []}
        filled = self.resolve(edge, child) if self.resolve else None
        if filled:
            key, text, row, cols, fallback = self.row_line(filled)
            a.update(key=key, text=text, row=row, fallback=fallback)
            if cols:
                trait = cols.get("Trait")
                a["trait"] = trait if trait in TRAITS else a["trait"]
                a["score"], a["clan_bonding"] = _int(cols.get("Score")), _int(cols.get("ClanBonding"))
            if self.default and not text and fallback != "key":    # no row, or a row that shows nothing
                k = self.default(edge, child, TRAITS.index(a["trait"]) if a["trait"] in TRAITS else 0)
                a.update(key=k if k in self.strings else None, text=self.strings.get(k), fallback="default")
        else:
            a["key"], a["text"] = _text((p.get("Button") or {}).get("Text"), self.strings)
        return a

    def reach(self, starts):
        """The talking nodes the conversation comes to first from starts (themselves, if they talk), through
        any actions and whichever way they branch."""
        out, seen, queue = [], set(), list(starts)
        while queue:
            n = queue.pop(0)
            if n.index in seen:
                continue
            seen.add(n.index)
            if n.cls in TALKING:
                out.append(n.index)
            else:
                queue += [c for c, _ in self.graph.children(n)]
        return out

    def lines(self):
        """The graph's talking nodes in reading order, each with its answers (the edges with a button, 1 to 4)
        and what follows; next and an answer's next are node indexes here."""
        out = []
        for node in self.graph.walk():
            if node.cls not in TALKING:
                continue
            line = self.line(node)
            simple = []
            for child, edge in self.graph.children(node):
                if edge is not None and edge.props.get("EdgeType", 0):
                    a = self.answer(edge, child)
                    a["next"] = self.reach([child])
                    line["answers"].append(a)
                else:
                    simple.append(child)
            line["next"] = self.reach(simple)
            out.append(line)
        return out


def _numbered(groups):
    """One conversation's lines from [(talk, a graph's lines)]: each gets "id", its place in the list, and
    "talk"; next and the answers' next become ids."""
    out, ids = [], {}
    for talk, lines in groups:
        for line in lines:
            ids[(talk, line["node"])] = len(out)
            out.append(dict(line, talk=talk))
    for line in out:
        line["id"] = ids[(line["talk"], line["node"])]
        line["next"] = [ids[(line["talk"], n)] for n in line["next"] if (line["talk"], n) in ids]
        for a in line["answers"]:
            a["next"] = [ids[(line["talk"], n)] for n in a["next"] if (line["talk"], n) in ids]
    return out


def _int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return 0


# ------------------------------------------------------------------------------------------ conversations
def story_types(tag):
    """The template types a story tag plays on successive talks, as the game picks them, or []."""
    for parent, types in STORY_TYPES:
        if tag == parent or tag.startswith(parent + "."):
            return types
    return []


def _stems(rows, suffixes):
    """{stem: [row names]}: each row under the stem it ends in stem + "." + suffix (+ "." + variant), the shortest
    stem when more than one fits."""
    out = {}
    for name in rows:
        best = None
        for s in suffixes:
            at = name.find("." + s)
            while at >= 0:
                end = at + 1 + len(s)
                if end == len(name) or name[end] == ".":
                    if best is None or at < best:
                        best = at
                    break
                at = name.find("." + s, at + 1)
        if best is not None:
            out.setdefault(name[:best], []).append(name)
    return out


def _under(rows):
    """{name: [the rows named name + "." + something]}, for every name a row's name starts with."""
    out = {}
    for row in rows:
        at = row.find(".")
        while at >= 0:
            out.setdefault(row[:at], []).append(row)
            at = row.find(".", at + 1)
    return out


def _story_resolver(tag, under):
    """resolve() for a story template played for tag: a node's SubTag names its row; the variants are the rows
    under it (".Positive", ".Warrior", ...); an answer's row is the SubTag of the node it leads to."""
    def resolve(obj, child=None):
        if child is not None:      # an edge: the answer's words are the row of the node it leads to
            sub = child.props.get("SubTag")
            return f"{tag}.{sub}" if sub else None
        sub = obj.props.get("SubTag")
        if not sub:
            return None
        name = f"{tag}.{sub}"
        return name, sorted(under.get(name, []))
    return resolve


def _quest_resolver(stem):
    """resolve() for a quest template played for a quest stem, as the game's fill does (0x1416648D0 a node,
    0x141663B70 an edge): with bAllowAutoFill on, the graph's own text is cleared and the row is
    "<stem>.<AutoFillSuffix>", joined even when the suffix is empty (no row is named "<stem>.", so such a node
    shows nothing and such an answer gets _quest_default's key); bAllowAutoFill off keeps the graph's own text."""
    def resolve(obj, child=None):
        if not _autofill(obj):
            return None
        name = f"{stem}.{obj.props.get('AutoFillSuffix') or ''}"
        return name if child is not None else (name, [])
    return resolve


def _quest_default(graph):
    """default() for a quest template: the key the game's edge fill (0x141663B70) puts on an answer button its
    row left empty. With no trait, STR_QUEST_DIALOGUE_DECLINE for button 4 and STR_QUEST_DIALOGUE_ACCEPT for the
    others. With one, "<AutoFillPrefix>.Context.Answer.<Trait>.Short" when the answer leads to a
    ResolveAcceptQuest node, else "<AutoFillPrefix>.Return.Answer.<Trait>.Short", shown only if Strings_EN has it.
    AutoFillPrefix is the graph's own (a key prefix such as QST_SideQuest.WinFights); the three templates leave it
    empty as cooked, and whether the game sets it before filling wasn't traced."""
    def default(edge, child, trait):
        if trait:
            part = "Context" if child is not None and child.cls == "QuestDialogueActionResolveAcceptQuest" else "Return"
            return f"{graph.props.get('AutoFillPrefix') or ''}.{part}.Answer.{TRAITS[trait]}.Short"
        return DECLINE if edge.props.get("EdgeType") == 4 else ACCEPT
    return default


def _suffixes(graph, field):
    out = set()
    for n in graph.objects.values():
        if n.props.get(field):
            out.add(n.props[field])
    return out


def sequence_tags(game):
    """{graph package path: [the tags that play it]} from DT_QuestSequenceDialogues (the cinematic talks)."""
    out = {}
    table = DataTable(game.read(SEQUENCES), SEQUENCE_ROW)
    for _, row in table.rows:
        target = table.pkg.resolve(row.get("DialogueToUse", 0))
        if target and target[0] == "package":
            out.setdefault(target[1], []).append(row.get("SequenceDialogueId", ""))
    return out


def conversations(game, strings=None):
    """Every conversation the game's files hold, as dicts:
      id        "npc:NpcDialogue_TheAgingLeader", "cinematic:…", "story:<its tag>" or "quest:<its stem>"
      kind      "npc" (a cat's own talk graph), "cinematic" (played by tag), "story" or "quest" (a template the
                game fills from StoryDialogues.csv or QuestDialogues.csv)
      package   the graph's package ("/Game/Quests/…"); graph: the graph's export name
      tag       the story tag or quest stem the template is filled for; for a cinematic, the tags that play it
      title     a quest's title: {"key", "text", "row", "fallback"}, or None
      plays     (npc) [{"when": quest tags, "story": story tag}]: the story talks its roots start
      used_by   (story) the npc conversations that play it ([]: none of the cats' graphs names the tag; a level's
                quest component or the code may still play it)
      lines     in reading order; each {"id", "node", "talk", "speaker", "speaker_key", "key", "text", "row",
                "fallback", "variants", "answers", "next"}: id its place in lines; node its export index in the
                graph's package; talk 1 the first time you talk, 2 the next, ...; speaker "npc", "player",
                "current" or "custom"; speaker_key the graph's name text (TalkingSourceText); key the Strings_EN
                key the game shows (None for inline words or a missing row); text its English, or None when
                there's none; row the table row it's filled from; fallback what the game shows instead of the
                key's Strings_EN words, by the code (0x14162DC10, 0x141663B70):
                  None       the key's words (or the graph's own inline words), as text says
                  "debug"    the key isn't in Strings_EN (or is empty there), so the row's DebugText: text is it
                             (StoryDialogues.csv's DebugText is older English, often unlike Strings_EN's)
                  "key"      the same, but the row's DebugText is the key itself (every QuestDialogues.csv row),
                             so the game shows the raw key string: text is None, not the key passed off as words
                  "default"  (a quest answer) its row is missing or shows nothing, so the game's own key:
                             STR_QUEST_DIALOGUE_ACCEPT / _DECLINE or a trait's answer key (_quest_default)
                variants [{"when", "key", "text", "row", "fallback"}]: the line instead, by bond, rank or at
                random; answers [{"slot" 1-4, "key", "text", "row", "fallback", "trait", "score",
                "clan_bonding", "next"}]; next the ids of the lines that follow by a plain edge (an answer's
                next, those after the button).
    game is a GameFiles (exists/find/read/read_text); strings {key: English} (default: the game's Strings_EN)."""
    strings = _strings(game.read_text) if strings is None else strings
    story_rows = _table(game.read_text, TABLES + "StoryDialogues.csv")
    quest_rows = _table(game.read_text, TABLES + "QuestDialogues.csv")
    cinematic_tags = sequence_tags(game) if game.exists(SEQUENCES) else {}
    out = []

    def path_of(asset):
        return "/Game/" + asset[len("Wrc/Content/"):-len(".uasset")]

    templates = {}
    for kind, table in (("story", STORY_TEMPLATES), ("quest", QUEST_TEMPLATES)):
        for typ, rel in table.items():
            asset = QUESTS + rel + ".uasset"
            if game.exists(asset):
                templates[(kind, typ)] = read_graphs(game.read(asset), path_of(asset), rel.rsplit("/", 1)[-1])[0]

    story_tags = set()
    for asset in game.find(QUESTS + "NpcDialogues/*.uasset"):
        kind = "cinematic" if "/Cinematic/" in asset else "npc"
        for g in read_graphs(game.read(asset), path_of(asset)):
            conv = _conversation(f"{kind}:{g.name}", kind, g, _numbered([(1, _Builder(g, strings).lines())]))
            if kind == "cinematic":
                conv["tag"] = cinematic_tags.get(g.package, [])
            else:
                conv["plays"] = _plays(g)
                story_tags.update(p["story"] for p in conv["plays"])
            out.append(conv)

    # story talks: every tag the cats' graphs play, and every other tag the table has rows for
    subtags = set()
    for (kind, _), g in templates.items():
        if kind == "story":
            subtags |= _suffixes(g, "SubTag")
    for tag in _stems(story_rows, subtags):
        if story_types(tag):
            story_tags.add(tag)
    under = _under(story_rows)
    for tag in sorted(story_tags):
        groups = []
        for talk, typ in enumerate(story_types(tag), 1):
            g = templates.get(("story", typ))
            lines = _Builder(g, strings, story_rows, _story_resolver(tag, under)).lines() if g else []
            if any(line["row"] or line["variants"] for line in lines):   # a template the table has no rows for
                groups.append((talk, lines))                              # isn't played for this tag
        if groups:
            first = templates.get(("story", story_types(tag)[0]))
            conv = _conversation(f"story:{tag}", "story", first, _numbered(groups), tag=tag)
            conv["used_by"] = [c["id"] for c in out
                               if c["kind"] == "npc" and any(p["story"] == tag for p in c["plays"])]
            out.append(conv)

    # quest talks: one per quest stem of QuestDialogues.csv, on the template whose suffixes its rows have
    quest_templates = {typ: g for (kind, typ), g in templates.items() if kind == "quest"}
    suffixes = {typ: _suffixes(g, "AutoFillSuffix") for typ, g in quest_templates.items()}
    for stem, names in sorted(_stems(quest_rows, set().union(*suffixes.values(), QUEST_TITLES)).items()):
        have = {n[len(stem) + 1:] for n in names}
        typ = _best_template(have, suffixes)
        if typ is None:
            continue
        g = quest_templates[typ]
        lines = _Builder(g, strings, quest_rows, _quest_resolver(stem), _quest_default(g)).lines()
        conv = _conversation(f"quest:{stem}", "quest", g, _numbered([(1, lines)]), tag=stem)
        title = _Builder(g, strings, quest_rows).row_fields(f"{stem}.Title")
        conv["title"] = title if title["row"] else None
        out.append(conv)
    return out


def _best_template(have, suffixes):
    """The quest template whose fill-in suffixes are all among a stem's rows, the one with the most if several
    are (the game picks by the quest's own type, which wcmods doesn't read; the rows fit only one)."""
    fits = [(len(s), typ) for typ, s in suffixes.items() if s and s <= have]
    return max(fits)[1] if fits else None


def _plays(graph):
    """The story talks an NPC graph starts, with the quest state tags of the root they hang from."""
    out = []
    for root in graph.roots():
        when = root.props.get("QuestTags", [])
        seen, stack = set(), [root]
        while stack:
            n = stack.pop()
            if n.index in seen:
                continue
            seen.add(n.index)
            if n.props.get("StoryDialogueTag"):
                out.append({"when": when, "story": n.props["StoryDialogueTag"]})
            stack += [c for c, _ in graph.children(n)]
    return out


def _conversation(cid, kind, graph, lines, tag=None):
    return {"id": cid, "kind": kind, "package": graph.package, "graph": graph.name, "tag": tag, "title": None, "plays": [], "used_by": [], "lines": lines}


def lines_by_key(convs):
    """{Strings_EN key: [(conversation id, line id, speaker)]}: every key a conversation shows, lines, answers
    and variants, and who says it."""
    out = {}
    for c in convs:
        for line in c["lines"]:
            if line["key"]:
                out.setdefault(line["key"], []).append((c["id"], line["id"], line["speaker"]))
            for v in line["variants"]:
                if v["key"]:
                    out.setdefault(v["key"], []).append((c["id"], line["id"], line["speaker"]))
            for a in line["answers"]:
                if a["key"]:
                    out.setdefault(a["key"], []).append((c["id"], line["id"], "player"))
    return out
