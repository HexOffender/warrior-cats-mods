"""Command line: python wcmods.py <command>."""
import argparse
import json
import os
import shutil
import sys
import time
import zipfile

from . import controls, eyeatlas, keymap, mods, names, pipeline, playstate, save, ue4ss
from .config import EXE_NAME, STEAM_APP_ID, Config, game_running
from .gamefiles import GameFiles
from .savejson import SaveDoc


class Ctx:
    def __init__(self, root):
        self.root = root
        self.cfg = Config(root)
        self.mods_root = os.path.join(root, "mods")
        self.build_dir = os.path.join(root, "build")
        self.backups = os.path.join(root, "backups")
        self._game = None

    def need_game(self):
        if not self.cfg.game_dir:
            sys.exit("Couldn't find the game. Put its folder in wcmods.json as \"game_dir\".")

    @property
    def game(self):
        self.need_game()
        if self._game is None:
            self._game = GameFiles(self.cfg)
        return self._game

    def need_oodle(self):
        if self.game.oodle is None:
            sys.exit("No Oodle DLL found (oo2core_*_win64.dll). Set \"oodle_dll\" in wcmods.json "
                     "to one shipped by another installed game.")


def cmd_status(ctx, args):
    cfg = ctx.cfg
    print(f"game folder : {cfg.game_dir or 'NOT FOUND'}")
    print(f"save folder : {cfg.save_dir} ({'found' if os.path.isfile(os.path.join(cfg.save_dir, save.SAV_NAME)) else 'no save yet'})")
    print(f"oodle dll   : {cfg.oodle_dll or 'NOT FOUND (needed for eye palettes, game data and extract)'}")
    print(f"UE4SS       : {cfg.ue4ss_mods_dir or 'not installed (needed for coat/pattern/marking colours)'}")
    if cfg.game_dir:
        inst = os.listdir(cfg.mods_install_dir) if os.path.isdir(cfg.mods_install_dir) else []
        print(f"installed   : {', '.join(inst) if inst else 'nothing'}")
        if pipeline.install_outdated(cfg):
            print("              built by an older wcmods, so the game never finds its files; install again")
    print(f"game running: {'yes' if game_running() else 'no'}")
    from . import gamebuild
    now = gamebuild.current(cfg)
    if now["build"]:
        print(f"game build  : {now['build']}" + (" (wcmods was checked on it)" if now["verified"] else
              " (newer than wcmods was checked on; `wcmods game build` says what that means)"))
    found = mods.discover(ctx.mods_root)
    old = gamebuild.outdated(cfg, found, now["build"])
    print("\nmods:")
    for m in found:
        note = ""
        if m.id in old:
            note = "  [made for an older version: " + ("used anyway]" if old[m.id]["allowed"] else "left out]")
        print(f"  [{'x' if m.enabled else ' '}] {m.id:28s} {', '.join(m.kinds()) or '(empty)':24s} {m.description}{note}")
    cfg.save()


def cmd_enable(ctx, args, value=True):
    for mod_id in args.mods:
        found = mods.discover(ctx.mods_root)
        if not any(m.id == mod_id for m in found):
            sys.exit(f"no mod named {mod_id}")
        # On: with what it requires. Off: with what needs it only when asked (--with-dependents).
        changed, blocked = mods.switch(found, mod_id, value, cascade=getattr(args, "with_dependents", False))
        if blocked:
            sys.exit(f"{', '.join(blocked)} need{'s' if len(blocked) == 1 else ''} {mod_id}; turn "
                     f"{'it' if len(blocked) == 1 else 'them'} off too with --with-dependents")
        for i, on in changed:
            print(f"{'enabled' if on else 'disabled'} {i}" + ("" if i == mod_id else
                  f" ({mod_id} needs it)" if on else f" (it needs {mod_id})"))
        if not changed:
            print(f"{mod_id} was already {'on' if value else 'off'}")


def cmd_add(ctx, args):
    from . import modzip
    folder = os.path.isdir(args.path)
    ids = [i.strip() for i in args.only.split(",") if i.strip()] if args.only else None
    # Several mods at once (a collection such as wcmods-examples) go in switched off, unless asked: turning
    # on every palette, remap and script in it at once is never what's wanted.
    found = modzip.inspect_folder(args.path, ctx.mods_root) if folder else modzip.inspect(args.path, ctx.mods_root)
    many = len(ids if ids is not None else found) > 1
    enable = not args.off and (args.on or not many)
    if folder:
        done = modzip.add_folder(args.path, ctx.mods_root, ctx.backups, ids=ids, enable=enable)
    else:
        done = modzip.add_zip(args.path, ctx.mods_root, ctx.backups, ids=ids, enable=enable)
    for d in done:
        if d.get("skipped"):
            print(f"skipped {d['id']} ({d['name']}): it {d['skipped']}")
            continue
        print(f"added {d['id']} ({d['name']})" + (f"; the old copy is in backups/mods/{d['replaced']}" if d["replaced"] else ""))
        for name in d["also_on"]:
            print(f"  also turned on {name} ({d['id']} needs it)")
        # The same check as the studio's preview (names as Windows sees them), so case can't hide code.
        if d["code"] and not ctx.cfg.data.get("allow_code_mods"):
            print(f"  note: {d['name']} runs code, so it stays out of the game until \"allow_code_mods\": true "
                  "(only for mods from people you trust)")
    found = mods.discover(ctx.mods_root)
    for d in done:
        for why in mods.unmet(found).get(d["id"], []):
            print(f"  {d['id']} {why}")
    if many and not enable:
        print("added switched off (several mods at once): `wcmods enable <mod>` turns on the ones you want")
    print("run `wcmods install` (game closed) to put it in the game")


