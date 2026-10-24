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
    lua = mouselook.script(mouselook.merge([mouselook.validate({"sensitivity": 1.5, "invert": True, "smoothing": 50})]))
    problems = luacheck.check(lua)
    check("mouse look script", not problems and "@SETTINGS@" not in lua and "sensitivity = 1.5" in lua
          and "invert = true" in lua and "smoothing = 50.0" in lua, "; ".join(problems[:3]))
    for module in (view, draw, world, menu, game_lua):
        lua = module.lua()
        problems = luacheck.check(lua)
        left = re.findall(r"@[A-Z_]+@", lua)   # placeholders that weren't filled in
        check(f"shared module {module.SHARED_NAME}", not problems and not left, "; ".join(problems[:3] + left[:3]))
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
    lua = bridge.script(cfg)
    problems = luacheck.check(lua) + re.findall(r"@[A-Z_]+@", lua)
    check("game bridge script", not problems and bridge.folder(cfg).replace("\\", "/") in lua, "; ".join(problems[:3]))
    check("in-game script mod", _script_mod(cfg))
    check("mod menu answers the agent controller", all(s in menu.lua() for s in ('"agent.read"', '"agent.act"', '"agent.scroll"'))
          and 'Menu.share("frame"' in menu.host_script({"sections": {}, "notes": {}, "warnings": [], "built": ""}, []))
    check("agent controller: pictures, menu rows, test files", _agent_parts())
    check("adding a downloaded mod from a .zip (and refusing unsafe ones)", _mod_zips())
    check("a .zip can't hide code in a name's case, carry a bad mod.json or claim to come with wcmods",
          _mod_zip_guards())
    check("mods that need other mods: switched on together, left out of a build without them", _requirements(cfg))
    check("the mod menu is a mod: its window and module only with it on", _menu_mod(cfg))
    check("example mods: each one in examples/ reads, and the studio can list and add them", _examples())
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
    check("new colour slots and your cat's colours", _colour_slots())
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
        for name, text in files.items():
            with open(os.path.join(root, mod_id, name), "w") as f:
                f.write(text)
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


def _examples():
    """wcmods ships only the mod menu in mods/; examples/ holds the rest, each a mod the studio lists
    and adds as a copy."""
    from . import mods, modzip
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = os.path.join(here, "examples")
    found = mods.discover(folder)
    listed = modzip.inspect_folder(folder, os.path.join(here, "mods"))
    with tempfile.TemporaryDirectory() as tmp:
        mine = os.path.join(tmp, "mods")
        os.makedirs(mine)
        added = modzip.add_folder(folder, mine, os.path.join(tmp, "backups"), ids=["palette-dark-forest"], enable=True)
        copied = mods.discover(mine)
    return (len(found) >= 10 and len(listed) == len(found) and all(m.name for m in found)
            and not any(m.builtin for m in found)
            and [a["id"] for a in added] == ["palette-dark-forest"] and [m.id for m in copied] == ["palette-dark-forest"]
            and copied[0].enabled)


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
    return (ok and fur_refused and not luacheck.check(script) and '["Fur Color"]' in script
            and fields == '(ClanType=RiverClan,FurColorIdx=3,Pattern01ColorIdx=25,CatSize=0.5,Pattern02ColorIdx=26)')


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
