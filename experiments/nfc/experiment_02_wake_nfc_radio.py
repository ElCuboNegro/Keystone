#!/usr/bin/env python3
"""
EXPERIMENT 02: Wake the NFC Radio via DIRECT SCardControl
==========================================================
Protocol: Unknown Domain Protocol v1.0

HYPOTHESIS:
  The NFC radio is off (Armoury Crate turned it off after last read).
  From Experiment 01: SCARD_W_REMOVED_CARD on SHARED/EXCLUSIVE connect.
  DIRECT mode connects fine (no card needed).

  We can re-enable the NFC radio by sending control commands in DIRECT mode,
  then switch to SHARED mode to read the card.

WHAT THIS TESTS:
  1. Which IOCTL values does Microsoft IFD 0 accept via SCardControl?
  2. Can we use PN532 escape commands (0x312000) on this reader?
  3. Can we use NFC CX IOCTLs to turn RF field on?
  4. After any successful control, can we connect in SHARED mode?
  5. Does simply waiting (without any control) allow the reader to re-enable RF?

REQUIRED:
  - Keystone card placed on the reader
  - Run from: C:\\Users\\jalba\\desktop\\keystone

RUN:
  python experiments/nfc/experiment_02_wake_nfc_radio.py
"""

import sys
import time
import ctypes
from pathlib import Path
from ctypes import byref, c_ubyte

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'tools' / 'probe'))
from winscard_ctypes import (
    SCardEstablishContext, SCardReleaseContext, SCardConnectW, SCardDisconnect,
    SCardBeginTransaction, SCardEndTransaction, SCardTransmit, SCardControl,
    SCARD_SCOPE_USER, SCARD_SHARE_SHARED, SCARD_SHARE_EXCLUSIVE, SCARD_SHARE_DIRECT,
    SCARD_PROTOCOL_ANY, SCARD_PROTOCOL_T0, SCARD_PROTOCOL_T1,
    SCARD_LEAVE_CARD, SCARD_UNPOWER_CARD, SCARD_PROTOCOL_UNDEFINED,
    SCARDCONTEXT, SCARDHANDLE, DWORD,
    WinSCardError, check, list_readers, transmit, control, bytes_to_hex
)

GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]

# ─── IOCTL candidates to try ─────────────────────────────────────────────────

IOCTL_CANDIDATES = {
    # ACR122U / CCID escape (USB CCID devices)
    'CCID_ESCAPE_WIN':        0x00312000,  # SCARD_CTL_CODE(3136)
    'CCID_ESCAPE_LINUX':      0x42000001,

    # Windows NFC CX IOCTL range (guesses based on IOCTL_NFCCX_* pattern)
    # IOCTL format: DeviceType=0x22 (FILE_DEVICE_SMARTCARD), Method=BUFFERED
    # SCARD_CTL_CODE(n) = 0x31 << 16 | n << 2
    'SCARD_CTL_3200':         0x00313200,
    'SCARD_CTL_3201':         0x00313204,
    'SCARD_CTL_3202':         0x00313208,
    'SCARD_CTL_1':            0x00310004,
    'SCARD_CTL_2':            0x00310008,
    'SCARD_CTL_0x4':          0x00310010,
    'SCARD_CTL_0x100':        0x00310400,
    'SCARD_CTL_0x200':        0x00310800,

    # NFC CX IOCTLs: FILE_DEVICE_NFP = 0x22 (same as smartcard), access varies
    # From Windows DDK headers (approximated)
    'NFP_ENABLE':             0x00220008,
    'NFP_DISABLE':            0x0022000C,
    'RADIO_ON':               0x00220004,
}

# PN532 RF field ON command (for ACR122U — may not work on NfcCx)
PN532_RF_ON  = [0xFF, 0x00, 0x00, 0x00, 0x04, 0xD4, 0x32, 0x01, 0x01]
PN532_SAM    = [0xFF, 0x00, 0x00, 0x00, 0x03, 0xD4, 0x14, 0x01]
NOP_CMD      = [0x00]  # minimal payload to test if any IOCTL responds


def try_connect_shared(hCtx, reader: str, label: str) -> bool:
    """Try to connect in SHARED mode and read UID. Returns True on success."""
    hCard = SCARDHANDLE()
    dwProto = DWORD()
    rv = SCardConnectW(hCtx, reader, SCARD_SHARE_SHARED, SCARD_PROTOCOL_ANY,
                       byref(hCard), byref(dwProto))
    if rv != 0:
        print(f"    [{label}] SHARED connect: FAILED 0x{rv & 0xFFFFFFFF:08X}")
        return False

    try:
        SCardBeginTransaction(hCard)
        data, sw1, sw2 = transmit(hCard, dwProto.value, GET_UID)
        uid = bytes_to_hex(data) if data else '(empty)'
        print(f"    [{label}] SHARED connect: OK  UID={uid}  SW={sw1:02X}{sw2:02X}")
        SCardEndTransaction(hCard, SCARD_LEAVE_CARD)
        SCardDisconnect(hCard, SCARD_LEAVE_CARD)
        return sw1 == 0x90
    except WinSCardError as e:
        print(f"    [{label}] SHARED read error: {e}")
        SCardDisconnect(hCard, SCARD_LEAVE_CARD)
        return False


