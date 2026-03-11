# Retro-Engineering Report

**Target:** `C:\Users\jalba\Desktop\keystone`  
**Generated:** 2026-03-10 20:33  
**Primary Language:** Python  
**Platform:** Windows  

---

## 1. Technology Stack

- **Languages:** Python (7 files)
- **Build Systems:** none detected
- **Total Source Files:** 7
- **Total Lines:** 2,638

### Hardware / External APIs Detected

| Pattern | Description | Category | Files |
|---------|-------------|----------|-------|
| `winscard` | WinSCard library import/link | winscard | `retro-report.dot`, `retro-report.md`, `skills\retro-engineer.md` +4 more |
| `SCardEstablishContext` | PC/SC: Establish context | winscard | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `SCardConnect` | PC/SC: Connect to card | winscard | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +1 more |
| `SCardTransmit` | PC/SC: Send APDU | winscard | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +1 more |
| `SCardDisconnect` | PC/SC: Disconnect | winscard | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `SCardBeginTransaction` | PC/SC: Begin transaction | winscard | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `SCardEndTransaction` | PC/SC: End transaction | winscard | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +1 more |
| `SCardGetStatusChange` | PC/SC: Poll reader state change | winscard | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `SCardListReaders` | PC/SC: List available readers | winscard | `retro-report.md`, `tools\retro\api_mapper.py`, `tools\retro\language_detector.py` |
| `SCardControl` | PC/SC: Send control/escape command | winscard | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `pcsclite` | PC/SC Lite (Linux/macOS) | pcsc-linux | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\language_detector.py` +1 more |
| `ISO15693` | ISO 15693 Vicinity Card protocol | nfc | `retro-report.md`, `tools\retro\language_detector.py` |
| `ISO14443` | ISO 14443 Proximity Card protocol | nfc | `retro-report.md`, `tools\retro\language_detector.py` |
| `APDU` | Application Protocol Data Unit | nfc | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\decision_extractor.py` +1 more |
| `ACR122` | ACR122U NFC reader | nfc | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\language_detector.py` +1 more |
| `libnfc` | libnfc library | nfc | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `nfc_open` | libnfc: open device | nfc | `retro-report.md`, `tools\retro\api_mapper.py`, `tools\retro\language_detector.py` |
| `nfc_initiator` | libnfc: initiator mode | nfc | `retro-report.md`, `tools\retro\api_mapper.py`, `tools\retro\language_detector.py` |
| `FF000000` | ACR122U escape command prefix | nfc | `retro-report.md`, `tools\retro\language_detector.py` |
| `libusb` | LibUSB direct USB access | usb | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `hidapi` | HIDAPI (HID device access) | usb | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +1 more |
| `WinUSB` | WinUSB driver | usb | `retro-report.md`, `tools\retro\language_detector.py` |
| `DeviceIoControl` | Windows: DeviceIoControl | winapi | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `CreateFile` | Windows: CreateFile (device handle) | winapi | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `SetupDiGetClassDevs` | Windows: Device enumeration | winapi | `retro-report.md`, `tools\retro\api_mapper.py`, `tools\retro\language_detector.py` |
| `RegisterDeviceNotification` | Windows: Device hotplug events | winapi | `retro-report.md`, `skills\retro-engineer.md`, `tools\retro\api_mapper.py` +2 more |
| `CM_Register_Notification` | Windows: PnP notifications | winapi | `retro-report.md`, `tools\retro\api_mapper.py`, `tools\retro\language_detector.py` |

## 2. Architecture & Structure

### Entry Points

- `tools\retro\main.py`
- `tools\retro\structure_mapper.py`

### Modules (7 source files)

| File | Language | Classes | Functions | Lines |
|------|----------|---------|-----------|-------|
| `tools\retro\structure_mapper.py` | Python | 0 | 12 | 298 |
| `tools\retro\decision_extractor.py` | Python | 1 | 9 | 297 |
| `tools\retro\call_tree.py` | Python | 1 | 10 | 292 |
| `tools\retro\reporter.py` | Python | 0 | 5 | 252 |
| `tools\retro\api_mapper.py` | Python | 1 | 6 | 182 |
| `tools\retro\language_detector.py` | Python | 0 | 2 | 164 |
| `tools\retro\main.py` | Python | 0 | 2 | 137 |

### Public API Surface (11 symbols)

- **class** `_ApiCallVisitor` — `tools\retro\api_mapper.py`
- **function** `map_api_calls` — `tools\retro\api_mapper.py`
- **class** `_CallVisitor` — `tools\retro\call_tree.py`
- **function** `build_call_tree` — `tools\retro\call_tree.py`
- **class** `Decision` — `tools\retro\decision_extractor.py`
- **function** `extract_decisions` — `tools\retro\decision_extractor.py`
- **function** `detect_language` — `tools\retro\language_detector.py`
- **function** `main` — `tools\retro\main.py`
- **function** `log` — `tools\retro\main.py`
- **function** `generate_report` — `tools\retro\reporter.py`
- **function** `map_structure` — `tools\retro\structure_mapper.py`

## 3. Call Tree

### Entry Point Flows

#### `main` (`tools\retro\main.py`)

```
└─ main
  └─ ArgumentParser
  └─ add_argument
  └─ parse_args
  └─ resolve
  └─ Path
  └─ exists
  └─ print
  └─ exit
