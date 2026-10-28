"""The repository's own rules: every Python file is Python 3.10, no module reads the player's folder as it's
imported, a stray `pytest tests/game` touches no game, the studio's committed fixture is current, and the
tests wrote nothing into the player's folder."""
import ast
import json
import os
import subprocess
import sys

from conftest import REPO, SANDBOX

SKIPPED_DIRS = {".git", ".claude", "__pycache__", "build", "cache", "node_modules"}


def python_files():
    for folder, dirs, files in os.walk(REPO):
        dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.endswith(".py"):
                yield os.path.join(folder, f)


def test_every_python_file_is_python_3_10():
    found = 0
    for path in python_files():
        with open(path, encoding="utf-8") as f:
            ast.parse(f.read(), path, feature_version=(3, 10))
        found += 1
    assert found > 50


class ImportTimeCalls(ast.NodeVisitor):
    """The calls a module makes as it's imported: at the top level, in class bodies, in decorators and in
    default arguments; not inside function bodies."""

    def __init__(self):
        self.calls = []

    def visit_Call(self, node):
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        self.calls.append((name, node.lineno))
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        for d in node.decorator_list:
            self.visit(d)
        self.visit(node.args)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        self.visit(node.args)


def test_no_module_reads_the_players_folder_as_it_is_imported():
    """config.data_dir() is where a player's mods and wcmods.json are: a module calling it at import would
    pin the folder before WCMODS_DATA or a test's Config(root, data) can say otherwise."""
    culprits = []
    for path in python_files():
        if not path.startswith(os.path.join(REPO, "wcmods")):
            continue
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
        v = ImportTimeCalls()
        v.visit(tree)
        culprits += [f"{os.path.relpath(path, REPO)}:{line}" for name, line in v.calls if name == "data_dir"]
    assert culprits == []


def test_the_command_line_loads_no_windows_dll_until_an_agent_command_runs(tmp_path):
    """The agent's window.py loads user32 as it's imported; the command line registers the agent's commands on
    every run, on Linux too, so it imports none of that until one of them runs. Here WinDLL refuses, as off
    Windows, and every command's help still prints."""
    code = ("import ctypes, sys\n"
            "def refuse(*a, **k):\n"
            "    raise OSError('no Windows DLLs here')\n"
            "ctypes.WinDLL = refuse\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from wcmods.cli import main\n"
            "main(sys.argv[2], ['--help'])\n")
    (tmp_path / "root").mkdir()
    r = subprocess.run([sys.executable, "-I", "-c", code, REPO, str(tmp_path / "root")], capture_output=True, text=True,
                       timeout=120, env={**os.environ, "WCMODS_DATA": str(tmp_path / "data")})
    assert r.returncode == 0 and "agent" in r.stdout, r.stdout + r.stderr


def test_pytest_collects_nothing_under_tests_game():
    r = subprocess.run([sys.executable, "-m", "pytest", os.path.join("tests", "game"), "--co", "-p", "no:cacheprovider"],
                       cwd=REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 5 and "error" not in (r.stdout + r.stderr).lower(), r.stdout + r.stderr   # 5: nothing collected
    assert "test_cat.py" not in r.stdout


# ---------- the studio's placeMesh against models.place ----------
FIXTURE = os.path.join(REPO, "tests", "studio", "fixtures", "place.json")
# An asymmetric little shape, in the game's space (cm; X the cat's left, Y its front, Z up).
MESH_POINTS = [(0, 0, 0), (10, 0, 0), (0, 20, 0), (0, 0, 30), (4, 6, 8), (-3, 12, 15)]
MESH_TRIANGLES = [(0, 1, 2), (0, 2, 3), (1, 2, 4), (3, 4, 5)]
PLACES = [
    ({}, False), ({"scale": 2}, False), ({"scale": {"left": 0.5, "up": 3}}, False), ({"roll": 30}, False),
    ({"pitch": -45}, False), ({"yaw": 90}, False), ({"left": 1.5, "forward": -2, "up": 3.25}, False),
    ({"roll": 10, "pitch": 20, "yaw": 30, "scale": 1.5, "up": 2}, False),
    ({"roll": 10, "pitch": 20, "yaw": 30, "scale": 1.5, "up": 2}, True), ({"scale": 2, "forward": 5}, True),
]


def place_fixture():
    """What tests/studio/shape.test.mjs checks placeMesh against: the mesh as the API sends one (flat lists)
    and, for each place, the positions models.place gives, to 6 decimals."""
    from wcmods import models
    model = models.Model(MESH_POINTS, [(0.0, 0.0, 1.0)] * len(MESH_POINTS), [(0.0, 0.0)] * len(MESH_POINTS), MESH_TRIANGLES)
    cases = []
    for spec, base in PLACES:
        models.check_place(spec, "test")
        placed = models.place(model, spec, base=base)
        cases.append({"place": spec, "base": base, "p": [round(float(c), 6) for p in placed.positions for c in p]})
    return {"_help": "Written by tests/unit/test_repo.py from wcmods.models.place (WC_UPDATE_FIXTURES=1 rewrites it); "
                     "tests/studio/shape.test.mjs checks studio/lib/shape.js's placeMesh against it.",
            "mesh": {"p": [float(c) for p in MESH_POINTS for c in p], "t": [i for t in MESH_TRIANGLES for i in t]},
            "cases": cases}


def test_the_studios_place_fixture_is_what_models_place_gives():
    want = place_fixture()
    if os.environ.get("WC_UPDATE_FIXTURES") == "1":
        with open(FIXTURE, "w", encoding="utf-8", newline="\n") as f:   # a case per line, so a diff reads
            f.write('{\n "_help": %s,\n "mesh": %s,\n "cases": [\n%s\n ]\n}\n' % (
                json.dumps(want["_help"]), json.dumps(want["mesh"]), ",\n".join("  " + json.dumps(c) for c in want["cases"])))
    with open(FIXTURE, encoding="utf-8") as f:
        have = json.load(f)
    assert have == want, "tests/studio/fixtures/place.json is out of date: run pytest with WC_UPDATE_FIXTURES=1 and commit it"


def test_nothing_was_written_to_the_players_folder():
    """WCMODS_DATA points at a folder of this run's own (conftest.py); the run's end checks it again."""
    assert os.environ["WCMODS_DATA"] == SANDBOX and os.listdir(SANDBOX) == []
