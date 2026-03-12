# ADR-0010: Hybrid WMI/PCSC Monitor for Real-time Keystone Removal Detection

**Status:** accepted
**Deciders:** jalba, antigravity
**Date:** 2026-03-11
**Technical Story:** While ADR-0009 successfully suppressed false "card removed" events caused by Armoury Crate's RF kill (`SCARD_UNPOWER_CARD`), it prevented the monitor from detecting genuine physical card removals in real-time. We needed a way to detect actual physical removal without being fooled by the PC/SC `SCARD_STATE_EMPTY` state. We discovered that ASUS software broadcasts a generic WMI event (`AsusAtkWmiEvent`, EventID `180`) on both physical insertion and removal of the Keystone card. 

---

## Context and Problem Statement

Armoury Crate's PC/SC interference causes the NFC reader to report `SCARD_STATE_EMPTY` even when the card is physically present. ADR-0009 mitigated this by suppressing `EMPTY` events after a successful insert, but at the cost of losing real-time removal detection. 

We discovered that Asus software broadcasts a WMI event (Class `AsusAtkWmiEvent` in namespace `root\wmi`) with an `EventID` of 180 every time a Keystone card is physically inserted or removed. However, the event itself does not distinguish between insertion and removal—it just fires EventID 180 in both cases.

How can we use this WMI event to restore real-time genuine removal detection, while maintaining the suppression of Armoury Crate's false `EMPTY` states?

---

## Decision Drivers

- Must provide real-time notification of actual physical card removal.
- Must not fire false removals when Armoury Crate kills the RF field.
- Must work within Python without requiring complex low-level HID/C hooks (unlike the `RegisterRawInputDevices` experiments which proved brittle in 64-bit Python).
- Cross-platform compatibility (the monitor must still work on Linux/macOS where Armoury Crate and WMI do not exist).

---

## Considered Options

1. **WM_INPUT HID listener in Python:** Attempted in experiments but proved too complex to implement robustly across 32/64-bit Python boundaries, requiring a dedicated UI thread and message pump.
2. **INI File Polling:** Attempted monitoring `SoulKeyPlugin_Status.ini`, but discovered the file does not update in real-time upon card removal.
3. **USB Device Enumeration Monitoring:** Attempted monitoring HID enumeration, but the Keystone insertion/removal does not trigger a USB device change (it's handled internally by the ATK ACPI / HID layers).
4. **Hybrid WMI + PC/SC Monitor:** Run a background WMI listener checking for EventID 180. Disambiguate the event's meaning by checking our current PC/SC application state.

---

## Decision Outcome

**Chosen option:** "Hybrid WMI + PC/SC Monitor". By combining the WMI event with our established PC/SC tracking flag (`inserted_fired`), we can deduce the physical hardware state with 100% accuracy.

1. PC/SC logic continues to suppress `SCARD_STATE_EMPTY` after an insert (carrying over the fix from ADR-0009).
2. A separate background thread uses `win32com.client` to monitor `root\wmi` for `AsusAtkWmiEvent`.
3. When `EventID 180` fires:
   - If `inserted_fired` is `False`, the system natively ignores the WMI event. (It's a physical insertion, which the primary PC/SC loop will detect a few milliseconds later and handle natively).
   - If `inserted_fired` is `True`, it is a **genuine physical removal** (because you cannot insert a card that is already inserted). The WMI thread immediately fires `on_removed()` and resets `inserted_fired` to `False`.

### Positive Consequences

- Completely solves the dual problem: false removals are suppressed, but real genuine removals are detected instantly.
- Very clean Python implementation using standard WMI query (`win32com.client`), avoiding direct C-types pointer manipulation.
- Degrades gracefully on non-Windows platforms (using a `try/except ImportError` block).

### Negative Consequences

- Introduces a dependency on `pywin32` for Windows users who want real-time removal detection. Without `pywin32`, the system gracefully degrades back to the ADR-0009 behavior (delayed removal).

---

## Related
- Supersedes **ADR-0009** (Suppress EMPTY on PC/SC).
- Relies on findings documented in `knowledge/nfc/soulkey-architecture-research.md` regarding ATKACPI and WMI behavior.
