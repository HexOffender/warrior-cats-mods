"""Does the lighting flicker? The screen's brightness read about 40 times a second (the green channel of every sixth
pixel in patches, straight from a desktop capture), 8 s per condition, standing still at WindClan's camp: midday, the
dusk with the clock running (the day sky's blend changing), the dusk with the clock stopped (nothing changing), and
midday with the sky's ApplyStraight called four times a second from Lua (the call measured on its own). A flicker shows
as one-frame dips: a drop of 1.5 or more followed within two samples by a rise. With the fix of 2026-11-08 (day_sky
fades the preset with StartTransition instead of putting it on again) the dusk gives none; ApplyStraight gives several.
The game must be in the forest with a mod running day_sky (Clan life with night_sky on) for the dusk conditions to mean
anything; the ApplyStraight one stands alone.

    python wcmods.py agent run tools/sky_flicker.py
"""
import ctypes
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from wcmods.agent import window  # noqa: E402

SRCCOPY = 0x00CC0020
user32, gdi32 = window.user32, window.gdi32
WINDCLAN_CAMP = (-31900, 33600)
APPLY = """
if __ap then Game.cancel(__ap) end
__ap_n = 0
__ap = Game.every(0.25, function()
  if Game.sky.set("WindClan", false) then __ap_n = __ap_n + 1 end   -- the sky's ApplyStraight, once, not held
end)
return true
"""
STOP_APPLY = "if __ap then Game.cancel(__ap) end __ap = nil return __ap_n or 0"


class Screen:
    """A desktop capture reused: BitBlt into one bitmap, the bytes read back each time."""

    def __init__(self):
        self.w, self.h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        self.hdc = user32.GetDC(None)
        self.mem = gdi32.CreateCompatibleDC(self.hdc)
        self.bmp = gdi32.CreateCompatibleBitmap(self.hdc, self.w, self.h)
        gdi32.SelectObject(self.mem, self.bmp)
        self.bmi = window.BITMAPINFOHEADER(ctypes.sizeof(window.BITMAPINFOHEADER), self.w, -self.h, 1, 32, 0, 0, 0, 0, 0, 0)
        self.buf = ctypes.create_string_buffer(self.w * self.h * 4)
        w, h = self.w, self.h
        self.boxes = {"all": (0, 0, w, h), "near": (w // 3, int(h * 0.75), 2 * w // 3, int(h * 0.95)),
                      "far": (w // 3, int(h * 0.5), 2 * w // 3, int(h * 0.6)), "sky": (w // 3, int(h * 0.05), 2 * w // 3, int(h * 0.15)),
                      "left": (0, int(h * 0.5), w // 3, int(h * 0.95)), "right": (2 * w // 3, int(h * 0.5), w, int(h * 0.95))}

    def grab(self):
        gdi32.BitBlt(self.mem, 0, 0, self.w, self.h, self.hdc, 0, 0, SRCCOPY)
        gdi32.GetDIBits(self.mem, self.bmp, 0, self.h, self.buf, ctypes.byref(self.bmi), 0)
        raw = self.buf.raw
        stride = self.w * 4
        out = {}
        for name, (x0, y0, x1, y1) in self.boxes.items():
            total, n = 0, 0
            for y in range(y0, y1, 6):
                row = raw[y * stride + x0 * 4 + 1:y * stride + x1 * 4:24]
                total += sum(row)
                n += len(row)
            out[name] = total / max(1, n)
        return out

    def close(self):
        gdi32.DeleteObject(self.bmp)
        gdi32.DeleteDC(self.mem)
        user32.ReleaseDC(None, self.hdc)


def sample(screen, seconds):
    rows = []
    t0 = time.time()
    while time.time() - t0 < seconds:
        vals = screen.grab()
        vals["t"] = round(time.time() - t0, 3)
        rows.append(vals)
    return rows


def dips(rows, key, down=1.5, back=1.0):
    v = [r[key] for r in rows]
    return [rows[i]["t"] for i in range(1, len(v) - 2) if v[i] - v[i - 1] < -down and max(v[i + 1], v[i + 2]) - v[i] > back]


def summary(rows, label):
    lines = [f"== {label}: {len(rows)} samples in {rows[-1]['t']:.1f} s"]
    for k in ("all", "near", "far", "left", "right", "sky"):
        v = [r[k] for r in rows]
        d = [abs(v[i] - v[i - 1]) for i in range(1, len(v))]
        ds = dips(rows, k)
        lines.append(f"   {k:5s} mean {sum(v) / len(v):6.1f}  jumps over 1.5: {sum(x > 1.5 for x in d):3d}  one-frame dips: {len(ds):2d}"
                     f"  at {' '.join(f'{t:.2f}' for t in ds[:12])}")
    return "\n".join(lines)


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def focus():
    hwnd = agent._window()
    if not window.is_foreground(hwnd):
        window.bring_to_front(hwnd)
    time.sleep(0.3)


def clock(running):
    agent.lua(f'Game.set(Game.gameState(), "WCM_ClockSpeed", {72 if running else 0}) return true')


def set_time(hour):
    agent.lua(f"Game.time.set({int(hour)}, {int(round((hour % 1) * 60))}) return true")
    time.sleep(4)   # the exposure settles


def run(label, screen, results):
    focus()
    rows = sample(screen, 8)
    say(summary(rows, label))
    results.append({"label": label, "rows": rows})


x, y = WINDCLAN_CAMP
g = agent.lua(f"return Game.ground({x}, {y}, 4000)")
r = agent.lua(f"return Game.cat():teleport({x}, {y}, {g + 60})")
assert r is True or (isinstance(r, list) and r and r[0] is True), f"couldn't teleport to WindClan's camp: {r}"
time.sleep(5)
screen = Screen()
results = []
try:
    clock(True)
    set_time(20.17)
    run("dusk, clock running", screen, results)
    clock(False)
    time.sleep(1.5)
    run("dusk, clock stopped", screen, results)
    set_time(12)
    run("midday, clock stopped", screen, results)
    agent.lua(APPLY)
    time.sleep(0.5)
    run("midday, clock stopped, ApplyStraight(WindClan) four times a second from Lua", screen, results)
    say("   applied", agent.lua(STOP_APPLY), "times")
finally:
    agent.lua(STOP_APPLY)
    clock(True)
    agent.lua("Game.time.set(12, 0) return true")
    screen.close()
    with open("sky_flicker.json", "w", encoding="utf-8") as f:
        json.dump(results, f)
say("DONE (sky_flicker.json written here)")
