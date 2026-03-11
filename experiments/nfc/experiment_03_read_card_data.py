#!/usr/bin/env python3
"""
EXPERIMENT 03: Full Card Data Dump
====================================
Protocol: Unknown Domain Protocol v1.0

CONFIRMED FROM EXPERIMENT 01:
  - UID: 54 D4 4C 4F 08 01 04 E0  (NXP ISO 15693 card)
  - SHARED connect works on Protocol T1 (2)
  - Session stays alive ~4.5 seconds before NfcCx deactivates
  - SCardBeginTransaction buys us a stable read window

HYPOTHESIS:
  The Keystone card contains data in ISO 15693 memory blocks.
  PCSC_Exchange__ApduGetData in SoulKeyServicePlugin reads this data.
  We can dump it using standard ISO 15693 READ SINGLE/MULTIPLE BLOCK APDUs.

WHAT THIS TESTS:
  1. What is the card's ATR? (identifies card type precisely)
  2. What ISO 15693 system info does the card report?
  3. What data is stored in each memory block?
  4. Is any block access-controlled (returns error)?
  5. Are there any custom/proprietary APDUs the card responds to?

REQUIRED:
  - Place Keystone card on reader immediately before running
  - We have ~4.5 second window — script connects fast

RUN:
  python experiments/nfc/experiment_03_read_card_data.py
"""

import sys
import time
import json
from pathlib import Path
from ctypes import byref

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'tools' / 'probe'))
from winscard_ctypes import (
    SCardEstablishContext, SCardReleaseContext, SCardConnectW, SCardDisconnect,
    SCardBeginTransaction, SCardEndTransaction, SCardGetAttrib,
    SCARD_SCOPE_USER, SCARD_SHARE_SHARED, SCARD_PROTOCOL_ANY,
    SCARD_LEAVE_CARD, SCARDCONTEXT, SCARDHANDLE, DWORD, LPBYTE,
    WinSCardError, check, list_readers, transmit, bytes_to_hex
)
import ctypes

# ─── APDU library ─────────────────────────────────────────────────────────────

# Standard PC/SC pseudo-APDUs for ISO 15693 via NfcCx
GET_UID         = [0xFF, 0xCA, 0x00, 0x00, 0x00]
GET_ATR         = [0xFF, 0xCA, 0x01, 0x00, 0x00]   # ATS

# ISO 15693 READ SINGLE BLOCK via PC/SC wrapper
# FF B0 00 <block> <length>
def read_block(block_num: int, length: int = 4) -> list[int]:
    return [0xFF, 0xB0, 0x00, block_num, length]

# ISO 15693 READ MULTIPLE BLOCKS
# FF B0 01 <first_block> <num_blocks * block_size>   -- some readers
def read_multi(first_block: int, count: int, block_size: int = 4) -> list[int]:
    return [0xFF, 0xB0, 0x01, first_block, count * block_size]

# GET SYSTEM INFORMATION (ISO 15693 command 0x2B via direct command)
# FF 30 00 00 00  -- some PC/SC stacks
GET_SYSTEM_INFO = [0xFF, 0x30, 0x00, 0x00, 0x00]

# NXP-specific: GET_MULTIPLE_BLOCK_SECURITY_STATUS
GET_BLOCK_SEC   = [0xFF, 0x36, 0x00, 0x00, 0x00]

# Try raw ISO 7816 SELECT (in case card has a file system)
SELECT_AID      = [0x00, 0xA4, 0x04, 0x00, 0x00]            # SELECT by AID (no AID = select MF)
SELECT_MF       = [0x00, 0xA4, 0x00, 0x00, 0x00]            # SELECT master file

# NXP ICODE SLI specific commands (ISO 15693 custom)
# These go via InCommunicateThru if PN532, but via direct APDU on NfcCx
ICODE_GET_SYS   = [0x02, 0x2B]          # flags=0x02 + GET_SYSTEM_INFORMATION

