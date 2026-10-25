"""Round-trip checks against the installed game and save. Writes only to a temp folder."""
import os
import re
import struct
import tempfile

from . import bridge, catlook, controls, draw, eyeatlas, keymap, luacheck, menu, mouselook, palettes, view, world
from . import game as game_lua
from .blake3 import blake3
from .iostore import IoStoreReader, ModContainerWriter
from .pak import PakReader, PakWriter
from .save import JSON_NAME, SAV_NAME, SaveGame


def run(cfg, oodle, log=print):
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        log(f"  [{'ok' if ok else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")

    check("blake3 test vector", blake3(b"").hex().startswith("af1349b9f5f9a1a6"))
    check("name hashes as in the game's name maps (CityHash64, every length)", _name_hashes())
    check("unversioned property headers write back as they read", _unversioned_headers())
    check("pictures: PNGs of every kind read, written back, DXT blocks and recolours", _pictures())
    lua = mouselook.script(mouselook.merge([mouselook.validate({"sensitivity": 1.5, "invert": True, "smoothing": 50})]))
    problems = luacheck.check(lua)
    check("mouse look script", not problems and "@SETTINGS@" not in lua and "sensitivity = 1.5" in lua
          and "invert = true" in lua and "smoothing = 50.0" in lua, "; ".join(problems[:3]))
    for module in (view, draw, world, menu, game_lua):
        lua = module.lua()
        problems = luacheck.check(lua)
        left = re.findall(r"@[A-Z_]+@", lua)   # placeholders that weren't filled in
        check(f"shared module {module.SHARED_NAME}", not problems and not left, "; ".join(problems[:3] + left[:3]))
    lua = world.names_lua()
    problems = luacheck.check(lua)
    check(f"shared module {world.NAMES_NAME}, with the game's own text for names it hasn't got",
          not problems and "function N.name(" in lua and lua.rstrip().endswith("return N"), "; ".join(problems[:3]))
    lua = mouselook.script(mouselook.merge([{}]), {"path": r"C:\mods\m\mouselook.json", "file": "mods/m/mouselook.json",
                                                  "keep": {"_help": 'say "hi"'}})
    problems = luacheck.check(lua)
    check("mouse look script with its menu page", not problems and "@SAVE@" not in lua
          and r'"C:\\mods\\m\\mouselook.json"' in lua, "; ".join(problems[:3]))
    lua = catlook.script({"fur": (1.0, 0.5, 0.0)}, save={"path": "x", "file": "y", "doc": {"player": {"colours": {}}}})
    problems = luacheck.check(lua) + re.findall(r"@[A-Z_]+@", lua)
    check("your cat's colours script with its menu page", not problems and '"#ff8000"' in lua, "; ".join(problems[:3]))
    lua = menu.host_script({"sections": {}, "notes": {}, "warnings": ["w"], "built": "2026-10-24T01:00:00"}, [], dev=True)
    problems = luacheck.check(lua) + re.findall(r"@[A-Z_]+@", lua)
    check("mod menu window script (with the Game, Inspector and Console pages)", not problems
          and 'Menu.page("Inspector"' in lua and '"Materials.Moss"' in lua, "; ".join(problems[:3]))
    check("the mod menu opens from a controller too: its button in the window script, none when it's off",
          '"Gamepad_Special_Left"' in lua and "(or View on a controller)" in lua
          and '["pad"] = ""' in menu.host_script({"sections": {}, "notes": {}, "warnings": [], "built": ""}, [], pad=""))
    lua = bridge.script(cfg)
    problems = luacheck.check(lua) + re.findall(r"@[A-Z_]+@", lua)
    check("game bridge script", not problems and bridge.folder(cfg).replace("\\", "/") in lua, "; ".join(problems[:3]))
    check("in-game script mod", _script_mod(cfg))
    ok, detail = _cpp_mod()
    check("C++ mod: dlls/main.dll goes in with wcmods.json; a DLL for another UE4SS, without UE4SS's exports, or "
          "not built yet is refused", ok, detail)
    ok, detail = _cpp_sdk()
    check("C++ SDK: WCMods.hpp's headers are there, every call in them is in SDK.md and called by its test mod, and "
          "the template uses them", ok, detail)
    check("mod menu answers the agent controller", all(s in menu.lua() for s in ('"agent.read"', '"agent.act"', '"agent.scroll"'))
          and 'Menu.share("frame"' in menu.host_script({"sections": {}, "notes": {}, "warnings": [], "built": ""}, []))
    check("agent controller: pictures, menu rows, test files", _agent_parts())
    check("adding a downloaded mod from a .zip (and refusing unsafe ones)", _mod_zips())
    check("a .zip can't hide code in a name's case, carry a bad mod.json or claim to come with wcmods",
          _mod_zip_guards())
    check("mods that need other mods: switched on together, left out of a build without them", _requirements(cfg))
    check("the mod menu is a mod: its window and module only with it on", _menu_mod(cfg))
    check("getting set up: the game found from any of its folders, a first backup, the script loader", _onboarding())
    check("palettes without the Oodle DLL: eye colours left out with a warning, the rest built", _palettes_without_oodle(cfg))
    check("getting set up, the rough edges: an install from before UE4SS is redone, a folder adds only the "
          "ticked mods, no drive letters in UE4SS's .zip, a studio without the game answers", _onboarding_edges())
    ok, detail = _signatures(cfg)
    check("game update signatures: the decoder, and every class and value found where wcmods expects", ok, detail)
    check("mods made for an older version of the game: left out unless used anyway on that build", _outdated_mods(cfg))
    ok, detail = _update_safety(cfg)
    check("after a game update: nothing kept without evidence, no move on one site's word, a failed check or "
          "broken cache leaves values off, an install from the old build is redone", ok, detail)
    problems = luacheck.check(palettes.ue4ss_script({}))
    check("palette script", not problems, "; ".join(problems[:3]))
    # Interact and Scent tracking move along F/E/Q, so Q goes quiet; X stays because Return to camp still
    # uses it; forward moves to I, so W goes quiet.
    send, block, warns = keymap.plan({"keyboard": {"Player_Interact": "F", "Player_Scent_Tracking": "E",
                                                   "Player_Den_Place": "Z"}, "keys": {"I": "W"}})
    check("key remap plan", send == {"F": "E", "E": "Q", "Z": "X", "I": "W"} and block == {"Q", "W"} and not warns)
    check("key remapper presses", _remapper_presses())
    check("menu remaps", _menu_remaps())
    check("CSV rows added and removed in the file's own style", _csv_rows())
    check("new colour slots and your cat's colours, slots and scars", _colour_slots())
    check("your cat's scars written into every copy of your cat in the save on install", _scars_build(cfg))
    check("cat rename inside save text", _rename_struct())
    check("palette switching", _palette_switching())

    base_pak = PakReader(os.path.join(cfg.paks_dir, "pakchunk0-Windows.pak"), oodle)
    csv = base_pak.read("Wrc/Content/Gameplay/DataTables/NonAsset/NPC/CatSize.csv")
    check("read base pak", csv.startswith(b"--,Role"), f"{len(base_pak.entries)} files")
    if oodle:
        tuning = base_pak.read("Wrc/Content/Gameplay/DataTables/NonAsset/TuningData.csv")
        check("Oodle decompress (pak)", len(tuning) > 1000 and tuning[:200].isascii())

    io = IoStoreReader(os.path.join(cfg.paks_dir, "pakchunk0-Windows.utoc"), oodle)
    check("read base utoc", len(io.files) > 1000, f"{len(io.files)} files, toc v{io.version}")

    if oodle:
        header = io.container_header()
        raw = io.read_chunk(next(i for i, c in enumerate(io.chunk_ids) if c[11] & 0x3F == 6))
        check("container header round-trip", header.serialize() == raw, f"{len(header.package_ids)} packages")

        ci = io.chunk_index(eyeatlas.PATH)
        original = io.read_chunk(ci)
        meta_ok = _meta_hash(io, ci) == blake3(original, 20)
        check("chunk hash is BLAKE3-160", meta_ok)
        atlas = eyeatlas.EyeAtlas(original)
        check("eye atlas layout", (atlas.width, atlas.height) == (64, 26), f"{atlas.width}x{atlas.height}, rows {atlas.labels[1]}..{atlas.labels[20]}")
        palettes.apply_eyes(atlas, {"Amber": (1.0, 0.0, 1.0)})
        patched = atlas.bytes()
        diff = [i for i in range(len(original)) if original[i] != patched[i]]
        inside = all(atlas.pixel_offset <= i < atlas.pixel_offset + atlas.width * atlas.height * 8 for i in diff)
        check("atlas patch stays inside pixel block", bool(diff) and inside and len(patched) == len(original))

        with tempfile.TemporaryDirectory() as tmp:
            pid = struct.unpack("<Q", io.chunk_ids[ci][:8])[0]
            imports, shaders = header.entry_for(pid)
            w = ModContainerWriter(b"WCTEST01")
            w.add_package(eyeatlas.PATH, io.chunk_ids[ci], patched, imports, shaders)
            w.write(os.path.join(tmp, "t.utoc"), os.path.join(tmp, "t.ucas"))
            mod = IoStoreReader(os.path.join(tmp, "t.utoc"))
            back = mod.read_file(eyeatlas.PATH)
            mh = mod.container_header()
            check("mod container round-trip", back == patched and mh.entry_for(pid) == (imports, shaders)
                  and _meta_hash(mod, mod.chunk_index(eyeatlas.PATH)) == blake3(patched, 20))

    with tempfile.TemporaryDirectory() as tmp:
        pw = PakWriter()
        pw.add("Wrc/Content/Gameplay/DataTables/NonAsset/NPC/CatSize.csv", csv)
        pw.add("Wrc/WCMods/test.txt", b"hello")
        pw.write(os.path.join(tmp, "t_P.pak"), "t_P.pak")
        rp = PakReader(os.path.join(tmp, "t_P.pak"))
        check("pak writer round-trip", rp.read("Wrc/Content/Gameplay/DataTables/NonAsset/NPC/CatSize.csv") == csv
              and rp.read("Wrc/WCMods/test.txt") == b"hello")
        # The engine only finds files whose names are stored the way its own pak stores them; the reader
        # counts any that aren't, in our pak and (as a check on the reader) in the game's.
        check("pak file names stored like the game's", rp.legacy_file_names == 0 and base_pak.legacy_file_names == 0,
              f"ours {rp.legacy_file_names}, game {base_pak.legacy_file_names} stored the old way")

    if oodle:
        ok, detail = _cooked_table(io)
        check("cooked item table: every row read and written back the same, and a new row added", ok, detail)
        ok, detail = _textures(io)
        check("new textures: a copy of the game's with the IDs the game would give it, new pixels in every mip",
              ok, detail)
        ok, detail = _accessory_looks(io)
        check("accessory looks: the game's lists read, new looks and their tags added, the rest as it was",
              ok, detail)
        ok, detail = _items_section(cfg)
        check("new items (items.json): tag, herb row, item table row, recipe, starting count, a game item's "
              "recipe, icons and an accessory's look of a mod's own; mistakes refused",
              ok, detail)
    else:
        log("  [skip] the game's item table, textures and accessories need the Oodle DLL")

    if oodle:
        from . import csvdata
        from .gamefiles import NONASSET
        names = [p for p in base_pak.entries if p.startswith(NONASSET) and p.endswith(".csv")]
        bad = [p for p in names if csvdata.Table(base_pak.read(p).decode("utf-8")).to_text().encode("utf-8") != base_pak.read(p)]
        check("CSV editor round-trips every game table", not bad, f"{len(names)} tables" + (f"; differs: {bad[:3]}" if bad else ""))
        xp = base_pak.read(NONASSET + "CombatBaseExperience.csv").decode("utf-8")
        new, applied, problems = csvdata.apply_edits(xp, {"*": {"BaseExperience": "x2"}, "Fish": {"DifficultyOffset": 1}})
        t0, t1 = csvdata.Table(xp), csvdata.Table(new)
        doubled = all(int(b.fields[1]) == 2 * int(a.fields[1]) for a, b in zip(t0.rows, t1.rows))
        check("CSV edits (multiply + single cell)", doubled and not problems and t1.rows[0].fields[2] == "1"
              and len(new.splitlines()) == len(xp.splitlines()), f"{len(applied)} cells")
        from .sdk import BuildContext
        ok, detail = _names_plan(lambda p: base_pak.read(BuildContext.data_path(p)).decode("utf-8"))
        check("names plan against the game's name tables", ok, detail)

    sav = os.path.join(cfg.save_dir, SAV_NAME)
    if os.path.isfile(sav):
        from .savejson import SaveDoc
        doc = SaveDoc(SaveGame(open(sav, "rb").read()).json_text)
        slot = str(doc.get("Shared/General/CurrentCatSlot"))
        level_path = f"{slot}/GameplayProgression/Level"
        if doc.exists(level_path):
            before = doc.text
            lvl = doc.get(level_path)
            doc.set(level_path, lvl)
            same = doc.text == before
            doc.set(level_path, lvl + 1)
            one_line = sum(1 for x, y in zip(before.splitlines(), doc.text.splitlines()) if x != y) == 1
            inv = f"{slot}/GameplayProgression/State/Inventory"
            inserted = True
            if doc.exists(inv):
                doc.insert(inv, "Gameplay.Inventory.Consumable.SmallHealingHerb", 3)
                inserted = doc.get(inv + "/Gameplay.Inventory.Consumable.SmallHealingHerb") == 3
            check("save editor changes only what it's told to", same and one_line and inserted and doc.get(level_path) == lvl + 1)
            xp_path = f"{slot}/GameplayProgression/Experience"
            if doc.exists(xp_path):
                before = doc.text
                xp = doc.get(xp_path)
                doc.set_many([(level_path, lvl + 2), (xp_path, xp + 5)])
                changed = sum(1 for x, y in zip(before.splitlines(), doc.text.splitlines()) if x != y)
                check("batched save edits", changed == 2 and doc.get(level_path) == lvl + 2 and doc.get(xp_path) == xp + 5)
        raw = open(sav, "rb").read()
        s = SaveGame(raw)
        mirror = os.path.join(cfg.save_dir, JSON_NAME)
        if os.path.isfile(mirror):
            check("save decodes to WrcGame.json", s.json_text == open(mirror, encoding="utf-8", newline="").read())
        # Python's zlib packs differently from the game's, so compare everything except the zlib stream.
        new = s.to_bytes()
        again = SaveGame(new)
        tail = len(raw) - s._data_end
        same_frame = (raw[:s._size_pos] == new[:s._size_pos]
                      and raw[s._data_start:s._data_start + 17] == new[again._data_start:again._data_start + 17]
                      and raw[len(raw) - tail:] == new[len(new) - tail:])
        check("save re-encode keeps structure and content", same_frame and again.json_text == s.json_text)
        b = controls.read_bindings(s.json_text)
        want = "G" if b["keyboard"].get("Player_Interact") == "F" else "F"   # must differ from the current key
        new, applied, _ = controls.apply(s.json_text, {"keyboard": {"Player_Interact": want}})
        check("controls edit touches one value", controls.read_bindings(new)["keyboard"]["Player_Interact"] == want
              and sum(1 for x, y in zip(s.json_text.splitlines(), new.splitlines()) if x != y) == 1,
              f"{len(b['keyboard'])} keyboard / {len(b['gamepad'])} gamepad actions")
    else:
        log("  [skip] no save yet")
    return all(results)


