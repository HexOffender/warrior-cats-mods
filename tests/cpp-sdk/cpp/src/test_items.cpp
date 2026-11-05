// Items.hpp and Animations.hpp, on request ("drop", "anims"), for tests/game/test_cpp_sdk.py. Items: what an item
// is from the game's tables; map_clear/map_add on a pickup's Reward; a game item and a mod's block (tests/items-mod,
// its own model) dropped beside your cat and collected with Interact, your cat moved 8 m off its spot first and put
// back; the inventory put back. Animations: the install's list (tests/animations-mod), a mod's played, seen playing
// and stopped; a game sequence by its path.
#include "checks.hpp"

#include <cmath>
#include <memory>
#include <string>

namespace t
{
    namespace
    {
        constexpr const wchar_t* MOSS = L"Gameplay.Inventory.Materials.Moss";
        constexpr const wchar_t* BLOCK = L"Gameplay.Inventory.Materials.WCModsTestBlock";   // tests/items-mod
        constexpr const char* MOSS8 = "Gameplay.Inventory.Materials.Moss";
        constexpr const char* BLOCK8 = "Gameplay.Inventory.Materials.WCModsTestBlock";

        auto info_json(const std::optional<ItemInfo>& i) -> Json
        {
            if (!i) return Json();
            Json o = Json::object();
            o.set("name", Json(text(i->name)));
            o.set("description", Json(text(i->description)));
            o.set("icon", Json(text(i->icon)));
            o.set("kind", Json(text(i->kind)));
            o.set("rarity", Json(text(i->rarity)));
            o.set("group", Json(text(i->group)));
            o.set("colour", Json(text(i->colour)));
            o.set("usable", Json(i->usable));
            o.set("effect", Json(text(i->effect)));
            o.set("use_type", Json(text(i->use_type)));
            o.set("target", Json(text(i->target)));
            o.set("in_fights", Json(i->in_fights));
            o.set("exploring", Json(i->exploring));
            o.set("fight_only", Json(i->fight_only));
            return o;
        }
        auto reward_json(UObject* pickup) -> Json
        {
            Json o = Json::object();
            for (auto& [k, v] : map_entries(pickup, L"Reward")) o.set(text(get(k, L"TagName").string()), Json(v.number()));
            return o;
        }
        // A pickup's look: its class, whether its own herb shows, and the skeletal mesh a mod's model added.
        auto pickup_json(UObject* pickup) -> Json
        {
            Json o = Json::object();
            if (!pickup) return Json();
            o.set("class", Json(text(class_name(pickup))));
            o.set("reward", reward_json(pickup));
            UObject* own = get(pickup, L"StaticMeshComponent").object;
            auto vis = own ? call_reflected(own, STR("IsVisible")) : std::nullopt;
            o.set("own_visible", vis ? Json(vis->get(L"ReturnValue").boolean()) : Json());
            UObject* cls = object(STR("/Script/Engine.SkeletalMeshComponent"));
            auto c = cls ? call_reflected(pickup, STR("GetComponentByClass"), [&](Params& p) { p.set_nth(0, Value::of(cls)); }) : std::nullopt;
            UObject* comp = c ? c->get(L"ReturnValue").object : nullptr;
            auto m = comp ? call_reflected(comp, STR("GetSkeletalMeshAsset")) : std::nullopt;
            UObject* mesh = m ? m->get(L"ReturnValue").object : nullptr;
            o.set("model", mesh ? Json(text(name(mesh))) : Json());
            o.set("hidden", Json(get(pickup, L"bHidden").boolean()));
            UObject* sphere = get(pickup, L"InteractionComponent").object;
            o.set("reach", sphere ? Json(get(sphere, L"SphereRadius").number()) : Json());
            auto me = location(player());
            auto it = location(pickup);
            if (me && it) o.set("distance", Json(std::sqrt((me->x - it->x) * (me->x - it->x) + (me->y - it->y) * (me->y - it->y))));
            if (auto at = location(pickup)) o.set("z", Json(at->z));
            return o;
        }
        auto count(const char* tag) -> double { return inventory_count(tag).value_or(0); }
        struct Kept
        {
            Vec3 home;
            double moss{}, block{};
            UObject* moss_pickup{};
            UObject* block_pickup{};
        };
    } // namespace

