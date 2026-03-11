# Run Context — NFC / Keystone Domain

> This file is the live context for the current analysis run.
> Updated by agents as discoveries are made. Do NOT commit static facts here —
> confirmed knowledge goes to `knowledge/`. Only session state goes here.

---

## Target Hardware (CONFIRMED)

- **Reader**: Built-in NXP NFC chip on ASUS ROG motherboard, connected via I2C
- **PC/SC name**: `"Microsoft IFD 0"` (NfcCx Windows driver — NOT an ACR122U)
- **Driver DLL**: `NxpNfcClientDriver.dll`
- **ST chip path**: USB HID `VID_0483 PID_5750` → `HandlePlugInST()`
- **NXP chip path**: PC/SC → `HandlePlugInNXP()`

## Target Software (CONFIRMED)

- **DLL**: `ArmouryCrate.SoulKeyServicePlugin.dll`
- **PDB path**: `D:\SourceCode\AC.Keystone\production_V6.4`
- **Trigger**: BIOS ACPI (ATKHotkey) `WM_INPUT WPARAM=0xB4` OR ATKACPI device event

## Card State Machine (CONFIRMED)

```
CardExist -> CardPlugin -> CardPaired -> CardAuthorized -> CardActivated
```

- Data extracted: `CardUID`, `CardData`, `CardSSNNEW` (via `GetSSNByUID`)
- Features unlocked: shadow drive, Aura RGB, fan mode, QuickLaunch, Stealth, Windows lock

## Root Cause of Millisecond Read (CONFIRMED)

Software explicitly calls "Off NFC" after read + `SCARD_UNPOWER_CARD` on disconnect.
This causes NfcCx to stop RF polling when no client holds the card session.

NfcCx additional constraints (CONFIRMED):
- SW=6981 on any block read → terminates entire RF session immediately
- Only block 0 is publicly readable (`01 01 01 01`) — all others → SW=6981
- Session length: ~4.5s under SHARED, less under EXCLUSIVE
- ALL `SCardControl` escape commands FAIL on NfcCx (ERROR_NOT_SUPPORTED)

## Experiment History

| # | File | Goal | Status | Result |
|---|------|------|--------|--------|
| 01 | `experiment_01_baseline_card_read.py` | Test LEAVE vs UNPOWER | Done | LEAVE keeps session |
| 02 | `experiment_02_wake_nfc_radio.py` | Wake NFC field | Done | SCardGetStatusChange |
| 03 | `experiment_03_read_card_data.py` | Read card data blocks | Done | Only block 0 readable |
| 04 | `experiment_04_block_structure.py` | Map block structure | Done | 1 readable block |
| 05 | `experiment_05_safe_read.py` | Safe read pattern | Done | UID + block 0 only |

## Linux Port Status

- Port skeleton: `tools/port/keystone_reader.cpp` + `tools/port/linux_setup.sh`
- NfcCx has NO Linux equivalent — must use physical ACR122U/SCL3711 on Linux
- PC/SC API is identical (pcsc-lite) — header change only

## Open Questions

- [ ] What is the full card authentication protocol? (CardPaired → CardAuthorized steps)
- [ ] What crypto does GetSSNByUID use?
- [ ] Does shadow drive unlock use the UID or a derived key?

## Agent Rules for This Project

- [HARDWARE ACTION NEEDED] format when asking user to plug/unplug hardware
- [EXPERT QUESTION] format for domain expert questions
- Experiments are MANDATORY to confirm hypotheses before documenting as facts
