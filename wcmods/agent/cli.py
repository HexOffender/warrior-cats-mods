"""`python wcmods.py agent ...`: the agent controller from the command line (docs/agent.md)."""
import json
import os
import runpy
import sys

from . import runner
from .controller import Agent, AgentError


def _agent(ctx):
    return Agent(ctx.root)


def _print(value, as_json=False):
    if as_json or not isinstance(value, str):
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(value)


def cmd_status(ctx, args):
    st = _agent(ctx).status()
    if args.json:
        return _print(st, True)
    if not st["running"]:
        print("the game isn't running" + (" (a crash reporter is open)" if st["crash_reporter"] else ""))
        return
    w = st["window"]
    print(f"the game is running (pid {st['pid']}), window {w[0]}x{w[1]}" if w else f"the game is running (pid {st['pid']})",
          "in front" if st["foreground"] else "behind other windows", "(minimised)" if st["minimized"] else "")
    if not st["bridge"]:
        print("the bridge isn't answering: loading, or not installed (agent install)")
        return
    print(f"level {st['world'] or '?'}; " + ("your cat is in the forest" if st["in_world"] else
                                             "your cat is in the world" if st["player"] else "no cat yet (menus or loading)"))
    print(f"mod menu open on {st['page']!r}" if st["menu"] else "mod menu closed")
    if st["crash_reporter"]:
        print("a crash reporter is open (agent crash --close)")


def cmd_launch(ctx, args):
    st = _agent(ctx).launch(world=args.world, cat=args.cat, timeout=args.timeout)
    print(f"running; {st['world']}" + (", in the forest" if st["in_world"] else ""))


def cmd_enter(ctx, args):
    _agent(ctx).enter(cat=args.cat, timeout=args.timeout)


def cmd_quit(ctx, args):
    _agent(ctx).quit(force=args.force)
    print("the game closed")


def cmd_install(ctx, args):
    a = _agent(ctx)
    if args.normal:
        manifest = a.install_normal(force=args.force)
        print("installed as wcmods.json says (like `wcmods install`)")
    else:
        manifest = a.install(extra=args.extra or (), code_mods=not args.no_code_mods, force=args.force)
        print("installed a test build" + (" with code mods and the bridge" if not args.no_code_mods else "")
              + "; wcmods.json is unchanged")
    print("  UE4SS mods: " + ", ".join(manifest["ue4ss_mods"]))
    for w in manifest["warnings"]:
        print(f"  warning: {w}")


def cmd_lua(ctx, args):
    a = _agent(ctx)
    code = open(args.file, encoding="utf-8-sig").read() if args.file else args.code
    value = a.lua(code, timeout=args.timeout)
    if a.output:
        print(a.output)
    if value is not None:
        _print(value, True)


def cmd_check(ctx, args):
    a, bad = _agent(ctx), 0
    for path in args.files:
        err = a.compile(open(path, encoding="utf-8-sig").read(), os.path.basename(path))
        print(f"{path}: {'ok' if err is None else err}")
        bad += err is not None
    if bad:
        sys.exit(1)


def cmd_wait(ctx, args):
    _print(_agent(ctx).wait_lua(args.expr, timeout=args.timeout))


def cmd_shot(ctx, args):
    a = _agent(ctx)
    region = tuple(int(v) for v in args.region.split(",")) if args.region else None
    print(a.shot(args.name, scale=args.scale, menu=args.menu, region=region, path=args.out))


def cmd_key(ctx, args):
    a = _agent(ctx)
    for _ in range(args.repeat):
        if len(args.keys) > 1:
            a.keys(*args.keys, hold=args.hold)
        else:
            a.key(args.keys[0], hold=args.hold)


def cmd_hotkey(ctx, args):
    _agent(ctx).hotkey(args.key, modifiers=args.mod or (), focus=args.focus)


def cmd_move(ctx, args):
    a = _agent(ctx)
    if args.turn:
        a.turn(args.turn)
    if args.seconds:
        print(f"moved {a.move(args.forward, args.right, args.seconds):.0f} cm")


def cmd_cat(ctx, args):
    a = _agent(ctx)
    if args.teleport:
        a.teleport(*[float(v) for v in args.teleport.split(",")])
    _print(a.cat(), True)


def cmd_screens(ctx, args):
    a = _agent(ctx)
    if args.press:
        a.press_ui(args.press[0], args.press[1])
    for s in a.screens():
        print(s)


