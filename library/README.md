# keystone-nfc

[![CI](https://github.com/ElCuboNegro/Keystone/actions/workflows/ci.yml/badge.svg)](https://github.com/ElCuboNegro/Keystone/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Python library for NFC card event monitoring and UID reading via PC/SC.

Works with any ISO 15693 card on any PC/SC-compatible reader — no binary dependencies,
pure ctypes. Ships with a two-factor AES-GCM encrypted vault (`folder_lock.py`) that
locks/unlocks using physical card presence.

---

## Platform support

| Platform | PC/SC stack | Tested hardware |
|----------|-------------|-----------------|
| Windows 10/11 | WinSCard (built-in) | NfcCx "Microsoft IFD 0" (built-in), ACR122U |
| Linux | pcsc-lite + pcscd | ACR122U, SCL3711 |
| macOS | pcsc-lite (Homebrew) | ACR122U |

> **Windows + ASUS ArmouryCrate users:** see [the ArmouryCrate section](#asus-armorycrate-coexistence)
> before you start — there are known driver conflicts that require specific workarounds.

---

## Installation

```bash
# Core package (NFC monitoring only, zero runtime dependencies)
pip install keystone-nfc

# + vault encryption (cryptography, watchdog)
pip install "keystone-nfc[vault]"

# + full GUI dependencies (pystray, Pillow, pywin32 on Windows)
pip install "keystone-nfc[gui]"
```

**Linux prerequisite:**
```bash
sudo apt install pcscd libpcsclite1
sudo systemctl start pcscd
```

**macOS prerequisite:**
```bash
brew install pcsc-lite
brew services start pcsc-lite
```

---

## Quick start

### Event-driven monitoring

```python
from keystone_nfc import KeystoneReader

reader = KeystoneReader()

@reader.on_card_inserted
def inserted(card):
    print(f'UID:          {card.uid_hex}')
    print(f'UID (compact): {card.uid_compact}')
    print(f'Manufacturer: {card.manufacturer}')
    print(f'Reader:       {card.reader}')

@reader.on_card_removed
def removed():
    print('Card removed')

@reader.on_error
def error(exc):
    print(f'Monitor error: {exc}')

# Context manager handles start()/stop() automatically
with reader:
    input('Watching for cards — press Enter to stop...')
```

### One-shot synchronous read

```python
card = KeystoneReader().read_once(timeout=30.0)
print(card.uid_hex)       # 'E0 04 01 4C D4 54 01 08'
print(card.uid_compact)   # 'E004014CD454010 8'
print(card.uid_bytes)     # b'\xe0\x04\x01...'
print(card.timestamp)     # datetime(2026, 3, 11, 14, 32, 5)
```

### Target a specific reader

```python
# List all readers on the system
readers = KeystoneReader().available_readers()
print(readers)
# ['Microsoft IFD 0', 'ACS ACR122U PICC Interface 0']

# Exact or substring match
reader = KeystoneReader(reader_name='ACR122U')
```

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Your Application                      │
│   @reader.on_card_inserted   @reader.on_card_removed        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                     KeystoneReader                           │
│  start() / stop() / read_once()  available_readers()        │
│  _dispatch_inserted / _dispatch_removed / _dispatch_error   │
└────────────────────┬────────────────────────────────────────┘
                     │ creates & owns
┌────────────────────▼────────────────────────────────────────┐
│                      CardMonitor                             │
│                                                              │
│  Thread 1: _run()               Thread 2: _wmi_listener_run()│
│  SCardGetStatusChange poll      AsusAtkWmiEvent listener    │
│  500ms timeout loop             (Windows + pywin32 only)    │
│  -> _read_card() on PRESENT     -> fires on_removed         │
│                                    when EventID=180 +       │
│                                    inserted_fired=True       │
└────────────────────┬────────────────────────────────────────┘
                     │ ctypes
┌────────────────────▼────────────────────────────────────────┐
│                       _pcsc.py                               │
│  WinSCard (Windows)  /  libpcsclite.so (Linux/macOS)        │
│  SCardEstablishContext, SCardGetStatusChange,                │
│  SCardConnect, SCardBeginTransaction, SCardEndTransaction,   │
│  SCardDisconnect, transmit()                                 │
└─────────────────────────────────────────────────────────────┘
```

### Call flow: card insertion → callback

```
Physical card tap
    -> SCardGetStatusChange detects SCARD_STATE_PRESENT
        -> CardMonitor._read_card()
            -> SCardConnect (retry up to 5x, 50ms apart)
            -> SCardBeginTransaction
            -> APDU FF CA 00 00 00  (GET DATA: UID)
            -> APDU FF B0 00 00 04  (READ BINARY: block 0)
            -> SCardEndTransaction
            -> SCardDisconnect(SCARD_LEAVE_CARD)  [never UNPOWER]
            -> CardInfo.from_raw(uid_raw, reader, proto, block0)
        -> on_inserted(card: CardInfo)
            -> KeystoneReader._dispatch_inserted
                -> your @reader.on_card_inserted callback
```

### Threading model

`CardMonitor` runs **two background threads**:

| Thread | Purpose | Platform |
|--------|---------|----------|
| `keystone-monitor` | `SCardGetStatusChange` polling (500ms intervals), fires `on_inserted` | All |
| `keystone-wmi-monitor` | WMI `AsusAtkWmiEvent` listener, fires `on_removed` | Windows + pywin32 |

**Why two threads?** On Windows with ASUS ArmouryCrate, `SCardDisconnect(SCARD_UNPOWER_CARD)`
kills the NFC RF field after each card read. PC/SC reports `SCARD_STATE_EMPTY` even though
the card is still physically present, making PC/SC-based removal detection unreliable.
The WMI thread listens for `AsusAtkWmiEvent` (EventID 180), which fires on genuine physical
removal regardless of RF field state. The `inserted_fired` flag on `CardMonitor` disambiguates
insertion events (EventID 180 also fires on insertion; we only treat it as removal if a card
was previously successfully read).

On Linux/macOS (no ArmouryCrate), the WMI thread is not started. PC/SC removal detection
works reliably via `SCARD_STATE_EMPTY`.

### Startup probe

When `CardMonitor.start()` is called, the monitor attempts up to **3 direct `_read_card()`
calls** (800ms apart) before entering the `SCardGetStatusChange` poll loop. This handles the
case where a card is already present in the reader at startup — the initial
`SCardGetStatusChange(SCARD_STATE_UNAWARE)` call will return the current state, which may
already be `PRESENT`, without generating a change event.

---

## API reference

### `KeystoneReader(reader_name=None)`

High-level API. Manages a `CardMonitor` internally.

```python
from keystone_nfc import KeystoneReader
```

| Method / Decorator | Signature | Description |
|-------------------|-----------|-------------|
| `on_card_inserted` | `(fn: Callable[[CardInfo], None]) -> fn` | Decorator: called with `CardInfo` when a card is detected |
| `on_card_removed` | `(fn: Callable[[], None]) -> fn` | Decorator: called when the card is physically removed |
| `on_error` | `(fn: Callable[[Exception], None]) -> fn` | Decorator: called on monitor errors |
| `start()` | `() -> None` | Start the background monitor thread |
| `stop(timeout=3.0)` | `(float) -> None` | Stop the monitor, wait up to `timeout` seconds |
| `read_once(timeout=30.0)` | `(float) -> CardInfo` | Block until a card is detected; raises `NoCardError` on timeout |
| `available_readers()` | `() -> List[str]` | List all PC/SC reader names currently visible to the OS |

**Context manager:** `with KeystoneReader() as r:` calls `start()` on enter, `stop()` on exit.

**Reader selection:** if `reader_name` is given, the first reader whose name matches exactly
(or contains the value as a substring) is used. Raises `NoReaderError` if not found.
If `reader_name` is `None`, the first available reader is auto-selected.

---

### `CardInfo`

Returned by `on_card_inserted` callbacks and `read_once()`. Immutable dataclass.

```python
from keystone_nfc import CardInfo
```

| Field | Type | Description |
|-------|------|-------------|
| `uid_bytes` | `bytes` | Raw UID. ISO 15693 = 8 bytes, stored LSB-first (as returned by the reader) |
| `uid_hex` | `str` | Space-separated uppercase hex — e.g. `'E0 04 01 4C D4 54 01 08'` |
| `uid_compact` | `str` | No-space uppercase hex — e.g. `'E004014CD4540108'` |
| `block0` | `Optional[bytes]` | Memory block 0 (4 bytes), or `None` if the read failed |
| `manufacturer` | `Optional[str]` | Decoded from ISO 15693 UID byte 6 (e.g. `'NXP Semiconductors'`) |
| `reader` | `str` | PC/SC reader name that read this card |
| `protocol` | `int` | PC/SC active protocol: `1` = T=0, `2` = T=1 |
| `timestamp` | `datetime` | When the card was read (local time) |

**ISO 15693 UID layout** (as returned by `FF CA 00 00 00`):

```
byte[0]  byte[1]  byte[2]  byte[3]  byte[4]  byte[5]  byte[6]  byte[7]
  IC       Serial number (5 bytes)              Mfr code  0xE0 (fixed)
```

`uid_bytes[7]` is always `0xE0` for ISO 15693. `uid_bytes[6]` is the manufacturer code
(NXP = `0x04`, STMicro = `0x02`, TI = `0x07`, Infineon = `0x05`).

---

### Exceptions

```python
from keystone_nfc import KeystoneError, NoReaderError, NoCardError, CardRemovedError, PCSCError
```

| Exception | Inherits | Raised when |
|-----------|---------|-------------|
| `KeystoneError` | `Exception` | Base class for all library exceptions |
| `NoReaderError` | `KeystoneError` | No PC/SC reader found, or specified reader not available |
| `NoCardError` | `KeystoneError` | `read_once()` timeout elapsed with no card detected |
| `CardRemovedError` | `KeystoneError` | Card removed during an active SCardBeginTransaction session |
| `PCSCError` | `KeystoneError` | PC/SC API call returned a non-success status code |

---

## folder_lock.py — Two-factor encrypted vault

`folder_lock.py` is a standalone vault utility (CLI + importable library) that encrypts a
folder using **two factors**: the physical NFC card UID (something you have) and a password
(something you know). Both are required to decrypt.

### Security model

**Protects against:**
- Reading the vault while locked (card absent / process not running)
- Learning original filenames from the encrypted vault
- Brute-forcing the password without the physical card (UID is the KDF salt)

**Does NOT protect against:**
- Reading plaintext from the working directory while the vault is open
  → Mitigate: use a RAM disk as `--workdir` (plaintext is volatile, gone on power cut)
- Full-disk access from another OS while the vault is open
  → Mitigate: combine with BitLocker / FileVault (full-disk encryption)

### Cryptographic specification

```
master_key  = PBKDF2-HMAC-SHA256(password, salt=uid_bytes, iterations=600_000, dklen=32)
enc_name    = HMAC-SHA256(master_key, rel_path_utf8)[:8 bytes].hex() + '.enc'

per_file_blob:
    [8 bytes]  magic = b'KSTNLK2\n'
    [12 bytes] nonce (random, per file)
    [N bytes]  AES-256-GCM(
                   key=master_key,
                   nonce=nonce,
                   aad=magic,
                   plaintext= uint32-BE(len(rel_path_utf8))
                              + rel_path_utf8
                              + file_content
               )
```

**Key properties:**
- Original filenames are never stored in the vault — the `.enc` filename is an HMAC of the
  relative path under the master key, so an attacker cannot enumerate files without the key
- Each file has a fresh 96-bit nonce; AES-GCM provides authenticated encryption
- The 16-byte GCM authentication tag is appended by `AESGCM.encrypt()`; any bit flip in the
  ciphertext raises `InvalidTag` before any plaintext is returned
- 600k PBKDF2 iterations (≈ NIST SP 800-63B level 2 for memory-constrained hardware)

### Vault layout

```
vault/                       <- permanent home of encrypted files
    a3f9b2c1d5e6f7b8.enc
    ff01234567890abc.enc
    subdir/
        89fe5b7e12340001.enc

workdir/                     <- plaintext lives here ONLY while unlocked
    notes.md                    (default: vault/.working/)
    subdir/
        ideas.md
```

`.enc` files are **never deleted** — they are the permanent safe copy. Decrypted files live
only in `workdir`. On card removal or process exit, `workdir` is wiped.

### CLI usage

```bash
# Watch vault, unlock when card is inserted
python folder_lock.py /path/to/vault

# Use a RAM disk as the working directory (maximum security)
python folder_lock.py /path/to/vault --workdir R:\keystone-work

# Force re-encrypt workdir -> vault (emergency lock)
python folder_lock.py /path/to/vault --lock

# Show vault status
python folder_lock.py /path/to/vault --status
```

### Python API

```python
from folder_lock import (
    derive_key,
    encrypt_file, decrypt_file,
    encrypt_workdir, decrypt_vault,
    enc_name_for_path,
    encrypt_one_file, delete_enc_for_path, move_enc_for_path,
    find_plaintext,
    MAGIC, KDF_ITERS, ENC_EXT,
)
```

| Function | Signature | Description |
|----------|-----------|-------------|
| `derive_key` | `(password: str, uid_bytes: bytes) -> bytes` | PBKDF2 key derivation. Both factors required. Returns 32-byte key. |
| `encrypt_file` | `(content: bytes, rel_path: str, key: bytes) -> bytes` | Encrypt one file into an opaque blob (magic + nonce + AES-GCM ciphertext) |
| `decrypt_file` | `(blob: bytes, key: bytes) -> tuple[str, bytes]` | Decrypt a blob. Returns `(original_rel_path, content)`. Raises `InvalidTag` on wrong key or tampering. |
| `encrypt_workdir` | `(vault: Path, workdir: Path, key: bytes) -> int` | Encrypt all plaintext files in `workdir` into `vault`. Deletes orphan `.enc` files. Returns file count. |
| `decrypt_vault` | `(vault: Path, workdir: Path, key: bytes) -> int` | Decrypt all `.enc` files from `vault` into `workdir`. Returns file count. |
| `enc_name_for_path` | `(key: bytes, rel_path: str) -> str` | Deterministic `.enc` filename for a given relative path + key (HMAC-SHA256). |
| `encrypt_one_file` | `(vault: Path, rel_path: str, content: bytes, key: bytes) -> Path` | Encrypt a single file in-place (used by `VaultWatcher`). |
| `delete_enc_for_path` | `(vault: Path, rel_path: str, key: bytes) -> bool` | Delete the `.enc` file corresponding to `rel_path`. |
| `move_enc_for_path` | `(vault: Path, old_rel: str, new_rel: str, content: bytes, key: bytes) -> None` | Rename a file: delete old `.enc`, write new one. |
| `find_plaintext` | `(workdir: Path) -> List[Path]` | All non-ignored plaintext files in `workdir` (recursive). |

---

## VaultRegistry

Persistent registry of vault locations stored at `~/.keystone/vaults.json`.

```python
from keystone_nfc.registry import VaultRegistry, VaultEntry, find_encrypted
```

```python
reg = VaultRegistry()

# Register a new vault
entry = reg.add(name='Work Notes', vault_path=Path('/data/vault'))

# List vaults whose folder currently exists on the filesystem
for v in reg.present():
    print(v.name, v.status())  # 'locked' | 'open' | 'empty' | 'not_found'

# Remove a vault from the registry (does not delete files)
reg.remove(entry.id)
```

### `VaultEntry`

| Field / Property | Type | Description |
|-----------------|------|-------------|
| `id` | `str` | UUID, assigned on creation |
| `name` | `str` | Human-readable label |
| `vault_path` | `str` | Absolute path to the encrypted vault folder |
| `workdir_path` | `Optional[str]` | Override for working directory. `None` → `vault/.working/` |
| `vault` | `Path` (property) | `vault_path` as a `Path` object |
| `workdir` | `Path` (property) | Resolved working directory |
| `is_present()` | `bool` | `True` when `vault` exists on the filesystem |
| `status()` | `str` | `'not_found'` \| `'locked'` \| `'open'` \| `'empty'` |

### `VaultRegistry`

| Method | Description |
|--------|-------------|
| `all() -> List[VaultEntry]` | All registered vaults |
| `present() -> List[VaultEntry]` | Vaults whose path currently exists |
| `get(id) -> Optional[VaultEntry]` | Look up by UUID |
| `add(name, vault_path, workdir_path=None) -> VaultEntry` | Register a new vault, persist immediately |
| `remove(id) -> bool` | Remove from registry (files untouched) |
| `update(id, **kwargs) -> bool` | Update a field and persist |

---

## VaultWatcher

Real-time file-system watcher that keeps the vault in sync while it is open.
Fires per-file callbacks with 500ms debounce (handles editor write-to-tmp + rename patterns
used by VS Code, Obsidian, Vim, etc.).

```python
from keystone_nfc.watcher import VaultWatcher

watcher = VaultWatcher(
    workdir    = Path('/data/vault/.working'),
    on_encrypt = lambda rel_path, content: ...,  # file created or modified
    on_delete  = lambda rel_path: ...,            # file deleted
    on_move    = lambda old, new, content: ...,   # file renamed / moved
    on_error   = lambda exc: ...,                 # optional error handler
    debounce   = 0.5,                             # seconds (default)
)
watcher.start()
# ...
watcher.stop()
```

> **Threading note:** all callbacks fire from the watchdog observer thread.
> Post to a UI queue (e.g. `queue.SimpleQueue`) if you need to update a GUI widget.

---

## ASUS ArmouryCrate coexistence

If you use this library on a system with **ASUS ArmouryCrate** installed, you will encounter
RF field interference. This section explains the problem and the mitigations built into the
library.

### The problem

ArmouryCrate monitors NFC cards via `WM_INPUT` (USB HID, `WPARAM=0xB4`). When a card is
detected, it calls `SCardDisconnect(SCARD_UNPOWER_CARD)`, which kills the NFC RF field.
After this, NfcCx stops RF polling and PC/SC reports `SCARD_STATE_EMPTY`, even though the
card is still physically present. The RF field does not restart until a genuine physical
card removal + re-insertion occurs.

### Mitigation 1 — SCardConnect retry on sharing violation

ArmouryCrate holds an exclusive PC/SC session for approximately 100ms after card insertion
(`SCARD_E_SHARING_VIOLATION`). `CardMonitor._read_card()` retries `SCardConnect` up to
**5 times with 50ms delays** (250ms total budget) before giving up.

### Mitigation 2 — `inserted_fired` guard

`on_removed` is only fired if `on_inserted` previously succeeded. This prevents false
vault-lock events when the card read fails (e.g. the 250ms retry window is exhausted).

### Mitigation 3 — Hybrid WMI / PC/SC monitor

All `SCARD_STATE_EMPTY` events that follow a successful card read are suppressed by the
PC/SC thread (ArmouryCrate killed RF — the card is still physically present). Genuine
physical removal is detected by a separate WMI listener thread watching for
`AsusAtkWmiEvent` with `EventID=180`.

Since `EventID=180` fires on **both** physical insertion and removal, the `inserted_fired`
flag disambiguates: if the event arrives when `inserted_fired=True`, it is treated as a
removal.

```
ArmouryCrate kills RF
    -> SCardGetStatusChange: SCARD_STATE_EMPTY
        -> inserted_fired=True -> suppress on_removed (card still present)
        -> WMI thread continues listening

User physically removes card
    -> AsusAtkWmiEvent EventID=180
        -> inserted_fired=True -> fire on_removed, set inserted_fired=False
```

**Requirement:** `pywin32` must be installed for the WMI thread to activate.
Without it, the library logs a warning and falls back to PC/SC-only detection
(removal events may be missed on ASUS hardware).

---

## Architectural decision records

All non-trivial design decisions are documented as ADRs in the monorepo at
[`retro/docs/adr/`](https://github.com/ElCuboNegro/Keystone/tree/master/retro/docs/adr).

| ADR | Decision |
|-----|---------|
| [ADR-0001](https://github.com/ElCuboNegro/Keystone/blob/master/retro/docs/adr/ADR-0001-pcsc-as-smartcard-abstraction.md) | Use ctypes instead of pyscard — no binary dependency |
| [ADR-0002](https://github.com/ElCuboNegro/Keystone/blob/master/retro/docs/adr/ADR-0002-scard-unpower-card-root-cause.md) | ArmouryCrate root-cause analysis — SCARD_UNPOWER_CARD confirmed |
| [ADR-0003](https://github.com/ElCuboNegro/Keystone/blob/master/retro/docs/adr/ADR-0003-nfccx-no-escape-commands.md) | NfcCx does not support ACR122U escape commands |
| [ADR-0004](https://github.com/ElCuboNegro/Keystone/blob/master/retro/docs/adr/ADR-0004-card-identified-by-uid-only.md) | Read only block 0 — further blocks cause SW=6981 on NfcCx, killing the RF session |
| [ADR-0005](https://github.com/ElCuboNegro/Keystone/blob/master/retro/docs/adr/ADR-0005-linux-port-requires-acr122u.md) | Linux port requires ACR122U (NfcCx is Windows-only) |
| [ADR-0007](https://github.com/ElCuboNegro/Keystone/blob/master/retro/docs/adr/ADR-0007-armorycrate-pcsc-contention-mitigations.md) | SCardConnect retry for ASUS exclusive-lock window |
| [ADR-0010](https://github.com/ElCuboNegro/Keystone/blob/master/retro/docs/adr/ADR-0010-hybrid-wmi-pcsc-monitor.md) | Hybrid WMI + PC/SC monitor for real-time removal detection |
| [ADR-0011](https://github.com/ElCuboNegro/Keystone/blob/master/retro/docs/adr/ADR-0011-two-factor-vault-cryptography.md) | Two-factor vault crypto: PBKDF2 + AES-256-GCM + HMAC deterministic filenames |
| [ADR-0012](https://github.com/ElCuboNegro/Keystone/blob/master/retro/docs/adr/ADR-0012-startup-probe-before-poll-loop.md) | Startup probe before entering the SCardGetStatusChange poll loop |

---

## Development

```bash
git clone https://github.com/ElCuboNegro/Keystone.git
cd Keystone/library
pip install -e ".[dev,vault]"
```

```bash
# Tests (no hardware required)
pytest tests/ -m "not hardware" -v

# Tests with a physical NFC card in the reader
pytest tests/ -v -s

# Type check
mypy keystone_nfc/ --strict

# Lint
ruff check keystone_nfc/ folder_lock.py tests/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributing guide.

---

## License

MIT — see [LICENSE](LICENSE).
