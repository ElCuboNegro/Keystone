# ADR-0007: Mitigate ASUS ArmouryCrate PC/SC contention — retry SCardConnect and suppress phantom card-removed events

**Status:** accepted
**Deciders:** Antigravity (agent), jalba
**Date:** 2026-03-11
**Technical Story:** ArmouryCrate races with keystone-nfc for the NFC reader. AC reads the card via WM_INPUT (HID, WPARAM=0xB4), then issues an "Off NFC" escape command that kills the RF field. This produces two observable failures in the PC/SC monitor loop.

---

## Context and Problem Statement

When ArmouryCrate is running on an ASUS system with a Keystone NFC reader, it competes with
keystone-nfc for access to the same PC/SC reader.  ArmouryCrate briefly holds an exclusive
session (~100 ms) and then kills the RF field via an escape command.  How should the monitor
module handle (a) the sharing violation on `SCardConnect`, and (b) the false card-removed
event that follows the RF field shutdown?

---

## Decision Drivers

- keystone-nfc must coexist with ArmouryCrate — users cannot be told to uninstall it
- Vault lock/unlock is driven by on_inserted / on_removed callbacks — a false on_removed locks all vaults while the card is still physically present
- SCardConnect fails immediately with a sharing violation; the lock is short-lived (~100 ms)
- ArmouryCrate's "Off NFC" causes SCARD_STATE_EMPTY to appear even though the card never left the reader
- Solution must not add perceptible latency to the normal (non-ArmouryCrate) code path

---

## Considered Options

- **Option A: Retry SCardConnect + inserted_fired guard** — retry the connect call in a tight loop with short sleeps; only fire on_removed if on_inserted actually succeeded
- **Option B: Detect ArmouryCrate process and delay** — check if ArmouryCrate.exe is running, if so add a fixed delay before the first SCardConnect
- **Option C: Kill / suspend ArmouryCrate during monitoring** — use TerminateProcess or NtSuspendProcess to remove the competitor

---

## Decision Outcome

**Chosen option:** "Option A: Retry SCardConnect + inserted_fired guard", because it is self-contained, process-agnostic, and adds negligible latency on systems without ArmouryCrate.

The retry loop (5 attempts × 50 ms = 250 ms budget) handles the exclusive-lock window.
The `inserted_fired` flag ensures that on_removed only fires when on_inserted previously
succeeded, suppressing the phantom card-removed event caused by RF field shutdown.

### Positive Consequences

- Zero-configuration coexistence with ArmouryCrate — no user action required
- No process enumeration or privilege escalation needed
- On systems without ArmouryCrate, the retry loop exits on the first attempt with zero added delay
- Phantom vault locks are eliminated — on_removed only fires when the user physically removes the card

### Negative Consequences

- Adds up to 250 ms latency on the initial card read when ArmouryCrate is present (imperceptible to the user)
- If ArmouryCrate holds the lock longer than 250 ms (not observed in practice), the card read will still fail
- If on_inserted fails for reasons other than ArmouryCrate (e.g., card removed during read), the next on_removed is also suppressed — acceptable because there was no successful insert to reverse

---

## Pros and Cons of the Options

### Option A: Retry SCardConnect + inserted_fired guard (chosen)

Retry `SCardConnect` up to 5 times with 50 ms sleeps. Track whether on_inserted actually
fired; only allow on_removed if it did.

- Good, because self-contained — no dependency on external process state
- Good, because zero overhead on systems without ArmouryCrate (first attempt succeeds)
- Good, because the retry parameters are trivially tunable via module-level constants
- Good, because the inserted_fired guard is a correct safety invariant even outside the AC scenario
- Bad, because introduces a fixed retry budget that may not cover all future AC timing changes

### Option B: Detect ArmouryCrate process and delay

Enumerate running processes, look for `ArmouryCrate.exe`, and add a pre-connect delay.

- Good, because explicitly targets the known cause
- Bad, because requires process enumeration (cross-platform complexity)
- Bad, because the process name or behavior could change across AC versions
- Bad, because adds latency unconditionally whenever AC is running, even if it hasn't touched the reader

### Option C: Kill / suspend ArmouryCrate

Terminate or suspend the competing process to remove contention entirely.

- Good, because eliminates the root cause completely
- Bad, because requires administrator privileges
- Bad, because ArmouryCrate provides other system management functions the user may depend on
- Bad, because hostile to the user — unacceptable UX

---

## Links

- Related: [ADR-0002](ADR-0002-scard-unpower-card-root-cause.md) — RF field lifecycle and SCARD_UNPOWER_CARD
- Related: [ADR-0003](ADR-0003-nfccx-no-escape-commands.md) — why NfcCx cannot re-enable RF via escape
- Related: [ADR-0006](ADR-0006-card-trigger-via-atkhotkey-acpi.md) — ATKHotkey WM_INPUT trigger that ArmouryCrate also intercepts
- Implementation: `library/keystone_nfc/monitor.py` — `_read_card()` retry loop and `_run()` inserted_fired guard
