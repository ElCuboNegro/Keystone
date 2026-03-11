# PC/SC API — Complete Reference
## Technical Reference for Smart Card Agent

---

## What is PC/SC

PC/SC (Personal Computer/Smart Card) is the interoperability specification for smart card readers and applications.

| Component | Windows | Linux/macOS |
|-----------|---------|------------|
| Library | `winscard.dll` | `libpcsclite` |
| Header | `<winscard.h>` | `<PCSC/winscard.h>` |
| Service | `SCardSvr` (Windows) | `pcscd` daemon |
| Compile | Automatic | `pkg-config --cflags --libs libpcsclite` |
| Python | `pyscard` | `pyscard` (same) |

**The good news:** The API is nearly identical on Windows and Linux. Same function names, same parameters, same constants. The only differences are:
1. Header path (`winscard.h` vs `PCSC/winscard.h`)
2. IOCTL_CCID_ESCAPE value differs (see ACR122U manual)
3. Error codes are `LONG` on Windows, may differ slightly on Linux

---

## Context Management

### SCardEstablishContext
```c
LONG SCardEstablishContext(
    DWORD    dwScope,       // SCARD_SCOPE_USER or SCARD_SCOPE_SYSTEM
    LPCVOID  pvReserved1,   // NULL
    LPCVOID  pvReserved2,   // NULL
    LPSCARDCONTEXT phContext // [OUT] context handle
);
```
- `SCARD_SCOPE_USER`: context is per-user (most applications)
- `SCARD_SCOPE_SYSTEM`: system-wide context (services, daemons)
- Must be called before any other SCard function
- One context per thread is recommended

### SCardReleaseContext
```c
LONG SCardReleaseContext(SCARDCONTEXT hContext);
```
Always call when done. Releases all associated resources.

### SCardIsValidContext
```c
LONG SCardIsValidContext(SCARDCONTEXT hContext);
```
Returns `SCARD_S_SUCCESS` if context is valid and service is running.

---

## Reader Enumeration

### SCardListReaders
```c
LONG SCardListReaders(
    SCARDCONTEXT hContext,
    LPCSTR       mszGroups,    // NULL = all groups
    LPSTR        mszReaders,   // [OUT] multi-string buffer
    LPDWORD      pcchReaders   // [IN/OUT] buffer size
);
```

Two-pass pattern:
```c
DWORD dwLen = SCARD_AUTOALLOCATE;
LPTSTR mszReaders;
SCardListReaders(hCtx, NULL, (LPTSTR)&mszReaders, &dwLen);
// mszReaders is now a double-null-terminated multi-string
// e.g.: "ACS ACR122U 00\0ACS ACR122U 01\0\0"
SCardFreeMemory(hCtx, mszReaders);
```

Or fixed-buffer:
```c
DWORD dwLen = 0;
SCardListReaders(hCtx, NULL, NULL, &dwLen);  // get required size
char *buf = malloc(dwLen);
SCardListReaders(hCtx, NULL, buf, &dwLen);   // get names
```

### SCardListReaderGroups
```c
LONG SCardListReaderGroups(
    SCARDCONTEXT hContext,
    LPSTR        mszGroups,
    LPDWORD      pcchGroups
);
```

---

## Card Connection

### SCardConnect
```c
LONG SCardConnect(
    SCARDCONTEXT hContext,
    LPCSTR       szReader,          // reader name from SCardListReaders
    DWORD        dwShareMode,       // sharing mode
    DWORD        dwPreferredProtocols, // protocol(s) to use
    LPSCARDHANDLE phCard,           // [OUT] card handle
    LPDWORD      pdwActiveProtocol  // [OUT] negotiated protocol
);
```

**Share modes:**
| Value | Name | Use case |
|-------|------|----------|
| 1 | `SCARD_SHARE_EXCLUSIVE` | Only this process can access the card |
| 2 | `SCARD_SHARE_SHARED` | Multiple apps can share (default for most apps) |
| 3 | `SCARD_SHARE_DIRECT` | Direct reader access, no card needed |

