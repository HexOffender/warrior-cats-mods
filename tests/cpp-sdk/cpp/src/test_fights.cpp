// Fights (Story.hpp), on request ("fights"), for tests/game/test_cpp_sdk.py, which backs the save up first and puts it
// back after (fights give experience and rewards). Four fights with the nearest roaming animal, each started the
// player's way: won by damage a Damage handler multiplies (a poison given on the way: the Status event), won with
// end_fight(true), fled, and lost with end_fight(false); the five fight events counted.
#include "checks.hpp"

#include <cmath>
#include <functional>
#include <memory>
#include <string>

namespace t
{
    namespace
    {
        int damage_events = 0, turn_events = 0, status_events = 0, start_events = 0, end_events = 0;
        Json dilemmas = Json::array();   // each dilemma answered: what it asked, and the code the game's event gave
        int boost = 0;   // hits on an enemy multiplied by this
        bool hooked = false;
        Json hits = Json::array();

        auto health_of(Fighter f) -> double
        {
            Resource hp = resource(f.actor(), STR("SwtQuestHealthComponent"));
            return hp ? *hp.value : -1;
        }
        auto events() -> Json
        {
            Json o = Json::object();
            o.set("start", Json(start_events));
            o.set("end", Json(end_events));
            o.set("damage", Json(damage_events));
            o.set("turn", Json(turn_events));
            o.set("status", Json(status_events));
            return o;
        }
        // Run `then` once `cond` holds (looked at every half second), or with false after `seconds`.
        auto when(std::function<bool()> cond, double seconds, std::function<void(bool)> then) -> void
        {
            auto left = std::make_shared<double>(seconds);
            auto tick = std::make_shared<std::function<void()>>();
            *tick = [cond, then, left, tick] {
                if (cond()) return then(true);
                if ((*left -= 0.5) <= 0) return then(false);
                after(0.5, *tick);
            };
            after(0.5, *tick);
        }
        // A fight with one of the nearest animals (up to three tried: they roam, and a pounce can miss); `then(started)`
        // once the fight menu is up (your cat's first turn).
        auto begin(std::string label, std::function<void(bool)> then, int attempt = 0) -> void
        {
            auto animals = fight_animals(20000);
            value("fights." + label + ".animals", static_cast<int>(animals.size()));
            if (attempt >= 3 || static_cast<int>(animals.size()) <= attempt || !start_fight(animals[attempt])) return then(false);
            value("fights." + label + ".attempts", attempt + 1);
            // A fight takes a few seconds to come up, longer while the computer is busy: 12 s before the next animal (5
            // gave up on fights still loading, and the next try was then refused with your cat already in one).
            when([] { return combat_active(); }, 12, [label, then, attempt](bool fighting) {
                if (!fighting) return begin(label, then, attempt + 1);
                when([] { return static_cast<bool>(fight_menu()); }, 10, then);
            });
        }
        auto over(std::string label, std::function<void()> then) -> void
        {
            // A side at 0 falls at the next action: when the menu is back with every enemy down, one more attack.
            auto nudged = std::make_shared<int>(0);
            when([nudged, label] {
                if (!combat_active()) return true;
                // A dilemma at a fight's end (Dilemma13 or 14, by chance): read, and answered (the second choice in
                // the "win" fight, the first otherwise).
                if (auto d = dilemma())
                {
                    static UObject* answered = nullptr;
                    UObject* popup = ui::screen(L"WBP_GuiPopupDilemma_C").object();
                    if (popup != answered)
                    {
                        answered = popup;
                        Json x = Json::object();
                        x.set("fight", Json(label));
                        x.set("title", Json(text(d->title)));
                        x.set("question", Json(text(d->question)));
                        x.set("option1", Json(text(d->option1)));
                        x.set("option2", Json(text(d->option2)));
                        x.set("selected_at_first", Json(detail::dilemma_selected(popup)));
                        x.set("answered", Json(answer_dilemma(label == "win" ? 1 : 0)));
                        dilemmas.push(x);
                    }
                    return false;
                }
                bool down = !fight_enemies().empty();
                for (auto& f : fight_enemies()) down = down && health_of(f) <= 0;
                if (down && fight_menu() && *nudged < 2 && fight_attack(0)) ++*nudged;
                return false;
            }, 40, [label, then, nudged](bool ended) {
                value("fights." + label + ".nudged", *nudged);
                if (!ended)
                {
                    std::wstring all;
                    for (auto& sname : screens()) all += sname + L" ";
                    value("fights." + label + ".stuck_screens", text(all));
                    Json hp = Json::array();
                    for (auto& f : fight_enemies()) hp.push(Json(health_of(f)));
                    value("fights." + label + ".stuck_enemies", hp);
                }
                value("fights." + label + ".ended", ended);
                value("fights." + label + ".events", events());
                if (auto h = resource(player(), STR("SwtQuestHealthComponent"))) value("fights." + label + ".cat_health", *h.value);
                after(3.0, then);   // the game's own ending (rewards, the respawn) settles
            });
        }
    } // namespace