def _name_hashes():
    from .cityhash import name_hash
    # Stored hashes from the game's name maps: names for each of CityHash64's length branches (1-3, 4-7,
    # 8-16, 17-32, 33-64 bytes, and longer).
    vectors = [("1", 0x811F023A122D0BE1), ("10", 0xFE9BEBCA6BBFE5AE), ("Ear", 0xF5BC7B7C8B0DF45C),
               ("NewRow", 0x8C07177607C72E43), ("BlueprintType", 0x136AFC1B797CDD04),
               ("Gameplay.Combat.Character.Badger", 0xC06922E4C7EC49BA),
               ("Gameplay.Combat.Attack.Ancestor.1", 0x2539218B357C41AC),
               ("/Game/Art/UXD/Textures/gui_icons/gui_icons_accesories/T_UI_Accessory_AutumnWreath_D",
                0x2382F8DFD9CE00C9)]
    return all(name_hash(n) == h for n, h in vectors)


def _unversioned_headers():
    from .cooked import _Reader, read_header, split_name, write_header
    cases = [([], set()), ([0], set()), ([0, 1, 2, 3, 4, 5, 6], {4, 5, 6}), ([0, 2, 3, 9], {3}),
             (list(range(130)), set(range(0, 130, 7))), ([200, 201], set()), (list(range(40)), {1, 33})]
    for present, zero in cases:
        if read_header(_Reader(write_header(present, zero))) != (present, zero):
            return False
    return (split_name("NewRow_45") == ("NewRow", 46) and split_name("Foo_0") == ("Foo", 1)
            and split_name("Foo_01") == ("Foo_01", 0) and split_name("Gameplay.Item") == ("Gameplay.Item", 0))


def _cooked_table(io):
    from . import cooked
    path, schema = cooked.TABLES["DT_QuestObjectsInfo"]
    data = io.read_file(path)
    dt = cooked.DataTable(data, schema)
    same = dt.bytes() == data
    count = len(dt.rows)
    ok = same and dt.check_encoder() and dt.pkg.check_hashes(len(dt.pkg.names)) and count > 100
    tag = "Gameplay.Inventory.Consumable.WCModsSelfTest"
    _, herb = dt.find("itemTag", "Gameplay.Inventory.Consumable.SmallHealingHerb")
    dt.add("WCMods_SelfTest", {"itemTag": tag, "Name": cooked.base_text("Test Herb", tag + ".Name"),
                               "Description": cooked.base_text("Héals a little", tag + ".Description"),
                               "Icon": herb["Icon"], "ItemGroupIcon": 1})
    try:                                    # a value it can't write is refused, and the table is as it was
        dt.add("WCMods_Bad", {"itemTag": tag + "Bad", "Name": "not a text value"})
        refused = False
    except ValueError:
        refused = len(dt.rows) == count + 1
    back = cooked.DataTable(dt.bytes(), schema)
    name, row = back.rows[-1]
    added = (name == "WCMods_SelfTest" and row["itemTag"] == tag and row["Description"]["text"] == "Héals a little"
             and "ItemRarity" not in row and row["ItemGroupIcon"] == 1 and back.check_encoder() and back.pkg.check_hashes(len(back.pkg.names))
             and back.rows[:-1] == dt.rows[:-1] and refused)
    return ok and added, f"{count} rows" + ("" if same else "; rebuilt package differs")


def _png_file(width, height, ctype, depth, rows, palette=None, trns=None):
    """A PNG as paint programs save them: each row with another of the five filters."""
    import zlib
    from .png import SIGNATURE
    bpp = max(1, {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype] * depth // 8)
    raw, prev = bytearray(), bytes(len(rows[0]))
    for y, line in enumerate(rows):
        f = y % 5
        raw.append(f)
        for i, v in enumerate(line):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
            paeth = a if pa <= pb and pa <= pc else b if pb <= pc else c
            raw.append((v - (0, a, b, (a + b) >> 1, paeth)[f]) & 0xFF)
        prev = line

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    out = SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, ctype, 0, 0, 0))
    if palette:
        out += chunk(b"PLTE", palette)
    if trns:
        out += chunk(b"tRNS", trns)
    return out + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")


def _pictures():
    from . import bcn, png, recolor
    w, h = 9, 6
    rgba = bytes(v for y in range(h) for x in range(w) for v in (x * 28, y * 50, x * y * 5, 255 - x * 20))
    ok = png.read(png.write(w, h, rgba)) == (w, h, rgba)
    # 8-bit RGB; 2-bit palette with a transparent colour; 16-bit grey + alpha.
    rgb = [bytes(v for x in range(5) for v in (x * 60, y * 80, 200 - x * 40)) for y in range(4)]
    ok = ok and png.read(_png_file(5, 4, 2, 8, rgb)) == (5, 4, b"".join(
        bytes(r[i:i + 3]) + b"\xff" for r in rgb for i in range(0, 15, 3)))
    pal = bytes((10, 20, 30, 200, 100, 0, 0, 255, 0, 250, 250, 250))
    idx = [[(x + y) % 4 for x in range(6)] for y in range(3)]
    packed = [bytes((r[0] << 6 | r[1] << 4 | r[2] << 2 | r[3], r[4] << 6 | r[5] << 4)) for r in idx]
    want = b"".join(pal[3 * i:3 * i + 3] + (b"\x00" if i == 1 else b"\xff") for r in idx for i in r)
    ok = ok and png.read(_png_file(6, 3, 3, 2, packed, pal, b"\xff\x00")) == (6, 3, want)
    ga = [b"".join(struct.pack(">HH", (x * 30000 + y) & 0xFFFF, 65535 - x * 1000) for x in range(3)) for y in range(3)]
    want = b"".join(bytes((r[4 * x], r[4 * x], r[4 * x], r[4 * x + 2])) for r in ga for x in range(3))
    ok = ok and png.read(_png_file(3, 3, 4, 16, ga)) == (3, 3, want)
    # Colours DXT can hold exactly come back exactly; a gradient comes back close.
    two = bytes(v for y in range(8) for x in range(8) for v in ((255, 0, 0, 255) if x < 4 else (0, 0, 255, 0)))
    opaque = bytes(255 if i % 4 == 3 else v for i, v in enumerate(two))      # DXT1 has no alpha
    ok = (ok and bcn.decode("PF_DXT5", 8, 8, bcn.encode("PF_DXT5", 8, 8, two)) == two
          and bcn.decode("PF_DXT1", 8, 8, bcn.encode("PF_DXT1", 8, 8, two)) == opaque)
    grad = bytes(v for y in range(16) for x in range(16) for v in (x * 16, 255 - x * 12, 128 + y, 255))
    back = bcn.decode("PF_DXT5", 16, 16, bcn.encode("PF_DXT5", 16, 16, grad))
    ok = ok and sum(abs(a - b) for a, b in zip(grad, back)) / len(grad) < 2
    ok = ok and bcn.size("PF_DXT1", 2048, 2048) == 2048 * 2048 // 2 and bcn.size("PF_DXT5", 1, 1) == 16
    # Recolours: grey in the tint's colour, red turned to cyan, alpha kept; and mistakes refused.
    tinted = recolor.apply(bytes((128, 128, 128, 77, 255, 0, 0, 255)), {"tint": "#a8c4ff"})
    turned = recolor.apply(bytes((255, 0, 0, 9)), {"hue": 180})
    ok = ok and all(abs(a - b) <= 2 for a, b in zip(tinted[:3], (168, 196, 255))) and tinted[3] == 77
    ok = ok and turned == bytes((0, 255, 255, 9))
    for bad in ({"tint": "blue"}, {"hue": 400}, {"strength": 0.5}, {"tint": "#ffffff", "glow": 1}):
        try:
            recolor.check(bad, "x")
            return False
        except ValueError:
            pass
    return ok