**Protocol flags:**
| Value | Name | Use case |
|-------|------|----------|
| 0x00000001 | `SCARD_PROTOCOL_T0` | ISO 7816 T=0 (byte-oriented) |
| 0x00000002 | `SCARD_PROTOCOL_T1` | ISO 7816 T=1 (block-oriented) |
| 0x00000003 | `T0 \| T1` | Accept either (recommended) |
| 0x00010000 | `SCARD_PROTOCOL_RAW` | Raw protocol (no framing) |
| 0x00020000 | `SCARD_PROTOCOL_UNDEFINED` | No protocol (use with DIRECT) |

### SCardReconnect
```c
LONG SCardReconnect(
    SCARDHANDLE hCard,
    DWORD       dwShareMode,
    DWORD       dwPreferredProtocols,
    DWORD       dwInitialization,  // SCARD_LEAVE_CARD / SCARD_RESET_CARD / SCARD_UNPOWER_CARD
    LPDWORD     pdwActiveProtocol
);
```
Reconnect to an already-connected card without full disconnect/connect cycle.

### SCardDisconnect
```c
LONG SCardDisconnect(
    SCARDHANDLE hCard,
    DWORD       dwDisposition  // what to do with the card on disconnect
);
```

**Disposition values — CRITICAL for NFC:**
| Value | Name | NFC effect |
|-------|------|-----------|
| 0 | `SCARD_LEAVE_CARD` | Card stays as-is (SAFE) |
| 1 | `SCARD_RESET_CARD` | Card reset, but field stays on |
| 2 | `SCARD_UNPOWER_CARD` | RF field turns OFF (DANGEROUS for NFC) |
| 3 | `SCARD_EJECT_CARD` | Reader-specific, often = unpower |

---

## Transactions

### SCardBeginTransaction
```c
LONG SCardBeginTransaction(SCARDHANDLE hCard);
```
Locks the card exclusively for the calling thread.
Other applications wanting the same reader will block until `SCardEndTransaction`.
**Required for multi-step operations** (read-then-write, sequential block reads).

### SCardEndTransaction
```c
LONG SCardEndTransaction(
    SCARDHANDLE hCard,
    DWORD       dwDisposition  // same values as SCardDisconnect
);
```
Releases the lock. Use `SCARD_LEAVE_CARD` for NFC.

---

## Data Exchange

### SCardTransmit
```c
LONG SCardTransmit(
    SCARDHANDLE         hCard,
    LPCSCARD_IO_REQUEST pioSendPci,   // protocol descriptor
    LPCBYTE             pbSendBuffer, // APDU command bytes
    DWORD               cbSendLength, // command length
    LPSCARD_IO_REQUEST  pioRecvPci,   // NULL usually
    LPBYTE              pbRecvBuffer, // [OUT] response
    LPDWORD             pcbRecvLength // [IN/OUT] response buffer size / actual length
);
```

Protocol descriptors (global constants):
```c
SCARD_IO_REQUEST pci;
pci.dwProtocol  = dwActiveProtocol;
pci.cbPciLength = sizeof(SCARD_IO_REQUEST);

// Or use predefined globals:
// g_rgSCardT0Pci  for T=0
// g_rgSCardT1Pci  for T=1
// g_rgSCardRawPci for raw
```

### SCardControl
```c
LONG SCardControl(
    SCARDHANDLE hCard,
    DWORD       dwControlCode,   // IOCTL code
    LPCVOID     lpInBuffer,      // command bytes
    DWORD       nInBufferSize,
    LPVOID      lpOutBuffer,     // [OUT] response
    DWORD       nOutBufferSize,
    LPDWORD     lpBytesReturned  // [OUT] actual response length
);
```
Used for escape/vendor commands (e.g., PN532 direct commands on ACR122U).
Requires `SCARD_SHARE_DIRECT` connection mode.

---

## Status and Monitoring

