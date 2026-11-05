// Bonds.hpp: your cat's bonds, on request ("bonds"), for tests/game/test_cpp_sdk.py. The ranks from the tuning; a
// clan's bond and a story cat's set and read back; the pause screen's Bonds panel opened and read (the game's own
// view of them); the game saved and its JSON read for them; everything put back as it was.
#include "checks.hpp"

#include <fstream>
#include <memory>
#include <sstream>
#include <string>

namespace t
{
    namespace
    {
        constexpr const wchar_t* CLAN = L"ShadowClan";   // the test cat's clan
        // The story cat changed: the first of your clan's roles with a base bond (the ones the Bonds panel lists).
        std::wstring ROLE;

        struct Kept
        {
            int clan{}, role{};
            int tries{};
        };
        auto num(std::optional<int> v) -> Json { return v ? Json(*v) : Json(); }

        // The Bonds panel's words: its clan bar's score and each cat row's name and score.
        auto read_panel() -> Json
        {
            Json out = Json::object();
            Widget panel;
            for (UObject* w : find_all(STR("WBP_GuiPausePanelBonds_C")))
            {
                Widget p(w);
                auto shown = call_reflected(w, STR("IsVisible"));
                if (shown && shown->get(L"ReturnValue").boolean()) panel = p;
            }
            if (!panel) return Json();
            out.set("clan_score", Json(text(Widget(get(panel.object(), L"mcGuiBondsClan.mcGuiScoreBar.mcGuiTextScore").object).text())));
            out.set("clan_info", Json(text(Widget(get(panel.object(), L"mcGuiBondsClan.mcGuiScoreBar.mcGuiTextInfo").object).text())));
            Json rows = Json::array();
            for (UObject* w : find_all(STR("WBP_GuiBondsCharacterControl_C")))
            {
                Json row = Json::object();
                row.set("name", Json(text(Widget(get(w, L"mcGuiTextName").object).text())));
                row.set("score", Json(text(Widget(get(w, L"mcGuiScoreBar.mcGuiTextScore").object).text())));
                rows.push(row);
            }
            out.set("rows", Json(rows));
            return out;
        }

        // Along the pause screen's tabs (Right, its next-tab key) until the Bonds panel shows, 12 at most.
        auto find_panel(std::shared_ptr<Kept> k, std::function<void()> then) -> void
        {
            if (k->tries == 0)
            {
                // What there is to find: every Bonds panel the game has, and whether each is drawn.
                Json seen = Json::array();
                for (UObject* w : find_all(STR("WBP_GuiPausePanelBonds_C")))
                {
                    auto shown = call_reflected(w, STR("IsVisible"));
                    seen.push(Json(text(full_name(w)) + (shown && shown->get(L"ReturnValue").boolean() ? " shown" : " hidden")));
                }
                value("bonds.panels_found", seen);
            }
            Json p = read_panel();
            if (!p.is_null() || k->tries >= 12)
            {
                value("bonds.panel", p);
                value("bonds.panel_tries", k->tries);
                then();
                return;
            }
            ++k->tries;
            // The next tab, as the game's tab key gives it (the arrows since build 26337109).
            ui::send(ui::screen(L"WBP_GuiScreenPause_C"), L"Button_Right");
            after(0.8, [k, then] { find_panel(k, then); });
        }

        auto slot_bonds_in_json() -> Json
        {
            std::ifstream f(save_path(), std::ios::binary);
            std::stringstream ss;
            ss << f.rdbuf();
            auto doc = Json::parse(ss.str());
            if (!doc) return Json();
            Json slot = detail::slot_of(*doc);
            return slot["GameplayProgression"]["Bonding"];
        }
    } // namespace

