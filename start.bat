@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0backend\.venv\Scripts\python.exe" (
    echo [SunPath] Missing backend virtual environment. See README.md for first-time setup.
    pause
    exit /b 1
)
set "PYTHONUTF8=1"
"%~dp0backend\.venv\Scripts\python.exe" "%~dp0start.py" %*
set "SUNPATH_EXIT=%ERRORLEVEL%"
if not "%SUNPATH_EXIT%"=="0" pause
exit /b %SUNPATH_EXIT%