    auto run_items_request() -> void
    {
        phase("drop");
        // ----- what items are
        value("drop.moss", info_json(item_info(MOSS)));
        value("drop.herb", info_json(item_info(L"Gameplay.Inventory.Consumable.SmallHealingHerb")));
        value("drop.block", info_json(item_info(BLOCK)));
        expect("drop.unknown", !item_info(L"Gameplay.Inventory.Materials.NoSuchThing") && !item_info(L""));
        expect("drop.soft_path_refused", soft_path(get(player(), L"bHidden")).empty() && soft_path(Value{}).empty());
        value("drop.tags", static_cast<int>(item_tags().size()));
        // ----- refused drops
        expect("drop.drop_refused", !drop_item(MOSS, 0) && !drop_item(L"") && !drop_item(L"Gameplay.Combat.Character.Cat.Player"));

        // ----- your cat 8 m off its spot (it stands by a den's Travel prompt), then a game item dropped beside it
        auto home = location(player());
        if (!home)
        {
            done("drop");
            return;
        }
        auto k = std::make_shared<Kept>();
        k->home = *home;
        k->moss = count(MOSS8);
        k->block = count(BLOCK8);
        value("drop.moss_before", k->moss);
        Vec3 away{home->x - 800, home->y, home->z};
        if (auto g = ground(away.x, away.y, away.z + 200)) away.z = *g + 5;
        teleport(player(), away);
        after(1.0, [k] {
            k->moss_pickup = drop_item(MOSS, 2);   // in front of the cat
            value("drop.moss_pickup", pickup_json(k->moss_pickup));
            if (auto me = location(player())) value("drop.cat_z", me->z);
            // map_clear and map_add on the pickup's reward: cleared, two pairs, a key given a new value.
            Value reward = get(k->moss_pickup, L"Reward");
            UObject* p = k->moss_pickup;
            expect("drop.map_clear", map_clear(reward) && map_entries(p, L"Reward").empty());
            map_add(reward, [](const Value& key, const Value& n) {
                set(key, L"TagName", std::wstring_view(L"Gameplay.Inventory.Materials.Ivy"));
                set(n, L"", 1);
            });
            map_add(reward, [](const Value& key, const Value& n) {
                set(key, L"TagName", std::wstring_view(MOSS));
                set(n, L"", 5);
            });
            map_add(reward, [](const Value& key, const Value& n) {
                set(key, L"TagName", std::wstring_view(MOSS));
                set(n, L"", 2);
            });
            value("drop.map_after_adds", reward_json(p));
            map_clear(reward);
            map_add(reward, [](const Value& key, const Value& n) {
                set(key, L"TagName", std::wstring_view(MOSS));
                set(n, L"", 2);
            });
            expect("drop.map_not_a_map", !map_clear(get(p, L"bHidden")) && !map_add(get(p, L"bHidden"), [](const Value&, const Value&) {}));
            // Interact once the game has seen the cat in the pickup's reach (an overlap, a frame or more later).
            after(0.7, [] { command(L"Player_Interact"); });
            after(2.2, [k] {
                value("drop.moss_after", count(MOSS8));
                value("drop.moss_pickup_after", pickup_json(k->moss_pickup));
                // ----- a mod's block, lying as its own model
                k->block_pickup = drop_item(BLOCK, 1, location(player()));   // a spot given: under the cat
                value("drop.block_pickup", pickup_json(k->block_pickup));
                after(0.7, [] { command(L"Player_Interact"); });
                after(2.2, [k] {
                    value("drop.block_after", count(BLOCK8));
                    value("drop.block_pickup_after", pickup_json(k->block_pickup));
                    // ----- put back: the inventory, the cat
                    double moss = count(MOSS8) - k->moss, block = count(BLOCK8) - k->block;
                    if (moss > 0) remove_item(MOSS, static_cast<int>(moss));
                    if (block > 0) remove_item(BLOCK, static_cast<int>(block));
                    value("drop.moss_restored", count(MOSS8));
                    value("drop.block_restored", count(BLOCK8));
                    teleport(player(), k->home);
                    done("drop");
                });
            });
        });
    }

    auto run_anims_request() -> void
    {
        phase("anims");
        Json list = Json::object();
        for (auto& a : animations())
        {
            Json o = Json::object();
            o.set("kind", Json(text(a.kind)));
            o.set("path", Json(text(a.path)));
            o.set("loop", Json(a.loop));
            o.set("emote", Json(a.emote));
            o.set("key", Json(text(a.key)));
            list.set(text(a.id), o);
        }
        value("anims.list", list);
        UObject* me = player();
        value("anims.kind", text(animation_kind(me)));
        auto yawn = animation(L"animations-mod/Yawn");
        value("anims.one", yawn ? Json(text(yawn->name)) : Json());
        expect("anims.one_unknown", !animation(L"no-mod/Nothing"));
        expect("anims.unknown", !play_animation(me, L"no-mod/Nothing") && !play_animation(nullptr, L"animations-mod/Yawn"));
        value("anims.playing_before", text(animation_playing(me)));
        expect("anims.stop_nothing", !stop_animation(me));
        UObject* m = play_animation(me, L"animations-mod/Yawn");
        expect("anims.play", m != nullptr);
        after(0.5, [me] {
            value("anims.playing", text(animation_playing(me)));
            expect("anims.stop", stop_animation(me, 0.1));
            after(0.6, [me] {
                value("anims.playing_after_stop", text(animation_playing(me)));
                // A game sequence by its path, once.
                const wchar_t* meow = L"/Game/Art/Characters/CatMaster/Animations/A_CatMaster_Meow.A_CatMaster_Meow";
                expect("anims.play_game", play_animation(me, meow) != nullptr);
                after(0.3, [me, meow] {
                    value("anims.playing_game", text(animation_playing(me)));
                    stop_animation(me, 0.1);
                    done("anims");
                });
            });
        });
    }
} // namespace t
