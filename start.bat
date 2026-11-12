@echo off
setlocal
cd /d "%~dp0"
rem Pick the launcher interpreter: project venv, portable Python 3.11 beside the repo, or python on PATH.
rem start.py verifies the chosen interpreter (3.11+ with backend dependencies) before starting anything.
set "PY="
if exist "%~dp0backend\.venv\Scripts\python.exe" set "PY=%~dp0backend\.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0..\Python311\python.exe" set "PY=%~dp0..\Python311\python.exe"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo [SunPath] No Python interpreter found. Complete first-time setup in README.md, or set SUNPATH_PYTHON.
    pause
    exit /b 1
)
set "PYTHONUTF8=1"
"%PY%" "%~dp0start.py" %*
set "SUNPATH_EXIT=%ERRORLEVEL%"
if not "%SUNPATH_EXIT%"=="0" pause
exit /b %SUNPATH_EXIT%
