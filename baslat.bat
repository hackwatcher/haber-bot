@echo off
cd /d "%~dp0"
start "" http://localhost:5055
python app.py
pause
