@echo off
chcp 65001 > nul
cd /d "%~dp0.."

echo.
echo  정부과제 매뉴얼 검색 도구 점검
echo  ================================

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   설치가 안 되어 있습니다. install.bat 을 먼저 실행해주세요.
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" deploy\selfcheck.py
echo.
pause
