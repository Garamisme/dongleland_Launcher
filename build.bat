@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Dongleland Mod Launcher v2.1 - Build Script
echo ============================================
echo.

REM Find a working Python command: prefer "py" (Python Launcher), fall back to "python"
set "PYCMD="
py --version >nul 2>nul && set "PYCMD=py"
if not defined PYCMD (
    python --version >nul 2>nul && set "PYCMD=python"
)
if not defined PYCMD (
    echo [ERROR] Python not found.
    echo  Install Python 3.10+ from https://www.python.org/downloads/
    echo  Make sure to check "Add python.exe to PATH" during install.
    pause & exit /b 1
)

echo [INFO] Using Python command: %PYCMD%
%PYCMD% --version
echo.

echo [1/3] Installing pip + PyInstaller + certifi + pywebview ...
%PYCMD% -m pip install --upgrade pip pyinstaller certifi pywebview
if %errorlevel% neq 0 ( echo [ERROR] Dependency install failed & pause & exit /b 1 )
echo.

echo [2/3] Building exe ... (this may take a while)
REM v2.1 changes vs old build:
REM  - entry point is app.py (pywebview), not mod_installer.py (old tkinter)
REM  - bundle frontend/ (HTML + local fonts + app_icon.png) so the UI is found
REM  - keep assets/ (icons, bundled mod jar) and certifi
REM  - collect-all webview so pywebview backend + injected JS are included
REM  - bundle dongleland-core.jar (Java Agent core mod). It must be next to
REM    this script before building (copy it from the core repo build/libs).
if not exist "dongleland-core.jar" (
    echo [WARN] dongleland-core.jar not found - building WITHOUT the core mod.
    echo        Build the core repo ^(gradlew build^) then copy
    echo        build\libs\dongleland-core.jar into this folder.
)
%PYCMD% -m PyInstaller --noconfirm --onefile --windowed ^
    --name "Dongleland_Launcher" ^
    --icon "assets/app_icon.ico" ^
    --add-data "assets;assets" ^
    --add-data "frontend;frontend" ^
    --add-data "dongleland-core.jar;." ^
    --collect-data certifi ^
    --collect-all webview ^
    app.py
if %errorlevel% neq 0 ( echo [ERROR] Build failed. Check the log above. & pause & exit /b 1 )
echo.

echo [3/3] Checking result ...
if exist "dist\Dongleland_Launcher.exe" (
    echo.
    echo [SUCCESS] dist\Dongleland_Launcher.exe created!
    echo  Location: %cd%\dist\Dongleland_Launcher.exe
    echo.
    echo  Distribution: just share this single exe file.
    echo  ^(assets + frontend are bundled inside the exe^)
    echo.
    echo  Note 1: antivirus may falsely flag the unsigned exe.
    echo   If the file disappears from dist, check the AV quarantine.
    echo  Note 2: the target PC needs the "WebView2 Runtime".
    echo   Windows 10/11 usually has it. If the window is blank,
    echo   install it from: https://developer.microsoft.com/microsoft-edge/webview2/
) else (
    echo [ERROR] exe was not created.
    echo  Check the log above or the AV quarantine.
)
echo.
pause