# READ BINARY for memory cards
def read_binary(offset: int, length: int) -> list[int]:
    return [0x00, 0xB0, (offset >> 8) & 0xFF, offset & 0xFF, length]

# ─── ATR attribute code ───────────────────────────────────────────────────────
SCARD_ATTR_ATR_STRING = 0x00090303


def decode_uid(uid_bytes: list[int]) -> dict:
    """Decode ISO 15693 UID."""
    if len(uid_bytes) != 8:
        return {'raw': bytes_to_hex(uid_bytes), 'note': f'unexpected length {len(uid_bytes)}'}

    mfr_codes = {
        0x01: 'Motorola', 0x02: 'STMicro', 0x03: 'Hitachi',
        0x04: 'NXP', 0x05: 'Infineon', 0x07: 'Texas Instruments',
        0x08: 'Fujitsu', 0x16: 'EM Microelectronic',
    }
    is_iso15693 = uid_bytes[7] == 0xE0
    mfr_code    = uid_bytes[6]
    mfr_name    = mfr_codes.get(mfr_code, f'Unknown(0x{mfr_code:02X})')
    serial      = uid_bytes[:6]

    return {
        'raw_lsb_first': bytes_to_hex(uid_bytes),
        'msb_first':     bytes_to_hex(reversed(uid_bytes)),
        'is_iso15693':   is_iso15693,
        'manufacturer':  mfr_name,
        'mfr_code':      f'0x{mfr_code:02X}',
        'serial':        bytes_to_hex(serial),
    }


def get_atr(hCard, proto: int) -> str:
    """Get ATR via SCardGetAttrib."""
    buf = (ctypes.c_ubyte * 36)()
    buflen = DWORD(36)
    rv = SCardGetAttrib(hCard, SCARD_ATTR_ATR_STRING, buf, byref(buflen))
    if rv == 0 and buflen.value > 0:
        return bytes_to_hex(bytes(buf[:buflen.value]))
    return f'failed: 0x{rv & 0xFFFFFFFF:08X}'


print("=" * 70)
print("EXPERIMENT 03: Full Card Data Dump")
print("=" * 70)
print("Place Keystone card on reader NOW — connecting immediately...\n")

hCtx = SCARDCONTEXT()
check(SCardEstablishContext(SCARD_SCOPE_USER, None, None, byref(hCtx)))
reader = list_readers(hCtx)[0]

# Connect fast
hCard = SCARDHANDLE()
dwProto = DWORD()
rv = SCardConnectW(hCtx, reader, SCARD_SHARE_SHARED, SCARD_PROTOCOL_ANY,
                   byref(hCard), byref(dwProto))
if rv != 0:
    print(f"Connect FAILED: 0x{rv & 0xFFFFFFFF:08X}")
    print("Did you place the card? Remove and replace it, then re-run.")
    SCardReleaseContext(hCtx)
    sys.exit(1)

print(f"Connected. Protocol: {dwProto.value} (T{'0' if dwProto.value==1 else '1'})")
SCardBeginTransaction(hCard)

results = {'uid': None, 'atr': None, 'blocks': {}, 'apdu_probe': {}}

# ─── Step 1: UID ──────────────────────────────────────────────────────────────
print("\n[1] Reading UID...")
try:
    data, sw1, sw2 = transmit(hCard, dwProto.value, GET_UID)
    uid_info = decode_uid(list(data))
    results['uid'] = uid_info
    print(f"    UID (LSB first): {uid_info['raw_lsb_first']}")
    print(f"    UID (MSB first): {uid_info['msb_first']}")
    print(f"    ISO 15693:       {uid_info['is_iso15693']}")
    print(f"    Manufacturer:    {uid_info['manufacturer']}")
    print(f"    Serial:          {uid_info['serial']}")
except WinSCardError as e:
    print(f"    FAILED: {e}")

