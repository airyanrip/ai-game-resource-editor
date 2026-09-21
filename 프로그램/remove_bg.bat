@echo off
rem Drag images or folders onto this file to remove backgrounds (output: "transparent" folder next to originals).
rem ASCII only on purpose (non-ASCII breaks .bat under some Windows code pages).
set "PATH=%PATH%;%LOCALAPPDATA%\hermes\bin;%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin"
if "%~1"=="" (
  echo Usage: drag images or folders onto this file, or: remove_bg.bat file_or_folder [options]
  pause
  exit /b 1
)
where uv >nul 2>nul
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_uv.ps1"
  if errorlevel 1 exit /b 1
  set "PATH=%PATH%;%USERPROFILE%\.localin"
)
uv run "%~dp0remove_bg.py" %*
pause
