"""The dialogue graphs (wcmods/dialogue.py) and the object property types they added to the cooked format
(wcmods/formats/cooked.py), without the game: one small graph captured from it (a cinematic talk: names and
string keys, no words) and synthetic packages built here."""
import fnmatch
import os
import struct

import pytest

from wcmods import dialogue
from wcmods.formats.anim import script_index
from wcmods.formats.cooked import (EXPORT_ENTRY, NAME_HASH_VERSION, SUMMARY, Empty, EmptyList, FormatError,
                                   ZenPackage, _Reader, _Values, split_name, write_header)

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dialogue")
CAPTURED = os.path.join(FIXTURES, "CinematicDialogue_Unique2_RiverClan_TheVengefulRogue.uasset")
NULL = (1 << 64) - 1


def key(k):
    return {"table": "SwtStrings", "key": k, "flags": 0}


# ------------------------------------------------------------------------------------- building packages
def build(package, objects):
    """A zen package holding objects, [(name, class, outer export index or None, props)], each written as the
    game writes an object: its class's properties, then HasGuid 0. Only what ZenPackage reads is filled in."""
    n = len(objects)
    names = [package.rsplit("/", 1)[-1]]
    strings = b"".join(x.encode() for x in names)
    head = struct.pack("<IIQ", len(names), len(strings), NAME_HASH_VERSION) + b"\0" * 8 + struct.pack(
        ">H", len(strings)) + strings
    pad = (-(SUMMARY.size + len(head))) % 8
    head += struct.pack("<q", pad) + b"\0" * pad
    rest = struct.pack("<q", 0)                     # the bulk data map: none
    sections = SUMMARY.size + len(head) + len(rest)  # no imported hashes, no imports, then the export map
    exports_at = sections
    after = exports_at + EXPORT_ENTRY * n
    rest += b"\0" * (EXPORT_ENTRY * n) + struct.pack("<I", 0)   # the export map, then no imported packages
    summary = [0, after + 4, 0, 0, 0, 0, sections, sections, exports_at, after, after, after, after, after, after]
    pkg = ZenPackage(SUMMARY.pack(*summary) + head + rest)
    values = _Values(pkg)
    blobs = []
    entries = bytearray(EXPORT_ENTRY * n)
    for i, (name, cls, outer, props) in enumerate(objects):
        blobs.append(values.write_object(props, dialogue.SCHEMA[cls]))
        base, number = split_name(name)
        struct.pack_into("<QQIIQQQQQI", entries, EXPORT_ENTRY * i, 0, 0, pkg.name_index(base), number,
                         NULL if outer is None else outer, script_index(f"/Script/{dialogue.CLASSES[cls][1]}.{cls}"),
                         NULL, NULL, 0, 8)
    em = pkg._export_map - pkg._after_names
    pkg._rest = pkg._rest[:em] + bytes(entries) + pkg._rest[em + len(entries):]
    return pkg.rebuild(b"".join(blobs), [len(b) for b in blobs])


def graph_objects(cls, nodes, edges, roots, name="Graph"):
    """[(name, class, outer, props)] for a graph (export 0, named name) whose nodes are nodes, [(name, class,
    props)], and edges [(from, to, edge props)] by node position, the edges after the nodes."""
    first_edge = 1 + len(nodes)
    children = {i: [] for i in range(len(nodes))}
    parents = {i: [] for i in range(len(nodes))}
    for k, (a, b, _) in enumerate(edges):
        children[a].append((b, first_edge + k))
        parents[b].append(a)
    out = [(name, cls, None, {"RootNodes": [2 + r for r in roots], "AllNodes": [2 + i for i in range(len(nodes))]})]
    for i, (name, ncls, props) in enumerate(nodes):
        p = dict(props, Graph=1)
        if parents[i]:
            p["ParentNodes"] = [2 + a for a in parents[i]]
        if children[i]:
            p["ChildrenNodes"] = [2 + b for b, _ in children[i]]
            p["Edges"] = [(2 + b, 1 + e) for b, e in children[i]]
        out.append((name, ncls, 0, p))
    for k, (a, b, props) in enumerate(edges):
        out.append((f"QuestDialogueEdge_{k}", "QuestDialogueEdge", 0, dict(props, Graph=1, StartNode=2 + a, EndNode=2 + b)))
    return out


