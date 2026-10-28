"""WrcGame.sav codec and save backups.

WrcGame.sav is a GVAS file whose SwtSaveGame object holds Hash, GamerId, Version, saveSlots
and CompressedData. CompressedData is what Unreal's FArchiveSaveCompressedProxy writes: one
compressed archive after another, each holding the next 128 KiB of the payload (the proxy
compresses its buffer as an archive of its own each time it fills, so a new save is one archive
and a long-played one is several). An archive is an 8-byte tag, the block size (128 KiB), a
compressor byte (3: zlib), a summary (compressed and uncompressed sizes), one entry per block (the
same two sizes), then the zlib blocks. The payload is [u32 len+8][u32 len][JSON bytes, each minus
1][u32 len]. WrcGame.json next to it is the same JSON in plain text.

Edits are made to the JSON text in place so the game's own formatting is preserved. The header (Hash,
GamerId, Version, saveSlots) is kept byte for byte. Hash is not a checksum: the game makes a new one
from the clock and an address each time it writes (next_hash) and never checks it, so there is nothing
to verify a save against (docs/reverse-engineering.md, "The save").
"""
import datetime
import os
import re
import shutil
import struct
import zlib

from .cityhash import cityhash64_with_seed

ARCHIVE_TAG = b"\xc1\x83\x2a\x9e\x22\x22\x22\x22"
BLOCK = 0x20000   # LOADING_COMPRESSION_CHUNK_SIZE: the proxy's buffer, so the most one archive holds
ZLIB = 3          # the compressor byte for zlib
SAV_NAME, JSON_NAME = "WrcGame.sav", "WrcGame.json"
# wcmods' record of the save edits made to the save, as it was when a backup was made (saverecord.py): kept in
# the backup's folder beside the save files, never copied into the saves folder or out of it as a save file.
RECORD_NAME = "wcmods-save-changes.json"


class SaveGame:
    def __init__(self, raw):
        self.raw = bytes(raw)
        name = self.raw.find(b"CompressedData\0")
        if not self.raw.startswith(b"GVAS") or name < 0:
            raise ValueError("not a Warrior Cats save (no CompressedData property)")
        tag = self.raw.find(ARCHIVE_TAG, name)
        if tag < 0:
            raise ValueError("not a Warrior Cats save (CompressedData holds no compressed archive)")
        # property tag: ... size(int32) flags(u8) | array count(int32) | archives
        self._size_pos = tag - 9
        self._count_pos = tag - 4
        (count,) = struct.unpack_from("<i", self.raw, self._count_pos)
        (size,) = struct.unpack_from("<i", self.raw, self._size_pos)
        if size != count + 4:
            raise ValueError("unexpected CompressedData layout")
        self._data_start = tag
        self._data_end = tag + count
        try:
            self.json_text = _decode_archive(self.raw[tag:tag + count])
        except (struct.error, IndexError, zlib.error) as e:   # cut short, or not laid out as expected
            raise ValueError(f"the save's compressed data isn't laid out the way wcmods expects ({e})") from None

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    @property
    def hash(self):
        """USwtSaveGame.Hash, the uint64 in the header, or None if the header hasn't got one. The game sets a
        new one at every write (next_hash) and never reads it back; wcmods keeps the value it read."""
        value = _header_value(self.raw[:self._data_start], "Hash", "UInt64Property", 8)
        return None if value is None else struct.unpack("<Q", value)[0]

    @property
    def version(self):
        """USwtSaveGame.Version, the game's SaveVersion when it wrote the save (20 on build 26184573), or None.
        The game doesn't load a save whose Version isn't its own: it starts a new one instead."""
        value = _header_value(self.raw[:self._data_start], "Version", "ByteProperty", 1)
        return None if value is None else value[0]

    def to_bytes(self):
        archive = _encode_archive(self.json_text)
        out = bytearray(self.raw[:self._data_start])
        struct.pack_into("<i", out, self._size_pos, len(archive) + 4)
        struct.pack_into("<i", out, self._count_pos, len(archive))
        out += archive
        out += self.raw[self._data_end:]
        return bytes(out)


