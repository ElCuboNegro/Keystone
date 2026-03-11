# Changelog

All notable changes to `keystone-nfc` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Fixed
- **ArmouryCrate coexistence** — `SCardConnect` now retries up to 5 × 50 ms to survive
  the ~100 ms exclusive lock ASUS holds after card insertion
- **Suppress-EMPTY on RF kill** — when ArmouryCrate kills the RF field (via
  `SCARD_UNPOWER_CARD`), PC/SC reports `SCARD_STATE_EMPTY`. Because NfcCx refuses to
  resume RF polling until a physical re-insertion, the monitor now entirely suppresses
  subsequent `SCARD_STATE_EMPTY` events once `on_inserted` has successfully fired. The
  card is conceptually held "present" until a genuine physical removal is detected.
- **Genuine real-time removal detection** — added a background WMI listener thread
  (Windows only) watching for `AsusAtkWmiEvent` (EventID 180). This accurately detects
  physical card removals in real-time even when the PC/SC layer is reporting a false `EMPTY`
  due to ArmouryCrate's RF kill.

### Changed
- `soulkey-architecture-research.md` enriched with WMI ATK ACPI event findings.

### Architecture decisions
- `ADR-0007`: Mitigate ArmouryCrate PC/SC contention — retry SCardConnect
- `ADR-0008`: Re-wake NfcCx RF to verify card presence (Superseded)
- `ADR-0009`: Suppress EMPTY events after successful insert to mitigate ArmouryCrate RF kill (Superseded)
- `ADR-0010`: Hybrid WMI/PCSC Monitor for Real-time Keystone Removal Detection

---

## [0.1.0] — 2026-03-11

### Added
- `KeystoneReader` — high-level API with decorator-based callbacks (`on_card_inserted`,
  `on_card_removed`, `on_error`) and synchronous `read_once()` mode
- `CardInfo` — dataclass for card read results: `uid_bytes`, `uid_hex`, `uid_compact`,
  `block0`, `manufacturer`, `reader`, `protocol`, `timestamp`
- `CardMonitor` — background thread using `SCardGetStatusChange` (500ms poll, no busy-loop)
- `_pcsc` — cross-platform PC/SC bindings via `ctypes` (WinSCard on Windows,
  libpcsclite on Linux/macOS); no `pyscard` dependency
- `VaultRegistry` — persistent vault location registry at `~/.keystone/vaults.json`
- `VaultWatcher` — real-time file-system watcher (watchdog-based, 500ms debounce)
- `find_encrypted()` — scan vault directory for `.enc` files
- ISO 15693 manufacturer code lookup (NXP, STMicro, TI, Infineon, Fujitsu, EM Micro, …)
- Always uses `SCARD_LEAVE_CARD` on disconnect — never powers off the RF field
- Context manager support (`with KeystoneReader() as r: ...`)
- Platform support: Windows (NfcCx + WinSCard), Linux (pcsc-lite + pcscd)

### Architecture decisions
- `ADR-0001`: PC/SC via ctypes (no pyscard)
- `ADR-0002`: Always SCARD_LEAVE_CARD (never SCARD_UNPOWER_CARD on NfcCx)
- `ADR-0003`: SCardGetStatusChange polling at 500ms
- `ADR-0004`: Read only block 0 (SW=6981 kills RF session on NfcCx)
- `ADR-0005`: SCardBeginTransaction wrapping
- `ADR-0006`: Manufacturer decoded from ISO 15693 UID byte 6
