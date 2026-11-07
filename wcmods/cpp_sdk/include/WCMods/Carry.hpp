// Carry.hpp: something carried in a cat's jaws (docs/plans/clan-life.md, S2): the game's own models of prey (a mouse, a
// rabbit, a bird, a squirrel, a fish), moss, a herb, feathers, or any mesh of the game's, attached to the cat's `mouth`
// bone so it moves with the head through every walk, run, move and look about. Any cat: yours, the game's, a mod's own.
// WCMods.hpp includes it; docs/SDK.md, "C++ mods", documents every call. Game thread only.
//
// The thing is a mesh component added to the cat and attached at the bone, with no collision (it never catches on the
// world or on another cat). The prey is the game's own animals' models in their rest pose, limp, held crosswise with
// the tail or the body hanging; it scales with the cat, so a kit's mouse is smaller.
#pragma once

#include <cmath>
#include <map>
#include <optional>
#include <string>
#include <string_view>

#include <WCMods/Core.hpp>
#include <WCMods/Events.hpp>
#include <WCMods/Game.hpp>
#include <WCMods/Reflect.hpp>

namespace wcmods
{
    enum class Carried
    {
        Mouse,
        Rabbit,
        Bird,
        Squirrel,
        Fish,
        Moss,
        Herb,       // a sprig of willow herb, by the stem
        Feathers,
    };
    // Where a carried thing sits, from the cat's `mouth` bone, in the bone's own axes: X across the jaws (the cat's
    // right), Y back along the head (so less is further forward), Z up through the head; turned yaw (about Z), pitch
    // (about Y), roll (about X) degrees as the engine's rotators turn, and scaled (1: the model as made, at the cat's
    // own scale). The default puts a model as made in the front of the jaws.
    struct CarryPlace
    {
        double scale{1.0};
        Vec3 offset{0, -2.5, -2};
        double yaw{}, pitch{}, roll{};
    };
    namespace detail
    {
        struct CarrySpec
        {
            const wchar_t* name;
            const wchar_t* path;   // the model's object path
            CarryPlace place;      // as it looked right in game (build 26391405)
        };
        inline auto carry_spec(Carried c) -> CarrySpec
        {
            switch (c)
            {
            case Carried::Mouse: return {L"mouse", L"/Game/Art/Characters/Enemy/Mice/Skel/SK_Mice.SK_Mice", {0.5, {0, -2.5, -2}, 90, 0, -30}};
            case Carried::Rabbit:
                return {L"rabbit", L"/Game/Art/Characters/Enemy/Rabbit/Skel/SK_Rabbit.SK_Rabbit", {0.4, {0, -2.5, -3}, 90, 0, -70}};
            case Carried::Bird: return {L"bird", L"/Game/Art/Characters/Enemy/Bird/Skel/SK_Bird.SK_Bird", {0.4, {0, -2.5, -2.5}, 90, 0, -30}};
            case Carried::Squirrel:
                return {L"squirrel", L"/Game/Art/Characters/Enemy/Squirrel/Skel/SK_Squirrel.SK_Squirrel", {0.33, {0, -2.5, -3}, 90, 0, -60}};
            case Carried::Fish: return {L"fish", L"/Game/Art/Vfx/Meshes/SM_VFX_Fish.SM_VFX_Fish", {0.8, {0, -2.5, -1.5}, 90, 0, -30}};
            case Carried::Moss: return {L"moss", L"/Game/Art/Environment/Den/Mesh/SM_GPE_MossMat.SM_GPE_MossMat", {0.14, {0, -2.5, -2}, 0, 0, -25}};
            case Carried::Herb:
                return {L"herb", L"/Game/Art/GameplayElements/Consumables/Meshes/SM_GPE_WillowHerb.SM_GPE_WillowHerb", {0.45, {0, -2.5, -1.5}, 0, 90, 0}};
            case Carried::Feathers:
                return {L"feathers", L"/Game/Art/Environment/Den/Mesh/SM_GPE_BirdFeathers.SM_GPE_BirdFeathers", {1.0, {0, -2.5, -1.5}, 0, 0, -25}};
            }
            return {L"", L"", {}};
        }
        // Each cat's carried component (and the cat's and the component's classes, to know the addresses are still
        // theirs).
        struct Held
        {
            UObject* component{};
            UClass* cat_class{};
            UClass* component_class{};
            std::wstring what;
        };
        inline auto held() -> std::map<UObject*, Held>&
        {
            static std::map<UObject*, Held> all;
            return all;
        }
        inline auto still_held(UObject* cat) -> Held*
        {
            auto& all = held();
            auto it = all.find(cat);
            if (it == all.end()) return nullptr;
            if (!object_staying(cat, it->second.cat_class) || !object_staying(it->second.component, it->second.component_class))
            {
                all.erase(it);
                return nullptr;
            }
            return &it->second;
        }
        // A rotator's quaternion, as the engine makes one (FRotator::Quaternion).
        inline auto set_rotation(const Value& t, double yaw, double pitch, double roll) -> void
        {
            const double d = 3.14159265358979323846 / 360.0;
            const double sy = std::sin(yaw * d), cy = std::cos(yaw * d), sp = std::sin(pitch * d), cp = std::cos(pitch * d),
                         sr = std::sin(roll * d), cr = std::cos(roll * d);
            set(t, L"Rotation.X", cr * sp * sy - sr * cp * cy);
            set(t, L"Rotation.Y", -cr * sp * cy - sr * cp * sy);
            set(t, L"Rotation.Z", cr * cp * sy - sr * sp * cy);
            set(t, L"Rotation.W", cr * cp * cy + sr * sp * sy);
        }
    } // namespace detail

