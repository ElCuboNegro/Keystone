@echo off
echo Installing required dependencies for codebase analysis...
pip install datasketch uncompyle6

echo Checking for dotnet (required for .NET decompilation)...
dotnet --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Installing ilspycmd...
    dotnet tool install -g ilspycmd
) else (
    echo [WARNING] Dotnet not found. Skipping ilspycmd installation.
)

echo Downloading CFR Java Decompiler...
if not exist "tools\bin" mkdir "tools\bin"
powershell -Command "Invoke-WebRequest -Uri 'https://www.benf.org/other/cfr/cfr-0.152.jar' -OutFile 'tools\bin\cfr.jar'"

echo Setup complete.
