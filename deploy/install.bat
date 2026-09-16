@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0.."

echo.
echo  정부과제 매뉴얼 검색 도구 설치
echo  ================================
echo.

echo  [1/5] 파이썬 확인
where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 goto NO_PYTHON
    set "PY=python"
) else (
    set "PY=py -3"
)
for /f "tokens=2" %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"
echo       OK    Python %PYVER%
echo.

echo  [2/5] 가상환경 생성
if exist ".venv\Scripts\python.exe" (
    echo       OK    이미 있음
) else (
    %PY% -m venv .venv
    if errorlevel 1 goto VENV_FAIL
    echo       OK
)
echo.

echo  [3/5] 패키지 설치 ^(몇 분 걸립니다^)
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -e . --quiet
if errorlevel 1 goto PIP_FAIL
echo       OK
echo.

echo  [4/5] 동작 점검
".venv\Scripts\python.exe" deploy\selfcheck.py
if errorlevel 1 goto CHECK_FAIL
echo.

echo  [5/5] Claude Desktop 등록
".venv\Scripts\python.exe" deploy\setup_claude.py
if errorlevel 1 goto CLAUDE_FAIL
echo.

echo  ================================
echo   설치가 끝났습니다.
echo.
echo   Claude Desktop 을 완전히 종료했다가 다시 켜주세요.
echo   (작업표시줄 아이콘 우클릭 - 종료)
echo.
echo   그다음 Claude 에 이렇게 물어보세요:
echo     "국가연구개발사업에서 중소기업 기술료율이 얼마야?"
echo.
echo   쪽번호가 있는 답이 오면 정상입니다.
echo  ================================
echo.
pause
exit /b 0

:NO_PYTHON
echo       실패  파이썬이 설치되어 있지 않습니다.
echo.
echo   https://www.python.org/downloads/ 에서 내려받아 설치해주세요.
echo   설치 화면 맨 아래 "Add python.exe to PATH" 를 반드시 체크하세요.
echo   설치 후 이 창을 닫고 install.bat 을 다시 실행하면 됩니다.
echo.
pause
exit /b 1

:VENV_FAIL
echo       실패  가상환경을 만들지 못했습니다.
echo   폴더를 C:\rnd-manual 처럼 짧은 경로로 옮긴 뒤 다시 시도해주세요.
echo.
pause
exit /b 1

:PIP_FAIL
echo       실패  패키지 설치에 실패했습니다.
echo   인터넷 연결을 확인하고 다시 실행해주세요.
echo   회사망이라면 사내 프록시 때문일 수 있습니다.
echo.
pause
exit /b 1

:CHECK_FAIL
echo   점검에서 문제가 발견되었습니다. 위 내용을 전달해주세요.
echo.
pause
exit /b 1

:CLAUDE_FAIL
echo   Claude Desktop 설정 등록에 실패했습니다. 위 내용을 전달해주세요.
echo.
pause
exit /b 1
