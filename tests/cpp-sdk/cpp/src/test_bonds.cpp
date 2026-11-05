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
        BondThresholds th = bond_thresholds();
        expect("bonds.thresholds", th.neutral == 10 && th.friendly == 28 && th.friend_ == 46 && th.close == 73
                                       && th.clan_negative == 33 && th.clan_positive == 67);
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
        // Outside 0 to 100: set_bond refuses and changes nothing; the game's own add stops at the bounds.
        expect("bonds.set_out_of_range", !set_bond(ROLE, 150) && !set_bond(ROLE, -20) && bond(ROLE) == 50);
        add_bond(ROLE, 200);
        value("bonds.role_high", num(bond(ROLE)));
        add_bond(ROLE, -300);
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

    namespace
    {
        auto row_json(const std::optional<TalkRow>& r) -> Json
        {
            if (!r) return Json();
            Json o = Json::object();
            o.set("name", Json(text(r->name)));
            o.set("score", Json(r->score));
            o.set("clan", Json(r->clan_bonding));
            o.set("trait", Json(r->trait));
            o.set("talker", Json(text(r->talker)));
            o.set("key", Json(text(r->string_key)));
            o.set("text", Json(text(r->text())));
            return o;
        }
        auto answer_json(const std::optional<BondAnswer>& a) -> Json
        {
            if (!a) return Json();
            Json o = Json::object();
            o.set("node", Json(text(a->node)));
            o.set("trait", Json(a->trait));
            o.set("bonus", Json(a->bonus));
            o.set("first", Json(a->first));
            o.set("role", Json(text(a->role)));
            o.set("personal", Json(a->personal));
            o.set("clan", Json(text(a->clan)));
            o.set("clan_change", Json(a->clan_change));
            return o;
        }
        // The first line with answers a story talk reaches from its first root (moving on through the lines).
        auto question_of(const Talk& t) -> const TalkNode*
        {
            std::vector<bool> seen(t.nodes.size());
            int at = t.roots.empty() ? -1 : t.roots.front();
            while (at >= 0 && static_cast<size_t>(at) < t.nodes.size() && !seen[at])
            {
                seen[at] = true;
                const TalkNode& n = t.nodes[at];
                if (n.line && !n.answers.empty()) return &n;
                at = !n.next.empty() ? n.next.front() : !n.answers.empty() ? n.answers.front().to : -1;
            }
            return nullptr;
        }
    } // namespace

    // A story talk filled from the game's tables, played, and one of its answers given: what the game's own bond answer
    // does to the story cat's bond and the clan's regard, the node marked; given again, and a talk played with the
    // bonds off; everything but the node put back after (a node can't be taken out).
    auto run_bond_answers_request() -> void
    {
        phase("bond_answers");
        const std::wstring seven = L"Gameplay.Dialogue.Story.Short.TheMistrustfulLeader.Main.7";
        // ----- the tables
        value("answers.row_right", row_json(talk_row(seven + L".Right.1.Short")));
        value("answers.row_quest", row_json(talk_row(L"quest.procedural.survival.gather.apprentice.context.answer.brave.short")));
        expect("answers.row_missing", !talk_row(L"Gameplay.WCModsTest.NoSuchRow"));
        value("answers.rows_under", static_cast<int>(talk_rows(seven + L".").size()));

        // ----- a story talk, as the game fills its template
        Talk st = story_talk(seven);
        Json lines = Json::array();
        for (auto& n : st.lines()) lines.push(Json(text(n.words)));
        value("answers.story_tag", Json(text(st.tag)));
        value("answers.story_lines", lines);
        Json answers = Json::array();
        if (const TalkNode* q = question_of(st))
            for (auto& a : q->answers)
            {
                Json o = Json::object();
                o.set("words", Json(text(a.words)));
                o.set("trait", Json(a.trait));
                o.set("score", Json(a.score));
                o.set("bonding", Json(a.bonding));
                o.set("row", Json(text(bond_answer_row(st, st.nodes[a.to]))));
                answers.push(o);
            }
        value("answers.story_answers", answers);
        Json end = Json::array();
        for (auto& n : story_talk(seven, 2).lines()) end.push(Json(text(n.words)));
        value("answers.end_lines", end);
        expect("answers.story_none", !story_talk(L"Gameplay.WCModsTest.NoSuchTalk") && !story_talk(seven, 0)
                                         && !story_talk(L"Gameplay.Dialogue.Story.Monologue.Interaction.WCModsTest", 4));

        // ----- the story cat, and an answer of its talks your cat hasn't given (one with a trait your cat has first)
        std::wstring role;
        for (auto& b : bonds())
            if (!b.clan && role.empty() && !talk_rows(L"Gameplay.Dialogue.Story.Short." + b.key + L".Main.").empty()) role = b.key;
        value("answers.role", Json(text(role)));
        Json traits = Json::array();
        for (auto& tr : cat_traits()) traits.push(Json(text(tr)));
        value("answers.cat_traits", traits);
        static const wchar_t* trait_names[] = {L"None", L"Brave", L"Ambitious", L"Wise", L"Energetic", L"Curious", L"Patient"};
        auto has_trait = [](int trait) {
            for (auto& tr : cat_traits())
                if (trait > 0 && trait < 7 && tr == trait_names[trait]) return true;
            return false;
        };
        std::wstring tag, node;
        int choice = -1;
        for (int pass = 0; pass < 2 && choice < 0; ++pass)
            for (int main = 1; main <= 20 && choice < 0; ++main)
            {
                std::wstring candidate = L"Gameplay.Dialogue.Story.Short." + role + L".Main." + std::to_wstring(main);
                Talk c = story_talk(candidate);
                const TalkNode* q = c ? question_of(c) : nullptr;
                if (!q) continue;
                for (size_t a = 0; a < q->answers.size() && choice < 0; ++a)
                {
                    const TalkAnswer& ans = q->answers[a];
                    std::wstring row = bond_answer_row(c, c.nodes[ans.to]);
                    if (ans.trait == 0 || row.empty() || bond_node(row).value_or(true)) continue;
                    if (pass == 0 && !has_trait(ans.trait)) continue;
                    tag = candidate;
                    node = row;
                    choice = static_cast<int>(a);
                }
            }
        value("answers.tag", Json(text(tag)));
        value("answers.node", Json(text(node)));
        value("answers.choice", Json(choice));
        auto chosen = talk_row(node);
        value("answers.chosen_row", row_json(chosen));
        if (choice < 0 || role.empty())
        {
            expect("answers.found", false, "no story cat, or no answer left to give");
            done("bond_answers");
            return;
        }
        const std::wstring clan = cat_clan(player());
        value("answers.clan", Json(text(clan)));
        const int personal_before = bond(role).value_or(-1), clan_before = bond(clan).value_or(-1);
        value("answers.personal_before", Json(personal_before));
        value("answers.clan_before", Json(clan_before));
        value("answers.node_before", Json(bond_node(node).value_or(true)));

        // ----- played, the answer chosen: the game's bond answer as the talk passes it
        auto seen = std::make_shared<std::vector<BondAnswer>>();
        TalkHooks h;
        h.role = role;
        h.on_bond = [seen](const TalkNode&, const BondAnswer& a) { seen->push_back(a); };
        expect("answers.play", play_talk(story_talk(tag), {}, h));
        int guard = 0;
        while (talk_playing() && talk_answers().empty() && guard++ < 20) talk_next();
        value("answers.question", Json(text(talk_line())));
        expect("answers.answered", talk_next(choice));
        value("answers.reply", Json(text(talk_line())));
        value("answers.on_bond", seen->empty() ? Json() : answer_json(seen->front()));
        value("answers.on_bond_count", Json(static_cast<int>(seen->size())));
        hide_talk();
        value("answers.personal_after", Json(bond(role).value_or(-1)));
        value("answers.clan_after", Json(bond(clan).value_or(-1)));
        value("answers.node_after", Json(bond_node(node).value_or(false)));

        // ----- the same answer again, by answer_bond: the clan's regard again, not the cat's bond
        value("answers.again", answer_json(answer_bond(node, role)));
        value("answers.personal_again", Json(bond(role).value_or(-1)));
        value("answers.clan_again", Json(bond(clan).value_or(-1)));
        // A row without a trait (the long line after the answer) and a row no table has: nothing.
        expect("answers.no_trait", !answer_bond(tag + L".Right.1.Long", role) && !answer_bond(L"Gameplay.WCModsTest.NoSuchRow", role));
        // Played with the bonds off: the answer does nothing.
        auto off_seen = std::make_shared<int>(0);
        TalkHooks off;
        off.role = role;
        off.bonds = false;
        off.on_bond = [off_seen](const TalkNode&, const BondAnswer&) { ++*off_seen; };
        if (play_talk(story_talk(tag), {}, off))
        {
            int g = 0;
            while (talk_playing() && talk_answers().empty() && g++ < 20) talk_next();
            talk_next(choice);
            hide_talk();
        }
        value("answers.off_count", Json(*off_seen));
        value("answers.personal_off", Json(bond(role).value_or(-1)));
        value("answers.clan_off", Json(bond(clan).value_or(-1)));

        // ----- put back (the node stays: nothing takes one out)
        expect("answers.restored", set_bond(role, personal_before) && set_bond(clan, clan_before));
        value("answers.personal_restored", Json(bond(role).value_or(-1)));
        value("answers.clan_restored", Json(bond(clan).value_or(-1)));
        done("bond_answers");
    }
} // namespace t