def cmd_remove(ctx, args):
    from . import modzip
    found = mods.discover(ctx.mods_root)
    m = next((x for x in found if x.id == args.mod), None)
    if not m:
        sys.exit(f"no mod named {args.mod}")
    need = mods.needing(found, m.id)
    try:
        moved = modzip.remove(m, ctx.backups, found, cascade=args.with_dependents)
    except modzip.Needed as e:
        sys.exit(f"{e} (or remove it with --with-dependents, which turns them off too)")
    for i in need:
        print(f"disabled {i} (it needs {m.id})")
    print(f"moved {args.mod} to backups/mods/{moved}; install again to take it out of the game")


def cmd_pack(ctx, args):
    from . import modzip
    found = {m.id: m for m in mods.discover(ctx.mods_root)}
    if args.mod not in found:
        sys.exit(f"no mod named {args.mod}")
    m = found[args.mod]
    out = args.out or modzip.zip_name(m)
    with open(out, "wb") as f:
        f.write(modzip.pack(m))
    print(f"wrote {out}: give it to someone, and they add it with Clan Mod Studio or `wcmods add {os.path.basename(out)}`")


def cmd_new(ctx, args):
    mod = mods.create(ctx.mods_root, args.id)
    template = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", args.kind)
    if os.path.isdir(template):
        shutil.copytree(template, mod.folder, dirs_exist_ok=True)
    print(f"created {mod.folder} (disabled; run `wcmods enable {args.id}` when ready)")


def cmd_files(ctx, args):
    hits = ctx.game.find(args.pattern)
    for p in hits[:args.limit]:
        print(p)
    if len(hits) > args.limit:
        print(f"... {len(hits) - args.limit} more (use --limit)")


def cmd_extract(ctx, args):
    ctx.need_oodle()
    out = os.path.join(ctx.root, args.out)
    hits = ctx.game.find(args.pattern)
    for p in hits:
        dst = os.path.join(out, p.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(ctx.game.read(p))
    print(f"extracted {len(hits)} file(s) into {out}")


def cmd_texture(ctx, args):
    """One of the game's textures as a PNG to paint over: an accessory's look, an item's icon, or a
    texture by its asset path."""
    from . import accessories, cooked, png, texture
    ctx.need_oodle()
    what = args.what
    if what.split(".", 1)[0] in ("Head", "Neck", "Body", "Legs"):
        what = "Cosmetic." + what
    if what.startswith("/Game/"):
        asset = what
    elif what.startswith(("Cosmetic.", "Gameplay.Inventory.Cosmetic.")):
        parts = what.split("Cosmetic.", 1)[1].split(".")
        looks = accessories.read_variations(ctx.game.read(accessories.GUI_MANAGER))
        if len(parts) != 3 or parts[1] not in looks or not parts[2].isdigit() or not 0 < int(parts[2]) <= len(looks[parts[1]]):
            sys.exit(f"{what}: give an accessory and its look, e.g. Neck.DogCollar.1")
        asset = looks[parts[1]][int(parts[2]) - 1]
    else:
        rows = {v.get("itemTag"): v for _, v in cooked.DataTable(ctx.game.read(cooked.TABLES["DT_QuestObjectsInfo"][0]),
                                                                 "QuestObjectsInfoDataStruct").rows}
        tag = next((t for t in (what, f"Gameplay.Inventory.Consumable.{what}", f"Gameplay.Inventory.Materials.{what}")
                    if t in rows), None)
        if tag is None:
            sys.exit(f"{what}: not a texture (/Game/...), an accessory (Neck.DogCollar.1) or an item")
        asset = f"{rows[tag]['Icon']['package']}.{rows[tag]['Icon']['asset']}"
    try:
        tex = texture.load(ctx.game, asset)
    except ValueError as e:
        sys.exit(str(e) if asset in str(e) else f"{asset}: {e}")
    w, h, rgba = tex.image(0)
    out = args.out or os.path.join(ctx.root, "vanilla", "textures", asset.split(".", 1)[0].rsplit("/", 1)[-1] + ".png")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "wb") as f:
        f.write(png.write(w, h, rgba))
    print(f"{asset}: {w} x {h} {tex.format} -> {out}")
    print("paint over it and keep the size; a mod's items.json uses it as an item's \"icon\" or an accessory's \"texture\"")


