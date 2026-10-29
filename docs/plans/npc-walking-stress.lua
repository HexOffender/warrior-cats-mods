-- 50-NPC walking stress test (probe). Usage: STRESS_START(n)  then read STRESS_REPORT() after ~70 s.
local Game = require("WCModsGame")
local gs = Game.library("GameplayStatics")

function STRESS_START(n)
  math.randomseed(12345)
  if S and S.tick then pcall(function() S.tick:stop() end) end
  for _, c in ipairs(Game.npcs.all()) do c:remove() end
  local me = Game.cat():location()
  S = { n = n, npcs = {}, res = {}, spawnFail = 0, t0 = os.clock(), dts = {}, overlaps = 0, samples = 0, minpair = 1e9, ev = {} }
  local function rnd(a, b) return a + math.random() * (b - a) end
  local function pt(cx, cy, r)
    local x, y = cx + rnd(-r, r), cy + rnd(-r, r)
    return { X = x, Y = y, Z = Game.ground(x, y, me.Z + 300) or me.Z }
  end
  local function hex() return string.format("#%02x%02x%02x", math.random(30, 240), math.random(30, 240), math.random(30, 240)) end
  local kinds = { "random", "pingpong", "route", "loop", "straight", "unreachable", "interrupt", "headon" }
  local function leg(e)
    -- run the next leg of this NPC's plan
    local c = e.npc
    if not c:actorOrNil() then return end
    e.legs = (e.legs or 0) + 1
    if e.legs > 12 then return end
    local p = e.pts[e.i]
    e.t0 = os.clock()
    c:walkTo(p.X, p.Y, p.Z, { speed = e.speed, radius = e.radius, avoid = e.avoid, done = function(_, r)
      S.res[r] = (S.res[r] or 0) + 1
      if r == "blocked" then
        local l = c:location()
        S.blk = S.blk or {}
        S.blk[#S.blk + 1] = string.format("%s t=%.1f rem=%.0f", e.kind, os.clock() - (e.t0 or 0), math.sqrt((l.X - p.X) ^ 2 + (l.Y - p.Y) ^ 2))
      end
      e.last = r
      if r == "arrived" then
        e.arrived = (e.arrived or 0) + 1
        e.i = e.i + e.dir
        if e.i > #e.pts or e.i < 1 then
          if e.kind == "route" then e.dir = -e.dir; e.i = e.i + 2 * e.dir
          elseif e.kind == "loop" then e.i = 1
          else e.dir = -e.dir; e.i = e.i + 2 * e.dir end
        end
        if e.i < 1 then e.i = 1 elseif e.i > #e.pts then e.i = #e.pts end
        leg(e)
      elseif r == "blocked" then
        e.blocked = (e.blocked or 0) + 1
      end
    end })
  end
  local k = 0
  for i = 1, n do
    local kind = kinds[(i - 1) % #kinds + 1]
    local at = pt(me.X, me.Y, 1500)
    local ok, c = pcall(Game.npcs.spawn, { at = at, yaw = math.random(0, 359), size = rnd(0.7, 1.3), eyes = math.random(0, 24),
      colours = { fur = hex(), pattern = hex(), markings = hex(), nose = hex(), paws = hex() } })
    if ok and c then
      local e = { npc = c, kind = kind, speed = ({ 90, 175, 175, 300, 450 })[math.random(1, 5)], radius = ({ 15, 30, 30, 60, 120 })[math.random(1, 5)],
        avoid = kind ~= "straight", i = 1, dir = 1, spawn = at, dist = 0 }
      e.pts = {}
      if kind == "random" then e.pts = { pt(me.X, me.Y, 2500) }
      elseif kind == "pingpong" then e.pts = { pt(me.X, me.Y, 1500), at }
      elseif kind == "route" or kind == "loop" then for j = 1, 4 do e.pts[j] = pt(me.X, me.Y, 1500) end
      elseif kind == "straight" then e.pts = { pt(me.X, me.Y, 1500), pt(me.X, me.Y, 1500) }
      elseif kind == "unreachable" then
        local p = pt(me.X, me.Y, 1500)
        if i % 16 == 6 then p.Y = p.Y - 30000 else p.X = p.X + 60000 end   -- far outside the nav mesh
        e.pts = { p }
      elseif kind == "interrupt" then e.pts = { pt(me.X, me.Y, 2000), pt(me.X, me.Y, 2000) }
      elseif kind == "headon" then
        -- walkers in pairs head-on: the previous headon spawned goes to where this one starts and vice versa
        e.pts = { pt(me.X, me.Y, 1500) }
        local prev = S.lastHeadon
        if prev then
          e.pts = { { X = prev.spawn.X, Y = prev.spawn.Y, Z = prev.spawn.Z } }
          prev.pts = { { X = at.X, Y = at.Y, Z = at.Z } }
          S.lastHeadon = nil
        else S.lastHeadon = e end
      end
      S.npcs[#S.npcs + 1] = e
    else S.spawnFail = S.spawnFail + 1 end
  end
  -- one crosses the player's cat
  local e = S.npcs[1]
  if e then e.kind = "crossplayer"; e.pts = { { X = me.X + 400, Y = me.Y + 10, Z = me.Z }, { X = me.X - 400, Y = me.Y - 10, Z = me.Z } }
    e.npc:moveTo(me.X - 400, me.Y, me.Z + 100) end
  for _, e2 in ipairs(S.npcs) do
    leg(e2)
    if e2.kind == "interrupt" then
      -- interrupt after a random time with stop / moveTo / another walkTo
      local when = rnd(3, 12)
      local how = math.random(1, 3)
      Game.after(when, function()
        local c = e2.npc
        if how == 1 then c:stop()
        elseif how == 2 then local p = pt(me.X, me.Y, 1500); c:moveTo(p.X, p.Y, p.Z)
        else local p = pt(me.X, me.Y, 1500); c:walkTo(p.X, p.Y, p.Z, { done = function(_, r) S.res[r] = (S.res[r] or 0) + 1 end }) end
        e2.interrupted = how
      end)
    end
  end
  -- sampler: positions, overlaps, frame delta
  local last = {}
  local tlast = os.clock()
  S.tick = Game.every(0.5, function()
    local now = os.clock()
    local ok, dt = pcall(function() return gs:GetWorldDeltaSeconds(Game.world()) end)
    if ok and type(dt) == "number" then S.dts[#S.dts + 1] = dt end
    local pos = {}
    local t1 = os.clock()
    for idx, e3 in ipairs(S.npcs) do
      local ok2, l = pcall(function() return e3.npc:location() end)
      if ok2 and l then
        pos[idx] = l
        if last[idx] then e3.dist = e3.dist + math.sqrt((l.X - last[idx].X) ^ 2 + (l.Y - last[idx].Y) ^ 2) end
        if last[idx] and e3.walkingNow == nil then e3.walkingNow = true end
      end
    end
    for a = 1, #S.npcs do for b = a + 1, #S.npcs do
      local pa, pb = pos[a], pos[b]
      if pa and pb then
        local d = math.sqrt((pa.X - pb.X) ^ 2 + (pa.Y - pb.Y) ^ 2)
        if d < S.minpair then S.minpair = d end
        if d < 40 then S.overlaps = S.overlaps + 1 end
      end
    end end
    S.samples = S.samples + 1
    S.sampleCost = (S.sampleCost or 0) + (os.clock() - t1)
    last = pos
  end)
  return { spawned = #S.npcs, fail = S.spawnFail }
end

function STRESS_REPORT()
  local live, walking, stuck = 0, 0, {}
  local byk = {}
  for i, e in ipairs(S.npcs) do
    if e.npc:actorOrNil() then live = live + 1 end
    if e.npc:walking() then walking = walking + 1 end
    local b = byk[e.kind] or { n = 0, moved = 0, arrived = 0, blocked = 0, stuck = 0 }
    byk[e.kind] = b
    b.n = b.n + 1; b.arrived = b.arrived + (e.arrived or 0); b.blocked = b.blocked + (e.blocked or 0)
    if e.dist < 100 then b.stuck = b.stuck + 1; stuck[#stuck + 1] = i .. ":" .. e.kind .. ":" .. tostring(e.last) end
  end
  local ds = {}
  for _, d in ipairs(S.dts) do ds[#ds + 1] = d end
  table.sort(ds)
  local function pct(p) return ds[math.max(1, math.floor(#ds * p))] or 0 end
  local sum = 0 for _, d in ipairs(ds) do sum = sum + d end
  return { n = S.n, live = live, walking = walking, spawnFail = S.spawnFail, res = S.res, byKind = byk, stuck = stuck,
    overlapPairSamples = S.overlaps, minPair = S.minpair, samples = S.samples,
    dtMeanMs = #ds > 0 and sum / #ds * 1000 or 0, dtP95Ms = pct(0.95) * 1000, dtMaxMs = (ds[#ds] or 0) * 1000,
    fpsMean = #ds > 0 and #ds / sum or 0, sampleCostMs = (S.sampleCost or 0) / math.max(1, S.samples) * 1000 }
end

function STRESS_CLEAN()
  if S and S.tick then pcall(function() S.tick:stop() end) end
  for _, c in ipairs(Game.npcs.all()) do c:remove() end
  S.npcs = {}
  return #Game.npcs.all()
end
return "loaded"



