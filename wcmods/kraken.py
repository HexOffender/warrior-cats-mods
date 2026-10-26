"""Kraken decompression in pure Python: the Oodle codec the game's pak and IoStore container use.

A port of the Kraken parts of ooz's kraken.cpp (https://github.com/powzix/ooz), Copyright (C) 2016
Powzix, which is free software under the GNU General Public License, version 3 or later. This file
is distributed under the same terms: you can redistribute it and/or modify it under the GPL as
published by the Free Software Foundation, either version 3 of the License, or (at your option)
any later version. It comes WITHOUT ANY WARRANTY; see <https://www.gnu.org/licenses/>.

Only Kraken (decoder type 6) is ported; every compressed block in the game's files is Kraken
(checked over both containers, docs/reverse-engineering.md). Mermaid, Leviathan, LZNA and Bitknit
raise KrakenError. It only decompresses; wcmods' own containers are written uncompressed.

Pure Python runs at a few megabytes a second, a few seconds for the item table or a texture: fine
for an install, slow for `extract "*"`. An oo2core DLL, when one is set in wcmods.json, is used
instead (oodle.py).

Format, as ooz reads it:
  * A 2-byte header in front of every 256 KB of output: byte 0 is 0x8C (bit 7 "restart the
    decoder", bit 6 "stored uncompressed"), byte 1 the decoder type with bit 7 "checksums".
  * A 3-byte quantum header (compressed size, or a memset marker), then the quantum: two 128 KB
    chunks, each either entropy-coded bytes alone or an LZ chunk (literals, commands, offsets and
    lengths as separate entropy-coded arrays, then a copy loop).
  * Entropy coding of an array ("DecodeBytes"): stored, Huffman (three interleaved bit streams, two
    forwards and one backwards), tANS (five states), RLE, or several arrays interleaved by
    intervals ("multi-array"), with recursion.
"""

__all__ = ["decompress", "KrakenError"]

_M32 = 0xFFFFFFFF


class KrakenError(ValueError):
    """The data isn't Kraken, or it's corrupt."""


# 11-bit values with their bits reversed: a Huffman code is read one bit at a time starting at the
# low bit of the stream, so the lookup table is indexed by the reversed code.
_REV11 = [int(format(i, "011b")[::-1], 2) for i in range(2048)]
_CODE_PREFIX_ORG = (0x0, 0x0, 0x2, 0x6, 0xE, 0x1E, 0x3E, 0x7E, 0xFE, 0x1FE, 0x2FE, 0x3FE)


def _rotl32(x, n):
    n &= 31
    return ((x << n) | (x >> (32 - n))) & _M32 if n else x


def _clz32(x):
    """Leading zeros of a 32-bit value; 32 for zero."""
    return 32 - x.bit_length()


# ============================================================================================ bit reader
# ooz's BitReader: a 32-bit window with the next bits at the top, refilled a byte at a time so that at
# least 24 bits are there. `bitpos` is how many bits the window is short of 32 (it goes negative when
# a refill lands more than needed). Bytes past the end read as zero, as in C.

class _Bits:
    __slots__ = ("src", "p", "p_end", "bits", "bitpos")

    def __init__(self, src, p, p_end):
        self.src = src
        self.p = p
        self.p_end = p_end
        self.bits = 0
        self.bitpos = 24

    def refill(self):
        src, p, p_end, bits, bitpos = self.src, self.p, self.p_end, self.bits, self.bitpos
        while bitpos > 0:
            bits |= (src[p] if p < p_end else 0) << bitpos
            bitpos -= 8
            p += 1
        self.p, self.bits, self.bitpos = p, bits & _M32, bitpos

    def refill_backwards(self):
        src, p, p_end, bits, bitpos = self.src, self.p, self.p_end, self.bits, self.bitpos
        while bitpos > 0:
            p -= 1
            bits |= (src[p] if p >= p_end else 0) << bitpos
            bitpos -= 8
        self.p, self.bits, self.bitpos = p, bits & _M32, bitpos

    def read_bit(self):
        self.refill()
        r = self.bits >> 31
        self.bits = (self.bits << 1) & _M32
        self.bitpos += 1
        return r

    def read_bit_norefill(self):
        r = self.bits >> 31
        self.bits = (self.bits << 1) & _M32
        self.bitpos += 1
        return r

    def read_bits_norefill(self, n):
        r = self.bits >> (32 - n)
        self.bits = (self.bits << n) & _M32
        self.bitpos += n
        return r

    def read_bits_norefill_zero(self, n):
        """n may be zero."""
        r = (self.bits >> 1) >> (31 - n)
        self.bits = (self.bits << n) & _M32
        self.bitpos += n
        return r

    def read_more_than_24_bits(self, n):
        if n <= 24:
            rv = self.read_bits_norefill_zero(n)
        else:
            rv = self.read_bits_norefill(24) << (n - 24)
            self.refill()
            rv += self.read_bits_norefill(n - 24)
        self.refill()
        return rv

    def read_more_than_24_bits_b(self, n):
        if n <= 24:
            rv = self.read_bits_norefill_zero(n)
        else:
            rv = self.read_bits_norefill(24) << (n - 24)
            self.refill_backwards()
            rv += self.read_bits_norefill(n - 24)
        self.refill_backwards()
        return rv

    def read_distance(self, v, backwards=False):
        """An offset code parametrized by `v`."""
        bits = self.bits
        if v < 0xF0:
            n = (v >> 4) + 4
            w = _rotl32(bits | 1, n)
            self.bitpos += n
            m = (2 << n) - 1
            self.bits = w & ~m & _M32
            rv = ((w & m) << 4) + (v & 0xF) - 248
        else:
            n = v - 0xF0 + 4
            w = _rotl32(bits | 1, n)
            self.bitpos += n
            m = (2 << n) - 1
            self.bits = w & ~m & _M32
            rv = 8322816 + ((w & m) << 12)
            if backwards:
                self.refill_backwards()
            else:
                self.refill()
            rv += self.bits >> 20
            self.bitpos += 12
            self.bits = (self.bits << 12) & _M32
        if backwards:
            self.refill_backwards()
        else:
            self.refill()
        return rv

    def read_length(self, backwards=False):
        """A length code, or None when it's bad."""
        n = _clz32(self.bits)
        if n > 12:
            return None
        self.bitpos += n
        self.bits = (self.bits << n) & _M32
        if backwards:
            self.refill_backwards()
        else:
            self.refill()
        n += 7
        self.bitpos += n
        rv = (self.bits >> (32 - n)) - 64
        self.bits = (self.bits << n) & _M32
        if backwards:
            self.refill_backwards()
        else:
            self.refill()
        return rv

    def normalized(self):
        """The byte after the last one any consumed bit is in (reading forwards)."""
        return self.p - ((24 - self.bitpos) >> 3)

    def read_fluff(self, num_symbols):
        if num_symbols == 256:
            return 0
        x = 257 - num_symbols
        if x > num_symbols:
            x = num_symbols
        x *= 2
        y = (x - 1).bit_length()   # BSR(x - 1) + 1
        v = self.bits >> (32 - y)
        z = (1 << y) - x
        if (v >> 1) >= z:
            self.bits = (self.bits << y) & _M32
            self.bitpos += y
            return v - z
        self.bits = (self.bits << (y - 1)) & _M32
        self.bitpos += y - 1
        return v >> 1


