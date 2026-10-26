"""New textures for mods, made from a PNG at install: a copy of one of the game's textures (the same
size, format and number of mips) under a new name, with the PNG's pixels.

Cooking a texture from scratch would mean writing every part of a cooked Texture2D. A copy keeps the
game's layout byte for byte and changes only:
  * the pixels, at the places the package's bulk data map gives for each mip (in the package itself,
    or in its .ubulk for the big mips);
  * its name: the package's and the texture's in the name map, and the export's public hash;
  * its IDs: the package ID is CityHash64 of the package name in lower case (UTF-16), and its chunks
    are that ID with the chunk type (1 the package, 2 its bulk data).
The new package goes into wcmods' IoStore container with the game texture's imports, so the game
loads it like its own: an item's icon, an accessory's look.

DXT1 and DXT5 textures can be copied (bcn.py encodes them).
"""
import struct

from . import bcn, png
from .cityhash import cityhash64, name_hash
from .cooked import ZenPackage

CHUNK_EXPORT_BUNDLE, CHUNK_BULK = 1, 2
BULK_IN_SEPARATE_FILE = 1 << 8
EXPORT_ENTRY = 72


def package_id(package_name):
    """FPackageId of a package path ("/Game/WCMods/my-mod/T_MoonHerb")."""
    return cityhash64(package_name.lower().encode("utf-16-le"))


def chunk_id(pid, kind):
    """A 12-byte IoStore chunk ID: the package ID, index 0, the chunk type."""
    return struct.pack("<Q", pid) + b"\0\0\0" + bytes([kind])


def export_hash(object_name):
    """An export's public hash: CityHash64 of its path in the package, in lower case (UTF-16)."""
    return cityhash64(object_name.lower().encode("utf-16-le"))


