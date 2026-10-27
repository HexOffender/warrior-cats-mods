"""Round-trip checks against the installed game and save. Writes only to a temp folder."""
import math
import os
import re
import struct
import tempfile

from . import bridge, catcolours, controls, draw, eyeatlas, keymap, luacheck, menu, mouselook, palettes, view, world
from .exe import gamebuild
from . import game as game_lua
from .formats.blake3 import blake3
from .formats.iostore import IoStoreReader, ModContainerWriter
from .formats.pak import PakReader, PakWriter
from .formats.save import JSON_NAME, SAV_NAME, SaveGame


def run(cfg, oodle, log=print):
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        log(f"  [{'ok' if ok else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")

    check("blake3 test vector", blake3(b"").hex().startswith("af1349b9f5f9a1a6"))
    check("name hashes as in the game's name maps (CityHash64, every length)", _name_hashes())
    check("unversioned property headers write back as they read", _unversioned_headers())
    ok, detail = _long_save()
    check("saves over 128 KiB: the game's archive per 128 KiB, read and written", ok, detail)
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
    check(f"shared module {world.NAMES_NAME}, with the game's own text for names it hasn't got, and areas and quests",
          not problems and "function N.name(" in lua and "function N.area(" in lua and "function N.quest(" in lua
          and lua.rstrip().endswith("return N"), "; ".join(problems[:3]))
    lua = mouselook.script(mouselook.merge([{}]), {"path": r"C:\mods\m\mouselook.json", "file": "mods/m/mouselook.json",
                                                  "keep": {"_help": 'say "hi"'}})
    problems = luacheck.check(lua)
    check("mouse look script with its menu page", not problems and "@SAVE@" not in lua
          and r'"C:\\mods\\m\\mouselook.json"' in lua, "; ".join(problems[:3]))
    lua = catcolours.script({"fur": (1.0, 0.5, 0.0)}, save={"path": "x", "file": "y", "doc": {"player": {"colours": {}}}})
    problems = luacheck.check(lua) + re.findall(r"@[A-Z_]+@", lua)
    check("your cat's colours script with its menu page", not problems and '"#ff8000"' in lua, "; ".join(problems[:3]))
    lua = menu.host_script({"sections": {}, "notes": {}, "warnings": ["w"], "built": "2026-10-24T01:00:00"}, [], dev=True)
    problems = luacheck.check(lua) + re.findall(r"@[A-Z_]+@", lua)
    check("mod menu window script (with its Overview, Installed mods, Inspector and Console pages, and none about "
          "the game: those are the Menu pages mod's)", not problems and 'Menu.page("Inspector"' in lua
          and 'Menu.page("Overview"' in lua and 'Menu.page("Installed mods"' in lua and 'Menu.page("Cheats"' not in lua,
          "; ".join(problems[:3]))
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
    ok, detail = _cpp_tooling()
    check("C++ tooling: a crash readout names the mod and line, and cpp ide picks the newest Visual Studio", ok, detail)
    check("mod menu answers the agent controller", all(s in menu.lua() for s in ('"agent.read"', '"agent.act"', '"agent.scroll"'))
          and 'Menu.share("frame"' in menu.host_script({"sections": {}, "notes": {}, "warnings": [], "built": ""}, []))
    check("agent controller: pictures, menu rows, test files", _agent_parts())
    check("adding a downloaded mod from a .zip (and refusing unsafe ones)", _mod_zips())
    check("a .zip can't hide code in a name's case or carry a bad mod.json; needing the mod menu needs nothing more",
          _mod_zip_guards())
    check("mods that need other mods: switched on together, left out of a build without them", _requirements(cfg))
    ok, detail = _menu_window(cfg)
    check("the mod menu is wcmods' own: its window and module in every build, its key from wcmods.json, and its "
          "Overview saying how to get the Menu pages mod while the build hasn't got it", ok, detail)
    ok, detail = _menu_pages()
    check("the Menu pages mod: added from its .zip, updated keeping your settings and whether it's on, cheats "
          "from the old mod menu taken along", ok, detail)
    check("getting set up: the game found from any of its folders, a first backup, the script loader, the menu's "
          "pages (skipped)", _onboarding())
    check("getting set up, the rough edges: an install from before UE4SS is redone, the mod menu goes in with "
          "no mods on, a folder adds only the ticked mods, no drive letters in UE4SS's .zip, a studio without the game answers", _onboarding_edges())
    ok, detail = _user_data()
    check("your files outside wcmods' folder: moved out once, the old mod menu's settings into wcmods.json, nothing "
          "overwritten by a second copy, the last install redone", ok, detail)
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

    ok, detail = _kraken_fixtures()
    check("Kraken decoder: samples compressed by Oodle itself, at several levels, decode back", ok, detail)
    base_pak = PakReader(os.path.join(cfg.paks_dir, "pakchunk0-Windows.pak"), oodle)
    csv = base_pak.read("Wrc/Content/Gameplay/DataTables/NonAsset/NPC/CatSize.csv")
    check("read base pak", csv.startswith(b"--,Role"), f"{len(base_pak.entries)} files")
    tuning = base_pak.read("Wrc/Content/Gameplay/DataTables/NonAsset/TuningData.csv")
    check(f"Kraken decompress (pak, {oodle.name})", len(tuning) > 1000 and tuning[:200].isascii())

    io = IoStoreReader(os.path.join(cfg.paks_dir, "pakchunk0-Windows.utoc"), oodle)
    check("read base utoc", len(io.files) > 1000, f"{len(io.files)} files, toc v{io.version}")
    if oodle.path:
        ok, detail = _kraken_against_dll(io, oodle)
        check("Kraken decoder: the game's own blocks decode the same as the oo2core DLL", ok, detail)

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

    ok, detail = _cooked_table(io)
    check("cooked item table: every row read and written back the same, and a new row added", ok, detail)
    ok, detail = _textures(io)
    check("new textures: a copy of the game's with the IDs the game would give it, new pixels in every mip",
          ok, detail)
    ok, detail = _accessory_looks(io)
    check("accessory looks: the game's lists read, new looks and their tags added, the rest as it was",
          ok, detail)
    ok, detail = _skeletal_meshes(io)
    check("accessory models: every accessory's mesh and the cat's read and written back the same, and a model "
          "through OBJ into a copy tied to the cat", ok, detail)
    ok, detail = _animations(io)
    check("animations: every one of the game's sequences read and written back the same and decoded (ACL ones with "
          "their skeleton's pose), each animal's template copied with new keys, and game animations through a start "
          "kit and back", ok, detail)
    ok, detail = _items_section(cfg)
    check("new items (items.json): tag, herb row, item table row, recipe, starting count, a game item's "
          "recipe, icons, an accessory's look, model, place and glass of a mod's own; mistakes refused",
          ok, detail)

    from .formats import csvdata
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
    areas, quests = world.place_names(lambda p: base_pak.read(p).decode("utf-8"))
    check("area names and quest titles from the game's tables (WCModsNames' area and quest)",
          len(areas) > 20 and len(quests) > 20 and all(quests.values()) and "R-05" in areas,
          f"{len(areas)} areas, {len(quests)} quests")

    sav = os.path.join(cfg.save_dir, SAV_NAME)
    if os.path.isfile(sav):
        from .formats.savejson import SaveDoc
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
    from .formats.cityhash import name_hash
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
    from .formats.cooked import _Reader, read_header, split_name, write_header
    cases = [([], set()), ([0], set()), ([0, 1, 2, 3, 4, 5, 6], {4, 5, 6}), ([0, 2, 3, 9], {3}),
             (list(range(130)), set(range(0, 130, 7))), ([200, 201], set()), (list(range(40)), {1, 33})]
    for present, zero in cases:
        if read_header(_Reader(write_header(present, zero))) != (present, zero):
            return False
    return (split_name("NewRow_45") == ("NewRow", 46) and split_name("Foo_0") == ("Foo", 1)
            and split_name("Foo_01") == ("Foo_01", 0) and split_name("Gameplay.Item") == ("Gameplay.Item", 0))