print("=" * 70)
print("EXPERIMENT 02: Wake NFC Radio")
print("=" * 70)
print("\nFindings from Exp 01:")
print("  - SCARD_W_REMOVED_CARD on SHARED = RF field is OFF")
print("  - DIRECT mode works = we can send control commands to reader")
print("  - Goal: find the IOCTL that re-enables NFC radio")

hCtx = SCARDCONTEXT()
check(SCardEstablishContext(SCARD_SCOPE_USER, None, None, byref(hCtx)))
reader = list_readers(hCtx)[0]
print(f"\nReader: {reader}")

# ─── Part A: Baseline check (before any control) ─────────────────────────────
print("\n[Part A] Baseline — can we connect SHARED right now?")
try_connect_shared(hCtx, reader, "baseline")

# ─── Part B: Try each IOCTL via DIRECT mode ──────────────────────────────────
print("\n[Part B] Probing IOCTLs in DIRECT mode...")

hCard = SCARDHANDLE()
dwProto = DWORD()
rv = SCardConnectW(hCtx, reader, SCARD_SHARE_DIRECT, SCARD_PROTOCOL_UNDEFINED,
                   byref(hCard), byref(dwProto))
if rv != 0:
    print(f"  DIRECT connect failed: 0x{rv & 0xFFFFFFFF:08X}")
    SCardReleaseContext(hCtx)
    sys.exit(1)

print(f"  DIRECT connected (protocol={dwProto.value})")
print()

successful_ioctls = []

for name, ioctl in IOCTL_CANDIDATES.items():
    for payload, payload_name in [
        (NOP_CMD,    'NOP'),
        (PN532_RF_ON,'PN532_RF_ON'),
        (PN532_SAM,  'PN532_SAM'),
    ]:
        try:
            resp = control(hCard, ioctl, payload)
            resp_hex = bytes_to_hex(resp) if resp else '(empty)'
            print(f"  [OK] IOCTL={name}(0x{ioctl:08X}) payload={payload_name} → {resp_hex}")
            successful_ioctls.append({'ioctl': name, 'value': hex(ioctl), 'payload': payload_name, 'response': resp_hex})

            # After any successful IOCTL, immediately try SHARED connect
            SCardDisconnect(hCard, SCARD_LEAVE_CARD)
            time.sleep(0.3)
            success = try_connect_shared(hCtx, reader, f"after {name}")
            if success:
                print(f"  *** SUCCESS: IOCTL {name} woke the NFC radio! ***")

            # Reconnect DIRECT for next iteration
            rv2 = SCardConnectW(hCtx, reader, SCARD_SHARE_DIRECT, SCARD_PROTOCOL_UNDEFINED,
                                byref(hCard), byref(dwProto))
            if rv2 != 0:
                print(f"  DIRECT reconnect failed: 0x{rv2 & 0xFFFFFFFF:08X}")
                break

        except WinSCardError as e:
            if 'SHARING_VIOLATION' in str(e):
                print(f"  [SHARE] IOCTL={name}: sharing violation — Armoury Crate holds reader")
            # Most will fail — only print non-generic errors
            elif '0x00000001' not in str(e) and 'INVALID' not in str(e).upper():
                print(f"  [--] IOCTL={name}(0x{ioctl:08X}) {payload_name}: {e}")
        break  # only try NOP first for each IOCTL

SCardDisconnect(hCard, SCARD_LEAVE_CARD)

# ─── Part C: Wait and retry (does radio come back on its own?) ────────────────
print("\n[Part C] Passive wait — does the NFC radio re-enable on its own?")
print("  Waiting 5 seconds (try moving card away and back)...")
time.sleep(5)
try_connect_shared(hCtx, reader, "after 5s wait")

# ─── Part D: WM_INPUT path — poke ATKHID ────────────────────────────────────
print("\n[Part D] Can we trigger the ATKHotkey BIOS path via ATKACPI device?")
# The log showed: "y\\\\.\\ATKACPI" — ASUS ATK hotkey device
# Armoury Crate listens for WPARAM=0xB4 on a window message
# Let's check if the ATKACPI device exists and what it does
import ctypes.wintypes
kernel32 = ctypes.WinDLL('kernel32')
hDevice = kernel32.CreateFileW(
    r'\\.\ATKACPI',
    0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
    0x01 | 0x02,              # FILE_SHARE_READ | FILE_SHARE_WRITE
    None, 3, 0, None          # OPEN_EXISTING, normal
)
if hDevice != -1 and hDevice != 0xFFFFFFFFFFFFFFFF:
    print(f"  ATKACPI device opened: handle={hDevice}")
    kernel32.CloseHandle(hDevice)
else:
    err = kernel32.GetLastError()
    print(f"  ATKACPI open failed: error={err}")

SCardReleaseContext(hCtx)

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
if successful_ioctls:
    print(f"Responding IOCTLs: {[i['ioctl'] for i in successful_ioctls]}")
else:
    print("No IOCTLs responded — Microsoft IFD 0 likely does not support")
    print("raw escape commands. Need to use Windows NFC Proximity API instead.")
    print()
    print("NEXT HYPOTHESIS: The NFC radio is controlled at the Windows.Devices.Radios")
    print("level (NfcRadioMedia.dll), not via PC/SC SCardControl.")
    print()
    print("NEXT EXPERIMENT: Use Windows.Networking.Proximity or")
    print("DeviceIoControl on the raw NFC device node (not via PC/SC)")

import json
Path('output/experiment_02_results.json').write_text(
    json.dumps({'successful_ioctls': successful_ioctls}, indent=2), encoding='utf-8'
)
