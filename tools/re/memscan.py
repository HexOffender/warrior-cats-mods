"""Read-only scan of the running game's memory (ReadProcessMemory) for byte patterns.

usage: memscan.py <process name or pid> <label>=<hex> ... [--context N] [--max M] [--old]
Prints every hit with N bytes of context either side (inside the hit's region), and the region it's in.
--old also runs the scan from before 2026-10-28 (scan_with_old()), and marks each hit it missed.

Each committed, readable region is read in chunks that stay inside it, with the last len(pattern) - 1
bytes searched in front of the next chunk, so a pattern across two chunks, or across two regions that
touch, is found, once. Before 2026-10-28 each chunk was read 64 bytes past its end, and a read that ran
into unreadable memory came back empty, so the last chunk of a region followed by unreadable memory
(up to 16 MB: all of any region of 16 MB or less) was never searched. "No other hits" from memscan
before then is worth repeating. scan() is the search itself, on any list of regions and any read
function; Proc is the Windows part.
"""
import ctypes
import sys

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}  # R, RW, WC, XR, XRW, XWC
USER_END = 0x7FFFFFFFFFFF


def scan(regions, read, patterns, chunk=16 << 20):
    """Every place each pattern is found: {label: [(address, base, size, type, protect)]}, the last four
    being the region the hit starts in (as `regions` gave it), in address order.

    regions: (base, size, type, protect) of each readable region, in address order (Proc.regions());
    read(address, n): the n bytes there, or fewer when some can't be read (Proc.read).
    A chunk is never read past its region's end. The last len(pattern) - 1 bytes searched go in front of
    the next chunk, also into the next region when it starts where this one ends, so a pattern across
    the seam is found, and reported once. Nothing is joined across a gap or after a short read."""
    if any(not p for p in patterns.values()):
        raise ValueError("an empty pattern matches everywhere")
    if chunk < 1:
        raise ValueError("chunk must be at least one byte")
    hits = {label: [] for label in patterns}
    keep = max((len(p) for p in patterns.values()), default=1) - 1
    tail, tail_end, held = b"", None, []   # the bytes carried over, the address they end at, the regions they're in
    for region in regions:
        base, size = region[0], region[1]
        if base != tail_end:   # a gap (or the first region): nothing to join
            tail, held = b"", []
        held.append(region)
        off = 0
        while off < size:
            n = min(chunk, size - off)
            data = read(base + off, n)[:n]
            buf, start = tail + data, base + off - len(tail)
            for label, pat in patterns.items():
                i = buf.find(pat)
                while i >= 0:
                    if i + len(pat) > len(tail):   # one wholly in the tail was found with the bytes before
                        at = start + i
                        hits[label].append((at,) + tuple(next(r for r in reversed(held) if r[0] <= at)))
                    i = buf.find(pat, i + 1)
            off += n
            if len(data) < n:   # the rest of this chunk couldn't be read: start afresh after it
                tail, tail_end, held = b"", None, [region]
                continue
            tail = buf[-keep:] if keep else b""
            tail_end = base + off
            held = [r for r in held if r is region or r[0] + r[1] > tail_end - len(tail)]
    for found in hits.values():
        found.sort()
    return hits


def scan_with_old(regions, read, patterns, chunk=16 << 20):
    """scan(), with the scan from before 2026-10-28 run beside it on the same chunks, to show the fix on a
    live process. Right before scan() reads a chunk, it is read the old way: 64 bytes past its end, and
    nothing at all when that read fails (ReadProcessMemory fails a read that runs into unreadable memory,
    and the old read() then returned nothing). The two reads come back to back, so memory changing
    between them is unlikely.
    Returns (hits, old, empty): scan()'s hits; {label: [address]}, what the old scan found (a pattern
    starting in the chunk); and [(address, size)] of each chunk the old read came back empty."""
    old = {label: [] for label in patterns}
    empty = []

    def both(addr, n):
        data = read(addr, n + 64)
        if len(data) < n + 64:
            data = b""
            empty.append((addr, n))
        for label, pat in patterns.items():
            i = data.find(pat)
            while 0 <= i < n:
                old[label].append(addr + i)
                i = data.find(pat, i + 1)
        return read(addr, n)

    hits = scan(regions, both, patterns, chunk)
    return hits, {label: sorted(found) for label, found in old.items()}, empty


_k32 = None