def _long_save():
    """A save whose JSON runs past 128 KiB. The game writes CompressedData as one compressed archive per
    128 KiB of payload; reading only the first one cut a long-played save short ("unpack_from requires a
    buffer of at least ... bytes"). Laid out here by hand, the way the game does it, not by save.py."""
    import zlib
    from .formats import save as savelib
    text = '{"Shared": {"General": {"CurrentCatSlot": 0}}, "Pad": "' + "x" * 500000 + '"}'
    body = text.encode("utf-8")
    payload = (struct.pack("<II", len(body) + 8, len(body)) + bytes((b - 1) & 0xFF for b in body)
               + struct.pack("<I", len(body)))
    block = 0x20000
    pieces = [payload[k:k + block] for k in range(0, len(payload), block)]
    packed = [zlib.compress(piece) for piece in pieces]
    head = savelib.ARCHIVE_TAG + struct.pack("<q", block) + bytes([3])
    archives = b"".join(head + struct.pack("<qq", len(c), len(u)) * 2 + c for c, u in zip(packed, pieces))

    def gvas(data):   # the property's tail: size (int32), flags (u8), count (int32), the archives
        return (b"GVAS" + bytes(20) + b"CompressedData" + bytes(1) + b"ArrayProperty" + bytes(1)
                + struct.pack("<i", len(data) + 4) + bytes(1) + struct.pack("<i", len(data)) + data + bytes(4))

    want = [len(piece) for piece in pieces]
    if len(want) < 4 or SaveGame(gvas(archives)).json_text != text:
        return False, "a save of several archives doesn't read back"
    # What wcmods writes for it has the same shape: an archive per 128 KiB, none over the game's buffer.
    new = SaveGame(gvas(archives)).to_bytes()
    again = SaveGame(new)
    sizes, p = [], again._data_start
    while p < again._data_end:
        (block_size,) = struct.unpack_from("<q", new, p + 8)
        csize, usize = struct.unpack_from("<qq", new, p + 17)
        sizes.append(usize)
        p += 33 + 16 * ((usize + block_size - 1) // block_size) + csize
    if sizes != want or again.json_text != text:
        return False, f"written as archives of {sizes}, not {want}"
    # One archive of several blocks (the engine's general layout) reads too.
    one = (head + struct.pack("<qq", sum(map(len, packed)), len(payload))
           + b"".join(struct.pack("<qq", len(c), len(u)) for c, u in zip(packed, pieces)) + b"".join(packed))
    if SaveGame(gvas(one)).json_text != text:
        return False, "an archive of several blocks doesn't read back"
    return True, f"{len(want)} archives for {len(payload)} bytes"


def _cooked_table(io):
    from .formats import cooked
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
    from .formats.png import SIGNATURE
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
    from . import recolor
    from .formats import bcn, png
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
    from . import accessories
    from .formats import texture
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
    from .formats.cooked import ZenPackage
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
    from . import accessories, mods, pipeline
    from .formats import png, texture
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
         "texture": {"tint": "#a8c4ff"}, "recipe": {"Bone": 1}},
        {"id": "WCModsTestRing", "like": "Neck.DogCollar.1", "name": "Test Ring", "description": "Its own shape.",
         "model": "models/ring.obj"},
        {"id": "WCModsTestGlass", "like": "Neck.DogCollar.1", "name": "Test Glass", "description": "Lower, bigger, glass.",
         "place": {"up": -1.5, "pitch": 10, "scale": 1.2}, "opacity": 0.5, "glass": "#a8e0ff"},
        {"id": "WCModsTestPebble", "kind": "material", "name": "Test Pebble", "description": "A ring on the ground.",
         "icon": "Rock", "model": "models/ring.obj", "texture": "icons/test.png", "place": {"up": 2}}],
        "recipes": {"Cosmetic.Head.MossPatch.1": {"Moss": 3, "WCModsTestStone": 1}}}
    bad = {"items": [
        {"id": "SmallCatnip", "kind": "consumable", "name": "Again", "description": "x", "like": "SmallCatnip"},
        {"id": "WCModsCrown", "kind": "accessory", "name": "Crown", "description": "x"},
        {"id": "WCModsNoStone", "like": "SmallHealingHerb", "name": "x", "description": "x", "recipe": {"Moonrock": 1}},
        {"id": "WCModsWhat", "like": "SmallHealingHerb", "name": "x", "description": "x", "effect": "Gameplay.Effect.Fly"},
        {"id": "WCModsHat", "like": "Head.BigLeaf.1", "name": "x", "description": "x", "texture": {"tint": "#ffffff"}},
        {"id": "WCModsShiny", "like": "SmallHealingHerb", "name": "x", "description": "x", "texture": {"tint": "#ffffff"}},
        {"id": "WCModsLost", "like": "SmallHealingHerb", "name": "x", "description": "x", "icon": "missing.png"},
        {"id": "WCModsOut", "like": "SmallHealingHerb", "name": "x", "description": "x", "icon": "../good/icons/test.png"},
        {"id": "WCModsShaped", "like": "SmallHealingHerb", "name": "x", "description": "x", "texture": "a.png"},
        {"id": "WCModsNoRing", "like": "Neck.DogCollar.1", "name": "x", "description": "x", "model": "models/none.glb"},
        {"id": "WCModsSeeHerb", "like": "SmallHealingHerb", "name": "x", "description": "x", "opacity": 0.5},
        {"id": "WCModsLostPebble", "kind": "material", "name": "x", "description": "x", "icon": "Rock",
         "model": "models/none.obj"}],
        "recipes": {"Cosmetic.Head.NoSuchHat.1": {"Moss": 1}}}
    colour = (200, 60, 160, 255)
    picture = png.write(32, 32, bytes(colour) * 1024)
    ring = _ring_obj(cfg)
    with tempfile.TemporaryDirectory() as tmp:
        typo = {"items": [{"id": "WCModsTypo", "like": "SmallHealingHerb", "name": "x", "description": "x", "icon": 5}]}
        tint = {"items": [{"id": "WCModsBlue", "like": "SmallHealingHerb", "name": "x", "description": "x",
                           "icon": {"tint": "blue"}}]}
        root = _mods_folder(tmp, {"good": ({"name": "Good", "enabled": True},
                                           {"items.json": json.dumps(good), "icons/test.png": picture,
                                            "models/ring.obj": ring}),
                                  "bad": ({"name": "Bad", "enabled": True}, {"items.json": json.dumps(bad)}),
                                  "typo": ({"name": "Typo", "enabled": True}, {"items.json": json.dumps(typo)}),
                                  "tint": ({"name": "Tint", "enabled": True}, {"items.json": json.dumps(tint)})},
                            build=gamebuild.steam_build(cfg))
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
        ring_tag = f"Gameplay.Inventory.Cosmetic.Neck.DogCollar.{len(looks['DogCollar']) + 2}"
        glass_tag = f"Gameplay.Inventory.Cosmetic.Neck.DogCollar.{len(looks['DogCollar']) + 3}"
        ok = gave and (rep["status"] == "partial" and any("typo" in e and "should be text" in e for e in rep["errors"])
              and any("tint" in e and "colour like" in e for e in rep["errors"])
              and sorted(r["row"] for r in rows) == sorted([
                  "WCMods_Consumable_WCModsTestHerb", "WCMods_Materials_WCModsTestHerb",
                  "WCMods_Materials_WCModsTestStone", "WCMods_Consumable_WCModsTestPicture",
                  "WCMods_" + collar[len("Gameplay.Inventory."):].replace(".", "_"),
                  "WCMods_" + ring_tag[len("Gameplay.Inventory."):].replace(".", "_"),
                  "WCMods_" + glass_tag[len("Gameplay.Inventory."):].replace(".", "_"),
                  "WCMods_Materials_WCModsTestPebble", "WCMods_Materials_WCModsLostPebble"]) and len(use) == 2
              and sorted(c["row"] for c in recipe) == sorted(["Gameplay.Inventory.Consumable.WCModsTestHerb", collar,
                                                              "Gameplay.Inventory.Cosmetic.Head.MossPatch.1"])
              and "Wrc/Config/Tags/WCModsItems.ini" in out["files"] and len(warned) == 13
              and all(any(s in w for w in warned) for s in ('needs "like"', "first look", "only accessories",
                                                             "no picture", "own folder", 'goes with a "model"',
                                                             "a picture (a PNG)", "no model",
                                                             "pickup instead"))
              and "zzz_WCMods_P.utoc" in out["outputs"] and "WCModsModels" in out["ue4ss_mods"]
              and "WCModsItems" in out["ue4ss_shared"])
        # What went into wcmods' container: the new textures (the look with its .ubulk), the look in the
        # game's list, and the icons in the item table.
        made = IoStoreReader(os.path.join(tmp, "out", "zzz_WCMods_P.utoc"))
        look = "/Game/WCMods/good/T_WCModsTestCollar_BC"
        icon = "/Game/WCMods/good/T_WCModsTestPicture_Icon"
        stone = "/Game/WCMods/good/T_WCModsTestStone_Icon"
        packed = (ok and all(texture.content_path(p) in made.files for p in (look, icon, stone))
                  and texture.content_path(look)[:-len(".uasset")] + ".ubulk" in made.files)
        if packed:
            from . import models
            from .formats import cooked, skelmesh
            worn = accessories.read_variations(made.read_file(accessories.GUI_MANAGER))
            path, schema = cooked.TABLES["DT_QuestObjectsInfo"]
            table = {v["itemTag"]: v for _, v in cooked.DataTable(made.read_file(path), schema).rows}
            pixels = texture.Texture(made.read_file(texture.content_path(icon))).image(0)[2]
            # The ring: the Dog Collar's mesh with the model in it, worn with the collar's own look, and the
            # script that puts it on a cat knowing which look it is.
            mesh = skelmesh.SkeletalMesh(made.read_file(texture.content_path("/Game/WCMods/good/SK_WCModsTestRing")))
            model = models.read("ring.obj", ring.encode())
            with open(os.path.join(tmp, "out", "ue4ss", "WCModsModels", "Scripts", "main.lua"), encoding="utf-8") as f:
                lua = f.read()
            ring_path = "/Game/WCMods/good/SK_WCModsTestRing.SK_WCModsTestRing"
            # The glass one: the Dog Collar's own shape placed lower and bigger, worn as glass of its colour.
            glass = skelmesh.SkeletalMesh(made.read_file(texture.content_path("/Game/WCMods/good/SK_WCModsTestGlass")))
            game = GameFiles(cfg)
            collar = skelmesh.SkeletalMesh(game.read(texture.content_path(
                accessories.read_meshes(game.read(accessories.GUI_MANAGER))["DogCollar"].split(".", 1)[0])))
            placed = models.place(models.from_mesh(collar), {"up": -1.5, "pitch": 10, "scale": 1.2})
            where = all(math.dist(a, b) < 1e-3 for a, b in zip(glass.lods[0].positions, placed.positions))
            n = len(looks["DogCollar"])
            packed = (worn["DogCollar"] == looks["DogCollar"] + [look + ".T_WCModsTestCollar_BC", looks["DogCollar"][0],
                                                                 looks["DogCollar"][0]]
                      and table["Gameplay.Inventory.Consumable.WCModsTestPicture"]["Icon"]["package"] == icon
                      and all(abs(a - b) <= 4 for a, b in zip(pixels[:4], colour))
                      and all(L.vertex_count == len(model.positions) for L in mesh.lods)
                      and mesh.export_names[mesh.main] == "SK_WCModsTestRing"
                      and all(len(m) > 0 for m in mesh.lods[0].morphs)
                      and f'["{n + 2}"] = {{ ["mesh"] = "{ring_path}" }}' in lua
                      and f'["{n + 3}"] = {{ ["mesh"] = "/Game/WCMods/good/SK_WCModsTestGlass.SK_WCModsTestGlass", '
                          '["opacity"] = 0.5, ["glass"] = { 0.3916, 0.7454, 1.0 } }' in lua
                      and glass.lods[0].vertex_count == collar.lods[0].vertex_count and where
                      and not luacheck.check(lua))
            # The pebble: the ring as it is (2 cm up) on the ground mesh's root bone, with its picture and
            # the plain ARM, in WCModsItems; the herb like Marigold lies as the game's pickup of it.
            pebble = "/Game/WCMods/good/Materials_WCModsTestPebble_SK"
            ground = skelmesh.SkeletalMesh(made.read_file(texture.content_path(pebble))).geometry(0)
            lifted = models.place(model, {"up": 2})
            with open(os.path.join(tmp, "out", "ue4ss_shared", "WCModsItems", "WCModsItems.lua"), encoding="utf-8") as f:
                items_lua = f.read()
            packed = (packed and all(w == [(0, 1.0)] for w in ground["weights"]) and not any(ground["morphs"].values())
                      and all(math.dist(a, b) < 1e-3 for a, b in zip(ground["positions"], lifted.positions))
                      and all(texture.content_path(p) in made.files for p in (
                          "/Game/WCMods/good/Materials_WCModsTestPebble_BC", "/Game/WCMods/_items/T_GroundARM"))
                      and f'["Gameplay.Inventory.Materials.WCModsTestPebble"] = {{ ["mesh"] = "{pebble}.Materials_WCModsTestPebble_SK"'
                          in items_lua
                      and '["Gameplay.Inventory.Consumable.WCModsTestHerb"] = { ["class"] = "MediumHealingHerb" }' in items_lua
                      and not luacheck.check(items_lua))
        return ok and packed, f"{len(rows)} rows, {len(warned)} refused" + ("" if ok else f"; {out['warnings']}")


