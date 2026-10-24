@echo off
rem Used by the launchers next to wcmods.py: sets PY to a Python 3.10 or newer. Without one, it says so
rem and offers to install it (with winget, Windows' own installer) or opens python.org. PY stays empty
rem when there's still none.
set "PY="
set "WCMODS_CHECK=import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
call :find
if defined PY exit /b 0

echo.
echo  Clan Mod Studio needs Python, version 3.10 or newer, and this computer doesn't have it.
echo  Python is free; it's what Clan Mod Studio is written in.
echo.
where winget >nul 2>nul || goto :manual
choice /c YN /m " Install it now, with Windows' own installer"
if errorlevel 2 goto :manual
echo.
winget install -e --id Python.Python.3.13 --scope user
set "WINGET=%errorlevel%"
call :find
if defined PY (
  echo.
  echo  Python is installed.
  echo.
  exit /b 0
)
if not "%WINGET%"=="0" (
  echo.
  echo  The installer couldn't install Python ^(the message above says why^).
  echo.
  goto :manual
)
echo.
echo  Python is installed, but this window can't see it yet.
echo  Close this window and double-click Clan Mod Studio again.
echo.
pause
exit /b 1

:manual
echo  Get it from https://www.python.org/downloads/ - in its installer, tick
echo  "Add python.exe to PATH". Then double-click Clan Mod Studio again.
echo.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:find
rem The Microsoft Store's "python" shortcut exists even without Python, so each one is asked to run.
for %%P in ("py -3" "python" "python3") do (
  if not defined PY %%~P -c "%WCMODS_CHECK%" >nul 2>nul && set "PY=%%~P"
)
if defined PY exit /b 0
rem Just installed, so not on this window's PATH yet: where Python puts itself for one user.
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
  if not defined PY if exist "%%~D\python.exe" "%%~D\python.exe" -c "%WCMODS_CHECK%" >nul 2>nul && set PY="%%~D\python.exe"
)
exit /b 0
