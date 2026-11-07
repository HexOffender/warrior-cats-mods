// Looks.hpp: cats' looks and the clan's cats, on request ("looks"), for tests/game/test_cpp_sdk.py. The struct's
// defaults against the game's; the save's text read; your cat's look changed (fur colour, tail) and the model read
// back (its material's Fur Color, the tail's mesh), then put back; an accessory worn and taken off; a spawned cat's
// look changed; the game saved with a changed look and its JSON read; the clan's cats from the save with their
// actors; a cat's role.
#include "checks.hpp"

#include <fstream>
#include <memory>
#include <sstream>
#include <string>

namespace t
{
    namespace
    {
        auto look_json(const Look& l) -> Json
        {
            Json o = Json::object();
            for (const detail::LookField& f : detail::look_struct_fields())
                std::visit(
                    [&](auto m) {
                        using T = std::remove_cvref_t<decltype(l.*m)>;
                        if constexpr (std::is_same_v<T, std::wstring>) o.set(text(std::wstring_view(f.name)), Json(text(l.*m)));
                        else if constexpr (std::is_same_v<T, bool>) o.set(text(std::wstring_view(f.name)), Json(l.*m));
                        else o.set(text(std::wstring_view(f.name)), Json(static_cast<double>(l.*m)));
                    },
                    f.member);
            return o;
        }
        auto mesh_name(UObject* comp) -> Json
        {
            auto r = comp ? call_reflected(comp, STR("GetSkeletalMeshAsset")) : std::nullopt;
            UObject* m = r ? r->get(L"ReturnValue").object : nullptr;
            return m ? Json(text(name(m))) : Json();
        }
        // A look component's model now: the body's first material's Fur Color, and each part's mesh.
        auto model(UObject* cat) -> Json
        {
            Json o = Json::object();
            UObject* c = detail::look_component(cat);
            if (!c) return Json();
            UObject* body = get(c, L"SkelMeshComp").object;
            auto mat = body ? call_reflected(body, STR("GetMaterial"), [&](Params& p) { p.set_nth(0, Value::of(0)); }) : std::nullopt;
            UObject* m = mat ? mat->get(L"ReturnValue").object : nullptr;
            auto fur = m ? call_reflected(m, STR("K2_GetVectorParameterValue"), [&](Params& p) { p.set_nth(0, Value::of(std::wstring_view(L"Fur Color"))); })
                         : std::nullopt;
            if (fur)
            {
                Value v = fur->get(L"ReturnValue");
                o.set("fur", Json(text(std::format(L"{:.3f},{:.3f},{:.3f}", get(v, L"R").number(), get(v, L"G").number(), get(v, L"B").number()))));
            }
            // The game's colour for the look's coat slot (the GUI manager's FurColors), as "r,g,b" bytes.
            int slot = static_cast<int>(get(c, L"CustomData.FurColorIdx").number());
            auto colours = elements(manager(STR("gui")), L"FurColors");
            if (slot >= 0 && slot < static_cast<int>(colours.size()))
            {
                Value f = colours[slot];
                o.set("fur_slot", Json(text(std::format(L"{},{},{}", get(f, L"R").number(), get(f, L"G").number(), get(f, L"B").number()))));
            }
            o.set("tail", mesh_name(get(c, L"TailSkelMeshComp").object));
            o.set("ears", mesh_name(get(c, L"EarSkelMeshComp").object));
            o.set("fur_mesh", mesh_name(get(c, L"FurSkelMeshComp").object));
            UObject* neck = get(c, L"AccSkelNeckComp").object;
            o.set("neck", mesh_name(neck));
            auto hidden = neck ? call_reflected(neck, STR("IsVisible")) : std::nullopt;
            o.set("neck_visible", hidden ? Json(hidden->get(L"ReturnValue").boolean()) : Json());
            return o;
        }
        auto saved_customization() -> Json
        {
            std::ifstream f(save_path(), std::ios::binary);
            std::stringstream ss;
            ss << f.rdbuf();
            auto doc = Json::parse(ss.str());
            if (!doc) return Json();
            return detail::slot_of(*doc)["GameplayProgression"]["Gameplay.Combat.Character.Cat.Player"]["Customization"];
        }
        struct Kept
        {
            Look before;
            Npc npc;
        };
    } // namespace

