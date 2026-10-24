"""Tests that run in the game, and the report they leave.

A test file is a Python file (tests/game/test_*.py); each function in it named test_*(agent) is a
test, run in the order the file has them. A file can say what it needs and set things up:

    NEEDS = "world"          # "world" (the default): your cat in the forest; "game": the game with the
                             # bridge, anywhere; "nothing": not even the game
    LOG_ERRORS_OK = False    # True: script errors in UE4SS.log during a test don't fail it
    def setup(agent): ...    # before each test in the file
    def teardown(agent): ... # after each, even one that failed

A test fails on an AssertionError, errs on any other exception, and is skipped by skip("why"). Script
errors that reach UE4SS.log while it runs fail it too, and a crash ends the run. A failing test gets
a picture of the game. Each run writes agent-output/runs/<time>/: report.md, report.html, report.json
and the pictures in shots/.
"""
import datetime
import html
import importlib.util
import inspect
import json
import os
import time
import traceback

from . import window
from .controller import Agent, AgentError


class Skip(Exception):
    pass


def skip(why):
    """Skip the test that's running."""
    raise Skip(why)


class Test:
    def __init__(self, module, fn, path):
        self.module, self.fn, self.path = module, fn, path
        self.name = f"{os.path.splitext(os.path.basename(path))[0]}::{fn.__name__}"
        self.doc = inspect.getdoc(fn) or ""

    @property
    def needs(self):
        return getattr(self.module, "NEEDS", "world")


