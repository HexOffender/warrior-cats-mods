"""Building C++ mods: `wcmods cpp setup` gets UE4SS's source at the game's UE4SS build, and `wcmods cpp
build` builds mods' cpp/ folders into their dlls/main.dll (sections/cpp.py installs that).

A UE4SS C++ mod links against UE4SS itself, so it's built together with UE4SS's source, at the very commit
of the UE4SS.dll in the game (UE4SS.log names it). That needs:
- Visual Studio 2022 or later with "Desktop development with C++" (MSVC 14.43 or later; it brings CMake and
  Ninja),
- Rust (https://rustup.rs; UE4SS's pattern scanner is written in it),
- git, and a GitHub account linked to an Epic Games account: UE4SS's Unreal headers (UEPseudo) are only
  open to members of the EpicGames organisation on GitHub.
The source goes in cache/ue4ss-src and the build in cache/cpp. The first build compiles UE4SS too (several
minutes); later ones only the mods. docs/SDK.md, "C++ mods", has the details.
"""
import datetime
import json
import os
import re
import shutil
import subprocess

from . import ue4ss
from .sections.cpp import BUILD_INFO, DLLS, SOURCE

REPO = "https://github.com/UE4SS-RE/RE-UE4SS.git"
CONFIG = "Game__Shipping__Win64"   # the build of UE4SS its releases are, and the one mods must match
SDK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cpp_sdk")
EPIC = ("UE4SS's Unreal headers (UEPseudo) are only open to GitHub accounts in the EpicGames organisation: "
        "link your GitHub account to an Epic Games account (epicgames.com, Account, Apps and Accounts), "
        "accept the invitation GitHub emails you, then run `python wcmods.py cpp setup` again")
# Submodules name github.com by SSH; https works with the login git already has. Long paths, because
# UE4SS's dependencies are checked out several folders deep.
GIT_CONFIG = {"url.https://github.com/.insteadOf": "git@github.com:", "core.longpaths": "true"}


def _git_env():
    env = dict(os.environ)
    n = int(env.get("GIT_CONFIG_COUNT", "0") or 0)
    for i, (key, value) in enumerate(GIT_CONFIG.items(), n):
        env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"] = key, value
    env["GIT_CONFIG_COUNT"] = str(n + len(GIT_CONFIG))
    return env


def source_dir(root):
    return os.path.join(root, "cache", "ue4ss-src")


def build_dir(root):
    return os.path.join(root, "cache", "cpp")


