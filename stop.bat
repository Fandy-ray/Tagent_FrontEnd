@echo off
setlocal enabledelayedexpansion

REM TAgent - stop services (double-click to run).
REM
REM Stops basic-agent (5001) and tagentnote (5173).
REM OpenNotebook is not started by start.bat, so it is not stopped here either.
REM
REM Works whether this file sits in the handover root or next to the
REM scripts folder - it looks for scripts\stop.ps1 in both places.

set "PS1="
if exist "%~dp0scripts\stop.ps1" set "PS1=%~dp0scripts\stop.ps1"
if not defined PS1 (
  for /d %%D in ("%~dp0*") do (
    if exist "%%~fD\scripts\stop.ps1" set "PS1=%%~fD\scripts\stop.ps1"
  )
)

if not defined PS1 (
  echo [ERROR] Cannot find scripts\stop.ps1 under "%~dp0".
  echo Keep this .bat in the handover root, or next to the scripts folder.
  echo.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "!PS1!" %*
set "RC=!ERRORLEVEL!"
echo.
pause
exit /b !RC!
