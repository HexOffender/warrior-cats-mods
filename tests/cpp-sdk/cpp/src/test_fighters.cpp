// The mod's cats as fighters (docs/plans/rivals-and-motives.md, S8), on request ("cat_fighters"), for
// tests/game/test_cpp_sdk.py: a cat of the mod's own made with scars and tags plays the cats' fight moves (an
// attack, a hit, a dodge, a defeat) by their tags, as your cat does; its tags are on its actor (and another mod finds
// it among the cats near by them); its scars are on its look, changed while it's in, and both are kept through a
// sleep and a wake.
#include "checks.hpp"

#include <algorithm>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        auto has(const std::vector<std::wstring>& v, std::wstring_view x) -> bool { return std::find(v.begin(), v.end(), x) != v.end(); }

        struct Fight
        {
            Npc npc;
            std::vector<std::wstring> moves{L"Gameplay.Combat.Attack.Universal.2", L"Animation.Combat.Hit.1.Neutral",
                                            L"Animation.Combat.Dodge.Right", L"Animation.Combat.Lose.1"};
            size_t at{};
            Json played = Json::object();
        };

        auto after_wake(const std::shared_ptr<Fight>& f) -> void
        {
            UObject* a = f->npc.actor();
            auto l = a ? look(a) : std::nullopt;
            value("fighters.woke_tags", Json(a && has_tag(a, L"wcmods.test.fighter") && has_tag(a, L"wcmods.test.late")));
            value("fighters.woke_scars", Json(l ? l->ScarEyeId * 10 + l->ScarBodyId : -1));
            f->npc.remove();
            done("cat_fighters");
        }

        auto moves(const std::shared_ptr<Fight>& f) -> void
        {
            UObject* a = f->npc.actor();
            if (f->at >= f->moves.size() || !a)
            {
                value("fighters.played", f->played);
                // the defeat's end: lying still
                value("fighters.still", Json(f->npc.pose(Pose::Still)));
                // scars changed while it's in, and a late tag
                f->npc.set_scars({{L"eye", 2}});
                f->npc.tag(L"wcmods.test.late");
                auto l = look(a);
                value("fighters.scars_now", Json(l ? l->ScarEyeId * 10 + l->ScarBodyId : -1));
                value("fighters.scars_kept", Json(f->npc.scars()[L"eye"] == 2 && f->npc.scars()[L"body"] == 3));
                value("fighters.late_tag", Json(has_tag(a, L"wcmods.test.late") && has(f->npc.tags(), L"wcmods.test.late")));
                // out of the world and back: the same scars and tags
                f->npc.sleep();
                after(0.5, [f] { f->npc.wake([f](Npc) { after(0.5, [f] { after_wake(f); }); }); });
                return;
            }
            const std::wstring tag = f->moves[f->at++];
            UObject* m = play_montage(a, tag);
            after(0.3, [f, tag, m] {
                UObject* a2 = f->npc.actor();
                f->played.set(utf8(tag), Json(m != nullptr && a2 && montage_playing(a2)));
                after(1.0, [f] { moves(f); });
            });
        }
    } // namespace

    auto run_cat_fighters_request() -> void
    {
        phase("cat_fighters");
        auto spot = npc_spot(260, 0);
        if (!spot)
        {
            expect("spot", false);
            done("cat_fighters");
            return;
        }
        auto f = std::make_shared<Fight>();
        // made asleep, its scars set before it first comes in: its look (a tail of 2) kept with them
        f->npc = spawn_npc({.at = *spot, .look = {{L"tail", 2}}, .asleep = true, .scars = {{L"eye", 1}}, .tags = {L"wcmods.test.fighter", L"ClanLife.7"}});
        value("fighters.bad_part", Json(!f->npc.set_scars({{L"eyes", 2}})));
        f->npc.set_scars({{L"body", 3}});
        f->npc.wake();
        auto waited = std::make_shared<int>(0);
        auto in = std::make_shared<std::function<void()>>();
        *in = [f, waited, in] {
            UObject* a = f->npc.actor();
            if (!a && ++*waited < 40)
            {
                after(0.25, *in);
                return;
            }
            if (!a)
            {
                expect("spawned", false);
                done("cat_fighters");
                return;
            }
            // its tags on its actor, and found by them among the cats near your cat
            const auto tags = actor_tags(a);
            value("fighters.tags", Json(has(tags, L"wcmods.test.fighter") && has(tags, L"ClanLife.7")));
            value("fighters.add_again", Json(add_tag(a, L"ClanLife.7") && actor_tags(a).size() == tags.size()));
            value("fighters.no_tag", Json(!has_tag(a, L"ClanLife.8") && !add_tag(nullptr, L"x")));
            int found = 0;
            for (const Nearby& n : nearby(Kind::Cats, 800))
                if (has_tag(n.actor, L"wcmods.test.fighter")) ++found;
            value("fighters.found_near", Json(found));
            value("fighters.yours_untagged", Json(!has_tag(player(), L"wcmods.test.fighter")));
            // its scars, on its look, and the rest of its look as given
            auto l = look(a);
            value("fighters.scars", Json(l ? l->ScarEyeId * 10 + l->ScarBodyId : -1));
            value("fighters.tail", Json(l ? l->TailIdx : -1));
            moves(f);
        };
        after(0.25, *in);
    }
} // namespace t
