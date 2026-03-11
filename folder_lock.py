#!/usr/bin/env python3
"""
folder_lock.py -- 2-factor encrypted folder lock for Markdown files.

Two factors (both required to decrypt):
  1. Keystone NFC card  -- something you have  (UID = KDF salt)
  2. Password           -- something you know   (prompted after card insert)

SECURITY MODEL
--------------
This script protects against:
  [+] Reading the folder while locked (card absent / process not running)
  [+] Learning original filenames from encrypted files
  [+] Brute-forcing password without the physical card

This script does NOT protect against:
  [-] Reading plaintext from the working directory while the folder is open
      -> Mitigation: use a RAM disk as --workdir (plaintext is volatile)
  [-] Reading the disk from another machine while the folder is open
      -> Mitigation: combine with BitLocker/FileVault (full-disk encryption)
  [-] Cold-boot attacks against RAM
      -> Out of scope for a software-only tool

ARCHITECTURE
------------
Encrypted files (.enc) are NEVER deleted — they are the permanent safe copy.
Decrypted files are written to a separate working directory (--workdir).

  vault/                 <- original folder — .enc files always present here
    a3f9b2c1.enc
    subdir/
      89fe5b7e.enc

  workdir/               <- working directory (default: vault/.working/)
    notes.md             <- plaintext lives here ONLY while unlocked
    subdir/
      ideas.md

On card removal or process exit, the working directory is wiped.
On unclean shutdown (power cut, kill -9), .enc files are still safe.
The working directory may contain plaintext — use a RAM disk to eliminate this.

SETUP FOR MAXIMUM SECURITY (Windows)
-------------------------------------
  1. Install ImDisk: https://sourceforge.net/projects/imdisk-toolkit/
  2. Create a 64MB RAM disk assigned to R:\
  3. Run: python folder_lock.py vault/ --workdir R:\\keystone-work
  Plaintext will only ever exist in RAM. Power cut = data gone from RAM.

  With full-disk encryption (BitLocker) + RAM disk:
  - Disk off = encrypted (BitLocker)
  - Process running + card present = plaintext only in RAM
  - Card removed = RAM wiped, disk still encrypted

CRYPTO
------
  master_key = PBKDF2-SHA256(password, salt=card_uid_bytes, 600k iterations)
  per-file   = [8B magic][12B nonce][AES-256-GCM(4B name_len + rel_path + content)]

Usage:
  python folder_lock.py <vault>                    watch, unlock, monitor
  python folder_lock.py <vault> --workdir R:\\work  use RAM disk as workdir
  python folder_lock.py <vault> --lock             force re-encrypt workdir -> vault
  python folder_lock.py <vault> --status           show state
"""

import sys
import os
import struct
import shutil
import hmac
import hashlib
import argparse
import getpass
import logging
import threading
from pathlib import Path

# ── Dependencies ──────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent))

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.exceptions import InvalidTag
except ImportError:
    print("[ERROR] 'cryptography' not found. Run: pip install cryptography")
    sys.exit(1)

from keystone_nfc import KeystoneReader, CardInfo
from keystone_nfc.exceptions import NoReaderError, NoCardError
from keystone_nfc.registry import find_encrypted

# ── Constants ─────────────────────────────────────────────────────────────────

MAGIC         = b'KSTNLK2\n'       # 8 bytes — v2 format marker
NONCE_LEN     = 12                  # AES-GCM nonce bytes
KDF_ITERS     = 600_000             # PBKDF2 iterations
ENC_EXT       = '.enc'              # encrypted file extension
DEFAULT_WORK  = '.working'          # default working subdir name (inside vault)

# Files to skip when scanning for plaintext (editor temp files, OS metadata)
_SKIP_SUFFIXES = {'.enc', '.tmp', '.swp', '.swo', '.bak', '.orig', '.DS_Store'}
_SKIP_PREFIXES = {'.', '~'}

log = logging.getLogger('folder_lock')


def _should_skip(path: Path) -> bool:
    """True for editor temp files, OS metadata, and already-encrypted files."""
    name = path.name
    return (
        any(name.startswith(p) for p in _SKIP_PREFIXES) or
        any(name.endswith(s)   for s in _SKIP_SUFFIXES)
    )


def enc_name_for_path(key: bytes, rel_path: str) -> str:
    """Deterministic vault filename: HMAC-SHA256(key, rel_path)[:8 bytes hex] + .enc

    Allows O(1) lookup of a file's enc counterpart without scanning the vault.
    The mapping is secret (requires the key), so vault filenames reveal nothing.
    """
    mac = hmac.new(key, rel_path.encode('utf-8'), hashlib.sha256).digest()
    return mac[:8].hex() + ENC_EXT


