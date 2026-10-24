"""The game bridge: run Lua in the running game from wcmods (the CLI, the studio, a script).

wcmods installs a small UE4SS mod, WCModsBridge, when code mods are allowed. On the game thread it
looks for a request file a few times a second, runs the Lua in it and writes back what it printed,
what it returned and any error, as JSON:

    from wcmods.bridge import Bridge
    Bridge(cfg).run("return Game.player().level")        # -> {"ok": True, "result": [20], ...}

Requests and replies are files in the game's Saved folder (WCMods/bridge/), written whole and then
renamed, so neither side ever reads half a file. Only one request runs at a time: a client holds the
`lock` file while it waits. The bridge also writes `status.json` once a second (the time, the level,
whether there's a player, the mod menu's page), which is how `wcmods game` tells whether the game is up.
The agent controller (wcmods/agent, docs/agent.md) drives the game for tests through this.
"""
import json
import os
import time
import uuid

NAME = "WCModsBridge"
STALE_LOCK = 60          # seconds; a lock older than this was left by a client that died
ALIVE = 5                # seconds; status.json older than this means the bridge isn't running

LUA = r'''-- WCModsBridge: runs Lua sent from wcmods (`wcmods lua`, the studio's console) in the game. Written by
-- wcmods on every install when code mods are allowed; see docs/scripting.md, "The game bridge".
local DIR = @DIR@
local REQUEST, REPLY, STATUS = DIR .. "/request.lua", DIR .. "/reply.json", DIR .. "/status.json"
local function log(fmt, ...) print(string.format("[WCModsBridge] " .. fmt .. "\n", ...)) end

local okGame, Game = pcall(require, "WCModsGame")
if not okGame then
    log("WCModsGame didn't load: %s", tostring(Game))
    Game = nil
end

-- ---------- JSON out ----------
local function describe(v)
    -- UE4SS hands back objects, names, texts and structs as userdata. Calling into an object that isn't
    -- there crashes the game, so that's checked first.
    local okV, alive = pcall(function() return v:IsValid() end)
    if okV and alive == false then return "<gone>" end
    local ok, s = pcall(function() return v:GetFullName() end)
    if ok and type(s) == "string" then return "<" .. s .. ">" end
    ok, s = pcall(function() return v:ToString() end)
    if ok and type(s) == "string" then return s end
    return tostring(v)
end

local function encode(v, depth, seen)
    local t = type(v)
    if v == nil then return "null" end
    if t == "boolean" then return v and "true" or "false" end
    if t == "number" then
        if v ~= v or v == math.huge or v == -math.huge then return '"' .. tostring(v) .. '"' end
        if math.type(v) == "integer" then return tostring(v) end
        return string.format("%.17g", v)
    end
    if t == "string" then
        return '"' .. v:gsub('[%c"\\]', function(c)
            local map = { ['"'] = '\\"', ["\\"] = "\\\\", ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }
            return map[c] or string.format("\\u%04x", c:byte())
        end) .. '"'
    end
    if t == "table" then
        depth = depth or 0
        seen = seen or {}
        if seen[v] then return '"<cycle>"' end
        if depth > 6 then return '"<table>"' end
        seen[v] = true
        local n, max = 0, 0
        for k in pairs(v) do
            n = n + 1
            if math.type(k) == "integer" and k > 0 and k > max then max = k end
        end
        local out = {}
        if n > 0 and max == n then
            for i = 1, n do out[i] = encode(v[i], depth + 1, seen) end
            seen[v] = nil
            return "[" .. table.concat(out, ",") .. "]"
        end
        local keys = {}
        for k in pairs(v) do keys[#keys + 1] = k end
        table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
        for _, k in ipairs(keys) do
            out[#out + 1] = encode(tostring(k)) .. ":" .. encode(v[k], depth + 1, seen)
        end
        seen[v] = nil
        return "{" .. table.concat(out, ",") .. "}"
    end
    return encode(describe(v))
end

-- ---------- files ----------
local function readAll(path)
    local f = io.open(path, "rb")
    if not f then return nil end
    local s = f:read("a")
    f:close()
    return s
end

local function writeWhole(path, text)
    local tmp = path .. ".tmp"
    local f = io.open(tmp, "wb")
    if not f then return false end
    f:write(text)
    f:close()
    os.remove(path)
    return os.rename(tmp, path)
end

-- ---------- running a request ----------
-- One environment for every request, so a global set by one (x = 5) is there for the next, as in a
-- console. print goes to the reply.
local lines = {}
local function say(...)
    local parts = table.pack(...)
    for i = 1, parts.n do parts[i] = type(parts[i]) == "string" and parts[i] or describe(parts[i]) end
    lines[#lines + 1] = table.concat(parts, "\t", 1, parts.n)
end
local env = setmetatable({ print = say, Game = Game }, { __index = _G })

local function run(code)
    lines = {}
    -- An expression is returned as it is ("Game.player()"); anything else runs as a chunk.
    local fn = load("return " .. code, "=wcmods", "t", env)
    local err
    if not fn then fn, err = load(code, "=wcmods", "t", env) end
    if not fn then return { ok = false, error = err, output = "" } end
    local started = os.clock()
    local res = table.pack(xpcall(fn, debug.traceback))
    local reply = { ok = res[1], ms = math.floor((os.clock() - started) * 1000 + 0.5),
                    output = table.concat(lines, "\n") }
    if res[1] then
        local values = {}
        for i = 2, res.n do values[i - 1] = res[i] == nil and "nil" or res[i] end
        reply.result = values
    else
        reply.error = tostring(res[2])
    end
    return reply
end

local function poll()
    local text = readAll(REQUEST)
    if not text then return end
    os.remove(REQUEST)
    local id = text:match("^%-%-wcmods%-id:([%w%-]+)") or ""
    local reply = run(text)
    reply.id = id
    local ok, json = pcall(encode, reply)
    if not ok then json = encode({ id = id, ok = false, error = "couldn't write the reply: " .. tostring(json) }) end
    writeWhole(REPLY, json)
end

local function status()
    local s = { time = os.time(), world = nil, player = false }
    pcall(function()
        local engine = FindFirstOf("GameEngine")
        local world = engine and engine.GameViewport and engine.GameViewport.World
        if world and world:IsValid() then s.world = world:GetFName():ToString() end
    end)
    if Game then pcall(function() s.player = Game.player() ~= nil end) end
    -- The mod menu: whether it's open and on which page (wcmods agent status).
    pcall(function()
        s.menu = ModRef:GetSharedVariable("WCModsMenu.open") == true
        local page = ModRef:GetSharedVariable("WCModsMenu.page")
        if type(page) == "string" and page ~= "" then s.page = page end
    end)
    writeWhole(STATUS, encode(s))
end

local nextPoll, nextStatus = 0, 0
local function frame()
    local now = os.clock()
    if now >= nextPoll then
        nextPoll = now + 0.1
        local ok, err = pcall(poll)
        if not ok then log("error: %s", tostring(err)) end
    end
    if now >= nextStatus then
        nextStatus = now + 1
        pcall(status)
    end
end

if LoopInGameThreadAfterFrames == nil or not pcall(LoopInGameThreadAfterFrames, 1, frame) then
    LoopAsync(16, function()
        ExecuteInGameThread(frame)
        return false
    end)
end
log("listening in %s", DIR)
'''


