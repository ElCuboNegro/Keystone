# keystone-nfc

Python package for NFC card event monitoring and UID reading via PC/SC.

Works with any ISO 15693 card and any PC/SC-compatible reader.
Primary target: ASUS Keystone NFC hardware (NfcCx built-in reader on Windows).

---

## Platform support

| Platform | PC/SC stack | Tested reader |
|----------|-------------|---------------|
| Windows  | WinSCard (built-in) | NfcCx "Microsoft IFD 0", ACR122U |
| Linux    | pcsc-lite + pcscd   | ACR122U |
| macOS    | pcsc-lite (Homebrew) | ACR122U |

---

## Installation

```bash
# Core package (no runtime dependencies — uses ctypes)
pip install keystone-nfc

# With vault file-watching support
pip install "keystone-nfc[vault]"

# With full GUI demo dependencies
pip install "keystone-nfc[gui]"
```

**Linux prerequisite:**
```bash
sudo apt install pcscd libpcsclite1
sudo systemctl start pcscd
```

---

## Quick start

```python
from keystone_nfc import KeystoneReader

reader = KeystoneReader()

@reader.on_card_inserted
def handle(card):
    print(f'UID:          {card.uid_hex}')
    print(f'Manufacturer: {card.manufacturer}')

@reader.on_card_removed
def removed():
    print('Card removed')

with reader:
    input('Watching for cards — press Enter to stop...')
```

### One-shot synchronous read

```python
card = KeystoneReader().read_once(timeout=30.0)
print(card.uid_hex)      # 'E0 04 01 02 03 04 05 06'
print(card.uid_compact)  # 'E004010203040506'
```

### List available readers

```python
print(KeystoneReader().available_readers())
```

---

## API reference

### `KeystoneReader(reader_name=None)`

| Method | Description |
|--------|-------------|
| `start()` | Start background monitor thread |
| `stop(timeout=3.0)` | Stop monitor thread |
| `read_once(timeout=30.0)` | Block until card detected; returns `CardInfo` |
| `available_readers()` | List all PC/SC reader names |
| `on_card_inserted(fn)` | Decorator: called with `CardInfo` on insert |
| `on_card_removed(fn)` | Decorator: called with no args on removal |
| `on_error(fn)` | Decorator: called with `Exception` on monitor error |

Context manager: `with KeystoneReader() as r: ...` calls `start()`/`stop()` automatically.

### `CardInfo`

| Field | Type | Description |
|-------|------|-------------|
| `uid_bytes` | `bytes` | Raw UID (ISO 15693 = 8 bytes, LSB-first) |
| `uid_hex` | `str` | Space-separated hex, e.g. `'E0 04 01 ...'` |
| `uid_compact` | `str` | No-space hex, e.g. `'E004010203040506'` |
| `block0` | `Optional[bytes]` | Memory block 0, or `None` if unreadable |
| `manufacturer` | `Optional[str]` | Decoded from ISO 15693 UID byte 6 |
| `reader` | `str` | PC/SC reader name |
| `protocol` | `int` | PC/SC protocol (1=T0, 2=T1) |
| `timestamp` | `datetime` | When the card was read |

### Exceptions

| Exception | When raised |
|-----------|-------------|
| `KeystoneError` | Base class |
| `NoReaderError` | No PC/SC reader found |
| `NoCardError` | `read_once()` timed out |
| `CardRemovedError` | Card removed during active operation |
| `PCSCError` | PC/SC API call returned an error code |

---

## Architecture decisions

See [`docs/adr/`](docs/adr/) for all architectural decisions with rationale.
Key decisions:

- **ADR-0001** ctypes over pyscard — no binary dependency, works everywhere
- **ADR-0002** Always `SCARD_LEAVE_CARD` — never power off the RF field
- **ADR-0004** Read only block 0 — reading further blocks causes `SW=6981` on NfcCx,
  which kills the RF session

---

## Development

```bash
pip install -e ".[dev]"
pytest
mypy keystone_nfc --strict
ruff check keystone_nfc
```

---

## License

MIT — see [LICENSE](LICENSE).
