"""In-game scripts without any Python: a mod's scripts/ folder runs in the game through UE4SS.

    mods/my-mod/
      mod.json
      scripts/main.lua      runs when the game starts (more .lua files beside it can be require'd)
      settings.json         optional: the script's settings, as MOD.settings; the mod menu gets a page
                            to change them live and save them back

Each mod's scripts become a UE4SS mod of their own, WCModsScript_<mod id>. Its main.lua is written by
wcmods: it sets up MOD (the mod's id, name, settings and a few helpers) and Game (WCModsGame), then runs
the mod's own scripts/main.lua. Scripts are code, so they only run with "allow_code_mods": true in
wcmods.json, like section.py. docs/scripting.md has the details.
"""
import json
import os
import re

from ..sdk import Section, lua_value

FOLDER = "scripts"
PREFIX = "WCModsScript_"

BOOTSTRAP = r'''-- Written by wcmods: starts @NAME@'s in-game script (mods/@ID@/scripts/main.lua) with its settings.
-- Change the mod's own files and install again rather than editing this. See docs/scripting.md.
local here = debug.getinfo(1, "S").source:gsub("^@", ""):gsub("\\", "/"):match("^(.*/)") or @FALLBACK@
package.path = here .. "mod/?.lua;" .. here .. "mod/?/init.lua;" .. package.path

MOD = {
    id = @ID_LUA@,
    name = @NAME_LUA@,
    folder = @FOLDER_LUA@,           -- the mod's folder in mods/
    settings = @SETTINGS@,           -- settings.json (an empty table without one)
    settingsFile = @SETTINGS_FILE@,  -- where MOD.save() writes them, or nil
}

function MOD.log(fmt, ...)
    print("[" .. MOD.name .. "] " .. string.format(fmt, ...) .. "\n")
end

-- Write MOD.settings back to the mod's settings.json (keys sorted, notes like "_help" kept first), so
-- the next install starts with them. Returns true, or false and why.
function MOD.save()
    if not MOD.settingsFile then return false, "this mod has no settings.json" end
    local ok, Menu = pcall(require, "WCModsMenu")
    if ok then return Menu.saveJson(MOD.settingsFile, MOD.settings) end
    -- Without the mod menu (its own mod, which may be off), WCModsGame writes it.
    local okG, G = pcall(require, "WCModsGame")
    if not okG then return false, "neither WCModsMenu nor WCModsGame is installed" end
    local f, err = io.open(MOD.settingsFile, "w")
    if not f then return false, tostring(err) end
    f:write(G.json.encode(MOD.settings), "\n")
    f:close()
    return true
end

-- A mod menu page for this mod: MOD.page(function(ui) ... end, { title, order, group }). Making one replaces
-- the page wcmods would make for the settings. The mod menu is a mod of its own: when it's off this does
-- nothing and returns false.
local pageMade = false
function MOD.page(fn, opts)
    pageMade = true
    opts = opts or {}
    local ok, Menu = pcall(require, "WCModsMenu")
    if not ok then return false end
    Menu.page(opts.title or MOD.name, fn, { order = opts.order or 40, group = opts.group,
                                            id = opts.id or ("script:" .. MOD.id) })
    return true
end

local okGame, game = pcall(require, "WCModsGame")
if okGame then Game = game else MOD.log("WCModsGame didn't load: %s", tostring(game)) end

local main, loadErr = loadfile(here .. "mod/main.lua")
if not main then
    MOD.log("can't load scripts/main.lua: %s", tostring(loadErr))
    return
end
local ok, err = xpcall(main, debug.traceback)
if not ok then MOD.log("error: %s", tostring(err)) end

-- Without a page of its own, a script with settings gets one: a row for each setting, and Save.
if not pageMade and @AUTO_PAGE@ and next(MOD.settings) ~= nil then
    local okMenu, Menu = pcall(require, "WCModsMenu")
    if okMenu then
        local keys = {}
        for k in pairs(MOD.settings) do keys[#keys + 1] = k end
        table.sort(keys)
        local function label(k)
            local s = tostring(k):gsub("_", " "):gsub("(%l)(%u)", "%1 %2"):lower()
            return (s:gsub("^%l", string.upper))
        end
        Menu.page(MOD.name, function(ui)
            ui.heading(MOD.name)
            for _, k in ipairs(keys) do
                local v = MOD.settings[k]
                if type(k) == "string" and k:sub(1, 1) == "_" then
                    if type(v) == "string" then ui.note(v) end
                elseif type(v) == "boolean" then
                    MOD.settings[k] = ui.switch(label(k), v)
                elseif type(v) == "number" then
                    local whole = math.type(v) == "integer"
                    local n = ui.number(label(k), v, { step = whole and 1 or 0.1, whole = whole })
                    MOD.settings[k] = whole and math.floor(n + 0.5) or n
                elseif type(v) == "string" and v:match("^#%x%x%x%x%x%x$") then
                    MOD.settings[k] = ui.color(label(k), v)
                elseif type(v) == "string" then
                    MOD.settings[k] = ui.input(label(k), v)
                else
                    ui.field(label(k), Menu.json(v))
                end
            end
            if ui.button("Save", { kind = "primary" }) then
                local saved, why = MOD.save()
                if not saved then MOD.log("couldn't save: %s", tostring(why)) end
            end
        end, { order = 40, id = "script:" .. MOD.id })
    end
end
'''


