@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal

:: ══════════════════════════════════════════════════════════════
::  build.bat  —  PyInstaller build script for DanOverlay
::  Zero-install: users only need to download and run the folder/executable.
::
::  Usage:
::    build.bat           → --onefile production build (single .exe)
::    build.bat --dev     → --onedir debug build (faster compilation)
::    build.bat --no-audio→ compile without ffmpeg (not recommended)
:: ══════════════════════════════════════════════════════════════

set "APP_BASE=DanOverlay"
set "APP_VERSION=2.2.0"
set "BUILD_NAME=%APP_BASE% %APP_VERSION%"
set "ENTRY=src\01_overlay_ui\main.py"

:: Build options
set "BUILD_MODE=--onefile"
set "REQUIRE_FFMPEG=1"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--dev" set "BUILD_MODE=--onedir"
if /I "%~1"=="--no-audio" set "REQUIRE_FFMPEG=0"
shift
goto parse_args
:args_done

echo =====================================================
echo  Build - %BUILD_NAME%
echo  Artifact : %BUILD_NAME%
echo  Mode     : %BUILD_MODE%
if "%REQUIRE_FFMPEG%"=="1" (
    echo  Audio    : ffmpeg required and embedded
) else (
    echo  Audio    : optional ^(no audio visualizer in build^)
)
echo =====================================================
echo.

:: ── Preflight: validar archivos criticos ─────────────────────
echo [INFO] Checking required files...
if not exist "%ENTRY%" (
    echo [ERROR] Missing entry point: %ENTRY%
    exit /b 1
)
if not exist "src\01_overlay_ui\web\index.html" (
    echo [ERROR] Missing web\index.html
    exit /b 1
)
if not exist "src\01_overlay_ui\web\ui-2\index.html" (
    echo [ERROR] Missing web\ui-2\index.html
    exit /b 1
)
if not exist "src\01_overlay_ui\web\ui-3\index.html" (
    echo [ERROR] Missing web\ui-3\index.html
    exit /b 1
)
if not exist "src\01_overlay_ui\web\ui-4\index.html" (
    echo [ERROR] Missing web\ui-4\index.html
    exit /b 1
)
if not exist "src\01_overlay_ui\web\ui-5\index.html" (
    echo [ERROR] Missing web\ui-5\index.html
    exit /b 1
)
if not exist "src\01_overlay_ui\web\ui-6\index.html" (
    echo [ERROR] Missing web\ui-6\index.html
    exit /b 1
)
if not exist "src\01_overlay_ui\web\graph.ico" (
    echo [ERROR] Missing graph.ico
    exit /b 1
)
if not exist "config\role_scales.json" (
    echo [ERROR] Missing config\role_scales.json
    exit /b 1
)
if not exist "config\sr_means.json" (
    echo [ERROR] Missing config\sr_means.json
    exit /b 1
)
if not exist "config\sr_means_7k.json" (
    echo [ERROR] Missing config\sr_means_7k.json
    exit /b 1
)
if not exist "config\celestial_profiles.json" (
    echo [ERROR] Missing config\celestial_profiles.json
    exit /b 1
)
if not exist "config\signicial_profiles.json" (
    echo [ERROR] Missing config\signicial_profiles.json
    exit /b 1
)
if not exist "config\shoegazer_profiles.json" (
    echo [ERROR] Missing config\shoegazer_profiles.json
    exit /b 1
)
if not exist "config\ln_course_profiles.json" (
    echo [ERROR] Missing config\ln_course_profiles.json
    exit /b 1
)
if not exist "tools\bin\msd.exe" (
    echo [ERROR] Missing tools\bin\msd.exe
    exit /b 1
)

