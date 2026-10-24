"""Generate the themed palette examples (palette-*/ in the wcmods-examples repository) from the game's
own colours.

    python tools/make_palettes.py --out ../wcmods-examples   # (re)writes every one; they start turned off

Themes are priority -10, below eyes-only and coats-only palettes, so those can go on top of one.
Each theme grades the game's natural coat, pattern and marking colours (slots 0-14), so a slot keeps
its place from light to dark and cats still look like cats. It gives the bright extras (15-24) a set of
the theme's own colours, and recolours the 20 standard eye slots. The game's colours come from
colour_tables.json (written by `wcmods tables`) and the eye atlas. Palettes are appearance-only: a cat
keeps the same slots, so traits and stats don't change.
"""
import colorsys
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

EYES = ["Olive", "Amber", "Orange", "Cooper", "Forest", "Leaf", "Cerulean", "Yellow", "Gold", "Hazel",
        "Lapiz", "Sky", "Coral", "Cadet", "Gray", "Pink", "PaleVioletRed", "Lavender", "Red", "FireBrick"]


# ---------- colour maths (sRGB, HLS) ----------
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def hexc(c):
    return "#" + "".join(f"{round(max(0.0, min(1.0, v)) * 255):02X}" for v in c)


def clamp(v):
    return max(0.0, min(1.0, v))


def grade(h, tint=None, amount=0.0, sat=1.0, lift=0.0, lmul=1.0, grey_sat=0.0, pre_sat=1.0):
    """Mix towards a tint hue at the colour's own lightness, then scale saturation and lightness.

    pre_sat washes the colour out before tinting (silvers: a ginger tinted blue at full colour turns
    muddy); lift raises lightness towards white (pastels); lmul darkens or brightens; grey_sat gives the
    greys (which have no hue of their own) a little of the tint.
    """
    r, g, b = rgb(h)
    hue, light, s = colorsys.rgb_to_hls(r, g, b)
    if pre_sat != 1.0:
        s = clamp(s * pre_sat)
        r, g, b = colorsys.hls_to_rgb(hue, light, s)
    if tint is not None:
        if s < 0.08 and grey_sat:
            hue, s = tint / 360, max(s, grey_sat)
        elif amount:
            tr, tg, tb = colorsys.hls_to_rgb(tint / 360, light, max(s, 0.35))
            r, g, b = (r + (tr - r) * amount, g + (tg - g) * amount, b + (tb - b) * amount)
            hue, light, s = colorsys.rgb_to_hls(r, g, b)
    s = clamp(s * sat)
    light = clamp(light * lmul)
    light = clamp(light + (1 - light) * lift)
    return hexc(colorsys.hls_to_rgb(hue, light, s))


def shade(h, lmul, sat=1.0):
    hue, light, s = colorsys.rgb_to_hls(*rgb(h))
    return hexc(colorsys.hls_to_rgb(hue, clamp(light * lmul), clamp(s * sat)))


def tint_up(h, lift, sat=1.0):
    hue, light, s = colorsys.rgb_to_hls(*rgb(h))
    return hexc(colorsys.hls_to_rgb(hue, clamp(light + (1 - light) * lift), clamp(s * sat)))


