// CatMoves.hpp: poses and moves for any cat (yours, the game's, a mod's own): sitting, sleeping, rearing up to
// sharpen claws, a sparring stance, lying still, two idles that move; and the game's own animations by name: eating, drinking, sleeping and
// waking, stalking, crouching, pouncing, bowing, cheering, digging, sniffing, meowing... (docs/plans/clan-life.md,
// S1). WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call. Game thread only.
//
// A pose is the cat AnimBlueprint's own state (ABP_CatMaker reads its CharacterSequenceState and FillerState every
// frame: the game's quest givers and camp cats sit and lie by them), so it holds until it's changed. A move is one of
// the game's animations played over whatever the cat does (its montage table's by tag, else its sequence through
// play_animation), some in two parts: a lead-in, then a part that loops until it's stopped (lying down to sleep, then
// sleeping).
#pragma once

#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Animations.hpp>
#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>
#include <WCMods/World.hpp>

namespace wcmods
{
    // ============================================================================================ poses
    enum class Pose
    {
        Stand,      // the AnimBlueprint's own: standing, walking as it moves
        Sit,        // sitting up (CharacterSequenceState Sit), and to one side or the other
        SitLeft,
        SitRight,
        Sleep,      // lying curled up asleep (FillerState Online2)
        Fidget,     // an idle that moves: stretching, settling (Online1, the game's online friends' den cats)
        Playful,    // an idle that moves: low at the front, playful (Online3)
        Rear,       // an idle that moves: scratching at a trunk, now and then up on its hind legs (Sharpen1; the
                    // Sharpen move rears up every time)
        Spar,       // a sparring stance (TrainingStance)
        Strike,     // a low strike (TrainingAttack1)
        Flinch,     // hit while sparring (TrainingHit)
        Still,      // lying still on its side (Dead)
    };
    namespace detail
    {
        struct PoseState
        {
            int sequence;   // ECharacterSequenceState
            int filler;     // EFillerStates
        };
        inline auto pose_state(Pose p) -> PoseState
        {
            switch (p)
            {
            case Pose::Stand: return {0, 0};
            case Pose::Sit: return {6, 0};
            case Pose::SitLeft: return {7, 0};
            case Pose::SitRight: return {8, 0};
            case Pose::Sleep: return {0, 2};
            case Pose::Fidget: return {0, 1};
            case Pose::Playful: return {0, 3};
            case Pose::Rear: return {0, 5};
            case Pose::Spar: return {0, 9};
            case Pose::Strike: return {0, 10};
            case Pose::Flinch: return {0, 12};
            case Pose::Still: return {0, 14};
            }
            return {0, 0};
        }
    } // namespace detail

    inline auto pose_name(Pose p) -> std::wstring_view
    {
        static const wchar_t* names[] = {L"stand", L"sit", L"sit left", L"sit right", L"sleep", L"fidget", L"playful",
                                         L"rear", L"spar", L"strike", L"flinch", L"still"};
        return names[static_cast<int>(p)];
    }

    // Put a cat in a pose; false without its AnimBlueprint (an animal's, or no cat). The pose holds while the cat
    // stands; walking a cat of the mod's own (Npc::walk_to) stands it first.
    inline auto set_pose(UObject* cat, Pose p) -> bool
    {
        if (!assert_game_thread(L"set_pose")) return false;
        UObject* ai = detail::anim_instance(cat);
        if (!ai || !get(ai, L"CharacterSequenceState").property) return false;
        const auto s = detail::pose_state(p);
        set(ai, L"CharacterSequenceState", s.sequence);
        set(ai, L"FillerState", s.filler);
        return true;
    }
    // The pose a cat's in, as set_pose would have put it; nullopt without the AnimBlueprint or in a state of the game's
    // that isn't one of these.
    inline auto pose_of(UObject* cat) -> std::optional<Pose>
    {
        if (!assert_game_thread(L"pose_of")) return std::nullopt;
        UObject* ai = detail::anim_instance(cat);
        if (!ai) return std::nullopt;
        const int sequence = static_cast<int>(get(ai, L"CharacterSequenceState").number(-1.0));
        const int filler = static_cast<int>(get(ai, L"FillerState").number(-1.0));
        for (int i = 0; i <= static_cast<int>(Pose::Still); ++i)
        {
            const auto s = detail::pose_state(static_cast<Pose>(i));
            if (s.sequence == sequence && s.filler == filler) return static_cast<Pose>(i);
        }
        return std::nullopt;
    }

