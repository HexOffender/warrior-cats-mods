"""Accessories: the game's own list of their looks, and new looks for them.

An accessory is a model (one per EAccesoryIds value: BigLeaf, DogCollar...) and a list of colour
textures, its variations: the Red Dog Collar is DogCollar's variation 2, the same model with another
texture. An inventory tag says which: Gameplay.Inventory.Cosmetic.<Head|Neck|Body|Legs>.<name>.<n>.

The GUI manager Blueprint's defaults hold both lists the game uses:
  * AccesoryVariations: a map of each accessory to a struct whose Textures array holds soft references
    to its looks' textures (look n is entry n);
  * AccesoriesTestTags: every accessory tag the game accepts. A tag missing from it is worn as look 1.
Both are read when the game starts, so a new look goes into the Blueprint at install (add_looks), not
into the running game.
"""
import struct

from .formats.cooked import ZenPackage, split_name

GUI_MANAGER = "Wrc/Content/Gameplay/Blueprints/Core/BP_WrcGuiManager.uasset"
ENUM_PREFIX = "EAccesoryIds::"
TAG_PREFIX = "Gameplay.Inventory.Cosmetic."
SOFT_REF = struct.Struct("<IIIIi")        # package FName, asset FName, sub-path FString (empty)
TAG_ITEM = struct.Struct("<HII")          # a gameplay tag in an array: header 0x0300, then its FName


def _lists(pkg, blob):
    """{accessory: (offset of its Textures count, [texture asset paths])} in the defaults' bytes. An
    entry is the key (FName "EAccesoryIds::<name>"), the struct's header (0x0300: one field, Textures),
    the array's count, then each soft reference."""
    names, out, p = pkg.names, {}, 0
    while True:
        p = blob.find(b"\x00\x03", p)
        if p < 0:
            return out
        q, p = p, p + 1
        if q < 8 or q + 6 > len(blob):
            continue
        key, num = struct.unpack_from("<II", blob, q - 8)
        if num != 0 or key >= len(names) or not names[key].startswith(ENUM_PREFIX):
            continue
        (count,) = struct.unpack_from("<i", blob, q + 2)
        if not 0 < count <= 64:
            continue
        r, textures = q + 6, []
        for _ in range(count):
            if r + SOFT_REF.size > len(blob):
                textures = None
                break
            pk, pn, ak, an, sub = SOFT_REF.unpack_from(blob, r)
            if pn or an or sub or pk >= len(names) or ak >= len(names) or not names[pk].startswith("/Game/"):
                textures = None
                break
            textures.append(f"{names[pk]}.{names[ak]}")
            r += SOFT_REF.size
        if textures:
            out[names[key][len(ENUM_PREFIX):]] = (q + 2, textures)
            p = r


def _tag_list(pkg, blob):
    """(offset of AccesoriesTestTags' count, [tags]): the longest array of accessory tags (the DLC's is
    the other, shorter one)."""
    names, best, p = pkg.names, None, 0
    while True:
        p = blob.find(b"\x00\x03", p)
        if p < 0:
            return best
        q, p = p, p + 1
        if q < 4:
            continue
        (count,) = struct.unpack_from("<i", blob, q - 4)
        if not 0 < count <= 512 or q + count * TAG_ITEM.size > len(blob):
            continue
        tags = []
        for i in range(count):
            head, idx, num = TAG_ITEM.unpack_from(blob, q + i * TAG_ITEM.size)
            if head != 0x0300 or num != 0 or idx >= len(names) or not names[idx].startswith(TAG_PREFIX):
                tags = None
                break
            tags.append(names[idx])
        if tags and (best is None or len(tags) > len(best[1])):
            best = (q - 4, tags)
            p = q + count * TAG_ITEM.size


def _defaults(pkg):
    """The index of the Blueprint's defaults export (Default__...)."""
    for i in range(pkg.export_count):
        name_index = struct.unpack_from("<I", pkg.data, pkg._export_map + 72 * i + 16)[0]
        if pkg.names[name_index].startswith("Default__"):
            return i
    raise ValueError("the GUI manager has no defaults object (the game may have updated)")


def read_variations(data):
    """{accessory name: [texture asset path, ...]} from BP_WrcGuiManager's package bytes."""
    pkg = ZenPackage(data)
    off, size = pkg.export(_defaults(pkg))
    return {name: textures for name, (_, textures) in _lists(pkg, pkg.export_data[off:off + size]).items()}


def add_looks(data, looks):
    """BP_WrcGuiManager's package with new looks: looks are {"name", "var", "path", "tag"}, var the
    look's number (its accessory's next). Each texture goes at the end of its accessory's list and each
    tag into AccesoriesTestTags."""
    pkg = ZenPackage(data)
    which = _defaults(pkg)
    exports = [pkg.export(i) for i in range(pkg.export_count)]
    if any(exports[i][0] != sum(s for _, s in exports[:i]) for i in range(len(exports))):
        raise ValueError("the GUI manager's exports aren't laid out as expected")
    off, size = exports[which]
    blob = bytearray(pkg.export_data[off:off + size])
    lists = _lists(pkg, bytes(blob))
    tags = _tag_list(pkg, bytes(blob))
    if tags is None:
        raise ValueError("the GUI manager's list of accessory tags isn't where expected (the game may have updated)")

    def name_ref(s):
        base, number = split_name(s)
        return pkg.name_index(base), number

    edits = {}                                # offset of an array's count -> [element bytes]
    for look in sorted(looks, key=lambda x: (x["name"], x["var"])):
        if look["name"] not in lists:
            raise ValueError(f"the game has no list of looks for {look['name']}")
        at, textures = lists[look["name"]]
        added = edits.setdefault(at, [])
        if look["var"] != len(textures) + len(added) + 1:
            raise ValueError(f"{look['name']} has {len(textures) + len(added)} looks, so a new one is "
                             f"{len(textures) + len(added) + 1}, not {look['var']}")
        package, asset = look["path"].split(".", 1)
        (pi, pn), (ai, an) = name_ref(package), name_ref(asset)
        added.append(SOFT_REF.pack(pi, pn, ai, an, 0))
        if look["tag"] in tags[1]:
            raise ValueError(f"the game already has {look['tag']}")
        ti, tn = name_ref(look["tag"])
        edits.setdefault(tags[0], []).append(TAG_ITEM.pack(0x0300, ti, tn))
    for at in sorted(edits, reverse=True):     # from the end, so earlier offsets stay right
        (count,) = struct.unpack_from("<i", blob, at)
        step = TAG_ITEM.size if at == tags[0] else SOFT_REF.size
        end = at + 4 + count * step
        blob[end:end] = b"".join(edits[at])
        struct.pack_into("<i", blob, at, count + len(edits[at]))
    parts = [pkg.export_data[o:o + s] for o, s in exports]
    parts[which] = bytes(blob)
    trailer = pkg.export_data[sum(s for _, s in exports):]
    return pkg.rebuild(b"".join(parts) + trailer, [len(x) for x in parts])
