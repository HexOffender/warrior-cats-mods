// Map.hpp: the HUD's quest pieces, markers on the minimap and the world map, the clock held at an hour, the places your
// cat can travel to, and the exploration camera. As Lua's Game.hud, Game.mapMarker and Game.time.hold
// (docs/scripting.md), which the first three follow. Game thread only. WCMods.hpp includes it; docs/SDK.md, "C++ mods",
// documents every call.
//
//   wcmods::hud_banner(wcmods::Banner::Begin, {.kind = L"Main Quest", .title = L"A Soft Nest", .text = L"New HudObjective"});
//   auto m = wcmods::map_marker(wcmods::Vec3{-16000, 13000, 1500}, L"search");   // m.remove() takes it off
//   wcmods::hold_time(6 * 3600);                                                  // the clock stays at 6:00
#pragma once

#include <cmath>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/Ui.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // ============================================================================================ the HUD's quest pieces
    // The game shows these only for its own quests and takes them back for those; for a mod's, nothing of the game's
    // touches them, so the mod puts them away (worked out for Lua on 2026-10-27).
    namespace detail
    {
        inline auto play_widget_animation(UObject* widget, const wchar_t* animation) -> bool
        {
            UObject* anim = get(widget, animation).object;
            if (!widget || !anim) return false;
            return call_reflected(widget, STR("PlayAnimation"), [&](Params& p) {
                       p.set_nth(0, Value::of(anim));
                       p.set_nth(1, Value::of(0.0));   // StartAtTime
                       p.set_nth(2, Value::of(1));     // NumLoopsToPlay
                       p.set_nth(3, Value::of(0));     // PlayMode: forward
                       p.set_nth(4, Value::of(1.0));   // PlaybackSpeed
                       p.set_nth(5, Value::of(false)); // bRestoreState
                   }).has_value();
        }
        inline auto loaded(std::wstring_view path) -> UObject*
        {
            if (path.empty()) return nullptr;
            if (UObject* o = object(std::wstring(path).c_str())) return o;
            return load(path);   // by its whole path: loading the package alone isn't enough
        }
        struct ObjectiveState
        {
            UObject* on{};   // the HUD the panel was put on (a new HUD starts without it)
        };
        inline auto objective_state() -> ObjectiveState&
        {
            static ObjectiveState s;
            return s;
        }
    } // namespace detail

    // One of the objective panel's goals: its name, its progress ("1/2"), an icon (a texture's object path) and whether
    // it's done (its tick).
    struct HudGoal
    {
        std::wstring name, progress, icon;
        bool done{};
    };
    // The objective panel (on the left of the HUD): the quest's title, where it is, what to do now and up to three goals.
    struct HudObjective
    {
        std::wstring title, location, activity;
        std::vector<HudGoal> goals;
    };
    // Put the objective panel up with these words, as the game does for its quests (its show animation the first time
    // on this HUD). False without the HUD (in a menu, or loading).
    inline auto hud_objective(const HudObjective& spec) -> bool
    {
        if (!assert_game_thread(L"hud_objective")) return false;
        Widget hud = ui::hud();
        Widget o = hud ? hud.find(L"mcGuiQuestObjective") : Widget();
        if (!o) return false;
        o.find(L"mcGuiTitle").set_text(spec.title);
        o.find(L"mcGuiActivity").set_text(spec.activity);
        o.find(L"mcGuiLocation").set_text(spec.location);
        Widget where = o.find(L"CanvasLocation");
        if (where) spec.location.empty() ? where.collapse() : where.show_passive();
        for (int i = 0; i < 3; ++i)
        {
            Widget g = o.find(L"mcGuiGoal" + std::to_wstring(i + 1));
            if (!g) continue;
            if (i >= static_cast<int>(spec.goals.size()))
            {
                g.collapse();
                continue;
            }
            const HudGoal& goal = spec.goals[static_cast<size_t>(i)];
            g.find(L"mcGuiGoalName").set_text(goal.name);
            g.find(L"mcGuiGoalValues").set_text(goal.progress);
            Widget tick = g.find(L"CanvasCheck");
            if (tick) goal.done ? tick.show_passive() : tick.collapse();
            Widget icon = g.find(L"mcGuiIcon");
            UObject* t = detail::loaded(goal.icon);
            if (icon && t) icon.set_image(t);
            if (icon) t ? icon.show_passive() : icon.collapse();
            g.show_passive();
        }
        auto& state = detail::objective_state();
        if (state.on != hud.object())
        {
            o.show_passive();
            detail::play_widget_animation(o.object(), L"AniMessageShow");
            state.on = hud.object();
        }
        return true;
    }
    // Put the objective panel away (its hide animation, then hidden). False without the HUD.
    inline auto hide_objective() -> bool
    {
        if (!assert_game_thread(L"hide_objective")) return false;
        Widget hud = ui::hud();
        Widget o = hud ? hud.find(L"mcGuiQuestObjective") : Widget();
        if (!o) return false;
        auto& state = detail::objective_state();
        if (state.on == hud.object())
        {
            detail::play_widget_animation(o.object(), L"AniMessageHide");
            UObject* panel = o.object();
            UClass* was = panel->GetClassPrivate();
            after(0.5, [panel, was] {   // the HUD can go in the meantime (a level change): only while it's still there
                if (detail::object_staying(panel, was) && detail::objective_state().on != ui::hud().object()) Widget(panel).collapse();
            });
        }
        state.on = nullptr;
        return true;
    }
    // The objective panel's words as shown now (its title, where, what to do), for checking.
    inline auto hud_objective_shown() -> std::optional<HudObjective>
    {
        if (!assert_game_thread(L"hud_objective_shown")) return std::nullopt;
        Widget hud = ui::hud();
        Widget o = hud ? hud.find(L"mcGuiQuestObjective") : Widget();
        if (!o || !o.visible()) return std::nullopt;
        HudObjective s;
        s.title = o.find(L"mcGuiTitle").text();
        s.activity = o.find(L"mcGuiActivity").text();
        s.location = o.find(L"mcGuiLocation").text();
        for (int i = 1; i <= 3; ++i)
        {
            Widget g = o.find(L"mcGuiGoal" + std::to_wstring(i));
            if (!g || !g.visible()) continue;
            s.goals.push_back({g.find(L"mcGuiGoalName").text(), g.find(L"mcGuiGoalValues").text(), L"", g.find(L"CanvasCheck").visible()});
        }
        return s;
    }

    // The game's quest banners, with their particles: a quest taken up (its kind, "Main Quest", its title and a line,
    // "New HudObjective"), updated ("Quest Update"), done ("Quest completed!") or failed.
    enum class Banner { Begin, Update, Done, Failed };
    struct BannerText
    {
        std::wstring kind, title, text;
        double seconds{4.5};   // how long it stays (the game's own code takes it away only for its own quests)
    };
    namespace detail
    {
        inline auto banner_part(Banner b) -> const wchar_t*
        {
            switch (b)
            {
            case Banner::Begin: return L"mcGuiBeginQuestMessage";
            case Banner::Update: return L"mcGuiQuestUpdateMessage";
            case Banner::Done: return L"mcGuiQuestCompetedMessage";   // (sic)
            case Banner::Failed: return L"mcGuiQuestFailedMessage";
            }
            return L"";
        }
        inline auto banner_shows() -> std::map<int, uint64_t>&
        {
            static std::map<int, uint64_t> shows;   // each banner's latest showing, so an older timer leaves it
            return shows;
        }
    } // namespace detail
    // Show one of the banners, its words those given (each left as the game has it when empty). False without the HUD.
    inline auto hud_banner(Banner which, const BannerText& words = {}) -> bool
    {
        if (!assert_game_thread(L"hud_banner")) return false;
        Widget hud = ui::hud();
        Widget b = hud ? hud.find(detail::banner_part(which)) : Widget();
        if (!b) return false;
        const std::pair<const wchar_t*, const std::wstring*> texts[] = {{L"mcGuiTextQuestType", &words.kind},
                                                                       {L"mcGuiTextQuestName", &words.title},
                                                                       {L"mcGuiTextObjective", &words.text},
                                                                       {L"mcGuiText", &words.text}};
        for (auto& [block, text] : texts)
            if (!text->empty())
                if (Widget t = b.find(block)) t.set_text(*text);
        b.show_passive();
        call_reflected(b.object(), STR("SequenceEvent"));
        const uint64_t mine = ++detail::banner_shows()[static_cast<int>(which)];
        UObject* banner = b.object();
        UClass* was = banner->GetClassPrivate();
        after(words.seconds, [banner, was, which, mine] {   // only while the HUD is still there (a level change takes it)
            if (detail::banner_shows()[static_cast<int>(which)] == mine && detail::object_staying(banner, was)) Widget(banner).collapse();
        });
        return true;
    }
    // A banner's words as shown now (each of its text blocks by name), or nullopt while it's hidden.
    inline auto hud_banner_shown(Banner which) -> std::optional<std::map<std::wstring, std::wstring>>
    {
        if (!assert_game_thread(L"hud_banner_shown")) return std::nullopt;
        Widget hud = ui::hud();
        Widget b = hud ? hud.find(detail::banner_part(which)) : Widget();
        if (!b || !b.visible()) return std::nullopt;
        std::map<std::wstring, std::wstring> out;
        for (auto& t : b.find_all(L"TextBlock")) out[t.name()] = t.text();
        return out;
    }

    // ============================================================================================ map markers
    // The game's own point of interest (SwtAdventurePOIComponent), as its quest givers and dens have: on the minimap
    // (kept at its edge when it's further off, with `border`) and on the world map (with `on_map`). Its icon is one of
    // the game's by name (L"search", L"talk", L"barter", L"freshkill", L"trainer", L"den", L"outpost", L"skirmish",
    // L"madcat", or a clan: L"shadowclan"...) or a material's object path.
    struct MarkerOptions
    {
        bool border{true}, on_map{true};
    };
    struct MapMarker
    {
        UObject* actor{};       // what it's on: an actor of its own at a place, or the actor given
        UObject* component{};   // the game's POI component
        bool owned{};           // the actor is the marker's own
        UClass* actor_class{};  // what they were, to tell they're still there (the game can take an actor away)
        UClass* component_class{};
        explicit operator bool() const { return component != nullptr; }
        // Whether it's still in the world (its actor and component not destroyed).
        auto valid() const -> bool
        {
            return detail::object_staying(actor, actor_class) && detail::object_staying(component, component_class);
        }
        // Take it off: its own actor goes, or the component comes off the actor it was put on. Safe to call twice.
        auto remove() -> void;
        // Move a marker of its own place (one on an actor goes where the actor goes).
        auto move_to(Vec3 at) -> bool;
    };
    namespace detail
    {
        inline auto marker_icon(std::wstring_view icon) -> UObject*
        {
            static const std::map<std::wstring, std::wstring, std::less<>> icons = {
                {L"search", L"MI_UI_IconSearch"},       {L"talk", L"MI_UI_IconGossip"},           {L"barter", L"MI_UI_IconBarter"},
                {L"freshkill", L"MI_UI_IconFreshkill"}, {L"trainer", L"MI_UI_IconTrainer"},       {L"den", L"MI_UI_IconDenVisit"},
                {L"outpost", L"MI_UI_IconOutpost"},     {L"skirmish", L"MI_UI_IconSkirmish"},     {L"madcat", L"MI_UI_IconMadCat"},
                {L"thunderclan", L"MI_UI_Icon_Thunderclan"}, {L"riverclan", L"MI_UI_Icon_Riverclan"},
                {L"windclan", L"MI_UI_Icon_Windclan"},  {L"shadowclan", L"MI_UI_Icon_Shadowclan"}};
            auto it = icons.find(icon.empty() ? std::wstring_view(L"search") : icon);
            if (it == icons.end()) return loaded(icon);
            return loaded(L"/Game/Art/UXD/Materials/MaterialInstances/" + it->second + L"." + it->second);
        }
        inline auto add_poi(UObject* actor, Vec3 relative, std::wstring_view icon, const MarkerOptions& o) -> UObject*
        {
            UObject* cls = object(STR("/Script/SwtAdventure.SwtAdventurePOIComponent"));
            if (!actor || !cls) return nullptr;
            auto made = call_reflected(actor, STR("AddComponentByClass"), [&](Params& p) {
                p.set_nth(0, Value::of(cls));
                p.set_nth(1, Value::of(false));
                transform_of(p, L"RelativeTransform", relative, 0);
                p.set_nth(3, Value::of(true));   // deferred: finished below, once it's set up
            });
            UObject* c = made ? made->get(L"ReturnValue").object : nullptr;
            if (!c) return nullptr;
            set(c, L"bStickPOIToBorder", o.border);
            set(c, L"bShowPOIAtBegin", true);
            set(c, L"bShouldShowIcon", true);
            set(c, L"bCanAppearOnWorldMap", o.on_map);
            if (UObject* mat = marker_icon(icon)) set(c, L"CustomPOIIcon", mat);
            call_reflected(actor, STR("FinishAddComponent"), [&](Params& p) {
                p.set_nth(0, Value::of(c));
                p.set_nth(1, Value::of(false));
                transform_of(p, L"RelativeTransform", relative, 0);
            });
            return c;
        }
    } // namespace detail
    // A marker at a place: an actor of its own there. An empty MapMarker outside the world.
    inline auto map_marker(Vec3 at, std::wstring_view icon = L"search", MarkerOptions options = {}) -> MapMarker
    {
        MapMarker m;
        if (!assert_game_thread(L"map_marker") || !player()) return m;
        // A plain Actor has no root to put the place on: the POI component, added while it's spawned (as the Lua's
        // does), is its root at `at`.
        UObject* comp = nullptr;
        UObject* actor = detail::spawn_deferred(object(STR("/Script/Engine.Actor")), at, 0, [&](UObject* a) {
            comp = detail::add_poi(a, at, icon, options);
        });
        if (!actor) return m;
        m.actor = actor;
        m.component = comp;
        m.owned = true;
        m.actor_class = actor->GetClassPrivate();
        m.component_class = comp ? comp->GetClassPrivate() : nullptr;
        if (!m.component) m.remove();
        return m;
    }
    // A marker on an actor (a cat, an animal, anything in the world): it follows it.
    inline auto map_marker(UObject* actor, std::wstring_view icon = L"search", MarkerOptions options = {}) -> MapMarker
    {
        MapMarker m;
        // An actor kept from earlier may be gone (a level change): calling into it would crash the game.
        if (!assert_game_thread(L"map_marker") || !detail::object_staying(actor, nullptr) || !location(actor)) return m;
        m.component = detail::add_poi(actor, {0, 0, 0}, icon, options);
        if (!m.component) return m;
        m.actor = actor;
        m.actor_class = actor->GetClassPrivate();
        m.component_class = m.component->GetClassPrivate();
        return m;
    }
    inline auto MapMarker::remove() -> void
    {
        if (owned && detail::object_staying(actor, actor_class)) call_reflected(actor, STR("K2_DestroyActor"));
        else if (valid()) call_reflected(component, STR("K2_DestroyComponent"), [&](Params& p) { p.set_nth(0, Value::of(component)); });
        actor = component = nullptr;
    }
    inline auto MapMarker::move_to(Vec3 at) -> bool
    {
        return owned && valid() && teleport(actor, at);
    }
    // The game's markers in the world now (its POI components: its quest givers', dens', a mod's own).
    inline auto map_marker_count() -> int
    {
        if (!assert_game_thread(L"map_marker_count")) return 0;
        int n = 0;
        // Not the ones taken off: a destroyed one stays in the engine's objects, marked as garbage, until it's collected.
        for (UObject* c : find_all(STR("SwtAdventurePOIComponent")))
            n += full_name(c).find(L"Default__") == std::wstring::npos && detail::object_staying(c, nullptr);
        return n;
    }

    // ============================================================================================ the clock held
    // Keep the clock at a time of day (seconds into it: 21600 is 6:00) while your cat is in the world, set again every
    // frame (the game's clock runs about 70 times real time, so twice a second, as the Lua's hold does, lets it run
    // half a minute ahead between sets); hold_time(nullopt) lets go. One hold for the mod (a second call moves it). A
    // Lua script's Game.time.hold is its own: a C++ and a Lua hold at once each set the clock, by turns.
    namespace detail
    {
        struct ClockHold
        {
            std::optional<int> at;
            bool hooked{};   // every_frame's callback, made once (it can't be taken off): it does nothing without a hold
        };
        inline auto clock_hold() -> ClockHold&
        {
            static ClockHold h;
            return h;
        }
    } // namespace detail
    inline auto hold_time(std::optional<int> seconds) -> bool
    {
        if (!assert_game_thread(L"hold_time")) return false;
        auto& h = detail::clock_hold();
        if (!seconds)
        {
            h.at.reset();
            return true;
        }
        h.at = ((*seconds % 86400) + 86400) % 86400;
        if (!h.hooked)
        {
            h.hooked = true;
            every_frame([](float) {
                auto& hold = detail::clock_hold();
                if (!hold.at || !player()) return;
                if (float* s = day_seconds()) *s = static_cast<float>(*hold.at);
            });
        }
        float* s = day_seconds();
        if (!s) return false;
        *s = static_cast<float>(*h.at);
        return true;
    }
    // The time of day this mod holds the clock at (seconds), or nullopt.
    inline auto time_held() -> std::optional<int> { return detail::clock_hold().at; }

    // ============================================================================================ places and travel
    // The places your cat can travel to: the game's checkpoints (SwtQuestCheckpoint), each clan's camp and outposts,
    // the Moonpool's and the island's. Each with its actor, tag (Gameplay.Checkpoints.Shadowclan.0), zone code ("S-09"),
    // where it is, whether it's open from the start, and whether your cat has it (unlocked: from your cat's slot of
    // the save, GameplayProgression/<level>/Checkpoints, as of its last save). The game's own travel is its world map's,
    // opened by Interact at a checkpoint (WBP_GuiPopupWorldMap_C), with the place picked by the map's pointer.
    struct Place
    {
        UObject* checkpoint{};
        std::wstring tag, zone;
        Vec3 at{};
        bool at_start{}, unlocked{};
    };
    inline auto places() -> std::vector<Place>
    {
        std::vector<Place> out;
        if (!assert_game_thread(L"places")) return out;
        const auto save = detail::read_save();   // the file's data, held, not copied
        static const Json none;
        const Json& slot = save.data ? detail::slot_of(*save.data) : none;
        std::map<std::wstring, bool> open;
        for (auto& level : slot["GameplayProgression"].values())
            for (auto& c : level["Checkpoints"].values()) open[c["UID"].wstring()] = c["Unlocked"].number() != 0;
        for (UObject* c : find_all(STR("SwtQuestCheckpoint")))
        {
            if (full_name(c).find(L"Default__") != std::wstring::npos) continue;
            auto at = location(c);
            if (!at) continue;
            Place p;
            p.checkpoint = c;
            p.tag = get(c, L"CheckpointTag.TagName").string();
            p.zone = get(c, L"ZoneCode").string();
            p.at = *at;
            p.at_start = get(c, L"bAvailableAtStart").boolean();
            auto it = open.find(p.tag);
            p.unlocked = it != open.end() ? it->second : p.at_start;
            out.push_back(std::move(p));
        }
        return out;
    }
    // Take your cat to a place it has (unlocked), where the game's travel brings it: the checkpoint. False for one it
    // hasn't got, outside the world or in a fight (player() is nullptr then), or with one of the game's screens up (the
    // map, a menu, a den's popup: the game travels only from its map, which closes first). (A put, not the map's
    // travel: there's no loading screen; the forest streams in.)
    inline auto travel(const Place& place) -> bool
    {
        if (!assert_game_thread(L"travel") || !player() || !place.checkpoint || !place.unlocked || !screens().empty()) return false;
        return teleport(player(), {place.at.x, place.at.y, place.at.z + 50});
    }

    // ============================================================================================ the camera
    // The exploration camera as it shows now: its actor (BP_AdventureCamera_C), how far it is from your cat (cm) and
    // the field of view shown (the engine's camera manager's, degrees). Its arm's length and the lens's field of view
    // are what the camera's own settings make them each frame (TuningData's Gameplay.Exploration.Camera.*, read when
    // it starts): writing them, even every frame, changed nothing seen (docs/reverse-engineering.md, "The exploration
    // camera"), so there's no setter yet.
    struct CameraView
    {
        UObject* actor{};
        double distance{}, fov{};
    };
    inline auto camera() -> std::optional<CameraView>
    {
        if (!assert_game_thread(L"camera")) return std::nullopt;
        UObject* cam = find_first(STR("SwtAdventureCameraActor"));
        UObject* lens = cam ? get(cam, L"CameraComponent").object : nullptr;
        auto me = location(player());
        auto r = lens ? call_reflected(lens, STR("K2_GetComponentLocation")) : std::nullopt;
        if (!cam || !me || !r) return std::nullopt;
        Value v = r->get(L"ReturnValue");
        CameraView view;
        view.actor = cam;
        const double dx = get(v, L"X").number() - me->x, dy = get(v, L"Y").number() - me->y, dz = get(v, L"Z").number() - me->z;
        view.distance = std::sqrt(dx * dx + dy * dy + dz * dz);
        auto f = call_reflected(get(controller(), L"PlayerCameraManager").object, STR("GetFOVAngle"));
        view.fov = f ? f->get(L"ReturnValue").number() : 0;
        return view;
    }
} // namespace wcmods