class Texture:
    """One of the game's cooked textures, to copy under a new name with new pixels."""

    def __init__(self, data, bulk=None):
        self.pkg = ZenPackage(data)
        if self.pkg.export_count != 1:
            raise ValueError("only textures with a single export can be copied")
        self.bulk = bytearray(bulk) if bulk is not None else None
        rest = self.pkg._rest
        (n,) = struct.unpack_from("<q", rest, 0)
        if n % 32:
            raise ValueError("unexpected bulk data map")
        self.entries = [struct.unpack_from("<qqqI", rest, 8 + 32 * i) for i in range(n // 32)]
        off, size = self.pkg.export(0)
        self.export = bytearray(self.pkg.export_data[off:off + size])
        self.trailer = self.pkg.export_data[off + size:]
        pf = self.export.find(b"PF_")
        if pf < 16:
            raise ValueError("no pixel format in the texture")
        end = self.export.index(b"\0", pf)
        self.format = self.export[pf:end].decode("ascii")
        if self.format not in bcn.FORMATS:
            raise ValueError(f"{self.format} textures can't be copied (only {', '.join(bcn.FORMATS)})")
        self.width, self.height = struct.unpack_from("<ii", self.export, pf - 16)
        self.mips = []                              # (width, height, in the .ubulk?, offset, size)
        for i, (offset, _dup, length, flags) in enumerate(self.entries):
            w, h = max(1, self.width >> i), max(1, self.height >> i)
            if bcn.size(self.format, w, h) != length:
                raise ValueError(f"mip {i} isn't {w} x {h} {self.format} as expected")
            separate = bool(flags & BULK_IN_SEPARATE_FILE)
            if separate and (self.bulk is None or offset + length > len(self.bulk)):
                raise ValueError("the texture's .ubulk is missing or short")
            if not separate and offset + length > len(self.export):
                raise ValueError("a mip runs past the texture's export")
            self.mips.append((w, h, separate, offset, length))
        if not self.mips:
            raise ValueError("the texture has no mips")

    def set_image(self, width, height, rgba):
        """Put an RGBA image in every mip (scaled to the texture's size first)."""
        rgba = png.resize(width, height, rgba, self.width, self.height)
        w, h = self.width, self.height
        for mw, mh, separate, offset, length in self.mips:
            while (w, h) != (mw, mh):
                w, h, rgba = png.half(w, h, rgba)
            blocks = bcn.encode(self.format, w, h, rgba)
            assert len(blocks) == length
            (self.bulk if separate else self.export)[offset:offset + length] = blocks

    def image(self, mip=0):
        """(width, height, RGBA) of one of the texture's mips."""
        w, h, separate, offset, length = self.mips[mip]
        src = self.bulk if separate else self.export
        return w, h, bcn.decode(self.format, w, h, bytes(src[offset:offset + length]))

    def rename(self, package_name, object_name):
        """Name it /Game/...: the package's and the texture's names, and the export's public hash."""
        names = self.pkg.names
        em = self.pkg.summary[8] - self.pkg._after_names
        rest = bytearray(self.pkg._rest)
        name_index = struct.unpack_from("<I", rest, em + 16)[0]
        package_index = self.pkg.summary[2]
        for i, new in ((name_index, object_name), (package_index, package_name)):
            if not new.isascii():
                raise ValueError(f"{new!r}: texture names must be ASCII")
            del self.pkg._index[names[i]]
            names[i] = new
            self.pkg._index[new] = i
            self.pkg.hashes[i] = name_hash(new)
        struct.pack_into("<Q", rest, em + 56, export_hash(object_name))
        self.pkg._rest = bytes(rest)
        self.package_name = package_name

    def files(self):
        """(package bytes, .ubulk bytes or None)."""
        data = self.pkg.rebuild(bytes(self.export) + self.trailer, [len(self.export)])
        return data, bytes(self.bulk) if self.bulk is not None else None


CACHE_VERSION = 2   # change when the encoder, the copy or recolor.py changes, so cached textures are made again


def load(game, asset):
    """One of the game's textures by its asset path ("/Game/.../T_X.T_X" or the package's path), with
    its .ubulk. ValueError if the game hasn't got it or it can't be copied."""
    path = content_path(asset.split(".", 1)[0])
    if not game.exists(path):
        raise ValueError(f"the game has no texture {asset}")
    ubulk = path[:-len(".uasset")] + ".ubulk"
    return Texture(game.read(path), game.read(ubulk) if game.exists(ubulk) else None)


def new_package_name(name):
    """/Game/WCMods/<name>: letters, digits, _ and / only, so the game takes it as a package path."""
    clean = "/".join("".join(c if c.isalnum() or c == "_" else "_" for c in part) for part in name.strip("/").split("/"))
    if not clean or not clean.isascii():
        raise ValueError(f"{name!r} isn't a usable texture name")
    return "/Game/WCMods/" + clean


def content_path(package):
    """The container path of a /Game/ package: Wrc/Content/....uasset."""
    return "Wrc/Content/" + package[len("/Game/"):] + ".uasset"


def _clear_out(cache, days=30):
    """Remove cached textures no install has used for `days` (a picture since changed, a mod gone)."""
    import os
    import time
    if not os.path.isdir(cache):
        return
    old = time.time() - days * 86400
    for name in os.listdir(cache):
        path, main = os.path.join(cache, name), os.path.join(cache, name.split(".", 1)[0] + ".uasset")
        try:                                    # a .ubulk goes with its package
            if os.path.getmtime(main if os.path.isfile(main) else path) < old:
                os.remove(path)
        except OSError:
            pass


def build(ctx, package, image, like, key=None):
    """{"data", "bulk", "chunk_id", "imports", "shaders"} for a new texture `package` from `image`
    (width, height, RGBA, or a function that makes them) and the game's texture `like` (an asset path).
    Kept in cache/textures under the template's bytes and `key`, text that changes whenever the image
    would (without one, the image's own bytes), so an install doesn't make the same texture twice."""
    import hashlib
    import os
    tex = load(ctx.game, like)
    if key is None:
        image = image() if callable(image) else image
        key = hashlib.sha1(f"{image[0]}x{image[1]}|".encode() + image[2]).hexdigest()
    template = hashlib.sha1(tex.pkg.data + (bytes(tex.bulk) if tex.bulk is not None else b"")).hexdigest()
    name = hashlib.sha1(f"{CACHE_VERSION}|{package}|{like}|{template}|{key}".encode()).hexdigest()
    cache = os.path.join(ctx.cache_dir, "textures")
    imports, shaders = ctx.game.io.container_header().entry_for(package_id(like.split(".", 1)[0]))
    found, found_bulk = os.path.join(cache, name + ".uasset"), os.path.join(cache, name + ".ubulk")
    if os.path.isfile(found) and (tex.bulk is None or os.path.isfile(found_bulk)):
        with open(found, "rb") as f:
            data = f.read()
        bulk = None
        if tex.bulk is not None:
            with open(found_bulk, "rb") as f:
                bulk = f.read()
        os.utime(found)                         # used: kept by the clear-out below
    else:
        _clear_out(cache)
        width, height, rgba = image() if callable(image) else image
        tex.set_image(width, height, rgba)
        tex.rename(package, package.rsplit("/", 1)[-1])
        data, bulk = tex.files()
        os.makedirs(cache, exist_ok=True)
        # The .ubulk first and each file whole, so a cached package always has all of itself.
        for path, content in ((found_bulk, bulk), (found, data)):
            if content is not None:
                with open(path + ".tmp", "wb") as f:
                    f.write(content)
                os.replace(path + ".tmp", path)
    return {"data": data, "bulk": bulk, "chunk_id": chunk_id(package_id(package), CHUNK_EXPORT_BUNDLE),
            "imports": imports, "shaders": shaders}
