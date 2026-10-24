@echo off
rem Double-click to start Warrior Cats with your key remaps (the Controls page) active.
rem The remapper stops by itself when the game closes; close this window to stop it sooner.
rem Clan Mod Studio's Play button does the same.
title Warrior Cats - key remapper
cd /d "%~dp0"
call "%~dp0wcmods\findpython.bat"
if not defined PY exit /b 1
%PY% wcmods.py play
if errorlevel 1 (
  echo.
  echo Something went wrong; the message above says what.
  pause
) else (
  timeout /t 5
)
