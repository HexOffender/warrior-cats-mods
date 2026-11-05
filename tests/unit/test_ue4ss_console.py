"""UE4SS's console enabler, with its self-unhook taken out (wcmods.ue4ss.fix_console_mod): unhooking ClientRestart from
inside its own callback crashed the game in UE4SS at the next ClientRestart (a fight's start)."""
import os

from wcmods import ue4ss

SCRIPT = '''Pre, Post = RegisterHook("/Script/Engine.PlayerController:ClientRestart",
function(Context)
    if (not WasConsoleCreated or IsDynamicViewport) then
        CreateConsole()
    end
    if (WasConsoleCreated and not IsDynamicViewport) then
        UnregisterHook("/Script/Engine.PlayerController:ClientRestart", Pre, Post)
    end
end)
'''


def _mod(tmp_path, text):
    scripts = tmp_path / "ConsoleEnablerMod" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "main.lua").write_text(text, encoding="utf-8")
    return scripts / "main.lua"


def test_the_self_unhook_comes_out_and_the_rest_stays(tmp_path):
    script = _mod(tmp_path, SCRIPT)
    assert ue4ss.fix_console_mod(str(tmp_path)) is True
    text = script.read_text(encoding="utf-8")
    assert ue4ss.CONSOLE_UNHOOK not in text and ue4ss.CONSOLE_UNHOOK_KEPT in text
    assert 'RegisterHook("/Script/Engine.PlayerController:ClientRestart"' in text and "CreateConsole()" in text
    assert ue4ss.fix_console_mod(str(tmp_path)) is False   # once only
    assert script.read_text(encoding="utf-8") == text


def test_the_unhook_spaced_or_quoted_differently_comes_out_too(tmp_path):
    script = _mod(tmp_path, SCRIPT.replace(ue4ss.CONSOLE_UNHOOK,
                                           "UnregisterHook( '/Script/Engine.PlayerController:ClientRestart', Pre,Post )"))
    assert ue4ss.fix_console_mod(str(tmp_path)) is True
    text = script.read_text(encoding="utf-8")
    assert not ue4ss.CONSOLE_UNHOOK_PATTERN.search(text) and ue4ss.CONSOLE_UNHOOK_KEPT in text


def test_an_unhook_it_doesnt_know_is_told(tmp_path):
    _mod(tmp_path, SCRIPT.replace(ue4ss.CONSOLE_UNHOOK, 'UnregisterHook("/Script/Engine.PlayerController:ClientRestart", Hooks.Pre, Hooks.Post)'))
    said = []
    assert ue4ss.fix_console_mod(str(tmp_path), log=said.append) is False
    assert len(said) == 1 and "fights may crash" in said[0]


def test_no_console_mod_or_another_script_is_left_alone(tmp_path):
    assert ue4ss.fix_console_mod(str(tmp_path)) is False
    script = _mod(tmp_path, "print('a console enabler of another kind')\n")
    assert ue4ss.fix_console_mod(str(tmp_path)) is False
    assert script.read_text(encoding="utf-8") == "print('a console enabler of another kind')\n"


def test_configure_loader_fixes_it(tmp_path):
    mods = tmp_path / "ue4ss" / "Mods"
    mods.mkdir(parents=True)
    (mods / "mods.txt").write_text("ConsoleEnablerMod : 1\n", encoding="utf-8")
    script = _mod(mods, SCRIPT)
    ue4ss.configure_loader(str(tmp_path), console=True)
    assert ue4ss.CONSOLE_UNHOOK not in script.read_text(encoding="utf-8")
    assert os.path.isfile(mods / "mods.txt")
