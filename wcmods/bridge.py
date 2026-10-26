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
from .lua import source as lua_source

NAME = "WCModsBridge"
STALE_LOCK = 60          # seconds; a lock older than this was left by a client that died
ALIVE = 5                # seconds; status.json older than this means the bridge isn't running

LUA = lua_source("bridge.lua")


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
