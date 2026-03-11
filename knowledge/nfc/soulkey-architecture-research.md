---
type: reverse-engineered
source: DLL string analysis — ArmouryCrate.SoulKeyServicePlugin.dll
confidence: high
domain: nfc
standard_body: proprietary (ASUS)
related_agents: nfc-rfid-specialist, smart-card-specialist
date_added: 2026-03-10
pdb_path: D:\SourceCode\AC.Keystone\production_V6.4\ServiceApp\SoulKeyServicePlugin
---

# ASUS SoulKey / Keystone Architecture — Reverse-Engineering Findings

## Discovery Method
Static binary analysis of `ArmouryCrate.SoulKeyServicePlugin.dll` v6.4.
PDB debug symbols were stripped but embedded UTF-16 log strings survived,
providing a near-complete reconstruction of the internal flow.

---

## Hardware Stack

```
NXP NFC chip (I2C bus, built into ASUS laptop)
  └── NxpNfcClientDriver.dll  (UMDF driver)
       └── NfcCx.dll           (Windows NFC Class Extension)
            └── Microsoft IFD 0  (presents as PC/SC reader)
                 └── WinSCard API (winscard.dll)
                      └── ArmouryCrate.SoulKeyServicePlugin.dll
                           └── Armoury Crate Service

ALSO: USB HID device  VID=0483 (STMicro) PID=5750 REV=0200
  └── Handled via hidapi / HidD_* functions
  (This may be the NFC dongle or an alternative ST-chip path)
```

**Two supported chip types:**
- `HandlePlugInNXP()` — NXP NFC chip path (via PC/SC / Microsoft IFD)
- `HandlePlugInST()` — STMicro chip path (via USB HID, VID 0483 PID 5750)

---

## Internal Function Mapping

### PC/SC wrapper functions (internal names recovered from log strings)

| Internal Name | WinSCard call | Purpose |
|--------------|--------------|---------|
| `PCSC_Connect` | `SCardConnectW` | Connect to card reader |
| `PCSC_ActivateCard` | `SCardBeginTransaction`? | Activate card for reading |
| `PCSC_GetAtrString` | `SCardGetAttrib(SCARD_ATTR_ATR_STRING)` | Read ATR |
| `PCSC_Exchange__ApduGetUID` | `SCardTransmit` | Send GET UID APDU |
| `PCSC_Exchange__ApduGetData` | `SCardTransmit` | Send GET DATA APDU |

### Card state machine

States (from `CardXxx` field names):
```
CardExist  →  CardPlugin  →  [CardPaired]  →  [CardAuthorized]  →  CardActivated
                                    ↓                  ↓
                              CardBindAccount    CardUnlock
                              CardUID            CardData
                              CardSSNNEW         CardLight
                              CardSound          CardLaunchSetting
```

Status flags tracked:
- `CardExist` — card is physically present
- `CardPlugin` — card was inserted (plug-in event)
- `CardPaired` — card is paired to this device
- `CardBindAccount` — card is bound to an account
- `CardAuthorized` — card is authorized to unlock
- `CardUnlock` — card is used to unlock (shadow drive, Windows)
- `CardActivated` — card is fully activated

Data read from card:
- `CardUID` — card UID (read via `PCSC_Exchange__ApduGetUID`)
- `CardData` — card payload data (read via `PCSC_Exchange__ApduGetData`)
- `CardSSNNEW` — Serial Number (looked up via `GetSSNByUID`)

---

## Event / Trigger Chain (reconstructed from log messages)

