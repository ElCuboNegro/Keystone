#!/usr/bin/env python3
"""
dll_analyzer.py — DLL decompilation and archaeology tool
Analyzes PE binaries (DLLs, EXEs) without requiring Ghidra or radare2.

Produces:
  - Import table (what APIs the DLL calls)
  - Export table (what functions it exposes)
  - String extraction (hardcoded values, paths, GUIDs, byte sequences)
  - WinSCard / NFC API call sites
  - Disassembly of key functions (via capstone)
  - .NET detection + IL metadata
  - Suspicious patterns (hardcoded credentials, device IDs, APDUs)

Usage:
    python dll_analyzer.py target.dll
    python dll_analyzer.py target.dll --output analysis.md
    python dll_analyzer.py target.dll --disasm   (include disassembly)
    python dll_analyzer.py *.dll                  (analyze all DLLs)
"""

import sys
import re
import struct
import argparse
import json
from pathlib import Path
from datetime import datetime

try:
    import pefile
except ImportError:
    sys.exit("ERROR: pefile not installed. Run: pip install pefile")

try:
    import capstone
    HAS_CAPSTONE = True
except ImportError:
    HAS_CAPSTONE = False
    print("[WARN] capstone not installed — disassembly disabled. Run: pip install capstone")


# ─── NFC / Smart card patterns to hunt for ───────────────────────────────────

INTERESTING_IMPORTS = {
    # PC/SC
    'SCardEstablishContext', 'SCardReleaseContext',
    'SCardConnect', 'SCardConnectA', 'SCardConnectW',
    'SCardDisconnect', 'SCardReconnect',
    'SCardTransmit', 'SCardControl',
    'SCardBeginTransaction', 'SCardEndTransaction',
    'SCardGetStatusChange', 'SCardGetStatusChangeA', 'SCardGetStatusChangeW',
    'SCardListReaders', 'SCardListReadersA', 'SCardListReadersW',
    'SCardGetAttrib', 'SCardSetAttrib', 'SCardStatus', 'SCardStatusA', 'SCardStatusW',
    # WinUSB / HID
    'WinUsb_Initialize', 'WinUsb_ControlTransfer', 'WinUsb_WritePipe', 'WinUsb_ReadPipe',
    'HidD_GetAttributes', 'HidD_GetSerialNumberString',
    # Device IO
    'DeviceIoControl', 'CreateFileA', 'CreateFileW',
    'SetupDiGetClassDevsA', 'SetupDiGetClassDevsW',
    'SetupDiEnumDeviceInterfaces', 'SetupDiGetDeviceInterfaceDetail',
    'RegisterDeviceNotification',
    # NFC specific (if using vendor SDKs)
    'nfc_open', 'nfc_init', 'nfc_initiator_init',
    'ACR_Open', 'ACR_Close', 'ACR_SendAPDU',
}

APDU_PATTERN   = re.compile(rb'(?:\x00|\xFF|[\x80-\x9F])[\x00-\xFF]{3}')
HEX_SEQ_PATTERN = re.compile(rb'(?:[\x00-\xFF]{4,32})')

# Interesting string patterns
STRING_PATTERNS = {
    'reader_name':    re.compile(r'(ACS|ACR122|ACR|Identiv|Gemalto|Omnikey|SCM|HID)\s*\w+', re.I),
    'device_path':    re.compile(r'\\\\\.\\[\w\\\-{}]+'),
    'guid':           re.compile(r'\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}', re.I),
    'iso_standard':   re.compile(r'ISO[\s\-]?1[45][0-9]{3}', re.I),
    'apdu_comment':   re.compile(r'(APDU|apdu|0xFF|0xCA|0xB0|SCard)', re.I),
    'registry_key':   re.compile(r'SOFTWARE\\[\w\\]+'),
    'timeout_value':  re.compile(r'timeout|delay|sleep|interval', re.I),
    'version_string': re.compile(r'v?\d+\.\d+\.\d+'),
}


# ─── Main analyzer ────────────────────────────────────────────────────────────

def analyze_dll(path: Path, include_disasm: bool = False) -> dict:
    print(f"\n[*] Analyzing: {path.name}")
    result = {
        'file':      str(path),
        'name':      path.name,
        'size':      path.stat().st_size,
        'timestamp': datetime.now().isoformat(),
    }

    raw = path.read_bytes()

    # Detect .NET
    if b'mscoree.dll' in raw or b'_CorExeMain' in raw or b'_CorDllMain' in raw:
        result['type'] = 'dotnet'
        print("  [*] .NET assembly detected")
        result.update(_analyze_dotnet(path, raw))
    else:
        result['type'] = 'native'
        result.update(_analyze_native(path, raw, include_disasm))

    result.update(_extract_strings(raw))
    result.update(_find_apdu_sequences(raw))

    return result