# ============================================================================================ Golomb-Rice
# ooz's BitReader2: a plain position (byte, bits already used in it), read most significant bit first.

def _golomb_rice_lengths(src, p, p_end, bitpos, count):
    """`count` unary values (zeros before each one bit). Returns (values, p, bitpos)."""
    if p >= p_end:
        raise KrakenError("rice lengths run past the end")
    out = []
    run = 0
    v = src[p] & (255 >> bitpos)
    p += 1
    bit = 7 - bitpos
    while True:
        while bit >= 0:
            if (v >> bit) & 1:
                out.append(run)
                run = 0
                if len(out) == count:
                    # The next bit of this byte is where reading goes on.
                    bitpos = 8 - bit
                    if bitpos == 8:
                        bitpos = 0
                    else:
                        p -= 1
                    return out, p, bitpos
            else:
                run += 1
            bit -= 1
        if p >= p_end:
            raise KrakenError("rice lengths run past the end")
        v = src[p]
        p += 1
        bit = 7


def _golomb_rice_bits(values, src, p, p_end, bitpos, bitcount):
    """Append `bitcount` bits (most significant first) to each value. Returns (p, bitpos)."""
    if bitcount == 0:
        return p, bitpos
    size = len(values)
    bits_required = bitpos + bitcount * size
    if (bits_required + 7) >> 3 > p_end - p:
        raise KrakenError("rice bits run past the end")
    total = int.from_bytes(src[p:p + ((bits_required + 7) >> 3)], "big")
    total_bits = ((bits_required + 7) >> 3) * 8
    shift = total_bits - bitpos
    mask = (1 << bitcount) - 1
    for i in range(size):
        shift -= bitcount
        values[i] = (values[i] << bitcount) | ((total >> shift) & mask)
    return p + (bits_required >> 3), bits_required & 7


def _bits_to_rice(bits):
    """Where a _Bits reader is, as a (byte, bits used) position for the Rice readers."""
    return bits.p - ((24 - bits.bitpos + 7) >> 3), (bits.bitpos - 24) & 7


def _rice_to_bits(bits, p, bitpos):
    """Put a _Bits reader at a Rice position."""
    bits.bitpos = 24
    bits.p = p
    bits.bits = 0
    bits.refill()
    bits.bits = (bits.bits << bitpos) & _M32
    bits.bitpos += bitpos


# ============================================================================================ Huffman
def _convert_to_ranges(num_symbols, P, symlen, bits):
    """[(first symbol, count)] from the fluff lengths `symlen`, or None."""
    num_ranges = P >> 1
    sym_idx = 0
    k = 0
    if P & 1:
        bits.refill()
        v = symlen[k]
        k += 1
        if v >= 8:
            return None
        sym_idx = bits.read_bits_norefill(v + 1) + (1 << (v + 1)) - 1
    syms_used = 0
    ranges = []
    for _ in range(num_ranges):
        bits.refill()
        v = symlen[k]
        if v >= 9:
            return None
        num = bits.read_bits_norefill_zero(v) + (1 << v)
        v = symlen[k + 1]
        if v >= 8:
            return None
        space = bits.read_bits_norefill(v + 1) + (1 << (v + 1)) - 1
        ranges.append((sym_idx, num))
        syms_used += num
        sym_idx += num + space
        k += 2
    if sym_idx >= 256 or syms_used >= num_symbols or sym_idx + num_symbols - syms_used > 256:
        return None
    ranges.append((sym_idx, num_symbols - syms_used))
    return ranges


def _read_code_lengths_old(bits, syms, code_prefix):
    if bits.read_bit_norefill():
        sym = 0
        num_symbols = 0
        avg_bits_x4 = 32
        forced_bits = bits.read_bits_norefill(2)
        thres = 1 << (31 - (20 >> forced_bits))
        skip_zeros = bits.read_bit()
        while True:
            if not skip_zeros:
                if not (bits.bits & 0xFF000000):
                    return -1
                sym += bits.read_bits_norefill(2 * (_clz32(bits.bits) + 1)) - 2 + 1
                if sym >= 256:
                    break
            skip_zeros = False
            bits.refill()
            if not (bits.bits & 0xFF000000):
                return -1
            n = bits.read_bits_norefill(2 * (_clz32(bits.bits) + 1)) - 2 + 1
            if sym + n > 256:
                return -1
            bits.refill()
            num_symbols += n
            for _ in range(n):
                if bits.bits < thres:
                    return -1
                lz = _clz32(bits.bits)
                v = bits.read_bits_norefill(lz + forced_bits + 1) + ((lz - 1) << forced_bits)
                codelen = (-(v & 1) ^ (v >> 1)) + ((avg_bits_x4 + 2) >> 2)
                if codelen < 1 or codelen > 11:
                    return -1
                avg_bits_x4 = codelen + ((3 * avg_bits_x4 + 2) >> 2)
                bits.refill()
                syms[code_prefix[codelen]] = sym
                code_prefix[codelen] += 1
                sym += 1
            if sym == 256:
                break
        return num_symbols if sym == 256 and num_symbols >= 2 else -1
    # Sparse symbol encoding
    num_symbols = bits.read_bits_norefill(8)
    if num_symbols == 0:
        return -1
    if num_symbols == 1:
        syms[0] = bits.read_bits_norefill(8)
    else:
        codelen_bits = bits.read_bits_norefill(3)
        if codelen_bits > 4:
            return -1
        for _ in range(num_symbols):
            bits.refill()
            sym = bits.read_bits_norefill(8)
            codelen = bits.read_bits_norefill_zero(codelen_bits) + 1
            if codelen > 11:
                return -1
            syms[code_prefix[codelen]] = sym
            code_prefix[codelen] += 1
    return num_symbols