```

#### `log` (`tools\retro\main.py`)

```
└─ log
  └─ print
```

#### `map_structure` (`tools\retro\structure_mapper.py`)

```
└─ map_structure
  └─ get
  └─ exists
  └─ _parse_python
    └─ read_text
    └─ parse
    └─ str
    └─ _parse_generic
      └─ read_text
      └─ set
      └─ finditer
      └─ group
      └─ add
      └─ append
      └─ count
      └─ start
    └─ walk
    └─ isinstance
    └─ getattr
    └─ append
  └─ _parse_c
    └─ read_text
    └─ enumerate
    └─ splitlines
    └─ findall
    └─ _line_of
      └─ find
      └─ count
    └─ finditer
    └─ group
    └─ append
  └─ _parse_js
    └─ read_text
    └─ findall
    └─ finditer
    └─ group
    └─ append
    └─ count
    └─ start
    └─ strip
  └─ _parse_csharp
    └─ read_text
    └─ findall
    └─ _line_of
      └─ find
      └─ count
    └─ strip
    └─ split
    └─ count
  └─ _parse_generic
    └─ read_text
    └─ set
    └─ finditer
    └─ group
    └─ add
    └─ append
    └─ count
    └─ start
  └─ append
```

#### `_parse_python` (`tools\retro\structure_mapper.py`)

```
└─ _parse_python
  └─ read_text
  └─ parse
  └─ str
  └─ _parse_generic
    └─ read_text
    └─ set
    └─ finditer
    └─ group
    └─ add
    └─ append
    └─ count
    └─ start
  └─ walk
  └─ isinstance
  └─ getattr
  └─ append
```

#### `_py_name` (`tools\retro\structure_mapper.py`)

```
└─ _py_name
  └─ isinstance
  └─ _py_name
```

#### `_py_decorator` (`tools\retro\structure_mapper.py`)

```
└─ _py_decorator
  └─ isinstance
  └─ _py_name
    └─ isinstance
    └─ _py_name
  └─ _py_decorator
```

#### `_is_method` (`tools\retro\structure_mapper.py`)

```
└─ _is_method
  └─ walk
  └─ isinstance
```

#### `_parse_c` (`tools\retro\structure_mapper.py`)

```
└─ _parse_c
  └─ read_text
  └─ enumerate
  └─ splitlines
  └─ findall
  └─ _line_of
    └─ find
    └─ count
  └─ finditer
  └─ group
  └─ append
```

#### `_parse_js` (`tools\retro\structure_mapper.py`)

```
└─ _parse_js
  └─ read_text
  └─ findall
  └─ finditer
  └─ group
  └─ append
  └─ count
  └─ start
  └─ strip
```

#### `_parse_csharp` (`tools\retro\structure_mapper.py`)

```
└─ _parse_csharp
  └─ read_text
  └─ findall
  └─ _line_of
    └─ find
    └─ count
  └─ strip
  └─ split
  └─ count
```

#### `_parse_generic` (`tools\retro\structure_mapper.py`)

```
└─ _parse_generic
  └─ read_text
  └─ set
  └─ finditer
  └─ group
  └─ add
  └─ append
  └─ count
  └─ start
```

#### `_line_of` (`tools\retro\structure_mapper.py`)

```
└─ _line_of
  └─ find
  └─ count
```

#### `_build_tree` (`tools\retro\structure_mapper.py`)

```
└─ _build_tree
  └─ Path
  └─ setdefault