# ─── Native PE analysis ───────────────────────────────────────────────────────

def _analyze_native(path: Path, raw: bytes, include_disasm: bool) -> dict:
    result = {}

    try:
        pe = pefile.PE(data=raw)
    except pefile.PEFormatError as e:
        return {'pe_error': str(e)}

    # Machine type
    machine = pe.FILE_HEADER.Machine
    result['machine'] = {
        0x014c: 'x86 (32-bit)',
        0x8664: 'x86-64 (64-bit)',
        0x01c4: 'ARM',
        0xaa64: 'ARM64',
    }.get(machine, f'0x{machine:04X}')
    print(f"  [*] Architecture: {result['machine']}")

    # Timestamps
    ts = pe.FILE_HEADER.TimeDateStamp
    result['compile_timestamp'] = datetime.utcfromtimestamp(ts).isoformat() if ts else None

    # Imports
    imports = {}
    interesting = []
    if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            dll_name = entry.dll.decode('utf-8', errors='replace').lower()
            funcs = []
            for imp in entry.imports:
                name = imp.name.decode('utf-8', errors='replace') if imp.name else f'ord_{imp.ordinal}'
                funcs.append({'name': name, 'address': hex(imp.address) if imp.address else None})
                if name in INTERESTING_IMPORTS:
                    interesting.append({'dll': dll_name, 'function': name, 'address': hex(imp.address)})
            imports[dll_name] = funcs

    result['imports'] = imports
    result['interesting_imports'] = interesting
    if interesting:
        print(f"  [+] INTERESTING imports: {[i['function'] for i in interesting]}")

    # Exports
    exports = []
    if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
        for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            name = exp.name.decode('utf-8', errors='replace') if exp.name else f'ord_{exp.ordinal}'
            exports.append({
                'name': name,
                'ordinal': exp.ordinal,
                'address': hex(exp.address),
                'rva': hex(exp.address - pe.OPTIONAL_HEADER.ImageBase) if exp.address else None,
            })
    result['exports'] = exports
    if exports:
        print(f"  [+] Exports: {[e['name'] for e in exports[:10]]}{'...' if len(exports) > 10 else ''}")

    # Sections
    sections = []
    for s in pe.sections:
        name = s.Name.rstrip(b'\x00').decode('utf-8', errors='replace')
        sections.append({
            'name':             name,
            'virtual_address':  hex(s.VirtualAddress),
            'virtual_size':     s.Misc_VirtualSize,
            'raw_size':         s.SizeOfRawData,
            'entropy':          round(s.get_entropy(), 3),
            'characteristics':  hex(s.Characteristics),
        })
    result['sections'] = sections

    # Disassembly of entry point and interesting functions
    if include_disasm and HAS_CAPSTONE:
        result['disassembly'] = _disassemble_key_functions(pe, raw, interesting)

    pe.close()
    return result


def _disassemble_key_functions(pe, raw: bytes, interesting_imports: list) -> dict:
    """Disassemble functions that call interesting APIs."""
    if not HAS_CAPSTONE:
        return {}

    is_64 = pe.FILE_HEADER.Machine == 0x8664
    mode = capstone.CS_MODE_64 if is_64 else capstone.CS_MODE_32
    md = capstone.Cs(capstone.CS_ARCH_X86, mode)
    md.detail = True

    disassembled = {}

    # Entry point
    ep_rva = pe.OPTIONAL_HEADER.AddressOfEntryPoint
    ep_raw = pe.get_offset_from_rva(ep_rva)
    if ep_raw:
        ep_bytes = raw[ep_raw:ep_raw + 256]
        disassembled['entry_point'] = {
            'rva': hex(ep_rva),
            'instructions': _disasm_bytes(md, ep_bytes, ep_rva, max_insns=40),
        }

    # For each interesting import, find call sites
    for imp in interesting_imports[:10]:  # limit to first 10
        func_name = imp['function']
        addr_str = imp.get('address', '0x0')
        try:
            import_addr = int(addr_str, 16)
        except Exception:
            continue

        # Search for CALL instructions to this import's IAT entry
        call_sites = _find_call_sites(pe, raw, import_addr, md, func_name)
        if call_sites:
            disassembled[f'callers_of_{func_name}'] = call_sites

    return disassembled


def _disasm_bytes(md, data: bytes, base_rva: int, max_insns: int = 50) -> list:
    insns = []
    for i in md.disasm(data, base_rva):
        insns.append({
            'address': hex(i.address),
            'mnemonic': i.mnemonic,
            'op_str': i.op_str,
            'bytes': i.bytes.hex(),
        })
        if len(insns) >= max_insns:
            break
    return insns


