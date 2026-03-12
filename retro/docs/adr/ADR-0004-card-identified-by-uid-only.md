# ADR-0004: Card identified by UID only — block reads beyond block 0 kill the RF session

**Status:** accepted
**Deciders:** ASUS Keystone engineering team (inferred); NfcCx behavior confirmed by experiment
**Date:** 2026-03-10
**Technical Story:** Confirmed via `retro/experiments/nfc/experiment_03_read_card_data.py` and `experiment_04_block_structure.py`. Output: `retro/output/experiment_03_card_dump.json`, `retro/output/experiment_04_block_structure.json`.

---

## Context and Problem Statement

What data is read from the Keystone card, and how? The card carries an 8-byte UID and potentially
multiple memory blocks. Should the system read UID only, or attempt to read full card memory?
On NfcCx, attempting to read a non-existent block returns SW=6981 which terminates the entire RF session.

---

## Decision Drivers

- Keystone card has only 1 publicly readable block (block 0 = `01 01 01 01`)
- All other block addresses return SW=6981 on NfcCx → session terminated immediately
- The card UID (8 bytes, ISO 15693) is the primary identifier used by `GetSSNByUID`
- Reading beyond block 0 makes subsequent reads in the same session impossible

---

## Considered Options

- Read UID + full memory scan (unsafe on NfcCx)
- Read UID + block 0 only (safe, confirmed readable)
- Read UID only (minimal, sufficient for identification)
- Read all blocks up to GET_SYSTEM_INFORMATION limit (unavailable — SW=6A81 on NfcCx)

---

## Decision Outcome

**Chosen option:** "Read UID + block 0 only", because block 0 is the only readable block and the UID is the primary key for all downstream operations (`GetSSNByUID`). Any attempt to read beyond block 0 terminates the RF session on NfcCx.

### Positive Consequences

- Safe read sequence — no session termination
- Sufficient data for card authentication (`CardUID`, `CardData` from block 0)
- Reproducible — same result on every card present event

### Negative Consequences

- Cannot read additional card data without NfcCx constraints being relaxed
- Dependent on NfcCx-specific behavior — on ACR122U, full memory could be read if needed
- Card memory layout cannot be verified via GET_SYSTEM_INFORMATION

---

## Pros and Cons of the Options

### Read UID + block 0 only (chosen)

- Good, because safe — no SW=6981, no session termination
- Good, because UID is the primary identifier for all downstream logic
- Good, because block 0 provides `CardData` field used by the state machine
- Bad, because limited visibility into full card memory

### Read UID + full memory scan

- Good, because complete data extraction
- Bad, because any out-of-range block → SW=6981 → NfcCx terminates the RF session immediately
- Bad, because without GET_SYSTEM_INFORMATION, block count is unknown

### Read UID only

- Good, because simplest and safest
- Bad, because misses `CardData` in block 0 which appears to be used by the application

### Read all blocks up to GET_SYSTEM_INFORMATION limit

- Good, because systematic and safe
- Bad, because GET_SYSTEM_INFORMATION (FF 30 / FF 2B) returns SW=6A81 on NfcCx — block count unknown

---

## Links

- Related: [ADR-0003](ADR-0003-nfccx-no-escape-commands.md) — NfcCx constraints
- Experiment: `retro/experiments/nfc/experiment_03_read_card_data.py`
- Experiment: `retro/experiments/nfc/experiment_04_block_structure.py`
- Knowledge: `retro/knowledge/nfc/iso-15693.md`
