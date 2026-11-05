// Animations.hpp: mods' own animations (animations.json, listed by the install in WCModsAnims.json) and the game's
// animation sequences, played on a cat or an animal over what it's doing, in the slot its AnimBlueprint plays the
// game's own montages in. As Lua's Game.anims (docs/scripting.md), which these follow. Game thread only. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods", documents every call.
//
//   wcmods::play_animation(wcmods::player(), L"my-mod/Wave");              // once
//   wcmods::play_animation(npc, L"my-mod/Swim", {.loop = true});           // until stop_animation(npc)
//
// A mod's animation is for one kind of animal (its "for": cats, mice...): another kind can't play it.
#pragma once

#include <algorithm>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <WCMods/Core.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>

namespace wcmods
{
    // A mod's animation, as the install lists it: `id` ("<mod>/<animation>"), `name`, `kind` (the animal it's for:
    // L"cat", L"mouse"...), `path` (its sequence's object path), `loop`, `speed`, `blend` (seconds in and out),
    // `seconds` (its length), and whether it's an `emote` (on the emote wheel, with its `key`).
    struct Animation
    {
        std::wstring id, name, kind, path, key;
        bool loop{}, emote{};
        double speed{1.0}, blend{0.25}, seconds{};
    };
    // How to play one: `loop` until it's stopped, `speed`, `blend` (seconds in and out); a mod's animation brings
    // its own, and these override them.
    struct AnimationOptions
    {
        std::optional<bool> loop;
        std::optional<double> speed, blend;
    };

    namespace detail
    {
        inline constexpr const wchar_t* ANIM_SLOT = L"DefaultSlot";
        inline constexpr int ANIM_LOOPS = 100000;   // a looping animation: this many times over, until it's stopped
        inline constexpr double ANIM_BLEND = 0.25;

        // The install's WCModsAnims.json ({"animations": {id: {...}}, "kinds": {kind: [mesh names]}}), read once.
        inline auto anims_data() -> const Json&
        {
            static Json data;
            static std::once_flag read;
            std::call_once(read, [] {
                auto text = read_file(mod().installed.parent_path() / L"shared" / L"WCModsAnims" / L"WCModsAnims.json");
                auto parsed = text ? Json::parse(*text) : std::nullopt;
                data = parsed ? *parsed : Json::object();
            });
            return data;
        }
        // The mesh an actor's AnimBlueprint runs on: a character's Mesh, else its first skeletal mesh (quest givers).
        inline auto anim_mesh(UObject* actor) -> UObject*
        {
            if (!actor) return nullptr;
            if (UObject* mesh = get(actor, L"Mesh").object) return mesh;
            UObject* cls = object(STR("/Script/Engine.SkeletalMeshComponent"));
            auto r = cls ? call_reflected(actor, STR("GetComponentByClass"), [&](Params& p) { p.set_nth(0, Value::of(cls)); })
                         : std::nullopt;
            return r ? r->get(L"ReturnValue").object : nullptr;
        }
        inline auto anim_instance(UObject* actor) -> UObject*
        {
            UObject* mesh = anim_mesh(actor);
            auto r = mesh ? call_reflected(mesh, STR("GetAnimInstance")) : std::nullopt;
            return r ? r->get(L"ReturnValue").object : nullptr;
        }
        // The montage an anim instance plays now, and the sequence that montage plays (its first slot's first
        // segment) as its object path.
        inline auto current_montage(UObject* ai) -> UObject*
        {
            auto r = ai ? call_reflected(ai, STR("GetCurrentActiveMontage")) : std::nullopt;
            return r ? r->get(L"ReturnValue").object : nullptr;
        }
        inline auto montage_sequence(UObject* montage) -> std::wstring
        {
            UObject* seq = montage ? get(montage, L"SlotAnimTracks[0].AnimTrack.AnimSegments[0].AnimReference").object : nullptr;
            return seq ? seq->GetPathName() : std::wstring{};
        }
        inline auto montage_playing(UObject* ai, UObject* montage) -> bool
        {
            auto r = ai && montage ? call_reflected(ai, STR("Montage_IsPlaying"), [&](Params& p) { p.set_nth(0, Value::of(montage)); })
                                   : std::nullopt;
            return r && r->get(L"ReturnValue").boolean();
        }
        // What this mod played on each actor that isn't a mod's animation (a game sequence by its path): its path.
        inline auto played_paths() -> std::vector<std::wstring>&
        {
            static std::vector<std::wstring> paths;
            return paths;
        }
    } // namespace detail

    // Every mod's animation the install has (none without the WCModsAnims.json an install with animations writes).
    inline auto animations() -> std::vector<Animation>
    {
        std::vector<Animation> out;
        const Json& list = detail::anims_data()["animations"];
        for (size_t i = 0; i < list.keys().size(); ++i)
        {
            const Json& a = list.values()[i];
            Animation x;
            x.id = wide(list.keys()[i]);
            x.name = a["name"].wstring();
            x.kind = a["kind"].wstring();
            x.path = a["path"].wstring();
            x.key = a["key"].wstring();
            x.loop = a["loop"].boolean();
            x.emote = a["emote"].boolean();
            x.speed = a["speed"].number(1.0);
            x.blend = a["blend"].number(detail::ANIM_BLEND);
            x.seconds = a["seconds"].number();
            out.push_back(std::move(x));
        }
        return out;
    }
    inline auto animation(std::wstring_view id) -> std::optional<Animation>
    {
        for (Animation& a : animations())
            if (a.id == id) return a;
        return std::nullopt;
    }