# What `wcmods inspect` and the studio's console ask for: an object's classes, properties and functions.
INSPECT_LUA = """
local o = (%s)
if not Game.valid(o) then return { error = "not an object: " .. Game.show(o) } end
local out = { name = Game.fullName(o), parents = Game.parents(o), props = {}, funcs = {} }
for _, p in ipairs(Game.properties(o, %s)) do
    out.props[#out.props + 1] = { owner = p.owner, name = p.name, type = p.type, value = Game.show(p.value) }
end
for _, f in ipairs(Game.functions(o, %s)) do
    local ps = {}
    for _, p in ipairs(f.params) do ps[#ps + 1] = p.name .. ": " .. p.type .. (p.out and " (out)" or "") end
    out.funcs[#out.funcs + 1] = { owner = f.owner, name = f.name, params = ps, returns = f.returns }
end
return out
"""


def inspect_code(expr, everything=False):
    """Lua that describes the object `expr` evaluates to (its own members, or with everything=True the
    engine's Actor/Object ones as well)."""
    flag = "true" if everything else "false"
    return INSPECT_LUA % (expr, flag, flag)


def folder(cfg):
    """Where requests, replies and the status go: the game's Saved folder, next to its saves."""
    return os.path.join(os.path.dirname(os.path.normpath(cfg.save_dir)), "WCMods", "bridge")


def script(cfg):
    from .sdk import lua_value
    return LUA.replace("@DIR@", lua_value(folder(cfg).replace("\\", "/")))


class BridgeError(RuntimeError):
    pass


class Bridge:
    def __init__(self, cfg):
        self.dir = folder(cfg)

    def status(self):
        """The bridge's last status, with "alive" set when it's recent; None when it never ran."""
        path = os.path.join(self.dir, "status.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            data["age"] = time.time() - os.path.getmtime(path)
        except (OSError, ValueError):
            return None
        data["alive"] = data["age"] < ALIVE
        return data

    def run(self, code, timeout=15):
        """Run Lua in the game; returns {"ok", "result" (a list), "output", "error", "ms"}."""
        os.makedirs(self.dir, exist_ok=True)
        st = self.status()
        if not st or not st["alive"]:
            raise BridgeError("the game isn't running with the bridge (start it after `wcmods install` with "
                              "\"allow_code_mods\": true)")
        lock = os.path.join(self.dir, "lock")
        self._take(lock, timeout)
        try:
            reply_path = os.path.join(self.dir, "reply.json")
            if os.path.exists(reply_path):
                os.remove(reply_path)
            rid = uuid.uuid4().hex
            tmp = os.path.join(self.dir, "request.tmp")
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(f"--wcmods-id:{rid}\n{code}")
            os.replace(tmp, os.path.join(self.dir, "request.lua"))
            end = time.time() + timeout
            while time.time() < end:
                if os.path.exists(reply_path):
                    try:
                        with open(reply_path, encoding="utf-8") as f:
                            reply = json.load(f)
                    except (OSError, ValueError):
                        time.sleep(0.05)
                        continue
                    if reply.get("id") == rid:
                        os.remove(reply_path)
                        return reply
                time.sleep(0.05)
            raise BridgeError(f"no reply within {timeout} s (the game may be loading, or the code is still running)")
        finally:
            try:
                os.remove(lock)
            except OSError:
                pass

    @staticmethod
    def _take(lock, timeout):
        end = time.time() + timeout
        while True:
            try:
                os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(lock) > STALE_LOCK:
                        os.remove(lock)
                        continue
                except OSError:
                    continue
                if time.time() > end:
                    raise BridgeError("another wcmods command is talking to the game; try again") from None
                time.sleep(0.05)