def _read_code_lengths_new(bits, syms, code_prefix):
    forced_bits = bits.read_bits_norefill(2)
    num_symbols = bits.read_bits_norefill(8) + 1
    fluff = bits.read_fluff(num_symbols)
    p, bitpos = _bits_to_rice(bits)
    code_len, p, bitpos = _golomb_rice_lengths(bits.src, p, bits.p_end, bitpos, num_symbols + fluff)
    head = code_len[:num_symbols]
    p, bitpos = _golomb_rice_bits(head, bits.src, p, bits.p_end, bitpos, forced_bits)
    _rice_to_bits(bits, p, bitpos)
    running_sum = 0x1E
    for i in range(num_symbols):
        v = head[i]
        v = -(v & 1) ^ (v >> 1)
        c = v + (running_sum >> 2) + 1
        if c < 1 or c > 11:
            return -1
        head[i] = c
        running_sum = (running_sum + v) & _M32
    ranges = _convert_to_ranges(num_symbols, fluff, code_len[num_symbols:], bits)
    if not ranges:
        return -1
    k = 0
    for sym, n in ranges:
        for _ in range(n):
            c = head[k]
            k += 1
            syms[code_prefix[c]] = sym
            code_prefix[c] += 1
            sym += 1
    return num_symbols


def _make_lut(code_prefix, syms):
    """The decoding table, indexed by the next 11 stream bits (low bit first): length << 8 | symbol."""
    lut = [0] * 2048
    rev = _REV11
    currslot = 0
    for i in range(1, 11):
        start = _CODE_PREFIX_ORG[i]
        count = code_prefix[i] - start
        if count:
            stepsize = 1 << (11 - i)
            num_to_set = count << (11 - i)
            if currslot + num_to_set > 2048:
                return None
            tag = i << 8
            for j in range(count):
                e = tag | syms[start + j]
                base = currslot + j * stepsize
                for t in range(base, base + stepsize):
                    lut[rev[t]] = e
            currslot += num_to_set
    start = _CODE_PREFIX_ORG[11]
    count = code_prefix[11] - start
    if count:
        if currslot + count > 2048:
            return None
        for j in range(count):
            lut[rev[currslot + j]] = (11 << 8) | syms[start + j]
        currslot += count
    return lut if currslot == 2048 else None


def _huff_core(src, p, mid, end, out, o, o_end, lut):
    """Three interleaved Huffman streams: [p, mid) forwards, [mid, end) forwards, and backwards from
    `end`. Writes out[o:o_end]. The streams must meet exactly where they should."""
    if p > mid:
        raise KrakenError("huffman streams out of order")
    pf, pm, pb = p, mid, end
    bits_f = bits_m = bits_b = 0
    n_f = n_m = n_b = 0
    from_bytes = int.from_bytes
    while o < o_end:
        if n_f < 11:
            bits_f |= from_bytes(src[pf:pf + 4], "little") << n_f
            pf += 4
            n_f += 32
        e = lut[bits_f & 0x7FF]
        n = e >> 8
        bits_f >>= n
        n_f -= n
        out[o] = e & 0xFF
        o += 1
        if o >= o_end:
            break
        if n_b < 11:
            bits_b |= from_bytes(src[pb - 4:pb], "big") << n_b
            pb -= 4
            n_b += 32
        e = lut[bits_b & 0x7FF]
        n = e >> 8
        bits_b >>= n
        n_b -= n
        out[o] = e & 0xFF
        o += 1
        if o >= o_end:
            break
        if n_m < 11:
            bits_m |= from_bytes(src[pm:pm + 4], "little") << n_m
            pm += 4
            n_m += 32
        e = lut[bits_m & 0x7FF]
        n = e >> 8
        bits_m >>= n
        n_m -= n
        out[o] = e & 0xFF
        o += 1
    if pf - (n_f >> 3) != mid or pb + (n_b >> 3) != pm - (n_m >> 3):
        raise KrakenError("huffman streams don't meet")


def _decode_huffman(src, p, src_size, out, o, output_size, two_halves):
    """ooz's Kraken_DecodeBytes_Type12: Huffman-coded bytes into out[o:o + output_size]."""
    src_end = p + src_size
    bits = _Bits(src, p, src_end)
    bits.refill()
    code_prefix = list(_CODE_PREFIX_ORG)
    syms = [0] * 1280
    if not bits.read_bit_norefill():
        num_syms = _read_code_lengths_old(bits, syms, code_prefix)
    elif not bits.read_bit_norefill():
        num_syms = _read_code_lengths_new(bits, syms, code_prefix)
    else:
        raise KrakenError("bad huffman header")
    if num_syms < 1:
        raise KrakenError("bad huffman code lengths")
    p = bits.normalized()
    if num_syms == 1:
        # ooz returns src - src_end here, which never matches the chunk size: a one-symbol stream
        # is treated as corrupt, the same as the reference.
        raise KrakenError("one-symbol huffman stream")
    lut = _make_lut(code_prefix, syms)
    if lut is None:
        raise KrakenError("bad huffman table")
    if not two_halves:
        if p + 3 > src_end:
            raise KrakenError("huffman stream too short")
        split_mid = src[p] | (src[p + 1] << 8)
        p += 2
        _huff_core(src, p, p + split_mid, src_end, out, o, o + output_size, lut)
    else:
        if p + 6 > src_end:
            raise KrakenError("huffman stream too short")
        half = (output_size + 1) >> 1
        split_mid = src[p] | (src[p + 1] << 8) | (src[p + 2] << 16)
        p += 3
        if split_mid > src_end - p:
            raise KrakenError("bad huffman split")
        src_mid = p + split_mid
        split_left = src[p] | (src[p + 1] << 8)
        p += 2
        if src_mid - p < split_left + 2 or src_end - src_mid < 3:
            raise KrakenError("bad huffman split")
        split_right = src[src_mid] | (src[src_mid + 1] << 8)
        if src_end - (src_mid + 2) < split_right + 2:
            raise KrakenError("bad huffman split")
        _huff_core(src, p, p + split_left, src_mid, out, o, o + half, lut)
        _huff_core(src, src_mid + 2, src_mid + 2 + split_right, src_end, out, o + half, o + output_size, lut)
    return src_size