def _header_value(head, name, type_name, size):
    """The value of a simple property in the save's header: its tag is the name and the type (FStrings), the
    type's parameter count (0), the value's size (int32) and flags (u8, 0), then the value. None if the
    property isn't there or its tag isn't laid out that way."""
    def fstring(text):
        return struct.pack("<i", len(text) + 1) + text.encode("ascii") + b"\0"
    at = head.find(fstring(name) + fstring(type_name))
    if at < 0:
        return None
    p = at + len(fstring(name) + fstring(type_name))
    if len(head) < p + 9 + size or head[p:p + 9] != struct.pack("<iiB", 0, size, 0):
        return None
    return head[p + 9:p + 9 + size]


def next_hash(previous, when, address):
    """The Hash the game gives the save when it writes it, read from the exe (build 26184573; see
    docs/reverse-engineering.md, "The save"): CityHash64WithSeed of the UTF-8 text "<when>__<address>",
    seeded with the save's previous Hash. `when` is the UTC time of the write (a datetime, to the second),
    `address` the storage manager's address in the game's memory (GameInstance.StorageManager, a
    SwtStorageManager: the writer is its virtual and formats its own `this`), which the game prints with
    %p (16 upper-case hex digits, zero-padded, as the UCRT does). Nothing in it comes from what the save
    holds."""
    text = f"{when:%Y.%m.%d-%H.%M.%S}__{address:016X}"
    return cityhash64_with_seed(text.encode("utf-8"), previous)


