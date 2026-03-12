# ADR-0008: Re-wake NfcCx RF to verify card presence after ArmouryCrate kills field

**Status:** superseded by ADR-0009
**Deciders:** jalba, antigravity
**Date:** 2026-03-11
**Technical Story:** ArmouryCrate kills the RF field after reading the Keystone card, causing false "card removed" events. The existing `inserted_fired` guard (ADR-0007) was insufficient because `on_inserted` DOES fire successfully before AC kills RF.

---

## Context and Problem Statement

ArmouryCrate's `SoulKeyServicePlugin.dll` reads the Keystone card via PC/SC, then calls `SCardDisconnect(SCARD_UNPOWER_CARD)`, which makes NfcCx stop RF polling. PC/SC then reports `SCARD_STATE_EMPTY` even though the card is physically present. ArmouryCrate itself maintains persistent card presence via HID raw-input events (`RegisterRawInputDevices` / `GetRawInputData`), independent of PC/SC state.

How can our PC/SC-based monitor distinguish between ArmouryCrate killing RF (card still present) and the user physically removing the card?

---

## Decision Drivers

- Must not require elevated privileges
- Must not require killing or suspending ArmouryCrate processes
- Must work on both NfcCx (Microsoft IFD) and ACR122U readers
- Must not miss genuine card removals (vault security depends on it)
- Should have minimal latency for genuine removal detection
- Cross-platform compatibility preferred

---

## Considered Options

1. **Debounce timer** — ignore EMPTY events for N seconds after insert
2. **RF re-wake via SCardConnect** — attempt to re-trigger NfcCx RF polling
3. **WM_INPUT HID listener** — mirror ArmouryCrate's approach using RegisterRawInputDevices
4. **Process detection** — detect/suspend ArmouryCrate during card operations

---

## Decision Outcome

**Chosen option:** "RF re-wake via SCardConnect", because it directly confirms physical card presence using the same PC/SC stack, works cross-platform, and doesn't require process manipulation or Windows-specific HID APIs.

*NOTE: This decision was later superseded by ADR-0009. During verification, it was discovered that NfcCx treats `SCARD_UNPOWER_CARD` as a hard stop for the polling loop, returning `SCARD_E_NO_SMARTCARD` (0x80100069) to all subsequent `SCardConnect` attempts until physical re-insertion.*

### Positive Consequences

- Directly verifies physical card presence via RF
- Works on any PC/SC reader (NfcCx, ACR122U, etc.)
- No elevated privileges required
- No dependency on ArmouryCrate's specific behavior
- Genuine removals detected within ~2.5s (1s cooldown + 3 × 0.5s retries)

### Negative Consequences

- Adds ~2.5s latency before confirming genuine card removal
- Small CPU overhead from re-connect attempts
- If NfcCx has a bug preventing RF re-wake, this approach would fail silently (which is what happened).

---

## Pros and Cons of the Options

### Debounce Timer

- ✅ Simple to implement
- ✅ Cross-platform
- ❌ Blind — doesn't actually verify card presence
- ❌ Misses genuine fast removals during the debounce window
- ❌ Arbitrary timer value may need per-system tuning

### RF Re-Wake via SCardConnect ✅

- ✅ Physically verifies card presence via RF
- ✅ Cross-platform (PC/SC standard)
- ✅ Self-documenting — connect success = card present
- ✅ NfcCx resumes RF polling with new client connection
- ⚠️ 2.5s latency on genuine removal

### WM_INPUT HID Listener

- ✅ Mirrors ArmouryCrate's exact approach (proven reliable)
- ✅ Zero latency — HID events are hardware-level
- ❌ Windows-only (`RegisterRawInputDevices` is Win32 API)
- ❌ Requires a message pump (window handle)
- ❌ Adding USB HID code significantly increases complexity

### Process Detection

- ❌ Fragile — depends on AC process names/paths
- ❌ May require elevated privileges
- ❌ Invasive — risks breaking ASUS warranty/support
- ❌ Not portable to systems without ArmouryCrate

---

## Implementation Notes

**`_verify_card_present()` in `library/keystone_nfc/monitor.py`:**
1. Wait `_REWAKE_DELAY` (1.0s) for AC to finish its "Off NFC" sequence
2. Attempt `SCardConnect(SCARD_SHARE_SHARED)` up to `_REWAKE_RETRIES` (3) times
3. On success: disconnect with `SCARD_LEAVE_CARD`, return True
4. On failure: return False — card genuinely removed

**Why it initially appeared to work:** NfcCx stops RF polling when no PC/SC client holds a card handle. A new `SCardConnect` request acts as a client handle request, triggering NfcCx to resume RF discovery. However, experiment 02 confirmed that if AC sends `SCARD_UNPOWER_CARD`, NfcCx will completely ignore subsequent `SCardConnect` attempts until the card is physically lifted and placed again.

---

## Related

- Supersedes ADR-0007's mitigation #2 (inserted_fired guard alone was insufficient)
- ADR-0007's mitigation #1 (SCardConnect retry) remains in effect
- Superseded by `ADR-0009` (Suppress EMPTY events)
- See `retro/knowledge/nfc/soulkey-architecture-research.md` for full DLL analysis
- See `retro/knowledge/nfc/rf-field-timing.md` for RF field timing reference
