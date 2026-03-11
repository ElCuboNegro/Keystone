# ADR-0003: NfcCx (Microsoft IFD 0) as NFC reader — escape commands unsupported

**Status:** accepted
**Deciders:** ASUS hardware design team (board-level decision); Microsoft (NfcCx driver constraints)
**Date:** 2026-03-10
**Technical Story:** Discovered via DLL analysis of `NxpNfcClientDriver.dll` and confirmed via `SCardControl` probing in experiments. IOCTL range 0x310004–0x313208 probed — all rejected.

---

## Context and Problem Statement

The ASUS ROG motherboard includes a built-in NXP NFC chip connected via I2C.
This chip is exposed to Windows via the NfcCx (NFC Class Extension) driver as a PC/SC reader named `"Microsoft IFD 0"`.
NfcCx is a Microsoft driver framework — not a vendor driver.
What are the constraints this imposes, and how do they differ from an external ACR122U?

---

## Decision Drivers

- Hardware choice: NXP chip soldered onto motherboard, accessed via I2C, driven by NfcCx
- NfcCx is a Windows-platform driver — provides PC/SC compatibility but restricts low-level access
- Application relies on PC/SC abstraction (`SCard*` API)
- No PN532 chip present — no PN532 escape command support

---

## Considered Options

- Use NfcCx built-in driver (current) — PC/SC compatible, no escape commands
- Use external ACR122U USB reader — full escape command support via CCID
- Use vendor NXP SDK — direct I2C access, full control
- Use libnfc — requires USB reader, not applicable to I2C chip

---

## Decision Outcome

**Chosen option:** "NfcCx built-in driver", because the NXP chip is soldered to the board and there is no alternative driver path on Windows. This is a hardware constraint, not a software preference.

### Positive Consequences

- No additional hardware required — works with built-in chip
- PC/SC API is available — standard APDU commands work
- Windows manages driver lifecycle

### Negative Consequences

- ALL `SCardControl` escape commands return `ERROR_NOT_SUPPORTED (0x32)` — RF field cannot be controlled programmatically
- `GET_SYSTEM_INFORMATION` (FF 30 / FF 2B) returns `SW=6A81` — card memory layout cannot be queried
- Reading a non-existent block returns `SW=6981` which **terminates the entire RF session** (not just the command)
- Session timeout ~4.5s under SHARED mode — cannot be extended
- No Linux equivalent — NfcCx is Windows-only; Linux port must use external USB reader

---

## Pros and Cons of the Options

### NfcCx built-in driver (chosen)

Windows NFC Class Extension driver — PC/SC compatible, Microsoft-managed.

- Good, because no additional hardware needed
- Good, because standard PC/SC API works
- Bad, because ALL escape commands rejected
- Bad, because SW=6981 kills entire RF session (not just the failing command)
- Bad, because no Linux driver exists

### External ACR122U USB reader

CCID-class USB NFC reader with PN532 inside.

- Good, because full escape command support (IOCTL_CCID_ESCAPE = 0x312000)
- Good, because PN532 RFConfiguration commands available — RF field fully controllable
- Good, because same reader model works on Linux via pcsc-lite
- Good, because GET_SYSTEM_INFORMATION works
- Bad, because requires extra USB hardware (not built-in)
- Bad, because not the hardware shipped with the ASUS system

### Vendor NXP SDK (direct I2C)

Direct access to the NXP chip bypassing all OS abstraction.

- Good, because full control over RF field, timing, and protocol
- Bad, because requires NDA/confidential documentation
- Bad, because Windows-only (I2C bus access is platform-specific)
- Bad, because no porting path to Linux

---

## Links

- Related: [ADR-0001](ADR-0001-pcsc-as-smartcard-abstraction.md) — PC/SC layer choice
- Related: [ADR-0002](ADR-0002-scard-unpower-card-root-cause.md) — RF field control via disposition
- Related: [ADR-0005](ADR-0005-linux-port-requires-acr122u.md) — Linux porting consequence
- Knowledge: `knowledge/nfc/acr122u-commands.md`
- Knowledge: `knowledge/nfc/rf-field-timing.md`