def cmd_menu(ctx, args):
    a = _agent(ctx)
    m, what = a.menu, args.what
    if what == "pages":
        for p in m.pages():
            print(f"{p['group']:<8} {p['title']}" + (f"  (id {p['id']})" if p["id"] != p["title"] else ""))
        return
    if what == "open":
        page = m.open(args.args[0] if args.args else None)
        print(f"open on {page.title!r}")
        return
    if what == "close":
        return m.close()
    if what == "shot":
        if args.args:
            m.open(args.args[0])
        print(m.shot(args.args[1] if len(args.args) > 1 else None))
        return
    if what == "read":
        page = m.open(args.args[0]) if args.args else m.read()
        if args.json:
            return _print({"id": page.id, "title": page.title, "rows": [vars(r) for r in page.rows]}, True)
        print(f"== {page.title} ==")
        print(page.text())
        return
    if what in ("press", "set", "section"):
        if not args.args or (what == "set" and len(args.args) < 2):
            sys.exit(f"usage: agent menu {what} LABEL" + (" VALUE" if what == "set" else ""))
        label = args.args[0]
        if what == "press":
            kind, used = m.press(label)
        elif what == "section":
            kind, used = m.section(label, open=not (len(args.args) > 1 and args.args[1] in ("close", "off")))
        else:
            kind, used = m.set(label, args.args[1])
        print(f"used {kind} {used!r}")
        return
    if what == "scroll":
        m.scroll(args.args[0] if args.args else "top")


def cmd_log(ctx, args):
    a = _agent(ctx)
    lines = a.errors_since(0) if args.errors else a.log_since(0)
    if args.grep:
        lines = [line for line in lines if args.grep.lower() in line.lower()]
    for line in lines[-args.lines:]:
        print(line)


def cmd_crash(ctx, args):
    a = _agent(ctx)
    if args.close:
        print(f"closed {a.close_crash_reporter()} crash reporter(s); nothing was sent")
    else:
        print("a crash reporter is open" if a.crashed() else "no crash reporter is open")


def cmd_test(ctx, args):
    paths = args.paths or [os.path.join(ctx.root, "tests", "game")]
    if args.list:
        for t in runner.discover(paths, args.k):
            print(f"{t.name}  (needs {t.needs})" + (f": {t.doc.splitlines()[0]}" if t.doc else ""))
        return
    report = runner.run(ctx.root, paths, pattern=args.k, launch=args.launch, stop_on_fail=args.stop,
                        backup=not args.no_backup)
    print(runner.summary(report))
    print("report: " + os.path.join(report["folder"], "report.md") + " (and report.html)")
    if not runner.ok(report):
        sys.exit(1)


def cmd_run(ctx, args):
    """Run a Python script with `agent` ready in it (and AgentError, skip)."""
    agent = _agent(ctx)
    sys.argv = [args.script] + list(args.args)
    runpy.run_path(args.script, init_globals={"agent": agent, "AgentError": AgentError, "skip": runner.skip},
                   run_name="__main__")


