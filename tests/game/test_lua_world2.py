"""The rest of the world from Lua, part two (docs/scripting.md "Places, photo mode, the camera, dens and looks"; the
Lua plan's step 7): the places your cat can travel to, the travel map opened at one, photo mode on and off, the
exploration camera's settings, the clans' dens and their hotspots, cats' looks, the accessories and the clan's cats.
Your cat goes back to its spot after each."""
import time

HOME = "local l = Game.cat():location() WCMODS_HOME = { l.X, l.Y, l.Z } return true"
BACK = "if WCMODS_HOME then Game.cat():teleport(WCMODS_HOME[1], WCMODS_HOME[2], WCMODS_HOME[3]) end return true"


def _no_screens(agent):
    for _ in range(6):
        shown = agent.lua("return Game.screens()") or []
        if not shown:
            return
        agent.lua("for _, c in ipairs({ 'GuiPopupWorldMap', 'GuiPopupPhotoMode', 'GuiScreenPause' }) do "
                  "local s = Game.screen(c) if s then Game.close(s) end end return true")
        time.sleep(1.2)


def test_lua_places_and_the_travel_map(agent):
    """The checkpoints (some open at the start, your cat's unlocked ones from the save); travel to an unlocked one puts
    your cat there; standing at it, Interact opens the world map in travel mode (Game.screen sees it), closed by
    Game.close (Back, again while it's up: it took no notice of the first); a locked or made-up place refused."""
    agent.lua(HOME)
    try:
        got = agent.lua("""
            local all = Game.places.list()
            local open, locked
            for _, p in ipairs(all) do
                if p.unlocked and not open then open = p end
                if not p.unlocked and not locked then locked = p end
            end
            WCMODS_PLACE = open
            return { count = #all, open = open and open.tag, zone = open and open.zone,
                     lockedRefused = locked == nil or Game.places.travel(locked) == false,
                     madeUp = Game.places.travel({ tag = "x" }) == false }""")
        assert got["count"] >= 3 and got["open"], got
        assert got["lockedRefused"] is True and got["madeUp"] is True, got
        assert agent.lua("return Game.places.travel(WCMODS_PLACE)") is True
        time.sleep(1.5)
        off = agent.lua("local l, p = Game.cat():location(), WCMODS_PLACE.at return math.sqrt((l.X - p.X) ^ 2 + (l.Y - p.Y) ^ 2)")
        assert off < 150, off
        assert agent.lua("return Game.places.openTravelMap()") is True
        agent.wait(lambda: agent.lua("return Game.screen('GuiPopupWorldMap') ~= nil"), 5, "the travel map")
        assert agent.lua("return Game.close(Game.screen('GuiPopupWorldMap'))") is True
        agent.wait(lambda: agent.lua("return Game.screen('GuiPopupWorldMap') == nil"), 6, "the travel map to close")
    finally:
        _no_screens(agent)
        agent.lua(BACK)


def test_lua_camera_settings(agent):
    """The camera following your cat (some distance off, a field of view) and its settings (distance 113, fov 90, the
    turning 55 and 120); its distance set to 300: shown farther a moment later; an unknown setting refused; put back."""
    got = agent.lua("""
        local v, s = Game.camera.view(), Game.camera.settings()
        return { distance = v and v.distance, fov = v and v.fov, settings = s, bad = Game.camera.set({ zoom = 2 }) }""")
    s = got["settings"]
    assert got["distance"] and got["distance"] > 20 and got["fov"] and got["fov"] > 0, got
    assert round(s["distance"]) == 113 and round(s["fov"]) == 90 and round(s["turnYaw"]) == 55 and round(s["turnPitch"]) == 120, s
    assert got["bad"] is False, got
    try:
        assert agent.lua("return Game.camera.set({ distance = 300 })") is True
        time.sleep(2)
        far = agent.lua("return Game.camera.view().distance")
        assert far > got["distance"] + 100, (far, got["distance"])
    finally:
        assert agent.lua("return Game.camera.reset()") is True
    assert round(agent.lua("return Game.camera.settings().distance")) == 113