def _ring_obj(cfg):
    """A model for a test: the Dog Collar's own shape, a fifth bigger, as an OBJ file (models.write_obj)."""
    from . import accessories, models
    from .formats import skelmesh, texture
    from .gamefiles import GameFiles
    game = GameFiles(cfg)
    path = accessories.read_meshes(game.read(accessories.GUI_MANAGER))["DogCollar"].split(".", 1)[0]
    mesh = skelmesh.SkeletalMesh(game.read(texture.content_path(path)))
    geo = mesh.geometry(0)
    o = mesh.bounds[:3]
    geo["positions"] = [tuple(o[c] + (p[c] - o[c]) * 1.2 for c in range(3)) for p in geo["positions"]]
    return models.write_obj("ring", geo)


def _skeletal_meshes(io):
    """Every accessory's mesh and the cat's body read and written back byte for byte (their morph data
    re-encoded), the GUI manager's model for every accessory with looks, and a model through OBJ into a copy."""
    from . import accessories, models
    from .formats import skelmesh, texture
    gui = io.read_file(accessories.GUI_MANAGER)
    meshes, looks = accessories.read_meshes(gui), accessories.read_variations(gui)
    paths = sorted({p.split(".", 1)[0] for p in meshes.values()}) + [models.BODY]
    bad = []
    for p in paths:
        data = io.read_file(texture.content_path(p))
        try:
            if skelmesh.SkeletalMesh(data).bytes() != data:
                bad.append(p.rsplit("/", 1)[-1])
        except ValueError as e:
            bad.append(f"{p.rsplit('/', 1)[-1]} ({e})")
    mesh = skelmesh.SkeletalMesh(io.read_file(texture.content_path(meshes["DogCollar"].split(".", 1)[0])))
    geo = mesh.geometry(0)
    model = models.read("collar.obj", models.write_obj("collar", geo).encode())
    # The same triangles in the same places (a read joins vertices that are alike in every way).
    same = len(model.triangles) == len(geo["triangles"]) and all(
        math.dist(model.positions[i], geo["positions"][j]) < 1e-3
        for t, u in zip(model.triangles, geo["triangles"]) for i, j in zip(t, u))
    body = models.Body(type("Game", (), {"read": staticmethod(io.read_file)})())
    shaped, farthest = models.mesh_model(model, body.skin(mesh.morph_names))
    mesh.set_geometry(shaped)
    mesh.rename("/Game/WCMods/t/SK_Test", "SK_Test")
    back = skelmesh.SkeletalMesh(mesh.bytes())
    copied = (back.lods[0].vertex_count == len(model.positions) and back.export_names[back.main] == "SK_Test"
              and back.morph_names == mesh.morph_names and farthest < 3)
    detail = f"{len(paths)} meshes"
    if bad:
        detail += f"; differ: {bad[:4]}"
    if not same:
        detail += "; OBJ round trip differs"
    if not copied:
        detail += f"; the copy didn't read back (farthest {farthest:.1f} cm)"
    return not bad and set(meshes) >= set(looks) and same and copied, detail


