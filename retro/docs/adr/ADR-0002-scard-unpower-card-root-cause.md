# ADR-0002: SCARD_UNPOWER_CARD used as disconnect disposition — root cause of millisecond RF drop

**Status:** accepted
**Deciders:** ASUS Keystone engineering team (inferred); confirmed by experiment
**Date:** 2026-03-10
**Technical Story:** Root cause of the "card readable for only milliseconds" bug. Confirmed via `retro/experiments/nfc/experiment_01_baseline_card_read.py`.

---

## Context and Problem Statement

After reading card data, the Keystone software disconnects from the PC/SC card handle.
The `SCardDisconnect` call requires a `dwDisposition` parameter that controls what happens
to the card after disconnect. Which disposition was chosen, and what are the consequences
for the RF field lifecycle?

---

## Decision Drivers

- Software must disconnect cleanly after reading card data
- The chosen disposition directly controls whether the NFC RF field stays active
- NfcCx behavior: when no client holds the card, RF polling stops
- Application design: "Off NFC" is called explicitly after the read sequence

---

## Considered Options

- `SCARD_LEAVE_CARD` — leave the card powered and connected
- `SCARD_RESET_CARD` — reset the card but keep it powered
- `SCARD_UNPOWER_CARD` — remove power from the card (turns off RF field on NfcCx)
- `SCARD_EJECT_CARD` — eject the card (not applicable for contactless)

---

## Decision Outcome

**Chosen option:** `SCARD_UNPOWER_CARD`, because the software intentionally powers off the NFC field after each card read — this is a deliberate "Off NFC" design choice, not a bug in the strict sense.

The consequence is that the RF field is active only for the duration of the read sequence (~milliseconds), then NfcCx stops RF polling entirely.

### Positive Consequences

- Reduces RF emissions when the card is not actively being used
- Prevents other applications from accessing the card after the read

### Negative Consequences

- Card is only readable for milliseconds — appears as a bug to users expecting persistent card presence detection
- On NfcCx, there is no escape command to re-enable RF independently — the only way to re-activate is to reconnect
- **This is the root cause of the "millisecond card read" problem**

---

## Pros and Cons of the Options

### SCARD_UNPOWER_CARD (chosen)

Removes power from the card. On NfcCx, this stops RF polling entirely.

- Good, because RF field is off when not needed (power saving, security)
- Bad, because card session ends immediately after disconnect
- Bad, because NfcCx cannot re-enable RF without a new `SCardConnect` cycle
- Bad, because creates millisecond read window that is invisible to the user

### SCARD_LEAVE_CARD

Leave the card in its current state. RF field stays active.

- Good, because card remains readable after disconnect
- Good, because RF field stays active — other operations can follow without reconnect
- Good, because this is the correct choice for NFC card presence detection
- Bad, because (not chosen by ASUS) — likely intentional "off" behavior

### SCARD_RESET_CARD

Reset the card but keep it powered.

- Good, because card is still in the field
- Bad, because forces ATR re-negotiation on next connect
- Bad, because not meaningful for ISO 15693 contactless cards

### SCARD_EJECT_CARD

Physically eject the card — only relevant for contact smart card readers with ejection mechanism.

- Bad, because not applicable for contactless NFC — behavior undefined on NfcCx

---

## Links

- Supersedes: N/A
- Related: [ADR-0003](ADR-0003-nfccx-no-escape-commands.md) — why RF field cannot be re-enabled via escape
- Related: [ADR-0001](ADR-0001-pcsc-as-smartcard-abstraction.md) — PC/SC layer
- Experiment: `retro/experiments/nfc/experiment_01_baseline_card_read.py`
- Knowledge: `retro/knowledge/nfc/rf-field-timing.md`
