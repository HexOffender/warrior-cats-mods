// Carry.hpp: something in a cat's jaws, on request ("carry"), for tests/game/test_cpp_sdk.py. A cat of the mod's own is
// put in front of your cat and given each kind in turn (each one dropping the one before), each read back from the
// engine: attached to the cat's mesh at `mouth`, its model on it, at the jaws, at its scale, with no collision. Then
// with a mouse it puts its head down to eat and walks (the mouse goes with the head), the mouse is moved in its jaws
// and dropped; your cat carries moss; a thing detached by something else isn't counted; a mesh without a `mouth` bone
// carries nothing; a cat removed with a mouse in its jaws carries nothing.
#include "checks.hpp"

#include <algorithm>
#include <cmath>
#include <memory>
#include <string>

namespace t
{
    namespace
    {
        struct CarryRun
        {
            Npc cat;
            size_t next{};
            UObject* last{};
            Json kinds = Json::object();
            double size{0.8};
            double mouse_z{};
            Vec3 start{};
        };
        constexpr Carried KINDS[] = {Carried::Mouse, Carried::Rabbit, Carried::Bird, Carried::Squirrel,
                                     Carried::Fish, Carried::Moss, Carried::Herb, Carried::Feathers};

        auto vec(const Value& v) -> Vec3 { return {get(v, L"X").number(), get(v, L"Y").number(), get(v, L"Z").number()}; }
        auto distance(Vec3 a, Vec3 b) -> double { return std::sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y) + (a.z - b.z) * (a.z - b.z)); }
        auto mouth_of(UObject* actor) -> Vec3
        {
            UObject* mesh = get(actor, L"Mesh").object;
            auto r = mesh ? call_reflected(mesh, STR("GetSocketLocation"), [&](Params& p) { p.set_nth(0, Value::of(L"mouth")); }) : std::nullopt;
            return r ? vec(r->get(L"ReturnValue")) : Vec3{};
        }
        auto where(UObject* c) -> Vec3
        {
            auto r = call_reflected(c, STR("K2_GetComponentLocation"));
            return r ? vec(r->get(L"ReturnValue")) : Vec3{};
        }
        // What the engine says of a carried component: what it's attached to and where, its model, how far from the
        // cat's mouth (as on a size-1 cat), its scale and its collision.
        auto read(UObject* actor, UObject* c, double size) -> Json
        {
            Json j = Json::object();
            auto parent = call_reflected(c, STR("GetAttachParent"));
            j.set("attached", Json(parent && parent->get(L"ReturnValue").object == get(actor, L"Mesh").object));
            auto socket = call_reflected(c, STR("GetAttachSocketName"));
            j.set("socket", Json(text(socket ? socket->get(L"ReturnValue").text : L"")));
            const bool skeletal = class_name(c) == L"SkeletalMeshComponent";
            // (a static mesh component's mesh is its StaticMesh property: GetStaticMesh isn't a function there)
            auto model = skeletal ? call_reflected(c, STR("GetSkeletalMeshAsset")) : std::nullopt;
            UObject* m = skeletal ? (model ? model->get(L"ReturnValue").object : nullptr) : get(c, L"StaticMesh").object;
            j.set("model", Json(text(full_name(m))));
            j.set("from_mouth", Json(distance(where(c), mouth_of(actor)) / size));
            j.set("scale", Json(get(c, L"RelativeScale3D.X").number()));
            auto collision = call_reflected(c, STR("GetCollisionEnabled"));
            j.set("collision", Json(collision ? collision->get(L"ReturnValue").number(-1) : -1.0));
            return j;
        }

        auto finish(const std::shared_ptr<CarryRun>& r) -> void
        {
            value("carry.kinds", r->kinds);
            done("carry");
        }
        // A cat removed with a mouse in its jaws carries nothing after.
        auto removed(const std::shared_ptr<CarryRun>& r) -> void
        {
            UObject* actor = r->cat.actor();
            r->cat.carry(Carried::Mouse);
            r->cat.remove();
            after(0.5, [r, actor] {
                expect("carry.removed", !carrying(actor));
                finish(r);
            });
        }
        // A mesh without a `mouth` bone (the game's animals have none: the cat's own mesh swapped for a mouse's for a
        // moment) carries nothing; with its own back it does again.
        auto no_mouth(const std::shared_ptr<CarryRun>& r) -> void
        {
            UObject* mesh = get(r->cat.actor(), L"Mesh").object;
            auto own = call_reflected(mesh, STR("GetSkeletalMeshAsset"));
            UObject* cat_model = own ? own->get(L"ReturnValue").object : nullptr;
            auto set_model = [mesh](UObject* m) {
                call_reflected(mesh, STR("SetSkeletalMeshAsset"), [&](Params& p) { p.set_nth(0, Value::of(m)); });
            };
            set_model(load(carried_model(Carried::Mouse)));
            expect("carry.no_mouth", !r->cat.carry(Carried::Moss) && !r->cat.carrying());
            set_model(cat_model);
            expect("carry.mouth_again", r->cat.carry(Carried::Moss) && r->cat.carrying() == std::wstring(L"moss"));
            after(0.3, [r] { removed(r); });
        }
        // A carried thing taken out of its jaws by something else (detached) isn't counted as carried: nothing says
        // so, nothing drops it.
        auto detached(const std::shared_ptr<CarryRun>& r) -> void
        {
            UObject* c = r->cat.carry(Carried::Feathers);
            call_reflected(c, STR("K2_DetachFromComponent"), [&](Params& p) {
                for (int rule = 0; rule <= 2; ++rule) p.set_nth(rule, Value::of(1));   // KeepWorld
                p.set_nth(3, Value::of(false));
            });
            expect("carry.detached", c && !r->cat.carrying() && !r->cat.drop_carried() && detail::object_staying(c, nullptr));
            call_reflected(c, STR("K2_DestroyComponent"), [&](Params& p) { p.set_nth(0, Value::of(r->cat.actor())); });
            after(0.3, [r] { no_mouth(r); });
        }
        // Your cat carries moss.
        auto yours(const std::shared_ptr<CarryRun>& r) -> void
        {
            UObject* me = player();
            UObject* c = carry(me, Carried::Moss);
            value("carry.yours", c ? read(me, c, 1.0) : Json());
            auto now = carrying(me);
            value("carry.yours_name", Json(now ? text(*now) : std::string("?")));
            after(1.0, [r, me] {
                expect("carry.yours_dropped", drop_carried(me) && !carrying(me));
                detached(r);
            });
        }
        // The mouse moved in its jaws, then dropped.
        auto moved_and_dropped(const std::shared_ptr<CarryRun>& r) -> void
        {
            CarryPlace bigger = carried_place(Carried::Mouse);
            bigger.scale = 1.5;
            expect("carry.placed", place_carried(r->cat.actor(), bigger) && get(r->last, L"RelativeScale3D.X").number() == 1.5);
            expect("carry.placed_nothing", !place_carried(nullptr, bigger));
            const bool dropped = r->cat.drop_carried();
            value("carry.dropped", Json(dropped));
            value("carry.dropped_gone", Json(!detail::object_staying(r->last, nullptr)));
            value("carry.after_drop", Json(r->cat.carrying() ? text(*r->cat.carrying()) : std::string()));
            value("carry.drop_again", Json(r->cat.drop_carried()));
            after(0.5, [r] { yours(r); });
        }
        // It walks with the mouse: still in its jaws, the cat a way along.
        auto walks(const std::shared_ptr<CarryRun>& r) -> void
        {
            r->start = r->cat.location().value_or(Vec3{});
            r->cat.walk_to({r->start.x + 300, r->start.y, r->start.z});
            auto samples = std::make_shared<double>(0);
            for (int i = 1; i <= 5; ++i)
                after(0.3 * i, [r, samples] { *samples = std::max(*samples, distance(where(r->last), mouth_of(r->cat.actor())) / r->size); });
            after(1.8, [r, samples] {
                value("carry.walk_from_mouth", Json(*samples));
                value("carry.walked", Json(distance(r->cat.location().value_or(Vec3{}), r->start)));
                auto now = r->cat.carrying();
                value("carry.walk_carrying", Json(now ? text(*now) : std::string()));
                r->cat.stop();
                after(0.5, [r] { moved_and_dropped(r); });
            });
        }
        // It puts its head down to eat: the mouse goes down with its head, still in its jaws.
        auto eats(const std::shared_ptr<CarryRun>& r) -> void
        {
            r->last = r->cat.carry(Carried::Mouse);
            after(0.5, [r] {
                r->mouse_z = where(r->last).z;
                r->cat.play(Move::Eat);
                after(1.5, [r] {
                    value("carry.eat_lower", Json((r->mouse_z - where(r->last).z) / r->size));
                    value("carry.eat_from_mouth", Json(distance(where(r->last), mouth_of(r->cat.actor())) / r->size));
                    r->cat.stop_move(0.1);
                    after(0.8, [r] { walks(r); });
                });
            });
        }
        auto next_kind(const std::shared_ptr<CarryRun>& r) -> void
        {
            if (r->next >= std::size(KINDS))
            {
                after(0.3, [r] { eats(r); });
                return;
            }
            const Carried k = KINDS[r->next++];
            UObject* before = r->last;
            UObject* c = r->cat.carry(k);
            Json j = c ? read(r->cat.actor(), c, r->size) : Json::object();
            j.set("made", Json(c != nullptr));
            auto now = r->cat.carrying();
            j.set("name", Json(now ? text(*now) : std::string()));
            j.set("place_scale", Json(carried_place(k).scale));
            j.set("path", Json(text(carried_model(k))));
            // the one before is gone (destroyed: the engine marks it garbage at once)
            j.set("before_gone", Json(!before || !detail::object_staying(before, nullptr)));
            r->kinds.set(text(carried_name(k)), j);
            r->last = c;
            after(0.4, [r] { next_kind(r); });
        }
    } // namespace

    auto run_carry_request() -> void
    {
        phase("carry");
        // what isn't a cat carries nothing; a path that isn't a mesh, or isn't anything, makes nothing
        UObject* me = player();
        expect("carry.refused", !carry(nullptr, Carried::Mouse) && !carrying(nullptr) && !drop_carried(nullptr)
                                    && !carry_mesh(me, L"/Game/Nothing/Here.Here") && !carrying(me));
        expect("carry.not_a_mesh", !carry_mesh(me, move_sequences(Move::Yawn).front()) && !carrying(me));
        auto at = location(me);
        if (!at)
        {
            done("carry");
            return;
        }
        auto r = std::make_shared<CarryRun>();
        // in front of your cat, 2.5 m along its facing, turned side on
        auto rot = call_reflected(me, STR("K2_GetActorRotation"));
        const double yaw = rot ? get(rot->get(L"ReturnValue"), L"Yaw").number() : 0;
        const double rad = yaw * 3.14159265358979 / 180;
        r->cat = spawn_npc({.at = {at->x + std::cos(rad) * 250, at->y + std::sin(rad) * 250, at->z}, .yaw = yaw + 90, .size = r->size});
        expect("carry.spawned", r->cat.actor() != nullptr);
        if (!r->cat.actor()) return done("carry");
        after(1.5, [r] { next_kind(r); });
    }
} // namespace t
