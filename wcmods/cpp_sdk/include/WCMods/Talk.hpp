// Talk.hpp: conversations. The game's dialogue box with a line of the mod's own (as Lua's Game.dialogue shows it),
// and the game's own talks: each read as data from its graph (its lines, who says them, its answers and where each
// leads), a story talk filled from the game's tables as the game fills it, and played in that box, line by line, as
// the mod moves it on, a bond talk's answers doing to your bonds what the game's do. Game thread only. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods", documents every call.
//
// Why not the game's own player: its sequencer manager (PlaySequenceDialogue) opens the talk's box as a popup of the
// game's screen, which only the talk's scene closes cleanly. Closed any other way (moved past its last line, or the
// game quitting with it still open) the screen's popup release reads a link the release has just cleared, and the
// game crashes; and a second talk after one ended early isn't tracked by the manager at all (docs/reverse-engineering.md,
// "Talks in game"). The box here is made outside the screens' popups, as say() always has, and is safe to take down any time.
#pragma once

#include <algorithm>
#include <cwctype>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <WCMods/Bonds.hpp>
#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Looks.hpp>
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
            bool shown{};    // a line is up (its words may be empty)
            bool fading{};   // hide_talk's fade-out is playing
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
        // Only what changed is written while a line is up (the box lays out again on each); all of it after a hide.
        if (!s.shown || std::wstring(speaker) != s.name) Widget(get(b, L"mcGuiDialogueTalker.mcGuiTextName").object).set_text(speaker);
        if (!s.shown || std::wstring(words) != s.words) Widget(get(b, L"mcGuiTextParagraph").object).set_text(words);
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
        else if (s.fading)
            s.box.play(L"AniScreenIn");   // back in from hide_talk's fade-out, which would leave it faded
        s.fading = false;
        s.shown = true;
        if (adding || answers != s.answers) detail::show_answers(b, answers);
        s.name = speaker;
        s.words = words;
        s.answers = answers;
        return true;
    }
    // Take say()'s box down, fading out as the game's does; false when it isn't up. A talk playing in it ends.
    inline auto hide_talk() -> bool;
    // Whether say()'s box shows a line now.
    inline auto talk_showing() -> bool { return detail::say_state().shown && detail::say_state().box; }
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
        std::wstring sub_tag;           // a story talk's node (a line, an answer): its row is the talk's tag, a dot and this
        std::wstring fallback_tag;      // a bond answer's FallbackDialogueTag: its row's prefix when the talk has no tag
    };
    // A talk: one read from the game's graph, or one a mod makes itself (nodes with `line`, `words`, `source` 3 and
    // `source_words` for the speaker, `next` and `answers` by index; `graph` and `node` left empty).
    struct Talk
    {
        UObject* graph{};
        std::vector<TalkNode> nodes;
        std::vector<int> roots;
        // Its rows' prefix: a story talk's tag (a BondDialogue's DialogueTag, or story_talk's). A quest's talk has none of
        // its own: the game uses the quest's row prefix (its tag and rank, L"Quest.Procedural.Survival.Gather.Apprentice",
        // set as the quest plays it), so a mod playing one sets it for its answers to resolve the quest's rows.
        std::wstring tag;
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
                n.sub_tag = get(o, L"SubTag").string();
                n.fallback_tag = get(o, L"FallbackDialogueTag.TagName").string();
                if (n.fallback_tag == L"None") n.fallback_tag.clear();
                n.words_text = get(o, L"Paragraph");
                if (n.words_text.kind == Value::Kind::Text && n.words_text.text.empty())
                    for (auto& more : elements(o, L"MultiParagraph"))   // a QuestDialogueMultiTextTalkingNode's
                        if (more.kind == Value::Kind::Text && !more.text.empty())
                        {
                            n.words_text = more;
                            break;
                        }
                if (n.words_text.kind == Value::Kind::Text)
                {
                    n.line = !n.words_text.text.empty();   // an empty one is passed like an action
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
        t.tag = get(graph, L"DialogueTag.TagName").string();
        if (t.tag == L"None") t.tag.clear();
        return t;
    }

    // The row a bond answer node resolves (QuestDialogueActionResolveBondAnswer, as the game's code joins it): the talk's
    // tag (a story talk's; for a quest's talk the game's is the quest's row prefix, which `tag` must be given), else the
    // node's FallbackDialogueTag, a dot and its SubTag. Empty for any other node, or one with neither.
    inline auto bond_answer_row(const Talk& talk, const TalkNode& n) -> std::wstring
    {
        if (n.kind != L"QuestDialogueActionResolveBondAnswer" || n.sub_tag.empty()) return {};
        const std::wstring& prefix = !talk.tag.empty() ? talk.tag : n.fallback_tag;
        return prefix.empty() ? std::wstring{} : prefix + L"." + n.sub_tag;
    }

    namespace detail
    {
        // The template a story tag plays the `time`th time you talk (the game's choice, read from its code,
        // docs/reverse-engineering.md, "Templates, filled in as they play"): the first kind its tag is under, and that
        // kind's template for the time (the last repeats; Monologue.Interaction has none after its third).
        inline auto story_template(std::wstring_view tag, int time) -> std::wstring
        {
            static const std::vector<std::pair<std::wstring, std::vector<std::wstring>>> kinds = {
                {L"Gameplay.Dialogue.Story.Long", {L"Long", L"End"}},
                {L"Gameplay.Dialogue.Story.Short", {L"Short", L"End"}},
                {L"Gameplay.Dialogue.Story.Monologue.Interaction", {L"Monologue_Interaction_1", L"Monologue_Interaction_2", L"Monologue_Interaction_3"}},
                {L"Gameplay.Dialogue.Story.Monologue.Filler", {L"Monologue_Filler"}},
                {L"Gameplay.Dialogue.Story.Monologue.Encounter", {L"Monologue_Encounter"}},
                {L"Gameplay.Dialogue.Activity.Transition", {L"Activity_Transition"}},
            };
            if (time < 1) return {};
            for (auto& [parent, types] : kinds)
                if (tag == parent || (tag.size() > parent.size() && tag.substr(0, parent.size()) == parent && tag[parent.size()] == L'.'))
                {
                    if (parent == L"Gameplay.Dialogue.Story.Monologue.Interaction" && static_cast<size_t>(time) > types.size()) return {};
                    return types[std::min(static_cast<size_t>(time), types.size()) - 1];
                }
            return {};
        }
        inline auto lower_key(std::wstring s) -> std::wstring
        {
            for (auto& c : s) c = static_cast<wchar_t>(std::towlower(c));
            return s;
        }
    } // namespace detail

    // One of the game's story talks by its tag (L"Gameplay.Dialogue.Story.Short.TheMistrustfulLeader.Main.7"), as the game
    // plays it the `time`th time you have it: its template (the quest manager's StoryDialogueTemplates: Short or Long
    // the first time and End after, Monologue.Interaction 1 to 3, a Filler's, an Encounter's...) filled from the rows
    // under the tag (talk_rows): each line's words and who says them (its row's Talker), a bonding line's words for each
    // clan bond (its .Neutral, .Positive and .Negative rows), and each answer's words, trait, score and bonding (the
    // row of the bond answer it leads to). `tag` is set, so playing it applies its answers' bonds (TalkHooks). A line
    // whose words vary by rank or role takes its first variant. An empty Talk for a tag that's none of those kinds, no
    // template for the time, or no rows.
    inline auto story_talk(std::wstring_view tag, int time = 1) -> Talk
    {
        if (!assert_game_thread(L"story_talk")) return {};
        std::wstring kind = detail::story_template(tag, time);
        if (kind.empty()) return {};
        UObject* graph = nullptr;
        for (auto& [k, v] : map_entries(manager(STR("quests")), L"StoryDialogueTemplates"))
        {
            std::wstring name = k.string();
            if (auto at = name.find(L"::"); at != std::wstring::npos) name = name.substr(at + 2);
            if (name == kind) graph = v.object;
        }
        std::map<std::wstring, TalkRow> rows;   // by lower-case name: the game's names ignore case
        for (auto& r : talk_rows(std::wstring(tag) + L"."))
            rows.emplace(detail::lower_key(r.name), std::move(r));
        if (!graph || rows.empty()) return {};
        Talk t = read_talk(graph);
        if (!t) return {};
        t.tag = tag;
        auto row = [&](const std::wstring& sub) -> const TalkRow* {
            auto it = rows.find(detail::lower_key(std::wstring(tag) + L"." + sub));
            return it == rows.end() ? nullptr : &it->second;
        };
        for (auto& n : t.nodes)
        {
            if (n.sub_tag.empty() || n.kind == L"QuestDialogueActionResolveBondAnswer") continue;
            if (n.words_text.kind != Value::Kind::Text) continue;   // only a line takes words
            const TalkRow* plain = row(n.sub_tag);
            const TalkRow* first = plain;
            n.by_bond.clear();
            static const wchar_t* bonds[] = {L"Neutral", L"Positive", L"Negative"};
            for (size_t b = 0; b < 3; ++b)
                if (const TalkRow* v = row(n.sub_tag + L"." + bonds[b]))
                {
                    n.by_bond.resize(b + 1);
                    n.by_bond[b] = v->text();
                    if (!first) first = v;
                }
            if (!first)   // a variant by rank or role: the first there is
            {
                std::wstring under = detail::lower_key(std::wstring(tag) + L"." + n.sub_tag + L".");
                for (auto& [name, r] : rows)
                    if (name.compare(0, under.size(), under) == 0)
                    {
                        first = &r;
                        break;
                    }
            }
            n.words = first ? first->text() : std::wstring{};
            n.words_text = Value{};
            n.line = !n.words.empty();
            if (first) n.source = first->talker == L"Player" ? 1 : 0;
        }
        for (auto& n : t.nodes)
            for (auto& a : n.answers)
            {
                if (a.to < 0 || static_cast<size_t>(a.to) >= t.nodes.size()) continue;
                const TalkNode& child = t.nodes[a.to];
                if (child.sub_tag.empty()) continue;
                if (const TalkRow* r = row(child.sub_tag))
                {
                    a.words = r->text();
                    a.trait = r->trait;
                    a.score = r->score;
                    a.bonding = r->clan_bonding;
                }
            }
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
        // A bond talk's answers (its ResolveBondAnswer nodes, as the talk passes them after an answer) do to your bonds
        // what the game's do (answer_bond, Bonds.hpp), with the story cat `role` names (L"TheMistrustfulLeader"), else
        // the one `cat` plays (role_of, as play_talk starts: the cat isn't read after); with neither, none is applied
        // (the game always has the cat talked to). Unless `bonds` is false. `on_bond` is told what each did.
        UObject* cat{};
        std::wstring role;
        bool bonds{true};
        std::function<void(const TalkNode&, const BondAnswer&)> on_bond;
    };
    namespace detail
    {
        struct TalkPlay
        {
            std::shared_ptr<const Talk> talk;   // shared: a hook holds on to it while it runs, whatever it plays
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
            const std::shared_ptr<const Talk> talk = p.talk;   // kept while a hook below may play another
            const size_t count = talk->nodes.size();
            for (size_t steps = 0; to >= 0 && static_cast<size_t>(to) < count && steps <= count; ++steps)
            {
                const TalkNode& n = talk->nodes[to];
                if (n.line)
                {
                    p.at = to;
                    std::vector<std::wstring> answers;
                    for (auto& a : n.answers) answers.push_back(a.words);
                    if (say(speaker_of(p, n), words_of(p, n), answers)) return true;
                    break;
                }
                to = !n.next.empty() ? n.next.front() : !n.answers.empty() ? n.answers.front().to : -1;
                if (p.hooks.bonds && (p.hooks.cat || !p.hooks.role.empty()))   // the cat's role read as it started
                {
                    std::wstring row = bond_answer_row(*talk, n);
                    if (!row.empty())
                    {
                        auto done = answer_bond(row, p.hooks.role);
                        if (done && p.hooks.on_bond)
                        {
                            const int gen = p.generation;
                            auto hook = p.hooks.on_bond;
                            hook(n, *done);
                            if (p.generation != gen) return p.playing;   // on_bond ended it, or played another
                        }
                    }
                }
                if (p.hooks.on_action)
                {
                    const int gen = p.generation;
                    auto hook = p.hooks.on_action;   // kept too: the hook may replace p.hooks
                    hook(*talk, n);
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
        p.talk = std::make_shared<const Talk>(std::move(talk));
        p.npc_name = npc_name;
        if (hooks.role.empty() && hooks.cat)   // the cat's story role now: the talk may outlive the cat
            if (auto r = role_of(hooks.cat)) hooks.role = r->story_role;
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
        const std::shared_ptr<const Talk> talk = p.talk;   // kept while on_answer may play another
        const TalkNode& n = talk->nodes[p.at];
        int to = -1;
        if (!n.answers.empty())
        {
            if (answer < 0 || static_cast<size_t>(answer) >= n.answers.size()) return false;
            TalkAnswer chosen = n.answers[answer];
            to = chosen.to;
            if (p.hooks.on_answer)
            {
                const int gen = p.generation;
                auto hook = p.hooks.on_answer;
                hook(n, chosen);
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
        return p.playing && p.at >= 0 && p.talk ? &p.talk->nodes[p.at] : nullptr;
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
        bool was_up = s.box && s.shown;
        s.shown = false;
        if (was_up)
        {
            s.name.clear();
            s.words.clear();
            s.answers.clear();
            int mine = ++s.closing;
            s.fading = true;
            s.box.play(L"AniScreenIn", true);
            after(0.4, [mine] {
                auto& st = detail::say_state();
                if (st.closing != mine) return;   // said again meanwhile
                st.fading = false;
                if (st.box) call_reflected(st.box.object(), STR("RemoveFromParent"));
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
            p.talk.reset();
            auto& s = say_state();
            if (on_game_thread_now() && s.box) call_reflected(s.box.object(), STR("RemoveFromParent"));
            s.shown = s.fading = false;
            s.words.clear();
            s.answers.clear();
        }
    } // namespace detail
} // namespace wcmods