class FakeGame:
    """The bits of GameFiles conversations() uses, over {path: bytes or str}."""

    def __init__(self, files):
        self.files = files

    def exists(self, path):
        return path in self.files

    def find(self, pattern):
        return sorted(p for p in self.files if fnmatch.fnmatch(p.lower(), pattern.lower()))

    def read(self, path):
        v = self.files[path]
        return v.encode() if isinstance(v, str) else v

    def read_text(self, path):
        return self.read(path).decode("utf-8")


HEADER = "---,Score,ClanBonding,Talker,Trait,VoiceOver,StringKey,DebugText\n"


# ------------------------------------------------------------------------------------------------ tests
def test_object_property_types_round_trip():
    pkg = ZenPackage(build("/Game/T/Empty", []))
    v = _Values(pkg)
    schema = [("On", "bool"), ("Off", "bool"), ("Name", "str"), ("Blank", "str"), ("Ref", "obj"),
              ("Colour", "color"), ("Tags", "tags"), ("Refs", ("array", "obj")), ("NoRefs", ("array", "obj")),
              ("Texts", ("map", "name", "text")), ("Button", ("struct", [("Text", "text"), ("Slot", "u8")]))]
    values = {"On": True, "Off": False, "Name": "Context.1", "Blank": Empty(), "Ref": -3,
              "Colour": [0.0, 0.5, 1.0, 1.0], "Tags": ["Quest.Main.1.0", "Quest.Main.1.1"], "Refs": [2, 5],
              "NoRefs": [], "Texts": [("EBondingTypes::Positive", key("K.Positive"))],
              "Button": {"Text": key("STR_OK"), "Slot": 0}}
    blob = v.write_object(values, schema)
    back = v.read_object(blob, schema)
    assert back == values
    assert v.write_object(back, schema) == blob
    # zero-masked values come back as plain "" and [], written-out empty ones as Empty and EmptyList, and
    # each writes back as it was
    assert type(back["Blank"]) is Empty and type(back["NoRefs"]) is list
    assert v.read_object(v.write_object({"NoRefs": EmptyList()}, schema), schema)["NoRefs"] == []
    assert type(v.read_object(v.write_object({"NoRefs": EmptyList()}, schema), schema)["NoRefs"]) is EmptyList
    assert len(v.write_object({"Blank": Empty()}, schema)) > len(v.write_object({"Blank": ""}, schema))
    # an object with a GUID, or with bytes after its properties, is refused
    with pytest.raises(FormatError):
        v.read_object(blob[:-4] + struct.pack("<I", 1), schema)
    with pytest.raises(FormatError):
        v.read_object(blob + b"\0", schema)
    # so is a count that can't fit in what's left
    with pytest.raises(FormatError):
        v.read(_Reader(struct.pack("<i", 1000) + b"\0" * 8), ("array", "obj"))


def test_properties_are_numbered_from_the_class_itself_then_its_bases():
    talking = dialogue.properties("QuestDialogueTalkingNode")
    assert talking[0] == ("Paragraph", "text")
    assert [f for f, _ in talking[-5:]] == ["Graph", "EdgeTypeOverride", "ParentNodes", "ChildrenNodes", "Edges"]
    # the Short story template's first BondNode sets field 0 (SubTag), 6 (Paragraph) and then 24 (Graph)
    bond = [f for f, _ in dialogue.SCHEMA["QuestDialogueBondNode"]]
    assert (bond[0], bond[6], bond[24]) == ("SubTag", "Paragraph", "Graph")
    for cls, fields in dialogue.SCHEMA.items():
        assert len({f for f, _ in fields}) == len(fields), cls


def test_classes_are_known_by_the_hashes_the_game_imports_them_by():
    # the class indexes in the game's own export maps (build 26184573)
    assert dialogue.CLASS_OF[0x423BAE5FDC811ABA] == "QuestDialogueTalkingNode"
    assert dialogue.CLASS_OF[0x4F835143922AE8E3] == "QuestDialogueEdge"
    assert dialogue.CLASS_OF[0x529EEA9A5852B055] == "BondDialogue"
    assert dialogue.CLASS_OF[0x6C993F7C3FF8A204] == "QuestDialogueBondNode"