def _textures(io):
    from . import accessories, texture
    from .sections.items import ICON_LIKE
    header = io.container_header()
    # The game's own IDs, worked out from names: the package's, its chunk's and its export's.
    path = texture.content_path(ICON_LIKE)
    pid = texture.package_id(ICON_LIKE)
    data = io.read_file(path)
    tex = texture.Texture(data)
    pkg = tex.pkg
    name = pkg.names[struct.unpack_from("<I", pkg.data, pkg._export_map + 16)[0]]
    ids = (pid in header.package_ids and io.chunk_ids[io.chunk_index(path)] == texture.chunk_id(pid, 1)
           and struct.unpack_from("<Q", pkg.data, pkg._export_map + 56)[0] == texture.export_hash(name))
    same = tex.files() == (data, None)
    # A copy under a new name with new pixels, read back.
    colour = (40, 200, 90, 255)
    tex.set_image(tex.width, tex.height, bytes(colour) * (tex.width * tex.height))
    tex.rename("/Game/WCMods/selftest/T_SelfTest", "T_SelfTest")
    new, _ = tex.files()
    back = texture.Texture(new)
    bp = back.pkg
    pixels = all(all(abs(a - b) <= 4 for a, b in zip(back.image(m)[2][:4], colour)) for m in range(len(back.mips)))
    renamed = ("/Game/WCMods/selftest/T_SelfTest" in bp.names and "T_SelfTest" in bp.names and name not in bp.names
               and bp.check_hashes(len(bp.names))
               and struct.unpack_from("<Q", bp.data, bp._export_map + 56)[0] == texture.export_hash("T_SelfTest"))
    # A texture with big mips in its .ubulk (an accessory's look) is copied whole.
    look = accessories.read_variations(io.read_file(accessories.GUI_MANAGER))["DogCollar"][0]
    big = texture.content_path(look.split(".", 1)[0])
    bulk_path = big[:-len(".uasset")] + ".ubulk"
    big_data, bulk = io.read_file(big), io.read_file(bulk_path)
    look_pid = texture.package_id(look.split(".", 1)[0])
    copy = texture.Texture(big_data, bulk)
    in_bulk = (copy.files() == (big_data, bulk) and any(m[2] for m in copy.mips)
               and io.chunk_ids[io.chunk_index(bulk_path)] == texture.chunk_id(look_pid, texture.CHUNK_BULK))
    ok = ids and same and pixels and renamed and in_bulk
    return ok, f"{tex.width} x {tex.height} {tex.format}, {copy.width} x {copy.height} {copy.format} in {len(copy.mips)} mips" + (
        "" if ok else f"; ids {ids}, same {same}, pixels {pixels}, renamed {renamed}, bulk {in_bulk}")


def _accessory_looks(io):
    from . import accessories
    from .cooked import ZenPackage
    data = io.read_file(accessories.GUI_MANAGER)
    looks = accessories.read_variations(data)
    n, m = len(looks["DogCollar"]), len(looks["RopeNecklace"])
    new = [{"name": "DogCollar", "var": n + 1, "path": "/Game/WCMods/t/T_A.T_A",
            "tag": f"Gameplay.Inventory.Cosmetic.Neck.DogCollar.{n + 1}"},
           {"name": "DogCollar", "var": n + 2, "path": "/Game/WCMods/t/T_B.T_B",
            "tag": f"Gameplay.Inventory.Cosmetic.Neck.DogCollar.{n + 2}"},
           {"name": "RopeNecklace", "var": m + 1, "path": "/Game/WCMods/t/T_C.T_C",
            "tag": f"Gameplay.Inventory.Cosmetic.Neck.RopeNecklace.{m + 1}"}]
    def tag_list(package):
        pkg = ZenPackage(package)
        off, size = pkg.export(accessories._defaults(pkg))
        return pkg, accessories._tag_list(pkg, pkg.export_data[off:off + size])[1]

    out = accessories.add_looks(data, new)
    after = accessories.read_variations(out)
    pkg, tags = tag_list(out)
    before_tags = tag_list(data)[1]
    ok = (after["DogCollar"] == looks["DogCollar"] + ["/Game/WCMods/t/T_A.T_A", "/Game/WCMods/t/T_B.T_B"]
          and after["RopeNecklace"] == looks["RopeNecklace"] + ["/Game/WCMods/t/T_C.T_C"]
          and all(after[k] == v for k, v in looks.items() if k not in ("DogCollar", "RopeNecklace"))
          and tags == before_tags + [e["tag"] for e in new] and pkg.check_hashes(len(pkg.names)) and len(looks) > 40)
    for bad in ([dict(new[0], var=n + 2)], [dict(new[0], tag=before_tags[0])], [dict(new[0], name="NoSuchThing")]):
        try:
            accessories.add_looks(data, bad)
            ok = False
        except ValueError:
            pass
    return ok, f"{len(looks)} accessories, {len(before_tags)} tags"


def _items_section(cfg):
    import json
    from . import accessories, mods, pipeline, png, texture
    from .gamefiles import GameFiles
    looks = accessories.read_variations(GameFiles(cfg).read(accessories.GUI_MANAGER))
    collar = f"Gameplay.Inventory.Cosmetic.Neck.DogCollar.{len(looks['DogCollar']) + 1}"
    good = {"items": [
        {"id": "WCModsTestHerb", "like": "MediumHealingHerb", "name": "Test Herb", "description": "Heals.",
         "recipe": {"Dandelion": 2, "WCModsTestStone": 1}, "rarity": "Rare", "give": 2},
        {"id": "WCModsTestStone", "kind": "material", "name": "Test Stone", "description": "A stone.",
         "icon": {"from": "Rock", "brightness": 1.2}},
        {"id": "WCModsTestHerb", "kind": "material", "name": "Test Herb Seed", "description": "Same id, a material.",
         "icon": "Rock"},
        {"id": "WCModsTestPicture", "like": "SmallHealingHerb", "name": "Test Picture", "description": "Its own icon.",
         "icon": "icons/test.png"},
        {"id": "WCModsTestCollar", "like": "Neck.DogCollar.1", "name": "Test Collar", "description": "Blue.",
         "texture": {"tint": "#a8c4ff"}, "recipe": {"Bone": 1}}],
        "recipes": {"Cosmetic.Head.MossPatch.1": {"Moss": 3, "WCModsTestStone": 1}}}
    bad = {"items": [
        {"id": "SmallCatnip", "kind": "consumable", "name": "Again", "description": "x", "like": "SmallCatnip"},
        {"id": "WCModsCrown", "kind": "accessory", "name": "Crown", "description": "x"},
        {"id": "WCModsNoStone", "like": "SmallHealingHerb", "name": "x", "description": "x", "recipe": {"Moonrock": 1}},
        {"id": "WCModsWhat", "like": "SmallHealingHerb", "name": "x", "description": "x", "effect": "Gameplay.Effect.Fly"},
        {"id": "WCModsHat", "like": "Head.BigLeaf.1", "name": "x", "description": "x", "texture": {"tint": "#ffffff"}},
        {"id": "WCModsShiny", "like": "SmallHealingHerb", "name": "x", "description": "x", "texture": {"tint": "#ffffff"}},
        {"id": "WCModsLost", "like": "SmallHealingHerb", "name": "x", "description": "x", "icon": "missing.png"},
        {"id": "WCModsOut", "like": "SmallHealingHerb", "name": "x", "description": "x", "icon": "../good/icons/test.png"}],
        "recipes": {"Cosmetic.Head.NoSuchHat.1": {"Moss": 1}}}
    colour = (200, 60, 160, 255)
    picture = png.write(32, 32, bytes(colour) * 1024)
    with tempfile.TemporaryDirectory() as tmp:
        typo = {"items": [{"id": "WCModsTypo", "like": "SmallHealingHerb", "name": "x", "description": "x", "icon": 5}]}
        tint = {"items": [{"id": "WCModsBlue", "like": "SmallHealingHerb", "name": "x", "description": "x",
                           "icon": {"tint": "blue"}}]}
        root = _mods_folder(tmp, {"good": ({"name": "Good", "enabled": True},
                                           {"items.json": json.dumps(good), "icons/test.png": picture}),
                                  "bad": ({"name": "Bad", "enabled": True}, {"items.json": json.dumps(bad)}),
                                  "typo": ({"name": "Typo", "enabled": True}, {"items.json": json.dumps(typo)}),
                                  "tint": ({"name": "Tint", "enabled": True}, {"items.json": json.dumps(tint)})})
        out = pipeline.build(cfg, mods.discover(root), os.path.join(tmp, "out"), log=lambda m: None)
        rows = out.get("table_rows", {}).get("DT_QuestObjectsInfo", [])
        csv = out.get("csv_changes", {})
        use = [c for c in csv.get("Wrc/Content/Gameplay/DataTables/NonAsset/Consumables.csv", []) if c["by"] == "good"]
        recipe = [c for c in csv.get("Wrc/Content/Gameplay/DataTables/NonAsset/BarteringCost.csv", [])
                  if c["by"] == "good"]
        warned = [w for w in out["warnings"] if w.startswith("items: bad:")]
        given = [o for o in out["save_ops"] if o.get("key") == "Gameplay.Inventory.Consumable.WCModsTestHerb"]
        has_save = os.path.isfile(os.path.join(cfg.save_dir, SAV_NAME))
        gave = ((len(given) == 1 and given[0]["value"] == 2 and given[0].get("only_new")) if has_save else
                any("no save yet" in w for w in out["warnings"]))
        rep = out["sections"]["items"]
        ok = gave and (rep["status"] == "partial" and any("typo" in e and "should be text" in e for e in rep["errors"])
              and any("tint" in e and "colour like" in e for e in rep["errors"])
              and sorted(r["row"] for r in rows) == sorted([
                  "WCMods_Consumable_WCModsTestHerb", "WCMods_Materials_WCModsTestHerb",
                  "WCMods_Materials_WCModsTestStone", "WCMods_Consumable_WCModsTestPicture",
                  "WCMods_" + collar[len("Gameplay.Inventory."):].replace(".", "_")]) and len(use) == 2
              and sorted(c["row"] for c in recipe) == sorted(["Gameplay.Inventory.Consumable.WCModsTestHerb", collar,
                                                              "Gameplay.Inventory.Cosmetic.Head.MossPatch.1"])
              and "Wrc/Config/Tags/WCModsItems.ini" in out["files"] and len(warned) == 9
              and all(any(s in w for w in warned) for s in ('needs "like"', "first look", "only accessories",
                                                             "no picture", "own folder"))
              and "zzz_WCMods_P.utoc" in out["outputs"])
        # What went into wcmods' container: the new textures (the look with its .ubulk), the look in the
        # game's list, and the icons in the item table.
        made = IoStoreReader(os.path.join(tmp, "out", "zzz_WCMods_P.utoc"))
        look = "/Game/WCMods/good/T_WCModsTestCollar_BC"
        icon = "/Game/WCMods/good/T_WCModsTestPicture_Icon"
        stone = "/Game/WCMods/good/T_WCModsTestStone_Icon"
        packed = (ok and all(texture.content_path(p) in made.files for p in (look, icon, stone))
                  and texture.content_path(look)[:-len(".uasset")] + ".ubulk" in made.files)
        if packed:
            from . import cooked
            worn = accessories.read_variations(made.read_file(accessories.GUI_MANAGER))
            path, schema = cooked.TABLES["DT_QuestObjectsInfo"]
            table = {v["itemTag"]: v for _, v in cooked.DataTable(made.read_file(path), schema).rows}
            pixels = texture.Texture(made.read_file(texture.content_path(icon))).image(0)[2]
            packed = (worn["DogCollar"] == looks["DogCollar"] + [look + ".T_WCModsTestCollar_BC"]
                      and table["Gameplay.Inventory.Consumable.WCModsTestPicture"]["Icon"]["package"] == icon
                      and all(abs(a - b) <= 4 for a, b in zip(pixels[:4], colour)))
        return ok and packed, f"{len(rows)} rows, {len(warned)} refused" + ("" if ok else f"; {out['warnings']}")


