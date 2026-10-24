@echo off
rem Double-click to open Clan Mod Studio in your browser. Close this window to stop it.
title Clan Mod Studio
cd /d "%~dp0"
where python >nul 2>nul && (set "PY=python") || (set "PY=py -3")
%PY% wcmods.py studio
if errorlevel 1 (
  echo.
  echo Something went wrong; the message above says what.
  pause
)
