@echo off
cd /d "%~dp0"
if exist scripts\setup-speech.py (python scripts\setup-speech.py) else (python setup-speech.py)
pause