def test_a_captured_cinematic_graph_decodes_and_its_objects_write_back():
    data = open(CAPTURED, "rb").read()
    [g] = dialogue.read_graphs(data, "/Game/Quests/NpcDialogues/Cinematic/X")
    assert (g.cls, g.name) == ("NpcDialogue", "CinematicDialogue_Unique2_RiverClan_TheVengefulRogue")
    walk = g.walk()
    assert [n.cls for n in walk] == ["QuestDialogueTalkingNode"] * 3
    assert [dialogue.text_key(n.props["Paragraph"]) for n in walk] == [
        f"QST_Story.Monologue.Interaction.TheVengefulRouge.Unique.2.Context.{i}" for i in (1, 2, 3)]
    pkg = ZenPackage(data)
    values = _Values(pkg)
    for i in range(pkg.export_count):
        e = pkg.export_entry(i)
        blob = pkg.export_data[e.offset:e.offset + e.size]
        schema = dialogue.SCHEMA[dialogue.CLASS_OF[e.cls]]
        assert values.write_object(values.read_object(blob, schema), schema) == blob
    lines = dialogue._numbered([(1, dialogue._Builder(g, {"QST_Story.Monologue.Interaction.TheVengefulRouge.Unique.2."
                                                          "Context.1": "Words."}).lines())])
    assert [line["next"] for line in lines] == [[1], [2], []]
    assert lines[0]["text"] == "Words." and lines[1]["text"] is None


def test_answers_their_buttons_and_where_they_lead():
    nodes = [("Hello", "QuestDialogueTalkingNode", {"Paragraph": key("K.Hello")}),
             ("Act", "QuestDialogueActionStayInPlace", {}),
             ("Brave", "QuestDialogueTalkingNode", {"Paragraph": key("K.Brave"), "TalkingSource": 1}),
             ("Wise", "QuestDialogueTalkingNode", {"Paragraph": {"ns": "", "key": "GUID", "text": "<Inline>",
                                                                 "flags": 0}})]
    edges = [(0, 1, {"EdgeType": 1, "Button": {"Text": key("B.Brave")}, "TraitType": 1, "Score": 9,
                     "ClanBonding": 2}),
             (1, 2, {}),
             (0, 3, {"EdgeType": 2, "Button": {"Text": key("B.Wise")}, "TraitType": 3})]
    data = build("/Game/Quests/NpcDialogues/NPCUniques/NpcDialogue_Cat", graph_objects("NpcDialogue", nodes, edges, [0]))
    [g] = dialogue.read_graphs(data, "x")
    lines = dialogue._numbered([(1, dialogue._Builder(g, {"K.Hello": "Hello.", "B.Brave": "I will!"}).lines())])
    assert [line["key"] for line in lines] == ["K.Hello", "K.Brave", None]
    assert lines[2]["text"] == "<Inline>"           # words in the graph itself: Strings_EN can't change them
    assert lines[1]["speaker"] == "player"
    a1, a2 = lines[0]["answers"]
    assert (a1["slot"], a1["key"], a1["text"], a1["trait"], a1["score"], a1["clan_bonding"], a1["next"]) == (
        1, "B.Brave", "I will!", "Brave", 9, 2, [1])      # through the action to the line after it
    assert (a2["slot"], a2["trait"], a2["next"]) == (2, "Wise", [2])
    assert lines[0]["next"] == []                      # answers, not a plain "go on"


