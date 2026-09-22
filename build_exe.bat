@echo off
setlocal
rem This script BUILDS the app from source (for developers). Requires uv: https://docs.astral.sh/uv/
rem Output: dist\AI-Game-Resource-Editor.exe (also copied next to this file, then launched automatically)
rem
rem Just want to USE the app? You don't need this script -- download the ready-made .exe instead:
rem   https://github.com/airyanrip/ai-game-resource-editor/releases/latest
rem (Downloading this repo as a ZIP via GitHub's "Code" button does NOT include the .exe --
rem  that only runs this build script, which takes a few minutes and needs uv.)
cd /d "%~dp0"
echo ============================================================
echo   Building AI Game Resource Editor from source (developers)
echo   Just want to use the app? Get the .exe here instead:
echo   https://github.com/airyanrip/ai-game-resource-editor/releases/latest
echo ============================================================
echo.
set "PATH=%PATH%;%USERPROFILE%\.local\bin;%LOCALAPPDATA%\hermes\bin"
where uv >nul 2>nul
if errorlevel 1 (
  rem uv (free Python runner) is missing: show a friendly dialog that offers auto-install or the install page.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup_uv.ps1"
  set "PATH=%PATH%;%USERPROFILE%\.local\bin"
  where uv >nul 2>nul
  if errorlevel 1 (
    echo uv still not found. Install it manually, then run build_exe.bat again:
    echo https://docs.astral.sh/uv/getting-started/installation/
    pause & exit /b 1
  )
)

uv run --with pyinstaller --with pillow --with numpy --with scipy --with tkinterdnd2 python tools\make_icon.py
if errorlevel 1 (pause & exit /b 1)

uv run --with pyinstaller --with pillow --with numpy --with scipy --with tkinterdnd2 pyinstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name AI-Game-Resource-Editor ^
  --icon assets\icon.ico ^
  --paths src ^
  --add-data "assets\icon.png;assets" ^
  --add-data "fonts\Galmuri11.ttf;fonts" ^
  --add-data "fonts\Galmuri14.ttf;fonts" ^
  --add-data "assets\icon.ico;assets" ^
  --collect-all tkinterdnd2 ^
  --hidden-import remove_bg ^
  --exclude-module matplotlib --exclude-module pandas --exclude-module IPython --exclude-module pytest ^
  "src\remove_bg_gui.pyw"
if errorlevel 1 (pause & exit /b 1)

copy /y "dist\AI-Game-Resource-Editor.exe" "%~dp0AI-Game-Resource-Editor.exe" >nul
echo.
echo ============================================================
echo   Done! Built: %~dp0AI-Game-Resource-Editor.exe
echo   Starting it now...
echo ============================================================
start "" "%~dp0AI-Game-Resource-Editor.exe"
timeout /t 5 >nul
