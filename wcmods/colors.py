"""Colour parsing and conversion (sRGB hex in palettes, linear floats in the engine)."""
import re

NAMED = {
    "black": "000000", "white": "ffffff", "red": "ff0000", "green": "00ff00", "blue": "0000ff",
    "gold": "ffd700", "silver": "c0c0c0", "pink": "ff69b4", "purple": "8a2be2", "teal": "008080",
    "orange": "ff8c00", "cyan": "00ffff", "magenta": "ff00ff", "lime": "32cd32", "navy": "000080",
}


def parse(value):
    """'#RRGGBB', 'RRGGBB', '#RGB', a CSS-ish name, or [r, g, b] (0-255) -> sRGB floats 0..1."""
    if isinstance(value, (list, tuple)):
        if len(value) not in (3, 4):
            raise ValueError(f"colour list needs 3 values: {value!r}")
        return tuple(max(0, min(255, float(c))) / 255.0 for c in value[:3])
    s = str(value).strip().lower()
    s = NAMED.get(s, s).lstrip("#")
    if re.fullmatch(r"[0-9a-f]{3}", s):
        s = "".join(c * 2 for c in s)
    if not re.fullmatch(r"[0-9a-f]{6}([0-9a-f]{2})?", s):
        raise ValueError(f"not a colour: {value!r}")
    return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def to_linear(rgb):
    return tuple(srgb_to_linear(c) for c in rgb)


def hex_from_linear(rgb):
    return "#" + "".join(f"{round(linear_to_srgb(c) * 255):02x}" for c in rgb[:3])


def hex_from_srgb(rgb):
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb[:3])


def luminance(rgb):
    r, g, b = rgb[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