```

### External/Hardware API Call Sites (17 calls)

| Caller | Callee | File | Line |
|--------|--------|------|------|
| `_scan_intent_comments` | `Decision` | `tools\retro\decision_extractor.py` | 131 |
| `_scan_constants` | `Decision` | `tools\retro\decision_extractor.py` | 152 |
| `_scan_constants` | `Decision` | `tools\retro\decision_extractor.py` | 161 |
| `_scan_constants` | `Decision` | `tools\retro\decision_extractor.py` | 175 |
| `_scan_timeouts` | `Decision` | `tools\retro\decision_extractor.py` | 189 |
| `_scan_timeouts` | `Decision` | `tools\retro\decision_extractor.py` | 196 |
| `_scan_byte_sequences` | `Decision` | `tools\retro\decision_extractor.py` | 223 |
| `_scan_threading` | `Decision` | `tools\retro\decision_extractor.py` | 241 |
| `_scan_winscard_choices` | `Decision` | `tools\retro\decision_extractor.py` | 255 |
| `_scan_winscard_choices` | `Decision` | `tools\retro\decision_extractor.py` | 262 |
| `_scan_winscard_choices` | `Decision` | `tools\retro\decision_extractor.py` | 270 |
| `_summarize` | `Counter` | `tools\retro\decision_extractor.py` | 295 |
| `detect_language` | `Counter` | `tools\retro\language_detector.py` | 94 |
| `main` | `ArgumentParser` | `tools\retro\main.py` | 39 |
| `main` | `Path` | `tools\retro\main.py` | 54 |
| `main` | `Path` | `tools\retro\main.py` | 93 |
| `_build_tree` | `Path` | `tools\retro\structure_mapper.py` | 293 |

> Total call edges found: **503**

## 4. External API Usage

## 5. Software Decisions

> Found 11 decisions: 7 protocol, 4 threading

### Critical Decisions (7)

- **[PROTOCOL]** `tools\retro\decision_extractor.py:67` — PC/SC constant usage: SCARD_CONSTANT_RE
  ```
  SCARD_CONSTANT_RE = re.compile(r'\bSCARD_[A-Z_]+\b')
  ```
- **[PROTOCOL]** `tools\retro\decision_extractor.py:71` — PC/SC constant usage: SCARD_SHARE_
  ```
  SHARE_MODE_RE = re.compile(r'SCARD_SHARE_(SHARED|EXCLUSIVE|DIRECT)')
  ```
- **[PROTOCOL]** `tools\retro\decision_extractor.py:267` — PC/SC constant usage: SCARD_CONSTANT_RE
  ```
  for m3 in SCARD_CONSTANT_RE.finditer(line):
  ```
- **[PROTOCOL]** `tools\retro\reporter.py:215` — PC/SC card disposition on disconnect: SCARD_UNPOWER_CARD — affects card state
  ```
  '1. `SCardDisconnect` called with `SCARD_UNPOWER_CARD` — turns off RF field',
  ```
- **[PROTOCOL]** `tools\retro\reporter.py:215` — PC/SC constant usage: SCARD_UNPOWER_CARD
  ```
  '1. `SCardDisconnect` called with `SCARD_UNPOWER_CARD` — turns off RF field',
  ```
- **[PROTOCOL]** `tools\retro\reporter.py:220` — PC/SC card disposition on disconnect: SCARD_LEAVE_CARD — affects card state
  ```
  'To fix on Linux: use `SCARD_LEAVE_CARD` disposition and wrap reads in `SCardBeginTransaction`.',
  ```
- **[PROTOCOL]** `tools\retro\reporter.py:220` — PC/SC constant usage: SCARD_LEAVE_CARD
  ```
  'To fix on Linux: use `SCARD_LEAVE_CARD` disposition and wrap reads in `SCardBeginTransaction`.',
  ```

### Threading Decisions (4)

- `tools\retro\call_tree.py:160` — Concurrency/threading: async
- `tools\retro\decision_extractor.py:9` — Concurrency/threading: threading
- `tools\retro\decision_extractor.py:57` — Concurrency/threading: thread
- `tools\retro\structure_mapper.py:196` — Concurrency/threading: async

### Protocol Decisions (7)

- `tools\retro\decision_extractor.py:67` — PC/SC constant usage: SCARD_CONSTANT_RE
- `tools\retro\decision_extractor.py:71` — PC/SC constant usage: SCARD_SHARE_
- `tools\retro\decision_extractor.py:267` — PC/SC constant usage: SCARD_CONSTANT_RE
- `tools\retro\reporter.py:215` — PC/SC card disposition on disconnect: SCARD_UNPOWER_CARD — affects card state
- `tools\retro\reporter.py:215` — PC/SC constant usage: SCARD_UNPOWER_CARD
- `tools\retro\reporter.py:220` — PC/SC card disposition on disconnect: SCARD_LEAVE_CARD — affects card state
- `tools\retro\reporter.py:220` — PC/SC constant usage: SCARD_LEAVE_CARD

## 6. Cross-Platform Porting Notes

**Current platform: Windows-only**

| Windows API | Linux Equivalent | Notes |
|-------------|-----------------|-------|

**Recommended Linux stack:**
```
ACR122U → pcscd (pcsc-lite daemon) → libpcsclite → your app
  OR
