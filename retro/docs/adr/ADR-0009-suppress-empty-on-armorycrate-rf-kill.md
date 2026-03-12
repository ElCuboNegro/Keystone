# ADR-0009: Suppress EMPTY events after successful insert to mitigate ArmouryCrate RF kill

**Status:** superseded by ADR-0010
**Deciders:** jalba, antigravity
**Date:** 2026-03-11
**Technical Story:** ArmouryCrate kills the RF field after reading the Keystone card via `SCardDisconnect(SCARD_UNPOWER_CARD)`. This stops NfcCx from polling, causing PC/SC to report `SCARD_STATE_EMPTY` even though the card is physically present. ADR-0008 attempted to re-wake the RF field, but NfcCx rejects the re-connection.

---

## Context and Problem Statement

ArmouryCrate's `SoulKeyServicePlugin.dll` reads the Keystone card via PC/SC, then calls `SCardDisconnect(SCARD_UNPOWER_CARD)`. This forces NfcCx to stop RF polling entirely, leading to a permanent `SCARD_STATE_EMPTY`. ArmouryCrate relies natively on WM_INPUT HID events for physical card tracking—not PC/SC state.

How can our monitor maintain the "inserted" state accurately, given that NfcCx cannot distinguish between "RF killed by AC" and "Card physically removed"?

---

## Decision Drivers

- Must not unexpectedly lock vaults (fire `on_removed`) while card is active.
- Must work within standard cross-platform PC/SC loops.
- Avoid invasive logic (hooks, suspending AC).
- Must handle NfcCx's refusal to re-poll after an `UNPOWER` call.

---

## Considered Options

1. **RF re-wake via SCardConnect** (ADR-0008). Fails because NfcCx returns `SCARD_E_NO_SMARTCARD` (0x80100069) to all reconnect requests until a raw hardware present event (a physical drop) is fired.
2. **WM_INPUT HID listener**. Too complex, Windows-only, required message pumps.
3. **Suppress EMPTY events completely after insert**. Once `on_inserted` succeeds, ignore all `SCARD_STATE_EMPTY` events until explicitly told to stop or a fresh `PRESENT` cycle occurs.

---

## Decision Outcome

**Chosen option:** "Suppress EMPTY events completely after insert." Because PC/SC goes completely blind to hardware events after an UNPOWER command, and there is no cross-platform software hook to restart NfcCx without physical lifting, the only robust path is trusting the initial insertion.

### Positive Consequences

- Completely eliminates the false "card removed" bug caused by ArmouryCrate.
- Zero CPU overhead, runs natively in standard `SCardGetStatusChange` loop.
- No elevated privileges or process hacking.

### Negative Consequences

- **Genuine physical removals are no longer detected live**. The `on_removed` callback is deferred until the monitor is stopped.
- To use the card again, the user must physically re-insert it (which triggers a new PC/SC PRESENT cycle mapping).

---

## Implementation Notes

**`_run()` loop in `monitor.py`:**
1. If `SCARD_STATE_EMPTY` appears:
   - If `inserted_fired` is True, log a suppression message and natively **skip** the `on_removed` callback.
2. Upon `stop()`:
   - If `inserted_fired` is True, execute `on_removed` accurately so app shutdown handles pending vault locks properly.

---

## Related
- Supersedes **ADR-0008** (RF re-wake).
- Validates **ADR-0007** (SCardConnect retries) as the sole active connect-time mitigation.
- See `retro/knowledge/nfc/soulkey-architecture-research.md` (DLL analysis confirms AC logic relies on HID hooks).
