"""The dialogue graphs (wcmods/dialogue.py) and the object property types they added to the cooked format
(wcmods/formats/cooked.py), without the game: synthetic packages built here, laid out as the game's are. The
game's own 91 dialogue packages are checked byte for byte by `python wcmods.py selftest`; the repository ships
none of the game's files."""
import fnmatch
import struct

import pytest

from wcmods import dialogue, selftest
from wcmods.formats.anim import script_index
from wcmods.formats.cityhash import name_hash
from wcmods.formats.cooked import (EXPORT_ENTRY, NAME_HASH_VERSION, OBJECT_PACKAGE, PACKAGE_FILE_TAG, SUMMARY, Empty,
                                   EmptyList, FormatError, ZenPackage, _Reader, _Values, split_name, write_header)

NULL = (1 << 64) - 1
CINEMATIC = "/Game/Quests/NpcDialogues/Cinematic/CinematicDialogue_Test"


def key(k):
    return {"table": "SwtStrings", "key": k, "flags": 0}


def asset(package):
    """The file a /Game package is read from."""
    return "Wrc/Content/" + package[len("/Game/"):] + ".uasset"


# ------------------------------------------------------------------------------------- building packages
def name_batch(names):
    """An FNameBatch as a package's ImportedPackageNames holds it: the count, the string bytes, the hash version,
    a hash per name, big-endian lengths, the strings, then each name's number (0: none)."""
    if not names:
        return struct.pack("<I", 0)
    strings = b"".join(n.encode() for n in names)
    return (struct.pack("<IIQ", len(names), len(strings), NAME_HASH_VERSION)
            + b"".join(struct.pack("<Q", name_hash(n)) for n in names) + struct.pack(f">{len(names)}H", *map(len, names))
            + strings + struct.pack(f"<{len(names)}i", *[0] * len(names)))


def zen(package, exports, imports=(), hashes=(), imported=(), tail=b""):
    """A zen package laid out as the game's are, with only what ZenPackage reads filled in.
    exports: [(name, class FPackageObjectIndex, outer export index or None, write)], write(values) giving the
    export's bytes (values is the package's _Values, so names go into its name map); imports: the import map
    (FPackageObjectIndex values); hashes: the imported public export hashes; imported: the imported package
    names; tail: what follows the last export (a table's package file tag)."""
    n = len(exports)
    short = package.rsplit("/", 1)[-1]
    head = struct.pack("<IIQ", 1, len(short), NAME_HASH_VERSION) + b"\0" * 8 + struct.pack(">H", len(short)) + short.encode()
    pad = (-(SUMMARY.size + len(head))) % 8
    head += struct.pack("<q", pad) + b"\0" * pad
    hashes_at = SUMMARY.size + len(head) + 8                     # after the bulk data map's size (none)
    imports_at = hashes_at + 8 * len(hashes)
    exports_at = imports_at + 8 * len(imports)
    after = exports_at + EXPORT_ENTRY * n                        # the empty sections, then the imported names
    rest = (struct.pack("<q", 0) + b"".join(struct.pack("<Q", h) for h in hashes)
            + b"".join(struct.pack("<Q", v) for v in imports) + b"\0" * (EXPORT_ENTRY * n) + name_batch(list(imported)))
    summary = [0, SUMMARY.size + len(head) + len(rest), 0, 0, 0, 0, hashes_at, imports_at, exports_at] + [after] * 6
    pkg = ZenPackage(SUMMARY.pack(*summary) + head + rest)
    values = _Values(pkg)
    blobs = [write(values) for _, _, _, write in exports]
    entries = bytearray(EXPORT_ENTRY * n)
    for i, (name, cls, outer, _) in enumerate(exports):
        base, number = split_name(name)
        struct.pack_into("<QQIIQQQQQI", entries, EXPORT_ENTRY * i, 0, 0, pkg.name_index(base), number,
                         NULL if outer is None else outer, cls, NULL, NULL, 0, 8)
    em = pkg._export_map - pkg._after_names
    pkg._rest = pkg._rest[:em] + bytes(entries) + pkg._rest[em + len(entries):]
    return pkg.rebuild(b"".join(blobs) + tail, [len(b) for b in blobs])