def _animations(io):
    """The game's sequences (formats/anim.py) and a mod's animations (animations.py), against the game's files."""
    import collections
    from . import animations
    from .formats import anim, texture
    paths = [p for p in io.files if p.startswith("Wrc/Content/") and p.rsplit("/", 1)[-1].startswith("A_")
             and p.endswith(".uasset")]
    codecs, bad, undecoded, skeletons = collections.Counter(), [], [], {}
    for p in paths:
        data = io.read_file(p)
        if not anim.is_sequence(data):
            continue
        name = p.rsplit("/", 1)[-1][:-len(".uasset")]
        try:
            seq = anim.AnimSequence(data)
            if seq.bytes() != data:
                bad.append(name)
                continue
            codecs[seq.codec] += 1
            bind = None
            if seq.codec == "acl":       # what an ACL stream leaves out is its skeleton's reference pose
                on = seq.skeleton_name()
                if on not in skeletons:
                    skeletons[on] = anim.Skeleton(io.read_file(texture.content_path(on)))
                bind = seq.bind_pose(skeletons[on])
            seq.tracks(bind)
        except (ValueError, KeyError) as e:
            undecoded.append(f"{name} ({e})")
    read = lambda path: io.read_file(texture.content_path(path))          # noqa: E731
    copies = []
    for kind in animations.KINDS:
        try:
            skeleton = anim.Skeleton(read(animations.asset(kind, "skeleton")))
            seq = anim.AnimSequence(read(animations.asset(kind, "template")))
            imports, _ = io.container_header().entry_for(texture.package_id(animations.asset(kind, "template")))
            imports = seq.use_unreal_codec(imports)
            bones = animations.track_bones(skeleton)
            if seq.codec == "acl" or kind != "cat":
                seq.clear_curves()
            keys = [([t, t], [q, q], [s, s]) for t, q, s in (skeleton.poses[b] for b in bones)]
            seq.set_tracks(keys, bones=bones)
            seq.rename(f"/Game/WCMods/t/A_{kind}", f"A_{kind}")
            back = anim.AnimSequence(seq.bytes())
            # w comes back from x, y and z, so a rotation near w = 0 is only as close as float x, y, z make it.
            same = all(max(abs(x - y) for x, y in zip(a[1][0], (q if q[3] >= 0 else tuple(-v for v in q)))) < 1e-3
                       for a, q in zip(back.tracks(), (skeleton.poses[b][1] for b in bones)))
            if not (same and back.codec == "per-track" and back.track_map == bones and len(imports) == len(set(imports))
                    and abs(back.sequence_length() - 1 / back.frame_rate()) < 1e-6
                    and texture.package_id(anim.UE_SETTINGS) in imports):
                copies.append(f"{kind}: the copy reads back otherwise")
        except (ValueError, KeyError) as e:
            copies.append(f"{kind} ({e})")
    # The game's Stretch (per-track) and Idle (ACL) in the start kit's glTF and back: the same keys.
    kit_ok, detail_kit = False, ""
    try:
        game = type("Game", (), {"read": staticmethod(io.read_file)})()
        import io as _io
        import zipfile
        kits, short = {}, []
        for kind in animations.KINDS:        # every kind's kit, with all its examples
            data, _ = animations.start_kit(game, kind)
            kits[kind] = animations.Gltf(f"{kind}.glb", zipfile.ZipFile(_io.BytesIO(data)).read(f"{kind}.glb"))
            if len(kits[kind].clips) != len(animations.KINDS[kind]["examples"]):
                short.append(kind)
        gltf = kits["cat"]
        skeleton = anim.Skeleton(read(animations.asset("cat", "skeleton")))
        pose = animations.Game(io.read_file).rest("cat")

        def apart(a, b):                  # q and -q are the same turn
            return min(max(abs(x - y) for x, y in zip(a, b)), max(abs(x + y) for x, y in zip(a, b)))
        worst = turn = 0.0
        for example in ("A_CatMaster_Stretch_1", "A_CatMaster_Idle_1"):
            seq = anim.AnimSequence(read("/Game/Art/Characters/CatMaster/Animations/" + example))
            keys = seq.tracks(seq.bind_pose(skeleton))
            back = animations.retarget(gltf, gltf.clip(example), skeleton, seq.track_map, seq.frame_rate(), pose)
            worst = max([worst] + [math.dist(a, b) for (T, _, _), (T2, _, _) in zip(keys, back) for a, b in zip(T, T2)])
            turn = max([turn] + [apart(a, b) for (_, Q, _), (_, Q2, _) in zip(keys, back) for a, b in zip(Q, Q2)])
        kit_ok = worst < 1e-3 and turn < 1e-4 and not short
        detail_kit = (f"{len(kits)} start kits, {sum(len(k.clips) for k in kits.values())} examples"
                      + (f" (short: {', '.join(short)})" if short else "")
                      + f"; kit round trip {worst:.1e} cm, {turn:.1e} in rotations")
    except (ValueError, KeyError) as e:
        detail_kit = f"start kit: {e}"
    detail = (f"{sum(codecs.values())} sequences ({', '.join(f'{n} {c}' for c, n in sorted(codecs.items()))}); "
              f"{len(animations.KINDS)} templates; {detail_kit}")
    for what, items in (("differ", bad), ("don't decode", undecoded), ("templates", copies)):
        if items:
            detail += f"; {what}: {items[:3]}"
    return not bad and not undecoded and not copies and kit_ok and codecs["acl"] > 0, detail


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
    from . import cppmods
    from .exe import pe
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
        # A mod carrying builds for several UE4SS versions (`cpp build --keep`): dlls/main.dll is for another
        # UE4SS, dlls/8333063/ (a 7-character name, as a log can give) for the game's, and the install takes
        # the latter's main.dll and build.json with the helper DLL beside dlls/main.dll, and leaves the
        # versions' folders out.
        kept = make("kept", built_for={"ue4ss": "aaaa1111"})
        with open(os.path.join(kept.folder, "dlls", "helper.dll"), "wb") as f:
            f.write(b"MZ")
        for commit, built in (("8333063", "8333063595fa3c49ad307f3b0f732accbb760d25"), ("bbbb2222", "bbbb2222")):
            os.makedirs(os.path.join(kept.folder, "dlls", commit))
            with open(os.path.join(kept.folder, "dlls", commit, "main.dll"), "wb") as f:
                f.write(_tiny_dll(cpp.EXPORTS + ("kept_" + commit,)))
            with open(os.path.join(kept.folder, "dlls", commit, "build.json"), "w") as f:
                json.dump({"ue4ss": built}, f)
        sec = cpp.CppSection()
        ctx = BuildContext(None, None, tmp, log=lambda m: None)
        ctx.cfg = type("Cfg", (), {"data": {"allow_code_mods": True}, "win64_dir": win64})()
        ctx.begin(sec.id)
        sec.build(ctx, [(m, sec.collect(m, ctx)) for m in (good, other, unknown, kept)])
        kept_files = ctx.ue4ss_mods.get("WCModsCpp_kept", ({}, None))[0]
        kept_data = sec.collect(kept, ctx)
        if kept_data["variant"] != "8333063" \
                or sorted(kept_files) != ["dlls/helper.dll", "dlls/main.dll", "enabled.txt", "wcmods.json"] \
                or kept_data["built_for"] != {"ue4ss": "8333063595fa3c49ad307f3b0f732accbb760d25"} \
                or b"kept_8333063" not in kept_files["dlls/main.dll"]:
            problems.append(f"kept installs {kept_data['variant']} with {sorted(kept_files)}")
        # A fresh dlls/main.dll for the game's UE4SS (a build without --keep) wins over the kept one.
        with open(os.path.join(kept.folder, "dlls", "build.json"), "w") as f:
            json.dump({"ue4ss": "83330635"}, f)
        fresh = sec.collect(kept, ctx)
        if fresh["variant"] is not None or b"kept_8333063" in fresh["files"]["main.dll"]:
            problems.append(f"a fresh main.dll for the game's UE4SS loses to the kept one ({fresh['variant']})")
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
                or cpp.matches({"ue4ss": "1234567"}, {"commit": None, "dll": "x"}) is not None
                or cpp.same_commit("8333063", "83330635AB") is not True or cpp.same_commit("8333063", "8333064") is True):
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
    # A call as the SDK's: not `Json::object(` for the SDK's object(path), and not part of a longer name;
    # the game's UI is called as `ui::text(`.
    untested = sorted(n for n in names - private if not re.search(rf"(?<![:\w])(?:ui::)?{n}\s*[(<]", tested))
    if untested:
        problems.append(f"not called by tests/cpp-sdk: {', '.join(untested[:8])}")
    test_py = os.path.join(os.path.dirname(here), "tests", "game", "test_cpp_sdk.py")
    if not os.path.isfile(test_py):
        problems.append("tests/game/test_cpp_sdk.py is missing")
    return not problems, "; ".join(problems[:3]) or f"{len(names)} calls, all in SDK.md and tests/cpp-sdk"


def _cpp_tooling():
    """The crash readout names the mod a crash was in from Unreal's crash context, and `cpp ide` picks the
    newest Visual Studio CMake knows."""
    from . import cppmods, crashes
    from .mods import Mod
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        folder = os.path.join(tmp, "mods", "boom")
        os.makedirs(folder)
        with open(os.path.join(folder, "mod.json"), "w") as f:
            f.write('{"name": "Boom"}')
        src = os.path.join(folder, "cpp", "src", "main.cpp")
        sdk = os.path.join(tmp, "sdk", "WCMods", "Events.hpp")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<FGenericCrashContext>