def story_template(name, extra=False):
    """A small Short-style story template: Context.1, Question.1 with two answers, each to its long line."""
    nodes = [("Context", "QuestDialogueBondNode", {"SubTag": "Context.1", "Paragraph": {
                 "ns": "", "key": "G1", "text": "None.Context.1", "flags": 0}}),
             ("Question", "QuestDialogueBondNode", {"SubTag": "Question.1"}),
             ("Right", "QuestDialogueActionResolveBondAnswer", {"SubTag": "Right.1.Short"}),
             ("Wrong", "QuestDialogueActionResolveBondAnswer", {"SubTag": "Wrong.1.Short"}),
             ("RightLong", "QuestDialogueBondNode", {"SubTag": "Right.1.Long", "TalkingSource": 1}),
             ("WrongLong", "QuestDialogueBondNode", {"SubTag": "Wrong.1.Long", "TalkingSource": 1})]
    edges = [(0, 1, {}), (1, 2, {"EdgeType": 1, "Button": {"Text": {"ns": "", "key": "G2", "text": "<Answer 1>",
                                                                    "flags": 0}}}),
             (1, 3, {"EdgeType": 2}), (2, 4, {}), (3, 5, {})]
    if extra:
        nodes, edges = [("End", "QuestDialogueBondNode", {"SubTag": "End"})], []
    return build(name, graph_objects("BondDialogue", nodes, edges, [0], name.rsplit("/", 1)[-1]))


def test_a_story_talk_is_its_template_filled_from_the_rows():
    tag = "Gameplay.Dialogue.Story.Short.Cat.Main.1"
    rows = HEADER + "".join(f"{tag}.{sub},{score},{bond},{talker},{trait},vo_dialog_talk,QST_{sub},Debug {sub}\n"
                            for sub, score, bond, talker, trait in [
                                ("Context.1", 0, 0, "NPC", "None"), ("Question.1", 0, 0, "NPC", "None"),
                                ("Right.1.Short", 9, 2, "Player", "Brave"), ("Wrong.1.Short", -3, -4, "Player", "Ambitious"),
                                ("Right.1.Long", 0, 0, "Player", "None"), ("Wrong.1.Long", 0, 0, "Player", "None"),
                                ("End", 0, 0, "NPC", "None")])
    npc = [("Root", "NpcDialogueRoot", {"QuestTags": ["Quest.Main.1.0"]}),
           ("Story", "QuestDialogueActionStoryDialogue", {"StoryDialogueTag": tag})]
    files = {
        dialogue.STRINGS: "Key,SourceString\nQST_Context.1,Hello there.\nQST_Right.1.Short,Of course!\n",
        dialogue.TABLES + "StoryDialogues.csv": rows,
        dialogue.TABLES + "QuestDialogues.csv": HEADER,
        dialogue.QUESTS + "StoryDialogues/StoryDialogue_Short_Template.uasset":
            story_template("/Game/Quests/StoryDialogues/StoryDialogue_Short_Template"),
        dialogue.QUESTS + "StoryDialogues/StoryDialogue_End_Template.uasset":
            story_template("/Game/Quests/StoryDialogues/StoryDialogue_End_Template", extra=True),
        dialogue.QUESTS + "NpcDialogues/NPCUniques/NpcDialogue_Cat.uasset":
            build("/Game/Quests/NpcDialogues/NPCUniques/NpcDialogue_Cat",
                  graph_objects("NpcDialogue", npc, [(0, 1, {})], [0], "NpcDialogue_Cat")),
    }
    convs = {c["id"]: c for c in dialogue.conversations(FakeGame(files))}
    assert convs["npc:NpcDialogue_Cat"]["plays"] == [{"when": ["Quest.Main.1.0"], "story": tag}]
    story = convs[f"story:{tag}"]
    assert story["used_by"] == ["npc:NpcDialogue_Cat"]
    lines = story["lines"]
    assert [(line["talk"], line["row"][len(tag) + 1:], line["speaker"]) for line in lines] == [
        (1, "Context.1", "npc"), (1, "Question.1", "npc"), (1, "Right.1.Long", "player"),
        (1, "Wrong.1.Long", "player"), (2, "End", "npc")]
    assert lines[0]["key"] == "QST_Context.1" and lines[0]["text"] == "Hello there."
    assert lines[1]["text"] == "Debug Question.1"       # a key Strings_EN lacks: the row's DebugText
    right, wrong = lines[1]["answers"]
    assert (right["key"], right["text"], right["trait"], right["score"], right["clan_bonding"], right["next"]) == (
        "QST_Right.1.Short", "Of course!", "Brave", 9, 2, [2])
    assert (wrong["trait"], wrong["score"], wrong["next"]) == ("Ambitious", -3, [3])
    assert dialogue.lines_by_key(convs.values())["QST_Right.1.Short"] == [(f"story:{tag}", 1, "player")]


