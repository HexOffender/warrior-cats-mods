"""The Agent: drive the running game, for tests and for looking at changes in it.

    from wcmods.agent import Agent
    agent = Agent(root)
    agent.install()                    # a test build: your mods plus the bridge (code mods on for it)
    agent.launch(world=True)           # start it through Steam and play into the forest
    agent.lua("return Game.cat():name()")
    page = agent.menu.open("Stats")    # the mod menu, read as rows
    agent.menu.set("Level", 12)
    agent.shot("stats")                # a PNG of the game's window
    agent.key("W", hold=1.5)           # walk
    agent.quit()

Everything goes through the bridge (WCModsBridge, installed when code mods are allowed) and the game's
window; see docs/agent.md.
"""
import os
import re
import time

from .. import mods as modlib, pipeline
from ..formats import save
from ..bridge import Bridge, BridgeError
from ..config import STEAM_APP_ID, Config
from ..sdk import lua_value
from . import window
from .menu import MenuDriver

WORLD = "L_WorldMap_01_P"
# A line in UE4SS.log that says a script went wrong.
ERROR_LINE = re.compile(r"\berror\b|stack traceback|attempt to (call|index|perform|compare|concatenate)", re.I)


class AgentError(RuntimeError):
    pass


class BridgeDown(AgentError):
    """The bridge didn't answer: the game isn't running, is loading, or another command holds it."""


class LuaError(AgentError):
    """The Lua ran and raised an error (the message has the game's traceback)."""


QUIT_LUA = """
ExecuteWithDelay(200, function() ExecuteInGameThread(function()
    local pc = Game.controller()
    Game.library("KismetSystemLibrary"):QuitGame(pc, pc, 0, false)
end) end)
return true
"""

SCREENS_LUA = """
local out = {}
for _, w in ipairs(Game.findAll("GuiScreenWrc")) do
    if w:IsVisible() then out[#out + 1] = Game.className(w) end
end
return out
"""

# Press a button on one of the game's own screens the way a click does.
PRESS_UI_LUA = """
local s = Game.find(%s)
if not s then return "no screen " .. %s end
local b = Game.get(s, %s)
if not Game.valid(b) then return "no button " .. %s end
Game.call(s, "OnUIPress", b)
Game.call(s, "OnUIRelease", b)
return true
"""

# Confirm on a screen that waits for any key (the splash, the cat choice).
CONFIRM_LUA = """
local s = Game.find(%s)
if not s then return false end
local pc = Game.controller()
for _, k in ipairs({ "Enter", "SpaceBar", "Gamepad_FaceButton_Bottom" }) do
    Game.call(s, "OnKeyPressed", { KeyName = FName(k) }, pc)
    Game.call(s, "OnKeyReleased", { KeyName = FName(k) }, pc)
end
Game.call(s, "OnListenCommand", 26, 0, pc)
Game.call(s, "OnListenCommand", 26, 1, pc)
return true
"""

CAT_LUA = """
local c = Game.cat()
if not c then return nil end
local l = c:location() or {}
local look = c:customization() or {}
return { name = c:name(), nameId = (look.PrefixNameId or "") .. (look.SuffixNameId or ""), level = c:level(),
         clan = c:clan(), health = c:health(), maxHealth = c:maxHealth(), stamina = c:stamina(),
         maxStamina = c:maxStamina(), xp = c:xp(), at = { l.X, l.Y, l.Z } }
"""

MOVE_LUA = """
if __agentMove then Game.cancel(__agentMove) end
local fwd, right = %s, %s
__agentMove = Game.onFrame(function()
    local pawn, pc = Game.player(), Game.controller()
    if not (pawn and pc) then return end
    local yaw = math.rad(pc:GetControlRotation().Yaw)
    pawn:AddMovementInput({ X = math.cos(yaw) * fwd - math.sin(yaw) * right,
                            Y = math.sin(yaw) * fwd + math.cos(yaw) * right, Z = 0 }, 1.0, false)
end)
return true
"""
STOP_LUA = "if __agentMove then Game.cancel(__agentMove) __agentMove = nil end return true"


