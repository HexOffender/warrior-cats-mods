"""The game bridge: run Lua in the running game from wcmods (the CLI, the studio, a script).

wcmods installs a small UE4SS mod, WCModsBridge, when code mods are allowed. On the game thread it
looks for a request file a few times a second, runs the Lua in it and writes back what it printed,
what it returned and any error, as JSON:

    from wcmods.bridge import Bridge
    Bridge(cfg).run("return Game.player().level")        # -> {"ok": True, "result": [20], ...}

Requests and replies are files in the game's Saved folder (WCMods/bridge/), written whole and then
renamed, so neither side ever reads half a file. Only one request runs at a time: a client holds the
`lock` file while it waits. A request the game doesn't take within the timeout (a loading screen, the
game held still behind another window) is withdrawn, so it can't run later unasked. The bridge also
writes `status.json` once a second (the time, the level, whether there's a player, the mod menu's page),
which is how `wcmods game` tells whether the game is up. The agent controller (wcmods/agent,
docs/agent.md) drives the game for tests through this.
"""
import json
import os
import time
import uuid
from .lua import source as lua_source

NAME = "WCModsBridge"
STALE_LOCK = 60          # seconds; a lock older than this was left by a client that died
ALIVE = 5                # seconds; status.json older than this means the bridge isn't running
FOREST = "L_WorldMap_01_P"   # the level your cat plays in (Game.levelName() there)

LUA = lua_source("bridge.lua")


def where(status):
    """Where the game is, in words, from a status: "in the forest", "in the main menu", "loading" (no world
    yet), or "in <level>" for another level."""
    level = (status or {}).get("world")
    if not level:
        return "loading"
    if level == FOREST:
        return "in the forest"
    if str(level).startswith("L_MainMenu"):
        return "in the main menu"
    return f"in {level}"


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
    engine's Actor/Object ones as well). A blank expr is refused (it would be a Lua syntax error)."""
    if not str(expr or "").strip():
        raise ValueError("type an object to look at, e.g. Game.player()")
    flag = "true" if everything else "false"
    return INSPECT_LUA % (expr, flag, flag)


def folder(cfg):
    """Where requests, replies and the status go: the game's Saved folder, next to its saves."""
    return os.path.join(os.path.dirname(os.path.normpath(cfg.save_dir)), "WCMods", "bridge")


def script(cfg):
    from .sdk import lua_value
    return LUA.replace("@DIR@", lua_value(folder(cfg).replace("\\", "/")))


class BridgeError(RuntimeError):
    """The bridge couldn't run a request. `kind` says why, for each surface to word it its own way:
    "down" (no recent status: the game is closed, or runs without the bridge, or is held still), "busy"
    (another client holds the lock), "withdrawn" (no reply in time, and the request was taken back before
    the game took it) or "running" (no reply in time, though the game took the request: it's still on it)."""

    def __init__(self, message, kind="down"):
        super().__init__(message)
        self.kind = kind


class Bridge:
    def __init__(self, cfg):
        self.dir = folder(cfg)

    def status(self):
        """The bridge's last status, with "alive" set when it's recent; None when it never ran. The bridge
        replaces status.json by removing it and renaming the new one in, so a status found missing while its
        folder is there is looked for once more a moment later."""
        path = os.path.join(self.dir, "status.json")
        for attempt in (0, 1):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                data["age"] = time.time() - os.path.getmtime(path)
            except FileNotFoundError:
                if attempt == 0 and os.path.isdir(self.dir):
                    time.sleep(0.05)
                    continue
                return None
            except (OSError, ValueError):
                return None
            data["alive"] = data["age"] < ALIVE
            return data
        return None

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
            request = os.path.join(self.dir, "request.lua")
            if os.path.exists(reply_path):
                os.remove(reply_path)
            rid = uuid.uuid4().hex
            tmp = os.path.join(self.dir, "request.tmp")
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(f"--wcmods-id:{rid}\n{code}")
            os.replace(tmp, request)
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
            if self._withdraw(request, rid):
                raise BridgeError(f"no reply within {timeout:g} s (the game may be loading, or held still behind "
                                  "another window); the request was withdrawn, so it won't run later", "withdrawn")
            raise BridgeError(f"no reply within {timeout:g} s: the game took the request and is still running it",
                              "running")
        finally:
            try:
                os.remove(lock)
            except OSError:
                pass

    @staticmethod
    def _withdraw(request, rid):
        """Take back a request the game hasn't taken (the bridge removes request.lua before it runs it, so one
        still there was never started): True when it was ours and is gone now."""
        try:
            with open(request, encoding="utf-8") as f:
                first = f.readline().strip()
        except OSError:
            return False   # taken
        if first != f"--wcmods-id:{rid}":
            return False   # another client's (it can't be, while we hold the lock; left alone all the same)
        try:
            os.remove(request)
        except FileNotFoundError:
            return False   # taken this moment
        except OSError:
            return False
        return True

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
                    raise BridgeError("another wcmods command is talking to the game; try again", "busy") from None
                time.sleep(0.05)
