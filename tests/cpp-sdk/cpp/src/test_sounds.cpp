// Sounds and music (World.hpp), on request ("sounds"), for tests/game/test_cpp_sdk.py: an id's sound replaced and
// heard from the game's own play while the cat walks, muted, put back; the music read, changed and stopped; the
// volumes and the pause.
#include "checks.hpp"

#include <functional>
#include <memory>
#include <set>
#include <string>
#include <vector>

namespace t
{
    namespace
    {
        // The sounds playing now, by name.
        auto playing_sounds() -> std::set<std::wstring>
        {
            std::set<std::wstring> out;
            for (UObject* c : find_all(STR("AudioComponent")))
            {
                auto r = call_reflected(c, STR("IsPlaying"));
                if (!r || !r->get(L"ReturnValue").boolean()) continue;
                if (UObject* s = get(c, L"Sound").object) out.insert(name(s));
            }
            return out;
        }
        auto name_json(UObject* o) -> Json { return o ? Json(text(name(o))) : Json(); }
    } // namespace

    auto run_sounds_request() -> void
    {
        phase("sounds");
        value("sounds.step_before", name_json(sound_of(L"cat_step")));
        expect("sounds.missing", !sound_of(L"no_such_sound") && !replace_sound(L"no_such_sound", L"ui_select")
                                     && !replace_sound(L"cat_step", L"no_such_sound") && !restore_sound(L"cat_step")
                                     && !sound_duration(L"no_such_sound") && !stop_sound(nullptr));
        auto d = sound_duration(L"ui_select");
        value("sounds.ui_select_duration", d ? Json(*d) : Json());
        UObject* one = play_sound(L"ui_select");
        expect("sounds.stop", one && stop_sound(one));

        // The cat's steps as the menu's select sound: what plays while the Python side walks the cat (4 s).
        expect("sounds.replace", replace_sound(L"cat_step", L"ui_select") && name(sound_of(L"cat_step")) == L"S_Cue_ui_select");
        auto heard = std::make_shared<std::set<std::wstring>>();
        auto ticks = std::make_shared<int>(0);
        auto sample = std::make_shared<std::function<void()>>();
        *sample = [heard, ticks, sample] {
            for (auto& s : playing_sounds()) heard->insert(s);
            if (++*ticks < 20)
            {
                after(0.2, [sample] { (*sample)(); });
                return;
            }
            Json list = Json::array();
            for (auto& s : *heard)
                if (s.find(L"cat_step") != std::wstring::npos || s.find(L"ui_select") != std::wstring::npos) list.push(text(s));
            value("sounds.heard_walking", list);
            expect("sounds.restore", restore_sound(L"cat_step") && name(sound_of(L"cat_step")) == L"S_Cue_cat_step" && !restore_sound(L"cat_step"));
            UObject* select = sound_of(L"ui_select");
            double volume = get(select, L"VolumeMultiplier").number();
            expect("sounds.mute", mute_sound(L"ui_select") && sound_of(L"ui_select") == select && get(select, L"VolumeMultiplier").number() == 0
                                      && restore_sound(L"ui_select") && get(select, L"VolumeMultiplier").number() == volume && !restore_sound(L"ui_select"));
            value("sounds.select_volume", volume);

            // The music: what plays, another track, stopped, and the game's track again.
            Music m = music();
            value("sounds.music_sound", text(m.sound));
            value("sounds.music_id", text(m.id));
            expect("sounds.play_music", play_music(L"mus_camp"));
            after(1.0, [m] {
                Music now = music();
                value("sounds.music_after_play", text(now.sound));
                expect("sounds.stop_music", stop_music(0));
                after(0.5, [m] {
                    value("sounds.music_after_stop", music().component ? Json(text(music().sound)) : Json());
                    if (!m.id.empty()) play_music(m.id);
                    // Volumes and the pause.
                    expect("sounds.volume", set_volume(Volume::Music, 0.5) && set_volume(Volume::Music, 1.0));
                    expect("sounds.pause", pause_sounds(true) && sounds_paused() && pause_sounds(false) && !sounds_paused());
                    done("sounds");
                });
            });
        };
        after(0.2, [sample] { (*sample)(); });
    }
} // namespace t