### SCardStatus
```c
LONG SCardStatus(
    SCARDHANDLE hCard,
    LPSTR       szReaderName,   // [OUT] reader name buffer
    LPDWORD     pcchReaderLen,  // [IN/OUT] reader name length
    LPDWORD     pdwState,       // [OUT] card state
    LPDWORD     pdwProtocol,    // [OUT] current protocol
    LPBYTE      pbAtr,          // [OUT] ATR bytes
    LPDWORD     pcbAtrLen       // [IN/OUT] ATR length
);
```

Card states:
| Value | Name | Meaning |
|-------|------|---------|
| 0 | `SCARD_UNKNOWN` | Reader unknown |
| 1 | `SCARD_ABSENT` | No card |
| 2 | `SCARD_PRESENT` | Card present, not powered |
| 4 | `SCARD_SWALLOWED` | Card present, not responsive |
| 5 | `SCARD_POWERED` | Card powered, ATR not read |
| 6 | `SCARD_NEGOTIABLE` | Card ready, protocol not selected |
| 7 | `SCARD_SPECIFIC` | Card ready, protocol selected |

### SCardGetStatusChange
```c
LONG SCardGetStatusChange(
    SCARDCONTEXT          hContext,
    DWORD                 dwTimeout,    // ms; INFINITE = block forever
    LPSCARD_READERSTATE   rgReaderStates, // array of reader states
    DWORD                 cReaders      // count of readers
);
```

`SCARD_READERSTATE` structure:
```c
typedef struct {
    LPCSTR  szReader;       // reader name
    LPVOID  pvUserData;     // user data pointer
    DWORD   dwCurrentState; // current known state
    DWORD   dwEventState;   // [OUT] new state
    DWORD   cbAtr;          // [OUT] ATR length
    BYTE    rgbAtr[36];     // [OUT] ATR bytes
} SCARD_READERSTATE;
```

Usage pattern:
```c
SCARD_READERSTATE rs;
rs.szReader = "ACS ACR122U 00";
rs.pvUserData = NULL;
rs.dwCurrentState = SCARD_STATE_UNAWARE;  // first call: don't know current state

// Block until something changes
while (1) {
    SCardGetStatusChange(hCtx, INFINITE, &rs, 1);
    if (rs.dwEventState & SCARD_STATE_PRESENT) {
        // card inserted
    } else if (rs.dwEventState & SCARD_STATE_EMPTY) {
        // card removed
    }
    rs.dwCurrentState = rs.dwEventState;  // update for next iteration
}
```

Event state flags:
| Bit | Name | Meaning |
|-----|------|---------|
| 0x0001 | `SCARD_STATE_IGNORE` | Ignore this reader |
| 0x0002 | `SCARD_STATE_CHANGED` | State has changed |
| 0x0004 | `SCARD_STATE_UNKNOWN` | Reader unknown |
| 0x0008 | `SCARD_STATE_UNAVAILABLE` | Reader unavailable |
| 0x0010 | `SCARD_STATE_EMPTY` | No card present |
| 0x0020 | `SCARD_STATE_PRESENT` | Card present |
| 0x0040 | `SCARD_STATE_ATRMATCH` | ATR matches target |
| 0x0080 | `SCARD_STATE_EXCLUSIVE` | Card exclusively used |
| 0x0100 | `SCARD_STATE_INUSE` | Card in use |
| 0x0200 | `SCARD_STATE_MUTE` | No ATR received |
| 0x0400 | `SCARD_STATE_UNPOWERED` | Card not powered |

---

## Reader Attributes

### SCardGetAttrib
```c
LONG SCardGetAttrib(
    SCARDHANDLE hCard,
    DWORD       dwAttrId,   // attribute ID
    LPBYTE      pbAttr,     // [OUT] attribute value
    LPDWORD     pcbAttrLen  // [IN/OUT] buffer size / actual length
);
```

