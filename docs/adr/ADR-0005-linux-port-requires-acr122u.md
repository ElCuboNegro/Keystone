# ADR-0005: Linux port requires physical ACR122U/SCL3711 — NfcCx has no Linux equivalent

**Status:** accepted
**Deciders:** Keystone porting team (this project)
**Date:** 2026-03-10
**Technical Story:** Consequence of ADR-0003 (NfcCx constraints). Documented during porting analysis. Port skeleton: `tools/port/keystone_reader.cpp`, `tools/port/linux_setup.sh`.

---

## Context and Problem Statement

The Windows implementation uses the built-in NXP NFC chip via the NfcCx driver (`"Microsoft IFD 0"`).
NfcCx is a Windows-only driver framework with no Linux equivalent.
How should the Linux port access NFC hardware, given that the original hardware path is unavailable?

---

## Decision Drivers

- NfcCx (`Microsoft IFD 0`) is Windows-only — no Linux driver exists for built-in I2C NXP chip
- Linux has pcsc-lite with the same `SCard*` API — only the reader hardware changes
- ACR122U is widely available, low cost, and natively supported by pcsc-lite on Linux
- The goal is functional equivalence — same card read behavior, different hardware path
- Code changes should be minimal (header swap + reader name handling)

---

## Considered Options

- ACR122U / SCL3711 external USB NFC reader via pcsc-lite
- libnfc direct USB access (bypasses pcsc-lite)
- NXP Linux kernel driver (I2C NFC chip via `nfc` subsystem)
- No NFC hardware path (software-only simulation)

---

## Decision Outcome

**Chosen option:** "ACR122U / SCL3711 via pcsc-lite", because it preserves the PC/SC abstraction layer established in ADR-0001, minimizes code changes (header swap only), and the ACR122U is the standard reference reader for pcsc-lite development.

On Linux, the ACR122U also enables escape commands (unlike NfcCx) — which is actually an improvement over the Windows path.

### Positive Consequences

- Minimal code change: `<winscard.h>` → `<PCSC/winscard.h>`, `IOCTL_CCID_ESCAPE` constant change
- PC/SC abstraction preserved — same `SCard*` calls work
- ACR122U supports ISO 15693 (Keystone cards) and ISO 14443 A/B
- Escape commands available on Linux — RF field can be controlled (improvement over NfcCx)
- `pcscd` daemon manages reader lifecycle

### Negative Consequences

- Requires purchasing an external USB NFC reader (~$30-50)
- Not a transparent drop-in — user must plug in the reader
- ACR122U requires PN532 analog configuration for reliable ISO 15693 detection (SAMConfiguration + RFConfiguration)
- Reader name will differ (`"ACS ACR122U PICC Interface 00"` vs `"Microsoft IFD 0"`) — must not hardcode reader name

---

## Pros and Cons of the Options

### ACR122U / SCL3711 via pcsc-lite (chosen)

Standard external USB NFC reader. Supported by pcsc-lite out of the box on all Linux distributions.

- Good, because PC/SC API is preserved — minimum code change
- Good, because widely available, well-documented, community supported
- Good, because escape commands work (unlike NfcCx on Windows) — RF field controllable
- Good, because ISO 15693 support confirmed for Keystone cards
- Bad, because requires external hardware (not built-in like the Windows path)
- Bad, because reader name differs — reader enumeration must be dynamic

### libnfc direct USB access

Open-source library with direct PN532 USB access, bypassing pcsc-lite.

- Good, because lower-level control, no pcsc daemon required
- Good, because better timing control for ISO 15693
- Bad, because requires complete rewrite of hardware access layer (no `SCard*` calls)
- Bad, because higher maintenance burden (different API, different error model)

### NXP Linux kernel NFC subsystem

Linux has an `nfc` kernel subsystem with drivers for some NXP chips.

- Good, because could work with the same embedded I2C chip on Linux
- Bad, because requires kernel module development or finding the exact driver
- Bad, because I2C bus access on a desktop motherboard is not standard
- Bad, because high complexity, platform-specific

### Software simulation (no hardware)

Run the logic without real NFC hardware — mock card reads.

- Good, because no hardware required for CI/CD testing
- Bad, because cannot test actual card communication
- Bad, because does not fulfill the porting goal

---

## Links

- Requires: [ADR-0001](ADR-0001-pcsc-as-smartcard-abstraction.md) — PC/SC as abstraction
- Caused by: [ADR-0003](ADR-0003-nfccx-no-escape-commands.md) — NfcCx Windows-only
- Port skeleton: `tools/port/keystone_reader.cpp`
- Port setup: `tools/port/linux_setup.sh`
- Knowledge: `knowledge/nfc/acr122u-commands.md`
