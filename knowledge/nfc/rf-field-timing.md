# RF Field Timing & The Millisecond Problem
## Root Cause Analysis Reference for NFC/RFID Agent

---

## The Problem Statement

> "The software reads the card for only milliseconds, then the card becomes unresponsive."

This is one of the most common NFC integration bugs. There are exactly **6 root causes**, ordered by likelihood.

---

## Root Cause 1: Wrong SCardDisconnect Disposition (Most Common)

### The code
```c
SCardDisconnect(hCard, SCARD_UNPOWER_CARD);  // ← kills RF field
```

### What happens
`SCARD_UNPOWER_CARD` instructs the CCID driver to cut power to the card interface.
For contact smart cards: harmless, just releases the physical contacts.
For NFC/contactless: **turns off the RF field**. The card loses power instantly.

### The fix
```c
SCardDisconnect(hCard, SCARD_LEAVE_CARD);    // ← card stays powered
```

### Disposition values explained
| Value | Name | Effect on NFC |
|-------|------|--------------|
| `SCARD_LEAVE_CARD` (0) | Leave | Card stays selected, field stays on |
| `SCARD_RESET_CARD` (1) | Reset | Card reset, field stays on |
| `SCARD_UNPOWER_CARD` (2) | Unpower | **RF field turns OFF** |
| `SCARD_EJECT_CARD` (3) | Eject | Reader-specific, often = unpower |

---

## Root Cause 2: Missing Transaction Wrapping

### The code
```c
SCardConnect(..., &hCard, &dwProto);
SCardTransmit(hCard, ...);   // first operation
// ... some processing time ...
SCardTransmit(hCard, ...);   // second operation → may fail
```

### What happens
Without `SCardBeginTransaction`, the PC/SC resource manager may:
- Deselect the card between API calls
- Allow another application to steal the reader
- Time out the implicit lock

### The fix
```c
SCardConnect(..., &hCard, &dwProto);
SCardBeginTransaction(hCard);
    SCardTransmit(hCard, ...);  // all operations inside transaction
    SCardTransmit(hCard, ...);
SCardEndTransaction(hCard, SCARD_LEAVE_CARD);
SCardDisconnect(hCard, SCARD_LEAVE_CARD);
```

---

## Root Cause 3: ACR122U Auto-Polling Cycle

### What happens
The ACR122U firmware, by default, runs an **auto-polling loop**:
```
ISO 14443A poll → ISO 14443B poll → ISO 15693 poll → Felica poll → repeat
```

Between polls, the RF field may briefly drop (configurable via PN532 register).
This causes the card to lose power mid-read if your code catches the card during one protocol's window but the poll moves on.

### How to detect it
- Card is detected intermittently even with no code changes
- Higher reliability when physically holding card very still
- Problem worse with ISO 15693 than ISO 14443 (15693 appears later in poll cycle)

### The fix
Disable auto-poll and control card detection manually:
```c
// Option A: Connect with SCARD_SHARE_DIRECT, send PN532 command to stop auto-poll
BYTE stop_poll[] = {0xFF, 0x00, 0x00, 0x00, 0x05,
    0xD4, 0x60,   // InSetParameters (PN532 cmd 0x60)
    0x01,         // BrTy = ISO 14443A
    0x00,         // disable
    0x00};
SCardControl(hCard, IOCTL_CCID_ESCAPE, stop_poll, ...);

// Option B: Use RFConfiguration to set retry to 0
BYTE rf_cfg[] = {0xFF, 0x00, 0x00, 0x00, 0x05,
    0xD4, 0x32,   // RFConfiguration
    0x05,         // MaxRetries item
    0xFF,         // MxRtyATR: infinite (0xFF)
    0x01,         // MxRtyPSL: 1 retry
    0x01};        // MxRtyPassiveActivation: 1 retry
```

---

## Root Cause 4: SCardGetStatusChange Timeout Too Short

### The code
```c
// Polling loop
while(running) {
    SCARD_READERSTATE rs = { readerName, NULL, SCARD_STATE_UNAWARE };
    LONG rv = SCardGetStatusChange(hCtx, 0, &rs, 1);  // timeout = 0 (immediate!)
    if (rs.dwEventState & SCARD_STATE_PRESENT) {
        handle_card();  // card present
    }
}
```

### What happens
`dwTimeout = 0` returns immediately (polling, not blocking).
The tight loop causes the PC/SC daemon to rapidly toggle card state detection,
which can cause the driver to repeatedly select/deselect the card.

### The fix
```c
// Block until state changes, with reasonable timeout
LONG rv = SCardGetStatusChange(hCtx, INFINITE, &rs, 1);
// Or with timeout: 500ms
LONG rv = SCardGetStatusChange(hCtx, 500, &rs, 1);
```

---

## Root Cause 5: Protocol Mismatch

### What happens
ISO 15693 cards on ACR122U may be presented under an unexpected protocol.
If `SCardConnect` is called with `SCARD_PROTOCOL_T0` only, and the card appears as T1 or raw, the connection may fail and the PC/SC layer may immediately disconnect.

