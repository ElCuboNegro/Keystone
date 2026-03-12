# ACR122U — Complete Command Reference
## Technical Reference for NFC/RFID Agent

---

## Hardware Overview

| Property | Value |
|----------|-------|
| NFC Chip | NXP PN532 |
| Interface | USB Full Speed (12 Mbps) |
| USB Class | CCID (smart card reader) |
| Protocols | ISO 14443 A/B, ISO 15693, FeliCa, Mifare, NDEF |
| Frequency | 13.56 MHz |
| PC/SC compliant | Yes (presents as CCID device) |
| Escape commands | Via `SCardControl` with IOCTL_CCID_ESCAPE |

Because it uses CCID, the OS presents it as a standard smart card reader.
Commands to the PN532 chip itself go through **escape commands** wrapped in `SCardControl`.

---

## PC/SC Pseudo-APDUs (via SCardTransmit)

These are handled by the ACR122U firmware, NOT forwarded to the card.

### Get UID / Serial Number
```
Command:  FF CA 00 00 00
Response: <UID bytes> 90 00        (success)
          63 00                     (no card present)
```

### Get ATS (Answer To Select) — ISO 14443A only
```
Command:  FF CA 01 00 00
Response: <ATS bytes> 90 00
```

### Load Authentication Keys (Mifare only)
```
Command:  FF 82 <P1> <key_num> 06 <key[6]>
P1: 00=Key A, 01=Key B
key_num: 00 or 01 (key slot)
```

### Authenticate Block (Mifare only)
```
Command:  FF 86 00 00 05 01 00 <block> <key_type> <key_num>
key_type: 60=Key A, 61=Key B
```

### Read Binary (NFC / Mifare)
```
Command:  FF B0 00 <block_num> <Le>
Response: <data[Le]> 90 00
```
- For Mifare Classic: block_num = 0..63 (1K) or 0..255 (4K)
- For ISO 15693: block_num = block index

### Update Binary (NFC / Mifare)
```
Command:  FF D6 00 <block_num> <Lc> <data[Lc]>
Response: 90 00
```

### Manage Session / LED+Buzzer Control
```
Command:  FF 00 40 <LED_state> 04 <T1> <T2> <rep> <buzzer>
LED_state: bit0=red_final, bit1=green_final, bit2=red_blink, bit3=green_blink
T1: initial blink duration (units of 100ms)
T2: toggle blink duration  (units of 100ms)
rep: number of blinks
buzzer: 00=off, 01=T1, 02=T2, 03=both
```

### Get Firmware Version
```
Command:  FF 00 48 00 00
Response: <version_string> 90 00
```

---

## PN532 Direct Commands (via SCardControl escape)

For low-level PN532 access, wrap PN532 commands in escape APDUs:
```
SCardControl(hCard, IOCTL_CCID_ESCAPE,
    inBuffer, inLen, outBuffer, outLen, &returned)
```
Where `inBuffer` = `FF 00 00 00 <Lc> <PN532_command>`

### PN532 Command/Response framing
- Host→PN532: command code = `D4 <cmd>`
- PN532→Host: response code = `D5 <cmd+1>`

### Essential PN532 Commands

#### SAMConfiguration — Configure Secure Access Module
```
D4 14 <mode> [timeout] [IRQ]
mode: 01=Normal (SAM not used), 02=Virtual, 03=Wired, 04=Dual
timeout: 14 = 50ms unit
```
Almost always called first with mode=01:
```
FF 00 00 00 03  D4 14 01
```
Response: `D5 15 00` (00 = success)

#### GetFirmwareVersion
```
D4 02
```
Response: `D5 03 <IC> <Ver> <Rev> <Support>`
- IC: 07 = PN532

#### RFConfiguration — Control RF field and timing
```
D4 32 <item> <data...>
```

| Item | Description | Data |
|------|-------------|------|
| 0x01 | RF Field | 01=ON, 00=OFF, 03=ON+auto-RFCA |
| 0x02 | Various timers | ATR_RES_TIMEOUT, RetryCount |
| 0x04 | MaxRtyCOM | retry count for RF comm |
| 0x05 | MaxRetries | InListPassiveTarget retry |
| 0x0A | Analog settings 14443A | |
| 0x0B | Analog settings 14443B | |
| 0x0C | Analog settings ISO15693 | |

