"""CityHash64 (version 1.1), which Unreal uses for the hashes in a package's name map.

A Python port of Google's CityHash (https://github.com/google/cityhash, src/city.cc):

    Copyright (c) 2011 Google, Inc.

    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
    associated documentation files (the "Software"), to deal in the Software without restriction,
    including without limitation the rights to use, copy, modify, merge, publish, distribute,
    sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all copies or
    substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
    NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES
    OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
    CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import struct

_M = 0xFFFFFFFFFFFFFFFF
K0, K1, K2 = 0xC3A5C85C97CB3127, 0xB492B66FBE98F273, 0x9AE16A3B2F90404F
_KMUL = 0x9DDFEA08EB382D69


def _f64(s, i):
    return struct.unpack_from("<Q", s, i)[0]


def _f32(s, i):
    return struct.unpack_from("<I", s, i)[0]


def _rot(v, n):
    return v if n == 0 else ((v >> n) | (v << (64 - n))) & _M


def _smix(v):
    return v ^ (v >> 47)


def _bswap(v):
    return int.from_bytes(v.to_bytes(8, "little"), "big")


def _len16(u, v, mul=_KMUL):
    a = ((u ^ v) * mul) & _M
    a ^= a >> 47
    b = ((v ^ a) * mul) & _M
    b ^= b >> 47
    return (b * mul) & _M


def _len0to16(s):
    n = len(s)
    if n >= 8:
        mul = (K2 + n * 2) & _M
        a = (_f64(s, 0) + K2) & _M
        b = _f64(s, n - 8)
        c = (_rot(b, 37) * mul + a) & _M
        d = ((_rot(a, 25) + b) * mul) & _M
        return _len16(c, d, mul)
    if n >= 4:
        mul = (K2 + n * 2) & _M
        return _len16((n + (_f32(s, 0) << 3)) & _M, _f32(s, n - 4), mul)
    if n > 0:
        y = s[0] + (s[n >> 1] << 8)
        z = n + (s[n - 1] << 2)
        return (_smix(((y * K2) ^ (z * K0)) & _M) * K2) & _M
    return K2


def _len17to32(s):
    n = len(s)
    mul = (K2 + n * 2) & _M
    a = (_f64(s, 0) * K1) & _M
    b = _f64(s, 8)
    c = (_f64(s, n - 8) * mul) & _M
    d = (_f64(s, n - 16) * K2) & _M
    return _len16((_rot((a + b) & _M, 43) + _rot(c, 30) + d) & _M,
                  (a + _rot((b + K2) & _M, 18) + c) & _M, mul)


def _len33to64(s):
    n = len(s)
    mul = (K2 + n * 2) & _M
    a = (_f64(s, 0) * K2) & _M
    b = _f64(s, 8)
    c = _f64(s, n - 24)
    d = _f64(s, n - 32)
    e = (_f64(s, 16) * K2) & _M
    f = (_f64(s, 24) * 9) & _M
    g = _f64(s, n - 8)
    h = (_f64(s, n - 16) * mul) & _M
    u = (_rot((a + g) & _M, 43) + (_rot(b, 30) + c) * 9) & _M
    v = (((a + g) ^ d) + f + 1) & _M
    w = (_bswap(((u + v) * mul) & _M) + h) & _M
    x = (_rot((e + f) & _M, 42) + c) & _M
    y = ((_bswap(((v + w) * mul) & _M) + g) * mul) & _M
    z = (e + f + c) & _M
    a = (_bswap(((x + z) * mul + y) & _M) + b) & _M
    b = (_smix(((z + a) * mul + d + h) & _M) * mul) & _M
    return (b + x) & _M


def _weak(s, i, a, b):
    w, x, y, z = _f64(s, i), _f64(s, i + 8), _f64(s, i + 16), _f64(s, i + 24)
    a = (a + w) & _M
    b = _rot((b + a + z) & _M, 21)
    c = a
    a = (a + x + y) & _M
    b = (b + _rot(a, 44)) & _M
    return (a + z) & _M, (b + c) & _M


def cityhash64(s):
    """CityHash64 of bytes."""
    n = len(s)
    if n <= 16:
        return _len0to16(s)
    if n <= 32:
        return _len17to32(s)
    if n <= 64:
        return _len33to64(s)
    x = _f64(s, n - 40)
    y = (_f64(s, n - 16) + _f64(s, n - 56)) & _M
    z = _len16((_f64(s, n - 48) + n) & _M, _f64(s, n - 24))
    v = _weak(s, n - 64, n, z)
    w = _weak(s, n - 32, (y + K1) & _M, x)
    x = (x * K1 + _f64(s, 0)) & _M
    left = (n - 1) & ~63
    i = 0
    while True:
        x = (_rot((x + y + v[0] + _f64(s, i + 8)) & _M, 37) * K1) & _M
        y = (_rot((y + v[1] + _f64(s, i + 48)) & _M, 42) * K1) & _M
        x ^= w[1]
        y = (y + v[0] + _f64(s, i + 40)) & _M
        z = (_rot((z + w[0]) & _M, 33) * K1) & _M
        v = _weak(s, i, (v[1] * K1) & _M, (x + w[0]) & _M)
        w = _weak(s, i + 32, (z + w[1]) & _M, (y + _f64(s, i + 16)) & _M)
        z, x = x, z
        i += 64
        left -= 64
        if left == 0:
            break
    return _len16((_len16(v[0], w[0]) + _smix(y) * K1 + z) & _M, (_len16(v[1], w[1]) + x) & _M)


def name_hash(name):
    """The hash a package's name map stores for an ASCII name: CityHash64 of it in lower case."""
    return cityhash64(name.lower().encode("ascii"))
