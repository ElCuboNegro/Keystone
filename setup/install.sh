#!/bin/bash
# ============================================================
#  Keystone — Decompilation, Archaeology & Backtracking Suite
#  Full installation script for Linux/macOS
# ============================================================

set -e
echo ""
echo "============================================================"
echo " Keystone Suite Installer (Linux/macOS)"
echo "============================================================"
echo ""

# Python check
python3 --version || { echo "[ERROR] Python 3 not found."; exit 1; }
echo "[OK] Python found."

# pip
echo "[*] Upgrading pip..."
python3 -m pip install --upgrade pip --quiet

# Core packages
echo "[*] Installing Python packages..."
pip3 install pefile capstone r2pipe rich click requests beautifulsoup4 lxml python-dotenv --quiet
echo "[OK] Python packages installed."

# pyscard on Linux (much easier than Windows)
echo "[*] Installing pyscard..."
if command -v apt-get &>/dev/null; then
    sudo apt-get install -y python3-pyscard swig libpcsclite-dev pcscd 2>/dev/null || true
fi
pip3 install pyscard --quiet 2>/dev/null && echo "[OK] pyscard installed." || echo "[WARN] pyscard failed."

# Radare2
echo "[*] Checking Radare2..."
if ! command -v r2 &>/dev/null; then
    echo "[INFO] Radare2 not found. Install with:"
    if command -v apt-get &>/dev/null; then
        echo "       sudo apt-get install radare2"
    elif command -v brew &>/dev/null; then
        echo "       brew install radare2"
    else
        echo "       https://github.com/radareorg/radare2/releases"
    fi
else
    echo "[OK] Radare2: $(r2 -v | head -1)"
fi

# PC/SC daemon
echo "[*] Checking pcscd..."
if command -v pcscd &>/dev/null; then
    echo "[OK] pcscd found."
    sudo systemctl enable pcscd 2>/dev/null || true
    sudo systemctl start  pcscd 2>/dev/null || true
else
    echo "[INFO] pcscd not found. Install:"
    if command -v apt-get &>/dev/null; then
        echo "       sudo apt-get install pcscd pcsc-tools"
    fi
fi

# libnfc (for direct NFC access without pcscd)
echo "[*] Checking libnfc..."
if ! command -v nfc-list &>/dev/null; then
    echo "[INFO] libnfc not found. Install:"
    if command -v apt-get &>/dev/null; then
        echo "       sudo apt-get install libnfc-dev libnfc-bin"
    fi
else
    echo "[OK] libnfc: $(nfc-list --version 2>&1 | head -1)"
fi

# ILSpy for .NET
echo "[*] Checking ilspycmd..."
if ! command -v ilspycmd &>/dev/null; then
    if command -v dotnet &>/dev/null; then
        dotnet tool install ilspycmd -g 2>/dev/null && echo "[OK] ilspycmd installed." || echo "[WARN] ilspycmd install failed."
    else
        echo "[INFO] .NET SDK not found. For .NET DLL analysis: https://dotnet.microsoft.com/download"
    fi
else
    echo "[OK] ilspycmd found."
fi

echo ""
echo "============================================================"
echo " Installation complete."
echo " Test: python3 tools/probe/card_probe.py"
echo " DLL:  python3 tools/probe/dll_analyzer.py target.dll"
echo " Retro: python3 tools/retro/main.py ."
echo "============================================================"
