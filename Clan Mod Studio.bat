@echo off
rem Double-click to open Clan Mod Studio in your browser. Close this window to stop it.
rem Drop a downloaded mod's .zip on this file to add it (the studio opens with it ready to add).
title Clan Mod Studio
cd /d "%~dp0"
call "%~dp0wcmods\findpython.bat"
if not defined PY exit /b 1
if "%~1"=="" (
  %PY% wcmods.py studio
) else (
  %PY% wcmods.py studio --add "%~1"
)
if errorlevel 1 (
  echo.
  echo Something went wrong; the message above says what.
  pause
)
