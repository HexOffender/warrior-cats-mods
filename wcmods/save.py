"""WrcGame.sav codec and save backups.

WrcGame.sav is a GVAS file whose SwtSaveGame object holds Hash, GamerId, Version, saveSlots
and CompressedData. CompressedData is an Unreal compressed archive (zlib, 128 KiB blocks)
wrapping [u32 len+8][u32 len][JSON bytes, each minus 1][u32 len]. WrcGame.json next to it is
the same JSON in plain text.

Edits are made to the JSON text in place so the game's own formatting is preserved.
"""
import datetime
import os
import re
import shutil
import struct
import zlib

ARCHIVE_TAG = b"\xc1\x83\x2a\x9e\x22\x22\x22\x22"
SAV_NAME, JSON_NAME = "WrcGame.sav", "WrcGame.json"


class SaveGame:
    def __init__(self, raw):
        self.raw = bytes(raw)
        name = self.raw.find(b"CompressedData\0")
        if not self.raw.startswith(b"GVAS") or name < 0:
            raise ValueError("not a Warrior Cats save (no CompressedData property)")
        tag = self.raw.find(ARCHIVE_TAG, name)
        # property tag: ... size(int32) flags(u8) | array count(int32) | archive
        self._size_pos = tag - 9
        self._count_pos = tag - 4
        (count,) = struct.unpack_from("<i", self.raw, self._count_pos)
        (size,) = struct.unpack_from("<i", self.raw, self._size_pos)
        if size != count + 4:
            raise ValueError("unexpected CompressedData layout")
        self._data_start = tag
        self._data_end = tag + count
        self.json_text = _decode_archive(self.raw[tag:tag + count])

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
    block_size, = struct.unpack_from("<q", a, 8)
    fmt = a[16]
    csize, usize = struct.unpack_from("<qq", a, 17)
    if fmt != 3:
        raise ValueError(f"unexpected save compression format {fmt}")
    p = 33
    chunks = []
    total = 0
    while total < usize:
        c, u = struct.unpack_from("<qq", a, p)
        chunks.append((c, u))
        total += u
        p += 16
    raw = bytearray()
    for c, u in chunks:
        raw += zlib.decompress(a[p:p + c])
        p += c
    outer, length = struct.unpack_from("<II", raw, 0)
    (trailer,) = struct.unpack_from("<I", raw, 8 + length)
    if outer != length + 8 or trailer != length:
        raise ValueError("unexpected save payload framing")
    return bytes((b + 1) & 0xFF for b in raw[8:8 + length]).decode("utf-8")


def _encode_archive(text):
    body = text.encode("utf-8")
    payload = struct.pack("<II", len(body) + 8, len(body)) + bytes((b - 1) & 0xFF for b in body) \
        + struct.pack("<I", len(body))
    block = 0x20000
    pieces = []
    for k in range(0, len(payload), block):
        part = payload[k:k + block]
        pieces.append((zlib.compress(part, 9), len(part)))
    out = bytearray(ARCHIVE_TAG)
    out += struct.pack("<q", block) + b"\x03"
    out += struct.pack("<qq", sum(len(c) for c, _ in pieces), len(payload))
    for c, u in pieces:
        out += struct.pack("<qq", len(c), u)
    for c, _ in pieces:
        out += c
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
        if os.path.isfile(src):
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
        shutil.copy2(os.path.join(src, fn), os.path.join(save_dir, fn))
        restored.append(fn)
    return restored