# ---------- themes ----------
# coats: grade() arguments for the natural slots; extras: ten colours for coat slots 15-24 (patterns get a
# darker, markings a lighter version); eyes: grade() arguments for the eye rims, or "glow" for gradients.
THEMES = {
    "thunderclan-forest": {
        "name": "ThunderClan Forest",
        "description": "Warm gingers and rich browns, moss and bracken extras, amber and leaf-green eyes.",
        "coats": dict(tint=30, amount=0.15, sat=1.2, grey_sat=0.05),
        "extras": ["#5E7C2F", "#7FA34A", "#A8692E", "#B3261E", "#C98A3D", "#2F5D3A", "#E0B341", "#7B3F1D",
                   "#9FB07A", "#5B2A3C"],
        "eyes": dict(tint=60, amount=0.3, sat=1.2),
    },
    "riverclan-waters": {
        "name": "RiverClan Waters",
        "description": "Silvery, cool coats with river-blue greys, reed and kingfisher extras, teal and blue eyes.",
        "coats": dict(pre_sat=0.7, tint=205, amount=0.22, sat=0.9, grey_sat=0.12),
        "extras": ["#3E7FA8", "#6F8F5A", "#B9C6CC", "#1F9DB5", "#5A4A3C", "#2E8C86", "#8C8A80", "#4C6BC2",
                   "#A9C9D9", "#1E3B5A"],
        "eyes": dict(tint=190, amount=0.45, sat=1.15),
    },
    "shadowclan-night": {
        "name": "ShadowClan Night",
        "description": "Darker, smoky coats, marsh and nightshade extras, glowing yellow-green eyes.",
        "coats": dict(pre_sat=0.8, tint=270, amount=0.12, sat=0.8, lmul=0.78, grey_sat=0.05),
        "extras": ["#1E1B3A", "#3D4A2C", "#6B2E4F", "#4B2C6E", "#4A4D55", "#2F4F3F", "#8A3B1A", "#5A4A2A",
                   "#22262E", "#3F3A5C"],
        "eyes": dict(tint=75, amount=0.4, sat=1.35, lift=0.05),
    },
    "windclan-moor": {
        "name": "WindClan Moor",
        "description": "Sandy, weathered coats, heather and gorse extras, pale gold and hazel eyes.",
        "coats": dict(pre_sat=0.75, tint=40, amount=0.15, sat=0.85, lmul=1.06, grey_sat=0.05),
        "extras": ["#9B7BA6", "#E0C04A", "#D8C29A", "#A8A86A", "#A0846A", "#9CC3DA", "#5E4A3A", "#B58BC2",
                   "#CDB27F", "#E8D16A"],
        "eyes": dict(tint=50, amount=0.3, sat=0.9, lmul=1.05),
    },
    "skyclan-sunset": {
        "name": "SkyClan Sunset",
        "description": "Glowing oranges and roses, sunset and twilight extras, fiery eyes.",
        "coats": dict(tint=15, amount=0.2, sat=1.2, grey_sat=0.06),
        "extras": ["#F2784B", "#E86A92", "#8E5FB0", "#F7B28A", "#F06C5B", "#6E3A6B", "#F5A623", "#C9A0DC",
                   "#D9462E", "#4E4A8A"],
        "eyes": dict(tint=20, amount=0.4, sat=1.25),
    },
    "starclan-silverpelt": {
        "name": "StarClan Silverpelt",
        "description": "Pale, frosted coats with a silver-blue sheen, starlight extras, eyes that glow from the pupil out.",
        "coats": dict(pre_sat=0.3, tint=220, amount=0.45, sat=0.9, lift=0.15, grey_sat=0.14),
        "extras": ["#DDE8FF", "#B8C6E6", "#6F8FD6", "#8E7CD6", "#CFEFFF", "#F2F6FF", "#9FB6E0", "#7FD6C2",
                   "#5A6FB0", "#E6D6FF"],
        "eyes": "glow",
    },
    "dark-forest": {
        "name": "Dark Forest",
        "description": "Dim, ashen coats, rot and bone extras, blood-red and sickly eyes.",
        "coats": dict(tint=95, amount=0.12, sat=0.5, lmul=0.78, grey_sat=0.04),
        "extras": ["#4A5A2A", "#6E1414", "#7A7A4A", "#3A3A38", "#BDB39A", "#4A3550", "#2E3A2A", "#7A3A1A",
                   "#3C4048", "#6A8A2A"],
        "eyes": dict(tint=5, amount=0.5, sat=1.3, lmul=0.95),
    },
    "leaf-bare-frost": {
        "name": "Leaf-bare Frost",
        "description": "Wintry, icy coats, snow and holly extras, ice-blue eyes.",
        "coats": dict(pre_sat=0.45, tint=205, amount=0.3, sat=0.9, lift=0.1, grey_sat=0.10),
        "extras": ["#F4F8FB", "#BFE3F2", "#8DB8D8", "#3D5A5A", "#A7C4E0", "#2E5E3E", "#9AA5AE", "#5FA3C7",
                   "#A3243B", "#6E8FA8"],
        "eyes": dict(tint=195, amount=0.5, sat=1.0, lmul=1.1),
    },
    "pastel-kits": {
        "name": "Pastel Kits",
        "description": "Soft pastel coats and eyes, mint, lavender and blush extras.",
        "coats": dict(sat=0.55, lift=0.42, tint=320, amount=0.08, grey_sat=0.05),
        "extras": ["#BFEFD8", "#D8C8F2", "#BCDCF7", "#F7C6D9", "#FBEBA8", "#FAD0B5", "#E3C7EC", "#B7E3DD",
                   "#F2B5C4", "#C3CCF4"],
        "eyes": dict(sat=0.85, lift=0.4),
    },
    "vivid-clans": {
        "name": "Vivid Clans",
        "description": "Saturated, storybook colours: bold coats, bright extras, vivid eyes.",
        "coats": dict(sat=1.45),
        "extras": ["#1E90FF", "#7CFC00", "#FF1DCE", "#FF8C00", "#8A2BE2", "#00E5CC", "#FF2400", "#FFD700",
                   "#FF4F9A", "#00C060"],
        "eyes": dict(sat=1.45, lift=0.03),
    },
}


