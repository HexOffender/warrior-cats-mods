"""The rest of the world from Lua, part one (docs/scripting.md "The world, more"; the Lua plan's step 7): console
commands, the save's hash, the sky's presets held, the game's sounds and music, its own animations, visual effects,
movement, your cat's speeds and its scent sense."""
import time

SKY = ("local sky = Game.sky.actor() local f = sky:GetExponentialHeightFog() "
       "local l = sky:GetDirectionLightComponent() return { fog = f.FogDensity, light = l.Intensity }")


def test_lua_sky_held(agent):
    """The presets by name (Night, NeutralDay, the clans'...) and their table (DT_SkyBoxParams, Night's row in it); Night
    put on and held: 4 s later (the game alone fades back to the area's within about 5) the fog and the sun are still
    what they were just after it went on (as C++'s test_sky_presets checks); let go, nothing held. A name the enum
    hasn't got is refused."""
    got = agent.lua("""
        local presets = Game.sky.presets()
        local t = Game.sky.table()
        local night = Game.tables.row(t, "Night")
        return { presets = presets, table = t and t:GetFName():ToString(), nightFog = night and night.FogDensity,
                 bad = Game.sky.set("NoSuchPreset"), set = Game.sky.set("Night"), held = Game.sky.held() }""")
    try:
        assert {"Night", "NeutralDay", "ThunderClan", "MoonPool"} <= set(got["presets"]), got["presets"]
        assert got["table"] == "DT_SkyBoxParams" and got["nightFog"] is not None, got
        assert got["bad"] is False and got["set"] is True and got["held"] == "Night", got
        time.sleep(0.5)
        night = agent.lua(SKY)
        time.sleep(4)
        now = agent.lua(SKY)
        assert all(abs(now[k] - night[k]) <= 1e-4 * max(1.0, abs(night[k])) for k in ("fog", "light")), (now, night)
    finally:
        assert agent.lua("return { Game.sky.followArea(), Game.sky.held() == nil }") == [True, True]


def test_lua_sounds_and_music(agent):
    """The game's sounds by id (about 390, ui_select among them), one's sound and length; played heard everywhere (a menu
    sound) and from a place (a cat's step); muted (its own volume 0) and given back; every sound paused and going on again; a track played on the
    music's component (mus_camp, then the music says so) and stopped; what isn't there refused."""
    got = agent.lua("""
        local ids = Game.sounds.ids()
        local has = false
        for _, id in ipairs(ids) do if id == "ui_select" then has = true end end
        local s = Game.sounds.of("ui_select")
        -- (a menu sound played at a place gives no component: it isn't one heard from somewhere; a step is)
        local c1, c2 = Game.sounds.play("ui_select"), Game.sounds.play("cat_step", Game.cat():location())
        local out = { ids = #ids, has = has, sound = s and Game.className(s), duration = Game.sounds.duration("ui_select"),
                      played = c1 ~= nil and c2 ~= nil, none = Game.sounds.play("no_such_sound") == nil and Game.sounds.of("no_such_sound") == nil,
                      badVolume = Game.sounds.setVolume("Loudness", 1) }
        local path = Game.isA(s, "SoundCue") and "VolumeMultiplier" or "Volume"
        out.volume = Game.get(s, path)
        out.mute = Game.sounds.mute("ui_select")
        out.muted = Game.get(s, path)
        out.restore = Game.sounds.restore("ui_select")
        out.restored = Game.get(s, path)
        out.again = Game.sounds.restore("ui_select")
        -- two ids muted on one sound: it comes back only once both are restored, at the game's volume
        local other
        for _, id in ipairs(ids) do
            if id ~= "ui_select" and Game.sounds.of(id) and Game.sounds.of(id):GetAddress() == s:GetAddress() then other = id end
        end
        if other then
            Game.sounds.mute("ui_select") Game.sounds.mute(other)
            Game.sounds.restore("ui_select")
            out.shareStill = Game.get(s, path)
            Game.sounds.restore(other)
            out.shareBack = Game.get(s, path)
        end
        out.noAt = Game.effects.game("Buff") == nil
        out.pause = Game.sounds.pause(true)
        out.paused = Game.sounds.paused()
        Game.sounds.pause(false)
        out.unpaused = Game.sounds.paused()
        Game.sounds.stop(c1) Game.sounds.stop(c2)
        return out""")
    assert got["ids"] > 300 and got["has"] is True and got["sound"] and got["duration"] and got["duration"] > 0, got
    assert got["played"] is True and got["none"] is True and got["badVolume"] is False, got
    assert got["mute"] is True and got["muted"] == 0 and got["restore"] is True and got["restored"] == got["volume"] and got["again"] is False, got
    assert (got["pause"], got["paused"], got["unpaused"]) == (True, True, False), got
    assert got.get("shareStill", 0) == 0 and got.get("shareBack", got["volume"]) == got["volume"] and got["noAt"] is True, got
    try:
        assert agent.lua('return Game.music.play("mus_camp")') is True
        time.sleep(1)
        now = agent.lua("local m = Game.music.now() return m and { id = m.id, sound = m.sound }")
        assert now and now["id"] == "mus_camp", now
        assert agent.lua('return Game.music.play("no_such_track")') is False
    finally:
        agent.lua("Game.music.stop(0) return true")


