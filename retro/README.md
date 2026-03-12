# Keystone — Reverse Engineering Layer

This directory contains the complete reverse-engineering research that produced the
`keystone-nfc` library. It documents every finding, confirmed hypothesis, failed experiment,
and architectural decision made while understanding the ASUS SoulKey/Keystone NFC system.

If you want to **use** the library, start at [`library/README.md`](../library/README.md).
If you want to understand **why** the library works the way it does, start here.

---

## What was reverse-engineered

The target is the ASUS Keystone hardware and its Windows software stack:

- **Hardware:** NFC reader built into ASUS ROG motherboards, driven by NxpNfcClientDriver (I2C),
  exposed via the Windows PC/SC API as `"Microsoft IFD 0"` under NfcCx.
- **Software:** `ArmouryCrate.SoulKeyServicePlugin.dll` — the ASUS service plugin that reads
  the card, manages the card state machine, and drives features like shadow drive unlock,
  Aura RGB, fan mode, QuickLaunch, and Windows lock.
- **Protocol:** ISO 15693 vicinity cards, identified by UID only.

The core engineering problem: **ArmouryCrate calls `SCardDisconnect(SCARD_UNPOWER_CARD)` after
every read, which kills the NFC RF field. Third-party PC/SC clients cannot read the card without
working around this behaviour.** Every architectural decision in the library traces back to a
finding in this research.

---

## Directory map

```
retro/
├── README.md                    <- you are here
│
├── knowledge/                   <- reference documentation
│   ├── INDEX.md                 <- master catalogue with confidence levels
│   ├── nfc/
│   │   ├── soulkey-architecture-research.md  <- DLL reverse-engineering (START HERE)
│   │   ├── rf-field-timing.md               <- root cause analysis of millisecond problem
│   │   ├── iso-15693.md                     <- ISO 15693 standard reference
│   │   └── acr122u-commands.md              <- ACR122U / PN532 command reference
│   └── smartcard/
│       ├── pcsc-api.md                      <- complete PC/SC API reference
│       └── apdu-reference.md                <- ISO 7816 APDU reference
│
├── docs/adr/                    <- architectural decision records (12 ADRs)
│   └── index.md                 <- ADR catalogue
│
├── experiments/nfc/             <- validated hardware experiments
│   ├── experiment_01_*          <- SCARD_LEAVE_CARD vs SCARD_UNPOWER_CARD
│   ├── experiment_02_*          <- RF re-wake via escape commands (failed — confirmed NfcCx refuses)
│   ├── experiment_03_*          <- card block structure mapping
│   ├── experiment_04_*          <- block boundary confirmation
│   ├── experiment_05_*          <- safe read sequence validation
│   ├── experiment_07_*          <- WM_INPUT raw event capture
│   ├── experiment_08_*          <- HID device enumeration
│   ├── experiment_09_*          <- SoulKeyPlugin_Status.ini monitoring
│   └── experiment_10_*          <- WMI AsusAtkWmiEvent listener
│
├── output/                      <- generated analysis artifacts
│   ├── retro-report.md/.dot     <- codebase call graph and structure analysis
│   ├── dll_analysis.md          <- PE header, imports, exports, APDU patterns
│   ├── soulkey_analysis.md      <- DLL string summary
│   ├── soulkey_deep.json        <- complete UTF-16 string dump (280+ strings)
│   ├── probe_results.json       <- live card probe output
│   └── experiment_0N_results.json  <- experiment results (5 files)
│
├── tools/
│   ├── probe/                   <- hardware interrogation tools
│   │   ├── card_probe.py        <- live reader enumeration, ATR, UID, memory dump
│   │   ├── dll_analyzer.py      <- PE header, imports, exports, APDU extraction
│   │   └── soulkey_deep.py      <- UTF-16 string extractor
│   └── retro/                   <- codebase analysis tools
│       ├── main.py              <- CLI entry point
│       ├── structure_mapper.py  <- module/class/function mapper
│       ├── call_tree.py         <- call graph builder (DOT export)
│       ├── api_mapper.py        <- hardware API call site detector
│       ├── decision_extractor.py <- hardcoded constant / timeout extractor
│       └── reporter.py          <- Markdown + JSON + DOT report generator
│
└── context/nfc/
    └── run_context.md           <- internal session state (not for publication)
```

---

## Reading guide

### 1. Start with the root cause

**`knowledge/nfc/rf-field-timing.md`** — explains the "card readable for milliseconds" problem,
ranks the six possible root causes, and documents the diagnostic process that confirmed
`SCARD_UNPOWER_CARD` as the answer.

**`knowledge/nfc/soulkey-architecture-research.md`** — the full DLL reverse-engineering:
internal function names, the card state machine, the event trigger chain, WMI events,
and the 280+ strings extracted from `ArmouryCrate.SoulKeyServicePlugin.dll`.

### 2. Follow the decision trail

