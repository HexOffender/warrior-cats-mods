"""Install and register UE4SS Lua mods (mods.txt and mods.json both list enabled mods)."""
import json
import os
import shutil


def _register(mods_dir, name, enabled):
    txt = os.path.join(mods_dir, "mods.txt")
    if os.path.isfile(txt):
        with open(txt, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
        lines = [l for l in lines if l.split(":")[0].strip() != name]
        if enabled:
            at = next((i for i, l in enumerate(lines) if l.strip().startswith("; Built-in keybinds")), len(lines))
            lines.insert(at, f"{name} : 1")
        with open(txt, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")
    js = os.path.join(mods_dir, "mods.json")
    if os.path.isfile(js):
        with open(js, encoding="utf-8-sig") as f:
            entries = json.load(f)
        entries = [e for e in entries if e.get("mod_name") != name]
        if enabled:
            at = next((i for i, e in enumerate(entries) if e.get("mod_name") == "Keybinds"), len(entries))
            entries.insert(at, {"mod_name": name, "mod_enabled": True})
        with open(js, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=4)


def install_mod(mods_dir, name, source_dir):
    target = os.path.join(mods_dir, name)
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(source_dir, target)
    _register(mods_dir, name, True)
    return target


def remove_mod(mods_dir, name):
    target = os.path.join(mods_dir, name)
    if os.path.isdir(target):
        shutil.rmtree(target)
    _register(mods_dir, name, False)


def log_path(win64_dir):
    for sub in (("ue4ss", "UE4SS.log"), ("UE4SS.log",)):
        p = os.path.join(win64_dir, *sub)
        if os.path.isfile(p):
            return p
    return None


def read_reports(win64_dir, tag="[WCModsPalettes]"):
    """Parse the TABLE lines (the game's original colour tables) and notes our script logs."""
    path = log_path(win64_dir)
    tables, notes = {}, []
    if not path:
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if tag not in line:
                continue
            msg = line.split(tag, 1)[1].strip()
            if msg.startswith("TABLE "):
                _, prop, _n, *hexes = msg.split()
                tables[prop] = hexes
            else:
                notes.append(msg)
    return {"tables": tables, "notes": notes[-20:], "log_time": os.path.getmtime(path)}