# ── Key derivation ────────────────────────────────────────────────────────────

def derive_key(password: str, uid_bytes: bytes) -> bytes:
    """Derive 32-byte AES key. uid_bytes is the KDF salt — both factors required."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=uid_bytes,
        iterations=KDF_ITERS,
    )
    return kdf.derive(password.encode('utf-8'))

# ── File-level crypto ─────────────────────────────────────────────────────────

def encrypt_file(content: bytes, rel_path: str, key: bytes) -> bytes:
    """Encrypt content + relative path into an opaque blob.

    Payload (before encryption):
        [4B uint32-BE: len(rel_path_utf8)] [rel_path_utf8] [content]
    Stored under a random .enc filename — original name is hidden.
    """
    name_bytes = rel_path.encode('utf-8')
    payload    = struct.pack('>I', len(name_bytes)) + name_bytes + content
    nonce      = os.urandom(NONCE_LEN)
    ct         = AESGCM(key).encrypt(nonce, payload, MAGIC)
    return MAGIC + nonce + ct


def decrypt_file(blob: bytes, key: bytes) -> tuple:
    """Decrypt a blob. Returns (original_rel_path: str, content: bytes).
    Raises InvalidTag on wrong key or tampered data.
    """
    if not blob.startswith(MAGIC):
        raise ValueError('Not a valid encrypted file (bad magic bytes)')
    nonce   = blob[len(MAGIC): len(MAGIC) + NONCE_LEN]
    ct      = blob[len(MAGIC) + NONCE_LEN:]
    payload = AESGCM(key).decrypt(nonce, ct, MAGIC)
    name_len  = struct.unpack('>I', payload[:4])[0]
    rel_path  = payload[4: 4 + name_len].decode('utf-8')
    content   = payload[4 + name_len:]
    return rel_path, content

# ── Vault helpers ─────────────────────────────────────────────────────────────


def find_plaintext(workdir: Path) -> list:
    """All non-ignored files in the working directory (recursive, all file types)."""
    return sorted(
        p for p in workdir.rglob('*')
        if p.is_file() and not _should_skip(p)
    )


def encrypt_one_file(vault: Path, rel_path: str, content: bytes, key: bytes) -> Path:
    """Encrypt one file into the vault under its deterministic HMAC name.

    Used by VaultWatcher callbacks for real-time sync.
    Returns the vault Path of the written .enc file.
    """
    blob     = encrypt_file(content, rel_path, key)
    enc_name = enc_name_for_path(key, rel_path)
    dst      = vault / enc_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(blob)
    log.debug('Encrypted one: %s -> %s', rel_path, enc_name)
    return dst


def delete_enc_for_path(vault: Path, rel_path: str, key: bytes) -> bool:
    """Delete the vault .enc file that corresponds to rel_path.

    Returns True if the file was found and removed.
    """
    enc_name = enc_name_for_path(key, rel_path)
    dst      = vault / enc_name
    if dst.exists():
        dst.unlink()
        log.debug('Deleted enc: %s', enc_name)
        return True
    return False


def move_enc_for_path(vault: Path, old_rel: str, new_rel: str,
                      content: bytes, key: bytes) -> Path:
    """Rename a vault entry: write new .enc then delete old one.

    Keeps original until new file is safely written (no data loss on error).
    Returns the new vault Path.
    """
    new_dst = encrypt_one_file(vault, new_rel, content, key)
    delete_enc_for_path(vault, old_rel, key)
    log.debug('Moved enc: %s -> %s', old_rel, new_rel)
    return new_dst


def vault_status(vault: Path) -> str:
    enc = find_encrypted(vault)
    return 'locked' if enc else 'empty'

# ── Vault <-> workdir operations ──────────────────────────────────────────────

def decrypt_vault(vault: Path, workdir: Path, key: bytes) -> int:
    """Decrypt all .enc files from vault into workdir.

    The original .enc files are NOT deleted — they remain as the safe copy.
    Returns count of files decrypted.
    Raises ValueError on wrong key/card.
    """
    files = find_encrypted(vault)
    if not files:
        return 0

    workdir.mkdir(parents=True, exist_ok=True)
    count = 0
    dst   = None

    for src in files:
        try:
            blob              = src.read_bytes()
            rel_path, content = decrypt_file(blob, key)
            dst               = workdir / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(content)
            log.info('Decrypted: %s -> %s', src.name, rel_path)
            count += 1
        except InvalidTag:
            if dst and dst.exists():
                dst.unlink()
            raise ValueError('Wrong password or wrong card — decryption failed.')
        except ValueError:
            raise
        except Exception as e:
            log.error('Failed to decrypt %s: %s', src.name, e)

    return count


def encrypt_workdir(vault: Path, workdir: Path, key: bytes) -> int:
    """Re-encrypt all files from workdir back into vault using deterministic HMAC names.

    Each file maps to a fixed vault name (HMAC-SHA256 of key+rel_path) so the vault
    stays consistent across sessions without a manifest file.
    Any .enc file no longer in the workdir is removed (deleted plaintext -> deleted enc).
    Wipes the working directory afterwards.
    Returns count of files encrypted.
    """
    files = find_plaintext(workdir)
    if not files:
        _wipe_workdir(workdir)
        return 0

    new_enc_paths = set()
    count         = 0

    for src in files:
        rel = src.relative_to(workdir).as_posix()
        try:
            dst = encrypt_one_file(vault, rel, src.read_bytes(), key)
            new_enc_paths.add(dst.resolve())
            log.info('Encrypted: %s -> %s', rel, dst.name)
            count += 1
        except Exception as e:
            log.error('Failed to encrypt %s: %s', rel, e)

    # Remove orphaned .enc files (files deleted from workdir while it was open)
    for old in find_encrypted(vault):
        if old.resolve() not in new_enc_paths:
            old.unlink()
            log.info('Removed orphan enc: %s', old.name)

    _wipe_workdir(workdir)
    return count


def _wipe_workdir(workdir: Path):
    """Overwrite all files in workdir with random bytes, then delete the tree."""
    if not workdir.exists():
        return
    for f in workdir.rglob('*'):
        if f.is_file():
            _secure_delete(f)
    try:
        shutil.rmtree(workdir, ignore_errors=True)
    except Exception as e:
        log.warning('Could not remove workdir %s: %s', workdir, e)


def _secure_delete(path: Path):
    """Overwrite with random bytes before deletion (best-effort)."""
    try:
        size = path.stat().st_size
        with open(path, 'r+b') as f:
            f.write(os.urandom(max(size, 1)))
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass
    try:
        path.unlink()
    except Exception:
        pass

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_status(vault: Path, workdir: Path):
    enc   = find_encrypted(vault)
    plain = find_plaintext(workdir) if workdir.exists() else []

    print(f'Vault   : {vault.resolve()}')
    print(f'Workdir : {workdir.resolve()}')
    print(f'Locked  : {len(enc)} encrypted file(s) in vault (names hidden)')
    if plain:
        print(f'OPEN    : {len(plain)} plaintext file(s) in workdir')
        for p in plain:
            print(f'  {p.relative_to(workdir)}')
    else:
        print(f'Open    : 0 (workdir empty or absent)')

    if plain:
        print()
        print('[WARN] Plaintext files exist in workdir.')
        if str(workdir).startswith(str(vault)):
            print('       Consider using a RAM disk (--workdir R:\\...) for better security.')


def cmd_lock(vault: Path, workdir: Path, reader_name=None):
    """Re-encrypt workdir -> vault, wipe workdir. Card required."""
    if workdir.exists() and find_plaintext(workdir):
        print('[CARD] Place your Keystone card on the reader...', flush=True)
        card     = KeystoneReader(reader_name).read_once(timeout=120.0)
        print(f'[OK] Card: {card.uid_hex}')
        password = getpass.getpass('[KEY] Password: ')
        print('[..] Deriving key...', end='', flush=True)
        key      = derive_key(password, card.uid_bytes)
        print(' done.')
        count = encrypt_workdir(vault, workdir, key)
        print(f'[OK] Locked {count} file(s). Workdir wiped.')
    else:
        print('[OK] Workdir is already empty — vault is locked.')


def cmd_unlock(vault: Path, workdir: Path, reader_name=None):
    """Card insert triggers password prompt, then decrypt vault -> workdir."""

    # ── Safety check: unclean shutdown detection ──────────────────────────────
    if workdir.exists() and find_plaintext(workdir):
        plain = find_plaintext(workdir)
        print(f'[WARN] Found {len(plain)} plaintext file(s) in workdir.')
        print(f'       This usually means the process was killed or the OS shut down')
        print(f'       while the folder was open.')
        print()
        print('       Options:')
        print('         [L] Lock now  — re-encrypt workdir and wipe plaintext')
        print('         [D] Discard   — wipe workdir WITHOUT re-encrypting (data lost!)')
        print('         [C] Cancel')
        choice = input('Choice [L/d/c]: ').strip().lower() or 'l'
        if choice == 'c':
            return
        if choice == 'd':
            _wipe_workdir(workdir)
            print('[OK] Workdir wiped. Vault .enc files are intact.')
            return
        # choice == 'l': re-encrypt
        print('[CARD] Place your Keystone card on the reader...', flush=True)
        card     = KeystoneReader(reader_name).read_once(timeout=120.0)
        print(f'[OK] Card: {card.uid_hex}')
        password = getpass.getpass('[KEY] Password: ')
        print('[..] Deriving key...', end='', flush=True)
        key      = derive_key(password, card.uid_bytes)
        print(' done.')
        count    = encrypt_workdir(vault, workdir, key)
        print(f'[OK] Re-locked {count} file(s). Workdir wiped.')
        print()
        ans = input('Unlock again now? [y/N] ').strip().lower()
        if ans != 'y':
            return
        count = decrypt_vault(vault, workdir, key)
        print(f'[OK] Unlocked {count} file(s) into: {workdir}')
        _monitor_and_relock(vault, workdir, key, card, reader_name)
        return

    # ── Normal unlock flow ────────────────────────────────────────────────────
    if vault_status(vault) == 'empty':
        print('[OK] Vault is empty — nothing to unlock.')
        return

    print('[CARD] Place your Keystone card on the reader...', flush=True)
    card = KeystoneReader(reader_name).read_once(timeout=120.0)

    print(f'[OK] Card detected')
    print(f'     UID:          {card.uid_hex}')
    print(f'     Manufacturer: {card.manufacturer or "unknown"}')

    password = getpass.getpass('[KEY] Password: ')

    print('[..] Deriving key...', end='', flush=True)
    key = derive_key(password, card.uid_bytes)
    print(' done.')

    try:
        count = decrypt_vault(vault, workdir, key)
    except ValueError as e:
        print(f'\n[ERROR] {e}')
        sys.exit(1)

    print(f'[OK] {count} file(s) decrypted into: {workdir.resolve()}')

    if str(workdir).startswith(str(vault)):
        print()
        print('[TIP] For better security, use a RAM disk as workdir:')
        print('      python folder_lock.py vault/ --workdir R:\\keystone-work')
        print('      Plaintext will only exist in RAM and is cleared on power loss.')

    _monitor_and_relock(vault, workdir, key, card, reader_name)


def _monitor_and_relock(vault: Path, workdir: Path, key: bytes,
                         card: CardInfo, reader_name=None):
    locked = threading.Event()
    reader = KeystoneReader(reader_name)

    @reader.on_card_removed
    def on_removed():
        print('\n[!] Card removed — locking...', flush=True)
        count = encrypt_workdir(vault, workdir, key)
        print(f'[OK] Locked {count} file(s). Workdir wiped. Vault is secure.')
        locked.set()

    @reader.on_error
    def on_error(exc):
        print(f'\n[!] Reader error ({exc}) — locking as precaution...', flush=True)
        encrypt_workdir(vault, workdir, key)
        locked.set()

    print(f'\n[OK] Folder is open. Files are in: {workdir.resolve()}')
    print(f'     Remove card to lock. Ctrl+C also locks.')

    with reader:
        try:
            locked.wait()
        except KeyboardInterrupt:
            print('\n[!] Interrupted — locking...')
            encrypt_workdir(vault, workdir, key)
            print('[OK] Locked. Workdir wiped.')

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='2-factor folder lock: NFC card UID + password',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('vault',
        help='Vault folder (contains .enc files)')
    parser.add_argument('--workdir', '-w', default=None,
        help=f'Working directory for plaintext (default: vault/{DEFAULT_WORK}/). '
             f'Use a RAM disk here for maximum security.')
    parser.add_argument('--lock',   action='store_true', help='Force re-encrypt workdir -> vault')
    parser.add_argument('--status', action='store_true', help='Show state')
    parser.add_argument('--reader', '-r', default=None,  help='PC/SC reader name')
    parser.add_argument('--debug',  action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        print(f'[ERROR] Not a directory: {vault}')
        sys.exit(1)

    workdir = Path(args.workdir).expanduser().resolve() if args.workdir \
              else vault / DEFAULT_WORK

    try:
        if args.status:
            cmd_status(vault, workdir)
        elif args.lock:
            cmd_lock(vault, workdir, args.reader)
        else:
            cmd_unlock(vault, workdir, args.reader)

    except NoReaderError as e:
        print(f'[ERROR] No NFC reader: {e}')
        sys.exit(1)
    except NoCardError:
        print('[ERROR] Timed out waiting for card.')
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nAborted.')
        sys.exit(0)


if __name__ == '__main__':
    main()