def _script_mod(cfg):
    """A script mod's scripts/ and settings.json become a UE4SS mod whose main.lua sets MOD and runs them."""
    import json
    import tempfile
    from .mods import Mod
    from .sdk import BuildContext
    from .sections.scripts import ScriptsSection
    with tempfile.TemporaryDirectory() as tmp:
        folder = os.path.join(tmp, "my-script")
        os.makedirs(os.path.join(folder, "scripts"))
        with open(os.path.join(folder, "mod.json"), "w") as f:
            json.dump({"name": "My Script", "enabled": True}, f)
        with open(os.path.join(folder, "settings.json"), "w") as f:
            json.dump({"_help": "notes", "on": True, "speed": 1.5, "tint": "#ffcc00"}, f)
        with open(os.path.join(folder, "scripts", "main.lua"), "w") as f:
            f.write('MOD.log("hi %s", tostring(MOD.settings.on))\n')
        with open(os.path.join(folder, "scripts", "helper.lua"), "w") as f:
            f.write("return {}\n")
        mod, sec = Mod(folder), ScriptsSection()
        ctx = BuildContext(cfg, None, tmp, log=lambda m: None)
        ctx.cfg = type("Cfg", (), {"data": {"allow_code_mods": True}, "ue4ss_mods_dir": tmp})()
        ctx.begin(sec.id)
        sec.build(ctx, [(mod, sec.collect(mod, ctx))])
        files, _ = ctx.ue4ss_mods.get("WCModsScript_my_script", ({}, None))
        main = files.get("Scripts/main.lua", b"").decode()
        return (not luacheck.check(main) and not re.findall(r"@[A-Z_]+@", main) and '["speed"] = 1.5' in main
                and "Scripts/mod/helper.lua" in files and "Scripts/mod/main.lua" in files and not ctx.warnings)


def _tiny_dll(exports, dll=True):
    """The smallest 64-bit PE wcmods reads: one section holding an export table with `exports`."""
    names = b"".join(n.encode() + b"\0" for n in exports)
    rva, raw = 0x1000, 0x200
    table = rva + 40                          # AddressOfNames, right after the export directory
    first = table + 4 * len(exports)          # the names themselves
    offsets, at = [], first
    for n in exports:
        offsets.append(at)
        at += len(n) + 1
    edata = struct.pack("<IIHHIIIIIII", 0, 0, 0, 0, 0, 1, len(exports), len(exports), 0, table, 0)
    edata += struct.pack(f"<{len(exports)}I", *offsets) + names
    head = bytearray(raw)
    head[:2], head[0x3C:0x40] = b"MZ", struct.pack("<I", 0x40)
    head[0x40:0x44] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", head, 0x44, 0x8664, 1, 0, 0, 0, 0xF0, 0x2022 if dll else 0x0022)
    opt = 0x58
    struct.pack_into("<H", head, opt, 0x20B)
    struct.pack_into("<Q", head, opt + 24, 0x180000000)
    struct.pack_into("<I", head, opt + 56, rva + 0x1000)
    struct.pack_into("<I", head, opt + 108, 16)
    struct.pack_into("<II", head, opt + 112, rva, len(edata))
    struct.pack_into("<8sIIIIIIHHI", head, opt + 0xF0, b".rdata", 0x1000, rva, len(edata), raw, 0, 0, 0, 0, 0x40000040)
    return bytes(head) + edata


def _cpp_mod():
    """A C++ mod's dlls/main.dll becomes a UE4SS mod with a wcmods.json naming the mod and its settings, as long
    as its build.json fits the game's UE4SS."""
    import json
    from . import cppmods, pe
    from .mods import Mod
    from .sdk import BuildContext
    from .sections import cpp
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        win64 = os.path.join(tmp, "Win64")
        os.makedirs(os.path.join(win64, "ue4ss"))
        for rel, text in (("dwmapi.dll", "MZ"), ("ue4ss/UE4SS.dll", "MZ ue4ss"),
                          ("ue4ss/UE4SS.log", "[x] UE4SS - v3.0.1 Beta #0 - Git SHA #83330635\n")):
            with open(os.path.join(win64, rel), "w") as f:
                f.write(text)
        game = cpp.ue4ss.loader_identity(win64)
        if not game or game["commit"] != "83330635":
            problems.append(f"the game's UE4SS read as {game}")

        def make(mod_id, exports=cpp.EXPORTS, built_for=None, source=False, dll=True):
            folder = os.path.join(tmp, "mods", mod_id)
            os.makedirs(os.path.join(folder, "dlls"))
            with open(os.path.join(folder, "mod.json"), "w") as f:
                json.dump({"name": mod_id.title(), "enabled": True, "version": "1.2"}, f)
            if exports is not None:
                with open(os.path.join(folder, "dlls", "main.dll"), "wb") as f:
                    f.write(_tiny_dll(exports, dll))
            if built_for is not None:
                with open(os.path.join(folder, "dlls", "build.json"), "w") as f:
                    json.dump(built_for, f)
            if source:
                os.makedirs(os.path.join(folder, "cpp"))
                with open(os.path.join(folder, "cpp", "CMakeLists.txt"), "w") as f:
                    f.write("wcmods_mod(${WCMODS_TARGET} src/main.cpp)\n")
            return Mod(folder)

        good = make("good", built_for={"ue4ss": "8333063595fa3c49ad307f3b0f732accbb760d25"})
        with open(os.path.join(good.folder, "settings.json"), "w") as f:
            json.dump({"speed": 2}, f)
        with open(os.path.join(good.folder, "dlls", "helper.dll"), "wb") as f:
            f.write(b"MZ")
        other = make("other", built_for={"ue4ss": "aaaa1111", "ue4ss_dll": "0" * 40})
        unknown = make("unknown")
        sec = cpp.CppSection()
        ctx = BuildContext(None, None, tmp, log=lambda m: None)
        ctx.cfg = type("Cfg", (), {"data": {"allow_code_mods": True}, "win64_dir": win64})()
        ctx.begin(sec.id)
        sec.build(ctx, [(m, sec.collect(m, ctx)) for m in (good, other, unknown)])
        files = ctx.ue4ss_mods.get("WCModsCpp_good", ({}, None))[0]
        info = json.loads(files.get("wcmods.json", b"{}"))
        if sorted(files) != ["dlls/helper.dll", "dlls/main.dll", "enabled.txt", "wcmods.json"]:
            problems.append(f"good installs {sorted(files)}")
        if info.get("settings") != {"speed": 2} or info.get("version") != "1.2" or not info.get("settings_file"):
            problems.append(f"wcmods.json is {info}")
        if "WCModsCpp_other" in ctx.ue4ss_mods or not any("other:" in w and "left out" in w for w in ctx.warnings):
            problems.append("a DLL built for another UE4SS isn't left out")
        if "WCModsCpp_unknown" not in ctx.ue4ss_mods or not any("unknown:" in w and "can't tell" in w for w in ctx.warnings):
            problems.append("a DLL without build.json isn't installed with a warning")

        for mod, want in ((make("bare", exports=["DllMain"]), "doesn't export start_mod"),
                          (make("exe", dll=False), "isn't a 64-bit Windows DLL"),
                          (make("unbuilt", exports=None, source=True), "cpp build unbuilt")):
            try:
                sec.collect(mod, ctx)
                problems.append(f"{mod.id} wasn't refused")
            except ValueError as e:
                if want not in str(e):
                    problems.append(f"{mod.id}: {e}")

        ctx = BuildContext(None, None, tmp, log=lambda m: None)
        ctx.cfg = type("Cfg", (), {"data": {}, "win64_dir": win64})()
        ctx.begin(sec.id)
        sec.build(ctx, [(good, sec.collect(good, ctx))])
        if ctx.ue4ss_mods or "allow_code_mods" not in " ".join(ctx.warnings):
            problems.append("installed without allow_code_mods")

        if pe.Image(os.path.join(good.folder, "dlls", "main.dll")).exports() != set(cpp.EXPORTS):
            problems.append("exports misread")
        if (cpp.matches({"ue4ss": "83330635abc"}, {"commit": "83330635", "dll": "x"}) is not True
                or cpp.matches({"ue4ss_dll": "x"}, {"commit": None, "dll": "x"}) is not True
                or cpp.matches({"ue4ss": "1234567"}, {"commit": None, "dll": "x"}) is not None):
            problems.append("matches() is wrong")
        project = cppmods.project(tmp, [good])
        if 'add_subdirectory("' not in project or "set(WCMODS_TARGET wcmods_good)" not in project:
            problems.append("cpp build's project is wrong")
    offsets = game_lua.offsets_json(None, 1)["members"]
    if offsets.get("/Script/SwtQuest.SwtQuestResourceComponent:WCM_Value", {}).get("offset") != 0x10C:
        problems.append("offsets.json is wrong")
    return not problems, "; ".join(problems[:3])