def build(package, objects):
    """A zen package holding objects, [(name, class, outer export index or None, props)], each written as the
    game writes an object: its class's properties, then HasGuid 0."""
    return zen(package, [(name, script_index(f"/Script/{dialogue.CLASSES[cls][1]}.{cls}"), outer,
                          lambda values, cls=cls, props=props: values.write_object(props, dialogue.SCHEMA[cls]))
                         for name, cls, outer, props in objects])


def graph_objects(cls, nodes, edges, roots, name="Graph", props=None):
    """[(name, class, outer, props)] for a graph (export 0, named name, with props of its own) whose nodes are
    nodes, [(name, class, props)], and edges [(from, to, edge props)] by node position, the edges after the nodes."""
    first_edge = 1 + len(nodes)
    children = {i: [] for i in range(len(nodes))}
    parents = {i: [] for i in range(len(nodes))}
    for k, (a, b, _) in enumerate(edges):
        children[a].append((b, first_edge + k))
        parents[b].append(a)
    out = [(name, cls, None, dict(props or {}, RootNodes=[2 + r for r in roots],
                                  AllNodes=[2 + i for i in range(len(nodes))]))]
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


def cinematic(package=CINEMATIC):
    """A cinematic talk as the game's are made: an NpcDialogue whose root is the first of three narrator lines,
    one after another by plain edges, each naming its key."""
    nodes = [(f"QuestDialogueTalkingNode_{i}", "QuestDialogueTalkingNode", {
                 "Paragraph": key(f"QST_Story.Test.Context.{i}"), "TalkingSource": 3,
                 "TalkingSourceText": key("STR_COMMON_NARRATOR")}) for i in (1, 2, 3)]
    return build(package, graph_objects("NpcDialogue", nodes, [(0, 1, {}), (1, 2, {})], [0], package.rsplit("/", 1)[-1]))


def sequence_table(rows):
    """DT_QuestSequenceDialogues as the game cooks it: one DataTable export, its RowStruct a script import and
    each row's DialogueToUse an import of a graph in another package. rows: [(tag, graph package)]."""
    packages = list(dict.fromkeys(p for _, p in rows))       # in the order the rows first name them
    imports = [script_index("/Script/SwtQuest.SwtQuestSequenceDialoguesStruct")] + [
        OBJECT_PACKAGE << 62 | k << 32 | k for k in range(len(packages))]

    def table(values):
        out = write_header([0], set()) + struct.pack("<iIi", -1, 0, len(rows))   # RowStruct, HasGuid, row count
        for i, (tag, package) in enumerate(rows):
            out += values.write_name(f"Row_{i}") + values.write_struct(
                {"SequenceDialogueId": tag, "WidgetToUse": 3, "DialogueToUse": -2 - packages.index(package)},
                dialogue.SEQUENCE_ROW)
        return out
    return zen("/Game/Gameplay/DataTables/Sequencer/DT_QuestSequenceDialogues",
               [("DT_QuestSequenceDialogues", script_index("/Script/Engine.DataTable"), None, table)],
               imports=imports, hashes=[0x1000 + k for k in range(len(packages))], imported=packages,
               tail=PACKAGE_FILE_TAG)


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


class FakeIo:
    """The bits of the game's container the self-test's dialogue check uses."""

    def __init__(self, files):
        self.files = files

    def read_file(self, path):
        return self.files[path]


HEADER = "---,Score,ClanBonding,Talker,Trait,VoiceOver,StringKey,DebugText\n"


def tables(strings="Key,SourceString\n", story=HEADER, quest=HEADER):
    return {dialogue.STRINGS: strings, dialogue.TABLES + "StoryDialogues.csv": story,
            dialogue.TABLES + "QuestDialogues.csv": quest}


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


