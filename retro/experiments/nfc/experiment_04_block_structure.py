#!/usr/bin/env python3
"""
EXPERIMENT 04: Block Structure Investigation
=============================================
Protocol: Unknown Domain Protocol v1.0

CONFIRMED FROM EXPERIMENT 03:
  - Block 0: 01 01 01 01  (SW=9000 — readable)
  - Block 1: SW=6981      (Command incompatible with file structure — NOT a security lock)
  - ATR historical bytes: A0 00 00 03 06 0C 00 14 ... (NXP / ISO 15693 / 20 blocks?)
  - Session expires ~4.5s — must work fast

HYPOTHESIS A: Block 1 is a special system block (DSFID / AFI / lock bits)
  that NfcCx wraps differently and needs GET_SYSTEM_INFORMATION to map.

HYPOTHESIS B: Block 1 requires a different Le (block size != 4 bytes at that offset).

HYPOTHESIS C: Standard ISO 15693 GET_SYSTEM_INFORMATION (FF 30 00 00 00 or
  direct via NCI) would tell us: block count, block size, DSFID, AFI.

HYPOTHESIS D: GET_MULTIPLE_BLOCK_SECURITY_STATUS (FF 36 00 00 64) reveals
  which blocks are locked and which are free.

WHAT THIS TESTS:
  1. GET_SYSTEM_INFORMATION via every known APDU variant
  2. Block 1 with different Le values (1, 2, 8, 16, 32 bytes)
  3. GET_MULTIPLE_BLOCK_SECURITY_STATUS
  4. ISO 15693 direct commands (addressed mode with UID)
  5. Read ALL blocks quickly (no sleep) before session expires
  6. READ_MULTIPLE_BLOCKS starting at 0 for varying counts

RUN:
  python experiments/nfc/experiment_04_block_structure.py
"""

import sys
import time
import json
from pathlib import Path
from ctypes import byref

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'tools' / 'probe'))
from winscard_ctypes import (
    SCardEstablishContext, SCardReleaseContext, SCardConnectW, SCardDisconnect,
    SCardBeginTransaction, SCardEndTransaction,
    SCARD_SCOPE_USER, SCARD_SHARE_SHARED, SCARD_PROTOCOL_ANY,
    SCARD_LEAVE_CARD, SCARDCONTEXT, SCARDHANDLE, DWORD,
    WinSCardError, check, list_readers, transmit, bytes_to_hex
)

# ─── APDU helpers ─────────────────────────────────────────────────────────────

# FF B0 READ SINGLE BLOCK with variable Le
def read_block(block: int, le: int) -> list[int]:
    return [0xFF, 0xB0, 0x00, block, le]

# FF B3 READ MULTIPLE BLOCKS (alternate form used by some NfcCx stacks)
def read_multi_b3(first: int, count: int) -> list[int]:
    return [0xFF, 0xB3, 0x00, first, count]

# GET SYSTEM INFORMATION variants
SYS_INFO_FF30    = [0xFF, 0x30, 0x00, 0x00, 0x00]   # common variant
SYS_INFO_FF2B    = [0xFF, 0x2B, 0x00, 0x00, 0x00]   # NfcCx alternate

# GET MULTIPLE BLOCK SECURITY STATUS: blocks 0-63
GET_BLOCK_SEC_64 = [0xFF, 0x36, 0x00, 0x00, 0x40]   # 64 blocks

# ISO 15693 direct via NfcCx transparent: some drivers forward raw ISO cmds
# GET_SYSTEM_INFORMATION: flags=0x26 (option + addressed mode + high data rate)
CARD_UID_LSB = [0x54, 0xD4, 0x4C, 0x4F, 0x08, 0x01, 0x04, 0xE0]
ISO15693_SYSINFO_ADDRESSED = [0x22, 0x2B] + CARD_UID_LSB  # flags=0x22 + cmd=0x2B + UID

# Standard PC/SC GET UID (fast confirmation we're still connected)
GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]

# ─── Connect ──────────────────────────────────────────────────────────────────

print("=" * 70)
print("EXPERIMENT 04: Block Structure Investigation")
print("=" * 70)
print("Place card on reader NOW — connecting immediately...\n")

hCtx = SCARDCONTEXT()
check(SCardEstablishContext(SCARD_SCOPE_USER, None, None, byref(hCtx)))
reader = list_readers(hCtx)[0]

hCard = SCARDHANDLE()
dwProto = DWORD()
rv = SCardConnectW(hCtx, reader, SCARD_SHARE_SHARED, SCARD_PROTOCOL_ANY,
                   byref(hCard), byref(dwProto))
if rv != 0:
    print(f"Connect FAILED: 0x{rv & 0xFFFFFFFF:08X} — place card first")
    SCardReleaseContext(hCtx)
    sys.exit(1)

print(f"Connected. Protocol: {dwProto.value}")
SCardBeginTransaction(hCard)
t0 = time.monotonic()

results = {}

