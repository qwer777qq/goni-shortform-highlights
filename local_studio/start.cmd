@echo off
cd /d "%~dp0"
if exist "..\.venv\Scripts\python.exe" (
  "..\.venv\Scripts\python.exe" server.py --port 8767
) else (
  python server.py --port 8767
)
pause