    inline auto carried_name(Carried c) -> std::wstring_view { return detail::carry_spec(c).name; }
    // Where a kind sits in the jaws, for a mod that wants it a little different (bigger, further back...).
    inline auto carried_place(Carried c) -> CarryPlace { return detail::carry_spec(c).place; }
    // Its model's object path.
    inline auto carried_model(Carried c) -> std::wstring_view { return detail::carry_spec(c).path; }

    // Drop what a cat carries (it's gone: a mod that wants it on the ground puts it there); false when it carries nothing.
    inline auto drop_carried(UObject* cat) -> bool
    {
        if (!assert_game_thread(L"drop_carried")) return false;
        detail::Held* h = detail::still_held(cat);
        if (!h) return false;
        UObject* c = h->component;
        detail::held().erase(cat);
        call_reflected(c, STR("K2_DestroyComponent"), [&](Params& p) { p.set_nth(0, Value::of(c)); });
        return true;
    }

    // Move what a cat carries to another place in its jaws; false when it carries nothing.
    inline auto place_carried(UObject* cat, CarryPlace place) -> bool
    {
        if (!assert_game_thread(L"place_carried")) return false;
        detail::Held* h = detail::still_held(cat);
        if (!h) return false;
        auto done = call_reflected(h->component, STR("K2_SetRelativeTransform"), [&](Params& p) {
            Value t = p.nth(0);
            set(t, L"Translation.X", place.offset.x);
            set(t, L"Translation.Y", place.offset.y);
            set(t, L"Translation.Z", place.offset.z);
            detail::set_rotation(t, place.yaw, place.pitch, place.roll);
            set(t, L"Scale3D.X", place.scale);
            set(t, L"Scale3D.Y", place.scale);
            set(t, L"Scale3D.Z", place.scale);
            p.set_nth(1, Value::of(false));   // bSweep
            p.set_nth(3, Value::of(true));    // bTeleport (after the sweep's hit result)
        });
        return done.has_value();
    }