def game_colours():
    path = os.path.join(ROOT, "colour_tables.json")
    if not os.path.isfile(path):
        sys.exit("colour_tables.json is missing. Start the game once with UE4SS and the mods installed, "
                 "then run `python wcmods.py tables`, which writes it from the game's log.")
    with open(path, encoding="utf-8-sig") as f:
        tables = json.load(f)
    from wcmods import eyeatlas
    from wcmods.colors import hex_from_linear
    from wcmods.config import Config
    from wcmods.gamefiles import GameFiles
    atlas = eyeatlas.EyeAtlas(GameFiles(Config(ROOT)).read(eyeatlas.PATH))
    rims = {atlas.labels[r]: hex_from_linear(atlas.row(r)[-1]).upper() for r in range(1, 21)}
    return tables, rims


def glow_eyes(rims):
    """StarClan: each eye glows from a dark pupil through its colour to a pale, starlit rim."""
    out = {}
    for name, h in rims.items():
        mid = grade(h, tint=220, amount=0.25, sat=1.1, lift=0.25)
        out[name] = [shade(mid, 0.18, 0.9), mid, tint_up(mid, 0.8, 0.5)]
    return out


def build(theme, tables, rims):
    coats = theme["coats"]
    palette = {"_help": "Generated by tools/make_palettes.py from the game's colours. Coat, pattern and "
                        "marking keys are slots (0-14 natural, 15-24 bright extras); eye keys are the game's slot names."}
    for sec, table, extra in (("fur", "FurColors", lambda c: c),
                              ("pattern", "PatternMaskColors", lambda c: shade(c, 0.72, 1.05)),
                              ("marking", "MarkingMaskColors", lambda c: tint_up(c, 0.45, 0.8))):
        colours = tables[table]
        palette[sec] = {str(i): grade(colours[i], **coats) for i in range(15)}
        palette[sec].update({str(15 + i): extra(c) for i, c in enumerate(theme["extras"])})
    palette["eyes"] = glow_eyes(rims) if theme["eyes"] == "glow" else {n: grade(h, **theme["eyes"]) for n, h in rims.items()}
    return palette


def main():
    import argparse
    p = argparse.ArgumentParser(description="Generate the themed palette examples from the game's colours.")
    p.add_argument("--out", default=os.path.join(os.path.dirname(ROOT), "wcmods-examples"),
                   help="the wcmods-examples checkout to write palette-*/ into (default: beside wcmods)")
    out = os.path.abspath(p.parse_args().out)
    if not os.path.isdir(out):
        sys.exit(f"{out} doesn't exist: clone wcmods-examples there, or pass --out")
    tables, rims = game_colours()
    for mod_id, theme in THEMES.items():
        folder = os.path.join(out, "palette-" + mod_id)
        os.makedirs(folder, exist_ok=True)
        meta_path = os.path.join(folder, "mod.json")
        # Full themes sit below partial palettes (Gemstone Eyes, Richer Coats are priority 0), so an
        # eyes-only or coats-only palette ticked with a theme goes on top of it.
        meta = {"name": theme["name"], "description": theme["description"], "enabled": False, "priority": -10}
        if os.path.isfile(meta_path):   # regenerating keeps whether it's on, its priority and any extras
            with open(meta_path, encoding="utf-8-sig") as f:
                meta.update({k: v for k, v in json.load(f).items() if k not in ("name", "description")})
        with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, indent=2)
            f.write("\n")
        with open(os.path.join(folder, "palette.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(build(theme, tables, rims), f, indent=2)
            f.write("\n")
        print(f"wrote {folder}")


if __name__ == "__main__":
    main()