    // ============================================================================================ moves
    enum class Move
    {
        Meow,
        Sniff,
        Dig,
        Sharpen,     // claws down a trunk, up on its hind legs
        Play,        // batting at something
        Yawn,
        Stretch,
        Shake,
        Alert,       // ears up, looking about
        Angry,       // fur up, hissing
        Bow,         // dipping its head (the game's reverence)
        Cheer,       // a victory, then held (loops)
        Eat,         // eating, head down (loops)
        Drink,       // lapping (a lead-in, then loops)
        Sleep,       // lying down, then asleep (loops)
        Wake,        // getting up from sleep
        Stalk,       // the hunting crouch, walking (loops: play it while the cat walks slowly)
        Crouch,      // the hunting crouch, still (loops)
        Pounce,      // the hunting leap
        WalkBack,    // stepping backwards (loops)
        Tired,       // a tired walk (loops)
        Surprised,   // startled, sitting (a lead-in, then holds)
    };
    struct CatMoveOptions
    {
        std::optional<double> speed;   // 1 as made
        std::optional<bool> loop;      // keep repeating a move of the sequences' that doesn't loop by itself (the montage
                                       // table's moves, meow to play, play once)
    };
    namespace detail
    {
        inline constexpr const wchar_t* CAT_ANIMS = L"/Game/Art/Characters/CatMaster/Animations/";
        struct MoveSpec
        {
            const wchar_t* name;
            const wchar_t* tag;    // the cat's montage table's row, or nullptr
            const wchar_t* in;     // a sequence (under CAT_ANIMS), played once
            const wchar_t* loop;   // then this one, looping (or nullptr)
        };
        inline auto move_spec(Move m) -> MoveSpec
        {
            switch (m)
            {
            case Move::Meow: return {L"meow", L"Animation.Exploration.Meow", nullptr, nullptr};
            case Move::Sniff: return {L"sniff", L"Animation.Exploration.Interaction.Sniff", nullptr, nullptr};
            case Move::Dig: return {L"dig", L"Animation.Exploration.Interaction.Dig", nullptr, nullptr};
            case Move::Sharpen: return {L"sharpen", L"Animation.Exploration.Interaction.Sharpen", nullptr, nullptr};
            case Move::Play: return {L"play", L"Animation.Exploration.Interaction.Play.Toy", nullptr, nullptr};
            case Move::Yawn: return {L"yawn", nullptr, L"A_CatMaster_Yawn_1", nullptr};
            case Move::Stretch: return {L"stretch", nullptr, L"A_CatMaster_Stretch_1", nullptr};
            case Move::Shake: return {L"shake", nullptr, L"A_CatMaster_Shake_1", nullptr};
            case Move::Alert: return {L"alert", nullptr, L"A_CatMaster_Alert_1", nullptr};
            case Move::Angry: return {L"angry", nullptr, L"A_CatMaster_Angry_1", nullptr};
            case Move::Bow: return {L"bow", nullptr, L"Cinematic/A_CatMaster_Reverence_1", nullptr};
            case Move::Cheer: return {L"cheer", nullptr, L"Combat/A_CatMaster_Win_In_1", L"Combat/A_CatMaster_Win_Loop_1"};
            case Move::Eat: return {L"eat", nullptr, nullptr, L"A_CatMaster_Eat_Loop_1"};
            case Move::Drink: return {L"drink", nullptr, L"A_CatMaster_Drinking_In_1", L"A_CatMaster_Drinking_Loop_1"};
            case Move::Sleep: return {L"sleep", nullptr, L"A_CatMaster_Sleep_In_1", L"A_CatMaster_Sleep_Loop_1"};
            case Move::Wake: return {L"wake", nullptr, L"A_CatMaster_Sleep_End_1", nullptr};
            case Move::Stalk: return {L"stalk", nullptr, nullptr, L"A_CatMaster_Walk_Crouching_1"};
            case Move::Crouch: return {L"crouch", nullptr, nullptr, L"A_CatMaster_Stand_Crouching_3"};
            case Move::Pounce: return {L"pounce", nullptr, L"Combat/OffensiveStance/A_CatMaster_WC_Hunting_Leap", nullptr};
            case Move::WalkBack: return {L"walk back", nullptr, nullptr, L"A_CatMaster_Walk_Back_1"};
            case Move::Tired: return {L"tired", nullptr, nullptr, L"A_CatMaster_Walk_Tired_1"};
            case Move::Surprised:
                return {L"surprised", nullptr, L"Cinematic/A_CatMaster_Sitting_Surprise_In_1", L"Cinematic/A_CatMaster_Sitting_Surprise_Loop_1"};
            }
            return {L"", nullptr, nullptr, nullptr};
        }
        // A sequence's object path ("A_CatMaster_Yawn_1" -> "/Game/.../A_CatMaster_Yawn_1.A_CatMaster_Yawn_1").
        inline auto cat_anim_path(std::wstring_view rel) -> std::wstring
        {
            const size_t slash = rel.find_last_of(L'/');
            const std::wstring_view name = slash == std::wstring_view::npos ? rel : rel.substr(slash + 1);
            return std::wstring(CAT_ANIMS) + std::wstring(rel) + L"." + std::wstring(name);
        }
        // Each cat's two-part move under way: the lead-in's montage, and the timer that starts the loop after it.
        struct MoveChain
        {
            UObject* lead{};
            TimerId timer{};
        };
        inline auto move_chains() -> std::map<UObject*, MoveChain>&
        {
            static std::map<UObject*, MoveChain> chains;
            return chains;
        }
        inline auto end_chain(UObject* cat) -> void
        {
            auto& chains = move_chains();
            auto it = chains.find(cat);
            if (it == chains.end()) return;
            if (it->second.timer) cancel(it->second.timer);
            chains.erase(it);
        }
    } // namespace detail