# ─── 1. Rapid block dump (all Le=4, no sleep) ─────────────────────────────────
print("\n[1] Rapid block dump (Le=4, no sleep)...")
blocks = {}
for b in range(32):
    try:
        data, sw1, sw2 = transmit(hCard, dwProto.value, read_block(b, 4))
        sw = f'{sw1:02X}{sw2:02X}'
        if sw1 == 0x90:
            h = bytes_to_hex(data)
            a = ''.join(chr(c) if 32 <= c < 127 else '.' for c in data)
            blocks[b] = {'hex': h, 'ascii': a, 'sw': sw}
            print(f"  Block {b:2d}: {h}  |{a}|")
        elif sw == '6A82':
            print(f"  Block {b:2d}: END OF MEMORY (6A82)")
            break
        elif sw == '6981':
            blocks[b] = {'sw': sw, 'note': 'incompatible structure'}
            print(f"  Block {b:2d}: SW=6981 (incompatible structure)")
        elif sw == '6982':
            blocks[b] = {'sw': sw, 'note': 'security not satisfied'}
            print(f"  Block {b:2d}: SW=6982 (security — locked)")
        else:
            blocks[b] = {'sw': sw}
            print(f"  Block {b:2d}: SW={sw}")
    except WinSCardError as e:
        blocks[b] = {'error': str(e)}
        print(f"  Block {b:2d}: {e}")
        if 'REMOVED' in str(e):
            print(f"  Session expired after {time.monotonic()-t0:.1f}s — stopping")
            break

results['blocks_le4'] = blocks
print(f"  [elapsed: {time.monotonic()-t0:.1f}s]")

# ─── 2. Block 1 with alternate Le values ──────────────────────────────────────
print("\n[2] Block 1 with alternate Le values...")
for le in [1, 2, 3, 8, 16, 32]:
    try:
        data, sw1, sw2 = transmit(hCard, dwProto.value, read_block(1, le))
        print(f"  Le={le:2d}: {bytes_to_hex(data) if data else '(empty)'}  SW={sw1:02X}{sw2:02X}")
    except WinSCardError as e:
        print(f"  Le={le:2d}: {e}")
        if 'REMOVED' in str(e):
            break

# ─── 3. GET SYSTEM INFORMATION variants ───────────────────────────────────────
print("\n[3] GET_SYSTEM_INFORMATION variants...")
for name, apdu in [('FF30', SYS_INFO_FF30), ('FF2B', SYS_INFO_FF2B)]:
    try:
        data, sw1, sw2 = transmit(hCard, dwProto.value, apdu)
        h = bytes_to_hex(data) if data else '(empty)'
        flag = '[OK]' if sw1 == 0x90 else '[--]'
        print(f"  {flag} {name}: {h}  SW={sw1:02X}{sw2:02X}")
        results[f'sys_info_{name}'] = {'data': h, 'sw': f'{sw1:02X}{sw2:02X}'}
    except WinSCardError as e:
        print(f"  [!!] {name}: {e}")
        if 'REMOVED' in str(e):
            break

# ─── 4. GET MULTIPLE BLOCK SECURITY STATUS ────────────────────────────────────
print("\n[4] GET_MULTIPLE_BLOCK_SECURITY_STATUS (blocks 0-63)...")
try:
    data, sw1, sw2 = transmit(hCard, dwProto.value, GET_BLOCK_SEC_64)
    if sw1 == 0x90:
        print(f"  [OK] Security status bytes: {bytes_to_hex(data)}")
        results['block_security'] = {'data': bytes_to_hex(data), 'sw': f'{sw1:02X}{sw2:02X}'}
        # Each byte: bit 0 = locked (1) / unlocked (0)
        for i, b in enumerate(data):
            if b != 0:
                print(f"  Block {i}: security byte = 0x{b:02X} (LOCKED)")
    else:
        print(f"  SW={sw1:02X}{sw2:02X}")
except WinSCardError as e:
    print(f"  {e}")

# ─── 5. READ MULTIPLE BLOCKS ──────────────────────────────────────────────────
print("\n[5] READ MULTIPLE BLOCKS (FF B3)...")
for count in [4, 8, 16]:
    try:
        data, sw1, sw2 = transmit(hCard, dwProto.value, read_multi_b3(0, count))
        if sw1 == 0x90:
            print(f"  count={count}: {bytes_to_hex(data)}  SW={sw1:02X}{sw2:02X}")
        else:
            print(f"  count={count}: SW={sw1:02X}{sw2:02X}")
    except WinSCardError as e:
        print(f"  count={count}: {e}")
        if 'REMOVED' in str(e):
            break

# ─── 6. Re-read block 0 to check timing ───────────────────────────────────────
print(f"\n[6] Block 0 re-read at t={time.monotonic()-t0:.1f}s...")
try:
    data, sw1, sw2 = transmit(hCard, dwProto.value, read_block(0, 4))
    print(f"  Block 0: {bytes_to_hex(data) if sw1==0x90 else '(fail)'}  SW={sw1:02X}{sw2:02X}")
    print(f"  Still alive at {time.monotonic()-t0:.1f}s")
except WinSCardError as e:
    print(f"  {e} at {time.monotonic()-t0:.1f}s")

SCardEndTransaction(hCard, SCARD_LEAVE_CARD)
SCardDisconnect(hCard, SCARD_LEAVE_CARD)
SCardReleaseContext(hCtx)

# ─── Output ───────────────────────────────────────────────────────────────────
Path('output').mkdir(exist_ok=True)
out = Path('output/experiment_04_block_structure.json')
out.write_text(json.dumps(results, indent=2), encoding='utf-8')

print("\n" + "=" * 70)
print("EXPERIMENT 04 SUMMARY")
print("=" * 70)
ok_blocks = [b for b, v in blocks.items() if 'hex' in v]
sw6981    = [b for b, v in blocks.items() if v.get('sw') == '6981']
sw6982    = [b for b, v in blocks.items() if v.get('sw') == '6982']
print(f"Readable blocks:  {ok_blocks}")
print(f"6981 (struct):    {sw6981}")
print(f"6982 (security):  {sw6982}")
print(f"Full dump: {out.resolve()}")
