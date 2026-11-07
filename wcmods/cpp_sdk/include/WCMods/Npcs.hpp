// Npcs.hpp: cats of a mod's own. The game's own walking clan cat (BP_WalkingNPC_Character_Base), spawned with a
// look, a size and a name, kept in the world (spawned again after a level change), walked along the nav mesh by
// its own AI controller, with the game's label over its head, the game's Talk prompt beside it, and the game's
// Interact key or button heard for it. As Lua's Game.npcs (docs/scripting.md), which these follow. Game thread
// only. WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call.
#pragma once

#include <algorithm>
#include <chrono>
#include <deque>
#include <cmath>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <random>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Carry.hpp>
#include <WCMods/CatMoves.hpp>
#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Looks.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/Ui.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // What a cat is made with. `look` and `slots` take the cat maker's parts (body, fur, tail, ears, eyes, whiskers,
    // face, pattern, marking) and colour slots (fur, pattern, marking); the parts not given are made up, as the game
    // does, once: each spawn of it is the same cat. `colours` paints a part (fur, pattern, markings, nose, paws, whiskers, ears) in
    // "#rrggbb". `prefix` and `suffix` are the name's ids, as the game's tables and the save have them (L"STR_CAT_NAME2",
    // L"_PAW": CatTables.hpp). `eyes` is the eyes' colour slot, `eyes2` the right eye's when it's another (odd eyes).
    // `ground` puts it on the ground below `at` (false: it floats where it's put). `freeze_beyond`: how far from your
    // cat the game lets it move (cm); beyond, the game freezes it (no moving, no collision) until your cat comes back
    // within it: the game's own is 2343. `asleep`: made as a handle only, out of the world until wake().
    struct NpcSpec
    {
        Vec3 at;
        double yaw{};
        std::optional<double> size;
        std::optional<std::wstring> prefix, suffix;
        std::map<std::wstring, int> look;
        std::map<std::wstring, int> slots;
        std::optional<int> eyes, eyes2;
        std::map<std::wstring, std::wstring> colours;
        bool ground{true};
        std::optional<double> freeze_beyond;
        bool asleep{false};
        std::map<std::wstring, int> scars;    // eye, ear, body, chest: the game's scar ids (0 or none given: none)
        std::vector<std::wstring> tags;       // put on its actor (actor_tags), each time it comes in
    };
    // A label over a cat's head, in the game's style: its name, a smaller title under it, an extra line above it in
    // the game's green, and an icon ("available", "ongoing", "done": the game's quest marks); shown within `range`
    // cm of your cat when its head can be seen.
    struct NpcLabel
    {
        std::wstring name, title, extra, icon;
        double range{1000};
    };
    // How a walk ended: arrived (within its radius across the ground), blocked (it stopped making progress, or its
    // controller wouldn't start), cancelled (stop, move_to, another walk, remove, or the cat unloaded).
    enum class WalkResult
    {
        None,
        Arrived,
        Blocked,
        Cancelled
    };
    struct WalkOptions
    {
        double speed{175};    // cm/s (the player's walk measured 174)
        double radius{30};    // cm: close enough
        bool avoid{true};     // along the nav mesh, round obstacles; false walks a straight line
    };

    namespace detail
    {
        struct WalkState
        {
            Vec3 to;
            WalkOptions options;
            std::function<void(WalkResult)> done;
            std::chrono::steady_clock::time_point started, best_at, mark_at, detour_till;
            double best{1e18};
            std::optional<Vec3> mark, detour;
            int tries{};
            UObject* goal{};          // a walk after another actor: the actor, its class (to know it's still that one)
            UClass* goal_class{};
            std::optional<Vec3> goal_at;   // and where it was when the move was last asked for
            double best_path{1e18};        // the shortest path still to walk seen (nav_path_length), when stalled
        };
        struct NpcState
        {
            NpcSpec spec;
            UObject* actor{};
            int32_t index{-1};
            std::wstring level;
            bool removed{};
            bool asleep{};                                      // out of the world by sleep() (or made asleep)
            bool queued{};                                      // waiting in the spawn queue
            std::chrono::steady_clock::time_point not_before;   // (its ground wasn't there: looked at again then)
            std::vector<std::function<void()>> woke;            // wake()'s done, when it's in
            std::map<std::wstring, int> made;                   // its look, made up once (each spawn the same cat)
            int spawns{};
            std::map<std::wstring, double> scalars;            // material scalar parameters (the eyes)
            std::map<std::wstring, UiColor> paint;              // material colours
            std::optional<NpcLabel> label;
            Widget label_widget;
            std::optional<NpcLabel> label_set;   // the label last written into label_set_on
            Widget label_set_on;
            std::wstring prompt;
            double reach{250};
            std::optional<WalkState> walk;
            WalkResult walk_result{WalkResult::None};
        };
        struct NpcsState
        {
            std::vector<std::shared_ptr<NpcState>> all;
            std::vector<std::function<void(std::shared_ptr<NpcState>)>> on_interact;
            TimerId keeper{}, walker{};
            HookId listen{};
            Widget prompt;              // the prompt widget on the HUD
            Widget prompt_hud;          // the HUD it was made on
            Widget menu, menu_hud;      // the HUD's contextual menu (the game's own prompts), found once per HUD
            std::shared_ptr<NpcState> prompt_on;   // whose prompt shows
            std::deque<std::shared_ptr<NpcState>> queue;   // cats to put in the world, a few a frame
            int per_frame{1};
        };
        inline auto npcs_state() -> NpcsState&
        {
            static NpcsState s;
            return s;
        }
        inline constexpr const wchar_t* NPC_CLASS = L"/Game/Gameplay/Blueprints/Characters/ExplorationCharacters/BP_WalkingNPC_Character_Base.BP_WalkingNPC_Character_Base_C";
        inline constexpr const wchar_t* LABEL_CLASS = L"/Game/Art/UXD/Blueprints/Controls/gui_actor_widgets/WBP_GuiQuestNpcWidgetsContainer.WBP_GuiQuestNpcWidgetsContainer_C";

        inline auto npc_alive(const NpcState& n) -> bool
        {
            if (!n.actor || n.index < 0 || n.index >= RC::Unreal::UObjectArray::GetNumElements()) return false;
            auto* item = RC::Unreal::UObjectArray::IndexToObject(n.index);
            return item && item->GetUObject() == n.actor && item->IsValid(false) && object_staying(n.actor, nullptr);
        }
        // A look's parts as the customisation fields each sets (the body sets the fur's shape to match, as the cat
        // maker does), the highest a made-up one takes, and the colour slots' fields.
        inline auto look_fields() -> const std::map<std::wstring, std::vector<std::wstring>>&
        {
            static const std::map<std::wstring, std::vector<std::wstring>> f{
                {L"body", {L"BodyValue", L"FurIdx"}}, {L"fur", {L"FurValue"}}, {L"tail", {L"TailIdx"}}, {L"ears", {L"EarIdx"}},
                {L"eyes", {L"EyeValue"}}, {L"whiskers", {L"WhiskerValue"}}, {L"face", {L"FaceValue"}},
                {L"pattern", {L"PatternIdx"}}, {L"marking", {L"MarkingIdx"}}};
            return f;
        }
        inline auto look_max(const std::wstring& part) -> int { return part == L"pattern" || part == L"marking" ? 20 : 9; }
        inline auto slot_fields() -> const std::map<std::wstring, std::pair<std::wstring, int>>&
        {
            static const std::map<std::wstring, std::pair<std::wstring, int>> f{
                {L"fur", {L"FurColorIdx", 19}}, {L"pattern", {L"Pattern01ColorIdx", 24}}, {L"marking", {L"Pattern02ColorIdx", 24}}};
            return f;
        }
        inline auto colour_params() -> const std::map<std::wstring, std::wstring>&
        {
            static const std::map<std::wstring, std::wstring> p{
                {L"fur", L"Fur Color"}, {L"pattern", L"Pattern Mask Color"}, {L"markings", L"Markings Mask Color"},
                {L"nose", L"Nose Color"}, {L"paws", L"Paws Color"}, {L"whiskers", L"Whiskers Color"}, {L"ears", L"Ears Color"}};
            return p;
        }
        inline auto random_int(int lo, int hi) -> int
        {
            static std::mt19937 rng{std::random_device{}()};
            return std::uniform_int_distribution<int>(lo, hi)(rng);
        }
        // The customisation fields for one spawn: the parts and slots given, the rest made up (each spawn anew). The
        // game keeps every field once bOverrideColors is set, so one left out would be 0 for every cat.
        inline auto scar_fields() -> const std::map<std::wstring, std::wstring>&
        {
            static const std::map<std::wstring, std::wstring> f{
                {L"eye", L"ScarEyeId"}, {L"ear", L"ScarEarId"}, {L"body", L"ScarBodyId"}, {L"chest", L"ScarChestId"}};
            return f;
        }
        inline auto npc_look(const NpcSpec& s) -> std::map<std::wstring, int>
        {
            std::map<std::wstring, int> out;
            for (auto& [part, fields] : look_fields())
            {
                auto given = s.look.find(part);
                int v = given != s.look.end() ? given->second : random_int(0, look_max(part));
                for (auto& f : fields) out[f] = v;
            }
            for (auto& [part, field] : slot_fields())
            {
                auto given = s.slots.find(part);
                out[field.first] = given != s.slots.end() ? given->second : random_int(0, field.second);
            }
            int eye = s.eyes.value_or(random_int(0, 24));
            out[L"EyeLeftColorIdx"] = eye;
            out[L"EyeRightColorIdx"] = s.eyes2.value_or(eye);
            for (auto& [part, field] : scar_fields())
            {
                auto given = s.scars.find(part);
                out[field] = given != s.scars.end() ? given->second : 0;
            }
            return out;
        }
        // Put the cat's feet (its mesh's origin) on the ground at height g.
        inline auto stand_on(UObject* a, std::optional<double> g) -> void
        {
            if (!g) return;
            UObject* mesh = get(a, L"Mesh").object;
            auto feet = mesh ? call_reflected(mesh, STR("K2_GetComponentLocation")) : std::nullopt;
            if (!feet) return;
            double dz = *g - get(feet->get(L"ReturnValue"), L"Z").number();
            if (std::abs(dz) < 1 || std::abs(dz) > 500) return;   // there already, or a trace gone wrong
            auto l = location(a);
            if (l) teleport(a, {l->x, l->y, l->z + dz});
        }
        // Colours and eyes onto every dynamic material of the cat's meshes.
        inline auto paint_npc(NpcState& n, bool check = false) -> void
        {
            if (n.paint.empty() && n.scalars.empty()) return;
            // Kept on (check): looked at on the body's first material, and painted again only when the game has put
            // its own back (the Lua's way), not every half second.
            if (check && !n.paint.empty())
            {
                UObject* mesh = get(n.actor, L"Mesh").object;
                auto m = mesh ? call_reflected(mesh, STR("GetMaterial"), [&](Params& p) { p.set_nth(0, Value::of(0)); }) : std::nullopt;
                UObject* mat = m ? m->get(L"ReturnValue").object : nullptr;
                auto& [param, colour] = *n.paint.begin();
                auto now = mat ? call_reflected(mat, STR("K2_GetVectorParameterValue"),
                                                [&](Params& p) { p.set_nth(0, Value::of(std::wstring_view(param))); })
                               : std::nullopt;
                if (now)
                {
                    auto want = detail::linear(colour);
                    Value c = now->get(L"ReturnValue");
                    if (std::abs(get(c, L"R").number() - want.r) < 0.002 && std::abs(get(c, L"G").number() - want.g) < 0.002
                        && std::abs(get(c, L"B").number() - want.b) < 0.002)
                        return;
                }
            }
            for (const wchar_t* field : {L"Mesh", L"Fur", L"Tail", L"Ears"})
            {
                UObject* mesh = get(n.actor, field).object;
                if (!mesh) continue;
                auto count = call_reflected(mesh, STR("GetNumMaterials"));
                int materials = count ? static_cast<int>(count->get(L"ReturnValue").number()) : 0;
                for (int i = 0; i < materials; ++i)
                {
                    auto m = call_reflected(mesh, STR("GetMaterial"), [&](Params& p) { p.set_nth(0, Value::of(i)); });
                    UObject* mat = m ? m->get(L"ReturnValue").object : nullptr;
                    if (!mat || !is_a(mat, STR("/Script/Engine.MaterialInstanceDynamic"))) continue;
                    for (auto& [param, colour] : n.paint)
                        call_reflected(mat, STR("SetVectorParameterValue"), [&](Params& p) {
                            p.set_nth(0, Value::of(std::wstring_view(param)));
                            Value c = p.nth(1);
                            auto lin = detail::linear(colour);
                            set(c, L"R", static_cast<double>(lin.r));
                            set(c, L"G", static_cast<double>(lin.g));
                            set(c, L"B", static_cast<double>(lin.b));
                            set(c, L"A", 1.0);
                        });
                    for (auto& [param, v] : n.scalars)
                        call_reflected(mat, STR("SetScalarParameterValue"), [&](Params& p) {
                            p.set_nth(0, Value::of(std::wstring_view(param)));
                            p.set_nth(1, Value::of(v));
                        });
                }
            }
        }
        // The walking cats have no label component: one is added with the game's own label widget, in screen space.
        inline auto add_label(NpcState& n) -> void
        {
            UObject* cls = object(STR("/Script/SwtQuest.QuestWidgetComponent"));
            UObject* wcls = load(LABEL_CLASS);
            if (!cls || !wcls) return;
            auto c = call_reflected(n.actor, STR("AddComponentByClass"), [&](Params& p) {
                p.set_nth(0, Value::of(cls));
                p.set_nth(1, Value::of(false));
                transform_of(p, L"RelativeTransform", {0, 0, 40}, 0);
                p.set_nth(3, Value::of(false));
            });
            UObject* comp = c ? c->get(L"ReturnValue").object : nullptr;
            if (!comp) return;
            auto w = call_reflected(object(STR("/Script/UMG.Default__WidgetBlueprintLibrary")), STR("Create"), [&](Params& p) {
                p.set_nth(0, Value::of(controller()));
                p.set_nth(1, Value::of(wcls));
                p.set_nth(2, Value::of(controller()));
            });
            UObject* widget = w ? w->get(L"ReturnValue").object : nullptr;
            if (!widget) return;
            call_reflected(comp, STR("SetWidget"), [&](Params& p) { p.set_nth(0, Value::of(widget)); });
            call_reflected(comp, STR("SetWidgetSpace"), [&](Params& p) { p.set_nth(0, Value::of(1)); });   // Screen
            call_reflected(comp, STR("SetDrawSize"), [&](Params& p) {
                Value s = p.nth(0);
                set(s, L"X", 500.0);
                set(s, L"Y", 500.0);
            });
            n.label_widget = Widget(widget);
            for (const wchar_t* part : {L"mcGuiActorName", L"mcGuiActorStatus"})
                if (Widget pw(get(widget, part).object); pw) pw.set_opacity(0);
        }
        inline auto set_freeze_radius(UObject* a, double cm) -> bool;
        inline auto start_npcs() -> void;
        inline auto spawn_npc(NpcState& n) -> bool
        {
            if (!player()) return false;
            if (!n.level.empty() && level_name() != n.level) return false;
            if (n.level.empty()) n.level = level_name();
            std::optional<double> g = n.spec.ground ? ground(n.spec.at.x, n.spec.at.y, n.spec.at.z) : std::nullopt;
            UObject* cls = load(NPC_CLASS);
            if (!cls) return false;
            Vec3 at{n.spec.at.x, n.spec.at.y, (g ? *g : n.spec.at.z) + 30};
            if (n.made.empty()) n.made = npc_look(n.spec);   // the parts made up once: each spawn the same cat
            const auto& look = n.made;
            auto dress = [&](UObject* a) {
                UObject* c = get(a, L"MeshCustomizationComponent").object;
                if (!c) return c;
                if (n.spec.size) set(c, L"CustomData.CatSize", *n.spec.size);
                if (n.spec.prefix) set(c, L"CustomData.PrefixNameId", std::wstring_view(*n.spec.prefix));
                if (n.spec.suffix) set(c, L"CustomData.SuffixNameId", std::wstring_view(*n.spec.suffix));
                for (auto& [field, v] : look) set(c, std::wstring(L"CustomData.") + field, v);
                set(c, L"CustomData.bOverrideColors", true);
                return c;
            };
            UObject* a = spawn_deferred(cls, at, n.spec.yaw, [&](UObject* a) {
                // Not one of the save's cats: no unique id for the save to keep it by, nothing remembered of its going.
                if (UObject* ids = get(a, L"InstancedUniqueIdentifierComponent").object) set(ids, L"bIsEnabled", false);
                set(a, L"bAddsToRemovedLocalData", false);
                dress(a);
            });
            if (!a) return false;
            // The game set a look up as it finished, not this one: set up again from it (the game's SetDefaultCustomData;
            // RefreshShape, the fallback, moves only the body's shape).
            if (UObject* c = dress(a))
                if (!detail::draw_look(c)) call_reflected(c, STR("RefreshShape"));
            if (UObject* m = get(a, L"CharacterMovement").object)
            {
                set(m, L"MaxWalkSpeed", 175.0);
                // The nav mesh the walking cats use (radius 1, height 25); round other characters.
                set(m, L"NavAgentProps.AgentRadius", 1.0);
                set(m, L"NavAgentProps.AgentHeight", 25.0);
                set(m, L"bUseRVOAvoidance", true);
                set(m, L"AvoidanceConsiderationRadius", 200.0);
                set(m, L"AvoidanceWeight", 0.5);
                if (!n.spec.ground) set(m, L"GravityScale", 0.0);
            }
            // The game's behaviour tree also drives the cat (and it aborted the game minutes after one spawned):
            // only walk_to moves it.
            if (UObject* brain = get(get(a, L"Controller").object, L"BrainComponent").object)
                call_reflected(brain, STR("StopLogic"), [&](Params& p) { p.set_nth(0, Value::of(std::wstring_view(L"wcmods"))); });
            stand_on(a, g);
            for (const std::wstring& tag : n.spec.tags) add_tag(a, tag);
            n.actor = a;
            n.index = a->GetInternalIndex();
            n.walk.reset();
            n.asleep = false;
            ++n.spawns;
            add_label(n);
            paint_npc(n);
            if (n.spec.freeze_beyond) set_freeze_radius(a, *n.spec.freeze_beyond);
            auto woke = std::move(n.woke);
            n.woke.clear();
            for (auto& fn : woke) guarded(L"a wake's done", fn);
            return true;
        }
        // The game's hiding by distance (SwtAdventureHideCharacterComponent: a sphere round the cat that your cat
        // overlapping keeps it moving; outside it, its ticking and collision are off).
        inline auto hide_component(UObject* a) -> UObject*
        {
            UObject* cls = find_class(STR("/Script/SwtAdventure.SwtAdventureHideCharacterComponent"));
            auto r = cls && a ? call_reflected(a, STR("GetComponentByClass"), [&](Params& p) { p.set_nth(0, Value::of(cls)); }) : std::nullopt;
            return r ? r->get(L"ReturnValue").object : nullptr;
        }
        inline auto set_freeze_radius(UObject* a, double cm) -> bool
        {
            UObject* h = hide_component(a);
            if (!h) return false;
            // (overlaps updated at once: a cat now within it moves again, one now outside freezes)
            return call_reflected(h, STR("SetSphereRadius"), [&](Params& p) {
                       p.set_nth(0, Value::of(cm));
                       p.set_nth(1, Value::of(true));
                   }).has_value();
        }
        // Queue a cat to be put in the world (each frame the budget's worth: a spawn holds the game ~12 ms).
        inline auto enqueue(const std::shared_ptr<NpcState>& n) -> void
        {
            if (n->queued || n->removed) return;
            n->queued = true;
            npcs_state().queue.push_back(n);
        }
        // Each frame: up to the budget's worth of the queue's cats put in the world, once the ground's there for each
        // (a cat whose ground isn't is looked at again half a second later, the others going on past it).
        inline auto pump_spawns() -> void
        {
            auto& s = npcs_state();
            if (s.queue.empty() || !player()) return;
            const auto now = std::chrono::steady_clock::now();
            int spawned = 0, looked = 0;
            const size_t n_queued = s.queue.size();
            for (size_t i = 0; i < n_queued && spawned < s.per_frame && looked < 16 && !s.queue.empty(); ++i)
            {
                auto n = s.queue.front();
                s.queue.pop_front();
                if (n->removed || n->asleep || npc_alive(*n))
                {
                    n->queued = false;
                    continue;
                }
                if (now < n->not_before)
                {
                    s.queue.push_back(n);
                    continue;
                }
                if (!n->level.empty() && level_name() != n->level)   // (its level isn't the one loaded: the keeper asks again)
                {
                    n->queued = false;
                    continue;
                }
                ++looked;
                if (n->spec.ground && !ready_at(n->spec.at))
                {
                    n->not_before = now + std::chrono::milliseconds(500);
                    s.queue.push_back(n);
                    continue;
                }
                n->queued = false;
                ++spawned;
                guarded(L"a spawn", [&] { spawn_npc(*n); });   // (not in: another level, a menu; the keeper asks again)
            }
        }
    } // namespace detail

    // A cat of the mod's own: a handle that stays the same cat across its spawns (a level change makes it again).
    class Npc
    {
      public:
        Npc() = default;
        explicit Npc(std::shared_ptr<detail::NpcState> s) : m(std::move(s)) {}
        explicit operator bool() const { return m && !m->removed; }
        auto operator==(const Npc& o) const -> bool { return m == o.m; }
        // Its actor now, or nullptr while it isn't in the world (a menu, another level, removed).
        auto actor() const -> UObject* { return m && !m->removed && detail::npc_alive(*m) ? m->actor : nullptr; }
        auto spawns() const -> int { return m ? m->spawns : 0; }
        auto location() const -> std::optional<Vec3> { return actor() ? wcmods::location(actor()) : std::nullopt; }
        // How far it is from your cat across the ground, in cm; nullopt when either isn't there.
        auto distance() const -> std::optional<double>
        {
            auto me = location();
            auto you = wcmods::location(player());
            if (!me || !you) return std::nullopt;
            return std::hypot(me->x - you->x, me->y - you->y);
        }
        auto within(double cm) const -> bool
        {
            auto d = distance();
            return d && *d <= cm;
        }
        // Turn to face a place.
        auto face(Vec3 at) -> bool
        {
            UObject* a = actor();
            auto l = location();
            if (!a || !l) return false;
            double yaw = std::atan2(at.y - l->y, at.x - l->x) * 180.0 / 3.14159265358979323846;
            return call_reflected(a, STR("K2_SetActorRotation"), [&](Params& p) {
                       Value r = p.nth(0);
                       set(r, L"Yaw", yaw);
                       p.set_nth(1, Value::of(true));
                   }).has_value();
        }
        // Put it somewhere at once (on the ground there), ending a walk. Asleep, it wakes there (true).
        auto move_to(Vec3 at) -> bool
        {
            if (!m || m->removed) return false;
            stop();
            m->spec.at = at;
            if (m->asleep) return true;
            UObject* a = actor();
            if (!a) return false;
            bool ok = teleport(a, at);
            detail::stand_on(a, m->spec.ground ? ground(at.x, at.y, at.z) : std::nullopt);
            return ok;
        }
        // Walk there with its own AI controller (its walk animation, turning, keeping to the ground), along the nav
        // mesh round obstacles; `done(result)` when the walk ends. False when it isn't in the world or the controller
        // wouldn't start (done is told Blocked).
        auto walk_to(Vec3 to, WalkOptions options = {}, std::function<void(WalkResult)> done = {}) -> bool;
        auto walking() const -> bool { return m && m->walk.has_value(); }
        auto walk_result() const -> WalkResult { return m ? m->walk_result : WalkResult::None; }
        auto stop() -> void;
        // A pose (CatMoves.hpp: sitting, lying, asleep...), held until another or a walk; one of the game's moves
        // played on it (eating, sleeping, stalking...), and stopped. As set_pose, play_move and stop_move on its actor.
        auto pose(Pose p) -> bool { return wcmods::set_pose(actor(), p); }
        auto play(Move move, CatMoveOptions options = {}) -> UObject* { return wcmods::play_move(actor(), move, options); }
        auto stop_move(double blend = 0.25) -> void { wcmods::stop_move(actor(), blend); }
        // Something in its jaws (Carry.hpp: prey, moss, a herb...), dropped, and what it carries: as carry,
        // drop_carried and carrying on its actor.
        auto carry(Carried what, std::optional<CarryPlace> place = std::nullopt) -> UObject* { return wcmods::carry(actor(), what, place); }
        auto drop_carried() -> bool { return wcmods::drop_carried(actor()); }
        auto carrying() const -> std::optional<std::wstring> { return wcmods::carrying(actor()); }
        // The label over its head (set_label({}) with no name takes it away), and the prompt beside it ("Talk", the
        // game's Interact glyph with it) while your cat is within `reach` cm; empty takes it away.
        auto set_label(NpcLabel label) -> void
        {
            if (m) m->label = label.name.empty() && label.title.empty() && label.extra.empty() && label.icon.empty() ? std::nullopt : std::optional(label);
        }
        // Its scars (eye, ear, body, chest: the game's ids, 0 for none; a part not given keeps its own), drawn now if it's
        // in the world and kept for each time it comes in. False when it's been removed, or for a part it hasn't got
        // (nothing changed then).
        auto set_scars(const std::map<std::wstring, int>& scars) -> bool
        {
            if (!m || m->removed) return false;
            for (auto& [part, id] : scars)
                if (!detail::scar_fields().contains(part)) return false;
            for (auto& [part, id] : scars) m->spec.scars[part] = id;
            // its look made up now if it hasn't come in yet (else its first coming in would take the scars for its look)
            if (m->made.empty()) m->made = detail::npc_look(m->spec);
            for (auto& [part, id] : scars) m->made[detail::scar_fields().at(part)] = id;
            if (UObject* a = actor())
                if (UObject* c = get(a, L"MeshCustomizationComponent").object)
                {
                    for (auto& [part, field] : detail::scar_fields()) set(c, std::wstring(L"CustomData.") + field, m->made[field]);
                    detail::draw_look(c);
                }
            return true;
        }
        auto scars() const -> std::map<std::wstring, int> { return m ? m->spec.scars : std::map<std::wstring, int>{}; }
        // A tag on its actor, now and each time it comes in (actor_tags); its tags.
        auto tag(std::wstring_view t) -> bool
        {
            if (!m || m->removed || t.empty()) return false;
            if (std::find(m->spec.tags.begin(), m->spec.tags.end(), t) == m->spec.tags.end()) m->spec.tags.emplace_back(t);
            if (UObject* a = actor()) add_tag(a, t);
            return true;
        }
        auto tags() const -> std::vector<std::wstring> { return m ? m->spec.tags : std::vector<std::wstring>{}; }

        auto set_prompt(std::wstring_view text, double reach = 250) -> void
        {
            if (!m) return;
            m->prompt = text;
            m->reach = reach;
        }
        // Out of the world, kept: where it was and which way it faced, its look, its label and prompt, what it's
        // asked to wake to. False when it isn't in the world (asleep already, or waiting to come in: that's called off).
        auto sleep() -> bool
        {
            if (!m || m->removed || m->asleep) return false;
            stop();
            m->asleep = true;
            m->woke.clear();
            UObject* a = actor();
            if (!a) return false;
            if (auto l = wcmods::location(a)) m->spec.at = *l;
            if (auto r = call_reflected(a, STR("K2_GetActorRotation"))) m->spec.yaw = get(r->get(L"ReturnValue"), L"Yaw").number();
            destroy(a);
            m->actor = nullptr;
            return true;
        }
        // Back in the world where it was (or was moved to), as it was: within the spawn budget (a few cats a frame)
        // and once the ground's there (ready_at); `done(npc)` when it's in. False when it's removed or already in.
        auto wake(std::function<void(Npc)> done = {}) -> bool
        {
            if (!m || m->removed || actor()) return false;
            m->asleep = false;
            if (done)
                m->woke.push_back([w = std::weak_ptr<detail::NpcState>(m), done] {
                    if (auto s = w.lock()) done(Npc(s));
                });
            detail::enqueue(m);
            detail::start_npcs();
            return true;
        }
        auto asleep() const -> bool { return m && !m->removed && m->asleep; }
        // Asked to come into the world (woken, made, or its level back), not in yet.
        auto waking() const -> bool { return m && !m->removed && !m->asleep && !actor(); }
        // Where it is, or where it'll come in.
        auto place() const -> Vec3
        {
            if (auto l = location()) return *l;
            return m ? m->spec.at : Vec3{};
        }
        // How far from your cat the game lets it move (cm); beyond, it's frozen (no moving, no collision) until your
        // cat comes back within it. The game's own is 2343.
        auto set_freeze_beyond(double cm) -> bool
        {
            if (!m) return false;
            m->spec.freeze_beyond = cm;
            UObject* a = actor();
            return a && detail::set_freeze_radius(a, cm);
        }
        // In the world but frozen by the game (your cat beyond its freeze distance).
        auto frozen() const -> bool
        {
            UObject* a = actor();
            auto r = a ? call_reflected(a, STR("IsActorTickEnabled")) : std::nullopt;
            return r && !r->get(L"ReturnValue").boolean();
        }
        // Take it out of the world for good.
        auto remove() -> void
        {
            if (!m) return;
            stop();
            m->removed = true;
            m->woke.clear();
            if (UObject* a = detail::npc_alive(*m) ? m->actor : nullptr) destroy(a);
            m->actor = nullptr;
        }
        auto state() const -> std::shared_ptr<detail::NpcState> { return m; }

      private:
        std::shared_ptr<detail::NpcState> m;
    };

    namespace detail
    {
        inline auto finish_walk(NpcState& n, WalkResult result) -> void
        {
            auto w = std::move(n.walk);
            n.walk.reset();
            n.walk_result = result;
            UObject* a = npc_alive(n) ? n.actor : nullptr;
            if (a && result != WalkResult::Arrived)
                if (UObject* c = get(a, L"Controller").object) call_reflected(c, STR("StopMovement"));
            if (a)
                if (auto l = location(a)) n.spec.at = *l;
            if (w && w->done) guarded(L"a walk's done", [&] { w->done(result); });
        }
        // Ask the controller to go: along the nav mesh when `avoid`, a straight line when the mesh has no path. The
        // controller's result (0 is failed).
        inline auto issue_move(UObject* a, Vec3 to, double radius, bool avoid) -> int
        {
            UObject* c = get(a, L"Controller").object;
            auto go = [&](bool path) {
                auto r = call_reflected(c, STR("MoveToLocation"), [&](Params& p) {
                    Value d = p.nth(0);
                    set(d, L"X", to.x);
                    set(d, L"Y", to.y);
                    set(d, L"Z", to.z);
                    p.set_nth(1, Value::of(radius));
                    p.set_nth(2, Value::of(false));   // stop on overlap
                    p.set_nth(3, Value::of(path));    // use pathfinding
                    p.set_nth(4, Value::of(path));    // project the destination to the nav mesh
                    p.set_nth(5, Value::of(true));    // can strafe
                    p.set_nth(7, Value::of(true));    // allow a partial path
                });
                return r ? static_cast<int>(r->get(L"ReturnValue").number()) : 0;
            };
            int r = go(avoid);
            if (avoid && r == 0) r = go(false);
            return r;
        }
        // One look at a walk of any actor an AI controller moves, every 0.1 s: its end when it's over, else nullopt.
        // Arrived (within its radius), or stalled (the controller ended the move far away, it stood still a second, or
        // got no closer in 8 s) and a 150 cm step to a clear side before asking for the path again; after five such
        // stalls it's blocked. A walk after another actor (`goal`) follows it, asking again as it moves; the goal gone,
        // the walk is cancelled.
        inline auto walk_step(UObject* a, WalkState& w) -> std::optional<WalkResult>
        {
            auto l = location(a);
            if (!l) return std::nullopt;
            auto now = std::chrono::steady_clock::now();
            if (w.goal)
            {
                if (!object_staying(w.goal, w.goal_class)) return WalkResult::Cancelled;
                if (auto g = location(w.goal))
                {
                    w.to = *g;
                    if (!w.detour && (!w.goal_at || std::hypot(g->x - w.goal_at->x, g->y - w.goal_at->y) > 100))
                    {
                        w.goal_at = *g;
                        if (issue_move(a, w.to, w.options.radius, w.options.avoid) == 0) return WalkResult::Blocked;
                    }
                }
            }
            double d = std::hypot(w.to.x - l->x, w.to.y - l->y);
            if (d <= w.options.radius + 15)
            {
                if (UObject* c = get(a, L"Controller").object) call_reflected(c, STR("StopMovement"));
                return WalkResult::Arrived;
            }
            if (w.detour)
            {
                if (std::hypot(w.detour->x - l->x, w.detour->y - l->y) > 35 && now < w.detour_till) return std::nullopt;
                w.detour.reset();
                w.mark.reset();
                if (issue_move(a, w.to, w.options.radius, w.options.avoid) == 0) return WalkResult::Blocked;
                return std::nullopt;
            }
            bool stopped = false;
            if (now - w.started > std::chrono::milliseconds(500))
            {
                auto st = call_reflected(get(a, L"Controller").object, STR("GetMoveStatus"));
                stopped = st && st->get(L"ReturnValue").number() == 0;   // Idle
            }
            if (!w.mark || now - w.mark_at >= std::chrono::seconds(1))
            {
                if (w.mark && std::hypot(l->x - w.mark->x, l->y - w.mark->y) < 15) stopped = true;
                w.mark = *l;
                w.mark_at = now;
            }
            if (d < w.best - 60)
            {
                w.best = d;
                w.best_at = now;
                w.tries = 0;
            }
            else if (now - w.best_at > std::chrono::seconds(8))
            {
                // no nearer in a straight line for 8 s: nearer along the path still to walk than at the last look? (a way
                // round goes away from the place a while.) Else it's stuck.
                auto left = w.options.avoid ? nav_path_length(*l, w.to, a) : std::nullopt;
                if (left && *left < w.best_path - 60) w.best_path = *left;
                else stopped = true;
                w.best_at = now;
            }
            if (!stopped) return std::nullopt;
            if (!w.options.avoid || ++w.tries > 5) return WalkResult::Blocked;
            double fx = w.to.x - l->x, fy = w.to.y - l->y, len = std::max(1.0, std::hypot(fx, fy));
            fx /= len;
            fy /= len;
            double side = w.tries % 2 == 0 ? -1 : 1;
            std::optional<Vec3> best;
            for (auto [dx, dy] : {std::pair{-fy * side, fx * side}, std::pair{fy * side, -fx * side}, std::pair{-fx, -fy}})
            {
                Vec3 to{l->x + dx * 150, l->y + dy * 150, l->z};
                if (!trace({l->x, l->y, l->z + 20}, {to.x, to.y, l->z + 20}))
                {
                    best = to;
                    break;
                }
            }
            w.detour = best.value_or(Vec3{l->x - fx * 150, l->y - fy * 150, l->z});
            w.detour_till = now + std::chrono::milliseconds(1500);
            w.goal_at.reset();   // after the step, the goal is asked for again
            issue_move(a, *w.detour, 20, false);
            return std::nullopt;
        }
        inline auto step_walk(NpcState& n) -> void
        {
            if (!n.walk) return;
            UObject* a = npc_alive(n) ? n.actor : nullptr;
            if (!a) return finish_walk(n, WalkResult::Cancelled);
            if (auto r = walk_step(a, *n.walk)) finish_walk(n, *r);
        }
        // Each frame while the cats have prompts or a mod listens for Interact: the nearest cat in reach with a prompt
        // gets the game's prompt widget (its contextual menu's own class, on the HUD's exploration layer, with the
        // Interact glyph), at its body on screen; none while a screen or the game's own prompt is up.
        inline auto update_prompt() -> void
        {
            auto& s = npcs_state();
            bool any = std::any_of(s.all.begin(), s.all.end(), [](auto& n) { return !n->removed && !n->prompt.empty(); });
            if (!any)
            {
                s.prompt_on.reset();
                if (s.prompt) s.prompt.collapse();
                return;
            }
            Widget h = ui::hud();
            std::shared_ptr<NpcState> best;
            double best_d = 1e18;
            if (h && screens().empty())
                for (auto& n : s.all)
                {
                    if (n->removed || n->prompt.empty() || !npc_alive(*n)) continue;
                    auto d = Npc(n).distance();
                    if (d && *d <= n->reach && *d < best_d) best = n, best_d = *d;
                }
            if (h && (!s.menu || !(s.menu_hud == h)))
            {
                s.menu = h.find(L"mcGuiContextualMenu");
                s.menu_hud = h;
            }
            Widget menu = h ? s.menu : Widget();
            bool game_up = menu && menu.visibility() != Visibility::Collapsed && menu.visibility() != Visibility::Hidden;
            if (game_up) best.reset();
            s.prompt_on = best;
            if (!best)
            {
                if (s.prompt) s.prompt.collapse();
                return;
            }
            if (!s.prompt || !(s.prompt_hud == h))
            {
                Widget model = menu.find(L"mcGuiPrompt1");
                Widget layer = h.find(L"CanvasExploration");
                if (!model || !layer) return;
                s.prompt = ui::game_widget(model.object()->GetClassPrivate());
                s.prompt_hud = h;
                if (!s.prompt) return;
                Slot slot = layer.add(s.prompt);
                slot.auto_size(true);
                slot.alignment(0.5, 0.5);
                slot.anchors(0, 0, 0, 0);
                Widget button = s.prompt.find(L"mcGuiButtonAction");
                auto interact = enum_value(STR("/Script/SwtEngine.ECommands"), L"Player_Interact");
                if (button && interact)
                {
                    button.set(L"ActionCommand", Value::of(*interact));
                    button.call(STR("OnSetupInputs"));
                }
            }
            if (Widget t = s.prompt.find(L"mcGuiTextAction"); t && t.text() != best->prompt) t.set_text(best->prompt);
            // At its body on screen, in the viewport's units.
            auto l = location(best->actor);
            auto r = call_reflected(object(STR("/Script/Engine.Default__GameplayStatics")), STR("ProjectWorldToScreen"), [&](Params& p) {
                p.set_nth(0, Value::of(controller()));
                Value at = p.nth(1);
                set(at, L"X", l->x);
                set(at, L"Y", l->y);
                set(at, L"Z", l->z - 15);
            });
            if (r && r->get(L"ReturnValue").boolean())
            {
                double scale = ui::viewport_scale();
                Value sp = r->nth(2);
                s.prompt.slot().position(static_cast<float>(get(sp, L"X").number() / scale), static_cast<float>(get(sp, L"Y").number() / scale));
            }
            s.prompt.show_passive();
        }
        // Every half second: each cat kept in the world (spawned again when its level comes back), its colours kept
        // on, its label shown or hidden by your cat's distance.
        inline auto keep_npcs() -> void
        {
            auto& s = npcs_state();
            if (s.all.empty() || !player()) return;   // no cats: nothing to keep (the timers stay, idle)
            std::erase_if(s.all, [](const std::shared_ptr<NpcState>& n) { return n->removed; });
            for (auto& n : s.all)
            {
                if (!npc_alive(*n))
                {
                    if (n->walk) finish_walk(*n, WalkResult::Cancelled);
                    if (!n->asleep) enqueue(n);   // (its level back, a menu closed: in within the spawn budget)
                    continue;
                }
                if (n->walk)
                    if (auto l = location(n->actor)) n->spec.at = *l;
                paint_npc(*n, true);
                Widget w = n->label_widget;
                if (!w) continue;
                Widget name_part(get(w.object(), L"mcGuiActorName").object), status(get(w.object(), L"mcGuiActorStatus").object);
                auto d = Npc(n).distance();
                if (!n->label || !d || *d > n->label->range)
                {
                    if (name_part) name_part.set_opacity(0);
                    if (status) status.set_opacity(0);
                    continue;
                }
                auto& l = *n->label;
                bool fresh = !n->label_set || !(n->label_set_on == w) || n->label_set->name != l.name || n->label_set->title != l.title
                          || n->label_set->extra != l.extra || n->label_set->icon != l.icon;
                double fade = std::min(1.0, (l.range - *d) / (l.range * 0.3));
                if (name_part) name_part.set_opacity(fade);
                if (status) status.set_opacity(l.icon.empty() ? 0 : fade);
                if (!fresh) continue;   // the texts are written once a label (and a spawn), as the Lua does
                n->label_set = l;
                n->label_set_on = w;
                if (Widget t(get(name_part.object(), L"mcGuiTextName").object); t) t.set_text(l.name);
                if (Widget t(get(name_part.object(), L"mcGuiTextRole").object); t)
                {
                    t.set_text(l.title);
                    t.set_visibility(l.title.empty() ? Visibility::Collapsed : Visibility::SelfHitTestInvisible);
                }
                if (Widget t(get(name_part.object(), L"mcGuiTextExtraInfo").object); t)
                {
                    t.set_text(l.extra);
                    t.set_visibility(l.extra.empty() ? Visibility::Collapsed : Visibility::SelfHitTestInvisible);
                }
                for (auto [key, canvas] : {std::pair{L"available", L"CanvasAvailable"}, std::pair{L"ongoing", L"CanvasOngoing"},
                                           std::pair{L"done", L"CanvasCompleted"}})
                    if (Widget c(get(status.object(), canvas).object); c)
                        c.set_visibility(l.icon == key ? Visibility::SelfHitTestInvisible : Visibility::Collapsed);
                if (status) status.set_translation(0, -100);   // the icon above the lines, as the game has it for its own
            }
        }
        inline auto start_npcs() -> void
        {
            auto& s = npcs_state();
            if (s.keeper) return;
            s.keeper = every(0.5, [] { guarded(L"npcs", keep_npcs); });
            s.walker = every(0.1, [] {
                auto all = npcs_state().all;
                for (auto& n : all)
                    if (n->walk) guarded(L"a walk", [&] { step_walk(*n); });
            });
            every_frame([](float) {
                if (!player()) return;
                guarded(L"npc prompts", update_prompt);
                guarded(L"npc spawns", pump_spawns);
            });
            // The game's Interact as the player's controller hears it (any key or button bound to it, remaps too):
            // the press is for the cat whose prompt showed.
            s.listen = on_function(STR("/Script/SwtEngine.SwtPlayerController:OnListenCommand"), [](Call& call) {
                auto& st = npcs_state();
                if (st.on_interact.empty() || !st.prompt_on || !call.has_params()) return;
                if (call.param(0).text != L"Player_Interact" || call.param(1).number() != 0) return;   // IE_Pressed
                auto who = st.prompt_on;
                for (auto& fn : st.on_interact) guarded(L"on_npc_interact", [&] { fn(who); });
            });
        }
    } // namespace detail

    inline auto Npc::walk_to(Vec3 to, WalkOptions options, std::function<void(WalkResult)> done) -> bool
    {
        UObject* a = actor();
        if (!a) return false;
        if (m->walk) detail::finish_walk(*m, WalkResult::Cancelled);
        // up from a sit or a sleep first, and out of a move it doesn't walk in (asleep, eating): they'd slide along
        set_pose(a, Pose::Stand);
        if (montage_playing(a))
        {
            const std::wstring now = animation_playing(a);
            bool walking = false;
            for (Move m : {Move::Stalk, Move::WalkBack, Move::Tired})
                for (const std::wstring& seq : move_sequences(m)) walking = walking || seq == now;
            if (!walking) wcmods::stop_move(a);
        }
        if (UObject* mv = get(a, L"CharacterMovement").object) set(mv, L"MaxWalkSpeed", options.speed);
        if (detail::issue_move(a, to, options.radius, options.avoid) == 0)
        {
            m->walk_result = WalkResult::Blocked;
            if (done) detail::guarded(L"a walk's done", [&] { done(WalkResult::Blocked); });
            return false;
        }
        auto now = std::chrono::steady_clock::now();
        detail::WalkState w;
        w.to = to;
        w.options = options;
        w.done = std::move(done);
        w.started = w.best_at = now;
        m->walk = std::move(w);
        m->walk_result = WalkResult::None;
        return true;
    }
    inline auto Npc::stop() -> void
    {
        if (m && m->walk) detail::finish_walk(*m, WalkResult::Cancelled);
    }

    // Spawn a cat of the mod's own; it's kept in the world from then on (spawned again when its level loads again),
    // until remove(). In a menu it appears once you're in the world.
    inline auto spawn_npc(NpcSpec spec) -> Npc
    {
        auto n = std::make_shared<detail::NpcState>();
        n->spec = std::move(spec);
        for (auto& [part, hex] : n->spec.colours)
        {
            auto param = detail::colour_params().find(part);
            if (param != detail::colour_params().end()) n->paint[param->second] = UiColor::hex(hex);
        }
        if (n->spec.eyes)
        {
            n->scalars[L"IndexIrisColorCurveLeft"] = *n->spec.eyes + 1;   // row 0 of the eye atlas is the eye's white
            n->scalars[L"IndexIrisColorCurveRight"] = n->spec.eyes2.value_or(*n->spec.eyes) + 1;
        }
        else if (n->spec.eyes2)
            n->scalars[L"IndexIrisColorCurveRight"] = *n->spec.eyes2 + 1;
        n->asleep = n->spec.asleep;
        detail::npcs_state().all.push_back(n);
        detail::start_npcs();
        if (!n->asleep && on_game_thread_now() && player()) detail::guarded(L"spawn_npc", [&] { detail::spawn_npc(*n); });
        return Npc(n);
    }
    // How many cats a frame come into the world from the spawn queue (woken ones, ones made asleep then woken, ones
    // whose level came back): each spawn holds the game about 12 ms. 1 at first.
    inline auto set_npc_spawn_budget(int per_frame) -> void { detail::npcs_state().per_frame = std::max(1, per_frame); }
    inline auto npc_spawn_budget() -> int { return detail::npcs_state().per_frame; }
    // How many cats wait to come into the world (the queue, ones waiting for their ground among them).
    inline auto npcs_waiting() -> int
    {
        int n = 0;
        for (auto& c : detail::npcs_state().queue)
            if (c->queued && !c->removed && !c->asleep) ++n;
        return n;
    }
    // Every cat the mod has spawned and not removed.
    inline auto npcs() -> std::vector<Npc>
    {
        std::vector<Npc> out;
        for (auto& n : detail::npcs_state().all)
            if (!n->removed) out.emplace_back(n);
        return out;
    }
    // fn(npc) when the game's Interact (any key or button bound to it) is pressed while a cat's prompt shows. The
    // game hears the press too: with nothing of its own in reach it does nothing (its own prompt, when up, wins).
    inline auto on_npc_interact(std::function<void(Npc)> fn) -> void
    {
        detail::npcs_state().on_interact.push_back([fn = std::move(fn)](std::shared_ptr<detail::NpcState> n) { fn(Npc(n)); });
        detail::start_npcs();
    }
    namespace detail
    {
        // As the mod is taken out: its cats leave the world with it when that's on the game thread. Off it, they're
        // left standing (destroying actors from another thread could break the world, and nothing can be queued for
        // the game thread from a mod that's going).
        inline auto stop_npcs() -> void
        {
            const bool here = on_game_thread_now();
            for (auto& n : npcs_state().all)
            {
                n->removed = true;
                if (here && npc_alive(*n)) destroy(n->actor);
            }
            npcs_state().all.clear();
            if (here && npcs_state().prompt) npcs_state().prompt.remove();
        }
    } // namespace detail
    // A place for a cat beside yours: `distance` cm away, `side` degrees round from where your cat faces, on the
    // ground; nullopt without your cat.
    inline auto npc_spot(double distance = 220, double side = -60) -> std::optional<Vec3>
    {
        UObject* me = player();
        auto l = location(me);
        if (!l) return std::nullopt;
        auto rot = call_reflected(me, STR("K2_GetActorRotation"));
        double yaw = rot ? get(rot->get(L"ReturnValue"), L"Yaw").number() : 0;
        double a = (yaw + side) * 3.14159265358979323846 / 180.0;
        Vec3 at{l->x + std::cos(a) * distance, l->y + std::sin(a) * distance, l->z};
        if (auto g = ground(at.x, at.y, at.z)) at.z = *g;
        return at;
    }
} // namespace wcmods