    auto run_fights_request() -> void
    {
        phase("fights");
        if (!hooked)
        {
            on(Event::Damage, [](const EventInfo& e) {
                damage_events++;
                UObject* who = get(e.a, L"Character").object;
                const int dmg = static_cast<int>(get(e.a, L"Damage").number());
                if (boost && who && who != player()) set(e.a, L"Damage", dmg * boost);   // changed before the game applies it
                hits.push(Json(text(std::format(L"{} {} -> {}", who == player() ? L"cat" : L"enemy", dmg, get(e.a, L"Damage").number()))));
            });
            on(Event::TurnEnded, [](const EventInfo&) { turn_events++; });
            on(Event::Status, [](const EventInfo&) { status_events++; });
            on(Event::CombatStart, [](const EventInfo&) { start_events++; });
            on(Event::CombatEnd, [](const EventInfo&) { end_events++; });

            hooked = true;
        }
        expect("fights.no_dilemma", !dilemma() && !answer_dilemma(0));
        expect("fights.refused", !start_fight(nullptr) && !end_fight(true) && !flee() && !fight_attack(0) && !apply_status(nullptr, L"Poisoned"));
        // ----- 1: won by damage a Damage handler multiplies; a poison on the enemy on the way
        begin("damage", [](bool started) {
            value("fights.damage.started", started);
            if (!started) return done("fights");
            // The fight menu's buttons' words, read as a dilemma's choices are (detail::button_words).
            Json words = Json::array();
            for (const wchar_t* b : {L"mcGuiButtonAttack", L"mcGuiButtonRest", L"mcGuiButtonItem", L"mcGuiButtonFlee"})
                words.push(Json(text(detail::button_words(get(fight_menu().object(), std::wstring(L"PanelCombatMenu.") + b).object))));
            value("fights.menu_words", words);
            // An effect in a fight (Effects.hpp: the world through the controller, as player() is nullptr now).
            if (auto at = location(fight_cat().actor()))
            {
                auto fx = std::make_shared<Effect>(game_effect(L"Buff", {at->x, at->y, at->z + 50}));
                after(0.3, [fx] {
                    value("fights.effect_playing", fx->playing());
                    fx->stop();
                });
            }
            // How answer_dilemma tells which choice is selected (detail::button_selected: the button's CanvasSelected
            // shown), checked on the fight menu's buttons, which are the same kind, against the panel's own selection.
            Json shown = Json::array();
            for (const wchar_t* b : {L"mcGuiButtonAttack", L"mcGuiButtonRest", L"mcGuiButtonItem", L"mcGuiButtonFlee"})
                shown.push(Json(detail::button_selected(get(fight_menu().object(), std::wstring(L"PanelCombatMenu.") + b).object)));
            value("fights.menu_shown_selected", shown);
            value("fights.menu_selected", detail::fight_spot(L"PanelCombatMenu", L"mcGuiButtonAttack").selected);
            auto enemies = fight_enemies();
            value("fights.damage.enemy_health", enemies.empty() ? Json() : Json(health_of(enemies.front())));
            expect("fights.status", !enemies.empty() && apply_status(enemies.front().actor(), L"Poisoned")
                                        && !apply_status(enemies.front().actor(), L"NoSuchStatus"));
            value("fights.status_events", status_events);
            boost = 10;
            expect("fights.attack", fight_attack(0));
            over("damage", [] {
                boost = 0;
                value("fights.hits", hits);
                // ----- 2: won with end_fight(true)
                begin("win", [](bool started) {
                    value("fights.win.started", started);
                    if (!started) return done("fights");
                    // A rest first (the turn goes to the enemy), then, on your cat's next turn, the end.
                    expect("fights.rest", fight_rest());
                    after(3.0, [] {
                        when([] { return static_cast<bool>(fight_menu()) || !combat_active(); }, 20, [](bool) {
                            value("fights.win.rested_turn", static_cast<bool>(fight_menu()));
                            // Where the selection is now: on Rest (1), end_fight's attack is picked with Up.
                            value("fights.win.selected_after_rest", detail::fight_spot(L"PanelCombatMenu", L"mcGuiButtonAttack").selected);
                            value("fights.win.move_count", detail::fight_move_count());
                            // Your cat in a fight: fight_cat(), as player() is nullptr until it ends.
                            value("fights.win.player_in_fight", player() != nullptr);
                            value("fights.win.fight_cat", text(name(fight_cat().actor())));
                            const int moves = detail::fight_move_count();
                            if (moves > 0 && moves < 4) expect("fights.missing_move", !fight_attack(moves));
                            expect("fights.end_win", end_fight(true));
                        });
                    });
                    over("win", [] {
                        // ----- 3: fled
                        begin("flee", [](bool started) {
                            value("fights.flee.started", started);
                            if (!started) return done("fights");
                            expect("fights.flee", flee());
                            over("flee", [] {
                                // ----- 4: lost with end_fight(false)
                                auto home = location(player());
                                begin("lose", [home](bool started) {
                                    value("fights.lose.started", started);
                                    if (!started) return done("fights");
                                    expect("fights.end_lose", end_fight(false));
                                    over("lose", [home] {
                                        auto now = location(player());
                                        if (home && now)
                                            value("fights.lose.moved", std::hypot(now->x - home->x, now->y - home->y));
                                        value("fights.dilemmas", dilemmas);
                                        done("fights");
                                    });
                                });
                            });
                        });
                    });
                });
            });
        });
    }
} // namespace t
