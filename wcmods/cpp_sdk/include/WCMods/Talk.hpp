// Talk.hpp: conversations. The game's dialogue box with a line of the mod's own (as Lua's Game.dialogue shows it),
// and the game's own talks: each read as data from its graph (its lines, who says them, its answers and where each
// leads) and played in that box, line by line, as the mod moves it on. Game thread only. WCMods.hpp includes it;
// docs/SDK.md, "C++ mods", documents every call.
//
// Why not the game's own player: its sequencer manager (PlaySequenceDialogue) opens the talk's box as a popup of the
// game's screen, which only the talk's scene closes cleanly. Closed any other way (moved past its last line, or the
// game quitting with it still open) the screen's popup release reads a link the release has just cleared, and the
// game crashes; and a second talk after one ended early isn't tracked by the manager at all (docs/reverse-engineering.md,
// "Talks"). The box here is made outside the screens' popups, as say() always has, and is safe to take down any time.
#pragma once

#include <algorithm>
#include <functional>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/Tables.hpp>
#include <WCMods/Ui.hpp>
#include <WCMods/Words.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // ============================================================================================ a line of the mod's own
    // The game's dialogue box made outside a talk shows a line with a cat's name, as Lua's Game.dialogue.say does: only
    // a picture (its answer buttons hold answers' words when a talk has them, never anything to click: the box's own
    // code runs an answer through a node of a talk it hasn't got), which the mouse goes through. It stays until
    // hide_talk().
    namespace detail
    {
        struct SayState
        {
            Widget box;
            std::wstring name, words;
            std::vector<std::wstring> answers;
            int closing{};
        };
        inline auto say_state() -> SayState&
        {
            static SayState s;
            return s;
        }
        inline constexpr const wchar_t* DIALOGUE_CLASS = L"/Game/Art/UXD/Blueprints/QuestDialogs/WBP_QuestGiver_Dialogue.WBP_QuestGiver_Dialogue_C";
        inline constexpr const wchar_t* ANSWER_BUTTONS[] = {L"mcButton1", L"mcButton2", L"mcButton3", L"mcButton4"};

        // The box's four answer buttons with `answers`' words (more than four are left out), the rest collapsed.
        inline auto show_answers(UObject* box, const std::vector<std::wstring>& answers) -> void
        {
            for (size_t i = 0; i < 4; ++i)
            {
                Widget button(get(box, ANSWER_BUTTONS[i]).object);
                if (!button) continue;
                if (i >= answers.size())
                {
                    button.collapse();
                    continue;
                }
                set(button.object(), L"Text", Value::of(std::wstring_view(answers[i])));
                for (const wchar_t* part : {L"mcGuiTextNormal", L"mcGuiTextSelected", L"mcGuiTextDisabled", L"mcGuiTextPressed", L"mcGuiTextOver"})
                    if (Widget t(get(button.object(), part).object); t) t.set_text(answers[i]);
                button.set_visibility(Visibility::HitTestInvisible);
            }
        }
    } // namespace detail

    // Show `words` said by `speaker` in the box, with `answers` (up to four) on its buttons. False when the box can't be
    // made (the game hasn't loaded its class).
    inline auto say(std::wstring_view speaker, std::wstring_view words, const std::vector<std::wstring>& answers = {}) -> bool
    {
        if (!assert_game_thread(L"say")) return false;
        auto& s = detail::say_state();
        if (!s.box)
        {
            UObject* cls = load(detail::DIALOGUE_CLASS);
            if (!cls) return false;
            auto made = call_reflected(object(STR("/Script/UMG.Default__WidgetBlueprintLibrary")), STR("Create"), [&](Params& p) {
                p.set_nth(0, Value::of(controller()));
                p.set_nth(1, Value::of(cls));
                p.set_nth(2, Value::of(controller()));
            });
            s.box = Widget(made ? made->get(L"ReturnValue").object : nullptr);
            if (!s.box) return false;
        }
        ++s.closing;   // a fade-out under way no longer takes it away
        UObject* b = s.box.object();
        if (std::wstring(speaker) != s.name) Widget(get(b, L"mcGuiDialogueTalker.mcGuiTextName").object).set_text(speaker);
        if (std::wstring(words) != s.words) Widget(get(b, L"mcGuiTextParagraph").object).set_text(words);
        auto in = call_reflected(b, STR("IsInViewport"));
        const bool adding = !in || !in->get(L"ReturnValue").boolean();
        if (adding)
        {
            call_reflected(b, STR("AddToViewport"), [&](Params& p) { p.set_nth(0, Value::of(1500)); });
            // Made outside a talk, the box hides its parts as it goes on screen: shown after.
            Widget(get(b, L"CanvasPanelDialog").object).set_visibility(Visibility::SelfHitTestInvisible);
            Widget(get(b, L"mcGuiTextParagraph").object).set_visibility(Visibility::HitTestInvisible);
            Widget(get(b, L"mcGuiNext").object).set_visibility(Visibility::HitTestInvisible);
            s.box.set_visibility(Visibility::HitTestInvisible);
            s.box.play(L"AniScreenIn");
        }
        if (adding || answers != s.answers) detail::show_answers(b, answers);
        s.name = speaker;
        s.words = words;
        s.answers = answers;
        return true;
    }
    // Take say()'s box down, fading out as the game's does; false when it isn't up. A talk playing in it ends.
    inline auto hide_talk() -> bool;
    // Whether say()'s box shows a line now.
    inline auto talk_showing() -> bool { return !detail::say_state().words.empty() && detail::say_state().box; }
    // What the box says now and who says it; empty without a line.
    inline auto talk_line() -> std::wstring { return talk_showing() ? detail::say_state().words : std::wstring{}; }
    inline auto talk_speaker() -> std::wstring { return talk_showing() ? detail::say_state().name : std::wstring{}; }
    // The answers on the box's buttons now (a talk's line that has them), else none.
    inline auto talk_answers() -> std::vector<std::wstring> { return talk_showing() ? detail::say_state().answers : std::vector<std::wstring>{}; }

    // ============================================================================================ the game's talks as data
    // Each of the game's talks is a graph (a UQuestDialogue, UBondDialogue or UNpcDialogue asset): nodes from its roots,
    // each to its children. A talking node is a line (UQuestDialogueTalkingNode: its words, and who says them); the
    // rest are the game's actions (UQuestDialogueActionCreateScreen, ...ResolveConfirm, ...ApplyEffect, ...Save...),
    // which its own player runs as it passes them. An edge to a child is plain (the line after) or one of four answers,
    // with the button's words and what it does to the clan's bond and your cat's traits.
    struct TalkAnswer
    {
        std::wstring words;   // the button's words ("I DO")
        int to{-1};           // the node it leads to (an index into Talk::nodes)
        int option{};         // EEdgeType: 1 to 4
        int trait{};          // ECharacterTrait the answer speaks for (0 None, 1 Brave, 2 Ambitious, 3 Wise, 4 Energetic, 5 Curious, 6 Patient)
        int score{};          // the trait's score for it
        int bonding{};        // what it does to your bond with the clan
    };
    struct TalkNode
    {
        UObject* node{};
        std::wstring kind;              // its class: L"QuestDialogueTalkingNode", L"QuestDialogueActionResolveConfirm"...
        bool line{};                    // a talking node: something said
        int source{};                   // ETalkingSource: 0 NPC (the cat talked to), 1 Player, 2 Current_Character, 3 Custom
        std::wstring source_words;      // the speaker's name for Custom ("Narrator"), as the game shows it
        std::wstring words;             // what's said (its Paragraph), as the game shows it
        Value words_text;               // the Paragraph itself, for words_key() (Words.hpp): its key in the string table
        std::vector<std::wstring> by_bond;   // a bonding node's words by your bond with the clan: [Neutral, Positive, Negative]
        std::vector<int> next;          // its children, in the graph's order
        std::vector<TalkAnswer> answers;   // the children through an answer edge, by option
    };
    // A talk: one read from the game's graph, or one a mod makes itself (nodes with `line`, `words`, `source` 3 and
    // `source_words` for the speaker, `next` and `answers` by index; `graph` and `node` left empty).
    struct Talk
    {
        UObject* graph{};
        std::vector<TalkNode> nodes;
        std::vector<int> roots;
        explicit operator bool() const
        {
            return !roots.empty() && !nodes.empty() && roots.front() >= 0 && static_cast<size_t>(roots.front()) < nodes.size();
        }
        // The lines, as the talk reaches them from its first root taking every first answer (for a list), copied.
        auto lines() const -> std::vector<TalkNode>
        {
            std::vector<TalkNode> out;
            std::vector<bool> seen(nodes.size());
            int at = roots.empty() ? -1 : roots.front();
            while (at >= 0 && at < static_cast<int>(nodes.size()) && !seen[at])
            {
                seen[at] = true;
                const TalkNode& n = nodes[at];
                if (n.line) out.push_back(n);
                at = !n.answers.empty() ? n.answers.front().to : !n.next.empty() ? n.next.front() : -1;
            }
            return out;
        }
    };

    // The tags of the game's cinematic talks, which its scenes play (DT_QuestSequenceDialogues: 30 of them,
    // Gameplay.Narrative.RankUp.WindClan.Leader, Gameplay.Narrative.Prophecy.Intro.ThunderClan...).
    inline auto conversation_tags() -> std::vector<std::wstring>
    {
        std::vector<std::wstring> out;
        if (!assert_game_thread(L"conversation_tags")) return out;
        for (auto& [row, value] : table(L"DT_QuestSequenceDialogues").rows())
        {
            std::wstring tag = get(value, L"SequenceDialogueId.TagName").text;
            if (!tag.empty() && tag != L"None") out.push_back(tag);
        }
        return out;
    }
    // One of those talks' graph by its tag, or nullptr.
    inline auto conversation(std::wstring_view tag) -> UObject*
    {
        if (!assert_game_thread(L"conversation")) return nullptr;
        for (auto& [row, value] : table(L"DT_QuestSequenceDialogues").rows())
            if (get(value, L"SequenceDialogueId.TagName").text == tag) return get(value, L"DialogueToUse").object;
        return nullptr;
    }

    // A talk's graph read as data: an empty Talk for nullptr, or an object that isn't a talk's graph. Any of the game's
    // talks: conversation(tag)'s, a quest's (its QuestDialogueOnStart...), or one loaded by its path
    // (load(L"/Game/Quests/NpcDialogues/NPCUniques/NpcDialogue_OnlineFriends.NpcDialogue_OnlineFriends")).
    inline auto read_talk(UObject* graph) -> Talk
    {
        Talk t;
        if (!graph || !assert_game_thread(L"read_talk")) return t;
        auto all = elements(graph, L"AllNodes");
        if (all.empty()) return t;
        t.graph = graph;
        std::vector<UObject*> objects;
        for (auto& v : all) objects.push_back(v.object);
        auto index = [&](UObject* o) -> int {
            for (size_t i = 0; i < objects.size(); ++i)
                if (objects[i] == o && o) return static_cast<int>(i);
            return -1;
        };
        for (UObject* o : objects)
        {
            TalkNode n;
            n.node = o;
            n.kind = class_name(o);
            if (o)
            {
                n.words_text = get(o, L"Paragraph");
                if (n.words_text.kind == Value::Kind::Text)
                {
                    n.line = true;
                    n.words = n.words_text.text;
                    n.source = static_cast<int>(get(o, L"TalkingSource").number());
                    n.source_words = get(o, L"TalkingSourceText").text;
                    for (auto& [bond, words] : map_entries(o, L"BondingTypesTexts"))
                    {
                        auto at = static_cast<size_t>(bond.number());
                        if (at < 3)
                        {
                            if (n.by_bond.size() <= at) n.by_bond.resize(at + 1);
                            n.by_bond[at] = words.text;
                        }
                    }
                }
            }
            t.nodes.push_back(std::move(n));
        }
        for (size_t i = 0; i < objects.size(); ++i)
        {
            if (!objects[i]) continue;
            TalkNode& n = t.nodes[i];
            auto edges = map_entries(objects[i], L"Edges");
            for (auto& child : elements(objects[i], L"ChildrenNodes"))
            {
                int to = index(child.object);
                if (to < 0) continue;
                UObject* edge = nullptr;
                for (auto& [k, v] : edges)
                    if (k.object == child.object) edge = v.object;
                int option = edge ? static_cast<int>(get(edge, L"EdgeType").number()) : 0;
                if (option >= 1 && option <= 4)
                {
                    TalkAnswer a;
                    a.words = get(edge, L"Button.Text").text;
                    a.to = to;
                    a.option = option;
                    a.trait = static_cast<int>(get(edge, L"TraitType").number());
                    a.score = static_cast<int>(get(edge, L"Score").number());
                    a.bonding = static_cast<int>(get(edge, L"ClanBonding").number());
                    n.answers.push_back(std::move(a));
                }
                else
                    n.next.push_back(to);
            }
            std::stable_sort(n.answers.begin(), n.answers.end(), [](const TalkAnswer& a, const TalkAnswer& b) { return a.option < b.option; });
        }
        for (auto& r : elements(graph, L"RootNodes"))
            if (int i = index(r.object); i >= 0) t.roots.push_back(i);
        return t;
    }

    // ============================================================================================ playing a talk
    // A talk played in say()'s box: each line with who says it (NPC and Current_Character: `npc_name`, Player: your
    // cat's name, Custom: the node's own, "Narrator"), its answers on the box's buttons. talk_next() moves it on, and
    // the mod chooses an answer by its number (keys of the mod's own: the box's buttons are only a picture). The game's
    // actions on the way are passed to `on_action` (the mod does what it wants of them; nothing runs them otherwise),
    // and `on_end` is called when the talk runs out of lines or is taken down.
    struct TalkHooks
    {
        std::function<void(const Talk&, const TalkNode&)> on_action;
        std::function<void(const TalkNode&, const TalkAnswer&)> on_answer;
        std::function<void()> on_end;
        int bond{-1};   // a bonding node's words for this bond (0 Neutral, 1 Positive, 2 Negative); -1: its Paragraph
    };
    namespace detail
    {
        struct TalkPlay
        {
            Talk talk;
            std::wstring npc_name;
            TalkHooks hooks;
            int at{-1};   // the line showing
            bool playing{};
            int generation{};   // a new talk, or one ended: a hook that did either leaves the walk it was called from
        };
        inline auto talk_play() -> TalkPlay&
        {
            static TalkPlay p;
            return p;
        }
        inline auto speaker_of(const TalkPlay& p, const TalkNode& n) -> std::wstring
        {
            if (n.source == 3) return n.source_words;
            if (n.source == 1) return cat_name(player());
            return p.npc_name.empty() ? n.source_words : p.npc_name;
        }
        inline auto words_of(const TalkPlay& p, const TalkNode& n) -> std::wstring
        {
            if (p.hooks.bond >= 0 && static_cast<size_t>(p.hooks.bond) < n.by_bond.size() && !n.by_bond[p.hooks.bond].empty())
                return n.by_bond[p.hooks.bond];
            return n.words;
        }
        // The talk on from `to` to its next line (passing its actions to on_action): shown, or the talk's end.
        inline auto talk_reach(int to) -> bool
        {
            auto& p = talk_play();
            const size_t count = p.talk.nodes.size();
            for (size_t steps = 0; to >= 0 && static_cast<size_t>(to) < count && steps <= count; ++steps)
            {
                const TalkNode& n = p.talk.nodes[to];
                if (n.line)
                {
                    p.at = to;
                    std::vector<std::wstring> answers;
                    for (auto& a : n.answers) answers.push_back(a.words);
                    if (say(speaker_of(p, n), words_of(p, n), answers)) return true;
                    break;
                }
                to = !n.next.empty() ? n.next.front() : !n.answers.empty() ? n.answers.front().to : -1;
                if (p.hooks.on_action)
                {
                    const int gen = p.generation;
                    p.hooks.on_action(p.talk, n);
                    if (p.generation != gen) return p.playing;   // on_action ended it, or played another
                }
            }
            hide_talk();
            return false;
        }
    } // namespace detail

    // Play a talk read with read_talk(), from its first root. False (nothing shown) for an empty talk or one with no
    // line; a talk already playing ends first (its on_end called).
    inline auto play_talk(Talk talk, std::wstring_view npc_name = {}, TalkHooks hooks = {}) -> bool
    {
        if (!assert_game_thread(L"play_talk") || !talk) return false;
        auto& p = detail::talk_play();
        if (p.playing) hide_talk();
        int root = talk.roots.front();
        p.talk = std::move(talk);
        p.npc_name = npc_name;
        p.hooks = std::move(hooks);
        p.at = -1;
        p.playing = true;
        ++p.generation;
        return detail::talk_reach(root);
    }
    // Move the talk playing on: past a line with answers by `answer` (0 for the first: false, with nothing done, when it
    // hasn't that many), else to the line after. False when nothing is playing, or the talk has just ended.
    inline auto talk_next(int answer = 0) -> bool
    {
        if (!assert_game_thread(L"talk_next")) return false;
        auto& p = detail::talk_play();
        if (!p.playing || p.at < 0) return false;
        const TalkNode& n = p.talk.nodes[p.at];
        int to = -1;
        if (!n.answers.empty())
        {
            if (answer < 0 || static_cast<size_t>(answer) >= n.answers.size()) return false;
            TalkAnswer chosen = n.answers[answer];
            to = chosen.to;
            if (p.hooks.on_answer)
            {
                const int gen = p.generation;
                p.hooks.on_answer(n, chosen);
                if (p.generation != gen) return p.playing;   // on_answer ended it, or played another
            }
        }
        else if (!n.next.empty())
            to = n.next.front();
        if (to < 0)
        {
            hide_talk();
            return false;
        }
        return detail::talk_reach(to);
    }
    // Whether a talk plays, and the line it shows (nullptr when none).
    inline auto talk_playing() -> bool { return detail::talk_play().playing; }
    inline auto talk_at() -> const TalkNode*
    {
        auto& p = detail::talk_play();
        return p.playing && p.at >= 0 ? &p.talk.nodes[p.at] : nullptr;
    }
    // The line showing as the text it was made from, for words_key() (Words.hpp): which key of the game's words it
    // is. Empty for a line of say()'s own, or none.
    inline auto talk_line_text() -> Value
    {
        const TalkNode* n = talk_at();
        return n ? n->words_text : Value{};
    }

    inline auto hide_talk() -> bool
    {
        if (!assert_game_thread(L"hide_talk")) return false;
        auto& p = detail::talk_play();
        std::function<void()> end;
        if (p.playing)
        {
            p.playing = false;
            p.at = -1;
            ++p.generation;
            end = std::move(p.hooks.on_end);
            p.hooks = {};
        }
        auto& s = detail::say_state();
        bool was_up = s.box && !s.words.empty();
        if (was_up)
        {
            s.name.clear();
            s.words.clear();
            s.answers.clear();
            int mine = ++s.closing;
            s.box.play(L"AniScreenIn", true);
            after(0.4, [mine] {
                auto& st = detail::say_state();
                if (st.closing == mine && st.box) call_reflected(st.box.object(), STR("RemoveFromParent"));
            });
        }
        if (end) end();   // last: it may play another talk, or say something
        return was_up;
    }
    namespace detail
    {
        // As the mod is taken out: its talk over and its box down (on the game thread only: the box is the game's).
        inline auto stop_talk() -> void
        {
            auto& p = talk_play();
            p.playing = false;
            p.hooks = {};
            p.talk = {};
            auto& s = say_state();
            if (on_game_thread_now() && s.box) call_reflected(s.box.object(), STR("RemoveFromParent"));
            s.words.clear();
            s.answers.clear();
        }
    } // namespace detail
} // namespace wcmods