# ============================================================================================ tANS
def _tans_decode_table(bits, L_bits):
    """(A, B): symbols of weight 1, and (symbol << 16 | weight) for the rest; or None."""
    bits.refill()
    if bits.read_bit_norefill():
        Q = bits.read_bits_norefill(3)
        num_symbols = bits.read_bits_norefill(8) + 1
        if num_symbols < 2:
            return None
        fluff = bits.read_fluff(num_symbols)
        p, bitpos = _bits_to_rice(bits)
        rice, p, bitpos = _golomb_rice_lengths(bits.src, p, bits.p_end, bitpos, fluff + num_symbols)
        _rice_to_bits(bits, p, bitpos)
        ranges = _convert_to_ranges(num_symbols, fluff, rice[num_symbols:], bits)
        if not ranges:
            return None
        bits.refill()
        L = 1 << L_bits
        k = 0
        average = 6
        somesum = 0
        A, B = [], []
        for symbol, num in ranges:
            for _ in range(num):
                bits.refill()
                nextra = Q + rice[k]
                k += 1
                if nextra > 15:
                    return None
                v = bits.read_bits_norefill_zero(nextra) + (1 << nextra) - (1 << Q)
                average_div4 = average >> 2
                limit = 2 * average_div4
                if v <= limit:
                    v = average_div4 + (-(v & 1) ^ (v >> 1))
                if limit > v:
                    limit = v
                v += 1
                average += limit - average_div4
                if v == 1:
                    A.append(symbol)
                else:
                    B.append((symbol << 16) + v)
                somesum += v
                symbol += 1
        if somesum != L:
            return None
        return A, B
    seen = [False] * 256
    L = 1 << L_bits
    count = bits.read_bits_norefill(3) + 1
    bits_per_sym = (L_bits.bit_length() - 1) + 1   # BSR(L_bits) + 1
    max_delta_bits = bits.read_bits_norefill(bits_per_sym)
    if max_delta_bits == 0 or max_delta_bits > L_bits:
        return None
    A, B = [], []
    weight = 0
    total_weights = 0
    for _ in range(count):
        bits.refill()
        sym = bits.read_bits_norefill(8)
        if seen[sym]:
            return None
        delta = bits.read_bits_norefill(max_delta_bits)
        weight += delta
        if weight == 0:
            return None
        seen[sym] = True
        if weight == 1:
            A.append(sym)
        else:
            B.append((sym << 16) + weight)
        total_weights += weight
    bits.refill()
    sym = bits.read_bits_norefill(8)
    if seen[sym]:
        return None
    if L - total_weights < weight or L - total_weights <= 1:
        return None
    B.append((sym << 16) + (L - total_weights))
    A.sort()
    B.sort()
    return A, B


def _tans_init_lut(A, B, L_bits):
    """The decoding table: lut[state] = (symbol, bits to read, mask, next state base)."""
    L = 1 << L_bits
    a_used = len(A)
    slots_left = L - a_used
    sa = slots_left >> 2
    pointers = [0, 0, 0, 0]
    sb = sa + (1 if (slots_left & 3) > 0 else 0)
    pointers[1] = sb
    sb += sa + (1 if (slots_left & 3) > 1 else 0)
    pointers[2] = sb
    sb += sa + (1 if (slots_left & 3) > 2 else 0)
    pointers[3] = sb
    lut = [None] * L
    # Single entries with weight 1
    x1 = (1 << L_bits) - 1
    for i in range(a_used):
        lut[slots_left + i] = (A[i], L_bits, x1, 0)
    weights_sum = 0
    for entry in B:
        weight = entry & 0xFFFF
        symbol = entry >> 16
        if weight > 4:
            sym_bits = weight.bit_length() - 1   # BSR(weight)
            Z = L_bits - sym_bits
            bits_x = Z
            x = (1 << Z) - 1
            w = (L - 1) & (weight << Z)
            what_to_add = 1 << Z
            X = (1 << (sym_bits + 1)) - weight
            for j in range(4):
                dst = pointers[j]
                Y = (weight + ((weights_sum - j - 1) & 3)) >> 2
                if X >= Y:
                    for _ in range(Y):
                        lut[dst] = (symbol, bits_x, x, w)
                        dst += 1
                        w += what_to_add
                    X -= Y
                else:
                    for _ in range(X):
                        lut[dst] = (symbol, bits_x, x, w)
                        dst += 1
                        w += what_to_add
                    Z -= 1
                    what_to_add >>= 1
                    bits_x = Z
                    w = 0
                    x >>= 1
                    for _ in range(Y - X):
                        lut[dst] = (symbol, bits_x, x, w)
                        dst += 1
                        w += what_to_add
                    X = weight
                pointers[j] = dst
        else:
            bitsv = ((1 << weight) - 1) << (weights_sum & 3)
            bitsv |= bitsv >> 4
            ww = weight
            for _ in range(weight):
                idx = (bitsv & -bitsv).bit_length() - 1   # BSF
                bitsv &= bitsv - 1
                dst = pointers[idx]
                pointers[idx] = dst + 1
                weight_bits = ww.bit_length() - 1
                lut[dst] = (symbol, L_bits - weight_bits, (1 << (L_bits - weight_bits)) - 1,
                            (L - 1) & (ww << (L_bits - weight_bits)))
                ww += 1
        weights_sum += weight
    return lut


def _decode_tans(src, p, src_size, out, o, dst_size):
    """ooz's Krak_DecodeTans: tANS-coded bytes into out[o:o + dst_size]."""
    if src_size < 8 or dst_size < 5:
        raise KrakenError("tans stream too short")
    src_end = p + src_size
    br = _Bits(src, p, src_end)
    br.refill()
    if br.read_bit_norefill():
        raise KrakenError("tans reserved bit set")
    L_bits = br.read_bits_norefill(2) + 8
    table = _tans_decode_table(br, L_bits)
    if table is None:
        raise KrakenError("bad tans table")
    p = br.normalized()
    if p >= src_end:
        raise KrakenError("tans stream too short")
    lut = _tans_init_lut(table[0], table[1], L_bits)
    L_mask = (1 << L_bits) - 1
    from_bytes = int.from_bytes
    bits_f = from_bytes(src[p:p + 4], "little")
    pf = p + 4
    bits_b = from_bytes(src[src_end - 4:src_end], "big")
    pb = src_end - 4
    n_f = n_b = 32
    s0 = bits_f & L_mask
    s1 = bits_b & L_mask
    bits_f >>= L_bits
    n_f -= L_bits
    bits_b >>= L_bits
    n_b -= L_bits
    s2 = bits_f & L_mask
    s3 = bits_b & L_mask
    bits_f >>= L_bits
    n_f -= L_bits
    bits_b >>= L_bits
    n_b -= L_bits
    while n_f < 24:
        bits_f |= src[pf] << n_f
        pf += 1
        n_f += 8
    s4 = bits_f & L_mask
    bits_f >>= L_bits
    n_f -= L_bits
    if pf - (n_f >> 3) > pb + (n_b >> 3):
        raise KrakenError("tans streams out of order")

    o_end = o + dst_size - 5
    states = [s0, s1, s2, s3, s4]
    if o < o_end:
        done = False
        while not done:
            # Forwards: states 0 and 1, 2 and 3, then 4; backwards the same.
            for pair in ((0, 1), (2, 3), (4,)):
                if n_f < 24:
                    bits_f |= from_bytes(src[pf:pf + 4], "little") << n_f
                    pf += 4
                    n_f += 32
                for si in pair:
                    sym, bx, x, w = lut[states[si]]
                    out[o] = sym
                    o += 1
                    n_f -= bx
                    states[si] = (bits_f & x) + w
                    bits_f >>= bx
                    if o >= o_end:
                        done = True
                        break
                if done:
                    break
            if done:
                break
            for pair in ((0, 1), (2, 3), (4,)):
                if n_b < 24:
                    bits_b |= from_bytes(src[pb - 4:pb], "big") << n_b
                    pb -= 4
                    n_b += 32
                for si in pair:
                    sym, bx, x, w = lut[states[si]]
                    out[o] = sym
                    o += 1
                    n_b -= bx
                    states[si] = (bits_b & x) + w
                    bits_b >>= bx
                    if o >= o_end:
                        done = True
                        break
                if done:
                    break
    if pf - (n_f >> 3) != pb + (n_b >> 3):
        raise KrakenError("tans streams don't meet")
    if (states[0] | states[1] | states[2] | states[3] | states[4]) & ~0xFF:
        raise KrakenError("bad tans final state")
    out[o_end:o_end + 5] = bytes(states)
    return src_size


