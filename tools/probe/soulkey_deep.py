#!/usr/bin/env python3
"""
Full reconstruction of SoulKeyServicePlugin call flow from UTF-16 strings.
Extracts ALL log messages to understand exact sequence of operations.
"""
import re, json
from pathlib import Path
from datetime import datetime

DLL = Path(r'C:\Program Files\ASUS\Armoury Crate Service\SoulKeyServicePlugin\ArmouryCrate.SoulKeyServicePlugin.dll')
raw = DLL.read_bytes()

# Extract ALL UTF-16LE strings of any meaningful length
utf16 = []
for m in re.finditer(rb'(?:[\x09\x0A\x0D\x20-\x7E]\x00){4,}', raw):
    try:
        s = m.group(0).decode('utf-16-le', 'replace').strip()
        if len(s.strip()) >= 4:
            utf16.append({'text': s, 'offset': hex(m.start())})
    except Exception:
        pass

# Also get all ASCII strings
ascii_s = [m.group(0).decode('ascii', 'replace') for m in re.finditer(rb'[\x20-\x7E]{5,}', raw)]

print('=' * 70)
print(f'SoulKeyServicePlugin.dll — Full String Reconstruction')
print(f'File: {DLL}')
print(f'Size: {DLL.stat().st_size:,} bytes')
print(f'ASCII strings: {len(ascii_s)}, UTF-16 strings: {len(utf16)}')
print('=' * 70)

# Group UTF-16 strings by theme
themes = {
    'SCard operations':   lambda s: 'SCard' in s or 'scard' in s.lower(),
    'HID operations':     lambda s: 'HID' in s or 'hid_' in s,
    'Card data / events': lambda s: any(k in s for k in ['SoulKey','UID','uid','ATR','Card','Event','Status','Type','Support','Keystone','key','Key']),
    'Error handling':     lambda s: any(k in s for k in ['Error','error','fail','Fail','invalid','Invalid','timeout','Timeout']),
    'Device / reader':    lambda s: any(k in s for k in ['Reader','reader','Device','device','USB','usb','connect','Connect','disconnect']),
    'Data fields':        lambda s: any(k in s for k in ['Value','value','Data','data','result','Result','response','Request','send','Send','receive','Receive']),
    'Source / debug':     lambda s: '.cpp' in s or '.h' in s or 'Plugin' in s or 'Service' in s or 'pdb' in s,
}

findings = {}
all_shown = set()

for theme, fn in themes.items():
    matches = [e for e in utf16 if fn(e['text']) and e['text'] not in all_shown]
    if matches:
        findings[theme] = matches
        for e in matches:
            all_shown.add(e['text'])
        print(f'\n[{theme}] ({len(matches)} strings)')
        for e in matches:
            print(f'  @{e["offset"]:>10}  {repr(e["text"])}')

# Unthemed strings
other = [e for e in utf16 if e['text'] not in all_shown]
if other:
    print(f'\n[other] ({len(other)} strings)')
    for e in other[:30]:
        print(f'  @{e["offset"]:>10}  {repr(e["text"])}')

# Save full findings
out = {
    'file': str(DLL),
    'analyzed': datetime.now().isoformat(),
    'utf16_total': len(utf16),
    'ascii_total': len(ascii_s),
    'by_theme': {k: [e['text'] for e in v] for k, v in findings.items()},
    'all_utf16': [e['text'] for e in utf16],
}
Path('output/soulkey_deep.json').write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print('\n[OK] Full results saved to output/soulkey_deep.json')
