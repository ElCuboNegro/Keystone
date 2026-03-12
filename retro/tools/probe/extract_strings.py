#!/usr/bin/env python3
"""Extract and categorize strings from NFC DLLs."""
import re, sys
from pathlib import Path

DLL_PATHS = [
    r'C:\Windows\System32\drivers\UMDF\NfcCx.dll',
    r'C:\Windows\System32\drivers\UMDF\NxpNfcClientDriver.dll',
    r'C:\Windows\System32\NfcRadioMedia.dll',
    r'C:\Windows\System32\NFCProvisioningPlugin.dll',
]

CATEGORIES = {
    'source_paths':   lambda s: '.cpp' in s or '.h:' in s or ('nfc' in s.lower() and ('/' in s or chr(92) in s)),
    'protocols':      lambda s: any(k in s for k in ['TypeA','TypeB','TypeF','TypeV','NFC-A','NFC-B','NFC-V','NFC-F','T1T','T2T','T3T','T4T','T5T','LLCP','SNEP','HCE','ISO 15693','ISO14443','15693','14443','Felica','Jewel','Barcode','NDEF','NCI']),
    'error_messages': lambda s: any(k in s for k in ['Failed','Error','error','Invalid','failed','cannot','Cannot','Timeout','timeout']),
    'device_ops':     lambda s: any(k in s for k in ['PresenceCheck','Deactivate','Activate','Discover','Listen','Poll','TagDiscover','ReaderMode','WriterMode','P2P']),
    'card_ifd':       lambda s: any(k in s for k in ['IFD','SCARD','SmartCard','SCard','smartcard','ATR','AID','APDU']),
    'ioctl':          lambda s: 'IOCTL' in s or 'DeviceIo' in s,
}

for dll_path in DLL_PATHS:
    p = Path(dll_path)
    if not p.exists():
        print(f'NOT FOUND: {dll_path}')
        continue

    raw = p.read_bytes()
    ascii_strings = [m.group(0).decode('ascii', 'replace') for m in re.finditer(rb'[\x20-\x7E]{8,}', raw)]

    print(f'\n{"="*60}')
    print(f'{p.name}  ({len(ascii_strings)} strings)')
    print('='*60)

    for cat, fn in CATEGORIES.items():
        matches = [s for s in ascii_strings if fn(s)]
        if matches:
            print(f'\n  [{cat}] ({len(matches)})')
            for s in matches[:15]:
                print(f'    {s}')