# ============================================================================================ RLE
def _decode_rle(src, p, src_size, out, o, dst_size):
    """ooz's Krak_DecodeRLE: run-length coded bytes into out[o:o + dst_size]."""
    if src_size <= 1:
        if src_size != 1:
            raise KrakenError("rle stream too short")
        out[o:o + dst_size] = bytes([src[p]]) * dst_size
        return 1
    src_end = p + src_size
    if src[p]:
        # The first part of the command buffer is itself entropy coded.
        n, data = _decode_bytes(src, p, src_end, 1 << 30)
        cmd = bytearray(data)
        cmd += src[p + n:src_end]
        cmd_ptr, cmd_end = 0, len(cmd)
    else:
        cmd = src
        cmd_ptr, cmd_end = p + 1, src_end
    d, d_end = o, o + dst_size
    rle_byte = 0
    while cmd_ptr < cmd_end:
        c = cmd[cmd_end - 1]
        if c == 0 or c >= 0x30:   # C's unsigned `cmd - 1 >= 0x2f`
            cmd_end -= 1
            to_copy = (-1 - c) & 0xF
            to_rle = c >> 4
            if d_end - d < to_copy + to_rle or cmd_end - cmd_ptr < to_copy:
                raise KrakenError("rle run out of bounds")
            out[d:d + to_copy] = cmd[cmd_ptr:cmd_ptr + to_copy]
            cmd_ptr += to_copy
            d += to_copy
            out[d:d + to_rle] = bytes([rle_byte]) * to_rle
            d += to_rle
        elif c >= 0x10:
            data = (cmd[cmd_end - 2] | (cmd[cmd_end - 1] << 8)) - 4096
            cmd_end -= 2
            to_copy = data & 0x3F
            to_rle = data >> 6
            if d_end - d < to_copy + to_rle or cmd_end - cmd_ptr < to_copy:
                raise KrakenError("rle run out of bounds")
            out[d:d + to_copy] = cmd[cmd_ptr:cmd_ptr + to_copy]
            cmd_ptr += to_copy
            d += to_copy
            out[d:d + to_rle] = bytes([rle_byte]) * to_rle
            d += to_rle
        elif c == 1:
            rle_byte = cmd[cmd_ptr]
            cmd_ptr += 1
            cmd_end -= 1
        elif c >= 9:
            to_rle = ((cmd[cmd_end - 2] | (cmd[cmd_end - 1] << 8)) - 0x8FF) * 128
            cmd_end -= 2
            if d_end - d < to_rle:
                raise KrakenError("rle run out of bounds")
            out[d:d + to_rle] = bytes([rle_byte]) * to_rle
            d += to_rle
        else:
            to_copy = ((cmd[cmd_end - 2] | (cmd[cmd_end - 1] << 8)) - 511) * 64
            cmd_end -= 2
            if cmd_end - cmd_ptr < to_copy or d_end - d < to_copy:
                raise KrakenError("rle run out of bounds")
            out[d:d + to_copy] = cmd[cmd_ptr:cmd_ptr + to_copy]
            d += to_copy
            cmd_ptr += to_copy
    if cmd_end != cmd_ptr or d != d_end:
        raise KrakenError("rle stream doesn't add up")
    return src_size


# ============================================================================================ arrays
def _block_size(src, p, src_end, dest_capacity):
    """The decoded size of the DecodeBytes block at p (ooz's Kraken_GetBlockSize)."""
    if src_end - p < 2:
        raise KrakenError("block header too short")
    chunk_type = (src[p] >> 4) & 7
    if chunk_type == 0:
        if src[p] >= 0x80:
            src_size = ((src[p] << 8) | src[p + 1]) & 0xFFF
            p += 2
        else:
            if src_end - p < 3:
                raise KrakenError("block header too short")
            src_size = (src[p] << 16) | (src[p + 1] << 8) | src[p + 2]
            if src_size & ~0x3FFFF:
                raise KrakenError("reserved bits set")
            p += 3
        if src_size > dest_capacity or src_end - p < src_size:
            raise KrakenError("stored block out of bounds")
        return src_size
    if chunk_type >= 6:
        raise KrakenError("unknown block type")
    if src[p] >= 0x80:
        if src_end - p < 3:
            raise KrakenError("block header too short")
        b = (src[p] << 16) | (src[p + 1] << 8) | src[p + 2]
        src_size = b & 0x3FF
        dst_size = src_size + ((b >> 10) & 0x3FF) + 1
        p += 3
    else:
        if src_end - p < 5:
            raise KrakenError("block header too short")
        b = (src[p + 1] << 24) | (src[p + 2] << 16) | (src[p + 3] << 8) | src[p + 4]
        src_size = b & 0x3FFFF
        dst_size = (((b >> 18) | (src[p] << 14)) & 0x3FFFF) + 1
        if src_size >= dst_size:
            raise KrakenError("bad block sizes")
        p += 5
    if src_end - p < src_size or dst_size > dest_capacity:
        raise KrakenError("block out of bounds")
    return dst_size


