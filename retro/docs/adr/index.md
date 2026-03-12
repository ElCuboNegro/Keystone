# Architecture Decision Records

All significant architectural decisions for the Keystone / SoulKey retro-engineering and Linux porting project.

Managed by `skills/adr-writer.md`. Do not edit ADR files once accepted — supersede them with a new ADR.

| ID | Title | Status | Date | Domain |
|----|-------|--------|------|--------|
| [ADR-0001](ADR-0001-pcsc-as-smartcard-abstraction.md) | Use PC/SC (WinSCard / pcsc-lite) as smart card abstraction layer | accepted | 2026-03-10 | Smart Card |
| [ADR-0002](ADR-0002-scard-unpower-card-root-cause.md) | SCARD_UNPOWER_CARD used as disconnect disposition — root cause of millisecond RF drop | accepted | 2026-03-10 | NFC / PC-SC |
| [ADR-0003](ADR-0003-nfccx-no-escape-commands.md) | NfcCx (Microsoft IFD 0) chosen as NFC reader — escape commands unsupported | accepted | 2026-03-10 | NFC |
| [ADR-0004](ADR-0004-card-identified-by-uid-only.md) | Card identified by UID only — block reads beyond block 0 kill the RF session | accepted | 2026-03-10 | NFC |
| [ADR-0005](ADR-0005-linux-port-requires-acr122u.md) | Linux port requires physical ACR122U/SCL3711 — NfcCx has no Linux equivalent | accepted | 2026-03-10 | Porting |
| [ADR-0006](ADR-0006-card-trigger-via-atkhotkey-acpi.md) | Card detection triggered via BIOS ACPI (ATKHotkey) WM_INPUT WPARAM=0xB4 | accepted | 2026-03-10 | Hardware |
| [ADR-0007](ADR-0007-armorycrate-pcsc-contention-mitigations.md) | Mitigate ArmouryCrate PC/SC contention — retry SCardConnect + suppress phantom removes | accepted | 2026-03-11 | NFC / PC-SC |
| [ADR-0008](ADR-0008-rewake-rf-on-armorycrate-empty.md) | Re-wake NfcCx RF to verify card presence after ArmouryCrate kills field | superseded | 2026-03-11 | NFC / PC-SC |
| [ADR-0009](ADR-0009-suppress-empty-on-armorycrate-rf-kill.md) | Suppress EMPTY events after successful insert to mitigate ArmouryCrate RF kill | superseded | 2026-03-11 | NFC / PC-SC |
| [ADR-0010](ADR-0010-hybrid-wmi-pcsc-monitor.md) | Hybrid WMI/PCSC Monitor for Real-time Keystone Removal Detection | accepted | 2026-03-11 | NFC / Windows |
| [ADR-0011](ADR-0011-two-factor-vault-cryptography.md) | Two-factor vault encryption — PBKDF2 + AES-256-GCM + HMAC deterministic filenames | accepted | 2026-03-11 | Cryptography |
| [ADR-0012](ADR-0012-startup-probe-before-poll-loop.md) | Startup probe — attempt direct card read before entering SCardGetStatusChange poll loop | accepted | 2026-03-11 | NFC / PC-SC |