def _cpp_sdk():
    """The C++ SDK can't be compiled here (that needs Visual Studio and UE4SS's source), so this checks what it
    can: the headers WCMods.hpp includes exist, every call they declare (outside `detail`) is in docs/SDK.md's
    "C++ mods" section, and the cpp template includes the SDK and ends with WCMODS_MOD."""
    here = os.path.dirname(os.path.abspath(__file__))
    sdk = os.path.join(here, "cpp_sdk", "include")
    umbrella = os.path.join(sdk, "WCMods", "WCMods.hpp")
    problems = []
    with open(umbrella, encoding="utf-8") as f:
        headers = re.findall(r"#include <(WCMods/\w+\.hpp)>", f.read())
    if len(headers) < 4:
        problems.append(f"WCMods.hpp includes only {headers}")
    docs_path = os.path.join(os.path.dirname(here), "docs", "SDK.md")
    with open(docs_path, encoding="utf-8") as f:
        docs = f.read()
    cpp_docs = docs[docs.index("## C++ mods"):docs.index("## JavaScript")] if "## C++ mods" in docs else ""
    names = set()
    for rel in headers:
        path = os.path.join(sdk, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            problems.append(f"{rel} is missing")
            continue
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        in_detail, access = False, "public"
        for line in lines:
            # Each `namespace detail` block ends with its "} // namespace detail" line (a brace count would
            # be thrown by the braces in format strings).
            if re.match(r"\s*namespace detail\b", line):
                in_detail = True
            if in_detail:
                if re.match(r"\s*} // namespace detail", line):
                    in_detail = False
                continue
            # A class's private members aren't calls: track the access specifier in force.
            if m := re.match(r"\s{4}(class|struct)\s+\w+", line):
                access = "private" if m.group(1) == "class" else "public"
            elif re.match(r"\s{4}};", line):
                access = "public"
            elif m := re.match(r"\s*(public|private|protected):", line):
                access = m.group(1)
            m = re.match(r"\s{4,8}(?:inline )?auto (\w+)\(", line)
            if m and not m.group(1).startswith("operator") and access == "public":
                names.add(m.group(1))
    private = set()   # names declared public that still aren't calls of the SDK's (none now)
    undocumented = sorted(n for n in names - private
                          if f"{n}(" not in cpp_docs and f"{n}<" not in cpp_docs and f"`{n}`" not in cpp_docs)
    if undocumented:
        problems.append(f"not in SDK.md: {', '.join(undocumented[:8])}")
    if len(names) < 40:
        problems.append(f"only {len(names)} calls found in the headers")
    template = os.path.join(here, "templates", "cpp", "cpp", "src", "main.cpp")
    with open(template, encoding="utf-8") as f:
        text = f.read()
    if "#include <WCMods/WCMods.hpp>" not in text or not text.rstrip().endswith(")") or "WCMODS_MOD(" not in text:
        problems.append("the cpp template doesn't include WCMods.hpp and end with WCMODS_MOD")
    # The test mod (tests/cpp-sdk) calls every one of them, so what's documented is what's checked in the game.
    test_src = os.path.join(os.path.dirname(here), "tests", "cpp-sdk", "cpp", "src")
    tested = ""
    for name in sorted(os.listdir(test_src)) if os.path.isdir(test_src) else []:
        with open(os.path.join(test_src, name), encoding="utf-8") as f:
            tested += f.read()
    # A call as the SDK's: not `Json::object(` for the SDK's object(path), and not part of a longer name.
    untested = sorted(n for n in names - private if not re.search(rf"(?<![:\w]){n}\s*[(<]", tested))
    if untested:
        problems.append(f"not called by tests/cpp-sdk: {', '.join(untested[:8])}")
    test_py = os.path.join(os.path.dirname(here), "tests", "game", "test_cpp_sdk.py")
    if not os.path.isfile(test_py):
        problems.append("tests/game/test_cpp_sdk.py is missing")
    return not problems, "; ".join(problems[:3]) or f"{len(names)} calls, all in SDK.md and tests/cpp-sdk"


def _agent_parts():
    """The agent's PNGs round-trip, a menu answer reads as rows, and tests/game's files load (no game needed)."""
    from .agent import image, menu as agent_menu, runner
    pic = image.Image(4, 3, bytes(range(36)))
    with tempfile.TemporaryDirectory() as tmp:
        path = pic.save(os.path.join(tmp, "p.png"))
        back = image.Image.load(path)
    small = image.Image.from_bgra(bytes([10, 20, 30, 255]) * 16, 4, 4).scaled(0.5)
    page = agent_menu.Page({"page": "Stats", "title": "Stats", "rows": [
        {"n": 1, "kind": "field", "label": "Name", "value": "Callie"},
        {"n": 2, "kind": "slider", "label": "Health", "value": 200, "options": [0, 233]}]})
    tests = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "game")
    found = runner.discover([tests]) if os.path.isdir(tests) else []
    return (back.rgb == pic.rgb and (small.width, small.height, small.pixel(0, 0)) == (2, 2, (30, 20, 10))
            and page.get("name") == "Callie" and page.find("Health").options == [0, 233]
            and "Health: 200   (0..233)   <slider>" in page.text() and (not os.path.isdir(tests) or len(found) > 10))


def _zip(path, files):
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


def _mod_zips():
    """A mod's folder a level down in a .zip is added as mods/<its name>; a second copy replaces it and
    keeps the first in backups/mods; paths that climb out are refused before anything is written."""
    import json
    from . import modzip
    from .mods import Mod
    with tempfile.TemporaryDirectory() as tmp:
        root, backups = os.path.join(tmp, "mods"), os.path.join(tmp, "backups")
        os.makedirs(root)
        meta = json.dumps({"name": "Cool Tweaks", "version": "1.2", "uses": ["mod-menu"]})
        z = _zip(os.path.join(tmp, "a.zip"), {"Cool Tweaks/mod.json": meta, "Cool Tweaks/scripts/main.lua": "",
                                              "Cool Tweaks/settings.json": "{}", "__MACOSX/x": ""})
        found = modzip.inspect(z, root)
        added = modzip.add_zip(z, root, backups)
        again = modzip.add_zip(z, root, backups)
        m = Mod(os.path.join(root, "cool-tweaks"))
        refused = 0
        for bad in ("../evil/mod.json", "/abs/mod.json", "C:/x/mod.json"):
            try:
                modzip.add_zip(_zip(os.path.join(tmp, "bad.zip"), {bad: "{}"}), root, backups)
            except ValueError:
                refused += 1
        return (len(found) == 1 and found[0]["code"] and found[0]["kinds"] == ["in-game script"]
                and added[0]["id"] == "cool-tweaks" and again[0]["replaced"] and m.version == "1.2" and m.menu_page()
                and refused == 3 and sorted(os.listdir(root)) == ["cool-tweaks"]
                and modzip.removed(backups)[0]["why"] == "replaced")


def _mod_zip_guards():
    """Names are checked as Windows sees them (Section.py is code; MOD.JSON beside mod.json is refused);
    a mod.json value Mod can't use is refused; "builtin" from a download is dropped; a mod added on
    turns on what it requires; a removed mod whose id ends in a number comes back under that id."""
    import json
    from . import modzip
    from .mods import Mod
    with tempfile.TemporaryDirectory() as tmp:
        root, backups = os.path.join(tmp, "mods"), os.path.join(tmp, "backups")
        os.makedirs(os.path.join(root, "helper"))
        with open(os.path.join(root, "helper", "mod.json"), "w") as f:
            json.dump({"name": "Helper", "enabled": False}, f)
        hidden = modzip.inspect(_zip(os.path.join(tmp, "a.zip"), {"q/mod.json": "{}", "q/Section.py": ""}), root)
        refused = 0
        for files in ({"q/mod.json": "{}", "q/MOD.JSON": "{}"}, {"q/mod.json": '{"priority": "high"}'}):
            try:
                modzip.inspect(_zip(os.path.join(tmp, "b.zip"), files), root)
            except ValueError:
                refused += 1
        added = modzip.add_zip(_zip(os.path.join(tmp, "c.zip"), {"pack-2/mod.json": json.dumps(
            {"name": "Pack", "builtin": True, "requires": ["helper"]})}), root, backups)
        claimed = Mod(os.path.join(root, "pack-2")).builtin
        helper_on = Mod(os.path.join(root, "helper")).enabled
        gone = modzip.remove(Mod(os.path.join(root, "pack-2")), backups)
        back = modzip.restore(backups, gone, root)
        return (hidden[0]["code"] and refused == 2 and not claimed and helper_on
                and added[0]["also_on"] == ["Helper"] and back == "pack-2")