def cmd_names(ctx, args):
    from .sdk import BuildContext
    ctx.need_oodle()
    game = names.GameNames(lambda path: ctx.game.read_text(BuildContext.data_path(path)))
    plan = names.Plan(game, names.merge(names.mod_specs(mods.discover(ctx.mods_root))))
    sav = os.path.join(ctx.cfg.save_dir, save.SAV_NAME)
    cats = names.cats_in_save(SaveDoc(save.SaveGame.load(sav).json_text).data) if os.path.isfile(sav) else []
    ops = plan.plan_cats(cats)
    if args.json:
        print(json.dumps({**game.summary(), "cats": names.cat_list(plan, cats, ops)}, indent=2))
        return
    if args.cats:
        if not cats:
            print("no save yet; start the game once")
        shown = names.cat_list(plan, cats, ops)
        games = len({c["slot"] for c in shown})
        last = None
        for c in shown:
            if games > 1 and c["slot"] != last:
                print(("" if last is None else "\n") + f"cat slot {c['slot']}" + (" (the game you're playing):" if c["current"] else ":"))
                last = c["slot"]
            now = c["name"] + (f" -> {c['with_mods']}" if c["with_mods"] != c["name"] else "")
            roles = f"  (story role: {', '.join(c['roles'])})" if c["roles"] else ""
            print(f"  {now:30s} {c['role']:16s} {c['target']}{roles}")
        print()
        print('In names.json, "cats" takes a cat by the name shown here, "player", or the last column'
              + (" (a slot first, like 1/player, picks a cat in another game; without one it means the game "
                 "you're playing)." if games > 1 else "."))
        return

    def show(title, items):
        print(f"{title} ({len(items)}):")
        line = " "
        for word in items:
            if len(line) + len(word) > 98:
                print(line)
                line = " "
            line += " " + word
        print(line)

    show("prefixes", [p["final"] if p["final"] == p["text"] else f"{p['text']}->{p['final']}" for p in plan.prefixes])
    show("suffixes", [s["final"] if s["final"] == s["text"] else f"{s['text']}->{s['final']}" for s in plan.suffixes])
    show("rogue names", [r["final"] for r in plan.rogues])
    show("cameo cats", [plan.final.get(k, v) for k, v in game.iconic.items()])
    show("banned", [plan.final.get(b["prefix"] + b["suffix"]) or b["name"] for b in game.banned])
    for w in plan.warnings:
        print(f"warning: {w}")
    print("\nnames --cats lists the cats in your save; names.json in a mod changes any of these (README, \"names.json\").")


def cmd_eyes(ctx, args):
    from .colors import hex_from_linear
    ctx.need_oodle()
    atlas = eyeatlas.EyeAtlas(ctx.game.read(eyeatlas.PATH))
    print("Eye palette slots (use these names in palette.json \"eyes\"):")
    for r, label in enumerate(atlas.labels):
        row = atlas.row(r)
        print(f"  row{r:<3d} {label:16s} pupil {hex_from_linear(row[0])}  mid {hex_from_linear(row[len(row) // 2])}  rim {hex_from_linear(row[-1])}")
    print("\nNote: some of the game's internal names don't match the colour (e.g. 'Yellow' is green).")


def cmd_controls(ctx, args):
    path = os.path.join(ctx.cfg.save_dir, save.SAV_NAME)
    if not os.path.isfile(path):
        sys.exit("No save found yet. Launch the game once first.")
    b = controls.read_bindings(save.SaveGame.load(path).json_text)
    if args.json:
        print(json.dumps(b, indent=2))
        return
    for dev in ("keyboard", "gamepad"):
        print(f"{dev}:")
        for action, key in b[dev].items():
            print(f"  {action:24s} {key}")


def cmd_palette(ctx, args):
    found = mods.discover(ctx.mods_root)
    presets = [m for m in found if mods.palette_only(m)]
    if not args.ids and not args.none:
        print("palette mods ([x] = on; several can be on, and the higher priority wins where they overlap):")
        for m in presets:
            print(f"  [{'x' if m.enabled else ' '}] {m.id:30s} {m.description}")
        print("\nrun `wcmods palette <name> [<name>...]` to use those, or `wcmods palette --none` for the game's colours")
        return
    if args.none and args.ids:
        sys.exit("error: give palette names or --none, not both")
    ids = [] if args.none else args.ids
    if args.no_install:
        on, _ = mods.choose_palettes(found, ids)
        print(f"palettes on: {', '.join(on) or 'none (the game colours)'}")
        print("not installed yet: run `wcmods install` with the game closed")
        return
    ctx.need_game()
    _, manifest = pipeline.apply_palettes(ctx.cfg, ctx.mods_root, ids, ctx.build_dir, ctx.backups,
                                          log=print, force=args.force)
    _print_build(manifest)
    print("done. Start the game from Steam to see them.")


def _remap_plan(ctx):
    from .sections.controls import ControlsSection, merge
    sec, datas = ControlsSection(), []
    for m in mods.discover(ctx.mods_root):   # priority order, so later mods win
        if m.enabled and sec.claims(m):
            data = sec.collect(m, None)
            if data:
                datas.append(data)
    merged = merge(datas)
    send, block, warnings = keymap.plan(merged)
    menu_send, menu_warnings = keymap.menu_plan(merged)
    return send, block, menu_send, warnings + menu_warnings