```
1. BIOS ACPI event (ATKHotkey) OR WM_INPUT (GetRawInputData)
     ↓  WPARAM = 0xB4 (180)
2. HandleExtKeystoneEvents()
     ↓
3. DoNotifyThread invoked
     ↓
4. CheckSoulKeySupport / CheckSoulKeySupportOrNot
     ├── CheckSupport NXP → HandlePlugInNXP()
     └── CheckSupport ST  → HandlePlugInST()
         ↓
5. "Ready to read NFC data"
     ↓
6. PCSC_Connect → SCardConnectW
   PCSC_ActivateCard
   PCSC_GetAtrString → SCardGetAttrib
   PCSC_Exchange__ApduGetUID → SCardTransmit (Get UID)
   PCSC_Exchange__ApduGetData → SCardTransmit (Get Data)
     ↓
7. Read OK / Read NFC data done
     ↓  OR
7a. "Card is NOT present after cooling down time!" → abort
     ↓
8. SCardDisconnect → (disposition unknown — see CRITICAL NOTE)
     ↓
9. "Off NFC" ← EXPLICITLY DISABLES NFC RADIO AFTER READING
     ↓
10. Update card state machine
    Trigger Aura, FanMode, ShadowDrive, QuickLaunch, etc.
```

---

## CRITICAL FINDING: "Off NFC" after read

Log string at offset `0x32910`: `'Soulkey Plugin : Off NFC'`

**The software explicitly turns off the NFC radio after reading the card.**

This is the root cause of the millisecond problem. The sequence is:
1. Card detected (BIOS/HID interrupt)
2. PC/SC connects and reads UID + data (~100ms)
3. `SCardDisconnect` is called (disposition TBD — likely `SCARD_UNPOWER_CARD`)
4. NFC radio is turned off

This is by design — the software is not intended for continuous card presence.
It reads the card once on insertion, then disconnects.

**To enable continuous reading:**
- Do NOT call "Off NFC" after reading
- Use `SCARD_LEAVE_CARD` disposition on disconnect
- Keep PC/SC context open and poll with `SCardGetStatusChange`

---

## Features Activated by the Card

| Feature | Log string / key | Mechanism |
|---------|-----------------|-----------|
| Shadow drive unlock | `CardUnlock`, `SetShadowDriveStatus` | Unlocks an encrypted virtual drive |
| Windows lock/unlock | `SetUnlockStatus`, `Plug-Out LockWindows` | Lock Windows on card removal |
| Aura RGB | `Send Red-key/Yellow-key/NonColor-key Aura message` | Changes keyboard RGB by card type |
| Fan / performance mode | `KeyStoneSetThrottleGearServiceHyperFanMode`, `Plug-In HyperFanMode` | Changes fan curve |
| Quick launch | `Plug-In QuickLaunch`, `QuickLaunch_LaunchType` | Launches app on card insert |
| Stealth mode | `Plug-Out Stealth` | Activates stealth mode on removal |
| Bluetooth pairing | `SetPairedStatus`, `SetPairedStatusEx` | Links card to BT device |
| Volume protection | `VolumeKeyProtectorID` | BitLocker-style volume key |

---

## Registry Keys

```
SOFTWARE\ASUS\ARMOURY CRATE Service\SoulkeyPlugin\DataCollection
%APPDATA%\ASUS\SoulKey\
%APPDATA%\ASUS\SoulKey\SoulKeyPlugin_Status.ini
```

---

## HID Device: VID_0483 PID_5750 REV_0200

- VID 0483 = STMicroelectronics
- PID 5750 = STM32-based HID device (possibly custom NFC interface chip)
- Used for `HandlePlugInST()` path
- Accessed via `HidD_GetAttributes`, `HidD_SetFeature`, `HidD_GetFeature`
- This is likely an alternative NFC reader presented as USB HID (not PC/SC)

---

## Windows Message: WPARAM = 0xB4

Log: `'Soulkey Plugin : WPARAM = B4, ready to update Keystone status.'`

`0xB4 = 180` — This is a custom `WM_INPUT` or registered window message value.
The card insertion/removal trigger a raw input device event that the plugin
listens for via `RegisterRawInputDevices()`.

This is separate from the PC/SC `SCardGetStatusChange` polling mechanism.
The plugin receives an OS-level input notification BEFORE it starts reading the card.

---

## Experiment Results