def _find_call_sites(pe, raw: bytes, target_addr: int, md, func_name: str) -> list:
    """Find all CALL instructions to a specific address."""
    sites = []
    target_bytes = struct.pack('<I', target_addr & 0xFFFFFFFF)

    for section in pe.sections:
        sec_data = section.get_data()
        offset = 0
        while True:
            idx = sec_data.find(target_bytes, offset)
            if idx == -1:
                break
            # Found a potential call target — look backwards for CALL opcode
            raw_off = section.PointerToRawData + idx
            context_start = max(0, raw_off - 64)
            context = raw[context_start:raw_off + 8]
            rva = section.VirtualAddress + idx
            sites.append({
                'rva': hex(rva),
                'context_hex': context.hex(),
                'disasm': _disasm_bytes(md, context, rva - 64, 20),
            })
            offset = idx + 1

    return sites[:5]  # limit results


# ─── .NET analysis ────────────────────────────────────────────────────────────

def _analyze_dotnet(path: Path, raw: bytes) -> dict:
    result = {'dotnet': {}}
    # Extract strings from managed resources (UTF-16LE is common in .NET assemblies)
    strings_utf16 = re.findall(rb'(?:[\x20-\x7E]\x00){4,}', raw)
    decoded = []
    for s in strings_utf16[:100]:
        try:
            decoded.append(s.decode('utf-16-le').strip())
        except Exception:
            pass
    result['dotnet']['strings_utf16'] = [s for s in decoded if len(s) > 3]

    # Detect common .NET NFC/smartcard libs
    clues = []
    if b'PCSC' in raw or b'PcscException' in raw:
        clues.append('PCSC.Net or pcsc-sharp library detected')
    if b'SmartCard' in raw or b'Smartcard' in raw:
        clues.append('Custom SmartCard namespace detected')
    if b'ISO14443' in raw or b'ISO15693' in raw:
        clues.append('ISO NFC standards referenced in code')
    result['dotnet']['clues'] = clues

    # Suggest: use ILSpy/dnSpy/ildasm for full decompilation
    result['dotnet']['note'] = (
        'For full .NET decompilation: use ILSpy (ilspy.net) or dnSpy. '
        'CLI: ilspycmd target.dll -o output_dir/'
    )
    return result


# ─── String extraction ────────────────────────────────────────────────────────

def _extract_strings(raw: bytes) -> dict:
    # ASCII strings >= 5 chars
    ascii_strings = [
        m.group(0).decode('ascii', errors='replace')
        for m in re.finditer(rb'[\x20-\x7E]{5,}', raw)
    ]

    # Categorize
    categorized = {k: [] for k in STRING_PATTERNS}
    for s in ascii_strings:
        for category, pattern in STRING_PATTERNS.items():
            if pattern.search(s):
                categorized[category].append(s)

    # Unique interesting strings
    interesting = []
    for strings in categorized.values():
        interesting.extend(strings)
    interesting = list(dict.fromkeys(interesting))  # deduplicate

    return {
        'strings_count': len(ascii_strings),
        'strings_interesting': interesting[:100],
        'strings_by_category': {k: list(dict.fromkeys(v))[:20] for k, v in categorized.items() if v},
    }


# ─── APDU / byte sequence detection ──────────────────────────────────────────

def _find_apdu_sequences(raw: bytes) -> dict:
    """Find hardcoded APDU-like byte sequences in the binary."""
    candidates = []

    # Look for FF CA 00 00 (Get UID pseudo-APDU)
    for pattern, description in [
        (b'\xFF\xCA\x00\x00', 'Get UID (pseudo-APDU)'),
        (b'\xFF\xCA\x01\x00', 'Get ATS (pseudo-APDU)'),
        (b'\xFF\xB0\x00',     'Read Binary Block'),
        (b'\xFF\xD6\x00',     'Update Binary Block'),
        (b'\xD4\x14',         'PN532 SAMConfiguration'),
        (b'\xD4\x32',         'PN532 RFConfiguration'),
        (b'\xD4\x4A',         'PN532 InListPassiveTarget'),
        (b'\xD4\x42',         'PN532 InCommunicateThru'),
        (b'\xD4\x40',         'PN532 InDataExchange'),
        (b'\x00\xA4\x04',     'SELECT by AID'),
        (b'\x00\xA4\x00',     'SELECT by FID'),
        (b'\x00\xB0',         'READ BINARY'),
        (b'\x00\xD6',         'UPDATE BINARY'),
    ]:
        idx = 0
        while True:
            pos = raw.find(pattern, idx)
            if pos == -1:
                break
            context = raw[pos:pos + 16]
            candidates.append({
                'description': description,
                'pattern_hex': pattern.hex().upper(),
                'offset':      hex(pos),
                'context':     context.hex().upper(),
            })
            idx = pos + 1

    return {'apdu_candidates': candidates[:50]}


# ─── Report generator ─────────────────────────────────────────────────────────