def _run_remapper(ctx, args, launching=False):
    """launching: `play` has just asked Steam to start the game, so any play state on disk is old."""
    send, block, menu_send, warnings = _remap_plan(ctx)
    for w in warnings:
        print(f"  warning: {w}")
    if not send and not block and not menu_send:
        print("No keyboard or mouse remaps in the enabled mods' controls.json; nothing to do.")
        return
    state_file = playstate.state_path(ctx.cfg) if ctx.cfg.game_dir else None
    script = os.path.join(os.path.dirname(state_file), "Scripts", "main.lua") if state_file else None
    if not (script and os.path.isfile(script)):
        state_file = None
        print("  note: the play-state script isn't installed yet, so remaps apply whenever the game is in front,\n"
              "        menus and the name screen too, and menu remaps can't apply. Install mods once (game closed).")
    elif launching and os.path.isfile(state_file):
        try:
            os.remove(state_file)   # last session's state; the script writes a fresh one as the game starts
        except OSError:
            pass
    when = "whenever the game is in front" if args.in_menus or not state_file else "while you play (game in front, not in a menu)"
    if send or block:
        print(f"remaps {when}:")
    for src, dst in sorted(send.items()):
        print(f"  {src:18s} -> {dst}")
    for key in sorted(block):
        print(f"  {key:18s} -> nothing (its action moved)")
    if menu_send:
        print("in menus:")
        for src, dst in sorted(menu_send.items()):
            print(f"  {src:18s} -> {dst}")
    from .remapper import Remapper
    state = {"seen": game_running(), "checked": time.monotonic(), "started": time.monotonic(), "nagged": False}

    def should_stop():
        # The game is checked every few seconds: listing processes is slow.
        if time.monotonic() - state["checked"] < 3:
            return False
        state["checked"] = time.monotonic()
        running = game_running()
        if running:
            state["seen"] = True
        elif state["seen"]:
            print("the game has closed; remapper stopped")
            return True
        elif not state["nagged"] and time.monotonic() - state["started"] > 180:
            state["nagged"] = True   # Steam may be updating; keep waiting
            print("still waiting for the game (3 minutes so far); Ctrl+C stops the remapper")
        return False

    print("waiting for the game..." if not state["seen"] else "the game is running.", "Ctrl+C stops the remapper.")
    try:
        Remapper(send, block, (EXE_NAME,), dry_run=args.dry_run, in_menus=args.in_menus,
                 debug=args.debug, state_file=state_file, menu_send=menu_send).run(should_stop)
    except KeyboardInterrupt:
        print("remapper stopped")
    except OSError as e:
        sys.exit(f"error: couldn't hook the keyboard: {e}")


def cmd_remap(ctx, args):
    _run_remapper(ctx, args)


def cmd_play(ctx, args):
    launching = not game_running()
    if launching:
        print("starting the game through Steam...")
        os.startfile(f"steam://rungameid/{STEAM_APP_ID}")
    _run_remapper(ctx, args, launching=launching)


def _print_build(manifest):
    for sid, rep in manifest["sections"].items():
        if rep["mods"] or rep["errors"]:
            label = rep["status"].upper() if rep["status"] != "ok" else "ok"
            print(f"  [{label}] {rep['title']}: {', '.join(rep['mods']) or 'no mods'}")
            for e in rep["errors"]:
                print(f"         {e}")
    for w in manifest["warnings"]:
        print(f"  warning: {w}")
    for name in manifest["outputs"]:
        print(f"  built {name}")
    for name in manifest["ue4ss_mods"]:
        print(f"  built UE4SS mod {name}")
    if manifest["save_ops"]:
        print(f"  {len(manifest['save_ops'])} save edit group(s) will be applied on install")


def cmd_build(ctx, args):
    ctx.need_game()
    found = mods.discover(ctx.mods_root)
    enabled = [m.id for m in found if m.enabled]
    print(f"building {len(enabled)} enabled mod(s): {', '.join(enabled) or 'none'}")
    manifest = pipeline.build(ctx.cfg, found, ctx.build_dir)
    _print_build(manifest)
    ctx.cfg.save()
    return manifest


def cmd_install(ctx, args):
    cmd_build(ctx, args)
    print("installing:")
    pipeline.install(ctx.cfg, ctx.build_dir, ctx.backups, force=args.force)
    print("done. Start the game from Steam to try it.")


def cmd_uninstall(ctx, args):
    ctx.need_game()
    removed = pipeline.uninstall(ctx.cfg)
    print("nothing installed" if not removed else "uninstalled.")
    print("Save edits live in your save; use `wcmods restore` to roll it back.")


def cmd_backup(ctx, args):
    where, files = save.backup(ctx.cfg.save_dir, ctx.backups, "manual")
    print(f"backed up {len(files)} file(s) -> {where}")


def cmd_restore(ctx, args):
    if game_running():
        sys.exit("Close the game first.")
    names = save.list_backups(ctx.backups)
    if not names:
        sys.exit("no backups yet")
    if not args.name:
        print("backups:")
        for n in names:
            print(f"  {n}")
        print("\nrun `wcmods restore <name>` (or `latest`) to restore one")
        return
    name = names[-1] if args.name == "latest" else args.name
    save.backup(ctx.cfg.save_dir, ctx.backups, "before-restore")
    restored = save.restore(ctx.backups, name, ctx.cfg.save_dir)
    print(f"restored {', '.join(restored)} from {name}")


