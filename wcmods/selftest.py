"""Round-trip checks against the installed game and save. Writes only to a temp folder."""
import os
import struct
import tempfile

from . import controls, eyeatlas, keymap, luacheck, mouselook, palettes
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
    lua = mouselook.script(mouselook.merge([mouselook.validate({"sensitivity": 1.5, "invert": True})]))
    problems = luacheck.check(lua)
    check("mouse look script", not problems and "@SETTINGS@" not in lua and "sensitivity = 1.5" in lua
          and "invert = true" in lua, "; ".join(problems[:3]))
    problems = luacheck.check(palettes.ue4ss_script({}))
    check("palette script", not problems, "; ".join(problems[:3]))
    # Interact and Scent tracking move along F/E/Q, so Q goes quiet; X stays because Return to camp still
    # uses it; forward moves to I, so W goes quiet.
    send, block, warns = keymap.plan({"keyboard": {"Player_Interact": "F", "Player_Scent_Tracking": "E",
                                                   "Player_Den_Place": "Z"}, "keys": {"I": "W"}})
    check("key remap plan", send == {"F": "E", "E": "Q", "Z": "X", "I": "W"} and block == {"Q", "W"} and not warns)
    check("key remapper presses", _remapper_presses())
    check("menu remaps", _menu_remaps())
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
