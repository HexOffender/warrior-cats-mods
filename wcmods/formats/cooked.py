"""Cooked DataTables: read the rows of one of the game's cooked table assets and add rows to it.

Some of the game's tables are cooked assets in its IoStore container rather than CSVs. The names,
descriptions and icons of items, for one, are DT_QuestObjectsInfo, and the inventory leaves out an item
without a row there. A mod's new rows are written into a copy of the game's own asset at install
(BuildContext.add_table_row), so nothing of the game's is shipped.

Format (UE 5.7 zen packages with unversioned properties; docs/reverse-engineering.md has the details):
  * Package: a 60-byte summary, the name map (an FNameBatch with CityHash64 hashes), an i64 pad size and
    that many bytes so the next field is 8-aligned, then the bulk data map, imports, export map and the
    other sections. The summary's HeaderSize is where the export data starts.
  * DataTable export: the object's own properties (an unversioned header and RowStruct), a u32 HasGuid,
    an i32 row count, then each row's FName and the row struct, also unversioned. The package file tag
    follows the export.
  * Unversioned struct: u16 fragments (skip count in bits 0-6, "has zeroes" bit 7, last-fragment bit 8,
    value count in bits 9-15), a zero mask when any fragment has zeroes, then the values that aren't zero,
    in the struct's property order.
"""
import struct

from .binio import read_fstring, write_fstring
from .cityhash import name_hash

SUMMARY = struct.Struct("<IIIIII" + "i" * 9)
SHIFTED = range(6, 15)          # summary fields that are offsets past the name map
EXPORT_ENTRY = 72
PACKAGE_FILE_TAG = b"\xc1\x83\x2a\x9e"
EMPTY_Z = "\0"                  # an empty FString written as a lone terminator (length 1), kept as it was
NAME_HASH_VERSION = 0xC1640000  # FNameHash's algorithm id, written in a name batch's header

# Row structs, as (field, type) in the struct's property order. Types: "tag" (FGameplayTag), "text"
# (FText), "soft" (FSoftObjectPath), "name", "u8" (a byte enum), "i32", "f32".
SCHEMAS = {
    "QuestObjectsInfoDataStruct": [
        ("itemTag", "tag"), ("Name", "text"), ("Description", "text"), ("Icon", "soft"),
        ("ItemRarity", "u8"), ("ItemGroupIcon", "u8"), ("ItemCategoryColor", "u8"),
    ],
}

# The cooked tables wcmods can add rows to: name -> (asset path, row struct).
TABLES = {
    "DT_QuestObjectsInfo": ("Wrc/Content/Gameplay/DataTables/Quests/DT_QuestObjectsInfo.uasset",
                            "QuestObjectsInfoDataStruct"),
}

# The enums in QuestObjectsInfoDataStruct, by name (read from the exe's reflection data).
ITEM_RARITY = {"None": 0, "Common": 1, "Uncommon": 2, "Rare": 3, "Mythic": 4}
ITEM_GROUP_ICON = {"None": 0, "Health": 1, "Stamina": 2, "Stats": 3, "Status": 4, "Damage": 5,
                   "Experience": 6, "Free": 7}
ITEM_CATEGORY_COLOR = {"None": 0, "Consumable": 1, "Quest": 2, "Den": 3}


class FormatError(ValueError):
    """The asset isn't laid out as wcmods expects (a game update may have changed it)."""


def split_name(s):
    """FName's split of "Base_N" into (base, number), as FName("NewRow_45") gives ("NewRow", 46)."""
    base, _, tail = s.rpartition("_")
    if base and tail.isdigit() and len(tail) <= 10 and (tail == "0" or tail[0] != "0") and int(tail) < 0x7FFFFFFF:
        return base, int(tail) + 1
    return s, 0


def base_text(text, key, namespace="WCMods"):
    """An FText value that shows `text` (in every language: the game has no translation for it)."""
    return {"ns": namespace, "key": key, "text": text}


