@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m backend.key_store save
pause