def test_lua_dens(agent):
    """The decorations (60, with names), every clan's dens (each clan's rank dens and shared ones) and your cat's clan's;
    one den's hotspots (tag, size, rank); your cat taken into it, then back."""
    agent.lua(HOME)
    try:
        got = agent.lua("""
            local decorations = Game.dens.decorations()
            local named = 0
            for _, d in ipairs(decorations) do if d.name and d.name ~= "" then named = named + 1 end end
            local all = Game.dens.list()
            local clans = {}
            for _, d in ipairs(all) do clans[d.clan] = true end
            local mine = Game.dens.list(Game.cat():clan())
            local den = mine[1]
            WCMODS_DEN = den
            local hs = den and Game.dens.hotspots(den) or {}
            local h = hs[1]
            return { decorations = #decorations, named = named, dens = #all, clans = clans, mine = #mine,
                     hotspots = #hs, h = h and { tag = h.tag, size = h.size, rank = h.rank, status = h.savedStatus },
                     again = h and Game.dens.hotspot(h.actor).tag }""")
        assert got["decorations"] == 60 and got["named"] >= 50, got
        assert got["dens"] >= 4 and len(got["clans"]) == 4 and got["mine"] >= 1, got
        h = got["h"]
        assert got["hotspots"] >= 1 and h["tag"].startswith("Gameplay.Den.Hotspot") and h["size"] and got["again"] == h["tag"], got
        assert agent.lua("return Game.dens.enter(WCMODS_DEN)") is True
        time.sleep(1)
        off = agent.lua("local l, p = Game.cat():location(), WCMODS_DEN.inside return math.sqrt((l.X - p.X) ^ 2 + (l.Y - p.Y) ^ 2)")
        assert off < 150, off
    finally:
        agent.lua(BACK)


def test_lua_looks_and_the_clan(agent):
    """Your cat's look in full (its clan and role by name, its accessories' ids, its scars); a look from the save's text
    for one (NPCData's), the clan's cats from the save with their names (thousands of name ids: a real name each) and
    story roles; the game's accessories with their slots; a cat's place."""
    got = agent.lua("""
        local look = Game.cat():look()
        local cats = Game.clanCats()
        local named, story = 0, 0
        for _, c in ipairs(cats) do
            if c.name and c.name ~= "" then named = named + 1 end
            if #c.storyRoles > 0 then story = story + 1 end
        end
        local acc = Game.accessories()
        local slots = {}
        for _, a in ipairs(acc) do slots[a.slot] = true end
        local text = Game.lookFromText('(ClanType=ShadowClan,Role=Leader,TailIdx=8,CatSize=0.6,Gender=True,PrefixNameId="STR_CAT_NAME5",CombatStats=(TagName="Gameplay.Combat.Character.Cat"))')
        return { clan = look.ClanType, role = look.Role, neck = look.AccesoryNeckId, fields = look.FurColorIdx ~= nil and look.ScarEyeId ~= nil,
                 cats = #cats, named = named, story = story, accessories = #acc, slots = slots, text = text,
                 role2 = Game.cat():role() }""")
    assert got["clan"] in ("ThunderClan", "ShadowClan", "RiverClan", "WindClan") and got["role"] and got["neck"], got
    assert got["fields"] is True, got
    assert got["cats"] >= 10 and got["named"] == got["cats"] and got["story"] >= 1, got
    assert got["accessories"] >= 5 and {"Neck", "Head"} <= set(got["slots"]), got
    assert got["text"] == {"ClanType": "ShadowClan", "Role": "Leader", "TailIdx": 8, "CatSize": 0.6, "Gender": True,
                           "PrefixNameId": "STR_CAT_NAME5", "CombatStats": "Gameplay.Combat.Character.Cat"}, got["text"]
    assert got["role2"]["clan"] == got["clan"] and got["role2"]["role"] == got["role"], got["role2"]


def test_lua_photo_mode(agent):
    """Photo mode on the game's way (the pause screen, then its Photo Mode), its camera there, its menus hidden and shown
    again, and off: back to play."""
    _no_screens(agent)
    try:
        assert agent.lua("return Game.photo.mode(true)") is True
        agent.wait(lambda: agent.lua("return Game.photo.active()"), 10, "photo mode")
        assert agent.lua("return Game.photo.camera() ~= nil") is True
        assert agent.lua("return Game.photo.ui(false)") is True
        time.sleep(0.8)
        assert agent.lua("return Game.photo.ui(true)") is True
        time.sleep(0.8)
        assert agent.lua("return Game.photo.mode(false)") is True
        agent.wait(lambda: not agent.lua("return Game.photo.active()"), 6, "photo mode to close")
    finally:
        agent.lua("Game.photo.mode(false) return true")
        _no_screens(agent)
