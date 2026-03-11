#!/usr/bin/env python3
"""
card_probe.py — Live NFC/Smart Card interrogation tool
Connects to every available reader, dumps everything about the card:
  - ATR (Answer To Reset)
  - UID
  - ISO 15693 system information
  - All readable memory blocks
  - ACR122U / PN532 firmware version
  - Reader capabilities

Usage:
    python card_probe.py
    python card_probe.py --reader "ACS ACR122U 00"
    python card_probe.py --output probe_results.json
    python card_probe.py --loop          (keep reading, wait for card)
"""

import sys
import json
import time
import argparse
import ctypes
from pathlib import Path
from datetime import datetime
from ctypes import byref, POINTER, c_ubyte

sys.path.insert(0, str(Path(__file__).parent))
from winscard_ctypes import (
    SCardEstablishContext, SCardReleaseContext, SCardConnectW, SCardDisconnect,
    SCardBeginTransaction, SCardEndTransaction, SCardGetStatusChangeW,
    SCARD_SCOPE_USER, SCARD_SHARE_SHARED, SCARD_SHARE_DIRECT,
    SCARD_PROTOCOL_UNDEFINED, SCARD_PROTOCOL_ANY, SCARD_PROTOCOL_T0, SCARD_PROTOCOL_T1,
    SCARD_LEAVE_CARD, SCARD_STATE_UNAWARE, SCARD_STATE_PRESENT,
    SCARD_STATE_CHANGED, SCARD_STATE_EMPTY, IOCTL_CCID_ESCAPE,
    SCARDCONTEXT, SCARDHANDLE, DWORD, SCARD_READERSTATE, INFINITE,
    WinSCardError, check, list_readers, transmit, control, bytes_to_hex
)


# ─── APDU definitions ────────────────────────────────────────────────────────

GET_UID           = [0xFF, 0xCA, 0x00, 0x00, 0x00]
GET_ATS           = [0xFF, 0xCA, 0x01, 0x00, 0x00]
GET_FIRMWARE      = [0xFF, 0x00, 0x48, 0x00, 0x00]  # ACR122U firmware version

# PN532 commands via escape (ACR122U)
PN532_SAM_CFG     = [0xFF, 0x00, 0x00, 0x00, 0x03, 0xD4, 0x14, 0x01]
PN532_FW_VERSION  = [0xFF, 0x00, 0x00, 0x00, 0x02, 0xD4, 0x02]
PN532_RF_ON       = [0xFF, 0x00, 0x00, 0x00, 0x04, 0xD4, 0x32, 0x01, 0x01]
PN532_RF_OFF      = [0xFF, 0x00, 0x00, 0x00, 0x04, 0xD4, 0x32, 0x01, 0x00]

# Detect ISO 15693 card
PN532_DETECT_15693 = [0xFF, 0x00, 0x00, 0x00, 0x04, 0xD4, 0x4A, 0x01, 0x06]

# ISO 15693 commands via InCommunicateThru (PN532)
# Flags: 0x26 = high data rate + inventory + 16 slots
ISO15693_INVENTORY       = [0xFF, 0x00, 0x00, 0x00, 0x05, 0xD4, 0x42, 0x26, 0x01, 0x00]
ISO15693_GET_SYS_INFO    = [0xFF, 0x00, 0x00, 0x00, 0x04, 0xD4, 0x42, 0x02, 0x2B]  # addressed: add UID after

# Read block N: flags=0x02 (high rate, not addressed), cmd=0x20, block_num
def iso15693_read_block(block: int) -> list[int]:
    return [0xFF, 0x00, 0x00, 0x00, 0x05, 0xD4, 0x42, 0x02, 0x20, block]

def iso15693_read_block_addressed(uid_bytes: list[int], block: int) -> list[int]:
    # flags=0x22 (high rate + addressed)
    cmd = [0xFF, 0x00, 0x00, 0x00] + [0x0D] + [0xD4, 0x42] + [0x22, 0x20] + uid_bytes + [block]
    cmd[4] = len(cmd) - 5
    return cmd


# ─── Probe functions ─────────────────────────────────────────────────────────