def _safe(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).strip("-")[:60] or "shot"


class Agent:
    """Drives the game. `out_dir` is where pictures go (agent-output by default:
    not under build/, which every build empties); `log` gets progress."""

    def __init__(self, root, out_dir=None, log=print):
        self.root = root
        self.cfg = Config(root)
        self.bridge = Bridge(self.cfg)
        self.log = log
        self.out_dir = out_dir or os.path.join(root, "agent-output")
        self.shots = []          # every picture taken, in order
        self.output = ""         # what the last Lua printed
        self.menu = MenuDriver(self)

    @staticmethod
    def error(message):
        return AgentError(message)

    # ---------- waiting ----------
    def wait(self, fn, timeout=30, what="it", interval=0.1):
        """Call fn() until it gives something truthy, and return that; AgentError after `timeout` seconds.
        A bridge that doesn't answer for a moment (loading) just means trying again."""
        end, last = time.time() + timeout, None
        while True:
            try:
                value = fn()
            except BridgeDown as e:
                value, last = None, e
            if value:
                return value
            if time.time() > end:
                raise AgentError(f"timed out after {timeout:g} s waiting for {what}" + (f" (last: {last})" if last else ""))
            time.sleep(interval)

    def wait_lua(self, expr, timeout=30, what=None):
        """Wait until a Lua expression is truthy; returns its value."""
        return self.wait(lambda: self.lua("return " + expr), timeout, what or expr, interval=0.25)

    # ---------- the game: is it there ----------
    def _window(self):
        hwnd = window.game_window()
        if not hwnd:
            raise AgentError("the game isn't running (agent.launch())")
        return hwnd

    def status(self):
        """What the game is doing: running, its window, the bridge, the level, your cat, the mod menu."""
        pid = window.game_pid()
        hwnd = window.game_window(pid) if pid else None
        st = (self.bridge.status() or {}) if pid else {}
        alive = bool(st.get("alive"))
        out = {"running": bool(pid), "pid": pid, "crash_reporter": bool(window.crash_reporters()),
               "window": list(window.client_size(hwnd)) if hwnd else None,
               "foreground": window.is_foreground(hwnd) if hwnd else False,
               "minimized": window.is_minimized(hwnd) if hwnd else False,
               "bridge": alive, "world": st.get("world") if alive else None,
               "player": bool(st.get("player")) if alive else False,
               "menu": bool(st.get("menu")) if alive else False, "page": st.get("page") if alive else None}
        out["in_world"] = alive and out["world"] == WORLD and out["player"]
        return out

    def crashed(self):
        """True when the game's crash reporter is up."""
        return bool(window.crash_reporters())

    def close_crash_reporter(self):
        """Close crash reporters without sending anything; returns how many there were."""
        pids = window.crash_reporters()
        for pid in pids:
            window.kill(pid)
        return len(pids)

    # ---------- starting and stopping ----------
    def launch(self, world=False, cat=1, timeout=180):
        """Start the game through Steam (unless it's running) and wait for the bridge; with world=True,
        also play into the forest with save slot `cat`. Returns status()."""
        if window.crash_reporters():
            raise AgentError("a crash reporter is open from an earlier run; agent.close_crash_reporter() first")
        if not window.game_pid():
            started = time.time()
            self.log("starting the game through Steam...")
            os.startfile(f"steam://rungameid/{STEAM_APP_ID}")
            self.wait(window.game_pid, 90, "the game to start")

            def fresh():
                st = self.bridge.status()
                return st and st["alive"] and time.time() - st["age"] > started
            self.wait(fresh, timeout, "the bridge to report in (installed with code mods? agent install)", interval=1)
        elif not self.status()["bridge"]:
            raise AgentError("the game is running without the bridge: quit it, then `agent install` and launch")
        if world:
            self.enter(cat=cat, timeout=timeout)
        return self.status()

    def screens(self):
        """The game's own screens that show now (WBP_GuiScreenMainMenu_C, ...)."""
        return self.lua(SCREENS_LUA) or []

    def press_ui(self, screen, button):
        """Click a button on one of the game's screens: press_ui("WBP_GuiScreenMainMenu_C", "mcGuiButtonProphecy")."""
        q = lua_value
        r = self.lua(PRESS_UI_LUA % (q(screen), q(screen), q(button), q(button)))
        if r is not True:
            raise AgentError(str(r))

    def enter(self, cat=1, timeout=240):
        """From the splash or main menu, play into the forest with save slot `cat` (1 to 3). Returns the
        seconds it took."""
        t0, step = time.time(), None
        while time.time() - t0 < timeout:
            st = self.status()
            if not st["running"]:
                raise AgentError("the game closed")
            if st["in_world"]:
                self.log(f"in the forest after {time.time() - t0:.0f} s")
                return time.time() - t0
            if not st["bridge"]:
                time.sleep(1)
                continue
            try:
                shown = ",".join(self.screens())
                if "SelectYourCat" in shown and step != "cat":
                    self.press_ui("WBP_GuiScreenSelectYourCat_C", f"mcGuiButtonCat{int(cat)}")
                    time.sleep(2)
                    self.lua(CONFIRM_LUA % lua_value("WBP_GuiScreenSelectYourCat_C"))
                    step = "cat"
                elif "MainMenu" in shown and step != "menu":
                    self.press_ui("WBP_GuiScreenMainMenu_C", "mcGuiButtonProphecy")
                    step = "menu"
                elif "Splash" in shown and step != "splash":
                    time.sleep(3)
                    self.lua(CONFIRM_LUA % lua_value("WBP_GuiScreenSplash_C"))
                    step = "splash"
            except BridgeDown:
                pass
            time.sleep(2)
        raise AgentError(f"didn't reach the forest in {timeout} s (screens: {self.screens()})")

    def quit(self, timeout=60, force=False):
        """Close the game the way its menu does; with force=True, end it if it won't close."""
        pid = window.game_pid()
        if not pid:
            return
        try:
            self.lua(QUIT_LUA, timeout=10)
        except AgentError as e:
            if not force:
                raise AgentError(f"couldn't ask the game to quit ({e}); quit(force=True) / --force ends it") from None
        try:
            self.wait(lambda: not window.game_pid(), timeout, "the game to close", interval=0.5)
        except AgentError:
            if not force:
                raise
            self.log("the game didn't close; ending it")
            window.kill(pid)
            self.wait(lambda: not window.game_pid(), 30, "the game to end", interval=0.5)

    def restart(self, world=True, cat=1):
        self.quit()
        return self.launch(world=world, cat=cat)

    # ---------- installing ----------
    def install(self, extra=(), code_mods=True, force=False):
        """Build and install your enabled mods for a test: code mods allowed for this build (so the bridge
        goes in, and every enabled mod's code runs, downloaded ones too), plus the mod folders in `extra`
        (e.g. ../wcmods-examples/game-tweaks), on for this build. wcmods.json keeps its settings; the install updates
        its record of what's installed. The game must be closed. Returns the build's manifest."""
        if window.game_pid():
            raise AgentError("the game is running; agent.quit() first (installing replaces files it has open)")
        cfg = Config(self.root)
        if code_mods:
            cfg.data["allow_code_mods"] = True
        found = modlib.discover(os.path.join(self.root, "mods"))
        for path in extra:
            m = modlib.Mod(os.path.abspath(os.path.join(self.root, path)))
            m.enabled = True
            found = [x for x in found if x.id != m.id] + [m]
        found.sort(key=lambda m: (m.priority, m.id))
        build_dir = os.path.join(self.root, "build", "agent-install")
        manifest = pipeline.build(cfg, found, build_dir, log=lambda m: None)
        pipeline.install(cfg, build_dir, os.path.join(self.root, "backups"), log=lambda m: None, force=force)
        return manifest

    def install_normal(self, force=False):
        """Install the way `wcmods install` does (wcmods.json as it is): what to finish a test session with."""
        if window.game_pid():
            raise AgentError("the game is running; agent.quit() first")
        cfg = Config(self.root)
        build_dir = os.path.join(self.root, "build")
        manifest = pipeline.build(cfg, modlib.discover(os.path.join(self.root, "mods")), build_dir, log=lambda m: None)
        pipeline.install(cfg, build_dir, os.path.join(self.root, "backups"), log=lambda m: None, force=force)
        cfg.save()
        return manifest

    def backup_save(self, reason="agent"):
        """Copy the save aside (backups/<time>-<reason>); returns the backup's name for restore_save."""
        dest, _ = save.backup(self.cfg.save_dir, os.path.join(self.root, "backups"), reason)
        return os.path.basename(dest)

    def restore_save(self, name):
        """Put a backed-up save back (the game must be closed: it rewrites the save as it plays)."""
        if window.game_pid():
            raise AgentError("the game is running; agent.quit() first")
        backups = os.path.join(self.root, "backups")
        save.backup(self.cfg.save_dir, backups, "before-restore")
        return save.restore(backups, name, self.cfg.save_dir)

    # ---------- Lua ----------
    def lua(self, code, timeout=15):
        """Run Lua in the game (WCModsGame is `Game`; globals stay for the next call). Returns what it
        returns: one value, a list for several, None for none."""
        try:
            reply = self.bridge.run(code, timeout=timeout)
        except BridgeError as e:
            raise BridgeDown(str(e)) from None
        self.output = reply.get("output") or ""
        if not reply.get("ok"):
            raise LuaError(reply.get("error") or "the Lua failed")
        values = [None if v == "nil" else v for v in (reply.get("result") or [])]
        return values[0] if len(values) == 1 else (values or None)

    def compile(self, source, name="chunk"):
        """Check Lua compiles, with the game's own Lua 5.4, without running it: None, or the error."""
        r = self.lua(f"local f, err = load({lua_value(source)}, {lua_value('=' + name)}, 't') return f and true or err")
        return None if r is True else str(r)

    # ---------- your cat and the world ----------
    def cat(self):
        """Your cat: name (and nameId, the string key it comes from), level, clan, health, stamina, xp, at
        [x, y, z]; None outside the world."""
        return self.lua(CAT_LUA)

    def location(self):
        c = self.cat()
        return c["at"] if c else None

    def teleport(self, x, y, z):
        r = self.lua(f"return Game.cat():teleport({float(x)}, {float(y)}, {float(z)})")
        first = r[0] if isinstance(r, list) and r else r
        if first is False:
            raise AgentError("couldn't teleport" + (f": {r[1]}" if isinstance(r, list) and len(r) > 1 else ""))

    def turn(self, degrees):
        """Turn the camera (and so which way is forward) by `degrees` to the right."""
        self.lua(f"local pc = Game.controller() local r = pc:GetControlRotation() "
                 f"pc:SetControlRotation({{ Pitch = r.Pitch, Yaw = r.Yaw + {float(degrees)}, Roll = r.Roll }}) return true")

    def move(self, forward=1.0, right=0.0, seconds=1.0):
        """Walk, relative to the camera (forward/right from -1 to 1), for `seconds`; works whatever window
        is in front. Returns how far the cat went."""
        before = self.location()
        self.lua(MOVE_LUA % (float(forward), float(right)))
        try:
            time.sleep(seconds)
        finally:
            self.lua(STOP_LUA)
        after = self.location()
        if not (before and after):
            return 0.0
        return sum((a - b) ** 2 for a, b in zip(after, before)) ** 0.5

    def pause(self, on=True):
        self.lua(f"Game.library('GameplayStatics'):SetGamePaused(Game.world(), {'true' if on else 'false'}) return true")

    def speed(self, factor=1.0):
        """The game's speed (time dilation): 2 runs it twice as fast, 1 is normal."""
        self.lua(f"Game.library('GameplayStatics'):SetGlobalTimeDilation(Game.world(), {float(factor)}) return true")

    # ---------- keys ----------
    def key(self, name, hold=0.08):
        """Press a key for the game's own controls (W walks, SpaceBar pounces, E interacts, Enter pauses),
        held for `hold` seconds. Posted to its window, so it works with other windows in front."""
        hwnd, vk = self._window(), window.vk_of(name)
        window.post_key(hwnd, vk, True)
        try:
            time.sleep(hold)
        finally:
            window.post_key(hwnd, vk, False)

    def keys(self, *names, hold=0.08):
        """Hold several keys together (keys("W", "LeftShift", hold=2) runs)."""
        hwnd, vks = self._window(), [window.vk_of(n) for n in names]
        for vk in vks:
            window.post_key(hwnd, vk, True)
        try:
            time.sleep(hold)
        finally:
            for vk in reversed(vks):
                window.post_key(hwnd, vk, False)

    def hotkey(self, name, modifiers=(), focus=False):
        """Press a key the way UE4SS's key binds see it (the mod menu's Insert, a script's Game.onKey).
        They read the real keyboard, so this presses it for real: the game must be in front. focus=True
        brings it there first."""
        hwnd = self._window()
        if not window.is_foreground(hwnd):
            if not focus:
                raise AgentError("the game isn't in front; UE4SS key binds need it there (pass focus=True / --focus)")
            if not window.bring_to_front(hwnd):
                raise AgentError("Windows wouldn't put the game in front")
        vks = [window.vk_of(m) for m in modifiers] + [window.vk_of(name)]
        for vk in vks:
            window.send_key(vk, True)
            time.sleep(0.03)
        time.sleep(0.1)
        for vk in reversed(vks):
            window.send_key(vk, False)
            time.sleep(0.03)

    # ---------- pictures ----------
    def picture(self, menu=False, region=None):
        """The game's window now, as an Image (menu=True: just the mod menu's window)."""
        hwnd = self._window()
        if window.is_minimized(hwnd):
            raise AgentError("the game is minimised; restore it to take a picture")
        img = window.capture(hwnd)
        if region is None and menu:
            region = self.menu.region()
            if not region:
                raise AgentError("the mod menu isn't open")
        return img.crop(*region) if region else img

    def shot(self, name=None, scale=1.0, menu=False, region=None, path=None):
        """Save a picture of the game's window as a PNG and return its path: in out_dir/shots, numbered
        in order and named after `name`, unless `path` says where."""
        img = self.picture(menu=menu, region=region)
        if scale < 1:
            img = img.scaled(scale)
        if not path:
            folder = os.path.join(self.out_dir, "shots")
            os.makedirs(folder, exist_ok=True)
            taken = [int(f[:3]) for f in os.listdir(folder) if f[:3].isdigit()]
            path = os.path.join(folder, f"{max(taken, default=0) + 1:03d}-{_safe(name or 'shot')}.png")
        img.save(path)
        self.shots.append(path)
        return path

    # ---------- the log ----------
    def log_path(self):
        return os.path.join(os.path.dirname(self.cfg.ue4ss_mods_dir), "UE4SS.log") if self.cfg.ue4ss_mods_dir else None

    def log_mark(self):
        """Where UE4SS.log ends now; log_since(mark) gives what's written after it."""
        try:
            return os.path.getsize(self.log_path())
        except (OSError, TypeError):
            return 0

    def log_since(self, mark=0):
        path = self.log_path()
        try:
            with open(path, "rb") as f:
                size = f.seek(0, 2)
                f.seek(mark if mark <= size else 0)   # a new game session starts the log again
                data = f.read()
        except (OSError, TypeError):
            return []
        return [line for line in data.decode("utf-8", "replace").splitlines() if line.strip()]

    def errors_since(self, mark=0):
        """Lines after `mark` that say a script went wrong."""
        return [line for line in self.log_since(mark) if ERROR_LINE.search(line)]