def test_a_cinematic_graph_decodes_and_its_objects_write_back():
    data = cinematic()
    [g] = dialogue.read_graphs(data, CINEMATIC)
    assert (g.cls, g.name) == ("NpcDialogue", "CinematicDialogue_Test")
    walk = g.walk()
    assert [n.cls for n in walk] == ["QuestDialogueTalkingNode"] * 3
    assert [dialogue.text_key(n.props["Paragraph"]) for n in walk] == [f"QST_Story.Test.Context.{i}" for i in (1, 2, 3)]
    pkg = ZenPackage(data)
    values = _Values(pkg)
    blobs = []
    for i in range(pkg.export_count):
        e = pkg.export_entry(i)
        blob = pkg.export_data[e.offset:e.offset + e.size]
        schema = dialogue.SCHEMA[dialogue.CLASS_OF[e.cls]]
        blobs.append(values.write_object(values.read_object(blob, schema), schema))
        assert blobs[-1] == blob
    assert pkg.rebuild(b"".join(blobs), [len(b) for b in blobs]) == data
    lines = dialogue._numbered([(1, dialogue._Builder(g, {"QST_Story.Test.Context.1": "Words."}).lines())])
    assert [line["next"] for line in lines] == [[1], [2], []]
    assert [line["speaker"] for line in lines] == ["custom"] * 3 and lines[0]["speaker_key"] == "STR_COMMON_NARRATOR"
    assert lines[0]["text"] == "Words." and lines[1]["text"] is None and lines[0]["fallback"] is None


def test_package_imports_resolve_and_a_cinematic_is_played_by_its_tags():
    other = "/Game/Quests/NpcDialogues/Cinematic/CinematicDialogue_Other"
    tags = [("Gameplay.Narrative.RankUp.WindClan.Leader", CINEMATIC), ("Gameplay.Narrative.Test", other),
            ("Gameplay.Narrative.Test.Again", CINEMATIC)]
    data = sequence_table(tags)
    pkg = ZenPackage(data)
    assert pkg.imported_packages() == [CINEMATIC, other]
    assert pkg.imports()[0] == script_index("/Script/SwtQuest.SwtQuestSequenceDialoguesStruct")
    assert pkg.resolve(-1) == ("script", script_index("/Script/SwtQuest.SwtQuestSequenceDialoguesStruct"))
    assert pkg.resolve(-2) == ("package", CINEMATIC, 0x1000)
    assert pkg.resolve(-3) == ("package", other, 0x1001)
    assert pkg.resolve(1) == ("export", 0) and pkg.resolve(0) is None
    for bad in (-4, 2):
        with pytest.raises(FormatError):
            pkg.resolve(bad)
    assert ZenPackage(cinematic()).imported_packages() == []
    game = FakeGame(dict(tables(), **{dialogue.SEQUENCES: data, asset(CINEMATIC): cinematic()}))
    assert dialogue.sequence_tags(game) == {CINEMATIC: ["Gameplay.Narrative.RankUp.WindClan.Leader",
                                                        "Gameplay.Narrative.Test.Again"],
                                            other: ["Gameplay.Narrative.Test"]}
    [conv] = dialogue.conversations(game)
    assert (conv["id"], conv["kind"], conv["package"]) == ("cinematic:CinematicDialogue_Test", "cinematic", CINEMATIC)
    assert conv["tag"] == ["Gameplay.Narrative.RankUp.WindClan.Leader", "Gameplay.Narrative.Test.Again"]
    # without the table, a cinematic has no tags
    del game.files[dialogue.SEQUENCES]
    assert dialogue.conversations(game)[0]["tag"] == []


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
    files = dict(tables("Key,SourceString\nQST_Context.1,Hello there.\nQST_Right.1.Short,Of course!\n", story=rows), **{
        dialogue.QUESTS + "StoryDialogues/StoryDialogue_Short_Template.uasset":
            story_template("/Game/Quests/StoryDialogues/StoryDialogue_Short_Template"),
        dialogue.QUESTS + "StoryDialogues/StoryDialogue_End_Template.uasset":
            story_template("/Game/Quests/StoryDialogues/StoryDialogue_End_Template", extra=True),
        dialogue.QUESTS + "NpcDialogues/NPCUniques/NpcDialogue_Cat.uasset":
            build("/Game/Quests/NpcDialogues/NPCUniques/NpcDialogue_Cat",
                  graph_objects("NpcDialogue", npc, [(0, 1, {})], [0], "NpcDialogue_Cat")),
    })
    convs = {c["id"]: c for c in dialogue.conversations(FakeGame(files))}
    assert convs["npc:NpcDialogue_Cat"]["plays"] == [{"when": ["Quest.Main.1.0"], "story": tag}]
    story = convs[f"story:{tag}"]
    assert story["used_by"] == ["npc:NpcDialogue_Cat"]
    lines = story["lines"]
    assert [(line["talk"], line["row"][len(tag) + 1:], line["speaker"]) for line in lines] == [
        (1, "Context.1", "npc"), (1, "Question.1", "npc"), (1, "Right.1.Long", "player"),
        (1, "Wrong.1.Long", "player"), (2, "End", "npc")]
    assert (lines[0]["key"], lines[0]["text"], lines[0]["fallback"]) == ("QST_Context.1", "Hello there.", None)
    # a key Strings_EN lacks: the game shows the row's DebugText, and says so
    assert (lines[1]["key"], lines[1]["text"], lines[1]["fallback"]) == ("QST_Question.1", "Debug Question.1", "debug")
    right, wrong = lines[1]["answers"]
    assert (right["key"], right["text"], right["trait"], right["score"], right["clan_bonding"], right["next"]) == (
        "QST_Right.1.Short", "Of course!", "Brave", 9, 2, [2])
    assert (wrong["trait"], wrong["score"], wrong["next"], wrong["fallback"]) == ("Ambitious", -3, [3], "debug")
    assert dialogue.lines_by_key(convs.values())["QST_Right.1.Short"] == [(f"story:{tag}", 1, "player")]