def _decode_bytes(src, p, src_end, output_size):
    """One entropy-coded array (ooz's Kraken_DecodeBytes): (bytes of src used, the bytes)."""
    src_org = p
    if src_end - p < 2:
        raise KrakenError("block header too short")
    chunk_type = (src[p] >> 4) & 7
    if chunk_type == 0:
        if src[p] >= 0x80:
            src_size = ((src[p] << 8) | src[p + 1]) & 0xFFF
            p += 2
        else:
            if src_end - p < 3:
                raise KrakenError("block header too short")
            src_size = (src[p] << 16) | (src[p + 1] << 8) | src[p + 2]
            if src_size & ~0x3FFFF:
                raise KrakenError("reserved bits set")
            p += 3
        if src_size > output_size or src_end - p < src_size:
            raise KrakenError("stored block out of bounds")
        return p + src_size - src_org, src[p:p + src_size]
    if src[p] >= 0x80:
        if src_end - p < 3:
            raise KrakenError("block header too short")
        b = (src[p] << 16) | (src[p + 1] << 8) | src[p + 2]
        src_size = b & 0x3FF
        dst_size = src_size + ((b >> 10) & 0x3FF) + 1
        p += 3
    else:
        if src_end - p < 5:
            raise KrakenError("block header too short")
        b = (src[p + 1] << 24) | (src[p + 2] << 16) | (src[p + 3] << 8) | src[p + 4]
        src_size = b & 0x3FFFF
        dst_size = (((b >> 18) | (src[p] << 14)) & 0x3FFFF) + 1
        if src_size >= dst_size:
            raise KrakenError("bad block sizes")
        p += 5
    if src_end - p < src_size or dst_size > output_size:
        raise KrakenError("block out of bounds")
    out = bytearray(dst_size)
    if chunk_type == 2 or chunk_type == 4:
        used = _decode_huffman(src, p, src_size, out, 0, dst_size, chunk_type == 4)
    elif chunk_type == 5:
        used = _decode_recursive(src, p, src_size, out, 0, dst_size)
    elif chunk_type == 3:
        used = _decode_rle(src, p, src_size, out, 0, dst_size)
    elif chunk_type == 1:
        used = _decode_tans(src, p, src_size, out, 0, dst_size)
    else:
        raise KrakenError("unknown block type")
    if used != src_size:
        raise KrakenError("block size doesn't add up")
    return p + src_size - src_org, out


def _decode_recursive(src, p, src_size, out, o, output_size):
    """ooz's Krak_DecodeRecursive: several arrays in a row, or one multi-array."""
    src_org = p
    src_end = p + src_size
    o_end = o + output_size
    if src_size < 6:
        raise KrakenError("recursive block too short")
    n = src[p] & 0x7F
    if n < 2:
        raise KrakenError("bad recursive block")
    if not (src[p] & 0x80):
        p += 1
        for _ in range(n):
            used, data = _decode_bytes(src, p, src_end, o_end - o)
            out[o:o + len(data)] = data
            o += len(data)
            p += used
        if o != o_end:
            raise KrakenError("recursive block doesn't add up")
        return p - src_org
    used, arrays, total = _decode_multi_array(src, p, src_end, o_end - o, 1)
    data = arrays[0]
    out[o:o + len(data)] = data
    if o + len(data) != o_end:
        raise KrakenError("recursive block doesn't add up")
    return used


def _decode_multi_array(src, p, src_end, dst_capacity, array_count):
    """ooz's Kraken_DecodeMultiArray: (bytes of src used, [array bytes], total decoded size)."""
    src_org = p
    if src_end - p < 4:
        raise KrakenError("multi-array too short")
    num_arrays_in_file = src[p]
    p += 1
    if not (num_arrays_in_file & 0x80):
        raise KrakenError("bad multi-array header")
    num_arrays_in_file &= 0x3F
    total_size = 0
    if num_arrays_in_file == 0:
        arrays = []
        for _ in range(array_count):
            used, data = _decode_bytes(src, p, src_end, dst_capacity - total_size)
            arrays.append(data)
            total_size += len(data)
            p += used
        return p - src_org, arrays, total_size
    entropy = []
    for _ in range(num_arrays_in_file):
        used, data = _decode_bytes(src, p, src_end, 1 << 30)
        entropy.append(data)
        total_size += len(data)
        p += used
    if src_end - p < 3:
        raise KrakenError("multi-array too short")
    Q = src[p] | (src[p + 1] << 8)
    p += 2
    num_indexes = _block_size(src, p, src_end, total_size)
    num_lens = num_indexes - array_count
    if num_lens < 1:
        raise KrakenError("bad multi-array index count")
    if Q & 0x8000:
        n, data = _decode_bytes(src, p, src_end, num_indexes)
        if len(data) != num_indexes:
            raise KrakenError("bad multi-array indexes")
        p += n
        interval_lenlog2 = [t >> 4 for t in data]
        interval_indexes = [t & 0xF for t in data]
        num_lens = num_indexes
    else:
        lenlog2_chunksize = num_indexes - array_count
        n, data = _decode_bytes(src, p, src_end, num_indexes)
        if len(data) != num_indexes:
            raise KrakenError("bad multi-array indexes")
        p += n
        interval_indexes = list(data)
        n, data = _decode_bytes(src, p, src_end, lenlog2_chunksize)
        if len(data) != lenlog2_chunksize:
            raise KrakenError("bad multi-array lengths")
        p += n
        interval_lenlog2 = list(data)
        for t in interval_lenlog2:
            if t > 16:
                raise KrakenError("bad multi-array length bits")
    varbits_complen = Q & 0x3FFF
    if src_end - p < varbits_complen:
        raise KrakenError("multi-array too short")
    # The interval lengths: each 2^n plus n bits, read alternately from the front (most significant
    # bit first) and from the back of the var-bits section.
    f = p
    bits_f = 0
    n_f = 0
    b = p + varbits_complen
    bits_b = 0
    n_b = 0
    decoded = [0] * num_lens
    i = 0
    while i + 2 <= num_lens:
        nb = interval_lenlog2[i]
        while n_f < nb:
            bits_f = (bits_f << 8) | src[f]
            f += 1
            n_f += 8
        n_f -= nb
        decoded[i] = (1 << nb) | ((bits_f >> n_f) & ((1 << nb) - 1))
        bits_f &= (1 << n_f) - 1
        nb = interval_lenlog2[i + 1]
        while n_b < nb:
            b -= 1
            bits_b = (bits_b << 8) | src[b]
            n_b += 8
        n_b -= nb
        decoded[i + 1] = (1 << nb) | ((bits_b >> n_b) & ((1 << nb) - 1))
        bits_b &= (1 << n_b) - 1
        i += 2
    if i < num_lens:
        nb = interval_lenlog2[i]
        while n_f < nb:
            bits_f = (bits_f << 8) | src[f]
            f += 1
            n_f += 8
        n_f -= nb
        decoded[i] = (1 << nb) | ((bits_f >> n_f) & ((1 << nb) - 1))
    if interval_indexes[num_indexes - 1]:
        raise KrakenError("bad multi-array end")
    sizes = [len(e) for e in entropy]
    heads = [0] * num_arrays_in_file
    indi = leni = 0
    increment_leni = 1 if (Q & 0x8000) else 0
    arrays = []
    for _ in range(array_count):
        if indi >= num_indexes:
            raise KrakenError("multi-array indexes run out")
        parts = []
        while True:
            source = interval_indexes[indi]
            indi += 1
            if source == 0:
                break
            if source > num_arrays_in_file or leni >= num_lens:
                raise KrakenError("bad multi-array interval")
            cur_len = decoded[leni]
            leni += 1
            k = source - 1
            if cur_len > sizes[k] - heads[k]:
                raise KrakenError("multi-array interval too long")
            parts.append(entropy[k][heads[k]:heads[k] + cur_len])
            heads[k] += cur_len
        leni += increment_leni
        arrays.append(b"".join(parts))
    if indi != num_indexes or leni != num_lens:
        raise KrakenError("multi-array doesn't add up")
    for k in range(num_arrays_in_file):
        if heads[k] != sizes[k]:
            raise KrakenError("multi-array leaves bytes over")
    if sum(len(a) for a in arrays) > dst_capacity:
        raise KrakenError("multi-array too big")
    return p + varbits_complen - src_org, arrays, total_size


