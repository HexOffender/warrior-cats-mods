// Map.hpp: the HUD's quest pieces, markers on the minimap and the world map, the clock held at an hour, the places your
// cat can travel to, and the exploration camera. As Lua's Game.hud, Game.mapMarker and Game.time.hold
// (docs/scripting.md), which the first three follow. Game thread only. WCMods.hpp includes it; docs/SDK.md, "C++ mods",
// documents every call.
//
//   wcmods::hud_banner(wcmods::Banner::Begin, {.kind = L"Main Quest", .title = L"A Soft Nest", .text = L"New HudObjective"});
//   auto m = wcmods::map_marker(wcmods::Vec3{-16000, 13000, 1500}, L"search");   // m.remove() takes it off
//   wcmods::hold_time(6 * 3600);                                                  // the clock stays at 6:00
//   wcmods::set_camera({.distance = 300, .fov = 60});                             // the camera far and narrow
#pragma once

#include <chrono>
#include <cmath>
#include <filesystem>
#include <format>
#include <functional>
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
    namespace detail
    {
        // What unlock_place set this session, by the save slot it was set on and the place's tag, and when: the save
        // file has it only once the game saves, and places() reads the file. A file written after it (the game saved
        // since: with this, or with what the game did to the place after) has the last word.
        struct UnlockedHere
        {
            bool unlocked{};
            std::filesystem::file_time_type at{};
        };
        inline auto unlocked_here() -> std::map<std::pair<int, std::wstring>, UnlockedHere>&
        {
            static std::map<std::pair<int, std::wstring>, UnlockedHere> set;
            return set;
        }
    } // namespace detail
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
            auto here = detail::unlocked_here().find({save_slot(), p.tag});
            if (here != detail::unlocked_here().end())
            {
                // The save read here is from a file the game wrote after the unlock: it has the last word.
                if (save.data && save.written > here->second.at) detail::unlocked_here().erase(here);
                else p.unlocked = here->second.unlocked;
            }
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

    // Unlock a place for your cat (or lock it again), as finding its checkpoint does: through the game's own
    // SetCheckpointUnlockState (signed), which writes the cat's save data and tells the map's markers and the
    // checkpoint. places() says so at once; the save file has it when the game next saves (save_game). False without
    // the function on this build, outside the world, or for a Place that isn't a checkpoint.
    inline auto unlock_place(const Place& place, bool unlocked = true) -> bool
    {
        if (!assert_game_thread(L"unlock_place") || !player() || place.tag.empty() || !place.checkpoint) return false;
        // (the checkpoint's tag, the save's UID for it; unlocked; the checkpoint, whose world names the save's level key)
        using SetUnlocked = void (*)(const RC::Unreal::FString*, bool, UObject*);
        auto set_unlocked = native<SetUnlocked>(L"Checkpoints:SetUnlocked");
        if (!set_unlocked || !detail::object_staying(place.checkpoint, nullptr)) return false;
        RC::Unreal::FString tag(place.tag.c_str());
        set_unlocked(&tag, unlocked, place.checkpoint);
        detail::unlocked_here()[{save_slot(), place.tag}] = {unlocked, std::filesystem::file_time_type::clock::now()};
        return true;
    }

    // ---- the world map's travel
    // The game travels only from its world map in travel mode, which a checkpoint's Interact opens (the "Travel" prompt;
    // the map key opens it without Travel). There, the place under the map's pointer is CurrentWidgetOverlapping, one of
    // HoverableWidgets (a WBP_GuiItemCheckPointMap_C for each unlocked place), and Travel (Confirm) takes your cat
    // there behind the game's own fade, the forest loaded first.
    namespace detail
    {
        // Where a place in the world is on the map's 4096-pixel picture (its MapCoordinates): the map's x runs with the
        // world's y, and its y against the world's x.
        inline auto map_point(UObject* map, const Vec3& at) -> std::pair<double, double>
        {
            auto c = [&](const wchar_t* n) { return get(map, std::wstring(L"MapCoordinates.") + n).number(); };
            const double w = c(L"MapWidth"), h = c(L"MapHeight");
            const double dx = c(L"WorldMaxX") - c(L"WorldMinX"), dy = c(L"WorldMaxY") - c(L"WorldMinY");
            if (dx == 0 || dy == 0) return {0, 0};
            return {c(L"MapOffsetX") + (at.y - c(L"WorldMinY")) / dy * w, c(L"MapOffsetY") + (c(L"WorldMaxX") - at.x) / dx * h};
        }
        // Press Travel once the map's own hover has the item under its pointer, checking every 0.1 s, `tries` more
        // times; when it never has (the map kept it off: a place at the map's edge, beyond its translation's limits),
        // says so in the log.
        inline auto press_travel(RC::Unreal::FWeakObjectPtr map, RC::Unreal::FWeakObjectPtr item, int tries) -> void
        {
            UObject* m = map.Get();
            if (!m) return;
            if (get(m, L"CurrentWidgetOverlapping").object == item.Get())
                ui::send(Widget(m), L"Button_Confirm");
            else if (tries > 0)
                after(0.1, [map, item, tries] { press_travel(map, item, tries - 1); });
            else
                log(L"map_travel: the world map didn't bring the place under its pointer, so Travel wasn't pressed");
        }
    } // namespace detail

    // Open the world map in travel mode as the game does: your cat's Interact, while it stands at an unlocked place's
    // checkpoint (within its prompt's reach). True when Interact was sent: the map is up a moment later, unless
    // something else in reach took the Interact (a cat to talk to); travel_map_item says whether it's there. False
    // anywhere else, or with a screen up.
    inline auto open_travel_map() -> bool
    {
        if (!assert_game_thread(L"open_travel_map") || !player() || !screens().empty()) return false;
        UObject* me = player();
        for (auto& p : places())
        {
            if (!p.unlocked) continue;
            // In its Interact sphere, where the game shows its Travel prompt.
            UObject* sphere = get(p.checkpoint, L"InteractComponent").object;
            auto in = call_reflected(sphere, STR("IsOverlappingActor"), [&](Params& q) { return q.set_nth(0, Value::of(me)); });
            if (in && in->get(L"ReturnValue").boolean()) return command(L"Player_Interact");
        }
        return false;
    }

    // The world map that shows, and the item on it for a place (one your cat has unlocked: the map makes those
    // hoverable), the nearest within 100 map pixels of where the place is; nullptr for either without.
    inline auto travel_map_item(const Place& place) -> std::pair<UObject*, UObject*>
    {
        if (!assert_game_thread(L"travel_map_item")) return {};
        UObject* map = ui::screen(L"GuiPopupWorldMap").object();
        if (!map || !place.checkpoint) return {map, nullptr};
        auto [x, y] = detail::map_point(map, place.at);
        UObject* best = nullptr;
        double best_d = 100;
        for (const Value& h : elements(map, L"HoverableWidgets"))
        {
            const double ix = get(h.object, L"RenderTransform.Translation.X").number();
            const double iy = get(h.object, L"RenderTransform.Translation.Y").number();
            const double d = std::hypot(ix - x, iy - y);
            if (h.object && d < best_d) best = h.object, best_d = d;
        }
        return {map, best};
    }

    // Travel to a place through the world map, the game's way: with the travel map up (open_travel_map), the map is
    // moved to put the place under its pointer, as moving it by hand does, and once the map has it there (its
    // CurrentWidgetOverlapping, a few frames on) Travel is pressed (Confirm: the map works out what's under its pointer
    // every frame, so setting CurrentWidgetOverlapping alone is undone; Button_A did nothing). The game fades out, loads
    // the forest there and
    // puts your cat at the checkpoint; for the place your cat is at, Travel is off and nothing happens. True when the map
    // was moved (Travel follows within a second, or a line in the log says why not). False without the map or before it
    // has drawn once, for a place it hasn't (locked: unlock_place first), or on a build wcmods hasn't the map's members for.
    inline auto map_travel(const Place& place) -> bool
    {
        if (!assert_game_thread(L"map_travel")) return false;
        auto [map, item] = travel_map_item(place);
        if (!map || !item) return false;
        constexpr const wchar_t* cls = L"/Script/Wrc.GuiPopupWorldMap";
        double* px = member<double>(map, cls, L"WCM_PointerX");
        double* py = member<double>(map, cls, L"WCM_PointerY");
        double* tx = member<double>(map, cls, L"WCM_TranslationX");
        double* ty = member<double>(map, cls, L"WCM_TranslationY");
        double* gx = member<double>(map, cls, L"WCM_TranslationToX");
        double* gy = member<double>(map, cls, L"WCM_TranslationToY");
        if (!px || !py || !tx || !ty || !gx || !gy || (*px == 0 && *py == 0)) return false;   // 0, 0: not drawn yet
        const double ix = get(item, L"RenderTransform.Translation.X").number();
        const double iy = get(item, L"RenderTransform.Translation.Y").number();
        *tx = *gx = *px - ix;
        *ty = *gy = *py - iy;
        RC::Unreal::FWeakObjectPtr weak_map(map), weak_item(item);
        after(0.1, [weak_map, weak_item] { detail::press_travel(weak_map, weak_item, 10); });
        return true;
    }

    // ============================================================================================ photo mode
    // The game's photo mode (WBP_GuiPopupPhotoMode_C), as the pause menu's Photo Mode opens it: its own camera
    // (PhotoModeCameraActor), moved by the player's sticks or keys; the filter, pose, effects, frame and guideline lists;
    // Hide UI and Exit. On PC it has no photo of its own (its Take photo is hidden): take_photo saves the view as the
    // engine's HighResShot does.
    namespace detail
    {
        inline auto photo_popup() -> UObject* { return ui::screen(L"GuiPopupPhotoMode").object(); }
        inline auto shown_widget(UObject* w) -> bool
        {
            if (!w) return false;
            const Visibility v = Widget(w).visibility();
            return v != Visibility::Collapsed && v != Visibility::Hidden;
        }
        // Which opening of photo mode is wanted: photo_mode(true) starts one, photo_mode(false) ends any still under way.
        inline auto photo_opening() -> int&
        {
            static int n = 0;
            return n;
        }
        // The opening photo_mode(false) last ended: its steps close the pause screen they opened.
        inline auto photo_cancelled() -> int&
        {
            static int n = -1;
            return n;
        }
        // On the pause screen (waited for while it comes up): to the General tab (Left, as its tab key), down its list
        // to Photo Mode, and Confirm, one press every 0.4 s (each released 0.3 s after it), up to `steps` tries. Gives
        // up, closing the pause screen and saying why in the log, when Photo Mode is off there (its CanvasDisabled
        // shows) or the tries run out; stops when photo_mode(false) came since (`opening` isn't the latest).
        inline auto pause_to_photo_mode(int steps, int opening, bool closing = false) -> void
        {
            UObject* pause = ui::screen(L"GuiScreenPause").object();
            if (opening != photo_opening())
            {
                // Ended by photo_mode(false): the pause screen it opened goes too, once it's up (asked again until it's
                // gone: one coming up takes no Back while it opens), and then nothing more: a pause screen opened later
                // is someone else's.
                if (opening != photo_cancelled() || steps <= 0 || (closing && !pause)) return;
                if (pause) ui::close(Widget(pause));
                after(0.4, [steps, opening, pause] { pause_to_photo_mode(steps - 1, opening, pause != nullptr); });
                return;
            }
            if (steps <= 0)
            {
                if (pause) ui::close(Widget(pause));
                log(L"photo_mode: the pause menu's Photo Mode couldn't be reached, so photo mode didn't open");
                return;
            }
            if (!pause)
            {
                after(0.4, [steps, opening] { pause_to_photo_mode(steps - 1, opening); });
                return;
            }
            Widget screen(pause);
            UObject* general = get(pause, L"mcGuiPanelGeneral").object;
            UObject* button = get(general, L"mcGuiButtonPhotoMode").object;
            if (get(pause, L"CurrentPanel").object == general && shown_widget(get(button, L"CanvasDisabled").object))
            {
                ui::close(screen);
                log(L"photo_mode: the pause menu's Photo Mode is off here, so photo mode didn't open");
                return;
            }
            const wchar_t* press = get(pause, L"CurrentPanel").object != general ? L"Button_Left"
                                 : shown_widget(get(button, L"CanvasSelected").object) ? L"Button_Confirm"
                                 : L"Button_Down";
            ui::send(screen, press);
            if (std::wstring_view(press) != L"Button_Confirm")
                after(0.4, [steps, opening] { pause_to_photo_mode(steps - 1, opening); });
        }
    } // namespace detail

    // Whether photo mode is up.
    inline auto in_photo_mode() -> bool { return assert_game_thread(L"in_photo_mode") && detail::photo_popup() != nullptr; }

    // Photo mode on, the game's way (the pause screen, then its Photo Mode: about two seconds), or off (its Exit, back
    // to play; an opening still under way stops). True when it was started or ended, or is already as asked (in_photo_mode
    // says when it's up: where the game has Photo Mode off, the pause screen closes again and the log says so); false
    // outside the world, in a fight, or with another screen up.
    inline auto photo_mode(bool on) -> bool
    {
        if (!assert_game_thread(L"photo_mode")) return false;
        if (!on) detail::photo_cancelled() = detail::photo_opening()++;
        if (UObject* p = detail::photo_popup()) return on || ui::send(Widget(p), L"Player_PhotoMode_Exit");
        if (!on) return true;
        if (!player() || !screens().empty() || !command(L"Player_Pause")) return false;
        const int opening = ++detail::photo_opening();
        after(0.5, [opening] { detail::pause_to_photo_mode(16, opening); });
        return true;
    }

    // Photo mode's menus and button hints hidden or shown again (its Hide UI); false outside photo mode.
    inline auto photo_mode_ui(bool shown) -> bool
    {
        if (!assert_game_thread(L"photo_mode_ui")) return false;
        UObject* p = detail::photo_popup();
        if (!p) return false;
        UObject* root = get(p, L"CanvasOver").object;
        if (detail::shown_widget(root) == shown) return true;
        return ui::send(Widget(p), L"Player_PhotoMode_HideUI");
    }

    // Photo mode's camera (a PhotoModeCameraActor), to read or move; nullptr outside photo mode.
    inline auto photo_camera() -> UObject*
    {
        if (!assert_game_thread(L"photo_camera")) return nullptr;
        return get(detail::photo_popup(), L"CameraActor").object;
    }

    // A picture of what the game shows, saved as the engine's HighResShot does, without the game's menus
    // (%LOCALAPPDATA%\Wrc\Saved\Screenshots\Windows\HighresScreenshotNNNNN.png, the next number each time), at the
    // window's size times `scale`. Works anywhere in the world; in photo mode it's photo mode's camera. True when the
    // command was given: the file is written a frame or two later (the engine says nothing back). False without a player
    // to give it.
    inline auto take_photo(int scale = 1) -> bool
    {
        if (!assert_game_thread(L"take_photo") || scale < 1 || scale > 4) return false;
        return console(std::format(L"HighResShot {}", scale).c_str());
    }
    inline auto photos_folder() -> std::filesystem::path { return save_path().parent_path().parent_path() / L"Screenshots" / L"Windows"; }

    // ============================================================================================ the camera
    // The exploration camera as it shows now: its actor (BP_AdventureCamera_C), how far it is from your cat (cm) and
    // the field of view shown (the engine's camera manager's, degrees). Its arm's length and the lens's field of view
    // are what the camera's own settings make them each frame (set_camera, below, changes those).
    struct CameraView
    {
        UObject* actor{};
        double distance{}, fov{};
    };
    namespace detail
    {
        // The exploration camera that follows your cat: one still in the world (a level change leaves the old one
        // behind until it's collected) whose TargetActor is player().
        inline auto exploration_camera() -> UObject*
        {
            UObject* me = player();
            if (!me) return nullptr;
            for (UObject* c : find_all(STR("SwtAdventureCameraActor")))
                if (object_staying(c, nullptr) && get(c, L"TargetActor").object == me) return c;
            return nullptr;
        }
    } // namespace detail
    inline auto camera() -> std::optional<CameraView>
    {
        if (!assert_game_thread(L"camera")) return std::nullopt;
        UObject* cam = detail::exploration_camera();
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

    // The exploration camera's settings: what its update turns into the arm's length, its tilt and the lens's field of
    // view each frame, and how it follows and turns. Each is the game's from TuningData (Gameplay.Exploration.Camera.*)
    // until a mod sets it; the defaults on build 26337109 are in brackets. The camera eases to a new distance, tilt or
    // field of view (its interpolators, about a second); lag takes at once.
    struct CameraSettings
    {
        std::optional<double> distance;        // the arm's length while exploring, cm (113): BoomArmTargetLength
        std::optional<double> fov;             // the lens's field of view, degrees (90): the camera's own, not a key
        std::optional<double> pitch;           // the arm's tilt, degrees, below 0 looking down (-5): BoomArmRotation.Pitch
        std::optional<double> speed_distance;  // added to the distance at a run (45): SpeedExtraArmTargetLength
        std::optional<double> speed_fov;       // added to the field of view at a run (5): SpeedFov
        std::optional<double> lag;             // how fast it catches up with your cat, 0 at once (10): Lag.Location.Vertical
        std::optional<double> rotation_lag;    // how fast it turns after a turn, 0 at once (5): Lag.Rotation
        // Turning with the mouse and stick, which your cat's exploration component does: degrees a second at full
        // tilt (55 and 120), and the pitch it stays within (-20 and 23).
        std::optional<double> turn_yaw, turn_pitch, pitch_min, pitch_max;
    };

    namespace detail
    {
        inline constexpr const wchar_t* camera_class = L"/Script/SwtAdventure.SwtAdventureCameraActor";
        inline constexpr int camera_fields = 11;
        // Each setting's member: the camera's, or (turning) the exploration component's. nullptr when this build's
        // offsets.json hasn't got it, or there's no such object.
        inline auto camera_member(UObject* cam, UObject* explore, int which) -> float*
        {
            switch (which)
            {
            case 0: return member<float>(cam, camera_class, L"WCM_ArmLength");
            case 1: return member<float>(cam, camera_class, L"WCM_Fov");
            case 2: return member<float>(cam, camera_class, L"WCM_ArmPitch");
            case 3: return member<float>(cam, camera_class, L"WCM_SpeedArmLength");
            case 4: return member<float>(cam, camera_class, L"WCM_SpeedFov");
            case 5: return member<float>(cam, camera_class, L"WCM_LagVertical");
            case 6: return member<float>(cam, camera_class, L"WCM_LagRotation");
            case 7: return member<float>(explore, exploration_class, L"WCM_TurnYaw");
            case 8: return member<float>(explore, exploration_class, L"WCM_TurnPitch");
            case 9: return member<float>(explore, exploration_class, L"WCM_PitchMin");
            case 10: return member<float>(explore, exploration_class, L"WCM_PitchMax");
            }
            return nullptr;
        }
        inline auto camera_field(CameraSettings& s, int which) -> std::optional<double>&
        {
            std::optional<double>* fields[camera_fields] = {&s.distance, &s.fov, &s.pitch, &s.speed_distance, &s.speed_fov,
                                                            &s.lag, &s.rotation_lag, &s.turn_yaw, &s.turn_pitch,
                                                            &s.pitch_min, &s.pitch_max};
            return *fields[which];
        }
        // What the camera had before this mod first set it, for reset_camera.
        inline auto camera_kept() -> Kept<CameraSettings>&
        {
            static Kept<CameraSettings> kept;
            return kept;
        }
        inline auto read_camera(UObject* cam, UObject* explore) -> CameraSettings
        {
            CameraSettings s;
            for (int i = 0; i < camera_fields; ++i)
                if (float* m = camera_member(cam, explore, i)) camera_field(s, i) = *m;
            return s;
        }
        // The spring arm takes the lag once, in the camera's BeginPlay: lag on while either location lag isn't 0, at
        // the vertical one's speed; rotation lag on while it isn't 0. False when the arm didn't take one of them.
        inline auto apply_lag(UObject* cam) -> bool
        {
            UObject* arm = get(cam, L"AdventureArmComponent").object;
            float* lag = member<float>(cam, camera_class, L"WCM_LagVertical");
            float* side = member<float>(cam, camera_class, L"WCM_LagHorizontal");
            float* turn = member<float>(cam, camera_class, L"WCM_LagRotation");
            if (!arm || !lag || !side || !turn) return false;
            bool ok = set(arm, L"bEnableCameraLag", *lag != 0 || *side != 0);
            ok = set(arm, L"CameraLagSpeed", static_cast<double>(*lag)) && ok;
            ok = set(arm, L"bEnableCameraRotationLag", *turn != 0) && ok;
            return set(arm, L"CameraRotationLagSpeed", static_cast<double>(*turn)) && ok;
        }
    } // namespace detail

    // The camera's settings now (the turning ones too while your cat has its exploration component); nullopt with no
    // exploration camera following your cat (in a fight, a scene, the menus) or on a build wcmods hasn't the camera's
    // settings for.
    inline auto camera_settings() -> std::optional<CameraSettings>
    {
        if (!assert_game_thread(L"camera_settings")) return std::nullopt;
        UObject* cam = detail::exploration_camera();
        if (!cam || !member<float>(cam, detail::camera_class, L"WCM_ArmLength")) return std::nullopt;
        return detail::read_camera(cam, detail::exploration_control());
    }

    // Set the settings given (the rest stay as they are) on the camera following your cat. The first set keeps what
    // the camera had, for reset_camera. False with no exploration camera, or when a setting given has nowhere to go on
    // this build (nothing is set then), or the spring arm didn't take the lag. Lasts while the camera does: a level's
    // new camera starts from the game's again.
    //   wcmods::set_camera({.distance = 300, .fov = 60, .pitch = -35});   // far, narrow, looking down
    inline auto set_camera(const CameraSettings& settings) -> bool
    {
        if (!assert_game_thread(L"set_camera")) return false;
        UObject* cam = detail::exploration_camera();
        if (!cam) return false;
        UObject* explore = detail::exploration_control();
        CameraSettings given = settings;
        for (int i = 0; i < detail::camera_fields; ++i)
            if (detail::camera_field(given, i) && !detail::camera_member(cam, explore, i)) return false;
        detail::camera_kept().keep(cam, [&] { return detail::read_camera(cam, explore); });
        for (int i = 0; i < detail::camera_fields; ++i)
            if (auto& v = detail::camera_field(given, i)) *detail::camera_member(cam, explore, i) = static_cast<float>(*v);
        return !(settings.lag || settings.rotation_lag) || detail::apply_lag(cam);
    }

    // Put back what the camera had before this mod first set it. True when there's nothing to put back (never set, or
    // the camera it was set on is gone: a new one has the game's settings); false with no exploration camera, or when
    // what it had can't all go back now (kept for another try).
    inline auto reset_camera() -> bool
    {
        if (!assert_game_thread(L"reset_camera")) return false;
        UObject* cam = detail::exploration_camera();
        if (!cam) return false;
        return detail::camera_kept().put_back(cam, [](const CameraSettings& before) { return set_camera(before); });
    }
} // namespace wcmods
