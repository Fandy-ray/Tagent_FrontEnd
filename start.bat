@echo off
setlocal enabledelayedexpansion

REM TAgent - one-click start (double-click to run).
REM
REM   basic-agent   127.0.0.1:5001
REM   tagentnote    127.0.0.1:5173   <- open this in your browser
REM
REM IMPORTANT: start OpenNotebook FIRST (UI on 8502, REST API on 5055).
REM This script only probes it; it will not launch it. Without OpenNotebook
REM the app still runs, but answers only use the local textbook.
REM
REM The first run installs Python and Node dependencies, which takes a while.
REM
REM Works whether this file sits in the handover root or next to the
REM scripts folder - it looks for scripts\start.ps1 in both places.

set "PS1="
if exist "%~dp0scripts\start.ps1" set "PS1=%~dp0scripts\start.ps1"
if not defined PS1 (
  for /d %%D in ("%~dp0*") do (
    if exist "%%~fD\scripts\start.ps1" set "PS1=%%~fD\scripts\start.ps1"
  )
)

if not defined PS1 (
  echo [ERROR] Cannot find scripts\start.ps1 under "%~dp0".
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