Common attribute IDs:
| ID | Name | Returns |
|----|------|---------|
| 0x00010100 | `SCARD_ATTR_VENDOR_NAME` | Reader vendor name string |
| 0x00010102 | `SCARD_ATTR_VENDOR_IFD_TYPE` | Reader model string |
| 0x00010103 | `SCARD_ATTR_VENDOR_IFD_VERSION` | Firmware version |
| 0x00020110 | `SCARD_ATTR_ICC_TYPE_PER_ATR` | Card type |
| 0x00090300 | `SCARD_ATTR_CURRENT_PROTOCOL_TYPE` | Current protocol |

---

## Return Codes

| Code | Hex | Meaning |
|------|-----|---------|
| `SCARD_S_SUCCESS` | 0x00000000 | Success |
| `SCARD_E_CANCELLED` | 0x80100002 | Action cancelled |
| `SCARD_E_INVALID_HANDLE` | 0x80100003 | Invalid handle |
| `SCARD_E_INVALID_PARAMETER` | 0x80100004 | Bad parameter |
| `SCARD_E_INVALID_TARGET` | 0x80100005 | Invalid target |
| `SCARD_E_NO_MEMORY` | 0x80100006 | Out of memory |
| `SCARD_E_INSUFFICIENT_BUFFER` | 0x80100008 | Buffer too small |
| `SCARD_E_UNKNOWN_READER` | 0x80100009 | Reader not found |
| `SCARD_E_TIMEOUT` | 0x8010000A | Timeout expired |
| `SCARD_E_SHARING_VIOLATION` | 0x8010000B | Reader in use |
| `SCARD_E_NO_SMARTCARD` | 0x8010000C | No card in reader |
| `SCARD_E_UNKNOWN_CARD` | 0x8010000D | Card not recognized |
| `SCARD_E_CANT_DISPOSE` | 0x8010000E | Cannot dispose handle |
| `SCARD_E_PROTO_MISMATCH` | 0x8010000F | Protocol mismatch |
| `SCARD_E_NOT_READY` | 0x80100010 | Subsystem not ready |
| `SCARD_E_INVALID_VALUE` | 0x80100011 | Invalid value |
| `SCARD_E_SYSTEM_CANCELLED` | 0x80100012 | Internal cancel |
| `SCARD_E_COMM_ERROR` | 0x80100013 | Communication error |
| `SCARD_E_UNKNOWN_ERROR` | 0x80100014 | Unknown error |
| `SCARD_E_INVALID_ATR` | 0x80100015 | Invalid ATR |
| `SCARD_E_NOT_TRANSACTED` | 0x80100016 | Transaction required |
| `SCARD_E_READER_UNAVAILABLE` | 0x80100017 | Reader unavailable |
| `SCARD_W_UNSUPPORTED_CARD` | 0x80100065 | Card unsupported |
| `SCARD_W_UNRESPONSIVE_CARD` | 0x80100066 | Card not responding |
| `SCARD_W_UNPOWERED_CARD` | 0x80100067 | Card not powered |
| `SCARD_W_RESET_CARD` | 0x80100068 | Card was reset |
| `SCARD_W_REMOVED_CARD` | 0x80100069 | Card removed |
| `SCARD_E_NO_SERVICE` | 0x8010001D | PC/SC service not running |
| `SCARD_E_SERVICE_STOPPED` | 0x8010001E | Service stopped |

---

## Linux-Specific Notes

### Starting pcscd
```bash
sudo pcscd --foreground --debug  # debug mode
sudo systemctl start pcscd       # systemd
```

### Python (pyscard)
```python
from smartcard.System import readers
from smartcard.CardConnection import CardConnection

r = readers()                    # list readers
c = r[0].createConnection()
c.connect()                      # connects with T0|T1
data, sw1, sw2 = c.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
c.disconnect()
```

### C on Linux
```c
#include <PCSC/winscard.h>    // note: PCSC/ prefix
#include <PCSC/wintypes.h>

// Compile:
// gcc myapp.c $(pkg-config --cflags --libs libpcsclite) -o myapp
```