:: ── Locate ffmpeg.exe (required for the audio visualizer) ────────
:: Check in src\01_overlay_ui\ffmpeg\ first, then local ffmpeg\, then PATH.
set "FFMPEG_BIN="
if exist "%~dp0src\01_overlay_ui\ffmpeg\ffmpeg.exe" (
    set "FFMPEG_BIN=%~dp0src\01_overlay_ui\ffmpeg\ffmpeg.exe"
    echo [INFO] ffmpeg.exe found in src\01_overlay_ui\ffmpeg\ -- will be embedded.
) else if exist "%~dp0ffmpeg\ffmpeg.exe" (
    set "FFMPEG_BIN=%~dp0ffmpeg\ffmpeg.exe"
    echo [INFO] ffmpeg.exe found in ffmpeg\ -- will be embedded.
) else (
    for /f "delims=" %%i in ('where ffmpeg 2^>nul') do (
        if not defined FFMPEG_BIN (
            set "FFMPEG_BIN=%%i"
            echo [INFO] ffmpeg.exe found in PATH -- will be embedded.
        )
    )
)
if "%FFMPEG_BIN%"=="" (
    if "%REQUIRE_FFMPEG%"=="1" (
        echo [ERROR] ffmpeg.exe NOT found in src\01_overlay_ui\ffmpeg\, ffmpeg\, or PATH.
        echo         This build mode requires ffmpeg for a complete bundle.
        echo         Place ffmpeg.exe in src\01_overlay_ui\ffmpeg\ and try again.
        exit /b 1
    ) else (
        echo [WARN] ffmpeg.exe NOT found in src\01_overlay_ui\ffmpeg\, ffmpeg\, or PATH.
        echo        Building without audio visualizer due to --no-audio.
        echo.
    )
)

:: ── Select Python Environment ──────────────────────────────────
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    set "PIP=.venv\Scripts\pip.exe"
) else (
    set "PY=python"
    set "PIP=pip"
    echo [WARN] .venv not found — using system Python.
)

:: ── Verify / install dependencies ─────────────────────────────
set "REQUIRED_PY_PKGS=pyinstaller pywebview requests pillow numpy pandas websocket-client pythonnet clr-loader tzdata"
for %%P in (%REQUIRED_PY_PKGS%) do (
    %PY% -m pip show %%P >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Installing %%P...
        %PIP% install %%P --quiet
        if errorlevel 1 (
            echo [ERROR] Could not install %%P.
            exit /b 1
        )
    )
)

:: ── Clean previous builds ─────────────────────────────────────
if exist "dist\%BUILD_NAME%"      rmdir /s /q "dist\%BUILD_NAME%"
if exist "dist\%BUILD_NAME%.exe"  del /f /q "dist\%BUILD_NAME%.exe"
if exist "build"                  rmdir /s /q "build"
if exist "%APP_BASE%.spec"        del /q "%APP_BASE%.spec"
if exist "%BUILD_NAME%.spec"      del /q "%BUILD_NAME%.spec"

:: ── Data Files to Bundle ──────────────────────────────────────
::  --add-data "source;destination_in_MEIPASS"
::  resource_path() in code relies on these paths.

set "DATA="
set "DATA=%DATA% --add-data "src\01_overlay_ui\web;web""
set "DATA=%DATA% --add-data "config;config""
set "DATA=%DATA% --add-data "tools\bin\msd.exe;.""
if not "%FFMPEG_BIN%"=="" set "DATA=%DATA% --add-binary "%FFMPEG_BIN%;.""

:: ── Module Search Paths ───────────────────────────────────────
set "PATHS="
set "PATHS=%PATHS% --paths "src""
set "PATHS=%PATHS% --paths "src\01_overlay_ui""
set "PATHS=%PATHS% --paths "src\02_runtime_bridge""
set "PATHS=%PATHS% --paths "src\03_engine_reference""
set "PATHS=%PATHS% --paths "src\07_model""

