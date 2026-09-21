@echo off
setlocal
rem ASCII only on purpose: non-ASCII text in .bat breaks under some Windows code pages.
cd /d "%~dp0"
if not defined BGT_MINI (
  set "BGT_MINI=1"
  start "" /min cmd /c ""%~f0""
  exit /b
)
set "PATH=%PATH%;%LOCALAPPDATA%\hermes\bin;%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%LOCALAPPDATA%\Programs\uv"
set "APP="
set "APPDIR="
for /d %%D in (*) do if exist "%%D\remove_bg_gui.pyw" (set "APP=%%~fD\remove_bg_gui.pyw" & set "APPDIR=%%~fD\")
set "LOG=%~dp0error_log.txt"
if not defined APP (
  echo remove_bg_gui.pyw not found next to this file.> "%LOG%"
  start "" notepad "%LOG%"
  exit /b 1
)
where uv >nul 2>nul
if errorlevel 1 (
  rem uv (free Python runner) is missing: show a friendly dialog that offers auto-install or the install page.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%APPDIR%setup_uv.ps1"
  if errorlevel 1 exit /b 1
  set "PATH=%PATH%;%USERPROFILE%\.local\bin"
  where uv >nul 2>nul
  if errorlevel 1 (
    echo uv was not found. Install it from https://docs.astral.sh/uv/getting-started/installation/ > "%LOG%"
    start "" notepad "%LOG%"
    exit /b 1
  )
)
uv run --gui-script "%APP%" > "%LOG%" 2>&1
if errorlevel 1 (
  start "" notepad "%LOG%"
) else (
  erase "%LOG%" >nul 2>nul
)