### Experiment 01 — Baseline Card Read (CONFIRMED)
- SHARED mode connects at Protocol T1 (value=2). Card readable for 10+ reads × 0.5s.
- EXCLUSIVE mode: connects, but card drops after ~1 read (NfcCx kicks EXCLUSIVE clients faster).
- UID confirmed: `54 D4 4C 4F 08 01 04 E0` — NXP ISO 15693.
- `SCARD_LEAVE_CARD` keeps card addressable across disconnect/reconnect cycles.
- `0x80100069` = `SCARD_E_NO_SMARTCARD` — card not present, NOT "radio off".

### Experiment 02 — Wake NFC Radio / IOCTL Probe (CONFIRMED)
- **Zero IOCTLs accepted by Microsoft IFD 0.** NfcCx does not expose SCardControl escape commands.
  - `0x00000032` = ERROR_NOT_SUPPORTED (all CCID escape + NFC CX candidates)
  - `0x00000057` = ERROR_INVALID_PARAMETER (SCARD_CTL_1/2 at 0x00310004/8)
- **RF field is never programmatically "off" via SCardControl.** The hypothesis was wrong.
- **Passive recovery confirmed:** removing/replacing card restores connectivity within 1 poll cycle.
- **ATKACPI device opens** (CreateFileW handle ~500). We can send DeviceIoControl to ATK hotkey device.
- **DIRECT mode protocol=2** when card is present; protocol=0 when no card — NfcCx reflects card state in DIRECT connects.

### Experiments 03, 04, 05 — Card Memory Mapping (CONFIRMED)
- **Card has exactly 1 readable block: Block 0 = `01 01 01 01` (SW=9000).**
- **Every other block address (1, 2, 3...) returns SW=6981** ("Command incompatible with file structure").
- **SW=6981 response immediately kills the NfcCx RF session** — NfcCx interprets the ISO 15693 error
  as a card malfunction and deactivates. Session dies ~0.5s after a 6981 response (retry timeout).
- **GET_SYSTEM_INFORMATION (FF 30, FF 2B) returns SW=6A81** ("Function not supported") — NfcCx
  does not expose this command for this card type. Does NOT kill session.
- ATR confirmed: `3B 8F 80 01 80 4F 0C A0 00 00 03 06 0C 00 14 00 00 00 00 70`
  - Historical bytes: NXP RID (`A0 00 00 03 06`) + Standard=ISO 15693 (`0C`) + variant (`00`) + `14`...
- **Safe APDU sequence (does not kill session):**
  1. `FF CA 00 00 00` → GET UID → `54 D4 4C 4F 08 01 04 E0` (SW=9000)
  2. `FF B0 00 00 04` → READ BLOCK 0 → `01 01 01 01` (SW=9000)
  3. Any subsequent `FF B0 00 01+` → SW=6981 → SESSION KILLED

### Card Data Interpretation
- **`01 01 01 01` in block 0** is likely a card type/tier/version marker (all bytes = 0x01 = "enabled/standard").
- **`CardData` read by `PCSC_Exchange__ApduGetData` is almost certainly block 0 = `01 01 01 01`.**
- **`CardSSNNEW` is looked up server-side** via `GetSSNByUID` — the card is identified by UID, not stored serial.
- Real authentication data (if any) is on ASUS servers, keyed by the 8-byte UID.
- **Linux portability: CONFIRMED STRAIGHTFORWARD.** pcsclite + `FF CA` + `FF B0 00 00 04`. No proprietary commands needed.

### Revised RF Off Theory — CONFIRMED
The "Off NFC" is achieved via option (d) — `SCardDisconnect(SCARD_UNPOWER_CARD)`.
NfcCx stops emitting RF polling frames when no PC/SC client holds an open card handle.
Experiment 02 confirmed that zero IOCTLs are accepted by NfcCx via SCardControl,
eliminating options (a), (b), and (c).

