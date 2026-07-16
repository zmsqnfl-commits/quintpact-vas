@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0\.."
python scripts\build_release.py
exit /b %errorlevel%