def test_lua_animations_effects_movement(agent):
    """The game's own Meow played on your cat (a montage playing); the game's effects by name (Buff, Poisoned...), one
    played at your cat (playing) and stopped, a system that isn't there refused; your cat's movement (walking, its jump
    420) and its jump changed and put back, its walking speed refused (the game sets it every frame); its speeds (walk
    175, run 390), run set to 700 and put back; the scent sense coming on."""
    got = agent.lua("""
        local me = Game.cat()
        local m = me:playMontage("Animation.Exploration.Meow")
        local out = { montage = m ~= nil, playing = me:montagePlaying(), noRow = me:playMontage("Animation.No.Such") == nil }
        local names = Game.effects.names()
        out.names = names
        local fx = Game.effects.game("Buff", me:location())
        out.fx = fx ~= nil and fx:playing()
        if fx then fx:stop() end
        out.fxStopped = fx ~= nil and not fx:playing()
        out.noFx = Game.effects.game("NoSuchEffect", me:location()) == nil and Game.effects.spawn("/Game/No/Such.Such", me:location()) == nil
        local mv = me:movement()
        out.mode, out.jump = mv.mode, mv.jumpSpeed
        out.setJump = me:setJumpSpeed(700)
        out.jumpNow = me:movement().jumpSpeed
        me:setJumpSpeed(mv.jumpSpeed)
        out.walkRefused = me:setWalkSpeed(500)
        local sp = Game.speeds()
        out.walk, out.run = sp.walk, sp.run
        out.setRun = Game.setSpeeds({ run = 700 })
        out.runNow = Game.speeds().run
        out.badSpeed = Game.setSpeeds({ sprint = 900 })
        out.reset = Game.resetSpeeds()
        out.runBack = Game.speeds().run
        return out""")
    assert got["montage"] is True and got["playing"] is True and got["noRow"] is True, got
    assert {"Buff", "Debuff", "Poisoned"} <= set(got["names"]), got["names"]
    assert got["fx"] is True and got["fxStopped"] is True and got["noFx"] is True, got
    assert got["mode"] == "MOVE_Walking" and got["jump"] > 0 and got["setJump"] is True and got["jumpNow"] == 700, got
    assert got["walkRefused"] is False, got
    assert (got["walk"], got["run"]) == (175, 390) and got["setRun"] is True and got["runNow"] == 700, got
    assert got["badSpeed"] is False and got["reset"] is True and got["runBack"] == 390, got
    assert agent.lua("return Game.useSense()") is True
    agent.wait(lambda: (agent.lua("return Game.sense()") or 0) > 0, 4, "the scent sense to come on")


def test_lua_console_and_save_hash(agent):
    """A console command run (the engine's own command, harmless here: a stat shown and hidden again); the save's hash, a
    number, changing when the game saves."""
    assert agent.lua('return Game.console("stat unit")') is True
    assert agent.lua('return Game.console("stat unit")') is True
    assert agent.lua('return Game.console("")') is False
    before = agent.lua("return Game.save.hash()")
    assert isinstance(before, (int, float)), before
    agent.lua('Game.save.write("WCModsTest") return true')
    agent.wait(lambda: agent.lua("return Game.save.hash()") != before, 5, "the save's hash to change")
