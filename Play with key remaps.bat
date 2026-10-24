@echo off
rem Double-click to start Warrior Cats with your key remaps (the Controls page) active.
rem The remapper stops by itself when the game closes; close this window to stop it sooner.
rem Clan Mod Studio's Play button does the same.
title Warrior Cats - key remapper
cd /d "%~dp0"
if not exist "%~dp0wcmods\findpython.bat" goto :moved
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
exit /b

:moved
echo.
echo  This file has to stay in the wcmods folder, next to wcmods.py, to find the rest of it.
echo  To start it from the desktop, make a shortcut instead: right-click it in the wcmods folder,
echo  then Send to, Desktop (create shortcut).
echo.
pause
exit /b 1