def discover(paths, pattern=None):
    """The tests in these files and folders (folders: their test_*.py), filtered by `pattern` (a part of
    the test's name)."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.startswith("test_") and f.endswith(".py")]
        elif os.path.isfile(p):
            files.append(p)
        else:
            raise AgentError(f"no test file or folder {p}")
    tests = []
    for path in files:
        name = "wcmods_game_test_" + os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fns = [f for n, f in vars(module).items() if n.startswith("test_") and inspect.isfunction(f)]
        fns.sort(key=lambda f: f.__code__.co_firstlineno)
        for fn in fns:
            t = Test(module, fn, path)
            if not pattern or pattern.lower() in t.name.lower():
                tests.append(t)
    return tests


def _where(exc):
    """The traceback from the test on (the runner's own frames say nothing)."""
    tb = exc.__traceback__
    while tb and os.path.abspath(tb.tb_frame.f_code.co_filename) == os.path.abspath(__file__):
        tb = tb.tb_next
    return "".join(traceback.format_exception(type(exc), exc, tb)).rstrip()


def run(root, paths, pattern=None, launch=False, stop_on_fail=False, out_dir=None, log=print, backup=True):
    """Run the tests; returns the report (a dict) after writing it to out_dir."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = out_dir or os.path.join(root, "agent-output", "runs", stamp)
    os.makedirs(out_dir, exist_ok=True)
    agent = Agent(root, out_dir=out_dir, log=log)
    tests = discover(paths, pattern)
    report = {"started": stamp, "folder": out_dir, "tests": [], "save_backup": None}
    if backup and any(t.needs != "nothing" for t in tests) and agent.cfg.save_dir and os.path.isdir(agent.cfg.save_dir):
        # Tests change your cat and the world, and the game saves as it goes.
        report["save_backup"] = agent.backup_save("before-agent-tests")
        log(f"backed up the save as {report['save_backup']} (python wcmods.py restore {report['save_backup']})")
    stopped = None
    unready = None   # why the game couldn't be got ready: the tests that need it after that aren't run
    for t in tests:
        r = {"name": t.name, "doc": t.doc, "status": "passed", "seconds": 0.0, "message": "", "where": "",
             "shots": [], "log_errors": []}
        report["tests"].append(r)
        if stopped or (unready and t.needs != "nothing"):
            r.update(status="not run", message=stopped or unready)
            continue
        t0, first_shot = time.time(), len(agent.shots)
        try:
            _ready(agent, t.needs, launch)
        except Skip as e:
            r.update(status="skipped", message=str(e))
            log(f"  skip  {t.name}: {e}")
            continue
        except Exception as e:   # noqa: BLE001 - starting the game failed: say so in the report, don't lose it
            r.update(status="error", message=f"the game couldn't be got ready: {type(e).__name__}: {e}", where=_where(e),
                     seconds=round(time.time() - t0, 2))
            log(f"  error   {t.name}: {r['message']}")
            unready = f"not run: the game couldn't be got ready for {t.name}"
            continue
        mark = agent.log_mark()
        try:
            if hasattr(t.module, "setup"):
                t.module.setup(agent)
            try:
                t.fn(agent)
            finally:
                if hasattr(t.module, "teardown"):
                    t.module.teardown(agent)
        except Skip as e:
            r.update(status="skipped", message=str(e))
        except AssertionError as e:
            r.update(status="failed", message=str(e) or "assertion failed", where=_where(e))
        except Exception as e:   # noqa: BLE001 - every other error is the test's result too
            r.update(status="error", message=f"{type(e).__name__}: {e}", where=_where(e))
        if t.needs != "nothing":
            r["log_errors"] = agent.errors_since(mark)[:40]
            if r["log_errors"] and r["status"] == "passed" and not getattr(t.module, "LOG_ERRORS_OK", False):
                r.update(status="failed", message="scripts logged errors while it ran (see below)")
            if agent.crashed() or (window.game_pid() is None and t.needs != "nothing"):
                r.update(status="crashed", message=(r["message"] + "; " if r["message"] else "") + "the game crashed or closed")
                stopped = f"not run: the game went away during {t.name}"
            elif r["status"] in ("failed", "error") and window.game_window():
                try:
                    agent.shot("FAIL-" + t.fn.__name__)
                except Exception:   # noqa: BLE001 - a picture is a nice-to-have
                    pass
        r["seconds"] = round(time.time() - t0, 2)
        r["shots"] = [os.path.relpath(p, out_dir).replace("\\", "/") for p in agent.shots[first_shot:]]
        log(f"  {r['status']:<7} {t.name} ({r['seconds']:.1f} s)" + (f": {r['message']}" if r["message"] and r["status"] != "passed" else ""))
        if stop_on_fail and r["status"] in ("failed", "error"):
            stopped = f"not run: stopped after {t.name} failed"
    report["counts"] = {s: sum(1 for r in report["tests"] if r["status"] == s)
                        for s in ("passed", "failed", "error", "crashed", "skipped", "not run")}
    write(report, out_dir)
    return report


def _ready(agent, needs, launch):
    if needs == "nothing":
        return
    st = agent.status()
    if st["crash_reporter"]:
        raise Skip("the game's crash reporter is open")
    if needs == "game" and st["bridge"]:
        return
    if needs == "world" and st["in_world"]:
        return
    if not launch:
        raise Skip("the game isn't " + ("in the forest" if needs == "world" else "running with the bridge")
                   + " (run with --launch, or `agent launch --world`)")
    agent.launch(world=needs == "world")


def ok(report):
    c = report["counts"]
    return not (c["failed"] or c["error"] or c["crashed"])


def summary(report):
    c = report["counts"]
    parts = [f"{n} {s}" for s, n in c.items() if n]
    return ", ".join(parts) or "no tests"


def write(report, out_dir):
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    md = [f"# In-game test run {report['started']}", "", summary(report), ""]
    if report.get("save_backup"):
        md += [f"The save was backed up first: `python wcmods.py restore {report['save_backup']}` puts it back "
               "(with the game closed).", ""]
    for r in report["tests"]:
        md.append(f"## {r['status'].upper()}: {r['name']} ({r['seconds']} s)")
        if r["doc"]:
            md += ["", r["doc"]]
        if r["message"] and r["status"] != "passed":
            md += ["", r["message"]]
        if r["where"]:
            md += ["", "```", r["where"], "```"]
        if r["log_errors"]:
            md += ["", "Log errors:", "", "```", *r["log_errors"], "```"]
        for s in r["shots"]:
            md += ["", f"![{os.path.basename(s)}]({s})"]
        md.append("")
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(os.path.join(out_dir, "report.html"), "w", encoding="utf-8") as f:
        f.write(_html(report))


_COLOURS = {"passed": "#2f8f4e", "failed": "#c0392b", "error": "#c0392b", "crashed": "#8e44ad", "skipped": "#7f8c8d",
            "not run": "#7f8c8d"}


def _html(report):
    e = html.escape
    rows = []
    for r in report["tests"]:
        body = []
        if r["doc"]:
            body.append(f"<p class=doc>{e(r['doc'])}</p>")
        if r["message"] and r["status"] != "passed":
            body.append(f"<p class=msg>{e(r['message'])}</p>")
        if r["where"]:
            body.append(f"<pre>{e(r['where'])}</pre>")
        if r["log_errors"]:
            body.append("<p>Log errors:</p><pre>" + e("\n".join(r["log_errors"])) + "</pre>")
        if r["shots"]:
            body.append("<div class=shots>" + "".join(
                f"<a href='{e(s)}'><img src='{e(s)}' alt='{e(os.path.basename(s))}' loading=lazy></a>" for s in r["shots"]) + "</div>")
        rows.append(f"<section><h2><span class=badge style='background:{_COLOURS.get(r['status'], '#555')}'>"
                    f"{e(r['status'])}</span> {e(r['name'])} <small>{r['seconds']} s</small></h2>{''.join(body)}</section>")
    backup = (f"<p>The save was backed up first: <code>python wcmods.py restore {e(report['save_backup'])}</code> "
              "puts it back (with the game closed).</p>") if report.get("save_backup") else ""
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1"><title>In-game tests</title><style>
:root {{ --bg: #f6f7f9; --fg: #1d232b; --card: #fff; --line: #dde1e6; --muted: #5f6b78; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #14181d; --fg: #e6e9ed; --card: #1c2128; --line: #2c333c; --muted: #9aa6b5; }} }}
body {{ margin: 0; padding: 24px 16px; background: var(--bg); color: var(--fg); font: 15px/1.5 system-ui, sans-serif; }}
main {{ max-width: 1100px; margin: 0 auto; }}
section {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px 16px; margin: 12px 0; }}
h1 {{ font-size: 22px; margin: 0 0 4px; }} h2 {{ font-size: 16px; margin: 0; }} small, .doc {{ color: var(--muted); }}
.badge {{ color: #fff; border-radius: 4px; padding: 1px 8px; font-size: 13px; margin-right: 6px; }}
pre {{ background: var(--bg); padding: 8px; overflow-x: auto; font-size: 12.5px; border-radius: 4px; }}
.shots {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
.shots img {{ width: 260px; max-width: 100%; border: 1px solid var(--line); border-radius: 4px; }}
</style></head><body><main><h1>In-game test run {e(report['started'])}</h1><p>{e(summary(report))}</p>{backup}
{''.join(rows)}</main></body></html>"""