def probe_reader_firmware(hCard: SCARDHANDLE, result: dict):
    """Get ACR122U firmware version and PN532 info."""
    print("  [*] Getting firmware version...")
    try:
        data, sw1, sw2 = transmit(hCard, SCARD_PROTOCOL_T1, GET_FIRMWARE)
        fw = bytes(data).decode('ascii', errors='replace').strip()
        result['firmware'] = {'raw': bytes_to_hex(data), 'decoded': fw, 'sw': f'{sw1:02X}{sw2:02X}'}
        print(f"  [+] Firmware: {fw}")
    except Exception as e:
        result['firmware'] = {'error': str(e)}
        print(f"  [-] Firmware read failed: {e}")

    try:
        resp = control(hCard, IOCTL_CCID_ESCAPE, PN532_FW_VERSION)
        result['pn532_version'] = bytes_to_hex(resp)
        # D5 03 IC Ver Rev Support
        if len(resp) >= 5 and resp[0] == 0xD5:
            ic  = resp[2]
            ver = resp[3]
            rev = resp[4]
            sup = resp[5] if len(resp) > 5 else 0
            result['pn532_decoded'] = {
                'IC': f'0x{ic:02X} ({"PN532" if ic == 7 else "unknown"})',
                'Version': ver,
                'Revision': rev,
                'Support': bin(sup),
            }
            print(f"  [+] PN532: IC=0x{ic:02X} v{ver}.{rev}")
    except Exception as e:
        result['pn532_version'] = {'error': str(e)}


def probe_card_uid(hCard: SCARDHANDLE, proto: int, result: dict):
    """Get card UID via pseudo-APDU."""
    print("  [*] Getting UID...")
    try:
        data, sw1, sw2 = transmit(hCard, proto, GET_UID)
        uid_hex = bytes_to_hex(data)
        result['uid'] = {
            'bytes': list(data),
            'hex': uid_hex,
            'length': len(data),
            'sw': f'{sw1:02X}{sw2:02X}',
        }
        if sw1 == 0x90:
            print(f"  [+] UID: {uid_hex} ({len(data)} bytes)")
            # Try to decode manufacturer from ISO 15693 UID
            if len(data) == 8 and data[-1] == 0xE0:
                mfr_code = data[-2]
                mfr = _manufacturer(mfr_code)
                result['uid']['manufacturer_code'] = f'0x{mfr_code:02X}'
                result['uid']['manufacturer'] = mfr
                print(f"  [+] Manufacturer: {mfr} (code 0x{mfr_code:02X})")
        else:
            print(f"  [-] UID failed: SW={sw1:02X}{sw2:02X}")
    except Exception as e:
        result['uid'] = {'error': str(e)}
        print(f"  [-] UID error: {e}")


def probe_ats(hCard: SCARDHANDLE, proto: int, result: dict):
    """Get ATS (Answer To Select) for ISO 14443A cards."""
    try:
        data, sw1, sw2 = transmit(hCard, proto, GET_ATS)
        if sw1 == 0x90:
            result['ats'] = {'hex': bytes_to_hex(data), 'sw': f'{sw1:02X}{sw2:02X}'}
            print(f"  [+] ATS: {bytes_to_hex(data)}")
        else:
            result['ats'] = None
    except Exception:
        result['ats'] = None


def probe_iso15693_via_pn532(hCard: SCARDHANDLE, result: dict):
    """
    Use PN532 escape commands to detect and read ISO 15693 card.
    This bypasses the PC/SC layer and talks directly to the PN532 chip.
    """
    print("  [*] Probing for ISO 15693 via PN532 escape...")
    iso15693 = {}

    # Configure SAM
    try:
        resp = control(hCard, IOCTL_CCID_ESCAPE, PN532_SAM_CFG)
        iso15693['sam_config'] = bytes_to_hex(resp)
    except Exception as e:
        iso15693['sam_config_error'] = str(e)

    # Turn RF on
    try:
        resp = control(hCard, IOCTL_CCID_ESCAPE, PN532_RF_ON)
        iso15693['rf_on'] = bytes_to_hex(resp)
    except Exception as e:
        iso15693['rf_on_error'] = str(e)

    # Detect ISO 15693 card
    try:
        resp = control(hCard, IOCTL_CCID_ESCAPE, PN532_DETECT_15693)
        iso15693['detect_raw'] = bytes_to_hex(resp)
        print(f"  [*] 15693 detect response: {bytes_to_hex(resp)}")

        # PN532 InListPassiveTarget response: D5 4B NbTg [target data]
        if len(resp) >= 3 and resp[0] == 0xD5 and resp[1] == 0x4B:
            nb_tg = resp[2]
            iso15693['targets_found'] = nb_tg
            if nb_tg > 0:
                print(f"  [+] ISO 15693: {nb_tg} target(s) found")
                iso15693['target_raw'] = bytes_to_hex(resp[3:])
            else:
                print("  [-] No ISO 15693 targets")
        else:
            print(f"  [?] Unexpected detect response: {bytes_to_hex(resp)}")
    except Exception as e:
        iso15693['detect_error'] = str(e)
        print(f"  [-] ISO 15693 detect error: {e}")

    # INVENTORY command
    try:
        resp = control(hCard, IOCTL_CCID_ESCAPE, ISO15693_INVENTORY)
        iso15693['inventory_raw'] = bytes_to_hex(resp)
        print(f"  [*] ISO 15693 INVENTORY: {bytes_to_hex(resp)}")

        # InCommunicateThru response: D5 43 status [data]
        if len(resp) >= 3 and resp[0] == 0xD5 and resp[1] == 0x43:
            status = resp[2]
            card_data = resp[3:]
            iso15693['inventory_status'] = f'0x{status:02X}'
            if status == 0x00 and len(card_data) >= 9:
                # Response flags (1B) + DSFID (1B) + UID (8B)
                flags = card_data[0]
                dsfid = card_data[1]
                uid   = list(card_data[2:10])
                uid_hex = ' '.join(f'{b:02X}' for b in uid)
                iso15693['card'] = {
                    'flags':  f'0x{flags:02X}',
                    'dsfid':  f'0x{dsfid:02X}',
                    'uid':    uid_hex,
                    'uid_bytes': uid,
                }
                print(f"  [+] ISO 15693 UID: {uid_hex}")
                print(f"  [+] DSFID: 0x{dsfid:02X}")

                # Try to read blocks
                _read_blocks_15693(hCard, uid, iso15693)
    except Exception as e:
        iso15693['inventory_error'] = str(e)

    result['iso15693'] = iso15693