    // Put any mesh of the game's (its object path: a skeletal mesh or a static one) in a cat's jaws, where `place` says;
    // what it carried before is dropped. The component, or nullptr (not a cat with a mesh, a model that won't load).
    inline auto carry_mesh(UObject* cat, std::wstring_view path, CarryPlace place = {}) -> UObject*
    {
        if (!assert_game_thread(L"carry") || !cat) return nullptr;
        UObject* mesh = get(cat, L"Mesh").object;
        UObject* model = mesh ? load(path) : nullptr;
        if (!model)
        {
            if (mesh) log(L"carry: couldn't load {}", std::wstring(path));
            return nullptr;
        }
        const std::wstring kind = class_name(model);
        const bool skeletal = kind == L"SkeletalMesh";
        if (!skeletal && kind != L"StaticMesh")
        {
            log(L"carry: {} is a {}, not a mesh", std::wstring(path), kind);
            return nullptr;
        }
        drop_carried(cat);
        // (and forget the cats gone since: the game destroys a cat's components with it)
        for (auto it = detail::held().begin(); it != detail::held().end();)
            it = detail::object_staying(it->first, it->second.cat_class) ? std::next(it) : detail::held().erase(it);
        UObject* cls = object(skeletal ? STR("/Script/Engine.SkeletalMeshComponent") : STR("/Script/Engine.StaticMeshComponent"));
        auto added = call_reflected(cat, STR("AddComponentByClass"), [&](Params& p) {
            p.set_nth(0, Value::of(cls));
            p.set_nth(1, Value::of(true));   // bManualAttachment: attached below, at the bone
            Value t = p.nth(2);
            set(t, L"Rotation.W", 1.0);
            set(t, L"Scale3D.X", 1.0);
            set(t, L"Scale3D.Y", 1.0);
            set(t, L"Scale3D.Z", 1.0);
            p.set_nth(3, Value::of(false));
        });
        UObject* c = added ? added->get(L"ReturnValue").object : nullptr;
        if (!c) return nullptr;
        // (SetSkeletalMesh isn't a UFUNCTION in UE 5: SetSkeletalMeshAsset is)
        if (skeletal) call_reflected(c, STR("SetSkeletalMeshAsset"), [&](Params& p) { p.set_nth(0, Value::of(model)); });
        else call_reflected(c, STR("SetStaticMesh"), [&](Params& p) { p.set_nth(0, Value::of(model)); });
        call_reflected(c, STR("SetCollisionEnabled"), [&](Params& p) { p.set_nth(0, Value::of(0)); });   // NoCollision
        call_reflected(c, STR("K2_AttachToComponent"), [&](Params& p) {
            p.set_nth(0, Value::of(mesh));
            p.set_nth(1, Value::of(L"mouth"));
            for (int rule = 2; rule <= 4; ++rule) p.set_nth(rule, Value::of(0));   // KeepRelative: placed from the bone
            p.set_nth(5, Value::of(false));
        });
        detail::held()[cat] = {c, cat->GetClassPrivate(), c->GetClassPrivate(), std::wstring(path)};
        place_carried(cat, place);
        return c;
    }

    // Put one of the game's things in a cat's jaws (a mouse, a rabbit, a bird, a squirrel, a fish, moss, a herb,
    // feathers), where it looks right unless `place` says otherwise; what it carried before is dropped. The component,
    // or nullptr.
    inline auto carry(UObject* cat, Carried what, std::optional<CarryPlace> place = std::nullopt) -> UObject*
    {
        const detail::CarrySpec s = detail::carry_spec(what);
        UObject* c = carry_mesh(cat, s.path, place.value_or(s.place));
        if (c) detail::held()[cat].what = s.name;
        return c;
    }

    // What a cat carries: the kind's name ("mouse"), or the model's path for one carry_mesh put there; nullopt for
    // nothing.
    inline auto carrying(UObject* cat) -> std::optional<std::wstring>
    {
        if (!assert_game_thread(L"carrying")) return std::nullopt;
        detail::Held* h = detail::still_held(cat);
        return h ? std::optional<std::wstring>(h->what) : std::nullopt;
    }
} // namespace wcmods