    // What kind of animal an actor is, by its mesh (L"cat", L"mouse", L"bird"...), as animations are made for; empty
    // for one that's none of them.
    inline auto animation_kind(UObject* actor) -> std::wstring
    {
        if (!assert_game_thread(L"animation_kind")) return {};
        UObject* mesh = detail::anim_mesh(actor);
        auto r = mesh ? call_reflected(mesh, STR("GetSkeletalMeshAsset")) : std::nullopt;
        UObject* sk = r ? r->get(L"ReturnValue").object : nullptr;
        if (!sk) return {};
        const std::wstring mesh_name = name(sk);
        const Json& kinds = detail::anims_data()["kinds"];
        if (!kinds.is_object()) return mesh_name == L"SK_CatMaster" ? L"cat" : L"";
        for (size_t i = 0; i < kinds.keys().size(); ++i)
            for (const Json& m : kinds.values()[i].values())
                if (m.wstring() == mesh_name) return wide(kinds.keys()[i]);
        return {};
    }

    // Play an animation on a cat or an animal: a mod's by its id (L"my-mod/Wave"), or one of the game's sequences by
    // its object path (L"/Game/.../A_CatMaster_Meow.A_CatMaster_Meow"). It plays over what the actor is doing and
    // ends by itself unless it loops. The montage playing it, or nullptr (with a line in the log) for an id the
    // install hasn't got, an animal the animation isn't for, a sequence that won't load, or an actor with no
    // AnimBlueprint.
    inline auto play_animation(UObject* actor, std::wstring_view id, AnimationOptions options = {}) -> UObject*
    {
        if (!assert_game_thread(L"play_animation") || !actor) return nullptr;
        auto info = animation(id);
        std::wstring path = info ? info->path : (id.starts_with(L"/Game/") ? std::wstring(id) : std::wstring{});
        if (path.empty())
        {
            log(L"play_animation: there's no animation {}", id);
            return nullptr;
        }
        if (info && !info->kind.empty())
        {
            std::wstring kind = animation_kind(actor);
            if (kind != info->kind)
            {
                log(L"play_animation: {} is for {}, not {}", info->name, info->kind, kind.empty() ? L"this one" : kind);
                return nullptr;
            }
        }
        UObject* seq = load(path);
        UObject* ai = detail::anim_instance(actor);
        if (!seq || !ai)
        {
            log(L"play_animation: {}", seq ? L"it has no AnimBlueprint to play it" : L"couldn't load " + path);
            return nullptr;
        }
        const bool loop = options.loop.value_or(info && info->loop);
        const double speed = options.speed.value_or(info ? info->speed : 1.0);
        const double blend = options.blend.value_or(info ? info->blend : detail::ANIM_BLEND);
        auto r = call_reflected(ai, STR("PlaySlotAnimationAsDynamicMontage"), [&](Params& p) {
            p.set_nth(0, Value::of(seq));
            p.set_nth(1, Value::of(std::wstring_view(detail::ANIM_SLOT)));
            p.set_nth(2, Value::of(blend));
            p.set_nth(3, Value::of(blend));
            p.set_nth(4, Value::of(speed));
            p.set_nth(5, Value::of(loop ? detail::ANIM_LOOPS : 1));
            p.set_nth(6, Value::of(-1.0));
            p.set_nth(7, Value::of(0.0));
        });
        UObject* montage = r ? r->get(L"ReturnValue").object : nullptr;
        if (!montage)
        {
            log(L"play_animation: the game didn't play {}", id);
            return nullptr;
        }
        if (!info)
        {
            auto& paths = detail::played_paths();
            if (std::find(paths.begin(), paths.end(), path) == paths.end()) paths.push_back(path);
        }
        return montage;
    }

    // The animation play_animation started on an actor that still plays: a mod's by its id (whichever mod or script
    // started it, Lua's Game.anims too: it's known by the sequence the actor's montage plays), or a game sequence's
    // path this mod played. Empty when it plays none of them (the game's own montages never count).
    inline auto animation_playing(UObject* actor) -> std::wstring
    {
        if (!assert_game_thread(L"animation_playing")) return {};
        UObject* ai = detail::anim_instance(actor);
        UObject* m = detail::current_montage(ai);
        if (!m || !detail::montage_playing(ai, m)) return {};
        std::wstring seq = detail::montage_sequence(m);
        if (seq.empty()) return {};
        for (Animation& a : animations())
            if (a.path == seq) return a.id;
        for (const std::wstring& p : detail::played_paths())
            if (p == seq) return p;
        return {};
    }

    // Stop what animation_playing() names on an actor, blending out over `blend` seconds (the animation's own by
    // default). False when it plays none of those: the game's own montages are never stopped.
    inline auto stop_animation(UObject* actor, std::optional<double> blend = std::nullopt) -> bool
    {
        if (!assert_game_thread(L"stop_animation")) return false;
        std::wstring playing = animation_playing(actor);
        if (playing.empty()) return false;
        UObject* ai = detail::anim_instance(actor);
        UObject* m = detail::current_montage(ai);
        auto info = animation(playing);
        const double out = blend.value_or(info ? info->blend : detail::ANIM_BLEND);
        return call_reflected(ai, STR("Montage_Stop"), [&](Params& p) {
                   p.set_nth(0, Value::of(out));
                   p.set_nth(1, Value::of(m));
               }).has_value();
    }
} // namespace wcmods
