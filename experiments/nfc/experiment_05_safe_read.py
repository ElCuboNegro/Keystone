#!/usr/bin/env python3
"""
EXPERIMENT 05: Safe Read — Avoid Session-Killing Block 1
=========================================================
Protocol: Unknown Domain Protocol v1.0

CRITICAL FINDING FROM EXPERIMENT 04:
  Reading block 1 (FF B0 00 01 04) returns SW=6981, and NfcCx IMMEDIATELY
  drops the RF session after that 6981 response. The card is generating an
  ISO 15693 protocol-level error, causing NfcCx to deactivate.

  Session timeline:
    t=0.0s  Connect OK
    t=0.1s  Block 0 -> 01 01 01 01 (SW=9000)
    t=0.2s  Block 1 -> SW=6981
    t=0.2s  NfcCx drops connection immediately
    t=0.3s+ All subsequent transmits -> SCARD_W_REMOVED_CARD

  Compare: UID reads (FF CA) do NOT kill the session — got 10 reads × 0.5s
  in experiment 01. The problem is specifically block 1's 6981 error.

REVISED STRATEGY:
  1. GET_SYSTEM_INFORMATION first (before any block read) — this tells us:
     - Exact block count (so we know which blocks exist)
     - Block size in bytes
     - DSFID (Data Storage Format Identifier)
     - AFI (Application Family Identifier)
     - IC reference (confirms chip type)
  2. UID read (always safe)
  3. Block 0 only (confirmed safe)
  4. Probe ALL other APDUs except FF B0 00 01 XX
  5. Blocks 2, 3, 4... (skipping block 1) if session survives

HYPOTHESES ON WHY BLOCK 1 KILLS SESSION:
  A. Card has only 1 user block (block 0); block 1 doesn't exist.
     NXP ICODE SLI-L has only 2 blocks but SLI-L block 1 should still read.
  B. Block 1 requires AES authentication (ICODE DNA card).
     The card sends an ISO 15693 error code that NfcCx interprets as fatal.
  C. Block 1 has AFI/DSFID protection enabled via password command.
  D. The card is a custom variant where block 1 is a system/config block.

RUN:
  python experiments/nfc/experiment_05_safe_read.py
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

# ─── APDU library ─────────────────────────────────────────────────────────────

GET_UID          = [0xFF, 0xCA, 0x00, 0x00, 0x00]
GET_SYS_INFO_30  = [0xFF, 0x30, 0x00, 0x00, 0x00]   # ISO 15693 GET SYSTEM INFO
GET_SYS_INFO_2B  = [0xFF, 0x2B, 0x00, 0x00, 0x00]   # alternate
GET_BLOCK_SEC    = [0xFF, 0x36, 0x00, 0x00, 0x00]   # GET MULTIPLE BLOCK SECURITY STATUS
READ_MULTI       = [0xFF, 0xB3, 0x00, 0x00, 0x04]   # READ MULTIPLE BLOCKS (4 blocks)

def read_block(block: int, le: int = 4) -> list[int]:
    return [0xFF, 0xB0, 0x00, block, le]

def read_binary(offset: int, length: int) -> list[int]:
    return [0x00, 0xB0, (offset >> 8) & 0xFF, offset & 0xFF, length]

# ─── Connect ──────────────────────────────────────────────────────────────────

print("=" * 70)
print("EXPERIMENT 05: Safe Read (avoid block 1 session killer)")
print("=" * 70)
print("Place card on reader NOW...\n")

hCtx = SCARDCONTEXT()
check(SCardEstablishContext(SCARD_SCOPE_USER, None, None, byref(hCtx)))
reader = list_readers(hCtx)[0]

hCard = SCARDHANDLE()
dwProto = DWORD()
rv = SCardConnectW(hCtx, reader, SCARD_SHARE_SHARED, SCARD_PROTOCOL_ANY,
                   byref(hCard), byref(dwProto))
if rv != 0:
    print(f"Connect FAILED: 0x{rv & 0xFFFFFFFF:08X}")
    SCardReleaseContext(hCtx)
    sys.exit(1)

print(f"Connected. Protocol: {dwProto.value}")
SCardBeginTransaction(hCard)
t0 = time.monotonic()

results = {}

def tx(label: str, apdu: list[int]) -> tuple | None:
    """Transmit and print. Returns (data, sw1, sw2) or None on error."""
    try:
        data, sw1, sw2 = transmit(hCard, dwProto.value, apdu)
        h = bytes_to_hex(data) if data else '(empty)'
        flag = '[OK]' if sw1 == 0x90 else '[--]'
        elapsed = time.monotonic() - t0
        print(f"  {flag} {label}: {h}  SW={sw1:02X}{sw2:02X}  (t={elapsed:.2f}s)")
        return data, sw1, sw2
    except WinSCardError as e:
        elapsed = time.monotonic() - t0
        print(f"  [!!] {label}: {e}  (t={elapsed:.2f}s)")
        return None


# ─── Step 1: GET_SYSTEM_INFORMATION (MUST be first) ───────────────────────────
print("\n[1] GET_SYSTEM_INFORMATION (before any block read)...")
sys_info_data = None
for name, apdu in [('FF30', GET_SYS_INFO_30), ('FF2B', GET_SYS_INFO_2B)]:
    r = tx(name, apdu)
    if r:
        data, sw1, sw2 = r
        results[f'sys_info_{name}'] = {'sw': f'{sw1:02X}{sw2:02X}', 'data': bytes_to_hex(data) if data else ''}
        if sw1 == 0x90 and data:
            sys_info_data = data
            break

if sys_info_data:
    # Decode ISO 15693 GET_SYSTEM_INFORMATION response
    # Byte 0: info flags
    # Bytes 1-8: UID (LSB first)
    # (if DSFID flag): DSFID byte
    # (if AFI flag): AFI byte
    # (if MEM_SIZE flag): 2 bytes: block_count(1) + block_size(1)
    # (if IC_REF flag): 1 byte
    flags = sys_info_data[0] if len(sys_info_data) > 0 else 0
    print(f"\n  System Info decoded:")
    print(f"  Info flags: 0x{flags:02X}")
    idx = 9  # skip flags(1) + UID(8)
    if flags & 0x01:  # DSFID present
        if idx < len(sys_info_data):
            print(f"  DSFID: 0x{sys_info_data[idx]:02X}")
            idx += 1
    if flags & 0x02:  # AFI present
        if idx < len(sys_info_data):
            print(f"  AFI:   0x{sys_info_data[idx]:02X}")
            idx += 1
    if flags & 0x04:  # Memory size present
        if idx + 1 < len(sys_info_data):
            block_count = sys_info_data[idx] + 1  # value is max block address
            block_size  = (sys_info_data[idx+1] & 0x1F) + 1  # bits 4:0
            print(f"  Blocks: {block_count} blocks x {block_size} bytes = {block_count*block_size} bytes total")
            results['memory'] = {'block_count': block_count, 'block_size': block_size}
            idx += 2
    if flags & 0x08:  # IC reference present
        if idx < len(sys_info_data):
            print(f"  IC ref: 0x{sys_info_data[idx]:02X}")


# ─── Step 2: UID read ─────────────────────────────────────────────────────────
print("\n[2] UID read...")
tx('GET_UID', GET_UID)


# ─── Step 3: Block 0 (safe) ───────────────────────────────────────────────────
print("\n[3] Block 0 (confirmed safe)...")
r = tx('Block 0 Le=4', read_block(0, 4))
if r:
    data, sw1, sw2 = r
    if sw1 == 0x90:
        results['block_0'] = bytes_to_hex(data)


# ─── Step 4: Blocks 2-20 (skip block 1) ──────────────────────────────────────
print("\n[4] Blocks 2-20 (skipping block 1)...")
for b in range(2, 21):
    r = tx(f'Block {b:2d}', read_block(b))
    if r is None:
        break
    data, sw1, sw2 = r
    if sw1 == 0x90:
        results[f'block_{b}'] = bytes_to_hex(data)
    elif f'{sw1:02X}{sw2:02X}' == '6A82':
        print(f"  End of memory at block {b}")
        break


# ─── Step 5: GET MULTIPLE BLOCK SECURITY STATUS ───────────────────────────────
print("\n[5] GET_MULTIPLE_BLOCK_SECURITY_STATUS...")
r = tx('BlockSec', GET_BLOCK_SEC)
if r:
    data, sw1, sw2 = r
    if sw1 == 0x90 and data:
        results['block_security'] = bytes_to_hex(data)
        locked = [i for i, b in enumerate(data) if b & 0x01]
        if locked:
            print(f"  Locked blocks: {locked}")
        else:
            print(f"  All blocks unlocked (or status not supported)")


# ─── Step 6: READ_MULTIPLE_BLOCKS from block 0 ───────────────────────────────
print("\n[6] READ_MULTIPLE_BLOCKS (FF B3)...")
tx('ReadMulti_4', [0xFF, 0xB3, 0x00, 0x00, 0x04])
tx('ReadMulti_1', [0xFF, 0xB3, 0x00, 0x00, 0x01])


# ─── Step 7: READ_BINARY (treats card as flat memory) ────────────────────────
print("\n[7] READ_BINARY (00 B0, flat memory view)...")
for off in [0, 4, 8, 16]:
    tx(f'ReadBin@{off}', read_binary(off, 4))


# ─── Step 8: SELECT / file system probe ───────────────────────────────────────
print("\n[8] File system probe...")
tx('SELECT_MF',    [0x00, 0xA4, 0x00, 0x00, 0x00])
tx('SELECT_AID',   [0x00, 0xA4, 0x04, 0x00, 0x00])
tx('GET_DATA_all', [0xFF, 0xCA, 0xFF, 0x00, 0x00])  # get ATS/extended data


print(f"\n  Session alive: {time.monotonic()-t0:.2f}s total")

SCardEndTransaction(hCard, SCARD_LEAVE_CARD)
SCardDisconnect(hCard, SCARD_LEAVE_CARD)
SCardReleaseContext(hCtx)

# ─── Output ───────────────────────────────────────────────────────────────────
Path('output').mkdir(exist_ok=True)
out = Path('output/experiment_05_safe_read.json')
out.write_text(json.dumps(results, indent=2), encoding='utf-8')

print("\n" + "=" * 70)
print("EXPERIMENT 05 SUMMARY")
print("=" * 70)
if 'memory' in results:
    m = results['memory']
    print(f"Card memory: {m['block_count']} blocks x {m['block_size']} bytes = {m['block_count']*m['block_size']} bytes")
readable = {k: v for k, v in results.items() if k.startswith('block_')}
for k, v in sorted(readable.items()):
    print(f"  {k}: {v}")
print(f"\nFull dump: {out.resolve()}")
