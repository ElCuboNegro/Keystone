#!/bin/bash
# linux_setup.sh — Set up the Linux NFC environment for Keystone card reading
# Run as: bash tools/port/linux_setup.sh
set -e

echo "=== Keystone Linux NFC Setup ==="
echo ""

# ── 1. Install pcsclite + tools ──────────────────────────────────────────────
echo "[1] Installing pcsclite..."
if command -v apt &>/dev/null; then
    sudo apt-get install -y pcscd libpcsclite-dev pcsc-tools g++
elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm pcsclite pcsc-tools gcc
elif command -v dnf &>/dev/null; then
    sudo dnf install -y pcsc-lite pcsc-lite-devel pcsc-tools gcc-c++
fi

# ── 2. Start pcscd ────────────────────────────────────────────────────────────
echo "[2] Starting pcscd service..."
sudo systemctl enable --now pcscd || sudo service pcscd start || true

# ── 3. Check for NFC device nodes ────────────────────────────────────────────
echo ""
echo "[3] Checking for NFC hardware..."
echo ""

echo "--- /dev/nfc* ---"
ls /dev/nfc* 2>/dev/null && echo "(found)" || echo "(none — built-in chip may not have Linux driver)"

echo ""
echo "--- Kernel NFC modules ---"
lsmod | grep -E "nfc|nxp|pn5|nq_nci" || echo "(no NFC modules loaded)"

echo ""
echo "--- dmesg NFC messages ---"
dmesg | grep -iE "nfc|nxp.nci|pn5[0-9]|nq.nci" | tail -20 || echo "(none)"

echo ""
echo "--- I2C devices (NXP chip would be here) ---"
ls /sys/bus/i2c/devices/ | head -20
grep -rli "nxp\|nfc" /sys/bus/i2c/devices/*/name 2>/dev/null || echo "(no NXP I2C device found)"

echo ""
echo "--- PC/SC readers (via pcscd) ---"
pcsc_scan -r 2>/dev/null || echo "(pcsc_scan not available or no readers)"

# ── 4. Check for asus-wmi ─────────────────────────────────────────────────────
echo ""
echo "[4] ASUS WMI (ACPI) module..."
lsmod | grep asus || echo "(asus-wmi not loaded)"
ls /sys/devices/platform/asus-*/ 2>/dev/null | head -5 || echo "(no asus platform device)"

# ── 5. NXP chip identification ───────────────────────────────────────────────
echo ""
echo "[5] NXP NFC ACPI device..."
cat /sys/bus/acpi/devices/*/hardware_id 2>/dev/null | grep -i nxp || echo "(no NXP ACPI device found)"

# ── 6. Build the card reader ─────────────────────────────────────────────────
echo ""
echo "[6] Building keystone_reader..."
cd "$(dirname "$0")/../.." || exit 1
g++ tools/port/keystone_reader.cpp -lpcsclite -I/usr/include/PCSC -o tools/port/keystone_reader && \
    echo "[OK] Built: tools/port/keystone_reader" || echo "[FAIL] Build failed — check libpcsclite-dev"

echo ""
echo "=== SUMMARY ==="
echo ""
echo "If readers are found above: place card and run:"
echo "  tools/port/keystone_reader"
echo ""
echo "If no NFC device found:"
echo "  Option A: Load nxp-nci module: sudo modprobe nxp-nci-i2c"
echo "  Option B: Use external USB reader (ACR122U / SCL3711 / ACS1252)"
echo "  Option C: Check ACPI table: sudo cat /sys/bus/acpi/devices/*/hardware_id | grep -i nxp"
echo ""
echo "NCI 2.0 kernel bug warning:"
echo "  If dmesg shows nxp-nci but pcsc_scan shows no reader: hit kernel bug."
echo "  Workaround: try kernel <= 5.15 LTS, or install ifdnfc-nci bridge."
echo "  See: https://github.com/StarGate01/ifdnfc-nci"
