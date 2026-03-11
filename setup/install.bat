@echo off
REM ============================================================
REM  Keystone — Decompilation, Archaeology & Backtracking Suite
REM  Full installation script for Windows
REM  Run as Administrator for system-wide tools
REM ============================================================

echo.
echo ============================================================
echo  Keystone Suite Installer
echo ============================================================
echo.

REM ─── Python check ───────────────────────────────────────────
python --version 2>NUL
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from python.org
    exit /b 1
)
echo [OK] Python found.

REM ─── pip upgrade ────────────────────────────────────────────
echo.
echo [*] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM ─── Core analysis tools ────────────────────────────────────
echo [*] Installing Python packages...
pip install pefile capstone r2pipe rich click requests beautifulsoup4 lxml python-dotenv --quiet
if errorlevel 1 (
    echo [WARN] Some packages failed. Continuing...
)
echo [OK] Python packages installed.

REM ─── pyscard (requires Visual Studio Build Tools) ───────────
echo.
echo [*] Attempting pyscard install...
pip install pyscard --quiet 2>NUL
if errorlevel 1 (
    echo [WARN] pyscard failed to build ^(needs Visual Studio Build Tools^).
    echo        Workaround: ctypes + winscard.dll ^(already implemented^).
    echo        To fix: install Visual Studio Build Tools from:
    echo        https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo        Then run: pip install pyscard
) else (
    echo [OK] pyscard installed.
)

REM ─── Radare2 ────────────────────────────────────────────────
echo.
echo [*] Checking for Radare2...
where r2 >NUL 2>&1
if errorlevel 1 (
    echo [INFO] Radare2 not found. For advanced disassembly, install from:
    echo        https://github.com/radareorg/radare2/releases
    echo        After install, r2pipe Python bindings will work automatically.
) else (
    echo [OK] Radare2 found.
)

REM ─── Check PC/SC service ────────────────────────────────────
echo.
echo [*] Checking PC/SC service (SCardSvr)...
sc query SCardSvr >NUL 2>&1
if errorlevel 1 (
    echo [WARN] SCardSvr not found. Smart card service may not be available.
) else (
    echo [OK] SCardSvr found.
)

REM ─── Check WinSCard DLL ─────────────────────────────────────
if exist "%SystemRoot%\System32\winscard.dll" (
    echo [OK] winscard.dll found at %SystemRoot%\System32\winscard.dll
) else (
    echo [WARN] winscard.dll not found. PC/SC operations will fail.
)

REM ─── Check for .NET decompiler ──────────────────────────────
echo.
echo [*] Checking for .NET decompiler (ilspycmd)...
where ilspycmd >NUL 2>&1
if errorlevel 1 (
    echo [INFO] ilspycmd not found. For .NET DLL decompilation:
    echo        dotnet tool install ilspycmd -g
    echo        ^(requires .NET SDK: https://dotnet.microsoft.com/download^)
) else (
    echo [OK] ilspycmd found.
)

echo.
echo ============================================================
echo  Installation complete.
echo  Run a quick test: python tools/probe/card_probe.py
echo  Analyze a DLL:    python tools/probe/dll_analyzer.py target.dll
echo  Retro-engineer:   python tools/retro/main.py .
echo ============================================================
echo.
pause