<RuntimeProperties>
<CrashType>Crash</CrashType>
<ErrorMessage>Unhandled Exception: EXCEPTION_ACCESS_VIOLATION reading address 0x0000000000000000</ErrorMessage>
<CallStack>
Wrc-Win64-ShippingDRM!UObject::ProcessEvent()
main!std::function&lt;void (wcmods::Call&amp;)&gt;::operator()() [{sdk}:120]
main!`SdkCheck::on_unreal_init'::`2'::&lt;lambda_5&gt;::operator()() [{src}:54]
UE4SS!RC::Unreal::Hook::Process()
KERNEL32!BaseThreadInitThunk()
</CallStack>
</RuntimeProperties>
</FGenericCrashContext>
"""
        crash = crashes.parse(xml)
        frames = crash["frames"]
        if crash["type"] != "Crash" or "ACCESS_VIOLATION" not in crash["error"] or len(frames) != 5 \
                or frames[2]["module"] != "main" or frames[2]["file"] != src or frames[2]["line"] != 54 \
                or frames[0]["file"] is not None or frames[0]["module"] != "Wrc-Win64-ShippingDRM":
            problems.append(f"crash context misread: {crash['type']!r}, {len(frames)} frames, {frames[2] if len(frames) > 2 else None}")
        who = crashes.blame(crash, [Mod(folder)], os.path.join(tmp, "sdk"))
        if not who or who["mod"] != "boom" or who["file"] != "cpp/src/main.cpp" or who["line"] != 54 or who["sdk"]:
            problems.append(f"blame is {who}")
        # With no mod of this folder's on the stack, the SDK's frame says a C++ mod was in it.
        who = crashes.blame(crash, [], os.path.join(tmp, "sdk"))
        if not who or who["mod"] or not who["sdk"] or who["file"] != "WCMods/Events.hpp":
            problems.append(f"blame without the mod is {who}")
        if crashes.blame(crash, [], os.path.join(tmp, "elsewhere")) is not None:
            problems.append("blames a C++ mod with none on the stack")
        path = os.path.join(tmp, "CrashContext.runtime-xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)
        text = crashes.readout(path, [Mod(folder)], os.path.join(tmp, "sdk"))
        if "in the C++ mod boom: cpp/src/main.cpp:54" not in text or "ACCESS_VIOLATION" not in text:
            problems.append(f"readout says: {text.splitlines()[:2]}")
    help_text = "Generators\n  Visual Studio 17 2022        = Generates Visual Studio 2022 project files.\n" \
                "  Visual Studio 18 2026        = Generates Visual Studio 2026 project files.\n  Ninja\n"
    if cppmods.vs_generator(help_text) != "Visual Studio 18 2026" or cppmods.vs_generator("Ninja") is not None:
        problems.append(f"vs_generator picks {cppmods.vs_generator(help_text)}")
    from .sections.cpp import VARIANT
    if not VARIANT.match("83330635") or VARIANT.match("main.dll") or VARIANT.match("abc"):
        problems.append("VARIANT matches the wrong folder names")
    return not problems, "; ".join(problems[:3])


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
    a mod.json value Mod can't use is refused; a mod added on turns on what it requires, and the mod menu
    (wcmods' own) counts as there; a removed mod whose id ends in a number comes back under that id."""
    import json
    from . import modzip, mods as modlib
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
            {"name": "Pack", "requires": ["helper", "mod-menu"]})}), root, backups)
        helper_on = Mod(os.path.join(root, "helper")).enabled
        unmet = modlib.unmet(modlib.discover(root))
        gone = modzip.remove(Mod(os.path.join(root, "pack-2")), backups)
        back = modzip.restore(backups, gone, root)
        return (hidden[0]["code"] and refused == 2 and helper_on and not unmet
                and added[0]["also_on"] == ["Helper"] and back == "pack-2")


def _mods_folder(tmp, mods, build=None):
    """Test mods in a folder of their own. With `build`, the installed game's, each mod that doesn't say
    which builds it was made for is made for that one, so a build on a newer game doesn't hold it back."""
    import json
    root = os.path.join(tmp, "mods")
    for mod_id, (meta, files) in mods.items():
        if build and "game_builds" not in meta and "game_build" not in meta:
            meta = dict(meta, game_builds=[build])
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
                                  "lost": ({"name": "Lost", "requires": ["ghost"], "enabled": True}, {})},
                            build=gamebuild.steam_build(cfg))
        on, _ = mods.switch(mods.discover(root), "needy", True)
        _, blocked = mods.switch(mods.discover(root), "helper", False)
        out = pipeline.build(cfg, mods.discover(root), os.path.join(tmp, "out"), log=lambda m: None)
        rep = out["sections"].get("requirements", {})
        return (sorted(on) == [("helper", True), ("needy", True)] and blocked == ["needy"]
                and "lost" not in out["mods"] and "needy" in out["mods"] and rep.get("status") == "failed"
                and any("ghost" in e for e in rep.get("errors", [])))


def _menu_window(cfg):
    """The mod menu's window goes in with every build, its key from wcmods.json; its Overview says how to get
    the Menu pages mod while it's missing, off or can't run, and nothing once the build has it."""
    from . import menu, menupages, mods, pipeline
    keys = ("menu_key", "menu_pad", "menu_scale", "allow_code_mods")
    kept = {k: cfg.data.pop(k) for k in keys if k in cfg.data}
    problems = []
    try:
        cfg.data["menu_key"] = "F2"
        build = gamebuild.steam_build(cfg)
        pages = ({"name": "Menu pages", "author": "wcmods", "uses": ["mod-menu"]},
                 {"scripts/main.lua": "local Menu = require('WCModsMenu')\n", "settings.json": '{"cheats": false}'})
        for label, folder, code, wanted in (
                ("no mods", {}, False, "Get set up"),
                ("Menu pages off", {menupages.ID: ({**pages[0], "enabled": False}, pages[1])}, True, "which is off"),
                ("Menu pages without code allowed", {menupages.ID: pages}, False, "allow mods that run code"),
                ("Menu pages on", {menupages.ID: pages}, True, None)):
            cfg.data["allow_code_mods"] = code
            with tempfile.TemporaryDirectory() as tmp:
                root = _mods_folder(tmp, folder, build=build)
                out = pipeline.build(cfg, mods.discover(root), os.path.join(tmp, "out"), log=lambda m: None)
                host = os.path.join(tmp, "out", "ue4ss", menu.HOST_NAME, "Scripts", "main.lua")
                text = open(host, encoding="utf-8").read() if os.path.isfile(host) else ""
                note = re.search(r'\["pages_note"\] = "([^"]*)"', text)
                if not (menu.HOST_NAME in out["ue4ss_mods"] and menu.SHARED_NAME in out["ue4ss_shared"]
                        and '["key"] = "F2"' in text and out["menu"] == {"key": "F2", "pad": menu.DEFAULT_PAD, "size": 1.0}):
                    problems.append(f"{label}: the window isn't in, or not with F2")
                if not note or (wanted is None) != (note.group(1) == "") or (wanted and wanted not in note.group(1)):
                    problems.append(f"{label}: the Overview says {note.group(1) if note else None!r}")
                if wanted is None and "WCModsScript_menu_pages" not in out["ue4ss_mods"]:
                    problems.append(f"{label}: its script isn't in")
    finally:
        for k in keys:
            cfg.data.pop(k, None)
        cfg.data.update(kept)
    return not problems, "; ".join(problems)


