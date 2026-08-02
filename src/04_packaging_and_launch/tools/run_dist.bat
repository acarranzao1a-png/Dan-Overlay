@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ===================================
echo  Dan Overlay - osu!mania 4K
echo ===================================

:: Check if tosu is running
echo [INFO] Verifying connection to tosu...
powershell -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:24050/json' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] tosu was not detected running.
    echo         Please start tosu and run this file again.
    echo         Download tosu from: https://tosu.app
    echo.
    pause
    exit /b 1
)
echo [OK] tosu detected.

:: Launch the overlay and redirect stderr to overlay_log.txt
echo [INFO] Starting overlay...
set "OVERLAY_EXE="
for %%F in (*.exe) do (
    set "OVERLAY_EXE=%%~nxF"
    goto :run_overlay
)

echo.
echo [ERROR] No .exe was found in this folder.
echo         Please verify if the build is complete.
echo.
pause
exit /b 1

:run_overlay
%OVERLAY_EXE% 2> overlay_log.txt
if errorlevel 1 (
    echo.
    echo [ERROR] The overlay exited with an error.
    echo         Check overlay_log.txt for details.
    echo.
    pause
)
