@echo off
chcp 65001 >nul 2>&1
title VAS 2.10.0
cd /d "%~dp0"

if not exist "src\vas-hub.html" goto :missing
if not exist "scripts\Start-VAS.ps1" goto :fallback

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Start-VAS.ps1"
if not errorlevel 1 exit /b 0

:fallback
echo [안내] 로컬 기능을 시작하지 못해 제한 모드로 엽니다.
echo Windows 폴더 선택창, 대화 설정 동기화, Windows 작업 기억은 사용할 수 없습니다.
echo 디자인 설정과 브라우저 저장, 프롬프트 복사, JSON 저장은 계속 사용할 수 있습니다.
start "" "%~dp0src\vas-hub.html"
if not errorlevel 1 exit /b 0
echo [오류] 브라우저를 열 수 없습니다.
echo 직접 여세요: %~dp0src\vas-hub.html
pause
exit /b 1

:missing
echo [오류] src\vas-hub.html 파일이 없습니다.
echo VAS 폴더가 완전히 복사되었는지 확인하세요.
pause
exit /b 1