def _read_blocks_15693(hCard: SCARDHANDLE, uid: list[int], iso15693: dict):
    """Read as many blocks as possible from ISO 15693 card."""
    print("  [*] Reading ISO 15693 blocks...")
    blocks = {}
    consecutive_errors = 0

    for block_num in range(64):  # most cards have 8-64 blocks
        try:
            cmd = iso15693_read_block_addressed(uid, block_num)
            resp = control(hCard, IOCTL_CCID_ESCAPE, cmd)

            if len(resp) >= 3 and resp[0] == 0xD5 and resp[1] == 0x43:
                status = resp[2]
                if status == 0x00:
                    block_data = resp[3:]
                    blocks[block_num] = bytes_to_hex(block_data)
                    print(f"  [+] Block {block_num:3d}: {bytes_to_hex(block_data)}")
                    consecutive_errors = 0
                else:
                    # status != 0 means card error (block not available, etc.)
                    print(f"  [-] Block {block_num:3d}: error status 0x{status:02X}")
                    consecutive_errors += 1
            else:
                consecutive_errors += 1

            if consecutive_errors >= 3:
                print(f"  [*] 3 consecutive errors at block {block_num}, stopping.")
                break

            time.sleep(0.02)  # small delay between block reads

        except Exception as e:
            blocks[block_num] = f'error: {e}'
            consecutive_errors += 1
            if consecutive_errors >= 3:
                break

    iso15693['blocks'] = blocks
    iso15693['blocks_read'] = len(blocks)
    print(f"  [+] Read {len(blocks)} blocks total")


def probe_card(hCtx: SCARDCONTEXT, reader: str) -> dict:
    """Full probe of a single reader/card. Returns structured result dict."""
    result = {
        'reader':    reader,
        'timestamp': datetime.now().isoformat(),
        'success':   False,
    }
    print(f"\n[PROBING] {reader}")

    hCard = SCARDHANDLE()
    dwProto = DWORD()

    # First: connect with SCARD_SHARE_DIRECT for escape commands
    rv = SCardConnectW(
        hCtx, reader,
        SCARD_SHARE_DIRECT, SCARD_PROTOCOL_UNDEFINED,
        byref(hCard), byref(dwProto)
    )

    if rv != 0:
        # Try shared mode
        rv = SCardConnectW(
            hCtx, reader,
            SCARD_SHARE_SHARED, SCARD_PROTOCOL_ANY,
            byref(hCard), byref(dwProto)
        )

    if rv != 0:
        result['error'] = f'SCardConnectW failed: 0x{rv & 0xFFFFFFFF:08X}'
        print(f"  [-] Connect failed: 0x{rv & 0xFFFFFFFF:08X}")
        return result

    proto = dwProto.value
    result['protocol'] = proto
    result['protocol_name'] = {0: 'UNDEFINED', 1: 'T0', 2: 'T1', 0x10000: 'RAW'}.get(proto, f'0x{proto:X}')
    print(f"  [*] Connected. Protocol: {result['protocol_name']}")

    try:
        # Firmware
        probe_reader_firmware(hCard, result)

        # If no card present, try to detect one
        if proto == 0:
            # Direct mode — try ISO 15693 via PN532 escape
            probe_iso15693_via_pn532(hCard, result)
        else:
            SCardBeginTransaction(hCard)
            try:
                probe_card_uid(hCard, proto, result)
                probe_ats(hCard, proto, result)

                # Also try ISO 15693 path if UID looks like ISO 15693
                uid_data = result.get('uid', {})
                if uid_data.get('length') == 8:
                    probe_iso15693_via_pn532(hCard, result)
            finally:
                SCardEndTransaction(hCard, SCARD_LEAVE_CARD)

        result['success'] = True

    except WinSCardError as e:
        result['error'] = str(e)
        print(f"  [!] Error: {e}")
    except Exception as e:
        result['error'] = str(e)
        print(f"  [!] Unexpected error: {e}")
    finally:
        SCardDisconnect(hCard, SCARD_LEAVE_CARD)  # ALWAYS leave card powered

    return result