**The re-wake fix**: a fresh `SCardConnect` from our monitor triggers NfcCx to resume
RF discovery.  If the card is physically present, it is re-found within 1-2 polling
cycles (~500ms).  Implemented in `keystone_nfc/monitor.py:_verify_card_present()`.

---

## Complete String Extraction — DLL Direct Analysis (2026-03-11)

Full UTF-16 string extraction from `ArmouryCrate.SoulKeyServicePlugin.dll` (280,168 bytes).
This is a direct extraction, not inferred from behavior.

### HID Raw Input Event Model (CONFIRMED)
```
RegisterRawInputDevices() on KS → GetRawInputData(dwType==2 [RIM_TYPEHID])
  → WPARAM = 0xB4 → HandleExtKeystoneEvents()
  → DoNotifyThread → "Keystone inserted." / "Keystone not present."
```

Key strings:
- `"RegisterRawInputDevices() on KS (test) failed!"`
- `"GetRawInputData dwType != 2return"` — filters for RIM_TYPEHID only
- `"GetRawInputData return"`
- `"WPARAM = B4, ready to update Keystone status."`

### Event Types
| Tag | Direction | Meaning |
|-----|-----------|---------|
| `RInsert` | HID → Plugin | **R**ed-key Keystone insertion event |
| `RRemove` | HID → Plugin | **R**ed-key Keystone removal event |
| `YInsert` | HID → Plugin | **Y**ellow-key Keystone insertion event |
| `YRemove` | HID → Plugin | **Y**ellow-key Keystone removal event |
| `PlugIn` | Plugin → AC | Card plugged in (state change notification) |
| `PlugOut` | Plugin → AC | Card plugged out (state change notification) |
| `QuickPlugIn` / `QuickPlugOut` | Plugin → AC | Quick-action triggered events |

> The R/Y prefixes map to Keystone card tiers, identified by Aura LED color:
> `"Send Red-key Aura message successed."` / `"Send Yellow-key Aura message successed."`
> A third message `"Send NonColor-key Aura message successed."` handles unknown/default cards.

### Internal State Machine
```
m_dwInternalStatus  — master state variable
g_dwLastGotTagSwitchNotify — event queuing/dedup flag (set to 1 when queued)
m_dwLastGotTagSwitchNotifyST — ST-chip specific tag switch state (0 or 1)
```

Key log strings for state tracking:
- `"m_dwInternalStatus = %d"` — numeric state value
- `"g_dwLastGotTagSwitchNotify = 1, queued."` — duplicate event suppression
- `"m_dwLastGotTagSwitchNotifyST == 0"` / `"== 1"` — ST chip state
- `"Keystone changed (%s -> %s) during sleep, handling..."` — power resume delta

### Power Management
- `"Power resumed.."` — sleep/resume handler
- `"Going to invoke DoNotifyThread after power resumed..."` — re-check after wake
- `"KeyStone Service Power Status Peeker"` — monitors AC/DC transitions
- `"Create Power Status Peeker Failed"` — fallback when peeker unavailable

### Card State Fields (all tracked in plugin, NOT via PC/SC)
| Field | Purpose |
|-------|---------|
| `CardExist` | Card physically present (from HID event) |
| `CardPlugin` | Card was inserted (plug-in event fired) |
| `CardPaired` | Card paired to this device |
| `CardBindAccount` | Card bound to ASUS account |
| `CardAuthorized` | Card authorized for features |
| `CardActivated` | Card fully activated |
| `CardUnlock` | Used to unlock shadow drive/Windows |
| `CardUID` | UID read via PC/SC |
| `CardData` | Block data read via PC/SC |
| `CardSSNNEW` | Serial number (server-side lookup) |
| `CardLight` | LED/Aura state |
| `CardSound` | Sound event state |
| `CardLaunchSetting` | Quick launch app setting |

### Plug-Out Flow (discovered from strings)
```
HandlePlugOut()!
  → "No CardPaired PlugOut" (if not paired)
  → "Notify plug-out."
  → "Plug-Out LockWindows" (if unlock enabled)
  → "Plug-Out Stealth" (if stealth enabled)
  → Update m_dwInternalStatus
```

