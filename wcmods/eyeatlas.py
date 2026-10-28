"""The eye colour atlas: CurveAtlas_Characters_Eyes_AllColors.

A 64 x 26 RGBA16F texture baked from 26 colour curves. Row 0 is the sclera (white of the eye),
rows 1-20 are the standard iris colours and rows 21-25 the DLC ones. Each iris row is a ramp
from black (pupil side) to the full colour. MI_Cat_Eyes samples a row per eye.

Patching keeps the package byte-for-byte identical except the pixel block, so the export
sizes in the zen header and the container's store entry stay valid.
"""
import re
import struct

from .formats.binio import read_name_batch

PATH = ("Wrc/Content/Art/Environment/Common/Materials/Curves/Characters/Eyes/Gradients/"
        "CurveAtlas_Characters_Eyes_AllColors.uasset")
PIXEL_FORMAT = b"PF_FloatRGBA\0"


class EyeAtlas:
    def __init__(self, data):
        self.data = bytearray(data)
        header_size = struct.unpack_from("<I", data, 4)[0]
        imp_map, exp_map = struct.unpack_from("<ii", data, 28)
        imp_names_off = struct.unpack_from("<i", data, 48)[0]
        pf = data.find(PIXEL_FORMAT, header_size)
        if pf < 0:
            raise ValueError("eye atlas: pixel format marker not found (game updated?)")
        self.width, self.height, slices = struct.unpack_from("<iii", data, pf - 16)
        if slices != 1:
            raise ValueError("eye atlas: unexpected texture layout")
        first_mip, num_mips, _ = struct.unpack_from("<iii", data, pf + len(PIXEL_FORMAT))
        if (first_mip, num_mips) != (0, 1):
            raise ValueError("eye atlas: unexpected mip layout")
        self.pixel_offset = pf + len(PIXEL_FORMAT) + 12
        end = self.pixel_offset + self.width * self.height * 8
        if struct.unpack_from("<ii", data, end) != (self.width, self.height):
            raise ValueError("eye atlas: pixel block size check failed")

        # Row labels: GradientCurves is the first array in the export (TextureSize, count, refs).
        imported, _ = read_name_batch(data, imp_names_off)
        imports = struct.unpack_from(f"<{(exp_map - imp_map) // 8}Q", data, imp_map)
        tex_size, count = struct.unpack_from("<ii", data, header_size + 4)
        refs = struct.unpack_from(f"<{count}i", data, header_size + 12) if count == self.height else ()
        self.labels = []
        dlc = 0
        for row in range(self.height):
            label = f"row{row}"
            if row < len(refs):
                imp = imports[-refs[row] - 1]
                if imp >> 62 == 2:
                    label = imported[(imp >> 32) & 0x3FFFFFFF].rsplit("/", 1)[-1]
            label = label.replace("CC_Character_Eyes_Iris_", "").replace("CC_Character_Eyes_", "")
            if label == "Dlc":
                dlc += 1
                label = f"Dlc{dlc}"
            elif label.startswith("Sclera"):
                label = "Sclera"
            self.labels.append(label)

    def slot(self, name):
        """Resolve a palette key ('Amber', 'sclera', 'iris3', 'row5', '5') to a row index (resolve())."""
        return resolve(self.labels, name, self.height)

    def row(self, r):
        if not 0 <= r < self.height:
            raise ValueError("bad row")
        base = self.pixel_offset + r * self.width * 8
        return [struct.unpack_from("<4e", self.data, base + x * 8) for x in range(self.width)]

    def set_row(self, r, pixels):
        if not 0 <= r < self.height or len(pixels) != self.width:
            raise ValueError("bad row")
        base = self.pixel_offset + r * self.width * 8
        for x, px in enumerate(pixels):
            struct.pack_into("<4e", self.data, base + x * 8, *[_clamp_half(c) for c in px])

    def bytes(self):
        return bytes(self.data)


def resolve(labels, name, height=None):
    """The row a palette's eye key means: one of the atlas's labels in any case ('Amber', 'sclera'), then
    'irisN', 'rowN' or a plain number, which has to be one of its rows. KeyError, with a sentence that names
    the key, for anything else: the build skips that entry, and Clan Mod Studio says so when it's saved."""
    height = len(labels) if height is None else height
    key = str(name).strip().lower()
    for i, label in enumerate(labels):
        if label.lower() == key:
            return i
    m = re.fullmatch(r"(?:iris|row)?([0-9]+)", key)
    if not m:
        raise KeyError(f"'{name}' isn't one of the game's eye colours ({', '.join(labels)})")
    row = int(m.group(1))
    if row >= height:
        raise KeyError(f"'{name}' is past the game's {height} eye colours (they're 0-{height - 1})")
    return row


def _clamp_half(v):
    return max(0.0, min(float(v), 65000.0))
