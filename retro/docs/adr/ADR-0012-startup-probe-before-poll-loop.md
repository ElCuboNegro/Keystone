# ADR-0012: Startup probe — attempt direct card read before entering SCardGetStatusChange poll loop

**Status:** accepted
**Deciders:** Antigravity (agent), jalba
**Date:** 2026-03-11
**Technical Story:** When `CardMonitor.start()` is called, a card may already be present in
the reader. The standard `SCardGetStatusChange(SCARD_STATE_UNAWARE)` call will return the
current state, but on NfcCx after ArmouryCrate has killed the RF field, that state is
`SCARD_STATE_EMPTY` even when a card is physically in the reader. A startup probe is needed
to correctly detect pre-inserted cards and to give NfcCx a chance to restart RF polling.

---

## Context and Problem Statement

`SCardGetStatusChange` is a change-detection API — it reports transitions, not presence.
If a card is in the reader when monitoring starts:

- **Case A (RF on):** `SCardGetStatusChange(SCARD_STATE_UNAWARE)` returns immediately
  with `SCARD_STATE_PRESENT`. This works correctly without a probe.
- **Case B (RF killed by ArmouryCrate):** `SCardGetStatusChange(SCARD_STATE_UNAWARE)`
  returns `SCARD_STATE_EMPTY`. The card is physically present but invisible to PC/SC.
  Without a probe, `on_inserted` never fires until the card is removed and re-inserted.

The probe must also not cause false positives when no card is present.

---

## Decision Drivers

- `read_once()` must work if the card is already in the reader when called
- The ASUS ArmouryCrate RF-kill scenario (ADR-0002, ADR-0007) applies at startup, not only after an insert event
- The probe should not block the start of monitoring indefinitely
- The probe itself (calling `SCardConnect`) may trigger NfcCx to restart RF polling
  as a side effect — experiments showed that failed `SCardConnect` attempts cause
  NfcCx to schedule a new RF scan cycle

---

## Considered Options

- **A: Startup probe — 3 × `_read_card()` at 800ms intervals** before entering the poll loop
- **B: Begin poll loop immediately, rely on `SCardGetStatusChange(SCARD_STATE_UNAWARE)`** returning PRESENT if card is already there
- **C: Set initial state to `SCARD_STATE_PRESENT` unconditionally** — always fire `on_inserted` at startup

---

## Decision Outcome

**Chosen option: A — 3 × `_read_card()` at 800ms intervals**

The probe loop attempts `_read_card()` (which calls `SCardConnect` with the 5-retry
mechanism from ADR-0007) up to 3 times, 800ms apart (2.4s total budget).

- If a card is found: fire `on_inserted`, set `inserted_fired = True`, skip the remaining
  probe attempts, proceed directly into the poll loop
- If no card found after 3 attempts: proceed into the poll loop normally

The 800ms interval allows NfcCx one full RF polling cycle between attempts (the NfcCx
RF scan period is approximately 500–800ms based on experiments in
`retro/experiments/nfc/experiment_02_wake_nfc_radio.py`).

The failed `SCardConnect` calls are not wasted — each attempt signals NfcCx to
re-check the RF field, increasing the probability that a card that was invisible due
to ArmouryCrate's RF kill is rediscovered within the budget.

### Positive Consequences

- `read_once()` and `start()` work correctly when a card is pre-inserted
- The NfcCx RF restart side-effect is exploited without any direct escape command
  (which are unavailable — see ADR-0003)
- The 2.4s probe budget is imperceptible at startup (the application is still
  initializing during this window)

### Negative Consequences

- Adds up to 2.4s to startup time when a card was pre-inserted and RF is off
- Does not guarantee detection (if ArmouryCrate holds RF off longer than 2.4s, the
  card is missed until physically removed and re-inserted)
- On systems without a card, the probe completes quickly (first `SCardConnect` fails,
  probe returns `None` immediately, loop skips via the 800ms wait only if the attempt
  itself took less than that)

---

## Outcome of ADR-0008 (superseded)

ADR-0008 explored explicit RF re-wake via NfcCx escape commands. Experiment 02
(`retro/experiments/nfc/experiment_02_wake_nfc_radio.py`) confirmed that NfcCx returns
`ERROR_NOT_SUPPORTED` for all CCID escape commands — there is no direct RF restart mechanism.
The startup probe achieves a partial equivalent by inducing NfcCx's internal RF scheduling
as a side effect of repeated `SCardConnect` attempts.

---

## Links

- Supersedes: [ADR-0008](ADR-0008-rewake-rf-on-armorycrate-empty.md) — explicit RF re-wake failed; startup probe is the working alternative
- Related: [ADR-0002](ADR-0002-scard-unpower-card-root-cause.md) — why RF is killed at startup
- Related: [ADR-0003](ADR-0003-nfccx-no-escape-commands.md) — why escape commands cannot restart RF directly
- Related: [ADR-0007](ADR-0007-armorycrate-pcsc-contention-mitigations.md) — `_read_card()` retry mechanism reused by the probe
- Experiment: `retro/experiments/nfc/experiment_02_wake_nfc_radio.py` — RF re-wake probe (confirmed: no escape command works)
- Implementation: `library/keystone_nfc/monitor.py` — `_run()` startup probe section