def register(sub):
    """Add `agent` and its commands to the main command line's subparsers."""
    p = sub.add_parser("agent", help="drive the running game for tests: launch, menus, keys, pictures (docs/agent.md)")
    a = p.add_subparsers(dest="agent_cmd", required=True)

    def cmd(name, fn, help):
        q = a.add_parser(name, help=help)
        q.set_defaults(fn=fn)
        return q

    q = cmd("status", cmd_status, "is the game running, where is your cat, what does the menu show")
    q.add_argument("--json", action="store_true")
    q = cmd("launch", cmd_launch, "start the game through Steam and wait for the bridge")
    q.add_argument("--world", action="store_true", help="and play into the forest")
    q.add_argument("--cat", type=int, default=1, help="the save slot to play (1-3)")
    q.add_argument("--timeout", type=float, default=240)
    q = cmd("enter", cmd_enter, "from the splash or main menu, play into the forest")
    q.add_argument("--cat", type=int, default=1)
    q.add_argument("--timeout", type=float, default=240)
    q = cmd("quit", cmd_quit, "close the game the way its menu does")
    q.add_argument("--force", action="store_true", help="end it if it doesn't close")
    q = cmd("install", cmd_install, "install a test build: your mods, code mods allowed, the bridge")
    q.add_argument("--with", dest="extra", action="append", metavar="MOD_FOLDER",
                   help="also put in this mod folder, on (e.g. examples/game-tweaks); repeatable")
    q.add_argument("--no-code-mods", action="store_true", help="as wcmods.json says about code mods")
    q.add_argument("--normal", action="store_true", help="install exactly as `wcmods install` does (to finish testing)")
    q.add_argument("--force", action="store_true", help="install even if a section failed to build")
    q = cmd("lua", cmd_lua, "run Lua in the game and print what it returns")
    q.add_argument("code", nargs="?")
    q.add_argument("-f", "--file")
    q.add_argument("--timeout", type=float, default=15)
    q = cmd("check", cmd_check, "check Lua files compile, with the game's own Lua (nothing runs)")
    q.add_argument("files", nargs="+")
    q = cmd("wait", cmd_wait, "wait until a Lua expression is true, e.g. \"Game.cat() ~= nil\"")
    q.add_argument("expr")
    q.add_argument("--timeout", type=float, default=60)
    q = cmd("shot", cmd_shot, "save a picture of the game's window (prints its path)")
    q.add_argument("name", nargs="?")
    q.add_argument("--scale", type=float, default=1.0, help="e.g. 0.5 for half size")
    q.add_argument("--menu", action="store_true", help="just the mod menu's window")
    q.add_argument("--region", help="x,y,w,h in the window's pixels")
    q.add_argument("--out", help="where to save it (default agent-output/shots)")
    q = cmd("key", cmd_key, "press keys for the game's own controls (posted to its window; no focus needed)")
    q.add_argument("keys", nargs="+", help="Unreal key names: W, SpaceBar, E, Enter, LeftShift...; several are held together")
    q.add_argument("--hold", type=float, default=0.08, help="seconds")
    q.add_argument("--repeat", type=int, default=1)
    q = cmd("hotkey", cmd_hotkey, "press a key for UE4SS's key binds (Insert, a script's key): real input, game in front")
    q.add_argument("key")
    q.add_argument("--mod", action="append", help="a modifier held with it (LeftControl, LeftShift, LeftAlt)")
    q.add_argument("--focus", action="store_true", help="bring the game in front first")
    q = cmd("move", cmd_move, "walk your cat (relative to the camera) and turn")
    q.add_argument("--forward", type=float, default=1.0)
    q.add_argument("--right", type=float, default=0.0)
    q.add_argument("--seconds", type=float, default=1.0)
    q.add_argument("--turn", type=float, help="degrees to the right first")
    q = cmd("cat", cmd_cat, "your cat's name, level, health, stamina and where it is")
    q.add_argument("--teleport", metavar="X,Y,Z")
    q = cmd("screens", cmd_screens, "the game's own screens that show (main menu, cat choice...)")
    q.add_argument("--press", nargs=2, metavar=("SCREEN", "BUTTON"), help="click a button on one")
    q = cmd("menu", cmd_menu, "the mod menu: pages | open [PAGE] | close | read [PAGE] | press LABEL | "
                              "set LABEL VALUE | section TITLE [close] | scroll [top|end|N|LABEL] | shot [PAGE [NAME]]")
    q.add_argument("what", choices=("pages", "open", "close", "read", "press", "set", "section", "scroll", "shot"))
    q.add_argument("args", nargs="*")
    q.add_argument("--json", action="store_true")
    q = cmd("log", cmd_log, "the end of UE4SS.log")
    q.add_argument("--errors", action="store_true", help="only lines that say a script went wrong")
    q.add_argument("--grep")
    q.add_argument("--lines", type=int, default=40)
    q = cmd("crash", cmd_crash, "whether the crash reporter is open; --close closes it without sending")
    q.add_argument("--close", action="store_true")
    q = cmd("test", cmd_test, "run the in-game tests (tests/game) and write a report with pictures")
    q.add_argument("paths", nargs="*", help="test files or folders (default tests/game)")
    q.add_argument("-k", help="only tests whose name has this in it")
    q.add_argument("--launch", action="store_true", help="start the game (and play into the forest) when a test needs it")
    q.add_argument("--stop", action="store_true", help="stop at the first failure")
    q.add_argument("--list", action="store_true", help="list the tests without running them")
    q.add_argument("--no-backup", action="store_true", help="don't back up the save first")
    q = cmd("run", cmd_run, "run a Python script with `agent` ready in it")
    q.add_argument("script")
    q.add_argument("args", nargs="*")