def test_a_quest_talk_is_its_template_filled_from_the_rows_and_decline_keeps_its_own_text():
    nodes = [("Task", "QuestDialogueTalkingNode", {"AutoFillSuffix": "Task.1"}),
             ("Accept", "QuestDialogueActionResolveAcceptQuest", {}),
             ("Long", "QuestDialogueTalkingNode", {"AutoFillSuffix": "Context.Answer.Long", "TalkingSource": 1}),
             ("Decline", "QuestDialogueTalkingNode", {"bAllowAutoFill": False, "Paragraph": key("STR_BYE")})]
    edges = [(0, 1, {"EdgeType": 1, "AutoFillSuffix": "Context.Answer.Short"}), (1, 2, {}),
             (0, 3, {"EdgeType": 4, "bAllowAutoFill": False, "Button": {"Text": key("STR_DECLINE")}})]
    stem = "Quest.Procedural.SideQuest.Things"
    rows = HEADER + "".join(f"{stem}.{s},{score},0,{t},{trait},vo,QST_Things.{s},QST_Things.{s}\n"
                            for s, score, t, trait in [
                                ("Title", 0, "NPC", "None"), ("Task.1", 0, "NPC", "None"),
                                ("Context.Answer.Short", 3, "Player", "Wise"), ("Context.Answer.Long", 0, "Player", "None")])
    files = dict(tables("Key,SourceString\nQST_Things.Task.1,Fetch things.\nQST_Things.Context.Answer.Short,Yes.\n"
                        "STR_BYE,Come back soon.\n", quest=rows), **{
        dialogue.QUESTS + "QuestDialogues/QuestDialogue_SideQuest_Template.uasset":
            build("/Game/Quests/QuestDialogues/QuestDialogue_SideQuest_Template",
                  graph_objects("QuestDialogue", nodes, edges, [0], "QuestDialogue_SideQuest_Template")),
    })
    [quest] = dialogue.conversations(FakeGame(files))
    assert (quest["id"], quest["graph"], quest["title"]["key"]) == (
        f"quest:{stem}", "QuestDialogue_SideQuest_Template", "QST_Things.Title")
    task, long, decline = quest["lines"]
    assert (task["row"], task["key"], task["text"], task["fallback"]) == (
        f"{stem}.Task.1", "QST_Things.Task.1", "Fetch things.", None)
    accept, no = task["answers"]
    assert (accept["key"], accept["text"], accept["trait"], accept["score"], accept["next"]) == (
        "QST_Things.Context.Answer.Short", "Yes.", "Wise", 3, [1])
    assert (no["slot"], no["key"], no["row"], no["next"]) == (4, "STR_DECLINE", None, [2])
    assert (decline["key"], decline["row"], decline["text"]) == ("STR_BYE", None, "Come back soon.")
    assert long["speaker"] == "player"
    # QuestDialogues.csv's DebugText is the key itself: a key Strings_EN lacks shows as the raw key in game, so
    # it isn't passed off as English
    assert (long["key"], long["text"], long["fallback"]) == ("QST_Things.Context.Answer.Long", None, "key")
    assert (quest["title"]["text"], quest["title"]["fallback"]) == (None, "key")