def toolchain():
    """What a build needs, found: {"vs", "vcvars", "cmake", "ninja", "cargo", "git"} (paths, or None)."""
    found = dict.fromkeys(("vs", "vcvars", "cmake", "ninja", "cargo", "git"))
    vswhere = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                           "Microsoft Visual Studio", "Installer", "vswhere.exe")
    if os.path.isfile(vswhere):
        try:
            out = subprocess.run([vswhere, "-latest", "-products", "*", "-requires",
                                  "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                                 capture_output=True, text=True, timeout=30).stdout.strip().splitlines()
        except (OSError, subprocess.SubprocessError):
            out = []
        if out:
            vs = out[0].strip()
            found["vs"] = vs
            vcvars = os.path.join(vs, "VC", "Auxiliary", "Build", "vcvars64.bat")
            found["vcvars"] = vcvars if os.path.isfile(vcvars) else None
            bundled = os.path.join(vs, "Common7", "IDE", "CommonExtensions", "Microsoft", "CMake")
            for tool, sub in (("cmake", ("CMake", "bin", "cmake.exe")), ("ninja", ("Ninja", "ninja.exe"))):
                path = os.path.join(bundled, *sub)
                found[tool] = path if os.path.isfile(path) else None
    for tool in ("cmake", "ninja", "git"):
        found[tool] = found[tool] or shutil.which(tool)
    cargo = os.path.join(os.path.expanduser("~"), ".cargo", "bin", "cargo.exe")
    found["cargo"] = shutil.which("cargo") or (cargo if os.path.isfile(cargo) else None)
    return found


def problems(tools):
    """What's missing from toolchain(), as things to do."""
    out = []
    if not tools["vcvars"]:
        out.append("Visual Studio 2022 or later with \"Desktop development with C++\" "
                   "(https://visualstudio.microsoft.com, Community is free)")
    elif not (tools["cmake"] and tools["ninja"]):
        out.append("CMake and Ninja: in the Visual Studio Installer, add \"C++ CMake tools for Windows\"")
    if not tools["cargo"]:
        out.append("Rust (https://rustup.rs, or `winget install Rustlang.Rustup`); UE4SS's pattern scanner is "
                   "written in it")
    if not tools["git"]:
        out.append("git (https://git-scm.com)")
    return out


def _git(args, cwd=None, check=True, shown=False):
    """Run git. `shown` leaves its output on the terminal rather than capturing it: for what goes to GitHub,
    so a login prompt is seen instead of waiting unseen."""
    p = subprocess.run(["git", *args], cwd=cwd, env=_git_env(), capture_output=not shown, text=True)
    if check and p.returncode:
        said = "" if shown else ": " + (p.stderr or p.stdout).strip()[-1500:]
        raise RuntimeError(f"git {' '.join(args)} failed{said}")
    return p


def source_commit(root):
    """The commit cache/ue4ss-src is at, or None without it."""
    src = source_dir(root)
    if not os.path.isdir(os.path.join(src, ".git")):
        return None
    p = _git(["rev-parse", "HEAD"], cwd=src, check=False)
    return p.stdout.strip() or None


def game_ue4ss(cfg):
    """The game's UE4SS, as ue4ss.loader_identity gives it, or None."""
    try:
        return ue4ss.loader_identity(cfg.win64_dir)
    except Exception:   # no game found
        return None


def setup(root, cfg, commit=None, log=print):
    """Get UE4SS's source at the game's UE4SS commit (or `commit`) into cache/ue4ss-src, with its
    submodules. Returns the commit it's at."""
    if not shutil.which("git"):
        raise RuntimeError("git isn't installed: get it from https://git-scm.com")
    if not commit:
        found = game_ue4ss(cfg)
        if not found:
            raise RuntimeError("the game hasn't got UE4SS: install it first (Clan Mod Studio's Get set up), or "
                               "pass --commit")
        commit = found["commit"]
        if not commit:
            raise RuntimeError("UE4SS.log doesn't say which UE4SS the game has yet: start the game once with UE4SS "
                               "(it writes the log), or pass --commit (the 8 letters after \"g\" in UE4SS's "
                               "file name, UE4SS_v3.0.1-1181-g83330635.zip)")
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
        raise ValueError(f"{commit!r} isn't a git commit")
    src = source_dir(root)
    if not os.path.isdir(os.path.join(src, ".git")):
        os.makedirs(os.path.dirname(src), exist_ok=True)
        log(f"getting UE4SS's source from {REPO} ...")
        _git(["clone", "--filter=blob:none", "--no-checkout", REPO, src], shown=True)
    if _git(["cat-file", "-e", commit + "^{commit}"], cwd=src, check=False).returncode:
        log("fetching UE4SS's newer commits ...")
        _git(["fetch", "origin"], cwd=src, shown=True)
    log(f"checking out UE4SS {commit[:8]} ...")
    _git(["checkout", "-q", "--force", commit], cwd=src)
    log("getting its submodules (UEPseudo, the Unreal headers, needs your GitHub login) ...")
    p = _git(["submodule", "update", "--init", "--recursive", "--force"], cwd=src, check=False, shown=True)
    if not os.path.isfile(os.path.join(src, "deps", "first", "Unreal", "CMakeLists.txt")):
        raise RuntimeError(EPIC + " (git's messages above say what happened)")
    if p.returncode:
        raise RuntimeError("getting UE4SS's submodules failed; git's messages above say why")
    return source_commit(root)


def status(root, cfg):
    """{"tools", "problems", "source" (commit or None), "game" (ue4ss.loader_identity or None), "matches"}."""
    tools = toolchain()
    source, game = source_commit(root), game_ue4ss(cfg)
    same = None
    if source and game and game.get("commit"):
        same = source.startswith(game["commit"]) or game["commit"].startswith(source)
    return {"tools": tools, "problems": problems(tools), "source": source, "game": game, "matches": same}


def cpp_mods(mods, ids=None, root=None):
    """The mods with C++ source (cpp/CMakeLists.txt): the ones named (a mod's id in mods/, or the path of a
    mod folder anywhere, like tests/cpp-sdk, as given or under wcmods' `root`), or the enabled ones."""
    from .mods import Mod
    have = [m for m in mods if os.path.isfile(os.path.join(m.folder, SOURCE, "CMakeLists.txt"))]
    if not ids:
        return [m for m in have if m.enabled]
    by_id = {m.id: m for m in mods}
    out = []
    for i in ids:
        folders = [i] + ([os.path.join(root, i)] if root and not os.path.isabs(i) else [])
        folder = next((f for f in folders if os.path.isfile(os.path.join(f, "mod.json"))), None)
        if i in by_id:
            m = by_id[i]
        elif folder:
            m = Mod(os.path.abspath(folder))
        else:
            raise ValueError(f"no mod named {i} (nor a mod folder at that path)")
        if not os.path.isfile(os.path.join(m.folder, SOURCE, "CMakeLists.txt")):
            raise ValueError(f"{i} has no C++ source (cpp/CMakeLists.txt)")
        out.append(m)
    return out


def target_name(mod_id):
    return "wcmods_" + re.sub(r"[^A-Za-z0-9]+", "_", mod_id).strip("_")


def _cmake_path(path):
    return os.path.abspath(path).replace("\\", "/")


def project(root, mods):
    """The CMake project `cpp build` builds: UE4SS's source, the SDK, and each mod's cpp/."""
    lines = ["# Written by wcmods (`wcmods cpp build`): UE4SS and the C++ mods it builds. Changes here are",
             "# overwritten; a mod's own build is its cpp/CMakeLists.txt.",
             "cmake_minimum_required(VERSION 3.22)",
             "project(WCModsCpp)",
             f'add_subdirectory("{_cmake_path(source_dir(root))}" ue4ss)',
             f'include("{_cmake_path(os.path.join(SDK_DIR, "WCMods.cmake"))}")']
    for m in mods:
        lines += [f"set(WCMODS_TARGET {target_name(m.id)})",
                  f'add_subdirectory("{_cmake_path(os.path.join(m.folder, SOURCE))}" "mods/{target_name(m.id)}")']
    return "\n".join(lines) + "\n"


def _write_if_changed(path, text):
    old = None
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            old = f.read()
    if old != text:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


def _run(bat, commands, tools, log):
    """Run cmd lines (written to the batch file `bat`) with Visual Studio's compiler, CMake, Ninja and Rust
    on the PATH, logging the output. Returns the exit code."""
    path = os.pathsep.join(os.path.dirname(tools[t]) for t in ("cmake", "ninja", "cargo"))
    lines = ["@echo off", f'call "{tools["vcvars"]}" >nul || exit /b 1', f'set "PATH={path};%PATH%"', *commands]
    with open(bat, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    p = subprocess.Popen(["cmd", "/d", "/c", bat], env=_git_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    # Everything goes in build.log beside it; the log gets the steps and the problems, not every command line.
    with open(os.path.join(os.path.dirname(bat), "build.log"), "w", encoding="utf-8") as full:
        for line in p.stdout:
            full.write(line)
            line = line.rstrip()
            if re.search(r"\berror\b|FAILED|warning C\d+.*[\\/]mods[\\/]", line, re.I) and not line.startswith("C:\\PROGRA"):
                log(line)
            elif re.match(r"\[\d+/\d+\] ", line):
                log(line if len(line) <= 140 else line[:137] + "...")
    return p.wait()


def vs_generator(help_text):
    """CMake's generator for the newest Visual Studio it knows, from `cmake --help` ("Visual Studio 18 2026")."""
    found = re.findall(r"Visual Studio (\d+) (\d{4})", help_text)
    if not found:
        return None
    major, year = max(found, key=lambda f: int(f[1]))
    return f"Visual Studio {major} {year}"


def ide(root, cfg, mods, log=print, open_it=False):
    """A Visual Studio solution for the mods' C++ (and UE4SS, which they link), in cache/cpp/ide, to edit, build
    and debug in (attach to the game). Returns the .sln's path."""
    if not mods:
        raise ValueError("no enabled mod has C++ source (cpp/CMakeLists.txt); name the mods")
    tools = toolchain()
    missing = problems(tools)
    if missing:
        raise RuntimeError("a Visual Studio solution needs:\n- " + "\n- ".join(missing))
    if not source_commit(root):
        raise RuntimeError("UE4SS's source isn't here yet: run `python wcmods.py cpp setup`")
    out = build_dir(root)
    os.makedirs(out, exist_ok=True)
    _write_if_changed(os.path.join(out, "CMakeLists.txt"), project(root, mods))
    help_text = subprocess.run([tools["cmake"], "--help"], capture_output=True, text=True).stdout
    generator = vs_generator(help_text)
    if not generator:
        raise RuntimeError("this CMake knows no Visual Studio generator")
    log(f"making a {generator} solution in {os.path.join(out, 'ide')} (it configures UE4SS too: a few minutes) ...")
    code = _run(os.path.join(out, "ide.bat"), [f'cd /d "{out}"', f'cmake -S . -B ide -G "{generator}" -A x64 || exit /b 1'], tools, log)
    if code:
        raise RuntimeError(f"making the solution failed (exit code {code}); {os.path.join(out, 'build.log')} has the messages")
    sln = os.path.join(out, "ide", "WCModsCpp.sln")
    log(f"solution: {sln}\n  build the mod's project in the Game__Shipping__Win64 configuration (the one the game's UE4SS is), "
        f"then install; to debug, attach to Wrc-Win64-ShippingDRM.exe")
    if open_it:
        os.startfile(sln)
    return sln


def watch(root, cfg, mods, log=print, every=2.0):
    """Build the mods, then again whenever a file in their cpp/ changes, until Ctrl+C."""
    from .sections.cpp import SOURCE, source_time
    import time

    def stamp():
        return max(source_time(os.path.join(m.folder, SOURCE)) for m in mods)

    seen = stamp()
    try:
        build(root, cfg, mods, log)
    except (RuntimeError, ValueError) as e:
        log(f"error: {e}")
    log("watching cpp/ for changes (Ctrl+C stops)")
    try:
        while True:
            time.sleep(every)
            now = stamp()
            if now == seen:
                continue
            seen = now
            log("changed; building ...")
            try:
                build(root, cfg, mods, log)
            except (RuntimeError, ValueError) as e:
                log(f"error: {e}")
    except KeyboardInterrupt:
        log("stopped")


def keep(mod, log=print):
    """Copy a mod's dlls/main.dll and build.json into dlls/<UE4SS commit>/, so the mod can carry builds for
    several UE4SS versions: an install uses the one for the game's. Returns the folder."""
    from .sections.cpp import BUILD_INFO, DLLS
    dlls = os.path.join(mod.folder, DLLS)
    info_path = os.path.join(dlls, BUILD_INFO)
    if not os.path.isfile(os.path.join(dlls, "main.dll")) or not os.path.isfile(info_path):
        raise ValueError(f"{mod.id}: build it first (dlls/main.dll and {BUILD_INFO})")
    with open(info_path, encoding="utf-8") as f:
        commit = str(json.load(f).get("ue4ss") or "")[:8]
    if not commit:
        raise ValueError(f"{mod.id}: dlls/{BUILD_INFO} doesn't say which UE4SS it was built for")
    dest = os.path.join(dlls, commit)
    os.makedirs(dest, exist_ok=True)
    for name in ("main.dll", BUILD_INFO):
        shutil.copyfile(os.path.join(dlls, name), os.path.join(dest, name))
    log(f"  {mod.id}: kept as dlls/{commit}/ (for UE4SS {commit})")
    return dest


def build(root, cfg, mods, log=print):
    """Build the mods' cpp/ into their dlls/main.dll, with a dlls/build.json naming the UE4SS it was built
    against. Returns [(mod id, path of its main.dll)]."""
    if not cfg.data.get("allow_code_mods"):
        raise RuntimeError("building C++ mods runs their build files: set \"allow_code_mods\": true in wcmods.json "
                           "(or allow mods that run code in Clan Mod Studio) first")
    if not mods:
        raise ValueError("no enabled mod has C++ source (cpp/CMakeLists.txt); name the mods to build")
    tools = toolchain()
    missing = problems(tools)
    if missing:
        raise RuntimeError("building C++ mods needs:\n- " + "\n- ".join(missing))
    source = source_commit(root)
    if not source or not os.path.isfile(os.path.join(source_dir(root), "deps", "first", "Unreal", "CMakeLists.txt")):
        raise RuntimeError("UE4SS's source isn't here yet: run `python wcmods.py cpp setup`")
    game = game_ue4ss(cfg)
    if game and game.get("commit") and not source.startswith(game["commit"]):
        raise RuntimeError(f"UE4SS's source is at {source[:8]} but the game has UE4SS {game['commit'][:8]}; a mod "
                           "built against the wrong one can crash the game. Run `python wcmods.py cpp setup`")
    # build.json vouches for the game's UE4SS.dll only when its log confirms the source is that UE4SS's;
    # otherwise it names just the source's commit, and install checks that against the log later.
    dll_sha = game["dll"] if game and game.get("commit") else None
    if game and not dll_sha:
        log("(can't tell which UE4SS the game has until it runs with it, so this build names only the commit it "
            "was built against)")
    targets = {}
    for m in mods:
        if target_name(m.id) in targets:
            raise ValueError(f"{m.id} and {targets[target_name(m.id)]} can't be built together: their names differ "
                             "only in punctuation; rename one")
        targets[target_name(m.id)] = m.id
    out = build_dir(root)
    os.makedirs(out, exist_ok=True)
    _write_if_changed(os.path.join(out, "CMakeLists.txt"), project(root, mods))
    # Configured once; a configure that stopped partway leaves a cache but no build.ninja, so that's the test.
    configure = [] if os.path.isfile(os.path.join(out, "out", "build.ninja")) else \
        [f'cmake -S . -B out -G Ninja -DCMAKE_BUILD_TYPE={CONFIG} || exit /b 1']
    targets = " ".join(target_name(m.id) for m in mods)
    log(f"building {', '.join(m.id for m in mods)} with UE4SS {source[:8]}"
        + (" (the first build compiles UE4SS too: several minutes)" if configure else "") + " ...")
    code = _run(os.path.join(out, "run.bat"), [f'cd /d "{out}"', *configure,
                f"cmake --build out --target {targets} || exit /b 1"], tools, log)
    if code:
        raise RuntimeError(f"the build failed (exit code {code}); the messages above say why, and "
                           f"{os.path.join(out, 'build.log')} has all of it")
    built = []
    for m in mods:
        made = os.path.join(out, "out", "wcmods", target_name(m.id), "main.dll")
        if not os.path.isfile(made):
            raise RuntimeError(f"{m.id}: the build made no main.dll; does cpp/CMakeLists.txt call wcmods_mod()?")
        dest = os.path.join(m.folder, DLLS)
        os.makedirs(dest, exist_ok=True)
        shutil.copyfile(made, os.path.join(dest, "main.dll"))
        info = {"ue4ss": source, "ue4ss_dll": dll_sha, "config": CONFIG,
                "built": datetime.datetime.now().replace(microsecond=0).isoformat()}
        with open(os.path.join(dest, BUILD_INFO), "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
            f.write("\n")
        built.append((m.id, os.path.join(dest, "main.dll")))
        log(f"  {m.id}: dlls/main.dll ({os.path.getsize(made) // 1024} KB)")
    return built