def _menu_pages():
    """menupages.add from a .zip: in, on, with the old mod menu's cheats (wcmods.json "cheats") taken into its
    settings.json; again with a newer .zip, turned off in between: still off, your settings kept and the
    new copy's new keys added, the older copy in backups."""
    import json
    from . import menupages, menusettings, modzip
    from .config import Config
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        data = os.path.join(tmp, "data")
        os.makedirs(data)
        with open(os.path.join(data, "wcmods.json"), "w") as f:
            json.dump({"cheats": True}, f)
        cfg = Config(tmp, data)

        def release(version, settings):
            return _zip(os.path.join(tmp, f"menu-pages-{version}.zip"), {
                "menu-pages/mod.json": json.dumps({"name": "Menu pages", "version": version, "uses": ["mod-menu"]}),
                "menu-pages/scripts/main.lua": "", "menu-pages/settings.json": json.dumps(settings)})

        def settings():
            with open(os.path.join(cfg.mods_root, menupages.ID, "settings.json"), encoding="utf-8") as f:
                return json.load(f)

        first = menupages.add(cfg, release("1.0", {"_help": "1", "cheats": False}), log=lambda m: None)
        m = menupages.installed(cfg.mods_root)
        if not (first["version"] == "1.0" and m and m.enabled and settings() == {"_help": "1", "cheats": True}):
            problems.append(f"the first add: {first}, {settings()}")
        if "cheats" in Config(tmp, data).data:
            problems.append("wcmods.json still has the old cheats")
        m.set_enabled(False)
        menupages.cheats(cfg, False)
        menupages.cheats(cfg, True)
        second = menupages.add(cfg, release("1.1", {"_help": "2", "cheats": False, "more": 1}), log=lambda m: None)
        m = menupages.installed(cfg.mods_root)
        if not (second["version"] == "1.1" and second["replaced"] and m and not m.enabled
                and settings() == {"_help": "2", "cheats": True, "more": 1}):
            problems.append(f"the update: {second}, on {m and m.enabled}, {settings()}")
        try:
            menupages.add(cfg, _zip(os.path.join(tmp, "other.zip"), {"other/mod.json": "{}"}), log=lambda m: None)
            problems.append("a .zip without menu-pages was taken")
        except ValueError:
            pass
        # Get the latest when GitHub's latest is the version you have: nothing downloaded or replaced.
        kept = menupages.find_release
        menupages.find_release = lambda timeout=20: {"name": "menu-pages-1.1.zip", "url": "http://invalid/", "size": 1,
                                                     "version": "1.1", "page": ""}
        try:
            same = menupages.add(cfg, log=lambda m: None)
        finally:
            menupages.find_release = kept
        if not same["unchanged"] or len(modzip.removed(cfg.backups_dir)) != 1:
            problems.append(f"Get the latest with nothing newer: {same}")
        # The studio's Options show and set its cheats at start.
        if menusettings.options(cfg)["cheats"] is not True or menusettings.set_options(cfg, cheats=False)["cheats"] is not False \
                or menupages.cheats(cfg) is not False:
            problems.append("cheats at start through the studio's Options")
    return not problems, "; ".join(problems)


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
        cfg = Config(root, root)
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
        before = onboarding.status(cfg, backups)
        onboarding.skip_pages(cfg)
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
                and not before["done"] and not before["pages"]["ok"] and st["pages"]["ok"]
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
            json.dump({"game_dir": os.path.join(tmp, "Game"),
                       "installed": {"mods": ["m"], "built": built, "ue4ss": False}}, f)
        cfg = Config(conf, conf)
        before = pipeline.pending(cfg, discover(root))
        fresh = os.path.join(tmp, "fresh")   # a first start with no mods: nothing to install without UE4SS
        os.makedirs(fresh)
        with open(os.path.join(fresh, "wcmods.json"), "w") as f:
            json.dump({"game_dir": os.path.join(tmp, "Game")}, f)
        none_yet = pipeline.pending(Config(fresh, fresh), [])
        os.makedirs(os.path.join(win64, "ue4ss", "Mods"))
        after = pipeline.pending(cfg, discover(root))
        ok.append(not before["any"] and after["any"] and after["redo"])
        # With UE4SS, the mod menu's window is worth an install even with no mods on.
        window = pipeline.pending(Config(fresh, fresh), [])
        ok.append(not none_yet["any"] and window["any"] and any("mod menu" in r for r in window["redo"]))
        # A test install (agent install) left code in the game: Apply takes it out unless code mods are allowed.
        tested = os.path.join(tmp, "tested")
        os.makedirs(tested)
        for allow in (False, True):
            with open(os.path.join(tested, "wcmods.json"), "w") as f:
                json.dump({"game_dir": os.path.join(tmp, "Game"), "allow_code_mods": allow,
                           "installed_ue4ss": ["WCModsCore", "WCModsScript_m", "WCModsMenuHost", "WCModsBridge"],
                           "installed": {"mods": ["m"], "built": built, "ue4ss": True}}, f)
            redo = pipeline.pending(Config(tested, tested), discover(root))["redo"]
            ok.append(any("test install" in r for r in redo) != allow)

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
        ctx = Ctx(bare, bare)
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


