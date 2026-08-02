@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: Error log file (same folder as the executable)
set "LOG_FILE=%~dp0DanOverlay_error.txt"

echo ===================================
echo  Dan Overlay - osu!mania 4K
echo ===================================

:: Check if tosu is running
echo [INFO] Verifying connection to tosu on 127.0.0.1:24050...
powershell -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:24050/json' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [WARN] tosu not detected ? the overlay will wait for connection automatically.
    echo        Download tosu from: https://tosu.app
    echo.
) else (
    echo [OK] tosu detected.
)

:: Launch the distributed executable (searches for DanOverlay*.exe in the same folder)
echo [INFO] Starting overlay...
for %%f in ("%~dp0DanOverlay*.exe") do (
    :: Clear previous log and launch if executable exists
    if exist "%LOG_FILE%" del /f /q "%LOG_FILE%" >nul 2>&1
    start "" "%%f"
    exit /b 0
)

:: Executable not found ? log error
(
    echo === DAN OVERLAY ? ERROR LOG ===
    echo Date/Time  : %DATE% %TIME%
    echo.
    echo [STARTUP ERROR] DanOverlay*.exe was not found in:
    echo   %~dp0
    echo.
    echo Possible causes:
    echo   1. build.bat has not been run yet.
    echo   2. The executable was moved out of this folder.
    echo   3. Antivirus quarantined or deleted the executable.
    echo.
    echo Solution: Run build.bat in the project root.
) > "%LOG_FILE%"

:: Fallback: dev mode ? search for Python in .venv or system PATH
set "DEV_ENTRY=%~dp0..\..\src\01_overlay_ui\main.py"
set "VENV_PY=%~dp0..\..\.venv\Scripts\python.exe"

if exist "%~dp0..\..\.venv\Scripts\python.exe" (
    echo [INFO] Dev mode ? using .venv
    "%~dp0..\..\.venv\Scripts\python.exe" "%DEV_ENTRY%"
    exit /b %ERRORLEVEL%
)

:: Final attempt: system Python
where python >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Dev mode ? using system Python
    python "%DEV_ENTRY%"
    exit /b %ERRORLEVEL%
)

echo [ERROR] Neither DanOverlay*.exe nor Python was found. Check %LOG_FILE%
pause