def test_a_quest_answer_its_row_leaves_empty_gets_the_games_own_key():
    # as the game's edge fill does (0x141663B70): Accept or Decline without a trait, the graph's trait answer key
    # with one (Context before a ResolveAcceptQuest, Return otherwise); an autofilled node or edge with no
    # suffix has its own text cleared
    nodes = [("Task", "QuestDialogueTalkingNode", {"AutoFillSuffix": "Task.1"}),
             ("AcceptA", "QuestDialogueActionResolveAcceptQuest", {}),
             ("AcceptB", "QuestDialogueActionResolveAcceptQuest", {}),
             ("Confirm", "QuestDialogueActionResolveConfirm", {}),
             ("Decline", "QuestDialogueActionResolveDeclineQuest", {}),
             ("Blank", "QuestDialogueTalkingNode", {"Paragraph": key("STR_OWN")})]
    edges = [(0, 1, {"EdgeType": 1, "Button": {"Text": key("STR_OWN")}}),
             (0, 2, {"EdgeType": 2, "TraitType": 1, "AutoFillSuffix": "No.Such.Row"}),
             (0, 3, {"EdgeType": 3, "TraitType": 3}),
             (0, 4, {"EdgeType": 4}),
             (1, 5, {})]
    data = build("/Game/Quests/QuestDialogues/Q", graph_objects("QuestDialogue", nodes, edges, [0], "Q",
                                                                 {"AutoFillPrefix": "QST_Things"}))
    [g] = dialogue.read_graphs(data, "x")
    strings = {"STR_QUEST_DIALOGUE_ACCEPT": "Accept", "STR_QUEST_DIALOGUE_DECLINE": "Decline", "STR_OWN": "Own",
               "QST_Things.Context.Answer.Brave.Short": "I'll go!"}
    stem = "Quest.Procedural.SideQuest.Things"
    rows = {f"{stem}.Task.1": {"StringKey": "QST_Things.Task.1", "DebugText": "QST_Things.Task.1", "Talker": "NPC"}}
    lines = dialogue._numbered([(1, dialogue._Builder(g, strings, rows, dialogue._quest_resolver(stem),
                                                      dialogue._quest_default(g)).lines())])
    task, blank = lines
    assert [(a["slot"], a["key"], a["text"], a["row"], a["fallback"]) for a in task["answers"]] == [
        (1, "STR_QUEST_DIALOGUE_ACCEPT", "Accept", None, "default"),
        (2, "QST_Things.Context.Answer.Brave.Short", "I'll go!", None, "default"),
        (3, None, None, None, "default"),         # QST_Things.Return.Answer.Wise.Short isn't a key: left empty
        (4, "STR_QUEST_DIALOGUE_DECLINE", "Decline", None, "default")]
    assert (task["key"], task["text"], task["fallback"]) == ("QST_Things.Task.1", None, "key")
    assert (blank["key"], blank["text"], blank["row"]) == (None, None, None)


def test_the_selftest_dialogue_check_rebuilds_packages_and_fails_on_bad_ones():
    short = dialogue.QUESTS + "StoryDialogues/StoryDialogue_Short_Template.uasset"
    files = {short: story_template("/Game/Quests/StoryDialogues/StoryDialogue_Short_Template"),
             asset(CINEMATIC): cinematic()}
    ok, detail = selftest._dialogue_graphs(FakeIo(files))
    assert ok, detail
    assert detail == "2 packages (2 rebuilt the same), 18 of 18 objects"
    # a package cut short, or a class wcmods doesn't know, fails the check instead of raising
    for bad in (files[asset(CINEMATIC)][:200], files[asset(CINEMATIC)][:-3]):
        ok, detail = selftest._dialogue_graphs(FakeIo(dict(files, **{asset(CINEMATIC): bad})))
        assert not ok and "CinematicDialogue_Test" in detail
    data = bytearray(files[asset(CINEMATIC)])
    struct.pack_into("<Q", data, ZenPackage(bytes(data))._export_map + EXPORT_ENTRY + 32, script_index("/Script/X.Y"))
    ok, detail = selftest._dialogue_graphs(FakeIo(dict(files, **{asset(CINEMATIC): bytes(data)})))
    assert not ok and "KeyError" in detail
    # and so does a Short template the walk can't read
    ok, detail = selftest._dialogue_graphs(FakeIo(dict(files, **{short: files[short][:150]})))
    assert not ok and "StoryDialogue_Short_Template" in detail


def test_an_unknown_class_or_field_is_refused():
    data = bytearray(cinematic())
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
