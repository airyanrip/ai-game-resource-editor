@echo off
rem Drag images or folders onto this file to remove backgrounds (output: "transparent" folder next to originals).
rem ASCII only on purpose (non-ASCII breaks .bat under some Windows code pages).
set "PATH=%PATH%;%LOCALAPPDATA%\hermes\bin;%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin"
if "%~1"=="" (
  echo Usage: drag images or folders onto this file, or: remove_bg.bat file_or_folder [options]
  pause
  exit /b 1
)
uv run "%~dp0remove_bg.py" %*
pause