def generate_report(analyses: list[dict], fmt: str = 'markdown') -> str:
    if fmt == 'json':
        return json.dumps(analyses, indent=2, default=str)
    return _to_markdown(analyses)


def _to_markdown(analyses: list[dict]) -> str:
    lines = [
        '# DLL Analysis Report',
        f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        '',
    ]
    for a in analyses:
        lines += [f'## {a["name"]}', '']
        lines += [f'- **Type:** {a.get("type", "?")}']
        lines += [f'- **Size:** {a.get("size", 0):,} bytes']
        lines += [f'- **Architecture:** {a.get("machine", "?")}']
        lines += [f'- **Compiled:** {a.get("compile_timestamp", "?")}']
        lines += ['']

        # Interesting imports
        interesting = a.get('interesting_imports', [])
        if interesting:
            lines += [f'### Hardware/NFC API Imports ({len(interesting)})', '']
            lines += ['| DLL | Function | IAT Address |']
            lines += ['|-----|----------|------------|']
            for i in interesting:
                lines += [f'| `{i["dll"]}` | `{i["function"]}` | `{i["address"]}` |']
            lines += ['']

        # Exports
        exports = a.get('exports', [])
        if exports:
            lines += [f'### Exports ({len(exports)})', '']
            for e in exports[:30]:
                lines += [f'- `{e["name"]}` @ `{e["address"]}`']
            if len(exports) > 30:
                lines += [f'- ... and {len(exports) - 30} more']
            lines += ['']

        # APDU candidates
        apdus = a.get('apdu_candidates', [])
        if apdus:
            lines += [f'### Hardcoded APDU/Protocol Sequences ({len(apdus)})', '']
            lines += ['| Description | Pattern | Offset | Context |']
            lines += ['|-------------|---------|--------|---------|']
            for ap in apdus:
                lines += [f'| {ap["description"]} | `{ap["pattern_hex"]}` | `{ap["offset"]}` | `{ap["context"]}` |']
            lines += ['']

        # Interesting strings
        by_cat = a.get('strings_by_category', {})
        if by_cat:
            lines += ['### Interesting Strings', '']
            for cat, strings in by_cat.items():
                if strings:
                    lines += [f'**{cat}:**']
                    for s in strings[:10]:
                        lines += [f'- `{s}`']
            lines += ['']

        # .NET notes
        if a.get('type') == 'dotnet':
            dt = a.get('dotnet', {})
            if dt.get('clues'):
                lines += ['### .NET Analysis', '']
                for c in dt['clues']:
                    lines += [f'- {c}']
                lines += [f'', f'> {dt.get("note", "")}', '']

        # Sections
        sections = a.get('sections', [])
        if sections:
            lines += ['### PE Sections', '']
            lines += ['| Name | Virtual Addr | Size | Entropy |']
            lines += ['|------|-------------|------|---------|']
            for s in sections:
                entropy_flag = ' << HIGH ENTROPY (packed/encrypted?)' if s['entropy'] > 7.0 else ''
                lines += [f'| `{s["name"]}` | `{s["virtual_address"]}` | {s["raw_size"]:,} | {s["entropy"]}{entropy_flag} |']
            lines += ['']

        lines += ['---', '']

    return '\n'.join(lines)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='DLL/EXE analyzer for NFC/SmartCard archaeology')
    parser.add_argument('targets', nargs='+', help='DLL/EXE files to analyze')
    parser.add_argument('--output', '-o', default='dll_analysis.md')
    parser.add_argument('--format', '-f', choices=['markdown', 'json'], default='markdown')
    parser.add_argument('--disasm', '-d', action='store_true', help='Include disassembly (slow)')
    args = parser.parse_args()

    analyses = []
    for pattern in args.targets:
        for path in Path('.').glob(pattern) if '*' in pattern else [Path(pattern)]:
            if not path.exists():
                print(f"[WARN] Not found: {path}")
                continue
            try:
                result = analyze_dll(path, include_disasm=args.disasm)
                analyses.append(result)
            except Exception as e:
                print(f"[ERROR] {path}: {e}")
                analyses.append({'file': str(path), 'error': str(e)})

    report = generate_report(analyses, fmt=args.format)
    out = Path(args.output)
    out.write_text(report, encoding='utf-8')
    print(f"\n[OK] Report written to: {out.resolve()}")

    # Print quick summary
    for a in analyses:
        interesting = a.get('interesting_imports', [])
        apdus = a.get('apdu_candidates', [])
        print(f"\n  {a['name']}:")
        print(f"    Architecture:     {a.get('machine', '?')}")
        print(f"    HW API imports:   {len(interesting)}")
        print(f"    APDU sequences:   {len(apdus)}")
        if interesting:
            print(f"    Key functions:    {', '.join(i['function'] for i in interesting[:5])}")


if __name__ == '__main__':
    main()
