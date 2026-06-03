@echo off
chcp 65001 >nul 2>&1
title VAS Agent Hub
echo =========================================
echo   Starting VAS Agent Hub (Local Mode)
echo =========================================
echo.
echo No server required. Opening directly in browser...
cd /d "%~dp0"
set "VAS_HUB=src\vas-hub.html"

if not exist "%VAS_HUB%" (
    echo.
    echo [ERROR] VAS hub file is missing.
    echo Missing file: %cd%\%VAS_HUB%
    echo Please check that the VAS folder was copied completely.
    echo.
    pause
    exit /b 1
)

echo Opening: %VAS_HUB%
start "" "%VAS_HUB%"

if errorlevel 1 (
    echo.
    echo [ERROR] Could not open the VAS hub automatically.
    echo Open this file manually in your browser:
    echo %cd%\%VAS_HUB%
    echo.
    pause
    exit /b 1
)
