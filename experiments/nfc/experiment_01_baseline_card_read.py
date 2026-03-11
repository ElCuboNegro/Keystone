#!/usr/bin/env python3
"""
EXPERIMENT 01: Baseline Card Read — How long can we hold the card connection?
===============================================================================
Protocol: Unknown Domain Protocol v1.0
Agent:    nfc-rfid-specialist

HYPOTHESIS:
  The SoulKey plugin calls SCardDisconnect with SCARD_UNPOWER_CARD immediately
  after reading card data, causing the card to lose power. By using
  SCARD_LEAVE_CARD, we can maintain the connection indefinitely.

WHAT THIS TESTS:
  1. Can we connect to the Microsoft IFD 0 reader via PC/SC?
  2. Can we read the card UID?
  3. How long does the connection stay alive with SCARD_LEAVE_CARD?
  4. What happens when Armoury Crate is also running (sharing violation)?

REQUIRED:
  - NFC card (Keystone card) placed on the reader
  - Armoury Crate may or may not be running (test both)

EXPECTED OUTCOMES:
  A. If SCARD_LEAVE_CARD works:
     → Card stays readable for multiple reads over several seconds
  B. If card disconnects anyway:
     → The NFC hardware itself is cycling (auto-poll issue)
  C. If SCARD_E_SHARING_VIOLATION:
     → Armoury Crate holds the reader exclusively — must be closed first

RUN:
  python experiments/nfc/experiment_01_baseline_card_read.py
"""

import sys
import time
import ctypes
from pathlib import Path
from ctypes import byref, c_ubyte

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'tools' / 'probe'))
from winscard_ctypes import (
    SCardEstablishContext, SCardReleaseContext, SCardConnectW, SCardDisconnect,
    SCardBeginTransaction, SCardEndTransaction, SCardTransmit,
    SCARD_SCOPE_USER, SCARD_SHARE_SHARED, SCARD_SHARE_EXCLUSIVE, SCARD_SHARE_DIRECT,
    SCARD_PROTOCOL_ANY, SCARD_LEAVE_CARD, SCARD_UNPOWER_CARD, SCARD_RESET_CARD,
    SCARD_PROTOCOL_UNDEFINED,
    SCARDCONTEXT, SCARDHANDLE, DWORD, SCARD_IO_REQUEST,
    WinSCardError, check, list_readers, transmit, bytes_to_hex
)

GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]

print(__doc__)
print("=" * 70)
print("STARTING EXPERIMENT 01")
print("=" * 70)

# Step 1: List readers
hCtx = SCARDCONTEXT()
check(SCardEstablishContext(SCARD_SCOPE_USER, None, None, byref(hCtx)))
readers = list_readers(hCtx)
print(f"\nReaders: {readers}")
if not readers:
    print("RESULT: BLOCKED — No readers found")
    sys.exit(1)
reader = readers[0]
print(f"Using: {reader}")

results = {
    'reader': reader,
    'trials': [],
}