def kernel32():
    """kernel32 with the signatures memscan calls (Windows only; loaded on first use, so scan() can be
    imported and tested without it)."""
    global _k32
    if _k32 is None:
        import ctypes.wintypes as wt
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wt.HANDLE
        k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
        k32.VirtualQueryEx.restype = ctypes.c_size_t
        k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.POINTER(ctypes.c_size_t)]
        k32.ReadProcessMemory.restype = wt.BOOL
        _k32 = k32
    return _k32


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong), ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", ctypes.c_uint32), ("__a", ctypes.c_uint32), ("RegionSize", ctypes.c_ulonglong),
                ("State", ctypes.c_uint32), ("Protect", ctypes.c_uint32), ("Type", ctypes.c_uint32), ("__b", ctypes.c_uint32)]


def find_pid(name):
    """The pid of the first process whose image name starts with `name`; a number is taken as a pid."""
    if name.isdigit():
        return int(name)
    import subprocess
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if parts and parts[0].lower().startswith(name.lower()):
            return int(parts[1])
    return None


class Proc:
    def __init__(self, pid):
        self.k32 = kernel32()
        self.h = self.k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not self.h:
            raise OSError(f"OpenProcess failed: {ctypes.get_last_error()}")

    def regions(self):
        addr, mbi = 0, MBI()
        while self.k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            if mbi.State == MEM_COMMIT and (mbi.Protect & 0xFF) in READABLE and not mbi.Protect & PAGE_GUARD:
                yield mbi.BaseAddress, mbi.RegionSize, mbi.Type, mbi.Protect
            addr = mbi.BaseAddress + mbi.RegionSize
            if addr >= USER_END:
                break

    def read(self, addr, size):
        """The bytes at addr, or fewer. A read that runs into unreadable memory fails with
        ERROR_PARTIAL_COPY (299) and reports copying only whole 56 KB (0xE000) blocks: nothing at all when
        the readable part is shorter (measured on a test process, Windows 11 build 26200, 2026-10-28).
        What it reports is returned; scan() never reads past a region's end, so it only cuts short the
        context printed around a hit."""
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        self.k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
        return buf.raw[:got.value]

    def scan(self, patterns, chunk=16 << 20):
        return scan(self.regions(), self.read, patterns, chunk)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    ctx, mx, with_old = 64, 20, False
    patterns = {}
    for i, a in enumerate(args[1:], 1):
        if a == "--context":
            ctx = int(args[i + 1])
        elif a == "--max":
            mx = int(args[i + 1])
        elif a == "--old":
            with_old = True
        elif "=" in a:
            label, hx = a.split("=", 1)
            patterns[label] = bytes.fromhex(hx)
    if not args or not patterns or not all(patterns.values()):
        sys.exit(__doc__)
    name = args[0]
    pid = find_pid(name)
    if not pid:
        sys.exit(f"{name} isn't running")
    p = Proc(pid)
    print("pid", pid)
    old, empty = None, []
    if with_old:
        regions = list(p.regions())
        hits, old, empty = scan_with_old(regions, p.read, patterns)
        old = {label: set(found) for label, found in old.items()}
        print(f"the old scan (before 2026-10-28) read {len(empty)} chunk(s) as empty, over {len(regions)} "
              f"readable regions")
    else:
        hits = p.scan(patterns)

    def by_old(addr, label):
        if addr in old[label]:
            return "found"
        return "blind" if any(a <= addr < a + n for a, n in empty) else "missed"

    for label, lst in hits.items():
        line = f"== {label}: {len(lst)} hit(s)"
        if with_old:
            says = [by_old(h[0], label) for h in lst]
            only_old = old[label] - {h[0] for h in lst}
            line += (f": {says.count('found')} the old scan found too, {says.count('blind')} only in chunks it read"
                     f" as empty, {says.count('missed')} it missed otherwise; {len(only_old)} only it found")
        print(line)
        for addr, base, size, typ, prot in lst[:mx]:
            mark = {"found": "  (old: found)", "blind": "  (old: missed, in a chunk it read as empty)",
                    "missed": "  (old: MISSED)"}[by_old(addr, label)] if with_old else ""
            print(f"  @{addr:#x} region {base:#x}+{size:#x} type {typ:#x} prot {prot:#x}{mark}")
            if ctx:
                lo = max(addr - ctx, base)   # inside the hit's region: a read past it can come back empty
                data = p.read(lo, min(addr + ctx, base + size) - lo)
                for row in range(0, len(data), 16):
                    seg = data[row:row + 16]
                    print(f"    {lo + row:#x}: {seg.hex(' ')}  {''.join(chr(b) if 32 <= b < 127 else '.' for b in seg)}")


if __name__ == "__main__":
    main()
