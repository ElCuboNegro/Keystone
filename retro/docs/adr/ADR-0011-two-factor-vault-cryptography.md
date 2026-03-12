# ADR-0011: Two-factor vault encryption — PBKDF2 + AES-256-GCM + HMAC deterministic filenames

**Status:** accepted
**Deciders:** Antigravity (agent), jalba
**Date:** 2026-03-11
**Technical Story:** The vault (`folder_lock.py`) must protect against an attacker who has
the ciphertext but not the physical card. The design must also hide original filenames so a
stolen vault directory reveals nothing about its contents.

---

## Context and Problem Statement

The Keystone NFC card provides a physical token whose UID is unique per card and cannot
be extracted without physical access.  When the card is removed the vault must lock.
The vault contents (filenames, content) must be opaque at rest.

Three questions must be answered:
1. How is the encryption key derived from the card UID and a password?
2. How are individual files encrypted so that tampering is detectable?
3. How are encrypted filenames chosen so that the original path is hidden?

---

## Decision Drivers

- Both factors (card + password) must be required to decrypt — neither alone is sufficient
- A compromised vault directory must reveal nothing about the number, names, or content of files
- An attacker who modifies an `.enc` file must be detected before any plaintext is returned
- Deterministic filenames are needed so that a changed file can be re-encrypted in-place
  without scanning the entire vault (required by `VaultWatcher` real-time sync)
- The crypto must be auditable — only well-understood, standardized primitives

---

## Considered Options

**Key derivation:**
- **A: PBKDF2-HMAC-SHA256** (card UID as salt, 600k iterations)
- **B: Argon2id** (memory-hard, stronger against GPU cracking)
- **C: scrypt** (memory + CPU hard)

**File encryption:**
- **A: AES-256-GCM** (authenticated; single pass)
- **B: AES-256-CBC + HMAC** (encrypt-then-MAC; two passes)
- **C: ChaCha20-Poly1305** (no hardware acceleration needed; same security level)

**Encrypted filename:**
- **A: HMAC-SHA256(key, rel_path)[:8 bytes].hex() + .enc** (deterministic, key-dependent)
- **B: Random UUID per file** (requires a separate index mapping UUID → rel_path)
- **C: Hash of content** (deduplication possible but reveals equal files)

---

## Decision Outcome

**Key derivation: PBKDF2-HMAC-SHA256** — widely available in `cryptography` (OpenSSL),
NIST SP 800-132 compliant, adequate for this use case.  Argon2id would be preferred for
pure password hashing, but here the card UID is an additional 64-bit secret salt that
makes dictionary attacks impractical regardless of iteration count.

600k iterations matches the 2023 OWASP recommendation for PBKDF2-SHA256 and takes
approximately 300ms on typical consumer hardware — acceptable for a one-time unlock event.

**File encryption: AES-256-GCM** — single-pass authenticated encryption, hardware
accelerated on all modern CPUs (AES-NI), provided directly by `cryptography.hazmat`.
The GCM authentication tag (16 bytes, appended by the library) detects tampering before
any plaintext is returned.  The magic header (`KSTNLK2\n`) is used as GCM additional
authenticated data (AAD), binding the file format version to the ciphertext.

**Encrypted filename: HMAC-SHA256(key, rel_path)[:8 bytes].hex()** — deterministic
(allows O(1) lookup without scanning), key-dependent (requires the master key to map
enc name → original path), and collision-resistant in practice (2^64 space for the
8-byte prefix).  A separate index would be an additional attack surface.

---

## Cryptographic Specification

```
master_key  = PBKDF2-HMAC-SHA256(
                  password   = user_password.encode('utf-8'),
                  salt       = card_uid_bytes,          # 8 bytes, ISO 15693 UID
                  iterations = 600_000,
                  dklen      = 32,                      # 256-bit key
              )

enc_name    = HMAC-SHA256(master_key, rel_path.encode('utf-8'))[:8].hex() + '.enc'

blob_format:
    [8  bytes]  magic b'KSTNLK2\n'   (AAD for GCM; also identifies v2 format)
    [12 bytes]  nonce                 (random per file, never reused)
    [N  bytes]  AES-256-GCM(
                    key        = master_key,
                    nonce      = nonce,
                    aad        = magic,
                    plaintext  = uint32-BE(len(rel_path_utf8))
                               + rel_path_utf8
                               + file_content
                )
                # GCM appends a 16-byte authentication tag at the end
```

The original relative path is encrypted inside the ciphertext. Decryption returns both
the path and the content in one authenticated operation.

### Positive Consequences

- Neither factor alone is sufficient: password without card → wrong salt → wrong key;
  card without password → PBKDF2 still required
- Vault filenames are opaque: an attacker with the vault directory cannot enumerate
  what files exist or guess their names
- Any single-bit modification to a `.enc` file raises `InvalidTag` before plaintext is
  returned — no unauthenticated decryption possible
- Real-time sync via `VaultWatcher` works without a separate index: `enc_name_for_path()`
  gives the vault filename in O(1)

### Negative Consequences

- PBKDF2 is weaker than Argon2id against GPU-based password cracking if the card UID is
  ever compromised — acceptable because the card must be physically present
- 8-byte HMAC prefix (2^64 space) is theoretically subject to birthday attacks only when
  a single vault contains > 2^32 files — not a practical concern
- Key rotation (e.g., replacing the card) requires re-encrypting every file in the vault
  — acceptable for a personal security tool; documented in usage notes

---

## Links

- Related: [ADR-0004](ADR-0004-card-identified-by-uid-only.md) — UID is the only card data reliably readable; this is why the UID is used as KDF salt rather than any other card data
- Related: [ADR-0001](ADR-0001-pcsc-as-smartcard-abstraction.md) — PC/SC layer that delivers the UID bytes
- Implementation: `library/folder_lock.py` — `derive_key()`, `encrypt_file()`, `decrypt_file()`, `enc_name_for_path()`
- Test coverage: `library/tests/test_e2e_vault.py` — `test_key_is_32_bytes`, `test_encrypt_decrypt_roundtrip`, `test_wrong_key_raises`, `test_tampered_blob_raises`, `test_enc_name_is_deterministic`
