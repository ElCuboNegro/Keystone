#!/bin/bash
echo "Installing required dependencies for codebase analysis..."
pip install datasketch uncompyle6

if command -v dotnet &> /dev/null; then
    echo "Installing ilspycmd..."
    dotnet tool install -g ilspycmd
else
    echo "[WARNING] Dotnet not found. Skipping ilspycmd."
fi

echo "Downloading CFR Java Decompiler..."
mkdir -p tools/bin
curl -L https://www.benf.org/other/cfr/cfr-0.152.jar -o tools/bin/cfr.jar

echo "Setup complete."