### The fix
```c
// Accept any protocol
SCardConnect(hCtx, readerName,
    SCARD_SHARE_SHARED,
    SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1,  // accept both
    &hCard, &dwActiveProtocol);

// Or for direct reader access (no protocol needed):
SCardConnect(hCtx, readerName,
    SCARD_SHARE_DIRECT,
    0,   // no protocol
    &hCard, &dwActiveProtocol);
```

---

## Root Cause 6: CCID Driver Timing Parameters

### What happens
The CCID driver has configurable timeouts for card power-up, ATR reading, etc.
On some systems these are set too short for ISO 15693 (which has a slower response than ISO 14443).

ISO 15693 typical response time: ~10ms at low data rate
ISO 14443A typical response time: <5ms
If driver timeout is set to 5ms, ISO 15693 will always fail.

### How to detect
- ISO 14443 (Mifare) cards work fine, ISO 15693 doesn't
- Works on some machines but not others (different driver versions)

### The fix (PN532 level)
```c
// Set ATR response timeout: item 0x02
// Byte 0: ATR_RES_TIMEOUT (0=disabled, 0x0B = ~100ms)
// Byte 1: RetryCount
BYTE timeout[] = {0xFF, 0x00, 0x00, 0x00, 0x04,
    0xD4, 0x32, 0x02,   // RFConfiguration, item 0x02
    0x0B};               // ATR_RES_TIMEOUT ≈ 100ms
SCardControl(hCard, IOCTL_CCID_ESCAPE, timeout, 9, ...);
```

---

## Diagnostic Decision Tree

```
Card readable for only ~ms?
│
├─ Does it work with SCARD_LEAVE_CARD in SCardDisconnect?
│   YES → Root Cause 1. Fix: change disposition.
│
├─ Does adding SCardBeginTransaction fix it?
│   YES → Root Cause 2. Fix: wrap in transaction.
│
├─ Is it intermittent even without code changes?
│   YES → Root Cause 3. Fix: disable auto-poll.
│
├─ Is SCardGetStatusChange timeout=0 in a loop?
│   YES → Root Cause 4. Fix: use INFINITE or 500ms timeout.
│
├─ Does ISO 14443 work but ISO 15693 doesn't?
│   YES → Root Cause 5 or 6. Fix: protocol flags or PN532 timeout.
│
└─ None of the above?
    → Check: is SCardDisconnect being called from a finalizer/destructor
      that runs immediately after the read? That's Root Cause 1 via RAII.
```

---

## Complete Working Pattern (C)

```c
SCARDCONTEXT hCtx;
SCARDHANDLE  hCard;
DWORD        dwProto;
LONG         rv;

// 1. Establish context
rv = SCardEstablishContext(SCARD_SCOPE_USER, NULL, NULL, &hCtx);
assert(rv == SCARD_S_SUCCESS);

// 2. Connect (accept T0 or T1)
rv = SCardConnect(hCtx, readerName,
    SCARD_SHARE_SHARED,
    SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1,
    &hCard, &dwProto);
assert(rv == SCARD_S_SUCCESS);

// 3. Lock card for exclusive access
rv = SCardBeginTransaction(hCard);
assert(rv == SCARD_S_SUCCESS);

// 4. Read UID
BYTE cmd[] = {0xFF, 0xCA, 0x00, 0x00, 0x00};
BYTE resp[256];
DWORD respLen = sizeof(resp);
SCARD_IO_REQUEST pci = {dwProto, sizeof(SCARD_IO_REQUEST)};
rv = SCardTransmit(hCard, &pci, cmd, sizeof(cmd), NULL, resp, &respLen);

// 5. Process...

// 6. Release — LEAVE the card powered!
SCardEndTransaction(hCard, SCARD_LEAVE_CARD);
SCardDisconnect(hCard, SCARD_LEAVE_CARD);  // ← NOT SCARD_UNPOWER_CARD
SCardReleaseContext(hCtx);
```

---

## Complete Working Pattern (Python/pyscard)

```python
from smartcard.System import readers
from smartcard.CardConnection import CardConnection
from smartcard.util import toHexString
import time

r = readers()
conn = r[0].createConnection()

# Connect with T0|T1 protocol
conn.connect(CardConnection.T0_protocol | CardConnection.T1_protocol)

# No explicit transaction API in pyscard, but we can do:
# Keep connection open, don't call disconnect between reads

GET_UID  = [0xFF, 0xCA, 0x00, 0x00, 0x00]
READ_BLK = [0xFF, 0xB0, 0x00, 0x00, 0x04]  # read block 0, 4 bytes

uid, sw1, sw2 = conn.transmit(GET_UID)
print(f"UID: {toHexString(uid)}")

for block in range(8):
    READ_BLK[3] = block
    data, sw1, sw2 = conn.transmit(READ_BLK)
    print(f"Block {block}: {toHexString(data)} [{sw1:02X}{sw2:02X}]")
    time.sleep(0.05)  # small delay between blocks is fine; don't disconnect

# When truly done:
conn.disconnect()  # pyscard uses SCARD_LEAVE_CARD by default
```