# ─── Step 2: ATR ──────────────────────────────────────────────────────────────
print("\n[2] Reading ATR...")
atr = get_atr(hCard, dwProto.value)
results['atr'] = atr
print(f"    ATR: {atr}")

# ─── Step 3: Memory blocks ────────────────────────────────────────────────────
print("\n[3] Reading memory blocks (ISO 15693 READ SINGLE BLOCK)...")
consecutive_errors = 0
for block in range(64):
    try:
        data, sw1, sw2 = transmit(hCard, dwProto.value, read_block(block))
        if sw1 == 0x90:
            hex_data = bytes_to_hex(data)
            ascii_data = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
            results['blocks'][block] = {'hex': hex_data, 'ascii': ascii_data, 'sw': f'{sw1:02X}{sw2:02X}'}
            print(f"    Block {block:3d}: {hex_data}  |{ascii_data}|")
            consecutive_errors = 0
        elif sw1 == 0x6A and sw2 == 0x82:
            print(f"    Block {block:3d}: NOT FOUND (end of memory)")
            break
        else:
            results['blocks'][block] = {'sw': f'{sw1:02X}{sw2:02X}', 'error': 'non-success SW'}
            print(f"    Block {block:3d}: SW={sw1:02X}{sw2:02X}")
            consecutive_errors += 1
    except WinSCardError as e:
        results['blocks'][block] = {'error': str(e)}
        print(f"    Block {block:3d}: {e}")
        consecutive_errors += 1
    if consecutive_errors >= 3:
        print(f"    3 consecutive errors, stopping at block {block}")
        break

# ─── Step 4: Probe other APDUs ────────────────────────────────────────────────
print("\n[4] Probing additional APDUs...")
probe_apdus = {
    'GET_ATS':          GET_ATR,
    'GET_SYSTEM_INFO':  GET_SYSTEM_INFO,
    'GET_BLOCK_SEC':    GET_BLOCK_SEC,
    'SELECT_MF':        SELECT_MF,
    'READ_BINARY_0':    read_binary(0, 16),
    'SELECT_AID_empty': SELECT_AID,
    'READ_MULTI_0_4':   read_multi(0, 4),
}

for name, apdu in probe_apdus.items():
    try:
        data, sw1, sw2 = transmit(hCard, dwProto.value, apdu)
        hex_r = bytes_to_hex(data) if data else '(empty)'
        results['apdu_probe'][name] = {'response': hex_r, 'sw': f'{sw1:02X}{sw2:02X}'}
        flag = '[OK]' if sw1 == 0x90 else '[--]'
        print(f"    {flag} {name}: {hex_r}  SW={sw1:02X}{sw2:02X}")
    except WinSCardError as e:
        results['apdu_probe'][name] = {'error': str(e)}
        print(f"    [!!] {name}: {e}")

SCardEndTransaction(hCard, SCARD_LEAVE_CARD)
SCardDisconnect(hCard, SCARD_LEAVE_CARD)
SCardReleaseContext(hCtx)

# ─── Output ───────────────────────────────────────────────────────────────────
Path('output').mkdir(exist_ok=True)
out_path = Path('output/experiment_03_card_dump.json')
out_path.write_text(json.dumps(results, indent=2), encoding='utf-8')

print("\n" + "=" * 70)
print("EXPERIMENT 03 SUMMARY")
print("=" * 70)
uid = results.get('uid', {})
print(f"Card:         {uid.get('manufacturer', '?')} ISO 15693")
print(f"UID:          {uid.get('msb_first', '?')}")
print(f"ATR:          {results.get('atr', '?')}")
blocks_ok = [b for b, v in results['blocks'].items() if 'hex' in v]
print(f"Blocks read:  {len(blocks_ok)} blocks")
if blocks_ok:
    print(f"Block range:  0 to {max(blocks_ok)}")
probes_ok = [n for n, v in results['apdu_probe'].items() if v.get('sw','')=='9000']
print(f"APDUs OK:     {probes_ok}")
print(f"\nFull dump:    {out_path.resolve()}")