**`docs/adr/index.md`** — 12 architectural decision records in chronological order.
Each ADR documents a specific decision, the alternatives considered, and the outcome.
Reading them in order tells the complete story of how the library was built.

Key ADRs to read first:

| ADR | Why it matters |
|-----|---------------|
| [ADR-0002](docs/adr/ADR-0002-scard-unpower-card-root-cause.md) | The root cause. Everything else flows from this. |
| [ADR-0003](docs/adr/ADR-0003-nfccx-no-escape-commands.md) | Why we cannot restart RF directly — forces indirect approaches. |
| [ADR-0004](docs/adr/ADR-0004-card-identified-by-uid-only.md) | Why the library reads only UID + block 0 and nothing else. |
| [ADR-0007](docs/adr/ADR-0007-armorycrate-pcsc-contention-mitigations.md) | How the library coexists with ArmouryCrate without killing it. |
| [ADR-0010](docs/adr/ADR-0010-hybrid-wmi-pcsc-monitor.md) | Why there are two monitoring threads instead of one. |
| [ADR-0011](docs/adr/ADR-0011-two-factor-vault-cryptography.md) | How the vault crypto was designed and why. |
| [ADR-0012](docs/adr/ADR-0012-startup-probe-before-poll-loop.md) | Why the monitor probes for cards before entering the poll loop. |

### 3. Verify with experiments

The `experiments/nfc/` scripts are runnable reproductions of each key finding.
All experiments require a physical NFC reader; experiment 02 also requires ArmouryCrate
to be running to observe the failure mode.

Each experiment writes its results to `output/experiment_NN_results.json`.

### 4. Standards references

- **ISO 15693** (`knowledge/nfc/iso-15693.md`) — the vicinity card standard that defines
  the 8-byte UID format, the manufacturer byte (byte 6), and the 0xE0 MSB.
- **PC/SC API** (`knowledge/smartcard/pcsc-api.md`) — the complete WinSCard / pcsc-lite
  API reference used throughout the library.
- **APDU** (`knowledge/smartcard/apdu-reference.md`) — ISO 7816 command reference for
  the `FF CA 00 00 00` (GET UID) and `FF B0 00 00 04` (READ BLOCK 0) commands the library sends.

---

## Key confirmed findings

| Finding | Evidence | ADR |
|---------|----------|-----|
| ArmouryCrate calls `SCardDisconnect(SCARD_UNPOWER_CARD)` after every read | DLL string analysis + experiment 01 | ADR-0002 |
| NfcCx refuses all CCID escape commands (`ERROR_NOT_SUPPORTED`) | Experiment 02: all IOCTLs rejected | ADR-0003 |
| Reading any block beyond block 0 returns `SW=6981` and kills the RF session | Experiment 03 + 04 | ADR-0004 |
| ArmouryCrate holds exclusive PC/SC session for ~100ms after card insertion | Experiment 01 + timing analysis | ADR-0007 |
| `AsusAtkWmiEvent` EventID 180 fires on both physical insertion and removal | WMI monitor (experiment 10) | ADR-0010 |
| NfcCx IS a valid ISO 15693 reader; it just requires `SCARD_LEAVE_CARD` | Experiment 05: 10+ consecutive reads | ADR-0002 |

---

## Tools

### Probe tools (require NFC hardware)

```bash
# Live card read — prints UID, ATR, block structure, manufacturer
python retro/tools/probe/card_probe.py

# DLL static analysis — PE header, imports, APDU patterns
python retro/tools/probe/dll_analyzer.py <path/to/dll>

# UTF-16 string extraction from DLL
python retro/tools/probe/soulkey_deep.py <path/to/ArmouryCrate.SoulKeyServicePlugin.dll>
```

### Retro tools (analyze any codebase)

```bash
# Full analysis: structure + call tree + API map + decisions → report
python retro/tools/retro/main.py <path/to/codebase>

# Output: retro/output/retro-report.md + retro/output/retro-report.dot
```

---

## Alignment with the library

Every design decision in `library/keystone_nfc/` and `library/folder_lock.py` has a
corresponding ADR in this directory. If you find a behaviour in the library that has no ADR,
that is a documentation gap — open an issue or write the ADR.

| Library component | Governing ADRs |
|------------------|----------------|
| `_pcsc.py` — ctypes over pyscard | ADR-0001 |
| `monitor.py` — `SCARD_LEAVE_CARD` | ADR-0002 |
| `monitor.py` — no escape commands | ADR-0003 |
| `monitor.py` — UID + block 0 only | ADR-0004 |
| `monitor.py` — SCardConnect retry | ADR-0007 |
| `monitor.py` — startup probe | ADR-0012 |
| `monitor.py` — WMI listener thread | ADR-0010 |
| `monitor.py` — `inserted_fired` guard | ADR-0007 |
| `folder_lock.py` — PBKDF2 + AES-GCM + HMAC names | ADR-0011 |
| Linux deployment — ACR122U required | ADR-0005 |
