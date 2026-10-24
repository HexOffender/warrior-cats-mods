@echo off
rem Double-click to open Clan Mod Studio in your browser. Close this window to stop it.
rem Drop a downloaded mod's .zip on this file to add it (the studio opens with it ready to add).
title Clan Mod Studio
cd /d "%~dp0"
if not exist "%~dp0wcmods\findpython.bat" goto :moved
call "%~dp0wcmods\findpython.bat"
if not defined PY exit /b 1
set "SELF=%~nx0"
set "ADD=%~1"
set "CUT="
rem Explorer quotes a dropped file's path only when it has a space, so cmd cuts a name with an ampersand
rem in it there, and would run the rest as a command. The whole path is still in cmd's command line.
if defined ADD if not exist "%~1" call :whole
if not defined ADD (
  %PY% wcmods.py studio
) else (
  %PY% wcmods.py studio --add "%ADD%"
)
if errorlevel 1 (
  echo.
  echo Something went wrong; the message above says what.
  pause
)
rem After a cut path, cmd itself ends here, so what came after the ampersand never runs.
if defined CUT exit
exit /b

:whole
setlocal EnableDelayedExpansion
set "LINE=!cmdcmdline!"
set "LINE=!LINE:*%SELF%=!"
set "LINE=!LINE:"=!"
for /f "tokens=*" %%A in ("!LINE!") do set "LINE=%%A"
if not exist "!LINE!" (endlocal & exit /b)
endlocal & set "ADD=%LINE%" & set "CUT=1"
exit /b

:moved
echo.
echo  This file has to stay in the wcmods folder, next to wcmods.py, to find the rest of it.
echo  To start it from the desktop, make a shortcut instead: right-click it in the wcmods folder,
echo  then Send to, Desktop (create shortcut).
echo.
pause
exit /b 1