class ZenPackage:
    """A cooked package: its name map can grow and its exports be replaced."""

    def __init__(self, data):
        if len(data) < SUMMARY.size:
            raise FormatError("too short for a package")
        self.summary = list(SUMMARY.unpack_from(data, 0))
        if self.summary[0]:
            raise FormatError("packages with versioning info aren't supported")
        p = SUMMARY.size
        (count,) = struct.unpack_from("<I", data, p)
        string_bytes, self.hash_version = 0, NAME_HASH_VERSION
        if count:                          # an empty batch is just its count
            string_bytes, self.hash_version = struct.unpack_from("<IQ", data, p + 4)
            p += 12
        p += 4
        self.hashes = list(struct.unpack_from(f"<{count}Q", data, p))
        p += 8 * count
        lengths = struct.unpack_from(f">{count}H", data, p)
        p += 2 * count
        start = p
        self.names = []
        for n in lengths:
            if n & 0x8000:
                raise FormatError("wide names in the name map aren't supported")
            self.names.append(data[p:p + n].decode("ascii"))
            p += n
        if p - start != string_bytes:
            raise FormatError("name map size doesn't add up")
        (pad,) = struct.unpack_from("<q", data, p)
        if pad != (-p) % 8:
            raise FormatError(f"unexpected padding after the name map ({pad})")
        self._after_names = p + 8 + pad
        self.header_size = self.summary[1]
        self._rest = data[self._after_names:self.header_size]
        self.export_data = data[self.header_size:]
        self._export_map = self.summary[8]
        self.export_count = (self.summary[13] - self._export_map) // EXPORT_ENTRY
        self.data = data
        self._index = {n: i for i, n in enumerate(self.names)}

    def check_hashes(self, sample=64):
        """True if wcmods' name hash matches the stored ones (the first `sample` names)."""
        return all(name_hash(n) == h for n, h in list(zip(self.names, self.hashes))[:sample])

    def name_index(self, name):
        """The name map index of `name`, adding it if it's new."""
        i = self._index.get(name)
        if i is None:
            if not name.isascii():
                raise ValueError(f"{name!r}: only ASCII names can be added")
            i = len(self.names)
            self.names.append(name)
            self.hashes.append(name_hash(name))
            self._index[name] = i
        return i

    def export(self, i):
        """(offset into the export data, size) of export i."""
        return struct.unpack_from("<QQ", self.data, self._export_map + EXPORT_ENTRY * i)

    def rebuild(self, export_data, sizes):
        """The package with the current name map and new export data; sizes[i] is export i's size."""
        strings = b"".join(n.encode("ascii") for n in self.names)
        if self.names:
            head = struct.pack("<IIQ", len(self.names), len(strings), self.hash_version)
            head += struct.pack(f"<{len(self.hashes)}Q", *self.hashes)
            head += struct.pack(f">{len(self.names)}H", *(len(n) for n in self.names))
            head += strings
        else:
            head = struct.pack("<I", 0)
        pad = (-(SUMMARY.size + len(head))) % 8
        head += struct.pack("<q", pad) + b"\0" * pad
        shift = SUMMARY.size + len(head) - self._after_names
        summary = list(self.summary)
        summary[1] += shift
        for i in SHIFTED:
            summary[i] += shift
        rest = bytearray(self._rest)
        em = self._export_map - self._after_names
        off = 0
        for i in range(self.export_count):
            struct.pack_into("<QQ", rest, em + EXPORT_ENTRY * i, off, sizes[i])
            off += sizes[i]
        return SUMMARY.pack(*summary) + head + bytes(rest) + export_data


# ------------------------------------------------------------------------------- unversioned values
class _Reader:
    def __init__(self, data, pos=0):
        self.data, self.pos = data, pos

    def take(self, fmt):
        v = struct.unpack_from(fmt, self.data, self.pos)
        self.pos += struct.calcsize(fmt)
        return v[0] if len(v) == 1 else v

    def fstring(self):
        if struct.unpack_from("<i", self.data, self.pos)[0] == 1 and self.data[self.pos + 4] == 0:
            self.pos += 5
            return EMPTY_Z
        s, self.pos = read_fstring(self.data, self.pos)
        return s


def _fstring(s):
    return struct.pack("<i", 1) + b"\0" if s == EMPTY_Z else write_fstring(s)