def ue4ss_name(mod_id):
    """The UE4SS mod a mod's scripts are installed as."""
    return PREFIX + re.sub(r"[^A-Za-z0-9]+", "_", mod_id).strip("_")


class ScriptsSection(Section):
    id = "scripts"
    title = "In-game scripts"
    files = (FOLDER,)

    def collect(self, mod, ctx):
        folder = os.path.join(mod.folder, FOLDER)
        if not os.path.isfile(os.path.join(folder, "main.lua")):
            raise ValueError("scripts/ needs a main.lua (it runs when the game starts)")
        files = {}
        for root, _, names in os.walk(folder):
            for name in sorted(names):
                path = os.path.join(root, name)
                rel = os.path.relpath(path, folder).replace(os.sep, "/")
                with open(path, "rb") as f:
                    files[rel] = f.read()
        settings, settings_file = {}, None
        if os.path.isfile(os.path.join(mod.folder, "settings.json")):
            settings = self.read_json(mod, "settings.json")
            if not isinstance(settings, dict):
                raise ValueError("settings.json should hold an object: {\"name\": value, ...}")
            settings_file = os.path.abspath(os.path.join(mod.folder, "settings.json"))
        return {"files": files, "settings": settings, "settings_file": settings_file}

    def build(self, ctx, items):
        if not ctx.cfg.data.get("allow_code_mods"):
            for mod, _ in items:
                ctx.warn(f"{mod.id}: has in-game scripts (scripts/, code); set \"allow_code_mods\": true in wcmods.json "
                         "to let them run")
            return
        try:
            fallback = ctx.cfg.ue4ss_mods_dir
        except Exception:   # no game found; the script works out its own folder anyway
            fallback = None
        for mod, data in items:
            name = ue4ss_name(mod.id)
            here = (os.path.join(fallback, name, "Scripts") + os.sep).replace("\\", "/") if fallback else ""
            main = (BOOTSTRAP.replace("@NAME@", mod.name.replace("\n", " ")).replace("@ID@", mod.id)
                    .replace("@FALLBACK@", lua_value(here)).replace("@ID_LUA@", lua_value(mod.id))
                    .replace("@NAME_LUA@", lua_value(mod.name)).replace("@FOLDER_LUA@", lua_value(os.path.abspath(mod.folder)))
                    .replace("@SETTINGS@", lua_value(data["settings"])).replace("@SETTINGS_FILE@", lua_value(data["settings_file"]))
                    .replace("@AUTO_PAGE@", "true" if mod.meta.get("settings_page", True) else "false"))
            files = {"Scripts/main.lua": main, "enabled.txt": ""}
            for rel, blob in data["files"].items():
                files["Scripts/mod/" + rel] = blob
            ctx.add_ue4ss_mod(name, files)
            ctx.note(mod.id, {"installed as": name, "files": sorted(data["files"]),
                              "settings": sorted(k for k in data["settings"] if not str(k).startswith("_"))})
            ctx.log(f"  {mod.id}: scripts/ goes in as {name}")