def cmd_tables(ctx, args):
    """Read the colour tables the UE4SS script logged and save them to colour_tables.json."""
    ctx.need_game()
    rep = ue4ss.read_reports(ctx.cfg.win64_dir)
    if rep is None:
        sys.exit("No UE4SS.log yet. Install UE4SS and the mods, then start the game once.")
    for msg in rep["notes"][-12:]:
        print(f"  log: {msg}")
    if not rep["tables"]:
        sys.exit("The log has no colour tables yet (the script hasn't found the colour owner). See the log lines above.")
    with open(os.path.join(ctx.root, "colour_tables.json"), "w", encoding="utf-8") as f:
        json.dump(rep["tables"], f, indent=2)
    for prop, hexes in rep["tables"].items():
        print(f"{prop} ({len(hexes)} slots):")
        for i, h in enumerate(hexes):
            print(f"  {i:3d}  {h}")
    print("saved colour_tables.json")


def cmd_selftest(ctx, args):
    from . import selftest
    ctx.need_game()
    print("self-test (reads the game and your save, writes only to a temp folder):")
    ok = selftest.run(ctx.cfg, ctx.game.oodle)
    print("all checks passed" if ok else "SOME CHECKS FAILED - don't install until this is fixed")
    if not ok:
        sys.exit(1)


def cmd_ingame(ctx, args, option):
    from . import ingame
    if args.state is not None:
        opts = ingame.set_options(ctx.cfg, **{option: args.state == "on"})
    else:
        opts = ingame.options(ctx.cfg)
    if option == "cheats":
        from .menu import KEY_NAMES
        key = KEY_NAMES.get(opts["menu_key"], opts["menu_key"])
        print(f"cheats start {'on' if opts['cheats'] else 'off'} in the mod menu ({key} in game, Cheats page)")
        if args.state is not None:
            print("install again to apply it (python wcmods.py install)")
    else:
        if not opts["console_available"]:
            print("UE4SS's console unlocker (ConsoleEnablerMod) isn't installed; this applies once UE4SS is")
        print(f"the game's console is {'on: ~ or F10 opens it' if opts['console'] else 'off'}"
              + (" (from the next time the game starts)" if args.state is not None else ""))


def _bridge(ctx):
    from .bridge import Bridge
    return Bridge(ctx.cfg)


def _run_lua(ctx, code, timeout):
    from .bridge import BridgeError
    try:
        return _bridge(ctx).run(code, timeout=timeout)
    except BridgeError as e:
        sys.exit(f"error: {e}")


def _print_reply(reply, as_json):
    if as_json:
        print(json.dumps(reply, indent=2, ensure_ascii=False))
        return
    if reply.get("output"):
        print(reply["output"])
    if reply.get("ok"):
        result = reply.get("result") or []
        if result:
            print(json.dumps(result if len(result) > 1 else result[0], indent=2, ensure_ascii=False))
    else:
        sys.exit(f"error: {reply.get('error')}")


def cmd_lua(ctx, args):
    if args.file:
        with open(args.file, encoding="utf-8-sig") as f:
            code = f.read()
    elif args.code in (None, "-"):
        code = sys.stdin.read()
    else:
        code = args.code
    _print_reply(_run_lua(ctx, code, args.timeout), args.json)


def cmd_game(ctx, args):
    if args.what == "build":
        return _game_build(ctx, args)
    if args.what == "signatures":
        return _game_signatures(ctx, args)
    if args.what == "types":
        # UE4SS writes Lua type annotations for every class it knows into Mods/shared/types.
        reply = _run_lua(ctx, "GenerateLuaTypes() return true", max(args.timeout, 120))
        _print_reply(reply, False)
        mods_dir = ctx.cfg.ue4ss_mods_dir
        print(f"written to {os.path.join(mods_dir, 'shared', 'types') if mods_dir else 'ue4ss/Mods/shared/types'}; "
              "point your editor's Lua language server at that folder")
        return
    st = _bridge(ctx).status()
    if not st:
        print("the bridge has never run: install with \"allow_code_mods\": true, then start the game")
        return
    if not st["alive"]:
        print(f"the game isn't running (the bridge last reported {st['age']:.0f} s ago)")
        return
    print(f"the game is running: {st.get('world') or 'loading'}, "
          + ("your cat is in the world" if st.get("player") else "no cat yet (menus or loading)"))




def _game_build(ctx, args):
    """Which build is installed, what wcmods found moved on it, and the mods made for older ones."""
    from . import gamebuild
    now = gamebuild.current(ctx.cfg)
    if not now["build"]:
        print("couldn't tell which build of the game is installed (no Steam manifest)")
    elif now["verified"]:
        print(f"build {now['build']}: wcmods was checked on this one ({now['label']})")
    else:
        print(f"build {now['build']}: not the one wcmods was checked on ({gamebuild.VERIFIED_BUILD})")
    fit = gamebuild.layout(ctx.cfg, refresh=args.refresh)
    if fit["status"] == "adapted":
        print("every value wcmods reads was found again" +
              (": moved " + ", ".join(gamebuild.describe(k) for k in fit["moved"]) if fit["moved"] else ", none moved"))
    elif fit["status"] == "partial":
        print("couldn't find these again, so what uses them stays off until wcmods is updated: " +
              ", ".join(gamebuild.describe(k) for k in fit["lost"]))
        if fit["moved"]:
            print("moved, and followed: " + ", ".join(gamebuild.describe(k) for k in fit["moved"]))
    found = mods.discover(ctx.mods_root)
    for mod_id, o in gamebuild.outdated(ctx.cfg, found, now["build"]).items():
        print(f"  {mod_id}: made for build {', '.join(map(str, o['made_for']))}; " +
              ("used anyway" if o["allowed"] else "left out (`wcmods allow-outdated " + mod_id + "` uses it anyway)"))


