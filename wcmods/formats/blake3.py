"""Minimal pure-Python BLAKE3 (hash mode only), used for IoStore chunk hashes (FIoHash)."""
import struct

_M = 0xFFFFFFFF
IV = (0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19)
PERM = (2, 6, 3, 10, 7, 0, 4, 13, 1, 11, 12, 5, 9, 14, 15, 8)
CHUNK_START, CHUNK_END, PARENT, ROOT = 1, 2, 4, 8
CHUNK_LEN, BLOCK_LEN = 1024, 64


def _g(s, a, b, c, d, x, y):
    s[a] = (s[a] + s[b] + x) & _M
    v = s[d] ^ s[a]; s[d] = ((v >> 16) | (v << 16)) & _M
    s[c] = (s[c] + s[d]) & _M
    v = s[b] ^ s[c]; s[b] = ((v >> 12) | (v << 20)) & _M
    s[a] = (s[a] + s[b] + y) & _M
    v = s[d] ^ s[a]; s[d] = ((v >> 8) | (v << 24)) & _M
    s[c] = (s[c] + s[d]) & _M
    v = s[b] ^ s[c]; s[b] = ((v >> 7) | (v << 25)) & _M


def _compress(cv, words, counter, block_len, flags):
    s = list(cv) + list(IV[:4]) + [counter & _M, (counter >> 32) & _M, block_len, flags]
    m = list(words)
    for r in range(7):
        _g(s, 0, 4, 8, 12, m[0], m[1]); _g(s, 1, 5, 9, 13, m[2], m[3])
        _g(s, 2, 6, 10, 14, m[4], m[5]); _g(s, 3, 7, 11, 15, m[6], m[7])
        _g(s, 0, 5, 10, 15, m[8], m[9]); _g(s, 1, 6, 11, 12, m[10], m[11])
        _g(s, 2, 7, 8, 13, m[12], m[13]); _g(s, 3, 4, 9, 14, m[14], m[15])
        if r < 6:
            m = [m[i] for i in PERM]
    for i in range(8):
        s[i] ^= s[i + 8]
        s[i + 8] ^= cv[i]
    return s


def _words(block):
    return struct.unpack("<16I", block.ljust(BLOCK_LEN, b"\0"))


def _chunk(data, counter, root):
    cv = IV
    blocks = [data[i:i + BLOCK_LEN] for i in range(0, len(data), BLOCK_LEN)] or [b""]
    for j, blk in enumerate(blocks):
        flags = (CHUNK_START if j == 0 else 0)
        last = j == len(blocks) - 1
        if last:
            flags |= CHUNK_END | (ROOT if root else 0)
        out = _compress(cv, _words(blk), counter, len(blk), flags)
        if last:
            return out
        cv = out[:8]


def _node(data, counter, root):
    if len(data) <= CHUNK_LEN:
        return _chunk(data, counter, root)
    chunks = (len(data) + CHUNK_LEN - 1) // CHUNK_LEN
    left_chunks = 1 << ((chunks - 1).bit_length() - 1)
    split = left_chunks * CHUNK_LEN
    left = _node(data[:split], counter, False)[:8]
    right = _node(data[split:], counter + left_chunks, False)[:8]
    return _compress(IV, tuple(left) + tuple(right), 0, BLOCK_LEN, PARENT | (ROOT if root else 0))


def blake3(data, length=32):
    out = _node(bytes(data), 0, True)
    return struct.pack("<16I", *out)[:length]