def wait_for_card(hCtx: SCARDCONTEXT, reader: str, timeout_ms: int = INFINITE) -> bool:
    """Block until a card is inserted into the reader."""
    rs = SCARD_READERSTATE()
    rs.szReader = reader
    rs.dwCurrentState = SCARD_STATE_UNAWARE

    print(f"\n[WAITING] for card in: {reader}")
    while True:
        rv = SCardGetStatusChangeW(hCtx, timeout_ms, byref(rs), 1)
        if rv != 0:
            return False
        if rs.dwEventState & SCARD_STATE_PRESENT:
            print(f"  [+] Card detected!")
            return True
        if rs.dwEventState & SCARD_STATE_EMPTY:
            print("  [-] No card. Waiting...")
        rs.dwCurrentState = rs.dwEventState


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Live NFC card probe')
    parser.add_argument('--reader', '-r', help='Reader name (default: first available)')
    parser.add_argument('--output', '-o', default='probe_results.json')
    parser.add_argument('--loop', '-l', action='store_true', help='Keep probing, wait for card')
    parser.add_argument('--quiet', '-q', action='store_true')
    args = parser.parse_args()

    hCtx = SCARDCONTEXT()
    check(SCardEstablishContext(SCARD_SCOPE_USER, None, None, byref(hCtx)), 'EstablishContext')

    try:
        readers = list_readers(hCtx)
        if not readers:
            print("[ERROR] No readers found. Is the reader plugged in?")
            sys.exit(1)

        print(f"[*] Readers found: {readers}")
        reader = args.reader or readers[0]

        all_results = []

        if args.loop:
            print("[*] Loop mode — press Ctrl+C to stop")
            while True:
                wait_for_card(hCtx, reader)
                result = probe_card(hCtx, reader)
                all_results.append(result)
                _save(all_results, args.output)
                time.sleep(0.5)
        else:
            result = probe_card(hCtx, reader)
            all_results.append(result)
            _save(all_results, args.output)
            _print_summary(result)

    except KeyboardInterrupt:
        print("\n[*] Stopped.")
    finally:
        SCardReleaseContext(hCtx)


def _save(results: list, path: str):
    Path(path).write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f"\n[OK] Results saved to: {Path(path).resolve()}")


def _print_summary(result: dict):
    print("\n" + "="*55)
    print("PROBE SUMMARY")
    print("="*55)
    print(f"Reader:    {result.get('reader')}")
    print(f"Success:   {result.get('success')}")
    if 'firmware' in result:
        print(f"Firmware:  {result['firmware'].get('decoded', result['firmware'])}")
    if 'uid' in result:
        u = result['uid']
        print(f"UID:       {u.get('hex')}  ({u.get('length')} bytes)")
        if 'manufacturer' in u:
            print(f"Vendor:    {u['manufacturer']}")
    if 'iso15693' in result:
        iso = result['iso15693']
        if 'card' in iso:
            print(f"ISO 15693 UID: {iso['card']['uid']}")
            print(f"Blocks read:   {iso.get('blocks_read', 0)}")
            if 'blocks' in iso:
                print("\nMemory blocks:")
                for b, d in iso['blocks'].items():
                    print(f"  [{b:3d}] {d}")
    if 'error' in result:
        print(f"Error:     {result['error']}")
    print("="*55)


def _manufacturer(code: int) -> str:
    TABLE = {
        0x01: 'Motorola', 0x02: 'STMicroelectronics', 0x03: 'Hitachi',
        0x04: 'NXP (Philips)', 0x05: 'Infineon', 0x07: 'Texas Instruments',
        0x08: 'Fujitsu', 0x16: 'EM Microelectronic',
    }
    return TABLE.get(code, f'Unknown (0x{code:02X})')


if __name__ == '__main__':
    main()
