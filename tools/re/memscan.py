"""Read-only scan of the running game's memory (ReadProcessMemory) for byte patterns.

usage: memscan.py <process name> <label>=<hex> ... [--context N] [--max M]
Prints every hit with N bytes of context either side, and the region it's in.
"""
import ctypes
import ctypes.wintypes as wt
import sys

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}  # R, RW, WC, XR, XRW, XWC


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong), ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", wt.DWORD), ("__a", wt.DWORD), ("RegionSize", ctypes.c_ulonglong),
                ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD), ("__b", wt.DWORD)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]


def find_pid(name):
    import subprocess
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if parts and parts[0].lower().startswith(name.lower()):
            return int(parts[1])
    return None


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not self.h:
            raise OSError(f"OpenProcess failed: {ctypes.get_last_error()}")

    def regions(self):
        addr, mbi = 0, MBI()
        while k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            if mbi.State == MEM_COMMIT and (mbi.Protect & 0xFF) in READABLE and not mbi.Protect & PAGE_GUARD:
                yield mbi.BaseAddress, mbi.RegionSize, mbi.Type, mbi.Protect
            addr = mbi.BaseAddress + mbi.RegionSize
            if addr >= 0x7FFFFFFFFFFF:
                break

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
            return b""
        return buf.raw[:got.value]

    def scan(self, patterns, chunk=16 << 20):
        hits = {k: [] for k in patterns}
        for base, size, typ, prot in self.regions():
            off = 0
            while off < size:
                n = min(chunk, size - off)
                data = self.read(base + off, n + 64)
                for label, pat in patterns.items():
                    i = data.find(pat)
                    while i >= 0:
                        if i < n:
                            hits[label].append((base + off + i, base, size, typ, prot))
                        i = data.find(pat, i + 1)
                off += n
        return hits


def main():
    name = sys.argv[1]
    ctx, mx = 64, 20
    patterns = {}
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a == "--context":
            ctx = int(args[i + 1])
        elif a == "--max":
            mx = int(args[i + 1])
        elif "=" in a:
            label, hx = a.split("=", 1)
            patterns[label] = bytes.fromhex(hx)
    pid = find_pid(name)
    if not pid:
        sys.exit(f"{name} isn't running")
    p = Proc(pid)
    print("pid", pid)
    hits = p.scan(patterns)
    for label, lst in hits.items():
        print(f"== {label}: {len(lst)} hit(s)")
        for addr, base, size, typ, prot in lst[:mx]:
            print(f"  @{addr:#x} region {base:#x}+{size:#x} type {typ:#x} prot {prot:#x}")
            if ctx:
                data = p.read(addr - ctx, 2 * ctx)
                for row in range(0, len(data), 16):
                    seg = data[row:row + 16]
                    print(f"    {addr - ctx + row:#x}: {seg.hex(' ')}  {''.join(chr(b) if 32 <= b < 127 else '.' for b in seg)}")


if __name__ == "__main__":
    main()
