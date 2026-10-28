"""WrcGame.sav codec and save backups.

WrcGame.sav is a GVAS file whose SwtSaveGame object holds Hash, GamerId, Version, saveSlots
and CompressedData. CompressedData is what Unreal's FArchiveSaveCompressedProxy writes: one
compressed archive after another, each holding the next 128 KiB of the payload (the proxy
compresses its buffer as an archive of its own each time it fills, so a new save is one archive
and a long-played one is several). An archive is an 8-byte tag, the block size (128 KiB), a
compressor byte (3: zlib), a summary (compressed and uncompressed sizes), one entry per block (the
same two sizes), then the zlib blocks. The payload is [u32 len+8][u32 len][JSON bytes, each minus
1][u32 len]. WrcGame.json next to it is the same JSON in plain text.

Edits are made to the JSON text in place so the game's own formatting is preserved.
"""
import datetime
import os
import re
import shutil
import struct
import zlib

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

    def to_bytes(self):
        archive = _encode_archive(self.json_text)
        out = bytearray(self.raw[:self._data_start])
        struct.pack_into("<i", out, self._size_pos, len(archive) + 4)
        struct.pack_into("<i", out, self._count_pos, len(archive))
        out += archive
        out += self.raw[self._data_end:]
        return bytes(out)


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


def backup(save_dir, backups_root, reason="manual"):
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
                  if re.match(r"^\d{8}-\d{6}-", d) and os.path.isdir(os.path.join(backups_root, d)))


def restore(backups_root, name, save_dir):
    src = os.path.join(backups_root, name)
    if not os.path.isdir(src):
        raise FileNotFoundError(f"no backup named {name}")
    restored = []
    for fn in os.listdir(src):
        if fn == RECORD_NAME or not os.path.isfile(os.path.join(src, fn)):
            continue
        shutil.copy2(os.path.join(src, fn), os.path.join(save_dir, fn))
        restored.append(fn)
    return restored
