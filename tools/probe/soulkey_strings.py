#!/usr/bin/env python3
"""Deep string extraction from SoulKeyServicePlugin.dll"""
import re
from pathlib import Path

DLL = Path(r'C:\Program Files\ASUS\Armoury Crate Service\SoulKeyServicePlugin\ArmouryCrate.SoulKeyServicePlugin.dll')
raw = DLL.read_bytes()
strings = [m.group(0).decode('ascii', 'replace') for m in re.finditer(rb'[\x20-\x7E]{6,}', raw)]

# Also scan for UTF-16 strings (common in .NET / Win32)
utf16 = [m.group(0).decode('utf-16-le', 'replace').strip() for m in re.finditer(rb'(?:[\x20-\x7E]\x00){5,}', raw)]

cats = {
    'scard_calls':  [s for s in strings if 'SCard' in s or 'SCARD' in s],
    'card_data':    [s for s in strings if any(k in s for k in ['UID','ATR','block','Block','ISO','NFC','nfc','SoulKey','soulkey','Keystone','keystone'])],
    'source_paths': [s for s in strings if ('.cpp' in s or '.h' in s) and len(s) > 10],
    'hid_strings':  [s for s in strings if 'hid' in s.lower() and len(s) > 4],
    'timing':       [s for s in strings if any(k in s.lower() for k in ['timeout','sleep','delay','interval','millisec','second'])],
    'apdu_related': [s for s in strings if any(k in s for k in ['APDU','apdu','transmit','Transmit','0xFF','0xCA','0xB0','dispatch'])],
    'device_paths': [s for s in strings if s.startswith(r'\\') or 'GUID' in s or 'VID_' in s or 'PID_' in s or 'USB' in s],
    'utf16_strings': [s for s in utf16 if len(s.strip()) > 4 and any(k in s for k in ['NFC','Card','Soul','Key','Reader','USB','HID','SCard'])],
}

for cat, items in cats.items():
    unique = list(dict.fromkeys(items))
    if unique:
        print(f'\n[{cat}] ({len(unique)}):')
        for s in unique[:25]:
            print(f'  {repr(s)}')

print(f'\n[total strings] ASCII: {len(strings)}, UTF-16: {len(utf16)}')