# ============================================================================================ LZ
def _unpack_offsets(src, p, src_end, packed_offs, packed_extra, multi_dist_scale, packed_litlen):
    """The offsets and lengths from their packed bytes and the var-bits section [p, src_end)."""
    bits_a = _Bits(src, p, src_end)
    bits_a.refill()
    bits_b = _Bits(src, src_end, p)
    bits_b.refill_backwards()
    if bits_b.bits < 0x2000:
        raise KrakenError("bad length count")
    n = _clz32(bits_b.bits)
    bits_b.bitpos += n
    bits_b.bits = (bits_b.bits << n) & _M32
    bits_b.refill_backwards()
    n += 1
    u32_len_stream_size = (bits_b.bits >> (32 - n)) - 1
    bits_b.bitpos += n
    bits_b.bits = (bits_b.bits << n) & _M32
    bits_b.refill_backwards()

    offs = []
    count = len(packed_offs)
    if multi_dist_scale == 0:
        i = 0
        while i < count:
            offs.append(-bits_a.read_distance(packed_offs[i]))
            i += 1
            if i == count:
                break
            offs.append(-bits_b.read_distance(packed_offs[i], backwards=True))
            i += 1
    else:
        i = 0
        while i < count:
            cmd = packed_offs[i]
            i += 1
            if (cmd >> 3) > 26:
                raise KrakenError("bad offset code")
            o = ((8 + (cmd & 7)) << (cmd >> 3)) | bits_a.read_more_than_24_bits(cmd >> 3)
            offs.append(8 - o)
            if i == count:
                break
            cmd = packed_offs[i]
            i += 1
            if (cmd >> 3) > 26:
                raise KrakenError("bad offset code")
            o = ((8 + (cmd & 7)) << (cmd >> 3)) | bits_b.read_more_than_24_bits_b(cmd >> 3)
            offs.append(8 - o)
        if multi_dist_scale != 1:
            offs = [multi_dist_scale * v - packed_extra[k] for k, v in enumerate(offs)]
    if u32_len_stream_size > 512:
        raise KrakenError("too many long lengths")
    u32_lens = []
    i = 0
    while i + 1 < u32_len_stream_size:
        v = bits_a.read_length()
        if v is None:
            raise KrakenError("bad length code")
        u32_lens.append(v)
        v = bits_b.read_length(backwards=True)
        if v is None:
            raise KrakenError("bad length code")
        u32_lens.append(v)
        i += 2
    if i < u32_len_stream_size:
        v = bits_a.read_length()
        if v is None:
            raise KrakenError("bad length code")
        u32_lens.append(v)
    if bits_a.p - ((24 - bits_a.bitpos) >> 3) != bits_b.p + ((24 - bits_b.bitpos) >> 3):
        raise KrakenError("offset streams don't meet")
    lens = []
    k = 0
    for v in packed_litlen:
        if v == 255:
            if k >= len(u32_lens):
                raise KrakenError("long lengths run out")
            v = u32_lens[k] + 255
            k += 1
        lens.append(v + 3)
    if k != len(u32_lens):
        raise KrakenError("long lengths left over")
    return offs, lens


def _read_lz_table(mode, src, p, src_end, out, d, dst_size, offset):
    """The streams of one LZ chunk: (literals, commands, offsets, lengths)."""
    if mode > 1:
        raise KrakenError("unknown lz mode")
    if src_end - p < 13:
        raise KrakenError("lz chunk too short")
    if offset == 0:
        out[d:d + 8] = src[p:p + 8]
        p += 8
    if src[p] & 0x80:
        raise KrakenError("lz excess bytes aren't supported")
    n, lit = _decode_bytes(src, p, src_end, dst_size)
    p += n
    n, cmd = _decode_bytes(src, p, src_end, dst_size)
    p += n
    if src_end - p < 3:
        raise KrakenError("lz chunk too short")
    offs_scaling = 0
    packed_extra = None
    if src[p] & 0x80:
        offs_scaling = src[p] - 127
        p += 1
        n, packed_offs = _decode_bytes(src, p, src_end, len(cmd))
        p += n
        if offs_scaling != 1:
            n, packed_extra = _decode_bytes(src, p, src_end, len(packed_offs))
            if len(packed_extra) != len(packed_offs):
                raise KrakenError("bad offset extra bytes")
            p += n
    else:
        n, packed_offs = _decode_bytes(src, p, src_end, len(cmd))
        p += n
    n, packed_len = _decode_bytes(src, p, src_end, dst_size >> 2)
    p += n
    offs, lens = _unpack_offsets(src, p, src_end, packed_offs, packed_extra, offs_scaling, packed_len)
    return lit, cmd, offs, lens


