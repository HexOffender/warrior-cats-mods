"""Little-endian helpers for Unreal Engine serialization formats."""
import struct


def read_fstring(buf, p):
    """Read an FString at offset p. Returns (text, new_offset)."""
    (n,) = struct.unpack_from("<i", buf, p)
    p += 4
    if n == 0:
        return "", p
    if n < 0:
        end = p - n * 2
        return buf[p:end].decode("utf-16-le").rstrip("\0"), end
    return buf[p:p + n].decode("utf-8").rstrip("\0"), p + n


def write_fstring(text):
    """Serialize an FString: ASCII as UTF-8, anything else as UTF-16 with a negative length."""
    if not text:
        return struct.pack("<i", 0)
    if text.isascii():
        raw = text.encode("ascii") + b"\0"
        return struct.pack("<i", len(raw)) + raw
    raw = text.encode("utf-16-le") + b"\0\0"
    return struct.pack("<i", -(len(raw) // 2)) + raw


def fnv64(data, offset=0):
    """FNV-1a 64 as used by FPakFile::HashPath (basis + seed)."""
    h = (0xCBF29CE484222325 + offset) & 0xFFFFFFFFFFFFFFFF
    for b in data:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def read_name_batch(buf, p):
    """Read an FNameBatch (zen package / container header name map). Returns (names, new_offset)."""
    (count,) = struct.unpack_from("<i", buf, p)
    p += 4
    if count == 0:
        return [], p
    p += 4 + 8 + count * 8  # string bytes, hash version, hashes
    lengths = [struct.unpack_from(">h", buf, p + i * 2)[0] for i in range(count)]
    p += count * 2
    names = []
    for n in lengths:
        if n < 0:
            names.append(buf[p:p - n * 2].decode("utf-16-le"))
            p += -n * 2
        else:
            names.append(buf[p:p + n].decode("utf-8"))
            p += n
    return names, p