def _decode_archive(a):
    """The payload from CompressedData: every archive in it, in order (see the module's docstring). A
    save over 128 KiB is several archives; reading only the first left the payload cut short."""
    raw = bytearray()
    p = 0
    while p < len(a):
        if a[p:p + 8] != ARCHIVE_TAG:
            raise ValueError(f"unexpected save compression layout (no archive tag at byte {p} of {len(a)})")
        (block_size,) = struct.unpack_from("<q", a, p + 8)
        fmt = a[p + 16]
        csize, usize = struct.unpack_from("<qq", a, p + 17)
        if fmt != ZLIB:
            raise ValueError(f"unexpected save compression format {fmt}")
        if block_size <= 0 or usize < 0 or csize < 0:
            raise ValueError("unexpected save compression layout (bad sizes)")
        p += 33
        # One entry per block, as the engine counts them from the summary and the block size.
        blocks = [struct.unpack_from("<qq", a, p + 16 * i) for i in range((usize + block_size - 1) // block_size)]
        p += 16 * len(blocks)
        for c, u in blocks:
            part = zlib.decompress(a[p:p + c])
            if len(part) != u:
                raise ValueError(f"a save block unpacks to {len(part)} bytes, not the {u} its entry says")
            raw += part
            p += c
    outer, length = struct.unpack_from("<II", raw, 0)
    (trailer,) = struct.unpack_from("<I", raw, 8 + length)
    if outer != length + 8 or trailer != length:
        raise ValueError("unexpected save payload framing")
    return bytes((b + 1) & 0xFF for b in raw[8:8 + length]).decode("utf-8")


def _encode_archive(text):
    """The payload as CompressedData, laid out as the game's proxy writes it: an archive of its own for
    each 128 KiB, each with one block. The game reads an archive into a 128 KiB buffer, so one holding
    more than that (the whole payload in several blocks, say) is one it can't load."""
    body = text.encode("utf-8")
    payload = (struct.pack("<II", len(body) + 8, len(body)) + bytes((b - 1) & 0xFF for b in body)
               + struct.pack("<I", len(body)))
    out = bytearray()
    for k in range(0, len(payload), BLOCK):
        part = payload[k:k + BLOCK]
        packed = zlib.compress(part, 9)
        sizes = struct.pack("<qq", len(packed), len(part))   # the summary, and the one block's entry
        out += ARCHIVE_TAG + struct.pack("<q", BLOCK) + bytes([ZLIB]) + sizes + sizes + packed
    return bytes(out)


def write_save(save_dir, save):
    """Write WrcGame.sav and its WrcGame.json mirror."""
    data = save.to_bytes()
    check = SaveGame(data)
    if check.json_text != save.json_text:
        raise RuntimeError("save re-encode check failed; nothing written")
    tmp = os.path.join(save_dir, SAV_NAME + ".wcmods-tmp")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, os.path.join(save_dir, SAV_NAME))
    with open(os.path.join(save_dir, JSON_NAME), "w", encoding="utf-8", newline="") as f:
        f.write(save.json_text)


NO_SAVE = "there's no save to back up yet; start the game once, and get into the forest"
# What each reason a backup is made for says to a player (backup_label).
BACKUP_REASONS = {"first-run": "first safety copy", "studio": "backed up by you", "manual": "backed up by you",
                  "before-restore": "the save you had before a restore", "before-save-edits": "before Apply (save edits)",
                  "agent": "before a test"}


def has_save(save_dir):
    return os.path.isfile(os.path.join(save_dir, SAV_NAME))


def backup(save_dir, backups_root, reason="manual"):
    """Copy the save folder's files to backups/<date>-<time>-<reason>. Returns (that folder, the files).
    Refused (ValueError, NO_SAVE) while there's no save, so no caller leaves an empty backup that would count
    as one."""
    if not has_save(save_dir):
        raise ValueError(NO_SAVE)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(backups_root, f"{stamp}-{reason}")
    n = 2
    while os.path.exists(dest):   # never merge into (and overwrite) an earlier backup
        dest = os.path.join(backups_root, f"{stamp}-{reason}-{n}")
        n += 1
    os.makedirs(dest)
    copied = []
    for fn in os.listdir(save_dir):
        src = os.path.join(save_dir, fn)
        if os.path.isfile(src) and fn != RECORD_NAME:
            shutil.copy2(src, os.path.join(dest, fn))
            copied.append(fn)
    return dest, copied


def list_backups(backups_root):
    """The save backups, oldest first: the folders named <date>-<time>-<reason> (backups/mods holds mods
    that were removed or replaced, which aren't saves)."""
    if not os.path.isdir(backups_root):
        return []
    return sorted(d for d in os.listdir(backups_root)
                  if _backup_time(d) and os.path.isdir(os.path.join(backups_root, d)))


def _backup_time(name):
    """When a backup folder's name says it was made, or None for a name that isn't one (a date that can't
    be, 20261399-250000-..., is no backup's: it's skipped rather than failing the whole list)."""
    m = re.match(r"^(\d{8}-\d{6})-", name)
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def backup_label(name, today=None):
    """A backup's name in words: "Today 15:30, backed up by you", "First safety copy, 27 Oct 2026 09:12"."""
    m = re.match(r"^(\d{8}-\d{6})-(.+?)(?:-\d+)?$", name)
    when = _backup_time(name)
    if not m or not when:
        return name
    today = today or datetime.date.today()
    day = ("Today" if when.date() == today else "Yesterday" if when.date() == today - datetime.timedelta(days=1)
           else f"{when.day} {when.strftime('%b %Y')}")
    said = f"{day} {when.strftime('%H:%M')}"
    why = BACKUP_REASONS.get(m.group(2), m.group(2).replace("-", " "))
    return f"First safety copy, {said}" if m.group(2) == "first-run" else f"{said}, {why}"


def restore(backups_root, name, save_dir):
    """Put a backup's files back in the save folder. Only a backup list_backups() lists: a name that climbs
    out of the backups folder, or names anything else, is no backup."""
    if name not in list_backups(backups_root):
        raise LookupError(f"there's no backup called {name}")
    src = os.path.join(backups_root, name)
    restored = []
    for fn in os.listdir(src):
        if fn == RECORD_NAME or not os.path.isfile(os.path.join(src, fn)):
            continue
        shutil.copy2(os.path.join(src, fn), os.path.join(save_dir, fn))
        restored.append(fn)
    return restored