    auto run_looks_request() -> void
    {
        phase("looks");
        UObject* me = player();
        // ----- the game's tables for making cats (CatTables.hpp), and the colour slots
        {
            const CatTables& t = cat_tables();
            Json v = Json::object();
            v.set("prefixes", Json(static_cast<int>(t.prefixes.size())));
            v.set("suffixes", Json(static_cast<int>(t.suffixes.size())));
            if (!t.prefixes.empty())
            {
                v.set("first_prefix", Json(text(t.prefixes[0].word) + " " + text(t.prefixes[0].id)));
                auto w = t.prefixes[0].weights.find(L"ThunderClan");
                v.set("first_prefix_thunderclan", Json(w == t.prefixes[0].weights.end() ? -1.0 : w->second));
            }
            for (const CatNamePart& s : t.suffixes)
                if (s.word == L"paw") v.set("paw_apprentice", Json(s.weights.count(L"Apprentice") ? s.weights.at(L"Apprentice") : -1.0));
            v.set("banned", Json(static_cast<int>(t.banned.size())));
            v.set("rogues", Json(static_cast<int>(t.rogues.size())));
            v.set("parts", Json(static_cast<int>(t.looks.size())));
            auto coat = t.looks.find(L"coat");
            v.set("windclan_coats", Json(coat != t.looks.end() && coat->second.count(L"WindClan") ? static_cast<int>(coat->second.at(L"WindClan").size()) : -1));
            v.set("banned_patterns", Json(static_cast<int>(t.banned_patterns.size())));
            Json kit_body = Json::array();
            if (t.kit_parts.count(L"body"))
                for (int b : t.kit_parts.at(L"body")) kit_body.push(Json(b));
            v.set("kit_body", kit_body);
            v.set("kit_size", Json(t.sizes.count(L"Kit") ? t.sizes.at(L"Kit").second : -1.0));
            int warriors = -1;
            if (t.generators.count(L"ThunderClan") && t.generators.at(L"ThunderClan").count(L"Warrior"))
                warriors = t.generators.at(L"ThunderClan").at(L"Warrior").count(L"ThunderClan") ? t.generators.at(L"ThunderClan").at(L"Warrior").at(L"ThunderClan") : -1;
            v.set("thunderclan_warriors", Json(warriors));
            v.set("scars", Json(static_cast<int>(t.scars.size())));
            v.set("odd_eyes", Json(t.odd_eyes));
            v.set("missing", Json(static_cast<int>(t.missing.size())));
            value("looks.cat_tables", v);
            ColourSlots slots = colour_slots();
            Json c = Json::object();
            auto rgb = [](const std::vector<SlotColour>& all) {
                Json a = Json::array();
                for (const SlotColour& x : all)
                {
                    Json one = Json::array();
                    one.push(Json(x.r));
                    one.push(Json(x.g));
                    one.push(Json(x.b));
                    a.push(one);
                }
                return a;
            };
            c.set("coats", rgb(slots.coats));
            c.set("patterns", Json(static_cast<int>(slots.patterns.size())));
            c.set("markings", Json(static_cast<int>(slots.markings.size())));
            c.set("eyes", Json(static_cast<int>(slots.eyes.size())));
            value("looks.colour_slots", c);
        }
        // ----- the struct's defaults are the game's (a quest actor's class default holds an untouched one)
        UObject* cdo = object(STR("/Script/SwtAdventure.Default__SwtAdventureQuestActor"));
        Look game_default = cdo ? detail::read_look(get(cdo, L"DefaultCustomData")) : Look{};
        expect("looks.defaults", cdo && game_default == Look{}, look_json(game_default).dump(0));

        // ----- the save's text: nested, quoted and escaped values, and fields left out at their defaults
        Look parsed = look_from_text(L"(ClanType=RiverClan,Role=Warrior,CombatStats=(TagName=\"Gameplay.A.B\"),TailIdx=3,"
                                     L"bOverrideColors=True,PrefixNameId=\"STR_X\\\"Y\",SuffixNameId=\"\",CatSize=0.930000,ScarEarId=6)");
        Look want;
        want.ClanType = L"RiverClan";
        want.Role = L"Warrior";
        want.CombatStats = L"Gameplay.A.B";
        want.TailIdx = 3;
        want.bOverrideColors = true;
        want.PrefixNameId = L"STR_X\"Y";
        want.SuffixNameId = L"";
        want.CatSize = 0.93f;
        want.ScarEarId = 6;
        expect("looks.from_text", parsed == want, look_json(parsed).dump(0));
        expect("looks.from_text_empty", look_from_text(L"") == Look{} && look_from_text(L"()") == Look{}
                                            && look_from_text(L"(CombatStats=(),TailIdx=2)").CombatStats == L"None");
        // A nested value whose text ends in an escaped backslash leaves the fields after it whole.
        Look nested = look_from_text(L"(CombatStats=(TagName=\"A\\\\\"),TailIdx=3,EarIdx=4)");
        expect("looks.from_text_nested_escape", nested.CombatStats == L"A\\" && nested.TailIdx == 3 && nested.EarIdx == 4,
               text(nested.CombatStats));

        // ----- your cat's look, and its role
        auto mine = look(me);
        expect("looks.read", mine.has_value());
        if (!mine)
        {
            done("looks");
            return;
        }
        value("looks.player", look_json(*mine));
        value("looks.saved_text", saved_customization());
        value("looks.model_before", model(me));
        auto r = role_of(me);
        value("looks.role", r ? Json(text(r->clan + L"/" + r->role + L"/" + r->story_role)) : Json());
        expect("looks.no_cat", !look(nullptr) && !set_look(nullptr, *mine) && !role_of(nullptr));

        // ----- changed: the fur colour slot and the tail, and the model follows
        auto k = std::make_shared<Kept>();
        k->before = *mine;
        Look changed = *mine;
        changed.FurColorIdx = (mine->FurColorIdx + 5) % 19;
        changed.TailIdx = (mine->TailIdx + 3) % 9;
        expect("looks.set", set_look(me, changed));
        value("looks.after", look_json(look(me).value_or(Look{})));
        value("looks.model_after", model(me));
        Look bad = changed;
        bad.ClanType = L"NoSuchClan";
        expect("looks.bad_enum", !set_look(me, bad) && look(me) == std::optional<Look>(changed) /* nothing changed */ && !keep_look(bad));
        // Kept in the save too (the game's SaveCatCustomData): the file as it is right after, then after a save.
        expect("looks.keep", keep_look(changed));
        value("looks.saved_after_keep", saved_customization());

        // ----- accessories
        auto all = accessories();
        value("looks.accessories", static_cast<int>(all.size()));
        Json collar;
        for (auto& a : all)
            if (a.id == L"DogCollar") collar = Json(text(a.slot + L"/" + std::to_wstring(a.variations)));
        value("looks.dog_collar", collar);
        expect("looks.wear_refused", !wear(me, L"NoSuchThing") && !wear(me, L"DogCollar", 0) && !wear(me, L"DogCollar", 99) && !take_off(me, L"Tail"));
        expect("looks.wear", wear(me, L"DogCollar", 2));
        value("looks.worn", look_json(look(me).value_or(Look{})));
        value("looks.model_worn", model(me));

        // ----- the save: the game saved with the changed look, its JSON read
        save_game(L"WCMods looks test");
        after(2.0, [k, me] {
            value("looks.saved_changed", saved_customization());
            expect("looks.take_off", take_off(me, L"Neck"));
            value("looks.model_taken_off", model(me));
            // ----- put back
            expect("looks.restore", set_look(me, k->before) && keep_look(k->before));
            value("looks.restored", look_json(look(me).value_or(Look{})));
            value("looks.model_restored", model(me));
            save_game(L"WCMods looks test");
            after(2.0, [k] {
                value("looks.saved_restored", saved_customization());
                // ----- a cat spawned by the mod: its look changed the same way
                NpcSpec spec;
                auto at = location(player());
                spec.at = {at->x + 200, at->y, at->z};
                k->npc = spawn_npc(spec);
                after(1.0, [k] {
                    UObject* a = k->npc.actor();
                    auto l = look(a);
                    value("looks.npc_model_before", model(a));
                    value("looks.npc_before", l ? look_json(*l) : Json());
                    if (l)
                    {
                        l->FurColorIdx = (l->FurColorIdx + 7) % 19;
                        l->EarIdx = (l->EarIdx + 4) % 9;
                        expect("looks.npc_set", set_look(a, *l));
                        value("looks.npc_model_after", model(a));
                        value("looks.npc_after", look_json(look(a).value_or(Look{})));
                        // Given a save cat's clan, role and name ids, the mod's cat still isn't taken for it.
                        for (auto& c : clan_cats())
                            if (c.index >= 0 && c.look.ClanType != L"None")
                            {
                                Look same = *look(a);
                                same.ClanType = c.look.ClanType;
                                same.Role = c.look.Role;
                                same.PrefixNameId = c.look.PrefixNameId;
                                same.SuffixNameId = c.look.SuffixNameId;
                                set_look(a, same);
                                bool taken = false;
                                for (auto& again : clan_cats())
                                    if (again.actor == a) taken = true;
                                expect("looks.mod_cat_not_a_save_cat", !taken, text(c.name));
                                break;
                            }
                    }
                    k->npc.remove();
                    // ----- the clan's cats, from the save
                    Json cats = Json::array();
                    int out_now = 0;
                    for (auto& c : clan_cats())
                    {
                        Json one = Json::object();
                        one.set("clan", Json(text(c.clan)));
                        one.set("role", Json(text(c.role)));
                        one.set("index", Json(c.index));
                        one.set("name", Json(text(c.name)));
                        one.set("prefix", Json(text(c.look.PrefixNameId)));
                        Json story = Json::array();
                        for (auto& s : c.story_roles) story.push(Json(text(s)));
                        one.set("story", story);
                        one.set("actor", Json(c.actor != nullptr));
                        if (c.actor)
                        {
                            ++out_now;
                            auto cr = role_of(c.actor);
                            one.set("actor_role", cr ? Json(text(cr->clan + L"/" + cr->role + L"/" + cr->story_role)) : Json());
                        }
                        cats.push(one);
                    }
                    value("looks.clan_cats", cats);
                    value("looks.clan_cats_out", out_now);
                    done("looks");
                });
            });
        });
    }
} // namespace t
