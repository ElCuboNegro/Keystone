# Changelog

All notable changes to `keystone-nfc` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [0.2.0] — 2026-03-11

### Fixed
- **ArmouryCrate coexistence** — `SCardConnect` now retries up to 5 × 50 ms to survive
  the ~100 ms exclusive lock ASUS holds after card insertion (`SCARD_E_SHARING_VIOLATION`)
- **Phantom card-removed events** — `on_removed` now only fires when `on_inserted`
  previously succeeded (`inserted_fired` guard), eliminating false vault-lock events caused
  by the PC/SC layer reporting `SCARD_STATE_EMPTY` after ArmouryCrate kills the RF field
- **Genuine physical removal** — added a background WMI listener thread (Windows, requires
  `pywin32`) watching for `AsusAtkWmiEvent` (EventID 180). Detects physical card removal
  in real-time independent of the PC/SC RF state

### Added
- `keystone_nfc/py.typed` — PEP 561 marker; package is now fully type-checkable with
  mypy and pyright
- `__all__` declared in every public module (`card`, `exceptions`, `monitor`, `reader`,
  `registry`, `watcher`)
- `CONTRIBUTING.md` — development setup, test instructions, PR process
- `.github/workflows/ci.yml` — GitHub Actions CI: pytest + mypy + ruff on Windows
  (Python 3.11, 3.12); import-check job on Ubuntu with pcsc-lite

### Changed
- `pyproject.toml` — `pywin32>=306` added to `[gui]` optional dependency group
- `DEMO/requirements.txt` — standalone requirements file for the GUI demo
- `DEMO/keystone_gui.py` — vault name label is now clickable (blue, hand cursor) when
  vault is open; click opens the working directory in the OS file browser

### Architecture decisions
- `ADR-0007`: Mitigate ArmouryCrate PC/SC contention — retry SCardConnect
- `ADR-0008`: Re-wake NfcCx RF to verify card presence (Superseded by ADR-0010)
- `ADR-0009`: Suppress EMPTY events after successful insert (Superseded by ADR-0010)
- `ADR-0010`: Hybrid WMI/PCSC Monitor for real-time Keystone removal detection

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