    auto run_bonds_request() -> void
    {
        phase("bonds");
        // ----- the ranks, by the tuning's thresholds
        expect("bonds.ranks", bond_rank(5) == BondRank::Unfriendly && bond_rank(10) == BondRank::Neutral && bond_rank(30) == BondRank::Friendly
                                  && bond_rank(46) == BondRank::Friend && bond_rank(80) == BondRank::CloseBond);
        expect("bonds.clan_ranks", clan_bond(20) == ClanBond::Negative && clan_bond(50) == ClanBond::Neutral && clan_bond(70) == ClanBond::Positive);
        expect("bonds.rank_names", std::wstring(bond_rank_name(BondRank::CloseBond)) == L"CloseBond"
                                       && std::wstring(clan_bond_name(ClanBond::Negative)) == L"Negative");
        // The enum's names in order, and a cat's name from its name ids (the test cat's, Emberpaw).
        auto clans = enum_names(STR("/Script/SwtQuest.EClanType"));
        expect("bonds.enum_names", clans.size() > 4 && clans[1].first == L"ThunderClan" && clans[1].second == 1 && enum_names(STR("/Script/NoSuch.Enum")).empty());
        value("bonds.name_from_ids", text(cat_name_of(L"STR_CAT_NAME2", L"_PAW")));
        auto roles = bond_roles();
        value("bonds.roles", static_cast<int>(roles.size()));
        value("bonds.first_role", roles.empty() ? Json() : Json(text(roles.front())));

        // ----- set and read back
        ROLE.clear();
        for (auto& b : bonds())
            if (!b.clan && b.base > 0 && ROLE.empty()) ROLE = b.key;
        value("bonds.role", text(ROLE));
        auto k = std::make_shared<Kept>();
        auto clan_before = bond(CLAN);
        auto role_before = bond(ROLE);
        expect("bonds.read", clan_before.has_value() && role_before.has_value());
        k->clan = clan_before.value_or(0);
        k->role = role_before.value_or(0);
        value("bonds.clan_before", num(clan_before));
        value("bonds.role_before", num(role_before));
        expect("bonds.unknown_key", !bond(L"NoSuchRole") && !set_bond(L"NoSuchRole", 5) && !bond(L"None"));
        expect("bonds.add", add_bond(ROLE, 3) && bond(ROLE) == role_before.value_or(0) + 3);
        expect("bonds.set", set_bond(CLAN, 42) && set_bond(ROLE, 50));
        value("bonds.clan_after", num(bond(CLAN)));
        value("bonds.role_after", num(bond(ROLE)));
        expect("bonds.set_high", !set_bond(ROLE, 150));   // the game keeps a bond within 100
        value("bonds.role_high", num(bond(ROLE)));
        expect("bonds.set_low", !set_bond(ROLE, -20));
        value("bonds.role_low", num(bond(ROLE)));
        set_bond(ROLE, 50);
        Json listed = Json::array();
        for (auto& b : bonds())
        {
            Json one = Json::object();
            one.set("key", Json(text(b.key)));
            one.set("clan", Json(b.clan));
            one.set("value", Json(b.value));
            one.set("rank", Json(text(b.rank)));
            one.set("cat", Json(text(b.cat_name)));
            one.set("base", Json(b.base));
            one.set("giver", Json(text(b.giver_role) + "/" + std::to_string(b.giver_index)));
            listed.push(one);
        }
        value("bonds.listed", listed);

        // ----- the game's own view: the pause screen's Bonds panel
        command(L"Player_Pause");
        after(1.5, [k] {
            value("bonds.pause_open", Json(static_cast<bool>(ui::screen(L"WBP_GuiScreenPause_C"))));
            find_panel(k, [k] {
                ui::close(ui::screen(L"WBP_GuiScreenPause_C"));
                // ----- the save: saved, its JSON read for them, then everything put back and saved again
                after(1.5, [k] {
                    save_game(L"WCMods bonds test");
                    after(2.0, [k] {
                        value("bonds.saved", slot_bonds_in_json());
                        set_bond(CLAN, k->clan);
                        set_bond(ROLE, k->role);
                        value("bonds.clan_restored", num(bond(CLAN)));
                        value("bonds.role_restored", num(bond(ROLE)));
                        save_game(L"WCMods bonds test");
                        after(2.0, [] {
                            value("bonds.saved_after", slot_bonds_in_json());
                            done("bonds");
                        });
                    });
                });
            });
        });
    }
} // namespace t
