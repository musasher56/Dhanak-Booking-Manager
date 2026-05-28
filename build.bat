@echo off
REM ═══════════════════════════════════════════════════════════════════
REM  build.bat  —  One-click builder for Dhanak Banquet Hall Manager
REM  Run this from the project root folder (where main.py lives).
REM ═══════════════════════════════════════════════════════════════════

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║   Dhanak Banquet Hall Manager — Build Script    ║
echo ╚══════════════════════════════════════════════════╝
echo.

REM ── Step 1: make sure pip packages are installed ────────────────────
echo [1/3] Installing / verifying dependencies...
pip install --quiet pyinstaller PySide6
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: pip install failed. Make sure Python is on your PATH.
    pause
    exit /b 1
)

REM ── Step 2: clean previous build artifacts ──────────────────────────
echo [2/3] Cleaning previous build...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

REM ── Step 3: run PyInstaller with our spec ───────────────────────────
echo [3/3] Building executable...
pyinstaller dhanak.spec
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: PyInstaller failed. Check the output above for details.
    pause
    exit /b 1
)

echo.
echo ══════════════════════════════════════════════════════
echo  BUILD SUCCESSFUL!
echo  Your application is at:  dist\Dhanak\Dhanak.exe
echo.
echo  To distribute: zip the entire dist\Dhanak\ folder.
echo  The .exe cannot run alone — it needs the whole folder.
echo ══════════════════════════════════════════════════════
echo.
pause