def _process_lz_runs(mode, out, d, dst_size, offset, lit, cmd, offs, lens):
    """The copy loop (ooz's Kraken_ProcessLzRuns): literals and matches into out[d:d + dst_size]."""
    d_end = d + dst_size
    if offset == 0:
        d += 8
    lit_len = len(lit)
    l = 0
    oi = li = 0
    n_offs, n_lens = len(offs), len(lens)
    recent = [0, 0, 0, -8, -8, -8, 0]
    last_offset = -8
    delta = mode == 0
    for f in cmd:
        litlen = f & 3
        offs_index = f >> 6
        matchlen = (f >> 2) & 0xF
        if litlen == 3:
            if li >= n_lens:
                raise KrakenError("lengths run out")
            litlen = lens[li]
            li += 1
        if litlen:
            if delta:
                # Each literal is added to the byte `last_offset` back.
                rem = litlen
                while rem:
                    c = -last_offset
                    if c > rem:
                        c = rem
                    s = d + last_offset
                    out[d:d + c] = bytes([(a + b) & 0xFF for a, b in zip(lit[l:l + c], out[s:s + c])])
                    d += c
                    l += c
                    rem -= c
            else:
                out[d:d + litlen] = lit[l:l + litlen]
                d += litlen
                l += litlen
        if offs_index == 3:
            if oi >= n_offs:
                raise KrakenError("offsets run out")
            recent[6] = offs[oi]
            oi += 1
        off = recent[offs_index + 3]
        recent[offs_index + 3] = recent[offs_index + 2]
        recent[offs_index + 2] = recent[offs_index + 1]
        recent[offs_index + 1] = recent[offs_index]
        recent[3] = off
        last_offset = off
        if off < -d or off >= 0:
            raise KrakenError("match offset out of bounds")
        if matchlen != 15:
            matchlen += 2
        else:
            if li >= n_lens:
                raise KrakenError("lengths run out")
            matchlen = 14 + lens[li]
            li += 1
            if matchlen > d_end - d:
                raise KrakenError("match length out of bounds")
        if -off >= matchlen:
            out[d:d + matchlen] = out[d + off:d + off + matchlen]
            d += matchlen
        else:
            rem = matchlen
            c = -off
            while rem:
                if c > rem:
                    c = rem
                out[d:d + c] = out[d + off:d + off + c]
                d += c
                rem -= c
    if oi != n_offs or li != n_lens:
        raise KrakenError("lz streams don't add up")
    final_len = d_end - d
    if final_len != lit_len - l:
        raise KrakenError("literals don't add up")
    if final_len:
        if delta:
            rem = final_len
            while rem:
                c = -last_offset
                if c > rem:
                    c = rem
                s = d + last_offset
                out[d:d + c] = bytes([(a + b) & 0xFF for a, b in zip(lit[l:l + c], out[s:s + c])])
                d += c
                l += c
                rem -= c
        else:
            out[d:d_end] = lit[l:l + final_len]


def _decode_quantum(src, p, src_end, out, d, d_end):
    """One 256 KB quantum (two 128 KB chunks) into out[d:d_end]. Returns the bytes of src used."""
    src_in = p
    while d_end - d:
        dst_count = d_end - d
        if dst_count > 0x20000:
            dst_count = 0x20000
        if src_end - p < 4:
            raise KrakenError("quantum too short")
        chunkhdr = src[p + 2] | (src[p + 1] << 8) | (src[p] << 16)
        if not (chunkhdr & 0x800000):
            # Entropy coded bytes, no matches.
            src_used, data = _decode_bytes(src, p, src_end, dst_count)
            if len(data) != dst_count:
                raise KrakenError("chunk size doesn't add up")
            out[d:d + dst_count] = data
        else:
            p += 3
            src_used = chunkhdr & 0x7FFFF
            mode = (chunkhdr >> 19) & 0xF
            if src_end - p < src_used:
                raise KrakenError("chunk too short")
            if src_used < dst_count:
                offset = d
                lit, cmd, offs, lens = _read_lz_table(mode, src, p, p + src_used, out, d, dst_count, offset)
                _process_lz_runs(mode, out, d, dst_count, offset, lit, cmd, offs, lens)
            elif src_used > dst_count or mode != 0:
                raise KrakenError("bad chunk header")
            else:
                out[d:d + dst_count] = src[p:p + dst_count]
        p += src_used
        d += dst_count
    return p - src_in


# ============================================================================================ top level
def decompress(src, dst_len):
    """Decompress `src` (bytes) into exactly `dst_len` bytes. KrakenError when it isn't Kraken data
    or doesn't decode to that size."""
    src = bytes(src) + bytes(16)   # the readers may look a few bytes past the end, like ooz does
    src_len = len(src) - 16
    out = bytearray(dst_len)
    p = 0
    offset = 0
    decoder_type = None
    uncompressed = False
    use_checksums = False
    while dst_len - offset:
        if (offset & 0x3FFFF) == 0:
            if src_len - p < 2:
                raise KrakenError("header too short")
            b = src[p]
            if (b & 0xF) != 0xC or ((b >> 4) & 3) != 0:
                raise KrakenError("not an Oodle LZ block")
            uncompressed = bool((b >> 6) & 1)
            b = src[p + 1]
            decoder_type = b & 0x7F
            use_checksums = bool(b >> 7)
            if decoder_type != 6:
                name = {5: "LZNA", 10: "Mermaid/Selkie", 11: "Bitknit", 12: "Leviathan"}.get(decoder_type)
                raise KrakenError(f"only Kraken is supported, not {name or f'decoder {decoder_type}'}")
            p += 2
        dst_bytes_left = min(0x40000, dst_len - offset)
        if uncompressed:
            if src_len - p < dst_bytes_left:
                raise KrakenError("stored block too short")
            out[offset:offset + dst_bytes_left] = src[p:p + dst_bytes_left]
            p += dst_bytes_left
            offset += dst_bytes_left
            continue
        # Quantum header
        v = (src[p] << 16) | (src[p + 1] << 8) | src[p + 2]
        size = v & 0x3FFFF
        if size != 0x3FFFF:
            compressed_size = size + 1
            p += 6 if use_checksums else 3
            fill = None
        elif (v >> 18) == 1:
            fill = src[p + 3]
            compressed_size = 0
            p += 4
        else:
            raise KrakenError("bad quantum header")
        if p > src_len:
            raise KrakenError("quantum header too short")
        if src_len - p < compressed_size:
            raise KrakenError("quantum too short")
        if compressed_size > dst_bytes_left:
            raise KrakenError("quantum bigger than its output")
        if compressed_size == 0:
            out[offset:offset + dst_bytes_left] = bytes([fill]) * dst_bytes_left
            offset += dst_bytes_left
            continue
        if use_checksums:
            raise KrakenError("checksums aren't supported")   # ooz doesn't compute them either
        if compressed_size == dst_bytes_left:
            out[offset:offset + dst_bytes_left] = src[p:p + dst_bytes_left]
            p += dst_bytes_left
            offset += dst_bytes_left
            continue
        n = _decode_quantum(src, p, p + compressed_size, out, offset, offset + dst_bytes_left)
        if n != compressed_size:
            raise KrakenError("quantum size doesn't add up")
        p += n
        offset += dst_bytes_left
    if p != src_len:
        raise KrakenError("input left over")
    return bytes(out)