def _game_signatures(ctx, args):
    """For maintainers: make wcmods/signatures.json on a verified build, or check another exe against it."""
    from . import pe, signatures
    exe = args.exe or pe.game_exe(ctx.cfg)
    if not exe:
        sys.exit("no game exe found; pass --exe")
    if args.action == "make":
        from . import gamebuild
        result = signatures.make(exe)
        # The installed game's build, unless it's another exe (whose build only --build can say).
        installed = pe.game_exe(ctx.cfg)
        same = installed and os.path.normcase(os.path.abspath(exe)) == os.path.normcase(os.path.abspath(installed))
        result["made_on"]["build"] = args.build if args.build else gamebuild.steam_build(ctx.cfg) if same else None
        signatures.save(result)
        print(f"wrote {signatures.DATA}")
    elif args.action in (None, "check"):
        if args.json:   # the JSON alone on stdout; what it looked at goes to stderr
            print(json.dumps(signatures.check(exe, log=lambda m: print(m, file=sys.stderr)), indent=1))
        else:
            res = signatures.check(exe)
            print("nothing moved" if res["same"] else "something moved or couldn't be found (above)")
    else:
        sys.exit("game signatures make | check")


def cmd_allow_outdated(ctx, args):
    from . import gamebuild
    build = gamebuild.current(ctx.cfg)["build"]
    if build is None:
        sys.exit("couldn't tell which build of the game is installed")
    found = {m.id: m for m in mods.discover(ctx.mods_root)}
    if args.mod not in found:
        sys.exit(f"no mod named {args.mod}")
    gamebuild.allow(ctx.cfg, args.mod, build, on=not args.off)
    if args.off:
        print(f"{args.mod} is left out again on build {build} until it's updated")
    else:
        print(f"{args.mod} will be used on build {build} even though it was made for an older version of the game.")
        print("It may not work, or may behave unpredictably. Install again to apply.")


def cmd_inspect(ctx, args):
    from .bridge import inspect_code
    reply = _run_lua(ctx, inspect_code(args.expr, args.all), args.timeout)
    if not reply.get("ok"):
        sys.exit(f"error: {reply.get('error')}")
    info = (reply.get("result") or [{}])[0]
    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return
    if info.get("error"):
        sys.exit(f"error: {info['error']}")
    print(info["name"])
    print("  is a " + " < ".join(info["parents"]))
    print("properties:")
    for p in info["props"]:
        print(f"  {p['owner']}.{p['name']} ({p['type'].replace('Property', '')}) = {p['value'][:100]}")
    print("functions:")
    for f in info["funcs"]:
        ret = f" -> {f['returns'].replace('Property', '')}" if f.get("returns") else ""
        print(f"  {f['owner']}.{f['name']}({', '.join(f['params'])}){ret}")


FIND_LUA = """
local out = {}
for i, o in ipairs(Game.findAll(%s)) do
    if i > %d then break end
    local loc = nil
    if Game.isA(o, "Actor") then
        local ok, l = pcall(function() return o:K2_GetActorLocation() end)
        if ok then loc = string.format("%%.0f, %%.0f, %%.0f", l.X, l.Y, l.Z) end
    end
    out[#out + 1] = { name = Game.fullName(o), at = loc }
end
return out
"""


def cmd_find(ctx, args):
    from .sdk import lua_value
    reply = _run_lua(ctx, FIND_LUA % (lua_value(args.cls), args.limit), args.timeout)
    if not reply.get("ok"):
        sys.exit(f"error: {reply.get('error')}")
    found = (reply.get("result") or [[]])[0] or []
    if args.json:
        print(json.dumps(found, indent=2, ensure_ascii=False))
        return
    for o in found:
        print(o["name"] + (f"   at {o['at']}" if o.get("at") else ""))
    print(f"{len(found)} found" + (" (the first ones)" if len(found) >= args.limit else ""))