def _user_data():
    """Your files outside wcmods' folder (userdata.py): what an older version kept in its folder moves out
    on the first start (to another drive too), the old mod menu's settings go into wcmods.json and its folder
    goes, a second copy of wcmods moving in loses nothing, and the last install is redone once so the game
    finds the mods."""
    import errno
    import json
    from . import pipeline, userdata
    from .config import Config, EXE_NAME
    from .mods import discover
    problems = []

    def read(*parts):
        try:
            with open(os.path.join(*parts), encoding="utf-8-sig") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def write(path, value):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(value if isinstance(value, str) else json.dumps(value))

    # The mod menu's own mod as older versions had it in mods/.
    menu_meta = {"name": "Mod menu", "enabled": True, "priority": -100, "version": "1.0", "author": "wcmods", "builtin": True}
    with tempfile.TemporaryDirectory() as tmp:
        game = os.path.join(tmp, "Game")
        os.makedirs(os.path.join(game, "Wrc", "Binaries", "Win64"))
        open(os.path.join(game, "Wrc", "Binaries", "Win64", EXE_NAME), "w").close()
        old, data = os.path.join(tmp, "wcmods"), os.path.join(tmp, "data")
        write(os.path.join(old, "wcmods.json"), {"game_dir": game, "installed": {"mods": ["mine"], "built": "2999-01-01T00:00:00"}})
        write(os.path.join(old, "mods", "mine", "mod.json"), {"name": "Mine", "enabled": True})
        write(os.path.join(old, "mods", "mine", "palette.json"), "{}")
        write(os.path.join(old, "mods", "_half", "notes.txt"), "half made")
        write(os.path.join(old, "mods", "mod-menu", "mod.json"), {**menu_meta, "enabled": False, "priority": 5})
        write(os.path.join(old, "mods", "mod-menu", "menu.json"), {"_help": "old", "key": "F2", "size": 1.25, "cheats": True})
        write(os.path.join(old, "backups", "20260101-000000-manual", "WrcGame.sav"), "save")
        write(os.path.join(old, "backups", "mods", "20260101-000000-removed-gone", "mod.json"), {"name": "Gone"})
        said = []
        userdata.prepare(old, data, log=said.append)
        if (read(data, "wcmods.json") or {}).get("game_dir") != game or os.path.exists(os.path.join(old, "wcmods.json")):
            problems.append("wcmods.json didn't move")
        if not os.path.isfile(os.path.join(data, "mods", "mine", "palette.json")) or os.path.exists(os.path.join(old, "mods")) \
                or not os.path.isfile(os.path.join(data, "mods", "_half", "notes.txt")):
            problems.append(f"mods didn't move: {sorted(os.listdir(os.path.join(data, 'mods')))}")
        if not os.path.isfile(os.path.join(data, "backups", "20260101-000000-manual", "WrcGame.sav")) \
                or not os.path.isdir(os.path.join(data, "backups", "mods", "20260101-000000-removed-gone")) \
                or os.path.exists(os.path.join(old, "backups")):
            problems.append("backups didn't move")
        if len(said) != 2 or "1 mod and backups" not in said[0] or data not in said[0] or "Menu pages" not in said[1]:
            problems.append(f"said {said}")
        settings = read(data, "wcmods.json") or {}
        if os.path.exists(os.path.join(data, "mods", "mod-menu")) or (settings.get("menu_key"), settings.get("menu_scale"),
                                                                      settings.get("cheats")) != ("F2", 1.25, True):
            problems.append(f"the old mod menu: {settings}")

        # The last install was made from the old folder: redone once; one made from here isn't.
        cfg = Config(old, data)
        found = discover(cfg.mods_root)
        if not any("moved" in r for r in pipeline.pending(cfg, found)["redo"]):
            problems.append("an install from the old mods folder isn't redone")
        cfg.data["installed"]["mods_root"] = cfg.mods_root
        cfg.save()   # pending() reads wcmods.json afresh
        if any("moved" in r for r in pipeline.pending(cfg, found)["redo"]):
            problems.append("an install from this mods folder is redone")

        # A second copy of wcmods moving in: what's here stays (taking settings only the other has); its
        # copies go to backups, a removed mod's under a number that keeps its id.
        old2 = os.path.join(tmp, "wcmods2")
        write(os.path.join(old2, "wcmods.json"), {"game_dir": "elsewhere", "console": True})
        write(os.path.join(old2, "mods", "mine", "mod.json"), {"name": "Mine, the other copy"})
        write(os.path.join(old2, "mods", "mod-menu", "mod.json"), menu_meta)
        write(os.path.join(old2, "mods", "mod-menu", "menu.json"), {"key": "F3"})
        write(os.path.join(old2, "backups", "mods", "20260101-000000-removed-gone", "mod.json"), {"name": "Gone too"})
        said = []
        userdata.prepare(old2, data, log=said.append)
        kept = [n for n in os.listdir(os.path.join(data, "backups")) if n.endswith("-wcmods.json")]
        now = read(data, "wcmods.json")
        if now["game_dir"] != game or now.get("console") is not True or len(kept) != 1 \
                or read(data, "backups", kept[0]) != {"game_dir": "elsewhere", "console": True}:
            problems.append(f"a second wcmods.json: {now}, {kept}")
        replaced = [n for n in os.listdir(os.path.join(data, "backups", "mods")) if n.endswith("-replaced-mine")]
        if read(data, "mods", "mine", "mod.json")["name"] != "Mine" or len(replaced) != 1:
            problems.append(f"a second copy of a mod: {replaced}")
        if read(data, "wcmods.json").get("menu_key") != "F2" or os.path.exists(os.path.join(data, "mods", "mod-menu")) \
                or os.path.exists(os.path.join(old2, "mods")):
            problems.append("a second copy of the mod menu")
        if read(data, "backups", "mods", "20260101-000000-2-removed-gone", "mod.json") != {"name": "Gone too"}:
            problems.append(f"a second removed mod: {sorted(os.listdir(os.path.join(data, 'backups', 'mods')))}")
        if not any("stays" in s and kept[0] in s for s in said) or not any("-replaced-mine" in s for s in said):
            problems.append(f"said {said}")

        # A new player: nothing to move and nothing to say. Then their old folder after all, over a mod menu
        # with its defaults that the version before put in: the old one's settings count.
        said = []
        fresh = os.path.join(tmp, "new-data")
        userdata.prepare(os.path.join(tmp, "new"), fresh, log=said.append)
        if said or (os.path.isdir(fresh) and os.listdir(fresh)):
            problems.append("a first start")
        write(os.path.join(fresh, "mods", "mod-menu", "mod.json"), menu_meta)
        write(os.path.join(fresh, "mods", "mod-menu", "menu.json"), {"_help": "new", "key": "INS", "size": 1.0, "cheats": False})
        old3 = os.path.join(tmp, "wcmods3")
        write(os.path.join(old3, "mods", "mod-menu", "mod.json"), {**menu_meta, "enabled": False})
        write(os.path.join(old3, "mods", "mod-menu", "menu.json"), {"key": "F4"})
        userdata.prepare(old3, fresh, log=said.append)
        if (read(fresh, "wcmods.json") or {}).get("menu_key") != "F4" or os.path.exists(os.path.join(fresh, "mods", "mod-menu")):
            problems.append(f"an old mod menu over one only put in: {read(fresh, 'wcmods.json')}")

        # WCMODS_DATA as wcmods' own folder, spelled as it is or through a junction: everything stays.
        said, here = [], os.path.join(tmp, "here")
        write(os.path.join(here, "mods", "mine", "mod.json"), {"name": "Mine"})
        write(os.path.join(here, "mods", "mod-menu", "mod.json"), {"name": "My menu", "author": "me"})
        write(os.path.join(here, "mods", "mod-menu", "menu.json"), {"key": "F5"})
        write(os.path.join(here, "mods", "mod-menu", "scripts", "main.lua"), "")   # a player's own mod-menu stays
        write(os.path.join(here, "wcmods.json"), {"console": True})
        try:
            import _winapi
            _winapi.CreateJunction(here, os.path.join(tmp, "there"))
            spellings = [here, os.path.join(tmp, "there")]
        except (ImportError, AttributeError, OSError):
            spellings = [here]
        for spelled in spellings:
            userdata.prepare(here, spelled, log=said.append)
            if said or sorted(os.listdir(os.path.join(here, "mods"))) != ["mine", "mod-menu"] \
                    or read(here, "wcmods.json") != {"console": True} or os.path.exists(os.path.join(here, "backups")):
                problems.append(f"data in wcmods' own folder, as {spelled}")

        # The old mod menu moving in where the data folder has a mod-menu of a player's own: that one stays,
        # and the old one's settings still go into wcmods.json.
        own, old4 = os.path.join(tmp, "own-data"), os.path.join(tmp, "wcmods4")
        write(os.path.join(own, "mods", "mod-menu", "mod.json"), {"name": "My menu", "author": "me"})
        write(os.path.join(own, "mods", "mod-menu", "scripts", "main.lua"), "")
        write(os.path.join(old4, "mods", "mod-menu", "mod.json"), menu_meta)
        write(os.path.join(old4, "mods", "mod-menu", "menu.json"), {"key": "F6"})
        userdata.prepare(old4, own, log=lambda m: None)
        if (read(own, "wcmods.json") or {}).get("menu_key") != "F6" \
                or read(own, "mods", "mod-menu", "mod.json") != {"name": "My menu", "author": "me"}:
            problems.append(f"the old mod menu beside a player's own: {read(own, 'wcmods.json')}")

        # A folder going to another drive: copied whole, then the old one taken away.
        src, dest = os.path.join(tmp, "far", "x"), os.path.join(tmp, "farther", "x")
        write(os.path.join(src, "mod.json"), {"name": "X"})
        rename, moves = os.rename, []

        def other_drive(a, b):
            if a == src:
                raise OSError(errno.EXDEV, "not the same drive")
            rename(a, b)
        os.rename = other_drive
        try:
            userdata._move(src, dest, moves)
        finally:
            os.rename = rename
        if moves or os.path.exists(src) or read(dest, "mod.json") != {"name": "X"} \
                or os.listdir(os.path.dirname(dest)) != ["x"]:
            problems.append(f"a move to another drive: {moves}")
    return not problems, "; ".join(problems)


def kraken_samples():
    """Inputs for the Kraken fixtures in tests/kraken (made by tools/make_kraken_fixtures.py with an
    oo2core DLL): {name: bytes}, the same every time, shaped to reach the decoder's paths: text
    (Huffman and short matches), records (tANS, RLE and arrays), long runs of one byte (memset
    quanta), noise (stored as it is) and a mix with matches further back than 64 KB."""
    import random
    import struct
    rng = random.Random(20261026)
    words = ("the clan cats walk the forest at dawn moss fern river shadow thunder wind sky star leaf "
             "paw whisker tail claw den nest prey hunt patrol border moon gathering warrior apprentice "
             "medicine elder kit queen leader deputy camp hollow stream oak pine bramble heather").split()
    text = bytearray()
    while len(text) < 64 * 1024:
        n = rng.randint(4, 14)
        line = " ".join(rng.choice(words) for _ in range(n)).capitalize() + ".\r\n"
        text += line.encode()
    records = bytearray()
    for i in range(6 * 1024):
        records += struct.pack("<IHHf", i, i % 7, 1000 + (i * 37) % 500, float(i % 13) / 4)
        if i % 512 == 511:
            records += bytes(64)
    runs = bytes(70 * 1024) + text[:1024] + bytes(200 * 1024) + b"\xff" * 3000
    noise = rng.randbytes(20 * 1024)
    mixed = bytes(text) + bytes(records[:100 * 1024]) + bytes(text) + noise[:4096] + bytes(text[:30000])
    return {"text": bytes(text), "records": bytes(records), "runs": runs, "noise": noise, "mixed": mixed}


def _kraken_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "kraken")


def _kraken_fixtures():
    """Every fixture decodes to the sample it was made from."""
    import hashlib
    import json
    from .formats import kraken
    folder = _kraken_dir()
    try:
        with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
    except OSError as e:
        return False, f"no fixtures: {e}"
    samples = kraken_samples()
    bad = []
    for entry in manifest:
        raw = samples.get(entry["sample"])
        if raw is None or len(raw) != entry["size"] or hashlib.sha1(raw).hexdigest() != entry["sha1"]:
            bad.append(f"{entry['file']}: the sample isn't what the fixture was made from")
            continue
        with open(os.path.join(folder, entry["file"]), "rb") as f:
            packed = f.read()
        try:
            got = kraken.decompress(packed, len(raw))
        except kraken.KrakenError as e:
            bad.append(f"{entry['file']}: {e}")
            continue
        if got != raw:
            first = next(i for i in range(len(raw)) if got[i] != raw[i])
            bad.append(f"{entry['file']}: differs at byte {first}")
    return not bad, f"{len(manifest)} fixtures" + (f"; {bad[:3]}" if bad else "")


