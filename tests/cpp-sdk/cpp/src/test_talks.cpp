// Talk.hpp: conversations, on request ("talks"), for tests/game/test_cpp_sdk.py. A line of the mod's own in the box;
// two of the game's talks read from their graphs and played in it (a prophecy told by a narrator, and a rank-up with
// an answer), moved on to their ends; the first line's words changed through its key and the talk played again (the
// roadmap's "an edited line shows in a talk").
#include "checks.hpp"

#include <memory>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        struct Seen
        {
            std::vector<std::string> lines, speakers, actions, answers;
            int ends{};
        };

        auto hooks_for(std::shared_ptr<Seen> seen) -> TalkHooks
        {
            TalkHooks h;
            h.on_action = [seen](const Talk&, const TalkNode& n) { seen->actions.push_back(text(n.kind)); };
            h.on_answer = [seen](const TalkNode&, const TalkAnswer& a) { seen->answers.push_back(text(a.words)); };
            h.on_end = [seen] { ++seen->ends; };
            return h;
        }
        auto list(const std::vector<std::string>& v) -> Json
        {
            Json out = Json::array();
            for (auto& s : v) out.push(s);
            return out;
        }
        // Moves the talk on (the first answer where there are some) until it ends, recording what shows.
        auto run_to_end(std::shared_ptr<Seen> seen) -> int
        {
            int steps = 0;
            while (talk_playing() && steps < 40)
            {
                seen->lines.push_back(text(talk_line()));
                seen->speakers.push_back(text(talk_speaker()));
                talk_next(0);
                ++steps;
            }
            return steps;
        }
    } // namespace

    auto run_talks_request() -> void
    {
        phase("talks");
        // ----- a line of the mod's own, with answers on the buttons
        expect("talks.say", say(L"Brindlemoon", L"Hello from C++", {L"Yes", L"No"}) && talk_showing());
        value("talks.say_line", text(talk_line()));
        value("talks.say_speaker", text(talk_speaker()));
        value("talks.say_answers", list({text(talk_answers().size() > 0 ? talk_answers()[0] : L""), text(talk_answers().size() > 1 ? talk_answers()[1] : L"")}));
        expect("talks.hide", hide_talk() && !talk_showing() && !hide_talk());
        expect("talks.not_playing", !talk_playing() && !talk_next() && !talk_at());

        // ----- the talks as data
        auto tags = conversation_tags();
        Json all = Json::array();
        for (auto& tag : tags) all.push(text(tag));
        value("talks.tags", all);
        expect("talks.unknown_tag", !conversation(L"Gameplay.No.Such.Talk") && !read_talk(nullptr));
        Talk prophecy = read_talk(conversation(L"Gameplay.Narrative.Prophecy.Intro.RiverClan"));
        value("talks.prophecy_graph", prophecy ? Json(text(name(prophecy.graph))) : Json());
        value("talks.prophecy_nodes", static_cast<int>(prophecy.nodes.size()));
        std::vector<std::string> data_lines;
        for (const TalkNode& n : prophecy.lines()) data_lines.push_back(text(n.words));
        value("talks.prophecy_lines", list(data_lines));
        Talk rankup = read_talk(conversation(L"Gameplay.Narrative.RankUp.WindClan.Warrior"));
        value("talks.rankup_graph", rankup ? Json(text(name(rankup.graph))) : Json());
        Json answers = Json::array();
        for (auto& n : rankup.nodes)
            for (auto& a : n.answers) answers.push(text(a.words));
        value("talks.rankup_answers", answers);
        Json bonds = Json::array();
        for (auto& n : rankup.nodes)
            if (!n.by_bond.empty()) bonds.push(static_cast<int>(n.by_bond.size()));
        value("talks.rankup_bonding_nodes", bonds);

        // ----- the prophecy played, told by its narrator, to its end
        auto seen = std::make_shared<Seen>();
        expect("talks.play", play_talk(prophecy, L"Brindlemoon", hooks_for(seen)) && talk_playing() && talk_showing());
        auto key = words_key(talk_line_text());
        value("talks.first_key", key ? Json(text(key->second)) : Json());
        value("talks.played_steps", run_to_end(seen));
        value("talks.played_lines", list(seen->lines));
        value("talks.played_speakers", list(seen->speakers));
        value("talks.played_actions", list(seen->actions));
        value("talks.played_ends", seen->ends);
        expect("talks.ended", !talk_playing() && !talk_showing());

        // ----- the rank-up, with its answer: a wrong answer number refused, the first taken
        auto seen2 = std::make_shared<Seen>();
        TalkHooks h2 = hooks_for(seen2);
        h2.bond = 1;   // the words for a good bond with the clan
        expect("talks.play_rankup", play_talk(rankup, L"Brindlemoon", h2));
        value("talks.rankup_opening", text(talk_line()));   // a bonding node: its words for a good bond
        int guard = 0;
        while (talk_playing() && talk_answers().empty() && guard++ < 20) talk_next();
        value("talks.answer_line", text(talk_line()));
        value("talks.answers_shown", list([] {
            std::vector<std::string> v;
            for (auto& a : talk_answers()) v.push_back(text(a));
            return v;
        }()));
        expect("talks.wrong_answer", talk_playing() && !talk_next(3) && talk_playing());
        run_to_end(seen2);
        value("talks.chosen", list(seen2->answers));
        value("talks.rankup_actions", list(seen2->actions));
        value("talks.rankup_first_line", seen2->lines.empty() ? Json() : Json(seen2->lines.front()));
        value("talks.rankup_ends", seen2->ends);

        // ----- the first line's words changed through its key: the talk shows them, then they're put back
        if (key)
        {
            set_words(key->second, L"WCMods changed this line", key->first);
            Talk again = read_talk(conversation(L"Gameplay.Narrative.Prophecy.Intro.RiverClan"));
            play_talk(again, L"Brindlemoon");
            value("talks.changed_line", text(talk_line()));
            hide_talk();
            restore_words(key->second, key->first);
            auto restored = read_talk(conversation(L"Gameplay.Narrative.Prophecy.Intro.RiverClan")).lines();
            value("talks.restored_line", restored.empty() ? Json() : Json(text(restored.front().words)));
        }
        // ----- a talk of the mod's own: a question with two answers, the second chosen
        {
            Talk own;
            TalkNode q;
            q.line = true;
            q.source = 3;
            q.source_words = L"Brindlemoon";
            q.words = L"Will you hunt with me?";
            q.answers = {TalkAnswer{L"Yes", 1, 1}, TalkAnswer{L"Not now", 2, 2}};
            TalkNode yes = q, no = q;
            yes.answers.clear();
            no.answers.clear();
            yes.words = L"Then follow me.";
            no.words = L"Another time, then.";
            own.nodes = {q, yes, no};
            own.roots = {0};
            auto chosen = std::make_shared<int>(0);
            TalkHooks h;
            h.on_answer = [chosen](const TalkNode&, const TalkAnswer& a) { *chosen = a.option; };
            expect("talks.own_play", play_talk(own, {}, h) && talk_answers().size() == 2);
            expect("talks.own_answer", talk_next(1) && *chosen == 2);
            value("talks.own_after", text(talk_line()));
            expect("talks.own_end", !talk_next() && !talk_playing());
        }
        // ----- a talk taken down by its own hook, and one started from another's end
        auto seen3 = std::make_shared<Seen>();
        TalkHooks h3;
        h3.on_end = [seen3] {
            ++seen3->ends;
            if (seen3->ends == 1) say(L"Brindlemoon", L"After the talk");
        };
        play_talk(prophecy, L"Brindlemoon", h3);
        hide_talk();
        value("talks.after_end_line", text(talk_line()));
        value("talks.after_end_ends", seen3->ends);
        // The removal hide_talk started is called off: past its 0.4 s the box is still in the viewport.
        after(0.6, [] {
            UObject* box = wcmods::detail::say_state().box.object();
            auto in = box ? call_reflected(box, STR("IsInViewport")) : std::nullopt;
            value("talks.after_end_in_view", Json(in && in->get(L"ReturnValue").boolean()));
            hide_talk();
            after(0.6, [] {
                value("talks.box_after", Json(talk_showing()));
                done("talks");
            });
        });
    }
} // namespace t
