// Npcs.hpp: a cat of the mod's own, on request ("npcs"), for tests/game/test_cpp_sdk.py. Your cat is moved 8 m
// from the den entrance it stands by (whose Travel prompt would take the Interact), and put back after.
#include "checks.hpp"

#include <cmath>
#include <memory>
#include <string>

namespace t
{
    namespace
    {
        std::atomic<int> interacts{};
        Npc interacted;
        bool listening{};

        auto widget_text(UObject* o, const wchar_t* path) -> Json
        {
            Value v = get(o, path);
            return v.object ? Json(text(Widget(v.object).text())) : Json();
        }
    } // namespace

    auto run_npcs_request() -> void
    {
        phase("npcs");
        auto home = location(player());
        if (!home)
        {
            done("npcs");
            return;
        }
        Vec3 away{home->x - 800, home->y, home->z};
        if (auto g = ground(away.x, away.y, away.z + 200)) away.z = *g + 5;
        value("npcs.moved", teleport(player(), away));
        if (!listening)
        {
            on_npc_interact([](Npc n) {
                interacts++;
                interacted = n;
            });
            listening = true;
        }
        after(1.0, [home] {
            auto spot = npc_spot(200, -60);
            value("npcs.spot", spot ? Json(true) : Json(false));
            if (!spot)
            {
                done("npcs");
                return;
            }
            NpcSpec spec;
            spec.at = *spot;
            spec.yaw = 90;
            spec.size = 1.0;
            spec.look = {{L"body", 3}, {L"tail", 2}};
            spec.slots = {{L"fur", 4}};
            spec.colours = {{L"fur", L"#ff8800"}};
            spec.prefix = L"STR_CAT_NAME2";
            spec.suffix = L"_PAW";
            auto npc = std::make_shared<Npc>(spawn_npc(spec));
            expect("npcs.spawned", npc->actor() != nullptr && npc->spawns() == 1 && npcs().size() >= 1);
            value("npcs.class", npc->actor() ? Json(text(class_name(npc->actor()))) : Json());
            value("npcs.distance", npc->distance() ? Json(*npc->distance()) : Json());
            UObject* custom = get(npc->actor(), L"MeshCustomizationComponent").object;
            value("npcs.body", get(custom, L"CustomData.BodyValue").number());
            value("npcs.tail", get(custom, L"CustomData.TailIdx").number());
            value("npcs.fur_slot", get(custom, L"CustomData.FurColorIdx").number());
            value("npcs.override", get(custom, L"CustomData.bOverrideColors").boolean());
            value("npcs.name_ids", Json(text(get(custom, L"CustomData.PrefixNameId").string() + L" " + get(custom, L"CustomData.SuffixNameId").string())));
            // Its class by its path (load), the Interact command by its name (enum_value), how near it is, turning.
            expect("npcs.load", load(detail::NPC_CLASS) == npc->actor()->GetClassPrivate() && !load(L"/Game/Nope/Nope.Nope") && !load(L""));
            expect("npcs.enum_value", enum_value(STR("/Script/SwtEngine.ECommands"), L"Player_Interact").value_or(-1) > 0
                                          && !enum_value(STR("/Script/SwtEngine.ECommands"), L"NoSuchCommand"));
            expect("npcs.within", npc->within(300) && !npc->within(50));
            expect("npcs.face", npc->face(*location(player())));
            npc->set_label({.name = L"Brindlemoon", .title = L"Elder", .icon = L"available"});
            npc->set_prompt(L"Talk");
            after(1.0, [npc, home] {
                // The label (filled by the keeper) and the prompt (each frame), and the fur colour on its body.
                auto st = npc->state();
                UObject* label = st->label_widget.object();
                value("npcs.label_name", label ? widget_text(label, L"mcGuiActorName.mcGuiTextName") : Json());
                value("npcs.label_title", label ? widget_text(label, L"mcGuiActorName.mcGuiTextRole") : Json());
                value("npcs.label_opacity", label ? Json(Widget(get(label, L"mcGuiActorName").object).opacity()) : Json());
                auto& s = detail::npcs_state();
                value("npcs.prompt_on", s.prompt_on == st);
                value("npcs.prompt_shown", s.prompt && s.prompt.visibility() == Visibility::SelfHitTestInvisible);
                value("npcs.prompt_text", s.prompt ? Json(text(s.prompt.find(L"mcGuiTextAction").text())) : Json());
                Widget menu = ui::hud().find(L"mcGuiContextualMenu");
                value("npcs.game_prompt_up", menu && menu.visibility() != Visibility::Collapsed && menu.visibility() != Visibility::Hidden);
                UObject* mesh = get(npc->actor(), L"Mesh").object;
                auto mat = call_reflected(mesh, STR("GetMaterial"), [&](Params& p) { p.set_nth(0, Value::of(0)); });
                UObject* m = mat ? mat->get(L"ReturnValue").object : nullptr;
                auto fur = m ? call_reflected(m, STR("K2_GetVectorParameterValue"), [&](Params& p) { p.set_nth(0, Value::of(std::wstring_view(L"Fur Color"))); })
                             : std::nullopt;
                value("npcs.fur_r", fur ? Json(get(fur->get(L"ReturnValue"), L"R").number()) : Json());
                value("npcs.fur_b", fur ? Json(get(fur->get(L"ReturnValue"), L"B").number()) : Json());
                // The game's Interact, given as its controls do, while the cat's prompt shows.
                bool sent = s.prompt_on == st && command(L"Player_Interact");
                value("npcs.interact_sent", sent);
                after(0.5, [npc, home] {
                    value("npcs.interacts", interacts.load());
                    value("npcs.interacted_is_it", interacted == *npc);
                    // Moved half a metre at once, then a walk of 5 m.
                    auto here = npc->location();
                    expect("npcs.move_to", npc->move_to({here->x, here->y + 50, here->z}) && std::abs(npc->location()->y - (here->y + 50)) < 5);
                    auto from = npc->location();
                    Vec3 to{from->x + 500, from->y, from->z};
                    if (auto g = ground(to.x, to.y, to.z + 200)) to.z = *g;
                    auto result = std::make_shared<WalkResult>(WalkResult::None);
                    value("npcs.walk_started", npc->walk_to(to, {}, [result](WalkResult r) { *result = r; }));
                    after(8.0, [npc, home, from, result] {
                        auto now = npc->location();
                        value("npcs.walked", now ? Json(std::hypot(now->x - from->x, now->y - from->y)) : Json());
                        value("npcs.walk_result", static_cast<int>(*result));
                        value("npcs.walking_after", npc->walking());
                        value("npcs.walk_result_after", static_cast<int>(npc->walk_result()));
                        npc->stop();
                        UObject* was = npc->actor();
                        npc->remove();
                        after(0.5, [was, home] {
                            value("npcs.removed_gone", !detail::object_alive(was, nullptr) || !detail::object_staying(was, nullptr));
                            value("npcs.left", static_cast<double>(npcs().size()));
                            teleport(player(), *home);
                            done("npcs");
                        });
                    });
                });
            });
        });
    }
} // namespace t