def read_header(r):
    """An unversioned header: (property indexes with a value, the subset of those that are zero)."""
    frags = []
    while True:
        v = r.take("<H")
        frags.append((v & 0x7F, v >> 9, bool(v & 0x80)))
        if v & 0x100:
            break
    zeroable = sum(n for _, n, z in frags if z)
    bits = 0
    if zeroable:
        if zeroable <= 8:
            bits = r.take("<B")
        elif zeroable <= 16:
            bits = r.take("<H")
        else:
            for k in range((zeroable + 31) // 32):
                bits |= r.take("<I") << (32 * k)
    present, zero, index, z = [], set(), 0, 0
    for skip, n, has_zero in frags:
        index += skip
        for _ in range(n):
            present.append(index)
            if has_zero:
                if bits >> z & 1:
                    zero.add(index)
                z += 1
            index += 1
    return present, zero


def write_header(present, zero):
    """Inverse of read_header for sorted property indexes."""
    if not present:
        return struct.pack("<H", 0x100)
    frags, i, last = [], 0, 0
    while i < len(present):
        run = 1
        while i + run < len(present) and present[i + run] == present[i] + run:
            run += 1
        skip = present[i] - last
        while skip > 127:
            frags.append((127, []))
            skip -= 127
        run_indexes = present[i:i + run]
        while run_indexes:
            frags.append((skip, run_indexes[:127]))
            run_indexes, skip = run_indexes[127:], 0
        last = present[i] + run
        i += run
    out, bits = b"", []
    for k, (skip, idx) in enumerate(frags):
        has_zero = any(j in zero for j in idx)
        out += struct.pack("<H", skip | (0x80 if has_zero else 0) | (0x100 if k == len(frags) - 1 else 0)
                           | len(idx) << 9)
        if has_zero:
            bits += [j in zero for j in idx]
    if bits:
        v = sum(1 << k for k, b in enumerate(bits) if b)
        if len(bits) <= 8:
            out += struct.pack("<B", v)
        elif len(bits) <= 16:
            out += struct.pack("<H", v)
        else:
            out += b"".join(struct.pack("<I", v >> (32 * k) & 0xFFFFFFFF) for k in range((len(bits) + 31) // 32))
    return out


ZERO = {"tag": "", "name": "None", "u8": 0, "i32": 0, "f32": 0.0}


def _zero(kind):
    if kind == "soft":
        return {"package": "None", "asset": "None", "sub": ""}
    if kind not in ZERO:
        raise FormatError(f"a {kind} field written as zero")
    return ZERO[kind]


class _Values:
    """Reads and writes property values; names go through the package's name map."""

    def __init__(self, pkg):
        self.pkg = pkg

    def name(self, r):
        i, number = r.take("<II")
        if i >= len(self.pkg.names):
            raise FormatError("a name index past the name map")
        n = self.pkg.names[i]
        return n if number == 0 else f"{n}_{number - 1}"

    def write_name(self, s):
        base, number = split_name(s)
        return struct.pack("<II", self.pkg.name_index(base), number)

    def read(self, r, kind):
        if kind == "name":
            return self.name(r)
        if kind == "tag":
            present, zero = read_header(r)
            return self.name(r) if present == [0] and not zero else ""
        if kind == "text":
            flags, history = r.take("<ib")
            if history == 11:
                return {"table": self.name(r), "key": r.fstring(), "flags": flags}
            if history == 0:
                return {"ns": r.fstring(), "key": r.fstring(), "text": r.fstring(), "flags": flags}
            if history == -1:
                return {"invariant": r.fstring() if r.take("<I") else None, "flags": flags}
            raise FormatError(f"text history type {history} isn't supported")
        if kind == "soft":
            return {"package": self.name(r), "asset": self.name(r), "sub": r.fstring()}
        if kind == "u8":
            return r.take("<B")
        if kind == "i32":
            return r.take("<i")
        if kind == "f32":
            return r.take("<f")
        raise FormatError(f"unknown field type {kind}")

    def write(self, v, kind):
        if kind == "name":
            return self.write_name(v)
        if kind == "tag":
            return write_header([0], set()) + self.write_name(v) if v else write_header([], set())
        if kind == "text":
            flags = v.get("flags", 0)
            if "table" in v:
                return struct.pack("<ib", flags, 11) + self.write_name(v["table"]) + _fstring(v["key"])
            if "text" in v:
                return (struct.pack("<ib", flags, 0) + _fstring(v.get("ns", "")) + _fstring(v["key"])
                        + _fstring(v["text"]))
            s = v.get("invariant")
            return (struct.pack("<ib", v.get("flags", 2), -1) + struct.pack("<I", s is not None)
                    + (_fstring(s) if s is not None else b""))
        if kind == "soft":
            return self.write_name(v["package"]) + self.write_name(v["asset"]) + _fstring(v.get("sub", ""))
        if kind == "u8":
            return struct.pack("<B", v)
        if kind == "i32":
            return struct.pack("<i", v)
        if kind == "f32":
            return struct.pack("<f", v)
        raise ValueError(f"unknown field type {kind}")

    @staticmethod
    def is_zero(v, kind):
        """Whether a value is written as "zero" (all bytes 0 in memory). Never for text: a zeroed FText
        isn't a valid one."""
        if kind == "soft":
            return v.get("package", "None") == "None" and v.get("asset", "None") == "None" and not v.get("sub")
        return kind in ZERO and v == ZERO[kind]

    def read_struct(self, r, schema):
        present, zero = read_header(r)
        if present and present[-1] >= len(schema):
            raise FormatError("a row has more fields than wcmods knows (the game may have updated)")
        return {schema[i][0]: _zero(schema[i][1]) if i in zero else self.read(r, schema[i][1])
                for i in present}

    def write_struct(self, values, schema):
        unknown = set(values) - {f for f, _ in schema}
        if unknown:
            raise ValueError(f"unknown field(s): {', '.join(sorted(unknown))}")
        # Fields left out (or None) aren't written, so the game gives them the struct's default.
        present = [i for i, (f, _) in enumerate(schema) if values.get(f) is not None]
        zero = {i for i in present if self.is_zero(values[schema[i][0]], schema[i][1])}
        out = write_header(present, zero)
        for i in present:
            if i not in zero:
                out += self.write(values[schema[i][0]], schema[i][1])
        return out


class DataTable:
    """A cooked DataTable's rows: [(row name, {field: value})], in the table's order. The game's rows
    are written back byte for byte as they were read (changing their values here changes nothing);
    add() adds new ones."""

    def __init__(self, data, schema):
        self.pkg = ZenPackage(data)
        if self.pkg.export_count != 1:
            raise FormatError("only tables with a single export are supported")
        self.schema = SCHEMAS[schema] if isinstance(schema, str) else schema
        self._values = _Values(self.pkg)
        off, size = self.pkg.export(0)
        if off != 0:
            raise FormatError("the table's export doesn't start the export data")
        blob = self.pkg.export_data[off:off + size]
        self._trailer = self.pkg.export_data[off + size:]
        if self._trailer[-4:] != PACKAGE_FILE_TAG:
            raise FormatError("the table's export doesn't end where expected")
        r = _Reader(blob)
        present, zero = read_header(r)
        if present != [0] or zero:
            raise FormatError("the table's own properties aren't laid out as expected")
        r.take("<i")                       # RowStruct (an import)
        if r.take("<I") != 0:              # HasGuid
            raise FormatError("the table has an object GUID")
        self._prefix = blob[:r.pos]
        count = r.take("<i")
        self.rows, self._raw = [], []
        for _ in range(count):
            start = r.pos
            name = self._values.name(r)
            self.rows.append((name, self._values.read_struct(r, self.schema)))
            self._raw.append(blob[start:r.pos])
        if r.pos != len(blob):
            raise FormatError(f"{len(blob) - r.pos} bytes after the last row (the row struct may have changed)")
        self._blob = blob

    def find(self, field, value):
        """The first row whose `field` is `value`, as (name, values), or None."""
        return next(((n, v) for n, v in self.rows if v.get(field) == value), None)

    def add(self, name, values):
        """Add a row (values for the fields it sets; the rest get the struct's default). It's encoded
        now, so a value wcmods can't write is refused here, with ValueError, not when the table is
        written."""
        if any(n == name for n, _ in self.rows):
            raise ValueError(f"the table already has a row {name}")
        try:
            raw = self.encode_row(name, values)
        except (ValueError, TypeError, AttributeError, KeyError, struct.error) as e:
            raise ValueError(f"row {name}: {type(e).__name__}: {e}") from None
        self.rows.append((name, dict(values)))
        self._raw.append(raw)

    def encode_row(self, name, values):
        return self._values.write_name(name) + self._values.write_struct(values, self.schema)

    def check_encoder(self):
        """True if re-encoding every row from its values gives the game's own bytes."""
        return all(self.encode_row(n, v) == raw for (n, v), raw in zip(self.rows, self._raw))

    def bytes(self):
        """The package with every row: the game's as they were, then the added ones."""
        out = bytearray(self._prefix)
        out += struct.pack("<i", len(self.rows))
        for raw in self._raw:
            out += raw
        return self.pkg.rebuild(bytes(out) + self._trailer, [len(out)])


def soft_path(asset_path):
    """An icon or other soft reference from an asset path, e.g. "/Game/Art/UXD/Textures/X/T_Icon_D"."""
    path = asset_path.split(".", 1)[0]
    return {"package": path, "asset": path.rsplit("/", 1)[-1], "sub": ""}


def game_file(asset_path):
    """The container path of an asset path: /Game/X/Y -> Wrc/Content/X/Y.uasset."""
    path = asset_path.split(".", 1)[0]
    if not path.startswith("/Game/"):
        raise ValueError(f"{asset_path}: asset paths start with /Game/")
    return "Wrc/Content/" + path[len("/Game/"):] + ".uasset"
