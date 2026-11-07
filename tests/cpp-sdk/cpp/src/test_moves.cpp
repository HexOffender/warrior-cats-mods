// CatMoves.hpp: cats' poses and the game's moves, on request ("moves"), for tests/game/test_cpp_sdk.py. A cat of the
// mod's own is put in front of your cat; each pose is set and measured a moment later by its bones (the head, the hips,
// a front paw, over its root, scaled to a size-1 cat), then each move is played and what plays read back: the montage,
// and for a two-part move (lying down to sleep) the loop it goes on into. Last, a walk stands it up.
#include "checks.hpp"

#include <algorithm>
#include <cmath>
#include <memory>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        struct MovesRun
        {
            Npc cat;
            Vec3 home{};
            size_t next{};
            double size{0.8};
        };
        // A bone's height over the mesh's root, as on a size-1 cat.
        auto bone_height(UObject* actor, const wchar_t* bone, double size) -> double
        {
            UObject* mesh = get(actor, L"Mesh").object;
            if (!mesh) return -1000;
            auto at = [&](const wchar_t* b) -> double {
                auto r = call_reflected(mesh, STR("GetSocketLocation"), [&](Params& p) { p.set_nth(0, Value::of(std::wstring_view(b))); });
                return r ? get(r->get(L"ReturnValue"), L"Z").number() : 0;
            };
            return (at(bone) - at(L"Root")) / size;
        }
        auto measure(UObject* actor, double size) -> Json
        {
            Json j = Json::object();
            j.set("head", Json(bone_height(actor, L"Head", size)));
            j.set("hips", Json(bone_height(actor, L"butt", size)));
            j.set("paw", Json(bone_height(actor, L"paw_f_L", size)));
            return j;
        }
        constexpr Pose POSES[] = {Pose::Stand, Pose::Sit, Pose::SitLeft, Pose::Sleep, Pose::Fidget, Pose::Playful,
                                  Pose::Rear, Pose::Spar, Pose::Strike, Pose::Still};
        constexpr Move MOVES[] = {Move::Meow, Move::Sniff, Move::Dig, Move::Sharpen, Move::Play, Move::Yawn, Move::Stretch,
                                  Move::Shake, Move::Alert, Move::Angry, Move::Bow, Move::Eat, Move::Drink, Move::Stalk,
                                  Move::Crouch, Move::Pounce, Move::WalkBack, Move::Tired, Move::Cheer, Move::Surprised, Move::Wake};

        auto finish(const std::shared_ptr<MovesRun>& r) -> void
        {
            r->cat.remove();
            done("moves");
        }
        auto walk_stands_it(const std::shared_ptr<MovesRun>& r) -> void
        {
            r->cat.pose(Pose::Sit);
            r->cat.play(Move::Eat);
            after(1.0, [r] {
                auto at = r->cat.location();
                if (at) r->cat.walk_to({at->x + 150, at->y, at->z});
                after(0.3, [r] {
                    auto p = pose_of(r->cat.actor());
                    value("moves.after_walk", Json(p ? text(pose_name(*p)) : std::string("?")));
                    value("moves.after_walk_plays", Json(text(animation_playing(r->cat.actor()))));
                    value("moves.walking_moves", Json(walking_move(Move::Stalk) && !walking_move(Move::Sleep)));
                    r->cat.stop();
                    finish(r);
                });
            });
        }
        auto sleep_goes_on(const std::shared_ptr<MovesRun>& r) -> void
        {
            UObject* lead = r->cat.play(Move::Sleep);
            value("moves.sleep.lead", Json(lead != nullptr));
            value("moves.sleep.lead_plays", Json(text(animation_playing(r->cat.actor()))));
            after(4.0, [r] {
                value("moves.sleep.loop_plays", Json(text(animation_playing(r->cat.actor()))));
                value("moves.sleep.sequences", Json(static_cast<int>(move_sequences(Move::Sleep).size())));
                r->cat.stop_move();
                after(0.6, [r] {
                    value("moves.sleep.stopped", Json(text(animation_playing(r->cat.actor()))));
                    walk_stands_it(r);
                });
            });
        }
        auto next_move(const std::shared_ptr<MovesRun>& r) -> void
        {
            if (r->next >= std::size(MOVES))
            {
                r->cat.stop_move(0.1);
                after(0.5, [r] { sleep_goes_on(r); });
                return;
            }
            const Move m = MOVES[r->next++];
            UObject* montage = r->cat.play(m);
            after(0.4, [r, m, montage] {
                Json j = Json::object();
                j.set("montage", Json(montage != nullptr));
                j.set("plays", Json(montage_playing(r->cat.actor())));
                j.set("sequence", Json(text(animation_playing(r->cat.actor()))));
                value(std::string("moves.move.") + text(move_name(m)), j);
                r->cat.stop_move(0.1);
                after(0.3, [r] { next_move(r); });
            });
        }
        auto next_pose(const std::shared_ptr<MovesRun>& r) -> void
        {
            if (r->next >= std::size(POSES))
            {
                r->cat.pose(Pose::Stand);
                r->next = 0;
                after(1.0, [r] { next_move(r); });
                return;
            }
            const Pose p = POSES[r->next++];
            const bool set_ok = r->cat.pose(p);
            // some poses move (rearing up scratches, a sleeper breathes): sampled six times over 2 s, each bone's
            // lowest and highest kept
            auto samples = std::make_shared<std::vector<Json>>();
            for (int i = 0; i < 6; ++i)
                after(1.2 + 0.35 * i, [r, samples] { samples->push_back(measure(r->cat.actor(), r->size)); });
            after(1.2 + 0.35 * 6, [r, p, set_ok, samples] {
                Json j = Json::object();
                for (const char* bone : {"head", "hips", "paw"})
                {
                    double lo = 1e9, hi = -1e9;
                    for (const Json& s : *samples)
                    {
                        lo = std::min(lo, s[bone].number());
                        hi = std::max(hi, s[bone].number());
                    }
                    j.set(std::string(bone) + "_min", Json(lo));
                    j.set(std::string(bone) + "_max", Json(hi));
                }
                j.set("set", Json(set_ok));
                auto now = pose_of(r->cat.actor());
                j.set("reads", Json(now ? text(pose_name(*now)) : std::string("?")));
                value(std::string("moves.pose.") + text(pose_name(p)), j);
                r->cat.pose(Pose::Stand);
                after(1.0, [r] { next_pose(r); });
            });
        }
    } // namespace

    auto run_moves_request() -> void
    {
        phase("moves");
        auto r = std::make_shared<MovesRun>();
        auto me = location(player());
        if (!me)
        {
            done("moves");
            return;
        }
        r->home = *me;
        // in front of your cat, 2.5 m along its facing
        auto rot = call_reflected(player(), STR("K2_GetActorRotation"));
        const double yaw = rot ? get(rot->get(L"ReturnValue"), L"Yaw").number() * 3.14159265358979 / 180 : 0;
        Vec3 at{me->x + std::cos(yaw) * 250, me->y + std::sin(yaw) * 250, me->z};
        r->cat = spawn_npc({.at = at, .yaw = yaw * 180 / 3.14159265358979 + 180, .size = r->size});
        expect("moves.spawned", r->cat.actor() != nullptr);
        if (!r->cat.actor()) return done("moves");
        // what isn't a cat has no poses
        expect("moves.not_a_cat", !set_pose(nullptr, Pose::Sit) && !play_move(nullptr, Move::Meow) && !pose_of(nullptr));
        after(1.5, [r] { next_pose(r); });
    }
} // namespace t
