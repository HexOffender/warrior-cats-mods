"""Recolouring a picture: a mod can ask for one of the game's textures in other colours ("tint" it, or turn
its hues), made at install from the player's own game files, so the mod ships no picture of the game's.

    {"tint": "#a8c4ff"}                       the picture's light and shade, in that colour
    {"tint": "#a8c4ff", "strength": 0.6}      part way there
    {"hue": 200, "saturation": 0.8}           its colours turned 200 degrees round the colour wheel
    {"brightness": 1.2}                       lighter (or darker below 1)

Images are RGBA bytes (png.py); alpha is kept.
"""
import colorsys

KEYS = {"from", "tint", "strength", "hue", "saturation", "brightness"}


def check(spec, where):
    """Raise ValueError for a recolour that can't be done."""
    unknown = sorted(set(spec) - KEYS - {k for k in spec if k.startswith("_")})
    if unknown:
        raise ValueError(f"{where}: unknown key(s) {', '.join(unknown)} (it takes {', '.join(sorted(KEYS))})")
    if "tint" in spec and _hex(spec["tint"]) is None:
        raise ValueError(f'{where}: "tint" should be a colour like "#a8c4ff"')
    for key, lo, hi in (("strength", 0, 1), ("hue", -360, 360), ("saturation", 0, 4), ("brightness", 0, 4)):
        v = spec.get(key)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi):
            raise ValueError(f'{where}: "{key}" should be a number from {lo} to {hi}')
    if not any(k in spec for k in ("tint", "hue", "saturation", "brightness")):
        raise ValueError(f'{where}: say how to recolour it: "tint", "hue", "saturation" or "brightness"')


def _hex(s):
    if not isinstance(s, str) or len(s) != 7 or s[0] != "#":
        return None
    try:
        return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        return None


def apply(rgba, spec):
    """The recoloured image's bytes."""
    out = bytearray(rgba)
    tint = _hex(spec["tint"]) if "tint" in spec else None
    strength = float(spec.get("strength", 1.0))
    turn = float(spec.get("hue", 0)) / 360.0
    sat = float(spec.get("saturation", 1.0))
    bright = float(spec.get("brightness", 1.0))
    hsv = turn or sat != 1.0
    cache = {}
    for i in range(0, len(out), 4):
        key = (out[i], out[i + 1], out[i + 2])
        new = cache.get(key)
        if new is None:
            r, g, b = key
            if hsv:
                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                r, g, b = (c * 255 for c in colorsys.hsv_to_rgb((h + turn) % 1.0, min(1.0, s * sat), v))
            if tint:
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                # The light of the picture in the tint's colour: shade below the tint's own light, highlights
                # toward white.
                tr, tg, tb = (lum * 2 * c if lum < 0.5 else c + (255 - c) * (lum - 0.5) * 2 for c in tint)
                r, g, b = (a + (t - a) * strength for a, t in ((r, tr), (g, tg), (b, tb)))
            r, g, b = (max(0, min(255, int(c * bright + 0.5))) for c in (r, g, b))
            new = (r, g, b)
            cache[key] = new
        out[i], out[i + 1], out[i + 2] = new
    return bytes(out)
