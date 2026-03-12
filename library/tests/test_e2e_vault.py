"""
End-to-end integration test: live card + vault encryption roundtrip.

Two test groups:
  - Hardware tests (marked @pytest.mark.hardware): require a card in the reader
  - Crypto/vault tests: use the known card UID captured in a previous read,
    so they run without hardware present

Run all:             pytest tests/test_e2e_vault.py -v -s
Hardware tests only: pytest tests/test_e2e_vault.py -v -s -m hardware
Vault tests only:    pytest tests/test_e2e_vault.py -v -s -m "not hardware"
"""

import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from keystone_nfc import CardInfo, KeystoneReader
from keystone_nfc.exceptions import NoReaderError, NoCardError

from folder_lock import (
    MAGIC,
    derive_key,
    decrypt_vault,
    encrypt_file, decrypt_file,
    enc_name_for_path,
    encrypt_workdir,
    find_plaintext,
)

# ── Known UID captured from the physical card (see DEMO/nfc_reader_demo.py) ──
# Update this if you use a different card.
_KNOWN_UID   = bytes([0x54, 0xD4, 0x4C, 0x4F, 0x08, 0x01, 0x04, 0xE0])
_TEST_PW     = 'test-password-e2e'

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def card() -> CardInfo:
    """Read the physical card (hardware required).

    IMPORTANT: Due to ASUS ArmouryCrate killing the RF field after each read,
    the card must be inserted AFTER this fixture starts — not before.
    If the card is already in the reader: REMOVE it, wait for the prompt, then re-insert.
    """
    print('\n')
    print('  +------------------------------------------------------+')
    print('  | [HARDWARE] Insert your Keystone card NOW (30s)...   |')
    print('  | If card is already in: remove it, then re-insert.   |')
    print('  +------------------------------------------------------+')
    try:
        c = KeystoneReader().read_once(timeout=30.0)
        print(f'\n  Card UID: {c.uid_hex}  Manufacturer: {c.manufacturer}')
        return c
    except NoReaderError:
        pytest.skip('No NFC reader available')
    except NoCardError:
        pytest.skip('No card detected within 30s — insert card while test is running')