**Critical insight**: `HandlePlugOut()` fires from a **HID removal event**,
NOT from PC/SC SCARD_STATE_EMPTY.  This is why AC maintains persistent "Enchufada"
(plugged-in) state even after killing RF — it only transitions to "unplugged" when
the HID device reports physical card removal.

### Complete PC/SC Error String Table
The DLL contains a full SCard error string lookup table (55+ entries) including:
`SCard sharing violation`, `SCard timeout`, `SCard no smartcard`,
`SCard warning removed card`, `SCard warning unpowered card`, etc.
These are used for the `"Error 0x%04X %s"` log format strings.

### Registry & File Paths
```
SOFTWARE\ASUS\ARMOURY CRATE Service\SoulkeyPlugin\DataCollection
%APPDATA%\ASUS\SoulKey\
%APPDATA%\ASUS\SoulKey\SoulKeyPlugin_Status.ini
```

### Sound Integration
```
AppEvents\Schemes\Apps\.Default\ProximityConnection\.Current
AppEvents\Schemes\Apps\.Default\ProximityConnection\.Default
"Write Sound Registry Before Read"
"Write Sound Registry After Read"
```

### ATKACPI Device Path and WMI Events
`\\.\ATKACPI` — opened for BIOS event notifications:
`"ACPI Notification through ATKHotkey from BIOS"`

This ATKACPI layer also broadcasts a generic WMI event whenever the Keystone hardware state changes. By monitoring the `root\wmi` namespace for the `AsusAtkWmiEvent` class, we observe that an event with `EventID = 180` fires upon **both** physical card insertion and physical card removal. 

Because `EventID 180` does not inherently distinguish between "in" and "out", any monitor using it must track its own state (e.g., if the card is currently considered inserted, and Event 180 fires, it must be a removal; if the card is absent, it must be an insertion).

---

## Open Questions (for experiments)

1. ~~What is the `dwDisposition` value in `SCardDisconnect`?~~
   - **ANSWERED**: `SCARD_UNPOWER_CARD` — confirmed by behavior.
2. ~~What are the exact APDUs sent in `ApduGetUID` and `ApduGetData`?~~
   - **ANSWERED**: GetUID = `FF CA 00 00 00`. GetData = `FF B0 00 00 04` (block 0).
3. ~~What data does the card store?~~
   - **ANSWERED**: Block 0 = `01 01 01 01` (4 bytes, only readable block). UID = 8 bytes.
4. How does `SetShadowDriveStatus` work — is this BitLocker or custom?
   - NEW: `"VolumeKeyProtectorID"` string suggests BitLocker key protector integration
   - NEW: `"RemoveShadowDriverData %d"`, `"KeyStoneRemoveShadowDriverData"` — cleanup API
5. ~~What is the "cooling down time" mentioned in the timeout message?~~
   - **ANSWERED**: This is the delay between HID trigger and PC/SC card check. If card
     is not detectable via PC/SC after this timeout: `"Card is NOT present after cooling down time!"`
6. Can the HID path (ST chip) be used independently of PC/SC?
   - PARTIALLY: `HandlePlugInST()` uses `HID\VID_0483&PID_5750&REV_0200` path
7. ~~What does ATKACPI respond to?~~
   - **ANSWERED**: `\\.\ATKACPI` opens for ACPI notifications via ATKHotkey. This is also exposed via WMI as `AsusAtkWmiEvent` (EventID 180). This WMI event fires on physical insertions and removals.

---

## Files to Analyze Next

- `ArmouryCrate.ServiceCore.dll` — core service (may contain shared crypto/auth)
- `ArmouryCrate.DevicePlugin.dll` — device management
- `ArmouryCrate.SystemFeature.dll` — system feature integration
- Any DLL in `SystemDevicePlugin/`