# Step 2: Try connecting with different share modes
for share_mode, share_name, proto in [
    (SCARD_SHARE_SHARED,    'SHARED',    SCARD_PROTOCOL_ANY),
    (SCARD_SHARE_EXCLUSIVE, 'EXCLUSIVE', SCARD_PROTOCOL_ANY),
    (SCARD_SHARE_DIRECT,    'DIRECT',    SCARD_PROTOCOL_UNDEFINED),
]:
    print(f"\n--- Trial: {share_name} ---")
    hCard = SCARDHANDLE()
    dwProto = DWORD()

    rv = SCardConnectW(hCtx, reader, share_mode, proto, byref(hCard), byref(dwProto))
    if rv != 0:
        print(f"  Connect FAILED: 0x{rv & 0xFFFFFFFF:08X}")
        results['trials'].append({'mode': share_name, 'connect': 'failed', 'rv': hex(rv & 0xFFFFFFFF)})
        continue

    print(f"  Connected. Protocol: {dwProto.value}")
    trial = {'mode': share_name, 'connect': 'ok', 'protocol': dwProto.value, 'reads': []}

    # Step 3: Try to read UID multiple times over 5 seconds
    if dwProto.value in (1, 2):  # T0 or T1
        try:
            SCardBeginTransaction(hCard)
            for i in range(10):
                try:
                    data, sw1, sw2 = transmit(hCard, dwProto.value, GET_UID)
                    uid_hex = bytes_to_hex(data) if data else '(empty)'
                    status = 'OK' if sw1 == 0x90 else 'FAIL'
                    print(f"  Read {i+1}: {uid_hex}  SW={sw1:02X}{sw2:02X}  [{status}]")
                    trial['reads'].append({'i': i+1, 'uid': uid_hex, 'sw': f'{sw1:02X}{sw2:02X}'})
                except WinSCardError as e:
                    print(f"  Read {i+1}: ERROR — {e}")
                    trial['reads'].append({'i': i+1, 'error': str(e)})
                    break
                time.sleep(0.5)
            SCardEndTransaction(hCard, SCARD_LEAVE_CARD)
        except WinSCardError as e:
            print(f"  Transaction error: {e}")

    rv2 = SCardDisconnect(hCard, SCARD_LEAVE_CARD)
    print(f"  SCardDisconnect(LEAVE_CARD): {'OK' if rv2 == 0 else f'0x{rv2 & 0xFFFFFFFF:08X}'}")
    trial['disconnect'] = {'disposition': 'LEAVE_CARD', 'rv': hex(rv2 & 0xFFFFFFFF)}

    # Try to reconnect immediately (only for SHARED/EXCLUSIVE modes, not DIRECT)
    if share_mode != SCARD_SHARE_DIRECT:
        time.sleep(0.2)
        hCard2 = SCARDHANDLE()
        dwProto2 = DWORD()
        rv3 = SCardConnectW(hCtx, reader, share_mode, proto, byref(hCard2), byref(dwProto2))
        if rv3 == 0:
            try:
                data2, sw1_2, sw2_2 = transmit(hCard2, dwProto2.value, GET_UID)
                uid2 = bytes_to_hex(data2) if data2 else '(empty)'
                print(f"  Reconnect after LEAVE_CARD: UID={uid2} SW={sw1_2:02X}{sw2_2:02X}")
                trial['reconnect_after_leave'] = {'uid': uid2, 'sw': f'{sw1_2:02X}{sw2_2:02X}'}
            except WinSCardError as e:
                print(f"  Reconnect read error: {e}")
            SCardDisconnect(hCard2, SCARD_LEAVE_CARD)
        else:
            print(f"  Reconnect after LEAVE_CARD: FAILED 0x{rv3 & 0xFFFFFFFF:08X}")
            trial['reconnect_after_leave'] = {'error': hex(rv3 & 0xFFFFFFFF)}

    results['trials'].append(trial)
    print()

SCardReleaseContext(hCtx)

print("\n" + "=" * 70)
print("EXPERIMENT 01 RESULTS")
print("=" * 70)
for t in results['trials']:
    print(f"\nMode: {t['mode']} — Connect: {t['connect']}")
    for r in t.get('reads', []):
        if 'error' in r:
            print(f"  Read {r['i']}: ERROR {r['error']}")
        else:
            print(f"  Read {r['i']}: {r['uid']}  SW={r['sw']}")

import json
Path('output/experiment_01_results.json').write_text(
    json.dumps(results, indent=2), encoding='utf-8'
)
print("\n[OK] Results saved to output/experiment_01_results.json")
print("\nNEXT STEPS:")
print("  - If UID was read successfully: run experiment_02 to test SCARD_UNPOWER_CARD effect")
print("  - If SHARING_VIOLATION: close Armoury Crate and retry")
print("  - If no card detected: place Keystone card on reader first")
