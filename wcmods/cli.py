"""Command line: python wcmods.py <command>."""
import argparse
import json
import os
import shutil
import sys
import time

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
    print("\nmods:")
    for m in mods.discover(ctx.mods_root):
        print(f"  [{'x' if m.enabled else ' '}] {m.id:28s} {', '.join(m.kinds()) or '(empty)':24s} {m.description}")
    cfg.save()


def cmd_enable(ctx, args, value=True):
    found = {m.id: m for m in mods.discover(ctx.mods_root)}
    for mod_id in args.mods:
        if mod_id not in found:
            sys.exit(f"no mod named {mod_id}")
        found[mod_id].set_enabled(value)
        print(f"{'enabled' if value else 'disabled'} {mod_id}")


def cmd_new(ctx, args):
    mod = mods.create(ctx.mods_root, args.id)
    template = os.path.join(ctx.mods_root, "_templates", args.kind)
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
        for c in names.cat_list(plan, cats, ops):
            now = c["name"] + (f" -> {c['with_mods']}" if c["with_mods"] != c["name"] else "")
            roles = f"  (story role: {', '.join(c['roles'])})" if c["roles"] else ""
            print(f"  {now:30s} {c['role']:16s} {c['target']}{roles}")
        print('\nIn names.json, "cats" takes a cat by the name shown here, "player", or the last column.')
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
    show("banned", [b["name"] for b in game.banned])
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


def cmd_studio(ctx, args):
    from . import studio
    ctx.need_game()
    studio.serve(ctx, port=args.port, open_browser=not args.no_browser)


def main(root, argv=None):
    ap = argparse.ArgumentParser(prog="wcmods", description="Warrior Cats: Clans of the Forest mod tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="show game, save, tool and mod status").set_defaults(fn=cmd_status)
    p = sub.add_parser("studio", help="open the mod manager in your browser")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(fn=cmd_studio)
    for name, value in (("enable", True), ("disable", False)):
        p = sub.add_parser(name, help=f"{name} mods by folder name")
        p.add_argument("mods", nargs="+")
        p.set_defaults(fn=lambda c, a, v=value: cmd_enable(c, a, v))
    p = sub.add_parser("new", help="create a mod from a template")
    p.add_argument("id")
    p.add_argument("--kind", choices=("palette", "controls", "files", "data", "save", "names"), default="palette")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("files", help="list game files matching a pattern, e.g. '*NPC/*.csv'")
    p.add_argument("pattern")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(fn=cmd_files)
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
    args = ap.parse_args(argv)
    try:
        args.fn(Ctx(root), args)
    except (RuntimeError, ValueError, KeyError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")