def _mods_folder(tmp, mods):
    import json
    root = os.path.join(tmp, "mods")
    for mod_id, (meta, files) in mods.items():
        os.makedirs(os.path.join(root, mod_id))
        with open(os.path.join(root, mod_id, "mod.json"), "w") as f:
            json.dump(meta, f)
        for name, content in files.items():
            path = os.path.join(root, mod_id, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb" if isinstance(content, bytes) else "w") as f:
                f.write(content)
    return root


def _requirements(cfg):
    from . import mods, pipeline
    with tempfile.TemporaryDirectory() as tmp:
        root = _mods_folder(tmp, {"needy": ({"name": "Needy", "requires": ["helper"], "enabled": False}, {}),
                                  "helper": ({"name": "Helper", "enabled": False}, {}),
                                  "lost": ({"name": "Lost", "requires": ["ghost"], "enabled": True}, {})})
        on, _ = mods.switch(mods.discover(root), "needy", True)
        _, blocked = mods.switch(mods.discover(root), "helper", False)
        out = pipeline.build(cfg, mods.discover(root), os.path.join(tmp, "out"), log=lambda m: None)
        rep = out["sections"].get("requirements", {})
        return (sorted(on) == [("helper", True), ("needy", True)] and blocked == ["needy"]
                and "lost" not in out["mods"] and "needy" in out["mods"] and rep.get("status") == "failed"
                and any("ghost" in e for e in rep.get("errors", [])))


def _menu_mod(cfg):
    from . import ingame
    # Menu settings still in wcmods.json would win over the test's menu.json; they're put back after.
    kept = {k: cfg.data.pop(k) for k in ingame.LEGACY.values() if k in cfg.data}
    try:
        return _menu_builds(cfg)
    finally:
        cfg.data.update(kept)


def _menu_builds(cfg):
    from . import menu, mods, pipeline
    results = []
    for on in (True, False):
        with tempfile.TemporaryDirectory() as tmp:
            root = _mods_folder(tmp, {"mod-menu": ({"name": "Mod menu", "enabled": on, "builtin": True},
                                                   {"menu.json": '{"key": "F2", "size": 1.25, "cheats": true}'})})
            out = pipeline.build(cfg, mods.discover(root), os.path.join(tmp, "out"), log=lambda m: None)
            host = os.path.join(tmp, "out", "ue4ss", menu.HOST_NAME, "Scripts", "main.lua")
            text = open(host, encoding="utf-8").read() if os.path.isfile(host) else ""
            results.append((out["menu"], menu.HOST_NAME in out["ue4ss_mods"], menu.SHARED_NAME in out["ue4ss_shared"],
                            '"F2"' in text or "F2" in text))
    return results == [("mod-menu", True, True, True), (None, False, False, False)]


def _onboarding():
    """In a made-up game folder and save: the game is found from its exe's folder, the first backup is
    made once there's a save, UE4SS goes in from its .zip set up for players, and a dropped .zip waits
    in the inbox until it's taken."""
    import json
    from . import onboarding, ue4ss
    from .config import EXE_NAME, Config
    with tempfile.TemporaryDirectory() as tmp:
        win64 = os.path.join(tmp, "Game", "Wrc", "Binaries", "Win64")
        os.makedirs(win64)
        open(os.path.join(win64, EXE_NAME), "w").close()
        os.makedirs(os.path.join(tmp, "Saves"))
        root = os.path.join(tmp, "wcmods")
        os.makedirs(root)
        with open(os.path.join(root, "wcmods.json"), "w") as f:
            json.dump({"save_dir": os.path.join(tmp, "Saves")}, f)
        cfg = Config(root)
        found = onboarding.set_game_dir(cfg, win64)
        backups = os.path.join(tmp, "backups")
        none_yet = onboarding.first_backup(cfg, backups)
        open(os.path.join(tmp, "Saves", "WrcGame.sav"), "w").close()
        first = onboarding.first_backup(cfg, backups)
        again = onboarding.first_backup(cfg, backups)
        z = _zip(os.path.join(tmp, "UE4SS_v3.0.1-test.zip"), {
            "dwmapi.dll": "MZ", "ue4ss/UE4SS.dll": "MZ", "ue4ss/UE4SS-settings.ini": "GuiConsoleEnabled = 1\n",
            "ue4ss/Mods/mods.txt": "CheatManagerEnablerMod : 1\n; Built-in keybinds, do not move up!\nKeybinds : 1\n"})
        ue4ss.install_loader(z, win64, log=lambda m: None)
        ini = open(os.path.join(win64, "ue4ss", "UE4SS-settings.ini")).read()
        txt = open(os.path.join(win64, "ue4ss", "Mods", "mods.txt")).read()
        st = onboarding.status(cfg, backups)
        kept = onboarding.INBOX
        onboarding.INBOX = os.path.join(tmp, "inbox.json")
        try:
            onboarding.put_inbox(z)
            waiting = onboarding.inbox()
            onboarding.clear_inbox()
            gone = onboarding.inbox()
        finally:
            onboarding.INBOX = kept
        return (os.path.normcase(found) == os.path.normcase(os.path.join(tmp, "Game")) and none_yet is None
                and first and first.endswith("first-run") and again is None
                and "GuiConsoleEnabled = 0" in ini and "CheatManagerEnablerMod : 0" in txt
                and st["game"]["ok"] and st["loader"]["ok"] and st["backup"]["ok"] and st["done"]
                and os.path.normcase(waiting) == os.path.normcase(z) and gone is None)


def _onboarding_edges():
    """PR #11's review: an install made before UE4SS was in is made again once it is; a dropped folder of
    mods adds only the ticked ones; a UE4SS .zip naming a drive deeper in a path is refused; and a studio
    that hasn't found the game answers its pages with a message instead of dying."""
    import datetime
    import json
    import threading
    import urllib.error
    import urllib.request
    from . import modzip, pipeline, studio as studio_mod, ue4ss
    from .cli import Ctx
    from .config import EXE_NAME, Config
    from .mods import discover
    ok = []
    with tempfile.TemporaryDirectory() as tmp:
        # An install with the loader missing, then the loader in.
        win64 = os.path.join(tmp, "Game", "Wrc", "Binaries", "Win64")
        os.makedirs(win64)
        open(os.path.join(win64, EXE_NAME), "w").close()
        root = _mods_folder(os.path.join(tmp, "a"), {"m": ({"name": "M", "enabled": True}, {})})
        conf = os.path.join(tmp, "conf")
        os.makedirs(conf)
        built = (datetime.datetime.now() + datetime.timedelta(minutes=1)).isoformat(timespec="seconds")
        with open(os.path.join(conf, "wcmods.json"), "w") as f:
            json.dump({"game_dir": os.path.join(tmp, "Game"), "oodle_dll": os.path.join(tmp, "none.dll"),
                       "installed": {"mods": ["m"], "built": built, "ue4ss": False, "oodle": True}}, f)
        cfg = Config(conf)
        before = pipeline.pending(cfg, discover(root))
        os.makedirs(os.path.join(win64, "ue4ss", "Mods"))
        after = pipeline.pending(cfg, discover(root))
        ok.append(not before["any"] and after["any"] and after["redo"])

        # A folder holding two mods, one of them ticked.
        drop = _mods_folder(os.path.join(tmp, "drop"), {"one": ({"name": "One"}, {}), "two": ({"name": "Two"}, {})})
        mods_root = os.path.join(tmp, "mine")
        os.makedirs(mods_root)
        added = modzip.add_folder(drop, mods_root, os.path.join(tmp, "backups"), ids=["two"])
        ok.append([a["id"] for a in added] == ["two"] and sorted(os.listdir(mods_root)) == ["two"])

        # "ue4ss/Q:/..." would land on drive Q.
        z = _zip(os.path.join(tmp, "bad.zip"), {"dwmapi.dll": "MZ", "ue4ss/UE4SS.dll": "MZ", "ue4ss/Q:/x.bat": "x"})
        try:
            ue4ss.install_loader(z, win64, log=lambda m: None)
            ok.append(False)
        except ValueError:
            ok.append(True)

        # The studio's server with no game: a page asking for the game's files gets a message back.
        bare = os.path.join(tmp, "bare")
        os.makedirs(bare)
        with open(os.path.join(bare, "wcmods.json"), "w") as f:
            json.dump({}, f)
        from . import config as config_mod
        kept = config_mod._find_game_dir
        config_mod._find_game_dir = lambda: None   # as on a computer without the game in Steam
        ctx = Ctx(bare)
        st = studio_mod.Studio(ctx)
        server = studio_mod._Server(("127.0.0.1", 0), None)
        port = server.server_address[1]
        server.RequestHandlerClass = studio_mod.make_handler(st, port)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            def ask(path, method="GET"):
                req = urllib.request.Request(f"http://127.0.0.1:{port}/api/{path}", method=method,
                                             headers={"X-WC-Token": st.token, "Content-Type": "application/json"},
                                             data=b"{}" if method == "POST" else None)
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        return r.status, json.load(r)
                except urllib.error.HTTPError as e:
                    return e.code, json.load(e)
            answers = [ask("game/data"), ask("install", "POST"), ask("play", "POST")]
        finally:
            server.shutdown()
            server.server_close()
            config_mod._find_game_dir = kept
        ok.append(all(code == 400 and "hasn't found the game" in a.get("error", "") for code, a in answers))
    return all(ok)


def _palettes_without_oodle(cfg):
    from . import mods, pipeline
    found, searched, data = cfg._oodle_found, cfg._oodle_searched, cfg.data.pop("oodle_dll", None)
    cfg._oodle_found, cfg._oodle_searched = None, True
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = _mods_folder(tmp, {"colours": ({"name": "Colours", "enabled": True},
                                                  {"palette.json": '{"eyes": {"Green": "#00ff00"}, "fur": {"0": "#ff8000"}}'})})
            out = pipeline.build(cfg, mods.discover(root), os.path.join(tmp, "out"), log=lambda m: None)
            rep = out["sections"].get("palettes", {})
            return (rep.get("status") == "ok" and "colours" in rep.get("mods", [])
                    and any("eye colours left out" in w for w in out["warnings"])
                    and not [k for k, r in out["sections"].items() if r["status"] == "failed"])
    finally:
        cfg._oodle_found, cfg._oodle_searched = found, searched
        if data:
            cfg.data["oodle_dll"] = data


def _signatures(cfg):
    """On the installed exe: the decoder cuts .pdata's functions at their ends, and (on a build wcmods was
    checked on) signatures.check finds every class and every member where game.HIDDEN says."""
    from . import gamebuild, pe, signatures, x64
    exe = pe.game_exe(cfg)
    if not exe:
        return False, "no game exe"
    img = pe.Image(exe)
    total, exact = x64.check_functions(img, limit=3000)
    if exact < total * 0.99:
        return False, f"the decoder ends only {exact} of {total} functions where .pdata does"
    if not gamebuild.current(cfg)["verified"]:
        return True, f"decoder fine; build {gamebuild.current(cfg)['build']} isn't one wcmods was checked on, so the layout isn't compared"
    res = signatures.check(exe, log=lambda m: None)
    bad = [f"{gamebuild.describe(c + ':' + n)} {f['status']}" for c, rep in res["classes"].items()
           for n, f in rep["fields"].items() if f["status"] not in ("same", "kept")]
    missing = [c.rsplit(".", 1)[-1] for c, rep in res["classes"].items() if not rep["found"]]
    signed = sum(1 for rep in res["classes"].values() for f in rep["fields"].values() if f["status"] == "same")
    detail = f"{len(res['classes'])} classes, {signed} values confirmed by signatures"
    return not bad and not missing, detail + (f"; {', '.join(missing + bad)}" if bad or missing else "")


def _update_safety(cfg):
    """PR #12's review: on an exe that isn't the one the signatures were made on, a class none of whose
    members is found keeps nothing, and one site alone can't move a member; members the layout doesn't
    name are left out; a check that fails or a cache cut short leaves every value off instead of stopping
    the build; an install made on another build asks to be made again; and the cats' names are built."""
    import copy
    import json
    from . import game, gamebuild, mods, pe, pipeline, signatures
    from .config import Config
    exe = pe.game_exe(cfg)
    if not exe:
        return True, "no game exe; skipped"
    problems = []
    sigs = copy.deepcopy(signatures.load())
    sigs["made_on"] = dict(sigs["made_on"], text_sha1="not this exe")
    res_cls = "/Script/SwtQuest.SwtQuestResourceComponent"
    for cls, entry in sigs["classes"].items():
        if cls.endswith(("TurnBasedCombatComponent", "GameplayGameState")):
            entry["sites"] = []   # as if none of their code matched any more
    max_was = sigs["classes"][res_cls]["fields"]["WCM_Max"]
    for site in sigs["classes"][res_cls]["sites"]:   # Max's one site now "says" it moved
        for k, was in site["captures"].items():
            if was == max_was:
                site["captures"][k] = 0x200
    sigs["classes"][res_cls]["fields"]["WCM_Max"] = 0x200
    res = signatures.check(exe, sigs, log=lambda m: None)
    fields = {f"{c.rsplit('.', 1)[-1]}.{n}": f for c, rep in res["classes"].items() for n, f in rep["fields"].items()}
    if fields["SwtQuestResourceComponent.WCM_Max"]["status"] != "unsure":
        problems.append("one site moved Max")
    if fields["SwtQuestResourceComponent.WCM_Value"]["status"] != "same":
        problems.append("Value not found")
    if fields["SwtQuestResourceComponent.WCM_ResourceType"]["now"] is not None:
        problems.append("ResourceType kept beside a member that may have moved")
    kept = [k for k, f in fields.items() if k.startswith(("TurnBasedCombat", "SwtAdventureGameplayGameState",
                                                          "SwtAdventureLevelComponent")) and f["now"] is not None]
    if kept:
        problems.append("kept with no evidence: " + ", ".join(kept))
    if res["same"]:
        problems.append("reported the same")
    if game.hidden({}) or game.hidden({k: -16 for k in gamebuild._members()}):
        problems.append("members the layout doesn't name (or can't be offsets) still go in")

    kept_env, kept_cache, kept_check = os.environ.get("WCMODS_GAME_BUILD"), gamebuild.CACHE_DIR, signatures.check
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["WCMODS_GAME_BUILD"] = "99999998"
            gamebuild.CACHE_DIR = os.path.join(tmp, "cache")
            os.makedirs(gamebuild.CACHE_DIR)
            with open(gamebuild._cache_path(cfg, gamebuild.layout_key(cfg)), "w") as f:
                f.write('{"build": 99999998, "offs')   # cut short
            def broken(*a, **k):
                raise ValueError("an exe unlike any wcmods knows")
            signatures.check = broken
            fit = gamebuild.layout(cfg, log=lambda m: None)
            if fit["status"] != "partial" or any(v is not None for v in fit["offsets"].values()):
                problems.append("a failed check didn't leave everything off")
            # An install recorded on 24847281, with mods on: the game is now 99999998.
            root = _mods_folder(tmp, {"m": ({"name": "M", "enabled": True, "game_builds": [99999998]}, {})})
            conf = os.path.join(tmp, "conf")
            os.makedirs(conf)
            with open(os.path.join(conf, "wcmods.json"), "w") as f:
                json.dump({"game_dir": cfg.game_dir, "installed": {"mods": ["m"], "built": "2999-01-01T00:00:00",
                                                                     "game_build": 24847281}}, f)
            p = pipeline.pending(Config(conf), mods.discover(root))
            if not any("game updated" in r for r in p["redo"]):
                problems.append("an install from the old build isn't redone")
            if cfg.oodle_dll:   # the cats' names for the mod menu, built from the game's tables (layout still off)
                pipeline.build(cfg, mods.discover(root), os.path.join(tmp, "out"), log=lambda m: None)
                with open(os.path.join(tmp, "out", "ue4ss_shared", "WCModsNames", "WCModsNames.lua"), encoding="utf-8") as f:
                    if len(f.read()) < 1000:
                        problems.append("WCModsNames is empty")
    finally:
        signatures.check = kept_check
        gamebuild.CACHE_DIR = kept_cache
        if kept_env is None:
            os.environ.pop("WCMODS_GAME_BUILD", None)
        else:
            os.environ["WCMODS_GAME_BUILD"] = kept_env
    return not problems, "; ".join(problems)


def _outdated_mods(cfg):
    from . import gamebuild, mods, pipeline
    kept_env, kept_cache = os.environ.get("WCMODS_GAME_BUILD"), gamebuild.CACHE_DIR
    kept_allow = cfg.data.get("allow_outdated")
    os.environ["WCMODS_GAME_BUILD"] = "99999999"   # as if Steam had installed a newer build
    try:
        with tempfile.TemporaryDirectory() as tmp:
            gamebuild.CACHE_DIR = os.path.join(tmp, "cache")   # what it works out for that build stays in tmp
            root = _mods_folder(tmp, {
                "old": ({"name": "Old", "enabled": True}, {"palette.json": '{"fur": {"0": "#ff8000"}}'}),
                "new": ({"name": "New", "enabled": True, "game_builds": [24847281, 99999999]}, {}),
                "needs-old": ({"name": "Needs old", "enabled": True, "game_builds": [99999999], "requires": ["old"]}, {})})
            found = mods.discover(root)
            old = gamebuild.outdated(cfg, found)
            cfg.data["allow_outdated"] = {}
            first = pipeline.build(cfg, found, os.path.join(tmp, "a"), log=lambda m: None)
            cfg.data["allow_outdated"] = {"old": [99999999]}
            second = pipeline.build(cfg, found, os.path.join(tmp, "b"), log=lambda m: None)
        return (set(old) == {"old"} and old["old"]["made_for"] == list(gamebuild.ASSUMED_BUILDS)
                and "old" not in first["mods"] and "new" in first["mods"] and "needs-old" not in first["mods"]
                and first["outdated"][0]["used"] is False
                and "old" in second["mods"] and "needs-old" in second["mods"] and second["outdated"][0]["used"] is True
                and any("may behave unpredictably" in w for w in second["warnings"]))
    finally:
        gamebuild.CACHE_DIR = kept_cache
        if kept_env is None:
            os.environ.pop("WCMODS_GAME_BUILD", None)
        else:
            os.environ["WCMODS_GAME_BUILD"] = kept_env
        if kept_allow is None:
            cfg.data.pop("allow_outdated", None)
        else:
            cfg.data["allow_outdated"] = kept_allow


def _csv_rows():
    """Row removal and addition keep every other byte, the line endings and a missing final newline."""
    from . import csvdata
    for text in ("#,Name,ID\r\n1,Wood,A\r\n2,Ember,B\r\n3,Berry,C", "#,Name,ID\r\n1,Wood,A\r\n2,Ember,B\r\n3,Berry,C\r\n"):
        out, applied, problems = csvdata.apply_edits(text, {"-": ["2"], "+": [{"#": "4", "Name": "Moth, Sr", "ID": "D"}]})
        end = "\r\n" if text.endswith("\r\n") else ""
        want = '#,Name,ID\r\n1,Wood,A\r\n3,Berry,C\r\n4,"Moth, Sr",D' + end
        if out != want or problems or len(applied) != 2:
            return False
    _, _, problems = csvdata.apply_edits("#,Name\n1,Wood\n", {"+": [{"#": "1", "Name": "Again"}], "-": ["9"]})
    return len(problems) == 2


def _colour_slots():
    """Pattern and marking colours take new slots, coats can't; a palette that only adds slots isn't a
    preset; your cat's colours and slots are checked and written as the game keeps them."""
    from . import catlook
    with tempfile.TemporaryDirectory() as tmp:
        def load(data):
            path = os.path.join(tmp, "palette.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            try:
                return palettes.load(path)
            except ValueError:
                return "error"
        adds = load('{"pattern": {"25": "#ff00cc"}, "marking": {"30": "#00e5ff"}}')
        mixed = load('{"pattern": {"3": "#112233", "25": "#ff00cc"}}')
        ok = (load('{"fur": {"25": "#ff00cc"}}') == "error" and adds != "error" and palettes.adds_only(adds)
              and not palettes.adds_only(mixed) and palettes.new_slots(adds) == {"pattern": [25], "marking": [30]})
    lua = palettes.ue4ss_script(palettes.merge([adds]))
    ok = ok and not luacheck.check(lua) and "PatternMaskColors = { [25]" in lua and "GROW = { PatternMaskColors" in lua
    look = catlook.validate({"player": {"colours": {"fur": "#ff6ec7", "nose": "#202020"}, "slots": {"fur": 3, "pattern": 25}}})
    script = catlook.script(look["player"]["colours"])
    try:
        catlook.validate({"player": {"slots": {"fur": 25}}})
        fur_refused = False
    except ValueError:
        fur_refused = True
    text = '(ClanType=RiverClan,FurColorIdx=11,Pattern01ColorIdx=2,CatSize=0.5)'
    fields = catlook.set_fields(text, {"FurColorIdx": 3, "Pattern01ColorIdx": 25, "Pattern02ColorIdx": 26})
    # Scars: "none" takes them all away; each place takes a scar's name or the game's number for it.
    scars = catlook.validate({"player": {"scars": "none"}})["player"]["scars"]
    some = catlook.validate({"player": {"scars": {"eye": 3, "ear": "notch-left", "body": "none"}}})["player"]["scars"]
    named = catlook.validate({"player": {"scars": {"eye": "claws-left", "back": "claws-1", "chest": "bite"}}})["player"]["scars"]
    refused = 0
    kept = catlook.validate({"player": {"scars": {"back": 5}}})["player"]["scars"]   # the game's, with a warning
    for bad in ({"scars": {"eye": 7}}, {"scars": {"chest": 3}}, {"scars": {"ear": "chewed"}}, {"scars": {"back": 7}},
                {"scars": {"tail": "none"}}, {"scars": "some"}, {"scars": {"ear": ["notch-left"]}},
                {"scars": {"body": 2, "back": 4}}):
        try:
            catlook.validate({"player": bad})
        except ValueError:
            refused += 1
    scarred = catlook.set_fields('(ClanType=RiverClan,CatSize=0.5,ScarEarId=4,ScarBodyId=2)',
                                 {catlook.SCARS[p]: 0 for p in scars})
    return (ok and fur_refused and not luacheck.check(script) and '["Fur Color"]' in script
            and fields == '(ClanType=RiverClan,FurColorIdx=3,Pattern01ColorIdx=25,CatSize=0.5,Pattern02ColorIdx=26)'
            and set(scars) == set(catlook.SCARS) and not any(scars.values())
            and some == {"eye": 3, "ear": 5, "back": 0} and named == {"eye": 6, "back": 3, "chest": 1}
            and kept == {"back": 5}
            and refused == 8
            and "ScarEarId=0" in scarred and "ScarBodyId=0" in scarred and "ScarEyeId=0" in scarred)


def _scars_build(cfg):
    """A cats.json with scars and no slots makes one save edit per copy of your cat, setting the scar fields."""
    import json
    from . import mods, pipeline
    with tempfile.TemporaryDirectory() as tmp:
        root = _mods_folder(tmp, {"scars": ({"name": "Scars", "enabled": True},
                                            {"cats.json": json.dumps({"player": {"scars": {"ear": "notch-left", "eye": "none"}}})})})
        out = pipeline.build(cfg, mods.discover(root), os.path.join(tmp, "out"), log=lambda m: None)
    ops = [o for o in out["save_ops"] if o.get("op") == "fields"]
    if not os.path.isfile(os.path.join(cfg.save_dir, SAV_NAME)):
        return any("no save yet" in w for w in out["warnings"])
    return (bool(ops) and all(o["set"] == {"ScarEarId": 5, "ScarEyeId": 0} for o in ops)
            and all(o["label"] == "ear scar notch-left, eye scar none" for o in ops))


def _rename_struct():
    from . import names
    text = '(ClanType=RiverClan,Role=Apprentice,PrefixNameId="STR_CAT_NAME65",CatSize=0.5)'
    new = names.rename_struct(text, {"PrefixNameId": "STR_CAT_NAME53", "SuffixNameId": "_HEART"},
                              {"PrefixNameId": "STR_CAT_NAME65"})
    moved_on = names.rename_struct(text, {"PrefixNameId": "STR_CAT_NAME53"}, {"PrefixNameId": "STR_CAT_NAME1"})
    return (new == '(ClanType=RiverClan,Role=Apprentice,PrefixNameId="STR_CAT_NAME53",SuffixNameId="_HEART",CatSize=0.5)'
            and moved_on is None)


def _names_plan(read_text):
    """A names.json against the game's own tables: renames reach every name with that part, additions
    get a text in every language, needed suffixes stay, and the ban list follows."""
    from . import names
    game = names.GameNames(read_text)
    plan = names.Plan(game, names.merge([names.validate({
        "prefixes": {"rename": {"Otter": "Moth"}, "add": {"Sparrow": {"like": "Wren"}}, "remove": ["Pigeon"]},
        "suffixes": {"add": {"whisper": {}}, "remove": ["kit"]},
        "rogues": {"add": ["Moss"]}, "banned": {"remove": ["Tigerstar"], "add": ["Mothheart"]}})]))
    en = plan.edits[names.strings_path("EN")]
    added = {r["Key"]: r["SourceString"] for r in en.get("+", [])}
    de_added = {r["Key"] for r in plan.edits[names.strings_path("DE")].get("+", [])}
    ok = (en.get("STR_CAT_NAME53_PAW", {}).get("SourceString") == "Mothpaw"
          and added.get("STR_CAT_NAME_WCM_SPARROW_PAW") == "Sparrowpaw"
          and added.get("STR_CAT_NAME53_WCM_WHISPER") == "Mothwhisper"
          and added.get("STR_ROGUE_CAT_NAME_WCM_MOSS") == "Moss"
          and set(added) <= de_added
          and "STR_CAT_NAME27_FACE" not in added
          and plan.edits[names.PREFIXES].get("-") == [p["row"] for p in game.prefixes if p["text"] == "Pigeon"]
          and "-" not in plan.edits.get(names.SUFFIXES, {})
          and any("only suffix for Kit" in w for w in plan.warnings)
          and plan.edits[names.BANNED]["+"][0]["PrefixID"] == "STR_CAT_NAME53")

    # Cats: a story role is a copy of a clan cat (renamed in both places); a place with "was" only
    # counts while that cat still has that name; a cat that isn't there still gets its texts; and a
    # rename already in the save needs nothing and warns about nothing.
    cat = '(ClanType=RiverClan,Role=Warrior,PrefixNameId="{}",SuffixNameId="_HEART")'
    data = {"0": {"GameplayProgression": {"Gameplay.Combat.Character.Cat.Player": {"Customization": cat.format("STR_CAT_NAME53")}},
                  "NPCData": {"RiverClan": {"Warrior": [cat.format("STR_CAT_NAME1"), cat.format("STR_CAT_NAME2"),
                                                        cat.format("STR_CAT_NAME_WCM_FIXED_GLOW")]},
                              "NarrativeRoles": {"TheAgingLeader": cat.format("STR_CAT_NAME1")}}}}
    cats = names.cats_in_save(data)
    plan = names.Plan(game, names.merge([names.validate({"cats": {
        "Woodheart": {"fixed": "Sparkle"}, "RiverClan/Warrior/1": {"name": "Mothheart", "was": "Someone"},
        "Nobody": {"prefix": "Glimmer"}, "Was-glow": {"fixed": "Glow"}}})]))
    ops = plan.plan_cats(cats)
    texts = {**plan.added_keys}
    ok_cats = (len(cats) == 4 and [len(c["paths"]) for c in cats if c["ids"]["PrefixNameId"] == "STR_CAT_NAME1"] == [2]
               and sorted(o["where"] for o in ops) == ["NarrativeRoles/TheAgingLeader", "RiverClan/Warrior/0"]
               and all(o["set"] == {"PrefixNameId": "STR_CAT_NAME_WCM_FIXED_SPARKLE"} for o in ops)
               and texts.get("STR_CAT_NAME_WCM_FIXED_SPARKLE_PAW") == "Sparkle"
               and texts.get("STR_CAT_NAME_WCM_GLIMMER_PAW") == "Glimmerpaw"
               and [w for w in plan.warnings if w.startswith("cats:")] == [
                   "cats: no cat in your save is called 'RiverClan/Warrior/1'", "cats: no cat in your save is called 'Nobody'"])
    return ok and ok_cats, f"{len(game.prefixes)} prefixes, {len(game.suffixes)} suffixes, {len(added)} new texts"


def _remapper_presses():
    """The remapper's key handling, with its key sending and play check replaced (no hooks involved)."""
    import sys
    if sys.platform != "win32":
        return True
    from .remapper import Remapper
    sent, on = [], [False]
    r = Remapper({"T": "W"}, {"W"}, ("game.exe",), log=lambda m: None)
    r._press = lambda name, down: sent.append((name, down))
    r.context = lambda: "play" if on[0] else "menu"

    def press(name, down, now=None):
        if now is not None:
            on[0] = now
        return r.handle(name, down)

    # A W held from a menu into play goes through to its release, so the game never keeps it down.
    held_over = [press("W", True, False), press("W", True, True), press("W", False)] == [False, False, False]
    # T stands for W while playing; its repeats stop in a menu, and its release always lets go of W.
    remapped = [press("T", True, True), press("T", True, False), press("T", False)] == [True, True, True]
    remapped = remapped and sent == [("W", True), ("W", False)]
    # A blocked W is held back, release included.
    blocked = [press("W", True, True), press("W", False)] == [True, True]
    clean = not r.held and not r.swallowed and not r.passed

    # Escape opens the pause menu (P) while playing and closes menus (BackSpace) in them. The press that
    # opens the menu releases as P, even though the menu is open by the time it's let go.
    sent.clear()
    m = Remapper({"Escape": "P"}, set(), ("game.exe",), log=lambda msg: None, menu_send={"Escape": "BackSpace"})
    m._press = lambda name, down: sent.append((name, down))
    m.context = lambda: "play" if on[0] else "menu"
    on[0] = True
    steps = [m.handle("Escape", True)]
    on[0] = False
    steps += [m.handle("Escape", False), m.handle("Escape", True), m.handle("Escape", False), m.handle("T", True)]
    menus = steps == [True, True, True, True, False] and sent == [("P", True), ("P", False), ("BackSpace", True),
                                                                  ("BackSpace", False)]
    return held_over and remapped and blocked and clean and menus


def _menu_remaps():
    """controls.json's "menus" section: how it's read, planned, and used with --in-menus."""
    import sys
    from . import mods as modlib
    from .sections.controls import ControlsSection
    with tempfile.TemporaryDirectory() as tmp:
        m = modlib.create(tmp, "menu-keys")

        def collect(data):
            with open(os.path.join(m.folder, "controls.json"), "w", encoding="utf-8") as f:
                f.write(data)
            try:
                return ControlsSection().collect(m, None)
            except ValueError:
                return "error"
        read = (collect('{"menus": {"keys": {"Escape": "BackSpace"}}}') == {"menus": {"Escape": "BackSpace"}}
                and collect('{"menus": {"Escape": "BackSpace"}}') == "error"
                and collect('{"menus": {"keys": ["Escape"]}}') == "error")
    send, warns = keymap.menu_plan({"menus": {"Escape": "BackSpace", "M": "Enter", "Tab": "Tab"}})
    planned = send == {"Escape": "BackSpace", "M": "Enter"} and len(warns) == 1 and "name screen" in warns[0]
    if sys.platform != "win32":
        return read and planned
    # With --in-menus the play remaps apply in menus too, and a menu remap for the same key wins.
    from .remapper import Remapper
    sent = []
    r = Remapper({"Escape": "P", "T": "W"}, set(), ("game.exe",), log=lambda msg: None, in_menus=True,
                 menu_send={"Escape": "BackSpace"})
    r._press = lambda name, down: sent.append((name, down))
    r.context = lambda: "menu"
    steps = [r.handle("Escape", True), r.handle("Escape", False), r.handle("T", True), r.handle("T", False)]
    both = steps == [True] * 4 and sent == [("BackSpace", True), ("BackSpace", False), ("W", True), ("W", False)]
    return read and planned and both


def _palette_switching():
    """choose_palettes switches only mods that hold nothing but a palette, in a throwaway mods folder."""
    from . import mods as modlib
    with tempfile.TemporaryDirectory() as tmp:
        for mod_id, files, enabled in (("theme-a", ["palette.json"], True), ("theme-b", ["palette.json"], False),
                                       ("mixed", ["palette.json", "data.json"], True)):
            m = modlib.create(tmp, mod_id, enabled=enabled)
            for name in files:
                with open(os.path.join(m.folder, name), "w", encoding="utf-8") as f:
                    f.write("{}")
        on, off = modlib.choose_palettes(modlib.discover(tmp), ["theme-b"])
        now = {m.id: m.enabled for m in modlib.discover(tmp)}
        try:
            modlib.choose_palettes(modlib.discover(tmp), ["mixed"])
            refused = False
        except ValueError:
            refused = True
    return on == ["theme-b"] and off == ["theme-a"] and refused and now == {"theme-a": False, "theme-b": True, "mixed": True}


def _meta_hash(io, index):
    buf = open(io.utoc_path, "rb").read()
    off = len(buf) - len(io.chunk_ids) * 24 + index * 24
    return buf[off:off + 20]