def cmd_cpp(ctx, args):
    from . import cppmods
    root = ctx.cfg.root
    if args.action == "setup":
        commit = cppmods.setup(root, ctx.cfg, commit=args.commit)
        print(f"UE4SS's source is at {commit[:8]} in {cppmods.source_dir(root)}")
        missing = cppmods.problems(cppmods.toolchain())
        if missing:
            print("to build C++ mods you also need:\n- " + "\n- ".join(missing))
        else:
            print("ready: `python wcmods.py cpp build` builds your mods' cpp/ folders")
        return
    if args.action == "build":
        which = cppmods.cpp_mods(mods.discover(ctx.mods_root), args.mods, root=root)
        if args.watch:
            cppmods.watch(root, ctx.cfg, which)
            return
        built = cppmods.build(root, ctx.cfg, which)
        if args.keep:
            for m in which:
                cppmods.keep(m)
        print(f"built {len(built)} C++ mod(s); install (or press Play in Clan Mod Studio) to put them in the game")
        return
    if args.action == "ide":
        cppmods.ide(root, ctx.cfg, cppmods.cpp_mods(mods.discover(ctx.mods_root), args.mods, root=root), open_it=args.open)
        return
    if args.action == "crash":
        from . import crashes
        path = crashes.latest()
        if not path:
            print("the game hasn't left a crash (nothing under " + crashes.crashes_dir() + ")")
            return
        found = mods.discover(ctx.mods_root) + [mods.Mod(os.path.abspath(os.path.join(root, m))) for m in args.mods
                                                 if os.path.isfile(os.path.join(root, m, "mod.json"))]
        print(crashes.readout(path, found, cppmods.SDK_DIR))
        return
    st = cppmods.status(root, ctx.cfg)
    game = st["game"]
    print(f"game's UE4SS: {(game['commit'] or 'unknown until the game runs with it') if game else 'not installed'}")
    print(f"UE4SS source: {st['source'][:8] if st['source'] else 'not here (python wcmods.py cpp setup)'}"
          + ("" if st["matches"] is not False else "  <- not the game's; run `python wcmods.py cpp setup`"))
    for tool in ("vs", "cmake", "ninja", "cargo", "git"):
        print(f"  {tool:6} {st['tools'][tool] or 'missing'}")
    for p in st["problems"]:
        print(f"needs: {p}")
    have = [m.id for m in cppmods.cpp_mods(mods.discover(ctx.mods_root))]
    print(f"enabled mods with C++ source: {', '.join(have) or 'none'}")


def cmd_studio(ctx, args):
    from . import studio
    # No ctx.need_game(): without the game, the studio opens on its "Get set up" steps, which ask where it is.
    if args.add and not os.path.exists(args.add):
        sys.exit(f"there's no {args.add}")
    studio.serve(ctx, port=args.port, open_browser=not args.no_browser, add=args.add)