**Turn RF field ON:**
```
FF 00 00 00 04  D4 32 01 01
```
**Turn RF field OFF:**
```
FF 00 00 00 04  D4 32 01 00
```
**Set retry count to 0 (don't wait for card):**
```
FF 00 00 00 05  D4 32 05 00 00 00
```
**Set timeout (ATR response timeout):**
```
FF 00 00 00 05  D4 32 02 00 0B 0A
```

#### InListPassiveTarget — Detect/select card
```
D4 4A <MaxTg> <BrTy> [InitiatorData]
MaxTg: max targets (01 = find one)
BrTy:  00=ISO14443A/106kbps, 01=ISO14443B/106kbps, 02=FeliCa/212, 03=FeliCa/424, 04=ISO14443A/passive, 05=Innovision Jewel, 06=ISO15693
```

**Detect ISO 15693 card:**
```
FF 00 00 00 04  D4 4A 01 06
```
Response: `D5 4B 01 01 <length> <ATQB_or_ATQA> ...`

#### InDataExchange — Send APDU to selected card
```
D4 40 <Tg> <data...>
Tg: target number (01 = first target)
```

#### InCommunicateThru — Raw bytes to/from card (no framing)
```
D4 42 <data...>
```
Useful for ISO 15693 custom commands.

#### InSelectPassiveTarget
```
D4 54 <Tg>
```

#### InDeselect
```
D4 44 <Tg>
```

#### InRelease
```
D4 52 <Tg>
```

---

## IOCTL Control Codes

| Platform | IOCTL_CCID_ESCAPE value |
|----------|------------------------|
| Windows | `0x00312000` (SCARD_CTL_CODE(3136)) |
| Linux (pcsclite) | `0x42000001` |

In code:
```c
// Windows
#define IOCTL_CCID_ESCAPE SCARD_CTL_CODE(3136)

// Linux (pcsc-lite)
#define IOCTL_CCID_ESCAPE 0x42000001
```

Python (pyscard):
```python
IOCTL_CCID_ESCAPE = 0x00312000  # Windows
# or
IOCTL_CCID_ESCAPE = 0x42000001  # Linux
connection.control(IOCTL_CCID_ESCAPE, command_bytes)
```

---

## ISO 15693 via ACR122U Step by Step

### 1. Connect to reader (no card needed for DIRECT mode)
```c
SCardConnect(hCtx, readerName,
    SCARD_SHARE_DIRECT,     // important: direct mode
    0,                       // no protocol needed
    &hCard, &dwProto)
```

### 2. Configure PN532 for ISO 15693
```c
// SAMConfiguration
BYTE sam_cfg[] = {0xFF,0x00,0x00,0x00,0x03,0xD4,0x14,0x01};
SCardControl(hCard, IOCTL_CCID_ESCAPE, sam_cfg, 8, resp, sizeof(resp), &rlen);

// RFConfiguration: set analog settings for ISO 15693
BYTE rf_cfg[] = {0xFF,0x00,0x00,0x00,0x09,
    0xD4,0x32,0x0C,            // RFConfiguration, item 0x0C (ISO15693 analog)
    0xFF,0x17,0x80,0x13,0x01,0x80};  // typical values
SCardControl(hCard, IOCTL_CCID_ESCAPE, rf_cfg, 15, resp, sizeof(resp), &rlen);
```

### 3. Detect ISO 15693 card
```c
BYTE detect[] = {0xFF,0x00,0x00,0x00,0x04, 0xD4,0x4A,0x01,0x06};
SCardControl(hCard, IOCTL_CCID_ESCAPE, detect, 9, resp, sizeof(resp), &rlen);
// resp contains: D5 4B 01 [card data]
```

### 4. Send ISO 15693 INVENTORY command
```c
// Flags: 0x26 = high data rate, 16 slots, inventory mode
BYTE inv[] = {0xFF,0x00,0x00,0x00,0x05,
    0xD4,0x42,           // InCommunicateThru
    0x26,0x01,0x00};     // Flags, INVENTORY cmd, Mask_len=0
SCardControl(hCard, IOCTL_CCID_ESCAPE, inv, 10, resp, sizeof(resp), &rlen);
```

---

## Common Failure Modes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Card read for ~100ms then stops | `SCardDisconnect(SCARD_UNPOWER_CARD)` | Use `SCARD_LEAVE_CARD` |
| Can't detect ISO 15693, only 14443 works | Auto-poll cycle too fast | Disable auto-poll, use manual InListPassiveTarget |
| `SCARD_E_NOT_TRANSACTED` | Missing SCardBeginTransaction | Add transaction wrapping |
| IOCTL_CCID_ESCAPE returns error on Linux | Wrong IOCTL value | Use `0x42000001` on Linux |
| SCardControl fails entirely | Reader connected with SCARD_SHARE_SHARED (not DIRECT) | Use SCARD_SHARE_DIRECT for escape commands |
| Card detected but SCardTransmit fails | Protocol mismatch | Check dwActiveProtocol, use SCARD_PROTOCOL_T1 for NFC |
| PN532 returns error D5 xx 01 | Command error | D5[cmd+1], last byte=error code; 01=timeout waiting for card |

---

## Useful Diagnostic Sequence

```python
# Python diagnostic — paste into any Python REPL with pyscard installed
from smartcard.System import readers
from smartcard.util import toHexString

r = readers()
print("Readers:", r)

c = r[0].createConnection()
c.connect(protocol=3)  # protocol=3 = T0|T1

# Get firmware version
fw, sw1, sw2 = c.transmit([0xFF, 0x00, 0x48, 0x00, 0x00])
print("FW:", toHexString(fw))

# SAM config
sam, sw1, sw2 = c.transmit([0xFF, 0x00, 0x00, 0x00, 0x03, 0xD4, 0x14, 0x01])
print("SAM:", toHexString(sam), f"{sw1:02X}{sw2:02X}")

# Detect ISO 15693
det, sw1, sw2 = c.transmit([0xFF, 0x00, 0x00, 0x00, 0x04, 0xD4, 0x4A, 0x01, 0x06])
print("ISO15693 detect:", toHexString(det), f"{sw1:02X}{sw2:02X}")

# Get UID
uid, sw1, sw2 = c.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
print("UID:", toHexString(uid), f"{sw1:02X}{sw2:02X}")
```
