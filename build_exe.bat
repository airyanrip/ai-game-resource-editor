@echo off
setlocal
rem Build AI-Game-Resource-Editor.exe (single file, no console). Requires uv: https://docs.astral.sh/uv/
rem Output: dist\AI-Game-Resource-Editor.exe   (build\ and dist\ are git-ignored; publish the exe via GitHub Releases)
cd /d "%~dp0"
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
echo.
echo Done: %~dp0dist\AI-Game-Resource-Editor.exe
pause
