@echo off
cd /d "%~dp0"
if exist "..\.venv-reel\Scripts\python.exe" (
  "..\.venv-reel\Scripts\python.exe" start_reel.py
) else (
  python start_reel.py
)
if errorlevel 1 pause
