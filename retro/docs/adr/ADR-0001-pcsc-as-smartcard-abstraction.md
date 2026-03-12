# ADR-0001: Use PC/SC (WinSCard / pcsc-lite) as the smart card abstraction layer

**Status:** accepted
**Deciders:** ASUS Keystone engineering team (inferred from DLL analysis)
**Date:** 2026-03-10
**Technical Story:** Reverse-engineered from `ArmouryCrate.SoulKeyServicePlugin.dll` — PDB path `D:\SourceCode\AC.Keystone\production_V6.4`

---

## Context and Problem Statement

The Keystone system needs to communicate with an NFC/smart card chip embedded in the motherboard.
How should the software layer access the hardware? Should it use a standard OS abstraction, a vendor SDK, or raw USB/I2C access?

---

## Decision Drivers

- Need to support the built-in NXP NFC chip (connected via I2C to the motherboard)
- Windows already provides a PC/SC service (WinSCard) for smart card readers
- The NXP chip is exposed as a PC/SC reader named `"Microsoft IFD 0"` via the NfcCx driver
- Standard PC/SC API (`SCardConnect`, `SCardTransmit`, etc.) enables portability to Linux via pcsc-lite

---

## Considered Options

- PC/SC (WinSCard on Windows / pcsc-lite on Linux) — standard OS API
- Vendor NXP SDK — direct I2C communication with the chip
- Raw Windows HID/USB — bypass OS abstraction entirely
- NFC Forum / libnfc — open-source NFC library (USB readers only)

---

## Decision Outcome

**Chosen option:** "PC/SC (WinSCard)", because it is the natural abstraction provided by Windows for the built-in NfcCx driver, requires no custom driver installation, and the same API is available on Linux via pcsc-lite.

### Positive Consequences

- Same `SCard*` function names work on Windows and Linux
- No need to ship or maintain a custom device driver
- Standard APDU commands work through the abstraction layer
- Reader management (enumeration, hot-plug) handled by the OS

### Negative Consequences

- NfcCx on Windows imposes constraints not present on standard PC/SC (escape commands disabled, session timeouts, SW=6981 kills session)
- Cannot use PN532-specific escape commands to control RF field behavior
- Linux equivalent requires a real external reader (ACR122U) — the built-in NfcCx chip has no Linux driver

---

## Pros and Cons of the Options

### PC/SC (WinSCard / pcsc-lite)

Standard industry API for smart card access, available on all major OSes.

- Good, because same API on Windows and Linux (header change only: `<winscard.h>` → `<PCSC/winscard.h>`)
- Good, because OS manages reader enumeration and driver lifecycle
- Good, because works with the built-in NfcCx reader on Windows
- Bad, because NfcCx restricts escape commands (all `SCardControl` calls return `ERROR_NOT_SUPPORTED`)
- Bad, because NfcCx session timeout (~4.5s) cannot be extended via escape commands

### Vendor NXP SDK

Direct communication with the NXP chip via I2C/internal bus.

- Good, because full control over RF field and timing
- Bad, because requires internal documentation not publicly available
- Bad, because Windows-only (tied to the specific motherboard hardware)
- Bad, because not portable at all

### Raw Windows HID/USB

Bypass PC/SC and send raw USB/HID commands to the device.

- Good, because full control over the protocol
- Bad, because requires reverse-engineering the internal USB protocol
- Bad, because not portable and fragile across driver updates

### libnfc

Open-source NFC library with direct chip access.

- Good, because cross-platform (Linux, macOS, Windows)
- Bad, because requires an external USB reader (ACR122U/PN532) — cannot access the built-in NfcCx chip
- Bad, because not suitable for the Windows path (NfcCx is not a libnfc-compatible device)

---

## Links

- Related: [ADR-0003](ADR-0003-nfccx-no-escape-commands.md) — NfcCx constraints
- Related: [ADR-0005](ADR-0005-linux-port-requires-acr122u.md) — Linux porting strategy
- Knowledge: `retro/knowledge/smartcard/pcsc-api.md`