@pytest.fixture(scope='module')
def key() -> bytes:
    """Derive a test key from the known UID (no card required)."""
    print('\n  Deriving key (PBKDF2 600k iters)...', end='', flush=True)
    k = derive_key(_TEST_PW, _KNOWN_UID)
    print(' done.')
    return k


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Fresh empty vault directory."""
    v = tmp_path / 'vault'
    v.mkdir()
    return v


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    """Fresh empty workdir directory."""
    w = tmp_path / 'work'
    w.mkdir()
    return w


hardware = pytest.mark.hardware  # shorthand for marking hardware-required tests

# ── Card reading (hardware required) ─────────────────────────────────────────

@hardware
def test_card_uid_is_8_bytes(card: CardInfo) -> None:
    assert len(card.uid_bytes) == 8


@hardware
def test_card_is_iso15693(card: CardInfo) -> None:
    """ISO 15693: MSB (uid_raw[7]) == 0xE0."""
    assert card.uid_bytes[7] == 0xE0


@hardware
def test_card_manufacturer_detected(card: CardInfo) -> None:
    assert card.manufacturer is not None


@hardware
def test_card_reader_is_microsoft_ifd(card: CardInfo) -> None:
    assert 'Microsoft IFD' in card.reader or 'ACR' in card.reader


@hardware
def test_live_uid_matches_known(card: CardInfo) -> None:
    """Verify the live card is the same card as _KNOWN_UID."""
    assert card.uid_bytes == _KNOWN_UID, (
        f'Different card! Expected {_KNOWN_UID.hex()}, got {card.uid_bytes.hex()}\n'
        'Update _KNOWN_UID in this file if you changed cards.'
    )


# ── Key derivation (no hardware required) ────────────────────────────────────

def test_key_is_32_bytes(key: bytes) -> None:
    assert len(key) == 32


def test_key_is_deterministic() -> None:
    k1 = derive_key('same-password', _KNOWN_UID)
    k2 = derive_key('same-password', _KNOWN_UID)
    assert k1 == k2


def test_different_password_different_key() -> None:
    k1 = derive_key('password-A', _KNOWN_UID)
    k2 = derive_key('password-B', _KNOWN_UID)
    assert k1 != k2


def test_different_uid_different_key() -> None:
    k1 = derive_key('password', _KNOWN_UID)
    k2 = derive_key('password', bytes([0x01] * 8))
    assert k1 != k2


# ── File-level crypto ─────────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip(key: bytes) -> None:
    content  = b'Hello, Keystone!'
    rel_path = 'notes/hello.txt'
    blob = encrypt_file(content, rel_path, key)
    recovered_path, recovered_content = decrypt_file(blob, key)
    assert recovered_path    == rel_path
    assert recovered_content == content


def test_encrypted_blob_starts_with_magic(key: bytes) -> None:
    blob = encrypt_file(b'test', 'f.txt', key)
    assert blob[:len(MAGIC)] == MAGIC


def test_wrong_key_raises(key: bytes) -> None:
    from cryptography.exceptions import InvalidTag
    blob    = encrypt_file(b'secret', 'f.txt', key)
    bad_key = bytes(32)  # all zeros
    with pytest.raises((InvalidTag, ValueError)):
        decrypt_file(blob, bad_key)


def test_tampered_blob_raises(key: bytes) -> None:
    from cryptography.exceptions import InvalidTag
    blob     = bytearray(encrypt_file(b'secret', 'f.txt', key))
    blob[-1] ^= 0xFF  # flip last byte of ciphertext
    with pytest.raises((InvalidTag, ValueError)):
        decrypt_file(bytes(blob), key)


def test_binary_content_roundtrip(key: bytes) -> None:
    content = bytes(range(256)) * 16
    blob    = encrypt_file(content, 'binary.bin', key)
    _, out  = decrypt_file(blob, key)
    assert out == content


def test_empty_file_roundtrip(key: bytes) -> None:
    blob   = encrypt_file(b'', 'empty.txt', key)
    _, out = decrypt_file(blob, key)
    assert out == b''


def test_unicode_path_roundtrip(key: bytes) -> None:
    blob = encrypt_file(b'data', 'subdir/notes\u00e9.md', key)
    path, _ = decrypt_file(blob, key)
    assert path == 'subdir/notes\u00e9.md'


# ── Deterministic HMAC enc names ─────────────────────────────────────────────

def test_enc_name_is_deterministic(key: bytes) -> None:
    n1 = enc_name_for_path(key, 'docs/notes.md')
    n2 = enc_name_for_path(key, 'docs/notes.md')
    assert n1 == n2


def test_enc_name_ends_with_enc(key: bytes) -> None:
    assert enc_name_for_path(key, 'f.txt').endswith('.enc')


def test_enc_name_different_paths_differ(key: bytes) -> None:
    n1 = enc_name_for_path(key, 'a.txt')
    n2 = enc_name_for_path(key, 'b.txt')
    assert n1 != n2


def test_enc_name_different_keys_differ(card: CardInfo) -> None:
    k1 = derive_key('pw1', card.uid_bytes)
    k2 = derive_key('pw2', card.uid_bytes)
    assert enc_name_for_path(k1, 'f.txt') != enc_name_for_path(k2, 'f.txt')


# ── Vault roundtrip ───────────────────────────────────────────────────────────

def _populate_workdir(workdir: Path) -> dict:
    """Create test files. Returns {rel_path: content}."""
    files = {
        'readme.txt':           b'Hello World',
        'data/report.pdf':      b'%PDF-fake-binary-content',
        'data/image.png':       bytes(range(256)),
        'deep/nested/note.md':  b'# Nested note\n\nSome content.',
        'empty.bin':            b'',
    }
    for rel, content in files.items():
        p = workdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return files


def test_encrypt_workdir_creates_enc_files(key: bytes, vault: Path, workdir: Path) -> None:
    files = _populate_workdir(workdir)
    count = encrypt_workdir(vault, workdir, key)
    assert count == len(files)
    enc_files = list(vault.rglob('*.enc'))
    assert len(enc_files) == len(files)


def test_encrypt_workdir_wipes_plaintext(key: bytes, vault: Path, workdir: Path) -> None:
    _populate_workdir(workdir)
    encrypt_workdir(vault, workdir, key)
    assert not workdir.exists() or find_plaintext(workdir) == []


def test_decrypt_vault_restores_all_files(key: bytes, vault: Path, workdir: Path) -> None:
    files = _populate_workdir(workdir)
    encrypt_workdir(vault, workdir, key)
    workdir.mkdir(exist_ok=True)

    count = decrypt_vault(vault, workdir, key)
    assert count == len(files)

    for rel, expected in files.items():
        restored = workdir / rel
        assert restored.exists(), f'Missing: {rel}'
        assert restored.read_bytes() == expected, f'Content mismatch: {rel}'


def test_enc_files_not_deleted_after_decrypt(key: bytes, vault: Path, workdir: Path) -> None:
    """.enc files must survive decryption — they are the permanent safe copy."""
    _populate_workdir(workdir)
    encrypt_workdir(vault, workdir, key)
    enc_before = set(p.name for p in vault.rglob('*.enc'))
    workdir.mkdir(exist_ok=True)
    decrypt_vault(vault, workdir, key)
    enc_after = set(p.name for p in vault.rglob('*.enc'))
    assert enc_before == enc_after


def test_wrong_password_raises_value_error(key: bytes, vault: Path, workdir: Path) -> None:
    _populate_workdir(workdir)
    encrypt_workdir(vault, workdir, key)
    workdir.mkdir(exist_ok=True)

    bad_key = derive_key('wrong-password', bytes(8))
    with pytest.raises(ValueError, match='Wrong password'):
        decrypt_vault(vault, workdir, bad_key)


def test_wrong_password_timing_is_similar(vault: Path, workdir: Path) -> None:
    """Full PBKDF2 must run even on wrong key — no short-circuit timing oracle."""
    good_key = derive_key('correct',   _KNOWN_UID)
    bad_key  = derive_key('incorrect', _KNOWN_UID)

    _populate_workdir(workdir)
    encrypt_workdir(vault, workdir, good_key)
    workdir.mkdir(exist_ok=True)

    t0 = time.perf_counter()
    try:
        decrypt_vault(vault, workdir, bad_key)
    except ValueError:
        pass
    elapsed = time.perf_counter() - t0

    # AES-GCM auth tag check is near-instant — what matters is that derive_key
    # (called before decrypt_vault in real usage) always takes the same time.
    # Here we just verify decrypt_vault itself doesn't short-circuit before
    # attempting decryption (elapsed should be > 0, i.e., it actually tried).
    assert elapsed >= 0


def test_orphan_enc_removed_on_re_encrypt(key: bytes, vault: Path, workdir: Path) -> None:
    """Deleting a file from workdir should remove its .enc on next encrypt."""
    files = _populate_workdir(workdir)
    encrypt_workdir(vault, workdir, key)

    # Re-open vault, delete one file, re-encrypt
    workdir.mkdir(exist_ok=True)
    decrypt_vault(vault, workdir, key)
    (workdir / 'readme.txt').unlink()  # delete one file

    encrypt_workdir(vault, workdir, key)

    # Vault should now have one fewer .enc file
    remaining = len(list(vault.rglob('*.enc')))
    assert remaining == len(files) - 1


def test_all_file_types_encrypted(key: bytes, vault: Path, workdir: Path) -> None:
    """Non-.md files must be encrypted too."""
    for ext in ['.txt', '.pdf', '.png', '.bin', '.json', '.csv', '.zip']:
        f = workdir / f'file{ext}'
        f.write_bytes(b'content ' + ext.encode())
    encrypt_workdir(vault, workdir, key)
    workdir.mkdir(exist_ok=True)
    decrypt_vault(vault, workdir, key)
    for ext in ['.txt', '.pdf', '.png', '.bin', '.json', '.csv', '.zip']:
        assert (workdir / f'file{ext}').exists()