    inline auto move_name(Move m) -> std::wstring_view { return detail::move_spec(m).name; }

    // Play one of the game's moves on a cat: the montage playing it now (the lead-in's, for a two-part move), or
    // nullptr (no AnimBlueprint, or the game wouldn't play it). It plays over what the cat does; a two-part move goes on
    // into its loop by itself when the lead-in ends, and a looping one plays until stop_move or another move.
    inline auto play_move(UObject* cat, Move m, CatMoveOptions o = {}) -> UObject*
    {
        if (!assert_game_thread(L"play_move") || !cat) return nullptr;
        detail::end_chain(cat);
        const detail::MoveSpec s = detail::move_spec(m);
        const double speed = o.speed.value_or(1.0);
        if (s.tag) return play_montage(cat, s.tag, speed);
        if (!s.in && s.loop) return play_animation(cat, detail::cat_anim_path(s.loop), {.loop = true, .speed = speed});
        UObject* lead = play_animation(cat, detail::cat_anim_path(s.in), {.loop = o.loop.value_or(false) && !s.loop, .speed = speed});
        if (!lead || !s.loop) return lead;
        // the loop as the lead-in ends: its length less the blend, at this speed
        UObject* seq = load(detail::cat_anim_path(s.in));
        auto length = seq ? call_reflected(seq, STR("GetPlayLength")) : std::nullopt;
        const double seconds = (length ? length->get(L"ReturnValue").number(1.0) : 1.0) / (speed > 0 ? speed : 1.0);
        const std::wstring loop = detail::cat_anim_path(s.loop);
        auto& chain = detail::move_chains()[cat];
        chain.lead = lead;
        chain.timer = after(std::max(0.05, seconds - detail::ANIM_BLEND - 0.05), [cat, lead, loop, speed] {
            auto& chains = detail::move_chains();
            auto it = chains.find(cat);
            if (it == chains.end() || it->second.lead != lead) return;   // stopped, or another move since
            chains.erase(it);
            if (!detail::object_staying(cat, nullptr)) return;
            // still playing (blending out by now: the game no longer calls it the active montage, but it plays), not
            // stopped or played over
            UObject* ai = detail::anim_instance(cat);
            auto playing = ai ? call_reflected(ai, STR("Montage_IsPlaying"), [&](Params& p) { p.set_nth(0, Value::of(lead)); }) : std::nullopt;
            if (!playing || !playing->get(L"ReturnValue").boolean()) return;
            play_animation(cat, loop, {.loop = true, .speed = speed});
        });
        return lead;
    }

    // Stop whatever move (or montage) plays on a cat, blending out over `blend` seconds; a two-part move's loop isn't
    // started after.
    inline auto stop_move(UObject* cat, double blend = 0.25) -> void
    {
        if (!assert_game_thread(L"stop_move") || !cat) return;
        detail::end_chain(cat);
        UObject* ai = detail::anim_instance(cat);
        if (!ai) return;
        auto now = call_reflected(ai, STR("GetCurrentActiveMontage"));
        UObject* m = now ? now->get(L"ReturnValue").object : nullptr;
        if (!m) return;   // (never call into a montage that isn't there)
        call_reflected(ai, STR("Montage_Stop"), [&](Params& p) {
            p.set_nth(0, Value::of(blend));
            p.set_nth(1, Value::of(m));
        });
    }

    // Whether a move is one a cat walks in (Stalk, WalkBack, Tired): a walk keeps it playing, and stops the others.
    inline auto walking_move(Move m) -> bool { return m == Move::Stalk || m == Move::WalkBack || m == Move::Tired; }

    // The sequences a move plays (its lead-in and its loop, as object paths; empty for a montage-table move), for a mod
    // that wants to know or preload them.
    inline auto move_sequences(Move m) -> std::vector<std::wstring>
    {
        const detail::MoveSpec s = detail::move_spec(m);
        std::vector<std::wstring> out;
        if (s.in) out.push_back(detail::cat_anim_path(s.in));
        if (s.loop) out.push_back(detail::cat_anim_path(s.loop));
        return out;
    }
} // namespace wcmods