def _kraken_against_dll(io, oodle):
    """A few of the game's own compressed blocks: the Python decoder and the DLL agree."""
    from .formats import kraken
    picks = [i for i, (_, _, _, m) in enumerate(io.blocks) if m][::max(1, len(io.blocks) // 12)][:12]
    bad = 0
    with open(io.ucas_path, "rb") as f:
        for bi in picks:
            boff, csize, usize, _ = io.blocks[bi]
            f.seek(boff)
            raw = f.read(csize)
            if kraken.decompress(raw, usize) != oodle.decompress(raw, usize):
                bad += 1
    return bad == 0, f"{len(picks)} blocks" + (f", {bad} differ" if bad else "")


def _signatures(cfg):
    """On the installed exe: the decoder cuts .pdata's functions at their ends, and (on a build wcmods was
    checked on) signatures.check finds every class and every member where game.HIDDEN says."""
    from .exe import gamebuild, pe, signatures, x64
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
    from . import game, mods, pipeline
    from .exe import gamebuild, pe, signatures
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
            p = pipeline.pending(Config(conf, conf), mods.discover(root))
            if not any("game updated" in r for r in p["redo"]):
                problems.append("an install from the old build isn't redone")
            # The cats' names for the mod menu, built from the game's tables (layout still off).
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
    from . import mods, pipeline
    from .exe import gamebuild
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
    from .formats import csvdata
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
    from . import catcolours
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
    look = catcolours.validate({"player": {"colours": {"fur": "#ff6ec7", "nose": "#202020"}, "slots": {"fur": 3, "pattern": 25}}})
    script = catcolours.script(look["player"]["colours"])
    try:
        catcolours.validate({"player": {"slots": {"fur": 25}}})
        fur_refused = False
    except ValueError:
        fur_refused = True
    text = '(ClanType=RiverClan,FurColorIdx=11,Pattern01ColorIdx=2,CatSize=0.5)'
    fields = catcolours.set_fields(text, {"FurColorIdx": 3, "Pattern01ColorIdx": 25, "Pattern02ColorIdx": 26})
    # Scars: "none" takes them all away; each place takes a scar's name or the game's number for it.
    scars = catcolours.validate({"player": {"scars": "none"}})["player"]["scars"]
    some = catcolours.validate({"player": {"scars": {"eye": 3, "ear": "notch-left", "body": "none"}}})["player"]["scars"]
    named = catcolours.validate({"player": {"scars": {"eye": "claws-left", "back": "claws-1", "chest": "bite"}}})["player"]["scars"]
    refused = 0
    kept = catcolours.validate({"player": {"scars": {"back": 5}}})["player"]["scars"]   # the game's, with a warning
    for bad in ({"scars": {"eye": 7}}, {"scars": {"chest": 3}}, {"scars": {"ear": "chewed"}}, {"scars": {"back": 7}},
                {"scars": {"tail": "none"}}, {"scars": "some"}, {"scars": {"ear": ["notch-left"]}},
                {"scars": {"body": 2, "back": 4}}):
        try:
            catcolours.validate({"player": bad})
        except ValueError:
            refused += 1
    scarred = catcolours.set_fields('(ClanType=RiverClan,CatSize=0.5,ScarEarId=4,ScarBodyId=2)',
                                 {catcolours.SCARS[p]: 0 for p in scars})
    return (ok and fur_refused and not luacheck.check(script) and '["Fur Color"]' in script
            and fields == '(ClanType=RiverClan,FurColorIdx=3,Pattern01ColorIdx=25,CatSize=0.5,Pattern02ColorIdx=26)'
            and set(scars) == set(catcolours.SCARS) and not any(scars.values())
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
                                            {"cats.json": json.dumps({"player": {"scars": {"ear": "notch-left", "eye": "none"}}})})},
                            build=gamebuild.steam_build(cfg))
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
    get a text in every language, needed suffixes stay, the ban list follows, and cats are picked by name,
    place or "player" in a save of one game or several."""
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
    # Shown names: a cat already renamed to a mod's own text (Glow) is listed by that text, not blank, and a
    # rename is logged from the name the cat has; the in-game module gets a few added keys to check the game has.
    from . import world
    listed = {c["target"]: c for c in names.cat_list(plan, cats, ops)}
    ndata = world.names_data(plan)
    ok_shown = (listed["RiverClan/Warrior/2"]["name"] == "Glow" and listed["player"]["name"] == "Otterheart"
                and listed["RiverClan/Warrior/0"]["with_mods"] == "Sparkle"
                and plan.cat_renames == [("Woodheart", "Sparkle")]
                and ndata["added"] and set(ndata["added"]) <= set(plan.added_keys)
                and ndata["whole"].get("STR_CAT_NAME_WCM_GLIMMER_PAW") == "Glimmerpaw")

    # Two games in one save (a cat slot each; slot 1 being played): its cats come first, your cat first in
    # each; "player", a name or a place means the game being played, a slot first picks another game's cat,
    # and a name only another game has still counts; the studio's list keys each cat the same way.
    two = {"Shared": {"General": {"CurrentCatSlot": 1}}, "0": data["0"],
           "1": {"GameplayProgression": {"Gameplay.Combat.Character.Cat.Player": {"Customization": cat.format("STR_CAT_NAME53")}},
                 "NPCData": {"RiverClan": {"Warrior": [cat.format("STR_CAT_NAME1")]}}}}
    cats2 = names.cats_in_save(two)
    only_there = names.cat_list(names.Plan(game, names.merge([])), cats2)[4]["name"]   # a cat only slot 0 has
    plan2 = names.Plan(game, names.merge([names.validate({"cats": {
        "player": {"fixed": "Me"}, "Woodheart": {"fixed": "Sparkle"}, "0/RiverClan/Warrior/0": {"fixed": "Other"},
        only_there: {"fixed": "Far"}, "NPCData/RiverClan/Warrior/2": {"fixed": "Prefixed"},   # the old key forms still work
        "0/GameplayProgression/Gameplay.Combat.Character.Cat.Player/Customization": {"fixed": "Old"},
        "1/": {"fixed": "Nothing"}}})]))
    ops2 = sorted((o["path"], o["to"], o["where"]) for o in plan2.plan_cats(cats2))
    shown = names.cat_list(plan2, cats2, ())
    ok_two = (names.current_slot(two) == "1" and names.current_slot(data) == "0" and only_there
              and [(c["slot"], c["player"], c["current"]) for c in cats2] == [
                  ("1", True, True), ("1", False, True), ("0", True, False), ("0", False, False), ("0", False, False), ("0", False, False)]
              and ops2 == [("0/GameplayProgression/Gameplay.Combat.Character.Cat.Player/Customization", "Old", "0/player"),
                           ("0/NPCData/NarrativeRoles/TheAgingLeader", "Other", "0/NarrativeRoles/TheAgingLeader"),
                           ("0/NPCData/RiverClan/Warrior/0", "Other", "0/RiverClan/Warrior/0"),
                           ("0/NPCData/RiverClan/Warrior/1", "Far", "0/RiverClan/Warrior/1"),
                           ("0/NPCData/RiverClan/Warrior/2", "Prefixed", "0/RiverClan/Warrior/2"),
                           ("1/GameplayProgression/Gameplay.Combat.Character.Cat.Player/Customization", "Me", "you"),
                           ("1/NPCData/RiverClan/Warrior/0", "Sparkle", "RiverClan/Warrior/0")]
              and [w for w in plan2.warnings if w.startswith("cats:")] == ["cats: no cat in your save is called '1/'"]
              and [c["target"] for c in shown] == ["player", "RiverClan/Warrior/0", "0/player", "0/RiverClan/Warrior/0",
                                                   "0/RiverClan/Warrior/1", "0/RiverClan/Warrior/2"]
              and [c["where"] for c in shown[:3]] == ["you", "RiverClan/Warrior/0", "your cat"]
              and all(c["ids"]["PrefixNameId"] == "STR_CAT_NAME53" for c in cats2 if c["player"]))
    return ok and ok_cats and ok_shown and ok_two, f"{len(game.prefixes)} prefixes, {len(game.suffixes)} suffixes, {len(added)} new texts"


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
