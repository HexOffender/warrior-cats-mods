// Dens (Dens.hpp), on request ("dens"), for tests/game/test_cpp_sdk.py, which backs the save up first and puts it
// back after (decorations are written to the save). The decorations table; ShadowClan's dens; your cat taken into the
// apprentices' den; a decoration placed, one built over 4 s, one taken off; the save after save_game.
#include "checks.hpp"

#include <cmath>
#include <memory>
#include <set>
#include <string>

namespace t
{
    namespace
    {
        const wchar_t* BUNNY = L"Gameplay.Inventory.Decoration.12";    // Bunny Soft Down: Large
        const wchar_t* PEBBLE = L"Gameplay.Inventory.Decoration.31";   // Moon-Polished Pebble: Tiny
        const wchar_t* TALON = L"Gameplay.Inventory.Decoration.36";    // Badger Talon Relic: Tiny

        struct Spots
        {
            UObject* large{};   // Personal.1
            UObject* tiny{};    // Personal.2
            UObject* tiny2{};   // Personal.3
        };
        auto spot_json(UObject* h) -> Json
        {
            Json o = Json::object();
            if (auto s = hotspot(h))
            {
                o.set("tag", Json(text(s->tag)));
                o.set("size", Json(text(s->size)));
                o.set("decoration", Json(text(s->decoration)));
                o.set("saved_status", Json(s->saved_status));
                o.set("saved_decoration", Json(text(s->saved_decoration)));
                o.set("started", Json(static_cast<double>(s->started)));
            }
            return o;
        }
    } // namespace

    auto run_dens_request() -> void
    {
        phase("dens");
        // ----- the decorations
        auto decos = decorations();
        value("dens.decorations", static_cast<int>(decos.size()));
        auto deco_json = [](const Decoration& d) {
            Json o = Json::object();
            o.set("name", Json(text(d.name)));
            o.set("mesh", Json(text(d.mesh)));
            o.set("size", Json(text(d.size)));
            o.set("rarity", Json(text(d.rarity)));
            o.set("cost", Json(text(d.cost)));
            o.set("build_seconds", Json(d.build_seconds));
            o.set("max", Json(d.max));
            o.set("hidden", Json(d.hidden));
            return o;
        };
        int skeletal = 0, named = 0, sized = 0;
        std::set<std::wstring> models;
        for (auto& d : decos)
        {
            if (d.tag == BUNNY) value("dens.bunny", deco_json(d));
            if (d.tag == L"Gameplay.Inventory.Decoration.1") value("dens.hay", deco_json(d));
            skeletal += !d.skeletal.empty();
            named += !d.name.empty();
            sized += !d.size.empty();
            models.insert(d.mesh.empty() ? d.skeletal : d.mesh);
        }
        value("dens.skeletal", skeletal);
        value("dens.named", named);
        value("dens.sized", sized);
        value("dens.models", static_cast<int>(models.size()));   // each decoration its own model: read back by it
        // ----- ShadowClan's dens, and the apprentices'
        auto mine = dens(L"ShadowClan");
        value("dens.shadowclan", static_cast<int>(mine.size()));
        value("dens.all", static_cast<int>(dens().size()));
        Json ranks = Json::array();
        const Den* apprentice = nullptr;
        for (auto& d : mine)
        {
            ranks.push(Json(text(d.rank)));
            if (d.rank == L"Apprentice") apprentice = &d;
        }
        value("dens.ranks", ranks);
        // Every clan's rank dens: each one's hotspots are that rank's (dens() names a multi-rank door's own way in
        // the apprentices', seen on ShadowClan's).
        int rank_dens = 0, empty_rank_dens = 0, wrong_rank = 0;
        Json wrong = Json::array();
        for (auto& d : dens())
        {
            if (d.rank.empty()) continue;
            ++rank_dens;
            auto in = hotspots(&d);
            empty_rank_dens += in.empty();
            for (auto& s : in)
                if (s.rank != d.rank)
                {
                    ++wrong_rank;
                    auto at = location(s.actor);
                    wrong.push(Json(text(d.clan + L" " + d.rank + L" den: " + s.tag + L" " + s.size + L" " + s.rank + L" at "
                                         + (at ? std::to_wstring(std::lround(at->x)) + L"," + std::to_wstring(std::lround(at->y)) : L"")
                                         + L", den in at " + std::to_wstring(std::lround(d.inside.x)) + L","
                                         + std::to_wstring(std::lround(d.inside.y)))));
                }
        }
        value("dens.wrong_rank_spots", wrong);
        value("dens.rank_dens", rank_dens);
        value("dens.empty_rank_dens", empty_rank_dens);
        value("dens.wrong_rank", wrong_rank);
        if (!apprentice) return done("dens");
        auto spots = hotspots(apprentice);
        Json tags = Json::array();
        auto kept = std::make_shared<Spots>();
        for (auto& s : spots)
        {
            tags.push(Json(text(s.tag + L" " + s.size)));
            if (s.tag == L"Gameplay.Den.Hotspot.Personal.1") kept->large = s.actor;
            if (s.tag == L"Gameplay.Den.Hotspot.Personal.2") kept->tiny = s.actor;
            if (s.tag == L"Gameplay.Den.Hotspot.Personal.3") kept->tiny2 = s.actor;
        }
        value("dens.apprentice_hotspots", tags);
        value("dens.every_hotspot", static_cast<int>(hotspots().size()));
        if (!kept->large || !kept->tiny || !kept->tiny2) return done("dens");
        // ----- refused
        expect("dens.refused", !place_decoration(nullptr, BUNNY) && !place_decoration(kept->large, L"Gameplay.Inventory.Decoration.999")
                                   && !place_decoration(player(), BUNNY) && !build_decoration(kept->tiny, PEBBLE, 0)
                                   && !remove_decoration(nullptr) && !remove_decoration(player()) && !hotspot(player()));
        // ----- your cat in the den
        expect("dens.enter", enter_den(*apprentice));
        const Vec3 inside = apprentice->inside;
        after(2.0, [kept, inside] {
            auto at = location(player());
            value("dens.cat_from_inside", at ? Json(std::hypot(at->x - inside.x, at->y - inside.y)) : Json());
            value("dens.before.large", spot_json(kept->large));
            // ----- placed at once, timed over 4 s, and placed again
            expect("dens.place", place_decoration(kept->large, BUNNY));
            expect("dens.build", build_decoration(kept->tiny, PEBBLE, 4));
            expect("dens.place_tiny", place_decoration(kept->tiny2, TALON));
            after(1.0, [kept] {
                value("dens.placed.large", spot_json(kept->large));
                value("dens.building.tiny", spot_json(kept->tiny));
                after(5.0, [kept] {
                    value("dens.built.tiny", spot_json(kept->tiny));
                    // ----- taken off
                    expect("dens.remove", remove_decoration(kept->large));
                    after(1.0, [kept] {
                        value("dens.removed.large", spot_json(kept->large));
                        // ----- the save
                        expect("dens.save", save_game());
                        value("dens.saved.large", spot_json(kept->large));
                        value("dens.saved.tiny", spot_json(kept->tiny));
                        value("dens.saved.tiny2", spot_json(kept->tiny2));
                        done("dens");
                    });
                });
            });
        });
    }
} // namespace t
