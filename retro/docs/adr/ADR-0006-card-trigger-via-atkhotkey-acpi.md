# ADR-0006: Card detection triggered via BIOS ACPI (ATKHotkey) WM_INPUT WPARAM=0xB4

**Status:** accepted
**Deciders:** ASUS Keystone / ArmouryCrate engineering team (inferred from DLL string analysis)
**Date:** 2026-03-10
**Technical Story:** Discovered via UTF-16 string extraction from `ArmouryCrate.SoulKeyServicePlugin.dll` (`tools/probe/soulkey_deep.py`). ATKACPI device path `\\.\ATKACPI` found. `WM_INPUT` with `WPARAM=0xB4` identified as card presence trigger.

---

## Context and Problem Statement

The Keystone software must know when a card is placed on or removed from the reader.
How does the application learn about card presence events? Does it poll the PC/SC layer,
wait for OS NFC events, or receive hardware events from the BIOS/ACPI subsystem?

---

## Decision Drivers

- ASUS ROG motherboards include an ATK hotkey ACPI device (`\\.\ATKACPI`)
- The NXP NFC chip reports card presence events via ACPI to the BIOS
- WinSCard `SCardGetStatusChange` can also detect card events — but may be slower or secondary
- Low latency card detection is important for user experience (LED feedback, drive unlock)

---

## Considered Options

- `SCardGetStatusChange` polling loop — standard PC/SC card detection
- ACPI/ATKHotkey `WM_INPUT` events (`WPARAM=0xB4`) — BIOS-level hardware events
- `RegisterDeviceNotification` — Windows device arrival/removal notifications
- Polling loop via `SCardStatus` — check card state on a timer

---

## Decision Outcome

**Chosen option:** "ACPI/ATKHotkey `WM_INPUT WPARAM=0xB4`", because the ASUS platform provides a dedicated BIOS-level card presence signal that is lower latency and more reliable than PC/SC polling. The software uses this as the primary trigger, with PC/SC access following the event.

### Positive Consequences

- Immediate card detection via hardware interrupt path (BIOS → ACPI → WM_INPUT)
- No polling overhead — event-driven architecture
- Consistent with other ASUS ArmouryCrate hotkey integrations on the platform

### Negative Consequences

- **This trigger is Windows and ASUS-platform specific** — no Linux equivalent
- On Linux, this path must be replaced with `SCardGetStatusChange` polling or `libudev` events
- `WPARAM=0xB4` is a magic constant — no public documentation found (inferred from DLL strings)
- Creates a hard dependency on the ATKACPI kernel driver being installed

---

## Pros and Cons of the Options

### ACPI/ATKHotkey WM_INPUT WPARAM=0xB4 (chosen)

ASUS-proprietary BIOS-level card presence notification via Windows message pump.

- Good, because hardware-interrupt driven — lowest possible latency
- Good, because integrates with ArmouryCrate's existing hotkey infrastructure
- Bad, because ASUS/Windows-only — must be replaced entirely on Linux
- Bad, because `WPARAM=0xB4` is undocumented — behavior under edge cases unknown
- Bad, because depends on ATKACPI driver and ArmouryCrate service being running

### SCardGetStatusChange polling loop

Standard PC/SC blocking call that waits for reader state change.

- Good, because cross-platform — same API on Windows and Linux (pcsc-lite)
- Good, because documented, standard, no proprietary dependencies
- Good, because this is the correct Linux replacement for the ACPI trigger
- Bad, because adds latency vs. BIOS-level event (typically 100-500ms polling interval)
- Bad, because requires a dedicated thread

### RegisterDeviceNotification

Windows WM_DEVICECHANGE notifications for USB device arrival/removal.

- Good, because works for USB reader hotplug detection
- Bad, because does not detect card presence (only reader presence)
- Bad, because Windows-only

### SCardStatus polling timer

Periodic `SCardStatus` call on a timer.

- Good, because simple
- Bad, because highest latency — timer interval determines detection speed
- Bad, because burns CPU in a polling loop

---

## Links

- Related: [ADR-0001](ADR-0001-pcsc-as-smartcard-abstraction.md) — PC/SC layer
- Related: [ADR-0005](ADR-0005-linux-port-requires-acr122u.md) — Linux trigger replacement needed
- Knowledge: `retro/knowledge/nfc/soulkey-architecture-research.md`
- Source: `retro/output/soulkey_deep.json` — UTF-16 strings with ATKACPI references
- Porting note: Replace with `SCardGetStatusChange` on Linux (blocking, no polling needed)
