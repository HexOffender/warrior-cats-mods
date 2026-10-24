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


def set_registered(mods_dir, name, enabled):
    """Turn an installed UE4SS mod on or off in place in mods.txt and mods.json, keeping its entry (for the
    mods that ship with UE4SS, listed as "Name : 0" when off)."""
    txt = os.path.join(mods_dir, "mods.txt")
    if os.path.isfile(txt):
        with open(txt, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
        hits = [i for i, l in enumerate(lines) if l.split(":")[0].strip() == name]
        if hits:
            lines[hits[0]] = f"{name} : {1 if enabled else 0}"
            with open(txt, "w", encoding="utf-8", newline="\r\n") as f:
                f.write("\n".join(lines) + "\n")
        else:
            _register(mods_dir, name, enabled)
            return
    js = os.path.join(mods_dir, "mods.json")
    if os.path.isfile(js):
        with open(js, encoding="utf-8-sig") as f:
            entries = json.load(f)
        for e in entries:
            if e.get("mod_name") == name:
                e["mod_enabled"] = bool(enabled)
        with open(js, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=4)


OUR_PREFIX = "WCMods"   # every UE4SS mod wcmods builds itself is named WCMods...


def ours(mods_dir):
    """The WCMods... mod folders installed now, whether or not wcmods.json still lists them."""
    if not os.path.isdir(mods_dir):
        return set()
    return {n for n in os.listdir(mods_dir)
            if n.startswith(OUR_PREFIX) and os.path.isdir(os.path.join(mods_dir, n))}


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


def install_shared(mods_dir, name, source_dir):
    """Install a shared Lua module as Mods/shared/<name>/, which any UE4SS script can require(name).
    Shared modules aren't mods: UE4SS doesn't run them on their own, so they aren't registered."""
    target = os.path.join(mods_dir, "shared", name)
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(source_dir, target)
    return target


def remove_shared(mods_dir, name):
    target = os.path.join(mods_dir, "shared", name)
    if os.path.isdir(target):
        shutil.rmtree(target)
        return target
    return None


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