def main(root, argv=None):
    ap = argparse.ArgumentParser(prog="wcmods", description="Warrior Cats: Clans of the Forest mod tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="show game, save, tool and mod status").set_defaults(fn=cmd_status)
    p = sub.add_parser("studio", help="open the mod manager in your browser")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--add", metavar="ZIP_OR_FOLDER", help="open with this mod ready to add (what dropping it on Clan Mod Studio does)")
    p.set_defaults(fn=cmd_studio)
    for name, value in (("enable", True), ("disable", False)):
        p = sub.add_parser(name, help=f"{name} mods by folder name" + (" (and the mods they require)" if value else ""))
        p.add_argument("mods", nargs="+")
        if not value:
            p.add_argument("--with-dependents", action="store_true", help="also turn off the mods that need it")
        p.set_defaults(fn=lambda c, a, v=value: cmd_enable(c, a, v))
    p = sub.add_parser("add", help="add a downloaded mod: a .zip (one or several mods) or a mod's folder")
    p.add_argument("path")
    p.add_argument("--off", action="store_true", help="add it switched off")
    p.add_argument("--only", metavar="MOD,MOD", help="of several mods in it, add just these (folder names)")
    p.add_argument("--on", action="store_true", help="of several mods, switch them all on (they go in off otherwise)")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("remove", help="take a mod out of mods/ (kept in backups/mods)")
    p.add_argument("mod")
    p.add_argument("--with-dependents", action="store_true", help="also turn off the mods that need it")
    p.set_defaults(fn=cmd_remove)
    p = sub.add_parser("pack", help="pack a mod as a .zip to share")
    p.add_argument("mod")
    p.add_argument("out", nargs="?")
    p.set_defaults(fn=cmd_pack)
    p = sub.add_parser("new", help="create a mod from a template")
    p.add_argument("id")
    p.add_argument("--kind", choices=("palette", "controls", "files", "data", "items", "save", "names", "script", "cpp"), default="palette")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("files", help="list game files matching a pattern, e.g. '*NPC/*.csv'")
    p.add_argument("pattern")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(fn=cmd_files)
    p = sub.add_parser("texture", help="save one of the game's textures as a PNG to paint over: an accessory's look "
                                       "(Neck.DogCollar.1), an item's icon (SmallHealingHerb) or /Game/...")
    p.add_argument("what")
    p.add_argument("--out", help="where to write the PNG (default vanilla/textures/<name>.png)")
    p.set_defaults(fn=cmd_texture)
    p = sub.add_parser("extract", help="copy game files matching a pattern into vanilla/ to start a files mod")
    p.add_argument("pattern")
    p.add_argument("--out", default="vanilla")
    p.set_defaults(fn=cmd_extract)
    sub.add_parser("eyes", help="list eye palette slots and their current colours").set_defaults(fn=cmd_eyes)
    p = sub.add_parser("names", help="list the game's name parts, rogue names and ban list (with your mods' changes)")
    p.add_argument("--cats", action="store_true", help="list the cats in your save and their names instead")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_names)
    p = sub.add_parser("palette", help="list the palette mods, or switch to some of them and install")
    p.add_argument("ids", nargs="*", help="palette mods to use; the other palette-only mods are turned off")
    p.add_argument("--none", action="store_true", help="turn every palette-only mod off (the game's colours)")
    p.add_argument("--no-install", action="store_true", help="only switch the mods; install later")
    p.add_argument("--force", action="store_true", help="install even if some other mods failed to build")
    p.set_defaults(fn=cmd_palette)
    p = sub.add_parser("controls", help="show the key/button bindings stored in your save")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_controls)
    for name, fn, text in (("play", cmd_play, "start the game and remap keys (controls.json) until it closes"),
                           ("remap", cmd_remap, "remap keys (controls.json) while the game runs; start the game yourself")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--dry-run", action="store_true", help="only report which remaps would happen")
        p.add_argument("--in-menus", action="store_true", help="remap in menus too (off: menus and name entry keep your keys)")
        p.add_argument("--debug", action="store_true",
                       help="log the window in front, the game's play state, and presses of the remapped keys")
        p.set_defaults(fn=fn)
    sub.add_parser("tables", help="show the game's coat/pattern/marking/eye-button colour tables (needs UE4SS)").set_defaults(fn=cmd_tables)
    sub.add_parser("selftest", help="check every file format against the installed game").set_defaults(fn=cmd_selftest)
    sub.add_parser("build", help="build enabled mods into build/").set_defaults(fn=cmd_build)
    p = sub.add_parser("install", help="build and install enabled mods")
    p.add_argument("--force", action="store_true", help="install even if some mods failed to build")
    p.set_defaults(fn=cmd_install)
    sub.add_parser("uninstall", help="remove installed mod files from the game").set_defaults(fn=cmd_uninstall)
    sub.add_parser("backup", help="back up your save files").set_defaults(fn=cmd_backup)
    p = sub.add_parser("restore", help="list or restore save backups")
    p.add_argument("name", nargs="?")
    p.set_defaults(fn=cmd_restore)
    p = sub.add_parser("lua", help="run Lua in the running game (needs allow_code_mods and an install)")
    p.add_argument("code", nargs="?", help="Lua to run; an expression shows its value. '-' or nothing reads stdin")
    p.add_argument("-f", "--file", help="run a .lua file instead")
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--json", action="store_true", help="print the bridge's whole reply")
    p.set_defaults(fn=cmd_lua)
    p = sub.add_parser("game", help="whether the game is running with the bridge; 'game build' says which build is "
                                    "installed and what changed; 'game types' writes Lua type files")
    p.add_argument("what", nargs="?", choices=("status", "types", "build", "signatures"), default="status")
    p.add_argument("action", nargs="?", help="for signatures: make | check")
    p.add_argument("--exe", help="for signatures: an exe other than the installed game's")
    p.add_argument("--build", type=int, help="for signatures make: the build of the exe given with --exe")
    p.add_argument("--refresh", action="store_true", help="for build: look for what moved again")
    p.add_argument("--json", action="store_true")
    p.add_argument("--timeout", type=float, default=15)
    p.set_defaults(fn=cmd_game)
    p = sub.add_parser("allow-outdated", help="use a mod made for an older version of the game anyway, on this build")
    p.add_argument("mod")
    p.add_argument("--off", action="store_true", help="leave it out again")
    p.set_defaults(fn=cmd_allow_outdated)
    p = sub.add_parser("inspect", help="show an object's properties and functions, e.g. inspect \"Game.player()\"")
    p.add_argument("expr", help="a Lua expression for the object")
    p.add_argument("--all", action="store_true", help="include the engine's Actor/Object members too")
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_inspect)
    p = sub.add_parser("find", help="list the game's objects of a class, e.g. find WrcRoamingEnemy")
    p.add_argument("cls")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_find)
    p = sub.add_parser("cpp", help="C++ mods: 'cpp setup' gets UE4SS's source at the game's UE4SS, 'cpp build' builds "
                                   "mods' cpp/ into dlls/main.dll, 'cpp ide' makes a Visual Studio solution, 'cpp crash' "
                                   "says which mod the game's last crash was in, 'cpp' alone says what's ready")
    p.add_argument("action", nargs="?", choices=("status", "setup", "build", "ide", "crash"), default="status")
    p.add_argument("mods", nargs="*", help="for build, ide and crash: the mods, by id or by a mod folder's path "
                                           "(all enabled mods with cpp/ without)")
    p.add_argument("--commit", help="for setup: UE4SS's commit, when the game hasn't run with UE4SS yet")
    p.add_argument("--watch", action="store_true", help="for build: build again whenever a file in cpp/ changes")
    p.add_argument("--keep", action="store_true", help="for build: also keep the DLL as dlls/<UE4SS commit>/, for a "
                                                        "mod that carries builds for several UE4SS versions")
    p.add_argument("--open", action="store_true", help="for ide: open the solution in Visual Studio")
    p.set_defaults(fn=cmd_cpp)
    from .agent import cli as agent_cli
    agent_cli.register(sub)
    for option, text in (("cheats", "show, or set, whether cheats start on in the mod menu (needs install)"),
                         ("console", "show, or switch on or off, the game's console (~ or F10; needs UE4SS)")):
        p = sub.add_parser(option, help=text)
        p.add_argument("state", nargs="?", choices=("on", "off"))
        p.set_defaults(fn=lambda c, a, o=option: cmd_ingame(c, a, o))
    args = ap.parse_args(argv)
    try:
        args.fn(Ctx(root), args)
    except (RuntimeError, ValueError, LookupError, FileNotFoundError, zipfile.BadZipFile) as e:
        sys.exit(f"error: {e}")