def test_a_quest_talk_is_its_template_filled_from_the_rows_and_decline_keeps_its_own_text():
    nodes = [("Task", "QuestDialogueTalkingNode", {"AutoFillSuffix": "Task.1"}),
             ("Accept", "QuestDialogueActionResolveAcceptQuest", {}),
             ("Long", "QuestDialogueTalkingNode", {"AutoFillSuffix": "Context.Answer.Long", "TalkingSource": 1}),
             ("Decline", "QuestDialogueTalkingNode", {"bAllowAutoFill": False, "Paragraph": key("STR_BYE")})]
    edges = [(0, 1, {"EdgeType": 1, "AutoFillSuffix": "Context.Answer.Short"}), (1, 2, {}),
             (0, 3, {"EdgeType": 4, "bAllowAutoFill": False, "Button": {"Text": key("STR_DECLINE")}})]
    stem = "Quest.Procedural.SideQuest.Things"
    rows = HEADER + "".join(f"{stem}.{s},{score},0,{t},{trait},vo,QST_Things.{s},x\n" for s, score, t, trait in [
        ("Title", 0, "NPC", "None"), ("Task.1", 0, "NPC", "None"), ("Context.Answer.Short", 3, "Player", "Wise"),
        ("Context.Answer.Long", 0, "Player", "None")])
    files = {
        dialogue.STRINGS: "Key,SourceString\nQST_Things.Task.1,Fetch things.\nSTR_BYE,Come back soon.\n",
        dialogue.TABLES + "StoryDialogues.csv": HEADER,
        dialogue.TABLES + "QuestDialogues.csv": rows,
        dialogue.QUESTS + "QuestDialogues/QuestDialogue_SideQuest_Template.uasset":
            build("/Game/Quests/QuestDialogues/QuestDialogue_SideQuest_Template",
                  graph_objects("QuestDialogue", nodes, edges, [0], "QuestDialogue_SideQuest_Template")),
    }
    [quest] = dialogue.conversations(FakeGame(files))
    assert (quest["id"], quest["graph"], quest["title"]["key"]) == (
        f"quest:{stem}", "QuestDialogue_SideQuest_Template", "QST_Things.Title")
    task, long, decline = quest["lines"]
    assert (task["row"], task["key"], task["text"]) == (f"{stem}.Task.1", "QST_Things.Task.1", "Fetch things.")
    accept, no = task["answers"]
    assert (accept["key"], accept["trait"], accept["score"], accept["next"]) == (
        "QST_Things.Context.Answer.Short", "Wise", 3, [1])
    assert (no["slot"], no["key"], no["row"], no["next"]) == (4, "STR_DECLINE", None, [2])
    assert (decline["key"], decline["row"], decline["text"]) == ("STR_BYE", None, "Come back soon.")
    assert long["speaker"] == "player"


def test_an_unknown_class_or_field_is_refused():
    data = bytearray(open(CAPTURED, "rb").read())
    pkg = ZenPackage(bytes(data))
    at = pkg._export_map + EXPORT_ENTRY * 1 + 32         # export 1's class index
    struct.pack_into("<Q", data, at, script_index("/Script/SwtQuest.SomethingNew"))
    with pytest.raises(FormatError, match="class wcmods doesn't know"):
        dialogue.read_graphs(bytes(data), "x")
    # ActivateDialogueView's RelativeOffsetDistance (an FFloatRange) has never been seen set; if it is, reading
    # the node fails rather than guessing
    view = graph_objects("NpcDialogue", [("View", "QuestDialogueActionActivateDialogueView", {})], [], [0])
    data = build("/Game/X", view)
    assert dialogue.read_graphs(data, "x")[0].roots()[0].cls == "QuestDialogueActionActivateDialogueView"
    schema = dialogue.SCHEMA["QuestDialogueActionActivateDialogueView"]
    assert schema[3] == ("RelativeOffsetDistance", "floatrange")
    with pytest.raises(FormatError, match="floatrange"):
        _Values(ZenPackage(data)).read_object(write_header([3], set()) + b"\0" * 24, schema)