:: ── Hidden imports ────────────────────────────────────────────
::  Modules imported dynamically that PyInstaller might miss.
set "HIDDEN="
set "HIDDEN=%HIDDEN% --hidden-import sr_core"
set "HIDDEN=%HIDDEN% --hidden-import sr_core.algorithm"
set "HIDDEN=%HIDDEN% --hidden-import sr_core.osu_file_parser"
set "HIDDEN=%HIDDEN% --hidden-import numpy"
set "HIDDEN=%HIDDEN% --hidden-import pandas"
set "HIDDEN=%HIDDEN% --hidden-import bisect"
set "HIDDEN=%HIDDEN% --hidden-import heapq"
:: New event-driven overlay runtime modules
set "HIDDEN=%HIDDEN% --hidden-import events"
set "HIDDEN=%HIDDEN% --hidden-import contracts"
set "HIDDEN=%HIDDEN% --hidden-import tosu_source"
set "HIDDEN=%HIDDEN% --hidden-import analysis_coordinator"
set "HIDDEN=%HIDDEN% --hidden-import bridge"
set "HIDDEN=%HIDDEN% --hidden-import audio_service"
set "HIDDEN=%HIDDEN% --hidden-import chart_export"
set "HIDDEN=%HIDDEN% --hidden-import overlay_host"
set "HIDDEN=%HIDDEN% --hidden-import webview"
set "HIDDEN=%HIDDEN% --hidden-import requests"
set "HIDDEN=%HIDDEN% --hidden-import websocket"
set "HIDDEN=%HIDDEN% --hidden-import pythonnet"
set "HIDDEN=%HIDDEN% --hidden-import clr_loader"
set "HIDDEN=%HIDDEN% --hidden-import bottle"
set "HIDDEN=%HIDDEN% --hidden-import proxy_tools"
set "HIDDEN=%HIDDEN% --hidden-import PIL"
set "HIDDEN=%HIDDEN% --hidden-import PIL.Image"
set "HIDDEN=%HIDDEN% --hidden-import PIL.ImageDraw"
set "HIDDEN=%HIDDEN% --hidden-import PIL.ImageFont"
set "HIDDEN=%HIDDEN% --hidden-import PIL.ImageFilter"
:: Pipeline dynamic imports (inside function bodies, missed by static analysis)
set "HIDDEN=%HIDDEN% --hidden-import parser"
set "HIDDEN=%HIDDEN% --hidden-import validator"
set "HIDDEN=%HIDDEN% --hidden-import feature_extractor"
set "HIDDEN=%HIDDEN% --hidden-import primary_sr_bridge"
set "HIDDEN=%HIDDEN% --hidden-import classifier"
set "HIDDEN=%HIDDEN% --hidden-import rank_engine"
set "HIDDEN=%HIDDEN% --hidden-import minacalc_estimator"
set "HIDDEN=%HIDDEN% --hidden-import minacalc_bridge"
set "HIDDEN=%HIDDEN% --hidden-import celestial_estimator"
set "HIDDEN=%HIDDEN% --hidden-import signicial_estimator"
set "HIDDEN=%HIDDEN% --hidden-import shoegazer_estimator"
set "HIDDEN=%HIDDEN% --hidden-import ln_course_estimator"
:: resource_path utils (used at freeze time)
set "HIDDEN=%HIDDEN% --hidden-import resource_path"

:: ── Collect Binaries and Data (native Windows DLLs) ───────────
set "COLLECT="
set "COLLECT=%COLLECT% --collect-binaries numpy"
set "COLLECT=%COLLECT% --collect-binaries pandas"
set "COLLECT=%COLLECT% --collect-data pandas"
set "COLLECT=%COLLECT% --collect-data tzdata"
set "COLLECT=%COLLECT% --collect-all webview"
set "COLLECT=%COLLECT% --collect-all clr_loader"
set "COLLECT=%COLLECT% --collect-all pythonnet"

:: ── Compile ───────────────────────────────────────────────────
echo [INFO] Compiling...
if not "%FFMPEG_BIN%"=="" (
    echo [INFO] ffmpeg embedded: %FFMPEG_BIN%
) else (
    echo [WARN] Compiling WITHOUT ffmpeg -- audio visualizer will be disabled.
)
%PY% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    %BUILD_MODE% ^
    --noconsole ^
    --name "%BUILD_NAME%" ^
    --icon "src\01_overlay_ui\web\graph.ico" ^
    --noupx ^
    %DATA% ^
    %PATHS% ^
    %HIDDEN% ^
    %COLLECT% ^
    "%ENTRY%"

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check the messages above.
    exit /b 1
)

if "%BUILD_MODE%"=="--onefile" (
    if not exist "dist\%BUILD_NAME%.exe" (
        echo [ERROR] Build finished but executable is missing in dist.
        exit /b 1
    )
) else (
    if not exist "dist\%BUILD_NAME%" (
        echo [ERROR] Build finished but output folder is missing in dist.
        exit /b 1
    )
)

:: ── Prepare Distribution (onedir files) ───────────────────────
if "%BUILD_MODE%"=="--onedir" (
    if exist "src\04_packaging_and_launch\run.bat" copy /y "src\04_packaging_and_launch\run.bat" "dist\%BUILD_NAME%\run.bat" >nul
)

echo.
echo [OK] Build complete.
if "%BUILD_MODE%"=="--onefile" (
    echo      → dist\%BUILD_NAME%.exe
) else (
    echo      → dist\%BUILD_NAME%\
)
echo.
if "%BUILD_MODE%"=="--onefile" (
    echo      To distribute: share only the single executable above.
) else (
    echo      To distribute: share the dist\%BUILD_NAME%\ folder.
    echo      Users only need to open run.bat ^(or launch the .exe directly^).
)
echo      No Python installation or dependencies are required.
echo.
endlocal