ACR122U → libnfc (direct USB, no pcscd needed)
```

**Key issue — RF field timing:**
The millisecond card-read problem is likely caused by one of:
1. `SCardDisconnect` called with `SCARD_UNPOWER_CARD` — turns off RF field
2. No `SCardBeginTransaction` — card is deselected between operations
3. `SCardGetStatusChange` timeout set too low
4. ACR122U firmware auto-polling disabled via escape command

To fix on Linux: use `SCARD_LEAVE_CARD` disposition and wrap reads in `SCardBeginTransaction`.

---
*Generated by retro-engineer v1.0*

---

## 7. ArmouryCrate SoulKeyServicePlugin — Reverse Engineering (2026-03-11)

**Target DLL:** `C:\Program Files\ASUS\Armoury Crate Service\SoulKeyServicePlugin\ArmouryCrate.SoulKeyServicePlugin.dll`
**Size:** 280,168 bytes | **Architecture:** x86-64 | **Analysis:** UTF-16 string extraction

### Card Presence Detection Model

ArmouryCrate does **NOT** use PC/SC state for persistent card presence.  It uses:

```
RegisterRawInputDevices() → GetRawInputData(dwType=RIM_TYPEHID)
  → WPARAM = 0xB4 → HandleExtKeystoneEvents() → DoNotifyThread
  → CheckSoulKeySupport (NXP / ST) → PC/SC read → "Off NFC"
```

The HID raw input tells AC that the card is physically present.
`HandlePlugOut()` only fires on a **separate HID removal event**, not on PC/SC EMPTY.
This is why the "Enchufada botón rojo" state persists after RF is killed.

### Root Cause — False Card Removal in Our Monitor

1. Card physically inserted → HID event → AC + our monitor both detect it
2. AC reads via PC/SC: `PCSC_Connect` → `ApduGetUID` → `ApduGetData`
3. AC calls `SCardDisconnect(SCARD_UNPOWER_CARD)` → NfcCx stops RF polling
4. PC/SC reports `SCARD_STATE_EMPTY` → our monitor fires `on_removed` ← **FALSE**
5. AC maintains `CardExist`/`CardPlugin` via HID → keeps showing "Enchufada" ← **CORRECT**

### Fix Applied — Suppress EMPTY After Insert

Initially, a fix was attempted to re-wake the RF field by re-issuing `SCardConnect` (documented in `ADR-0008`). This failed because NfcCx returns `SCARD_E_NO_SMARTCARD` to all subsequent connect attempts until the card is physically lifted and placed again.

The final fix (`ADR-0009`) instead relies on suppressing the phantom EMPTY event entirely:
1. Card physically inserted → AC + monitor both detect it
2. Monitor successfully fires `on_inserted` and marks `inserted_fired = True`
3. AC reads PC/SC and kills RF → PC/SC reports `SCARD_STATE_EMPTY`
4. Monitor sees EMPTY but `inserted_fired` is True → suppresses `on_removed`
5. The monitor maintains "inserted" state conceptually until `stop()` is called. Genuine live removals are no longer detected immediately, but false vault locks are completely eliminated.

**See:** `ADR-0008` (failed re-wake), `ADR-0009` (suppress-EMPTY), `knowledge/nfc/soulkey-architecture-research.md`

### Keystone Card Types (from Aura LED integration)

| Prefix | Card Tier | Aura Message |
|--------|-----------|-------------|
| R | Red-key | `"Send Red-key Aura message successed."` |
| Y | Yellow-key | `"Send Yellow-key Aura message successed."` |
| — | NonColor-key | `"Send NonColor-key Aura message successed."` |

Each type has separate `RInsert`/`RRemove` and `YInsert`/`YRemove` events.

### Internal State Tracking

- `m_dwInternalStatus` — master state variable (numeric)
- `g_dwLastGotTagSwitchNotify` — event queuing/dedup (set to 1 when queued)
- `m_dwLastGotTagSwitchNotifyST` — ST-chip specific tag switch (0 or 1)
- Power management: `"Keystone changed (%s -> %s) during sleep, handling..."`