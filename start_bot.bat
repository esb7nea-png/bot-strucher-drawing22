@echo off
cd /d "%~dp0"
echo Starting Structural Drawing Bot...
start "" "%~dp0.venv\Scripts\pythonw.exe" bot.py
echo Bot started in background!
timeout /t 3 >nul
